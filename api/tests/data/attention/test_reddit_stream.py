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
from api.data.attention.types import SourceSeries
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


def live_stream(clock: Clock, *, comments_span_h: float = 15.0, posts_span_h: float = 72.0, depth: int = 10_000):
    """A responder whose feeds follow the injected clock: the newest 100 entries before `now`, or before `after`.
    The feed holds its newest `depth` entries only (Reddit's listing depth): paging past them returns an empty page."""
    def respond(req: httpx.Request) -> httpx.Response:
        now = clock()
        after = parse_qs(urlsplit(str(req.url)).query).get("after")
        kind, span = ("t1", comments_span_h) if "/comments/" in req.url.path else ("t3", posts_span_h)
        deep = stream_times(now, span_h=span, count=depth)
        times = deep[:100]
        if after:
            last = next((w for w in deep if rid(kind, w) == after[0]), None)
            times = [w for w in deep if w < last][:100] if last is not None else []
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


FAR_BACK = at(-24 * 30)


def P(kind: str, oldest: datetime, newest: datetime, collected: datetime | None = None, entries: int = 100,
      truncated: bool = False, floor: datetime | None = FAR_BACK) -> rs.Poll:
    """A stored poll. Its default floor lies far back: a complete poll stopped at the feed's end, not at its floor,
    so a hole before it is unreachable (fix round 2); pass `floor` to model a poll that reached a nearer floor."""
    return rs.Poll(kind, collected or newest + timedelta(minutes=1), newest, oldest, entries, 1, truncated, floor)


def record(*polls: rs.Poll) -> None:
    for p in polls:
        rs.append_poll(p)


def full_posts() -> list[rs.Poll]:
    """Posts polls that cover D fully and settle it."""
    return [P("new", at(-30), at(24.5)), P("new", at(30), at(40))]


def floor_at(kind: str, now: datetime, retention_days: int = 30) -> datetime:
    """The paging floor a poll at `now` runs against, from the poll files inside the retention window."""
    return rs._paging_floor(kind, now, rs.stored_polls(now.date(), retention_days))


def after_ids(fake: Fake) -> list[str | None]:
    return [parse_qs(urlsplit(str(r.url)).query).get("after", [None])[0] for r in fake.requests]


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
    # fix round 3 (E1): a posts anchor at 03:30, so the one-entry posts poll at 12:00 reaches its floor (complete)
    record(P("new", at(-30), at(3.5), collected=at(4)))
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
    assert q.config.reddit_impl_order == ("reddit_web", "reddit_stream")  # SPEC AC14 default (owner D3)
    method, pts = rs.pick_impl(q.config.reddit_impl_order, series, days[-1], D, min_points=3)
    assert method == "reddit_web" and all(v == 9.0 for _, v in pts)
    method, pts = rs.pick_impl(("reddit_stream", "reddit_web"), series, days[-1], D, min_points=3)
    assert method == "reddit_stream" and pts == sorted(series["reddit_stream"]) and all(v == 1.0 for _, v in pts)


def test_fallback_to_posts_only_series_when_comments_missing(q):
    days = [D - timedelta(days=i) for i in range(5)]
    series = {"reddit_stream": [(D, 1.0)], "reddit_web": [(d, 9.0) for d in days]}
    stream_first = ("reddit_stream", "reddit_web")
    method, pts = rs.pick_impl(stream_first, series, days[-1], D, min_points=3)
    assert method == "reddit_web" and len(pts) == 5
    assert rs.pick_impl(stream_first, {"reddit_stream": [], "reddit_web": []}, days[-1], D,
                        min_points=1) == (None, [])
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
    st = rs.stream_status(at(48), q, days=3)
    day = st["days"][D.isoformat()]
    assert day["coverage_comments"] == 1.0 and day["coverage_new"] == 1.0 and day["partial"] is False
    assert day["fetched"] >= 2 and isinstance(day["missing"], int)
    assert set(st["today"]) == {"polls_comments", "polls_new", "entries_seen"}


# --- fix round 1: truncated comments paging never settles a day (review finding 1) ---

def _d_covered_to_20h(q, led) -> None:
    """Four SOL posts in D, posts that cover and settle D, one complete comments poll over [D-3 h, D 20:00]."""
    poll(q, Clock(at(12)), ok(atom([entry(f"t3_h{i}", at(1 + i)) for i in range(4)])), kind="new", led=led)
    record(*full_posts(), P("comments", at(-3), at(20), collected=at(20)))


def _not_settled(q, led, now: datetime) -> None:
    doc = rs.commit_day(D, q, led, now=now)
    assert doc["settled"] is False and doc["coins"]["SOL"]["reason"] == "not_settled"
    assert store.read_points(rs.SOURCE, "SOL") == [] and D in rs.open_days(now)


def test_budget_cut_paging_after_midnight_does_not_settle_previous_day(q):
    led = ledger()
    _d_covered_to_20h(q, led)
    clock = Clock(at(26))
    s = src(q, clock)
    s.spend(s.remaining() - 1)  # room for one page only; the page lies wholly after D
    out, fake = poll(q, clock, live_stream(clock, comments_span_h=1), led=led, s=s)
    assert len(fake.requests) == 1 and out.poll.entries == 100 and out.poll.oldest >= at(24)
    stored = [p for p in rs.read_polls(D, D + timedelta(days=1)) if p.kind == "comments" and p.collected_at == at(26)]
    assert out.poll.truncated is True and stored == [out.poll]
    # its real span still counts toward coverage (of D+1 here)
    assert rs.coverage(D + timedelta(days=1), rs.read_polls(D, D + timedelta(days=1)), "comments") > 0
    _not_settled(q, led, at(27))


