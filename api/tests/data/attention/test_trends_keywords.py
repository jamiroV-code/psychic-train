"""Trends keyword file loader and validator (T100a). Pure: no network, no pytrends."""
from __future__ import annotations

import copy
import importlib
import json
import re
import sys
from pathlib import Path

import pytest

from api.analytics.attention import narratives
from api.data.attention import trends_keywords as k
from api.tests.trends_fixtures import block_network


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    block_network(monkeypatch)


def _placed() -> set[str]:
    return {c["symbol"] for n in narratives.load_narratives()["narratives"] for c in n["coins"]}


def _doc(**coins) -> dict:
    doc = {"_anchor": {"term": "Bitcoin", "label": "Bitcoin"}}
    doc.update(coins)
    return doc


def _term(t: str) -> dict:
    return {"term": t, "label": t}


def _err(doc, placed=None) -> str:
    with pytest.raises(k.KeywordFileError) as ei:
        k.validate(doc, placed)
    return str(ei.value)


def test_shipped_file_validates_against_placed_symbols():
    m = k.load(placed_symbols=_placed())
    assert m.warnings == []
    assert m.anchor["term"] == "Bitcoin"
    raw = k.KEYWORDS_PATH.read_text(encoding="utf-8")
    assert '"topic"' not in raw  # seed carries no topic id: those come only from the owner's checker run


def test_seed_term_labels_equal_terms():
    m = k.load()
    for sym, e in m.entries.items():
        if "term" in e:
            assert e["label"] == e["term"], sym
        else:
            assert e.get("no-keyword") is True and e["note"], sym


def test_every_placed_coin_has_an_entry():
    placed = _placed()
    assert placed, "narratives file places no coin"
    assert placed - set(k.load().entries) == set()


def test_placed_coin_without_entry_fails():
    doc = _doc(SOL=_term("Solana"))
    msg = _err(doc, {"SOL", "NEWCOIN"})
    assert "NEWCOIN" in msg


def test_extra_symbol_outside_universe_warns_only():
    out = k.validate(_doc(SOL=_term("Solana"), OLD=_term("Old Coin")), {"SOL"})
    assert any("OLD" in w for w in out["warnings"])
    assert set(out["entries"]) == {"SOL", "OLD"}


@pytest.mark.parametrize("entry", [
    {"label": "X"},
    {"topic": "/m/0abc", "term": "Xcoin", "label": "X"},
    {"term": "Xcoin", "no-keyword": True, "note": "n", "label": "X"},
    {"no-keyword": False, "note": "n", "label": "X"},
])
def test_entry_needs_exactly_one_of_topic_term_no_keyword(entry):
    assert "XC" in _err(_doc(XC=entry))


@pytest.mark.parametrize("topic,ok", [
    ("/m/0abc_1", True), ("/g/11xyz", True),
    ("m/0abc", False), ("/x/1", False), ("/m/", False), ("/m/a b", False),
    ("https://trends.google.com/m/0abc", False), (7, False),
])
def test_topic_regex(topic, ok):
    doc = _doc(XC={"topic": topic, "label": "X"})
    if ok:
        assert k.validate(doc)["entries"]["XC"]["topic"] == topic
    else:
        _err(doc)


@pytest.mark.parametrize("term,ok", [
    ("Pump.fun", True), ("AT&T", True), ("Shiba Inu", True), ("O'Hara-X", True),
    ("a,b", False), ('a"b', False), ("a/b", False), ("a\\b", False), ("a?b", False), ("a#b", False),
    ("a\nb", False), ("x", False), ("y" * 41, False), (" lead", False), ("trail ", False), ("Café", False),
])
def test_term_safe_characters(term, ok):
    doc = _doc(XC={"term": term, "label": "X"})
    if ok:
        assert k.validate(doc)["entries"]["XC"]["term"] == term
    else:
        _err(doc)


def test_duplicate_topic_rejected():
    msg = _err(_doc(AA={"topic": "/m/0abc", "label": "A"}, BB={"topic": "/m/0abc", "label": "B"}))
    assert "BB" in msg and "unique" in msg


def test_duplicate_term_rejected_case_insensitive():
    msg = _err(_doc(AA=_term("Aave"), BB={"term": "AAVE", "label": "B"}))
    assert "BB" in msg and "unique" in msg
    _err(_doc(AA=_term("Aave"), BB={"term": "aave ", "label": "B"}))


def test_no_keyword_requires_note():
    assert "XC" in _err(_doc(XC={"no-keyword": True, "label": "X"}))
    assert "XC" in _err(_doc(XC={"no-keyword": True, "label": "X", "note": "  "}))
    assert k.validate(_doc(XC={"no-keyword": True, "label": "X", "note": "gold token"}))


@pytest.mark.parametrize("label", [None, "", "   ", "a\tb", "z" * 61, 5])
def test_label_required_and_non_empty_on_every_entry(label):
    for base in ({"term": "Xcoin"}, {"no-keyword": True, "note": "n"}, {"topic": "/m/0x"}):
        entry = dict(base)
        if label is not None:
            entry["label"] = label
        assert "XC" in _err(_doc(XC=entry))


