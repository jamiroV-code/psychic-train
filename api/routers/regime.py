"""GET /api/regime/legs (item 42) and GET /api/regime/components (regime
dashboard RFC-004, plan §11).

Thin FastAPI wrapper — real logic lives in
`api/analytics/regime/leg_boundary.py::compute_current_leg_state`
(Architecture Clarification: routers/ exposes HTTP only, no router calls a
provider directly).
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from api.analytics.regime import components, leg_boundary
from api.analytics.regime.components_response import serialize_components
from api.models.regime import LegBoundaryResponse, RegimeComponentsResponse

router = APIRouter(prefix="/api/regime", tags=["regime"])


@router.get("/legs", response_model=LegBoundaryResponse)
def get_legs() -> LegBoundaryResponse:
    state = leg_boundary.compute_current_leg_state()
    return LegBoundaryResponse(
        composite_variant=state.composite_variant,
        candidate_boundaries=state.candidate_boundaries,
        confirmed_boundaries=state.confirmed_boundaries,
    )


@router.get("/components", response_model=RegimeComponentsResponse)
def get_components(
    start: date | None = Query(None, description="ISO date, inclusive"),
    end: date | None = Query(None, description="ISO date, inclusive"),
) -> RegimeComponentsResponse:
    """Six components + reproduced/published composite. Reads FRED/DefiLlama
    through their cache-first adapters and LiqTide from its archive only —
    never `liqtide_adapter.fetch_latest` (VALIDATE P1). A failed source
    degrades only its own component's status; the endpoint still answers."""
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    return serialize_components(components.build_regime_components(), start, end)
