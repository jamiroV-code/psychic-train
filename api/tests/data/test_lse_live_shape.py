"""LSE adapter against the live response shape (T49). No network: every call
goes through an `httpx.MockTransport`; synthetic values only."""
from __future__ import annotations

import json
import logging

import httpx
import pandas as pd

from api.data import cache, lse_adapter

SENTINEL = "LSE_TEST_SENTINEL_KEY_0123456789"
NOW = pd.Timestamp("2026-09-10T15:00:00Z")
UNKNOWN_BODY = {"detail": json.dumps({"detail": "'SYNTH' has no candle data; browse /catalog"})}


def _live_row(day: str, open_, close: float) -> dict:
    return {"ts": f"{day} 00:00:00.000000", "symbol": "TEST", "open": open_,
            "high": close + 1, "low": close - 1, "close": close, "volume": 1000}


LIVE_ROWS = [
    _live_row("2026-09-04", 20, 20.5),  # Friday
    _live_row("2026-09-05", 20.5, 20.5),  # Saturday: dropped
    _live_row("2026-09-07", 20.5, 20.5),  # Labor Day: dropped
    _live_row("2026-09-08", 20.5, 21.0),
    _live_row("2026-09-09", 21, 21.25),
]


def _transport(requests: list, status: int = 200, json_body=None, content: bytes | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if content is not None:
            return httpx.Response(status, content=content)
        return httpx.Response(status, json=json_body)
    return httpx.MockTransport(handler)


def test_live_ts_rows_parse_to_session_frame():
    df = lse_adapter.parse_candles(LIVE_ROWS)
    assert list(df.columns) == cache.OHLCV_COLUMNS
    assert [t.date().isoformat() for t in df["timestamp"]] == ["2026-09-04", "2026-09-08", "2026-09-09"]
    assert all(t == t.floor("D") and str(t.tz) == "UTC" for t in df["timestamp"])
    assert df["open"].tolist() == [20.0, 20.5, 21.0]
    assert df["open"].dtype == "float64"


def test_request_targets_vault_candles_with_x_api_key(isolated_cache, monkeypatch):
    monkeypatch.setenv("LSE_API_KEY", SENTINEL)
    requests: list[httpx.Request] = []
    lse_adapter.fetch_equity_ohlcv("TEST", "1d", transport=_transport(requests, json_body=LIVE_ROWS), now=NOW)
    (req,) = requests
    assert req.url.host == "api.londonstrategicedge.com"
    assert req.url.path == "/vault/candles"
    assert req.headers["x-api-key"] == SENTINEL
    assert "authorization" not in {k.lower() for k in req.headers}
    assert SENTINEL not in str(req.url)


def test_live_404_body_is_unknown_ticker(isolated_cache, monkeypatch):
    monkeypatch.setenv("LSE_API_KEY", SENTINEL)
    requests: list[httpx.Request] = []
    result = lse_adapter.fetch_equity_ohlcv(
        "SYNTH", "1d", transport=_transport(requests, status=404, json_body=UNKNOWN_BODY), now=NOW)
    assert (result.status, result.reason) == ("bad_symbol", "unknown-ticker")
    assert result.df.empty


def test_bare_400_is_http_error_and_key_stays_hidden(isolated_cache, monkeypatch, caplog):
    monkeypatch.setenv("LSE_API_KEY", SENTINEL)
    caplog.set_level(logging.DEBUG)
    requests: list[httpx.Request] = []
    result = lse_adapter.fetch_equity_ohlcv("TEST", "1d", transport=_transport(requests, status=400, content=b""), now=NOW)
    assert (result.status, result.reason) == ("unavailable", "http-error")
    assert len(requests) == 1
    assert SENTINEL not in repr(result)
    assert SENTINEL not in caplog.text
