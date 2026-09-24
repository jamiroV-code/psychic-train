"""Narrative dashboard RFC-3: history, composite, comparison and
change-in-attention behind `GET /api/narrative/history` (ADR-4, ADR-5).

A pure read of the narrative archive. Nothing here calls a provider adapter
or `trigger.compute_narrative_categories` (those fetch live data and write
the cache). The only thing shared with the `/categories` path is
`trigger.load_seed_categories` (ADR-4); trigger constants are read, not changed.

Series keying (RFC-2 report item 6): pytrends and reddit are stored under the
seed's primary keyword (`keywords[0]`, what trigger.py passes to the
adapters); coingecko, coingecko-narrative and exchange rows are stored under
the category id.

Numbers are never silently wrong:
- every source is normalised within itself only (`scoring.normalize_within_source`),
  and nightly vs backfilled pytrends are normalised separately (different
  Google windows, not the same scale);
- null raw values are carried as null, never 0-filled;
- a composite point exists only when at least `trigger.MIN_AVAILABLE_SOURCES`
  composite sources have a value that date — otherwise the date is absent;
- a category missing from a ranking gets `rank=None` + a reason, never last place.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from api.analytics.narrative import mapping, scoring, trigger
from api.data import cache
from api.data.hyperliquid_narrative_adapter import HYPERLIQUID_REDISTRIBUTABLE
from api.data.pytrends_adapter import PYTRENDS_DEAD_THRESHOLD_DAYS

# One missed nightly run (2-day step) is tolerated; two are flagged.
NARRATIVE_MAX_GAP_DAYS = 2
CHANGE_WINDOW_DAYS = 7  # ADR-5
CHANGE_BASELINE_TOLERANCE_DAYS = 2  # baseline may sit 7..9 days back
FRESH_MAX_AGE_DAYS = 1  # nightly archive: yesterday's point still counts as fresh
RANK_DECIMALS = 6

# Redistribution flags. None of these sources is cleared for redistribution;
# each is a one-line flip once its terms are checked.
PYTRENDS_REDISTRIBUTABLE = False  # unofficial Google Trends scraper
REDDIT_REDISTRIBUTABLE = False  # Reddit API terms
COINGECKO_REDISTRIBUTABLE = False  # free-tier attribution terms

BACKFILLED_STATUS = "backfilled"
LEGACY_COINGECKO_LABEL = "CoinGecko trending (legacy-map count)"
LEGACY_COINGECKO_REASON = "legacy-map-count: counts BTC/ETH/HYPE only; excluded from composite"
COINGECKO_NARRATIVE_SOURCE = "coingecko-narrative"  # written by RFC-4's nightly job, not here

# Composite source slots (coverage denominator). pytrends counts once per
# date whichever variant (nightly/backfill) exists.
COMPOSITE_SLOTS = ("pytrends", "reddit", COINGECKO_NARRATIVE_SOURCE, "exchange_volume_share")


class UnknownCategoryError(ValueError):
    def __init__(self, unknown: list[str]):
        self.unknown = unknown
        super().__init__(f"unknown category id(s): {', '.join(unknown)}")


@dataclass
class SeriesData:
    source: str
    label: str
    cache_key: str
    redistributable: bool
    in_composite: bool
    composite_slot: str | None
    variant: str | None = None
    # columns: date (str), raw (float|None), point_status, reason, normalized, gap_before
    frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    status: str = "unavailable"
    reason: str | None = "no-archived-data"


@dataclass
class CategoryHistory:
    category_id: str
    label: str
    keywords: list[str]
    coins: list[tuple[str, bool]]
    series: list[SeriesData]
    composite: pd.DataFrame  # date, value, coverage, sources_present, trust_weight, mixed_scale, gap_before
    composite_status: str
    composite_reason: str | None


@dataclass
class RankEntry:
    category_id: str
    rank: int | None
    value: float | None
    mixed_scale: bool
    status: str
    reason: str | None
    baseline_date: str | None = None


@dataclass
class NarrativeHistoryResult:
    generated_utc: str
    grid_dates: list[str]
    categories: list[CategoryHistory]
    comparison_as_of: str | None
    comparison: list[RankEntry]
    change: list[RankEntry]

    @property
    def redistributable_all(self) -> bool:
        return all(s.redistributable for c in self.categories for s in c.series)


# --- pure helpers ----------------------------------------------------------


def gap_before_flags(dates: list[str], max_gap_days: int = NARRATIVE_MAX_GAP_DAYS) -> list[bool]:
    """True when the calendar-day step from the previous date exceeds
    `max_gap_days`. Same rule as regime `gap_before_flags`, re-implemented
    (ADR-4: different package). Run on the full series before filtering."""
    out: list[bool] = []
    prev: date | None = None
    for d in dates:
        cur = date.fromisoformat(d)
        out.append(prev is not None and (cur - prev).days > max_gap_days)
        prev = cur
    return out


def normalize(frame: pd.DataFrame) -> pd.Series:
    """Within-series min-max over the full stored history; null raw stays null."""
    raw = pd.to_numeric(frame["raw"], errors="coerce")
    valid = raw.dropna()
    out = pd.Series([None] * len(frame), index=frame.index, dtype=object)
    if not valid.empty:
        norm = scoring.normalize_within_source(valid.astype(float))
        for idx, v in norm.items():
            out[idx] = float(v)
    return out


def competition_rank(values: dict[str, float]) -> dict[str, int]:
    """Descending competition rank (1, 1, 3) on values rounded to RANK_DECIMALS."""
    rounded = {k: round(v, RANK_DECIMALS) for k, v in values.items()}
    ordered = sorted(rounded.values(), reverse=True)
    return {k: ordered.index(v) + 1 for k, v in rounded.items()}


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.sort_values("date", kind="stable").reset_index(drop=True)
    frame["normalized"] = normalize(frame) if not frame.empty else pd.Series(dtype=object)
    frame["gap_before"] = gap_before_flags(list(frame["date"])) if not frame.empty else pd.Series(dtype=bool)
    return frame


def _age_status(s: SeriesData, today: date) -> None:
    f = s.frame
    if f.empty or f["raw"].isna().all() and s.source != "exchange_new_listings":
        s.status, s.reason = "unavailable", "no-archived-data"
        return
    last = f.iloc[-1]
    if s.variant == "backfill-269d":
        s.status, s.reason = "ok", "backfilled history (269-day Google window, separate scale)"
        return
    age = (today - date.fromisoformat(last["date"])).days
    if age <= FRESH_MAX_AGE_DAYS:
        if s.source.startswith("exchange_") and last["point_status"] not in (None, "ok"):
            s.status, s.reason = "unavailable", last["reason"] or "unavailable"
        else:
            s.status, s.reason = "ok", LEGACY_COINGECKO_REASON if s.source == "coingecko" else None
        return
    if s.source == "pytrends" and age > PYTRENDS_DEAD_THRESHOLD_DAYS:
        s.status = "presumed-dead"
    else:
        s.status = "stale"
    s.reason = f"last-point-{age}-days-old"


def _narrative_frame(source: str, key: str) -> pd.DataFrame:
    df = cache.read_narrative_series(source, key)
    if df.empty:
        return pd.DataFrame(columns=["date", "raw", "point_status", "reason"])
    return pd.DataFrame({
        "date": df["date"].astype(str).to_numpy(),
        "raw": pd.to_numeric(df["raw_value"], errors="coerce").to_numpy(),
        "point_status": df["source_status"].astype(object).where(df["source_status"].notna(), None).to_numpy(),
        "reason": [None] * len(df),
    })


def _exchange_frames(category_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = cache.read_exchange_series(category_id)
    cols = ["date", "raw", "point_status", "reason"]
    if df.empty:
        return pd.DataFrame(columns=cols), pd.DataFrame(columns=cols)

    def _obj(col: str) -> list:
        return [None if pd.isna(v) else v for v in df[col]]

    dates = df["date"].astype(str).to_list()
    vol = pd.DataFrame({"date": dates, "raw": [None if pd.isna(v) else float(v) for v in df["volume_share"]],
                        "point_status": _obj("volume_status"), "reason": _obj("volume_reason")})
    lst = pd.DataFrame({"date": dates, "raw": [None if pd.isna(v) else float(v) for v in df["new_listing_count"]],
                        "point_status": _obj("listing_status"), "reason": _obj("listing_reason")})
    return vol, lst


def load_category_series(category_id: str, keyword: str, today: date) -> list[SeriesData]:
    py = _narrative_frame("pytrends", keyword)
    backfilled = py["point_status"] == BACKFILLED_STATUS
    vol, listings = _exchange_frames(category_id)
    series = [
        SeriesData("pytrends", "Google Trends (nightly, 7-day window)", keyword, PYTRENDS_REDISTRIBUTABLE,
                   True, "pytrends", "nightly-7d", py[~backfilled].copy()),
        SeriesData("pytrends", "Google Trends (backfill, 269-day window)", keyword, PYTRENDS_REDISTRIBUTABLE,
                   True, "pytrends", "backfill-269d", py[backfilled].copy()),
        SeriesData("reddit", "Reddit mentions", keyword, REDDIT_REDISTRIBUTABLE, True, "reddit",
                   frame=_narrative_frame("reddit", keyword)),
        SeriesData("coingecko", LEGACY_COINGECKO_LABEL, category_id, COINGECKO_REDISTRIBUTABLE, False, None,
                   frame=_narrative_frame("coingecko", category_id)),
        SeriesData(COINGECKO_NARRATIVE_SOURCE, "CoinGecko trending (narrative-map count)", category_id,
                   COINGECKO_REDISTRIBUTABLE, True, COINGECKO_NARRATIVE_SOURCE,
                   frame=_narrative_frame(COINGECKO_NARRATIVE_SOURCE, category_id)),
        SeriesData("exchange_volume_share", "Hyperliquid 24h volume share", category_id,
                   HYPERLIQUID_REDISTRIBUTABLE, True, "exchange_volume_share", frame=vol),
        SeriesData("exchange_new_listings", "Hyperliquid new listings (display only)", category_id,
                   HYPERLIQUID_REDISTRIBUTABLE, False, None, frame=listings),
    ]
    for s in series:
        s.frame = _prepare(s.frame)
        _age_status(s, today)
    return series


def build_composite(series: list[SeriesData]) -> pd.DataFrame:
    """Skipna mean of within-source-normalised composite sources per date,
    only where >= MIN_AVAILABLE_SOURCES slots are present (ADR-5)."""
    by_date: dict[str, dict[str, tuple[float, bool]]] = {}
    for s in series:
        if not s.in_composite or s.frame.empty:
            continue
        for row in s.frame.itertuples(index=False):
            if row.normalized is None:
                continue
            slots = by_date.setdefault(row.date, {})
            backfill = s.variant == "backfill-269d"
            # nightly and backfill never share a date (backfill skips owned
            # dates); if they ever did, the nightly value wins.
            if s.composite_slot in slots and backfill:
                continue
            slots[s.composite_slot] = (float(row.normalized), backfill)

    rows = []
    for d in sorted(by_date):
        slots = by_date[d]
        if len(slots) < trigger.MIN_AVAILABLE_SOURCES:
            continue
        values = [v for v, _ in slots.values()]
        pytrends_present = "pytrends" in slots
        rows.append({
            "date": d,
            "value": float(sum(values) / len(values)),
            "coverage": len(slots) / len(COMPOSITE_SLOTS),
            "sources_present": [k for k in COMPOSITE_SLOTS if k in slots],
            "trust_weight": trigger.BASE_TRUST_WEIGHT if pytrends_present else trigger.REDUCED_SOURCE_TRUST_CAP,
            "mixed_scale": bool(pytrends_present and slots["pytrends"][1]),
        })
    cols = ["date", "value", "coverage", "sources_present", "trust_weight", "mixed_scale"]
    out = pd.DataFrame(rows, columns=cols)
    out["gap_before"] = gap_before_flags(list(out["date"])) if not out.empty else pd.Series(dtype=bool)
    return out


def _in_range(frame: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
    if frame.empty:
        return frame
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= frame["date"] >= start.isoformat()
    if end is not None:
        mask &= frame["date"] <= end.isoformat()
    return frame[mask]


def rank_comparison(composites: dict[str, pd.DataFrame]) -> tuple[str | None, list[RankEntry]]:
    """Rank categories on their composite at `as_of` (latest composite date)."""
    dates = [c["date"].max() for c in composites.values() if not c.empty]
    as_of = max(dates) if dates else None
    values: dict[str, tuple[float, bool]] = {}
    for cid, c in composites.items():
        hit = c[c["date"] == as_of] if as_of else c.iloc[0:0]
        if not hit.empty:
            values[cid] = (float(hit.iloc[0]["value"]), bool(hit.iloc[0]["mixed_scale"]))
    ranks = competition_rank({k: v for k, (v, _) in values.items()})
    entries = []
    for cid in composites:
        if cid in values:
            entries.append(RankEntry(cid, ranks[cid], values[cid][0], values[cid][1], "ok", None))
        else:
            reason = "no-composite-on-as-of" if as_of else "no-composite-data"
            entries.append(RankEntry(cid, None, None, False, "unavailable", reason))
    return as_of, _sort_entries(entries)


def rank_change(composites: dict[str, pd.DataFrame], as_of: str | None) -> list[RankEntry]:
    """delta = composite(as_of) - composite(baseline); baseline = latest point
    in [as_of - 9d, as_of - 7d]."""
    deltas: dict[str, tuple[float, bool, str]] = {}
    reasons: dict[str, str] = {}
    for cid, c in composites.items():
        if as_of is None:
            reasons[cid] = "no-composite-data"
            continue
        now = c[c["date"] == as_of]
        if now.empty:
            reasons[cid] = "no-composite-on-as-of"
            continue
        a = date.fromisoformat(as_of)
        lo = (a - timedelta(days=CHANGE_WINDOW_DAYS + CHANGE_BASELINE_TOLERANCE_DAYS)).isoformat()
        hi = (a - timedelta(days=CHANGE_WINDOW_DAYS)).isoformat()
        base = c[(c["date"] >= lo) & (c["date"] <= hi)]
        if base.empty:
            reasons[cid] = "no-baseline-in-window"
            continue
        b = base.iloc[-1]
        deltas[cid] = (
            float(now.iloc[0]["value"]) - float(b["value"]),
            bool(now.iloc[0]["mixed_scale"]) or bool(b["mixed_scale"]),
            str(b["date"]),
        )
    ranks = competition_rank({k: v for k, (v, _, _) in deltas.items()})
    entries = []
    for cid in composites:
        if cid in deltas:
            d, mixed, bdate = deltas[cid]
            entries.append(RankEntry(cid, ranks[cid], d, mixed, "ok", None, bdate))
        else:
            entries.append(RankEntry(cid, None, None, False, "unavailable", reasons[cid]))
    return _sort_entries(entries)


def _sort_entries(entries: list[RankEntry]) -> list[RankEntry]:
    return sorted(entries, key=lambda e: (e.rank is None, e.rank or 0, e.category_id))


def _coins_for(category_id: str) -> list[tuple[str, bool]]:
    curated = mapping.load_category_map()
    out = []
    for symbol in sorted(s for s, cid in curated.items() if cid == category_id):
        _, narrative_only = mapping.map_coin_to_narrative_category(symbol)
        out.append((symbol, narrative_only))
    return out


# --- orchestrator ----------------------------------------------------------


def build_narrative_history(
    category_ids: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    today: date | None = None,
) -> NarrativeHistoryResult:
    """Read-only. `category_ids` must be seed ids (allow-listed before any
    cache path is built from them); unknown ids raise UnknownCategoryError."""
    seeds = trigger.load_seed_categories()
    seed_by_id = {c["id"]: c for c in seeds}
    if category_ids is None:
        wanted = [c["id"] for c in seeds]
    else:
        unknown = [c for c in category_ids if c not in seed_by_id]
        if unknown:
            raise UnknownCategoryError(unknown)
        wanted = list(dict.fromkeys(category_ids))
    now = datetime.now(timezone.utc)
    today = today or now.date()

    histories: list[CategoryHistory] = []
    full_composites: dict[str, pd.DataFrame] = {}
    grid: set[str] = set()
    for cid in wanted:
        seed = seed_by_id[cid]
        keyword = seed["keywords"][0] if seed.get("keywords") else cid
        series = load_category_series(cid, keyword, today)
        composite = build_composite(series)
        # Rankings see composites up to `end` only (the viewing window's as-of).
        full_composites[cid] = _in_range(composite, None, end)
        for s in series:
            s.frame = _in_range(s.frame, start, end)
            grid.update(s.frame["date"])
        shown = _in_range(composite, start, end)
        grid.update(shown["date"])
        status, reason = ("ok", None) if not shown.empty else (
            "unavailable", f"insufficient-coverage: fewer than {trigger.MIN_AVAILABLE_SOURCES} sources on every date")
        histories.append(CategoryHistory(
            cid, seed.get("label", cid), list(seed.get("keywords", [])), _coins_for(cid),
            series, shown, status, reason,
        ))

    as_of, comparison = rank_comparison(full_composites)
    change = rank_change(full_composites, as_of)
    return NarrativeHistoryResult(
        generated_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        grid_dates=sorted(grid),
        categories=histories,
        comparison_as_of=as_of,
        comparison=comparison,
        change=change,
    )
