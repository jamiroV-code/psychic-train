"""Finish plan 06-11-26 S-StatusAPI: optional, allowlisted status fields read from files only (AC13, AC14).

Every producer file is seeded under the isolated cache; no network, no writes, all-off wire shape unchanged."""
from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from api.analytics.attention import sources as src
from api.data.attention import web_queries
from api.models.discovery import (DiscoveryAccountHealth, DiscoveryCollectorStatus, DiscoveryRedditAccountHealth,
                                  DiscoveryRedditMethodHealth, DiscoverySourceHealth)
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_sources import live, row  # noqa: F401 (fixture)

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
DAY = NOW.date().replace(day=6)
SECRET = "SECRET-MARKER-7f3a"


def cfg(**changes):
    return dataclasses.replace(web_queries.load().config, **changes)


def put(root, rel, doc):
    path = root / "attention" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return path


def completeness(root, store_id, day):
    put(root, f"{store_id}/_meta/_completeness/{day}.json", {"coins": {"BTC": {"reason": "fetched"}}})


REDDIT = dict(reddit_live_methods=("browser",), reddit_surface_path="C:/private/surface.json",
              reddit_browser_accounts=({"label": "r-one", "profile": "r_one"}, {"label": "r-two", "profile": "r_two"},
                                       {"label": "r-three", "profile": "r_three"}))


# --- method-health reader --------------------------------------------------------------------------------------------

def test_method_rows_are_omitted_while_reddit_live_is_off(isolated_cache):
    assert src.reddit_methods(cfg(), DAY, NOW) is None
    assert src.reddit_accounts(cfg(), NOW) is None


def test_one_row_per_method_never_merged(isolated_cache):
    put(isolated_cache, "_pc_state/reddit_live/reddit_live_browser_health.json", {
        "state": "needs_probe", "reason": "needs_probe", "lanes": {"posts": 1.0, "comments": 0.75},
        "comments_scope": "threads_opened", "requests_today": 40, "cap": 400, "token": SECRET})
    put(isolated_cache, "_pc_state/reddit_live/reddit_live_gql_health.json", {"state": "ok"})   # switch off
    completeness(isolated_cache, "reddit_live_browser", "2026-11-05")
    completeness(isolated_cache, "reddit_live_browser", "2026-11-04")
    rows = src.reddit_methods(cfg(**REDDIT), DAY, NOW)
    assert [r.method for r in rows] == list(web_queries.REDDIT_METHODS)
    browser, gql, web, stream = rows
    assert (browser.state, browser.reason, browser.last_settled_day, browser.lanes, browser.comments_scope,
            browser.requests_today, browser.cap) == ("needs_probe", "needs_probe", "2026-11-05",
                                                    {"posts": 1.0, "comments": 0.75}, "threads_opened", 40, 400)
    assert (gql.state, gql.reason, gql.last_settled_day) == ("disabled", "method_disabled", None)
    assert web.state == stream.state == "unknown"      # no worker state: unknown, never ok
    assert SECRET not in json.dumps([r.model_dump() for r in rows])


@pytest.mark.parametrize("doc", [
    "{not json", [], {"state": "fine"}, {"state": "ok", "reason": f"https://x.invalid/{SECRET}"},
    {"state": "ok", "lanes": {"posts": 2}}, {"state": "ok", "requests_today": -1, "cap": True}])
def test_malformed_method_evidence_is_unknown_never_success(isolated_cache, doc):
    put(isolated_cache, "_pc_state/reddit_live/reddit_live_browser_health.json", doc)
    browser = src.reddit_methods(cfg(**REDDIT), DAY, NOW)[0]
    dumped = json.dumps(browser.model_dump())
    assert SECRET not in dumped and "invalid" not in dumped
    if not (isinstance(doc, dict) and doc.get("state") == "ok"):
        assert browser.state == "unknown"
    assert browser.lanes is None or all(0 <= v <= 1 for v in browser.lanes.values())
    assert browser.requests_today is None and (browser.cap is None or browser.cap >= 0)


