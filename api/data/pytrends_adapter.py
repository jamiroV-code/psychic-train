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
            if "isPartial" in df.columns:
                df = df[~df["isPartial"].astype(bool)]
                if df.empty:
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


# --- narrative-v2 RFC-3 (ADR-3): batched multi-keyword fetch ---------------
#
# Additive: `fetch_trend` / `_fetch_live` above are unchanged. Google Trends
# accepts at most 5 terms per request and rescales each request 0-100 on its
# own. To put more than 5 keywords on one scale we use anchor-keyword
# chaining: every request carries the same `anchor` term plus up to 4 others,
# and batch b is rescaled onto batch 0 by `anchor_b0 / anchor_b`.
#
# Guard: if the anchor's value in a batch (or in the reference batch 0) is
# missing or below ANCHOR_EPSILON, the ratio is undefined/unstable, so every
# keyword in that batch is `insufficient` — a ratio is never fabricated.
# These helpers never write to the cache; callers decide what to archive.

BATCH_SIZE = 5  # pytrends' per-request term cap
ANCHOR_EPSILON = 1.0

BatchStatus = Literal["ok", "insufficient", "unavailable"]


@dataclass
class ChainedValue:
    value: float | None
    status: BatchStatus
    reason: str | None = None


def plan_batches(keywords: list[str], anchor: str | None = None) -> list[list[str]]:
    """Split keywords into requests of <= BATCH_SIZE terms, each starting
    with the shared anchor. Duplicates are dropped (first occurrence wins)."""
    uniq = list(dict.fromkeys(k for k in keywords if k))
    if not uniq:
        return []
    anchor = anchor or uniq[0]
    others = [k for k in uniq if k != anchor]
    per = BATCH_SIZE - 1
    if not others:
        return [[anchor]]
    return [[anchor, *others[i:i + per]] for i in range(0, len(others), per)]


def chain_batches(batch_values: list[dict[str, float | None] | None], batches: list[list[str]],
                  anchor: str) -> dict[str, ChainedValue]:
    """Rescale one observation (one date) of every batch onto batch 0's scale.

    `batch_values[i]` is keyword -> raw 0-100 value for `batches[i]`, or None
    when that request failed. Returns keyword -> ChainedValue.
    """
    out: dict[str, ChainedValue] = {}
    ref_vals = batch_values[0] if batch_values else None
    ref = None if ref_vals is None else ref_vals.get(anchor)
    for i, (terms, vals) in enumerate(zip(batches, batch_values)):
        members = terms if i == 0 else [t for t in terms if t != anchor]
        if vals is None:
            for t in members:
                out[t] = ChainedValue(None, "unavailable", "batch-fetch-failed")
            continue
        a = vals.get(anchor)
        if ref is None or ref < ANCHOR_EPSILON or a is None or a < ANCHOR_EPSILON:
            for t in members:
                out[t] = ChainedValue(None, "insufficient", "anchor-below-epsilon")
            continue
        scale = 1.0 if i == 0 else ref / a
        for t in members:
            v = vals.get(t)
            if v is None:
                out[t] = ChainedValue(None, "unavailable", "keyword-missing")
            else:
                out[t] = ChainedValue(float(v) * scale, "ok")
    return out


def _fetch_batch_live(keywords: list[str], timeframe: str = "now 7-d"):
    """One live request for up to BATCH_SIZE terms. Returns the raw
    interest_over_time frame, or None on any failure (incl. no pytrends)."""
    try:
        from pytrends.request import TrendReq
    except Exception:
        return None
    for attempt in range(MAX_RETRIES):
        try:
            client = TrendReq(timeout=(TIMEOUT_SECONDS, TIMEOUT_SECONDS))
            client.build_payload(list(keywords), timeframe=timeframe)
            df = client.interest_over_time()
            if df is None or df.empty:
                return None
            return df
        except Exception:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
    return None


@dataclass
class BatchedTrends:
    as_of: str | None
    values: dict[str, ChainedValue]
    requests: int


def fetch_trends_batched(keywords: list[str], anchor: str | None = None) -> BatchedTrends:
    """Latest "now 7-d" point for every keyword, anchor-chained onto one scale.

    A batch whose last timestamp differs from batch 0's is treated as failed
    (values from different moments are not chained). Never raises."""
    batches = plan_batches(keywords, anchor)
    if not batches:
        return BatchedTrends(None, {}, 0)
    anchor = batches[0][0]
    as_of: str | None = None
    batch_values: list[dict[str, float | None] | None] = []
    for i, terms in enumerate(batches):
        try:
            df = _fetch_batch_live(terms)
        except Exception:
            df = None
        if df is None or df.empty:
            batch_values.append(None)
            continue
        day = df.index[-1].strftime("%Y-%m-%d")
        if i == 0:
            as_of = day
        elif as_of is not None and day != as_of:
            batch_values.append(None)
            continue
        last = df.iloc[-1]
        batch_values.append({t: (float(last[t]) if t in df.columns and last[t] == last[t] else None)
                             for t in terms})
    return BatchedTrends(as_of, chain_batches(batch_values, batches, anchor), len(batches))


def blend(values: list[float]) -> float:
    """Simple mean of per-keyword values already on one normalised scale."""
    return float(sum(values) / len(values))
