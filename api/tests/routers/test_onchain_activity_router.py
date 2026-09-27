"""GET /api/onchain/growth + /chains (chain-growth RFC-4).

Synthetic archive in `isolated_cache`, a temp chains.json, no network (any
httpx send fails the test), and no writes (cache tree unchanged by requests).
"""
from __future__ import annotations

import gzip
import json
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.testclient import TestClient

from api.analytics.onchain import response as resp
from api.data import cache
from api.data.chain_growth_config import load_chains
from api.main import app

URL = "/api/onchain/growth"
TODAY = datetime.now(timezone.utc).date()

CHAINS = {"chains": [
    {"id": "alpha", "label": "Alpha", "enabled": True, "launch_date": None,
     "metrics": {"active_addresses": {"source": "growthepie", "source_key": "alpha"},
                 "transactions": {"source": "growthepie", "source_key": "alpha"}},
     "cross_check": {"source": "l2beat", "source_key": "alpha"}},
    {"id": "newbie", "label": "Newbie", "enabled": True, "launch_date": (TODAY - timedelta(days=40)).isoformat(),
     "limited_history": True,
     "metrics": {"active_addresses": {"source": "growthepie", "source_key": "newbie"},
                 "transactions": {"source": "growthepie", "source_key": "newbie"}}},
    {"id": "solana", "label": "Solana", "enabled": True, "launch_date": None,
     "metrics": {"active_addresses": {"source": "none", "unavailable_reason": "source-unavailable"},
                 "transactions": {"source": "none", "unavailable_reason": "source-unavailable"}}},
    {"id": "off", "label": "Off", "enabled": False, "launch_date": None,
     "metrics": {"transactions": {"source": "growthepie", "source_key": "off"}}},
]}


def _points(start: date, n: int, value, skip: set[int] = frozenset()):
    return [((start + timedelta(days=i)).isoformat(), float(value(i))) for i in range(n) if i not in skip]


@pytest.fixture
def archive(isolated_cache, tmp_path, monkeypatch):
    cfg = tmp_path / "chains.json"
    cfg.write_text(json.dumps(CHAINS))
    chains = load_chains(cfg)
    monkeypatch.setattr(resp, "load_chains", lambda: chains)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    kw = {"today": TODAY.isoformat(), "now_utc": now}
    start = TODAY - timedelta(days=399)
    for m in ("active_addresses", "transactions"):
        cache.merge_onchain_series("growthepie", "alpha", m, _points(start, 400, lambda i: 1000 + i, skip={100, 101, 102}), **kw)
        cache.merge_onchain_series("growthepie", "newbie", m, _points(TODAY - timedelta(days=59), 60, lambda i: 1 if i < 20 else 500), **kw)
    cache.merge_onchain_series("l2beat", "alpha", "transactions", _points(start, 400, lambda i: (1000 + i) * 1.01), **kw)

    def no_network(*a, **k):
        raise AssertionError("network call from a read-only endpoint")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)
    return isolated_cache


