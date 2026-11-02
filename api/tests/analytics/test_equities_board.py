"""S9A: equities board, chart view and spaghetti (cache only, calendar
freshness, closed reasons). Synthetic bars; cache and store redirected."""
from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest

from api.analytics import equities_board
from api.data import equities_store, lse_adapter
from api.tests import equities_fixtures as fx

MON_2130 = pd.Timestamp("2026-10-12T21:30:00Z")
SAT = pd.Timestamp("2026-10-10T12:00:00Z")
FRI = date(2026, 10, 9)
MON = date(2026, 10, 12)


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(tmp_path / "equities.json"))
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    return tmp_path


def _store(tmp_path, tickers):
    (tmp_path / "equities.json").write_text(json.dumps({"tickers": tickers}))


def test_board_order_follows_store(_isolate):
    _store(_isolate, ["MSFT", "AAPL", "KO"])
    for t in ("AAPL", "KO", "MSFT"):
        fx.seed(t, MON, 120)
    board = equities_board.build_board("1d", now=MON_2130)
    assert [p.symbol for p in board.coins] == ["MSFT", "AAPL", "KO"]


def test_panel_has_price_sma_and_rsi():
    equities_store.add_ticker("AAPL")
    fx.seed("AAPL", MON, 120)
    panel = equities_board.build_board("1d", now=MON_2130).coins[0]
    assert panel.chart.available and len(panel.chart.price) == 120
    assert len(panel.chart.sma) == 120 - 59
    assert panel.rsi.value is not None and panel.rsi.as_of == "2026-10-12T00:00:00Z"
    assert panel.chart.rsi == []
    assert panel.daily_data_gap is None
    assert equities_board.build_chart_view("AAPL", "1d", now=MON_2130).daily_data_gap is None
    assert equities_board.build_chart_view("AAPL", "1w", now=MON_2130).daily_data_gap is None


def test_server_time_from_clock_and_skew_fields_null(monkeypatch):
    monkeypatch.setattr(lse_adapter, "_now", lambda: MON_2130)
    board = equities_board.build_board("1w")
    assert board.timeframe == "1w" and board.coins == []
    assert board.server_time == "2026-10-12T21:30:00Z"
    assert board.clock_skew_seconds is None and board.clock_skew_warning is False


def test_reads_never_touch_network_or_refresh(monkeypatch):
    equities_store.add_ticker("AAPL")
    equities_store.add_ticker("MSFT")
    fx.seed("AAPL", MON, 120)
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)

    def boom(*args, **kwargs):
        raise AssertionError("network touched")

    monkeypatch.setattr(lse_adapter.httpx, "Client", boom)
    monkeypatch.setattr(lse_adapter, "refresh_equity", boom)
    monkeypatch.setattr(lse_adapter, "fetch_equity_ohlcv", boom)
    board = equities_board.build_board("1d", now=MON_2130)
    assert [p.chart.available for p in board.coins] == [True, False]
    equities_board.build_chart_view("AAPL", "1w", now=MON_2130)
    equities_board.build_spaghetti("1d", now=MON_2130)


def test_no_file_maps_to_source_unavailable():
    equities_store.add_ticker("NOPE")
    panel = equities_board.build_board("1d", now=MON_2130).coins[0]
    assert panel.chart.available is False and panel.chart.reason == "source-unavailable"
    assert panel.rsi.reason == "source-unavailable"
    assert panel.gain_by_timeframe["1d"].reason == "source-unavailable"


def test_bad_symbol_maps_to_bad_symbol(_isolate):
    _store(_isolate, ["1BAD"])  # a hand-edited file can hold anything
    panel = equities_board.build_board("1d", now=MON_2130).coins[0]
    assert panel.chart.reason == "bad-symbol"
    assert panel.gain_by_timeframe["1w"].reason == "bad-symbol"


def test_short_history_maps_to_insufficient_history():
    equities_store.add_ticker("NEW")
    fx.seed("NEW", MON, 40)
    panel = equities_board.build_board("1d", now=MON_2130).coins[0]
    assert panel.chart.available is False and panel.chart.reason == "insufficient-history"
    assert panel.gain_by_timeframe["1d"].pct is not None  # chips need one bar


