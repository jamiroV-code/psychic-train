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

def stripped_page():
    ids = tuple(f"tweet-{next(_ids)}" for _ in range(20))
    entries = [{"entryId": entry_id, "content": {"itemContent": {"tweet_results": {}}}}
               for entry_id in ids]
    return xrd.RawPage({"data": {"search_by_raw_query": {"search_timeline": {
        "timeline": {"instructions": [{"type": "TimelineAddEntries", "entries": entries}]}}}}},
        ids, 40, 50)


class StrippedReader(xrd.FakeXReader):
    def parse_tweets(self, body):
        if "data" in body:
            return []
        return super().parse_tweets(body)


def test_incident_shape_is_retried_and_classified():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    out = unit(pool, {"acct_a": StrippedReader("acct_a", [stripped_page()]),
                      "acct_b": reader("acct_b", day_pages())}, src)
    assert out.result is not None and out.reads == 60 and out.pages == 3
    assert any("content_stripped" in line for line in pool.log)
    assert pool.health()["accounts"][0]["parse_strikes"] == 1


def test_strikes_expire_reset_and_make_account_suspect():
    clock = Clock()
    pool = xp.XPool(LABELS, clock=clock)
    pool.note_parse_drop("acct_a", "unparseable")
    clock.advance(hours=25)
    pool.note_parse_drop("acct_a", "unparseable")
    assert pool.health()["accounts"][0]["parse_strikes"] == 1
    pool.clear_parse_strikes("acct_a")
    assert pool.health()["accounts"][0]["parse_strikes"] == 0
    pool.note_parse_drop("acct_a", "unparseable")
    pool.note_parse_drop("acct_a", "unparseable")
    assert pool.account_state("acct_a")[0] == "suspect"
    assert pool.alerts()[0]["reason"] == xp.SUSPECT_REASON
    assert pool.usable() == ["acct_b"]


def test_second_stripped_attempt_flags_account_and_other_account_continues():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    for _ in range(2):
        pool.begin_pass()
        out = unit(pool, {"acct_a": StrippedReader("acct_a", [stripped_page()]),
                          "acct_b": reader("acct_b", day_pages())}, src)
        assert out.result is not None and out.reads == 60
        clock.advance(hours=1)
    assert pool.account_state("acct_a")[0] == "suspect"
    assert pool.alerts()[0]["reason"] == xp.SUSPECT_REASON
    assert pool.stopped_reason() is None and pool.usable() == ["acct_b"]


def test_clean_page_resets_account_streak():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    pool.note_parse_drop("acct_a", "unparseable")
    out = unit(pool, {"acct_a": reader("acct_a", day_pages()), "acct_b": reader("acct_b")}, src)
    assert out.result is not None
    assert pool.health()["accounts"][0]["parse_strikes"] == 0


def test_two_accounts_with_same_parse_failure_stop_pool():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    readers = {label: StrippedReader(label, [stripped_page()]) for label in LABELS}
    out = unit(pool, readers, src)
    assert out.reason == "layout_changed" and pool.stopped_reason() == "layout_changed"
    assert out.reads == 40 and out.pages == 2


def test_same_failure_on_different_units_in_pass_stops():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    pool.begin_pass()
    readers = {label: StrippedReader(label, [stripped_page()]) for label in LABELS}
    config = cfg(x_unit_max_restarts=0)
    assert unit(pool, readers, src, config).reason == "account_failed"
    clock.advance(hours=1)
    out = unit(pool, readers, src, config, symbol="OTHER")
    assert out.reason == "layout_changed" and pool.stopped_reason() == "layout_changed"


def test_single_account_second_strike_stops():
    clock = Clock()
    pool, src = xp.XPool(["acct_a"], clock=clock), source(clock)
    pool.set_canary_passed(labels=["acct_a"])
    config = cfg(x_unit_max_restarts=0)
    first = unit(pool, {"acct_a": StrippedReader("acct_a", [stripped_page()])}, src, config)
    assert first.reason != "layout_changed" and pool.stopped_reason() is None
    clock.advance(hours=1)
    second = unit(pool, {"acct_a": StrippedReader("acct_a", [stripped_page()])}, src, config)
    assert second.reason == "layout_changed" and pool.stopped_reason() == "layout_changed"


