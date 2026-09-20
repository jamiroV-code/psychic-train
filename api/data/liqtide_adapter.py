"""LiqTide macro-liquidity composite adapter (Implementation Checklist item 30).

Public Contracts: returns a typed result carrying an explicit `status`
(`ok` | `unavailable` | `stale`) — never raises past this module's boundary
into a router or analytics call (same discipline as `ccxt_adapter`).

Standing Rule 8 (`data-sources/all-data-sources.md`): LiqTide publishes a
derived composite, not raw inputs, and the product describes itself as beta
and "free while it's beta" — its own history is not recoverable after the
fact if the endpoint changes or is discontinued. Every daily payload is
therefore archived append-only to `cache/liqtide/{date}.parquet` the first
time it is seen; a later re-fetch for a date already archived never
overwrites that file (this is the one deliberate divergence from
`cache.write_ohlcv`'s overwrite-the-whole-series pattern — OHLCV bars are
re-fetchable from the exchange forever, a LiqTide day's payload is not).

Staleness: LiqTide refreshes once daily (~22:45 UTC per
`all-data-sources.md`). A cached payload older than STALENESS_HOURS is
served with `status="stale"`, never silently as fresh.

Stage 0 research (RFC-002, re-confirmed against the live endpoint): top-level
keys are `generated_utc`, `data_quality`, `tide_index` (`value`/`label`/
`score`/`components`/`weights`), `tide_series`, `regime`, `metrics` (one
sub-object per series — `net_liquidity`, `walcl`, `tga`, `rrp`, `reserves`,
`dollar`, `ecb_usd`, `boj_usd`, `stables`, `btc`, `btc_dom`, `fng` — each
carrying `value`/`as_of`/`series`), `fng`. This adapter reads `tide_index`
for `tide_score` (the finished 6-part composite,
`liquidity_composite.build_full_composite`'s input) and the four metric
sub-series this plan's composites actually consume: `net_liquidity`,
`dollar`, `stables`, `btc_dom` (see METRIC_KEYS). LiqTide's own metrics
history was confirmed at Stage 0 to only go back to ~2024-09 (net_liquidity/
dollar) / ~2025-06 (btc_dom) — nowhere near deep enough for the 2017/2020-21
backtest; this is exactly why `liquidity_composite.build_reduced_composite`
does NOT depend on this adapter's history for its net-liquidity/dollar
inputs (it uses `fred_adapter` instead, which has decades of history) and
only reuses this adapter's archived `btc_dom`/`stables` for whatever
history has actually accumulated locally since this adapter first ran.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import httpx
import pandas as pd

from api.data import cache

LIQTIDE_URL = "https://liqtide.com/data/latest.json"
STALENESS_HOURS = 48
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0
TIMEOUT_SECONDS = 10.0

Status = Literal["ok", "unavailable", "stale"]

# The metric sub-series this plan's composites actually read (net liquidity,
# dollar index, stablecoin supply, BTC dominance — data-sources doc's
# weight table plus ADR-2's reduced-composite definition). `walcl`/`tga`/
# `rrp` are LiqTide's own upstream inputs to `net_liquidity` and are not
# separately consumed here (fred_adapter reproduces those independently for
# the reduced composite's deep-history need); `reserves`/`ecb_usd`/
# `boj_usd`/`btc`/`fng` are not consumed by this plan.
METRIC_KEYS: tuple[str, ...] = ("net_liquidity", "dollar", "stables", "btc_dom")


@dataclass
class LiqTidePayload:
    generated_utc: str | None
    date: str  # YYYY-MM-DD, derived from generated_utc — the archive key
    tide_score: float | None
    metrics: dict[str, float | None]  # one current value per METRIC_KEYS entry
    status: Status


def _empty_payload(status: Status) -> LiqTidePayload:
    return LiqTidePayload(
        generated_utc=None, date="", tide_score=None,
        metrics={k: None for k in METRIC_KEYS}, status=status,
    )


def _fetch_with_backoff(client: httpx.Client) -> dict | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(LIQTIDE_URL, timeout=TIMEOUT_SECONDS)
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
            # Malformed JSON or any other adapter-boundary failure — never
            # raise past the adapter (Public Contracts).
            return None
    return None


def _parse_payload(raw: dict) -> LiqTidePayload:
    generated_utc = raw.get("generated_utc")
    if isinstance(generated_utc, str) and len(generated_utc) >= 10:
        date = generated_utc[:10]
    else:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    tide_index = raw.get("tide_index") or {}
    metrics_raw = raw.get("metrics") or {}
    metrics: dict[str, float | None] = {}
    for key in METRIC_KEYS:
        entry = metrics_raw.get(key) or {}
        value = entry.get("value")
        metrics[key] = float(value) if isinstance(value, (int, float)) else None

    tide_score = tide_index.get("score")
    tide_score = float(tide_score) if isinstance(tide_score, (int, float)) else None

    return LiqTidePayload(generated_utc=generated_utc, date=date, tide_score=tide_score, metrics=metrics, status="ok")


def _payload_to_row(payload: LiqTidePayload) -> pd.DataFrame:
    row = {"date": payload.date, "generated_utc": payload.generated_utc, "tide_score": payload.tide_score}
    row.update(payload.metrics)
    return pd.DataFrame([row])


def _row_to_payload(row: pd.Series) -> LiqTidePayload:
    tide_score = row.get("tide_score")
    return LiqTidePayload(
        generated_utc=row.get("generated_utc"),
        date=row.get("date"),
        tide_score=float(tide_score) if pd.notna(tide_score) else None,
        metrics={k: (float(row[k]) if k in row.index and pd.notna(row[k]) else None) for k in METRIC_KEYS},
        status="ok",
    )


def _hours_since(date_str: str) -> float | None:
    try:
        then = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return (datetime.now(timezone.utc) - then).total_seconds() / 3600.0


def fetch_latest(client: httpx.Client | None = None) -> LiqTidePayload:
    """Fetch (or serve cached) today's LiqTide payload.

    Archives every newly-seen daily payload append-only (Standing Rule 8).
    On a live-fetch failure, falls back to the most recently archived
    payload; if that payload is older than STALENESS_HOURS it is served
    with `status="stale"`, never silently as fresh. Only an
    empty/never-cached history returns `status="unavailable"`.
    """
    cache.bootstrap_cache_dirs()
    own_client = client is None
    client = client or httpx.Client()
    try:
        raw = _fetch_with_backoff(client)
    finally:
        if own_client:
            client.close()

    if raw is not None:
        try:
            payload = _parse_payload(raw)
        except Exception:
            payload = None
        if payload is not None and payload.date:
            cache.write_liqtide_payload(payload.date, _payload_to_row(payload))
            return payload

    history = cache.read_liqtide_history()
    if history is None or history.empty:
        return _empty_payload("unavailable")
    latest_row = history.sort_values("date").iloc[-1]
    payload = _row_to_payload(latest_row)
    age_hours = _hours_since(payload.date)
    payload.status = "ok" if (age_hours is not None and age_hours <= STALENESS_HOURS) else "stale"
    return payload
