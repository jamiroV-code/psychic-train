"""W8c AC2, AC3, AC9, AC24, AC25, AC28, AC37 (Reddit part), SPEC A.2 M1: the Reddit `search.rss` connector.

Fake HTTP clients only (httpx.MockTransport); no live Reddit request. Clocks are injected.
"""
from __future__ import annotations

import dataclasses
import logging
import random
import re
from datetime import date, datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from api.data import cache
from api.data.attention import density, pc_pace, reddit_items, store, web_evidence
from api.data.attention import reddit_web as rw
from api.data.attention import web_queries as wq

D = date(2026, 10, 26)
NOW = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
SALT = b"0123456789abcdef0123456789abcdef"
SECRET = "cookie=sessid-PLANTED-c00k1e&q=PLANTED"
MODULES = [Path(rw.__file__), Path(reddit_items.__file__), Path(rw.reddit_metrics.__file__)]


class Clock:
    def __init__(self, t: datetime):
        self.t = t

    def __call__(self) -> datetime:
        return self.t

    def sleep(self, s: float) -> None:
        assert s >= 0
        self.t += timedelta(seconds=s)


TITLE = "SOL ETH ADA BTC XRP news"  # the default entry mentions every coin the tests query


def entry(i: int, when: datetime, *, author: str | None = None, title: str = TITLE, sub: str = "CryptoCurrency",
          published: bool = True, kind: str = "t3") -> str:
    """One Atom entry; each entry has its own author unless one is given (the author cap is 3 per coin-day)."""
    author = author or f"u{i}"
    stamp = when.isoformat()
    pub = f"<published>{stamp}</published>" if published else ""
    return (f'<entry><author><name>/u/{author}</name><uri>https://www.reddit.com/user/{author}</uri></author>'
            f'<category term="{sub}" label="r/{sub}"/><content type="html">&lt;p&gt;body {i}&lt;/p&gt;</content>'
            f'<id>{kind}_{i:x}</id><link href="https://www.reddit.com/r/{sub}/comments/{i:x}/t/"/>'
            f'<updated>{stamp}</updated>{pub}<title>{title}</title></entry>')


def atom(entries: list[str]) -> bytes:
    return ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">'
            '<title>search results</title>' + "".join(entries) + "</feed>").encode()


def feed_at(times: list[datetime], **kw) -> bytes:
    return atom([entry(i + 1, t, **kw) for i, t in enumerate(times)])


def at(h: int, m: int = 0, day: date = D) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=h, minutes=m)


EXACT = feed_at([at(20), at(15), at(3), at(-2)])  # three in D, one before D: the feed reaches the window start
CANARY_FEED = feed_at([NOW - timedelta(minutes=10 * i) for i in range(100)])


def is_canary(request: httpx.Request) -> bool:
    return request.url.path.endswith("/new.rss")


class Fake:
    """Records every search request (and, given a clock, when it was sent); `respond(request)` returns the response.

    A canary request (`new.rss`) is answered by `canary` (a normal 100-entry feed by default) and recorded apart.
    """

    def __init__(self, respond, clock: Clock | None = None, canary=None):
        self.respond, self.clock, self.requests, self.sent_at = respond, clock, [], []
        self.canary_respond, self.canary = canary or ok(CANARY_FEED), []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if is_canary(request):
            self.canary.append(request)
            return self.canary_respond(request)
        self.requests.append(request)
        if self.clock is not None:
            self.sent_at.append(self.clock())
        return self.respond(request)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def ok(body: bytes, ctype: str = "application/atom+xml; charset=UTF-8"):
    return lambda req: httpx.Response(200, content=body, headers={"content-type": ctype})


def cfg(**kw) -> wq.CollectorConfig:
    return dataclasses.replace(wq.load().config, **kw)


@pytest.fixture
def q(attention_cache):
    """The committed query file; every test that uses it also runs on a throwaway cache root."""
    return wq.load()


def seed_canary(q, clock: Clock, respond=None) -> rw.CanaryOutcome:
    """Run today's canary through the real path, then drop the pace state so the next unit is not spaced."""
    pc_pace.state_path(rw.SOURCE).unlink(missing_ok=True)
    src = rw.reddit_source(q.config, degraded=True, clock=clock)
    out = rw.run_canary(Fake(ok(b""), canary=respond).client(), src, q)
    pc_pace.state_path(rw.SOURCE).unlink(missing_ok=True)
    return out


def unit(fake: Fake, q, clock: Clock, *, symbol="SOL", day=D, degraded=False, ledger=None, canary=True):
    """One unit on a fresh Reddit state (no pause or spacing carried over), after today's canary unless told not to."""
    if canary:
        seed_canary(q, clock)
    pc_pace.state_path(rw.SOURCE).unlink(missing_ok=True)
    src = rw.reddit_source(q.config, degraded=degraded, clock=clock)
    return rw.run_search_unit(fake.client(), src, q, symbol=symbol, day=day, ledger=ledger), src


def count(entries_body: bytes, *, symbol="SOL", limit=rw.SEARCH_LIMIT, canary_ok=True, searched_from=None,
          sample_min=10, q=None):
    """`count_day` for D with the committed query file's terms for `symbol`; returns (result, reason, tally)."""
    q = q or wq.load()
    return rw.count_day(D, rw.parse_feed(entries_body, rw.ephemeral_hasher()),
                        coin=rw.reddit_metrics.coin_term(q, symbol), sample_min=sample_min,
                        author_cap=q.config.reddit_author_cap, limit=limit, canary_ok=canary_ok,
                        searched_from=searched_from)


# --- parser and A.2 counting ---

