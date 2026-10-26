"""SPEC AC42, AC54, Annex A.1b point 3: the X read-sample density and the per-unit summary. Pure; no network.

Changed from A.1 so the sample matches the read budget: N counts raw timeline entries READ (from the raw pages,
the unit the daily budget counts), k counts tweets COUNTED after parsing and the filters, and the span runs from
the window end to the oldest READ tweet.
- window start reached: value k (exact), whatever N;
- N entries read before the window start: value 24 * k / span_hours, span floor 0.25 h (`capped`);
- the page cap hit with N_min <= read < N: the same formula (`capped`, `pagecap`);
- otherwise the coin-day is missing (None), never 0: `window_not_reached` when no read tweet is inside the window
  yet, `short_result` below N_min;
- a value of 0 needs the day's canary data, else it is missing (`zero_without_canary`). `density.finalize` still
  applies the trailing-median part of AC3 when the value is stored.
The window start counts as reached when a read tweet is older than it or the cursor ran out (`x_window`); then
k is the exact count even below N_min (low attention is a valid measurement).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from api.data.attention import density, x_filters, x_window


def read_sample_value(day: date, **kw) -> density.DayResult | None:
    return read_sample_outcome(day, **kw)[0]


def read_sample_outcome(day: date, *, n_read: int, counted_times: list[datetime], oldest_read: datetime | None,
                        window_start_reached: bool, page_cap_hit: bool, n_target: int, n_min: int,
                        canary_ok: bool) -> tuple[density.DayResult | None, str | None]:
    """(value, None), or (None, the missing reason)."""
    if not (isinstance(n_target, int) and isinstance(n_min, int) and 0 < n_min <= n_target):
        raise ValueError("need 0 < n_min <= n_target")
    if not isinstance(n_read, int) or isinstance(n_read, bool) or n_read < 0:
        raise ValueError("n_read must be a non-negative int")
    end = density.window(day)[1]
    k = sum(1 for t in counted_times if x_window.in_window(t, day))
    if window_start_reached:
        result = density.DayResult(float(k), k, 24.0, False, False)
    elif oldest_read is None or oldest_read.astimezone(timezone.utc) >= end:
        return None, "window_not_reached"
    elif n_read >= n_target or (page_cap_hit and n_read >= n_min):
        oldest = oldest_read.astimezone(timezone.utc)
        span = max((end - oldest).total_seconds() / 3600.0, density.SPAN_FLOOR_H)
        result = density.DayResult(24.0 * k / span, k, span, True, n_read < n_target)
    else:
        return None, "short_result"
    if result.value == 0 and canary_ok is not True:
        return None, "zero_without_canary"
    return result, None


@dataclass(frozen=True)
class UnitSummary:
    result: density.DayResult | None
    n_read: int
    n_counted: int
    exclusions: dict
    unique_authors: int
    top_author_share: float | None
    engagement: float
    median_views: float | None
    read_age_hours: float | None
    missing_reason: str | None = None


def summarize(day: date, read_tweets: list[x_filters.Tweet], *, n_read: int, window_start_reached: bool,
              page_cap_hit: bool, canary_ok: bool, coin: x_filters.Coin, policy: x_filters.FilterPolicy, n_target: int, n_min: int,
              now: datetime) -> UnitSummary:
    """Filter the parsed tweets of one attempt and compute the value and the quality metrics."""
    f = x_filters.filter_tweets(read_tweets, coin, day, policy)
    oldest = min((t.date for t in read_tweets), default=None)
    result, why = read_sample_outcome(day, n_read=n_read, counted_times=[t.date for t in f.counted],
                                      oldest_read=oldest, window_start_reached=window_start_reached,
                                      page_cap_hit=page_cap_hit, n_target=n_target, n_min=n_min, canary_ok=canary_ok)
    return UnitSummary(result, n_read, len(f.counted), f.exclusions, f.unique_authors, f.top_author_share,
                       x_filters.engagement_sum(f.counted), x_filters.median_views(f.counted),
                       x_filters.read_age_hours(f.counted, now), why)
