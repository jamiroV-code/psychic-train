"""DefiLlama stablecoin-supply adapter — the reduced composite's 4th input,
added per ADR-2's conditional clause ("include stablecoin-supply only if
item 32's probe confirms sufficient depth").

EXECUTE-time note (documented per this project's ADR-1 precedent — "document,
never silently guess"): item 32's probe (`scripts/probe_stablecoin_history.py`)
confirmed `https://stablecoins.llama.fi/stablecoincharts/all` is keyless,
returns JSON, and has daily aggregate circulating-supply history back to
2017-11-29 — comfortably deep enough for both the 2017 and 2020-21 backtest
cycles. Neither `data-sources/all-data-sources.md`'s adapter table nor the
plan's original Touchpoints list named a dedicated stablecoin adapter file
(the plan's "5 adapters" enumeration in Component Details predates ADR-2's
conditional clause and item 32's probe result); this file is added as an
EXECUTE-time deviation directly required by ADR-2 plus this project's own
Rules ("every provider behind an adapter in api/data/... no provider name
should ever appear in ... an analytics function") — the same kind of
documented, rule-driven deviation RFC-001 took for `screener_board.py`
(not originally in Touchpoints either, added because the Architecture
Clarification's own separation rule required it).

Public Contracts: returns a typed result carrying an explicit `status`
(`ok` | `unavailable` | `stale`) — never raises past this module's boundary.
Cached as a full overwrite-per-refresh series (`cache/liquidity/
stablecoin_supply.parquet`), same reasoning as `fred_adapter`: DefiLlama's
aggregate endpoint is itself the durable historical archive for this
metric, not a derived one-off composite (contrast `liqtide_adapter`'s
Standing-Rule-8 per-day archival).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import httpx
import pandas as pd

from api.data import cache

STABLECOIN_CHARTS_URL = "https://stablecoins.llama.fi/stablecoincharts/all"
SERIES_ID = "stablecoin_supply"
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0
TIMEOUT_SECONDS = 20.0
# DefiLlama's aggregate series updates at most daily — see fred_adapter's
# matching FRESH_TTL_SECONDS note (Standing Rule 4).
FRESH_TTL_SECONDS = 6 * 60 * 60

Status = Literal["ok", "unavailable", "stale"]


@dataclass
class StablecoinSupplyResult:
    df: pd.DataFrame  # columns: date, value (aggregate circulating USD supply)
    status: Status


def _fetch_with_backoff(client: httpx.Client) -> list | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(STABLECOIN_CHARTS_URL, timeout=TIMEOUT_SECONDS)
            if resp.status_code == 429:
                if attempt == MAX_RETRIES - 1:
                    return None
                time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else None
        except httpx.TimeoutException:
            return None
        except httpx.HTTPStatusError:
            return None
        except httpx.NetworkError:
            return None
        except Exception:
            return None
    return None


def _parse_points(raw: list) -> pd.DataFrame:
    rows = []
    for entry in raw:
        try:
            ts = int(entry["date"])
            value = entry["totalCirculatingUSD"]["peggedUSD"]
        except (KeyError, TypeError, ValueError):
            continue
        rows.append({"date": pd.Timestamp(ts, unit="s", tz="utc"), "value": float(value)})
    if not rows:
        return pd.DataFrame(columns=["date", "value"])
    df = pd.DataFrame(rows).sort_values("date")
    # one point per calendar day — DefiLlama's own series is already daily,
    # this just guards against an accidental duplicate timestamp.
    return df.drop_duplicates(subset="date", keep="last")


def fetch_stablecoin_supply(client: httpx.Client | None = None) -> StablecoinSupplyResult:
    """Fetch (or serve cached) DefiLlama's aggregate stablecoin circulating
    supply series, cache-first. A live-fetch failure or empty/malformed
    response falls back to the cached series marked `stale`; only a
    never-cached series returns `unavailable`.
    """
    cache.bootstrap_cache_dirs()

    age = cache.liquidity_series_age_seconds(SERIES_ID)
    if age is not None and age < FRESH_TTL_SECONDS:
        fresh_cached = cache.read_liquidity_series(SERIES_ID)
        if not fresh_cached.empty:
            return StablecoinSupplyResult(df=fresh_cached, status="ok")

    own_client = client is None
    client = client or httpx.Client()
    try:
        raw = _fetch_with_backoff(client)
    finally:
        if own_client:
            client.close()

    cached = cache.read_liquidity_series(SERIES_ID)

    if raw is not None:
        try:
            fetched = _parse_points(raw)
        except Exception:
            fetched = pd.DataFrame(columns=["date", "value"])
        if not fetched.empty:
            cache.write_liquidity_series(SERIES_ID, fetched)
            return StablecoinSupplyResult(df=fetched, status="ok")

    if cached is None or cached.empty:
        return StablecoinSupplyResult(df=pd.DataFrame(columns=["date", "value"]), status="unavailable")
    return StablecoinSupplyResult(df=cached, status="stale")
