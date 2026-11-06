"""B2 public account JSON: additive, closed and credential-free."""
import json

import pytest
from pydantic import ValidationError

from api.models.discovery import DiscoveryAccountHealth


BASE = dict(label="acct-1", state="active")
FIELDS = ("proxy_id", "proxy_state", "proxy_reason", "proxy_checked_at",
          "proxy_quarantine_until", "region", "connection_style", "identity_revision")


def test_legacy_json_retains_nulls_and_omits_unavailable_proxy_fields():
    row = json.loads(DiscoveryAccountHealth(**BASE).model_dump_json())
    assert row == dict(BASE, reason=None, last_used=None, cookie_age_days=None)
    assert not set(FIELDS) & row.keys()
    assert json.loads(DiscoveryAccountHealth(**BASE, **dict.fromkeys(FIELDS)).model_dump_json()) == row


@pytest.mark.parametrize("state", ["direct", "unknown", "healthy", "quarantined", "blocked"])
def test_all_proxy_states_round_trip_actual_json(state):
    values = dict(proxy_state=state, proxy_reason="proxy_region",
                  proxy_id="12345678-1234-4234-8234-123456789abc",
                  proxy_checked_at="2026-11-03T12:00:00Z",
                  proxy_quarantine_until="2026-11-03T13:00:00Z",
                  region="US-CA", connection_style="plain",
                  identity_revision="12345678-1234-4234-8234-123456789abd")
    row = json.loads(DiscoveryAccountHealth(**BASE, **values).model_dump_json())
    assert all(row[k] == v for k, v in values.items())
    assert row["state"] == "active" and row["reason"] is None


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("unsafe", ["https://user:SECRET@proxy.invalid/path", "192.0.2.1", "C:\\private\\SECRET", "/private/SECRET"])
def test_new_fields_refuse_untrusted_text(field, unsafe):
    with pytest.raises(ValidationError):
        DiscoveryAccountHealth(**BASE, **{field: unsafe})


def test_existing_account_reason_is_not_reclassified_as_proxy_state():
    row = json.loads(DiscoveryAccountHealth(**BASE, reason="x_login_required").model_dump_json())
    assert row["reason"] == "x_login_required"
    assert "proxy_state" not in row


@pytest.mark.parametrize("scenario", ["configured", "direct"])
@pytest.mark.parametrize("malformed", [None, "proxy_reason", "proxy_checked_at", "state"])
def test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection(
        isolated_cache, monkeypatch, scenario, malformed):
    import shutil
    from fastapi.testclient import TestClient
    from api.analytics.attention import discovery
    from api.data.attention import web_queries, x_pool
    from api.main import app
    from api.tests.collector_status_e2e import SECRET, seed

    monkeypatch.setenv("SCREENER_CACHE_ROOT", str(isolated_cache))
    seed()
    private = isolated_cache / "collector-private"
    shutil.copyfile(private / f"queries-{scenario}.json", private / "queries.json")
    monkeypatch.setattr(web_queries, "QUERIES_PATH", private / "queries.json")
    monkeypatch.setattr(discovery, "CONFIG_PATH", isolated_cache / "discovery.json")
    if malformed:
        original_health = x_pool.XPool.health

        def malformed_projection(pool):
            result = original_health(pool)
            account = next(a for a in result["accounts"] if a["label"] == "healthy")
            account["proxy_state"] = "healthy"
            account[malformed] = SECRET if malformed in ("proxy_reason", "state") else "2026-11-03T12:00:00"
            return result

        monkeypatch.setattr(x_pool.XPool, "health", malformed_projection)

    def snapshot():
        return {str(p.relative_to(isolated_cache)): p.read_bytes()
                for p in isolated_cache.rglob("*") if p.is_file()}

    before = snapshot()

    from api.tests.network_guard import deny_network
    deny_network(monkeypatch)
    response = TestClient(app).get("/api/narrative/sources")
    assert response.status_code == 200
    payload = response.json()
    health = next(r for r in payload["sources"] if r["id"] == "xsearch")["health"]
    accounts = health["accounts"]
    assert SECRET not in response.text and "collector-private" not in response.text
    assert snapshot() == before
    if malformed == "state":
        assert accounts == []
        assert health["accounts_active"] is None and health["accounts_total"] is None
        assert health["paused"] is True and health["pause_reason"] == "state_error"
        return
    expected = {"legacy": "unknown", "unknown": "unknown", "healthy": "healthy",
                "quarantined": "quarantined", "blocked": "blocked"}
    if malformed:
        expected["healthy"] = "unknown"
    expected_states = {label: "direct" for label in expected} if scenario == "direct" else expected
    if malformed:
        expected_states["healthy"] = "unknown"
        account = next(a for a in accounts if a["label"] == "healthy")
        assert account["state"] == "active"
        assert account["proxy_reason"] == "proxy_response"
        assert not (set(FIELDS) - {"proxy_state", "proxy_reason"}) & account.keys()
    assert {a["label"]: a.get("proxy_state", "unknown") for a in accounts} == expected_states
    assert SECRET not in response.text and "collector-private" not in response.text
    assert all(set(a) <= set(DiscoveryAccountHealth.model_fields) for a in accounts)
    assert all(a["last_used"] is None for a in accounts)
    assert all(a.get(key, "absent") is not None for a in accounts for key in FIELDS)
    assert snapshot() == before


@pytest.mark.parametrize("field,value", [
    ("identity_revision", "12345678-1234-1234-8234-123456789abd"),
    ("proxy_id", "12345678-1234-4234-8234-123456789ABC"),
    ("proxy_checked_at", "2026-11-03T12:00:00"),
    ("proxy_quarantine_until", "2026-11-03T12:00:00+01:00"),
    ("proxy_reason", "new_unknown_upstream_error"),
    ("proxy_state", "active"),
    ("region", "US California"),
    ("connection_style", "chrome"),
])
def test_public_proxy_metadata_rejects_noncanonical_or_unclosed_values(field, value):
    with pytest.raises(ValidationError):
        DiscoveryAccountHealth(**BASE, **{field: value})
