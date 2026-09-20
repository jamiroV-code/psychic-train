"""Supplementary pure-logic test for api/data/watchlist.py's CRUD functions
(not a plan-named file — added because api/tests/routers/test_watchlist.py,
the plan's actual item-19 gate, requires fastapi.testclient which could not
be installed in this sandbox; see EXECUTE report Deviations). Exercises the
exact same store this project's watchlist router calls, just without going
through FastAPI's HTTP layer.
"""
from __future__ import annotations

import pytest

from api.data import watchlist as watchlist_store


@pytest.fixture
def wl_path(tmp_path):
    return tmp_path / "watchlist.json"


def test_read_empty_watchlist_when_no_file_yet(wl_path):
    assert watchlist_store.read_watchlist(wl_path) == []


def test_add_coin_then_read(wl_path):
    watchlist_store.add_coin("btc", wl_path)
    assert watchlist_store.read_watchlist(wl_path) == ["BTC"]


def test_add_coin_is_idempotent(wl_path):
    watchlist_store.add_coin("BTC", wl_path)
    watchlist_store.add_coin("BTC", wl_path)
    assert watchlist_store.read_watchlist(wl_path) == ["BTC"]


def test_remove_coin(wl_path):
    watchlist_store.add_coin("BTC", wl_path)
    watchlist_store.add_coin("HYPE", wl_path)
    result = watchlist_store.remove_coin("BTC", wl_path)
    assert result == ["HYPE"]
    assert watchlist_store.read_watchlist(wl_path) == ["HYPE"]


def test_remove_missing_coin_raises_not_silent_noop(wl_path):
    with pytest.raises(watchlist_store.SymbolNotFoundError):
        watchlist_store.remove_coin("DOGE", wl_path)
