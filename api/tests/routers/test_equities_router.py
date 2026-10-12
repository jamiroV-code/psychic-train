"""S9A: `/api/equities` routes. Store, layout, watchlist and cache are
redirected to tmp; refresh is recorded or awaited; no real network or key."""
from __future__ import annotations

import json
import logging
import threading
from datetime import date

import pandas as pd
import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from api.data import equities_refresh, equities_store, lse_adapter  # noqa: E402
from api.data import watchlist as watchlist_store  # noqa: E402
from api.main import app  # noqa: E402
from api.tests import equities_fixtures as fx  # noqa: E402

MESSAGE = "Equities list is full: 30 tickers maximum. Remove a ticker to add another."
NOW = pd.Timestamp("2026-10-12T21:30:00Z")


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(tmp_path / "equities.json"))
    monkeypatch.setenv("SCREENER_LAYOUT_PATH", str(tmp_path / "layout.json"))
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    monkeypatch.setattr(lse_adapter, "_now", lambda: NOW)
    yield tmp_path
    assert equities_refresh.wait_until_idle(5.0)


@pytest.fixture
def refreshes(monkeypatch):
    calls = []
    lock = threading.Lock()

    def record(*args, **kwargs):
        with lock:
            calls.append(1)
        return {"accepted": True, "already_running": False}

    monkeypatch.setattr(equities_refresh, "request_refresh_now", record)
    return calls


@pytest.fixture
def client():
    return fastapi_testclient.TestClient(app)


def _add(client, symbol, **extra):
    return client.post("/api/equities", json={"symbol": symbol, **extra})


def test_get_empty_list(client):
    resp = client.get("/api/equities")
    assert resp.status_code == 200 and resp.json() == {"tickers": []}


def test_add_normalizes_and_lists(client, refreshes):
    assert _add(client, " aapl ").json() == {"tickers": ["AAPL"]}
    assert _add(client, "brk.b").json() == {"tickers": ["AAPL", "BRK.B"]}
    assert client.get("/api/equities").json() == {"tickers": ["AAPL", "BRK.B"]}


def test_add_invalid_is_422(client, refreshes):
    for bad in ("1ABC", "AA PL", "$SPY", ""):
        assert _add(client, bad).status_code == 422
    assert refreshes == [] and equities_store.load_tickers() == []


def test_thirty_first_is_409_with_exact_message(client, refreshes):
    for i in range(30):
        assert _add(client, f"T{i:02d}").status_code == 200
    resp = _add(client, "LATE")
    assert resp.status_code == 409 and resp.json() == {"detail": MESSAGE}
    assert len(equities_store.load_tickers()) == equities_store.MAX_TICKERS == 30
    assert _add(client, "T05").status_code == 200  # existing re-adds


def test_concurrent_adds_store_exactly_thirty(client, refreshes):
    codes = []
    lock = threading.Lock()

    def worker(i):
        code = _add(client, f"C{i:02d}").status_code
        with lock:
            codes.append(code)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(35)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200] * 30 + [409] * 5
    stored = equities_store.load_tickers()
    assert len(stored) == 30 and len(set(stored)) == 30


def test_new_ticker_triggers_one_background_refresh(client, refreshes):
    _add(client, "AAPL")
    assert refreshes == [1]


def test_existing_ticker_does_not_trigger_refresh(client, refreshes):
    _add(client, "AAPL")
    _add(client, "aapl")
    assert refreshes == [1]


def test_layout_failure_is_logged_not_failed(client, refreshes, caplog):
    with caplog.at_level(logging.WARNING):
        resp = _add(client, "AAPL", group_id="g-missing")
        assert resp.status_code == 200 and resp.json() == {"tickers": ["AAPL"]}
        assert client.delete("/api/equities/AAPL").status_code == 200
    assert "layout not updated after adding AAPL" in caplog.text


def test_delete_removes(client, refreshes):
    _add(client, "AAPL")
    _add(client, "MSFT")
    resp = client.delete("/api/equities/aapl")
    assert resp.status_code == 200 and resp.json() == {"tickers": ["MSFT"]}


def test_delete_missing_is_404(client):
    assert client.delete("/api/equities/NOPE").status_code == 404


def test_board_is_cache_only(client, refreshes, monkeypatch):
    _add(client, "AAPL")
    fx.seed("AAPL", date(2026, 10, 12), 120)
    monkeypatch.setattr(lse_adapter, "_request_daily", lambda *a, **k: pytest.fail("network"))
    body = client.get("/api/equities/board").json()
    assert body["timeframe"] == "1d" and body["server_time"] == "2026-10-12T21:30:00Z"
    panel = body["coins"][0]
    assert panel["symbol"] == "AAPL" and panel["chart"]["available"] is True
    assert set(panel["gain_by_timeframe"]) == {"1d", "1w"}
    assert client.get("/api/equities/board?timeframe=1w").status_code == 200


def test_board_other_timeframe_is_422(client):
    for tf in ("4h", "15m", "1m"):
        assert client.get(f"/api/equities/board?timeframe={tf}").status_code == 422


def test_spaghetti_route_has_no_references(client, refreshes):
    _add(client, "AAPL")
    fx.seed("AAPL", date(2026, 10, 12), 300)
    body = client.get("/api/equities/spaghetti?timeframe=1d").json()
    assert body["references"] == [] and body["window_cap_bars"] == 200
    assert body["series"][0]["points"][0]["close"] == 0.0
    assert client.get("/api/equities/spaghetti?timeframe=1h").status_code == 422


def test_chart_route(client):
    fx.seed("AAPL", date(2026, 10, 12), 120)
    body = client.get("/api/equities/aapl/chart?timeframe=1d").json()
    assert body["symbol"] == "AAPL" and body["timeframe"] == "1d"
    assert body["chart"]["available"] is True and body["chart"]["rsi"]


def test_chart_other_timeframe_is_422(client):
    assert client.get("/api/equities/AAPL/chart?timeframe=4h").status_code == 422


def test_status_route_never_shows_the_key(client, monkeypatch):
    body = client.get("/api/equities/status").json()
    assert body["running"] is False and body["disabled_reason"] == "missing-key"
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)
    resp = client.get("/api/equities/status")
    assert resp.json()["disabled_reason"] == "not-started"
    assert fx.SYNTHETIC_CREDENTIAL not in resp.text


def test_refresh_post_is_202_and_runs_in_background(client, monkeypatch):
    seen = []
    monkeypatch.setattr(lse_adapter, "refresh_equity", lambda t: seen.append(t))
    (equities_store.equities_path()).write_text(json.dumps({"tickers": ["AAPL"]}))
    resp = client.post("/api/equities/refresh")
    assert resp.status_code == 202
    assert resp.json()["accepted"] is True and "already_running" in resp.json()
    assert equities_refresh.wait_until_idle(5.0)
    assert seen == ["AAPL"]


def test_routes_registered_and_crypto_routes_kept():
    paths = set(app.openapi()["paths"])
    assert {
        "/api/equities", "/api/equities/{ticker}", "/api/equities/board",
        "/api/equities/spaghetti", "/api/equities/{ticker}/chart",
        "/api/equities/status", "/api/equities/refresh",
    } <= paths
    assert {"/api/screener/board", "/api/watchlist", "/api/refresh/status"} <= paths
