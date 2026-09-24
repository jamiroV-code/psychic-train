"""Narrative dashboard RFC-3: GET /api/narrative/history through the real app.

Seeds the cache with the real writers under `isolated_cache`; every provider
fetch is monkeypatched to raise, proving the endpoint is a pure read.
"""
from __future__ import annotations

import gzip
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.data import cache, coingecko_adapter, hyperliquid_narrative_adapter, pytrends_adapter, reddit_adapter
from api.main import app
from api.routers import narrative as narrative_router

URL = "/api/narrative/history"
SEEDS = {"ai": "AI crypto", "rwa": "RWA crypto", "l2s": "layer 2 crypto", "memecoins": "memecoin"}


def _day(offset: int) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=offset)).isoformat()


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("/history must not fetch a provider")
    monkeypatch.setattr(pytrends_adapter, "fetch_trend", boom)
    monkeypatch.setattr(reddit_adapter, "fetch_mentions", boom)
    monkeypatch.setattr(coingecko_adapter, "fetch_trending", boom)
    monkeypatch.setattr(hyperliquid_narrative_adapter, "fetch_daily_market_snapshot", boom)


@pytest.fixture
def seeded(isolated_cache, no_network):
    for n, (cid, kw) in enumerate(SEEDS.items()):
        for off in range(-10, 1):
            cache.write_narrative_point("pytrends", kw, _day(off), float(10 + off * (n + 1)))
            cache.write_narrative_point("reddit", kw, _day(off), float(5 + (off % 3) + n))
            cache.write_narrative_point("coingecko", cid, _day(off), 0.0)
    return isolated_cache


def _cat(body, cid):
    return next(c for c in body["categories"] if c["category_id"] == cid)


def _files(root):
    return sorted(str(p) for p in root.rglob("*") if p.is_file())


class TestShape:
    def test_full_response_shape(self, seeded):
        resp = TestClient(app).get(URL)
        assert resp.status_code == 200
        body = resp.json()
        assert [c["category_id"] for c in body["categories"]] == list(SEEDS)
        assert body["grid_dates"] == sorted(set(body["grid_dates"]))
        grid = set(body["grid_dates"])
        for c in body["categories"]:
            for s in c["series"]:
                assert isinstance(s["redistributable"], bool)
                assert {p["date"] for p in s["points"]} <= grid
            assert {p["date"] for p in c["composite"]["points"]} <= grid
            assert c["composite"]["status"] == "ok"
        assert body["redistributable_all"] is False
        assert body["comparison"]["as_of"] == _day(0)
        assert all(e["rank"] is not None for e in body["comparison"]["entries"])
        ch = body["change_in_attention"]
        assert ch["window_days"] == 7 and all(e["status"] == "ok" for e in ch["entries"])

    def test_legacy_coingecko_labelled_and_excluded(self, seeded):
        cg = next(s for s in _cat(TestClient(app).get(URL).json(), "ai")["series"] if s["source"] == "coingecko")
        assert "legacy-map" in cg["label"] and cg["in_composite"] is False

    def test_pytrends_variants_listed_separately(self, seeded):
        srcs = [(s["source"], s["variant"]) for s in _cat(TestClient(app).get(URL).json(), "ai")["series"]]
        assert ("pytrends", "nightly-7d") in srcs and ("pytrends", "backfill-269d") in srcs

    def test_narrative_only_coins(self, seeded):
        coins = {c["symbol"]: c["narrative_only"] for c in _cat(TestClient(app).get(URL).json(), "l2s")["coins"]}
        assert coins["ETH"] is False and coins["ARB"] is True


class TestParams:
    def test_category_filter(self, seeded):
        body = TestClient(app).get(URL, params={"categories": "ai, l2s"}).json()
        assert [c["category_id"] for c in body["categories"]] == ["ai", "l2s"]
        assert {e["category_id"] for e in body["comparison"]["entries"]} == {"ai", "l2s"}

    def test_start_end_filter(self, seeded):
        body = TestClient(app).get(URL, params={"start": _day(-2), "end": _day(-1)}).json()
        assert body["grid_dates"] == [_day(-2), _day(-1)]
        assert body["comparison"]["as_of"] == _day(-1)

    @pytest.mark.parametrize("params", [
        {"categories": "ai,nope"},
        {"categories": "../../secrets"},
        {"categories": " , "},
        {"start": "2026-09-10", "end": "2026-09-01"},
        {"start": "not-a-date"},
        {"end": "2026-13-40"},
    ])
    def test_bad_params_422(self, seeded, params):
        assert TestClient(app).get(URL, params=params).status_code == 422


class TestDegradation:
    def test_one_source_down_others_unaffected(self, isolated_cache, no_network):
        for off in range(-3, 1):
            cache.write_narrative_point("pytrends", "AI crypto", _day(off), float(off))
            cache.write_narrative_point("reddit", "AI crypto", _day(off), float(-off))
        full = _cat(TestClient(app).get(URL).json(), "ai")
        (isolated_cache / "narrative" / "reddit" / "AI crypto.parquet").unlink()
        cache.write_narrative_point("coingecko-narrative", "ai", _day(0), 1.0)
        cache.write_narrative_point("coingecko-narrative", "ai", _day(-1), 0.0)
        resp = TestClient(app).get(URL)
        assert resp.status_code == 200
        ai = _cat(resp.json(), "ai")
        reddit = next(s for s in ai["series"] if s["source"] == "reddit")
        assert reddit["status"] == "unavailable" and reddit["points"] == []
        py = lambda c: next(s for s in c["series"] if s["variant"] == "nightly-7d")["points"]
        assert py(ai) == py(full)
        assert [p["date"] for p in ai["composite"]["points"]] == [_day(-1), _day(0)]

    def test_empty_cache_never_500(self, isolated_cache, no_network):
        resp = TestClient(app).get(URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["grid_dates"] == []
        for c in body["categories"]:
            assert c["composite"]["status"] == "unavailable" and c["composite"]["points"] == []
            assert all(s["status"] == "unavailable" for s in c["series"])
        assert {e["reason"] for e in body["comparison"]["entries"]} == {"no-composite-data"}

    def test_read_only_no_cache_writes(self, seeded):
        before = _files(seeded)
        assert TestClient(app).get(URL).status_code == 200
        assert _files(seeded) == before


class TestTransport:
    def test_gzip(self, seeded):
        resp = TestClient(app).get(URL, headers={"Accept-Encoding": "gzip"})
        assert resp.headers.get("content-encoding") == "gzip"
        assert resp.json()["categories"]  # httpx decodes transparently
        assert gzip  # imported for clarity of intent

    def test_get_history_is_separate_from_get_categories(self):
        import inspect
        src = inspect.getsource(narrative_router.get_categories)
        assert "history" not in src
        assert "assemble_narrative_categories" not in inspect.getsource(narrative_router.get_history)
