"""Equities cache refresh (S9A) and its market-hours tick (S9E).

Separate from the crypto refresh worker (D-5): own module, own status, same
JSON keys, so `refresh_worker.py` is untouched.

* `refresh_ticker` fetches one ticker through `fetch` (default
  `lse_adapter.refresh_equity`, looked up at call time) and never raises.
* `refresh_all` runs the stored tickers one by one under one module lock
  (`PASS_LOCK`, which the S9E tick reuses), isolating each ticker; it never
  raises.
* `request_refresh_now` runs a pass on a background thread. A request that
  arrives during a pass sets a pending flag and exactly one more pass
  follows, so a ticker added mid-pass is not missed.
* `EquitiesRefreshWorker` (S9E) is a daemon thread tied to the US close:
  first tick `FIRST_TICK_DELAY_SECONDS` after start only when some ticker's
  newest bar is behind `last_due_session` (catch-up), otherwise it sleeps
  until `equities_calendar.next_refresh_at`. A tick runs `refresh_all`; a
  ticker still behind the session the tick is for is retried every
  `RETRY_SECONDS` up to `MAX_RETRIES` times, then the worker waits for the
  next close. A tick where every ticker failed doubles the retry wait (cap
  `MAX_BACKOFF_SECONDS`); a success resets it. `next_tick_at` is the stored
  wake instant, never recomputed per status call, so a missed tick can read
  overdue while a weekend or holiday never does.
* `start_from_env` / `stop_worker` are the app lifespan hooks: no
  `LSE_API_KEY` or `SCREENER_REFRESH_WORKER=0` keeps the worker off.
* `status` reports the crypto status keys plus `last_bar_date`.

Logs carry only a ticker and an exception class name: never the key, a URL
or exception text.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import date
from typing import Callable

import pandas as pd

from api.data import equities_calendar, equities_fallback, equities_store, lse_adapter, refresh_worker
from api.data.freshness import iso_z

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 86400
FIRST_TICK_DELAY_SECONDS = 20.0
RETRY_SECONDS = 1800.0
MAX_RETRIES = 3
MAX_BACKOFF_SECONDS = 3600.0
STOP_JOIN_TIMEOUT_SECONDS = 10.0
KEY_ENV = "LSE_API_KEY"
_SUCCESS = {"ok", "stale"}

# One pass at a time (manual, add-triggered or the S9E tick).
PASS_LOCK = threading.Lock()

_state_lock = threading.Lock()
_running = False
_pending = False
_idle = threading.Event()
_idle.set()


def _default_fetch(ticker: str):
    """LSE first; Hyperliquid, then a reconstruction such as DXY (`equities_fallback`), when LSE cannot serve the ticker or its bars are stale.
    The fallback counts as the result only when it fetched bars, so a failure still reports LSE's reason."""
    result = lse_adapter.refresh_equity(ticker)
    if not equities_fallback.needs_fallback(result):
        return result
    fallback = equities_fallback.refresh_equity_fallback(ticker)
    return fallback if fallback.status == "ok" else result


def refresh_ticker(ticker: str, fetch: Callable[[str], object] | None = None):
    """One ticker; the fetch result, or None when the fetch raised."""
    fetch = fetch or _default_fetch
    try:
        return fetch(ticker)
    except Exception as exc:
        logger.warning("equities refresh failed for %s: %s", ticker, type(exc).__name__)
        return None


def refresh_all(
    tickers: list[str] | None = None,
    fetch: Callable[[str], object] | None = None,
) -> dict:
    """Refresh every ticker in turn; returns `{"ok": n, "failed": n}`."""
    ok = failed = 0
    with PASS_LOCK:
        try:
            todo = list(equities_store.load_tickers() if tickers is None else tickers)
        except Exception as exc:
            logger.warning("equities list unreadable: %s", type(exc).__name__)
            todo = []
        for ticker in todo:
            result = refresh_ticker(ticker, fetch)
            if getattr(result, "status", None) in _SUCCESS:
                ok += 1
            else:
                failed += 1
    return {"ok": ok, "failed": failed}


