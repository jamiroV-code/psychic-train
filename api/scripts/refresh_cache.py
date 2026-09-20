"""Manual/cron-triggered cache refresh (ADR-6) — not a queue-backed worker.

Refreshes OHLCV tails for every watchlist symbol + BTC + HYPE, across all
five cached timeframes. Idempotent: `ccxt_adapter.fetch_ohlcv` merges +
dedupes against the existing cache, so running this multiple times a day is
safe (it only ever fetches/merges the tail past the last cached bar's
worth of a fresh `limit`-sized pull).

Run: `uv run python api/scripts/refresh_cache.py`
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

from api.data import ccxt_adapter, watchlist as watchlist_store
from api.data.cache import TIMEFRAMES

BENCHMARK_SYMBOLS = ("BTC", "HYPE")


def refresh_all() -> None:
    symbols = sorted(set(watchlist_store.read_watchlist()) | set(BENCHMARK_SYMBOLS))
    for symbol in symbols:
        for timeframe in TIMEFRAMES:
            result = ccxt_adapter.fetch_ohlcv(symbol, timeframe)
            print(
                f"{symbol:<8} {timeframe:<4} status={result.status:<11} "
                f"bars={len(result.df):<5} insufficient_history={result.insufficient_history}"
            )


if __name__ == "__main__":
    refresh_all()
