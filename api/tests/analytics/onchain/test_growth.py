"""Floor/ramp rule, gate, pre-launch exclusion, stale rule (chain-growth RFC-4).

Synthetic series for rule logic; frozen real-data fixtures (commit 7143733)
for the D1 headline dates — the leg_boundary confirming-backtest pattern.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from api.analytics.onchain import growth
from api.analytics.onchain.response import STALE_AFTER_DAYS, is_stale

FIXTURES = Path(__file__).parent / "fixtures"


def _daily(values, start="2020-01-01") -> pd.Series:
    return pd.Series(np.asarray(values, float), index=pd.date_range(start, periods=len(values), freq="D"))


def _v_shape() -> pd.Series:
    return _daily(np.concatenate([
        np.full(250, 1000.0),
        np.linspace(1000, 400, 120),
        np.full(60, 400.0),
        np.linspace(400, 1000, 120),
        np.full(100, 1000.0),
    ]))


def _fixture(name: str) -> pd.Series:
    df = pd.read_csv(FIXTURES / f"{name}_7143733.csv")
    return pd.Series(df["value"].to_numpy(float), index=pd.to_datetime(df["date"]))


class TestConstants:
    def test_d1_d3_values(self):
        assert (growth.EMA_SPAN, growth.WINDOW_DAYS, growth.RECOVERY_PCT, growth.SUSTAIN_DAYS, growth.SPACING_DAYS) == (28, 180, 0.25, 14, 180)
        assert growth.FLOOR_STATE_PCT == 0.10 and growth.FLOOR_STATE_PCT != growth.RECOVERY_PCT
        assert growth.MIN_HISTORY_DAYS == 194


class TestEma:
    def test_gaps_not_zero_filled(self):
        s = growth.to_daily(pd.Series([100.0, 100.0, 100.0], index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-10"])))
        assert s.isna().sum() == 7  # missing days stay NaN
        e = growth.ema(s, 7)
        assert e.min() == pytest.approx(100.0)  # a zero-fill would drag it down

    def test_leading_nan_stays_nan(self):
        s = _daily([np.nan, np.nan, 5.0, 5.0])
        assert growth.ema(s, 7).iloc[:2].isna().all()


class TestFloorRamp:
    def test_v_shape_one_event(self):
        r = growth.detect_floor_ramp(_v_shape())
        assert len(r.events) == 1
        ev = r.events[0]
        low_start, low_end = date(2020, 1, 1) + pd.Timedelta(days=370), date(2020, 1, 1) + pd.Timedelta(days=430)
        assert low_start <= ev.floor_date <= low_end + pd.Timedelta(days=30)
        assert ev.ramp_date > ev.floor_date
        assert r.state in ("ramping", "neutral")

    def test_flat_series_no_events(self):
        r = growth.detect_floor_ramp(_daily(np.full(400, 50.0)))
        assert r.events == [] and r.state == "floor"

    def test_small_dip_below_recovery_is_not_a_ramp(self):
        vals = np.concatenate([np.full(250, 1000.0), np.linspace(1000, 900, 50), np.linspace(900, 1000, 50), np.full(100, 1000.0)])
        assert growth.detect_floor_ramp(_daily(vals)).events == []

    def test_close_floors_merge_keep_lower(self):
        # two V's 100 days apart (< SPACING_DAYS) -> one event at the lower floor
        v1 = np.concatenate([np.linspace(1000, 400, 60), np.full(20, 400.0), np.linspace(400, 1000, 30)])
        v2 = np.concatenate([np.linspace(1000, 300, 30), np.full(20, 300.0), np.linspace(300, 1000, 40), np.full(60, 1000.0)])
        vals = np.concatenate([np.full(250, 1000.0), v1, v2])
        r = growth.detect_floor_ramp(_daily(vals))
        assert len(r.events) == 1
        assert r.events[0].floor_date >= date(2020, 1, 1) + pd.Timedelta(days=250 + 110)

    def test_declining_state(self):
        # +20% (below R, so no ramp) then fading: >10% off the low, EMA7 < EMA28
        vals = np.concatenate([np.full(250, 100.0), np.linspace(100, 120, 100), np.linspace(120, 112, 20)])
        assert growth.detect_floor_ramp(_daily(vals)).state == "declining"

    def test_ramp_then_fade_is_neutral(self):
        vals = np.concatenate([np.full(250, 100.0), np.linspace(100, 200, 100), np.linspace(200, 170, 20)])
        r = growth.detect_floor_ramp(_daily(vals))
        assert len(r.events) == 1 and r.state == "neutral"


class TestGate:
    def test_below_gate(self):
        s = _daily(np.full(193, 10.0), start="2026-07-01")
        r = growth.detect_floor_ramp(s)
        assert r.state == "not-enough-history" and r.events == []
        assert r.history_days == 193
        assert r.gate_met_on == date(2027, 1, 10)

    def test_at_gate(self):
        r = growth.detect_floor_ramp(_daily(np.full(194, 10.0)))
        assert r.state != "not-enough-history"

    def test_gate_counts_only_post_launch(self):
        s = _daily(np.full(300, 10.0), start="2026-01-01")
        post = growth.post_launch(s, "2026-07-01")
        assert post.index[0] == pd.Timestamp("2026-07-01")
        assert growth.detect_floor_ramp(post).state == "not-enough-history"
        assert growth.detect_floor_ramp(s).state != "not-enough-history"

    def test_pre_launch_ramp_from_zero_excluded(self):
        # testnet noise (~1) then launch at 1000: without trimming this is a fake floor->ramp
        vals = np.concatenate([np.full(60, 1.0), np.full(400, 1000.0)])
        s = _daily(vals)
        assert growth.detect_floor_ramp(growth.post_launch(s, "2020-03-01")).events == []

    def test_empty(self):
        r = growth.detect_floor_ramp(pd.Series(dtype=float))
        assert r.state == "not-enough-history" and r.gate_met_on is None


class TestStale:
    NOW = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)

    def test_fresh(self):
        assert not is_stale("2026-09-26T11:00:00Z", self.NOW)

    def test_boundary(self):
        assert STALE_AFTER_DAYS == 3
        assert not is_stale("2026-09-23T12:00:00Z", self.NOW)
        assert is_stale("2026-09-23T11:59:59Z", self.NOW)

    def test_missing_is_stale(self):
        assert is_stale(None, self.NOW)


class TestRealDataRegression:
    """D1 headline dates on data frozen from commit 7143733."""

    def _events(self, name, launch):
        r = growth.detect_floor_ramp(growth.post_launch(growth.to_daily(_fixture(name)), launch))
        return [(e.floor_date.isoformat(), e.ramp_date.isoformat()) for e in r.events]

    def test_ethereum_daa(self):
        assert self._events("ethereum_active_addresses", "2015-07-30") == [
            ("2022-06-30", "2022-08-08"), ("2023-07-29", "2024-03-15"), ("2024-09-26", "2024-12-19")]

    def test_arbitrum_tx(self):
        assert self._events("arbitrum_transactions", "2021-08-31") == [
            ("2023-09-17", "2023-11-27"), ("2026-05-31", "2026-07-09")]

    def test_base_daa(self):
        assert self._events("base_active_addresses", "2023-08-09") == [("2025-04-23", "2025-05-24")]

    def test_base_pre_launch_would_distort(self):
        # pre-launch rows exist in the real data (starts 2023-06-15, launch 2023-08-09)
        assert _fixture("base_active_addresses").index[0] < pd.Timestamp("2023-08-09")
