"""GET /api/onchain/growth and GET /api/onchain/chains (chain-growth RFC-4).

Thin HTTP wrapper; logic lives in `api/analytics/onchain/`. Read-only: serves
the nightly archive, never fetches a provider.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from api.analytics.onchain.response import build_chains_response, build_growth_response
from api.models.onchain_activity import OnchainChainsResponse, OnchainGrowthResponse

router = APIRouter(prefix="/api/onchain", tags=["onchain"])


@router.get("/growth", response_model=OnchainGrowthResponse)
def get_growth(
    metric: Literal["active_addresses", "transactions"] = Query("active_addresses"),
    start: date | None = Query(None, description="Comparison rebase date (ISO); default = latest date - 365 days"),
) -> OnchainGrowthResponse:
    if start is not None and start > datetime.now(timezone.utc).date():
        raise HTTPException(status_code=422, detail="start must not be in the future")
    return build_growth_response(metric, start)


@router.get("/chains", response_model=OnchainChainsResponse)
def get_chains() -> OnchainChainsResponse:
    return build_chains_response()
