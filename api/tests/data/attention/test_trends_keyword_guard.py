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


# Reviewed Discovery eligible set (78 coins on the 2026-10-24 snapshot, BDX included). Pinned so a daily snapshot
# commit cannot turn CI red; update it on purpose when the universe changes. The live gap is reported, not failed:
# `gap_report`, the runner's no-keyword reasons and the Sources "Trends keyword: N of M" line.
PINNED_ELIGIBLE = (
    "AAVE", "ADA", "AERO", "AKE", "ALGO", "APT", "ARB", "ASTER", "ATOM", "AVAX", "BCH", "BDX", "BGB", "BNB", "BTC",
    "BTW", "CAKE", "CC", "CRO", "DASH", "DOGE", "DOT", "ENA", "ETC", "ETH", "ETHFI", "FIL", "GRAM", "GT", "HBAR",
    "HTX", "HYPE", "ICP", "INJ", "JST", "JUP", "KAS", "KCS", "LEO", "LINK", "LIT", "LTC", "M", "MNT", "MORPHO",
    "NEAR", "NEXO", "NIGHT", "OKB", "ONDO", "PAXG", "PEARL", "PEPE", "PI", "POL", "PUMP", "QNT", "RAIN", "RENDER",
    "SHIB", "SKY", "SOL", "SUI", "TAO", "TRX", "UNI", "VET", "VVV", "WBT", "WLD", "WLFI", "XAUT", "XDC", "XLM",
    "XMR", "XRP", "ZEC", "ZRO",
)
# Stage 2 (D-30, Q1 and the second approval round of 01-11-26): the ambiguous coins whose term the owner has not
# approved are not pulled. STABLE is listed too but is not in the pinned eligible set.
UNAPPROVED_PINNED = ["M", "SKY"]
SHIPPED_GAPS = {"no-entry": [], "no-keyword": [], "skipped-unqualified": UNAPPROVED_PINNED,
                "allowlist-has-keyword": []}
STAGE2_STOPPED = {"SKY", "M", "STABLE"}


def _ambiguous_doc(**coins) -> dict:
    return {**_doc(**coins), "_ambiguous": ["LINK"]}


def test_pinned_eligible_set_is_the_reviewed_one():
    assert len(PINNED_ELIGIBLE) == len(set(PINNED_ELIGIBLE)) == 78 and "BDX" in PINNED_ELIGIBLE


def test_every_pinned_discovery_coin_has_a_trends_keyword():
    gaps = k.guard_gaps(k.load(), PINNED_ELIGIBLE)
    assert gaps == SHIPPED_GAPS, f"eligible Discovery coins without a Google Trends keyword: {gaps}"


def _pulled_before_stage2(km, symbol: str) -> bool:
    """The pre-stage-2 rule (T125 constant): a listed coin's term was pulled when it held a qualifier word."""
    from api.data.attention import trends
    t125 = {"TRX", "ONDO", "MORPHO", "ICP", "SHIB", "PEPE", "BNB", "CRO", "HBAR", "LINK", "APT", "SOL"}
    e = km.entries.get(symbol) or {}
    if "topic" in e:
        return True
    if "term" not in e:
        return False
    return symbol not in t125 or trends.is_qualified_term(e["term"])


def test_stage2_exactly_the_three_unapproved_coins_stop_being_pulled():
    """E7: read from the shipped file before (old rule) and after (stage-2 rule)."""
    m = k.load()
    changed = {s for s in m.entries
               if _pulled_before_stage2(m, s) != (k.keyword_status(m, s) in ("topic", "term"))}
    assert changed == STAGE2_STOPPED
    assert all(k.keyword_status(m, s) == "skipped-unqualified" for s in changed)


def test_live_snapshot_gap_is_reported_never_failed():
    """A new live coin without a keyword only shows in the report line; the live set is never asserted gap-free."""
    line = k.gap_report(k.load(), [*PINNED_ELIGIBLE, "NEWCOIN"])
    assert line == ("trends keyword: 76 of 79 eligible coins; no keyword: "
                    + ", ".join(f"{s} (skipped-unqualified)" for s in UNAPPROVED_PINNED) + ", NEWCOIN (no-entry)")
    assert k.gap_report(k.load(), discovery.eligible_discovery_symbols()).startswith("trends keyword: ")
    assert k.gap_report(None, ["A"]) == "trends keyword: 0 of 1 eligible coins; no keyword: A (bad-file)"
    assert k.gap_report(k.load(), ["BTC"]) == "trends keyword: 1 of 1 eligible coins"


def test_guard_lists_the_exact_missing_symbols(monkeypatch):
    monkeypatch.setattr(k, "UNIDENTIFIED_TICKERS", frozenset({"AKE"}))   # T192: the shipped list is empty
    m = k.KeywordMap(**k.validate(_ambiguous_doc(
        SOL={"topic": "/m/0sol", "label": "Solana"}, LINK={"term": "Chainlink", "label": "Chainlink"},
        ZZZ=NO_KW, AKE=NO_KW)))
    gaps = k.guard_gaps(m, ["SOL", "NEWCOIN", "LINK", "ZZZ", "AKE"])
    assert gaps == {"no-entry": ["NEWCOIN"], "no-keyword": ["ZZZ"], "skipped-unqualified": ["LINK"],
                    "allowlist-has-keyword": []}


