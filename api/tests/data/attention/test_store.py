from datetime import date, timedelta

import pandas as pd
import pytest

from api.data import cache
from api.data.attention import store
from api.data.attention.types import SourceSeries

TODAY = date(2026, 10, 16)


def _s(points, source="wikipedia", symbol="BTC"):
    return SourceSeries(source=source, symbol=symbol, points=points, state="ok", reason="")


def test_round_trip(attention_cache):
    pts = [(TODAY - timedelta(days=3), 1.0), (TODAY - timedelta(days=2), 2.0)]
    store.write_series(_s(pts), today=TODAY)
    assert store.read_points("wikipedia", "BTC") == pts


def test_path_under_cache_root_at_call_time(attention_cache):
    p = store.store_path("wikipedia", "btc")
    assert p == attention_cache / "attention" / "wikipedia" / "BTC.parquet"


def test_path_follows_cache_root_change(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    monkeypatch.setattr(cache, "CACHE_ROOT", a)
    pa = store.store_path("wikipedia", "BTC")
    monkeypatch.setattr(cache, "CACHE_ROOT", b)
    assert store.store_path("wikipedia", "BTC") != pa


def test_completed_days_only(attention_cache):
    pts = [(TODAY - timedelta(days=1), 1.0), (TODAY, 9.0), (TODAY + timedelta(days=1), 9.0)]
    store.write_series(_s(pts), today=TODAY)
    assert store.read_points("wikipedia", "BTC") == [(TODAY - timedelta(days=1), 1.0)]


def test_first_observation_wins(attention_cache):
    d = TODAY - timedelta(days=2)
    store.write_series(_s([(d, 1.0)]), today=TODAY)
    store.write_series(_s([(d, 5.0), (TODAY - timedelta(days=1), 2.0)]), today=TODAY)
    assert store.read_points("wikipedia", "BTC") == [(d, 1.0), (TODAY - timedelta(days=1), 2.0)]


def test_one_row_per_day_within_a_write(attention_cache):
    d = TODAY - timedelta(days=2)
    store.write_series(_s([(d, 1.0), (d, 7.0)]), today=TODAY)
    assert store.read_points("wikipedia", "BTC") == [(d, 1.0)]


def test_read_missing_is_empty(attention_cache):
    assert store.read_points("wikipedia", "NOPE") == []


def test_no_write_when_nothing_completed(attention_cache):
    store.write_series(_s([(TODAY, 1.0)]), today=TODAY)
    assert not store.store_path("wikipedia", "BTC").exists()


def test_atomic_no_temp_leftovers(attention_cache):
    store.write_series(_s([(TODAY - timedelta(days=1), 1.0)]), today=TODAY)
    d = store.store_path("wikipedia", "BTC").parent
    assert [p.name for p in d.iterdir()] == ["BTC.parquet"]


def test_sorted_by_date(attention_cache):
    a, b = TODAY - timedelta(days=5), TODAY - timedelta(days=2)
    store.write_series(_s([(b, 2.0), (a, 1.0)]), today=TODAY)
    assert [d for d, _ in store.read_points("wikipedia", "BTC")] == [a, b]


def test_stored_frame_has_one_row_per_day(attention_cache):
    d = TODAY - timedelta(days=1)
    store.write_series(_s([(d, 1.0)]), today=TODAY)
    df = pd.read_parquet(store.store_path("wikipedia", "BTC"))
    assert len(df) == 1


# --- T100b: mode="replace-series" (Trends only); the default mode stays first-write-wins. ---

def _run_of(n, value=1.0, end=TODAY - timedelta(days=1)):
    return [(end - timedelta(days=n - 1 - i), float(value)) for i in range(n)]


def test_replace_series_drops_old_rows(attention_cache):
    old = _run_of(95, 1.0, end=TODAY - timedelta(days=10))
    store.write_series(_s(old, source="trends"), today=TODAY)
    new = _run_of(92, 2.0)
    assert store.write_series(_s(new, source="trends"), today=TODAY, mode="replace-series") == 92
    assert store.read_points("trends", "BTC") == new


def test_replace_series_ignores_today_and_future(attention_cache):
    pts = _run_of(91, 3.0) + [(TODAY, 9.0), (TODAY + timedelta(days=1), 9.0)]
    assert store.write_series(_s(pts, source="trends"), today=TODAY, mode="replace-series") == 91
    assert all(d < TODAY for d, _ in store.read_points("trends", "BTC"))


def test_replace_series_short_pull_keeps_old_series(attention_cache):
    old = _run_of(92, 1.0)
    store.write_series(_s(old, source="trends"), today=TODAY, mode="replace-series")
    assert store.write_series(_s(_run_of(89, 5.0), source="trends"), today=TODAY, mode="replace-series") == 0
    short = _run_of(89, 5.0) + [(TODAY, 5.0)]  # 90 rows, only 89 complete days
    assert store.write_series(_s(short, source="trends"), today=TODAY, mode="replace-series") == 0
    assert store.read_points("trends", "BTC") == old
    assert store.write_series(_s(_run_of(10), source="other"), today=TODAY, mode="replace-series") == 0
    assert not store.store_path("other", "BTC").exists()


def test_replace_series_is_atomic_on_write_error(attention_cache, monkeypatch):
    old = _run_of(92, 1.0)
    store.write_series(_s(old, source="trends"), today=TODAY, mode="replace-series")

    def broken(df, path):
        raise OSError("disk full")
    monkeypatch.setattr(cache, "_atomic_to_parquet", broken)
    with pytest.raises(OSError):
        store.write_series(_s(_run_of(95, 7.0), source="trends"), today=TODAY, mode="replace-series")
    assert store.read_points("trends", "BTC") == old


def test_default_mode_unchanged_first_wins(attention_cache):
    store.write_series(_s(_run_of(3, 1.0)), today=TODAY)
    assert store.write_series(_s(_run_of(95, 2.0)), today=TODAY) == 92
    assert store.write_series(_s(_run_of(96, 3.0)), today=TODAY, mode="first") == 1
    got = dict(store.read_points("wikipedia", "BTC"))
    assert [got[d] for d, _ in _run_of(3)] == [1.0] * 3 and got[TODAY - timedelta(days=96)] == 3.0
    assert len(got) == 96


def test_replace_series_sorted_and_returns_count(attention_cache):
    pts = list(reversed(_run_of(95, 4.0)))
    pts.append((pts[0][0], 99.0))  # a repeated day: the first row of the pull wins
    assert store.write_series(_s(pts, source="trends"), today=TODAY, mode="replace-series") == 95
    got = store.read_points("trends", "BTC")
    assert [d for d, _ in got] == sorted(d for d, _ in got) and got[-1][1] == 4.0
    assert len(pd.read_parquet(store.store_path("trends", "BTC"))) == 95


def test_replace_mode_rejects_unknown_mode(attention_cache):
    with pytest.raises(ValueError):
        store.write_series(_s(_run_of(95)), today=TODAY, mode="replace-window")
    assert not store.store_path("wikipedia", "BTC").exists()
