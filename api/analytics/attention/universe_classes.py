"""Discovery universe classes (T115 U2): why a top-100 coin is OUT, from a closed reason list.

Order per coin: `force_include` wins over a class and over `not-tradeable`; then the class (stablecoin,
wrapped-staked, tokenized fund = `no-market`), then `not_tradeable` (config), then the venue lists
(`tradeable_markets`, T189): no trading market = zero 24h volume, or no listing on any fresh tracked venue list,
reason `not-tradeable`. A venue list that failed, is stale or is not built is `unknown`: the coin stays IN as
`unverified`, never cut. Otherwise volume never excludes; under `thin_volume_label_below_usd` it only labels the
coin `thin_volume`.

Baskets does not read this module: it keeps `universe.load_reference` (Q-V1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from api.data.attention import tradeable_markets

# Closed list for `excluded_coins` / `excluded_counts`. The last three are not exclusions: an IN coin that is not
# shown (no narrative, only hidden narratives, no usable source until U5), so shown + sum(counts) = universe.
REASONS = ("stablecoin", "wrapped-staked", "no-market", "not-tradeable-config", "not-tradeable", "unassigned",
           "hidden-narrative", "no-source-data")
CLASS_REASON = {"stablecoin": ("stablecoin", "stablecoin"), "wrapped_staked": ("wrapped-staked", "wrapped or staked"),
                "tokenized_fund": ("no-market", "tokenized fund")}
THIN_VOLUME_DEFAULT_USD = 20_000_000
SYMBOL_PATTERN = r"^[A-Z0-9_\-]{1,24}$"
# Removed by U2: a stale local config fails loudly instead of being half-read.
REMOVED_KEYS = {"min_volume_24h_usd": "no volume cut; volume only sets thin_volume (universe_rules)",
                "exclude": "use universe_rules.classes or universe_rules.not_tradeable",
                "exclude_category_ids": "no category exclusion; exchange tokens are IN",
                "include_despite_category": "no category exclusion; use universe_rules.force_include"}


@dataclass
class Universe:
    """The Discovery universe after classes and tradeability; `rows` keep snapshot (cap) order."""
    rows: list[dict]
    eligible: list[str] = field(default_factory=list)                   # IN, universe order
    out: dict[str, tuple[str, str]] = field(default_factory=dict)       # symbol -> (reason, detail)
    tradeability: dict[str, str] = field(default_factory=dict)          # IN symbol -> tradeable | unverified
    volume: dict[str, float | None] = field(default_factory=dict)
    thin: dict[str, bool] = field(default_factory=dict)
    venues: dict[str, tradeable_markets.VenueList] = field(default_factory=dict)   # the lists the answer used


def _symbols(value, name: str) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(s, str) and re.match(SYMBOL_PATTERN, s) for s in value):
        raise ValueError(f"discovery config: universe_rules.{name} must be a list of upper-case symbols")
    return set(value)


def validate_rules(cfg: dict) -> None:
    for key, why in REMOVED_KEYS.items():
        if key in cfg:
            raise ValueError(f"discovery config: {key} is no longer read ({why})")
    rules = cfg["universe_rules"]
    thin = rules.get("thin_volume_label_below_usd", THIN_VOLUME_DEFAULT_USD)
    if isinstance(thin, bool) or not isinstance(thin, (int, float)) or thin < 0:
        raise ValueError("discovery config: universe_rules.thin_volume_label_below_usd must be a number >= 0")
    if "backup_floor_usd" in rules:
        raise ValueError("discovery config: universe_rules.backup_floor_usd is not allowed (no volume cut)")
    classes = rules.get("classes", {})
    if not isinstance(classes, dict) or set(classes) - set(CLASS_REASON):
        raise ValueError(f"discovery config: universe_rules.classes keys must be in {', '.join(CLASS_REASON)}")
    seen: dict[str, str] = {}
    for name, syms in classes.items():
        for s in _symbols(syms, f"classes.{name}"):
            if s in seen:
                raise ValueError(f"discovery config: {s} is in classes {seen[s]} and {name}")
            seen[s] = name
    nt = rules.get("not_tradeable", {})
    if not isinstance(nt, dict) or not all(isinstance(v, str) and v for v in nt.values()):
        raise ValueError("discovery config: universe_rules.not_tradeable must map symbol -> reason text")
    _symbols(list(nt), "not_tradeable")
    both = _symbols(rules.get("force_include", []), "force_include") & set(nt)
    if both:
        raise ValueError(f"discovery config: {', '.join(sorted(both))} in both force_include and not_tradeable")


def classify(symbol: str, rules: dict) -> str:
    """`stablecoin`, `wrapped_staked`, `tokenized_fund` or `normal`."""
    for name, syms in rules.get("classes", {}).items():
        if symbol in syms:
            return name
    return "normal"


def build(rows: list[dict], rules: dict, venues: dict[str, tradeable_markets.VenueList] | None = None,
          today=None) -> Universe:
    """`venues` None: the stored lists, point in time at `today` (None = the UTC date)."""
    if venues is None:
        venues = tradeable_markets.load_venues(today, [str(r["symbol"]) for r in rows])
    force = set(rules.get("force_include", []))
    nt = rules.get("not_tradeable", {})
    thin_below = float(rules.get("thin_volume_label_below_usd", THIN_VOLUME_DEFAULT_USD))
    u = Universe(rows=rows, venues=venues)
    for r in rows:
        s = str(r["symbol"]).upper()
        if s in u.out or s in u.tradeability:
            continue
        vol = r.get("volume_24h")
        vol = float(vol) if isinstance(vol, (int, float)) and not isinstance(vol, bool) else None
        cls = classify(s, rules)
        t = tradeable_markets.tradeability(s, venues, vol)
        if s in force:
            pass
        elif cls != "normal":
            u.out[s] = CLASS_REASON[cls]
            continue
        elif s in nt:
            u.out[s] = ("not-tradeable-config", nt[s])
            continue
        elif t.status == "not_tradeable":
            u.out[s] = ("not-tradeable", t.detail)
            continue
        u.eligible.append(s)
        u.tradeability[s] = "tradeable" if t.status == "tradeable" else "unverified"
        u.volume[s] = vol
        u.thin[s] = vol is not None and vol < thin_below
    return u
