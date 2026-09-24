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
    # The untouched upstream JSON, when this payload came from a fresh live
    # parse. Carries the fields `_parse_payload` otherwise discards
    # (`tide_index.components`/`weights`/`value`/`label`, `data_quality`,
    # `regime`) so a verifier (`scripts/snapshot_liqtide.py`) can re-derive
    # the published score and check it. Defaulted fields must follow the
    # non-defaulted ones.
    raw: dict | None = None
    # Regime dashboard RFC-001 (additive): the published 0-100 index
    # (`tide_index.value`) and its band label. `tide_score` above is the
    # -1..+1 `tide_index.score` (value = 50 + 50 * score, confirmed against
    # the live payload 24-09-26) — the two are different scales.
    tide_value: float | None = None
    tide_label: str | None = None


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
    tide_value = tide_index.get("value")
    tide_value = float(tide_value) if isinstance(tide_value, (int, float)) else None
    tide_label = tide_index.get("label")
    tide_label = tide_label if isinstance(tide_label, str) else None

    return LiqTidePayload(
        generated_utc=generated_utc, date=date, tide_score=tide_score,
        metrics=metrics, status="ok", raw=raw,
        tide_value=tide_value, tide_label=tide_label,
    )


def _payload_to_row(payload: LiqTidePayload) -> pd.DataFrame:
    row = {"date": payload.date, "generated_utc": payload.generated_utc, "tide_score": payload.tide_score}
    row.update(payload.metrics)
    # Appended after the original columns so older readers are unaffected.
    row["tide_value"] = payload.tide_value
    row["tide_label"] = payload.tide_label
    return pd.DataFrame([row])


def _row_to_payload(row: pd.Series) -> LiqTidePayload:
    # `raw` is deliberately left at its default None: the archived parquet row
    # holds only the flattened fields, so a cache-replay payload has no fresh
    # upstream JSON to verify against. Absent, never a fabricated stand-in.
    tide_score = row.get("tide_score")
    tide_value = row.get("tide_value")
    tide_label = row.get("tide_label")
    return LiqTidePayload(
        generated_utc=row.get("generated_utc"),
        date=row.get("date"),
        tide_score=float(tide_score) if pd.notna(tide_score) else None,
        metrics={k: (float(row[k]) if k in row.index and pd.notna(row[k]) else None) for k in METRIC_KEYS},
        status="ok",
        # Rows archived before 24-09-26 have no such columns -> None.
        tide_value=float(tide_value) if tide_value is not None and pd.notna(tide_value) else None,
        tide_label=tide_label if isinstance(tide_label, str) else None,
    )


def _hours_since(date_str: str) -> float | None:
    try:
        then = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return (datetime.now(timezone.utc) - then).total_seconds() / 3600.0


def fetch_latest(client: httpx.Client | None = None, dry_run: bool = False) -> LiqTidePayload:
    """Fetch (or serve cached) today's LiqTide payload.

    `dry_run=True` fetches and parses exactly as normal but skips the archive
    write, so a verifier can inspect a live payload without mutating the
    append-only archive. The returned payload is fully populated either way.

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
            if not dry_run:
                cache.write_liqtide_payload(payload.date, _payload_to_row(payload))
                # Verbatim upstream JSON, append-only (regime dashboard
                # RFC-001). A failure here must not lose the parquet row
                # above or raise past the adapter boundary.
                try:
                    cache.write_liqtide_raw(payload.date, raw)
                except Exception:
                    pass
            return payload

    history = cache.read_liqtide_history()
    if history is None or history.empty:
        return _empty_payload("unavailable")
    latest_row = history.sort_values("date").iloc[-1]
    payload = _row_to_payload(latest_row)
    age_hours = _hours_since(payload.date)
    payload.status = "ok" if (age_hours is not None and age_hours <= STALENESS_HOURS) else "stale"
    return payload


# --- Regime dashboard RFC-002: history carried inside archived payloads ----
#
# Each payload ships thinned history (`tide_series`, `metrics.*.series`).
# `extract_history_series` flattens one payload; `read_history_series`
# unions every archived raw payload (newest payload wins for a repeated
# `(series_key, date)`) — a pure cache read, never a network call, so the
# dashboard can use it without ever touching `latest.json` (VALIDATE P1).

HISTORY_COLUMNS = ["series_key", "date", "value"]
TIDE_SERIES_KEY = "tide_value"


def _history_points(series: object) -> list[tuple[str, float]]:
    """`[[date, value], ...]` -> clean `(date, value)` tuples; anything
    malformed is dropped rather than coerced."""
    if not isinstance(series, list):
        return []
    out: list[tuple[str, float]] = []
    for point in series:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        date, value = point[0], point[1]
        if not isinstance(date, str) or isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        out.append((date[:10], float(value)))
    return out


def extract_history_series(raw: dict) -> pd.DataFrame:
    """Long-format history (`series_key, date, value`) carried in one payload."""
    rows: list[dict] = []
    for date, value in _history_points(raw.get("tide_series")):
        rows.append({"series_key": TIDE_SERIES_KEY, "date": date, "value": value})
    metrics = raw.get("metrics")
    if isinstance(metrics, dict):
        for key in sorted(metrics):
            entry = metrics[key]
            if not isinstance(entry, dict):
                continue
            for date, value in _history_points(entry.get("series")):
                rows.append({"series_key": key, "date": date, "value": value})
    if not rows:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    df = pd.DataFrame(rows, columns=HISTORY_COLUMNS)
    return (
        df.drop_duplicates(subset=["series_key", "date"], keep="last")
        .sort_values(["series_key", "date"])
        .reset_index(drop=True)
    )


def read_history_series() -> pd.DataFrame:
    """Union of the history in every archived raw payload. Empty frame with
    `HISTORY_COLUMNS` when nothing is archived."""
    frames = []
    for date in cache.list_liqtide_raw_dates():  # sorted oldest -> newest
        raw = cache.read_liqtide_raw(date)
        if raw is None:
            continue
        df = extract_history_series(raw)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    merged = pd.concat(frames, ignore_index=True)
    return (
        merged.drop_duplicates(subset=["series_key", "date"], keep="last")
        .sort_values(["series_key", "date"])
        .reset_index(drop=True)
    )
