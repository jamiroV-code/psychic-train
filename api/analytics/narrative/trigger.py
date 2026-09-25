"""Fork B narrative trigger/confirmation (items 51, 52, 47a) plus the
`compute_narrative_categories` orchestration that backs
`GET /api/narrative/categories` (item 56) — mirrors
`regime/leg_boundary.py::compute_current_leg_state`'s role for
`routers/regime.py` (Architecture Clarification: routers/ exposes HTTP
only, no router calls a provider directly).

Fork B is a rate-of-change-vs-trailing-baseline rule, the same documented,
auditable-rule shape ADR-1 chose for Fork A at leg-boundary scale, not a
formal change-point method (same rationale: too little historical ground
truth to honestly tune one).

ADR-3 governs confirmation here: a triggered-but-unconfirmed category is
never hidden from the response, only carries a lower `trust_weight` and
`confirmed=False` — confirmation changes trust weighting only, it never
gates visibility (Risk-#2 hard gate, item 53).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from api.analytics.narrative import mapping, scoring
from api.data import cache, coingecko_adapter, pytrends_adapter, reddit_adapter
from api.models.narrative import NarrativeCategory

TRIGGER_ROC_DAYS = 3
TRIGGER_ZSCORE_MIN_PERIODS = 3
TRIGGER_ZSCORE_THRESHOLD = 1.0
CONFIRMATION_SUSTAINED_DAYS = 10

BASE_TRUST_WEIGHT = 0.6
CONFIRMED_TRUST_WEIGHT = 0.9
REDUCED_SOURCE_TRUST_CAP = 0.4  # item 47a: never full-confidence on partial/dead sources
MIN_AVAILABLE_SOURCES = 2  # of 3 total (pytrends, reddit, coingecko)
TOTAL_SOURCES = ("pytrends", "reddit", "coingecko")

NARRATIVE_CATEGORIES_PATH = Path(__file__).resolve().parents[2] / "data" / "narrative_categories.json"


@dataclass
class TriggerResult:
    category_id: str
    triggered: bool
    confirmed: bool
    trust_weight: float
    trigger_date: str | None
    confirmed_date: str | None
    source_availability: dict[str, str]


KEYWORD_KEYED_SOURCES = ("pytrends", "reddit")


def _source_history_key(source: str, category_id: str, primary_keyword: str) -> str:
    """The narrative-cache key a source's history lives under. pytrends and
    reddit are fetched (and archived by their adapters) by search keyword,
    not category id — same convention `history.py` documents; coingecko is
    archived by this module under `category_id`. Reading with any other key
    silently returns an empty series.
    """
    return primary_keyword if source in KEYWORD_KEYED_SOURCES else category_id


def load_seed_categories() -> list[dict]:
    """Shared with `routers/narrative.py` so category metadata (label,
    keywords) is loaded from exactly one place, not duplicated.
    """
    if not NARRATIVE_CATEGORIES_PATH.exists():
        return []
    with open(NARRATIVE_CATEGORIES_PATH) as f:
        data = json.load(f)
    return data.get("seed_categories", [])


def compute_trigger(
    category_id: str,
    proxy_series_by_source: dict[str, pd.Series | None],
    source_status: dict[str, str],
) -> TriggerResult:
    """`proxy_series_by_source`: per-source, already within-source-normalized
    date-indexed series (`None` for a source with no usable data right
    now). `source_status`: each source's own adapter status
    (`ok`/`unavailable`/`stale`/`presumed-dead`), used only for the
    minimum-available-source-count trust-weight cap (item 47a) and surfaced
    in the API response — never used to silently substitute a neutral
    value for a missing source.
    """
    available = {s: series for s, series in proxy_series_by_source.items() if series is not None and not series.empty}
    n_available = len(available)

    if n_available == 0:
        return TriggerResult(
            category_id=category_id, triggered=False, confirmed=False, trust_weight=0.0,
            trigger_date=None, confirmed_date=None, source_availability=source_status,
        )

    # Combine already-normalized per-source series into one composite proxy
    # via a skipna mean (same "unavailable inputs excluded, never
    # zero-filled" discipline as RFC-002's liquidity composite).
    combined = pd.concat(available.values(), axis=1).mean(axis=1, skipna=True).dropna()
    if len(combined) < TRIGGER_ROC_DAYS + TRIGGER_ZSCORE_MIN_PERIODS:
        return TriggerResult(
            category_id=category_id, triggered=False, confirmed=False, trust_weight=0.0,
            trigger_date=None, confirmed_date=None, source_availability=source_status,
        )

    roc = combined.pct_change(periods=TRIGGER_ROC_DAYS)
    mean = roc.expanding(min_periods=TRIGGER_ZSCORE_MIN_PERIODS).mean()
    std = roc.expanding(min_periods=TRIGGER_ZSCORE_MIN_PERIODS).std()
    z = (roc - mean) / std

    triggered_mask = z.abs() >= TRIGGER_ZSCORE_THRESHOLD
    triggered_mask = triggered_mask.fillna(False)
    if not triggered_mask.any():
        return TriggerResult(
            category_id=category_id, triggered=False, confirmed=False, trust_weight=0.0,
            trigger_date=None, confirmed_date=None, source_availability=source_status,
        )

    trigger_idx = triggered_mask[triggered_mask].index[-1]
    trigger_date_str = trigger_idx.strftime("%Y-%m-%d") if hasattr(trigger_idx, "strftime") else str(trigger_idx)

    # item 47a: pytrends unavailable/presumed-dead, or fewer than
    # MIN_AVAILABLE_SOURCES total, caps trust_weight — never a silent
    # full-confidence trigger computed on partial sources.
    trust_weight = BASE_TRUST_WEIGHT
    if n_available < MIN_AVAILABLE_SOURCES or source_status.get("pytrends") in ("unavailable", "presumed-dead"):
        trust_weight = min(trust_weight, REDUCED_SOURCE_TRUST_CAP)

    return TriggerResult(
        category_id=category_id, triggered=True, confirmed=False, trust_weight=trust_weight,
        trigger_date=trigger_date_str, confirmed_date=None, source_availability=source_status,
    )


def apply_confirmation(state: TriggerResult, as_of: str | None = None, user_action: bool = False) -> TriggerResult:
    """ADR-3: confirmation changes `trust_weight` only, never visibility — a
    triggered-but-unconfirmed category (returned by `compute_trigger`
    above) is already visible to the caller; this function only ever
    raises `trust_weight` and sets `confirmed=True`, it never hides an
    unconfirmed one. Confirms via an explicit `user_action`, OR once
    `CONFIRMATION_SUSTAINED_DAYS` have passed since `trigger_date`.
    """
    if not state.triggered or state.confirmed:
        return state

    confirmed = False
    confirmed_date: str | None = None

    if user_action:
        confirmed = True
        confirmed_date = as_of or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    elif state.trigger_date:
        trigger_dt = datetime.strptime(state.trigger_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        as_of_dt = (
            datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if as_of
            else datetime.now(timezone.utc)
        )
        if (as_of_dt - trigger_dt).days >= CONFIRMATION_SUSTAINED_DAYS:
            confirmed = True
            confirmed_date = as_of_dt.strftime("%Y-%m-%d")

    if not confirmed:
        return state

    # A reduced-confidence trigger (item 47a's cap) stays capped even once
    # confirmed — confirmation cannot launder a partial-source reading into
    # full confidence.
    new_trust_weight = CONFIRMED_TRUST_WEIGHT if state.trust_weight > REDUCED_SOURCE_TRUST_CAP else state.trust_weight

    return TriggerResult(
        category_id=state.category_id, triggered=True, confirmed=True, trust_weight=new_trust_weight,
        trigger_date=state.trigger_date, confirmed_date=confirmed_date, source_availability=state.source_availability,
    )


def compute_narrative_categories(as_of: str | None = None) -> list[TriggerResult]:
    """Orchestrates the full RFC-003 pipeline for every seed category: fetch
    each source's today's proxy value, archive it, read back each source's
    accumulated history, normalize within-source, and run
    `compute_trigger` + `apply_confirmation`. Backs `GET
    /api/narrative/categories` (item 56).
    """
    categories = load_seed_categories()
    trending = coingecko_adapter.fetch_trending()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    results: list[TriggerResult] = []
    for cat in categories:
        category_id = cat["id"]
        primary_keyword = cat["keywords"][0] if cat.get("keywords") else category_id

        pytrends_result = pytrends_adapter.fetch_trend(primary_keyword)
        reddit_result = reddit_adapter.fetch_mentions(primary_keyword)

        # CoinGecko: today's trending-membership count for this category,
        # archived into the same per-(source, category) cache shape as the
        # other two sources so trigger computation stays source-agnostic.
        if trending.status != "unavailable":
            trending_count = sum(
                1 for symbol in trending.symbols if mapping.map_coin_to_category(symbol) == category_id
            )
            cache.write_narrative_point("coingecko", category_id, trending.as_of or today, float(trending_count))

        source_status = {
            "pytrends": pytrends_result.status,
            "reddit": reddit_result.status,
            "coingecko": trending.status,
        }

        series_by_source: dict[str, pd.Series | None] = {}
        for source in TOTAL_SOURCES:
            history = cache.read_narrative_series(source, _source_history_key(source, category_id, primary_keyword))
            if history.empty:
                series_by_source[source] = None
                continue
            s = pd.Series(history["raw_value"].to_numpy(dtype=float), index=pd.to_datetime(history["date"]))
            series_by_source[source] = scoring.normalize_within_source(s)

        result = compute_trigger(category_id, series_by_source, source_status)
        result = apply_confirmation(result, as_of=as_of or today)
        results.append(result)

    return results


def assemble_narrative_categories(as_of: str | None = None) -> list[NarrativeCategory]:
    """Shared `TriggerResult` + seed-metadata assembly (label/keywords/
    `seed` lookup), extracted so both `routers/narrative.py::get_categories`
    (item 56) and `screener_board.py` (RFC-004, item 64) get the same fully-
    shaped `NarrativeCategory` list from exactly one place — added during
    RFC-004 EXECUTE, not in the original Touchpoints list, but a direct
    consequence of the Architecture Clarification's own rule ("routers/
    exposes HTTP only") when it turned out `screener_board.py` needs this
    same assembly and is explicitly NOT a router, so it cannot call
    `routers/narrative.py` directly (same reasoning RFC-002's
    `screener_board.py::compute_current_leg_state` wiring and RFC-003's own
    `compute_narrative_categories` addition to this file already followed).
    This was previously inlined directly in `routers/narrative.py`; that
    router now just calls this function.
    """
    results = compute_narrative_categories(as_of=as_of)
    seed_meta = {c["id"]: c for c in load_seed_categories()}

    categories: list[NarrativeCategory] = []
    for result in results:
        meta = seed_meta.get(result.category_id, {})
        categories.append(
            NarrativeCategory(
                id=result.category_id,
                label=meta.get("label", result.category_id),
                keywords=meta.get("keywords", []),
                seed=result.category_id in seed_meta,
                triggered=result.triggered,
                confirmed=result.confirmed,
                trust_weight=result.trust_weight,
                source_availability=result.source_availability,  # type: ignore[arg-type]
            )
        )
    return categories
