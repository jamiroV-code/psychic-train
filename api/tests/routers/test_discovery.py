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
                         "universe_size", "eligible_size", "categories"}
    c = body["categories"][0]
    assert set(c) == {"id", "name", "score", "median", "coins_used", "gaining_count", "coins"}
    assert set(c["coins"][0]) == {"symbol", "change", "raw_change", "covered_weight", "rising_weight",
                                  "trigger", "sources"}
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


def test_categories_missing_over_http(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setattr(router_mod, "utc_today", lambda: TODAY)
    world(tmp_path, monkeypatch, {"A": 5e7}, cats=None)
    body = TestClient(app).get(URL).json()
    assert (body["status"], body["reason"], body["categories"]) == ("no-data", "categories-missing", [])
