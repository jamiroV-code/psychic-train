"""T201: candidate term groups for the campaign, from repo data only. Pure; no network."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from api.data.attention import trends
from api.data.attention import trends_candidates as c
from api.data.attention import trends_keywords as tk


def terms(groups):
    return [list(g.terms) for g in groups]


def test_baseline_first_then_variant_then_bundle():
    entry = {"term": "akedo crypto", "label": "Akedo"}
    groups = c.candidate_groups("AKE", entry, query_name="AKE", coingecko_id="akedo")
    assert [g.kind for g in groups] == ["baseline", "variant", "bundle"]
    assert terms(groups)[0] == ["akedo crypto"]
    assert terms(groups)[1] == ["ake crypto"]
    # the bundle keeps the current term first, then the best-fitting variants (label name first), at most 3 terms
    assert terms(groups)[2] == ["akedo crypto", "ake crypto", "akedo coin"]


def test_topic_baseline_is_never_bundled_with_terms():
    entry = {"topic": "/g/11w1qyc8h6", "label": "Aave"}
    groups = c.candidate_groups("AAVE", entry, query_name="Aave", coingecko_id="aave")
    assert terms(groups)[0] == ["/g/11w1qyc8h6"]
    assert terms(groups)[2] == ["aave crypto", "aave coin", "aave token"]
    assert all("/g/" not in t for g in groups[1:] for t in g.terms)


def test_no_keyword_coin_has_no_baseline():
    groups = c.candidate_groups("XYZ", {"no-keyword": True, "label": "Xyz Labs", "note": "n"}, query_name=None)
    assert groups[0].kind == "variant" and "baseline" not in [g.kind for g in groups]
    assert terms(groups)[0] == ["xyz labs crypto"]
    # the ticker is the last name source
    assert terms(c.candidate_groups("XYZ", None))[0] == ["xyz crypto"]


def test_name_risk_coins_get_qualified_terms_only():
    for sym in sorted(trends.NAME_RISK_SYMBOLS):
        groups = c.candidate_groups(sym, {"term": f"{sym.lower()} crypto", "label": sym.title()},
                                    query_name=sym.title(), coingecko_id=sym.lower(), max_groups=c.MAX_GROUPS)
        for g in groups:
            for t in g.terms:
                assert tk.is_valid_topic(t) or trends.is_qualified_term(t), (sym, t)
        assert "bare-name" not in [g.kind for g in groups] and "bare-ticker" not in [g.kind for g in groups]


def test_bare_name_and_ticker_only_for_other_coins_and_marked():
    groups = c.candidate_groups("AKE", {"term": "akedo crypto", "label": "Akedo"}, query_name="Akedo",
                                max_groups=c.MAX_GROUPS)
    bare = [g for g in groups if g.kind.startswith("bare")]
    assert [g.terms for g in bare] == [("akedo",), ("AKE",)]
    assert all(g.note == "needs qualifier word" for g in bare)
    assert all(not g.kind.startswith("bare") or g.note for g in groups)


def test_every_term_passes_the_loader_safe_check():
    entry = {"term": "pax gold crypto", "label": "PAX Gold (gold-backed!)"}
    groups = c.candidate_groups("PAXG", entry, query_name="PAX Gold", coingecko_id="pax-gold",
                                max_groups=c.MAX_GROUPS)
    flat = [t for g in groups for t in g.terms]
    assert flat and all(tk.is_valid_topic(t) or tk.is_valid_term(t) for t in flat)
    assert not any("!" in t or "(" in t for t in flat)
    long_name = "x" * 39
    assert all(len(t) <= 40 for g in c.candidate_groups("ABC", None, query_name=long_name, max_groups=6)
               for t in g.terms)
    # an underscore or one-letter ticker is never a bare candidate
    memecore = c.candidate_groups("M", None, query_name="Memecore", max_groups=6)
    assert all(g.terms != ("M",) for g in memecore)
    assert not any(t.startswith("m ") for g in memecore for t in g.terms)   # a one-letter name is never a source


def test_dedupe_case_insensitive_and_already_qualified_names_kept_as_is():
    groups = c.candidate_groups("NEAR", {"topic": "/g/11q3ypz8pd", "label": "NEAR Protocol"},
                                query_name="NEAR Protocol", coingecko_id="near", max_groups=c.MAX_GROUPS)
    flat = [t.casefold() for g in groups if g.kind != "bundle" for t in g.terms]
    assert len(flat) == len(set(flat))
    assert ["near protocol"] in terms(groups)
    assert not any("near protocol crypto" in t for t in flat)
    keys = [frozenset(x.casefold() for x in g.terms) for g in groups]
    assert len(keys) == len(set(keys))
    # the current term is not repeated as a variant
    same = c.candidate_groups("AKE", {"term": "ake crypto", "label": "AKE"}, query_name="AKE")
    assert [t for g in same if g.kind == "variant" for t in g.terms].count("ake crypto") == 0


def test_max_groups_and_bundle_size():
    entry = {"term": "akedo crypto", "label": "Akedo"}
    assert len(c.candidate_groups("AKE", entry, query_name="Akedo", max_groups=1)) == 1
    assert len(c.candidate_groups("AKE", entry, query_name="Akedo", max_groups=2)) == 2
    many = c.candidate_groups("AKE", entry, query_name="Akedo", coingecko_id="akedo-two", max_groups=c.MAX_GROUPS)
    assert len(many) == c.MAX_GROUPS
    assert all(len(g.terms) <= trends_groups_max() for g in many)
    assert all(2 <= len(g.terms) <= c.MAX_BUNDLE for g in many if g.kind == "bundle")
    with pytest.raises(ValueError):
        c.candidate_groups("AKE", entry, max_groups=0)
    with pytest.raises(ValueError):
        c.candidate_groups("AKE", entry, max_groups=c.MAX_GROUPS + 1)


def trends_groups_max():
    from api.data.attention import trends_groups
    return trends_groups.MAX_TERMS


def test_key_is_stable():
    g = c.candidate_groups("AKE", {"term": "akedo crypto", "label": "Akedo"})[0]
    assert g.key == "akedo crypto"
    assert c.Candidate(("a b", "c d"), "bundle").key == "a b|c d"


def test_module_has_no_network_import():
    tree = ast.parse(Path(c.__file__).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    banned = ("pytrends", "requests", "httpx", "urllib", "socket", "http", "aiohttp", "pandas", "store", "cache")
    assert not [n for n in names for b in banned if b in n.split(".")], names
