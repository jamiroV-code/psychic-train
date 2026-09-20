"""Report the week anchor of every cached `1w` series (ADR-5 verification).

The unit tests prove `_derive_weekly_from_daily`'s arithmetic against a
fixture. They deliberately run against an isolated cache, so they say nothing
about the *live* Parquet files under `api/data/cache/ohlcv/`. Those were
written by the pre-ADR-5 code with Sunday labels and are expected to
self-heal on the next board request, because `cache.write_ohlcv` overwrites
the whole series. This script is how that prediction gets checked instead of
assumed.

Usage (from the repo root):

    uv run --project api python api/scripts/check_weekly_anchor.py

Weekdays are evaluated IN UTC (`pd.to_datetime(..., utc=True)`), deliberately:
an exchange weekly open is Monday 00:00 UTC, and Monday 00:00 in a local
timezone is Sunday 22:00/23:00 UTC. Before ADR-6 this script reported `Sun`
while a local-weekday reading of the same file said `Mon` — this one was right.

Exit code 0 when every cached weekly series is Monday-anchored and no bar is
stamped in the future; 1 otherwise. Safe to re-run — it only reads.
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

import pandas as pd

from api.data import cache

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def main() -> int:
    ohlcv_root = cache.CACHE_ROOT / "ohlcv"
    if not ohlcv_root.exists():
        print(f"no cache at {ohlcv_root} — nothing to check")
        return 0

    now = pd.Timestamp.now(tz="UTC")
    symbols = sorted(p.name for p in ohlcv_root.iterdir() if p.is_dir())
    if not symbols:
        print(f"no symbols cached under {ohlcv_root}")
        return 0

    failures: list[str] = []
    print(f"{'symbol':<8} {'bars':>5}  {'oldest':<12} {'newest':<12} {'labels':<12} verdict")
    print("-" * 70)

    for symbol in symbols:
        df = cache.read_ohlcv(symbol, "1w")
        if df.empty:
            print(f"{symbol:<8} {0:>5}  {'-':<12} {'-':<12} {'-':<12} no 1w cache yet")
            continue

        stamps = pd.to_datetime(df["timestamp"], utc=True)
        weekdays = sorted(stamps.dt.dayofweek.unique().tolist())
        label_desc = "/".join(WEEKDAY_NAMES[d] for d in weekdays)
        newest = stamps.max()

        problems = []
        if weekdays != [0]:
            problems.append(f"not Monday-anchored ({label_desc})")
        if newest > now:
            problems.append(f"newest bar {newest:%Y-%m-%d} is in the future")

        verdict = "OK" if not problems else "; ".join(problems)
        if problems:
            failures.append(f"{symbol}: {verdict}")

        print(
            f"{symbol:<8} {len(df):>5}  {stamps.min():%Y-%m-%d}   {newest:%Y-%m-%d}   "
            f"{label_desc:<12} {verdict}"
        )

    print()
    if failures:
        print("STALE — these series still carry pre-ADR-5 labels:")
        for line in failures:
            print(f"  - {line}")
        print(
            "\nThis is expected until the API process is restarted and a board request\n"
            "re-derives them. Restart uvicorn, hit /api/screener/board, re-run this script."
        )
        return 1

    print("All cached weekly series are Monday-anchored with no future-dated bars (ADR-5).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