def test_parse_atom_entries_with_updated_timestamps():
    both = rw.parse_feed(feed_at([at(12)]))
    (e,) = both
    assert e.id == "t3_1" and e.created == at(12) and e.updated == at(12) and e.subreddit == "CryptoCurrency"
    assert TITLE in e.text and "body 1" in e.text and "<p>" not in e.text
    assert e.author_hash is None  # no hasher given: the username is dropped at the parser
    only_updated = rw.parse_feed(atom([entry(2, at(7), published=False)]))
    assert only_updated[0].created == at(7)
    offset = rw.parse_feed(atom([entry(3, at(7)).replace(at(7).isoformat(), "2026-10-26T09:00:00+02:00")]))
    assert offset[0].created == at(7) and offset[0].created.tzinfo == timezone.utc


def test_exact_count_when_feed_reaches_window_start():
    result, reason, _ = count(EXACT)
    assert reason is None and result.value == 3 and not result.capped and result.n == 3
    full, why, _ = count(EXACT, limit=4, canary_ok=False)  # a feed filled to the limit needs no canary
    assert why is None and full.value == 3 and not full.capped
    zero, _, _ = count(feed_at([at(30), at(-5)]))
    assert zero.value == 0 and not zero.capped  # exact zero; the AC3 zero rule decides at commit time


def test_feed_capped_uses_density_over_covered_span():
    times = [at(h) for h in range(23, 11, -1)]  # 12 entries, 23:00 .. 12:00, no entry before D, feed at the limit
    result, reason, _ = count(feed_at(times), limit=12)
    assert reason is None and result.capped and not result.pagecap
    assert result.n == 12 and result.span_hours == pytest.approx(12.0) and result.value == pytest.approx(24.0)
    late = [at(23, 59 - m) for m in range(10)]  # ten entries in the last 10 minutes: span floor 0.25 h
    floor, _, _ = count(feed_at(late), limit=10)
    assert floor.span_hours == pytest.approx(0.25) and floor.value == pytest.approx(960.0)


def test_day_not_reached_is_missing():
    result, reason, _ = count(feed_at([at(24 + h) for h in range(5)]), limit=5)
    assert result is None and reason == "day_not_reached"
    empty, why, _ = count(atom([]), canary_ok=False)
    assert empty is None and why == "no_canary"


def test_entries_after_window_end_ignored():
    times = [at(24 + h) for h in range(5)] + [at(12), at(1), at(-1)]
    result, _, _ = count(feed_at(times))
    assert result.value == 2 and not result.capped
    edge, _, _ = count(feed_at([at(24), at(0), at(-1)]))
    assert edge.value == 1  # D+1 00:00 is outside, D 00:00 is inside


def test_below_reddit_sample_min_is_missing():
    nine = [at(23 - h) for h in range(9)]
    result, reason, _ = count(feed_at(nine), limit=9)
    assert result is None and reason == "below_sample_min"
    ten, _, _ = count(feed_at(nine + [at(10)]), limit=10)
    assert ten is not None and ten.capped


def test_malformed_entry_is_layout_changed():
    bad = atom(["<entry><title>x</title></entry>"])
    with pytest.raises(rw.pa.LayoutChanged):
        rw.parse_feed(bad)


# --- URL, terms, user agent ---

def test_search_rss_url_form_sort_new_t_week_and_subreddit_set(q):
    url = rw.search_url(["CryptoCurrency", "CryptoMarkets"], ["SOL", "Solana"], "week")
    assert url == ("https://www.reddit.com/r/CryptoCurrency+CryptoMarkets/search.rss"
                   "?q=%22SOL%22%20OR%20%22Solana%22&restrict_sr=1&sort=new&t=week&limit=100")
    assert q.config.reddit_search_time_filter == "week"
    fake = Fake(ok(EXACT))
    unit(fake, q, Clock(NOW))
    (req,) = fake.requests
    parts = urlsplit(str(req.url))
    assert parts.scheme == "https" and parts.netloc == "www.reddit.com"
    assert parts.path == "/r/" + "+".join(q.subreddits) + "/search.rss"
    qs = parse_qs(parts.query)
    assert qs["sort"] == ["new"] and qs["restrict_sr"] == ["1"] and qs["t"] == ["week"] and qs["q"] == ['"SOL" OR "Solana"']


def test_search_request_uses_t_week_by_config(q):
    assert q.config.reddit_search_time_filter == "week"
    fake = Fake(ok(EXACT))
    unit(fake, q, Clock(NOW))
    assert parse_qs(urlsplit(str(fake.requests[0].url)).query)["t"] == ["week"]
    block = {k: v for k, v in q.config.as_dict().items()}
    for bad in ("fortnight", "", 7, None):
        with pytest.raises(wq.QueriesError):
            wq.validate_config({**block, "reddit_search_time_filter": bad})


def test_name_only_coin_searches_by_name_and_plain_coin_by_ticker_and_name(q):
    assert rw.search_terms(q, "LINK") == ["Chainlink"]
    assert rw.search_terms(q, "SOL") == ["SOL", "Solana"]
    assert rw.search_terms(q, "XRP") == ["XRP"]
    assert rw.search_terms(q, "NOPE") is None


def test_single_honest_user_agent_constant(q):
    fake = Fake(ok(EXACT))
    unit(fake, q, Clock(NOW))
    assert fake.requests[0].headers["user-agent"] == wq.HONEST_USER_AGENT == rw.USER_AGENT
    for path in MODULES:
        text = path.read_text(encoding="utf-8")
        assert "HONEST_USER_AGENT =" not in text and not re.search(r"USER_AGENT\s*=\s*['\"]", text), path.name
        assert not re.search(r"['\"]user-agent['\"]\s*:\s*['\"]", text, re.IGNORECASE), path.name


