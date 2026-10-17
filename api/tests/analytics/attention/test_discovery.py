"""S-F1: Discovery rules on fixtures. Store only; every path redirected to tmp_path."""
from __future__ import annotations

import json
from datetime import timedelta

from api.analytics.attention import discovery as disc, score as score_mod, universe as universe_mod
from api.data.attention import categories_store, registry, store, universe_store
from api.data.attention.types import SourceSeries
from api.tests.analytics.attention.conftest import SOURCES, TODAY, write_configs

END = TODAY - timedelta(days=1)
CATS = [{"id": "ai", "name": "AI"}, {"id": "defi", "name": "DeFi"}]


def put_change(source, symbol, recent, base, days=130, lag=0):
    """Completed days ending `lag` days before yesterday: `base` before the last 7 days, `recent` in them."""
    pts = [(END - timedelta(days=lag + days - 1 - i), recent if i >= days - 7 else base) for i in range(days)]
    store.write_series(SourceSeries(source, symbol, pts, "ok"), today=TODAY)


def cfg(tmp_path, **over):
    base = {"min_volume_24h_usd": 20_000_000, "exclude": ["BNB"], "exclude_category_ids": ["cex"],
            "min_independent_sources": 2, "winsor_percentile": 95, "recent_days": 7,
            "max_source_lag_days": 3,
            "source_groups": {}, "categories": CATS}
    base.update(over)
    p = tmp_path / "discovery.json"
    p.write_text(json.dumps(base))
    return p


def world(tmp_path, monkeypatch, coins, cats=None, **over):
    """coins: {SYM: volume}; cats: {category id: [SYM]} (None = no categories snapshot)."""
    probe, w, u = write_configs(tmp_path, reference=())
    monkeypatch.setattr(registry, "PROBE_RECORDS_PATH", probe)
    monkeypatch.setattr(score_mod, "WEIGHTS_PATH", w)
    monkeypatch.setattr(universe_mod, "UNIVERSE_PATH", u)
    monkeypatch.setattr(disc, "CONFIG_PATH", cfg(tmp_path, **over))
    rows = [{"id": s.lower(), "symbol": s, "market_cap": 1000 - i, "volume_24h": v}
            for i, (s, v) in enumerate(coins.items())]
    universe_store.write_snapshot("2026-10-15", rows)
    if cats is not None:
        names = {c["id"]: c["name"] for c in CATS}
        categories_store.write_snapshot("2026-10-15", [
            {"id": k, "name": names.get(k, k), "symbols": v} for k, v in cats.items()])


def cat(res, cid):
    return next(c for c in res.categories if c.id == cid)


def coin(res, cid, sym):
    return next(c for c in cat(res, cid).coins if c.symbol == sym)


def gain(sym, n=3, factor=2.0):
    for s in SOURCES[:n]:
        put_change(s, sym, factor, 1.0)


def test_categories_missing_is_not_ok(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats=None)
    res = disc.build_discovery(30, today=TODAY)
    assert (res.status, res.reason, res.categories) == ("no-data", "categories-missing", [])


def test_universe_missing(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    (isolated_cache / "attention" / "universe.json").unlink()
    res = disc.build_discovery(30, today=TODAY)
    assert (res.status, res.reason) == ("no-data", "reference-missing")


def test_exclusion_list_and_stablecoins(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "BNB": 5e7, "USDT": 5e7}, cats={"ai": ["A", "BNB", "USDT"]})
    for s in ("A", "BNB", "USDT"):
        gain(s)
    res = disc.build_discovery(30, today=TODAY)
    assert [c.symbol for c in cat(res, "ai").coins] == ["A"]


def test_exclusion_by_category_tag(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "T": 5e7}, cats={"ai": ["A", "T"], "cex": ["T"]})
    gain("A"), gain("T")
    res = disc.build_discovery(30, today=TODAY)
    assert [c.symbol for c in cat(res, "ai").coins] == ["A"]
    assert all(c.id != "cex" for c in res.categories)