@pytest.mark.parametrize("stop", ["paused_between_pages", "error_on_page_2"])
def test_pause_mid_paging_after_midnight_does_not_settle_previous_day(q, stop):
    led = ledger()
    _d_covered_to_20h(q, led)
    clock = Clock(at(26))
    s = src(q, clock)
    live = live_stream(clock, comments_span_h=1)

    def respond(req):
        if "after" not in parse_qs(urlsplit(str(req.url)).query):
            if stop == "paused_between_pages":
                s.warn("rate_limited")  # another unit paused Reddit while this page was in flight
            return live(req)
        return httpx.Response(429, content=b"slow")
    out, fake = poll(q, clock, respond, led=led, s=s)
    assert len(fake.requests) == (1 if stop == "paused_between_pages" else 2) and s.is_paused()
    assert out.poll is not None and out.poll.oldest >= at(24) and out.poll.truncated is True
    _not_settled(q, led, at(27))


def test_non_t1_last_id_after_midnight_does_not_settle_previous_day(q):
    led = ledger()
    _d_covered_to_20h(q, led)
    times = stream_times(at(26), span_h=1)
    body = atom([entry(rid("t1", w), w) for w in times[:-1]] + [entry("t3_odd1", times[-1])])
    out, fake = poll(q, Clock(at(26)), ok(body), led=led)
    assert len(fake.requests) == 1 and out.poll.entries == 100 and out.poll.oldest >= at(24)
    assert out.poll.truncated is True
    _not_settled(q, led, at(27))


def test_complete_paging_after_midnight_settles_previous_day(q):
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry(f"t3_h{i}", at(1 + i)) for i in range(4)])), kind="new", led=led)
    record(*full_posts(), P("comments", at(4), at(24.2), collected=at(24.2)))
    clock = Clock(at(28))
    out, fake = poll(q, clock, live_stream(clock, comments_span_h=1), led=led)
    assert out.reason is None and len(fake.requests) == 4 and out.poll.truncated is False
    assert at(24) <= out.poll.oldest <= at(24.2)  # paging reached the floor; the poll lies wholly after D
    doc = rs.commit_day(D, q, led, now=at(29))
    assert doc["settled"] is True and doc["partial"] is True and doc["coins"]["SOL"]["reason"] == "fetched"
    assert dict(store.read_points(rs.SOURCE, "SOL"))[D] == 4.0


def test_poll_after_truncated_poll_pages_back_to_last_complete_poll(q):
    led = ledger()
    _d_covered_to_20h(q, led)
    record(P("comments", at(25), at(26), collected=at(26), truncated=True))
    clock = Clock(at(28.5))
    out, fake = poll(q, clock, live_stream(clock, comments_span_h=1), led=led)
    assert out.reason is None and out.poll.truncated is False and out.poll.oldest <= at(20)
    doc = rs.commit_day(D, q, led, now=at(30))
    assert doc["coverage"]["comments"] == 1.0 and doc["settled"] is True and doc["partial"] is False
    assert doc["coins"]["SOL"]["reason"] == "fetched"


def test_posts_never_send_after(q):
    record(P("new", at(0), at(1), collected=at(1)))
    clock = Clock(at(20))
    out, fake = poll(q, clock, live_stream(clock, posts_span_h=3), kind="new")
    assert out.reason is None and len(fake.requests) == 1 and out.poll.entries == 100
    # fix round 3 (E1): the page does not reach its floor (01:00), so the poll is truncated, never a feed end
    assert out.poll.oldest > at(1) and out.poll.pages == 1 and out.poll.truncated is True
    assert floor_at("new", at(26)) == at(1)  # it never becomes the anchor: the next posts poll keeps the floor
    assert all("after" not in parse_qs(urlsplit(str(r.url)).query) for r in fake.requests)


# --- fix round 1: a well-formed empty feed is a recorded poll (S2) ---

def test_empty_feed_recorded_as_poll_and_not_retried_before_interval(q):
    clock = Clock(at(12))
    s = src(q, clock)
    out, fake = poll(q, clock, ok(atom([])), s=s)
    assert out.reason == "empty_feed" and len(fake.requests) == 1
    assert out.poll is not None and out.poll.entries == 0 and out.poll.newest is None and out.poll.oldest is None
    assert rs.read_polls(D, D) == [out.poll]
    clock.t = at(12) + timedelta(seconds=120)
    again, fake2 = poll(q, clock, ok(atom([])), s=s)
    assert again.reason == "not_due" and fake2.requests == [] and s.used == 1
    assert rs.coverage(D, rs.read_polls(D, D), "comments") == 0.0
    assert rs.due_kinds(q, at(12) + timedelta(seconds=q.config.reddit_comments_poll_interval_s)) == ["comments", "new"]


def test_empty_poll_never_settles_a_day():
    polls = [*full_posts(), P("comments", at(-3), at(20)), rs.Poll("comments", at(30), None, None, 0, 1, False)]
    st = rs.day_status(D, polls, now=at(48), min_coverage=0.8)
    assert st.settled is False and st.reason == "not_settled" and st.polls["comments"] == 1


# --- fix round 1: AC3 zero rule without a stream canary (owner D2) ---

def _commit_zero_sol(q):
    """D covered and settled for both kinds; four posts mention ETH only, so SOL's count is a real zero."""
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry(f"t3_z{i}", at(1 + i), title="ETH news") for i in range(4)])),
         kind="new", led=led)
    record(*full_posts(), P("comments", at(-3), at(24.5)), P("comments", at(30), at(40)))
    return rs.commit_day(D, q, led, now=at(48))


