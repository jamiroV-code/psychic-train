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

T32 / S1 (04-10-26) — freshness core:

* The cache is fresh only if it was fetched inside the current bar and less
  than `freshness.FORMING_TTL` ago (B4), so the forming candle expires. The
  fetch time lives in a sidecar next to the parquet (`cache.read_fetched_at`).
* A refresh with `since=None` asks for the LATEST `TAIL_LIMIT` bars (B3)
  instead of the oldest bars after the cached tail, which could never catch
  up a cache more than one request behind (the gap bug). A tail that does
  not touch the cache replaces sub-daily history (`note="gap-replaced"`) and
  is appended to daily history (`note="gap-kept"`).
* 15m/1h/4h keep their newest 200 bars on every write (B2).
* On the `since=None` path a newest bar older than `freshness.is_stale`
  allows reports `status="stale"`; the explicit-`since` path (backfill) never
  does.
* Clock skew against the exchange is measured opportunistically on the live
  path, at most once per 15 minutes (B6).

T35 / S8 (04-10-26) — background refresh worker (B9):

* `cached_reads_only()` is a context manager (a `ContextVar` flag). Inside
  it `fetch_ohlcv` serves the cache with ZERO exchange work and, for a pair
  that is not fresh (a missing file included), calls the registered refresh
  hook (`set_refresh_hook`) and marks the result `note="refresh-queued"`.
  Outside it, behaviour is exactly S1's fetch-through.
* `retry_markets_if_latched()` clears the market-load latch once, so the
  worker's next tick retries `load_markets()` (never per fetch).
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Callable, Iterator, Literal

import ccxt
import pandas as pd

from api.data import cache, freshness
from api.data.cache import Timeframe

DEFAULT_LIMIT = 500
DEEP_LOOKBACK_LIMIT = 5000
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0

# The 60-period trend line (Amendment 2, AC-17) is the binding lookback
# requirement at every timeframe — RSI(14) always needs fewer bars than
# SMA(60). insufficient_history is therefore keyed off this single constant.
MIN_BARS_REQUIRED = 60

_TIMEFRAME_SECONDS: dict[str, int] = freshness.TIMEFRAME_SECONDS

# Clock skew (B6): cached this long per process; warn above the threshold.
SKEW_CACHE_SECONDS = 15 * 60
SKEW_WARNING_SECONDS = 120.0

_FETCHABLE_TIMEFRAMES = {"15m", "1h", "4h", "1d"}

Status = Literal["ok", "unavailable", "stale", "bad_symbol"]


@dataclass
class OhlcvResult:
    symbol: str
    timeframe: Timeframe
    df: pd.DataFrame
    insufficient_history: bool
    status: Status
    # T32 / S1: appended after `status` and defaulted, so positional callers
    # that pass the first five fields keep working.
    fetched_at: pd.Timestamp | None = None
    note: str | None = None


def _now() -> pd.Timestamp:
    """The adapter's clock (host UTC). Tests replace it."""
    return pd.Timestamp.now(tz="UTC")


def _host_time() -> float:
    """Raw host clock for the skew bracket. Tests replace it."""
    return time.time()


# --------------------------------------------------------------------------
# Clock skew (B6)
#
# Measured inside the live fetch path only, reusing the process-wide
# exchange: `fetch_time` bracketed by two host reads, skew = host midpoint
# minus exchange time (positive = host clock ahead). Cached for 15 minutes,
# including an "unknown" result, so a missing or failing `fetch_time` costs
# one attempt per window and never an error.
# --------------------------------------------------------------------------
_skew_lock = threading.Lock()
_skew_value: float | None = None
_skew_measured_at: pd.Timestamp | None = None


def reset_clock_skew() -> None:
    """Test seam — forget the measured skew."""
    global _skew_value, _skew_measured_at
    with _skew_lock:
        _skew_value = None
        _skew_measured_at = None


def last_clock_skew() -> float | None:
    """Last measured skew in seconds, or None when unknown."""
    return _skew_value


def clock_skew_warning(skew: float | None) -> bool:
    return skew is not None and abs(skew) > SKEW_WARNING_SECONDS


def reference_now(now: pd.Timestamp | None = None) -> pd.Timestamp:
    """Host clock corrected by the measured skew when known (B5)."""
    now = _now() if now is None else now
    skew = last_clock_skew()
    return now if skew is None else now - pd.Timedelta(seconds=skew)


