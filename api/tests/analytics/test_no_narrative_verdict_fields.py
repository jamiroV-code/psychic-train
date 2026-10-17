"""T80 / S-D2: the old trigger/momentum verdict is gone from the narrative API.

Routes `/categories` and `/momentum` 404, the modules are not importable, the
`/history` and `/mindshare` JSON carry no `triggered` / `confirmed`, and the
`/history` composite keeps exactly its pre-D2 keys (`trust_weight` stays: it is
history-owned since D1). Scan scope is the narrative package, its router and
its models only: regime code legitimately says `confirmed`.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app

API = Path(__file__).resolve().parents[2]
SCAN = [*sorted((API / "analytics" / "narrative").glob("*.py")), API / "routers" / "narrative.py", API / "models" / "narrative.py"]
VERDICT = re.compile(r"\b(triggered|confirmed)\b")

COMPOSITE_POINT_KEYS = {"date", "value", "coverage", "sources_present", "trust_weight", "mixed_scale", "gap_before"}
COMPOSITE_KEYS = {"status", "reason", "sources", "min_sources", "max_gap_days", "points"}
CATEGORY_KEYS = {"category_id", "label", "keywords", "coins", "series", "composite"}
RESPONSE_KEYS = {"generated_utc", "redistributable_all", "grid_dates", "categories", "comparison", "change_in_attention"}


@pytest.mark.parametrize("path", ["/api/narrative/categories", "/api/narrative/momentum"])
def test_removed_routes_404(path):
    assert TestClient(app).get(path).status_code == 404
    assert path not in app.openapi()["paths"]


@pytest.mark.parametrize("mod", ["trigger", "momentum"])
def test_verdict_modules_not_importable(mod):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"api.analytics.narrative.{mod}")


@pytest.mark.parametrize("name", ["NarrativeCategory", "NarrativeTriggerState", "NarrativeMomentumEntry", "NarrativeMomentumResponse"])
def test_verdict_models_removed(name):
    from api.models import narrative

    assert not hasattr(narrative, name)


def test_history_schema_keys_unchanged():
    from api.models.narrative import (
        NarrativeComposite, NarrativeCompositePoint, NarrativeHistoryCategory, NarrativeHistoryResponse,
    )

    assert set(NarrativeHistoryResponse.model_fields) == RESPONSE_KEYS
    assert set(NarrativeHistoryCategory.model_fields) == CATEGORY_KEYS
    assert set(NarrativeComposite.model_fields) == COMPOSITE_KEYS
    assert set(NarrativeCompositePoint.model_fields) == COMPOSITE_POINT_KEYS


def test_history_and_mindshare_schemas_carry_no_verdict_field():
    schemas = app.openapi()["components"]["schemas"]
    for name, schema in schemas.items():
        if name.startswith(("NarrativeHistory", "NarrativeMindshare", "NarrativeComposite")):
            assert not {"triggered", "confirmed"} & set(schema.get("properties", {})), name


def test_narrative_source_has_no_verdict_words():
    hits = [
        f"{p.relative_to(API)}:{n}: {m.group(0)}"
        for p in SCAN
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        for m in VERDICT.finditer(line)
    ]
    assert not hits, "\n".join(hits)
