"""L2BEAT activity adapter: cross-check only, never the primary series.

Chain growth RFC-2. Keyless. GET https://l2beat.com/api/scaling/activity/{project}?range={range}
(confirmed on the user's PC 2026-09-25) -> {"data": {"chart": {"types":
["timestamp", "count", "uopsCount"], "data": [[ts, count, uops], ...]}}}.
Columns are read by name, not position. Optimism's project slug is
`op-mainnet`; `optimism` answers 200 with zero rows, which this adapter
reports as `unavailable` ("empty-chart"), never as zero activity.

Public Contract: never raises; failure is `status="unavailable"` + `reason`.
L2BEAT terms do not allow redistribution: `REDISTRIBUTABLE = False`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import httpx

from api.data.growthepie_adapter import unix_to_utc_date

BASE_URL = "https://l2beat.com/api/scaling/activity"
REDISTRIBUTABLE = False
TIMEOUT_S = 60.0
RANGES = frozenset({"7d", "30d", "90d", "180d", "1y", "max"})

ActivityStatus = Literal["ok", "unavailable", "stale"]


@dataclass(frozen=True)
class ActivityPoint:
    date: str  # YYYY-MM-DD UTC
    count: float
    uops_count: float | None


@dataclass
class L2beatActivity:
    project: str
    status: ActivityStatus
    range: str
    points: list[ActivityPoint] = field(default_factory=list)
    reason: str | None = None
    redistributable: bool = REDISTRIBUTABLE


def _num(raw: object) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v) or v < 0:
        return None
    return v


def parse_activity(payload: object, project: str, range_: str) -> L2beatActivity:
    def bad(reason: str) -> L2beatActivity:
        return L2beatActivity(project=project, status="unavailable", range=range_, reason=reason)

    if not isinstance(payload, dict):
        return bad("unexpected-shape")
    body = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    chart = body.get("chart")
    if not isinstance(chart, dict):
        return bad("unexpected-shape")
    types, rows = chart.get("types"), chart.get("data")
    if not isinstance(types, list) or not isinstance(rows, list) or "timestamp" not in types or "count" not in types:
        return bad("unexpected-shape")
    i_ts, i_c = types.index("timestamp"), types.index("count")
    i_u = types.index("uopsCount") if "uopsCount" in types else None
    by_date: dict[str, ActivityPoint] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) <= max(i_ts, i_c):
            continue
        d, c = unix_to_utc_date(row[i_ts]), _num(row[i_c])
        if d is None or c is None:
            continue
        u = _num(row[i_u]) if i_u is not None and len(row) > i_u else None
        by_date[d] = ActivityPoint(date=d, count=c, uops_count=u)
    if not by_date:
        return bad("empty-chart")
    return L2beatActivity(project=project, status="ok", range=range_, points=[by_date[d] for d in sorted(by_date)])


def fetch_activity(project: str, range_: str = "max", client: httpx.Client | None = None) -> L2beatActivity:
    """Daily transaction counts for an L2BEAT project. `range_="max"` for
    backfill, `"30d"` for nightly updates."""
    if range_ not in RANGES:
        return L2beatActivity(project=project, status="unavailable", range=range_, reason="invalid-range")
    url = f"{BASE_URL}/{project}"
    try:
        if client is None:
            with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True) as c:
                resp = c.get(url, params={"range": range_})
        else:
            resp = client.get(url, params={"range": range_})
    except Exception as exc:
        return L2beatActivity(project=project, status="unavailable", range=range_, reason=f"fetch-failed: {type(exc).__name__}")
    if resp.status_code != 200:
        return L2beatActivity(project=project, status="unavailable", range=range_, reason=f"http-{resp.status_code}")
    try:
        payload = resp.json()
    except Exception:
        return L2beatActivity(project=project, status="unavailable", range=range_, reason="invalid-json")
    try:
        return parse_activity(payload, project, range_)
    except Exception as exc:
        return L2beatActivity(project=project, status="unavailable", range=range_, reason=f"parse-failed: {type(exc).__name__}")
