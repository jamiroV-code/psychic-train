"""SPEC Annex A.2 M2, A.2b, rules 10, 13-16, AC14, AC26, AC28-AC30, AC37, AC38: Reddit stream-and-count.

Method `reddit_stream`, stored under its own source and method id, apart from `reddit_web` (AC14). The stream polls
two public feeds over the configured subreddit set (`web_queries.stream_subreddits`: `reddit_stream_subreddits`, or
the top-level `subreddits` list when that key is None), each as ONE combined multi-subreddit feed so the polls fit
the shared daily Reddit request budget:
- comments: `https://www.reddit.com/r/<A+B+...>/comments/.rss?limit=100`, every `reddit_comments_poll_interval_s`;
- posts: `https://www.reddit.com/r/<A+B+...>/new/.rss?limit=100`, every `reddit_posts_poll_interval_s`;
at most `reddit_stream_polls_per_day_cap` polls per feed kind and UTC day. Fetching, parsing, the honest user agent
and the block rules are W8c's (`reddit_web.fetch_feed`, `reddit_web.parse_feed`): a 403, 429, redirect, HTML or
non-Atom body pauses Reddit for the rest of the UTC day with no retry, and every request is spent from the one Reddit
budget and pace state that the per-coin searches use (`reddit_web.reddit_source`).

Comments paging (`reddit_comments_paging`, on by default after the owner's probe P-R7): when a full comments page
does not reach back to the paging floor (the newest entry of the previous COMPLETE comments poll or, with none, the
start of the newest completed UTC day), the next page is requested with `after=<last t1 id>` at the configured
request spacing, until the floor is reached, a page is short or makes no progress (the natural ends), or paging is
cut: Reddit pauses, a page fails, the last id is not a `t1_` id, or the daily budget is spent. A cut poll is stored
as TRUNCATED: its entries and its real [oldest, newest] span still count, but it never settles a day, and the next
poll pages back to the last complete poll's newest entry so the gap it left can still be closed. Posts never page.

Every entry goes into the item ledger (`reddit_items`: Reddit id, author hash, subreddit, created, `collected_at`,
feed kind, matched coins); the ids the stream saw are kept per created day, so an id counts once across polls and
feeds. Each poll stores `collected_at`, its newest and oldest entry times, the entry count, the pages and whether it
was truncated. A well-formed empty feed is a recorded poll with no entries (reason `empty_feed`): it covers nothing
and settles nothing, and the kind waits for its interval like after any poll, so it does not spend the budget again.

Coverage (A.2 M2, A.2b), per feed KIND over the one combined feed, never per subreddit (owner-approved waiver of
the SPEC's per-subreddit coverage, AC26 and A.2 M2; a combined span can look continuous while one subreddit has a
hole, and the per-entry subreddit label read from a combined feed is UNVERIFIED until the owner's probe): a poll
covers [oldest entry, newest entry]; per kind the union of those intervals clipped to D, as a share of 24 h, is the
kind's coverage (a gap where the next poll's oldest entry is newer than the previous poll's newest stays uncovered).
A completed day is SETTLED for a kind once its coverage is 1 or a poll of that kind that was not truncated starts
after D (its oldest entry is at or after D's end), so the collector will not add to D any more. The day's value is
written only when D is complete, both kinds are settled, and BOTH kinds reach `reddit_stream_min_coverage`: the
count of distinct stream entries created in D that mention the coin (`reddit_metrics`, author cap), no scaling;
`partial` when a kind is below 1. Otherwise the coin-day is missing (`not_settled` or `below_coverage`), never 0.
Values go through `web_evidence.commit_day` and the AC3 zero rule as the SPEC states it: a zero needs a canary query
that returned data in the same pass AND a trailing median below 5. The stream sends no canary query, so `canary_ok`
is False (written as such in the completeness file) and a covered, settled real zero stays missing
(`zero_no_canary`, with the coin's trailing median, None without history). Completeness per day (rule 16, AC38) is
written next to the evidence rows.

`pick_impl` is the AC14 method choice: the first method in `reddit_impl_order` (default `reddit_web`, then
`reddit_stream`, as SPEC AC14 states) with enough points in the window is used for the whole window; points of two
methods are never mixed. The clock is injected; nothing here compares the clock to an hour of the day (AC28).
"""
from __future__ import annotations

