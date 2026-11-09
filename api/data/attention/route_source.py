"""Route source feeder (D-33, EXPERIMENT tier): free public proxy lists -> B2 private route list + assignments.

The B2 collector consumes an owner private route list and assignment file (`x_proxy.parse_assignments`); this module
PRODUCES them for the labels the owner names in `x_proxy_experiment_labels` / `reddit_proxy_experiment_identities`.
Every other label, line and opaque ID is carried over byte-for-byte. Nothing here relaxes B2: the collector still
admits each route itself (verified HTTPS, expected exit, fresh blocklists, baseline digest) before any use.

Pipeline, all bounded: owner-allowlisted https list fetch (no off-host redirect, byte/line caps) -> numeric public
HTTP proxies only -> concurrent prescreen (raw CONNECT, real TLS verification of the policy echo origin, exit echo
twice to refuse rotating exits, latency cap, baseline digest) -> exit-country through the SAME verified tunnel from
ipapi.co's keyless JSON (`x_proxy.IPAPI`, already the B2 metadata provider; no paid API, no local GeoIP database) ->
same-country spares -> sticky assignment. A route is replaced only when the collector's pool quarantined it or the
feeder's own probe failed `FAILURE_THRESHOLD` runs in a row; the replacement is a fresh, distinct, same-country spare,
recorded as an opaque change (label, old ID, new ID, reason) and raised as an alert. With no spare the failing route
stays in place (B2 then refuses that account): never a direct/home fallback, never a deletion of a required label.
"""
from __future__ import annotations

import concurrent.futures
import contextlib
import hashlib
import ipaddress
import json
import socket
import ssl
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from api.data.attention import web_queries, x_proxy as p
from api.data.attention.x_proxy_private import atomic_bytes, atomic_json, handle_bytes, read_bounded, state_lock, \
    verified_open

TIER = "experiment"
LIST_BYTES = 2 * 1024 * 1024
LIST_LINES = 50_000
HEAD_LIMIT = 16 * 1024
CANDIDATE_CAP = 300
FAN_OUT = 16
PROBE_TIMEOUT = 8.0
LATENCY_CAP = 5.0
RUN_DEADLINE = 600.0
GEO_PER_RUN = 15
GEO_TTL = timedelta(days=7)
REJECT_TTL = timedelta(hours=6)
REJECT_KEEP = 5000
SPARE_MAX_AGE = timedelta(hours=6)
FAILURE_THRESHOLD = 2
CHANGE_KEEP = 200
REDIRECTS = 3
BAD_PORTS = frozenset({0, 21, 22, 23, 25, 53, 110, 135, 137, 138, 139, 143, 445, 465, 587, 993, 995, 1433, 3306,
                       3389, 5432, 5900})
STATE_DIR = "route_source"
STATUS_FILE = "route_source.json"


