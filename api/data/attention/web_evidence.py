"""Evidence sidecar for the PC-side web sources (SPEC Annex B) and the one call that stores a coin-day.

Rows live at `<cache>/attention/<source>/_meta/<SYMBOL>.json` (git-ignored cache root), one row per completed
UTC day, frozen with the value: the first write wins, like `store.write_series`. `commit_day` writes the value
and its row together and writes nothing for a missing day, a day not yet complete, or a day already stored.
Pure file I/O; no network.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from api.data import cache
from api.data.attention import density, store
from api.data.attention.types import SourceSeries

SOURCE_RE = re.compile(r"[a-z0-9_]{1,40}")
SYMBOL_RE = re.compile(r"[A-Z0-9_]{1,24}")


@dataclass(frozen=True)
class EvidenceRow:
    date: date
    n: int
    span_hours: float
    capped: bool
    pagecap: bool
    spike: bool
    method: str
    collected_at: datetime
    backfilled: bool

    def to_json(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        d["collected_at"] = self.collected_at.isoformat()
        return d

    @classmethod
    def from_json(cls, d: dict) -> EvidenceRow:
        return cls(**{**d, "date": date.fromisoformat(d["date"]),
                      "collected_at": datetime.fromisoformat(d["collected_at"])})


def evidence_path(source: str, symbol: str) -> Path:
    if not SOURCE_RE.fullmatch(source) or not SYMBOL_RE.fullmatch(symbol.upper()):
        raise ValueError("bad source or symbol")
    return cache.CACHE_ROOT / "attention" / source / "_meta" / f"{symbol.upper()}.json"


def read_rows(source: str, symbol: str) -> dict[date, EvidenceRow]:
    path = evidence_path(source, symbol)
    if not path.exists():
        return {}
    rows = (EvidenceRow.from_json(r) for r in json.loads(path.read_text(encoding="utf-8"))["rows"])
    return {r.date: r for r in rows}


def commit_day(source: str, symbol: str, day: date, result: density.DayResult | None, *, now: datetime,
               method: str, backfilled: bool = False, value: float | None = None,
               trailing_median: float | None = None) -> bool:
    """Store one completed coin-day and its evidence row; return True when something new was written.

    `value` overrides `result.value` (the caller passes `density.finalize`'s output); None from either is a
    missing day and writes nothing.
    """
    value = result.value if value is None and result is not None else value
    if result is None or value is None or not density.storable(day, now):
        return False
    rows = read_rows(source, symbol)
    if day in rows or any(d == day for d, _ in store.read_points(source, symbol)):
        return False
    series = SourceSeries(source, symbol.upper(), [(day, float(value))])
    if store.write_series(series, today=now.astimezone(timezone.utc).date()) != 1:
        return False
    rows[day] = EvidenceRow(day, result.n, result.span_hours, result.capped, result.pagecap,
                            density.is_spike(float(value), trailing_median), method, now, backfilled)
    path = evidence_path(source, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json({"rows": [rows[d].to_json() for d in sorted(rows)]}, path)
    return True
