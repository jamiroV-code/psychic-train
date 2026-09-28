"""Narrative-v2 RFC-5 (ADR-5): daily social-mindshare, "blend + show each",
behind `GET /api/narrative/mindshare?date=`.

For one selected day, each source's own same-day cross-narrative share:

- `pytrends`  — RFC-3 `pytrends-blended` within-source-normalised value
               (shared scale via anchor-chaining, ADR-3); insufficient series skipped.
- `coingecko` — `coingecko-narrative` raw count (narrative's coins in trending,
               ADR-2 config map) / total trending-tagged appearances that day.
- `reddit`    — primary-keyword Reddit mention count, same shape. With no Reddit
               credentials there are simply no rows: Reddit is absent that day,
               never zero-filled.

    share[s][i] = v[s][i] / sum_j v[s][j]   over narratives with a value in s that day

A source is PRESENT that day when >= 1 narrative has a value and the total > 0.
Headline mindshare[i] = skipna mean of i's present per-source shares (the
`build_composite` pattern), renormalised over included narratives so the day
sums to exactly 1.0 even when narratives differ in source coverage (identity
when coverage is uniform). Narratives with no share in any present source are
EXCLUDED explicitly (mindshare None + reason), never shown as 0.

Day labels: `no_sources_available` (0 present), `only_one_source` (1 present) —
a single-source day is never presented as consensus. The narrative list length
drives everything; no slot count is hardcoded. Read-only: no provider fetch,
no cache write.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import pandas as pd

from api.analytics.narrative import history, narrative_config, scoring

SOURCES = ("pytrends", "coingecko", "reddit")
REASON_EXCLUDED = "no data from any available source on this day"


@dataclass
class MindshareEntry:
    category_id: str
    label: str
    mindshare: float | None
    sources: dict[str, float | None]
    status: str  # "ok" | "excluded"
    reason: str | None


@dataclass
class MindshareResult:
    generated_utc: str
    date: str | None
    available_dates: list[str]
    sources_present: list[str]
    n_sources: int
    only_one_source: bool
    no_sources_available: bool
    entries: list[MindshareEntry] = field(default_factory=list)


# --- pure maths ------------------------------------------------------------


def source_shares(values: dict[str, float | None]) -> dict[str, float] | None:
    """Same-day cross-narrative share for ONE source. None = source absent."""
    present = {k: float(v) for k, v in values.items() if v is not None and not pd.isna(v)}
    total = sum(present.values())
    if not present or total <= 0:
        return None
    return {k: v / total for k, v in present.items()}


def blend_day(ids: list[str], per_source: dict[str, dict[str, float | None]]) -> tuple[
        list[str], dict[str, float | None], dict[str, dict[str, float | None]]]:
    """-> (sources_present, headline mindshare per id, per-source share per id)."""
    shares = {s: source_shares(per_source.get(s, {})) for s in SOURCES}
    present = [s for s in SOURCES if shares[s] is not None]
    by_id: dict[str, dict[str, float | None]] = {
        i: {s: (shares[s] or {}).get(i) for s in SOURCES} for i in ids}
    raw: dict[str, float] = {}
    for i in ids:
        vals = [by_id[i][s] for s in present if by_id[i][s] is not None]
        if vals:
            raw[i] = sum(vals) / len(vals)
    total = sum(raw.values())
    headline = {i: (raw[i] / total if i in raw and total > 0 else None) for i in ids}
    return present, headline, by_id


# --- cache read ------------------------------------------------------------


def _values(frame: pd.DataFrame, col: str) -> dict[str, float]:
    if frame.empty:
        return {}
    out = {}
    for d, v in zip(frame["date"], frame[col]):
        if v is not None and not pd.isna(v):
            out[str(d)] = float(v)
    return out


def _load(today: date) -> tuple[list[dict], dict[str, dict[str, dict[str, float]]]]:
    """-> (narratives, {source: {narrative_id: {date: value}}})."""
    narratives = narrative_config.load_narratives()
    data: dict[str, dict[str, dict[str, float]]] = {s: {} for s in SOURCES}
    for seed in narratives:
        cid = seed["id"]
        series = history.load_category_series(
            cid, narrative_config.primary_keyword(seed), today, list(seed.get("keywords", [])))
        for s in series:
            if s.source == history.PYTRENDS_BLENDED_SOURCE:
                if s.sufficiency != scoring.SUFFICIENCY_INSUFFICIENT:
                    data["pytrends"][cid] = _values(s.frame, "normalized")
            elif s.source == history.COINGECKO_NARRATIVE_SOURCE:
                data["coingecko"][cid] = _values(s.frame, "raw")
            elif s.source == "reddit":
                data["reddit"][cid] = _values(s.frame, "raw")
    return narratives, data


def build_mindshare(day: date | None = None, today: date | None = None) -> MindshareResult:
    now = datetime.now(timezone.utc)
    today = today or now.date()
    narratives, data = _load(today)
    ids = [n["id"] for n in narratives]
    labels = {n["id"]: n.get("label", n["id"]) for n in narratives}

    dates: set[str] = set()
    for per_id in data.values():
        for series in per_id.values():
            dates.update(series)
    available = sorted(d for d in dates
                       if blend_day(ids, {s: {i: data[s].get(i, {}).get(d) for i in ids} for s in SOURCES})[0])
    selected = day.isoformat() if day else (available[-1] if available else None)

    per_source = {s: {i: data[s].get(i, {}).get(selected) for i in ids} for s in SOURCES} if selected else {}
    present, headline, by_id = blend_day(ids, per_source)
    entries = [
        MindshareEntry(i, labels[i], headline[i], by_id[i],
                       "ok" if headline[i] is not None else "excluded",
                       None if headline[i] is not None else REASON_EXCLUDED)
        for i in ids
    ]
    entries.sort(key=lambda e: (e.mindshare is None, -(e.mindshare or 0.0), e.category_id))
    return MindshareResult(
        generated_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        date=selected,
        available_dates=available,
        sources_present=present,
        n_sources=len(present),
        only_one_source=len(present) == 1,
        no_sources_available=len(present) == 0,
        entries=entries,
    )
