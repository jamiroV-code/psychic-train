"""CoinGecko attention source: top-100 reference list and daily volume series.

Thin fetchers kept here; `coingecko_adapter` is wrapped (trending), never edited.
Daily 24h-volume from `market_chart` is the stored attention proxy (completed
UTC days only; the store drops today).
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone

import httpx

from api.data import coingecko_adapter
from api.data.attention.types import MIN_HISTORY_DAYS, SourceSeries

MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
CHART_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0
TIMEOUT_SECONDS = 10.0

# Excluded from the D-3 reference universe (stablecoins, wrapped/staked wrappers).
STABLECOIN_SYMBOLS = frozenset({"USDT", "USDC", "DAI", "USDE", "FDUSD", "TUSD", "USDD", "PYUSD", "USDS", "USD1"})
WRAPPED_SYMBOLS = frozenset({"WBTC", "WETH", "STETH", "WSTETH", "WEETH", "CBBTC", "WBETH", "BSC-USD", "WBNB"})


def _get(client: httpx.Client, url: str, params: dict, sleep) -> httpx.Response | None:
    resp = None
    for attempt in range(MAX_RETRIES):
        resp = client.get(url, params=params, timeout=TIMEOUT_SECONDS)
        if resp.status_code != 429:
            return resp
        if attempt < MAX_RETRIES - 1:
            sleep(BACKOFF_BASE_SECONDS * (2**attempt))
    return resp


def fetch_top100(*, client: httpx.Client, sleep=time.sleep) -> list[dict] | None:
    """Top-100 by market cap, minus stablecoins and wrapped coins. None on failure."""
    try:
        resp = _get(client, MARKETS_URL, {"vs_currency": "usd", "order": "market_cap_desc",
                                          "per_page": 100, "page": 1}, sleep)
        if resp is None or resp.status_code >= 400:
            return None
        rows = []
        for r in resp.json():
            sym = str(r["symbol"]).upper()
            if sym in STABLECOIN_SYMBOLS or sym in WRAPPED_SYMBOLS:
                continue
            rows.append({"id": r["id"], "symbol": sym, "market_cap": r.get("market_cap")})
        return rows
    except Exception:
        return None


def fetch_series(symbol: str, coin_id: str, *, client: httpx.Client,
                 today: date | None = None, sleep=time.sleep) -> SourceSeries:
    sym = symbol.upper()
    today = today or datetime.now(timezone.utc).date()
    try:
        resp = _get(client, CHART_URL.format(coin_id=coin_id),
                    {"vs_currency": "usd", "days": 100, "interval": "daily"}, sleep)
        if resp is None or resp.status_code == 429:
            return SourceSeries("coingecko", sym, [], "capped", "HTTP 429")
        if resp.status_code >= 400:
            return SourceSeries("coingecko", sym, [], "unavailable", f"HTTP {resp.status_code}")
        raw = resp.json().get("total_volumes") or []
        pts = sorted(
            (datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date(), float(v)) for ms, v in raw
        )
    except Exception as exc:
        return SourceSeries("coingecko", sym, [], "unavailable", type(exc).__name__)
    pts = [p for p in pts if p[0] < today]
    if not pts:
        return SourceSeries("coingecko", sym, [], "unavailable", "empty response")
    if len(pts) < MIN_HISTORY_DAYS:
        return SourceSeries("coingecko", sym, pts, "insufficient-history", f"{len(pts)} days")
    return SourceSeries("coingecko", sym, pts, "ok", "")


def fetch_trending_symbols() -> list[str]:
    """Wrap the existing adapter (snapshot, not stored as a daily series)."""
    return coingecko_adapter.fetch_trending().symbols
