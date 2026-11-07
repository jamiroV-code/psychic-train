"""Finish plan RC-2 to RC-6, RC-9: the method-independent core of the Reddit live methods. Pure file I/O; no network.

`LiveMethod` is the plug-in interface (S-RBrowser and S-RGQL supply it through `reddit_core.FACTORY_TABLE`, the
worker in `attention_pc_refresh.py` drives it). Everything here works on what a method reports in a `PollResult`:

- Lane evidence (RC-2): per (subreddit, kind `posts|comments`) and poll, the floor, newest/oldest item times, items,
  pages, the cursor chain `[(cursor, oldest in page)]` and a stop reason from `reddit_core.STOP_REASONS`. A lane is
  COMPLETE only when its paging reached the floor (`exhausted`). A posts lane pages `new` from the head at
  `collected_at`, so a complete lane observed [floor, collected_at] and a truncated one [oldest, collected_at]; a
  lane with no item observed nothing. Coverage is the union of observed intervals clipped to the UTC day, as in
  `reddit_stream.coverage`: no span bridges an interval no page observed.
- Floor (RC-3): the newest item of the previous complete posts lane (the ANCHOR), else the start of the newest
  completed UTC day; never older than that start.
- Comments (RC-3): each poll opens up to `reddit_live_threads_per_poll` threads: never-opened threads and threads
  whose `num_comments` grew since their last open. The day's DENOMINATOR is the set of threads observed active in
  the day's listings (created in D, or comment-count growth observed in D). A thread is covered when an exhausted
  open at or after D's end (the close poll; after the never-opened and grown threads, each poll re-opens the newest
  completed day's uncovered denominator) re-read it. Scope `threads_opened`: comments on posts that never reappear
  are unobserved.
- Settle and zero (RC-4): a day is valued only when every required subreddit's posts lane covers all of D and the
  comments coverage reaches `reddit_live_min_thread_coverage`; otherwise every coin-day is `lane_incomplete`
  missing. A zero is stored only through the `positive_history` commit policy (contract C3): the canary
  (`CryptoCurrency` posts lane of the closing poll returned >= `reddit_live_canary_min_items` items) AND at least
  `reddit_zero_min_history_days` days with a stored positive value in any Reddit method within 28 days; else
  `zero_unverified` missing.
- Counters and breaker (RC-6): per method and UTC day, requests and navigations; three consecutive failed polls
  open the breaker until the next UTC midnight; both persist over a restart.
Nothing here stores or logs text or usernames: items arrive reduced (`reddit_core.LiveItem`).
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from api.data import cache
from api.data.attention import density, reddit_core, reddit_metrics, registry, store, web_evidence
from api.data.attention.reddit_core import COMMENTS_SCOPE, LANE_KINDS, METHOD_IDS, STOP_REASONS, LiveItem
from api.data.attention.web_queries import SUBREDDIT_RE, Queries

DAY_S = 86400.0
_EPS_S = 1e-6
HISTORY_WINDOW_DAYS = 28
TRAILING_DAYS = 28
BREAKER_FAILURES = 3
# Stop reasons that make a poll a failed unit for the breaker (`cap` and `breaker` are budget ends, not failures).
FAILED_STOPS = frozenset({"error", "empty_shell", "login_required", "schema_mismatch", "unsupported_format",
                          "unknown"})

GateState = Literal["ready", "needs_probe", "no_ready_account", "browser_unadmitted",
                    "containment_residual_unaccepted", "cdp_pipe_unavailable", "profile_policy_unsatisfied",
                    "unsupported_format", "disabled", "method_unavailable"]


def _utc(t: datetime) -> datetime:
    if not isinstance(t, datetime) or t.tzinfo is None:
        raise ValueError("times must be timezone-aware")
    return t.astimezone(timezone.utc)


def _iso(t: datetime | None) -> str | None:
    return None if t is None else t.isoformat()


def _dt(s: str | None) -> datetime | None:
    return None if s is None else _utc(datetime.fromisoformat(s))


# --- the plug-in interface (RC-9) ---

@dataclass(frozen=True)
class LaneEvidence:
    subreddit: str
    kind: str  # "posts" | "comments"
    poll_id: str
    collected_at: datetime
    floor: datetime | None  # posts: the paging floor; comments: None
    newest: datetime | None
    oldest: datetime | None
    items_seen: int
    pages: int
    cursor_chain: tuple[tuple[str, datetime], ...]
    stop_reason: str
    threads: tuple[tuple[str, int], ...] = ()  # posts: (t3 id, num_comments) listed; comments: threads opened

    def __post_init__(self):
        if not SUBREDDIT_RE.fullmatch(self.subreddit) or self.kind not in LANE_KINDS:
            raise ValueError("bad lane")
        if self.stop_reason not in STOP_REASONS:
            raise ValueError("bad stop reason")
        if self.kind == "posts" and self.floor is None:
            raise ValueError("a posts lane needs its floor")
        if (isinstance(self.items_seen, bool) or not isinstance(self.items_seen, int) or self.items_seen < 0
                or isinstance(self.pages, bool) or not isinstance(self.pages, int) or self.pages < 0):
            raise ValueError("bad counts")
        if not all(isinstance(t, str) and t.startswith("t3_") and isinstance(n, int) and not isinstance(n, bool)
                   and n >= 0 for t, n in self.threads):
            raise ValueError("bad threads")
        for name in ("collected_at", "floor", "newest", "oldest"):
            v = getattr(self, name)
            if v is not None:
                object.__setattr__(self, name, _utc(v))
        object.__setattr__(self, "cursor_chain", tuple((c, _utc(t)) for c, t in self.cursor_chain))
        object.__setattr__(self, "threads", tuple(self.threads))

    @property
    def complete(self) -> bool:
        return self.stop_reason == "exhausted"

    def span(self) -> tuple[datetime, datetime] | None:
        """The interval this lane observed, paging from its head at `collected_at` (posts lanes only)."""
        if self.kind != "posts":
            return None
        if self.complete:
            low = self.floor if self.oldest is None else min(self.floor, self.oldest)
            return low, self.collected_at
        if self.items_seen > 0 and self.oldest is not None:
            return self.oldest, self.collected_at
        return None

    def to_json(self) -> dict:
        return {"subreddit": self.subreddit, "kind": self.kind, "poll_id": self.poll_id,
                "collected_at": self.collected_at.isoformat(), "floor": _iso(self.floor),
                "newest": _iso(self.newest), "oldest": _iso(self.oldest), "items_seen": self.items_seen,
                "pages": self.pages, "cursor_chain": [[c, t.isoformat()] for c, t in self.cursor_chain],
                "stop_reason": self.stop_reason, "threads": [[t, n] for t, n in self.threads]}

    @classmethod
    def from_json(cls, d: dict) -> LaneEvidence:
        return cls(d["subreddit"], d["kind"], d["poll_id"], _dt(d["collected_at"]), _dt(d["floor"]), _dt(d["newest"]),
                   _dt(d["oldest"]), d["items_seen"], d["pages"], tuple((c, _dt(t)) for c, t in d["cursor_chain"]),
                   d["stop_reason"], tuple((t, n) for t, n in d["threads"]))


@dataclass(frozen=True)
class PollContext:
    now: datetime
    subreddits: tuple[str, ...]
    floors: Mapping[str, datetime]  # posts-lane floor per subreddit
    threads: tuple[str, ...]  # threads to open this poll
    requests_left: int


@dataclass(frozen=True)
class PollResult:
    poll_id: str
    collected_at: datetime
    lanes: tuple[LaneEvidence, ...]
    items: tuple[LiveItem, ...]
    requests: int
    navigations: int = 0

    @property
    def stop_reasons(self) -> dict[str, int]:
        return dict(Counter(lane.stop_reason for lane in self.lanes))

    @property
    def failed(self) -> bool:
        return any(lane.stop_reason in FAILED_STOPS for lane in self.lanes)


@runtime_checkable
class LiveMethod(Protocol):
    method_id: str
    label: str
    store: str

    def gate_state(self, now: datetime) -> GateState: ...

    def next_poll_due(self, now: datetime) -> datetime | None: ...

    def run_poll(self, ctx: PollContext) -> PollResult: ...

    def close(self) -> None: ...


# --- files ---

def _meta(store_name: str) -> Path:
    if store_name not in METHOD_IDS:
        raise ValueError("unknown live store")
    return cache.CACHE_ROOT / "attention" / store_name / "_meta"


def lanes_path(store_name: str, day: date) -> Path:
    return _meta(store_name) / "_polls" / f"{day.isoformat()}.json"


def completeness_path(store_name: str, day: date) -> Path:
    return _meta(store_name) / "_completeness" / f"{day.isoformat()}.json"


def state_path(store_name: str) -> Path:
    return _meta(store_name) / "_live_state.json"


def _write(doc: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json(doc, path)


def read_lanes(store_name: str, start: date, end: date) -> list[LaneEvidence]:
    out, d = [], start
    while d <= end:
        path = lanes_path(store_name, d)
        if path.exists():
            out += [LaneEvidence.from_json(r) for r in json.loads(path.read_text(encoding="utf-8"))["lanes"]]
        d += timedelta(days=1)
    return sorted(out, key=lambda lane: lane.collected_at)


# --- counters and breaker (RC-6) ---

def _fresh_state(day: date) -> dict:
    return {"day": day.isoformat(), "requests": 0, "navigations": 0, "failures": 0, "breaker_until": None}


def read_state(store_name: str, now: datetime) -> dict:
    """Today's counters; a new UTC day starts at zero (an open breaker keeps its until-midnight end)."""
    today = _utc(now).date()
    path = state_path(store_name)
    s = json.loads(path.read_text(encoding="utf-8")) if path.exists() else _fresh_state(today)
    if s["day"] != today.isoformat():
        s = _fresh_state(today)
    return s


