"""S-C: GET /api/narrative/baskets/attention through the real app, store only."""
from __future__ import annotations

import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from api.analytics.attention import score as score_mod, universe as universe_mod
from api.data.attention import registry
from api.main import app
from api.routers import attention as router_mod
from api.tests.analytics.attention.conftest import SOURCES, TODAY, make_layout, put, put_refs, write_configs

URL = "/api/narrative/baskets/attention"


@pytest.fixture
def wired(isolated_cache, tmp_path, monkeypatch):
    probe, w, u = write_configs(tmp_path)
    monkeypatch.setattr(registry, "PROBE_RECORDS_PATH", probe)
    monkeypatch.setattr(score_mod, "WEIGHTS_PATH", w)
    monkeypatch.setattr(universe_mod, "UNIVERSE_PATH", u)
    monkeypatch.setattr(router_mod, "utc_today", lambda: TODAY)
    monkeypatch.setattr(router_mod, "read_layout", lambda section: make_layout(
        {"main": ["Z"], "alpha": ["A1", "A2"]}))
    put_refs()
    for s in SOURCES:
        put(s, "A1", 1.5)
        put(s, "A2", 3.5)

    def boom(*a, **k):
        raise AssertionError("handler must not reach the network")
    monkeypatch.setattr(httpx.Client, "send", boom)
    monkeypatch.setattr(httpx.AsyncClient, "send", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    return TestClient(app)


def test_default_window_30_reads_store_only(wired):
    r = wired.get(URL)
    assert r.status_code == 200
    body = r.json()
    assert body["window"] == 30 and body["membership_as_of"]
    (b,) = body["baskets"]
    assert b["id"] == "alpha" and b["score"] == pytest.approx(50.0)
    assert b["coverage"] == "covers 2 of 2" and b["universe_size"] == 4
    assert "total" not in body


@pytest.mark.parametrize("w", [7, 30, 90])
def test_valid_windows(wired, w):
    assert wired.get(URL, params={"window": w}).json()["window"] == w


@pytest.mark.parametrize("w", ["14", "0", "abc"])
def test_bad_window_is_422(wired, w):
    assert wired.get(URL, params={"window": w}).status_code == 422
