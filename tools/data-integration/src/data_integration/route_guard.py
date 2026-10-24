"""Browser request guard for tier 2/3 (stdlib only): which sub-requests a pass lets through."""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

RESOURCE_TYPES = frozenset({"script", "stylesheet", "font", "image", "xhr", "fetch"})
ABORT_TEXT = "browser request outside the pass was aborted"
MAX_LABELS, MAX_DETAIL_BYTES = 20, 600
_HOST_RE = re.compile(r"^[a-z0-9.-]+$")


def host_label(url: object) -> str:
    """Lowercase hostname of a URL, `(ip)` for an address, `(invalid)` otherwise. Never a path or query."""
    try:
        host = (urlsplit(url).hostname or "").lower() if isinstance(url, str) else ""
    except ValueError:
        return "(invalid)"
    if not host or len(host) > 253 or not _HOST_RE.match(host):
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return "(invalid)"
        return "(ip)"
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    return "(ip)"


def summarise(labels) -> tuple[str, ...]:
    """Distinct, sorted, at most 20 host labels."""
    return tuple(sorted(set(labels))[:MAX_LABELS])


def describe(hosts) -> str:
    """Refusal detail naming the blocked hosts, at most 600 bytes."""
    hosts = tuple(hosts)
    if not hosts:
        return ABORT_TEXT
    text = f"{ABORT_TEXT}; blocked hosts: " + ", ".join(hosts)
    while len(text.encode()) > MAX_DETAIL_BYTES and ", " in text:
        text = text.rsplit(", ", 1)[0]
    return text[:MAX_DETAIL_BYTES]


def decide(url: object, resource_type: object, is_navigation: bool, pass_) -> bool:
    """True when the browser may send this request."""
    if not isinstance(url, str) or "\\" in url:
        return False
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if host in pass_.hosts:
        return not is_navigation or pass_.permits(url)
    if (host and host in getattr(pass_, "resource_hosts", ()) and not is_navigation and "@" not in parts.netloc
            and parts.scheme.lower() == "https" and port in (None, 443) and resource_type in RESOURCE_TYPES):
        return True
    return False


def make_handler(pass_, blocked: list):
    """A Playwright route handler: continue allowed requests, abort the rest and record only the host."""

    def guard(route) -> None:
        request = route.request
        if decide(request.url, request.resource_type, request.is_navigation_request(), pass_):
            route.continue_()
        else:
            blocked.append(host_label(request.url))
            route.abort()

    return guard
