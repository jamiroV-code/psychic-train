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
