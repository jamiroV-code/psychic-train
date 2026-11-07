"""S-F1 payload for GET /api/narrative/discovery."""
from __future__ import annotations

from typing import Literal
from datetime import datetime
from uuid import UUID
import re

from pydantic import BaseModel, Field, field_validator, model_serializer

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
    reason: str            # closed list: universe_classes.REASONS (T223 adds watching, inactive, unclassified)
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


ProxyState = Literal["direct", "unknown", "healthy", "quarantined", "blocked"]
ProxyReason = Literal[
    "proxy_config", "proxy_private", "proxy_assignment", "proxy_policy", "proxy_address",
    "proxy_transport", "proxy_timeout", "proxy_redirect", "proxy_response", "proxy_exit",
    "proxy_region", "proxy_feed", "proxy_baseline", "proxy_budget", "proxy_quarantine",
    "proxy_revision", "proxy_lock",
]

# Finish plan 06-11-26 (S-StatusAPI): optional, allowlisted status fields. Every value is a closed code, a count,
# a UTC timestamp or a date; never free text, a URL, an address, a cookie, a token or a private path.
SAFE_CODE = re.compile(r"[a-z][a-z0-9_]{0,39}")


def _utc_timestamp(value):
    if value is not None:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("invalid UTC timestamp")
    return value


def _safe_code(value):
    if value is not None and SAFE_CODE.fullmatch(value) is None:
        raise ValueError("invalid code")
    return value


def _iso_day(value):
    if value is not None:
        from datetime import date
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("invalid day")
    return value


def _drop_none(row: dict, keys) -> dict:
    for key in keys:
        if row.get(key, 0) is None:
            row.pop(key)
    return row


class XAccountBehaviour(BaseModel):
    """B3 per-account behaviour (S-B3P producer); every field unknown (None) until the pool persists it."""
    quiet_until: str | None = None
    cooldown_until: str | None = None
    cooldown_reason: str | None = None
    warmup_stage: int | None = Field(default=None, ge=0)
    effective_cap: int | None = Field(default=None, ge=0)
    mixed_calls_today: int | None = Field(default=None, ge=0)

    check_times = field_validator("quiet_until", "cooldown_until")(classmethod(lambda cls, v: _utc_timestamp(v)))
    check_code = field_validator("cooldown_reason")(classmethod(lambda cls, v: _safe_code(v)))


class XAccountHarvest(BaseModel):
    """S-Cookie-X harvest outcome per account: a state code, a reason code and when; never a cookie."""
    state: Literal["none", "ok", "needs_owner", "refused", "failed", "unknown"] = "unknown"
    reason: str | None = None
    last_at: str | None = None

    check_code = field_validator("reason")(classmethod(lambda cls, v: _safe_code(v)))
    check_time = field_validator("last_at")(classmethod(lambda cls, v: _utc_timestamp(v)))


QueryIdState = Literal["ok", "candidate", "stale", "unknown", "blocked", "refused_by_policy"]


class DiscoveryQueryIdHealth(BaseModel):
    """X GraphQL query-id registry (S-XProto producer: `_pc_state/x_queryids.json`)."""
    mode: Literal["off", "sentinel", "auto"]
    state: QueryIdState = "unknown"
    active_source: Literal["pinned", "bundle", "mixed"] | None = None
    active_age_days: int | None = Field(default=None, ge=0)
    last_check: str | None = None

    check_time = field_validator("last_check")(classmethod(lambda cls, v: _utc_timestamp(v)))


RedditMethod = Literal["reddit_live_browser", "reddit_live_gql", "reddit_web", "reddit_stream"]
RedditMethodState = Literal["ok", "degraded", "needs_probe", "disabled", "blocked", "stale", "unknown"]


class DiscoveryRedditMethodHealth(BaseModel):
    """One Reddit method's own status row (separate method-health reader; methods never merge)."""
    method: RedditMethod
    label: str
    state: RedditMethodState = "unknown"
    reason: str | None = None
    last_settled_day: str | None = None
    lanes: dict[Literal["posts", "comments"], float] | None = None   # coverage share of the last close poll, 0..1
    comments_scope: Literal["threads_opened"] | None = None
    requests_today: int | None = Field(default=None, ge=0)
    cap: int | None = Field(default=None, ge=0)

    check_code = field_validator("reason")(classmethod(lambda cls, v: _safe_code(v)))
    check_day = field_validator("last_settled_day")(classmethod(lambda cls, v: _iso_day(v)))

    @field_validator("lanes")
    @classmethod
    def lane_share(cls, value):
        if value is not None and not all(0.0 <= v <= 1.0 for v in value.values()):
            raise ValueError("invalid lane coverage")
        return value


RedditAccountState = Literal["active", "resting", "paused", "locked", "unknown"]


