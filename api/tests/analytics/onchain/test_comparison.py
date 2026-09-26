"""Normalised comparison (chain-growth RFC-4, D5, AC-13)."""
from __future__ import annotations

import dataclasses
from datetime import date

import numpy as np
import pandas as pd

from api.analytics.onchain import comparison as cmp
from api.models.onchain_activity import ComparisonSeriesModel


def _daily(values, start="2025-01-01") -> pd.Series:
    return pd.Series(np.asarray(values, float), index=pd.date_range(start, periods=len(values), freq="D"))


def test_constant_series_indexes_to_100():
    idx, base, late = cmp.rebase_index(_daily(np.full(100, 42.0)), date(2025, 2, 1))
    assert base == date(2025, 2, 1) and not late
    assert idx.index[0] == pd.Timestamp("2025-02-01")
    assert np.allclose(idx.to_numpy(), 100.0)


def test_growth_ratio_preserved():
    idx, _, _ = cmp.rebase_index(_daily(np.full(300, 10.0)).where(lambda s: s.index < "2025-06-01", 20.0), date(2025, 1, 10))
    assert idx.iloc[-1] > 190  # converging to 200 (2x)


def test_rebased_late_when_series_starts_after_start():
    idx, base, late = cmp.rebase_index(_daily(np.full(30, 5.0), start="2025-06-01"), date(2025, 1, 1))
    assert late and base == date(2025, 6, 1)
    assert idx.iloc[0] == 100.0


def test_start_after_series_end():
    idx, base, late = cmp.rebase_index(_daily(np.full(10, 5.0)), date(2030, 1, 1))
    assert idx.empty and base is None


def test_log_safe_non_positive_is_none():
    s = _daily(np.concatenate([np.full(10, 5.0), np.full(10, 0.0)]))
    cs = cmp.build_comparison_series("x", s, date(2025, 1, 1), [d.date().isoformat() for d in s.index])
    assert all(v is None or v > 0 for v in cs.index_values)


def test_pct_above_low():
    s = _daily(np.concatenate([np.full(200, 100.0), np.full(200, 200.0)]))
    p = cmp.pct_above_rolling_low(s).dropna()
    assert p.index[0] == pd.Timestamp("2025-01-01") + pd.Timedelta(days=179)
    assert p.iloc[0] == 0
    assert p.max() > 90  # just after the step
    assert p.iloc[-1] < p.max()  # the 180d low catches up afterwards


def test_values_aligned_to_grid_with_nulls():
    s = _daily(np.full(5, 1.0), start="2025-01-03")
    grid = ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-07"]
    cs = cmp.build_comparison_series("x", s, date(2025, 1, 3), grid)
    assert cs.index_values[:2] == [None, None] and cs.index_values[2] == 100.0
    assert len(cs.pct_above_low_values) == len(grid)


def test_ac13_no_raw_value_field():
    names = {f.name for f in dataclasses.fields(cmp.ComparisonSeries)} | set(ComparisonSeriesModel.model_fields)
    assert not names & {"value", "values", "raw", "raw_values", "points"}


def test_defaults():
    assert cmp.LOG_SCALE_DEFAULT is True
    assert cmp.DEFAULT_RANGE_DAYS == 365
