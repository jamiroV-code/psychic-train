"""W8e (PLAN section W8e; SPEC rules 7, 10, 15, 16; AC8, AC10, AC21, AC22, AC24, AC37, AC38, AC40): the PC-side
attention worker shell that runs the X and Reddit collectors as two streams.

Fakes only: X goes through `x_reader.FakeXReader` (a subclass that answers any coin-day), Reddit through
`httpx.MockTransport`; socket connects are blocked for every test here. Clocks are injected and timezone-aware.
"""
from __future__ import annotations

import ast
import dataclasses
import functools
import json
import logging
import random
import re
import socket
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from api.data import attention_pc_refresh as apr
from api.data import cache
from api.data.attention import pc_pace, store, web_evidence, x_raw
from api.data.attention import reddit_web as rw
from api.data.attention import web_queries as wq
from api.data.attention import x_filters as xf
from api.data.attention import x_pool as xp
from api.data.attention import x_reader as xrd
from api.data.attention.types import SourceSeries

T0 = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
YESTERDAY = date(2026, 10, 26)
MIDNIGHT = datetime(2026, 10, 28, tzinfo=timezone.utc)
COINS = ["SOL", "ETH", "ADA"]
REPO = Path(__file__).resolve().parents[3]
X, R = apr.X_SOURCE, apr.REDDIT_SOURCE


@pytest.fixture(autouse=True)
def _isolated(isolated_cache, monkeypatch):
    """Throwaway cache root, no socket connect off the loopback, no worker left behind. The loopback stays open
    only for the event loop's own socket pair (Windows asyncio builds it with a loopback connect)."""
    real_connect = socket.socket.connect

    def refuse(self, address, *a, **k):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return real_connect(self, address, *a, **k)
        raise OSError("network blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    yield isolated_cache
    apr.stop_worker()


# --- clock, X reader and Reddit fakes ---------------------------------------------------------------------------

class Clock:
    """A fake UTC clock. `wait` is the worker's wait: it advances the clock; past `limit` the host is 'off' and it
    blocks (really) until the worker stops."""

    def __init__(self, t: datetime = T0, limit: datetime | None = None):
        self.t, self.limit, self.lock, self.blocked = t, limit, threading.Lock(), 0

    def __call__(self) -> datetime:
        with self.lock:
            return self.t

    def sleep(self, s: float) -> None:
        assert s >= 0
        with self.lock:
            self.t += timedelta(seconds=s)

    def wait(self, s: float, stopping: threading.Event) -> bool:
        with self.lock:
            over = self.limit is not None and self.t + timedelta(seconds=s) > self.limit
            if not over:
                self.t += timedelta(seconds=s)
        if over:
            self.blocked += 1
            return stopping.wait(5)
        time.sleep(0)  # let the other stream and the test thread run
        return stopping.is_set()


_ids = iter(range(1, 10**9))


def tweet(when: datetime, text: str, cashtags: tuple) -> xf.Tweet:
    tid = next(_ids)
    user = xf.XUser(tid, datetime(2024, 1, 1, tzinfo=timezone.utc), 100, 100, "https://img/p.jpg", False)
    return xf.Tweet(tid, when, f"{text} {tid}", user, "en", cashtags)


class DayReader(xrd.FakeXReader):
    """Answers any coin-day: 20 tweets per page from just before the window end (10 minutes apart), so two pages
    reach N = 40; the canary query gets 20 tweets inside its hour. Records when each page was asked for."""

    def __init__(self, label: str, clock: Clock, fail: BaseException | None = None):
        super().__init__(label)
        self.clock, self.fail, self.sent = clock, fail, []

    def search_raw(self, query, kv, page):
        self.calls.append((query, dict(kv), page))
        self.sent.append((self.clock(), query, page))
        end = datetime.fromtimestamp(int(re.search(r"until_time:(\d+)", query).group(1)), tz=timezone.utc)
        m = re.search(r'"\$([A-Z0-9_]+)"', query)
        if m is None:
            return self.page_of([tweet(end - timedelta(minutes=2 * i + 1), "bitcoin", ()) for i in range(20)])
        if self.fail is not None:
            raise self.fail
        sym, newest = m.group(1), end - timedelta(minutes=1 + 200 * page)
        return self.page_of([tweet(newest - timedelta(minutes=10 * i), sym, (sym,)) for i in range(20)])

    def units(self) -> list[tuple[datetime, str, list[datetime]]]:
        """(start, query, page times) per unit, canary included, in call order."""
        out = []
        for t, query, page in self.sent:
            if page == 0:
                out.append((t, query, [t]))
            else:
                out[-1][2].append(t)
        return out

    def coin_units(self):
        return [u for u in self.units() if '"$' in u[1]]


def entry(i: int, when: datetime, title: str = "SOL ETH ADA BTC news") -> str:
    stamp = when.isoformat()
    return (f'<entry><author><name>/u/a{i}</name><uri>https://www.reddit.com/user/a{i}</uri></author>'
            f'<category term="CryptoCurrency" label="r/CryptoCurrency"/><content type="html">body</content>'
            f'<id>t3_{i:x}</id><link href="https://www.reddit.com/r/CryptoCurrency/comments/{i:x}/t/"/>'
            f'<updated>{stamp}</updated><published>{stamp}</published><title>{title}</title></entry>')


def atom(times) -> bytes:
    return ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>r</title>'
            + "".join(entry(i + 1, t) for i, t in enumerate(times)) + "</feed>").encode()


class RedditFake:
    """A full 100-entry feed every 2 hours back from the clock (reaches 8 days back); `respond` overrides searches."""

    def __init__(self, clock: Clock, respond=None):
        self.clock, self.respond, self.searches, self.canaries = clock, respond, [], []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        now = self.clock()
        if request.url.path.endswith("/new.rss"):
            self.canaries.append(now)
            return httpx.Response(200, content=atom([now - timedelta(minutes=10 * i) for i in range(100)]),
                                  headers={"content-type": "application/atom+xml"})
        self.searches.append((now, str(request.url)))
        if self.respond is not None:
            return self.respond(request)
        return httpx.Response(200, content=atom([now - timedelta(hours=2 * i) for i in range(100)]),
                              headers={"content-type": "application/atom+xml"})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def queries(**over) -> wq.Queries:
    q = wq.load()
    return dataclasses.replace(q, config=dataclasses.replace(q.config, x_accounts=("acct_a",), **over))


