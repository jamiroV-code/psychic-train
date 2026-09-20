"""Screener board assembly tests (items 21, 29h, 29j, 29l).

SANDBOX NOTE: `fastapi` could not be installed in this sandbox (see EXECUTE
report Deviations), so these exercise `api/analytics/screener_board.py`
directly — the exact same logic `routers/screener.py`'s thin FastAPI
handlers call — rather than going through `fastapi.testclient.TestClient`
as the plan's Verification Evidence command
(`uv run pytest api/tests/routers/test_screener.py::... -v`) implies. Test
names match the plan's exactly; only the HTTP-client layer is bypassed.

RFC-002 note (item 44): `build_screener_board` now calls
`leg_boundary.compute_current_leg_state()`, which — on a real cache miss —
would hit FRED/LiqTide/DefiLlama over the network. These are screener
data-binding tests, not regime tests (those live in `test_leg_boundary.py`/
`test_benchmark.py`/`test_regime.py`), so every fixture here monkeypatches
`compute_current_leg_state` to a fixed, network-free `has_data=False`
state (mirroring RFC-001's own `RegimeState()` stub default — this keeps
these tests' behavior unchanged by RFC-002).

RFC-004 note (items 62/64): `build_screener_board` now additionally calls
`narrative_trigger.assemble_narrative_categories()` once per board build,
which would otherwise hit pytrends/Reddit/CoinGecko over the network on a
cache miss — same cross-RFC coupling shape as the leg-boundary note above.
Every fixture here also monkeypatches `assemble_narrative_categories` to an
empty list (no categories fetched -> every coin's `narrative_state`
resolves to `unavailable` via `badge.derive_narrative_state`, since none of
this file's fixture coins have curated mappings anyway except BTC, whose
mapped category is never a seed category regardless — see
`badge.derive_narrative_state`'s docstring) so these data-binding tests'
existing assertions (about momentum/trend/chart/gain-readout, not about the
confidence badge itself — that's `test_confidence_badge.py`'s job) stay
unaffected by RFC-004.
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.analytics import screener_board
from api.analytics.indicators.trend import SMA_LENGTH
from api.data.ccxt_adapter import OhlcvResult
from api.data import watchlist as watchlist_store
from api.models.regime import CurrentLegState

_NO_LEG_DATA = CurrentLegState(candidate_boundaries=[], confirmed_boundaries=[], composite_variant="reduced", has_data=False)


def _df(closes: list[float], freq: str = "D") -> pd.DataFrame:
    idx = pd.date_range(start="2024-01-01", periods=len(closes), freq=freq, tz="UTC")
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
        "ETH": {tf: _df(_bearish_closes(n, 50.0), freq=_TF_FREQ[tf]) for tf in ("15m", "1h", "4h", "1d", "1w")},
    }
    fake = _FakeAdapter(per_symbol)
    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake.fetch_ohlcv)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["BTC", "ETH"])
    monkeypatch.setattr(screener_board.leg_boundary, "compute_current_leg_state", lambda *a, **k: _NO_LEG_DATA)
    monkeypatch.setattr(screener_board.narrative_trigger, "assemble_narrative_categories", lambda *a, **k: [])
    return fake


def test_screener_board_grid_data_binding(two_coin_fixture):
    board = screener_board.build_screener_board(timeframe="1d")
    assert len(board.coins) == 2
    by_symbol = {p.symbol: p for p in board.coins}

    # AC-5: no cross-contamination — BTC (bullish fixture) passes momentum,
    # ETH (bearish fixture) does not, and each panel's own values reflect
    # its own fixture's trend direction.
    assert by_symbol["BTC"].momentum.state == "PASS"
    assert by_symbol["ETH"].momentum.state == "FAIL"
    assert by_symbol["BTC"].trend.direction == "up"
    assert by_symbol["ETH"].trend.direction == "down"
    assert by_symbol["BTC"].symbol != by_symbol["ETH"].symbol

    # AC-6: SMA present on both panels.
    assert by_symbol["BTC"].trend.sma_value is not None
    assert by_symbol["ETH"].trend.sma_value is not None

    # AC-7: scalp endpoint reachable (drill-down data assembles cleanly).
    scalp = screener_board.build_scalp_view("BTC")
    assert scalp.symbol == "BTC"
    assert scalp.scalp_momentum.state in ("PASS", "FAIL", "insufficient")


def test_board_timeframe_toggle_global_switch(two_coin_fixture):
    """AC-16: same watchlist at two timeframes returns different chart
    series but identical momentum PASS/FAIL.
    """
    board_1d = screener_board.build_screener_board(timeframe="1d")
    board_1h = screener_board.build_screener_board(timeframe="1h")

    btc_1d = next(p for p in board_1d.coins if p.symbol == "BTC")
    btc_1h = next(p for p in board_1h.coins if p.symbol == "BTC")

    assert btc_1d.momentum == btc_1h.momentum  # unaffected by display timeframe
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
    monkeypatch.setattr(screener_board.leg_boundary, "compute_current_leg_state", lambda *a, **k: _NO_LEG_DATA)
    monkeypatch.setattr(screener_board.narrative_trigger, "assemble_narrative_categories", lambda *a, **k: [])

    board = screener_board.build_screener_board(timeframe="15m")
    by_symbol = {p.symbol: p for p in board.coins}

    assert by_symbol["THIN"].chart.available is False
    assert by_symbol["THIN"].chart.price == []
    assert by_symbol["BTC"].chart.available is True  # unaffected by THIN's thinness


def test_drilldown_chart_timeframe_range(two_coin_fixture):
    """AC-18: the drill-down chart honors its own `timeframe` param,
    independent of the board's own toggle; the scalp RSI stays labeled 4h.
    """
    view_1h = screener_board.build_scalp_view("BTC", timeframe="1h")
    view_1d = screener_board.build_scalp_view("BTC", timeframe="1d")

    assert view_1h.timeframe == "1h"
    assert view_1d.timeframe == "1d"
    assert view_1h.scalp_momentum.timeframe == "4h"
    assert view_1d.scalp_momentum.timeframe == "4h"


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
    monkeypatch.setattr(screener_board.leg_boundary, "compute_current_leg_state", lambda *a, **k: _NO_LEG_DATA)
    monkeypatch.setattr(screener_board.narrative_trigger, "assemble_narrative_categories", lambda *a, **k: [])

    board = screener_board.build_screener_board(timeframe="1d")
    btc = board.coins[0]
    assert btc.percent_change_by_timeframe["15m"] is None  # never 0%
    assert btc.percent_change_by_timeframe["1d"] is not None  # other slots unaffected
