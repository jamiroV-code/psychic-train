"""W8c AC2, AC3, AC9, AC24, AC25, AC28, AC37 (Reddit part), SPEC A.2 M1: the Reddit `search.rss` connector.

Fake HTTP clients only (httpx.MockTransport); no live Reddit request. Clocks are injected.
"""
from __future__ import annotations

import dataclasses
import logging
import random
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from api.data import cache
from api.data.attention import pc_pace, reddit_items, reddit_web as rw, store, web_evidence
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


def entry(i: int, when: datetime, *, author: str = "u1", title: str = "SOL news", sub: str = "CryptoCurrency",
          published: bool = True, kind: str = "t3") -> str:
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


class Fake:
    """Records every request; `respond(request)` returns the response."""

    def __init__(self, respond):
        self.respond, self.requests = respond, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def ok(body: bytes, ctype: str = "application/atom+xml; charset=UTF-8"):
    return lambda req: httpx.Response(200, content=body, headers={"content-type": ctype})


def cfg(**kw) -> wq.CollectorConfig:
    return dataclasses.replace(wq.load().config, **kw)


@pytest.fixture
def q():
    return wq.load()


def unit(fake: Fake, q, clock: Clock, *, symbol="SOL", day=D, degraded=False, ledger=None):
    src = rw.reddit_source(q.config, degraded=degraded, clock=clock)
    return rw.run_search_unit(fake.client(), src, q, symbol=symbol, day=day, ledger=ledger), src


# --- parser and A.2 counting ---

def test_parse_atom_entries_with_updated_timestamps():
    both = rw.parse_feed(feed_at([at(12)]))
    (e,) = both
    assert e.id == "t3_1" and e.created == at(12) and e.updated == at(12) and e.subreddit == "CryptoCurrency"
    assert "SOL news" in e.text and "body 1" in e.text and "<p>" not in e.text
    assert e.author_hash is None  # no hasher given: the username is dropped at the parser
    only_updated = rw.parse_feed(atom([entry(2, at(7), published=False)]))
    assert only_updated[0].created == at(7)
    offset = rw.parse_feed(atom([entry(3, at(7)).replace(at(7).isoformat(), "2026-10-26T09:00:00+02:00")]))
    assert offset[0].created == at(7) and offset[0].created.tzinfo == timezone.utc


def test_exact_count_when_feed_reaches_window_start():
    result, reason = rw.count_day(D, rw.parse_feed(EXACT), sample_min=10)
    assert reason is None and result.value == 3 and not result.capped and result.n == 3
    zero, _ = rw.count_day(D, rw.parse_feed(feed_at([at(30), at(-5)])), sample_min=10)
    assert zero.value == 0 and not zero.capped  # exact zero; the AC3 zero rule decides at commit time


def test_feed_capped_uses_density_over_covered_span():
    times = [at(h) for h in range(23, 11, -1)]  # 12 entries, 23:00 .. 12:00, no entry before D
    result, reason = rw.count_day(D, rw.parse_feed(feed_at(times)), sample_min=10)
    assert reason is None and result.capped and not result.pagecap
    assert result.n == 12 and result.span_hours == pytest.approx(12.0) and result.value == pytest.approx(24.0)
    late = [at(23, 59 - m) for m in range(10)]  # ten entries in the last 10 minutes: span floor 0.25 h
    floor, _ = rw.count_day(D, rw.parse_feed(feed_at(late)), sample_min=10)
    assert floor.span_hours == pytest.approx(0.25) and floor.value == pytest.approx(960.0)


def test_day_not_reached_is_missing():
    result, reason = rw.count_day(D, rw.parse_feed(feed_at([at(24 + h) for h in range(5)])), sample_min=10)
    assert result is None and reason == "day_not_reached"
    empty, why = rw.count_day(D, rw.parse_feed(atom([])), sample_min=10)
    assert empty is None and why == "empty_feed"


def test_entries_after_window_end_ignored():
    times = [at(24 + h) for h in range(5)] + [at(12), at(1), at(-1)]
    result, _ = rw.count_day(D, rw.parse_feed(feed_at(times)), sample_min=10)
    assert result.value == 2 and not result.capped
    edge, _ = rw.count_day(D, rw.parse_feed(feed_at([at(24), at(0), at(-1)])), sample_min=10)
    assert edge.value == 1  # D+1 00:00 is outside, D 00:00 is inside


def test_below_reddit_sample_min_is_missing():
    nine = [at(23 - h) for h in range(9)]
    result, reason = rw.count_day(D, rw.parse_feed(feed_at(nine)), sample_min=10)
    assert result is None and reason == "below_sample_min"
    ten, _ = rw.count_day(D, rw.parse_feed(feed_at(nine + [at(10)])), sample_min=10)
    assert ten is not None and ten.capped


