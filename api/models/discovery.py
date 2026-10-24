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
    covered_weight: float  # weight points that had usable data for this coin (weights need not sum to 100)
    rising_weight: float   # points of covered_weight that are rising; a source group votes its weight once
    trigger: bool
    sources: list[DiscoverySource]
    primary: bool = False  # this category is the coin's primary narrative
    volume_24h: float | None = None   # snapshot 24h volume (USD); never excludes
    thin_volume: bool = False         # volume under universe_rules.thin_volume_label_below_usd: a label only
    tradeability: Literal["tradeable", "unverified"] = "unverified"   # unverified = a venue list is unknown


class DiscoveryCategory(BaseModel):
    id: str
    name: str
    score: float | None    # mean of winsorized coin changes
    median: float | None
    coins_used: int
    gaining_count: int     # coins with trigger true
    ranked: bool = True    # False when fewer than `min_category_coins` coins had data: score kept, not ranked
    coins: list[DiscoveryCoin]


class DiscoveryExcluded(BaseModel):
    """Legacy (deprecated, kept for the old web; U2): `excluded_counts` folded into the old four keys.
    They add up to universe - shown."""
    exclusion_list: int = 0       # stablecoin + wrapped-staked + no-market + not-tradeable-config
    below_volume_floor: int = 0   # always 0: there is no volume cut
    no_category: int = 0          # unassigned + hidden-narrative
    no_source_data: int = 0       # in a visible narrative but no source has usable data


class DiscoveryExcludedCoin(BaseModel):
    symbol: str
    reason: str            # closed list: universe_classes.REASONS
    detail: str = ""


class DiscoveryHiddenNarrative(BaseModel):
    """A narrative with fewer than `min_category_coins` member coins in the universe: listed, not scored."""
    id: str
    name: str
    coins: list[str]       # its in-universe members


class DiscoveryResponse(BaseModel):
    window: Literal[7, 30, 90]
    as_of: str
    categories_as_of: str
    status: DiscoveryStatus
    reason: str
    universe_size: int
    eligible_size: int
    shown_size: int = 0                  # distinct coins listed in any category
    excluded: DiscoveryExcluded = DiscoveryExcluded()
    excluded_coins: list[DiscoveryExcludedCoin] = []   # every universe coin not shown, with its reason
    excluded_counts: dict[str, int] = {}               # reason -> count; shown_size + sum = universe_size
    min_category_coins: int = 3          # value of universe_rules.min_narrative_coins (name kept for the web)
    rising_threshold_pct: float = 10.0
    min_covered_weight: float = 30.0
    categories: list[DiscoveryCategory]  # the narratives; `categories_as_of` is the narratives file `as_of`
    narratives_status: Literal["proposed", "reviewed"] = "proposed"
    unassigned: list[str] = []           # universe coins in no narrative
    hidden_narratives: list[DiscoveryHiddenNarrative] = []
    weights_version: int = 1             # weights version scoring `as_of` (T130); additive


SourceState = Literal["ok", "insufficient-history", "unavailable", "not-probed", "off"]


class DiscoverySourceRow(BaseModel):
    """One line of GET /api/narrative/sources."""
    id: str
    label: str
    kind: Literal["weighted", "exchange-member", "fallback", "helper"]
    weight: float | None   # points of 100; sub-weight for an exchange member; None when it carries none
    state: SourceState
    newest: str | None     # newest stored date (ISO)
    history_days: int      # max stored days over coins
    coins_with_data: int   # eligible coins whose series is usable (>= the history gate)
    eligible_size: int
    note: str = ""


class DiscoverySourcesResponse(BaseModel):
    as_of: str
    universe_size: int
    eligible_size: int
    live_sources: int      # weighted sources in state ok
    total_sources: int     # weighted sources configured
    live_weight: float     # points of 100 whose source is ok
    newest: str | None     # newest stored date over live sources
    sources: list[DiscoverySourceRow]


class DiscoveryHistoryDay(BaseModel):
    """One coin-day, computed from points dated on or before `date` only."""
    date: str
    score: float           # weighted mean of source changes over covered weight (raw, not winsorized)
    covered_weight: float
    rising_weight: float
    trigger: bool
    thin: bool             # covered_weight below the trigger floor (min_covered_weight)
    weights_version: int = 1   # weights version that scored this day (T130); a day keeps its version


class DiscoveryCategoryDay(BaseModel):
    """One category-day over the coins scorable that day."""
    date: str
    score: float           # mean of winsorized coin scores
    coins_used: int
    triggered_count: int
    triggered_share: float  # triggered_count / coins_used, 0..1
    weights_version: int = 1   # weights version that scored this day (T130)


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
    membership_as_of: str = ""     # narratives file `as_of`: the membership used for EVERY day of the chart
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
