"""Stage 2 (D-30): the pure selection rule over a campaign coin record. No network, no file writes."""
from __future__ import annotations

import json

import pytest

from api.data.attention import trends_select as sel
from api.tests.trends_fixtures import block_network


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    block_network(monkeypatch)


def m(verdict="ok", zero=0.0, distinct=20, corr=None, spike=False, moves_alone=(), reason="n/a: no stored volume"):
    return {"verdict": verdict, "clean": False, "zero_pct": zero, "distinct": distinct, "identity_corr": corr,
            "identity_reason": None if corr is not None else reason, "median": 10, "spike": spike,
            "moves_alone": list(moves_alone)}


def g(terms, metrics=None, kind="variant", outcome="ok"):
    terms = [terms] if isinstance(terms, str) else list(terms)
    return "|".join(terms), {"terms": terms, "kind": kind, "outcome": outcome, "metrics": metrics,
                             "loader_flags": {t: "loader-valid" for t in terms}}


def coin(*groups):
    return {"groups": dict(groups)}


TERM = {"term": "akedo crypto", "label": "Akedo"}
NONE = frozenset()


def test_empty_quiet_and_spike_groups_are_never_chosen():
    """AC2: empty or quiet (not usable), and a one-term spike, are refused."""
    c = coin(g("akedo crypto", m("too-little-interest", zero=100, distinct=1)),
             g("ake crypto", m(spike=True)),
             g("akedo coin", None, outcome="frame-rejected: gap"))
    s = sel.select("AKE", c, TERM, NONE)
    assert s.verdict == "needs-owner" and s.term is None
    why = dict(s.others)
    assert "not usable" in why["[akedo crypto]"] and "one-term spike" in why["[ake crypto]"]
    assert "frame rejected" in why["[akedo coin]"]


def test_one_day_spike_in_a_bundle_never_becomes_the_signal():
    """AC1, AC2: a bundle never becomes the signal, even with a one-term spike or the best numbers."""
    c = coin(g(["x crypto", "x coin"], m(zero=0, spike=True), kind="bundle"))
    s = sel.select("XX", c, {"term": "x crypto", "label": "X"}, NONE)
    assert s.verdict == "needs-owner" and s.term is None


def test_bundle_present_never_changes_the_term():
    """AC1: the chosen keyword is one term; the bundle only adds flags."""
    base = coin(g("akedo crypto", m(zero=5)), g("ake crypto", m(zero=10)))
    with_bundle = coin(g("akedo crypto", m(zero=5)), g("ake crypto", m(zero=10)),
                       g(["akedo crypto", "ake crypto"], m(zero=0, distinct=99), kind="bundle"))
    a, b = sel.select("AKE", base, TERM, NONE), sel.select("AKE", with_bundle, TERM, NONE)
    assert a.term == b.term == "akedo crypto" and a.verdict == b.verdict == "use-term"


def test_rising_but_gappy_loses_to_steady_but_complete():
    """AC3: fewest zero days wins; rising/clean plays no part."""
    gappy = m(zero=30, distinct=40)
    gappy["clean"] = True
    c = coin(g("akedo coin", gappy), g("akedo token", m(zero=2, distinct=10)))
    s = sel.select("AKE", c, TERM, NONE)   # the current term was not tested: a change is proposed
    assert s.verdict == "use-term" and s.term == "akedo token"


def test_ties_break_on_distinct_values_then_volume():
    c = coin(g("a1 crypto", m(zero=2, distinct=10)), g("a2 crypto", m(zero=2, distinct=12)))
    assert sel.select("AKE", c, TERM, NONE).term == "a2 crypto"
    c = coin(g("a1 crypto", m(zero=2, distinct=10, corr=0.1)), g("a2 crypto", m(zero=2, distinct=10, corr=0.6)),
             g("a3 crypto", m(zero=2, distinct=10)))
    assert sel.select("AKE", c, TERM, NONE).term == "a2 crypto"


def test_current_keyword_kept_when_it_is_a_candidate_even_against_a_bare_ticker():
    c = coin(g("akedo crypto", m(zero=20)), g("AKE", m(zero=0), kind="bare-ticker"))
    s = sel.select("AKE", c, TERM, NONE)
    assert s.verdict == "use-term" and s.term == "akedo crypto" and "current keyword" in " ".join(s.reasons)


def test_topic_first_when_the_current_keyword_is_not_a_candidate():
    c = coin(g("akedo crypto", m("too-little-interest")), g("/g/11abc", m(zero=9)), g("ake coin", m(zero=0)))
    s = sel.select("AKE", c, TERM, NONE)
    assert s.verdict == "use-topic" and s.term == "/g/11abc"


@pytest.mark.parametrize("corr,flag", [(None, "unchecked (no volume)"), (0.05, "unconfirmed (volume)"),
                                       (0.7, "agrees (volume)")])
def test_volume_flags(corr, flag):
    """AC4: with stored volume a low correlation is unconfirmed; without volume it is unchecked, never confirmed."""
    s = sel.select("AKE", coin(g("akedo crypto", m(corr=corr))), TERM, NONE)
    assert flag in s.flags and s.verdict == "use-term"


