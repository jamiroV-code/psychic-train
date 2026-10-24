"""S-A (T68): watchlist add/remove keep baskets coherent (AC-32, D-1)."""
from __future__ import annotations

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from api.data import layout as layout_store  # noqa: E402
from api.data import watchlist as watchlist_store  # noqa: E402
from api.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.delenv("SCREENER_LAYOUT_PATH", raising=False)
    return tmp_path


@pytest.fixture
def client():
    for s in ("BTC", "TAO", "SOL"):
        watchlist_store.add_coin(s)
    return fastapi_testclient.TestClient(app)


def _save(client):
    groups = [
        {"id": "main", "name": "Main", "coins": ["BTC"]},
        {"id": "ai", "name": "AI", "coins": ["TAO"]},
        {"id": "l1", "name": "L1", "coins": ["SOL"]},
    ]
    resp = client.post("/api/layout/crypto", json={"revision": 0, "groups": groups, "hidden_lines": []})
    assert resp.status_code == 200


def test_remove_basket_coin_reports_affected_basket(client):
    _save(client)
    resp = client.delete("/api/watchlist/tao")
    assert resp.status_code == 200
    assert resp.json() == {"coins": ["BTC", "SOL"], "affected_baskets": ["AI"]}


def test_remove_unassigned_coin_has_no_affected_baskets(client):
    _save(client)
    assert client.delete("/api/watchlist/BTC").json()["affected_baskets"] == []


def test_remove_without_layout_file_has_no_affected_baskets(client):
    assert client.delete("/api/watchlist/SOL").json()["affected_baskets"] == []


def test_remove_survives_layout_failure(client, monkeypatch):
    _save(client)

    def boom(*a, **k):
        raise RuntimeError("layout down")

    monkeypatch.setattr(layout_store, "read_layout", boom)
    resp = client.delete("/api/watchlist/TAO")
    assert resp.status_code == 200
    assert resp.json()["affected_baskets"] == []


def test_remove_missing_still_404(client):
    _save(client)
    assert client.delete("/api/watchlist/DOGE").status_code == 404


def test_add_coin_without_group_id_lands_in_main_not_last_basket(client):
    _save(client)
    assert client.post("/api/watchlist", json={"symbol": "ETH"}).status_code == 200
    groups = {g["id"]: g["coins"] for g in client.get("/api/layout/crypto").json()["groups"]}
    assert "ETH" in groups["main"]
    assert "ETH" not in groups["l1"]


def test_add_coin_with_group_id_still_honoured(client):
    _save(client)
    client.post("/api/watchlist", json={"symbol": "ETH", "group_id": "ai"})
    groups = {g["id"]: g["coins"] for g in client.get("/api/layout/crypto").json()["groups"]}
    assert "ETH" in groups["ai"]


def test_add_coin_without_layout_file_does_not_create_one(client):
    client.post("/api/watchlist", json={"symbol": "ETH"})
    assert not layout_store.layout_path().exists()


def test_re_adding_existing_coin_does_not_move_it(client):
    _save(client)
    client.post("/api/watchlist", json={"symbol": "TAO"})
    groups = {g["id"]: g["coins"] for g in client.get("/api/layout/crypto").json()["groups"]}
    assert "TAO" in groups["ai"]
