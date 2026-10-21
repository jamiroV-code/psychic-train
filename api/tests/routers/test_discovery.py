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
                         "narratives_status", "unassigned", "hidden_narratives", "weights_version"}
    assert set(body["excluded"]) == {"exclusion_list", "below_volume_floor", "no_category", "no_source_data"}
    c = body["categories"][0]
    assert set(c) == {"id", "name", "score", "median", "coins_used", "gaining_count", "ranked", "coins"}
    assert set(c["coins"][0]) == {"symbol", "change", "raw_change", "covered_weight", "rising_weight",
                                  "trigger", "sources", "primary", "volume_24h", "thin_volume", "tradeability"}
    assert set(c["coins"][0]["sources"][0]) == {"source", "change", "as_of", "members"}
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
                      "newest", "sources"}
    assert set(b["sources"][0]) == {"id", "label", "kind", "weight", "state", "newest", "history_days",
                                    "coins_with_data", "eligible_size", "note"}
    assert b["total_sources"] == 7 and b["eligible_size"] == 2


def test_router_discovery_new_fields_present(wired):
    body = wired.get(URL, params={"window": 30}).json()
    assert (body["narratives_status"], body["categories_as_of"]) == ("proposed", "2026-10-14")
    assert (body["unassigned"], body["min_category_coins"]) == ([], 1)
    assert body["hidden_narratives"] == [{"id": "defi", "name": "DeFi", "coins": []}]
    assert [c["primary"] for c in body["categories"][0]["coins"]] == [True, True]