def test_volume_floor(isolated_cache, tmp_path, monkeypatch):
    coins = {"LOW": 19_999_999, "EDGE": 20_000_000, "HIGH": 9e8}
    world(tmp_path, monkeypatch, coins, cats={"ai": list(coins)})
    for s in coins:
        gain(s)
    res = disc.build_discovery(30, today=TODAY)
    assert sorted(c.symbol for c in cat(res, "ai").coins) == ["EDGE", "HIGH"]


def test_unknown_volume_is_excluded(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": None, "B": 5e7}, cats={"ai": ["A", "B"]})
    gain("A"), gain("B")
    assert [c.symbol for c in cat(disc.build_discovery(30, today=TODAY), "ai").coins] == ["B"]


def test_gaining_needs_two_sources(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"ONE": 5e7, "TWO": 5e7, "ZERO": 5e7}, cats={"ai": ["ONE", "TWO", "ZERO"]})
    put_change("wikipedia", "ONE", 2.0, 1.0)
    put_change("coingecko", "ONE", 0.5, 1.0)
    put_change("trends", "ONE", 0.5, 1.0)
    put_change("wikipedia", "TWO", 2.0, 1.0)
    put_change("coingecko", "TWO", 2.0, 1.0)
    put_change("trends", "TWO", 0.5, 1.0)
    for s in SOURCES:
        put_change(s, "ZERO", 0.5, 1.0)
    res = disc.build_discovery(30, today=TODAY)
    assert coin(res, "ai", "ONE").gaining is False and coin(res, "ai", "ONE").sources_gaining == 1
    assert coin(res, "ai", "TWO").gaining is True and coin(res, "ai", "TWO").sources_gaining == 2
    assert coin(res, "ai", "ZERO").gaining is False
    assert cat(res, "ai").gaining_count == 1


def test_sources_in_one_group_count_once(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]},
          source_groups={"coingecko": "volume", "trends": "volume"})
    put_change("wikipedia", "A", 0.5, 1.0)
    put_change("coingecko", "A", 2.0, 1.0)
    put_change("trends", "A", 2.0, 1.0)
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    assert c.sources_gaining == 1 and c.gaining is False


def test_coin_with_one_source_is_not_used(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]})
    gain("A")
    put_change("wikipedia", "B", 9.0, 1.0)
    c = cat(disc.build_discovery(30, today=TODAY), "ai")
    assert c.coins_used == 1 and [x.symbol for x in c.coins] == ["A"]


def test_mean_median_and_coins_used(isolated_cache, tmp_path, monkeypatch):
    coins = {"A": 5e7, "B": 5e7, "C": 5e7}
    world(tmp_path, monkeypatch, coins, cats={"ai": list(coins)}, winsor_percentile=100)
    for s, f in (("A", 1.1), ("B", 1.2), ("C", 2.0)):
        gain(s, factor=f)
    c = cat(disc.build_discovery(30, today=TODAY), "ai")
    assert c.coins_used == 3
    assert round(c.score, 2) == round((10 + 20 + 100) / 3, 2)
    assert round(c.median, 2) == 20.0


def test_winsorized_at_p95(isolated_cache, tmp_path, monkeypatch):
    coins = {f"C{i:02d}": 5e7 for i in range(20)}
    world(tmp_path, monkeypatch, coins, cats={"ai": list(coins)})
    for i, s in enumerate(coins):
        gain(s, factor=51.0 if i == 19 else 1.0 + 0.01 * (i + 1))  # C19: raw change 5000 percent
    c = cat(disc.build_discovery(30, today=TODAY), "ai")
    top = coin(disc.build_discovery(30, today=TODAY), "ai", "C19")
    assert top.raw_change == 5000.0
    assert top.change < top.raw_change
    # p95 of 20 values, linear interpolation: between the 19th and 20th sorted value
    others = sorted(0.01 * (i + 1) * 100 for i in range(19))
    assert round(top.change, 3) == round(others[-1] + 0.05 * (5000.0 - others[-1]), 3)
    assert c.score < sum(x.raw_change for x in c.coins) / 20


