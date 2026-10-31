"""W8e: the PC-side attention worker (SPEC rules 1-3, 6, 7, 9, 10, 15, 16; AC8, AC10, AC21, AC22, AC24, AC37, AC38,
AC40). It runs the X (`xsearch_web`) and Reddit (`reddit_web`) collectors inside the API process on the owner's host.

Off unless `SCREENER_ATTENTION_PC_WORKER` is exactly `1`; the test conftest and the workflows never set it, so tests
and runners never start it. The app lifespan starts it after the equities worker and stops it last
(`start_from_env` / `stop_worker`, the `equities_refresh` pattern).

- Two streams on two threads, each with its own lock in `PASS_LOCKS` (owner Q14): X never waits for Reddit and
  Reddit never waits for X. X goes only through the `x_reader.XReader` seam: the readers come from
  `twscrape_reader.start`, imported lazily when X first starts; the canary and every unit are `x_pool`'s.
- Fetch side: only Discovery sources whose fetch side is `pc_side` run here; every other source is GitHub's. The
  default map is `FETCH_SIDE` (`xsearch` and `reddit` on the PC). A `fetch_side` object in `discovery.json`
  overrides it when present (W8f adds and validates that key); a value other than `pc_side` keeps a source off here.
- Schedule (the T51 `_behind` pattern): at start a source with work is due `BEHIND_DELAY_S` (20 s) later, never
  earlier than the configured minimum delay after its previous unit, also right after a restart (the last unit time
  is persisted, `pc_pace.Trickle.first_due`). A source that is up to date, paused or out of budget waits for the next
  UTC day (00:00 + 20 s); X waiting for an account's in-flight lock (`account_wait`, `x_pool.XPool.resume_at`)
  is due at that lock's end instead. A pass that raised is retried after `RETRY_SECONDS`; unreadable state pauses
  the source, keeps the file and is re-checked after `RECHECK_SECONDS`. A pass begins 20 s before its due time
  because its first unit is scheduled that long after the pass begins.
- Modes (rule 15, AC37): BASELINE once the worker has been up since before 00:00 UTC of the current day, DEGRADED
  otherwise (rule 10, AC24), so a restart is degraded for the rest of that UTC day; never a fixed hour of the day.
  BASELINE spreads the X units over the day (`x_spread_over_day`: at least 24 h / (effective budget / `x_sample_n`)
  apart) and Reddit searches at max(60-120 s, 24 h / coins) with the budget 250; DEGRADED runs at the configured
  pace with the Reddit budget 150. The configured minimum delay always holds.
- Work (rules 2, 6, 9, 16): yesterday first, then the backfill (X `x_backfill_days`; Reddit the completed days its
  `t` filter reaches, at most `REDDIT_BACKFILL_DAYS`); X orders yesterday by the oldest newest-stored day (rotation).
  The X queue is rebuilt from the store before every unit, so a coin-day not finished (host stopped, budget spent,
  missing) stays queued for a later pass inside the backfill limits and is otherwise missing, never 0. Nothing is
  cut to fit time: a unit that started reads its pages; `x_sample_n`, `x_page_cap` and the feed depth are unchanged.
  X runs units only while its daily budget lasts. The per-source state (`pc_pace.PcSource`, under
  `<cache>/attention/_pc_state`) holds the daily counts, pause, effective budget, clean days and last unit time.
- Nothing runs and nothing is stored while the host is off; values are stored only through
  `web_evidence.commit_day` for completed UTC days.
- Unattended weeks (AC40): a rotating log file `<cache>/attention/_logs/attention_pc.log` (size and count from
  `SCREENER_ATTENTION_PC_LOG_MAX_BYTES` and `SCREENER_ATTENTION_PC_LOG_FILES`), X raw pages pruned after
  `x_raw_retention_days`, Reddit ledger partitions and per-day canary and completeness files pruned after
  `ledger_retention_days` (default 400, the SPEC's `reddit_ledger_retention_days`); no in-memory structure grows
  with the number of days. Times are UTC; a naive clock is refused.

Logs carry a source, an outcome or reason code and an exception class name only.
"""
from __future__ import annotations

