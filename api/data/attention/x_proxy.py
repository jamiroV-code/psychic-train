"""B2 private route decisions. No client imports, DNS, requests or provider calls.

All public failures contain only the frozen reason vocabulary. Private routes must
never be written to the account database, pool state, child protocol or diagnostics.
"""
from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import io
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote, urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REASONS = frozenset({"proxy_config", "proxy_private", "proxy_assignment", "proxy_policy", "proxy_address", "proxy_transport", "proxy_timeout", "proxy_redirect", "proxy_response", "proxy_exit", "proxy_region", "proxy_feed", "proxy_baseline", "proxy_budget", "proxy_quarantine", "proxy_revision", "proxy_lock"})
BLOCK_REASONS = frozenset({"proxy_config", "proxy_private", "proxy_assignment", "proxy_policy"})
SPAMHAUS = "https://www.spamhaus.org/drop/drop.txt"
FIREHOL = "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level1.netset"
IPAPI = "https://ipapi.co/json/"
FEED_WIRE_LIMIT = 8 * 1024 * 1024
FEED_DECODED_LIMIT = 32 * 1024 * 1024
SMALL_LIMIT = 64 * 1024
BASELINE_LIMIT = 1024 * 1024
X_LIMIT = 32 * 1024 * 1024
CHILD_STDOUT_LIMIT = 16 * 1024 * 1024
CHILD_STDERR_LIMIT = 1024 * 1024
REGION = re.compile(r"[A-Z]{2}(?:-[A-Z0-9]{1,3})?")
LANGUAGE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?(?:\s*;q=(?:0(?:\.\d{1,3})?|1(?:\.0{1,3})?))?(?:,\s*[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?(?:\s*;q=(?:0(?:\.\d{1,3})?|1(?:\.0{1,3})?))?)*")


class ProxyFailure(Exception):
    """Safe route failure; callers must suppress unsafe transport exception chains."""
    def __init__(self, reason: str = "proxy_transport"):
        self.reason = reason if isinstance(reason, str) and reason in REASONS else "proxy_transport"
        super().__init__(self.reason)


def require(ok: bool, reason: str):
    if not ok:
        raise ProxyFailure(reason)


def strict_json(body: bytes, *, limit: int = SMALL_LIMIT):
    require(len(body) <= limit, "proxy_config")
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "proxy_config")
            out[key] = value
        return out
    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ProxyFailure("proxy_config")))
    except (UnicodeError, ValueError, TypeError, RecursionError):
        pass
    # Outside the handler: JSONDecodeError.doc may contain the private input.
    raise ProxyFailure("proxy_config")


def exact(value, keys, reason="proxy_config"):
    require(isinstance(value, dict) and set(value) == set(keys), reason)
    return value


def canonical_origin(url: str, *, origin_only: bool = False) -> str:
    try:
        require(isinstance(url, str) and bool(url) and not any(ord(c) <= 32 or ord(c) == 127 for c in url), "proxy_policy")
        u = urlsplit(url)
        require(u.scheme == "https" and bool(u.hostname) and u.username is None and u.password is None
                and not u.fragment and "#" not in url and "\\" not in url, "proxy_policy")
        require(not origin_only or (u.path in ("", "/") and not u.query and "?" not in url), "proxy_policy")
        host = u.hostname.encode("idna").decode("ascii").lower()
        require(not host.endswith(".") and "%" not in host, "proxy_policy")
        port = u.port if u.port is not None else 443
        require(1 <= port <= 65535, "proxy_policy")
        if ":" in host:
            host = "[" + str(ipaddress.IPv6Address(host)) + "]"
        return "https://" + host + (":" + str(port) if port != 443 else "")
    except (ValueError, UnicodeError, AttributeError):
        pass
    raise ProxyFailure("proxy_policy")


def public_address(value: str) -> str:
    try:
        addr = ipaddress.ip_address(value)
        require(addr.is_global and not addr.is_multicast and not addr.is_unspecified
                and not addr.is_reserved and not (getattr(addr, "ipv4_mapped", None)), "proxy_address")
        return str(addr)
    except (ValueError, TypeError):
        pass
    raise ProxyFailure("proxy_address")


def normalized_ip(value) -> str:
    try:
        require(isinstance(value, str), "proxy_assignment")
        address = ipaddress.ip_address(value)
        return str(getattr(address, "ipv4_mapped", None) or address)
    except ValueError:
        pass
    raise ProxyFailure("proxy_assignment")


