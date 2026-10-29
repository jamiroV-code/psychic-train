"""Source registry and the store-only reader (no network)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from api.data.attention import (coingecko_attention, exchange_volume, reddit, store, trends, web_evidence,
                                 wikipedia, xsearch)
from api.data.attention.types import MIN_HISTORY_DAYS, SourceSeries

FETCHERS = {
    "wikipedia": wikipedia.fetch_series,
    "coingecko": coingecko_attention.fetch_series,
    "exchange_volume": exchange_volume.fetch_binance_series,
    "hyperliquid_volume": exchange_volume.fetch_hyperliquid_series,
    "trends": trends.fetch_series,
    "reddit": reddit.fetch_series,
    "xsearch": xsearch.fetch_series,
}

# Fetchers with no weight on purpose: same volume group as exchange_volume, so it adds no independent signal.
EXCLUDED_SOURCES = {"hyperliquid_volume": "same volume group as exchange_volume"}

# Weighted Discovery source -> the methods (stores) that can feed it (SPEC AC14, Annex B). The first is the
# official-API store fetched on GitHub; the others are written by the PC worker. Each is its own series.
SOURCE_IMPLS = {"xsearch": ("xsearch", "xsearch_web"), "reddit": ("reddit", "reddit_web", "reddit_stream")}
# Stores written by the in-API PC worker on the owner's host (W8c, W8c2, W8d, W8e). They have no separate probe
# step: a stored file is itself the evidence that the worker ran there, so the probe-record gate does not apply.
PC_STORES = frozenset({"xsearch_web", "reddit_web", "reddit_stream"})

PROBE_RECORDS_PATH = Path(__file__).with_name("probe_records.json")


def load_probe_records(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or PROBE_RECORDS_PATH).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _known_at_time(source: str, symbol: str, pts: list[tuple[date, float]]) -> list[tuple[date, float]]:
    """Drop points not known on the day after them (SPEC AC5, Annex B): an evidence row flagged `backfilled`, or
    one collected after D+1. Points without an evidence row (sources with no sidecar) are kept."""
    try:
        rows = web_evidence.read_rows(source, symbol)
    except (OSError, ValueError, KeyError, TypeError):
        return pts
    out = []
    for d, v in pts:
        r = rows.get(d)
        if r is not None and (r.backfilled or r.collected_at.date() > d + timedelta(days=1)):
            continue
        out.append((d, v))
    return out


def read_series(source: str, symbol: str, today: date | None = None,
                probe_path: Path | None = None, *, known_at_time: bool = False) -> SourceSeries:
    """Read one series from the store. A source without a probe record is not-probed (PC stores excepted).
    `known_at_time` keeps only the points known the day after them (backfilled values excluded)."""
    if source not in PC_STORES and source not in load_probe_records(probe_path):
        return SourceSeries(source, symbol, [], "not-probed", "no probe record")
    try:
        pts = store.read_points(source, symbol)
    except store.StoreReadError as exc:
        return SourceSeries(source, symbol, [], "unavailable", str(exc))
    if today is not None:
        pts = [p for p in pts if p[0] < today]
    if known_at_time:
        pts = _known_at_time(source, symbol, pts)
    if not pts:
        return SourceSeries(source, symbol, [], "unavailable", "no stored data")
    if len(pts) < MIN_HISTORY_DAYS:
        return SourceSeries(source, symbol, pts, "insufficient-history", f"{len(pts)} days")
    return SourceSeries(source, symbol, pts, "ok", "")
