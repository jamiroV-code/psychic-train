"""Response models for /api/onchain/* (chain-growth RFC-4, ADR-7).

Reuses the regime dashboard's `grid_dates` / `gap_before` / `max_gap_days`
contract (`api/models/regime.py`).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Metric = Literal["active_addresses", "transactions"]
SeriesStatus = Literal["ok", "stale", "unavailable"]
FloorRampState = Literal["not-enough-history", "floor", "ramping", "declining", "neutral"]


class GrowthPoint(BaseModel):
    date: str
    value: float
    ema7: float | None = None  # null for pre-launch points
    ema28: float | None = None
    # True when the previous point is more than `max_gap_days` days earlier.
    gap_before: bool = False
    pre_launch: bool = False  # D2: shaded in the UI, excluded from analytics


class GrowthSeries(BaseModel):
    source: str
    method: str
    attribution: str
    redistributable: bool
    max_gap_days: int
    last_as_of_utc: str | None = None
    points: list[GrowthPoint]


class FloorRampEventModel(BaseModel):
    floor_date: str
    ramp_date: str


class FloorRamp(BaseModel):
    state: FloorRampState
    events: list[FloorRampEventModel]
    min_history_days: int
    history_days: int
    gate_met_on: str | None = None


class CrossCheck(BaseModel):
    """Display-only (verdict: L2BEAT is never a series, never redistributed)."""
    source: str
    redistributable: bool
    display_only: bool = True
    latest_common_date: str | None = None
    latest_divergence_pct: float | None = None
    median_abs_divergence_pct_90d: float | None = None


class ChainGrowth(BaseModel):
    id: str
    label: str
    launch_date: str | None
    limited_history: bool
    status: SeriesStatus
    unavailable_reason: str | None = None
    history_start_date: str | None = None  # first post-launch point (AC-8)
    series: GrowthSeries | None = None
    floor_ramp: FloorRamp | None = None
    cross_check: CrossCheck | None = None


class ComparisonSeriesModel(BaseModel):
    """No raw-value field by design (AC-13)."""
    chain_id: str
    rebase_date: str | None
    rebased_late: bool
    index_values: list[float | None]
    pct_above_low_values: list[float | None]


class Comparison(BaseModel):
    normalization_method: str
    alternative_method: str
    start_date: str
    log_scale_default: bool
    series: list[ComparisonSeriesModel]


class GrowthParams(BaseModel):
    ema_span: int
    ema_fast_span: int
    window_days: int
    recovery_pct: float
    sustain_days: int
    spacing_days: int
    floor_state_pct: float
    min_history_days: int
    stale_after_days: int


class OnchainGrowthResponse(BaseModel):
    generated_utc: str
    metric: Metric
    grid_dates: list[str]
    attribution: str
    params: GrowthParams
    chains: list[ChainGrowth]
    comparison: Comparison


class ChainMetricInfo(BaseModel):
    metric: str
    source: str
    unavailable_reason: str | None = None


class ChainInfo(BaseModel):
    id: str
    label: str
    enabled: bool
    launch_date: str | None
    limited_history: bool
    metrics: list[ChainMetricInfo]
    cross_check_source: str | None = None


class OnchainChainsResponse(BaseModel):
    chains: list[ChainInfo]
