"""Finish plan S-B3I: B3 behaviour measures wired into the pool, the X stream and the approved ordinary calls.

Each switch on/off plus the all-off baseline; fake readers, fake clock and an isolated cache only; no network.
"""
from __future__ import annotations

import random
import types
from datetime import date, datetime, timedelta, timezone

import pytest

from api.data import attention_pc_refresh as apr
from api.data.attention import daily_facts
from api.data.attention import pc_pace as pp
from api.data.attention import web_queries as wq
from api.data.attention import x_behaviour as xb
from api.data.attention import x_filters as xf
from api.data.attention import x_pool as xp
from api.data.attention import x_reader as xrd

T0 = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 20)
END = datetime(2026, 10, 21, tzinfo=timezone.utc)
SOL = xf.Coin("SOL", "Solana")
QUERY = '"$SOL" lang:en -filter:replies -filter:retweets'
LABELS = ["acct_a", "acct_b"]
QUIET_UTC = {"timezone": "UTC", "start": "09:00", "end": "11:00"}  # T0 (10:00 UTC) is inside


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    return attention_cache


class Clock:
    def __init__(self, now: datetime = T0):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> None:
        self.now += timedelta(**kw)


def cfg(**over) -> wq.CollectorConfig:
    return wq.CollectorConfig(**{**wq.load().config.as_dict(), "x_accounts": tuple(LABELS), **over})


_ids = iter(range(1, 10**9))


def pages(n_pages: int = 2, per: int = 20) -> list[xrd.RawPage]:
    tws = []
    for i in range(n_pages * per):
        tid = next(_ids)
        u = xf.XUser(tid, datetime(2024, 1, 1, tzinfo=timezone.utc), 100, 100, "https://img/p.jpg", False)
        tws.append(xf.Tweet(tid, END - timedelta(minutes=1 + 10 * i), f"Solana {tid}", u, "en", ("SOL",)))
    return [xrd.FakeXReader.page_of(tws[i * per:(i + 1) * per], remaining=40) for i in range(n_pages)]


def reader(label, items=(), ordinary=()):
    return xrd.FakeXReader(label, list(items), ordinary_items=list(ordinary))


def source(clock, budget=800):
    return pp.PcSource("xsearch_web", configured_budget=budget, floor=40, adaptive=True, clock=clock)


def pool_for(clock, labels=LABELS, **over) -> xp.XPool:
    return xp.from_config(cfg(x_accounts=tuple(labels), **over), clock=clock)


def unit(pool, readers, src, config):
    return xp.run_unit(pool, readers, src, config, symbol="SOL", day=DAY, query=QUERY, coin=SOL,
                       policy=xf.FilterPolicy(), rng=random.Random(1), sleep=lambda s: None)


def facts(kind):
    return [e for e in daily_facts.read_events(T0.date()) if e.get("kind") == kind]


# --- all-off baseline -----------------------------------------------------------------------------------------------

def test_all_off_baseline_ignores_configured_windows_targets_and_adds_no_health():
    clock = Clock()
    pool = pool_for(clock, x_account_quiet_hours={"acct_a": QUIET_UTC}, x_mixed_targets=("solana",))
    assert pool.account_state("acct_a") == ("active", None)
    pool.note_remaining("acct_a", 0)
    assert pool.account_state("acct_a") == ("active", None)  # no B3 cooldown when off
    assert all("behaviour" not in a for a in pool.health()["accounts"])
    readers = {x: reader(x, ordinary=[1]) for x in LABELS}
    assert xp.run_mixed(pool, readers, source(clock), cfg(x_mixed_targets=("solana",)), units_since_last=99,
                        stale=set()) is None
    assert all(not r.ordinary_calls for r in readers.values())


# --- quiet hours ----------------------------------------------------------------------------------------------------

