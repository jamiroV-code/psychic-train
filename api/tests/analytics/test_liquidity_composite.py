"""Tests for the macro-liquidity composite variant selector (Implementation
Checklist item 36: `test_leg_boundary_composite_variant_selection_by_date`)
plus the reduced-composite builder's "never zero-fill a missing component"
discipline.
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.analytics.regime import liquidity_composite


def _liqtide_row(date: str, **overrides) -> dict:
    row = {"date": date, "generated_utc": f"{date}T22:45:00Z", "tide_score": 55.0,
           "net_liquidity": 1.0, "dollar": 2.0, "stables": 3.0, "btc_dom": 4.0}
    row.update(overrides)
    return row


class _Empty:
    df = pd.DataFrame(columns=["date", "value"])
    status = "unavailable"


def _series_stub(n: int = 40):
    """A smooth 40-point daily series — long enough to clear the slowest
    component's ROC window (30d) plus ZSCORE_MIN_PERIODS."""
    import numpy as np

    dates = pd.date_range("2020-01-01", periods=n, freq="D", tz="utc")
    df = pd.DataFrame({"date": dates, "value": 100.0 + np.arange(n) * 0.5})

    class _Ok:
        status = "ok"

    _Ok.df = df
    return _Ok


def _patch_inputs(monkeypatch, present: tuple[str, ...]):
    """Patch the four reduced-composite inputs so exactly `present` have data
    and the rest are hard-unavailable. Keeps each coverage test's setup down
    to the one thing it is actually about: which components exist."""
    net_liq = _series_stub() if "net_liquidity" in present else _Empty
    dollar = _series_stub() if "dollar" in present else _Empty
    stables = _series_stub() if "stables" in present else _Empty

    if "btc_dom" in present:
        history = _series_stub().df.rename(columns={"value": "btc_dom"})
    else:
        history = pd.DataFrame()

    monkeypatch.setattr(liquidity_composite.fred_adapter, "fetch_net_liquidity", lambda: net_liq())
    monkeypatch.setattr(liquidity_composite.fred_adapter, "fetch_series", lambda *a, **k: dollar())
    monkeypatch.setattr(liquidity_composite.defillama_adapter, "fetch_stablecoin_supply", lambda: stables())
    monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: history)


class TestSelectCompositeVariant:
    def test_pre_cutover_date_is_always_reduced(self, monkeypatch):
        monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: pd.DataFrame([_liqtide_row("2017-06-01")]))
        assert liquidity_composite.select_composite_variant(pd.Timestamp("2017-06-01", tz="utc")) == "reduced"

    def test_post_cutover_with_all_inputs_available_is_full(self, monkeypatch):
        history = pd.DataFrame([_liqtide_row("2024-06-01")])
        monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: history)
        assert liquidity_composite.select_composite_variant(pd.Timestamp("2024-06-01", tz="utc")) == "full"

    def test_post_cutover_but_one_input_missing_falls_back_to_reduced(self, monkeypatch):
        history = pd.DataFrame([_liqtide_row("2024-06-01", btc_dom=None)])
        monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: history)
        assert liquidity_composite.select_composite_variant(pd.Timestamp("2024-06-01", tz="utc")) == "reduced"

    def test_exact_cutover_date_with_data_is_full(self, monkeypatch):
        history = pd.DataFrame([_liqtide_row("2024-01-11")])
        monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: history)
        assert liquidity_composite.select_composite_variant(liquidity_composite.CUTOVER_DATE) == "full"

    def test_day_before_cutover_is_reduced_even_with_full_data_cached(self, monkeypatch):
        history = pd.DataFrame([_liqtide_row("2024-01-10")])
        monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: history)
        assert liquidity_composite.select_composite_variant(pd.Timestamp("2024-01-10", tz="utc")) == "reduced"

    def test_no_cached_history_at_all_is_reduced(self, monkeypatch):
        monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: pd.DataFrame())
        assert liquidity_composite.select_composite_variant(pd.Timestamp("2025-01-01", tz="utc")) == "reduced"


