"""60-period simple moving average line (RFC-001 + Amendment 2; moved from
`trend.py`, T36 / S4).

Constraint (SPEC): the line is a 60-period **simple** moving average — never
EMA/WMA. Amendment 2 (AC-17) generalizes "60-day" to "60-period of whichever
timeframe is active" — `compute_sma` takes a plain `length` against whatever
DataFrame (daily, 4h, 15m, ...) is passed in.
"""
from __future__ import annotations

import pandas as pd
import pandas_ta_classic  # noqa: F401 - registers the `.ta` DataFrame accessor.
# See analytics/indicators/rsi.py's comment on this same line - the installed
# distribution `pandas-ta-classic` imports as `pandas_ta_classic`, not
# `pandas_ta` (fixed 18-09-26 after a real `uv sync` run surfaced it).

SMA_LENGTH = 60


def compute_sma(df: pd.DataFrame, length: int = SMA_LENGTH, close_col: str = "close") -> pd.Series | None:
    """Simple moving average over `df[close_col]`, `length` bars of whichever
    timeframe `df` itself represents (AC-17 — re-scales with the active
    timeframe, never a fixed 60-calendar-day window).

    Returns `None` explicitly when there are fewer than `length` rows —
    see `rsi.py::compute_rsi`'s comment on this same pattern for why this is
    checked here rather than trusted to `pandas-ta-classic`'s own
    insufficient-data return shape.
    """
    if df is None or len(df) < length:
        return None
    return df.ta.sma(length=length, close=close_col)
