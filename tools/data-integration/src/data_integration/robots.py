"""robots.txt checking. The robots fetch needs a pass too, shares the client (UA, politeness,
logging) and fails closed: unreachable, timeout, 5xx or unparsable robots means refuse."""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from data_integration.gate import FetchPass
from data_integration.politeness import USER_AGENT

_DEFAULT_PORTS = {"http": 80, "https": 443}
_DIRECTIVES = ("user-agent", "disallow", "allow", "crawl-delay", "sitemap", "host")


@dataclass(frozen=True)
class RawResponse:
    status: int
    body: bytes = b""
    headers: dict = field(default_factory=dict)


def _parse(body: bytes) -> RobotFileParser | None:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    lines = [ln.split("#", 1)[0].strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    if any(ln.split(":", 1)[0].strip().lower() not in _DIRECTIVES or ":" not in ln for ln in lines):
        return None
    parser = RobotFileParser()
    parser.parse(lines)
    return parser


class RobotsChecker:
    """`client` must offer get(url) -> RawResponse and may raise (any failure is fail-closed)."""

    def __init__(self, client):
        self._client = client
        self._cache: dict[tuple[str, str], tuple[RobotFileParser | None, str]] = {}

    def _load(self, scheme: str, host: str) -> tuple[RobotFileParser | None, str]:
        key = (scheme, host)
        if key not in self._cache:
            self._cache[key] = self._fetch(scheme, host)
        return self._cache[key]

    def _fetch(self, scheme: str, host: str) -> tuple[RobotFileParser | None, str]:
        try:
            resp = self._client.get(f"{scheme}://{host}/robots.txt")
        except Exception as exc:  # fail closed on timeout / refused / anything
            return None, f"robots unreachable ({type(exc).__name__})"
        if resp.status in (404, 410):
            allow_all = RobotFileParser()
            allow_all.parse([])
            return allow_all, "no robots.txt"
        if resp.status != 200:
            return None, f"robots returned {resp.status}"
        parser = _parse(resp.body)
        return (parser, "") if parser else (None, "robots unparsable")

    def allowed(self, url: str, pass_: object) -> tuple[bool, str]:
        if not isinstance(pass_, FetchPass):
            return False, "robots check needs a FetchPass"
        try:
            parts = urlsplit(url)
            host = (parts.hostname or "").lower()
            scheme = parts.scheme.lower()
            port = parts.port
        except ValueError:
            return False, "bad url"
        if scheme not in _DEFAULT_PORTS or (port not in (None, _DEFAULT_PORTS[scheme])) or host not in pass_.hosts:
            return False, "robots host not permitted by pass"
        parser, detail = self._load(scheme, host)
        if parser is None:
            return False, detail
        if parser.can_fetch(USER_AGENT, url):
            return True, detail
        return False, "robots disallow"
