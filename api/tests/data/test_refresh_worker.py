"""T35 / S8: the in-process background refresh worker (B9, D3, D7).

Fake clock, fake exchange, no network, and nothing sleeps: loops run on an
injected wait Event that advances the fake clock instead of blocking.
"""
from __future__ import annotations

import threading
import time

import pandas as pd
import pytest

from api.data import cache, ccxt_adapter, freshness, refresh_worker
from api.data import watchlist as watchlist_store
from api.data.refresh_worker import RefreshWorker

NOW = pd.Timestamp("2026-10-04T12:07:00Z")
PLAN_TIMEFRAMES = ("15m", "1h", "4h", "1d")


def _bars(timeframe: str, end: pd.Timestamp, count: int = 120) -> list[list[float]]:
    step = freshness.TIMEFRAME_SECONDS[timeframe] * 1000
    last = int(freshness.current_bar_open(timeframe, end).timestamp() * 1000)
    first = last - (count - 1) * step
    return [[first + i * step, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 10.0] for i in range(count)]


class FakeExchange:
    id = "fakeex"
    markets: dict = {}

    def __init__(self, end: pd.Timestamp = NOW):
        self.end = end
        self.calls: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        with self._lock:
            self.calls.append((symbol, timeframe))
        return _bars(timeframe, self.end)


class Result:
    def __init__(self, status: str):
        self.status = status


class FakeWait:
    """Stands in for the wake Event: `wait` advances the fake clock by its
    timeout and returns False (timed out); stops the worker after `limit`."""

    def __init__(self, clock: list[pd.Timestamp], limit: int, worker_ref: list):
        self.clock = clock
        self.limit = limit
        self.worker_ref = worker_ref
        self.timeouts: list[float] = []
        self._flag = False

    def wait(self, timeout=None):
        self.timeouts.append(round(timeout, 3))
        self.clock[0] = self.clock[0] + pd.Timedelta(seconds=timeout)
        if len(self.timeouts) > self.limit:
            self.worker_ref[0]._stopping.set()
        return False

    def set(self):
        self._flag = True

    def clear(self):
        self._flag = False

    def is_set(self):
        return self._flag


@pytest.fixture
def adapter_env(isolated_cache, monkeypatch):
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: NOW)
    ccxt_adapter.reset_clock_skew()
    ccxt_adapter.reset_exchange_cache()
    ccxt_adapter.set_refresh_hook(None)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda path=None: ["ETH"])
    yield isolated_cache
    ccxt_adapter.set_refresh_hook(None)
    ccxt_adapter.reset_exchange_cache()
    ccxt_adapter.reset_clock_skew()
    refresh_worker.stop_worker()


def _plan(symbols=("BTC", "ETH", "HYPE")) -> set[tuple[str, str]]:
    return {(s, tf) for s in symbols for tf in PLAN_TIMEFRAMES}


def test_tick_refreshes_watchlist_plus_benchmarks_all_timeframes(adapter_env):
    ex = FakeExchange()
    worker = RefreshWorker(clock=lambda: NOW, exchange=ex)
    counts = worker.run_tick()

    assert set(ex.calls) == _plan()
    assert len(ex.calls) == 12
    assert counts["ok"] == 12 and counts["failed"] == 0
    assert worker.last_tick_ok == 12 and worker.last_tick_failed == 0
    for sym in ("BTC", "ETH", "HYPE"):
        for tf in (*PLAN_TIMEFRAMES, "1w"):
            assert cache.ohlcv_path(sym, tf).exists(), (sym, tf)


def test_tick_skips_fresh_pairs(adapter_env, monkeypatch):
    ex = FakeExchange()
    worker = RefreshWorker(clock=lambda: NOW, exchange=ex)
    worker.run_tick()
    ex.calls.clear()

    counts = worker.run_tick()
    assert ex.calls == []
    assert counts["ok"] == 0 and counts["failed"] == 0 and counts["skipped"] >= 12
    assert worker.delay_seconds == worker.interval_seconds  # nothing failed: no backoff

    # Once one pair's forming TTL (15m: 180 s) has passed, only it is refetched.
    later = NOW + pd.Timedelta(seconds=200)
    worker._clock = lambda: later
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: later)
    worker.run_tick()
    assert set(ex.calls) == {("BTC", "15m"), ("ETH", "15m"), ("HYPE", "15m")}