def test_chips_exist_for_1d_and_1w_only():
    equities_store.add_ticker("AAPL")
    fx.seed("AAPL", MON, 120)
    panel = equities_board.build_board("1d", now=MON_2130).coins[0]
    assert set(panel.gain_by_timeframe) == {"1d", "1w"}
    assert set(panel.percent_change_by_timeframe) == {"1d", "1w"}


def test_1d_chip_is_newest_daily_bar_open_to_close():
    equities_store.add_ticker("AAPL")
    daily = fx.seed("AAPL", MON, 120)
    chip = equities_board.build_board("1d", now=MON_2130).coins[0].gain_by_timeframe["1d"]
    last = daily.iloc[-1]
    assert chip.pct == pytest.approx((last.close - last.open) / last.open * 100.0)
    assert chip.open_ts == "2026-10-12T00:00:00Z"
    assert chip.is_partial is False and chip.stale is False


def test_1w_chip_in_labor_day_week_is_a_number():
    equities_store.add_ticker("AAPL")
    daily = fx.seed("AAPL", date(2026, 9, 11), 120)
    now = pd.Timestamp("2026-09-11T22:00:00Z")
    chip = equities_board.build_board("1w", now=now).coins[0].gain_by_timeframe["1w"]
    week = daily[daily["timestamp"] >= pd.Timestamp("2026-09-07", tz="UTC")]
    assert week["timestamp"].iloc[0] == pd.Timestamp("2026-09-08", tz="UTC")  # Monday is a holiday
    expected = (week["close"].iloc[-1] - week["open"].iloc[0]) / week["open"].iloc[0] * 100.0
    assert chip.pct == pytest.approx(expected)
    assert chip.open_ts == "2026-09-07T00:00:00Z"
    assert chip.is_partial is False and chip.reason is None


def test_stale_and_partial_come_from_the_calendar():
    equities_store.add_ticker("AAPL")
    fx.seed("AAPL", FRI, 400)
    panel = equities_board.build_board("1d", now=MON_2130).coins[0]
    assert panel.chart.stale is True and panel.chart.is_partial is False
    assert panel.gain_by_timeframe["1d"].stale is True
    weekly = equities_board.build_board("1w", now=pd.Timestamp("2026-10-09T20:30:00Z")).coins[0]
    assert weekly.chart.is_partial is True and weekly.chart.stale is False


def test_weekend_is_never_overdue():
    equities_store.add_ticker("AAPL")
    fx.seed("AAPL", FRI, 120)
    panel = equities_board.build_board("1d", now=SAT).coins[0]
    assert panel.chart.stale is False
    assert panel.chart.server_time == "2026-10-10T12:00:00Z"


def test_chart_view_has_rsi_series_at_its_timeframe():
    fx.seed("AAPL", MON, 500)
    view = equities_board.build_chart_view("aapl", "1w", now=MON_2130)
    assert view.symbol == "AAPL" and view.timeframe == "1w"
    assert view.chart.available and view.chart.rsi
    assert view.chart.stale is False
    missing = equities_board.build_chart_view("NOPE", "1d", now=MON_2130)
    assert missing.chart.available is False and missing.chart.reason == "source-unavailable"


def test_spaghetti_windows_start_at_zero_and_have_no_references():
    equities_store.add_ticker("AAPL")
    equities_store.add_ticker("NOPE")
    fx.seed("AAPL", MON, 500)
    daily = equities_board.build_spaghetti("1d", now=MON_2130)
    assert daily.references == [] and daily.window_cap_bars == 200
    assert [s.symbol for s in daily.series] == ["AAPL", "NOPE"]
    line = daily.series[0]
    assert line.bars == 200 and line.points[0].close == 0.0 and line.stale is False
    assert daily.series[1].available is False and daily.series[1].points == []
    weekly = equities_board.build_spaghetti("1w", now=MON_2130)
    assert weekly.window_cap_bars == 28 and weekly.series[0].bars == 28
