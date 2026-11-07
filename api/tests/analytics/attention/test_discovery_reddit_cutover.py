"""Finish plan 06-11-26, S-RDisc (contract C): the Reddit live methods wired into Discovery and its history.

The real `build_discovery` and `coin_history` over synthetic stores: live points present -> live selected; absent
-> feeds selected; never mixed within a window; known-lag respected in both consumers; a method switch is flagged.
Store and config only; every path redirected to tmp_path.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from api.analytics.attention import discovery as disc, discovery_history as hist
from api.data.attention import store, web_evidence, web_queries as wq
from api.data.attention.types import SourceSeries
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import END, cat, put_change, world

ORDER = ["reddit_live_browser", "reddit_live_gql", "reddit_web", "reddit_stream"]
LIVE = ("reddit_live_browser", "reddit_live_gql")
COINS = {"A": 5e7}
CATS = {"ai": ["A"]}


@pytest.fixture(autouse=True)
def _fresh_cache():
    hist.clear_cache()
    yield
    hist.clear_cache()


def put_points(source, symbol, pts):
    p = store.store_path(source, symbol)
    if p.exists():
        p.unlink()
    store.write_series(SourceSeries(source, symbol, sorted(pts), "ok"), today=TODAY)


def evidence(source, symbol, rows):
    p = web_evidence.evidence_path(source, symbol)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"rows": [r.to_json() for r in rows]}), encoding="utf-8")


def row(day, value, *, backfilled=False, late_days=1):
    at = datetime(day.year, day.month, day.day, 1, tzinfo=timezone.utc) + timedelta(days=late_days)
    return web_evidence.EvidenceRow(day, value, 10, 24.0, False, False, False, "m", at, backfilled)


def reddit(res, symbol="A"):
    coin = next(c for c in cat(res, "ai").coins if c.symbol == symbol)
    return {s.source: s for s in coin.sources}.get("reddit")


def run(**kw):
    return disc.build_discovery(30, today=TODAY, **kw)


def setup(tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, COINS, cats=CATS, source_impl={"reddit": ORDER})
    put_change("wikipedia", "A", 1.2, 1.0)


# ---- C1: committed order ------------------------------------------------------------------------

def test_shipped_discovery_and_queries_carry_the_same_live_first_order():
    shipped = json.loads(disc.CONFIG_PATH.read_text(encoding="utf-8"))
    assert shipped["source_impl"]["reddit"] == ORDER
    assert disc.source_impls(disc.load_config())["reddit"] == tuple(ORDER)
    assert wq.load().config.reddit_impl_order == tuple(ORDER)
    assert set(LIVE) <= disc.series_names(disc.load_config())


# ---- C1 / C5: real build_discovery --------------------------------------------------------------

def test_live_selected_when_it_has_enough_points(isolated_cache, tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    put_change("reddit_live_browser", "A", 1.5, 1.0)   # +50 %
    put_change("reddit_live_gql", "A", 1.3, 1.0)       # +30 %
    put_change("reddit_web", "A", 1.2, 1.0)            # +20 %
    assert reddit(run()).change == pytest.approx(50.0)
    store.store_path("reddit_live_browser", "A").unlink()
    assert reddit(run()).change == pytest.approx(30.0)


def test_feeds_keep_winning_without_live_points(isolated_cache, tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    put_change("reddit_web", "A", 1.2, 1.0)
    put_change("reddit_stream", "A", 1.1, 1.0)
    assert reddit(run()).change == pytest.approx(20.0)


def test_live_and_feed_never_mixed_in_a_window(isolated_cache, tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    # the live store holds only the recent days (+200 % against the feed base if spliced); one method per window
    put_points("reddit_live_browser", "A", [(END - timedelta(days=i), 3.0) for i in range(7)])
    put_change("reddit_web", "A", 1.1, 1.0)
    assert reddit(run()).change == pytest.approx(10.0)


def test_known_lag_drops_late_live_points_in_build_discovery(isolated_cache, tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    put_change("reddit_live_browser", "A", 1.5, 1.0)
    put_change("reddit_web", "A", 1.2, 1.0)
    pts = store.read_points("reddit_live_browser", "A")
    late = {d for d, _ in pts[-7:]}                  # the whole recent window collected 5 days late
    evidence("reddit_live_browser", "A", [row(d, v, late_days=5 if d in late else 1) for d, v in pts])
    assert reddit(run()).change == pytest.approx(50.0)
    assert reddit(run(known_at_time=True)).change == pytest.approx(20.0)   # live drops out, the feed wins


# ---- C2 / C4: history admission, known-lag, cache ------------------------------------------------

def test_history_admits_live_stores_without_probe_record(isolated_cache, tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    put_change("reddit_live_browser", "A", 1.5, 1.0)
    res = hist.coin_history("A", 30, today=TODAY)
    assert res.history_days["reddit_live_browser"] == 130
    last = res.days[-1]
    live = next(c for c in cat(run(), "ai").coins if c.symbol == "A")
    assert (last.score, last.covered_weight) == (pytest.approx(live.raw_change), live.covered_weight)
    assert last.covered_weight == pytest.approx(25.0 + 15.0)


def test_history_keeps_legacy_gate_for_feed_methods(isolated_cache, tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    put_change("reddit_web", "A", 1.2, 1.0)   # no probe record: history keeps today's behaviour for the feeds
    res = hist.coin_history("A", 30, today=TODAY)
    assert res.history_days["reddit_web"] == 0
    assert res.days[-1].covered_weight == pytest.approx(25.0)


def test_history_applies_known_lag_and_backfilled_to_live(isolated_cache, tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    put_change("reddit_live_gql", "A", 1.5, 1.0)
    pts = store.read_points("reddit_live_gql", "A")
    evidence("reddit_live_gql", "A", [row(d, v, backfilled=d == pts[0][0], late_days=5 if d == pts[1][0] else 1)
                                      for d, v in pts])
    assert hist.coin_history("A", 30, today=TODAY).history_days["reddit_live_gql"] == 128


def test_history_cache_follows_live_evidence_sidecar(isolated_cache, tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    put_change("reddit_live_gql", "A", 1.5, 1.0)
    pts = store.read_points("reddit_live_gql", "A")
    evidence("reddit_live_gql", "A", [row(d, v) for d, v in pts])
    assert hist.coin_history("A", 30, today=TODAY).history_days["reddit_live_gql"] == 130
    evidence("reddit_live_gql", "A", [row(d, v, backfilled=d == pts[0][0]) for d, v in pts])
    assert hist.coin_history("A", 30, today=TODAY).history_days["reddit_live_gql"] == 129


def test_history_flags_the_method_switch(isolated_cache, tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    # the browser store starts later: 100 days ending END reach min_history_days (90) on END - 10, so the window
    # reads the GraphQL store before that day and the browser store from it on
    put_points("reddit_live_browser", "A", [(END - timedelta(days=99 - i), 1.0 + 0.01 * i) for i in range(100)])
    put_points("reddit_live_gql", "A", [(END - timedelta(days=129 - i), 1.0 + 0.02 * i) for i in range(130)])
    switches = hist.method_switches("A", 30, today=TODAY)
    assert switches == [((END - timedelta(days=10)).isoformat(), "reddit_live_gql", "reddit_live_browser")]
    assert hist.method_switches("A", 30, today=TODAY, source="xsearch") == []
