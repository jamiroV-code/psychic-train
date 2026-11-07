"""A5-A9 per-account, per-session, in-process CONNECT relay (loopback only).

The browser is launched with ``--proxy-server=http://127.0.0.1:<port>`` of ONE
relay bound to ONE account, ONE route mode and ONE route/identity revision. It
accepts only ``CONNECT <hostname>:443``, checks the effective allowlist,
resolves and pins a public address with the B2 policy, and opens either a
numeric CONNECT through the admitted upstream (``proxy``) or a numeric origin
socket (``direct``, only under the explicit direct/off predicate). TLS stays
end-to-end between browser and origin. No gateway, route list or shared
service; no credentials reach argv, env, logs, exceptions or CDP. Nothing is
logged; refusal metadata keeps hostnames only.
"""
from __future__ import annotations

import asyncio
import base64
import ipaddress
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from api.data.attention import x_proxy as p
from api.data.attention.x_proxy_private import atomic_json

LISTEN_HOST = "127.0.0.1"  # A9: the only address the relay ever binds
HEADER_LIMIT = 16384
REFUSAL_LIMIT = 50
CONNECT_TIMEOUT = 5.0
# Code-owned bootstrap allowlist used before any surface section is published (A6).
BOOTSTRAP_HOSTS = {"x": ("x.com",), "reddit": ("www.reddit.com",)}
# A6c code-owned per-browser background suffixes (BP1/BP1c observations). Classified
# `background_refused`: refused, counted separately, never forwarded or proposed.
BROWSER_BACKGROUND = {"edge": ("microsoft.com", "bing.com", "office.com", "msn.com", "live.com")}
MODES = ("proxy", "direct", "refuse")
_HOST = re.compile(r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


class RelayFailure(RuntimeError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def require(ok, reason):
    if not ok:
        raise RelayFailure(reason)


def select_mode(config, *, route=None, admitted=False):
    """The shared B2 predicate, chosen once per session (A5). Partial config is `refuse`."""
    paths = tuple(getattr(config, key, None) for key in
                  ("x_proxy_list_path", "x_proxy_assignments_path", "x_proxy_policy_path"))
    required = getattr(config, "x_proxy_required", None)
    if required is False and all(path is None for path in paths):
        return "direct" if route is None else "refuse"
    if (required is True and all(isinstance(path, str) for path in paths)
            and isinstance(route, p.PrivateRoute) and admitted is True):
        return "proxy"
    return "refuse"


def parse_authority(target: bytes) -> str:
    """Strict CONNECT authority: lower-case hostname, port 443; IP literals/userinfo refused."""
    try:
        text = target.decode("ascii")
    except UnicodeError:
        raise RelayFailure("relay_authority") from None
    require("@" not in text and "[" not in text and text.count(":") == 1, "relay_authority")
    host, port = text.split(":")
    require(port == "443", "relay_authority")
    host = host.lower()
    try:
        ipaddress.ip_address(host)
        literal = True
    except ValueError:
        literal = False
    require(not literal and re.fullmatch(r"[0-9.]+", host) is None, "relay_authority")
    require(_HOST.fullmatch(host) is not None, "relay_authority")
    return host


def _matches(host, entries):
    for entry in entries:
        if entry.startswith("."):
            if host.endswith(entry):
                return True
        elif host == entry:
            return True
    return False


@dataclass(frozen=True)
class Admission:
    """Route admission snapshot read before every CONNECT (A8)."""
    revision: str
    expires_at: float  # relay clock seconds
    quarantined: bool = False


class SocketDialer:
    """Production dialer: a plain TCP socket to an already-validated numeric address."""

    def dial(self, host: str, port: int, *, timeout: float) -> socket.socket:
        ipaddress.ip_address(host)
        return socket.create_connection((host, port), timeout=timeout)


def _resolver():
    from api.data.attention.x_proxy_transport import resolve_public
    return resolve_public


class Relay:
    def __init__(self, site, label, mode, *, revision, admission, hosts=None, route=None,
                 browser="edge", resolver=None, dialer=None, proxy_context=None, clock=time.monotonic):
        require(mode in MODES, "proxy_not_admitted")
        require(mode != "refuse", "proxy_not_admitted")
        require(site in BOOTSTRAP_HOSTS and browser in BROWSER_BACKGROUND, "relay_config")
        require((mode == "proxy") == isinstance(route, p.PrivateRoute), "proxy_not_admitted")
        entries = BOOTSTRAP_HOSTS[site] if hosts is None else tuple(hosts)
        require(all(isinstance(h, str) and _HOST.fullmatch(h.lstrip(".")) for h in entries), "relay_config")
        self.site, self.label, self.mode, self.revision = site, label, mode, revision
        self.hosts = entries
        self.background = BROWSER_BACKGROUND[browser]
        self._admission = admission
        self._route = route
        self._resolve = resolver or _resolver()
        self._dialer = dialer or SocketDialer()
        self._clock = clock
        self._proxy_context = proxy_context
        if route is not None and route.url.startswith("https://"):
            self._proxy_context = proxy_context or ssl.create_default_context()
            require(self._proxy_context.check_hostname and self._proxy_context.verify_mode == ssl.CERT_REQUIRED,
                    "proxy_policy")
        self.refusals: dict[str, int] = {}
        self.background_refused: dict[str, int] = {}
        self.refused_other = 0
        self.forwarded = 0
        self.failure = None
        self._tunnels: set = set()
        self._lock = threading.Lock()
        self._loop = None
        self._server = None
        self._thread = None
        self.port = None

    # -- lifecycle ---------------------------------------------------------------------------------
    def start(self) -> int:
        require(self._thread is None, "relay_config")
        ready = threading.Event()
        errors = []

        def run():
            loop = asyncio.new_event_loop()
            self._loop = loop
            try:
                self._server = loop.run_until_complete(
                    asyncio.start_server(self._handle, LISTEN_HOST, 0, limit=HEADER_LIMIT))
                self.port = self._server.sockets[0].getsockname()[1]
                watcher = loop.create_task(self._watch())
            except Exception:
                errors.append("relay_start")
                ready.set()
                loop.close()
                return
            ready.set()
            try:
                loop.run_forever()
            finally:
                watcher.cancel()
                for task in asyncio.all_tasks(loop):
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
                loop.close()

        self._thread = threading.Thread(target=run, name="collector-browser-relay", daemon=True)
        self._thread.start()
        ready.wait(10)
        require(not errors and self.port is not None, "relay_start")
        return self.port

    def close(self):
        loop, thread = self._loop, self._thread
        if loop is None or thread is None:
            return

        async def stop():
            self._server.close()
            self._close_tunnels()
            loop.stop()
        try:
            asyncio.run_coroutine_threadsafe(stop(), loop)
        except RuntimeError:
            pass
        thread.join(10)
        self._thread = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()

    def health(self) -> dict:
        with self._lock:
            return {"relay_refusals": dict(self.refusals), "background_refused": dict(self.background_refused),
                    "refused_other": self.refused_other, "forwarded": self.forwarded,
                    "mode": self.mode, "failure": self.failure}

    # -- enforcement -------------------------------------------------------------------------------
    def _count(self, table, host):
        with self._lock:
            if host in table or len(table) < REFUSAL_LIMIT:
                table[host] = table.get(host, 0) + 1
            else:
                self.refused_other += 1

    def _check_admission(self):
        if self.failure:
            raise RelayFailure(self.failure)
        try:
            snapshot = self._admission()
            reason = None
            if not isinstance(snapshot, Admission):
                reason = "proxy_admission_expired"
            elif snapshot.quarantined:
                reason = "proxy_quarantined"
            elif snapshot.revision != self.revision or self._clock() >= snapshot.expires_at:
                reason = "proxy_admission_expired"
        except Exception:
            reason = "proxy_admission_expired"
        if reason:
            self.failure = reason
            self._close_tunnels()
            raise RelayFailure(reason)

    def _close_tunnels(self):
        for writer in list(self._tunnels):
            writer.transport.abort()
        self._tunnels.clear()

    async def _watch(self):
        while True:
            await asyncio.sleep(.05)
            if self._tunnels:
                try:
                    self._check_admission()
                except RelayFailure:
                    pass

    async def _handle(self, reader, writer):
        upstream = None
        try:
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    header = await reader.readuntil(b"\r\n\r\n")
            except (asyncio.LimitOverrunError, asyncio.IncompleteReadError, TimeoutError, ValueError):
                return
            line = header.split(b"\r\n", 1)[0]
            parts = line.split(b" ")
            if len(parts) != 3 or parts[0] != b"CONNECT" or parts[2] not in (b"HTTP/1.1", b"HTTP/1.0"):
                writer.write(b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
                return
            try:
                host = parse_authority(parts[1])
            except RelayFailure:
                self._count_raw(parts[1])
                writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
                return
            if not _matches(host, self.hosts):
                background = any(host == s or host.endswith("." + s) for s in self.background)
                self._count(self.background_refused if background else self.refusals, host)
                writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
                return
            try:
                self._check_admission()
                upstream = await self._open(host)
            except Exception:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
                return
            up_reader, up_writer = upstream
            with self._lock:
                self.forwarded += 1
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self._tunnels.update((writer, up_writer))
            await asyncio.gather(self._pipe(reader, up_writer), self._pipe(up_reader, writer),
                                 return_exceptions=True)
        except Exception:
            pass
        finally:
            for w in (writer, upstream[1] if upstream else None):
                if w is not None:
                    self._tunnels.discard(w)
                    try:
                        await w.drain()
                    except Exception:
                        pass
                    w.transport.abort() if w.transport else None

    def _count_raw(self, target):
        try:
            host = target.decode("ascii").rsplit(":", 1)[0].strip("[]").lower()
        except UnicodeError:
            host = ""
        if "@" in host or not host or len(host) > 253 or any(c in host for c in "/?#\\ "):
            with self._lock:
                self.refused_other += 1
            return
        self._count(self.refusals, host)

    async def _open(self, host):
        address = p.public_address(await asyncio.wait_for(self._resolve(host, 443), CONNECT_TIMEOUT))
        if self.mode == "direct":
            sock = await asyncio.to_thread(self._dialer.dial, address, 443, timeout=CONNECT_TIMEOUT)
            return await asyncio.open_connection(sock=sock, limit=HEADER_LIMIT)
        route = urlsplit(self._route.url)
        proxy_host = route.hostname
        proxy_address = p.public_address(await asyncio.wait_for(self._resolve(proxy_host, route.port), CONNECT_TIMEOUT))
        sock = await asyncio.to_thread(self._dialer.dial, proxy_address, route.port, timeout=CONNECT_TIMEOUT)
        if route.scheme == "https":
            reader, writer = await asyncio.open_connection(sock=sock, ssl=self._proxy_context,
                                                           server_hostname=proxy_host, limit=HEADER_LIMIT)
        else:
            reader, writer = await asyncio.open_connection(sock=sock, limit=HEADER_LIMIT)
        try:
            original = f"{host}:443".encode("ascii")
            numeric = (f"[{address}]" if ":" in address else address).encode("ascii") + b":443"
            rows = [b"CONNECT " + original + b" HTTP/1.1", b"Host: " + original]
            if self._route.auth is not None:
                token = base64.b64encode(":".join(self._route.auth).encode("utf-8"))
                rows.append(b"Proxy-Authorization: Basic " + token)
            frame = p.ConnectFrame({original: numeric}).feed(b"\r\n".join(rows) + b"\r\n\r\n")
            writer.write(frame)
            async with asyncio.timeout(CONNECT_TIMEOUT):
                reply = await reader.readuntil(b"\r\n\r\n")
            status = reply.split(b"\r\n", 1)[0].split(b" ")
            p.require(len(status) >= 2 and status[1] == b"200", "proxy_response")
            return reader, writer
        except Exception:
            writer.transport.abort()
            raise RelayFailure("proxy_transport") from None

    async def _pipe(self, source, destination):
        try:
            while True:
                data = await source.read(65536)
                if not data:
                    break
                destination.write(data)
                await destination.drain()
        finally:
            try:
                if destination.can_write_eof():
                    destination.write_eof()
            except Exception:
                destination.transport.abort()


def write_health(cache_root, relay: Relay, *, profile_state: str):
    """S-StatusAPI layout `_pc_state/browser_health.json`: hostnames and counts only."""
    data = relay.health()
    atomic_json(Path(cache_root) / "attention" / "_pc_state" / "browser_health.json",
                {"relay_refusals": data["relay_refusals"], "background_refused": data["background_refused"],
                 "profile_state": profile_state})
