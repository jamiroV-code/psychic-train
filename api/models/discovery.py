"""S-F1 payload for GET /api/narrative/discovery."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

DiscoveryStatus = Literal["ok", "no-data"]


class DiscoverySource(BaseModel):
    source: str            # weighted source, or "coingecko" when it fed the exchange_activity slot
    change: float          # percent over the window
    as_of: str             # newest stored day the change is anchored to (ISO date)
    members: list["DiscoverySource"] = []   # exchange_activity only: one entry per exchange with data


class DiscoveryCoin(BaseModel):
    symbol: str
    change: float          # percent, winsorized at the category's 95th percentile
    raw_change: float      # percent, weighted mean over covered weight, as measured
    covered_weight: float  # points of the 100 that had usable data for this coin
    rising_weight: float   # points of covered_weight whose source change is at or above the threshold
    trigger: bool
    sources: list[DiscoverySource]


class DiscoveryCategory(BaseModel):
    id: str
    name: str
    score: float | None    # mean of winsorized coin changes
    median: float | None
    coins_used: int
    gaining_count: int     # coins with trigger true
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
