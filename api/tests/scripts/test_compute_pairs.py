"""compute_pairs.py + pairs_response compute path (cointegration-screener RFC-003).

All runs use `isolated_cache`; the universe file is a tmp copy. No network.
"""
from __future__ import annotations

import json
from itertools import combinations

import pandas as pd
import pytest

from api.analytics.cointegration import pairs_response, stats
from api.data import cache, ccxt_adapter
from api.tests.pairs_fixtures import seed_small_universe, write_universe


def _hand_bh(ps: list[float]) -> list[float]:
    """Benjamini-Hochberg step-up, written out independently of statsmodels."""
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    adj = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, ps[i] * m / rank)
        adj[i] = running
    return adj


@pytest.fixture
def seeded(isolated_cache, tmp_path, monkeypatch):
    return seed_small_universe(tmp_path, monkeypatch)


def test_writes_every_pair_and_provenance(seeded, tmp_path):
    s = pairs_response.compute_and_persist()
    table = pd.read_parquet(cache.pairs_results_path())
    assert len(table) == len(list(combinations(seeded, 2))) == s.pair_count == 10  # AC-1
    assert set(zip(table.coin_a, table.coin_b)) == set(combinations(seeded, 2))
    assert s.status_counts == {"ok": 3, "insufficient_overlap": 3, "coin_unavailable": 4}

    prov = json.loads(cache.pairs_provenance_path().read_text())
    assert prov["universe"] == seeded
    for c in ("AAA", "BBB", "CCC", "DDD"):
        n, last = cache.ohlcv_footer_stats(c, "1d")
        assert prov["per_coin_bar_count"][c] == n == cache.ohlcv_bar_count(c, "1d")
        assert prov["per_coin_last_bar_date"][c] == last.date().isoformat()
    assert prov["per_coin_bar_count"]["EEE"] == 0 and prov["per_coin_last_bar_date"]["EEE"] is None
    assert prov["eg_autolag"] == stats.EG_AUTOLAG
    import statsmodels
    assert prov["statsmodels_version"] == statsmodels.__version__


def test_bh_only_over_ok_pairs_matches_hand_computed(seeded):
    pairs_response.compute_and_persist()
    t = pd.read_parquet(cache.pairs_results_path())
    ok = t[t.status == "ok"]
    assert ok.eg_p_bh.notna().all() and t[t.status != "ok"].eg_p_bh.isna().all()  # AC-5
    expected = _hand_bh(ok.eg_p_raw.tolist())
    assert ok.eg_p_bh.tolist() == pytest.approx(expected, rel=1e-12)


def test_golden_bh_set():
    """Fixed raw p-values -> hand-computed BH set (m=4)."""
    assert _hand_bh([0.01, 0.04, 0.03, 0.20]) == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.20])
    # the production helper agrees with the golden set
    rs = [stats.PairStatsResult("A", str(i), "ok", None, 400, None, None, eg_min_p=p)
          for i, p in enumerate([0.01, 0.04, 0.03, 0.20])]
    assert stats.bh_adjust(rs) == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.20])


def test_spread_files_only_for_ok_pairs(seeded):
    pairs_response.compute_and_persist()
    names = sorted(p.name for p in cache.pairs_spreads_dir().iterdir())
    assert names == ["AAA_BBB.parquet", "AAA_CCC.parquet", "BBB_CCC.parquet"]
    sp = pd.read_parquet(cache.pairs_spread_path("AAA", "BBB"))
    assert list(sp.columns) == ["date", "spread", "z_score"] and len(sp) == 500
    assert sp.z_score.mean() == pytest.approx(0, abs=1e-9)


def test_compute_path_never_touches_network(seeded, monkeypatch):
    """E5: compute reads cache.read_ohlcv only."""
    def boom(*a, **k):
        raise AssertionError("compute path called the network adapter")
    monkeypatch.setattr(ccxt_adapter, "fetch_ohlcv", boom)
    pairs_response.compute_and_persist()


def test_writes_land_under_isolated_root(seeded, tmp_path):
    """E6: every write resolves under the redirected CACHE_ROOT."""
    pairs_response.compute_and_persist()
    assert (tmp_path / "pairs" / "results.parquet").exists()
    assert (tmp_path / "pairs" / "provenance.json").exists()
    assert (tmp_path / "pairs" / "spreads" / "AAA_BBB.parquet").exists()
    assert not (tmp_path / "pairs" / "spreads.tmp").exists()
    assert not list((tmp_path / "pairs").glob("*.tmp"))


def test_rerun_after_universe_change_updates_provenance(seeded, tmp_path, monkeypatch):
    pairs_response.compute_and_persist()
    write_universe(tmp_path, monkeypatch, ["AAA", "BBB", "CCC"])
    pairs_response.compute_and_persist()
    prov = json.loads(cache.pairs_provenance_path().read_text())
    assert prov["universe"] == ["AAA", "BBB", "CCC"]
    assert len(pd.read_parquet(cache.pairs_results_path())) == 3
    assert len(list(cache.pairs_spreads_dir().iterdir())) == 3  # stale spread files removed


def test_johansen_refused_pair_stays_ok(seeded, monkeypatch):
    def refuse(*a, **k):
        raise stats.JohansenNumericallyUnstable("Johansen numerically unstable: max|imag(eig)|=1e-03 > 1e-09")
    monkeypatch.setattr(stats, "johansen", refuse)
    s = pairs_response.compute_and_persist()
    t = pd.read_parquet(cache.pairs_results_path())
    ok = t[t.status == "ok"]
    assert len(ok) == 3 and s.johansen_refused == 3
    assert ok.johansen_trace_stat.isna().all()
    assert ok.johansen_reason.str.startswith("Johansen numerically unstable").all()
    assert ok.eg_p_raw.notna().all() and ok.z_score.notna().all() and ok.half_life_state.notna().all()


def test_script_main_prints_summary(seeded, capsys):
    from api.scripts import compute_pairs
    assert compute_pairs.main() == 0
    out = capsys.readouterr().out
    assert "pairs computed: 10" in out and "coin_unavailable" in out and "BH-adjusted" in out