def breaker_open(store_name: str, now: datetime) -> bool:
    until = read_state(store_name, now)["breaker_until"]
    return until is not None and _utc(now) < _dt(until)


def charge(store_name: str, now: datetime, *, requests: int, navigations: int = 0) -> dict:
    s = read_state(store_name, now)
    s["requests"] += requests
    s["navigations"] += navigations
    _write(s, state_path(store_name))
    return s


def record_unit(store_name: str, now: datetime, *, ok: bool) -> dict:
    """Count one unit; the third consecutive failure opens the breaker until the next UTC midnight."""
    s = read_state(store_name, now)
    s["failures"] = 0 if ok else s["failures"] + 1
    if s["failures"] >= BREAKER_FAILURES:
        s["breaker_until"] = density.window(_utc(now).date())[1].isoformat()
    _write(s, state_path(store_name))
    return s


# --- polls ---

def record_poll(store_name: str, result: PollResult) -> None:
    """Persist one poll: lane evidence by collection day, the reduced items, the counters and the breaker unit."""
    when = _utc(result.collected_at)
    if any(lane.collected_at != when or lane.poll_id != result.poll_id for lane in result.lanes):
        raise ValueError("lanes must belong to the poll")
    path = lanes_path(store_name, when.date())
    doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"lanes": []}
    doc["lanes"] += [lane.to_json() for lane in result.lanes]
    _write(doc, path)
    reddit_core.add_items(store_name, result.items)
    charge(store_name, when, requests=result.requests, navigations=result.navigations)
    record_unit(store_name, when, ok=not result.failed)


