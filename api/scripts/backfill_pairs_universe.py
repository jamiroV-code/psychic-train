"""One-shot deep daily-history fetch for the pair-screener universe (RFC-001).

For every coin in `api/data/pairs_universe.json`, calls the EXISTING public
`ccxt_adapter.fetch_ohlcv(ticker, "1d", since=..., limit=...)` with an
EXPLICIT early `since` - never `since=None`. With `since=None` against an
already-populated cache the adapter either skips the call (warm cache) or
only tops up forward from the newest cached bar, so a shallow cache would
never deepen (feasibility VERDICT, CONCERN-1). An explicit `since` bypasses
both; the adapter merges the result into the existing cache via its own
concat + `write_ohlcv` sort/dedupe path. `ccxt_adapter.py` is not modified.

Defensive pagination: if a raw exchange response comes back with exactly
`DEEP_FETCH_LIMIT` bars, the window may have been capped, so the script
re-fetches from the day after the last returned bar until a page comes back
short, empty, or reaches today.

Prints a per-coin table: status, bars in cache, first and last date, pages.
No CLI arguments (mirrors `backfill_primaries.py`).

Run: `uv run --project api python api/scripts/backfill_pairs_universe.py`
"""
from __future__ import annotations

# Scripts run as files, so put the repo root on sys.path before `api.*`
# imports (same bootstrap as backfill_primaries.py).
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from api.data import ccxt_adapter  # noqa: E402
from api.data.pairs_universe import load_universe  # noqa: E402

# 2020-01-01T00:00:00Z - predates every Hyperliquid listing (user decision, Stage 0).
DEEP_FETCH_SINCE_MS = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
DEEP_FETCH_LIMIT = 5000
DAY_MS = 86_400_000
# Hard stop on runaway pagination: 20 pages x 5000 daily bars is ~270 years.
MAX_PAGES = 20


class RecordingExchange:
    """Thin proxy over a ccxt exchange that records each raw response.

    The adapter returns the merged cache, not the raw page, so the script
    cannot otherwise see whether a single response was capped. Every other
    attribute (markets, id, ...) is delegated unchanged.
    """

    def __init__(self, inner):
        self._inner = inner
        self.last_raw: list | None = None

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=None):
        self.last_raw = None
        raw = self._inner.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        self.last_raw = raw
        return raw

    def __getattr__(self, name):
        return getattr(self._inner, name)


@dataclass
class CoinResult:
    ticker: str
    status: str
    bars: int
    first: str
    last: str
    pages: int
    capped_pages: int


def _now_ms() -> int:
    return int(time.time() * 1000)


def backfill_coin(ticker: str, exchange, now_ms: int | None = None) -> CoinResult:
    """Deep-fetch one ticker from `DEEP_FETCH_SINCE_MS`, paging on a capped response."""
    now_ms = _now_ms() if now_ms is None else now_ms
    proxy = RecordingExchange(exchange)
    since = DEEP_FETCH_SINCE_MS
    pages = capped = 0
    result = None
    while pages < MAX_PAGES:
        result = ccxt_adapter.fetch_ohlcv(
            ticker, "1d", since=since, limit=DEEP_FETCH_LIMIT, exchange=proxy
        )
        pages += 1
        raw = proxy.last_raw
        if result.status != "ok" or not raw:
            break
        if len(raw) < DEEP_FETCH_LIMIT:
            break
        capped += 1
        next_since = int(raw[-1][0]) + DAY_MS
        if next_since <= since or next_since > now_ms:
            break
        since = next_since

    df = result.df
    if df.empty:
        first = last = "n/a"
    else:
        first = str(df["timestamp"].min().date())
        last = str(df["timestamp"].max().date())
    return CoinResult(ticker, result.status, len(df), first, last, pages, capped)


def backfill_all(exchange=None, coins: list[str] | None = None) -> list[CoinResult]:
    coins = load_universe() if coins is None else coins
    if exchange is None:
        exchange = ccxt_adapter._exchange()
        if exchange is None:
            print("Hyperliquid market list unavailable - nothing fetched.")
            return []
    results = []
    print(f"{'coin':<6} {'status':<11} {'bars':>5} {'first':<10} {'last':<10} pages capped")
    for ticker in coins:
        r = backfill_coin(ticker, exchange)
        results.append(r)
        flag = "  <-- a page hit the cap" if r.capped_pages else ""
        print(
            f"{r.ticker:<6} {r.status:<11} {r.bars:>5} {r.first:<10} {r.last:<10} "
            f"{r.pages:>5} {r.capped_pages:>6}{flag}"
        )
    return results


if __name__ == "__main__":
    backfill_all()
