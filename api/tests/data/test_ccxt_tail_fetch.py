"""T32 / S1 — tail fetch, forming-candle expiry and gap handling (B3, B4).

The fake exchange mirrors Hyperliquid's request semantics as far as they
matter here: with `since` it returns the OLDEST `limit` bars at or after
`since`; with `since=None` it returns the LATEST `limit` bars. The bar that
contains the clock is the forming bar, and its close moves with the clock,
so a refetch is observable in the data.

The clock is anchored to the real hour (`NOW`) so that, on a base whose
freshness check reads the real clock, the forming-candle tests fail on
behaviour (the base serves the forming bar for a whole bar interval) rather
than passing by accident. Every assertion reads only the injected clock.
"""
from __future__ import annotations

import os

import ccxt
import pandas as pd
import pytest

from api.data import cache, ccxt_adapter

S = pd.Timedelta(seconds=1)
TF_SECONDS = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
NOW = pd.Timestamp.now(tz="UTC").floor("1h") + 10 * S


def _ms(ts: pd.Timestamp) -> int:
    return int(ts.timestamp() * 1000)


class Clock:
    def __init__(self, now: pd.Timestamp = NOW):
        self.now = now

    def __call__(self) -> pd.Timestamp:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + pd.Timedelta(seconds=seconds)


class TailExchange:
    """No `markets` attribute, so the ticker is passed through unchanged."""

    id = "hyperliquid"

    def __init__(self, clock: Clock, *, end: pd.Timestamp | None = None, history: int = 6000,
                 empty: bool = False, raise_on_fetch: Exception | None = None):
        self.clock = clock
        self.end = end  # newest bar open the exchange knows; default: the forming bar
        self.history = history
        self.empty = empty
        self.raise_on_fetch = raise_on_fetch
        self.calls: list[dict] = []

    def _bars(self, timeframe: str) -> list[list]:
        step = TF_SECONDS[timeframe]
        now_ms = _ms(self.clock())
        newest = _ms(self.end) if self.end is not None else now_ms - now_ms % (step * 1000)
        out = []
        for i in range(self.history - 1, -1, -1):
            open_ms = newest - i * step * 1000
            forming = open_ms <= now_ms < open_ms + step * 1000
            close = 1000.0 + (now_ms / 1000.0 % 10000 if forming else (open_ms // 1000) % 997)
            out.append([open_ms, close, close + 1, close - 1, close, 10.0])
        return out

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        self.calls.append({"symbol": symbol, "timeframe": timeframe, "since": since, "limit": limit})
        if self.raise_on_fetch is not None:
            raise self.raise_on_fetch
        if self.empty:
            return []
        bars = self._bars(timeframe)
        if since is not None:
            picked = [b for b in bars if b[0] >= since]
            return picked[:limit] if limit else picked
        return bars[-limit:] if limit else bars


def _frame(end: pd.Timestamp, periods: int, timeframe: str) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=periods, freq=pd.Timedelta(seconds=TF_SECONDS[timeframe]), tz="UTC")
    return pd.DataFrame({
        "timestamp": idx, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
        "volume": 10.0, "source": "fixture",
    })


def _bar_open(timeframe: str, now: pd.Timestamp) -> pd.Timestamp:
    return now.floor(pd.Timedelta(seconds=TF_SECONDS[timeframe]))


def _seed_legacy(symbol, timeframe, df, *, mtime: pd.Timestamp) -> None:
    """A cache file as an older build left it: parquet only, no sidecar, so
    its fetch time is the parquet mtime (B1 migration rule)."""
    cache.write_ohlcv(symbol, timeframe, df)
    for p in cache.ohlcv_path(symbol, timeframe).parent.glob(f"{timeframe}.meta.json"):
        p.unlink()
    os.utime(cache.ohlcv_path(symbol, timeframe), (mtime.timestamp(), mtime.timestamp()))


def _fetched_at(symbol, timeframe):
    return cache.read_fetched_at(symbol, timeframe)


@pytest.fixture
def clock(isolated_cache, monkeypatch):
    c = Clock()
    # raising=False: on a base without `_now` the patch is a no-op and the
    # tests fail on behaviour, not on the patch itself.
    monkeypatch.setattr(ccxt_adapter, "_now", c, raising=False)
    ccxt_adapter.reset_exchange_cache()
    yield c
    ccxt_adapter.reset_exchange_cache()


def test_tail_fetch_uses_since_none_and_latest_limit(clock):
    tf = "1h"
    cache.write_ohlcv("BTC", tf, _frame(_bar_open(tf, clock()) - 3 * pd.Timedelta(hours=1), 150, tf),
                      fetched_at=clock() - pd.Timedelta(hours=4))
    ex = TailExchange(clock)
    result = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)

    assert ex.calls == [{"symbol": "BTC", "timeframe": tf, "since": None, "limit": 200}]
    assert result.status == "ok"
    assert result.df["timestamp"].max() == _bar_open(tf, clock())
    assert result.note is None


def test_500_bar_gap_regression_catches_up(clock):
    tf = "15m"
    behind = _bar_open(tf, clock()) - 576 * pd.Timedelta(minutes=15)
    _seed_legacy("BTC", tf, _frame(behind, 200, tf), mtime=behind)
    ex = TailExchange(clock)

    result = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)

    assert len(ex.calls) == 1, "one refresh must be enough"
    assert result.df["timestamp"].max() == _bar_open(tf, clock())
    assert result.status == "ok"


