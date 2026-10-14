"""Table validation: required columns, numeric types, ranges, ordering, minimum rows."""
from __future__ import annotations

from datetime import datetime

from data_integration.types import ParsedTable

REQUIRED = ("date", "open", "high", "low", "close", "volume")
PRICES = ("open", "high", "low", "close")


def column_index(table: ParsedTable) -> dict[str, int]:
    return {c.strip().lower(): i for i, c in enumerate(table.columns)}


def parse_number(text: object) -> float:
    return float(str(text).replace(",", "").strip())


def parse_time(text: object) -> datetime:
    return datetime.fromisoformat(str(text).strip())


def validate_table(table: ParsedTable, min_rows: int = 2) -> list[str]:
    """Problems found; an empty list means valid."""
    idx = column_index(table)
    missing = [c for c in REQUIRED if c not in idx]
    if missing:
        return [f"missing columns: {', '.join(missing)}"]
    if len(table.rows) < min_rows:
        return [f"too few rows: {len(table.rows)} < {min_rows}"]
    problems: list[str] = []
    prev = None
    for n, row in enumerate(table.rows, start=1):
        try:
            nums = {c: parse_number(row[idx[c]]) for c in PRICES + ("volume",)}
        except ValueError:
            problems.append(f"row {n}: non-numeric value")
            continue
        if any(not v == v or v in (float("inf"), float("-inf")) for v in nums.values()):
            problems.append(f"row {n}: non-finite value")
            continue
        if any(nums[c] <= 0 for c in PRICES):
            problems.append(f"row {n}: non-positive price")
        if nums["volume"] < 0:
            problems.append(f"row {n}: negative volume")
        if nums["high"] < nums["low"]:
            problems.append(f"row {n}: high below low")
        try:
            ts = parse_time(row[idx["date"]])
        except ValueError:
            problems.append(f"row {n}: unparseable timestamp")
            continue
        if prev is not None:
            try:
                if ts <= prev:
                    problems.append(f"row {n}: timestamp not increasing")
            except TypeError:
                problems.append(f"row {n}: mixed naive and aware timestamps")
        prev = ts
    return problems
