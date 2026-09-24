"""Regime dashboard RFC-002: component maths (AC-3, AC-4, AC-5).

Golden values are hand-computed; the `TestLiveGolden` class pins the six
published LiqTide components of the real 2026-09-24 payload (from its own
`signals` impulses), which is the evidence the tanh normalisation rests on.
No network: adapters are monkeypatched.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from api.analytics.regime import components as comp
from api.data import cache, defillama_adapter, etf_flows_adapter, fred_adapter, liqtide_adapter

S = comp.SPEC_BY_ID


def _series(pairs: dict[str, float]) -> pd.Series:
    s = pd.Series(pairs, dtype=float)
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


class TestLiveGolden:
    """2026-09-24T00:53:56Z payload: `signals` impulse -> published component."""

    CASES = [
        ("net_liquidity", -59_511_000_000.0, -0.3772),
        ("stablecoin_supply", 0.007124, 0.6122),
        ("broad_dollar", 0.009976, -0.4612),
        ("rrp_release", -241_000_000.0, 0.0032),
        ("etf_flows", 2_338_600_000.0, 0.9816),
        ("btc_dominance", -0.445111, 0.2190),
    ]

    @pytest.mark.parametrize("cid,impulse,published", CASES)
    def test_normalise_matches_published(self, cid, impulse, published):
        assert round(comp.normalise(impulse, S[cid]), 4) == pytest.approx(published, abs=1e-4)

    def test_composite_matches_published_value(self):
        published = {"net_liquidity": -0.3772, "stablecoin_supply": 0.6122, "broad_dollar": -0.4612,
                     "rrp_release": 0.0032, "etf_flows": 0.9816, "btc_dominance": 0.2190}
        score = sum(S[k].weight * v for k, v in published.items())
        assert round(score, 4) == pytest.approx(0.0911, abs=1e-4)
        assert round(50 + 50 * score) == 55

    def test_weights_sum_to_one(self):
        assert sum(s.weight for s in comp.COMPONENTS) == pytest.approx(1.0)


class TestAsofLookup:
    def test_calendar_not_rows_across_business_day_gap(self):
        # Business days only, with a holiday (2026-01-19 missing).
        s = _series({"2026-01-12": 1, "2026-01-13": 2, "2026-01-14": 3, "2026-01-15": 4,
                     "2026-01-16": 5, "2026-01-20": 6, "2026-01-21": 7})
        out = comp.asof_lookup(s, pd.DatetimeIndex(["2026-01-21"]), lag_days=7, max_lag_days=5)
        # 2026-01-21 - 7 days = 2026-01-14 -> 3 (a 7-ROW lookback would give 1 day earlier than exists)
        assert out.iloc[0] == 3

    def test_weekend_target_uses_previous_business_day(self):
        s = _series({"2026-01-16": 5, "2026-01-19": 6})
        out = comp.asof_lookup(s, pd.DatetimeIndex(["2026-01-25"]), lag_days=7, max_lag_days=5)
        assert out.iloc[0] == 5  # target Sunday 01-18 -> Friday 01-16

    def test_too_stale_is_nan_not_carried(self):
        s = _series({"2026-01-01": 1, "2026-03-01": 2})
        out = comp.asof_lookup(s, pd.DatetimeIndex(["2026-03-01"]), lag_days=28, max_lag_days=5)
        assert np.isnan(out.iloc[0])

    def test_before_first_observation_is_nan(self):
        s = _series({"2026-02-01": 1})
        out = comp.asof_lookup(s, pd.DatetimeIndex(["2026-02-05"]), lag_days=7, max_lag_days=5)
        assert np.isnan(out.iloc[0])


class TestChangeComponent:
    def test_absolute_change_golden(self):
        spec = S["rrp_release"]  # 28-day window, sign -1, scale 75bn
        level = _series({"2026-08-26": 0.702e9, "2026-09-23": 0.461e9})
        df = comp.change_component(spec, level, relative=False)
        assert len(df) == 1
        row = df.iloc[0]
        assert row["value"] == pytest.approx(-0.241e9)
        assert row["raw"] == pytest.approx(0.461e9)
        assert row["contribution"] == pytest.approx(-math.tanh(-0.241e9 / 75e9))

    def test_relative_change_golden(self):
        spec = S["broad_dollar"]  # 30-day window, relative, sign -1, scale 2%
        level = _series({"2026-08-19": 118.3328, "2026-09-18": 119.5133})
        df = comp.change_component(spec, level, relative=True)
        assert df.iloc[0]["value"] == pytest.approx(0.009976, abs=1e-6)
        assert round(df.iloc[0]["contribution"], 4) == -0.4612

    def test_no_output_without_prior_value(self):
        df = comp.change_component(S["broad_dollar"], _series({"2026-09-18": 119.5}), relative=True)
        assert df.empty

    def test_outputs_have_no_nan_or_inf(self):
        level = _series({f"2026-01-{d:02d}": float(d) for d in range(1, 31)})
        df = comp.change_component(S["stablecoin_supply"], level, relative=True)
        assert not df.empty
        assert np.isfinite(df[["value", "raw", "contribution"]].to_numpy()).all()


class TestRollingSum:
    def test_five_day_sum_golden(self):
        flows = _series({"2026-09-17": 159.5e6, "2026-09-18": 433.0e6, "2026-09-21": 999.0e6,
                         "2026-09-22": 714.7e6, "2026-09-23": 32.4e6})
        df = comp.rolling_sum_component(S["etf_flows"], flows)
        assert len(df) == 1
        assert df.iloc[0]["value"] == pytest.approx(2338.6e6)
        assert round(df.iloc[0]["contribution"], 4) == 0.9816

    def test_gap_in_record_does_not_widen_window(self):
        flows = _series({"2026-08-01": 1e8, "2026-09-18": 1e8, "2026-09-21": 1e8,
                         "2026-09-22": 1e8, "2026-09-23": 1e8})
        assert comp.rolling_sum_component(S["etf_flows"], flows).empty


def _fred(frames: dict[str, pd.Series], status: str = "ok"):
    def fetch_series(series_id, client=None):
        s = frames.get(series_id)
        if s is None:
            return fred_adapter.FredSeriesResult(series_id, pd.DataFrame(columns=["date", "value"]), "unavailable")
        df = pd.DataFrame({"date": pd.to_datetime(s.index, utc=True), "value": s.values})
        return fred_adapter.FredSeriesResult(series_id, df, status)
    return fetch_series


class TestNetLiquidity:
    def test_wednesday_grid_golden_and_weekly_only(self, monkeypatch):
        # Values in FRED units: WALCL/WDTGAL millions, RRP billions.
        walcl = _series({"2026-08-19": 6_745_699, "2026-09-16": 6_746_548})
        tga = _series({"2026-08-19": 936_406, "2026-09-16": 991_708})
        rrp = _series({"2026-08-19": 0.317, "2026-09-15": 0.7, "2026-09-16": 5.375, "2026-09-17": 1.0})
        monkeypatch.setattr(fred_adapter, "fetch_series",
                            _fred({"WALCL": walcl, "WDTGAL": tga, "RRPONTSYD": rrp}))
        c = comp.build_net_liquidity()
        assert c.status == "ok"
        # Only Wednesday points, and the first has no 4-week-earlier value.
        assert list(c.points["date"]) == [pd.Timestamp("2026-09-16")]
        row = c.points.iloc[0]
        assert row["raw"] == pytest.approx(5_749.465e9)
        assert row["value"] == pytest.approx(-59.511e9)
        assert round(row["contribution"], 4) == -0.3772

    def test_missing_input_unavailable(self, monkeypatch):
        monkeypatch.setattr(fred_adapter, "fetch_series", _fred({"WALCL": _series({"2026-09-16": 1.0})}))
        c = comp.build_net_liquidity()
        assert c.status == "unavailable"
        assert c.points.empty


def _history(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["series_key", "date", "value"])


class TestLiqTideSourced:
    def test_etf_before_launch_dropped(self):
        rows = [("etf_flows", f"2024-01-{d:02d}", 1e8) for d in (3, 4, 5, 8, 9, 10, 11, 12, 16, 17, 18)]
        c = comp.build_etf_flows(_history(rows))
        assert c.points["date"].min() >= comp.ETF_LAUNCH_DATE
        assert any("Not applicable before 2024-01-11" in n for n in c.notes)

    def test_etf_no_history_unavailable(self):
        c = comp.build_etf_flows(_history([]))
        assert c.status == "unavailable"

    def test_etf_no_history_reason_names_farside(self):
        farside = etf_flows_adapter.EtfFlowsResult(pd.DataFrame(columns=etf_flows_adapter.COLUMNS),
                                                   "unavailable", "request timed out")
        c = comp.build_etf_flows(_history([]), farside)
        assert c.status == "unavailable"
        assert "Farside unavailable" in c.reason and "timed out" in c.reason

    def test_btc_dominance_golden(self):
        c = comp.build_btc_dominance(_history([("btc_dom", "2026-08-25", 59.237158),
                                               ("btc_dom", "2026-09-24", 58.792047)]))
        assert c.status == "ok"
        row = c.points.iloc[0]
        assert row["value"] == pytest.approx(-0.445111, abs=1e-6)
        assert round(row["contribution"], 4) == 0.2190


def _component(cid: str, pairs: dict[str, float]) -> comp.ComponentSeries:
    df = pd.DataFrame({"date": pd.to_datetime(list(pairs)), "value": 0.0, "raw": 0.0,
                       "contribution": list(pairs.values())})
    return comp.ComponentSeries(S[cid], df, "ok")


class TestStablecoinPartialDay:
    def test_current_utc_day_excluded(self, monkeypatch):
        days = pd.date_range("2026-09-01", "2026-09-24", freq="D")
        df = pd.DataFrame({"date": pd.to_datetime(days, utc=True), "value": np.linspace(3.0e11, 3.1e11, len(days))})
        monkeypatch.setattr(defillama_adapter, "fetch_stablecoin_supply",
                            lambda client=None: defillama_adapter.StablecoinSupplyResult(df, "ok"))
        monkeypatch.setattr(comp, "_utc_today", lambda: pd.Timestamp("2026-09-24"))
        c = comp.build_stablecoin_supply()
        assert c.points["date"].max() == pd.Timestamp("2026-09-23")


class TestReproducedComposite:
    def test_full_coverage_matches_liqtide_formula(self):
        vals = {"net_liquidity": -0.3772, "stablecoin_supply": 0.6122, "broad_dollar": -0.4612,
                "rrp_release": 0.0032, "etf_flows": 0.9816, "btc_dominance": 0.2190}
        comps = [_component(k, {"2026-09-24": v}) for k, v in vals.items()]
        out = comp.build_reproduced(comps)
        assert len(out) == 1
        assert out.iloc[0]["coverage"] == pytest.approx(1.0)
        assert out.iloc[0]["value"] == pytest.approx(50 + 50 * sum(S[k].weight * v for k, v in vals.items()))
        assert round(out.iloc[0]["value"]) == 55

    def test_renormalises_over_present_weights(self):
        comps = [_component("net_liquidity", {"2026-09-24": 0.5}),
                 _component("stablecoin_supply", {"2026-09-24": -0.5}),
                 _component("broad_dollar", {"2026-09-24": 0.2})]
        out = comp.build_reproduced(comps)
        expected = (0.3 * 0.5 + 0.25 * -0.5 + 0.15 * 0.2) / 0.70
        assert out.iloc[0]["coverage"] == pytest.approx(0.70)
        assert out.iloc[0]["value"] == pytest.approx(50 + 50 * expected)
        assert out.iloc[0]["components_present"] == "net_liquidity,stablecoin_supply,broad_dollar"

    def test_below_sixty_percent_is_dropped(self):
        comps = [_component("net_liquidity", {"2026-09-24": 0.5}),
                 _component("stablecoin_supply", {"2026-09-24": 0.5})]  # 55%
        assert comp.build_reproduced(comps).empty

    def test_weekly_component_carried_as_of_within_tolerance_only(self):
        comps = [_component("net_liquidity", {"2026-09-16": 0.5}),
                 _component("stablecoin_supply", {"2026-09-20": 0.1, "2026-10-10": 0.1}),
                 _component("broad_dollar", {"2026-09-20": 0.1, "2026-10-10": 0.1})]
        out = comp.build_reproduced(comps).set_index("date")
        assert pd.Timestamp("2026-09-20") in out.index  # net liquidity 4 days old: used
        assert pd.Timestamp("2026-10-10") not in out.index  # 24 days old: not used -> 40% coverage


class TestPublishedAndAgreement:
    def test_published_merges_weekly_history_and_archive(self, isolated_cache):
        cache.write_liqtide_payload("2026-09-24", pd.DataFrame([{
            "date": "2026-09-24", "generated_utc": "x", "tide_score": 0.0911,
            "net_liquidity": 1.0, "dollar": 1.0, "stables": 1.0, "btc_dom": 1.0,
            "tide_value": 55.0, "tide_label": "SLACK WATER"}]))
        hist = _history([("tide_value", "2026-09-09", 68.0), ("tide_value", "2026-09-16", 32.0)])
        pub = comp.build_published(hist)
        assert list(pub["value"]) == [68.0, 32.0, 55.0]
        assert pub.iloc[-1]["label"] == "SLACK WATER"
        assert pub.iloc[0]["label"] is None  # never invented

    def test_agreement_numbers(self):
        rep = pd.DataFrame({"date": pd.to_datetime(["2026-09-02", "2026-09-09", "2026-09-16"]),
                            "value": [50.0, 60.0, 40.0], "coverage": [1.0, 1.0, 0.8]})
        pub = pd.DataFrame({"date": pd.to_datetime(["2026-09-02", "2026-09-09", "2026-09-16"]),
                            "value": [52.0, 58.0, 41.0], "label": None})
        a = comp.agreement_stats(rep, pub)
        assert a["overlap_days"] == 3
        assert a["mean_abs_diff"] == pytest.approx((2 + 2 + 1) / 3)
        assert a["full_coverage_days"] == 2
        assert a["pearson_r"] > 0.9


class TestOrchestrator:
    def test_end_to_end_no_network(self, isolated_cache, monkeypatch):
        days = pd.date_range("2026-06-01", "2026-09-24", freq="D")
        weds = days[days.dayofweek == 2]
        monkeypatch.setattr(fred_adapter, "fetch_series", _fred({
            "WALCL": pd.Series(6.7e6, index=weds), "WDTGAL": pd.Series(9e5, index=weds),
            "RRPONTSYD": pd.Series(np.linspace(5, 1, len(days)), index=days),
            "DTWEXBGS": pd.Series(np.linspace(118, 120, len(days)), index=days),
        }))
        monkeypatch.setattr(defillama_adapter, "fetch_stablecoin_supply", lambda client=None:
                            defillama_adapter.StablecoinSupplyResult(
                                pd.DataFrame({"date": pd.to_datetime(days, utc=True),
                                              "value": np.linspace(3.0e11, 3.1e11, len(days))}), "ok"))
        monkeypatch.setattr(liqtide_adapter, "fetch_latest", lambda *a, **k: pytest.fail("live LiqTide call"))
        monkeypatch.setattr(etf_flows_adapter, "fetch_btc_spot_flows", lambda *a, **k:
                            etf_flows_adapter.EtfFlowsResult(pd.DataFrame(columns=etf_flows_adapter.COLUMNS),
                                                             "unavailable", "test: no network"))
        result = comp.build_regime_components()
        ids = [c.spec.id for c in result.components]
        assert ids == [s.id for s in comp.COMPONENTS]
        by_id = {c.spec.id: c for c in result.components}
        assert by_id["net_liquidity"].status == "ok"
        assert by_id["etf_flows"].status == "unavailable"
        assert by_id["btc_dominance"].status in ("unavailable", "no_data")
        assert not result.reproduced.empty
        assert (result.reproduced["coverage"] >= 0.6).all()
        assert result.grid_dates == sorted(result.grid_dates)
        for c in result.components:
            assert np.isfinite(c.points[["value", "contribution"]].to_numpy(dtype=float)).all()


def _farside(pairs: dict[str, float], status: str = "ok", reason: str | None = None):
    df = pd.DataFrame({"date": pd.to_datetime(list(pairs)), "net_flow_usd_m": list(pairs.values())})
    return etf_flows_adapter.EtfFlowsResult(df, status, reason)


class TestEtfFarsideWiring:
    """RFC-003: Farside daily totals (US$m) feed the 5-day ETF impulse."""

    FLOWS_M = {"2026-09-17": 159.5, "2026-09-18": 433.0, "2026-09-21": 999.0,
               "2026-09-22": 714.7, "2026-09-23": 32.4}

    def test_farside_usd_m_converted_and_golden(self):
        c = comp.build_etf_flows(_history([]), _farside(self.FLOWS_M))
        assert c.status == "ok"
        last = c.points.iloc[-1]
        assert last["value"] == pytest.approx(2338.6e6)
        assert round(last["contribution"], 4) == 0.9816
        assert any("personal use only" in n for n in c.notes)

    def test_farside_preferred_liqtide_fills_missing_dates(self):
        flows = dict(self.FLOWS_M)
        del flows["2026-09-17"]
        history = _history([("etf_flows", "2026-09-17", 159.5e6), ("etf_flows", "2026-09-23", 9e9)])
        c = comp.build_etf_flows(history, _farside(flows))
        last = c.points.iloc[-1]
        assert last["date"] == pd.Timestamp("2026-09-23")
        assert last["value"] == pytest.approx(2338.6e6)  # Farside's 32.4m wins over LiqTide's 9bn

    def test_farside_pre_launch_rows_dropped(self):
        pairs = {f"2024-01-{d:02d}": 100.0 for d in (8, 9, 10, 11, 12, 16, 17, 18)}
        c = comp.build_etf_flows(_history([]), _farside(pairs))
        assert c.points["date"].min() >= comp.ETF_LAUNCH_DATE

    def test_farside_stale_propagates(self):
        c = comp.build_etf_flows(_history([]), _farside(self.FLOWS_M, "stale", "latest fetch failed"))
        assert c.status == "stale"
        assert c.reason == "latest fetch failed"

    def test_farside_unavailable_falls_back_to_liqtide_archive(self):
        rows = [("etf_flows", d, v * 1e6) for d, v in self.FLOWS_M.items()]
        farside = etf_flows_adapter.EtfFlowsResult(pd.DataFrame(columns=etf_flows_adapter.COLUMNS),
                                                   "unavailable", "blocked by source")
        c = comp.build_etf_flows(_history(rows), farside)
        assert c.status == "ok"
        assert c.points.iloc[-1]["value"] == pytest.approx(2338.6e6)
        assert any("LiqTide archive only" in n for n in c.notes)
