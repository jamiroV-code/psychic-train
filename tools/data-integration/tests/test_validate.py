"""validate.py: required columns, numeric types, ranges, ordering, minimum rows."""
from __future__ import annotations

from pathlib import Path

from data_integration.parse import parse_table
from data_integration.types import ParsedTable
from data_integration.validate import validate_table

FIX = Path(__file__).parent / "fixtures"
COLS = ("Date", "Open", "High", "Low", "Close", "Volume")


def _t(rows, cols=COLS):
    return ParsedTable(columns=cols, rows=tuple(tuple(r) for r in rows))


GOOD = [("2025-01-01", "1", "2", "1", "2", "10"), ("2025-01-02", "2", "3", "2", "3", "11")]


def test_good_table_has_no_problems():
    assert validate_table(_t(GOOD)) == []
    assert validate_table(parse_table((FIX / "ok.html").read_text(), "table.prices")) == []


def test_missing_required_column():
    assert validate_table(_t([r[:5] for r in GOOD], COLS[:5]))


def test_non_numeric_value():
    assert validate_table(_t([GOOD[0], ("2025-01-02", "x", "3", "2", "3", "11")]))


def test_non_positive_price():
    assert validate_table(_t([GOOD[0], ("2025-01-02", "0", "3", "2", "3", "11")]))


def test_high_below_low():
    assert validate_table(parse_table((FIX / "bad_range.html").read_text(), "table.prices"))


def test_timestamps_must_increase():
    assert validate_table(_t([GOOD[1], GOOD[0]]))
    assert validate_table(_t([GOOD[0], GOOD[0]]))


def test_unparseable_timestamp():
    assert validate_table(_t([GOOD[0], ("not-a-date", "2", "3", "2", "3", "11")]))


def test_minimum_rows():
    assert validate_table(parse_table((FIX / "one_row.html").read_text(), "table.prices"))
    assert validate_table(_t(GOOD), min_rows=3)


def test_negative_volume():
    assert validate_table(_t([GOOD[0], ("2025-01-02", "2", "3", "2", "3", "-1")]))
