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
    assert m.warnings == [f"keywords: {s} is not a placed coin" for s in sorted(DISCOVERY_EXTRA | {"PYTH"})]  # T160 extras; T195 PYTH (owner-approved, not placed)
    assert m.anchor["term"] == "Bitcoin"
    topics = {s: e["topic"] for s, e in m.entries.items() if "topic" in e}
    assert topics == ALL_TOPICS  # topic ids come only from the owner (checker runs 21-10-26, 22-10-26; T134, T154)
    assert len(topics) == 41


OWNER_PASS_TOPICS = {
    "AAVE": "/g/11w1qyc8h6", "ADA": "/g/11gf2dcwbj", "ARB": "/g/11w99dbsyz", "BCH": "/g/11d_wtvc5k",
    "BTC": "/m/05p0rrx", "DOGE": "/m/0zmxk9t", "DOT": "/g/11f3mbgrgj", "INJ": "/g/11ldr16mw_",
    "LINK": "/g/11qn04qyw9", "LTC": "/m/0t544l4", "SHIB": "/g/11q1jsfvsn", "SOL": "/g/11qh5y640t",
}
PASS_22 = {
    "BGB": ("/g/11xgyky_2b", "Bitget Token"), "CAKE": ("/g/11vb5nyrj6", "PancakeSwap"),
    "GT": ("/g/11n3zc6c3t", "GateToken"), "HBAR": ("/g/11hbsyfq3f", "Hedera"), "HTX": ("/m/012vj2d4", "HTX"),
    "KCS": ("/g/11ydr7tg_8", "KuCoin Token"), "NEAR": ("/g/11q3ypz8pd", "NEAR Protocol"),
    "UNI": ("/g/11h1dsqb_m", "Uniswap"), "VVV": ("/g/11xv_6jggk", "Venice token"),
    "WLD": ("/g/11t_vkgtjf", "Worldcoin"), "XAUT": ("/g/11n3zb_gpq", "Tether Gold"),
    "XLM": ("/m/0121k_50", "Stellar"), "XMR": ("/m/0130q41b", "Monero"), "XRP": ("/g/11ggfsh1hd", "XRP"),
}
OWNER_ACCEPTED_22 = {
    "ETH": ("/m/0108bn2x", "Ethereum"), "BNB": ("/g/11mjf91p7c", "Binance Coin"),
    "ALGO": ("/g/11rgg857l7", "Algorand"), "FIL": ("/g/11g9ngp3p7", "Filecoin"),
    "KAS": ("/g/11dxd52vfh", "Kaspa"), "ZEC": ("/g/11c1tqqpyq", "Zcash"),
    "TAO": ("/g/11n9szvdlj", "Bittensor"), "HYPE": ("/g/11z3m2dkm4", "Hyperliquid"),
    "ICP": ("/g/11q1mbrj5p", "Internet Computer"), "NEXO": ("/g/113nvt4wp", "Nexo"),
    "PI": ("/g/11kzq2y5bk", "Pi Network"), "PUMP": ("/g/11wr7k80z3", "pump.fun"),
    "XDC": ("/g/11h1y76mtz", "XDC Network"), "WLFI": ("/g/11lp7f_05g", "World Liberty Financial"),
    "AERO": ("/g/11mrd65ng5", "Aerodrome Finance"),
}
ALL_TOPICS = {**OWNER_PASS_TOPICS, **{s: v[0] for s, v in {**PASS_22, **OWNER_ACCEPTED_22}.items()}}


def test_seeded_topics_carry_checker_note_and_name_label():
    m = k.load()
    labels = {"AAVE": "Aave", "ADA": "Cardano", "ARB": "Arbitrum", "BCH": "Bitcoin Cash", "BTC": "Bitcoin",
              "DOGE": "Dogecoin", "DOT": "Polkadot", "INJ": "Injective", "LINK": "Chainlink", "LTC": "Litecoin",
              "SHIB": "Shiba Inu", "SOL": "Solana"}
    for sym, label in labels.items():
        assert m.entries[sym] == {"topic": OWNER_PASS_TOPICS[sym], "label": label, "note": "checker PASS 21-10-26"}


def test_seed_term_labels_equal_terms():
    m = k.load()
    for sym, e in m.entries.items():
        if "term" in e:
            assert e["term"].casefold().startswith(e["label"].casefold()), sym  # T160: label is the project name
        elif "topic" in e:
            assert e["note"] in ("checker PASS 21-10-26", "checker PASS 22-10-26",
                                 "owner-accepted 22-10-26, not checker PASS"), sym
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


