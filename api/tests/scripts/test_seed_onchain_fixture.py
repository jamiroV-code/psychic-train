"""Unit tests for the /onchain part of `seed_e2e_cache` (chain-growth RFC-6).

The seeder writes through `cache.merge_onchain_series` into `isolated_cache`;
these tests read it back through the real reader and the real response
builder, and pin the manifest facts the Playwright spec asserts against.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.analytics.onchain.response import build_growth_response, is_stale
from api.data import cache
from api.main import app
from api.scripts.seed_e2e_cache import ONCHAIN_SEED_TODAY, build_onchain_fixture, seed_onchain

NOW = pd.Timestamp("2026-09-27T12:00:00Z")


def _now() -> datetime:
    return NOW.to_pydatetime()


def test_fixture_is_pure_bounded_and_skips_config_unavailable_chains():
    fixture = build_onchain_fixture()
    facts = fixture["facts"]
    assert {src for src, *_ in fixture["rows"]} == {"growthepie", "l2beat"}
    assert all(d <= ONCHAIN_SEED_TODAY for *_, pts, _ in fixture["rows"] for d, _ in pts)
    seeded = {cid for _, cid, *_ in fixture["rows"]}
    assert seeded == set(facts["live_ids"])
    assert set(facts["unavailable_ids"]) == {"solana", "bnb", "tron"}
    assert not seeded & set(facts["unavailable_ids"])
    # D2: every live chain has pre-launch points; D3: polygon has no tx archive.
    assert all(c["pre_launch_points"] > 0 for c in facts["chains"].values())
    assert not any(cid == "polygon" and m == "transactions" for _, cid, m, *_ in fixture["rows"])


def test_seed_round_trips_through_the_real_reader(isolated_cache):
    facts = seed_onchain(now=NOW)
    for cid, c in facts["chains"].items():
        df = cache.read_onchain_series("growthepie", cid, "active_addresses")
        assert len(df) == c["points"]
        assert df["date"].iloc[0] == c["first_date"]
        assert df["date"].iloc[-1] == ONCHAIN_SEED_TODAY
        assert (df["date"] < c["launch_date"]).sum() == c["pre_launch_points"]
        tx = cache.read_onchain_series("growthepie", cid, "transactions")
        assert tx.empty is (not c["has_transactions"])
    base_dates = set(cache.read_onchain_series("growthepie", "base", "active_addresses")["date"])
    assert "2026-05-12" not in base_dates and facts["gap"]["gap_before_date"] in base_dates
    stale_df = cache.read_onchain_series("growthepie", facts["stale"]["chain"], "active_addresses")
    assert is_stale(stale_df["as_of_utc"].max(), _now())
    fresh_df = cache.read_onchain_series("growthepie", "ethereum", "active_addresses")
    assert not is_stale(fresh_df["as_of_utc"].max(), _now())
    for cid in facts["cross_check"]["chains"]:
        assert not cache.read_onchain_series("l2beat", cid, "transactions").empty


@pytest.mark.parametrize("metric", ["active_addresses", "transactions"])
def test_growth_response_over_the_seed_matches_the_manifest(isolated_cache, metric):
    facts = seed_onchain(now=NOW)
    r = build_growth_response(metric, now=_now())
    by_id = {c.id: c for c in r.chains}
    assert r.comparison.start_date == facts["default_start"]
    assert r.grid_dates[-1] == ONCHAIN_SEED_TODAY
    assert r.attribution == facts["attribution"]
    for cid in facts["unavailable_ids"]:
        assert by_id[cid].status == "unavailable" and by_id[cid].series is None

    polygon = by_id[facts["no_tx_archive"]["chain"]]
    if metric == "transactions":
        assert polygon.status == "unavailable"
        assert polygon.unavailable_reason == facts["no_tx_archive"]["reason"]
    else:
        assert polygon.status == "ok"

    for cid, c in facts["chains"].items():
        if metric == "transactions" and not c["has_transactions"]:
            continue
        item = by_id[cid]
        assert item.floor_ramp.state == c["state"], cid
        assert item.status == ("stale" if cid == facts["stale"]["chain"] else "ok"), cid
        assert sum(p.pre_launch for p in item.series.points) == c["pre_launch_points"]
        expected_events = facts["designed"]["events"] if cid == facts["designed"]["chain"] else []
        assert [e.model_dump() for e in item.floor_ramp.events] == expected_events, cid

    arb = by_id["arbitrum"].floor_ramp.events
    assert (arb[0].floor_date, arb[0].ramp_date) == ("2026-03-01", "2026-04-14")

    rh = by_id[facts["limited"]["chain"]]
    assert rh.limited_history is True
    assert rh.floor_ramp.gate_met_on == facts["limited"]["gate_met_on"] == "2027-01-10"
    assert rh.floor_ramp.history_days == facts["limited"]["history_days"]
    late = [s for s in r.comparison.series if s.rebased_late]
    assert [(s.chain_id, s.rebase_date) for s in late] == [("robinhood", facts["limited"]["rebase_date"])]

    gap_point = next(p for p in by_id["base"].series.points if p.date == facts["gap"]["gap_before_date"])
    assert gap_point.gap_before is True
    assert sum(p.gap_before for p in by_id["base"].series.points) == 1

    for cid in facts["cross_check"]["chains"]:
        cc = by_id[cid].cross_check
        if metric == "transactions":
            assert cc.latest_divergence_pct == pytest.approx(facts["cross_check"]["divergence_pct"], abs=1e-3)
        else:
            assert cc is None


def test_router_echoes_the_two_year_start(isolated_cache):
    facts = seed_onchain(now=pd.Timestamp.now(tz="UTC"))
    with TestClient(app) as client:
        body = client.get("/api/onchain/growth", params={"start": facts["start_2y"]}).json()
    assert body["comparison"]["start_date"] == facts["start_2y"]
    assert datetime.now(timezone.utc).date().isoformat() >= ONCHAIN_SEED_TODAY
