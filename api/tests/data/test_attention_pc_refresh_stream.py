"""W8c2w (T222): the Reddit stream (`reddit_stream`) wired into the PC worker's Reddit pass.

SPEC AC4, AC14, AC24, AC26, AC28-AC30, AC37-AC40, rules 10, 15, 16; owner decisions Q1 (b) budget share 0.45,
Q2 switch `SCREENER_ATTENTION_REDDIT_STREAM=1`, Q3 no Sources row, Q7 canary days. Fakes only: every Reddit request
goes through `httpx.MockTransport`; socket connects off the loopback are refused. Clocks are injected and UTC.
"""
from __future__ import annotations

import dataclasses
import inspect
import ipaddress
import json
import logging
import random
import socket
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from api.data import attention_pc_refresh as apr
from api.data import cache
from api.data.attention import pc_adapter as pa
from api.data.attention import pc_pace, reddit_items, store, web_evidence
from api.data.attention import reddit_stream as rs
from api.data.attention import reddit_web as rw
from api.data.attention import web_queries as wq
from api.data.attention.types import SourceSeries
from api.tests.tooling_guards.test_pc_collector_guards import fixed_hour_offenders

R = apr.REDDIT_SOURCE
S = rs.SOURCE
T0 = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
YESTERDAY = date(2026, 10, 26)
MIDNIGHT = datetime(2026, 10, 28, tzinfo=timezone.utc)
COINS = ["SOL", "ETH", "ADA"]
SALT = b"0123456789abcdef0123456789abcdef"
REPO = Path(__file__).resolve().parents[3]
STREAM_KINDS = ("comments", "new")


def _loopback(host) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def _isolated(isolated_cache, monkeypatch):
    real_connect = socket.socket.connect

    def refuse(self, address, *a, **k):
        if isinstance(address, tuple) and _loopback(address[0]):
            return real_connect(self, address, *a, **k)
        raise OSError("network blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.delenv("SCREENER_ATTENTION_REDDIT_STREAM", raising=False)
    yield isolated_cache
    apr.stop_worker()


# --- fakes ----------------------------------------------------------------------------------------------------------

class Clock:
    def __init__(self, t: datetime = T0):
        self.t, self.lock = t, threading.Lock()

    def __call__(self) -> datetime:
        with self.lock:
            return self.t

    def wait(self, s: float, stopping: threading.Event) -> bool:
        assert s >= 0
        with self.lock:
            self.t += timedelta(seconds=s)
        return stopping.is_set()


GRID0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def grid(now: datetime, span_h: float, count: int) -> list[datetime]:
    step = timedelta(hours=span_h) / 100
    k = int((now - GRID0) / step)
    return [GRID0 + step * (k - i) for i in range(count)]


def rid(prefix: str, when: datetime) -> str:
    return f"{prefix}_{int(when.timestamp()) // 60:x}"


def entry(i: str, when: datetime, title: str = "SOL ETH ADA BTC news") -> str:
    stamp = when.isoformat()
    return (f'<entry><author><name>/u/a{i}</name></author>'
            f'<category term="CryptoCurrency" label="r/CryptoCurrency"/><content type="html">body</content>'
            f'<id>{i}</id><updated>{stamp}</updated><published>{stamp}</published><title>{title}</title></entry>')


def atom(rows: list[tuple[str, datetime]]) -> bytes:
    return ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>r</title>'
            + "".join(entry(i, t) for i, t in rows) + "</feed>").encode()


def ok(body: bytes) -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": "application/atom+xml"})


@dataclasses.dataclass
class Req:
    t: datetime
    kind: str
    url: str
    ua: str | None
    reddit_locked: bool
    x_locked: bool


def kind_of(url: httpx.URL) -> str:
    p = url.path
    if p.endswith("/search.rss"):
        return "search"
    if p.endswith("/comments/.rss"):
        return "comments"
    if p.endswith("/new/.rss"):
        return "new"
    if p.endswith("/new.rss"):
        return "canary"
    return "other"


class Net:
    """Every Reddit endpoint on one fake: canary, per-coin search and the two stream feeds, all following the clock.
    `override(kind, request, n_of_kind)` may answer instead (None: the default answer)."""

    def __init__(self, clock: Clock, override=None, *, comments_span_h: float = 15.0, posts_span_h: float = 72.0,
                 depth: int = 1500):
        self.clock, self.override, self.log = clock, override, []
        self.comments_span_h, self.posts_span_h, self.depth = comments_span_h, posts_span_h, depth

    def __call__(self, request: httpx.Request) -> httpx.Response:
        now = self.clock()
        kind = kind_of(request.url)
        n = sum(r.kind == kind for r in self.log)
        self.log.append(Req(now, kind, str(request.url), request.headers.get("user-agent"),
                            apr.PASS_LOCKS[R].locked(), apr.PASS_LOCKS[apr.X_SOURCE].locked()))
        if self.override is not None:
            got = self.override(kind, request, n)
            if got is not None:
                return got
        if kind == "canary":
            return ok(atom([(rid("t3", now - timedelta(minutes=i)), now - timedelta(minutes=10 * i))
                            for i in range(100)]))
        if kind == "search":
            return ok(atom([(f"t3_s{n}x{i}", now - timedelta(hours=2 * i)) for i in range(100)]))
        prefix, span = ("t1", self.comments_span_h) if kind == "comments" else ("t3", self.posts_span_h)
        deep = grid(now, span, self.depth)
        times = deep[:100]
        after = parse_qs(urlsplit(str(request.url)).query).get("after")
        if after:
            last = next((w for w in deep if rid(prefix, w) == after[0]), None)
            times = [w for w in deep if w < last][:100] if last is not None else []
        return ok(atom([(rid(prefix, w), w) for w in times]))

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))

    def of(self, *kinds) -> list[Req]:
        return [r for r in self.log if r.kind in kinds]

    def stream(self) -> list[Req]:
        return self.of(*STREAM_KINDS)


def queries(**over) -> wq.Queries:
    q = wq.load()
    return dataclasses.replace(q, config=dataclasses.replace(q.config, **over))


def ledger() -> reddit_items.Ledger:
    return reddit_items.Ledger(reddit_items.AuthorHasher(SALT))


def _no_x(_cfg):
    raise AssertionError("X must not start in these tests")


