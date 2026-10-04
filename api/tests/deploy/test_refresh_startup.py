"""T35 / S8: the app lifespan starts and stops the refresh worker, driven by
the tri-state `SCREENER_REFRESH_WORKER` (0 off, 1 forces on, unset on).

The package conftest blocks the network and guards the real cache; the
worker's first tick is 20 s away and its fetch is stubbed, so nothing is
refreshed here.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.data import ccxt_adapter, refresh_worker
from api.main import app


def _no_fetch(symbol, timeframe, exchange=None):
    raise AssertionError("the startup tests must not refresh anything")


def test_lifespan_starts_and_stops_worker(isolated_cache, monkeypatch):
    # A2: conftest forces 0, so drop it to test the unset-means-on default.
    monkeypatch.delenv("SCREENER_REFRESH_WORKER", raising=False)
    monkeypatch.setattr(refresh_worker, "_default_fetch", _no_fetch)

    with TestClient(app) as client:
        worker = refresh_worker.current_worker()
        assert worker is not None and worker.running
        assert ccxt_adapter._refresh_hook == worker.request_refresh
        body = client.get("/api/refresh/status").json()
        assert body["running"] is True and body["disabled_reason"] is None

    assert not worker.running
    assert worker._thread is not None and not worker._thread.is_alive()
    assert refresh_worker.current_worker() is None
    assert ccxt_adapter._refresh_hook is None


def test_worker_off_when_env_is_zero(isolated_cache, monkeypatch):
    monkeypatch.setenv("SCREENER_REFRESH_WORKER", "0")

    with TestClient(app) as client:
        assert refresh_worker.current_worker() is None
        body = client.get("/api/refresh/status").json()
        assert body["running"] is False
        assert body["disabled_reason"] == "SCREENER_REFRESH_WORKER=0"
        assert client.post("/api/refresh/now").status_code == 503


def test_env_one_forces_worker_on_even_with_cache_root_override(isolated_cache, monkeypatch, tmp_path):
    monkeypatch.setenv("SCREENER_REFRESH_WORKER", "1")
    monkeypatch.setenv("SCREENER_CACHE_ROOT", str(tmp_path / "custom-cache"))
    monkeypatch.setattr(refresh_worker, "_default_fetch", _no_fetch)

    with TestClient(app) as client:
        worker = refresh_worker.current_worker()
        assert worker is not None and worker.running
        assert client.get("/api/refresh/status").json()["running"] is True

    assert not worker.running and refresh_worker.current_worker() is None
