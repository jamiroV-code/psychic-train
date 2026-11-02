"""T106 D: the read-only sources status. Store and config only; every path redirected to tmp_path."""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta

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


def test_universe_row_counts_top_100_of_a_120_row_snapshot(isolated_cache):
    from api.data.attention import universe_store
    src.clear_cache()
    universe_store.write_snapshot(TODAY.isoformat(), [
        {"id": f"c{i}", "symbol": f"C{i}", "market_cap": 1000 - i, "volume_24h": 1, "rank": i} for i in range(1, 121)])
    assert row(src.build_sources(TODAY), "universe").coins_with_data == 100


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
    """T180: every eligible coin without a usable keyword is listed with reason no-trends-keyword; stage 2 (AC8):
    an ambiguous coin without an approved term reads skipped-unqualified (the waiting-for-approval group)."""
    _keywords(live, monkeypatch, '{"_anchor": {"term": "Bitcoin", "label": "B"}, "_ambiguous": ["A"],'
              ' "A": {"term": "a crypto", "label": "A"},'
              ' "B": {"no-keyword": true, "label": "B", "note": "unidentified"}, "OLD": {"term": "Old", "label": "O"}}')
    tk = src.build_sources(TODAY).trends_keyword
    assert (tk.eligible_size, tk.with_keyword) == (3, 0)
    assert [(g.symbol, g.reason, g.detail) for g in tk.missing] == [
        ("A", "no-trends-keyword", "skipped-unqualified"), ("B", "no-trends-keyword", "no-keyword"),
        ("C", "no-trends-keyword", "no-entry")]


def test_trends_keyword_bad_file_counts_every_coin_missing(live, monkeypatch):
    _keywords(live, monkeypatch, "{bad")
    tk = src.build_sources(TODAY).trends_keyword
    assert tk.with_keyword == 0 and [g.detail for g in tk.missing] == ["bad-file"] * 3


# --- stage 2 (D-30, S4): the waking-up watch list (shown only, never scored) ---

def _run_file(day, coins):
    import json as _json
    from api.data import cache
    d = cache.CACHE_ROOT / "attention" / "trends_runs"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{day.isoformat()}.json").write_text(_json.dumps({"coins": {s: {"outcome": o} for s, o in coins.items()}}))


def test_trends_watch_present_and_empty(live):
    assert src.build_sources(TODAY).trends_watch == []


def test_trends_watch_lists_days_held(live):
    _run_file(TODAY - timedelta(days=1), {"A": "quiet-then-surge", "B": "ok"})
    _run_file(TODAY, {"A": "quiet-then-surge", "B": "quiet-then-surge"})
    watch = src.build_sources(TODAY).trends_watch
    assert [(w.symbol, w.days_held) for w in watch] == [("A", 2), ("B", 1)]
    _run_file(TODAY, {"A": "ok", "B": "quiet-then-surge"})     # a coin that stops jumping leaves the list
    assert [w.symbol for w in src.build_sources(TODAY).trends_watch] == ["B"]


def test_sources_model_key_set_without_testclient():
    from api.models.discovery import (DiscoveryCollectorSource, DiscoveryCollectorStatus, DiscoverySourcesResponse,
                                      DiscoveryTrendsWatch)
    assert set(DiscoverySourcesResponse.model_fields) == {
        "as_of", "universe_size", "eligible_size", "live_sources", "total_sources", "live_weight", "newest",
        "sources", "trends_keyword", "trends_watch", "collector"}
    assert set(DiscoveryTrendsWatch.model_fields) == {"symbol", "days_held"}
    assert DiscoverySourcesResponse.model_fields["trends_watch"].default is None
    assert DiscoverySourcesResponse.model_fields["collector"].default is None
    assert set(DiscoveryCollectorStatus.model_fields) == {
        "state", "reason", "started_at", "last_beat", "age_s", "mode", "version", "running_sources", "sources"}
    assert set(DiscoveryCollectorSource.model_fields) == {
        "id", "label", "has_state", "last_unit_at", "paused", "pause_reason", "pause_until", "stale", "budget_used",
        "effective_budget"}


# --- standalone collector (C): the heartbeat read as a `collector` object, files only ------------------------------

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
OTHER_PID = 424242


def _beat(*, age_s=10.0, stopped=False, pid=OTHER_PID, mode="standalone"):
    from api.data.attention import collector_heartbeat as hb
    beat = NOW - timedelta(seconds=age_s)
    hb.path().parent.mkdir(parents=True, exist_ok=True)
    hb.path().write_text(json.dumps({
        "pid": pid, "started_at": (beat - timedelta(hours=3)).isoformat(), "last_beat": beat.isoformat(),
        "mode": mode, "sources": ["xsearch_web", "reddit_web"], "version": "abc1234", "stopped": stopped,
        "stopped_at": beat.isoformat() if stopped else None}), encoding="utf-8")