def make(clock: Clock, *, stream=True, q=None, net=None, coins=COINS, led=True, started=None, **kw):
    """A worker on fakes. `started`: when the process started (default: now, i.e. DEGRADED for the rest of the day)."""
    q = q or queries()
    net = net or Net(clock)
    now = clock.t
    if started is not None:
        clock.t = started
    args = dict(clock=clock, wait=clock.wait, queries=lambda: q, symbols=lambda _q, _s: list(coins),
                x_start=_no_x, x_cleanup=lambda: None, reddit_client=net.client,
                reddit_ledger=ledger if led else (lambda: None), seed=1, **kw)
    if stream is not None:
        args["reddit_stream"] = stream
    w = apr.AttentionPcWorker(**args)
    clock.t = now
    return w, net


def baseline(clock: Clock, **kw):
    """A worker up since before 00:00 UTC of the clock's day: BASELINE."""
    return make(clock, started=apr._day_start(clock.t) - timedelta(hours=1), **kw)


def drive(w, clock: Clock, until: datetime, *, max_passes: int = 2000) -> list[str]:
    """The stream loop on the fake clock: schedule -> wait (due - 20 s) -> run_pass, until the next unit would be
    due at or after `until` (the host stops there, so that unit is never sent)."""
    s, out, outcome = w.streams[R], [], None
    for _ in range(max_passes):
        due = s.schedule(outcome)
        if due >= until:
            return out
        clock.t = max(clock.t, due - timedelta(seconds=apr.BEHIND_DELAY_S))
        outcome = s.run_pass(stop_at=until)
        out.append(outcome)
        if clock.t >= until:
            return out
    raise AssertionError("the schedule did not advance")


def share_of(w, q=None):
    s = w.streams[R]
    q = q or w.queries()
    return s.stream_share(q, s.source_state(q))


def budget_doc(day: date) -> dict | None:
    return apr.read_stream_budget(day)


def set_count(day: date, n: int) -> None:
    path = apr.stream_budget_path(day)
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json({"day": day.isoformat(), "requests": n, "cap": None, "budget": None,
                              "share_exhausted": False, "exhausted_at": None}, path)


def shared(clock, *, degraded=True, q=None) -> pc_pace.PcSource:
    return rw.reddit_source((q or queries()).config, degraded=degraded, clock=clock)


def seed_web(days, symbols=COINS) -> None:
    for sym in symbols:
        store.write_series(SourceSeries(R, sym, [(d, 5.0) for d in days]), today=T0.date())


def all_days_seeded():
    seed_web([YESTERDAY - timedelta(days=i) for i in range(7)])


def stream_dir() -> Path:
    return cache.CACHE_ROOT / "attention" / S


def gaps(reqs: list[Req]) -> list[float]:
    ts = sorted(r.t for r in reqs)
    return [(b - a).total_seconds() for a, b in zip(ts, ts[1:])]


def polls_of(kind: str, day: date) -> list[rs.Poll]:
    return [p for p in rs.read_polls(day, day) if p.kind == kind]


# --- switch and no regression (Q2) ----------------------------------------------------------------------------------

def test_stream_off_by_default_runs_only_search_pass_as_before():
    clock = Clock()
    w, net = make(clock, stream=None)
    assert w.reddit_stream is False
    assert w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=10)) == "host_stopped"
    assert net.of("search") and net.stream() == []
    assert {r.kind for r in net.log} <= {"search", "canary"}
    assert not stream_dir().exists()


@pytest.mark.parametrize("value,on", [("1", True), (None, False), ("", False), ("0", False), ("true", False),
                                      (" 1", False), ("2", False), ("1 ", False), ("yes", False)])
def test_stream_flag_only_exact_one_enables(value, on, monkeypatch):
    env = {} if value is None else {apr.STREAM_ENV: value}
    assert apr.STREAM_ENV == "SCREENER_ATTENTION_REDDIT_STREAM"
    assert apr.stream_enabled(env) is on
    seen = {}

    class Capture:
        streams: dict = {}  # the worker's stream map (named in the collector heartbeat)

        def __init__(self, **kw):
            seen.update(kw)

        def start(self):
            return None

        def stop(self, timeout=None):
            return None

    monkeypatch.setattr(apr, "AttentionPcWorker", Capture)
    assert apr.start_from_env(env={apr.FLAG_ENV: "1", **env}) is not None
    assert seen["reddit_stream"] is on


def test_start_from_env_without_variable_means_stream_off(monkeypatch):
    seen = {}

    class Capture:
        streams: dict = {}

        def __init__(self, **kw):
            seen.update(kw)

        def start(self):
            return None

        def stop(self, timeout=None):
            return None

    monkeypatch.setattr(apr, "AttentionPcWorker", Capture)
    apr.start_from_env(env={apr.FLAG_ENV: "1"})
    assert seen.get("reddit_stream") is False
    assert apr.STREAM_ENV not in (REPO / "api" / "tests" / "conftest.py").read_text(encoding="utf-8")
    for wf in sorted((REPO / ".github" / "workflows").glob("*.y*ml")):
        assert apr.STREAM_ENV not in wf.read_text(encoding="utf-8"), wf.name


def test_stream_off_leaves_schedule_outcomes_unchanged():
    clock = Clock()
    w, net = make(clock, stream=False)
    s = w.streams[R]
    assert s.schedule() == T0 + timedelta(seconds=20)
    assert s.schedule("done") == MIDNIGHT + timedelta(seconds=20)
    assert s.schedule("paused") == MIDNIGHT + timedelta(seconds=20)
    assert s.run_pass(stop_at=T0 + timedelta(minutes=10)) == "host_stopped"
    all_days_seeded()
    assert s.schedule() == MIDNIGHT + timedelta(seconds=20)
    assert s.run_pass() == "done"
    assert net.stream() == []


def test_env_off_sends_zero_stream_requests_and_writes_no_stream_store_files():
    assert apr.stream_enabled({}) is False
    clock = Clock()
    w, net = make(clock, stream=apr.stream_enabled({}))
    drive(w, clock, T0 + timedelta(hours=6))
    assert net.of("search") and net.stream() == []
    assert not stream_dir().exists()


# --- cadence (AC37 c) -----------------------------------------------------------------------------------------------