def test_no_browser_user_agent_string_in_module():
    browser = re.compile(r"Mozilla/|AppleWebKit|Chrome/\d|Safari/\d|Gecko/|Firefox/|Edg/", re.IGNORECASE)
    for path in MODULES:
        assert not browser.search(path.read_text(encoding="utf-8")), path.name


def test_no_json_endpoint_url_in_module(q):
    endpoint = re.compile(r"reddit\.com\S*\.json|search\.json|/\.json|\.json\?|oauth\.reddit|api\.reddit|/api/v1/")
    for path in MODULES:
        assert not endpoint.search(path.read_text(encoding="utf-8")), path.name
    fake = Fake(ok(EXACT))
    unit(fake, q, Clock(NOW))
    assert urlsplit(str(fake.requests[0].url)).path.endswith("/search.rss")


# --- blocks and pauses ---

def _assert_paused_rest_of_day(src, clock: Clock):
    assert src.is_paused()
    clock.t = datetime(2026, 10, 27, 23, 59, tzinfo=timezone.utc)
    assert src.is_paused()
    clock.t = datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc)
    assert not src.is_paused()


def test_html_block_page_is_not_parsed_and_pauses(q):
    page = b"<html><head><title>Blocked</title></head><body>whoa there</body></html>"
    with pytest.raises(rw.FeedRejected):
        rw.parse_feed(page)
    fake, clock = Fake(ok(page, "text/html; charset=utf-8")), Clock(NOW)
    out, src = unit(fake, q, clock)
    assert out.result is None and out.reason == "reddit_blocked" and src.pause_reason() == "reddit_blocked"
    clock.sleep(600)
    again = rw.run_search_unit(fake.client(), src, q, symbol="ETH", day=D)
    assert again.reason == "paused" and len(fake.requests) == 1
    _assert_paused_rest_of_day(src, clock)
    # an Atom body served as HTML, or a non-Atom XML root, is a block too
    assert unit(Fake(ok(EXACT, "text/html")), q, Clock(NOW))[0].reason == "reddit_blocked"
    rss = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    with pytest.raises(rw.FeedRejected):
        rw.parse_feed(rss)


@pytest.mark.parametrize("status, reason", [(403, "reddit_blocked")])
def test_403_pauses_rest_of_day_no_retry(q, status, reason):
    fake, clock = Fake(lambda req: httpx.Response(status, content=b"blocked")), Clock(NOW)
    out, src = unit(fake, q, clock)
    assert out.reason == reason and out.status == status and len(fake.requests) == 1
    assert src.pause_reason() == reason
    _assert_paused_rest_of_day(src, clock)


def test_429_pauses_rest_of_day_no_retry(q):
    fake, clock = Fake(lambda req: httpx.Response(429, content=b"slow down")), Clock(NOW)
    out, src = unit(fake, q, clock)
    assert out.reason == "rate_limited" and len(fake.requests) == 1 and src.pause_reason() == "rate_limited"
    res = rw.run_pass(fake.client(), src, q, queue=[("ETH", D), ("ADA", D)], clock=clock, sleep=clock.sleep,
                      rng=random.Random(1), degraded=True)
    assert len(fake.requests) == 1 and res.stop == "paused"
    _assert_paused_rest_of_day(src, clock)


def test_redirect_is_not_followed_and_counts_as_block(q):
    fake = Fake(lambda req: httpx.Response(302, headers={"location": "https://www.reddit.com/login"}))
    out, src = unit(fake, q, Clock(NOW))
    assert out.reason == "reddit_blocked" and len(fake.requests) == 1 and src.is_paused()


def test_5xx_and_network_errors_are_missing_without_pause(q):
    out, src = unit(Fake(lambda req: httpx.Response(503)), q, Clock(NOW))
    assert out.reason == "offline" and out.result is None and not src.is_paused()

    def boom(req):
        raise httpx.ConnectError("down")
    out2, src2 = unit(Fake(boom), q, Clock(NOW))
    assert out2.reason == "offline" and not src2.is_paused()


def test_feed_with_doctype_or_entity_rejected(q):
    doctype = b'<?xml version="1.0"?><!DOCTYPE feed [<!ENTITY x "SOL">]><feed xmlns="http://www.w3.org/2005/Atom"/>'
    entity = b'<?xml version="1.0"?><!ENTITY x "y"><feed xmlns="http://www.w3.org/2005/Atom"/>'
    lower = b'<?xml version="1.0"?><!doctype feed><feed xmlns="http://www.w3.org/2005/Atom"/>'
    for body in (doctype, entity, lower):
        with pytest.raises(rw.FeedRejected):
            rw.parse_feed(body)
    out, src = unit(Fake(ok(doctype)), q, Clock(NOW))
    assert out.reason == "reddit_blocked" and src.is_paused()


def test_oversize_body_rejected(q, monkeypatch):
    monkeypatch.setattr(rw, "MAX_BODY_BYTES", 2000)
    big = feed_at([at(23 - (h % 24)) for h in range(40)])
    assert len(big) > 2000
    with pytest.raises(rw.FeedRejected):
        rw.parse_feed(big)
    out, src = unit(Fake(ok(big)), q, Clock(NOW))
    assert out.reason == "reddit_blocked" and src.is_paused()
    assert rw.parse_feed(feed_at([at(1)]))  # a small body still parses


