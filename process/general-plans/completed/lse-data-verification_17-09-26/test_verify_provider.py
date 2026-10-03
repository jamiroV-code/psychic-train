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


# --- EVL-001 E1: history()-export shapes through the store ------------------

def _export_frame(kind):
    d = pd.bdate_range("2023-06-01", "2024-06-28")
    base = bars(d).drop(columns="date")
    if kind == "timestamp-iso":
        return base.assign(timestamp=[x.strftime("%Y-%m-%dT00:00:00.000000Z") for x in d])
    if kind == "datetimeindex":
        return base.set_index(pd.DatetimeIndex(d, name="ts"))
    if kind == "epoch-ms":
        return base.assign(ts=(d.asi8 // 1_000_000))
    if kind == "upper-with-symbol":
        return base.rename(columns=str.title).assign(Timestamp=d, symbol="X")
    raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["timestamp-iso", "datetimeindex", "epoch-ms", "upper-with-symbol"])
def test_history_export_shape_round_trips_store(tmp_path, kind):
    root = tmp_path / "store"
    vp.write_store({"AAA": _export_frame(kind)}, root)
    assert vp.store_columns(root) == vp.STORE_COLS
    q = vp.query_store(root, "2024-01-01", "2024-06-28")
    assert q["rows"].item() == len(pd.bdate_range("2024-01-01", "2024-06-28"))


def test_query_ignores_stray_parquet_outside_partitions(tmp_path):
    vp.write_store({"AAA": bars(pd.bdate_range("2024-01-01", periods=5))}, tmp_path)
    (tmp_path / "_downloads").mkdir()
    pd.DataFrame({"open": [1.0]}).to_parquet(tmp_path / "_downloads" / "raw.parquet")
    assert vp.query_store(tmp_path, "2024-01-01", "2024-12-31")["rows"].item() == 5


def test_candle_row_live_shape():
    rows = [{"symbol": "AAPL", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 9,
             "timestamp": "2026-08-26T00:00:00.000000Z"}]
    df = vp.normalize_candles(rows)
    assert df["date"].iloc[0] == pd.Timestamp("2026-08-26")


# --- EVL-001 E4: export budget + rate limit --------------------------------

def test_plan_fetch_methods_respects_export_cap():
    syms = [f"S{i}" for i in range(10)]
    plan = vp.plan_fetch_methods(syms, {"exports_this_hour": 2, "exports_cap_hour": 5,
                                        "calls_per_minute": 200})
    assert [plan[s] for s in syms] == ["history"] * 3 + ["candles"] * 7
    assert set(vp.plan_fetch_methods(syms, {"exports_this_hour": 9, "exports_cap_hour": 5}).values()) == {"candles"}
    assert set(vp.plan_fetch_methods(syms, {}).values()) == {"candles"}


def test_rate_limiter_spacing():
    t = [0.0]
    slept = []
    rl = vp.RateLimiter(200, clock=lambda: t[0], sleep=lambda s: (slept.append(s), t.__setitem__(0, t[0] + s)))
    rl.wait(); rl.wait()
    assert slept == [pytest.approx(0.3)]


# --- EVL-001 E2: date clamp + cross-check sources (mocked) -----------------

def test_clamp_end_to_today():
    from datetime import date
    assert vp.clamp_end("2026-09-25", date(2026, 9, 24)) == date(2026, 9, 24)
    assert vp.clamp_end(date(2026, 9, 1), date(2026, 9, 24)) == date(2026, 9, 1)


class _Resp:
    def __init__(self, status, text):
        self.status_code, self.text = status, text


def _fake_httpx(monkeypatch, get):
    import types
    monkeypatch.setitem(sys.modules, "httpx", types.SimpleNamespace(get=get))


def test_fetch_stooq_mocked_ok_and_error_body(monkeypatch):
    csv = "Date,Open,High,Low,Close,Volume\n2024-01-02,1,2,0.5,1.5,10\n"
    _fake_httpx(monkeypatch, lambda *a, **k: _Resp(200, csv))
    assert vp.fetch_stooq("AAPL", "2024-01-01", "2024-01-05")["close"].item() == 1.5
    _fake_httpx(monkeypatch, lambda *a, **k: _Resp(404, "x" * 1000))
    with pytest.raises(RuntimeError) as e:
        vp.fetch_stooq("AAPL", "2024-01-01", "2024-01-05")
    assert "404" in str(e.value) and "x" * 300 in str(e.value) and "x" * 301 not in str(e.value)


def test_fetch_alpaca_mocked(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")

    class R(_Resp):
        def json(self):
            return {"bars": [{"t": "2024-01-02T05:00:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 3}],
                    "next_page_token": None}
    _fake_httpx(monkeypatch, lambda *a, **k: R(200, ""))
    assert vp.fetch_alpaca("AAPL", "2024-01-01", "2024-01-05")["close"].item() == 1.5


def test_fetch_yfinance_mocked(monkeypatch):
    import types
    d = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="Date")
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], ["AAPL"]])
    frame = pd.DataFrame([[1, 2, 0.5, 1.5, 10], [1, 2, 0.5, 1.6, 10]], index=d, columns=cols)
    calls = {}
    fake = types.SimpleNamespace(download=lambda sym, **k: (calls.update(k), frame)[1])
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    df = vp.fetch_yfinance("AAPL", "2024-01-01", "2024-01-03", adjust="total")
    assert list(df["close"]) == [1.5, 1.6]
    assert calls["auto_adjust"] is True and calls["progress"] is False and calls["end"] == "2024-01-04"