import json
import logging
import random
import re
import statistics
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from api.data import cache
from api.data.attention import density, pc_pace, reddit_items, reddit_metrics, store, web_evidence, web_queries
from api.data.attention import pc_adapter as pa
from api.data.attention import reddit_web as rw
from api.data.attention.web_queries import Queries

log = logging.getLogger(__name__)

SOURCE = "reddit_stream"
METHOD = "reddit_stream_feeds_v1"
KINDS = ("comments", "new")  # comments first: the shorter feed span
LIMIT = rw.SEARCH_LIMIT
DAY_S = 86400.0
TRAILING_DAYS = rw.TRAILING_DAYS
_EPS_S = 1e-6
_COMMENT_ID = re.compile(r"t1_[a-z0-9]{1,16}")
CANARY_OK = False  # the stream sends no canary query (AC3); none is assumed, so no zero is stored
COVERAGE_SCOPE = "feed_kind"  # coverage per feed kind over the combined feed, never per subreddit (owner waiver)


def _utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        raise ValueError("clock must be timezone-aware UTC")
    return t.astimezone(timezone.utc)


def feed_url(subreddits: Iterable[str], kind: str, after: str | None = None) -> str:
    subs = list(subreddits)
    if not subs or not all(web_queries.SUBREDDIT_RE.fullmatch(s) for s in subs):
        raise ValueError("bad subreddit set")
    if kind not in KINDS:
        raise ValueError("bad feed kind")
    url = f"{rw.BASE_URL}/r/{'+'.join(subs)}/{kind}/.rss?limit={LIMIT}"
    if after is not None:
        if kind != "comments" or not _COMMENT_ID.fullmatch(after):
            raise ValueError("paging needs a comments feed and a t1 id")
        url += f"&after={after}"
    return url


# --- poll log and seen ids (git-ignored cache root) ---

@dataclass(frozen=True)
class Poll:
    kind: str
    collected_at: datetime
    newest: datetime | None  # None for a well-formed empty feed (no entries)
    oldest: datetime | None
    entries: int
    pages: int
    truncated: bool  # comments paging stopped early (budget, pause, error, non-t1 last id): see `run_poll`

    def to_json(self) -> dict:
        return {"kind": self.kind, "collected_at": self.collected_at.isoformat(),
                "newest": self.newest.isoformat() if self.newest else None,
                "oldest": self.oldest.isoformat() if self.oldest else None,
                "entries": self.entries, "pages": self.pages, "truncated": self.truncated}

    @classmethod
    def from_json(cls, d: dict) -> Poll:
        def t(v: str | None) -> datetime | None:
            return datetime.fromisoformat(v) if v is not None else None
        return cls(d["kind"], datetime.fromisoformat(d["collected_at"]), t(d["newest"]), t(d["oldest"]), d["entries"],
                   d["pages"], d["truncated"])


def _meta() -> Path:
    return cache.CACHE_ROOT / "attention" / SOURCE / "_meta"


def polls_path(day: date) -> Path:
    return _meta() / "_polls" / f"{day.isoformat()}.json"


def seen_path(day: date) -> Path:
    return _meta() / "_seen" / f"{day.isoformat()}.json"


def completeness_path(day: date) -> Path:
    return _meta() / "_completeness" / f"{day.isoformat()}.json"