@pytest.mark.parametrize("bundles,flag", [
    ([g(["akedo crypto", "ake crypto"], m(moves_alone=[]), kind="bundle")], "agrees (variants)"),
    ([g(["akedo crypto", "ake crypto"], m(moves_alone=["akedo crypto"]), kind="bundle")], "unconfirmed (variants)"),
    ([], "unchecked (no variants)"),
    ([g(["akedo crypto", "ake crypto"], m("too-little-interest"), kind="bundle")], "unchecked (no variants)"),
])
def test_variant_flags_only_warn(bundles, flag):
    """AC5, D4: the variant check warns and never rejects."""
    s = sel.select("AKE", coin(g("akedo crypto", m()), *bundles), TERM, NONE)
    assert flag in s.flags and s.verdict == "use-term" and s.term == "akedo crypto"


AMB = frozenset({"SKY"})


def test_ambiguous_coin_topic_is_used():
    c = coin(g("sky crypto", m()), g("/g/11sky", m(zero=5)))
    s = sel.select("SKY", c, {"term": "sky crypto", "label": "Sky"}, AMB)
    assert s.verdict == "use-topic" and s.term == "/g/11sky"


def test_ambiguous_coin_approved_term_is_used():
    s = sel.select("SKY", coin(g("sky crypto", m())),
                   {"term": "sky crypto", "label": "Sky", "approved": "sky crypto"}, AMB)
    assert s.verdict == "use-term" and s.term == "sky crypto"


def test_ambiguous_coin_unapproved_term_needs_approval_and_bare_names_never_count():
    c = coin(g("sky crypto", m(zero=3)), g("sky", m(zero=0), kind="bare-name"), g("SKY", m(zero=0), kind="bare-ticker"))
    s = sel.select("SKY", c, {"term": "sky crypto", "label": "Sky"}, AMB)
    assert s.verdict == "needs-approval" and s.term == "sky crypto"
    why = dict(s.others)
    assert "ambiguous" in why["[sky]"] and "ambiguous" in why["[SKY]"]


def test_ambiguous_term_approved_for_another_coin_does_not_count():
    """AC6: an approval is per coin: SKY's entry approves nothing, another coin's approval is not read."""
    s = sel.select("SKY", coin(g("sky crypto", m())), {"term": "sky crypto", "label": "Sky"}, AMB)
    assert s.verdict == "needs-approval"
    s = sel.select("SKY", coin(g("sky coin", m())),
                   {"term": "sky crypto", "label": "Sky", "approved": "sky crypto"}, AMB)
    assert s.verdict == "needs-approval" and s.term == "sky coin"


def test_no_passing_term_is_needs_owner_with_reason():
    s = sel.select("AKE", coin(g("akedo crypto", m("too-little-interest"))), TERM, NONE)
    assert s.verdict == "needs-owner" and "too-little-interest" in s.reasons
    s = sel.select("AKE", coin(g("akedo crypto", None, outcome="frame-rejected: gap")), TERM, NONE)
    assert s.verdict == "needs-owner" and "frame-rejected" in s.reasons
    s = sel.select("AKE", coin(g("akedo crypto", m("something-else"))), TERM, NONE)
    assert s.verdict == "needs-owner" and "no usable group" in s.reasons


def test_waking_up():
    s = sel.select("AKE", coin(g("akedo crypto", m("quiet-then-surge"))), TERM, NONE)
    assert s.verdict == "waking-up" and s.term is None


def test_listed_coin_missing_from_state_is_untested():
    """AC15: STABLE was not in the campaign: untested, never use-term."""
    s = sel.select("STABLE", None, {"term": "stable chain", "label": "Stable"}, frozenset({"STABLE"}))
    assert s.verdict == "untested" and s.term is None
    s = sel.select("AKE", coin(g("akedo crypto", None, outcome="request-failed: x")), TERM, NONE)
    assert s.verdict == "untested"


@pytest.mark.parametrize("metrics", [{"verdict": "ok"}, {"verdict": "ok", "zero_pct": "x", "distinct": 3},
                                     "garbage", {"verdict": "ok", "zero_pct": 1, "distinct": 3,
                                                 "identity_corr": "no"}])
def test_malformed_metrics_are_no_candidate_never_a_crash(metrics):
    key, rec = g("akedo crypto", m())
    rec["metrics"] = metrics
    s = sel.select("AKE", {"groups": {key: rec, "bad": "x"}}, TERM, NONE)
    assert s.verdict == "needs-owner" and s.term is None


def test_malformed_coin_record_is_untested():
    assert sel.select("AKE", {"groups": "x"}, TERM, NONE).verdict == "untested"
    assert sel.select("AKE", "x", TERM, NONE).verdict == "untested"


def test_proposal_never_contains_approved_and_filters_invalid():
    props = sel.proposal({
        "AKE": (sel.Selection("use-term", "ake crypto", (), (), ()), TERM),
        "SOL": (sel.Selection("use-topic", "/g/11sol", (), (), ()), {"term": "sol crypto", "label": "Solana"}),
        "SKY": (sel.Selection("needs-approval", "sky coin", (), (), ()), {"term": "sky crypto", "label": "Sky"}),
        "KEEP": (sel.Selection("use-term", "keep crypto", (), (), ()), {"term": "keep crypto", "label": "K"}),
        "BAD": (sel.Selection("use-term", "bad|term;rm", (), (), ()), {"term": "bad crypto", "label": "B"}),
    })
    assert props == {"AKE": {"term": "ake crypto", "label": "Akedo"}, "SOL": {"topic": "/g/11sol", "label": "Solana"}}
    assert "approved" not in json.dumps(props)


def test_module_is_pure():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(sel))
    names = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not ({"httpx", "requests", "pytrends", "socket", "open"} & (names | mods))
    assert "open(" not in inspect.getsource(sel) and "write" not in inspect.getsource(sel)
