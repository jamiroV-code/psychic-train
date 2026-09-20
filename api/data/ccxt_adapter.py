"""ccxt (Hyperliquid) OHLCV adapter.

Adapter interface contract (Public Contracts): returns a typed result
(`OhlcvResult`) carrying an explicit `status` (`ok` | `unavailable` | `stale`
| `bad_symbol`) — never raises past this module's boundary into a router or
analytics call.

RFC-005 (19-09-26) — symbol resolution and failure honesty:

Watchlist tickers are bare coin names ("BTC"). ccxt's unified layer for
Hyperliquid requires a full market symbol ("BTC/USDC:USDC" for perps). The
original implementation passed the bare ticker straight through, which raises
`ccxt.BadSymbol` — an `ExchangeError`, NOT a `NetworkError` — and the old
blanket `except Exception` reported that as `unavailable`, i.e. "the exchange
is down." It was not down. That mislabel is what made the bug expensive to
find, so `bad_symbol` is now its own status and never collapses into
`unavailable`.

Symbols are RESOLVED against the exchange's own market list, never
constructed from a format string. A constructed fallback (`f"{t}/USDC:USDC"`)
was considered and deliberately rejected at VALIDATE (gap G3): it would fire
only when `load_markets()` failed — exactly when it could not be verified —
and an adapter that guesses about failure is the defect this module exists to
remove, merely relocated.

Timeframes: 15m/1h/4h/1d/1w (`1w` is derived once from cached/fetched daily
bars via real OHLC resampling — real weekly closes, per AC-1 — and cached,
never re-derived from daily on every request).

Deep-lookback calls pass `limit=5000` explicitly (Hyperliquid's underlying
API allows up to 5000 candles; ccxt's own `fetchOHLCV` default limit is only
500).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Literal

import ccxt
import pandas as pd

from api.data import cache
from api.data.cache import Timeframe

DEFAULT_LIMIT = 500
DEEP_LOOKBACK_LIMIT = 5000
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0

# The 60-period trend line (Amendment 2, AC-17) is the binding lookback
# requirement at every timeframe — RSI(14) always needs fewer bars than
# SMA(60). insufficient_history is therefore keyed off this single constant.
MIN_BARS_REQUIRED = 60

_TIMEFRAME_SECONDS: dict[str, int] = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
    # Unused for "1w" in practice: `fetch_ohlcv` returns from its `1w`
    # branch before `_cache_is_fresh` is consulted, so weekly bars are
    # re-derived from daily on every call. Kept for key-completeness only.
    "1w": 7 * 24 * 60 * 60,
}

_FETCHABLE_TIMEFRAMES = {"15m", "1h", "4h", "1d"}

Status = Literal["ok", "unavailable", "stale", "bad_symbol"]


@dataclass
class OhlcvResult:
    symbol: str
    timeframe: Timeframe
    df: pd.DataFrame
    insufficient_history: bool
    status: Status


# --------------------------------------------------------------------------
# Exchange singleton (RFC-005)
#
# The old `_exchange()` built a fresh `ccxt.hyperliquid()` per call, so every
# fetch paid a full `load_markets()` round trip before it could do anything —
# 16+ round trips for one board request. One instance per process, markets
# loaded once.
#
# Lock discipline (VALIDATE gap G2): `RLock`, not `Lock`. `fetch_ohlcv(sym,
# "1w")` recurses into `fetch_ohlcv(sym, "1d")`, and `1w` is on the board's
# hot path — a plain `Lock` held across the fetch would self-deadlock and hang
# the primary endpoint on first use. The lock is held only around exchange
# construction and the ccxt call itself, never across that recursion.
# --------------------------------------------------------------------------
_exchange_lock = threading.RLock()
_exchange_instance = None
_markets_unavailable = False


def _exchange():
    """Return the process-wide exchange, or None if its market list could not
    be loaded.

    `load_markets()` failure is terminal for the process (gap G4): it is
    cached rather than retried per-fetch, so a dead network degrades every
    symbol to `unavailable` quickly instead of re-timing-out on each call.
    Retry happens on the next process start.
    """
    global _exchange_instance, _markets_unavailable
    with _exchange_lock:
        if _markets_unavailable:
            return None
        if _exchange_instance is None:
            ex = ccxt.hyperliquid()
            try:
                ex.load_markets()
            except Exception:
                # Never raise past the adapter boundary (Public Contracts).
                _markets_unavailable = True
                return None
            _exchange_instance = ex
        return _exchange_instance


def reset_exchange_cache() -> None:
    """Test seam — drop the cached instance and the markets-failure latch."""
    global _exchange_instance, _markets_unavailable
    with _exchange_lock:
        _exchange_instance = None
        _markets_unavailable = False


def resolve_market_symbol(ticker: str, exchange) -> str | None:
    """Map a bare watchlist ticker ("BTC") to a ccxt unified market symbol
    ("BTC/USDC:USDC"), by lookup against the exchange's own market list.

    Returns None when the ticker matches no listed market — the caller turns
    that into `status="bad_symbol"`. Never constructs a symbol from a format
    string (gap G3).

    When the exchange exposes no usable market map — an injected test double,
    or markets that failed to load — the ticker is passed through UNCHANGED.
    That is not a fabricated symbol: it is the caller's own input, forwarded
    untouched so the underlying failure surfaces as itself rather than as a
    resolution error.
    """
    markets = getattr(exchange, "markets", None)
    if not markets:
        return ticker

    # Already a unified symbol.
    if ticker in markets:
        return ticker

    # Perpetual swap first — this is what the screener actually charts.
    for symbol, market in markets.items():
        if not market.get("swap"):
            continue
        if market.get("active") is False:
            continue
        if market.get("baseName") == ticker or market.get("base") == ticker:
            return symbol

    # Spot fallback for anything without a perp listing.
    for symbol, market in markets.items():
        if market.get("spot") and market.get("base") == ticker:
            return symbol

    return None


def _cache_is_fresh(cached: pd.DataFrame, timeframe: str) -> bool:
    """True when the newest cached bar is still within the current bar's
    still-open interval, i.e. no live call could possibly return anything
    new yet (Standing Rule 4).
    """
    if cached.empty:
        return False
    last_ts = cached["timestamp"].max()
    if pd.isna(last_ts):
        return False
    age = (pd.Timestamp.now(tz="UTC") - last_ts).total_seconds()
    return age < _TIMEFRAME_SECONDS[timeframe]


def _raw_to_df(raw: list, source: str) -> pd.DataFrame:
    df = pd.DataFrame(
        raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["source"] = source
    return df


def _fetch_with_backoff(
    exchange, symbol: str, timeframe: str, since, limit
) -> tuple[list | None, Status | None]:
    """Fetch OHLCV with exponential backoff on rate-limit errors.

    Returns `(raw, None)` on success, or `(None, status)` on failure, where
    `status` distinguishes a configuration error (`bad_symbol`) from a
    transport error (`unavailable`). Never raises past this function.

    RFC-005: the old single blanket `except Exception` collapsed both into
    `unavailable`. `BadSymbol` is an `ExchangeError`, so it landed in the
    branch commented "malformed/unexpected payload" and was reported as an
    outage. Those are different facts and callers need to tell them apart.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return (
                exchange.fetch_ohlcv(
                    symbol, timeframe=timeframe, since=since, limit=limit
                ),
                None,
            )
        except ccxt.RateLimitExceeded:
            if attempt == MAX_RETRIES - 1:
                return (None, "unavailable")
            time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
            continue
        except ccxt.BadSymbol:
            # Configuration error, not an outage. Retrying cannot help.
            return (None, "bad_symbol")
        except ccxt.NetworkError:
            return (None, "unavailable")
        except ccxt.ExchangeError:
            # Exchange rejected the request for a non-transport reason.
            # Distinct from a network outage; treated as a symbol/config
            # problem rather than silently reported as downtime.
            return (None, "bad_symbol")
        except Exception:
            # Malformed/unexpected payload or any other adapter-boundary
            # failure — never raise past the adapter (Public Contracts).
            return (None, "unavailable")
    return (None, "unavailable")


