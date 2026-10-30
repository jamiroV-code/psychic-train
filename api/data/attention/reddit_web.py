"""SPEC Annex A.2 M1, rules 10, 15, 16, AC25, AC28, AC37 (Reddit part): the Reddit `search.rss` connector.

One request per coin: `https://www.reddit.com/r/<A+B+...>/search.rss?q=<terms>&restrict_sr=1&sort=new&t=<filter>
&limit=100` over the configured subreddit set, `t` from `reddit_search_time_filter` (default `week`: `t=day`
reaches back only 24 h from the request and misses part of yesterday). Plain HTTP with the one honest user agent
of `web_queries`; no JSON endpoint, no login, no browser, no proxy, redirects are not followed.

Safety: a 403, any other non-200 that is not a 5xx, a redirect, an HTML body, a body with a DOCTYPE or entity
declaration, a body above `MAX_BODY_BYTES` or an XML root other than an Atom feed is never parsed as data: it is
`reddit_blocked` (429: `rate_limited`) and pauses Reddit for the rest of the UTC day with no retry. A 5xx or a
network error is `offline`: that coin-day stays missing, no pause, no retry in the unit. Logs carry the exception
class and HTTP status only (`pc_adapter.log_failure`).

Counting for a completed UTC day D (A.2, planner decisions T211 Q-b and Q-d). The value k is the number of
entries created in D that MATCH the coin (`reddit_metrics`: cashtag, full name, bare ticker unless `name_only` or
`cashtag_only`), at most `reddit_author_cap` per author; never the raw number of search results (Reddit search
returns fuzzy matches). Coverage is decided on the raw entries:
- a feed filled to the limit whose oldest entry is older than D 00:00 covers D: k is exact;
- a short feed (fewer entries than the limit, a valid Atom feed, so the search returned all it had for its time
  filter) covers D when an entry is older than D 00:00 or the time filter's span starts at or before D 00:00,
  and only when today's canary succeeded (`no_canary` otherwise): k is exact, even 0 for an empty feed;
- otherwise at least `reddit_sample_min` raw entries in D give the A.1 density 24 * k / span over the covered span
  (span from D+1 00:00 back to the oldest raw entry in D, floor 0.25 h, via `density.day_value`; `capped`);
- otherwise the coin-day is missing: `day_not_reached` or `below_sample_min` for a full feed, `window_not_reached`
  for a short one; never 0.
A zero is stored only when today's canary succeeded and the coin has a trailing median below 5 (AC3, Q-e): a coin
with no stored history stays missing until it has some. Values are stored only through `web_evidence.commit_day`
(complete day, frozen evidence row) under the source `reddit_web`, never `reddit`.

Canary (Q-d): once per UTC day, before the first search, one control request on `r/CryptoCurrency/new.rss`; it
succeeds when a valid feed holds at least `CANARY_MIN_ENTRIES` entries. It counts against the same daily budget,
follows the same pacing and block rules, and is recorded in a per-day canary file copied into each completeness
file.

Pacing (rule 15): BASELINE spreads the coins over the day at max(configured 60-120 s, 24 h / coins) per request,
budget `reddit_daily_request_budget` (250); DEGRADED runs at the configured 60-120 s, budget
`reddit_degraded_request_budget` (150). The worker (W8e) picks the mode from host uptime; nothing here reads an
hour of the day. Completeness per day (rule 16) is written next to the evidence rows.
"""
from __future__ import annotations

import html
import json
import logging
import random
import re
import secrets
import statistics
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from api.data import cache
from api.data.attention import (
    density,
    pc_pace,
    reddit_items,
    reddit_metrics,
    store,
    web_evidence,
    web_queries,
)
from api.data.attention import pc_adapter as pa
from api.data.attention.web_queries import HONEST_USER_AGENT as USER_AGENT
from api.data.attention.web_queries import CollectorConfig, Queries

log = logging.getLogger(__name__)


