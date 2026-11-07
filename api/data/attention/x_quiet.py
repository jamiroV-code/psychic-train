"""X quiet hours (B3, `x_quiet_hours_enabled`, default off): pure zone-aware window math.

Each configured account label may carry `{"timezone": IANA, "start": "HH:MM", "end": "HH:MM"}` in
`x_account_quiet_hours`; the window may cross local midnight. `next_outside` returns the first UTC instant at or after
`now` whose local wall time is outside the window, honouring DST gaps (resume at the transition) and folds (the first
occurrence of the end time). Evidence status: quiet hours have NO primary evidence of benefit (REF-X section 4.3); the
measure exists to be measured and removed if it shows none. This is the only X module allowed to read a local hour
(Table H); scheduling, caps, canary and the global ceiling are unaffected here. Pure: no clock, no network, no state.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

HHMM_RE = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")
_SEARCH_DAYS = (-1, 0, 1, 2)


@dataclass(frozen=True)
class Window:
    zone: ZoneInfo
    start: int  # minutes after local midnight
    end: int


def parse_window(spec: Mapping) -> Window:
    """Validate one owner window; raises ValueError on anything malformed (the config validator does the same)."""
    if not isinstance(spec, Mapping) or set(spec) != {"timezone", "start", "end"}:
        raise ValueError("quiet window needs exactly timezone, start and end")
    minutes = []
    for key in ("start", "end"):
        m = HHMM_RE.fullmatch(spec[key]) if isinstance(spec[key], str) else None
        if m is None:
            raise ValueError(f"quiet window {key} must be HH:MM")
        minutes.append(int(m.group(1)) * 60 + int(m.group(2)))
    if minutes[0] == minutes[1]:
        raise ValueError("quiet window start and end must differ")
    try:
        zone = ZoneInfo(spec["timezone"]) if isinstance(spec["timezone"], str) else None
    except (ZoneInfoNotFoundError, ValueError):
        zone = None
    if zone is None:
        raise ValueError("quiet window timezone is not a known IANA zone")
    return Window(zone, minutes[0], minutes[1])


def _utc(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("quiet hours need an aware datetime")
    return now.astimezone(timezone.utc)


def _inside(w: Window, now: datetime) -> bool:
    local = now.astimezone(w.zone)
    m = local.hour * 60 + local.minute
    return w.start <= m < w.end if w.start < w.end else (m >= w.start or m < w.end)


def in_quiet(now: datetime, spec: Mapping) -> bool:
    return _inside(parse_window(spec), _utc(now))


def next_outside(now: datetime, spec: Mapping) -> datetime:
    """First UTC instant >= now outside the window (now itself when already outside)."""
    w, now = parse_window(spec), _utc(now)
    if not _inside(w, now):
        return now
    local_day = now.astimezone(w.zone).date()
    candidates = []
    for offset in _SEARCH_DAYS:
        d: date = local_day + timedelta(days=offset)
        # fold=0: the first occurrence in a fold; inside a gap it lands just past the transition.
        wall = datetime(d.year, d.month, d.day, w.end // 60, w.end % 60, tzinfo=w.zone, fold=0)
        at = wall.astimezone(timezone.utc)
        if at > now and not _inside(w, at):
            candidates.append(at)
    hi = min(candidates)
    lo = now  # invariant: lo inside, hi outside; narrow to the exact first outside second (DST gap transition)
    while hi - lo > timedelta(seconds=1):
        mid = lo + (hi - lo) / 2
        mid = mid.replace(microsecond=0)
        if mid <= lo:
            break
        if _inside(w, mid):
            lo = mid
        else:
            hi = mid
    return hi


def quiet_until(now: datetime, label: str, windows: Mapping[str, Mapping], *, enabled: bool) -> datetime | None:
    """The instant this label leaves its quiet window, or None when off, unconfigured or not currently quiet."""
    if not enabled or label not in windows:
        return None
    nxt = next_outside(now, windows[label])
    return None if nxt == _utc(now) else nxt
