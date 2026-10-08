"""Golden-value + boundary tests for api/analytics/indicators/rsi.py (moved
from test_momentum.py, T36 / S4).
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.analytics.indicators.rsi import RSI_LENGTH, compute_rsi


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


def test_compute_rsi_returns_none_below_length():
    # Explicit None, never a silently short-window number.
    assert compute_rsi(_make_daily_df([100.0] * (RSI_LENGTH - 1))) is None
    assert compute_rsi(None) is None
    assert compute_rsi(_make_daily_df([float(100 + i) for i in range(RSI_LENGTH + 1)])) is not None
