"""S-B3P quiet hours: zone-aware window math, midnight crossing, DST gap and fold. Pure; no clock, no network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from api.data.attention import x_quiet as xq

UTC = timezone.utc


def spec(tz="Europe/London", start="22:00", end="06:00"):
    return {"timezone": tz, "start": start, "end": end}


def test_same_day_window_and_outside_is_now():
    s = spec(tz="UTC", start="09:00", end="17:00")
    t = datetime(2026, 11, 7, 8, 59, tzinfo=UTC)
    assert not xq.in_quiet(t, s) and xq.next_outside(t, s) == t
    inside = datetime(2026, 11, 7, 9, 0, tzinfo=UTC)
    assert xq.in_quiet(inside, s)
    assert xq.next_outside(inside, s) == datetime(2026, 11, 7, 17, 0, tzinfo=UTC)
    assert not xq.in_quiet(datetime(2026, 11, 7, 17, 0, tzinfo=UTC), s)


def test_window_crossing_midnight():
    s = spec(tz="UTC")
    assert xq.in_quiet(datetime(2026, 11, 7, 23, 30, tzinfo=UTC), s)
    assert xq.in_quiet(datetime(2026, 11, 8, 5, 59, tzinfo=UTC), s)
    assert not xq.in_quiet(datetime(2026, 11, 8, 6, 0, tzinfo=UTC), s)
    assert xq.next_outside(datetime(2026, 11, 7, 23, 30, tzinfo=UTC), s) == datetime(2026, 11, 8, 6, tzinfo=UTC)
    assert xq.next_outside(datetime(2026, 11, 8, 1, 0, tzinfo=UTC), s) == datetime(2026, 11, 8, 6, tzinfo=UTC)


def test_local_zone_is_honoured():
    s = spec(tz="America/New_York", start="00:00", end="07:00")
    t = datetime(2026, 11, 10, 6, 0, tzinfo=UTC)  # 01:00 EST
    assert xq.in_quiet(t, s)
    assert xq.next_outside(t, s) == datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def test_dst_gap_end_inside_gap_resumes_at_transition():
    # US spring forward 2026-03-08: 02:00 EST jumps to 03:00 EDT (07:00 UTC). Local 02:30 never exists.
    s = spec(tz="America/New_York", start="00:00", end="02:30")
    t = datetime(2026, 3, 8, 6, 0, tzinfo=UTC)  # 01:00 EST
    assert xq.next_outside(t, s) == datetime(2026, 3, 8, 7, 0, tzinfo=UTC)


def test_dst_fold_end_uses_first_occurrence():
    # US fall back 2026-11-01: 02:00 EDT -> 01:00 EST. Local 01:30 occurs twice; the first is 05:30 UTC.
    s = spec(tz="America/New_York", start="00:00", end="01:30")
    t = datetime(2026, 11, 1, 4, 30, tzinfo=UTC)  # 00:30 EDT
    assert xq.next_outside(t, s) == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


def test_result_is_always_utc_and_not_quiet():
    s = spec(tz="Australia/Lord_Howe", start="23:15", end="01:45")
    t = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    for step in range(0, 72 * 4):
        now = t + timedelta(minutes=15 * step)
        nxt = xq.next_outside(now, s)
        assert nxt >= now and nxt.utcoffset() == timedelta(0) and not xq.in_quiet(nxt, s)
        assert nxt - now < timedelta(hours=4)


@pytest.mark.parametrize("bad", [
    {"timezone": "Not/AZone", "start": "01:00", "end": "02:00"},
    {"timezone": "UTC", "start": "01:00", "end": "01:00"},
    {"timezone": "UTC", "start": "24:00", "end": "01:00"},
    {"timezone": "UTC", "start": "1:00", "end": "02:00"},
    {"timezone": "UTC", "start": "01:00"},
])
def test_bad_window_rejected(bad):
    with pytest.raises(ValueError):
        xq.parse_window(bad)


def test_naive_time_rejected():
    with pytest.raises(ValueError):
        xq.in_quiet(datetime(2026, 11, 7, 1, 0), spec())


def test_label_lookup_off_or_unconfigured_is_none():
    windows = {"acct_a": spec(tz="UTC")}
    t = datetime(2026, 11, 7, 23, 0, tzinfo=UTC)
    assert xq.quiet_until(t, "acct_a", windows, enabled=False) is None
    assert xq.quiet_until(t, "acct_b", windows, enabled=True) is None
    assert xq.quiet_until(t, "acct_a", windows, enabled=True) == datetime(2026, 11, 8, 6, tzinfo=UTC)
    assert xq.quiet_until(datetime(2026, 11, 7, 12, 0, tzinfo=UTC), "acct_a", windows, enabled=True) is None
