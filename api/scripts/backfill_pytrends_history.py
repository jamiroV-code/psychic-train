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
SEEDS_PATH = Path(__file__).resolve().parents[1] / "data" / "narrative_categories.json"


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
    seeds = json.loads(path.read_text(encoding="utf-8"))["seed_categories"]
    return [(s["id"], (s.get("keywords") or [None])[0]) for s in seeds]


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
    return 0 if any(o.status == "ok" for o in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
