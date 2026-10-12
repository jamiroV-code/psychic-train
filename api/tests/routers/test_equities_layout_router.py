"""S9B: `/api/layout/equities` and the equities add/remove upkeep. Store,
layout, watchlist and cache are redirected to tmp; refresh is recorded, so
nothing reaches the network or a key.
"""
from __future__ import annotations

import json

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from api.data import equities_refresh, equities_store  # noqa: E402
from api.data import watchlist as watchlist_store  # noqa: E402
from api.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(tmp_path / "equities.json"))
    monkeypatch.setenv("SCREENER_LAYOUT_PATH", str(tmp_path / "layout.json"))
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    monkeypatch.setattr(
        equities_refresh, "request_refresh_now", lambda *a, **k: {"accepted": True, "already_running": False}
    )
    return tmp_path


@pytest.fixture
def client():
    for s in ("AAPL", "VOD"):
        equities_store.add_ticker(s)
    return fastapi_testclient.TestClient(app)


def _body(revision=0, groups=None, hidden=None):
    groups = groups if groups is not None else [{"id": "main", "name": "Main", "coins": ["VOD", "AAPL"]}]
    return {"revision": revision, "groups": groups, "hidden_lines": hidden or []}


def _members(resp):
    return [c for g in resp.json()["groups"] for c in g["coins"]]


def test_get_default(client):
    resp = client.get("/api/layout/equities")
    assert resp.status_code == 200
    assert resp.json() == {
        "version": 1,
        "section": "equities",
        "revision": 0,
        "saved_at": None,
        "source": "default",
        "groups": [{"id": "main", "name": "Main", "coins": ["AAPL", "VOD"]}],
        "hidden_lines": [],
    }


def test_post_then_get(client):
    body = _body(0, [{"id": "us", "name": "US", "coins": ["AAPL"]}, {"id": "uk", "name": "UK", "coins": ["VOD"]}], ["VOD"])
    saved = client.post("/api/layout/equities", json=body)
    assert saved.status_code == 200 and saved.json()["revision"] == 1 and saved.json()["source"] == "file"
    got = client.get("/api/layout/equities").json()
    assert [(g["id"], g["coins"]) for g in got["groups"]] == [("us", ["AAPL"]), ("uk", ["VOD"])]
    assert got["hidden_lines"] == ["VOD"] and got["revision"] == 1


def test_stale_revision_is_409(client):
    assert client.post("/api/layout/equities", json=_body(0)).status_code == 200
    assert client.post("/api/layout/equities", json=_body(0)).status_code == 409


def test_invalid_layout_is_422(client, tmp_path):
    dup = [{"id": "a", "name": "A", "coins": ["AAPL"]}, {"id": "b", "name": "B", "coins": ["AAPL"]}]
    assert client.post("/api/layout/equities", json=_body(0, dup)).status_code == 422
    assert client.post("/api/layout/equities", json=_body(0, [])).status_code == 422
    assert not (tmp_path / "layout.json").exists()


def test_add_with_group_id_places_the_ticker(client):
    groups = [{"id": "us", "name": "US", "coins": ["AAPL", "VOD"]}, {"id": "uk", "name": "UK", "coins": []}]
    client.post("/api/layout/equities", json=_body(0, groups))
    assert client.post("/api/equities", json={"symbol": "barc", "group_id": "uk"}).status_code == 200
    got = client.get("/api/layout/equities").json()
    assert [(g["id"], g["coins"]) for g in got["groups"]] == [("us", ["AAPL", "VOD"]), ("uk", ["BARC"])]


def test_remove_drops_the_ticker(client, tmp_path):
    client.post("/api/layout/equities", json=_body(0, hidden=["VOD"]))
    assert client.delete("/api/equities/vod").status_code == 200
    stored = json.loads((tmp_path / "layout.json").read_text())["sections"]["equities"]
    assert [c for g in stored["groups"] for c in g["coins"]] == ["AAPL"] and stored["hidden_lines"] == []
    assert _members(client.get("/api/layout/equities")) == ["AAPL"]


def test_no_equity_in_crypto_layout_after_adds(client):
    watchlist_store.add_coin("ETH")
    client.post("/api/equities", json={"symbol": "MSFT"})
    client.post("/api/equities", json={"symbol": "TSLA", "group_id": "main"})
    assert _members(client.get("/api/layout/crypto")) == ["ETH"]
    assert _members(client.get("/api/layout/equities")) == ["AAPL", "VOD", "MSFT", "TSLA"]


def test_delete_resets_only_equities(client, tmp_path):
    watchlist_store.add_coin("ETH")
    client.post("/api/layout/crypto", json={"revision": 0, "groups": [{"id": "main", "name": "Main", "coins": ["ETH"]}], "hidden_lines": ["BTC"]})
    client.post("/api/layout/equities", json=_body(0))
    crypto_before = json.loads((tmp_path / "layout.json").read_text())["sections"]["crypto"]
    resp = client.delete("/api/layout/equities")
    assert resp.status_code == 200 and resp.json()["source"] == "default" and resp.json()["revision"] == 0
    assert json.loads((tmp_path / "layout.json").read_text())["sections"] == {"crypto": crypto_before}