def test_enabled_method_without_evidence_is_unknown(isolated_cache):
    assert src.reddit_methods(cfg(**REDDIT), DAY, NOW)[0].state == "unknown"


def test_feed_row_reuses_the_worker_health():
    h = DiscoverySourceHealth(collection_day="2026-11-07", completeness_day="2026-11-06", completeness="",
                              paused=True, pause_reason="http_429", budget_used=12, effective_budget=300)
    web = src._feed_method("reddit_web", DAY, NOW, {"reddit_web": h})
    assert (web.state, web.reason, web.requests_today, web.cap) == ("degraded", "http_429", 12, 300)
    h.paused, h.stale = False, True
    assert src._feed_method("reddit_web", DAY, NOW, {"reddit_web": h}).state == "stale"
    h.stale = False
    assert src._feed_method("reddit_web", DAY, NOW, {"reddit_web": h}).state == "ok"


def test_pc_stores_stream_exclusion_contract_is_unchanged():
    assert src.PC_STORES == frozenset({"xsearch_web", "reddit_web"})


# --- Reddit account model --------------------------------------------------------------------------------------------

def test_reddit_accounts_use_their_own_model(isolated_cache):
    put(isolated_cache, "_pc_state/reddit_accounts.json", {"accounts": {
        "r-one": {"state": "resting", "reason": "resting", "reads_day": "2026-11-07", "reads_used": 17,
                  "rest_until": "2026-11-10T00:00:00+00:00", "session_state": "logged_in",
                  "session_checked_at": "2026-11-07T08:00:00+00:00", "proxy_state": "healthy", "cookie": SECRET},
        "r-two": {"state": "active", "reason": None, "reads_day": "2026-11-06", "reads_used": 90,
                  "rest_until": "2026-11-10T01:00:00+02:00", "session_state": f"x {SECRET}"},
        "not-configured": {"state": "active"}}})
    put(isolated_cache, "_pc_state/reddit_account_ready.json", {"ready": {"r-one": "2026-11-06",
                                                                          "r-two": "2026-11-07"}})
    one, two, three = src.reddit_accounts(cfg(**REDDIT), NOW)
    assert all(isinstance(a, DiscoveryRedditAccountHealth) for a in (one, two, three))
    assert (one.state, one.reason, one.reads_today, one.cap, one.ready, one.session_state, one.proxy_state) == (
        "resting", "resting", 17, 200, True, "logged_in", "healthy")
    assert (two.state, two.reads_today, two.ready, two.rest_until, two.session_state) == (
        "active", 0, False, None, None)                 # marked today joins tomorrow; non-UTC/unsafe → unknown
    assert (three.label, three.state, three.ready) == ("r-three", "unknown", False)
    text = json.dumps([a.model_dump() for a in (one, two, three)])
    assert SECRET not in text and "not-configured" not in text


def test_reddit_accounts_without_files_are_unknown(isolated_cache):
    rows = src.reddit_accounts(cfg(**REDDIT), NOW)
    assert [(a.state, a.ready, a.reads_today) for a in rows] == [("unknown", None, None)] * 3


def test_reddit_account_state_literals_are_not_x_states():
    with pytest.raises(ValidationError):
        DiscoveryRedditAccountHealth(label="r-one", state="suspect")
    with pytest.raises(ValidationError):
        DiscoveryAccountHealth(label="x-one", state="resting")
    with pytest.raises(ValidationError):
        DiscoveryRedditAccountHealth(label="user@example.com")


# --- X additions -----------------------------------------------------------------------------------------------------

BASE = dict(label="acct-1", state="active", proxy_state="healthy", proxy_reason="proxy_region")


