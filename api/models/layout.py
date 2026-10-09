"""T40 / S5a: the screener layout contract (grouping, order, hidden lines).

Mirrored by hand in `web/lib/types/layout.ts`;
`api/tests/routers/test_layout.py` cross-checks the field names and types.
Membership itself stays in `watchlist.json`; a layout only arranges it.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

MAX_GROUPS = 12
MAX_GROUP_NAME = 40
# Upper bound on any list in a request body; more is a 422.
MAX_LIST = 64
MAX_SYMBOL_LEN = 15

# "file": read from layout.json; "default": no file or no section yet;
# "recovered": the file was unreadable and the default stands in for it.
LayoutSource = Literal["file", "default", "recovered"]

Symbol = Annotated[str, Field(max_length=MAX_SYMBOL_LEN)]


class LayoutGroup(BaseModel):
    id: str
    name: str
    coins: list[Symbol] = Field(max_length=MAX_LIST)


class Layout(BaseModel):
    """One section's layout after reconciling it with the watchlist.
    `saved_at` is ISO-8601 UTC with a trailing `Z`, null until a save."""

    version: int
    section: str
    revision: int
    saved_at: str | None
    source: LayoutSource
    groups: list[LayoutGroup]
    hidden_lines: list[str]


class LayoutUpdate(BaseModel):
    """`revision` must equal the stored one (0 for the default)."""

    revision: int
    groups: list[LayoutGroup] = Field(max_length=MAX_LIST)
    hidden_lines: list[Symbol] = Field(default_factory=list, max_length=MAX_LIST)
