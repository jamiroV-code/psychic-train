"""GET/POST/DELETE /api/watchlist — add/remove/list, idempotent add, 404 on
remove-missing (item 19).

SANDBOX NOTE: this test requires `fastapi` + `fastapi.testclient`, which
could not be installed in the execution sandbox (no package-registry
network access — see the EXECUTE report's Deviations section). It is
written to the plan's exact spec and is expected to pass once `uv sync`
installs the real dependencies; it was not runnable in this session.
"""
from __future__ import annotations

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from api.data import watchlist as watchlist_store  # noqa: E402
from api.main import app  # noqa: E402

TestClient = fastapi_testclient.TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    wl_path = tmp_path / "watchlist.json"
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", wl_path)
    return TestClient(app)


def test_get_empty_watchlist(client):
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    assert resp.json() == {"coins": []}


def test_add_coin(client):
    resp = client.post("/api/watchlist", json={"symbol": "btc"})
    assert resp.status_code == 200
    assert resp.json() == {"coins": ["BTC"]}


def test_add_coin_is_idempotent(client):
    client.post("/api/watchlist", json={"symbol": "BTC"})
    resp = client.post("/api/watchlist", json={"symbol": "BTC"})
    assert resp.json() == {"coins": ["BTC"]}


def test_remove_coin(client):
    client.post("/api/watchlist", json={"symbol": "BTC"})
    resp = client.delete("/api/watchlist/BTC")
    assert resp.status_code == 200
    assert resp.json() == {"coins": []}


def test_remove_missing_coin_returns_404_not_silent_noop(client):
    resp = client.delete("/api/watchlist/DOGE")
    assert resp.status_code == 404
