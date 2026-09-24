"""Unit tests for the /regime part of `seed_e2e_cache` (RFC-006).

Pure: `build_regime_fixture` writes nothing, so no cache root is needed.
These pin the fixture properties the Playwright spec depends on.
"""
from __future__ import annotations

import pandas as pd

from api.analytics.regime.components import ETF_LAUNCH_DATE, SPEC_BY_ID, gap_before_flags
from api.scripts.seed_e2e_cache import GAP_COMPONENT, build_regime_fixture

TODAY = pd.Timestamp("2026-09-24")


def test_history_spans_more_than_three_years_with_distinct_first_dates():
    facts = build_regime_fixture(TODAY)["facts"]
    firsts = facts["input_first_dates"]
    assert min(firsts.values()) < "2023-09-24"
    fred_firsts = [firsts[k] for k in ("WALCL", "WDTGAL", "RRPONTSYD", "DTWEXBGS")]
    assert len(set(fred_firsts)) == 4


def test_fred_dates_are_utc_aware_like_the_adapter():
    fixture = build_regime_fixture(TODAY)
    for df in fixture["fred"].values():
        assert str(df["date"].dt.tz) == "UTC"
    assert str(fixture["stablecoin"]["date"].dt.tz) == "UTC"


def test_exactly_one_deliberate_hole_exceeds_the_dollar_max_gap():
    fixture = build_regime_fixture(TODAY)
    gap = fixture["facts"]["gap"]
    dates = fixture["fred"][gap["series"]]["date"].dt.tz_localize(None)
    flags = gap_before_flags(dates, SPEC_BY_ID[GAP_COMPONENT].max_gap_days)
    flagged = [d.strftime("%Y-%m-%d") for d, f in zip(dates, flags) if f]
    assert flagged == [gap["expected_gap_date"]]
    inside = dates[(dates >= gap["hole_start"]) & (dates < gap["hole_end_exclusive"])]
    assert inside.empty


def test_etf_flows_start_on_or_after_launch():
    fixture = build_regime_fixture(TODAY)
    assert fixture["etf"]["date"].min() >= ETF_LAUNCH_DATE
    assert fixture["facts"]["etf_first_date"] == "2024-01-11"


def test_liqtide_archive_days_are_consecutive_and_end_today():
    raws = build_regime_fixture(TODAY)["liqtide_raw"]
    dates = [d for d, _ in raws]
    assert dates[-1] == "2026-09-24"
    assert len(dates) == len(set(dates)) >= 2
    for _, raw in raws:
        assert raw["tide_series"] and raw["metrics"]["btc_dom"]["series"]
