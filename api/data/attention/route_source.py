"""Route source feeder (D-33, EXPERIMENT tier): free public proxy lists -> B2 private route list + assignments.

The B2 collector consumes an owner private route list and assignment file (`x_proxy.parse_assignments`); this module
PRODUCES them for the labels the owner names in `x_proxy_experiment_labels` / `reddit_proxy_experiment_identities`.
Every other label, line and opaque ID is carried over byte-for-byte. Nothing here relaxes B2: the collector still
admits each route itself (verified HTTPS, expected exit, fresh blocklists, baseline digest) before any use.

Pipeline, all bounded: owner-allowlisted https list fetch (no off-host redirect, byte/line caps) -> numeric public
HTTP proxies only -> a persistent private candidate BANK (first seen, last ok, ok/fail streaks, exit, country, latency
EWMA, dead-until backoff) -> one whole-bank scan per pass under a wall-clock budget with bounded fan-out and a short
connect timeout (assigned routes first, never-probed candidates next, then known ones by score; known-dead skipped
until their backoff expires) -> prescreen (raw CONNECT, real TLS verification of the policy echo origin, exit echo
twice to refuse rotating exits, latency cap, baseline digest) -> exit-country through the SAME verified tunnel from
ipapi.co's keyless JSON (`x_proxy.IPAPI`, already the B2 metadata provider; no paid API, no local GeoIP database) ->
target-site reachability (verified TLS `GET /` of the public landing page, no cookies; non-200 or a block page is a
refusal for that site) -> scored same-country spares -> sticky assignment. A managed route is replaced PRE-EMPTIVELY
when the collector's pool quarantined it, its own probe failed once, its site check failed, or its latency degraded,
and only when a verified, distinct, same-country candidate exists; all replacements of a pass are published as ONE
change (B2 re-revisions accounts on any list change) and each is recorded as an opaque change (label, old ID, new ID,
reason) and raised as an alert. Without a candidate the route stays in place (B2 then refuses that account) and the
pass records `no_spare:<country>`: never a direct/home fallback, never a deletion of a required label.
"""
from __future__ import annotations

import concurrent.futures
import contextlib
import threading
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
PROBE_TIMEOUT = 8.0
CONNECT_TIMEOUT = 3.0  # dead hosts dominate a public list; a short dial keeps them from dominating the wall clock
LATENCY_CAP = 5.0
DEGRADED_LATENCY = 3.0  # an assigned route whose latency EWMA exceeds this is replaced when a better one exists
EWMA = 0.3
GEO_PER_RUN = 60
GEO_TTL = timedelta(days=7)
BANK_MAX = 20_000
BANK_FORGET = timedelta(days=3)  # unlisted this long and not live: forgotten
DEAD_TTL = timedelta(hours=6)  # never-ok candidates: 6 h, doubling per failure
SHORT_DEAD_TTL = timedelta(minutes=30)  # once-ok candidates: 30 min, doubling per failure
DEAD_TTL_MAX = timedelta(hours=24)
REACH_TTL = timedelta(hours=1)
LIVE_WINDOW = timedelta(hours=2)  # `--coverage`: verified within this window
STATE_LIMIT = 16 * 1024 * 1024
SITE_LIMIT = 256 * 1024
SITE_URLS = {"x": "https://x.com/", "reddit": "https://www.reddit.com/"}
# Lower-cased fragments of block/interstitial pages. UNVERIFIED live: chosen from public knowledge of Cloudflare and
# Reddit network-security pages; a false positive only costs a candidate, never admits one.
BLOCK_MARKERS = (b"attention required! | cloudflare", b"cf-chl", b"just a moment...", b"access denied",
                 b"blocked by network security", b"whoa there, pardner", b"too many requests")
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


def _read_body(sock, headers: dict[str, str], rest: bytes, limit: int, truncate: bool = False) -> bytes:
    """The body, at most `limit` bytes. Over the limit: an error, or with `truncate` the first `limit` bytes."""
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
            if truncate and len(out) + size > limit:
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
        if truncate:
            length = min(length, limit)
        _need(length <= limit, "too_large")
        while len(buffer) < length:
            chunk = more()
            _need(bool(chunk), "truncated")
            buffer.extend(chunk)
        return bytes(buffer[:length])
    while True:
        if truncate and len(buffer) > limit:
            return bytes(buffer[:limit])
        _need(len(buffer) <= limit, "too_large")
        try:
            chunk = more()
        except ssl.SSLError:
            chunk = b""  # a close without close_notify ends an unframed body
        if not chunk:
            return bytes(buffer)
        buffer.extend(chunk)


