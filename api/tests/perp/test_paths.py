"""Perp path resolution (call-time root) and synthetic fixture shape."""
from __future__ import annotations

import json
from pathlib import Path

from api.data import cache
from api.data.perp import paths

FIXTURE = Path(__file__).parent / "fixtures" / "hl_snapshot.json"


def test_perp_root_follows_env_at_call_time(tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_PERP_ROOT", str(tmp_path / "elsewhere"))
    assert paths.perp_root() == tmp_path / "elsewhere"


def test_perp_root_defaults_under_cache_root(tmp_path, monkeypatch):
    monkeypatch.delenv("SCREENER_PERP_ROOT", raising=False)
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
    assert paths.perp_root() == tmp_path / "perp"


def test_hl_snapshot_path_is_coin_and_month_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_PERP_ROOT", str(tmp_path))
    assert paths.hl_snapshot_path("btc", "2026-01") == tmp_path / "hl_snapshot" / "BTC" / "2026-01.jsonl"


def test_fixture_is_synthetic_list_of_two_with_btc_and_eth():
    wrapper = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert wrapper["_synthetic"] is True
    for key in ("response", "response_eth_null"):
        meta, contexts = wrapper[key]
        names = [a["name"] for a in meta["universe"]]
        assert names.index("BTC") == 1 and names.index("ETH") == 2
        assert len(contexts) == len(names)
    eth_null = wrapper["response_eth_null"][1][2]
    assert eth_null["premium"] is None and eth_null["midPx"] is None and eth_null["impactPxs"] is None