def fakes(clock: Clock, *, q=None, coins=COINS, reader=None, reddit=None, **kw):
    """Worker keyword arguments on fakes, and the fakes; state persists in the cache, so a second worker built
    from them is a restart."""
    q = q or queries()
    reader = reader or DayReader("acct_a", clock)
    reddit = reddit or RedditFake(clock)
    start = SimpleNamespace(readers={"acct_a": reader}, fallback=None, close=lambda: None)
    kw.setdefault("seed", 1)
    kw.setdefault("reddit_ledger", lambda: None)
    kwargs = dict(clock=clock, wait=clock.wait, queries=lambda: q, symbols=lambda _q, _s: list(coins),
                  x_start=lambda _cfg: start, x_cleanup=lambda: None, reddit_client=reddit.client, **kw)
    return kwargs, reader, reddit


def make(clock: Clock, **kw):
    kwargs, reader, reddit = fakes(clock, **kw)
    return apr.AttentionPcWorker(**kwargs), reader, reddit


def x_state(clock, q=None) -> pc_pace.PcSource:
    c = (q or queries()).config
    return pc_pace.PcSource(X, configured_budget=c.x_daily_post_budget, floor=c.x_sample_n, adaptive=True,
                            clock=clock)


def seed_points(source: str, symbol: str, days) -> None:
    store.write_series(SourceSeries(source, symbol, [(d, 5.0) for d in days]), today=T0.date())


def state_files() -> list[Path]:
    return sorted((cache.CACHE_ROOT / "attention" / "_pc_state").glob("*.json"))


# --- flag, lifespan, threads --------------------------------------------------------------------------------------

def _pc_threads():
    return [t for t in threading.enumerate() if t.name.startswith("attention-pc")]


def test_flag_off_starts_no_thread():
    for env in ({}, {apr.FLAG_ENV: "0"}, {apr.FLAG_ENV: ""}, {apr.FLAG_ENV: "yes please"}):
        assert apr.start_from_env(env=env) is None
        assert apr.current_worker() is None and apr.disabled_reason() == "flag-off"
    assert _pc_threads() == []


def test_tests_and_runners_never_start_worker_by_default(monkeypatch):
    monkeypatch.delenv(apr.FLAG_ENV, raising=False)
    assert not apr.enabled({})
    with TestClient(__import__("api.main", fromlist=["app"]).app) as client:
        assert client.get("/api/health").status_code == 200
        assert apr.current_worker() is None and _pc_threads() == []
    for wf in sorted((REPO / ".github" / "workflows").glob("*.y*ml")):
        assert apr.FLAG_ENV not in wf.read_text(encoding="utf-8"), wf.name
    assert apr.FLAG_ENV not in (REPO / "api" / "tests" / "conftest.py").read_text(encoding="utf-8")


def test_lifespan_starts_and_stops_worker(monkeypatch):
    clock = Clock(limit=T0 + timedelta(minutes=30))
    kwargs, _, _ = fakes(clock)
    monkeypatch.setenv(apr.FLAG_ENV, "1")
    monkeypatch.setattr(apr, "AttentionPcWorker", functools.partial(apr.AttentionPcWorker, **kwargs))
    from api.main import app
    with TestClient(app):
        w = apr.current_worker()
        assert w is not None and w.running and len(_pc_threads()) == 2
    assert apr.current_worker() is None and _pc_threads() == []
    assert not w.running


def test_stop_worker_joins_thread():
    clock = Clock(limit=T0 + timedelta(minutes=30))
    kwargs, _, _ = fakes(clock)
    started = apr.start_from_env(env={apr.FLAG_ENV: "1"}, **kwargs)
    assert started is apr.current_worker() and started.running
    threads = list(started.threads.values())
    assert [t.name for t in threads] == ["attention-pc-xsearch_web", "attention-pc-reddit_web"]
    apr.stop_worker()
    assert all(not t.is_alive() for t in threads)
    assert apr.current_worker() is None and not started.running
    apr.stop_worker()  # idempotent
    assert not [h for name in apr.LOG_LOGGERS for h in logging.getLogger(name).handlers
                if getattr(h, "attention_pc", False)]


def test_worker_with_two_hours_uptime_stops_cleanly(caplog):
    caplog.set_level(logging.WARNING)
    clock = Clock(limit=T0 + timedelta(hours=2))
    w, reader, reddit = make(clock)
    w.start()
    deadline = time.monotonic() + 20
    while clock.blocked < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert clock.blocked >= 2, "both streams should reach the end of the uptime"
    sent = (len(reader.sent), len(reddit.searches), len(reddit.canaries))
    w.stop()
    assert not w.running and all(not t.is_alive() for t in w.threads.values())
    assert (len(reader.sent), len(reddit.searches), len(reddit.canaries)) == sent
    assert all(t <= T0 + timedelta(hours=2) for t, _q, _p in reader.sent)
    assert reader.coin_units() and reddit.searches
    for p in state_files():
        json.loads(p.read_text(encoding="utf-8"))
    assert not [r for r in caplog.records if "failed" in r.getMessage()]


def test_unit_failure_never_crashes_the_api(caplog):
    caplog.set_level(logging.WARNING)
    clock = Clock(limit=T0 + timedelta(hours=2))
    w, reader, _ = make(clock, reader=DayReader("acct_a", Clock(), RuntimeError("PLANTED-secret-text")))
    reader.clock = clock
    w.start()
    deadline = time.monotonic() + 20
    while clock.blocked < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert w.running and all(t.is_alive() for t in w.threads.values())
    fails = [r.getMessage() for r in caplog.records if "pass failed" in r.getMessage()]
    assert len(fails) >= 2  # retried after RETRY_SECONDS, still alive
    assert all("RuntimeError" in m and "PLANTED" not in m for m in fails)
    w.stop()
    assert TestClient(__import__("api.main", fromlist=["app"]).app).get("/api/health").status_code == 200


# --- fetch side ---------------------------------------------------------------------------------------------------