class TestBuildFullComposite:
    def test_no_archived_history_is_unavailable(self, monkeypatch):
        monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: pd.DataFrame())
        result = liquidity_composite.build_full_composite()
        assert result.available is False
        assert result.series.empty

    def test_pre_cutover_rows_excluded_even_if_archived(self, monkeypatch):
        history = pd.DataFrame([_liqtide_row(d) for d in ["2023-12-01", "2024-06-01", "2024-06-02", "2024-06-03",
                                                             "2024-06-04", "2024-06-05", "2024-06-06"]])
        monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: history)
        result = liquidity_composite.build_full_composite()
        assert (pd.to_datetime(result.series["date"]) >= liquidity_composite.CUTOVER_DATE).all()


class TestBuildReducedComposite:
    def test_missing_component_never_zero_fills_others(self, monkeypatch):
        """A component with no data at all is simply excluded from the
        average, never contributes a fabricated zero (this project's
        general 'unavailable, never neutral' discipline).

        Setup clears the availability floor deliberately: net_liquidity +
        stables = 55/80 = 68.75% >= AVAILABILITY_WEIGHT_THRESHOLD, with
        dollar and btc_dom absent — so the surviving dates prove the
        no-zero-fill discipline rather than the coverage filter.
        """
        _patch_inputs(monkeypatch, present=("net_liquidity", "stables"))

        result = liquidity_composite.build_reduced_composite()
        assert result.available is True
        assert not result.series["composite"].isna().any()
        # absent components contribute nothing at all — not a zero weight
        assert result.series["dollar_weight"].isna().all()
        assert result.series["btc_dom_weight"].isna().all()
        assert (result.series["components_present"] == "net_liquidity,stables").all()

    def test_below_weight_threshold_is_unavailable(self, monkeypatch):
        """1-of-4 components (net_liquidity alone, 30/80 = 37.5% coverage) is
        the exact shape the 2026-09-20 FRED incident produced while still
        reporting available=True. It must now be unavailable."""
        _patch_inputs(monkeypatch, present=("net_liquidity",))

        result = liquidity_composite.build_reduced_composite()
        assert result.available is False
        assert result.series.empty

    def test_two_components_below_threshold_is_also_unavailable(self, monkeypatch):
        """net_liquidity + btc_dom = 40/80 = 50% — more than one component,
        still under the floor."""
        _patch_inputs(monkeypatch, present=("net_liquidity", "btc_dom"))

        result = liquidity_composite.build_reduced_composite()
        assert result.available is False

    def test_component_reporting_columns_and_renormalized_weights(self, monkeypatch):
        """net_liquidity + dollar = 45/80 = 56.25%... below the floor, so use
        net_liquidity + stables (55/80) and assert the renormalization:
        30/55 and 25/55."""
        _patch_inputs(monkeypatch, present=("net_liquidity", "stables"))

        result = liquidity_composite.build_reduced_composite()
        assert result.available is True
        assert (result.series["n_components"] == 2).all()
        assert (result.series["components_present"] == "net_liquidity,stables").all()
        assert result.series["net_liquidity_weight"].iloc[0] == pytest.approx(30.0 / 55.0)
        assert result.series["stables_weight"].iloc[0] == pytest.approx(25.0 / 55.0)
        weight_cols = ["net_liquidity_weight", "dollar_weight", "stables_weight", "btc_dom_weight"]
        assert result.series[weight_cols].sum(axis=1).iloc[0] == pytest.approx(1.0)

    def test_no_inputs_available_is_unavailable_not_raise(self, monkeypatch):
        class _Empty:
            df = pd.DataFrame(columns=["date", "value"])
            status = "unavailable"

        monkeypatch.setattr(liquidity_composite.fred_adapter, "fetch_net_liquidity", lambda: _Empty())
        monkeypatch.setattr(liquidity_composite.fred_adapter, "fetch_series", lambda *a, **k: _Empty())
        monkeypatch.setattr(liquidity_composite.defillama_adapter, "fetch_stablecoin_supply", lambda: _Empty())
        monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: pd.DataFrame())

        result = liquidity_composite.build_reduced_composite()
        assert result.available is False