def refresh_clock_skew(exchange) -> None:
    """Measure the skew unless a measurement is younger than 15 minutes."""
    global _skew_value, _skew_measured_at
    now = _now()
    with _skew_lock:
        if _skew_measured_at is not None and (now - _skew_measured_at).total_seconds() < SKEW_CACHE_SECONDS:
            return
        _skew_measured_at = now
        _skew_value = None
        fetch_time = getattr(exchange, "fetch_time", None)
        if not callable(fetch_time):
            return
        try:
            before = _host_time()
            exchange_ms = fetch_time()
            after = _host_time()
            if exchange_ms is None:
                return
            _skew_value = (before + after) / 2.0 - float(exchange_ms) / 1000.0
        except Exception:
            # Unknown, not an error (never raise past the adapter).
            _skew_value = None


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


def retry_markets_if_latched() -> bool:
    """Clear the market-load latch so the next fetch retries `load_markets()`.

    Called once per refresh-worker tick (N1). `_exchange()` keeps its
    per-fetch latch, so within one tick a dead network still costs one
    `load_markets()` attempt, not one per pair. Returns True when a latch was
    cleared.
    """
    global _markets_unavailable
    with _exchange_lock:
        if not _markets_unavailable:
            return False
        _markets_unavailable = False
        return True


# --------------------------------------------------------------------------
# Cache-only reads (T35 / S8, B9)
#
# While the background refresh worker runs, page reads must never wait on
# the exchange: the router wraps them in `cached_reads_only()`, and the
# worker refreshes whatever those reads report as not fresh. The hook is
# expected to be non-blocking (the worker only enqueues).
# --------------------------------------------------------------------------
_cached_reads_only: ContextVar[bool] = ContextVar("screener_cached_reads_only", default=False)
_refresh_hook: Callable[[str, str], object] | None = None


@contextmanager
def cached_reads_only() -> Iterator[None]:
    """Serve `fetch_ohlcv` from the cache only, for the current context."""
    token = _cached_reads_only.set(True)
    try:
        yield
    finally:
        _cached_reads_only.reset(token)


def set_refresh_hook(hook: Callable[[str, str], object] | None) -> None:
    """Register (or clear, with None) the `request_refresh(symbol, timeframe)`
    callback used by cache-only reads."""
    global _refresh_hook
    _refresh_hook = hook


def _cached_only_result(symbol, timeframe, cached, fetched_at) -> OhlcvResult:
    note = None
    hook = _refresh_hook
    if hook is not None and not _cache_is_fresh(cached, timeframe, fetched_at):
        try:
            hook(symbol, timeframe)
            note = "refresh-queued"
        except Exception:
            # A failing hook must never break a page read.
            note = None
    if cached.empty:
        return _result(symbol, timeframe, cached, "unavailable", None, note)
    return _result(symbol, timeframe, cached, _tail_status(cached, timeframe), fetched_at, note)


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


def _cache_is_fresh(
    cached: pd.DataFrame,
    timeframe: str,
    fetched_at: pd.Timestamp | None = None,
    now: pd.Timestamp | None = None,
) -> bool:
    """True when the cache was fetched inside the current bar and within the
    timeframe's forming-candle TTL (B4, `freshness.cache_is_fresh`).

    The old rule (newest bar younger than one timeframe) served a forming
    candle for up to a whole bar interval after it was fetched.
    """
    if cached.empty:
        return False
    return freshness.cache_is_fresh(fetched_at, timeframe, _now() if now is None else now)


def _tail_since(timeframe: str, now: pd.Timestamp) -> int | None:
    """Request start for the tail fetch (B3). None asks the exchange for its
    latest bars. Fallback, should the PC probe show `since=None` does not
    return the latest bars:
    `now_ms - (TAIL_LIMIT - 1) * timeframe_ms`.
    """
    return None


def _tail_status(df: pd.DataFrame, timeframe: str) -> Status:
    """B5 on the newest bar, `since=None` path only."""
    if df.empty:
        return "ok"
    return "stale" if freshness.is_stale(df["timestamp"].max(), timeframe, reference_now()) else "ok"


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