class _DropRedditRequestLine(logging.Filter):
    """httpx logs every request URL at INFO; a Reddit URL carries the search terms, so its line is dropped."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args if isinstance(record.args, tuple) else ()
        return not any("reddit.com" in str(a) for a in args)


logging.getLogger("httpx").addFilter(_DropRedditRequestLine())

SOURCE = "reddit_web"
METHOD = "reddit_web_search_rss_v1"
BASE_URL = "https://www.reddit.com"
SEARCH_LIMIT = 100
MAX_BODY_BYTES = 2_000_000  # the measured feeds are 50-90 KB; the 403 block page was about 190 KB
TIMEOUT_S = 30.0
CANARY_SUBREDDIT = "CryptoCurrency"  # a known-active subreddit: its newest-posts feed is always full
CANARY_MIN_ENTRIES = 25  # Reddit's default page; a working feed with limit=100 returns 100 (owner probe P-R6)
# How far back each `t` value reaches; month and year are the short ends so coverage is never over-claimed.
TIME_FILTER_SPAN = {"hour": timedelta(hours=1), "day": timedelta(days=1), "week": timedelta(days=7),
                    "month": timedelta(days=28), "year": timedelta(days=365), "all": None}
TRAILING_DAYS = 28
DAY_S = 86400.0
ATOM = "{http://www.w3.org/2005/Atom}"
_DTD = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
_HTML = re.compile(rb"<\s*html[\s>]", re.IGNORECASE)
_TAG = re.compile(r"<[^>]*>")
# Outcomes that never sent a request.
NOT_SENT = ("day_not_complete", "ambiguous", "paused", "too_early", "budget_spent")
EXCLUSION_REASONS = ("no_match", "author_cap")


class FeedRejected(pa.RedditBlocked):
    """The body is not a safe Atom feed (DTD or entity, oversize, HTML, another root): treated as a block."""


@dataclass(frozen=True)
class FeedEntry:
    id: str
    created: datetime
    updated: datetime | None
    author_hash: str | None
    subreddit: str | None
    text: str = field(repr=False)


@dataclass(frozen=True)
class Tally:
    """Evidence for one coin-day: raw entries, those in D, those matching the coin, those counted."""
    fetched: int
    in_window: int
    matched: int
    counted: int

    @property
    def excluded(self) -> dict:
        return {"no_match": self.in_window - self.matched, "author_cap": self.matched - self.counted}


@dataclass(frozen=True)
class SearchOutcome:
    result: density.DayResult | None
    reason: str | None  # None: a day result; else a missing reason or why nothing was sent
    status: int | None = None
    entries: int = 0
    newest: datetime | None = None
    oldest: datetime | None = None
    tally: Tally | None = None
    canary_ok: bool = False

    @property
    def sent(self) -> bool:
        return self.reason not in NOT_SENT


@dataclass(frozen=True)
class CanaryOutcome:
    ok: bool
    reason: str | None  # None: ok; else why it failed or why nothing was sent
    status: int | None = None
    entries: int = 0

    @property
    def sent(self) -> bool:
        return self.reason not in NOT_SENT


@dataclass(frozen=True)
class PassResult:
    requests: int  # search requests; the canary has its own count
    stop: str  # "done", "paused", "budget_spent", "host_stopped", "too_early"
    stored: int
    canary_requests: int = 0


def _utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        raise ValueError("clock must be timezone-aware UTC")
    return t.astimezone(timezone.utc)


# --- URL and terms ---

def search_terms(q: Queries, symbol: str) -> list[str] | None:
    """Ticker and name, the name only for a `name_only` coin; None when ambiguous for Reddit or unknown."""
    terms = web_queries.reddit_terms(q, symbol)
    if terms is None:
        return None
    if q.coins[symbol].get("name_only"):
        return [q.coins[symbol]["name"]]
    return terms


def search_url(subreddits: Iterable[str], terms: list[str], time_filter: str, limit: int = SEARCH_LIMIT) -> str:
    subs = list(subreddits)
    if not subs or not all(web_queries.SUBREDDIT_RE.fullmatch(s) for s in subs):
        raise ValueError("bad subreddit set")
    if time_filter not in web_queries.REDDIT_TIME_FILTERS or not terms:
        raise ValueError("bad time filter or no terms")
    if not all(web_queries.NAME_RE.fullmatch(t) for t in terms):
        raise ValueError("bad search term")
    query = quote(" OR ".join(f'"{t}"' for t in terms), safe="")
    return (f"{BASE_URL}/r/{'+'.join(subs)}/search.rss?q={query}&restrict_sr=1&sort=new&t={time_filter}"
            f"&limit={int(limit)}")


# --- HTTP and parsing ---

def make_client() -> httpx.Client:
    """The owner's client: no redirects, no proxy or other environment settings."""
    return httpx.Client(timeout=TIMEOUT_S, follow_redirects=False, trust_env=False)


