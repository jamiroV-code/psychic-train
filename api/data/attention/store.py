"""Per-source, per-symbol daily attention store (Parquet under the cache root).

Only COMPLETED UTC days (date < today) are kept: a partial day would freeze a
wrong value. One row per day; the first observation wins. Paths resolve at
call time so tests can redirect `cache.CACHE_ROOT`.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from api.data import cache
from api.data.attention.types import SourceSeries


def store_path(source: str, symbol: str) -> Path:
    return cache.CACHE_ROOT / "attention" / source / f"{symbol.upper()}.parquet"


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def read_points(source: str, symbol: str) -> list[tuple[date, float]]:
    path = store_path(source, symbol)
    if not path.exists():
        return []
    df = pd.read_parquet(path)
    return [(pd.Timestamp(d).date(), float(v)) for d, v in zip(df["date"], df["value"])]


def write_series(series: SourceSeries, today: date | None = None) -> int:
    """Merge completed days into the store; return the number of new rows."""
    today = today or _utc_today()
    merged: dict[date, float] = dict(read_points(series.source, series.symbol))
    existing = len(merged)
    for d, v in series.points:
        if d < today and d not in merged:
            merged[d] = float(v)
    added = len(merged) - existing
    if added == 0:
        return 0
    path = store_path(series.source, series.symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    days = sorted(merged)
    df = pd.DataFrame({"date": pd.to_datetime(days), "value": [merged[d] for d in days]})
    cache._atomic_to_parquet(df, path)
    return added
