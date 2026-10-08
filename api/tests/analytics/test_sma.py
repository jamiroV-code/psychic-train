"""Golden-value + boundary tests for api/analytics/indicators/sma.py.

Covers AC-6 (60-period SMA line) and AC-17 (Amendment 2: the SMA
re-scales to whichever timeframe is active, not a fixed 60-calendar-day
window).
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.analytics.indicators.sma import SMA_LENGTH, compute_sma


def _make_df(closes: list[float], freq: str = "D") -> pd.DataFrame:
    idx = pd.date_range(start="2024-01-01", periods=len(closes), freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": idx,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [100.0] * len(closes),
            "source": "test",
        }
    )


def test_sma_golden_value():
    # 65 bars: first 5 constant at 10, remaining ramp 1..60 -> last 60-bar
    # window is exactly [1..60], mean = 30.5.
    closes = [10.0] * 5 + [float(i) for i in range(1, 61)]
    df = _make_df(closes)
    sma = compute_sma(df, length=SMA_LENGTH)
    assert sma.iloc[-1] == pytest.approx(30.5)


def test_sma_insufficient_history_is_explicit_not_zero_or_nan_rendered_as_valid():
    df = _make_df([100.0] * 10)  # fewer than 60 bars
    assert compute_sma(df, length=SMA_LENGTH) is None


def test_sma_period_rescales_with_timeframe():
    """AC-17: the same `compute_sma(length=60)` call must produce correct,
    distinguishable values on a daily fixture vs. a 4h fixture for the same
    underlying price shape — proving the window is period-based (60 bars of
    whichever timeframe), not pinned to a fixed 60-calendar-day span.
    """
    daily_closes = [10.0] * 5 + [float(i) for i in range(1, 61)]
    daily_df = _make_df(daily_closes, freq="D")
    daily_sma = compute_sma(daily_df, length=SMA_LENGTH).iloc[-1]

    # Same 65 bars, but at 4h cadence -> the SAME 60-period SMA calculation
    # (same last-60-bars-mean = 30.5) even though the *calendar* span is
    # totally different (65 * 4h ≈ 10.8 days vs 65 days) — proving the
    # function itself is period-based, not calendar-based.
    fourh_df = _make_df(daily_closes, freq="4h")
    fourh_sma = compute_sma(fourh_df, length=SMA_LENGTH).iloc[-1]

    assert daily_sma == pytest.approx(30.5)
    assert fourh_sma == pytest.approx(30.5)
    assert daily_sma == pytest.approx(fourh_sma)  # same period-based math either way

    # And the two fixtures' timestamps genuinely span different calendar
    # windows, proving this isn't a calendar-window coincidence.
    daily_span = daily_df["timestamp"].iloc[-1] - daily_df["timestamp"].iloc[0]
    fourh_span = fourh_df["timestamp"].iloc[-1] - fourh_df["timestamp"].iloc[0]
    assert daily_span != fourh_span
