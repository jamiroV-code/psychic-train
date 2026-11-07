"""SPEC rule 18, AC46, AC49-AC54: the X account pool (design A), the daily cross-account canary and one coin-day
unit across the pool. Pure logic over injected readers, clock, RNG and sleep; no network.

- Selection is ours: the least recently used of the usable accounts (active, not locked, not suspect), ties broken
  by registration order (the order of the configured labels), never alphabetical; each choice is logged by label.
- States: active; locked (a rate limit locks that account until the next 00:00 UTC, it stays active; the
  library's bare in-flight lock, left by a killed process, locks it only until that lock's end plus
  `LOCK_MARGIN_S`); inactive (ban or logout, with an owner alert naming the label, until the owner acts);
  suspect (the canary saw a smaller result, until the owner clears it). The state file under
  `<cache>/attention/_pc_state/x_pool.json` survives a restart; the library's own locks are never reset or
  rewritten (a crash's in-use lock expires by itself). A rate limit needs evidence from our side
  (`x_reader.no_account_cause`): an HTTP 429, the code 88 on an active row, or `x-rate-limit-remaining` near 0
  on that account's last page within the rate window (persisted as `rate_limit_seen`).
- A unit is fetched by one account end to end. A ban, logout or lock restarts it once on another account
  (`x_unit_max_restarts`): the aborted attempt's tweets are discarded, its reads still count against the GLOBAL
  budget, and a second failure leaves the coin-day missing (`account_failed`). Zero usable accounts pause X for
  the rest of the UTC day, unless an account waits for an in-flight lock: then X pauses only until the earliest
  such lock ends (`in_flight_lock`, `resume_at`). Budget, sample size and spacing are global (one `PcSource` for
  the whole pool); each request is stamped before it is sent, so a killed request still counts for the spacing.
- Fail closed: a None, empty or short result, an exception or a block page is missing with a reason, never 0.
  An empty page after a FULL page, or a page of repeated ids, is a stalled cursor (`x_window.cursor_end`), never
  an exact count. An exact count from an exhausted cursor needs the unit's account among the accounts that passed
  today's canary (`canary_labels`), else it is missing `account_not_canaried`; so does every other value.
  Cloudflare and HTML blocks pause the day (the curl fallback of rule 19 first when the owner flag is on: ONE
  retry per UTC day for the whole pool, canary and units together; the next block anywhere pauses the day for
  the pool; every unit still tries the default backend first while the day is not paused);
  an inconclusive canary sits the canaried accounts out for the UTC day while the others continue (no account
  passed, so their units are missing `account_not_canaried`); three consecutive parse, 404 or transaction-id
  failures count toward `layout_changed`; page parse drops first strike the account and retry elsewhere.
- Finish plan S-XDrift: a SearchTimeline 404 (`not_found`) first reruns the SAME unit once on another selectable
  account (charged normally, counted once); when that succeeds the first account is `endpoint_restricted` for the
  rest of the UTC day, and a second restricted event on a different day locks it for 24 h (`x_endpoint_404`;
  the count resets after 7 clean days). A 404 on both accounts, or with no other account, is drift. An API error
  with a ban code (64) deactivates its account and fails over once. In `auto` query-ID mode a confirmed drift
  with a registry candidate runs `XPool.evaluate_candidate` (forced, never the canary's daily cache) before
  `DRIFT_STOP` pauses; only passed evaluations adopt. Facts record isolation, locks and evaluations.
- Finish plan S-B3I (B3 integration, every switch default off; off adds nothing): quiet hours and B3 cooldowns lock
  an account like an in-flight lock (the pool waits for the earliest end, never the day); a challenge waits for the
  owner; warm-up lowers the account cap through `effective_cap`; the shrink history and rate-limit/stripped-strike
  cooldowns consume the existing signals; `run_mixed` makes at most one approved ordinary call (pinned library IDs,
  a 404 suspends that operation as `ordinary_op_stale`) charged max(20, actual) to the account and global counters.
- Quality over speed: nothing is cut for a time budget; only the safety limits above stop reading.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from functools import wraps
from contextvars import ContextVar

from api.data import cache
from api.data.attention import daily_facts, density, x_behaviour, x_density, x_filters, x_quiet, x_raw, x_window
from api.data.attention import pc_pace as pp
from api.data.attention import x_queryids as xq
from api.data.attention import x_reader as xr
from api.data.attention.web_queries import FINISH_OPTIONAL_DEFAULTS, CollectorConfig
from api.data.attention import x_proxy as xp
from api.data.attention.x_proxy_private import atomic_json, read_bounded, state_lock

LABEL_RE = re.compile(r"[a-z0-9_]{1,24}")
STATES = ("active", "inactive", "suspect")
DAY_PAUSE_REASONS = ("no_usable_account", "cloudflare_block", "html_block", "empty_results", "canary_disagree")
WAIT_REASON = xr.IN_FLIGHT_REASON
PAUSE_REASONS = (*DAY_PAUSE_REASONS, WAIT_REASON, "proxy_quarantine")
LOCK_MARGIN_S = 30  # past the library's lock end before the account is tried again
RATE_LIMIT_WINDOW = timedelta(minutes=15)  # X's rate-limit window: older near-zero headers are no evidence
SUSPECT_REASON = "x_account_suspect"
ALERT_REASONS = ("x_account_suspended", "x_login_required", SUSPECT_REASON)
DRIFT_STOP = 3
SINGLE_ACCOUNT_NOTE = "comparison skipped: single active account"
TOP_KEYS = {"accounts", "alerts", "pause_until", "pause_reason", "stopped", "drift_streak", "canary_day",
            "canary_note", "canary_labels", "curl_uses", "curl_last_use", "proxy_provider_budget"}
ACCOUNT_KEYS = {"state", "reason", "last_used", "lock_until", "last_canary", "suspect_since", "rate_limit_seen",
                "reads_day", "reads_used", "rest_until", "parse_strikes", "parse_strike_last_at",
                "proxy_id", "identity_revision", "proxy_health", "proxy_checked_at",
                "proxy_quarantine_until", "proxy_reason", "proxy_changed_at",
                "endpoint_404_day", "endpoint_404_count",
                "warmup_start_day", "behaviour_cooldown_until", "behaviour_reason", "shrink_run", "result_history",
                "mixed_day", "mixed_calls"}
TIME_KEYS = ("last_used", "lock_until", "last_canary", "suspect_since", "rate_limit_seen", "rest_until",
             "parse_strike_last_at", "proxy_checked_at", "proxy_quarantine_until", "proxy_changed_at")
READY_FILE = "account_ready.json"
B2_ACCOUNT_KEYS = ("proxy_id", "identity_revision", "proxy_health", "proxy_checked_at",
                   "proxy_quarantine_until", "proxy_reason", "proxy_changed_at")
XDRIFT_ACCOUNT_DEFAULTS = {"endpoint_404_day": None, "endpoint_404_count": 0}  # rollback contract G literals
# S-B3P behaviour keys (rollback contract G strips exactly these seven); result_history is copied per account.
B3_ACCOUNT_DEFAULTS = {"warmup_start_day": None, "behaviour_cooldown_until": None, "behaviour_reason": None,
                       "shrink_run": 0, "result_history": [], "mixed_day": None, "mixed_calls": 0}
ENDPOINT_404_REASON = "x_endpoint_404"
ENDPOINT_404_LOCK = timedelta(hours=24)
ENDPOINT_404_CLEAN_DAYS = 7
EVALUATIONS_PER_DAY = 3
EVALUATION_ACCOUNTS = 2
CANDIDATE_REJECT = timedelta(hours=24)
B3_WAIT_REASONS = ("quiet_hours", "behaviour_cooldown")  # timed B3 holds: the pool waits for them, never the day
QUERY_CLASS = "coin_day"  # the one comparable unit class of the shrink history (coin-day SearchTimeline units)
ORDINARY_STALE = "ordinary_op_stale"
EVALUATION_FAILED_KINDS = frozenset({"not_found", "gql_outdated", "parse"})
FACTS_SOURCE = "xsearch_web"


def facts_switches(config: CollectorConfig) -> dict:
    """The effective optional switches recorded with each day's facts (names only safe tokens)."""
    keys = [k for k, v in FINISH_OPTIONAL_DEFAULTS.items() if isinstance(v, bool) and "cookie" not in k]
    return {"x_queryid_mode": config.x_queryid_mode, **{k: getattr(config, k) for k in keys}}