class SourceError(Exception):
    """A safe, value-free reason code."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _need(ok: bool, reason: str):
    if not ok:
        raise SourceError(reason)


# --- candidates ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Candidate:
    host: str
    port: int

    @property
    def key(self) -> str:
        return f"{self.host}|{self.port}"

    @property
    def line(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.port}"


def candidate_from_line(text: str) -> Candidate | None:
    """A numeric, globally routable, credential-free HTTP proxy, or None. Never resolves a name."""
    text = text.strip()
    if not text or text.startswith("#") or len(text) > 80 or not text.isprintable():
        return None
    if "://" in text:
        scheme, _, text = text.partition("://")
        if scheme.lower() != "http":
            return None  # SOCKS and credentialed HTTPS are not feeder material
    text = text.rstrip("/")
    if any(c in text for c in "@/?#\\ \t"):
        return None
    if text.startswith("["):
        host, sep, port = text[1:].partition("]:")
    else:
        host, sep, port = text.rpartition(":")
    if not sep or not port.isdigit() or len(port) > 5:
        return None
    try:
        host = p.public_address(host)
    except p.ProxyFailure:
        return None
    number = int(port)
    if not 1 <= number <= 65535 or number in BAD_PORTS:
        return None
    return Candidate(host, number)


def parse_candidates(body: bytes) -> list[Candidate]:
    text = body[:LIST_BYTES].decode("utf-8", "replace")
    seen, out = set(), []
    for raw in text.splitlines()[:LIST_LINES]:
        cand = candidate_from_line(raw)
        if cand is not None and cand.key not in seen:
            seen.add(cand.key)
            out.append(cand)
    return out


def candidate_from_route(route: p.PrivateRoute) -> Candidate | None:
    if route.auth is not None or not route.url.startswith("http://"):
        return None  # an owner credentialed/HTTPS route: only the pool's quarantine signal applies
    return candidate_from_line(route.url)


# --- minimal bounded HTTP/1.1 over a socket ----------------------------------------------------------------------------

def _read_head(sock) -> tuple[int, dict[str, str], bytes]:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        _need(bool(chunk), "closed")
        data.extend(chunk)
        _need(len(data) <= HEAD_LIMIT, "head_too_large")
    head, _, rest = bytes(data).partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    parts = lines[0].split(" ", 2)
    _need(len(parts) >= 2 and parts[0].startswith("HTTP/1.") and parts[1].isdigit(), "bad_status")
    headers = {}
    for line in lines[1:]:
        name, sep, value = line.partition(":")
        _need(bool(sep), "bad_header")
        headers[name.strip().lower()] = value.strip()
    return int(parts[1]), headers, rest


def _read_body(sock, headers: dict[str, str], rest: bytes, limit: int) -> bytes:
    def more() -> bytes:
        chunk = sock.recv(65536)
        return chunk
    buffer = bytearray(rest)
    if headers.get("transfer-encoding", "").lower() == "chunked":
        out = bytearray()
        while True:
            while b"\r\n" not in buffer:
                chunk = more()
                _need(bool(chunk), "truncated")
                buffer.extend(chunk)
                _need(len(buffer) <= limit + HEAD_LIMIT, "too_large")
            size_line, _, tail = bytes(buffer).partition(b"\r\n")
            try:
                size = int(size_line.split(b";", 1)[0].strip(), 16)
            except ValueError:
                raise SourceError("bad_chunk") from None
            buffer = bytearray(tail)
            if size == 0:
                return bytes(out)
            _need(len(out) + size <= limit, "too_large")
            while len(buffer) < size + 2:
                chunk = more()
                _need(bool(chunk), "truncated")
                buffer.extend(chunk)
            out.extend(buffer[:size])
            buffer = buffer[size + 2:]
    if "content-length" in headers:
        _need(headers["content-length"].isdigit(), "bad_length")
        length = int(headers["content-length"])
        _need(length <= limit, "too_large")
        while len(buffer) < length:
            chunk = more()
            _need(bool(chunk), "truncated")
            buffer.extend(chunk)
        return bytes(buffer[:length])
    while True:
        _need(len(buffer) <= limit, "too_large")
        try:
            chunk = more()
        except ssl.SSLError:
            chunk = b""  # a close without close_notify ends an unframed body
        if not chunk:
            return bytes(buffer)
        buffer.extend(chunk)


def _get(sock, host: str, target: str, limit: int) -> tuple[int, dict[str, str], bytes]:
    sock.sendall((f"GET {target} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: route-source/1\r\nAccept: */*\r\n"
                  "Accept-Encoding: identity\r\nConnection: close\r\n\r\n").encode("ascii"))
    status, headers, rest = _read_head(sock)
    _need("content-encoding" not in headers or headers["content-encoding"].lower() == "identity", "encoded")
    return status, headers, (_read_body(sock, headers, rest, limit) if status == 200 else b"")


def _target(url: str) -> tuple[str, int, str]:
    u = urlsplit(url)
    _need(u.scheme == "https" and bool(u.hostname) and u.username is None, "bad_url")
    return u.hostname, u.port or 443, (u.path or "/") + ("?" + u.query if u.query else "")


def default_dial(host: str, port: int, timeout: float):
    return socket.create_connection((host, port), timeout=timeout)


@dataclass
class Net:
    """Injected network seams: `dial(host, port, timeout) -> socket` and the verifying TLS context."""
    dial: Callable = default_dial
    tls: ssl.SSLContext = field(default_factory=ssl.create_default_context)
    timeout: float = PROBE_TIMEOUT
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self):
        _need(self.tls.verify_mode == ssl.CERT_REQUIRED and self.tls.check_hostname, "tls_not_verifying")


def fetch_list(url: str, allowed_hosts, net: Net) -> bytes:
    """One owner-allowlisted public list, directly; same-host https redirects only; bounded bytes."""
    for _ in range(REDIRECTS + 1):
        host, port, target = _target(url)
        _need(host in allowed_hosts and port == 443, "list_host")
        with contextlib.closing(net.dial(host, port, net.timeout)) as raw:
            raw.settimeout(net.timeout)
            with net.tls.wrap_socket(raw, server_hostname=host) as sock:
                status, headers, body = _get(sock, host, target, LIST_BYTES)
        if status in (301, 302, 303, 307, 308):
            location = headers.get("location", "")
            nxt = urlsplit(location)
            _need(nxt.scheme == "https" and nxt.hostname == host and nxt.port in (None, 443), "list_redirect")
            url = location
            continue
        _need(status == 200, "list_status")
        return body
    raise SourceError("list_redirect")


def via_proxy(cand: Candidate, url: str, limit: int, net: Net) -> tuple[bytes, float]:
    """GET `url` through `cand` with a raw CONNECT and real TLS verification of the origin."""
    host, port, target = _target(url)
    started = net.clock()
    try:
        raw = net.dial(cand.host, cand.port, net.timeout)
    except OSError:
        raise SourceError("dead") from None
    with contextlib.closing(raw):
        try:
            raw.settimeout(net.timeout)
            raw.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode("ascii"))
            status, _, rest = _read_head(raw)
        except OSError:
            raise SourceError("dead") from None
        _need(status == 200 and not rest, "no_connect")
        try:
            with net.tls.wrap_socket(raw, server_hostname=host) as sock:
                status, _, body = _get(sock, host, target, limit)
        except ssl.SSLError:
            raise SourceError("tls") from None  # interception or a broken tunnel: never trusted
        except OSError:
            raise SourceError("dead") from None
    _need(status == 200, "origin_status")
    return body, net.clock() - started


def _echo_ip(body: bytes) -> str:
    try:
        doc = p.strict_json(body)
        _need(isinstance(doc, dict) and isinstance(doc.get("ip"), str), "echo")
        return p.public_address(p.normalized_ip(doc["ip"]))
    except p.ProxyFailure:
        raise SourceError("echo") from None


@dataclass(frozen=True)
class Verified:
    cand: Candidate
    exit_ip: str
    latency: float


def prescreen(cand: Candidate, policy: p.Policy, net: Net) -> Verified:
    body, latency = via_proxy(cand, policy.echo, p.SMALL_LIMIT, net)
    _need(latency <= LATENCY_CAP, "slow")
    first = _echo_ip(body)
    second = _echo_ip(via_proxy(cand, policy.echo, p.SMALL_LIMIT, net)[0])
    _need(first == second, "rotating")
    baseline, _ = via_proxy(cand, policy.baseline, p.BASELINE_LIMIT, net)
    _need(hashlib.sha256(baseline).hexdigest() == policy.baseline_sha256, "baseline")
    return Verified(cand, first, latency)


def recheck(cand: Candidate, exit_ip: str, policy: p.Policy, net: Net) -> None:
    body, latency = via_proxy(cand, policy.echo, p.SMALL_LIMIT, net)
    _need(latency <= LATENCY_CAP and _echo_ip(body) == exit_ip, "exit_changed")


def geolocate(cand: Candidate, exit_ip: str, net: Net) -> dict[str, str]:
    """Exit country/timezone as ipapi.co observes the SAME tunnel; unknown is a rejection."""
    body, _ = via_proxy(cand, p.IPAPI, p.SMALL_LIMIT, net)
    try:
        doc = p.strict_json(body)
    except p.ProxyFailure:
        raise SourceError("geo") from None
    _need(isinstance(doc, dict) and all(isinstance(doc.get(k), str) for k in ("ip", "country_code", "timezone")),
          "geo")
    try:
        same = p.normalized_ip(doc["ip"]) == exit_ip
    except p.ProxyFailure:
        same = False
    country = doc["country_code"].upper()
    _need(same and len(country) == 2 and country.isalpha(), "geo")
    return {"country": country, "timezone": doc["timezone"]}


# --- targets, files, state -------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Target:
    label: str
    site: str
    region: str
    timezone: str
    accept_language: str


def targets(config: web_queries.CollectorConfig) -> list[Target]:
    out = []
    for label in config.x_proxy_experiment_labels:
        ident = config.x_account_identities[label]
        out.append(Target(label, "x", ident["region"].split("-", 1)[0], ident["timezone"], ident["accept_language"]))
    for label, ident in sorted(config.reddit_proxy_experiment_identities.items()):
        out.append(Target(label, "reddit", ident["region"], ident["timezone"], ident["accept_language"]))
    return out


def _empty_state() -> dict:
    return {"version": 1, "owned_ids": [], "health": {}, "spares": [], "geo": {}, "quarantine": {}, "rejected": {},
            "changes": []}


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _when(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else None


def compose(old_doc: dict, old_lines: list[str], owned: set[str], wanted: dict[str, tuple[str, dict]]):
    """New (assignments doc, lines). `wanted` maps label -> (proxy_id, entry) for every managed label that has a
    route; an entry whose id already has a line keeps it. Lines referenced by the OLD file are never rewritten, so a
    reader holding the old assignments with the new list (or vice versa within one run) never meets a moved slot:
    new routes take unreferenced slots, then append."""
    accounts = {label: dict(item) for label, item in old_doc["accounts"].items()}
    lines = list(old_lines)
    line_map = dict(old_doc["lines"])
    referenced = set(line_map.values())
    free = [n for n in range(1, len(lines) + 1) if n not in referenced]
    new_ids = {pid for pid, _ in wanted.values()}
    for label, (pid, entry) in wanted.items():
        accounts[label] = {k: entry[k] for k in ("proxy_id", "expected_ip", "region", "timezone",
                                                  "accept_language")}
        if pid not in line_map:
            if free:
                slot = free.pop(0)
                lines[slot - 1] = entry["line"]
            else:
                lines.append(entry["line"])
                slot = len(lines)
            line_map[pid] = slot
    live_ids = {item["proxy_id"] for item in accounts.values()}
    for pid in list(line_map):
        if pid in owned and pid not in live_ids and pid not in new_ids:
            line_map.pop(pid)  # a replaced feeder route: its slot is reusable next time
    return {"version": 1, "lines": line_map, "accounts": accounts}, lines


@dataclass
class Deps:
    net: Net = field(default_factory=Net)
    opener: Callable = verified_open
    publish: Callable = atomic_bytes
    write_state: Callable = atomic_json
    write_status: Callable = atomic_json
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    new_id: Callable[[], str] = lambda: str(uuid.uuid4())
    cache_root: Path | None = None
    repo_root: Path = web_queries.REPO_ROOT
    log: Callable[[str], None] = lambda message: None


@dataclass
class Result:
    state: str
    reason: str
    managed: int = 0
    assigned: int = 0
    spares: int = 0
    replaced: int = 0
    published: bool = False
    alerts: list = field(default_factory=list)
    rejections: dict = field(default_factory=dict)

    def status(self, now: datetime) -> dict:
        return {"version": 1, "tier": TIER, "state": self.state, "reason": self.reason, "checked_at": _iso(now),
                "managed": self.managed, "assigned": self.assigned, "spares": self.spares,
                "replaced": self.replaced, "published": self.published, "alerts": list(self.alerts),
                "rejections": dict(sorted(self.rejections.items()))}


def status_path(cache_root: Path) -> Path:
    return Path(cache_root) / "attention" / "_reports" / STATUS_FILE


def _private(path: Path, policy: p.Policy, deps: Deps, limit: int) -> bytes:
    with deps.opener(path, policy.private_root, repo_root=deps.repo_root, service_sid=policy.service_sid) as stream:
        return handle_bytes(stream, limit)


def _pool_quarantined(cache_root: Path) -> dict[str, str]:
    """label -> proxy_id the collector's X pool currently holds quarantined (read-only; absent means none)."""
    path = Path(cache_root) / "attention" / "_pc_state" / "x_pool.json"
    try:
        doc = json.loads(read_bounded(path, 16 * 1024 * 1024)) if path.exists() else {}
    except (p.ProxyFailure, ValueError):
        return {}
    accounts = doc.get("accounts") if isinstance(doc, dict) else None
    if not isinstance(accounts, dict):
        return {}
    return {label: a.get("proxy_id") for label, a in accounts.items()
            if isinstance(a, dict) and a.get("proxy_health") == "quarantined" and isinstance(a.get("proxy_id"), str)}


