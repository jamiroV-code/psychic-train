"""Synthetic equities fixtures for the S9A tests.

Every bar here is generated, never real LSE data (the licence forbids
redistribution). Callers must redirect the cache root (`isolated_cache`)
before seeding. The credential below is a made-up placeholder for tests that
need some value in the environment; it is not a real key.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import httpx
import pandas as pd

from api.data import lse_adapter

SYNTHETIC_CREDENTIAL = "synthetic-placeholder-0000"


def session_days(end: date, n: int) -> list[date]:
    """The last `n` NYSE sessions up to and including `end`."""
    days: list[date] = []
    d = end
    while len(days) < n:
        if lse_adapter.is_nyse_session(d):
            days.append(d)
        d -= timedelta(days=1)
    return sorted(days)


def daily_frame(end: date, n: int, base: float = 100.0) -> pd.DataFrame:
    """`n` synthetic daily bars ending at `end`; open differs from close."""
    days = session_days(end, n)
    closes = [base + 0.2 * i + 3.0 * math.sin(i / 5.0) for i in range(n)]
    opens = [c - 0.5 for c in closes]
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime([d.isoformat() for d in days], utc=True),
            "open": opens,
            "high": [c + 1.0 for c in closes],
            "low": [o - 1.0 for o in opens],
            "close": closes,
            "volume": [1000.0 + i for i in range(n)],
            "source": lse_adapter.SOURCE,
        }
    )[lse_adapter.OHLCV_COLUMNS]


def seed(ticker: str, end: date, n: int = 300, fetched_at=None, base: float = 100.0) -> pd.DataFrame:
    """Write `1d` and the derived `1w` for `ticker` into the (redirected) cache."""
    daily = daily_frame(end, n, base)
    fetched = pd.Timestamp(fetched_at) if fetched_at is not None else pd.Timestamp(end.isoformat()) + pd.Timedelta(hours=22)
    fetched = fetched.tz_localize("UTC") if fetched.tzinfo is None else fetched
    lse_adapter._write_cache(ticker, "1d", daily, fetched)
    weekly = lse_adapter._derive_weekly_from_daily(daily, lse_adapter.SOURCE)
    lse_adapter._write_cache(ticker, "1w", weekly, fetched)
    return daily


def candles_payload(end: date, n: int = 300, symbol: str = "TEST") -> list[dict]:
    """A synthetic candles response in the documented row shape."""
    df = daily_frame(end, n)
    return [
        {
            "symbol": symbol,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(r.volume),
            "timestamp": r.timestamp.strftime("%Y-%m-%dT00:00:00Z"),
        }
        for r in df.itertuples()
    ]


class CountingTransport(httpx.MockTransport):
    """A mock transport answering every GET with `payload`, counting calls."""

    def __init__(self, payload):
        self.calls = 0
        self.payload = payload
        super().__init__(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(200, json=self.payload)
