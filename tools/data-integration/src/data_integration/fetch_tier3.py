"""Tier 3: gated browser fetch through scrapling StealthyFetcher. Same gate, robots and status rules as tier 2.

Scope: gating, block-page mapping (challenge text, 403, captcha marker -> challenge_page / http_error) and option
pass-through. It is NOT proven against any real protected site and makes no bypass claim. Challenge solving is never
invoked: `solve_cloudflare` is not an allowed option and is refused if passed.
"""
from __future__ import annotations

from scrapling.fetchers import StealthyFetcher

from data_integration import status
from data_integration.fetch_tier1 import DEFAULT_MAX_BODY_BYTES, _out
from data_integration.fetch_tier2 import ALLOWED_OPTIONS, make_navigator, run_browser_fetch
from data_integration.gate import FetchPass

ALLOWED_OPTIONS_TIER3: frozenset[str] = ALLOWED_OPTIONS | {"humanize", "hide_canvas", "block_webrtc", "allow_webgl"}

# solve_cloudflare stays False even if the library default changes.
default_navigator = make_navigator(StealthyFetcher, {"solve_cloudflare": False})


def fetch(url: str, pass_: object, *, options: dict | None = None, navigator=None, cache=None, refresh: bool = False,
          politeness=None, robots=None, proxy: str | None = None, timeout: float = 10.0, logger=None,
          max_body_bytes: int = DEFAULT_MAX_BODY_BYTES):
    if not isinstance(pass_, FetchPass):
        return _out(status.REFUSED, str(url), detail="a FetchPass from request_access is required")
    if pass_.tier != 3:
        return _out(status.REFUSED, str(url), detail="tier 3 needs a pass with allowed tier 3")
    opts = dict(options or {})
    unknown = sorted(k for k in opts if k not in ALLOWED_OPTIONS_TIER3)
    if unknown:
        return _out(status.REFUSED, str(url), detail=f"option not allowed: {', '.join(unknown)}")
    return run_browser_fetch(3, url, pass_, navigator or default_navigator, opts, cache=cache, refresh=refresh,
                             politeness=politeness, robots=robots, proxy=proxy, timeout=timeout, logger=logger,
                             max_body_bytes=max_body_bytes)
