"""W8b AC8/AC15/AC20: query file, collector config block and validator, coin set. Pure; no network."""
from __future__ import annotations

import copy
import json

import pytest

from api.data.attention import web_queries as wq

LOCKED = {
    "x_query_delay_min_s": 180, "x_query_delay_max_s": 360, "x_daily_post_budget": 800, "x_sample_n": 40,
    "x_sample_min": 20, "x_page_cap": 3, "reddit_request_delay_min_s": 60, "reddit_request_delay_max_s": 120,
    "reddit_daily_request_budget": 250, "reddit_sample_min": 10,
}


@pytest.fixture
def doc():
    return json.loads(wq.QUERIES_PATH.read_text(encoding="utf-8"))


def test_committed_file_loads_with_locked_defaults():
    q = wq.load(placed_symbols=wq.placed_symbols())
    for key, value in LOCKED.items():
        assert getattr(q.config, key) == value, key
    assert q.config.x_page_gap_min_s == 5 and q.config.x_page_gap_max_s == 15
    assert q.config.x_backfill_days == 14
    assert {k: wq.DEFAULTS[k] for k in LOCKED} == LOCKED
    assert set(wq.DEFAULTS) == set(q.config.as_dict())


def test_reddit_baseline_250_and_separate_degraded_150_budget():
    assert wq.DEFAULTS["reddit_daily_request_budget"] == 250
    assert wq.REDDIT_DEFAULTS["reddit_degraded_request_budget"] == wq.REDDIT_DEGRADED_BUDGET == 150
    c = wq.load().config
    assert c.reddit_daily_request_budget == 250 and c.reddit_degraded_request_budget == 150
    absent = {k: v for k, v in c.as_dict().items() if k != "reddit_degraded_request_budget"}
    assert wq.validate_config(absent).reddit_degraded_request_budget == 150  # the default applies when absent


def test_pace_config_rejects_min_above_max_and_nonpositive(doc):
    for key, bad in (("x_query_delay_min_s", 400), ("reddit_request_delay_min_s", 121), ("x_page_gap_min_s", 16)):
        d = copy.deepcopy(doc)
        d["collector"][key] = bad
        with pytest.raises(wq.QueriesError, match="must be <="):
            wq.validate(d)
    for key in LOCKED:
        for bad in (0, -1, "180", True, None):
            d = copy.deepcopy(doc)
            d["collector"][key] = bad
            with pytest.raises(wq.QueriesError):
                wq.validate(d)


def test_sample_min_above_sample_n_rejected(doc):
    doc["collector"]["x_sample_min"] = 41
    with pytest.raises(wq.QueriesError, match="x_sample_min"):
        wq.validate(doc)


def test_unknown_and_missing_config_keys_rejected(doc):
    d = copy.deepcopy(doc)
    d["collector"]["x_turbo"] = 1
    with pytest.raises(wq.QueriesError, match="unknown"):
        wq.validate(d)
    d = copy.deepcopy(doc)
    del d["collector"]["x_daily_post_budget"]
    with pytest.raises(wq.QueriesError, match="x_daily_post_budget"):
        wq.validate(d)


def test_config_change_is_read(doc, tmp_path):
    doc["collector"]["x_query_delay_min_s"] = 600
    doc["collector"]["x_query_delay_max_s"] = 900
    p = tmp_path / "q.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    q = wq.load(p)
    assert (q.config.x_query_delay_min_s, q.config.x_query_delay_max_s) == (600, 900)


def test_coin_set_is_narrative_placed_symbols_minus_ambiguous():
    placed = wq.placed_symbols()
    assert len(placed) == 75 and "SOL" in placed
    q = wq.load(placed_symbols=placed)
    for source in wq.SOURCES:
        coins = wq.coin_set(q, source, placed)
        assert set(coins) == set(placed) - q.ambiguous[source]
        assert coins == sorted(coins)
    assert set(wq.coin_set(q, "xsearch_web", ["SOL", "NOPE"])) == {"SOL", "NOPE"} - q.ambiguous["xsearch_web"]


