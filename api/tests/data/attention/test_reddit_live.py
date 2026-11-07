"""Finish plan RC-2 to RC-6, RC-9: the Reddit live core with a synthetic in-test `LiveMethod` that reads its pages
through the real surface grammar engine. Loopback-free and network-free: the "pages" are bytes built in the test."""
from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from api.data import cache
from api.data.attention import reddit_core as rc
from api.data.attention import reddit_items, reddit_metrics, registry, store, web_evidence
from api.data.attention import reddit_live as rl
from api.data.attention import reddit_surface as rs
from api.data.attention import web_queries as wq
from api.data.attention.types import SourceSeries

D = date(2026, 11, 5)
STORE = "reddit_live_gql"
SALT = b"0123456789abcdef0123456789abcdef"
PLANTED_USER = "PlantedUserName77"
PLANTED_TEXT = "secret-body-words"
CC = "CryptoCurrency"


def at(h: float, day: date = D) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=h)


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    return attention_cache


def lane(sub="solana", kind="posts", t=at(4), floor=at(0), newest=at(3), oldest=at(0.5), items=3, stop="exhausted",
         threads=(), poll_id=None) -> rl.LaneEvidence:
    return rl.LaneEvidence(sub, kind, poll_id or t.isoformat(), t, floor if kind == "posts" else None, newest, oldest,
                           items, 1, (), stop, tuple(threads))


# --- lane evidence, floor and anchor -------------------------------------------------------------------------------

def test_lane_validation():
    for bad in (dict(stop="timeout"), dict(kind="search"), dict(sub="a b"), dict(threads=(("t1_x", 1),))):
        with pytest.raises(ValueError):
            lane(**bad)
    with pytest.raises(ValueError):
        rl.LaneEvidence("solana", "posts", "p", at(1), None, None, None, 0, 0, (), "exhausted")
    assert lane().to_json() == rl.LaneEvidence.from_json(json.loads(json.dumps(lane().to_json()))).to_json()


FLOOR_TABLE = [  # (lanes, now) -> floor
    ([], at(10), at(0, D - timedelta(days=1))),  # no anchor: start of the newest completed day
    ([lane(t=at(4), newest=at(3))], at(10), at(3)),  # anchor's newest item
    ([lane(t=at(4), newest=at(3)), lane(t=at(8), newest=at(7), stop="cap")], at(10), at(3)),  # truncated: no anchor
    ([lane(t=at(4), newest=None, items=0, floor=at(1))], at(10), at(1)),  # quiet complete lane: its own floor
    ([lane(t=at(4, D - timedelta(days=3)), newest=at(3, D - timedelta(days=3)))], at(10),
     at(0, D - timedelta(days=1))),  # an old anchor never pulls the floor before the completed day
    ([lane(sub="Bitcoin", t=at(4), newest=at(3))], at(10), at(0, D - timedelta(days=1))),  # other subreddit
]


@pytest.mark.parametrize("lanes,now,want", FLOOR_TABLE)
def test_floor_and_anchor_table(lanes, now, want):
    assert rl.lane_floor(lanes, "solana", now) == want


def test_spans_and_truncation():
    assert lane(floor=at(1), oldest=at(1.5), t=at(4)).span() == (at(1), at(4))
    assert lane(stop="cap", oldest=at(2), t=at(4)).span() == (at(2), at(4))
    assert lane(stop="error", items=0, oldest=None, newest=None).span() is None
    assert lane(kind="comments").span() is None
    assert not lane(stop="cap").complete and lane().complete


HOLE_TABLE = [  # posts lanes for D -> (coverage, holes)
    ([lane(t=at(0), floor=at(0, D - timedelta(days=1))), lane(t=at(12), floor=at(0)), lane(t=at(24), floor=at(11))],
     1.0, []),
    ([lane(t=at(0), floor=at(0, D - timedelta(days=1))), lane(t=at(24), floor=at(11), stop="cap", oldest=at(14))],
     10 / 24, [(at(0), at(14))]),  # a truncated poll never bridges back to the previous coverage
    ([lane(t=at(6), floor=at(0)), lane(t=at(24), floor=at(10), oldest=at(10.5))], 20 / 24, [(at(6), at(10))]),
    ([], 0.0, [(at(0), at(24))]),
]


