"""Trickle scheduler core for the PC-side collectors (SPEC Locked pacing rules 1-3, 6, 7; Annex C). Pure; no network.

- `Trickle`: the delay before the next unit, uniform in the configured min..max from a seeded RNG; `plan_run`
  lays units over one PC session and is never faster than the minimum delay, also across a restart.
- `PcSource`: per-source persisted state under `<cache>/attention/_pc_state/<source>.json` (git-ignored):
  the daily budget (X: posts loaded; Reddit: requests) that resets at 00:00 UTC, the adaptive effective budget
  (X: halved after a warning day, floor one unit; doubled once after 7 clean days, up to the configured value),
  and the pause (rest of the UTC day on any warning; until the owner acts on suspension or login-expired).
- `build_queue`: yesterday for every coin first, then older missing days newest first; never today.
- `run_x_unit`: one coin-day through an `XAdapter`: refused before the minimum delay since the last unit (also
  across a restart), pause and budget checked before every page load, never a retry after a warning.

The clock is injected everywhere; nothing here compares the clock to a fixed hour of the day. A clock moved back
never reopens a day's budget or shortens a pause: the counted day is never earlier than the newest one seen.
A state file that exists but is unreadable or invalid raises `PcStateError` (fail closed): the worker (W8e)
must then pause that source and leave the file alone, never delete or reset it.
"""
from __future__ import annotations

import json
import random
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from api.data import cache
from api.data.attention import density
from api.data.attention import pc_adapter as pa
from api.data.attention.web_queries import CollectorConfig

BEHIND_DELAY_S = 20  # first unit after a start when the source is behind (T51 `_behind` pattern)
CLEAN_DAYS_TO_DOUBLE = 7
SOURCE_DELAYS = {"xsearch_web": ("x_query_delay_min_s", "x_query_delay_max_s"),
                 "reddit_web": ("reddit_request_delay_min_s", "reddit_request_delay_max_s")}


STATE_KEYS = ("budget_day", "used", "spent_day", "effective", "clean_days", "activity", "pause_until",
              "pause_reason", "last_unit_at")


class PcStateError(ValueError):
    """A state file exists but is unreadable or invalid; the message never holds the path or the content."""


def _utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("clock must be timezone-aware UTC")
    return now.astimezone(timezone.utc)


def _iso_day(v) -> bool:
    try:
        return isinstance(v, str) and date.fromisoformat(v).isoformat() == v
    except ValueError:
        return False


def _iso_aware(v) -> bool:
    try:
        return isinstance(v, str) and datetime.fromisoformat(v).tzinfo is not None
    except ValueError:
        return False


def _count(v, low: int = 0) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= low


def _valid_state(s) -> bool:
    if not isinstance(s, dict) or set(s) != set(STATE_KEYS):
        return False
    act, reason = s["activity"], s["pause_reason"]
    return all((
        s["budget_day"] is None or _iso_day(s["budget_day"]),
        s["spent_day"] is None or _iso_day(s["spent_day"]),
        _count(s["used"]), _count(s["effective"], 1), _count(s["clean_days"]),
        act is None or (isinstance(act, dict) and set(act) == {"day", "units", "warned"} and _iso_day(act["day"])
                        and _count(act["units"]) and isinstance(act["warned"], bool)),
        reason is None or reason in pa.WARNING_REASONS,
        s["pause_until"] is None or _iso_aware(s["pause_until"]),
        reason is None or reason in pa.OWNER_ACTION_REASONS or s["pause_until"] is not None,
        s["last_unit_at"] is None or _iso_aware(s["last_unit_at"]),
    ))


class Trickle:
    def __init__(self, min_s: float, max_s: float, rng: random.Random):
        if not (0 < min_s <= max_s):
            raise ValueError("need 0 < min delay <= max delay")
        self.min_s, self.max_s, self.rng = float(min_s), float(max_s), rng

    @classmethod
    def for_source(cls, config: CollectorConfig, source: str, rng: random.Random) -> Trickle:
        lo, hi = SOURCE_DELAYS[source]
        return cls(getattr(config, lo), getattr(config, hi), rng)

    def next_delay(self) -> float:
        return self.rng.uniform(self.min_s, self.max_s)

    def first_due(self, start: datetime, last_unit_at: datetime | None) -> datetime:
        """`last_unit_at` is when the previous unit ENDED (`PcSource.record_unit` stamps the end)."""
        due = _utc(start) + timedelta(seconds=BEHIND_DELAY_S)
        if last_unit_at is not None:
            due = max(due, _utc(last_unit_at) + timedelta(seconds=self.min_s))
        return due

    def next_due(self, last_unit_end: datetime) -> datetime:
        """The delay runs from the end of the previous unit, so idle time is never below the minimum."""
        return _utc(last_unit_end) + timedelta(seconds=self.next_delay())


def plan_run(trickle: Trickle, *, start: datetime, stop: datetime,
             last_unit_at: datetime | None = None) -> list[datetime]:
    """Unit start times for one PC session [start, stop): the same pace whatever was missed before.

    Units are treated as instantaneous here; the worker passes each unit's end to `next_due`.
    """
    out: list[datetime] = []
    due = trickle.first_due(start, last_unit_at)
    while due < _utc(stop):
        out.append(due)
        due = trickle.next_due(due)
    return out