def test_baseline_24h_polls_comments_every_7200s_posts_every_21600s():
    clock = Clock(datetime(2026, 10, 27, 0, 0, 30, tzinfo=timezone.utc))
    w, net = baseline(clock)
    assert w.mode(clock()) == "baseline"
    drive(w, clock, MIDNIGHT)
    day = date(2026, 10, 27)
    for kind, interval, n in (("comments", 7200, 12), ("new", 21600, 4)):
        polls = polls_of(kind, day)
        assert len(polls) == n, kind
        steps = [(b.collected_at - a.collected_at).total_seconds() for a, b in zip(polls, polls[1:])]
        assert all(interval <= g <= interval + 600 for g in steps), (kind, steps)


def test_polls_and_searches_never_closer_than_min_delay():
    clock = Clock()
    w, net = make(clock)
    drive(w, clock, T0 + timedelta(hours=8))
    assert net.stream() and net.of("search")
    assert min(gaps(net.log)) >= 60


def test_search_slice_resumes_at_spacing_after_poll():
    clock = Clock()
    w, net = make(clock)
    drive(w, clock, T0 + timedelta(hours=6))
    log = net.log
    after_poll = [(a, b) for a, b in zip(log, log[1:])
                  if a.kind in STREAM_KINDS and b.kind in ("search", "canary")]
    assert after_poll
    assert all(60 <= (b.t - a.t).total_seconds() <= 120 + apr.BEHIND_DELAY_S for a, b in after_poll)


def test_empty_search_queue_still_polls_stream():
    clock = Clock()
    all_days_seeded()
    w, net = make(clock)
    out = w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    assert out != "done" or net.stream()
    assert {r.kind for r in net.stream()} == {"comments", "new"} and net.of("search") == []
    assert w.streams[R].schedule(out) < MIDNIGHT


def test_done_outcome_with_stream_on_waits_for_next_poll_not_next_day():
    clock = Clock()
    all_days_seeded()
    w, net = make(clock)
    out = w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    assert out == "done"
    last = polls_of("comments", T0.date())[-1].collected_at
    due = w.streams[R].schedule("done")
    assert due == last + timedelta(seconds=7200)
    assert due < MIDNIGHT


def test_next_poll_due_matches_due_kinds():
    q = queries()
    clock = Clock()
    w, _ = make(clock, q=q)
    s = w.streams[R]
    rng = random.Random(7)
    t = T0
    for _ in range(40):
        t += timedelta(seconds=rng.randint(600, 9000))
        kind = rng.choice(STREAM_KINDS)
        rs.append_poll(rs.Poll(kind, t, t - timedelta(minutes=1), t - timedelta(hours=1), 5, 1, False, None))
        now = t + timedelta(seconds=rng.randint(0, 9000))
        due = s.next_poll_due(q, now)
        assert due is not None
        if due > now:
            assert rs.due_kinds(q, due) != [], now
            assert rs.due_kinds(q, due - timedelta(seconds=1)) == [] or due - timedelta(seconds=1) < now
        else:
            assert rs.due_kinds(q, now) != []


# --- degraded mode (AC24, AC28, AC30; Q1 b) ------------------------------------------------------------------------

def test_degraded_mode_polls_stream_within_share():
    clock = Clock()
    w, net = make(clock)
    assert w.mode(clock()) == "degraded"
    drive(w, clock, MIDNIGHT)
    n = len([r for r in net.stream() if r.t.date() == T0.date()])
    assert 0 < n <= 67
    assert budget_doc(T0.date())["requests"] == n


def test_degraded_stream_never_starts_a_request_once_count_reached_67_at_default_share():
    clock = Clock()
    set_count(T0.date(), 67)
    w, net = make(clock)
    drive(w, clock, T0 + timedelta(hours=4))
    assert net.stream() == [] and net.of("search")
    assert budget_doc(T0.date())["requests"] == 67


def test_mode_switch_stream_starts_next_utc_day_when_up_since_midnight():
    clock = Clock()
    w, net = make(clock)
    assert w.mode(clock()) == "degraded" and share_of(w).cap() == 67
    drive(w, clock, MIDNIGHT + timedelta(hours=3))
    assert w.mode(clock()) == "baseline" and share_of(w).cap() == 112
    nextday = [r for r in net.stream() if r.t >= MIDNIGHT]
    assert nextday and budget_doc(MIDNIGHT.date())["requests"] == len(nextday)


def test_no_fixed_utc_hour_in_stream_schedule():
    src = inspect.getsource(apr.RedditStream) + inspect.getsource(apr.StreamShare)
    import textwrap
    assert fixed_hour_offenders(textwrap.dedent(src)) == []
    firsts = []
    for start in (T0, T0 + timedelta(hours=7, minutes=13)):
        clock = Clock(start)
        w, net = make(clock, net=None)
        w.streams[R].run_pass(stop_at=start + timedelta(minutes=30))
        firsts.append(net.stream()[0].t - start)
        for p in (stream_dir() / "_meta").rglob("*.json"):
            p.unlink()
        for p in (cache.CACHE_ROOT / "attention" / "_pc_state").glob("*.json"):
            p.unlink()
    assert firsts[0] == firsts[1]


# --- budget share across a mode change inside one UTC day (W11b) ---------------------------------------------------

def test_budget_baseline_to_degraded_same_utc_day_count_not_refunded_stream_sends_nothing_more():
    clock = Clock()
    set_count(T0.date(), 100)
    w, _ = baseline(clock)
    assert share_of(w).cap() == 112 and share_of(w).can_spend(1)
    w2, net = make(clock)  # restart: DEGRADED for the rest of the day
    assert share_of(w2).cap() == 67 and not share_of(w2).can_spend(1)
    drive(w2, clock, T0 + timedelta(hours=3))
    assert net.stream() == [] and net.of("search")
    assert budget_doc(T0.date())["requests"] == 100


def test_budget_degraded_to_baseline_same_utc_day_remaining_baseline_cap_applies():
    clock = Clock()
    set_count(T0.date(), 40)
    w, _ = baseline(clock)
    sh = share_of(w)
    sent = 0
    while sh.can_spend(1):
        sh.spend(1)
        sent += 1
    assert sent == 72 and budget_doc(T0.date())["requests"] == 112
    with pytest.raises(pa.BudgetSpent):
        sh.spend(1)


