"""Relative-performance ("spaghetti") chart normalization tests (item 29b,
AC-14/AC-15).

SANDBOX NOTE: exercises `api/analytics/screener_board.build_relative_performance`
directly rather than via `fastapi.testclient.TestClient` — see EXECUTE report
Deviations (fastapi could not be installed in this sandbox).
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.analytics import screener_board
from api.data import watchlist as watchlist_store
from api.data.ccxt_adapter import OhlcvResult


def _df(closes: list[float], start: str = "2024-01-01") -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=len(closes), freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": idx,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [100.0] * len(closes),
            "source": "test",
        }
    )


class _FakeAdapter:
    def __init__(self, per_symbol: dict[str, pd.DataFrame]):
        self.per_symbol = per_symbol

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, exchange=None):
        df = self.per_symbol.get(symbol, pd.DataFrame())
        return OhlcvResult(symbol, timeframe, df, len(df) < 60, "ok" if not df.empty else "unavailable")


def test_relative_performance_chart_normalization_golden_values(monkeypatch):
    # 100 daily bars ending "today"; last 30 days go 100 -> 130 (linear).
    closes = [100.0] * 70 + [100.0 + i for i in range(30)]
    per_symbol = {"BTC": _df(closes)}
    fake = _FakeAdapter(per_symbol)
    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake.fetch_ohlcv)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC"])

    result = screener_board.build_relative_performance(timeframe="30d")
    btc = result.series[0]
    assert btc.available is True
    assert btc.points[0].close == pytest.approx(0.0)  # starts at 0% at the window's first bar
    assert btc.points[-1].close == pytest.approx(29.0)  # (129-100)/100 * 100


def test_relative_performance_timeframe_switch_renormalizes_from_new_window_start(monkeypatch):
    closes = [100.0] * 60 + [100.0 + i for i in range(40)]  # ramps for the last 40 days
    per_symbol = {"BTC": _df(closes)}
    fake = _FakeAdapter(per_symbol)
    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake.fetch_ohlcv)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC"])

    result_7d = screener_board.build_relative_performance(timeframe="7d")
    result_30d = screener_board.build_relative_performance(timeframe="30d")

    # Both renormalize to 0% at THEIR OWN window's start, not the other
    # window's start.
    assert result_7d.series[0].points[0].close == pytest.approx(0.0)
    assert result_30d.series[0].points[0].close == pytest.approx(0.0)
    # And the two windows' start values are genuinely different points in
    # the underlying series (7d starts later / higher than 30d's start).
    assert result_7d.series[0].points[0].timestamp != result_30d.series[0].points[0].timestamp


def test_relative_performance_insufficient_history_for_window_is_per_coin_unavailable(monkeypatch):
    per_symbol = {
        "BTC": _df([100.0 + i for i in range(100)]),  # plenty of history
        "NEWCOIN": _df([10.0, 10.5, 11.0]),  # only 3 bars -> unavailable for a 30d window
    }
    fake = _FakeAdapter(per_symbol)
    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake.fetch_ohlcv)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC", "NEWCOIN"])

    result = screener_board.build_relative_performance(timeframe="30d")
    by_symbol = {s.symbol: s for s in result.series}

    assert by_symbol["NEWCOIN"].available is False
    assert by_symbol["NEWCOIN"].points == []
    # BTC (the other coin on the same response) is unaffected.
    assert by_symbol["BTC"].available is True
    assert len(by_symbol["BTC"].points) > 0