def test_x_account_finish_fields_round_trip_and_are_omitted_when_absent():
    full = src._project_account({**BASE, "endpoint_state": "restricted", "ct0_rotations_seen": 2,
                                 "behaviour": {"cooldown_reason": "shrink", "effective_cap": 600,
                                               "quiet_until": "2026-11-07T22:00:00+00:00"},
                                 "harvest": {"state": "needs_owner", "reason": "x_login_required"}})
    row = json.loads(full.model_dump_json())
    assert row["endpoint_state"] == "restricted" and row["behaviour"]["effective_cap"] == 600
    assert row["harvest"]["state"] == "needs_owner" and row["proxy_state"] == "healthy"
    legacy = json.loads(DiscoveryAccountHealth(label="acct-1", state="active").model_dump_json())
    assert not {"endpoint_state", "behaviour", "harvest", "ct0_rotations_seen"} & legacy.keys()


@pytest.mark.parametrize("bad", [{"behaviour": {"cooldown_reason": SECRET}}, {"endpoint_state": SECRET},
                                 {"harvest": {"last_at": "2026-11-07T01:00:00"}}, {"ct0_rotations_seen": -1}])
def test_malformed_finish_group_is_refused_whole_and_proxy_kept(bad):
    projected = src._project_account({**BASE, **bad})
    row = json.loads(projected.model_dump_json())
    assert row["endpoint_state"] == "unknown" and "behaviour" not in row and "harvest" not in row
    assert row["proxy_state"] == "healthy" and SECRET not in json.dumps(row)


def test_malformed_legacy_state_still_raises():
    with pytest.raises(ValidationError):
        src._project_account({**BASE, "state": SECRET})


# --- query ids -------------------------------------------------------------------------------------------------------

def test_queryids_omitted_while_off_and_unchecked(isolated_cache):
    assert src._queryids(cfg(), NOW) is None
    assert src._queryids(cfg(x_queryid_mode="sentinel"), NOW).state == "unknown"


def test_queryids_report_state_source_and_age(isolated_cache):
    put(isolated_cache, "_pc_state/x_queryids.json", {
        "version": 1, "check_state": "candidate", "last_check": "2026-11-07T06:00:00+00:00",
        "operations": {"SearchTimeline": {"active": {"id": "a" * 22, "source": "pinned",
                                                     "adopted_at": "2026-11-01T00:00:00+00:00"}},
                       "UserByScreenName": {"active": {"id": "b" * 22, "source": "bundle",
                                                       "adopted_at": "2026-11-05T00:00:00+00:00"}}}})
    q = src._queryids(cfg(x_queryid_mode="auto"), NOW)
    assert (q.mode, q.state, q.active_source, q.active_age_days, q.last_check) == (
        "auto", "candidate", "mixed", 6, "2026-11-07T06:00:00+00:00")
    assert "a" * 22 not in q.model_dump_json()


# --- collector: daily report, doctor, browser ------------------------------------------------------------------------

def counts(eligible, stored, missing=0):
    return {"eligible": eligible, "stored": stored, "exact": stored, "estimated": 0, "missing": missing,
            "reasons": {"lane_incomplete": missing} if missing else {}}


def test_daily_report_newest_and_complete_rule(isolated_cache):
    assert src._daily_report() is None
    put(isolated_cache, "_reports/daily_report_2026-11-05.json", {"revision": 1, "per_source_method": {
        "xsearch/xsearch_web": counts(72, 72)}})
    put(isolated_cache, "_reports/daily_report_2026-11-06.json", {"revision": 3, "per_source_method": {
        "xsearch/xsearch_web": counts(72, 72), "reddit/reddit_live_browser": counts(72, 70, 2)}})
    put(isolated_cache, "_reports/daily_report_notaday.json", {})
    report = src._daily_report()
    assert (report.day, report.revision, report.complete) == ("2026-11-06", 3, False)
    assert report.per_source_method["reddit/reddit_live_browser"].reasons == {"lane_incomplete": 2}
    put(isolated_cache, "_reports/daily_report_2026-11-06.json", {"revision": 4, "per_source_method": {
        "xsearch/xsearch_web": counts(72, 72)}})
    assert src._daily_report().complete is True
    put(isolated_cache, "_reports/daily_report_2026-11-06.json", {"per_source_method": {"x": counts(0, 0)}})
    assert (src._daily_report().complete, src._daily_report().per_source_method) == (None, None)
    put(isolated_cache, "_reports/daily_report_2026-11-06.json", {"per_source_method": {
        "xsearch/xsearch_web": counts(0, 0)}})
    assert src._daily_report().complete is False        # 100% only when eligible > 0