def poll_due(store_name: str, now: datetime, polls_per_day: int) -> datetime:
    """When the next poll is due: `polls_per_day` evenly spaced from the last poll (now when none ran)."""
    now = _utc(now)
    lanes = read_lanes(store_name, now.date() - timedelta(days=1), now.date())
    if not lanes:
        return now
    return lanes[-1].collected_at + timedelta(seconds=DAY_S / polls_per_day)


def lane_floor(lanes: Iterable[LaneEvidence], subreddit: str, now: datetime) -> datetime:
    """The posts-lane floor: the newest item of the previous complete lane, not older than the newest completed
    UTC day's start (the start itself without an anchor)."""
    base = density.window(density.completed_day(now))[0]
    anchor = None
    for lane in lanes:
        if lane.kind == "posts" and lane.subreddit == subreddit and lane.complete and lane.collected_at <= _utc(now):
            if anchor is None or lane.collected_at > anchor.collected_at:
                anchor = lane
    if anchor is None:
        return base
    return max(anchor.newest or anchor.floor, base)


def reopened_after(day: date, lanes: Iterable[LaneEvidence]) -> set[str]:
    """Threads an exhausted comments open re-read at or after D's end (by the close poll or a later one)."""
    end = density.window(day)[1]
    return {t for lane in lanes if lane.kind == "comments" and lane.complete and lane.collected_at >= end
            for t, _ in lane.threads}


