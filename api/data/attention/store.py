"""Per-source, per-symbol daily attention store (Parquet under the cache root).

Only COMPLETED UTC days (date < today) are kept: a partial day would freeze a
wrong value. One row per day; the first observation wins, except for Trends, whose
daily pull replaces the whole series (mode "replace-series") and is also frozen per
pull date. Paths resolve at call time so tests can redirect `cache.CACHE_ROOT`.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from itertools import pairwise
from pathlib import Path

import pandas as pd

from api.data import cache
from api.data.attention.types import SourceSeries


def store_path(source: str, symbol: str) -> Path:
    return cache.CACHE_ROOT / "attention" / source / f"{symbol.upper()}.parquet"


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


class StoreReadError(Exception):
    """A stored file exists but cannot be read (truncated, copied half-way, not parquet)."""


def read_points(source: str, symbol: str) -> list[tuple[date, float]]:
    path = store_path(source, symbol)
    if not path.exists():
        return []
    try:
        df = pd.read_parquet(path)
        return [(pd.Timestamp(d).date(), float(v)) for d, v in zip(df["date"], df["value"])]
    except Exception as exc:  # unreadable file: callers report `unavailable`, never a 500
        raise StoreReadError(f"unreadable store file {path.name}") from exc


WRITE_MODES = ("first", "replace-series")
# A replace-series pull shorter than this never replaces (a short pull must not shrink a good series).
MIN_REPLACE_DAYS = 90


def _write_frame(path: Path, days: list[date], values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_to_parquet(pd.DataFrame({"date": pd.to_datetime(days), "value": values}), path)


def _replaceable(points: list[tuple[date, float]]) -> bool:
    """A replace-series pull is stored only when it has at least MIN_REPLACE_DAYS rows, one per consecutive day
    in increasing order (no duplicate, gap or reversal), finite and not negative, and not all zero. Guarded here
    so no caller can bypass it."""
    if len(points) < MIN_REPLACE_DAYS or not any(v for _, v in points):
        return False
    if not all(math.isfinite(v) and v >= 0 for _, v in points):
        return False
    return all((b[0] - a[0]).days == 1 for a, b in pairwise(points))


def write_series(series: SourceSeries, today: date | None = None, mode: str = "first") -> int:
    """Store completed days; return the number of new rows.

    mode "first": merge, the first observation of a day wins (every source but Trends).
    mode "replace-series": the stored series becomes exactly this pull's completed days (one request
    scale, nothing stitched); a pull that fails `_replaceable` changes nothing.
    """
    if mode not in WRITE_MODES:
        raise ValueError(f"unknown store mode {mode!r}")
    today = today or _utc_today()
    path = store_path(series.source, series.symbol)
    if mode == "replace-series":
        pulled = [(d, float(v)) for d, v in series.points if d < today]
        if not _replaceable(pulled):
            return 0
        _write_frame(path, [d for d, _ in pulled], [v for _, v in pulled])
        return len(pulled)
    merged: dict[date, float] = dict(read_points(series.source, series.symbol))
    existing = len(merged)
    for d, v in series.points:
        if d < today and d not in merged:
            merged[d] = float(v)
    added = len(merged) - existing
    if added == 0:
        return 0
    days = sorted(merged)
    _write_frame(path, days, [merged[d] for d in days])
    return added


def pull_archive_path(source: str, pull_date: date) -> Path:
    return cache.CACHE_ROOT / "attention" / f"{source}_pulls" / f"{pull_date.isoformat()}.parquet"


def read_pull_archive(source: str, pull_date: date) -> dict[str, list[tuple[date, float]]]:
    """symbol -> points of the pull dated `pull_date` ({} when there is none)."""
    path = pull_archive_path(source, pull_date)
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    out: dict[str, list[tuple[date, float]]] = {}
    for sym, d, v in zip(df["symbol"], df["date"], df["value"]):
        out.setdefault(str(sym), []).append((pd.Timestamp(d).date(), float(v)))
    return {s: sorted(p) for s, p in out.items()}


def write_pull_archive(source: str, pull_date: date, series_list) -> int:
    """Freeze one pull for point-in-time reads: the `ok` series' completed days, by pull date. A second run on
    the same pull date adds only symbols not archived yet (first write per symbol and pull date wins).
    Returns the number of rows added."""
    archived = read_pull_archive(source, pull_date)
    rows = {s: p for s, p in archived.items()}
    added = 0
    for s in series_list:
        if s.state != "ok" or s.symbol in rows:
            continue
        pts = sorted({d: float(v) for d, v in reversed(s.points) if d < pull_date}.items())
        if pts:
            rows[s.symbol] = pts
            added += len(pts)
    if added == 0:
        return 0
    flat = [(sym, d, v) for sym in sorted(rows) for d, v in rows[sym]]
    df = pd.DataFrame({"symbol": [r[0] for r in flat], "date": pd.to_datetime([r[1] for r in flat]),
                       "value": [r[2] for r in flat]})
    path = pull_archive_path(source, pull_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_to_parquet(df, path)
    return added
