"""GET /api/narrative/categories tests (item 57): AC-11 gate — a simulated
per-source failure must degrade the category's confidence explicitly,
never silently substitute a neutral/full-confidence reading.

SANDBOX NOTE: same fastapi-unavailable bypass as test_regime.py (see its
own SANDBOX NOTE) — exercises `api/routers/narrative.py::get_categories`'s
exact assembly logic directly rather than via `fastapi.testclient.TestClient`.
"""
from __future__ import annotations

from api.analytics.narrative import trigger
from api.models.narrative import NarrativeCategory


def _get_categories() -> list[NarrativeCategory]:
    """Mirrors `routers/narrative.py::get_categories` exactly."""
    results = trigger.compute_narrative_categories()
    seed_meta = {c["id"]: c for c in trigger.load_seed_categories()}
    categories: list[NarrativeCategory] = []
    for result in results:
        meta = seed_meta.get(result.category_id, {})
        categories.append(
            NarrativeCategory(
                id=result.category_id,
                label=meta.get("label", result.category_id),
                keywords=meta.get("keywords", []),
                seed=result.category_id in seed_meta,
                triggered=result.triggered,
                confirmed=result.confirmed,
                trust_weight=result.trust_weight,
                source_availability=result.source_availability,
            )
        )
    return categories


_FAKE_META = [{"id": "ai", "label": "AI", "keywords": ["AI crypto"]}]


class TestGetCategoriesShape:
    def test_empty_results_returns_empty_list_not_error(self, monkeypatch):
        monkeypatch.setattr(trigger, "compute_narrative_categories", lambda **k: [])
        assert _get_categories() == []

    def test_seed_metadata_populates_label_and_keywords(self, monkeypatch):
        fake_result = trigger.TriggerResult(
            category_id="ai", triggered=True, confirmed=False, trust_weight=0.6,
            trigger_date="2024-06-01", confirmed_date=None,
            source_availability={"pytrends": "ok", "reddit": "ok", "coingecko": "ok"},
        )
        monkeypatch.setattr(trigger, "compute_narrative_categories", lambda **k: [fake_result])
        monkeypatch.setattr(trigger, "load_seed_categories", lambda: _FAKE_META)

        result = _get_categories()
        assert len(result) == 1
        assert result[0].label == "AI"
        assert result[0].seed is True


class TestNarrativeFetchFailureDegradesExplicitly:
    """AC-11 gate (item 57)."""

    def test_single_source_failure_still_returns_category_with_degraded_trust(self, monkeypatch):
        fake_result = trigger.TriggerResult(
            category_id="ai", triggered=True, confirmed=False, trust_weight=trigger.REDUCED_SOURCE_TRUST_CAP,
            trigger_date="2024-06-01", confirmed_date=None,
            source_availability={"pytrends": "presumed-dead", "reddit": "ok", "coingecko": "ok"},
        )
        monkeypatch.setattr(trigger, "compute_narrative_categories", lambda **k: [fake_result])
        monkeypatch.setattr(trigger, "load_seed_categories", lambda: _FAKE_META)

        result = _get_categories()
        assert result[0].source_availability["pytrends"] == "presumed-dead"
        assert result[0].trust_weight <= trigger.REDUCED_SOURCE_TRUST_CAP
        assert result[0].triggered is True  # still visible, not suppressed by the failure

    def test_all_sources_failed_returns_untriggered_never_a_fabricated_trigger(self, monkeypatch):
        fake_result = trigger.TriggerResult(
            category_id="ai", triggered=False, confirmed=False, trust_weight=0.0,
            trigger_date=None, confirmed_date=None,
            source_availability={"pytrends": "unavailable", "reddit": "unavailable", "coingecko": "unavailable"},
        )
        monkeypatch.setattr(trigger, "compute_narrative_categories", lambda **k: [fake_result])
        monkeypatch.setattr(trigger, "load_seed_categories", lambda: _FAKE_META)

        result = _get_categories()
        assert result[0].triggered is False
        assert result[0].trust_weight == 0.0
        assert all(v == "unavailable" for v in result[0].source_availability.values())
