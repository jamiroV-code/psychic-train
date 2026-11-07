"""Test-only shared seams for the collector finish plan (S-Fixtures).

PERMITTED injection seams are exactly those named in ``PERMITTED_SEAMS``; every
fixture that replaces a dependency names its seam through ``require_permitted``.
The FORBIDDEN list (``run_unit``, real ``search_raw`` dispatch, pool/selection,
the reader bootstrap request path, the relay policy code, ``browser_host``,
the CDP client, ``browser_selftest``) is guard-tested by the E2E.

A6b: fixtures replace ONLY the relay ``Dialer`` and the resolver's answer
source. The REAL B2 public-address policy (``x_proxy.public_address``) still
validates the synthetic public-class token; the fixture dialer maps that exact
token to a loopback listener. Nothing here is reachable from production code,
configuration or environment.
"""
from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import shutil
import socket
import sys
from pathlib import Path

from api.data.attention import x_proxy as p


PERMITTED_SEAMS = (
    "temporary_paths",
    "clock_and_wait",
    "memory_rss_inspector",
    "acl_inspector",
    "spawn_launcher",
    "resolver_answer_source",
    "relay_dialer",
    "synthetic_trust_roots",
    "transaction_id_parser",
)
FORBIDDEN_REPLACEMENTS = (
    "run_unit",
    "search_raw_dispatch",
    "pool_selection",
    "reader_bootstrap_request",
    "relay_policy",
    "browser_host",
    "cdp_client",
    "browser_selftest",
)
PARSER_QUALIFICATION = (
    "With the deterministic transaction-ID parser substituted, fixture runs exercise the real "
    "bootstrap REQUEST path but NOT the real transaction-ID parser; no scenario claims the parser "
    "was exercised (it stays covered only by the existing B1/B2 tests).")
NATIVE_CONTAINMENT_GAP = (
    "BP13 INCONCLUSIVE: install_network_denial is a Python-level audit-hook guard; it does not "
    "intercept native curl or Chromium sockets or arbitrary grandchildren and is not a universal "
    "sandbox. Native paths claim only 'no non-loopback attempt observed through the instrumented paths'.")

# The BP1/BP7 synthetic public-class numeric token. Never dialed: the fixture
# dialer maps it to a loopback listener.
SYNTHETIC_PUBLIC_TOKEN = "93.184.216.34"
X_STATIC_ORIGIN = "abs.twimg.com"
REDDIT_FEED_ORIGIN = "www.reddit.com"  # the .rss feeds share the www origin
SYNTHETIC_HOSTS = ("x.com", X_STATIC_ORIGIN, "www.reddit.com", "gql-fed.reddit.com", REDDIT_FEED_ORIGIN)
GIT_OPENSSL = Path("C:/Program Files/Git/usr/bin/openssl.exe")


def require_permitted(seam: str) -> str:
    if seam in FORBIDDEN_REPLACEMENTS:
        raise AssertionError(f"forbidden fixture replacement: {seam}")
    if seam not in PERMITTED_SEAMS:
        raise AssertionError(f"unlisted fixture seam: {seam}")
    return seam


def openssl_binary() -> str:
    """OpenSSL preflight with the Git-for-Windows fallback. Missing FAILS, never skips."""
    binary = shutil.which("openssl")
    if binary is None and GIT_OPENSSL.is_file():
        binary = str(GIT_OPENSSL)
    if binary is None:
        raise AssertionError("mandatory TLS fixtures require an OpenSSL executable")
    return binary


def synthetic_resolver(answers: dict[str, str]):
    """Resolver whose ANSWER SOURCE is a fixture table; the answer still passes the real policy."""
    require_permitted("resolver_answer_source")
    table = dict(answers)

    async def resolve(host: str, port: int) -> str:
        if host not in table:
            raise AssertionError("fixture resolver rejected non-fixture host")
        return p.public_address(table[host])
    return resolve


class FixtureDialer:
    """A6b relay Dialer: maps exact numeric tokens to loopback listeners and records each dial."""

    def __init__(self, mapping: dict[str, tuple[str, int]]):
        require_permitted("relay_dialer")
        for token, (host, _port) in mapping.items():
            if not ipaddress.ip_address(host).is_loopback:
                raise AssertionError("fixture dialer target must be loopback")
            ipaddress.ip_address(token)
        self.mapping = dict(mapping)
        self.dialed: list[tuple[str, int]] = []

    def dial(self, host: str, port: int, *, timeout: float) -> socket.socket:
        if host not in self.mapping:
            raise AssertionError("fixture dialer refused unmapped destination")
        self.dialed.append((host, port))
        return socket.create_connection(self.mapping[host], timeout=timeout)


class FakeClock:
    """Injected clock and wait; time advances only through waits."""

    def __init__(self, start: float):
        require_permitted("clock_and_wait")
        self.current = float(start)
        self.waits: list[float] = []

    def now(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise AssertionError("negative wait")
        self.waits.append(seconds)
        self.current += seconds

    async def wait(self, seconds: float) -> None:
        self.sleep(seconds)
        await asyncio.sleep(0)


class ScriptedInspector:
    """Memory/RSS or ACL inspector returning scripted observations; exhaustion fails loudly."""

    def __init__(self, observations, seam: str = "memory_rss_inspector"):
        require_permitted(seam)
        self.observations = list(observations)
        self.calls: list[tuple] = []

    def __call__(self, *args):
        if not self.observations:
            raise AssertionError("scripted inspector exhausted")
        self.calls.append(args)
        return self.observations.pop(0)


def spawn_launcher(module: str, *args: str) -> list[str]:
    """Constructor-injected spawn command for test modules (A13); no production switch."""
    require_permitted("spawn_launcher")
    return [sys.executable, "-m", module, *args]


@contextlib.contextmanager
def loopback_resolution():
    """In-process name mapping of the fixture HOSTS to 127.0.0.1 (other names fail)."""
    from api.tests.data.attention.proxy_wire_fixture import HOSTS
    original = socket.getaddrinfo

    def resolve(host, port, *args, **kwargs):
        if host not in HOSTS and host not in ("127.0.0.1", "localhost"):
            raise AssertionError("fixture resolution rejected non-fixture host")
        return original("127.0.0.1", port, *args, **kwargs)
    socket.getaddrinfo = resolve
    try:
        yield
    finally:
        socket.getaddrinfo = original


class NetworkDenied(RuntimeError):
    pass


def _loopback(host) -> bool:
    if host in (None, "localhost"):
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    try:
        return ipaddress.ip_address(str(host).split("%", 1)[0]).is_loopback
    except ValueError:
        return False


_installed = False


def install_network_denial() -> None:
    """Python-level denial of non-loopback lookups/connects for SPAWNED fixture processes.

    Audit hooks cannot be removed, so only fixture entrypoints call this. See
    NATIVE_CONTAINMENT_GAP for what it does not cover.
    """
    global _installed
    if _installed:
        return

    def audit(event, args):
        if event == "socket.getaddrinfo" and not _loopback(args[0]):
            raise NetworkDenied("fixture process denied a non-loopback lookup")
        if event in ("socket.connect", "socket.sendto"):
            address = args[1] if event == "socket.connect" else args[-1]
            if not isinstance(address, tuple) or not _loopback(address[0]):
                raise NetworkDenied("fixture process denied a non-loopback connect")
    sys.addaudithook(audit)
    _installed = True