def fetch_feed(client: httpx.Client, url: str) -> bytes:
    """One GET; the body, or a `CollectorError` carrying only a reason and the HTTP status."""
    try:
        with client.stream("GET", url, headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml"},
                           follow_redirects=False, timeout=TIMEOUT_S) as r:
            status = r.status_code
            if status == 429:
                raise pa.RateLimited(status)
            if 500 <= status < 600:
                raise pa.Offline(status)
            if status != 200:
                raise pa.RedditBlocked(status)
            if "html" in r.headers.get("content-type", "").lower():
                raise FeedRejected(status)
            body = bytearray()
            for chunk in r.iter_bytes():
                body += chunk
                if len(body) > MAX_BODY_BYTES:
                    raise FeedRejected(status)
            return bytes(body)
    except httpx.HTTPError:
        raise pa.Offline() from None


def _child_text(node: ET.Element, path: str) -> str | None:
    found = node.find(path)
    return found.text.strip() if found is not None and found.text else None


def _time(text: str | None) -> datetime | None:
    if text is None:
        return None
    try:
        t = datetime.fromisoformat(text)
    except ValueError:
        raise pa.LayoutChanged() from None
    if t.tzinfo is None:
        raise pa.LayoutChanged()
    return t.astimezone(timezone.utc)


def parse_feed(body: bytes, hasher: Callable[[str | None], str | None] | None = None) -> list[FeedEntry]:
    """Atom entries, newest first as served. The username never leaves this function: only its hash does."""
    if len(body) > MAX_BODY_BYTES or _DTD.search(body) or _HTML.search(body[:4096]):
        raise FeedRejected()
    try:
        root = ET.fromstring(body)  # safe here: a DOCTYPE or entity declaration was rejected above
    except ET.ParseError:
        raise FeedRejected() from None
    if root.tag != ATOM + "feed":
        raise FeedRejected()
    out = []
    for e in root.findall(ATOM + "entry"):
        rid = _child_text(e, ATOM + "id")
        updated, published = _time(_child_text(e, ATOM + "updated")), _time(_child_text(e, ATOM + "published"))
        if rid is None or not reddit_items.REDDIT_ID_RE.fullmatch(rid) or (updated or published) is None:
            raise pa.LayoutChanged()
        author = _child_text(e, f"{ATOM}author/{ATOM}name") if hasher is not None else None
        cat = e.find(ATOM + "category")
        sub = cat.get("term") if cat is not None else None
        title = _child_text(e, ATOM + "title") or ""
        content = html.unescape(_TAG.sub(" ", _child_text(e, ATOM + "content") or ""))
        out.append(FeedEntry(rid, published or updated, updated, hasher(author) if hasher is not None else None,
                             sub if sub and web_queries.SUBREDDIT_RE.fullmatch(sub) else None,
                             " ".join(f"{title} {content}".split())))
    return out


# --- counting (A.2) ---

def ephemeral_hasher() -> reddit_items.AuthorHasher:
    """An in-memory author hasher for counting without a ledger: the author cap needs only distinct authors."""
    return reddit_items.AuthorHasher(secrets.token_bytes(32))


