"""Symbol suggestions: ranking, per-symbol name choice, never-raise behaviour. No network."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.data import symbol_index
from api.main import app

COINS = [
    {"symbol": "SHIB", "name": "Shiba Inu", "venues": ["gate"], "rank": 20},
    {"symbol": "SHIBDOGE", "name": "ShibaDoge", "venues": ["gate"], "rank": 10_000},
    {"symbol": "BTC", "name": "Bitcoin", "venues": ["Hyperliquid"], "rank": 0},
    {"symbol": "WBTC", "name": "Wrapped Bitcoin", "venues": ["gate"], "rank": 15},
    {"symbol": "LEO", "name": "LEO Token", "venues": ["bitfinex"], "rank": 30},
    {"symbol": "ABC", "name": "Bitcoin Cash Abc", "venues": [], "rank": 10_000},
]


@pytest.fixture(autouse=True)
def _index(monkeypatch):
    monkeypatch.setattr(symbol_index, "ensure_built", lambda: None)
    monkeypatch.setattr(symbol_index, "_indexes", {
        "coin": symbol_index.Index(rows=COINS, ready=True),
        "ticker": symbol_index.Index(rows=[{"symbol": "NVDA", "name": "Nvidia Corp", "venues": ["Hyperliquid"], "rank": 0}], ready=True),
    })


def _symbols(kind, q, **kw):
    return [s["symbol"] for s in symbol_index.suggest(kind, q, **kw)["suggestions"]]


def test_exact_symbol_then_prefix_then_name_words_then_substring():
    assert _symbols("coin", "btc") == ["BTC", "WBTC"]  # exact symbol, then the symbol merely containing it
    assert _symbols("coin", "shib")[:2] == ["SHIB", "SHIBDOGE"]  # exact before prefix, rank breaks ties inside a tier
    assert _symbols("coin", "bitc") == ["BTC", "WBTC", "ABC"]  # typed by name: word-prefix of the name, best rank first


def test_names_are_matched_case_insensitively_and_by_any_word():
    assert _symbols("coin", "TOKEN") == ["LEO"]
    assert _symbols("coin", "cash") == ["ABC"]


def test_empty_or_unmatched_query_returns_nothing_and_limit_is_clamped():
    assert symbol_index.suggest("coin", "  ")["suggestions"] == []
    assert _symbols("coin", "zzzz") == []
    assert len(_symbols("coin", "b", limit=2)) == 2


def test_tickers_and_coins_are_separate_indexes():
    assert _symbols("ticker", "nvidia") == ["NVDA"] and _symbols("coin", "nvidia") == []


def test_best_name_prefers_universe_coin_then_non_copy_then_shortest_id():
    listing = [
        {"id": "binance-peg-shib", "symbol": "shib", "name": "Binance-Peg SHIB"},
        {"id": "shiba-inu-wormhole", "symbol": "shib", "name": "Shiba Inu (Wormhole)"},
        {"id": "shiba-inu", "symbol": "shib", "name": "Shiba Inu"},
        {"id": "x-token", "symbol": "xyz", "name": "X Token"},
        {"id": "x", "symbol": "xyz", "name": "X Wrapped"},
    ]
    assert symbol_index._best_names(listing, {})["SHIB"][0] == "Shiba Inu"
    assert symbol_index._best_names(listing, {"binance-peg-shib": 3})["SHIB"][0] == "Binance-Peg SHIB"  # top-100 wins
    assert symbol_index._best_names(listing, {})["XYZ"][0] == "X Token"  # the 'Wrapped' copy loses to the plain coin


def test_endpoint_shape_and_validation():
    client = TestClient(app)
    body = client.get("/api/symbols/suggest", params={"kind": "coin", "q": "shib"}).json()
    assert body["ready"] is True and body["suggestions"][0] == {"symbol": "SHIB", "name": "Shiba Inu", "venues": ["gate"]}
    assert client.get("/api/symbols/suggest", params={"kind": "nope", "q": "x"}).status_code == 422
    assert client.get("/api/symbols/suggest", params={"kind": "coin", "q": "x" * 41}).status_code == 422


def test_a_failed_build_keeps_the_index_empty_and_unready(monkeypatch, isolated_cache):
    monkeypatch.setattr(symbol_index, "_indexes", {"coin": symbol_index.Index(), "ticker": symbol_index.Index()})
    monkeypatch.setattr(symbol_index, "_BUILDERS", {"coin": ("coins.json", lambda c: (_ for _ in ()).throw(RuntimeError("down")))})
    symbol_index._build_all()
    assert symbol_index._indexes["coin"].ready is False


def test_exchange_leveraged_tokens_are_never_listed(monkeypatch):
    class Gate:
        markets = {
            "SHIB/USDT": {"base": "SHIB", "quote": "USDT", "spot": True, "active": True},
            "SHIB3L/USDT": {"base": "SHIB3L", "quote": "USDT", "spot": True, "active": True},
            "BTC5S/USDT": {"base": "BTC5S", "quote": "USDT", "spot": True, "active": True},
        }

    monkeypatch.setattr(symbol_index.ccxt_adapter, "_exchange", lambda: None)
    monkeypatch.setattr(symbol_index.ccxt_adapter, "_fallback_exchange", lambda n: Gate() if n == "gate" else None)
    assert "SHIB" in symbol_index._tradable_coin_venues()
    assert not {"SHIB3L", "BTC5S"} & set(symbol_index._tradable_coin_venues())
