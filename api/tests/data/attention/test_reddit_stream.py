"""W8c2 AC14, AC26, AC28-AC30, AC37, AC38 (SPEC A.2 M2, A.2b): Reddit stream-and-count, method `reddit_stream`.

Fake HTTP clients only (httpx.MockTransport); no live Reddit request. Clocks are injected. The stream polls one
combined `new/.rss` (posts) and one combined `comments/.rss` (comments) feed over the configured subreddit set.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from api.data.attention import pc_pace, reddit_items, store, web_evidence
from api.data.attention import reddit_stream as rs
from api.data.attention import reddit_web as rw
from api.data.attention import web_queries as wq
from api.tests.tooling_guards.test_pc_collector_guards import fixed_hour_offenders

D = date(2026, 10, 26)
SALT = b"0123456789abcdef0123456789abcdef"
PLANTED_USER = "PlantedUserName77"
TITLE = "SOL ETH news"  # mentions SOL and ETH (bare tickers; neither is name_only)


def at(h: float, day: date = D) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=h)


class Clock:
    def __init__(self, t: datetime):
        self.t = t

    def __call__(self) -> datetime:
        return self.t

    def sleep(self, s: float) -> None:
        assert s >= 0
        self.t += timedelta(seconds=s)


def entry(rid: str, when: datetime, *, author: str | None = None, title: str = TITLE) -> str:
    author = author or f"u{rid}"
    return (f'<entry><author><name>/u/{author}</name></author><category term="CryptoCurrency" label="r/CryptoCurrency"/>'
            f'<content type="html">&lt;p&gt;body&lt;/p&gt;</content><id>{rid}</id>'
            f'<updated>{when.isoformat()}</updated><published>{when.isoformat()}</published>'
            f'<title>{title}</title></entry>')


def atom(entries: list[str]) -> bytes:
    return ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>t</title>'
            + "".join(entries) + "</feed>").encode()


def rid(kind: str, when: datetime) -> str:
    return f"{kind}_{int(when.timestamp()) // 60:x}"


def stream_times(t: datetime, *, span_h: float = 15.0, n: int = 100, count: int | None = None) -> list[datetime]:
    """Entries on a fixed grid of span_h / n hours, newest first, the newest just before t: by default 100 entries
    over 15 hours. `count` asks for more entries on the same grid."""
    step = timedelta(hours=span_h) / n
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    k = int((t - first) / step)
    return [first + step * (k - i) for i in range(count or n)]


def stream_feed(t: datetime, kind: str = "t1", **kw) -> bytes:
    return atom([entry(rid(kind, w), w) for w in stream_times(t, **kw)])


def ok(body: bytes):
    return lambda req: httpx.Response(200, content=body, headers={"content-type": "application/atom+xml"})


class Fake:
    def __init__(self, respond):
        self.respond, self.requests = respond, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def live_stream(clock: Clock, *, comments_span_h: float = 15.0, posts_span_h: float = 72.0):
    """A responder whose feeds follow the injected clock: the newest 100 entries before `now`, or before `after`."""
    def respond(req: httpx.Request) -> httpx.Response:
        now = clock()
        after = parse_qs(urlsplit(str(req.url)).query).get("after")
        kind, span = ("t1", comments_span_h) if "/comments/" in req.url.path else ("t3", posts_span_h)
        times = stream_times(now, span_h=span)
        if after:
            deep = stream_times(now, span_h=span, count=10_000)
            last = next(w for w in deep if rid(kind, w) == after[0])
            times = [w for w in deep if w < last][:100]
        return httpx.Response(200, content=atom([entry(rid(kind, w), w) for w in times]),
                              headers={"content-type": "application/atom+xml"})
    return respond


@pytest.fixture
def q(attention_cache):
    return wq.load()


def with_cfg(q, **kw):
    return dataclasses.replace(q, config=dataclasses.replace(q.config, **kw))


def ledger() -> reddit_items.Ledger:
    return reddit_items.Ledger(reddit_items.AuthorHasher(SALT))


def src(q, clock, *, degraded: bool = False) -> pc_pace.PcSource:
    return rw.reddit_source(q.config, degraded=degraded, clock=clock)


def poll(q, clock, respond, *, kind="comments", led=None, s=None, degraded=False) -> tuple[rs.PollOutcome, Fake]:
    fake = Fake(respond)
    out = rs.run_poll(fake.client(), s or src(q, clock, degraded=degraded), q, kind=kind, ledger=led or ledger(),
                      sleep=clock.sleep, rng=random.Random(1))
    return out, fake


def P(kind: str, oldest: datetime, newest: datetime, collected: datetime | None = None, entries: int = 100) -> rs.Poll:
    return rs.Poll(kind, collected or newest + timedelta(minutes=1), newest, oldest, entries, 1)


def record(*polls: rs.Poll) -> None:
    for p in polls:
        rs.append_poll(p)


def full_posts() -> list[rs.Poll]:
    """Posts polls that cover D fully and settle it."""
    return [P("new", at(-30), at(24.5)), P("new", at(30), at(40))]


# --- polling, ledger, dedupe ---

def test_poll_parses_feeds_and_stores_collected_at_and_timestamps(q):
    q = with_cfg(q, reddit_comments_paging=False)
    clock = Clock(at(12))
    out, fake = poll(q, clock, ok(stream_feed(at(12))))
    assert out.reason is None and out.requests == 1 and out.entries == 100
    [p] = rs.read_polls(D, D)
    assert p.kind == "comments" and p.collected_at == at(12) and p.entries == 100 and p.pages == 1
    times = stream_times(at(12))
    assert p.newest == times[0] and p.oldest == times[-1]
    assert fake.requests[0].url.path.endswith("/comments/.rss")


def test_comments_feed_hundred_entries_over_fifteen_hours_fixture(q):
    clock = Clock(at(20))
    poll(q, clock, ok(stream_feed(at(20))))
    [p] = rs.read_polls(D, D)
    assert p.entries == 100 and 14.5 <= (p.newest - p.oldest).total_seconds() / 3600 <= 15.0


def test_dedupe_by_entry_id_across_overlapping_polls(q):
    clock, led = Clock(at(12)), ledger()
    first, _ = poll(q, clock, ok(stream_feed(at(12))), led=led)
    clock.t = at(14)
    second, _ = poll(q, clock, ok(stream_feed(at(14))), led=led)
    fresh = {rid("t1", w) for w in stream_times(at(14))} - {rid("t1", w) for w in stream_times(at(12))}
    assert first.new_ids == 100 and second.new_ids == len(fresh) > 0
    assert len(rs.read_seen(D)) + len(rs.read_seen(D - timedelta(days=1))) == first.new_ids + second.new_ids


def test_cross_feed_duplicate_entry_id_counted_once(q):
    clock, led = Clock(at(12)), ledger()
    same = atom([entry("t3_abc1", at(10)), entry("t3_abc2", at(9))])
    poll(q, clock, ok(same), kind="new", led=led)
    clock.t = at(12.1)
    out, _ = poll(q, clock, ok(same), kind="comments", led=led)
    assert out.new_ids == 0 and rs.read_seen(D) == {"t3_abc1", "t3_abc2"}


def test_comment_items_enter_ledger_with_t1_id_and_author_hash(q, caplog):
    caplog.set_level(logging.DEBUG)
    clock, led = Clock(at(12)), ledger()
    poll(q, clock, ok(atom([entry("t1_c0ffee", at(11), author=PLANTED_USER)])), led=led)
    row = led.read_day(D)["t1_c0ffee"]
    assert row.kind == "t1" and row.feed_kind == "comments" and row.author_hash is not None
    assert row.author_hash == reddit_items.AuthorHasher(SALT)(PLANTED_USER) and row.coins == ("ETH", "SOL")
    blob = "".join(p.read_text(encoding="utf-8") for p in Path(reddit_items.ledger_path(D)).parent.parent.rglob("*.json"))
    assert PLANTED_USER not in blob and PLANTED_USER.lower() not in blob and PLANTED_USER not in caplog.text


# --- coverage rule (AC26, AC30) ---

def test_coverage_fraction_from_entry_timestamps():
    polls = [P("comments", at(-2), at(6)), P("comments", at(5), at(12))]
    assert rs.coverage(D, polls, "comments") == pytest.approx(12 / 24)
    assert rs.coverage(D, polls, "new") == 0.0


def test_gap_uncovered_when_oldest_of_next_poll_newer_than_previous_newest():
    polls = [P("comments", at(-1), at(8)), P("comments", at(10), at(25))]
    assert rs.coverage(D, polls, "comments") == pytest.approx(22 / 24)  # 08:00-10:00 uncovered
    touching = [P("comments", at(-1), at(8)), P("comments", at(8), at(25))]
    assert rs.coverage(D, touching, "comments") == 1.0


def _commit_with_comments(q, oldest_h: float, newest_h: float, *, led=None):
    """Seen SOL entries in D, full posts coverage, one settled comments poll set covering [oldest, newest] of D."""
    led = led or ledger()
    clock = Clock(at(12))
    poll(q, clock, ok(atom([entry(f"t3_a{i}", at(1 + i)) for i in range(4)])), kind="new", led=led)
    record(*full_posts(), P("comments", at(oldest_h), at(newest_h)), P("comments", at(30), at(40)))
    return rs.commit_day(D, q, led, now=at(48))


def test_day_stored_at_coverage_0_80_flagged_partial(q):
    doc = _commit_with_comments(q, 24 - 0.8 * 24, 24)
    assert doc["coverage"]["comments"] == pytest.approx(0.8) and doc["partial"] is True
    assert doc["coins"]["SOL"]["reason"] == "fetched" and dict(store.read_points(rs.SOURCE, "SOL"))[D] == 4.0


def test_day_below_coverage_missing_not_zero(q):
    doc = _commit_with_comments(q, 24 - 0.79 * 24, 24)
    assert doc["coins"]["SOL"]["reason"] == "below_coverage" and doc["coins"]["SOL"]["value"] is None
    assert store.read_points(rs.SOURCE, "SOL") == [] and doc["missing"]["below_coverage"] >= 1


def test_full_coverage_not_flagged_partial(q):
    doc = _commit_with_comments(q, -3, 24.5)
    assert doc["coverage"] == {"comments": 1.0, "new": 1.0} and doc["partial"] is False


def test_posts_plus_comments_day_needs_both_feed_kinds_covered(q):
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry("t3_b1", at(3))])), kind="new", led=led)
    record(P("comments", at(-3), at(24.5)), P("comments", at(30), at(40)), P("new", at(10), at(23)),
           P("new", at(30), at(40)))
    doc = rs.commit_day(D, q, led, now=at(48))
    assert doc["coverage"]["comments"] == 1.0 and doc["coverage"]["new"] < 0.8
    assert doc["coins"]["SOL"]["reason"] == "below_coverage" and store.read_points(rs.SOURCE, "SOL") == []


def test_baseline_two_hourly_comments_polls_give_full_coverage(q):
    clock, s, led = Clock(at(-2)), None, ledger()
    s = src(q, clock)
    while clock.t <= at(26):
        out, _ = poll(q, clock, ok(stream_feed(clock.t)), led=led, s=s)
        assert out.reason is None
        clock.t += timedelta(seconds=q.config.reddit_comments_poll_interval_s)
    polls = rs.read_polls(D - timedelta(days=1), D + timedelta(days=1))
    assert rs.coverage(D, polls, "comments") == 1.0
    assert len([p for p in polls if p.collected_at.date() == D]) == 12


def test_degraded_one_poll_per_day_below_0_80(q):
    clock = Clock(at(12))
    poll(q, clock, ok(stream_feed(at(12))), degraded=True)
    clock.t = at(36)
    poll(q, clock, ok(stream_feed(at(36))), degraded=True)
    cov = rs.coverage(D, rs.read_polls(D, D + timedelta(days=1)), "comments")
    assert cov < 0.8


def test_one_poll_per_day_comments_coverage_below_0_80_day_missing(q):
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry("t3_c1", at(3)), entry("t3_c2", at(4)), entry("t3_c3", at(5))])),
         kind="new", led=led)
    times = stream_times(at(12))
    record(*full_posts(), P("comments", times[-1], times[0]), P("comments", at(30), at(40)))
    doc = rs.commit_day(D, q, led, now=at(48))
    assert doc["coverage"]["comments"] < 0.8 and doc["coins"]["SOL"]["reason"] == "below_coverage"
    assert store.read_points(rs.SOURCE, "SOL") == [] and doc["coins"]["SOL"]["value"] is None


def test_two_polls_gap_under_feed_span_coverage_at_least_0_80(q):
    a, b = stream_times(at(8)), stream_times(at(20))  # 12 h gap under the 15 h feed span
    polls = [P("comments", a[-1], a[0]), P("comments", b[-1], b[0])]
    cov = rs.coverage(D, polls, "comments")
    assert 0.8 <= cov < 1.0


def test_newest_slice_bias_flag_in_evidence(q):
    doc = _commit_with_comments(q, -3, 24.5)
    assert doc["newest_slice_bias"] is True  # the polls were full (100 entries): older entries were cut off
    record(P("new", at(-30), at(23.9), entries=20), P("new", at(30), at(40), entries=20),
           P("comments", at(-3), at(24.5), entries=30), P("comments", at(30), at(40), entries=30))
    status = rs.day_status(D, [p for p in rs.read_polls(D - timedelta(days=1), D + timedelta(days=2))
                               if p.entries < rs.LIMIT], now=at(48), min_coverage=0.8)
    assert status.newest_slice_bias is False


def test_value_only_after_day_complete(q):
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry("t3_d1", at(3))])), kind="new", led=led)
    record(P("comments", at(-3), at(23.99)), P("new", at(-30), at(23.99)))
    doc = rs.commit_day(D, q, led, now=at(23.99))
    assert doc is None and store.read_points(rs.SOURCE, "SOL") == []
    assert rs.read_completeness(D) is None


def test_day_waits_until_settled(q):
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry("t3_e1", at(3))])), kind="new", led=led)
    record(P("comments", at(5), at(24.5)), P("new", at(-30), at(23.9)), P("new", at(30), at(40)))
    doc = rs.commit_day(D, q, led, now=at(30))
    assert doc["settled"] is False and doc["coins"]["SOL"]["reason"] == "not_settled"
    assert store.read_points(rs.SOURCE, "SOL") == [] and D in rs.open_days(at(30))


def test_mentions_counted_for_all_narrative_coins_from_same_entries(q):
    doc = _commit_with_comments(q, -3, 24.5)
    pts = {sym: dict(store.read_points(rs.SOURCE, sym)).get(D) for sym in ("SOL", "ETH")}
    assert pts == {"SOL": 4.0, "ETH": 4.0}
    assert doc["coins"]["ETH"]["reason"] == "fetched"


def test_ambiguity_list_skips_coin(q):
    amb = sorted(q.ambiguous["reddit_web"])[0]
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry(f"t3_f{i}", at(1 + i), title=f"{amb} {q.coins[amb]['name']} ${amb}")
                                    for i in range(4)])), kind="new", led=led)
    record(*full_posts(), P("comments", at(-3), at(24.5)), P("comments", at(30), at(40)))
    doc = rs.commit_day(D, q, led, now=at(48))
    assert doc["coins"][amb]["reason"] == "ambiguous" and store.read_points(rs.SOURCE, amb) == []


# --- method separation (AC14) ---

def test_stream_method_id_separate_store_from_reddit_web(q):
    _commit_with_comments(q, -3, 24.5)
    assert rs.SOURCE == "reddit_stream" != rw.SOURCE and rs.METHOD != rw.METHOD
    assert dict(store.read_points(rs.SOURCE, "SOL"))[D] == 4.0 and store.read_points(rw.SOURCE, "SOL") == []
    assert web_evidence.read_rows(rs.SOURCE, "SOL")[D].method == rs.METHOD
    assert web_evidence.read_rows(rw.SOURCE, "SOL") == {}


def test_methods_never_mixed_in_one_window_config_order(q):
    days = [D - timedelta(days=i) for i in range(5)]
    series = {"reddit_stream": [(d, 1.0) for d in days[:4]], "reddit_web": [(d, 9.0) for d in days]}
    method, pts = rs.pick_impl(q.config.reddit_impl_order, series, days[-1], D, min_points=3)
    assert method == "reddit_stream" and pts == sorted(series["reddit_stream"]) and all(v == 1.0 for _, v in pts)
    method, pts = rs.pick_impl(("reddit_web", "reddit_stream"), series, days[-1], D, min_points=3)
    assert method == "reddit_web" and all(v == 9.0 for _, v in pts)


def test_fallback_to_posts_only_series_when_comments_missing(q):
    days = [D - timedelta(days=i) for i in range(5)]
    series = {"reddit_stream": [(D, 1.0)], "reddit_web": [(d, 9.0) for d in days]}
    method, pts = rs.pick_impl(q.config.reddit_impl_order, series, days[-1], D, min_points=3)
    assert method == "reddit_web" and len(pts) == 5
    assert rs.pick_impl(q.config.reddit_impl_order, {"reddit_stream": [], "reddit_web": []}, days[-1], D,
                        min_points=1) == (None, [])


# --- pace, budget, pause (AC26, AC37) ---

def test_poll_interval_and_daily_poll_cap(q):
    q = with_cfg(q, reddit_comments_poll_interval_s=600, reddit_stream_polls_per_day_cap=2)
    clock = Clock(at(1))
    s = src(q, clock)
    assert poll(q, clock, ok(stream_feed(at(1))), s=s)[0].reason is None
    clock.t = at(1.1)
    out, fake = poll(q, clock, ok(stream_feed(at(1.1))), s=s)
    assert out.reason == "not_due" and fake.requests == []
    clock.t = at(1.2)
    assert poll(q, clock, ok(stream_feed(at(1.2))), s=s)[0].reason is None
    clock.t = at(5)
    out, fake = poll(q, clock, ok(stream_feed(at(5))), s=s)
    assert out.reason == "poll_cap" and fake.requests == []
    assert rs.due_kinds(with_cfg(q, reddit_stream_polls_per_day_cap=12), at(5)) == ["comments", "new"]


def test_baseline_intervals_comments_7200_posts_21600(q):
    assert q.config.reddit_comments_poll_interval_s == 7200 and q.config.reddit_posts_poll_interval_s == 21600
    record(P("comments", at(0), at(1), collected=at(1)), P("new", at(0), at(1), collected=at(1)))
    assert rs.due_kinds(q, at(2.9)) == []
    assert rs.due_kinds(q, at(3)) == ["comments"]
    assert rs.due_kinds(q, at(7)) == ["comments", "new"]


def test_stream_requests_share_daily_budget_150(q):
    clock = Clock(at(12))
    s = src(q, clock, degraded=True)
    assert s.effective_budget() == 150
    s.spend(149)
    assert poll(q, clock, ok(stream_feed(at(12))), s=s)[0].reason is None
    clock.t = at(13)
    out, fake = poll(q, clock, ok(stream_feed(at(13), kind="t3")), kind="new", s=s)
    assert out.reason == "budget_spent" and fake.requests == [] and s.used == 150


@pytest.mark.parametrize("respond,reason", [
    (lambda r: httpx.Response(403, content=b"blocked"), "reddit_blocked"),
    (lambda r: httpx.Response(429, content=b"slow"), "rate_limited"),
    (lambda r: httpx.Response(200, content=b"<html><body>blocked</body></html>",
                              headers={"content-type": "text/html"}), "reddit_blocked"),
])
def test_403_429_block_page_pauses_rest_of_day(q, respond, reason):
    clock = Clock(at(12))
    s = src(q, clock)
    out, fake = poll(q, clock, respond, s=s)
    assert out.reason == reason and len(fake.requests) == 1 and s.is_paused()
    clock.t = at(18)
    out, fake = poll(q, clock, ok(stream_feed(at(18), kind="t3")), kind="new", s=s)
    assert out.reason == "paused" and fake.requests == []
    clock.t = at(24.1)
    assert not s.is_paused()
    assert rs.read_polls(D, D) == []


def test_paging_off_makes_no_after_request(q):
    q = with_cfg(q, reddit_comments_paging=False)
    clock = Clock(at(20))
    record(P("comments", at(0), at(4), collected=at(4)))
    out, fake = poll(q, clock, live_stream(clock, comments_span_h=3))
    assert out.reason is None and len(fake.requests) == 1
    assert all("after" not in parse_qs(urlsplit(str(r.url)).query) for r in fake.requests)


def test_paging_on_requests_after_t1_id_within_daily_budget(q):
    assert q.config.reddit_comments_paging is True
    clock = Clock(at(20))
    record(P("comments", at(0), at(4), collected=at(4)))
    s = src(q, clock)
    s.spend(s.remaining() - 3)  # room for exactly three requests
    out, fake = poll(q, clock, live_stream(clock, comments_span_h=3), s=s)
    assert len(fake.requests) == 3 and s.remaining() == 0 and out.requests == 3
    first = parse_qs(urlsplit(str(fake.requests[0].url)).query)
    assert "after" not in first
    prev_last = None
    for r in fake.requests[1:]:
        after = parse_qs(urlsplit(str(r.url)).query)["after"][0]
        assert after.startswith("t1_") and after != prev_last
        prev_last = after
    [p] = [p for p in rs.read_polls(D, D) if p.collected_at > at(5)]
    assert p.pages == 3 and (p.newest - p.oldest) > timedelta(hours=8)


def test_paging_stops_when_gap_closed(q):
    clock = Clock(at(20))
    record(P("comments", at(0), at(15), collected=at(15)))
    out, fake = poll(q, clock, live_stream(clock, comments_span_h=3))
    assert len(fake.requests) == 2 and out.reason is None  # page 2 reaches back past 15:00
    gaps = [g for g in rs.read_polls(D, D) if g.collected_at == at(20)]
    assert gaps[0].oldest <= at(15)


def test_pages_respect_configured_spacing(q):
    clock = Clock(at(20))
    record(P("comments", at(0), at(4), collected=at(4)))
    sent = []

    def respond(req):
        sent.append(clock())
        return live_stream(clock, comments_span_h=3)(req)
    poll(q, clock, respond)
    gaps = [(b - a).total_seconds() for a, b in zip(sent, sent[1:], strict=False)]
    assert gaps and min(gaps) >= q.config.reddit_request_delay_min_s


# --- schedule, completeness (AC28, AC37, AC38) ---

def test_stream_continues_next_window_without_dropping_feeds(q):
    clock, led = Clock(at(10)), ledger()
    s = src(q, clock)
    fake = Fake(live_stream(clock))
    first = rs.run_due(fake.client(), s, q, ledger=led, clock=clock, sleep=clock.sleep, rng=random.Random(2),
                       stop_at=at(10) + timedelta(seconds=30))
    assert first.stop == "host_stopped" and [o.kind for o in first.outcomes] == ["comments"]
    assert rs.due_kinds(q, clock()) == ["new"]
    clock.t = at(11)  # comments were polled an hour ago (not due); posts are still due
    second = rs.run_due(fake.client(), s, q, ledger=led, clock=clock, sleep=clock.sleep, rng=random.Random(2))
    assert second.stop == "done" and [o.kind for o in second.outcomes] == ["new"]
    assert {p.kind for p in rs.read_polls(D, D)} == {"comments", "new"}


@pytest.mark.parametrize("start_h", [0.5, 9, 17, 23])
def test_pc_start_hours_vary_no_fixed_utc_window(q, start_h):
    clock, led = Clock(at(start_h)), ledger()
    fake = Fake(live_stream(clock))
    res = rs.run_due(fake.client(), src(q, clock, degraded=True), q, ledger=led, clock=clock, sleep=clock.sleep,
                     rng=random.Random(3))
    assert res.stop == "done" and sorted(o.kind for o in res.outcomes) == ["comments", "new"]
    assert all(o.reason is None for o in res.outcomes)
    assert all(p.collected_at >= at(start_h) for p in rs.read_polls(D, D + timedelta(days=1)))
    assert fixed_hour_offenders(Path(rs.__file__).read_text(encoding="utf-8")) == []


def test_stream_completeness_fields_written(q):
    _commit_with_comments(q, -3, 24.5)
    doc = json.loads(rs.completeness_path(D).read_text(encoding="utf-8"))
    for key in ("day", "method", "settled", "coverage", "min_coverage", "partial", "newest_slice_bias", "polls",
                "entries_seen", "collected_at", "attempted", "fetched", "missing", "coins"):
        assert key in doc, key
    assert doc["method"] == rs.METHOD and doc["fetched"] >= 2 and doc["entries_seen"] == 4
    assert doc["attempted"] == len([s for s in q.coins if s not in q.ambiguous["reddit_web"]])
    assert sum(doc["missing"].values()) + doc["fetched"] == len(q.coins)
    assert doc["polls"] == {"comments": 1, "new": 2}  # polls whose entries reach into D


def test_open_days_lists_unsettled_completed_days(q):
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry("t3_g1", at(3))])), kind="new", led=led)
    assert rs.open_days(at(20)) == []  # D is not complete yet
    assert rs.open_days(at(30)) == [D]
    record(*full_posts(), P("comments", at(-3), at(24.5)), P("comments", at(30), at(40)))
    rs.commit_day(D, q, led, now=at(48))
    assert rs.open_days(at(48)) == []


def test_stream_subreddit_set_is_top_level_list_in_one_combined_feed_url(q):
    """Owner delta 29-10-26 replaces the PLAN's 4-6 feed check: the stream set is the 12-name `subreddits` list."""
    subs = wq.stream_subreddits(q)
    assert subs == q.subreddits and len(subs) == 12
    for kind, tail in (("comments", "/comments/.rss"), ("new", "/new/.rss")):
        url = rs.feed_url(subs, kind)
        assert urlsplit(url).path == "/r/" + "+".join(subs) + tail
        assert parse_qs(urlsplit(url).query) == {"limit": ["100"]}
    assert parse_qs(urlsplit(rs.feed_url(subs, "comments", after="t1_abc")).query)["after"] == ["t1_abc"]
    with pytest.raises(ValueError):
        rs.feed_url(subs, "comments", after="t3_abc")
    with pytest.raises(ValueError):
        rs.feed_url(["bad name"], "new")


def test_stream_status_numbers_only(q):
    _commit_with_comments(q, -3, 24.5)
    st = rs.stream_status(at(48), days=3)
    day = st["days"][D.isoformat()]
    assert day["coverage_comments"] == 1.0 and day["coverage_new"] == 1.0 and day["partial"] is False
    assert day["fetched"] >= 2 and isinstance(day["missing"], int)
    assert set(st["today"]) == {"polls_comments", "polls_new", "entries_seen"}
