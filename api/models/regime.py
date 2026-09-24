"""Pydantic contracts for RFC-002 (Leg-backtest / Macro Liquidity), items 41/44.

`LegBoundary` (ADR-3): API responses always carry both
`candidate_boundaries` and `confirmed_boundaries` — an unconfirmed
candidate is never silently dropped once detected; `candidate_boundaries`
lists every detected candidate (its own `confirmed` flag says whether it
was later confirmed), `confirmed_boundaries` is the confirmed subset.

`CurrentLegState` is the REAL input type that replaces RFC-001's throwaway
`RegimeState` stub wholesale (item 44, `models/screener.py`'s own docstring
anticipates this swap) — `BenchmarkSelection`'s shape (models/screener.py,
Public Contracts) is unaffected by it.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

LiquidityCompositeVariant = Literal["reduced", "full"]


class LegBoundary(BaseModel):
    date: str  # ISO date (YYYY-MM-DD) the boundary candidate centers on
    z_score: float
    confirmed: bool
    confirmed_date: str | None = None  # ISO date the price-structure shift confirmed it, if any


class CurrentLegState(BaseModel):
    """Real input to `select_active_benchmark` (item 44) — replaces
    RFC-001's `RegimeState` stub wholesale, not extended in place.
    """

    candidate_boundaries: list[LegBoundary]
    confirmed_boundaries: list[LegBoundary]
    composite_variant: LiquidityCompositeVariant
    # True once a composite was actually built and detection ran for this
    # read; lets `derive_leg_context` (RFC-004, item 64a) distinguish "no
    # leg data computed yet" (ADR-4's `unavailable`) from "computed,
    # currently showing zero boundaries" (ADR-3's "never collapses into
    # silence" — zero boundaries is a real, visible state, not a failure).
    has_data: bool


class LegBoundaryResponse(BaseModel):
    composite_variant: LiquidityCompositeVariant
    candidate_boundaries: list[LegBoundary]
    confirmed_boundaries: list[LegBoundary]
    active_benchmark_reason: str


# --- RFC-004 (regime dashboard): GET /api/regime/components, plan §11 ------
#
# Additive. `status` gains `not_applicable` (RFC-004 decision 1): a component
# that cannot exist in the requested range, distinct from `unavailable`
# (source failed, nothing cached) and `no_data` (history shorter than the
# change window). Point lists never carry null/NaN/0 stand-ins — a date with
# no value is simply absent.

ComponentStatus = Literal["ok", "stale", "unavailable", "not_applicable", "no_data"]
PublishedStatus = Literal["ok", "unavailable"]


class ComponentPoint(BaseModel):
    date: str  # ISO date
    value: float  # impulse, in the component's unit
    raw: float  # underlying level
    contribution: float  # sign·tanh(impulse/scale), in [-1, 1]
    # True when the previous point of this series is more than the series'
    # `max_gap_days` calendar days earlier (RFC-005 decision 9). Computed on
    # the full series, so it survives start/end filtering. Charts must not
    # draw a line into a point with gap_before = true.
    gap_before: bool = False


class RegimeComponent(BaseModel):
    id: str
    label: str
    weight: float
    source: str
    transform: str
    frequency: str
    unit: str
    status: ComponentStatus
    reason: str | None = None
    notes: list[str]
    first_date: str | None = None
    last_date: str | None = None
    # Most recent fetch among this component's cached inputs (decision 2);
    # null only when nothing is cached.
    last_fetched_utc: str | None = None
    # Longest normal step between points (release cadence + holiday slack).
    max_gap_days: int
    points: list[ComponentPoint]


class ReproducedPoint(BaseModel):
    date: str
    value: float
    coverage: float
    gap_before: bool = False


class ReproducedComposite(BaseModel):
    label: str
    normalisation: str
    max_gap_days: int
    points: list[ReproducedPoint]


class PublishedPoint(BaseModel):
    date: str
    value: float
    regime_label: str | None = None  # only where LiqTide published one
    gap_before: bool = False


class PublishedComposite(BaseModel):
    label: str
    attribution: str
    status: PublishedStatus
    max_gap_days: int
    points: list[PublishedPoint]


class CompositeAgreement(BaseModel):
    overlap_days: int
    pearson_r: float | None = None
    mean_abs_diff: float | None = None
    full_coverage_days: int = 0
    full_coverage_mean_abs_diff: float | None = None


class RegimeComposite(BaseModel):
    reproduced: ReproducedComposite
    published: PublishedComposite
    agreement: CompositeAgreement


class RegimeComponentsResponse(BaseModel):
    generated_utc: str
    grid_dates: list[str]
    components: list[RegimeComponent]
    composite: RegimeComposite
