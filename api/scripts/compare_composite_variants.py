"""Do the full and reduced liquidity composites find the same leg boundaries?

The reduced composite is the only variant with historical depth, so every
pre-2024 backtest (2017, 2020-21) is built on it alone. The full composite is
only computable from `liquidity_composite.CUTOVER_DATE` (2024-01-11) onward.
This script runs both over the one window where both exist, detects and
confirms leg boundaries with each, and reports whether they agree.

That is the only available evidence on whether the reduced composite is a
faithful stand-in for the full one. If they disagree here, the historical
backtests are measuring the reduced composite's behavior, not the full
composite's — which is exactly the question this script exists to answer.

Diagnostic, not a gate: it always exits 0 and the verdict is for human review.

Run (from inside `api/`): `uv run python scripts/compare_composite_variants.py`
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Standalone-script bootstrap: a plain `python scripts/<name>.py` invocation
# only puts this script's own directory on sys.path, so `from api...` fails
# with ModuleNotFoundError regardless of cwd (pyproject's pytest `pythonpath`
# does not apply here). Insert the project root explicitly.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd

from api.analytics.regime import leg_boundary, liquidity_composite
from api.data import ccxt_adapter

REPORT_DIR = _PROJECT_ROOT / "process" / "general-plans" / "active" / "liqtide-snapshot-tooling_20-09-26"

# Reuses the same confirmation window `confirm_boundaries` itself already uses
# to decide whether a price-structure pivot counts as confirming a candidate —
# applying a tighter or looser number here would imply the two composites need
# a different definition of "same event" than the codebase already uses for
# boundary confirmation, which has no basis.
AGREEMENT_TOLERANCE_DAYS = leg_boundary.CONFIRMATION_WINDOW_DAYS


def _confirmed_dates(composite, btc_df: pd.DataFrame | None) -> tuple[list[pd.Timestamp], int, str | None]:
    """Detect + confirm boundaries for one composite variant.

    Returns (confirmed candidate dates, candidate count, skip note).
    """
    if not composite.available:
        return [], 0, f"{composite.variant} composite unavailable for this window — no detection possible."

    candidates = leg_boundary.detect_candidate_boundaries(composite.series)
    if btc_df is None or btc_df.empty:
        return [], len(candidates), "BTC price history unavailable — candidates detected but none confirmable."

    confirmations = leg_boundary.confirm_boundaries(candidates, btc_df)
    return [c.candidate_date for c in confirmations if c.confirmed], len(candidates), None


def _match(left: list[pd.Timestamp], right: list[pd.Timestamp]) -> tuple[list[tuple], list, list]:
    """Pair each left date with the nearest right date inside the tolerance.

    Greedy nearest-first, each date usable once, so a single date can never
    account for two matches on the other side.
    """
    tolerance = pd.Timedelta(days=AGREEMENT_TOLERANCE_DAYS)
    remaining = list(right)
    matched: list[tuple] = []
    left_unmatched: list = []

    for left_date in left:
        candidates = [(abs(left_date - r), r) for r in remaining if abs(left_date - r) <= tolerance]
        if not candidates:
            left_unmatched.append(left_date)
            continue
        delta, best = min(candidates, key=lambda p: p[0])
        remaining.remove(best)
        matched.append((left_date, best, delta.days))

    return matched, left_unmatched, remaining


def _verdict(matched: list, full_unmatched: list, reduced_unmatched: list,
             full_count: int, reduced_count: int) -> str:
    if full_count == 0 and reduced_count == 0:
        return "DISAGREE"
    if matched and not full_unmatched and not reduced_unmatched:
        return "AGREE"
    if matched:
        return "PARTIAL"
    return "DISAGREE"


def _iso(ts) -> str:
    return pd.Timestamp(ts).date().isoformat()


def run_comparison() -> dict:
    window = (liquidity_composite.CUTOVER_DATE, pd.Timestamp.now(tz="utc"))
    start, end = window

    full = liquidity_composite.build_full_composite(date_range=window)
    reduced = liquidity_composite.build_reduced_composite(date_range=window)

    btc_result = ccxt_adapter.fetch_ohlcv("BTC", "1d")
    btc_df = btc_result.df
    # `timestamp` confirmed as the column name from `cache.OHLCV_COLUMNS` and
    # from `leg_boundary.confirm_boundaries`, which sorts on it directly.
    if btc_df is not None and not btc_df.empty:
        btc_df = btc_df[(btc_df["timestamp"] >= start) & (btc_df["timestamp"] <= end)]

    full_dates, full_candidates, full_note = _confirmed_dates(full, btc_df)
    reduced_dates, reduced_candidates, reduced_note = _confirmed_dates(reduced, btc_df)

    matched, full_unmatched, reduced_unmatched = _match(full_dates, reduced_dates)
    verdict = _verdict(matched, full_unmatched, reduced_unmatched, len(full_dates), len(reduced_dates))

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "window": [_iso(start), _iso(end)],
        "tolerance_days": AGREEMENT_TOLERANCE_DAYS,
        "btc_history_points": int(len(btc_df)) if btc_df is not None else 0,
        "btc_status": btc_result.status,
        "full": {
            "available": full.available,
            "points": int(len(full.series)),
            "candidates": full_candidates,
            "confirmed": [_iso(d) for d in full_dates],
            "note": full_note,
        },
        "reduced": {
            "available": reduced.available,
            "points": int(len(reduced.series)),
            "candidates": reduced_candidates,
            "confirmed": [_iso(d) for d in reduced_dates],
            "note": reduced_note,
        },
        "matched_pairs": [
            {"full": _iso(f), "reduced": _iso(r), "days_apart": days} for f, r, days in matched
        ],
        "full_only_unmatched": [_iso(d) for d in full_unmatched],
        "reduced_only_unmatched": [_iso(d) for d in reduced_unmatched],
        "verdict": verdict,
    }


def write_report(result: dict) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"composite-variant-agreement-{ts}.json"
    # Atomic write (same reason as backtest_leg_boundaries.write_report): a
    # process death mid-write can otherwise leave a truncated file sitting at
    # the real report name.
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(result, indent=2))
    tmp_path.replace(path)
    return path


def main() -> None:
    argparse.ArgumentParser(
        description="Compare full vs reduced liquidity-composite leg boundaries"
    ).parse_args()

    result = run_comparison()
    path = write_report(result)

    full, reduced = result["full"], result["reduced"]
    print(f"Window: {result['window'][0]} -> {result['window'][1]} "
          f"(tolerance {result['tolerance_days']} days, BTC bars {result['btc_history_points']})")
    print(f"  full    available={full['available']} points={full['points']} "
          f"candidates={full['candidates']} confirmed={full['confirmed']}")
    if full["note"]:
        print(f"          note: {full['note']}")
    print(f"  reduced available={reduced['available']} points={reduced['points']} "
          f"candidates={reduced['candidates']} confirmed={reduced['confirmed']}")
    if reduced["note"]:
        print(f"          note: {reduced['note']}")
    print(f"  matched pairs:          {result['matched_pairs']}")
    print(f"  full-only unmatched:    {result['full_only_unmatched']}")
    print(f"  reduced-only unmatched: {result['reduced_only_unmatched']}")
    print(f"VERDICT: {result['verdict']}")
    print(f"Report written to {path}")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
