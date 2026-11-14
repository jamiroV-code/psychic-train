"""Pure internal-day disclosure; never fills, writes or fetches candles."""
from datetime import timedelta
from itertools import pairwise

import pandas as pd

from api.data.freshness import as_utc
from api.models.screener import DailyDataGap, DailyDataGapRange


def summarize_daily_data_gap(frame: pd.DataFrame) -> DailyDataGap:
    """Sort distinct observed UTC dates, then scan O(candles + gaps) storage.

    The supplied frame is untouched. Missing timestamps violate the adapter
    contract: they cannot honestly be treated as checked, continuous history.
    """
    if frame.empty:
        return DailyDataGap(missing_days=0, ranges=[])
    if "timestamp" not in frame:
        raise ValueError("Daily OHLCV requires timestamp")
    days = set()
    for value in frame["timestamp"]:
        try:
            timestamp = as_utc(value)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("Daily OHLCV contains an invalid timestamp") from exc
        if timestamp is None:
            raise ValueError("Daily OHLCV contains a null timestamp")
        days.add(timestamp.date())
    ordered = sorted(days)
    ranges = []
    missing_days = 0
    one_day = timedelta(days=1)
    for previous, current in pairwise(ordered):
        missing = (current - previous).days - 1
        if missing > 0:
            missing_days += missing
            ranges.append(DailyDataGapRange(start=previous + one_day, end=current - one_day))
    return DailyDataGap(missing_days=missing_days, ranges=ranges)
