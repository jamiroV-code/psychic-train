"""P5 fix pack: shipped config vs fetchers (F-1), breadth window (F-2), unreadable store file (F-3)."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest

from api.analytics.attention import basket as basket_mod, discovery as disc, score as score_mod
from api.analytics.attention.basket import build_attention
from api.data.attention import registry, store
from api.tests.analytics.attention.conftest import SOURCES, TODAY, make_layout, put, put_refs, write_configs
from api.tests.analytics.attention.test_discovery import END, gain, world


def test_shipped_files_use_registry_source_names():
    weights = json.loads(score_mod.WEIGHTS_PATH.read_text())
    cfg = json.loads(disc.CONFIG_PATH.read_text())
    assert set(weights) <= set(registry.FETCHERS)
    assert set(cfg["source_groups"]) <= set(weights)
    assert set(registry.FETCHERS) == set(weights) | set(registry.EXCLUDED_SOURCES)
    assert not set(weights) & set(registry.EXCLUDED_SOURCES)
    assert weights["xsearch"] < weights["wikipedia"]


def test_volume_sources_stay_one_independence_group():
    cfg = json.loads(disc.CONFIG_PATH.read_text())
    assert cfg["source_groups"]["coingecko"] == cfg["source_groups"]["exchange_volume"]


def test_breadth_uses_the_selected_window(isolated_cache, tmp_path, monkeypatch):
    put_refs()
    for s in SOURCES:
        put(s, "A1", 2.5)
    end = TODAY - timedelta(days=1)
    by_day = {end: 50.0, end - timedelta(days=7): 30.0, end - timedelta(days=30): 80.0,
              end - timedelta(days=90): 80.0}
    real = basket_mod.ser.coin_score_at

    def fake(symbol, sources, weights, data, reference, day):
        return by_day.get(day, 60.0) if symbol == "A1" else real(symbol, sources, weights, data, reference, day)

    monkeypatch.setattr(basket_mod.ser, "coin_score_at", fake)
    layout = make_layout({"alpha": ["A1"]})
    probe, w, u = write_configs(tmp_path)
    got = {win: build_attention(win, layout=layout, today=TODAY, probe_path=probe, weights_path=w,
                                universe_path=u).baskets[0] for win in (7, 30, 90)}
    assert (got[7].breadth, got[7].change) == (1.0, pytest.approx(20.0))
    for win in (30, 90):
        assert got[win].change == pytest.approx(-30.0) and got[win].breadth == 0.0


def _garbage(source, symbol):
    path = store.store_path(source, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a parquet file")


def test_unreadable_store_file_is_unavailable(isolated_cache, tmp_path):
    _, _, _ = write_configs(tmp_path)
    probe = tmp_path / "probe_records.json"
    _garbage("wikipedia", "BAD")
    sr = registry.read_series("wikipedia", "BAD", TODAY, probe)
    assert sr.state == "unavailable" and sr.points == []


def test_baskets_attention_survives_garbage_file(isolated_cache, tmp_path):
    put_refs()
    for s in SOURCES:
        put(s, "A1", 2.5)
    _garbage("wikipedia", "BAD")
    probe, w, u = write_configs(tmp_path)
    body = build_attention(30, layout=make_layout({"alpha": ["A1", "BAD"]}), today=TODAY,
                           probe_path=probe, weights_path=w, universe_path=u)
    bad = next(c for c in body.baskets[0].coins if c.symbol == "BAD")
    assert bad.score is None
    assert next(x for x in bad.sources if x.source == "wikipedia").state == "unavailable"


def test_discovery_survives_garbage_file(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "BAD": 5e7}, cats={"ai": ["A", "BAD"]})
    gain("A")
    _garbage("wikipedia", "BAD")
    res = disc.build_discovery(30, today=TODAY)
    assert res.status == "ok"
