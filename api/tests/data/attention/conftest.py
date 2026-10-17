"""Shared fixtures: mock HTTP only, no live provider call."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 16)


def wiki_payload(days: int, end: date = TODAY - timedelta(days=1)) -> dict:
    items = []
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        items.append({"timestamp": d.strftime("%Y%m%d") + "00", "views": 100 + i})
    return {"items": items}


def chart_payload(days: int, include_today: bool = True) -> dict:
    vols = []
    last = TODAY if include_today else TODAY - timedelta(days=1)
    for i in range(days):
        d = last - timedelta(days=days - 1 - i)
        ms = int(__import__("datetime").datetime(d.year, d.month, d.day, tzinfo=__import__("datetime").timezone.utc).timestamp() * 1000)
        vols.append([ms, 1000.0 + i])
    return {"total_volumes": vols}


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def markets_json():
    return json.loads((FIXTURES / "markets_top.json").read_text())


@pytest.fixture
def attention_cache(isolated_cache):
    return isolated_cache


@pytest.fixture(autouse=True)
def _no_real_pacing(monkeypatch):
    """Per-host pacing would really sleep in tests that use the default `sleep`."""
    from api.data.attention import coingecko_attention, http_retry, wikipedia
    monkeypatch.setattr(coingecko_attention, "PACER", http_retry.Pacer(0))
    monkeypatch.setattr(wikipedia, "PACER", http_retry.Pacer(0))
