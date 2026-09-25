"""Pair-screener RFC-001: deep-fetch backfill script (AC-11 mechanics, CONCERN-1).

All tests use `isolated_cache` and an injected fake exchange - no network, and
the real `api/data/cache/` tree is never touched.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from api.data import cache, ccxt_adapter
from api.scripts import backfill_pairs_universe as bp

DAY = bp.DAY_MS
DEEP_START = bp.DEEP_FETCH_SINCE_MS + 400 * DAY  # "listing date" of the fake coin
NOW = DEEP_START + 1200 * DAY
WATCHLIST_JSON = Path(ccxt_adapter.__file__).resolve().parent / "watchlist.json"

MARKETS = {
    "BTC/USDC:USDC": {"symbol": "BTC/USDC:USDC", "base": "BTC", "baseName": "BTC",
                      "swap": True, "spot": False, "active": True},
}


def _bar(ts: int, close: float = 100.0) -> list:
    return [ts, close, close + 1, close - 1, close, 10.0]


class FakeExchange:
    """Serves daily bars from DEEP_START..NOW, honouring since/limit, with an optional cap."""

    id = "hyperliquid"

    def __init__(self, cap: int | None = None, start: int = DEEP_START, end: int = NOW):
        self.markets = MARKETS
        self.cap = cap
        self.bars = [_bar(t) for t in range(start, end + 1, DAY)]
        self.calls: list[dict] = []

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        self.calls.append({"symbol": symbol, "since": since, "limit": limit})
        rows = self.bars if since is None else [b for b in self.bars if b[0] >= since]
        if since is None:
            rows = rows[-(limit or 500):]
        n = min(x for x in (limit, self.cap) if x is not None) if (limit or self.cap) else len(rows)
        return rows[:n]


def _seed_shallow(n: int = 501) -> pd.DataFrame:
    stamps = [NOW - (n - 1 - i) * DAY for i in range(n)]
    df = pd.DataFrame([_bar(t, 50.0) for t in stamps],
                      columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["source"] = "hyperliquid"
    cache.write_ohlcv("BTC", "1d", df)
    return cache.read_ohlcv("BTC", "1d")


def _digest(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def test_shallow_cache_is_deepened_to_the_real_start(isolated_cache):
    before = _seed_shallow()
    assert len(before) == 501
    ex = FakeExchange()
    r = bp.backfill_coin("BTC", ex, now_ms=NOW)
    after = cache.read_ohlcv("BTC", "1d")
    expected = len(ex.bars)
    assert r.status == "ok"
    assert len(after) == expected == r.bars
    assert after["timestamp"].min() == pd.Timestamp(DEEP_START, unit="ms", tz="UTC")
    assert r.first == str(pd.Timestamp(DEEP_START, unit="ms", tz="UTC").date())
    # Grew, not replaced: same newest date, the old tail's timestamps all survive.
    assert after["timestamp"].max() == before["timestamp"].max()
    assert set(before["timestamp"]).issubset(set(after["timestamp"]))


def test_every_exchange_call_uses_an_explicit_since(isolated_cache):
    _seed_shallow()
    ex = FakeExchange(cap=300)
    bp.backfill_coin("BTC", ex, now_ms=NOW)
    assert ex.calls
    assert all(c["since"] is not None for c in ex.calls)
    assert ex.calls[0]["since"] == bp.DEEP_FETCH_SINCE_MS
    assert all(c["limit"] == bp.DEEP_FETCH_LIMIT for c in ex.calls)


def test_capped_response_pages_forward(isolated_cache, monkeypatch):
    # Cap below the requested limit: simulate the exchange silently truncating.
    monkeypatch.setattr(bp, "DEEP_FETCH_LIMIT", 300)
    ex = FakeExchange(cap=300)
    r = bp.backfill_coin("BTC", ex, now_ms=NOW)
    sinces = [c["since"] for c in ex.calls]
    assert len(ex.calls) > 1
    assert sinces == sorted(sinces) and len(set(sinces)) == len(sinces)
    for prev_call, nxt in zip(ex.calls, ex.calls[1:]):
        prev_page = [b for b in ex.bars if b[0] >= prev_call["since"]][:300]
        assert nxt["since"] == prev_page[-1][0] + DAY
    assert r.bars == len(ex.bars)
    assert r.capped_pages == len(ex.calls) - 1


def test_uncapped_response_is_a_single_call(isolated_cache):
    ex = FakeExchange()
    r = bp.backfill_coin("BTC", ex, now_ms=NOW)
    assert len(ex.calls) == 1 and r.pages == 1 and r.capped_pages == 0


def test_pagination_stops_at_now_and_at_max_pages(isolated_cache, monkeypatch):
    monkeypatch.setattr(bp, "DEEP_FETCH_LIMIT", 10)
    monkeypatch.setattr(bp, "MAX_PAGES", 3)
    ex = FakeExchange(cap=10)
    r = bp.backfill_coin("BTC", ex, now_ms=NOW)
    assert r.pages == 3


def test_unknown_coin_is_reported_not_fetched(isolated_cache):
    ex = FakeExchange()
    r = bp.backfill_coin("NOPE", ex, now_ms=NOW)
    assert r.status == "bad_symbol" and r.bars == 0 and ex.calls == []


def test_backfill_all_never_touches_watchlist_json(isolated_cache, capsys):
    before = _digest(WATCHLIST_JSON)
    results = bp.backfill_all(exchange=FakeExchange(), coins=["BTC", "NOPE"])
    assert [r.status for r in results] == ["ok", "bad_symbol"]
    assert _digest(WATCHLIST_JSON) == before
    out = capsys.readouterr().out
    assert "BTC" in out and "NOPE" in out


def test_recording_proxy_delegates_attributes():
    ex = FakeExchange()
    proxy = bp.RecordingExchange(ex)
    assert proxy.markets is MARKETS and proxy.id == "hyperliquid"


@pytest.mark.parametrize("value", [bp.DEEP_FETCH_SINCE_MS])
def test_since_constant_is_2020_01_01_utc(value):
    assert pd.Timestamp(value, unit="ms", tz="UTC") == pd.Timestamp("2020-01-01", tz="UTC")
