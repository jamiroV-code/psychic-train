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

Counting for a completed UTC day D (A.2): the response covers the window when its oldest entry is older than D
00:00, then the value is the exact count of entries in D (newer entries ignored); otherwise at least
`reddit_sample_min` entries in D give the A.1 density 24 * k / span (span from D+1 00:00 back to the oldest entry
in D, floor 0.25 h, `capped`); otherwise the coin-day is missing (`day_not_reached`, `below_sample_min`,
`empty_feed`), never 0. Values are stored only through `web_evidence.commit_day` (complete day, AC3 zero rule,
frozen evidence row) under the source `reddit_web`, never `reddit`.

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
TRAILING_DAYS = 28
DAY_S = 86400.0
ATOM = "{http://www.w3.org/2005/Atom}"
_DTD = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
_HTML = re.compile(rb"<\s*html[\s>]", re.IGNORECASE)
_TAG = re.compile(r"<[^>]*>")
# Outcomes that never sent a request.
NOT_SENT = ("day_not_complete", "ambiguous", "paused", "too_early", "budget_spent")


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
class SearchOutcome:
    result: density.DayResult | None
    reason: str | None  # None: a day result; else a missing reason or why nothing was sent
    status: int | None = None
    entries: int = 0
    newest: datetime | None = None
    oldest: datetime | None = None

    @property
    def sent(self) -> bool:
        return self.reason not in NOT_SENT


@dataclass(frozen=True)
class PassResult:
    requests: int
    stop: str  # "done", "paused", "budget_spent", "host_stopped", "too_early"
    stored: int


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

def count_day(day: date, entries: list[FeedEntry], *, sample_min: int) -> tuple[density.DayResult | None, str | None]:
    if not entries:
        return None, "empty_feed"
    start, end = density.window(day)
    inside = [e.created for e in entries if start <= e.created < end]
    k = len(inside)
    if min(e.created for e in entries) < start:
        return density.DayResult(float(k), k, 24.0, False, False), None
    if k == 0:
        return None, "day_not_reached"
    if k < sample_min:
        return None, "below_sample_min"
    return density.day_value(day, inside, n_target=k, n_min=k, window_start_reached=False), None


# --- budget and pace ---

def daily_budget(config: CollectorConfig, *, degraded: bool) -> int:
    return config.reddit_degraded_request_budget if degraded else config.reddit_daily_request_budget


def reddit_source(config: CollectorConfig, *, degraded: bool, clock: Callable[[], datetime]) -> pc_pace.PcSource:
    """The Reddit budget and pause state. The budget is not adaptive: it follows the mode, never a stored value."""
    budget = daily_budget(config, degraded=degraded)
    src = pc_pace.PcSource(SOURCE, configured_budget=budget, floor=1, adaptive=False, clock=clock)
    if src._s["effective"] != budget:  # PcSource clamps a stored value to the configured one; undo a stale clamp
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
    src.spend(1)
    try:
        entries = parse_feed(fetch_feed(client, url), ledger.hasher if ledger is not None else None)
    except pa.CollectorError as exc:
        src.stamp_attempt()
        pa.log_failure(logger, SOURCE, exc)
        if exc.warning:
            src.warn(exc.reason)
        return SearchOutcome(None, exc.reason, exc.status)
    except Exception:
        src.stamp_attempt()
        raise
    src.record_unit()
    if ledger is not None:
        coins = reddit_metrics.coin_terms(q)
        ledger.add(reddit_items.LedgerRow(e.id, e.author_hash, e.subreddit, e.created, now, "search",
                                          reddit_metrics.matched_coins(e.text, coins)) for e in entries)
    result, reason = count_day(day, entries, sample_min=q.config.reddit_sample_min)
    times = [e.created for e in entries]
    return SearchOutcome(result, reason, 200, len(entries), max(times, default=None), min(times, default=None))


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
        return _summarize({"day": day.isoformat(), "requests": 0, "budget_cut": False, "coins": {}})
    return _summarize(json.loads(path.read_text(encoding="utf-8")))


def _record(day: date, symbol: str, reason: str, *, out: SearchOutcome | None = None, value: float | None = None,
            collected_at: datetime | None = None, budget_cut: bool = False) -> None:
    doc = read_completeness(day)
    attempted = out is not None and out.sent
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
            "value": value, "capped": bool(attempted and out.result is not None and out.result.capped)}
        doc["requests"] += 1 if attempted else 0
        doc["budget_cut"] = doc["budget_cut"] or budget_cut
    stored = {k: doc[k] for k in ("day", "requests", "budget_cut", "coins")}
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
    web_evidence.commit_day(SOURCE, symbol, day, out.result, canary_ok=out.entries > 0,
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
    requests = stored = 0
    stop = "done"
    items = list(queue)
    for i, (symbol, day) in enumerate(items):
        if not density.storable(day, _utc(clock())):
            continue
        if search_terms(q, symbol) is None:
            _record(day, symbol, "ambiguous")
            continue
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
    return PassResult(requests, stop, stored)