def _transaction(method):
    """Reload before mutation; nested helpers use explicit internal ownership."""
    @wraps(method)
    def call(self, *args, **kwargs):
        if self._lock_owned is not None:
            return method(self, *args, **kwargs)
        with state_lock(self.path) as ownership:
            self._lock_owned = ownership
            try:
                self._s = self._load()
                return method(self, *args, **kwargs)
            finally:
                self._lock_owned = None
    return call


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


def _day(value) -> bool:
    try:
        return value is None or (isinstance(value, str) and date.fromisoformat(value).isoformat() == value)
    except ValueError:
        return False


def read_ready(directory: str | Path) -> dict:
    """Read only label/timestamp marks, never account databases or secrets. Bad evidence is not ready."""
    if not directory:
        return {}
    try:
        marks = xp.strict_json(read_bounded(Path(directory) / READY_FILE, xp.SMALL_LIMIT))
    except (OSError, ValueError, xp.ProxyFailure):
        return {}
    if not isinstance(marks, dict):
        return {}
    return {label: at for label, at in marks.items()
            if LABEL_RE.fullmatch(label) and at is not None and _iso(at)}


def write_ready(directory: str | Path, label: str, now: datetime, *, labels, service_sid=None) -> None:
    """Separate atomic owner file: a collector pool save cannot overwrite these marks."""
    if label not in labels or not LABEL_RE.fullmatch(label) or not directory:
        raise ValueError("configured label and accounts directory required")
    marks = read_ready(directory)
    marks[label] = _utc(now).isoformat()
    if service_sid is None:
        cache._atomic_write_json(marks, Path(directory) / READY_FILE)
    else:
        atomic_json(Path(directory) / READY_FILE, marks, service_sid=service_sid)


def from_config(config: CollectorConfig, *, clock: Callable[[], datetime]) -> XPool:
    pool = XPool(list(config.x_accounts), clock=clock, cap=config.x_account_daily_cap,
                 rest_days=config.x_account_rest_days, ready=read_ready(config.x_accounts_db_path))
    pool.ready_directory = config.x_accounts_db_path
    paths = (config.x_proxy_list_path, config.x_proxy_assignments_path, config.x_proxy_policy_path)
    pool.proxy_direct = not config.x_proxy_required and all(path is None for path in paths)
    pool.proxy_required = not pool.proxy_direct
    pool.connection_style = config.x_connection_style
    pool.proxy_regions = {k: v.get("region") for k, v in config.x_account_identities.items()}
    pool.proxy_max_age = config.x_proxy_admission_max_age_seconds
    pool.switches = facts_switches(config)
    pool.quiet_hours = dict(config.x_account_quiet_hours) if config.x_quiet_hours_enabled else {}
    pool.warmup_enabled = config.x_warmup_enabled
    pool.cooldown_enabled = config.x_adaptive_cooldown_enabled
    pool.b3_status = any((config.x_quiet_hours_enabled, config.x_mixed_traffic_enabled, config.x_variation_enabled,
                          config.x_adaptive_cooldown_enabled, config.x_warmup_enabled))
    return pool


def _b3_defaults() -> dict:
    return {k: list(v) if isinstance(v, list) else v for k, v in B3_ACCOUNT_DEFAULTS.items()}


def _fresh_account() -> dict:
    return dict.fromkeys(ACCOUNT_KEYS) | {"state": "active", "reads_used": 0, "proxy_health": "unknown",
                                          **XDRIFT_ACCOUNT_DEFAULTS, **_b3_defaults()}


def _valid_b3(a: dict) -> bool:
    """Types and bounds of the seven B3 keys; history records are exactly {day, count, query_class}, nonsecret."""
    until, history = a["behaviour_cooldown_until"], a["result_history"]
    return (_day(a["warmup_start_day"]) and _day(a["mixed_day"])
            and (until is None or _iso(until) and datetime.fromisoformat(until).utcoffset() == timedelta(0))
            and (a["behaviour_reason"] is None or isinstance(a["behaviour_reason"], str)
                 and a["behaviour_reason"] in x_behaviour.BEHAVIOUR_REASONS)
            and type(a["shrink_run"]) is int and 0 <= a["shrink_run"] <= x_behaviour.SHRINK_RUN_MAX
            and type(a["mixed_calls"]) is int and 0 <= a["mixed_calls"] <= x_behaviour.MIXED_DAILY_MAX
            and isinstance(history, list) and len(history) <= x_behaviour.HISTORY_LEN
            and all(isinstance(h, dict) and set(h) == {"day", "count", "query_class"}
                    and h["day"] is not None and _day(h["day"]) and type(h["count"]) is int and h["count"] >= 0
                    and isinstance(h["query_class"], str) and x_behaviour.QUERY_CLASS_RE.fullmatch(h["query_class"])
                    for h in history))


