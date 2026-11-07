"""Finish plan 06-11-26, S-Report (AC14, RP-1..RP-3): the daily report built from day D's durable facts.

Synthetic facts, universe snapshots and completeness documents under a throwaway cache root; no network.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone

import pytest

from api.analytics.attention import daily_report as dr
from api.analytics.attention import discovery_history as hist
from api.analytics.attention.sources import _daily_report
from api.data import cache
from api.data.attention import daily_facts

D = date(2026, 11, 5)
AT = datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 7, 3, 0, tzinfo=timezone.utc)
REDDIT_ORDER = ["reddit_live_browser", "reddit_live_gql", "reddit_web", "reddit_stream"]


def none_selector(day, universe):
    return {src: {s: None for s in syms} for src, syms in universe.items()}


def snapshot(source, eligible, ambiguous=(), order=None):
    daily_facts.write_universe_snapshot(D, source, eligible_symbols=eligible, ambiguous_symbols=list(ambiguous),
                                        method_order=order or (["xsearch_web"] if source == "xsearch" else
                                                               REDDIT_ORDER), now=AT, switches={})


def doc(store, coins, **extra):
    path = cache.CACHE_ROOT / "attention" / store / "_meta" / "_completeness" / f"{D.isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"day": D.isoformat(), "coins": coins, **extra}), encoding="utf-8")
    return path


def fetched(capped=False):
    return {"reason": "fetched", "capped": capped, "attempted": True}


def build(**kw):
    return dr.rebuild(D, now=NOW, selector=kw.pop("selector", none_selector), **kw)


def test_full_day_is_100_percent_with_exact_and_estimated(isolated_cache):
    snapshot("xsearch", ["SOL", "ETH"])
    doc("xsearch_web", {"SOL": fetched(), "ETH": fetched(capped=True)})
    rep = build()
    m = rep["sources"]["xsearch"]["methods"]["xsearch_web"]
    assert (m["eligible"], m["stored"], m["exact"], m["estimated"], m["missing"]) == (2, 2, 1, 1, 0)
    assert m["coverage"] == "100% stored"
    assert rep["per_source_method"]["xsearch/xsearch_web"] == {
        "eligible": 2, "stored": 2, "exact": 1, "estimated": 1, "missing": 0, "reasons": {}}
    assert "100% stored" in dr.render(rep)


def test_partial_day_counts_missing_with_reasons_and_never_100(isolated_cache):
    syms = [f"C{i}" for i in range(1000)]
    snapshot("xsearch", syms, ambiguous=["AMB"])
    coins = {s: fetched() for s in syms[:999]}
    doc("xsearch_web", coins)
    rep = build()
    m = rep["sources"]["xsearch"]["methods"]["xsearch_web"]
    assert (m["eligible"], m["stored"], m["missing"]) == (1000, 999, 1)
    assert m["eligible"] == m["stored"] + m["missing"]
    assert m["reasons"] == {"not_recorded": 1} and m["missing_coins"] == {"C999": "not_recorded"}
    assert m["coverage"] == "99.9% stored"
    assert rep["sources"]["xsearch"]["ambiguous"] == ["AMB"]
    assert "100%" not in dr.render(rep)


def test_all_missing_is_listed_as_missing_never_zero(isolated_cache):
    snapshot("reddit", ["SOL", "ETH"])
    doc("reddit_live_browser", {"SOL": {"reason": "zero_unverified", "value": None},
                                "ETH": {"reason": "not_settled", "value": None}})
    rep = build()
    m = rep["sources"]["reddit"]["methods"]["reddit_live_browser"]
    assert (m["stored"], m["missing"], m["coverage"]) == (0, 2, "0% stored")
    assert m["missing_coins"] == {"ETH": "not_settled", "SOL": "zero_unverified"}
    text = dr.render(rep)
    assert "SOL missing (zero_unverified)" in text and "SOL 0" not in text
    for coin in rep["coins"]["reddit"].values():
        assert "value" not in coin


def test_absent_snapshot_and_documents_say_no_data_and_unknown(isolated_cache):
    doc("xsearch_web", {"SOL": fetched()})   # a document alone never recomputes the universe
    rep = build()
    assert rep["sources"]["xsearch"]["state"] == "no_data"
    assert rep["sources"]["reddit"]["state"] == "no_data"
    assert rep["per_source_method"] == {}
    assert rep["queryids"] == "unknown" and rep["containment"] == "unknown"
    text = dr.render(rep)
    assert f"no data for {D.isoformat()}" in text and "unknown" in text


def test_method_without_document_is_no_data_and_methods_are_separate(isolated_cache):
    snapshot("reddit", ["SOL", "ETH"])
    doc("reddit_live_browser", {"SOL": fetched()})
    doc("reddit_live_gql", {"SOL": fetched(), "ETH": fetched()})
    rep = build()
    methods = rep["sources"]["reddit"]["methods"]
    assert methods["reddit_web"] == {"state": "no_data"}
    assert methods["reddit_live_browser"]["stored"] == 1 and methods["reddit_live_gql"]["stored"] == 2
    assert set(rep["per_source_method"]) == {"reddit/reddit_live_browser", "reddit/reddit_live_gql"}
    assert rep["coins"]["reddit"]["ETH"]["methods"] == {"reddit_live_browser": "not_recorded",
                                                       "reddit_live_gql": "fetched"}


def test_unreadable_document_is_unknown_not_zero(isolated_cache):
    snapshot("xsearch", ["SOL"])
    doc("xsearch_web", {}).write_text("{broken", encoding="utf-8")
    rep = build()
    assert rep["sources"]["xsearch"]["methods"]["xsearch_web"] == {"state": "unknown", "reason": "unreadable"}
    assert rep["per_source_method"] == {}


def test_per_coin_selected_method_comes_from_the_selector(isolated_cache):
    snapshot("reddit", ["SOL", "ETH"])
    doc("reddit_live_gql", {"SOL": fetched(), "ETH": fetched()})
    seen = {}

    def selector(day, universe):
        seen.update(day=day, universe=universe)
        return {"reddit": {"SOL": "reddit_live_gql", "ETH": None}}

    rep = build(selector=selector)
    assert seen == {"day": D, "universe": {"reddit": ["ETH", "SOL"]}}
    assert rep["coins"]["reddit"]["SOL"]["selected_method"] == "reddit_live_gql"
    assert rep["coins"]["reddit"]["ETH"]["selected_method"] is None
    assert "ETH none" in dr.render(rep)


def test_facts_sections_from_events(isolated_cache):
    snapshot("xsearch", ["SOL"])
    doc("xsearch_web", {"SOL": fetched()})
    for ev in ({"kind": "unit_completed", "source": "xsearch_web", "account": "a1", "coin": "SOL",
                "coin_day": D.isoformat(), "reads": 3, "pages": 1, "raw_results": 9},
               {"kind": "poll_result", "source": "reddit_live_browser", "method": "browser", "account": "r1",
                "navigations": 4, "lanes": 2, "stop_reason": "complete"},
               {"kind": "poll_result", "source": "reddit_live_browser", "method": "browser", "account": "r1",
                "navigations": 1, "lanes": 0, "stop_reason": "breaker"},
               {"kind": "request_counter", "source": "reddit_live_browser", "method": "browser", "requests": 5},
               {"kind": "queryid_state", "operation": "SearchTimeline", "from_state": "ok", "to_state": "stale",
                "reason": "drift"},
               {"kind": "challenge", "source": "xsearch_web", "account": "a1", "class": "login_required"}):
        daily_facts.append(ev, now=AT, switches={})
    rep = build()
    assert rep["x_accounts"]["xsearch_web"]["a1"]["reads"] == 3
    rb = rep["reddit_methods"]["reddit_live_browser"]
    assert (rb["polls"], rb["navigations"], rb["lanes"], rb["requests"]) == (2, 5, 2, 5)
    assert rb["stop_reasons"] == {"breaker": 1, "complete": 1}
    assert rep["queryids"] == {"SearchTimeline": "stale"}
    assert rep["signals"]["challenge"] == {"login_required": 1}


def test_containment_from_admission_records(isolated_cache):
    probes = cache.CACHE_ROOT / "attention" / "_probes"
    probes.mkdir(parents=True, exist_ok=True)
    (probes / "browser_admission_abc.json").write_text(json.dumps({"outcome": "contained"}), encoding="utf-8")
    assert build()["containment"] == ["contained"]


def test_revision_is_idempotent_and_late_settle_revises(isolated_cache):
    snapshot("reddit", ["SOL"])
    doc("reddit_live_browser", {"SOL": {"reason": "not_settled", "value": None}})
    first = build()
    js, txt = dr.report_paths(D)
    assert first["revision"] == 1 and js.exists() and txt.exists()
    before = js.read_bytes()
    assert build()["revision"] == 1 and js.read_bytes() == before
    doc("reddit_live_browser", {"SOL": {"reason": "fetched", "value": 4.0}}, settled=True)
    second = dr.rebuild(D, now=NOW + timedelta(hours=1), selector=none_selector)
    assert second["revision"] == 2 and second["inputs_digest"] != first["inputs_digest"]
    last = second["revisions"][-1]
    assert last["revision"] == 2 and last["changed"] == ["completeness/reddit_live_browser"]
    assert "revised" in dr.render(second) and "completeness/reddit_live_browser" in dr.render(second)
    status = _daily_report()
    assert status.day == D.isoformat() and status.revision == 2 and status.complete is True


def test_today_or_future_day_is_refused(isolated_cache):
    with pytest.raises(ValueError):
        dr.rebuild(NOW.date(), now=NOW, selector=none_selector)


def test_atomic_write_leaves_previous_report_on_failure(isolated_cache, monkeypatch):
    snapshot("xsearch", ["SOL"])
    doc("xsearch_web", {"SOL": fetched()})
    build()
    js, _ = dr.report_paths(D)
    before = js.read_bytes()
    doc("xsearch_web", {"SOL": {"reason": "failed"}})
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        build()
    assert js.read_bytes() == before
    assert not [p for p in js.parent.iterdir() if p.suffix == ".tmp"]


def test_rebuild_recent_skips_days_without_inputs(isolated_cache):
    snapshot("xsearch", ["SOL"])
    doc("xsearch_web", {"SOL": fetched()})
    built = dr.rebuild_recent(NOW, selector=none_selector)
    assert built == [D]
    assert sorted(p.name for p in dr.report_paths(D)[0].parent.iterdir()) == [
        f"daily_report_{D.isoformat()}.json", f"daily_report_{D.isoformat()}.txt"]


def test_selected_methods_uses_pick_source_impl_over_the_stores(isolated_cache, tmp_path, monkeypatch):
    from api.tests.analytics.attention.test_discovery import END, world
    from api.tests.analytics.attention.test_discovery_reddit_cutover import ORDER, put_points

    hist.clear_cache()
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]}, source_impl={"reddit": ORDER})
    put_points("reddit_live_gql", "A", [(END - timedelta(days=129 - i), 1.0 + 0.02 * i) for i in range(130)])
    got = dr.selected_methods(END, {"reddit": ["A", "B"], "xsearch": ["A"]})
    assert got == {"reddit": {"A": "reddit_live_gql", "B": None}, "xsearch": {"A": None}}
