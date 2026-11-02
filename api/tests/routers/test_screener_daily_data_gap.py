"""Consumer payload and local-storage boundaries for daily gap disclosure."""
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from api.analytics import screener_board, equities_board
from api.analytics.indicators import sma, rsi
from api.data import cache, ccxt_adapter, watchlist
from api.data.ccxt_adapter import OhlcvResult
from api.models.screener import CoinPanel, ChartView, DailyDataGap, DailyDataGapRange


@pytest.fixture
def stored(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_WATCHLIST_PATH", str(tmp_path / "watchlist.json"))
    monkeypatch.setenv("SCREENER_LAYOUT_PATH", str(tmp_path / "layout.json"))
    monkeypatch.setattr(watchlist, "read_watchlist", lambda: ["BTC"])
    dates = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("D"), periods=100)
    frame = pd.DataFrame({"timestamp": dates, "open": range(100), "high": range(100),
                          "low": range(100), "close": [100.0+i for i in range(100)], "volume": 1.0, "source": "fixture"})
    cache.write_ohlcv("BTC", "1d", frame.drop(index=[40, 41, 70]).reset_index(drop=True))
    return frame


@pytest.mark.parametrize("timeframe", ["15m", "1h", "4h", "1d", "1w"])
def test_full_daily_history_payload_and_repair(stored, monkeypatch, timeframe):
    calls = []
    def fetch(symbol, tf):
        calls.append(tf)
        daily = cache.read_ohlcv(symbol, "1d")
        frame = daily if tf == "1d" else stored
        return OhlcvResult(symbol, tf, frame, False, "ok")
    monkeypatch.setattr(ccxt_adapter, "fetch_ohlcv", fetch)
    before = cache.read_ohlcv("BTC", "1d")
    sma_before = sma.compute_sma(before).copy()
    rsi_before = rsi.compute_rsi(before).copy()
    board = screener_board.build_coin_panel("BTC", timeframe)
    assert len(calls) == 5
    calls.clear()
    chart = screener_board.build_chart_view("BTC", timeframe)
    assert calls == (["1w", "1d"] if timeframe == "1w" else [timeframe])
    expected = {"missing_days": 3, "ranges": [
        {"start": stored.timestamp.iloc[40].date().isoformat(), "end": stored.timestamp.iloc[41].date().isoformat()},
        {"start": stored.timestamp.iloc[70].date().isoformat(), "end": stored.timestamp.iloc[70].date().isoformat()},
    ]}
    assert board.model_dump(mode="json")["daily_data_gap"] == expected
    assert chart.model_dump(mode="json")["daily_data_gap"] == expected
    assert screener_board.build_chart_view("BTC", timeframe).daily_data_gap == chart.daily_data_gap
    assert_frame_equal(cache.read_ohlcv("BTC", "1d"), before)
    pd.testing.assert_series_equal(sma.compute_sma(before), sma_before)
    pd.testing.assert_series_equal(rsi.compute_rsi(before), rsi_before)
    cache.write_ohlcv("BTC", "1d", stored)
    assert screener_board.build_chart_view("BTC", timeframe).daily_data_gap.missing_days == 0
    assert screener_board.build_coin_panel("BTC", timeframe).daily_data_gap.missing_days == 0


@pytest.mark.parametrize("daily", [pd.DataFrame(), pd.DataFrame({
    "timestamp": pd.date_range("2020-01-01", periods=2, tz="UTC"), "close": [1., 2.],
    "open": [1., 2.], "high": [1., 2.], "low": [1., 2.], "volume": 1., "source": "fixture",
})])
def test_intraday_absent_or_stale_daily_does_not_fetch_daily(isolated_cache, tmp_path, monkeypatch, daily):
    monkeypatch.setenv("SCREENER_LAYOUT_PATH", str(tmp_path / "layout.json"))
    monkeypatch.setenv("SCREENER_WATCHLIST_PATH", str(tmp_path / "watchlist.json"))
    if not daily.empty:
        cache.write_ohlcv("BTC", "1d", daily)
    calls = []
    def fetch(symbol, tf):
        calls.append(tf)
        return OhlcvResult(symbol, tf, pd.DataFrame(), True, "unavailable")
    monkeypatch.setattr(ccxt_adapter, "fetch_ohlcv", fetch)
    result = screener_board.build_chart_view("BTC", "4h")
    assert calls == ["4h"]
    assert not result.chart.available
    assert result.daily_data_gap.missing_days == 0


def test_shared_contract_null_and_nested_schema():
    assert CoinPanel.model_fields["daily_data_gap"].default is None
    assert ChartView.model_fields["daily_data_gap"].default is None
    assert DailyDataGap.model_json_schema()["properties"]["missing_days"]["minimum"] == 0
    assert DailyDataGapRange.model_json_schema()["properties"]["start"]["format"] == "date"
    for parent in (CoinPanel, ChartView):
        alternatives = parent.model_json_schema()["properties"]["daily_data_gap"]["anyOf"]
        assert {"type": "null"} in alternatives
        assert {"$ref": "#/$defs/DailyDataGap"} in alternatives
    assert DailyDataGap.model_json_schema()["properties"]["ranges"]["items"] == {
        "$ref": "#/$defs/DailyDataGapRange",
    }


def test_equities_do_not_infer_crypto_weekend_gaps(isolated_cache, monkeypatch):
    from api.data import equities_store, lse_adapter
    monkeypatch.setattr(equities_store, "load_tickers", lambda: ["TEST"])
    # Empty cache is still a real equities assembly and retains not-evaluated null.
    assert equities_board.build_panel("TEST", "1d", None).daily_data_gap is None
    assert equities_board.build_chart_view("TEST").daily_data_gap is None
