"""Pydantic contracts for RFC-003 (Narrative / Mindshare), items 54/56.

`NarrativeCategory` (ADR-3): API responses always carry every triggered
category regardless of `confirmed` — a triggered-but-unconfirmed category
is never hidden, only carries a lower `trust_weight` (see Public
Contracts, `GET /api/narrative/categories`).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SourceAvailability = Literal["ok", "unavailable", "stale", "presumed-dead"]


class NarrativeTriggerState(BaseModel):
    """Internal trigger-computation result for one category (items 51/52)
    — the pre-response shape `trigger.compute_trigger`/`apply_confirmation`
    produce; `routers/narrative.py` assembles this into the public
    `NarrativeCategory` response shape below.
    """

    category_id: str
    triggered: bool
    confirmed: bool
    trust_weight: float
    trigger_date: str | None = None
    confirmed_date: str | None = None
    source_availability: dict[str, SourceAvailability]


class NarrativeCategory(BaseModel):
    id: str
    label: str
    keywords: list[str]
    seed: bool  # True = curated narrative_categories.json seed list; False = auto-flagged emerging
    triggered: bool
    confirmed: bool
    trust_weight: float
    source_availability: dict[str, SourceAvailability]


# --- Narrative dashboard RFC-3: GET /api/narrative/history (ADR-4) ---------
#
# Separate model set from `NarrativeCategory` above: nothing here is used by
# `GET /api/narrative/categories`, so that endpoint's shape cannot drift.

HistorySource = Literal[
    "pytrends", "reddit", "coingecko", "coingecko-narrative",
    "exchange_volume_share", "exchange_new_listings",
    "pytrends-blended",  # narrative-v2 RFC-3: id-keyed multi-keyword blend
]
SeriesStatus = Literal["ok", "stale", "unavailable", "presumed-dead"]
EntryStatus = Literal["ok", "unavailable"]


class NarrativeHistoryPoint(BaseModel):
    date: str
    raw_value: float | None
    normalized_value: float | None  # null only when raw_value is null
    point_status: str | None  # stored source_status / volume_status / listing_status
    reason: str | None = None
    gap_before: bool
    # Narrative-v2 ADR-1: the owning series' data sufficiency. "insufficient"
    # (< history.MIN_SUFFICIENT_POINTS real points) => normalized_value is null
    # and the series never feeds the composite; "provisional" is thin history
    # (< history.MATURE_POINTS_THRESHOLD); "mature" otherwise.
    sufficiency: Literal["insufficient", "provisional", "mature"]


class NarrativeHistorySeries(BaseModel):
    source: HistorySource
    label: str
    variant: Literal["nightly-7d", "backfill-269d"] | None = None  # pytrends only
    cache_key: str
    redistributable: bool
    status: SeriesStatus
    reason: str | None
    first_date: str | None
    last_date: str | None
    max_gap_days: int
    in_composite: bool
    points: list[NarrativeHistoryPoint]


class NarrativeCoin(BaseModel):
    symbol: str
    narrative_only: bool  # mapped only in the curated map, not the frozen legacy map


class NarrativeCompositePoint(BaseModel):
    date: str
    value: float
    coverage: float  # sources present / composite source slots
    sources_present: list[str]
    trust_weight: float
    mixed_scale: bool  # uses backfilled (269-day window) pytrends
    gap_before: bool


class NarrativeComposite(BaseModel):
    status: EntryStatus
    reason: str | None
    sources: list[str]  # composite source slots (coverage denominator)
    min_sources: int
    max_gap_days: int
    points: list[NarrativeCompositePoint]


class NarrativeHistoryCategory(BaseModel):
    category_id: str
    label: str
    keywords: list[str]
    coins: list[NarrativeCoin]
    series: list[NarrativeHistorySeries]
    composite: NarrativeComposite


class NarrativeComparisonEntry(BaseModel):
    category_id: str
    rank: int | None
    value: float | None
    mixed_scale: bool
    status: EntryStatus
    reason: str | None


class NarrativeComparison(BaseModel):
    as_of: str | None
    entries: list[NarrativeComparisonEntry]


class NarrativeChangeEntry(BaseModel):
    category_id: str
    delta: float | None
    rank: int | None
    baseline_date: str | None
    mixed_scale: bool
    status: EntryStatus
    reason: str | None


class NarrativeChange(BaseModel):
    window_days: int
    baseline_tolerance_days: int
    as_of: str | None
    entries: list[NarrativeChangeEntry]


class NarrativeHistoryResponse(BaseModel):
    generated_utc: str
    redistributable_all: bool
    grid_dates: list[str]
    categories: list[NarrativeHistoryCategory]
    comparison: NarrativeComparison
    change_in_attention: NarrativeChange


# --- Narrative-v2 RFC-4 (ADR-4): GET /api/narrative/momentum. Additive only;
# no existing model above is changed.


class NarrativeMomentumEntry(BaseModel):
    category_id: str
    label: str
    momentum_basis: Literal["pytrends-blended", "composite", "insufficient"]
    rank: int | None  # vs-the-field rank on `change`; None when insufficient
    as_of: str | None
    change: float | None
    prev_change: float | None
    acceleration: float | None
    direction: Literal["up", "down", "flat"] | None
    trend: Literal["accelerating", "decelerating", "steady"] | None
    baseline_date: str | None
    prior_baseline_date: str | None
    status: Literal["ok", "insufficient"]
    reason: str | None


class NarrativeMomentumResponse(BaseModel):
    generated_utc: str
    window_days: int
    acceleration_window_days: int
    tolerance_days: int
    entries: list[NarrativeMomentumEntry]