@pytest.mark.parametrize("key", ["sol", "../x", "A" * 25, "", "SO L"])
def test_symbol_keys_must_match_pattern(key):
    _err(_doc(**{key: _term("Solana")}))


def test_symbol_pattern_matches_narratives_module():
    assert k.SYMBOL_RE.pattern == narratives.SYMBOL_RE.pattern


def test_anchor_required_and_shape():
    _err({"SOL": _term("Solana")})
    _err({"_anchor": {"no-keyword": True, "note": "n", "label": "x"}})
    _err({"_anchor": "Bitcoin"})
    assert k.validate({"_anchor": {"topic": "/m/05p0rrx", "label": "Bitcoin"}})["anchor"]["topic"] == "/m/05p0rrx"
    assert k.validate({"_anchor": _term("Bitcoin")})["anchor"]["term"] == "Bitcoin"


def test_anchor_may_share_keyword_with_a_coin_and_is_not_a_coin():
    doc = _doc(BTC=_term("Bitcoin"), ETH=_term("Ethereum"))
    out = k.validate(doc, {"BTC", "ETH"})
    assert k.ANCHOR_KEY not in out["entries"] and out["warnings"] == []
    m = k.KeywordMap(out["entries"], out["anchor"], out["warnings"])
    assert m.keyword_symbols() == ["BTC", "ETH"]
    assert m.keyword_for(k.ANCHOR_KEY) is None
    assert m.anchor_keyword() == "Bitcoin"


def test_unknown_underscore_key_and_unknown_field_rejected():
    _err(_doc(_comment={"term": "Note", "label": "x"}))
    assert "XC" in _err(_doc(XC={"term": "Xcoin", "label": "X", "tpoic": "/m/0x"}))
    _err(["not", "an", "object"])
    _err(_doc(XC=["Xcoin"]))


def test_duplicate_json_key_rejected(tmp_path):
    p = tmp_path / "k.json"
    p.write_text('{"_anchor": {"term": "Bitcoin", "label": "Bitcoin"}, "SOL": {"term": "Solana", "label": "Solana"},'
                 ' "SOL": {"term": "Sol", "label": "Sol"}}', encoding="utf-8")
    with pytest.raises(k.KeywordFileError):
        k.load(p)


def test_safe_load_never_raises_and_returns_fixed_reason(tmp_path):
    marker = "UNIQUE_CONTENT_MARKER"
    cases = {
        "missing": None,
        "badjson": "{" + marker,
        "list": json.dumps([marker]),
        "utf8": b"\xff\xfe" + marker.encode(),
        "invalid": json.dumps({"_anchor": {"term": "Bitcoin", "label": "Bitcoin"}, "XC": {"term": marker + ",", "label": "X"}}),
    }
    for name, content in cases.items():
        p = tmp_path / f"{name}.json"
        if isinstance(content, bytes):
            p.write_bytes(content)
        elif content is not None:
            p.write_text(content, encoding="utf-8")
        result, reason = k.safe_load(p)
        assert result is None and reason == k.BAD_FILE_REASON == "bad keyword file", name
        assert marker not in reason and str(tmp_path) not in reason
    good, reason = k.safe_load(placed_symbols=_placed())
    assert good is not None and reason == ""
    missing, reason = k.safe_load(placed_symbols=_placed() | {"ZZZNEW"})
    assert missing is None and reason == "bad keyword file"


def test_keyword_for_returns_topic_over_term_none_for_no_keyword():
    out = k.validate(_doc(TT={"topic": "/m/0t", "label": "T"}, RR=_term("Rcoin"),
                          NN={"no-keyword": True, "note": "n", "label": "N"}))
    m = k.KeywordMap(out["entries"], out["anchor"], out["warnings"])
    assert m.keyword_for("TT") == "/m/0t"
    assert m.keyword_for("RR") == "Rcoin"
    assert m.keyword_for("NN") is None and m.keyword_for("UNKNOWN") is None
    assert m.keyword_symbols() == ["TT", "RR"]


def test_module_imports_without_pytrends_or_analytics(monkeypatch):
    monkeypatch.setitem(sys.modules, "pytrends", None)
    monkeypatch.setitem(sys.modules, "pytrends.request", None)
    monkeypatch.delitem(sys.modules, "api.data.attention.trends_keywords", raising=False)
    mod = importlib.import_module("api.data.attention.trends_keywords")
    assert mod.load().entries
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+api\.analytics", src, re.MULTILINE)
    assert not re.search(r"^\s*(from|import)\s+(pytrends|requests|httpx|socket|urllib)", src, re.MULTILINE)


def test_validate_does_not_mutate_input():
    doc = _doc(SOL=_term("Solana"))
    before = copy.deepcopy(doc)
    k.validate(doc, {"SOL"})
    assert doc == before
