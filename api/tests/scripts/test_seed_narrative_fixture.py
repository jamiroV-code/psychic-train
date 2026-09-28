"""Unit tests for the /narrative part of `seed_e2e_cache` (narrative RFC-6).

The seeder writes through the real cache writers into `isolated_cache`; these
tests read it back through the real readers and the real `/history` builder,
and pin the hand-derived facts the Playwright spec asserts against.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from api.analytics.narrative import history, trigger
from api.data import cache
from api.scripts.seed_e2e_cache import build_narrative_fixture, seed_narrative

TODAY = pd.Timestamp("2026-09-24")


@pytest.fixture(autouse=True)
def _fixture_narratives_path(tmp_path, monkeypatch):
    """narrative-v2 RFC-7: the seeder refuses to run without a disposable
    NARRATIVES_PATH (it writes the config there, never the real file)."""
    monkeypatch.setenv("NARRATIVES_PATH", str(tmp_path / "cfg" / "narratives.json"))


def test_fixture_is_pure_and_keys_pytrends_by_primary_keyword():
    fixture = build_narrative_fixture(TODAY)
    seeds = {c["id"]: c["keywords"][0] for c in trigger.load_seed_categories()}
    assert fixture["facts"]["keywords"] == seeds
    pytrends_keys = {key for source, key, *_ in fixture["points"] if source == "pytrends"}
    assert pytrends_keys <= set(seeds.values())
    other_keys = {key for source, key, *_ in fixture["points"] if source != "pytrends"}
    assert other_keys <= set(seeds)
    assert not any(source == "reddit" for source, *_ in fixture["points"])


def test_seed_writes_what_the_manifest_says_via_the_real_readers(isolated_cache):
    facts = seed_narrative(TODAY)
    ai_kw = facts["keywords"]["ai"]
    py = cache.read_narrative_series("pytrends", ai_kw)
    assert (py["source_status"] == "backfilled").sum() == 60
    assert facts["gap"]["gap_date"] in set(py["date"])
    assert "2026-09-13" not in set(py["date"])  # inside the hole
    for cid in facts["category_ids"]:
        assert cache.read_narrative_series("reddit", facts["keywords"][cid]).empty
        ex = cache.read_exchange_series(cid)
        assert list(ex["date"].astype(str)) == [facts["day_minus_1"], facts["today"]]
        assert ex.iloc[0]["listing_reason"] == "no-baseline-yet"
    assert cache.read_exchange_market_snapshot(facts["today"]) is not None
    assert cache.read_trending_snapshot() is None  # deliberately unseeded


def test_history_over_the_seed_matches_the_hand_derived_facts(isolated_cache):
    facts = seed_narrative(TODAY)
    result = history.build_narrative_history(today=date(2026, 9, 24))
    assert result.comparison_as_of == facts["today"]
    assert [(e.category_id, e.rank) for e in result.comparison] == [
        (e["category_id"], e["rank"]) for e in facts["comparison"]
    ]
    assert result.comparison[-1].reason == facts["comparison"][-1]["reason"]
    change = {e.category_id: e for e in result.change}
    for expected in facts["change"]:
        got = change[expected["category_id"]]
        assert got.rank == expected["rank"]
        if expected["rank"] is None:
            assert got.value is None and got.reason == expected["reason"]
        else:
            assert (got.value > 0) == (expected["sign"] > 0)
    ai = next(c for c in result.categories if c.category_id == "ai")
    assert int(ai.composite["mixed_scale"].sum()) == facts["ai_mixed_scale_points"]
    nightly = next(s for s in ai.series if s.variant == "nightly-7d")
    flagged = list(nightly.frame.loc[nightly.frame["gap_before"], "date"])
    assert flagged == [facts["gap"]["gap_date"]]
    reddit = next(s for s in ai.series if s.source == "reddit")
    assert (reddit.status, reddit.reason) == ("unavailable", "no-archived-data")


def test_history_endpoint_serialises_the_seeded_cache(isolated_cache):
    """Regression (RFC-6 E2E): once an exchange series holds a day with a
    listing reason and a day without, pandas inferred a NaN-backed string
    column and `/history` returned 500 (reason=NaN failed the response model)."""
    from fastapi.testclient import TestClient

    from api.main import app

    facts = seed_narrative(pd.Timestamp.now(tz="UTC").tz_localize(None).normalize())
    response = TestClient(app).get("/api/narrative/history")
    assert response.status_code == 200
    body = response.json()
    ai = next(c for c in body["categories"] if c["category_id"] == "ai")
    listings = next(s for s in ai["series"] if s["source"] == "exchange_new_listings")
    assert [p["reason"] for p in listings["points"]] == ["no-baseline-yet", None]
    assert [e["rank"] for e in body["comparison"]["entries"]] == [e["rank"] for e in facts["comparison"]]
