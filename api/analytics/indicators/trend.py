"""60-period simple moving average trend line (RFC-001 + Amendment 2).

Constraint (SPEC): the trend layer is a 60-day **simple** moving average —
never EMA/WMA. Amendment 2 (AC-17) generalizes "60-day" to "60-period of
whichever timeframe is active" — `compute_sma`'s signature already takes a
plain `length` against whatever DataFrame (daily, 4h, 15m, ...) is passed in,
so no fixed "daily" assumption survives past this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import pandas_ta_classic  # noqa: F401 - registers the `.ta` DataFrame accessor.
# See analytics/indicators/momentum.py's comment on this same line - the
# installed distribution `pandas-ta-classic` imports as `pandas_ta_classic`,
# not `pandas_ta` (fixed 18-09-26 after a real `uv sync` run surfaced it).

TrendDirectionLiteral = Literal["up", "down", "insufficient"]

SMA_LENGTH = 60


def compute_sma(df: pd.DataFrame, length: int = SMA_LENGTH, close_col: str = "close") -> pd.Series | None:
    """Simple moving average over `df[close_col]`, `length` bars of whichever
    timeframe `df` itself represents (AC-17 — re-scales with the active
    timeframe, never a fixed 60-calendar-day window).

    Returns `None` explicitly when there are fewer than `length` rows —
    see `momentum.py::compute_rsi`'s comment on this same pattern for why
    this is checked here rather than trusted to `pandas-ta-classic`'s own
    insufficient-data return shape.
    """
    if df is None or len(df) < length:
        return None
    return df.ta.sma(length=length, close=close_col)


@dataclass(frozen=True)
class TrendResult:
    direction: TrendDirectionLiteral
    sma_value: float | None


def compute_trend(df: pd.DataFrame, length: int = SMA_LENGTH, close_col: str = "close") -> TrendResult:
    """Trend direction: price above its own 60-period SMA reads `up`, below
    reads `down`; insufficient history (fewer than `length` bars) reads
    `insufficient` — never a silently-shortened-window number (AC-12).
    """
    sma_series = compute_sma(df, length=length, close_col=close_col)
    if sma_series is None or sma_series.empty or pd.isna(sma_series.iloc[-1]):
        return TrendResult("insufficient", None)

    sma_value = float(sma_series.iloc[-1])
    latest_close = df[close_col].iloc[-1]
    if pd.isna(latest_close):
        return TrendResult("insufficient", sma_value)

    direction: TrendDirectionLiteral = "up" if float(latest_close) > sma_value else "down"
    return TrendResult(direction, sma_value)
