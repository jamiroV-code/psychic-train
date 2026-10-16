"""Hand-computed basket scoring through build_attention (AC-36, AC-24, AC-35)."""
from __future__ import annotations

import pytest

from api.analytics.attention.basket import build_attention
from api.tests.analytics.attention.conftest import (
    SOURCES, TODAY, make_layout, put, put_refs, write_configs,
)


def _build(tmp_path, layout, window=30, **cfg):
    probe, w, u = write_configs(tmp_path, **cfg)
    return build_attention(window, layout=layout, today=TODAY, probe_path=probe, weights_path=w, universe_path=u)


@pytest.fixture
def two_baskets(isolated_cache):
    put_refs()
    # last7 vs refs 1..4: 0.5 -> rank 0, 1.5 -> 25, 2.5 -> 50, 3.5 -> 75, 4.5 -> 100
    for s in SOURCES:
        for sym, a in (("A1", 1.5), ("A2", 2.5), ("A3", 3.5), ("B1", 0.5), ("B2", 1.5), ("B3", 2.5)):
            put(s, sym, a)
    return make_layout({"main": ["Z1"], "alpha": ["A1", "A2", "A3"], "beta": ["B1", "B2", "B3"]})


def test_two_baskets_three_coins_three_sources(two_baskets, tmp_path):
    body = _build(tmp_path, two_baskets, window=7)
    by = {b.id: b for b in body.baskets}
    assert set(by) == {"alpha", "beta"}  # main is never scored
    a, b = by["alpha"], by["beta"]
    assert [c.score for c in a.coins] == pytest.approx([25.0, 50.0, 75.0])
    assert a.score == pytest.approx(50.0)
    assert b.score == pytest.approx(25.0)  # (0 + 25 + 50) / 3
    assert a.coverage == "covers 3 of 3" and a.status == "ok"
    assert a.universe_size == 4 == b.universe_size  # outside coins placed, not added
    assert body.membership_as_of == "2026-10-15T10:00:00Z"
    assert not hasattr(body, "total") and "total" not in body.model_dump()


def test_series_rebased_to_100_and_change(two_baskets, tmp_path):
    body = _build(tmp_path, two_baskets, window=7)
    by = {b.id: b for b in body.baskets}
    sa, sb = by["alpha"].series, by["beta"].series
    assert len(sa) == 8 and sa[0].value == pytest.approx(100.0)  # score 50 at window start
    assert sa[-1].value == pytest.approx(100.0) and by["alpha"].change == pytest.approx(0.0)
    assert sb[0].value == pytest.approx(100.0)  # start score 50
    assert sb[-1].value == pytest.approx(50.0)  # 25 / 50 * 100
    assert by["beta"].change == pytest.approx(-25.0)


def test_dominant_coin_breadth_one_third(two_baskets, tmp_path):
    body = _build(tmp_path, two_baskets, window=7)
    by = {b.id: b for b in body.baskets}
    # at d-7 every ratio is flat (1.0): all ties, rank 50. Only A3 (75) exceeds it.
    assert by["alpha"].breadth == pytest.approx(1 / 3)
    assert by["beta"].breadth == pytest.approx(0.0)


def test_missing_source_two_of_three(isolated_cache, tmp_path):
    put_refs()
    put("wikipedia", "M1", 1.5)
    put("coingecko", "M1", 3.5)  # trends has no stored data
    body = _build(tmp_path, make_layout({"main": [], "alpha": ["M1"]}))
    coin = body.baskets[0].coins[0]
    assert coin.score == pytest.approx((25.0 + 75.0) / 2)
    assert (coin.sources_used, coin.sources_total) == (2, 3)
    miss = next(s for s in coin.sources if s.source == "trends")
    assert miss.state == "unavailable" and miss.rank is None and miss.ratio is None and miss.raw is None


def test_not_probed_source_feeds_nothing(isolated_cache, tmp_path):
    put_refs()
    for s in SOURCES:
        put(s, "M1", 1.5)
    body = _build(tmp_path, make_layout({"main": [], "alpha": ["M1"]}), sources=("wikipedia", "coingecko"))
    coin = body.baskets[0].coins[0]
    tr = next(s for s in coin.sources if s.source == "trends")
    assert tr.state == "not-probed" and tr.rank is None
    assert (coin.sources_used, coin.sources_total) == (2, 3)


def test_coin_outside_top_100_placed_above_all(isolated_cache, tmp_path):
    put_refs()
    for s in SOURCES:
        put(s, "BIG", 9.0)
    body = _build(tmp_path, make_layout({"main": [], "alpha": ["BIG"]}))
    assert body.baskets[0].coins[0].score == pytest.approx(100.0)
    assert body.baskets[0].universe_size == 4


def test_all_missing_is_no_data_never_zero(isolated_cache, tmp_path):
    put_refs()
    body = _build(tmp_path, make_layout({"main": [], "alpha": ["N1", "N2"]}))
    b = body.baskets[0]
    assert b.status == "no-data" and b.reason
    assert b.score is None and b.change is None and b.breadth is None
    assert b.coverage == "covers 0 of 2"
    assert all(c.score is None for c in b.coins)
    assert all(p.value is None for p in b.series)


def test_empty_basket(isolated_cache, tmp_path):
    put_refs()
    body = _build(tmp_path, make_layout({"main": ["Z"], "alpha": []}))
    b = body.baskets[0]
    assert b.status == "empty" and b.score is None and b.coins == []
    assert b.coverage == "covers 0 of 0"


def test_no_reference_data_makes_ranking_unavailable(isolated_cache, tmp_path):
    for s in SOURCES:
        put(s, "A1", 2.0)
    body = _build(tmp_path, make_layout({"main": [], "alpha": ["A1"]}))
    assert body.baskets[0].status == "no-data" and body.baskets[0].score is None
