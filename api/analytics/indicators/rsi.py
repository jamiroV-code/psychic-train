"""RSI over a bar series (moved from `momentum.py`, T36 / S4).

`pandas-ta-classic` Stage-0 confirmation (PLAN.md RFC-001 Stage 0): the
DataFrame accessor pattern is `df.ta.rsi(length=N)` — `length` is the
confirmed parameter name. Callers pass `length=` explicitly rather than
relying on the library's own default.
"""
from __future__ import annotations

import pandas as pd
import pandas_ta_classic  # noqa: F401 - registers the `.ta` DataFrame accessor.
# The installed PyPI distribution is `pandas-ta-classic`, whose importable
# module is `pandas_ta_classic` (confirmed against PyPI's own usage example,
# 18-09-26) - NOT `pandas_ta`. The original `import pandas_ta` only worked in
# the EXECUTE sandbox because its local shim happened to be named to match
# the (incorrect) import statement rather than the real package - a real
# `uv sync` run on the user's machine caught this for real (ModuleNotFoundError).

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