# --------------------------------------------------------------------------
# Week anchor (ADR-5, 19-09-26) — Monday-open, left-labelled.
#
# The previous implementation used a bare `resample("W")`. Pandas reads "W"
# as `W-SUN` with closed="right", label="right": it groups Monday..Sunday
# correctly, but stamps each bucket with the week's CLOSE date. Exchange
# weekly candles are stamped with their OPEN. Every derived weekly bar was
# therefore six days late, and the still-forming week was stamped with a
# Sunday that had not happened yet — a bar dated in the future.
#
# `W-MON` + closed="left" + label="left" produces byte-identical OHLCV
# membership (same open/high/low/close/volume per bucket — only the index
# label moves) and stamps each bar with its Monday open. Because the values
# never moved, no indicator computed over the close *sequence* (weekly RSI,
# the 60-period SMA) was ever wrong; the chart placement and any
# cross-timeframe date join were.
#
# `write_ohlcv` overwrites the whole series on every refresh, so existing
# Sunday-labelled `1w.parquet` files self-heal on the next board request —
# there is no migration step.
#
# The still-forming week is deliberately KEPT, labelled with its Monday like
# every other bar, so the weekly momentum leg reflects the current week
# rather than lagging it by up to six days. This is the single carve-out
# from Standing Rule 4 (closed bars are immutable): the newest weekly bar is
# mutable until its week closes; every earlier bar is immutable. Callers
# that need only closed weeks must drop the last row explicitly.
# --------------------------------------------------------------------------
WEEK_ANCHOR = "W-MON"
WEEK_CLOSED = "left"
WEEK_LABEL = "left"


