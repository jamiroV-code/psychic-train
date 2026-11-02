"""GET /api/symbols/suggest: symbol and name suggestions for the add boxes. Reads the prebuilt index only."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from api.data import symbol_index

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.get("/suggest")
def suggest(kind: Literal["coin", "ticker"] = Query(...), q: str = Query(default="", max_length=40),
            limit: int = Query(default=8, ge=1, le=25)) -> dict:
    return symbol_index.suggest(kind, q, limit)
