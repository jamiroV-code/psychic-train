"""Narrative-v2 RFC-4: GET /api/narrative/momentum through the real app."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api.data import cache, coingecko_adapter, hyperliquid_narrative_adapter, pytrends_adapter, reddit_adapter
from api.main import app

URL = "/api/narrative/momentum"


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("/momentum must not fetch a provider")
    monkeypatch.setattr(pytrends_adapter, "fetch_trend", boom)
    monkeypatch.setattr(reddit_adapter, "fetch_mentions", boom)
    monkeypatch.setattr(coingecko_adapter, "fetch_trending", boom)
    monkeypatch.setattr(hyperliquid_narrative_adapter, "fetch_daily_market_snapshot", boom)


def _seed_blended(cid, values):
    today = date.today()
    for i, v in enumerate(values):
        cache.write_narrative_point("pytrends-blended", cid, (today - timedelta(days=len(values) - 1 - i)).isoformat(),
                                    float(v))


def test_empty_cache_every_narrative_explicitly_insufficient(isolated_cache, no_network):
    body = TestClient(app).get(URL).json()
    assert body["window_days"] == 7 and body["acceleration_window_days"] == 14
    assert body["entries"]
    for e in body["entries"]:
        assert e["status"] == "insufficient" and e["momentum_basis"] == "insufficient"
        assert e["change"] is None and e["rank"] is None and e["reason"]


def test_ranked_vs_the_field_with_basis_disclosed(isolated_cache, no_network):
    _seed_blended("ai", [i for i in range(15)])          # steady rise
    _seed_blended("rwa", [14 - i for i in range(15)])    # steady fall
    body = TestClient(app).get(URL).json()
    by = {e["category_id"]: e for e in body["entries"]}
    assert by["ai"]["rank"] == 1 and by["ai"]["direction"] == "up"
    assert by["rwa"]["rank"] == 2 and by["rwa"]["direction"] == "down"
    assert by["ai"]["momentum_basis"] == "pytrends-blended"
    assert by["ai"]["change"] == pytest.approx(0.5)  # 7 of 14 normalised steps
    assert body["entries"][0]["category_id"] == "ai"
    assert all(e["rank"] is None for e in body["entries"] if e["category_id"] not in ("ai", "rwa"))
