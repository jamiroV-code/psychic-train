from datetime import date, timedelta

import pandas as pd

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
