"""Regime dashboard RFC-003: Farside spot-BTC ETF flows adapter (AC-6).

Fixture HTML only; no network except the opt-in `integration` test
(`uv run --project api pytest api/ -m integration -k etf`). Every test that
touches the cache uses `isolated_cache` so nothing reaches the live tree.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd
import pytest

from api.data import etf_flows_adapter as etf

FIXTURE = (Path(__file__).parent / "fixtures" / "farside_btc_etf_flows.html").read_text(encoding="utf-8")


def _flows(df: pd.DataFrame) -> dict[str, float]:
    return {d.strftime("%Y-%m-%d"): v for d, v in zip(df["date"], df["net_flow_usd_m"])}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    monkeypatch.setattr(etf.time, "sleep", lambda s: None)


class TestParse:
    def setup_method(self):
        self.df = etf.parse_flows_html(FIXTURE)
        self.flows = _flows(self.df)

    def test_fixture_parse_total_column(self):
        assert list(self.df.columns) == ["date", "net_flow_usd_m"]
        assert self.flows["2024-01-11"] == pytest.approx(655.3)
        assert self.flows["2024-01-12"] == pytest.approx(203.9)
        assert self.df["date"].is_monotonic_increasing

    def test_parentheses_are_negative(self):
        assert self.flows["2024-01-16"] == pytest.approx(-94.0)

    def test_commas_stripped_including_daily_cells(self):
        assert self.flows["2024-01-17"] == pytest.approx(-1234.5)
        assert self.flows["2024-01-24"] == pytest.approx(1500.0)

    def test_dash_is_missing_not_zero(self):
        assert "2024-01-18" not in self.flows

    def test_real_zero_kept(self):
        assert self.flows["2024-01-19"] == 0.0

    def test_unreported_today_row_dropped(self):
        # All fund cells `-`, Total `0.0` before the close: not a zero-flow day.
        assert "2026-09-24" not in self.flows

    def test_malformed_and_non_date_rows_skipped(self):
        assert "2024-01-22" not in self.flows  # too few cells
        assert "2024-01-23" not in self.flows  # unparseable total
        assert set(self.flows) == {"2024-01-11", "2024-01-12", "2024-01-16", "2024-01-17",
                                   "2024-01-19", "2024-01-24"}

    def test_parse_value_rules(self):
        assert etf.parse_value("(27,841)") == -27841.0
        assert etf.parse_value("-") is None
        assert etf.parse_value("") is None
        assert etf.parse_value("nan") is None
        assert etf.parse_value("-12.5") == -12.5

    def test_no_table_gives_empty_frame(self):
        assert etf.parse_flows_html("<html><table class='nav'><tr><td>x</td></tr></table></html>").empty
        assert etf.parse_flows_html("").empty


class TestFetch:
    def test_ok_writes_cache_and_is_not_redistributable(self, isolated_cache):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, text=FIXTURE)

        result = etf.fetch_btc_spot_flows(client=_client(handler))
        assert result.status == "ok"
        assert result.redistributable is False
        assert len(calls) == 1
        assert "Mozilla" in calls[0].headers["user-agent"]
        assert etf.cache_path() == isolated_cache / "etf_flows" / "btc_spot.parquet"
        cached = etf.read_cached()
        assert _flows(cached) == _flows(result.df)
        assert cached["date"].min() == pd.Timestamp("2024-01-11")

    def test_at_most_one_request_per_day(self, isolated_cache):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, text=FIXTURE)

        client = _client(handler)
        etf.fetch_btc_spot_flows(client=client)
        second = etf.fetch_btc_spot_flows(client=client)
        assert len(calls) == 1
        assert second.status == "ok" and not second.df.empty

    def test_timeout_unavailable_when_nothing_cached(self, isolated_cache):
        def handler(request):
            raise httpx.ReadTimeout("timed out", request=request)

        result = etf.fetch_btc_spot_flows(client=_client(handler))
        assert result.status == "unavailable"
        assert "timed out" in result.reason
        assert result.df.empty
        assert result.redistributable is False

    def test_timeout_falls_back_to_cache_as_stale(self, isolated_cache):
        etf.fetch_btc_spot_flows(client=_client(lambda r: httpx.Response(200, text=FIXTURE)))

        def handler(request):
            raise httpx.ConnectTimeout("timed out", request=request)

        result = etf.fetch_btc_spot_flows(client=_client(handler), force=True)
        assert result.status == "stale"
        assert "timed out" in result.reason
        assert result.df["date"].min() == pd.Timestamp("2024-01-11")
        # A later call the same day does not retry and still reports stale.
        again = etf.fetch_btc_spot_flows(client=_client(lambda r: pytest.fail("refetched")))
        assert again.status == "stale"

    def test_challenge_page_is_unavailable_without_retry(self, isolated_cache):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(403, text="<title>Just a moment...</title>")

        result = etf.fetch_btc_spot_flows(client=_client(handler))
        assert result.status == "unavailable"
        assert "blocked" in result.reason
        assert len(calls) == 1

    def test_layout_change_is_unavailable(self, isolated_cache):
        result = etf.fetch_btc_spot_flows(client=_client(lambda r: httpx.Response(200, text="<html></html>")))
        assert result.status == "unavailable"
        assert "no flow rows" in result.reason

    def test_merge_dedupes_on_date_newest_wins(self, isolated_cache):
        etf.merge_into_cache(pd.DataFrame({"date": [pd.Timestamp("2024-01-10"), pd.Timestamp("2024-01-11")],
                                           "net_flow_usd_m": [1.0, 2.0]}))
        merged = etf.merge_into_cache(etf.parse_flows_html(FIXTURE))
        flows = _flows(merged)
        assert flows["2024-01-10"] == 1.0  # older cached row kept
        assert flows["2024-01-11"] == pytest.approx(655.3)  # newest fetch wins
        assert merged["date"].is_unique


@pytest.mark.integration
def test_etf_live_farside_single_request(isolated_cache):
    """Opt-in: one real GET to Farside. Proves only that it worked today."""
    result = etf.fetch_btc_spot_flows(force=True)
    assert result.redistributable is False
    if result.status != "ok":
        pytest.fail(f"Farside {result.status}: {result.reason}")
    assert result.df["date"].min() == pd.Timestamp("2024-01-11")
    assert len(result.df) > 600
