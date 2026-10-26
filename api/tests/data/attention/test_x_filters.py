"""W8d1 AC43, AC44: X post-filters, exclusion counts, author quality, engagement and views. Pure; no network."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import pytest

from api.data.attention import web_queries as wq
from api.data.attention import x_filters as xf

DAY = date(2026, 10, 20)
NOON = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
OLD = datetime(2024, 1, 1, tzinfo=timezone.utc)
SOL = xf.Coin("SOL", "Solana")
POLICY = xf.FilterPolicy()


def user(uid: int = 1, **over) -> xf.XUser:
    base = {"id": uid, "created": OLD, "followers": 500, "statuses": 900, "profile_image_url": "https://img/x.jpg",
            "protected": False}
    return xf.XUser(**{**base, **over})


_ids = iter(range(10_000, 10**9))


def tw(text: str = "gm $SOL", *, uid: int = 1, when: datetime = NOON, **over) -> xf.Tweet:
    base = {"id": next(_ids), "date": when, "text": text, "user": user(uid), "lang": "en", "cashtags": ("SOL",)}
    return xf.Tweet(**{**base, **over})


def run(tweets, coin=SOL, policy=POLICY) -> xf.FilterResult:
    return xf.filter_tweets(tweets, coin, DAY, policy)


def test_retweets_and_replies_excluded_by_fields():
    r = run([tw("a"), tw("b", retweeted_id=5), tw("c", reply_to_id=6), tw("d", uid=2)])
    assert [t.text for t in r.counted] == ["a", "d"]
    assert r.exclusions["retweet"] == 1 and r.exclusions["reply"] == 1


def test_lang_policy_default_en_and_override_and_any():
    tweets = [tw("a", lang="en"), tw("b", lang="es", uid=2), tw("c", lang="EN", uid=3)]
    assert POLICY.lang == "en"
    assert [t.text for t in run(tweets).counted] == ["a", "c"]
    assert run(tweets).exclusions["lang"] == 1
    assert [t.text for t in run(tweets, policy=xf.FilterPolicy(lang="es")).counted] == ["b"]
    assert len(run(tweets, policy=xf.FilterPolicy(lang="")).counted) == 3
    cfg = wq.load().config
    assert xf.FilterPolicy.from_config(cfg, {"name": "Solana"}).lang == "en"
    assert xf.FilterPolicy.from_config(cfg, {"name": "Solana", "x_lang": "ja"}).lang == "ja"
    assert xf.FilterPolicy.from_config(cfg, {"name": "Solana", "x_lang": ""}).lang == ""


def test_cashtag_field_matching():
    r = run([tw("no tag but Solana is up", cashtags=()), tw("tag only", cashtags=("SOL",), uid=2),
             tw("other coin", cashtags=("ETH",), uid=3), tw("lowercase solana rally", cashtags=(), uid=4)])
    assert [t.text for t in r.counted] == ["no tag but Solana is up", "tag only", "lowercase solana rally"]
    assert r.exclusions["no_coin_match"] == 1


def test_cashtags_without_dollar_matching_case_folded():
    assert xf.cashtag_matches(("sol",), "SOL")
    assert xf.cashtag_matches(("$Sol",), "SOL")
    assert not xf.cashtag_matches(("SOLX",), "SOL")
    assert not xf.cashtag_matches((), "SOL")


def test_name_only_tickers_etc_link_near_hype_pi_pump_gt_cc():
    assert xf.NAME_ONLY == frozenset({"ETC", "LINK", "NEAR", "HYPE", "PI", "PUMP", "GT", "CC"})
    link = xf.Coin("LINK", "Chainlink")
    r = run([tw("click the link below", cashtags=()), tw("Chainlink oracles", cashtags=(), uid=2),
             tw("tagged", cashtags=("LINK",), uid=3)], coin=link)
    assert [t.text for t in r.counted] == ["Chainlink oracles", "tagged"]
    assert r.exclusions["name_only_no_match"] == 1
    # A name-only coin whose name equals its ticker never matches the bare word.
    near = xf.Coin("NEAR", "NEAR")
    r = run([tw("near the top", cashtags=()), tw("x", cashtags=("near",), uid=2)], coin=near)
    assert [t.text for t in r.counted] == ["x"]
    # A word-like ticker that is NOT name-only matches its name when the name equals the ticker.
    aave = xf.Coin("AAVE", "Aave")
    assert len(run([tw("aave is up", cashtags=())], coin=aave).counted) == 1


def test_placeholder_user_excluded():
    ph = user(9, profile_image_url="", followers=0, statuses=0, created=datetime(1970, 1, 1, tzinfo=timezone.utc))
    assert xf.is_placeholder(ph)
    assert not xf.is_placeholder(user(9, profile_image_url="", followers=50))
    r = run([tw("a", user=ph), tw("b", uid=2)])
    assert [t.text for t in r.counted] == ["b"] and r.exclusions["placeholder"] == 1


def test_young_account_and_low_followers_and_protected_excluded():
    young = user(2, created=NOON - timedelta(days=29))
    edge = user(3, created=NOON - timedelta(days=30))
    r = run([tw("young", user=young), tw("edge", user=edge), tw("few", user=user(4, followers=9)),
             tw("ten", user=user(5, followers=10)), tw("prot", user=user(6, protected=True))])
    assert [t.text for t in r.counted] == ["edge", "ten"]
    assert (r.exclusions["young_account"], r.exclusions["low_followers"], r.exclusions["protected"]) == (1, 1, 1)


def test_author_cap_three_and_duplicate_text_once():
    r = run([tw(f"post {i}", uid=1) for i in range(5)] + [tw("same  TEXT", uid=2), tw("same text", uid=3)])
    assert [t.text for t in r.counted] == ["post 0", "post 1", "post 2", "same  TEXT"]
    assert r.exclusions["author_cap"] == 2 and r.exclusions["duplicate_text"] == 1


def test_cashtag_spam_over_five_excluded():
    five = ("SOL", "A", "B", "C", "D")
    six = five + ("E",)
    r = run([tw("five", cashtags=five), tw("six", cashtags=six, uid=2)])
    assert [t.text for t in r.counted] == ["five"] and r.exclusions["cashtag_spam"] == 1


def test_unique_authors_and_top_author_share():
    r = run([tw("a1", uid=1), tw("a2", uid=1), tw("a3", uid=1), tw("b1", uid=2)])
    assert r.unique_authors == 2 and r.top_author_share == pytest.approx(0.75)
    empty = run([])
    assert empty.unique_authors == 0 and empty.top_author_share is None


def test_exclusions_counted_by_reason_in_evidence():
    r = run([tw("out", when=NOON - timedelta(days=1)), tw("rt", retweeted_id=1, uid=2), tw("ok", uid=3)])
    assert set(r.exclusions) == set(xf.EXCLUSION_REASONS)
    assert r.exclusions["not_in_window"] == 1 and sum(r.exclusions.values()) == 2
    assert r.as_evidence()["exclusions"] == dict(r.exclusions)
    # Each tweet is excluded by exactly one reason (the first that applies).
    both = run([tw("x", retweeted_id=1, reply_to_id=2, lang="fr")])
    assert sum(both.exclusions.values()) == 1 and both.exclusions["retweet"] == 1


def test_engagement_sum_log1p_like_reply_quote_retweet():
    tweets = [tw("a", like=10, reply=2, quote=0, retweet=3, views=999_999), tw("b", like=0, uid=2)]
    expect = math.log1p(10) + math.log1p(2) + math.log1p(0) + math.log1p(3)
    assert xf.engagement_sum(tweets) == pytest.approx(expect)
    assert xf.engagement_sum([]) == 0.0
    assert xf.ENGAGEMENT_SOURCE == "xsearch_engagement"


def test_missing_view_count_not_zero_and_median_views_stored():
    assert xf.median_views([tw("a", views=None), tw("b", views=10), tw("c", views=30)]) == 20
    assert xf.median_views([tw("a", views=None)]) is None
    assert xf.median_views([tw("a", views=0), tw("b", views=None)]) == 0


def test_read_age_hours_recorded():
    now = NOON + timedelta(hours=30)
    tweets = [tw("a", when=NOON), tw("b", when=NOON + timedelta(hours=6))]
    assert xf.read_age_hours(tweets, now) == pytest.approx(27.0)
    assert xf.read_age_hours([], now) is None