def test_logs_class_and_status_only_with_planted_secrets(q, caplog):
    caplog.set_level(logging.DEBUG)

    def boom(req):
        raise httpx.ConnectError(SECRET)
    unit(Fake(boom), q, Clock(NOW))
    unit(Fake(lambda req: httpx.Response(403, content=SECRET.encode(), headers={"x-secret": SECRET})), q, Clock(NOW))
    unit(Fake(ok(b"<html>" + SECRET.encode() + b"</html>", "text/html")), q, Clock(NOW))
    text = caplog.text
    assert "PLANTED" not in text and "cookie" not in text and "reddit.com" not in text and "Solana" not in text
    assert "Offline status=none" in text and "RedditBlocked status=403" in text


# --- coins, completed days, stores ---

def test_ambiguity_list_skips_coin(q, attention_cache):
    assert rw.search_terms(q, "SKY") is None and "SKY" in q.ambiguous["reddit_web"]
    fake, clock = Fake(ok(EXACT)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=False, clock=clock)
    res = rw.run_pass(fake.client(), src, q, queue=[("SKY", D)], clock=clock, sleep=clock.sleep,
                      rng=random.Random(1), degraded=False)
    assert fake.requests == [] and fake.canary == [] and res.requests == 0
    assert rw.read_completeness(D)["reasons"] == {"ambiguous": 1}
    assert store.read_points("reddit_web", "SKY") == []


def test_value_written_only_for_completed_day(q, attention_cache):
    today = NOW.date()
    fake, clock = Fake(ok(EXACT)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=False, clock=clock)
    out = rw.run_search_unit(fake.client(), src, q, symbol="SOL", day=today)
    assert out.reason == "day_not_complete" and fake.requests == [] and src.used == 0
    rw.run_pass(fake.client(), src, q, queue=[("SOL", today)], clock=clock, sleep=clock.sleep,
                rng=random.Random(1), degraded=False)
    assert store.read_points("reddit_web", "SOL") == [] and fake.requests == []
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D)], clock=clock, sleep=clock.sleep,
                rng=random.Random(1), degraded=False)
    assert store.read_points("reddit_web", "SOL") == [(D, 3.0)]


def test_writes_reddit_web_store_not_reddit(q, attention_cache):
    fake, clock = Fake(ok(EXACT)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=False, clock=clock)
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D)], clock=clock, sleep=clock.sleep,
                rng=random.Random(1), degraded=False)
    assert rw.SOURCE == "reddit_web"
    assert store.read_points("reddit_web", "SOL") == [(D, 3.0)]
    assert store.read_points("reddit", "SOL") == []
    assert not (cache.CACHE_ROOT / "attention" / "reddit").exists()


def test_evidence_row_written(q, attention_cache):
    times = [at(23, 59) - timedelta(minutes=6 * i) for i in range(100)]  # a full feed, oldest D 14:05
    fake, clock = Fake(ok(feed_at(times))), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=False, clock=clock)
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D)], clock=clock, sleep=clock.sleep,
                rng=random.Random(1), degraded=False)
    row = web_evidence.read_rows("reddit_web", "SOL")[D]
    span = (at(24) - at(14, 5)).total_seconds() / 3600
    assert row.value == pytest.approx(2400 / span) and row.n == 100 and row.capped and not row.pagecap
    assert row.span_hours == pytest.approx(span) and row.method == rw.METHOD and not row.backfilled
    assert row.collected_at >= NOW


def test_unconfirmed_zero_is_missing_not_zero(q, attention_cache):
    fake, clock = Fake(ok(feed_at([at(30), at(-5)]))), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=False, clock=clock)
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D)], clock=clock, sleep=clock.sleep,
                rng=random.Random(1), degraded=False)
    # no trailing median yet: a zero is not confirmed (AC3), the coin-day stays missing
    assert store.read_points("reddit_web", "SOL") == []
    assert rw.read_completeness(D)["reasons"] == {"zero_unconfirmed": 1}


def test_search_unit_writes_ledger_rows_with_matched_coins(q, attention_cache):
    feed = atom([entry(1, at(12), title="SOL and Ethereum", author="PlantedUser"),
                 entry(2, at(11), title="LINK only"), entry(3, at(-3), title="Chainlink up")])
    led = reddit_items.Ledger(reddit_items.AuthorHasher(SALT))
    unit(Fake(ok(feed)), q, Clock(NOW), ledger=led)
    rows = led.read_day(D)
    assert rows["t3_1"].coins == ("ETH", "SOL") and rows["t3_1"].feed_kind == "search"
    assert rows["t3_2"].coins == ()  # bare LINK is name_only: no match
    assert led.read_day(D - timedelta(days=1))["t3_3"].coins == ("LINK",)
    assert rows["t3_1"].author_hash == reddit_items.AuthorHasher(SALT)("PlantedUser")
    files = "".join(p.read_text(encoding="utf-8") for p in cache.CACHE_ROOT.rglob("*.json"))
    assert "planteduser" not in files.lower()


# --- budget and pacing ---

def test_budget_150_requests_per_day(q, attention_cache):
    fake, clock = Fake(ok(EXACT)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=True, clock=clock)
    assert src.effective_budget() == 150
    syms = [s for s in sorted(q.coins) if rw.search_terms(q, s)]
    queue = [(s, D - timedelta(days=b)) for b in range(3) for s in syms][:151]
    res = rw.run_pass(fake.client(), src, q, queue=queue, clock=clock, sleep=clock.sleep, rng=random.Random(2),
                      degraded=True, n_coins=len(syms))
    # the canary is one request of the same budget
    assert len(fake.canary) == res.canary_requests == 1
    assert len(fake.requests) == res.requests == 149 and res.stop == "budget_spent" and src.used == 150
    assert any(rw.read_completeness(d)["budget_cut"] for d in {d for _, d in queue})


