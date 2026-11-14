"""Stored UTC-day gaps, bounded by observed candles rather than elapsed days."""
from datetime import date

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from api.analytics.daily_data_gap import summarize_daily_data_gap


@pytest.mark.parametrize("timestamps,missing,ranges", [
    ([], 0, []),
    (["2020-01-01"], 0, []),
    (["2020-01-01", "2020-01-02"], 0, []),
    (["2025-12-30", "2026-01-03", "2026-02-02", "2026-01-31"], 31,
     [("2025-12-31", "2026-01-02"), ("2026-01-04", "2026-01-30"), ("2026-02-01", "2026-02-01")]),
    (["2026-01-04", "2026-01-01", "2026-01-01"], 2, [("2026-01-02", "2026-01-03")]),
    (["2026-01-01T23:00:00-02:00", "2026-01-04T00:00:00Z"], 1, [("2026-01-03", "2026-01-03")]),
    (["1900-01-01", "2200-01-01"], (date(2200, 1, 1)-date(1900, 1, 1)).days-1,
     [("1900-01-02", "2199-12-31")]),
])
def test_exact_intervals_and_unchanged_input(timestamps, missing, ranges):
    frame = pd.DataFrame({"timestamp": timestamps, "close": range(len(timestamps))})
    before = frame.copy(deep=True)
    result = summarize_daily_data_gap(frame)
    assert result.missing_days == missing
    assert [(r.start.isoformat(), r.end.isoformat()) for r in result.ranges] == ranges
    assert_frame_equal(frame, before)


def test_empty_without_columns_is_checked_zero():
    assert summarize_daily_data_gap(pd.DataFrame()).model_dump() == {"missing_days": 0, "ranges": []}


@pytest.mark.parametrize("frame", [pd.DataFrame({"close": [1]}), *[
    pd.DataFrame({"timestamp": [value]}) for value in (None, pd.NaT, "not-a-date")
]])
def test_invalid_nonempty_input_is_contract_error(frame):
    with pytest.raises(ValueError):
        summarize_daily_data_gap(frame)
