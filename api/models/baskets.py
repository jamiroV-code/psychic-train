"""S-A (T68): response and request models for /api/narrative/baskets."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from api.models.layout import MAX_SYMBOL_LEN, LayoutGroup


class BasketsResponse(BaseModel):
    revision: int
    baskets: list[LayoutGroup]
    unassigned: list[str]


class MoveCoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(max_length=MAX_SYMBOL_LEN)


class MoveCoinResponse(BaseModel):
    symbol: str
    basket: str | None  # name; null when moved to Unassigned
    previous_basket: str | None  # name; null when it came from Unassigned
