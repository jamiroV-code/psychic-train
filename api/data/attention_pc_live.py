"""S-RCore-B: one worker stream per ENABLED live Reddit method (`reddit_live_methods`, RC-9).

The PC worker (`attention_pc_refresh.AttentionPcWorker`) builds a `LiveStream` per method that
`reddit_core.resolve_methods` returns, only while the Reddit fetch side is `pc_side`; with no method named nothing
here is imported or run and the worker keeps its feed streams unchanged. Each stream has its own thread, lock,
schedule, persisted counters/breaker (`reddit_live`) and daily cap, and never waits for the feed streams.

A pass: gate (`method.gate_state`) -> breaker -> daily cap -> due -> one poll (`build_context` -> `run_poll` ->
`record_poll`), then the commit of the completed UTC days still open, the method health file
`_pc_state/reddit_live/<store>_health.json` (S-StatusAPI contract) and the facts (`poll_result`,
`request_counter`, the day's Reddit universe snapshot). Polls are spaced `86400 / reddit_live_polls_per_day` apart
(`reddit_live.poll_due`), never before the method's own `next_poll_due`. Logs carry codes and class names only.
"""
from __future__ import annotations

import dataclasses
import logging
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace

from api.data import attention_pc_refresh as apr
from api.data import cache
from api.data.attention import daily_facts, reddit_core, reddit_live, web_queries, x_pool

log = logging.getLogger(__name__)

FACTS_SOURCE = "reddit"
COMMIT_DAYS = 2  # completed days still open: the lanes `build_context` reads reach two days back
# gate state -> (health state, reason); `ready` is ok. Gates that cannot change before a restart or a new day wait
# for the next day, the rest are re-checked after `RECHECK_SECONDS`.
GATE_HEALTH = {"needs_probe": ("needs_probe", "needs_probe"), "disabled": ("disabled", "method_disabled")}
NEXT_DAY_GATES = ("method_unavailable", "disabled")
HELD = ("breaker", "request_cap")


def deps(worker: apr.AttentionPcWorker) -> SimpleNamespace:
    """What a method factory may use from the worker: its clock and its stop-aware sleep."""
    return SimpleNamespace(clock=worker.clock, sleep=worker._sleep)


def health_path(store_id: str):
    return cache.CACHE_ROOT / "attention" / "_pc_state" / "reddit_live" / f"{store_id}_health.json"


