"""Google Trends source.

`fetch_alone` (T100b, used by the daily runner): one request per coin with only its keyword over an explicit
100-day daily range; the runner replaces the stored series with each pull. `fetch_series` (superseded ticker
path, kept for the registry and its tests) wraps pytrends_adapter: one latest value per refresh, kept only if
its date is a completed UTC day. Without a probe record the reader reports not-probed. Never raises; reasons
carry the exception class and HTTP status only. pytrends is never imported here: the client is injected.
"""
from __future__ import annotations

import math
import statistics
from datetime import date, datetime, timedelta, timezone
from itertools import pairwise

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


# --- T100b: one coin per request (design 1 of the T144 PLAN) ---
# A coin requested alone peaks at 100 (best resolution). Consumers only use per-coin ratios
# (recent mean / longer mean), so no anchor term and no cross-coin scale is needed.
TRENDS_RANGE_DAYS = 100  # explicit daily range: covers the widest compared span (7 + 90 days)
MIN_COMPLETE_DAYS = 90
# "Too little interest" on the coin's own complete days. PLACEHOLDERS: the owner sets both after probe P-RES.
TRENDS_MIN_MEDIAN = 3
TRENDS_MAX_ZERO_DAY_PCT = 40
TOO_LITTLE_INTEREST = "too-little-interest"
# Quiet baseline (median of the days before the last week < TRENDS_MIN_MEDIAN) but a live last week (every day > 0,
# median >= TRENDS_MIN_MEDIAN): still missing, never 0, but
# reported apart so the owner sees it. Whether "rising from nothing" counts as rising is an open SPEC question.
QUIET_THEN_SURGE = "quiet-then-surge"
SURGE_DAYS = 7
# Fail-closed pull checks: a row outside [requested start, yesterday], or a last row that is not yesterday.
OUT_OF_RANGE = "out-of-range"
NOT_CURRENT = "not-current"
NAME_AMBIGUOUS = "name-ambiguous: needs topic"
# Bare names that collect unrelated searches (T125 review list): fetched by topic id only, never by term.
NAME_RISK_SYMBOLS = frozenset(
    {"TRX", "ONDO", "MORPHO", "ICP", "SHIB", "PEPE", "BNB", "CRO", "HBAR", "LINK", "APT", "SOL"})


def explicit_timeframe(today: date) -> str:
    """'<start> <end>' over the TRENDS_RANGE_DAYS complete UTC days ending yesterday."""
    end = today - timedelta(days=1)
    return f"{(end - timedelta(days=TRENDS_RANGE_DAYS - 1)).isoformat()} {end.isoformat()}"


def requested_range(timeframe: str) -> tuple[date, date] | None:
    """(start, end) of an explicit 'YYYY-MM-DD YYYY-MM-DD' timeframe; None for a relative one ('today 3-m')."""
    parts = timeframe.split(" ")
    try:
        return (date.fromisoformat(parts[0]), date.fromisoformat(parts[1])) if len(parts) == 2 else None
    except ValueError:
        return None


def http_status(exc: BaseException) -> int | None:
    code = getattr(getattr(exc, "response", None), "status_code", None)
    return code if isinstance(code, int) and not isinstance(code, bool) else None


def error_class(exc: BaseException) -> str:
    """Class name plus HTTP status; never the message (pytrends puts the whole response on it)."""
    status = http_status(exc)
    return f"{type(exc).__name__}(HTTP {status})" if status is not None else type(exc).__name__


def is_rate_limited(exc: BaseException) -> bool:
    return type(exc).__name__ == "TooManyRequestsError" or http_status(exc) == 429


def interest_verdict(values: list[float]) -> str:
    """'ok', TOO_LITTLE_INTEREST (all zero, median under TRENDS_MIN_MEDIAN, or zero days at least
    TRENDS_MAX_ZERO_DAY_PCT percent of the days) or QUIET_THEN_SURGE (too little, but a live last week)."""
    if values and any(values):
        zero_pct = 100.0 * sum(1 for v in values if v == 0) / len(values)
        if statistics.median(values) >= TRENDS_MIN_MEDIAN and zero_pct < TRENDS_MAX_ZERO_DAY_PCT:
            return "ok"
    base, last = values[:-SURGE_DAYS], values[-SURGE_DAYS:]
    if (base and len(last) == SURGE_DAYS and statistics.median(base) < TRENDS_MIN_MEDIAN
            and all(v > 0 for v in last) and statistics.median(last) >= TRENDS_MIN_MEDIAN):
        return QUIET_THEN_SURGE
    return TOO_LITTLE_INTEREST


def _partial(value) -> bool:
    return value.strip().lower() == "true" if isinstance(value, str) else bool(value)


def complete_days(frame, term: str) -> tuple[list[tuple[date, float]] | None, str]:
    """(points, "") on a daily frame without its isPartial rows, else (None, reason). A missing value is a gap
    (never 0). Dates are not filtered here: fetch_alone rejects rows outside the requested range."""
    if frame is None or len(frame) == 0:
        return None, "empty response"
    if term not in frame.columns:
        return None, "missing-column"
    idx = list(frame.index)
    if any((b - a).total_seconds() != 86400 for a, b in pairwise(idx)):
        return None, "non-daily"
    flags = frame["isPartial"].tolist() if "isPartial" in frame.columns else [False] * len(idx)
    points = []
    for ts, v, partial in zip(idx, frame[term].tolist(), flags):
        if _partial(partial):
            continue
        if v is None or math.isnan(v):
            return None, "gap"
        points.append((ts.date() if hasattr(ts, "date") else ts, float(v)))
    return points, ""


def fetch_alone(symbol: str, term: str, client, *, today: date, timeframe: str | None = None) -> SourceSeries:
    """One request with only `term`. Never raises; a reason carries the exception class and HTTP status only."""
    sym = symbol.upper()
    try:
        client.build_payload([term], timeframe=timeframe or explicit_timeframe(today), geo="")
        frame = client.interest_over_time()
    except Exception as exc:  # noqa: BLE001 - the class is reported, never the message
        if is_rate_limited(exc):
            return SourceSeries(SOURCE, sym, [], "capped", f"rate-limited: {error_class(exc)}")
        return SourceSeries(SOURCE, sym, [], "unavailable", f"fetch-failed: {error_class(exc)}")
    points, reason = complete_days(frame, term)
    if points is None:
        return SourceSeries(SOURCE, sym, [], "unavailable", reason)
    # Fail closed: every row inside [requested start, yesterday] and the last row is yesterday, or nothing is
    # stored (a stale or oversized pull would otherwise replace the whole stored series).
    yesterday = today - timedelta(days=1)
    rng = requested_range(timeframe or explicit_timeframe(today))
    if any(d > yesterday for d, _ in points):
        return SourceSeries(SOURCE, sym, [], "unavailable", OUT_OF_RANGE)
    if points and points[-1][0] != yesterday:
        return SourceSeries(SOURCE, sym, [], "unavailable", NOT_CURRENT)
    if rng is not None and points and points[0][0] < rng[0]:
        return SourceSeries(SOURCE, sym, [], "unavailable", OUT_OF_RANGE)
    if len(points) < MIN_COMPLETE_DAYS:
        return SourceSeries(SOURCE, sym, [], "insufficient-history", f"{len(points)} days")
    verdict = interest_verdict([v for _, v in points])
    if verdict != "ok":
        return SourceSeries(SOURCE, sym, [], "unavailable", verdict)  # missing, never 0
    return SourceSeries(SOURCE, sym, points, "ok", "")