def test_old_state_has_unknown_strikes():
    write_old_state()
    health = xp.XPool(["acct_a"], clock=Clock()).health()["accounts"][0]
    assert health["parse_strikes"] is None and health["parse_strike_last_at"] is None

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


# --- S-XDrift: per-account 404 isolation, forced candidate evaluation, adoption (finish plan XD-1, XD-3, XD-4) ---

from api.data.attention import daily_facts as dfacts  # noqa: E402
from api.data.attention import x_queryids as xq  # noqa: E402

CAND = "vLHjqbDv7TPFMBkIIO1nOA"
CANARY_END = END  # the canary window is the last hour of the previous UTC day


def not_found():
    return xrd.ReaderFailure("not_found")


def canary_page(n=20):
    tws = []
    for i in range(n):
        tid = next(_ids)
        u = xf.XUser(tid, datetime(2024, 1, 1, tzinfo=timezone.utc), 100, 100, "https://img/p.jpg", False)
        tws.append(xf.Tweet(tid, CANARY_END - timedelta(minutes=1 + i * 2), f"bitcoin {tid}", u, "en", ()))
    return xrd.FakeXReader.page_of(tws, remaining=40)


def registry_with_candidate(now=T0, candidate=CAND):
    state = xq.apply_check(xq.initial_state(), now, outcome="ok", mapping={"SearchTimeline": candidate},
                           sha256="a" * 64)
    xq.save(xq.state_path(cache.CACHE_ROOT), state)
    return state


def registry():
    return xq.load(xq.state_path(cache.CACHE_ROOT))


def account(label):
    return json.loads(state_file().read_text())["accounts"][label]


def drift_unit(pool, readers, src, config=None, bind=None, symbol="SOL"):
    return xp.run_unit(pool, readers, src, config or cfg(), symbol=symbol, day=DAY, query=QUERY, coin=SOL,
                       policy=xf.FilterPolicy(), rng=random.Random(1), sleep=lambda s: None, bind=bind)


def facts(kind):
    return [e for e in dfacts.read_events(T0.date()) if e["kind"] == kind]


def test_fresh_and_migrated_accounts_get_literal_404_defaults():
    pool = xp.XPool(LABELS, clock=Clock())
    pool.begin_pass()
    assert (account("acct_a")["endpoint_404_day"], account("acct_a")["endpoint_404_count"]) == (None, 0)
    write_old_state(("acct_a", "acct_b"))
    xp.XPool(LABELS, clock=Clock()).begin_pass()
    assert (account("acct_b")["endpoint_404_day"], account("acct_b")["endpoint_404_count"]) == (None, 0)
    doc = json.loads(state_file().read_text())
    for bad in ({"endpoint_404_day": "x"}, {"endpoint_404_count": -1}, {"endpoint_404_count": True},
                {"endpoint_404_count": None}, {"endpoint_404_day": "2026-10-21T00:00:00+00:00"}):
        doc["accounts"]["acct_a"] = {**account("acct_b"), **bad}
        state_file().write_text(json.dumps(doc))
        with pytest.raises(xp.XPoolStateError):
            xp.XPool(LABELS, clock=Clock())


def test_404_single_account_is_unchanged_drift():
    clock = Clock()
    pool, src = xp.XPool(["acct_a"], clock=clock), source(clock)
    pool.set_canary_passed(labels=["acct_a"])
    out = unit(pool, {"acct_a": reader("acct_a", [not_found()])}, src)
    assert out.result is None and out.reason == "drift" and out.restarts == 0
    assert pool.health()["drift_streak"] == 1 and account("acct_a")["endpoint_404_count"] == 0


