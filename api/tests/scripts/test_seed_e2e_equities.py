"""Unit tests for `seed_e2e_equities` (T48 / S9D).

Every write goes to `tmp_path`: the cache root (`isolated_cache` plus the
env var the guard reads), the equities file and the manifest. No network, no
key.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from api.data import cache, equities_calendar, equities_store, lse_adapter
from api.scripts import seed_e2e_equities as seeder

NOW = pd.Timestamp("2026-10-12T08:00:00Z")  # a Monday morning: newest due session is Friday


@pytest.fixture(autouse=True)
def _isolated(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    monkeypatch.setenv("SCREENER_CACHE_ROOT", str(isolated_cache))
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(tmp_path / "equities.json"))
    monkeypatch.setenv("SCREENER_LAYOUT_PATH", str(tmp_path / "layout.json"))
    monkeypatch.setattr(seeder, "MANIFEST_PATH", tmp_path / "manifest.json")
    return isolated_cache


def test_refuses_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("SCREENER_CACHE_ROOT")
    with pytest.raises(SystemExit, match="SCREENER_CACHE_ROOT is not set"):
        seeder.seed(now=NOW)
    monkeypatch.setenv("SCREENER_CACHE_ROOT", str(cache.CACHE_ROOT))
    monkeypatch.delenv("SCREENER_EQUITIES_PATH")
    with pytest.raises(SystemExit, match="SCREENER_EQUITIES_PATH is not set"):
        seeder.seed(now=NOW)
    assert not (tmp_path / "equities.json").exists()
    assert not (tmp_path / "manifest.json").exists()


def test_refuses_real_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("SCREENER_CACHE_ROOT", str(cache.DEFAULT_CACHE_ROOT))
    with pytest.raises(SystemExit, match="real cache"):
        seeder.seed(now=NOW)
    monkeypatch.setenv("SCREENER_CACHE_ROOT", str(cache.CACHE_ROOT))
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(equities_store.DEFAULT_EQUITIES_PATH))
    with pytest.raises(SystemExit, match="real equities list"):
        seeder.seed(now=NOW)
    assert not (tmp_path / "manifest.json").exists()
    assert not (cache.CACHE_ROOT / "equities").exists()


def test_writes_files_and_sidecars(tmp_path):
    seeder.seed(now=NOW)
    for ticker in seeder.TICKERS:
        for tf in ("1d", "1w"):
            path = lse_adapter.equity_parquet_path(ticker, tf)
            assert path.exists(), (ticker, tf)
            meta = json.loads(path.with_name(f"{tf}.meta.json").read_text())
            assert pd.Timestamp(meta["fetched_at"]) == NOW
            footer = pd.read_parquet(path).attrs
            assert footer.get("mysite.redistributable") == "false"
    assert json.loads((tmp_path / "equities.json").read_text()) == {"tickers": seeder.TICKERS}
    assert equities_store.load_tickers() == seeder.TICKERS


def test_last_bar_is_newest_due_session_and_bars_are_sessions():
    seeder.seed(now=NOW)
    due = equities_calendar.last_due_session(NOW)
    assert due.isoformat() == "2026-10-09"
    for ticker in seeder.TICKERS:
        daily = lse_adapter._read_cache(ticker, "1d")
        expected = seeder.THIN_SESSION_COUNT if ticker == seeder.THIN_TICKER else seeder.SESSION_COUNT
        assert len(daily) == expected
        dates = [ts.date() for ts in daily["timestamp"]]
        assert dates[-1] == due
        assert all(lse_adapter.is_nyse_session(d) for d in dates)
        assert dates == sorted(set(dates))
    weekly = lse_adapter._read_cache("SYNA", "1w")
    assert len(weekly) >= 60
    view, _ = lse_adapter.read_cached_equity("SYNA", "1d", now=NOW)
    assert (view.status, view.reason) == ("ok", "fresh-cache")
    assert not equities_calendar.bar_is_stale(due, NOW)


def test_names_and_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"watchlist": ["BTC", "ETH", "THIN"], "benchmarks": ["BTC", "HYPE"]}))
    entry = seeder.seed(now=NOW)
    assert all(t.startswith("SYN") for t in seeder.TICKERS)
    assert len(seeder.TICKERS) == 4 and seeder.THIN_TICKER in seeder.TICKERS
    data = json.loads(manifest.read_text())
    assert data["watchlist"] == ["BTC", "ETH", "THIN"]
    assert data["benchmarks"] == ["BTC", "HYPE"]
    assert data["equities"] == entry
    assert entry["tickers"] == seeder.TICKERS
    assert entry["thin_ticker"] == "SYNTHIN"
    assert entry["redistributable"] is False
    assert entry["last_session"] == "2026-10-09"
    assert entry["bars_written"]["SYNTHIN"]["1d"] == 20
