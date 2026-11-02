"""US Dollar Index (DXY), reconstructed daily from the ECB's euro foreign-exchange reference rates.

The ICE index is proprietary and no free feed carries it (Stooq now needs a browser, Hyperliquid's `XYZ-DXY` is
delisted, FRED has only the Fed's broad-dollar index). Its formula is public: a geometric weighted mean of six
currencies against the dollar,

    DXY = 50.14348112 * EURUSD^-0.576 * USDJPY^0.136 * GBPUSD^-0.119 * USDCAD^0.091 * USDSEK^0.042 * USDCHF^0.036

so it is rebuilt from `api.frankfurter.dev`, a free keyless mirror of the ECB reference rates (one fixing per TARGET
business day, around 14:15 CET, history back to 1999). The result is a CLOSE-ONLY series: open, high and low equal
the close and volume is 0. It differs from ICE's New York close by the time-of-day gap, 0.2-0.4% on the dates
checked against remembered closes (2024-12-31, 2025-01-13, 2025-06-30), so the page labels it a reconstruction.
"""
from __future__ import annotations

import httpx
import pandas as pd

from api.data import cache

SOURCE = "ecb"
URL = "https://api.frankfurter.dev/v1/{start}..{end}"
CURRENCIES = ("EUR", "JPY", "GBP", "CAD", "SEK", "CHF")
HISTORY_DAYS = 1500
TIMEOUT = 30.0


def dxy_from_rates(rates: dict[str, float]) -> float:
    """The index for one day's `USD -> currency` rates (units of the currency per dollar)."""
    return (
        50.14348112
        * (1 / rates["EUR"]) ** -0.576
        * rates["JPY"] ** 0.136
        * (1 / rates["GBP"]) ** -0.119
        * rates["CAD"] ** 0.091
        * rates["SEK"] ** 0.042
        * rates["CHF"] ** 0.036
    )


def fetch_dxy_daily(now: pd.Timestamp, client: httpx.Client | None = None) -> pd.DataFrame:
    """Daily bars (cache.OHLCV_COLUMNS) for the last `HISTORY_DAYS`; raises on any transport or payload problem."""
    start = (now - pd.Timedelta(days=HISTORY_DAYS)).date().isoformat()
    url = URL.format(start=start, end=now.date().isoformat())
    own = client is None
    client = client or httpx.Client(follow_redirects=True)
    try:
        resp = client.get(url, params={"base": "USD", "symbols": ",".join(CURRENCIES)}, timeout=TIMEOUT)
        resp.raise_for_status()
        rates = resp.json()["rates"]
    finally:
        if own:
            client.close()
    rows = []
    for day in sorted(rates):
        if all(isinstance(rates[day].get(c), (int, float)) and rates[day][c] > 0 for c in CURRENCIES):
            rows.append((pd.Timestamp(day, tz="UTC"), dxy_from_rates(rates[day])))
    if not rows:
        raise ValueError("no usable rate days")
    out = pd.DataFrame(rows, columns=["timestamp", "close"])
    out["open"] = out["high"] = out["low"] = out["close"]
    out["volume"] = 0.0
    out["source"] = SOURCE
    return out[cache.OHLCV_COLUMNS]