class DiscoveryRedditAccountHealth(BaseModel):
    """One Reddit throwaway account (its OWN model; X states are not widened): opaque label only."""
    site: Literal["reddit"] = "reddit"
    label: str
    state: RedditAccountState = "unknown"
    reason: str | None = None
    reads_today: int | None = Field(default=None, ge=0)
    cap: int | None = Field(default=None, ge=0)
    rest_until: str | None = None
    ready: bool | None = None
    session_state: str | None = None
    session_checked_at: str | None = None
    proxy_state: ProxyState | None = None

    check_codes = field_validator("reason", "session_state")(classmethod(lambda cls, v: _safe_code(v)))
    check_times = field_validator("rest_until", "session_checked_at")(classmethod(lambda cls, v: _utc_timestamp(v)))

    @field_validator("label")
    @classmethod
    def opaque_label(cls, value):
        if re.fullmatch(r"[A-Za-z0-9_-]{1,32}", value) is None:
            raise ValueError("invalid label")
        return value


class DiscoveryRelayRefusal(BaseModel):
    host: str
    count: int = Field(ge=0)

    @field_validator("host")
    @classmethod
    def hostname(cls, value):
        if re.fullmatch(r"(?=.{1,253}$)[a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63})+", value) is None or value.replace(
                ".", "").isdigit():
            raise ValueError("invalid hostname")
        return value


class DiscoveryBrowserHealth(BaseModel):
    """Browser host (S-Relay producer: `_pc_state/browser_health.json`): bounded top refused hostnames only."""
    relay_refusals: list[DiscoveryRelayRefusal] = Field(default_factory=list, max_length=5)
    profile_state: Literal["ok", "missing", "policy_unsatisfied", "unknown"] = "unknown"


class DiscoveryReportCounts(BaseModel):
    eligible: int = Field(ge=0)
    stored: int = Field(ge=0)
    exact: int = Field(ge=0)
    estimated: int = Field(ge=0)
    missing: int = Field(ge=0)
    reasons: dict[str, int] = {}

    @field_validator("reasons")
    @classmethod
    def reason_codes(cls, value):
        if not all(SAFE_CODE.fullmatch(k) and v >= 0 for k, v in value.items()):
            raise ValueError("invalid reasons")
        return value


class DiscoveryDailyReportStatus(BaseModel):
    """Newest `_reports/daily_report_<D>.json` (S-Report producer); unreadable → counts unknown, never zero."""
    day: str
    revision: int | None = Field(default=None, ge=0)
    per_source_method: dict[str, DiscoveryReportCounts] | None = None   # "<source>/<method>" -> counts
    complete: bool | None = None   # True only when every eligible coin-day is stored (and eligible > 0)

    check_day = field_validator("day")(classmethod(lambda cls, v: _iso_day(v)))

    @field_validator("per_source_method")
    @classmethod
    def method_keys(cls, value):
        if value is not None and not all(re.fullmatch(r"[a-z_]{1,40}/[a-z_]{1,40}", k) for k in value):
            raise ValueError("invalid source/method key")
        return value


class DiscoveryDoctorStatus(BaseModel):
    """`_reports/doctor.json` (S-OpsDoctor producer): verdict and counts only, never check text."""
    state: Literal["PASS", "WARN", "FAIL", "UNKNOWN"] = "UNKNOWN"
    checked_at: str | None = None
    failures: int | None = Field(default=None, ge=0)
    warnings: int | None = Field(default=None, ge=0)

    check_time = field_validator("checked_at")(classmethod(lambda cls, v: _utc_timestamp(v)))


_X_FINISH_FIELDS = ("endpoint_state", "behaviour", "harvest", "ct0_rotations_seen")


class DiscoveryAccountHealth(BaseModel):
    """One X account of the pool (AC47, AC52): opaque label only, never a cookie, token or username."""
    label: str
    state: Literal["active", "locked", "inactive", "suspect"]
    reason: str | None = None
    last_used: str | None = None
    cookie_age_days: int | None = None   # None: never refreshed through `--refresh-cookies`
    reads_today: int | None = None  # unknown until accounting has begun; missing cap means unlimited
    cap: int | None = None
    rest_until: str | None = None
    ready: bool | None = None      # None: grandfathered/no ready gate
    parse_strikes: int | None = None
    parse_strike_last_at: str | None = None
    proxy_id: str | None = None
    proxy_state: ProxyState | None = None
    proxy_reason: ProxyReason | None = None
    proxy_checked_at: str | None = None
    proxy_quarantine_until: str | None = None
    region: str | None = None
    connection_style: Literal["plain", "curl"] | None = None
    identity_revision: str | None = None
    endpoint_state: Literal["ok", "restricted", "unknown"] | None = None   # S-XDrift per-account 404 isolation
    behaviour: XAccountBehaviour | None = None
    harvest: XAccountHarvest | None = None
    ct0_rotations_seen: int | None = Field(default=None, ge=0)

    @field_validator("proxy_id", "identity_revision")
    @classmethod
    def opaque_uuid(cls, value, info):
        if value is not None:
            parsed = UUID(value)
            if str(parsed) != value or (info.field_name == "identity_revision" and parsed.version != 4):
                raise ValueError("invalid opaque identifier")
        return value

    @field_validator("region")
    @classmethod
    def safe_region(cls, value):
        if value is not None and re.fullmatch(r"[A-Z]{2}(?:-[A-Z0-9]{1,3})?", value) is None:
            raise ValueError("invalid region code")
        return value

    @field_validator("proxy_checked_at", "proxy_quarantine_until")
    @classmethod
    def proxy_timestamp(cls, value):
        if value is not None:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
                raise ValueError("invalid UTC timestamp")
        return value

    @model_serializer(mode="wrap")
    def serialize_account(self, handler):
        row = handler(self)
        for key in ("reads_today", "cap", "rest_until", "ready", "parse_strikes", "parse_strike_last_at",
                    "proxy_id", "proxy_state", "proxy_reason", "proxy_checked_at", "proxy_quarantine_until",
                    "region", "connection_style", "identity_revision", *_X_FINISH_FIELDS):
            if row[key] is None:
                row.pop(key)
        return row


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
    accounts: list[DiscoveryAccountHealth | DiscoveryRedditAccountHealth] = []
    free_disk_bytes: int | None = None
    clock_sync_age_seconds: float | None = None  # no clock-sync evidence persisted by this worker
    queryids: DiscoveryQueryIdHealth | None = None             # X row only; omitted while off and never checked
    methods: list[DiscoveryRedditMethodHealth] | None = None   # Reddit row only; omitted while no live method/account

    @model_serializer(mode="wrap")
    def serialize_health(self, handler):
        return _drop_none(handler(self), ("queryids", "methods"))


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


