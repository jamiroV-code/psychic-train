"""Source registry and the store-only reader (no network)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from api.data.attention import coingecko_attention, store, wikipedia
from api.data.attention.types import MIN_HISTORY_DAYS, SourceSeries

FETCHERS = {
    "wikipedia": wikipedia.fetch_series,
    "coingecko": coingecko_attention.fetch_series,
}

PROBE_RECORDS_PATH = Path(__file__).with_name("probe_records.json")


def load_probe_records(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or PROBE_RECORDS_PATH).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_series(source: str, symbol: str, today: date | None = None,
                probe_path: Path | None = None) -> SourceSeries:
    """Read one series from the store. A source without a probe record is not-probed."""
    if source not in load_probe_records(probe_path):
        return SourceSeries(source, symbol, [], "not-probed", "no probe record")
    pts = store.read_points(source, symbol)
    if today is not None:
        pts = [p for p in pts if p[0] < today]
    if not pts:
        return SourceSeries(source, symbol, [], "unavailable", "no stored data")
    if len(pts) < MIN_HISTORY_DAYS:
        return SourceSeries(source, symbol, pts, "insufficient-history", f"{len(pts)} days")
    return SourceSeries(source, symbol, pts, "ok", "")
