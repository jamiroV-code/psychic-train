"""X behaviour measures (B3 part a): pure, independently switchable rules. Every switch defaults off and off returns
the Part A behaviour unchanged; no rule here can raise a cap, bypass the global ceiling, skip the canary or lift the
mandatory challenge pause. S-B3I wires these into scheduling and accounting; this module reads no clock and no state.

- Warm-up (`x_warmup_enabled`): after the rest and ready eligibility, effective cap = min(configured, 100 for the first
  2 eligible UTC days, 200 for the next 2, 400 for the next 3), then the configured cap. No primary evidence of
  benefit (REF-X section 4.3).
- Variation (`x_variation_enabled`): seeded per label and UTC day; page size 10 or 20 within the page cap, pause
  multiplier 1.0-1.2 (never below base pacing), shuffle only equally due coins. Query text is never changed.
- Adaptive cooldown (`x_adaptive_cooldown_enabled`): consumes the stripped-page fix's confirmed strike (never
  reclassifies raw pages), rate-limit remaining <= 1, and a run of three shrunken units (< 25% of the mean of seven
  comparable successes). A challenge always pauses for the owner with no timed retry, switch on or off.
- Mixed traffic (`x_mixed_traffic_enabled`): only the three allowlisted ordinary operations, one per 20 completed coin
  units, at most 3 per account per UTC day, 20 read units reserved and max(20, actual) charged.
"""
from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

# --- warm-up ------------------------------------------------------------------------------------------------------

WARMUP_LADDER = ((2, 100), (4, 200), (7, 400))  # (eligible UTC days elapsed below, cap)


def warmup_stage(start_day: str | None, today: date) -> int | None:
    """1-based ladder stage, or None when not started or past the ladder."""
    if start_day is None:
        return None
    elapsed = (today - date.fromisoformat(start_day)).days
    for stage, (below, _) in enumerate(WARMUP_LADDER, 1):
        if 0 <= elapsed < below:
            return stage
    return None


def effective_cap(configured: int | None, start_day: str | None, today: date, *, enabled: bool,
                  grandfathered: bool = False) -> int | None:
    """The account's daily read cap; None means no finite per-account cap (the global ceiling still applies)."""
    stage = warmup_stage(start_day, today) if enabled and not grandfathered else None
    if stage is None:
        return configured
    ladder = WARMUP_LADDER[stage - 1][1]
    return ladder if configured is None else min(configured, ladder)


def warmup_start(current: str | None, *, eligible: bool, today: date, enabled: bool) -> str | None:
    """Persist the start day once, only when eligible; downtime and refreshes never reset it."""
    if current is not None or not enabled or not eligible:
        return current
    return today.isoformat()


# --- variation ----------------------------------------------------------------------------------------------------

PAGE_SIZES = (10, 20)
PAUSE_RANGE = (1.0, 1.2)


@dataclass(frozen=True)
class Variation:
    page_size: int
    pause_multiplier: float
    seed: int = field(default=0, repr=False)
    enabled: bool = False

    def order(self, items: list) -> list:
        """Shuffle one group of equally due items (same target UTC day); off keeps the order."""
        out = list(items)
        if self.enabled:
            random.Random(self.seed).shuffle(out)
        return out

    def order_groups(self, groups: list[list]) -> list[list]:
        """Groups stay in due order; only members within each group move."""
        return [Variation(self.page_size, self.pause_multiplier, self.seed + i, self.enabled).order(g)
                for i, g in enumerate(groups)]


def _seed(label: str, day: date) -> int:
    return int.from_bytes(hashlib.sha256(f"{label}|{day.isoformat()}".encode()).digest()[:8], "big")


def variation(label: str, day: date, *, page_cap: int, enabled: bool) -> Variation:
    if not enabled:
        return Variation(page_cap, 1.0)
    seed = _seed(label, day)
    rng = random.Random(seed)
    sizes = [s for s in PAGE_SIZES if s <= page_cap]
    size = rng.choice(sizes) if sizes else page_cap
    pause = round(rng.uniform(*PAUSE_RANGE), 3)
    return Variation(size, pause, seed, True)