def _run(fetch) -> None:
    global _running, _pending
    while True:
        try:
            refresh_all(fetch=fetch)
        except Exception as exc:
            logger.warning("equities refresh pass failed: %s", type(exc).__name__)
        with _state_lock:
            if not _pending:
                _running = False
                _idle.set()
                return
            _pending = False


def request_refresh_now(fetch: Callable[[str], object] | None = None) -> dict:
    """Start a background pass, or mark one pending when a pass is running."""
    global _running, _pending
    with _state_lock:
        if _running:
            _pending = True
            return {"accepted": True, "already_running": True}
        _running = True
        _idle.clear()
    threading.Thread(target=_run, args=(fetch,), name="equities-refresh", daemon=True).start()
    return {"accepted": True, "already_running": False}


def wait_until_idle(timeout: float = 5.0) -> bool:
    """Block until no pass runs or is pending (tests and shutdown)."""
    return _idle.wait(timeout)


def _ticker_bar_date(ticker: str, now) -> date | None:
    result, _fetched = equities_fallback.read_cached(ticker, "1d", now=now)
    if result.df is None or result.df.empty:
        return None
    return result.df["timestamp"].max().date()


def _ticker_fetched_at(ticker: str, now) -> pd.Timestamp | None:
    return equities_fallback.read_cached(ticker, "1d", now=now)[1]


def _fetched_at_unknown(ticker: str, now) -> pd.Timestamp | None:
    """Default when only `bar_date` is injected: no fetch-time check."""
    return pd.Timestamp.max.tz_localize("UTC")


def _last_bar_date(now) -> str | None:
    dates = [d for d in (_ticker_bar_date(t, now) for t in equities_store.load_tickers()) if d is not None]
    return max(dates).isoformat() if dates else None