def test_worker_skips_github_side_sources(tmp_path):
    clock = Clock()
    w, _, _ = make(clock)
    assert set(w.streams) == {X, R}  # the committed discovery.json: default map
    assert apr.FETCH_SIDE["xsearch"] == apr.FETCH_SIDE["reddit"] == apr.PC_SIDE
    assert {s for s, side in apr.FETCH_SIDE.items() if side == apr.GITHUB_SIDE} >= {
        "trends", "wikipedia", "exchange_activity", "defillama", "github_dev"}
    doc = json.loads(apr.DISCOVERY_PATH.read_text(encoding="utf-8"))
    doc["fetch_side"] = {"xsearch": "pc_side", "reddit": "github", "trends": "pc_side"}
    path = tmp_path / "discovery.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert apr.pc_sources(path) == [X]
    w2, _, _ = make(clock, discovery_path=path)
    assert set(w2.streams) == {X}
    doc["fetch_side"] = {"xsearch": "github", "reddit": "github"}
    path.write_text(json.dumps(doc), encoding="utf-8")
    w3, _, _ = make(clock, discovery_path=path)
    assert w3.streams == {}
    w3.start()
    assert _pc_threads() == [] and not w3.running
    w3.stop()


# --- schedule: _behind, waits, locks ------------------------------------------------------------------------------

def test_behind_source_schedules_first_unit_20s_after_start():
    clock = Clock()
    w, reader, reddit = make(clock)
    for s in (X, R):
        assert w.streams[s].schedule() == T0 + timedelta(seconds=20)
    assert reader.sent == [] and reddit.searches == []
    assert w.streams[X].run_pass(stop_at=T0 + timedelta(minutes=2)) == "host_stopped"
    assert reader.sent[0][0] == T0 + timedelta(seconds=20)  # the canary, then units at the configured pace


def test_up_to_date_source_waits():
    clock = Clock()
    q = queries(x_backfill_days=0)
    for sym in COINS:
        seed_points(X, sym, [YESTERDAY])
        seed_points(R, sym, [YESTERDAY - timedelta(days=i) for i in range(7)])
    w, reader, reddit = make(clock, q=q)
    for s in (X, R):
        assert w.streams[s].schedule() == MIDNIGHT + timedelta(seconds=20)
        assert w.streams[s].run_pass() == "done"
    assert reader.sent == [] and reddit.searches == [] and reddit.canaries == []


def test_pass_lock_prevents_overlap():
    clock = Clock()
    w, reader, reddit = make(clock)
    with apr.PASS_LOCKS[X]:
        assert w.streams[X].run_pass() == "locked"
    with apr.PASS_LOCKS[R]:
        assert w.streams[R].run_pass() == "locked"
    assert reader.sent == [] and reddit.searches == [] and reddit.canaries == []
    assert w.streams[X].schedule("locked") >= clock() + timedelta(seconds=20)
    assert w.streams[X].run_pass(stop_at=T0 + timedelta(minutes=10)) == "host_stopped"
    assert reader.sent and not apr.PASS_LOCKS[X].locked()


def test_x_and_reddit_streams_have_separate_locks():
    assert set(apr.PASS_LOCKS) == {X, R} and apr.PASS_LOCKS[X] is not apr.PASS_LOCKS[R]
    clock = Clock()
    w, reader, reddit = make(clock)
    with apr.PASS_LOCKS[X]:
        assert w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=10)) == "host_stopped"
    assert reddit.searches and reader.sent == []
    with apr.PASS_LOCKS[R]:
        assert w.streams[X].run_pass(stop_at=T0 + timedelta(minutes=20)) == "host_stopped"
    assert reader.coin_units()


def test_no_unit_before_min_delay_after_restart():
    clock = Clock()
    w, reader, _ = make(clock)
    w.streams[X].run_pass(stop_at=T0 + timedelta(minutes=4))  # canary, then the first unit
    last = x_state(clock).last_unit_at()
    assert last is not None
    clock.t = last + timedelta(seconds=30)  # crash and restart 30 s after the last unit ended
    w2, _, _ = make(clock, reader=reader)
    due = w2.streams[X].schedule()
    assert due == last + timedelta(seconds=180) > clock() + timedelta(seconds=20)
    n = len(reader.sent)
    w2.streams[X].run_pass(stop_at=clock() + timedelta(minutes=10))
    assert reader.sent[n][0] >= last + timedelta(seconds=180)


def test_restart_at_any_tick_resumes_via_behind_no_burst():
    clock = Clock()
    reader = DayReader("acct_a", clock)
    restarts = []
    for minutes in (1, 7, 8, 13, 26, 27, 41):
        w, _, _ = make(clock, reader=reader)
        restarts.append(clock())
        w.streams[X].run_pass(stop_at=T0 + timedelta(minutes=minutes))
        clock.t = max(clock.t, T0 + timedelta(minutes=minutes))  # the power cut
    units = reader.units()
    assert len(units) >= 6
    for (_s, _q, pages), (start, _q2, _p2) in zip(units, units[1:]):
        assert (start - pages[-1]).total_seconds() >= 180  # never faster than the configured minimum
    for r in restarts:
        after = [u[0] for u in units if u[0] >= r]
        assert not after or after[0] >= r + timedelta(seconds=20)


def test_restart_keeps_pause_and_daily_counts():
    clock = Clock()
    blocked = RedditFake(clock, respond=lambda req: httpx.Response(429))
    w, reader, _ = make(clock, reddit=blocked)
    assert w.streams[R].run_pass() == "paused"
    w.streams[X].run_pass(stop_at=T0 + timedelta(minutes=15))
    r_used, x_used = rw.reddit_source(queries().config, degraded=True, clock=clock).used, x_state(clock).used
    assert r_used == 2 and x_used > 0  # the canary and the 429 search; X canary and units
    sent = (len(blocked.searches), len(blocked.canaries))
    clock.sleep(600)
    w2, _, _ = make(clock, reader=reader, reddit=blocked)  # restart
    assert w2.streams[R].schedule() == MIDNIGHT + timedelta(seconds=20)
    assert w2.streams[R].run_pass() == "paused" and (len(blocked.searches), len(blocked.canaries)) == sent
    assert rw.reddit_source(queries().config, degraded=True, clock=clock).used == r_used
    assert x_state(clock).used == x_used


