"""Confidence badge tests (items 63, 64a) — Risk Predictions #1 (HIGH) and
#5 (MEDIUM) hard gates.

Four independent checks, matching the Implementation Checklist exactly:
(a) exhaustive enumeration across all 162 closed-enum input combinations
    (3 momentum x 3 trend x 3 leg_context x 6 narrative_state), asserting
    every one matches ADR-4's table and none raises/returns None;
(b) source-inspection guard — `badge.py`'s own source contains no
    numeric-accumulation construct;
(c) insufficient-data wins over conflicting when both would otherwise apply;
(d) the three specific combinations VALIDATE found falling through the
    original (pre-fix) table.
"""
from __future__ import annotations

import inspect
import itertools

from api.analytics.confidence import badge
from api.models.narrative import NarrativeCategory
from api.models.regime import CurrentLegState, LegBoundary
from api.models.screener import MomentumState, TrendState

MOMENTUM_VALUES = ("PASS", "FAIL", "insufficient")
TREND_VALUES = ("up", "down", "insufficient")
LEG_CONTEXT_VALUES = ("confirmed", "candidate-pending", "unavailable")
NARRATIVE_STATE_VALUES = (
    "in-focus", "confirmed-emerging", "unconfirmed-emerging", "rotated-out", "unmapped", "unavailable",
)


def _badge(momentum: str, trend: str, leg_context: str, narrative_state: str) -> str:
    return badge.compute_badge(
        MomentumState(state=momentum), TrendState(direction=trend), leg_context, narrative_state
    )


def _expected(momentum: str, trend: str, leg_context: str, narrative_state: str) -> str:
    """Independent restatement of ADR-4's corrected table (plan doc,
    `## Architecture Decisions (Final)`), used to lock in the table itself
    as a regression guard — not merely a re-assertion of `compute_badge`'s
    own implementation.
    """
    if momentum == "insufficient" or trend == "insufficient" or leg_context == "unavailable" or narrative_state == "unavailable":
        return "insufficient-data"
    if (momentum == "PASS" and trend == "down") or (momentum == "FAIL" and trend == "up"):
        return "conflicting"
    if momentum == "PASS" and trend == "up" and leg_context == "confirmed" and narrative_state in ("in-focus", "confirmed-emerging"):
        return "aligned"
    return "mixed"


class TestExhaustiveEnumeration:
    def test_every_combination_matches_adr4_table_and_never_none(self):
        combos = list(itertools.product(MOMENTUM_VALUES, TREND_VALUES, LEG_CONTEXT_VALUES, NARRATIVE_STATE_VALUES))
        assert len(combos) == 162  # 3 x 3 x 3 x 6, per ADR-4's closed enums

        for momentum, trend, leg_context, narrative_state in combos:
            actual = _badge(momentum, trend, leg_context, narrative_state)
            assert actual is not None
            assert actual in ("aligned", "mixed", "conflicting", "insufficient-data")
            expected = _expected(momentum, trend, leg_context, narrative_state)
            assert actual == expected, (momentum, trend, leg_context, narrative_state, actual, expected)


class TestSourceInspectionGuard:
    def test_badge_source_has_no_numeric_accumulation_construct(self):
        source = inspect.getsource(badge)
        forbidden = ("sum(", "_weight", "average")
        for token in forbidden:
            assert token not in source, f"forbidden token {token!r} found in badge.py — see Risk Prediction #1"


class TestInsufficientPriority:
    def test_insufficient_takes_priority_over_conflicting(self):
        # momentum PASS + trend down would read `conflicting` on its own,
        # but leg_context unavailable must win (priority 1 beats priority 2).
        result = _badge("PASS", "down", "unavailable", "in-focus")
        assert result == "insufficient-data"

        # Same shape, this time momentum itself is insufficient.
        result = _badge("insufficient", "down", "confirmed", "in-focus")
        assert result == "insufficient-data"


class TestPreviouslyUnhandledCombinations:
    """Regression test for the three combinations VALIDATE found falling
    through the original (pre-fix) 4-row table (see ADR-4's note)."""

    def test_full_bearish_agreement_with_strong_context_is_mixed_not_undefined(self):
        result = _badge("FAIL", "down", "confirmed", "in-focus")
        assert result == "mixed"  # never `aligned` — that state is bullish-corroborated only

    def test_confirmed_emerging_without_in_focus_still_reaches_aligned(self):
        result = _badge("PASS", "up", "confirmed", "confirmed-emerging")
        assert result == "aligned"

    def test_leg_context_unavailable_with_everything_else_healthy_is_insufficient(self):
        result = _badge("PASS", "up", "unavailable", "in-focus")
        assert result == "insufficient-data"


