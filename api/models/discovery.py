"""S-F1 payload for GET /api/narrative/discovery."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_serializer

DiscoveryStatus = Literal["ok", "no-data"]


class DiscoverySource(BaseModel):
    source: str            # weighted source, or "coingecko" when it fed the exchange_activity slot
    change: float          # percent over the window
    as_of: str             # newest stored day the change is anchored to (ISO date)
    members: list["DiscoverySource"] = []   # exchange_activity only: one entry per exchange with data
    coverage_only: bool = False   # CoinGecko volume fallback under T204: counts toward coverage, never rising


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
    tradeability: Literal["tradeable", "unverified"] = "unverified"   # unverified = tradeability unknown: no fresh
    # venue list has the coin and not every tracked list is loaded (never excludes)


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
    exclusion_list: int = 0       # stablecoin + wrapped-staked + commodity-backed + no-market + not-tradeable-*
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


class DiscoveryVenueList(BaseModel):
    """One tracked venue's stored market list as Discovery used it (T189)."""
    venue: str             # binance | hyperliquid
    status: Literal["ok", "missing", "failed", "stale"]   # only ok proves or rules out a market
    as_of: str | None = None


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
    tradeability_unknown: int = 0                      # shown coins with tradeability "unverified"
    venue_lists: list[DiscoveryVenueList] = []         # per tracked venue: the list state behind tradeability
    tradeability_data_suspect: bool = False            # no-market rule hit > 25% of checked coins: it cut none
    min_category_coins: int = 3          # value of universe_rules.min_narrative_coins (name kept for the web)
    rising_threshold_pct: float = 10.0
    min_covered_weight: float = 30.0
    categories: list[DiscoveryCategory]  # the narratives; `categories_as_of` is the narratives file `as_of`
    narratives_status: Literal["proposed", "reviewed"] = "proposed"
    unassigned: list[str] = []           # universe coins in no narrative
    hidden_narratives: list[DiscoveryHiddenNarrative] = []
    weights_version: int = 1             # weights version scoring `as_of` (T130); additive


SourceState = Literal["ok", "insufficient-history", "unavailable", "not-probed", "off"]
# Why a Sources row is not `ok` (W8f), a closed list beside the free-text note; "" when ok.
SourceReason = Literal["", "parked", "x_live_off", "not_probed", "stale", "insufficient_history",
                       "no_stored_data", "invalid_file"]


class DiscoveryAccountHealth(BaseModel):
    """One X account of the pool (AC47, AC52): opaque label only, never a cookie, token or username."""
    label: str
    state: Literal["active", "locked", "inactive", "suspect"]
    reason: str | None = None
    last_used: str | None = None
    cookie_age_days: int | None = None   # None: never refreshed through `--refresh-cookies`


class DiscoverySourceHealth(BaseModel):
    """W8e2 health line (AC38, AC39): read from the worker's state and evidence files only."""
    last_unit_at: str | None = None
    paused: bool = False
    pause_reason: str | None = None
    pause_until: str | None = None  # None while paused: owner action needed or state unreadable
    collection_day: str
    attempted: int | None = None   # distinct coin-days attempted on collection_day; excludes canaries
    fetched: int | None = None     # those coin-days successfully stored
    completeness_day: str
    completeness_attempted: int | None = None
    completeness_fetched: int | None = None
    missing: int | None = None
    missing_reasons: dict[str, int] | None = None
    capped: int | None = None
    newest_age_hours: float | None = None  # age of newest collection, not the target day
    budget_used: int | None = None  # today's count (X: posts loaded; Reddit: requests), includes canaries
    effective_budget: int | None = None
    budget_spent: bool | None = None
    mode: Literal["baseline", "degraded"] | None = None
    expected_gap_s: float | None = None  # worker's persisted upper interval; unknown for older state
    stale: bool | None = None       # no unit for > 2 x expected gap, counted from the end of a by-design wait
                                    # (budget spent: next UTC day; timed pause: pause_until); unknown without timing
    completeness: str
    accounts_active: int | None = None
    accounts_total: int | None = None
    accounts: list[DiscoveryAccountHealth] = []
    free_disk_bytes: int | None = None
    clock_sync_age_seconds: float | None = None  # no clock-sync evidence persisted by this worker


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
    reason: SourceReason = ""
    impl: str | None = None   # weighted sources: the store (method) the row reports, from `source_impl`
    health: DiscoverySourceHealth | None = None   # W8e2: PC worker sources only, None without worker state

    @model_serializer(mode="wrap")
    def serialize_row(self, handler):
        """Keep the pre-worker wire shape exactly when there is no worker state."""
        row = handler(self)
        if self.health is None:
            row.pop("health", None)
        return row


class DiscoveryKeywordGap(BaseModel):
    """An eligible coin the daily Trends pull skips (T180): it gets no Trends data, never a 0."""
    symbol: str
    reason: Literal["no-trends-keyword"] = "no-trends-keyword"
    detail: str            # trends_keywords.MISSING_STATUSES: no-entry, no-keyword, skipped-unqualified, bad-file


class DiscoveryTrendsKeyword(BaseModel):
    """Google Trends keyword coverage over the eligible coins (T180)."""
    eligible_size: int
    with_keyword: int      # eligible coins with a topic or a pullable term
    missing: list[DiscoveryKeywordGap] = []


class DiscoverySourcesResponse(BaseModel):
    as_of: str
    universe_size: int
    eligible_size: int
    live_sources: int      # weighted sources in state ok
    total_sources: int     # weighted sources configured
    live_weight: float     # points of 100 whose source is ok
    newest: str | None     # newest stored date over live sources
    sources: list[DiscoverySourceRow]
    trends_keyword: DiscoveryTrendsKeyword | None = None   # additive (T180)


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