def test_restart_keeps_effective_budget_and_clean_day_count():
    clock = Clock(datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc))
    src = x_state(clock)
    src.record_unit()
    src.warn("rate_limited")  # a warning day: tomorrow's effective budget is halved
    clock.t = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
    w, _, _ = make(clock, q=queries(x_backfill_days=0))
    assert w.streams[X].source_state().effective_budget() == 400
    for day in range(3):  # three clean days with units
        w, _, _ = make(clock, q=queries(x_backfill_days=0))  # a restart every day
        w.streams[X].run_pass(stop_at=clock() + timedelta(hours=1))
        clock.t = datetime(2026, 10, 22 + day, 10, 0, tzinfo=timezone.utc)
    w, _, _ = make(clock, q=queries(x_backfill_days=0))
    s = w.streams[X].source_state()
    assert s.effective_budget() == 400
    doc = json.loads(pc_pace.state_path(X).read_text(encoding="utf-8"))
    assert doc["clean_days"] == 3 and doc["effective"] == 400


def test_corrupt_state_pauses_source_and_keeps_file():
    clock = Clock()
    path = pc_pace.state_path(X)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    w, reader, _ = make(clock)
    assert w.streams[X].run_pass() == "state_error"
    assert w.streams[X].schedule("state_error") == T0 + timedelta(seconds=apr.RECHECK_SECONDS)
    assert reader.sent == [] and path.read_text(encoding="utf-8") == "{not json"


def test_naive_clock_refused():
    with pytest.raises(ValueError):
        apr.AttentionPcWorker(clock=lambda: datetime(2026, 10, 27, 10, 0), queries=queries)


# --- degraded mode (AC24) and budget (AC21) -----------------------------------------------------------------------

def test_one_hour_uptime_runs_about_13_x_units_and_reddit_concurrently():
    clock = Clock()
    w, reader, reddit = make(clock)
    assert w.mode(clock()) == "degraded"
    stop = T0 + timedelta(hours=1)
    assert w.streams[X].run_pass(stop_at=stop) == "host_stopped"
    clock.t = T0  # the Reddit stream runs over the same hour on its own lock
    w.streams[R].run_pass(stop_at=stop)
    units = reader.coin_units()
    assert 10 <= len(units) <= 16
    starts = [u[0] for u in reader.units()]
    assert all(180 <= (b - a).total_seconds() for a, b in zip(starts, starts[1:]))
    times = [t for t, _u in reddit.searches]
    assert times and reddit.canaries
    assert all(60 <= (b - a).total_seconds() for a, b in zip(times, times[1:]))
    assert len(times) + len(reddit.canaries) <= queries().config.reddit_degraded_request_budget
    for t in [u[0] for u in units] + times:
        assert T0 < t < stop
    assert times[0] < units[-1][0] and units[0][0] < times[-1]  # interleaved over the same hour


def test_three_hour_uptime_x_stops_at_budget():
    clock = Clock()
    w, reader, _ = make(clock)
    stop = T0 + timedelta(hours=3)
    assert w.streams[X].run_pass(stop_at=stop) == "budget_spent"
    src = x_state(clock)
    assert src.used <= queries().config.x_daily_post_budget and src.budget_spent()
    assert clock() < stop
    n = len(reader.sent)
    assert w.streams[X].run_pass(stop_at=stop) == "budget_spent" and len(reader.sent) == n
    assert w.streams[X].schedule("budget_spent") == MIDNIGHT + timedelta(seconds=20)
    assert 17 <= len(reader.coin_units()) <= 20


