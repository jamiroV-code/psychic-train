"""One-off Google Trends history backfill for the narrative dashboard (RFC-2, ADR-2).

For each seed category it requests ONE daily window (the last
`WINDOW_DAYS` = 269 days — Google only returns daily points for windows up to
roughly 270 days; longer windows switch to weekly, which is out of scope per
decision D5). Rows flagged `isPartial` are dropped. Each remaining day is
written through the existing `cache.write_narrative_point(...,
source_status="backfilled")`.

Forward-written points always win (ADR-2): the script reads the existing
series ONCE up front and skips every date whose `source_status` is anything
other than "backfilled". `write_narrative_point` itself has no source
priority, so this read-before-write check is the only guard. Re-running only
replaces earlier backfilled rows.

Series key: the pytrends forward writer (`pytrends_adapter.fetch_trend`)
stores under `("pytrends", <keyword>)`, where the keyword is the seed's first
keyword (the same one `trigger.py` passes). The backfill writes under exactly
that key, otherwise the forward-wins check would compare against the wrong file.

Scale caveat (for RFC-5): every Google Trends request is normalised 0-100
within its own window. Backfilled daily values (269-day window) and the forward
values (last point of a `now 7-d` window) are therefore NOT on the same scale.

`pytrends` is deliberately NOT a dependency (unmaintained since 2025-04). To
run this for real, on a machine that can reach Google:
  uv run --project api --with pytrends python api/scripts/backfill_pytrends_history.py
  (add --dry-run to print the rows without writing)

Exit codes: 0 = at least one category written or all skipped cleanly;
1 = pytrends unavailable or every category failed to fetch.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import pandas as pd

from api.data import cache

SOURCE = "pytrends"
BACKFILLED = "backfilled"
WINDOW_DAYS = 269
TIMEOUT_SECONDS = 10.0
SEEDS_PATH = Path(__file__).resolve().parents[1] / "data" / "narratives.json"


@dataclass
class CategoryOutcome:
    category_id: str
    keyword: str | None
    status: str  # "ok" | "unavailable"
    reason: str | None = None
    written: int = 0
    skipped_forward: int = 0
    dropped_partial: int = 0
    first_date: str | None = None
    last_date: str | None = None


def load_seed_keywords(path: Path = SEEDS_PATH) -> list[tuple[str, str | None]]:
    """Enabled narratives from api/data/narratives.json (RFC-2 loader)."""
    from api.analytics.narrative import narrative_config
    return [(n["id"], narrative_config.primary_keyword(n)) for n in narrative_config.load_narratives(path)]


def window_timeframe(today: date) -> str:
    start = today - timedelta(days=WINDOW_DAYS)
    return f"{start.isoformat()} {today.isoformat()}"


def _default_trendreq_factory():
    from pytrends.request import TrendReq  # optional, may be absent

    return TrendReq(timeout=(TIMEOUT_SECONDS, TIMEOUT_SECONDS))


def fetch_daily_window(keyword: str, today: date, trendreq_factory: Callable | None = None) -> pd.DataFrame | None:
    """Return the raw interest_over_time frame, or None on any failure."""
    factory = trendreq_factory or _default_trendreq_factory
    try:
        client = factory()
        client.build_payload([keyword], timeframe=window_timeframe(today))
        df = client.interest_over_time()
    except Exception:
        return None
    if df is None or df.empty or keyword not in df.columns:
        return None
    return df


def daily_points(df: pd.DataFrame, keyword: str) -> tuple[list[tuple[str, float]], int]:
    """(date, value) pairs with isPartial rows dropped. Rejects non-daily
    frames rather than silently storing weekly points as daily."""
    work = df
    dropped = 0
    if "isPartial" in work.columns:
        partial = work["isPartial"].astype(bool)
        dropped = int(partial.sum())
        work = work[~partial]
    idx = pd.to_datetime(work.index)
    if len(idx) > 1 and pd.Series(idx).diff().dropna().max() > pd.Timedelta(days=1):
        raise ValueError("non-daily granularity returned")
    points: list[tuple[str, float]] = []
    for ts, value in zip(idx, work[keyword]):
        if pd.isna(value):
            continue
        points.append((ts.strftime("%Y-%m-%d"), float(value)))
    return points, dropped


def backfill_category(category_id: str, keyword: str | None, today: date,
                      trendreq_factory: Callable | None = None, dry_run: bool = False) -> CategoryOutcome:
    if not keyword:
        return CategoryOutcome(category_id, keyword, "unavailable", "no-keyword")
    df = fetch_daily_window(keyword, today, trendreq_factory)
    if df is None:
        return CategoryOutcome(category_id, keyword, "unavailable", "fetch-failed")
    try:
        points, dropped = daily_points(df, keyword)
    except ValueError as exc:
        return CategoryOutcome(category_id, keyword, "unavailable", str(exc))

    existing = cache.read_narrative_series(SOURCE, keyword)
    forward_dates: set[str] = set()
    if not existing.empty:
        mask = existing["source_status"].astype(str) != BACKFILLED
        forward_dates = set(existing.loc[mask, "date"].astype(str))

    out = CategoryOutcome(category_id, keyword, "ok", dropped_partial=dropped)
    for day, value in points:
        if day in forward_dates:
            out.skipped_forward += 1
            continue
        if not dry_run:
            cache.write_narrative_point(SOURCE, keyword, day, value, source_status=BACKFILLED)
        out.written += 1
        out.first_date = out.first_date or day
        out.last_date = day
    return out


def run(today: date | None = None, trendreq_factory: Callable | None = None,
        dry_run: bool = False, seeds_path: Path = SEEDS_PATH) -> list[CategoryOutcome]:
    today = today or datetime.now(timezone.utc).date()
    return [backfill_category(cid, kw, today, trendreq_factory, dry_run) for cid, kw in load_seed_keywords(seeds_path)]


# --- narrative-v2 RFC-3 (ADR-3): batched blended backfill -----------------
#
# The per-narrative primary-keyword backfill above is preserved exactly
# (already-backfilled 269-day history stays as-is). The blended series
# (`pytrends-blended/{narrative id}`) uses the SAME batching/anchor-chaining
# helpers as the nightly job (`pytrends_adapter.plan_batches` +
# `chain_batches`), applied per date, and only writes dates on/after
# BLEND_START_DATE — net-new keywords backfill only from the day RFC-3 first
# ran (v1's "grows forward only" precedent).

BLENDED_SOURCE = "pytrends-blended"
BLEND_START_DATE = "2026-09-28"


@dataclass
class BlendOutcome:
    category_id: str
    status: str  # "ok" | "unavailable"
    reason: str | None = None
    written: int = 0
    skipped_forward: int = 0
    insufficient_days: int = 0
    requests: int = 0


def _batch_daily(df: pd.DataFrame | None, terms: list[str]) -> dict[str, dict[str, float]] | None:
    """date -> {term: value} with isPartial rows dropped; None when unusable."""
    if df is None or df.empty:
        return None
    work = df
    if "isPartial" in work.columns:
        work = work[~work["isPartial"].astype(bool)]
    idx = pd.to_datetime(work.index)
    if len(idx) > 1 and pd.Series(idx).diff().dropna().max() > pd.Timedelta(days=1):
        return None  # non-daily: never stored as daily
    out: dict[str, dict[str, float]] = {}
    for pos, ts in enumerate(idx):
        row = {}
        for t in terms:
            if t in work.columns and not pd.isna(work[t].iloc[pos]):
                row[t] = float(work[t].iloc[pos])
        out[ts.strftime("%Y-%m-%d")] = row
    return out


def chained_daily(narratives: list[dict], today: date, trendreq_factory: Callable | None = None,
                  ) -> tuple[dict[str, dict[str, "pytrends_adapter.ChainedValue"]], int]:
    """date -> keyword -> ChainedValue over the 269-day window, using the same
    batch plan and anchor as the nightly job (anchor = first narrative's
    primary keyword)."""
    from api.data import pytrends_adapter

    keywords = [kw for n in narratives for kw in n["keywords"]]
    anchor = narratives[0]["keywords"][0] if narratives else None
    batches = pytrends_adapter.plan_batches(keywords, anchor)
    if not batches:
        return {}, 0
    anchor = batches[0][0]
    per_batch: list[dict[str, dict[str, float]] | None] = []
    factory = trendreq_factory or _default_trendreq_factory
    for terms in batches:
        try:
            client = factory()
            client.build_payload(list(terms), timeframe=window_timeframe(today))
            per_batch.append(_batch_daily(client.interest_over_time(), terms))
        except Exception:
            per_batch.append(None)
    dates = sorted({d for b in per_batch if b for d in b})
    chained = {
        d: pytrends_adapter.chain_batches([None if b is None else b.get(d) for b in per_batch], batches, anchor)
        for d in dates
    }
    return chained, len(batches)


def run_blended(today: date | None = None, trendreq_factory: Callable | None = None, dry_run: bool = False,
                seeds_path: Path = SEEDS_PATH, start_date: str = BLEND_START_DATE) -> list[BlendOutcome]:
    from api.analytics.narrative import narrative_config
    from api.data import pytrends_adapter

    today = today or datetime.now(timezone.utc).date()
    narratives = narrative_config.load_narratives(seeds_path)
    multi = [n for n in narratives if len(n["keywords"]) >= 2]
    if not multi:
        return []
    chained, requests = chained_daily(narratives, today, trendreq_factory)
    outcomes = []
    for n in multi:
        o = BlendOutcome(n["id"], "ok", requests=requests)
        if not chained:
            o.status, o.reason = "unavailable", "fetch-failed"
            outcomes.append(o)
            continue
        existing = cache.read_narrative_series(BLENDED_SOURCE, n["id"])
        forward: set[str] = set()
        if not existing.empty:
            forward = set(existing.loc[existing["source_status"].astype(str) != BACKFILLED, "date"].astype(str))
        for d, vals in chained.items():
            if d < start_date:
                continue
            cvs = [vals.get(kw) for kw in n["keywords"]]
            if any(cv is None or cv.status != "ok" for cv in cvs):
                o.insufficient_days += 1
                continue
            if d in forward:
                o.skipped_forward += 1
                continue
            if not dry_run:
                cache.write_narrative_point(BLENDED_SOURCE, n["id"], d,
                                            pytrends_adapter.blend([cv.value for cv in cvs]),
                                            source_status=BACKFILLED)
            o.written += 1
        outcomes.append(o)
    return outcomes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    args = parser.parse_args(argv)
    try:
        import pytrends  # noqa: F401
    except Exception:
        print("pytrends is not installed. Run with: uv run --project api --with pytrends python api/scripts/backfill_pytrends_history.py")
        return 1
    outcomes = run(dry_run=args.dry_run)
    print(f"{'category':<12} {'keyword':<24} {'status':<12} {'written':>7} {'skipped':>7} {'partial':>7}  first..last / reason")
    for o in outcomes:
        tail = f"{o.first_date}..{o.last_date}" if o.status == "ok" else o.reason
        print(f"{o.category_id:<12} {str(o.keyword):<24} {o.status:<12} {o.written:>7} {o.skipped_forward:>7} {o.dropped_partial:>7}  {tail}")
    for b in run_blended(dry_run=args.dry_run):
        print(f"blended {b.category_id:<12} {b.status:<12} written={b.written} skipped={b.skipped_forward} "
              f"insufficient-days={b.insufficient_days} requests={b.requests} {b.reason or ''}")
    return 0 if any(o.status == "ok" for o in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
