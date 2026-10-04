"""LSE equities adapter (S3). No network: every call goes through an
`httpx.MockTransport`; every cache write goes to `isolated_cache`."""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import httpx
import pandas as pd
import pyarrow.parquet as pq
import pytest

from api.analytics.indicators.momentum import compute_rsi
from api.data import cache, lse_adapter

FIXTURES = Path(__file__).parent / "fixtures"
SYNTHETIC = FIXTURES / "lse_candles_synthetic.json"
PROBE_SHAPE = FIXTURES / "lse_candles_probe_shape.json"
REPO_ROOT = Path(__file__).resolve().parents[3]
SENTINEL = "LSE_TEST_SENTINEL_KEY_0123456789"
NOW = pd.Timestamp("2026-10-01T15:00:00Z")  # synthetic fixture ends 2026-09-30


def _row(day: str, close: float = 10.0, symbol: str = "TEST") -> dict:
    return {"symbol": symbol, "open": close, "high": close + 1, "low": close - 1, "close": close,
            "volume": 1000, "timestamp": f"{day}T00:00:00Z"}


def _dates(df: pd.DataFrame) -> set[str]:
    return {ts.date().isoformat() for ts in df["timestamp"]}


class _Recorder:
    def __init__(self, status: int = 200, body=None, exc: Exception | None = None):
        self.status, self.body, self.exc = status, body, exc
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        return httpx.Response(self.status, json=self.body if self.body is not None else {"detail": "x"})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


@pytest.fixture
def synthetic_rows() -> list[dict]:
    return json.loads(SYNTHETIC.read_text())


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setenv("LSE_API_KEY", SENTINEL)


def test_parse_documented_row_shape_to_ohlcv_frame(synthetic_rows):
    df = lse_adapter.parse_candles(synthetic_rows)
    assert list(df.columns) == cache.OHLCV_COLUMNS
    assert str(df["timestamp"].dt.tz) == "UTC"
    assert df["timestamp"].is_monotonic_increasing and df["timestamp"].is_unique
    assert (df["source"] == "lse").all()
    # 109 weekdays + 2 Saturdays in the fixture; 4 NYSE holidays and both Saturdays dropped.
    assert len(synthetic_rows) == 111 and len(df) == 105
    first = synthetic_rows[0]
    assert df.iloc[0]["close"] == pytest.approx(first["close"])
    assert df.iloc[0]["volume"] == pytest.approx(first["volume"])
    # Wrapped payloads parse the same way.
    assert len(lse_adapter.parse_candles({"data": synthetic_rows})) == 105


def test_non_session_days_are_dropped():
    dropped = ["2006-11-23", "2007-11-22", "2008-01-01", "2005-03-25",
               "2026-05-02", "2026-05-09", "2026-05-16", "2026-05-23", "2026-05-30"]
    kept = ["2026-05-05"]  # an ordinary Tuesday
    df = lse_adapter.parse_candles([_row(d) for d in dropped + kept])
    assert _dates(df) == set(kept)


def test_session_calendar_nyse_traps():
    kept = ["2010-12-31", "2021-12-31", "2006-10-09", "2005-11-11"]
    dropped = ["2015-07-03", "2022-06-20"]
    df = lse_adapter.parse_candles([_row(d) for d in kept + dropped])
    assert _dates(df) == set(kept)


def test_missing_key_is_unavailable_and_makes_no_call(isolated_cache, monkeypatch):
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    rec = _Recorder(body=[])
    result = lse_adapter.fetch_equity_ohlcv("AAPL", "1d", transport=rec.transport, now=NOW)
    assert (result.status, result.reason) == ("unavailable", "missing-key")
    assert rec.requests == []
    assert result.df.empty


def test_http_error_or_timeout_never_raises(isolated_cache, keyed):
    cases = [
        (_Recorder(status=500), "http-error"),
        (_Recorder(status=401), "auth-rejected"),
        (_Recorder(status=429), "rate-limited"),
        (_Recorder(body={"unexpected": 1}), "bad-payload"),
        (_Recorder(exc=httpx.ReadTimeout("slow")), "timeout"),
        (_Recorder(exc=httpx.ConnectError("down")), "network-error"),
    ]
    for rec, reason in cases:
        result = lse_adapter.fetch_equity_ohlcv("AAPL", "1d", transport=rec.transport, now=NOW)
        assert (result.status, result.reason) == ("unavailable", reason)
        assert len(rec.requests) == 1


