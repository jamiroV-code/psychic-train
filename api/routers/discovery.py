"""GET /api/narrative/discovery: category momentum over the top-100 (S-F1). Store only."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from api.analytics.attention import discovery_history, sources
from api.analytics.attention.discovery import build_discovery
from api.data import cache
from api.models.discovery import (DiscoveryCategoryHistory, DiscoveryCoinHistory, DiscoveryPrice,
                                  DiscoveryPriceDay, DiscoveryResponse, DiscoverySourcesResponse, OnboardingResponse)

WINDOWS = (7, 30, 90)

router = APIRouter(prefix="/api/narrative", tags=["discovery"])


@router.get("/onboarding", response_model=OnboardingResponse)
def get_onboarding() -> OnboardingResponse:
    from api.analytics.attention import onboarding
    return onboarding.build()


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


@router.get("/discovery", response_model=DiscoveryResponse)
def get_discovery(window: int = Query(default=30)) -> DiscoveryResponse:
    if window not in WINDOWS:
        raise HTTPException(status_code=422, detail="window must be 7, 30 or 90")
    return build_discovery(window, today=utc_today())


@router.get("/sources", response_model=DiscoverySourcesResponse)
def get_sources() -> DiscoverySourcesResponse:
    """What each Discovery input has stored today. Files and config only; no provider is called."""
    return sources.build_sources(utc_today())


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


@router.get("/discovery/price", response_model=DiscoveryPrice)
def get_discovery_price(symbol: str = Query(pattern=r"^[A-Za-z0-9]{1,24}$"), window: int = Query(default=30)) -> DiscoveryPrice:
    """Daily closes for the history chart's window, read from the local 1d cache (no network).

    The window matches `/discovery/history`: the `window` days ending yesterday (UTC). Bars after that day
    are never returned. Missing or non-positive closes are dropped, never filled.
    """
    if window not in WINDOWS:
        raise HTTPException(status_code=422, detail="window must be 7, 30 or 90")
    sym = symbol.upper()
    end = utc_today() - timedelta(days=1)
    start = end - timedelta(days=window - 1)
    frame = cache.read_ohlcv(sym, "1d")
    rows: list[tuple[date, float]] = []
    for ts, close in zip(frame["timestamp"], frame["close"]):
        day = ts.date()
        if day <= end and close is not None and math.isfinite(float(close)) and float(close) > 0:
            rows.append((day, float(close)))
    days = [DiscoveryPriceDay(date=d.isoformat(), close=c) for d, c in rows if d >= start]
    return DiscoveryPrice(symbol=sym, window=window, status="ok" if days else "no-data",
                          last_date=rows[-1][0].isoformat() if rows else None, days=days)