@pytest.fixture
def other_alive(monkeypatch):
    from api.data.attention import collector_heartbeat as hb
    state = {"alive": True}
    monkeypatch.setattr(hb, "pid_alive", lambda pid: state["alive"] if pid == OTHER_PID else False)
    return state


def test_collector_never_started_reports_no_values(live):
    c = src.build_sources(TODAY, now=NOW).collector
    assert (c.state, c.reason, c.started_at, c.last_beat, c.age_s, c.mode, c.version) == (
        "never_started", "no_heartbeat", None, None, None, None, None)
    assert c.running_sources == []
    assert [(s.id, s.label) for s in c.sources] == [("xsearch", "X search"), ("reddit", "Reddit")]
    for s in c.sources:   # no worker state: unknown, never 0 or "not paused"
        assert (s.has_state, s.last_unit_at, s.paused, s.pause_reason, s.stale, s.budget_used,
                s.effective_budget) == (False, None, None, None, None, None, None)


def test_collector_running_when_heartbeat_fresh_and_process_alive(live, other_alive):
    _beat(age_s=12.5, mode="in_api")
    c = src.build_sources(TODAY, now=NOW).collector
    assert (c.state, c.reason, c.age_s, c.mode, c.version) == ("running", "", 12.5, "in_api", "abc1234")
    assert c.last_beat == (NOW - timedelta(seconds=12.5)).isoformat()
    assert c.started_at == (NOW - timedelta(seconds=12.5, hours=3)).isoformat()
    assert c.running_sources == ["xsearch_web", "reddit_web"]


@pytest.mark.parametrize("age_s,stopped,alive,reason", [
    (91.0, False, True, "heartbeat_stale"), (5.0, True, True, "stopped_cleanly"), (5.0, False, False, "process_gone")])
def test_collector_stopped(live, other_alive, age_s, stopped, alive, reason):
    other_alive["alive"] = alive
    _beat(age_s=age_s, stopped=stopped)
    c = src.build_sources(TODAY, now=NOW).collector
    assert (c.state, c.reason, c.age_s) == ("stopped", reason, age_s)


def test_collector_unknown_when_heartbeat_unreadable(live):
    from api.data.attention import collector_heartbeat as hb
    hb.path().parent.mkdir(parents=True, exist_ok=True)
    hb.path().write_text("{broken", encoding="utf-8")
    c = src.build_sources(TODAY, now=NOW).collector
    assert (c.state, c.reason, c.age_s, c.last_beat) == ("unknown", "unreadable", None, None)


def test_collector_sources_reuse_the_health_fields(live, other_alive):
    from api.data.attention import pc_pace
    _beat()
    reddit = pc_pace.PcSource("reddit_web", configured_budget=250, floor=1, adaptive=False, clock=lambda: NOW)
    reddit.spend(3)
    reddit.record_unit()
    res = src.build_sources(TODAY, now=NOW)
    health = row(res, "reddit").health
    s = next(s for s in res.collector.sources if s.id == "reddit")
    assert health is not None and s.has_state is True
    assert (s.last_unit_at, s.paused, s.pause_reason, s.pause_until, s.stale, s.budget_used, s.effective_budget) == (
        health.last_unit_at, health.paused, health.pause_reason, health.pause_until, health.stale,
        health.budget_used, health.effective_budget)
    assert s.last_unit_at == NOW.isoformat() and s.budget_used == 3 and s.effective_budget == 250
    x = next(s for s in res.collector.sources if s.id == "xsearch")
    assert x.has_state is False and x.budget_used is None


def test_collector_summary_kept_for_a_parked_source(live, monkeypatch):
    """A PC source with weight 0 has no row health; the collector box still reads its worker state."""
    from api.data.attention import pc_pace
    real = src.load_config

    def parked(path=None):
        cfg = real(path)
        return {**cfg, "source_weights": {**cfg["source_weights"], "xsearch": 0}}

    monkeypatch.setattr(src, "load_config", parked)
    pc_pace.PcSource("xsearch_web", configured_budget=400, floor=40, adaptive=True, clock=lambda: NOW).record_unit()
    res = src.build_sources(TODAY, now=NOW)
    assert row(res, "xsearch").health is None
    x = next(s for s in res.collector.sources if s.id == "xsearch")
    assert x.has_state is True and x.last_unit_at == NOW.isoformat()
