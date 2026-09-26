"""RFC-1 (narrative dashboard) contract test — AC-1 / E5, option B.

`GET /api/narrative/categories` and `/screener`'s `narrative_state` must be
byte-identical before and after the curated narrative map
(`api/data/narrative_category_map.json`) lands — INCLUDING when a coin that
is mapped only in that new map shows up in CoinGecko's trending list.

The golden file `fixtures/narrative_categories_contract.json` was captured
against the pre-RFC-1 code (legacy 3-entry `COIN_CATEGORY_MAP` only). If a
future change makes this test fail, the curated map has leaked into the
trigger/screener path — that is an AC-1 break, not a snapshot to refresh.

Same SANDBOX NOTE as test_narrative.py: drives the exact assembly function
the router calls (`trigger.assemble_narrative_categories`) rather than a
TestClient.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from api.analytics import screener_board
from api.analytics.narrative import trigger
from api.data import cache, coingecko_adapter, pytrends_adapter, reddit_adapter

GOLDEN_PATH = Path(__file__).resolve().parent / "fixtures" / "narrative_categories_contract.json"
AS_OF = "2024-06-30"
SEED_IDS = ("ai", "rwa", "l2s", "memecoins")

# Legacy-only coins, plus coins mapped ONLY in the curated map (one or more
# per seed category) — the scenario that would expose trending_count drift.
TRENDING_SCENARIOS = {
    "legacy_only": ["ETH", "HYPE", "BTC", "SOMEUNMAPPED"],
    "with_newly_mapped": ["ETH", "HYPE", "ARB", "OP", "FET", "TAO", "ONDO", "LINK", "DOGE", "PEPE", "WIF"],
}
SCREENER_SYMBOLS = ("BTC", "ETH", "HYPE", "ARB", "FET", "ONDO", "DOGE", "SOMEUNMAPPED")


def _seed_history() -> None:
    # pytrends/reddit rows are keyed by each category's search keyword
    # (`keywords[0]`), exactly as the real adapters archive them; coingecko
    # is keyed by category id, as `trigger.py` archives it.
    keyword_by_id = {c["id"]: c["keywords"][0] for c in trigger.load_seed_categories()}
    start = date.fromisoformat(AS_OF) - timedelta(days=20)
    for i in range(20):
        d = (start + timedelta(days=i)).isoformat()
        for n, cat in enumerate(SEED_IDS):
            spike = 6.0 if (i >= 16 and n % 2 == 0) else 0.0
            keyword = keyword_by_id[cat]
            cache.write_narrative_point("pytrends", keyword, d, 10.0 + (i % 3) + spike * 3)
            cache.write_narrative_point("reddit", keyword, d, 5.0 + (i % 2) + spike)
            cache.write_narrative_point("coingecko", cat, d, float(i % 2))


def _run_scenario(symbols: list[str], monkeypatch, tmp_path: Path) -> dict:
    root = tmp_path / symbols[2]
    monkeypatch.setattr(cache, "CACHE_ROOT", root)
    cache.bootstrap_cache_dirs()
    _seed_history()
    monkeypatch.setattr(
        coingecko_adapter, "fetch_trending",
        lambda *a, **k: coingecko_adapter.TrendingResult(symbols=list(symbols), as_of=AS_OF, status="ok"),
    )
    monkeypatch.setattr(
        pytrends_adapter, "fetch_trend",
        lambda kw: pytrends_adapter.TrendResult(keyword=kw, value=1.0, as_of=AS_OF, status="ok"),
    )
    monkeypatch.setattr(
        reddit_adapter, "fetch_mentions",
        lambda q, *a, **k: reddit_adapter.MentionResult(query=q, mention_count=1.0, as_of=AS_OF, status="ok"),
    )

    categories = trigger.assemble_narrative_categories(as_of=AS_OF)
    by_id = {c.id: c for c in categories}
    coingecko_today = {
        cat: cache.read_narrative_series("coingecko", cat).set_index("date")["raw_value"].get(AS_OF)
        for cat in SEED_IDS
    }
    return {
        "categories": [c.model_dump(mode="json") for c in categories],
        "coingecko_cache_as_of": coingecko_today,
        "screener_narrative_state": {s: screener_board._coin_narrative_state(s, by_id) for s in SCREENER_SYMBOLS},
    }


def build_contract_snapshot(monkeypatch, tmp_path: Path) -> str:
    out = {name: _run_scenario(syms, monkeypatch, tmp_path) for name, syms in TRENDING_SCENARIOS.items()}
    return json.dumps(out, indent=2, sort_keys=True) + "\n"


class TestNarrativeCategoriesContract:
    def test_full_response_byte_identical_to_pre_rfc1_snapshot(self, monkeypatch, tmp_path):
        assert build_contract_snapshot(monkeypatch, tmp_path) == GOLDEN_PATH.read_text(encoding="utf-8")

    def test_newly_mapped_trending_coins_do_not_move_any_category(self, monkeypatch, tmp_path):
        snap = json.loads(build_contract_snapshot(monkeypatch, tmp_path))
        legacy, widened = snap["legacy_only"], snap["with_newly_mapped"]
        assert legacy["categories"] == widened["categories"]
        assert legacy["coingecko_cache_as_of"] == widened["coingecko_cache_as_of"]
        assert widened["coingecko_cache_as_of"]["l2s"] == 2.0  # ETH + HYPE only
        assert widened["coingecko_cache_as_of"]["ai"] == 0.0

    def test_screener_state_ignores_curated_only_mappings(self, monkeypatch, tmp_path):
        snap = json.loads(build_contract_snapshot(monkeypatch, tmp_path))
        states = snap["with_newly_mapped"]["screener_narrative_state"]
        for sym in ("ARB", "FET", "ONDO", "DOGE", "SOMEUNMAPPED"):
            assert states[sym] == "unmapped"
        assert states["BTC"] == "unavailable"  # legacy non-seed store-of-value
