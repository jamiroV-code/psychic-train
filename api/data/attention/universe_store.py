"""Top-100 market-cap snapshots for the D-3 reference universe.

One JSON file under the cache root: {"snapshots": [{date, coins}]}, newest last,
at most KEEP_SNAPSHOTS kept. The path is resolved at call time so tests redirect it.
"""
from __future__ import annotations

import json
from pathlib import Path

from api.data import cache

KEEP_SNAPSHOTS = 14


def _path() -> Path:
    return cache.CACHE_ROOT / "attention" / "universe.json"


def _read_snapshots() -> list[dict]:
    try:
        snaps = json.loads(_path().read_text(encoding="utf-8"))["snapshots"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return [s for s in snaps if isinstance(s, dict) and "date" in s] if isinstance(snaps, list) else []


def write_snapshot(date: str, rows: list[dict]) -> None:
    snaps = [s for s in _read_snapshots() if s["date"] != date]
    snaps.append({"date": date, "coins": rows})
    snaps.sort(key=lambda s: s["date"])
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json({"snapshots": snaps[-KEEP_SNAPSHOTS:]}, path)


def read_latest() -> dict | None:
    snaps = _read_snapshots()
    return snaps[-1] if snaps else None
