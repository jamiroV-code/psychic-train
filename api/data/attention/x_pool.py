"""SPEC rule 18, AC46, AC49-AC54: the X account pool (design A), the daily cross-account canary and one coin-day
unit across the pool. Pure logic over injected readers, clock, RNG and sleep; no network.

- Selection is ours: the least recently used of the usable accounts (active, not locked, not suspect), ties broken
  by registration order (the order of the configured labels), never alphabetical; each choice is logged by label.
- States: active; locked (a rate limit locks that account until the next 00:00 UTC, it stays active);
  inactive (ban or logout, with an owner alert naming the label, until the owner acts); suspect (the canary saw a
  smaller result, until the owner clears it). The state file under `<cache>/attention/_pc_state/x_pool.json`
  survives a restart; the library's own locks are never reset (a crash's in-use lock expires by itself).
- A unit is fetched by one account end to end. A ban, logout or lock restarts it once on another account
  (`x_unit_max_restarts`): the aborted attempt's tweets are discarded, its reads still count against the GLOBAL
  budget, and a second failure leaves the coin-day missing (`account_failed`). Zero usable accounts pause X for
  the rest of the UTC day; budget, sample size and spacing are global (one `PcSource` for the whole pool).
- Fail closed: a None, empty or short result, an exception or a block page is missing with a reason, never 0.
  An empty page after a FULL page, or a page of repeated ids, is a stalled cursor (`x_window.cursor_end`), never
  an exact count. An exact count from an exhausted cursor needs the unit's account among the accounts that passed
  today's canary (`canary_labels`), else it is missing `account_not_canaried`.
  Cloudflare and HTML blocks pause the day (the curl fallback of rule 19 first when the owner flag is on: one
  retry per unit and one per daily canary; the next block pauses the day for the whole pool);
  an inconclusive canary sits the canaried accounts out for the UTC day while the others continue (no account
  passed, so their exact counts are missing); three consecutive parse, 404 or transaction-id failures, or a
  small-page parse drop, count toward `layout_changed`; a parse drop (`x_reader.parse_drop`) stops X at once.
- Quality over speed: nothing is cut for a time budget; only the safety limits above stop reading.
"""
from __future__ import annotations

import json
import random
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from api.data import cache
from api.data.attention import density, x_density, x_filters, x_raw, x_window
from api.data.attention import pc_pace as pp
from api.data.attention import x_reader as xr
from api.data.attention.web_queries import CollectorConfig

LABEL_RE = re.compile(r"[a-z0-9_]{1,24}")
STATES = ("active", "inactive", "suspect")
DAY_PAUSE_REASONS = ("no_usable_account", "cloudflare_block", "html_block", "empty_results", "canary_disagree")
SUSPECT_REASON = "x_account_suspect"
ALERT_REASONS = ("x_account_suspended", "x_login_required", SUSPECT_REASON)
DRIFT_STOP = 3
SINGLE_ACCOUNT_NOTE = "comparison skipped: single active account"
TOP_KEYS = {"accounts", "alerts", "pause_until", "pause_reason", "stopped", "drift_streak", "canary_day",
            "canary_note", "canary_labels", "curl_uses", "curl_last_use"}
ACCOUNT_KEYS = {"state", "reason", "last_used", "lock_until", "last_canary", "suspect_since"}


class XPoolStateError(ValueError):
    """The pool state file is unreadable, invalid or names an unknown label; never holds the content."""


def _utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("clock must be timezone-aware UTC")
    return now.astimezone(timezone.utc)


def _iso(v) -> bool:
    try:
        return v is None or (isinstance(v, str) and datetime.fromisoformat(v).tzinfo is not None)
    except ValueError:
        return False


def _fresh_account() -> dict:
    return dict.fromkeys(ACCOUNT_KEYS) | {"state": "active"}