@pytest.mark.parametrize("lanes,cov,holes", HOLE_TABLE)
def test_hole_table(lanes, cov, holes):
    got_cov, got_holes = rl.posts_coverage(D, lanes, "solana")
    assert got_cov == pytest.approx(cov) and got_holes == holes


# --- threads: denominator, selection, close poll -------------------------------------------------------------------

def item(i: str, created: datetime, kind="post", coins=("SOL",), author=None, sub="solana") -> rc.LiveItem:
    return rc.LiveItem(i, kind, sub, created, author, coins)


def test_thread_denominator_new_posts_and_growth_in_d():
    lanes = [lane(t=at(-2), threads=(("t3_old", 1), ("t3_flat", 2))),
             lane(t=at(6), threads=(("t3_old", 4), ("t3_flat", 2))),
             lane(t=at(25), threads=(("t3_late", 0), ("t3_flat", 9)))]  # growth after D is not D's activity
    items = [item("t3_new", at(3)), item("t3_prev", at(-1)), item("t1_c", at(3), kind="comment")]
    assert rl.thread_denominator(D, lanes, items) == {"t3_new", "t3_old"}


def test_threads_to_open_never_opened_grown_then_close():
    lanes = [lane(t=at(1), threads=(("t3_a", 1), ("t3_b", 5), ("t3_c", 0))),
             lane(kind="comments", t=at(2), threads=(("t3_a", 1), ("t3_b", 2))),
             lane(kind="comments", t=at(2.5), stop="error", threads=(("t3_c", 0),))]
    assert rl.threads_to_open(lanes, 10) == ("t3_b", "t3_c")  # b grew by 3; c was never opened completely
    assert rl.threads_to_open(lanes, 10, close={"t3_z", "t3_b"}) == ("t3_b", "t3_c", "t3_z")
    assert rl.threads_to_open(lanes, 1, close={"t3_z"}) == ("t3_b",)


def test_comments_coverage_counts_only_reopens_at_or_after_the_close():
    lanes = [lane(kind="comments", t=at(10), threads=(("t3_a", 1), ("t3_b", 1))),
             lane(kind="comments", t=at(24), threads=(("t3_a", 2),)),
             lane(kind="comments", t=at(25), stop="cap", threads=(("t3_b", 2),))]
    assert rl.comments_coverage(D, lanes, {"t3_a", "t3_b"}) == 0.5
    assert rl.comments_coverage(D, lanes, set()) == 1.0


# --- counters and breaker ------------------------------------------------------------------------------------------

def test_breaker_opens_after_three_failures_until_midnight_and_persists():
    for k in range(2):
        rl.record_unit(STORE, at(1 + k), ok=False)
    assert not rl.breaker_open(STORE, at(3))
    rl.record_unit(STORE, at(3), ok=True)  # a success resets the run
    for k in range(3):
        rl.record_unit(STORE, at(4 + k), ok=False)
    assert rl.breaker_open(STORE, at(7)) and rl.breaker_open(STORE, at(23.9))
    raw = json.loads(rl.state_path(STORE).read_text())  # persisted: a restart reads the same file
    assert raw["breaker_until"] == at(24).isoformat() and raw["failures"] == 3
    assert not rl.breaker_open(STORE, at(24))
    assert rl.read_state(STORE, at(24))["failures"] == 0


def test_counters_persist_per_day_and_feed_the_context():
    rl.charge(STORE, at(1), requests=5, navigations=2)
    rl.charge(STORE, at(2), requests=3)
    s = rl.read_state(STORE, at(3))
    assert (s["requests"], s["navigations"]) == (8, 2)
    assert rl.build_context(STORE, ["solana"], at(3), threads_per_poll=5, request_cap=10).requests_left == 2
    assert rl.read_state(STORE, at(25))["requests"] == 0


# --- a synthetic method through the surface engine -----------------------------------------------------------------

