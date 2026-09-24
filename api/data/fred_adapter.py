"""FRED (Federal Reserve Economic Data) adapter — deep-history net-liquidity
and dollar-strength input for the reduced macro-liquidity composite
(Implementation Checklist item 31, ADR-2).

Uses FRED's public, keyless CSV export (`fredgraph.csv`) — confirmed at
RFC-002 Stage 0 to require no API key:
`https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES_ID>`. This is
deep, durable, primary-source history (decades) — unlike LiqTide's own live
endpoint, whose `metrics` series were confirmed at Stage 0 to only go back
to ~2024/2025, far too short for the 2017/2020-21 backtest (item 40). This
is why the reduced composite is built from FRED, not reproduced from
LiqTide's own short history.

Because FRED is itself the durable primary archive (not a derived composite
that could disappear), this adapter caches each series as a full
overwrite-per-refresh (`cache/liquidity/{series_id}.parquet`) rather than
Standing-Rule-8 append-only-per-day archival (contrast `liqtide_adapter`,
which archives one immutable file per day because LiqTide's own composite
history is not otherwise recoverable).

Public Contracts: returns a typed result carrying an explicit `status`
(`ok` | `unavailable` | `stale`) — never raises past this module's boundary.

Units (confirmed at Stage 0 against each series' own FRED page — this
matters, the three net-liquidity inputs are not all in the same unit):
WALCL and WTREGEN are both "Millions of U.S. Dollars"; RRPONTSYD is
"Billions of U.S. Dollars" — `fetch_net_liquidity` converts RRP to millions
before combining (`* 1000`), matching the standard WALCL-TGA-RRP*1000
combination used in FRED's own community-shared comparison graphs of this
identity. WRESBAL (reserve balances) is "Billions of U.S. Dollars", weekly
— NOT millions like WALCL/WTREGEN; it is not part of the net-liquidity
identity and is therefore never converted or combined here.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass
from typing import Literal

import httpx
import pandas as pd

from api.data import cache

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0
TIMEOUT_SECONDS = 15.0
# FRED series update at most daily (WALCL/TGA are weekly). Re-downloading
# each series' full CSV history on every single request (as this adapter
# did before) is pure waste under Standing Rule 4 — 6h keeps the leg-
# timeline/screener-board fast across repeat page loads within a session
# without staling out real day-to-day updates.
FRESH_TTL_SECONDS = 6 * 60 * 60

# Series IDs confirmed at RFC-002 Stage 0 (data-sources/all-data-sources.md
# §Macro Liquidity's core identity `NET LIQUIDITY = WALCL - TGA - RRP`, plus
# the weight table's "Broad dollar... 15%" row):
WALCL = "WALCL"            # Fed total assets, weekly Wednesday level, millions
TGA = "WTREGEN"             # Treasury General Account balance, weekly average, millions
RRP = "RRPONTSYD"           # Overnight reverse repo, daily, billions (converted below)
BROAD_DOLLAR = "DTWEXBGS"   # Nominal Broad U.S. Dollar Index, daily
RESERVES = "WRESBAL"        # Reserve balances at the Fed, weekly, billions (TOTRESNS discontinued 2020)
# Regime dashboard RFC-002: TGA *Wednesday level* (H.4.1), weekly, millions.
# Unlike WTREGEN (a weekly average), WALCL - WDTGAL - RRPONTSYD*1000 on the
# Wednesday grid reproduces LiqTide's published net liquidity exactly
# (checked 24-09-26 on 2024-09-04, 2026-08-19, 2026-09-09, 2026-09-16).
# `fetch_net_liquidity` below keeps WTREGEN on purpose: the leg-boundary
# path was tuned on it (see backlog liquidity-composite-calendar-windows).
TGA_WEDNESDAY = "WDTGAL"

RRP_BILLIONS_TO_MILLIONS = 1000.0

Status = Literal["ok", "unavailable", "stale"]


@dataclass
class FredSeriesResult:
    series_id: str
    df: pd.DataFrame  # columns: date, value
    status: Status


def _fetch_csv_with_backoff(client: httpx.Client, series_id: str) -> str | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(FRED_CSV_URL, params={"id": series_id}, timeout=TIMEOUT_SECONDS)
            if resp.status_code == 429:
                if attempt == MAX_RETRIES - 1:
                    return None
                time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            resp.raise_for_status()
            return resp.text
        except httpx.TimeoutException:
            return None
        except httpx.HTTPStatusError:
            return None
        except httpx.NetworkError:
            return None
        except Exception:
            return None
    return None


def _parse_csv(text: str, series_id: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text))
    # FRED's CSV export header is `observation_date`; older exports used `DATE`.
    df = df.rename(columns={"DATE": "date", "observation_date": "date", series_id: "value"})
    if "date" not in df.columns or "value" not in df.columns:
        return pd.DataFrame(columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["date", "value"])[["date", "value"]]


def fetch_series(series_id: str, client: httpx.Client | None = None) -> FredSeriesResult:
    """Fetch (or serve cached) one FRED series' full history, cache-first.

    A live-fetch failure or malformed/empty response falls back to the
    cached series (if any) marked `stale`; only a never-cached series
    returns `unavailable`.
    """
    cache.bootstrap_cache_dirs()

    age = cache.liquidity_series_age_seconds(series_id)
    if age is not None and age < FRESH_TTL_SECONDS:
        fresh_cached = cache.read_liquidity_series(series_id)
        if not fresh_cached.empty:
            return FredSeriesResult(series_id=series_id, df=fresh_cached, status="ok")

    own_client = client is None
    client = client or httpx.Client()
    try:
        text = _fetch_csv_with_backoff(client, series_id)
    finally:
        if own_client:
            client.close()

    cached = cache.read_liquidity_series(series_id)

    if text is not None:
        try:
            fetched = _parse_csv(text, series_id)
        except Exception:
            fetched = pd.DataFrame(columns=["date", "value"])
        if not fetched.empty:
            cache.write_liquidity_series(series_id, fetched)
            return FredSeriesResult(series_id=series_id, df=fetched, status="ok")

    if cached is None or cached.empty:
        return FredSeriesResult(series_id=series_id, df=pd.DataFrame(columns=["date", "value"]), status="unavailable")
    return FredSeriesResult(series_id=series_id, df=cached, status="stale")


def fetch_net_liquidity(client: httpx.Client | None = None) -> FredSeriesResult:
    """NET LIQUIDITY = WALCL - TGA - RRP (data-sources doc's core identity).

    Fetches all three FRED series, aligns them on date (WALCL/TGA are
    weekly; RRP is daily — `merge_asof` backward-fills each weekly value
    onto the daily RRP index, i.e. "as of the most recent weekly reading"),
    and combines. RRP is converted from billions to millions first (see
    module docstring's Units note) so the subtraction is unit-consistent.
    """
    own_client = client is None
    client = client or httpx.Client()
    try:
        walcl = fetch_series(WALCL, client=client)
        tga = fetch_series(TGA, client=client)
        rrp = fetch_series(RRP, client=client)
    finally:
        if own_client:
            client.close()

    if walcl.df.empty or tga.df.empty or rrp.df.empty:
        worst: Status = "unavailable"
        return FredSeriesResult(series_id="net_liquidity", df=pd.DataFrame(columns=["date", "value"]), status=worst)

    worst = "ok"
    for r in (walcl, tga, rrp):
        if r.status == "stale" and worst == "ok":
            worst = "stale"

    merged = rrp.df.rename(columns={"value": "rrp"}).sort_values("date")
    merged["rrp"] = merged["rrp"] * RRP_BILLIONS_TO_MILLIONS
    for name, r in (("walcl", walcl), ("tga", tga)):
        s = r.df.rename(columns={"value": name}).sort_values("date")
        merged = pd.merge_asof(merged, s, on="date", direction="backward")
    merged = merged.dropna(subset=["walcl", "tga", "rrp"])
    merged["value"] = merged["walcl"] - merged["tga"] - merged["rrp"]
    return FredSeriesResult(series_id="net_liquidity", df=merged[["date", "value"]], status=worst)
