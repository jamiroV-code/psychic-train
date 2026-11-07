"""S-B3P behaviour policy: warm-up cap ladder, seeded variation, cooldown decisions and precedence, mixed-call
budget. Pure rules only; every switch off returns the Part A behaviour unchanged. No clock, no network."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from api.data.attention import x_behaviour as xb

NOW = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)
D0 = date(2026, 11, 1)


# --- warm-up ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("offset,cap", [(0, 100), (1, 100), (2, 200), (3, 200), (4, 400), (6, 400), (7, 600),
                                        (30, 600)])
def test_warmup_ladder_boundaries(offset, cap):
    assert xb.effective_cap(600, D0.isoformat(), D0 + timedelta(days=offset), enabled=True) == cap


def test_warmup_never_raises_a_lower_configured_cap_and_supplies_finite_caps_for_unlimited():
    assert xb.effective_cap(150, D0.isoformat(), D0 + timedelta(days=3), enabled=True) == 150
    assert xb.effective_cap(None, D0.isoformat(), D0, enabled=True) == 100
    assert xb.effective_cap(None, D0.isoformat(), D0 + timedelta(days=7), enabled=True) is None


def test_warmup_off_not_started_or_grandfathered_keeps_configured_cap():
    assert xb.effective_cap(600, D0.isoformat(), D0, enabled=False) == 600
    assert xb.effective_cap(600, None, D0, enabled=True) == 600
    assert xb.effective_cap(600, D0.isoformat(), D0, enabled=True, grandfathered=True) == 600


def test_warmup_stage_and_start_only_when_eligible():
    assert [xb.warmup_stage(D0.isoformat(), D0 + timedelta(days=d)) for d in (0, 2, 4, 7)] == [1, 2, 3, None]
    assert xb.warmup_stage(None, D0) is None
    assert xb.warmup_start(None, eligible=False, today=D0, enabled=True) is None
    assert xb.warmup_start(None, eligible=True, today=D0, enabled=True) == "2026-11-01"
    assert xb.warmup_start("2026-10-01", eligible=True, today=D0, enabled=True) == "2026-10-01"  # never reset
    assert xb.warmup_start(None, eligible=True, today=D0, enabled=False) is None


# --- variation ----------------------------------------------------------------------------------------------------

def test_variation_off_is_identity():
    v = xb.variation("acct_a", D0, page_cap=20, enabled=False)
    assert (v.page_size, v.pause_multiplier) == (20, 1.0)
    assert v.order(["SOL", "BTC", "ETH"]) == ["SOL", "BTC", "ETH"]


def test_variation_is_seeded_per_label_and_day_and_bounded():
    a = xb.variation("acct_a", D0, page_cap=20, enabled=True)
    assert a == xb.variation("acct_a", D0, page_cap=20, enabled=True)
    seen = set()
    for d in range(60):
        for label in ("acct_a", "acct_b"):
            v = xb.variation(label, D0 + timedelta(days=d), page_cap=20, enabled=True)
            assert v.page_size in (10, 20) and 1.0 <= v.pause_multiplier <= 1.2
            seen.add((v.page_size, round(v.pause_multiplier, 1)))
    assert {s[0] for s in seen} == {10, 20}


def test_variation_respects_lower_page_cap():
    for d in range(20):
        assert xb.variation("acct_a", D0 + timedelta(days=d), page_cap=15, enabled=True).page_size == 10
    assert xb.variation("acct_a", D0, page_cap=5, enabled=True).page_size == 5


def test_variation_shuffles_only_equally_due_groups():
    v = xb.variation("acct_a", D0, page_cap=20, enabled=True)
    groups = [["A", "B", "C", "D", "E"], ["F"], ["G", "H"]]
    out = v.order_groups(groups)
    assert [sorted(g) for g in out] == [sorted(g) for g in groups]
    assert out == v.order_groups(groups)
    assert any(xb.variation("acct_a", D0 + timedelta(days=d), page_cap=20, enabled=True).order(list("ABCDEF"))
               != list("ABCDEF") for d in range(10))


# --- cooldown -----------------------------------------------------------------------------------------------------

def test_challenge_pauses_without_deadline_even_when_off():
    d = xb.cooldown(NOW, enabled=False, challenge=True)
    assert (d.reason, d.until, d.owner_pause) == ("challenge", None, True)


def test_off_adds_no_cooldown_for_other_signals():
    assert xb.cooldown(NOW, enabled=False, stripped_strike=True, rate_remaining=0, shrink_run=5) is None


def test_stripped_strike_one_hour_or_longer_lock():
    assert xb.cooldown(NOW, enabled=True, stripped_strike=True).until == NOW + timedelta(hours=1)
    lock = NOW + timedelta(hours=3)
    d = xb.cooldown(NOW, enabled=True, stripped_strike=True, lock_until=lock)
    assert (d.reason, d.until) == ("stripped_strike", lock)


def test_rate_limit_waits_for_reset_or_fifteen_minutes():
    reset = NOW + timedelta(minutes=7)
    assert xb.cooldown(NOW, enabled=True, rate_remaining=1, rate_reset=reset).until == reset
    assert xb.cooldown(NOW, enabled=True, rate_remaining=0).until == NOW + timedelta(minutes=15)
    assert xb.cooldown(NOW, enabled=True, rate_remaining=2) is None


def test_shrink_run_three_triggers_one_hour():
    assert xb.cooldown(NOW, enabled=True, shrink_run=2) is None
    d = xb.cooldown(NOW, enabled=True, shrink_run=3)
    assert (d.reason, d.until) == ("shrink", NOW + timedelta(hours=1))


def test_precedence_challenge_then_latest_deadline():
    d = xb.cooldown(NOW, enabled=True, challenge=True, stripped_strike=True, rate_remaining=0, shrink_run=3)
    assert d.reason == "challenge"
    d = xb.cooldown(NOW, enabled=True, stripped_strike=True, rate_remaining=0, shrink_run=3)
    assert d.reason == "stripped_strike" and d.until == NOW + timedelta(hours=1)
    d = xb.cooldown(NOW, enabled=True, rate_remaining=0, rate_reset=NOW + timedelta(hours=2), shrink_run=3)
    assert d.reason == "rate_limit" and d.until == NOW + timedelta(hours=2)
    assert all(r in xb.BEHAVIOUR_REASONS for r in ("challenge", "stripped_strike", "rate_limit", "shrink"))


def _history(counts, qc="coin"):
    return [{"day": (D0 + timedelta(days=i)).isoformat(), "count": c, "query_class": qc} for i, c in enumerate(counts)]


def test_shrink_needs_seven_comparable_observations():
    hist, run = xb.record_result(_history([100] * 6), 0, day=D0, count=1, query_class="coin", canary=False)
    assert run == 0 and len(hist) == 7
    hist, run = xb.record_result(_history([100] * 6 + [100], qc="other"), 0, day=D0, count=1, query_class="coin",
                                 canary=False)
    assert run == 0


def test_shrink_run_counts_and_resets_on_recovery_and_history_bounded():
    hist, run = _history([100] * 7), 0
    for _ in range(3):
        hist, run = xb.record_result(hist, run, day=D0, count=10, query_class="coin", canary=False)
    assert len(hist) == 7 and run == 3
    hist, run = xb.record_result(_history([100] * 7), 2, day=D0, count=30, query_class="coin", canary=False)
    assert run == 0


def test_canary_and_failed_units_do_not_touch_history():
    hist = _history([100] * 7)
    assert xb.record_result(hist, 2, day=D0, count=1, query_class="coin", canary=True) == (hist, 2)
    assert xb.record_result(hist, 2, day=D0, count=None, query_class="coin", canary=False) == (hist, 2)


# --- mixed traffic budget -----------------------------------------------------------------------------------------

def test_mixed_allowlist_and_budget():
    ok = dict(enabled=True, units_since_last=20, calls_today=0, room=20)
    assert xb.mixed_allowed("user_by_login", **ok)
    assert xb.mixed_allowed("tweet_details", **ok) and xb.mixed_allowed("user_tweets", **ok)
    assert not xb.mixed_allowed("home_timeline", **ok)
    assert not xb.mixed_allowed("user_by_login", **{**ok, "enabled": False})
    assert not xb.mixed_allowed("user_by_login", **{**ok, "units_since_last": 19})
    assert not xb.mixed_allowed("user_by_login", **{**ok, "calls_today": 3})
    assert not xb.mixed_allowed("user_by_login", **{**ok, "room": 19})
    assert xb.MIXED_OPS == ("user_by_login", "tweet_details", "user_tweets")


def test_mixed_charge_and_day_rollover():
    assert xb.mixed_charge(0) == 20 and xb.mixed_charge(35) == 35
    with pytest.raises(ValueError):
        xb.mixed_charge(-1)
    assert xb.mixed_today("2026-10-31", 3, D0) == 0
    assert xb.mixed_today("2026-11-01", 2, D0) == 2
    assert xb.mixed_today(None, 0, D0) == 0
