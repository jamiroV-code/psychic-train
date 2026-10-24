"""SPEC AC42, AC54, Annex A.1b point 3: the X read-sample density and the per-unit summary. Pure; no network.

Changed from A.1 so the sample matches the read budget: N counts raw timeline entries READ (from the raw pages,
the unit the daily budget counts), k counts tweets COUNTED after parsing and the filters, and the span runs from
the window end to the oldest READ tweet.
- window start reached: value k (exact), whatever N;
- N entries read before the window start: value 24 * k / span_hours, span floor 0.25 h (`capped`);
- the page cap hit with N_min <= read < N: the same formula (`capped`, `pagecap`);
- otherwise the coin-day is missing (None), never 0. The zero rule of AC3 is `density.finalize`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from api.data.attention import density, x_filters, x_window


def read_sample_value(day: date, *, n_read: int, counted_times: list[datetime], oldest_read: datetime | None,
                      window_start_reached: bool, page_cap_hit: bool, n_target: int,
                      n_min: int) -> density.DayResult | None:
    if not (isinstance(n_target, int) and isinstance(n_min, int) and 0 < n_min <= n_target):
        raise ValueError("need 0 < n_min <= n_target")
    if not isinstance(n_read, int) or isinstance(n_read, bool) or n_read < 0:
        raise ValueError("n_read must be a non-negative int")
    end = density.window(day)[1]
    k = sum(1 for t in counted_times if x_window.in_window(t, day))
    if window_start_reached:
        return density.DayResult(float(k), k, 24.0, False, False)
    if oldest_read is None:
        return None
    if n_read >= n_target or (page_cap_hit and n_read >= n_min):
        oldest = oldest_read.astimezone(timezone.utc)
        span = max((end - oldest).total_seconds() / 3600.0, density.SPAN_FLOOR_H)
        return density.DayResult(24.0 * k / span, k, span, True, n_read < n_target)
    return None


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


def summarize(day: date, read_tweets: list[x_filters.Tweet], *, n_read: int, window_start_reached: bool,
              page_cap_hit: bool, coin: x_filters.Coin, policy: x_filters.FilterPolicy, n_target: int, n_min: int,
              now: datetime) -> UnitSummary:
    """Filter the parsed tweets of one attempt and compute the value and the quality metrics."""
    f = x_filters.filter_tweets(read_tweets, coin, day, policy)
    oldest = min((t.date for t in read_tweets), default=None)
    result = read_sample_value(day, n_read=n_read, counted_times=[t.date for t in f.counted], oldest_read=oldest,
                               window_start_reached=window_start_reached, page_cap_hit=page_cap_hit,
                               n_target=n_target, n_min=n_min)
    return UnitSummary(result, n_read, len(f.counted), f.exclusions, f.unique_authors, f.top_author_share,
                       x_filters.engagement_sum(f.counted), x_filters.median_views(f.counted),
                       x_filters.read_age_hours(f.counted, now))
