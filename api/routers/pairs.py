"""GET /api/pairs and GET /api/pairs/{a}/{b} (cointegration-screener RFC-003, plan §11).

Thin wrapper over `pairs_response.py`'s READ path: persisted-file reads plus
the staleness check. Never computes statistics on request (ADR-8 Amendment).

Path params: uppercased; self-pair -> 422 (checked first); malformed -> 422;
not in the universe -> 404. An unreadable universe file is a configuration
error -> 500 with the loader's message (Stage 0 D-6).
"""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from api.analytics.cointegration import pairs_response
from api.data.pairs_universe import UniverseFileError, load_universe
from api.models.pairs import PairDetailResponse, PairsResponse

router = APIRouter(prefix="/api/pairs", tags=["pairs"])

_TICKER = re.compile(r"^[A-Z0-9]{1,15}$")


@router.get("", response_model=PairsResponse)
def get_pairs() -> PairsResponse:
    try:
        return pairs_response.read_table()
    except UniverseFileError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{a}/{b}", response_model=PairDetailResponse)
def get_pair(a: str, b: str) -> PairDetailResponse:
    a, b = a.strip().upper(), b.strip().upper()
    if a == b:
        raise HTTPException(status_code=422, detail="a and b must be different coins")
    for t in (a, b):
        if not _TICKER.match(t):
            raise HTTPException(status_code=422, detail=f"malformed ticker: {t!r}")
    try:
        universe = set(load_universe())
    except UniverseFileError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    for t in (a, b):
        if t not in universe:
            raise HTTPException(status_code=404, detail=f"{t} is not in the pair-screener universe")
    try:
        return pairs_response.read_detail(a, b)
    except UniverseFileError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