def _write(doc: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(doc, path)


def append_poll(poll: Poll) -> None:
    """Store one poll under the UTC day it was collected on."""
    if poll.kind not in KINDS:
        raise ValueError("bad feed kind")
    path = polls_path(_utc(poll.collected_at).date())
    rows = json.loads(path.read_text(encoding="utf-8"))["polls"] if path.exists() else []
    _write({"polls": [*rows, poll.to_json()]}, path)


def read_polls(start: date, end: date) -> list[Poll]:
    """Polls collected on the UTC days start..end (inclusive), oldest collection first."""
    out = []
    day = start
    while day <= end:
        path = polls_path(day)
        if path.exists():
            out += [Poll.from_json(p) for p in json.loads(path.read_text(encoding="utf-8"))["polls"]]
        day += timedelta(days=1)
    return sorted(out, key=lambda p: p.collected_at)


def read_seen(day: date) -> set[str]:
    path = seen_path(day)
    return set(json.loads(path.read_text(encoding="utf-8"))["ids"]) if path.exists() else set()


def _add_seen(entries: Iterable[rw.FeedEntry]) -> int:
    """Remember the ids the stream saw, by created day; returns how many were new."""
    by_day: dict[date, set[str]] = {}
    for e in entries:
        by_day.setdefault(e.created.date(), set()).add(e.id)
    new = 0
    for day, ids in by_day.items():
        known = read_seen(day)
        fresh = ids - known
        if fresh:
            _write({"ids": sorted(known | fresh)}, seen_path(day))
            new += len(fresh)
    return new


# --- coverage (A.2 M2, A.2b) ---

def _covered_s(day: date, polls: Iterable[Poll], kind: str) -> float:
    start, end = density.window(day)
    spans = sorted((max(p.oldest, start), min(p.newest, end)) for p in polls if p.kind == kind and p.entries > 0)
    total, cur_a, cur_b = 0.0, None, None
    for a, b in spans:
        if b <= a:
            continue
        if cur_b is None or a > cur_b:
            if cur_b is not None:
                total += (cur_b - cur_a).total_seconds()
            cur_a, cur_b = a, b
        else:
            cur_b = max(cur_b, b)
    if cur_b is not None:
        total += (cur_b - cur_a).total_seconds()
    return total


def coverage(day: date, polls: Iterable[Poll], kind: str) -> float:
    """The covered share of D's 24 hours for one feed kind, from entry timestamps only."""
    return _covered_s(day, list(polls), kind) / DAY_S


@dataclass(frozen=True)
class DayStatus:
    coverage: dict[str, float]
    settled: bool
    ok: bool
    partial: bool
    newest_slice_bias: bool
    polls: dict[str, int]
    collected_at: datetime | None
    reason: str | None  # None, "day_not_complete", "not_settled" or "below_coverage"


def _moved_past(p: Poll, end: datetime) -> bool:
    """The poll shows the collector has moved past D: all its entries are at or after D's end and its paging was not
    truncated (a truncated poll stopped before its floor, so a complete poll could still reach back into D)."""
    return p.entries > 0 and not p.truncated and p.oldest >= end


def day_status(day: date, polls: Iterable[Poll], *, now: datetime, min_coverage: float) -> DayStatus:
    polls = list(polls)
    start, end = density.window(day)
    reaching = [p for p in polls if p.entries > 0 and p.newest >= start and p.oldest < end]
    covered = {k: _covered_s(day, polls, k) for k in KINDS}
    cov = {k: covered[k] / DAY_S for k in KINDS}
    settled = all(covered[k] >= DAY_S or any(p.kind == k and _moved_past(p, end) for p in polls) for k in KINDS)
    ok = all(covered[k] + _EPS_S >= min_coverage * DAY_S for k in KINDS)
    if not density.storable(day, now):
        reason = "day_not_complete"
    elif not settled:
        reason = "not_settled"
    elif not ok:
        reason = "below_coverage"
    else:
        reason = None
    return DayStatus(cov, settled, ok, ok and any(covered[k] < DAY_S for k in KINDS),
                     any(p.entries >= LIMIT for p in reaching), {k: sum(p.kind == k for p in reaching) for k in KINDS},
                     max((p.collected_at for p in reaching), default=None), reason)


# --- one poll ---

@dataclass(frozen=True)
class PollOutcome:
    kind: str
    # None, "paused", "too_early", "not_due", "poll_cap", "budget_spent", "empty_feed" or a CollectorError reason
    reason: str | None
    status: int | None = None
    requests: int = 0
    entries: int = 0
    new_ids: int = 0
    poll: Poll | None = None


def _interval(q: Queries, kind: str) -> int:
    c = q.config
    return c.reddit_comments_poll_interval_s if kind == "comments" else c.reddit_posts_poll_interval_s


def _recent_polls(q: Queries, now: datetime) -> list[Poll]:
    back = max(q.config.reddit_comments_poll_interval_s, q.config.reddit_posts_poll_interval_s) // int(DAY_S) + 1
    return read_polls(now.date() - timedelta(days=back), now.date())


def _not_due_reason(q: Queries, kind: str, now: datetime, recent: list[Poll]) -> str | None:
    mine = [p for p in recent if p.kind == kind]
    if mine and now < mine[-1].collected_at + timedelta(seconds=_interval(q, kind)):
        return "not_due"
    if sum(p.collected_at.date() == now.date() for p in mine) >= q.config.reddit_stream_polls_per_day_cap:
        return "poll_cap"
    return None


def due_kinds(q: Queries, now: datetime) -> list[str]:
    """Feed kinds whose interval has passed and whose daily poll cap is not reached."""
    now = _utc(now)
    recent = _recent_polls(q, now)
    return [k for k in KINDS if _not_due_reason(q, k, now, recent) is None]


def _paging_floor(kind: str, now: datetime, recent: list[Poll]) -> datetime:
    """How far back a comments poll must reach: the newest entry of the previous complete (not truncated) poll with
    entries, so a gap left by a truncated poll is paged again; else the start of the newest completed day."""
    mine = [p for p in recent if p.kind == kind and p.entries > 0 and not p.truncated]
    return mine[-1].newest if mine else density.window(density.completed_day(now))[0]


def run_poll(client: httpx.Client, src: pc_pace.PcSource, q: Queries, *, kind: str, ledger: reddit_items.Ledger,
             sleep: Callable[[float], None], rng: random.Random, logger: logging.Logger = log) -> PollOutcome:
    """One poll of one feed kind (pages included); never a retry. Nothing is sent when not allowed."""
    if kind not in KINDS:
        raise ValueError("bad feed kind")
    if ledger.hasher is None:
        raise ValueError("a ledger needs an author hasher")
    c = q.config
    now = _utc(src.clock())
    if src.is_paused():
        return PollOutcome(kind, "paused")
    due = src.earliest_next(c.reddit_request_delay_min_s)
    if due is not None and now < due:
        return PollOutcome(kind, "too_early")
    recent = _recent_polls(q, now)
    not_due = _not_due_reason(q, kind, now, recent)
    if not_due is not None:
        return PollOutcome(kind, not_due)
    if not src.can_spend(1):
        src.mark_spent()
        return PollOutcome(kind, "budget_spent")
    floor = _paging_floor(kind, now, recent)
    gap = pc_pace.Trickle(c.reddit_request_delay_min_s, c.reddit_request_delay_max_s, rng)
    subs = web_queries.stream_subreddits(q)
    pages: list[list[rw.FeedEntry]] = []
    after, requests, error, truncated = None, 0, None, False
    while True:
        src.spend(1)
        requests += 1
        try:
            entries = rw.parse_feed(rw.fetch_feed(client, feed_url(subs, kind, after)), ledger.hasher)
        except pa.CollectorError as exc:
            src.stamp_attempt()
            pa.log_failure(logger, SOURCE, exc)
            if exc.warning:
                src.warn(exc.reason)
            error, truncated = exc, True
            break
        except Exception:
            src.stamp_attempt()
            raise
        src.record_unit()
        if not entries or (pages and min(e.created for e in entries) >= min(e.created for e in pages[-1])):
            break  # empty, or a page that reaches no further back: paging made no progress (a natural end)
        pages.append(entries)
        if (kind != "comments" or not c.reddit_comments_paging or len(entries) < LIMIT
                or min(e.created for e in entries) <= floor):
            break  # no paging for this kind, a short page, or the floor is reached (natural ends)
        if not _COMMENT_ID.fullmatch(entries[-1].id) or src.is_paused():
            truncated = True  # paging is cut before its floor
            break
        if not src.can_spend(1):
            src.mark_spent()
            truncated = True
            break
        sleep(gap.next_delay())
        after = entries[-1].id
    if not pages:
        if error is not None:
            return PollOutcome(kind, error.reason, error.status, requests)
        poll = Poll(kind, now, None, None, 0, 0, False)  # a well-formed empty feed: a poll that covers nothing
        append_poll(poll)
        return PollOutcome(kind, "empty_feed", 200, requests, poll=poll)
    seen = [e for page in pages for e in page]
    coins = reddit_metrics.coin_terms(q)
    ledger.add(reddit_items.LedgerRow(e.id, e.author_hash, e.subreddit, e.created, now, kind,
                                      reddit_metrics.matched_coins(e.text, coins)) for e in seen)
    new_ids = _add_seen(seen)
    times = [e.created for e in seen]
    poll = Poll(kind, now, max(times), min(times), len(seen), len(pages), truncated)
    append_poll(poll)
    return PollOutcome(kind, error.reason if error is not None else None,
                       error.status if error is not None else 200, requests, len(seen), new_ids, poll)


@dataclass(frozen=True)
class StreamPass:
    outcomes: list[PollOutcome]
    stop: str  # "done", "host_stopped", "paused", "budget_spent" or a CollectorError reason


def run_due(client: httpx.Client, src: pc_pace.PcSource, q: Queries, *, ledger: reddit_items.Ledger,
            clock: Callable[[], datetime], sleep: Callable[[float], None], rng: random.Random,
            stop_at: datetime | None = None, logger: logging.Logger = log) -> StreamPass:
    """Poll every due feed kind at the configured request spacing. A kind left at `stop_at` stays due for the next
    window (nothing is dropped); only the safety limits (pause, budget) end a pass early."""
    gap = pc_pace.Trickle(q.config.reddit_request_delay_min_s, q.config.reddit_request_delay_max_s, rng)
    outcomes: list[PollOutcome] = []
    for kind in due_kinds(q, clock()):
        now = _utc(clock())
        last = src.last_unit_at()
        due = max(now, last + timedelta(seconds=gap.next_delay())) if last is not None else now
        if stop_at is not None and due >= _utc(stop_at):
            return StreamPass(outcomes, "host_stopped")
        wait = (due - now).total_seconds()
        if wait > 0:
            sleep(wait)
        out = run_poll(client, src, q, kind=kind, ledger=ledger, sleep=sleep, rng=rng, logger=logger)
        outcomes.append(out)
        if src.is_paused():
            return StreamPass(outcomes, out.reason or "paused")
        if out.reason == "budget_spent":
            return StreamPass(outcomes, "budget_spent")
    return StreamPass(outcomes, "done")


# --- day values and completeness (AC26, AC30, AC38) ---

def trailing_median(symbol: str, day: date) -> float | None:
    start = day - timedelta(days=TRAILING_DAYS)
    vals = [v for d, v in store.read_points(SOURCE, symbol) if start <= d < day]
    return statistics.median(vals) if vals else None


def read_completeness(day: date) -> dict | None:
    path = completeness_path(day)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def commit_day(day: date, q: Queries, ledger: reddit_items.Ledger, *, now: datetime) -> dict | None:
    """Evaluate one completed UTC day for every coin; store the values that pass the coverage rule.

    Returns the completeness document (also written), or None when D is not complete (nothing written).
    """
    now = _utc(now)
    if not density.storable(day, now):
        return None
    c = q.config
    st = day_status(day, read_polls(day, now.date()), now=now, min_coverage=c.reddit_stream_min_coverage)
    seen = read_seen(day)
    items = reddit_items.to_items(r for r in ledger.read_day(day).values() if r.id in seen)
    ambiguous = q.ambiguous["reddit_web"]
    coins: dict[str, dict] = {}
    for sym in sorted(q.coins):
        if sym in ambiguous:
            coins[sym] = {"reason": "ambiguous", "value": None}
            continue
        if st.reason is not None:
            coins[sym] = {"reason": st.reason, "value": None}
            continue
        k = len(reddit_metrics.counted(items, sym, day, author_cap=c.reddit_author_cap))
        result = density.DayResult(float(k), k, 24.0 * min(st.coverage.values()), False, False)
        median = trailing_median(sym, day)
        web_evidence.commit_day(SOURCE, sym, day, result, canary_ok=CANARY_OK, trailing_median=median, now=now,
                                method=METHOD)
        stored = dict(store.read_points(SOURCE, sym))
        # only a zero is held back (AC3): with no stream canary it stays missing whatever the trailing median
        coins[sym] = ({"reason": "fetched", "value": stored[day]} if day in stored
                      else {"reason": "zero_no_canary", "value": None, "trailing_median": median})
    missing = Counter(v["reason"] for v in coins.values() if v["reason"] != "fetched")
    doc = {"day": day.isoformat(), "method": METHOD, "settled": st.settled, "coverage_scope": COVERAGE_SCOPE,
           "coverage": {k: round(v, 6) for k, v in st.coverage.items()}, "canary_ok": CANARY_OK,
           "min_coverage": c.reddit_stream_min_coverage, "partial": st.partial,
           "newest_slice_bias": st.newest_slice_bias, "polls": st.polls, "entries_seen": len(seen),
           "collected_at": st.collected_at.isoformat() if st.collected_at else None,
           "attempted": sum(1 for s in q.coins if s not in ambiguous),
           "fetched": sum(1 for v in coins.values() if v["reason"] == "fetched"),
           "missing": dict(sorted(missing.items())), "coins": coins}
    _write(doc, completeness_path(day))
    return doc


def open_days(now: datetime) -> list[date]:
    """Completed days the stream saw entries for that are not settled yet (oldest first)."""
    now = _utc(now)
    folder = _meta() / "_seen"
    if not folder.exists():
        return []
    out = []
    for path in sorted(folder.glob("*.json")):
        day = date.fromisoformat(path.stem)
        doc = read_completeness(day)
        if density.storable(day, now) and (doc is None or not doc["settled"]):
            out.append(day)
    return out


# --- method choice (AC14) ---

def pick_impl(order: Iterable[str], series: Mapping[str, list[tuple[date, float]]], start: date, end: date, *,
              min_points: int) -> tuple[str | None, list[tuple[date, float]]]:
    """The first method in `order` with at least `min_points` points in [start, end], and only its points."""
    for method in order:
        pts = sorted((d, v) for d, v in series.get(method, []) if start <= d <= end)
        if len(pts) >= min_points:
            return method, pts
    return None, []


# --- owner probe (local state only) ---

def stream_status(now: datetime, *, days: int = 3) -> dict:
    """Polls today and per feed kind the coverage for the last `days` completed days, from local files only (no
    request). A kind no poll with entries reached on a day has unknown coverage there: None, never 0."""
    now = _utc(now)
    today = read_polls(now.date(), now.date())
    out = {"today": {"polls_comments": sum(p.kind == "comments" for p in today),
                     "polls_new": sum(p.kind == "new" for p in today),
                     "entries_seen": len(read_seen(now.date()))},
           "days": {}}
    for i in range(1, days + 1):
        day = now.date() - timedelta(days=i)
        doc = read_completeness(day)
        if doc is None:
            st = day_status(day, read_polls(day, now.date()), now=now, min_coverage=0.0)
            cov, polls, settled, partial, fetched, missing = st.coverage, st.polls, st.settled, None, None, None
        else:
            cov, polls, settled, partial = doc["coverage"], doc["polls"], doc["settled"], doc["partial"]
            fetched, missing = doc["fetched"], sum(doc["missing"].values())
        known = {k: round(cov[k], 4) if polls[k] else None for k in KINDS}
        out["days"][day.isoformat()] = {"coverage_comments": known["comments"], "coverage_new": known["new"],
                                        "settled": settled, "partial": partial, "fetched": fetched,
                                        "missing": missing}
    return out
