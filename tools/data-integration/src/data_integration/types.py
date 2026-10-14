"""Shared value types. No network imports here (see the import-boundary guard)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class FetchOutcome:
    status: str
    url: str
    http_status: int | None = None
    body: bytes = b""
    detail: str = ""
    body_sha256: str | None = None


@dataclass(frozen=True)
class ParsedTable:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...] = field(default_factory=tuple)


class Fetcher(Protocol):
    def fetch(self, url: str, pass_: Any) -> FetchOutcome: ...
