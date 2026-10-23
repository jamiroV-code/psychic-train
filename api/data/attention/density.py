"""SPEC Annex A.1: tweet rate per coin per completed UTC day from a newest-first sample. Pure; no network, no I/O.

A day's window is D 00:00 to D+1 00:00 UTC. With k unique posts in the window, N the target and N_min the floor:
- window start reached with k < N: value k (exact);
- k reaches N: value 24 * N / span_hours, span from the window end to the N-th newest post, floor 0.25 h (`capped`);
- a load limit (page cap or daily read budget) with N_min <= k < N: the same formula with k (`capped`, `pagecap`);
- otherwise the coin-day is missing (None), never 0.

A value is storable only once the injected clock is at or after the window end (yesterday-only). A zero is kept
only when the pass's canary returned data and the coin's trailing median is below 5 (AC3).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

SPAN_FLOOR_H = 0.25
ZERO_MEDIAN_MAX = 5.0
SPAM_SPIKE_RATIO = 10.0  # same ratio as api.data.attention.xsearch
MAX_PER_AUTHOR = 3


@dataclass(frozen=True)
class Post:
    author: str
    text: str
    created_at: datetime


@dataclass(frozen=True)
class DayResult:
    value: float
    n: int
    span_hours: float
    capped: bool
    pagecap: bool


def _aware(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("clock must be timezone-aware UTC")
    return now.astimezone(timezone.utc)


def window(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(0), tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def completed_day(now: datetime) -> date:
    """The newest UTC day that is complete at `now` (yesterday)."""
    return _aware(now).date() - timedelta(days=1)


def storable(day: date, now: datetime) -> bool:
    return _aware(now) >= window(day)[1]


def dedupe(posts: list[Post]) -> list[Post]:
    """Drop identical text (case and outer space folded) and keep at most 3 posts per author, order kept."""
    seen: set[str] = set()
    per_author: dict[str, int] = {}
    out = []
    for p in posts:
        key = " ".join(p.text.split()).casefold()
        if key in seen or per_author.get(p.author, 0) >= MAX_PER_AUTHOR:
            continue
        seen.add(key)
        per_author[p.author] = per_author.get(p.author, 0) + 1
        out.append(p)
    return out


def _rate(k: int, oldest: datetime, end: datetime) -> tuple[float, float]:
    span = max((end - oldest).total_seconds() / 3600.0, SPAN_FLOOR_H)
    return 24.0 * k / span, span


def day_value(day: date, times: list[datetime], *, n_target: int, n_min: int, window_start_reached: bool,
              limit_hit: bool = False) -> DayResult | None:
    """Annex A.1 value for `day` from post timestamps (any order); None when the coin-day is missing."""
    if not (isinstance(n_target, int) and isinstance(n_min, int) and 0 < n_min <= n_target):
        raise ValueError("need 0 < n_min <= n_target")
    start, end = window(day)
    inside = sorted((_aware(t) for t in times if start <= _aware(t) < end), reverse=True)
    k = len(inside)
    if k >= n_target:
        value, span = _rate(n_target, inside[n_target - 1], end)
        return DayResult(value, n_target, span, True, False)
    if window_start_reached:
        return DayResult(float(k), k, 24.0, False, False)
    if limit_hit and k >= n_min:
        value, span = _rate(k, inside[-1], end)
        return DayResult(value, k, span, True, True)
    return None


def finalize(result: DayResult | None, *, canary_ok: bool, trailing_median: float | None) -> float | None:
    """The value to store, or None (failed or missing). A zero needs canary data and a trailing median below 5.

    A non-finite or negative value is never a count: None.
    """
    if result is None or not math.isfinite(result.value) or result.value < 0:
        return None
    if result.value == 0 and not (canary_ok and trailing_median is not None and trailing_median < ZERO_MEDIAN_MAX):
        return None
    return result.value


def is_spike(value: float, trailing_median: float | None) -> bool:
    return bool(trailing_median) and trailing_median > 0 and value > SPAM_SPIKE_RATIO * trailing_median