def searched_from(now: datetime, time_filter: str) -> datetime | None:
    """The oldest time a search with this `t` can return; None for `all` (no limit)."""
    span = TIME_FILTER_SPAN[time_filter]
    return None if span is None else _utc(now) - span


def _tally(day: date, entries: list[FeedEntry], coin: reddit_metrics.CoinTerms,
           author_cap: int) -> tuple[list[FeedEntry], Tally]:
    start, end = density.window(day)
    inside = [e for e in entries if start <= e.created < end]
    items = [reddit_metrics.Item(e.id, e.author_hash, e.created,
                                 (coin.symbol,) if reddit_metrics.mentions(e.text, coin) else ()) for e in inside]
    matched = len({i.id for i in items if i.coins})
    kept = reddit_metrics.counted(items, coin.symbol, day, author_cap=author_cap)
    return inside, Tally(len(entries), len({e.id for e in inside}), matched, len(kept))


def count_day(day: date, entries: list[FeedEntry], *, coin: reddit_metrics.CoinTerms, sample_min: int,
              author_cap: int, limit: int = SEARCH_LIMIT, canary_ok: bool,
              searched_from: datetime | None) -> tuple[density.DayResult | None, str | None, Tally]:
    """The A.2 value for D from one parsed feed: (result, None, tally) or (None, the missing reason, tally)."""
    start = density.window(day)[0]
    inside, tally = _tally(day, entries, coin, author_cap)
    k = tally.counted
    exact = density.DayResult(float(k), k, 24.0, False, False)
    reached = any(e.created < start for e in entries)
    short = len(entries) < limit
    if short:
        if not canary_ok:
            return None, "no_canary", tally
        if reached or searched_from is None or searched_from <= start:
            return exact, None, tally
    elif reached:
        return exact, None, tally
    if len(inside) < sample_min or not inside:
        if short:
            return None, "window_not_reached", tally
        return None, "below_sample_min" if inside else "day_not_reached", tally
    # the covered span comes from the raw entries (W8b density); the count from the matched ones
    raw = density.day_value(day, [e.created for e in inside], n_target=len(inside), n_min=len(inside),
                            window_start_reached=False)
    return density.DayResult(24.0 * k / raw.span_hours, k, raw.span_hours, True, False), None, tally


# --- budget and pace ---

def daily_budget(config: CollectorConfig, *, degraded: bool) -> int:
    return config.reddit_degraded_request_budget if degraded else config.reddit_daily_request_budget


def reddit_source(config: CollectorConfig, *, degraded: bool, clock: Callable[[], datetime]) -> pc_pace.PcSource:
    """The Reddit budget and pause state. The budget is not adaptive: it follows the mode, never a stored value."""
    budget = daily_budget(config, degraded=degraded)
    src = pc_pace.PcSource(SOURCE, configured_budget=budget, floor=1, adaptive=False, clock=clock)
    # Kept deviation (W8c, accepted T211): PcSource clamps a stored effective budget down to the configured one and
    # has no way to raise it, so a UTC day first run degraded (150) would cap a later baseline run at 150. Reset the
    # private field to the mode's budget and write it through; the day's used count is untouched. Remove once W8e
    # lets `pc_pace` follow the configured budget for non-adaptive sources.
    if src._s["effective"] != budget:
        src._s["effective"] = budget
        src._save()
    return src


def search_trickle(config: CollectorConfig, n_coins: int, *, degraded: bool, rng: random.Random) -> pc_pace.Trickle:
    lo, hi = config.reddit_request_delay_min_s, config.reddit_request_delay_max_s
    if not degraded and n_coins > 0:
        spread = DAY_S / n_coins
        lo, hi = max(lo, spread), max(hi, spread)
    return pc_pace.Trickle(lo, hi, rng)


# --- one coin-day ---

