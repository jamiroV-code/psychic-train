"""Narrative-v2 RFC-5: GET /api/narrative/mindshare through the real app."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api.data import cache, coingecko_adapter, hyperliquid_narrative_adapter, pytrends_adapter, reddit_adapter
from api.main import app

URL = "/api/narrative/mindshare"


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("/mindshare must not fetch a provider")
    monkeypatch.setattr(pytrends_adapter, "fetch_trend", boom)
    monkeypatch.setattr(reddit_adapter, "fetch_mentions", boom)
    monkeypatch.setattr(coingecko_adapter, "fetch_trending", boom)
    monkeypatch.setattr(hyperliquid_narrative_adapter, "fetch_daily_market_snapshot", boom)


def test_empty_cache_no_sources_available(isolated_cache, no_network):
    body = TestClient(app).get(URL).json()
    assert body["date"] is None and body["no_sources_available"] is True
    assert body["entries"] and all(e["status"] == "excluded" and e["mindshare"] is None for e in body["entries"])


def test_default_latest_day_and_explicit_date(isolated_cache, no_network):
    today = date.today()
    y = (today - timedelta(days=1)).isoformat()
    cache.write_narrative_point("coingecko-narrative", "ai", y, 3.0)
    cache.write_narrative_point("coingecko-narrative", "rwa", y, 1.0)
    cache.write_narrative_point("coingecko-narrative", "ai", today.isoformat(), 1.0)
    cache.write_narrative_point("coingecko-narrative", "rwa", today.isoformat(), 1.0)
    c = TestClient(app)
    body = c.get(URL).json()
    assert body["date"] == today.isoformat() and body["only_one_source"] is True
    assert body["available_dates"] == [y, today.isoformat()]
    body = c.get(URL, params={"date": y}).json()
    by = {e["category_id"]: e for e in body["entries"]}
    assert by["ai"]["mindshare"] == pytest.approx(0.75)
    assert by["ai"]["sources"] == {"pytrends": None, "coingecko": 0.75, "reddit": None}


def test_bad_date_is_422(isolated_cache, no_network):
    assert TestClient(app).get(URL, params={"date": "not-a-date"}).status_code == 422
