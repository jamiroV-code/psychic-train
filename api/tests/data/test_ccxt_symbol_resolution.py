"""RFC-005 — ccxt unified-symbol resolution and failure honesty.

Covers checklist items 13, 13a, 13b, 13c. Proves AC-1, AC-3, AC-4, AC-5,
AC-9, AC-10.

Why this file exists: `ccxt_adapter` was written and marked verified against
a sandbox SHIM of ccxt (parent plan Deviations item #2) that never validated
symbols. Real ccxt requires `BTC/USDC:USDC`, not `BTC`. Nothing in the suite
pinned the real contract shape, so the gap survived until a live run.
"""
from __future__ import annotations

import threading

import ccxt
import pytest

import pandas as pd

from api.data import cache, ccxt_adapter


# --------------------------------------------------------------------------
# Fakes — shaped like real Hyperliquid markets (perp + spot), so resolution
# is exercised against the structure ccxt actually produces.
# --------------------------------------------------------------------------
MARKETS = {
    "BTC/USDC:USDC": {"swap": True, "spot": False, "base": "BTC", "baseName": "BTC", "active": True},
    "ETH/USDC:USDC": {"swap": True, "spot": False, "base": "ETH", "baseName": "ETH", "active": True},
    "HYPE/USDC:USDC": {"swap": True, "spot": False, "base": "HYPE", "baseName": "HYPE", "active": True},
    "SOL/USDC:USDC": {"swap": True, "spot": False, "base": "SOL", "baseName": "SOL", "active": True},
    "DEAD/USDC:USDC": {"swap": True, "spot": False, "base": "DEAD", "baseName": "DEAD", "active": False},
    "PURR/USDC": {"swap": False, "spot": True, "base": "PURR", "quote": "USDC", "active": True},
}

_BAR = [1_700_000_000_000, 1.0, 2.0, 0.5, 1.5, 100.0]


class FakeExchange:
    """Stands in for a loaded `ccxt.hyperliquid()`."""

    id = "hyperliquid"

    def __init__(self, markets=None, raise_on_fetch=None):
        self.markets = MARKETS if markets is None else markets
        self.load_markets_calls = 0
        self.fetch_calls: list[str] = []
        self._raise = raise_on_fetch

    def load_markets(self):
        self.load_markets_calls += 1
        return self.markets

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        self.fetch_calls.append(symbol)
        if self._raise is not None:
            raise self._raise
        if symbol not in self.markets:
            raise ccxt.BadSymbol(f"hyperliquid does not have market symbol {symbol}")
        return [_BAR]


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(ccxt_adapter.cache, "CACHE_ROOT", tmp_path)
    ccxt_adapter.reset_exchange_cache()
    yield
    ccxt_adapter.reset_exchange_cache()


# --------------------------------------------------------------------------
# AC-1 — resolution
# --------------------------------------------------------------------------
def test_bare_ticker_resolves_to_unified_swap_symbol():
    assert ccxt_adapter.resolve_market_symbol("BTC", FakeExchange()) == "BTC/USDC:USDC"
    assert ccxt_adapter.resolve_market_symbol("HYPE", FakeExchange()) == "HYPE/USDC:USDC"


def test_already_unified_symbol_passes_through():
    assert ccxt_adapter.resolve_market_symbol("ETH/USDC:USDC", FakeExchange()) == "ETH/USDC:USDC"


def test_spot_only_ticker_falls_back_to_spot_market():
    assert ccxt_adapter.resolve_market_symbol("PURR", FakeExchange()) == "PURR/USDC"


def test_inactive_market_is_not_resolved():
    assert ccxt_adapter.resolve_market_symbol("DEAD", FakeExchange()) is None


def test_fetch_sends_the_unified_symbol_to_ccxt():
    """AC-1: the whole defect was that the bare ticker reached ccxt."""
    exch = FakeExchange()
    ccxt_adapter.fetch_ohlcv("BTC", "1d", exchange=exch)
    assert exch.fetch_calls == ["BTC/USDC:USDC"]