def test_pc_off_stores_nothing():
    clock = Clock()
    q = queries(x_backfill_days=4)
    w, _, _ = make(clock, q=q)
    w.streams[X].run_pass(stop_at=T0 + timedelta(minutes=30))
    w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=30))
    root = cache.CACHE_ROOT / "attention"
    before = sorted((p.relative_to(root), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file())
    clock.t = T0 + timedelta(days=3)  # the host is off for three days: nothing runs, nothing is written
    after = sorted((p.relative_to(root), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file())
    assert after == before
    back = clock()
    w2, _, _ = make(clock, q=q)
    w2.streams[X].run_pass(stop_at=back + timedelta(minutes=30))
    # a unit that started before the host stopped finishes its pages (5-15 s apart)
    slack = timedelta(seconds=q.config.x_page_cap * q.config.x_page_gap_max_s)
    for source in (X, R):
        for sym in COINS:
            rows = web_evidence.read_rows(source, sym)
            for d, row in rows.items():
                assert row.value > 0 and d < row.collected_at.date()
                in_session = (T0 <= row.collected_at <= T0 + timedelta(minutes=30) + slack
                              or back <= row.collected_at <= back + timedelta(minutes=30) + slack)
                assert in_session
            assert {d for d, _v in store.read_points(source, sym)} == set(rows)
    assert web_evidence.read_rows(X, "SOL") and web_evidence.read_rows(R, "SOL")


def test_unfinished_coin_day_carries_over():
    clock = Clock()
    q = queries(x_backfill_days=2)
    w, reader, _ = make(clock, q=q)
    # the canary at 20 s, then exactly one unit: it is due 200-380 s after the start, a second one not before 385 s
    assert w.streams[X].run_pass(stop_at=T0 + timedelta(seconds=381)) == "host_stopped"
    done_day1 = {s for s in COINS if YESTERDAY in dict(store.read_points(X, s))}
    assert 0 < len(done_day1) < len(COINS)
    clock.t = T0 + timedelta(days=1)  # the next day: a new yesterday, the old one is backfill
    w2, _, _ = make(clock, q=q, reader=reader)
    queue = w2.streams[X].queue()
    new_yesterday = YESTERDAY + timedelta(days=1)
    assert [d for _s, d in queue[:3]] == [new_yesterday] * 3  # yesterday first
    assert {s for s, d in queue if d == YESTERDAY} == set(COINS) - done_day1  # the rest stays queued
    w2.streams[X].run_pass(stop_at=clock() + timedelta(hours=2))
    for s in COINS:
        assert {YESTERDAY, new_yesterday} <= set(dict(store.read_points(X, s)))


def test_rotation_queue_oldest_stored_first():
    clock = Clock()
    seed_points(X, "SOL", [YESTERDAY - timedelta(days=2)])
    seed_points(X, "ETH", [YESTERDAY - timedelta(days=5)])
    w, reader, _ = make(clock, coins=["SOL", "ETH", "ADA"], q=queries(x_backfill_days=0))
    assert w.streams[X].queue() == [("ADA", YESTERDAY), ("ETH", YESTERDAY), ("SOL", YESTERDAY)]
    assert w.streams[X].run_pass(stop_at=T0 + timedelta(hours=1)) == "done"
    order = [re.search(r'"\$([A-Z]+)"', u[1]).group(1) for u in reader.coin_units()]
    assert order == ["ADA", "ETH", "SOL"]  # nothing stored first, then the oldest newest-stored day


# --- baseline and quality (AC37, AC38) ----------------------------------------------------------------------------

def test_mode_switch_baseline_degraded():
    for hour in (0, 9, 17, 23):
        start = datetime(2026, 10, 27, hour, 30, tzinfo=timezone.utc)
        clock = Clock(start)
        w, _, _ = make(clock)
        assert w.mode(start) == "degraded"  # not up for the whole UTC day yet
        assert w.mode(start.replace(hour=23, minute=59)) == "degraded"  # the rest of that UTC day, any hour
        nxt = datetime(2026, 10, 28, 0, 0, 1, tzinfo=timezone.utc)
        assert w.mode(nxt) == "baseline"  # up since before 00:00 UTC of this day
        assert w.mode(nxt + timedelta(days=3)) == "baseline"
        clock.t = nxt + timedelta(hours=hour)
        w2, _, _ = make(clock)  # a restart: degraded again for the rest of that day
        assert w2.mode(clock()) == "degraded"
    # budgets and pace follow the mode
    clock = Clock(datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc))
    w, reader, _ = make(clock)
    assert w.streams[R].source_state().effective_budget() == 150
    clock.t = datetime(2026, 10, 28, 0, 5, tzinfo=timezone.utc)
    assert w.mode(clock()) == "baseline" and w.streams[R].source_state().effective_budget() == 250
    w.streams[X].run_pass(stop_at=clock() + timedelta(hours=6))
    starts = [u[0] for u in reader.units() if u[0] >= datetime(2026, 10, 28, tzinfo=timezone.utc)]
    gaps = [(b - a).total_seconds() for a, b in zip(starts, starts[1:])]
    assert gaps and all(g >= 86400 / 20 for g in gaps)  # 800 / 40 = 20 units spread over the day
    w.x_spread_over_day = False
    clock.t = datetime(2026, 10, 29, 0, 5, tzinfo=timezone.utc)
    n = len(reader.units())
    w.streams[X].run_pass(stop_at=clock() + timedelta(hours=1))
    starts = [u[0] for u in reader.units()[n:]]
    gaps = [(b - a).total_seconds() for a, b in zip(starts, starts[1:])]
    assert gaps and all(180 <= g <= 360 + 30 for g in gaps)


def test_pass_that_cannot_finish_continues_in_next_window():
    clock = Clock()
    q = queries(x_backfill_days=0)
    w, reader, reddit = make(clock, q=q)
    assert w.streams[X].run_pass(stop_at=T0 + timedelta(minutes=4)) == "host_stopped"
    assert w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=2)) == "host_stopped"
    first = {s for s in COINS if YESTERDAY in dict(store.read_points(X, s))}
    assert len(first) < len(COINS)
    clock.t = T0 + timedelta(hours=2)  # the host is back two hours later the same day
    w2, _, _ = make(clock, q=q, reader=reader, reddit=reddit)
    assert w2.streams[X].run_pass(stop_at=clock() + timedelta(hours=1)) == "done"
    assert w2.streams[R].run_pass(stop_at=clock() + timedelta(hours=1)) == "done"
    for s in COINS:
        assert YESTERDAY in dict(store.read_points(X, s)) and YESTERDAY in dict(store.read_points(R, s))
    syms = [re.search(r'"\$([A-Z]+)"', u[1]).group(1) for u in reader.coin_units()]
    assert sorted(syms) == sorted(COINS)  # each coin once: nothing dropped, nothing repeated


def test_no_coin_or_sample_dropped_to_fit_time():
    clock = Clock()
    q = queries(x_backfill_days=0)
    w, reader, reddit = make(clock, q=q)
    for minutes in (4, 9, 14, 30):  # short windows; every unit that starts finishes in full
        w.streams[X].run_pass(stop_at=T0 + timedelta(minutes=minutes))
        clock.t = max(clock.t, T0 + timedelta(minutes=minutes))
    units = reader.coin_units()
    assert len(units) == len(COINS)
    assert all(len(pages) == 2 for _s, _q, pages in units)  # N = 40 reached each time; page cap 3 unchanged
    for s in COINS:
        row = web_evidence.read_rows(X, s)[YESTERDAY]
        assert row.n == q.config.x_sample_n
    w.streams[R].run_pass(stop_at=clock() + timedelta(hours=1))
    for _t, url in reddit.searches:
        assert "t=week" in url and "limit=100" in url


# --- unattended weeks (AC40) --------------------------------------------------------------------------------------

def _sizes(obj, seen=None) -> int:
    """Total length of the containers reachable from a worker (its streams included); files are not counted."""
    seen = seen if seen is not None else set()
    if id(obj) in seen or isinstance(obj, (str, bytes, threading.Thread, random.Random)):
        return 0
    seen.add(id(obj))
    if isinstance(obj, dict):
        return len(obj) + sum(_sizes(v, seen) for v in obj.values())
    if isinstance(obj, (list, set, tuple, frozenset)):
        return len(obj) + sum(_sizes(v, seen) for v in obj)
    if isinstance(obj, (apr.AttentionPcWorker, apr.Stream)):
        return sum(_sizes(v, seen) for v in vars(obj).values())
    return 0


def _ninety_days(clock, w, days=90, probe=None):
    for i in range(days):
        clock.t = datetime(2026, 10, 27, 0, 30, tzinfo=timezone.utc) + timedelta(days=i)
        stop = clock() + timedelta(hours=23)
        w.streams[X].run_pass(stop_at=stop)
        clock.t = datetime(2026, 10, 27, 0, 30, tzinfo=timezone.utc) + timedelta(days=i)
        w.streams[R].run_pass(stop_at=stop)
        if probe:
            probe(i)


