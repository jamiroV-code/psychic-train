"""T40 / S5a: the 30-coin cap, symbol validation and the watchlist's layout
upkeep (C3, C5). Store names are read as `watchlist_store.<Name>` at call
time: `tests/deploy` reloads that module before this file runs.
"""
from __future__ import annotations

import json
import threading

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from api.data import layout as layout_store  # noqa: E402
from api.data import watchlist as watchlist_store  # noqa: E402
from api.main import app  # noqa: E402

MESSAGE = "Screener is full: 30 coins maximum. Remove a coin to add another."


@pytest.fixture(autouse=True)
def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.delenv("SCREENER_LAYOUT_PATH", raising=False)
    return tmp_path


@pytest.fixture
def client():
    return fastapi_testclient.TestClient(app)


def _fill(tmp_path, n):
    coins = [f"C{i}" for i in range(n)]
    (tmp_path / "watchlist.json").write_text(json.dumps({"coins": coins}))
    return coins


def _add(client, symbol, **extra):
    return client.post("/api/watchlist", json={"symbol": symbol, **extra})


def test_thirty_accepted_and_thirty_first_refused_with_exact_message(client):
    for i in range(30):
        assert _add(client, f"c{i}").status_code == 200
    assert len(watchlist_store.read_watchlist()) == watchlist_store.MAX_COINS == 30
    resp = _add(client, "LATE")
    assert resp.status_code == 409
    assert resp.json() == {"detail": MESSAGE}
    assert watchlist_store.CAP_MESSAGE == MESSAGE


def test_refusal_leaves_watchlist_and_layout_unchanged(client, tmp_path):
    _fill(tmp_path, 30)
    assert client.post("/api/layout/crypto", json={
        "revision": 0, "groups": [{"id": "main", "name": "Main", "coins": []}], "hidden_lines": []
    }).status_code == 200
    before = {p: (tmp_path / p).read_bytes() for p in ("watchlist.json", "layout.json")}
    assert _add(client, "LATE", group_id="main").status_code == 409
    assert {p: (tmp_path / p).read_bytes() for p in before} == before


def test_removing_one_at_thirty_allows_exactly_one_add(client, tmp_path):
    _fill(tmp_path, 30)
    assert client.delete("/api/watchlist/C0").status_code == 200
    assert _add(client, "NEW1").status_code == 200
    assert _add(client, "NEW2").status_code == 409
    assert len(watchlist_store.read_watchlist()) == 30


def test_re_adding_existing_coin_at_thirty_is_noop(client, tmp_path):
    coins = _fill(tmp_path, 30)
    resp = _add(client, "c5")
    assert resp.status_code == 200 and resp.json() == {"coins": coins}


def test_file_over_thirty_is_kept_and_new_adds_blocked(client, tmp_path):
    coins = _fill(tmp_path, 33)
    assert client.get("/api/watchlist").json() == {"coins": coins}
    assert _add(client, "NEW").status_code == 409
    assert watchlist_store.read_watchlist() == coins


def test_from_thirty_two_removing_to_thirty_blocks_and_twenty_nine_allows(client, tmp_path):
    _fill(tmp_path, 32)
    for symbol in ("C0", "C1"):
        assert client.delete(f"/api/watchlist/{symbol}").status_code == 200
    assert _add(client, "NEW").status_code == 409
    assert client.delete("/api/watchlist/C2").status_code == 200
    assert _add(client, "NEW").status_code == 200
    assert len(watchlist_store.read_watchlist()) == 30


def test_invalid_symbols_are_422_and_nothing_stored(client, tmp_path):
    for bad in ("", "   ", "BT C", "A" * 16, "BTC!", "-BTC"):
        assert _add(client, bad).status_code == 422, bad
    assert not (tmp_path / "watchlist.json").exists()
    resp = _add(client, "  eth.b  ")
    assert resp.status_code == 200 and resp.json() == {"coins": ["ETH.B"]}


def test_add_with_group_id_places_coin_in_that_group(client, tmp_path):
    # No layout file yet: the default is saved with the coin moved.
    _add(client, "BTC")
    resp = _add(client, "ETH", group_id="main")
    assert resp.status_code == 200 and resp.json() == {"coins": ["BTC", "ETH"]}
    stored = json.loads((tmp_path / "layout.json").read_text())["sections"]["crypto"]
    assert stored["revision"] == 1 and stored["groups"] == [{"id": "main", "name": "Main", "coins": ["BTC", "ETH"]}]
    # With a saved layout: the coin lands in the named group.
    client.post("/api/layout/crypto", json={"revision": 1, "groups": [
        {"id": "majors", "name": "Majors", "coins": ["BTC", "ETH"]}, {"id": "alts", "name": "Alts", "coins": []},
    ], "hidden_lines": []})
    _add(client, "SOL", group_id="majors")
    _add(client, "DOGE")
    layout = client.get("/api/layout/crypto").json()
    assert layout["revision"] == 3
    assert [g["coins"] for g in layout["groups"]] == [["BTC", "ETH", "SOL"], ["DOGE"]]


def test_remove_drops_coin_from_groups_and_hidden_lines_keeps_btc(client, tmp_path):
    for s in ("BTC", "ETH", "SOL"):
        _add(client, s)
    client.post("/api/layout/crypto", json={"revision": 0, "groups": [
        {"id": "main", "name": "Main", "coins": ["BTC", "ETH", "SOL"]}], "hidden_lines": ["BTC", "ETH"]})
    for s in ("ETH", "BTC"):
        assert client.delete(f"/api/watchlist/{s}").status_code == 200
    stored = json.loads((tmp_path / "layout.json").read_text())["sections"]["crypto"]
    assert stored["revision"] == 3
    assert stored["groups"][0]["coins"] == ["SOL"]
    assert stored["hidden_lines"] == ["BTC"]


def test_failing_layout_write_does_not_fail_the_add(client, tmp_path, monkeypatch):
    def boom(*_a, **_kw):
        raise OSError("layout disk gone")

    monkeypatch.setattr(layout_store, "_write", boom)
    resp = _add(client, "BTC", group_id="main")
    assert resp.status_code == 200 and resp.json() == {"coins": ["BTC"]}
    assert client.delete("/api/watchlist/BTC").status_code == 200
    assert not (tmp_path / "layout.json").exists()


def test_store_add_coin_enforces_cap_validation_and_concurrency(tmp_path):
    with pytest.raises(watchlist_store.InvalidSymbolError):
        watchlist_store.add_coin("not valid")
    _fill(tmp_path, 29)
    barrier = threading.Barrier(8)
    outcomes: list[object] = []

    def worker(i):
        barrier.wait()
        try:
            watchlist_store.add_coin(f"T{i}")
            outcomes.append("ok")
        except Exception as exc:  # recorded and checked below
            outcomes.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("ok") == 1
    errors = [o for o in outcomes if o != "ok"]
    assert len(errors) == 7 and all(isinstance(e, watchlist_store.WatchlistFullError) for e in errors)
    assert len(json.loads((tmp_path / "watchlist.json").read_text())["coins"]) == 30
