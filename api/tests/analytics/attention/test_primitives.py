"""Hand-computed ratio, rank and coin-score primitives (AC-36)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from api.analytics.attention.ratio import attention_ratio
from api.analytics.attention.rank import percentile
from api.analytics.attention.score import coin_score


def _pts(values):
    d0 = date(2026, 1, 1)
    return [(d0 + timedelta(days=i), v) for i, v in enumerate(values)]


def test_ratio_is_mean7_over_mean90():
    pts = _pts([1.0] * 83 + [8.0] * 7)  # mean7 = 8, mean90 = (83 + 56) / 90
    assert attention_ratio(pts) == pytest.approx(8.0 / (139.0 / 90.0))


def test_ratio_uses_only_last_90_and_sorts_by_date():
    pts = _pts([1000.0] * 10 + [2.0] * 90)
    assert attention_ratio(list(reversed(pts))) == pytest.approx(1.0)


def test_ratio_none_under_90_points_or_zero_mean():
    assert attention_ratio(_pts([1.0] * 89)) is None
    assert attention_ratio(_pts([0.0] * 90)) is None


def test_percentile_strictly_between_and_extremes():
    refs = [1.0, 2.0, 3.0, 4.0]
    assert percentile(2.5, refs) == 50.0
    assert percentile(0.1, refs) == 0.0
    assert percentile(9.0, refs) == 100.0


def test_percentile_ties_averaged_and_refs_untouched():
    refs = [1.0, 2.0, 2.0, 4.0]
    assert percentile(2.0, refs) == pytest.approx((1 + 0.5 * 2) / 4 * 100)
    assert refs == [1.0, 2.0, 2.0, 4.0]


def test_percentile_empty_reference_is_none():
    assert percentile(1.0, []) is None


def test_coin_score_weighted_mean_renormalised():
    ranks = {"a": 20.0, "b": 80.0, "c": None}
    score, used, total = coin_score(ranks, {"a": 1.0, "b": 3.0, "c": 5.0})
    assert score == pytest.approx((20 * 1 + 80 * 3) / 4)
    assert (used, total) == (2, 3)


def test_coin_score_all_missing_is_none_not_zero():
    assert coin_score({"a": None, "b": None}, {"a": 1.0, "b": 1.0}) == (None, 0, 2)