@pytest.fixture
def no_fsync(monkeypatch):
    """Ninety days of atomic writes: the disk flush is the slow part and proves nothing here."""
    monkeypatch.setattr(cache.os, "fsync", lambda _fd: None)


def test_state_files_bounded_after_ninety_simulated_days(no_fsync):
    clock = Clock(datetime(2026, 10, 27, 0, 30, tzinfo=timezone.utc))
    q = queries(x_backfill_days=0, x_raw_retention_days=10)
    w, _, _ = make(clock, q=q, coins=["SOL", "ETH"], ledger_retention_days=20,
                   reddit_ledger=lambda: rw.reddit_items.Ledger(rw.reddit_items.AuthorHasher(b"0" * 32)))
    sizes = {}

    def probe(i):
        if i in (30, 89):
            sizes[i] = {p.name: p.stat().st_size for p in state_files()}

    _ninety_days(clock, w, probe=probe)
    assert set(sizes[30]) == set(sizes[89])  # no new state files over time
    assert all(sizes[89][k] <= 4096 for k in sizes[89])
    attention = cache.CACHE_ROOT / "attention"
    ledger_days = sorted(p.stem for p in (attention / "reddit_items").glob("*.json"))
    raw_days = sorted(p.name for p in (attention / "xsearch_raw").iterdir())
    canary_days = sorted(p.stem for p in rw.canary_path(T0.date()).parent.glob("*.json"))
    assert 0 < len(ledger_days) <= 20 + 9  # retention plus the feed's reach (8 days) and today
    assert 0 < len(raw_days) <= 10 + 1
    assert 0 < len(canary_days) <= 20 + 1
    completeness_days = list(rw.completeness_path(T0.date()).parent.glob("*.json"))
    assert 0 < len(completeness_days) <= 20 + 1
    x_completeness = list((attention / X / "_meta" / "_completeness").glob("*.json"))
    assert 0 < len(x_completeness) <= 10 + 1
    stored = dict(store.read_points(X, "SOL"))
    assert len(stored) >= 85  # it kept collecting the whole time


def test_memory_structures_do_not_grow_with_days(no_fsync):
    clock = Clock(datetime(2026, 10, 27, 0, 30, tzinfo=timezone.utc))
    w, _, _ = make(clock, q=queries(x_backfill_days=0), coins=["SOL", "ETH"])
    seen = {}

    def probe(i):
        if i in (10, 89):
            seen[i] = _sizes(w)

    _ninety_days(clock, w, probe=probe)
    assert seen[89] == seen[10]


def test_log_rotation_size_and_count_from_config(tmp_path):
    tmp_path = tmp_path / "logs"  # the cache root is tmp_path itself
    assert apr.log_settings({}) == (apr.LOG_MAX_BYTES_DEFAULT, apr.LOG_FILES_DEFAULT)
    assert apr.log_settings({apr.LOG_MAX_BYTES_ENV: "300", apr.LOG_FILES_ENV: "2"}) == (300, 2)
    assert apr.log_settings({apr.LOG_MAX_BYTES_ENV: "-1", apr.LOG_FILES_ENV: "x"}) == (
        apr.LOG_MAX_BYTES_DEFAULT, apr.LOG_FILES_DEFAULT)
    handler = apr.install_log_handler(tmp_path, max_bytes=300, files=2)
    try:
        log = logging.getLogger("api.data.attention.reddit_web")
        for i in range(200):
            log.warning("line %03d RedditBlocked status=403", i)
        logging.getLogger(apr.__name__).warning("worker line")
    finally:
        apr.remove_log_handler(handler)
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["attention_pc.log", "attention_pc.log.1", "attention_pc.log.2"]
    assert all((tmp_path / f).stat().st_size <= 300 + 100 for f in files)
    assert "worker line" in (tmp_path / "attention_pc.log").read_text(encoding="utf-8")
    assert not [h for name in apr.LOG_LOGGERS for h in logging.getLogger(name).handlers if h is handler]


def test_no_network_in_tests():
    with pytest.raises(OSError):
        socket.create_connection(("192.0.2.1", 443), timeout=0.1)  # TEST-NET-1: refused before any packet
    tree = ast.parse(Path(apr.__file__).read_text(encoding="utf-8"))
    top = {a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names}
    top |= {f"{n.module}.{a.name}" for n in tree.body if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not [m for m in top if "twscrape" in m or m.split(".")[0] in ("socket", "requests", "urllib")]
    clock = Clock()
    w, reader, reddit = make(clock)
    w.streams[X].run_pass(stop_at=T0 + timedelta(minutes=10))
    clock.t = T0  # the Reddit stream runs over the same ten minutes on its own lock
    w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=10))
    assert reader.coin_units() and reddit.searches


# --- W8e2: real producer path -> persisted files -> read-only Sources health -------------------------------

def source_health(tmp_path, monkeypatch, clock, q, sid):
    from api.analytics.attention import sources
    from api.tests.analytics.attention.test_discovery import world

    world(tmp_path, monkeypatch, {s: 5e7 for s in COINS}, cats={"ai": COINS},
          source_impl={"xsearch": X, "reddit": R})
    monkeypatch.setattr(sources, "_collector", lambda: q.config)
    return next(row.health for row in sources.build_sources(clock().date(), now=clock()).sources if row.id == sid)


def test_worker_files_feed_sources_health_without_network(tmp_path, monkeypatch):
    clock = Clock()
    q = queries(x_backfill_days=0)
    worker, reader, reddit = make(clock, q=q)
    assert worker.streams[X].run_pass(stop_at=T0 + timedelta(hours=1)) == "done"
    x = source_health(tmp_path, monkeypatch, clock, q, "xsearch")
    assert (x.attempted, x.fetched, x.completeness_attempted, x.completeness_fetched) == (3, 3, 3, 3)
    assert x.missing == 0 and x.capped == 3 and x.mode == "degraded"
    assert x.expected_gap_s == q.config.x_query_delay_max_s
    assert x.budget_used == x_state(clock, q).used
    assert len(reader.coin_units()) == 3  # daily canary did not inflate attempted
    assert x.accounts_active == x.accounts_total == 1
    clock.t = T0
    assert worker.streams[R].run_pass(stop_at=T0 + timedelta(hours=1)) == "done"
    r = source_health(tmp_path, monkeypatch, clock, q, "reddit")
    assert r.attempted == len(reddit.searches) and r.fetched > 0
    assert r.completeness_attempted == r.completeness_fetched == 3
    assert r.expected_gap_s == q.config.reddit_request_delay_max_s
    assert r.budget_used == len(reddit.searches) + len(reddit.canaries)
    # Restart reads existing evidence; a fetched coin-day is neither requested nor counted twice.
    restarted, _, _ = make(clock, q=q, reader=reader, reddit=reddit)
    restarted.streams[X].run_pass(stop_at=clock() + timedelta(hours=1))
    assert source_health(tmp_path, monkeypatch, clock, q, "xsearch").fetched == 3
    assert len(reader.coin_units()) == 3


