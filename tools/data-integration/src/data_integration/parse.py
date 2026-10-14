"""Table parsing over the Scrapling Selector (parser only: no fetchers, no networking)."""
from __future__ import annotations

from scrapling.parser import Selector

from data_integration.types import ParsedTable


class ParseError(ValueError):
    """The page did not contain the expected table."""


def _text(cell) -> str:
    return " ".join(str(cell.get_all_text()).split())


def parse_table(content: str | bytes, selector: str = "table") -> ParsedTable:
    """First element matching `selector` read as header row plus body rows (Scrapling has no table helper)."""
    page = Selector(content)
    found = page.css(selector)
    if not found:
        raise ParseError(f"selector matched nothing: {selector}")
    rows = [[_text(c) for c in tr.css("th, td")] for tr in found[0].css("tr")]
    rows = [r for r in rows if r]
    if not rows:
        raise ParseError("table has no rows")
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ParseError("ragged table")
    return ParsedTable(columns=tuple(rows[0]), rows=tuple(tuple(r) for r in rows[1:]))
