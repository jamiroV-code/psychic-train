"""S9E: `/api/equities/status` and `/refresh` through the `TestClient(app)`
lifespan, with the equities worker on (fake fetch), off and missing its
key. The crypto worker's fetch is stubbed; nothing reaches the network."""
from __future__ import annotations

import threading
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.data import equities_refresh, equities_store, lse_adapter, refresh_worker
from api.data import watchlist as watchlist_store
from api.main import app
from api.tests import equities_fixtures as fx

NOW = pd.Timestamp("2026-10-13T12:00:00Z")


def _no_crypto_fetch(symbol, timeframe, exchange=None):
    raise AssertionError("the equities status tests must not refresh crypto")


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(tmp_path / "equities.json"))
    monkeypatch.setenv("SCREENER_LAYOUT_PATH", str(tmp_path / "layout.json"))
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    monkeypatch.delenv("SCREENER_REFRESH_WORKER", raising=False)
    monkeypatch.setattr(lse_adapter, "_now", lambda: NOW)
    monkeypatch.setattr(refresh_worker, "_default_fetch", _no_crypto_fetch)
    yield
    equities_refresh.stop_worker()
    assert equities_refresh.wait_until_idle(5.0)


def test_lifespan_running_with_fake_fetch(monkeypatch):
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)
    equities_store.add_ticker("AAPL")
    fx.seed("AAPL", date(2026, 10, 12), 80)
    fetched = threading.Event()
    seen = []

    def fake(ticker):
        seen.append(ticker)
        fetched.set()

    monkeypatch.setattr(equities_refresh, "_default_fetch", fake)
    with TestClient(app) as client:
        worker = equities_refresh.current_worker()
        assert worker is not None and worker.running
        for _ in range(100):
            if worker.next_tick_at is not None:
                break
            fetched.wait(0.01)
        body = client.get("/api/equities/status").json()
        assert body["running"] is True and body["disabled_reason"] is None
        assert body["next_tick_at"] == "2026-10-13T20:30:00Z"
        assert body["last_bar_date"] == "2026-10-12"
        resp = client.post("/api/equities/refresh")
        assert resp.status_code == 202 and resp.json()["accepted"] is True
        assert fetched.wait(5.0)
        assert fx.SYNTHETIC_CREDENTIAL not in client.get("/api/equities/status").text
    assert seen == ["AAPL"]
    assert not worker.running and equities_refresh.current_worker() is None


def test_lifespan_off_with_env_zero(monkeypatch):
    monkeypatch.setenv("SCREENER_REFRESH_WORKER", "0")
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)
    with TestClient(app) as client:
        assert equities_refresh.current_worker() is None
        body = client.get("/api/equities/status").json()
        assert body["running"] is False
        assert body["disabled_reason"] == "SCREENER_REFRESH_WORKER=0"
        assert body["next_tick_at"] is None


def test_lifespan_missing_key():
    with TestClient(app) as client:
        assert equities_refresh.current_worker() is None
        body = client.get("/api/equities/status").json()
        assert body["running"] is False and body["disabled_reason"] == "missing-key"
        # The crypto worker is unaffected.
        assert client.get("/api/refresh/status").json()["running"] is True
