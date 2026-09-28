"""Pair-screener E2E fixture (RFC-005): `seed_e2e_cache.seed_pairs`.

Runs the real seeder section against an isolated cache + a temp
PAIRS_UNIVERSE_PATH: the production compute path must produce every designed
row state, the result must be `fresh`, and the guard must refuse the real
universe file. No network: `compute_and_persist` only reads the cache.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from api.analytics.cointegration import pairs_response
from api.data import cache, pairs_universe
from api.scripts import seed_e2e_cache as seed

TODAY = pd.Timestamp("2026-09-28")


@pytest.fixture
def universe_env(isolated_cache, tmp_path, monkeypatch):
    path = tmp_path / "fixture_universe.json"
    monkeypatch.setenv(pairs_universe.UNIVERSE_PATH_ENV, str(path))
    return path


def test_build_is_pure_and_deterministic():
    a = seed.build_pairs_fixture(TODAY)
    b = seed.build_pairs_fixture(TODAY)
    assert seed.PAIRS_MISSING not in a
    assert set(a) == set(seed.PAIRS_COINS) - {seed.PAIRS_MISSING}
    for sym in a:
        pd.testing.assert_frame_equal(a[sym], b[sym])
    assert len(a[seed.PAIRS_SHORT]) == seed.PAIRS_SHORT_BARS
    assert len(a["CINTA"]) == seed.PAIRS_BARS
    assert a["CINTA"]["timestamp"].iloc[-1] == TODAY.tz_localize("UTC")


def test_seed_produces_every_designed_state_and_is_fresh(universe_env):
    facts = seed.seed_pairs(TODAY)

    assert json.loads(universe_env.read_text(encoding="utf-8")) == {"coins": seed.PAIRS_COINS}
    assert facts["pair_count"] == 15
    assert facts["status_counts"] == {"ok": 6, "insufficient_overlap": 4, "coin_unavailable": 5}
    assert facts["raw_only_pairs"] == ["CINTA-WEAKB"]
    assert facts["ok_order"][0] == "CINTA-CINTB"
    assert facts["significant_count"] >= 1
    assert facts["significant_sample"]["overlap_days"] == seed.PAIRS_BARS

    table = pairs_response.read_table()
    assert table.computation_status == "fresh"
    assert table.pair_count == 15

    nmr = pairs_response.read_detail("CINTA", "DRIFT").pair
    assert nmr.half_life.state == "not_mean_reverting"
    assert nmr.half_life.days is None


def test_check_flags_a_missed_state(universe_env):
    seed.seed_pairs(TODAY)
    table = pd.read_parquet(cache.pairs_results_path())
    assert seed.check_pairs_results(table) == []
    broken = table.copy()
    mask = (broken["coin_a"] == "CINTA") & (broken["coin_b"] == "DRIFT")
    broken.loc[mask, "half_life_state"] = "computed"
    problems = seed.check_pairs_results(broken)
    assert any("not_mean_reverting" in p for p in problems)
    assert seed.check_pairs_results(table.iloc[:-1]) != []


def test_refuses_unset_universe_path(isolated_cache, monkeypatch):
    monkeypatch.delenv(pairs_universe.UNIVERSE_PATH_ENV, raising=False)
    with pytest.raises(SystemExit, match="REFUSING"):
        seed.seed_pairs(TODAY)


def test_refuses_the_real_universe_file(isolated_cache, monkeypatch):
    real = pairs_universe.real_universe_path()
    before = real.read_bytes()
    monkeypatch.setenv(pairs_universe.UNIVERSE_PATH_ENV, str(real))
    with pytest.raises(SystemExit, match="real universe file"):
        seed.seed_pairs(TODAY)
    assert real.read_bytes() == before
