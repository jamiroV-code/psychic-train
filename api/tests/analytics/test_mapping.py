"""Coin -> narrative-category mapping tests (items 58/59)."""
from __future__ import annotations

from api.analytics.narrative import mapping


class TestMapCoinToCategory:
    def test_mapped_coin_returns_its_category(self):
        assert mapping.map_coin_to_category("ETH") == "l2s"

    def test_lookup_is_case_insensitive(self):
        assert mapping.map_coin_to_category("eth") == "l2s"

    def test_unmapped_coin_returns_explicit_none_never_silently_aligned(self):
        # A coin with no curated entry must return the None sentinel, not
        # get silently attached to whatever category happens to be
        # triggered — ADR-4's `unmapped` is a distinct, non-failure state.
        result = mapping.map_coin_to_category("SOMECOIN_NOT_IN_MAP")
        assert result is None
