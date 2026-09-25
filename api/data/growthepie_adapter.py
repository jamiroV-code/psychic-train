"""growthepie adapter: daily active addresses and transaction counts per chain.

Chain growth RFC-2 (fallback scope: growthepie is the primary source, no Dune).
Keyless. Host `https://api.growthepie.xyz`. Endpoints confirmed on the user's
PC (2026-09-25):

- per chain:  GET /v1/metrics/chains/{chain}/{metric}.json
  -> {"last_updated_utc": ..., "details": {"metric_id": ..., "timeseries":
      {"daily": {"types": ["unix", "value", ...], "data": [[unix, value], ...]}}}}
- bulk:       GET /v1/export/{metric}.json
  -> [{"metric_key", "origin_key", "date": "YYYY-MM-DD", "value"}, ...]
- master:     GET /v1/master.json -> metrics.{metric}.supported_chains

Never use /v1/metrics/{metric}.json, /v1/chains/... or fundamentals_full.json
(403 AccessDenied).

Public Contract: every function here never raises. Failure is a typed
`status="unavailable"` result with a `reason`; missing or bad values are
dropped, never zero-filled. Each chain's result is independent: one chain
failing never changes another chain's result. Dates are UTC calendar dates.
`stale` is reserved for the cache layer (RFC-3); this adapter only returns
`ok` or `unavailable`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Iterable, Literal

import httpx

BASE_URL = "https://api.growthepie.xyz"
REDISTRIBUTABLE = True
ATTRIBUTION = "Source: growthepie, https://www.growthepie.com."
TIMEOUT_S = 60.0

# Our metric name -> growthepie metric key.
METRIC_KEYS: dict[str, str] = {"active_addresses": "daa", "transactions": "txcount"}

# Unix values above this are milliseconds (1e11 s is year 5138).
_MS_THRESHOLD = 1e11

SeriesStatus = Literal["ok", "unavailable", "stale"]


@dataclass
class GrowthepieSeries:
    chain_key: str
    metric: str  # our metric name, e.g. "active_addresses"
    status: SeriesStatus
    points: list[tuple[str, float]] = field(default_factory=list)  # (YYYY-MM-DD UTC, value), ascending
    reason: str | None = None
    last_updated_utc: str | None = None
    redistributable: bool = REDISTRIBUTABLE
    attribution: str = ATTRIBUTION


@dataclass
class SupportedChains:
    metric: str
    status: SeriesStatus
    chains: frozenset[str] = frozenset()
    reason: str | None = None


def _unavailable(chain_key: str, metric: str, reason: str) -> GrowthepieSeries:
    return GrowthepieSeries(chain_key=chain_key, metric=metric, status="unavailable", reason=reason)


def _metric_key(metric: str) -> str | None:
    return METRIC_KEYS.get(metric)


def _to_value(raw: object) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v) or v < 0:
        return None
    return v


def unix_to_utc_date(raw: object) -> str | None:
    """UTC date for a unix timestamp in seconds or milliseconds."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        ts = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(ts) or math.isinf(ts) or ts < 0:
        return None
    if ts > _MS_THRESHOLD:
        ts /= 1000.0
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _finish(chain_key: str, metric: str, by_date: dict[str, float], last_updated: str | None) -> GrowthepieSeries:
    if not by_date:
        return _unavailable(chain_key, metric, "empty-series")
    return GrowthepieSeries(
        chain_key=chain_key,
        metric=metric,
        status="ok",
        points=sorted(by_date.items()),
        last_updated_utc=last_updated,
    )


def parse_chain_metric(payload: object, chain_key: str, metric: str) -> GrowthepieSeries:
    """Parse a per-chain metric response. Wrong shape -> unavailable."""
    if not isinstance(payload, dict):
        return _unavailable(chain_key, metric, "unexpected-shape")
    details = payload.get("details")
    daily = ((details or {}).get("timeseries") or {}).get("daily") if isinstance(details, dict) else None
    if not isinstance(daily, dict):
        return _unavailable(chain_key, metric, "unexpected-shape")
    types, rows = daily.get("types"), daily.get("data")
    if not isinstance(types, list) or not isinstance(rows, list) or "unix" not in types or "value" not in types:
        return _unavailable(chain_key, metric, "unexpected-shape")
    i_ts, i_val = types.index("unix"), types.index("value")
    by_date: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) <= max(i_ts, i_val):
            continue
        d, v = unix_to_utc_date(row[i_ts]), _to_value(row[i_val])
        if d is None or v is None:
            continue
        by_date[d] = v
    last = payload.get("last_updated_utc")
    return _finish(chain_key, metric, by_date, last if isinstance(last, str) else None)


