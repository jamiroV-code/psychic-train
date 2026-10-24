"""T180: every coin that passes into Discovery has a Google Trends keyword, over the REAL shipped files.

The shipped universe snapshot, Discovery config and keyword file are read as they are; no network.
"""
from __future__ import annotations

import pytest

from api.analytics.attention import discovery
from api.data.attention import trends_keywords as k
from api.tests.trends_fixtures import block_network


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    block_network(monkeypatch)


def _doc(**coins) -> dict:
    return {"_anchor": {"term": "Bitcoin", "label": "Bitcoin"}, **coins}


NO_KW = {"no-keyword": True, "label": "X", "note": "unidentified"}


def test_eligible_discovery_symbols_is_the_discovery_eligible_set():
    cfg = discovery.load_config()
    rows, _ = discovery.load_universe_rows()
    assert discovery.eligible_discovery_symbols() == discovery.eligibility(cfg, rows).eligible
    assert len(discovery.eligible_discovery_symbols()) > 0


def test_eligible_discovery_symbols_empty_without_universe(tmp_path):
    missing = tmp_path / "nope.json"
    assert discovery.eligible_discovery_symbols(universe_path=missing) == []


def test_every_eligible_discovery_coin_has_a_trends_keyword():
    eligible = discovery.eligible_discovery_symbols()
    gaps = k.guard_gaps(k.load(), eligible)
    assert gaps == {"no-entry": [], "no-keyword": [], "skipped-unqualified": [], "allowlist-has-keyword": []}, (
        f"eligible Discovery coins without a Google Trends keyword: {gaps}")


def test_guard_lists_the_exact_missing_symbols():
    m = k.KeywordMap(**k.validate(_doc(
        SOL={"topic": "/m/0sol", "label": "Solana"}, LINK={"term": "Chainlink", "label": "Chainlink"},
        ZZZ=NO_KW, AKE=NO_KW)))
    gaps = k.guard_gaps(m, ["SOL", "NEWCOIN", "LINK", "ZZZ", "AKE"])
    assert gaps == {"no-entry": ["NEWCOIN"], "no-keyword": ["ZZZ"], "skipped-unqualified": ["LINK"],
                    "allowlist-has-keyword": []}


def test_guard_fails_when_an_allowlisted_ticker_gains_a_keyword():
    m = k.KeywordMap(**k.validate(_doc(AKE={"term": "ake crypto", "label": "Ake"})))
    assert k.guard_gaps(m, ["AKE"])["allowlist-has-keyword"] == ["AKE"]
    # also when it is not eligible today: the list must shrink once the owner names the coin
    assert k.guard_gaps(m, [])["allowlist-has-keyword"] == ["AKE"]


def test_allowlist_is_the_named_unidentified_tickers():
    assert k.UNIDENTIFIED_TICKERS == frozenset({"AKE", "BTW", "GRAM", "LIT", "PRL", "RAIN", "STABLE"})


def test_allowlisted_ticker_without_entry_is_still_a_gap():
    m = k.KeywordMap(**k.validate(_doc()))
    assert k.guard_gaps(m, ["AKE"])["no-entry"] == ["AKE"]


def test_bdx_is_eligible_and_has_a_keyword():
    """T160 found BDX eligible but missing; #171 added a qualified term."""
    m = k.load()
    if "BDX" in discovery.eligible_discovery_symbols():
        assert k.keyword_status(m, "BDX") in ("topic", "term")
    assert m.entries["BDX"]["term"] == "beldex crypto"


@pytest.mark.parametrize("entry,status", [
    ({"topic": "/m/0abc", "label": "X"}, "topic"),
    ({"term": "Xcoin", "label": "X"}, "term"),
    (NO_KW, "no-keyword"),
])
def test_keyword_status_kinds(entry, status):
    m = k.KeywordMap(**k.validate(_doc(XC=entry)))
    assert k.keyword_status(m, "XC") == status
    assert k.keyword_status(m, "OTHER") == "no-entry"


def test_name_risk_term_status():
    m = k.KeywordMap(**k.validate(_doc(LINK={"term": "Chainlink", "label": "Chainlink"},
                                       SOL={"term": "solana crypto", "label": "Solana"})))
    assert k.keyword_status(m, "LINK") == "skipped-unqualified"
    assert k.keyword_status(m, "SOL") == "term"


def test_keyword_status_without_a_map_is_bad_file():
    assert k.keyword_status(None, "SOL") == "bad-file"


def test_coverage_counts_no_keyword_apart_from_topic_and_term():
    m = k.KeywordMap(**k.validate(_doc(A={"topic": "/m/0a", "label": "A"}, B={"term": "Bcoin", "label": "B"},
                                       C=NO_KW, LINK={"term": "Chainlink", "label": "L"})))
    cov = k.coverage(m, ["A", "B", "C", "D", "LINK"])
    assert cov.counts == {"topic": 1, "term": 1, "keyword-missing": 3}
    assert cov.with_keyword == 2 and cov.eligible == 5
    assert cov.missing == [("C", "no-keyword"), ("D", "no-entry"), ("LINK", "skipped-unqualified")]


def test_coverage_with_bad_file_counts_every_coin_missing():
    cov = k.coverage(None, ["A", "B"])
    assert cov.with_keyword == 0 and cov.missing == [("A", "bad-file"), ("B", "bad-file")]


def test_safe_load_names_symbols_that_are_not_placed(tmp_path):
    p = tmp_path / "kw.json"
    p.write_text('{"_anchor": {"term": "Bitcoin", "label": "B"}, "SOL": {"term": "Solana", "label": "S"},'
                 ' "OLD": {"term": "Old Coin", "label": "O"}}')
    m, reason = k.safe_load(p, placed_symbols={"SOL"})
    assert reason == "" and m.not_placed == ["OLD"]
    assert m.warnings == ["keywords: OLD is not a placed coin"]


def test_safe_load_without_placed_symbols_names_none():
    m, _ = k.safe_load(placed_symbols=None)
    assert m.not_placed == [] and m.warnings == []


def test_shipped_file_names_keys_that_are_not_eligible():
    eligible = discovery.eligible_discovery_symbols()
    m, reason = k.safe_load(placed_symbols=eligible)
    assert reason == ""
    assert m.not_placed == sorted(set(m.entries) - set(eligible))
    assert m.warnings == [f"keywords: {s} is not a placed coin" for s in m.not_placed]