import json
import logging
import os
import random
import statistics
import threading
import time as _time
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from api.data import cache
from api.data.attention import (
    pc_pace,
    reddit_items,
    reddit_web,
    store,
    web_evidence,
    web_queries,
    x_filters,
    x_pool,
    x_raw,
    x_window,
)
from api.data.attention import x_reader as xr

log = logging.getLogger(__name__)

FLAG_ENV = "SCREENER_ATTENTION_PC_WORKER"
X_SOURCE = "xsearch_web"
REDDIT_SOURCE = reddit_web.SOURCE
PC_SIDE = "pc_side"
GITHUB_SIDE = "github"
# Default fetch side per Discovery source (W8e deviation: W8f adds `fetch_side` to discovery.json and validates it).
FETCH_SIDE = {"xsearch": PC_SIDE, "reddit": PC_SIDE, "trends": GITHUB_SIDE, "wikipedia": GITHUB_SIDE,
              "exchange_activity": GITHUB_SIDE, "defillama": GITHUB_SIDE, "github_dev": GITHUB_SIDE}
STREAM_SOURCES = {"xsearch": X_SOURCE, "reddit": REDDIT_SOURCE}  # Discovery source -> the stream that fetches it
DISCOVERY_PATH = Path(__file__).resolve().parent / "discovery.json"
PASS_LOCKS = {X_SOURCE: threading.Lock(), REDDIT_SOURCE: threading.Lock()}
X_METHOD = "xsearch_web_read_sample_v1"
BEHIND_DELAY_S = pc_pace.BEHIND_DELAY_S
LOCKED_RETRY_SECONDS = 60.0
RETRY_SECONDS = 600.0
RECHECK_SECONDS = 3600.0
STOP_JOIN_TIMEOUT_SECONDS = 10.0
DAY_S = 86400.0
REDDIT_BACKFILL_DAYS = 5  # `t=week` reaches 7 days back from the request: 5 completed days before yesterday
TRAILING_DAYS = 28
LEDGER_RETENTION_DAYS_DEFAULT = 400
LOG_MAX_BYTES_ENV = "SCREENER_ATTENTION_PC_LOG_MAX_BYTES"
LOG_FILES_ENV = "SCREENER_ATTENTION_PC_LOG_FILES"
LOG_MAX_BYTES_DEFAULT = 5_000_000
LOG_FILES_DEFAULT = 5
LOG_NAME = "attention_pc.log"
LOG_LOGGERS = (__name__, "api.data.attention")
# Outcomes after which the source waits for the next UTC day.
NEXT_DAY = ("done", "paused", "budget_spent", "not_configured")


class _Stopped(BaseException):
    """The worker is stopping: unwinds a pass from inside a wait (never caught by a collector's `except Exception`)."""


def _utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        raise ValueError("clock must be timezone-aware UTC")
    return t.astimezone(timezone.utc)


def _day_start(t: datetime) -> datetime:
    return datetime.combine(_utc(t).date(), time(0), tzinfo=timezone.utc)


def _next_day(t: datetime) -> datetime:
    """The next UTC day's first due time: 00:00 plus the behind delay."""
    return _day_start(t) + timedelta(days=1, seconds=BEHIND_DELAY_S)


def _stored(source: str, symbols) -> dict[str, set[date]]:
    return {s: {d for d, _v in store.read_points(source, s)} for s in symbols}


def _trailing_median(source: str, symbol: str, day: date) -> float | None:
    start = day - timedelta(days=TRAILING_DAYS)
    vals = [v for d, v in store.read_points(source, symbol) if start <= d < day]
    return statistics.median(vals) if vals else None


def _prune_day_files(folder: Path, today: date, keep_days: int) -> int:
    """Delete `<YYYY-MM-DD>.json` files older than `keep_days`; any other file is never touched."""
    removed = 0
    if not folder.is_dir():
        return 0
    for p in folder.glob("*.json"):
        try:
            day = date.fromisoformat(p.stem)
        except ValueError:
            continue
        if (today - day).days > keep_days:
            p.unlink()
            removed += 1
    return removed


# --- defaults (the owner's host) ------------------------------------------------------------------------------------

def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_wait(seconds: float, stopping: threading.Event) -> bool:
    return stopping.wait(seconds)


def _default_symbols(q: web_queries.Queries, source: str) -> list[str]:
    return web_queries.coin_set(q, source, web_queries.placed_symbols())