def test_covered_settled_real_zero_missing_without_stream_canary(q):
    store.write_series(SourceSeries(rs.SOURCE, "SOL", [(D - timedelta(days=i), 1.0) for i in range(1, 4)]), today=D)
    assert rs.trailing_median("SOL", D) == 1.0  # history exists and its median is below 5
    doc = _commit_zero_sol(q)
    assert doc["settled"] is True and doc["coverage"] == {"comments": 1.0, "new": 1.0}
    assert doc["canary_ok"] is False  # the stream sends no canary query; none is assumed
    assert doc["coins"]["SOL"] == {"reason": "zero_no_canary", "value": None, "trailing_median": 1.0}
    assert D not in dict(store.read_points(rs.SOURCE, "SOL")) and D not in web_evidence.read_rows(rs.SOURCE, "SOL")
    assert doc["coins"]["ETH"]["reason"] == "fetched" and dict(store.read_points(rs.SOURCE, "ETH"))[D] == 4.0


def test_zero_without_history_stays_missing(q):
    assert rs.trailing_median("SOL", D) is None
    doc = _commit_zero_sol(q)
    assert doc["coins"]["SOL"] == {"reason": "zero_no_canary", "value": None, "trailing_median": None}
    assert store.read_points(rs.SOURCE, "SOL") == [] and doc["missing"]["zero_no_canary"] >= 1


# --- fix round 1: coverage is per feed kind, never per subreddit (owner D1), unknown without polls (S1) ---

def test_coverage_is_per_feed_kind_never_per_subreddit(q):
    doc = _commit_with_comments(q, -3, 24.5)
    assert doc["coverage_scope"] == "feed_kind" and set(doc["coverage"]) == set(rs.KINDS)
    assert not any("subreddit" in k for k in doc)
    st = rs.stream_status(at(48), q)
    assert not any("subreddit" in k for day in st["days"].values() for k in day)


def test_stream_status_coverage_unknown_without_polls(q):
    record(P("comments", at(1), at(23)))
    st = rs.stream_status(at(48), q, days=3)
    day = st["days"][D.isoformat()]
    assert day["coverage_comments"] == pytest.approx(22 / 24, abs=1e-4) and day["coverage_new"] is None
    for other in (D - timedelta(days=1), D + timedelta(days=1)):
        assert st["days"][other.isoformat()]["coverage_comments"] is None
        assert st["days"][other.isoformat()]["coverage_new"] is None


# --- fix round 2: the floor reaches back to the last complete poll, however old; a day settles only through
# --- continuity or the feed's end (review finding: aged-out floor undercount)

def _cut_poll(q, led, when: datetime, span_h: float = 1) -> rs.PollOutcome:
    """A comments poll at `when` that the day's budget cuts after its first page (stored as truncated)."""
    clock = Clock(when)
    s = src(q, clock)
    s.spend(s.remaining() - 1)
    out, fake = poll(q, clock, live_stream(clock, comments_span_h=span_h), led=led, s=s)
    assert len(fake.requests) == 1 and out.poll.truncated is True
    return out


def _full_poll(q, led, when: datetime, **feed) -> rs.PollOutcome:
    """Comments polls 2 h apart from `when` until one reaches its floor; returns that complete poll. Fix round 3 (E3):
    a poll stops at `reddit_stream_max_pages_per_poll` requests, and the next one resumes at its saved cursor."""
    for i in range(4):
        clock = Clock(when + timedelta(hours=2 * i))
        out, fake = poll(q, clock, live_stream(clock, **feed), led=led)
        assert out.reason is None and len(fake.requests) <= q.config.reddit_stream_max_pages_per_poll
        if not out.poll.truncated:
            return out
    raise AssertionError("no poll reached its floor")


def _next(out: rs.PollOutcome, hours: float = 2) -> datetime:
    return out.poll.collected_at + timedelta(hours=hours)


def _comments_of_d_from(h: float, span_h: float) -> set[str]:
    """The ids of every comment the fake feed holds created in [D h:00, D's end)."""
    return {rid("t1", w) for w in stream_times(at(24), span_h=span_h, count=2000) if at(h) <= w < at(24)}


def _settled_full(q, led, now: datetime, span_h: float) -> None:
    """D settles with full comments coverage and the count of every comment of D 20:00-24:00 (no undercount)."""
    doc = rs.commit_day(D, q, led, now=now)
    assert doc["settled"] is True and doc["coverage"] == {"comments": 1.0, "new": 1.0} and doc["partial"] is False
    seen = rs.read_seen(D)
    assert _comments_of_d_from(20, span_h) <= seen
    assert doc["coins"]["SOL"]["reason"] == "fetched" and dict(store.read_points(rs.SOURCE, "SOL"))[D] == len(seen)
    assert doc["gap_unreachable"]["comments"] == {"hours": 0.0, "spans": []}


def test_two_budget_cut_polls_then_complete_poll_reaches_aged_out_floor_no_undercount(q):
    """(a) Complete at D 20:00, cut on D+1 and on D+2, complete on D+3: the D 20:00 poll is older than the due
    window, yet the complete poll pages back to its newest entry, so D is never settled on 20 h of comments."""
    led = ledger()
    _d_covered_to_20h(q, led)
    _cut_poll(q, led, at(26), span_h=3)  # the cut polls read the same 3 h feed as the complete ones
    _cut_poll(q, led, at(50), span_h=3)
    out = _full_poll(q, led, at(74), comments_span_h=3)
    assert out.poll.floor == at(20) and out.poll.oldest <= at(20)
    last = _full_poll(q, led, _next(out), comments_span_h=3)  # a poll wholly after D
    _settled_full(q, led, _next(last, 1), 3)


