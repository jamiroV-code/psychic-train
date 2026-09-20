"""Tests for Fork A leg-boundary candidate detection + price-structure
confirmation (Implementation Checklist item 39).

Covers: synthetic planted-shift composite (candidate-detection correctness);
synthetic BTC price with/without a matching structure shift
(confirm/no-confirm branches); unconfirmed candidates still appear in
`candidate_boundaries` (ADR-3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from api.analytics.regime import leg_boundary


def _synthetic_composite(n_days: int = 200, shift_at: int | None = 100, shift_size: float = 3.0) -> pd.DataFrame:
    """A flat, noiseless composite series, with an optional sharp, sustained
    level shift planted at `shift_at` — should trigger a candidate boundary
    there. `shift_at=None` produces a perfectly flat series (no shift ever).
    """
    dates = pd.date_range("2023-01-01", periods=n_days, freq="D", tz="utc")
    base = np.full(n_days, 100.0)
    if shift_at is not None:
        base[shift_at:] += shift_size
    return pd.DataFrame({"date": dates, "composite": base})


def _mean_zero_composite(
    n_days: int = 200,
    shift_at: int | None = 100,
    shift_size: float = 0.5,
    oscillation: float = 0.0,
) -> pd.DataFrame:
    """A composite centered on 0.0 — the realistic shape, since the composite
    is itself a blended z-score (live 2024-2026 data ranged ~-0.8..+0.65).
    Optional `oscillation` makes it repeatedly cross zero; `shift_at` plants a
    real sustained level shift of `shift_size` on top.
    """
    dates = pd.date_range("2023-01-01", periods=n_days, freq="D", tz="utc")
    base = np.zeros(n_days)
    if oscillation:
        base += oscillation * np.sign(np.sin(np.arange(n_days) * np.pi / 10.0))
    if shift_at is not None:
        base[shift_at:] += shift_size
    return pd.DataFrame({"date": dates, "composite": base})


def _synthetic_btc_price(n_bars: int = 200, structure_shift_at: int | None = None) -> pd.DataFrame:
    """Flat BTC price series, with an optional clean higher-high/higher-low
    structure shift starting at `structure_shift_at`. `structure_shift_at
    =None` produces a flat series with no structure shift anywhere.
    """
    dates = pd.date_range("2023-01-01", periods=n_bars, freq="D", tz="utc")
    close = np.full(n_bars, 100.0)
    if structure_shift_at is not None:
        # start strictly above the flat baseline (not tied at 100.0) so the
        # very first bar of the "after" window already clears the prior
        # swing low/high, not just later bars in the run.
        close[structure_shift_at:] = 100.0 + (np.arange(n_bars - structure_shift_at) + 1) * 0.8
    high = close + 0.5
    low = close - 0.5
    return pd.DataFrame({"timestamp": dates, "open": close, "high": high, "low": low, "close": close, "volume": 1.0})


class TestDetectCandidateBoundaries:
    def test_planted_shift_is_detected_near_its_date(self):
        composite = _synthetic_composite(shift_at=100, shift_size=4.0)
        candidates = leg_boundary.detect_candidate_boundaries(composite)
        assert len(candidates) >= 1
        shift_date = composite.iloc[100]["date"]
        closest = min(candidates, key=lambda c: abs((c.date - shift_date).days))
        # ROC_WINDOW_DAYS + SUSTAINED_DAYS lag before the rule can flag it
        assert abs((closest.date - shift_date).days) <= leg_boundary.ROC_WINDOW_DAYS + leg_boundary.SUSTAINED_DAYS + 2
        assert abs(closest.z_score) >= leg_boundary.ZSCORE_THRESHOLD

    def test_flat_series_produces_no_candidates(self):
        composite = _synthetic_composite(shift_at=None)  # no shift ever applied
        candidates = leg_boundary.detect_candidate_boundaries(composite)
        assert candidates == []

    def test_too_short_series_returns_empty_not_raise(self):
        composite = _synthetic_composite(n_days=5)
        assert leg_boundary.detect_candidate_boundaries(composite) == []

    def test_planted_shift_near_zero_baseline_is_detected(self):
        """Regression test for the 2026-09-20 mean-zero ROC fix: the composite
        is itself a z-score centered on 0, so the old `pct_change` formula
        divided by ~0 here and produced infinite/wildly unstable values. With
        an absolute `diff`, a real planted shift on a zero baseline is detected
        normally.
        """
        composite = _mean_zero_composite(shift_at=100, shift_size=0.5)
        candidates = leg_boundary.detect_candidate_boundaries(composite)
        assert len(candidates) >= 1
        shift_date = composite.iloc[100]["date"]
        closest = min(candidates, key=lambda c: abs((c.date - shift_date).days))
        assert abs((closest.date - shift_date).days) <= leg_boundary.ROC_WINDOW_DAYS + leg_boundary.SUSTAINED_DAYS + 2
        assert abs(closest.z_score) >= leg_boundary.ZSCORE_THRESHOLD

    def test_zero_crossing_series_shift_not_swamped_by_spurious_variance(self):
        """The old failure mode: a composite that legitimately crosses zero
        produced huge spurious divide-by-near-zero spikes that inflated the
        expanding baseline's variance and buried the real shift. A real
        sustained shift on an oscillating, zero-crossing series must still be
        detected.
        """
        composite = _mean_zero_composite(shift_at=100, shift_size=1.0, oscillation=0.5)
        candidates = leg_boundary.detect_candidate_boundaries(composite)
        assert len(candidates) >= 1
        shift_date = composite.iloc[100]["date"]
        closest = min(candidates, key=lambda c: abs((c.date - shift_date).days))
        assert abs((closest.date - shift_date).days) <= leg_boundary.ROC_WINDOW_DAYS + leg_boundary.SUSTAINED_DAYS + 2

    def test_brief_sustained_shift_detected_at_lowered_threshold(self):
        """Regression test for the 2026-09-20 `SUSTAINED_DAYS` 5 -> 2 finding:
        a real-but-brief move that sustains only ~2-3 days then reverts is
        exactly what a 5-day requirement silently dropped (the whole
        H2-2020..2021 stretch of the known-cycle gate went dark that way).
        At `SUSTAINED_DAYS=2` such a spike must be flagged.
        """
        composite = _mean_zero_composite(shift_at=None)
        # a brief excursion: 3 days above baseline, then back to 0.
        composite.loc[100:102, "composite"] = 0.6

        candidates = leg_boundary.detect_candidate_boundaries(composite)
        assert len(candidates) >= 1
        shift_date = composite.iloc[100]["date"]
        closest = min(candidates, key=lambda c: abs((c.date - shift_date).days))
        assert abs((closest.date - shift_date).days) <= leg_boundary.ROC_WINDOW_DAYS + leg_boundary.SUSTAINED_DAYS + 2
        assert abs(closest.z_score) >= leg_boundary.ZSCORE_THRESHOLD

    def test_empty_series_returns_empty(self):
        assert leg_boundary.detect_candidate_boundaries(pd.DataFrame(columns=["date", "composite"])) == []


def _candidate_index(candidate_date: pd.Timestamp, base: str = "2023-01-01") -> int:
    return int((candidate_date - pd.Timestamp(base, tz="utc")).days)


class TestConfirmBoundaries:
    def test_candidate_confirmed_when_structure_shifts(self):
        composite = _synthetic_composite(shift_at=100, shift_size=4.0)
        candidates = leg_boundary.detect_candidate_boundaries(composite)
        assert candidates  # sanity: fixture actually produced a candidate

        # Plant BTC's structure shift starting exactly at the candidate's
        # own detected date — the confirmation window centers there.
        shift_idx = _candidate_index(candidates[0].date)
        btc_df = _synthetic_btc_price(structure_shift_at=shift_idx)
        confirmations = leg_boundary.confirm_boundaries(candidates, btc_df)
        assert any(c.confirmed for c in confirmations)
        confirmed = next(c for c in confirmations if c.confirmed)
        assert confirmed.confirmed_date is not None

    def test_candidate_not_confirmed_without_structure_shift(self):
        composite = _synthetic_composite(shift_at=100, shift_size=4.0)
        candidates = leg_boundary.detect_candidate_boundaries(composite)
        assert candidates

        btc_df = _synthetic_btc_price(structure_shift_at=None)  # flat, no shift anywhere
        confirmations = leg_boundary.confirm_boundaries(candidates, btc_df)
        assert all(not c.confirmed for c in confirmations)
        assert all(c.confirmed_date is None for c in confirmations)

    def test_unconfirmed_candidates_never_dropped(self):
        """ADR-3: candidates always come back, confirmed or not — the
        caller decides visibility, this function never silently drops one.
        """
        composite = _synthetic_composite(shift_at=100, shift_size=4.0)
        candidates = leg_boundary.detect_candidate_boundaries(composite)
        btc_df = _synthetic_btc_price(structure_shift_at=None)
        confirmations = leg_boundary.confirm_boundaries(candidates, btc_df)
        assert len(confirmations) == len(candidates)

    def test_empty_btc_df_never_raises_all_unconfirmed(self):
        composite = _synthetic_composite(shift_at=100, shift_size=4.0)
        candidates = leg_boundary.detect_candidate_boundaries(composite)
        confirmations = leg_boundary.confirm_boundaries(candidates, pd.DataFrame())
        assert len(confirmations) == len(candidates)
        assert all(not c.confirmed for c in confirmations)


class TestComputeCurrentLegState:
    def test_no_composite_data_returns_has_data_false(self, monkeypatch):
        from api.analytics.regime import liquidity_composite

        class _Empty:
            available = False
            series = pd.DataFrame(columns=["date", "composite"])

        monkeypatch.setattr(liquidity_composite, "select_composite_variant", lambda d: "reduced")
        monkeypatch.setattr(liquidity_composite, "build_reduced_composite", lambda *a, **k: _Empty())

        state = leg_boundary.compute_current_leg_state()
        assert state.has_data is False
        assert state.candidate_boundaries == []
        assert state.confirmed_boundaries == []

    def test_candidate_boundaries_always_superset_of_confirmed(self, monkeypatch):
        from api.analytics.regime import liquidity_composite

        composite = _synthetic_composite(shift_at=100, shift_size=4.0)
        expected_candidates = leg_boundary.detect_candidate_boundaries(composite)
        assert expected_candidates  # sanity

        class _Result:
            available = True
            series = composite
            variant = "reduced"

        monkeypatch.setattr(liquidity_composite, "select_composite_variant", lambda d: "reduced")
        monkeypatch.setattr(liquidity_composite, "build_reduced_composite", lambda *a, **k: _Result())

        # Plant BTC's structure shift at the first candidate's own date so
        # this fixture is guaranteed to produce at least one confirmation.
        shift_idx = _candidate_index(expected_candidates[0].date)

        class _FakeOhlcv:
            df = _synthetic_btc_price(structure_shift_at=shift_idx)

        monkeypatch.setattr(leg_boundary.ccxt_adapter, "fetch_ohlcv", lambda *a, **k: _FakeOhlcv())

        state = leg_boundary.compute_current_leg_state()
        assert state.has_data is True
        confirmed_dates = {b.date for b in state.confirmed_boundaries}
        candidate_dates = {b.date for b in state.candidate_boundaries}
        assert confirmed_dates.issubset(candidate_dates)
        assert len(state.confirmed_boundaries) >= 1  # Stage 1 fixture is designed to confirm
