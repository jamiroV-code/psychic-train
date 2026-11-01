"""W8e2 (AC38, AC39, AC47, AC52): the read-only health fields on the PC sources' rows, from state and evidence
files only. Every path is redirected to tmp_path; the clock is passed in."""
from __future__ import annotations

import dataclasses
import json
import socket
from datetime import datetime, time, timedelta, timezone

import pytest

from api.analytics.attention import sources as src
from api.data import cache
from api.data.attention import pc_pace, reddit_web, web_evidence, web_queries
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import END, world

COINS = {"A": 5e7, "B": 5e7, "C": 5e7}
NOW = datetime.combine(TODAY, time(12), tzinfo=timezone.utc)


def row(res, sid):
    return next(r for r in res.sources if r.id == sid)


@pytest.fixture
def live(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.delenv("X_LIVE", raising=False)
    world(tmp_path, monkeypatch, COINS, cats={"ai": list(COINS)},
          source_impl={"xsearch": "xsearch_web", "reddit": "reddit_web"})
    monkeypatch.setattr(web_queries, "QUERIES_PATH", tmp_path / "no_queries.json")
    src.clear_cache()
    return tmp_path


def put_state(source, **over):
    s = {"budget_day": TODAY.isoformat(), "used": 120, "spent_day": None, "effective": 400, "clean_days": 2,
         "activity": {"day": TODAY.isoformat(), "units": 3, "warned": False}, "pause_until": None,
         "pause_reason": None, "last_unit_at": (NOW - timedelta(minutes=30)).isoformat()} | over
    p = pc_pace.state_path(source)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s), encoding="utf-8")
    gap = 8640 if source == "xsearch_web" else 28800
    p.with_name(f"{source}_health.json").write_text(json.dumps(
        {"mode": "baseline", "expected_gap_s": gap, "observed_at": NOW.isoformat()}))
    return p


def put_x_evidence(symbol, *, capped=False, collected=NOW - timedelta(hours=2)):
    p = web_evidence.evidence_path("xsearch_web", symbol)
    p.parent.mkdir(parents=True, exist_ok=True)
    r = web_evidence.EvidenceRow(END, 5.0, 40, 6.0, capped, False, False, "x", collected, False)
    p.write_text(json.dumps({"rows": [r.to_json()]}), encoding="utf-8")


def coin(reason, *, capped=False, collected=NOW - timedelta(hours=4), newest=None):
    return {"reason": reason, "attempted": reason != "not_reached", "capped": capped,
            "collected_at": collected.isoformat() if collected else None,
            "newest": newest.isoformat() if newest else None}


def put_completeness(coins, source="reddit_web", day=END):
    p = cache.CACHE_ROOT / "attention" / source / "_meta" / "_completeness" / f"{day.isoformat()}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"day": day.isoformat(), "requests": 3, "budget_cut": False, "canary": None,
                             "coins": coins}), encoding="utf-8")