def test_404_reruns_the_same_unit_once_on_another_account_and_restricts_the_first_for_the_day():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    b = reader("acct_b", day_pages())
    out = unit(pool, {"acct_a": reader("acct_a", [not_found()]), "acct_b": b}, src)
    assert out.result is not None and out.label == "acct_b" and out.restarts == 1
    assert pool.health()["drift_streak"] == 0 and pool.stopped_reason() is None
    assert pool.account_state("acct_a") == ("locked", "endpoint_restricted")
    assert (account("acct_a")["endpoint_404_day"], account("acct_a")["endpoint_404_count"]) == ("2026-10-21", 1)
    assert pool.select().label == "acct_b"
    handoff = facts("handoff")
    assert [(e["from_account"], e["to_account"], e["reason"]) for e in handoff] == [("acct_a", "acct_b", "endpoint_404")]
    clock.advance(days=1)
    assert pool.account_state("acct_a") == ("active", None)


def test_404_with_three_accounts_reruns_on_another_and_counts_the_unit_once():
    clock = Clock()
    labels = ["acct_a", "acct_b", "acct_c"]
    pool, src = xp.XPool(labels, clock=clock), source(clock)
    pool.set_canary_passed(labels=labels)
    readers = {"acct_a": reader("acct_a", [not_found()]), "acct_b": reader("acct_b", day_pages()),
               "acct_c": reader("acct_c", day_pages())}
    out = unit(pool, readers, src)
    assert out.result is not None and out.label == "acct_b" and out.attempts == 2 and out.restarts == 1
    assert readers["acct_c"].calls == [] and out.reads == 40 and pool.reads_today("acct_b") == 40
    assert pool.account_state("acct_a") == ("locked", "endpoint_restricted")
    assert pool.account_state("acct_c") == ("active", None)


def test_second_restricted_event_on_a_different_day_locks_the_account_for_24h():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    for day_no in range(2):
        pool.set_canary_passed(labels=LABELS)
        out = unit(pool, {"acct_a": reader("acct_a", [not_found()]), "acct_b": reader("acct_b", day_pages())},
                   src, symbol=f"C{day_no}")
        assert out.label == "acct_b" and out.result is not None
        if day_no == 0:
            assert pool.account_state("acct_a") == ("locked", "endpoint_restricted")
            clock.advance(days=1)
            pool = xp.XPool(LABELS, clock=clock)  # the day guard survives a restart
            assert pool.account_state("acct_a") == ("active", None)
    assert pool.account_state("acct_a") == ("locked", "endpoint_404")
    assert account("acct_a")["endpoint_404_count"] == 2 and account("acct_a")["reason"] == "x_endpoint_404"
    locks = [e for e in dfacts.read_events(clock.now.date()) if e["kind"] == "account_state"]
    assert [(e["account"], e["state"], e["reason"]) for e in locks] == [("acct_a", "lock", "x_endpoint_404")]
    clock.advance(hours=23, minutes=59)
    assert pool.account_state("acct_a") == ("locked", "endpoint_404")
    clock.advance(minutes=2)
    assert pool.account_state("acct_a") == ("active", None)


def test_404_count_resets_after_seven_clean_days():
    clock = Clock()
    pool = xp.XPool(LABELS, clock=clock)
    assert pool.note_endpoint_404("acct_a") == "restricted"
    clock.advance(days=7)
    assert pool.note_endpoint_404("acct_a") == "locked"  # only six clean days in between
    pool = xp.XPool(LABELS, clock=clock)
    pool.owner_clear("acct_a")
    clock.advance(days=8)
    assert pool.note_endpoint_404("acct_a") == "restricted"
    assert account("acct_a")["endpoint_404_count"] == 1


def test_both_accounts_404_is_drift_and_nobody_is_restricted():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    out = unit(pool, {"acct_a": reader("acct_a", [not_found()]), "acct_b": reader("acct_b", [not_found()])}, src)
    assert out.result is None and out.reason == "drift" and out.attempts == 2
    assert pool.health()["drift_streak"] == 1
    assert account("acct_a")["endpoint_404_count"] == account("acct_b")["endpoint_404_count"] == 0


class Binder:
    def __init__(self):
        self.calls = []

    def __call__(self, query_id):
        self.calls.append(query_id)


