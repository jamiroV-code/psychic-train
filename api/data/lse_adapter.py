"""London Strategic Edge (LSE) equities adapter — daily/weekly US equity bars (S3).

Private use only: LSE data may not be redistributed without a separate licence
(`process/context/data-sources/all-data-sources.md` §Licensing), so every
result carries `redistributable=False` and every cached parquet carries the
footer tag `mysite.redistributable=false`.

Verified behaviour (`lse-data-verification_17-09-26/findings.md`): rows are
`{symbol, open, high, low, close, volume, timestamp ISO}`, at most 5000 per
request; the feed also has bars on NYSE-closed days (filtered here by an
explicit session calendar); delisted tickers 404 (survivorship bias); series
are split-adjusted only; the daily close can include extended-hours trades.

ASSUMED until the user-PC probe (`s3-probe/lse_probe.py`) confirms them:
`BASE_URL`, `CANDLES_PATH`, the header auth scheme (`AUTH_HEADER`), the query
parameter names, and the bar-timestamp convention (bars are keyed by the UTC
calendar date of `timestamp`). They are isolated constants for that reason.

Public contract: `fetch_equity_ohlcv` never raises past this module and never
logs; `reason` is a closed enum string, never exception text. The API key is
read from the environment at call time and travels only in a request header.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import httpx
import pandas as pd

from api.data import cache
from api.data.ccxt_adapter import _derive_weekly_from_daily
from api.data.equities_store import TICKER_RE

BASE_URL = "https://londonstrategicedge.com/api"  # ASSUMED (probe P-S3-1)
CANDLES_PATH = "/vault/candles"  # ASSUMED (probe P-S3-1)
AUTH_HEADER = "Authorization"  # ASSUMED scheme: "Bearer <key>" (probe P-S3-1)
TIMEOUT = httpx.Timeout(15.0)
MAX_ROWS_PER_REQUEST = 5000
DAILY_HISTORY_DAYS = 2500  # ~7 years of sessions, well under the 5000-row cap
FRESH_TTL_SECONDS = 6 * 60 * 60
STALE_AFTER = pd.Timedelta(days=6)  # longest normal NYSE gap is a 4-day weekend
SOURCE = "lse"
SIDECAR_SCHEMA = 1

Status = Literal["ok", "unavailable", "stale", "bad_symbol"]
Reason = Literal[
    "fresh-cache",
    "fetched",
    "missing-key",
    "unsupported-timeframe",
    "invalid-ticker",
    "unknown-ticker",
    "auth-rejected",
    "rate-limited",
    "http-error",
    "timeout",
    "network-error",
    "bad-payload",
    "no-data",
    "newest-bar-old",
]

CAVEATS = (
    "split-adjusted-only",
    "close-may-include-extended-hours",
    "survivorship-bias",
    "special-closures-not-modelled",
)
PARQUET_ATTRS = {"mysite.redistributable": "false", "source": SOURCE}
OHLCV_COLUMNS = cache.OHLCV_COLUMNS


@dataclass
class EquityOhlcvResult:
    symbol: str
    timeframe: str
    df: pd.DataFrame  # cache.OHLCV_COLUMNS
    status: Status
    reason: Reason
    redistributable: bool = False
    source: str = SOURCE
    caveats: list[str] = field(default_factory=lambda: list(CAVEATS))


def _now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


# --- NYSE session calendar (D11) --------------------------------------------
# An explicit rule set, NOT pandas' USFederalHolidayCalendar: that calendar
# observes a Saturday New Year on the Friday before (NYSE stays open) and
# includes Columbus and Veterans Day (NYSE open). Special one-off closures
# (2007-01-02, 2012-10-29/30, 2018-12-05, 2025-01-09) are not modelled.


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    # Anonymous Gregorian computus.
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month = (h + m - 7 * n + 114) // 31
    day = (h + m - 7 * n + 114) % 31 + 1
    return date(year, month, day)


def _observed(d: date) -> date:
    """Saturday holiday -> Friday, Sunday holiday -> Monday."""
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def nyse_holidays(year: int) -> set[date]:
    new_year = date(year, 1, 1)
    days = {
        # A Saturday New Year is NOT observed (Dec 31 trades); Sunday -> Monday.
        new_year + timedelta(days=1) if new_year.weekday() == 6 else new_year,
        _nth_weekday(year, 1, 0, 3),  # MLK
        _nth_weekday(year, 2, 0, 3),  # Presidents
        _easter(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),  # Labor
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        days.add(_observed(date(year, 6, 19)))  # Juneteenth
    return days


def is_nyse_session(d: date) -> bool:
    return d.weekday() < 5 and d not in nyse_holidays(d.year)


# --- parsing -----------------------------------------------------------------


def extract_rows(payload) -> list[dict]:
    """The row list of a candles response: a bare list, or a list under a
    wrapper key. Raises ValueError on any other shape."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "candles", "rows", "results"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError("unrecognised candles payload")