class DiscoveryTrendsWatch(BaseModel):
    """A coin waking up in the daily Trends pulls (stage 2, D-30): shown on the Sources panel only, never scored."""
    symbol: str
    days_held: int         # consecutive quiet-then-surge days; at the 30-file cap the panel shows "30+"


CollectorState = Literal["running", "stopped", "never_started", "unknown"]
# Why the collector is in its state, a closed list ("" while running).
CollectorReason = Literal["", "stopped_cleanly", "heartbeat_stale", "process_gone", "no_heartbeat", "unreadable"]


class DiscoveryCollectorSource(BaseModel):
    """One PC stream in the collector box: the Sources health fields reused; None (unknown) without worker state."""
    id: str                 # Discovery source id: xsearch | reddit
    label: str
    has_state: bool         # False: the worker never wrote this source's state file
    last_unit_at: str | None = None
    paused: bool | None = None
    pause_reason: str | None = None
    pause_until: str | None = None
    stale: bool | None = None
    budget_used: int | None = None
    effective_budget: int | None = None
    sizing_day: str | None = None
    capacity_reads: int | None = None
    need_reads: int | None = None
    shortfall_reads: int | None = None
    backlog_reads: int | None = None
    methods: list[DiscoveryRedditMethodHealth] | None = None   # Reddit: per-method state, same reader as the row

    @model_serializer(mode="wrap")
    def serialize_source(self, handler):
        return _drop_none(handler(self), ("sizing_day", "capacity_reads", "need_reads", "shortfall_reads",
                                          "backlog_reads", "methods"))


class DiscoveryCollectorStatus(BaseModel):
    """The attention collector process (standalone-collector): read from its heartbeat file only, no network.
    running = heartbeat younger than 90 s and its process alive; stopped = stopped cleanly, stale or process gone;
    never_started = no heartbeat file; unknown = the file is unreadable."""
    state: CollectorState
    reason: CollectorReason = ""
    started_at: str | None = None
    last_beat: str | None = None
    age_s: float | None = None          # seconds since last_beat, computed by the API
    mode: Literal["standalone", "in_api"] | None = None
    version: str | None = None          # the commit the collector runs, when readable
    running_sources: list[str] = []     # streams the process runs (xsearch_web, reddit_web)
    sources: list[DiscoveryCollectorSource] = []
    daily_report: DiscoveryDailyReportStatus | None = None
    doctor: DiscoveryDoctorStatus | None = None
    browser: DiscoveryBrowserHealth | None = None

    @model_serializer(mode="wrap")
    def serialize_collector(self, handler):
        return _drop_none(handler(self), ("daily_report", "doctor", "browser"))


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
    trends_watch: list[DiscoveryTrendsWatch] | None = None  # additive (stage 2): waking-up watch list, not scored
    collector: DiscoveryCollectorStatus | None = None       # additive (standalone-collector): collector heartbeat


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


class OnboardingSource(BaseModel):
    state: Literal["name", "pending", "missing", "none"]
    value: str | None = None
    reason: str = ""


class OnboardingCoin(BaseModel):
    symbol: str
    state: Literal["watching", "member", "inactive"]
    days_in_top100: int
    coin_class: str = Field(alias="class")
    class_source: Literal["owner", "auto", "confirmed"]
    class_evidence: dict = {}
    sources: dict[str, OnboardingSource]
    pending: list[dict] = []
    proposal: list[dict] = []


class OnboardingResponse(BaseModel):
    mode: Literal["shadow", "enforce"]
    as_of: str | None = None
    status: Literal["ok", "no-ledger", "corrupt"]
    probation_days: int
    exit_band_rank: int
    exit_days: int
    coins: list[OnboardingCoin] = []
