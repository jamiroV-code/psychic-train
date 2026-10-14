"""parse.py: explicit table helper over the Scrapling Selector; no fetch-tier code is loaded."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from data_integration.parse import ParseError, parse_table

FIX = Path(__file__).parent / "fixtures"


def test_parse_table_reads_header_and_rows():
    t = parse_table((FIX / "ok.html").read_text(), "table.prices")
    assert t.columns == ("Date", "Open", "High", "Low", "Close", "Volume")
    assert len(t.rows) == 4
    assert t.rows[0] == ("2025-01-01", "100", "110", "95", "105", "1000")


def test_parse_table_accepts_bytes():
    assert len(parse_table((FIX / "ok.html").read_bytes(), "table.prices").rows) == 4


def test_parse_table_missing_selector_raises():
    with pytest.raises(ParseError):
        parse_table((FIX / "no_table.html").read_text(), "table.prices")


def test_parse_table_changed_layout_no_direct_match():
    with pytest.raises(ParseError):
        parse_table((FIX / "changed.html").read_text(), "table.prices")


@pytest.mark.parametrize("mod", ["data_integration.parse", "data_integration.adaptive"])
def test_import_leaves_fetch_clients_out_of_sys_modules(mod):
    code = (
        f"import sys, {mod}\n"
        "bad = [m for m in ('curl_cffi', 'playwright', 'patchright', 'scrapling.fetchers', 'scrapling.engines') if m in sys.modules]\n"
        "assert not bad, bad\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
