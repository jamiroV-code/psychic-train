"""Contract D (collector-identity-pool finish plan): durable nonsecret daily facts and the universe snapshot."""
from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta, timezone

import pytest

from api.data.attention import daily_facts as df

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
SWITCHES = {"x_quiet_hours_enabled": False, "facts_retention_days": 180, "reddit_live_methods": ["browser"]}


def _unit(account="acct_a", coin="BTC", reads=3):
    return {"kind": "unit_completed", "source": "x", "account": account, "coin": coin, "coin_day": "2026-11-06",
            "reads": reads, "pages": 2, "raw_results": 40}


def test_path_follows_cache_root(isolated_cache):
    assert df.events_path(date(2026, 11, 7)) == isolated_cache / "attention" / "_facts" / "events_2026-11-07.jsonl"


def test_first_event_of_day_records_switch_provenance_then_event(isolated_cache):
    assert df.append(_unit(), now=NOW, switches=SWITCHES)
    events = df.read_events(NOW.date())
    assert [e["kind"] for e in events] == ["switch_provenance", "unit_completed"]
    assert events[0]["switches"] == SWITCHES
    assert events[1]["ts"] == "2026-11-07T12:00:00Z" and events[1]["v"] == df.SCHEMA_VERSION


def test_switch_change_during_day_is_recorded_once(isolated_cache):
    df.append(_unit(), now=NOW, switches=SWITCHES)
    df.append(_unit(), now=NOW + timedelta(minutes=1), switches=SWITCHES)
    changed = {**SWITCHES, "x_quiet_hours_enabled": True}
    df.append(_unit(), now=NOW + timedelta(minutes=2), switches=changed)
    df.append(_unit(), now=NOW + timedelta(minutes=3), switches=changed)
    kinds = [e["kind"] for e in df.read_events(NOW.date())]
    assert kinds.count("switch_provenance") == 2
    assert df.summarize(df.read_events(NOW.date()))["switches"] == [SWITCHES, changed]


def test_rollover_never_rewrites_yesterday(isolated_cache):
    late = datetime(2026, 11, 6, 23, 59, 59, tzinfo=timezone.utc)
    df.append(_unit(reads=5), now=late, switches=SWITCHES)
    before = df.events_path(late.date()).read_bytes()
    df.append(_unit(reads=1), now=late + timedelta(seconds=2), switches=SWITCHES)
    assert df.events_path(late.date()).read_bytes() == before
    assert df.summarize(df.read_events(late.date()))["accounts"]["x"]["acct_a"]["reads"] == 5
    assert df.summarize(df.read_events(NOW.date()))["accounts"]["x"]["acct_a"]["reads"] == 1


def test_naive_or_non_utc_clock_rejected(isolated_cache):
    with pytest.raises(ValueError):
        df.append(_unit(), now=datetime(2026, 11, 7, 12), switches=SWITCHES)


@pytest.mark.parametrize("event", [
    {"kind": "not_a_kind", "source": "x"},
    {**_unit(), "cookie": "abc"},
    {**_unit(), "auth_token": "abc"},
    {**_unit(), "extra_field": 1},
    {**_unit(), "account": "a=b; ct0=zz"},
    {**_unit(), "reads": -1},
    {**_unit(), "reads": True},
    {"kind": "switch_provenance", "switches": {}},
    {"kind": "universe_snapshot", "day": "2026-11-07", "source": "x", "eligible_symbols": [],
     "ambiguous_symbols": [], "method_order": []},
])
def test_event_allowlist_and_no_secret_fields(isolated_cache, event):
    with pytest.raises(ValueError):
        df.append(event, now=NOW, switches=SWITCHES)
    assert not df.events_path(NOW.date()).exists()


@pytest.mark.parametrize("switches", [{"proxy_password": "x"}, {"x_token": "a"}, {"k": "has space"},
                                      {"k": {"n": {"deep": 1}}}])
def test_switches_must_be_nonsecret(isolated_cache, switches):
    with pytest.raises(ValueError):
        df.append(_unit(), now=NOW, switches=switches)


