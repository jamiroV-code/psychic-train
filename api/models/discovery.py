"""S-F1 payload for GET /api/narrative/discovery."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

DiscoveryStatus = Literal["ok", "no-data"]


class DiscoveryCoin(BaseModel):
    symbol: str
    change: float          # percent, winsorized at the category's 95th percentile
    raw_change: float      # percent, as measured
    gaining: bool
    sources_used: int
    sources_gaining: int


class DiscoveryCategory(BaseModel):
    id: str
    name: str
    score: float | None    # mean of winsorized coin changes
    median: float | None
    coins_used: int
    gaining_count: int
    coins: list[DiscoveryCoin]


class DiscoveryResponse(BaseModel):
    window: Literal[7, 30, 90]
    as_of: str
    categories_as_of: str
    status: DiscoveryStatus
    reason: str
    universe_size: int
    eligible_size: int
    categories: list[DiscoveryCategory]
