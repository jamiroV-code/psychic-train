"""T223 O6: read-only onboarding rows from an isolated cache, no provider calls."""
import socket

import httpx
import pytest

from api.analytics.attention import onboarding
from api.data.attention import coin_ledger, onboarding_store as ob


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("onboarding must not reach the network")
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom)


def test_no_ledger_and_corrupt_ledger(isolated_cache):
    assert onboarding.build().status == "no-ledger"
    ob.ledger_path().parent.mkdir(parents=True, exist_ok=True)
    ob.ledger_path().write_text("{broken")
    assert onboarding.build().status == "corrupt"
    assert ob.ledger_path().read_text() == "{broken"


def test_fixture_rows_names_pending_missing_proposals_and_no_writes(isolated_cache):
    led = coin_ledger.empty()
    led["last_advanced_date"] = "2026-11-01"
    led["coins"]["new"] = coin_ledger._entry({"symbol": "ZZNEW"}, "2026-11-01", state="watching", count=3)
    led["coins"]["new"]["class_evidence"] = {"reason": "no categories"}
    ob.write_ledger(led)
    ob.write_json("wiki_articles_auto.json", {"entries": {"ZZNEW": {"title": "New Coin"}}})
    ob.write_json("pending.json", {"coins": {"ZZNEW": {"trends": {"reason": "volume history 20 of 66 days", "evidence": {}}}}})
    ob.write_json("narrative_proposals.json", {"coins": {"ZZNEW": [{"narrative": "defi", "category": "cat"}]}})
    before = {p: p.read_bytes() for p in ob.root().rglob("*.json")}
    payload = onboarding.build().model_dump(by_alias=True)
    assert payload["mode"] == "shadow" and payload["as_of"] == "2026-11-01"
    row = payload["coins"][0]
    assert (row["symbol"], row["state"], row["days_in_top100"], row["class"]) == ("ZZNEW", "watching", 3, "unknown")
    assert row["sources"]["wikipedia"] == {"state": "name", "value": "New Coin", "reason": ""}
    assert row["sources"]["trends"]["state"] == "pending"
    assert row["sources"]["reddit_x"]["value"] is None
    assert row["sources"]["reddit_x"]["state"] == "missing"
    assert row["pending"][0]["source"] == "trends" and row["proposal"][0]["narrative"] == "defi"
    assert before == {p: p.read_bytes() for p in ob.root().rglob("*.json")}


def test_nothing_pending_is_an_empty_list(isolated_cache):
    led = coin_ledger.empty()
    led["coins"]["new"] = coin_ledger._entry({"symbol": "ZZNEW"}, "2026-11-01", state="inactive", count=0)
    ob.write_ledger(led)
    assert onboarding.build().coins[0].pending == []