def test_budget_250_baseline_and_150_degraded(q, attention_cache):
    c = q.config
    assert c.reddit_daily_request_budget == 250 and c.reddit_degraded_request_budget == 150
    assert rw.daily_budget(c, degraded=False) == 250 and rw.daily_budget(c, degraded=True) == 150
    clock = Clock(NOW)
    assert rw.reddit_source(c, degraded=True, clock=clock).effective_budget() == 150
    # the same UTC day switched back to the 24/7 baseline gets the baseline budget, not a stale 150
    assert rw.reddit_source(c, degraded=False, clock=clock).effective_budget() == 250
    with pytest.raises(wq.QueriesError):
        wq.validate_config({**c.as_dict(), "reddit_degraded_request_budget": 300})


def test_search_requests_spread_over_day_baseline(q, attention_cache):
    c = q.config
    start = datetime(2026, 10, 27, 13, 17, tzinfo=timezone.utc)
    times = pc_pace.plan_run(rw.search_trickle(c, 75, degraded=False, rng=random.Random(4)), start=start,
                             stop=start + timedelta(hours=24))
    gaps = [(b - a).total_seconds() for a, b in pairwise(times)]
    assert min(gaps) >= 86400 / 75 and len(times) >= 74 and (times[-1] - times[0]) >= timedelta(hours=23)
    few = pc_pace.plan_run(rw.search_trickle(c, 3, degraded=False, rng=random.Random(4)), start=start,
                           stop=start + timedelta(hours=24))
    assert min((b - a).total_seconds() for a, b in pairwise(few)) >= 28800
    fast = pc_pace.plan_run(rw.search_trickle(c, 75, degraded=True, rng=random.Random(4)), start=start,
                            stop=start + timedelta(hours=1))
    assert all(60 <= (b - a).total_seconds() <= 120 for a, b in pairwise(fast)) and len(fast) >= 29
    # many coins: the configured 60-120 s stays the floor
    crowd = pc_pace.plan_run(rw.search_trickle(c, 5000, degraded=False, rng=random.Random(4)), start=start,
                             stop=start + timedelta(hours=1))
    assert min((b - a).total_seconds() for a, b in pairwise(crowd)) >= 60
    # the pass itself keeps the spread: three coins, a sent request every 8 h or more
    clock = Clock(start)
    fake = Fake(ok(EXACT), clock)
    src = rw.reddit_source(c, degraded=False, clock=clock)
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D), ("ETH", D), ("ADA", D)], clock=clock, sleep=clock.sleep,
                rng=random.Random(5), degraded=False)
    assert len(fake.sent_at) == 3 and all((b - a).total_seconds() >= 28800 for a, b in pairwise(fake.sent_at))


def test_search_completeness_written_attempted_fetched_missing_reasons(q, attention_cache):
    feeds = {"SOL": lambda r: httpx.Response(200, content=EXACT),
             "ETH": lambda r: httpx.Response(200, content=feed_at([at(30)])),
             "ADA": lambda r: httpx.Response(200, content=feed_at([at(23)])),
             "BTC": lambda r: httpx.Response(503)}

    def respond(req):
        term = parse_qs(urlsplit(str(req.url)).query)["q"][0].split('"')[1]
        return feeds[term](req)
    fake, clock = Fake(respond), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=False, clock=clock)
    res = rw.run_pass(fake.client(), src, q, queue=[("SOL", D), ("ETH", D), ("ADA", D), ("BTC", D), ("SKY", D)],
                      clock=clock, sleep=clock.sleep, rng=random.Random(1), degraded=False)
    assert res.requests == 4
    c = rw.read_completeness(D)
    # ETH: a short feed with nothing in D is an exact 0, which needs a trailing median; ADA: a short exact 1
    assert c["attempted"] == 4 and c["fetched"] == 2 and c["missing"] == 3
    assert c["reasons"] == {"zero_unconfirmed": 1, "offline": 1, "ambiguous": 1}
    assert c["requests"] == 4 and c["capped"] == 0 and c["budget_cut"] is False
    assert c["newest_entry_at"] == at(30).isoformat()
    assert set(c["coins"]) == {"SOL", "ETH", "ADA", "BTC", "SKY"}
    for sym in ("SOL", "ETH", "ADA", "BTC"):
        assert datetime.fromisoformat(c["coins"][sym]["collected_at"]) >= NOW
    assert c["coins"]["SOL"] == {**c["coins"]["SOL"], "reason": "fetched", "entries": 4, "value": 3.0}
    # a later retry of a missing coin replaces its record; the counts follow
    feeds["BTC"] = lambda r: httpx.Response(200, content=EXACT)
    clock.sleep(3600)
    rw.run_pass(fake.client(), src, q, queue=[("BTC", D)], clock=clock, sleep=clock.sleep, rng=random.Random(1),
                degraded=False)
    c2 = rw.read_completeness(D)
    assert c2["fetched"] == 3 and c2["missing"] == 2 and "offline" not in c2["reasons"] and c2["requests"] == 5


def test_completeness_marks_budget_cut_and_pause_for_the_rest(q, attention_cache):
    fake, clock = Fake(lambda req: httpx.Response(429)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=False, clock=clock)
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D), ("ETH", D)], clock=clock, sleep=clock.sleep,
                rng=random.Random(1), degraded=False)
    c = rw.read_completeness(D)
    assert c["reasons"] == {"rate_limited": 2} and c["attempted"] == 1


