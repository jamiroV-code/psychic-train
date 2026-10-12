"""S9A: equities refresh (sequential, isolated, never raises, no secret in
logs) and its status. Fetches are injected; no real network or key."""
from __future__ import annotations

import json
import logging
import threading
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from api.data import equities_refresh, equities_store, lse_adapter
from api.tests import equities_fixtures as fx

NOW = pd.Timestamp("2026-10-13T12:00:00Z")
END = date(2026, 10, 12)


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(tmp_path / "equities.json"))
    monkeypatch.setenv("SCREENER_LAYOUT_PATH", str(tmp_path / "layout.json"))
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    yield
    assert equities_refresh.wait_until_idle(5.0)


def _ok(ticker):
    return SimpleNamespace(symbol=ticker, status="ok")


def test_refresh_ticker_uses_injected_fetch():
    seen = []
    result = equities_refresh.refresh_ticker("AAPL", fetch=lambda t: seen.append(t) or _ok(t))
    assert seen == ["AAPL"] and result.status == "ok"


def test_refresh_ticker_isolates_exception_and_logs_no_secret(caplog, monkeypatch):
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)

    def boom(ticker):
        raise RuntimeError(f"GET {lse_adapter.BASE_URL}?k={fx.SYNTHETIC_CREDENTIAL}")

    with caplog.at_level(logging.DEBUG):
        assert equities_refresh.refresh_ticker("AAPL", fetch=boom) is None
    assert "RuntimeError" in caplog.text
    assert fx.SYNTHETIC_CREDENTIAL not in caplog.text
    assert lse_adapter.BASE_URL not in caplog.text


def test_refresh_all_is_sequential_and_isolates_each_ticker():
    for t in ("AAA", "BBB", "CCC"):
        equities_store.add_ticker(t)
    order = []

    def fetch(t):
        order.append(t)
        if t == "BBB":
            raise ValueError("boom")
        return _ok(t)

    assert equities_refresh.refresh_all(fetch=fetch) == {"ok": 2, "failed": 1}
    assert order == ["AAA", "BBB", "CCC"]


def test_default_fetch_is_looked_up_at_call_time(monkeypatch):
    calls = []
    monkeypatch.setattr(lse_adapter, "refresh_equity", lambda t: calls.append(t) or _ok(t))
    assert equities_refresh.refresh_all(tickers=["MSFT"]) == {"ok": 1, "failed": 0}
    assert calls == ["MSFT"]


def test_refresh_inside_fresh_window_still_fetches(monkeypatch):
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)
    fx.seed("AAPL", END, 120, fetched_at=NOW - pd.Timedelta(hours=1))
    assert lse_adapter._is_fresh("AAPL", "1d", NOW)
    transport = fx.CountingTransport(fx.candles_payload(END, 130))

    def fetch(t):
        return lse_adapter.refresh_equity(t, transport=transport, now=NOW)

    assert equities_refresh.refresh_all(tickers=["AAPL"], fetch=fetch) == {"ok": 1, "failed": 0}
    assert transport.calls == 1
    result, fetched_at = lse_adapter.read_cached_equity("AAPL", "1d", now=NOW)
    assert len(result.df) == 130 and fetched_at == NOW


def test_request_during_a_pass_is_not_lost():
    equities_store.add_ticker("AAA")
    gate, started = threading.Event(), threading.Event()
    seen = []

    def fetch(t):
        seen.append(t)
        if t == "AAA" and not started.is_set():
            started.set()
            assert gate.wait(5.0)
        return _ok(t)

    first = equities_refresh.request_refresh_now(fetch=fetch)
    assert first == {"accepted": True, "already_running": False}
    assert started.wait(5.0)
    equities_store.add_ticker("BBB")  # added mid-pass
    second = equities_refresh.request_refresh_now(fetch=fetch)
    third = equities_refresh.request_refresh_now(fetch=fetch)
    assert second == third == {"accepted": True, "already_running": True}
    gate.set()
    assert equities_refresh.wait_until_idle(5.0)
    # One more pass, not two: AAA (blocked), then AAA and BBB.
    assert seen == ["AAA", "AAA", "BBB"]


def test_status_missing_key_shape(monkeypatch):
    monkeypatch.setattr(lse_adapter, "_now", lambda: NOW)
    body = equities_refresh.status()
    assert body == {
        "running": False,
        "disabled_reason": "missing-key",
        "interval_seconds": 86400,
        "last_tick_started": None,
        "last_tick_finished": None,
        "last_tick_ok": None,
        "last_tick_failed": None,
        "next_tick_at": None,
        "queue_depth": 0,
        "backoff_seconds": 0.0,
        "server_time": "2026-10-13T12:00:00Z",
        "last_bar_date": None,
    }


def test_status_with_key_is_not_started_and_never_shows_the_key(monkeypatch):
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)
    equities_store.add_ticker("AAPL")
    equities_store.add_ticker("MSFT")
    fx.seed("AAPL", date(2026, 10, 9), 80)
    fx.seed("MSFT", END, 80)
    body = equities_refresh.status(now=NOW)
    assert body["disabled_reason"] == "not-started"
    assert body["last_bar_date"] == "2026-10-12"
    assert fx.SYNTHETIC_CREDENTIAL not in json.dumps(body)
