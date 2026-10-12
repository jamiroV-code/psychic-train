"""S9A: US market calendar (pure; every case injects `now`)."""
from __future__ import annotations

from datetime import date

import pandas as pd

from api.data import equities_calendar as cal


def T(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


FRI_OCT_9 = date(2026, 10, 9)
MON_OCT_12 = date(2026, 10, 12)
FRI_SEP_4 = date(2026, 9, 4)


def test_close_daylight_fri_oct_30():
    assert cal.session_close_utc(date(2026, 10, 30)) == T("2026-10-30 20:00")


def test_close_standard_mon_nov_2_after_nov_1_edge():
    assert cal.session_close_utc(date(2026, 11, 2)) == T("2026-11-02 21:00")


def test_close_standard_fri_mar_6():
    assert cal.session_close_utc(date(2026, 3, 6)) == T("2026-03-06 21:00")


def test_close_daylight_mon_mar_9_after_mar_8_edge():
    assert cal.session_close_utc(date(2026, 3, 9)) == T("2026-03-09 20:00")


def test_saturday_with_friday_bar_not_stale():
    assert cal.bar_is_stale(FRI_OCT_9, T("2026-10-10 12:00")) is False


def test_sunday_with_friday_bar_not_stale():
    assert cal.bar_is_stale(FRI_OCT_9, T("2026-10-11 23:00")) is False


def test_monday_morning_with_friday_bar_not_stale():
    assert cal.bar_is_stale(FRI_OCT_9, T("2026-10-12 10:00")) is False


def test_monday_after_due_with_friday_bar_stale():
    assert cal.last_due_session(T("2026-10-12 21:30")) == MON_OCT_12
    assert cal.bar_is_stale(FRI_OCT_9, T("2026-10-12 21:30")) is True


def test_monday_after_due_with_monday_bar_not_stale():
    assert cal.bar_is_stale(MON_OCT_12, T("2026-10-12 21:30")) is False
    assert cal.bar_is_stale(pd.Timestamp("2026-10-12", tz="UTC"), T("2026-10-12 21:30")) is False


def test_labor_day_evening_with_friday_bar_not_stale():
    assert cal.bar_is_stale(FRI_SEP_4, T("2026-09-07 23:00")) is False


def test_tuesday_after_labor_day_morning_with_friday_bar_not_stale():
    assert cal.bar_is_stale(FRI_SEP_4, T("2026-09-08 12:00")) is False


def test_next_refresh_after_friday_close_is_monday():
    assert cal.next_refresh_at(T("2026-10-09 21:00")) == T("2026-10-12 20:30")


def test_next_refresh_skips_labor_day():
    assert cal.next_refresh_at(T("2026-09-04 21:00")) == T("2026-09-08 20:30")


def test_next_refresh_skips_thanksgiving_and_good_friday():
    assert cal.next_refresh_at(T("2026-11-25 22:00")) == T("2026-11-27 21:30")
    assert cal.next_refresh_at(T("2026-04-02 21:00")) == T("2026-04-06 20:30")
    # Strictly after: exactly at a refresh time moves to the next session.
    assert cal.next_refresh_at(T("2026-10-12 20:30")) == T("2026-10-13 20:30")


def test_unknown_bar_not_stale_and_daily_partial_until_due():
    assert cal.bar_is_stale(None, T("2026-10-12 21:30")) is False
    assert cal.bar_is_partial(None, T("2026-10-12 21:30")) is None
    assert cal.bar_is_partial(MON_OCT_12, T("2026-10-12 20:59")) is True
    assert cal.bar_is_partial(MON_OCT_12, T("2026-10-12 21:00")) is False


def test_weekly_partial_until_last_session_of_week_due():
    # Week of Mon 10-12: Friday 10-16 closes 20:00Z, due 21:00Z.
    assert cal.bar_is_partial(MON_OCT_12, T("2026-10-12 21:30"), "1w") is True
    assert cal.bar_is_partial(date(2026, 10, 16), T("2026-10-16 20:59"), "1w") is True
    assert cal.bar_is_partial(date(2026, 10, 16), T("2026-10-16 21:00"), "1w") is False
    # Good Friday week: Thursday 04-02 is the last session.
    assert cal.bar_is_partial(date(2026, 4, 2), T("2026-04-02 21:00"), "1w") is False