def test_404_ticker_is_bad_symbol(isolated_cache, keyed):
    rec = _Recorder(status=404)
    result = lse_adapter.fetch_equity_ohlcv("SIVB", "1d", transport=rec.transport, now=NOW)
    assert (result.status, result.reason) == ("bad_symbol", "unknown-ticker")
    assert result.df.empty


def test_unsupported_timeframe_is_unavailable(isolated_cache, keyed):
    rec = _Recorder(body=[])
    for tf in ("15m", "1h", "4h", "1M"):
        result = lse_adapter.fetch_equity_ohlcv("AAPL", tf, transport=rec.transport, now=NOW)
        assert (result.status, result.reason) == ("unavailable", "unsupported-timeframe")
    assert rec.requests == []


def test_result_and_parquet_are_tagged_redistributable_false(isolated_cache, keyed, synthetic_rows):
    rec = _Recorder(body=synthetic_rows)
    result = lse_adapter.fetch_equity_ohlcv("SYNTH", "1d", transport=rec.transport, now=NOW)
    assert result.status == "ok"
    assert result.redistributable is False and result.source == "lse"
    assert set(lse_adapter.CAVEATS) <= set(result.caveats)
    for tf in ("1d", "1w"):
        path = isolated_cache / "equities" / "SYNTH" / f"{tf}.parquet"
        assert pd.read_parquet(path).attrs["mysite.redistributable"] == "false"
        assert pq.read_schema(path).pandas_metadata["attributes"]["mysite.redistributable"] == "false"
        meta = json.loads((path.parent / f"{tf}.meta.json").read_text())
        assert meta["schema"] == 1 and pd.Timestamp(meta["fetched_at"]) == NOW
    assert ".to_parquet(" not in Path(lse_adapter.__file__).read_text()


def test_weekly_is_monday_anchored_from_daily(isolated_cache, keyed, synthetic_rows):
    rec = _Recorder(body=synthetic_rows)
    weekly = lse_adapter.fetch_equity_ohlcv("SYNTH", "1w", transport=rec.transport, now=NOW).df
    daily = lse_adapter.parse_candles(synthetic_rows)
    assert (weekly["timestamp"].dt.dayofweek == 0).all()
    week = daily[(daily["timestamp"] >= "2026-09-14") & (daily["timestamp"] < "2026-09-21")]
    row = weekly[weekly["timestamp"] == pd.Timestamp("2026-09-14", tz="UTC")].iloc[0]
    assert row["open"] == pytest.approx(week["open"].iloc[0])
    assert row["close"] == pytest.approx(week["close"].iloc[-1])
    assert row["high"] == pytest.approx(week["high"].max())
    assert row["low"] == pytest.approx(week["low"].min())
    assert row["volume"] == pytest.approx(week["volume"].sum())
    assert len(rec.requests) == 1  # one daily request serves both timeframes


def test_cache_is_fresh_for_six_hours_then_refetched(isolated_cache, keyed, synthetic_rows):
    rec = _Recorder(body=synthetic_rows)
    first = lse_adapter.fetch_equity_ohlcv("SYNTH", "1d", transport=rec.transport, now=NOW)
    assert (first.status, first.reason, len(rec.requests)) == ("ok", "fetched", 1)
    within = lse_adapter.fetch_equity_ohlcv("SYNTH", "1d", transport=rec.transport,
                                            now=NOW + pd.Timedelta(hours=5, minutes=59))
    assert (within.status, within.reason, len(rec.requests)) == ("ok", "fresh-cache", 1)
    assert len(within.df) == len(first.df)
    weekly = lse_adapter.fetch_equity_ohlcv("SYNTH", "1w", transport=rec.transport,
                                            now=NOW + pd.Timedelta(hours=1))
    assert (weekly.reason, len(rec.requests)) == ("fresh-cache", 1)
    after = lse_adapter.fetch_equity_ohlcv("SYNTH", "1d", transport=rec.transport,
                                           now=NOW + pd.Timedelta(hours=6, minutes=1))
    assert (after.reason, len(rec.requests)) == ("fetched", 2)


