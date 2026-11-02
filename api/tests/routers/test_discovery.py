"""S-F1: GET /api/narrative/discovery through the real app, store only."""
from __future__ import annotations

import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routers import discovery as router_mod
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import gain, world

URL = "/api/narrative/discovery"


@pytest.fixture
def wired(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setattr(router_mod, "utc_today", lambda: TODAY)
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]})
    gain("A"), gain("B", factor=3.0)

    def boom(*a, **k):
        raise AssertionError("handler must not reach the network")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    return TestClient(app)


def test_ok_payload_shape(wired):
    r = wired.get(URL, params={"window": 30})
    assert r.status_code == 200
    body = r.json()
    assert body["window"] == 30 and body["status"] == "ok" and body["reason"] == ""
    assert set(body) == {"window", "as_of", "categories_as_of", "status", "reason",
                         "universe_size", "eligible_size", "shown_size", "excluded", "excluded_coins",
                         "excluded_counts", "min_category_coins",
                         "rising_threshold_pct", "min_covered_weight", "categories",
                         "narratives_status", "unassigned", "hidden_narratives", "weights_version",
                         "tradeability_unknown", "venue_lists", "tradeability_data_suspect"}
    assert set(body["excluded"]) == {"exclusion_list", "below_volume_floor", "no_category", "no_source_data"}
    c = body["categories"][0]
    assert set(c) == {"id", "name", "score", "median", "coins_used", "gaining_count", "ranked", "coins"}
    assert set(c["coins"][0]) == {"symbol", "change", "raw_change", "covered_weight", "rising_weight",
                                  "trigger", "sources", "primary", "volume_24h", "thin_volume", "tradeability"}
    assert set(c["coins"][0]["sources"][0]) == {"source", "change", "as_of", "members", "coverage_only"}
    assert [x["symbol"] for x in c["coins"]] == ["B", "A"]


def test_default_window_is_30(wired):
    assert wired.get(URL).json()["window"] == 30


@pytest.mark.parametrize("w", [7, 30, 90])
def test_enum_accepts(wired, w):
    assert wired.get(URL, params={"window": w}).status_code == 200


@pytest.mark.parametrize("w", ["14", "0", "-7", "abc", "30.5"])
def test_enum_rejects_with_422(wired, w):
    assert wired.get(URL, params={"window": w}).status_code == 422