def _get(sock, host: str, target: str, limit: int, truncate: bool = False) -> tuple[int, dict[str, str], bytes]:
    sock.sendall((f"GET {target} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: route-source/1\r\nAccept: */*\r\n"
                  "Accept-Encoding: identity\r\nConnection: close\r\n\r\n").encode("ascii"))
    status, headers, rest = _read_head(sock)
    _need("content-encoding" not in headers or headers["content-encoding"].lower() == "identity", "encoded")
    return status, headers, (_read_body(sock, headers, rest, limit, truncate) if status == 200 else b"")


def _target(url: str) -> tuple[str, int, str]:
    u = urlsplit(url)
    _need(u.scheme == "https" and bool(u.hostname) and u.username is None, "bad_url")
    return u.hostname, u.port or 443, (u.path or "/") + ("?" + u.query if u.query else "")


def default_dial(host: str, port: int, timeout: float):
    return socket.create_connection((host, port), timeout=timeout)


@dataclass
class Net:
    """Injected network seams: `dial(host, port, timeout) -> socket` and the verifying TLS context. Proxy dials use
    `connect_timeout`; every read/write after the dial uses `timeout`."""
    dial: Callable = default_dial
    tls: ssl.SSLContext = field(default_factory=ssl.create_default_context)
    timeout: float = PROBE_TIMEOUT
    connect_timeout: float = CONNECT_TIMEOUT
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


def via_proxy(cand: Candidate, url: str, limit: int, net: Net, truncate: bool = False) -> tuple[bytes, float]:
    """GET `url` through `cand` with a raw CONNECT and real TLS verification of the origin."""
    host, port, target = _target(url)
    started = net.clock()
    try:
        raw = net.dial(cand.host, cand.port, net.connect_timeout)
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
                status, _, body = _get(sock, host, target, limit, truncate)
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


def recheck(cand: Candidate, exit_ip: str, policy: p.Policy, net: Net) -> float:
    """One echo through `cand`: the same exit within the latency cap. Returns the latency."""
    body, latency = via_proxy(cand, policy.echo, p.SMALL_LIMIT, net)
    _need(latency <= LATENCY_CAP, "slow")
    _need(_echo_ip(body) == exit_ip, "exit_changed")
    return latency


def reach(cand: Candidate, site: str, net: Net) -> None:
    """The target site's public landing page through `cand`: verified TLS, `GET /` without cookies, status 200 and
    no block/interstitial marker in its first `SITE_LIMIT` bytes. A read of a public page only."""
    body, _ = via_proxy(cand, SITE_URLS[site], SITE_LIMIT, net, truncate=True)
    lower = body.lower()
    _need(not any(marker in lower for marker in BLOCK_MARKERS), "blocked")


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
    return {"version": 2, "owned_ids": [], "assigned_at": {}, "bank": {}, "spares": [], "geo": {}, "quarantine": {},
            "changes": []}


def _load_state(doc) -> dict:
    """The private feeder state; a v1 state keeps its owned IDs, quarantine, geo cache and change log (its spares
    and rejection memory are re-earned by the bank)."""
    state = _empty_state()
    if isinstance(doc, dict) and doc.get("version") == 2 and set(doc) == set(state):
        return doc
    if isinstance(doc, dict) and doc.get("version") == 1:
        for key in ("owned_ids", "geo", "quarantine", "changes"):
            if key in doc:
                state[key] = doc[key]
    return state


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
    clock: Callable[[], float] = time.monotonic  # the scan's wall-clock budget
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
    bank: dict = field(default_factory=dict)

    def status(self, now: datetime) -> dict:
        return {"version": 1, "tier": TIER, "state": self.state, "reason": self.reason, "checked_at": _iso(now),
                "managed": self.managed, "assigned": self.assigned, "spares": self.spares,
                "replaced": self.replaced, "published": self.published, "alerts": list(self.alerts),
                "rejections": dict(sorted(self.rejections.items())), "bank": dict(self.bank)}


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


