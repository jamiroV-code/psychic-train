"""Pydantic contracts for RFC-002 (Leg-backtest / Macro Liquidity), items 41/44.

`LegBoundary` (ADR-3): API responses always carry both
`candidate_boundaries` and `confirmed_boundaries` — an unconfirmed
candidate is never silently dropped once detected; `candidate_boundaries`
lists every detected candidate (its own `confirmed` flag says whether it
was later confirmed), `confirmed_boundaries` is the confirmed subset.

`CurrentLegState` (item 44) is the current leg read that backs
`GET /api/regime/legs`.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from api.models.screener import ChartBar

LiquidityCompositeVariant = Literal["reduced", "full"]


class LegBoundary(BaseModel):
    date: str  # ISO date (YYYY-MM-DD) the boundary candidate centers on
    z_score: float
    confirmed: bool
    confirmed_date: str | None = None  # ISO date the price-structure shift confirmed it, if any


class CurrentLegState(BaseModel):
    """The current leg read (item 44): candidate and confirmed boundaries
    plus the composite variant they were detected on.
    """

    candidate_boundaries: list[LegBoundary]
    confirmed_boundaries: list[LegBoundary]
    composite_variant: LiquidityCompositeVariant
    # True once a composite was actually built and detection ran for this
    # read: distinguishes "no leg data computed yet" from "computed,
    # currently showing zero boundaries" (ADR-3's "never collapses into
    # silence" — zero boundaries is a real, visible state, not a failure).
    has_data: bool


class LegBoundaryResponse(BaseModel):
    composite_variant: LiquidityCompositeVariant
    candidate_boundaries: list[LegBoundary]
    confirmed_boundaries: list[LegBoundary]


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


# --- T38 / S7: GET /api/regime/btc-legs (C7, C8, C9) ------------------------
#
# The BTC leg chart: every cached BTC `1d` bar, the confirmed boundaries, the
# legs between them, the current leg and the D-14 estimate. A leg runs from a
# confirmed boundary's `date` to the next one; the current leg runs to the
# last BTC bar. Timestamps are ISO UTC with a trailing `Z`; dates YYYY-MM-DD.
# The two estimate labels are closed enums and are never merged; a label is
# null only together with a `reason`.

AgeLabel = Literal["early", "mid", "late"]
CompositeChangeLabel = Literal["rising", "falling", "flat"]


class BtcLegBoundary(BaseModel):
    date: str
    z_score: float
    confirmed_date: str | None = None


class BtcLeg(BaseModel):
    start: str
    end: str | None = None  # null for the current leg
    days: int
    is_current: bool


class LatestCandidate(BaseModel):
    date: str
    z_score: float
    confirmed: bool


class CurrentLeg(BaseModel):
    start_date: str
    days_in_leg: int
    composite_value: float | None = None
    composite_as_of: str | None = None
    change_14d: float | None = None
    last_boundary_z: float
    latest_candidate: LatestCandidate | None = None
    composite_variant: LiquidityCompositeVariant


class AgeEstimate(BaseModel):
    label: AgeLabel | None = None
    age_days: int
    median_days: float | None = None
    ratio: float | None = None
    earlier_legs: int
    earlier_lengths_days: list[int]
    rule: str
    reason: str | None = None


class CompositeEstimate(BaseModel):
    label: CompositeChangeLabel | None = None
    change_14d: float | None = None
    threshold: float | None = None
    history_std: float | None = None
    n_changes: int
    composite_as_of: str | None = None
    rule: str
    reason: str | None = None


class LegEstimate(BaseModel):
    heading: str
    age: AgeEstimate
    composite: CompositeEstimate


class BtcLegChartResponse(BaseModel):
    available: bool
    reason: str | None = None
    server_time: str
    composite_variant: LiquidityCompositeVariant
    first_bar_ts: str | None = None
    last_bar_ts: str | None = None
    bar_count: int
    btc: list[ChartBar]
    boundaries: list[BtcLegBoundary]
    legs: list[BtcLeg]
    current_leg: CurrentLeg | None = None
    estimate: LegEstimate | None = None