# --- EVL-002 E5/E6: adjustment basis + worst days ------------------------------

def _fake_yf(monkeypatch, frame):
    import types
    calls = {}
    fake = types.SimpleNamespace(download=lambda sym, **k: (calls.update(k), frame)[1])
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    return calls


@pytest.mark.parametrize("fields", [
    ["Open", "High", "Low", "Close", "Adj Close", "Volume"],
    ["Adj Close", "Open", "High", "Low", "Close", "Volume"],   # Adj Close first
])
def test_fetch_yfinance_split_mode_uses_close_not_adj_close(monkeypatch, fields):
    d = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="Date")
    vals = {"Open": 1, "High": 200, "Low": 0.5, "Close": 100.0, "Adj Close": 90.0, "Volume": 10}
    cols = pd.MultiIndex.from_product([fields, ["KO"]])
    frame = pd.DataFrame([[vals[f] for f in fields]] * 2, index=d, columns=cols)
    calls = _fake_yf(monkeypatch, frame)
    df = vp.fetch_yfinance("KO", "2024-01-01", "2024-01-03")  # default = split
    assert calls["auto_adjust"] is False
    assert list(df["close"]) == [100.0, 100.0]
    assert "adj close" not in df.columns


def test_fetch_yfinance_rejects_bad_adjust():
    with pytest.raises(ValueError):
        vp.fetch_yfinance("KO", "2024-01-01", "2024-01-03", adjust="dividend")


def test_cli_yf_adjust_choices():
    with pytest.raises(SystemExit):
        vp.main(["--phase", "3", "--yf-adjust", "bogus"])


def test_worst_days_top_n():
    dates = pd.bdate_range("2024-01-01", periods=8)
    a = bars(dates, closes=[100, 101, 125, 100, 90, 100, 100, 111])
    b = bars(dates, closes=[100] * 8)
    rows = vp.worst_days(a, b, n=3)
    assert [r["date"] for r in rows] == [dates[2].date().isoformat(), dates[7].date().isoformat(),
                                         dates[4].date().isoformat()]
    assert rows[0] == {"date": dates[2].date().isoformat(), "lse_close": 125.0,
                       "xsource_close": 100.0, "pct": 25.0}
    assert len(vp.worst_days(a, b)) == 5
    assert vp.worst_days(a, bars(pd.bdate_range("2030-01-01", periods=2))) == []