def _valid(s) -> bool:
    if not isinstance(s, dict) or set(s) != TOP_KEYS or not isinstance(s["accounts"], dict):
        return False
    budget = s["proxy_provider_budget"]
    if not (isinstance(budget, dict) and set(budget) == {"day", "used"} and _day(budget["day"])
            and type(budget["used"]) is int and 0 <= budget["used"] <= 899
            and (budget["day"] is not None or budget["used"] == 0)):
        return False
    for a in s["accounts"].values():
        if not (isinstance(a, dict) and set(a) == ACCOUNT_KEYS and a["state"] in STATES
                and all(_iso(a[k]) for k in TIME_KEYS) and _day(a["reads_day"])
                and type(a["reads_used"]) is int and a["reads_used"] >= 0
                and (a["parse_strikes"] is None or type(a["parse_strikes"]) is int and a["parse_strikes"] >= 0)
                and _day(a["endpoint_404_day"]) and type(a["endpoint_404_count"]) is int
                and a["endpoint_404_count"] >= 0 and _valid_b3(a)):
            return False
        if a["proxy_health"] not in ("unknown", "healthy", "quarantined") or (
                a["proxy_reason"] is not None and (not isinstance(a["proxy_reason"], str) or a["proxy_reason"] not in xp.REASONS)):
            return False
        try:
            for key in ("proxy_id", "identity_revision"):
                if a[key] is not None:
                    xp.opaque_id(a[key])
        except xp.ProxyFailure:
            return False
        if any(a[key] is not None and datetime.fromisoformat(a[key]).utcoffset() != timedelta(0)
               for key in ("proxy_checked_at", "proxy_quarantine_until", "proxy_changed_at")):
            return False
        if a["proxy_health"] == "healthy" and (
                any(a[key] is None for key in ("proxy_id", "identity_revision", "proxy_checked_at"))
                or a["proxy_reason"] is not None or a["proxy_quarantine_until"] is not None):
            return False
        if a["proxy_health"] == "quarantined" and any(a[key] is None for key in
                ("proxy_checked_at", "proxy_quarantine_until", "proxy_reason")):
            return False
    return all((
        isinstance(s["alerts"], list), _iso(s["pause_until"]), _iso(s["curl_last_use"]),
        s["pause_reason"] is None or s["pause_reason"] in PAUSE_REASONS,
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

    def __init__(self, labels: list[str], *, clock: Callable[[], datetime], cap: int | None = None,
                 rest_days: int = 0, ready: Mapping[str, str] | None = None):
        if not labels or len(set(labels)) != len(labels) or not all(
                isinstance(x, str) and LABEL_RE.fullmatch(x) for x in labels):
            raise ValueError("labels must be unique opaque labels")
        self.labels, self.clock = list(labels), clock
        if cap is not None and (type(cap) is not int or cap < 1):
            raise ValueError("cap must be a positive integer or None")
        if type(rest_days) is not int or rest_days < 0:
            raise ValueError("rest days must be a nonnegative integer")
        self.cap, self.rest_days, self.ready = cap, rest_days, dict(ready or {})
        self.ready_directory = ""
        self.log: list[str] = []
        self._parse_failures: dict[str, set[str]] = {}
        self.path = cache.CACHE_ROOT / "attention" / "_pc_state" / "x_pool.json"
        self._ownership = ContextVar("x_pool_lock_owner", default=None)
        self.proxy_direct = False
        self.proxy_required = False
        self.connection_style = None
        self.proxy_regions = {}
        self.proxy_max_age = 86400
        self.switches: dict = {}  # facts switch provenance; `from_config` sets the effective values
        self.quiet_hours: dict = {}  # S-B3I effective quiet windows (empty while the switch is off)
        self.warmup_enabled = self.cooldown_enabled = self.b3_status = False
        self._s = self._load()

    @property
    def _lock_owned(self):
        return self._ownership.get()

    @_lock_owned.setter
    def _lock_owned(self, value):
        self._ownership.set(value)

    # --- persistence ---
    def _load(self) -> dict:
        if not self.path.exists():
            s = {"accounts": {}, "alerts": [], "pause_until": None, "pause_reason": None, "stopped": None,
                 "drift_streak": 0, "canary_day": None, "canary_note": None, "canary_labels": [], "curl_uses": 0,
                 "curl_last_use": None, "proxy_provider_budget": {"day": None, "used": 0}}
        else:
            try:
                s = xp.strict_json(read_bounded(self.path, 1024 * 1024), limit=1024 * 1024)
            except (OSError, ValueError, xp.ProxyFailure):
                raise XPoolStateError("pool state unreadable") from None
            if isinstance(s, dict):
                s.setdefault("canary_labels", [])  # a state file from before T190: no account passed yet
                s.setdefault("proxy_provider_budget", {"day": None, "used": 0})
                accounts = s.get("accounts")
                for a in accounts.values() if isinstance(accounts, dict) else ():
                    if isinstance(a, dict):
                        a.setdefault("rate_limit_seen", None)  # a state file from before the in-flight lock fix
                        a.setdefault("reads_day", None)
                        a.setdefault("reads_used", 0)
                        a.setdefault("rest_until", None)
                        a.setdefault("parse_strikes", None)
                        a.setdefault("parse_strike_last_at", None)
                        for key in B2_ACCOUNT_KEYS:
                            a.setdefault(key, "unknown" if key == "proxy_health" else None)
                        for key, value in XDRIFT_ACCOUNT_DEFAULTS.items():
                            a.setdefault(key, value)
                        for key, value in _b3_defaults().items():
                            a.setdefault(key, value)
            if not _valid(s):
                raise XPoolStateError("pool state invalid")
            if set(s["accounts"]) - set(self.labels):
                raise XPoolStateError("pool state names a label that is not configured")
            if s["proxy_provider_budget"]["day"] is not None and s["proxy_provider_budget"]["day"] > self._now().date().isoformat():
                raise XPoolStateError("pool state invalid")
        for label in self.labels:
            if label not in s["accounts"]:
                a = _fresh_account()
                if self.path.exists() and self.rest_days:
                    a["rest_until"] = (self._now() + timedelta(days=self.rest_days)).isoformat()
                s["accounts"][label] = a
        return s

    def _save(self) -> None:
        xp.require(self._lock_owned is not None, "proxy_lock")
        atomic_json(self.path, self._s)

    @_transaction
    def begin_pass(self) -> None:
        """Persist registration/rest start even if no account reads. Status consumers never call this.
        S-B3I: an expired B3 cooldown is cleared (a shrink cooldown also resets its run) and warm-up starts on the
        first eligible day (rest over and ready; grandfathered accounts never enter the ladder)."""
        self._parse_failures.clear()
        now = self._now()
        for label in self.labels:
            a = self._acct(label)
            until = a["behaviour_cooldown_until"]
            if until is not None and now >= datetime.fromisoformat(until):
                if a["behaviour_reason"] == "shrink":
                    a["shrink_run"] = 0
                a["behaviour_cooldown_until"] = a["behaviour_reason"] = None
                self.fact({"kind": "cooldown", "source": FACTS_SOURCE, "account": label, "action": "cleared"})
            eligible = (a["rest_until"] is not None and now >= datetime.fromisoformat(a["rest_until"])
                        and bool(self.ready_today(label)))
            a["warmup_start_day"] = x_behaviour.warmup_start(a["warmup_start_day"], eligible=eligible,
                                                             today=now.date(), enabled=self.warmup_enabled)
        self._save()

    def _now(self) -> datetime:
        return _utc(self.clock())

    def _next_midnight(self) -> str:
        return datetime.combine(self._now().date() + timedelta(days=1), time(0), tzinfo=timezone.utc).isoformat()

    def _acct(self, label: str) -> dict:
        if label not in self._s["accounts"]:
            raise ValueError("unknown label")
        return self._s["accounts"][label]

    # --- accounts ---
    def reads_today(self, label: str) -> int | None:
        """Unknown before the first counted page; reset only forwards, never on a clock rollback."""
        a = self._acct(label)
        if a["reads_day"] is None:
            return None
        return 0 if self._now().date() > date.fromisoformat(a["reads_day"]) else a["reads_used"]

    @_transaction
    def charge(self, label: str, loaded: int) -> None:
        """Charge exactly where the global counter charges, including aborted attempts and curl pages."""
        if type(loaded) is not int or loaded < 0:
            raise ValueError("loaded reads must be nonnegative")
        a = self._acct(label)
        today = self._now().date().isoformat()
        if a["reads_day"] is None or today > a["reads_day"]:
            a["reads_day"], a["reads_used"] = today, 0
        a["reads_used"] += loaded
        self._save()

    def ready_today(self, label: str) -> bool | None:
        if self._acct(label)["rest_until"] is None:
            return None  # grandfathered, no ready mark required
        if self.ready_directory:
            self.ready = read_ready(self.ready_directory)
        mark = self.ready.get(label)
        return bool(mark and _iso(mark) and _utc(datetime.fromisoformat(mark)).date() < self._now().date())

    def effective_cap(self, label: str) -> int | None:
        """The configured cap, lowered by the warm-up ladder when `x_warmup_enabled` (grandfathered: unchanged)."""
        a = self._acct(label)
        return x_behaviour.effective_cap(self.cap, a["warmup_start_day"], self._now().date(),
                                         enabled=self.warmup_enabled, grandfathered=a["rest_until"] is None)

    def remaining_caps(self) -> int | None:
        caps = {label: self.effective_cap(label) for label in self.usable()}
        if self.cap is None and (not caps or None in caps.values()):
            return None
        return sum(max(0, cap - (self.reads_today(label) or 0)) for label, cap in caps.items() if cap is not None)

    def b3_hold(self, label: str) -> tuple[str, datetime | None] | None:
        """S-B3I: (reason, end) while a B3 measure holds the account; a challenge has no end (owner intervention)."""
        a, now = self._acct(label), self._now()
        if a["behaviour_reason"] == "challenge":
            return "challenge", None
        until = a["behaviour_cooldown_until"] if self.cooldown_enabled else None
        cooldown = datetime.fromisoformat(until) if until else now
        quiet = x_quiet.quiet_until(max(now, cooldown), label, self.quiet_hours, enabled=bool(self.quiet_hours))
        end = max(cooldown, quiet or now)
        if end <= now:
            return None
        return ("quiet_hours" if quiet else "behaviour_cooldown"), end


    def account_state(self, label: str) -> tuple[str, str | None]:
        a = self._acct(label)
        if a["state"] != "active":
            return a["state"], a["reason"]
        if a["lock_until"] and self._now() < datetime.fromisoformat(a["lock_until"]):
            if a["reason"] == ENDPOINT_404_REASON:
                return "locked", "endpoint_404"
            return "locked", WAIT_REASON if a["reason"] == WAIT_REASON else "rate_limited"
        if a["endpoint_404_day"] == self._now().date().isoformat():
            return "locked", "endpoint_restricted"  # skipped for SearchTimeline units for the rest of the UTC day
        if a["rest_until"] and (self._now() < datetime.fromisoformat(a["rest_until"])
                                or not self.ready_today(label)):
            return "locked", "resting"
        hold = self.b3_hold(label)
        if hold is not None:
            return "locked", hold[0]
        if self.proxy_required:
            if a["proxy_health"] == "quarantined":
                return "locked", "proxy_quarantine"
            if a["proxy_health"] != "healthy":
                return "locked", a["proxy_reason"] or "proxy_revision"
            if not a["proxy_checked_at"] or not timedelta(0) <= self._now() - datetime.fromisoformat(a["proxy_checked_at"]) < timedelta(seconds=self.proxy_max_age):
                return "locked", "proxy_revision"
        cap = self.effective_cap(label)
        if cap is not None and (self.reads_today(label) or 0) >= cap:
            return "locked", "account_cap"
        return "active", None

    def usable(self) -> list[str]:
        return [x for x in self.labels if self.account_state(x)[0] == "active"]

    def _least_recent(self, cands: list[str]) -> str | None:
        last = {x: self._acct(x)["last_used"] or "" for x in cands}
        return min(cands, key=lambda x: (last[x], self.labels.index(x))) if cands else None

    def peek(self) -> str | None:
        """The account `select` would choose next, without logging a selection."""
        return self._least_recent(self.usable())

    def select(self, *, exclude=()) -> Selection | None:
        """Least recently used usable account; never-used first; ties by registration order."""
        cands = [label for label in self.usable() if label not in exclude]
        pick = self._least_recent(cands)
        if pick is None:
            return None
        last = self._acct(pick)["last_used"] or ""
        tie = sum(1 for x in cands if (self._acct(x)["last_used"] or "") == last) > 1
        reason = "least recently used" + ("; tie by registration order" if tie else "")
        self.log.append(f"x pool: selected {pick} ({reason})")
        return Selection(pick, reason)

    @_transaction
    def mark_used(self, label: str) -> None:
        self._acct(label)["last_used"] = self._now().isoformat()
        self._save()

    @_transaction
    def lock_for_day(self, label: str) -> None:
        """A rate limit: no retry on this account until the next 00:00 UTC; it stays active."""
        a = self._acct(label)
        a["lock_until"] = self._next_midnight()
        if a["reason"] in (WAIT_REASON, ENDPOINT_404_REASON):
            a["reason"] = None
        self._save()

    @_transaction
    def note_endpoint_404(self, label: str) -> str:
        """XD-1: a SearchTimeline 404 that another account did not see. `restricted` for the rest of the UTC day;
        a second restricted event on a different day `locked` for 24 h. The count resets after 7 clean days."""
        a, now = self._acct(label), self._now()
        today, previous = now.date(), a["endpoint_404_day"]
        if previous is not None and (today - date.fromisoformat(previous)).days > ENDPOINT_404_CLEAN_DAYS:
            a["endpoint_404_count"] = 0
        second = a["endpoint_404_count"] >= 1 and previous != today.isoformat()
        a["endpoint_404_count"] += 1
        a["endpoint_404_day"] = today.isoformat()
        if second:
            a["lock_until"], a["reason"] = (now + ENDPOINT_404_LOCK).isoformat(), ENDPOINT_404_REASON
        self.log.append(f"x pool: {label} SearchTimeline 404 seen only here: "
                        + ("locked for 24 h" if second else "restricted for the UTC day"))
        self._save()
        self.fact({"kind": "account_state", "source": FACTS_SOURCE, "account": label,
                   "state": "lock" if second else "pause",
                   "reason": ENDPOINT_404_REASON if second else "endpoint_restricted"})
        return "locked" if second else "restricted"

    def fact(self, event: dict) -> None:
        """A durable nonsecret daily fact; a refused or failed write never stops collection."""
        try:
            if not daily_facts.append(event, now=self._now(), switches=self.switches):
                self.log.append("x pool: facts file for the day is full")
        except (OSError, ValueError):
            self.log.append(f"x pool: fact {event.get('kind')} not recorded")

    @_transaction
    def wait_for_lock(self, label: str, lock_end: datetime) -> None:
        """The library's bare in-flight lock: skip this account until that lock ends (plus a margin), never for
        the day; the library's own lock is left as it is and expires by itself."""
        a = self._acct(label)
        a["lock_until"] = (_utc(lock_end) + timedelta(seconds=LOCK_MARGIN_S)).isoformat()
        a["reason"] = WAIT_REASON
        self.log.append(f"x pool: {label} waits for the library's in-flight lock until {a['lock_until']}")
        self._save()

    @_transaction
    def note_remaining(self, label: str, remaining: int | None) -> None:
        """Keep the rate-limit evidence of a page's `x-rate-limit-remaining`: near 0 is evidence, more clears it."""
        a = self._acct(label)
        if xr.near_rate_limit(remaining):
            a["rate_limit_seen"] = self._now().isoformat()
            self.apply_cooldown(label, x_behaviour.cooldown(self._now(), enabled=self.cooldown_enabled,
                                                           rate_remaining=remaining))
        elif remaining is not None and a["rate_limit_seen"] is not None:
            a["rate_limit_seen"] = None
        else:
            return
        self._save()

    def rate_limit_evidence(self, label: str) -> bool:
        seen = self._acct(label)["rate_limit_seen"]
        return seen is not None and self._now() - datetime.fromisoformat(seen) < RATE_LIMIT_WINDOW

    def _alert(self, label: str, reason: str) -> None:
        if not any(a["label"] == label and a["reason"] == reason for a in self._s["alerts"]):
            self._s["alerts"].append({"label": label, "reason": reason, "at": self._now().isoformat()})

    @_transaction
    def mark_inactive(self, label: str, reason: str) -> None:
        if reason not in ("x_account_suspended", "x_login_required"):
            raise ValueError("unknown inactive reason")
        a = self._acct(label)
        a["state"], a["reason"] = "inactive", reason
        self._alert(label, reason)
        self._save()

    @_transaction
    def flag_suspect(self, label: str) -> None:
        """Excluded from selection until the owner clears it; its stored units get `suspect_since`."""
        a, now = self._acct(label), self._now()
        a["state"], a["reason"], a["suspect_since"] = "suspect", SUSPECT_REASON, now.isoformat()
        self._alert(label, SUSPECT_REASON)
        self._save()
        x_raw.mark_suspect(label, now)

    @_transaction
    def note_parse_drop(self, label: str, kind: str) -> int:
        a, now = self._acct(label), self._now()
        last = a["parse_strike_last_at"]
        recent = last is not None and timedelta(0) <= now - datetime.fromisoformat(last) < timedelta(hours=24)
        a["parse_strikes"] = (a["parse_strikes"] or 0) + 1 if recent else 1
        a["parse_strike_last_at"] = now.isoformat()
        self.log.append(f"x pool: {label} parse drop {kind}")
        self._save()
        if a["parse_strikes"] >= 2 and a["state"] == "active":
            self.flag_suspect(label)
        if a["parse_strikes"] >= 2 and kind == "content_stripped":  # the fix's confirmed strike (S-B3I consumes it)
            self.apply_cooldown(label, x_behaviour.cooldown(now, enabled=self.cooldown_enabled, stripped_strike=True))
        return a["parse_strikes"]

    @_transaction
    def clear_parse_strikes(self, label: str) -> None:
        a = self._acct(label)
        if a["parse_strikes"] is not None and a["parse_strikes"] != 0:
            a["parse_strikes"], a["parse_strike_last_at"] = 0, None
            self._save()

    def parse_failure_seen_elsewhere(self, label: str, kind: str) -> bool:
        labels = self._parse_failures.setdefault(kind, set())
        other = any(previous != label for previous in labels)
        labels.add(label)
        return other

    @_transaction
    def owner_clear(self, label: str) -> None:
        """The owner acted on this account (fresh cookies, or cleared a suspect flag)."""
        a = self._acct(label)
        a["state"], a["reason"], a["suspect_since"] = "active", None, None
        a["parse_strikes"], a["parse_strike_last_at"] = 0, None
        a["behaviour_cooldown_until"] = a["behaviour_reason"] = None
        a["shrink_run"] = 0
        self._s["alerts"] = [x for x in self._s["alerts"] if x["label"] != label]
        self._save()

    def alerts(self) -> list[dict]:
        return [dict(a) for a in self._s["alerts"]]

    @_transaction
    def apply_cooldown(self, label: str, decision: x_behaviour.Cooldown | None) -> None:
        if decision is None:
            return
        a = self._acct(label)
        old = a["behaviour_cooldown_until"]
        if a["behaviour_reason"] == "challenge":
            return
        if not decision.owner_pause and old and datetime.fromisoformat(old) >= decision.until:
            return
        a["behaviour_reason"] = decision.reason
        a["behaviour_cooldown_until"] = decision.until.isoformat() if decision.until else None
        self._save()
        self.fact({"kind": "cooldown", "source": FACTS_SOURCE, "account": label,
                   "action": "set", "until": decision.until.isoformat().replace("+00:00", "Z")
                   if decision.until else None})

    @_transaction
    def note_result(self, label: str, day: date, count: int) -> None:
        if not self.cooldown_enabled:
            return
        a = self._acct(label)
        a["result_history"], a["shrink_run"] = x_behaviour.record_result(
            a["result_history"], a["shrink_run"], day=day, count=count, query_class=QUERY_CLASS, canary=False)
        self._save()
        self.apply_cooldown(label, x_behaviour.cooldown(self._now(), enabled=True, shrink_run=a["shrink_run"]))

    # --- pause, stop, drift, fallback ---
    @_transaction
    def pause_day(self, reason: str) -> None:
        if reason not in DAY_PAUSE_REASONS:
            raise ValueError("unknown pause reason")
        self._s["pause_until"], self._s["pause_reason"] = self._next_midnight(), reason
        self._save()

    @_transaction
    def pause_for_locks(self) -> bool:
        """Pause X until the earliest in-flight lock end of the accounts that wait for one; False when none waits."""
        ends = [self._acct(x)["lock_until"] for x in self.labels if self.account_state(x) == ("locked", WAIT_REASON)]
        for label in self.labels:
            if self.account_state(label)[1] in B3_WAIT_REASONS:
                hold = self.b3_hold(label)
                if hold and hold[1]:
                    ends.append(hold[1].isoformat())
        if not ends:
            return False
        self._s["pause_until"] = min(ends, key=datetime.fromisoformat)
        self._s["pause_reason"] = WAIT_REASON
        self._save()
        return True

    @_transaction
    def pause_no_account(self, src: pp.PcSource | None = None) -> str:
        """No usable account: wait for the earliest in-flight lock end when an account waits for one, else pause
        the UTC day (`no_usable_account`). Returns the pause reason."""
        waiting = self.pause_for_locks()
        if self.pause_for_proxies():
            return self._s["pause_reason"]
        if waiting:
            return WAIT_REASON
        if src is not None and any(self.account_state(x) == ("locked", "account_cap") for x in self.labels):
            src.mark_spent()
            return "budget_spent"
        self.pause_day("no_usable_account")
        return "no_usable_account"

    def resume_at(self) -> datetime | None:
        """Short control wake without clearing an independent pool day pause."""
        if self._s["stopped"] or not self.is_paused():
            return None
        if self._s["pause_reason"] in (WAIT_REASON, "proxy_quarantine"):
            return datetime.fromisoformat(self._s["pause_until"])
        wakes = [datetime.fromisoformat(a["proxy_quarantine_until"]) for a in self._s["accounts"].values()
                 if a["proxy_quarantine_until"] and datetime.fromisoformat(a["proxy_quarantine_until"]) > self._now()]
        return min(wakes) if wakes else None

    @_transaction
    def stop(self, reason: str = "layout_changed") -> None:
        self._s["stopped"] = reason
        self._save()

    def stopped_reason(self) -> str | None:
        return self._s["stopped"]

    @_transaction
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

    @_transaction
    def note_drift(self) -> int:
        self._s["drift_streak"] += 1
        if self._s["drift_streak"] >= DRIFT_STOP:
            self._s["stopped"] = "layout_changed"
        self._save()
        return self._s["drift_streak"]

    @_transaction
    def clear_drift(self) -> None:
        if self._s["drift_streak"]:
            self._s["drift_streak"] = 0
            self._save()

    def evaluate_candidate(self, operation: str, candidate_id: str, *, readers: Mapping[str, xr.XReader],
                           src: pp.PcSource, config: CollectorConfig, bind: Callable[[str], None],
                           observed_by: str | None = None) -> str:
        """XD-3 forced candidate evaluation (contract E), never the daily canary: today's `already_passed` cache
        is ignored. One canary page per account with `candidate_id` bound through `bind`, charged normally, on up
        to two distinct selectable accounts (others than `observed_by` first); one evidence record per executed
        evaluation. `adopted` iff every executed evaluation passed and N equals the selectable accounts capped at
        2; any failure `rejected` (+24 h); anything else `inconclusive` (the candidate stays). At most 3
        evaluations per UTC day (`budget`); `no_candidate` when the registry holds no live candidate with that ID.
        The registry's active ID is bound again before returning."""
        if operation != xq.TRACKED or not xq.valid_id(candidate_id):
            raise ValueError("only a SearchTimeline candidate is evaluated")
        path, now = xq.state_path(cache.CACHE_ROOT), self._now()
        state = xq.load(path)
        entry = state["operations"][operation]
        cand = entry["candidate"]
        if cand is None or cand["id"] != candidate_id or (
                cand["rejected_until"] and datetime.fromisoformat(cand["rejected_until"]) > now):
            return "no_candidate"
        done_today = sum(1 for e in state["evidence"] if e["operation"] == operation
                         and datetime.fromisoformat(e["evaluated_at"]).date() == now.date())
        if done_today >= EVALUATIONS_PER_DAY:
            return "budget"
        usable = self.usable()
        required = min(EVALUATION_ACCOUNTS, len(usable))
        order = [x for x in usable if x != observed_by] + [x for x in usable if x == observed_by]
        start, end = canary_window(now)
        query = canary_query(config, start, end)
        results = []
        final_id = entry["active"]["id"]
        try:
            for label in order[:min(required, EVALUATIONS_PER_DAY - done_today)]:
                if not src.can_spend(xr.PAGE_ENTRIES):
                    src.mark_spent()
                    break
                results.append((label, *self._evaluate_once(label, readers[label], src, config, bind, candidate_id,
                                                            query, start, end)))
            ids = {e["evidence_id"] for e in state["evidence"]}
            for i, (label, result, entries, parse_ok) in enumerate(results):
                evidence_id = f"ev{int(now.timestamp())}_{i}_{label}"
                while evidence_id in ids:
                    evidence_id += "x"
                ids.add(evidence_id)
                state["evidence"].append({"evidence_id": evidence_id, "operation": operation,
                                          "candidate_id": candidate_id, "account_label": label,
                                          "evaluated_at": now.isoformat(), "result": result, "entries": entries,
                                          "parse_ok": parse_ok})
            outcomes = [r[1] for r in results]
            before = state["check_state"]
            if "failed" in outcomes:
                verdict = "rejected"
                cand.update(rejected_until=(now + CANDIDATE_REJECT).isoformat(), reason="evaluation_failed")
                state["check_state"] = "stale"
            elif outcomes and all(r == "passed" for r in outcomes) and len(outcomes) == required:
                verdict = "adopted"
                passed = [e for e in state["evidence"] if e["candidate_id"] == candidate_id
                          and e["evaluated_at"] == now.isoformat() and e["result"] == "passed"]
                entry["active"] = {"id": candidate_id, "source": "bundle", "adopted_at": now.isoformat(),
                                   "evidence_id": passed[-1]["evidence_id"]}
                entry["candidate"], state["check_state"] = None, "ok"
                final_id = candidate_id
            else:
                verdict = "inconclusive"
                cand["reason"] = "inconclusive"
            keep = entry["active"]["evidence_id"]
            while len(state["evidence"]) > xq.EVIDENCE_LIMIT:
                drop = next(i for i, e in enumerate(state["evidence"]) if e["evidence_id"] != keep)
                del state["evidence"][drop]
            xq.save(path, state)
        finally:
            bind(final_id)
        self.log.append(f"x pool: query-id candidate evaluation {verdict} ({len(results)} of {required})")
        self.fact({"kind": "queryid_state", "operation": operation, "from_state": before, "to_state": verdict,
                   "reason": "forced_evaluation"})
        return verdict

    def _evaluate_once(self, label, reader, src, config, bind, candidate_id, query, start, end):
        """(result, parseable entries, parse_ok) of one forced evaluation page on `label`."""
        self.mark_used(label)
        src.stamp_attempt()  # before the request: a request killed in flight still counts for the spacing
        try:
            bind(candidate_id)
            raw = reader.search_raw(query, x_window.search_kv(), 0)
        except xr.ReaderFailure as f:
            src.stamp_attempt()
            if f.charged_reads:
                src.record_loaded(f.charged_reads)
                self.charge(label, f.charged_reads)
            if f.kind == "proxy":
                self.proxy_result(label, reason=f.proxy_reason, quarantine_seconds=config.x_proxy_quarantine_seconds)
            elif _is_block(f):
                self.pause_day(f"{f.abort}_block")
            elif f.kind == "no_account":
                _account_failure(self, label, reader, f)
            elif xr.inactive_reason(f):
                self.mark_inactive(label, xr.inactive_reason(f))
            return ("failed" if f.kind in EVALUATION_FAILED_KINDS else "inconclusive"), 0, False
        if raw is None:
            raw = xr.RawPage({}, ())
        n = len(raw.entry_ids)
        src.record_loaded(n)
        self.charge(label, n)
        self.note_remaining(label, raw.rate_limit_remaining)
        src.record_unit()
        try:
            tweets = reader.parse_tweets(raw.body)
        except Exception:  # noqa: BLE001 - a broken page is a failed evaluation, never a pass
            tweets = []
        if xr.parse_drop(entries=n, parsed=len(tweets), threshold=config.x_parse_drop_threshold) or \
                xr.small_page_drop(entries=n, parsed=len(tweets)):
            return "failed", 0, False
        found = len(xr.canary_ids(tweets, start, end))
        return ("passed" if found >= config.x_canary_min_results else "inconclusive"), found, True

    def curl_used_today(self) -> bool:
        """The day's one curl retry (rule 19) is spent: the next block pauses the day for the pool."""
        last = self._s["curl_last_use"]
        return last is not None and datetime.fromisoformat(last).astimezone(timezone.utc).date() == self._now().date()

    @_transaction
    def note_curl(self) -> None:
        self._s["curl_uses"] += 1
        self._s["curl_last_use"] = self._now().isoformat()
        self._save()

    # --- canary ---
    @_transaction
    def set_canary_passed(self, note: str | None = None, *, labels) -> None:
        """Today's canary passed; `labels` are the accounts that passed it (an exact count needs one of them)."""
        if set(labels) - set(self.labels):
            raise ValueError("unknown label")
        today = self._now().date().isoformat()
        previous = set(self._s["canary_labels"]) if self._s["canary_day"] == today else set()
        passed = previous | set(labels)
        self._s["canary_day"], self._s["canary_note"] = today, note
        self._s["canary_labels"] = [x for x in self.labels if x in passed and self._acct(x)["state"] == "active"]
        self._save()

    def canary_passed_today(self) -> bool:
        pending = any(self._acct(label)["proxy_changed_at"] is not None
                      and self._acct(label)["last_canary"] is None for label in self.usable())
        return not pending and self._s["canary_day"] == self._now().date().isoformat()

    def canary_labels(self) -> list[str]:
        """The accounts that passed today's canary; empty on another day."""
        return list(self._s["canary_labels"]) if self.canary_passed_today() else []

    def canary_accounts(self) -> list[str]:
        """The least recently canaried usable accounts: two, or three when there are three or more (a majority)."""
        cands = sorted(self.usable(), key=lambda x: (
            not (self._acct(x)["proxy_changed_at"] is not None and self._acct(x)["last_canary"] is None),
            self._acct(x)["last_canary"] or "", self.labels.index(x)))
        return cands[:3] if len(cands) >= 3 else cands

    @_transaction
    def mark_canaried(self, labels) -> None:
        for x in labels:
            self._acct(x)["last_canary"] = self._now().isoformat()
        self._save()

    @_transaction
    def reconcile_proxy(self, label: str, proxy_id: str | None, revision: str) -> bool:
        xp.opaque_id(revision)
        if proxy_id is not None:
            xp.opaque_id(proxy_id)
        a = self._acct(label)
        if a["proxy_id"] == proxy_id and a["identity_revision"] == revision:
            return False
        a.update(proxy_id=proxy_id, identity_revision=revision, proxy_health="unknown",
                 proxy_checked_at=None, proxy_quarantine_until=None, proxy_reason=None,
                 proxy_changed_at=self._now().isoformat(), last_canary=None)
        self._s["canary_labels"] = [x for x in self._s["canary_labels"] if x != label]
        self._save()
        return True

    @_transaction
    def proxy_result(self, label: str, *, reason: str | None, quarantine_seconds: int = 3600):
        xp.require(reason is None or reason in xp.REASONS, "proxy_config")
        a = self._acct(label)
        a.update(proxy_health="healthy" if reason is None else "quarantined",
                 proxy_reason=reason, proxy_checked_at=self._now().isoformat(),
                 proxy_quarantine_until=None if reason is None else
                 (self._now() + timedelta(seconds=quarantine_seconds)).isoformat())
        self._save()

    @_transaction
    def proxy_unknown(self, label: str, reason: str, *, wake_at: datetime | None = None):
        xp.require(reason in xp.REASONS, "proxy_config")
        self._acct(label).update(proxy_health="unknown", proxy_reason=reason,
                                proxy_quarantine_until=None if wake_at is None else _utc(wake_at).isoformat())
        self._save()

    @_transaction
    def pause_for_proxies(self) -> bool:
        ends = [a["proxy_quarantine_until"] for a in self._s["accounts"].values()
                if a["proxy_health"] in ("quarantined", "unknown") and a["proxy_quarantine_until"]
                and datetime.fromisoformat(a["proxy_quarantine_until"]) > self._now()]
        if not ends:
            return False
        if self._s["pause_reason"] in DAY_PAUSE_REASONS and self.is_paused():
            return True
        until = min(ends, key=datetime.fromisoformat)
        reason = "proxy_quarantine"
        if self._s["pause_until"] and self._s["pause_reason"] == WAIT_REASON and datetime.fromisoformat(self._s["pause_until"]) <= datetime.fromisoformat(until):
            until, reason = self._s["pause_until"], WAIT_REASON
        self._s["pause_until"], self._s["pause_reason"] = until, reason
        self._save()
        return True
    def proxy_health_wake(self, interval_seconds: int) -> datetime | None:
        if not self.proxy_required:
            return None
        wakes = []
        now = self._now()
        for a in self._s["accounts"].values():
            if a["state"] != "active":
                continue
            if a["proxy_quarantine_until"]:
                wakes.append(max(now, datetime.fromisoformat(a["proxy_quarantine_until"])))
            elif a["proxy_checked_at"]:
                wakes.append(max(now, datetime.fromisoformat(a["proxy_checked_at"]) + timedelta(seconds=interval_seconds)))
            else:
                wakes.append(now)
        return min(wakes) if wakes else None


    def provider_request(self, send):
        """Reserve durably before a one-shot send; lock remains held to completion."""
        xp.require(self._lock_owned is None, "proxy_lock")
        with state_lock(self.path) as ownership:
            self._lock_owned = ownership
            try:
                self._s = self._load()
                now = self._now()
                midnight = datetime.combine(now.date() + timedelta(days=1), time(), tzinfo=timezone.utc)
                xp.require((midnight - now).total_seconds() > 11, "proxy_budget")
                budget = self._s["proxy_provider_budget"]
                today = now.date().isoformat()
                xp.require(budget["day"] is None or budget["day"] <= today, "proxy_budget")
                if budget["day"] is None or budget["day"] < today:
                    budget.update(day=today, used=0)
                xp.require(budget["used"] < 899, "proxy_budget")
                budget["used"] += 1
                self._save()
                xp.require(self._now().date().isoformat() == today, "proxy_budget")
                return send()
            finally:
                self._lock_owned = None

    def health(self) -> dict:
        """Active over total and per-account label, state and last use; the pause and its end; never a secret."""
        accts = []
        for x in self.labels:
            state, reason = self.account_state(x)
            a = self._acct(x)
            accts.append({"label": x, "state": state, "reason": reason, "last_used": a["last_used"],
                          "reads_today": self.reads_today(x), "cap": self.cap,
                          "rest_until": a["rest_until"], "ready": self.ready_today(x),
                          "parse_strikes": a["parse_strikes"], "parse_strike_last_at": a["parse_strike_last_at"]})
            safe = {}
            for key in ("proxy_id", "identity_revision", "proxy_reason", "proxy_checked_at", "proxy_quarantine_until"):
                if a[key] is not None:
                    safe[key] = a[key]
            if self.proxy_direct:
                safe["proxy_state"] = "direct"
            elif a["proxy_health"] == "quarantined":
                safe["proxy_state"] = "quarantined"
            elif a["proxy_health"] == "healthy" and a["proxy_checked_at"] and timedelta(0) <= self._now() - datetime.fromisoformat(a["proxy_checked_at"]) < timedelta(seconds=self.proxy_max_age):
                safe["proxy_state"] = "healthy"
            else:
                safe["proxy_state"] = "blocked" if a["proxy_reason"] in xp.BLOCK_REASONS else "unknown"
            if self.connection_style is not None:
                safe["connection_style"] = self.connection_style
            if self.proxy_regions.get(x) is not None:
                safe["region"] = self.proxy_regions[x]
            accts[-1].update(safe)
            if self.b3_status:
                quiet = x_quiet.quiet_until(self._now(), x, self.quiet_hours, enabled=bool(self.quiet_hours))
                accts[-1]["behaviour"] = {
                    "quiet_until": quiet.isoformat() if quiet else None,
                    "cooldown_until": a["behaviour_cooldown_until"], "cooldown_reason": a["behaviour_reason"],
                    "warmup_stage": x_behaviour.warmup_stage(a["warmup_start_day"], self._now().date()),
                    "effective_cap": self.effective_cap(x),
                    "mixed_calls_today": x_behaviour.mixed_today(a["mixed_day"], a["mixed_calls"], self._now().date())}
        paused = self.is_paused() and not self._s["stopped"]
        return {"active": sum(1 for a in accts if a["state"] == "active"), "total": len(self.labels),
                "accounts": accts, "pause_reason": self.pause_reason(),
                "pause_until": self._s["pause_until"] if paused else None, "drift_streak": self._s["drift_streak"],
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
    """Apply a NoAccountError's cause to our state; return `restart`, `wait` (the account waits for the library's
    in-flight lock; another account may take the unit) or the unit's missing reason."""
    row = reader.pool_row()
    evidence = failure.status == xr.RATE_LIMIT_STATUS or pool.rate_limit_evidence(label)
    cause, reason = xr.no_account_cause(row, pool._now(), rate_limit_evidence=evidence)
    if cause == "inactive":
        pool.mark_inactive(label, reason)
        return "restart"
    if cause == "locked":
        pool.lock_for_day(label)
        return "restart"
    if cause == "waiting":
        pool.wait_for_lock(label, xr.search_lock(row))
        return "wait"
    return reason


Fallback = Callable[[str, str, dict, int], "xr.RawPage | None"]


def _on_block(pool: XPool, f: xr.ReaderFailure, config: CollectorConfig, fallback: Fallback | None, label: str,
              query: str, kv: dict, page_no: int, events: list, *, src, counts=None) -> tuple[xr.RawPage | None, str | None]:
    """A Cloudflare or HTML block: (the fallback's page, None) after the pool's one curl retry of the UTC day,
    else (None, block reason) with the UTC day paused for the whole pool."""
    block = f"{f.abort}_block"
    decision = xr.fallback_decision(f.abort, allow_curl=config.x_allow_curl_backend, retried=pool.curl_used_today())
    if decision == "curl_retry" and fallback is not None:
        pool.note_curl()
        try:
            raw = fallback(label, query, kv, page_no)
        except xr.ReaderFailure as failure:
            if failure.charged_reads:
                src.record_loaded(failure.charged_reads)
                pool.charge(label, failure.charged_reads)
                if counts is not None:
                    counts["reads"] += failure.charged_reads
                    counts["pages"] += 1
            if failure.kind == "proxy":
                pool.proxy_result(label, reason=failure.proxy_reason, quarantine_seconds=config.x_proxy_quarantine_seconds)
                return None, failure.proxy_reason
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
    through the same fallback rule as a unit read (one curl retry for the canary, then the day pauses). An account
    waiting for the library's in-flight lock does not drop out of the day's canary: the whole canary runs again
    after that lock ends (its reads so far still count)."""
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
    events = []
    waited = False
    for i, label in enumerate(labels):
        if not src.can_spend(xr.PAGE_ENTRIES):
            src.mark_spent()
            return CanaryOutcome(False, reason="budget_spent")
        if i:
            sleep(rng.uniform(config.x_query_delay_min_s, config.x_query_delay_max_s))
        pool.mark_used(label)
        reader = readers[label]
        src.stamp_attempt()  # before the request: a request killed in flight still counts for the spacing
        try:
            raw = reader.search_raw(query, kv, 0)
        except xr.ReaderFailure as f:
            src.stamp_attempt()
            if f.charged_reads:
                src.record_loaded(f.charged_reads)
                pool.charge(label, f.charged_reads)
            if f.kind == "proxy":
                pool.proxy_result(label, reason=f.proxy_reason, quarantine_seconds=config.x_proxy_quarantine_seconds)
                continue
            if not _is_block(f):
                if f.kind == "no_account":
                    waited |= _account_failure(pool, label, reader, f) == "wait"
                elif xr.inactive_reason(f):
                    pool.mark_inactive(label, xr.inactive_reason(f))
                continue
            raw, block = _on_block(pool, f, config, fallback, label, query, kv, 0, events, src=src)
            if block:
                if block in xp.REASONS:
                    continue
                return CanaryOutcome(False, reason=block)
        if raw is None:
            src.stamp_attempt()
            results[label] = set()
            continue
        src.record_loaded(len(raw.entry_ids))
        pool.charge(label, len(raw.entry_ids))
        pool.note_remaining(label, raw.rate_limit_remaining)
        src.record_unit()
        results[label] = xr.canary_ids(reader.parse_tweets(raw.body), start, end)
    if waited and pool.pause_for_locks():
        return CanaryOutcome(False, reason=WAIT_REASON)
    pool.mark_canaried(list(results))
    if not results:
        reason = pool.pause_no_account(src)
        return CanaryOutcome(False, reason=reason)
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


def _drift(pool: XPool, evaluate: Callable[[], str | None] | None = None, *, confirmed: bool = False) -> str:
    """Count one drift. A confirmed drift (the one that would stop X, or a 404 on two accounts) first runs the
    forced candidate evaluation when one is wired; an adoption clears the streak instead of stopping."""
    if evaluate is not None and (confirmed or pool._s["drift_streak"] + 1 >= DRIFT_STOP) and evaluate() == "adopted":
        pool.clear_drift()
        return "drift"
    return "layout_changed" if pool.note_drift() >= DRIFT_STOP else "drift"


def _evaluate_pending(pool: XPool, readers, src, config: CollectorConfig, bind, observed_by: str) -> str | None:
    """XD-4: only in `auto` mode, with a bind hook and a registry candidate."""
    if bind is None or config.x_queryid_mode != "auto":
        return None
    cand = xq.load(xq.state_path(cache.CACHE_ROOT))["operations"][xq.TRACKED]["candidate"]
    if cand is None:
        return None
    return pool.evaluate_candidate(xq.TRACKED, cand["id"], readers=readers, src=src, config=config, bind=bind,
                                   observed_by=observed_by)


def _parse_drop_kind(body: dict, entry_ids: tuple[str, ...], parsed: int) -> str:
    """Only classify stripped when every identified tweet entry has an empty result."""
    found = {}
    def visit(value):
        if isinstance(value, dict):
            entry_id = value.get("entryId")
            if entry_id in entry_ids:
                content = value.get("content")
                item = content.get("itemContent") if isinstance(content, dict) else None
                found[entry_id] = item.get("tweet_results") if isinstance(item, dict) else None
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    if not parsed:
        visit(body)
        if len(found) == len(entry_ids) and found and all(value == {} for value in found.values()):
            return "content_stripped"
    return "unparseable"


def _run_attempt(pool, reader, src, config, *, label, attempt, symbol, day, query, rng, sleep, fallback, collected_at,
                 counts, evaluate=None) -> _Attempt:
    out, kv = _Attempt(), x_window.search_kv()
    variation = x_behaviour.variation(label, pool._now().date(), page_cap=xr.PAGE_ENTRIES,
                                      enabled=config.x_variation_enabled)
    if config.x_variation_enabled:
        kv["count"] = variation.page_size
    for page_no in range(config.x_page_cap):
        if pool.is_paused() or src.is_paused():
            return _Attempt("stop", "paused")
        if not src.can_spend(variation.page_size):
            src.mark_spent()
            return _Attempt("stop", "budget_spent")
        if page_no:
            sleep(rng.uniform(config.x_page_gap_min_s, config.x_page_gap_max_s) * variation.pause_multiplier)
        backend = "default"
        src.stamp_attempt()  # before the request: a request killed in flight still counts for the spacing
        try:
            raw = reader.search_raw(query, kv, page_no)
        except xr.ReaderFailure as f:
            src.stamp_attempt()
            if f.charged_reads:
                src.record_loaded(f.charged_reads)
                pool.charge(label, f.charged_reads)
                counts["reads"] += f.charged_reads
                counts["pages"] += 1
            if f.kind == "proxy":
                pool.proxy_result(label, reason=f.proxy_reason, quarantine_seconds=config.x_proxy_quarantine_seconds)
                return _Attempt("restart", f.proxy_reason)
            if _is_block(f):
                raw, block = _on_block(pool, f, config, fallback, label, query, kv, page_no, out.events, src=src, counts=counts)
                if block:
                    return _Attempt("restart" if block in xp.REASONS else "stop", block, events=out.events)
                backend = "curl"
            elif f.kind == "no_account":
                step = _account_failure(pool, label, reader, f)
                return _Attempt("restart" if step in ("restart", "wait") else "stop", step)
            elif f.kind == "not_found":
                return _Attempt("restart", "not_found")  # run_unit decides: rerun elsewhere once, or drift
            elif xr.inactive_reason(f):
                pool.mark_inactive(label, xr.inactive_reason(f))
                return _Attempt("restart", xr.inactive_reason(f))
            elif f.kind in xr.DRIFT_KINDS or f.kind == "abort":
                return _Attempt("stop", _drift(pool, evaluate))
            else:
                return _Attempt("stop", "failed")
        except Exception:
            src.stamp_attempt()
            raise
        if raw is None:
            raw = xr.RawPage({}, ())  # rule 20b: None is not an error, it is an exhausted cursor
        n = len(raw.entry_ids)
        src.record_loaded(n)
        pool.charge(label, n)
        pool.note_remaining(label, raw.rate_limit_remaining)
        counts["reads"] += n
        counts["pages"] += 1 + raw.retries
        x_raw.write_page(symbol, day, attempt=attempt, page=page_no, body=raw.body, entry_ids=raw.entry_ids,
                         retries=raw.retries, headers=raw.headers(), collected_at=collected_at,
                         parser_version=xr.PARSER_VERSION, reader_version=reader.version,
                         reader_commit=reader.commit, backend=backend,
                         scrub_names={name: label for name in reader.account_names}, entry_times=raw.entry_times,
                         requested_page_size=variation.page_size if config.x_variation_enabled else None)
        end = x_window.cursor_end(raw.entry_ids, seen=out.seen, last_entries=out.last_entries,
                                  page_size=variation.page_size)
        if end:
            # Exhausted (exact, given the account passed today's canary) or stalled (never exact).
            out.reason = x_window.stop_reason(pages=page_no + 1, entries_read=out.n_read, oldest_read=out.oldest(),
                                              day=day, sample_n=config.x_sample_n, page_cap=config.x_page_cap,
                                              exhausted=end == "cursor_exhausted", stalled=end == x_window.STALLED)
            return out
        try:
            tweets = reader.parse_tweets(raw.body)
        except Exception:  # noqa: BLE001 - a broken page must never become a zero
            tweets = []
        if xr.parse_drop(entries=n, parsed=len(tweets), threshold=config.x_parse_drop_threshold) or \
                xr.small_page_drop(entries=n, parsed=len(tweets)):
            kind = _parse_drop_kind(raw.body, raw.entry_ids, len(tweets))
            single = len(pool.usable()) <= 1
            shared = pool.parse_failure_seen_elsewhere(label, kind)
            strikes = pool.note_parse_drop(label, kind)
            src.stamp_attempt()
            if shared or (single and strikes >= 2):
                pool.stop("layout_changed")
                return _Attempt("stop", "layout_changed")
            return _Attempt("restart", "account_failed")
        if n:
            pool.clear_parse_strikes(label)
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
             fallback: Fallback | None = None, bind: Callable[[str], None] | None = None) -> XUnitOutcome:
    """One X coin-day across the pool: one account end to end, at most `x_unit_max_restarts` restarts.

    `fallback(label, query, kv, page)` is the owner-allowed curl process of rule 19 (W8d2); it is called at most
    once per UTC day for the whole pool (`XPool.curl_used_today`) and only when `fallback_decision` says so; the
    next block pauses the day. On a value the raw pages are marked complete and the X evidence row is built by
    `x_raw.reparse` from them, so a re-parse gives the same row.
    """
    if pool.is_paused() or src.is_paused():
        return XUnitOutcome(None, "paused")
    if not pool.canary_passed_today():
        return XUnitOutcome(None, "canary_pending")
    due = src.earliest_next(config.x_query_delay_min_s)
    now = _utc(src.clock())
    if due is not None and now < due:
        return XUnitOutcome(None, "too_early")
    counts = {"reads": 0, "pages": 0}
    attempts = restarts = 0
    label = None

    def done(result, reason, row=None):
        if result is None and counts["pages"]:
            src.stamp_attempt()  # requests were sent: the next unit still waits the minimum delay
        return XUnitOutcome(result, reason, label, attempts, restarts, row, counts["pages"], counts["reads"])

    waiting = False  # the last attempt's account waits for the library's in-flight lock
    failed_labels = set()
    first_404 = None  # XD-1: the account whose SearchTimeline 404 this unit reruns elsewhere once
    extra = 0
    while attempts < 1 + config.x_unit_max_restarts + extra:
        sel = pool.select(exclude=failed_labels)
        if sel is None:
            return done(None, "account_failed" if failed_labels else pool.pause_no_account(src))
        if attempts:
            restarts += 1
        attempts += 1
        label, reader = sel.label, readers[sel.label]
        pool.mark_used(label)
        evaluate = (lambda observed=label: _evaluate_pending(pool, readers, src, config, bind, observed))
        att = _run_attempt(pool, reader, src, config, label=label, attempt=attempts, symbol=symbol, day=day,
                           query=query, rng=rng, sleep=sleep, fallback=fallback, collected_at=now, counts=counts,
                           evaluate=evaluate)
        if att.status == "restart" and att.reason == "not_found":
            if first_404 is None and any(x != label and x not in failed_labels for x in pool.usable()):
                first_404, extra = label, 1
                failed_labels.add(label)
                pool.log.append(f"x pool: {label} SearchTimeline 404; the unit reruns once on another account")
                continue
            return done(None, _drift(pool, evaluate, confirmed=first_404 is not None))
        if att.status == "restart":
            if att.reason == "account_failed":
                failed_labels.add(label)
            waiting = att.reason == "wait"
            continue
        if att.status == "stop":
            return done(None, att.reason)
        if first_404 is not None:
            pool.note_endpoint_404(first_404)
            pool.fact({"kind": "handoff", "source": FACTS_SOURCE, "from_account": first_404, "to_account": label,
                       "reason": "endpoint_404"})
            first_404 = None
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
        pool.note_result(label, day, att.n_read)
        pool.fact({"kind": "unit_completed", "source": FACTS_SOURCE, "account": label, "coin": symbol,
                   "coin_day": day.isoformat(), "reads": counts["reads"], "pages": counts["pages"],
                   "raw_results": att.n_read})
        meta = {"attempt": attempts, "label": label, "attempts": attempts, "restarts": restarts,
                "backend_events": att.events, "overhead_requests": reader.overhead_requests, "canary_ok": canary_ok}
        x_raw.mark_complete(symbol, day, meta, run=x_raw.run_id(now))
        row = x_raw.reparse(symbol, day, parse=reader.parse_tweets, coin=coin, cfg=config,
                            parser_version=xr.PARSER_VERSION, policy=policy)
        x_raw.write_x_row(symbol, row)
        return done(summary.result, att.reason, row)
    if waiting:  # not failed: the coin-day is tried again after the lock ends
        return done(None, pool.pause_no_account(src) if not pool.usable() else WAIT_REASON)
    return done(None, "account_failed")


def mixed_pick(targets, label: str, day: date, calls: int, stale: set[str]):
    candidates = [(op, target) for op in x_behaviour.MIXED_OPS if op not in stale for target in targets
                  if (not target.isdecimal() if op == "user_by_login" else target.isdecimal())]
    if not candidates:
        return None, None
    seed = int.from_bytes(hashlib.sha256(f"{label}|{day}".encode()).digest()[:8], "big")
    return candidates[(seed + calls) % len(candidates)]


def run_mixed(pool, readers, src, config, *, units_since_last: int, stale: set[str]) -> str | None:
    """One optional ordinary page. Callback charging is authoritative, including failures; never coin writes."""
    if not config.x_mixed_traffic_enabled or not config.x_mixed_targets or pool.is_paused() or src.is_paused():
        return None
    if not pool.canary_passed_today():
        return None
    label = pool.peek()
    if label is None:
        return None
    a, today = pool._acct(label), pool._now().date()
    calls = x_behaviour.mixed_today(a["mixed_day"], a["mixed_calls"], today)
    op, target = mixed_pick(config.x_mixed_targets, label, today, calls, stale)
    cap = pool.effective_cap(label)
    room = src.remaining()
    if cap is not None:
        room = min(room, cap - (pool.reads_today(label) or 0))
    if not x_behaviour.mixed_allowed(op, enabled=True, units_since_last=units_since_last,
                                    calls_today=calls, room=room):
        return None
    with state_lock(pool.path) as ownership:
        pool._lock_owned = ownership
        try:
            pool._s = pool._load()
            a = pool._acct(label)
            a["mixed_day"], a["mixed_calls"] = today.isoformat(), calls + 1
            pool._save()
        finally:
            pool._lock_owned = None
    charged = False
    def on_page(actual):
        nonlocal charged
        if charged:
            raise ValueError("ordinary call produced more than one page")
        charged = True
        reads = x_behaviour.mixed_charge(actual)
        src.record_loaded(reads)
        pool.charge(label, reads)
        pool.fact({"kind": "mixed_call", "source": FACTS_SOURCE, "account": label, "target": op, "reads": reads})
    src.stamp_attempt()
    try:
        readers[label].ordinary(op, target, on_page=on_page)
    except xr.ReaderFailure as failure:
        if failure.kind == "not_found":
            stale.add(op)
            pool.fact({"kind": "queryid_state", "operation": op, "from_state": "pinned",
                       "to_state": ORDINARY_STALE, "reason": ORDINARY_STALE})
        elif xr.inactive_reason(failure):
            pool.mark_inactive(label, xr.inactive_reason(failure))
        elif failure.kind == "proxy":
            pool.proxy_result(label, reason=failure.proxy_reason,
                              quarantine_seconds=config.x_proxy_quarantine_seconds)
    finally:
        if not charged:
            on_page(0)
    return op
