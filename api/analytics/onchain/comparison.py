"""Cross-chain normalised comparison (chain-growth RFC-4, decision D5).

AC-13 by construction: `ComparisonSeries` has no raw-value field. Only the
rebased index and the %-above-rolling-low alternative leave this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from api.analytics.onchain.growth import EMA_SPAN, WINDOW_DAYS, ema

NORMALIZATION_METHOD = "index-100-at-start-ema28"
ALTERNATIVE_METHOD = "pct-above-180d-low-ema28"
DEFAULT_RANGE_DAYS = 365  # default visible range when no `start` is given
LOG_SCALE_DEFAULT = True


@dataclass(frozen=True)
class ComparisonSeries:
    chain_id: str
    rebase_date: date | None
    rebased_late: bool
    index_values: list[float | None]  # aligned to grid_dates
    pct_above_low_values: list[float | None]  # aligned to grid_dates


def _clean(v: float) -> float | None:
    return None if pd.isna(v) else float(v)


def rebase_index(s: pd.Series, start: date) -> tuple[pd.Series, date | None, bool]:
    """EMA28 of a daily post-launch series, indexed to 100 at `start`.

    If the series has no observation on/before `start`, it is rebased at its
    first observation after `start` and flagged `rebased_late` (never
    back-filled). Points before the rebase date are NaN. Non-positive values
    are NaN (log-safe)."""
    obs = s.dropna()
    if obs.empty:
        return pd.Series(dtype=float), None, False
    e = ema(s, EMA_SPAN)
    ts = pd.Timestamp(start)
    late = obs.index[0] > ts
    base_day = obs.index[0] if late else ts
    if base_day > e.index[-1]:
        return pd.Series(dtype=float), None, False
    base = e.loc[base_day]
    if pd.isna(base) or base <= 0:
        return pd.Series(dtype=float), None, False
    idx = (e / base * 100.0)[e.index >= base_day]
    idx = idx.where(idx > 0)
    return idx, base_day.date(), bool(late)


def pct_above_rolling_low(s: pd.Series) -> pd.Series:
    """(EMA28 / trailing-180d low of EMA28 - 1) * 100; NaN until 180 days exist."""
    if s.dropna().empty:
        return pd.Series(dtype=float)
    e = ema(s, EMA_SPAN).dropna()
    low = e.rolling(WINDOW_DAYS, min_periods=WINDOW_DAYS).min()
    return ((e / low - 1.0) * 100.0).where(low > 0)


def build_comparison_series(chain_id: str, s: pd.Series, start: date, grid: list[str]) -> ComparisonSeries:
    idx, rebase_date, late = rebase_index(s, start)
    pct = pct_above_rolling_low(s)
    idx_map = {d.date().isoformat(): v for d, v in idx.items()}
    pct_map = {d.date().isoformat(): v for d, v in pct.items()}
    return ComparisonSeries(
        chain_id=chain_id,
        rebase_date=rebase_date,
        rebased_late=late,
        index_values=[_clean(idx_map.get(g, float("nan"))) for g in grid],
        pct_above_low_values=[_clean(pct_map.get(g, float("nan"))) for g in grid],
    )