def build_queue(symbols: Iterable[str], *, now: datetime, stored: Mapping[str, set[date]],
                backfill_days: int, rotation: bool = False) -> list[tuple[str, date]]:
    """(symbol, day) work items: yesterday for every coin, then older missing days newest first.

    `rotation` (X rotation mode, SPEC rule 9): yesterday's items run oldest newest-stored day first, coins with
    nothing stored before all others; ties keep the given symbol order.
    """
    syms = list(symbols)
    yesterday = density.completed_day(now)
    out: list[tuple[str, date]] = []
    for back in range(backfill_days + 1):
        day = yesterday - timedelta(days=back)
        items = [(s, day) for s in syms if day not in stored.get(s, set())]
        if rotation and back == 0:
            items.sort(key=lambda item: max(stored.get(item[0]) or {date.min}))
        out += items
    return out


def state_path(source: str) -> Path:
    if source not in SOURCE_DELAYS:
        raise ValueError("unknown source")
    return cache.CACHE_ROOT / "attention" / "_pc_state" / f"{source}.json"


class PcSource:
    """Budget, adaptive budget and pause for one source; every change is written through to disk."""

    def __init__(self, source: str, *, configured_budget: int, floor: int, adaptive: bool,
                 clock: Callable[[], datetime]):
        if not (0 < floor <= configured_budget):
            raise ValueError("need 0 < floor <= configured budget")
        self.source, self.configured, self.floor, self.adaptive, self.clock = (
            source, configured_budget, floor, adaptive, clock)
        self.path = state_path(source)
        self._s = self._load()

    # --- persistence ---
    def _load(self) -> dict:
        if not self.path.exists():
            # "activity": {"day", "units", "warned"} for the newest day with activity
            return {"budget_day": None, "used": 0, "spent_day": None, "effective": self.configured,
                    "clean_days": 0, "activity": None, "pause_until": None, "pause_reason": None,
                    "last_unit_at": None}
        try:
            s = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise PcStateError("state file unreadable") from None
        if not _valid_state(s):
            raise PcStateError("state file invalid")
        s["effective"] = max(self.floor, min(s["effective"], self.configured))
        return s

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        cache._atomic_write_json(self._s, self.path)

    def _today(self) -> str:
        """The UTC day being counted: never earlier than the newest day already counted (a clock moved back)."""
        today = _utc(self.clock()).date().isoformat()
        last = self._s["budget_day"]
        return max(today, last) if last else today

    def _roll(self) -> None:
        """Close the last activity day once a later UTC day starts; reset the day's budget count."""
        today, s, changed = self._today(), self._s, False
        act = s["activity"]
        if act and act["day"] < today:
            if self.adaptive and act["warned"]:
                s["effective"], s["clean_days"] = max(self.floor, s["effective"] // 2), 0
            elif self.adaptive and act["units"] > 0:
                s["clean_days"] += 1
                if s["clean_days"] >= CLEAN_DAYS_TO_DOUBLE:
                    s["effective"], s["clean_days"] = min(self.configured, s["effective"] * 2), 0
            s["activity"], changed = None, True
        if s["budget_day"] != today:
            s["budget_day"], s["used"], changed = today, 0, True
        if changed:
            self._save()

    def _activity(self) -> dict:
        today = self._today()
        if not self._s["activity"]:
            self._s["activity"] = {"day": today, "units": 0, "warned": False}
        return self._s["activity"]

    # --- budget ---
    @property
    def used(self) -> int:
        self._roll()
        return self._s["used"]

    def effective_budget(self) -> int:
        self._roll()
        return self._s["effective"]

    def remaining(self) -> int:
        self._roll()
        return max(0, self._s["effective"] - self._s["used"])

    def can_spend(self, n: int) -> bool:
        return not self.budget_spent() and n <= self.remaining()

    def spend(self, n: int) -> None:
        """Count loaded items (posts or requests). Refused when it would exceed the effective budget."""
        if not isinstance(n, int) or n < 0:
            raise ValueError("count must be a non-negative int")
        if n > self.remaining():
            raise pa.BudgetSpent()
        self._roll()
        self._s["used"] += n
        self._save()

    def record_loaded(self, n: int) -> None:
        """Count items a load already returned, kept or dropped, even past the budget (X stops after it)."""
        if not isinstance(n, int) or n < 0:
            raise ValueError("count must be a non-negative int")
        self._roll()
        self._s["used"] += n
        self._save()

    def mark_spent(self) -> None:
        """The next load does not fit: the source stops for the rest of the UTC day (not a warning)."""
        self._roll()
        self._s["spent_day"] = self._today()
        self._save()

    def budget_spent(self) -> bool:
        self._roll()
        return self._s["spent_day"] == self._today() or self._s["used"] >= self._s["effective"]

    # --- units and warnings ---
    def record_unit(self) -> None:
        """A unit ran (counts toward a clean day); stamps its end for the next delay."""
        self._roll()
        self._activity()["units"] += 1
        self._s["last_unit_at"] = _utc(self.clock()).isoformat()
        self._save()

    def stamp_attempt(self) -> None:
        """A request was sent but the unit failed: the next delay still runs from now."""
        self._s["last_unit_at"] = _utc(self.clock()).isoformat()
        self._save()

    def last_unit_at(self) -> datetime | None:
        v = self._s["last_unit_at"]
        return datetime.fromisoformat(v) if v else None

    def earliest_next(self, min_s: float) -> datetime | None:
        """When the next unit may start: the end of the last unit or attempt plus the minimum delay."""
        last = self.last_unit_at()
        return None if last is None else last + timedelta(seconds=min_s)

    def warn(self, reason: str) -> None:
        """Pause on a warning: rest of the UTC day, or until `owner_reset` for suspension and login-expired.

        An active owner-action pause is never replaced by a shorter one.
        """
        if reason not in pa.WARNING_REASONS:
            raise ValueError("unknown warning reason")
        self._roll()
        self._activity()["warned"] = True
        if self._s["pause_reason"] in pa.OWNER_ACTION_REASONS:
            self._save()
            return
        if reason in pa.OWNER_ACTION_REASONS:
            until = None
        else:
            until = datetime.combine(date.fromisoformat(self._today()) + timedelta(days=1), datetime.min.time(),
                                     tzinfo=timezone.utc).isoformat()
        self._s["pause_until"], self._s["pause_reason"] = until, reason
        self._save()

    def is_paused(self) -> bool:
        reason = self._s["pause_reason"]
        if reason is None:
            return False
        if reason in pa.OWNER_ACTION_REASONS:
            return True
        return _utc(self.clock()) < datetime.fromisoformat(self._s["pause_until"])

    def pause_reason(self) -> str | None:
        return self._s["pause_reason"] if self.is_paused() else None

    def owner_reset(self) -> None:
        """The owner acted (re-login, new account): lift an owner-action pause."""
        self._s["pause_until"], self._s["pause_reason"] = None, None
        self._save()


def _kept(raw: list[pa.Post], start: datetime, end: datetime) -> list[pa.Post]:
    return density.dedupe([p for p in raw if start <= p.created_at < end])


@dataclass(frozen=True)
class UnitOutcome:
    result: density.DayResult | None
    posts_loaded: int
    pages: int
    # "done", "pagecap", "budget_spent", "paused", "too_early", "page_overrun", or a CollectorError reason
    stop: str


def run_x_unit(adapter: pa.XAdapter, src: PcSource, config: CollectorConfig, *, symbol: str, day: date, query: str,
               rng: random.Random, sleep: Callable[[float], None]) -> UnitOutcome:
    """Collect one X coin-day (SPEC A.1): at most `x_page_cap` pages, 5-15 s apart, inside the daily budget.

    Nothing is sent when the source is paused or the minimum delay since the last unit has not passed. A page
    with more posts than the adapter's declared `page_size` is counted in full and stops X for the UTC day.
    """
    size = adapter.page_size
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ValueError("adapter page_size must be a positive int")
    if src.is_paused():
        return UnitOutcome(None, 0, 0, "paused")
    due = src.earliest_next(config.x_query_delay_min_s)
    if due is not None and _utc(src.clock()) < due:
        return UnitOutcome(None, 0, 0, "too_early")
    start, end = density.window(day)
    raw: list[pa.Post] = []
    loaded = pages = 0
    reached = limit = False
    stop = "done"
    for page in range(config.x_page_cap):
        if src.is_paused():
            stop = "paused"
            break
        if not src.can_spend(size):
            src.mark_spent()
            limit, stop = True, "budget_spent"
            break
        if page:
            sleep(rng.uniform(config.x_page_gap_min_s, config.x_page_gap_max_s))
        try:
            got = adapter.search_page(query, start, end, page)
        except pa.CollectorError as exc:
            src.stamp_attempt()
            if exc.warning:
                src.warn(exc.reason)
            return UnitOutcome(None, loaded, pages, exc.reason)
        except Exception:
            src.stamp_attempt()
            raise
        pages += 1
        loaded += len(got.posts)
        src.record_loaded(len(got.posts))
        if len(got.posts) > size:
            src.mark_spent()
            src.stamp_attempt()
            return UnitOutcome(None, loaded, pages, "page_overrun")
        raw += got.posts
        if len(_kept(raw, start, end)) >= config.x_sample_n:
            break
        if not got.has_more or any(p.created_at < start for p in got.posts):
            reached = True
            break
    else:
        limit, stop = True, "pagecap"
    if pages == 0:
        return UnitOutcome(None, 0, 0, stop)
    src.record_unit()
    times = [p.created_at for p in _kept(raw, start, end)]
    result = density.day_value(day, times, n_target=config.x_sample_n, n_min=config.x_sample_min,
                               window_start_reached=reached, limit_hit=limit)
    return UnitOutcome(result, loaded, pages, stop)
