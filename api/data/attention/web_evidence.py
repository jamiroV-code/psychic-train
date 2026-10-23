"""Evidence sidecar for the PC-side web sources (SPEC Annex B) and the one call that stores a coin-day.

Rows live at `<cache>/attention/<source>/_meta/<SYMBOL>.json` (git-ignored cache root), one row per completed
UTC day, frozen with the value: the first write wins, like `store.write_series`. `commit_day` is the only way a
web value is stored: the number comes from `density.finalize` (the zero rule of AC3, never a non-finite or
negative value), the evidence row (which carries the value) is written first, and a value missing after a crash
between the two writes is restored from that row on the next call. Pure file I/O; no network.
"""
from __future__ import annotations

import json
import math
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
    value: float
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


def _storable_value(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _write_value(source: str, symbol: str, day: date, value: float, now: datetime) -> bool:
    series = SourceSeries(source, symbol.upper(), [(day, float(value))])
    return store.write_series(series, today=now.astimezone(timezone.utc).date()) == 1


def commit_day(source: str, symbol: str, day: date, result: density.DayResult | None, *, canary_ok: bool,
               trailing_median: float | None, now: datetime, method: str, backfilled: bool = False) -> bool:
    """Store one completed coin-day and its evidence row; return True when something new was written.

    `canary_ok` and `trailing_median` have no default, so no caller can skip the zero rule. Nothing is written
    for a missing day, a rejected zero, a day not yet complete or a day already stored.
    """
    if not density.storable(day, now):
        return False
    rows = read_rows(source, symbol)
    stored = {d for d, _ in store.read_points(source, symbol)}
    if day in rows:
        # The evidence row is the frozen record; restore its value if a crash lost it.
        if day in stored or not _storable_value(rows[day].value):
            return False
        return _write_value(source, symbol, day, rows[day].value, now)
    if day in stored:
        return False
    value = density.finalize(result, canary_ok=canary_ok, trailing_median=trailing_median)
    if result is None or not _storable_value(value):
        return False
    rows[day] = EvidenceRow(day, float(value), result.n, result.span_hours, result.capped, result.pagecap,
                            density.is_spike(float(value), trailing_median), method, now, backfilled)
    path = evidence_path(source, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    cache._atomic_write_json({"rows": [rows[d].to_json() for d in sorted(rows)]}, path)
    return _write_value(source, symbol, day, value, now)
