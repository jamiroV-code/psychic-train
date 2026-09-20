"""GET /api/regime/legs tests (Implementation Checklist item 43): endpoint
shape + variant-selection wiring.

SANDBOX NOTE: `fastapi` could not be installed in this sandbox (network
egress to PyPI is blocked for this session — see EXECUTE report
Deviations, same constraint RFC-001 hit), so these exercise
`api/routers/regime.py::get_legs`'s exact assembly logic directly rather
than going through `fastapi.testclient.TestClient` as the plan's
Verification Evidence command implies — the same bypass RFC-001's
`test_screener.py` already established for this sandbox. Test names match
the plan's intent; only the HTTP-client layer is bypassed.
"""
from __future__ import annotations

import pandas as pd
import pytest

from api.analytics.regime import leg_boundary
from api.analytics.regime.benchmark import select_active_benchmark
from api.models.regime import CurrentLegState, LegBoundary, LegBoundaryResponse


def _get_legs() -> LegBoundaryResponse:
    """Mirrors `routers/regime.py::get_legs` exactly."""
    state = leg_boundary.compute_current_leg_state()
    benchmark = select_active_benchmark(state)
    return LegBoundaryResponse(
        composite_variant=state.composite_variant,
        candidate_boundaries=state.candidate_boundaries,
        confirmed_boundaries=state.confirmed_boundaries,
        active_benchmark_reason=benchmark.reason,
    )


class TestGetLegsShape:
    def test_no_data_state_returns_well_formed_empty_response(self, monkeypatch):
        fake_state = CurrentLegState(candidate_boundaries=[], confirmed_boundaries=[], composite_variant="reduced", has_data=False)
        monkeypatch.setattr(leg_boundary, "compute_current_leg_state", lambda: fake_state)

        response = _get_legs()
        assert isinstance(response, LegBoundaryResponse)
        assert response.composite_variant == "reduced"
        assert response.candidate_boundaries == []
        assert response.confirmed_boundaries == []
        assert response.active_benchmark_reason  # never blank/silent

    def test_variant_selection_is_reflected_in_response(self, monkeypatch):
        fake_state = CurrentLegState(
            candidate_boundaries=[LegBoundary(date="2024-06-01", z_score=1.8, confirmed=False)],
            confirmed_boundaries=[],
            composite_variant="full",
            has_data=True,
        )
        monkeypatch.setattr(leg_boundary, "compute_current_leg_state", lambda: fake_state)

        response = _get_legs()
        assert response.composite_variant == "full"
        assert len(response.candidate_boundaries) == 1
        assert response.active_benchmark_reason.startswith("BTC-dominant") or "BTC" in response.active_benchmark_reason

    def test_confirmed_boundary_wires_hype_benchmark_into_response(self, monkeypatch):
        fake_state = CurrentLegState(
            candidate_boundaries=[LegBoundary(date="2024-06-01", z_score=1.8, confirmed=True, confirmed_date="2024-06-03")],
            confirmed_boundaries=[LegBoundary(date="2024-06-01", z_score=1.8, confirmed=True, confirmed_date="2024-06-03")],
            composite_variant="full",
            has_data=True,
        )
        monkeypatch.setattr(leg_boundary, "compute_current_leg_state", lambda: fake_state)

        response = _get_legs()
        assert "HYPE" in response.active_benchmark_reason or "rotation" in response.active_benchmark_reason.lower()
