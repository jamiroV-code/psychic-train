"""compute_pairs.py + pairs_response compute path (cointegration-screener RFC-003).

All runs use `isolated_cache`; the universe file is a tmp copy. No network.

SAFETY (T22): `_isolate` below is module-level `autouse=True`. It depends on
`isolated_cache` AND redirects `watchlist_store.DEFAULT_WATCHLIST_PATH`, so
isolation holds for every test in this file including the pure ones that name
no fixture.
"""
from __future__ import annotations

import json
import os
import threading
import time
from itertools import combinations

import pandas as pd
import pytest

from api.analytics.cointegration import pairs_response, stats
from api.data import cache, ccxt_adapter, watchlist as watchlist_store
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


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    return isolated_cache


def test_isolated_cache_redirects_cache_root(tmp_path):
    """Canary: the autouse isolation is really in effect inside a test."""
    assert cache.CACHE_ROOT == tmp_path
    assert watchlist_store.DEFAULT_WATCHLIST_PATH == tmp_path / "watchlist.json"


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
    assert not list((tmp_path / "pairs").glob("spreads.tmp*"))


def test_persisted_files_are_fsynced_with_unique_temps(seeded, monkeypatch):
    """KG3: results, provenance and every spread file are fsynced before they
    are renamed into place, through cache.py's same-directory unique temps; a
    file sitting at the old fixed temp names is never overwritten or renamed."""
    pairs_dir = cache.pairs_results_path().parent
    pairs_dir.mkdir(parents=True, exist_ok=True)
    foreign = [pairs_dir / "results.parquet.tmp", pairs_dir / "provenance.json.tmp"]
    for f in foreign:
        f.write_bytes(b"another writer")
    synced: list[int] = []
    real_fsync = os.fsync

    def spy(fd):
        synced.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(cache.os, "fsync", spy)
    pairs_response.compute_and_persist()
    assert len(synced) == 3 + 2  # three ok-pair spreads, results, provenance
    assert [f.read_bytes() for f in foreign] == [b"another writer"] * 2
    assert json.loads(cache.pairs_provenance_path().read_text())["universe"] == seeded


def test_rerun_after_universe_change_updates_provenance(seeded, tmp_path, monkeypatch):
    pairs_response.compute_and_persist()
    write_universe(tmp_path, monkeypatch, ["AAA", "BBB", "CCC"])
    pairs_response.compute_and_persist()
    prov = json.loads(cache.pairs_provenance_path().read_text())
    assert prov["universe"] == ["AAA", "BBB", "CCC"]
    assert len(pd.read_parquet(cache.pairs_results_path())) == 3
    assert len(list(cache.pairs_spreads_dir().iterdir())) == 3  # stale spread files removed


# ------------------------------------------- spreads staging (KG3 follow-up)

OK_SPREADS = ["AAA_BBB.parquet", "AAA_CCC.parquet", "BBB_CCC.parquet"]


def _is_spread_write(path) -> bool:
    return path.parent != cache.pairs_results_path().parent


def _assert_one_complete_spreads_dir(pairs_dir):
    spreads = cache.pairs_spreads_dir()
    assert sorted(p.name for p in spreads.iterdir()) == OK_SPREADS
    for name in OK_SPREADS:
        sp = pd.read_parquet(spreads / name)
        assert list(sp.columns) == ["date", "spread", "z_score"] and len(sp) == 500
    assert not list(pairs_dir.glob("spreads.tmp*"))  # no staging dir left behind


