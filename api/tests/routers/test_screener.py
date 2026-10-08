"""Screener board assembly tests (items 21, 29h, 29j, 29l).

SANDBOX NOTE: `fastapi` could not be installed in this sandbox (see EXECUTE
report Deviations), so these exercise `api/analytics/screener_board.py`
directly — the exact same logic `routers/screener.py`'s thin FastAPI
handlers call — rather than going through `fastapi.testclient.TestClient`
as the plan's Verification Evidence command
(`uv run pytest api/tests/routers/test_screener.py::... -v`) implies. Test
names match the plan's exactly; only the HTTP-client layer is bypassed.
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.analytics import screener_board
from api.analytics.indicators.trend import SMA_LENGTH
from api.data.ccxt_adapter import OhlcvResult
from api.data import watchlist as watchlist_store


def _df(closes: list[float], freq: str = "D") -> pd.DataFrame:
    idx = pd.date_range(start="2024-01-01", periods=len(closes), freq=freq, tz="UTC")
    # T34 / S2: each bar opens at the previous close, so the current-candle
    # chips (open to latest) read the fixture's direction instead of a flat 0.
    opens = closes[:1] + closes[:-1]
    return pd.DataFrame(
        {
            "timestamp": idx,
            "open": opens,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [100.0] * len(closes),
            "source": "test",
        }
    )


def _bullish_closes(n: int, base: float) -> list[float]:
    # Strictly increasing -> RSI well above midline on both daily & weekly.
    return [base + i * 2.0 for i in range(n)]


def _bearish_closes(n: int, base: float) -> list[float]:
    return [base - i * 2.0 for i in range(n)]


class _FakeAdapter:
    """Per-(symbol, timeframe) synthetic OHLCV, so a data-binding test can
    prove one coin's panel never leaks another coin's values (AC-5).
    """

    def __init__(self, per_symbol: dict[str, dict[str, pd.DataFrame]]):
        self.per_symbol = per_symbol
        self.calls: list[tuple[str, str]] = []

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, exchange=None):
        self.calls.append((symbol, timeframe))
        df = self.per_symbol.get(symbol, {}).get(timeframe, pd.DataFrame())
        return OhlcvResult(
            symbol=symbol,
            timeframe=timeframe,
            df=df,
            insufficient_history=len(df) < 60,
            status="ok" if not df.empty else "unavailable",
        )


_TF_FREQ = {"15m": "15min", "1h": "h", "4h": "4h", "1d": "D", "1w": "W"}


@pytest.fixture
def two_coin_fixture(monkeypatch):
    n = 90
    per_symbol = {
        "BTC": {tf: _df(_bullish_closes(n, 100.0), freq=_TF_FREQ[tf]) for tf in ("15m", "1h", "4h", "1d", "1w")},
        # Base 500 keeps every bearish price positive: a non-positive open is
        # an N/A chip, not a loss (T34 / S2).
        "ETH": {tf: _df(_bearish_closes(n, 500.0), freq=_TF_FREQ[tf]) for tf in ("15m", "1h", "4h", "1d", "1w")},
    }
    fake = _FakeAdapter(per_symbol)
    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake.fetch_ohlcv)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC", "ETH"])
    return fake


def test_screener_board_grid_data_binding(two_coin_fixture):
    board = screener_board.build_screener_board(timeframe="1d")
    assert len(board.coins) == 2
    by_symbol = {p.symbol: p for p in board.coins}

    # AC-5: no cross-contamination — BTC (bullish fixture) and ETH (bearish
    # fixture) each carry their own series.
    assert by_symbol["BTC"].chart.price[-1].close > by_symbol["BTC"].chart.price[0].close
    assert by_symbol["ETH"].chart.price[-1].close < by_symbol["ETH"].chart.price[0].close
    assert by_symbol["BTC"].symbol != by_symbol["ETH"].symbol

    # AC-6: SMA present on both panels.
    assert by_symbol["BTC"].chart.sma
    assert by_symbol["ETH"].chart.sma

    # AC-7: the drill-down chart assembles cleanly.
    view = screener_board.build_chart_view("BTC")
    assert view.symbol == "BTC"
    assert view.timeframe == "4h"
    assert view.chart.available is True
    assert view.chart.price and view.chart.sma
    assert view.chart.last_bar_ts is not None and view.chart.server_time is not None


def test_board_timeframe_toggle_global_switch(two_coin_fixture):
    """AC-16: same watchlist at two timeframes returns different chart
    series.
    """
    board_1d = screener_board.build_screener_board(timeframe="1d")
    board_1h = screener_board.build_screener_board(timeframe="1h")

    btc_1d = next(p for p in board_1d.coins if p.symbol == "BTC")
    btc_1h = next(p for p in board_1h.coins if p.symbol == "BTC")

    # Chart series differ because the two fixtures' timestamps differ (daily
    # vs hourly cadence over the same synthetic index) — the toggle actually
    # changed what's drawn.
    assert btc_1d.chart.price[-1].timestamp != btc_1h.chart.price[-1].timestamp


def test_board_timeframe_toggle_insufficient_history(monkeypatch):
    """AC-19: a coin with too little cached history at the requested
    timeframe returns an unavailable chart for itself only; other coins on
    the same response are unaffected.
    """
    n = 90
    per_symbol = {
        "BTC": {tf: _df(_bullish_closes(n, 100.0)) for tf in ("15m", "1h", "4h", "1d", "1w")},
        "THIN": {
            **{tf: _df(_bullish_closes(n, 10.0)) for tf in ("1h", "4h", "1d", "1w")},
            "15m": _df(_bullish_closes(5, 10.0)),  # too thin at 15m specifically
        },
    }
    fake = _FakeAdapter(per_symbol)
    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake.fetch_ohlcv)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC", "THIN"])

    board = screener_board.build_screener_board(timeframe="15m")
    by_symbol = {p.symbol: p for p in board.coins}

    assert by_symbol["THIN"].chart.available is False
    assert by_symbol["THIN"].chart.price == []
    assert by_symbol["BTC"].chart.available is True  # unaffected by THIN's thinness


def test_drilldown_chart_timeframe_range(two_coin_fixture):
    """AC-18: the drill-down chart honors its own `timeframe` param,
    independent of the board's own toggle.
    """
    view_1h = screener_board.build_chart_view("BTC", timeframe="1h")
    view_1d = screener_board.build_chart_view("BTC", timeframe="1d")

    assert view_1h.timeframe == "1h"
    assert view_1d.timeframe == "1d"
    assert view_1h.chart.price[-1].timestamp != view_1d.chart.price[-1].timestamp


def test_per_coin_multi_timeframe_gain_readout(two_coin_fixture):
    """AC-20: every coin's panel includes a complete 5-key dict, correct
    per-coin values, independent of the request's own `timeframe`.
    """
    board = screener_board.build_screener_board(timeframe="1d")
    for panel in board.coins:
        assert set(panel.percent_change_by_timeframe.keys()) == {"15m", "1h", "4h", "1d", "1w"}
    btc = next(p for p in board.coins if p.symbol == "BTC")
    eth = next(p for p in board.coins if p.symbol == "ETH")
    assert btc.percent_change_by_timeframe["1d"] > 0  # bullish fixture
    assert eth.percent_change_by_timeframe["1d"] < 0  # bearish fixture
    # T34 / S2: the chips carry the same value plus their own candle open.
    for panel in board.coins:
        assert set(panel.gain_by_timeframe.keys()) == {"15m", "1h", "4h", "1d", "1w"}
        for tf, chip in panel.gain_by_timeframe.items():
            assert panel.percent_change_by_timeframe[tf] == chip.pct
    assert btc.gain_by_timeframe["1d"].pct > 0
    assert eth.gain_by_timeframe["1d"].pct < 0
    assert btc.gain_by_timeframe["1d"].open_ts.endswith("Z")


def test_per_coin_gain_readout_thin_slot_is_none_not_zero(monkeypatch):
    n = 90
    per_symbol = {
        "BTC": {
            **{tf: _df(_bullish_closes(n, 100.0)) for tf in ("1h", "4h", "1d", "1w")},
            "15m": pd.DataFrame(),  # no cached bars at all for this slot
        },
    }
    fake = _FakeAdapter(per_symbol)
    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake.fetch_ohlcv)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC"])

    board = screener_board.build_screener_board(timeframe="1d")
    btc = board.coins[0]
    assert btc.percent_change_by_timeframe["15m"] is None  # never 0%
    assert btc.percent_change_by_timeframe["1d"] is not None  # other slots unaffected
    # T34 / S2: the thin slot's chip says why (the fake adapter reports an
    # empty frame as `unavailable`).
    assert btc.gain_by_timeframe["15m"].pct is None
    assert btc.gain_by_timeframe["15m"].reason == "source-unavailable"
    assert btc.gain_by_timeframe["1d"].pct is not None