def test_stream_never_starts_a_request_when_count_at_or_above_current_mode_cap():
    clock = Clock()
    w, _ = baseline(clock)
    for count, allowed in ((111, True), (112, False), (113, False), (500, False)):
        set_count(T0.date(), count)
        sh = share_of(w)
        assert sh.can_spend(1) is allowed, count
        if not allowed:
            with pytest.raises(pa.BudgetSpent):
                sh.spend(1)
            assert budget_doc(T0.date())["requests"] == count


def test_shared_reddit_web_budget_stays_hard_limit_in_both_modes():
    for degraded, budget in ((True, 150), (False, 250)):
        clock = Clock(T0 + timedelta(days=0 if degraded else 1))
        w, _ = (make(clock) if degraded else baseline(clock))
        src = w.streams[R].source_state(w.queries())
        src.spend(budget - 1)
        sh = w.streams[R].stream_share(w.queries(), src)
        assert sh.can_spend(1)
        sh.spend(1)
        assert not sh.can_spend(1) and src.budget_spent()
        assert budget_doc(clock().date())["requests"] == 1


# --- budget share key in the worker (Q1 b, default 0.45) ------------------------------------------------------------

def test_stream_cap_is_112_baseline_and_67_degraded_at_default_share():
    clock = Clock()
    assert queries().config.reddit_stream_budget_share == 0.45
    w, _ = make(clock)
    assert share_of(w).cap() == 67
    w2, _ = baseline(clock)
    assert share_of(w2).cap() == 112
    w3, _ = baseline(clock, q=queries(reddit_stream_budget_share=1))
    assert share_of(w3).cap() == 250


def _spend_all(sh) -> int:
    n = 0
    while sh.can_spend(1):
        sh.spend(1)
        n += 1
    return n


def test_stream_spend_capped_by_share_in_baseline_250():
    clock = Clock()
    w, _ = baseline(clock)
    assert _spend_all(share_of(w)) == 112
    src = shared(clock, degraded=False)
    assert src.used == 112 and src.can_spend(1) and src.remaining() == 138


def test_stream_spend_capped_by_share_in_degraded_150():
    clock = Clock()
    w, _ = make(clock)
    assert _spend_all(share_of(w)) == 67
    src = shared(clock)
    assert src.used == 67 and src.remaining() == 83


def test_poll_cut_by_share_is_truncated_keeps_cursor_not_dropped():
    clock = Clock()
    set_count(T0.date(), 66)
    all_days_seeded()
    w, net = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    assert len(net.stream()) == 1
    [p] = polls_of("comments", T0.date())
    assert p.truncated and p.runs and p.runs[-1][2].startswith("t1_")
    assert budget_doc(T0.date())["share_exhausted"] is True


def test_share_cut_poll_continues_at_first_poll_next_utc_day():
    clock = Clock()
    set_count(T0.date(), 66)
    all_days_seeded()
    w, net = make(clock)
    drive(w, clock, MIDNIGHT + timedelta(hours=1))
    today = [r for r in net.stream() if r.t < MIDNIGHT]
    after = [r for r in net.stream() if r.t >= MIDNIGHT]
    assert len(today) == 1 and after
    assert after[0].kind == "comments" and (after[0].t - MIDNIGHT).total_seconds() < 600


def test_share_spent_does_not_mark_shared_budget_spent():
    clock = Clock()
    set_count(T0.date(), 67)
    w, _ = make(clock)
    sh = share_of(w)
    assert not sh.can_spend(1)
    sh.mark_spent()
    src = shared(clock)
    assert not src.budget_spent() and src.can_spend(1)
    doc = json.loads(pc_pace.state_path(R).read_text(encoding="utf-8")) if pc_pace.state_path(R).exists() else {}
    assert doc.get("spent_day") is None


def test_searches_keep_the_remainder_when_share_is_spent():
    clock = Clock()
    set_count(T0.date(), 67)
    w, net = make(clock)
    out = w.streams[R].run_pass(stop_at=T0 + timedelta(hours=2))
    assert out in ("done", "host_stopped", "stream_due") and out != "budget_spent"
    assert len(net.of("search")) > 5 and net.stream() == []


def test_unused_stream_share_stays_available_to_searches():
    clock = Clock()
    w, _ = baseline(clock)
    src = w.streams[R].source_state(w.queries())
    src.spend(200)  # searches took more than 250 - 112
    sh = w.streams[R].stream_share(w.queries(), src)
    assert sh.can_spend(1)
    assert src.remaining() == 50


def test_stream_spend_counter_survives_restart_same_utc_day():
    clock = Clock()
    w, _ = make(clock)
    sh = share_of(w)
    for _ in range(5):
        sh.spend(1)
    w2, _ = make(clock)
    assert share_of(w2).requests() == 5


def test_stream_spend_counter_resets_next_utc_day():
    clock = Clock()
    w, _ = make(clock)
    share_of(w).spend(3)
    clock.t = MIDNIGHT + timedelta(minutes=5)
    assert share_of(w).requests() == 0
    assert budget_doc(T0.date())["requests"] == 3 and budget_doc(MIDNIGHT.date()) is None


def test_baseline_cap_reached_mid_day_truncates_remaining_polls_next_utc_day_continues_nothing_dropped():
    clock = Clock(datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc))
    set_count(T0.date(), 111)
    all_days_seeded()
    w, net = baseline(clock)
    drive(w, clock, MIDNIGHT + timedelta(hours=3))
    today = [r for r in net.stream() if r.t < MIDNIGHT]
    assert len(today) == 1
    doc = budget_doc(T0.date())
    assert doc["share_exhausted"] is True and doc["requests"] == 112 and doc["cap"] == 112
    assert [r for r in net.stream() if r.t >= MIDNIGHT]
    assert polls_of("comments", MIDNIGHT.date())


def test_cap_truncated_day_is_missing_or_partial_never_zero():
    clock = Clock()
    set_count(T0.date(), 66)
    all_days_seeded()
    w, net = make(clock)
    drive(w, clock, MIDNIGHT + timedelta(hours=3))
    for sym in COINS:
        assert all(v != 0 for _d, v in store.read_points(S, sym))
    doc = rs.read_completeness(T0.date())
    if doc is not None:
        assert all(c["value"] is None or c["value"] > 0 for c in doc["coins"].values())