# --- the candidate bank and its scanner ------------------------------------------------------------------------------

def _entry(line: str, now: datetime) -> dict:
    return {"line": line, "first_seen": _iso(now), "last_listed": _iso(now), "last_probe": None, "last_ok": None,
            "ok_streak": 0, "fail_streak": 0, "exit_ip": None, "country": None, "timezone": None, "latency": None,
            "dead_until": None, "reach": {}, "reach_at": None}


def score(entry: dict, now: datetime) -> float:
    """Higher is better: uptime streak and age in the bank earn, latency and recent failures cost."""
    if entry["last_ok"] is None:
        return float("-inf")
    age_hours = max(0.0, (now - (_when(entry["first_seen"]) or now)).total_seconds() / 3600)
    return (min(entry["ok_streak"], 20) * 5 + min(age_hours, 72) * 0.5
            - (entry["latency"] if entry["latency"] is not None else LATENCY_CAP) * 10 - entry["fail_streak"] * 50)


def _dead(entry: dict, now: datetime) -> bool:
    until = _when(entry["dead_until"])
    return until is not None and until > now


def _evict(bank: dict, keep: set, now: datetime) -> None:
    """Bound the bank: forget long-unlisted entries that are not live, then the least valuable over `BANK_MAX`."""
    forget, live_since = now - BANK_FORGET, now - LIVE_WINDOW
    for key in [k for k, e in bank.items() if k not in keep and (_when(e["last_listed"]) or now) < forget
                and (_when(e["last_ok"]) or forget) < live_since]:
        del bank[key]
    excess = len(bank) - BANK_MAX
    if excess > 0:
        ranked = sorted((k for k in bank if k not in keep), key=lambda k: (score(bank[k], now), bank[k]["first_seen"], k))
        for key in ranked[:excess]:
            del bank[key]


@dataclass(frozen=True)
class Job:
    kind: str  # "assigned" | "candidate"
    key: str
    cand: Candidate
    exit_ip: str | None  # None: a full prescreen; else a recheck of this exit
    geo: dict | None  # known country/timezone, or None: look it up (budgeted)
    sites: tuple | None  # sites to reach-check, or None: decide from the looked-up country
    label: str = ""


class _Probe:
    """Per-pass probe context shared by the worker threads; only the geo budget is mutable."""

    def __init__(self, policy, net: Net, geo_cache: dict, needed: dict, now: datetime):
        self.policy, self.net, self.geo_cache, self.needed, self.now = policy, net, dict(geo_cache), needed, now
        self._geo_left, self._lock = GEO_PER_RUN, threading.Lock()

    def _take_geo(self) -> bool:
        with self._lock:
            if self._geo_left <= 0:
                return False
            self._geo_left -= 1
            return True

    def __call__(self, job: Job) -> dict:
        out = {"ok": False, "reason": None, "exit_ip": job.exit_ip, "latency": None, "geo": None, "reach": {},
               "geo_budget": False}
        try:
            if job.exit_ip is None:
                verified = prescreen(job.cand, self.policy, self.net)
                out["exit_ip"], out["latency"] = verified.exit_ip, verified.latency
            else:
                out["latency"] = recheck(job.cand, job.exit_ip, self.policy, self.net)
            geo = job.geo or self.geo_cache.get(out["exit_ip"])
            if geo is None:
                if self._take_geo():
                    geo = out["geo"] = {**geolocate(job.cand, out["exit_ip"], self.net), "at": _iso(self.now)}
                else:
                    out["geo_budget"] = True
            elif job.geo is None:
                out["geo"] = geo
            sites = job.sites if job.sites is not None else \
                tuple(sorted(self.needed.get(geo["country"], ()))) if geo else ()
            for site in sites:
                try:
                    reach(job.cand, site, self.net)
                    out["reach"][site] = True
                except SourceError:
                    out["reach"][site] = False
                except (OSError, ssl.SSLError):
                    out["reach"][site] = False
            out["ok"] = True
        except SourceError as failure:
            out["reason"] = failure.reason
        except (OSError, ssl.SSLError):
            out["reason"] = "dead"
        return out