def test_no_fixed_utc_hour_assumption_start_times_0030_0900_1700_2300(q, tmp_path, monkeypatch):
    busy_every = timedelta(minutes=1)

    def respond(req):
        now = clock()
        term = parse_qs(urlsplit(str(req.url)).query)["q"][0].split('"')[1]
        if term == "SOL":  # busy: 100 entries one minute apart, ending now
            return httpx.Response(200, content=feed_at([now - busy_every * (i + 1) for i in range(100)]))
        # quiet: one entry a day, so the feed always reaches back past yesterday
        return httpx.Response(200, content=feed_at([now - timedelta(days=i, hours=1) for i in range(5)]))

    for hh, mm in ((0, 30), (9, 0), (17, 0), (23, 0)):
        monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path / f"run{hh:02d}{mm:02d}")
        start = datetime(2026, 10, 27, tzinfo=timezone.utc) + timedelta(hours=hh, minutes=mm)
        clock = Clock(start)
        fake = Fake(respond, clock)
        sent = fake.sent_at
        src = rw.reddit_source(q.config, degraded=True, clock=clock)
        res = rw.run_pass(fake.client(), src, q, queue=[("SOL", D), ("ETH", D)], clock=clock, sleep=clock.sleep,
                          rng=random.Random(hh), degraded=True, stop_at=start + timedelta(hours=1))
        # the canary goes first, then the searches at the degraded 60-120 s
        assert res.requests == 2 and len(fake.canary) == 1
        assert sent[0] - start <= timedelta(seconds=pc_pace.BEHIND_DELAY_S + 120)
        assert 60 <= (sent[1] - sent[0]).total_seconds() <= 120
        c = rw.read_completeness(D)
        assert c["coins"]["ETH"]["reason"] == "fetched" and store.read_points("reddit_web", "ETH") == [(D, 1.0)]
        assert all("collected_at" in c["coins"][s] for s in ("SOL", "ETH"))
        sol = store.read_points("reddit_web", "SOL")
        if (hh, mm) == (0, 30):
            assert c["coins"]["SOL"]["reason"] == "fetched" and web_evidence.read_rows("reddit_web", "SOL")[D].capped
        else:
            assert sol == [] and c["coins"]["SOL"]["reason"] == "day_not_reached"  # missing, never 0


def test_host_stop_ends_pass_and_leaves_the_rest_queued(q, attention_cache):
    fake, clock = Fake(ok(EXACT)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=True, clock=clock)
    queue = [(s, D) for s in ("SOL", "ETH", "ADA", "BTC", "XRP")]
    res = rw.run_pass(fake.client(), src, q, queue=queue, clock=clock, sleep=clock.sleep, rng=random.Random(3),
                      degraded=True, stop_at=NOW + timedelta(seconds=150))
    assert res.stop == "host_stopped" and 1 <= res.requests <= 3
    assert clock() <= NOW + timedelta(seconds=150)
    assert set(rw.read_completeness(D)["coins"]) == {s for s, _ in queue[:res.requests]}


def test_min_spacing_kept_across_a_restart(q, attention_cache):
    fake, clock = Fake(ok(EXACT)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=True, clock=clock)
    rw.run_search_unit(fake.client(), src, q, symbol="SOL", day=D)
    clock.sleep(30)
    again = rw.reddit_source(q.config, degraded=True, clock=clock)
    assert rw.run_search_unit(fake.client(), again, q, symbol="ETH", day=D).reason == "too_early"
    assert len(fake.requests) == 1


def test_entry_exactly_at_window_start_does_not_prove_coverage():
    result, reason, _ = count(feed_at([at(12), at(0)]), limit=2)
    assert result is None and reason == "below_sample_min"  # the feed must reach strictly before D 00:00


def test_created_time_is_published_not_a_later_edit():
    edited = entry(1, at(-1)).replace(f"<updated>{at(-1).isoformat()}</updated>", f"<updated>{at(5).isoformat()}</updated>")
    (e,) = rw.parse_feed(atom([edited]))
    assert e.created == at(-1) and e.updated == at(5)


def test_stream_stops_reading_above_the_size_cap(monkeypatch):
    monkeypatch.setattr(rw, "MAX_BODY_BYTES", 2000)
    big = feed_at([at(1)] * 40)
    with pytest.raises(rw.FeedRejected):
        rw.fetch_feed(Fake(ok(big)).client(), "https://www.reddit.com/r/x/search.rss")


# --- T211 decisions: matched value (Q-b), cashtag_only (Q-c), short feeds and the canary (Q-d), zero (Q-e) ---

def test_value_counts_matched_entries_then_author_cap_not_raw_results(q, attention_cache):
    ents = [entry(1, at(20), title="Solana breaks out"), entry(2, at(19), title="$sol to the moon"),
            entry(3, at(18), title="solar panels on sale"),  # a fuzzy search hit that does not mention SOL
            entry(4, at(17), title="Sole trader tips")]
    ents += [entry(10 + i, at(10, i), title="SOL again", author="spammer") for i in range(5)]
    ents.append(entry(30, at(-1)))
    fake, clock = Fake(ok(atom(ents))), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=False, clock=clock)
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D)], clock=clock, sleep=clock.sleep,
                rng=random.Random(1), degraded=False)
    assert store.read_points("reddit_web", "SOL") == [(D, 5.0)]  # 2 plus the spammer capped at 3
    rec = rw.read_completeness(D)["coins"]["SOL"]
    assert rec["entries"] == 10 and rec["in_window"] == 9 and rec["matched"] == 7 and rec["counted"] == 5
    assert rec["excluded"] == {"no_match": 2, "author_cap": 2}