def _result(symbol, timeframe, df, status: Status, fetched_at=None, note=None) -> OhlcvResult:
    return OhlcvResult(
        symbol=symbol,
        timeframe=timeframe,
        df=df,
        insufficient_history=len(df) < MIN_BARS_REQUIRED,
        status=status,
        fetched_at=fetched_at,
        note=note,
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
            return _result(symbol, "1w", cache.read_ohlcv(symbol, "1w"), "bad_symbol", daily.fetched_at)
        weekly_df = _derive_weekly_from_daily(daily.df, source=_source_label(exchange, daily.df))
        if not weekly_df.empty:
            # `1w` stores its daily leg's fetch time (B1).
            cache.write_ohlcv(symbol, "1w", weekly_df, fetched_at=daily.fetched_at)
        return _result(
            symbol, "1w", cache.read_ohlcv(symbol, "1w"), daily.status, daily.fetched_at, daily.note
        )

    cached = cache.read_ohlcv(symbol, timeframe)
    fetched_at = cache.read_fetched_at(symbol, timeframe) if not cached.empty else None

    if _cached_reads_only.get():
        # Worker running (S8): never touch the exchange from a read.
        return _cached_only_result(symbol, timeframe, cached, fetched_at)

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
    tail = since is None
    if tail and _cache_is_fresh(cached, timeframe, fetched_at):
        return _result(symbol, timeframe, cached, _tail_status(cached, timeframe), fetched_at)

    injected = exchange is not None
    if not injected:
        exchange = _exchange()
        if exchange is None:
            # Market list unavailable for this process (gap G4). Serve
            # whatever is cached and say plainly that the source is down.
            return _result(symbol, timeframe, cached, "unavailable", fetched_at)
        refresh_clock_skew(exchange)

    market_symbol = resolve_market_symbol(symbol, exchange)
    if market_symbol is None:
        # Ticker matches no listed market. This is a configuration fact, not
        # an outage — say so (gap G3).
        return _result(symbol, timeframe, cached, "bad_symbol", fetched_at)

    if tail:
        effective_since = _tail_since(timeframe, _now())
        effective_limit = limit or freshness.TAIL_LIMIT[timeframe]
    else:
        effective_since = since
        effective_limit = limit or DEFAULT_LIMIT

    with _exchange_lock:
        raw, failure = _fetch_with_backoff(
            exchange, market_symbol, timeframe, effective_since, effective_limit
        )

    if failure is not None:
        # Serve cache, mark the real reason — never a silent stale-reuse
        # pretending to be fresh, and never an outage label on a config error.
        # Cache and fetch time stay as they were.
        return _result(symbol, timeframe, cached, failure, fetched_at)

    try:
        fetched = _raw_to_df(raw, source=getattr(exchange, "id", "unknown"))
    except Exception:
        return _result(symbol, timeframe, cached, "unavailable", fetched_at)

    retain = freshness.RETAIN_BARS.get(timeframe)

    if not tail:
        # Explicit `since` (backfill): today's merge, never `stale`.
        merged = pd.concat([cached, fetched], ignore_index=True) if not cached.empty else fetched
        stamp = _now()
        cache.write_ohlcv(symbol, timeframe, merged, retain_bars=retain, fetched_at=stamp)
        return _result(symbol, timeframe, cache.read_ohlcv(symbol, timeframe), "ok", stamp)

    if fetched.empty:
        # A successful empty response writes nothing (D5).
        return _result(symbol, timeframe, cached, _tail_status(cached, timeframe), fetched_at)

    note = None
    if cached.empty:
        merged = fetched
    else:
        step = pd.Timedelta(seconds=_TIMEFRAME_SECONDS[timeframe])
        contiguous = fetched["timestamp"].min() <= cached["timestamp"].max() + step
        if contiguous:
            # Newest wins: `write_ohlcv` dedupes with keep="last".
            merged = pd.concat([cached, fetched], ignore_index=True)
        elif timeframe == "1d":
            # Deep daily history is kept; the hole stays a hole (D18).
            merged = pd.concat([cached, fetched], ignore_index=True)
            note = "gap-kept"
        else:
            merged = fetched
            note = "gap-replaced"

    stamp = _now()
    cache.write_ohlcv(symbol, timeframe, merged, retain_bars=retain, fetched_at=stamp)
    stored = cache.read_ohlcv(symbol, timeframe)
    return _result(symbol, timeframe, stored, _tail_status(stored, timeframe), stamp, note)
