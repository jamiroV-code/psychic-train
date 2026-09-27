"""Shared synthetic fixtures for the pair-screener RFC-003 tests (no network, no real cache).

Every helper writes through `api.data.cache`, so callers must use the
`isolated_cache` fixture (CACHE_ROOT redirected to tmp_path).
"""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from api.analytics.cointegration import pairs_response, stats
from api.data import cache, pairs_universe

END = pd.Timestamp("2026-09-25", tz="UTC")


def ohlcv_frame(closes: np.ndarray, end: pd.Timestamp = END) -> pd.DataFrame:
    ts = pd.date_range(end=end, periods=len(closes), freq="D", tz="UTC")
    return pd.DataFrame({
        "timestamp": ts, "open": closes, "high": closes * 1.01, "low": closes * 0.99,
        "close": closes, "volume": np.full(len(closes), 1000.0), "source": "fixture",
    })


def seed_small_universe(tmp_path: Path, monkeypatch, n: int = 500) -> list[str]:
    """AAA/BBB cointegrated, CCC independent walk, DDD too short, EEE never cached."""
    rng = np.random.default_rng(42)
    x = np.cumsum(rng.normal(0, 0.02, n)) + 3.0
    noise = np.zeros(n)
    for i in range(1, n):
        noise[i] = 0.5 * noise[i - 1] + rng.normal(0, 0.01)
    y = 0.8 * x + 0.5 + noise
    z = np.cumsum(rng.normal(0, 0.02, n)) + 2.0
    short = np.cumsum(rng.normal(0, 0.02, 200)) + 1.0
    cache.write_ohlcv("AAA", "1d", ohlcv_frame(np.exp(x)))
    cache.write_ohlcv("BBB", "1d", ohlcv_frame(np.exp(y)))
    cache.write_ohlcv("CCC", "1d", ohlcv_frame(np.exp(z)))
    cache.write_ohlcv("DDD", "1d", ohlcv_frame(np.exp(short)))
    coins = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    write_universe(tmp_path, monkeypatch, coins)
    return coins


def write_universe(tmp_path: Path, monkeypatch, coins: list[str]) -> Path:
    path = tmp_path / "pairs_universe.json"
    path.write_text(json.dumps({"coins": coins}), encoding="utf-8")
    monkeypatch.setattr(pairs_universe, "default_universe_path", lambda: path)
    return path


def seed_realistic_results(tmp_path: Path, monkeypatch, n_coins: int = 18, bars: int = 2229) -> list[str]:
    """Real-size persisted cache (153 pairs, ~2229-day spreads) without running the 46 s compute.

    Rows/spreads are written with the same `_row`/`_spread_frame` serializers
    the compute path uses; provenance matches the seeded OHLCV so the state is `fresh`.
    """
    rng = np.random.default_rng(7)
    coins = [f"C{i:02d}" for i in range(n_coins)]
    for c in coins:
        cache.write_ohlcv(c, "1d", ohlcv_frame(np.exp(np.cumsum(rng.normal(0, 0.02, bars)) + 3)))
    write_universe(tmp_path, monkeypatch, coins)
    idx = pd.date_range(end=END, periods=bars, freq="D", tz="UTC")
    results, p_raw = [], []
    for a, b in combinations(coins, 2):
        spread = pd.Series(np.cumsum(rng.normal(0, 0.01, bars)), index=idx)
        eg_ab = stats.EGResult(a, b, 0.9, 0.1, -3.0, float(rng.random()))
        eg_ba = stats.EGResult(b, a, 1.1, -0.1, -2.9, float(rng.random()))
        results.append(stats.PairStatsResult(
            a, b, "ok", None, bars, idx[0].date(), idx[-1].date(),
            eg_a_on_b=eg_ab, eg_b_on_a=eg_ba, eg_min_p=min(eg_ab.p_value, eg_ba.p_value),
            eg_rank_direction="a_on_b" if eg_ab.p_value <= eg_ba.p_value else "b_on_a",
            johansen=stats.JohansenResult(12.0, 15.49, False),
            half_life=stats.HalfLife("computed", 20.0, -0.03), zscore=0.5, spread=spread,
        ))
    p_bh = stats.bh_adjust(results)
    cache.pairs_spreads_dir().mkdir(parents=True, exist_ok=True)
    for r in results:
        pairs_response._spread_frame(r.spread).to_parquet(cache.pairs_spread_path(r.symbol_a, r.symbol_b), index=False)
    pd.DataFrame([pairs_response._row(r, p) for r, p in zip(results, p_bh)]).to_parquet(
        cache.pairs_results_path(), index=False
    )
    last, count = pairs_response._coin_snapshot(coins)
    import statsmodels
    cache.pairs_provenance_path().write_text(json.dumps({
        "computed_at": "2026-09-26T00:00:00Z", "universe": coins,
        "per_coin_last_bar_date": last, "per_coin_bar_count": count,
        "statsmodels_version": statsmodels.__version__, "eg_autolag": stats.EG_AUTOLAG,
    }), encoding="utf-8")
    return coins