def test_one_week_is_derived_not_fetched(adapter_env):
    ex = FakeExchange()
    worker = RefreshWorker(clock=lambda: NOW, exchange=ex, symbols=lambda: [])
    worker.run_tick()

    assert all(tf != "1w" for _, tf in ex.calls)
    weekly = cache.read_ohlcv("BTC", "1w")
    assert not weekly.empty
    assert set(weekly["timestamp"].dt.dayofweek) == {0}  # Monday-open (ADR-5)
    assert cache.read_fetched_at("BTC", "1w") == cache.read_fetched_at("BTC", "1d")


def test_per_pair_lock_never_two_refreshers_on_one_file(adapter_env):
    entered, release = threading.Event(), threading.Event()
    active, peak, calls = [0], [0], []
    guard = threading.Lock()

    def slow_fetch(symbol, timeframe, exchange=None):
        with guard:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            calls.append((symbol, timeframe))
        entered.set()
        release.wait(5)
        with guard:
            active[0] -= 1
        return Result("ok")

    worker = RefreshWorker(clock=lambda: NOW, fetch=slow_fetch, is_fresh=lambda *a: False)
    barrier = threading.Barrier(2)
    results: list[list[str]] = []
    one_done = threading.Event()

    def run():
        barrier.wait(5)
        out = worker.refresh_pair("BTC", "15m")
        results.append(out)
        one_done.set()

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    assert one_done.wait(5)  # the loser returns at once, without waiting
    assert entered.wait(5)
    release.set()
    for t in threads:
        t.join(5)

    assert sorted(results) == [["busy"], ["ok"]]
    assert calls == [("BTC", "15m")]
    assert peak[0] == 1


def test_request_refresh_dedupes_and_never_blocks(adapter_env):
    worker = RefreshWorker(clock=lambda: NOW, fetch=lambda *a, **k: Result("ok"))
    # Even with a run in progress and the pair locked, enqueueing is instant.
    worker._run_mutex.acquire()
    worker._pair_lock(("BTC", "1h")).acquire()
    try:
        started = time.monotonic()
        assert worker.request_refresh("BTC", "1h") is True
        assert worker.request_refresh("btc", "1h") is False
        assert worker.request_refresh("ETH", "1h") is True
        assert time.monotonic() - started < 0.5
    finally:
        worker._pair_lock(("BTC", "1h")).release()
        worker._run_mutex.release()
    assert worker.queue_depth == 2
    assert worker._wake.is_set()


def test_stale_on_load_queues_refresh_and_board_reads_cache(adapter_env, monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app

    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda path=None: ["BTC"])
    old = NOW - pd.Timedelta(days=3)
    for tf in PLAN_TIMEFRAMES:
        cache.write_ohlcv("BTC", tf, ccxt_adapter._raw_to_df(_bars(tf, old), "fakeex"), fetched_at=old)
    cached_last = cache.read_ohlcv("BTC", "1d")["timestamp"].max()

    ex = FakeExchange()
    refreshed = threading.Event()

    def fetch(symbol, timeframe, exchange=None):
        result = ccxt_adapter.fetch_ohlcv(symbol, timeframe, exchange=ex)
        if (symbol, timeframe) == ("BTC", "1d"):
            refreshed.set()
        return result

    worker = RefreshWorker(clock=lambda: NOW, fetch=fetch, first_delay_seconds=3600, interval_seconds=3600)
    refresh_worker.install_worker(worker)
    # Hold the run mutex so the woken loop cannot refresh during the request.
    worker._run_mutex.acquire()
    try:
        response = TestClient(app).get("/api/screener/board", params={"timeframe": "1d"})
        assert response.status_code == 200
        assert ex.calls == []  # the board read the cache only
        assert ("BTC", "1d") in worker._queued
        assert worker._wake.is_set()
    finally:
        worker._run_mutex.release()

    # The queued refresh runs between ticks; the next read sees newer bars.
    assert refreshed.wait(5)
    refresh_worker.stop_worker()
    assert ("BTC", "1d") in ex.calls
    assert cache.read_ohlcv("BTC", "1d")["timestamp"].max() > cached_last


