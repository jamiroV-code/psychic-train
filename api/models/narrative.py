"""Pydantic contracts for RFC-003 (Narrative / Mindshare), items 54/56.

`NarrativeCategory` (ADR-3): API responses always carry every triggered
category regardless of `confirmed` — a triggered-but-unconfirmed category
is never hidden, only carries a lower `trust_weight` (see Public
Contracts, `GET /api/narrative/categories`).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SourceAvailability = Literal["ok", "unavailable", "stale", "presumed-dead"]


class NarrativeTriggerState(BaseModel):
    """Internal trigger-computation result for one category (items 51/52)
    — the pre-response shape `trigger.compute_trigger`/`apply_confirmation`
    produce; `routers/narrative.py` assembles this into the public
    `NarrativeCategory` response shape below.
    """

    category_id: str
    triggered: bool
    confirmed: bool
    trust_weight: float
    trigger_date: str | None = None
    confirmed_date: str | None = None
    source_availability: dict[str, SourceAvailability]


class NarrativeCategory(BaseModel):
    id: str
    label: str
    keywords: list[str]
    seed: bool  # True = curated narrative_categories.json seed list; False = auto-flagged emerging
    triggered: bool
    confirmed: bool
    trust_weight: float
    source_availability: dict[str, SourceAvailability]
