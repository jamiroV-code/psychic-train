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