def _fits(target: Target, geo: dict, strict_timezone: bool) -> bool:
    return geo.get("country") == target.region and (not strict_timezone or geo.get("timezone") == target.timezone)


def run_once(config_path: Path, deps: Deps | None = None, *, dry_run: bool = False) -> Result:
    deps = deps or Deps()
    from api.data import cache
    cache_root = Path(deps.cache_root or cache.CACHE_ROOT)
    now = deps.now()
    try:
        config = web_queries.load(Path(config_path)).config
    except (OSError, ValueError):
        result = Result("error", "config_invalid")
        deps.write_status(status_path(cache_root), result.status(now))
        return result
    if not config.route_source_enabled:
        result = Result("off", "route_source_off")
        deps.write_status(status_path(cache_root), result.status(now))
        return result
    try:
        policy_path = Path(config.x_proxy_policy_path)
        policy = p.parse_policy(read_bounded(policy_path, p.SMALL_LIMIT), policy_path.parent)
        _need(p.canonical_origin(p.IPAPI, origin_only=False) in policy.origins, "geo_origin_not_allowed")
        state_path = policy.cache_dir / STATE_DIR / "state.json"
        with state_lock(state_path, timeout=1.0):
            result = _run_locked(config, policy, state_path, deps, cache_root, now, dry_run)
    except (ValueError, OSError, KeyError, TypeError):
        result = Result("error", "files_invalid")
    except SourceError as failure:
        result = Result("error", failure.reason)
    except p.ProxyFailure as failure:
        result = Result("error", "busy" if failure.reason == "proxy_lock" else failure.reason)
    deps.write_status(status_path(cache_root), result.status(now))
    return result