def opaque_id(value) -> str:
    try:
        require(isinstance(value, str) and str(UUID(value)) == value, "proxy_assignment")
        return value
    except (ValueError, TypeError, AttributeError):
        pass
    raise ProxyFailure("proxy_assignment")


@dataclass(frozen=True)
class PrivateRoute:
    url: str
    auth: tuple[str, str] | None = field(default=None, repr=False)

    def __repr__(self):
        return "PrivateRoute(<private>)"


def parse_proxy(value: str) -> PrivateRoute:
    try:
        require(isinstance(value, str) and bool(value) and not any(ord(c) <= 32 or ord(c) == 127 for c in value), "proxy_assignment")
        u = urlsplit(value)
        require(u.scheme in ("http", "https") and bool(u.hostname) and u.path in ("", "/")
                and not u.query and not u.fragment and "?" not in value and "#" not in value
                and "\\" not in value, "proxy_assignment")
        require(u.scheme == "https" or (u.username is None and u.password is None), "proxy_assignment")
        require((u.username is None) == (u.password is None), "proxy_assignment")
        host = u.hostname.encode("idna").decode("ascii").lower()
        require("%" not in host and not host.endswith("."), "proxy_assignment")
        port = u.port if u.port is not None else (443 if u.scheme == "https" else 80)
        require(1 <= port <= 65535, "proxy_assignment")
        if ":" in host:
            host = "[" + str(ipaddress.IPv6Address(host)) + "]"
        auth = None if u.username is None else (unquote(u.username), unquote(u.password))
        if auth is not None:
            require(all(auth) and ":" not in auth[0] and all(not any(ord(c) < 32 or ord(c) == 127 for c in s) for s in auth), "proxy_assignment")
        return PrivateRoute(f"{u.scheme}://{host}:{port}", auth)
    except (ValueError, TypeError, UnicodeError, AttributeError):
        pass
    raise ProxyFailure("proxy_assignment")


@dataclass(frozen=True)
class Policy:
    origins: frozenset[str]
    echo: str
    baseline: str
    baseline_sha256: str
    metadata_provider: str | None
    service_sid: str
    cache_dir: Path
    private_root: Path | None = field(default=None, repr=False)

    def validate_url(self, url: str):
        require(canonical_origin(url) in self.origins, "proxy_policy")

def valid_sid(value) -> bool:
    if not isinstance(value, str) or re.fullmatch(r"S-1-\d+(?:-\d+){1,15}", value) is None:
        return False
    numbers = value.split("-")[2:]
    return (all(str(int(part)) == part for part in numbers)
            and int(numbers[0]) < 2 ** 48 and all(int(part) < 2 ** 32 for part in numbers[1:]))



