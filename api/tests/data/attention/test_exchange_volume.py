"""Exchange volume sources on fixtures: no live call."""
from datetime import datetime, timedelta, timezone

import ccxt

from api.data.attention import exchange_volume, registry
from api.data.hyperliquid_narrative_adapter import ExchangeSnapshotResult, PerpMarket
from .conftest import TODAY


def _ms(d):
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def _bars(days, include_today=True):
    last = TODAY if include_today else TODAY - timedelta(days=1)
    return [[_ms(last - timedelta(days=days - 1 - i)), 1, 1, 1, 2.0, 10.0 + i] for i in range(days)]


class FakeEx:
    def __init__(self, bars=None, exc=None, tickers=None):
        self.bars, self.exc, self.tickers, self.calls = bars, exc, tickers, []

    def fetch_ohlcv(self, symbol, timeframe, limit=None):
        self.calls.append((symbol, timeframe))
        if self.exc:
            raise self.exc
        return self.bars


def test_binance_ok_quote_volume_and_today_dropped():
    ex = FakeEx(_bars(100))
    s = exchange_volume.fetch_binance_series("btc", exchange=ex, today=TODAY)
    assert s.state == "ok" and s.source == "exchange_volume" and s.symbol == "BTC"
    assert ex.calls == [("BTC/USDT", "1d")]
    assert len(s.points) == 99 and all(d < TODAY for d, _ in s.points)
    assert s.points[0][1] == 2.0 * 11.0  # close * base volume


def test_binance_empty():
    s = exchange_volume.fetch_binance_series("BTC", exchange=FakeEx([]), today=TODAY)
    assert s.state == "unavailable" and s.reason == "empty response"


def test_binance_short_history():
    s = exchange_volume.fetch_binance_series("BTC", exchange=FakeEx(_bars(30, False)), today=TODAY)
    assert s.state == "insufficient-history" and len(s.points) == 30


def test_binance_http_error_never_raises():
    s = exchange_volume.fetch_binance_series("BTC", exchange=FakeEx(exc=ccxt.NetworkError("x")), today=TODAY)
    assert s.state == "unavailable" and "NetworkError" in s.reason


def test_binance_rate_limit():
    s = exchange_volume.fetch_binance_series("BTC", exchange=FakeEx(exc=ccxt.RateLimitExceeded("x")), today=TODAY)
    assert s.state == "unavailable" and s.reason == "rate-limited"


def test_binance_bad_symbol_has_no_secret_in_reason():
    s = exchange_volume.fetch_binance_series("BTC", exchange=FakeEx(exc=ValueError("key=abc")), today=TODAY)
    assert "abc" not in s.reason and s.reason == "fetch-failed: ValueError"


def _snap(perps, status="ok"):
    return lambda exchange=None, now=None: ExchangeSnapshotResult(status=status, as_of="2026-10-16", perps=perps,
                                                                   reason=None if status == "ok" else "x")


def test_hyperliquid_forward_single_point():
    snap = _snap([PerpMarket("BTC", "BTC", 5e9), PerpMarket("KPEPE", "kPEPE", 1e6)])
    s = exchange_volume.fetch_hyperliquid_series("btc", exchange=object(), today=TODAY, snapshot=snap)
    assert s.source == "hyperliquid_volume" and s.state == "insufficient-history"
    assert s.points == [(TODAY - timedelta(days=1), 5e9)]


def test_hyperliquid_missing_symbol_or_volume():
    snap = _snap([PerpMarket("ETH", "ETH", None)])
    for sym in ("ETH", "BTC"):
        s = exchange_volume.fetch_hyperliquid_series(sym, exchange=object(), today=TODAY, snapshot=snap)
        assert s.state == "unavailable" and s.points == []


def test_hyperliquid_snapshot_unavailable():
    s = exchange_volume.fetch_hyperliquid_series("BTC", exchange=object(), today=TODAY,
                                                 snapshot=_snap([], "unavailable"))
    assert s.state == "unavailable"


def test_registered_and_not_probed_without_record(tmp_path):
    assert {"exchange_volume", "hyperliquid_volume"} <= set(registry.FETCHERS)
    p = tmp_path / "p.json"
    p.write_text("{}")
    for src in ("exchange_volume", "hyperliquid_volume"):
        assert registry.read_series(src, "BTC", today=TODAY, probe_path=p).state == "not-probed"