def test_cache_only_mode_makes_zero_exchange_calls(adapter_env, monkeypatch):
    old = NOW - pd.Timedelta(days=3)
    cache.write_ohlcv("BTC", "1h", ccxt_adapter._raw_to_df(_bars("1h", old), "fakeex"), fetched_at=old)
    ccxt_adapter.fetch_ohlcv("SOL", "1h", exchange=FakeExchange())  # fresh at NOW
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: NOW + pd.Timedelta(seconds=10))

    def no_exchange():
        raise AssertionError("cache-only read reached the exchange")

    monkeypatch.setattr(ccxt_adapter, "_exchange", no_exchange)
    hooked: list[tuple[str, str]] = []
    ccxt_adapter.set_refresh_hook(lambda s, tf: hooked.append((s, tf)))
    ex = FakeExchange()

    with ccxt_adapter.cached_reads_only():
        stale = ccxt_adapter.fetch_ohlcv("BTC", "1h", exchange=ex)
        missing = ccxt_adapter.fetch_ohlcv("ETH", "4h")
        fresh = ccxt_adapter.fetch_ohlcv("SOL", "1h")
        weekly = ccxt_adapter.fetch_ohlcv("ETH", "1w")

    assert ex.calls == []
    assert not stale.df.empty and stale.status == "stale" and stale.note == "refresh-queued"
    assert missing.df.empty and missing.status == "unavailable" and missing.note == "refresh-queued"
    assert fresh.status == "ok" and fresh.note is None
    assert weekly.status == "unavailable"
    assert hooked == [("BTC", "1h"), ("ETH", "4h"), ("ETH", "1d")]

    # Outside the context: S1 fetch-through, the hook is not consulted.
    hooked.clear()
    through = ccxt_adapter.fetch_ohlcv("BTC", "1h", exchange=ex)
    assert ex.calls == [("BTC", "1h")] and through.note is None and hooked == []


def test_one_pair_failure_does_not_stop_the_tick(adapter_env):
    seen: list[tuple[str, str]] = []

    def fetch(symbol, timeframe, exchange=None):
        seen.append((symbol, timeframe))
        if (symbol, timeframe) == ("ETH", "1h"):
            raise RuntimeError("boom")
        return Result("ok")

    worker = RefreshWorker(clock=lambda: NOW, fetch=fetch, is_fresh=lambda *a: False)
    counts = worker.run_tick()

    assert {p for p in seen if p[1] != "1w"} == _plan()
    assert counts["ok"] == 11 and counts["failed"] == 1
    assert worker.last_tick_failed == 1
    assert worker.delay_seconds == worker.interval_seconds


def test_unavailable_streak_backs_off_and_resets_on_success(adapter_env):
    status = ["unavailable"]
    worker = RefreshWorker(
        clock=lambda: NOW,
        fetch=lambda *a, **k: Result(status[0]),
        is_fresh=lambda *a: False,
        interval_seconds=900,
    )
    delays = []
    for _ in range(3):
        worker.run_tick()
        delays.append((worker.delay_seconds, worker.backoff_seconds))
    status[0] = "ok"
    worker.run_tick()
    delays.append((worker.delay_seconds, worker.backoff_seconds))

    assert delays == [(1800, 1800), (3600, 3600), (3600, 3600), (900, 0.0)]


def test_loop_ticks_every_interval_with_fake_clock(adapter_env):
    clock = [NOW]
    ref: list = []
    wait = FakeWait(clock, limit=3, worker_ref=ref)
    worker = RefreshWorker(
        clock=lambda: clock[0],
        wake=wait,
        fetch=lambda *a, **k: Result("ok"),
        is_fresh=lambda *a: False,
        interval_seconds=900,
    )
    ref.append(worker)
    started = []
    original = worker.run_tick

    def tick():
        started.append(clock[0])
        return original()

    worker.run_tick = tick
    worker._loop()

    assert wait.timeouts == [20.0, 900.0, 900.0, 900.0]
    assert worker.ticks == 3
    assert [(b - a).total_seconds() for a, b in zip(started, started[1:])] == [900.0, 900.0]
    assert worker.next_tick_at == started[-1] + pd.Timedelta(seconds=900)


def test_stop_joins_threads_and_is_idempotent(adapter_env):
    worker = RefreshWorker(clock=lambda: NOW, first_delay_seconds=3600, fetch=lambda *a, **k: Result("ok"))
    worker.start()
    worker.start()  # idempotent: still one loop thread
    loops = [t for t in threading.enumerate() if t.name == "refresh-worker"]
    assert len(loops) == 1 and worker.running

    worker.stop(timeout=5)
    assert not worker.running
    assert not loops[0].is_alive()
    worker.stop(timeout=5)  # second stop is a no-op
    assert not any(t.name.startswith("refresh-") and t.is_alive() for t in threading.enumerate())