def _valid(s) -> bool:
    if not isinstance(s, dict) or set(s) != TOP_KEYS or not isinstance(s["accounts"], dict):
        return False
    for a in s["accounts"].values():
        if not (isinstance(a, dict) and set(a) == ACCOUNT_KEYS and a["state"] in STATES
                and all(_iso(a[k]) for k in ("last_used", "lock_until", "last_canary", "suspect_since"))):
            return False
    return all((
        isinstance(s["alerts"], list), _iso(s["pause_until"]), _iso(s["curl_last_use"]),
        s["pause_reason"] is None or s["pause_reason"] in DAY_PAUSE_REASONS,
        s["stopped"] in (None, "layout_changed"),
        isinstance(s["drift_streak"], int) and isinstance(s["curl_uses"], int),
        isinstance(s["canary_labels"], list) and all(isinstance(x, str) for x in s["canary_labels"]),
    ))


@dataclass(frozen=True)
class Selection:
    label: str
    reason: str


class XPool:
    """Our persisted account state; `labels` is the configured registration order."""

    def __init__(self, labels: list[str], *, clock: Callable[[], datetime]):
        if not labels or len(set(labels)) != len(labels) or not all(
                isinstance(x, str) and LABEL_RE.fullmatch(x) for x in labels):
            raise ValueError("labels must be unique opaque labels")
        self.labels, self.clock = list(labels), clock
        self.log: list[str] = []
        self.path = cache.CACHE_ROOT / "attention" / "_pc_state" / "x_pool.json"
        self._s = self._load()

    # --- persistence ---
    def _load(self) -> dict:
        if not self.path.exists():
            s = {"accounts": {}, "alerts": [], "pause_until": None, "pause_reason": None, "stopped": None,
                 "drift_streak": 0, "canary_day": None, "canary_note": None, "canary_labels": [], "curl_uses": 0,
                 "curl_last_use": None}
        else:
            try:
                s = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise XPoolStateError("pool state unreadable") from None
            if isinstance(s, dict):
                s.setdefault("canary_labels", [])  # a state file from before T190: no account passed yet
            if not _valid(s):
                raise XPoolStateError("pool state invalid")
            if set(s["accounts"]) - set(self.labels):
                raise XPoolStateError("pool state names a label that is not configured")
        for label in self.labels:
            s["accounts"].setdefault(label, _fresh_account())
        return s

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        cache._atomic_write_json(self._s, self.path)

    def _now(self) -> datetime:
        return _utc(self.clock())

    def _next_midnight(self) -> str:
        return datetime.combine(self._now().date() + timedelta(days=1), time(0), tzinfo=timezone.utc).isoformat()

    def _acct(self, label: str) -> dict:
        if label not in self._s["accounts"]:
            raise ValueError("unknown label")
        return self._s["accounts"][label]

    # --- accounts ---
    def account_state(self, label: str) -> tuple[str, str | None]:
        a = self._acct(label)
        if a["state"] != "active":
            return a["state"], a["reason"]
        if a["lock_until"] and self._now() < datetime.fromisoformat(a["lock_until"]):
            return "locked", "rate_limited"
        return "active", None

    def usable(self) -> list[str]:
        return [x for x in self.labels if self.account_state(x)[0] == "active"]

    def select(self) -> Selection | None:
        """Least recently used usable account; never-used first; ties by registration order."""
        cands = self.usable()
        if not cands:
            return None
        last = {x: self._acct(x)["last_used"] or "" for x in cands}
        pick = min(cands, key=lambda x: (last[x], self.labels.index(x)))
        tie = sum(1 for x in cands if last[x] == last[pick]) > 1
        reason = "least recently used" + ("; tie by registration order" if tie else "")
        self.log.append(f"x pool: selected {pick} ({reason})")
        return Selection(pick, reason)

    def mark_used(self, label: str) -> None:
        self._acct(label)["last_used"] = self._now().isoformat()
        self._save()

    def lock_for_day(self, label: str) -> None:
        """A rate limit: no retry on this account until the next 00:00 UTC; it stays active."""
        self._acct(label)["lock_until"] = self._next_midnight()
        self._save()

    def _alert(self, label: str, reason: str) -> None:
        if not any(a["label"] == label and a["reason"] == reason for a in self._s["alerts"]):
            self._s["alerts"].append({"label": label, "reason": reason, "at": self._now().isoformat()})

    def mark_inactive(self, label: str, reason: str) -> None:
        if reason not in ("x_account_suspended", "x_login_required"):
            raise ValueError("unknown inactive reason")
        a = self._acct(label)
        a["state"], a["reason"] = "inactive", reason
        self._alert(label, reason)
        self._save()

    def flag_suspect(self, label: str) -> None:
        """Excluded from selection until the owner clears it; its stored units get `suspect_since`."""
        a, now = self._acct(label), self._now()
        a["state"], a["reason"], a["suspect_since"] = "suspect", SUSPECT_REASON, now.isoformat()
        self._alert(label, SUSPECT_REASON)
        self._save()
        x_raw.mark_suspect(label, now)

    def owner_clear(self, label: str) -> None:
        """The owner acted on this account (fresh cookies, or cleared a suspect flag)."""
        a = self._acct(label)
        a["state"], a["reason"], a["suspect_since"] = "active", None, None
        self._s["alerts"] = [x for x in self._s["alerts"] if x["label"] != label]
        self._save()

    def alerts(self) -> list[dict]:
        return [dict(a) for a in self._s["alerts"]]

    # --- pause, stop, drift, fallback ---
    def pause_day(self, reason: str) -> None:
        if reason not in DAY_PAUSE_REASONS:
            raise ValueError("unknown pause reason")
        self._s["pause_until"], self._s["pause_reason"] = self._next_midnight(), reason
        self._save()

    def stop(self, reason: str = "layout_changed") -> None:
        self._s["stopped"] = reason
        self._save()

    def stopped_reason(self) -> str | None:
        return self._s["stopped"]

    def owner_clear_stop(self) -> None:
        """The owner reviewed and installed a new pin: X may run again."""
        self._s["stopped"], self._s["drift_streak"] = None, 0
        self._save()

    def is_paused(self) -> bool:
        if self._s["stopped"]:
            return True
        until = self._s["pause_until"]
        return until is not None and self._now() < datetime.fromisoformat(until)

    def pause_reason(self) -> str | None:
        if self._s["stopped"]:
            return self._s["stopped"]
        return self._s["pause_reason"] if self.is_paused() else None

    def note_drift(self) -> int:
        self._s["drift_streak"] += 1
        if self._s["drift_streak"] >= DRIFT_STOP:
            self._s["stopped"] = "layout_changed"
        self._save()
        return self._s["drift_streak"]

    def clear_drift(self) -> None:
        if self._s["drift_streak"]:
            self._s["drift_streak"] = 0
            self._save()

    def note_curl(self) -> None:
        self._s["curl_uses"] += 1
        self._s["curl_last_use"] = self._now().isoformat()
        self._save()

    # --- canary ---
    def set_canary_passed(self, note: str | None = None, *, labels) -> None:
        """Today's canary passed; `labels` are the accounts that passed it (an exact count needs one of them)."""
        if set(labels) - set(self.labels):
            raise ValueError("unknown label")
        self._s["canary_day"], self._s["canary_note"] = self._now().date().isoformat(), note
        self._s["canary_labels"] = [x for x in self.labels if x in set(labels)]
        self._save()

    def canary_passed_today(self) -> bool:
        return self._s["canary_day"] == self._now().date().isoformat()

    def canary_labels(self) -> list[str]:
        """The accounts that passed today's canary; empty on another day."""
        return list(self._s["canary_labels"]) if self.canary_passed_today() else []

    def canary_accounts(self) -> list[str]:
        """The least recently canaried usable accounts: two, or three when there are three or more (a majority)."""
        cands = sorted(self.usable(), key=lambda x: (self._acct(x)["last_canary"] or "", self.labels.index(x)))
        return cands[:3] if len(cands) >= 3 else cands

    def mark_canaried(self, labels) -> None:
        for x in labels:
            self._acct(x)["last_canary"] = self._now().isoformat()
        self._save()

    def health(self) -> dict:
        """Active over total and per-account label, state and last use; never a secret."""
        accts = []
        for x in self.labels:
            state, reason = self.account_state(x)
            accts.append({"label": x, "state": state, "reason": reason, "last_used": self._acct(x)["last_used"]})
        return {"active": sum(1 for a in accts if a["state"] == "active"), "total": len(self.labels),
                "accounts": accts, "pause_reason": self.pause_reason(), "drift_streak": self._s["drift_streak"],
                "canary_note": self._s["canary_note"], "curl_uses": self._s["curl_uses"],
                "curl_last_use": self._s["curl_last_use"]}


