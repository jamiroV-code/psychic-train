"""S9A: `lse_adapter.read_cached_equity` (cache only) and `refresh_equity`.
Synthetic bars only; the cache is redirected; no real network or key."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from api.data import lse_adapter
from api.tests import equities_fixtures as fx

NOW = pd.Timestamp("2026-10-13T12:00:00Z")
END = date(2026, 10, 12)


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(tmp_path / "equities.json"))
    monkeypatch.delenv("LSE_API_KEY", raising=False)


def _no_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("network touched")

    monkeypatch.setattr(lse_adapter.httpx, "Client", boom)
    monkeypatch.setattr(lse_adapter, "_request_daily", boom)


def test_no_file_is_unavailable_no_data():
    result, fetched_at = lse_adapter.read_cached_equity("AAPL", "1d", now=NOW)
    assert (result.status, result.reason) == ("unavailable", "no-data")
    assert result.df.empty and fetched_at is None


def test_reads_cache_and_sidecar_fetched_at():
    fx.seed("AAPL", END, 120, fetched_at="2026-10-12T22:00:00Z")
    result, fetched_at = lse_adapter.read_cached_equity("aapl", "1d", now=NOW)
    assert result.symbol == "AAPL" and result.status == "ok"
    assert len(result.df) == 120
    assert fetched_at == pd.Timestamp("2026-10-12T22:00:00Z")
    weekly, _ = lse_adapter.read_cached_equity("AAPL", "1w", now=NOW)
    assert weekly.status == "ok" and not weekly.df.empty


def test_old_newest_bar_is_stale():
    fx.seed("AAPL", date(2026, 9, 1), 120)
    result, _ = lse_adapter.read_cached_equity("AAPL", "1d", now=NOW)
    assert (result.status, result.reason) == ("stale", "newest-bar-old")
    assert len(result.df) == 120


def test_invalid_ticker_and_timeframe():
    bad, fetched = lse_adapter.read_cached_equity("1BAD", "1d", now=NOW)
    assert (bad.status, bad.reason, fetched) == ("bad_symbol", "invalid-ticker", None)
    tf, _ = lse_adapter.read_cached_equity("AAPL", "4h", now=NOW)
    assert (tf.status, tf.reason) == ("unavailable", "unsupported-timeframe")


def test_cached_read_never_touches_network_or_key(monkeypatch):
    fx.seed("AAPL", END, 120)
    _no_network(monkeypatch)
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)
    # A fresh-cache window does not matter either way: no fetch can happen.
    result, _ = lse_adapter.read_cached_equity("AAPL", "1d", now=NOW)
    assert result.status == "ok"
    monkeypatch.delenv("LSE_API_KEY")
    result, _ = lse_adapter.read_cached_equity("AAPL", "1d", now=NOW)
    assert result.status == "ok"


def test_refresh_equity_fetches_inside_fresh_window_and_writes_both(monkeypatch):
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)
    transport = fx.CountingTransport(fx.candles_payload(END, 120))
    first = lse_adapter.refresh_equity("AAPL", transport=transport, now=NOW)
    second = lse_adapter.refresh_equity("AAPL", transport=transport, now=NOW + pd.Timedelta(hours=1))
    assert transport.calls == 2
    assert (first.status, first.reason) == ("ok", "fetched")
    assert (second.status, second.reason) == ("ok", "fetched")
    assert lse_adapter.equity_parquet_path("AAPL", "1d").exists()
    assert lse_adapter.equity_parquet_path("AAPL", "1w").exists()
    _, fetched_at = lse_adapter.read_cached_equity("AAPL", "1w", now=NOW)
    assert fetched_at == NOW + pd.Timedelta(hours=1)
    # No key: never raises, never a request.
    monkeypatch.delenv("LSE_API_KEY")
    missing = lse_adapter.refresh_equity("AAPL", transport=transport, now=NOW)
    assert (missing.reason, transport.calls) == ("missing-key", 2)


def test_unknown_ticker_stays_bad_symbol_for_cache_only_reads(monkeypatch):
    """A 404 from the provider is a ticker fact; the board must not call it an outage."""
    monkeypatch.setattr(lse_adapter, "_known_bad_tickers", set())
    monkeypatch.setenv("LSE_API_KEY", "k")
    monkeypatch.setattr(lse_adapter, "_request_daily", lambda *a, **k: (None, "bad_symbol", "unknown-ticker"))
    assert lse_adapter.read_cached_equity("SPX", "1d", now=NOW)[0].status == "unavailable"

    assert lse_adapter.refresh_equity("SPX", now=NOW).status == "bad_symbol"
    result, _ = lse_adapter.read_cached_equity("SPX", "1d", now=NOW)
    assert (result.status, result.reason) == ("bad_symbol", "unknown-ticker")

    monkeypatch.setattr(lse_adapter, "_request_daily", lambda *a, **k: (fx.daily_frame(END, 120), "ok", "fetched"))
    assert lse_adapter.refresh_equity("SPX", now=NOW).status == "ok"
    assert lse_adapter.read_cached_equity("SPX", "1d", now=NOW)[0].status != "bad_symbol"
