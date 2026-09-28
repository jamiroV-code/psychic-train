"""Narrative-v2 RFC-5 (ADR-5): daily mindshare, blend + show each (AC-11)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from api.analytics.narrative import mindshare, narrative_config
from api.data import cache
from api.tests.analytics.narrative.test_narrative_config import narrative_fixture

TODAY = date(2026, 9, 20)
D = TODAY.isoformat()


def _write_days(source, key, values, end=TODAY):
    for i, v in enumerate(values):
        if v is not None:
            cache.write_narrative_point(source, key, (end - timedelta(days=len(values) - 1 - i)).isoformat(), float(v))


@pytest.fixture
def three(monkeypatch):
    seeds = [{"id": c, "label": c.upper(), "keywords": [f"{c} crypto", f"{c} alt"]} for c in ("a", "b", "c")]
    monkeypatch.setattr(narrative_config, "load_narratives", lambda *a, **k: seeds)


# --- pure maths ----------------------------------------------------------


def test_source_shares_absent_when_no_values_or_zero_total():
    assert mindshare.source_shares({"a": None}) is None
    assert mindshare.source_shares({"a": 0.0, "b": 0.0}) is None
    assert mindshare.source_shares({"a": 1.0, "b": 3.0, "c": None}) == {"a": 0.25, "b": 0.75}


def test_mindshare_golden_shares_sum_to_one():
    # Mixed availability: pytrends a/b only, coingecko a/b/c, reddit absent.
    present, head, by = mindshare.blend_day(["a", "b", "c", "d"], {
        "pytrends": {"a": 0.6, "b": 0.2, "c": None, "d": None},
        "coingecko": {"a": 2, "b": 1, "c": 1, "d": None},
        "reddit": {"a": None, "b": None, "c": None, "d": None},
    })
    assert present == ["pytrends", "coingecko"]
    assert by["a"] == {"pytrends": pytest.approx(0.75), "coingecko": pytest.approx(0.5), "reddit": None}
    # raw means: a=(.75+.5)/2=.625, b=(.25+.25)/2=.25, c=.25 -> total 1.125
    assert head["a"] == pytest.approx(0.625 / 1.125)
    assert head["b"] == pytest.approx(0.25 / 1.125)
    assert head["c"] == pytest.approx(0.25 / 1.125)
    assert head["d"] is None  # excluded explicitly, not zero
    assert sum(v for v in head.values() if v is not None) == pytest.approx(1.0)


def test_uniform_coverage_is_plain_mean():
    _, head, _ = mindshare.blend_day(["a", "b"], {"pytrends": {"a": 1, "b": 1}, "coingecko": {"a": 3, "b": 1}})
    assert head == {"a": pytest.approx(0.625), "b": pytest.approx(0.375)}


# --- through the cache boundary -------------------------------------------


def test_mindshare_only_one_source_labelled(isolated_cache, three):
    _write_days("coingecko-narrative", "a", [3])
    _write_days("coingecko-narrative", "b", [1])
    r = mindshare.build_mindshare(TODAY, today=TODAY)
    assert r.date == D and r.sources_present == ["coingecko"]
    assert r.only_one_source and not r.no_sources_available and r.n_sources == 1
    by = {e.category_id: e for e in r.entries}
    assert by["a"].mindshare == pytest.approx(0.75)
    assert by["c"].status == "excluded" and by["c"].mindshare is None and by["c"].reason


def test_mindshare_no_sources_available_labelled(isolated_cache, three):
    r = mindshare.build_mindshare(TODAY, today=TODAY)
    assert r.no_sources_available and not r.only_one_source and r.n_sources == 0
    assert r.available_dates == [] and all(e.status == "excluded" for e in r.entries)
    assert mindshare.build_mindshare(today=TODAY).date is None


def test_reddit_absent_without_rows_and_default_is_latest_day(isolated_cache, three):
    _write_days("pytrends-blended", "a", [1, 2, 3, 4, 5])
    _write_days("pytrends-blended", "b", [5, 4, 3, 2, 1])
    _write_days("coingecko-narrative", "a", [1, 1, 1, 1, 1])
    _write_days("coingecko-narrative", "b", [1, 1, 1, 1, 3])
    r = mindshare.build_mindshare(today=TODAY)
    assert r.date == D and len(r.available_dates) == 5
    assert r.sources_present == ["pytrends", "coingecko"] and not r.only_one_source
    by = {e.category_id: e for e in r.entries}
    assert by["a"].sources["reddit"] is None
    # a: pytrends normalised 1.0 vs b 0.0 -> share 1/0; cg .25/.75
    assert by["a"].sources == {"pytrends": 1.0, "coingecko": 0.25, "reddit": None}
    assert by["a"].mindshare == pytest.approx(0.625)
    assert sum(e.mindshare for e in r.entries if e.mindshare is not None) == pytest.approx(1.0)


def test_mindshare_correct_at_15_narratives(isolated_cache, monkeypatch):
    seeds = narrative_fixture(15)["narratives"]
    monkeypatch.setattr(narrative_config, "load_narratives", lambda *a, **k: seeds)
    for k in range(15):
        _write_days("coingecko-narrative", f"n{k}", [k + 1])
    r = mindshare.build_mindshare(TODAY, today=TODAY)
    assert len(r.entries) == 15 and all(e.status == "ok" for e in r.entries)
    total = sum(range(1, 16))
    by = {e.category_id: e.mindshare for e in r.entries}
    for k in range(15):
        assert by[f"n{k}"] == pytest.approx((k + 1) / total)
    assert sum(by.values()) == pytest.approx(1.0)
