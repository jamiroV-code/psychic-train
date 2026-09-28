"""narrative-v2 RFC-2: unified narratives.json loader (AC-4..AC-8 partial).

The 6- and 15-narrative fixture builders here are reused by RFC-7's tripwire.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date

import pytest

from api.analytics.narrative import history, mapping, narrative_config
from api.data import cache
from api.scripts import migrate_narrative_config

TODAY = date(2026, 9, 20)


def narrative_fixture(n: int) -> dict:
    """Synthetic config with `n` valid narratives (6 and 15 are the v2 range)."""
    return {"version": 2, "narratives": [
        {"id": f"n{i}", "label": f"Narrative {i}", "keywords": [f"kw{i} crypto", f"alt{i}"],
         "coins": [f"C{i}A", f"C{i}B"], "enabled": True}
        for i in range(n)
    ]}


def _write(path, doc) -> None:
    text = doc if isinstance(doc, str) else json.dumps(doc)
    # Bump mtime explicitly so rapid successive writes are always seen as changes.
    prev = path.stat().st_mtime_ns if path.exists() else 0
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(prev + 10**9, prev + 10**9))


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    path = tmp_path / "narratives.json"
    monkeypatch.setattr(narrative_config, "NARRATIVES_PATH", path)
    return path


def _ids(path=None):
    return [n["id"] for n in narrative_config.load_narratives(path)]


# --- AC-4: edits reflected on re-read, no restart ----------------------------


def test_load_narratives_add_rename_remove_reflected_on_reread(cfg):
    doc = narrative_fixture(2)
    _write(cfg, doc)
    assert _ids() == ["n0", "n1"]

    doc["narratives"].append({"id": "new", "label": "New", "keywords": ["new crypto"], "coins": []})
    _write(cfg, doc)
    assert _ids() == ["n0", "n1", "new"]

    doc["narratives"][0]["label"] = "Renamed"
    _write(cfg, doc)
    assert narrative_config.load_narratives()[0]["label"] == "Renamed"

    doc["narratives"] = doc["narratives"][1:]
    _write(cfg, doc)
    assert _ids() == ["n1", "new"]

    doc["narratives"][0]["enabled"] = False
    _write(cfg, doc)
    assert _ids() == ["new"]
    assert [n["id"] for n in narrative_config.load_all_narratives()] == ["n1", "new"]


def test_returned_copies_do_not_mutate_cache(cfg):
    _write(cfg, narrative_fixture(1))
    narrative_config.load_narratives()[0]["coins"].append("X")
    assert narrative_config.load_narratives()[0]["coins"] == ["C0A", "C0B"]


# --- AC-6: malformed input ---------------------------------------------------


def test_malformed_entry_empty_name_skipped_with_warning(cfg, caplog):
    doc = narrative_fixture(2)
    doc["narratives"][0]["label"] = "  "
    _write(cfg, doc)
    with caplog.at_level(logging.WARNING):
        assert _ids() == ["n1"]
    assert "'n0'" in caplog.text and "label" in caplog.text


@pytest.mark.parametrize("bad", [
    {"id": "", "label": "x", "keywords": ["k"]},
    {"id": "../etc", "label": "x", "keywords": ["k"]},
    {"id": "ok", "label": "x", "keywords": []},
    {"id": "ok", "label": "x", "keywords": ["k"], "enabled": "yes"},
    "not-an-object",
])
def test_other_malformed_entries_skipped(cfg, bad):
    doc = narrative_fixture(1)
    doc["narratives"].insert(0, bad)
    _write(cfg, doc)
    assert _ids() == ["n0"]


def test_invalid_coin_skipped_entry_kept(cfg, caplog):
    doc = narrative_fixture(1)
    doc["narratives"][0]["coins"] = ["FET", "fet", 3, "FET"]
    _write(cfg, doc)
    with caplog.at_level(logging.WARNING):
        assert narrative_config.load_narratives()[0]["coins"] == ["FET"]
    assert "'fet'" in caplog.text


def test_malformed_entry_duplicate_id_skipped_with_warning(cfg, caplog):
    doc = narrative_fixture(2)
    doc["narratives"].append({"id": "n0", "label": "Dup", "keywords": ["dup"]})
    _write(cfg, doc)
    with caplog.at_level(logging.WARNING):
        loaded = narrative_config.load_narratives()
    assert [n["id"] for n in loaded] == ["n0", "n1"]
    assert loaded[0]["label"] == "Narrative 0"  # first wins
    assert "duplicate id 'n0'" in caplog.text and "#2" in caplog.text and "#0" in caplog.text


def test_duplicate_label_allowed_but_warned(cfg, caplog):
    doc = narrative_fixture(2)
    doc["narratives"][1]["label"] = "Narrative 0"
    _write(cfg, doc)
    with caplog.at_level(logging.WARNING):
        assert _ids() == ["n0", "n1"]
    assert "share label" in caplog.text


@pytest.mark.parametrize("broken", ["{not json", "[]", json.dumps({"version": 2}),
                                    json.dumps({"narratives": "x"})])
def test_malformed_top_level_falls_back_to_last_known_good(cfg, caplog, broken):
    _write(cfg, narrative_fixture(3))
    assert _ids() == ["n0", "n1", "n2"]
    _write(cfg, broken)
    with caplog.at_level(logging.WARNING):
        assert _ids() == ["n0", "n1", "n2"]
    assert "last-known-good" in caplog.text


def test_missing_file_without_prior_good_is_empty(tmp_path):
    assert narrative_config.load_narratives(tmp_path / "absent.json") == []


# --- AC-5: narrative coins tagged in the history response ---------------------


def test_narrative_coins_tagged_in_history_response(cfg, isolated_cache):
    _write(cfg, {"version": 2, "narratives": [
        {"id": "ai", "label": "AI", "keywords": ["AI crypto"], "coins": ["TAO", "FET"]},
        {"id": "l2s", "label": "L2s", "keywords": ["layer 2 crypto"], "coins": ["ETH", "ARB"]},
    ]})
    result = history.build_narrative_history(today=TODAY)
    coins = {c.category_id: c.coins for c in result.categories}
    assert coins["ai"] == [("FET", True), ("TAO", True)]
    # ETH is in the frozen legacy map, so it is not narrative-only.
    assert coins["l2s"] == [("ARB", True), ("ETH", False)]


def test_history_unknown_or_disabled_id_rejected(cfg, isolated_cache):
    doc = narrative_fixture(2)
    doc["narratives"][1]["enabled"] = False
    _write(cfg, doc)
    with pytest.raises(history.UnknownCategoryError):
        history.build_narrative_history(["n1"], today=TODAY)


# --- AC-7: rename / remove keep archived history keyed by id ------------------


def _seed_archive(cid: str) -> None:
    for k in range(5):
        cache.write_narrative_point("coingecko-narrative", cid, f"2026-09-{15 + k:02d}", float(k + 1))


def _cg_points(result, cid):
    cat = next(c for c in result.categories if c.category_id == cid)
    s = next(s for s in cat.series if s.source == "coingecko-narrative")
    return list(s.frame["raw"])


def test_rename_preserves_archived_history_by_id(cfg, isolated_cache):
    doc = narrative_fixture(1)
    _write(cfg, doc)
    _seed_archive("n0")
    before = _cg_points(history.build_narrative_history(today=TODAY), "n0")
    doc["narratives"][0]["label"] = "Totally New Name"
    _write(cfg, doc)
    after_result = history.build_narrative_history(today=TODAY)
    assert after_result.categories[0].label == "Totally New Name"
    assert _cg_points(after_result, "n0") == before == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_remove_retains_archive_under_old_id(cfg, isolated_cache):
    doc = narrative_fixture(2)
    _write(cfg, doc)
    _seed_archive("n0")
    removed = doc["narratives"].pop(0)
    _write(cfg, doc)
    assert [c.category_id for c in history.build_narrative_history(today=TODAY).categories] == ["n1"]
    assert list(cache.read_narrative_series("coingecko-narrative", "n0")["raw_value"]) == [1.0, 2.0, 3.0, 4.0, 5.0]
    doc["narratives"].insert(0, removed)
    _write(cfg, doc)
    assert _cg_points(history.build_narrative_history(today=TODAY), "n0") == [1.0, 2.0, 3.0, 4.0, 5.0]


# --- AC-8 (partial): nothing breaks past 4 narratives -------------------------


@pytest.mark.parametrize("n", [6, 15])
def test_many_narratives_load_and_render(cfg, isolated_cache, n):
    _write(cfg, narrative_fixture(n))
    assert len(narrative_config.load_narratives()) == n
    result = history.build_narrative_history(today=TODAY)
    assert [c.category_id for c in result.categories] == [f"n{i}" for i in range(n)]
    assert all(len(c.coins) == 2 for c in result.categories)


# --- migration + repo file -----------------------------------------------------


def test_migration_is_union_of_legacy_files():
    data = migrate_narrative_config.DATA
    doc, dropped = migrate_narrative_config.migrate(
        data / "narrative_categories.json", data / "narrative_category_map.json")
    seeds = json.loads((data / "narrative_categories.json").read_text())["seed_categories"]
    cmap = json.loads((data / "narrative_category_map.json").read_text())["map"]
    assert [n["id"] for n in doc["narratives"]] == [s["id"] for s in seeds]
    for n, s in zip(doc["narratives"], seeds):
        assert n["keywords"] == s["keywords"] and n["label"] == s["label"]
        assert n["coins"] == [sym for sym, cid in cmap.items() if cid == s["id"]]
    assert dropped == ["BTC -> store-of-value"]
    committed = json.loads((data / "narratives.json").read_text())
    assert committed == doc


def test_committed_config_loads_cleanly(caplog):
    with caplog.at_level(logging.WARNING):
        loaded = narrative_config.load_narratives(narrative_config.NARRATIVES_PATH)
    assert [n["id"] for n in loaded] == ["ai", "rwa", "l2s", "memecoins"]
    assert "narratives:" not in caplog.text


def test_legacy_mapping_functions_untouched():
    assert mapping.LEGACY_COIN_CATEGORY_MAP == {"BTC": "store-of-value", "ETH": "l2s", "HYPE": "l2s"}
    assert mapping.map_coin_to_category("eth") == "l2s"
