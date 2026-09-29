"""Shared fixtures for the deployability (P2 Phase 1) tests.

Two hard rules from the plan's Validate Contract (P2, E1, E2):

* No test in this package may reach the network. `offline_providers` stubs
  every provider entry point a screen endpoint can reach (ccxt, CoinGecko,
  pytrends, Reddit, FRED, DefiLlama, Farside) with that adapter's own
  "source failed" result shape, and a socket guard fails loudly on any
  non-loopback connect that slips past the stubs.
* No test may touch the real `api/data/cache/` or `api/data/watchlist.json`.
  `_real_data_snapshot` records their listing (path, size, mtime) when the
  package starts; `test_zz_real_data_guard.py` and this fixture's teardown
  both compare against it.
"""
from __future__ import annotations

import socket
from pathlib import Path

import pandas as pd
import pytest

from api.data import (
    cache,
    ccxt_adapter,
    coingecko_adapter,
    defillama_adapter,
    etf_flows_adapter,
    fred_adapter,
    pytrends_adapter,
    reddit_adapter,
)
from api.data import watchlist as watchlist_store

API_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
REAL_CACHE_DIR = API_DATA_DIR / "cache"
REAL_WATCHLIST = API_DATA_DIR / "watchlist.json"

# Captured at import of this conftest — before any test in the package runs
# and before any module reload can move the attributes.
ORIGINAL_CACHE_ROOT = cache.CACHE_ROOT
ORIGINAL_WATCHLIST_PATH = watchlist_store.DEFAULT_WATCHLIST_PATH


def snapshot_real_data() -> dict[str, tuple[int, int]]:
    """(size, mtime_ns) for every file under the real cache dir plus the real
    watchlist. Missing paths simply contribute nothing."""
    listing: dict[str, tuple[int, int]] = {}
    if REAL_CACHE_DIR.exists():
        for p in REAL_CACHE_DIR.rglob("*"):
            if p.is_file():
                st = p.stat()
                listing[str(p)] = (st.st_size, st.st_mtime_ns)
    if REAL_WATCHLIST.exists():
        st = REAL_WATCHLIST.stat()
        listing[str(REAL_WATCHLIST)] = (st.st_size, st.st_mtime_ns)
    return listing


REAL_DATA_AT_START = snapshot_real_data()


@pytest.fixture(scope="package", autouse=True)
def _real_data_snapshot():
    yield REAL_DATA_AT_START
    assert snapshot_real_data() == REAL_DATA_AT_START, (
        "a deploy test modified the real api/data/cache or api/data/watchlist.json"
    )


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Safety net behind the explicit stubs: any non-loopback TCP connect
    fails immediately instead of hanging on the container's egress proxy."""
    real_connect = socket.socket.connect

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and (host.startswith("127.") or host in ("localhost", "::1") or host.startswith("/")):
            return real_connect(self, address)
        raise RuntimeError(f"deploy tests must stay offline; attempted connect to {address!r}")

    monkeypatch.setattr(socket.socket, "connect", guarded)


class _DeadExchange:
    """ccxt Hyperliquid stand-in whose market list never loads, so
    `ccxt_adapter._exchange()` returns None and every OHLCV call serves
    whatever is cached with status `unavailable` — the real outage path."""

    id = "hyperliquid"
    markets: dict = {}

    def load_markets(self):
        import ccxt

        raise ccxt.NetworkError("offline test: exchange unreachable")


def _fred_offline(series_id, client=None):
    cached = cache.read_liquidity_series(series_id)
    if cached is None or cached.empty:
        return fred_adapter.FredSeriesResult(series_id=series_id, df=pd.DataFrame(columns=["date", "value"]), status="unavailable")
    return fred_adapter.FredSeriesResult(series_id=series_id, df=cached, status="stale")


@pytest.fixture
def offline_providers(monkeypatch):
    """Every provider entry point reachable from a screen endpoint, stubbed to
    the adapter's own failure shape (E1). Cached data, if a test seeded any,
    is served exactly as the real adapter serves it after a failed refresh."""
    monkeypatch.setattr(ccxt_adapter.ccxt, "hyperliquid", lambda *a, **k: _DeadExchange())
    ccxt_adapter.reset_exchange_cache()

    monkeypatch.setattr(
        coingecko_adapter, "fetch_trending",
        lambda client=None: coingecko_adapter.TrendingResult(symbols=[], as_of=None, status="unavailable"),
    )
    monkeypatch.setattr(
        pytrends_adapter, "fetch_trend",
        lambda keyword: pytrends_adapter.TrendResult(keyword=keyword, value=None, as_of=None, status="unavailable"),
    )
    monkeypatch.setattr(
        reddit_adapter, "fetch_mentions",
        lambda query, *a, **k: reddit_adapter.MentionResult(query=query, mention_count=None, as_of=None, status="unavailable"),
    )
    monkeypatch.setattr(fred_adapter, "fetch_series", _fred_offline)
    monkeypatch.setattr(
        fred_adapter, "fetch_net_liquidity",
        lambda client=None: fred_adapter.FredSeriesResult(series_id="NET_LIQUIDITY", df=pd.DataFrame(columns=["date", "value"]), status="unavailable"),
    )
    monkeypatch.setattr(
        defillama_adapter, "fetch_stablecoin_supply",
        lambda client=None: defillama_adapter.StablecoinSupplyResult(df=pd.DataFrame(columns=["date", "value"]), status="unavailable"),
    )
    monkeypatch.setattr(
        etf_flows_adapter, "fetch_btc_spot_flows",
        lambda client=None, force=False: etf_flows_adapter.EtfFlowsResult(
            df=pd.DataFrame(columns=["date", "net_flow_usd_m"]), status="unavailable", reason="offline test"
        ),
    )
    yield
    ccxt_adapter.reset_exchange_cache()


@pytest.fixture
def temp_watchlist(tmp_path, monkeypatch):
    """Point the watchlist store at a temp file BEFORE any client is built
    (the api/tests/routers/test_watchlist.py pattern)."""
    wl = tmp_path / "watchlist.json"
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", wl)
    return wl
