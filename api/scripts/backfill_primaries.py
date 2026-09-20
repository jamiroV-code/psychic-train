"""One-shot cache warmer for the 5 primary FRED series (ADR-2 / RFC-002).

Fetches full history for WALCL, TGA, RRP, RESERVES and BROAD_DOLLAR through
the existing keyless `fredgraph.csv` path and writes each to
`cache/liquidity/{series_id}.parquet`. Idempotent: `fred_adapter.fetch_series`
is cache-first (6h TTL) and overwrites the series file per refresh, so running
this repeatedly is safe.

No CLI arguments: the CSV export always returns FULL history (there is no
date filtering to expose), and FRED is the only source here.

Run: `uv run python api/scripts/backfill_primaries.py`
"""
from __future__ import annotations

# Scripts are run as files (`python api/scripts/<name>.py`), so `sys.path[0]`
# is this directory, not the repo root, and `import api.*` cannot resolve.
# `pythonpath = [".."]` in pyproject.toml is a pytest setting and does not
# apply here. Put the repo root on the path before importing anything from
# `api`, so the script works from any working directory.
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from api.data import fred_adapter

PRIMARY_SERIES = {
    "walcl": fred_adapter.WALCL,
    "tga": fred_adapter.TGA,
    "rrp": fred_adapter.RRP,
    "reserves": fred_adapter.RESERVES,
    "dollar_broad": fred_adapter.BROAD_DOLLAR,
}


def _coverage(df) -> tuple[str, str]:
    if df.empty:
        return "n/a", "n/a"
    return str(df["date"].min().date()), str(df["date"].max().date())


def backfill_all() -> None:
    for label, series_id in PRIMARY_SERIES.items():
        result = fred_adapter.fetch_series(series_id)
        first, last = _coverage(result.df)
        print(
            f"{label:<13} {series_id:<10} status={result.status:<11} "
            f"rows={len(result.df):<6} first={first:<10} last={last}"
        )


if __name__ == "__main__":
    backfill_all()
