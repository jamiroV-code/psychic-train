"""GET /api/narrative/discovery: category momentum over the top-100 (S-F1). Store only."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from api.analytics.attention import discovery_history
from api.analytics.attention.discovery import build_discovery
from api.models.discovery import DiscoveryCategoryHistory, DiscoveryCoinHistory, DiscoveryResponse

WINDOWS = (7, 30, 90)

router = APIRouter(prefix="/api/narrative", tags=["discovery"])


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


@router.get("/discovery", response_model=DiscoveryResponse)
def get_discovery(window: int = Query(default=30)) -> DiscoveryResponse:
    if window not in WINDOWS:
        raise HTTPException(status_code=422, detail="window must be 7, 30 or 90")
    return build_discovery(window, today=utc_today())


@router.get("/discovery/history", response_model=DiscoveryCoinHistory | DiscoveryCategoryHistory)
def get_discovery_history(symbol: str | None = Query(default=None), category: str | None = Query(default=None),
                          window: int = Query(default=30)):
    """Point-in-time daily series for one coin (`symbol`) or one category aggregate (`category`)."""
    if window not in WINDOWS:
        raise HTTPException(status_code=422, detail="window must be 7, 30 or 90")
    if (symbol is None) == (category is None):
        raise HTTPException(status_code=422, detail="pass exactly one of symbol or category")
    try:
        if symbol is not None:
            return discovery_history.coin_history(symbol, window, today=utc_today())
        return discovery_history.category_history(category, window, today=utc_today())
    except discovery_history.UnknownSubject as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
