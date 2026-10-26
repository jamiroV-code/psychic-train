"""Google Trends term groups (T196): pure metrics for the owner's `probe_trends --try` tester.

A group is 1 to MAX_TERMS search terms for one coin, fetched in ONE request so every term shares one 0-100 scale.
The group series is the sum of the term series. The usable verdict is the daily run's own rule
(trends.interest_verdict); the rest says whether attention is rising without one-term or off-topic noise.
No network, no store, no pandas: the caller passes the frame and the stored volume points. A failure or too few
days is a reason string or None, never 0.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta

from api.data.attention import trends

# Every threshold below is a PLACEHOLDER the owner tunes after real runs.
MAX_TERMS = 5  # pytrends compares at most 5 terms in one request
SMOOTH_DAYS = 7  # trailing mean used before any correlation (weekday swings would dominate raw days)
RECENT_DAYS = 7  # "last week" of the rising measure
BASELINE_DAYS = 28  # the 4 weeks before it: the baseline
MIN_RISE_RATIO = 1.10  # median of the last 7 days over the prior-28-day median
MIN_DAYS_ABOVE = 4  # of the last 7 days, at least this many above the prior-28-day median (not a one-day spike)
SPIKE_SHARE = 0.80  # one term carrying more than this share of the group's last-7-day increase: a one-term spike
MOVES_ALONE_CORR = 0.2  # a term whose smoothed series correlates below this with the best term "moves alone"
IDENTITY_MIN_DAYS = 60  # overlapping days needed before the volume correlation is computed
IDENTITY_MIN_CORR = 0.2  # below this the group "does not track this coin's volume" (a hint, not proof)


@dataclass
class Group:
    terms: dict[str, list[float]]
    total: list[float]


@dataclass
class TermStats:
    median: float
    zero_pct: float


@dataclass
class Rising:
    ratio: float | None
    days_above: int | None
    reason: str = ""


@dataclass
class Identity:
    corr: float | None
    days: int
    reason: str = ""


@dataclass
class GroupStats:
    days: int
    min: float
    median: float
    max: float
    zero_pct: float


@dataclass
class GroupMetrics:
    terms: dict[str, TermStats]
    shares: dict[str, float | None]
    group: GroupStats
    verdict: str
    rising: Rising
    spike_share: float | None
    spike: bool
    spike_reason: str
    best_term: str
    correlations: dict[str, float | None]
    moves_alone: list[str]
    identity: Identity
    clean: bool
    reasons: list[str] = field(default_factory=list)


def group_series(series: dict[str, list[float]]) -> Group:
    if not series or len({len(v) for v in series.values()}) != 1:
        raise ValueError("a group needs at least one term and equal-length series")
    terms = {t: [float(v) for v in vals] for t, vals in series.items()}
    return Group(terms, [sum(day) for day in zip(*terms.values())])


def term_stats(values: list[float]) -> TermStats:
    return TermStats(statistics.median(values), 100.0 * sum(1 for v in values if v == 0) / len(values))


def shares(grp: Group) -> dict[str, float | None]:
    whole = sum(grp.total)
    return {t: (sum(v) / whole if whole else None) for t, v in grp.terms.items()}


def rising(values: list[float]) -> Rising:
    need = RECENT_DAYS + BASELINE_DAYS
    if len(values) < need:
        return Rising(None, None, f"missing: {len(values)} days, need {need}")
    base = statistics.median(values[-need:-RECENT_DAYS])
    recent = values[-RECENT_DAYS:]
    if base == 0:
        return Rising(None, None, "missing: baseline median 0")
    return Rising(statistics.median(recent) / base, sum(1 for v in recent if v > base))


def _increase(values: list[float]) -> float:
    """The term's last-7-day sum above its own prior-28-day median, floored at 0."""
    base = statistics.median(values[-RECENT_DAYS - BASELINE_DAYS:-RECENT_DAYS])
    return max(0.0, sum(v - base for v in values[-RECENT_DAYS:]))


def one_term_spike(grp: Group) -> tuple[float | None, bool, str]:
    """(largest term's share of the group's last-7-day increase, flagged, reason when the share is missing)."""
    if len(grp.terms) < 2:
        return None, False, "n/a: one term"
    if len(grp.total) < RECENT_DAYS + BASELINE_DAYS:
        return None, False, "missing: too few days"
    inc = [_increase(v) for v in grp.terms.values()]
    if not sum(inc):
        return None, False, "missing: no increase over baseline"
    share = max(inc) / sum(inc)
    return share, share > SPIKE_SHARE, ""


def smooth(values: list[float], n: int = SMOOTH_DAYS) -> list[float]:
    """Trailing n-day mean; point i covers days i .. i+n-1 (dated at its last day)."""
    return [sum(values[i:i + n]) / n for i in range(len(values) - n + 1)]


def pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) != len(b) or len(a) < 2:
        return None
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if sa == 0 or sb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def term_correlations(grp: Group, share: dict[str, float | None]) -> tuple[str, dict[str, float | None], list[str]]:
    """Best term = largest share of the group total (first term on ties); every other term's smoothed correlation
    with it, and the terms below MOVES_ALONE_CORR. A flat series has no correlation (None), never 0."""
    best = max(grp.terms, key=lambda t: share[t] or 0.0)
    ref = smooth(grp.terms[best])
    corr = {t: pearson(smooth(v), ref) for t, v in grp.terms.items() if t != best}
    return best, corr, [t for t, c in corr.items() if c is not None and c < MOVES_ALONE_CORR]


def identity(total: list[float], dates: list[date], volume) -> Identity:
    """Pearson of the smoothed group series vs log(1 + stored daily volume) on the days both exist."""
    if not volume:
        return Identity(None, 0, "n/a: no stored volume")
    vol = {d: math.log1p(v) for d, v in volume
           if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0}
    sm = smooth(total)
    pairs = [(s, vol[d]) for s, d in zip(sm, dates[SMOOTH_DAYS - 1:]) if d in vol]
    if len(pairs) < IDENTITY_MIN_DAYS:
        return Identity(None, len(pairs), f"n/a: no stored volume ({len(pairs)} overlapping days, "
                                          f"need {IDENTITY_MIN_DAYS})")
    c = pearson([a for a, _ in pairs], [b for _, b in pairs])
    return Identity(c, len(pairs), "" if c is not None else "n/a: a flat series")


def analyze(series: dict[str, list[float]], dates: list[date], volume=None) -> GroupMetrics:
    grp = group_series(series)
    share = shares(grp)
    total = grp.total
    zero_pct = term_stats(total).zero_pct
    verdict = trends.interest_verdict(total)
    rise = rising(total)
    spike_share, spike, spike_reason = one_term_spike(grp)
    best, corr, alone = term_correlations(grp, share)
    ident = identity(total, dates, volume)
    reasons = []
    if verdict != "ok":
        reasons.append(f"not usable: {verdict}")
    if rise.ratio is None:
        reasons.append(f"rising {rise.reason}")
    else:
        if rise.ratio < MIN_RISE_RATIO:
            reasons.append(f"last7/prior28 {rise.ratio:.3g} < {MIN_RISE_RATIO:g}")
        if rise.days_above < MIN_DAYS_ABOVE:
            reasons.append(f"{rise.days_above}/{RECENT_DAYS} days above baseline < {MIN_DAYS_ABOVE}")
    if spike:
        reasons.append(f"one-term spike ({100 * spike_share:.0f}% of the increase from one term)")
    if ident.corr is not None and ident.corr < IDENTITY_MIN_CORR:
        reasons.append(f"does not track this coin's volume ({ident.corr:.2f} < {IDENTITY_MIN_CORR:g})")
    return GroupMetrics(
        terms={t: term_stats(v) for t, v in grp.terms.items()}, shares=share,
        group=GroupStats(len(total), min(total), statistics.median(total), max(total), zero_pct),
        verdict=verdict, rising=rise, spike_share=spike_share, spike=spike, spike_reason=spike_reason,
        best_term=best, correlations=corr, moves_alone=alone, identity=ident, clean=not reasons, reasons=reasons)


def rank_key(m: GroupMetrics) -> tuple:
    """Best first: usable, then clean rising, then the highest group median (each request has its own scale)."""
    return (m.verdict != "ok", not m.clean, -m.group.median)


def check_group_frame(frame, terms: list[str], today: date) -> tuple[dict[str, list[float]] | None, list[date], str]:
    """Fail closed exactly like fetch_alone, for every term of one shared frame: daily, no gap, values 0..100, rows
    inside [range start, yesterday], last row yesterday, and TRENDS_RANGE_DAYS complete rows. Never raises; the
    reason is a class, never response content."""
    yesterday = today - timedelta(days=1)
    start = yesterday - timedelta(days=trends.TRENDS_RANGE_DAYS - 1)
    out: dict[str, list[float]] = {}
    dates: list[date] | None = None
    for term in terms:
        try:
            points, reason = trends.complete_days(frame, term)
        except Exception as exc:  # noqa: BLE001 - a malformed frame is a reason, never a crash
            return None, [], f"parse-failed: {type(exc).__name__}"
        if points is None:
            return None, [], reason
        if any(d > yesterday for d, _ in points):
            return None, [], trends.OUT_OF_RANGE
        if points and points[-1][0] != yesterday:
            return None, [], trends.NOT_CURRENT
        if points and points[0][0] < start:
            return None, [], trends.OUT_OF_RANGE
        if len(points) != trends.TRENDS_RANGE_DAYS:
            return None, [], f"rows: {len(points)}, need {trends.TRENDS_RANGE_DAYS}"
        days = [d for d, _ in points]
        if dates is not None and days != dates:
            return None, [], "gap"
        dates = days
        out[term] = [v for _, v in points]
    return out, dates or [], ""