class LiveStream(apr.Stream):
    """One live method's schedule and poll pass (the base `Stream` lifecycle; its own lock and outcomes)."""

    def __init__(self, worker, source, rng, method):
        super().__init__(worker, source, rng)
        self.method = method
        self._lock = threading.Lock()
        self._lanes: dict | None = None

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    def _symbols(self, q):
        return apr.RedditStream._symbols(self, q)

    # --- budget ---
    def _uses_navigations(self) -> bool:
        return self.source == reddit_core.STORES["browser"]

    def cap(self, config) -> int:
        return (config.reddit_browser_daily_navigation_cap if self._uses_navigations()
                else config.reddit_live_gql_daily_request_cap)

    def used(self, now: datetime) -> int:
        s = reddit_live.read_state(self.source, now)
        return s["navigations"] if self._uses_navigations() else s["requests"]

    # --- schedule ---
    def next_poll_due(self, q, now: datetime) -> datetime:
        due = reddit_live.poll_due(self.source, now, q.config.reddit_live_polls_per_day)
        own = self.method.next_poll_due(now)
        return due if own is None else max(due, apr._utc(own))

    def _idle(self, q, syms) -> bool:
        return apr._utc(self.worker.clock()) < self.next_poll_due(q, apr._utc(self.worker.clock()))

    def _extra_wake(self, q, src, now):
        return self.next_poll_due(q, now)

    def schedule(self, outcome: str | None = None) -> datetime:
        now = apr._utc(self.worker.clock())
        if outcome == "locked":
            return now + timedelta(seconds=apr.LOCKED_RETRY_SECONDS)
        if outcome == "failed":
            return now + timedelta(seconds=apr.RETRY_SECONDS)
        if outcome in HELD or outcome in NEXT_DAY_GATES:
            return apr._next_day(now)
        if outcome in reddit_core.GATE_STATES:
            return now + timedelta(seconds=apr.RECHECK_SECONDS)
        return max(now, self._extra_wake(self.worker.queries(), None, now))

    # --- pass ---
    def run_pass(self, stop_at: datetime | None = None) -> str:
        if not self.lock.acquire(blocking=False):
            return "locked"
        try:
            q = self.worker.queries()
            now = apr._utc(self.worker.clock())
            self._snapshot(q, self._symbols(q))
            outcome = self._poll(q, now, stop_at)
            self._commit_open_days(q, apr._utc(self.worker.clock()))
            self._write_health(q, outcome)
            return outcome
        finally:
            self.lock.release()

    def _poll(self, q, now, stop_at) -> str:
        c = q.config
        gate = self.method.gate_state(now)
        if gate != "ready":
            return gate
        if reddit_live.breaker_open(self.source, now):
            return "breaker"
        cap = self.cap(c)
        if self.used(now) >= cap:
            return "request_cap"
        if now < self.next_poll_due(q, now) or (stop_at is not None and now >= apr._utc(stop_at)):
            return "not_due"
        ctx = reddit_live.build_context(self.source, web_queries.stream_subreddits(q), now,
                                        threads_per_poll=c.reddit_live_threads_per_poll, request_cap=cap)
        ctx = dataclasses.replace(ctx, requests_left=max(cap - self.used(now), 0))
        result = self.method.run_poll(ctx)
        reddit_live.record_poll(self.source, result)
        self._facts(q, result)
        return "polled"

    def _commit_open_days(self, q, now: datetime) -> None:
        """Commit the completed days the method observed (lanes on D or D+1) that are not settled yet."""
        subs = web_queries.stream_subreddits(q)
        for offset in range(COMMIT_DAYS, 0, -1):
            day = now.date() - timedelta(days=offset)
            done = reddit_live.read_completeness(self.source, day)
            if (done is not None and done.get("settled")) or not reddit_live.read_lanes(
                    self.source, day, day + timedelta(days=1)):
                continue
            try:
                doc = reddit_live.commit_day(self.source, day, q, now=now, subreddits=subs)
            except Exception as exc:  # noqa: BLE001 - a day that fails to commit stays open; the pass goes on
                log.warning("attention pc %s commit skipped: %s", self.source, type(exc).__name__)
                continue
            if doc:
                posts = doc.get("posts_coverage") or {}
                self._lanes = {"posts": min(posts.values()) if posts else 0.0,
                               "comments": doc.get("comments_coverage", 0.0)}

    def _facts(self, q, result) -> None:
        stops = result.stop_reasons
        failed = [r for r in stops if r in reddit_live.FAILED_STOPS]
        stop = failed[0] if failed else max(stops, key=stops.get) if stops else "exhausted"
        switches = x_pool.facts_switches(q.config)
        try:
            daily_facts.append({"kind": "poll_result", "source": FACTS_SOURCE, "method": self.source,
                                "account": None, "navigations": result.navigations, "lanes": len(result.lanes),
                                "stop_reason": stop}, now=result.collected_at, switches=switches)
            daily_facts.append({"kind": "request_counter", "source": FACTS_SOURCE, "method": self.source,
                                "requests": result.requests}, now=result.collected_at, switches=switches)
        except Exception as exc:  # noqa: BLE001 - facts never stop collection
            log.warning("attention pc %s facts skipped: %s", self.source, type(exc).__name__)

    def _write_health(self, q, outcome: str) -> None:
        now = apr._utc(self.worker.clock())
        if outcome in reddit_core.GATE_STATES:
            state, reason = GATE_HEALTH.get(outcome, ("blocked", outcome))
        elif outcome in HELD:
            state, reason = "degraded", outcome
        else:
            state, reason = "ok", None
        doc = {"state": state, "reason": reason, "lanes": self._lanes, "comments_scope": reddit_core.COMMENTS_SCOPE,
               "requests_today": self.used(now), "cap": self.cap(q.config), "observed_at": now.isoformat()}
        path = health_path(self.source)
        path.parent.mkdir(parents=True, exist_ok=True)
        cache._atomic_write_json(doc, path)

    def close(self) -> None:
        self.method.close()


def build(worker: apr.AttentionPcWorker, factory, rng) -> dict[str, LiveStream]:
    """The live streams for the configured methods, keyed by store; empty when none is named or the config fails."""
    try:
        config = worker.queries().config
    except Exception as exc:  # noqa: BLE001 - an unreadable config runs no live method
        log.warning("attention pc live methods off: %s", type(exc).__name__)
        return {}
    if not config.reddit_live_methods:
        return {}
    methods = factory(config, deps(worker))
    return {m.store: LiveStream(worker, m.store, rng, m) for m in methods.values() if m.store is not None}
