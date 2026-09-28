"""Per-source normalization tests (item 50) — not separately named in the
Implementation Checklist as its own numbered item, but covered here per
Rules' "numbers are never silently wrong" (calc + test pair), since
`normalize_within_source` is only otherwise exercised indirectly through
`trigger.compute_narrative_categories`'s orchestration, which itself has no
direct test this session (see EXECUTE Deviations).
"""
from __future__ import annotations

import pandas as pd

from api.analytics.narrative import scoring


class TestNormalizeWithinSource:
    def test_min_max_normalizes_to_zero_one_range(self):
        series = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = scoring.normalize_within_source(series)
        assert result.min() == 0.0
        assert result.max() == 1.0
        assert result.iloc[2] == 0.5  # midpoint

    def test_all_constant_series_normalizes_to_flat_half_not_nan(self):
        series = pd.Series([7.0, 7.0, 7.0])
        result = scoring.normalize_within_source(series)
        assert (result == 0.5).all()
        assert not result.isna().any()

    def test_empty_series_returns_empty(self):
        series = pd.Series([], dtype=float)
        result = scoring.normalize_within_source(series)
        assert result.empty


class TestNormalizeWithSufficiency:
    """Narrative-v2 ADR-1 / AC-1: thin series are insufficient, never 0.5."""

    def test_normalize_with_sufficiency_zero_points(self):
        for series in (pd.Series([], dtype=float), pd.Series([None, None], dtype=object)):
            out, status = scoring.normalize_with_sufficiency(series)
            assert status == "insufficient"
            assert len(out) == len(series)
            assert all(v is None for v in out)

    def test_normalize_with_sufficiency_one_point(self):
        out, status = scoring.normalize_with_sufficiency(pd.Series([None, 42.0, None], dtype=object))
        assert status == "insufficient"
        assert list(out) == [None, None, None]  # never a flat 0.5

    def test_provisional_below_mature_threshold_and_nulls_stay_null(self):
        out, status = scoring.normalize_with_sufficiency(pd.Series([10.0, None, 30.0], dtype=object))
        assert status == "provisional"
        assert list(out) == [0.0, None, 1.0]

    def test_mature_at_threshold(self):
        _, status = scoring.normalize_with_sufficiency(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]), mature_points=5)
        assert status == "mature"

    def test_existing_normalize_within_source_unchanged(self):
        assert (scoring.normalize_within_source(pd.Series([3.0])) == 0.5).all()
