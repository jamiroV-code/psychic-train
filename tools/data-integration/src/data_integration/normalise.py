"""Validated ParsedTable -> DataFrame with exactly the cache OHLCV columns (UTC timestamps)."""
from __future__ import annotations

import pandas as pd

from data_integration import paths

paths._repo_root()
from api.data.cache import OHLCV_COLUMNS  # noqa: E402

from data_integration.types import ParsedTable  # noqa: E402
from data_integration.validate import column_index, parse_number  # noqa: E402


def normalise(table: ParsedTable, source: str) -> pd.DataFrame:
    idx = column_index(table)
    data = {
        "timestamp": pd.to_datetime([r[idx["date"]].strip() for r in table.rows], utc=True),
        "source": [source] * len(table.rows),
    }
    for col in ("open", "high", "low", "close", "volume"):
        data[col] = [float(parse_number(r[idx[col]])) for r in table.rows]
    return pd.DataFrame(data)[OHLCV_COLUMNS]
