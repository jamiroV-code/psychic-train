"""Tier 2: gated, polite browser fetch (scrapling DynamicFetcher). Never raises; closed status set.

Order is fixed: pass check, url check, cache, robots (plain HTTP, never the browser), then ONE navigation.
A navigation never happens when robots disallows, is unreachable or is unparsable. `run_browser_fetch` is the
shared core; tier 3 reuses it with its own navigator and option allow-list.

Limits: the body cap is checked after the browser returns the whole rendered page (it bounds parsing and caching,
not the download); robots is checked for the requested URL and for the final URL after redirects, not for every
hop; the default navigator aborts requests to hosts outside the pass but cannot refuse a hop that the pass allows.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from scrapling.fetchers import DynamicFetcher

from data_integration import status
from data_integration.fetch_tier1 import DEFAULT_MAX_BODY_BYTES, HttpClient, _is_challenge, _is_timeout, _out
from data_integration.gate import FetchPass
from data_integration.logging_setup import get_logger, log_request
from data_integration.politeness import Politeness
from data_integration.response_cache import ResponseCache
from data_integration.route_guard import describe, make_handler, summarise
from data_integration.robots import RawResponse, RobotsChecker
from data_integration.types import FetchOutcome

# The library logs full URLs (query strings included); our one-line log is the only request log.
logging.getLogger("scrapling").setLevel(logging.CRITICAL)

# Optional path to a browser executable (an installed Chromium); unset means the library default.
BROWSER_ENV = "DIT_BROWSER_EXECUTABLE"
ALLOWED_OPTIONS: frozenset[str] = frozenset({"network_idle", "wait", "wait_selector", "disable_resources"})

_NAVIGATIONS = 0


def navigations_made() -> int:
    """Counter used by tests to prove refusals never launch a browser (default navigators only)."""
    return _NAVIGATIONS


@dataclass(frozen=True)
class BrowserResponse:
    status: int
    body: bytes = b""
    headers: dict = field(default_factory=dict)
    final_url: str | None = None  # where the browser ended up, when known
    blocked_url: str | None = None  # host label of the first request the navigator aborted (never a full URL)
    blocked_hosts: tuple[str, ...] = ()  # distinct sorted host labels of every aborted request


def _browser_kwargs(pass_: FetchPass, timeout: float, proxy: str | None, blocked: list[str]) -> dict:
    def page_setup(page) -> None:
        guard = make_handler(pass_, blocked)
        page.route("**/*", guard)

    kwargs: dict = {"headless": True, "timeout": int(timeout * 1000), "google_search": False, "page_setup": page_setup}
    if proxy:
        kwargs["proxy"] = proxy
    if os.environ.get(BROWSER_ENV):
        kwargs["executable_path"] = os.environ[BROWSER_ENV]
    return kwargs


def make_navigator(fetcher, extra: dict | None = None):
    """Build a navigator around a scrapling fetcher class (`fetcher.fetch(url, **kwargs)`)."""

    def navigate(url: str, pass_: FetchPass, options: dict, timeout: float, proxy: str | None) -> BrowserResponse:
        global _NAVIGATIONS
        _NAVIGATIONS += 1
        blocked: list[str] = []
        kwargs = _browser_kwargs(pass_, timeout, proxy, blocked)
        kwargs.update(extra or {})
        kwargs.update(options)
        try:
            resp = fetcher.fetch(url, **kwargs)
        except Exception:
            if blocked:
                return BrowserResponse(0, blocked_url=blocked[0], blocked_hosts=summarise(blocked))
            raise
        headers = {str(k).lower(): str(v) for k, v in dict(resp.headers).items()}
        return BrowserResponse(int(resp.status), bytes(resp.body or b""), headers, str(resp.url), blocked[0] if blocked else None,
                               summarise(blocked))

    return navigate


default_navigator = make_navigator(DynamicFetcher)


def fetch(url: str, pass_: object, *, navigator=None, cache: ResponseCache | None = None, refresh: bool = False,
          politeness: Politeness | None = None, robots: RobotsChecker | None = None, proxy: str | None = None,
          timeout: float = 10.0, logger=None, max_body_bytes: int = DEFAULT_MAX_BODY_BYTES) -> FetchOutcome:
    return run_browser_fetch(2, url, pass_, navigator or default_navigator, {}, cache=cache, refresh=refresh,
                             politeness=politeness, robots=robots, proxy=proxy, timeout=timeout, logger=logger,
                             max_body_bytes=max_body_bytes)


def run_browser_fetch(tier: int, url, pass_, navigator, options: dict, *, cache=None, refresh=False, politeness=None,
                      robots=None, proxy=None, timeout=10.0, logger=None,
                      max_body_bytes: int = DEFAULT_MAX_BODY_BYTES) -> FetchOutcome:
    try:
        return _run(tier, url, pass_, navigator, options, cache, refresh, politeness, robots, proxy, timeout, logger,
                    max_body_bytes)
    except Exception as exc:
        return _out(status.CONNECTION_FAILED, str(url), detail=f"unexpected {type(exc).__name__}")


def _run(tier, url, pass_, navigator, options, cache, refresh, politeness, robots, proxy, timeout, logger,
         max_body_bytes) -> FetchOutcome:
    if not isinstance(pass_, FetchPass):
        return _out(status.REFUSED, str(url), detail="a FetchPass from request_access is required")
    if pass_.tier is None or pass_.tier < tier:
        return _out(status.REFUSED, str(url), detail=f"pass does not allow tier {tier}")
    if not pass_.permits(url):
        return _out(status.REFUSED, url, detail="url not permitted by pass")
    if cache is not None and cache.tier != pass_.tier:
        return _out(status.REFUSED, url, detail="response cache tier does not match the pass tier")
    if cache is not None and not refresh:
        hit = cache.get(url)
        if hit is not None:
            return hit
    pol = politeness or Politeness()
    log = logger or get_logger()
    client = HttpClient(proxy=proxy, timeout=timeout, politeness=pol, tier=tier, logger=log)
    checker = robots or RobotsChecker(client)
    ok, why = checker.allowed(url, pass_)
    if not ok:
        return _out(status.ROBOTS_BLOCKED, url, detail=why)
    parts = urlsplit(url)
    host = parts.hostname or ""
    code: object = "error"
    started = time.monotonic()
    try:
        with pol.slot(host):
            started = time.monotonic()
            resp = navigator(url, pass_, dict(options), timeout, proxy)
        code = resp.status
    except Exception as exc:
        code = "timeout" if _is_timeout(exc) else "error"
        return _out(status.TIMEOUT if code == "timeout" else status.CONNECTION_FAILED, url, detail=type(exc).__name__)
    finally:
        log_request(host, parts.path, code, time.monotonic() - started, tier, log)
    if resp.blocked_url is not None:
        detail = describe(resp.blocked_hosts)
        log.info(detail)
        return _out(status.REFUSED, url, detail=detail)
    final = resp.final_url or url
    if final != url:
        if not pass_.permits(final):
            return _out(status.REFUSED, final, resp.status, detail="final url not permitted by pass")
        ok, why = checker.allowed(final, pass_)
        if not ok:
            return _out(status.ROBOTS_BLOCKED, final, detail=why)
    if len(resp.body) > max_body_bytes:
        return _out(status.HTTP_ERROR, final, resp.status, detail=f"body too large (cap {max_body_bytes} bytes)")
    if _is_challenge(RawResponse(resp.status, resp.body, resp.headers)) and (resp.status == 200 or resp.status in (403, 429, 503)):
        return _out(status.CHALLENGE_PAGE, final, resp.status, detail="challenge page markers")
    if resp.status >= 400 or resp.status < 200:
        return _out(status.HTTP_ERROR, final, resp.status, detail=f"http {resp.status}")
    if cache is not None:
        cache.put(url, resp.status, resp.body)
    return _out(status.OK, final, resp.status, resp.body)