class TestDeriveLegContext:
    def test_no_data_is_unavailable(self):
        state = CurrentLegState(candidate_boundaries=[], confirmed_boundaries=[], composite_variant="reduced", has_data=False)
        assert badge.derive_leg_context(state) == "unavailable"

    def test_data_but_zero_boundaries_is_confirmed_not_a_failure(self):
        # ADR-3: zero detected boundaries is a real, visible state, not a
        # failure — must not collapse into `unavailable`.
        state = CurrentLegState(candidate_boundaries=[], confirmed_boundaries=[], composite_variant="reduced", has_data=True)
        assert badge.derive_leg_context(state) == "confirmed"

    def test_most_recent_candidate_confirmed_is_confirmed(self):
        state = CurrentLegState(
            candidate_boundaries=[LegBoundary(date="2024-01-01", z_score=2.0, confirmed=True, confirmed_date="2024-01-05")],
            confirmed_boundaries=[LegBoundary(date="2024-01-01", z_score=2.0, confirmed=True, confirmed_date="2024-01-05")],
            composite_variant="reduced", has_data=True,
        )
        assert badge.derive_leg_context(state) == "confirmed"

    def test_most_recent_candidate_unconfirmed_is_candidate_pending(self):
        state = CurrentLegState(
            candidate_boundaries=[
                LegBoundary(date="2024-01-01", z_score=2.0, confirmed=True, confirmed_date="2024-01-05"),
                LegBoundary(date="2024-06-01", z_score=1.8, confirmed=False),
            ],
            confirmed_boundaries=[LegBoundary(date="2024-01-01", z_score=2.0, confirmed=True, confirmed_date="2024-01-05")],
            composite_variant="reduced", has_data=True,
        )
        assert badge.derive_leg_context(state) == "candidate-pending"


class TestDeriveNarrativeState:
    def _category(self, **overrides) -> NarrativeCategory:
        defaults = dict(
            id="ai", label="AI", keywords=["ai"], seed=True, triggered=True, confirmed=False,
            trust_weight=0.6, source_availability={"pytrends": "ok", "reddit": "ok", "coingecko": "ok"},
        )
        defaults.update(overrides)
        return NarrativeCategory(**defaults)

    def test_no_mapping_at_all_is_unmapped(self):
        assert badge.derive_narrative_state(None, has_mapping=False) == "unmapped"

    def test_mapping_exists_but_category_not_found_is_unavailable(self):
        # BTC's real case: mapped to `store-of-value`, which is never a seed
        # category, so it's never found in the fetched category list.
        assert badge.derive_narrative_state(None, has_mapping=True) == "unavailable"

    def test_all_sources_failed_is_unavailable_even_if_triggered(self):
        category = self._category(source_availability={"pytrends": "unavailable", "reddit": "unavailable", "coingecko": "presumed-dead"})
        assert badge.derive_narrative_state(category) == "unavailable"

    def test_untriggered_seed_category_is_rotated_out(self):
        category = self._category(seed=True, triggered=False)
        assert badge.derive_narrative_state(category) == "rotated-out"

    def test_triggered_seed_category_is_in_focus_regardless_of_confirmed(self):
        assert badge.derive_narrative_state(self._category(seed=True, triggered=True, confirmed=False)) == "in-focus"
        assert badge.derive_narrative_state(self._category(seed=True, triggered=True, confirmed=True)) == "in-focus"

    def test_triggered_non_seed_confirmed_is_confirmed_emerging(self):
        category = self._category(seed=False, triggered=True, confirmed=True)
        assert badge.derive_narrative_state(category) == "confirmed-emerging"

    def test_triggered_non_seed_unconfirmed_is_unconfirmed_emerging(self):
        category = self._category(seed=False, triggered=True, confirmed=False)
        assert badge.derive_narrative_state(category) == "unconfirmed-emerging"


class TestDerivationMatchesUpstreamModels:
    """Item 64a: every real field combination `CurrentLegState`/
    `NarrativeCategory` can actually produce maps to exactly one closed-enum
    value — closes the "RFC-004 might silently invent a mapping that
    doesn't match what RFC-002/003 actually produce" gap VALIDATE flagged.
    """

    def test_derive_leg_context_never_raises_or_returns_unlisted_value(self):
        has_data_options = (True, False)
        boundary_sets = (
            [],
            [LegBoundary(date="2024-01-01", z_score=1.5, confirmed=True, confirmed_date="2024-01-04")],
            [LegBoundary(date="2024-01-01", z_score=1.5, confirmed=False)],
        )
        for has_data in has_data_options:
            for boundaries in boundary_sets:
                state = CurrentLegState(
                    candidate_boundaries=boundaries, confirmed_boundaries=[b for b in boundaries if b.confirmed],
                    composite_variant="reduced", has_data=has_data,
                )
                result = badge.derive_leg_context(state)
                assert result in ("confirmed", "candidate-pending", "unavailable")

    def test_derive_narrative_state_never_raises_or_returns_unlisted_value_across_all_real_fields(self):
        for seed in (True, False):
            for triggered in (True, False):
                for confirmed in (True, False):
                    for availability in (
                        {"pytrends": "ok", "reddit": "ok", "coingecko": "ok"},
                        {"pytrends": "unavailable", "reddit": "unavailable", "coingecko": "unavailable"},
                        {"pytrends": "presumed-dead", "reddit": "ok", "coingecko": "ok"},
                    ):
                        category = NarrativeCategory(
                            id="x", label="X", keywords=[], seed=seed, triggered=triggered, confirmed=confirmed,
                            trust_weight=0.6, source_availability=availability,
                        )
                        result = badge.derive_narrative_state(category)
                        assert result in NARRATIVE_STATE_VALUES
        assert badge.derive_narrative_state(None, has_mapping=False) in NARRATIVE_STATE_VALUES
        assert badge.derive_narrative_state(None, has_mapping=True) in NARRATIVE_STATE_VALUES
