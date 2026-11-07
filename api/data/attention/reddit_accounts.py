"""Reddit account pool state (S-RAcct-A): selection, caps, rest, ready and the CK-2 session day guard.

Reddit has its own account model; X's states are not widened. Pure logic over an injected clock; no network.
- Single-writer file `<cache>/attention/_pc_state/reddit_accounts.json` (`{"accounts": {label: entry}}`), exact keys,
  `setdefault` migration, atomic writes under the adjacent lock (`state_lock`). Labels no longer configured are kept
  untouched and never selected. Ready marks live in the separate `reddit_account_ready.json`
  (`{"ready": {label: "YYYY-MM-DD"}}`), written only by `--mark-ready`; a mark counts from the next UTC day.
- States: `active`, `resting` (rest period or no ready mark), `locked` (daily cap, route not admitted), `paused`
  (sticky: login, challenge, suspension; a `logged_in` session check reopens login/challenge pauses only).
- Selection: least recently used usable account, ties by registration order. A poll is read by ONE account start
  to finish; a lost account's unfinished poll is retried once on another account, and its data is counted once
  (the lost attempt's navigations stay charged). None usable: `no_ready_account`, missing, never zero.
- `try_claim` is the atomic CK-2 day guard (`DayGuard.try_claim(site, label, day)`), backed by `session_day`.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from api.data import cache
from api.data.attention import x_proxy as xp
from api.data.attention.x_pool import LABEL_RE
from api.data.attention.x_proxy_private import atomic_json, read_bounded, state_lock

STATES = ("active", "resting", "paused", "locked")
REASONS = ("reddit_login_required", "challenge", "cap", "resting", "proxy_quarantined", "proxy_not_admitted",
           "suspended", "unknown")
LOSS_REASONS = ("reddit_login_required", "challenge", "suspended", "proxy_quarantined", "proxy_not_admitted",
                "unknown")
REOPENED_BY_LOGIN = ("reddit_login_required", "challenge")
SESSION_PAUSES = {"logged_out": "reddit_login_required", "expired": "reddit_login_required",
                  "challenge": "challenge", "suspended": "suspended"}
SESSION_STATES = ("logged_in", *SESSION_PAUSES, "refused", "unknown")
PROXY_STATES = ("direct", "unknown", "healthy", "quarantined", "blocked")
NO_READY_ACCOUNT = "no_ready_account"
B2_ACCOUNT_KEYS = ("proxy_id", "identity_revision", "proxy_health", "proxy_checked_at",
                   "proxy_quarantine_until", "proxy_reason", "proxy_changed_at")
ACCOUNT_KEYS = frozenset({"state", "reason", "reads_day", "reads_used", "rest_until", "last_used", "session_state",
                          "session_checked_at", "session_day", "proxy_state", *B2_ACCOUNT_KEYS})
TIME_KEYS = ("rest_until", "last_used", "session_checked_at", "proxy_checked_at", "proxy_quarantine_until",
             "proxy_changed_at")
STATE_FILE = "reddit_accounts.json"
READY_FILE = "reddit_account_ready.json"
STATE_LIMIT = 256 * 1024


class RedditAccountStateError(ValueError):
    """The Reddit account state is unreadable or invalid; never holds the content."""


class AccountLost(Exception):
    """Raised by a poll reader when its account is lost or paused mid-poll; `navigations` stay charged."""

    def __init__(self, reason: str, navigations: int = 0):
        if reason not in LOSS_REASONS or type(navigations) is not int or navigations < 0:
            raise ValueError("unknown loss reason or bad navigation count")
        super().__init__(reason)
        self.reason, self.navigations = reason, navigations


@dataclass(frozen=True)
class PollResult:
    label: str | None
    value: Any
    reason: str | None
    attempts: tuple[str, ...]


def _root() -> Path:
    return cache.CACHE_ROOT / "attention" / "_pc_state"


def _utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("clock must be timezone-aware UTC")
    return now.astimezone(timezone.utc)


def _iso(value) -> bool:
    try:
        return value is None or (isinstance(value, str) and datetime.fromisoformat(value).tzinfo is not None)
    except ValueError:
        return False


def _day(value) -> bool:
    try:
        return value is None or (isinstance(value, str) and date.fromisoformat(value).isoformat() == value)
    except ValueError:
        return False


def _read_json(path: Path):
    return xp.strict_json(read_bounded(path, STATE_LIMIT), limit=STATE_LIMIT)


def read_ready() -> dict[str, str]:
    """Label -> marked ISO day. Bad evidence is not ready."""
    try:
        doc = _read_json(_root() / READY_FILE)
    except (OSError, ValueError, xp.ProxyFailure):
        return {}
    marks = doc.get("ready") if isinstance(doc, dict) else None
    if not isinstance(marks, dict):
        return {}
    return {k: v for k, v in marks.items() if LABEL_RE.fullmatch(k) and v is not None and _day(v)}


def write_ready(label: str, now: datetime, *, labels) -> None:
    """Owner mark (separate atomic file under its own lock): the account joins from the next UTC day."""
    if label not in labels or not LABEL_RE.fullmatch(label):
        raise ValueError("configured label required")
    path = _root() / READY_FILE
    with state_lock(path):
        marks = read_ready()
        marks[label] = _utc(now).date().isoformat()
        atomic_json(path, {"ready": marks})


def _fresh(proxy_required: bool) -> dict:
    return dict.fromkeys(ACCOUNT_KEYS) | {"state": "active", "reads_used": 0, "proxy_health": "unknown",
                                          "proxy_state": "unknown" if proxy_required else "direct"}


def _valid_entry(a) -> bool:
    return (isinstance(a, dict) and set(a) == ACCOUNT_KEYS and a["state"] in STATES
            and (a["reason"] is None or a["reason"] in REASONS)
            and type(a["reads_used"]) is int and a["reads_used"] >= 0 and _day(a["reads_day"])
            and _day(a["session_day"]) and all(_iso(a[k]) for k in TIME_KEYS)
            and (a["session_state"] is None or a["session_state"] in SESSION_STATES)
            and a["proxy_state"] in PROXY_STATES)


def _transaction(method):
    """Reload under the adjacent lock; public transactions never call other transactions."""
    @wraps(method)
    def call(self, *args, **kwargs):
        with state_lock(self.path):
            self._s = self._load()
            return method(self, *args, **kwargs)
    return call


class RedditAccounts:
    def __init__(self, labels: list[str], *, clock: Callable[[], datetime], cap: int | None = None,
                 rest_days: int = 0, proxy_required: bool = False,
                 admission: Callable[[str, str], str] | None = None):
        if len(set(labels)) != len(labels) or not all(LABEL_RE.fullmatch(x) for x in labels):
            raise ValueError("invalid labels")
        self.labels, self.clock, self.cap, self.rest_days = list(labels), clock, cap, rest_days
        self.proxy_required = proxy_required
        self.admission = admission
        self.path = _root() / STATE_FILE
        self._s: dict = {"accounts": {}}

    # --- persistence ---
    def _load(self) -> dict:
        existed = self.path.exists()
        if not existed:
            s = {"accounts": {}}
        else:
            try:
                s = _read_json(self.path)
            except (OSError, ValueError, xp.ProxyFailure):
                raise RedditAccountStateError("reddit account state unreadable") from None
            if not isinstance(s, dict) or set(s) != {"accounts"} or not isinstance(s["accounts"], dict):
                raise RedditAccountStateError("reddit account state invalid")
            for label, a in s["accounts"].items():
                if isinstance(a, dict):
                    for key in ACCOUNT_KEYS:  # migration: a file from an earlier layout
                        a.setdefault(key, _fresh(self.proxy_required)[key])
                if not LABEL_RE.fullmatch(label) or not _valid_entry(a):
                    raise RedditAccountStateError("reddit account state invalid")
        for label in self.labels:
            if label not in s["accounts"]:
                a = _fresh(self.proxy_required)
                if self.rest_days:
                    a["rest_until"] = (self._now() + timedelta(days=self.rest_days)).isoformat()
                s["accounts"][label] = a
        return s

    def _save(self) -> None:
        for label in self.labels:
            a = self._acct(label)
            a["proxy_state"] = self._proxy_state(a)
            a["state"], a["reason"] = self._effective(label)
        atomic_json(self.path, self._s)

    @_transaction
    def begin_pass(self) -> None:
        self._save()

    def _now(self) -> datetime:
        return _utc(self.clock())

    def _today(self) -> str:
        return self._now().date().isoformat()

    def _acct(self, label: str) -> dict:
        if label not in self.labels:
            raise ValueError("unknown label")
        return self._s["accounts"][label]

    def _proxy_state(self, a: dict) -> str:
        if not self.proxy_required:
            return "direct"
        if a["proxy_reason"] in xp.BLOCK_REASONS:
            return "blocked"
        return a["proxy_health"] if a["proxy_health"] in ("healthy", "quarantined") else "unknown"

    def _ready(self, label: str) -> bool:
        mark = read_ready().get(label)
        return bool(mark and mark < self._today())

    def _effective(self, label: str) -> tuple[str, str | None]:
        a = self._acct(label)
        if a["state"] == "paused":
            return "paused", a["reason"] or "unknown"
        if (a["rest_until"] and self._now() < datetime.fromisoformat(a["rest_until"])) or not self._ready(label):
            return "resting", "resting"
        if self.proxy_required:
            if a["proxy_health"] == "quarantined":
                return "locked", "proxy_quarantined"
            if a["proxy_health"] != "healthy":
                return "locked", "proxy_not_admitted"
        route = self.admission("reddit", label) if self.admission is not None else "unadmitted"
        if route != ("proxy" if self.proxy_required else "direct"):
            return "locked", "proxy_not_admitted"
        if self.cap is not None and self._reads_today(a) >= self.cap:
            return "locked", "cap"
        return "active", None

    def _reads_today(self, a: dict) -> int:
        return a["reads_used"] if a["reads_day"] == self._today() else 0

    # --- reads ---
    @_transaction
    def account_state(self, label: str) -> tuple[str, str | None]:
        return self._effective(label)

    @_transaction
    def reads_today(self, label: str) -> int:
        return self._reads_today(self._acct(label))

    @_transaction
    def usable(self) -> list[str]:
        return [x for x in self.labels if self._effective(x)[0] == "active"]

    @_transaction
    def select(self, *, exclude=()) -> str | None:
        """Least recently used usable account; never-used first; ties by registration order."""
        cands = [x for x in self.labels if x not in exclude and self._effective(x)[0] == "active"]
        if not cands:
            return None
        return min(cands, key=lambda x: (self._acct(x)["last_used"] or "", self.labels.index(x)))

    # --- writes ---
    @_transaction
    def mark_used(self, label: str) -> None:
        self._acct(label)["last_used"] = self._now().isoformat()
        self._save()

    @_transaction
    def charge(self, label: str, navigations: int) -> None:
        if type(navigations) is not int or navigations < 0:
            raise ValueError("bad navigation count")
        a = self._acct(label)
        if a["reads_day"] != self._today():
            a["reads_day"], a["reads_used"] = self._today(), 0
        a["reads_used"] += navigations
        self._save()

    @_transaction
    def pause(self, label: str, reason: str) -> None:
        if reason not in LOSS_REASONS:
            raise ValueError("unknown pause reason")
        a = self._acct(label)
        if reason in ("proxy_quarantined", "proxy_not_admitted"):
            a["proxy_health"] = "quarantined" if reason == "proxy_quarantined" else "unknown"
        elif not (a["state"] == "paused" and a["reason"] not in REOPENED_BY_LOGIN):
            a["state"], a["reason"] = "paused", reason
        self._save()

    @_transaction
    def set_proxy(self, label: str, **fields) -> None:
        """The seven B2 proxy fields (route integration, S-RAcct-B, writes them through here)."""
        if set(fields) - set(B2_ACCOUNT_KEYS):
            raise ValueError("unknown proxy field")
        a = self._acct(label)
        a.update(fields)
        if not _valid_entry(a | {"proxy_state": self._proxy_state(a | fields)}):
            raise ValueError("invalid proxy field")
        self._save()

    @_transaction
    def record_session(self, label: str, session_state: str) -> None:
        """A session check outcome: logged_in reopens login/challenge pauses; a lost session pauses."""
        if session_state not in SESSION_STATES:
            raise ValueError("unknown session state")
        a = self._acct(label)
        a["session_state"], a["session_checked_at"] = session_state, self._now().isoformat()
        if session_state == "logged_in" and a["state"] == "paused" and a["reason"] in REOPENED_BY_LOGIN:
            a["state"], a["reason"] = "active", None
        elif session_state in SESSION_PAUSES and not (a["state"] == "paused" and a["reason"] == "suspended"):
            a["state"], a["reason"] = "paused", SESSION_PAUSES[session_state]
        self._save()

    @_transaction
    def try_claim(self, site: str, label: str, day: str) -> bool:
        """CK-2 day guard: at most one automatic session check per account per UTC day, atomic across processes."""
        if site != "reddit" or label not in self.labels or not isinstance(day, str) or not _day(day):
            raise ValueError("reddit site, configured label and ISO day required")
        a = self._acct(label)
        if a["session_day"] is not None and a["session_day"] >= day:
            return False
        a["session_day"] = day
        self._save()
        return True


def from_config(config, *, clock: Callable[[], datetime],
                admission: Callable[[str, str], str] | None = None) -> RedditAccounts:
    """Admission(site, label) -> 'proxy'|'direct'|'unadmitted'; omitted means fail closed.

    S-RAcct-B supplies authoritative, current site-scoped route admission. A stored healthy flag alone
    never admits a route. Any configured proxy input disables direct, including union assignments.
    """
    proxy_required = bool(getattr(config, "x_proxy_required", False)) or any(
        getattr(config, key, None) is not None
        for key in ("x_proxy_list_path", "x_proxy_assignments_path", "x_proxy_policy_path"))
    return RedditAccounts([a["label"] for a in config.reddit_browser_accounts], clock=clock,
                          cap=config.reddit_browser_account_daily_cap,
                          rest_days=config.reddit_browser_account_rest_days, proxy_required=proxy_required,
                          admission=admission)


def run_poll(pool: RedditAccounts, read: Callable[[str], tuple[Any, int]]) -> PollResult:
    """One poll by one account; on `AccountLost` the unfinished poll is retried once on another account."""
    attempts: list[str] = []
    reason = NO_READY_ACCOUNT
    for _ in range(2):
        label = pool.select(exclude=attempts)
        if label is None:
            return PollResult(None, None, NO_READY_ACCOUNT, tuple(attempts))
        attempts.append(label)
        pool.mark_used(label)
        try:
            value, navigations = read(label)
        except AccountLost as lost:
            pool.charge(label, lost.navigations)
            pool.pause(label, lost.reason)
            reason = lost.reason
            continue
        pool.charge(label, navigations)
        return PollResult(label, value, None, tuple(attempts))
    return PollResult(None, None, reason, tuple(attempts))


def _load_config(path: Path | None):
    from api.data.attention import web_queries
    return (web_queries.load(path) if path else web_queries.load()).config


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="reddit_accounts", description="Reddit account owner commands (codes only).")
    p.add_argument("--mark-ready", metavar="LABEL", required=True,
                   help="mark a configured Reddit account ready from the next UTC day")
    p.add_argument("--queries", type=Path, help="explicit absolute owner query configuration")
    args = p.parse_args(argv)
    try:
        config = _load_config(args.queries)
        write_ready(args.mark_ready, datetime.now(timezone.utc),
                    labels=[a["label"] for a in config.reddit_browser_accounts])
    except (OSError, ValueError, xp.ProxyFailure):
        sys.stdout.write("ready status=refused\n")
        return 2
    sys.stdout.write(f"ready status=ok label={args.mark_ready}\n")  # configured label, validated by write_ready
    return 0


if __name__ == "__main__":
    sys.exit(main())
