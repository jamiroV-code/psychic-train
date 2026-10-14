"""Tier 1: gated, polite HTTP fetch. Never raises; every result maps to the closed status set.

The gate is checked first (the pass and every redirect hop); the HTTP client is built only after.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit, urljoin

from scrapling.fetchers import Fetcher

from data_integration import status
from data_integration.gate import FetchPass
from data_integration.logging_setup import get_logger, log_request
from data_integration.politeness import USER_AGENT, Politeness
from data_integration.response_cache import ResponseCache
from data_integration.robots import RawResponse, RobotsChecker
from data_integration.types import FetchOutcome

# The library logs full URLs (query strings included); our one-line log is the only request log.
logging.getLogger("scrapling").setLevel(logging.CRITICAL)

_CLIENTS_BUILT = 0
_CHALLENGE_MARKERS = (b"just a moment", b"cf-chl", b"captcha", b"checking your browser", b"attention required")
_REDIRECTS = {301, 302, 303, 307, 308}


def clients_built() -> int:
    """Counter used by tests to prove refusals never build an HTTP client."""
    return _CLIENTS_BUILT


class HttpClient:
    """Thin wrapper: honest UA, no auto-redirects, politeness slot and one log line per request."""

    def __init__(self, proxy: str | None = None, timeout: float = 10.0, politeness: Politeness | None = None,
                 tier: int = 1, logger=None):
        global _CLIENTS_BUILT
        _CLIENTS_BUILT += 1
        self._proxy = proxy
        self._timeout = timeout
        self._politeness = politeness or Politeness()
        self._tier = tier
        self._logger = logger or get_logger()

    def get(self, url: str) -> RawResponse:
        parts = urlsplit(url)
        host = parts.hostname or ""
        started = time.monotonic()
        code: object = "error"
        try:
            with self._politeness.slot(host):
                started = time.monotonic()
                kwargs = {"proxy": self._proxy} if self._proxy else {}
                resp = Fetcher.get(url, follow_redirects=False, timeout=self._timeout, retries=1,
                                   stealthy_headers=False, headers={"User-Agent": USER_AGENT}, **kwargs)
            code = resp.status
            headers = {str(k).lower(): str(v) for k, v in dict(resp.headers).items()}
            return RawResponse(int(resp.status), bytes(resp.body or b""), headers)
        except Exception as exc:
            code = "timeout" if _is_timeout(exc) else "error"
            raise
        finally:
            log_request(host, parts.path, code, time.monotonic() - started, self._tier, self._logger)


def _is_timeout(exc: BaseException) -> bool:
    return getattr(exc, "code", None) == 28 or "timeout" in type(exc).__name__.lower() or "timed out" in str(exc).lower()


def _is_challenge(resp: RawResponse) -> bool:
    low = resp.body[:20000].lower()
    return any(m in low for m in _CHALLENGE_MARKERS)


def _out(st: str, url: str, http_status: int | None = None, body: bytes = b"", detail: str = "") -> FetchOutcome:
    return FetchOutcome(st, url, http_status, body, detail)


def fetch(url: str, pass_: object, *, cache: ResponseCache | None = None, refresh: bool = False,
          politeness: Politeness | None = None, robots: RobotsChecker | None = None, proxy: str | None = None,
          timeout: float = 10.0, max_redirects: int = 5, logger=None) -> FetchOutcome:
    try:
        return _fetch(url, pass_, cache, refresh, politeness, robots, proxy, timeout, max_redirects, logger)
    except Exception as exc:
        return _out(status.CONNECTION_FAILED, str(url), detail=f"unexpected {type(exc).__name__}")


def _fetch(url, pass_, cache, refresh, politeness, robots, proxy, timeout, max_redirects, logger) -> FetchOutcome:
    if not isinstance(pass_, FetchPass):
        return _out(status.REFUSED, str(url), detail="a FetchPass from request_access is required")
    if not pass_.permits(url):
        return _out(status.REFUSED, url, detail="url not permitted by pass")
    if cache is not None and not refresh:
        hit = cache.get(url)
        if hit is not None:
            return hit
    client = HttpClient(proxy=proxy, timeout=timeout, politeness=politeness, tier=1, logger=logger)
    checker = robots or RobotsChecker(client)
    current = url
    for _ in range(max_redirects + 1):
        ok, why = checker.allowed(current, pass_)
        if not ok:
            return _out(status.ROBOTS_BLOCKED, current, detail=why)
        try:
            resp = client.get(current)
        except Exception as exc:
            st = status.TIMEOUT if _is_timeout(exc) else status.CONNECTION_FAILED
            return _out(st, current, detail=type(exc).__name__)
        if resp.status in _REDIRECTS:
            target = resp.headers.get("location")
            if not target:
                return _out(status.HTTP_ERROR, current, resp.status, detail="redirect without location")
            current = urljoin(current, target)
            if not pass_.permits(current):
                return _out(status.REFUSED, current, resp.status, detail="redirect target not permitted by pass")
            continue
        if _is_challenge(resp) and (resp.status == 200 or resp.status in (403, 429, 503)):
            return _out(status.CHALLENGE_PAGE, current, resp.status, detail="challenge page markers")
        if resp.status >= 400 or resp.status < 200:
            return _out(status.HTTP_ERROR, current, resp.status, detail=f"http {resp.status}")
        if cache is not None:
            cache.put(url, resp.status, resp.body)
        return _out(status.OK, current, resp.status, resp.body)
    return _out(status.HTTP_ERROR, current, detail="too many redirects")
