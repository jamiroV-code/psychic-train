"""US equities market calendar for the equities board and refresh (S9A, D-2).

Pure code, no clock of its own and no new dependency: every function takes
`now` (a tz-aware timestamp, naive values are read as Z time) and answers in
Z time. US Eastern is a hand-rolled rule, not `zoneinfo`: daylight time runs
from the 2nd Sunday of March to the 1st Sunday of November, so the regular
16:00 Eastern close is 20:00Z in daylight time and 21:00Z otherwise.

* A session's bar is due `BAR_DUE_AFTER_MINUTES` after its close.
* Stale: the newest daily bar is older than the newest due session, so
  weekends and holidays are never overdue.
* Partial: the bar's session is not yet due (`1w`: any session of its week).
* Next refresh: the first session close + `REFRESH_DELAY_MINUTES` strictly
  after now.

Sessions come from `lse_adapter.is_nyse_session`. Early closes and special
one-off closures are not modelled (residual AC-S9-r2).
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from api.data.freshness import as_utc
from api.data.lse_adapter import is_nyse_session

BAR_DUE_AFTER_MINUTES = 60
REFRESH_DELAY_MINUTES = 30
# Longest search for a session; the longest real gap is a 4-day weekend.
_MAX_SCAN_DAYS = 15


def _nth_sunday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))


def is_eastern_daylight(d: date) -> bool:
    """True when the US Eastern close on day `d` falls in daylight time."""
    return _nth_sunday(d.year, 3, 2) <= d < _nth_sunday(d.year, 11, 1)


def session_close_utc(d: date) -> pd.Timestamp:
    """The regular 16:00 US Eastern close of day `d`, in Z time."""
    hour = 20 if is_eastern_daylight(d) else 21
    return as_utc(pd.Timestamp(d.year, d.month, d.day, hour))


def _bar_due_at(d: date) -> pd.Timestamp:
    return session_close_utc(d) + pd.Timedelta(minutes=BAR_DUE_AFTER_MINUTES)


def bar_due_at(d) -> pd.Timestamp:
    """Public: the instant session `d`'s final daily bar is due (UTC)."""
    return _bar_due_at(d)


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, pd.Timestamp):
        return value
    ts = as_utc(value)
    return None if ts is None else ts.date()


def last_due_session(now) -> date:
    """The newest session whose close + `BAR_DUE_AFTER_MINUTES` <= now."""
    now = as_utc(now)
    d = now.date()
    for _ in range(_MAX_SCAN_DAYS):
        if is_nyse_session(d) and _bar_due_at(d) <= now:
            return d
        d -= timedelta(days=1)
    return d


def bar_is_stale(last_bar_date, now) -> bool:
    """True when the newest daily bar predates the newest due session. An
    unknown bar (None) is not stale."""
    bar_day = _as_date(last_bar_date)
    if bar_day is None:
        return False
    return bar_day < last_due_session(now)


def bar_is_partial(last_bar_date, now, timeframe: str = "1d") -> bool | None:
    """True while the bar is still forming. For `1d` that is its session not
    yet due; for `1w` pass the newest DAILY bar's date: the weekly bar is
    partial while any session of that Monday-to-Friday week is not yet due.
    None for an unknown bar."""
    bar_day = _as_date(last_bar_date)
    if bar_day is None:
        return None
    now = as_utc(now)
    if timeframe == "1w":
        monday = bar_day - timedelta(days=bar_day.weekday())
        week = (monday + timedelta(days=i) for i in range(5))
        return any(is_nyse_session(d) and _bar_due_at(d) > now for d in week)
    return _bar_due_at(bar_day) > now


def next_refresh_at(now) -> pd.Timestamp:
    """The first session close + `REFRESH_DELAY_MINUTES` strictly after now,
    skipping weekends and holidays."""
    now = as_utc(now)
    d = now.date()
    for _ in range(_MAX_SCAN_DAYS):
        if is_nyse_session(d):
            at = session_close_utc(d) + pd.Timedelta(minutes=REFRESH_DELAY_MINUTES)
            if at > now:
                return at
        d += timedelta(days=1)
    return session_close_utc(d) + pd.Timedelta(minutes=REFRESH_DELAY_MINUTES)