def test_forced_evaluation_ignores_already_passed_canary_and_adopts_on_two_distinct_passes():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    assert xp.run_daily_canary(pool, {}, src, cfg(), rng=random.Random(1), sleep=lambda s: None).reason == "already_passed"
    registry_with_candidate()
    bind = Binder()
    readers = {"acct_a": reader("acct_a", [canary_page()]), "acct_b": reader("acct_b", [canary_page()])}
    result = pool.evaluate_candidate("SearchTimeline", CAND, readers=readers, src=src, config=cfg(), bind=bind,
                                     observed_by="acct_a")
    assert result == "adopted"
    state = registry()
    active = state["operations"]["SearchTimeline"]["active"]
    assert (active["id"], active["source"]) == (CAND, "bundle") and state["operations"]["SearchTimeline"]["candidate"] is None
    assert [e["account_label"] for e in state["evidence"]] == ["acct_b", "acct_a"]  # the observer last
    assert all(e["result"] == "passed" and e["parse_ok"] and e["entries"] == 20 for e in state["evidence"])
    assert bind.calls[0] == CAND and bind.calls[-1] == CAND
    assert pool.reads_today("acct_a") == 20 and pool.reads_today("acct_b") == 20
    assert [e["to_state"] for e in facts("queryid_state")] == ["adopted"]


def test_inconclusive_mixes_never_adopt_and_the_candidate_stays():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    registry_with_candidate()
    bind = Binder()
    readers = {"acct_a": reader("acct_a", [canary_page()]), "acct_b": reader("acct_b", [canary_page(3)])}
    assert pool.evaluate_candidate("SearchTimeline", CAND, readers=readers, src=src, config=cfg(),
                                   bind=bind) == "inconclusive"
    state = registry()
    assert state["operations"]["SearchTimeline"]["active"]["source"] == "pinned"
    cand = state["operations"]["SearchTimeline"]["candidate"]
    assert cand["id"] == CAND and cand["reason"] == "inconclusive" and cand["rejected_until"] is None
    assert sorted(e["result"] for e in state["evidence"]) == ["inconclusive", "passed"]
    assert bind.calls[-1] == xq.PINNED["SearchTimeline"]


def test_fewer_evaluations_than_required_is_inconclusive():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    registry_with_candidate()
    readers = {"acct_a": reader("acct_a", [canary_page()]),
               "acct_b": reader("acct_b", [xrd.ReaderFailure("abort", text="Blocked by Cloudflare")])}
    assert pool.evaluate_candidate("SearchTimeline", CAND, readers=readers, src=src, config=cfg(),
                                   bind=Binder()) == "inconclusive"
    assert registry()["operations"]["SearchTimeline"]["active"]["source"] == "pinned"


def test_any_failed_evaluation_rejects_the_candidate_for_24h():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    registry_with_candidate()
    readers = {"acct_a": reader("acct_a", [canary_page()]), "acct_b": reader("acct_b", [not_found()])}
    assert pool.evaluate_candidate("SearchTimeline", CAND, readers=readers, src=src, config=cfg(),
                                   bind=Binder()) == "rejected"
    cand = registry()["operations"]["SearchTimeline"]["candidate"]
    assert cand["reason"] == "evaluation_failed"
    assert datetime.fromisoformat(cand["rejected_until"]) == T0 + timedelta(hours=24)
    assert registry()["operations"]["SearchTimeline"]["active"]["source"] == "pinned"


def test_single_selectable_account_needs_one_pass():
    clock = Clock()
    pool, src = xp.XPool(["acct_a"], clock=clock), source(clock)
    registry_with_candidate()
    assert pool.evaluate_candidate("SearchTimeline", CAND, readers={"acct_a": reader("acct_a", [canary_page()])},
                                   src=src, config=cfg(), bind=Binder()) == "adopted"
    assert xq.active_id(registry()) == CAND


def test_at_most_three_evaluations_per_utc_day():
    clock = Clock()
    pool, src = xp.XPool(["acct_a"], clock=clock), source(clock)
    registry_with_candidate()
    for _ in range(3):
        r = {"acct_a": reader("acct_a", [canary_page(2)])}
        assert pool.evaluate_candidate("SearchTimeline", CAND, readers=r, src=src, config=cfg(),
                                       bind=Binder()) == "inconclusive"
    r = {"acct_a": reader("acct_a", [canary_page()])}
    assert pool.evaluate_candidate("SearchTimeline", CAND, readers=r, src=src, config=cfg(),
                                   bind=Binder()) == "budget"
    assert r["acct_a"].calls == [] and len(registry()["evidence"]) == 3