def run_search_unit(client: httpx.Client, src: pc_pace.PcSource, q: Queries, *, symbol: str, day: date,
                    ledger: reddit_items.Ledger | None = None, logger: logging.Logger = log) -> SearchOutcome:
    """One `search.rss` request for a completed coin-day; never a retry. Nothing is sent when not allowed."""
    if ledger is not None and ledger.hasher is None:
        raise ValueError("a ledger needs an author hasher")
    now = _utc(src.clock())
    if not density.storable(day, now):
        return SearchOutcome(None, "day_not_complete")
    terms = search_terms(q, symbol)
    if terms is None:
        return SearchOutcome(None, "ambiguous")
    if src.is_paused():
        return SearchOutcome(None, "paused")
    due = src.earliest_next(q.config.reddit_request_delay_min_s)
    if due is not None and now < due:
        return SearchOutcome(None, "too_early")
    if not src.can_spend(1):
        src.mark_spent()
        return SearchOutcome(None, "budget_spent")
    url = search_url(q.subreddits, terms, q.config.reddit_search_time_filter)
    canary = canary_ok(now)
    src.spend(1)
    # Durable dispatch evidence: a power cut leaves an attempted, interrupted coin-day, not invisible work.
    # The terminal record in run_pass replaces this same key and counts the request only once.
    _record(day, symbol, "unit_interrupted", out=SearchOutcome(None, "unit_interrupted"),
            collected_at=now, count_request=False)
    try:
        entries = parse_feed(fetch_feed(client, url), ledger.hasher if ledger is not None else ephemeral_hasher())
    except pa.CollectorError as exc:
        src.stamp_attempt()
        pa.log_failure(logger, SOURCE, exc)
        if exc.warning:
            src.warn(exc.reason)
        return SearchOutcome(None, exc.reason, exc.status)
    except Exception:
        src.stamp_attempt()
        _record(day, symbol, "failed", out=SearchOutcome(None, "failed"), collected_at=_utc(src.clock()))
        raise
    src.record_unit()
    if ledger is not None:
        coins = reddit_metrics.coin_terms(q)
        ledger.add(reddit_items.LedgerRow(e.id, e.author_hash, e.subreddit, e.created, now, "search",
                                          reddit_metrics.matched_coins(e.text, coins)) for e in entries)
    c = q.config
    result, reason, tally = count_day(day, entries, coin=reddit_metrics.coin_term(q, symbol),
                                      sample_min=c.reddit_sample_min, author_cap=c.reddit_author_cap,
                                      canary_ok=canary, searched_from=searched_from(now, c.reddit_search_time_filter))
    times = [e.created for e in entries]
    return SearchOutcome(result, reason, 200, len(entries), max(times, default=None), min(times, default=None),
                         tally, canary)


# --- the daily canary (T211 Q-d) ---

def canary_url() -> str:
    return f"{BASE_URL}/r/{CANARY_SUBREDDIT}/new.rss?limit={SEARCH_LIMIT}"


def canary_path(day: date) -> Path:
    return cache.CACHE_ROOT / "attention" / SOURCE / "_meta" / "_canary" / f"{day.isoformat()}.json"


def read_canary(day: date) -> dict:
    path = canary_path(day)
    if not path.exists():
        return {"day": day.isoformat(), "requests": 0, "ok": False, "at": None, "status": None, "entries": 0,
                "reason": None}
    return json.loads(path.read_text(encoding="utf-8"))


def canary_ok(now: datetime) -> bool:
    """True once a canary of the same UTC day succeeded."""
    return read_canary(_utc(now).date())["ok"] is True


def _write_canary(now: datetime, out: CanaryOutcome) -> None:
    doc = read_canary(now.date())
    doc.update(requests=doc["requests"] + 1, ok=doc["ok"] or out.ok, at=now.isoformat(), status=out.status,
               entries=out.entries, reason=out.reason)
    path = canary_path(now.date())
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(doc, path)


