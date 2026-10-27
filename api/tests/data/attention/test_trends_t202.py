"""T202: quiet-then-surge ordering and labels, adaptive candidate depth. Pure: no network."""
from __future__ import annotations

import string
from datetime import date, timedelta

import pytest

from api.data.attention import trends
from api.data.attention import trends_candidates as c
from api.data.attention import trends_groups as g

OK, SURGE, LITTLE = "ok", trends.QUIET_THEN_SURGE, trends.TOO_LITTLE_INTEREST


def rv(verdict, clean=False, zero=0.0, distinct=5, corr=None):
    return g.rank_values(verdict, clean, zero, distinct, corr)


def test_rank_class_order_clean_usable_surge_little_other():
    order = [rv(OK, True, 90, 1), rv(OK, False, 0, 99), rv(SURGE, False, 90, 1), rv(LITTLE, False, 0, 99),
             rv("something-else", False, 0, 99)]
    assert order == sorted(order) and len(set(order)) == 5
    assert rv(SURGE, False, 50, 1) < rv(LITTLE, False, 0, 99)      # surge beats little interest whatever the zeros
    assert rv(OK, False, 99, 1) < rv(SURGE, False, 0, 99)          # any usable group beats a surge
    assert rv(SURGE, False, 10, 1) < rv(SURGE, False, 20, 9)       # inside a class the old tie-breaks hold


def test_rank_key_surge_group_beats_too_little():
    d0 = date(2026, 1, 1)
    dates = [d0 + timedelta(days=i) for i in range(100)]
    surge = g.analyze({"a": [0.0] * 50 + [1.0] * 43 + [10.0] * 7}, dates)
    little = g.analyze({"a": [0.0] * 100}, dates)
    assert surge.verdict == SURGE and little.verdict == LITTLE
    assert sorted([little, surge], key=g.rank_key) == [surge, little]


def test_label_marks_surge_as_waking_up_only():
    assert g.verdict_label(SURGE) == "quiet-then-surge (waking up)"
    assert g.verdict_label(OK) == OK and g.verdict_label(LITTLE) == LITTLE


# --- depth ---

ENTRY = {"term": "akedo crypto", "label": "Akedo"}


def kinds(groups):
    return [x.kind for x in groups]


def test_defaults_are_4_weak_2_usable():
    assert c.DEFAULT_MAX_GROUPS == 4 and c.DEFAULT_MAX_USABLE == 2


def test_usable_baseline_gets_baseline_and_bundle_only():
    groups = c.candidate_groups("AKE", ENTRY, query_name="Akedo", coingecko_id="akedo", usable=True)
    assert kinds(groups) == ["baseline", "bundle"]
    assert groups[1].terms[0] == "akedo crypto" and len(groups[1].terms) > 1


def test_usable_depth_one_is_the_baseline():
    groups = c.candidate_groups("AKE", ENTRY, query_name="Akedo", coingecko_id="akedo", usable=True, max_usable=1)
    assert kinds(groups) == ["baseline"]


def test_usable_topic_baseline_bundles_variants_only():
    groups = c.candidate_groups("AAVE", {"topic": "/g/11w1qyc8h6", "label": "Aave"}, query_name="Aave",
                                coingecko_id="aave", usable=True)
    assert kinds(groups) == ["baseline", "bundle"] and "/g/" not in "".join(groups[1].terms)


def test_usable_without_a_bundle_falls_back_to_the_best_variant():
    groups = c.candidate_groups("XYZ", {"term": "xyz crypto"}, usable=True)
    assert len(groups) <= 2 and groups[0].kind == "baseline"


def test_weak_non_name_risk_gets_four_including_both_bare_candidates():
    groups = c.candidate_groups("AKE", ENTRY, query_name="Akedo", coingecko_id="akedo")
    assert len(groups) == 4 and kinds(groups)[0] == "baseline"
    assert "bare-name" in kinds(groups) and "bare-ticker" in kinds(groups)
    assert all(x.note == c.NEEDS_QUALIFIER for x in groups if x.kind.startswith("bare"))


def test_weak_name_risk_gets_four_qualified_never_bare():
    for sym in sorted(trends.NAME_RISK_SYMBOLS):
        groups = c.candidate_groups(sym, {"term": f"{sym.lower()} crypto", "label": sym.title()},
                                    query_name=sym.title(), coingecko_id=sym.lower())
        assert 1 <= len(groups) <= 4
        assert not any(x.kind.startswith("bare") for x in groups), sym
    big = c.candidate_groups("SOL", {"term": "solana crypto", "label": "Solana"}, query_name="Solana",
                             coingecko_id="solana")
    assert len(big) == 4


def test_weak_ceiling_is_the_argument_and_missing_baseline_is_weak():
    assert len(c.candidate_groups("AKE", ENTRY, query_name="Akedo", coingecko_id="akedo", max_groups=2)) == 2
    groups = c.candidate_groups("AKE", None, query_name="Akedo", coingecko_id="akedo")
    assert "baseline" not in kinds(groups) and len(groups) == 4 and "bare-ticker" in kinds(groups)


def test_request_total_for_78_coins_stays_under_the_bound():
    names = ["".join(p) for p in zip(*[iter(string.ascii_lowercase * 4)] * 3)][:78]
    risky = sorted(trends.NAME_RISK_SYMBOLS)
    weak = usable = total = 0
    for i, n in enumerate(names):
        sym = risky[i] if i < len(risky) else n.upper() + "X"
        nm = (sym.lower() if sym in trends.NAME_RISK_SYMBOLS else n + "one")
        is_usable = i % 3 == 0
        groups = c.candidate_groups(sym, {"term": f"{nm} crypto", "label": nm.title()}, query_name=nm.title(),
                                    coingecko_id=nm, usable=is_usable)
        assert len(groups) <= (2 if is_usable else 4), sym
        if sym in trends.NAME_RISK_SYMBOLS:
            assert not any(x.kind.startswith("bare") for x in groups)
        weak += not is_usable
        usable += is_usable
        total += len(groups)
    assert weak + usable == 78 and total <= 4 * weak + 2 * usable
    assert total > 2 * 78      # weak coins really do get the deeper test