def _run_locked(config, policy, state_path, deps: Deps, cache_root: Path, now: datetime, dry_run: bool) -> Result:
    net = deps.net
    started = net.clock()
    list_path, assign_path = Path(config.x_proxy_list_path), Path(config.x_proxy_assignments_path)
    reddit_labels = tuple(a["label"] for a in config.reddit_browser_accounts)
    identities = config.x_account_identities if config.x_identity_enabled else None
    _need(list_path.exists() == assign_path.exists(), "partial_route_files")
    if list_path.exists():
        list_body = _private(list_path, policy, deps, 1024 * 1024)
        assign_body = _private(assign_path, policy, deps, p.SMALL_LIMIT)
        current = p.parse_assignments(assign_body, list_body, config.x_accounts, required=False,
                                      identities=identities, reddit_labels=reddit_labels)
        old_doc = json.loads(assign_body)
        old_lines = list_body.decode("utf-8").splitlines()
    else:
        current, old_doc, old_lines = {}, {"version": 1, "lines": {}, "accounts": {}}, []
    state = _empty_state()
    if state_path.exists():
        loaded = json.loads(_private(state_path, policy, deps, 4 * 1024 * 1024))
        if isinstance(loaded, dict) and set(loaded) == set(state) and loaded.get("version") == 1:
            state = loaded
    owned = set(state["owned_ids"])
    strict_tz = policy.metadata_provider == "ipapi"
    wanted_targets = targets(config)
    result = Result("ok", "steady", managed=len(wanted_targets))
    reject = result.rejections

    def count(reason):
        reject[reason] = reject.get(reason, 0) + 1

    # Expire bounded memories.
    state["quarantine"] = {ip: until for ip, until in state["quarantine"].items() if (_when(until) or now) > now}
    state["rejected"] = dict(list({k: v for k, v in state["rejected"].items()
                                   if (_when(v) or now) > now}.items())[-REJECT_KEEP:])
    state["geo"] = {ip: g for ip, g in state["geo"].items() if (_when(g.get("at")) or now) > now - GEO_TTL}
    quarantined_exits = set(state["quarantine"])

    # 1. Health of the current managed routes (sticky: a healthy route is never rotated).
    pool_quarantine = _pool_quarantined(cache_root)
    replace: dict[str, str] = {}
    pool_ = concurrent.futures.ThreadPoolExecutor(max_workers=FAN_OUT)
    try:
        probes = {}
        for t in wanted_targets:
            item = current.get(t.label)
            if item is None:
                replace[t.label] = "unassigned"
                continue
            cand = candidate_from_route(item.route)
            if cand is not None:
                probes[t.label] = pool_.submit(recheck, cand, item.expected_ip, policy, net)
        health = state["health"]
        for label, future in probes.items():
            pid = current[label].proxy_id
            try:
                future.result()
                health.pop(pid, None)
            except SourceError as failure:
                count("assigned_" + failure.reason)
                health[pid] = int(health.get(pid, 0)) + 1
                if health[pid] >= FAILURE_THRESHOLD:
                    replace[label] = "probe_failed"
        for t in wanted_targets:
            item = current.get(t.label)
            if item is not None and t.site == "x" and pool_quarantine.get(t.label) == item.proxy_id:
                replace[t.label] = "pool_quarantined"
        assigned_exits = {item.expected_ip for item in current.values()}

        # 2. Re-verify spares; drop stale, quarantined, assigned or changed ones.
        spares = []
        checks = {}
        for spare in state["spares"]:
            cand = candidate_from_line(spare.get("line", ""))
            fresh = (_when(spare.get("verified_at")) or now - SPARE_MAX_AGE * 2) > now - SPARE_MAX_AGE
            if cand is None or spare.get("exit_ip") in quarantined_exits | assigned_exits:
                continue
            checks[cand.key] = (spare, pool_.submit(recheck, cand, spare["exit_ip"], policy, net)) if not fresh \
                else (spare, None)
        for spare, future in checks.values():
            try:
                if future is not None:
                    future.result()
                    spare = {**spare, "verified_at": _iso(now)}
                spares.append(spare)
            except SourceError as failure:
                count("spare_" + failure.reason)

        # 3. Demand per target: one route for each needing replacement plus the owner's spare depth.
        def available(t):
            return [s for s in spares if _fits(t, s, strict_tz)]

        def deficit():
            need = 0
            for country_tz in {(t.region, t.timezone if strict_tz else None) for t in wanted_targets}:
                group = [t for t in wanted_targets if (t.region, t.timezone if strict_tz else None) == country_tz]
                want = config.route_source_spares_per_country + sum(1 for t in group if t.label in replace)
                need += max(0, want - len(available(group[0])))
            return need

        if wanted_targets and deficit() > 0:
            known = {s["line"] for s in spares} | {c.line for c in (candidate_from_route(i.route)
                                                                   for i in current.values()) if c}
            candidates, seen = [], set()
            for url in config.route_source_list_urls:
                if net.clock() - started > RUN_DEADLINE:
                    break
                try:
                    found = parse_candidates(fetch_list(url, config.route_source_allowed_hosts, net))
                except (SourceError, OSError, ssl.SSLError) as failure:
                    count("list_" + getattr(failure, "reason", "unreachable"))
                    continue
                for cand in found:
                    if cand.key in seen or cand.line in known or cand.key in state["rejected"]:
                        continue
                    seen.add(cand.key)
                    candidates.append(cand)
            candidates = candidates[:CANDIDATE_CAP]
            futures = {pool_.submit(prescreen, cand, policy, net): cand for cand in candidates}
            passed = []
            for future in concurrent.futures.as_completed(futures):
                cand = futures[future]
                try:
                    passed.append(future.result())
                except SourceError as failure:
                    count(failure.reason)
                    state["rejected"][cand.key] = _iso(now + REJECT_TTL)
            passed.sort(key=lambda v: (v.latency, v.cand.key))
            exits = assigned_exits | {s["exit_ip"] for s in spares}
            geo_calls = 0
            for verified in passed:
                if deficit() <= 0 or net.clock() - started > RUN_DEADLINE:
                    break
                if verified.exit_ip in exits or verified.exit_ip in quarantined_exits:
                    count("duplicate_exit" if verified.exit_ip in exits else "quarantined_exit")
                    continue
                geo = state["geo"].get(verified.exit_ip)
                if geo is None:
                    if geo_calls >= GEO_PER_RUN:
                        count("geo_budget")
                        continue
                    geo_calls += 1
                    try:
                        geo = {**geolocate(verified.cand, verified.exit_ip, net), "at": _iso(now)}
                    except SourceError as failure:
                        count(failure.reason)
                        state["rejected"][verified.cand.key] = _iso(now + REJECT_TTL)
                        continue
                    state["geo"][verified.exit_ip] = geo
                if not any(_fits(t, geo, strict_tz) for t in wanted_targets):
                    count("wrong_country")
                    state["rejected"][verified.cand.key] = _iso(now + REJECT_TTL)
                    continue
                exits.add(verified.exit_ip)
                spares.append({"line": verified.cand.line, "exit_ip": verified.exit_ip, "country": geo["country"],
                               "timezone": geo["timezone"], "verified_at": _iso(now)})
    finally:
        pool_.shutdown(wait=True, cancel_futures=True)

    # 4. Plan: replacements take a fresh, distinct, same-country spare; otherwise keep the old route and alert.
    wanted: dict[str, tuple[str, dict]] = {}
    planned, remaining = [], list(spares)
    for t in wanted_targets:
        reason = replace.get(t.label)
        if reason is None:
            continue
        choice = next((s for s in remaining if _fits(t, s, strict_tz)), None)
        if choice is None:
            result.alerts.append({"code": "no_spare", "site": t.site})
            continue
        remaining.remove(choice)
        pid = deps.new_id()
        wanted[t.label] = (pid, {"proxy_id": pid, "expected_ip": choice["exit_ip"], "region": t.region,
                                 "timezone": t.timezone, "accept_language": t.accept_language, "line": choice["line"]})
        planned.append((t, current.get(t.label), pid, reason))

    # 5. Compose, validate with the REAL B2 loader, publish atomically (list first; old slots never move).
    new_doc, new_lines = compose(old_doc, old_lines, owned, wanted)
    if wanted and set(config.x_accounts) - set(new_doc["accounts"]):
        # A file without every X label would refuse every account: keep the old files and the spares.
        result.alerts.append({"code": "x_labels_unassigned", "site": "x"})
        wanted, planned, remaining = {}, [], spares
        new_doc, new_lines = old_doc, old_lines
    if wanted:
        assign_bytes = json.dumps(new_doc, separators=(",", ":"), sort_keys=True).encode("utf-8")
        list_bytes = ("\n".join(new_lines) + "\n").encode("utf-8")
        p.parse_assignments(assign_bytes, list_bytes, config.x_accounts, required=True,
                            identities=identities, reddit_labels=reddit_labels)
        if not dry_run:
            deps.publish(list_path, list_bytes, service_sid=policy.service_sid)
            deps.publish(assign_path, assign_bytes, service_sid=policy.service_sid)
            result.published = True
        owned = (owned | {pid for pid, _ in wanted.values()}) & set(new_doc["lines"])
    for t, old, pid, reason in planned:
        if old is not None:
            state["quarantine"][old.expected_ip] = _iso(now + timedelta(seconds=config.x_proxy_quarantine_seconds))
            state["health"].pop(old.proxy_id, None)
            result.replaced += 1
            result.alerts.append({"code": "route_replaced", "site": t.site})
        state["changes"] = (state["changes"] + [{"at": _iso(now), "label": t.label,
                                                 "from": None if old is None else old.proxy_id,
                                                 "to": pid, "reason": reason}])[-CHANGE_KEEP:]
    spares = remaining
    result.spares = len(spares)
    result.assigned = sum(1 for t in wanted_targets if t.label in new_doc["accounts"])
    state["owned_ids"] = sorted(owned)
    state["spares"] = spares
    if not dry_run:
        deps.write_state(state_path, state, service_sid=policy.service_sid)
    problems = [a["code"] for a in result.alerts if a["code"] != "route_replaced"]
    if problems:
        result.state, result.reason = "degraded", problems[0]
    elif result.replaced:
        result.reason = "replaced"
    elif wanted:
        result.reason = "assigned"
    for alert in result.alerts:
        deps.log(f"route_source alert: {alert['code']} ({alert['site']})")
    return result