def test_interpret_bases_picks_lower_median():
    line = vp.interpret_bases("KO", {"split": {"median": 0.05}, "total": {"median": 7.4}})
    assert "`split`" in line and "NOT dividend-adjusted" in line
    line = vp.interpret_bases("X", {"split": {"median": 3.0}, "total": {"median": 0.1}})
    assert "`total`" in line
    assert "no comparable" in vp.interpret_bases("Y", {"split": {"median": None}})


def test_phase3_compare_both_output(monkeypatch, capsys):
    sessions = pd.bdate_range("2024-01-02", periods=10)
    lse = bars(sessions, closes=[100.0] * 10)
    monkeypatch.setattr(vp, "FIXED_SYMBOLS", ["KO"])
    monkeypatch.setattr(vp, "SPLITS", [])
    monkeypatch.setattr(vp, "EARLIEST", "2024-01-01")
    monkeypatch.setattr(vp, "lse_client", lambda: object())
    monkeypatch.setattr(vp, "fetch_candles", lambda *a, **k: lse)
    monkeypatch.setattr(vp, "clamp_end", lambda d: pd.Timestamp("2024-01-31").date())
    seen = []
    def fake_yf(sym, start, end, adjust="split"):
        seen.append(adjust)
        return bars(sessions, closes=[100.0] * 10 if adjust == "split" else [93.0] * 10)
    monkeypatch.setattr(vp, "fetch_yfinance", fake_yf)
    monkeypatch.setattr(vp, "CROSS_SOURCE_YEARS", 1)
    vp.phase3("yfinance", "split", compare_both=True)
    out = capsys.readouterr().out
    assert seen == ["split", "total"]
    assert "| symbol | source | basis |" in out
    assert "| KO | yfinance | split |" in out and "| KO | yfinance | total |" in out
    assert "KO: LSE closest to yfinance `split`" in out
    assert "**KO (split)**" in out and "**KO (total)**" in out
    assert "lse_close" in out and "xsource_close" in out


def test_cross_check_chain_fallback_and_all_fail():
    good = bars(pd.bdate_range("2024-01-01", periods=2))
    def bad(*a):
        raise RuntimeError("404")
    def nokey(*a):
        raise SystemExit("no key")
    src, df, errs = vp.fetch_cross_check(["stooq", "alpaca"], "A", "s", "e",
                                         {"stooq": bad, "alpaca": lambda *a: good})
    assert src == "alpaca" and len(df) == 2 and errs and "404" in errs[0]
    with pytest.raises(RuntimeError):
        vp.fetch_cross_check(["stooq", "alpaca"], "A", "s", "e", {"stooq": bad, "alpaca": nokey})
    assert vp.XSOURCES["stooq"] == ["stooq", "alpaca"]


def test_cli_xsource_choices():
    with pytest.raises(SystemExit):
        vp.main(["--phase", "3", "--xsource", "bogus"])


# --- EVL-001 E3: extra / duplicate dates -----------------------------------

def test_calendar_anomalies_extra_and_duplicates():
    sessions = vp.nyse_sessions("2024-07-01", "2024-07-12")
    df = bars(sessions)
    extra = bars(pd.to_datetime(["2024-07-04", "2024-07-06"]))   # holiday + Saturday
    dup = bars(pd.to_datetime(["2024-07-08"]))
    cov = vp.compute_coverage(pd.concat([df, extra, dup]), sessions)
    assert cov["missing_sessions"] == 0
    assert cov["rows"] == len(sessions) + 3
    assert cov["extra_rows"] == 2 and cov["extra_sample"] == ["2024-07-04", "2024-07-06"]
    assert cov["duplicate_dates"] == 1 and cov["duplicate_sample"] == ["2024-07-08"]
    many = bars(pd.date_range("2024-07-13", periods=8, freq="7D"))  # Saturdays
    assert len(vp.calendar_anomalies(many, sessions)["extra_sample"]) == 5
