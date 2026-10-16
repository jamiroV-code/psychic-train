"""Exchange volume sources: Binance daily quote volume (history), Hyperliquid (forward only).

Binance quote volume is close * base volume of each completed UTC daily bar (ccxt
returns no quote-volume column), so it is an approximation. Hyperliquid reports a
rolling 24h notional; the snapshot is stored as the previous UTC day and history
builds forward one point per refresh. Fetchers never raise.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from api.data import hyperliquid_narrative_adapter
from api.data.attention.types import MIN_HISTORY_DAYS, SourceSeries

BINANCE_SOURCE = "exchange_volume"
HYPERLIQUID_SOURCE = "hyperliquid_volume"
LOOKBACK_DAYS = 100


def make_binance():
    import ccxt
    return ccxt.binance({"enableRateLimit": True})


def _classify(source: str, symbol: str, pts: list[tuple[date, float]]) -> SourceSeries:
    if not pts:
        return SourceSeries(source, symbol, [], "unavailable", "empty response")
    state = "ok" if len(pts) >= MIN_HISTORY_DAYS else "insufficient-history"
    return SourceSeries(source, symbol, pts, state, "" if state == "ok" else f"{len(pts)} days")


def fetch_binance_series(symbol: str, *, exchange=None, today: date | None = None) -> SourceSeries:
    sym = symbol.upper()
    today = today or datetime.now(timezone.utc).date()
    try:
        import ccxt
        ex = exchange if exchange is not None else make_binance()
        try:
            bars = ex.fetch_ohlcv(f"{sym}/USDT", "1d", limit=LOOKBACK_DAYS)
        except ccxt.RateLimitExceeded:
            return SourceSeries(BINANCE_SOURCE, sym, [], "unavailable", "rate-limited")
    except Exception as exc:
        return SourceSeries(BINANCE_SOURCE, sym, [], "unavailable", f"fetch-failed: {type(exc).__name__}")
    pts: dict[date, float] = {}
    for bar in bars or []:
        try:
            day = datetime.fromtimestamp(bar[0] / 1000, tz=timezone.utc).date()
            vol = float(bar[4]) * float(bar[5])
        except (TypeError, ValueError, IndexError):
            continue
        if day < today and vol == vol and vol >= 0:  # completed UTC days only
            pts[day] = vol
    return _classify(BINANCE_SOURCE, sym, sorted(pts.items()))


def fetch_hyperliquid_series(symbol: str, *, exchange=None, today: date | None = None,
                             snapshot=hyperliquid_narrative_adapter.fetch_daily_market_snapshot) -> SourceSeries:
    sym = symbol.upper()
    today = today or datetime.now(timezone.utc).date()
    try:
        snap = snapshot(exchange)
    except Exception as exc:
        return SourceSeries(HYPERLIQUID_SOURCE, sym, [], "unavailable", f"fetch-failed: {type(exc).__name__}")
    if snap.status != "ok":
        return SourceSeries(HYPERLIQUID_SOURCE, sym, [], "unavailable", snap.reason or "snapshot unavailable")
    for perp in snap.perps:
        if perp.base.upper() == sym and perp.quote_volume is not None:
            return _classify(HYPERLIQUID_SOURCE, sym, [(today - timedelta(days=1), perp.quote_volume)])
    return SourceSeries(HYPERLIQUID_SOURCE, sym, [], "unavailable", "symbol not listed or no volume")
