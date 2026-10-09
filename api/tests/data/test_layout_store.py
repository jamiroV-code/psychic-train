"""T40 / S5a: the layout store (C2, C3). Every test runs against tmp_path:
the autouse fixture redirects the watchlist path, and the layout follows it.
"""
from __future__ import annotations

import inspect
import json
import os

import pytest

from api.analytics import screener_board
from api.data import layout as layout_store
from api.data import watchlist as watchlist_store
from api.models.layout import LayoutGroup, LayoutUpdate


@pytest.fixture(autouse=True)
def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.delenv("SCREENER_LAYOUT_PATH", raising=False)
    return tmp_path


def _coins(*symbols):
    for s in symbols:
        watchlist_store.add_coin(s)


def _update(revision, groups, hidden=()):
    return LayoutUpdate(
        revision=revision,
        groups=[LayoutGroup(id=i, name=n, coins=list(c)) for i, n, c in groups],
        hidden_lines=list(hidden),
    )


def _stored(tmp_path):
    return json.loads((tmp_path / "layout.json").read_text())


def test_default_is_one_main_group_in_watchlist_order():
    _coins("ETH", "BTC", "SOL")
    layout = layout_store.read_layout("crypto")
    assert layout.source == "default" and layout.revision == 0 and layout.saved_at is None
    assert [(g.id, g.name, g.coins) for g in layout.groups] == [("main", "Main", ["ETH", "BTC", "SOL"])]
    assert layout.hidden_lines == [] and layout.version == 1 and layout.section == "crypto"


def test_read_of_missing_file_creates_nothing(tmp_path):
    _coins("BTC")
    layout_store.read_layout("crypto")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["watchlist.json"]


