"""Perp data paths. The root is read at call time so tests can redirect it."""
from __future__ import annotations

import os
from pathlib import Path

from api.data import cache


def perp_root() -> Path:
    """`SCREENER_PERP_ROOT` if set, else `<cache root>/perp`."""
    raw = os.environ.get("SCREENER_PERP_ROOT")
    if raw:
        return Path(raw)
    return cache.CACHE_ROOT / "perp"


def hl_snapshot_path(coin: str, month: str) -> Path:
    """Monthly Hyperliquid snapshot file: `<root>/hl_snapshot/<COIN>/<YYYY-MM>.jsonl`."""
    return perp_root() / "hl_snapshot" / coin.upper() / f"{month}.jsonl"
