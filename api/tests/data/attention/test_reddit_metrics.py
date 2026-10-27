"""W8c AC31, AC32, AC35: Reddit mention and engagement metrics. Pure; no network."""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

import pytest

from api.data.attention import reddit_metrics as rm
from api.data.attention import web_queries as wq

D = date(2026, 10, 26)


def at(h: int, m: int = 0, day: date = D) -> datetime:
    return datetime(day.year, day.month, day.day, h, m, tzinfo=timezone.utc)


def item(i: int, author: str | None = "a1", coins=("SOL",), created=None, **kw) -> rm.Item:
    return rm.Item(id=kw.pop("id", f"t3_{i:x}"), author_hash=author, created=created or at(12), coins=tuple(coins), **kw)


def coins():
    return {c.symbol: c for c in rm.coin_terms(wq.load())}


# --- AC31 matching ---

def test_name_only_tickers_need_full_name_or_cashtag():
    terms = coins()
    names = {"ETC": "Ethereum Classic", "LINK": "Chainlink", "NEAR": "NEAR Protocol", "HYPE": "Hyperliquid",
             "PI": "Pi Network", "PUMP": "Pump.fun", "GT": "GateToken", "CC": "Canton Coin"}
    for sym, name in names.items():
        c = terms[sym]
        assert c.name_only, sym
        assert not rm.mentions(f"big {sym} news today", c), sym
        assert rm.mentions(f"big {name} news today", c), sym
        assert rm.mentions(f"big ${sym} news today", c), sym
        assert rm.mentions(f"big ${sym.lower()} news", c), sym


def test_bare_ticker_matches_for_other_coins():
    terms = coins()
    assert rm.mentions("SOL breaks out", terms["SOL"])
    assert rm.mentions("solana breaks out", terms["SOL"])
    assert rm.mentions("bought $sol", terms["SOL"])
    assert not rm.mentions("SOLAR panels", terms["SOL"])
    assert not rm.mentions("console sol", terms["SOL"])  # bare ticker is an upper-case word only
    assert not rm.mentions("PARSOL x", terms["SOL"])
    assert not terms["SOL"].name_only


def test_ambiguity_list_not_in_coin_terms_and_never_matched():
    terms = coins()
    for sym in ("AKE", "BTW", "GRAM", "LIT", "NIGHT", "PRL", "RAIN", "SKY", "STABLE"):
        assert sym not in terms
    assert "SKY" not in rm.matched_coins("SKY is the limit $SKY", list(terms.values()))


def test_matched_coins_sorted_and_distinct():
    terms = list(coins().values())
    assert rm.matched_coins("SOL and Ethereum and $SOL", terms) == ("ETH", "SOL")
    assert rm.matched_coins("nothing here", terms) == ()


def test_author_cap_three_per_coin_day():
    items = [item(i, author="spam", created=at(1 + i)) for i in range(5)] + [item(9, author="b")]
    day = rm.mention_day(items, "SOL", D, author_cap=3, min_mentions=3)
    assert day.mentions == 4 and day.unique_authors == 2


def test_unique_authors_counts_distinct_hashes():
    items = [item(1, "a"), item(2, "b"), item(3, "a"), item(4, "c", coins=("ETH",)),
             item(5, "d", created=at(1, day=date(2026, 10, 25)))]
    day = rm.mention_day(items, "SOL", D, author_cap=3, min_mentions=3)
    assert day.mentions == 3 and day.unique_authors == 2


def test_mentions_dedupe_by_id_and_window_bounds():
    items = [item(1), item(1), item(2, created=at(0)), item(3, created=datetime(2026, 10, 27, tzinfo=timezone.utc)),
             item(4, id="t1_4")]
    day = rm.mention_day(items, "SOL", D, author_cap=10, min_mentions=1)
    assert day.mentions == 3  # t3_1 once, t3_2 at 00:00, the comment t1_4; 27 Oct 00:00 is outside


def test_missing_author_hash_is_capped_as_one_author():
    items = [item(i, author=None, created=at(1 + i)) for i in range(5)]
    day = rm.mention_day(items, "SOL", D, author_cap=3, min_mentions=3)
    assert day.mentions == 3 and day.unique_authors == 0


# --- AC32 volume honesty ---

def test_low_volume_below_three_mentions_change_missing():
    day = rm.mention_day([item(1, "a"), item(2, "b")], "SOL", D, author_cap=3, min_mentions=3)
    assert day.low_volume
    assert rm.mention_change([2.0, 2.0, 2.0], [5.0, 5.0], min_mentions=3) is None
    assert rm.mention_change([5.0, 5.0], [2.9, 2.9], min_mentions=3) is None
    assert rm.mention_change([], [5.0], min_mentions=3) is None


def test_exactly_three_mentions_change_computed():
    day = rm.mention_day([item(1, "a"), item(2, "b"), item(3, "c")], "SOL", D, author_cap=3, min_mentions=3)
    assert not day.low_volume and day.mentions == 3
    assert rm.mention_change([6.0, 6.0], [3.0, 3.0], min_mentions=3) == pytest.approx(100.0)
    assert rm.mention_change([3.0], [3.0], min_mentions=3) == pytest.approx(0.0)


# --- AC35 engagement ---

def test_engagement_weighted_sum_posts_add_log1p_num_comments():
    items = [item(1, score=10, num_comments=4), item(2, score=-5, num_comments=0), item(3, score=None)]
    assert rm.engagement_weighted(items) == pytest.approx(math.log1p(10) + math.log1p(4) + 0.0)
    assert rm.engagement_weighted([item(3, score=None)]) is None  # nothing available: missing, never 0


def test_comment_num_comments_not_added():
    c = item(1, id="t1_1", score=3, num_comments=500)
    assert rm.engagement_weighted([c]) == pytest.approx(math.log1p(3))


def test_controversy_boundaries_ratio_0_30_and_votes_9_10():
    p = lambda ratio, ups: item(1, score=1, num_comments=0, upvote_ratio=ratio, ups=ups)
    assert rm.is_controversial(p(0.29, 3))  # 3 / 0.29 = 10.3 votes
    assert not rm.is_controversial(p(0.30, 3))  # ratio boundary: 0.30 is not below 0.3
    assert rm.is_controversial(p(0.2, 2))  # exactly 10 votes
    assert not rm.is_controversial(p(0.2, 1.8))  # 9 votes
    assert not rm.is_controversial(item(2, id="t1_2", upvote_ratio=0.1, ups=5))  # comments are never classed
    assert not rm.is_controversial(p(None, 50)) and not rm.is_controversial(p(0.0, 0))
    hot, cold = p(0.2, 4), item(3, score=10, num_comments=0, upvote_ratio=0.9, ups=11)
    assert rm.engagement_weighted([hot, cold]) == pytest.approx(math.log1p(10))
    assert rm.controversy_count([hot, cold]) == 1


def test_deleted_later_removed_from_settled():
    keep = item(1, score=5, num_comments=1)
    gone = item(2, score=50, num_comments=9, deleted_later=True)
    removed = item(3, score=50, num_comments=9, removal_type="moderator")
    assert [i.id for i in rm.settled([keep, gone, removed])] == ["t3_1"]
    assert rm.engagement_weighted([keep, gone, removed]) == pytest.approx(math.log1p(5) + math.log1p(1))
    # provisional mention counts keep them (flagged later), settled ones do not
    assert rm.mention_day([keep, gone, removed], "SOL", D, author_cap=9, min_mentions=1).mentions == 3