def test_health_payload_has_last_unit_pause_reason_attempted_fetched_budget(live, monkeypatch):
    put_state("xsearch_web")
    put_x_evidence("A")
    put_x_evidence("B")
    put_completeness({"A": coin("fetched"), "B": coin("fetched"), "C": coin("failed")}, "xsearch_web")
    pool = cache.CACHE_ROOT / "attention" / "_pc_state" / "x_pool.json"
    pool.write_text(json.dumps({
        "accounts": {"a1": {"state": "active", "reason": None, "last_used": NOW.isoformat(), "lock_until": None,
                            "last_canary": None, "suspect_since": None},
                     "a2": {"state": "inactive", "reason": "x_login_required", "last_used": None,
                            "lock_until": None, "last_canary": None, "suspect_since": None}},
        "alerts": [], "pause_until": None, "pause_reason": None, "stopped": None, "drift_streak": 0,
        "canary_day": None, "canary_note": None, "canary_labels": [], "curl_uses": 0, "curl_last_use": None}))
    acc = live / "accounts"
    acc.mkdir()
    (acc / "cookie_ages.json").write_text(json.dumps({"a1": (NOW - timedelta(days=4)).isoformat()}))
    base = web_queries.validate_config(dict(web_queries.DEFAULTS))
    monkeypatch.setattr(src, "_collector", lambda: dataclasses.replace(
        base, x_accounts=("a1", "a2"), x_accounts_db_path=str(acc)))
    h = row(src.build_sources(TODAY, now=NOW), "xsearch").health
    assert h is not None
    assert h.last_unit_at == (NOW - timedelta(minutes=30)).isoformat()
    assert (h.paused, h.pause_reason, h.pause_until) == (False, None, None)
    assert (h.attempted, h.fetched, h.budget_used, h.effective_budget) == (3, 2, 120, 400)
    assert (h.accounts_active, h.accounts_total) == (1, 2)
    by = {a.label: a for a in h.accounts}
    assert (by["a1"].state, by["a1"].cookie_age_days) == ("active", 4)
    assert (by["a2"].state, by["a2"].reason, by["a2"].cookie_age_days) == ("inactive", "x_login_required", None)
    assert h.free_disk_bytes > 0 and h.clock_sync_age_seconds is None


def test_paused_source_shows_reason_code_and_end(live):
    until = datetime.combine(TODAY + timedelta(days=1), time(0), tzinfo=timezone.utc).isoformat()
    put_state("reddit_web", pause_reason="rate_limited", pause_until=until)
    h = row(src.build_sources(TODAY, now=NOW), "reddit").health
    assert (h.paused, h.pause_reason, h.pause_until) == (True, "rate_limited", until)
    put_state("reddit_web", pause_reason="x_login_required", pause_until=None)   # owner action: no end
    h = row(src.build_sources(TODAY, now=NOW), "reddit").health
    assert (h.paused, h.pause_reason, h.pause_until) == (True, "x_login_required", None)
    past = (NOW - timedelta(hours=1)).isoformat()
    put_state("reddit_web", pause_reason="rate_limited", pause_until=past)        # a day pause that ended
    h = row(src.build_sources(TODAY, now=NOW), "reddit").health
    assert (h.paused, h.pause_reason) == (False, None)


def test_stale_after_twice_the_expected_gap(live):
    # X defaults: 400 effective / 40 per unit = 10 units a day -> gap 8640 s, stale after 17280 s
    put_state("xsearch_web", last_unit_at=(NOW - timedelta(hours=4)).isoformat())
    h = row(src.build_sources(TODAY, now=NOW), "xsearch").health
    assert (h.expected_gap_s, h.stale) == (8640, False)
    put_state("xsearch_web", last_unit_at=(NOW - timedelta(seconds=17280)).isoformat())
    assert row(src.build_sources(TODAY, now=NOW), "xsearch").health.stale is False
    put_state("xsearch_web", last_unit_at=(NOW - timedelta(hours=5)).isoformat())
    assert row(src.build_sources(TODAY, now=NOW), "xsearch").health.stale is True
    # Reddit: max(120 s, 24 h / 3 coins) = 28800 s, stale after 16 h
    put_state("reddit_web", last_unit_at=(NOW - timedelta(hours=15)).isoformat())
    h = row(src.build_sources(TODAY, now=NOW), "reddit").health
    assert (h.expected_gap_s, h.stale) == (28800, False)
    put_state("reddit_web", last_unit_at=(NOW - timedelta(hours=17)).isoformat())
    h = row(src.build_sources(TODAY, now=NOW), "reddit").health
    assert h.stale is True and "stale" in h.completeness
    put_state("reddit_web", last_unit_at=None)                                    # never ran a unit
    assert row(src.build_sources(TODAY, now=NOW), "reddit").health.stale is True