class EquitiesRefreshWorker:
    """The market-hours tick. Clock, wait Event, fetch, tickers and the
    per-ticker bar date are injectable, so tests run on a fake clock."""

    def __init__(
        self,
        *,
        clock: Callable[[], pd.Timestamp] | None = None,
        wake: threading.Event | None = None,
        fetch: Callable[[str], object] | None = None,
        tickers: Callable[[], list[str]] | None = None,
        bar_date: Callable[[str, pd.Timestamp], date | None] | None = None,
        first_delay_seconds: float = FIRST_TICK_DELAY_SECONDS,
        fetched_at: Callable[[str, pd.Timestamp], pd.Timestamp | None] | None = None,
    ) -> None:
        self._clock = clock or (lambda: lse_adapter._now())
        self._wake = wake if wake is not None else threading.Event()
        self._fetch = fetch
        self._tickers = tickers or equities_store.load_tickers
        self._bar_date = bar_date or _ticker_bar_date
        # A cache fetched before its session's bar was due holds a forming bar.
        # With an injected `bar_date` and no `fetched_at`, that check is off.
        if fetched_at is not None:
            self._fetched_at = fetched_at
        elif bar_date is None:
            self._fetched_at = _ticker_fetched_at
        else:
            self._fetched_at = _fetched_at_unknown
        self.first_delay_seconds = float(first_delay_seconds)
        self.interval_seconds = INTERVAL_SECONDS

        self._state_lock = threading.Lock()
        self._now_requested = False
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()

        self.ticks = 0
        self.retries = 0
        self.backoff_seconds = 0.0
        self.last_tick_started: pd.Timestamp | None = None
        self.last_tick_finished: pd.Timestamp | None = None
        self.last_tick_ok: int | None = None
        self.last_tick_failed: int | None = None
        self.next_tick_at: pd.Timestamp | None = None
        # The session the next scheduled tick is for (its retry reference).
        self.tick_session: date | None = None

    # ------------------------------------------------------------ lifecycle
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stopping.is_set()

    def start(self) -> None:
        with self._state_lock:
            if self._thread is not None:
                return
            self._stopping.clear()
            self._thread = threading.Thread(target=self._loop, name="equities-refresh-worker", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = STOP_JOIN_TIMEOUT_SECONDS) -> None:
        """Stop the loop and join its thread (idempotent)."""
        self._stopping.set()
        self._wake.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)

    def request_now(self) -> bool:
        """Wake one pass now. Returns False when one is already pending."""
        with self._state_lock:
            already = self._now_requested
            self._now_requested = True
        self._wake.set()
        return not already

    # ------------------------------------------------------------- schedule
    def _behind(self, session: date, now: pd.Timestamp) -> list[str]:
        """Tickers whose newest daily bar predates `session`, or is dated
        `session` but was fetched before that session's bar was due (a forming
        bar). No bar, or no/unreadable fetch time: behind."""
        behind = []
        due = equities_calendar.bar_due_at(session)
        for ticker in self._tickers():
            try:
                bar = self._bar_date(ticker, now)
            except Exception as exc:
                logger.warning("equities bar date unreadable for %s: %s", ticker, type(exc).__name__)
                bar = None
            if bar is None or bar < session:
                behind.append(ticker)
                continue
            if bar == session:
                try:
                    fetched = self._fetched_at(ticker, now)
                except Exception as exc:
                    logger.warning("equities fetch time unreadable for %s: %s", ticker, type(exc).__name__)
                    fetched = None
                if fetched is None or pd.Timestamp(fetched) < due:
                    behind.append(ticker)
        return behind

    def _schedule_next_close(self, now: pd.Timestamp) -> None:
        self.retries = 0
        self.next_tick_at = equities_calendar.next_refresh_at(now)
        self.tick_session = self.next_tick_at.date()

    def schedule_first(self) -> pd.Timestamp:
        """Catch-up 20 s after start when a ticker is behind the newest due
        session; otherwise the next close + `REFRESH_DELAY_MINUTES`."""
        now = self._clock()
        session = equities_calendar.last_due_session(now)
        try:
            behind = self._behind(session, now)
        except Exception as exc:
            logger.warning("equities catch-up check failed: %s", type(exc).__name__)
            behind = []
        if behind:
            self.next_tick_at = now + pd.Timedelta(seconds=self.first_delay_seconds)
            self.tick_session = session
        else:
            self._schedule_next_close(now)
        return self.next_tick_at

    def run_tick(self) -> dict:
        """One scheduled tick, then the next wake instant: a retry while a
        ticker is behind the tick's own session (3 x 30 min, longer when every
        ticker failed), else the next close."""
        session = self.tick_session
        start = self._clock()
        self.last_tick_started = start
        # Advanced as the tick starts; refined below once it has run.
        self.next_tick_at = equities_calendar.next_refresh_at(start)
        counts = self._pass()
        now = self._clock()
        self.ticks += 1
        if counts["ok"] == 0 and counts["failed"] > 0:
            self.backoff_seconds = min(max(self.backoff_seconds, RETRY_SECONDS) * 2, MAX_BACKOFF_SECONDS)
        elif counts["ok"] > 0:
            self.backoff_seconds = 0.0
        behind = self._behind(session, now) if session is not None else []
        if behind and self.retries < MAX_RETRIES:
            self.retries += 1
            self.next_tick_at = now + pd.Timedelta(seconds=self.backoff_seconds or RETRY_SECONDS)
            self.tick_session = session
        else:
            self._schedule_next_close(now)
        return counts

    def _pass(self) -> dict:
        try:
            tickers = list(self._tickers())
        except Exception as exc:
            logger.warning("equities list unreadable: %s", type(exc).__name__)
            tickers = []
        counts = refresh_all(tickers=tickers, fetch=self._fetch)
        self.last_tick_ok = counts["ok"]
        self.last_tick_failed = counts["failed"]
        self.last_tick_finished = self._clock()
        return counts

    def run_requested(self) -> dict:
        """A woken pass (`POST /refresh`, an add): the schedule is unchanged."""
        self.last_tick_started = self._clock()
        return self._pass()

    def _remaining(self) -> float:
        try:
            return (self.next_tick_at - self._clock()).total_seconds()
        except Exception:
            return RETRY_SECONDS

    def _loop(self) -> None:
        try:
            self.schedule_first()
        except Exception as exc:
            logger.warning("equities schedule failed: %s", type(exc).__name__)
            self.next_tick_at = self._clock() + pd.Timedelta(seconds=RETRY_SECONDS)
        while not self._stopping.is_set():
            try:
                woken = self._wake.wait(max(self._remaining(), 0.0))
                if self._stopping.is_set():
                    break
                self._wake.clear()
                with self._state_lock:
                    requested = self._now_requested
                    self._now_requested = False
                if not woken or self._remaining() <= 0:
                    self.run_tick()
                elif requested:
                    self.run_requested()
            except Exception as exc:  # the loop itself must never die
                logger.warning("equities refresh loop iteration failed: %s", type(exc).__name__)
                try:
                    self.next_tick_at = self._clock() + pd.Timedelta(seconds=RETRY_SECONDS)
                except Exception:
                    pass