def canary_window(now: datetime) -> tuple[datetime, datetime]:
    """A fixed past hour, the last hour of the previous UTC day: both window syntaxes can express it (the date
    form as `since:D-1 until:D`, newest first), and it is the same for every account and every run of the day."""
    end = datetime.combine(_utc(now).date(), time(0), tzinfo=timezone.utc)
    return end - timedelta(hours=1), end


def canary_query(config: CollectorConfig, start: datetime, end: datetime) -> str:
    if config.x_window_syntax == "since_time":
        window = f"since_time:{int(start.timestamp())} until_time:{int(end.timestamp())}"
    else:
        window = f"since:{start.date().isoformat()} until:{end.date().isoformat()}"
    return f"{config.x_canary_query} {window}"


def _agree(a: set, b: set, tol: float, min_overlap: float) -> bool:
    hi, lo = max(len(a), len(b)), min(len(a), len(b))
    if hi == 0:
        return True
    if (hi - lo) / hi > tol or lo == 0:
        return False
    return len(a & b) / lo >= min_overlap


def compare_canary(results: Mapping[str, set], order: list[str], tol: float,
                   min_overlap: float) -> tuple[list[str], bool]:
    """(suspects, inconclusive). Two accounts: on disagreement the smaller result is suspect, equal sizes are
    inconclusive. Three or more: an account that agrees with fewer than half of the others is suspect; when no
    account has that support the canary is inconclusive."""
    labels = [x for x in order if x in results]
    if len(labels) < 2:
        return [], False
    if len(labels) == 2:
        a, b = labels
        if _agree(results[a], results[b], tol, min_overlap):
            return [], False
        if len(results[a]) == len(results[b]):
            return [], True
        return [a if len(results[a]) < len(results[b]) else b], False
    need = (len(labels) - 1) / 2
    support = {x: sum(_agree(results[x], results[o], tol, min_overlap) for o in labels if o != x) for x in labels}
    if not any(v >= need for v in support.values()):
        return [], True
    return [x for x in labels if support[x] < need], False