def test_t154_topics_carry_owner_notes_and_labels():
    m = k.load()
    for sym, (topic, label) in PASS_22.items():
        assert m.entries[sym] == {"topic": topic, "label": label, "note": "checker PASS 22-10-26"}, sym
    for sym, (topic, label) in OWNER_ACCEPTED_22.items():
        assert m.entries[sym] == {"topic": topic, "label": label,
                                  "note": "owner-accepted 22-10-26, not checker PASS"}, sym


# T160: qualified terms for the coins the owner's checker could not resolve to a topic id.
UNIDENTIFIED: set[str] = set()   # T192: the owner named every one
# Eligible Discovery coins outside the narratives (cache snapshot 2026-10-24); the placed coins are read live.
DISCOVERY_EXTRA = {"DASH", "ETHFI", "M", "PEARL", "VET", "BDX"}
CHECKER_GIVEN = {"APT": "aptos crypto", "ATOM": "cosmos crypto", "AVAX": "avalanche crypto", "CC": "canton coin",
                 "ETC": "ethereum classic crypto", "JST": "just crypto"}


def test_t160_topics_unchanged_and_no_new_topic():
    m = k.load()
    assert {s: e["topic"] for s, e in m.entries.items() if "topic" in e} == ALL_TOPICS


# T192: owner-named projects (CoinGecko pages, 26-10-26). Untested search phrases, not checker PASS. The wanted
# shapes "lighter exchange" and "stable blockchain" have no loader qualifier word, so they are "lighter crypto" and
# "stable chain"; PRL and PEARL are one project (pearl-research / pearl-2) but a term must be unique, so PRL differs.
T192_TERMS = {
    "AKE": ("akedo crypto", "Akedo"), "BTW": ("bitway crypto", "Bitway"),
    "GRAM": ("the open network", "The Open Network"), "LIT": ("lighter crypto", "Lighter"),
    "STABLE": ("stable chain", "Stable"), "RAIN": ("rain protocol", "Rain"),
    "PRL": ("pearl ai coin", "Pearl"),   # OKB and PEARL were reverted by T195
}
T192_NOTE = "owner-named 26-10-26, qualified-term, not checker PASS"
T192_NOTE_OVERRIDE = {"GRAM": "term switched 01-11-26 to the campaign-usable name; owner approved"}


def test_t192_named_tickers_have_exact_qualified_terms():
    from api.data.attention import trends
    m = k.load()
    for sym, (term, label) in T192_TERMS.items():
        want_entry = {"term": term, "label": label, "note": T192_NOTE_OVERRIDE.get(sym, T192_NOTE)}
        got = {f: v for f, v in m.entries[sym].items() if f != "approved"}
        assert got == want_entry, sym
        # stage 2: a listed coin is pulled only when its term is approved (STABLE has no approval)
        approved = m.entries[sym].get("approved") == term
        want = "term" if (sym not in m.ambiguous or approved) else "skipped-unqualified"
        assert trends.is_qualified_term(term) and k.keyword_status(m, sym) == want, sym


# T195: owner probes 26-10-26 showed the T192 terms for OKB and PEARL return mostly zero days; both go back to the
# T160 terms (git history, 235268e). PYTH had no entry; its fallback term is untested.
T195_OKB = {"term": "okb token", "label": "OKB",
            "note": "qualified term: name equals ticker, so 'okb token' (rule exception, T160); not checker-verified"}
T195_PEARL = {"term": "pearl crypto", "label": "Pearl",
              "note": "qualified term: '<project name> crypto' (rule, T160); name from CoinGecko id pearl-2; "
                      "not checker-verified"}


def test_t195_okb_and_pearl_are_reverted_to_the_t160_terms():
    m = k.load()
    for sym, old, why in (("OKB", T195_OKB, "reverted 26-10-26: 'okb crypto' returned 99% zero days, 'okb token' median 65"),
                          ("PEARL", T195_PEARL, "reverted 26-10-26: 'pearl ai crypto' 98% zero days, 'pearl crypto' median 7")):
        e = m.entries[sym]
        assert (e["term"], e["label"]) == (old["term"], old["label"]), sym
        assert e["note"].startswith(old["note"]) and why in e["note"], sym


