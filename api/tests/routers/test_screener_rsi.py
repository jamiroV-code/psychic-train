"""T40 / S5a (C6): RSI numbers on board panels and the drill-down chart,
checked against an independent loop-based Wilder RSI on non-monotone
closes, plus the `screener.ts` mirror.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd
import pytest

from api.analytics import screener_board
from api.analytics.indicators import sma as sma_mod
from api.data import ccxt_adapter
from api.data import watchlist as watchlist_store
from api.data.ccxt_adapter import OhlcvResult
from api.models.screener import CoinPanel, RsiPoint, RsiReading

_TS_PATH = Path(__file__).resolve().parents[3] / "web" / "lib" / "types" / "screener.ts"
NOW = pd.Timestamp("2026-10-03T14:10:00Z")
_FREQ = {"15m": "15min", "1h": "h", "4h": "4h", "1d": "D", "1w": "7D"}


@pytest.fixture(autouse=True)
def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.delenv("SCREENER_LAYOUT_PATH", raising=False)


def wilder_rsi(closes: list[float], length: int = 14) -> float | None:
    gains = [max(b - a, 0.0) for a, b in zip(closes, closes[1:])]
    losses = [max(a - b, 0.0) for a, b in zip(closes, closes[1:])]
    if len(gains) < length:
        return None
    avg_gain = sum(gains[:length]) / length
    avg_loss = sum(losses[:length]) / length
    for g, l in zip(gains[length:], losses[length:]):
        avg_gain = (avg_gain * (length - 1) + g) / length
        avg_loss = (avg_loss * (length - 1) + l) / length
    if avg_gain == 0 and avg_loss == 0:
        return None
    return 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def _closes(n: int, phase: float) -> list[float]:
    return [100.0 + 10.0 * math.sin(i / 3.0 + phase) + 0.15 * i for i in range(n)]


def _df(tf: str, closes: list[float]) -> pd.DataFrame:
    end = NOW.floor("D")
    stamps = pd.date_range(end=end, periods=len(closes), freq=_FREQ[tf])
    return pd.DataFrame({
        "timestamp": stamps, "open": closes, "high": closes, "low": closes,
        "close": closes, "volume": [1.0] * len(closes), "source": "test",
    })


def _install(monkeypatch, frames: dict[str, pd.DataFrame], statuses: dict[str, str] | None = None):
    statuses = statuses or {}

    def fetch(symbol, timeframe, since=None, limit=None, exchange=None):
        df = frames.get(timeframe, pd.DataFrame())
        status = statuses.get(timeframe, "ok" if not df.empty else "unavailable")
        return OhlcvResult(symbol, timeframe, df, len(df) < 60, status)

    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fetch)
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: NOW, raising=False)
    monkeypatch.setattr(ccxt_adapter, "last_clock_skew", lambda: None, raising=False)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC"])


def _frames() -> dict[str, list[float]]:
    return {tf: _closes(80 + 7 * i, phase=i) for i, tf in enumerate(("15m", "1h", "4h", "1d", "1w"))}


def _install_all(monkeypatch):
    closes = _frames()
    _install(monkeypatch, {tf: _df(tf, c) for tf, c in closes.items()})
    return closes


def test_board_rsi_equals_wilder_reference(monkeypatch):
    closes = _install_all(monkeypatch)
    panel = screener_board.build_screener_board("1d").coins[0]
    assert panel.rsi.length == 14 and panel.rsi.reason is None
    assert panel.rsi.value == pytest.approx(wilder_rsi(closes["1d"]), abs=1e-9)
    assert 0 < panel.rsi.value < 100


def test_each_timeframe_gets_its_own_value(monkeypatch):
    closes = _install_all(monkeypatch)
    values = {}
    for tf in ("15m", "1h", "4h", "1d", "1w"):
        reading = screener_board.build_coin_panel("BTC", tf, now=NOW).rsi
        assert reading.value == pytest.approx(wilder_rsi(closes[tf]), abs=1e-9), tf
        values[tf] = round(reading.value, 6)
    assert len(set(values.values())) == 5


def test_short_history_and_failed_sources_give_null_with_reason(monkeypatch):
    frames = {"1d": _df("1d", _closes(30, 0)), "4h": pd.DataFrame(), "1h": pd.DataFrame()}
    _install(monkeypatch, frames, statuses={"4h": "unavailable", "1h": "bad_symbol"})
    expected = {"1d": "insufficient-history", "4h": "source-unavailable", "1h": "bad-symbol"}
    for tf, reason in expected.items():
        reading = screener_board.build_coin_panel("BTC", tf, now=NOW).rsi
        assert reading.value is None and reading.reason == reason, tf
    payload = screener_board.build_screener_board("1d").model_dump_json()
    assert "NaN" not in payload and "Infinity" not in payload


def test_flat_window_gives_flat_price(monkeypatch):
    _install(monkeypatch, {"1d": _df("1d", [42.0] * 70)})
    reading = screener_board.build_coin_panel("BTC", "1d", now=NOW).rsi
    assert reading.value is None and reading.reason == "flat-price"
    assert reading.as_of == "2026-10-03T00:00:00Z"
    assert screener_board.build_chart_view("BTC", "1d").chart.rsi == []


def test_as_of_is_last_bar_in_z(monkeypatch):
    _install_all(monkeypatch)
    for tf in ("15m", "1d", "1w"):
        reading = screener_board.build_coin_panel("BTC", tf, now=NOW).rsi
        assert reading.as_of == "2026-10-03T00:00:00Z", tf


def test_chart_view_carries_rsi_series_and_board_charts_do_not(monkeypatch):
    closes = _install_all(monkeypatch)
    view = screener_board.build_chart_view("BTC", "4h")
    assert len(view.chart.rsi) == len(closes["4h"]) - 14
    assert screener_board.build_screener_board("4h").coins[0].chart.rsi == []
    assert view.model_dump()["chart"]["rsi"][0].keys() == {"timestamp", "value"}


def test_series_points_are_z_and_last_point_equals_reading(monkeypatch):
    _install_all(monkeypatch)
    for tf in ("1h", "1w"):
        series = screener_board.build_chart_view("BTC", tf).chart.rsi
        assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", p.timestamp) for p in series)
        reading = screener_board.build_coin_panel("BTC", tf, now=NOW).rsi
        assert series[-1].value == reading.value and series[-1].timestamp == reading.as_of


def test_sixty_bar_rule_matches_chart(monkeypatch):
    assert sma_mod.SMA_LENGTH == 60
    for n, available in ((59, False), (60, True)):
        _install(monkeypatch, {"1d": _df("1d", _closes(n, 0))})
        panel = screener_board.build_coin_panel("BTC", "1d", now=NOW)
        assert panel.chart.available is available
        assert (panel.rsi.value is not None) is available, n
        assert (panel.rsi.reason is None) is available, n
        chart = screener_board.build_chart_view("BTC", "1d").chart
        assert bool(chart.rsi) is available, n


def _ts_interface(source: str, name: str) -> dict[str, str]:
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.S)
    assert match is not None, name
    return dict(re.findall(r"^\s*(\w+\??):\s*([^;]+);", match.group(1), re.M))


def test_rsi_models_match_typescript():
    source = _TS_PATH.read_text()
    assert _ts_interface(source, "RsiReading") == {
        "value": "number | null", "length": "number", "as_of": "string | null", "reason": "RsiReason | null",
    }
    assert set(RsiReading.model_fields) == {"value", "length", "as_of", "reason"}
    assert RsiReading().model_dump() == {"value": None, "length": 14, "as_of": None, "reason": None}
    assert _ts_interface(source, "RsiPoint") == {"timestamp": "string", "value": "number"}
    assert set(RsiPoint.model_fields) == {"timestamp", "value"}
    reasons = re.search(r"export type RsiReason = ([^;]+);", source).group(1)
    py_reasons = RsiReading.model_fields["reason"].annotation.__args__[0].__args__
    assert reasons == " | ".join(f'"{r}"' for r in py_reasons)
    assert _ts_interface(source, "CoinPanel")["rsi"] == "RsiReading"
    assert _ts_interface(source, "ChartSeries")["rsi"] == "RsiPoint[]"
    assert "rsi" in CoinPanel.model_fields