# --------------------------------------------------------------------------
# AC-3 / AC-4 — bad_symbol and unavailable stay distinct
# --------------------------------------------------------------------------
def test_unknown_ticker_is_bad_symbol_not_unavailable():
    result = ccxt_adapter.fetch_ohlcv("NOPE", "1d", exchange=FakeExchange())
    assert result.status == "bad_symbol"


def test_network_error_is_unavailable_not_bad_symbol():
    exch = FakeExchange(raise_on_fetch=ccxt.NetworkError("simulated"))
    result = ccxt_adapter.fetch_ohlcv("BTC", "1d", exchange=exch)
    assert result.status == "unavailable"


def test_bad_symbol_raised_by_ccxt_is_not_reported_as_an_outage():
    """The original blanket `except Exception` collapsed BadSymbol — an
    ExchangeError, not a NetworkError — into `unavailable`, i.e. "exchange is
    down". It was not down.
    """
    exch = FakeExchange(raise_on_fetch=ccxt.BadSymbol("simulated"))
    result = ccxt_adapter.fetch_ohlcv("BTC", "1d", exchange=exch)
    assert result.status == "bad_symbol"


# --------------------------------------------------------------------------
# AC-10 / gap G3 — never fabricate a symbol
# --------------------------------------------------------------------------
def test_adapter_never_constructs_a_usdc_symbol_for_an_unknown_ticker():
    """Asserts on the OUTBOUND symbol, not just the status, so a
    reintroduced `f"{ticker}/USDC:USDC"` fallback fails this test.
    """
    exch = FakeExchange()
    ccxt_adapter.fetch_ohlcv("NOPE", "1d", exchange=exch)
    assert exch.fetch_calls == []
    assert "NOPE/USDC:USDC" not in exch.fetch_calls


# --------------------------------------------------------------------------
# AC-5 — load_markets once per process
# --------------------------------------------------------------------------
def test_load_markets_runs_once_across_many_fetches(monkeypatch, isolated_cache):
    exch = FakeExchange()
    monkeypatch.setattr(ccxt_adapter.ccxt, "hyperliquid", lambda *a, **k: exch)
    for tf in ("15m", "1h", "4h", "1d"):
        ccxt_adapter.fetch_ohlcv("BTC", tf)
    assert exch.load_markets_calls == 1


# --------------------------------------------------------------------------
# AC-10 / gap G4 — load_markets failure degrades cleanly
# --------------------------------------------------------------------------
def test_load_markets_failure_degrades_every_symbol_to_unavailable(monkeypatch, isolated_cache):
    class Exploding:
        id = "hyperliquid"
        markets = None

        def load_markets(self):
            raise ccxt.NetworkError("cannot reach exchange")

    monkeypatch.setattr(ccxt_adapter.ccxt, "hyperliquid", lambda *a, **k: Exploding())
    for ticker in ("BTC", "ETH", "HYPE", "SOL"):
        result = ccxt_adapter.fetch_ohlcv(ticker, "1d")
        assert result.status == "unavailable"
        assert result.status != "bad_symbol"


def test_load_markets_failure_is_latched_not_retried_per_fetch(monkeypatch, isolated_cache):
    calls = {"n": 0}

    class Exploding:
        id = "hyperliquid"
        markets = None

        def load_markets(self):
            calls["n"] += 1
            raise ccxt.NetworkError("cannot reach exchange")

    monkeypatch.setattr(ccxt_adapter.ccxt, "hyperliquid", lambda *a, **k: Exploding())
    for _ in range(5):
        ccxt_adapter.fetch_ohlcv("BTC", "1d")
    assert calls["n"] == 1, "markets failure must be latched for the process, not retried per fetch"