def test_rsi_on_equity_bars_via_compute_rsi(isolated_cache, keyed, synthetic_rows):
    rec = _Recorder(body=synthetic_rows)
    df = lse_adapter.fetch_equity_ohlcv("SYNTH", "1d", transport=rec.transport, now=NOW).df
    rsi = compute_rsi(df)
    assert rsi is not None
    last = rsi.dropna().iloc[-1]
    assert 0.0 <= last <= 100.0


@pytest.mark.skipif(not PROBE_SHAPE.exists(), reason="probe fixture absent: run s3-probe/lse_probe.py on the user PC (P-S3-1)")
def test_probe_fixture_parses():
    payload = json.loads(PROBE_SHAPE.read_text())
    rows = lse_adapter.extract_rows(payload)
    assert rows, "probe fixture has no rows"
    assert {"symbol", "open", "high", "low", "close", "volume", "timestamp"} <= set(rows[0])
    df = lse_adapter.parse_candles(payload)
    assert list(df.columns) == cache.OHLCV_COLUMNS
    assert len(df) > 0 and df["close"].notna().all()


def test_cache_path_is_gitignored():
    paths = ["api/data/cache/equities/AAPL/1d.parquet", "api/data/cache/equities/AAPL/1d.meta.json",
             "api/data/cache/equities/_probe/x.json", "api/data/equities.json"]
    out = subprocess.run(["git", "check-ignore", *paths], cwd=REPO_ROOT, capture_output=True, text=True)
    assert out.returncode == 0
    assert out.stdout.split() == paths


def test_api_key_never_in_result_repr_logs_or_exception_text(isolated_cache, monkeypatch, caplog):
    monkeypatch.setenv("LSE_API_KEY", SENTINEL)
    caplog.set_level(logging.DEBUG)
    cases = [
        _Recorder(status=401),
        _Recorder(status=404),
        _Recorder(status=500),
        _Recorder(exc=httpx.ConnectError("cannot reach host")),
        _Recorder(exc=httpx.ReadTimeout("read timed out")),
    ]
    for rec in cases:
        try:
            result = lse_adapter.fetch_equity_ohlcv("AAPL", "1d", transport=rec.transport, now=NOW)
        except Exception as exc:  # contract is never-raise; the text must be clean regardless
            assert SENTINEL not in str(exc)
            pytest.fail(f"raised {type(exc).__name__}")
        assert result.status in ("unavailable", "bad_symbol")
        (req,) = rec.requests
        assert SENTINEL not in str(req.url)
        assert SENTINEL in req.headers.get(lse_adapter.AUTH_HEADER, "")
        others = [v for k, v in req.headers.items() if k.lower() != lse_adapter.AUTH_HEADER.lower()]
        assert all(SENTINEL not in v for v in others)
        for text in (repr(result), result.reason, " ".join(result.caveats)):
            assert SENTINEL not in text
    assert SENTINEL not in caplog.text


def test_request_uses_explicit_timeout_and_header_auth(isolated_cache, keyed, synthetic_rows):
    rec = _Recorder(body=synthetic_rows)
    lse_adapter.fetch_equity_ohlcv("SYNTH", "1d", transport=rec.transport, now=NOW)
    (req,) = rec.requests
    timeout = req.extensions["timeout"]
    assert all(timeout[k] is not None and timeout[k] <= 15 for k in ("connect", "read", "write", "pool"))
    assert req.headers[lse_adapter.AUTH_HEADER] == f"Bearer {SENTINEL}"
    assert SENTINEL not in str(req.url)
    assert req.url.params["symbol"] == "SYNTH"
    assert int(req.url.params["limit"]) <= 5000


def test_committed_lse_fixtures_are_synthetic_only():
    files = sorted(FIXTURES.glob("lse_*.json"))
    assert SYNTHETIC in files
    for f in files:
        rows = lse_adapter.extract_rows(json.loads(f.read_text()))
        assert rows, f.name
        assert {r.get("symbol") for r in rows} <= {"TEST", "SYNTH"}, f.name