def parse_policy(body: bytes, root: Path) -> Policy:
    d = exact(strict_json(body), ("version", "allowed_origins", "echo", "baseline", "metadata_provider", "service_sid", "cache_dir"))
    require(type(d["version"]) is int and d["version"] == 1, "proxy_policy")
    origins = d["allowed_origins"]
    require(isinstance(origins, list) and bool(origins), "proxy_policy")
    origins = [canonical_origin(v, origin_only=True) for v in origins]
    require(len(set(origins)) == len(origins), "proxy_policy")
    echo = exact(d["echo"], ("url", "response_format"))
    baseline = exact(d["baseline"], ("url", "sha256"))
    require(echo["response_format"] == "json-ip", "proxy_policy")
    require(isinstance(baseline["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", baseline["sha256"]) is not None, "proxy_policy")
    require(d["metadata_provider"] is None or d["metadata_provider"] == "ipapi", "proxy_policy")
    require(valid_sid(d["service_sid"]), "proxy_private")
    require(isinstance(d["cache_dir"], str) and Path(d["cache_dir"]).is_absolute(), "proxy_private")
    cache_dir = Path(d["cache_dir"])
    require(cache_dir != root and root in cache_dir.parents and ".." not in cache_dir.parts, "proxy_private")
    policy = Policy(frozenset(origins), echo["url"], baseline["url"], baseline["sha256"], d["metadata_provider"], d["service_sid"], cache_dir, root)
    for url in [policy.echo, policy.baseline, SPAMHAUS, FIREHOL] + ([IPAPI] if policy.metadata_provider else []):
        policy.validate_url(url)
    return policy


@dataclass(frozen=True)
class Assignment:
    proxy_id: str
    expected_ip: str = field(repr=False)
    region: str
    timezone: str
    accept_language: str
    route: PrivateRoute = field(repr=False)


def parse_assignments(body: bytes, lines_body: bytes, labels, *, required: bool, identities: Mapping = None) -> dict[str, Assignment]:
    from api.data.attention import web_queries
    d = exact(strict_json(body), ("version", "lines", "accounts"))
    require(type(d["version"]) is int and d["version"] == 1, "proxy_assignment")
    require(isinstance(d["lines"], dict) and isinstance(d["accounts"], dict), "proxy_assignment")
    require(set(d["accounts"]) <= set(labels) and (not required or set(d["accounts"]) == set(labels)), "proxy_assignment")
    require(len(lines_body) <= 1024 * 1024, "proxy_assignment")
    try:
        lines = lines_body.decode("utf-8").splitlines()
    except UnicodeError:
        lines = None
    require(bool(lines) and all(lines), "proxy_assignment")
    routes = [parse_proxy(line) for line in lines]
    used_lines = set()
    for key, number in d["lines"].items():
        opaque_id(key)
        require(type(number) is int and 1 <= number <= len(routes) and number not in used_lines, "proxy_assignment")
        used_lines.add(number)
    used_ids, used_ips, out = set(), set(), {}
    try:
        countries = web_queries._timezone_countries()
    except web_queries.QueriesError:
        countries = None
    require(countries is not None, "proxy_region")
    for label, item in d["accounts"].items():
        exact(item, ("proxy_id", "expected_ip", "region", "timezone", "accept_language"))
        pid = opaque_id(item["proxy_id"])
        ip = normalized_ip(item["expected_ip"])
        require(pid in d["lines"] and pid not in used_ids and ip not in used_ips, "proxy_assignment")
        require(isinstance(item["region"], str) and REGION.fullmatch(item["region"]) is not None, "proxy_region")
        require(isinstance(item["accept_language"], str) and len(item["accept_language"]) <= 256 and LANGUAGE.fullmatch(item["accept_language"]) is not None, "proxy_region")
        try:
            valid_zone = True
            require(isinstance(item["timezone"], str), "proxy_region")
            ZoneInfo(item["timezone"])
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            valid_zone = False
        require(valid_zone, "proxy_region")
        country = item["region"].split("-", 1)[0]
        try:
            web_queries._identity_coherence({**item, "region": country, "impersonation_target": ""}, countries)
            coherent = True
        except web_queries.QueriesError:
            coherent = False
        require(coherent, "proxy_region")
        if identities and label in identities:
            require(identities[label].get("region") == country and
                    all(identities[label].get(k) == item[k] for k in ("timezone", "accept_language")), "proxy_region")
        out[label] = Assignment(pid, ip, item["region"], item["timezone"], item["accept_language"], routes[d["lines"][pid] - 1])
        used_ids.add(pid)
        used_ips.add(ip)
    return out


class ConnectFrame:
    """One bounded CONNECT frame. Never forwards a partial or ambiguous header."""
    def __init__(self, bindings: Mapping[bytes, bytes]):
        self.bindings = bindings
        self.pending = bytearray()
        self.done = False

    def feed(self, data: bytes) -> bytes | None:
        if self.done:
            return data
        require(len(self.pending) + len(data) <= 16384, "proxy_transport")
        self.pending.extend(data)
        marker = self.pending.find(b"\r\n\r\n")
        if marker < 0:
            return None
        require(marker + 4 == len(self.pending), "proxy_transport")
        rows = bytes(self.pending[:-4]).split(b"\r\n")
        parts = rows[0].split(b" ")
        require(len(parts) == 3 and parts[0] == b"CONNECT" and parts[2] == b"HTTP/1.1" and parts[1] in self.bindings, "proxy_transport")
        original = parts[1]
        target = self.bindings[original]
        require(re.fullmatch(rb"(?:[0-9.]+|\[[0-9a-fA-F:]+\]):[0-9]{1,5}", target) is not None, "proxy_transport")
        try:
            host, port = target.decode("ascii").rsplit(":", 1)
            ipaddress.ip_address(host.strip("[]"))
            require(1 <= int(port) <= 65535, "proxy_transport")
        except (ValueError, UnicodeError):
            target = None
        require(target is not None, "proxy_transport")
        result = [b"CONNECT " + target + b" HTTP/1.1"]
        hosts = 0
        seen = set()
        for row in rows[1:]:
            require(bool(row) and not row.startswith((b" ", b"\t")) and b":" in row, "proxy_transport")
            key, value = row.split(b":", 1)
            require(re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) is not None and not any(c < 32 and c != 9 or c == 127 for c in value), "proxy_transport")
            name = key.lower()
            require(name not in seen, "proxy_transport")
            seen.add(name)
            require(name not in (b"content-length", b"transfer-encoding", b"connection", b"upgrade"), "proxy_transport")
            if name == b"host":
                hosts += 1
                require(value.strip() == original, "proxy_transport")
                result.append(b"Host: " + target)
            else:
                require(name in (b"accept", b"proxy-authorization", b"user-agent"), "proxy_transport")
                result.append(row)
        require(hosts == 1, "proxy_transport")
        self.pending.clear()
        self.done = True
        return b"\r\n".join(result) + b"\r\n\r\n"


