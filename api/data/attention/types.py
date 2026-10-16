"""Shared types for attention sources."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

State = Literal["ok", "unavailable", "insufficient-history", "no-article", "capped", "not-probed"]

MIN_HISTORY_DAYS = 90


@dataclass
class SourceSeries:
    source: str
    symbol: str
    points: list[tuple[date, float]] = field(default_factory=list)
    state: State = "unavailable"
    reason: str = ""
