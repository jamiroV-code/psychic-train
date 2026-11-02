"""T223 O1/O4: onboarding store (ledger file, log, JSON helpers); everything under the isolated cache."""
from __future__ import annotations

import json

import pytest

from api.data.attention import coin_ledger as cl
from api.data.attention import onboarding_store as ob


def test_absent_ledger_reads_absent(isolated_cache):
    assert ob.read_ledger() == (None, "absent")


def test_write_then_read_round_trip_and_path(isolated_cache):
    doc = cl.empty()
    doc["coins"]["a"] = cl._entry({"symbol": "A"}, "2026-11-01", state="member", count=3,
                                 cls="normal", source="owner")
    ob.write_ledger(doc)
    assert (isolated_cache / "attention" / "onboarding" / "ledger.json").exists()
    assert ob.read_ledger() == (doc, "ok")
    assert not list((isolated_cache / "attention" / "onboarding").glob("*.tmp"))


@pytest.mark.parametrize("text", ["{nope", "[]", json.dumps({"coins": {"a": {"state": "boss"}}}),
                                  json.dumps({"last_advanced_date": None, "seeded_at": None, "coins": []})])
def test_corrupt_ledger_is_refused_and_kept(isolated_cache, text):
    p = isolated_cache / "attention" / "onboarding" / "ledger.json"
    p.parent.mkdir(parents=True)
    p.write_text(text)
    assert ob.read_ledger() == (None, "corrupt")
    assert p.read_text() == text


def test_size_cap_refuses_the_write_and_keeps_the_old_file(isolated_cache, monkeypatch):
    ob.write_ledger(cl.empty())
    before = ob.ledger_path().read_bytes()
    monkeypatch.setattr(ob, "MAX_LEDGER_BYTES", 10)
    doc = cl.empty()
    doc["coins"]["x" * 50] = {}
    with pytest.raises(ValueError, match="size cap"):
        ob.write_ledger(doc)
    assert ob.ledger_path().read_bytes() == before


def test_log_appends_and_strips_control_and_bidi_characters(isolated_cache):
    ob.append_log("2026-11-01", [{"source": "ledger", "action": "entered", "evidence": "a\x1b[31mb\u202ec\n" + "z" * 400}])
    ob.append_log("2026-11-01", [{"source": "ledger", "action": "joined", "evidence": "ok"}])
    doc = json.loads((isolated_cache / "attention" / "onboarding" / "log" / "2026-11-01.json").read_text())
    assert [e["action"] for e in doc["entries"]] == ["entered", "joined"]
    ev = doc["entries"][0]["evidence"]
    assert ev.startswith("a[31mbc") and len(ev) == ob.MAX_TEXT and "\u202e" not in ev and "\n" not in ev


def test_log_size_cap_drops_new_entries_and_marks_it(isolated_cache, monkeypatch):
    monkeypatch.setattr(ob, "MAX_LOG_ENTRIES", 2)
    ob.append_log("2026-11-01", [{"action": "a"}, {"action": "b"}, {"action": "c"}])
    doc = ob.read_log("2026-11-01")
    assert [e["action"] for e in doc["entries"]] == ["a", "b"] and doc["dropped"] == 1


def test_bad_log_date_is_refused(isolated_cache):
    with pytest.raises(ValueError):
        ob.append_log("../x", [])


def test_sanitize_nested_values():
    out = ob.sanitize({"k\x00": ["\u2066x\u2069", 1, None, {"y": "\x7f"}]})
    assert out == {"k": ["x", 1, None, {"y": ""}]}


def test_has_log_history(isolated_cache):
    assert not ob.has_log_history()
    ob.append_log("2026-11-01", [{"action": "seeded"}])
    assert ob.has_log_history()


@pytest.mark.parametrize("key,value", [
    ("consecutive_top100", "14"), ("consecutive_outside120", -1),
    ("consecutive_top100", True), ("class", "other"), ("class_evidence", []),
    ("class_source", "other"), ("seeded", 1), ("updated", "2026-02-30"),
    ("symbol", "BAD-SYMBOL"), ("resolver", {"trends": []}),
])
def test_malformed_values_are_corrupt_and_preserved(isolated_cache, key, value):
    doc = cl.empty()
    doc["coins"]["a"] = cl._entry({"symbol": "A"}, "2026-11-01", state="watching", count=1)
    doc["coins"]["a"][key] = value
    ob.write_ledger(doc)
    before = ob.ledger_path().read_bytes()
    assert ob.read_ledger() == (None, "corrupt")
    assert ob.ledger_path().read_bytes() == before


def test_oversized_ledger_read_is_refused(isolated_cache, monkeypatch):
    ob.write_ledger(cl.empty())
    before = ob.ledger_path().read_bytes()
    monkeypatch.setattr(ob, "MAX_LEDGER_BYTES", 10)
    assert ob.read_ledger() == (None, "corrupt")
    assert ob.ledger_path().read_bytes() == before