# --- one counting path (W11) ----------------------------------------------------------------------------------------

def _round(w, clock, net, q=None):
    """One stream round through the share wrapper, as the worker builds it."""
    s = w.streams[R]
    q = q or w.queries()
    src = s.source_state(q)
    sh = s.stream_share(q, src)
    client = net.client()
    res = rs.run_due(client, sh, q, ledger=s._ledger_obj(), clock=clock, sleep=w._sleep, rng=random.Random(1))
    return res, src


def test_stream_counter_equals_requests_sent_no_double_count():
    clock = Clock()
    w, net = make(clock)
    used0 = shared(clock).used
    res, src = _round(w, clock, net)
    n = len(net.stream())
    assert n >= 2
    assert share_of(w).requests() == n
    assert shared(clock).used - used0 == n
    assert sum(o.requests for o in res.outcomes) == n


def test_stream_counter_counts_failed_empty_and_dead_cursor_requests_that_poll_records_miss():
    clock = Clock()

    def over(kind, req, n):
        if kind == "comments" and n == 1:
            return httpx.Response(500)
        if kind == "new":
            return ok(atom([]))
        return None

    net = Net(clock, over)
    w, _ = make(clock, net=net)
    _round(w, clock, net)
    sent = len(net.stream())
    assert share_of(w).requests() == sent
    pages = sum(p.pages for p in rs.read_polls(T0.date(), T0.date()))
    assert pages < sent


def test_stream_counter_after_restart_continues_from_file_no_double_count():
    clock = Clock()
    w, net = make(clock)
    _round(w, clock, net)
    n = len(net.stream())
    w2, _ = make(clock, net=net)
    assert share_of(w2).requests() == n
    clock.t += timedelta(hours=3)
    _round(w2, clock, net)
    m = len(net.stream()) - n
    assert m > 0 and share_of(w2).requests() == n + m


@pytest.mark.parametrize("status", [403, 429, 500])
def test_failed_request_counts_once(status):
    clock = Clock()
    net = Net(clock, lambda kind, req, n: httpx.Response(status) if kind == "comments" else None)
    w, _ = make(clock, net=net)
    s = w.streams[R]
    q = w.queries()
    src = s.source_state(q)
    sh = s.stream_share(q, src)
    out = rs.run_poll(net.client(), sh, q, kind="comments", ledger=ledger(), sleep=w._sleep, rng=random.Random(1))
    assert out.requests == 1 and len(net.of("comments")) == 1
    assert sh.requests() == 1 and shared(clock).used == 1


def test_unexpected_exception_in_poll_still_counts_its_request_once():
    clock = Clock()

    def boom(kind, req, n):
        raise RuntimeError("unexpected")

    net = Net(clock, boom)
    w, _ = make(clock, net=net)
    s = w.streams[R]
    q = w.queries()
    sh = s.stream_share(q, s.source_state(q))
    with pytest.raises(RuntimeError):
        rs.run_poll(net.client(), sh, q, kind="comments", ledger=ledger(), sleep=w._sleep, rng=random.Random(1))
    assert sh.requests() == 1 and shared(clock).used == 1


def test_spend_refused_by_shared_budget_does_not_increment_stream_counter():
    clock = Clock()
    w, _ = make(clock)
    s = w.streams[R]
    q = w.queries()
    src = s.source_state(q)
    src.spend(150)
    sh = s.stream_share(q, src)
    assert not sh.can_spend(1)
    with pytest.raises(pa.BudgetSpent):
        sh.spend(1)
    assert sh.requests() == 0


# --- share-exhausted record (W12) -----------------------------------------------------------------------------------

def test_share_exhausted_recorded_with_cap_and_count_distinct_from_no_entry():
    clock = Clock()
    w, _ = baseline(clock)
    sh = share_of(w)
    _spend_all(sh)
    doc = budget_doc(T0.date())
    assert doc["share_exhausted"] is True and doc["requests"] == 112 and doc["cap"] == 112
    assert doc["budget"] == 250 and doc["exhausted_at"] is not None
    assert budget_doc(T0.date() - timedelta(days=1)) is None  # a day with no entry: no record, never 0


def test_share_exhausted_not_set_when_shared_budget_is_the_reason():
    clock = Clock()
    w, _ = make(clock)
    s = w.streams[R]
    q = w.queries()
    src = s.source_state(q)
    src.spend(150)
    sh = s.stream_share(q, src)
    assert not sh.can_spend(1)
    sh.mark_spent()
    doc = budget_doc(T0.date())
    assert doc is None or doc["share_exhausted"] is False
    assert src.budget_spent()


def test_share_exhausted_day_without_completeness_file_is_missing_never_zero():
    clock = Clock()
    w, _ = make(clock)
    _spend_all(share_of(w))
    clock.t = MIDNIGHT + timedelta(hours=1)
    st = rs.stream_status(clock(), queries(), days=1)
    day = st["days"][T0.date().isoformat()]
    assert rs.read_completeness(T0.date()) is None
    assert day["coverage_comments"] is None and day["fetched"] is None and day["missing"] is None
    assert budget_doc(T0.date())["share_exhausted"] is True
    assert all(store.read_points(S, sym) == [] for sym in COINS)


def test_share_exhausted_record_carries_cap_and_budget_of_current_mode():
    clock = Clock()
    w, _ = make(clock)
    _spend_all(share_of(w))
    doc = budget_doc(T0.date())
    assert (doc["cap"], doc["budget"], doc["requests"], doc["share_exhausted"]) == (67, 150, 67, True)


# --- shared budget and pause (rules 10, 15, 16; AC24) ---------------------------------------------------------------

def test_stream_and_search_requests_count_in_one_budget():
    clock = Clock()
    w, net = make(clock)
    drive(w, clock, T0 + timedelta(hours=3))
    assert net.stream() and net.of("search")
    assert shared(clock).used == len(net.log)
    assert budget_doc(T0.date())["requests"] == len(net.stream())


def test_budget_spent_by_polls_stops_searches_until_next_utc_day():
    clock = Clock()
    q = queries(reddit_stream_budget_share=1)
    src = shared(clock, q=q)
    src.spend(149)
    w, net = make(clock, q=q)
    out = w.streams[R].run_pass(stop_at=T0 + timedelta(hours=2))
    assert out == "budget_spent"
    assert net.of("search") == [] and len(net.stream()) == 1
    assert w.streams[R].schedule(out) == MIDNIGHT + timedelta(seconds=20)