def test_overlapping_runs_do_not_clobber_each_others_staging(seeded, monkeypatch):
    """Run B starts staging while run A has already staged a spread file; then
    both finish staging and swap at the same moment. Neither run may lose or
    have overwritten the files it staged, both must finish, and exactly one
    complete spreads dir must remain, holding one run's files only, with no
    staging dir left behind. B's spreads are shifted so the runs' bytes differ."""
    a_staged, b_staged = threading.Event(), threading.Event()
    swap_together = threading.Barrier(2, timeout=10)
    real_write, real_bh = cache._atomic_to_parquet, stats.bh_adjust
    written: dict[str, dict] = {"A": {}, "B": {}}
    clobbered: list[str] = []

    def bh_adjust(results):
        if threading.current_thread().name == "B":
            assert a_staged.wait(10)  # B reaches its staging step only after A staged a file
        return real_bh(results)

    def write(df, path):
        if not _is_spread_write(path):
            return real_write(df, path)
        me = threading.current_thread().name
        if me == "B":
            df = df.assign(spread=df["spread"] + 1.0)
        real_write(df, path)
        mine = written[me]
        mine[path] = path.read_bytes()
        if len(mine) == 1:
            if me == "A":
                a_staged.set()
                assert b_staged.wait(10)  # A keeps staging only after B has started staging
            else:
                b_staged.set()
        if len(mine) == len(OK_SPREADS):
            clobbered.extend(f"{me}:{p.name}" for p, b in mine.items()
                             if not p.exists() or p.read_bytes() != b)
            swap_together.wait()

    monkeypatch.setattr(stats, "bh_adjust", bh_adjust)
    monkeypatch.setattr(cache, "_atomic_to_parquet", write)
    errors: list[BaseException] = []

    def run():
        try:
            pairs_response.compute_and_persist()
        except BaseException as e:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(e)

    threads = [threading.Thread(target=run, name=n) for n in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert not any(t.is_alive() for t in threads)
    assert errors == [] and clobbered == []
    _assert_one_complete_spreads_dir(cache.pairs_results_path().parent)
    final = {p.name: p.read_bytes() for p in cache.pairs_spreads_dir().iterdir()}
    assert final in [{p.name: b for p, b in written[r].items()} for r in ("A", "B")]  # one run's set, not a mix
    assert json.loads(cache.pairs_provenance_path().read_text())["universe"] == seeded


def test_failure_mid_staging_keeps_previous_spreads_and_cleans_staging(seeded, monkeypatch):
    pairs_response.compute_and_persist()
    spreads = cache.pairs_spreads_dir()
    before = {p.name: p.read_bytes() for p in spreads.iterdir()}
    real_write = cache._atomic_to_parquet
    calls = []

    def write(df, path):
        if _is_spread_write(path):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("disk full")
        return real_write(df, path)

    monkeypatch.setattr(cache, "_atomic_to_parquet", write)
    with pytest.raises(OSError, match="disk full"):
        pairs_response.compute_and_persist()
    assert {p.name: p.read_bytes() for p in spreads.iterdir()} == before
    assert not list(spreads.parent.glob("spreads.tmp*"))


def test_stale_staging_dirs_swept_but_live_one_kept(seeded):
    """A crashed run's staging dirs older than the safe age are removed at the
    start of a run; a recent one (a concurrent live run) is never touched."""
    pairs_dir = cache.pairs_results_path().parent
    pairs_dir.mkdir(parents=True, exist_ok=True)
    old = time.time() - 2 * 3600
    stale = [pairs_dir / "spreads.tmp", pairs_dir / "spreads.tmp.crashed"]
    for d in stale:
        d.mkdir()
        (d / "AAA_BBB.parquet").write_bytes(b"partial")
        os.utime(d / "AAA_BBB.parquet", (old, old))
        os.utime(d, (old, old))
    live = pairs_dir / "spreads.tmp.live"
    live.mkdir()
    (live / "AAA_BBB.parquet").write_bytes(b"another run")

    pairs_response.compute_and_persist()
    assert not any(d.exists() for d in stale)
    assert (live / "AAA_BBB.parquet").read_bytes() == b"another run"
    assert sorted(p.name for p in cache.pairs_spreads_dir().iterdir()) == OK_SPREADS


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


# ------------------------------------------------------- exit-code policy (AC-6)


class _Summary:
    """Minimal stand-in for `pairs_response.ComputeSummary` — `exit_code` only
    reads `status_counts`."""

    def __init__(self, status_counts, pair_count=None):
        self.status_counts = status_counts
        self.pair_count = pair_count if pair_count is not None else sum(status_counts.values())
        self.not_mean_reverting = 0
        self.johansen_refused = 0
        self.bh_significant_05 = 0
        self.elapsed_s = 0.0
        self.provenance = {}


def test_exit_code_zero_when_any_pair_is_ok():
    counts = {"ok": 3, "insufficient_overlap": 3, "coin_unavailable": 4}
    assert compute_pairs_module().exit_code(_Summary(counts)) == 0


def test_exit_code_two_when_every_pair_is_coin_unavailable():
    assert compute_pairs_module().exit_code(_Summary({"coin_unavailable": 153})) == 2


def test_exit_code_two_when_every_pair_is_insufficient_overlap():
    """C2: `insufficient_overlap`-only is a degraded run, not a success."""
    assert compute_pairs_module().exit_code(_Summary({"insufficient_overlap": 153})) == 2


def test_exit_code_two_when_pair_count_is_zero():
    assert compute_pairs_module().exit_code(_Summary({}, pair_count=0)) == 2


def compute_pairs_module():
    from api.scripts import compute_pairs
    return compute_pairs


def test_main_returns_exit_code_from_stubbed_compute(monkeypatch, capsys):
    compute_pairs = compute_pairs_module()
    monkeypatch.setattr(pairs_response, "compute_and_persist",
                        lambda: _Summary({"coin_unavailable": 153}))
    assert compute_pairs.main() == 2
    out = capsys.readouterr().out
    assert "pairs computed: 153" in out and "coin_unavailable" in out and "BH-adjusted" in out


def test_main_with_explicit_empty_argv_matches_bare_main(monkeypatch):
    """C5: `main()` and `main([])` behave identically under pytest."""
    compute_pairs = compute_pairs_module()
    monkeypatch.setattr(pairs_response, "compute_and_persist", lambda: _Summary({"ok": 1}))
    assert compute_pairs.main() == compute_pairs.main([]) == 0


def test_empty_cache_real_compute_returns_two(tmp_path, monkeypatch, capsys):
    """E2 (NEW): the real compute path on an empty cache with the repo's own
    read-only universe file yields all `coin_unavailable` and exit 2.

    The universe file is only READ; every write lands under the redirected
    CACHE_ROOT.
    """
    compute_pairs = compute_pairs_module()
    from api.data import pairs_universe

    coins = pairs_universe.load_universe(pairs_universe.real_universe_path())
    monkeypatch.setattr(pairs_universe, "default_universe_path",
                        pairs_universe.real_universe_path)

    assert compute_pairs.main() == 2
    table = pd.read_parquet(cache.pairs_results_path())
    expected = len(list(combinations(coins, 2)))
    assert len(table) == expected
    assert set(table.status) == {"coin_unavailable"}
    assert (tmp_path / "pairs" / "results.parquet").exists()


def test_recompute_if_needed_computes_missing_then_skips_fresh_then_follows_new_bars(seeded):
    first = pairs_response.recompute_if_needed()
    assert first is not None and first.pair_count == 10          # no results yet -> computed
    assert pairs_response.recompute_if_needed() is None           # fresh -> nothing to do

    prov_path = cache.pairs_provenance_path()
    prov = json.loads(prov_path.read_text())
    prov["per_coin_last_bar_date"]["AAA"] = "2000-01-01"          # cache now looks newer than results
    prov_path.write_text(json.dumps(prov))
    assert pairs_response.recompute_if_needed() is not None       # stale -> recomputed
    assert pairs_response.recompute_if_needed() is None
