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
        general 'unavailable, never neutral' discipline)."""
        import numpy as np

        dates = pd.date_range("2020-01-01", periods=40, freq="D", tz="utc")
        net_liq_df = pd.DataFrame({"date": dates, "value": 100.0 + np.arange(40) * 0.5})

        class _NetLiq:
            df = net_liq_df
            status = "ok"

        class _Empty:
            df = pd.DataFrame(columns=["date", "value"])
            status = "unavailable"

        monkeypatch.setattr(liquidity_composite.fred_adapter, "fetch_net_liquidity", lambda: _NetLiq())
        monkeypatch.setattr(liquidity_composite.fred_adapter, "fetch_series", lambda *a, **k: _Empty())
        monkeypatch.setattr(liquidity_composite.defillama_adapter, "fetch_stablecoin_supply", lambda: _Empty())
        monkeypatch.setattr(liquidity_composite.cache, "read_liqtide_history", lambda: pd.DataFrame())

        result = liquidity_composite.build_reduced_composite()
        assert result.available is True
        assert not result.series["composite"].isna().any()

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