# --- adaptive cooldown --------------------------------------------------------------------------------------------

BEHAVIOUR_REASONS = ("challenge", "stripped_strike", "rate_limit", "shrink")
STRIKE_COOLDOWN = timedelta(hours=1)
SHRINK_COOLDOWN = timedelta(hours=1)
RATE_LIMIT_DEFAULT_WAIT = timedelta(minutes=15)
SHRINK_RUN_TRIGGER = 3
SHRINK_RATIO = 0.25
HISTORY_LEN = 7
SHRINK_RUN_MAX = 10_000
QUERY_CLASS_RE = re.compile(r"[a-z0-9_]{1,24}")


@dataclass(frozen=True)
class Cooldown:
    reason: str
    until: datetime | None  # None: owner intervention, no timed retry
    owner_pause: bool = False


def cooldown(now: datetime, *, enabled: bool, challenge: bool = False, stripped_strike: bool = False,
             lock_until: datetime | None = None, rate_remaining: int | None = None,
             rate_reset: datetime | None = None, shrink_run: int = 0) -> Cooldown | None:
    """Decide the B3 cooldown. Precedence: challenge (always, even off), then the latest timed deadline."""
    if challenge:
        return Cooldown("challenge", None, True)
    if not enabled:
        return None
    timed = []
    if stripped_strike:
        timed.append(Cooldown("stripped_strike", max(now + STRIKE_COOLDOWN, lock_until or now)))
    if rate_remaining is not None and rate_remaining <= 1:
        timed.append(Cooldown("rate_limit", rate_reset if rate_reset and rate_reset > now
                              else now + RATE_LIMIT_DEFAULT_WAIT))
    if shrink_run >= SHRINK_RUN_TRIGGER:
        timed.append(Cooldown("shrink", now + SHRINK_COOLDOWN))
    if not timed:
        return None
    return max(timed, key=lambda c: (c.until, -BEHAVIOUR_REASONS.index(c.reason)))


def record_result(history: list[dict], shrink_run: int, *, day: date, count: int | None, query_class: str,
                  canary: bool) -> tuple[list[dict], int]:
    """Fold one successful non-canary unit into the bounded history and shrink run (canary/failed: unchanged)."""
    if canary or count is None:
        return history, shrink_run
    if type(count) is not int or count < 0 or not QUERY_CLASS_RE.fullmatch(query_class):
        raise ValueError("result count must be a nonnegative int and the class a safe token")
    comparable = [h["count"] for h in history if h["query_class"] == query_class]
    if len(comparable) >= HISTORY_LEN:
        baseline = sum(comparable[-HISTORY_LEN:]) / HISTORY_LEN
        shrink_run = min(shrink_run + 1, SHRINK_RUN_MAX) if count < SHRINK_RATIO * baseline else 0
    record = {"day": day.isoformat(), "count": count, "query_class": query_class}
    return [*history, record][-HISTORY_LEN:], shrink_run


# --- mixed traffic ------------------------------------------------------------------------------------------------

MIXED_OPS = ("user_by_login", "tweet_details", "user_tweets")
MIXED_EVERY_UNITS = 20
MIXED_DAILY_MAX = 3
MIXED_RESERVE = 20


def mixed_allowed(op: str, *, enabled: bool, units_since_last: int, calls_today: int, room: int) -> bool:
    return (enabled and op in MIXED_OPS and units_since_last >= MIXED_EVERY_UNITS
            and calls_today < MIXED_DAILY_MAX and room >= MIXED_RESERVE)


def mixed_charge(actual_units: int) -> int:
    if type(actual_units) is not int or actual_units < 0:
        raise ValueError("actual read units must be a nonnegative int")
    return max(MIXED_RESERVE, actual_units)


def mixed_today(mixed_day: str | None, mixed_calls: int, today: date) -> int:
    return mixed_calls if mixed_day == today.isoformat() else 0