def test_ambiguous_coin_is_missing(doc):
    doc["ambiguous"]["xsearch_web"] = ["SOL"]
    q = wq.validate(doc)
    assert wq.x_query(q, "SOL") is None
    assert "SOL" not in wq.coin_set(q, "xsearch_web", ["SOL", "ETH"])
    assert wq.x_query(q, "ETH") == '("$ETH" OR "Ethereum") lang:en -filter:replies -filter:retweets'


def test_every_placed_coin_has_a_name_entry():
    with pytest.raises(wq.QueriesError, match="no entry"):
        wq.validate({**json.loads(wq.QUERIES_PATH.read_text(encoding="utf-8")), "coins": {}},
                    placed_symbols=["SOL"])


def test_bad_terms_and_subreddits_rejected(doc):
    d = copy.deepcopy(doc)
    d["coins"]["SOL"]["name"] = 'Sol" OR "x'
    with pytest.raises(wq.QueriesError):
        wq.validate(d)
    d = copy.deepcopy(doc)
    d["subreddits"] = ["ok", "bad/path"]
    with pytest.raises(wq.QueriesError):
        wq.validate(d)
    d = copy.deepcopy(doc)
    d["ambiguous"]["unknown_source"] = []
    with pytest.raises(wq.QueriesError):
        wq.validate(d)


def test_subreddit_set_matches_spec_proposal():
    q = wq.load()
    assert q.subreddits[:3] == ("CryptoCurrency", "CryptoMarkets", "altcoin") and len(q.subreddits) == 12


def test_honest_user_agent_is_plain():
    assert wq.HONEST_USER_AGENT == "attention-probe/0.1"


# --- W8c2 stream keys (owner deltas 29-10-26: 12-name set by reference, comments 7200 s, posts 21600 s, paging on) ---

def test_stream_keys_committed_with_owner_defaults():
    c = wq.load().config
    assert c.reddit_stream_subreddits is None  # None: the stream uses the top-level `subreddits` list
    assert c.reddit_comments_poll_interval_s == 7200 and c.reddit_posts_poll_interval_s == 21600
    assert c.reddit_stream_polls_per_day_cap == 12 and c.reddit_stream_min_coverage == 0.8
    assert c.reddit_comments_paging is True
    assert c.reddit_impl_order == ("reddit_stream", "reddit_web")


def test_stream_keys_default_when_absent(doc):
    for key in wq.REDDIT_STREAM_DEFAULTS:
        doc["collector"].pop(key, None)
    c = wq.validate(doc).config
    for key, value in wq.REDDIT_STREAM_DEFAULTS.items():
        assert getattr(c, key) == (tuple(value) if isinstance(value, list) else value), key


def test_stream_subreddit_set_resolves_to_top_level_list(doc):
    q = wq.validate(doc)
    assert wq.stream_subreddits(q) == q.subreddits and len(q.subreddits) == 12
    doc["collector"]["reddit_stream_subreddits"] = ["CryptoCurrency", "altcoin"]
    assert wq.stream_subreddits(wq.validate(doc)) == ("CryptoCurrency", "altcoin")


@pytest.mark.parametrize("key,bad", [
    ("reddit_stream_subreddits", []), ("reddit_stream_subreddits", ["bad name!"]),
    ("reddit_stream_subreddits", ["altcoin", "Altcoin"]), ("reddit_stream_subreddits", "subreddits"),
    ("reddit_comments_poll_interval_s", 0), ("reddit_comments_poll_interval_s", True),
    ("reddit_posts_poll_interval_s", -1), ("reddit_stream_polls_per_day_cap", 0),
    ("reddit_stream_min_coverage", 0), ("reddit_stream_min_coverage", 1.5), ("reddit_stream_min_coverage", True),
    ("reddit_comments_paging", 1), ("reddit_impl_order", []), ("reddit_impl_order", ["reddit_web", "reddit_web"]),
    ("reddit_impl_order", ["reddit_api"]), ("reddit_impl_order", "reddit_stream"),
])
def test_stream_keys_rejected_when_invalid(doc, key, bad):
    doc["collector"][key] = bad
    with pytest.raises(wq.QueriesError, match=key):
        wq.validate(doc)