def threads_to_open(lanes: Iterable[LaneEvidence], limit: int, close: Iterable[str] = ()) -> tuple[str, ...]:
    """Never-opened threads and threads whose comment count grew since their last open (most growth first), then
    the `close` threads (the newest completed day's denominator not yet re-opened since its end)."""
    listed: dict[str, int] = {}
    opened: dict[str, int] = {}
    for lane in sorted(lanes, key=lambda x: x.collected_at):
        target = listed if lane.kind == "posts" else opened if lane.complete else None
        if target is not None:
            target.update(lane.threads)
    grown = [(n - opened.get(t, -1), t) for t, n in listed.items() if t not in opened or n > opened[t]]
    first = [t for _, t in sorted(grown, key=lambda x: (-x[0], x[1]))]
    rest = sorted(set(close) - set(first))
    return tuple((first + rest)[:limit])


def build_context(store_name: str, subreddits: Iterable[str], now: datetime, *, threads_per_poll: int,
                  request_cap: int) -> PollContext:
    now = _utc(now)
    subs = tuple(dict.fromkeys([*subreddits, reddit_core.CANARY_SUBREDDIT]))
    lanes = read_lanes(store_name, now.date() - timedelta(days=2), now.date())
    floors = {s: lane_floor(lanes, s, now) for s in subs}
    day = density.completed_day(now)
    close = (thread_denominator(day, lanes, reddit_core.read_items(store_name, day).values())
             - reopened_after(day, lanes))
    left = max(request_cap - read_state(store_name, now)["requests"], 0)
    return PollContext(now, subs, floors, threads_to_open(lanes, threads_per_poll, close), left)


# --- coverage and settle (RC-2, RC-3) ---

