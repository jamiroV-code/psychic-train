"""Hyperliquid fallback for equities: eligibility, session filtering, source choice, board label. No network."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from api.analytics import equities_board
from api.data import ccxt_adapter, equities_fallback, equities_refresh, lse_adapter
from api.tests import equities_fixtures as fx

MON = date(2026, 10, 12)
NOW = pd.Timestamp("2026-10-12T21:30:00Z")
MARKETS = {
    "XYZ-NVDA/USDC:USDC": {"active": True},
    "XYZ-SP500/USDC:USDC": {"active": True},  # an index perp, not a stock
    "XYZ-DXY/USDC:USDC": {"active": False},  # delisted
    "SPX/USDC:USDC": {"active": True},       # the SPX6900 memecoin, not the S&P 500
}


class FakeExchange:
    id = "hyperliquid"
    markets = MARKETS

    def __init__(self, n_days: int = 150, end: date = MON):
        self.n_days, self.end, self.calls = n_days, end, []

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        self.calls.append(symbol)
        days = [self.end - timedelta(days=k) for k in range(self.n_days - 1, -1, -1)]  # every calendar day
        return [[int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000),
                 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 10.0] for i, d in enumerate(days)]


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(tmp_path / "equities.json"))
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    return tmp_path


def test_refresh_keeps_only_nyse_sessions_and_writes_daily_and_weekly():
    result = equities_fallback.refresh_equity_hl("NVDA", exchange=FakeExchange(), now=NOW)
    assert (result.status, result.source) == ("ok", "hyperliquid")
    days = [ts.date() for ts in result.df["timestamp"]]
    assert days and all(lse_adapter.is_nyse_session(d) for d in days)   # weekends and holidays are dropped
    assert MON in days
    daily, _ = equities_fallback.read_hl_cached("NVDA", "1d", now=NOW)
    weekly, _ = equities_fallback.read_hl_cached("NVDA", "1w", now=NOW)
    assert len(daily.df) == len(days) and not weekly.df.empty
    assert not lse_adapter.equity_parquet_path("NVDA", "1d").exists()    # the LSE cache is never touched


@pytest.mark.parametrize("ticker", ["DXY", "SPX", "ZZZZ", "1BAD"])
def test_only_active_xyz_stock_markets_qualify(ticker):
    ex = FakeExchange()
    result = equities_fallback.refresh_equity_hl(ticker, exchange=ex, now=NOW)
    assert result.status == "bad_symbol" and result.df.empty and ex.calls == []


def test_exchange_failure_is_unavailable_and_never_raises():
    class Down(FakeExchange):
        def fetch_ohlcv(self, *a, **k):
            raise RuntimeError("secret-url")

    result = equities_fallback.refresh_equity_hl("NVDA", exchange=Down(), now=NOW)
    assert (result.status, result.reason) == ("unavailable", "network-error")


# ------------------------------------------------------------- which series is read

def test_lse_is_used_while_its_bars_are_fresh_even_if_hyperliquid_is_cached():
    fx.seed("NVDA", MON, 120)
    equities_fallback.refresh_equity_hl("NVDA", exchange=FakeExchange(), now=NOW)
    result, _ = equities_fallback.read_cached("NVDA", "1d", now=NOW)
    assert result.source == "lse"


def test_hyperliquid_serves_a_ticker_lse_does_not_have():
    equities_fallback.refresh_equity_hl("NVDA", exchange=FakeExchange(), now=NOW)
    result, fetched = equities_fallback.read_cached("NVDA", "1d", now=NOW)
    assert result.source == "hyperliquid" and not result.df.empty and fetched is not None


def test_hyperliquid_replaces_stale_lse_bars_only_when_newer():
    fx.seed("NVDA", date(2026, 9, 1), 120)  # LSE newest bar is six weeks old: stale
    equities_fallback.refresh_equity_hl("NVDA", exchange=FakeExchange(), now=NOW)
    assert equities_fallback.read_cached("NVDA", "1d", now=NOW)[0].source == "hyperliquid"

    # Older Hyperliquid bars than the stale LSE ones never win.
    fx.seed("MU", date(2026, 9, 1), 120)
    # The fake lists only NVDA, so seed MU's Hyperliquid cache by hand.
    lse_adapter._write_cache("MU", "1d", fx.daily_frame(date(2026, 8, 1), 120), NOW, equities_fallback.CACHE_DIR)
    assert equities_fallback.read_cached("MU", "1d", now=NOW)[0].source == "lse"


def test_nothing_cached_anywhere_keeps_the_lse_failure_reason():
    result, _ = equities_fallback.read_cached("NVDA", "1d", now=NOW)
    assert (result.status, result.reason, result.source) == ("unavailable", "no-data", "lse")


# ------------------------------------------------------------- refresh decision

def _lse_result(status, df=None):
    empty = pd.DataFrame(columns=lse_adapter.OHLCV_COLUMNS)
    return lse_adapter.EquityOhlcvResult("NVDA", "1d", empty if df is None else df, status, "no-data")


@pytest.mark.parametrize("status, expected", [("bad_symbol", True), ("unavailable", True), ("stale", True), ("ok", False)])
def test_needs_fallback_only_when_lse_cannot_serve(status, expected):
    df = fx.daily_frame(MON, 10) if status in ("ok", "stale") else None
    assert equities_fallback.needs_fallback(_lse_result(status, df)) is expected


def test_default_fetch_uses_fallback_result_only_when_it_fetched(monkeypatch):
    lse = _lse_result("bad_symbol")
    monkeypatch.setattr(lse_adapter, "refresh_equity", lambda t: lse)
    monkeypatch.setattr(equities_fallback, "refresh_equity_hl",
                        lambda t: equities_fallback._result(t, "1d", fx.daily_frame(MON, 5), "ok", "fetched"))
    assert equities_refresh._default_fetch("NVDA").source == "hyperliquid"
    monkeypatch.setattr(equities_fallback, "refresh_equity_hl",
                        lambda t: equities_fallback._result(t, "1d", lse.df, "bad_symbol", "unknown-ticker"))
    assert equities_refresh._default_fetch("ZZZ") is lse  # a failed fallback reports LSE's own reason


def test_default_fetch_never_calls_the_fallback_when_lse_is_fine(monkeypatch):
    ok = _lse_result("ok", fx.daily_frame(MON, 10))
    monkeypatch.setattr(lse_adapter, "refresh_equity", lambda t: ok)
    monkeypatch.setattr(equities_fallback, "refresh_equity_hl", lambda t: pytest.fail("fallback called"))
    assert equities_refresh._default_fetch("NVDA") is ok


# ------------------------------------------------------------- the page

def test_board_labels_a_fallback_chart_and_leaves_lse_charts_unlabelled(tmp_path):
    (tmp_path / "equities.json").write_text(json.dumps({"tickers": ["NVDA", "AAPL"]}))
    fx.seed("AAPL", MON, 120)
    equities_fallback.refresh_equity_hl("NVDA", exchange=FakeExchange(), now=NOW)
    panels = {p.symbol: p for p in equities_board.build_board("1d", now=NOW).coins}
    assert panels["NVDA"].chart.available and panels["NVDA"].chart.source == "hyperliquid"
    assert panels["AAPL"].chart.available and panels["AAPL"].chart.source is None


# ------------------------------------------------------------- S&P 500 via Hyperliquid, DXY via ECB rates

def test_sp500_index_perp_is_served_like_a_stock():
    result = equities_fallback.refresh_equity_hl("SP500", exchange=FakeExchange(), now=NOW)
    assert (result.status, result.source) == ("ok", "hyperliquid")
    assert equities_fallback.read_cached("SP500", "1d", now=NOW)[0].source == "hyperliquid"


def _rates_payload(days: int = 120):
    out = {}
    for i in range(days):
        day = (pd.Timestamp("2026-06-01") + pd.Timedelta(days=i))
        if day.weekday() < 5:
            out[day.date().isoformat()] = {"EUR": 0.9 + i * 1e-4, "JPY": 150.0, "GBP": 0.75, "CAD": 1.4, "SEK": 9.5, "CHF": 0.82}
    return {"rates": out}


def _frankfurter(payload, status=200):
    import httpx
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=payload)))


def test_dxy_formula_matches_the_published_weights():
    from api.data import equities_dxy
    # With every pair at parity (EURUSD = GBPUSD = 1 and the dollar pairs at 1) the index is its constant.
    parity = {c: 1.0 for c in equities_dxy.CURRENCIES}
    assert equities_dxy.dxy_from_rates(parity) == pytest.approx(50.14348112)
    # Real-world level: late-2026 style rates give an index near 100.
    rates = {"EUR": 0.895, "JPY": 157.25, "GBP": 0.7463, "CAD": 1.3969, "SEK": 9.8264, "CHF": 0.82295}
    assert 100 < equities_dxy.dxy_from_rates(rates) < 104


def test_dxy_is_rebuilt_from_ecb_rates_as_close_only_bars_and_read_back_labelled():
    result = equities_fallback.refresh_synthetic("DXY", now=NOW, client=_frankfurter(_rates_payload()))
    assert (result.status, result.source) == ("ok", "ecb")
    assert (result.df["open"] == result.df["close"]).all() and (result.df["volume"] == 0).all()
    read, fetched = equities_fallback.read_cached("DXY", "1d", now=NOW)
    assert read.source == "ecb" and len(read.df) == len(result.df) and fetched is not None
    assert not equities_fallback.read_cached("DXY", "1w", now=NOW)[0].df.empty


def test_only_dxy_can_be_reconstructed_and_an_outage_is_reported_not_raised():
    assert equities_fallback.refresh_synthetic("AAPL", now=NOW).status == "bad_symbol"
    down = equities_fallback.refresh_synthetic("DXY", now=NOW, client=_frankfurter({}, status=503))
    assert (down.status, down.reason) == ("unavailable", "network-error")


def test_refresh_chain_tries_hyperliquid_then_reconstruction(monkeypatch):
    seen = []
    monkeypatch.setattr(equities_fallback, "refresh_equity_hl",
                        lambda t: equities_fallback._result(t, "1d", pd.DataFrame(columns=lse_adapter.OHLCV_COLUMNS), "bad_symbol", "unknown-ticker"))
    monkeypatch.setattr(equities_fallback, "refresh_synthetic", lambda t: seen.append(t) or "rebuilt")
    assert equities_fallback.refresh_equity_fallback("DXY") == "rebuilt" and seen == ["DXY"]
    assert equities_fallback.refresh_equity_fallback("ZZZ").status == "bad_symbol" and seen == ["DXY"]
