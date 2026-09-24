"""Exchange (Hyperliquid) attention proxy: per-category volume share and
new-listing counts. Narrative dashboard RFC-2, ADR-6.

DISPLAY-ONLY. Nothing here is imported by `trigger.py`, `screener_board.py`
or the `/categories` router; it feeds `/history` only.

Formulas (Stage 0 decisions D1/D3, 2026-09-24):
- volume share(cat) = Σ 24h quote volume of active non-HIP-3 perps resolved
  to coins mapped to `cat` ÷ Σ 24h quote volume of ALL active non-HIP-3 perps.
  Perps not claimed by any map coin go to the explicit "unmapped" bucket,
  which is in the denominator, so shares sum to 1.
- new listings = perp names in today's snapshot absent from the latest
  snapshot strictly before today (`baseline_date` records which one). No
  earlier snapshot → `new_listing_count=None`, status "unavailable", reason
  "no-baseline-yet" (E2) — never 0.

Coin symbols come from `mapping.load_category_map()` on every run (the map is
user-editable), never a hard-coded list. Symbol resolution: active perp with
`base == SYM`, else `baseName == "k" + SYM` (Hyperliquid thousand-unit
contracts; ccxt upper-cases their base to e.g. "KPEPE", so `baseName` is the
only place the `k` survives). A map coin with no market is reported per coin
as "no-hyperliquid-market", never silently dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from api.analytics.narrative import mapping
from api.data import cache, hyperliquid_narrative_adapter as hl

UNMAPPED = "unmapped"
NO_MARKET = "no-hyperliquid-market"
NO_BASELINE = "no-baseline-yet"


@dataclass
class CoinResolution:
    symbol: str
    category_id: str
    market: str | None  # Hyperliquid raw name, e.g. "kPEPE"
    status: str  # "ok" | "unavailable"
    reason: str | None = None


@dataclass
class CategoryAttention:
    category_id: str
    volume_share: float | None
    volume_status: str
    volume_reason: str | None
    new_listing_count: int | None
    listing_status: str
    listing_reason: str | None
    baseline_date: str | None
    new_listings: list[str] = field(default_factory=list)

    def as_row(self, date: str) -> dict:
        return {
            "date": date,
            "volume_share": self.volume_share,
            "volume_status": self.volume_status,
            "volume_reason": self.volume_reason,
            "new_listing_count": self.new_listing_count,
            "listing_status": self.listing_status,
            "listing_reason": self.listing_reason,
            "baseline_date": self.baseline_date,
        }


@dataclass
class ExchangeAttentionResult:
    as_of: str
    status: str  # snapshot-level "ok" | "unavailable"
    reason: str | None
    redistributable: bool
    categories: dict[str, CategoryAttention]
    coins: list[CoinResolution]


def resolve_symbol(symbol: str, perps: list[hl.PerpMarket]) -> hl.PerpMarket | None:
    sym = symbol.upper().strip()
    for p in perps:
        if p.base == sym:
            return p
    for p in perps:
        if p.base_name == "k" + sym:
            return p
    return None


def name_to_symbol(name: str, category_map: dict[str, str]) -> str | None:
    """Reverse of `resolve_symbol` for a raw perp name."""
    if name in category_map:
        return name
    if name.startswith("k") and name[1:] in category_map:
        return name[1:]
    if name.upper() in category_map:
        return name.upper()
    return None


def compute_exchange_attention(
    snapshot: hl.ExchangeSnapshotResult,
    category_map: dict[str, str],
    baseline: tuple[str, list[str]] | None,
) -> ExchangeAttentionResult:
    category_ids = sorted(set(category_map.values())) + [UNMAPPED]

    if snapshot.status != "ok":
        cats = {
            c: CategoryAttention(c, None, "unavailable", snapshot.reason, None, "unavailable", snapshot.reason, None)
            for c in category_ids
        }
        coins = [CoinResolution(s, c, None, "unavailable", snapshot.reason) for s, c in sorted(category_map.items())]
        return ExchangeAttentionResult(snapshot.as_of, "unavailable", snapshot.reason, snapshot.redistributable, cats, coins)

    perps = snapshot.perps

    # --- resolution + volume share ---------------------------------------
    coins: list[CoinResolution] = []
    claimed: dict[str, str] = {}  # base_name -> category
    for sym, cat in sorted(category_map.items()):
        market = resolve_symbol(sym, perps)
        if market is None:
            coins.append(CoinResolution(sym, cat, None, "unavailable", NO_MARKET))
            continue
        claimed.setdefault(market.base_name, cat)
        coins.append(CoinResolution(sym, cat, market.base_name, "ok"))

    volumes = {p.base_name: p.quote_volume for p in perps if p.quote_volume is not None}
    total = sum(volumes.values())
    per_cat: dict[str, float] = {c: 0.0 for c in category_ids}
    has_market: set[str] = set()
    for p in perps:
        cat = claimed.get(p.base_name, UNMAPPED)
        has_market.add(cat)
        if p.quote_volume is not None:
            per_cat[cat] += p.quote_volume

    # --- new listings ------------------------------------------------------
    today_names = {p.base_name for p in perps}
    new_by_cat: dict[str, list[str]] = {c: [] for c in category_ids}
    baseline_date = None
    if baseline is not None:
        baseline_date, baseline_names = baseline
        for name in sorted(today_names - set(baseline_names)):
            sym = name_to_symbol(name, category_map)
            cat = category_map[sym] if sym is not None else UNMAPPED
            new_by_cat[cat].append(name)

    cats: dict[str, CategoryAttention] = {}
    for c in category_ids:
        if total <= 0:
            share, v_status, v_reason = None, "unavailable", "zero-total-volume"
        elif c not in has_market:
            share, v_status, v_reason = None, "unavailable", NO_MARKET
        else:
            share, v_status, v_reason = per_cat[c] / total, "ok", None
        if baseline is None:
            count, l_status, l_reason = None, "unavailable", NO_BASELINE
        else:
            count, l_status, l_reason = len(new_by_cat[c]), "ok", None
        cats[c] = CategoryAttention(c, share, v_status, v_reason, count, l_status, l_reason, baseline_date, new_by_cat[c])

    return ExchangeAttentionResult(snapshot.as_of, "ok", None, snapshot.redistributable, cats, coins)


def latest_baseline_before(date: str) -> tuple[str, list[str]] | None:
    earlier = [d for d in cache.list_exchange_market_snapshot_dates() if d < date]
    if not earlier:
        return None
    d = earlier[-1]
    names = cache.read_exchange_market_snapshot(d)
    return None if names is None else (d, names)


def run_daily(exchange=None, now: datetime | None = None, category_map: dict[str, str] | None = None) -> ExchangeAttentionResult:
    """Fetch once, archive today's market list, compute, and append one row
    per category. Safe to re-run the same UTC day: every write is
    append-only, so the day's first observation stands."""
    snapshot = hl.fetch_daily_market_snapshot(exchange=exchange, now=now)
    cmap = mapping.load_category_map() if category_map is None else category_map
    baseline = latest_baseline_before(snapshot.as_of)
    result = compute_exchange_attention(snapshot, cmap, baseline)
    if snapshot.status == "ok":
        cache.write_exchange_market_snapshot(snapshot.as_of, [p.base_name for p in snapshot.perps])
    for cat_id, attention in result.categories.items():
        cache.write_exchange_point(cat_id, attention.as_row(snapshot.as_of))
    return result