def test_host_off_for_a_day_then_complete_poll_reaches_aged_out_floor_no_undercount(q):
    """(b) Complete at D 20:00, the host off all of D+1, complete on D+2."""
    led = ledger()
    _d_covered_to_20h(q, led)
    out = _full_poll(q, led, at(58), comments_span_h=3)
    assert out.poll.floor == at(20) and out.poll.oldest <= at(20)
    last = _full_poll(q, led, _next(out), comments_span_h=3)
    _settled_full(q, led, _next(last, 1), 3)


def test_truncated_poll_then_complete_poll_past_due_window_settles_previous_day(q):
    """(e) Continuity with an aged-out complete poll: cut on D+1, complete on D+2 pages back to D 20:00."""
    led = ledger()
    _d_covered_to_20h(q, led)
    _cut_poll(q, led, at(26), span_h=3)
    out = _full_poll(q, led, at(58), comments_span_h=3)
    assert out.poll.floor == at(20) and out.poll.oldest <= at(20)
    last = _full_poll(q, led, _next(out), comments_span_h=3)
    _settled_full(q, led, _next(last, 1), 3)


def test_paging_floor_uses_complete_poll_older_than_due_window(q):
    """(c) The newest entry of the last complete poll, looked up across every stored poll file."""
    record(P("comments", at(-3), at(20), collected=at(20)),
           P("comments", at(25), at(26), collected=at(26), truncated=True),
           P("comments", at(49), at(50), collected=at(50), truncated=True),
           P("new", at(-30), at(51), collected=at(51)))
    assert not [p for p in rs._recent_polls(q, at(58)) if p.kind == "comments" and not p.truncated]
    assert floor_at("comments", at(58)) == at(20)
    assert floor_at("comments", at(24 * 6)) == at(20)
    assert floor_at("new", at(58)) == at(51)


def test_paging_floor_without_complete_poll_falls_back_then_first_complete_poll_anchors(q):
    """(d) No complete poll: the start of the newest completed day; the first complete poll reaches it, stores it
    as its floor, and the next floor is that poll's newest entry."""
    assert floor_at("comments", at(30)) == at(0)
    record(P("comments", at(25), at(26), collected=at(26), truncated=True))
    assert floor_at("comments", at(30)) == at(0)
    out = _full_poll(q, ledger(), at(30), comments_span_h=3)
    assert out.poll.floor == at(0) and out.poll.oldest <= at(0)
    assert floor_at("comments", _next(out)) == out.poll.newest
    assert rs.read_polls(D + timedelta(days=1), D + timedelta(days=1))[-1].floor == at(0)


def test_day_with_only_truncated_polls_never_settles_through_fallback_floor(q):
    """A truncated poll left 20:00-24:00 of D unpaged; the first complete poll (D+2) pages back to the fallback floor
    (D+1 00:00) only, so nothing reached D's hole: D stays missing (`not_settled`), never stored at 0.83."""
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry(f"t3_h{i}", at(1 + i)) for i in range(4)])), kind="new", led=led)
    record(*full_posts(), P("comments", at(0), at(20), collected=at(20), truncated=True))
    out = _full_poll(q, led, at(58), comments_span_h=3)
    assert out.poll.floor == at(24)
    last = _full_poll(q, led, _next(out), comments_span_h=3)
    _not_settled(q, led, _next(last, 1))


@pytest.mark.parametrize("anchor_h", [20, 12])
def test_gap_beyond_feed_depth_stays_truncated_and_never_stored(q, anchor_h):
    """(I3, superseded by fix round 3 E1) The host was off; the feed holds 36 h only, so paging ends at the feed's
    end (an empty page) before the floor. That poll is truncated: it never settles D or becomes the anchor, the next
    polls page the gap again, and D stays missing (`not_settled`) at its covered share, never stored as full."""
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry(f"t3_h{i}", at(1 + i)) for i in range(4)])), kind="new", led=led)
    record(*full_posts(), P("comments", at(-3), at(anchor_h), collected=at(anchor_h)))
    for h in (58, 60, 62):
        clock = Clock(at(h))
        out, fake = poll(q, clock, live_stream(clock, comments_span_h=3, depth=1200), led=led)
        assert out.poll.truncated is True and out.poll.floor == at(anchor_h)
        assert len(fake.requests) <= q.config.reddit_stream_max_pages_per_poll
    assert floor_at("comments", at(64)) == at(anchor_h)  # the gap is paged again by the next poll
    doc = rs.commit_day(D, q, led, now=at(63))
    assert doc["settled"] is False and doc["coverage"]["comments"] == pytest.approx(anchor_h / 24, abs=1e-6)
    assert doc["gap_unreachable"]["new"] == {"hours": 0.0, "spans": []}
    assert doc["coins"]["SOL"] == {"reason": "not_settled", "value": None}
    assert store.read_points(rs.SOURCE, "SOL") == [] and D in rs.open_days(at(63))


def test_complete_poll_with_unknown_floor_never_closes_a_hole():
    """A hole before a complete poll is unreachable only when that poll's floor reached back to the previous complete
    poll (it stopped at the feed's end); an unknown floor (a poll file of an earlier head) keeps the day open."""
    unknown = [*full_posts(), P("comments", at(-3), at(20)), P("comments", at(30), at(40), floor=None)]
    st = rs.day_status(D, unknown, now=at(48), min_coverage=0.8)
    assert st.settled is False and st.reason == "not_settled"
    skipped = [*full_posts(), P("comments", at(-3), at(20)), P("comments", at(30), at(40), floor=at(24))]
    assert rs.day_status(D, skipped, now=at(48), min_coverage=0.8).settled is False
    feed_end = [*full_posts(), P("comments", at(-3), at(20)), P("comments", at(30), at(40), floor=at(20))]
    st = rs.day_status(D, feed_end, now=at(48), min_coverage=0.8)
    assert st.settled is True and st.reason is None and st.partial is True
    assert st.gap_unreachable == {"comments": [(at(20), at(24))], "new": []}


