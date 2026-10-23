"""Transport seam for the PC-side X collector (SPEC rule 12, Annex D, AC11, AC19, AC27). Pure; no network.

`XAdapter` is the only surface the collector calls. The real API Anything adapter arrives in W8d, pinned to
`PINNED_COMMIT`; here are the Protocol, the error classes the collector reacts to, a scripted fake for tests,
the `SafeAdapter` wrapper that refuses API Anything's registry pull, publish and cookie import features, the
monthly self-repair cost meter (15 USD per UTC calendar month) and the log helper that writes only the
exception class name and the HTTP status.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from api.data import cache
from api.data.attention.density import Post

PINNED_COMMIT = "20cb677039fcfe92d3d9c777aa9362e30ff1fdb8"
INSTALL_COMMAND = "npm ci --ignore-scripts"
MONTHLY_REPAIR_CAP_USD = 15.0
PROFILE_ENV = "SCREENER_PC_PROFILE_DIR"
DEFAULT_PROFILE_NAME = ".screener-pc-profile"  # under the owner's home folder, outside any repository
REPO_ROOT = Path(__file__).resolve().parents[3]
# API Anything features the wrapper never reaches: registry pull, publish, cookie import.
_REFUSED = re.compile(r"registry|publish|cookie", re.IGNORECASE)
_SHIPPED_RECIPE = re.compile(r"x\..+")
_MONTH_RE = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")


class CollectorError(Exception):
    """A collection failure. Carries a fixed reason and an int HTTP status, never a message or body."""

    reason = "failed"
    warning = False  # True: pause the source for the rest of the UTC day, no retry (Locked pacing rule 3)

    def __init__(self, status: int | None = None):
        if status is not None and (not isinstance(status, int) or isinstance(status, bool)):
            raise TypeError("status must be an int HTTP status")
        super().__init__()
        self.status = status

    def __str__(self) -> str:
        return type(self).__name__


class RateLimited(CollectorError):
    reason, warning = "rate_limited", True


class LoginRequired(CollectorError):
    reason, warning = "x_login_required", True


class AccountSuspended(CollectorError):
    reason, warning = "x_account_suspended", True


class RedditBlocked(CollectorError):
    reason, warning = "reddit_blocked", True


class EmptyResults(CollectorError):
    reason, warning = "empty_results", True


class LayoutChanged(CollectorError):
    reason = "layout_changed"


class Offline(CollectorError):
    reason = "offline"


class BudgetSpent(CollectorError):
    reason = "budget_spent"


class SelfRepairRefused(CollectorError):
    reason = "layout_changed"


class RefusedFeature(CollectorError):
    reason = "refused_feature"


WARNING_REASONS = ("rate_limited", "x_login_required", "x_account_suspended", "reddit_blocked", "empty_results")
OWNER_ACTION_REASONS = ("x_account_suspended", "x_login_required")


@dataclass(frozen=True)
class SearchPage:
    posts: list[Post]
    has_more: bool


@runtime_checkable
class XAdapter(Protocol):
    page_size: int

    def search_page(self, query: str, since: datetime, until: datetime, page: int) -> SearchPage: ...

    def self_repair(self) -> float:
        """Run one recipe self-repair; return its LLM cost in USD."""
        ...


def is_refused_name(name: str) -> bool:
    return bool(_REFUSED.search(name)) or name.lower().startswith("import")


@dataclass
class FakeAdapter:
    """Scripted pages for tests: each call returns the next SearchPage or raises the next CollectorError."""

    pages: list[SearchPage | CollectorError] = field(default_factory=list)
    page_size: int = 20
    repair_cost_usd: float = 0.0
    calls: int = 0
    repairs: int = 0

    def search_page(self, query: str, since: datetime, until: datetime, page: int) -> SearchPage:
        self.calls += 1
        if not self.pages:
            raise LayoutChanged()
        item = self.pages.pop(0)
        if isinstance(item, CollectorError):
            raise item
        return item

    def self_repair(self) -> float:
        self.repairs += 1
        return self.repair_cost_usd


class SafeAdapter:
    """Forwards `search_page`, `self_repair` and `page_size` only; anything else is refused."""

    _ALLOWED = frozenset({"search_page", "self_repair", "page_size"})

    def __init__(self, inner: XAdapter):
        if [n for n in dir(inner) if not n.startswith("_") and is_refused_name(n)]:
            raise RefusedFeature()
        self._inner = inner

    def __getattr__(self, name: str):
        # Only reached for names not defined here; the three allowed ones are.
        raise RefusedFeature()

    def search_page(self, query: str, since: datetime, until: datetime, page: int) -> SearchPage:
        return self._inner.search_page(query, since, until, page)

    def self_repair(self) -> float:
        return self._inner.self_repair()

    @property
    def page_size(self) -> int:
        return self._inner.page_size


def check_recipe_path(path: Path) -> Path:
    """Refuse the X recipe shipped in the package (`sites/x.*`); only recipes learned on the owner's PC load."""
    p = Path(path)
    if any(part.lower() == "sites" for part in p.parts[:-1]) and _SHIPPED_RECIPE.fullmatch(p.name.lower()):
        raise RefusedFeature()
    return p