@pytest.mark.parametrize("source,sid", [(X, "xsearch"), (R, "reddit")])
def test_attempt_is_durable_before_reader_and_retry_is_distinct(tmp_path, monkeypatch, source, sid):
    class PowerCut(BaseException):
        pass

    clock = Clock()
    q = queries(x_backfill_days=0)
    path = cache.CACHE_ROOT / "attention" / source / "_meta" / "_completeness" / f"{YESTERDAY}.json"

    def cut():
        record = json.loads(path.read_text())["coins"]["SOL"]
        assert record["attempted"] is True and record["reason"] == "unit_interrupted"
        raise PowerCut

    class CuttingReader(DayReader):
        def search_raw(self, query, kv, page):
            if '"$' in query:
                cut()
            return super().search_raw(query, kv, page)

    reddit = RedditFake(clock, respond=lambda request: cut())
    worker, _, _ = make(clock, q=q, coins=["SOL"], reader=CuttingReader("acct_a", clock), reddit=reddit)
    with pytest.raises(PowerCut):
        worker.streams[source].run_pass()
    h = source_health(tmp_path, monkeypatch, clock, q, sid)
    assert h.attempted == 1 and h.fetched == 0
    assert h.missing_reasons["unit_interrupted"] == 1
    clock.t += timedelta(hours=1)
    restarted, _, _ = make(clock, q=q, coins=["SOL"])
    restarted.streams[source].run_pass(stop_at=clock() + timedelta(hours=1))
    h = source_health(tmp_path, monkeypatch, clock, q, sid)
    assert h.completeness_attempted == h.completeness_fetched == 1
    assert h.missing == 0


def test_terminal_reader_exception_records_failed_not_interrupted(tmp_path, monkeypatch):
    clock = Clock()
    q = queries(x_backfill_days=0)
    worker, _, _ = make(clock, q=q, coins=["SOL"], reader=DayReader("acct_a", clock, fail=ValueError("test")))
    with pytest.raises(ValueError):
        worker.streams[X].run_pass()
    h = source_health(tmp_path, monkeypatch, clock, q, "xsearch")
    assert h.attempted == 1 and h.fetched == 0 and h.missing_reasons == {"failed": 1}


