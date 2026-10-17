"""GET /api/narrative/history and /api/narrative/mindshare.

Thin FastAPI wrappers over `api/analytics/narrative/{history,mindshare}.py`;
routers/ exposes HTTP only and never calls a provider directly.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from api.analytics.narrative import history
from api.models.narrative import (
    NarrativeChange,
    NarrativeChangeEntry,
    NarrativeCoin,
    NarrativeComparison,
    NarrativeComparisonEntry,
    NarrativeComposite,
    NarrativeCompositePoint,
    NarrativeHistoryCategory,
    NarrativeHistoryPoint,
    NarrativeHistoryResponse,
    NarrativeHistorySeries,
)

router = APIRouter(prefix="/api/narrative", tags=["narrative"])


@router.get("/history", response_model=NarrativeHistoryResponse)
def get_history(
    categories: str | None = Query(None, description="Comma-separated seed category ids; default all"),
    start: date | None = Query(None, description="ISO date, inclusive"),
    end: date | None = Query(None, description="ISO date, inclusive"),
) -> NarrativeHistoryResponse:
    """Read-only history of every narrative source per category, plus the
    composite, comparison rank and 7-day change. Never fetches a provider."""
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    ids: list[str] | None = None
    if categories is not None:
        ids = [c.strip() for c in categories.split(",") if c.strip()]
        if not ids:
            raise HTTPException(status_code=422, detail="categories must name at least one category id")
    try:
        result = history.build_narrative_history(ids, start, end)
    except history.UnknownCategoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _history_response(result)


def _history_response(result: history.NarrativeHistoryResult) -> NarrativeHistoryResponse:
    cats = []
    for c in result.categories:
        series = [
            NarrativeHistorySeries(
                source=s.source, label=s.label, variant=s.variant, cache_key=s.cache_key,
                redistributable=s.redistributable, status=s.status, reason=s.reason,
                first_date=None if s.frame.empty else str(s.frame["date"].iloc[0]),
                last_date=None if s.frame.empty else str(s.frame["date"].iloc[-1]),
                max_gap_days=history.NARRATIVE_MAX_GAP_DAYS, in_composite=s.in_composite,
                points=[
                    NarrativeHistoryPoint(
                        date=r.date, raw_value=None if pd_isna(r.raw) else float(r.raw),
                        normalized_value=r.normalized, point_status=r.point_status,
                        reason=r.reason, gap_before=bool(r.gap_before), sufficiency=r.sufficiency,
                    )
                    for r in s.frame.itertuples(index=False)
                ],
            )
            for s in c.series
        ]
        composite = NarrativeComposite(
            status=c.composite_status, reason=c.composite_reason, sources=list(history.COMPOSITE_SLOTS),
            min_sources=history.MIN_AVAILABLE_SOURCES, max_gap_days=history.NARRATIVE_MAX_GAP_DAYS,
            points=[
                NarrativeCompositePoint(
                    date=r.date, value=r.value, coverage=r.coverage, sources_present=list(r.sources_present),
                    trust_weight=r.trust_weight, mixed_scale=bool(r.mixed_scale), gap_before=bool(r.gap_before),
                )
                for r in c.composite.itertuples(index=False)
            ],
        )
        cats.append(NarrativeHistoryCategory(
            category_id=c.category_id, label=c.label, keywords=c.keywords,
            coins=[NarrativeCoin(symbol=s, narrative_only=n) for s, n in c.coins],
            series=series, composite=composite,
        ))
    return NarrativeHistoryResponse(
        generated_utc=result.generated_utc,
        redistributable_all=result.redistributable_all,
        grid_dates=result.grid_dates,
        categories=cats,
        comparison=NarrativeComparison(
            as_of=result.comparison_as_of,
            entries=[NarrativeComparisonEntry(category_id=e.category_id, rank=e.rank, value=e.value,
                                              mixed_scale=e.mixed_scale, status=e.status, reason=e.reason)
                     for e in result.comparison],
        ),
        change_in_attention=NarrativeChange(
            window_days=history.CHANGE_WINDOW_DAYS,
            baseline_tolerance_days=history.CHANGE_BASELINE_TOLERANCE_DAYS,
            as_of=result.comparison_as_of,
            entries=[NarrativeChangeEntry(category_id=e.category_id, delta=e.value, rank=e.rank,
                                          baseline_date=e.baseline_date, mixed_scale=e.mixed_scale,
                                          status=e.status, reason=e.reason)
                     for e in result.change],
        ),
    )


def pd_isna(v) -> bool:
    return v is None or (isinstance(v, float) and v != v)


# --- Narrative-v2 RFC-5 (ADR-5): GET /api/narrative/mindshare. Additive only;
# shares nothing with /history.
from api.analytics.narrative import mindshare  # noqa: E402
from api.models.narrative import (  # noqa: E402
    NarrativeMindshareEntry,
    NarrativeMindshareResponse,
    NarrativeMindshareSources,
)


@router.get("/mindshare", response_model=NarrativeMindshareResponse)
def get_mindshare(day: date | None = Query(default=None, alias="date")) -> NarrativeMindshareResponse:
    """Daily cross-narrative mindshare for `date` (default: latest archived day). Read-only."""
    r = mindshare.build_mindshare(day)
    return NarrativeMindshareResponse(
        generated_utc=r.generated_utc, date=r.date, available_dates=r.available_dates,
        sources_present=r.sources_present, n_sources=r.n_sources,
        only_one_source=r.only_one_source, no_sources_available=r.no_sources_available,
        entries=[NarrativeMindshareEntry(category_id=e.category_id, label=e.label, mindshare=e.mindshare,
                                         sources=NarrativeMindshareSources(**e.sources),
                                         status=e.status, reason=e.reason)  # type: ignore[arg-type]
                 for e in r.entries],
    )
