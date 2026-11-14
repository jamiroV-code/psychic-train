"""T223 O4: bot overlays merge under the owner files and never break them (AC12, AC16)."""
from __future__ import annotations

import json

from api.data.attention import trends_keywords as tk
from api.data.attention import web_queries as wq


def write_overlay(path, entries) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"entries": entries}))


def owner_map():
    return tk.KeywordMap({"BTC": {"topic": "/m/05p0rrx", "label": "Bitcoin"},
                          "AMB": {"term": "amb coin", "label": "Amb"}},
                         {"term": "cryptocurrency", "label": "anchor"}, ambiguous=frozenset({"AMB", "NEWAMB"}))


def test_owner_entry_beats_overlay_and_good_entries_merge():
    km, dropped = tk.merge_overlay(owner_map(), {"entries": {
        "BTC": {"topic": "/g/other", "label": "x"},
        "NEW": {"topic": "/g/new1", "label": "New", "source": "auto", "resolved_at": "2026-11-01"}}})
    assert km.entries["BTC"]["topic"] == "/m/05p0rrx"
    assert km.entries["NEW"] == {"topic": "/g/new1", "label": "New"}
    assert dropped == [("BTC", "owner entry wins")]


def test_collisions_bad_entries_and_hostile_names_are_dropped_never_raise():
    entries = {
        "DUPT": {"topic": "/m/05p0rrx", "label": "dup of owner"},
        "ANC": {"term": "Cryptocurrency", "label": "anchor clash"},
        "ONE": {"topic": "/g/same", "label": "a"}, "TWO": {"topic": "/g/same", "label": "b"},
        "APP": {"term": "app coin", "label": "x", "approved": "app coin"},
        "NOK": {"no-keyword": True, "note": "n", "label": "x"},
        "NEWAMB": {"term": "newamb coin", "label": "x"},
        "BADT": {"topic": "not-a-topic", "label": "x"},
        "_anchor": {"term": "x x", "label": "x"}, "_ambiguous": ["X"],
        "lower": {"topic": "/g/l", "label": "x"}, "HOST": {"topic": "/g/h", "label": "\u202e::warning::"},
        "LIST": [1, 2], "EXTRA": {"topic": "/g/e", "label": "x", "evil": 1},
    }
    km, dropped = tk.merge_overlay(owner_map(), {"entries": entries})
    assert set(km.entries) == {"BTC", "AMB", "ONE"}
    reasons = dict(dropped)
    assert reasons["DUPT"] == reasons["ANC"] == reasons["TWO"] == "collides with another keyword"
    assert reasons["APP"] == reasons["NOK"] == "approved or no-keyword not allowed"
    assert reasons["NEWAMB"] == "ambiguous symbol: no automatic term"
    assert reasons["BADT"] == reasons["HOST"] == reasons["LIST"] == reasons["EXTRA"] == "invalid entry"
    assert reasons["_anchor"] == reasons["_ambiguous"] == reasons["lower"] == "bad symbol"


def test_overlay_absent_or_broken_loads_as_before(isolated_cache):
    owner = tk.load()
    assert tk.load_merged().entries == owner.entries
    tk.overlay_path().parent.mkdir(parents=True, exist_ok=True)
    tk.overlay_path().write_text("{not json")
    assert tk.load_merged().entries == owner.entries
    write_overlay(tk.overlay_path(), "nope")
    assert tk.load_merged().entries == owner.entries


def test_load_and_safe_load_stay_owner_only_and_an_explicit_path_never_merges(isolated_cache):
    write_overlay(tk.overlay_path(), {"ZZNEW": {"topic": "/g/zznew", "label": "Zz"}})
    assert "ZZNEW" in tk.load_merged().entries and "ZZNEW" in tk.safe_load_merged()[0].entries
    assert "ZZNEW" not in tk.load().entries and "ZZNEW" not in tk.safe_load()[0].entries
    assert "ZZNEW" not in tk.load_merged(tk.KEYWORDS_PATH).entries
    assert tk.keyword_status(tk.load_merged(), "ZZNEW") == "topic"


def test_queries_overlay_joins_only_placed_coins_and_owner_wins(isolated_cache):
    owner = wq.load()
    some = next(iter(owner.coins))
    write_overlay(wq.overlay_path(), {
        "ZZNEW": {"name": "Zz New", "cashtag_only": True, "source": "auto"},
        "ZZOFF": {"name": "Zz Off", "cashtag_only": True},
        some: {"name": "Other Name", "cashtag_only": True},
        "ZZBAD": {"name": "Zz", "cashtag_only": False}, "ZZHOST": {"name": "\u202eevil", "cashtag_only": True}})
    assert set(wq.load_merged().coins) == set(owner.coins)                      # nothing placed: overlay stays out
    placed = [*owner.coins, "ZZNEW"]
    q = wq.load_merged(placed_symbols=placed)
    assert q.coins["ZZNEW"] == {"name": "Zz New", "cashtag_only": True} and "ZZOFF" not in q.coins
    assert q.coins[some] == owner.coins[some]
    assert wq.x_query(q, "ZZNEW").startswith('"$ZZNEW"')
    assert "ZZNEW" not in wq.load().coins and "ZZNEW" not in wq.load(wq.QUERIES_PATH).coins
    _, dropped = wq.merge_overlay(owner, json.loads(wq.overlay_path().read_text()), placed)
    assert dict(dropped) == {some: "owner entry wins", "ZZBAD": "invalid entry", "ZZHOST": "invalid entry"}


def test_queries_overlay_absent_loads_as_before(isolated_cache):
    assert wq.load_merged().coins == wq.load().coins
