"""GET /api/regime/components tests (regime dashboard RFC-004, AC-7, plan §11).

Goes through `fastapi.testclient.TestClient` against the real app (fastapi
installed via `uv sync` in this session, so the `test_regime.py` sandbox
bypass is not needed here). No network: FRED/DefiLlama adapters are
monkeypatched with synthetic series, LiqTide is read from an `isolated_cache`
archive (VALIDATE E2), and `liqtide_adapter.fetch_latest` fails the test if
anything calls it (VALIDATE P1).
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.testclient import TestClient

from api.analytics.regime import components as comp
from api.analytics.regime import leg_boundary
from api.data import cache, defillama_adapter, etf_flows_adapter, fred_adapter, liqtide_adapter
from api.main import app
from api.models.regime import CurrentLegState, LegBoundaryResponse

DAYS = pd.date_range("2026-06-01", "2026-09-23", freq="D")
WEDS = DAYS[DAYS.dayofweek == 2]
URL = "/api/regime/components"


def _fred_frames() -> dict[str, pd.Series]:
    return {
        "WALCL": pd.Series(np.linspace(6.6e6, 6.7e6, len(WEDS)), index=WEDS),
        "WDTGAL": pd.Series(9e5, index=WEDS),
        "RRPONTSYD": pd.Series(np.linspace(5, 1, len(DAYS)), index=DAYS),
        "DTWEXBGS": pd.Series(np.linspace(118, 120, len(DAYS)), index=DAYS),
    }


def _patch_fred(monkeypatch, frames: dict[str, pd.Series]) -> None:
    def fetch_series(series_id, client=None):
        s = frames.get(series_id)
        if s is None:
            return fred_adapter.FredSeriesResult(series_id, pd.DataFrame(columns=["date", "value"]), "unavailable")
        return fred_adapter.FredSeriesResult(
            series_id, pd.DataFrame({"date": pd.to_datetime(s.index, utc=True), "value": s.values}), "ok")
    monkeypatch.setattr(fred_adapter, "fetch_series", fetch_series)


def _patch_defillama(monkeypatch, ok: bool = True) -> None:
    df = (pd.DataFrame({"date": pd.to_datetime(DAYS, utc=True), "value": np.linspace(3.0e11, 3.1e11, len(DAYS))})
          if ok else pd.DataFrame(columns=["date", "value"]))
    monkeypatch.setattr(defillama_adapter, "fetch_stablecoin_supply", lambda client=None:
                        defillama_adapter.StablecoinSupplyResult(df, "ok" if ok else "unavailable"))


def _write_liqtide_archive() -> None:
    """Two archived daily payload rows with a published tide value/label."""
    for d, v, label in [("2026-09-22", 48.0, "neutral"), ("2026-09-23", 44.0, "ebbing")]:
        cache.write_liqtide_payload(d, pd.DataFrame({"date": [d], "tide_value": [v], "tide_label": [label]}))


@pytest.fixture
def client(isolated_cache, monkeypatch):
    _patch_fred(monkeypatch, _fred_frames())
    _patch_defillama(monkeypatch)
    monkeypatch.setattr(comp, "_utc_today", lambda: pd.Timestamp("2026-09-24"))
    monkeypatch.setattr(liqtide_adapter, "fetch_latest",
                        lambda *a, **k: pytest.fail("live LiqTide call from /components"))
    # RFC-003: /components builds ETF flows from Farside; never hit the network.
    monkeypatch.setattr(etf_flows_adapter, "fetch_btc_spot_flows", lambda *a, **k: etf_flows_adapter.EtfFlowsResult(
        pd.DataFrame(columns=etf_flows_adapter.COLUMNS), "unavailable", "stubbed: no network in tests"))
    _write_liqtide_archive()
    return TestClient(app)


def _by_id(body: dict) -> dict:
    return {c["id"]: c for c in body["components"]}


class TestShape:
    def test_top_level_and_component_fields(self, client):
        resp = client.get(URL)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"generated_utc", "grid_dates", "components", "composite"}
        assert [c["id"] for c in body["components"]] == [s.id for s in comp.COMPONENTS]
        for c in body["components"]:
            assert {"id", "label", "weight", "source", "transform", "frequency", "status", "reason",
                    "first_date", "last_date", "last_fetched_utc", "points", "notes", "unit"} <= set(c)
            assert c["status"] in {"ok", "stale", "unavailable", "not_applicable", "no_data"}
        nl = _by_id(body)["net_liquidity"]
        assert nl["status"] == "ok" and nl["points"]
        assert nl["first_date"] == nl["points"][0]["date"] and nl["last_date"] == nl["points"][-1]["date"]
        assert body["grid_dates"] == sorted(body["grid_dates"])

    def test_composite_labels_and_published_rename(self, client):
        composite = client.get(URL).json()["composite"]
        rep, pub = composite["reproduced"], composite["published"]
        assert rep["label"] == "Reproduced tide index (this app)"
        assert rep["normalisation"] == "sign·tanh(impulse/scale); 50 + 50·Σw·x / Σw_present"
        assert rep["points"] and set(rep["points"][0]) == {"date", "value", "coverage"}
        assert pub["attribution"] == "Data: LiqTide (liqtide.com)"
        assert pub["status"] == "ok"
        assert pub["points"] == [
            {"date": "2026-09-22", "value": 48.0, "regime_label": "neutral"},
            {"date": "2026-09-23", "value": 44.0, "regime_label": "ebbing"},
        ]
        assert {"overlap_days", "pearson_r", "mean_abs_diff", "full_coverage_days",
                "full_coverage_mean_abs_diff"} <= set(composite["agreement"])

    def test_published_unavailable_when_archive_empty(self, isolated_cache, monkeypatch):
        _patch_fred(monkeypatch, _fred_frames())
        _patch_defillama(monkeypatch)
        body = TestClient(app).get(URL).json()
        pub = body["composite"]["published"]
        assert pub["status"] == "unavailable" and pub["points"] == []


class TestNoStandIns:
    def test_points_have_no_null_nan_or_inf(self, client):
        body = client.get(URL).json()
        lists = [c["points"] for c in body["components"]]
        lists += [body["composite"]["reproduced"]["points"], body["composite"]["published"]["points"]]
        for points in lists:
            for p in points:
                for k, v in p.items():
                    if k in ("date", "regime_label"):
                        continue
                    assert v is not None and isinstance(v, (int, float)) and math.isfinite(v), (k, p)

    def test_nan_rows_are_dropped_not_nulled(self, client, monkeypatch):
        real = comp.build_regime_components

        def with_nan():
            result = real()
            pts = result.components[0].points.copy()
            pts.loc[0, "raw"] = np.nan
            result.components[0].points = pts
            return result
        monkeypatch.setattr(comp, "build_regime_components", with_nan)
        full = comp.build_regime_components()  # via patched fn: first row has NaN raw
        body = client.get(URL).json()
        nl = _by_id(body)["net_liquidity"]
        assert len(nl["points"]) == len(full.components[0].points) - 1


class TestDateFilter:
    def test_start_end_filter_all_lists(self, client):
        body = client.get(URL, params={"start": "2026-09-01", "end": "2026-09-22"}).json()
        dates = [p["date"] for c in body["components"] for p in c["points"]]
        dates += [p["date"] for p in body["composite"]["reproduced"]["points"]]
        dates += [p["date"] for p in body["composite"]["published"]["points"]]
        dates += body["grid_dates"]
        assert dates and all("2026-09-01" <= d <= "2026-09-22" for d in dates)
        assert [p["date"] for p in body["composite"]["published"]["points"]] == ["2026-09-22"]

    def test_start_after_end_is_422(self, client):
        assert client.get(URL, params={"start": "2026-09-10", "end": "2026-09-01"}).status_code == 422

    def test_bad_date_is_422(self, client):
        assert client.get(URL, params={"start": "not-a-date"}).status_code == 422

    def test_window_with_no_points_is_no_data_not_ok(self, client):
        body = client.get(URL, params={"start": "2030-01-01"}).json()
        nl = _by_id(body)["net_liquidity"]
        assert nl["points"] == [] and nl["status"] == "no_data"


class TestDegradation:
    def test_one_adapter_down_only_that_component_unavailable(self, client, monkeypatch):
        frames = _fred_frames()
        del frames["DTWEXBGS"]
        _patch_fred(monkeypatch, frames)
        resp = client.get(URL)
        assert resp.status_code == 200
        by_id = _by_id(resp.json())
        assert by_id["broad_dollar"]["status"] == "unavailable" and by_id["broad_dollar"]["points"] == []
        assert by_id["broad_dollar"]["reason"]
        assert by_id["net_liquidity"]["status"] == "ok"
        assert by_id["stablecoin_supply"]["status"] == "ok"

    def test_defillama_down(self, client, monkeypatch):
        _patch_defillama(monkeypatch, ok=False)
        by_id = _by_id(client.get(URL).json())
        assert by_id["stablecoin_supply"]["status"] == "unavailable"
        assert by_id["net_liquidity"]["status"] == "ok"

    def test_never_calls_liqtide_fetch_latest(self, isolated_cache, monkeypatch):
        calls = []
        monkeypatch.setattr(liqtide_adapter, "fetch_latest", lambda *a, **k: calls.append(1))
        _patch_fred(monkeypatch, _fred_frames())
        _patch_defillama(monkeypatch)
        assert TestClient(app).get(URL).status_code == 200
        assert calls == []


class TestNotApplicable:
    def test_etf_not_applicable_when_range_ends_before_launch(self, client):
        etf = _by_id(client.get(URL, params={"end": "2023-12-31"}).json())["etf_flows"]
        assert etf["status"] == "not_applicable"
        assert "2024-01-11" in etf["reason"]
        assert etf["points"] == []

    def test_etf_without_data_is_unavailable_naming_farside(self, client):
        etf = _by_id(client.get(URL).json())["etf_flows"]
        assert etf["status"] == "unavailable"
        assert etf["reason"] == "no ETF flow history: Farside unavailable (stubbed: no network in tests)"
        assert any("Not applicable before 2024-01-11" in n for n in etf["notes"])

    def test_other_components_unaffected_by_pre_launch_end(self, client):
        by_id = _by_id(client.get(URL, params={"end": "2023-12-31"}).json())
        assert by_id["net_liquidity"]["status"] != "not_applicable"


class TestLastFetched:
    def test_null_when_nothing_cached(self, client):
        assert _by_id(client.get(URL).json())["net_liquidity"]["last_fetched_utc"] is None

    def test_from_cache_mtime(self, client):
        cache.write_liquidity_series("WALCL", pd.DataFrame({"date": ["2026-09-16"], "value": [1.0]}))
        cache.write_liqtide_raw("2026-09-23", {"x": 1})
        by_id = _by_id(client.get(URL).json())
        assert by_id["net_liquidity"]["last_fetched_utc"].endswith("Z")
        assert by_id["rrp_release"]["last_fetched_utc"] is None  # RRPONTSYD not cached
        assert by_id["btc_dominance"]["last_fetched_utc"].endswith("Z")


class TestAppWiring:
    def test_legs_shape_unchanged(self, monkeypatch):
        state = CurrentLegState(candidate_boundaries=[], confirmed_boundaries=[],
                                composite_variant="reduced", has_data=False)
        monkeypatch.setattr(leg_boundary, "compute_current_leg_state", lambda: state)
        resp = TestClient(app).get("/api/regime/legs")
        assert resp.status_code == 200
        assert set(resp.json()) == set(LegBoundaryResponse.model_fields)

    def test_gzip_middleware_registered(self):
        assert any(m.cls is GZipMiddleware for m in app.user_middleware)

    def test_response_is_gzipped_when_requested(self, client):
        resp = client.get(URL, headers={"Accept-Encoding": "gzip"})
        assert resp.headers.get("content-encoding") == "gzip"
        assert json.loads(resp.content)["components"]  # httpx decodes transparently