def test_save_round_trip_bumps_revision_and_sets_z_saved_at(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(layout_store, "_now", lambda: datetime(2026, 10, 9, 12, 0, 5, tzinfo=timezone.utc))
    _coins("BTC", "ETH")
    saved = layout_store.save_layout("crypto", _update(0, [("majors", "Majors", ["ETH", "BTC"])]))
    assert saved.revision == 1 and saved.source == "file"
    assert saved.saved_at == "2026-10-09T12:00:05Z"
    again = layout_store.read_layout("crypto")
    assert again.model_dump() == saved.model_dump()
    assert layout_store.save_layout("crypto", _update(1, [("majors", "Majors", ["BTC", "ETH"])])).revision == 2


def test_stale_revision_is_refused_and_file_unchanged(tmp_path):
    _coins("BTC")
    layout_store.save_layout("crypto", _update(0, [("main", "Main", ["BTC"])]))
    before = (tmp_path / "layout.json").read_bytes()
    with pytest.raises(layout_store.StaleRevisionError):
        layout_store.save_layout("crypto", _update(0, [("other", "Other", ["BTC"])]))
    assert (tmp_path / "layout.json").read_bytes() == before


def test_reconcile_drops_coins_off_the_watchlist():
    _coins("BTC", "ETH")
    layout_store.save_layout("crypto", _update(0, [("a", "A", ["BTC"]), ("b", "B", ["ETH"])]))
    watchlist_store.remove_coin("ETH")
    groups = layout_store.read_layout("crypto").groups
    assert [(g.id, g.coins) for g in groups] == [("a", ["BTC"]), ("b", [])]


def test_reconcile_appends_unplaced_coins_to_last_group():
    _coins("BTC", "ETH")
    layout_store.save_layout("crypto", _update(0, [("a", "A", ["BTC"]), ("b", "B", [])]))
    _coins("SOL", "DOGE")
    groups = layout_store.read_layout("crypto").groups
    assert [(g.id, g.coins) for g in groups] == [("a", ["BTC"]), ("b", ["ETH", "SOL", "DOGE"])]


def test_save_drops_unknown_coins(tmp_path):
    _coins("BTC")
    saved = layout_store.save_layout("crypto", _update(0, [("main", "Main", ["NOPE", "BTC"])]))
    assert saved.groups[0].coins == ["BTC"]
    assert _stored(tmp_path)["sections"]["crypto"]["groups"][0]["coins"] == ["BTC"]


def test_save_rejects_coin_in_two_groups_and_bad_shapes(tmp_path):
    _coins("BTC")
    bad = [
        _update(0, [("a", "A", ["BTC"]), ("b", "B", ["BTC"])]),
        _update(0, []),
        _update(0, [("a", "   ", [])]),
        _update(0, [("a", "x" * 41, [])]),
        _update(0, [("Bad_Id", "A", [])]),
        _update(0, [("a", "A", []), ("a", "B", [])]),
    ]
    for update in bad:
        with pytest.raises(layout_store.InvalidLayoutError):
            layout_store.save_layout("crypto", update)
    assert not (tmp_path / "layout.json").exists()


def test_save_rejects_duplicate_names_and_thirteenth_group():
    with pytest.raises(layout_store.InvalidLayoutError):
        layout_store.save_layout("crypto", _update(0, [("a", "Majors", []), ("b", " majors ", [])]))
    twelve = [(f"g{i}", f"G{i}", []) for i in range(12)]
    assert len(layout_store.save_layout("crypto", _update(0, twelve)).groups) == 12
    with pytest.raises(layout_store.InvalidLayoutError):
        layout_store.save_layout("crypto", _update(1, twelve + [("g12", "G12", [])]))


def test_hidden_lines_keep_references_and_drop_removed_coins():
    assert layout_store.REFERENCE_SYMBOLS == screener_board.SPAGHETTI_REFERENCES
    _coins("ETH", "SOL")
    saved = layout_store.save_layout(
        "crypto", _update(0, [("main", "Main", [])], hidden=["BTC", "HYPE", "ETH", "SOL", "NOPE"])
    )
    assert saved.hidden_lines == ["BTC", "HYPE", "ETH", "SOL"]
    watchlist_store.remove_coin("SOL")
    assert layout_store.read_layout("crypto").hidden_lines == ["BTC", "HYPE", "ETH"]


def test_interrupted_write_keeps_old_file_and_no_temp_file(tmp_path, monkeypatch):
    _coins("BTC")
    layout_store.save_layout("crypto", _update(0, [("main", "Main", ["BTC"])]))
    before = (tmp_path / "layout.json").read_bytes()

    def boom(_fd):
        raise OSError("disk gone")

    monkeypatch.setattr(layout_store.os, "fsync", boom)
    with pytest.raises(OSError):
        layout_store.save_layout("crypto", _update(1, [("other", "Other", ["BTC"])]))
    assert (tmp_path / "layout.json").read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["layout.json", "watchlist.json"]


def test_corrupt_or_wrong_version_reads_recovered_and_moves_to_bad_on_save(tmp_path):
    _coins("BTC")
    path, bad = tmp_path / "layout.json", tmp_path / "layout.json.bad"
    for content in ("{not json", json.dumps({"version": 2, "sections": {}})):
        path.write_text(content)
        bad.write_text("older bad file")
        layout = layout_store.read_layout("crypto")
        assert layout.source == "recovered" and layout.revision == 0
        assert path.read_text() == content
        saved = layout_store.save_layout("crypto", _update(0, [("main", "Main", ["BTC"])]))
        assert saved.revision == 1 and saved.source == "file"
        assert bad.read_text() == content
    source = inspect.getsource(layout_store)
    assert "os.replace(" in source and "os.rename(" not in source


def test_other_sections_survive_save_and_reset(tmp_path):
    _coins("BTC")
    other = {"revision": 3, "saved_at": None, "groups": [{"id": "x", "name": "X", "coins": ["VOD"]}], "hidden_lines": []}
    (tmp_path / "layout.json").write_text(json.dumps({"version": 1, "sections": {"equities": other}}))
    layout_store.save_layout("crypto", _update(0, [("main", "Main", ["BTC"])]))
    assert _stored(tmp_path)["sections"]["equities"] == other
    reset = layout_store.reset_layout("crypto")
    assert reset.source == "default" and reset.revision == 0
    assert _stored(tmp_path)["sections"] == {"equities": other}


def test_path_follows_watchlist_and_env_override_wins(tmp_path, monkeypatch):
    assert layout_store.layout_path() == tmp_path / "layout.json"
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "sub" / "watchlist.json")
    assert layout_store.layout_path() == tmp_path / "sub" / "layout.json"
    monkeypatch.setenv("SCREENER_LAYOUT_PATH", str(tmp_path / "custom.json"))
    assert layout_store.layout_path() == tmp_path / "custom.json"
    _coins("BTC")
    layout_store.save_layout("crypto", _update(0, [("main", "Main", ["BTC"])]))
    assert (tmp_path / "custom.json").exists() and not (tmp_path / "sub" / "layout.json").exists()


def test_unknown_section_is_refused(tmp_path):
    for call in (
        lambda: layout_store.read_layout("stocks"),
        lambda: layout_store.save_layout("stocks", _update(0, [("main", "Main", [])])),
        lambda: layout_store.reset_layout("stocks"),
    ):
        with pytest.raises(layout_store.UnknownSectionError):
            call()
    assert not os.path.exists(tmp_path / "layout.json")