def _merged(spans: Iterable[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def posts_coverage(day: date, lanes: Iterable[LaneEvidence], subreddit: str) -> tuple[float, list]:
    """The covered share of D for one subreddit's posts lane, and the uncovered holes (clipped to D)."""
    start, end = density.window(day)
    spans = (lane.span() for lane in lanes if lane.kind == "posts" and lane.subreddit == subreddit)
    covered = _merged((max(a, start), min(b, end)) for a, b in (s for s in spans if s) if min(b, end) > max(a, start))
    holes, cur = [], start
    for a, b in covered:
        if a > cur:
            holes.append((cur, a))
        cur = max(cur, b)
    if cur < end:
        holes.append((cur, end))
    return sum((b - a).total_seconds() for a, b in covered) / DAY_S, holes


def thread_denominator(day: date, lanes: Iterable[LaneEvidence], items: Iterable[LiveItem]) -> set[str]:
    """Threads observed active in D's listings: posts created in D, or comment-count growth observed in D."""
    start, end = density.window(day)
    out = {it.id for it in items if it.kind == "post" and start <= it.created_utc < end}
    seen: dict[str, int] = {}
    for lane in sorted((x for x in lanes if x.kind == "posts"), key=lambda x: x.collected_at):
        for t, n in lane.threads:
            if t in seen and n > seen[t] and start <= lane.collected_at < end:
                out.add(t)
            seen[t] = n
    return out


def comments_coverage(day: date, lanes: Iterable[LaneEvidence], denominator: set[str]) -> float:
    """The share of the denominator re-opened (an exhausted open) at or after D's end; 1 for no active thread."""
    if not denominator:
        return 1.0
    return len(denominator & reopened_after(day, lanes)) / len(denominator)


def closing_canary(day: date, lanes: Iterable[LaneEvidence], min_items: int) -> tuple[bool, int | None]:
    """The canary of the closing poll: the first complete `CryptoCurrency` posts lane at or after D's end."""
    end = density.window(day)[1]
    for lane in sorted(lanes, key=lambda x: x.collected_at):
        if (lane.kind == "posts" and lane.subreddit == reddit_core.CANARY_SUBREDDIT and lane.complete
                and lane.collected_at >= end):
            return lane.items_seen >= min_items, lane.items_seen
    return False, None


@dataclass(frozen=True)
class LiveDayStatus:
    posts_coverage: dict[str, float]
    holes: dict[str, list[tuple[datetime, datetime]]]
    comments_coverage: float
    threads: int
    settled: bool
    canary_ok: bool
    canary_items: int | None
    reason: str | None  # None, "day_not_complete" or "lane_incomplete"
    polls: int
    collected_at: datetime | None


def day_status(store_name: str, day: date, *, now: datetime, subreddits: Iterable[str], min_thread_coverage: float,
               canary_min_items: int) -> LiveDayStatus:
    now = _utc(now)
    lanes = read_lanes(store_name, day - timedelta(days=1), now.date())
    subs = tuple(dict.fromkeys([*subreddits, reddit_core.CANARY_SUBREDDIT]))
    cov, holes = {}, {}
    for s in subs:
        cov[s], holes[s] = posts_coverage(day, lanes, s)
    denom = thread_denominator(day, lanes, reddit_core.read_items(store_name, day).values())
    ccov = comments_coverage(day, lanes, denom)
    posts_ok = all(c * DAY_S + _EPS_S >= DAY_S for c in cov.values())
    settled = posts_ok and ccov + 1e-9 >= min_thread_coverage
    canary_ok, canary_items = closing_canary(day, lanes, canary_min_items)
    reason = "day_not_complete" if not density.storable(day, now) else None if settled else "lane_incomplete"
    reaching = {lane.poll_id for lane in lanes if lane.span() and lane.span()[1] >= density.window(day)[0]}
    return LiveDayStatus(cov, holes, ccov, len(denom), settled, canary_ok, canary_items, reason, len(reaching),
                         max((lane.collected_at for lane in lanes), default=None))


# --- values and completeness (RC-4, RC-5) ---

def positive_history_days(symbol: str, day: date) -> int:
    """Days in the 28 before D with a stored positive value in ANY Reddit method (the zero eligibility gate)."""
    start = day - timedelta(days=HISTORY_WINDOW_DAYS)
    days: set[date] = set()
    for source in registry.SOURCE_IMPLS["reddit"]:
        try:
            pts = store.read_points(source, symbol)
        except store.StoreReadError:
            continue
        days |= {d for d, v in pts if start <= d < day and v > 0}
    return len(days)


def trailing_median(store_name: str, symbol: str, day: date) -> float | None:
    start = day - timedelta(days=TRAILING_DAYS)
    vals = [v for d, v in store.read_points(store_name, symbol) if start <= d < day]
    return statistics.median(vals) if vals else None


def read_completeness(store_name: str, day: date) -> dict | None:
    path = completeness_path(store_name, day)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def commit_day(store_name: str, day: date, q: Queries, *, now: datetime, subreddits: Iterable[str]) -> dict | None:
    """Evaluate one completed UTC day for every coin and store the values that pass (contract C3 policy
    `positive_history`). Returns the completeness document (also written), or None before D is complete."""
    now = _utc(now)
    if not density.storable(day, now):
        return None
    c = q.config
    st = day_status(store_name, day, now=now, subreddits=subreddits,
                    min_thread_coverage=c.reddit_live_min_thread_coverage,
                    canary_min_items=c.reddit_live_canary_min_items)
    items = [reddit_metrics.Item(id=i.id, author_hash=i.author_hash, created=i.created_utc, coins=i.coins)
             for i in reddit_core.read_items(store_name, day).values()]
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
        history = positive_history_days(sym, day)
        history_ok = history >= c.reddit_zero_min_history_days
        web_evidence.commit_day(store_name, sym, day, density.DayResult(float(k), k, 24.0, False, False),
                                canary_ok=st.canary_ok, trailing_median=trailing_median(store_name, sym, day),
                                now=now, method=METHOD_IDS[store_name], zero_policy="positive_history",
                                history_ok=history_ok)
        stored = dict(store.read_points(store_name, sym))
        coins[sym] = ({"reason": "fetched", "value": stored[day]} if day in stored
                      else {"reason": "zero_unverified", "value": None, "canary_ok": st.canary_ok,
                            "history_days": history})
    missing = Counter(v["reason"] for v in coins.values() if v["reason"] != "fetched")
    doc = {"day": day.isoformat(), "method": METHOD_IDS[store_name], "settled": st.settled,
           "comments_scope": COMMENTS_SCOPE,
           "posts_coverage": {s: round(v, 6) for s, v in sorted(st.posts_coverage.items())},
           "holes": {s: {"hours": round(sum((b - a).total_seconds() for a, b in h) / 3600, 6),
                         "spans": [[a.isoformat(), b.isoformat()] for a, b in h]}
                     for s, h in sorted(st.holes.items()) if h},
           "comments_coverage": round(st.comments_coverage, 6), "threads": st.threads,
           "min_thread_coverage": c.reddit_live_min_thread_coverage, "canary_ok": st.canary_ok,
           "canary_items": st.canary_items, "polls": st.polls, "collected_at": _iso(st.collected_at),
           "attempted": sum(1 for s in q.coins if s not in ambiguous),
           "fetched": sum(1 for v in coins.values() if v["reason"] == "fetched"),
           "missing": dict(sorted(missing.items())), "coins": coins}
    _write(doc, completeness_path(store_name, day))
    return doc
