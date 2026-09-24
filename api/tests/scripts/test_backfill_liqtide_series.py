"""Regime dashboard RFC-001: history backfill from a raw LiqTide payload (AC-2)."""
from __future__ import annotations

import pandas as pd

from api.data import cache
from api.scripts.backfill_liqtide_series import (
    BACKFILL_COLUMNS,
    TIDE_SERIES_KEY,
    backfill,
    extract_series,
)


def _raw() -> dict:
    return {
        "tide_series": [["2024-09-04", 50], ["2024-09-11", 48], ["2026-09-16", 32]],
        "metrics": {
            "btc_dom": {"value": 58.7, "series": [["2025-06-10", 54.9], ["2026-09-23", 58.7]]},
            "rrp": {"value": 4.53e8, "series": [["2024-09-03", 3.498e11]]},
            "fng": {"value": 71},  # no series key at all
        },
    }


class TestExtractSeries:
    def test_expected_rows(self):
        df = extract_series(_raw())
        assert list(df.columns) == BACKFILL_COLUMNS
        tide = df[df["series_key"] == TIDE_SERIES_KEY]
        assert list(tide["date"]) == ["2024-09-04", "2024-09-11", "2026-09-16"]
        assert list(tide["value"]) == [50.0, 48.0, 32.0]
        assert set(df["series_key"]) == {TIDE_SERIES_KEY, "btc_dom", "rrp"}
        assert df.loc[df["series_key"] == "rrp", "value"].iloc[0] == 3.498e11

    def test_missing_series_skipped_not_zero(self):
        df = extract_series(_raw())
        assert "fng" not in set(df["series_key"])
        assert (df["value"] != 0).all()

    def test_malformed_points_dropped(self):
        raw = {"tide_series": [["2024-09-04", None], ["2024-09-11", "48"], ["bad"], 5, ["2024-09-18", True], ["2024-09-25", 47]]}
        df = extract_series(raw)
        assert list(df["date"]) == ["2024-09-25"]

    def test_empty_payload(self):
        assert extract_series({}).empty
        assert extract_series({"metrics": "nope", "tide_series": "nope"}).empty

    def test_datetime_strings_trimmed_to_date(self):
        df = extract_series({"tide_series": [["2024-09-04T00:00:00Z", 50]]})
        assert df.loc[0, "date"] == "2024-09-04"


class TestBackfill:
    def test_newest_raw_written_and_idempotent(self, isolated_cache):
        cache.write_liqtide_raw("2026-09-23", {"tide_series": [["2024-09-04", 1]]})
        cache.write_liqtide_raw("2026-09-24", _raw())

        date, df = backfill()
        assert date == "2026-09-24"
        stored = pd.read_parquet(cache.liqtide_backfill_path("2026-09-24"))
        pd.testing.assert_frame_equal(stored, df)

        backfill()  # re-run: same content
        pd.testing.assert_frame_equal(pd.read_parquet(cache.liqtide_backfill_path("2026-09-24")), df)

    def test_no_raw_returns_none(self, isolated_cache):
        assert backfill() is None

    def test_backfill_not_read_as_a_daily_payload(self, isolated_cache):
        cache.write_liqtide_raw("2026-09-24", _raw())
        backfill()
        # read_liqtide_history globs liqtide/*.parquet; the backfill lives in a
        # subfolder and must not appear as an archived day.
        assert cache.read_liqtide_history().empty