def parse_candles(payload) -> pd.DataFrame:
    """Documented row shape -> `cache.OHLCV_COLUMNS` frame of NYSE sessions.

    Bars are keyed by the UTC calendar date of `timestamp` (normalised to
    00:00 UTC like the crypto daily bars); non-session days are dropped and a
    duplicated date keeps its last row.
    """
    rows = extract_rows(payload)
    if not rows:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    df = pd.DataFrame(rows)
    missing = {"timestamp", "open", "high", "low", "close", "volume"} - set(df.columns)
    if missing:
        raise ValueError("candles rows missing required keys")
    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(df["timestamp"], utc=True).dt.floor("D"),
            **{c: pd.to_numeric(df[c]).astype("float64") for c in ("open", "high", "low", "close", "volume")},
        }
    )
    sessions = out["timestamp"].map(lambda ts: is_nyse_session(ts.date()))
    out = out[sessions].drop_duplicates(subset="timestamp", keep="last")
    out = out.sort_values("timestamp").reset_index(drop=True)
    out["source"] = SOURCE
    return out[OHLCV_COLUMNS]


# --- cache -------------------------------------------------------------------


def equity_cache_dir(symbol: str) -> Path:
    # cache.CACHE_ROOT is read at call time so `isolated_cache` redirects it.
    return cache.CACHE_ROOT / "equities" / symbol


def equity_parquet_path(symbol: str, timeframe: str) -> Path:
    return equity_cache_dir(symbol) / f"{timeframe}.parquet"


def _sidecar_path(symbol: str, timeframe: str) -> Path:
    return equity_cache_dir(symbol) / f"{timeframe}.meta.json"