@dataclass(frozen=True)
class CanaryOutcome:
    passed: bool
    suspects: list[str] = field(default_factory=list)
    reason: str | None = None


def _account_failure(pool: XPool, label: str, reader: xr.XReader, failure: xr.ReaderFailure) -> str:
    """Apply a NoAccountError's cause to our state; return `restart` or the unit's missing reason."""
    cause, reason = xr.no_account_cause(reader.pool_row(), pool._now())
    if cause == "inactive":
        pool.mark_inactive(label, reason)
        return "restart"
    if cause == "locked":
        pool.lock_for_day(label)
        return "restart"
    return reason


Fallback = Callable[[str, str, dict, int], "xr.RawPage | None"]


def _on_block(pool: XPool, f: xr.ReaderFailure, config: CollectorConfig, fallback: Fallback | None, state: dict,
              label: str, query: str, kv: dict, page_no: int, events: list) -> tuple[xr.RawPage | None, str | None]:
    """A Cloudflare or HTML block: (the fallback's page, None) after the one curl retry of this unit or canary
    (`state["curl_retried"]`), else (None, block reason) with the UTC day paused for the whole pool."""
    block = f"{f.abort}_block"
    decision = xr.fallback_decision(f.abort, allow_curl=config.x_allow_curl_backend, retried=state["curl_retried"])
    if decision == "curl_retry" and fallback is not None:
        state["curl_retried"] = True
        pool.note_curl()
        try:
            raw = fallback(label, query, kv, page_no)
        except xr.ReaderFailure:
            events.append({"backend": "curl", "reason": block, "outcome": "blocked"})
            pool.pause_day(block)
            return None, block
        events.append({"backend": "curl", "reason": block, "outcome": "ok"})
        return raw, None
    pool.pause_day(block)
    return None, block