# --------------------------------------------------------------------------
# AC-9 / gap G2 — the 1w recursion must not deadlock
#
# `fetch_ohlcv(sym, "1w")` recurses into `fetch_ohlcv(sym, "1d")`. With a
# plain `threading.Lock` held across the fetch, the inner call blocks forever
# on a lock the outer call already holds. `1w` is on the board's hot path, so
# that would hang the primary endpoint on first use.
# --------------------------------------------------------------------------
def test_weekly_recursion_does_not_deadlock(isolated_cache):
    # `isolated_cache` (api/tests/conftest.py) added 19-09-26: this test
    # drives the real cache-first path, so without it the fixture bar is
    # merged into the user's live BTC Parquet files and `write_ohlcv`
    # overwrites the whole series. Same class as the RFC-005 watchlist
    # incident — a test quietly writing over real data.
    exch = FakeExchange()
    done = threading.Event()
    box: dict = {}

    def run():
        try:
            box["result"] = ccxt_adapter.fetch_ohlcv("BTC", "1w", exchange=exch)
        except Exception as exc:  # pragma: no cover
            box["error"] = exc
        finally:
            done.set()

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    assert done.wait(timeout=5.0), "1w recursion deadlocked (>5s) — check lock reentrancy"
    assert "error" not in box, f"1w recursion raised: {box.get('error')!r}"
    # T32 / S1: the 2023 fixture bar is now reported `stale` (B5).
    assert box["result"].status in ("ok", "stale", "unavailable")


def test_weekly_propagates_bad_symbol_from_its_daily_leg(isolated_cache):
    result = ccxt_adapter.fetch_ohlcv("NOPE", "1w", exchange=FakeExchange())
    assert result.status == "bad_symbol"


# --------------------------------------------------------------------------
# Cache-fresh short circuit (19-09-26).
#
# `_cache_is_fresh` now runs BEFORE exchange construction. These pin both
# halves of that: a warm cache must reach no exchange at all, and a cold one
# must still reach it.
# --------------------------------------------------------------------------
class _CountingExchange(FakeExchange):
    """Counts how many times anything asked it for a market list or a bar."""

    def __init__(self):
        super().__init__()
        self.touches = 0

    def load_markets(self):
        self.touches += 1
        return super().load_markets()

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        self.touches += 1
        return super().fetch_ohlcv(symbol, timeframe, since, limit)


def _fresh_daily(bars: int = 3):
    """Daily bars ending at today 00:00 UTC — inside the current, still-open
    daily bar, so `_cache_is_fresh` is True."""
    end = pd.Timestamp.now(tz="UTC").normalize()
    idx = pd.date_range(end=end, periods=bars, freq="D", tz="UTC")
    return pd.DataFrame({
        "timestamp": idx,
        "open": [1.0] * bars, "high": [2.0] * bars, "low": [0.5] * bars,
        "close": [1.5] * bars, "volume": [100.0] * bars,
        "source": ["fixture"] * bars,
    })


def test_a_fresh_cache_is_served_without_touching_the_exchange(isolated_cache):
    cache.write_ohlcv("BTC", "1d", _fresh_daily())
    exch = _CountingExchange()

    result = ccxt_adapter.fetch_ohlcv("BTC", "1d", exchange=exch)

    assert result.status == "ok"
    assert exch.touches == 0, (
        "a warm cache reached the exchange anyway — the freshness check has moved back "
        "below exchange construction, which reintroduces a load_markets() round trip on "
        "every warm request and makes an offline run impossible"
    )


def test_a_cold_cache_still_reaches_the_exchange(isolated_cache, monkeypatch):
    """The other half — the short circuit must not swallow the real path."""
    # T32 / S1: the fake bar sits at the injected clock's current-bar open,
    # so the newest bar is current and the status stays `ok` (not `stale`).
    now = pd.Timestamp("2026-10-03T14:10:00Z")
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: now)
    monkeypatch.setitem(globals(), "_BAR", [int(now.floor("D").timestamp() * 1000), 1.0, 2.0, 0.5, 1.5, 100.0])
    exch = _CountingExchange()
    result = ccxt_adapter.fetch_ohlcv("BTC", "1d", exchange=exch)

    assert exch.touches > 0, "a cold cache must still fetch"
    assert result.status == "ok"


def test_weekly_derivation_from_a_fresh_daily_cache_needs_no_exchange(isolated_cache):
    """`1w` recurses into `1d`; if that leg is warm, nothing in the weekly
    path needs a market list. `_source_label` must then fall back to the
    source recorded on the daily bars rather than labelling it "unknown"."""
    cache.write_ohlcv("BTC", "1d", _fresh_daily(bars=30))

    result = ccxt_adapter.fetch_ohlcv("BTC", "1w")

    assert result.status == "ok"
    assert not result.df.empty
    assert result.df["source"].unique().tolist() == ["fixture"]
