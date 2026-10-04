"""T32 / S1 — clock skew measured on the live fetch path (B6).

Skew = host midpoint (two host reads bracketing `fetch_time`) minus the
exchange's time, in seconds; cached 15 minutes per process; warning above
120 s; a missing or failing `fetch_time` is "unknown", never an error. No
test here touches the network.
"""
from __future__ import annotations

import ccxt
import pandas as pd
import pytest

from api.data import ccxt_adapter

NOW = pd.Timestamp("2026-10-03T14:10:00Z")


class SkewExchange:
    id = "hyperliquid"

    def __init__(self, exchange_ms=None, raise_exc=None):
        self.exchange_ms = exchange_ms
        self.raise_exc = raise_exc
        self.fetch_time_calls = 0
        self.markets = None

    def load_markets(self):
        return {}

    def fetch_time(self):
        self.fetch_time_calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.exchange_ms

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        return []


class NoTimeExchange:
    id = "hyperliquid"

    def load_markets(self):
        return {}


@pytest.fixture
def clocks(monkeypatch, isolated_cache):
    state = {"now": NOW, "host": iter([])}
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: state["now"], raising=False)
    monkeypatch.setattr(ccxt_adapter, "_host_time", lambda: next(state["host"]), raising=False)
    ccxt_adapter.reset_clock_skew()
    ccxt_adapter.reset_exchange_cache()
    yield state
    ccxt_adapter.reset_clock_skew()
    ccxt_adapter.reset_exchange_cache()


def test_skew_is_host_midpoint_minus_exchange_time(clocks):
    clocks["host"] = iter([1000.0, 1002.0])
    ex = SkewExchange(exchange_ms=995_000)

    ccxt_adapter.refresh_clock_skew(ex)

    assert ccxt_adapter.last_clock_skew() == pytest.approx(6.0)
    assert ex.fetch_time_calls == 1


def test_skew_warning_above_120s_only():
    assert ccxt_adapter.clock_skew_warning(None) is False
    assert ccxt_adapter.clock_skew_warning(120.0) is False
    assert ccxt_adapter.clock_skew_warning(-120.0) is False
    assert ccxt_adapter.clock_skew_warning(120.5) is True
    assert ccxt_adapter.clock_skew_warning(-121.0) is True


def test_skew_measured_once_per_15_minutes(clocks, monkeypatch):
    clocks["host"] = iter([1000.0, 1000.0, 2000.0, 2000.0])
    ex = SkewExchange(exchange_ms=1_000_000)
    # the live path: the process-wide exchange, not an injected one
    monkeypatch.setattr(ccxt_adapter.ccxt, "hyperliquid", lambda *a, **k: ex)

    ccxt_adapter.fetch_ohlcv("BTC", "1h")
    clocks["now"] = NOW + pd.Timedelta(seconds=899)
    ccxt_adapter.fetch_ohlcv("ETH", "1h")
    assert ex.fetch_time_calls == 1

    clocks["now"] = NOW + pd.Timedelta(seconds=900)
    ex.exchange_ms = 1_999_000
    ccxt_adapter.fetch_ohlcv("SOL", "1h")
    assert ex.fetch_time_calls == 2
    assert ccxt_adapter.last_clock_skew() == pytest.approx(1.0)


def test_missing_fetch_time_means_unknown_not_error(clocks):
    ccxt_adapter.refresh_clock_skew(NoTimeExchange())
    assert ccxt_adapter.last_clock_skew() is None
    assert ccxt_adapter.clock_skew_warning(ccxt_adapter.last_clock_skew()) is False

    clocks["host"] = iter([1000.0, 1000.0])
    ccxt_adapter.reset_clock_skew()
    ccxt_adapter.refresh_clock_skew(SkewExchange(exchange_ms=None))
    assert ccxt_adapter.last_clock_skew() is None


def test_fetch_time_exception_means_unknown(clocks):
    clocks["host"] = iter([1000.0, 1000.0])
    ccxt_adapter.refresh_clock_skew(SkewExchange(raise_exc=ccxt.NetworkError("down")))
    assert ccxt_adapter.last_clock_skew() is None
    assert ccxt_adapter.clock_skew_warning(ccxt_adapter.last_clock_skew()) is False
