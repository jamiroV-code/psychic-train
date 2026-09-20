"""Confidence badge (Fork C, ADR-4) — items 62, 63, 64a.

`compute_badge` implements ADR-4's literal priority-ordered rule chain and
nothing else: no other module may compute a "verdict" (Component Details).
It is deliberately the most locked-down module in this plan — Risk
Prediction #1 (HIGH) names a future refactor toward a numerically-combined
score as the single biggest implementation risk here, so this file contains
no numeric-accumulation construct anywhere (item 63(b)'s source-inspection
guard test asserts this directly against this file's own source — see that
test for the exact forbidden tokens; deliberately not spelled out here so
this docstring itself can never accidentally trip the guard it describes).

`derive_leg_context`/`derive_narrative_state` (item 64a) are the
input-derivation layer: they map RFC-002's `CurrentLegState` and RFC-003's
`NarrativeCategory` onto ADR-4's closed enums, so `compute_badge` itself
never has to know anything about leg-boundary or narrative internals — it
only ever sees the four already-closed enum values ADR-4 defines.
"""
from __future__ import annotations

from typing import Literal

from api.models.narrative import NarrativeCategory
from api.models.regime import CurrentLegState
from api.models.screener import ConfidenceState, MomentumState, TrendState

LegContext = Literal["confirmed", "candidate-pending", "unavailable"]
NarrativeState = Literal[
    "in-focus", "confirmed-emerging", "unconfirmed-emerging", "rotated-out", "unmapped", "unavailable"
]


def derive_leg_context(current_leg_state: CurrentLegState) -> LegContext:
    """ADR-4: `unavailable` when no leg data has been computed yet
    (`has_data=False`); otherwise looks at the most recently dated detected
    candidate (if any) — `confirmed` if that candidate is itself confirmed,
    OR if there is currently no open/pending candidate at all (a leg with
    zero detected boundaries is a settled, real state per ADR-3, "never
    collapses into silence" — not a failure, and not left ambiguous here);
    `candidate-pending` only when the most recent candidate is still
    unconfirmed — i.e. there is a genuinely open question about the current
    leg boundary.
    """
    if not current_leg_state.has_data:
        return "unavailable"

    candidates = current_leg_state.candidate_boundaries
    if not candidates:
        return "confirmed"

    latest = max(candidates, key=lambda c: c.date)
    return "confirmed" if latest.confirmed else "candidate-pending"


def derive_narrative_state(category: NarrativeCategory | None, *, has_mapping: bool = True) -> NarrativeState:
    """ADR-4: `category` is the coin's mapped `NarrativeCategory` (already
    looked up by the caller via `mapping.map_coin_to_category` + a
    category-id lookup against the currently fetched category list), or
    `None` when no such category was found. `has_mapping` disambiguates
    *why* `category` is `None` — this is the one place ADR-4's signature
    (`derive_narrative_state(category: NarrativeCategory | None)`) needed a
    small, documented extension beyond its literal one-argument form: a
    single `NarrativeCategory | None` cannot on its own distinguish
    "coin has no curated mapping at all" (`unmapped`) from "coin has a
    mapping, but that category wasn't among the ones actually fetched/
    computed this cycle" (`unavailable`) — and ADR-4's own rule table
    explicitly requires that distinction (priority 1's `unavailable` check
    is "only checked when the coin has a mapping attempt at all; `unmapped`
    does NOT trigger this row"). Concretely this matters today: `BTC` is
    curated to `store-of-value` (`mapping.py`), but `store-of-value` is not
    one of RFC-003's 4 seed categories, so it is never returned by
    `trigger.compute_narrative_categories()` — BTC has a real mapping
    attempt that currently always resolves to `unavailable`, not
    `unmapped`. Defaults to `True` so a direct `derive_narrative_state(None)`
    call (e.g. from a test not exercising this specific edge) still reads
    as the more common "mapping existed, data didn't" case rather than
    silently defaulting to the friendlier `unmapped`.
    """
    if category is None:
        return "unavailable" if has_mapping else "unmapped"

    available = [status for status in category.source_availability.values() if status == "ok"]
    if not available:
        # Every source for this category failed/hasn't fetched (or no
        # sources were ever recorded at all) — the narrative source itself
        # failed, per ADR-4's `unavailable` definition, distinct from a
        # healthy source that simply isn't triggered right now.
        return "unavailable"

    if not category.triggered:
        return "rotated-out"

    if category.seed:
        # A curated seed category is already an established narrative by
        # definition; once triggered, it counts as `in-focus` regardless of
        # `confirmed` — confirmation still adjusts trust (ADR-3) but doesn't
        # gate whether it counts as corroborating context here.
        return "in-focus"

    return "confirmed-emerging" if category.confirmed else "unconfirmed-emerging"


def compute_badge(
    momentum_state: MomentumState,
    trend_state: TrendState,
    leg_context: LegContext,
    narrative_state: NarrativeState,
) -> ConfidenceState:
    """ADR-4's exact priority-ordered rule chain (authoritative table lives
    in the plan doc, `## Architecture Decisions (Final)` ADR-4). Literal
    `if`/`elif` branches only — no numeric accumulation anywhere in this
    function (Risk Prediction #1, item 63(b)'s source-inspection guard).
    """
    momentum = momentum_state.state
    trend = trend_state.direction

    # Priority 1: any input reads as insufficient/unavailable -> insufficient-data.
    # `narrative_state == "unavailable"` is included here; `"unmapped"` is a
    # distinct value and deliberately does NOT match this branch.
    if momentum == "insufficient" or trend == "insufficient" or leg_context == "unavailable" or narrative_state == "unavailable":
        return "insufficient-data"

    # Priority 2: momentum and trend directly disagree -> conflicting.
    if (momentum == "PASS" and trend == "down") or (momentum == "FAIL" and trend == "up"):
        return "conflicting"

    # Priority 3: full bullish corroboration across all four signals -> aligned.
    if (
        momentum == "PASS"
        and trend == "up"
        and leg_context == "confirmed"
        and narrative_state in ("in-focus", "confirmed-emerging")
    ):
        return "aligned"

    # Priority 4 (catch-all): momentum and trend agree (bullish or bearish)
    # but priority 3's full bullish-corroboration bar isn't met. This covers
    # `leg_context == "candidate-pending"`, `narrative_state` in
    # `{"rotated-out", "unconfirmed-emerging", "unmapped"}`, and every full
    # bearish-agreement case (which can never reach `aligned` — that state
    # is defined as bullish-corroborated only).
    return "mixed"