def _is_block(f: xr.ReaderFailure) -> bool:
    return f.kind == "abort" and f.abort in ("cloudflare", "html")


def run_daily_canary(pool: XPool, readers: Mapping[str, xr.XReader], src: pp.PcSource, config: CollectorConfig, *,
                     rng: random.Random, sleep: Callable[[float], None],
                     fallback: Fallback | None = None) -> CanaryOutcome:
    """The day's canary before any unit: one page of the canary query over the last complete hour on the least
    recently canaried accounts, read at the global spacing and counted against the global budget. A block goes
    through the same fallback rule as a unit read (one curl retry for the canary, then the day pauses)."""
    if pool.canary_passed_today():
        return CanaryOutcome(True, reason="already_passed")
    if pool.is_paused() or src.is_paused():
        return CanaryOutcome(False, reason="paused")
    due = src.earliest_next(config.x_query_delay_min_s)
    if due is not None and _utc(src.clock()) < due:
        return CanaryOutcome(False, reason="too_early")
    labels = pool.canary_accounts()
    start, end = canary_window(pool._now())
    query, kv = canary_query(config, start, end), x_window.search_kv()
    results: dict[str, set] = {}
    state, events = {"curl_retried": False}, []
    for i, label in enumerate(labels):
        if not src.can_spend(xr.PAGE_ENTRIES):
            src.mark_spent()
            return CanaryOutcome(False, reason="budget_spent")
        if i:
            sleep(rng.uniform(config.x_query_delay_min_s, config.x_query_delay_max_s))
        pool.mark_used(label)
        reader = readers[label]
        try:
            raw = reader.search_raw(query, kv, 0)
        except xr.ReaderFailure as f:
            src.stamp_attempt()
            if not _is_block(f):
                if f.kind == "no_account":
                    _account_failure(pool, label, reader, f)
                continue
            raw, block = _on_block(pool, f, config, fallback, state, label, query, kv, 0, events)
            if block:
                return CanaryOutcome(False, reason=block)
        if raw is None:
            src.stamp_attempt()
            results[label] = set()
            continue
        src.record_loaded(len(raw.entry_ids))
        src.record_unit()
        results[label] = xr.canary_ids(reader.parse_tweets(raw.body), start, end)
    pool.mark_canaried(list(results))
    if not results:
        pool.pause_day("no_usable_account")
        return CanaryOutcome(False, reason="no_usable_account")
    suspects, note = [], SINGLE_ACCOUNT_NOTE if len(results) == 1 else None
    if len(results) >= 2:
        suspects, inconclusive = compare_canary(results, labels, config.x_canary_tolerance,
                                                config.x_canary_min_overlap)
        if inconclusive:
            # No account can be blamed: those canaried sit out the UTC day (not suspect), the others continue.
            for x in results:
                pool.lock_for_day(x)
            if not pool.usable():
                pool.pause_day("canary_disagree")
                return CanaryOutcome(False, reason="canary_disagree")
            pool.set_canary_passed(f"inconclusive: {', '.join(results)} sit out the day", labels=[])
            return CanaryOutcome(True, reason="canary_disagree")
        for x in suspects:
            pool.flag_suspect(x)
    if max(len(results[x]) for x in results if x not in suspects) < config.x_canary_min_results:
        pool.pause_day("empty_results")
        return CanaryOutcome(False, suspects, "empty_results")
    pool.set_canary_passed(note, labels=[x for x in results if x not in suspects])
    return CanaryOutcome(True, suspects)


@dataclass(frozen=True)
class XUnitOutcome:
    result: density.DayResult | None
    # a stop of x_window.stop_reason when a value was found, else the missing reason
    reason: str
    label: str | None = None
    attempts: int = 0
    restarts: int = 0
    row: dict | None = None
    pages: int = 0
    reads: int = 0


