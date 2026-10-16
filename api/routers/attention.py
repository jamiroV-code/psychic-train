"""GET /api/narrative/baskets/attention: coin and basket attention scores (S-C).

Store only: the handler reads parquet and config, never a provider.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from fastapi import APIRouter, HTTPException, Query

from api.analytics.attention.basket import build_attention
from api.data.layout import read_layout
from api.models.attention import AttentionResponse

WINDOWS = (7, 30, 90)

router = APIRouter(prefix="/api/narrative/baskets", tags=["baskets"])


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


@router.get("/attention", response_model=AttentionResponse)
def get_attention(window: int = Query(default=30)) -> AttentionResponse:
    if window not in WINDOWS:
        raise HTTPException(status_code=422, detail="window must be 7, 30 or 90")
    return build_attention(window, layout=read_layout("crypto"), today=utc_today())
