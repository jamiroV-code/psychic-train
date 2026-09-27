"""Pydantic contracts for the pair screener (cointegration-screener RFC-003, plan §11).

Two levels of status, never merged:
- per-pair `status` (ADR-7): ok | insufficient_overlap | coin_unavailable;
- response-level `computation_status` (ADR-8 Amendment): whether the
  precomputed results still match the current universe, price cache and
  statistics configuration. `stale_reason` explains every non-fresh state
  (Stage 0 D-3) and is null iff fresh.

No field is ever NaN or a 0 stand-in: a value that does not exist is null,
with a reason alongside it.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

PairStatus = Literal["ok", "insufficient_overlap", "coin_unavailable"]
ComputationStatus = Literal["fresh", "stale", "results_unavailable"]
HalfLifeState = Literal["computed", "not_mean_reverting"]
DiagnosticScope = Literal["whole_history_in_sample"]

DIAGNOSTIC_DISCLOSURE = (
    "These statistics use each pair's entire shared price history at once (in-sample). "
    "They describe how the two coins moved together in the past. They are not a trading "
    "signal, and they do not show whether the relationship still holds today."
)


class HalfLifeOut(BaseModel):
    state: HalfLifeState
    days: float | None  # None iff state == "not_mean_reverting"


class JohansenOut(BaseModel):
    trace_stat: float
    crit_value_95: float
    rank_at_least_1: bool


class EGDirectionOut(BaseModel):
    dependent: str
    independent: str
    hedge_ratio: float
    intercept: float
    t_stat: float
    p_value: float


class SpreadPoint(BaseModel):
    date: str  # ISO date
    spread: float
    z_score: float


class PairSummary(BaseModel):
    coin_a: str
    coin_b: str
    status: PairStatus
    reason: str | None
    overlap_days: int | None
    sample_start: str | None
    sample_end: str | None
    eg_p_raw: float | None
    eg_p_bh: float | None
    eg_direction: str | None  # "{dependent}~{independent}" of the lower-p direction
    eg_p_other_direction: float | None
    johansen: JohansenOut | None
    johansen_reason: str | None  # set iff ok and Johansen refused (D2); pair stays ok
    half_life: HalfLifeOut | None
    z_score: float | None


class PairDetail(PairSummary):
    eg_a_on_b: EGDirectionOut | None
    eg_b_on_a: EGDirectionOut | None
    spread_direction: str | None
    half_life_ar1_beta: float | None
    spread: list[SpreadPoint]  # [] iff status != ok


class _Envelope(BaseModel):
    generated_utc: str
    computed_at: str | None
    computation_status: ComputationStatus
    stale_reason: str | None
    diagnostic_scope: DiagnosticScope = "whole_history_in_sample"
    diagnostic_disclosure: str = DIAGNOSTIC_DISCLOSURE


class PairsResponse(_Envelope):
    universe_size: int
    pair_count: int
    min_overlap_days: int
    pairs: list[PairSummary]


class PairDetailResponse(_Envelope):
    pair: PairDetail | None