def test_poll_file_of_earlier_head_reads_as_truncated_with_unknown_floor(q):
    """A poll file written before `truncated` (and `floor`) existed: read as truncated, so it never settles a day."""
    rs._write({"polls": [{"kind": "comments", "collected_at": at(20).isoformat(), "newest": at(19.9).isoformat(),
                          "oldest": at(5).isoformat(), "entries": 100, "pages": 1}]}, rs.polls_path(D))
    [p] = rs.read_polls(D, D)
    assert p.truncated is True and p.floor is None
    assert floor_at("comments", at(21)) == at(-24)  # not a complete poll: the fallback floor


# --- fix round 3 (owner decisions E1-E4): a poll that ends before its floor is truncated (E1); poll files are kept
# --- `reddit_stream_poll_retention_days` (E2); a per-poll page cap with continuation at a saved cursor (E3);
# --- `gap_unreachable` without what truncated polls covered (E4)

@pytest.mark.parametrize("transient", ["empty", "short", "no_progress"])
def test_transient_end_before_floor_is_truncated_then_good_poll_pages_the_gap_no_undercount(q, transient):
    """E1: page 2 of the poll at D+1 02:00 is blank, short, or page 1 again, before the floor (D 20:00). The poll is
    truncated: D stays unsettled and the floor stays D 20:00, so the good poll at 04:30 pages the gap again and D
    settles on every comment of 20:00-24:00, never on an undercount."""
    led = ledger()
    _d_covered_to_20h(q, led)
    clock = Clock(at(26))
    live = live_stream(clock, comments_span_h=1)

    def respond(req):
        if "after" not in parse_qs(urlsplit(str(req.url)).query):
            return live(req)
        if transient == "empty":
            return ok(atom([]))(req)
        if transient == "short":
            return ok(atom([entry(rid("t1", w), w) for w in stream_times(at(25), span_h=1)[:10]]))(req)
        return ok(stream_feed(at(26), span_h=1))(req)
    out, fake = poll(q, clock, respond, led=led)
    assert len(fake.requests) == 2 and out.reason is None
    assert out.poll.truncated is True and out.poll.floor == at(20) and out.poll.oldest > at(20)
    _not_settled(q, led, at(27))
    assert floor_at("comments", at(28)) == at(20)  # never the anchor
    good = _full_poll(q, led, at(28.5), comments_span_h=1)
    assert good.poll.floor == at(20) and good.poll.oldest <= at(20)
    last = _full_poll(q, led, _next(good), comments_span_h=1)
    _settled_full(q, led, _next(last, 1), 1)


def test_comments_paging_off_full_page_short_of_floor_is_truncated(q):
    """E1: with paging off, a full comments page that does not reach the floor is truncated, not the feed's end."""
    q = with_cfg(q, reddit_comments_paging=False)
    record(P("comments", at(0), at(4), collected=at(4)))
    clock = Clock(at(20))
    out, fake = poll(q, clock, live_stream(clock, comments_span_h=3))
    assert len(fake.requests) == 1 and out.poll.entries == 100 and out.poll.oldest > at(4)
    assert out.poll.truncated is True and floor_at("comments", at(22)) == at(4)


def test_quiet_feed_short_page_reaching_its_floor_is_complete(q):
    """E1: fewer entries than a page, the oldest older than the floor: the poll reached its floor (complete)."""
    record(P("comments", at(0), at(4), collected=at(4)))
    quiet = atom([entry(rid("t1", w), w) for w in stream_times(at(20), span_h=60, count=30)])
    out, fake = poll(q, Clock(at(20)), ok(quiet))
    assert len(fake.requests) == 1 and out.poll.entries == 30 and out.poll.oldest <= at(4)
    assert out.poll.truncated is False and floor_at("comments", at(22)) == out.poll.newest


def test_posts_page_reaching_its_floor_is_complete(q):
    """E1, posts (never paged): a page whose oldest entry reaches the floor is complete; one that does not is
    truncated (`test_posts_never_send_after`)."""
    record(P("new", at(0), at(1), collected=at(1)))
    clock = Clock(at(20))
    out, fake = poll(q, clock, live_stream(clock, posts_span_h=72), kind="new")
    assert len(fake.requests) == 1 and out.poll.oldest <= at(1) and out.poll.truncated is False
    assert floor_at("new", at(26)) == out.poll.newest


def test_empty_feed_poll_is_truncated_and_never_the_anchor(q):
    """E1: a well-formed empty feed stays a recorded poll; it is truncated and never moves the floor."""
    record(P("comments", at(0), at(4), collected=at(4)))
    out, _ = poll(q, Clock(at(12)), ok(atom([])))
    assert out.reason == "empty_feed" and out.poll.entries == 0 and out.poll.truncated is True
    assert floor_at("comments", at(14)) == at(4)


