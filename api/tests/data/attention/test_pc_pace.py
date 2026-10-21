"""W8b AC8/AC10/AC21/AC22: trickle pace, daily read budget, adaptive budget, pause state, queue.

Injected clock and seeded RNG throughout; the fake adapter stands in for the transport. Pure; no network.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from itertools import pairwise

import pytest

from api.data.attention import pc_adapter as pa
from api.data.attention import pc_pace as pp
from api.data.attention import web_queries as wq

T0 = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
YESTERDAY = date(2026, 10, 20)


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    """Every test here writes state or evidence: keep it out of the real cache root."""
    return attention_cache



class Clock:
    def __init__(self, now: datetime = T0):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> None:
        self.now += timedelta(**kw)


def x_source(clock, budget: int = 800, unit: int = 40) -> pp.PcSource:
    return pp.PcSource("xsearch_web", configured_budget=budget, floor=unit, adaptive=True, clock=clock)


def reddit_source(clock) -> pp.PcSource:
    return pp.PcSource("reddit_web", configured_budget=150, floor=1, adaptive=False, clock=clock)


def cfg(**over) -> wq.CollectorConfig:
    return wq.CollectorConfig(**{**wq.DEFAULTS, **over})


def posts(n: int, newest: datetime, step_min: float, prefix: str = "p") -> list[pa.Post]:
    return [pa.Post(f"{prefix}{i}", f"{prefix} text {i}", newest - timedelta(minutes=step_min * i)) for i in range(n)]


# --- AC8 trickle -----------------------------------------------------------------------------------------------

def test_x_spacing_within_configured_min_max_seeded():
    a = pp.Trickle(180, 360, random.Random(7))
    b = pp.Trickle(180, 360, random.Random(7))
    delays = [a.next_delay() for _ in range(500)]
    assert all(180 <= x <= 360 for x in delays)
    assert delays == [b.next_delay() for _ in range(500)]
    assert min(delays) < 200 and max(delays) > 340


def test_x_spacing_follows_changed_config():
    t = pp.Trickle.for_source(cfg(x_query_delay_min_s=600, x_query_delay_max_s=900), "xsearch_web", random.Random(1))
    assert all(600 <= t.next_delay() <= 900 for _ in range(200))


def test_reddit_spacing_within_configured_60_120_seconds_seeded():
    t = pp.Trickle.for_source(cfg(), "reddit_web", random.Random(3))
    delays = [t.next_delay() for _ in range(500)]
    assert all(60 <= x <= 120 for x in delays)


def test_reddit_daily_budget_150():
    clock = Clock()
    src = reddit_source(clock)
    for _ in range(150):
        assert src.can_spend(1)
        src.spend(1)
    assert not src.can_spend(1)
    with pytest.raises(pa.BudgetSpent):
        src.spend(1)
    assert src.remaining() == 0


def test_catch_up_never_faster_than_min_delay():
    t = pp.Trickle(180, 360, random.Random(11))
    last = T0 - timedelta(seconds=30)            # a unit ran 30 s before this restart
    runs = pp.plan_run(t, start=T0, stop=T0 + timedelta(hours=3), last_unit_at=last)
    assert runs[0] >= last + timedelta(seconds=180)
    assert runs[0] >= T0 + timedelta(seconds=pp.BEHIND_DELAY_S)
    gaps = [(b - a).total_seconds() for a, b in pairwise(runs)]
    assert gaps and min(gaps) >= 180


def test_days_off_start_is_behind_delay_then_same_pace():
    t = pp.Trickle(180, 360, random.Random(5))
    runs = pp.plan_run(t, start=T0, stop=T0 + timedelta(hours=1), last_unit_at=T0 - timedelta(days=4))
    assert runs[0] == T0 + timedelta(seconds=pp.BEHIND_DELAY_S)
    assert all((b - a).total_seconds() >= 180 for a, b in pairwise(runs))


def test_few_hours_uptime_runs_at_configured_pace():
    t = pp.Trickle(180, 360, random.Random(2))
    stop = T0 + timedelta(hours=2)
    runs = pp.plan_run(t, start=T0, stop=stop)
    assert all(T0 <= r < stop for r in runs)
    assert 2 * 3600 // 360 <= len(runs) <= 2 * 3600 // 180 + 1
    one_hour = pp.plan_run(pp.Trickle(180, 360, random.Random(2)), start=T0, stop=T0 + timedelta(hours=1))
    assert 10 <= len(one_hour) <= 21


def test_yesterday_before_backfill():
    stored = {"SOL": {YESTERDAY - timedelta(days=1)}, "ETH": {YESTERDAY}}
    q = pp.build_queue(["SOL", "ETH", "BTC"], now=T0, stored=stored, backfill_days=3)
    assert q[:2] == [("SOL", YESTERDAY), ("BTC", YESTERDAY)]
    assert q[2:] == [("ETH", YESTERDAY - timedelta(days=1)), ("BTC", YESTERDAY - timedelta(days=1)),
                     ("SOL", YESTERDAY - timedelta(days=2)), ("ETH", YESTERDAY - timedelta(days=2)),
                     ("BTC", YESTERDAY - timedelta(days=2)), ("SOL", YESTERDAY - timedelta(days=3)),
                     ("ETH", YESTERDAY - timedelta(days=3)), ("BTC", YESTERDAY - timedelta(days=3))]
    assert all(d < T0.date() for _, d in q)
    assert pp.build_queue(["SOL"], now=T0, stored={}, backfill_days=0) == [("SOL", YESTERDAY)]


def test_rotation_queue_oldest_newest_stored_first():
    stored = {"SOL": {YESTERDAY - timedelta(days=2)},
              "ETH": {YESTERDAY - timedelta(days=9), YESTERDAY - timedelta(days=5)},
              "LINK": {YESTERDAY}}
    q = pp.build_queue(["SOL", "ETH", "BTC", "AAVE", "LINK"], now=T0, stored=stored, backfill_days=0, rotation=True)
    assert q == [("BTC", YESTERDAY), ("AAVE", YESTERDAY), ("ETH", YESTERDAY), ("SOL", YESTERDAY)]
    window = pp.build_queue(["SOL", "ETH", "BTC", "AAVE", "LINK"], now=T0, stored=stored, backfill_days=0)
    assert window == [("SOL", YESTERDAY), ("ETH", YESTERDAY), ("BTC", YESTERDAY), ("AAVE", YESTERDAY)]


def test_pace_rejects_bad_delays():
    for lo, hi in ((0, 10), (10, 5), (-1, 3)):
        with pytest.raises(ValueError):
            pp.Trickle(lo, hi, random.Random(0))


# --- AC21 daily read budget --------------------------------------------------------------------------------------

def run_unit(adapter, src, clock, c=None, symbol="SOL", day=YESTERDAY, sleeps=None):
    return pp.run_x_unit(adapter, src, c or cfg(), symbol=symbol, day=day, query="q", rng=random.Random(0),
                         sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


def test_budget_counts_posts_loaded_including_dropped(attention_cache):
    clock = Clock()
    end = datetime(2026, 10, 21, tzinfo=timezone.utc)
    dup = [pa.Post("a", "same text", end - timedelta(minutes=i + 1)) for i in range(20)]
    adapter = pa.FakeAdapter(pages=[pa.SearchPage(dup, has_more=True),
                                    pa.SearchPage(posts(20, end - timedelta(minutes=30), 1), has_more=False)])
    src = x_source(clock)
    out = run_unit(adapter, src, clock)
    assert out.posts_loaded == 40 and src.used == 40
    assert out.result is not None and out.result.n == 21    # 1 kept from the duplicates + 20


def test_page_load_refused_when_it_would_exceed_budget(attention_cache):
    clock = Clock()
    src = x_source(clock, budget=50)
    end = datetime(2026, 10, 21, tzinfo=timezone.utc)
    adapter = pa.FakeAdapter(pages=[pa.SearchPage(posts(20, end - timedelta(minutes=1), 2), has_more=True)] * 3,
                             page_size=20)
    out = run_unit(adapter, src, clock)
    assert adapter.calls == 2 and src.used == 40 and out.stop == "budget_spent"
    assert src.budget_spent() and not src.can_spend(20)


def test_unread_coin_days_missing_not_zero(attention_cache):
    clock = Clock()
    src = x_source(clock, budget=40)
    src.spend(40)
    adapter = pa.FakeAdapter(pages=[])
    out = run_unit(adapter, src, clock)
    assert adapter.calls == 0 and out.result is None and out.stop == "budget_spent"


def test_unit_with_k_at_least_n_min_kept_when_budget_ends(attention_cache):
    clock = Clock()
    src = x_source(clock, budget=40)
    end = datetime(2026, 10, 21, tzinfo=timezone.utc)
    adapter = pa.FakeAdapter(pages=[pa.SearchPage(posts(20, end - timedelta(minutes=1), 10), has_more=True),
                                    pa.SearchPage(posts(5, end - timedelta(hours=4), 10, "q"), has_more=True),
                                    pa.SearchPage(posts(20, end - timedelta(hours=8), 10, "r"), has_more=True)])
    out = run_unit(adapter, src, clock)
    assert out.stop == "budget_spent" and out.result is not None
    assert out.result.n == 25 and out.result.pagecap and out.result.capped


def test_page_spacing_inside_unit_5_to_15_seconds(attention_cache):
    clock = Clock()
    end = datetime(2026, 10, 21, tzinfo=timezone.utc)
    adapter = pa.FakeAdapter(pages=[pa.SearchPage(posts(10, end - timedelta(minutes=1), 5, c), has_more=True)
                                    for c in "abc"])
    sleeps: list[float] = []
    out = run_unit(adapter, x_source(clock), clock, sleeps=sleeps)
    assert adapter.calls == 3 and out.stop == "pagecap" and out.result is not None and out.result.pagecap
    assert len(sleeps) == 2 and all(5 <= s <= 15 for s in sleeps)


def test_budget_resets_at_utc_midnight(attention_cache):
    clock = Clock(datetime(2026, 10, 21, 23, 59, tzinfo=timezone.utc))
    src = x_source(clock)
    src.spend(800)
    assert src.budget_spent()
    clock.advance(minutes=1)
    assert src.remaining() == 800 and not src.budget_spent()


def test_budget_count_survives_restart(attention_cache):
    clock = Clock()
    x_source(clock).spend(120)
    again = x_source(clock)
    assert again.used == 120 and again.remaining() == 680


# --- AC22 adaptive budget -------------------------------------------------------------------------------------

def day_with_unit(src, clock, warned=False):
    src.record_unit()
    if warned:
        src.warn("rate_limited")
    clock.advance(days=1)


def test_warning_day_halves_next_day_budget_floor_one_unit(attention_cache):
    clock = Clock()
    src = x_source(clock)
    day_with_unit(src, clock, warned=True)
    assert src.effective_budget() == 400
    for expected in (200, 100, 50, 40, 40):
        day_with_unit(src, clock, warned=True)
        assert src.effective_budget() == expected


def test_seven_clean_days_double_once_up_to_configured(attention_cache):
    clock = Clock()
    src = x_source(clock)
    day_with_unit(src, clock, warned=True)
    day_with_unit(src, clock, warned=True)
    assert src.effective_budget() == 200
    for _ in range(6):
        day_with_unit(src, clock)
        assert src.effective_budget() == 200
    day_with_unit(src, clock)
    assert src.effective_budget() == 400
    for _ in range(7):
        day_with_unit(src, clock)
    assert src.effective_budget() == 800
    for _ in range(7):
        day_with_unit(src, clock)
    assert src.effective_budget() == 800


def test_warning_resets_clean_count(attention_cache):
    clock = Clock()
    src = x_source(clock)
    day_with_unit(src, clock, warned=True)
    for _ in range(6):
        day_with_unit(src, clock)
    day_with_unit(src, clock, warned=True)
    assert src.effective_budget() == 200
    for _ in range(6):
        day_with_unit(src, clock)
    assert src.effective_budget() == 200


def test_no_activity_day_changes_nothing(attention_cache):
    clock = Clock()
    src = x_source(clock)
    day_with_unit(src, clock, warned=True)
    for _ in range(6):
        day_with_unit(src, clock)
    clock.advance(days=5)                       # PC off: no units, no warnings
    assert src.effective_budget() == 400
    day_with_unit(src, clock)                   # the seventh clean day
    assert src.effective_budget() == 800


def test_adaptive_state_survives_restart(attention_cache):
    clock = Clock()
    src = x_source(clock)
    day_with_unit(src, clock, warned=True)
    assert x_source(clock).effective_budget() == 400


def test_reddit_budget_is_not_adaptive(attention_cache):
    clock = Clock()
    src = reddit_source(clock)
    src.record_unit()
    src.warn("rate_limited")
    clock.advance(days=1)
    assert src.effective_budget() == 150


# --- AC10 pause on warning -----------------------------------------------------------------------------------------

def test_429_pauses_until_next_utc_midnight(attention_cache):
    clock = Clock()
    src = x_source(clock)
    adapter = pa.FakeAdapter(pages=[pa.RateLimited(429)])
    out = run_unit(adapter, src, clock)
    assert out.stop == "rate_limited" and out.result is None
    assert src.is_paused() and src.pause_reason() == "rate_limited"
    clock.now = datetime(2026, 10, 21, 23, 59, 59, tzinfo=timezone.utc)
    assert src.is_paused()
    clock.now = datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc)
    assert not src.is_paused()


def test_pause_persists_over_restart(attention_cache):
    clock = Clock()
    x_source(clock).warn("rate_limited")
    assert x_source(clock).is_paused()


def test_no_retry_after_warning(attention_cache):
    clock = Clock()
    src = x_source(clock)
    adapter = pa.FakeAdapter(pages=[pa.RateLimited(429), pa.SearchPage(posts(5, T0, 1), has_more=False)])
    run_unit(adapter, src, clock)
    assert adapter.calls == 1
    out = run_unit(adapter, src, clock, symbol="ETH")
    assert adapter.calls == 1 and out.stop == "paused" and out.result is None


def test_suspension_and_login_expired_stay_paused(attention_cache):
    for exc, reason in ((pa.AccountSuspended(403), "x_account_suspended"), (pa.LoginRequired(401), "x_login_required")):
        clock = Clock()
        src = x_source(clock)
        src.owner_reset()
        run_unit(pa.FakeAdapter(pages=[exc]), src, clock)
        clock.advance(days=3)
        assert src.is_paused() and src.pause_reason() == reason
        assert x_source(clock).is_paused()
        src.owner_reset()
        assert not src.is_paused()


def test_owner_action_pause_not_downgraded(attention_cache):
    clock = Clock()
    src = x_source(clock)
    src.warn("x_account_suspended")
    src.warn("rate_limited")
    clock.advance(days=2)
    assert src.is_paused() and src.pause_reason() == "x_account_suspended"


def test_failed_attempt_stamps_time_for_next_delay(attention_cache):
    clock = Clock()
    src = x_source(clock)
    run_unit(pa.FakeAdapter(pages=[pa.Offline()]), src, clock)
    assert src.last_unit_at() == T0
    t = pp.Trickle(180, 360, random.Random(0))
    assert t.first_due(T0, src.last_unit_at()) == T0 + timedelta(seconds=180)

    class Broken(pa.FakeAdapter):
        def search_page(self, *a):
            raise RuntimeError

    clock.advance(minutes=10)
    with pytest.raises(RuntimeError):
        run_unit(Broken(), src, clock)
    assert src.last_unit_at() == T0 + timedelta(minutes=10)


def test_other_source_keeps_running(attention_cache):
    clock = Clock()
    x_source(clock).warn("rate_limited")
    assert not reddit_source(clock).is_paused()
    assert reddit_source(clock).can_spend(1)


def test_offline_and_layout_change_do_not_pause(attention_cache):
    for exc in (pa.Offline(), pa.LayoutChanged()):
        clock = Clock()
        src = x_source(clock)
        out = run_unit(pa.FakeAdapter(pages=[exc]), src, clock)
        assert out.result is None and out.stop == exc.reason and not src.is_paused()


def test_state_file_under_cache_pc_state(attention_cache):
    clock = Clock()
    x_source(clock).spend(1)
    assert (attention_cache / "attention" / "_pc_state" / "xsearch_web.json").exists()


def test_unknown_warning_reason_rejected(attention_cache):
    with pytest.raises(ValueError):
        x_source(Clock()).warn("whatever")
