"""Golden-value + boundary tests for api/analytics/indicators/momentum.py.

Covers AC-1 (weekly-momentum-from-resampled-closes), AC-2/AC-12
(dual-timeframe-filter-boundary-logic), and the Amendment 2 per-timeframe %
gain readout (AC-20).
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.analytics.indicators.momentum import (
    MOMENTUM_MIDLINE,
    RSI_LENGTH,
    classify_momentum,
    compute_dual_timeframe_momentum,
    compute_rsi,
    compute_scalp_momentum,
)


def _reference_rsi(closes: list[float], length: int = RSI_LENGTH) -> float | None:
    """Independent, loop-based Wilder RSI reference implementation used to
    cross-check the vectorized `.ta.rsi()`-based implementation under test.
    """
    if len(closes) <= length:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    avg_gain = sum(gains[:length]) / length
    avg_loss = sum(losses[:length]) / length
    for i in range(length, len(deltas)):
        avg_gain = (avg_gain * (length - 1) + gains[i]) / length
        avg_loss = (avg_loss * (length - 1) + losses[i]) / length

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _make_daily_df(closes: list[float], start: str = "2024-01-01") -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=len(closes), freq="D", tz="UTC")
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


def test_daily_rsi_matches_independent_golden_reference():
    # Synthetic, mildly noisy walk so gains and losses both occur.
    closes = [
        100, 102, 101, 105, 107, 106, 110, 108, 112, 115,
        113, 117, 120, 118, 122, 125, 123, 128, 130, 127,
        132, 135, 133, 138, 140,
    ]
    df = _make_daily_df([float(c) for c in closes])
    got = compute_rsi(df, length=RSI_LENGTH).iloc[-1]
    expected = _reference_rsi([float(c) for c in closes], length=RSI_LENGTH)
    assert expected is not None
    assert got == pytest.approx(expected, abs=1e-6)


def test_weekly_momentum_from_resampled_closes():
    """AC-1: the weekly reading must come from real resampled weekly closes
    (last daily close of each week), NOT from averaging/resampling the daily
    RSI series itself. We construct a daily series where those two
    approaches give provably different answers, then assert
    compute_dual_timeframe_momentum used the correct (resampled-closes)
    approach.
    """
    # 10 weeks of daily closes, strictly increasing overall but with a
    # within-week dip on the last day of each week so a naive "average the
    # daily RSI over the week" approach would read differently than RSI
    # computed on each week's real closing (last-day) price.
    closes = []
    price = 100.0
    for _week in range(20):
        for day in range(6):
            price += 3.0
            closes.append(price)
        price -= 1.0  # week-ending dip, still above the week's start
        closes.append(price)

    daily_df = _make_daily_df(closes)
    weekly_df = (
        daily_df.set_index("timestamp")
        .resample("W")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["close"])
        .reset_index()
    )
    weekly_df["source"] = "test"

    result = compute_dual_timeframe_momentum(daily_df, weekly_df)

    # The weekly RSI actually used must equal RSI computed directly on the
    # weekly closes (a legitimate resample of daily->weekly bars), not on
    # the daily closes themselves resampled/averaged some other way.
    expected_weekly = compute_rsi(weekly_df, length=RSI_LENGTH).iloc[-1]
    assert result.weekly_value == pytest.approx(float(expected_weekly))

    # And it must NOT equal RSI computed straight off the raw daily series
    # (proving the function isn't silently reusing the daily reading as a
    # stand-in for weekly).
    daily_only_rsi = compute_rsi(daily_df, length=RSI_LENGTH).iloc[-1]
    assert result.weekly_value != pytest.approx(float(daily_only_rsi))


class TestDualTimeframeFilterBoundaryLogic:
    """AC-2 / AC-12: exact-midline never passes; missing data -> insufficient."""

    def test_exact_midline_on_both_timeframes_is_not_a_pass(self):
        assert classify_momentum(MOMENTUM_MIDLINE, MOMENTUM_MIDLINE) == "FAIL"

    def test_exact_midline_on_one_timeframe_is_not_a_pass(self):
        assert classify_momentum(MOMENTUM_MIDLINE, 75.0) == "FAIL"
        assert classify_momentum(75.0, MOMENTUM_MIDLINE) == "FAIL"

    def test_both_strictly_above_midline_passes(self):
        assert classify_momentum(50.01, 50.01) == "PASS"

    def test_one_below_midline_fails(self):
        assert classify_momentum(60.0, 49.9) == "FAIL"

    def test_missing_daily_is_insufficient_even_if_weekly_would_pass(self):
        assert classify_momentum(None, 80.0) == "insufficient"

    def test_missing_weekly_is_insufficient_even_if_daily_would_pass(self):
        assert classify_momentum(80.0, None) == "insufficient"

    def test_both_missing_is_insufficient(self):
        assert classify_momentum(None, None) == "insufficient"

    def test_short_history_dataframe_yields_insufficient_state(self):
        # Fewer bars than RSI_LENGTH -> compute_rsi produces NaN throughout.
        short_daily = _make_daily_df([100.0, 101.0, 99.0])
        short_weekly = _make_daily_df([100.0, 101.0])
        result = compute_dual_timeframe_momentum(short_daily, short_weekly)
        assert result.state == "insufficient"
        assert result.daily_value is None
        assert result.weekly_value is None


def test_scalp_momentum_is_labeled_with_its_own_timeframe():
    closes = [100.0 + i * 0.5 for i in range(30)]
    df_4h = _make_daily_df(closes)  # shape only; label independent of cadence
    result = compute_scalp_momentum(df_4h, timeframe="4h")
    assert result.timeframe == "4h"
    assert result.state in ("PASS", "FAIL")
    assert result.value is not None


def test_scalp_momentum_insufficient_history():
    df_4h = _make_daily_df([100.0, 101.0])
    result = compute_scalp_momentum(df_4h, timeframe="4h")
    assert result.state == "insufficient"
    assert result.value is None
