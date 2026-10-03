"""Atomic parquet writes in `api/data/cache.py` (pipeline-completeness P1, AC12).

Every parquet writer in `cache.py` must go through one private helper that
writes a same-directory temp file, fsyncs it and only then renames it over the
target. These tests simulate an interrupted write (a fake parquet writer that
raises part-way) and a failing rename, and check that the original file stays
byte-identical and readable and that no temp file is left behind.

The fake writer TRUNCATES the target when handed a path (what the old
path-based code did) and writes junk into a file handle when handed one (what
the helper does). A handle-only fake would pass vacuously on the old code.

What this does NOT prove: behaviour under real power loss / SIGKILL (KG1), or
Windows `os.replace` against an open reader (KG2). Scope is `cache.py` only —
`etf_flows_adapter.merge_into_cache` is a known, separate non-atomic writer (KG5).

Isolation (T22): every test takes `isolated_cache`; the autouse fixture below
also redirects the watchlist store, so the real `api/data/cache` and
`api/data/watchlist.json` are never touched.
"""
from __future__ import annotations

import inspect
from contextlib import contextmanager
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

from api.data import cache
from api.data import watchlist as watchlist_store

_REAL_TO_PARQUET = pd.DataFrame.to_parquet
_REAL_REPLACE = os.replace


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json", raising=True)
    return isolated_cache


def _temps(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.name.endswith(".tmp")]


@contextmanager
def _interrupt():
    """Make every parquet write fail part-way through, inside the `with` only.

    Uses its own MonkeyPatch so leaving the block never undoes the
    `isolated_cache` redirect (a bare `monkeypatch.undo()` would).
    """

    def fake(self, target, *args, **kwargs):
        if isinstance(target, (str, os.PathLike)):
            with open(target, "wb") as fh:  # truncate the real target, like a crash mid-write
                fh.write(b"JUNKJUNKJU")
        else:
            target.write(b"JUNKJUNKJU")
        raise RuntimeError("simulated crash mid-write")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(pd.DataFrame, "to_parquet", fake)
        yield


@contextmanager
def _fail_replace(root: Path):
    def fake(src, dst, *args, **kwargs):
        if Path(dst).resolve().is_relative_to(root.resolve()):
            raise OSError("simulated rename failure")
        return _REAL_REPLACE(src, dst, *args, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cache.os, "replace", fake)
        yield


def _v1() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


def _v2() -> pd.DataFrame:
    return pd.DataFrame({"a": [9, 8], "b": ["p", "q"]})


# --- helper level -----------------------------------------------------------


def test_helper_round_trip(isolated_cache):
    path = isolated_cache / "sub" / "f.parquet"
    path.parent.mkdir(parents=True)
    cache._atomic_to_parquet(_v1(), path)
    pd.testing.assert_frame_equal(pd.read_parquet(path), _v1())
    assert _temps(isolated_cache) == []


def test_interrupted_write_preserves_original(isolated_cache):
    path = isolated_cache / "f.parquet"
    cache._atomic_to_parquet(_v1(), path)
    before = path.read_bytes()
    with _interrupt(), pytest.raises(RuntimeError):
        cache._atomic_to_parquet(_v2(), path)
    assert path.read_bytes() == before
    pd.testing.assert_frame_equal(pd.read_parquet(path), _v1())
    assert _temps(isolated_cache) == []


def test_replace_failure_preserves_original(isolated_cache):
    path = isolated_cache / "f.parquet"
    cache._atomic_to_parquet(_v1(), path)
    before = path.read_bytes()
    with _fail_replace(isolated_cache), pytest.raises(OSError):
        cache._atomic_to_parquet(_v2(), path)
    assert path.read_bytes() == before
    pd.testing.assert_frame_equal(pd.read_parquet(path), _v1())
    assert _temps(isolated_cache) == []


