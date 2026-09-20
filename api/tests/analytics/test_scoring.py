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
