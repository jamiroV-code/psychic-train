"""chain-growth RFC-3: on-chain archive merge rules (isolated cache, no network)."""
from __future__ import annotations

import math

import pandas as pd

from api.data import cache

NOW1 = "2026-09-20T22:00:00Z"
NOW2 = "2026-09-25T22:00:00Z"
TODAY = "2026-09-25"


def _merge(points, *, today=TODAY, now=NOW2, window=14, chain="base"):
    return cache.merge_onchain_series("growthepie", chain, "active_addresses", points,
                                      today=today, now_utc=now, window_days=window)


def test_round_trip_columns_and_dtypes(isolated_cache):
    res = _merge([("2026-09-01", 10.0), ("2026-09-02", 12.5)], now=NOW1)
    assert (res.inserted, res.revised, res.wrote_file, res.rows) == (2, 0, True, 2)
    df = cache.read_onchain_series("growthepie", "base", "active_addresses")
    assert list(df.columns) == cache.ONCHAIN_COLUMNS
    assert df["date"].tolist() == ["2026-09-01", "2026-09-02"]
    assert df["value"].tolist() == [10.0, 12.5]
    assert df["first_seen_utc"].tolist() == [NOW1, NOW1]
    assert df["as_of_utc"].tolist() == [NOW1, NOW1]
    assert df["revised"].tolist() == [False, False]
    assert df["previous_value"].isna().all()
    assert str(df["value"].dtype) == "float64" and str(df["revised"].dtype) == "bool"


def test_missing_file_reads_empty_frame(isolated_cache):
    df = cache.read_onchain_series("growthepie", "nope", "transactions")
    assert df.empty and list(df.columns) == cache.ONCHAIN_COLUMNS


def test_path_uses_our_chain_id(isolated_cache):
    _merge([("2026-09-01", 1.0)], chain="polygon")
    assert (isolated_cache / "onchain" / "growthepie" / "polygon" / "active_addresses.parquet").exists()
    assert not (isolated_cache / "onchain" / "growthepie" / "polygon_pos").exists()


def test_in_window_revision_replaces_and_keeps_trail(isolated_cache):
    _merge([("2026-09-20", 100.0)], now=NOW1)
    res = _merge([("2026-09-20", 150.0)])
    assert (res.revised, res.inserted, res.wrote_file) == (1, 0, True)
    row = cache.read_onchain_series("growthepie", "base", "active_addresses").iloc[0]
    assert row["value"] == 150.0 and row["previous_value"] == 100.0 and bool(row["revised"])
    assert row["as_of_utc"] == NOW2 and row["first_seen_utc"] == NOW1


def test_window_boundary_is_inclusive(isolated_cache):
    _merge([("2026-09-11", 1.0), ("2026-09-10", 1.0)], now=NOW1)
    res = _merge([("2026-09-11", 2.0), ("2026-09-10", 2.0)])  # 14 days before 09-25 = 09-11
    assert res.revised == 1 and res.out_of_window_drift == 1


def test_out_of_window_change_kept_and_counted(isolated_cache):
    _merge([("2026-08-01", 100.0)], now=NOW1)
    path = cache.onchain_series_path("growthepie", "base", "active_addresses")
    before = path.read_bytes()
    res = _merge([("2026-08-01", 999.0)])
    assert res.out_of_window_drift == 1 and res.revised == 0 and res.wrote_file is False
    assert path.read_bytes() == before
    assert cache.read_onchain_series("growthepie", "base", "active_addresses")["value"].tolist() == [100.0]


def test_missing_dates_never_deleted_and_duplicates_dedupe(isolated_cache):
    _merge([("2026-09-01", 1.0), ("2026-09-02", 2.0)], now=NOW1)
    res = _merge([("2026-09-03", 3.0), ("2026-09-03", 4.0)])
    assert res.inserted == 1
    df = cache.read_onchain_series("growthepie", "base", "active_addresses")
    assert df["date"].tolist() == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert df["value"].tolist() == [1.0, 2.0, 4.0]


def test_no_change_merge_does_not_rewrite(isolated_cache):
    pts = [("2026-09-20", 5.0), ("2026-09-21", 6.0)]
    _merge(pts, now=NOW1)
    path = cache.onchain_series_path("growthepie", "base", "active_addresses")
    before_bytes, before_mtime = path.read_bytes(), path.stat().st_mtime_ns
    res = _merge(pts)
    assert (res.unchanged, res.inserted, res.revised, res.wrote_file) == (2, 0, 0, False)
    assert path.read_bytes() == before_bytes and path.stat().st_mtime_ns == before_mtime


def test_empty_input_writes_no_file(isolated_cache):
    res = _merge([])
    assert res.wrote_file is False
    assert not cache.onchain_series_path("growthepie", "base", "active_addresses").exists()


def test_future_dates_dropped_utc(isolated_cache):
    res = _merge([("2026-09-25", 1.0), ("2026-09-26", 2.0)], today="2026-09-25", now="2026-09-25T23:59:59Z")
    assert res.inserted == 1 and res.dropped_future == 1
    df = cache.read_onchain_series("growthepie", "base", "active_addresses")
    assert df["date"].tolist() == ["2026-09-25"]
    assert all(len(d) == 10 and pd.Timestamp(d).strftime("%Y-%m-%d") == d for d in df["date"])


def test_tiny_float_noise_is_not_a_revision(isolated_cache):
    _merge([("2026-09-20", 1e6)], now=NOW1)
    res = _merge([("2026-09-20", 1e6 + 1e-7)])
    assert res.unchanged == 1 and res.wrote_file is False


def test_revision_then_second_revision_tracks_latest_previous(isolated_cache):
    _merge([("2026-09-20", 1.0)], now=NOW1)
    _merge([("2026-09-20", 2.0)], now="2026-09-21T22:00:00Z", today="2026-09-21")
    _merge([("2026-09-20", 3.0)])
    row = cache.read_onchain_series("growthepie", "base", "active_addresses").iloc[0]
    assert row["value"] == 3.0 and row["previous_value"] == 2.0 and not math.isnan(row["previous_value"])