def test_first_write_interrupted_leaves_no_file(isolated_cache):
    path = isolated_cache / "new.parquet"
    with _interrupt(), pytest.raises(RuntimeError):
        cache._atomic_to_parquet(_v1(), path)
    assert not path.exists()
    assert _temps(isolated_cache) == []


def test_fsync_called_before_replace(isolated_cache, monkeypatch):
    """A3: the temp file is fsynced before it is renamed over the target."""
    events: list[str] = []
    real_fsync = os.fsync

    def spy_fsync(fd):
        events.append("fsync")
        return real_fsync(fd)

    def spy_replace(src, dst, *a, **k):
        events.append("replace")
        return _REAL_REPLACE(src, dst, *a, **k)

    monkeypatch.setattr(cache.os, "fsync", spy_fsync)
    monkeypatch.setattr(cache.os, "replace", spy_replace)
    cache._atomic_to_parquet(_v1(), isolated_cache / "f.parquet")
    assert "fsync" in events and "replace" in events
    assert events.index("fsync") < events.index("replace")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_mode_handling(isolated_cache):
    path = isolated_cache / "f.parquet"
    cache._atomic_to_parquet(_v1(), path)
    assert os.stat(path).st_mode & 0o7777 == 0o644
    os.chmod(path, 0o600)
    cache._atomic_to_parquet(_v2(), path)
    assert os.stat(path).st_mode & 0o7777 == 0o600


def test_no_bypass(isolated_cache):
    assert inspect.getsource(cache).count(".to_parquet(") == 1


def test_isolation_canary(isolated_cache, tmp_path):
    assert cache.CACHE_ROOT == tmp_path
    assert watchlist_store.DEFAULT_WATCHLIST_PATH == tmp_path / "watchlist.json"


# --- per-writer: interrupted second write keeps the prior file ---------------


def _ohlcv(n: int, start: str = "2026-01-01") -> pd.DataFrame:
    ts = pd.date_range(start, periods=n, freq="D", tz="UTC")
    return pd.DataFrame({
        "timestamp": ts, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
        "volume": 10.0, "source": "test",
    })


def _onchain(today: str, pts):
    return lambda: cache.merge_onchain_series("src", "chain", "metric", pts, today=today, now_utc=f"{today}T00:00:00Z")


# Each case: (first call, interrupted second call that reaches the write, target path, reader)
WRITERS = {
    "write_ohlcv": (
        lambda: cache.write_ohlcv("BTC", "1d", _ohlcv(3)),
        lambda: cache.write_ohlcv("BTC", "1d", _ohlcv(5)),
        lambda: cache.ohlcv_path("BTC", "1d"),
        lambda: cache.read_ohlcv("BTC", "1d"),
    ),
    "write_liqtide_backfill": (
        lambda: cache.write_liqtide_backfill("2026-09-01", pd.DataFrame({"series_key": ["k"], "date": ["2026-09-01"], "value": [1.0]})),
        lambda: cache.write_liqtide_backfill("2026-09-01", pd.DataFrame({"series_key": ["k", "j"], "date": ["2026-09-01"] * 2, "value": [2.0, 3.0]})),
        lambda: cache.liqtide_backfill_path("2026-09-01"),
        lambda: pd.read_parquet(cache.liqtide_backfill_path("2026-09-01")),
    ),
    "write_liquidity_series": (
        lambda: cache.write_liquidity_series("WALCL", pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "value": [1.0, 2.0]})),
        lambda: cache.write_liquidity_series("WALCL", pd.DataFrame({"date": ["2026-01-03"], "value": [3.0]})),
        lambda: cache.liquidity_series_path("WALCL"),
        lambda: cache.read_liquidity_series("WALCL"),
    ),
    "write_narrative_point": (
        lambda: cache.write_narrative_point("pytrends", "AI crypto", "2026-09-01", 10.0),
        lambda: cache.write_narrative_point("pytrends", "AI crypto", "2026-09-02", 20.0),
        lambda: cache.narrative_series_path("pytrends", "AI crypto"),
        lambda: cache.read_narrative_series("pytrends", "AI crypto"),
    ),
    "write_trending_snapshot": (
        lambda: cache.write_trending_snapshot("2026-09-01", ["BTC", "ETH"]),
        lambda: cache.write_trending_snapshot("2026-09-02", ["SOL"]),
        cache.trending_snapshot_path,
        cache.read_trending_snapshot,
    ),
    "write_exchange_point": (
        lambda: cache.write_exchange_point("ai", {"date": "2026-09-01", "volume_share": 0.1}),
        lambda: cache.write_exchange_point("ai", {"date": "2026-09-02", "volume_share": 0.2}),
        lambda: cache.exchange_series_path("ai"),
        lambda: cache.read_exchange_series("ai"),
    ),
    "merge_onchain_series": (
        _onchain("2026-09-02", [("2026-09-01", 1.0), ("2026-09-02", 2.0)]),
        _onchain("2026-09-03", [("2026-09-01", 1.0), ("2026-09-02", 5.0), ("2026-09-03", 3.0)]),
        lambda: cache.onchain_series_path("src", "chain", "metric"),
        lambda: cache.read_onchain_series("src", "chain", "metric"),
    ),
}


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_writer_interrupted_preserves_prior(name, isolated_cache):
    first, second, path_fn, reader = WRITERS[name]
    first()
    path = path_fn()
    before_bytes = path.read_bytes()
    before_read = reader()
    with _interrupt(), pytest.raises(RuntimeError):
        second()
    assert path.read_bytes() == before_bytes
    after_read = reader()
    if isinstance(before_read, pd.DataFrame):
        pd.testing.assert_frame_equal(after_read, before_read)
    else:
        assert after_read == before_read
    assert _temps(isolated_cache) == []