SECTION = {
    "revision": 1, "hosts": ["gql.example.test"], "body_format": "json", "max_body_bytes": 2 * 1024 * 1024,
    "endpoints": [{
        "name": "listing", "lane": "posts",
        "match": {"method": "POST", "url": "/", "operation": {"pointer": "/operationName", "equals": "SubredditNew"}},
        "items": {"path": "/data/posts/[*]"},
        "fields": {"id": {"pointer": "/id"}, "kind": {"const": "post"}, "subreddit": {"pointer": "/sub"},
                   "created": {"pointer": "/created", "transform": "epoch_s"}, "author": {"pointer": "/author"},
                   "text": {"pointer": "/title"}, "text_complete": {"selftext_full": True},
                   "num_comments": {"pointer": "/num_comments"}},
        "continuation": {"next_cursor": "/data/after", "has_more": "/data/more",
                         "request_cursor": "body:/variables/after"},
    }, {
        "name": "thread", "lane": "comments",
        "match": {"method": "POST", "url": "/", "operation": {"pointer": "/operationName", "equals": "Thread"}},
        "items": {"path": "/data/comments/[*]"},
        "fields": {"id": {"pointer": "/id"}, "kind": {"const": "comment"}, "subreddit": {"pointer": "/sub"},
                   "created": {"pointer": "/created", "transform": "epoch_s"}, "author": {"pointer": "/author"},
                   "text": {"pointer": "/body"}, "text_complete": {"declared_length": "/len"},
                   "parent_id": {"pointer": "/post"}},
        "continuation": {"next_cursor": "/data/after", "has_more": "/data/more",
                         "request_cursor": "body:/variables/after"},
    }],
}
PAGE = 10


class World:
    """Posts every 10 min in r/CryptoCurrency (no coin) and three SOL posts and two SOL comments in r/solana on D."""

    def __init__(self, solana_posts=((3, "SOL to the moon"), (9, "SOL news"), (15, "solana SOL")), comments=True):
        self.posts = [(f"t3_c{i}", CC, at(-24 + i / 6), "ccuser", "market talk") for i in range(6 * 60)]
        self.posts += [(f"t3_s{k}", "solana", at(h), f"{PLANTED_USER}{k}", f"{text} {PLANTED_TEXT}")
                       for k, (h, text) in enumerate(solana_posts)]
        self.comments = ([("t1_m1", "t3_s1", at(10), PLANTED_USER, "SOL yes"),
                          ("t1_m2", "t3_s1", at(11), "other", "more SOL")] if comments and solana_posts else [])

    def num_comments(self, pid: str, now: datetime) -> int:
        return sum(1 for c in self.comments if c[1] == pid and c[2] <= now)