def _pause_by_poll(status):
    clock = Clock()
    net = Net(clock, lambda kind, req, n: httpx.Response(status) if kind == "comments" else None)
    w, _ = make(clock, net=net)
    out = w.streams[R].run_pass(stop_at=T0 + timedelta(hours=2))
    assert out == "paused" and shared(clock).is_paused()
    assert net.of("search") == [] and net.of("canary") == []
    assert w.streams[R].schedule(out) == MIDNIGHT + timedelta(seconds=20)
    clock.t += timedelta(hours=3)
    assert w.streams[R].run_pass() == "paused" and len(net.log) == 1


def test_pause_by_poll_403_pauses_searches_same_day():
    _pause_by_poll(403)


def test_pause_by_poll_429_pauses_searches_same_day():
    _pause_by_poll(429)


def _pause_by_search(status):
    clock = Clock()
    for kind in STREAM_KINDS:  # polls just ran: not due during the first pass
        rs.append_poll(rs.Poll(kind, T0 - timedelta(minutes=5), T0 - timedelta(minutes=6), T0 - timedelta(hours=1),
                               5, 1, False, None))
    net = Net(clock, lambda kind, req, n: httpx.Response(status) if kind == "search" else None)
    w, _ = make(clock, net=net)
    assert w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1)) == "paused"
    assert net.stream() == [] and net.of("search")
    clock.t = T0 + timedelta(hours=7)
    assert w.streams[R].run_pass() == "paused"
    assert net.stream() == []


def test_pause_by_search_403_stops_polls_same_day():
    _pause_by_search(403)


def test_pause_by_search_429_stops_polls_same_day():
    _pause_by_search(429)


def test_stream_requests_use_honest_user_agent_no_redirect_no_proxy():
    clock = Clock()
    w, net = make(clock)
    _round(w, clock, net)
    assert net.stream() and all(r.ua == wq.HONEST_USER_AGENT for r in net.stream())
    default = apr.AttentionPcWorker(clock=clock, queries=queries, reddit_stream=True)
    assert default.reddit_client is rw.make_client
    client = rw.make_client()
    assert client.follow_redirects is False and client._trust_env is False
    client.close()
    clock2 = Clock(T0 + timedelta(days=2))
    moved = Net(clock2, lambda kind, req, n: httpx.Response(301, headers={"location": "https://example.invalid/"})
                if kind == "comments" else None)
    w2, _ = make(clock2, net=moved)
    assert w2.streams[R].run_pass(stop_at=clock2() + timedelta(hours=1)) == "paused"
    assert len(moved.log) == 1


# --- lock and spacing -----------------------------------------------------------------------------------------------

def test_poll_runs_under_reddit_pass_lock_never_beside_search():
    clock = Clock()
    w, net = make(clock)
    with apr.PASS_LOCKS[R]:
        assert w.streams[R].run_pass() == "locked"
    assert net.log == []
    drive(w, clock, T0 + timedelta(hours=3))
    assert net.stream() and all(r.reddit_locked for r in net.log)
    assert len(w.streams) == 2 and set(apr.PASS_LOCKS) == {apr.X_SOURCE, R}


def test_x_stream_not_blocked_by_reddit_poll():
    clock = Clock()
    w, net = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=30))
    assert net.stream() and not any(r.x_locked for r in net.stream())
    assert apr.PASS_LOCKS[apr.X_SOURCE] is not apr.PASS_LOCKS[R]
    with apr.PASS_LOCKS[R]:
        assert apr.PASS_LOCKS[apr.X_SOURCE].acquire(blocking=False)
        apr.PASS_LOCKS[apr.X_SOURCE].release()


# --- canary across search slices (Q7) -------------------------------------------------------------------------------

def test_canary_failure_not_repeated_across_search_slices_same_day():
    # BASELINE spreads 30 coins over the day (one search per 48 min), so the 2-hourly polls slice the search pass
    clock = Clock(datetime(2026, 10, 27, 0, 0, 30, tzinfo=timezone.utc))
    short = ok(atom([(f"t3_c{i}", T0 - timedelta(minutes=i)) for i in range(3)]))
    net = Net(clock, lambda kind, req, n: short if kind == "canary" else None)
    w, _ = baseline(clock, net=net, coins=sorted(wq.load().coins)[:30])
    outcomes = drive(w, clock, MIDNIGHT)
    assert outcomes.count("stream_due") >= 3 and len(net.of("search")) >= 2
    assert len(net.of("canary")) == 1  # one failed canary per UTC day, never one per search slice


# --- own store, method order (AC14, AC26) ---------------------------------------------------------------------------

def test_stream_values_stored_under_reddit_stream_never_reddit_web():
    clock = Clock()
    all_days_seeded()
    before = {sym: store.read_points(R, sym) for sym in COINS}
    w, net = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    assert any(YESTERDAY in dict(store.read_points(S, sym)) for sym in COINS)
    assert {sym: store.read_points(R, sym) for sym in COINS} == before
    rows = web_evidence.read_rows(S, "SOL")
    assert rows and all(r.method == rs.METHOD for r in rows.values())


def test_reddit_impl_order_equals_discovery_source_impl_reddit():
    doc = json.loads(apr.DISCOVERY_PATH.read_text(encoding="utf-8"))
    order = doc["source_impl"]["reddit"]
    assert tuple(order) == wq.load().config.reddit_impl_order == ("reddit_web", "reddit_stream")


def test_stream_store_used_when_reddit_web_has_no_usable_points(tmp_path, monkeypatch):
    from api.analytics.attention import discovery as disc
    from api.tests.analytics.attention.test_discovery import cat, put_change, world

    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]},
          source_impl={"reddit": ["reddit_web", "reddit_stream"]})
    put_change("reddit_stream", "A", 1.1, 1.0)
    res = disc.build_discovery(30, today=__import__("api.tests.analytics.attention.conftest",
                                                    fromlist=["TODAY"]).TODAY)
    coin = next(r for r in cat(res, "ai").coins if r.symbol == "A")
    reddit = {s.source: s for s in coin.sources}["reddit"]
    assert reddit.change == pytest.approx(10.0)