def test_write_liqtide_payload_interrupted_preserves_prior(isolated_cache):
    """N7: a new date targets a different file, so assert that file is absent."""
    cache.write_liqtide_payload("2026-09-01", pd.DataFrame({"date": ["2026-09-01"], "v": [1.0]}))
    p1 = cache.liqtide_payload_path("2026-09-01")
    before = p1.read_bytes()
    with _interrupt(), pytest.raises(RuntimeError):
        cache.write_liqtide_payload("2026-09-02", pd.DataFrame({"date": ["2026-09-02"], "v": [2.0]}))
    assert not cache.liqtide_payload_path("2026-09-02").exists()
    assert _temps(isolated_cache) == []
    assert p1.read_bytes() == before
    hist = cache.read_liqtide_history()
    assert list(hist["date"]) == ["2026-09-01"]


# --- round trip: normal behaviour unchanged ---------------------------------


def test_round_trip_ohlcv(isolated_cache):
    cache.write_ohlcv("BTC", "1d", _ohlcv(3))
    out = cache.read_ohlcv("BTC", "1d")
    assert len(out) == 3 and list(out.columns) == cache.OHLCV_COLUMNS
    assert out["timestamp"].iloc[0] == pd.Timestamp("2026-01-01", tz="UTC")


def test_round_trip_liqtide_payload_no_overwrite(isolated_cache):
    cache.write_liqtide_payload("2026-09-01", pd.DataFrame({"date": ["2026-09-01"], "v": [1.0]}))
    before = cache.liqtide_payload_path("2026-09-01").read_bytes()
    cache.write_liqtide_payload("2026-09-01", pd.DataFrame({"date": ["2026-09-01"], "v": [99.0]}))
    assert cache.liqtide_payload_path("2026-09-01").read_bytes() == before
    assert cache.read_liqtide_history()["v"].tolist() == [1.0]


def test_round_trip_liqtide_backfill(isolated_cache):
    df = pd.DataFrame({"series_key": ["k"], "date": ["2026-09-01"], "value": [1.0]})
    cache.write_liqtide_backfill("2026-09-01", df)
    pd.testing.assert_frame_equal(pd.read_parquet(cache.liqtide_backfill_path("2026-09-01")), df)