def test_capped_polls_make_deeper_progress_across_polls_and_settle_without_undercount(q):
    """E3: after a host stop the floor (D 20:00) lies 80 h back, 27 pages of the 3 h feed. Each poll stops at the
    page cap; the next reconnects its fresh prefix to the stored coverage and resumes at the saved cursor, so it
    reaches deeper instead of refetching the capped prefix. D stays unsettled after each cut poll and settles on
    every comment of 20:00-24:00 once a poll reaches the floor."""
    led = ledger()
    _d_covered_to_20h(q, led)
    cap = q.config.reddit_stream_max_pages_per_poll
    outs, t = [], at(100)
    while True:
        clock = Clock(t)
        out, fake = poll(q, clock, live_stream(clock, comments_span_h=3), led=led)
        assert out.reason is None and out.requests == len(fake.requests) <= cap
        outs.append((out, fake))
        if not out.poll.truncated:
            break
        _not_settled(q, led, _next(out, 1))
        t += timedelta(hours=2)
    assert len(outs) == 3 and outs[0][0].requests == cap
    for (prev, _), (cur, fake) in zip(outs, outs[1:]):
        cursor = prev.poll.runs[-1][2]
        assert cursor in after_ids(fake) and after_ids(fake).index(cursor) <= 2  # reconnected, then resumed
        assert cur.poll.oldest < prev.poll.oldest  # deeper
    done = outs[-1][0]
    assert done.poll.floor == at(20) and done.poll.oldest <= at(20)
    last = _full_poll(q, led, _next(done), comments_span_h=3)
    _settled_full(q, led, _next(last, 1), 3)


def test_disconnected_fresh_prefix_never_bridges_and_later_polls_still_reach_the_floor(q):
    """E3: a poll whose fresh prefix stops (here a page cap of 1) before it reconnects to the stored coverage keeps
    its own span only: the hole between them stays uncovered and nothing is resumed. The next polls reconnect to the
    newest stored stretch, page through the hole and resume deeper; D settles once a poll reaches the floor."""
    led = ledger()
    _d_covered_to_20h(q, led)
    clock = Clock(at(100))
    first, _ = poll(q, clock, live_stream(clock, comments_span_h=3), led=led)
    clock = Clock(at(130))
    cut, fake = poll(with_cfg(q, reddit_stream_max_pages_per_poll=1), clock, live_stream(clock, comments_span_h=3),
                     led=led)
    assert first.poll.truncated is True and cut.poll.truncated is True and len(fake.requests) == 1
    assert [r[:2] for r in cut.poll.runs] == [(cut.poll.oldest, cut.poll.newest)]
    assert cut.poll.oldest > first.poll.newest
    day4 = D + timedelta(days=4)  # 96 h to 120 h: only the first poll's 96-100 h is covered, the hole is not bridged
    polls = rs.stored_polls(day4 + timedelta(days=1), 30)
    assert rs.coverage(day4, polls, "comments") == pytest.approx((first.poll.newest - at(96)) / timedelta(days=1))
    _not_settled(q, led, at(131))
    out = _full_poll(q, led, at(132), comments_span_h=3)
    assert out.poll.floor == at(20) and out.poll.oldest <= at(20)
    last = _full_poll(q, led, _next(out), comments_span_h=3)
    _settled_full(q, led, _next(last, 1), 3)


def test_requests_per_poll_stay_within_page_cap_after_long_host_stop(q):
    """E3: eight days off; one pass spends at most the page cap per feed kind (posts never page: one request)."""
    led = ledger()
    _d_covered_to_20h(q, led)
    clock = Clock(at(24 * 9 + 5))
    s = src(q, clock)
    fake = Fake(live_stream(clock, comments_span_h=3))
    res = rs.run_due(fake.client(), s, q, ledger=led, clock=clock, sleep=clock.sleep, rng=random.Random(4))
    cap = q.config.reddit_stream_max_pages_per_poll
    by_kind = {o.kind: o for o in res.outcomes}
    assert res.stop == "done" and set(by_kind) == set(rs.KINDS)
    assert by_kind["comments"].requests == cap and by_kind["comments"].poll.truncated is True
    assert by_kind["new"].requests == 1 and by_kind["new"].poll.truncated is True
    assert len(fake.requests) == s.used == cap + 1


@pytest.mark.parametrize("state", ["valid", "other_floor", "not_t1", "beyond_retention"])
def test_saved_cursor_resumed_only_from_valid_state(q, state):
    """E3: a cursor is resumed only from a truncated poll of the open segment that ran against the same floor, inside
    the retention window, with a t1 id. A stale or invalid one is never requested, and the poll is complete only
    when its own pages reach the floor."""
    led = ledger()
    _d_covered_to_20h(q, led)
    times = stream_times(at(47.5), span_h=3)
    cursor = rid("t1", times[-1]) if state != "not_t1" else "t3_" + rid("t1", times[-1])[3:]
    floor = at(10) if state == "other_floor" else at(20)
    record(rs.Poll("comments", at(47.5), times[0], times[-1], 100, 1, True, floor, ((times[-1], times[0], cursor),)))
    if state == "beyond_retention":
        q = with_cfg(q, reddit_stream_poll_retention_days=1)
    clock = Clock(at(74))
    out, fake = poll(q, clock, live_stream(clock, comments_span_h=3), led=led)
    assert (cursor in after_ids(fake)) is (state == "valid")
    assert len(fake.requests) <= q.config.reddit_stream_max_pages_per_poll
    if state == "beyond_retention":  # neither the cursor nor the D 20:00 anchor is read: the fallback floor
        assert out.poll.floor == at(48) and out.poll.truncated is False and out.poll.oldest <= at(48)
    else:
        assert out.poll.floor == at(20) and out.poll.truncated is True and out.poll.oldest > at(20)
        _not_settled(q, led, at(75))