def test_written_bytes_hold_no_secret_markers(isolated_cache):
    df.append(_unit(), now=NOW, switches=SWITCHES)
    df.append({"kind": "session_check", "source": "x", "account": "acct_a", "result_class": "ok",
               "cookie_age_class": "lt_7d"}, now=NOW, switches=SWITCHES)
    text = df.events_path(NOW.date()).read_text("utf-8")
    for marker in ("ct0=", "auth_token", "password", "Bearer"):
        assert marker not in text


def test_each_allowlisted_kind_accepted(isolated_cache):
    samples = [
        {"kind": "handoff", "source": "reddit", "from_account": "rd_a", "to_account": "rd_b", "reason": "cap"},
        {"kind": "account_state", "source": "x", "account": "acct_a", "state": "quarantine",
         "reason": "proxy_quarantined"},
        {"kind": "challenge", "source": "reddit", "account": "rd_a", "class": "login_required"},
        {"kind": "cooldown", "source": "x", "account": "acct_a", "action": "set",
         "until": "2026-11-07T13:00:00Z"},
        {"kind": "session_check", "source": "x", "account": "acct_a", "result_class": "ok",
         "cookie_age_class": "lt_7d"},
        {"kind": "queryid_state", "operation": "SearchTimeline", "from_state": "active", "to_state": "candidate",
         "reason": "endpoint_404"},
        {"kind": "mixed_call", "source": "x", "account": "acct_a", "target": "home", "reads": 1},
        {"kind": "poll_result", "source": "reddit", "method": "browser", "account": "rd_a", "navigations": 4,
         "lanes": 3, "stop_reason": "settled"},
        {"kind": "request_counter", "source": "reddit", "method": "gql_anon", "requests": 12},
    ]
    for ev in samples:
        assert df.append(ev, now=NOW, switches=SWITCHES)
    summary = df.summarize(df.read_events(NOW.date()))
    assert summary["kinds"]["handoff"] == 1 and summary["kinds"]["request_counter"] == 1
    assert summary["requests"] == {"reddit": {"gql_anon": 12}}
    assert summary["reasons"] == {"proxy_quarantined": 1}


@pytest.mark.parametrize("event", [
    {"kind": "account_state", "source": "x", "account": "acct_a", "state": "vanished", "reason": "unknown"},
    {"kind": "challenge", "source": "x", "account": "acct_a", "class": "captcha_solved"},
    {"kind": "cooldown", "source": "x", "account": "acct_a", "action": "extended"},
])
def test_enumerated_values_enforced(isolated_cache, event):
    with pytest.raises(ValueError):
        df.append(event, now=NOW, switches=SWITCHES)


def test_summarizer_totals_per_source_and_account(isolated_cache):
    df.append(_unit("acct_a", "BTC", 3), now=NOW, switches=SWITCHES)
    df.append(_unit("acct_a", "ETH", 2), now=NOW, switches=SWITCHES)
    df.append(_unit("acct_b", "SOL", 4), now=NOW, switches=SWITCHES)
    s = df.summarize(df.read_events(NOW.date()))
    assert s["accounts"]["x"]["acct_a"] == {"units": 2, "reads": 5, "pages": 4, "raw_results": 80}
    assert s["accounts"]["x"]["acct_b"]["units"] == 1
    assert s["kinds"]["unit_completed"] == 3


def test_summarize_is_pure_and_empty_safe():
    s = df.summarize([])
    assert s["kinds"] == {} and s["accounts"] == {} and s["switches"] == [] and s["universe"] == {}


def test_size_bound_refuses_and_keeps_file(isolated_cache, monkeypatch):
    monkeypatch.setattr(df, "MAX_FILE_BYTES", 600)
    written = [df.append(_unit(), now=NOW, switches=SWITCHES) for _ in range(20)]
    assert written[0] and not written[-1]
    assert df.events_path(NOW.date()).stat().st_size <= 600
    assert all(e["kind"] for e in df.read_events(NOW.date()))


