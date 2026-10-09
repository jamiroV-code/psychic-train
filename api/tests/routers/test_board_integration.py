"""RFC-005 item 14a/14b — the automated gate AC-2 was missing.

Before this file, AC-2 ("the board returns real prices end-to-end") rested
solely on a human clicking around. VALIDATE's vacuous-green ban (V3 Net Gate
Rule) forbids a terminal PASS where developed behavior has no Fully-Automated
or Hybrid gate, which is what sent RFC-005 back for a PVL supplement cycle.

Two gates live here:
  * default   — TestClient + stubbed markets/OHLCV. No network. Proves the
                wiring from router through analytics to response model.
  * integration — same assertions against the real exchange. Opt-in via
                `-m integration`, because it needs network and a live market
                list. This is the real-contract pin whose absence allowed
                parent-plan deviations #8, #9 and #13 through.
"""
from __future__ import annotations

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")
TestClient = fastapi_testclient.TestClient

from api.data import ccxt_adapter  # noqa: E402
from api.data import watchlist as watchlist_store  # noqa: E402
from api.main import app  # noqa: E402

TICKERS = ("BTC", "ETH", "HYPE", "SOL")
MARKETS = {
    f"{t}/USDC:USDC": {"swap": True, "spot": False, "base": t, "baseName": t, "active": True}
    for t in TICKERS
}

# 90 daily bars — comfortably past MIN_BARS_REQUIRED (60) and SMA_LENGTH, so
# `available` is True for real reasons rather than by luck.
_DAY_MS = 24 * 60 * 60 * 1000
_START = 1_700_000_000_000
BARS = [
    [_START + i * _DAY_MS, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000.0]
    for i in range(90)
]


class StubExchange:
    id = "hyperliquid"

    def __init__(self):
        self.markets = MARKETS

    def load_markets(self):
        return self.markets

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        assert symbol in self.markets, f"unified symbol expected, got {symbol!r}"
        return BARS


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(ccxt_adapter.cache, "CACHE_ROOT", tmp_path)
    monkeypatch.setattr(ccxt_adapter.ccxt, "hyperliquid", lambda *a, **k: StubExchange())
    ccxt_adapter.reset_exchange_cache()
    # The real api/data/watchlist.json is gitignored user data (absent on a
    # fresh checkout), so isolate and seed it like the price cache above —
    # tests/all-tests.md Standing Lessons #3/#7.
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    for t in TICKERS:
        watchlist_store.add_coin(t)
    yield TestClient(app)
    ccxt_adapter.reset_exchange_cache()


def test_board_returns_populated_chart_series(client):
    """AC-2, Fully-Automated."""
    resp = client.get("/api/screener/board", params={"timeframe": "1d"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["coins"]) >= 1

    populated = [c for c in body["coins"] if c["chart"]["available"]]
    assert populated, f"no coin had an available chart: {body['coins']}"
    for coin in populated:
        assert len(coin["chart"]["price"]) > 0
        assert coin["chart"]["reason"] is None


def test_unavailable_chart_states_its_reason(client, monkeypatch):
    """RFC-005's other half: a failure must say which failure it was."""
    import ccxt

    class Dead(StubExchange):
        def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
            raise ccxt.NetworkError("simulated outage")

    monkeypatch.setattr(ccxt_adapter.ccxt, "hyperliquid", lambda *a, **k: Dead())
    ccxt_adapter.reset_exchange_cache()

    body = client.get("/api/screener/board", params={"timeframe": "1d"}).json()
    for coin in body["coins"]:
        assert coin["chart"]["available"] is False
        assert coin["chart"]["reason"] == "source-unavailable", (
            "a dead data source must not report itself as insufficient history"
        )


def test_chart_view_populated(client):
    body = client.get("/api/screener/BTC/chart", params={"timeframe": "4h"}).json()
    assert body["symbol"] == "BTC"
    assert body["chart"]["available"] is True
    assert len(body["chart"]["price"]) > 0


def test_spaghetti_populated(client):
    body = client.get("/api/screener/spaghetti", params={"timeframe": "1d"}).json()
    available = [s for s in body["series"] if s["available"]]
    assert available, f"no series available: {body['series']}"
    assert len(available[0]["points"]) > 0


@pytest.mark.integration
def test_board_against_real_exchange():
    """AC-1/AC-2, Hybrid. Opt-in: `uv run --project api pytest api/ -m integration`.

    Deselected by default — needs network and a live Hyperliquid market list.
    This is the gate that would have caught deviations #8, #9 and #13 at
    write time instead of at first live run.
    """
    ccxt_adapter.reset_exchange_cache()
    try:
        client = TestClient(app)
        resp = client.get("/api/screener/board", params={"timeframe": "1d"})
        assert resp.status_code == 200
        coins = resp.json()["coins"]
        assert coins, "watchlist produced no coins"
        reasons = {c["chart"].get("reason") for c in coins}
        assert "bad-symbol" not in reasons, (
            f"a watchlist ticker failed to resolve against the real market list: {reasons}"
        )
    finally:
        ccxt_adapter.reset_exchange_cache()
