"""AC-37/AC-38: header outline of the selected table. Pure parser, no network."""
from __future__ import annotations

from pathlib import Path

from data_integration.parse import render_table_outline, table_outline

FIX = Path(__file__).parent / "fixtures_table_outline"


def load(name):
    return (FIX / name).read_bytes()


def test_basic_counts_and_headers():
    o = table_outline(load("basic.html"), "table.prices", None)
    assert (o.matched, o.cols, o.rows) == (2, 3, 3)
    assert o.headers == ("Date", "Price (USD)", "Change %")
    assert render_table_outline(o) == ("tables matched: 2", "columns: 3", "rows: 3", "headers: Date, Price (USD), Change %")


def test_header_count_bound_12_13():
    assert len(table_outline(load("twelve.html"), "table").headers) == 12
    o = table_outline(load("thirteen.html"), "table")
    assert len(o.headers) == 12 and render_table_outline(o)[-1].endswith("(+1 more)")


def test_header_length_bound_24_25():
    assert table_outline(load("len24.html"), "table").headers == ("B" * 24,)
    assert table_outline(load("len25.html"), "table").headers == ("B" * 24,)


def test_hostile_headers_never_raw_and_no_data():
    lines = render_table_outline(table_outline(load("hostile.html"), "table.prices"))
    text = "\n".join(lines)
    assert text.isascii() and all(ch == "\n" or 32 <= ord(ch) < 127 for ch in text)
    assert "SECRETROW" not in text and "Other page text" not in text
    assert "Pri" in text and "\x1b" not in text and "A" * 24 in text and "A" * 25 not in text


def test_no_match_and_garbage_never_raise():
    assert table_outline(b"<p>x</p>", "table").matched == 0
    assert render_table_outline(table_outline(b"<p>x</p>", "table")) == ("tables matched: 0",)
    assert table_outline(object(), "[[[").ok is False
    assert render_table_outline(table_outline(None, "table")) in ((), ("tables matched: 0",))


def test_ten_thousand_cells_and_5000_char_header_stay_bounded():
    from data_integration.parse import parse_table

    cells = "".join(f"<th>H{i}</th>" for i in range(10000))
    page = f"<table><tr>{cells}</tr><tr>{'<td>1</td>' * 10000}</tr></table>".encode()
    o = table_outline(page, "table", parse_table(page, "table"))
    assert (o.cols, len(o.headers), o.extra) == (10000, 12, 9988)
    long = f"<table><tr><th>{'Z' * 5000}</th><th>ok</th></tr><tr><td>1</td><td>2</td></tr></table>".encode()
    lines = render_table_outline(table_outline(long, "table", parse_table(long, "table")))
    assert all(len(x) < 100 for x in lines) and "Z" * 24 in "".join(lines) and "Z" * 25 not in "".join(lines)
