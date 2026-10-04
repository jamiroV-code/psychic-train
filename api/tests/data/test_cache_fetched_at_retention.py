"""T32 / S1 — `fetched_at` sidecar and sub-daily retention (B1, B2)."""
from __future__ import annotations

import json
import os

import pandas as pd
import pytest

from api.data import cache, ccxt_adapter
from api.tests.data.test_ccxt_tail_fetch import (
    TailExchange,
    _bar_open,
    _frame,
    _seed_legacy,
    clock,  # noqa: F401  (fixture)
)

STAMP = pd.Timestamp("2026-10-03T14:15:00Z")


def _meta_path(symbol: str, timeframe: str):
    return cache.ohlcv_path(symbol, timeframe).parent / f"{timeframe}.meta.json"


def _temps(root):
    return [p for p in root.rglob("*") if p.is_file() and p.name.endswith(".tmp")]


def test_sidecar_round_trip_and_written_after_parquet(isolated_cache, monkeypatch):
    order: list[str] = []
    real_replace = cache.os.replace

    def spy(src, dst, *a, **k):
        order.append(os.path.basename(str(dst)))
        return real_replace(src, dst, *a, **k)

    monkeypatch.setattr(cache.os, "replace", spy)
    cache.write_ohlcv("BTC", "1h", _frame(STAMP.floor("1h"), 10, "1h"), fetched_at=STAMP)

    assert order == ["1h.parquet", "1h.meta.json"]
    meta = json.loads(_meta_path("BTC", "1h").read_text())
    assert meta == {"fetched_at": "2026-10-03T14:15:00Z", "schema": 1}
    assert cache.read_fetched_at("BTC", "1h") == STAMP
    assert _temps(isolated_cache) == []


def test_legacy_parquet_without_sidecar_uses_mtime(isolated_cache):
    old = pd.Timestamp("2026-09-01T08:00:00Z")
    _seed_legacy("BTC", "4h", _frame(old.floor("4h"), 10, "4h"), mtime=old)

    assert not _meta_path("BTC", "4h").exists()
    assert cache.read_fetched_at("BTC", "4h") == old
    assert cache.read_fetched_at("ETH", "4h") is None  # no cache at all


def test_sidecar_never_newer_than_parquet_after_crash(isolated_cache, monkeypatch):
    first = pd.Timestamp("2026-10-03T10:00:00Z")
    second = pd.Timestamp("2026-10-03T11:00:00Z")
    cache.write_ohlcv("BTC", "1h", _frame(first.floor("1h"), 10, "1h"), fetched_at=first)

    # 1) crash in the parquet write: neither file moves
    def boom(*a, **k):
        raise RuntimeError("simulated crash mid-write")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(pd.DataFrame, "to_parquet", boom)
        with pytest.raises(RuntimeError):
            cache.write_ohlcv("BTC", "1h", _frame(second.floor("1h"), 12, "1h"), fetched_at=second)
    assert cache.read_fetched_at("BTC", "1h") == first
    assert len(cache.read_ohlcv("BTC", "1h")) == 10

    # 2) crash between parquet and sidecar: the parquet is new, the sidecar
    # keeps the OLDER stamp (an extra refetch, never a missed one)
    real_replace = cache.os.replace

    def fail_meta(src, dst, *a, **k):
        if str(dst).endswith(".meta.json"):
            raise OSError("simulated rename failure")
        return real_replace(src, dst, *a, **k)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cache.os, "replace", fail_meta)
        with pytest.raises(OSError):
            cache.write_ohlcv("BTC", "1h", _frame(second.floor("1h"), 12, "1h"), fetched_at=second)
    assert len(cache.read_ohlcv("BTC", "1h")) == 12
    assert cache.read_fetched_at("BTC", "1h") == first
    assert _temps(isolated_cache) == []


def test_trim_on_write_15m_1h_4h_keeps_newest_200(clock):  # noqa: F811
    for tf in ("15m", "1h", "4h"):
        step = pd.Timedelta(seconds={"15m": 900, "1h": 3600, "4h": 14400}[tf])
        # a legacy 500-bar file, contiguous with the exchange's latest bars
        end = _bar_open(tf, clock()) - 2 * step
        _seed_legacy("BTC", tf, _frame(end, 500, tf), mtime=end)

        result = ccxt_adapter.fetch_ohlcv("BTC", tf, exchange=TailExchange(clock))

        stored = cache.read_ohlcv("BTC", tf)
        assert len(stored) == 200, tf
        assert stored["timestamp"].max() == _bar_open(tf, clock())
        assert stored["timestamp"].min() == _bar_open(tf, clock()) - 199 * step
        assert len(result.df) == 200


def test_one_day_bars_are_never_trimmed(clock):  # noqa: F811
    end = _bar_open("1d", clock()) - pd.Timedelta(days=2)
    _seed_legacy("BTC", "1d", _frame(end, 600, "1d"), mtime=end)

    ccxt_adapter.fetch_ohlcv("BTC", "1d", exchange=TailExchange(clock))

    stored = cache.read_ohlcv("BTC", "1d")
    assert len(stored) == 602
    assert stored["timestamp"].min() == end - pd.Timedelta(days=599)


def test_write_defaults_fetched_at_to_now(isolated_cache):
    before = pd.Timestamp.now(tz="UTC").floor("s")
    cache.write_ohlcv("BTC", "1d", _frame(before.floor("D"), 5, "1d"))
    after = pd.Timestamp.now(tz="UTC").ceil("s")

    stamp = cache.read_fetched_at("BTC", "1d")
    assert stamp is not None and before <= stamp <= after
    assert _meta_path("BTC", "1d").exists()
