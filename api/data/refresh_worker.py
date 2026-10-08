"""In-process background OHLCV refresh worker (T35 / S8, decisions B9, D3, D7).

The API refreshes its own cache, so a page load only reads it: while the
worker runs, board and chart reads are cache-only
(`ccxt_adapter.cached_reads_only`) and queue a refresh for any pair that is
not fresh. The web client's 10 s timeout is unchanged (D7).

* A daemon thread loops: first tick `FIRST_TICK_DELAY_SECONDS` after start,
  then every `SCREENER_REFRESH_INTERVAL_SECONDS` (default 900). A tick plans
  sorted(watchlist + BTC + HYPE) x (15m, 1h, 4h, 1d) and fetches only pairs
  that fail `freshness.cache_is_fresh`; `1w` is derived by
  `fetch_ohlcv(sym, "1w")` right after the coin's `1d`, never fetched.
* A pool of `POOL_SIZE` threads runs the pairs. One non-blocking lock per
  (symbol, timeframe): a busy pair is skipped, never refreshed twice at once.
  Live calls still serialize on `ccxt_adapter._exchange_lock`.
* The loop waits on a wake `Event` with the delay as timeout.
  `request_refresh` (cache-only reads) and `request_now` (`POST
  /api/refresh/now`) set it, so a woken run happens between ticks; the
  Event is a flag, so at most one run is pending.
* Failure isolation: every pair runs inside `try/except`, and so does each
  loop iteration; nothing leaves the thread. Logs carry no values or secrets.
* Backoff: a tick with no `ok`/`stale` pair and at least one `unavailable`
  doubles the next delay (cap `MAX_BACKOFF_SECONDS`); any success resets it.
* Market-load recovery (N1): each tick starts with
  `ccxt_adapter.retry_markets_if_latched()`, so one offline start does not
  stop refreshing until the API restarts.
* `SCREENER_REFRESH_WORKER` is tri-state: `0` off, `1` forces on, unset on.
  A `SCREENER_CACHE_ROOT` override does not disable it.

Time, the wait Event, the fetch function and the exchange are injectable, so
tests run on a fake clock with a fake exchange and never sleep.
"""
from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from typing import Callable, Iterator

import pandas as pd

from api.data import cache, ccxt_adapter, freshness
from api.data import watchlist as watchlist_store

logger = logging.getLogger(__name__)

ENV_FLAG = "SCREENER_REFRESH_WORKER"
ENV_INTERVAL = "SCREENER_REFRESH_INTERVAL_SECONDS"

BENCHMARK_SYMBOLS = ("BTC", "HYPE")
TICK_TIMEFRAMES = ("15m", "1h", "4h", "1d")
DEFAULT_INTERVAL_SECONDS = 900.0
FIRST_TICK_DELAY_SECONDS = 20.0
MAX_BACKOFF_SECONDS = 3600.0
POOL_SIZE = 4
STOP_JOIN_TIMEOUT_SECONDS = 10.0

_SUCCESS = {"ok", "stale"}


def _default_fetch(symbol: str, timeframe: str, exchange=None):
    # Looked up at call time so tests can monkeypatch the adapter.
    return ccxt_adapter.fetch_ohlcv(symbol, timeframe, exchange=exchange)


def _default_symbols() -> list[str]:
    return list(watchlist_store.read_watchlist())


def pair_is_fresh(symbol: str, timeframe: str, now: pd.Timestamp) -> bool:
    """The worker's skip rule: a cached file whose fetch time is fresh (B4).
    A missing file is never fresh. `1w` has no forming TTL of its own and is
    judged by the daily rule it is derived from."""
    if not cache.ohlcv_path(symbol, timeframe).exists():
        return False
    rule = "1d" if timeframe == "1w" else timeframe
    return freshness.cache_is_fresh(cache.read_fetched_at(symbol, timeframe), rule, now)


