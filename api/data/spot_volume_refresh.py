"""Daily attention-store refresh run inside the API process: spot volume for the Discovery exchange slot (Binance,
Coinbase, Kraken) and DefiLlama fees for the `defillama` source.

Why here and not in GitHub Actions: Binance refuses GitHub's US runners (HTTP 451). The PC already runs the API, so a
small daemon thread keeps `attention/{exchange,coinbase,kraken}_volume/` and `attention/defillama/` current on the
owner's own connection.

* The first pass starts `FIRST_DELAY_SECONDS` after start; later passes run at `RUN_AT_UTC` each day (a completed UTC
  day is only final after midnight) and again after `RETRY_SECONDS` while any venue had a provider failure.
* A coin whose store already holds yesterday is skipped, so a restart costs no requests. A coin a venue does not list
  is a fact (`not listed`), not a failure, and is retried only on the next daily pass.
* Stores are written with the usual first-observation-wins merge (`store.write_series`), so a re-run is harmless.
* Nothing leaves the thread: every coin and every pass is isolated, and logs carry counts and reason classes only.
* `SCREENER_REFRESH_WORKER=0` turns it off with the other workers; `SPOT_VOLUME_REFRESH=0` turns off just this one.

Clock, sleep, symbols and HTTP client are injectable so tests never touch the network or sleep.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Callable

import httpx

from api.data import refresh_worker
from api.data.attention import defillama, spot_volume, store

logger = logging.getLogger(__name__)

ENV_FLAG = "SPOT_VOLUME_REFRESH"
FIRST_DELAY_SECONDS = 45.0
RUN_AT_UTC = dtime(0, 40)
RETRY_SECONDS = 3600.0
# A reason that is a fact about the coin or the venue's contract, not a failure worth an early retry.
_FACT_REASONS = ("not listed", "no protocol", "empty response")
# name -> (fetch(symbol, client, today), store, seconds between requests)
SOURCES = {
    **{v: (f, spot_volume.STORES[v], spot_volume.PACE_SECONDS[v]) for v, f in spot_volume.FETCHERS.items()},
    "defillama": (defillama.fetch_series, defillama.SOURCE, 0.3),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_symbols() -> list[str]:
    from api.analytics.attention.discovery import eligibility, load_config
    from api.analytics.attention.universe import load_universe_rows

    rows, _ = load_universe_rows()
    return list(eligibility(load_config(), rows).eligible) if rows else []


def _newest(source: str, symbol: str) -> date | None:
    try:
        pts = store.read_points(source, symbol)
    except Exception:  # noqa: BLE001 - a broken file is refetched (and rewritten) rather than skipped
        return None
    return pts[-1][0] if pts else None


def refresh_once(symbols: list[str], *, today: date, client: httpx.Client, sleep: Callable[[float], None],
                 stopping: threading.Event | None = None) -> dict[str, dict[str, int]]:
    """One pass over every venue and coin: `{venue: {"written": n, "ok": n, "skipped": n, "fact": n, "failed": n}}`."""
    stop = stopping or threading.Event()
    out: dict[str, dict[str, int]] = {}
    for venue, (fetch, store_name, pace) in SOURCES.items():
        counts = out[venue] = {"written": 0, "ok": 0, "skipped": 0, "fact": 0, "failed": 0}
        for sym in symbols:
            if stop.is_set():
                return out
            newest = _newest(store_name, sym)
            if newest is not None and newest >= today - timedelta(days=1):
                counts["skipped"] += 1
                continue
            series = fetch(sym, client, today)
            sleep(pace)
            if series.state in ("ok", "insufficient-history"):
                try:
                    counts["written"] += store.write_series(series, today=today)
                    counts["ok"] += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("spot volume store write failed for %s %s: %s", venue, sym, type(exc).__name__)
                    counts["failed"] += 1
            elif series.reason in _FACT_REASONS:
                counts["fact"] += 1
            else:
                counts["failed"] += 1
    return out


def next_run_after(now: datetime, *, retry: bool) -> datetime:
    """The next pass: `RETRY_SECONDS` from now after a failure, else the next `RUN_AT_UTC`."""
    if retry:
        return now + timedelta(seconds=RETRY_SECONDS)
    at = datetime.combine(now.date(), RUN_AT_UTC, tzinfo=timezone.utc)
    return at if at > now else at + timedelta(days=1)


class SpotVolumeWorker:
    def __init__(self, *, clock: Callable[[], datetime] | None = None, sleep: Callable[[float], None] | None = None,
                 symbols: Callable[[], list[str]] | None = None, client_factory: Callable[[], httpx.Client] | None = None,
                 first_delay_seconds: float = FIRST_DELAY_SECONDS) -> None:
        self._clock = clock or _utc_now
        self._stopping = threading.Event()
        self._sleep = sleep or (lambda s: self._stopping.wait(s))
        self._symbols = symbols or _default_symbols
        self._client_factory = client_factory or (lambda: httpx.Client(follow_redirects=True))
        self.first_delay_seconds = first_delay_seconds
        self._thread: threading.Thread | None = None
        self.passes = 0
        self.last_result: dict[str, dict[str, int]] | None = None
        self.last_finished: datetime | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stopping.is_set()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="spot-volume-refresh", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stopping.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)

    def run_pass(self) -> bool:
        """One pass; True when a venue had a provider failure (the loop then retries in an hour)."""
        now = self._clock()
        symbols = self._symbols()
        with self._client_factory() as client:
            result = refresh_once(symbols, today=now.date(), client=client, sleep=self._sleep, stopping=self._stopping)
        self.passes += 1
        self.last_result, self.last_finished = result, self._clock()
        logger.info("spot volume pass: %s", result)
        return any(c["failed"] for c in result.values())

    def _loop(self) -> None:
        wait = self.first_delay_seconds
        while not self._stopping.wait(max(wait, 0.0)):
            try:
                retry = self.run_pass()
            except Exception as exc:  # noqa: BLE001 - the loop must never die
                logger.warning("spot volume pass failed: %s", type(exc).__name__)
                retry = True
            now = self._clock()
            wait = (next_run_after(now, retry=retry) - now).total_seconds()


_registry_lock = threading.Lock()
_worker: SpotVolumeWorker | None = None


def enabled_from_env(env=None) -> bool:
    env = os.environ if env is None else env
    return refresh_worker.enabled_from_env(env)[0] and env.get(ENV_FLAG) != "0"


def start_from_env(env=None, **kwargs) -> SpotVolumeWorker | None:
    """Lifespan entry. Never raises."""
    global _worker
    if not enabled_from_env(env):
        return None
    try:
        worker = SpotVolumeWorker(**kwargs)
        with _registry_lock:
            previous, _worker = _worker, worker
        if previous is not None:
            previous.stop()
        worker.start()
        return worker
    except Exception as exc:  # noqa: BLE001
        logger.warning("spot volume worker failed to start: %s", type(exc).__name__)
        stop_worker()
        return None


def stop_worker() -> None:
    """Lifespan exit (idempotent, never raises)."""
    global _worker
    with _registry_lock:
        worker, _worker = _worker, None
    if worker is not None:
        try:
            worker.stop()
        except Exception as exc:  # noqa: BLE001
            logger.warning("spot volume worker failed to stop: %s", type(exc).__name__)


def current_worker() -> SpotVolumeWorker | None:
    return _worker
