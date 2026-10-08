"""T32 / S1 — freshness fields on every chart payload and on the board (B5, B6).

`stale` comes from the displayed series' last bar age (1w: from its daily
bar), not from the adapter status, so an aged cache served while the exchange
is down still carries the marker (A1).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from api.analytics import screener_board
from api.data import ccxt_adapter
from api.data import watchlist as watchlist_store
from api.data.ccxt_adapter import OhlcvResult
from api.models.screener import ChartSeries, ScreenerBoardResponse

NOW = pd.Timestamp("2026-10-03T14:10:00Z")
FETCHED = pd.Timestamp("2026-10-03T14:08:30Z")
_FREQ = {"15m": "15min", "1h": "h", "4h": "4h", "1d": "D", "1w": "W-MON"}
_ZFORM = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _df(end: pd.Timestamp, tf: str, n: int = 90) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=n, freq=_FREQ[tf], tz="UTC")
    closes = [100.0 + i for i in range(n)]
    return pd.DataFrame({
        "timestamp": idx, "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": 1.0, "source": "fixture",
    })


def _install(monkeypatch, frames: dict[str, pd.DataFrame], status: str = "ok", skew=None):
    def fake_fetch(symbol, timeframe, since=None, limit=None, exchange=None):
        df = frames.get(timeframe, pd.DataFrame())
        return OhlcvResult(symbol, timeframe, df, len(df) < 60, status if not df.empty else "unavailable",
                           fetched_at=FETCHED if not df.empty else None)

    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake_fetch)
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: NOW, raising=False)
    monkeypatch.setattr(ccxt_adapter, "last_clock_skew", lambda: skew, raising=False)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC"])


def _fresh_frames():
    return {
        "15m": _df(pd.Timestamp("2026-10-03T14:00:00Z"), "15m"),
        "1h": _df(pd.Timestamp("2026-10-03T14:00:00Z"), "1h"),
        "4h": _df(pd.Timestamp("2026-10-03T12:00:00Z"), "4h"),
        "1d": _df(pd.Timestamp("2026-10-03T00:00:00Z"), "1d"),
        "1w": _df(pd.Timestamp("2026-09-28T00:00:00Z"), "1w"),
    }


def test_chart_series_carries_freshness_fields(monkeypatch):
    frames = _fresh_frames()
    _install(monkeypatch, frames)

    chart = screener_board.build_coin_panel("BTC", "1h").chart
    assert chart.available is True
    assert chart.last_bar_ts == "2026-10-03T14:00:00Z"
    assert chart.fetched_at == "2026-10-03T14:08:30Z"
    assert chart.server_time == "2026-10-03T14:10:00Z"
    assert chart.is_partial is True
    assert chart.stale is False
    for value in (chart.last_bar_ts, chart.fetched_at, chart.server_time):
        assert _ZFORM.match(value)

    # 1w: its own bar opened 6 days ago, but staleness is judged on the daily
    # bar (fresh), so it is NOT stale
    weekly = screener_board.build_coin_panel("BTC", "1w").chart
    assert weekly.last_bar_ts == "2026-09-28T00:00:00Z"
    assert weekly.stale is False
    assert weekly.is_partial is True

    # A1: an aged cache served while the exchange is down still carries the
    # marker, whatever the adapter status says
    aged_end = pd.Timestamp("2026-09-03T00:00:00Z")
    aged = {tf: _df(aged_end.floor(_FREQ[tf]) if tf != "1w" else pd.Timestamp("2026-08-31T00:00:00Z"), tf)
            for tf in frames}
    _install(monkeypatch, aged, status="unavailable")
    aged_chart = screener_board.build_coin_panel("BTC", "1d").chart
    assert aged_chart.available is True
    assert aged_chart.stale is True
    assert aged_chart.is_partial is False
    assert aged_chart.last_bar_ts == "2026-09-03T00:00:00Z"
    # 1w with an aged daily leg is stale too
    assert screener_board.build_coin_panel("BTC", "1w").chart.stale is True

    # the drill-down chart view carries the same fields
    _install(monkeypatch, frames)
    view_chart = screener_board.build_chart_view("BTC", "4h").chart
    assert view_chart.last_bar_ts == "2026-10-03T12:00:00Z"
    assert view_chart.server_time == "2026-10-03T14:10:00Z"
    assert view_chart.stale is False


def test_unavailable_chart_has_null_freshness(monkeypatch):
    _install(monkeypatch, {})
    chart = screener_board.build_coin_panel("BTC", "1h").chart
    assert chart.available is False
    assert chart.last_bar_ts is None
    assert chart.fetched_at is None
    assert chart.is_partial is None
    assert chart.server_time is None
    assert chart.stale is False


def test_board_carries_clock_skew_fields(monkeypatch):
    for skew, warning in [(None, False), (6.5, False), (150.0, True), (-150.0, True)]:
        _install(monkeypatch, _fresh_frames(), skew=skew)
        body = screener_board.build_screener_board("1d").model_dump()
        assert body["server_time"] == "2026-10-03T14:10:00Z"
        assert body["clock_skew_seconds"] == skew
        assert body["clock_skew_warning"] is warning


def _ts_interface(name: str) -> dict[str, str]:
    src = (Path(__file__).resolve().parents[3] / "web" / "lib" / "types" / "screener.ts").read_text()
    match = re.search(r"export interface " + name + r"\s*\{(.*?)\n\}", src, re.S)
    assert match, f"interface {name} not found in screener.ts"
    fields = {}
    for line in match.group(1).splitlines():
        m = re.match(r"\s*(\w+)\??:\s*([^;]+);", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


def test_pydantic_fields_match_typescript_interfaces():
    for model, name in [(ChartSeries, "ChartSeries"), (ScreenerBoardResponse, "ScreenerBoardResponse")]:
        _check_interface(model, name)


def _check_interface(model, name):
    ts = _ts_interface(name)
    assert set(ts) == set(model.model_fields), f"{name}: pydantic and TypeScript field names differ"
    for field, info in model.model_fields.items():
        nullable_py = info.default is None and not info.is_required()
        assert ("| null" in ts[field]) == nullable_py, f"{name}.{field}: nullability differs ({ts[field]!r})"
    new = {
        "ChartSeries": {"last_bar_ts": "string | null", "fetched_at": "string | null",
                        "is_partial": "boolean | null", "server_time": "string | null", "stale": "boolean"},
        "ScreenerBoardResponse": {"server_time": "string | null", "clock_skew_seconds": "number | null",
                                  "clock_skew_warning": "boolean"},
    }[name]
    for field, ts_type in new.items():
        assert ts[field] == ts_type
