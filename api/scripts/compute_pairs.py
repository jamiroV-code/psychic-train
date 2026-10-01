"""Precompute pair-screener statistics (cointegration-screener RFC-003, ADR-8 Amendment).

Reads the current `api/data/pairs_universe.json` and the cached daily OHLCV
(`cache.read_ohlcv` only — no network), computes every pair, and writes
`api/data/cache/pairs/{spreads/, results.parquet, provenance.json}`.
The API only reads these files; it never computes on request.

Run after `backfill_pairs_universe.py`, and again whenever the universe or
the price cache changes (the API reports `stale` until you do).
No CLI arguments; safe to re-run.

Exit codes: 0 = at least one pair computed `ok`; 2 = ran but no pair was ok
(covers `pair_count == 0`, all `coin_unavailable`, all `insufficient_overlap`
— the workflow warns); 1 = unexpected crash.

Run: `uv run --project api python -m api.scripts.compute_pairs`
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse  # noqa: E402
import time  # noqa: E402
from typing import Callable  # noqa: E402

from api.analytics.cointegration import pairs_response  # noqa: E402
from api.data import cache  # noqa: E402


def exit_code(summary) -> int:
    """0 when at least one pair is `ok`, else 2 (C2)."""
    return 0 if summary.status_counts.get("ok", 0) >= 1 else 2


def main(argv: list[str] | None = None, *, sleep: Callable[[float], None] = time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # `[] if argv is None else argv` so a bare `main()` under pytest never
    # consumes pytest's own sys.argv (C5).
    parser.parse_args([] if argv is None else argv)
    s = pairs_response.compute_and_persist()
    print(f"pairs computed: {s.pair_count} in {s.elapsed_s:.1f} s")
    for status, n in s.status_counts.items():
        print(f"  {status:22s} {n}")
    print(f"  {'not_mean_reverting':22s} {s.not_mean_reverting}  (within ok)")
    print(f"  {'johansen_refused':22s} {s.johansen_refused}  (within ok)")
    print(f"BH-adjusted EG p < 0.05: {s.bh_significant_05}")
    print(f"written: {cache.pairs_results_path()}")
    print(f"         {cache.pairs_provenance_path()}")
    return exit_code(s)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # pragma: no cover
        print(f"compute_pairs: fatal: {exc!r}", file=sys.stderr)
        sys.exit(1)