def test_quiet_hours_lock_the_account_and_the_unit_waits_instead_of_pausing_the_day():
    clock = Clock()
    c = cfg(x_accounts=("acct_a",), x_quiet_hours_enabled=True, x_account_quiet_hours={"acct_a": QUIET_UTC})
    pool, src = xp.from_config(c, clock=clock), source(clock)
    assert pool.account_state("acct_a") == ("locked", "quiet_hours")
    pool.set_canary_passed(labels=["acct_a"])
    out = unit(pool, {"acct_a": reader("acct_a", pages())}, src, c)
    assert out.result is None and out.reason == xp.WAIT_REASON
    assert pool.resume_at() == datetime(2026, 10, 21, 11, 0, tzinfo=timezone.utc)
    clock.now = datetime(2026, 10, 21, 11, 0, tzinfo=timezone.utc)
    assert pool.account_state("acct_a") == ("active", None)


def test_quiet_hours_off_or_unconfigured_label_keeps_existing_scheduling():
    clock = Clock()
    pool = pool_for(clock, x_quiet_hours_enabled=True, x_account_quiet_hours={"acct_a": QUIET_UTC})
    assert pool.account_state("acct_b") == ("active", None)
    assert pool.usable() == ["acct_b"]


# --- warm-up --------------------------------------------------------------------------------------------------------

def _rested(clock, tmp_path, **over):
    xp.write_ready(tmp_path, "acct_a", T0 - timedelta(days=2), labels=["acct_a"])
    pool = xp.from_config(cfg(x_accounts=("acct_a",), x_accounts_db_path=str(tmp_path), **over), clock=clock)
    pool._s["accounts"]["acct_a"]["rest_until"] = (T0 - timedelta(days=1)).isoformat()
    xp.atomic_json(pool.path, pool._s)
    return pool


def test_warmup_starts_when_eligible_and_caps_the_account(tmp_path):
    clock = Clock()
    pool = _rested(clock, tmp_path, x_warmup_enabled=True, x_account_daily_cap=800)
    pool.begin_pass()
    assert pool._s["accounts"]["acct_a"]["warmup_start_day"] == T0.date().isoformat()
    assert pool.effective_cap("acct_a") == 100
    pool.charge("acct_a", 100)
    assert pool.account_state("acct_a") == ("locked", "account_cap")
    clock.advance(days=2)
    assert pool.effective_cap("acct_a") == 200
    clock.advance(days=5)
    assert pool.effective_cap("acct_a") == 800


def test_warmup_off_and_grandfathered_accounts_keep_the_configured_cap(tmp_path):
    clock = Clock()
    pool = _rested(clock, tmp_path, x_account_daily_cap=800)
    pool.begin_pass()
    assert pool._s["accounts"]["acct_a"]["warmup_start_day"] is None and pool.effective_cap("acct_a") == 800
    grand = pool_for(clock, x_warmup_enabled=True, x_account_daily_cap=800)
    grand.begin_pass()
    assert grand._s["accounts"]["acct_a"]["warmup_start_day"] is None and grand.effective_cap("acct_a") == 800


# --- adaptive cooldown ----------------------------------------------------------------------------------------------

def test_rate_limit_cooldown_waits_fifteen_minutes_then_clears_with_facts():
    clock = Clock()
    pool = pool_for(clock, x_adaptive_cooldown_enabled=True)
    pool.note_remaining("acct_a", 1)
    assert pool.account_state("acct_a") == ("locked", "behaviour_cooldown")
    assert pool._s["accounts"]["acct_a"]["behaviour_reason"] == "rate_limit"
    assert pool.health()["accounts"][0]["behaviour"]["cooldown_until"] == (T0 + timedelta(minutes=15)).isoformat()
    clock.advance(minutes=15)
    pool.begin_pass()
    a = pool._s["accounts"]["acct_a"]
    assert a["behaviour_cooldown_until"] is None and a["behaviour_reason"] is None
    assert [e["action"] for e in facts("cooldown")] == ["set", "cleared"]