def test_name_only_coin_value_counts_full_name_or_cashtag_only():
    body = atom([entry(1, at(20), title="LINK in bio"), entry(2, at(19), title="Chainlink oracle news"),
                 entry(3, at(18), title="$LINK pumps"), entry(4, at(-1), title="old")])
    result, reason, tally = count(body, symbol="LINK")
    assert reason is None and result.value == 2
    assert tally.matched == 2 and tally.excluded == {"no_match": 1, "author_cap": 0}


def test_cashtag_only_coin_value_ignores_bare_ticker():
    body = atom([entry(1, at(20), title="ASTER moon"), entry(2, at(19), title="an aster flower"),
                 entry(3, at(18), title="bought $ASTER"), entry(4, at(17), title="ATOM staking"),
                 entry(5, at(16), title="Cosmos hub upgrade"), entry(6, at(15), title="$atom"),
                 entry(7, at(14), title="SOL pump"), entry(8, at(-1), title="old")])
    assert count(body, symbol="ASTER")[0].value == 1  # only the cashtag: the name equals the ticker
    assert count(body, symbol="ATOM")[0].value == 2  # the full name or the cashtag, never the bare ticker
    assert count(body, symbol="SOL")[0].value == 1  # a normal coin keeps the bare upper-case ticker


def test_short_feed_all_inside_window_is_exact_only_with_canary():
    body = feed_at([at(20), at(9)])  # 2 entries, fewer than the limit: the search returned all it had
    result, reason, _ = count(body, searched_from=at(-5 * 24))
    assert reason is None and result.value == 2 and not result.capped
    missing, why, _ = count(body, canary_ok=False)
    assert missing is None and why == "no_canary"


def test_short_feed_not_reaching_window_start_is_window_not_reached_or_density():
    body = feed_at([at(20), at(9)])
    result, reason, _ = count(body, searched_from=at(10))  # e.g. t=day sent at D+1 10:00
    assert result is None and reason == "window_not_reached"
    twelve = feed_at([at(23) - timedelta(minutes=30 * i) for i in range(12)])  # 23:00 .. 17:30
    capped, why, _ = count(twelve, searched_from=at(17))
    assert why is None and capped.capped and capped.value == pytest.approx(24 * 12 / 6.5)


def test_feed_capped_at_limit_is_density_without_canary():
    times = [at(23, 59) - timedelta(minutes=6 * i) for i in range(100)]
    result, reason, _ = count(feed_at(times), canary_ok=False)
    assert reason is None and result.capped and result.n == 100


def test_time_filter_span_sets_the_search_start():
    assert rw.searched_from(NOW, "day") == NOW - timedelta(days=1)
    assert rw.searched_from(NOW, "week") == NOW - timedelta(days=7)
    assert rw.searched_from(NOW, "all") is None


def test_valid_empty_feed_zero_needs_canary_and_trailing_median(q, attention_cache):
    empty = atom([])
    assert count(empty, canary_ok=False)[1] == "no_canary"
    assert count(empty, searched_from=at(10))[1] == "window_not_reached"
    assert count(empty)[0].value == 0
    clock = Clock(NOW)
    fake = Fake(ok(empty))
    src = rw.reddit_source(q.config, degraded=True, clock=clock)
    for b in range(1, 4):  # ETH has history (median 2); SOL has none
        web_evidence.commit_day(rw.SOURCE, "ETH", D - timedelta(days=b), density.DayResult(2.0, 2, 24.0, False, False),
                                canary_ok=True, trailing_median=None, now=NOW, method=rw.METHOD)
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D), ("ETH", D)], clock=clock, sleep=clock.sleep,
                rng=random.Random(1), degraded=True)
    c = rw.read_completeness(D)["coins"]
    assert c["SOL"]["reason"] == "zero_unconfirmed" and store.read_points("reddit_web", "SOL") == []
    assert c["ETH"]["reason"] == "fetched" and (D, 0.0) in store.read_points("reddit_web", "ETH")


def test_200_with_html_or_empty_body_is_a_block(q):
    for body, ctype in ((b"", "application/atom+xml"), (b"<html><body>x</body></html>", "application/atom+xml")):
        out, src = unit(Fake(ok(body, ctype)), q, Clock(NOW))
        assert out.reason == "reddit_blocked" and src.is_paused()


def test_failed_canary_keeps_short_feed_missing_no_canary(q, attention_cache):
    fake, clock = Fake(ok(EXACT), canary=lambda r: httpx.Response(503)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=True, clock=clock)
    res = rw.run_pass(fake.client(), src, q, queue=[("SOL", D)], clock=clock, sleep=clock.sleep,
                      rng=random.Random(1), degraded=True)
    assert res.canary_requests == 1 and res.requests == 1 and src.used == 2
    c = rw.read_completeness(D)
    assert c["coins"]["SOL"]["reason"] == "no_canary" and store.read_points("reddit_web", "SOL") == []
    assert c["canary"]["ok"] is False and c["canary"]["requests"] == 1 and c["canary"]["reason"] == "offline"


def test_short_canary_feed_or_yesterdays_canary_does_not_count(q, attention_cache):
    short = seed_canary(q, Clock(NOW), ok(feed_at([NOW] * (rw.CANARY_MIN_ENTRIES - 1))))
    assert not short.ok and short.reason == "canary_short" and not rw.canary_ok(NOW)
    rw.canary_path(NOW.date()).unlink()
    assert seed_canary(q, Clock(NOW - timedelta(days=1))).ok
    out, _ = unit(Fake(ok(EXACT)), q, Clock(NOW), canary=False)
    assert out.reason == "no_canary" and out.result is None
    assert seed_canary(q, Clock(NOW)).ok and rw.canary_ok(NOW)


