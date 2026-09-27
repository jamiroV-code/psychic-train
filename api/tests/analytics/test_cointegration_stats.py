"""RFC-002 golden-value tests for the pure pair-cointegration stats engine.

Golden-value provenance (validate-contract E4, tests Standing Lesson #4):
- hedge ratio, AR(1) beta, half-life and z-score are checked against independent
  numpy oracles (np.polyfit / np.linalg.lstsq), written separately from stats.py.
- EG p-values and the Johansen trace statistic are asymptotic test statistics with
  no hand derivation; they are checked against a reviewed pinned baseline
  (statsmodels 0.15.0) plus threshold/ordering assertions that must hold whatever
  the pinned digits are. Fixtures are built to land far from the 5% threshold.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import fields
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from numpy.exceptions import ComplexWarning
from statsmodels.tsa.vector_ar.vecm import coint_johansen

from api.analytics.cointegration import stats

SEED = 20260925
N = 1000
PIN_REL = 1e-6  # pinned-baseline tolerance for statsmodels outputs


# ------------------------------------------------------------------ fixtures

def _frame(logp: np.ndarray, start: str = "2022-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(logp), freq="D", tz="UTC")
    return pd.DataFrame({"timestamp": idx, "close": np.exp(logp)})


def _ar(rng, phi: float, sig: float, u0: float = 0.0) -> np.ndarray:
    u = np.zeros(N)
    u[0] = u0
    eps = rng.normal(0, sig, N)
    for t in range(1, N):
        u[t] = phi * u[t - 1] + eps[t]
    return u


@pytest.fixture(scope="module")
def series():
    """(a) cointegrated and (b) random-walk share one RNG stream (Stage 0 construction)."""
    rng = np.random.default_rng(SEED)
    log_a = np.cumsum(rng.normal(0, 0.03, N)) + np.log(100)
    e = _ar(rng, 0.8, 0.02)
    log_b_coint = 0.5 + 2 * log_a + e
    log_b_rw = np.cumsum(rng.normal(0, 0.03, N)) + np.log(50)

    # (c) not mean-reverting under D3: two coins with different explosive components,
    # tiny random-walk noise, so the rank-driving direction's residual is explosive.
    rng_c = np.random.default_rng(SEED)
    c_a = np.cumsum(rng_c.normal(0, 0.001, N)) + np.log(100) + _ar(rng_c, 1.006, 0.002, 0.05)
    c_b = np.cumsum(rng_c.normal(0, 0.001, N)) + np.log(50) + _ar(rng_c, 1.003, 0.002, 0.05)
    return SimpleNamespace(log_a=log_a, log_b_coint=log_b_coint, log_b_rw=log_b_rw, c_a=c_a, c_b=c_b)


@pytest.fixture(scope="module")
def res_a(series):
    return stats.compute_pair_stats(_frame(series.log_a), _frame(series.log_b_coint), "AAA", "BBB")


@pytest.fixture(scope="module")
def res_b(series):
    return stats.compute_pair_stats(_frame(series.log_a), _frame(series.log_b_rw), "AAA", "BBB")


@pytest.fixture(scope="module")
def res_c(series):
    return stats.compute_pair_stats(_frame(series.c_a), _frame(series.c_b), "AAA", "BBB")


# ------------------------------------------------------------------ independent numpy oracles

def _oracle_ols(y, x):
    slope, intercept = np.polyfit(x, y, 1)
    return intercept, slope


def _oracle_ar1_beta(spread):
    X = np.column_stack([np.ones(len(spread) - 1), spread[:-1]])
    coef, *_ = np.linalg.lstsq(X, np.diff(spread), rcond=None)
    return coef[1]


def _oracle_spread(y, x):
    a, b = _oracle_ols(y, x)
    return y - (a + b * x)


# ------------------------------------------------------------------ (a) cointegrated

def test_a_cointegrated_eg_and_johansen(res_a):
    assert res_a.status == "ok" and res_a.reason is None
    assert res_a.overlap_days == N
    assert res_a.eg_a_on_b.p_value < 0.01 and res_a.eg_b_on_a.p_value < 0.01
    # pinned baseline (statsmodels 0.15.0, reviewed)
    assert res_a.eg_a_on_b.p_value == pytest.approx(1.9923425743804672e-19, rel=PIN_REL)
    assert res_a.eg_b_on_a.p_value == pytest.approx(1.8405912846706125e-19, rel=PIN_REL)
    assert res_a.eg_rank_direction == "b_on_a"
    assert res_a.eg_min_p == res_a.eg_b_on_a.p_value
    assert res_a.johansen.rank_at_least_1 is True
    assert res_a.johansen.trace_stat_r0 == pytest.approx(122.9192139745732, rel=PIN_REL)
    assert res_a.johansen.crit_95 == pytest.approx(15.4943)
    assert res_a.johansen.trace_stat_r0 > res_a.johansen.crit_95


def test_a_cointegrated_numpy_goldens(series, res_a):
    la, lb = series.log_a, series.log_b_coint
    a1, b1 = _oracle_ols(la, lb)
    a2, b2 = _oracle_ols(lb, la)
    assert res_a.eg_a_on_b.hedge_ratio == pytest.approx(b1, rel=1e-9)
    assert res_a.eg_a_on_b.intercept == pytest.approx(a1, rel=1e-9)
    assert res_a.eg_b_on_a.hedge_ratio == pytest.approx(b2, rel=1e-9)
    assert res_a.eg_b_on_a.hedge_ratio == pytest.approx(2.0, abs=0.05)  # construction: logB = 0.5 + 2 logA
    # D3: rank-driving (b_on_a) spread drives half-life + z-score
    spread = _oracle_spread(lb, la)
    np.testing.assert_allclose(res_a.spread.to_numpy(), spread, rtol=0, atol=1e-10)
    beta = _oracle_ar1_beta(spread)
    assert res_a.half_life.state == "computed"
    assert res_a.half_life.ar1_beta == pytest.approx(beta, rel=1e-9)
    assert res_a.half_life.days == pytest.approx(-math.log(2) / beta, rel=1e-9)
    assert 2.0 < res_a.half_life.days < 5.0  # AR(1) φ=0.8 → theory ln2/0.2 ≈ 3.47
    z = (spread[-1] - spread.mean()) / np.std(spread, ddof=1)
    assert res_a.zscore == pytest.approx(z, rel=1e-9)


# ------------------------------------------------------------------ (b) random walk

def test_b_random_walk_not_cointegrated(res_b):
    assert res_b.status == "ok"
    assert res_b.eg_a_on_b.p_value > 0.3 and res_b.eg_b_on_a.p_value > 0.3
    assert res_b.eg_a_on_b.p_value == pytest.approx(0.6831877465520058, rel=PIN_REL)
    assert res_b.eg_b_on_a.p_value == pytest.approx(0.8729548479114756, rel=PIN_REL)
    assert res_b.eg_rank_direction == "a_on_b"
    assert res_b.johansen.rank_at_least_1 is False
    assert res_b.johansen.trace_stat_r0 == pytest.approx(4.904708573175433, rel=PIN_REL)
    assert res_b.johansen.trace_stat_r0 < res_b.johansen.crit_95


def test_b_random_walk_numpy_goldens(series, res_b):
    spread = _oracle_spread(series.log_a, series.log_b_rw)  # a_on_b is rank-driving
    np.testing.assert_allclose(res_b.spread.to_numpy(), spread, rtol=0, atol=1e-10)
    assert res_b.zscore == pytest.approx((spread[-1] - spread.mean()) / np.std(spread, ddof=1), rel=1e-9)


# ------------------------------------------------------------------ (c) not mean-reverting

def test_c_not_mean_reverting(series, res_c):
    assert res_c.status == "ok"
    assert res_c.eg_rank_direction == "b_on_a"
    spread = _oracle_spread(series.c_b, series.c_a)
    beta = _oracle_ar1_beta(spread)
    assert beta >= 0
    assert res_c.half_life.state == "not_mean_reverting"
    assert res_c.half_life.days is None
    assert res_c.half_life.ar1_beta == pytest.approx(beta, rel=1e-9)
    assert res_c.eg_min_p > 0.5
    # Johansen intentionally NOT asserted (D4): explosive spreads give a spurious rank>=1.


# ------------------------------------------------------------------ (d) short overlap / unavailable

def test_d_short_overlap(series):
    la = series.log_a[:300]
    lb = series.log_b_coint[:300]
    r = stats.compute_pair_stats(_frame(la), _frame(lb), "AAA", "BBB")
    assert r.status == "insufficient_overlap"
    assert "300" in r.reason and "365" in r.reason
    assert r.overlap_days == 300
    _assert_no_stats(r)


def test_overlap_is_date_intersection(series):
    # A has 1000 days from 2022-01-01; B starts 700 days later → 300 overlapping days.
    fa = _frame(series.log_a)
    fb = _frame(series.log_b_coint[:600], start=str((pd.Timestamp("2022-01-01") + pd.Timedelta(days=700)).date()))
    r = stats.compute_pair_stats(fa, fb, "AAA", "BBB")
    assert r.status == "insufficient_overlap" and r.overlap_days == 300
    assert str(r.sample_start) == "2023-12-02" and str(r.sample_end) == "2024-09-26"


def test_exactly_min_overlap_is_ok(series):
    n = stats.MIN_OVERLAP_DAYS
    r = stats.compute_pair_stats(_frame(series.log_a[:n]), _frame(series.log_b_coint[:n]), "AAA", "BBB")
    assert r.status == "ok" and r.overlap_days == 365


def test_one_below_min_overlap_is_insufficient(series):
    n = stats.MIN_OVERLAP_DAYS - 1
    r = stats.compute_pair_stats(_frame(series.log_a[:n]), _frame(series.log_b_coint[:n]), "AAA", "BBB")
    assert r.status == "insufficient_overlap" and r.overlap_days == n == 364
    _assert_no_stats(r)


@pytest.mark.parametrize("empty_side", ["a", "b"])
def test_coin_unavailable(series, empty_side):
    empty = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    full = _frame(series.log_a)
    fa, fb = (empty, full) if empty_side == "a" else (full, empty)
    r = stats.compute_pair_stats(fa, fb, "AAA", "BBB")
    assert r.status == "coin_unavailable"
    assert ("AAA" if empty_side == "a" else "BBB") in r.reason
    assert r.overlap_days is None
    _assert_no_stats(r)


def _assert_no_stats(r):
    for name in ("eg_a_on_b", "eg_b_on_a", "eg_min_p", "eg_rank_direction", "johansen",
                 "half_life", "zscore", "spread"):
        assert getattr(r, name) is None, name


# ------------------------------------------------------------------ hand-exact AR(1) case

def test_half_life_exact_geometric_spread():
    hl = stats.half_life(np.array([1.0, 0.5, 0.25, 0.125, 0.0625]))
    assert hl.ar1_beta == pytest.approx(-0.5, abs=1e-12)
    assert hl.days == pytest.approx(math.log(2) / 0.5, abs=1e-12)


# ------------------------------------------------------------------ no NaN/inf, labelling

def test_no_nan_or_inf_in_any_ok_output(res_a, res_b, res_c):
    for r in (res_a, res_b, res_c):
        nums = [r.eg_min_p, r.zscore, r.half_life.ar1_beta, r.johansen.trace_stat_r0, r.johansen.crit_95]
        for eg in (r.eg_a_on_b, r.eg_b_on_a):
            nums += [eg.hedge_ratio, eg.intercept, eg.t_stat, eg.p_value]
        if r.half_life.days is not None:
            nums.append(r.half_life.days)
        assert all(isinstance(v, float) and math.isfinite(v) for v in nums)
        assert np.isfinite(r.spread.to_numpy()).all()
        assert r.diagnostic_scope == "whole_history_in_sample"


def test_named_constants():
    assert stats.MIN_OVERLAP_DAYS == 365
    assert stats.EG_AUTOLAG == "aic"
    assert (stats.JOHANSEN_DET_ORDER, stats.JOHANSEN_K_AR_DIFF) == (0, 1)


def test_engine_is_pure_no_io_imports():
    src = open(stats.__file__, encoding="utf-8").read()
    for forbidden in ("ccxt_adapter", "fetch_ohlcv", "api.data", "read_parquet", "to_parquet"):
        assert forbidden not in src, forbidden


# ------------------------------------------------------------------ ComplexWarning guard (D2)

def test_complex_warning_suppressed_and_values_unchanged(series):
    la, lb = series.log_a, series.log_b_coint
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        jr = stats.johansen(la, lb)
    assert not [w for w in caught if issubclass(w.category, ComplexWarning)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = coint_johansen(np.column_stack([la, lb]), 0, 1)
    assert jr.trace_stat_r0 == float(raw.lr1[0])
    assert jr.crit_95 == float(raw.cvt[0, 1])


def test_complex_warning_suppression_is_scoped():
    # The filter must not leak: ComplexWarning outside the Johansen call still surfaces.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        stats.half_life(np.array([1.0, 0.5, 0.25, 0.125, 0.0625]))
        warnings.warn("probe", ComplexWarning)
    assert any(issubclass(w.category, ComplexWarning) for w in caught)


def test_complex_eigenvalues_refuse_johansen(monkeypatch, series):
    fake = SimpleNamespace(
        eig=np.array([0.1 + 1e-6j, 0.01 - 1e-6j]),
        lr1=np.array([99.0, 1.0]),
        cvt=np.array([[13.4, 15.49, 19.9], [2.7, 3.8, 6.6]]),
    )
    monkeypatch.setattr(stats, "coint_johansen", lambda *a, **k: fake)
    r = stats.compute_pair_stats(_frame(series.log_a), _frame(series.log_b_coint), "AAA", "BBB")
    assert r.status == "ok"
    assert r.johansen is None
    assert "numerically unstable" in r.johansen_reason
    # EG / half-life / z-score still produced
    assert r.eg_min_p is not None and r.half_life is not None and r.zscore is not None


# ------------------------------------------------------------------ BH golden

def _ok(p):
    eg = stats.EGResult("X", "Y", 1.0, 0.0, -3.0, p)
    return stats.PairStatsResult("X", "Y", "ok", None, 400, None, None,
                                 eg_a_on_b=eg, eg_b_on_a=eg, eg_min_p=p, eg_rank_direction="a_on_b")


def test_bh_golden_excludes_non_ok():
    insufficient = stats.PairStatsResult("X", "Z", "insufficient_overlap", "only 10 days", 10, None, None)
    unavailable = stats.PairStatsResult("X", "W", "coin_unavailable", "W: none", None, None, None)
    results = [_ok(0.01), insufficient, _ok(0.04), _ok(0.03), unavailable, _ok(0.20)]
    # Hand BH, m=4: sorted .01,.03,.04,.20 → p*m/k = .04,.06,.0533..,.20 → step-up min → .04,.0533,.0533,.20
    expected = [0.04, None, 0.16 / 3, 0.16 / 3, None, 0.20]
    got = stats.bh_adjust(results)
    for g, e in zip(got, expected):
        if e is None:
            assert g is None
        else:
            assert g == pytest.approx(e, abs=1e-12)


def test_bh_empty_and_all_non_ok():
    assert stats.bh_adjust([]) == []
    only_bad = [stats.PairStatsResult("X", "Z", "insufficient_overlap", "r", 10, None, None)]
    assert stats.bh_adjust(only_bad) == [None]


def test_result_dataclass_fields_stable():
    names = [f.name for f in fields(stats.PairStatsResult)]
    for required in ("status", "reason", "overlap_days", "sample_start", "sample_end",
                     "eg_a_on_b", "eg_b_on_a", "eg_min_p", "eg_rank_direction", "johansen",
                     "half_life", "zscore", "spread", "diagnostic_scope"):
        assert required in names
