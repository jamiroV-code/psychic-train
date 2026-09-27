"""Pure cointegration statistics for one pair of coins (pair-screener RFC-002).

Input is two per-coin daily OHLCV frames (the shape `cache.read_ohlcv` returns:
a `timestamp` column plus `close`). This module performs no I/O: it never reads
the cache, never fetches from an exchange, and knows nothing about the persisted
results cache or provenance (that is RFC-003's `pairs_response.py`).

Every number here is a whole-history (in-sample) diagnostic (ADR-2c), not a live
trading signal. Decisions referenced below live in
process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from datetime import date
from typing import Literal, Sequence

import numpy as np
import pandas as pd
from numpy.exceptions import ComplexWarning
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import coint
from statsmodels.tsa.vector_ar.vecm import coint_johansen

# ADR-6: minimum overlapping daily bars before a pair is tested at all.
MIN_OVERLAP_DAYS = 365
# D1: coint()'s ADF lag selection. One named constant so RFC-003 provenance can record it.
EG_AUTOLAG = "aic"
# ADR-5: fixed Johansen specification for every pair.
JOHANSEN_DET_ORDER = 0
JOHANSEN_K_AR_DIFF = 1
# D2: largest tolerated imaginary part in Johansen eigenvalues before the result is refused.
JOHANSEN_MAX_IMAG = 1e-9
# ADR-2c: label attached to every result — whole-history, in-sample, not a live signal.
DIAGNOSTIC_SCOPE = "whole_history_in_sample"

PairStatus = Literal["ok", "insufficient_overlap", "coin_unavailable"]
Direction = Literal["a_on_b", "b_on_a"]


@dataclass(frozen=True)
class EGResult:
    """One Engle-Granger direction: `dependent` regressed on `independent`, log-space."""

    dependent: str
    independent: str
    hedge_ratio: float
    intercept: float
    t_stat: float
    p_value: float


@dataclass(frozen=True)
class JohansenResult:
    trace_stat_r0: float
    crit_95: float
    rank_at_least_1: bool


@dataclass(frozen=True)
class HalfLife:
    state: Literal["computed", "not_mean_reverting"]
    days: float | None  # None iff state == "not_mean_reverting" (ADR-3)
    ar1_beta: float


@dataclass(frozen=True)
class PairStatsResult:
    symbol_a: str
    symbol_b: str
    status: PairStatus
    reason: str | None
    overlap_days: int | None
    sample_start: date | None
    sample_end: date | None
    eg_a_on_b: EGResult | None = None
    eg_b_on_a: EGResult | None = None
    eg_min_p: float | None = None
    eg_rank_direction: Direction | None = None
    johansen: JohansenResult | None = None
    johansen_reason: str | None = None  # set iff the Johansen result was refused (D2)
    half_life: HalfLife | None = None
    zscore: float | None = None
    spread: pd.Series | None = None  # rank-driving (min-p) direction's spread (D3)
    diagnostic_scope: str = DIAGNOSTIC_SCOPE


class JohansenNumericallyUnstable(ValueError):
    """Johansen eigenvalues carry a non-negligible imaginary part (D2)."""


# ---------------------------------------------------------------- primitives

def _close_series(df: pd.DataFrame | None) -> pd.Series:
    """Daily close indexed by UTC calendar day; NaN / non-positive closes dropped."""
    if df is None or df.empty or "timestamp" not in df.columns or "close" not in df.columns:
        return pd.Series(dtype=float)
    idx = pd.DatetimeIndex(pd.to_datetime(df["timestamp"], utc=True)).normalize()
    vals = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    s = pd.Series(vals, index=idx)
    s = s[np.isfinite(vals) & (vals > 0)]
    return s[~s.index.duplicated(keep="last")].sort_index()


def ols_fit(y: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    """Closed-form OLS of y = alpha + beta*x. Returns (alpha, beta)."""
    xm, ym = x.mean(), y.mean()
    dx = x - xm
    beta = float((dx * (y - ym)).sum() / (dx * dx).sum())
    return float(ym - beta * xm), beta


def ar1_beta(spread: np.ndarray) -> float:
    """β from OLS of Δspread on lagged spread (with intercept) — ADR-3."""
    return ols_fit(np.diff(spread), spread[:-1])[1]


def half_life(spread: np.ndarray) -> HalfLife:
    """ADR-3: HL = −ln(2)/β; β ≥ 0 → not_mean_reverting with no number."""
    beta = ar1_beta(spread)
    if beta >= 0:
        return HalfLife(state="not_mean_reverting", days=None, ar1_beta=beta)
    return HalfLife(state="computed", days=-math.log(2) / beta, ar1_beta=beta)


def zscore_latest(spread: np.ndarray) -> float:
    """ADR-4: latest spread vs full-sample mean / sample std (ddof=1)."""
    return float((spread[-1] - spread.mean()) / spread.std(ddof=1))


def engle_granger(y: np.ndarray, x: np.ndarray, dep: str, indep: str) -> EGResult:
    """One EG direction: static full-sample OLS hedge ratio (ADR-2a) + coint() p-value."""
    alpha, beta = ols_fit(y, x)
    t_stat, p_value, _crit = coint(y, x, trend="c", method="aeg", autolag=EG_AUTOLAG)
    return EGResult(dep, indep, beta, alpha, float(t_stat), float(p_value))


def johansen(log_a: np.ndarray, log_b: np.ndarray) -> JohansenResult:
    """ADR-5 Johansen trace test (r=0) with the D2 scoped ComplexWarning handling.

    coint_johansen's eigenvalues come back complex128 with a zero imaginary part
    (RFC-002 Stage 0: 153/153 real pairs), and statsmodels' internal cast to real
    emits ComplexWarning. That warning is suppressed ONLY around this call (D2);
    the guard below refuses the result if the imaginary part is ever non-negligible.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ComplexWarning)
        j = coint_johansen(np.column_stack([log_a, log_b]), JOHANSEN_DET_ORDER, JOHANSEN_K_AR_DIFF)
    eig = np.asarray(j.eig)
    max_imag = float(np.abs(np.imag(eig)).max()) if eig.size else 0.0
    if max_imag > JOHANSEN_MAX_IMAG:
        raise JohansenNumericallyUnstable(
            f"Johansen numerically unstable: max|imag(eig)|={max_imag:.3e} > {JOHANSEN_MAX_IMAG:g}"
        )
    trace = float(np.real(j.lr1[0]))
    crit = float(np.real(j.cvt[0, 1]))  # cvt columns are 90/95/99%
    return JohansenResult(trace, crit, bool(trace > crit))


