"""Spot exchange volume for the Discovery exchange slot: Binance, Coinbase and Kraken, daily, keyless.

One `SourceSeries` per (venue, coin): the daily quote (USD or USDT) volume of each completed UTC day, from the
venue's public candle endpoint. Binance and Kraken report a real quote volume; Coinbase reports base volume only,
so its quote volume is close * base volume (an approximation, like the old Binance ccxt series). History comes
back in one request (Binance 120 days, Coinbase about 350, Kraken 720), so a new store is Discovery-ready at once.

Fetchers never raise. A coin the venue does not list is `unavailable` with reason `not listed`, which is a fact
about the coin, not an outage. Only the PC worker (`api/data/spot_volume_refresh.py`) calls these: Binance answers
HTTP 451 to GitHub's US runners.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

import httpx

from api.data.attention.types import MIN_HISTORY_DAYS, SourceSeries

BINANCE_STORE = "exchange_volume"  # the series name Discovery already reads for Binance
COINBASE_STORE = "coinbase_volume"
KRAKEN_STORE = "kraken_volume"
STORES = {"binance": BINANCE_STORE, "coinbase": COINBASE_STORE, "kraken": KRAKEN_STORE}
# Seconds to wait between two requests to one venue (public limits: Binance weight 6000/min, Coinbase 10/s, Kraken ~1/s).
PACE_SECONDS = {"binance": 0.1, "coinbase": 0.2, "kraken": 1.2}
TIMEOUT = 20.0
LOOKBACK_DAYS = 120


def _failure_reason(exc: Exception) -> str:
    """`fetch-failed: Class[ HTTP n]`: the class and a 3-digit status found in the message, never the message."""
    m = re.search(r"\b([45]\d\d)\b", str(exc))
    return f"fetch-failed: {type(exc).__name__}" + (f" HTTP {m.group(1)}" if m else "")


def _day(ts_seconds: float) -> date:
    return datetime.fromtimestamp(ts_seconds, tz=timezone.utc).date()


def _finish(store: str, sym: str, rows: list[tuple[date, float]], today: date) -> SourceSeries:
    pts: dict[date, float] = {}
    for day, vol in rows:
        if day < today and vol == vol and vol >= 0:  # completed UTC days only; NaN and negatives are dropped
            pts[day] = vol
    if not pts:
        return SourceSeries(store, sym, [], "unavailable", "empty response")
    ordered = sorted(pts.items())
    ok = len(ordered) >= MIN_HISTORY_DAYS
    return SourceSeries(store, sym, ordered, "ok" if ok else "insufficient-history", "" if ok else f"{len(ordered)} days")


def _get(client: httpx.Client, url: str, params: dict) -> httpx.Response:
    return client.get(url, params=params, timeout=TIMEOUT)


def fetch_binance(sym: str, client: httpx.Client, today: date) -> SourceSeries:
    try:
        resp = _get(client, "https://api.binance.com/api/v3/klines",
                    {"symbol": f"{sym}USDT", "interval": "1d", "limit": LOOKBACK_DAYS})
        if resp.status_code == 400:  # {"code": -1121, "msg": "Invalid symbol."}
            return SourceSeries(BINANCE_STORE, sym, [], "unavailable", "not listed")
        resp.raise_for_status()
        # [openTime ms, o, h, l, c, base volume, closeTime, quote volume, trades, ...]
        rows = [(_day(bar[0] / 1000), float(bar[7])) for bar in resp.json()]
    except Exception as exc:  # noqa: BLE001 - classified, never raised
        return SourceSeries(BINANCE_STORE, sym, [], "unavailable", _failure_reason(exc))
    return _finish(BINANCE_STORE, sym, rows, today)


def fetch_coinbase(sym: str, client: httpx.Client, today: date) -> SourceSeries:
    try:
        resp = _get(client, f"https://api.exchange.coinbase.com/products/{sym}-USD/candles", {"granularity": 86400})
        if resp.status_code == 404:
            return SourceSeries(COINBASE_STORE, sym, [], "unavailable", "not listed")
        resp.raise_for_status()
        # [time s, low, high, open, close, base volume], newest first
        rows = [(_day(bar[0]), float(bar[4]) * float(bar[5])) for bar in resp.json()]
    except Exception as exc:  # noqa: BLE001
        return SourceSeries(COINBASE_STORE, sym, [], "unavailable", _failure_reason(exc))
    return _finish(COINBASE_STORE, sym, rows, today)


def fetch_kraken(sym: str, client: httpx.Client, today: date) -> SourceSeries:
    try:
        resp = _get(client, "https://api.kraken.com/0/public/OHLC",
                    {"pair": f"{sym}USD", "interval": 1440})
        resp.raise_for_status()
        body = resp.json()
        errors = body.get("error") or []
        if any("Unknown asset pair" in str(e) for e in errors):
            return SourceSeries(KRAKEN_STORE, sym, [], "unavailable", "not listed")
        if errors:
            return SourceSeries(KRAKEN_STORE, sym, [], "unavailable", "fetch-failed: KrakenError")
        pair_rows = next(v for k, v in body["result"].items() if k != "last")
        # [time s, o, h, l, c, vwap, base volume, trades]; quote volume = vwap * base volume
        rows = [(_day(bar[0]), float(bar[5]) * float(bar[6])) for bar in pair_rows]
    except Exception as exc:  # noqa: BLE001
        return SourceSeries(KRAKEN_STORE, sym, [], "unavailable", _failure_reason(exc))
    return _finish(KRAKEN_STORE, sym, rows, today)


FETCHERS = {"binance": fetch_binance, "coinbase": fetch_coinbase, "kraken": fetch_kraken}