class Synthetic:
    """A `LiveMethod` whose `run_poll` reads synthetic response bytes through `reddit_surface` and the core."""

    method_id, label, store = "gql_anon", "synthetic", STORE

    def __init__(self, world: World, q: wq.Queries, *, fail_sub: str | None = None):
        self.world, self.q, self.fail_sub = world, q, fail_sub
        self.section = rs.load_section("gql_anon", SECTION)
        self.hasher = reddit_items.AuthorHasher(SALT)
        terms = reddit_metrics.coin_terms(q)
        self.match = lambda text: reddit_metrics.matched_coins(text, terms)

    def gate_state(self, now):
        return "ready"

    def next_poll_due(self, now):
        return rl.poll_due(STORE, now, self.q.config.reddit_live_polls_per_day)

    def close(self):
        pass

    def _request(self, op: str, after: str | None) -> tuple[rs.Endpoint, dict]:
        body = {"operationName": op, "variables": {"after": None}}
        ep = rs.match_request(self.section, "POST", "https://gql.example.test/", json.dumps(body).encode())
        if after is not None:
            _, body = rs.place_cursor(ep, "https://gql.example.test/", body, after)
        return ep, body

    def _listing(self, sub: str, now: datetime, after: str | None) -> bytes:
        rows = sorted((p for p in self.world.posts if p[1] == sub and p[2] <= now), key=lambda p: p[2], reverse=True)
        start = 0 if after is None else next(i for i, p in enumerate(rows) if p[0] == after) + 1
        chunk = rows[start:start + PAGE]
        return json.dumps({"data": {"more": start + PAGE < len(rows), "after": chunk[-1][0] if chunk else None,
                                    "posts": [{"id": i, "sub": s, "created": c.timestamp(), "author": a, "title": t,
                                               "num_comments": self.world.num_comments(i, now)}
                                              for i, s, c, a, t in chunk]}}).encode()

    def _thread(self, pid: str, now: datetime) -> bytes:
        rows = [c for c in self.world.comments if c[1] == pid and c[2] <= now]
        return json.dumps({"data": {"more": False, "after": None, "comments": [
            {"id": i, "sub": "solana", "post": p, "created": c.timestamp(), "author": a, "body": b, "len": len(b)}
            for i, p, c, a, b in rows]}}).encode()

    def run_poll(self, ctx: rl.PollContext) -> rl.PollResult:
        pid, now, lanes, items, requests = ctx.now.isoformat(), ctx.now, [], [], 0
        for sub in ctx.subreddits:
            floor, after, seen, chain, pages, stop = ctx.floors[sub], None, [], [], 0, "exhausted"
            while True:
                ep, body = self._request("SubredditNew", after)
                raw = self._listing(sub, now, body["variables"]["after"])
                requests += 1
                try:
                    page = rs.extract_page(self.section, ep, status=200, content_type="application/json",
                                           body=b"" if sub == self.fail_sub else raw)
                except rs.SurfaceError as exc:
                    stop = exc.reason
                    break
                pages += 1
                seen += page.items
                if page.items:
                    chain.append((page.next_cursor or page.items[-1].id, page.items[-1].created))
                if not page.has_more or (page.items and page.items[-1].created <= floor):
                    break
                after = page.next_cursor
            listed = [r for r in seen if r.created > floor] + [r for r in seen if r.created <= floor][:1]
            items += [rc.reduce_item(r, self.hasher, self.match) for r in listed]
            lanes.append(rl.LaneEvidence(sub, "posts", pid, now, floor, max((r.created for r in listed), default=None),
                                         min((r.created for r in listed), default=None),
                                         sum(r.created > floor for r in listed), pages, tuple(chain), stop,
                                         tuple((r.id, r.num_comments or 0) for r in listed)))
        by_sub: dict[str, list] = {}
        for t in ctx.threads:
            sub = next(p[1] for p in self.world.posts if p[0] == t)
            ep, _ = self._request("Thread", None)
            page = rs.extract_page(self.section, ep, status=200, content_type="application/json",
                                   body=self._thread(t, now))
            requests += 1
            items += [rc.reduce_item(r, self.hasher, self.match) for r in page.items]
            by_sub.setdefault(sub, []).append((t, self.world.num_comments(t, now)))
        for sub, opened in by_sub.items():
            lanes.append(rl.LaneEvidence(sub, "comments", pid, now, None, None, None, 0, len(opened), (), "exhausted",
                                         tuple(opened)))
        return rl.PollResult(pid, now, tuple(lanes), tuple(items), requests)


@pytest.fixture
def q(attention_cache):
    base = wq.load()
    cfg = dataclasses.replace(base.config, reddit_live_threads_per_poll=100)
    return dataclasses.replace(base, config=cfg)


def run_polls(method: Synthetic, hours, subs=("solana",)) -> None:
    for h in hours:
        now = at(h)
        ctx = rl.build_context(STORE, subs, now, threads_per_poll=method.q.config.reddit_live_threads_per_poll,
                               request_cap=10_000)
        assert isinstance(method, rl.LiveMethod) and method.gate_state(now) == "ready"
        rl.record_poll(STORE, method.run_poll(ctx))


POLL_HOURS = (0, 4, 8, 12, 16, 20, 24, 26, 28)


def test_synthetic_surface_yields_values_discovery_reads(q):
    m = Synthetic(World(), q)
    run_polls(m, POLL_HOURS)
    doc = rl.commit_day(STORE, D, q, now=at(29), subreddits=("solana",))
    assert doc["settled"] and doc["posts_coverage"] == {CC: 1.0, "solana": 1.0} and doc["holes"] == {}
    assert doc["comments_coverage"] == 1.0 and doc["comments_scope"] == "threads_opened" and doc["canary_ok"]
    assert doc["method"] == "reddit_live_gql_v1"
    assert doc["coins"]["SOL"] == {"reason": "fetched", "value": 5.0}  # three posts and two comments in D
    assert rl.read_completeness(STORE, D) == doc
    series = registry.read_series(STORE, "SOL", today=D + timedelta(days=1), known_at_time=True)
    assert series.points == [(D, 5.0)]
    assert web_evidence.read_rows(STORE, "SOL")[D].method == "reddit_live_gql_v1"