def _default_x_start(config: web_queries.CollectorConfig):
    from api.data.attention import twscrape_reader  # lazy: the X library is never loaded before X starts

    return twscrape_reader.start(config)


def _default_x_cleanup() -> None:
    from api.data.attention import twscrape_reader

    twscrape_reader.clean_dumps([twscrape_reader.LIBRARY_DUMP_ROOT, twscrape_reader.private_tmp()])


def _default_ledger() -> reddit_items.Ledger | None:
    try:
        return reddit_items.Ledger(reddit_items.AuthorHasher(reddit_items.load_salt(create=True)))
    except (reddit_items.SaltError, OSError, ValueError) as exc:
        log.warning("attention pc %s item ledger off: %s", REDDIT_SOURCE, type(exc).__name__)
        return None


def pc_sources(path: Path | None = None) -> list[str]:
    """The streams this worker runs: the Discovery sources whose fetch side is `pc_side`, X first."""
    sides = dict(FETCH_SIDE)
    try:
        doc = json.loads((path or DISCOVERY_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("attention pc discovery config unreadable: %s", type(exc).__name__)
        return []
    raw = doc.get("fetch_side") if isinstance(doc, dict) else None
    if raw is not None:
        if not isinstance(raw, dict):
            log.warning("attention pc fetch_side is not an object: no PC source runs")
            return []
        sides.update(raw)
    return [stream for key, stream in STREAM_SOURCES.items() if sides.get(key) == PC_SIDE]


# --- streams --------------------------------------------------------------------------------------------------------

class Stream:
    """One source's schedule and pass; the X and Reddit subclasses plug in their collector."""

    def __init__(self, worker: AttentionPcWorker, source: str, rng: random.Random):
        self.worker, self.source, self.rng = worker, source, rng

    @property
    def lock(self) -> threading.Lock:
        return PASS_LOCKS[self.source]

    # --- per source ---
    def source_state(self, q: web_queries.Queries | None = None) -> pc_pace.PcSource:
        raise NotImplementedError

    def _symbols(self, q: web_queries.Queries) -> list[str]:
        raise NotImplementedError

    def _backfill_days(self, config: web_queries.CollectorConfig) -> int:
        raise NotImplementedError

    def _trickle(self, q: web_queries.Queries, n_coins: int) -> pc_pace.Trickle:
        raise NotImplementedError

    def _held(self, q: web_queries.Queries) -> str | None:
        """Why the source cannot run before the next day (or `state_error`), beyond pause and budget."""
        return None

    def _resume_at(self, q: web_queries.Queries) -> datetime | None:
        """A short hold that is not a day pause: the source's first unit waits until then (X: an in-flight lock)."""
        return None

    def _pass(self, q, src, syms, stop_at) -> str:
        raise NotImplementedError

    def _prune(self, q: web_queries.Queries) -> None:
        return None

    def close(self) -> None:
        return None

    rotation = False

    def _health_schedule(self, q, src, syms) -> None:
        """Persist the actual scheduling mode and upper interval, never a consumer-side guess."""
        now = _utc(self.worker.clock())
        gap = self._trickle(q, len(syms)).max_s
        if self.source == X_SOURCE and self.worker.x_spread_over_day and self.worker.mode(now) == "baseline":
            gap = max(gap, DAY_S / max(1, src.effective_budget() // q.config.x_sample_n))
        path = pc_pace.state_path(self.source).with_name(f"{self.source}_health.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        cache._atomic_write_json({"mode": self.worker.mode(now), "expected_gap_s": gap,
                                  "observed_at": now.isoformat()}, path)

    def _completeness(self, syms, day, *, symbol=None, reason="not_reached", attempted=False, result=None):
        """Reddit-compatible target-day evidence; one latest record per coin-day, never canary or page counts.

        A dispatched unit is durable before its first reader call. A power cut leaves `unit_interrupted`;
        retries replace that record instead of adding another fetched coin-day.
        """
        path = cache.CACHE_ROOT / "attention" / self.source / "_meta" / "_completeness" / f"{day.isoformat()}.json"
        if path.exists():
            doc = json.loads(path.read_text(encoding="utf-8"))
        else:
            doc = {"day": day.isoformat(), "coins": {}, "requests": 0, "budget_cut": False, "canary": None}
        for sym in syms:
            previous = doc["coins"].get(sym)
            if previous is None or previous["reason"] == "unit_interrupted":
                stored = web_evidence.read_rows(self.source, sym).get(day)
                if stored and day not in dict(store.read_points(self.source, sym)):
                    stored = None
                if previous is None or stored:
                    doc["coins"][sym] = {
                        "attempted": previous["attempted"] if previous else None if stored else False,
                        "reason": "fetched" if stored else reason,
                        "capped": bool(stored and (stored.capped or stored.pagecap)),
                        "collected_at": stored.collected_at.isoformat() if stored else None,
                        "n": stored.n if stored else None, "newest": None}
        if symbol is not None:
            previous = doc["coins"][symbol]
            doc["coins"][symbol] = {
                "attempted": attempted or previous["attempted"],
                "reason": reason, "capped": bool(result and (result.capped or result.pagecap)),
                "collected_at": _utc(self.worker.clock()).isoformat(),
                "n": result.n if result else None, "newest": None}
        path.parent.mkdir(parents=True, exist_ok=True)
        cache._atomic_write_json(reddit_web._summarize(doc), path)

    # --- shared ---
    def queue(self, q: web_queries.Queries | None = None, syms: list[str] | None = None) -> list[tuple[str, date]]:
        """(symbol, completed day) work, yesterday first, rebuilt from the store."""
        q = q or self.worker.queries()
        syms = self._symbols(q) if syms is None else syms
        return pc_pace.build_queue(syms, now=_utc(self.worker.clock()), stored=_stored(self.source, syms),
                                   backfill_days=self._backfill_days(q.config), rotation=self.rotation)

    def schedule(self, outcome: str | None = None) -> datetime:
        """When the next pass's first unit is due, after `outcome` (None: the worker just started)."""
        now = _utc(self.worker.clock())
        if outcome == "locked":
            return now + timedelta(seconds=LOCKED_RETRY_SECONDS)
        if outcome == "failed":
            return now + timedelta(seconds=RETRY_SECONDS)
        if outcome in ("state_error", "start_refused"):
            return now + timedelta(seconds=RECHECK_SECONDS)
        if outcome in NEXT_DAY:
            return _next_day(now)
        return self._behind(now)

    def _behind(self, now: datetime) -> datetime:
        q = self.worker.queries()
        try:
            src = self.source_state(q)
        except pc_pace.PcStateError:
            return now + timedelta(seconds=RECHECK_SECONDS)
        syms = self._symbols(q)
        if not self.queue(q, syms) or src.is_paused() or src.budget_spent():
            return _next_day(now)
        held = self._held(q)
        if held == "state_error":
            return now + timedelta(seconds=RECHECK_SECONDS)
        if held:
            return _next_day(now)
        due = self._trickle(q, len(syms)).first_due(now, src.last_unit_at())
        resume = self._resume_at(q)
        return due if resume is None else max(due, resume)

    def run_pass(self, stop_at: datetime | None = None) -> str:
        """Work the queue at the source's pace until done, paused, out of budget or `stop_at` (the host stops).

        Returns the outcome code; a collector exception propagates (the stream loop logs and retries it).
        """
        stop_at = None if stop_at is None else _utc(stop_at)
        if not self.lock.acquire(blocking=False):
            return "locked"
        try:
            q = self.worker.queries()
            try:
                src = self.source_state(q)
            except pc_pace.PcStateError:
                log.warning("attention pc %s state unreadable: source paused, file kept", self.source)
                return "state_error"
            syms = self._symbols(q)
            self._health_schedule(q, src, syms)
            today = _utc(self.worker.clock()).date()
            hold = src.pause_reason() or ("budget_spent" if src.budget_spent() else "not_reached")
            for offset in range(1, self._backfill_days(q.config) + 2):
                self._completeness(syms, today - timedelta(days=offset), reason=hold)
            if not self.queue(q, syms):
                return "done"
            if src.is_paused():
                return "paused"
            if src.budget_spent():
                return "budget_spent"
            try:
                outcome = self._pass(q, src, syms, stop_at)
            finally:
                self._health_schedule(q, src, syms)
            try:
                self._prune(q)
            except Exception as exc:  # noqa: BLE001 - housekeeping never stops the collector
                log.warning("attention pc %s prune skipped: %s", self.source, type(exc).__name__)
            return outcome
        finally:
            self.lock.release()


class XStream(Stream):
    """X: the daily canary and coin-day units across the account pool, inside the global read budget."""

    def __init__(self, worker, source, rng):
        super().__init__(worker, source, rng)
        self._start = None

    @property
    def rotation(self) -> bool:  # owner Q10: X runs in rotation mode
        return self.worker.x_rotation

    def source_state(self, q=None) -> pc_pace.PcSource:
        c = (q or self.worker.queries()).config
        return pc_pace.PcSource(X_SOURCE, configured_budget=c.x_daily_post_budget, floor=c.x_sample_n,
                                adaptive=True, clock=self.worker.clock)

    def _symbols(self, q):
        return [s for s in self.worker.symbols(q, X_SOURCE) if x_window.coin_terms(q, s) is not None]

    def _backfill_days(self, config):
        return config.x_backfill_days

    def _trickle(self, q, n_coins):
        return pc_pace.Trickle.for_source(q.config, X_SOURCE, self.rng)

    def _pool(self, config) -> x_pool.XPool:
        return x_pool.XPool(list(config.x_accounts), clock=self.worker.clock)

    def _held(self, q):
        if not q.config.x_accounts:
            return "not_configured"
        try:
            pool = self._pool(q.config)
            return "paused" if pool.is_paused() and pool.resume_at() is None else None
        except x_pool.XPoolStateError:
            return "state_error"

    def _resume_at(self, q):
        try:
            return self._pool(q.config).resume_at() if q.config.x_accounts else None
        except x_pool.XPoolStateError:
            return None

    def _reader(self, config):
        start = self._start
        if start is not None and set(config.x_accounts) <= set(start.readers):
            return start
        self.close()
        try:
            self._start = self.worker.x_start(config)
        except Exception as exc:  # noqa: BLE001 - a refused start pauses X; the reasons are codes, never values
            detail = str(exc) if type(exc).__name__ == "XStartRefused" else type(exc).__name__
            log.warning("attention pc %s reader did not start: %s", X_SOURCE, detail)
            return None
        return self._start

    def close(self) -> None:
        start, self._start = self._start, None
        if start is None:
            return
        try:
            start.close()
        finally:
            self.worker.x_cleanup()

    def _next_due(self, trickle: pc_pace.Trickle, src: pc_pace.PcSource, config) -> datetime:
        """The configured delay from the end of the last unit; spread over the day in BASELINE."""
        w = self.worker
        now = _utc(w.clock())
        due = trickle.next_due(now)
        if w.x_spread_over_day and w.mode(now) == "baseline":
            units = max(1, src.effective_budget() // config.x_sample_n)
            due = max(due, now + timedelta(seconds=DAY_S / units))
        return due

    def _pass(self, q, src, syms, stop_at):
        w, c = self.worker, q.config
        if not c.x_accounts:
            return "not_configured"
        try:
            pool = self._pool(c)
        except x_pool.XPoolStateError:
            log.warning("attention pc %s pool state unreadable: source paused, file kept", X_SOURCE)
            return "state_error"
        if pool.is_paused() and pool.resume_at() is None:
            return "paused"
        start = self._reader(c)
        if start is None:
            return "start_refused"
        trickle = self._trickle(q, len(syms))
        due = trickle.first_due(_utc(w.clock()), src.last_unit_at())
        tried: set[tuple[str, date]] = set()  # this pass only: a missing coin-day waits for a later pass
        while True:
            items = [item for item in self.queue(q, syms) if item not in tried]
            if not items:
                return "done"
            if src.is_paused() or (pool.is_paused() and pool.resume_at() is None):
                return "paused"
            if pool.resume_at() is not None:  # an account's in-flight lock: wait it out, never the day
                due = max(due, pool.resume_at())
            if not src.can_spend(xr.PAGE_ENTRIES):
                src.mark_spent()
                return "budget_spent"
            if stop_at is not None and due >= stop_at:
                return "host_stopped"
            w._wait_until(due)
            if not pool.canary_passed_today():
                canary = x_pool.run_daily_canary(pool, start.readers, src, c, rng=self.rng, sleep=w._sleep,
                                                 fallback=start.fallback)
                due = self._next_due(trickle, src, c)
                if canary.passed:
                    continue
                if canary.reason in ("budget_spent", "too_early"):
                    return canary.reason
                if pool.resume_at() is not None:
                    log.warning("attention pc %s canary waits for an account lock until %s", X_SOURCE,
                                pool.resume_at().isoformat())
                    return "account_wait"
                log.warning("attention pc %s canary did not pass: %s", X_SOURCE, canary.reason)
                return "paused"
            symbol, day = items[0]
            tried.add((symbol, day))
            entry = q.coins[symbol]
            policy = x_filters.FilterPolicy.from_config(c, entry)
            query = x_window.build_query(x_window.coin_terms(q, symbol), day, syntax=c.x_window_syntax,
                                         lang=policy.lang)
            self._completeness(syms, day, symbol=symbol, reason="unit_interrupted", attempted=True)
            try:
                out = x_pool.run_unit(pool, start.readers, src, c, symbol=symbol, day=day, query=query,
                                      coin=x_filters.Coin(symbol, entry["name"]), policy=policy, rng=self.rng,
                                      sleep=w._sleep, fallback=start.fallback)
            except Exception:
                self._completeness(syms, day, symbol=symbol, reason="failed", attempted=True)
                raise
            stored = False
            if out.result is not None:
                stored = web_evidence.commit_day(
                    X_SOURCE, symbol, day, out.result,
                    canary_ok=bool(out.row and out.row.get("canary_ok") is True),
                    trailing_median=_trailing_median(X_SOURCE, symbol, day),
                    now=_utc(w.clock()), method=X_METHOD)
            self._completeness(syms, day, symbol=symbol,
                               reason="fetched" if stored else "zero_unconfirmed" if out.result else out.reason,
                               attempted=out.attempts > 0, result=out.result if stored else None)
            self._health_schedule(q, src, syms)
            due = self._next_due(trickle, src, c)
            if out.reason in ("budget_spent", "too_early"):
                return out.reason
            if pool.resume_at() is not None:
                log.warning("attention pc %s waits for an account lock until %s", X_SOURCE,
                            pool.resume_at().isoformat())
                return "account_wait"
            if pool.is_paused() or src.is_paused():
                log.warning("attention pc %s paused: %s", X_SOURCE, pool.pause_reason() or src.pause_reason())
                return "paused"

    def _prune(self, q):
        x_raw.prune(now=_utc(self.worker.clock()), retention_days=q.config.x_raw_retention_days)
        _prune_day_files(cache.CACHE_ROOT / "attention" / X_SOURCE / "_meta" / "_completeness",
                         _utc(self.worker.clock()).date(), q.config.x_raw_retention_days)


class RedditStream(Stream):
    """Reddit: the daily canary and one `search.rss` request per coin-day (`reddit_web.run_pass`)."""

    def __init__(self, worker, source, rng):
        super().__init__(worker, source, rng)
        self._ledger: reddit_items.Ledger | None = None
        self._ledger_ready = False

    def _degraded(self) -> bool:
        return self.worker.mode(_utc(self.worker.clock())) == "degraded"

    def source_state(self, q=None) -> pc_pace.PcSource:
        c = (q or self.worker.queries()).config
        return reddit_web.reddit_source(c, degraded=self._degraded(), clock=self.worker.clock)

    def _symbols(self, q):
        return [s for s in self.worker.symbols(q, REDDIT_SOURCE) if reddit_web.search_terms(q, s) is not None]

    def _backfill_days(self, config):
        span = reddit_web.TIME_FILTER_SPAN[config.reddit_search_time_filter]
        if span is None:
            return REDDIT_BACKFILL_DAYS
        return max(0, min(REDDIT_BACKFILL_DAYS, span.days - 2))

    def _trickle(self, q, n_coins):
        return reddit_web.search_trickle(q.config, n_coins, degraded=self._degraded(), rng=self.rng)

    def _ledger_obj(self) -> reddit_items.Ledger | None:
        if not self._ledger_ready:
            self._ledger, self._ledger_ready = self.worker.reddit_ledger(), True
        return self._ledger

    def _pass(self, q, src, syms, stop_at):
        w = self.worker
        ledger = self._ledger_obj()
        client = w.reddit_client()
        try:
            res = reddit_web.run_pass(client, src, q, queue=self.queue(q, syms), clock=w.clock, sleep=w._sleep,
                                      rng=self.rng, degraded=self._degraded(), ledger=ledger, stop_at=stop_at,
                                      n_coins=len(syms))
        finally:
            client.close()
        return res.stop

    def _prune(self, q):
        today, keep = _utc(self.worker.clock()).date(), self.worker.ledger_retention_days
        _prune_day_files(reddit_items.ledger_path(today).parent, today, keep)
        _prune_day_files(reddit_web.canary_path(today).parent, today, keep)
        _prune_day_files(reddit_web.completeness_path(today).parent, today, keep)


# --- the worker -----------------------------------------------------------------------------------------------------

class AttentionPcWorker:
    """The two streams and their threads. Every input is injectable, so tests run on a fake clock and fakes."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None,
                 wait: Callable[[float, threading.Event], bool] | None = None,
                 queries: Callable[[], web_queries.Queries] | None = None,
                 symbols: Callable[[web_queries.Queries, str], list[str]] | None = None,
                 x_start: Callable | None = None, x_cleanup: Callable[[], None] | None = None,
                 reddit_client: Callable | None = None,
                 reddit_ledger: Callable[[], reddit_items.Ledger | None] | None = None,
                 seed: int | None = None, discovery_path: Path | None = None,
                 ledger_retention_days: int = LEDGER_RETENTION_DAYS_DEFAULT, x_spread_over_day: bool = True,
                 x_rotation: bool = True):
        self.clock = clock or _default_clock
        self.started_at = _utc(self.clock())  # refuses a naive clock
        if not isinstance(ledger_retention_days, int) or isinstance(ledger_retention_days, bool) \
                or ledger_retention_days < 1:
            raise ValueError("ledger retention must be at least one day")
        self._wait = wait or _default_wait
        self.queries = queries or web_queries.load
        self.symbols = symbols or _default_symbols
        self.x_start = x_start or _default_x_start
        self.x_cleanup = x_cleanup or _default_x_cleanup
        self.reddit_client = reddit_client or reddit_web.make_client
        self.reddit_ledger = reddit_ledger or _default_ledger
        self.ledger_retention_days = ledger_retention_days
        self.x_spread_over_day = x_spread_over_day
        self.x_rotation = x_rotation
        self._stopping = threading.Event()
        self._state_lock = threading.Lock()
        self.threads: dict[str, threading.Thread] = {}
        kinds = {X_SOURCE: XStream, REDDIT_SOURCE: RedditStream}
        self.streams: dict[str, Stream] = {s: kinds[s](self, s, random.Random(seed)) for s in pc_sources(discovery_path)}

    def mode(self, now: datetime) -> str:
        """`baseline` when up since before 00:00 UTC of `now`'s day, else `degraded` (host uptime, never an hour)."""
        return "baseline" if self.started_at <= _day_start(now) else "degraded"

    # --- waits ---
    def _wait_until(self, due: datetime) -> None:
        while True:
            if self._stopping.is_set():
                raise _Stopped()
            left = (_utc(due) - _utc(self.clock())).total_seconds()
            if left <= 0:
                return
            if self._wait(left, self._stopping):
                raise _Stopped()

    def _sleep(self, seconds: float) -> None:
        self._wait_until(_utc(self.clock()) + timedelta(seconds=seconds))

    # --- lifecycle ---
    @property
    def running(self) -> bool:
        return (not self._stopping.is_set()) and any(t.is_alive() for t in self.threads.values())

    def start(self) -> None:
        with self._state_lock:
            if self.threads or not self.streams:
                return
            self._stopping.clear()
            for source, stream in self.streams.items():
                self.threads[source] = threading.Thread(target=self._loop, args=(stream,),
                                                        name=f"attention-pc-{source}", daemon=True)
            for t in self.threads.values():
                t.start()

    def stop(self, timeout: float = STOP_JOIN_TIMEOUT_SECONDS) -> None:
        """Stop both streams, join their threads and close the X readers (idempotent)."""
        self._stopping.set()
        for t in list(self.threads.values()):
            if t is not threading.current_thread():
                t.join(timeout)
        for source, stream in self.streams.items():
            t = self.threads.get(source)
            if t is not None and t.is_alive():
                continue  # still inside a request: never close what it uses
            try:
                stream.close()
            except Exception as exc:  # noqa: BLE001 - stopping must not raise
                log.warning("attention pc %s close skipped: %s", source, type(exc).__name__)

    def _loop(self, stream: Stream) -> None:
        outcome: str | None = None
        lead = timedelta(seconds=BEHIND_DELAY_S)
        while not self._stopping.is_set():
            try:
                due = stream.schedule(outcome)
                self._wait_until(due - lead)
                outcome = stream.run_pass()
                log.info("attention pc %s pass: %s", stream.source, outcome)
            except _Stopped:
                break
            except Exception as exc:  # noqa: BLE001 - the loop must never die; never the message
                log.warning("attention pc %s pass failed: %s", stream.source, type(exc).__name__)
                outcome = "failed"


# --- log rotation -----------------------------------------------------------------------------------------------------

def _positive_int(value, default: int) -> int:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return n if n >= 1 else default


def log_settings(env=None) -> tuple[int, int]:
    """(max bytes per file, rotated file count) from the environment; a missing or invalid value is the default."""
    env = os.environ if env is None else env
    return (_positive_int(env.get(LOG_MAX_BYTES_ENV), LOG_MAX_BYTES_DEFAULT),
            _positive_int(env.get(LOG_FILES_ENV), LOG_FILES_DEFAULT))


def log_dir() -> Path:
    return cache.CACHE_ROOT / "attention" / "_logs"


def install_log_handler(directory: Path, *, max_bytes: int = LOG_MAX_BYTES_DEFAULT,
                        files: int = LOG_FILES_DEFAULT) -> RotatingFileHandler:
    """A size-rotated UTC log file for the worker and the attention collectors."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / LOG_NAME, maxBytes=max_bytes, backupCount=files, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)sZ %(levelname)s %(name)s %(message)s", "%Y-%m-%dT%H:%M:%S")
    fmt.converter = _time.gmtime
    handler.setFormatter(fmt)
    handler.setLevel(logging.INFO)
    handler.attention_pc = True
    for name in LOG_LOGGERS:
        logging.getLogger(name).addHandler(handler)
    return handler


def remove_log_handler(handler: logging.Handler) -> None:
    for name in LOG_LOGGERS:
        logging.getLogger(name).removeHandler(handler)
    handler.close()


# --- process-wide registry (the app lifespan owns it) -----------------------------------------------------------------

_registry_lock = threading.Lock()
_worker: AttentionPcWorker | None = None
_handler: logging.Handler | None = None
_disabled_reason = "not-started"


def enabled(env=None) -> bool:
    env = os.environ if env is None else env
    return env.get(FLAG_ENV) == "1"


def start_from_env(env=None, **worker_kwargs) -> AttentionPcWorker | None:
    """Lifespan entry: start only with `SCREENER_ATTENTION_PC_WORKER=1`; never raises."""
    global _worker, _handler, _disabled_reason
    env = os.environ if env is None else env
    if not enabled(env):
        with _registry_lock:
            _disabled_reason = "flag-off"
        return None
    try:
        max_bytes, files = log_settings(env)
        handler = install_log_handler(log_dir(), max_bytes=max_bytes, files=files)
        with _registry_lock:
            old_handler, _handler = _handler, handler
        if old_handler is not None:
            remove_log_handler(old_handler)
        worker = AttentionPcWorker(**worker_kwargs)
        with _registry_lock:
            previous, _worker = _worker, worker
        if previous is not None:
            previous.stop()
        worker.start()
        return worker
    except Exception as exc:  # noqa: BLE001 - the API starts whatever happens here
        log.warning("attention pc worker did not start: %s", type(exc).__name__)
        stop_worker()
        with _registry_lock:
            _disabled_reason = "start-failed"
        return None


def stop_worker() -> None:
    """Lifespan exit: stop and unregister the worker and its log file handler (idempotent, never raises)."""
    global _worker, _handler, _disabled_reason
    with _registry_lock:
        worker, _worker = _worker, None
        handler, _handler = _handler, None
        _disabled_reason = "not-started"
    if worker is not None:
        try:
            worker.stop()
        except Exception as exc:  # noqa: BLE001
            log.warning("attention pc worker stop skipped: %s", type(exc).__name__)
    if handler is not None:
        remove_log_handler(handler)


def current_worker() -> AttentionPcWorker | None:
    return _worker


def disabled_reason() -> str:
    return _disabled_reason
