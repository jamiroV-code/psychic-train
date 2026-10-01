"""AC3, AC4, AC11 automated halves (gate G3).

* Empty cache (a fresh copy on a new machine): every screen's primary
  endpoint answers 200 with an honest empty/unavailable state, never a 500.
* Aged cache (the PC was off for a while): endpoints still answer 200 with no
  NaN, and every affected series carries its explicit staleness marker.
* `SCREENER_WATCHLIST_PATH` / `SCREENER_CACHE_ROOT` are honored at import, and
  a watchlist write round-trips to the configured path.

Isolation (Validate Contract P2/E1/E2): every endpoint test requests
`offline_providers` (no provider is ever called) plus `isolated_cache` and
`temp_watchlist` built BEFORE the client. The reload tests do NOT use
`isolated_cache` (its undo would restore a stale attribute after a reload);
they restore the recorded originals themselves.
"""
from __future__ import annotations

import importlib
import json
import math

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.data import cache, fred_adapter
from api.data import watchlist as watchlist_store
from api.main import app
from api.tests.pairs_fixtures import ohlcv_frame

SCREEN_ENDPOINTS = {
    "screener": "/api/screener/board",
    "pairs": "/api/pairs",
    "regime": "/api/regime/components",
    "narrative": "/api/narrative/history",
}


@pytest.fixture
def client(offline_providers, isolated_cache, temp_watchlist):
    return TestClient(app)


def _walk_floats(obj):
    if isinstance(obj, float):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_floats(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_floats(v)


# ------------------------------------------------------------ empty cache


@pytest.mark.parametrize("screen", sorted(SCREEN_ENDPOINTS))
def test_empty_cache_all_screen_endpoints_never_500(client, screen):
    resp = client.get(SCREEN_ENDPOINTS[screen])
    assert resp.status_code == 200, resp.text[:500]
    assert isinstance(resp.json(), dict)


def test_empty_cache_pairs_reports_results_unavailable(client):
    body = client.get("/api/pairs").json()
    assert body["computation_status"] == "results_unavailable"


def test_empty_cache_regime_components_reports_no_points(client):
    body = client.get("/api/regime/components").json()
    assert body["grid_dates"] == []
    for component in body["components"]:
        assert component["points"] == []
        assert component["status"] != "ok"


# ------------------------------------------------------------- aged cache


AGED_END = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=30)


def _seed_aged_cache():
    closes = np.exp(np.linspace(3.0, 3.5, 200))
    cache.write_ohlcv("BTC", "1d", ohlcv_frame(closes, end=AGED_END))
    weekly = ohlcv_frame(closes[:60], end=AGED_END)
    weekly["timestamp"] = pd.date_range(end=AGED_END, periods=60, freq="W-MON", tz="UTC")
    cache.write_ohlcv("BTC", "1w", weekly)
    dates = pd.date_range(end=AGED_END.tz_localize(None), periods=400, freq="D")
    cache.write_liquidity_series(
        fred_adapter.BROAD_DOLLAR,
        pd.DataFrame({"date": dates, "value": np.linspace(120.0, 125.0, len(dates))}),
    )
    watchlist_store.add_coin("BTC")


@pytest.mark.parametrize(
    "check",
    [
        "never_500_and_no_nan",
        pytest.param(
            "screener_chart_carries_staleness_marker",
            marks=pytest.mark.xfail(
                strict=True,
                reason=(
                    "FINDING (plan step 5 / R9): an aged OHLCV cache is served on /api/screener/board "
                    "as chart.available=true with no staleness marker — ChartSeries has no as_of/stale "
                    "field and `reason` is only set when available=false. Requirement handed to the "
                    "screener's owning lane; not fixed here (router/model out of lane)."
                ),
            ),
        ),
    ],
)
def test_aged_cache_regime_and_screener_never_500_and_no_nan(client, check):
    _seed_aged_cache()

    board = client.get("/api/screener/board", params={"timeframe": "1d"})
    regime = client.get("/api/regime/components")

    if check == "never_500_and_no_nan":
        assert board.status_code == 200, board.text[:500]
        assert regime.status_code == 200, regime.text[:500]
        for body in (board.json(), regime.json()):
            assert not any(math.isnan(x) or math.isinf(x) for x in _walk_floats(body))

        # Regime: the aged series is served, and says so explicitly.
        dollar = next(c for c in regime.json()["components"] if c["id"] == "broad_dollar")
        assert dollar["points"], "aged cache should still be served"
        assert dollar["status"] == "stale"
        assert dollar["reason"]
        assert dollar["last_date"] is not None
        assert not all(p["value"] == 0 for p in dollar["points"]), "no zero stand-ins"

        # Screener: the aged bars are real bars, not zero stand-ins.
        coin = board.json()["coins"][0]
        assert coin["symbol"] == "BTC"
        closes = [bar["close"] for bar in coin["chart"]["price"]]
        assert closes and all(v > 0 for v in closes)
    else:
        coin = board.json()["coins"][0]
        chart = coin["chart"]
        assert chart["available"] is False or chart.get("reason") is not None or "as_of" in chart, (
            "an aged cache is displayed with no staleness marker"
        )


# --------------------------------------------------------- env overrides


def test_watchlist_env_override_is_honored_at_import(tmp_path, monkeypatch):
    from api.tests.deploy.conftest import ORIGINAL_WATCHLIST_PATH

    target = tmp_path / "operator_watchlist.json"
    monkeypatch.setenv("SCREENER_WATCHLIST_PATH", str(target))
    try:
        reloaded = importlib.reload(watchlist_store)
        assert reloaded.DEFAULT_WATCHLIST_PATH == target
    finally:
        monkeypatch.delenv("SCREENER_WATCHLIST_PATH", raising=False)
        importlib.reload(watchlist_store)
        watchlist_store.DEFAULT_WATCHLIST_PATH = ORIGINAL_WATCHLIST_PATH
    assert watchlist_store.DEFAULT_WATCHLIST_PATH == ORIGINAL_WATCHLIST_PATH


def test_watchlist_add_round_trips_to_env_path(offline_providers, temp_watchlist):
    client = TestClient(app)
    resp = client.post("/api/watchlist", json={"symbol": "zztest"})
    assert resp.status_code == 200
    assert "ZZTEST" in resp.json()["coins"]
    on_disk = json.loads(temp_watchlist.read_text())
    assert "ZZTEST" in json.dumps(on_disk)
    # A fresh read through the store (what a restarted API does) sees it too.
    assert "ZZTEST" in watchlist_store.read_watchlist()


def test_cache_root_env_override_is_honored_at_import(tmp_path, monkeypatch):
    from api.tests.deploy.conftest import ORIGINAL_CACHE_ROOT

    target = tmp_path / "operator_cache"
    monkeypatch.setenv("SCREENER_CACHE_ROOT", str(target))
    try:
        reloaded = importlib.reload(cache)
        assert reloaded.CACHE_ROOT == target
        assert reloaded.liquidity_series_path("X").is_relative_to(target)
    finally:
        monkeypatch.delenv("SCREENER_CACHE_ROOT", raising=False)
        importlib.reload(cache)
        cache.CACHE_ROOT = ORIGINAL_CACHE_ROOT
    assert cache.CACHE_ROOT == ORIGINAL_CACHE_ROOT