def scan(jobs, work, concurrency: int, budget: float, clock: Callable[[], float]):
    """Run `work(job)` for `jobs` in order, at most `concurrency` in flight; once `budget` seconds of `clock` have
    passed no further job starts (in-flight ones finish within their own timeouts). Returns ([(job, outcome)],
    number of jobs never started)."""
    results, pending = [], iter(jobs)
    started, skipped = clock(), 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        inflight, more = {}, True
        while True:
            while more and len(inflight) < concurrency:
                job = next(pending, None)
                if job is None:
                    more = False
                elif clock() - started > budget:
                    skipped, more = 1 + sum(1 for _ in pending), False
                else:
                    inflight[executor.submit(work, job)] = job
            if not inflight:
                return results, skipped
            done, _ = concurrent.futures.wait(inflight, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                results.append((inflight.pop(future), future.result()))


def _apply(entry: dict, out: dict, now: datetime) -> None:
    entry["last_probe"] = _iso(now)
    if out["ok"]:
        latency = out["latency"]
        entry.update(last_ok=_iso(now), ok_streak=entry["ok_streak"] + 1, fail_streak=0, dead_until=None,
                     exit_ip=out["exit_ip"], latency=round(latency if entry["latency"] is None else
                                                           (1 - EWMA) * entry["latency"] + EWMA * latency, 3))
        if out["geo"]:
            entry["country"], entry["timezone"] = out["geo"]["country"], out["geo"]["timezone"]
        if out["reach"]:
            entry["reach"] = {**entry["reach"], **out["reach"]}
            entry["reach_at"] = _iso(now)
        return
    entry["fail_streak"] += 1
    entry["ok_streak"] = 0
    base = SHORT_DEAD_TTL if entry["last_ok"] else DEAD_TTL
    entry["dead_until"] = _iso(now + min(DEAD_TTL_MAX, base * 2 ** min(entry["fail_streak"] - 1, 6)))
    if out["reason"] in ("exit_changed", "rotating", "echo", "geo"):
        entry.update(exit_ip=None, country=None, timezone=None, reach={}, reach_at=None)


def coverage(config_path: Path, deps: Deps | None = None) -> dict[str, int]:
    """Read-only: distinct exits per country the bank verified within `LIVE_WINDOW`. No network, no lock, no write."""
    deps = deps or Deps()
    config = web_queries.load(Path(config_path)).config
    _need(config.x_proxy_policy_path is not None, "files_invalid")
    policy_path = Path(config.x_proxy_policy_path)
    policy = p.parse_policy(read_bounded(policy_path, p.SMALL_LIMIT), policy_path.parent)
    state_path = policy.cache_dir / STATE_DIR / "state.json"
    if not state_path.exists():
        return {}
    state = _load_state(json.loads(_private(state_path, policy, deps, STATE_LIMIT)))
    now, exits = deps.now(), {}
    for entry in state["bank"].values():
        seen = _when(entry.get("last_ok"))
        if entry.get("country") and not entry.get("fail_streak") and seen is not None and seen >= now - LIVE_WINDOW:
            exits.setdefault(entry["country"], set()).add(entry.get("exit_ip"))
    return {country: len(found) for country, found in sorted(exits.items())}


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
    scan_started = deps.clock()
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
        state = _load_state(json.loads(_private(state_path, policy, deps, STATE_LIMIT)))
    owned = set(state["owned_ids"])
    strict_tz = policy.metadata_provider == "ipapi"
    wanted_targets = targets(config)
    checks = config.route_source_site_checks
    result = Result("ok", "steady", managed=len(wanted_targets))
    reject = result.rejections

    def count(reason, n=1):
        reject[reason] = reject.get(reason, 0) + n

    # Expire bounded memories.
    state["quarantine"] = {ip: until for ip, until in state["quarantine"].items() if (_when(until) or now) > now}
    state["geo"] = {ip: g for ip, g in state["geo"].items() if (_when(g.get("at")) or now) > now - GEO_TTL}
    quarantined_exits = set(state["quarantine"])
    bank = state["bank"]
    needed: dict[str, set] = {}  # identity country -> sites whose reachability is checked
    for t in wanted_targets:
        needed.setdefault(t.region, set())
        if checks[t.site]:
            needed[t.region].add(t.site)

    # 1. Every owner list, merged into the bank (new candidates are remembered; listed ones refreshed).
    listed = set()
    for url in config.route_source_list_urls:
        try:
            found = parse_candidates(fetch_list(url, config.route_source_allowed_hosts, net))
        except (SourceError, OSError, ssl.SSLError) as failure:
            count("list_" + getattr(failure, "reason", "unreachable"))
            continue
        for cand in found:
            listed.add(cand.key)
            if cand.key in bank:
                bank[cand.key]["last_listed"] = _iso(now)
            else:
                bank[cand.key] = _entry(cand.line, now)

    # 2. One scan: assigned routes first, never-probed candidates next, then known ones by score; known-dead skipped.
    jobs, assigned = [], {}
    for t in wanted_targets:
        item = current.get(t.label)
        cand = candidate_from_route(item.route) if item is not None else None
        if cand is None:
            continue  # unassigned, or an owner credentialed route: only the pool's quarantine signal applies
        assigned[t.label] = cand.key
        bank.setdefault(cand.key, _entry(cand.line, now))
        jobs.append(Job("assigned", cand.key, cand, item.expected_ip, {"country": t.region, "timezone": t.timezone},
                        (t.site,) if checks[t.site] else (), t.label))
    _evict(bank, listed | set(assigned.values()), now)
    fresh, known = [], []
    for key, entry in bank.items():
        cand = candidate_from_line(entry["line"])
        if key in assigned.values() or cand is None or _dead(entry, now):
            continue
        if entry["last_probe"] is None:
            fresh.append(Job("candidate", key, cand, None, None, None))
            continue
        geo = {"country": entry["country"], "timezone": entry["timezone"]} if entry["country"] else None
        stale = (_when(entry["reach_at"]) or now - 2 * REACH_TTL) <= now - REACH_TTL
        sites = None if geo is None else tuple(sorted(needed.get(geo["country"], ()))) if stale else ()
        known.append(Job("candidate", key, cand, entry["exit_ip"], geo, sites))
    known.sort(key=lambda job: (-score(bank[job.key], now), job.key))
    probe = _Probe(policy, net, state["geo"], needed, now)
    results, skipped = scan(jobs + fresh + known, probe, config.route_source_scan_concurrency,
                            config.route_source_scan_budget_seconds, deps.clock)
    if skipped:
        count("scan_budget", skipped)
    failing: dict[str, str] = {}
    for job, out in results:
        _apply(bank[job.key], out, now)
        if out["geo"] and out["exit_ip"]:
            state["geo"][out["exit_ip"]] = {**out["geo"], "at": out["geo"].get("at", _iso(now))}
        if out["geo_budget"]:
            count("geo_budget")
        blocked = [site for site, ok in sorted(out["reach"].items()) if not ok]
        if job.kind == "assigned":
            bad = out["reason"] if not out["ok"] else ("reach_" + blocked[0] if blocked else None)
            if bad:
                count("assigned_" + bad)
                failing[job.label] = "site_blocked" if bad.startswith("reach_") else "probe_failed"
            continue
        if not out["ok"]:
            count(out["reason"])
        for site in blocked:
            count("reach_" + site)

    # 3. Pre-emptive replacement decisions; healthy routes are sticky.
    pool_quarantine = _pool_quarantined(cache_root)
    replace: dict[str, str] = {}
    for t in wanted_targets:
        item = current.get(t.label)
        if item is None:
            replace[t.label] = "unassigned"
        elif t.site == "x" and pool_quarantine.get(t.label) == item.proxy_id:
            replace[t.label] = "pool_quarantined"
        elif t.label in failing:
            replace[t.label] = failing[t.label]
        elif t.label in assigned and (bank[assigned[t.label]]["latency"] or 0) > DEGRADED_LATENCY:
            replace[t.label] = "degraded"

    # 4. Verified-this-pass candidates, best first, one per exit, never an assigned or quarantined exit.
    now_iso = _iso(now)
    assigned_exits = {item.expected_ip for item in current.values()}
    live, seen_exits = [], set()
    for key in sorted(bank, key=lambda k: (-score(bank[k], now), k)):
        entry = bank[key]
        if (key in assigned.values() or entry["last_ok"] != now_iso or entry["fail_streak"] or not entry["country"]
                or entry["exit_ip"] in assigned_exits | quarantined_exits | seen_exits):
            continue
        seen_exits.add(entry["exit_ip"])
        live.append(key)

    def fits(t: Target, key: str) -> bool:
        entry = bank[key]
        return _fits(t, entry, strict_tz) and (not checks[t.site] or entry["reach"].get(t.site) is True)

    # 5. Plan: replacements take the best fitting candidate; then N spares per identity country.
    wanted: dict[str, tuple[str, dict]] = {}
    planned, remaining, no_spare = [], list(live), {}
    for t in wanted_targets:
        reason = replace.get(t.label)
        if reason is None:
            continue
        choice = next((k for k in remaining if fits(t, k)), None)
        if choice is None:
            if reason != "degraded":  # a slow but working route stays without complaint
                no_spare.setdefault(t.region, t.site)
            continue
        remaining.remove(choice)
        pid = deps.new_id()
        entry = bank[choice]
        wanted[t.label] = (pid, {"proxy_id": pid, "expected_ip": entry["exit_ip"], "region": t.region,
                                 "timezone": t.timezone, "accept_language": t.accept_language, "line": entry["line"]})
        planned.append((t, current.get(t.label), pid, reason))
    spares, per_country = [], {}
    for group_key in sorted({(t.region, t.timezone if strict_tz else "") for t in wanted_targets}):
        group = [t for t in wanted_targets if (t.region, t.timezone if strict_tz else "") == group_key]
        picks = [k for k in remaining if all(fits(t, k) for t in group)][:config.route_source_spares_per_country]
        for key in picks:
            remaining.remove(key)
        spares += picks
        per_country[group_key[0]] = per_country.get(group_key[0], 0) + len(picks)
        if config.route_source_spares_per_country and not picks:
            no_spare.setdefault(group_key[0], group[0].site)
    for country, site in sorted(no_spare.items()):
        result.alerts.append({"code": f"no_spare:{country}", "site": site})

    # 6. Compose, validate with the REAL B2 loader, publish atomically (list first; old slots never move).
    new_doc, new_lines = compose(old_doc, old_lines, owned, wanted)
    if wanted and set(config.x_accounts) - set(new_doc["accounts"]):
        # A file without every X label would refuse every account: keep the old files.
        result.alerts.append({"code": "x_labels_unassigned", "site": "x"})
        wanted, planned = {}, []
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
        state["assigned_at"][pid] = now_iso
        if old is not None:
            state["quarantine"][old.expected_ip] = _iso(now + timedelta(seconds=config.x_proxy_quarantine_seconds))
            result.replaced += 1
            result.alerts.append({"code": "route_replaced", "site": t.site})
        state["changes"] = (state["changes"] + [{"at": now_iso, "label": t.label,
                                                 "from": None if old is None else old.proxy_id,
                                                 "to": pid, "reason": reason}])[-CHANGE_KEEP:]
    for pid in owned:
        state["assigned_at"].setdefault(pid, now_iso)  # a v1 route: its age starts now
    state["assigned_at"] = {pid: at for pid, at in state["assigned_at"].items() if pid in owned}
    result.spares = len(spares)
    result.assigned = sum(1 for t in wanted_targets if t.label in new_doc["accounts"])
    ages = [now - at for at in (_when(v) for v in state["assigned_at"].values()) if at is not None]
    result.bank = {"size": len(bank), "verified_live": sum(1 for e in bank.values() if e["last_ok"] == now_iso),
                   "spares_per_country": dict(sorted(per_country.items())), "no_spare": sorted(no_spare),
                   "last_scan_seconds": round(max(0.0, deps.clock() - scan_started), 1), "scanned": len(results),
                   "oldest_assigned_age_hours": round(max(ages).total_seconds() / 3600, 1) if ages else None}
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
