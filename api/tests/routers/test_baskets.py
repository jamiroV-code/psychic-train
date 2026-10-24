"""S-A (T68): GET/POST /api/narrative/baskets (AC-35, AC-27, AC-9)."""
from __future__ import annotations

import hashlib

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from api.data import layout as layout_store  # noqa: E402
from api.data import watchlist as watchlist_store  # noqa: E402
from api.main import app  # noqa: E402

URL = "/api/narrative/baskets"


@pytest.fixture(autouse=True)
def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.delenv("SCREENER_LAYOUT_PATH", raising=False)
    return tmp_path


@pytest.fixture
def client():
    for s in ("BTC", "ETH", "SOL", "TAO"):
        watchlist_store.add_coin(s)
    return fastapi_testclient.TestClient(app)


def _save(client, groups, revision=0):
    resp = client.post("/api/layout/crypto", json={"revision": revision, "groups": groups, "hidden_lines": []})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _two_groups(client):
    return _save(
        client,
        [
            {"id": "main", "name": "Main", "coins": ["BTC", "ETH"]},
            {"id": "ai", "name": "AI", "coins": ["TAO"]},
            {"id": "l1", "name": "L1", "coins": ["SOL"]},
        ],
    )


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_get_default_layout_is_all_unassigned(client):
    body = client.get(URL).json()
    assert body["revision"] == 0
    assert body["baskets"] == []
    assert sorted(body["unassigned"]) == ["BTC", "ETH", "SOL", "TAO"]


def test_get_splits_main_from_baskets(client):
    saved = _two_groups(client)
    body = client.get(URL).json()
    assert body["revision"] == saved["revision"]
    assert body["baskets"] == [
        {"id": "ai", "name": "AI", "coins": ["TAO"]},
        {"id": "l1", "name": "L1", "coins": ["SOL"]},
    ]
    assert body["unassigned"] == ["BTC", "ETH"]


def test_move_into_basket_names_previous_basket(client):
    _two_groups(client)
    resp = client.post(f"{URL}/ai/coins", json={"symbol": "sol"})
    assert resp.status_code == 200
    assert resp.json() == {"symbol": "SOL", "basket": "AI", "previous_basket": "L1"}
    body = client.get(URL).json()
    assert body["baskets"][0]["coins"] == ["TAO", "SOL"]
    assert body["baskets"][1]["coins"] == []  # empty basket stays


def test_move_from_unassigned_has_null_previous(client):
    _two_groups(client)
    resp = client.post(f"{URL}/ai/coins", json={"symbol": "BTC"})
    assert resp.json() == {"symbol": "BTC", "basket": "AI", "previous_basket": None}


def test_move_to_main_unassigns(client):
    _two_groups(client)
    resp = client.post(f"{URL}/main/coins", json={"symbol": "TAO"})
    assert resp.status_code == 200
    assert resp.json() == {"symbol": "TAO", "basket": None, "previous_basket": "AI"}
    assert "TAO" in client.get(URL).json()["unassigned"]


def test_one_basket_per_coin(client):
    _two_groups(client)
    client.post(f"{URL}/ai/coins", json={"symbol": "SOL"})
    body = client.get(URL).json()
    held = [c for b in body["baskets"] for c in b["coins"]] + body["unassigned"]
    assert sorted(held) == sorted(set(held)) == ["BTC", "ETH", "SOL", "TAO"]


def test_move_survives_reload_via_layout_api(client):
    _two_groups(client)
    client.post(f"{URL}/ai/coins", json={"symbol": "SOL"})
    groups = client.get("/api/layout/crypto").json()["groups"]
    assert next(g for g in groups if g["id"] == "ai")["coins"] == ["TAO", "SOL"]


@pytest.mark.parametrize("gid", ["Bad_ID", "-x", "a" * 41, "UP"])
def test_bad_group_id_is_422(client, gid):
    assert client.post(f"{URL}/{gid}/coins", json={"symbol": "BTC"}).status_code == 422


@pytest.mark.parametrize("sym", ["", "bad symbol", "X" * 16, "!!"])
def test_bad_symbol_is_422(client, sym):
    _two_groups(client)
    assert client.post(f"{URL}/ai/coins", json={"symbol": sym}).status_code == 422


def test_unknown_group_is_404(client):
    _two_groups(client)
    assert client.post(f"{URL}/nope/coins", json={"symbol": "BTC"}).status_code == 404


def test_extra_body_field_is_422(client):
    _two_groups(client)
    resp = client.post(f"{URL}/ai/coins", json={"symbol": "BTC", "x": 1})
    assert resp.status_code == 422


def test_not_on_screener_is_404_and_files_unchanged(client, tmp_path):
    _two_groups(client)
    wl, lay = tmp_path / "watchlist.json", layout_store.layout_path()
    before = (_sha(wl), _sha(lay))
    resp = client.post(f"{URL}/ai/coins", json={"symbol": "DOGE"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "DOGE is not on your screener. Add it to the screener first."
    assert (_sha(wl), _sha(lay)) == before


def test_not_on_screener_without_layout_file_writes_nothing(client, tmp_path):
    resp = client.post(f"{URL}/ai/coins", json={"symbol": "DOGE"})
    assert resp.status_code == 404
    assert not layout_store.layout_path().exists()
