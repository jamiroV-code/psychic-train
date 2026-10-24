"""S-C payload for GET /api/narrative/baskets/attention."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SourceState = Literal["ok", "unavailable", "insufficient-history", "no-article", "capped", "not-probed"]
BasketStatus = Literal["ok", "no-data", "empty"]


class SourceDetail(BaseModel):
    source: str
    raw: float | None
    ratio: float | None
    rank: float | None
    state: SourceState


class CoinAttention(BaseModel):
    symbol: str
    score: float | None
    sources_used: int
    sources_total: int
    sources: list[SourceDetail]


class SeriesPoint(BaseModel):
    date: str
    value: float | None


class BasketAttention(BaseModel):
    id: str
    name: str
    score: float | None
    change: float | None
    breadth: float | None
    coverage: str
    series: list[SeriesPoint]
    coins: list[CoinAttention]
    status: BasketStatus
    reason: str
    universe_size: int


class AttentionResponse(BaseModel):
    window: Literal[7, 30, 90]
    as_of: str
    membership_as_of: str
    baskets: list[BasketAttention]
