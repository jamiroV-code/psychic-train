"""Narrative-v2 RFC-4 (ADR-4): cross-sectional momentum behind
`GET /api/narrative/momentum`.

For each enabled narrative this module picks ONE basis series and computes:

- `change`       = value(as_of) - value(base1)      (MOMENTUM_WINDOW_DAYS back)
- `prev_change`  = value(base1) - value(base2)      (the window before that)
- `acceleration` = change - prev_change             (this week's change vs last
                   week's, spanning ACCELERATION_WINDOW_DAYS in total)

`base1` is the latest point in [as_of - 9d, as_of - 7d] and `base2` the latest
in [base1 - 9d, base1 - 7d] — the same 7-day window + 2-day tolerance as
`history.rank_change`. Narratives are then RANKED against each other on
`change` (descending competition rank); the absolute number is secondary.

Basis (disclosed per narrative in `momentum_basis`, never silently mixed):
1. `pytrends-blended` — the id-keyed RFC-3 blend, within-source normalised,
   when its ADR-1 sufficiency is `mature`. The keyword-keyed primary pytrends
   series is deliberately NOT used: its scale changed with RFC-3's batching.
2. `composite` — the narrative's ADR-1 composite, when it has at least
   `history.MATURE_POINTS_THRESHOLD` points (composite "mature").
3. `insufficient` — neither basis is mature, or neither has enough history to
   resolve both windows. Explicit state + reason; never a fabricated 0 trend.

A mature basis whose windows cannot be resolved falls through to the next
basis. Read-only: nothing here fetches a provider or writes the cache.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

import pandas as pd

from api.analytics.narrative import history, narrative_config, scoring

MOMENTUM_WINDOW_DAYS = history.CHANGE_WINDOW_DAYS  # 7, ADR-4
ACCELERATION_WINDOW_DAYS = 2 * MOMENTUM_WINDOW_DAYS  # 14: this week's change vs last week's
WINDOW_TOLERANCE_DAYS = history.CHANGE_BASELINE_TOLERANCE_DAYS  # baseline may sit 7..9 days back

BASIS_BLENDED = "pytrends-blended"
BASIS_COMPOSITE = "composite"
BASIS_INSUFFICIENT = "insufficient"
MomentumBasis = Literal["pytrends-blended", "composite", "insufficient"]

Direction = Literal["up", "down", "flat"]
Trend = Literal["accelerating", "decelerating", "steady"]

REASON_NO_MATURE_BASIS = "not enough history for momentum yet: no mature pytrends-blended or composite series"
REASON_WINDOWS_UNRESOLVED = (
    "not enough history for momentum yet: need points ~7 and ~14 days before the latest point")


@dataclass
class MomentumPoint:
    as_of: str
    value: float
    baseline_date: str
    baseline_value: float
    prior_baseline_date: str
    prior_baseline_value: float

    @property
    def change(self) -> float:
        return self.value - self.baseline_value

    @property
    def prev_change(self) -> float:
        return self.baseline_value - self.prior_baseline_value

    @property
    def acceleration(self) -> float:
        return self.change - self.prev_change


@dataclass
class MomentumEntry:
    category_id: str
    label: str
    momentum_basis: MomentumBasis
    rank: int | None
    as_of: str | None
    change: float | None
    prev_change: float | None
    acceleration: float | None
    direction: Direction | None
    trend: Trend | None
    baseline_date: str | None
    prior_baseline_date: str | None
    status: Literal["ok", "insufficient"]
    reason: str | None


@dataclass
class MomentumResult:
    generated_utc: str
    window_days: int
    acceleration_window_days: int
    tolerance_days: int
    entries: list[MomentumEntry]


# --- pure helpers ----------------------------------------------------------


def _latest_in_window(points: list[tuple[str, float]], anchor: str) -> tuple[str, float] | None:
    a = date.fromisoformat(anchor)
    lo = (a - timedelta(days=MOMENTUM_WINDOW_DAYS + WINDOW_TOLERANCE_DAYS)).isoformat()
    hi = (a - timedelta(days=MOMENTUM_WINDOW_DAYS)).isoformat()
    hits = [p for p in points if lo <= p[0] <= hi]
    return hits[-1] if hits else None


def momentum_from_points(points: list[tuple[str, float]]) -> MomentumPoint | None:
    """`points` = (iso date, value) with no nulls. Returns None when either
    window cannot be resolved (never a guessed or zero-filled value)."""
    pts = sorted(points)
    if not pts:
        return None
    as_of, value = pts[-1]
    base1 = _latest_in_window(pts, as_of)
    if base1 is None:
        return None
    base2 = _latest_in_window(pts, base1[0])
    if base2 is None:
        return None
    return MomentumPoint(as_of, value, base1[0], base1[1], base2[0], base2[1])


def _sign(x: float) -> int:
    # Rounded like history's ranks so float noise never reads as a trend.
    x = round(x, history.RANK_DECIMALS)
    return (x > 0) - (x < 0)


def classify(change: float, acceleration: float) -> tuple[Direction, Trend]:
    """Direction = sign(change). Trend = sign(change) x sign(acceleration):
    positive -> accelerating (moving faster in its own direction), negative ->
    decelerating, zero -> steady."""
    direction: Direction = {1: "up", -1: "down", 0: "flat"}[_sign(change)]
    product = _sign(change) * _sign(acceleration)
    trend: Trend = {1: "accelerating", -1: "decelerating", 0: "steady"}[product]
    return direction, trend


def _blended_points(series: list[history.SeriesData]) -> list[tuple[str, float]] | None:
    """Normalised blended points when the blended series is mature, else None."""
    blended = next((s for s in series if s.source == history.PYTRENDS_BLENDED_SOURCE), None)
    if blended is None or blended.sufficiency != scoring.SUFFICIENCY_MATURE or blended.frame.empty:
        return None
    return [(str(r.date), float(r.normalized)) for r in blended.frame.itertuples(index=False)
            if r.normalized is not None and not pd.isna(r.normalized)]


def _composite_points(composite: pd.DataFrame) -> list[tuple[str, float]] | None:
    if composite.empty or len(composite) < history.MATURE_POINTS_THRESHOLD:
        return None
    return [(str(r.date), float(r.value)) for r in composite.itertuples(index=False)]


def select_momentum(
    blended: list[tuple[str, float]] | None,
    composite: list[tuple[str, float]] | None,
) -> tuple[MomentumBasis, MomentumPoint | None, str | None]:
    """ADR-4 basis fallback. Inputs are None when that basis is not mature."""
    if blended is None and composite is None:
        return BASIS_INSUFFICIENT, None, REASON_NO_MATURE_BASIS
    for basis, pts in ((BASIS_BLENDED, blended), (BASIS_COMPOSITE, composite)):
        if pts is None:
            continue
        m = momentum_from_points(pts)
        if m is not None:
            return basis, m, None  # type: ignore[return-value]
    return BASIS_INSUFFICIENT, None, REASON_WINDOWS_UNRESOLVED


def rank_entries(entries: list[MomentumEntry]) -> list[MomentumEntry]:
    """Rank ok entries against each other on change; insufficient last, rank None."""
    ranks = history.competition_rank({e.category_id: e.change for e in entries
                                      if e.status == "ok" and e.change is not None})
    for e in entries:
        e.rank = ranks.get(e.category_id)
    return sorted(entries, key=lambda e: (e.rank is None, e.rank or 0, e.category_id))


# --- orchestrator ----------------------------------------------------------


def build_momentum(today: date | None = None) -> MomentumResult:
    """Read-only momentum for every enabled narrative in `narratives.json`."""
    now = datetime.now(timezone.utc)
    today = today or now.date()
    entries: list[MomentumEntry] = []
    for seed in narrative_config.load_narratives():
        cid = seed["id"]
        keywords = list(seed.get("keywords", []))
        series = history.load_category_series(cid, narrative_config.primary_keyword(seed), today, keywords)
        composite = history.build_composite(series)
        basis, m, reason = select_momentum(_blended_points(series), _composite_points(composite))
        label = seed.get("label", cid)
        if m is None:
            entries.append(MomentumEntry(cid, label, basis, None, None, None, None, None, None, None,
                                         None, None, "insufficient", reason))
            continue
        direction, trend = classify(m.change, m.acceleration)
        entries.append(MomentumEntry(
            cid, label, basis, None, m.as_of, m.change, m.prev_change, m.acceleration, direction, trend,
            m.baseline_date, m.prior_baseline_date, "ok", None))
    return MomentumResult(
        generated_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window_days=MOMENTUM_WINDOW_DAYS,
        acceleration_window_days=ACCELERATION_WINDOW_DAYS,
        tolerance_days=WINDOW_TOLERANCE_DAYS,
        entries=rank_entries(entries),
    )