def test_worker_exception_never_escapes_the_loop(adapter_env):
    clock = [NOW]
    ref: list = []
    wait = FakeWait(clock, limit=3, worker_ref=ref)

    def bad_symbols():
        raise RuntimeError("watchlist unreadable")

    def bad_retry():
        raise RuntimeError("latch")

    worker = RefreshWorker(
        clock=lambda: clock[0],
        wake=wait,
        fetch=lambda *a, **k: Result("ok"),
        symbols=bad_symbols,
        retry_markets=bad_retry,
        is_fresh=lambda *a: False,
        interval_seconds=900,
    )
    ref.append(worker)
    calls = [0]
    original = worker.run_tick

    def flaky_tick():
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError("tick blew up")
        return original()

    worker.run_tick = flaky_tick
    worker._loop()  # returns only because the fake wait stopped it

    assert calls[0] == 3
    assert wait.timeouts == [20.0, 900.0, 900.0, 900.0]
    # The broken watchlist falls back to the benchmarks; the tick still ran.
    assert worker.ticks == 2 and worker.last_tick_ok == 8


def test_markets_latch_retried_once_per_tick_and_backoff_resets(adapter_env, monkeypatch):
    loads = [0]

    class FlakyMarketsExchange(FakeExchange):
        def load_markets(self):
            loads[0] += 1
            if loads[0] <= 2:  # the offline start and the first tick's retry
                raise ccxt_adapter.ccxt.NetworkError("offline")
            self.markets = {}
            return {}

    monkeypatch.setattr(ccxt_adapter.ccxt, "hyperliquid", lambda *a, **k: FlakyMarketsExchange())
    # Offline start: the latch is already set before the first tick.
    assert ccxt_adapter._exchange() is None
    assert ccxt_adapter._markets_unavailable is True and loads[0] == 1

    cleared: list[bool] = []

    def retry():
        cleared.append(ccxt_adapter.retry_markets_if_latched())

    clock = [NOW]
    worker = RefreshWorker(clock=lambda: clock[0], retry_markets=retry, symbols=lambda: [], interval_seconds=900)

    worker.run_tick()  # latch cleared once; this tick's single load fails again
    assert cleared == [True] and loads[0] == 2  # one load per tick, not per pair
    assert worker.last_tick_ok == 0 and worker.last_tick_failed == 8
    assert worker.delay_seconds == 1800

    worker.run_tick()  # latch cleared once more; markets load, fetches succeed
    assert cleared == [True, True] and loads[0] == 3
    assert worker.last_tick_ok == 8 and worker.last_tick_failed == 0
    assert worker.delay_seconds == 900  # backoff reset by the successful tick

    clock[0] = NOW + pd.Timedelta(seconds=10)
    worker.run_tick()  # no latch: nothing cleared, no extra load
    assert cleared[-1] is False and loads[0] == 3


def test_now_and_load_requests_wake_the_loop_without_sleeping(adapter_env):
    seen: list[tuple[str, str]] = []
    got_queued, got_tick = threading.Event(), threading.Event()

    def fetch(symbol, timeframe, exchange=None):
        seen.append((symbol, timeframe))
        if (symbol, timeframe) == ("SOL", "1h"):
            got_queued.set()
        if len({p for p in seen if p[1] != "1w"} & _plan()) == 12:
            got_tick.set()
        return Result("ok")

    worker = RefreshWorker(
        clock=lambda: NOW,
        fetch=fetch,
        is_fresh=lambda *a: False,
        first_delay_seconds=3600,
        interval_seconds=3600,
    )
    worker.start()
    try:
        started = time.monotonic()
        worker.request_refresh("SOL", "1h")  # a load-triggered refresh
        assert got_queued.wait(5)
        assert seen == [("SOL", "1h")]  # only the queued pair, not a tick
        assert worker.ticks == 0

        assert worker.request_now() is True  # /now wakes one full run
        assert got_tick.wait(5)
        assert time.monotonic() - started < 5  # never waited for the 3600 s tick
    finally:
        worker.stop(timeout=5)
    assert worker.ticks == 1
