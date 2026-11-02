"""Hyperliquid fallback for the Equities page, used when London Strategic Edge (LSE) cannot serve a ticker.

Hyperliquid lists US stocks as HIP-3 perpetuals on the `xyz` deployer (`XYZ-NVDA/USDC:USDC`). Their daily bars are a
different instrument from the stock: the perp trades around the clock and tracks the price rather than being it, so
every result here carries `source="hyperliquid"` and the page labels the chart. Bars on NYSE-closed days are dropped so
the 200-session windows match the LSE series; the newest bar is the current (forming) UTC day.

* Own cache root `equities_hl/`, never mixed with the LSE bars in `equities/`: the two price series are not the same.
* `read_cached` is the one place that decides which series a ticker uses: LSE while it has fresh bars, else Hyperliquid
  when that cache holds newer bars, else whatever LSE reports (so an unlisted ticker still reads `bad-symbol`).
* Only tickers `XYZ-<TICKER>/USDC:USDC` lists and marks active qualify. Indices and look-alike tickers do not: Hyperliquid's
  plain `SPX` is the SPX6900 memecoin, and `XYZ-DXY` is delisted.
* Never raises; `reason` is a closed string, never exception text.
"""
from __future__ import annotations

import pandas as pd

from api.data import ccxt_adapter, lse_adapter
from api.data.equities_store import TICKER_RE
from api.data.freshness import as_utc
from api.data.lse_adapter import EquityOhlcvResult, OHLCV_COLUMNS

SOURCE = "hyperliquid"
CACHE_DIR = "equities_hl"
DEPLOYER = "XYZ"
HISTORY_DAYS = 2500
FETCH_LIMIT = 5000
CAVEATS = ("perp-not-spot", "trades-24-7", "bars-on-nyse-sessions-only")
PARQUET_ATTRS = {"source": SOURCE}


def market_symbol(ticker: str, exchange) -> str | None:
    """The active `XYZ-<ticker>/USDC:USDC` market, or None when Hyperliquid lists no such stock."""
    symbol = f"{DEPLOYER}-{ticker}/USDC:USDC"
    market = (getattr(exchange, "markets", None) or {}).get(symbol)
    if not market or market.get("active") is False:
        return None
    return symbol


def _result(ticker: str, timeframe: str, df: pd.DataFrame, status, reason) -> EquityOhlcvResult:
    return EquityOhlcvResult(ticker, timeframe, df, status, reason, source=SOURCE, caveats=list(CAVEATS))


def refresh_equity_hl(symbol: str, exchange=None, now=None) -> EquityOhlcvResult:
    """Fetch the ticker's daily perp bars once, then write `1d` and the derived `1w`. Never raises."""
    ticker = symbol.strip().upper() if isinstance(symbol, str) else ""
    empty = pd.DataFrame(columns=OHLCV_COLUMNS)
    try:
        if not TICKER_RE.match(ticker):
            return _result(ticker, "1d", empty, "bad_symbol", "invalid-ticker")
        now = as_utc(lse_adapter._now() if now is None else now)
        ex = exchange if exchange is not None else ccxt_adapter._exchange()
        if ex is None:
            return _result(ticker, "1d", empty, "unavailable", "network-error")
        market = market_symbol(ticker, ex)
        if market is None:
            return _result(ticker, "1d", empty, "bad_symbol", "unknown-ticker")
        since = int((now - pd.Timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
        with ccxt_adapter._exchange_lock:
            raw, failure = ccxt_adapter._fetch_with_backoff(ex, market, "1d", since, FETCH_LIMIT)
        if failure is not None:
            reason = "unknown-ticker" if failure == "bad_symbol" else "network-error"
            return _result(ticker, "1d", empty, failure, reason)
        bars = ccxt_adapter._raw_to_df(raw, source=SOURCE)
        sessions = bars["timestamp"].map(lambda ts: lse_adapter.is_nyse_session(ts.date()))
        daily = bars[sessions].drop_duplicates(subset="timestamp", keep="last").sort_values("timestamp")
        daily = daily.reset_index(drop=True)[OHLCV_COLUMNS]
        if daily.empty:
            return _result(ticker, "1d", empty, "unavailable", "no-data")
        weekly = ccxt_adapter._derive_weekly_from_daily(daily, SOURCE)
        lse_adapter._write_cache(ticker, "1d", daily, now, CACHE_DIR, PARQUET_ATTRS)
        lse_adapter._write_cache(ticker, "1w", weekly, now, CACHE_DIR, PARQUET_ATTRS)
        return _result(ticker, "1d", daily, "ok", "fetched")
    except Exception:  # noqa: BLE001 - the contract is never to raise
        return _result(ticker, "1d", empty, "unavailable", "network-error")


def read_hl_cached(symbol: str, timeframe: str, now=None) -> tuple[EquityOhlcvResult, pd.Timestamp | None]:
    """The cached Hyperliquid bars and their fetch time; `unavailable/no-data` when none."""
    ticker = symbol.strip().upper() if isinstance(symbol, str) else ""
    empty = pd.DataFrame(columns=OHLCV_COLUMNS)
    df = lse_adapter._read_cache(ticker, timeframe, CACHE_DIR) if TICKER_RE.match(ticker) else None
    if df is None or df.empty:
        return _result(ticker, timeframe, empty, "unavailable", "no-data"), None
    now = as_utc(lse_adapter._now() if now is None else now)
    result = lse_adapter._finish(ticker, timeframe, df, now, "fresh-cache")
    return (_result(ticker, timeframe, result.df, result.status, result.reason),
            lse_adapter._fetched_at(ticker, timeframe, CACHE_DIR))


def read_cached(symbol: str, timeframe: str, now=None) -> tuple[EquityOhlcvResult, pd.Timestamp | None]:
    """The series the Equities page and refresh schedule use for one ticker, from caches only.

    LSE while its bars are fresh; Hyperliquid when LSE has none or its newest bar is stale and Hyperliquid's cache
    holds newer bars; otherwise the LSE result unchanged (including its failure reason).
    """
    lse_result, lse_fetched = lse_adapter.read_cached_equity(symbol, timeframe, now=now)
    lse_empty = lse_result.df is None or lse_result.df.empty
    if not lse_empty and lse_result.status != "stale":
        return lse_result, lse_fetched
    hl_result, hl_fetched = read_hl_cached(symbol, timeframe, now=now)
    if hl_result.df.empty:
        return lse_result, lse_fetched
    if not lse_empty and hl_result.df["timestamp"].max() <= lse_result.df["timestamp"].max():
        return lse_result, lse_fetched
    return hl_result, hl_fetched


def needs_fallback(result: EquityOhlcvResult) -> bool:
    """True when an LSE refresh result cannot serve the ticker: nothing fetched, or the bars are stale."""
    if result.status in ("bad_symbol", "unavailable", "stale"):
        return True
    df = getattr(result, "df", None)
    return df is not None and df.empty