@dataclass
class _Attempt:
    status: str = "ok"  # ok, restart, stop
    reason: str = ""
    tweets: list = field(default_factory=list)
    n_read: int = 0
    events: list = field(default_factory=list)
    seen: set = field(default_factory=set)  # entry ids read by this attempt
    last_entries: int | None = None  # entries on the last non-empty page
    raw_oldest: datetime | None = None  # oldest raw entry time, when the reader exposes it

    def oldest(self) -> datetime | None:
        return x_density.oldest_read(self.tweets, self.raw_oldest)


def _drift(pool: XPool) -> str:
    return "layout_changed" if pool.note_drift() >= DRIFT_STOP else "drift"


def _run_attempt(pool, reader, src, config, *, label, attempt, symbol, day, query, rng, sleep, fallback, collected_at,
                 counts) -> _Attempt:
    out, kv = _Attempt(), x_window.search_kv()
    for page_no in range(config.x_page_cap):
        if pool.is_paused() or src.is_paused():
            return _Attempt("stop", "paused")
        if not src.can_spend(xr.PAGE_ENTRIES):
            src.mark_spent()
            return _Attempt("stop", "budget_spent")
        if page_no:
            sleep(rng.uniform(config.x_page_gap_min_s, config.x_page_gap_max_s))
        backend = "default"
        try:
            raw = reader.search_raw(query, kv, page_no)
        except xr.ReaderFailure as f:
            src.stamp_attempt()
            if _is_block(f):
                raw, block = _on_block(pool, f, config, fallback, counts, label, query, kv, page_no, out.events)
                if block:
                    return _Attempt("stop", block, events=out.events)
                backend = "curl"
            elif f.kind == "no_account":
                step = _account_failure(pool, label, reader, f)
                return _Attempt("restart" if step == "restart" else "stop", step)
            elif f.kind in xr.DRIFT_KINDS or f.kind == "abort":
                return _Attempt("stop", _drift(pool))
            else:
                return _Attempt("stop", "failed")
        except Exception:
            src.stamp_attempt()
            raise
        if raw is None:
            raw = xr.RawPage({}, ())  # rule 20b: None is not an error, it is an exhausted cursor
        n = len(raw.entry_ids)
        src.record_loaded(n)
        counts["reads"] += n
        counts["pages"] += 1 + raw.retries
        x_raw.write_page(symbol, day, attempt=attempt, page=page_no, body=raw.body, entry_ids=raw.entry_ids,
                         retries=raw.retries, headers=raw.headers(), collected_at=collected_at,
                         parser_version=xr.PARSER_VERSION, reader_version=reader.version,
                         reader_commit=reader.commit, backend=backend,
                         scrub_names={name: label for name in reader.account_names}, entry_times=raw.entry_times)
        end = x_window.cursor_end(raw.entry_ids, seen=out.seen, last_entries=out.last_entries,
                                  page_size=xr.PAGE_ENTRIES)
        if end:
            # Exhausted (exact, given the account passed today's canary) or stalled (never exact).
            out.reason = x_window.stop_reason(pages=page_no + 1, entries_read=out.n_read, oldest_read=out.oldest(),
                                              day=day, sample_n=config.x_sample_n, page_cap=config.x_page_cap,
                                              exhausted=end == "cursor_exhausted", stalled=end == x_window.STALLED)
            return out
        try:
            tweets = reader.parse_tweets(raw.body)
        except Exception:  # noqa: BLE001 - a parse failure is drift, whatever the library raised
            src.stamp_attempt()
            return _Attempt("stop", _drift(pool))
        # Per page; a unit-wide rate can only exceed the threshold when one of its pages does.
        if xr.parse_drop(entries=n, parsed=len(tweets), threshold=config.x_parse_drop_threshold):
            pool.stop("layout_changed")
            src.stamp_attempt()
            return _Attempt("stop", "layout_changed")
        if xr.small_page_drop(entries=n, parsed=len(tweets)):
            src.stamp_attempt()
            return _Attempt("stop", _drift(pool))
        pool.clear_drift()
        out.tweets += tweets
        out.n_read += n
        out.seen.update(raw.entry_ids)
        out.last_entries = n
        if raw.entry_times:
            out.raw_oldest = min(_utc(t) for t in (*raw.entry_times, *([out.raw_oldest] if out.raw_oldest else [])))
        stop = x_window.stop_reason(pages=page_no + 1, entries_read=out.n_read, oldest_read=out.oldest(), day=day,
                                    sample_n=config.x_sample_n, page_cap=config.x_page_cap)
        if stop:
            out.reason = stop
            return out
    return out


