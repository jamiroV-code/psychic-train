"""Hyperliquid daily market snapshot for the narrative exchange-attention proxy.

Narrative dashboard RFC-2 (ADR-6). Display-only: this feeds
`analytics/narrative/exchange_attention.py` and, through it, `/history` —
never `trigger.compute_trigger`, `/categories` or the screener.

Public Contract: `fetch_daily_market_snapshot()` never raises. Any failure is a
typed `status="unavailable"` result with a `reason`, never an empty "ok" list
and never zero volumes standing in for missing ones.

What is fetched (Stage 0, read from ccxt 4.5.78 `hyperliquid.py`):
- `fetch_tickers(params={"type": "swap"})` = one `metaAndAssetCtxs` call,
  perpetuals only. Spot is excluded on purpose: ccxt maps spot `UBTC` to `BTC`,
  which would double-count against the BTC perp. HIP-3 (builder-deployed dexes,
  e.g. `xyz:TSLA` equities) are excluded because they are not crypto
  narratives.
- `quoteVolume` is Hyperliquid's `dayNtlVlm`: rolling 24h notional in USDC. It
  is already a dollar amount, so `k`-prefixed thousand-unit contracts
  (`kPEPE`) need no rescaling.
- The perp's raw name is read from the ticker's `info["name"]`, not from the
  process-wide market cache, so a listing that appeared after `load_markets()`
  still shows up (that is exactly what new-listing detection needs).

Dating: `as_of` is the UTC calendar date at fetch time. The value is a rolling
24h window, not a closed UTC day — documented, not hidden.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from api.data import ccxt_adapter

# Decision D4 (2026-09-24): Hyperliquid's terms have not been checked yet.
# Stay conservative until the user confirms them — flipping this is a
# one-line change.
HYPERLIQUID_REDISTRIBUTABLE = False

SnapshotStatus = Literal["ok", "unavailable"]


@dataclass(frozen=True)
class PerpMarket:
    base: str  # ccxt unified base, upper-cased (e.g. "KPEPE")
    base_name: str  # Hyperliquid's raw name (e.g. "kPEPE")
    quote_volume: float | None  # 24h notional USDC; None when not reported


@dataclass
class ExchangeSnapshotResult:
    status: SnapshotStatus
    as_of: str  # UTC date, YYYY-MM-DD
    perps: list[PerpMarket] = field(default_factory=list)
    reason: str | None = None
    redistributable: bool = HYPERLIQUID_REDISTRIBUTABLE


def utc_date(now: datetime | None = None) -> str:
    now = datetime.now(timezone.utc) if now is None else now
    if now.tzinfo is None:
        raise ValueError("naive datetime: pass a timezone-aware value")
    return now.astimezone(timezone.utc).date().isoformat()


def _is_hip3(info: dict, name: str) -> bool:
    return bool(info.get("hip3")) or ":" in name


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out < 0:  # NaN or negative → not a usable volume
        return None
    return out


def parse_tickers(tickers: dict) -> list[PerpMarket]:
    """Active, non-HIP-3 perps from a ccxt `fetch_tickers` result."""
    perps: list[PerpMarket] = []
    for symbol, ticker in (tickers or {}).items():
        if not isinstance(ticker, dict):
            continue
        info = ticker.get("info") or {}
        name = info.get("name")
        if not isinstance(name, str) or not name:
            continue
        if _is_hip3(info, name):
            continue
        if info.get("isDelisted") is True:
            continue
        base = str(symbol).split("/")[0] if symbol else name.upper()
        perps.append(PerpMarket(base=base, base_name=name, quote_volume=_to_float(ticker.get("quoteVolume"))))
    return perps


def fetch_daily_market_snapshot(exchange=None, now: datetime | None = None) -> ExchangeSnapshotResult:
    as_of = utc_date(now)
    try:
        ex = ccxt_adapter._exchange() if exchange is None else exchange
        if ex is None:
            return ExchangeSnapshotResult(status="unavailable", as_of=as_of, reason="exchange-unavailable")
        tickers = ex.fetch_tickers(params={"type": "swap"})
    except Exception as exc:  # timeout, network, exchange error — never raise
        return ExchangeSnapshotResult(status="unavailable", as_of=as_of, reason=f"fetch-failed: {type(exc).__name__}")
    try:
        perps = parse_tickers(tickers)
    except Exception as exc:
        return ExchangeSnapshotResult(status="unavailable", as_of=as_of, reason=f"parse-failed: {type(exc).__name__}")
    if not perps:
        return ExchangeSnapshotResult(status="unavailable", as_of=as_of, reason="empty-market-list")
    return ExchangeSnapshotResult(status="ok", as_of=as_of, perps=perps)