def _snapshot(root):
    return sorted((p.as_posix(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file())


@pytest.fixture
def client():
    return TestClient(app)


def test_shape_and_grid_sync(archive, client):
    before = _snapshot(archive)
    body = client.get(URL, params={"metric": "transactions"}).json()
    assert _snapshot(archive) == before  # read-only
    assert body["metric"] == "transactions"
    grid = body["grid_dates"]
    assert grid == sorted(grid) and len(grid) == 397  # 400 minus the 3-day gap
    ids = [c["id"] for c in body["chains"]]
    assert ids == ["alpha", "newbie", "solana"]  # disabled chain omitted
    alpha = body["chains"][0]
    s = alpha["series"]
    assert s["source"] == "growthepie" and s["redistributable"] is True
    assert s["attribution"].startswith("Source: growthepie")
    assert s["max_gap_days"] == 1
    assert sum(p["gap_before"] for p in s["points"]) == 1
    assert set(p["date"] for p in s["points"]) <= set(grid)
    assert alpha["status"] == "ok"
    for cs in body["comparison"]["series"]:
        assert len(cs["index_values"]) == len(grid) == len(cs["pct_above_low_values"])
    assert body["params"]["min_history_days"] == 194


def test_unavailable_chain_never_zero_filled(archive, client):
    sol = next(c for c in client.get(URL).json()["chains"] if c["id"] == "solana")
    assert sol["status"] == "unavailable" and sol["unavailable_reason"] == "source-unavailable"
    assert sol["series"] is None and sol["floor_ramp"] is None


def test_pre_launch_flagged_and_gate(archive, client):
    body = client.get(URL, params={"metric": "active_addresses"}).json()
    nb = next(c for c in body["chains"] if c["id"] == "newbie")
    pts = nb["series"]["points"]
    assert sum(p["pre_launch"] for p in pts) == 19  # TODAY-59 .. TODAY-41
    assert all(p["ema28"] is None for p in pts if p["pre_launch"])
    assert nb["history_start_date"] == nb["launch_date"]
    fr = nb["floor_ramp"]
    assert fr["state"] == "not-enough-history" and fr["history_days"] == 41 and fr["events"] == []
    cs = next(c for c in body["comparison"]["series"] if c["chain_id"] == "newbie")
    assert cs["rebased_late"] is True and cs["rebase_date"] == nb["launch_date"]


def test_cross_check_display_only_transactions_only(archive, client):
    tx = client.get(URL, params={"metric": "transactions"}).json()["chains"][0]["cross_check"]
    assert tx["display_only"] is True and tx["redistributable"] is False
    assert tx["latest_divergence_pct"] == pytest.approx(-0.990099, abs=1e-3)
    assert client.get(URL, params={"metric": "active_addresses"}).json()["chains"][0]["cross_check"] is None


def test_comparison_defaults_and_start(archive, client):
    body = client.get(URL).json()
    comp = body["comparison"]
    assert comp["log_scale_default"] is True and comp["normalization_method"] == "index-100-at-start-ema28"
    assert comp["start_date"] == (date.fromisoformat(body["grid_dates"][-1]) - timedelta(days=365)).isoformat()
    start = (TODAY - timedelta(days=50)).isoformat()
    comp2 = client.get(URL, params={"start": start}).json()["comparison"]
    alpha = next(s for s in comp2["series"] if s["chain_id"] == "alpha")
    assert alpha["rebase_date"] == start and alpha["rebased_late"] is False
    grid = client.get(URL).json()["grid_dates"]
    assert alpha["index_values"][grid.index(start)] == 100.0


def test_stale(archive, client, monkeypatch):
    monkeypatch.setattr(resp, "_utcnow", lambda: datetime.now(timezone.utc) + timedelta(days=4))
    assert client.get(URL).json()["chains"][0]["status"] == "stale"


@pytest.mark.parametrize("params", [{"metric": "new_addresses"}, {"start": "not-a-date"},
                                    {"start": (TODAY + timedelta(days=2)).isoformat()}])
def test_422(archive, client, params):
    assert client.get(URL, params=params).status_code == 422


def test_gzip(archive, client):
    r = client.get(URL, headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"
    assert any(m.cls is GZipMiddleware for m in app.user_middleware)


def test_chains_endpoint(archive, client):
    body = client.get("/api/onchain/chains").json()
    by = {c["id"]: c for c in body["chains"]}
    assert set(by) == {"alpha", "newbie", "solana", "off"}
    assert by["off"]["enabled"] is False
    assert by["alpha"]["cross_check_source"] == "l2beat"
    assert {m["metric"]: m["unavailable_reason"] for m in by["solana"]["metrics"]} == {
        "active_addresses": "source-unavailable", "transactions": "source-unavailable"}


def test_empty_archive_is_unavailable_not_zero(isolated_cache, tmp_path, monkeypatch, client):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"chains": [CHAINS["chains"][0]]}))
    chains = load_chains(cfg)
    monkeypatch.setattr(resp, "load_chains", lambda: chains)
    c = client.get(URL).json()["chains"][0]
    assert c["status"] == "unavailable" and c["unavailable_reason"] == "no-archived-data"


def test_existing_routes_unchanged():
    paths = set(app.openapi()["paths"])
    for p in ["/api/regime/legs", "/api/regime/components", "/api/narrative/categories",
              "/api/narrative/history", "/api/health"]:
        assert p in paths
    new = {p for p in paths if p.startswith("/api/onchain")}
    assert new == {"/api/onchain/growth", "/api/onchain/chains"}


def test_real_config_polygon_launch_date():
    poly = next(c for c in load_chains() if c.id == "polygon")
    assert poly.launch_date == "2020-05-30"
