"""W8d1 AC42: X query and exact UTC-day window, Latest order, paging stop conditions, X config keys.

Pure; nothing from the X library is imported; no network.
"""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from api.data.attention import web_queries as wq
from api.data.attention import x_window as xw

DAY = date(2026, 10, 20)
START = datetime(2026, 10, 20, tzinfo=timezone.utc)
END = START + timedelta(days=1)


def test_query_since_time_until_time_form():
    q = xw.build_query('("$SOL" OR "Solana")', DAY, syntax="since_time", lang="en")
    assert q == (f'("$SOL" OR "Solana") lang:en -filter:replies -filter:retweets '
                 f'since_time:{int(START.timestamp())} until_time:{int(END.timestamp())}')
    assert int(END.timestamp()) - int(START.timestamp()) == 86400


def test_query_utc_date_form_until_exclusive():
    q = xw.build_query('"$SOL"', DAY, syntax="date", lang="en")
    assert q.endswith("since:2026-10-20 until:2026-10-21")
    assert xw.window_operator(date(2026, 12, 31), "date") == "since:2026-12-31 until:2027-01-01"
    # An empty language means any: no lang operator at all.
    assert "lang:" not in xw.build_query('"$SOL"', DAY, syntax="date", lang="")
    with pytest.raises(ValueError):
        xw.build_query('"$SOL"', DAY, syntax="top", lang="en")


def test_out_of_window_tweet_excluded_by_timestamp():
    assert xw.in_window(START, DAY)
    assert xw.in_window(END - timedelta(seconds=1), DAY)
    assert not xw.in_window(END, DAY)
    assert not xw.in_window(START - timedelta(seconds=1), DAY)
    # A non-UTC aware timestamp is compared in UTC.
    plus2 = timezone(timedelta(hours=2))
    assert xw.in_window(datetime(2026, 10, 21, 1, 59, tzinfo=plus2), DAY)
    assert not xw.in_window(datetime(2026, 10, 21, 2, 0, tzinfo=plus2), DAY)
    with pytest.raises(ValueError):
        xw.in_window(datetime(2026, 10, 20, 12), DAY)  # noqa: DTZ001 - naive on purpose


def test_latest_order_only():
    assert xw.search_kv() == {"product": "Latest"}
    for bad in ("Top", "top", "Media", ""):
        with pytest.raises(ValueError):
            xw.search_kv(bad)


def test_paging_stops_at_window_start_or_sample_or_page_cap():
    inside = START + timedelta(hours=6)
    before = START - timedelta(minutes=1)
    stop = xw.stop_reason
    assert stop(pages=1, entries_read=20, oldest_read=inside, day=DAY, sample_n=40, page_cap=3) is None
    assert stop(pages=1, entries_read=20, oldest_read=before, day=DAY, sample_n=40, page_cap=3) == "window_start"
    assert stop(pages=2, entries_read=40, oldest_read=inside, day=DAY, sample_n=40, page_cap=3) == "sample"
    assert stop(pages=3, entries_read=39, oldest_read=inside, day=DAY, sample_n=40, page_cap=3) == "page_cap"
    # The window start wins: every tweet of the day was read, so the count is exact.
    assert stop(pages=3, entries_read=60, oldest_read=before, day=DAY, sample_n=40, page_cap=3) == "window_start"
    # Exactly at the window start is still inside the window.
    assert stop(pages=1, entries_read=20, oldest_read=START, day=DAY, sample_n=40, page_cap=3) is None


def test_coin_terms_cashtag_first_and_ambiguous_none():
    q = wq.load()
    assert xw.coin_terms(q, "SOL") == '("$SOL" OR "Solana")'
    assert xw.coin_terms(q, "ATOM") == '"$ATOM"'  # cashtag_only
    assert xw.coin_terms(q, "AKE") is None  # ambiguous for X
    assert xw.coin_terms(q, "NOPE") is None


def test_x_config_keys_in_query_file_with_spec_defaults():
    q = wq.load(placed_symbols=wq.placed_symbols())
    c = q.config
    assert (c.x_lang, c.x_window_syntax, c.x_min_account_age_days, c.x_min_followers, c.x_max_cashtags,
            c.x_raw_retention_days, c.x_canary_query, c.x_canary_min_results) == (
        "en", "since_time", 30, 10, 5, 180, "bitcoin", 15)
    assert (c.x_unit_max_restarts, c.x_canary_tolerance, c.x_canary_min_overlap, c.x_parse_drop_threshold,
            c.x_allow_curl_backend) == (1, 0.25, 0.6, 0.2, False)
    doc = json.loads(wq.QUERIES_PATH.read_text(encoding="utf-8"))
    assert set(wq.X_DEFAULTS) <= set(doc["collector"])


