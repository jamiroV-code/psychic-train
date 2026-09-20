"""CoinGecko trending-coins proxy adapter (item 49).

Keyless public endpoint (`/api/v3/search/trending`) — no credentials, no
Security Posture env var needed for this one source. Returns which coin
symbols are currently trending; narrative-category attribution happens
downstream in `analytics/narrative/trigger.py`'s orchestration, which maps
each trending symbol to a category via `mapping.map_coin_to_category` and
counts hits per category (Architecture Clarification: `data/` fetches,
`analytics/` computes — this adapter has no concept of "categories", only
"which coins are trending right now").
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import httpx

from api.data import cache

COINGECKO_TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0
TIMEOUT_SECONDS = 10.0
STALENESS_HOURS = 6  # CoinGecko trending refreshes frequently intraday

Status = Literal["ok", "unavailable", "stale"]


@dataclass
class TrendingResult:
    symbols: list[str]  # uppercased trending coin symbols, most-trending first
    as_of: str | None
    status: Status


def _fetch_with_backoff(client: httpx.Client) -> dict | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(COINGECKO_TRENDING_URL, timeout=TIMEOUT_SECONDS)
            if resp.status_code == 429:
                if attempt == MAX_RETRIES - 1:
                    return None
                time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            return None
        except httpx.HTTPStatusError:
            return None
        except httpx.NetworkError:
            return None
        except Exception:
            return None
    return None


def _parse_symbols(raw: dict) -> list[str]:
    coins = raw.get("coins") or []
    symbols: list[str] = []
    for entry in coins:
        item = entry.get("item") or {}
        symbol = item.get("symbol")
        if isinstance(symbol, str) and symbol:
            symbols.append(symbol.upper())
    return symbols


def fetch_trending(client: httpx.Client | None = None) -> TrendingResult:
    """Fetch (or serve cached) the current CoinGecko trending-coins list.

    Trending is a live "right now" snapshot, not archived per-day the way
    LiqTide is (Standing Rule 8 applies only to LiqTide's irrecoverable
    composite) — cached under one fixed key, overwritten on every
    successful fetch.
    """
    cache.bootstrap_cache_dirs()
    own_client = client is None
    client = client or httpx.Client()
    try:
        raw = _fetch_with_backoff(client)
    finally:
        if own_client:
            client.close()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if raw is not None:
        try:
            symbols = _parse_symbols(raw)
        except Exception:
            symbols = []
        if symbols:
            cache.write_trending_snapshot(today, symbols)
            return TrendingResult(symbols=symbols, as_of=today, status="ok")

    snapshot = cache.read_trending_snapshot()
    if snapshot is None:
        return TrendingResult(symbols=[], as_of=None, status="unavailable")

    as_of, symbols = snapshot
    hours: float | None = None
    try:
        then = datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - then).total_seconds() / 3600.0
    except (ValueError, TypeError):
        pass
    status: Status = "ok" if (hours is not None and hours <= STALENESS_HOURS) else "stale"
    return TrendingResult(symbols=symbols, as_of=as_of, status=status)
