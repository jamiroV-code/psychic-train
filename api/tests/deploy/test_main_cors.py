"""AC1 + AC2 (deployability plan, gate G1): the `api/main.py` docstring stops
claiming a localhost-only bind, and CORS is an explicit, tightened allow-list
driven only by `SCREENER_CORS_ORIGINS`.

All offline: preflight checks run against a throwaway FastAPI app built with
`api.main._cors_options`, or against the real app through TestClient.
"""
from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

import api.main as main_module

TAILNET_ORIGIN = "http://100.101.102.103:3000"


def _throwaway_app(origins: list[str]) -> FastAPI:
    app = FastAPI()
    app.add_middleware(CORSMiddleware, **main_module._cors_options(origins))

    @app.get("/probe")
    def probe() -> dict:
        return {"ok": True}

    return app


def _preflight(client: TestClient, origin: str, method: str = "GET"):
    return client.options(
        "/probe",
        headers={"Origin": origin, "Access-Control-Request-Method": method},
    )


# ----------------------------------------------------------------- docstring


def test_docstring_no_longer_claims_localhost_only_bind():
    doc = main_module.__doc__ or ""
    assert "binds to 127.0.0.1 only" not in doc
    assert "never 0.0.0.0" not in doc


def test_docstring_states_tailscale_posture_and_run_command_concern():
    doc = (main_module.__doc__ or "").lower()
    assert "tailscale" in doc
    assert "run command" in doc, "the bind address must be described as a run-command concern"


# ------------------------------------------------------------- parse helper


def test_default_origin_is_localhost_3000_when_env_unset():
    assert main_module._parse_cors_origins(None) == ["http://localhost:3000"]


def test_empty_env_value_denies_all_origins():
    assert main_module._parse_cors_origins("") == []
    assert main_module._parse_cors_origins(" , ,") == []


def test_override_env_is_parsed_comma_separated_and_stripped():
    raw = f" {TAILNET_ORIGIN} , http://localhost:3000,, "
    assert main_module._parse_cors_origins(raw) == [TAILNET_ORIGIN, "http://localhost:3000"]


# --------------------------------------------------------- preflight behavior


def test_allowlisted_origin_preflight_accepted():
    client = TestClient(_throwaway_app([TAILNET_ORIGIN]))
    resp = _preflight(client, TAILNET_ORIGIN)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == TAILNET_ORIGIN


def test_non_allowlisted_origin_preflight_rejected():
    client = TestClient(_throwaway_app([TAILNET_ORIGIN]))
    resp = _preflight(client, "http://192.168.1.50:3000")
    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


def test_cors_options_no_credentials_no_wildcards():
    opts = main_module._cors_options([TAILNET_ORIGIN])
    assert opts["allow_origins"] == [TAILNET_ORIGIN]
    assert opts["allow_credentials"] is False
    assert "*" not in opts["allow_methods"]
    assert "*" not in opts["allow_headers"]
    assert set(opts["allow_methods"]) == {"GET", "POST", "DELETE"}
    assert list(opts["allow_headers"]) == ["Content-Type"]
    # A method the API never serves is refused at preflight.
    client = TestClient(_throwaway_app([TAILNET_ORIGIN]))
    assert _preflight(client, TAILNET_ORIGIN, method="PUT").status_code == 400


# ------------------------------------------------------ import-time wiring


def _cors_kwargs(app: FastAPI) -> dict:
    for mw in app.user_middleware:
        if mw.cls is CORSMiddleware:
            return dict(mw.kwargs)
    raise AssertionError("CORSMiddleware not registered on api.main.app")


@pytest.fixture
def restore_main(monkeypatch):
    """Reload hygiene (plan step 3, rule iii): record the original module
    attributes, and after the test undo the env and reload again so every
    later test sees the default app. A final assert proves the restore."""
    original_origins = list(main_module.CORS_ORIGINS)
    yield
    monkeypatch.undo()
    reloaded = importlib.reload(main_module)
    assert reloaded.CORS_ORIGINS == original_origins


def test_import_time_wiring_honors_env(monkeypatch, restore_main):
    monkeypatch.setenv("SCREENER_CORS_ORIGINS", f"{TAILNET_ORIGIN}, http://mysite.tailnet.ts.net:3000")
    reloaded = importlib.reload(main_module)
    assert reloaded.CORS_ORIGINS == [TAILNET_ORIGIN, "http://mysite.tailnet.ts.net:3000"]
    kwargs = _cors_kwargs(reloaded.app)
    assert kwargs["allow_origins"] == [TAILNET_ORIGIN, "http://mysite.tailnet.ts.net:3000"]
    assert kwargs["allow_credentials"] is False


def test_no_credentials_header_on_real_app_response():
    client = TestClient(main_module.app)
    origin = main_module.CORS_ORIGINS[0] if main_module.CORS_ORIGINS else "http://localhost:3000"
    resp = client.get("/api/health", headers={"Origin": origin})
    assert resp.status_code == 200
    assert "access-control-allow-credentials" not in resp.headers