def test_guard_fails_when_an_allowlisted_ticker_gains_a_keyword(monkeypatch):
    monkeypatch.setattr(k, "UNIDENTIFIED_TICKERS", frozenset({"AKE"}))
    m = k.KeywordMap(**k.validate(_doc(AKE={"term": "ake crypto", "label": "Ake"})))
    assert k.guard_gaps(m, ["AKE"])["allowlist-has-keyword"] == ["AKE"]
    # also when it is not eligible today: the list must shrink once the owner names the coin
    assert k.guard_gaps(m, [])["allowlist-has-keyword"] == ["AKE"]


def test_empty_allowlist_makes_a_no_keyword_entry_a_gap():
    m = k.KeywordMap(**k.validate(_doc(AKE=NO_KW)))
    assert k.guard_gaps(m, ["AKE"])["no-keyword"] == ["AKE"]


def test_allowlist_is_the_named_unidentified_tickers():
    assert k.UNIDENTIFIED_TICKERS == frozenset()   # T192: the owner named all seven


def test_allowlisted_ticker_without_entry_is_still_a_gap(monkeypatch):
    monkeypatch.setattr(k, "UNIDENTIFIED_TICKERS", frozenset({"AKE"}))
    m = k.KeywordMap(**k.validate(_doc()))
    assert k.guard_gaps(m, ["AKE"])["no-entry"] == ["AKE"]


def test_t195_pyth_is_outside_the_pinned_set_and_only_warns():
    """PYTH is not narrative-placed or Discovery-eligible: it only shows as a 'not a placed coin' warning."""
    m, reason = k.safe_load(placed_symbols=PINNED_ELIGIBLE)
    assert reason == "" and "PYTH" in m.not_placed and "PYTH" not in PINNED_ELIGIBLE


def test_bdx_is_eligible_and_has_a_keyword():
    """T160 found BDX eligible but missing; #171 added a qualified term."""
    m = k.load()
    assert "BDX" in PINNED_ELIGIBLE and k.keyword_status(m, "BDX") == "term"
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
    m = k.KeywordMap(**k.validate(_ambiguous_doc(LINK={"term": "Chainlink", "label": "Chainlink"},
                                       SOL={"term": "solana crypto", "label": "Solana"})))
    assert k.keyword_status(m, "LINK") == "skipped-unqualified"
    assert k.keyword_status(m, "SOL") == "term"


def test_keyword_status_without_a_map_is_bad_file():
    assert k.keyword_status(None, "SOL") == "bad-file"


def test_coverage_counts_no_keyword_apart_from_topic_and_term():
    m = k.KeywordMap(**k.validate(_ambiguous_doc(A={"topic": "/m/0a", "label": "A"}, B={"term": "Bcoin", "label": "B"},
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
    """Pinned set: the live set would make safe_load fail on any new snapshot coin without an entry (T186)."""
    m, reason = k.safe_load(placed_symbols=PINNED_ELIGIBLE)
    assert reason == ""
    assert m.not_placed == sorted(set(m.entries) - set(PINNED_ELIGIBLE))
    assert m.warnings == [f"keywords: {s} is not a placed coin" for s in m.not_placed]


def test_new_live_coin_without_keyword_fails_no_shipped_data_test(tmp_path, monkeypatch):
    """T186 regression: a bot snapshot that adds an eligible coin with no keyword must not turn CI red. Every
    argument-free test that reads the shipped files (this module and test_trends_keywords) is re-run against a
    snapshot copy with such a coin; the full `pytest api` run against it is in the T180 report."""
    import inspect
    import json
    import shutil

    from api.data import cache
    from api.tests.data.attention import test_trends_keywords

    src = cache.CACHE_ROOT / "attention" / "universe.json"
    (tmp_path / "attention").mkdir()
    doc = json.loads(src.read_text())
    doc["snapshots"][-1]["coins"].insert(0, {"id": "zz-fake", "symbol": "ZZFAKE", "market_cap": 9e12,
                                             "volume_24h": 1e9})
    (tmp_path / "attention" / "universe.json").write_text(json.dumps(doc))
    shutil.copy(cache.CACHE_ROOT / "attention" / "categories.json", tmp_path / "attention" / "categories.json")
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
    assert "ZZFAKE" in discovery.eligible_discovery_symbols()
    assert "ZZFAKE (no-entry)" in k.gap_report(k.load(), discovery.eligible_discovery_symbols())
    me = inspect.currentframe().f_code.co_name
    ran = []
    for mod in (__import__(__name__, fromlist=["_"]), test_trends_keywords):
        for name, fn in vars(mod).items():
            if name.startswith("test_") and name != me and inspect.isfunction(fn) \
                    and not inspect.signature(fn).parameters:
                fn()
                ran.append(name)
    assert "test_shipped_file_names_keys_that_are_not_eligible" in ran and len(ran) > 20
