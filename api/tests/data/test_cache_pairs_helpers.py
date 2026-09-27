"""cache.py additive helpers for the pair screener (RFC-003, Stage 0 D-5 / E6 / E9)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from api.data import cache
from api.tests.pairs_fixtures import ohlcv_frame


def test_footer_stats_match_existing_helpers(isolated_cache):
    cache.write_ohlcv("AAA", "1d", ohlcv_frame(np.linspace(1, 2, 400)))
    cache.write_ohlcv("BBB", "1d", ohlcv_frame(np.linspace(1, 2, 37), end=pd.Timestamp("2025-01-03", tz="UTC")))
    for sym in ("AAA", "BBB"):
        n, last = cache.ohlcv_footer_stats(sym, "1d")
        assert n == cache.ohlcv_bar_count(sym, "1d")
        assert last == cache.ohlcv_last_refresh(sym, "1d")
        assert last.tzinfo is not None
    assert cache.ohlcv_footer_stats("AAA", "1d")[0] == 400
    assert cache.ohlcv_footer_stats("BBB", "1d")[1] == pd.Timestamp("2025-01-03", tz="UTC")


def test_footer_stats_missing_file_and_batch(isolated_cache):
    cache.write_ohlcv("AAA", "1d", ohlcv_frame(np.linspace(1, 2, 10)))
    assert cache.ohlcv_footer_stats("ZZZ", "1d") == (0, None)
    many = cache.ohlcv_footer_stats_many(["AAA", "ZZZ"], "1d")
    assert many["AAA"][0] == 10 and many["ZZZ"] == (0, None)


def test_footer_stats_resolve_through_cache_root(isolated_cache, tmp_path):
    """The helper follows a redirected CACHE_ROOT (isolation really isolates)."""
    cache.write_ohlcv("AAA", "1d", ohlcv_frame(np.linspace(1, 2, 5)))
    assert (tmp_path / "ohlcv" / "AAA" / "1d.parquet").exists()
    assert cache.ohlcv_footer_stats("AAA", "1d")[0] == 5


def test_pairs_paths_resolve_at_call_time(isolated_cache, tmp_path):
    assert cache.pairs_results_path() == tmp_path / "pairs" / "results.parquet"
    assert cache.pairs_provenance_path() == tmp_path / "pairs" / "provenance.json"
    assert cache.pairs_spread_path("btc", "eth") == tmp_path / "pairs" / "spreads" / "BTC_ETH.parquet"


def test_bootstrap_creates_pairs_dir(isolated_cache, tmp_path):
    assert (tmp_path / "pairs").is_dir()