def test_round_trip_liquidity_series(isolated_cache):
    cache.write_liquidity_series("WALCL", pd.DataFrame({"date": ["2026-01-02", "2026-01-01", "2026-01-02"], "value": [2.0, 1.0, 3.0]}))
    out = cache.read_liquidity_series("WALCL")
    assert out["date"].tolist() == ["2026-01-01", "2026-01-02"]
    assert out["value"].tolist() == [1.0, 3.0]


def test_round_trip_trending_snapshot(isolated_cache):
    cache.write_trending_snapshot("2026-09-01", ["BTC", "ETH"])
    assert cache.read_trending_snapshot() == ("2026-09-01", ["BTC", "ETH"])


def test_round_trip_narrative_point(isolated_cache):
    cache.write_narrative_point("reddit", "rwa", "2026-09-01", 1.0)
    cache.write_narrative_point("reddit", "rwa", "2026-09-01", 2.0)
    out = cache.read_narrative_series("reddit", "rwa")
    assert out["date"].tolist() == ["2026-09-01"] and out["raw_value"].tolist() == [2.0]


def test_round_trip_exchange_point(isolated_cache):
    assert cache.write_exchange_point("ai", {"date": "2026-09-01", "volume_share": 0.1}) is True
    assert cache.write_exchange_point("ai", {"date": "2026-09-01", "volume_share": 0.9}) is False
    out = cache.read_exchange_series("ai")
    assert out["volume_share"].tolist() == [0.1]


def test_round_trip_onchain_unchanged_does_not_write(isolated_cache):
    pts = [("2026-09-01", 1.0), ("2026-09-02", 2.0)]
    r1 = cache.merge_onchain_series("s", "c", "m", pts, today="2026-09-02", now_utc="t1")
    assert r1.wrote_file is True and r1.inserted == 2
    path = cache.onchain_series_path("s", "c", "m")
    before_bytes, before_mtime = path.read_bytes(), path.stat().st_mtime_ns
    r2 = cache.merge_onchain_series("s", "c", "m", pts, today="2026-09-02", now_utc="t2")
    assert r2.wrote_file is False and r2.unchanged == 2
    assert path.read_bytes() == before_bytes and path.stat().st_mtime_ns == before_mtime
    assert cache.read_onchain_series("s", "c", "m")["value"].tolist() == [1.0, 2.0]


# --- AC(e): read-modify-write writers keep prior rows ------------------------


def test_narrative_rmw_interrupted_then_resumed(isolated_cache):
    cache.write_narrative_point("pytrends", "ai", "2026-09-01", 1.0)
    with _interrupt(), pytest.raises(RuntimeError):
        cache.write_narrative_point("pytrends", "ai", "2026-09-02", 2.0)
    assert cache.read_narrative_series("pytrends", "ai")["date"].tolist() == ["2026-09-01"]
    cache.write_narrative_point("pytrends", "ai", "2026-09-02", 2.0)
    out = cache.read_narrative_series("pytrends", "ai")
    assert out["date"].tolist() == ["2026-09-01", "2026-09-02"]
    assert out["raw_value"].tolist() == [1.0, 2.0]


def test_exchange_rmw_interrupted_then_resumed(isolated_cache):
    cache.write_exchange_point("ai", {"date": "2026-09-01", "volume_share": 0.1})
    with _interrupt(), pytest.raises(RuntimeError):
        cache.write_exchange_point("ai", {"date": "2026-09-02", "volume_share": 0.2})
    assert cache.read_exchange_series("ai")["date"].astype(str).tolist() == ["2026-09-01"]
    assert cache.write_exchange_point("ai", {"date": "2026-09-02", "volume_share": 0.2}) is True
    out = cache.read_exchange_series("ai")
    assert out["date"].astype(str).tolist() == ["2026-09-01", "2026-09-02"]
    assert out["volume_share"].tolist() == [0.1, 0.2]
