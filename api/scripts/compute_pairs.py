"""Precompute pair-screener statistics (cointegration-screener RFC-003, ADR-8 Amendment).

Reads the current `api/data/pairs_universe.json` and the cached daily OHLCV
(`cache.read_ohlcv` only — no network), computes every pair, and writes
`api/data/cache/pairs/{spreads/, results.parquet, provenance.json}`.
The API only reads these files; it never computes on request.

Run after `backfill_pairs_universe.py`, and again whenever the universe or
the price cache changes (the API reports `stale` until you do).
No CLI arguments; safe to re-run.

Run: `uv run --project api python api/scripts/compute_pairs.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from api.analytics.cointegration import pairs_response  # noqa: E402
from api.data import cache  # noqa: E402


def main() -> int:
    s = pairs_response.compute_and_persist()
    print(f"pairs computed: {s.pair_count} in {s.elapsed_s:.1f} s")
    for status, n in s.status_counts.items():
        print(f"  {status:22s} {n}")
    print(f"  {'not_mean_reverting':22s} {s.not_mean_reverting}  (within ok)")
    print(f"  {'johansen_refused':22s} {s.johansen_refused}  (within ok)")
    print(f"BH-adjusted EG p < 0.05: {s.bh_significant_05}")
    print(f"written: {cache.pairs_results_path()}")
    print(f"         {cache.pairs_provenance_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
