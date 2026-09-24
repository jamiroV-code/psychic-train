"""Extract the history LiqTide ships inside one payload into a long-format
parquet (regime dashboard RFC-001).

`latest.json` has no historical endpoint, but each payload carries thinned
history: `tide_series` (weekly `[date, value]` pairs of the published 0-100
index, from 2024-09-04 as of 24-09-26) and one `series` per `metrics.*`
entry (net_liquidity, walcl, tga, rrp, reserves, dollar, stables, btc_dom,
...). This script reads an archived raw payload
(`cache/liqtide/raw/{date}.json`, written by `liqtide_adapter.fetch_latest`)
and writes `cache/liqtide/backfill/{date}.parquet` with columns
`series_key, date, value`:

- `tide_series` rows get `series_key = "tide_value"`;
- `metrics.<key>.series` rows get `series_key = "<key>"`.

A missing or malformed series is skipped, never written as zeros; a point
whose value is not a number is dropped. Idempotent: re-running for the same
source date rewrites the same content.

Run:
  uv run --project api python api/scripts/backfill_liqtide_series.py            # newest raw payload
  uv run --project api python api/scripts/backfill_liqtide_series.py --date 2026-09-24
"""
from __future__ import annotations

# Scripts are run as files, so put the repo root on sys.path first (same
# pattern as the other api/scripts/*).
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse

import pandas as pd

from api.data import cache, liqtide_adapter

# The extraction logic lives in the adapter so analytics can reuse it
# without importing a script; re-exported here under the original names.
BACKFILL_COLUMNS = liqtide_adapter.HISTORY_COLUMNS
TIDE_SERIES_KEY = liqtide_adapter.TIDE_SERIES_KEY
extract_series = liqtide_adapter.extract_history_series


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["series_key", "first", "last", "points"])
    return (
        df.groupby("series_key")["date"]
        .agg(first="min", last="max", points="count")
        .reset_index()
    )


def backfill(date: str | None = None) -> tuple[str, pd.DataFrame] | None:
    dates = cache.list_liqtide_raw_dates()
    if date is None:
        if not dates:
            return None
        date = dates[-1]
    raw = cache.read_liqtide_raw(date)
    if raw is None:
        return None
    df = extract_series(raw)
    if not df.empty:
        cache.write_liqtide_backfill(date, df)
    return date, df


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract LiqTide payload history into a backfill parquet")
    parser.add_argument("--date", help="raw payload date (YYYY-MM-DD); default: newest archived")
    args = parser.parse_args()

    result = backfill(args.date)
    if result is None:
        print("ERROR: no archived raw LiqTide payload found — run snapshot_liqtide.py first.", file=sys.stderr)
        return 1
    date, df = result
    if df.empty:
        print(f"WARN: raw payload {date} carries no history series — nothing written.", file=sys.stderr)
        return 2
    print(f"LiqTide backfill from raw payload {date} -> {cache.liqtide_backfill_path(date)}")
    print(summarize(df).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