def _get_json(path: str, client: httpx.Client | None) -> tuple[object | None, str | None]:
    """(payload, None) on success, (None, reason) on failure. Never raises."""
    url = f"{BASE_URL}{path}"
    try:
        if client is None:
            with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True) as c:
                resp = c.get(url)
        else:
            resp = client.get(url)
    except Exception as exc:  # network, timeout, transport
        return None, f"fetch-failed: {type(exc).__name__}"
    if resp.status_code != 200:
        return None, f"http-{resp.status_code}"
    try:
        return resp.json(), None
    except Exception:
        return None, "invalid-json"


def fetch_chain_metric(chain_key: str, metric: str, client: httpx.Client | None = None) -> GrowthepieSeries:
    """Full daily history of one metric for one chain."""
    mkey = _metric_key(metric)
    if mkey is None:
        return _unavailable(chain_key, metric, "unknown-metric")
    payload, err = _get_json(f"/v1/metrics/chains/{chain_key}/{mkey}.json", client)
    if err:
        return _unavailable(chain_key, metric, err)
    try:
        return parse_chain_metric(payload, chain_key, metric)
    except Exception as exc:  # defensive: parser bug must not raise
        return _unavailable(chain_key, metric, f"parse-failed: {type(exc).__name__}")


def fetch_chain_metrics(chain_keys: Iterable[str], metric: str, client: httpx.Client | None = None) -> dict[str, GrowthepieSeries]:
    """One call per chain; each chain isolated from the others' failures."""
    out: dict[str, GrowthepieSeries] = {}
    for key in chain_keys:
        try:
            out[key] = fetch_chain_metric(key, metric, client)
        except Exception as exc:  # belt and braces: isolation must hold
            out[key] = _unavailable(key, metric, f"fetch-failed: {type(exc).__name__}")
    return out


def parse_export(payload: object, metric: str, chain_keys: Iterable[str] | None = None) -> dict[str, GrowthepieSeries]:
    """Split a bulk export into per-chain series. Requested chains missing from
    the export are `unavailable` ("chain-not-in-export"). Rows with a bad date
    or value are dropped, not zero-filled."""
    wanted = None if chain_keys is None else list(chain_keys)
    if not isinstance(payload, list):
        keys = wanted or []
        return {k: _unavailable(k, metric, "unexpected-shape") for k in keys}
    mkey = _metric_key(metric)
    grouped: dict[str, dict[str, float]] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        origin = row.get("origin_key")
        if not isinstance(origin, str) or not origin:
            continue
        if row.get("metric_key") not in (None, mkey):
            continue
        d, v = row.get("date"), _to_value(row.get("value"))
        if not isinstance(d, str) or v is None:
            continue
        try:
            d = date.fromisoformat(d[:10]).isoformat()
        except ValueError:
            continue
        if wanted is not None and origin not in wanted:
            continue
        grouped.setdefault(origin, {})[d] = v
    keys = wanted if wanted is not None else sorted(grouped)
    out: dict[str, GrowthepieSeries] = {}
    for k in keys:
        if k not in grouped:
            out[k] = _unavailable(k, metric, "chain-not-in-export")
        else:
            out[k] = _finish(k, metric, grouped[k], None)
    return out


def fetch_export(metric: str, chain_keys: Iterable[str] | None = None, client: httpx.Client | None = None) -> dict[str, GrowthepieSeries]:
    """Bulk export of one metric for all chains (one request)."""
    wanted = None if chain_keys is None else list(chain_keys)
    mkey = _metric_key(metric)
    if mkey is None:
        return {k: _unavailable(k, metric, "unknown-metric") for k in (wanted or [])}
    payload, err = _get_json(f"/v1/export/{mkey}.json", client)
    if err:
        return {k: _unavailable(k, metric, err) for k in (wanted or [])}
    try:
        return parse_export(payload, metric, wanted)
    except Exception as exc:
        return {k: _unavailable(k, metric, f"parse-failed: {type(exc).__name__}") for k in (wanted or [])}


def parse_supported_chains(payload: object, metric: str) -> SupportedChains:
    mkey = _metric_key(metric)
    metrics = payload.get("metrics") if isinstance(payload, dict) else None
    entry = metrics.get(mkey) if isinstance(metrics, dict) and mkey else None
    chains = entry.get("supported_chains") if isinstance(entry, dict) else None
    if not isinstance(chains, list):
        return SupportedChains(metric=metric, status="unavailable", reason="unexpected-shape")
    return SupportedChains(metric=metric, status="ok", chains=frozenset(c for c in chains if isinstance(c, str)))


def fetch_supported_chains(metric: str, client: httpx.Client | None = None) -> SupportedChains:
    """Which chain keys growthepie supports for `metric` (from master.json)."""
    if _metric_key(metric) is None:
        return SupportedChains(metric=metric, status="unavailable", reason="unknown-metric")
    payload, err = _get_json("/v1/master.json", client)
    if err:
        return SupportedChains(metric=metric, status="unavailable", reason=err)
    try:
        return parse_supported_chains(payload, metric)
    except Exception as exc:
        return SupportedChains(metric=metric, status="unavailable", reason=f"parse-failed: {type(exc).__name__}")
