"""The only cache writer: api.data.cache.write_ohlcv, which replaces the whole series."""
from __future__ import annotations

import pandas as pd

from data_integration import paths

paths._repo_root()
from api.data import cache  # noqa: E402


class TargetNotEmpty(RuntimeError):
    """The cache key already holds data and replace=True was not passed."""


def existing(symbol: str, timeframe: str) -> pd.DataFrame:
    return cache.read_ohlcv(symbol, timeframe)


def write_series(symbol: str, timeframe: str, df: pd.DataFrame, *, replace: bool = False) -> None:
    if not replace and len(existing(symbol, timeframe)):
        raise TargetNotEmpty(f"{symbol}/{timeframe} already holds data")
    cache.write_ohlcv(symbol, timeframe, df)