def test_only_search_timeline_and_the_registry_candidate_are_evaluated():
    clock = Clock()
    pool, src = xp.XPool(["acct_a"], clock=clock), source(clock)
    registry_with_candidate()
    r = {"acct_a": reader("acct_a", [canary_page()])}
    with pytest.raises(ValueError):
        pool.evaluate_candidate("UserTweets", CAND, readers=r, src=src, config=cfg(), bind=Binder())
    assert pool.evaluate_candidate("SearchTimeline", "zzzzzzzzzzzzzzzzzzzzzz", readers=r, src=src, config=cfg(),
                                   bind=Binder()) == "no_candidate"
    assert r["acct_a"].calls == []


def drift_to_two(pool, src, clock):
    for i in range(2):
        out = drift_unit(pool, {"acct_a": reader("acct_a", [xrd.ReaderFailure("parse")])}, src, symbol=f"D{i}")
        assert out.reason == "drift"
        clock.advance(minutes=10)


def test_confirmed_drift_with_a_candidate_is_evaluated_before_the_stop_and_adoption_avoids_it():
    clock = Clock()
    pool, src = xp.XPool(["acct_a"], clock=clock), source(clock)
    pool.set_canary_passed(labels=["acct_a"])
    registry_with_candidate()
    drift_to_two(pool, src, clock)
    bind = Binder()
    a = reader("acct_a", [xrd.ReaderFailure("parse"), canary_page()])
    out = drift_unit(pool, {"acct_a": a}, src, config=cfg(x_queryid_mode="auto"), bind=bind)
    assert out.result is None and pool.stopped_reason() is None and pool.health()["drift_streak"] == 0
    assert xq.active_id(registry()) == CAND and bind.calls[-1] == CAND


def test_confirmed_drift_with_a_failing_candidate_stops_and_rejects():
    clock = Clock()
    pool, src = xp.XPool(["acct_a"], clock=clock), source(clock)
    pool.set_canary_passed(labels=["acct_a"])
    registry_with_candidate()
    drift_to_two(pool, src, clock)
    a = reader("acct_a", [xrd.ReaderFailure("parse"), not_found()])
    out = drift_unit(pool, {"acct_a": a}, src, config=cfg(x_queryid_mode="auto"), bind=Binder())
    assert out.reason == "layout_changed" and pool.stopped_reason() == "layout_changed"
    assert registry()["operations"]["SearchTimeline"]["candidate"]["reason"] == "evaluation_failed"


def test_sentinel_mode_never_evaluates_or_adopts():
    clock = Clock()
    pool, src = xp.XPool(["acct_a"], clock=clock), source(clock)
    pool.set_canary_passed(labels=["acct_a"])
    registry_with_candidate()
    drift_to_two(pool, src, clock)
    a = reader("acct_a", [xrd.ReaderFailure("parse"), canary_page()])
    out = drift_unit(pool, {"acct_a": a}, src, config=cfg(x_queryid_mode="sentinel"), bind=Binder())
    assert out.reason == "layout_changed" and len(a.items) == 1
    assert registry()["operations"]["SearchTimeline"]["active"]["source"] == "pinned"


def test_both_accounts_404_with_a_candidate_triggers_evaluation_before_counting_drift():
    clock = Clock()
    pool, src = xp.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    registry_with_candidate()
    readers = {"acct_a": reader("acct_a", [not_found(), canary_page()]),
               "acct_b": reader("acct_b", [not_found(), canary_page()])}
    out = drift_unit(pool, readers, src, config=cfg(x_queryid_mode="auto"), bind=Binder())
    assert out.result is None and xq.active_id(registry()) == CAND
    assert pool.health()["drift_streak"] == 0


# --- S-B3P behaviour keys -----------------------------------------------------------------------------------------