def test_persisted_gap_changes_with_real_worker_mode(tmp_path, monkeypatch):
    clock = Clock()
    q = queries(x_backfill_days=0)
    worker, _, _ = make(clock, q=q, coins=["SOL"])
    worker.streams[X].run_pass(stop_at=clock() + timedelta(minutes=10))
    assert source_health(tmp_path, monkeypatch, clock, q, "xsearch").mode == "degraded"
    clock.t = MIDNIGHT
    worker.streams[X].run_pass(stop_at=clock() + timedelta(minutes=10))
    h = source_health(tmp_path, monkeypatch, clock, q, "xsearch")
    assert h.mode == "baseline"
    assert h.expected_gap_s == max(q.config.x_query_delay_max_s, 86400 / (h.effective_budget // q.config.x_sample_n))


# --- unclean stop: the library's in-flight lock after a kill (restart test 30-10-26) ------------------------------

IN_FLIGHT = timedelta(minutes=15)


class PowerCut(BaseException):
    """The host dies: nothing after it runs, nothing unlocks the account in the library's file."""


class LockingReader(DayReader):
    """The library's view of one account file. A request takes the 15-minute in-flight lock at queue take and
    releases it when the page comes back; a kill leaves it. While the lock is in the future the library has no
    account for the queue and raises NoAccountError (`no_account`); the pool row shows the bare lock, active, no
    error. Two ticks per request: `2 i` kills while request i is in flight, `2 i + 1` after X served the page and
    before it reached us. `returned` counts the entries that reached our side."""

    def __init__(self, label, clock, kill_at=None):
        super().__init__(label, clock)
        self.kill_at, self.ticks, self.lock, self.returned, self.taken, self.refused = kill_at, 0, None, 0, [], 0

    def pool_row(self):
        return xrd.PoolRow(True, None, {"SearchTimeline": self.lock} if self.lock else {}, None)

    def _tick(self):
        tick, self.ticks = self.ticks, self.ticks + 1
        if tick == self.kill_at:
            raise PowerCut

    def search_raw(self, query, kv, page):
        now = self.clock()
        if self.lock is not None and now < self.lock:
            self.refused += 1
            raise xrd.ReaderFailure("no_account")
        self.lock = now + IN_FLIGHT
        self.taken.append(now)
        self._tick()
        raw = super().search_raw(query, kv, page)
        self._tick()
        self.lock = None
        self.returned += len(raw.entry_ids)
        return raw


@pytest.fixture
def day_locks(monkeypatch):
    calls = []
    real = xp.XPool.lock_for_day

    def spy(self, label):
        calls.append(label)
        real(self, label)

    monkeypatch.setattr(xp.XPool, "lock_for_day", spy)
    return calls


def _killed(clock, q, reader):
    w, _, _ = make(clock, q=q, reader=reader)
    with pytest.raises(PowerCut):
        w.streams[X].run_pass()
    return reader.taken[-1]


def test_attempt_stamped_before_request_so_killed_request_counts_for_spacing():
    clock = Clock()
    q = queries(x_backfill_days=0)
    reader = LockingReader("acct_a", clock, kill_at=2)  # ticks 0-1 are the canary; the first coin page is in flight
    killed_at = _killed(clock, q, reader)
    assert x_state(clock, q).last_unit_at() == killed_at
    clock.t = killed_at + timedelta(seconds=30)
    w2, _, _ = make(clock, q=q, reader=reader)
    assert w2.streams[X].schedule() >= killed_at + timedelta(seconds=q.config.x_query_delay_min_s)


def test_health_shows_transient_pause_with_real_end(day_locks, tmp_path, monkeypatch):
    clock = Clock()
    q = queries(x_backfill_days=0)
    reader = LockingReader("acct_a", clock, kill_at=2)
    _killed(clock, q, reader)
    end = reader.lock + timedelta(seconds=xp.LOCK_MARGIN_S)
    clock.t += timedelta(minutes=1)
    w2, _, _ = make(clock, q=q, reader=reader)
    assert w2.streams[X].run_pass() == "account_wait"
    health = xp.XPool(["acct_a"], clock=clock).health()
    assert (health["pause_reason"], health["pause_until"]) == ("in_flight_lock", end.isoformat())
    assert (health["accounts"][0]["state"], health["accounts"][0]["reason"]) == ("locked", "in_flight_lock")
    h = source_health(tmp_path, monkeypatch, clock, q, "xsearch")
    assert (h.paused, h.pause_reason, h.pause_until) == (True, "in_flight_lock", end.isoformat())
    assert w2.streams[X].schedule("account_wait") == end < MIDNIGHT
    assert day_locks == []


def test_both_accounts_bare_locked_pass_retries_after_lock_end_not_next_day(day_locks):
    clock = Clock()
    q = queries(x_backfill_days=0)
    q = dataclasses.replace(q, config=dataclasses.replace(q.config, x_accounts=("acct_a", "acct_b")))
    canary = {}

    class SameCanary(LockingReader):  # both accounts see the same canary hour, so the canary agrees
        def search_raw(self, query, kv, page):
            raw = super().search_raw(query, kv, page)
            return raw if '"$' in query else canary.setdefault(query, raw)

    readers = {x: SameCanary(x, clock) for x in ("acct_a", "acct_b")}
    for r in readers.values():
        r.lock = T0 + IN_FLIGHT  # a killed process left both accounts' in-flight locks
    kwargs, _, _ = fakes(clock, q=q)
    kwargs["x_start"] = lambda _cfg: SimpleNamespace(readers=readers, fallback=None, close=lambda: None)
    w = apr.AttentionPcWorker(**kwargs)
    assert w.streams[X].run_pass() == "account_wait"
    end = T0 + IN_FLIGHT + timedelta(seconds=xp.LOCK_MARGIN_S)
    pool = xp.XPool(["acct_a", "acct_b"], clock=clock)
    assert pool.pause_reason() == "in_flight_lock" and pool.resume_at() == end
    due = w.streams[X].schedule("account_wait")
    assert due == end < MIDNIGHT
    clock.t = due - timedelta(seconds=apr.BEHIND_DELAY_S)
    assert w.streams[X].run_pass(stop_at=clock() + timedelta(hours=3)) == "done"
    assert day_locks == [] and all(t >= end for r in readers.values() for t in r.taken)
    for s in COINS:
        assert [d for d, _v in store.read_points(X, s)] == [YESTERDAY]


@pytest.mark.parametrize("tick", range(14))  # canary + 3 coins x 2 pages = 7 requests, two ticks each
def test_kill_at_every_tick_never_pauses_a_utc_day(tick, day_locks, tmp_path, monkeypatch):
    clock = Clock()
    q = queries(x_backfill_days=0)
    reader = LockingReader("acct_a", clock, kill_at=tick)
    killed_at = _killed(clock, q, reader)
    assert reader.lock == killed_at + IN_FLIGHT  # the kill left the library's in-flight lock
    clock.t += timedelta(minutes=1)  # back a minute later, well inside the lock
    w, _, _ = make(clock, q=q, reader=reader)  # the restart
    outcome, outcomes = None, []
    for _ in range(8):  # the worker loop: each pass at the time `schedule` gives
        due = w.streams[X].schedule(outcome)
        assert due < MIDNIGHT, outcomes  # never 'paused until the next UTC day'
        clock.t = max(clock.t, due - timedelta(seconds=apr.BEHIND_DELAY_S))
        outcome = w.streams[X].run_pass(stop_at=clock() + timedelta(hours=3))
        outcomes.append(outcome)
        if outcome == "done":
            break
    assert outcomes[-1] == "done" and "paused" not in outcomes and reader.refused >= 1
    assert day_locks == []
    pool = xp.XPool(["acct_a"], clock=clock)
    assert pool.account_state("acct_a") == ("active", None) and not pool.is_paused()
    assert [t for t in reader.taken if killed_at < t < killed_at + IN_FLIGHT] == []  # waited the lock out
    for s in COINS:
        assert [d for d, _v in store.read_points(X, s)] == [YESTERDAY]  # no duplicate coin-day
        assert len(x_raw.read_x_rows(s)) == 1
    h = source_health(tmp_path, monkeypatch, clock, q, "xsearch")
    assert h.completeness_attempted == h.completeness_fetched == len(COINS) and h.missing == 0
    assert x_state(clock, q).used == reader.returned  # only what reached us, each page once


def test_default_collector_uses_placed_overlay_query(monkeypatch, tmp_path):
    from api.data.attention import onboarding_store
    document = {"narratives": [{"id": "defi", "coins": [{"symbol": "ZZNEW"}]}]}
    placement = tmp_path / "narratives.json"
    placement.write_text(json.dumps(document))
    monkeypatch.setattr(wq, "NARRATIVES_PATH", placement)
    onboarding_store.write_json("attention_queries_auto.json", {"entries": {
        "ZZNEW": {"name": "New Coin", "cashtag_only": True},
        "ZZOFF": {"name": "Not Placed", "cashtag_only": True}}})
    clock = Clock()
    kwargs, _, _ = fakes(clock)
    kwargs.pop("queries")
    kwargs.pop("symbols")
    worker = apr.AttentionPcWorker(**kwargs)
    loaded = worker.queries()
    assert "ZZNEW" in worker.symbols(loaded, X)
    assert "ZZOFF" not in loaded.coins
    assert wq.x_query(loaded, "ZZNEW").startswith('"$ZZNEW"')
