"""S-A (T68): the baskets view over screener groups (D-1). Pure: no I/O.

Groups of section `crypto` ARE the baskets; the group `main` is "Unassigned"
and is never a basket. A layout without `main` has every group as a basket.
"""
from __future__ import annotations

from api.data.layout import DEFAULT_GROUP_ID
from api.models.layout import Layout, LayoutGroup


def baskets(layout: Layout) -> list[LayoutGroup]:
    return [g for g in layout.groups if g.id != DEFAULT_GROUP_ID]


def unassigned(layout: Layout) -> list[str]:
    main = next((g for g in layout.groups if g.id == DEFAULT_GROUP_ID), None)
    return list(main.coins) if main else []


def basket_of(layout: Layout, symbol: str) -> LayoutGroup | None:
    """The basket holding `symbol`; None when Unassigned or not in the layout."""
    return next((g for g in baskets(layout) if symbol in g.coins), None)
