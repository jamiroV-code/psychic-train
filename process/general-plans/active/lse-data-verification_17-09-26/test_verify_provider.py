"""Offline tests for verify_provider.py -- synthetic fixtures only, no network."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import verify_provider as vp  # noqa: E402


def bars(dates, closes=None, opens=None):
    dates = pd.to_datetime(dates)
    closes = closes if closes is not None else [100.0 + i for i in range(len(dates))]
    opens = opens if opens is not None else closes
    return pd.DataFrame({
        "date": dates, "open": opens, "close": closes,
        "high": [max(o, c) + 1 for o, c in zip(opens, closes)],
        "low": [min(o, c) - 1 for o, c in zip(opens, closes)],
        "volume": 1.0,
    })


# --- constants ------------------------------------------------------------

def test_phase4_universe_frozen_list():
    assert len(vp.PHASE4_UNIVERSE) == 50
    assert len(set(vp.PHASE4_UNIVERSE)) == 50
    assert set(vp.FIXED_SYMBOLS) <= set(vp.PHASE4_UNIVERSE)
    assert vp.FIXED_SYMBOLS == ["AAPL", "MSFT", "SPY", "XOM", "KO", "NVDA"]
    assert (vp.DELISTED_PRIMARY, vp.DELISTED_BACKUP) == ("SIVB", "FRC")


# --- normalize ------------------------------------------------------------

def test_normalize_candles_lse_row_shape():
    rows = [{"timestamp": "2024-01-02T00:00:00Z", "open": 1, "high": 2, "low": 0.5, "close": 1.5}]
    df = vp.normalize_candles(rows)
    assert df["date"].iloc[0] == pd.Timestamp("2024-01-02")
    assert df["volume"].iloc[0] == 0.0


def test_normalize_candles_stooq_csv_shape_and_empty():
    df = vp.normalize_candles(pd.DataFrame({"Date": ["2024-01-02"], "Open": [1], "High": [2],
                                            "Low": [0.5], "Close": [1.5], "Volume": [10]}))
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert vp.normalize_candles([]).empty


def test_normalize_candles_missing_column_raises():
    with pytest.raises(ValueError):
        vp.normalize_candles([{"timestamp": "2024-01-02", "open": 1}])


# --- AC2 coverage -----------------------------------------------------------

def test_coverage_known_gaps():
    sessions = pd.bdate_range("2024-01-01", "2024-01-31")  # 23 weekdays
    have = sessions.delete([3, 10, 11, 12])                 # 1 single + one run of 3
    cov = vp.compute_coverage(bars(have), sessions)
    assert cov["first_date"] == sessions[0].date()
    assert cov["last_date"] == sessions[-1].date()
    assert cov["rows"] == len(sessions) - 4
    assert cov["missing_sessions"] == 4
    assert cov["longest_gap"] == 3


def test_coverage_ignores_sessions_outside_data_span_and_empty():
    sessions = pd.bdate_range("2023-01-01", "2024-12-31")
    have = pd.bdate_range("2024-03-01", "2024-03-29")
    cov = vp.compute_coverage(bars(have), sessions)
    assert cov["missing_sessions"] == 0 and cov["longest_gap"] == 0
    assert vp.compute_coverage(vp.normalize_candles([]), sessions)["rows"] == 0


def test_coverage_with_real_nyse_calendar():
    sessions = vp.nyse_sessions("2024-07-01", "2024-07-12")  # Jul 4 holiday excluded
    assert len(sessions) == 9
    cov = vp.compute_coverage(bars(sessions), sessions)
    assert cov["missing_sessions"] == 0


# --- AC3 delisted -----------------------------------------------------------

def test_delisted_empty_means_survivorship_bias_present():
    assert vp.classify_delisted(vp.normalize_candles([]))["survivorship_bias"] == "present"


def test_delisted_history_means_survivorship_bias_absent():
    res = vp.classify_delisted(bars(pd.bdate_range("2023-03-01", "2023-03-10")))
    assert res["survivorship_bias"] == "absent"
    assert res["rows"] == 8
    assert str(res["last_date"]) == "2023-03-10"


# --- AC4 cross-source -------------------------------------------------------

def test_cross_source_diff_distribution():
    dates = pd.bdate_range("2024-01-01", periods=100)
    b = bars(dates, closes=[100.0] * 100)
    a_close = [100.0] * 100
    a_close[0] = 110.0   # 10% outlier
    a_close[1] = 101.0   # 1%
    res = vp.cross_source_diff(bars(dates, closes=a_close), b)
    assert res["n"] == 100
    assert res["median"] == pytest.approx(0.0)
    assert res["max"] == pytest.approx(10.0)
    assert 1.0 <= res["p99"] <= 10.0


def test_cross_source_diff_aligns_on_dates_only():
    a = bars(pd.bdate_range("2024-01-01", periods=10), closes=[100.0] * 10)
    b = bars(pd.bdate_range("2024-01-08", periods=10), closes=[102.0] * 10)
    res = vp.cross_source_diff(a, b)
    assert res["n"] == 5
    assert res["median"] == pytest.approx(2 / 102 * 100)
    assert vp.cross_source_diff(a, bars(pd.bdate_range("2030-01-01", periods=2)))["n"] == 0


# --- AC5 split probe --------------------------------------------------------

@pytest.mark.parametrize("ratio,split", [(4.0, "2020-08-31"), (10.0, "2024-06-10")])
def test_split_probe_raw_series(ratio, split):
    d = pd.bdate_range(end=pd.Timestamp(split) - pd.Timedelta(days=1), periods=5).append(
        pd.bdate_range(split, periods=5))
    closes = [400.0] * 5 + [400.0 / ratio] * 5
    res = vp.detect_split_discontinuity(bars(d, closes=closes), split, ratio)
    assert res["classification"] == "raw"
    assert res["observed_ratio"] == pytest.approx(ratio)


@pytest.mark.parametrize("ratio,split", [(4.0, "2020-08-31"), (10.0, "2024-06-10")])
def test_split_probe_adjusted_series(ratio, split):
    d = pd.bdate_range(end=pd.Timestamp(split) - pd.Timedelta(days=1), periods=5).append(
        pd.bdate_range(split, periods=5))
    res = vp.detect_split_discontinuity(bars(d, closes=[100.0] * 5 + [101.0] * 5), split, ratio)
    assert res["classification"] == "adjusted"


def test_split_probe_ambiguous_and_insufficient():
    d = pd.bdate_range("2020-08-24", periods=10)
    res = vp.detect_split_discontinuity(bars(d, closes=[100.0] * 5 + [50.0] * 5), "2020-08-31", 4.0)
    assert res["classification"] == "ambiguous"
    only_before = bars(pd.bdate_range("2020-08-01", periods=5))
    assert vp.detect_split_discontinuity(only_before, "2020-08-31", 4.0)["classification"] == "insufficient-data"
    assert len(vp.split_window(bars(d), "2020-08-31", n=3)) == 6


# --- AC6 OHLC integrity -----------------------------------------------------

def test_ohlc_integrity_clean_fixture_is_zero():
    res = vp.assert_ohlc_integrity(bars(pd.bdate_range("2024-01-01", periods=20)))
    assert all(v == 0 for v in res.values())


def test_ohlc_integrity_flags_each_injected_violation():
    df = bars(pd.bdate_range("2024-01-01", periods=10))
    df.loc[1, "low"] = df.loc[1, "open"] + 5          # low > min(open, close)
    df.loc[2, "high"] = df.loc[2, "close"] - 5        # high < max(open, close)
    df.loc[3, ["open", "low"]] = [0.0, -1.0]          # non-positive (also low ok vs open)
    df.loc[5, "date"] = df.loc[4, "date"]             # duplicate timestamp (also non-monotonic)
    df.loc[8, "date"] = pd.Timestamp("2023-01-01")    # out of order
    res = vp.assert_ohlc_integrity(df)
    assert res["low_gt_min_open_close"] == 1
    assert res["high_lt_max_open_close"] == 1
    assert res["non_positive_price"] == 1
    assert res["duplicate_timestamp"] == 1
    assert res["non_monotonic"] == 2
    assert res["nan_price"] == 0


# --- AC1/AC7 quota delta ----------------------------------------------------

def test_quota_delta_nested_numeric():
    before = {"rest": {"used": 10, "limit": 1000}, "exports": {"hour": 0}, "tier": "free"}
    after = {"rest": {"used": 13, "limit": 1000}, "exports": {"hour": 2}, "tier": "free"}
    assert vp.quota_delta(before, after) == {"exports.hour": 2, "rest.used": 3}
    assert vp.quota_delta({}, {"x": 1}) == {}


# --- AC7 store shape / DuckDB -----------------------------------------------

def test_store_shape_and_duckdb_query(tmp_path):
    frames = {s: bars(pd.bdate_range("2020-01-01", "2024-12-31")) for s in ("AAA", "BBB", "CCC")}
    frames["CCC"] = frames["CCC"][frames["CCC"]["date"] >= "2024-01-01"]
    size = vp.write_store(frames, tmp_path)
    assert size > 0
    assert sorted(p.parent.name for p in tmp_path.rglob("*.parquet")) == \
        ["symbol=AAA", "symbol=BBB", "symbol=CCC"]
    q = vp.query_store(tmp_path, "2022-01-01", "2024-12-31")
    assert list(q["symbol"]) == ["AAA", "BBB", "CCC"]
    expected = len(pd.bdate_range("2022-01-01", "2024-12-31"))
    assert q.loc[q.symbol == "AAA", "rows"].item() == expected
    assert q.loc[q.symbol == "CCC", "rows"].item() == len(pd.bdate_range("2024-01-01", "2024-12-31"))


# --- output + CLI guards ----------------------------------------------------

def test_to_markdown_table():
    md = vp.to_markdown([{"a": 1, "b": 0.5, "c": None}])
    assert md.splitlines()[0] == "| a | b | c |"
    assert "0.5000" in md
    assert vp.to_markdown([]) == "_(no rows)_"


def test_missing_key_exits_without_network(monkeypatch):
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        vp._require_env("LSE_API_KEY")


def test_cli_rejects_key_flag():
    with pytest.raises(SystemExit):
        vp.main(["--phase", "1", "--api-key", "x"])
