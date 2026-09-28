"""narrative-v2 RFC-7 (ADR-7 item 1): tripwire on the frozen `/categories` path.

`trigger.py` and `mapping.py`'s legacy symbols drive `/api/narrative/categories`
and `/screener`, which narrative-v2 must leave byte-identical (AC-13). These
tests pin the file's bytes, its public surface and every signature, as they
stood at the pre-plan base commit `a86a2f0` (and unchanged since `bc64b63`).

If one of these fails, someone edited a frozen file. Do NOT update the
snapshot to make it pass — revert the edit, or get an explicit, separately
scoped AC-13 re-baseline approved first.
"""
from __future__ import annotations

import dataclasses
import hashlib
import inspect
from pathlib import Path

from api.analytics.narrative import mapping, trigger

TRIGGER_SHA256 = "3687f80a1ec91ff70647401c7ef46374cf2700f55d9a50748b35378a37b7641b"

TRIGGER_NAMES = {
    "BASE_TRUST_WEIGHT", "CONFIRMATION_SUSTAINED_DAYS", "CONFIRMED_TRUST_WEIGHT", "KEYWORD_KEYED_SOURCES",
    "MIN_AVAILABLE_SOURCES", "NARRATIVE_CATEGORIES_PATH", "NarrativeCategory", "Path", "REDUCED_SOURCE_TRUST_CAP",
    "TOTAL_SOURCES", "TRIGGER_ROC_DAYS", "TRIGGER_ZSCORE_MIN_PERIODS", "TRIGGER_ZSCORE_THRESHOLD", "TriggerResult",
    "_source_history_key", "annotations", "apply_confirmation", "assemble_narrative_categories", "cache",
    "coingecko_adapter", "compute_narrative_categories", "compute_trigger", "dataclass", "datetime", "json",
    "load_seed_categories", "mapping", "pd", "pytrends_adapter", "reddit_adapter", "scoring", "timezone",
}

TRIGGER_SIGNATURES = {
    "_source_history_key": "(source: 'str', category_id: 'str', primary_keyword: 'str') -> 'str'",
    "load_seed_categories": "() -> 'list[dict]'",
    "compute_trigger": "(category_id: 'str', proxy_series_by_source: 'dict[str, pd.Series | None]', "
                       "source_status: 'dict[str, str]') -> 'TriggerResult'",
    "apply_confirmation": "(state: 'TriggerResult', as_of: 'str | None' = None, "
                          "user_action: 'bool' = False) -> 'TriggerResult'",
    "compute_narrative_categories": "(as_of: 'str | None' = None) -> 'list[TriggerResult]'",
    "assemble_narrative_categories": "(as_of: 'str | None' = None) -> 'list[NarrativeCategory]'",
}

TRIGGER_CONSTANTS = {
    "TRIGGER_ROC_DAYS": 3, "TRIGGER_ZSCORE_MIN_PERIODS": 3, "TRIGGER_ZSCORE_THRESHOLD": 1.0,
    "CONFIRMATION_SUSTAINED_DAYS": 10, "BASE_TRUST_WEIGHT": 0.6, "CONFIRMED_TRUST_WEIGHT": 0.9,
    "REDUCED_SOURCE_TRUST_CAP": 0.4, "MIN_AVAILABLE_SOURCES": 2,
    "TOTAL_SOURCES": ("pytrends", "reddit", "coingecko"), "KEYWORD_KEYED_SOURCES": ("pytrends", "reddit"),
}

TRIGGER_RESULT_FIELDS = [
    ("category_id", "str"), ("triggered", "bool"), ("confirmed", "bool"), ("trust_weight", "float"),
    ("trigger_date", "str | None"), ("confirmed_date", "str | None"), ("source_availability", "dict[str, str]"),
]


def test_trigger_file_bytes_unchanged():
    digest = hashlib.sha256(Path(trigger.__file__).read_bytes()).hexdigest()
    assert digest == TRIGGER_SHA256, "api/analytics/narrative/trigger.py is frozen (AC-13) and was edited"


def test_trigger_exported_names_unchanged():
    assert {n for n in vars(trigger) if not n.startswith("__")} == TRIGGER_NAMES


def test_trigger_tripwire_signatures_unchanged():
    got = {name: str(inspect.signature(getattr(trigger, name))) for name in TRIGGER_SIGNATURES}
    assert got == TRIGGER_SIGNATURES


def test_trigger_constants_and_result_shape_unchanged():
    assert {k: getattr(trigger, k) for k in TRIGGER_CONSTANTS} == TRIGGER_CONSTANTS
    assert trigger.NARRATIVE_CATEGORIES_PATH.name == "narrative_categories.json"
    assert [(f.name, str(f.type)) for f in dataclasses.fields(trigger.TriggerResult)] == TRIGGER_RESULT_FIELDS


def test_trigger_still_reads_the_legacy_seed_file_not_narratives_json():
    seeds = trigger.load_seed_categories()
    assert [c["id"] for c in seeds] == ["ai", "rwa", "l2s", "memecoins"]


def test_mapping_frozen_legacy_surface_unchanged():
    assert mapping.LEGACY_COIN_CATEGORY_MAP == {"BTC": "store-of-value", "ETH": "l2s", "HYPE": "l2s"}
    assert mapping.COIN_CATEGORY_MAP is mapping.LEGACY_COIN_CATEGORY_MAP
    assert str(inspect.signature(mapping.map_coin_to_category)) == "(symbol: 'str') -> 'str | None'"
