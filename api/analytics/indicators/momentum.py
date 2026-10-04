"""Dual-timeframe RSI momentum (RFC-001). The per-timeframe gain chips moved
to `gain.py` (T34 / S2).

`pandas-ta-classic` Stage-0 confirmation (PLAN.md RFC-001 Stage 0): the
DataFrame accessor pattern is `df.ta.rsi(length=N)` — `length` is the
confirmed parameter name. Every call site below passes `length=` explicitly
(never relies on the library's own default), per Stage 0's own defensive
note.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import pandas_ta_classic  # noqa: F401 - registers the `.ta` DataFrame accessor.
# The installed PyPI distribution is `pandas-ta-classic`, whose importable
# module is `pandas_ta_classic` (confirmed against PyPI's own usage example,
# 18-09-26) - NOT `pandas_ta`. The original `import pandas_ta` only worked in
# the EXECUTE sandbox because its local shim happened to be named to match
# the (incorrect) import statement rather than the real package - a real
# `uv sync` run on the user's machine caught this for real (ModuleNotFoundError).

MomentumStateLiteral = Literal["PASS", "FAIL", "insufficient"]

# A reading sitting exactly on the threshold never silently counts as a pass
# (AC-2) - the comparison below is a strict ">", not ">=".
MOMENTUM_MIDLINE = 50.0
RSI_LENGTH = 14

def compute_rsi(df: pd.DataFrame, length: int = RSI_LENGTH, close_col: str = "close") -> pd.Series | None:
    """RSI over `df[close_col]`, via the pandas-ta-classic `.ta` accessor.

    Returns `None` explicitly when there are fewer than `length` rows,
    checked here rather than trusting whatever `pandas-ta-classic` itself
    returns in that case. Found (18-09-26, first real-dependency run) that
    this isn't reliably a clean NaN-filled Series — there's an open upstream
    question about this exact behavior (pandas-ta-classic issue #145,
    "Should verify_series return None, or raise?"). Our own guard, matching
    the library's own stated threshold from its "requires at least N" log
    message, sidesteps the ambiguity rather than depending on it.
    """
    if df is None or len(df) < length:
        return None
    return df.ta.rsi(length=length, close=close_col)


def _latest_valid(series: pd.Series) -> float | None:
    if series is None or series.empty:
        return None
    last = series.iloc[-1]
    if pd.isna(last):
        return None
    return float(last)


@dataclass(frozen=True)
class MomentumResult:
    state: MomentumStateLiteral
    daily_value: float | None
    weekly_value: float | None


def classify_momentum(daily_val: float | None, weekly_val: float | None) -> MomentumStateLiteral:
    """Pure AND-gate decision (AC-2), factored out for exhaustive boundary
    testing independent of RSI computation itself. A reading sitting exactly
    on the midline is NOT a pass (strict ">"); either reading missing means
    `insufficient`, never a silent pass/fail guess (AC-12).
    """
    if daily_val is None or weekly_val is None:
        return "insufficient"
    return "PASS" if (daily_val > MOMENTUM_MIDLINE and weekly_val > MOMENTUM_MIDLINE) else "FAIL"


def compute_dual_timeframe_momentum(
    daily_df: pd.DataFrame, weekly_df: pd.DataFrame, length: int = RSI_LENGTH
) -> MomentumResult:
    """Dual-timeframe AND-gate (AC-2): PASS only if daily AND weekly RSI both
    clear the midline. `weekly_df` must already be real resampled weekly
    bars (real weekly closes) — never a daily-derived approximation (AC-1);
    this function computes RSI independently on each DataFrame's own close
    column, it does not resample or average one series from the other.
    """
    daily_val = _latest_valid(compute_rsi(daily_df, length=length))
    weekly_val = _latest_valid(compute_rsi(weekly_df, length=length))
    return MomentumResult(classify_momentum(daily_val, weekly_val), daily_val, weekly_val)


@dataclass(frozen=True)
class ScalpMomentumResult:
    state: MomentumStateLiteral
    value: float | None
    timeframe: str


def compute_scalp_momentum(
    df_4h: pd.DataFrame, length: int = RSI_LENGTH, timeframe: str = "4h"
) -> ScalpMomentumResult:
    """Faster single-timeframe RSI reading for the on-demand scalp drill-down
    (AC-7). Always independently labeled with its own timeframe (default 4h)
    so it's never confused with the board's currently-displayed interval.
    """
    value = _latest_valid(compute_rsi(df_4h, length=length))
    if value is None:
        return ScalpMomentumResult("insufficient", None, timeframe)
    return ScalpMomentumResult("PASS" if value > MOMENTUM_MIDLINE else "FAIL", value, timeframe)
