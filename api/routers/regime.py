"""GET /api/regime/legs (item 42).

Thin FastAPI wrapper — real logic lives in
`api/analytics/regime/leg_boundary.py::compute_current_leg_state` and
`api/analytics/regime/benchmark.py::select_active_benchmark` (Architecture
Clarification: routers/ exposes HTTP only, no router calls a provider
directly).
"""
from __future__ import annotations

from fastapi import APIRouter

from api.analytics.regime import leg_boundary
from api.analytics.regime.benchmark import select_active_benchmark
from api.models.regime import LegBoundaryResponse

router = APIRouter(prefix="/api/regime", tags=["regime"])


@router.get("/legs", response_model=LegBoundaryResponse)
def get_legs() -> LegBoundaryResponse:
    state = leg_boundary.compute_current_leg_state()
    benchmark = select_active_benchmark(state)
    return LegBoundaryResponse(
        composite_variant=state.composite_variant,
        candidate_boundaries=state.candidate_boundaries,
        confirmed_boundaries=state.confirmed_boundaries,
        active_benchmark_reason=benchmark.reason,
    )
