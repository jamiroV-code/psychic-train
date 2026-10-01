"""Scheduled/manual cache refresh (ADR-6) — not a queue-backed worker.

Refreshes OHLCV tails for every watchlist symbol + BTC + HYPE, across all
five cached timeframes, and additionally every pair-screener universe coin
that is NOT already in that set on `1d` only (pipeline-completeness D7 — the
only timeframe `compute_pairs` reads; `1w` is derived from `1d`). Idempotent:
`ccxt_adapter.fetch_ohlcv` merges + dedupes against the existing cache, so
running this multiple times a day is safe (it only ever fetches/merges the
tail past the last cached bar's worth of a fresh `limit`-sized pull).

Side effect worth knowing (D7): `/pairs` provenance compares per-coin bar
counts, so after ANY run of this script `/pairs` reads `stale` until
`compute_pairs.py` runs. See `api/scripts/BOOTSTRAP.md`.

Exit codes: 0 = at least one (symbol, timeframe) fetch was ok with full
history; 2 = ran but nothing qualified (workflow warns); 1 = unexpected
crash, or every item raised.

Run: `uv run --project api python -m api.scripts.refresh_cache`
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

import argparse  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Callable  # noqa: E402

from api.data import ccxt_adapter, watchlist as watchlist_store  # noqa: E402
from api.data.cache import TIMEFRAMES  # noqa: E402
from api.data.pairs_universe import UniverseFileError, load_universe  # noqa: E402

BENCHMARK_SYMBOLS = ("BTC", "HYPE")
# The only timeframe `compute_pairs` reads. Universe-only coins get this one.
UNIVERSE_TIMEFRAMES = ("1d",)
# No rate tuning in this plan (SPEC puts it out of scope); kept injectable so
# a future change is a one-constant edit and the tests stay instant.
REQUEST_SPACING_SECONDS = 0.0


@dataclass
class FetchSummary:
    symbol: str
    timeframe: str
    ok: bool
    status: str
    bars: int = 0
    insufficient_history: bool = False

    def line(self) -> str:
        return (
            f"{self.symbol:<8} {self.timeframe:<4} status={self.status:<11} "
            f"bars={self.bars:<5} insufficient_history={self.insufficient_history}"
        )


def _summary(symbol: str, timeframe: str, result) -> FetchSummary:
    """E4: `ok` means a usable full-history fetch — `insufficient_history`
    does not count, so the Public Contracts table and `exit_code` agree."""
    return FetchSummary(
        symbol=symbol,
        timeframe=timeframe,
        ok=result.status == "ok" and not result.insufficient_history,
        status=result.status,
        bars=len(result.df),
        insufficient_history=bool(result.insufficient_history),
    )


def _plan_fetches() -> tuple[list[tuple[str, str]], list[FetchSummary]]:
    """(symbol, timeframe) work list, plus any summaries for config failures."""
    failures: list[FetchSummary] = []
    base = sorted(set(watchlist_store.read_watchlist()) | set(BENCHMARK_SYMBOLS))
    work = [(symbol, tf) for symbol in base for tf in TIMEFRAMES]

    try:
        universe = load_universe()
    except UniverseFileError as exc:
        # A broken universe file must never take the watchlist refresh down.
        failures.append(FetchSummary("universe", "-", ok=False, status="error"))
        print(f"universe unavailable: {exc!r}", file=sys.stderr)
        universe = []

    extra = sorted(set(universe) - set(base))
    work.extend((symbol, tf) for symbol in extra for tf in UNIVERSE_TIMEFRAMES)
    return work, failures


def run_refresh(
    *,
    sleep: Callable[[float], None] = time.sleep,
    spacing: float = REQUEST_SPACING_SECONDS,
) -> list[FetchSummary]:
    """Fetch every planned (symbol, timeframe). Per-item isolated: an
    exception records `status="error"` and the run continues."""
    work, summaries = _plan_fetches()
    for symbol, timeframe in work:
        try:
            result = ccxt_adapter.fetch_ohlcv(symbol, timeframe)
        except Exception as exc:  # per-item isolation (C3)
            summaries.append(FetchSummary(symbol, timeframe, ok=False, status="error"))
            print(f"{symbol:<8} {timeframe:<4} status=error      {exc!r}", file=sys.stderr)
        else:
            summaries.append(_summary(symbol, timeframe, result))
        if spacing:
            sleep(spacing)
    return summaries


def exit_code(summaries: list[FetchSummary]) -> int:
    if summaries and all(s.status == "error" for s in summaries):
        return 1
    if any(s.ok for s in summaries):
        return 0
    return 2


def refresh_all() -> list[FetchSummary]:
    """Thin back-compat wrapper (no importers today; keeps the old name)."""
    return run_refresh()


def main(argv: list[str] | None = None, *, sleep: Callable[[float], None] = time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # `[] if argv is None else argv` so a bare `main()` under pytest never
    # consumes pytest's own sys.argv (C5).
    parser.parse_args([] if argv is None else argv)
    summaries = run_refresh(sleep=sleep)
    for s in summaries:
        print(s.line())
    return exit_code(summaries)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # pragma: no cover
        print(f"refresh_cache: fatal: {exc!r}", file=sys.stderr)
        sys.exit(1)
