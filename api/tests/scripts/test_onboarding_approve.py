"""T223 O5: approval prints a placement, never edits owner or bot data."""
import io
import json
import socket

import pytest

from api.data import cache
from api.data.attention import coin_ledger, onboarding_store as ob
from api.scripts import onboarding_approve as approve


@pytest.fixture
def approval_world(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path / "cache")
    def boom(*args, **kwargs):
        raise AssertionError("no network")
    monkeypatch.setattr(socket.socket, "connect", boom)
    ledger = coin_ledger.empty()
    ledger["coins"]["new"] = coin_ledger._entry({"symbol": "ZZNEW"}, "2026-11-01", state="member", count=14,
                                               cls="normal")
    ob.write_ledger(ledger)
    ob.write_json("attention_queries_auto.json", {"entries": {"ZZNEW": {"name": "New Coin", "cashtag_only": True}}})
    ob.write_json("trends_keywords_auto.json", {"entries": {"ZZNEW": {"topic": "/g/new_coin", "label": "New Coin"}}})
    return ledger


def invoke(symbol="ZZNEW", narrative="defi"):
    out, err = io.StringIO(), io.StringIO()
    code = approve.main([symbol, narrative], out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_approve_prints_paste_ready_placement_without_writing(approval_world):
    before = {p: p.read_bytes() for p in ob.root().rglob("*.json")}
    code, out, _ = invoke()
    assert code == 0
    assert json.loads(out.splitlines()[-1]) == {"symbol": "ZZNEW", "primary": True}
    assert "defi" in out and "test_narratives" in out
    assert before == {p: p.read_bytes() for p in ob.root().rglob("*.json")}


@pytest.mark.parametrize("source", ["attention_queries_auto.json", "trends_keywords_auto.json"])
def test_approve_requires_both_source_entries(approval_world, source):
    ob.write_json(source, {"entries": {}})
    assert invoke()[0] == 2


def test_approve_requires_membership(approval_world):
    approval_world["coins"]["new"]["state"] = "watching"
    ob.write_ledger(approval_world)
    assert invoke()[0] == 2


@pytest.mark.parametrize("symbol,narrative", [("BAD\n", "defi"), ("ZZNEW", "../defi"), ("ZZNEW", "missing")])
def test_hostile_or_unknown_arguments_are_refused(approval_world, symbol, narrative):
    assert invoke(symbol, narrative)[0] == 2
