"""GET /api/narrative/discovery: category momentum over the top-100 (S-F1). Store only."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from api.analytics.attention.discovery import build_discovery
from api.models.discovery import DiscoveryResponse

WINDOWS = (7, 30, 90)

router = APIRouter(prefix="/api/narrative", tags=["discovery"])


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


@router.get("/discovery", response_model=DiscoveryResponse)
def get_discovery(window: int = Query(default=30)) -> DiscoveryResponse:
    if window not in WINDOWS:
        raise HTTPException(status_code=422, detail="window must be 7, 30 or 90")
    return build_discovery(window, today=utc_today())
