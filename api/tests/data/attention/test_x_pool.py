"""Collector identity pool, Part A (Stage 0): per-account daily cap, sequential handoff, rest period, ready mark,
per-account status and sizing. Fake readers, fake clock and an isolated cache only; no network, no live state.
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta, timezone

import pytest

from api.data import cache
from api.data.attention import pc_pace as pp
from api.data.attention import web_queries as wq
from api.data.attention import x_capacity
from api.data.attention import x_filters as xf
from api.data.attention import x_pool as xp
from api.data.attention import x_reader as xrd

T0 = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 20)
END = datetime(2026, 10, 21, tzinfo=timezone.utc)
SOL = xf.Coin("SOL", "Solana")
QUERY = '"$SOL" lang:en -filter:replies -filter:retweets'
LABELS = ["acct_a", "acct_b"]


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
    return wq.CollectorConfig(**{**wq.load().config.as_dict(), **over})


_ids = iter(range(1, 10**9))


def day_pages(n_pages: int = 2, per: int = 20) -> list[xrd.RawPage]:
    tws = []
    for i in range(n_pages * per):
        tid = next(_ids)
        u = xf.XUser(tid, datetime(2024, 1, 1, tzinfo=timezone.utc), 100, 100, "https://img/p.jpg", False)
        tws.append(xf.Tweet(tid, END - timedelta(minutes=1 + 10 * i), f"Solana {tid}", u, "en", ("SOL",)))
    return [xrd.FakeXReader.page_of(tws[i * per:(i + 1) * per], remaining=40) for i in range(n_pages)]


ACTIVE = xrd.PoolRow(active=True, error_msg=None, locks={}, last_used=None)


def reader(label, items=(), row=ACTIVE):
    return xrd.FakeXReader(label, list(items), row)


def source(clock, budget=800):
    return pp.PcSource("xsearch_web", configured_budget=budget, floor=40, adaptive=True, clock=clock)


def unit(pool, readers, src, config=None, symbol="SOL"):
    return xp.run_unit(pool, readers, src, config or cfg(), symbol=symbol, day=DAY, query=QUERY, coin=SOL,
                       policy=xf.FilterPolicy(), rng=random.Random(1), sleep=lambda s: None)


def test_parse_drop_restarts_on_another_account_and_charges_both():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock, cap=1000), source(clock)
    pool.set_canary_passed(labels=LABELS)
    broken = day_pages(1)[0]
    broken.body["entries"] = [{**entry, "broken": True} for entry in broken.body["entries"]]
    outcome = unit(pool, {"acct_a": reader("acct_a", [broken]), "acct_b": reader("acct_b", day_pages())}, src)
    assert outcome.result is not None
    assert outcome.restarts == 1 and outcome.reads == 60 and outcome.pages == 3
    assert pool.stopped_reason() is None
    assert pool.health()["accounts"][0]["parse_strikes"] == 1

def state_file():
    return cache.CACHE_ROOT / "attention" / "_pc_state" / "x_pool.json"


OLD_ACCOUNT = {"state": "active", "reason": None, "last_used": None, "lock_until": None, "last_canary": None,
               "suspect_since": None, "rate_limit_seen": None}
OLD_STATE = {"accounts": {"acct_a": OLD_ACCOUNT}, "alerts": [], "pause_until": None, "pause_reason": None,
             "stopped": None, "drift_streak": 0, "canary_day": None, "canary_note": None, "canary_labels": [],
             "curl_uses": 0, "curl_last_use": None}


def write_old_state(accounts=("acct_a",)):
    state_file().parent.mkdir(parents=True, exist_ok=True)
    state_file().write_text(json.dumps({**OLD_STATE, "accounts": {x: dict(OLD_ACCOUNT) for x in accounts}}))


# --- state migration ----------------------------------------------------------------------------------------------

def test_old_state_file_without_new_keys_loads_and_counts_unknown():
    write_old_state(("acct_a", "acct_b"))
    pool = xp.XPool(LABELS, clock=Clock(), cap=100)
    assert pool.account_state("acct_a") == ("active", None)
    h = pool.health()["accounts"][0]
    assert h["reads_today"] is None and h["cap"] == 100 and h["rest_until"] is None and h["ready"] is None
    pool.mark_used("acct_a")
    saved = json.loads(state_file().read_text())["accounts"]["acct_a"]
    assert (saved["reads_day"], saved["reads_used"], saved["rest_until"]) == (None, 0, None)


def test_new_keys_validated():
    write_old_state()
    doc = json.loads(state_file().read_text())
    for bad in ({"reads_day": "2026-13-01"}, {"reads_used": -1}, {"reads_used": True}, {"rest_until": "x"},
                {"reads_day": "2026-10-21T00:00:00+00:00"}):
        doc["accounts"]["acct_a"] = {**OLD_ACCOUNT, "reads_day": None, "reads_used": 0, "rest_until": None, **bad}
        state_file().write_text(json.dumps(doc))
        with pytest.raises(xp.XPoolStateError):
            xp.XPool(["acct_a"], clock=Clock())


# --- cap -----------------------------------------------------------------------------------------------------------

def test_reads_charged_per_page_to_the_reading_account_and_reset_next_utc_day():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock, cap=1000), source(clock)
    pool.set_canary_passed(labels=LABELS)
    out = unit(pool, {"acct_a": reader("acct_a", day_pages()), "acct_b": reader("acct_b")}, src)
    assert out.label == "acct_a" and out.reads == 40
    assert pool.reads_today("acct_a") == 40 and pool.reads_today("acct_b") is None
    assert xp.XPool(LABELS, clock=clock).reads_today("acct_a") == 40  # persisted
    clock.advance(days=1)
    assert pool.reads_today("acct_a") == 0  # a real reset: known zero, not unknown


def test_account_at_cap_skipped_with_reason():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock, cap=40), source(clock)
    pool.set_canary_passed(labels=LABELS)
    a, b = reader("acct_a", day_pages()), reader("acct_b", day_pages())
    unit(pool, {"acct_a": a, "acct_b": b}, src)
    assert pool.account_state("acct_a") == ("locked", "account_cap")
    clock.advance(minutes=10)
    out = unit(pool, {"acct_a": a, "acct_b": b}, src, symbol="ETH")
    assert out.label == "acct_b" and len(a.calls) == 2
    assert pool.health()["accounts"][0]["state"] == "locked"


def test_unit_crossing_cap_finishes_on_its_account_no_split():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock, cap=30), source(clock)
    pool.set_canary_passed(labels=LABELS)
    a, b = reader("acct_a", day_pages()), reader("acct_b", day_pages())
    out = unit(pool, {"acct_a": a, "acct_b": b}, src)
    assert out.result is not None and out.label == "acct_a" and len(a.calls) == 2 and b.calls == []
    assert pool.reads_today("acct_a") == 40  # overshoot at most one unit's pages
    assert pool.select().label == "acct_b"


def test_all_at_cap_is_budget_spent_without_no_usable_account_pause():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock, cap=20), source(clock)
    pool.set_canary_passed(labels=LABELS)
    pool.charge("acct_a", 20)
    pool.charge("acct_b", 20)
    out = unit(pool, {"acct_a": reader("acct_a"), "acct_b": reader("acct_b")}, src)
    assert out.reason == "budget_spent" and src.budget_spent()
    assert pool.pause_reason() is None and not pool.is_paused()
    clock.advance(days=1)
    assert not src.budget_spent() and pool.select() is not None


def test_in_flight_lock_wait_wins_over_all_at_cap():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock, cap=20), source(clock)
    pool.set_canary_passed(labels=LABELS)
    pool.charge("acct_a", 20)
    pool.wait_for_lock("acct_b", T0 + timedelta(minutes=5))
    out = unit(pool, {"acct_a": reader("acct_a"), "acct_b": reader("acct_b")}, src)
    assert out.reason == xp.WAIT_REASON and not src.budget_spent()


def test_global_budget_stays_the_ceiling():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock, cap=10_000), source(clock, budget=40)
    pool.set_canary_passed(labels=LABELS)
    unit(pool, {"acct_a": reader("acct_a", day_pages()), "acct_b": reader("acct_b", day_pages())}, src)
    out = unit(pool, {"acct_a": reader("acct_a", day_pages()), "acct_b": reader("acct_b", day_pages())}, src,
               symbol="ETH")
    assert out.reason in ("budget_spent", "too_early") and src.used <= 40


def test_no_cap_behaves_as_before():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    pool.charge("acct_a", 10_000)
    assert pool.account_state("acct_a") == ("active", None) and pool.health()["accounts"][0]["cap"] is None


# --- loss failover -------------------------------------------------------------------------------------------------

def test_lost_account_unit_read_by_another_once_reads_split_and_sum_to_global():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock, cap=1000), source(clock)
    pool.set_canary_passed(labels=LABELS)
    gone = xrd.PoolRow(active=False, error_msg="(32) Could not authenticate you", locks={}, last_used=None)
    a = reader("acct_a", [day_pages()[0], xrd.ReaderFailure("no_account")], gone)
    b = reader("acct_b", day_pages())
    out = unit(pool, {"acct_a": a, "acct_b": b}, src)
    assert out.label == "acct_b" and out.restarts == 1 and out.result is not None
    assert pool.reads_today("acct_a") == 20 and pool.reads_today("acct_b") == 40
    assert pool.reads_today("acct_a") + pool.reads_today("acct_b") == src.used == out.reads == 60
    assert pool.health()["accounts"][0]["state"] == "inactive"
    assert out.row["n_read"] == 40 and out.row["n_counted"] == 40
    print("STAGE0 SMOKE: loss failover once; account reads 20+40=global 60; stored sample 40, not 60")


# --- rest and ready ------------------------------------------------------------------------------------------------

def test_first_ever_state_file_does_not_rest():
    pool = xp.XPool(LABELS, clock=Clock(), rest_days=3)
    assert pool.usable() == LABELS


def test_existing_accounts_grandfathered_new_label_rests_until_rest_and_ready():
    write_old_state(("acct_a",))
    clock = Clock()
    pool = xp.XPool(LABELS, clock=clock, rest_days=2)
    pool.begin_pass()  # registration is persisted by the producer, never by a read-only status load
    assert pool.account_state("acct_a") == ("active", None)
    assert pool.account_state("acct_b") == ("locked", "resting")
    clock.advance(days=3)
    assert xp.XPool(LABELS, clock=clock, rest_days=2).account_state("acct_b") == ("locked", "resting")  # not ready
    ready = {"acct_b": clock().isoformat()}
    assert xp.XPool(LABELS, clock=clock, rest_days=2, ready=ready).account_state("acct_b") == ("locked", "resting")
    clock.advance(days=1)  # marked ready yesterday: selectable from the next UTC day
    pool = xp.XPool(LABELS, clock=clock, rest_days=2, ready=ready)
    assert pool.account_state("acct_b") == ("active", None)
    h = pool.health()["accounts"][1]
    assert h["ready"] is True and h["rest_until"] is not None


def test_ready_before_rest_passed_is_not_enough():
    write_old_state(("acct_a",))
    clock = Clock()
    xp.XPool(LABELS, clock=clock, rest_days=5).begin_pass()
    ready = {"acct_b": clock().isoformat()}
    clock.advance(days=2)
    assert xp.XPool(LABELS, clock=clock, rest_days=5, ready=ready).account_state("acct_b") == ("locked", "resting")


def test_rest_off_by_default_new_label_usable():
    write_old_state(("acct_a",))
    assert xp.XPool(LABELS, clock=Clock()).usable() == LABELS


def test_ready_mark_survives_a_running_pass(tmp_path):
    write_old_state(("acct_a",))
    clock = Clock()
    pool = xp.XPool(LABELS, clock=clock, rest_days=1)
    xp.write_ready(tmp_path, "acct_b", clock(), labels=LABELS)
    src = source(clock)
    pool.set_canary_passed(labels=["acct_a"])
    unit(pool, {"acct_a": reader("acct_a", day_pages()), "acct_b": reader("acct_b")}, src)
    assert xp.read_ready(tmp_path) == {"acct_b": T0.isoformat()}
    assert "ready" not in json.dumps(json.loads(state_file().read_text()))


def test_write_ready_refuses_unconfigured_label(tmp_path):
    with pytest.raises(ValueError):
        xp.write_ready(tmp_path, "nobody", T0, labels=LABELS)
    assert xp.read_ready(tmp_path) == {}


def test_read_ready_ignores_bad_file(tmp_path):
    (tmp_path / xp.READY_FILE).write_text("not json")
    assert xp.read_ready(tmp_path) == {}
    (tmp_path / xp.READY_FILE).write_text(json.dumps({"acct_b": "yesterday", "acct_a": T0.isoformat()}))
    assert xp.read_ready(tmp_path) == {"acct_a": T0.isoformat()}


def test_account_marked_ready_joins_next_utc_day_canary():
    write_old_state(("acct_a",))
    clock = Clock()
    xp.XPool(LABELS, clock=clock, rest_days=1).begin_pass()
    clock.advance(days=1)
    ready = {"acct_b": clock().isoformat()}
    assert xp.XPool(LABELS, clock=clock, rest_days=1, ready=ready).canary_accounts() == ["acct_a"]
    clock.advance(days=1)
    pool = xp.XPool(LABELS, clock=clock, rest_days=1, ready=ready)
    assert sorted(pool.canary_accounts()) == LABELS


def test_from_config_reads_cap_rest_and_ready(tmp_path):
    xp.write_ready(tmp_path, "acct_b", T0, labels=LABELS)
    config = cfg(x_accounts=tuple(LABELS), x_accounts_db_path=str(tmp_path), x_account_daily_cap=50,
                 x_account_rest_days=2)
    pool = xp.from_config(config, clock=Clock())
    assert (pool.cap, pool.rest_days, pool.ready) == (50, 2, {"acct_b": T0.isoformat()})


# --- sizing --------------------------------------------------------------------------------------------------------

def test_remaining_caps_sums_selectable_accounts():
    clock = Clock()
    pool = xp.XPool(["acct_a", "acct_b", "acct_c"], clock=clock, cap=100)
    pool.charge("acct_a", 30)
    pool.lock_for_day("acct_c")
    assert pool.remaining_caps() == 70 + 100
    assert xp.XPool(["acct_a", "acct_b", "acct_c"], clock=clock).remaining_caps() is None


def test_sizing_reports_shortfall_and_backlog_separately():
    per = x_capacity.per_unit_reads(sample_n=40, page_cap=3, page_size=20)
    assert per == 40 and x_capacity.per_unit_reads(sample_n=100, page_cap=3, page_size=20) == 60
    s = x_capacity.sizing(global_room=800, remaining_caps=100, queued_target=5, backlog=7, per_unit=40,
                          canary_pages=2, page_size=20)
    assert s == {"capacity_reads": 100, "need_reads": 240, "shortfall_reads": 140, "backlog_reads": 280}
    s = x_capacity.sizing(global_room=800, remaining_caps=None, queued_target=5, backlog=0, per_unit=40,
                          canary_pages=0, page_size=20)
    assert s["capacity_reads"] == 800 and s["shortfall_reads"] == 0


def test_read_only_status_never_persists_registration_or_resets_counters():
    write_old_state()
    before = state_file().read_bytes()
    pool = xp.XPool(LABELS, clock=Clock(), rest_days=2, cap=40)
    pool.health()
    assert state_file().read_bytes() == before


def test_clock_rollback_cannot_clear_cap():
    clock = Clock()
    pool = xp.XPool(LABELS, clock=clock, cap=20)
    pool.charge("acct_a", 20)
    clock.advance(days=-1)
    assert pool.reads_today("acct_a") == 20
    assert pool.account_state("acct_a") == ("locked", "account_cap")
