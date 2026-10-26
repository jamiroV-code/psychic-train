"""SPEC AC42, AC54, Annex A.1b point 3: the X read-sample density and the per-unit summary. Pure; no network.

Changed from A.1 so the sample matches the read budget: N counts raw timeline entries READ (from the raw pages,
the unit the daily budget counts), k counts tweets COUNTED after parsing and the filters, and the span runs from
the window end to the oldest READ tweet.
- window start reached: value k (exact), whatever N;
- N entries read before the window start: value 24 * k / span_hours, span floor 0.25 h (`capped`);
- the page cap hit with N_min <= read < N: the same formula (`capped`, `pagecap`);
- otherwise the coin-day is missing (None), never 0: `window_not_reached` when no read tweet is inside the window
  yet, `short_result` below N_min;
- a stalled cursor (`x_window.cursor_end`: a full page, then nothing or repeated ids) is never exact: the same
  formula from N_min read entries (`capped`, `pagecap`), else missing `cursor_stalled`;
- every value (exact, capped, window start, zero) needs the unit's account in today's canary (`canary_ok`), else
  the coin-day is missing (`account_not_canaried`) and nothing else is computed (planner decision T190, quality
  first: an account not shown today to see full results, e.g. one continuing after an inconclusive canary, gives
  no value). This also covers AC3's "zero only after a canary"; `density.finalize` still applies the
  trailing-median part of AC3 when the value is stored.
The window start counts as reached when a read tweet is older than it or the cursor ran out (`x_window`); then
k is the exact count even below N_min (low attention is a valid measurement).

The oldest read time comes from the raw timeline entries when the reader exposes their times (`raw_oldest`),
else from the parsed tweets. Taken from parsed tweets only, a tweet the library dropped can be older than every
parsed one, so the span is a little short and the capped value a little high; the parse-drop guard bounds the
drop to the threshold (20 percent of a page of at least 10 entries), which bounds that bias.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from api.data.attention import density, x_filters, x_window


def read_sample_value(day: date, **kw) -> density.DayResult | None:
    return read_sample_outcome(day, **kw)[0]


def read_sample_outcome(day: date, *, n_read: int, counted_times: list[datetime], oldest_read: datetime | None,
                        window_start_reached: bool, page_cap_hit: bool, n_target: int, n_min: int,
                        canary_ok: bool, cursor_exhausted: bool = False,
                        cursor_stalled: bool = False) -> tuple[density.DayResult | None, str | None]:
    """(value, None), or (None, the missing reason)."""
    if not (isinstance(n_target, int) and isinstance(n_min, int) and 0 < n_min <= n_target):
        raise ValueError("need 0 < n_min <= n_target")
    if not isinstance(n_read, int) or isinstance(n_read, bool) or n_read < 0:
        raise ValueError("n_read must be a non-negative int")
    if canary_ok is not True:
        return None, "account_not_canaried"
    end = density.window(day)[1]
    k = sum(1 for t in counted_times if x_window.in_window(t, day))
    if window_start_reached:
        result = density.DayResult(float(k), k, 24.0, False, False)
    elif oldest_read is None or oldest_read.astimezone(timezone.utc) >= end:
        return None, "window_not_reached"
    elif n_read >= n_target or ((page_cap_hit or cursor_stalled) and n_read >= n_min):
        oldest = oldest_read.astimezone(timezone.utc)
        span = max((end - oldest).total_seconds() / 3600.0, density.SPAN_FLOOR_H)
        result = density.DayResult(24.0 * k / span, k, span, True, n_read < n_target)
    else:
        return None, "cursor_stalled" if cursor_stalled else "short_result"
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


def oldest_read(read_tweets: list[x_filters.Tweet], raw_oldest: datetime | None = None) -> datetime | None:
    """The older of the raw entries' oldest time (when the reader exposes it) and the oldest parsed tweet."""
    times = [t.date.astimezone(timezone.utc) for t in read_tweets]
    if raw_oldest is not None:
        times.append(raw_oldest.astimezone(timezone.utc))
    return min(times, default=None)


def summarize(day: date, read_tweets: list[x_filters.Tweet], *, n_read: int, window_start_reached: bool,
              page_cap_hit: bool, canary_ok: bool, coin: x_filters.Coin, policy: x_filters.FilterPolicy, n_target: int, n_min: int,
              now: datetime, cursor_exhausted: bool = False, cursor_stalled: bool = False,
              raw_oldest: datetime | None = None) -> UnitSummary:
    """Filter the parsed tweets of one attempt and compute the value and the quality metrics."""
    f = x_filters.filter_tweets(read_tweets, coin, day, policy)
    result, why = read_sample_outcome(day, n_read=n_read, counted_times=[t.date for t in f.counted],
                                      oldest_read=oldest_read(read_tweets, raw_oldest),
                                      window_start_reached=window_start_reached, page_cap_hit=page_cap_hit,
                                      n_target=n_target, n_min=n_min, canary_ok=canary_ok,
                                      cursor_exhausted=cursor_exhausted, cursor_stalled=cursor_stalled)
    return UnitSummary(result, n_read, len(f.counted), f.exclusions, f.unique_authors, f.top_author_share,
                       x_filters.engagement_sum(f.counted), x_filters.median_views(f.counted),
                       x_filters.read_age_hours(f.counted, now), why)