# --- commit of settled days, frozen (AC4, AC30) ---------------------------------------------------------------------

def test_open_day_committed_when_settled_and_not_before():
    clock = Clock()
    all_days_seeded()
    w, _ = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    doc = rs.read_completeness(YESTERDAY)
    assert doc is not None and doc["settled"] is True
    assert rs.read_completeness(T0.date()) is None  # today is not complete: never committed before it is


def test_open_days_reevaluated_each_round_until_settled(monkeypatch):
    clock = Clock()
    all_days_seeded()
    calls = []
    monkeypatch.setattr(rs, "open_days", lambda now: [YESTERDAY])
    monkeypatch.setattr(rs, "commit_day", lambda day, q, led, *, now: calls.append((day, now)))
    w, _ = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    clock.t = T0 + timedelta(hours=3)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=4))
    assert [d for d, _ in calls] == [YESTERDAY, YESTERDAY]


def test_second_commit_of_settled_day_changes_nothing():
    clock = Clock()
    all_days_seeded()
    w, _ = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    snap = rs.completeness_path(YESTERDAY).read_bytes()
    points = {sym: store.read_points(S, sym) for sym in COINS}
    clock.t = T0 + timedelta(hours=3)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=4))
    assert rs.completeness_path(YESTERDAY).read_bytes() == snap
    assert {sym: store.read_points(S, sym) for sym in COINS} == points


def test_unsettled_or_below_coverage_day_writes_no_zero():
    clock = Clock()
    all_days_seeded()
    net = Net(clock, lambda kind, req, n: ok(atom([])) if kind == "comments" else None)
    w, _ = make(clock, net=net)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    doc = rs.read_completeness(YESTERDAY)
    assert doc is not None and doc["settled"] is False and doc["fetched"] == 0
    assert all(c["value"] is None for c in doc["coins"].values())
    assert all(store.read_points(S, sym) == [] for sym in COINS)


def test_commit_exception_logged_by_class_only_pass_continues(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    clock = Clock()
    monkeypatch.setattr(rs, "open_days", lambda now: [YESTERDAY])

    def bad(*a, **k):
        raise ValueError("PLANTED-secret-text")

    monkeypatch.setattr(rs, "commit_day", bad)
    w, net = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    msgs = [r.getMessage() for r in caplog.records]
    assert "attention pc reddit_stream commit skipped: ValueError" in msgs
    assert not [m for m in msgs if "PLANTED" in m]
    assert net.of("search")


# --- per-day completeness (AC38) ------------------------------------------------------------------------------------

def _committed():
    clock = Clock()
    all_days_seeded()
    w, _ = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    return rs.read_completeness(YESTERDAY)


def test_stream_completeness_file_written_for_complete_day():
    doc = _committed()
    assert rs.completeness_path(YESTERDAY).exists()
    for key in ("coverage", "polls", "settled", "partial", "gap_unreachable", "canary_ok", "fetched", "missing"):
        assert key in doc
    assert doc["canary_ok"] is False


def test_stream_day_record_has_attempted_fetched_and_missing_reason_counts():
    doc = _committed()
    assert isinstance(doc["attempted"], int) and isinstance(doc["fetched"], int)
    assert isinstance(doc["missing"], dict) and all(isinstance(v, int) for v in doc["missing"].values())


def test_stream_day_record_attempted_equals_fetched_plus_missing():
    doc = _committed()
    assert doc["attempted"] == doc["fetched"] + sum(v for k, v in doc["missing"].items() if k != "ambiguous")


def test_stream_day_record_missing_reason_counts_sum_to_missing():
    doc = _committed()
    assert sum(doc["missing"].values()) == sum(c["reason"] != "fetched" for c in doc["coins"].values())


def test_stream_day_without_completeness_file_reports_none_never_zero():
    clock = Clock()
    st = rs.stream_status(clock(), queries(), days=3)
    for day in st["days"].values():
        assert day["coverage_comments"] is None and day["coverage_new"] is None
        assert day["fetched"] is None and day["missing"] is None


# --- Sources route unchanged (Q3, AC39) -----------------------------------------------------------------------------

def test_sources_route_unchanged_with_stream_enabled(tmp_path, monkeypatch):
    import shutil

    from api.analytics.attention import sources
    from api.tests.analytics.attention.test_discovery import world

    clock = Clock()
    q = queries()
    w, net = make(clock, q=q)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    assert stream_dir().exists() and net.stream()
    world(tmp_path, monkeypatch, {s: 5e7 for s in COINS}, cats={"ai": COINS}, source_impl={"reddit": R})
    monkeypatch.setattr(sources, "_collector", lambda: q.config)

    def rows():
        out = [r.model_dump() for r in sources.build_sources(clock().date(), now=clock()).sources]
        for r in out:  # the host's free disk space moves between two reads; nothing else may
            if r.get("health"):
                r["health"].pop("free_disk_bytes", None)
        return out

    with_stream = rows()
    shutil.rmtree(stream_dir())
    assert rows() == with_stream
    assert "reddit_stream" not in {r["id"] for r in with_stream}


def test_sources_pc_stores_still_excludes_reddit_stream():
    from api.analytics.attention import sources

    assert "reddit_stream" not in sources.PC_STORES
    assert sources.PC_STORES == frozenset({"xsearch_web", "reddit_web"})


# --- ledger (AC29) --------------------------------------------------------------------------------------------------

def test_ledger_unavailable_holds_stream_searches_continue(caplog):
    caplog.set_level(logging.INFO)
    clock = Clock()
    w, net = make(clock, led=False)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    assert net.of("search") and net.stream() == []
    assert any("ledger_unavailable" in r.getMessage() for r in caplog.records)
    assert not stream_dir().exists()


def test_polled_entries_reach_the_ledger_once_per_id():
    clock = Clock()
    all_days_seeded()
    w, net = make(clock)
    drive(w, clock, T0 + timedelta(hours=5))
    led = ledger()
    for day in (YESTERDAY, T0.date()):
        rows = led.read_day(day)
        seen = rs.read_seen(day)
        assert seen and seen <= set(rows)
        ids = [r["id"] for r in json.loads(reddit_items.ledger_path(day).read_text(encoding="utf-8"))["rows"]]
        assert len(ids) == len(set(ids))


# --- unattended weeks, restart (AC40) -------------------------------------------------------------------------------

def test_stream_day_files_pruned_by_ledger_retention_days():
    clock = Clock()
    old, kept = T0.date() - timedelta(days=11), T0.date() - timedelta(days=3)
    for d in (old, kept):
        for path in (rs.seen_path(d), rs.completeness_path(d), apr.stream_budget_path(d)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"ids": [], "settled": True, "requests": 0}), encoding="utf-8")
    w, _ = make(clock, ledger_retention_days=10)
    w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=30))
    for f in (rs.seen_path, rs.completeness_path, apr.stream_budget_path):
        assert not f(old).exists() and f(kept).exists()


