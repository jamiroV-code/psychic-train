"""T103 W2: GET /api/narrative/discovery/history through the real app, store only."""
from __future__ import annotations

import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from api.analytics.attention import discovery_history
from api.main import app
from api.routers import discovery as router_mod
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import gain, world

URL = "/api/narrative/discovery/history"


@pytest.fixture
def wired(isolated_cache, tmp_path, monkeypatch):
    discovery_history.clear_cache()
    monkeypatch.setattr(router_mod, "utc_today", lambda: TODAY)
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]})
    gain("A"), gain("B", factor=3.0)

    def boom(*a, **k):
        raise AssertionError("handler must not reach the network")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    return TestClient(app)


def test_coin_payload_shape(wired):
    r = wired.get(URL, params={"symbol": "a", "window": 30})
    assert r.status_code == 200
    b = r.json()
    assert (b["kind"], b["id"], b["window"], b["status"], b["reason"]) == ("coin", "A", 30, "ok", "")
    assert set(b) == {"kind", "id", "window", "as_of", "status", "reason", "min_history_days",
                      "min_covered_weight", "history_days", "days"}
    assert b["min_covered_weight"] == 30
    assert len(b["days"]) == 30
    assert set(b["days"][-1]) == {"date", "score", "covered_weight", "rising_weight", "trigger", "thin"}
    assert b["days"][-1]["date"] == b["as_of"]


def test_category_payload_shape(wired):
    r = wired.get(URL, params={"category": "ai", "window": 7})
    assert r.status_code == 200
    b = r.json()
    assert (b["kind"], b["id"], b["status"]) == ("category", "ai", "ok")
    assert set(b["days"][-1]) == {"date", "score", "coins_used", "triggered_count", "triggered_share"}
    assert b["days"][-1]["coins_used"] == 2


def test_default_window_is_30(wired):
    assert wired.get(URL, params={"symbol": "A"}).json()["window"] == 30


@pytest.mark.parametrize("w", ["14", "0", "abc"])
def test_bad_window_is_422(wired, w):
    assert wired.get(URL, params={"symbol": "A", "window": w}).status_code == 422


def test_needs_exactly_one_subject(wired):
    assert wired.get(URL).status_code == 422
    assert wired.get(URL, params={"symbol": "A", "category": "ai"}).status_code == 422


def test_unknown_subjects_are_404_with_plain_message(wired):
    r = wired.get(URL, params={"symbol": "NOPE"})
    assert r.status_code == 404 and "NOPE" in r.json()["detail"]
    r = wired.get(URL, params={"category": "nope"})
    assert r.status_code == 404 and "nope" in r.json()["detail"]


def test_empty_is_no_data(wired, isolated_cache):
    for p in (isolated_cache / "attention").glob("*/B.parquet"):
        p.unlink()
    b = wired.get(URL, params={"symbol": "B"}).json()
    assert (b["status"], b["reason"], b["days"]) == ("no-data", "no-attention-data", [])


def test_live_endpoint_unchanged(wired):
    assert wired.get("/api/narrative/discovery", params={"window": 30}).status_code == 200
