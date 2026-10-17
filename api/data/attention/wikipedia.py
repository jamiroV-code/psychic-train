"""Wikipedia daily pageviews (keyless Wikimedia REST API)."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from api.data.attention.http_retry import Pacer, get_with_retry
from api.data.attention.types import MIN_HISTORY_DAYS, SourceSeries

BASE_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/user/{article}/daily/{start}/{end}"
)
LOOKBACK_DAYS = 100
MAX_RETRIES = 3  # retries after the first attempt, on HTTP 429 only
BACKOFF_BASE_SECONDS = 1.0
TIMEOUT_SECONDS = 10.0
RETRY_AFTER_CAP_SECONDS = 30.0
MIN_INTERVAL_SECONDS = 0.25  # about 4 calls/s, far under the Wikimedia guidance
# Wikimedia requires an identifying User-Agent with a contact URL.
USER_AGENT = ("psychic-train-attention/1.0 (https://github.com/jamirov-code/psychic-train; "
              "research dashboard) python-httpx")
PACER = Pacer(MIN_INTERVAL_SECONDS)


def fetch_series(symbol: str, article: str | None, *, client: httpx.Client,
                 today: date | None = None, sleep=time.sleep) -> SourceSeries:
    sym = symbol.upper()
    if not article:
        return SourceSeries("wikipedia", sym, [], "no-article", "no article mapped")
    today = today or datetime.now(timezone.utc).date()
    url = BASE_URL.format(
        article=quote(article.replace(" ", "_"), safe=""),
        start=(today - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d00"),
        end=(today - timedelta(days=1)).strftime("%Y%m%d00"),
    )
    try:
        resp = get_with_retry(client, url, sleep=sleep, retries=MAX_RETRIES, base=BACKOFF_BASE_SECONDS,
                              timeout=TIMEOUT_SECONDS, pacer=PACER, headers={"User-Agent": USER_AGENT},
                              retry_after_cap=RETRY_AFTER_CAP_SECONDS)
    except Exception as exc:
        return SourceSeries("wikipedia", sym, [], "unavailable", type(exc).__name__)
    if resp.status_code == 429:
        return SourceSeries("wikipedia", sym, [], "capped", "HTTP 429")
    if resp.status_code == 404:
        return SourceSeries("wikipedia", sym, [], "no-article", "HTTP 404")
    if resp.status_code >= 400:
        return SourceSeries("wikipedia", sym, [], "unavailable", f"HTTP {resp.status_code}")
    try:
        items = resp.json().get("items") or []
        pts = sorted(
            (datetime.strptime(str(i["timestamp"])[:8], "%Y%m%d").date(), float(i["views"]))
            for i in items
        )
    except Exception as exc:
        return SourceSeries("wikipedia", sym, [], "unavailable", type(exc).__name__)
    pts = [p for p in pts if p[0] < today]
    if not pts:
        return SourceSeries("wikipedia", sym, [], "unavailable", "empty response")
    if len(pts) < MIN_HISTORY_DAYS:
        return SourceSeries("wikipedia", sym, pts, "insufficient-history", f"{len(pts)} days")
    return SourceSeries("wikipedia", sym, pts, "ok", "")