def test_t195_prl_keeps_its_own_term_and_pyth_is_qualified():
    from api.data.attention import trends
    m = k.load()
    assert m.entries["PRL"]["term"] == "pearl ai coin"
    assert m.entries["PYTH"] == {"term": "pyth network crypto", "label": "Pyth Network",
                                 "note": "owner-approved 26-10-26 fallback term, untested; name from CoinGecko id"}
    assert trends.is_qualified_term("pyth network crypto") and k.keyword_status(m, "PYTH") == "term"


def test_t195_no_duplicate_terms_or_topics_and_topics_unchanged():
    m = k.load()
    terms = [e["term"].casefold() for e in m.entries.values() if "term" in e]
    assert len(terms) == len(set(terms))
    topics = {s: e["topic"] for s, e in m.entries.items() if "topic" in e}
    assert topics == ALL_TOPICS and len(set(topics.values())) == len(topics)


def test_t192_no_unidentified_entry_is_left():
    assert not [s for s, e in k.load().entries.items() if e.get("no-keyword")]


def test_t160_name_risk_symbols_never_have_a_bare_term():
    from api.data.attention import trends
    m = k.load()
    assert m.ambiguous == STAGE2_AMBIGUOUS
    for sym in m.ambiguous:
        e = m.entries[sym]
        assert "topic" in e or trends.is_qualified_term(e["term"]), sym
        if "term" in e:
            assert e["term"].casefold() != sym.casefold(), sym


def test_t160_every_term_has_a_qualifier_word_and_a_note():
    from api.data.attention import trends
    m = k.load()
    terms = {s: e for s, e in m.entries.items() if "term" in e}
    assert terms
    for sym, e in terms.items():
        assert trends.is_qualified_term(e["term"]), sym
        assert e.get("note"), sym


def test_t160_checker_given_terms_exact():
    m = k.load()
    for sym, term in CHECKER_GIVEN.items():
        assert m.entries[sym]["term"] == term, sym
        assert "checker-given" in m.entries[sym]["note"], sym


def test_t160_every_eligible_discovery_symbol_has_an_entry_except_unidentified():
    m = k.load()
    wanted = (_placed() | DISCOVERY_EXTRA) - UNIDENTIFIED
    assert sorted(wanted - set(m.entries)) == []
    for sym in wanted:
        assert "topic" in m.entries[sym] or "term" in m.entries[sym], sym


def test_t160_shipped_file_loads_with_safe_load():
    loaded, reason = k.safe_load(placed_symbols=_placed())
    assert loaded is not None and reason == ""


# --- Stage 2 (D-30): `_ambiguous` list and per-coin approvals bound to the term ---
STAGE2_AMBIGUOUS = frozenset({"TRX", "ONDO", "MORPHO", "ICP", "SHIB", "PEPE", "BNB", "CRO", "HBAR", "LINK", "APT",
                              "SOL", "SKY", "PI", "JST", "NEAR", "GRAM", "RAIN", "M", "CC", "LIT", "NIGHT", "STABLE"})
STAGE2_APPROVED = {"ONDO": "ondo crypto", "PEPE": "Pepe coin", "TRX": "tron crypto", "APT": "aptos crypto",
                   "CRO": "cronos crypto", "MORPHO": "morpho crypto", "RAIN": "rain protocol",
                   "CC": "canton coin", "JST": "just crypto", "GRAM": "the open network",
                   "LIT": "lighter crypto", "NIGHT": "midnight crypto", "STABLE": "stable chain"}
TOPIC = {"topic": "/m/0abc", "label": "X"}
NOKW = {"no-keyword": True, "label": "X", "note": "n"}


def _amb(listed, **coins) -> dict:
    return {**_doc(**coins), "_ambiguous": listed}


def test_stage2_shipped_ambiguous_list_and_exact_approvals():
    m = k.load()
    assert m.ambiguous == STAGE2_AMBIGUOUS and len(m.ambiguous) == 23
    assert {s: e["approved"] for s, e in m.entries.items() if "approved" in e} == STAGE2_APPROVED
    for sym, term in STAGE2_APPROVED.items():
        assert m.entries[sym]["term"] == term and k.keyword_status(m, sym) == "term", sym