@pytest.mark.parametrize("key,bad", [
    ("x_window_syntax", "top"), ("x_window_syntax", 1), ("x_lang", "english"), ("x_lang", None),
    ("x_canary_tolerance", 0), ("x_canary_tolerance", 1.5), ("x_canary_min_overlap", "0.6"),
    ("x_parse_drop_threshold", True), ("x_allow_curl_backend", 1), ("x_allow_curl_backend", "false"),
    ("x_min_followers", -1), ("x_canary_min_results", 0), ("x_canary_query", ""), ("x_unit_max_restarts", True),
    ("x_raw_retention_days", 0), ("x_max_cashtags", 1.5),
])
def test_x_config_keys_rejected_when_mistyped(key, bad):
    doc = json.loads(wq.QUERIES_PATH.read_text(encoding="utf-8"))
    d = copy.deepcopy(doc)
    d["collector"][key] = bad
    with pytest.raises(wq.QueriesError, match=key):
        wq.validate(d)


def test_per_coin_lang_override_validated():
    doc = json.loads(wq.QUERIES_PATH.read_text(encoding="utf-8"))
    d = copy.deepcopy(doc)
    d["coins"]["SOL"]["x_lang"] = ""
    assert wq.validate(d).coins["SOL"]["x_lang"] == ""
    d["coins"]["SOL"]["x_lang"] = "spanish"
    with pytest.raises(wq.QueriesError, match="x_lang"):
        wq.validate(d)


def test_paging_continues_while_all_read_tweets_are_after_the_window_end():
    """T187 M1: entries read after the window end never fill the sample; keep paging to the page cap."""
    after = END + timedelta(minutes=5)
    stop = xw.stop_reason
    assert stop(pages=2, entries_read=40, oldest_read=after, day=DAY, sample_n=40, page_cap=3) is None
    assert stop(pages=2, entries_read=40, oldest_read=END, day=DAY, sample_n=40, page_cap=3) is None
    assert stop(pages=3, entries_read=60, oldest_read=after, day=DAY, sample_n=40, page_cap=3) == "page_cap"
    assert stop(pages=2, entries_read=40, oldest_read=END - timedelta(seconds=1), day=DAY, sample_n=40,
                page_cap=3) == "sample"


def test_exhausted_cursor_is_a_complete_read_of_the_window():
    """T187 M3: an empty page (or None) ends the cursor: everything matching was read, so the count is exact."""
    stop = xw.stop_reason
    inside = START + timedelta(hours=3)
    assert stop(pages=1, entries_read=0, oldest_read=None, day=DAY, sample_n=40, page_cap=3,
                exhausted=True) == "cursor_exhausted"
    assert stop(pages=2, entries_read=20, oldest_read=inside, day=DAY, sample_n=40, page_cap=3,
                exhausted=True) == "cursor_exhausted"
    assert stop(pages=2, entries_read=20, oldest_read=START, day=DAY, sample_n=40, page_cap=3,
                exhausted=True) == "cursor_exhausted"
    assert stop(pages=2, entries_read=20, oldest_read=START - timedelta(seconds=1), day=DAY, sample_n=40,
                page_cap=3, exhausted=True) == "window_start"
    assert xw.COMPLETE_STOPS == ("window_start", "cursor_exhausted")


def test_cursor_end_exhausted_only_after_a_short_last_page():
    ce = xw.cursor_end
    assert ce((), seen=set(), last_entries=None, page_size=20) == "cursor_exhausted"  # empty first page
    assert ce((), seen={"a"}, last_entries=19, page_size=20) == "cursor_exhausted"
    assert ce((), seen={"a"}, last_entries=20, page_size=20) == "cursor_stalled"
    assert ce(("a", "b"), seen={"a"}, last_entries=20, page_size=20) == "cursor_stalled"  # repeated ids
    assert ce(("a", "b"), seen={"a"}, last_entries=5, page_size=20) == "cursor_stalled"
    assert ce(("c",), seen={"a"}, last_entries=20, page_size=20) is None
    day = date(2026, 10, 20)
    end = datetime(2026, 10, 21, tzinfo=timezone.utc)
    kw = {'pages': 1, 'entries_read': 20, 'oldest_read': end - timedelta(minutes=10), 'day': day, 'sample_n': 40, 'page_cap': 3}
    assert xw.stop_reason(**kw, stalled=True) == "cursor_stalled"
    assert xw.stop_reason(**{**kw, "oldest_read": end - timedelta(days=2)}, stalled=True) == "window_start"
