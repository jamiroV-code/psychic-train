"""Equities cache refresh (S9A, minimal; S9E adds the market-hours tick).

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
* `status` reports the S9A form: nothing scheduled yet.

Logs carry only a ticker and an exception class name: never the key, a URL
or exception text.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Callable

from api.data import equities_store, lse_adapter
from api.data.freshness import iso_z

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 86400
_SUCCESS = {"ok", "stale"}

# One pass at a time (manual, add-triggered or the S9E tick).
PASS_LOCK = threading.Lock()

_state_lock = threading.Lock()
_running = False
_pending = False
_idle = threading.Event()
_idle.set()


def _default_fetch(ticker: str):
    return lse_adapter.refresh_equity(ticker)


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


def _last_bar_date(now) -> str | None:
    newest = None
    for ticker in equities_store.load_tickers():
        result, _fetched = lse_adapter.read_cached_equity(ticker, "1d", now=now)
        if result.df is not None and not result.df.empty:
            last = result.df["timestamp"].max()
            newest = last if newest is None or last > newest else newest
    return None if newest is None else newest.date().isoformat()


def status(now=None) -> dict:
    """The crypto status keys; S9A schedules nothing, so `running` is False."""
    now = lse_adapter._now() if now is None else now
    try:
        last_bar_date = _last_bar_date(now)
    except Exception:
        last_bar_date = None
    return {
        "running": False,
        "disabled_reason": "not-started" if os.environ.get("LSE_API_KEY") else "missing-key",
        "interval_seconds": INTERVAL_SECONDS,
        "last_tick_started": None,
        "last_tick_finished": None,
        "last_tick_ok": None,
        "last_tick_failed": None,
        "next_tick_at": None,
        "queue_depth": 0,
        "backoff_seconds": 0.0,
        "server_time": iso_z(now),
        "last_bar_date": last_bar_date,
    }
