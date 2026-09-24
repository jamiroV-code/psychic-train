"""Regime dashboard RFC-001: raw LiqTide payload archive (AC-1).

Every test uses `isolated_cache` — `api/data/cache/liqtide/` is the live,
git-tracked archive and must never receive fixture data.
"""
from __future__ import annotations

import json

import httpx
import pandas as pd

from api.data import cache, liqtide_adapter


def _payload(generated_utc: str = "2026-09-24T00:25:12Z", value: float = 52, score: float = 0.0427) -> dict:
    return {
        "generated_utc": generated_utc,
        "data_quality": "live",
        "tide_index": {
            "value": value,
            "label": "SLACK WATER",
            "score": score,
            "components": {"net_liquidity_4w": -0.3772, "stablecoin_7d": 0.4669},
            "weights": {"net_liquidity_4w": 0.3, "stablecoin_7d": 0.25},
        },
        "tide_series": [["2024-09-04", 50], ["2026-09-16", 32]],
        "metrics": {
            "net_liquidity": {"value": 5.749465e12, "as_of": "2026-09-16", "series": [["2024-09-04", 6.0e12]]},
            "dollar": {"value": 119.5133, "as_of": "2026-09-18", "series": []},
            "stables": {"value": 3.13e11, "as_of": "2026-09-22", "series": []},
            "btc_dom": {"value": 58.7, "as_of": "2026-09-23", "series": [["2025-06-10", 54.9]]},
        },
        "signals": {"etf_flow5": 1.66e9},
    }


def _client(body: object, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


class TestRawArchiveHelpers:
    def test_write_once_then_noop(self, isolated_cache):
        assert cache.write_liqtide_raw("2026-09-24", {"a": 1}) is True
        assert cache.write_liqtide_raw("2026-09-24", {"a": 2}) is False
        assert cache.read_liqtide_raw("2026-09-24") == {"a": 1}

    def test_missing_date_reads_none(self, isolated_cache):
        assert cache.read_liqtide_raw("2020-01-01") is None
        assert cache.list_liqtide_raw_dates() == []

    def test_list_dates_sorted(self, isolated_cache):
        for d in ("2026-09-24", "2026-09-22", "2026-09-23"):
            cache.write_liqtide_raw(d, {})
        assert cache.list_liqtide_raw_dates() == ["2026-09-22", "2026-09-23", "2026-09-24"]

    def test_raw_and_backfill_live_in_subfolders(self, isolated_cache):
        assert cache.liqtide_raw_path("2026-09-24").parent == isolated_cache / "liqtide" / "raw"
        assert cache.liqtide_backfill_path("2026-09-24").parent == isolated_cache / "liqtide" / "backfill"


class TestFetchLatestArchivesRaw:
    def test_fresh_fetch_writes_raw_verbatim(self, isolated_cache):
        body = _payload()
        payload = liqtide_adapter.fetch_latest(client=_client(body))
        assert payload.status == "ok"
        stored = json.loads(cache.liqtide_raw_path("2026-09-24").read_text(encoding="utf-8"))
        assert stored == body

    def test_second_fetch_same_day_does_not_overwrite(self, isolated_cache):
        liqtide_adapter.fetch_latest(client=_client(_payload(value=52)))
        liqtide_adapter.fetch_latest(client=_client(_payload(value=99)))
        assert cache.read_liqtide_raw("2026-09-24")["tide_index"]["value"] == 52

    def test_dry_run_writes_nothing(self, isolated_cache):
        payload = liqtide_adapter.fetch_latest(client=_client(_payload()), dry_run=True)
        assert payload.status == "ok"
        assert cache.list_liqtide_raw_dates() == []
        assert not cache.liqtide_payload_path("2026-09-24").exists()

    def test_malformed_payload_writes_nothing(self, isolated_cache):
        payload = liqtide_adapter.fetch_latest(client=_client("not json"))
        assert payload.status == "unavailable"
        assert cache.list_liqtide_raw_dates() == []

    def test_http_error_writes_nothing(self, isolated_cache):
        payload = liqtide_adapter.fetch_latest(client=_client({}, status=500))
        assert payload.status == "unavailable"
        assert cache.list_liqtide_raw_dates() == []


class TestTideValueColumns:
    def test_parse_carries_value_and_label_separately_from_score(self, isolated_cache):
        payload = liqtide_adapter.fetch_latest(client=_client(_payload()), dry_run=True)
        assert payload.tide_score == 0.0427
        assert payload.tide_value == 52.0
        assert payload.tide_label == "SLACK WATER"

    def test_archive_row_has_new_columns_last(self, isolated_cache):
        liqtide_adapter.fetch_latest(client=_client(_payload()))
        row = pd.read_parquet(cache.liqtide_payload_path("2026-09-24"))
        assert list(row.columns)[-2:] == ["tide_value", "tide_label"]
        assert row.loc[0, "tide_value"] == 52.0

    def test_history_reads_old_and_new_schema_together(self, isolated_cache):
        # A row archived before 24-09-26 (no tide_value/tide_label columns).
        old = pd.DataFrame([{
            "date": "2026-09-20", "generated_utc": "2026-09-20T00:25:12Z", "tide_score": -0.0701,
            "net_liquidity": 5.7e12, "dollar": 118.2, "stables": 3.1e11, "btc_dom": 58.86,
        }])
        cache.write_liqtide_payload("2026-09-20", old)
        liqtide_adapter.fetch_latest(client=_client(_payload()))

        history = cache.read_liqtide_history()
        assert list(history["date"]) == ["2026-09-20", "2026-09-24"]
        assert pd.isna(history.loc[0, "tide_value"])  # absent, never fabricated
        assert history.loc[1, "tide_value"] == 52.0

    def test_cache_fallback_on_old_row_leaves_value_none(self, isolated_cache):
        old = pd.DataFrame([{
            "date": "2026-09-20", "generated_utc": "2026-09-20T00:25:12Z", "tide_score": -0.0701,
            "net_liquidity": 5.7e12, "dollar": 118.2, "stables": 3.1e11, "btc_dom": 58.86,
        }])
        cache.write_liqtide_payload("2026-09-20", old)
        payload = liqtide_adapter.fetch_latest(client=_client({}, status=500))
        assert payload.status in ("ok", "stale")
        assert payload.tide_score == -0.0701
        assert payload.tide_value is None
        assert payload.tide_label is None
