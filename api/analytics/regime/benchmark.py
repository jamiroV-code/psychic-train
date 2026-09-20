"""Regime-dependent BTC/HYPE benchmark switch — real logic (RFC-002, item 44).

SPEC AC-3: "BTC while BTC-dominant / early in a leg, switching to HYPE once
rotation into alts is confirmed for that leg." The most recent leg-boundary
event (by date, across both the candidate and confirmed lists in
`CurrentLegState`) decides it: if that most recent event is a CONFIRMED one,
rotation has been structurally confirmed for the current leg -> HYPE; if the
most recent event is still only a candidate (or there is no leg data at all
yet), we're still BTC-dominant / early in the leg -> BTC. This is an
explicit, auditable rule per this plan's ADRs (no hidden judgment) — it is
the simplest rule expressible from the data `leg_boundary.py` actually
produces (candidate + confirmed dates; no separate leg-phase classifier was
specified elsewhere in SPEC/PLAN).

This replaces RFC-001's `RegimeState` stub wholesale (item 44) —
`BenchmarkSelection`'s own shape (Public Contracts, `models/screener.py`) is
unchanged by the swap; `RegimeState` itself is left defined in
`models/screener.py` (already documented there as intentionally throwaway
and not extended in place) but is no longer used by this module.
"""
from __future__ import annotations

from api.models.regime import CurrentLegState
from api.models.screener import BenchmarkSelection

NO_DATA_REASON = "no leg data computed yet — defaulting to BTC (ADR-3: unavailable, not guessed)"


def select_active_benchmark(current_leg_state: CurrentLegState) -> BenchmarkSelection:
    if not current_leg_state.has_data:
        return BenchmarkSelection(active="BTC", reason=NO_DATA_REASON)

    latest_confirmed = max((b.date for b in current_leg_state.confirmed_boundaries), default=None)
    latest_candidate = max((b.date for b in current_leg_state.candidate_boundaries), default=None)

    if latest_confirmed is not None and (latest_candidate is None or latest_confirmed >= latest_candidate):
        return BenchmarkSelection(
            active="HYPE",
            reason=f"rotation into alts confirmed at {latest_confirmed} (most recent leg-boundary event is confirmed)",
        )

    return BenchmarkSelection(
        active="BTC",
        reason="BTC-dominant / early in the current leg — most recent leg-boundary event is not yet confirmed",
    )