def test_prune_removes_only_stream_poll_files_older_than_retention(q):
    """E2: after a poll, poll files of days older than `reddit_stream_poll_retention_days` are deleted; the seen ids,
    completeness files, item ledger and pace state are other stores and stay."""
    led = ledger()
    old, edge = D - timedelta(days=31), D - timedelta(days=30)
    record(P("comments", at(1, old), at(2, old)), P("comments", at(1, edge), at(2, edge)))
    rs._write({"ids": ["t1_old1"]}, rs.seen_path(old))
    rs._write({"day": old.isoformat()}, rs.completeness_path(old))
    led.add([reddit_items.LedgerRow("t1_old1", None, None, at(1, old), at(2, old), "comments", ())])
    poll(q, Clock(at(12)), ok(stream_feed(at(12))), led=led)
    assert not rs.polls_path(old).exists()
    assert rs.polls_path(edge).exists() and rs.polls_path(D).exists()
    assert rs.seen_path(old).exists() and rs.completeness_path(old).exists() and reddit_items.ledger_path(old).exists()
    assert pc_pace.state_path(rw.SOURCE).exists()
    rs.prune_polls(at(12), 5)
    assert [p.stem for p in rs.polls_path(D).parent.glob("*.json")] == [D.isoformat()]


def test_paging_floor_falls_back_past_retention(q):
    """E2: a complete poll older than the retention window is never the anchor: the fallback floor applies."""
    old = D - timedelta(days=31)
    record(P("comments", at(-3, old), at(20, old), collected=at(20, old)))
    assert floor_at("comments", at(12), 31) == at(20, old)
    assert floor_at("comments", at(12), 30) == at(-24)
    clock = Clock(at(12))
    out, _ = poll(q, clock, live_stream(clock))
    assert out.poll.floor == at(-24) and out.poll.truncated is False and not rs.polls_path(old).exists()


def test_gap_unreachable_excludes_what_a_truncated_poll_covered(q):
    """E4: the hole between two complete polls (20:00 to D's end) loses the hour a truncated poll observed; only the
    uncovered rest is reported, in hours and spans."""
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry(f"t3_h{i}", at(1 + i)) for i in range(4)])), kind="new", led=led)
    record(*full_posts(), P("comments", at(-3), at(20), collected=at(20)),
           P("comments", at(21), at(22), collected=at(22.5), truncated=True),
           P("comments", at(30), at(40), floor=at(20)))
    doc = rs.commit_day(D, q, led, now=at(48))
    assert doc["settled"] is True and doc["coverage"]["comments"] == pytest.approx(21 / 24)
    assert doc["gap_unreachable"]["comments"] == {
        "hours": 3.0, "spans": [[at(20).isoformat(), at(21).isoformat()], [at(22).isoformat(), at(24).isoformat()]]}
    assert doc["partial"] is True and doc["coins"]["SOL"]["reason"] == "fetched"


def test_gap_unreachable_empty_when_a_truncated_poll_covered_the_whole_hole(q):
    """E4: a truncated poll observed all of the hole: nothing is unreachable, D is fully covered and not partial."""
    led = ledger()
    poll(q, Clock(at(12)), ok(atom([entry(f"t3_h{i}", at(1 + i)) for i in range(4)])), kind="new", led=led)
    record(*full_posts(), P("comments", at(-3), at(20), collected=at(20)),
           P("comments", at(19), at(25), collected=at(25.5), truncated=True),
           P("comments", at(30), at(40), floor=at(20)))
    doc = rs.commit_day(D, q, led, now=at(48))
    assert doc["settled"] is True and doc["coverage"]["comments"] == 1.0 and doc["partial"] is False
    assert doc["gap_unreachable"]["comments"] == {"hours": 0.0, "spans": []}
    assert doc["coins"]["SOL"]["reason"] == "fetched"


def test_day_before_retention_window_is_not_evaluated_again(q):
    """E2: once a day's poll files are pruned it can no longer be evaluated; its last completeness document stays as
    written, never rewritten with a coverage of 0 from missing polls."""
    led = ledger()
    _d_covered_to_20h(q, led)
    doc = rs.commit_day(D, q, led, now=at(27))
    assert doc["settled"] is False and doc["coverage"]["comments"] == pytest.approx(20 / 24)
    later = at(24 * 32)
    rs.prune_polls(later, q.config.reddit_stream_poll_retention_days)
    assert rs.read_polls(D - timedelta(days=1), D + timedelta(days=2)) == []
    assert rs.commit_day(D, q, led, now=later) == doc and rs.read_completeness(D) == doc


# --- fix round 4: a saved cursor whose resumed page is empty or makes no progress is dead (never resumed again);
# --- a cursor whose resumed page failed (error, pause) stays retriable

def _stale_cursor_setup(q, led) -> str:
    """D covered to 20:00 by a complete poll (the floor), and a truncated poll at D+3 00:00 against that floor whose
    one stretch (the 3 h before it) saved the cursor returned: its id."""
    _d_covered_to_20h(q, led)
    times = stream_times(at(72), span_h=3)
    cursor = rid("t1", times[-1])
    record(rs.Poll("comments", at(72), times[0], times[-1], 100, 1, True, at(20), ((times[-1], times[0], cursor),)))
    return cursor


def _resume_answers(clock: Clock, cursor: str, answer: str):
    """The 3 h comments feed of `live_stream`, except that a request resumed at `cursor` gets `answer`: an empty
    page, a page that makes no progress (the newest page again), a 503, or the real page below the cursor."""
    live = live_stream(clock, comments_span_h=3)

    def respond(req):
        if parse_qs(urlsplit(str(req.url)).query).get("after") != [cursor] or answer == "live":
            return live(req)
        if answer == "empty":
            return ok(atom([]))(req)
        if answer == "no_progress":
            return ok(stream_feed(clock(), span_h=3))(req)
        return httpx.Response(503, content=b"down")
    return respond


