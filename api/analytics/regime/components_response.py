"""RegimeComponentsResult -> GET /api/regime/components response (RFC-004, plan §11).

Serialization only: every number is already computed by
`api/analytics/regime/components.py`; this module filters by date range,
drops non-finite rows (never a null/NaN/0 stand-in), and attaches the
per-component `last_fetched_utc`, which is read from cache file times here
rather than inside the pure builders (RFC-004 decision 2).
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

import pandas as pd

from api.analytics.regime.components import (
    PUBLISHED_MAX_GAP_DAYS,
    REPRODUCED_MAX_GAP_DAYS,
    ComponentSeries,
    RegimeComponentsResult,
    status_for_range,
    with_gap_flags,
)
from api.data import cache, defillama_adapter, fred_adapter
from api.models.regime import (
    CompositeAgreement,
    ComponentPoint,
    PublishedComposite,
    PublishedPoint,
    RegimeComponent,
    RegimeComponentsResponse,
    RegimeComposite,
    ReproducedComposite,
    ReproducedPoint,
)

REPRODUCED_LABEL = "Reproduced tide index (this app)"
REPRODUCED_NORMALISATION = "sign·tanh(impulse/scale); 50 + 50·Σw·x / Σw_present"
PUBLISHED_LABEL = "LiqTide tide index (published)"
PUBLISHED_ATTRIBUTION = "Data: LiqTide (liqtide.com)"

# Cached FRED/DefiLlama inputs per component (decision 2). Components not
# listed here are LiqTide-archive-derived and use the latest raw archive file.
LIQUIDITY_INPUTS: dict[str, tuple[str, ...]] = {
    "net_liquidity": (fred_adapter.WALCL, fred_adapter.TGA_WEDNESDAY, fred_adapter.RRP),
    "stablecoin_supply": (defillama_adapter.SERIES_ID,),
    "broad_dollar": (fred_adapter.BROAD_DOLLAR,),
    "rrp_release": (fred_adapter.RRP,),
}


def _iso_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def last_fetched_utc(component_id: str) -> str | None:
    """Most recent write time among the component's cached inputs, or None
    when none is cached."""
    if component_id in LIQUIDITY_INPUTS:
        paths = [cache.liquidity_series_path(sid) for sid in LIQUIDITY_INPUTS[component_id]]
    else:
        raw_dates = cache.list_liqtide_raw_dates()
        paths = [cache.liqtide_raw_path(raw_dates[-1])] if raw_dates else []
    mtimes = [p.stat().st_mtime for p in paths if p.exists()]
    return _iso_utc(max(mtimes)) if mtimes else None


def _in_range(df: pd.DataFrame, start: pd.Timestamp | None, end: pd.Timestamp | None) -> pd.DataFrame:
    if df.empty:
        return df
    dates = pd.to_datetime(df["date"]).dt.normalize()
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= dates >= start
    if end is not None:
        mask &= dates <= end
    return df[mask]


def _finite(*values) -> bool:
    return all(v is not None and isinstance(v, (int, float)) and math.isfinite(v) for v in values)


def _iso(d) -> str:
    return pd.Timestamp(d).strftime("%Y-%m-%d")


def _flagged(df: pd.DataFrame, cols: tuple[str, ...], max_gap_days: int, start, end) -> pd.DataFrame:
    """Drop non-finite rows, flag gaps on the WHOLE remaining series, then
    filter to the window (RFC-005 decision 9): the flags describe the series,
    not the viewing window."""
    if df.empty:
        return df.assign(gap_before=pd.Series(dtype=bool))
    keep = df[[_finite(*vals) for vals in df[list(cols)].itertuples(index=False, name=None)]]
    return _in_range(with_gap_flags(keep, max_gap_days), start, end)


def _component(c: ComponentSeries, start, end) -> RegimeComponent:
    rows = _flagged(c.points, ("value", "raw", "contribution"), c.spec.max_gap_days, start, end)
    points = [
        ComponentPoint(date=_iso(r.date), value=float(r.value), raw=float(r.raw), contribution=float(r.contribution),
                       gap_before=bool(r.gap_before))
        for r in rows.itertuples(index=False)
    ]
    status, reason = status_for_range(c, end)
    if status == "ok" and not points and not c.points.empty:
        # Data exists, just not in the requested window.
        status, reason = "no_data", "no points in the requested date range"
    spec = c.spec
    return RegimeComponent(
        id=spec.id, label=spec.label, weight=spec.weight, source=spec.source,
        transform=spec.transform, frequency=spec.frequency, unit=spec.unit,
        status=status, reason=reason, notes=list(c.notes),
        first_date=points[0].date if points else None,
        last_date=points[-1].date if points else None,
        last_fetched_utc=last_fetched_utc(spec.id),
        max_gap_days=spec.max_gap_days,
        points=points,
    )


def _optional_float(v) -> float | None:
    return float(v) if _finite(v) else None


def serialize_components(
    result: RegimeComponentsResult,
    start: date | None = None,
    end: date | None = None,
    now: datetime | None = None,
) -> RegimeComponentsResponse:
    """Build the §11 response. `start`/`end` are inclusive and filter every
    point list plus `grid_dates`; `agreement` stays whole-history (it is a
    property of the model, not of the viewing window). Caller guarantees
    start <= end."""
    s = pd.Timestamp(start) if start is not None else None
    e = pd.Timestamp(end) if end is not None else None

    reproduced = [
        ReproducedPoint(date=_iso(r.date), value=float(r.value), coverage=float(r.coverage),
                        gap_before=bool(r.gap_before))
        for r in _flagged(result.reproduced, ("value", "coverage"), REPRODUCED_MAX_GAP_DAYS, s, e)
        .itertuples(index=False)
    ]
    published = [
        PublishedPoint(date=_iso(r.date), value=float(r.value),
                       regime_label=r.label if isinstance(r.label, str) and r.label else None,
                       gap_before=bool(r.gap_before))
        for r in _flagged(result.published, ("value",), PUBLISHED_MAX_GAP_DAYS, s, e).itertuples(index=False)
    ]
    grid = [d for d in result.grid_dates if (s is None or d >= _iso(s)) and (e is None or d <= _iso(e))]
    a = result.agreement
    agreement = CompositeAgreement(
        overlap_days=int(a.get("overlap_days", 0)),
        pearson_r=_optional_float(a.get("pearson_r")),
        mean_abs_diff=_optional_float(a.get("mean_abs_diff")),
        full_coverage_days=int(a.get("full_coverage_days", 0)),
        full_coverage_mean_abs_diff=_optional_float(a.get("full_coverage_mean_abs_diff")),
    )
    generated = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return RegimeComponentsResponse(
        generated_utc=generated,
        grid_dates=grid,
        components=[_component(c, s, e) for c in result.components],
        composite=RegimeComposite(
            reproduced=ReproducedComposite(label=REPRODUCED_LABEL, normalisation=REPRODUCED_NORMALISATION,
                                           max_gap_days=REPRODUCED_MAX_GAP_DAYS, points=reproduced),
            published=PublishedComposite(label=PUBLISHED_LABEL, attribution=PUBLISHED_ATTRIBUTION,
                                         status="ok" if published else "unavailable",
                                         max_gap_days=PUBLISHED_MAX_GAP_DAYS, points=published),
            agreement=agreement,
        ),
    )