def test_no_categories_snapshot_is_not_an_error_over_http(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setattr(router_mod, "utc_today", lambda: TODAY)
    world(tmp_path, monkeypatch, {"A": 5e7}, cats=None)
    body = TestClient(app).get(URL).json()
    assert body["reason"] != "categories-missing"


def test_sources_route_shape_and_no_network(wired):
    r = wired.get("/api/narrative/sources")
    assert r.status_code == 200
    b = r.json()
    assert set(b) == {"as_of", "universe_size", "eligible_size", "live_sources", "total_sources", "live_weight",
                      "newest", "sources", "trends_keyword", "trends_watch", "collector"}
    assert set(b["trends_keyword"]) == {"eligible_size", "with_keyword", "missing"}
    assert set(b["collector"]) == {"state", "reason", "started_at", "last_beat", "age_s", "mode", "version",
                                   "running_sources", "sources"}
    assert (b["collector"]["state"], b["collector"]["reason"]) == ("never_started", "no_heartbeat")
    assert [s["id"] for s in b["collector"]["sources"]] == ["xsearch", "reddit"]
    assert set(b["collector"]["sources"][0]) == {"id", "label", "has_state", "last_unit_at", "paused",
                                                 "pause_reason", "pause_until", "stale", "budget_used",
                                                 "effective_budget"}
    assert set(b["sources"][0]) == {"id", "label", "kind", "weight", "state", "newest", "history_days",
                                    "coins_with_data", "eligible_size", "note", "reason", "impl"}
    assert b["total_sources"] == 7 and b["eligible_size"] == 2


def test_router_discovery_new_fields_present(wired):
    body = wired.get(URL, params={"window": 30}).json()
    assert (body["narratives_status"], body["categories_as_of"]) == ("proposed", "2026-10-14")
    assert (body["unassigned"], body["min_category_coins"]) == ([], 1)
    assert body["hidden_narratives"] == [{"id": "defi", "name": "DeFi", "coins": []}]
    assert [c["primary"] for c in body["categories"][0]["coins"]] == [True, True]


# Fields and reason keys served before T189: they keep their names and their values (additive change only).
OLD_TOP = {"window", "as_of", "categories_as_of", "status", "reason", "universe_size", "eligible_size", "shown_size",
           "excluded", "excluded_coins", "excluded_counts", "min_category_coins", "rising_threshold_pct",
           "min_covered_weight", "categories", "narratives_status", "unassigned", "hidden_narratives",
           "weights_version"}
OLD_REASONS = {"stablecoin", "wrapped-staked", "no-market", "not-tradeable-config", "unassigned", "hidden-narrative",
               "no-source-data"}


def test_payload_is_backward_compatible_with_a_not_tradeable_coin(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setattr(router_mod, "utc_today", lambda: TODAY)
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7, "JAAA": 0}, cats={"ai": ["A", "B", "JAAA"]})
    gain("A"), gain("B", factor=3.0), gain("JAAA")
    body = TestClient(app).get(URL, params={"window": 30}).json()
    assert OLD_TOP <= set(body) and set(body) - OLD_TOP == {"tradeability_unknown", "venue_lists",
                                                             "tradeability_data_suspect"}
    new = {"not-tradeable", "commodity-backed", "watching", "inactive", "unclassified"}
    assert set(body["excluded_counts"]) == OLD_REASONS | new
    assert all(body["excluded_counts"][k] == 0 for k in OLD_REASONS | new - {"not-tradeable"})
    assert body["excluded_counts"]["not-tradeable"] == 1
    assert body["excluded_coins"] == [{"symbol": "JAAA", "reason": "not-tradeable", "detail": "zero 24h volume"}]
    assert body["excluded"] == {"exclusion_list": 1, "below_volume_floor": 0, "no_category": 0, "no_source_data": 0}
    assert (body["universe_size"], body["eligible_size"], body["shown_size"]) == (3, 2, 2)
    assert [c["tradeability"] for c in body["categories"][0]["coins"]] == ["unverified", "unverified"]
    assert body["tradeability_unknown"] == 2 and body["tradeability_data_suspect"] is False
    assert body["venue_lists"] == [{"venue": "binance", "status": "missing", "as_of": None},
                                   {"venue": "hyperliquid", "status": "missing", "as_of": None}]


def test_no_data_payload_carries_the_new_fields_with_defaults(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setattr(router_mod, "utc_today", lambda: TODAY)
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    body = TestClient(app).get(URL, params={"window": 30}).json()
    assert body["status"] == "no-data" and body["tradeability_unknown"] == 0


def test_onboarding_route_reads_fixture_without_network(isolated_cache, monkeypatch):
    from api.data.attention import coin_ledger, onboarding_store
    import ipaddress
    real_connect = socket.socket.connect
    def boom(*args, **kwargs):
        raise AssertionError("onboarding route must not reach the network")
    def local_only(sock, address, *args, **kwargs):
        if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
            return real_connect(sock, address, *args, **kwargs)
        return boom()
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", boom)
    monkeypatch.setattr(socket.socket, "connect", local_only)
    ledger = coin_ledger.empty()
    ledger["coins"]["new"] = coin_ledger._entry({"symbol": "ZZNEW"}, "2026-11-01", state="watching", count=4)
    onboarding_store.write_ledger(ledger)
    before = onboarding_store.ledger_path().read_bytes()
    response = TestClient(app).get("/api/narrative/onboarding")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "shadow" and payload["status"] == "ok"
    assert payload["coins"][0]["days_in_top100"] == 4
    assert payload["coins"][0]["class"] == "unknown"
    assert onboarding_store.ledger_path().read_bytes() == before
