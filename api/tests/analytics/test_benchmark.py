"""Tests for the real regime-dependent benchmark switch (item 45 —
re-points RFC-001's `test_benchmark.py` at real `CurrentLegState` fixtures,
replacing the throwaway `RegimeState` stub fixtures).

SPEC AC-3: BTC while BTC-dominant/early in a leg, HYPE once rotation into
alts is confirmed for that leg.
"""
from __future__ import annotations

from api.analytics.regime.benchmark import select_active_benchmark
from api.models.regime import CurrentLegState, LegBoundary
from api.models.screener import BenchmarkSelection


def _state(candidates: list[LegBoundary], confirmed: list[LegBoundary], has_data: bool = True, variant: str = "reduced") -> CurrentLegState:
    return CurrentLegState(candidate_boundaries=candidates, confirmed_boundaries=confirmed, composite_variant=variant, has_data=has_data)


def test_no_leg_data_defaults_to_btc_with_explicit_reason():
    result = select_active_benchmark(_state([], [], has_data=False))
    assert isinstance(result, BenchmarkSelection)
    assert result.active == "BTC"
    assert result.reason  # never a blank/silent reason


def test_no_boundaries_yet_stays_btc_dominant():
    """Early in a leg — no candidate or confirmed boundary at all yet."""
    result = select_active_benchmark(_state([], [], has_data=True))
    assert result.active == "BTC"


def test_only_unconfirmed_candidate_stays_btc():
    """A candidate exists but hasn't been structurally confirmed — still
    BTC-dominant/early in the leg per SPEC AC-3."""
    candidates = [LegBoundary(date="2024-06-01", z_score=1.8, confirmed=False)]
    result = select_active_benchmark(_state(candidates, [], has_data=True))
    assert result.active == "BTC"


def test_confirmed_rotation_switches_to_hype():
    """A confirmed boundary that is the most recent leg-boundary event ->
    rotation into alts confirmed -> HYPE (SPEC AC-3)."""
    boundary = LegBoundary(date="2024-06-01", z_score=1.8, confirmed=True, confirmed_date="2024-06-05")
    result = select_active_benchmark(_state([boundary], [boundary], has_data=True))
    assert result.active == "HYPE"
    assert "2024-06-01" in result.reason


def test_newer_unconfirmed_candidate_after_an_older_confirmation_reverts_to_btc():
    """A later, still-unconfirmed candidate is the most recent event ->
    we're back to early-in-a-new-leg -> BTC, even though an earlier
    boundary was confirmed."""
    older_confirmed = LegBoundary(date="2024-01-01", z_score=1.8, confirmed=True, confirmed_date="2024-01-05")
    newer_candidate = LegBoundary(date="2024-06-01", z_score=-1.7, confirmed=False)
    result = select_active_benchmark(_state([older_confirmed, newer_candidate], [older_confirmed], has_data=True))
    assert result.active == "BTC"


def test_benchmark_selection_is_deterministic_across_calls():
    boundary = LegBoundary(date="2024-06-01", z_score=1.8, confirmed=True, confirmed_date="2024-06-05")
    state = _state([boundary], [boundary], has_data=True)
    a = select_active_benchmark(state)
    b = select_active_benchmark(state)
    assert a == b
