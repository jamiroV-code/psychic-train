"""Unit tests for `snapshot_liqtide`'s pure helpers (E2, validate-contract).

Synthetic fixtures only — no network, no cache reads. These cover the two
paths the CLI gates cannot reach locally: a payload whose published score
disagrees with its own components, and a non-empty archive with gaps (the
local archive is currently empty, so `--coverage` only ever exercises the
empty branch).
"""
from __future__ import annotations

import pandas as pd

from api.scripts.snapshot_liqtide import WEIGHTS, check_arithmetic, check_coverage


def _payload(value: int, *, data_quality: str = "live", components: dict | None = None,
             weights: dict | None = None) -> dict:
    return {
        "data_quality": data_quality,
        "tide_index": {
            "value": value,
            "components": components if components is not None else {k: 0.0 for k in WEIGHTS},
            "weights": weights if weights is not None else dict(WEIGHTS),
        },
    }


def test_check_arithmetic_clean_payload_has_no_problems():
    # All components 0.0 -> score 0 -> 50 + 50*0 = 50.
    assert check_arithmetic(_payload(50)) == []


def test_check_arithmetic_flags_score_mismatch():
    problems = check_arithmetic(_payload(80))
    assert any("does not match recomputation" in p for p in problems)


def test_check_arithmetic_flags_missing_component():
    components = {k: 0.0 for k in WEIGHTS}
    missing_key = "net_liquidity_4w"
    components.pop(missing_key)
    problems = check_arithmetic(_payload(50, components=components))
    assert any(missing_key in p for p in problems)


def test_check_arithmetic_flags_weights_not_summing_to_one():
    bad_weights = dict(WEIGHTS)
    bad_weights["net_liquidity_4w"] = 0.60
    problems = check_arithmetic(_payload(50, weights=bad_weights))
    assert any("weights sum to" in p for p in problems)


def test_check_arithmetic_flags_non_live_data_quality():
    problems = check_arithmetic(_payload(50, data_quality="stale"))
    assert any("data_quality" in p for p in problems)


def test_check_arithmetic_clamps_to_0_100():
    # Every component at +10 -> raw score 10 -> 50 + 500 = 550, clamped to 100.
    problems = check_arithmetic(_payload(100, components={k: 10.0 for k in WEIGHTS}))
    assert problems == []


def _history(dates: list[str]) -> pd.DataFrame:
    return pd.DataFrame({
        "date": dates,
        "tide_score": [1.0] * len(dates),
        "net_liquidity": [1.0] * len(dates),
        "dollar": [1.0] * len(dates),
        "stables": [1.0] * len(dates),
        "btc_dom": [1.0] * len(dates),
    })


def test_check_coverage_empty_archive_is_flagged():
    problems = check_coverage(pd.DataFrame())
    assert any("empty" in p for p in problems)


def test_check_coverage_consecutive_days_are_clean():
    assert check_coverage(_history(["2026-09-01", "2026-09-02", "2026-09-03"])) == []


def test_check_coverage_reports_gap_length():
    problems = check_coverage(_history(["2026-09-01", "2026-09-02", "2026-09-10"]))
    assert any("gap(s) in daily coverage, worst 8 days" in p for p in problems)


def test_check_coverage_flags_null_values():
    history = _history(["2026-09-01", "2026-09-02"])
    history.loc[0, "tide_score"] = None
    problems = check_coverage(history)
    assert any("tide_score: 1 archived day(s) have no value" in p for p in problems)


def test_check_coverage_flags_missing_column():
    history = _history(["2026-09-01", "2026-09-02"]).drop(columns=["btc_dom"])
    problems = check_coverage(history)
    assert any("btc_dom" in p for p in problems)
