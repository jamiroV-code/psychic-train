"""Seed a throwaway Parquet cache for the Playwright E2E. Writes nothing live.

Run by `web/playwright.config.ts` immediately before uvicorn starts, with
`SCREENER_CACHE_ROOT` and `SCREENER_WATCHLIST_PATH` pointing at a temp tree.

Why seeding rather than mocking: the E2E exists to cover the boundaries the
unit suites structurally cannot — the real client, real CORS, real FastAPI
routing, real adapter, real DuckDB read. Intercepting HTTP in the browser
would test the UI against a fixture of what we *believe* the API returns,
which is the same mistake the vitest suites already make by injecting
`fetchBoard`. So every layer stays real and only the exchange is absent.

The exchange is absent because the seeded bars are FRESH: `fetch_ohlcv`'s
cache-fresh check now runs above exchange construction, so a warm cache is
served without a market list being loaded. The bars are therefore anchored to
*now*, not to a fixed date — a fixture ending last Tuesday would be stale and
the API would reach for the network.

Safety: refuses to run unless `SCREENER_CACHE_ROOT` is set AND differs from
`cache.DEFAULT_CACHE_ROOT`. Three live-data incidents in two days (the
watchlist deletion, the cache-writing tests, the weekly overwrite) is enough
to justify an explicit guard rather than a convention.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd

# Symbols. BTC and HYPE are the two benchmark candidates and must exist
# whichever way the regime switch falls; THIN deliberately carries fewer than
# MIN_BARS_REQUIRED bars so the "not enough history" path is exercised.
WATCHLIST = ["BTC", "ETH", "THIN"]
BENCHMARKS = ["BTC", "HYPE"]
THIN_SYMBOL = "THIN"

# 500 daily bars is chosen, not arbitrary: `1w` is derived from `1d`, and
# MIN_BARS_REQUIRED is 60, so the weekly series needs >= 60 weeks behind it or
# every panel reports insufficient history and the board proves nothing.
BAR_COUNTS = {"15m": 120, "1h": 120, "4h": 120, "1d": 500}
THIN_BAR_COUNT = 20  # below MIN_BARS_REQUIRED (60) on purpose

FLOOR_FREQ = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "D"}
STEP = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "D"}

MANIFEST_PATH = _REPO_ROOT / "web" / "e2e" / ".fixture-manifest.json"


def _guard() -> Path:
    from api.data import cache

    raw = os.environ.get("SCREENER_CACHE_ROOT")
    if not raw:
        sys.exit(
            "REFUSING: SCREENER_CACHE_ROOT is not set.\n"
            "Without it this would seed fixture bars into the real cache and "
            "overwrite live market data."
        )
    root = Path(raw).resolve()
    if root == cache.DEFAULT_CACHE_ROOT.resolve():
        sys.exit(
            f"REFUSING: SCREENER_CACHE_ROOT points at the real cache ({root}).\n"
            "Point it somewhere disposable."
        )
    return root


def _bars(timeframe: str, count: int, base: float) -> pd.DataFrame:
    """A deterministic rising series whose newest bar is the current, still-open
    one for this timeframe — so `_cache_is_fresh` is True and no exchange is
    contacted."""
    end = pd.Timestamp.now(tz="UTC").floor(FLOOR_FREQ[timeframe])
    idx = pd.date_range(end=end, periods=count, freq=STEP[timeframe], tz="UTC")
    n = range(count)
    return pd.DataFrame(
        {
            "timestamp": idx,
            "open": [base + i for i in n],
            "high": [base + i + 5 for i in n],
            "low": [base + i - 5 for i in n],
            "close": [base + i + 1 for i in n],
            "volume": [1000 + i for i in n],
            "source": ["e2e-fixture"] * count,
        }
    )


def main() -> int:
    root = _guard()
    from api.data import cache, watchlist as watchlist_store

    if root.exists():
        shutil.rmtree(root)
    cache.bootstrap_cache_dirs()

    written: dict[str, dict[str, int]] = {}
    for offset, symbol in enumerate(sorted(set(WATCHLIST) | set(BENCHMARKS))):
        written[symbol] = {}
        for timeframe, count in BAR_COUNTS.items():
            bars = THIN_BAR_COUNT if symbol == THIN_SYMBOL else count
            df = _bars(timeframe, bars, base=100.0 + offset * 1000)
            cache.write_ohlcv(symbol, timeframe, df)
            written[symbol][timeframe] = bars
        # `1w` is deliberately NOT seeded. It is derived from `1d` on request,
        # which is what makes the Monday-anchor assertion (ADR-5/ADR-6) an
        # end-to-end one rather than a check of whatever we wrote here.

    watchlist_path = os.environ.get("SCREENER_WATCHLIST_PATH")
    if watchlist_path:
        Path(watchlist_path).parent.mkdir(parents=True, exist_ok=True)
        # `watchlist.py::_load_raw` expects `{"coins": [...]}`, not a bare
        # array — it calls `data.setdefault("coins", [])` on whatever
        # `json.load` returns, which raises `AttributeError: 'list' object
        # has no attribute 'setdefault'` on a bare list. That exception fires
        # on `build_screener_board`'s very first line (`read_watchlist()`),
        # before any per-coin or per-timeframe code runs — which is why
        # every board request 500'd identically regardless of `timeframe`.
        Path(watchlist_path).write_text(json.dumps({"coins": WATCHLIST}), encoding="utf-8")
    else:
        print("WARNING: SCREENER_WATCHLIST_PATH unset — the API will read the real watchlist.")

    manifest = {
        "cache_root": str(root),
        "watchlist": WATCHLIST,
        "benchmarks": BENCHMARKS,
        "thin_symbol": THIN_SYMBOL,
        "min_bars_required": 60,
        "bars_written": written,
        "seeded_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"seeded {len(written)} symbols into {root}")
    print(f"watchlist  {WATCHLIST} -> {watchlist_path or '(not set)'}")
    print(f"manifest   {MANIFEST_PATH}")
    print(f"store path {watchlist_store.DEFAULT_WATCHLIST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