def test_day_not_complete_and_missing_close_poll(q):
    m = Synthetic(World(), q)
    run_polls(m, (0, 4, 8, 12, 16, 20))
    assert rl.commit_day(STORE, D, q, now=at(23), subreddits=("solana",)) is None
    doc = rl.commit_day(STORE, D, q, now=at(25), subreddits=("solana",))  # no poll after D's end yet
    assert not doc["settled"] and doc["coins"]["SOL"]["reason"] == "lane_incomplete"
    assert doc["holes"]["solana"]["hours"] == pytest.approx(4.0)
    assert store.read_points(STORE, "SOL") == []


def test_truncated_lane_leaves_the_day_incomplete(q):
    m = Synthetic(World(), q)
    run_polls(m, (0, 4, 8, 12))
    m.fail_sub = "solana"
    run_polls(m, (16, 20, 24, 26, 28))
    doc = rl.commit_day(STORE, D, q, now=at(29), subreddits=("solana",))
    assert doc["coins"]["SOL"]["reason"] == "lane_incomplete" and doc["posts_coverage"]["solana"] < 1
    lanes = rl.read_lanes(STORE, D, D + timedelta(days=1))
    assert {x.stop_reason for x in lanes if x.subreddit == "solana" and x.kind == "posts"
            and x.collected_at >= at(16)} == {"empty_shell"}


def test_low_thread_coverage_blocks_the_day(q):
    m = Synthetic(World(), q)
    run_polls(m, (0, 4, 8, 12, 16, 20, 24))  # the close poll ran but has not re-opened every D thread
    doc = rl.commit_day(STORE, D, q, now=at(24.5), subreddits=("solana",))
    assert doc["comments_coverage"] < q.config.reddit_live_min_thread_coverage
    assert doc["coins"]["SOL"]["reason"] == "lane_incomplete"


def _history(symbol: str, days: int, source="reddit_stream") -> None:
    pts = [(D - timedelta(days=k), 2.0) for k in range(1, days + 1)]
    store.write_series(SourceSeries(source, symbol, pts, "ok", ""), today=D)


ZERO_TABLE = [  # (positive history days, canary items) -> stored zero?
    (7, True, True),
    (6, True, False),
    (7, False, False),
    (0, True, False),
]


@pytest.mark.parametrize("history,canary,stored", ZERO_TABLE)
def test_zero_table(q, history, canary, stored):
    world = World(solana_posts=((3, "nothing here"),), comments=False)
    if not canary:  # a thin canary: the closing poll's CryptoCurrency lane returns fewer than 15 new items
        world.posts = [p for p in world.posts if p[1] != CC or p[2] < at(21)]
    _history("SOL", history)
    run_polls(Synthetic(world, q), POLL_HOURS)
    doc = rl.commit_day(STORE, D, q, now=at(29), subreddits=("solana",))
    assert doc["settled"] and doc["canary_ok"] is canary
    if stored:
        assert doc["coins"]["SOL"] == {"reason": "fetched", "value": 0.0}
        assert store.read_points(STORE, "SOL") == [(D, 0.0)]
    else:
        assert doc["coins"]["SOL"]["reason"] == "zero_unverified" and doc["coins"]["SOL"]["value"] is None
        assert store.read_points(STORE, "SOL") == []


def test_positive_history_counts_any_reddit_method_within_28_days():
    _history("SOL", 4, "reddit_web")
    pts = [(D - timedelta(days=k), 1.0) for k in (2, 3, 5, 30)]
    store.write_series(SourceSeries("reddit_live_browser", "SOL", pts, "ok", ""), today=D)
    store.write_series(SourceSeries("reddit_stream", "SOL", [(D - timedelta(days=6), 0.0)], "ok", ""), today=D)
    assert rl.positive_history_days("SOL", D) == 5  # days 1-4 and 5; day 30 is outside, a zero is not positive


def test_failed_polls_open_the_breaker(q):
    m = Synthetic(World(), q, fail_sub="solana")
    run_polls(m, (1, 2, 3))
    assert rl.breaker_open(STORE, at(3.5))
    assert rl.read_state(STORE, at(3.5))["requests"] > 0


def test_no_text_or_username_persisted(q):
    run_polls(Synthetic(World(), q), POLL_HOURS)
    rl.commit_day(STORE, D, q, now=at(29), subreddits=("solana",))
    files = [p for p in cache.CACHE_ROOT.rglob("*") if p.is_file()]
    assert files
    for p in files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        for planted in (PLANTED_USER, PLANTED_USER.lower(), PLANTED_TEXT, "to the moon", "market talk"):
            assert planted not in text, p.name
