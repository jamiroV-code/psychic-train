"""VA-41: the seeder refuses to wipe a root that holds unmarked perp data.

Pytest only, temp folders only. The autouse fixture in conftest.py points
every perp variable at the same temp root.
"""
from __future__ import annotations

import pytest

from api.scripts import seed_e2e_cache as seed


def _tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_main_refuses_unmarked_perp_data_and_changes_nothing(isolated_cache):
    snapshot = isolated_cache / "perp" / "hl_snapshot" / "BTC" / "2026-01.jsonl"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text('{"synthetic": 1}\n', encoding="utf-8")
    (isolated_cache / "unrelated.txt").write_text("keep", encoding="utf-8")
    before = _tree(isolated_cache)

    with pytest.raises(SystemExit) as exit_info:
        seed.main()

    assert exit_info.value.code not in (0, None)
    assert _tree(isolated_cache) == before


def test_empty_sub_folders_pass(isolated_cache):
    (isolated_cache / "perp" / "hl_snapshot" / "BTC").mkdir(parents=True)
    seed._refuse_unmarked_perp_data(isolated_cache)


def test_absent_perp_folder_passes(isolated_cache):
    seed._refuse_unmarked_perp_data(isolated_cache)


def test_marked_perp_tree_passes(isolated_cache):
    perp = isolated_cache / "perp"
    (perp / "hl_snapshot" / "BTC").mkdir(parents=True)
    (perp / "hl_snapshot" / "BTC" / "2026-01.jsonl").write_text("{}\n", encoding="utf-8")
    (perp / seed.SEED_MARKER).write_text("", encoding="utf-8")
    seed._refuse_unmarked_perp_data(isolated_cache)


def test_perp_root_named_elsewhere_inside_root_is_refused(isolated_cache, monkeypatch):
    elsewhere = isolated_cache / "other-perp"
    (elsewhere / "daily").mkdir(parents=True)
    (elsewhere / "daily" / "BTC.csv").write_text("2026-01-01,1\n", encoding="utf-8")
    monkeypatch.setenv("SCREENER_PERP_ROOT", str(elsewhere))
    before = _tree(isolated_cache)

    with pytest.raises(SystemExit) as exit_info:
        seed._refuse_unmarked_perp_data(isolated_cache)

    assert exit_info.value.code not in (0, None)
    assert _tree(isolated_cache) == before
