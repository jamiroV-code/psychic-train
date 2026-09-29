"""AC5 (gate G2): `GET /api/health` returns exactly `{"status": "ok"}` and is
GET-only. This is the body the runbook's reachability checks (B8, B12) read."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_health_returns_exact_status_ok_body():
    resp = TestClient(app).get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_is_get_only():
    assert TestClient(app).post("/api/health").status_code == 405