def test_restart_resumes_polls_without_burst():
    clock = Clock()
    w, net = make(clock)
    drive(w, clock, T0 + timedelta(hours=3))
    n = len(net.log)
    clock.t += timedelta(minutes=1)
    w2, _ = make(clock, net=net)
    drive(w2, clock, T0 + timedelta(hours=6))
    assert min(gaps(net.log)) >= 60
    comments = polls_of("comments", T0.date())
    steps = [(b.collected_at - a.collected_at).total_seconds() for a, b in zip(comments, comments[1:])]
    assert all(s >= 7200 for s in steps) and len(net.log) > n


def test_behind_restart_schedules_next_poll_at_spacing_not_immediately_for_all_due_kinds():
    clock = Clock()
    all_days_seeded()
    w, net = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=30))
    last = shared(clock).last_unit_at()
    clock.t = T0 + timedelta(hours=7)  # both kinds overdue
    src = shared(clock)
    src.stamp_attempt()  # a search ended just now
    last = src.last_unit_at()
    w2, _ = make(clock, net=net)
    due = w2.streams[R].schedule()
    assert due >= last + timedelta(seconds=60)
    n = len(net.log)
    drive(w2, clock, clock() + timedelta(hours=1))
    fresh = net.log[n:]
    assert len(fresh) >= 2 and fresh[0].t >= last + timedelta(seconds=60)
    assert all(60 <= g <= 120 for g in gaps(fresh[:2]))


def test_restart_with_overdue_kinds_sends_one_poll_per_spacing_not_a_burst():
    clock = Clock()
    all_days_seeded()
    w, net = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=30))
    clock.t = T0 + timedelta(hours=8)
    n = len(net.log)
    w2, _ = make(clock, net=net)
    drive(w2, clock, clock() + timedelta(minutes=30))
    fresh = net.stream()[len([r for r in net.log[:n] if r.kind in STREAM_KINDS]):]
    assert {r.kind for r in fresh} == {"comments", "new"}
    assert min(gaps(fresh)) >= 60


def test_ninety_day_ticks_state_bounded_with_stream_on():
    clock = Clock()
    all_days_seeded()
    net = Net(clock, depth=300)
    w, _ = make(clock, net=net, ledger_retention_days=10)
    for day in range(90):
        clock.t = T0 + timedelta(days=day)
        w.streams[R].run_pass(stop_at=clock() + timedelta(minutes=10))
    meta = stream_dir() / "_meta"
    for sub in ("_seen", "_completeness", "_budget"):
        assert len(list((meta / sub).glob("*.json"))) <= 12, sub
    assert len(list((meta / "_polls").glob("*.json"))) <= 31


def test_host_stop_leaves_poll_kind_due_for_next_window():
    clock = Clock()
    w, net = make(clock)
    assert w.streams[R].run_pass(stop_at=T0) == "host_stopped"  # the host stops before the first poll is due
    assert net.stream() == []
    assert rs.due_kinds(queries(), clock()) == ["comments", "new"]


def test_pass_that_cannot_finish_in_its_window_continues_next_window_no_poll_dropped():
    clock = Clock()
    all_days_seeded()
    w, net = make(clock)
    out = w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=2))
    assert out == "host_stopped"
    kinds = {r.kind for r in net.stream()}
    assert kinds != {"comments", "new"}
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=1))
    assert {r.kind for r in net.stream()} == {"comments", "new"}


def test_host_stop_mid_round_keeps_every_due_poll_for_next_window():
    clock = Clock()
    all_days_seeded()
    w, net = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=2))
    assert "new" in rs.due_kinds(queries(), clock())
    clock.t = T0 + timedelta(hours=1)
    w.streams[R].run_pass(stop_at=T0 + timedelta(hours=2))
    assert polls_of("new", T0.date())


def test_search_queue_leftover_resumes_next_window_in_order_no_coin_skipped():
    clock = Clock()
    w, net = make(clock)
    w.streams[R].run_pass(stop_at=T0 + timedelta(minutes=10))
    first = len(net.of("search"))
    assert 0 < first
    clock.t = T0 + timedelta(hours=1)
    drive(w, clock, T0 + timedelta(hours=6))
    doc = rw.read_completeness(YESTERDAY)
    assert set(doc["coins"]) == set(COINS) and all(c["attempted"] for c in doc["coins"].values())
    assert w.streams[R].queue() == [] or all(d < YESTERDAY for _s, d in w.streams[R].queue())


def test_slow_day_never_trades_completeness_for_speed():
    clock = Clock()
    q = queries()
    w, net = make(clock, q=q)
    drive(w, clock, MIDNIGHT)
    for p in rs.read_polls(T0.date(), T0.date()):
        assert p.pages <= q.config.reddit_stream_max_pages_per_poll
    doc = rw.read_completeness(YESTERDAY)
    assert set(doc["coins"]) == set(COINS)


# --- privacy --------------------------------------------------------------------------------------------------------

def test_logs_hold_no_url_subreddit_id_or_author_with_stream_on(caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    clock = Clock()
    net = Net(clock, lambda kind, req, n: httpx.Response(500) if kind == "new" else None)
    monkeypatch.setattr(rs, "commit_day", lambda *a, **k: (_ for _ in ()).throw(KeyError("t1_secret")))
    w, _ = make(clock, net=net)
    drive(w, clock, T0 + timedelta(hours=3))
    text = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("api."))
    for bad in ("reddit.com", "CryptoCurrency", "t1_", "t3_", "/u/", "after="):
        assert bad not in text, bad