def run_unit(pool: XPool, readers: Mapping[str, xr.XReader], src: pp.PcSource, config: CollectorConfig, *,
             symbol: str, day: date, query: str, coin: x_filters.Coin, policy: x_filters.FilterPolicy,
             rng: random.Random, sleep: Callable[[float], None],
             fallback: Fallback | None = None) -> XUnitOutcome:
    """One X coin-day across the pool: one account end to end, at most `x_unit_max_restarts` restarts.

    `fallback(label, query, kv, page)` is the owner-allowed curl process of rule 19 (W8d2); it is called at most
    once per unit (restarts included) and only when `fallback_decision` says so; the next block pauses the day. On a value the raw pages are marked
    complete and the X evidence row is built by `x_raw.reparse` from them, so a re-parse gives the same row.
    """
    if pool.is_paused() or src.is_paused():
        return XUnitOutcome(None, "paused")
    if not pool.canary_passed_today():
        return XUnitOutcome(None, "canary_pending")
    due = src.earliest_next(config.x_query_delay_min_s)
    now = _utc(src.clock())
    if due is not None and now < due:
        return XUnitOutcome(None, "too_early")
    counts = {"reads": 0, "pages": 0, "curl_retried": False}  # one curl retry per unit, across restarts
    attempts = restarts = 0
    label = None

    def done(result, reason, row=None):
        if result is None and counts["pages"]:
            src.stamp_attempt()  # requests were sent: the next unit still waits the minimum delay
        return XUnitOutcome(result, reason, label, attempts, restarts, row, counts["pages"], counts["reads"])

    while attempts < 1 + config.x_unit_max_restarts:
        sel = pool.select()
        if sel is None:
            pool.pause_day("no_usable_account")
            return done(None, "no_usable_account")
        if attempts:
            restarts += 1
        attempts += 1
        label, reader = sel.label, readers[sel.label]
        pool.mark_used(label)
        att = _run_attempt(pool, reader, src, config, label=label, attempt=attempts, symbol=symbol, day=day,
                           query=query, rng=rng, sleep=sleep, fallback=fallback, collected_at=now, counts=counts)
        if att.status == "restart":
            continue
        if att.status == "stop":
            return done(None, att.reason)
        src.record_unit()
        canary_ok = label in pool.canary_labels()
        summary = x_density.summarize(day, att.tweets, n_read=att.n_read,
                                      window_start_reached=att.reason in x_window.COMPLETE_STOPS,
                                      page_cap_hit=att.reason == "page_cap", canary_ok=canary_ok, coin=coin,
                                      policy=policy, n_target=config.x_sample_n, n_min=config.x_sample_min, now=now,
                                      cursor_exhausted=att.reason == "cursor_exhausted",
                                      cursor_stalled=att.reason == x_window.STALLED, raw_oldest=att.raw_oldest)
        if summary.result is None:
            return done(None, summary.missing_reason)
        meta = {"attempt": attempts, "label": label, "attempts": attempts, "restarts": restarts,
                "backend_events": att.events, "overhead_requests": reader.overhead_requests, "canary_ok": canary_ok}
        x_raw.mark_complete(symbol, day, meta, run=x_raw.run_id(now))
        row = x_raw.reparse(symbol, day, parse=reader.parse_tweets, coin=coin, cfg=config,
                            parser_version=xr.PARSER_VERSION, policy=policy)
        x_raw.write_x_row(symbol, row)
        return done(summary.result, att.reason, row)
    return done(None, "account_failed")