def test_canary_counted_in_budget_and_evidence_once_a_day(q, attention_cache):
    fake, clock = Fake(ok(EXACT)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=True, clock=clock)
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D)], clock=clock, sleep=clock.sleep, rng=random.Random(1),
                degraded=True)
    assert len(fake.canary) == 1 and src.used == 2 and str(fake.canary[0].url) == rw.canary_url()
    assert fake.canary[0].headers["user-agent"] == wq.HONEST_USER_AGENT
    c = rw.read_completeness(D)
    assert c["canary"] == {**c["canary"], "ok": True, "requests": 1, "entries": 100, "status": 200}
    assert store.read_points("reddit_web", "SOL") == [(D, 3.0)]
    clock.sleep(3600)
    rw.run_pass(fake.client(), src, q, queue=[("ETH", D)], clock=clock, sleep=clock.sleep, rng=random.Random(1),
                degraded=True)
    assert len(fake.canary) == 1 and src.used == 3  # one canary per UTC day


def test_canary_block_pauses_and_sends_no_search(q, attention_cache):
    fake, clock = Fake(ok(EXACT), canary=lambda r: httpx.Response(403)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=True, clock=clock)
    res = rw.run_pass(fake.client(), src, q, queue=[("SOL", D), ("ETH", D)], clock=clock, sleep=clock.sleep,
                      rng=random.Random(1), degraded=True)
    assert res.stop == "paused" and fake.requests == [] and src.pause_reason() == "reddit_blocked"


# --- kept deviations: the budget reset and the httpx log filter ---

def test_reddit_source_resets_a_stale_clamped_budget_on_disk(q, attention_cache):
    clock = Clock(NOW)
    rw.reddit_source(q.config, degraded=True, clock=clock).spend(1)
    src = rw.reddit_source(q.config, degraded=False, clock=clock)
    assert src.effective_budget() == 250 and src.used == 1  # the reset keeps the day's count
    plain = pc_pace.PcSource(rw.SOURCE, configured_budget=250, floor=1, adaptive=False, clock=clock)
    assert plain.effective_budget() == 250  # written through to the state file, not only held in memory
    assert rw.reddit_source(q.config, degraded=True, clock=clock).effective_budget() == 150


def test_planted_secret_url_query_never_reaches_a_log_record(q, caplog):
    caplog.set_level(logging.DEBUG)
    rw.fetch_feed(Fake(ok(EXACT)).client(), "https://www.reddit.com/r/x/search.rss?q=PLANTED&" + SECRET)
    unit(Fake(ok(EXACT)), q, Clock(NOW))
    httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))).get("https://example.org/ok")
    assert any(r.name == "httpx" for r in caplog.records)  # the httpx request lines are live and captured
    for rec in caplog.records:
        text = rec.getMessage()
        assert "PLANTED" not in text and "cookie" not in text and "reddit.com" not in text, rec.name


# --- boundary tests from the T211 mutation check ---

def test_canary_success_stays_for_the_day_after_a_later_failure(q, attention_cache):
    assert seed_canary(q, Clock(NOW)).ok
    later = seed_canary(q, Clock(NOW + timedelta(hours=1)), lambda r: httpx.Response(503))
    assert not later.ok and rw.canary_ok(NOW + timedelta(hours=1))
    assert rw.read_canary(NOW.date())["requests"] == 2


def test_failed_canary_is_tried_once_per_pass_and_day(q, attention_cache):
    fake, clock = Fake(ok(EXACT), canary=lambda r: httpx.Response(503)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=True, clock=clock)
    res = rw.run_pass(fake.client(), src, q, queue=[("SOL", D), ("ETH", D), ("ADA", D)], clock=clock,
                      sleep=clock.sleep, rng=random.Random(1), degraded=True)
    assert res.canary_requests == len(fake.canary) == 1 and res.requests == 3


def test_full_feed_zero_without_canary_is_not_stored(q, attention_cache):
    times = [at(20)] + [at(-1) - timedelta(minutes=i) for i in range(99)]  # full, reaches back, none in D match
    body = atom([entry(i + 1, t, title="nothing relevant") for i, t in enumerate(times)])
    for b in range(1, 4):
        web_evidence.commit_day(rw.SOURCE, "SOL", D - timedelta(days=b), density.DayResult(2.0, 2, 24.0, False, False),
                                canary_ok=True, trailing_median=None, now=NOW, method=rw.METHOD)
    fake, clock = Fake(ok(body), canary=lambda r: httpx.Response(503)), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=True, clock=clock)
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D)], clock=clock, sleep=clock.sleep, rng=random.Random(1),
                degraded=True)
    assert rw.read_completeness(D)["coins"]["SOL"]["reason"] == "zero_unconfirmed"
    assert (D, 0.0) not in store.read_points("reddit_web", "SOL")


def test_time_filter_starting_exactly_at_window_start_covers_the_day():
    result, reason, _ = count(feed_at([at(20), at(9)]), searched_from=at(0))
    assert reason is None and result.value == 2 and not result.capped


def test_density_span_comes_from_raw_entries_not_matched_ones():
    times = [at(23, 59) - timedelta(minutes=6 * i) for i in range(100)]  # oldest raw entry D 14:05
    body = atom([entry(i + 1, t, title=TITLE if i < 50 else "unrelated") for i, t in enumerate(times)])
    result, reason, tally = count(body)
    span = (at(24) - at(14, 5)).total_seconds() / 3600
    assert reason is None and result.capped and tally.counted == 50
    assert result.span_hours == pytest.approx(span) and result.value == pytest.approx(24 * 50 / span)