def run_canary(client: httpx.Client, src: pc_pace.PcSource, q: Queries, *,
               logger: logging.Logger = log) -> CanaryOutcome:
    """One control request on a known-active feed; the same gates, budget and block rules as a search."""
    now = _utc(src.clock())
    if src.is_paused():
        return CanaryOutcome(False, "paused")
    due = src.earliest_next(q.config.reddit_request_delay_min_s)
    if due is not None and now < due:
        return CanaryOutcome(False, "too_early")
    if not src.can_spend(1):
        src.mark_spent()
        return CanaryOutcome(False, "budget_spent")
    src.spend(1)
    try:
        entries = parse_feed(fetch_feed(client, canary_url()))
    except pa.CollectorError as exc:
        src.stamp_attempt()
        pa.log_failure(logger, SOURCE, exc)
        if exc.warning:
            src.warn(exc.reason)
        out = CanaryOutcome(False, exc.reason, exc.status)
        _write_canary(now, out)
        return out
    except Exception:
        src.stamp_attempt()
        raise
    src.record_unit()
    n = len(entries)
    out = CanaryOutcome(n >= CANARY_MIN_ENTRIES, None if n >= CANARY_MIN_ENTRIES else "canary_short", 200, n)
    _write_canary(now, out)
    return out


# --- completeness (rule 16) ---

def completeness_path(day: date) -> Path:
    return cache.CACHE_ROOT / "attention" / SOURCE / "_meta" / "_completeness" / f"{day.isoformat()}.json"


def _summarize(doc: dict) -> dict:
    coins = doc["coins"]
    reasons = Counter(c["reason"] for c in coins.values() if c["reason"] != "fetched")
    newest = [c["newest"] for c in coins.values() if c.get("newest")]
    collected = [c["collected_at"] for c in coins.values() if c.get("collected_at")]
    return {**doc, "attempted": sum(1 for c in coins.values() if c["attempted"]),
            "fetched": sum(1 for c in coins.values() if c["reason"] == "fetched"),
            "missing": sum(reasons.values()), "reasons": dict(sorted(reasons.items())),
            "capped": sum(1 for c in coins.values() if c["reason"] == "fetched" and c["capped"]),
            "newest_entry_at": max(newest, default=None), "collected_at": max(collected, default=None)}


def read_completeness(day: date) -> dict:
    path = completeness_path(day)
    if not path.exists():
        return _summarize({"day": day.isoformat(), "requests": 0, "budget_cut": False, "canary": None, "coins": {}})
    return _summarize(json.loads(path.read_text(encoding="utf-8")))


def _record(day: date, symbol: str, reason: str, *, out: SearchOutcome | None = None, value: float | None = None,
            collected_at: datetime | None = None, budget_cut: bool = False, count_request: bool = True) -> None:
    doc = read_completeness(day)
    attempted = out is not None and out.sent
    tally = out.tally if attempted else None
    old = doc["coins"].get(symbol)
    if not attempted and old is not None and reason != "ambiguous":
        # an item the pass did not reach keeps an earlier attempt's record
        doc["budget_cut"] = doc["budget_cut"] or budget_cut
    else:
        doc["coins"][symbol] = {
            "reason": reason, "attempted": attempted, "status": out.status if attempted else None,
            "collected_at": collected_at.isoformat() if attempted and collected_at else None,
            "entries": out.entries if attempted else 0,
            "newest": out.newest.isoformat() if attempted and out.newest else None,
            "oldest": out.oldest.isoformat() if attempted and out.oldest else None,
            "in_window": tally.in_window if tally else 0, "matched": tally.matched if tally else 0,
            "counted": tally.counted if tally else 0,
            "excluded": tally.excluded if tally else dict.fromkeys(EXCLUSION_REASONS, 0),
            "canary_ok": bool(attempted and out.canary_ok),
            "value": value, "capped": bool(attempted and out.result is not None and out.result.capped)}
        doc["requests"] += 1 if attempted and count_request else 0
        doc["budget_cut"] = doc["budget_cut"] or budget_cut
        if attempted and collected_at is not None:
            doc["canary"] = read_canary(collected_at.date())  # the run day's canary, as seen at this record
    stored = {k: doc.get(k) for k in ("day", "requests", "budget_cut", "canary", "coins")}
    path = completeness_path(day)
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(_summarize(stored), path)


