"""provenance.py: <dataset>.provenance.json beside the data; atomic append; survives cache.write_ohlcv."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from api.data import cache
from data_integration.approvals import ApprovalStore
from data_integration.gate import request_access
from data_integration.normalise import normalise
from data_integration.parse import parse_table
from data_integration.provenance import append_record, build_record, provenance_path, read_records
from data_integration.store_writer import write_series

from _helpers import fixed_clock, make_record

FIX = Path(__file__).parent / "fixtures"
URL = "https://a.example.test/data/prices"


def _pass(tmp_path):
    store = ApprovalStore(tmp_path / "ap")
    store.write(make_record())
    p = request_access("example-src", 2, store, fixed_clock())
    assert not hasattr(p, "reason")
    return p


def _df():
    return normalise(parse_table((FIX / "ok.html").read_text(), "table.prices"), "synthetic")


def test_path_is_beside_data_file():
    p = provenance_path("BTC-HIST", "1d")
    assert p.parent == cache.ohlcv_path("BTC-HIST", "1d").parent
    assert p.name == "1d.provenance.json"


def test_record_copies_approval_facts(tmp_path):
    rec = build_record(_pass(tmp_path), URL, _df(), datetime(2026, 1, 10, 12, tzinfo=timezone.utc))
    assert rec["source"] == "example-src"
    assert rec["tier"] == 2
    assert rec["hosts"] == ["a.example.test"]
    assert rec["pages"] == ["/data/"]
    assert rec["url"] == URL
    assert rec["rows"] == 4
    assert rec["fetched_at"] == "2026-01-10T12:00:00Z"
    assert len(rec["content_sha256"]) == 64


def test_append_keeps_earlier_records_and_leaves_no_temp(tmp_path):
    append_record("BTC-HIST", "1d", {"n": 1})
    append_record("BTC-HIST", "1d", {"n": 2})
    assert read_records("BTC-HIST", "1d") == [{"n": 1}, {"n": 2}]
    assert [p.name for p in provenance_path("BTC-HIST", "1d").parent.iterdir() if p.name.endswith(".tmp")] == []


def test_write_ohlcv_afterwards_leaves_provenance_intact():
    write_series("BTC-HIST", "1d", _df())
    append_record("BTC-HIST", "1d", {"n": 1})
    before = provenance_path("BTC-HIST", "1d").read_bytes()
    cache.write_ohlcv("BTC-HIST", "1d", _df())
    assert provenance_path("BTC-HIST", "1d").read_bytes() == before
    assert len(cache.read_ohlcv("BTC-HIST", "1d")) == 4