def test_completeness_text_attempted_fetched_missing_reasons_capped_newest_age(live):
    put_state("reddit_web")
    put_completeness({"A": coin("fetched", capped=True, collected=NOW - timedelta(hours=3),
                                newest=NOW - timedelta(hours=20)),
                      "B": coin("fetched", collected=NOW - timedelta(hours=5)),
                      "C": coin("blocked")})
    h = row(src.build_sources(TODAY, now=NOW), "reddit").health
    assert (h.attempted, h.fetched, h.missing, h.missing_reasons, h.capped) == (3, 2, 1, {"blocked": 1}, 1)
    assert h.newest_age_hours == 3.0
    assert h.completeness == f"{END.isoformat()}: attempted 3, fetched 2, missing 1 (blocked 1), capped 1, newest 3h old"


def test_health_reads_files_only_no_network(live, monkeypatch):
    p = put_state("xsearch_web")
    put_state("reddit_web")
    before = p.read_bytes()

    def refuse(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(pc_pace.PcSource, "__init__", refuse)  # do not invoke the mutating day-roll object
    res = src.build_sources(TODAY + timedelta(days=3), now=NOW + timedelta(days=3))   # a later day: no roll
    assert row(res, "xsearch").health is not None and row(res, "reddit").health is not None
    assert p.read_bytes() == before                                               # read only, never written
    assert row(res, "xsearch").health.budget_used == 0                            # a past day's count is not today's


def test_existing_sources_rows_unchanged_when_no_worker_state(live):
    res = src.build_sources(TODAY, now=NOW)
    assert all(r.health is None for r in res.sources)
    assert not (cache.CACHE_ROOT / "attention" / "_pc_state").exists()
    baseline = src.build_sources(TODAY)
    assert [r.model_dump() for r in baseline.sources] == [r.model_dump() for r in res.sources]
    assert all("health" not in r.model_dump() for r in res.sources)


def test_historical_unknowns_are_not_fabricated_from_units(live):
    p = put_state("xsearch_web")
    p.with_name("xsearch_web_health.json").unlink()
    put_x_evidence("A")
    h = row(src.build_sources(TODAY, now=NOW), "xsearch").health
    assert h.attempted is None and h.fetched is None
    assert h.expected_gap_s is None and h.stale is None
    assert h.completeness_attempted is None and h.missing_reasons is None
    assert "attempted unknown" in h.completeness


def test_collection_counts_exclude_old_attempts_and_include_backfill(live):
    put_state("reddit_web")
    put_completeness({"A": coin("fetched"), "B": coin("fetched", collected=NOW - timedelta(days=1))})
    put_completeness({"A": coin("failed")}, day=END - timedelta(days=1))
    h = row(src.build_sources(TODAY, now=NOW), "reddit").health
    assert (h.attempted, h.fetched) == (2, 1)
    assert (h.completeness_attempted, h.completeness_fetched) == (2, 2)
    assert h.collection_day == TODAY.isoformat() and h.completeness_day == END.isoformat()


@pytest.mark.parametrize("raw", ["broken", "[]", "{}"])
def test_bad_state_is_read_only_and_unknown_not_zero(live, raw):
    p = put_state("reddit_web")
    p.write_text(raw)
    h = row(src.build_sources(TODAY, now=NOW), "reddit").health
    assert h.paused and h.pause_reason == "state_error"
    assert h.attempted is None and h.effective_budget is None and h.stale is None
    assert p.read_text() == raw


# --- idle by design (budget spent, timed pause) is not stale; a stuck source still is (AC39) ---
NEXT_DUE = datetime.combine(TODAY + timedelta(days=1), time(0), tzinfo=timezone.utc) + timedelta(
    seconds=pc_pace.BEHIND_DELAY_S)
GAP = 360  # the degraded X in-day gap from the real run


def put_spent(source="xsearch_web", **over):
    p = put_state(source, **({"used": 792, "effective": 800, "spent_day": TODAY.isoformat(),
                              "last_unit_at": (NOW - timedelta(hours=10)).isoformat()} | over))
    p.with_name(f"{source}_health.json").write_text(json.dumps(
        {"mode": "degraded", "expected_gap_s": GAP, "observed_at": NOW.isoformat()}))
    return p


def x_health(now, day=TODAY):
    return row(src.build_sources(day, now=now), "xsearch").health


def test_budget_spent_idle_until_next_day_is_not_stale(live):
    put_spent()
    for now in (NOW, NEXT_DUE - timedelta(seconds=1), NEXT_DUE + timedelta(seconds=2 * GAP)):
        h = x_health(now, now.date())
        assert (h.stale, h.paused, h.pause_reason) == (False, False, None), now
    h = x_health(NOW)
    assert h.budget_spent is True and h.expected_gap_s == GAP
    put_spent(spent_day=None, used=800)                                          # spent by count, not marked
    assert x_health(NOW).stale is False


def test_budget_spent_stale_again_after_next_due_plus_two_gaps(live):
    put_spent()
    late = NEXT_DUE + timedelta(seconds=2 * GAP + 1)
    h = x_health(late, late.date())
    assert h.stale is True and h.completeness.endswith("; stale")
    put_spent(spent_day=None, used=800)
    assert x_health(late, late.date()).stale is True
    put_spent(last_unit_at=(NEXT_DUE + timedelta(seconds=GAP)).isoformat())     # the worker resumed on time
    assert x_health(late, late.date()).stale is False


def test_future_pause_until_idle_is_not_stale(live):
    until = datetime.combine(TODAY + timedelta(days=1), time(0), tzinfo=timezone.utc)
    put_spent(used=120, spent_day=None, pause_reason="rate_limited", pause_until=until.isoformat())
    h = x_health(NOW)
    assert (h.paused, h.pause_reason, h.stale) == (True, "rate_limited", False)
    assert not h.completeness.endswith("; stale")
    edge = until + timedelta(seconds=2 * GAP)
    assert x_health(edge, edge.date()).stale is False
    late = edge + timedelta(seconds=1)
    h = x_health(late, late.date())
    assert (h.paused, h.stale) == (False, True)


def test_owner_action_pause_keeps_existing_stale_rule(live):
    put_spent(used=120, spent_day=None, pause_reason="x_login_required", pause_until=None)
    h = x_health(NOW)
    assert (h.paused, h.pause_reason, h.pause_until, h.stale) == (True, "x_login_required", None, True)
    assert h.completeness.endswith("; stale")
    put_spent(used=120, spent_day=None, pause_reason="x_login_required", pause_until=None,
              last_unit_at=(NOW - timedelta(seconds=GAP)).isoformat())
    assert x_health(NOW).stale is False


def test_stuck_source_without_budget_spent_is_still_stale(live):
    put_spent(used=300, spent_day=None, last_unit_at=(NOW - timedelta(seconds=2 * GAP + 1)).isoformat())
    h = x_health(NOW)
    assert (h.budget_spent, h.paused, h.stale) == (False, False, True)
    assert h.completeness.endswith("; stale")
    put_spent(used=300, spent_day=None, last_unit_at=None)                        # never ran a unit
    assert x_health(NOW).stale is True
    yesterday = (TODAY - timedelta(days=1)).isoformat()                           # an old spent day ended long ago
    put_spent(budget_day=yesterday, used=800, spent_day=yesterday)
    assert x_health(NOW).stale is True


def test_completeness_text_has_no_stale_suffix_when_waiting_by_design(live):
    put_spent()
    h = x_health(NOW)
    assert "stale" not in h.completeness
    assert h.completeness.endswith("; waiting for next UTC day")
    late = NEXT_DUE + timedelta(seconds=2 * GAP + 1)
    assert "waiting" not in x_health(late, late.date()).completeness


def test_rows_without_worker_state_unchanged(live):
    baseline = [r.model_dump() for r in src.build_sources(TODAY, now=NOW).sources]
    put_spent()
    res = src.build_sources(TODAY, now=NOW)
    assert row(res, "xsearch").health is not None
    assert row(res, "reddit").health is None and "health" not in row(res, "reddit").model_dump()
    assert ([r.model_dump() for r in res.sources if r.id != "xsearch"]
            == [r for r in baseline if r["id"] != "xsearch"])