class RefreshWorker:
    def __init__(
        self,
        *,
        interval_seconds: float | None = None,
        first_delay_seconds: float = FIRST_TICK_DELAY_SECONDS,
        clock: Callable[[], pd.Timestamp] | None = None,
        wake: threading.Event | None = None,
        fetch: Callable[..., object] | None = None,
        exchange=None,
        symbols: Callable[[], list[str]] | None = None,
        is_fresh: Callable[[str, str, pd.Timestamp], bool] | None = None,
        retry_markets: Callable[[], object] | None = None,
        pool_size: int = POOL_SIZE,
    ) -> None:
        self.interval_seconds = float(interval_seconds or DEFAULT_INTERVAL_SECONDS)
        self.first_delay_seconds = float(first_delay_seconds)
        self._clock = clock or (lambda: ccxt_adapter._now())
        self._wake = wake if wake is not None else threading.Event()
        self._fetch = fetch or _default_fetch
        self._exchange = exchange
        self._symbols = symbols or _default_symbols
        self._is_fresh = is_fresh or pair_is_fresh
        self._retry_markets = retry_markets or ccxt_adapter.retry_markets_if_latched
        self._pool_size = pool_size

        self._state_lock = threading.Lock()
        self._pair_locks: dict[tuple[str, str], threading.Lock] = {}
        self._queued: set[tuple[str, str]] = set()
        self._now_requested = False
        # Pairs whose fetch failed since the last tick: woken drains skip them
        # until the next (backoff-aware) tick, so repeated page loads cannot
        # turn a failing pair into a stream of exchange calls.
        self._failed_since_tick: set[tuple[str, str]] = set()
        # Held for the whole of one run (tick or drain).
        self._run_mutex = threading.Lock()

        self._thread: threading.Thread | None = None
        self._pool: ThreadPoolExecutor | None = None
        self._stopping = threading.Event()

        self.delay_seconds = self.interval_seconds
        self.ticks = 0
        self.last_tick_started: pd.Timestamp | None = None
        self.last_tick_finished: pd.Timestamp | None = None
        self.last_tick_ok = 0
        self.last_tick_failed = 0
        self.next_tick_at: pd.Timestamp | None = None

    # ------------------------------------------------------------ lifecycle
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stopping.is_set()

    def start(self) -> None:
        with self._state_lock:
            if self._thread is not None:
                return
            self._stopping.clear()
            self._pool = ThreadPoolExecutor(max_workers=self._pool_size, thread_name_prefix="refresh-pair")
            self._thread = threading.Thread(target=self._loop, name="refresh-worker", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = STOP_JOIN_TIMEOUT_SECONDS) -> None:
        """Stop the loop and join its threads (idempotent)."""
        self._stopping.set()
        self._wake.set()
        with self._state_lock:
            thread, pool = self._thread, self._pool
            self._pool = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        if pool is not None:
            # Never block shutdown on an in-flight ccxt call.
            pool.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------- requests
    def request_refresh(self, symbol: str, timeframe: str) -> bool:
        """Queue one pair and wake the loop. Non-blocking and deduplicated:
        returns False when the pair is already queued."""
        key = (symbol.upper(), timeframe)
        with self._state_lock:
            if key in self._queued:
                return False
            self._queued.add(key)
        self._wake.set()
        return True

    def request_now(self) -> bool:
        """Wake one full run. Returns False when one is already pending."""
        with self._state_lock:
            already = self._now_requested
            self._now_requested = True
        self._wake.set()
        return not already

    @property
    def queue_depth(self) -> int:
        with self._state_lock:
            return len(self._queued)

    @property
    def backoff_seconds(self) -> float:
        return self.delay_seconds if self.delay_seconds > self.interval_seconds else 0.0

    # ----------------------------------------------------------------- loop
    def _next_at(self, delay: float) -> pd.Timestamp | None:
        try:
            return self._clock() + pd.Timedelta(seconds=delay)
        except Exception:
            return None

    def _remaining(self, fallback: float) -> float:
        try:
            return (self.next_tick_at - self._clock()).total_seconds()
        except Exception:
            return fallback

    def _loop(self) -> None:
        delay = self.first_delay_seconds
        self.next_tick_at = self._next_at(delay)
        while not self._stopping.is_set():
            try:
                woken = self._wake.wait(max(delay, 0.0))
                if self._stopping.is_set():
                    break
                with self._run_mutex:
                    self._wake.clear()
                    with self._state_lock:
                        full = (not woken) or self._now_requested
                        self._now_requested = False
                    if full:
                        self.run_tick()
                        self.next_tick_at = self._next_at(self.delay_seconds)
                    else:
                        self.drain_queue()
                delay = self._remaining(self.delay_seconds)
            except Exception as exc:  # the loop itself must never die
                logger.warning("refresh loop iteration failed: %s", type(exc).__name__)
                delay = self.interval_seconds
                self.next_tick_at = self._next_at(delay)

    def _take_queue(self) -> list[tuple[str, str]]:
        with self._state_lock:
            queued = sorted(self._queued)
            self._queued.clear()
        return queued

    def run_tick(self) -> dict[str, int]:
        """One full refresh: the plan plus anything queued."""
        self.last_tick_started = self._clock()
        with self._state_lock:
            self._failed_since_tick.clear()
        try:
            self._retry_markets()
        except Exception as exc:
            logger.warning("market latch retry failed: %s", type(exc).__name__)
        try:
            symbols = list(self._symbols())
        except Exception as exc:
            logger.warning("refresh plan failed: %s", type(exc).__name__)
            symbols = []
        coins = sorted({s.upper() for s in symbols} | set(BENCHMARK_SYMBOLS))
        plan = [(s, tf) for s in coins for tf in TICK_TIMEFRAMES]
        for key in self._take_queue():
            if key not in plan:
                plan.append(key)
        counts = self._run_pairs(plan)

        self.ticks += 1
        self.last_tick_ok = counts["ok"]
        self.last_tick_failed = counts["failed"]
        self.last_tick_finished = self._clock()
        if counts["ok"] == 0 and counts["unavailable"] > 0:
            self.delay_seconds = min(max(self.delay_seconds, self.interval_seconds) * 2, MAX_BACKOFF_SECONDS)
        elif counts["ok"] > 0:
            self.delay_seconds = self.interval_seconds
        return counts

    def drain_queue(self) -> dict[str, int]:
        """Refresh only the queued pairs (a woken run between ticks). Pairs
        that failed since the last tick wait for the next tick."""
        queued = self._take_queue()
        with self._state_lock:
            pairs = [key for key in queued if key not in self._failed_since_tick]
        return self._run_pairs(pairs)

    # ---------------------------------------------------------------- pairs
    def _pair_lock(self, key: tuple[str, str]) -> threading.Lock:
        with self._state_lock:
            return self._pair_locks.setdefault(key, threading.Lock())

    def _run_pairs(self, pairs: list[tuple[str, str]]) -> dict[str, int]:
        counts = {"ok": 0, "failed": 0, "unavailable": 0, "skipped": 0}
        if not pairs:
            return counts
        pool = self._pool
        if pool is None:
            outcomes = [self.refresh_pair(s, tf) for s, tf in pairs]
        else:
            outcomes = list(pool.map(lambda p: self.refresh_pair(*p), pairs))
        for statuses in outcomes:
            for status in statuses:
                if status in _SUCCESS:
                    counts["ok"] += 1
                elif status in ("fresh", "busy"):
                    counts["skipped"] += 1
                else:
                    counts["failed"] += 1
                    if status == "unavailable":
                        counts["unavailable"] += 1
        return counts

    def _refresh_one(self, symbol: str, timeframe: str, force: bool = False) -> str:
        if self._stopping.is_set():
            return "busy"
        lock = self._pair_lock((symbol, timeframe))
        if not lock.acquire(blocking=False):
            return "busy"
        try:
            if not force and self._is_fresh(symbol, timeframe, self._clock()):
                return "fresh"
            result = self._fetch(symbol, timeframe, exchange=self._exchange)
            status = str(getattr(result, "status", "unavailable"))
        except Exception as exc:
            logger.warning("refresh %s %s failed: %s", symbol, timeframe, type(exc).__name__)
            status = "error"
        finally:
            lock.release()
        if status not in _SUCCESS:
            with self._state_lock:
                self._failed_since_tick.add((symbol, timeframe))
        return status

    def refresh_pair(self, symbol: str, timeframe: str) -> list[str]:
        """Refresh one pair; `1d` is followed by its derived `1w`. Returns the
        statuses produced ("fresh"/"busy" for skips, "error" for exceptions)."""
        symbol = symbol.upper()
        if timeframe == "1w":
            return [self._refresh_one(symbol, "1w")]
        statuses = [self._refresh_one(symbol, timeframe)]
        if timeframe == "1d":
            fetched_daily = statuses[0] in _SUCCESS
            if fetched_daily or statuses[0] == "fresh":
                weekly = self._refresh_one(symbol, "1w", force=fetched_daily)
                # The weekly leg is a derivation: count only its failures.
                if weekly not in _SUCCESS:
                    statuses.append(weekly)
        return statuses