def _derive_weekly_from_daily(daily_df: pd.DataFrame, source: str) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame(columns=cache.OHLCV_COLUMNS)
    indexed = daily_df.set_index("timestamp")
    weekly = (
        indexed.resample(WEEK_ANCHOR, closed=WEEK_CLOSED, label=WEEK_LABEL)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["close"])
    )
    weekly = weekly.reset_index()
    weekly["source"] = source
    return weekly[cache.OHLCV_COLUMNS]


def _source_label(exchange, daily_df=None) -> str:
    """Name the source for a derived weekly bar.

    `fetch_ohlcv`'s `1w` branch no longer constructs an exchange when the
    daily leg is served from a fresh cache, so `exchange` can legitimately be
    None here. Fall back to the source already recorded on the daily bars
    rather than mislabelling the derivation "unknown".
    """
    if exchange is not None:
        return getattr(exchange, "id", "unknown")
    if daily_df is not None and "source" in daily_df.columns and len(daily_df):
        return str(daily_df["source"].iloc[-1])
    return "unknown"


def _result(symbol, timeframe, df, status: Status) -> OhlcvResult:
    return OhlcvResult(
        symbol=symbol,
        timeframe=timeframe,
        df=df,
        insufficient_history=len(df) < MIN_BARS_REQUIRED,
        status=status,
    )


def fetch_ohlcv(
    symbol: str,
    timeframe: Timeframe,
    since: int | None = None,
    limit: int | None = None,
    exchange=None,
) -> OhlcvResult:
    """Fetch (or derive) OHLCV bars for one (symbol, timeframe), cache-first.

    `symbol` is a bare watchlist ticker ("BTC"); it is resolved to a ccxt
    unified market symbol internally. Returns a typed `OhlcvResult` — never
    raises.
    """
    cache.bootstrap_cache_dirs()

    # `1w` is derived from daily, never fetched. Recurse BEFORE taking any
    # lock (gap G2) — the inner call does its own locking — and before any
    # exchange work, since the derivation itself needs no market list.
    if timeframe == "1w":
        daily = fetch_ohlcv(symbol, "1d", since=since, limit=limit, exchange=exchange)
        if daily.status == "bad_symbol":
            return _result(symbol, "1w", cache.read_ohlcv(symbol, "1w"), "bad_symbol")
        weekly_df = _derive_weekly_from_daily(daily.df, source=_source_label(exchange, daily.df))
        if not weekly_df.empty:
            cache.write_ohlcv(symbol, "1w", weekly_df)
        return _result(symbol, "1w", cache.read_ohlcv(symbol, "1w"), daily.status)

    cached = cache.read_ohlcv(symbol, timeframe)

    # Skip the live call entirely once the cache already covers the current,
    # not-yet-closed bar for this timeframe (Standing Rule 4).
    #
    # This check sits ABOVE exchange construction, not below it (moved
    # 19-09-26). Previously `_exchange()` ran first, so every warm request
    # paid a `load_markets()` round trip whose result was then discarded one
    # branch later — the exact per-call overhead RFC-005 set out to remove,
    # left in place for the warm path. It also made an offline run
    # impossible: a fully seeded cache still could not be served without
    # reaching the network, which is what the Playwright E2E needs.
    #
    # Nothing is lost by ordering it this way. A fresh cache is served
    # identically whether or not a market list was loaded first.
    if since is None and _cache_is_fresh(cached, timeframe):
        return _result(symbol, timeframe, cached, "ok")

    injected = exchange is not None
    if not injected:
        exchange = _exchange()
        if exchange is None:
            # Market list unavailable for this process (gap G4). Serve
            # whatever is cached and say plainly that the source is down.
            return _result(symbol, timeframe, cached, "unavailable")

    market_symbol = resolve_market_symbol(symbol, exchange)
    if market_symbol is None:
        # Ticker matches no listed market. This is a configuration fact, not
        # an outage — say so (gap G3).
        return _result(symbol, timeframe, cached, "bad_symbol")

    effective_limit = limit or DEFAULT_LIMIT
    effective_since = since
    if effective_since is None and not cached.empty:
        effective_since = int(cached["timestamp"].max().timestamp() * 1000)

    with _exchange_lock:
        raw, failure = _fetch_with_backoff(
            exchange, market_symbol, timeframe, effective_since, effective_limit
        )

    if failure is not None:
        # Serve cache, mark the real reason — never a silent stale-reuse
        # pretending to be fresh, and never an outage label on a config error.
        return _result(symbol, timeframe, cached, failure)

    try:
        fetched = _raw_to_df(raw, source=getattr(exchange, "id", "unknown"))
    except Exception:
        return _result(symbol, timeframe, cached, "unavailable")

    merged = pd.concat([cached, fetched], ignore_index=True) if not cached.empty else fetched
    cache.write_ohlcv(symbol, timeframe, merged)
    return _result(symbol, timeframe, cache.read_ohlcv(symbol, timeframe), "ok")
