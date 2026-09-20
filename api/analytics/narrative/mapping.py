"""Coin -> narrative-category mapping (item 58).

Curated lookup, never inferred/fuzzy-matched from a coin's name or
description — an unmapped coin returns an explicit no-mapping sentinel
(`None`), never silently treated as belonging to whatever category happens
to be triggered. ADR-4 treats `unmapped` as a distinct, non-failure
`narrative_state`, not folded into `rotated-out` or any other value — a
false mapping would let an unrelated coin's price action masquerade as
corroborating narrative evidence for a category it has nothing to do with,
which is exactly the silent-wrongness this plan's "numbers never silently
wrong" rule forbids.
"""
from __future__ import annotations

# symbol -> category_id. Extend by hand as the watchlist grows; deliberately
# not auto-inferred. Category ids match api/data/narrative_categories.json's
# seed_categories (item 55).
COIN_CATEGORY_MAP: dict[str, str] = {
    "BTC": "store-of-value",
    "ETH": "l2s",
    "HYPE": "l2s",
}


def map_coin_to_category(symbol: str) -> str | None:
    """Returns the curated category_id for `symbol`, or `None` if this coin
    has no curated mapping yet. Callers must treat `None` as an explicit,
    valid state (ADR-4's `unmapped`) — never as a signal to exclude the
    coin from anything, and never as a fallback that treats it as
    vacuously aligned with whatever category is currently triggered.
    """
    return COIN_CATEGORY_MAP.get(symbol.upper())
