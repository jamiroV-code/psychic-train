"""T104 W3: GET /api/narrative/discovery/price, daily closes from the local 1d cache only."""
from __future__ import annotations

import socket
from datetime import date

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.data import cache
from api.main import app
from api.routers import discovery as router_mod

URL = "/api/narrative/discovery/price"
TODAY = date(2026, 10, 16)   # as_of / last day is 2026-10-15


def bars(start: str, n: int, base: float = 100.0) -> pd.DataFrame:
    ts = pd.date_range(start, periods=n, freq="D", tz="UTC")
    close = [base + i for i in range(n)]
    return pd.DataFrame({"timestamp": ts, "open": close, "high": close, "low": close, "close": close,
                         "volume": 1.0, "source": "test"})


@pytest.fixture
def client(isolated_cache, monkeypatch):
    monkeypatch.setattr(router_mod, "utc_today", lambda: TODAY)

    def boom(*a, **k):
        raise AssertionError("handler must not reach the network")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    return TestClient(app)


def test_ok_returns_window_days_ending_yesterday(client):
    cache.write_ohlcv("BTC", "1d", bars("2026-07-01", 110))   # runs to 2026-10-17, past TODAY
    b = client.get(URL, params={"symbol": "btc", "window": 7}).json()
    assert (b["symbol"], b["window"], b["status"]) == ("BTC", 7, "ok")
    assert [d["date"] for d in b["days"]] == [f"2026-10-{d:02d}" for d in range(9, 16)]
    assert b["last_date"] == "2026-10-15"                      # nothing after as_of: no lookahead
    assert set(b["days"][0]) == {"date", "close"}


def test_no_cache_is_no_data(client):
    b = client.get(URL, params={"symbol": "ZZZ", "window": 30}).json()
    assert (b["status"], b["days"], b["last_date"]) == ("no-data", [], None)


def test_cache_older_than_window_is_no_data_but_reports_last_date(client):
    cache.write_ohlcv("OLD", "1d", bars("2026-01-01", 30))    # ends 2026-01-30
    b = client.get(URL, params={"symbol": "OLD", "window": 30}).json()
    assert (b["status"], b["days"], b["last_date"]) == ("no-data", [], "2026-01-30")


def test_non_finite_and_non_positive_closes_are_dropped(client):
    df = bars("2026-10-01", 15)
    df.loc[3, "close"] = float("nan")
    df.loc[4, "close"] = 0.0
    cache.write_ohlcv("X", "1d", df)
    days = client.get(URL, params={"symbol": "X", "window": 30}).json()["days"]
    assert "2026-10-04" not in [d["date"] for d in days] and "2026-10-05" not in [d["date"] for d in days]


@pytest.mark.parametrize("params", [{"symbol": "../x"}, {"symbol": "a/b"}, {"symbol": ""}, {"symbol": "A", "window": 14}, {}])
def test_bad_input_is_422(client, params):
    assert client.get(URL, params=params).status_code == 422