def test_coin_counts_in_each_category_and_no_total(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"], "defi": ["A"]})
    gain("A"), gain("B")
    res = disc.build_discovery(30, today=TODAY)
    assert coin(res, "ai", "A").symbol == coin(res, "defi", "A").symbol == "A"
    assert cat(res, "defi").coins_used == 1 and cat(res, "ai").coins_used == 2
    assert not any(k in res.model_dump() for k in ("total", "score", "overall"))


def test_ranked_by_momentum_desc(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A"], "defi": ["B"]})
    gain("A", factor=1.2), gain("B", factor=3.0)
    assert [c.id for c in disc.build_discovery(30, today=TODAY).categories] == ["defi", "ai"]


def test_category_without_usable_coins_has_no_score(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"], "defi": []})
    gain("A")
    d = cat(disc.build_discovery(30, today=TODAY), "defi")
    assert (d.score, d.median, d.coins_used) == (None, None, 0)


def test_no_attention_data(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    res = disc.build_discovery(30, today=TODAY)
    assert (res.status, res.reason) == ("no-data", "no-attention-data")


def test_window_changes_baseline(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    for s in SOURCES[:2]:
        put_change(s, "A", 2.0, 1.0)
    for w in (7, 30, 90):
        assert disc.build_discovery(w, today=TODAY).window == w


def test_shipped_config_keeps_bnb_excludes_other_exchange_tokens():
    cfg = json.loads(disc.CONFIG_PATH.read_text())
    uni = json.loads(universe_mod.UNIVERSE_PATH.read_text())
    assert "BNB" not in cfg["exclude"] and "BNB" not in uni["exchange_tokens"]
    assert "BNB" in cfg["include_despite_category"]
    for s in ("LEO", "OKB", "CRO", "GT", "KCS", "BGB", "MX"):
        assert s in cfg["exclude"] and s in uni["exchange_tokens"]


def test_bnb_eligible_despite_exchange_category_but_leo_excluded(isolated_cache, tmp_path, monkeypatch):
    coins = {"BNB": 5e7, "LEO": 5e7}
    world(tmp_path, monkeypatch, coins, cats={"ai": ["BNB", "LEO"], "cex": ["BNB", "LEO"]},
          exclude=["LEO"], include_despite_category=["BNB"])
    for s in coins:
        gain(s)
    res = disc.build_discovery(30, today=TODAY)
    assert [c.symbol for c in cat(res, "ai").coins] == ["BNB"]


def test_lagging_sources_are_anchored_to_their_own_newest_day(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0, lag=2)
    put_change("coingecko", "A", 2.0, 1.0, lag=1)
    res = disc.build_discovery(30, today=TODAY)
    assert res.status == "ok"
    c = coin(res, "ai", "A")
    assert c.sources_used == 2 and c.gaining is True and round(c.raw_change, 2) == 100.0


def test_source_lagging_beyond_limit_is_not_used(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0, lag=4)
    put_change("coingecko", "A", 2.0, 1.0, lag=1)
    res = disc.build_discovery(30, today=TODAY)
    assert (res.status, res.reason) == ("no-data", "no-attention-data")


def test_source_lagging_exactly_at_limit_is_used(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0, lag=3)
    put_change("coingecko", "A", 2.0, 1.0)
    assert coin(disc.build_discovery(30, today=TODAY), "ai", "A").sources_used == 2


def test_lag_limit_comes_from_config(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, max_source_lag_days=1)
    put_change("wikipedia", "A", 2.0, 1.0, lag=2)
    put_change("coingecko", "A", 2.0, 1.0)
    assert disc.build_discovery(30, today=TODAY).status == "no-data"


def test_shipped_config_lag_limit_is_sane():
    assert 1 <= json.loads(disc.CONFIG_PATH.read_text())["max_source_lag_days"] <= 7