def _write_cache(symbol: str, timeframe: str, df: pd.DataFrame, fetched_at: pd.Timestamp) -> None:
    path = equity_parquet_path(symbol, timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    tagged = df.copy()
    tagged.attrs = dict(PARQUET_ATTRS)
    cache._atomic_to_parquet(tagged, path)
    sidecar = _sidecar_path(symbol, timeframe)
    fd, tmp = tempfile.mkstemp(dir=sidecar.parent, prefix=f".{sidecar.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump({"fetched_at": fetched_at.isoformat(), "schema": SIDECAR_SCHEMA}, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, sidecar)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_cache(symbol: str, timeframe: str) -> pd.DataFrame | None:
    path = equity_parquet_path(symbol, timeframe)
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df[OHLCV_COLUMNS]


def _fetched_at(symbol: str, timeframe: str) -> pd.Timestamp | None:
    try:
        meta = json.loads(_sidecar_path(symbol, timeframe).read_text())
        return pd.Timestamp(meta["fetched_at"]).tz_convert("UTC")
    except Exception:
        return None


def _is_fresh(symbol: str, timeframe: str, now: pd.Timestamp) -> bool:
    fetched = _fetched_at(symbol, timeframe)
    if fetched is None or not equity_parquet_path(symbol, timeframe).exists():
        return False
    return pd.Timedelta(0) <= now - fetched < pd.Timedelta(seconds=FRESH_TTL_SECONDS)


# --- network -----------------------------------------------------------------


def _request_daily(symbol: str, key: str, now: pd.Timestamp, transport) -> tuple[pd.DataFrame | None, Status, Reason]:
    params = {
        "symbol": symbol,
        "timeframe": "1d",
        "start": (now - pd.Timedelta(days=DAILY_HISTORY_DAYS)).date().isoformat(),
        "limit": MAX_ROWS_PER_REQUEST,
        "order": "asc",
    }
    try:
        with httpx.Client(transport=transport, timeout=TIMEOUT) as client:
            resp = client.get(
                BASE_URL + CANDLES_PATH,
                params=params,
                headers={AUTH_HEADER: f"Bearer {key}"},
                timeout=TIMEOUT,
            )
    except httpx.TimeoutException:
        return None, "unavailable", "timeout"
    except httpx.HTTPError:
        return None, "unavailable", "network-error"
    except Exception:
        return None, "unavailable", "network-error"

    code = resp.status_code
    if code == 404:
        return None, "bad_symbol", "unknown-ticker"
    if code in (401, 403):
        return None, "unavailable", "auth-rejected"
    if code == 429:
        return None, "unavailable", "rate-limited"
    if code != 200:
        return None, "unavailable", "http-error"
    try:
        df = parse_candles(resp.json())
    except Exception:
        return None, "unavailable", "bad-payload"
    if df.empty:
        return None, "unavailable", "no-data"
    return df, "ok", "fetched"


def _with_cached(symbol: str, timeframe: str, status: Status, reason: Reason) -> EquityOhlcvResult:
    """A failure result that still serves any cached bars (as `stale`)."""
    cached = _read_cache(symbol, timeframe)
    if status == "unavailable" and cached is not None and not cached.empty and reason != "missing-key":
        status = "stale"
    df = cached if cached is not None else pd.DataFrame(columns=OHLCV_COLUMNS)
    return EquityOhlcvResult(symbol, timeframe, df, status, reason)


def fetch_equity_ohlcv(symbol: str, timeframe: str, transport=None, now=None) -> EquityOhlcvResult:
    """Daily (`1d`) or Monday-anchored weekly (`1w`) bars for one US equity.

    Serves the cache when its `fetched_at` sidecar is under 6 h old; otherwise
    one GET for ~7 years of daily bars. `1w` is always derived from the daily
    bars with `ccxt_adapter._derive_weekly_from_daily`. Never raises.
    """
    ticker = symbol.strip().upper() if isinstance(symbol, str) else ""
    empty = pd.DataFrame(columns=OHLCV_COLUMNS)
    if timeframe not in ("1d", "1w"):
        return EquityOhlcvResult(ticker, timeframe, empty, "unavailable", "unsupported-timeframe")
    if not TICKER_RE.match(ticker):
        return EquityOhlcvResult(ticker, timeframe, empty, "bad_symbol", "invalid-ticker")
    now = _now() if now is None else pd.Timestamp(now)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")

    if _is_fresh(ticker, timeframe, now):
        cached = _read_cache(ticker, timeframe)
        if cached is not None:
            return _finish(ticker, timeframe, cached, now, "fresh-cache")

    key = os.environ.get("LSE_API_KEY")
    if not key:
        return _with_cached(ticker, timeframe, "unavailable", "missing-key")

    daily, status, reason = _request_daily(ticker, key, now, transport)
    if daily is None:
        return _with_cached(ticker, timeframe, status, reason)

    _write_cache(ticker, "1d", daily, now)
    weekly = _derive_weekly_from_daily(daily, SOURCE)
    _write_cache(ticker, "1w", weekly, now)
    return _finish(ticker, timeframe, daily if timeframe == "1d" else weekly, now, reason)


def _finish(symbol: str, timeframe: str, df: pd.DataFrame, now: pd.Timestamp, reason: Reason) -> EquityOhlcvResult:
    if df.empty:
        return EquityOhlcvResult(symbol, timeframe, df, "unavailable", "no-data")
    # Weekly bars are judged on the newest daily bar they contain (label is the
    # Monday open), so use the daily leg's freshness rule on the last open + 4d.
    newest = df["timestamp"].iloc[-1] + (pd.Timedelta(days=4) if timeframe == "1w" else pd.Timedelta(0))
    if now - newest > STALE_AFTER:
        return EquityOhlcvResult(symbol, timeframe, df, "stale", "newest-bar-old")
    return EquityOhlcvResult(symbol, timeframe, df, "ok", reason)