@dataclass(frozen=True)
class Feed:
    networks: tuple
    source_version: tuple[str, ...]
    expires_at: datetime

    def contains(self, value: str) -> bool:
        addr = ipaddress.ip_address(value)
        return any(addr.version == n.version and addr in n for n in self.networks)


def _feed_time(value: str, now: datetime) -> datetime:
    try:
        stamp = parsedate_to_datetime(value)
        require(stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0) and stamp <= now, "proxy_feed")
        return stamp.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        pass
    raise ProxyFailure("proxy_feed")


def parse_feed(slot: str, body: bytes, now: datetime) -> Feed:
    require(slot in ("spamhaus", "firehol") and len(body) <= FEED_DECODED_LIMIT, "proxy_feed")
    try:
        rows = io.StringIO(body.decode("ascii"))
    except UnicodeError:
        rows = None
    require(rows is not None, "proxy_feed")
    headers, networks = {}, []
    comment = ";" if slot == "spamhaus" else "#"
    while True:
        line = rows.readline(4099)
        if not line:
            break
        require(len(line.rstrip("\r\n")) <= 4096, "proxy_feed")
        line = line.strip()
        if not line:
            continue
        if line.startswith(comment):
            text = line[1:].strip()
            for key in ("Last-Modified", "Expires", "This File Date", "Source File Date", "Entries"):
                if text.startswith(key + ":"):
                    require(key not in headers, "proxy_feed")
                    headers[key] = text[len(key) + 1:].strip()
            continue
        if slot == "spamhaus":
            match = re.fullmatch(r"([0-9.]+/[0-9]{1,2})\s*;\s*SBL[0-9]+", line)
            require(match is not None, "proxy_feed")
            value = match.group(1)
        else:
            value = line
        try:
            network = ipaddress.ip_network(value, strict=True)
            require(slot != "spamhaus" or network.version == 4, "proxy_feed")
        except ValueError:
            network = None
        require(network is not None, "proxy_feed")
        networks.append(network)
        require(len(networks) <= 50000, "proxy_feed")
    require(bool(networks), "proxy_feed")
    if slot == "spamhaus":
        require(set(("Last-Modified", "Expires")) <= headers.keys(), "proxy_feed")
        start = _feed_time(headers["Last-Modified"], now)
        try:
            end = parsedate_to_datetime(headers["Expires"])
            require(end.tzinfo is not None and end.utcoffset() == timedelta(0) and start < end and end > now, "proxy_feed")
        except (ValueError, TypeError, OverflowError):
            end = None
        require(end is not None, "proxy_feed")
        version = (headers["Last-Modified"], headers["Expires"])
    else:
        require(set(("This File Date", "Source File Date", "Entries")) <= headers.keys(), "proxy_feed")
        start = _feed_time(headers["This File Date"], now)
        _feed_time(headers["Source File Date"], now)
        require(headers["Entries"].isdigit() and int(headers["Entries"]) == len(networks), "proxy_feed")
        end = start + timedelta(days=1)
        version = (headers["This File Date"], headers["Source File Date"], headers["Entries"])
    require(now - start <= timedelta(days=1) and min(end, start + timedelta(days=1)) > now, "proxy_feed")
    return Feed(tuple(networks), version, min(end, start + timedelta(days=1)))