def test_malformed_entry_is_layout_changed():
    bad = atom(["<entry><title>x</title></entry>"])
    with pytest.raises(rw.pa.LayoutChanged):
        rw.parse_feed(bad)


# --- URL, terms, user agent ---

def test_search_rss_url_form_sort_new_t_day_and_subreddit_set(q):
    url = rw.search_url(["CryptoCurrency", "CryptoMarkets"], ["SOL", "Solana"], "day")
    assert url == ("https://www.reddit.com/r/CryptoCurrency+CryptoMarkets/search.rss"
                   "?q=%22SOL%22%20OR%20%22Solana%22&restrict_sr=1&sort=new&t=day&limit=100")
    fake = Fake(ok(EXACT))
    unit(fake, dataclasses.replace(q, config=cfg(reddit_search_time_filter="day")), Clock(NOW))
    (req,) = fake.requests
    parts = urlsplit(str(req.url))
    assert parts.scheme == "https" and parts.netloc == "www.reddit.com"
    assert parts.path == "/r/" + "+".join(q.subreddits) + "/search.rss"
    qs = parse_qs(parts.query)
    assert qs["sort"] == ["new"] and qs["restrict_sr"] == ["1"] and qs["t"] == ["day"] and qs["q"] == ['"SOL" OR "Solana"']


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
    assert fake.requests == [] and res.requests == 0
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
    times = [at(h) for h in range(23, 11, -1)]
    fake, clock = Fake(ok(feed_at(times))), Clock(NOW)
    src = rw.reddit_source(q.config, degraded=False, clock=clock)
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D)], clock=clock, sleep=clock.sleep,
                rng=random.Random(1), degraded=False)
    row = web_evidence.read_rows("reddit_web", "SOL")[D]
    assert row.value == pytest.approx(24.0) and row.n == 12 and row.capped and not row.pagecap
    assert row.span_hours == pytest.approx(12.0) and row.method == rw.METHOD and not row.backfilled
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
    assert len(fake.requests) == res.requests == 150 and res.stop == "budget_spent" and src.used == 150
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
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    assert min(gaps) >= 86400 / 75 and len(times) >= 74 and (times[-1] - times[0]) >= timedelta(hours=23)
    few = pc_pace.plan_run(rw.search_trickle(c, 3, degraded=False, rng=random.Random(4)), start=start,
                           stop=start + timedelta(hours=24))
    assert min((b - a).total_seconds() for a, b in zip(few, few[1:])) >= 28800
    fast = pc_pace.plan_run(rw.search_trickle(c, 75, degraded=True, rng=random.Random(4)), start=start,
                            stop=start + timedelta(hours=1))
    assert all(60 <= (b - a).total_seconds() <= 120 for a, b in zip(fast, fast[1:])) and len(fast) >= 29
    # many coins: the configured 60-120 s stays the floor
    crowd = pc_pace.plan_run(rw.search_trickle(c, 5000, degraded=False, rng=random.Random(4)), start=start,
                             stop=start + timedelta(hours=1))
    assert min((b - a).total_seconds() for a, b in zip(crowd, crowd[1:])) >= 60
    # the pass itself keeps the spread: three coins, a sent request every 8 h or more
    fake, clock = Fake(ok(EXACT)), Clock(start)
    src = rw.reddit_source(c, degraded=False, clock=clock)
    sent = []
    orig = fake.respond
    fake.respond = lambda req: (sent.append(clock()), orig(req))[1]
    rw.run_pass(fake.client(), src, q, queue=[("SOL", D), ("ETH", D), ("ADA", D)], clock=clock, sleep=clock.sleep,
                rng=random.Random(5), degraded=False)
    assert len(sent) == 3 and all((b - a).total_seconds() >= 28800 for a, b in zip(sent, sent[1:]))


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
    assert c["attempted"] == 4 and c["fetched"] == 1 and c["missing"] == 4
    assert c["reasons"] == {"day_not_reached": 1, "below_sample_min": 1, "offline": 1, "ambiguous": 1}
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
    assert c2["fetched"] == 2 and c2["missing"] == 3 and "offline" not in c2["reasons"] and c2["requests"] == 5


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
        fake = Fake(respond)
        sent = []
        fake.respond = (lambda f: lambda req: (sent.append(clock()), f(req))[1])(respond)
        src = rw.reddit_source(q.config, degraded=True, clock=clock)
        res = rw.run_pass(fake.client(), src, q, queue=[("SOL", D), ("ETH", D)], clock=clock, sleep=clock.sleep,
                          rng=random.Random(hh), degraded=True, stop_at=start + timedelta(hours=1))
        assert res.requests == 2 and sent[0] - start <= timedelta(seconds=pc_pace.BEHIND_DELAY_S)
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
