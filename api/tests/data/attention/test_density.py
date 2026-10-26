"""W8b AC1/AC3: SPEC Annex A.1 density formula and the yesterday-only rule. Pure; no network."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from api.data.attention import density as d

DAY = date(2026, 10, 20)
START = datetime(2026, 10, 20, tzinfo=timezone.utc)
END = START + timedelta(days=1)


def times_back(n: int, step_min: float, first: datetime = END - timedelta(minutes=1)) -> list[datetime]:
    """n timestamps newest first, `step_min` minutes apart."""
    return [first - timedelta(minutes=step_min * i) for i in range(n)]


def test_exact_count_when_window_start_reached():
    r = d.day_value(DAY, times_back(12, 60), n_target=40, n_min=20, window_start_reached=True)
    assert r.value == 12 and r.n == 12 and not r.capped and not r.pagecap


def test_capped_rate_24_times_n_over_span():
    # 50 posts one every 6 min: the 40th newest is 39*6+1 min before the window end
    r = d.day_value(DAY, times_back(50, 6), n_target=40, n_min=20, window_start_reached=False)
    span = (39 * 6 + 1) / 60
    assert r.capped and r.n == 40
    assert r.span_hours == pytest.approx(span)
    assert r.value == pytest.approx(24 * 40 / span)


def test_span_floor_quarter_hour():
    burst = [END - timedelta(seconds=s + 1) for s in range(40)]
    r = d.day_value(DAY, burst, n_target=40, n_min=20, window_start_reached=False)
    assert r.span_hours == d.SPAN_FLOOR_H == 0.25
    assert r.value == pytest.approx(24 * 40 / 0.25)


def test_pagecap_uses_k():
    r = d.day_value(DAY, times_back(25, 30), n_target=40, n_min=20, window_start_reached=False, limit_hit=True)
    span = (24 * 30 + 1) / 60
    assert r.pagecap and r.capped and r.n == 25
    assert r.value == pytest.approx(24 * 25 / span)


def test_below_n_min_is_missing():
    assert d.day_value(DAY, times_back(19, 30), n_target=40, n_min=20, window_start_reached=False,
                       limit_hit=True) is None
    assert d.day_value(DAY, times_back(30, 30), n_target=40, n_min=20, window_start_reached=False) is None


def test_boundary_k_equals_n_is_continuous():
    # 40 posts spread evenly over the full day: the capped estimate is about N
    spread = [END - timedelta(hours=24 * i / 40) - timedelta(seconds=1) for i in range(40)]
    spread[-1] = START
    capped = d.day_value(DAY, spread, n_target=40, n_min=20, window_start_reached=True)
    assert capped.capped and capped.value == pytest.approx(40, rel=1e-6)
    exact = d.day_value(DAY, spread[:39], n_target=40, n_min=20, window_start_reached=True)
    assert exact.value == 39 and abs(capped.value - exact.value) <= 1.01


def test_entries_outside_window_are_ignored():
    inside = times_back(5, 60)
    outside = [END + timedelta(minutes=5), START - timedelta(minutes=5)]
    r = d.day_value(DAY, outside + inside, n_target=40, n_min=20, window_start_reached=True)
    assert r.value == 5


def test_no_value_before_window_end_2359_vs_0000():
    assert not d.storable(DAY, END - timedelta(minutes=1))
    assert d.storable(DAY, END)
    assert d.storable(DAY, END + timedelta(hours=7))


def test_newest_never_today():
    for now in (END, END + timedelta(hours=12), END + timedelta(hours=23, minutes=59)):
        assert d.completed_day(now) == DAY
        assert d.completed_day(now) < now.date()
        assert not d.storable(now.date(), now)


def test_naive_clock_rejected():
    with pytest.raises(ValueError):
        d.storable(DAY, datetime(2026, 10, 21, 1, 0))  # noqa: DTZ001


def test_zero_needs_canary_and_low_median():
    zero = d.day_value(DAY, [], n_target=40, n_min=20, window_start_reached=True)
    assert zero.value == 0
    assert d.finalize(zero, canary_ok=True, trailing_median=2.0) == 0
    assert d.finalize(zero, canary_ok=False, trailing_median=2.0) is None
    assert d.finalize(zero, canary_ok=True, trailing_median=5.0) is None
    assert d.finalize(zero, canary_ok=True, trailing_median=None) is None
    assert d.finalize(None, canary_ok=True, trailing_median=0.0) is None
    some = d.day_value(DAY, times_back(3, 60), n_target=40, n_min=20, window_start_reached=True)
    assert d.finalize(some, canary_ok=False, trailing_median=None) == 3


def test_spike_flag_above_ten_times_median():
    assert d.is_spike(101.0, 10.0) and not d.is_spike(100.0, 10.0)
    assert not d.is_spike(50.0, None) and not d.is_spike(50.0, 0.0)


def test_dedupe_identical_text_and_three_per_author():
    t = END - timedelta(minutes=1)
    posts = [d.Post("a", "same", t), d.Post("b", "same", t), d.Post("c", "x1", t), d.Post("c", "x2", t),
             d.Post("c", "x3", t), d.Post("c", "x4", t), d.Post("e", "  SAME ", t)]
    kept = d.dedupe(posts)
    assert [(p.author, p.text) for p in kept] == [("a", "same"), ("c", "x1"), ("c", "x2"), ("c", "x3")]


def test_bad_config_rejected():
    with pytest.raises(ValueError):
        d.day_value(DAY, [], n_target=10, n_min=20, window_start_reached=True)
    with pytest.raises(ValueError):
        d.day_value(DAY, [], n_target=0, n_min=0, window_start_reached=True)
