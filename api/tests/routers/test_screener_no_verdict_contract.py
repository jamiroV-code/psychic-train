"""T36 / S4: the screener carries no verdict.

No confidence badge, signal detail, momentum, trend, scalp reading,
benchmark label, leg context or narrative state in the screener payloads or
in their TypeScript mirror; `/scalp` is gone and `/chart` serves the
drill-down. This file and `web/lib/__tests__/screener-api.test.ts` are the
only places allowed to name the removed symbols (the symbol-gate carve-out).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from api.analytics import screener_board
from api.analytics.narrative import trigger as narrative_trigger
from api.analytics.regime import leg_boundary
from api.data import ccxt_adapter
from api.data import watchlist as watchlist_store
from api.data.ccxt_adapter import OhlcvResult
from api.models import screener as screener_models
from api.models.screener import TIMEFRAMES, CoinPanel, ScreenerBoardResponse

_TS_PATH = Path(__file__).resolve().parents[3] / "web" / "lib" / "types" / "screener.ts"

VERDICT_PANEL_FIELDS = {"momentum", "trend", "confidence", "leg_context", "narrative_state"}
VERDICT_TS_NAMES = (
    "MomentumState", "TrendState", "ConfidenceState", "BenchmarkSelection", "ScalpView",
    "ScalpMomentumState", "LegContextLiteral", "NarrativeStateLiteral", "LegBoundary",
    "LegBoundaryResponse", "LiquidityCompositeVariant", "NarrativeCategory", "SourceAvailability",
    "active_benchmark", "scalp_momentum", "leg_context", "narrative_state", "confidence",
)

NOW = pd.Timestamp("2026-10-03T14:10:00Z")
FETCHED = pd.Timestamp("2026-10-03T14:08:30Z")
_FREQ = {"15m": "15min", "1h": "h", "4h": "4h", "1d": "D", "1w": "W-MON"}
_LAST = {
    "15m": "2026-10-03T14:00:00Z",
    "1h": "2026-10-03T14:00:00Z",
    "4h": "2026-10-03T12:00:00Z",
    "1d": "2026-10-03T00:00:00Z",
    "1w": "2026-09-28T00:00:00Z",
}


def _df(tf: str, end: str, n: int = 90) -> pd.DataFrame:
    idx = pd.date_range(end=pd.Timestamp(end), periods=n, freq=_FREQ[tf], tz="UTC")
    closes = [100.0 + i for i in range(n)]
    return pd.DataFrame({
        "timestamp": idx, "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": 1.0, "source": "fixture",
    })


def _install(monkeypatch, frames: dict[str, pd.DataFrame]) -> None:
    def fake_fetch(symbol, timeframe, since=None, limit=None, exchange=None):
        df = frames.get(timeframe, pd.DataFrame())
        return OhlcvResult(symbol, timeframe, df, len(df) < 60, "ok" if not df.empty else "unavailable",
                           fetched_at=FETCHED if not df.empty else None)

    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake_fetch)
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: NOW, raising=False)
    monkeypatch.setattr(ccxt_adapter, "last_clock_skew", lambda: None, raising=False)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC", "ETH"])


def _fresh_frames() -> dict[str, pd.DataFrame]:
    return {tf: _df(tf, end) for tf, end in _LAST.items()}


def test_coin_panel_has_no_verdict_fields(monkeypatch):
    assert not VERDICT_PANEL_FIELDS & set(CoinPanel.model_fields)
    _install(monkeypatch, _fresh_frames())
    payload = screener_board.build_coin_panel("BTC", "1d", now=NOW).model_dump()
    assert set(payload) == {"symbol", "chart", "percent_change_by_timeframe", "gain_by_timeframe", "rsi"}
    for name in ("ScalpView", "ScalpMomentumState"):
        assert not hasattr(screener_models, name), name
    assert hasattr(screener_models, "ChartView")


def test_board_response_has_no_active_benchmark_and_keeps_freshness_fields(monkeypatch):
    assert "active_benchmark" not in ScreenerBoardResponse.model_fields
    _install(monkeypatch, _fresh_frames())
    body = screener_board.build_screener_board("1d").model_dump()
    assert "active_benchmark" not in body
    assert body["server_time"] == "2026-10-03T14:10:00Z"
    assert body["clock_skew_seconds"] is None
    assert body["clock_skew_warning"] is False
    assert [c["symbol"] for c in body["coins"]] == ["BTC", "ETH"]
    for coin in body["coins"]:
        assert not VERDICT_PANEL_FIELDS & set(coin)
        assert coin["chart"]["last_bar_ts"] == "2026-10-03T00:00:00Z"


def test_scalp_route_is_gone_and_chart_route_serves_the_drill_down(monkeypatch):
    testclient = pytest.importorskip("fastapi.testclient")
    from api.main import app

    _install(monkeypatch, _fresh_frames())
    client = testclient.TestClient(app)

    assert client.get("/api/screener/BTC/scalp", params={"timeframe": "4h"}).status_code == 404

    resp = client.get("/api/screener/BTC/chart")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"symbol", "timeframe", "chart"}
    assert body["symbol"] == "BTC"
    assert body["timeframe"] == "4h"  # the drill-down's default interval
    assert body["chart"]["available"] is True
    assert body["chart"]["price"] and body["chart"]["sma"]

    assert client.get("/api/screener/BTC/chart", params={"timeframe": "1h"}).json()["timeframe"] == "1h"


def test_chart_view_carries_freshness_fields_for_every_timeframe(monkeypatch):
    _install(monkeypatch, _fresh_frames())
    for tf in TIMEFRAMES:
        view = screener_board.build_chart_view("BTC", tf)
        assert view.timeframe == tf
        chart = view.chart
        assert chart.available is True, tf
        assert chart.last_bar_ts == _LAST[tf], tf
        assert chart.fetched_at == "2026-10-03T14:08:30Z", tf
        assert chart.server_time == "2026-10-03T14:10:00Z", tf
        assert chart.is_partial is not None, tf
        assert chart.stale is False, tf

    # 1w is judged on its daily bar: a fresh weekly bar over an aged daily
    # leg is stale.
    aged = _fresh_frames()
    aged["1d"] = _df("1d", "2026-09-03T00:00:00Z")
    _install(monkeypatch, aged)
    assert screener_board.build_chart_view("BTC", "1w").chart.stale is True

    # An unavailable chart carries nulls and stale=False.
    _install(monkeypatch, {})
    empty = screener_board.build_chart_view("BTC", "4h").chart
    assert empty.available is False
    assert (empty.last_bar_ts, empty.fetched_at, empty.is_partial, empty.server_time) == (None,) * 4
    assert empty.stale is False


def test_board_build_makes_no_leg_boundary_or_narrative_call(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the screener board must not read leg or narrative state")

    monkeypatch.setattr(leg_boundary, "compute_current_leg_state", boom)
    monkeypatch.setattr(narrative_trigger, "assemble_narrative_categories", boom)
    if hasattr(screener_board, "leg_boundary"):
        monkeypatch.setattr(screener_board.leg_boundary, "compute_current_leg_state", boom)
    if hasattr(screener_board, "narrative_trigger"):
        monkeypatch.setattr(screener_board.narrative_trigger, "assemble_narrative_categories", boom)
    _install(monkeypatch, _fresh_frames())

    board = screener_board.build_screener_board("1d")
    assert len(board.coins) == 2


def _ts_interface(src: str, name: str) -> set[str]:
    match = re.search(r"export interface " + name + r"\s*\{(.*?)\n\}", src, re.S)
    assert match, f"interface {name} not found in screener.ts"
    return {m.group(1) for line in match.group(1).splitlines() if (m := re.match(r"\s*(\w+)\??:", line))}


def test_typescript_mirror_has_no_verdict_names_and_declares_chart_view():
    src = _TS_PATH.read_text(encoding="utf-8")
    code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("//"))
    for name in VERDICT_TS_NAMES:
        assert not re.search(r"\b" + name + r"\b", code), f"screener.ts still declares {name}"
    assert _ts_interface(src, "ChartView") == set(screener_models.ChartView.model_fields)
    assert _ts_interface(src, "CoinPanel") == set(CoinPanel.model_fields)
    assert _ts_interface(src, "ScreenerBoardResponse") == set(ScreenerBoardResponse.model_fields)