def test_forming_candle_refresh_after_ttl(clock):
    tf = "1h"
    ex = TailExchange(clock)
    first = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)
    first_close = first.df["close"].iloc[-1]

    clock.advance(301)  # TTL for 1h is 300 s; still inside the same bar
    second = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)

    assert len(ex.calls) == 2, "the forming candle must be refetched once its TTL has passed"
    assert second.df["timestamp"].max() == first.df["timestamp"].max()
    assert second.df["close"].iloc[-1] != first_close
    assert second.fetched_at == clock()


def test_forming_candle_not_refetched_inside_ttl(clock):
    tf = "1h"
    ex = TailExchange(clock)
    first = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)
    clock.advance(299)
    second = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)

    assert len(ex.calls) == 1
    assert second.status == "ok"
    assert second.fetched_at == first.fetched_at


def test_new_bar_boundary_forces_refetch_even_inside_ttl(clock):
    tf = "1h"
    clock.now = _bar_open(tf, clock()) + 3570 * S
    ex = TailExchange(clock)
    ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)
    clock.advance(60)  # crosses into the next bar, well inside the 300 s TTL
    result = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)

    assert len(ex.calls) == 2
    assert result.df["timestamp"].max() == _bar_open(tf, clock())


def test_non_contiguous_tail_replaces_cache_and_notes_gap(clock):
    tf = "4h"
    old_end = _bar_open(tf, clock()) - 400 * pd.Timedelta(hours=4)
    cache.write_ohlcv("BTC", tf, _frame(old_end, 100, tf), fetched_at=old_end)
    ex = TailExchange(clock)

    result = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)

    assert result.note == "gap-replaced"
    assert result.df["timestamp"].min() > old_end, "old bars must not survive a gap"
    assert len(result.df) == 200
    assert result.df["timestamp"].max() == _bar_open(tf, clock())


def test_old_newest_bar_returns_status_stale(clock):
    tf = "1h"
    ex = TailExchange(clock, end=_bar_open(tf, clock()) - pd.Timedelta(hours=3))  # 3 h > 8100 s
    result = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)

    assert result.status == "stale"
    assert not result.df.empty


def test_failed_fetch_keeps_cache_and_fetched_at(clock):
    tf = "1h"
    stamp = clock() - pd.Timedelta(hours=2)
    cache.write_ohlcv("BTC", tf, _frame(_bar_open(tf, clock()) - pd.Timedelta(hours=2), 120, tf), fetched_at=stamp)
    before = cache.ohlcv_path("BTC", tf).read_bytes()
    ex = TailExchange(clock, raise_on_fetch=ccxt.NetworkError("down"))

    result = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)

    assert result.status == "unavailable"
    assert len(result.df) == 120
    assert cache.ohlcv_path("BTC", tf).read_bytes() == before
    assert _fetched_at("BTC", tf) == stamp
    assert result.fetched_at == stamp


def test_explicit_since_path_unchanged_for_backfill(clock):
    # backfill_pairs_universe.py passes since/limit explicitly and treats any
    # status other than "ok" as failure; it feeds old (May 2024) bars.
    tf = "1d"
    end = pd.Timestamp("2024-05-31T00:00:00Z")
    ex = TailExchange(clock, end=end, history=400)
    since = _ms(pd.Timestamp("2024-01-01T00:00:00Z"))

    result = ccxt_adapter.fetch_ohlcv("BTC", tf, since=since, limit=5000, exchange=ex)

    assert ex.calls == [{"symbol": "BTC", "timeframe": tf, "since": since, "limit": 5000}]
    assert result.status == "ok", "the explicit-since path must never report stale"
    assert result.df["timestamp"].max() == end
    assert result.df["timestamp"].min() == pd.Timestamp("2024-01-01T00:00:00Z")


def test_one_week_derivation_uses_daily_fetched_at(clock):
    ex = TailExchange(clock)
    result = ccxt_adapter.fetch_ohlcv("BTC", "1w", exchange=ex)

    daily_stamp = _fetched_at("BTC", "1d")
    assert daily_stamp == clock()
    assert result.fetched_at == daily_stamp
    assert _fetched_at("BTC", "1w") == daily_stamp
    assert not result.df.empty


def test_empty_tail_response_keeps_cache_and_fetched_at(clock):
    tf = "1h"
    stamp = clock() - pd.Timedelta(hours=1)
    cache.write_ohlcv("BTC", tf, _frame(_bar_open(tf, clock()), 120, tf), fetched_at=stamp)
    before = cache.ohlcv_path("BTC", tf).read_bytes()
    ex = TailExchange(clock, empty=True)

    result = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)

    assert len(ex.calls) == 1
    assert cache.ohlcv_path("BTC", tf).read_bytes() == before
    assert _fetched_at("BTC", tf) == stamp
    assert result.fetched_at == stamp
    assert result.status == "ok"  # B5 on the cached newest bar (the current one)
    assert len(result.df) == 120


def test_one_day_gap_keeps_deep_history_and_notes_gap_kept(clock):
    tf = "1d"
    old_end = _bar_open(tf, clock()) - pd.Timedelta(days=700)
    cache.write_ohlcv("BTC", tf, _frame(old_end, 600, tf), fetched_at=old_end)
    ex = TailExchange(clock)

    result = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=ex)

    assert result.note == "gap-kept"
    assert len(result.df) == 600 + 500
    assert result.df["timestamp"].min() == old_end - pd.Timedelta(days=599)
    assert result.df["timestamp"].max() == _bar_open(tf, clock())
    assert result.status == "ok"
