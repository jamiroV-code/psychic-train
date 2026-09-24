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


import json
import logging

import pytest

SEEDS = {"seed_categories": [{"id": i, "label": i, "keywords": []} for i in ("ai", "rwa", "l2s", "memecoins")]}


@pytest.fixture
def map_files(tmp_path):
    seeds = tmp_path / "seeds.json"
    seeds.write_text(json.dumps(SEEDS))
    cmap = tmp_path / "map.json"

    def write(obj):
        cmap.write_text(obj if isinstance(obj, str) else json.dumps(obj))
        return mapping.load_category_map(cmap, seeds)

    return write, cmap, seeds


class TestLegacyMapFrozen:
    def test_legacy_map_is_exactly_the_three_original_entries(self):
        assert mapping.LEGACY_COIN_CATEGORY_MAP == {"BTC": "store-of-value", "ETH": "l2s", "HYPE": "l2s"}
        assert mapping.COIN_CATEGORY_MAP is mapping.LEGACY_COIN_CATEGORY_MAP

    def test_curated_only_coin_is_unmapped_in_legacy_lookup(self):
        assert mapping.map_coin_to_category("ARB") is None


class TestCuratedMapFile:
    def test_real_file_loads_the_approved_map(self):
        m = mapping.load_category_map()
        assert len(m) == 32
        counts = {c: sum(1 for v in m.values() if v == c) for c in ("ai", "rwa", "l2s", "memecoins")}
        assert counts == {"ai": 7, "rwa": 7, "l2s": 9, "memecoins": 8}

    def test_every_legacy_entry_is_in_the_curated_map_with_same_value(self):
        m = mapping.load_category_map()
        for sym, cat in mapping.LEGACY_COIN_CATEGORY_MAP.items():
            assert m[sym] == cat

    def test_narrative_only_flag(self):
        assert mapping.map_coin_to_narrative_category("arb") == ("l2s", True)
        assert mapping.map_coin_to_narrative_category("ETH") == ("l2s", False)
        assert mapping.map_coin_to_narrative_category("BTC") == ("store-of-value", False)
        assert mapping.map_coin_to_narrative_category("NOPE") == (None, False)


class TestCuratedMapValidation:
    def test_invalid_entries_skipped_with_warning_valid_ones_kept(self, map_files, caplog):
        write, _, _ = map_files
        with caplog.at_level(logging.WARNING, logger=mapping.logger.name):
            m = write({"_comment": "ignored", "map": {
                "ARB": "l2s", "arb": "l2s", "FOO": "defi", "BTC": "store-of-value", "SOL": "store-of-value",
                "FET": 3,
            }})
        assert m == {"ARB": "l2s", "BTC": "store-of-value"}
        text = caplog.text
        for bad in ("'arb'", "'FOO'", "'SOL'", "'FET'"):
            assert bad in text

    def test_missing_file_is_empty_map_not_crash(self, tmp_path):
        assert mapping.load_category_map(tmp_path / "absent.json", tmp_path / "absent_seeds.json") == {}

    def test_malformed_json_is_empty_map_not_crash(self, map_files):
        write, _, _ = map_files
        assert write("{not json") == {}

    def test_non_object_map_is_empty(self, map_files):
        write, _, _ = map_files
        assert write({"map": ["ARB"]}) == {}

    def test_edit_on_disk_takes_effect_without_restart(self, map_files):
        write, cmap, seeds = map_files
        assert write({"map": {"ARB": "l2s"}}) == {"ARB": "l2s"}
        import os
        cmap.write_text(json.dumps({"map": {"ARB": "ai", "DOGE": "memecoins"}}))
        st = cmap.stat()
        os.utime(cmap, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
        assert mapping.load_category_map(cmap, seeds) == {"ARB": "ai", "DOGE": "memecoins"}
