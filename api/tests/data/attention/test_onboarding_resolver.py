"""T223 O4: pure resolver checks (AC8-AC12). Fakes only; nothing here can reach the network."""
from __future__ import annotations

import pytest

from api.data.attention import onboarding_resolver as res
from api.data.attention.onboarding_settings import Settings

S = Settings()


def cand(mid, title, type_="Cryptocurrency"):
    return {"mid": mid, "title": title, "type": type_}


def page(canonical="Foo Network", type_="standard", extract="Foo Network is a blockchain protocol. More.",
         description="cryptocurrency"):
    return {"canonical": canonical, "type": type_, "extract": extract, "description": description}


# --- Trends (AC8, AC10-AC12) ---

def test_strict_trends_rule_applies_with_evidence():
    pick = res.trends_pick("FOO", "Foo Network", [cand("/g/foo", "Foo Network"), cand("/m/x", "Foo", "Song")],
                           taken_topics=set())
    assert pick.action == "candidate" and pick.value == {"topic": "/g/foo", "label": "Foo Network"}
    v = res.trends_confirm(pick, series_state="ok", corr=0.6, overlap_days=70, settings=S)
    assert v.action == "applied" and v.value["topic"] == "/g/foo"
    assert v.evidence["volume_days"] == 70 and v.evidence["correlation"] == 0.6


@pytest.mark.parametrize("kw, reason", [
    ({"series_state": "ok", "corr": 0.9, "overlap_days": 20}, "volume history 20 of 66 days"),
    ({"series_state": "ok", "corr": None, "overlap_days": 0}, "volume history 0 of 66 days"),
    ({"series_state": "ok", "corr": 0.05, "overlap_days": 90}, "does not track this coin's volume"),
    ({"series_state": "unavailable", "corr": 0.9, "overlap_days": 90}, "trends series unavailable"),
])
def test_strict_rule_falls_to_pending(kw, reason):
    pick = res.trends_pick("FOO", "Foo", [cand("/g/foo", "Foo")], taken_topics=set())
    v = res.trends_confirm(pick, settings=S, **kw)
    assert (v.action, v.reason) == ("pending", reason) and v.value is None


@pytest.mark.parametrize("cands, reason", [
    ([cand("/g/a", "FOO")], "lead only (ticker-title)"),
    ([cand("/g/a", "Foo Chain (cryptocurrency)")], "lead only (bracket)"),
    ([cand("/g/a", "Foo Chain Token")], "lead only (contained)"),
    ([cand("/g/a", "Foo Chain"), cand("/g/b", "Foo Chain", "Coin")], "several equally likely entities"),
])
def test_leads_and_several_entities_go_to_pending(cands, reason):
    v = res.trends_pick("FOO", "Foo Chain", cands, taken_topics=set())
    assert (v.action, v.reason) == ("pending", reason) and v.evidence["candidates"]


def test_name_from_id_and_taken_topic_go_to_pending():
    assert res.trends_pick("FOO", "Foo", [cand("/g/a", "Foo")], taken_topics=set(), name_from_id=True).reason == (
        "name from CoinGecko id")
    assert res.trends_pick("FOO", "Foo", [cand("/g/a", "Foo")], taken_topics={"/g/a"}).reason == (
        "topic already used by another symbol")


@pytest.mark.parametrize("cands, name, reason", [
    (None, "Foo", "no Google entity for the name"), ([], "Foo", "no Google entity for the name"),
    ([cand("/g/a", "Foo", "Song")], "Foo", "no cryptocurrency entity with the exact name"),
    ([cand("/g/a", "Foo")], None, "no name in the snapshot"),
])
def test_no_candidate_is_none_with_a_reason_never_zero(cands, name, reason):
    v = res.trends_pick("FOO", name, cands, taken_topics=set())
    assert (v.action, v.reason, v.value) == ("none", reason, None)


def test_no_automatic_term_is_ever_proposed():
    """The ambiguity list is never bypassed: only topics can be applied, so an `_ambiguous` coin gets no term."""
    pick = res.trends_pick("FOO", "Foo", [cand("/g/foo", "Foo")], taken_topics=set())
    v = res.trends_confirm(pick, series_state="ok", corr=0.9, overlap_days=90, settings=S)
    assert set(v.value) == {"topic", "label"}


# --- Wikipedia (AC9) ---

def wiki(p, taken=None, days=90, name="Foo Network", sym="FOO"):
    return res.wiki_verdict(sym, name, p, taken=taken or {}, pageview_days=days, min_days=S.wiki_min_days)


def test_wikipedia_pass():
    v = wiki(page())
    assert v.action == "applied" and v.value == {"title": "Foo Network"}


@pytest.mark.parametrize("p, kw, reason", [
    (page(canonical="Foo (company)"), {}, "redirect to another title"),
    (page(type_="disambiguation"), {}, "disambiguation page"),
    (page(extract="Bar is a river in France. Foo Network blockchain."), {}, "name not in the first sentence"),
    (page(canonical="Foo", extract="Foo is a band.", description="band"), {"name": "Foo"}, "no crypto terms"),
    (page(canonical="Foo", extract="Foo is a cointreau brand.", description="drinks"), {"name": "Foo"},
     "no crypto terms"),
    (page(), {"taken": {"foo network": "BAR"}}, "title already assigned to BAR"),
    (page(), {"days": 5}, "pageviews 5 of 30 days"),
])
def test_wikipedia_refusals_wait_for_the_owner(p, kw, reason):
    v = wiki(p, **kw)
    assert (v.action, v.reason) == ("pending", reason) and v.evidence["title"]


def test_wikipedia_symbol_in_first_sentence_counts_and_no_page_is_none():
    assert wiki(page(extract="FOO is a token on a blockchain.")).action == "applied"
    assert wiki(None).action == "none" and wiki(page(), name=None).reason == "no name in the snapshot"
    assert wiki(page(type_="no-extract")).action == "none"


def test_merge_wiki_owner_wins_and_duplicates_drop():
    owner = {"BTC": "Bitcoin", "NUL": None}
    merged, dropped = res.merge_wiki(owner, {"entries": {
        "BTC": {"title": "Other"}, "NUL": {"title": "X"}, "NEW": {"title": "New Coin"}, "DUP": {"title": "bitcoin"},
        "bad sym": {"title": "Y"}, "BAD": {"title": "\x00"}, "BAD2": "x"}})
    assert merged == {"BTC": "Bitcoin", "NUL": None, "NEW": "New Coin"}
    assert dict(dropped) == {"BTC": "owner entry wins", "NUL": "owner entry wins", "DUP": "title already used",
                             "bad sym": "invalid entry", "BAD": "invalid entry", "BAD2": "invalid entry"}
    assert res.merge_wiki(owner, None) == (owner, []) and res.merge_wiki(owner, {"entries": 3}) == (owner, [])


# --- Reddit / X (AC10) ---

def test_reddit_x_is_cashtag_only_and_bad_names_wait():
    assert res.reddit_x_verdict("FOO", "Foo Network").value == {"name": "Foo Network", "cashtag_only": True}
    for bad in ("Fōō", "x" * 41, "Foo\u202e", "$FOO"):
        assert res.reddit_x_verdict("FOO", bad).action == "pending"
    assert res.reddit_x_verdict("FOO", None).action == "none"