# --------------------------------------------------------------------------
# Process-wide registry (the app lifespan owns it)
# --------------------------------------------------------------------------
_registry_lock = threading.Lock()
_worker: RefreshWorker | None = None
_disabled_reason: str | None = "not-started"


def enabled_from_env(env=None) -> tuple[bool, str | None]:
    """Tri-state `SCREENER_REFRESH_WORKER`: `0` off, `1` forces on, unset on."""
    env = os.environ if env is None else env
    raw = env.get(ENV_FLAG)
    if raw is not None and raw.strip() == "0":
        return False, f"{ENV_FLAG}=0"
    return True, None


def interval_from_env(env=None) -> float:
    env = os.environ if env is None else env
    raw = env.get(ENV_INTERVAL)
    try:
        value = float(raw) if raw else DEFAULT_INTERVAL_SECONDS
    except ValueError:
        value = DEFAULT_INTERVAL_SECONDS
    return value if value > 0 else DEFAULT_INTERVAL_SECONDS


def install_worker(worker: RefreshWorker, start: bool = True) -> RefreshWorker:
    """Register `worker` as the process worker and hook it into the adapter.
    A previously installed worker is stopped first."""
    global _worker, _disabled_reason
    with _registry_lock:
        previous, _worker = _worker, worker
        _disabled_reason = None
    if previous is not None and previous is not worker:
        previous.stop()
    ccxt_adapter.set_refresh_hook(worker.request_refresh)
    if start:
        worker.start()
    return worker


