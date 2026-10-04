"""T32 / S1 — pure freshness rules (`api/data/freshness.py`, B4/B5).

`freshness` is imported inside each test (not at module top) so that, on a
base without the module, every test here fails on its own instead of the
whole G-S1-1 run aborting at collection.
"""
from __future__ import annotations

import importlib

import pandas as pd

S = pd.Timedelta(seconds=1)


def _f():
    return importlib.import_module("api.data.freshness")


def test_stale_threshold_per_timeframe_boundary():
    f = _f()
    now = pd.Timestamp("2026-10-03T14:10:00Z")
    for timeframe, threshold in [("15m", 2700), ("1h", 8100), ("4h", 29700), ("1d", 173700)]:
        assert f.stale_threshold_seconds(timeframe) == threshold
        # strict: exactly at the threshold is not yet stale
        assert f.is_stale(now - threshold * S, timeframe, now) is False
        assert f.is_stale(now - (threshold + 1) * S, timeframe, now) is True
        assert f.is_stale(None, timeframe, now) is False


def test_one_week_staleness_is_judged_on_its_daily_bar():
    f = _f()
    now = pd.Timestamp("2026-10-03T14:10:00Z")
    assert f.stale_threshold_seconds("1w") == f.stale_threshold_seconds("1d")
    # a weekly bar opened 5 days ago would be "old" for 1d, but the caller
    # passes the DAILY bar's open; judged on that, it is fresh
    daily_open = now.floor("D")
    assert f.is_stale(daily_open, "1w", now) is False
    assert f.is_stale(now - 173701 * S, "1w", now) is True


def test_is_partial_true_inside_bar_false_after_close():
    f = _f()
    bar_open = pd.Timestamp("2026-10-03T00:00:00Z")
    for timeframe, seconds in [("15m", 900), ("1h", 3600), ("4h", 14400), ("1d", 86400)]:
        assert f.is_partial(bar_open, timeframe, bar_open + (seconds - 1) * S) is True
        assert f.is_partial(bar_open, timeframe, bar_open + seconds * S) is False
        assert f.is_partial(None, timeframe, bar_open) is None


def test_cache_is_fresh_requires_fetch_inside_current_bar():
    f = _f()
    now = pd.Timestamp("2026-10-03T14:01:00Z")  # 1h bar opened 14:00
    assert f.current_bar_open("1h", now) == pd.Timestamp("2026-10-03T14:00:00Z")
    assert f.current_bar_open("15m", now) == pd.Timestamp("2026-10-03T14:00:00Z")
    assert f.current_bar_open("4h", now) == pd.Timestamp("2026-10-03T12:00:00Z")
    assert f.current_bar_open("1d", now) == pd.Timestamp("2026-10-03T00:00:00Z")
    assert f.current_bar_open("1w", now) == pd.Timestamp("2026-09-28T00:00:00Z")  # Monday
    # fetched 2 minutes ago, i.e. inside the TTL but in the PREVIOUS bar
    assert f.cache_is_fresh(now - 120 * S, "1h", now) is False
    # fetched 30 s ago, inside the current bar and the TTL
    assert f.cache_is_fresh(now - 30 * S, "1h", now) is True
    assert f.cache_is_fresh(None, "1h", now) is False


def test_forming_ttl_boundary_per_timeframe():
    f = _f()
    bar_open = pd.Timestamp("2026-10-03T00:00:00Z")
    fetched = bar_open + 1 * S
    for timeframe, ttl in [("15m", 180), ("1h", 300), ("4h", 900), ("1d", 900)]:
        assert f.FORMING_TTL[timeframe] == ttl
        assert f.cache_is_fresh(fetched, timeframe, fetched + (ttl - 1) * S) is True
        assert f.cache_is_fresh(fetched, timeframe, fetched + ttl * S) is False