def test_shrink_run_of_three_triggers_a_one_hour_cooldown_and_resets_on_recovery():
    clock = Clock()
    pool = pool_for(clock, x_adaptive_cooldown_enabled=True)
    for _ in range(7):
        pool.note_result("acct_a", DAY, 40)
    for _ in range(3):
        pool.note_result("acct_a", DAY, 5)
    a = pool._s["accounts"]["acct_a"]
    assert a["behaviour_reason"] == "shrink" and pool.account_state("acct_a") == ("locked", "behaviour_cooldown")
    clock.advance(hours=1)
    pool.begin_pass()
    assert pool._acct("acct_a")["shrink_run"] == 0 and pool.account_state("acct_a") == ("active", None)


def test_cooldown_off_records_no_history_and_never_cools_down():
    clock = Clock()
    pool = pool_for(clock)
    for _ in range(10):
        pool.note_result("acct_a", DAY, 0)
    a = pool._s["accounts"]["acct_a"]
    assert a["result_history"] == [] and a["shrink_run"] == 0 and a["behaviour_reason"] is None


def test_successful_unit_feeds_the_shrink_history():
    clock = Clock()
    c = cfg(x_adaptive_cooldown_enabled=True)
    pool, src = xp.from_config(c, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    out = unit(pool, {x: reader(x, pages()) for x in LABELS}, src, c)
    assert out.result is not None
    assert pool._s["accounts"][out.label]["result_history"][-1]["count"] == out.reads


def test_owner_clear_lifts_a_challenge_pause():
    clock = Clock()
    pool = pool_for(clock)
    pool.apply_cooldown("acct_a", xb.cooldown(T0, enabled=False, challenge=True))
    assert pool.account_state("acct_a") == ("locked", "challenge")
    pool.owner_clear("acct_a")
    assert pool.account_state("acct_a") == ("active", None)


@pytest.mark.parametrize("enabled", [True, False])
def test_confirmed_stripped_strike_sets_a_one_hour_cooldown_only_when_on(enabled):
    clock = Clock()
    pool = pool_for(clock, x_adaptive_cooldown_enabled=enabled)
    pool.note_parse_drop("acct_a", "content_stripped")
    assert pool._acct("acct_a")["behaviour_reason"] is None  # one strike is not confirmed
    pool.note_parse_drop("acct_a", "content_stripped")
    a = pool._acct("acct_a")
    if enabled:
        assert a["behaviour_reason"] == "stripped_strike"
        assert a["behaviour_cooldown_until"] == (T0 + timedelta(hours=1)).isoformat()
    else:
        assert a["behaviour_reason"] is None and a["behaviour_cooldown_until"] is None


def test_unparseable_strikes_never_set_a_stripped_cooldown():
    clock = Clock()
    pool = pool_for(clock, x_adaptive_cooldown_enabled=True)
    pool.note_parse_drop("acct_a", "unparseable")
    pool.note_parse_drop("acct_a", "unparseable")
    assert pool._acct("acct_a")["behaviour_reason"] is None


# --- mixed traffic --------------------------------------------------------------------------------------------------

def _mixed(clock, targets=("solana", "1234567890123456789"), **over):
    c = cfg(x_mixed_traffic_enabled=True, x_mixed_targets=targets, **over)
    pool = xp.from_config(c, clock=clock)
    pool.set_canary_passed(labels=pool.labels)
    return c, pool, source(clock)


def test_mixed_call_charges_max_of_reserve_and_actual_to_account_and_global():
    clock = Clock()
    c, pool, src = _mixed(clock)
    readers = {x: reader(x, ordinary=[3, 25]) for x in LABELS}
    op = xp.run_mixed(pool, readers, src, c, units_since_last=20, stale=set())
    label = pool.peek()
    assert op in xb.MIXED_OPS and sum(len(r.ordinary_calls) for r in readers.values()) == 1
    assert pool.reads_today(label) == 20 and src.remaining() == 800 - 20
    assert pool._s["accounts"][label]["mixed_calls"] == 1
    assert pool._s["accounts"][label]["mixed_day"] == T0.date().isoformat()
    xp.run_mixed(pool, readers, src, c, units_since_last=20, stale=set())
    assert pool.reads_today(label) == 45  # max(20, 25)
    assert [e["reads"] for e in facts("mixed_call")] == [20, 25]


def test_mixed_refused_before_twenty_units_after_three_calls_and_without_room():
    clock = Clock()
    c, pool, src = _mixed(clock)
    readers = {x: reader(x, ordinary=[1] * 9) for x in LABELS}
    assert xp.run_mixed(pool, readers, src, c, units_since_last=19, stale=set()) is None
    for _ in range(3):
        assert xp.run_mixed(pool, readers, src, c, units_since_last=20, stale=set())
    assert xp.run_mixed(pool, readers, src, c, units_since_last=20, stale=set()) is None
    small = source(clock, budget=40)
    small.record_loaded(25)
    assert xp.run_mixed(pool, readers, small, c, units_since_last=20, stale=set()) is None


def test_mixed_failure_is_charged_and_a_404_suspends_the_operation():
    clock = Clock()
    c, pool, src = _mixed(clock, targets=("1234567890123456789",))
    readers = {x: reader(x, ordinary=[xrd.ReaderFailure("not_found")]) for x in LABELS}
    stale: set[str] = {"user_tweets"}
    assert xp.run_mixed(pool, readers, src, c, units_since_last=20, stale=stale) == "tweet_details"
    assert stale == {"tweet_details", "user_tweets"} and src.remaining() == 780
    assert xp.run_mixed(pool, readers, src, c, units_since_last=20, stale=stale) is None


def test_mixed_targets_split_logins_and_ids():
    assert xp.mixed_pick(("solana",), "acct_a", DAY, 0, set())[0] == "user_by_login"
    assert xp.mixed_pick(("123",), "acct_a", DAY, 0, set())[0] in ("tweet_details", "user_tweets")
    assert xp.mixed_pick((), "acct_a", DAY, 0, set()) == (None, None)


# --- the X stream ---------------------------------------------------------------------------------------------------

class _Trickle:
    def next_due(self, now):
        return now + timedelta(seconds=100)


def _stream(clock):
    worker = types.SimpleNamespace(clock=clock, x_spread_over_day=False, mode=lambda now: "catchup")
    return apr.XStream(worker, apr.X_SOURCE, random.Random(1))


def test_next_due_variation_multiplies_the_pause_never_below_base():
    clock = Clock()
    stream, src = _stream(clock), source(clock)
    assert stream._next_due(_Trickle(), src, cfg()) == T0 + timedelta(seconds=100)
    on = cfg(x_variation_enabled=True)
    due = stream._next_due(_Trickle(), src, on, label="acct_a")
    mult = xb.variation("acct_a", T0.date(), page_cap=xrd.PAGE_ENTRIES, enabled=True).pause_multiplier
    assert due == T0 + timedelta(seconds=100 * mult) and due >= T0 + timedelta(seconds=100)


def test_next_due_waits_out_quiet_hours_when_no_account_is_usable():
    clock = Clock()
    c = cfg(x_accounts=("acct_a",), x_quiet_hours_enabled=True, x_account_quiet_hours={"acct_a": QUIET_UTC})
    pool = xp.from_config(c, clock=clock)
    due = _stream(clock)._next_due(_Trickle(), source(clock), c, pool=pool)
    assert due == datetime(2026, 10, 21, 11, 0, tzinfo=timezone.utc)


def test_variation_orders_only_equally_due_items():
    items = [("A", DAY), ("B", DAY), ("C", DAY), ("D", DAY - timedelta(days=1))]
    off = apr.XStream.vary_order(items, cfg(), "acct_a", T0.date())
    assert off == items
    on = apr.XStream.vary_order(items, cfg(x_variation_enabled=True), "acct_a", T0.date())
    assert sorted(on[:3]) == items[:3] and on[3] == items[3]
