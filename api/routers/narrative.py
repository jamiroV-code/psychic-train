"""GET /api/narrative/categories (item 56).

Thin FastAPI wrapper — real orchestration lives in
`api/analytics/narrative/trigger.py::compute_narrative_categories`, and the
`TriggerResult` -> `NarrativeCategory` assembly (label/keywords/`seed`
lookup) lives in that same module's `assemble_narrative_categories` (moved
there at RFC-004 EXECUTE so `screener_board.py` can reuse it without a
non-router module calling into this router — see that function's docstring)
(Architecture Clarification: routers/ exposes HTTP only, no router calls a
provider directly; mirrors `routers/regime.py`'s role for
`leg_boundary.compute_current_leg_state`).
"""
from __future__ import annotations

from fastapi import APIRouter

from api.analytics.narrative import trigger
from api.models.narrative import NarrativeCategory

router = APIRouter(prefix="/api/narrative", tags=["narrative"])


@router.get("/categories", response_model=list[NarrativeCategory])
def get_categories() -> list[NarrativeCategory]:
    return trigger.assemble_narrative_categories()