def trailing_median(symbol: str, day: date) -> float | None:
    start = day - timedelta(days=TRAILING_DAYS)
    vals = [v for d, v in store.read_points(SOURCE, symbol) if start <= d < day]
    return statistics.median(vals) if vals else None


def _commit(symbol: str, day: date, out: SearchOutcome, now: datetime) -> tuple[str, float | None]:
    if out.result is None:
        return out.reason or "failed", None
    web_evidence.commit_day(SOURCE, symbol, day, out.result, canary_ok=out.canary_ok,
                            trailing_median=trailing_median(symbol, day), now=now, method=METHOD)
    stored = dict(store.read_points(SOURCE, symbol))
    return ("fetched", stored[day]) if day in stored else ("zero_unconfirmed", None)


# --- one pass over a queue ---

def run_pass(client: httpx.Client, src: pc_pace.PcSource, q: Queries, *, queue: list[tuple[str, date]],
             clock: Callable[[], datetime], sleep: Callable[[float], None], rng: random.Random, degraded: bool,
             ledger: reddit_items.Ledger | None = None, stop_at: datetime | None = None, n_coins: int | None = None,
             logger: logging.Logger = log) -> PassResult:
    """Work through (symbol, completed day) items at the mode's pace until done, paused, out of budget or `stop_at`.

    Items left when the pass stops stay for a later pass (the worker re-queues missing days, yesterday first).
    """
    n = n_coins if n_coins is not None else len({s for s, _ in queue})
    trickle = search_trickle(q.config, n, degraded=degraded, rng=rng)
    due = trickle.first_due(_utc(clock()), src.last_unit_at())
    requests = stored = canaries = 0
    canary_days: set[date] = set()  # UTC days this pass already tried a canary on
    canary_gap = search_trickle(q.config, n, degraded=True, rng=rng)  # the configured 60-120 s
    stop = "done"
    items = list(queue)
    for i, (symbol, day) in enumerate(items):
        if not density.storable(day, _utc(clock())):
            continue
        if search_terms(q, symbol) is None:
            _record(day, symbol, "ambiguous")
            continue
        today = _utc(clock()).date()
        if today not in canary_days and not canary_ok(_utc(clock())) and not src.is_paused() and src.can_spend(1):
            # one canary attempt per pass and UTC day, before the day's first search; the search follows at the
            # configured minimum spacing so it runs on the same UTC day as its canary
            canary_days.add(today)
            if stop_at is not None and due >= _utc(stop_at):
                stop = "host_stopped"
                break
            wait = (due - _utc(clock())).total_seconds()
            if wait > 0:
                sleep(wait)
            c_out = run_canary(client, src, q, logger=logger)
            if c_out.reason == "too_early":
                stop = "too_early"
                break
            canaries += c_out.sent
            due = canary_gap.next_due(_utc(clock()))
        if src.is_paused() or not src.can_spend(1):
            if src.is_paused():
                stop, reason, cut = "paused", src.pause_reason(), False
            else:
                src.mark_spent()
                stop, reason, cut = "budget_spent", "budget_spent", True
            for sym, d in items[i:]:
                if density.storable(d, _utc(clock())):
                    _record(d, sym, "ambiguous" if search_terms(q, sym) is None else reason, budget_cut=cut)
            break
        if stop_at is not None and due >= _utc(stop_at):
            stop = "host_stopped"
            break
        wait = (due - _utc(clock())).total_seconds()
        if wait > 0:
            sleep(wait)
        out = run_search_unit(client, src, q, symbol=symbol, day=day, ledger=ledger, logger=logger)
        if out.reason == "too_early":
            stop = "too_early"
            break
        now = _utc(clock())
        reason, value = _commit(symbol, day, out, now)
        stored += reason == "fetched"
        requests += out.sent
        _record(day, symbol, reason, out=out, value=value, collected_at=now)
        due = trickle.next_due(now)
    return PassResult(requests, stop, stored, canaries)