B3_DEFAULTS = {"warmup_start_day": None, "behaviour_cooldown_until": None, "behaviour_reason": None,
               "shrink_run": 0, "result_history": [], "mixed_day": None, "mixed_calls": 0}


def test_b3_keys_literal_defaults_for_fresh_and_migrated_accounts():
    assert xp.B3_ACCOUNT_DEFAULTS == B3_DEFAULTS
    xp.XPool(LABELS, clock=Clock()).begin_pass()
    assert {k: account("acct_a")[k] for k in B3_DEFAULTS} == B3_DEFAULTS
    write_old_state(("acct_a", "acct_b"))
    xp.XPool(LABELS, clock=Clock()).begin_pass()
    assert {k: account("acct_b")[k] for k in B3_DEFAULTS} == B3_DEFAULTS
    # an S-XDrift-era file (all but the seven B3 keys) migrates too
    doc = json.loads(state_file().read_text())
    for a in doc["accounts"].values():
        for k in B3_DEFAULTS:
            del a[k]
    state_file().write_text(json.dumps(doc))
    xp.XPool(LABELS, clock=Clock()).begin_pass()
    assert {k: account("acct_a")[k] for k in B3_DEFAULTS} == B3_DEFAULTS


def test_b3_valid_values_round_trip():
    xp.XPool(LABELS, clock=Clock()).begin_pass()
    doc = json.loads(state_file().read_text())
    good = {"warmup_start_day": "2026-10-20", "behaviour_cooldown_until": "2026-10-21T11:00:00+00:00",
            "behaviour_reason": "shrink", "shrink_run": 3, "mixed_day": "2026-10-21", "mixed_calls": 3,
            "result_history": [{"day": "2026-10-20", "count": 12, "query_class": "coin"}] * 7}
    doc["accounts"]["acct_a"].update(good)
    state_file().write_text(json.dumps(doc))
    xp.XPool(LABELS, clock=Clock()).begin_pass()
    assert {k: account("acct_a")[k] for k in good} == good


@pytest.mark.parametrize("bad", [
    {"warmup_start_day": "2026-10-20T00:00:00+00:00"}, {"warmup_start_day": 1},
    {"behaviour_cooldown_until": "2026-10-21T11:00:00"}, {"behaviour_cooldown_until": "2026-10-21T11:00:00+02:00"},
    {"behaviour_reason": "made_up"}, {"behaviour_reason": 1},
    {"shrink_run": -1}, {"shrink_run": True}, {"shrink_run": None}, {"shrink_run": 10_001},
    {"result_history": None}, {"result_history": [{"day": "2026-10-20", "count": 1, "query_class": "coin"}] * 8},
    {"result_history": [{"day": "2026-10-20", "count": -1, "query_class": "coin"}]},
    {"result_history": [{"day": "2026-10-20", "count": 1, "query_class": "Bad Class"}]},
    {"result_history": [{"day": "2026-10-20", "count": 1, "query_class": "coin", "text": "x"}]},
    {"result_history": [{"day": None, "count": 1, "query_class": "coin"}]},
    {"mixed_day": "yesterday"}, {"mixed_calls": 4}, {"mixed_calls": -1}, {"mixed_calls": 1.0},
])
def test_b3_bad_values_are_rejected(bad):
    xp.XPool(LABELS, clock=Clock()).begin_pass()
    doc = json.loads(state_file().read_text())
    doc["accounts"]["acct_a"].update(bad)
    state_file().write_text(json.dumps(doc))
    with pytest.raises(xp.XPoolStateError):
        xp.XPool(LABELS, clock=Clock())


def test_b3_rollback_strip_set_is_exactly_the_seven_keys():
    assert set(xp.B3_ACCOUNT_DEFAULTS) <= xp.ACCOUNT_KEYS
    assert len(xp.B3_ACCOUNT_DEFAULTS) == 7
    assert not set(xp.B3_ACCOUNT_DEFAULTS) & (set(xp.B2_ACCOUNT_KEYS) | set(xp.XDRIFT_ACCOUNT_DEFAULTS))