def test_torn_tail_is_skipped_and_next_append_starts_clean_line(isolated_cache):
    df.append(_unit(), now=NOW, switches=SWITCHES)
    with df.events_path(NOW.date()).open("ab") as fh:
        fh.write(b'{"kind":"unit_comp')
    assert [e["kind"] for e in df.read_events(NOW.date())] == ["switch_provenance", "unit_completed"]
    df.append(_unit(), now=NOW, switches=SWITCHES)
    assert [e["kind"] for e in df.read_events(NOW.date())].count("unit_completed") == 2


def test_concurrent_appends_are_whole_lines(isolated_cache):
    def worker(n):
        for _ in range(25):
            df.append(_unit(account=f"acct_{n}"), now=NOW, switches=SWITCHES)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    lines = df.events_path(NOW.date()).read_bytes().splitlines()
    assert all(json.loads(line) for line in lines)
    kinds = [json.loads(line)["kind"] for line in lines]
    assert kinds.count("unit_completed") == 100 and kinds.count("switch_provenance") == 1


def test_retention_prunes_by_day(isolated_cache):
    for back in (0, 29, 30, 31, 200):
        d = NOW - timedelta(days=back)
        df.append(_unit(), now=d, switches=SWITCHES)
    (df.facts_dir() / "unrelated.txt").write_text("keep")
    removed = df.prune(now=NOW, retention_days=30)
    assert removed == 2
    left = sorted(p.name for p in df.facts_dir().glob("events_*.jsonl"))
    assert left == ["events_2026-10-08.jsonl", "events_2026-10-09.jsonl", "events_2026-11-07.jsonl"]
    assert (df.facts_dir() / "unrelated.txt").exists()


@pytest.mark.parametrize("bad", [29, 0, -1, True, "180"])
def test_retention_below_floor_rejected(isolated_cache, bad):
    with pytest.raises(ValueError):
        df.prune(now=NOW, retention_days=bad)


def test_prune_on_missing_dir_is_zero(isolated_cache):
    assert df.prune(now=NOW, retention_days=180) == 0


def test_universe_snapshot_once_per_source_per_day(isolated_cache):
    day = NOW.date()
    assert df.write_universe_snapshot(day, "x", eligible_symbols=["BTC", "ETH"], ambiguous_symbols=["ONE"],
                                      method_order=["x_web"], now=NOW, switches=SWITCHES)
    assert not df.write_universe_snapshot(day, "x", eligible_symbols=["SOL"], ambiguous_symbols=[],
                                          method_order=["x_web"], now=NOW, switches=SWITCHES)
    assert df.write_universe_snapshot(day, "reddit", eligible_symbols=["SOL"], ambiguous_symbols=[],
                                      method_order=["reddit_live_browser", "reddit_live_gql"], now=NOW,
                                      switches=SWITCHES)
    snap = df.read_universe_snapshot(day, "x")
    assert snap == {"day": "2026-11-07", "source": "x", "eligible_symbols": ["BTC", "ETH"],
                    "ambiguous_symbols": ["ONE"], "method_order": ["x_web"]}
    assert df.read_universe_snapshot(day, "reddit")["method_order"] == ["reddit_live_browser", "reddit_live_gql"]
    assert set(df.summarize(df.read_events(day))["universe"]) == {"x", "reddit"}


def test_universe_snapshot_absent_is_none(isolated_cache):
    assert df.read_universe_snapshot(NOW.date(), "x") is None


@pytest.mark.parametrize("kwargs", [
    {"eligible_symbols": ["btc"]}, {"eligible_symbols": ["BTC", "BTC"]}, {"ambiguous_symbols": ["A B"]},
    {"method_order": ["Bad Method"]},
])
def test_universe_snapshot_symbols_validated(isolated_cache, kwargs):
    args = {"eligible_symbols": ["BTC"], "ambiguous_symbols": [], "method_order": ["x_web"], **kwargs}
    with pytest.raises(ValueError):
        df.write_universe_snapshot(NOW.date(), "x", now=NOW, switches=SWITCHES, **args)


def test_universe_snapshot_day_is_event_day(isolated_cache):
    with pytest.raises(ValueError):
        df.write_universe_snapshot(NOW.date() - timedelta(days=1), "x", eligible_symbols=["BTC"],
                                   ambiguous_symbols=[], method_order=["x_web"], now=NOW, switches=SWITCHES)
