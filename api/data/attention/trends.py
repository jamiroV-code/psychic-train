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
SURGE_RATIO = 3  # the last-week median must also be at least this many times the baseline median
# Fail-closed pull checks: a row outside [requested start, yesterday], or a last row that is not yesterday.
OUT_OF_RANGE = "out-of-range"
NOT_CURRENT = "not-current"
NAME_AMBIGUOUS = "name-ambiguous: needs topic or qualified term"
# Stage 2 (D-30): which coins are ambiguous lives in the keyword file (`_ambiguous`), with per-coin approvals.
# A qualifier word beside the name ("tron crypto") marks a qualified term (candidate generation, file checks).
QUALIFIER_WORDS = frozenset({"crypto", "coin", "token", "network", "protocol", "finance", "swap", "chain"})


def is_qualified_term(term: str) -> bool:
    words = term.casefold().split()
    return any(w in QUALIFIER_WORDS for w in words) and any(w not in QUALIFIER_WORDS for w in words)


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
            and all(v > 0 for v in last)
            and statistics.median(last) >= max(TRENDS_MIN_MEDIAN, SURGE_RATIO * statistics.median(base))):
        return QUIET_THEN_SURGE
    return TOO_LITTLE_INTEREST


def series_stats(values: list[float]) -> dict:
    """median, zero_share_pct and last7_vs_prior28_ratio (mean of the last 7 days over the mean of the 28 days
    before them; None when that mean is 0 or there are fewer than 35 days). Read-only evidence for the run file."""
    n = len(values)
    out = {"median": round(statistics.median(values), 2) if n else None,
           "zero_share_pct": round(100.0 * sum(1 for v in values if v == 0) / n, 1) if n else None,
           "last7_vs_prior28_ratio": None}
    if n >= SURGE_DAYS + 28:
        prior = statistics.fmean(values[-SURGE_DAYS - 28:-SURGE_DAYS])
        if prior > 0:
            out["last7_vs_prior28_ratio"] = round(statistics.fmean(values[-SURGE_DAYS:]) / prior, 2)
    return out


def _partial(value) -> bool:
    return value.strip().lower() == "true" if isinstance(value, str) else bool(value)


def complete_days(frame, term: str) -> tuple[list[tuple[date, float]] | None, str]:
    """(points, "") on a daily frame without its isPartial rows, else (None, reason). A missing value, or a
    partial row inside the series, is a gap (never 0); a value outside 0..100 is a bad value. Dates are not
    filtered here: fetch_alone rejects rows outside the requested range."""
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
        if isinstance(v, bool) or not 0 <= v <= 100:  # NaN is handled above; inf fails the range
            return None, "bad-value"
        points.append((ts.date() if hasattr(ts, "date") else ts, float(v)))
    if any((b[0] - a[0]).days != 1 for a, b in pairwise(points)):
        return None, "gap"
    return points, ""


def fetch_alone(symbol: str, term: str, client, *, today: date, timeframe: str | None = None,
                stats: dict | None = None) -> SourceSeries:
    """One request with only `term`. Never raises; a reason carries the exception class and HTTP status only.
    `stats`, when given, is cleared and filled with series_stats of a pull that passed the checks and has at
    least MIN_COMPLETE_DAYS days (ok, too-little-interest or quiet-then-surge); otherwise it stays empty."""
    sym = symbol.upper()
    if stats is not None:
        stats.clear()
    try:
        client.build_payload([term], timeframe=timeframe or explicit_timeframe(today), geo="")
        frame = client.interest_over_time()
    except Exception as exc:  # noqa: BLE001 - the class is reported, never the message
        if is_rate_limited(exc):
            return SourceSeries(SOURCE, sym, [], "capped", f"rate-limited: {error_class(exc)}")
        return SourceSeries(SOURCE, sym, [], "unavailable", f"fetch-failed: {error_class(exc)}")
    try:
        points, reason = complete_days(frame, term)
    except Exception as exc:  # noqa: BLE001 - a malformed frame must not cost the other coins' pulls
        return SourceSeries(SOURCE, sym, [], "unavailable", f"parse-failed: {error_class(exc)}")
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
    if stats is not None:
        stats.update(series_stats([v for _, v in points]))
    verdict = interest_verdict([v for _, v in points])
    if verdict != "ok":
        return SourceSeries(SOURCE, sym, [], "unavailable", verdict)  # missing, never 0
    return SourceSeries(SOURCE, sym, points, "ok", "")