# ---------------------------------------------------------------- orchestrator

def compute_pair_stats(
    df_a: pd.DataFrame | None, df_b: pd.DataFrame | None, symbol_a: str, symbol_b: str
) -> PairStatsResult:
    """Full statistical result for one pair. Pure: frames in, result out."""
    ca, cb = _close_series(df_a), _close_series(df_b)
    missing = [s for s, c in ((symbol_a, ca), (symbol_b, cb)) if c.empty]
    if missing:
        return PairStatsResult(
            symbol_a, symbol_b, "coin_unavailable",
            f"{', '.join(missing)}: no usable cached daily closes",
            None, None, None,
        )

    joined = pd.concat([ca.rename("a"), cb.rename("b")], axis=1, join="inner").dropna()
    n = len(joined)
    start = joined.index[0].date() if n else None
    end = joined.index[-1].date() if n else None
    if n < MIN_OVERLAP_DAYS:
        return PairStatsResult(
            symbol_a, symbol_b, "insufficient_overlap",
            f"only {n} days of overlapping history available, need {MIN_OVERLAP_DAYS}",
            n, start, end,
        )

    log_a = np.log(joined["a"].to_numpy())  # ADR-1
    log_b = np.log(joined["b"].to_numpy())
    eg_ab = engle_granger(log_a, log_b, symbol_a, symbol_b)
    eg_ba = engle_granger(log_b, log_a, symbol_b, symbol_a)
    # ADR-2b / D3: the lower-p direction ranks the pair and its spread drives z-score/half-life/chart.
    if eg_ab.p_value <= eg_ba.p_value:
        direction: Direction = "a_on_b"
        spread = log_a - (eg_ab.intercept + eg_ab.hedge_ratio * log_b)
        min_p = eg_ab.p_value
    else:
        direction = "b_on_a"
        spread = log_b - (eg_ba.intercept + eg_ba.hedge_ratio * log_a)
        min_p = eg_ba.p_value

    try:
        jo, jo_reason = johansen(log_a, log_b), None
    except JohansenNumericallyUnstable as exc:
        jo, jo_reason = None, str(exc)

    result = PairStatsResult(
        symbol_a, symbol_b, "ok", None, n, start, end,
        eg_a_on_b=eg_ab, eg_b_on_a=eg_ba, eg_min_p=min_p, eg_rank_direction=direction,
        johansen=jo, johansen_reason=jo_reason,
        half_life=half_life(spread), zscore=zscore_latest(spread),
        spread=pd.Series(spread, index=joined.index, name="spread"),
    )
    _assert_finite(result)
    return result


def _assert_finite(r: PairStatsResult) -> None:
    """AC-8: an ok result never carries NaN/inf. A violation is an internal error, never a stand-in."""
    assert r.eg_a_on_b and r.eg_b_on_a and r.half_life and r.spread is not None
    vals: list[float | None] = [r.eg_min_p, r.zscore, r.half_life.ar1_beta]
    for eg in (r.eg_a_on_b, r.eg_b_on_a):
        vals += [eg.hedge_ratio, eg.intercept, eg.t_stat, eg.p_value]
    if r.johansen is not None:
        vals += [r.johansen.trace_stat_r0, r.johansen.crit_95]
    if r.half_life.days is not None:
        vals.append(r.half_life.days)
    bad = [v for v in vals if v is None or not math.isfinite(v)]
    if bad or not np.isfinite(r.spread.to_numpy()).all():
        raise ValueError(f"{r.symbol_a}-{r.symbol_b}: non-finite statistic produced {bad}")


def bh_adjust(results: Sequence[PairStatsResult]) -> list[float | None]:
    """Benjamini-Hochberg adjusted EG min-p, aligned index-for-index with `results`.

    Only `status == "ok"` pairs enter the denominator (AC-5); every other pair maps to None.
    `method` is always passed explicitly (statsmodels' default is not fdr_bh).
    """
    idx = [i for i, r in enumerate(results) if r.status == "ok" and r.eg_min_p is not None]
    out: list[float | None] = [None] * len(results)
    if not idx:
        return out
    _reject, p_adj, _sidak, _bonf = multipletests(
        [results[i].eg_min_p for i in idx], method="fdr_bh"
    )
    for i, p in zip(idx, p_adj):
        out[i] = float(p)
    return out
