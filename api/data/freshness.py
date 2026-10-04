"""Pure OHLCV freshness rules (T32 / S1, decisions B2-B5).

No ccxt import and no clock of its own: every function takes `now`
explicitly, so the adapter (`ccxt_adapter._now()`), the board and later
slices (S2, S3, S8) share one definition and tests inject time.

* Fresh (B4): the cache was fetched inside the CURRENT bar and less than
  `FORMING_TTL` ago. The forming candle therefore expires after its TTL and
  at every bar boundary.
* Stale (B5): reference now minus the newest bar's open is MORE than
  2 x timeframe + 900 s. `1w` is judged on its daily bar, so its threshold is
  the daily one and the caller passes the daily bar's open.
* Partial (B5): the bar's open plus one timeframe lies after now.
"""
from __future__ import annotations

import pandas as pd

TIMEFRAME_SECONDS: dict[str, int] = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}

# How long a fetched forming candle may be served before it is refetched,
# even inside the same bar [estimate]. 1d = AC-13's 15 minutes.
FORMING_TTL: dict[str, int] = {"15m": 180, "1h": 300, "4h": 900, "1d": 900}

# Bars kept on every write (B2). 1d is never trimmed; 1w derives from all
# cached daily bars.
RETAIN_BARS: dict[str, int] = {"15m": 200, "1h": 200, "4h": 200}

# Explicit request size on the since=None tail path (B3). `limit=None` would
# ask for history from epoch 0.
TAIL_LIMIT: dict[str, int] = {"15m": 200, "1h": 200, "4h": 200, "1d": 500}

STALE_ALLOWANCE_SECONDS = 900

# 1970-01-05 was a Monday: weekly bars open on Mondays 00:00 UTC (ADR-5).
_MONDAY_EPOCH = pd.Timestamp("1970-01-05T00:00:00Z")


def as_utc(value) -> pd.Timestamp | None:
    """Any timestamp-like value as a tz-aware UTC `Timestamp`; None stays None."""
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        return None
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def iso_z(value) -> str | None:
    """ISO-8601 UTC with seconds and a trailing `Z` (gate convention 3)."""
    ts = as_utc(value)
    return None if ts is None else ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def current_bar_open(timeframe: str, now) -> pd.Timestamp:
    """Open of the bar that contains `now`."""
    now = as_utc(now)
    if timeframe == "1w":
        weeks = (now - _MONDAY_EPOCH) // pd.Timedelta(weeks=1)
        return _MONDAY_EPOCH + weeks * pd.Timedelta(weeks=1)
    return now.floor(pd.Timedelta(seconds=TIMEFRAME_SECONDS[timeframe]))


def cache_is_fresh(fetched_at, timeframe: str, now) -> bool:
    """True when `fetched_at` lies inside the current bar and is younger than
    the timeframe's `FORMING_TTL` (B4). An unknown fetch time is never fresh."""
    fetched_at, now = as_utc(fetched_at), as_utc(now)
    if fetched_at is None:
        return False
    if fetched_at < current_bar_open(timeframe, now):
        return False
    return (now - fetched_at).total_seconds() < FORMING_TTL[timeframe]


def stale_threshold_seconds(timeframe: str) -> int:
    judged_on = "1d" if timeframe == "1w" else timeframe
    return 2 * TIMEFRAME_SECONDS[judged_on] + STALE_ALLOWANCE_SECONDS


def is_stale(last_bar_open, timeframe: str, now) -> bool:
    """Strictly older than the threshold (B5). No bar means nothing to judge."""
    last_bar_open, now = as_utc(last_bar_open), as_utc(now)
    if last_bar_open is None:
        return False
    return (now - last_bar_open).total_seconds() > stale_threshold_seconds(timeframe)


def is_partial(last_bar_open, timeframe: str, now) -> bool | None:
    """True while the bar is still forming; None when there is no bar."""
    last_bar_open, now = as_utc(last_bar_open), as_utc(now)
    if last_bar_open is None:
        return None
    return last_bar_open + pd.Timedelta(seconds=TIMEFRAME_SECONDS[timeframe]) > now