# --------------------------------------------------------------------------
# Process-wide registry (the app lifespan owns it)
# --------------------------------------------------------------------------
_registry_lock = threading.Lock()
_worker: EquitiesRefreshWorker | None = None
_disabled_reason = "not-started"


def start_from_env(env=None, **worker_kwargs) -> EquitiesRefreshWorker | None:
    """Lifespan entry: start unless `SCREENER_REFRESH_WORKER=0` or no key."""
    global _worker, _disabled_reason
    env = os.environ if env is None else env
    enabled, reason = refresh_worker.enabled_from_env(env)
    if enabled and not env.get(KEY_ENV):
        enabled, reason = False, "missing-key"
    if not enabled:
        with _registry_lock:
            _disabled_reason = reason
        return None
    try:
        worker = EquitiesRefreshWorker(**worker_kwargs)
        with _registry_lock:
            previous, _worker = _worker, worker
        if previous is not None:
            previous.stop()
        worker.start()
        return worker
    except Exception as exc:
        logger.warning("equities refresh worker failed to start: %s", type(exc).__name__)
        stop_worker()
        with _registry_lock:
            _disabled_reason = "start-failed"
        return None


def stop_worker() -> None:
    """Lifespan exit: stop and unregister the worker (idempotent, never raises)."""
    global _worker, _disabled_reason
    with _registry_lock:
        worker, _worker = _worker, None
        _disabled_reason = "not-started"
    if worker is not None:
        try:
            worker.stop()
        except Exception as exc:
            logger.warning("equities refresh worker failed to stop: %s", type(exc).__name__)


def current_worker() -> EquitiesRefreshWorker | None:
    return _worker


def request_now() -> dict:
    """`POST /refresh`: wake the running worker, else a background pass."""
    worker = _worker
    if worker is not None and worker.running:
        return {"accepted": True, "already_running": not worker.request_now()}
    return request_refresh_now()


def status(now=None) -> dict:
    """The crypto status keys plus `last_bar_date`. Without a running worker
    it is the S9A form (`running` False, ticks null)."""
    worker = _worker
    running = worker is not None and worker.running
    if now is None:
        now = worker._clock() if running else lse_adapter._now()
    try:
        last_bar_date = _last_bar_date(now)
    except Exception:
        last_bar_date = None
    reason = None
    if not running:
        reason = _disabled_reason
        if reason == "not-started" and not os.environ.get(KEY_ENV):
            reason = "missing-key"
    shown = worker if running else None
    return {
        "running": running,
        "disabled_reason": reason,
        "interval_seconds": INTERVAL_SECONDS,
        "last_tick_started": iso_z(shown.last_tick_started) if shown else None,
        "last_tick_finished": iso_z(shown.last_tick_finished) if shown else None,
        "last_tick_ok": shown.last_tick_ok if shown else None,
        "last_tick_failed": shown.last_tick_failed if shown else None,
        "next_tick_at": iso_z(shown.next_tick_at) if shown else None,
        "queue_depth": 0,
        "backoff_seconds": shown.backoff_seconds if shown else 0.0,
        "server_time": iso_z(now),
        "last_bar_date": last_bar_date,
    }
