"""Google Trends proxy adapter via the unofficial `pytrends` library (item 47).

RESEARCH finding (Risk Prediction #2a): `pytrends` (GeneralMills/pytrends) is
confirmed archived/unmaintained since April 2025 — a permanently dead source
is a different failure mode than a normal flaky API, so this adapter's
failure handling distinguishes *transient* failure from *sustained*
failure, unlike the other two narrative adapters:

- A single failed live call is transient: this call returns
  `status="unavailable"`, retried on the next refresh (item 47's exact
  language) — it does NOT silently fall back to serving a stale cached
  value labeled as if it were current.
- Once `PYTRENDS_DEAD_THRESHOLD_DAYS` (7) have passed with zero successful
  live fetches, the call instead returns `status="presumed-dead"` — a
  distinct, more severe signal than a same-day blip, consumed by
  `trigger.compute_trigger`'s minimum-available-source-count rule (item
  47a) to cap `trust_weight` rather than silently treating a dead source as
  merely absent-today.

Public Contracts: never raises past this module's boundary — `pytrends`
itself may not even be installed (it is not a hard dependency of this
plan's own `pyproject.toml`, precisely because it is unmaintained); an
`ImportError` here is treated exactly like any other fetch failure.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from api.data import cache

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0
TIMEOUT_SECONDS = 10.0
PYTRENDS_DEAD_THRESHOLD_DAYS = 7

Status = Literal["ok", "unavailable", "presumed-dead"]


@dataclass
class TrendResult:
    keyword: str
    value: float | None  # normalized (0-100) interest-over-time value, most recent point
    as_of: str | None
    status: Status


def _fetch_live(keyword: str) -> tuple[float | None, str | None]:
    """Attempt a live pytrends fetch. Returns (value, as_of) or (None, None)
    on any failure — including `pytrends` not being importable at all.
    """
    try:
        from pytrends.request import TrendReq  # unofficial, archived since 2025-04
    except Exception:
        return None, None

    for attempt in range(MAX_RETRIES):
        try:
            pytrends = TrendReq(timeout=(TIMEOUT_SECONDS, TIMEOUT_SECONDS))
            pytrends.build_payload([keyword], timeframe="now 7-d")
            df = pytrends.interest_over_time()
            if df is None or df.empty or keyword not in df.columns:
                return None, None
            last = df.iloc[-1]
            value = float(last[keyword])
            as_of = df.index[-1].strftime("%Y-%m-%d")
            return value, as_of
        except Exception:
            if attempt == MAX_RETRIES - 1:
                return None, None
            time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
    return None, None


def _days_since(date_str: str) -> float | None:
    try:
        then = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return (datetime.now(timezone.utc) - then).total_seconds() / 86400.0


def fetch_trend(keyword: str) -> TrendResult:
    """Fetch today's Google Trends interest for `keyword`.

    On a live-fetch failure, checks how long it's been since the last
    successful fetch was archived: under `PYTRENDS_DEAD_THRESHOLD_DAYS`,
    this call is `unavailable` (transient); at or past it, `presumed-dead`
    (sustained) — see module docstring. Neither failure path serves the
    stale cached value as `value` (that would defeat the point of the
    distinction: a presumed-dead record must never be silently reused as if
    fresh, per item 47a's staleness test).
    """
    cache.bootstrap_cache_dirs()
    value, as_of = _fetch_live(keyword)

    if value is not None and as_of is not None:
        cache.write_narrative_point("pytrends", keyword, as_of, value, source_status="fresh")
        return TrendResult(keyword=keyword, value=value, as_of=as_of, status="ok")

    history = cache.read_narrative_series("pytrends", keyword)
    if history is None or history.empty:
        return TrendResult(keyword=keyword, value=None, as_of=None, status="unavailable")

    last_row = history.sort_values("date").iloc[-1]
    days_since = _days_since(str(last_row["date"]))
    if days_since is not None and days_since >= PYTRENDS_DEAD_THRESHOLD_DAYS:
        return TrendResult(keyword=keyword, value=None, as_of=str(last_row["date"]), status="presumed-dead")

    return TrendResult(keyword=keyword, value=None, as_of=str(last_row["date"]), status="unavailable")
