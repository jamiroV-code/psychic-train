"""Per-source normalization (item 50).

Standing Rule (`data-sources/all-data-sources.md`): normalize within-source
only. pytrends' 0-100 relative-interest index, Reddit's raw mention count,
and CoinGecko's trending-membership count are not on comparable scales —
this function is only ever applied to one source's own series at a time;
`trigger.py` combines the already-per-source-normalized results afterward,
it never compares raw values across sources directly.
"""
from __future__ import annotations

import pandas as pd


def normalize_within_source(series: pd.Series) -> pd.Series:
    """Min-max normalize a single source's series to [0, 1].

    An all-constant series (min == max) normalizes to a flat 0.5 rather
    than dividing by zero — a flat series has no meaningful rate-of-change
    either way, and 0.5 keeps it numerically inert rather than NaN (which
    would silently drop real dates out of a downstream composite mean).
    """
    if series.empty:
        return series
    lo, hi = series.min(), series.max()
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(0.5, index=series.index)
    return (series - lo) / (hi - lo)


SUFFICIENCY_INSUFFICIENT = "insufficient"
SUFFICIENCY_PROVISIONAL = "provisional"
SUFFICIENCY_MATURE = "mature"
DEFAULT_MATURE_POINTS = 5  # history.MATURE_POINTS_THRESHOLD is the owner; kept equal


def normalize_with_sufficiency(
    series: pd.Series, min_points: int = 2, *, mature_points: int = DEFAULT_MATURE_POINTS,
) -> tuple[pd.Series, str]:
    """Narrative-v2 ADR-1: within-source min-max plus a data-sufficiency status.

    Returns (normalized_or_none_series, status), status in
    {"insufficient", "provisional", "mature"}. A series with fewer than
    `min_points` non-null values returns an all-None series (never 0.5) and
    "insufficient" — callers must never feed it into a composite or a rank.
    Otherwise non-null values are normalised with `normalize_within_source`
    (unchanged), nulls stay None, and the status is "provisional" below
    `mature_points` real observations, "mature" at or above it.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    out = pd.Series([None] * len(series), index=series.index, dtype=object)
    if len(valid) < min_points:
        return out, SUFFICIENCY_INSUFFICIENT
    norm = normalize_within_source(valid.astype(float))
    for idx, v in norm.items():
        out[idx] = float(v)
    status = SUFFICIENCY_MATURE if len(valid) >= mature_points else SUFFICIENCY_PROVISIONAL
    return out, status
