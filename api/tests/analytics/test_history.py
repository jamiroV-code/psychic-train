"""Narrative dashboard RFC-3: history/composite/rank/change maths (ADR-5).

Every test goes through the real cache writers/readers under `isolated_cache`
(AC-2), never hand-built parquet. No network.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from api.analytics.narrative import history, trigger
from api.data import cache

TODAY = date(2026, 9, 24)
AI_KW = "AI crypto"
L2_KW = "layer 2 crypto"


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _exchange(cat: str, day: str, share, count=None, listing_status="ok", listing_reason=None, volume_status="ok"):
    cache.write_exchange_point(cat, {
        "date": day, "volume_share": share, "volume_status": volume_status, "volume_reason": None,
        "new_listing_count": count, "listing_status": listing_status, "listing_reason": listing_reason,
        "baseline_date": None,
    })


def _cat(result, cid):
    return next(c for c in result.categories if c.category_id == cid)


def _series(cat, source, variant=None):
    return next(s for s in cat.series if s.source == source and s.variant == variant)


def _composite(cat) -> dict[str, float]:
    return dict(zip(cat.composite["date"], cat.composite["value"]))


class TestCacheRoundTrip:
    def test_pytrends_and_reddit_read_by_keyword_not_category_id(self, isolated_cache):
        cache.write_narrative_point("pytrends", AI_KW, _d(0), 40.0)
        cache.write_narrative_point("reddit", AI_KW, _d(0), 7.0)
        cache.write_narrative_point("pytrends", "ai", _d(0), 99.0)  # wrong key: must be ignored
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        py = _series(cat, "pytrends", "nightly-7d")
        assert py.cache_key == AI_KW
        assert list(py.frame["raw"]) == [40.0]
        assert list(_series(cat, "reddit").frame["raw"]) == [7.0]
        assert (isolated_cache / "narrative" / "pytrends" / f"{AI_KW}.parquet").exists()

    def test_history_accumulates_many_archived_days(self, isolated_cache):
        for i in range(-5, 1):
            cache.write_narrative_point("reddit", AI_KW, _d(i), float(10 + i))
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        assert len(_series(cat, "reddit").frame) == 6


class TestComposite:
    def test_golden_three_source_composite(self, isolated_cache):
        for i, (p, r, v) in enumerate([(0, 30, 0.1), (50, 20, 0.1), (100, 10, 0.3)]):
            cache.write_narrative_point("pytrends", AI_KW, _d(i - 2), float(p))
            cache.write_narrative_point("reddit", AI_KW, _d(i - 2), float(r))
            _exchange("ai", _d(i - 2), v)
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        comp = _composite(cat)
        assert comp[_d(-2)] == pytest.approx(1 / 3)
        assert comp[_d(-1)] == pytest.approx(1 / 3)
        assert comp[_d(0)] == pytest.approx(2 / 3)
        last = cat.composite.iloc[-1]
        assert last["coverage"] == pytest.approx(3 / 4)
        assert last["sources_present"] == ["pytrends", "reddit", "exchange_volume_share"]
        assert last["trust_weight"] == trigger.BASE_TRUST_WEIGHT

    def test_one_source_missing_still_computes_over_remaining(self, isolated_cache):
        for i in range(3):
            cache.write_narrative_point("pytrends", AI_KW, _d(i - 2), float(i))
            cache.write_narrative_point("reddit", AI_KW, _d(i - 2), float(i))
        cache.write_narrative_point("reddit", AI_KW, _d(-3), 0.0)  # reddit alone on -3
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        comp = _composite(cat)
        assert _d(-3) not in comp  # 1 source: no point, not 0/NaN
        assert len(comp) == 3
        assert all(v == v for v in comp.values())

    def test_only_one_source_ever_means_composite_unavailable(self, isolated_cache):
        cache.write_narrative_point("reddit", AI_KW, _d(0), 5.0)
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        assert cat.composite.empty
        assert cat.composite_status == "unavailable"
        assert "insufficient-coverage" in cat.composite_reason

    def test_trust_weight_capped_when_pytrends_absent(self, isolated_cache):
        # two points each: single-point series are insufficient (narrative-v2 ADR-1)
        for off in (-1, 0):
            cache.write_narrative_point("reddit", AI_KW, _d(off), 5.0 + off)
            _exchange("ai", _d(off), 0.2 + off / 10)
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        assert cat.composite.iloc[0]["trust_weight"] == trigger.REDUCED_SOURCE_TRUST_CAP

    def test_within_source_boundary_scale_invariant(self, isolated_cache, tmp_path, monkeypatch):
        """AC-10: multiplying one source's raw values by 1000 cannot change the
        composite — there is no cross-source raw comparison anywhere."""
        def run(scale: float, root: Path):
            monkeypatch.setattr(cache, "CACHE_ROOT", root)
            for i, (p, r) in enumerate([(1, 3), (2, 1), (4, 2)]):
                cache.write_narrative_point("pytrends", AI_KW, _d(i), float(p))
                cache.write_narrative_point("reddit", AI_KW, _d(i), float(r) * scale)
            return _composite(_cat(history.build_narrative_history(["ai"], today=TODAY), "ai"))
        assert run(1.0, tmp_path / "a") == pytest.approx(run(1000.0, tmp_path / "b"))

    def test_legacy_coingecko_shown_but_excluded(self, isolated_cache):
        for i in range(3):
            cache.write_narrative_point("coingecko", "ai", _d(i - 2), 0.0)
            cache.write_narrative_point("reddit", AI_KW, _d(i - 2), float(i))
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        cg = _series(cat, "coingecko")
        assert cg.in_composite is False
        assert "legacy-map" in cg.label and "legacy-map" in cg.reason
        assert len(cg.frame) == 3
        assert cat.composite.empty  # reddit alone; the legacy count never counts

    def test_coingecko_narrative_absent_is_unavailable(self, isolated_cache):
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        s = _series(cat, "coingecko-narrative")
        assert s.status == "unavailable" and s.frame.empty and s.in_composite

    def test_coingecko_narrative_joins_composite_when_present(self, isolated_cache):
        for i in range(3):
            cache.write_narrative_point("reddit", AI_KW, _d(i - 2), float(i))
            cache.write_narrative_point("coingecko-narrative", "ai", _d(i - 2), float(2 - i))
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        assert len(cat.composite) == 3
        assert "coingecko-narrative" in cat.composite.iloc[0]["sources_present"]
        assert _composite(cat)[_d(0)] == pytest.approx(0.5)

    def test_new_listing_count_display_only(self, isolated_cache):
        # two points each: single-point series are insufficient (narrative-v2 ADR-1)
        _exchange("ai", _d(-1), 0.1, count=None, listing_status="unavailable", listing_reason="no-baseline-yet")
        _exchange("ai", _d(0), 0.2, count=None, listing_status="unavailable", listing_reason="no-baseline-yet")
        cache.write_narrative_point("reddit", AI_KW, _d(-1), 4.0)
        cache.write_narrative_point("reddit", AI_KW, _d(0), 5.0)
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        nl = _series(cat, "exchange_new_listings")
        assert nl.in_composite is False
        row = nl.frame.iloc[0]
        assert row["raw"] is None or pd.isna(row["raw"])
        assert row["normalized"] is None
        assert row["reason"] == "no-baseline-yet"
        assert nl.status == "unavailable" and nl.reason == "no-baseline-yet"
        assert cat.composite.iloc[0]["sources_present"] == ["reddit", "exchange_volume_share"]


class TestPytrendsVariants:
    def test_separate_series_separately_normalised_and_mixed_scale(self, isolated_cache):
        cache.write_narrative_point("pytrends", AI_KW, _d(-20), 10.0, source_status="backfilled")
        cache.write_narrative_point("pytrends", AI_KW, _d(-19), 90.0, source_status="backfilled")
        cache.write_narrative_point("pytrends", AI_KW, _d(-1), 50.0)
        cache.write_narrative_point("pytrends", AI_KW, _d(0), 60.0)
        for i in (-20, -19, -1, 0):
            cache.write_narrative_point("reddit", AI_KW, _d(i), 1.0)
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        bf = _series(cat, "pytrends", "backfill-269d")
        nt = _series(cat, "pytrends", "nightly-7d")
        assert list(bf.frame["normalized"]) == [0.0, 1.0]
        assert list(nt.frame["normalized"]) == [0.0, 1.0]  # not spliced with 10..90
        mixed = dict(zip(cat.composite["date"], cat.composite["mixed_scale"]))
        assert mixed == {_d(-20): True, _d(-19): True, _d(-1): False, _d(0): False}
        assert set(cat.composite["coverage"]) == {0.5}  # pytrends counted once per date


class TestFilteringAndGaps:
    def test_normalisation_stable_under_start_end(self, isolated_cache):
        for i, v in enumerate([0, 50, 100]):
            cache.write_narrative_point("reddit", AI_KW, _d(i - 2), float(v))
        full = _series(_cat(history.build_narrative_history(["ai"], today=TODAY), "ai"), "reddit")
        cut = _series(_cat(history.build_narrative_history(
            ["ai"], start=TODAY - timedelta(days=1), end=TODAY - timedelta(days=1), today=TODAY), "ai"), "reddit")
        assert list(cut.frame["normalized"]) == [0.5]
        assert list(full.frame["normalized"]) == [0.0, 0.5, 1.0]

    def test_gap_flags_boundary_and_survive_filtering(self, isolated_cache):
        for off in (-10, -8, -5):  # steps of 2 then 3 days
            cache.write_narrative_point("reddit", AI_KW, _d(off), 1.0)
        s = _series(_cat(history.build_narrative_history(["ai"], today=TODAY), "ai"), "reddit")
        assert list(s.frame["gap_before"]) == [False, False, True]
        cut = _series(_cat(history.build_narrative_history(
            ["ai"], start=TODAY - timedelta(days=5), today=TODAY), "ai"), "reddit")
        assert list(cut.frame["gap_before"]) == [True]

    def test_gap_before_flags_helper(self):
        assert history.gap_before_flags(["2026-01-01", "2026-01-03", "2026-01-06"]) == [False, False, True]


class TestStatus:
    def test_age_rules(self, isolated_cache):
        cache.write_narrative_point("reddit", AI_KW, _d(-1), 1.0)
        cache.write_narrative_point("pytrends", AI_KW, _d(-8), 1.0)
        cache.write_narrative_point("coingecko", "ai", _d(-3), 1.0)
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        assert _series(cat, "reddit").status == "ok"
        assert _series(cat, "pytrends", "nightly-7d").status == "presumed-dead"
        cg = _series(cat, "coingecko")
        assert cg.status == "stale" and cg.reason == "last-point-3-days-old"


class TestRanking:
    def test_competition_rank_ties(self):
        assert history.competition_rank({"a": 0.5, "b": 0.5, "c": 0.2, "d": 0.9}) == {"d": 1, "a": 2, "b": 2, "c": 4}
        assert history.competition_rank({"a": 0.1 + 0.2, "b": 0.3}) == {"a": 1, "b": 1}

    def _two_source(self, kw, cat, values):
        for off, v in values.items():
            cache.write_narrative_point("reddit", kw, _d(off), v)
            cache.write_narrative_point("coingecko-narrative", cat, _d(off), v)

    def test_comparison_and_missing_category(self, isolated_cache):
        self._two_source(AI_KW, "ai", {-1: 0.0, 0: 1.0})
        self._two_source(L2_KW, "l2s", {-1: 1.0, 0: 0.0})
        res = history.build_narrative_history(["ai", "l2s", "rwa"], today=TODAY)
        assert res.comparison_as_of == _d(0)
        by = {e.category_id: e for e in res.comparison}
        assert (by["ai"].rank, by["ai"].value) == (1, 1.0)
        assert (by["l2s"].rank, by["l2s"].value) == (2, 0.0)
        assert by["rwa"].rank is None and by["rwa"].reason == "no-composite-on-as-of"
        assert [e.category_id for e in res.comparison] == ["ai", "l2s", "rwa"]

    def test_no_data_anywhere(self, isolated_cache):
        res = history.build_narrative_history(today=TODAY)
        assert res.comparison_as_of is None
        assert {e.reason for e in res.comparison} == {"no-composite-data"}
        assert {e.reason for e in res.change} == {"no-composite-data"}

    def test_change_exact_fallback_and_missing_baseline(self, isolated_cache):
        # RankEntry.value holds the delta for change entries.
        self._two_source(AI_KW, "ai", {-7: 0.0, -3: 0.5, 0: 1.0})  # exact 7-day
        self._two_source(L2_KW, "l2s", {-9: 0.0, -2: 0.5, 0: 1.0})  # 9-day fallback
        self._two_source("RWA crypto", "rwa", {-10: 0.0, -2: 0.5, 0: 1.0})  # too old
        res = history.build_narrative_history(["ai", "l2s", "rwa"], today=TODAY)
        by = {e.category_id: e for e in res.change}
        assert by["ai"].value == pytest.approx(1.0) and by["ai"].baseline_date == _d(-7)
        assert by["l2s"].value == pytest.approx(1.0) and by["l2s"].baseline_date == _d(-9)
        assert (by["ai"].rank, by["l2s"].rank) == (1, 1)
        assert by["rwa"].value is None and by["rwa"].reason == "no-baseline-in-window"

    def test_change_mixed_scale_when_baseline_backfilled(self, isolated_cache):
        cache.write_narrative_point("pytrends", AI_KW, _d(-7), 10.0, source_status="backfilled")
        cache.write_narrative_point("pytrends", AI_KW, _d(-8), 20.0, source_status="backfilled")
        cache.write_narrative_point("pytrends", AI_KW, _d(-1), 40.0)  # nightly needs >=2 points (ADR-1)
        cache.write_narrative_point("pytrends", AI_KW, _d(0), 50.0)
        for off in (-8, -7, 0):
            cache.write_narrative_point("reddit", AI_KW, _d(off), float(off))
        res = history.build_narrative_history(["ai"], today=TODAY)
        assert res.change[0].mixed_scale is True


class TestBoundaries:
    def test_unknown_category_rejected_before_any_path_is_built(self, isolated_cache):
        with pytest.raises(history.UnknownCategoryError) as exc:
            history.build_narrative_history(["ai", "../../etc"], today=TODAY)
        assert exc.value.unknown == ["../../etc"]

    def test_utc_midnight_boundary(self, isolated_cache):
        """Writers date points by UTC; 23:59:59 and 00:00:00 are different days."""
        before = datetime(2026, 9, 23, 23, 59, 59, tzinfo=timezone.utc)
        after = datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc)
        cache.write_narrative_point("reddit", AI_KW, before.strftime("%Y-%m-%d"), 1.0)
        cache.write_narrative_point("reddit", AI_KW, after.strftime("%Y-%m-%d"), 2.0)
        res = history.build_narrative_history(["ai"], today=TODAY)
        assert list(_series(_cat(res, "ai"), "reddit").frame["date"]) == ["2026-09-23", "2026-09-24"]
        assert res.grid_dates == ["2026-09-23", "2026-09-24"]

    def test_narrative_only_coins_flagged(self, isolated_cache):
        coins = dict(_cat(history.build_narrative_history(["l2s"], today=TODAY), "l2s").coins)
        assert coins["ETH"] is False and coins["HYPE"] is False
        assert coins["ARB"] is True

    def test_trigger_and_screener_do_not_import_history(self):
        root = Path(history.__file__).resolve().parents[1]
        for rel in ("narrative/trigger.py", "screener_board.py"):
            text = (root / rel).read_text(encoding="utf-8")
            assert "narrative.history" not in text and "import history" not in text


class TestSufficiencyGating:
    """Narrative-v2 ADR-1 / AC-2: insufficient series never feed the composite."""

    def test_build_composite_never_uses_insufficient_slot(self, isolated_cache):
        # Real 25-09-26 shape: pytrends backfilled (mature), everything else 0-1 point.
        for i in range(-10, 0):
            cache.write_narrative_point("pytrends", AI_KW, _d(i), float(20 + i), source_status="backfilled")
        cache.write_narrative_point("coingecko-narrative", "ai", _d(0), 3.0)
        _exchange("ai", _d(0), 0.1)
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        assert _series(cat, "pytrends", "backfill-269d").sufficiency == "mature"
        for src in ("coingecko-narrative", "exchange_volume_share"):
            s = _series(cat, src)
            assert s.sufficiency == "insufficient"
            assert list(s.frame["normalized"]) == [None]
            assert list(s.frame["sufficiency"]) == ["insufficient"]
        # only one sufficient slot on any date -> no composite, never a 0.5 reading
        assert cat.composite.empty
        assert cat.composite_status == "unavailable"

    def test_composite_no_fake_tie_across_categories(self, isolated_cache):
        # Pre-fix: each category's 1-point sources normalised to a flat 0.5 and
        # both composites tied at exactly 0.5.
        for cid, kw in (("ai", AI_KW), ("l2s", L2_KW)):
            cache.write_narrative_point("reddit", kw, _d(0), 7.0)
            cache.write_narrative_point("coingecko-narrative", cid, _d(0), 2.0)
            _exchange(cid, _d(0), 0.3)
        result = history.build_narrative_history(["ai", "l2s"], today=TODAY)
        for cid in ("ai", "l2s"):
            assert _cat(result, cid).composite.empty
        assert all(e.rank is None and e.value is None for e in result.comparison)
        assert not any(e.value == 0.5 for e in result.comparison)

    def test_provisional_series_still_feeds_composite(self, isolated_cache):
        for i in (-1, 0):
            cache.write_narrative_point("reddit", AI_KW, _d(i), float(i + 5))
            cache.write_narrative_point("coingecko-narrative", "ai", _d(i), float(-i))
        cat = _cat(history.build_narrative_history(["ai"], today=TODAY), "ai")
        assert _series(cat, "reddit").sufficiency == "provisional"
        assert len(cat.composite) == 2