def test_stage2_ambiguous_list_valid_and_missing_key_loads():
    m = k.KeywordMap(**k.validate(_amb(["SOL"], SOL=TOPIC)))
    assert m.ambiguous == frozenset({"SOL"})
    assert k.KeywordMap(**k.validate(_doc(SOL=TOPIC))).ambiguous == frozenset()


@pytest.mark.parametrize("listed,needle", [
    (["SOL", "SOL"], "twice"),
    (["SOL", 7], "items must be symbols"),
    (["_anchor"], "items must be symbols"),
    (["sol"], "items must be symbols"),
    ("SOL", "must be a list"),
    (["SOL", "ZZZ"], "without an entry: ZZZ"),
])
def test_stage2_bad_ambiguous_list_is_refused(listed, needle):
    assert needle in _err(_amb(listed, SOL=TOPIC))


@pytest.mark.parametrize("entry,needle", [
    ({**TOPIC, "approved": "x"}, "only on a coin's term entry"),
    ({**NOKW, "approved": "x"}, "only on a coin's term entry"),
    ({"term": "sol crypto", "label": "S", "approved": True}, "must equal its term"),
    ({"term": "sol crypto", "label": "S", "approved": "solana crypto"}, "must equal its term"),
])
def test_stage2_bad_approval_is_refused(entry, needle):
    assert needle in _err(_amb(["SOL"], SOL=entry))


def test_stage2_approval_on_anchor_is_refused():
    doc = _doc()
    doc["_anchor"] = {"term": "Bitcoin", "label": "Bitcoin", "approved": "Bitcoin"}
    assert "only on a coin's term entry" in _err(doc)


def test_stage2_bad_approval_makes_safe_load_report_bad_file(tmp_path):
    p = tmp_path / "kw.json"
    p.write_text(json.dumps(_amb(["SOL"], SOL={"term": "sol crypto", "label": "S", "approved": "other"})))
    m, reason = k.safe_load(p)
    assert m is None and reason == k.BAD_FILE_REASON == "bad keyword file"
    assert k.keyword_status(m, "SOL") == "bad-file"


def test_stage2_keyword_status_rule():
    m = k.KeywordMap(**k.validate(_amb(
        ["APR", "UNA", "TOP", "NOK"],
        APR={"term": "apr crypto", "label": "A", "approved": "apr crypto"},
        UNA={"term": "una crypto", "label": "U"},
        TOP=TOPIC, NOK=NOKW,
        FREE={"term": "FREE", "label": "F"})))
    assert k.keyword_status(m, "APR") == "term"                  # approved term pulled
    assert k.keyword_status(m, "UNA") == "skipped-unqualified"   # unapproved term (qualified or not) skipped
    assert k.keyword_status(m, "TOP") == "topic"                 # topic pulled
    assert k.keyword_status(m, "NOK") == "no-keyword"
    assert k.keyword_status(m, "FREE") == "term"                 # unlisted bare term pulled


def test_stage2_term_edited_without_reapproval_is_skipped():
    """A term edit with the old approval left is a bad file; with the approval removed the coin is skipped."""
    assert "must equal its term" in _err(_amb(["APR"], APR={"term": "apr coin", "label": "A",
                                                             "approved": "apr crypto"}))
    m = k.KeywordMap(**k.validate(_amb(["APR"], APR={"term": "apr coin", "label": "A"})))
    assert k.keyword_status(m, "APR") == "skipped-unqualified"


def test_stage2_approval_for_another_coin_does_not_count():
    m = k.KeywordMap(**k.validate(_amb(["AAA", "BBB"],
                                       AAA={"term": "aaa crypto", "label": "A", "approved": "aaa crypto"},
                                       BBB={"term": "bbb crypto", "label": "B"})))
    assert k.keyword_status(m, "BBB") == "skipped-unqualified"


def test_stage2_added_coin_takes_effect_from_the_file(tmp_path):
    doc = json.loads(k.KEYWORDS_PATH.read_text(encoding="utf-8"))
    assert k.keyword_status(k.load(), "AKE") == "term"
    doc["_ambiguous"] = [*doc["_ambiguous"], "AKE"]
    p = tmp_path / "kw.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert k.keyword_status(k.load(p), "AKE") == "skipped-unqualified"


def test_stage2_keyword_map_positional_construction_still_works():
    m = k.KeywordMap({"SOL": TOPIC}, {"term": "Bitcoin", "label": "B"}, [], [])
    assert m.ambiguous == frozenset() and k.keyword_status(m, "SOL") == "topic"
