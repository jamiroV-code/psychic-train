"""Screener fallback: coins Hyperliquid cannot serve come from a spot provider, in their own cache series. No network."""
from __future__ import annotations

import ccxt
import pandas as pd
import pytest

from api.data import cache, ccxt_adapter

NOW = pd.Timestamp("2026-11-02T12:07:00Z")


def _bars(timeframe: str, n: int = 120, base: float = 50.0) -> list[list[float]]:
    from api.data import freshness
    step = freshness.TIMEFRAME_SECONDS[timeframe] * 1000
    last = int(freshness.current_bar_open(timeframe, NOW).timestamp() * 1000)
    return [[last - (n - 1 - i) * step, base + i, base + i + 1, base + i - 1, base + i + 0.5, 10.0] for i in range(n)]


class FakeProvider:
    """A spot exchange: lists SHIB/USDT (spot) and ETH/USDT:USDT (a perp that must never be picked)."""

    def __init__(self, name: str, listed=("SHIB",)):
        self.id = name
        self.markets = {f"{c}/USDT": {"spot": True, "active": True} for c in listed}
        self.markets["ETH/USDT:USDT"] = {"spot": False, "swap": True, "active": True}
        self.calls: list[tuple[str, str]] = []

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        self.calls.append((symbol, timeframe))
        if symbol not in self.markets:
            raise ccxt.BadSymbol(symbol)
        return _bars(timeframe)


class HyperliquidWithoutShib:
    id = "hyperliquid"
    markets = {"BTC/USDC:USDC": {"swap": True, "spot": False, "base": "BTC", "baseName": "BTC", "active": True}}

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        return _bars(timeframe, base=100.0)


@pytest.fixture(autouse=True)
def _env(isolated_cache, monkeypatch):
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: NOW)
    ccxt_adapter.reset_exchange_cache()
    ccxt_adapter.set_refresh_hook(None)
    monkeypatch.setattr(ccxt_adapter, "_known_bad_symbols", set())
    monkeypatch.setenv("SCREENER_FALLBACK_PROVIDERS", "gate,mexc")
    monkeypatch.setattr(ccxt_adapter, "_exchange", lambda: HyperliquidWithoutShib())
    providers = {"gate": FakeProvider("gate"), "mexc": FakeProvider("mexc", listed=("SHIB", "XDC"))}
    monkeypatch.setattr(ccxt_adapter, "_fallback_exchange", lambda name: providers.get(name))
    yield providers
    ccxt_adapter.reset_exchange_cache()


def test_unlisted_coin_is_served_by_the_first_provider_that_lists_it_and_labelled(_env):
    r = ccxt_adapter.fetch_ohlcv("SHIB", "1d")
    assert (r.status, r.source) == ("ok", "gate") and len(r.df) == 120
    assert _env["gate"].calls == [("SHIB/USDT", "1d")] and _env["mexc"].calls == []


def test_next_provider_is_tried_when_the_first_does_not_list_the_coin(_env):
    r = ccxt_adapter.fetch_ohlcv("XDC", "1d")
    assert r.source == "mexc" and not r.df.empty


def test_never_picks_a_perpetual_and_unlisted_everywhere_stays_bad_symbol(_env):
    r = ccxt_adapter.fetch_ohlcv("ETH", "1d")  # only ETH/USDT:USDT exists on the fakes
    assert (r.status, r.source, r.df.empty) == ("bad_symbol", None, True)


def test_hyperliquid_coins_never_touch_a_fallback(_env):
    r = ccxt_adapter.fetch_ohlcv("BTC", "1d")
    assert r.source is None and r.status == "ok"
    assert _env["gate"].calls == [] and _env["mexc"].calls == []


def test_fallback_bars_are_cached_apart_from_hyperliquid(_env):
    ccxt_adapter.fetch_ohlcv("SHIB", "1d")
    assert cache.read_ohlcv("SHIB@gate", "1d").shape[0] == 120
    assert cache.read_ohlcv("SHIB", "1d").empty            # Hyperliquid's series for SHIB is untouched
    _env["gate"].calls.clear()
    assert ccxt_adapter.fetch_ohlcv("SHIB", "1d").source == "gate" and _env["gate"].calls == []  # fresh cache


def test_weekly_is_derived_from_the_fallback_daily_and_stored_under_its_key(_env):
    r = ccxt_adapter.fetch_ohlcv("SHIB", "1w")
    assert r.source == "gate" and not r.df.empty
    assert not cache.read_ohlcv("SHIB@gate", "1w").empty and cache.read_ohlcv("SHIB", "1w").empty


def test_cache_only_reads_serve_the_fallback_series_without_the_network(_env, monkeypatch):
    ccxt_adapter.fetch_ohlcv("SHIB", "1d")
    monkeypatch.setattr(ccxt_adapter, "_fallback_exchange", lambda name: pytest.fail("network"))
    with ccxt_adapter.cached_reads_only():
        r = ccxt_adapter.fetch_ohlcv("SHIB", "1d")
        assert r.source == "gate" and not r.df.empty
        assert ccxt_adapter.fetch_ohlcv("NOPE", "1d").source is None  # nothing cached anywhere


def test_injected_exchange_and_backfill_never_fall_back(_env):
    assert ccxt_adapter.fetch_ohlcv("SHIB", "1d", exchange=HyperliquidWithoutShib()).status == "bad_symbol"
    assert ccxt_adapter.fetch_ohlcv("SHIB", "1d", since=1).status == "bad_symbol"
    assert _env["gate"].calls == []


def test_no_providers_configured_means_no_fallback(_env, monkeypatch):
    monkeypatch.setenv("SCREENER_FALLBACK_PROVIDERS", "")
    assert ccxt_adapter.fetch_ohlcv("SHIB", "1d").status == "bad_symbol" and _env["gate"].calls == []

