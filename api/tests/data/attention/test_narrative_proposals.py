"""T223 O5: proposals use stored categories; they never place a coin."""
import copy

from api.data.attention import narrative_proposals as proposals


def test_all_category_matches_are_proposed_without_mutation():
    ledger = {"coins": {"new": {"symbol": "NEW", "state": "member", "class": "normal"}}}
    categories = {"date": "2026-11-01", "categories": [
        {"id": "cat-a", "symbols": ["NEW"]}, {"id": "cat-b", "symbols": ["NEW"]},
        {"id": "unmapped", "symbols": ["NEW"]}]}
    mapping = {"cat-a": {"narrative": "defi"}, "cat-b": {"narrative": "layer-1"}}
    before = copy.deepcopy((ledger, categories, mapping))
    result = proposals.build(ledger, categories, mapping, set())
    assert [p["narrative"] for p in result["coins"]["NEW"]] == ["defi", "layer-1"]
    assert result["coins"]["NEW"][0]["category"] == "cat-a"
    assert (ledger, categories, mapping) == before
    assert proposals.build(ledger, categories, mapping, {"NEW"})["coins"] == {}
    for key, value in (("state", "watching"), ("class", "unknown")):
        changed = copy.deepcopy(ledger)
        changed["coins"]["new"][key] = value
        assert proposals.build(changed, categories, mapping, set())["coins"] == {}
    assert proposals.build(ledger, categories, {}, set())["coins"] == {}
