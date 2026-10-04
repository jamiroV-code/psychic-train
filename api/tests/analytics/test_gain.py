"""Golden and boundary tests for api/analytics/indicators/gain.py (T34 / S2).

AC-S2-1: a chip is the current candle, open to latest price, with a
Monday-anchored week. AC-S2-2: N/A with a reason, never 0; a real flat
candle is 0.0.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from api.analytics.indicators.gain import compute_gain_chip, compute_gain_chips


def _bars(opens_ts: list[str], opens: list[float], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(opens_ts, utc=True),
            "open": opens,
            "high": [max(o, c) for o, c in zip(opens, closes)],
            "low": [min(o, c) for o, c in zip(opens, closes)],
            "close": closes,
            "volume": [1.0] * len(opens),
            "source": "test",
        }
    )


NOW = pd.Timestamp("2026-10-03T14:22:00Z")


def test_chip_15m_golden_open_to_latest():
    # Older bar's close is ignored: the chip reads the newest bar only.
    df = _bars(["2026-10-03T14:00:00Z", "2026-10-03T14:15:00Z"], [90.0, 200.0], [95.0, 203.0])
    chip = compute_gain_chip(df, "15m", NOW)
    assert chip.pct == pytest.approx(1.5)
    assert chip.open_ts == "2026-10-03T14:15:00Z"
    assert chip.is_partial is True
    assert chip.reason is None


def test_chip_1h_golden():
    df = _bars(["2026-10-03T13:00:00Z", "2026-10-03T14:00:00Z"], [10.0, 50.0], [12.0, 49.0])
    chip = compute_gain_chip(df, "1h", NOW)
    assert chip.pct == pytest.approx(-2.0)
    assert chip.open_ts == "2026-10-03T14:00:00Z"
    assert chip.is_partial is True


def test_chip_4h_golden():
    df = _bars(["2026-10-03T08:00:00Z", "2026-10-03T12:00:00Z"], [1.0, 400.0], [2.0, 410.0])
    chip = compute_gain_chip(df, "4h", NOW)
    assert chip.pct == pytest.approx(2.5)
    assert chip.open_ts == "2026-10-03T12:00:00Z"


def test_chip_1d_is_since_midnight_utc_golden():
    # Old meaning (first-to-last close) would read (120 - 100) / 100 = +20%.
    df = _bars(["2026-10-02T00:00:00Z", "2026-10-03T00:00:00Z"], [100.0, 110.0], [108.0, 120.0])
    chip = compute_gain_chip(df, "1d", NOW)
    assert chip.pct == pytest.approx(120.0 / 110.0 * 100.0 - 100.0)
    assert chip.open_ts == "2026-10-03T00:00:00Z"
    assert chip.is_partial is True


def test_chip_1w_monday_anchor_golden():
    daily = _bars(
        ["2026-09-28T00:00:00Z", "2026-09-29T00:00:00Z", "2026-09-30T00:00:00Z", "2026-10-01T00:00:00Z"],
        [100.0, 102.0, 101.0, 105.0],
        [102.0, 101.0, 104.0, 106.0],
    )
    chip = compute_gain_chip(None, "1w", pd.Timestamp("2026-10-01T12:00:00Z"), daily_df=daily)
    assert chip.pct == pytest.approx(6.0)
    assert chip.open_ts == "2026-09-28T00:00:00Z"
    assert chip.is_partial is True
    assert chip.stale is False
    assert chip.reason is None


def test_chip_1w_without_monday_bar_is_na():
    # Tue-Thu only: the derived bucket is still labelled Monday 28 Sep, but its
    # open would be Tuesday's, so the chip must not pretend to be the week.
    daily = _bars(
        ["2026-09-29T00:00:00Z", "2026-09-30T00:00:00Z", "2026-10-01T00:00:00Z"],
        [102.0, 101.0, 105.0],
        [101.0, 104.0, 106.0],
    )
    chip = compute_gain_chip(None, "1w", pd.Timestamp("2026-10-01T12:00:00Z"), daily_df=daily)
    assert chip.pct is None
    assert chip.reason == "insufficient-history"


def test_empty_frame_is_na_never_zero():
    for tf in ("15m", "1h", "4h", "1d", "1w"):
        chip = compute_gain_chip(pd.DataFrame(), tf, NOW, daily_df=pd.DataFrame())
        assert chip.pct is None, tf
        assert chip.reason == "insufficient-history"
        assert chip.open_ts is None


def test_nan_or_zero_open_is_na():
    for bad_open in (math.nan, 0.0, -1.0):
        df = _bars(["2026-10-03T14:00:00Z"], [bad_open], [10.0])
        chip = compute_gain_chip(df, "1h", NOW)
        assert chip.pct is None, bad_open
        assert chip.reason == "insufficient-history"
    nan_close = _bars(["2026-10-03T14:00:00Z"], [10.0], [math.nan])
    assert compute_gain_chip(nan_close, "1h", NOW).pct is None


def test_flat_candle_is_real_zero():
    df = _bars(["2026-10-03T14:00:00Z"], [50.0], [50.0])
    chip = compute_gain_chip(df, "1h", NOW)
    assert chip.pct == 0.0
    assert chip.reason is None
    assert chip.open_ts == "2026-10-03T14:00:00Z"


def test_is_partial_and_stale_flags_follow_reference_time():
    df = _bars(["2026-10-03T12:00:00Z"], [100.0], [101.0])
    # Bar 12:00-13:00: forming at 12:30, closed at 13:00 sharp.
    assert compute_gain_chip(df, "1h", pd.Timestamp("2026-10-03T12:30:00Z")).is_partial is True
    assert compute_gain_chip(df, "1h", pd.Timestamp("2026-10-03T13:00:00Z")).is_partial is False
    # 1h stale threshold 8100 s, strict.
    assert compute_gain_chip(df, "1h", pd.Timestamp("2026-10-03T14:15:00Z")).stale is False
    assert compute_gain_chip(df, "1h", pd.Timestamp("2026-10-03T14:15:01Z")).stale is True
    # 1w is judged on its newest daily bar (1d threshold 173700 s).
    daily = _bars(["2026-09-28T00:00:00Z", "2026-09-29T00:00:00Z"], [100.0, 101.0], [101.0, 102.0])
    fresh = pd.Timestamp("2026-09-29T00:00:00Z") + pd.Timedelta(seconds=173700)
    assert compute_gain_chip(None, "1w", fresh, daily_df=daily).stale is False
    assert compute_gain_chip(None, "1w", fresh + pd.Timedelta(seconds=1), daily_df=daily).stale is True


def test_adapter_status_maps_to_reason():
    empty = pd.DataFrame()
    assert compute_gain_chip(empty, "1h", NOW, status="bad_symbol").reason == "bad-symbol"
    assert compute_gain_chip(empty, "1h", NOW, status="unavailable").reason == "source-unavailable"
    assert compute_gain_chip(empty, "1h", NOW, status="ok").reason == "insufficient-history"
    assert compute_gain_chip(None, "1w", NOW, status="bad_symbol", daily_df=empty).reason == "bad-symbol"
    # Cached bars served while the source is down still give a real chip.
    df = _bars(["2026-10-03T14:00:00Z"], [100.0], [99.0])
    chip = compute_gain_chip(df, "1h", NOW, status="unavailable")
    assert chip.pct == pytest.approx(-1.0)
    assert chip.reason is None
    # The batch builder keeps every slot independent.
    chips = compute_gain_chips(
        {"15m": empty, "1h": df, "4h": empty, "1d": empty, "1w": empty},
        {"15m": "bad_symbol", "1h": "unavailable", "4h": "ok", "1d": "unavailable", "1w": "unavailable"},
        NOW,
    )
    assert chips["15m"].reason == "bad-symbol"
    assert chips["1h"].pct == pytest.approx(-1.0)
    assert chips["4h"].reason == "insufficient-history"
    assert chips["1w"].reason == "source-unavailable"
