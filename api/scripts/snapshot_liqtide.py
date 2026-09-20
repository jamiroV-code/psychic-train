"""Daily LiqTide snapshot + payload verifier.

Why a schedule matters: LiqTide publishes only `latest.json` — there is no
historical endpoint. A day that is never fetched is gone forever, and the
archive under `api/data/cache/liqtide/` is the only place that day's
composite will ever exist (Standing Rule 8, `data-sources/all-data-sources.md`).
Every gap in that archive is a permanent hole in the full composite's history.

This script does not write the cache itself — `liqtide_adapter.fetch_latest`
already owns the append-only archive write. `--verify-only` simply runs that
same fetch with `dry_run=True`, so a live payload can be inspected and its
arithmetic checked without touching the archive.

Run:
  uv run --project api python api/scripts/snapshot_liqtide.py
  uv run --project api python api/scripts/snapshot_liqtide.py --coverage
  uv run --project api python api/scripts/snapshot_liqtide.py --verify-only

Exit codes: 0 clean, 1 fetch/write failed (unavailable), 2 archived but flagged.
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

import argparse

import pandas as pd

from api.data import cache, liqtide_adapter

# Hand-verified against the live payload 2026-09-20 — used only as a fallback
# when the payload omits a published weight for a component, so that a missing
# weight is never silently treated as zero.
WEIGHTS = {
    "net_liquidity_4w": 0.30, "stablecoin_7d": 0.25, "dollar_1m": 0.15,
    "rrp_release_4w": 0.10, "etf_flow_5d": 0.10, "rotation_30d": 0.10,
}

WEIGHT_SUM_TOLERANCE = 0.001
SCORE_TOLERANCE = 1  # published value is an integer 0-100; allow 1 for rounding


def check_arithmetic(raw: dict) -> list[str]:
    """Re-derive the published tide index from its own components/weights.

    Catches an upstream inconsistency (published score not matching the
    components it claims to be built from) rather than trusting the headline
    number. Only meaningful on a fresh live payload — a cache-replay payload
    has no `raw`.
    """
    problems: list[str] = []

    tide_index = raw.get("tide_index") or {}
    components = tide_index.get("components") or {}
    weights = tide_index.get("weights") or {}
    published = tide_index.get("value")

    missing = [k for k in WEIGHTS if k not in components]
    if missing:
        problems.append(f"tide_index.components missing expected key(s): {', '.join(sorted(missing))}")

    if weights:
        total = sum(v for v in weights.values() if isinstance(v, (int, float)))
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            problems.append(f"published weights sum to {total:.4f}, expected ~1.0")

    if not missing and isinstance(published, (int, float)):
        score = sum(
            (weights.get(k) if isinstance(weights.get(k), (int, float)) else WEIGHTS[k]) * components[k]
            for k in WEIGHTS
        )
        recomputed = max(0, min(100, round(50 + 50 * score)))
        if abs(recomputed - published) > SCORE_TOLERANCE:
            problems.append(
                f"tide_index.value {published} does not match recomputation {recomputed} "
                f"from its own components/weights"
            )
    elif not missing:
        problems.append("tide_index.value missing or non-numeric — cannot verify published score")

    quality = raw.get("data_quality")
    if quality != "live":
        problems.append(f"data_quality is {quality!r}, not 'live'")

    return problems


def check_coverage(history: pd.DataFrame) -> list[str]:
    """Report how complete the local archive is: per-column non-null counts
    and calendar gaps between archived days. Inspection output, not a gate.
    """
    problems: list[str] = []

    if history is None or history.empty:
        print("liqtide archive: EMPTY — no payloads captured yet.")
        problems.append("archive is empty — no LiqTide days captured")
        return problems

    total = len(history)
    print(f"liqtide archive: {total} archived day(s)")

    for column in ("tide_score", *liqtide_adapter.METRIC_KEYS):
        if column not in history.columns:
            print(f"  {column:<16} MISSING COLUMN")
            problems.append(f"archive has no {column!r} column")
            continue
        present = int(history[column].notna().sum())
        print(f"  {column:<16} {present}/{total} non-null")
        if present < total:
            problems.append(f"{column}: {total - present} archived day(s) have no value")

    dates = sorted(set(pd.to_datetime(history["date"], utc=True, errors="coerce").dt.date.dropna()))
    if len(dates) < 2:
        print("  gaps            n/a (fewer than 2 archived days)")
        return problems

    gaps = [
        (previous, current, (current - previous).days)
        for previous, current in zip(dates, dates[1:])
        if (current - previous).days > 1
    ]
    print(f"  date range      {dates[0]} -> {dates[-1]}")
    if not gaps:
        print("  gaps            none (consecutive daily coverage)")
        return problems

    worst = max(gaps, key=lambda g: g[2])
    print(f"  gaps            {len(gaps)} (worst: {worst[2]} days, {worst[0]} -> {worst[1]})")
    problems.append(f"{len(gaps)} gap(s) in daily coverage, worst {worst[2]} days ({worst[0]} -> {worst[1]})")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily LiqTide snapshot + payload verifier")
    parser.add_argument("--coverage", action="store_true",
                        help="inspect the local archive's completeness; no fetch, always exits 0")
    parser.add_argument("--verify-only", action="store_true",
                        help="fetch and verify a live payload without writing it to the archive")
    args = parser.parse_args()

    if args.coverage:
        check_coverage(cache.read_liqtide_history())
        return 0

    payload = liqtide_adapter.fetch_latest(dry_run=args.verify_only)

    if payload.status == "unavailable":
        print("ERROR: LiqTide fetch failed and no archived payload exists.", file=sys.stderr)
        return 1

    problems: list[str] = []
    if payload.raw is not None:
        problems.extend(check_arithmetic(payload.raw))
    elif args.verify_only:
        problems.append("no fresh payload — nothing to verify (live fetch failed; served from archive)")

    mode = "verify-only (no archive write)" if args.verify_only else "archived"
    print(f"LiqTide snapshot [{mode}]")
    print(f"  date            {payload.date}")
    print(f"  generated_utc   {payload.generated_utc}")
    print(f"  status          {payload.status}")
    print(f"  tide_score      {payload.tide_score}")
    if payload.raw is not None:
        tide_index = payload.raw.get("tide_index") or {}
        print(f"  tide_index      value={tide_index.get('value')} label={tide_index.get('label')!r}")
        print(f"  regime          {payload.raw.get('regime')!r}")

    if payload.status == "stale":
        problems.append(f"payload is stale (older than {liqtide_adapter.STALENESS_HOURS}h)")

    for problem in problems:
        print(f"WARN: {problem}", file=sys.stderr)

    return 2 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