def profile_dir() -> Path:
    """The owner's API Anything profile/cookie folder; refused when it would sit inside this repository."""
    raw = os.environ.get(PROFILE_ENV)
    p = Path(raw).expanduser() if raw else Path.home() / DEFAULT_PROFILE_NAME
    resolved = p.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise RefusedFeature()
    return p


def describe_error(exc: BaseException, status: object = None) -> str:
    """`<ClassName> status=<int|none>`: the only failure text a collector log line or probe line carries.

    Never raises: a `status` attribute that raises reads as none, and an int subclass prints as a plain int.
    """
    if status is None:
        try:
            status = getattr(exc, "status", None)
        except Exception:  # noqa: BLE001 - a broken status attribute is just "no status"
            status = None
    code = int.__int__(status) if isinstance(status, int) and not isinstance(status, bool) else None
    return f"{type(exc).__name__} status={'none' if code is None else code}"


def log_failure(logger, source: str, exc: BaseException, status: object = None) -> None:
    """Log one failure as class name and status only; never raises (logging must not break a collector)."""
    label = source if isinstance(source, str) and re.fullmatch(r"[a-z0-9_]{1,40}", source) else "source"
    try:
        logger.warning("%s collector failed: %s", label, describe_error(exc, status))
    except Exception:  # noqa: BLE001, S110 - a broken logger must not stop the collector
        pass


class CostMeter:
    """Self-repair LLM spend per UTC calendar month, persisted under the cache root."""

    def __init__(self, clock: Callable[[], datetime], cap_usd: float = MONTHLY_REPAIR_CAP_USD):
        self.clock = clock
        self.cap_usd = cap_usd

    @staticmethod
    def path() -> Path:
        return cache.CACHE_ROOT / "attention" / "_pc_state" / "self_repair_cost.json"

    def _month(self) -> str:
        return self.clock().astimezone(timezone.utc).strftime("%Y-%m")

    def _current(self) -> tuple[str, float]:
        """(month, spent) to count against. A clock moved back keeps the later stored month; a file that exists
        but is unreadable or invalid counts as the cap already spent this month (fail closed)."""
        month, p = self._month(), self.path()
        if not p.exists():
            return month, 0.0
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            stored, spent = d["month"], d["spent_usd"]
            if not (isinstance(stored, str) and _MONTH_RE.fullmatch(stored) and valid_cost(spent)):
                raise ValueError
        except Exception:  # noqa: BLE001 - any unreadable meter file fails closed
            return month, self.cap_usd
        if stored >= month:
            return stored, float(spent)
        return month, 0.0

    def spent(self) -> float:
        return self._current()[1]

    def can_repair(self) -> bool:
        return self.spent() < self.cap_usd

    def charge(self, usd: float) -> None:
        if not valid_cost(usd):
            raise ValueError("cost must be a finite non-negative number")
        month, spent = self._current()
        self._write(month, spent + float(usd))

    def exhaust(self) -> None:
        """Mark the month's cap as spent (an unknown repair cost fails closed)."""
        month, spent = self._current()
        self._write(month, max(spent, self.cap_usd))

    def _write(self, month: str, spent_usd: float) -> None:
        p = self.path()
        p.parent.mkdir(parents=True, exist_ok=True)
        cache._atomic_write_json({"month": month, "spent_usd": spent_usd}, p)


def valid_cost(usd: object) -> bool:
    return isinstance(usd, (int, float)) and not isinstance(usd, bool) and math.isfinite(usd) and usd >= 0


def attempt_self_repair(adapter: XAdapter, meter: CostMeter) -> float:
    """One self-repair while the monthly cap is not spent; refused (source stays `layout_changed`) otherwise.

    A repair that raises or reports no usable cost spends the rest of the month's cap: the meter never
    under-counts.
    """
    if not meter.can_repair():
        raise SelfRepairRefused()
    try:
        cost = adapter.self_repair()
    except BaseException:
        meter.exhaust()
        raise
    if not valid_cost(cost):
        meter.exhaust()
        raise SelfRepairRefused()
    meter.charge(cost)
    return cost