def start_from_env(env=None) -> RefreshWorker | None:
    """Lifespan entry: start the worker unless the env switches it off."""
    global _disabled_reason
    enabled, reason = enabled_from_env(env)
    if not enabled:
        with _registry_lock:
            _disabled_reason = reason
        return None
    try:
        return install_worker(RefreshWorker(interval_seconds=interval_from_env(env)))
    except Exception as exc:
        # A worker that cannot start must not take the API down: reads fall
        # back to the S1 fetch-through.
        logger.warning("refresh worker failed to start: %s", type(exc).__name__)
        stop_worker(reason="start-failed")
        return None


def stop_worker(reason: str = "stopped") -> None:
    """Lifespan exit: stop and unregister the worker (idempotent)."""
    global _worker, _disabled_reason
    with _registry_lock:
        worker, _worker = _worker, None
        if worker is not None or _disabled_reason is None:
            _disabled_reason = reason
    ccxt_adapter.set_refresh_hook(None)
    if worker is not None:
        worker.stop()


def current_worker() -> RefreshWorker | None:
    return _worker


def disabled_reason() -> str | None:
    worker = _worker
    if worker is not None and worker.running:
        return None
    return _disabled_reason or "not-running"


def is_running() -> bool:
    worker = _worker
    return worker is not None and worker.running


@contextmanager
def reads_cache_only_if_running() -> Iterator[None]:
    """Cache-only reads while the worker runs; S1 fetch-through otherwise."""
    with (ccxt_adapter.cached_reads_only() if is_running() else nullcontext()):
        yield


def status() -> dict:
    worker = _worker
    running = worker is not None and worker.running
    body = {
        "running": running,
        "disabled_reason": None if running else disabled_reason(),
        "interval_seconds": worker.interval_seconds if worker else interval_from_env(),
        "last_tick_started": freshness.iso_z(worker.last_tick_started) if worker else None,
        "last_tick_finished": freshness.iso_z(worker.last_tick_finished) if worker else None,
        "last_tick_ok": worker.last_tick_ok if worker else 0,
        "last_tick_failed": worker.last_tick_failed if worker else 0,
        "next_tick_at": freshness.iso_z(worker.next_tick_at) if running else None,
        "queue_depth": worker.queue_depth if worker else 0,
        "backoff_seconds": worker.backoff_seconds if worker else 0.0,
    }
    return body
