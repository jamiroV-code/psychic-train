"""Google Trends source: wraps pytrends_adapter (partial rows already dropped there).

One latest value per refresh, kept only if its date is a completed UTC day. Cross-coin
comparability is decided in slice G; without a probe record the reader reports it
not-probed. Never raises; reasons carry the exception type only.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from api.data import pytrends_adapter
from api.data.attention.types import SourceSeries

SOURCE = "trends"


def fetch_series(symbol: str, keyword: str | None, *, fetch=pytrends_adapter.fetch_trend,
                 today: date | None = None) -> SourceSeries:
    sym = symbol.upper()
    today = today or datetime.now(timezone.utc).date()
    if not keyword:
        return SourceSeries(SOURCE, sym, [], "unavailable", "no keyword mapped")
    try:
        res = fetch(keyword)
    except Exception as exc:
        return SourceSeries(SOURCE, sym, [], "unavailable", f"fetch-failed: {type(exc).__name__}")
    if res.status != "ok" or res.value is None or not res.as_of:
        return SourceSeries(SOURCE, sym, [], "unavailable", res.status)
    try:
        day = date.fromisoformat(res.as_of[:10])
    except ValueError:
        return SourceSeries(SOURCE, sym, [], "unavailable", "bad date")
    if day >= today:  # current-day row is partial
        return SourceSeries(SOURCE, sym, [], "unavailable", "partial row dropped")
    return SourceSeries(SOURCE, sym, [(day, float(res.value))], "insufficient-history", "1 days")
