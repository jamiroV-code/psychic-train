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


class DiscoveryHistoryDay(BaseModel):
    """One coin-day, computed from points dated on or before `date` only."""
    date: str
    score: float           # weighted mean of source changes over covered weight (raw, not winsorized)
    covered_weight: float
    rising_weight: float
    trigger: bool
    thin: bool             # covered_weight below the trigger floor (min_covered_weight)


class DiscoveryCategoryDay(BaseModel):
    """One category-day over the coins scorable that day."""
    date: str
    score: float           # mean of winsorized coin scores
    coins_used: int
    triggered_count: int
    triggered_share: float  # triggered_count / coins_used, 0..1


class DiscoveryHistoryBase(BaseModel):
    id: str
    window: Literal[7, 30, 90]
    as_of: str
    status: DiscoveryStatus
    reason: str
    min_history_days: int
    min_covered_weight: float   # trigger floor, so a chart can draw covered_weight against it


class DiscoveryCoinHistory(DiscoveryHistoryBase):
    kind: Literal["coin"] = "coin"
    history_days: dict[str, int]   # series name -> stored days dated on or before as_of
    days: list[DiscoveryHistoryDay]


class DiscoveryCategoryHistory(DiscoveryHistoryBase):
    kind: Literal["category"] = "category"
    history_days: dict[str, int] = {}
    days: list[DiscoveryCategoryDay]


class DiscoveryPriceDay(BaseModel):
    date: str              # UTC day of the daily bar
    close: float


class DiscoveryPrice(BaseModel):
    """Daily closes for the chart's price line, from the local 1d cache only (T104)."""
    symbol: str
    window: Literal[7, 30, 90]
    status: DiscoveryStatus
    last_date: str | None  # newest cached day on or before as_of, even when it is older than the window
    days: list[DiscoveryPriceDay]
