"""S-A (T68): pure baskets view over screener groups (D-1)."""
from __future__ import annotations

from api.data import baskets_view
from api.models.layout import Layout, LayoutGroup


def _layout(groups, revision=3):
    return Layout(
        version=1,
        section="crypto",
        revision=revision,
        saved_at=None,
        source="file",
        groups=[LayoutGroup(id=i, name=n, coins=c) for i, n, c in groups],
        hidden_lines=[],
    )


def test_main_is_unassigned_never_a_basket():
    lay = _layout([("main", "Main", ["BTC", "ETH"]), ("ai", "AI", ["TAO"])])
    assert [g.id for g in baskets_view.baskets(lay)] == ["ai"]
    assert baskets_view.unassigned(lay) == ["BTC", "ETH"]


def test_layout_without_main_returns_every_group():
    lay = _layout([("ai", "AI", ["TAO"]), ("l2", "L2", ["OP"])])
    assert [g.id for g in baskets_view.baskets(lay)] == ["ai", "l2"]
    assert baskets_view.unassigned(lay) == []


def test_empty_basket_stays_listed():
    lay = _layout([("main", "Main", []), ("ai", "AI", [])])
    assert [g.id for g in baskets_view.baskets(lay)] == ["ai"]


def test_basket_of_returns_group_or_none():
    lay = _layout([("main", "Main", ["BTC"]), ("ai", "AI", ["TAO"])])
    assert baskets_view.basket_of(lay, "TAO").name == "AI"
    assert baskets_view.basket_of(lay, "BTC") is None
    assert baskets_view.basket_of(lay, "NOPE") is None