@pytest.mark.parametrize("answer", ["empty", "no_progress"])
def test_stale_cursor_with_empty_or_no_progress_resume_is_dead_and_next_poll_pages_fresh(q, answer):
    """A syntactically valid cursor inside the retention window whose resumed page is empty (or makes no progress)
    is marked dead in the poll that tried it: the poll stays truncated and D unsettled, the next poll spends no
    request on that cursor and pages fresh toward the floor under the page cap as if no cursor existed, and the dead
    mark survives the poll file round trip."""
    led = ledger()
    cursor = _stale_cursor_setup(q, led)
    clock = Clock(at(74))
    out, fake = poll(q, clock, _resume_answers(clock, cursor, answer), led=led)
    assert after_ids(fake) == [None, cursor] and out.reason is None
    assert out.poll.dead == (cursor,) and out.poll.truncated is True and out.poll.floor == at(20)
    assert all(c != cursor for _, _, c in out.poll.spans())
    [stored] = [p for p in rs.read_polls(D + timedelta(days=3), D + timedelta(days=3)) if p.collected_at == at(74)]
    assert stored.dead == (cursor,)
    _not_settled(q, led, at(75))
    assert floor_at("comments", at(75)) == at(20)  # never the anchor
    clock = Clock(at(76))
    nxt, fake = poll(q, clock, _resume_answers(clock, cursor, answer), led=led)
    assert cursor not in after_ids(fake)
    assert nxt.requests == len(fake.requests) == q.config.reddit_stream_max_pages_per_poll  # fresh, under the cap
    assert nxt.poll.oldest < out.poll.oldest and nxt.poll.truncated is True
    _not_settled(q, led, at(77))


def test_dead_cursor_costs_at_most_one_failed_resume_over_several_days(q):
    """Polls every 2 h over three days: the stale cursor is requested once in total, never again, every poll stays
    under the page cap, later polls still reach the floor (live cursors resume), and D settles without undercount
    only after a poll whose own pages reached the floor."""
    led = ledger()
    cursor = _stale_cursor_setup(q, led)
    cap = q.config.reddit_stream_max_pages_per_poll
    tries, complete, t = 0, None, at(74)
    while t < at(74 + 72):
        clock = Clock(t)
        out, fake = poll(q, clock, _resume_answers(clock, cursor, "empty"), led=led)
        assert out.reason is None and len(fake.requests) <= cap
        tries += after_ids(fake).count(cursor)
        if complete is None and not out.poll.truncated:
            complete = out
        t += timedelta(hours=2)
    assert tries == 1 and complete is not None and complete.poll.oldest <= at(20)
    _settled_full(q, led, at(74 + 72), 3)


def test_dead_cursor_is_not_recreated_from_a_later_stored_stretch(q):
    """A later truncated poll of the same segment that stored the dead cursor again (as its stretch's cursor) does
    not revive it: the next poll that reaches that coverage pages fresh instead of resuming it."""
    led = ledger()
    cursor = _stale_cursor_setup(q, led)
    clock = Clock(at(74))
    poll(q, clock, _resume_answers(clock, cursor, "empty"), led=led)
    times = stream_times(at(72), span_h=3)
    record(rs.Poll("comments", at(74.5), times[0], times[-1], 100, 1, True, at(20), ((times[-1], times[0], cursor),)))
    clock = Clock(at(77))
    _, fake = poll(q, clock, _resume_answers(clock, cursor, "empty"), led=led)
    assert cursor not in after_ids(fake)


def test_poll_never_stores_a_dead_cursor_as_its_stretch_cursor(q):
    """A later poll whose own page happens to end at the dead cursor's entry (here cut by a page cap of 1) stores no
    cursor for that stretch, so the dead cursor is not re-created once its dead mark leaves the retention window."""
    led = ledger()
    cursor = _stale_cursor_setup(q, led)
    clock = Clock(at(74))
    poll(q, clock, _resume_answers(clock, cursor, "empty"), led=led)
    oldest = stream_times(at(72), span_h=3)[-1]
    page = atom([entry(rid("t1", w), w) for w in stream_times(at(76), span_h=3, count=400) if w >= oldest])
    out, fake = poll(with_cfg(q, reddit_stream_max_pages_per_poll=1), Clock(at(76)), ok(page), led=led)
    assert len(fake.requests) == 1 and out.poll.truncated is True and out.poll.oldest == oldest
    assert all(c != cursor for _, _, c in out.poll.spans())


def test_failed_resume_keeps_the_cursor_retriable_unlike_an_empty_resume(q):
    """A resumed page that FAILED (here a 503) is transient: the cursor is not marked dead and the next poll resumes
    it and reaches deeper, while an empty resumed page marks it dead (see above)."""
    led = ledger()
    cursor = _stale_cursor_setup(q, led)
    clock = Clock(at(74))
    out, fake = poll(q, clock, _resume_answers(clock, cursor, "error"), led=led)
    assert after_ids(fake) == [None, cursor] and out.reason is not None
    assert out.poll.dead == () and out.poll.truncated is True
    _not_settled(q, led, at(75))
    clock = Clock(at(76))
    nxt, fake = poll(q, clock, _resume_answers(clock, cursor, "live"), led=led)
    assert cursor in after_ids(fake) and after_ids(fake).index(cursor) <= 2  # reconnected, then resumed
    assert nxt.poll.dead == () and nxt.poll.oldest < at(70)