def test_doctor_counts_only(isolated_cache):
    assert src._doctor() is None
    put(isolated_cache, "_reports/doctor.json", {"state": "WARN", "checked_at": "2026-11-07T05:00:00+00:00",
                                                 "failures": [], "warnings": [f"proxy at {SECRET}"]})
    d = src._doctor()
    assert (d.state, d.failures, d.warnings) == ("WARN", 0, 1) and SECRET not in d.model_dump_json()
    put(isolated_cache, "_reports/doctor.json", {"state": "PASSED"})
    assert src._doctor().state == "UNKNOWN"
    put(isolated_cache, "_reports/doctor.json", "garbage")
    assert (src._doctor().state, src._doctor().failures) == ("UNKNOWN", None)


def test_browser_refusals_bounded_hostnames_only(isolated_cache):
    assert src._browser() is None
    refusals = {f"h{i}.example.net": i for i in range(8)}
    refusals.update({"192.0.2.1": 99, f"https://{SECRET}.invalid/x": 99, "user:pw@host.example": 99})
    put(isolated_cache, "_pc_state/browser_health.json", {"relay_refusals": refusals, "profile_state": "ok"})
    b = src._browser()
    assert [r.host for r in b.relay_refusals] == [f"h{i}.example.net" for i in (7, 6, 5, 4, 3)]
    assert b.profile_state == "ok" and SECRET not in b.model_dump_json() and "192.0.2.1" not in b.model_dump_json()


def test_collector_model_omits_absent_optional_blocks():
    dumped = DiscoveryCollectorStatus(state="unknown").model_dump()
    assert not {"daily_report", "doctor", "browser"} & dumped.keys()


# --- end to end through build_sources --------------------------------------------------------------------------------

def test_all_off_wire_shape_is_unchanged(live):
    res = json.loads(src.build_sources(TODAY).model_dump_json())
    for r in res["sources"]:
        assert "health" not in r or not {"methods", "queryids"} & r["health"].keys()
    assert not {"daily_report", "doctor", "browser"} & res["collector"].keys()
    assert all("methods" not in s for s in res["collector"]["sources"])


def test_reddit_row_and_collector_carry_method_rows(live, monkeypatch):
    monkeypatch.setattr(src, "_collector", lambda: cfg(**REDDIT))
    put(live, "_pc_state/reddit_live/reddit_live_browser_health.json", {"state": "blocked", "reason": "cap"})
    put(live, "_reports/doctor.json", {"state": "FAIL", "failures": ["a", "b"]})
    res = src.build_sources(TODAY, now=NOW)
    health = row(res, "reddit").health
    assert [m.state for m in health.methods] == ["blocked", "disabled", "unknown", "unknown"]
    assert health.accounts_total == 3 and health.accounts_active == 0
    assert all(isinstance(a, DiscoveryRedditAccountHealth) for a in health.accounts)
    reddit_box = next(s for s in res.collector.sources if s.id == "reddit")
    assert reddit_box.methods == health.methods
    assert (res.collector.doctor.state, res.collector.doctor.failures) == ("FAIL", 2)
    wire = json.loads(res.model_dump_json())
    accounts = next(r for r in wire["sources"] if r["id"] == "reddit")["health"]["accounts"]
    assert {a["site"] for a in accounts} == {"reddit"}
    assert isinstance(DiscoveryRedditMethodHealth(**health.methods[0].model_dump()), DiscoveryRedditMethodHealth)
