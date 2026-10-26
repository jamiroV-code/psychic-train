"""T106 D: the read-only sources status. Store and config only; every path redirected to tmp_path."""
from __future__ import annotations

import time
from datetime import timedelta

import pytest

from api.analytics.attention import sources as src
from api.data.attention import store
from api.data.attention.types import SourceSeries
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import END, gain, put_change, world

COINS = {"A": 5e7, "B": 5e7, "C": 5e7}


def row(res, sid):
    return next(r for r in res.sources if r.id == sid)


@pytest.fixture
def live(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.delenv("X_LIVE", raising=False)
    world(tmp_path, monkeypatch, COINS, cats={"ai": list(COINS)})
    src.clear_cache()
    return tmp_path


def test_row_set_is_every_configured_source(live):
    ids = [r.id for r in src.build_sources(TODAY).sources]
    assert ids == ["wikipedia", "trends", "reddit", "xsearch", "exchange_activity", "github_dev", "defillama",
                   "binance", "coinbase", "kraken", "hyperliquid", "coingecko", "universe", "narratives"]


def test_ok_source_reports_coins_days_and_newest(live):
    for s in "BC":
        put_change("wikipedia", s, 2.0, 1.0, days=130)
    put_change("wikipedia", "A", 2.0, 1.0, days=130, lag=1)   # a lagging coin must not set `newest`
    r = row(src.build_sources(TODAY), "wikipedia")
    assert (r.state, r.weight, r.coins_with_data, r.eligible_size, r.history_days) == ("ok", 25, 3, 3, 130)
    assert r.newest == END.isoformat() and r.note == ""


def test_short_history_is_insufficient_with_counts(live):
    put_change("trends", "A", 2.0, 1.0, days=40)
    r = row(src.build_sources(TODAY), "trends")
    assert (r.state, r.coins_with_data, r.history_days) == ("insufficient-history", 0, 40)
    assert "40/90" in r.note


def test_no_files_is_unavailable(live):
    r = row(src.build_sources(TODAY), "reddit")
    assert (r.state, r.coins_with_data, r.history_days, r.newest) == ("unavailable", 0, 0, None)
    assert r.note == "no stored data"


def test_stale_series_does_not_count_as_data(live):
    put_change("reddit", "A", 2.0, 1.0, days=130, lag=10)
    r = row(src.build_sources(TODAY), "reddit")
    assert (r.state, r.coins_with_data) == ("unavailable", 0) and "stale" in r.note


def test_unprobed_source_is_not_probed_even_with_files(live, monkeypatch):
    from api.data.attention import registry
    p = live / "probe_records.json"
    p.write_text('{"wikipedia": {}}')
    monkeypatch.setattr(registry, "PROBE_RECORDS_PATH", p)
    put_change("trends", "A", 2.0, 1.0)
    r = row(src.build_sources(TODAY), "trends")
    assert r.state == "not-probed" and r.note == "not probed yet"


def test_xsearch_is_off_unless_x_live(live, monkeypatch):
    put_change("xsearch", "A", 2.0, 1.0)
    assert row(src.build_sources(TODAY), "xsearch").state == "off"
    assert "X_LIVE" in row(src.build_sources(TODAY), "xsearch").note
    monkeypatch.setenv("X_LIVE", "1")
    assert row(src.build_sources(TODAY), "xsearch").state == "ok"


def test_exchange_slot_uses_members_then_coingecko_fallback(live):
    put_change("coingecko", "A", 2.0, 1.0)
    slot = row(src.build_sources(TODAY), "exchange_activity")
    assert (slot.state, slot.weight, slot.coins_with_data) == ("ok", 10, 1) and "CoinGecko" in slot.note
    assert row(src.build_sources(TODAY), "coingecko").weight is None
    put_change("exchange_volume", "B", 2.0, 1.0)
    res = src.build_sources(TODAY)
    assert row(res, "exchange_activity").coins_with_data == 2
    assert (row(res, "binance").state, row(res, "binance").weight) == ("ok", 40)


def test_summary_counts_weighted_sources_only(live):
    for s in COINS:
        put_change("wikipedia", s, 2.0, 1.0)
        put_change("coingecko", s, 2.0, 1.0)
    res = src.build_sources(TODAY)
    assert (res.live_sources, res.total_sources, res.live_weight) == (2, 7, 35)
    assert res.newest == END.isoformat()
    assert (res.universe_size, res.eligible_size) == (3, 3)


def test_helper_stores(live):
    res = src.build_sources(TODAY)
    assert (row(res, "universe").state, row(res, "universe").coins_with_data) == ("ok", 3)
    assert row(res, "universe").newest == "2026-10-15"
    assert (row(res, "narratives").state, row(res, "narratives").note) == ("ok", "status proposed")


def test_helper_snapshot_without_date_is_not_a_500():
    r = src._helper("universe", {"coins": ["A"]}, "coins", "top-100 snapshot")
    assert (r.state, r.newest, r.coins_with_data) == ("ok", None, 1)


def test_helper_stores_missing(isolated_cache, tmp_path):
    src.clear_cache()
    res = src.build_sources(TODAY)
    assert row(res, "universe").state == "unavailable"
    assert res.eligible_size == 0 and res.live_weight == 0


def test_unreadable_file_is_unavailable_not_a_500(live):
    put_change("wikipedia", "A", 2.0, 1.0)
    store.store_path("wikipedia", "A").write_bytes(b"not parquet")
    r = row(src.build_sources(TODAY), "wikipedia")
    assert r.state == "unavailable" and r.coins_with_data == 0


def test_cache_follows_file_changes(live):
    put_change("wikipedia", "A", 2.0, 1.0, days=130)
    assert row(src.build_sources(TODAY), "wikipedia").history_days == 130
    pts = [(END - timedelta(days=i), 1.0) for i in range(200)]
    p = store.store_path("wikipedia", "A")
    p.unlink()
    store.write_series(SourceSeries("wikipedia", "A", pts, "ok"), today=TODAY)
    assert row(src.build_sources(TODAY), "wikipedia").history_days == 200


def test_100_coin_fixture_is_fast_and_cached(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.delenv("X_LIVE", raising=False)
    coins = {f"C{i:03d}": 5e7 for i in range(100)}
    world(tmp_path, monkeypatch, coins, cats={"ai": list(coins)})
    for s in coins:
        for name in ("wikipedia", "coingecko", "trends"):
            put_change(name, s, 2.0, 1.0, days=130)
    src.clear_cache()
    t0 = time.perf_counter()
    cold = src.build_sources(TODAY)
    t1 = time.perf_counter()
    warm = src.build_sources(TODAY)
    t2 = time.perf_counter()
    print(f"sources 100 coins: cold {1000 * (t1 - t0):.0f} ms, warm {1000 * (t2 - t1):.0f} ms")
    assert row(cold, "wikipedia").coins_with_data == 100 and cold == warm
    assert (t1 - t0) < 5.0 and (t2 - t1) < 1.0


def _keywords(tmp_path, monkeypatch, text):
    p = tmp_path / "kw.json"
    p.write_text(text)
    monkeypatch.setattr(src.trends_keywords, "KEYWORDS_PATH", p)   # the module object sources reads (a test reimports it)


def test_trends_keyword_coverage_over_eligible_coins(live, monkeypatch):
    """T180: every eligible coin without a usable keyword is listed with reason no-trends-keyword."""
    _keywords(live, monkeypatch, '{"_anchor": {"term": "Bitcoin", "label": "B"}, "A": {"topic": "/m/0a", "label": "A"},'
              ' "B": {"no-keyword": true, "label": "B", "note": "unidentified"}, "OLD": {"term": "Old", "label": "O"}}')
    tk = src.build_sources(TODAY).trends_keyword
    assert (tk.eligible_size, tk.with_keyword) == (3, 1)
    assert [(g.symbol, g.reason, g.detail) for g in tk.missing] == [
        ("B", "no-trends-keyword", "no-keyword"), ("C", "no-trends-keyword", "no-entry")]


def test_trends_keyword_bad_file_counts_every_coin_missing(live, monkeypatch):
    _keywords(live, monkeypatch, "{bad")
    tk = src.build_sources(TODAY).trends_keyword
    assert tk.with_keyword == 0 and [g.detail for g in tk.missing] == ["bad-file"] * 3
