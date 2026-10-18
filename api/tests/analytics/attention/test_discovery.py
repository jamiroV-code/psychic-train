"""S-F1: Discovery rules on fixtures. Store only; every path redirected to tmp_path."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest

from api.analytics.attention import discovery as disc, score as score_mod, universe as universe_mod
from api.data.attention import categories_store, registry, store, universe_store
from api.data.attention.types import SourceSeries
from api.tests.analytics.attention.conftest import SOURCES, TODAY, write_configs

END = TODAY - timedelta(days=1)
CATS = [{"id": "ai", "name": "AI"}, {"id": "defi", "name": "DeFi"}]
WEIGHTS = {"wikipedia": 25, "trends": 25, "reddit": 15, "xsearch": 10, "exchange_activity": 10,
           "github_dev": 8, "defillama": 7}
SUB = {"binance": 40, "coinbase": 25, "kraken": 15, "hyperliquid": 20}
PROBED = ("wikipedia", "coingecko", "trends", "reddit", "xsearch", "exchange_volume", "hyperliquid_volume",
          "coinbase_volume", "kraken_volume")


def put_change(source, symbol, recent, base, days=130, lag=0):
    """Completed days ending `lag` days before yesterday: `base` before the last 7 days, `recent` in them."""
    pts = [(END - timedelta(days=lag + days - 1 - i), recent if i >= days - 7 else base) for i in range(days)]
    store.write_series(SourceSeries(source, symbol, pts, "ok"), today=TODAY)


def cfg(tmp_path, **over):
    base = {"min_volume_24h_usd": 20_000_000, "exclude": ["BNB"], "exclude_category_ids": ["cex"],
            "source_weights": WEIGHTS, "exchange_sub_weights": SUB, "rising_threshold_pct": 10,
            "trigger_pct": 60, "min_covered_weight": 30, "min_history_days": 90,
            "winsor_percentile": 95, "recent_days": 7, "max_source_lag_days": 3, "categories": CATS}
    base.update(over)
    p = tmp_path / "discovery.json"
    p.write_text(json.dumps(base))
    return p


def world(tmp_path, monkeypatch, coins, cats=None, **over):
    """coins: {SYM: volume}; cats: {category id: [SYM]} (None = no categories snapshot)."""
    probe, w, u = write_configs(tmp_path, sources=PROBED, reference=())
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


def test_coin_with_one_source_is_scored_but_cannot_trigger(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]})
    gain("A")
    put_change("wikipedia", "B", 2.0, 1.0)
    c = cat(disc.build_discovery(30, today=TODAY), "ai")
    b = next(x for x in c.coins if x.symbol == "B")
    assert c.coins_used == 2 and (b.covered_weight, b.trigger, round(b.raw_change, 2)) == (25, False, 100.0)


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
    assert c.covered_weight == 35 and c.trigger is True and round(c.raw_change, 2) == 100.0


def test_source_lagging_beyond_limit_is_not_used(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0, lag=4)
    put_change("coingecko", "A", 2.0, 1.0, lag=4)
    res = disc.build_discovery(30, today=TODAY)
    assert (res.status, res.reason) == ("no-data", "no-attention-data")


def test_source_lagging_exactly_at_limit_is_used(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0, lag=3)
    put_change("coingecko", "A", 2.0, 1.0)
    assert coin(disc.build_discovery(30, today=TODAY), "ai", "A").covered_weight == 35


def test_lag_limit_comes_from_config(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, max_source_lag_days=1)
    put_change("wikipedia", "A", 2.0, 1.0, lag=2)
    put_change("coingecko", "A", 2.0, 1.0, lag=2)
    assert disc.build_discovery(30, today=TODAY).status == "no-data"


def test_shipped_config_lag_limit_is_sane():
    assert 1 <= json.loads(disc.CONFIG_PATH.read_text())["max_source_lag_days"] <= 7


# ---- T101 W1: weighted scoring ------------------------------------------------------------

def good(**over):
    return {"source_weights": dict(WEIGHTS), "exchange_sub_weights": dict(SUB), "rising_threshold_pct": 10,
            "trigger_pct": 60, "min_covered_weight": 30, "min_history_days": 90, **over}


def test_shipped_config_is_valid_and_sums_to_100():
    c = disc.load_config()
    assert sum(c["source_weights"].values()) == pytest.approx(100)
    assert sum(c["exchange_sub_weights"].values()) == pytest.approx(100)
    assert c["source_weights"] == WEIGHTS and c["exchange_sub_weights"] == SUB
    assert (c["rising_threshold_pct"], c["trigger_pct"], c["min_covered_weight"], c["min_history_days"]) == (
        10, 60, 30, 90)
    assert "min_independent_sources" not in c and "source_groups" not in c


def _sw(**kw):
    return {**WEIGHTS, **kw}


@pytest.mark.parametrize("over", [
    {"source_weights": _sw(wikipedia=-1, trends=51)},
    {"source_weights": _sw(wikipedia=24)},
    {"source_weights": _sw(wikipedia=25.02)},
    {"source_weights": {**WEIGHTS, "coingecko": 0}},
    {"source_weights": {**WEIGHTS, "exchange_volume": 0}},
    {"source_weights": {**WEIGHTS, "hyperliquid_volume": 0}},
    {"source_weights": {**WEIGHTS, "nonsense": 0}},
    {"exchange_sub_weights": {**SUB, "binance": 41}},
    {"exchange_sub_weights": {"binance": 101, "coinbase": -1}},
    {"exchange_sub_weights": {**SUB, "okx": 0}},
    {"min_history_days": 0},
    {"trigger_pct": 101},
])
def test_invalid_config_is_rejected(tmp_path, over):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({**cfg_base(), **good(), **over}))
    with pytest.raises(ValueError):
        disc.load_config(p)


def cfg_base():
    return {"min_volume_24h_usd": 1, "winsor_percentile": 95, "recent_days": 7, "max_source_lag_days": 3,
            "categories": CATS}


def test_weight_sum_tolerance_accepts_small_drift(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({**cfg_base(), **good(source_weights=_sw(wikipedia=25.005))}))
    assert disc.load_config(p)["source_weights"]["wikipedia"] == 25.005


def test_rising_boundary_is_ten_percent():
    assert disc._is_rising(10.0, 10.0) is True
    assert disc._is_rising(9.99, 10.0) is False


def test_rescaled_weighted_score(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]})
    put_change("wikipedia", "A", 2.0, 1.0)      # +100
    put_change("coingecko", "A", 1.5, 1.0)      # +50, fallback slot weight 10
    put_change("wikipedia", "B", 2.0, 1.0)
    res = disc.build_discovery(30, today=TODAY)
    assert round(coin(res, "ai", "A").raw_change, 6) == round((25 * 100 + 10 * 50) / 35, 6)
    assert coin(res, "ai", "B").raw_change == pytest.approx(100.0)


def test_unavailable_source_drops_out_and_is_not_zero(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0)
    put_change("trends", "A", 2.0, 1.0, days=50)       # insufficient-history -> not ok
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    assert c.covered_weight == 25 and c.raw_change == pytest.approx(100.0)
    assert [s.source for s in c.sources] == ["wikipedia"]


def test_none_change_drops_out(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0)
    put_change("trends", "A", 0.0, 0.0)                # base mean 0 -> change None
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    assert c.covered_weight == 25 and c.raw_change == pytest.approx(100.0)


def test_rising_threshold_comes_from_config(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]},
          source_weights=_sw(wikipedia=60, trends=40, reddit=0, xsearch=0, exchange_activity=0,
                             github_dev=0, defillama=0), rising_threshold_pct=100.0)
    put_change("wikipedia", "A", 2.0, 1.0)             # exactly +100.0 -> rising
    put_change("wikipedia", "B", 1.99, 1.0)            # +99 -> not rising
    res = disc.build_discovery(30, today=TODAY)
    assert (coin(res, "ai", "A").rising_weight, coin(res, "ai", "B").rising_weight) == (60, 0)


WIKI_TRENDS = dict(reddit=0, xsearch=0, exchange_activity=0, github_dev=0, defillama=0)


def trig(tmp_path, monkeypatch, w, t, **cfgover):
    """Coin A: wikipedia and trends weights (w, t); returns the row. Rising = 2.0x, flat = 1.0x."""
    sw = {**WEIGHTS, **WIKI_TRENDS, "wikipedia": w, "trends": t}
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, source_weights=sw, **cfgover)
    return sw


def test_trigger_boundary_at_60_percent_rising_weight(isolated_cache, tmp_path, monkeypatch):
    trig(tmp_path, monkeypatch, 60, 40)
    put_change("wikipedia", "A", 2.0, 1.0)
    put_change("trends", "A", 1.0, 1.0)
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    assert (c.covered_weight, c.rising_weight, c.trigger) == (100, 60, True)      # 0.60 exactly


def test_trigger_just_below_60_percent(isolated_cache, tmp_path, monkeypatch):
    trig(tmp_path, monkeypatch, 59, 41)
    put_change("wikipedia", "A", 2.0, 1.0)
    put_change("trends", "A", 1.0, 1.0)
    assert coin(disc.build_discovery(30, today=TODAY), "ai", "A").trigger is False


def test_covered_floor_boundary_30(isolated_cache, tmp_path, monkeypatch):
    trig(tmp_path, monkeypatch, 30, 70)
    put_change("wikipedia", "A", 2.0, 1.0)
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    assert (c.covered_weight, c.rising_weight, c.trigger) == (30, 30, True)


def test_below_floor_still_scored_but_no_trigger(isolated_cache, tmp_path, monkeypatch):
    trig(tmp_path, monkeypatch, 29, 71)
    put_change("wikipedia", "A", 2.0, 1.0)
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    assert (c.covered_weight, c.trigger) == (29, False) and c.raw_change == pytest.approx(100.0)


def test_25_covered_all_rising_does_not_trigger(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 3.0, 1.0)
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    assert (c.covered_weight, c.rising_weight, c.trigger) == (25, 25, False)


def test_trigger_count_is_gaining_count(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7, "C": 5e7}, cats={"ai": ["A", "B", "C"]})
    gain("A"), gain("B")
    put_change("wikipedia", "C", 2.0, 1.0)             # 25 covered -> no trigger
    c = cat(disc.build_discovery(30, today=TODAY), "ai")
    assert c.gaining_count == 2 and c.coins_used == 3


def test_zero_sources_coin_is_omitted(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]})
    put_change("wikipedia", "A", 2.0, 1.0)
    assert [x.symbol for x in cat(disc.build_discovery(30, today=TODAY), "ai").coins] == ["A"]


def test_row_sources_carry_change_and_as_of(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0, lag=2)
    put_change("trends", "A", 2.0, 1.0)
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    by = {s.source: s for s in c.sources}
    assert by["wikipedia"].as_of == (END - timedelta(days=2)).isoformat()
    assert by["trends"].as_of == END.isoformat() and by["trends"].change == pytest.approx(100.0)


def test_payload_drops_old_fields(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    gain("A")
    row = disc.build_discovery(30, today=TODAY).model_dump()["categories"][0]["coins"][0]
    assert set(row) == {"symbol", "change", "raw_change", "covered_weight", "rising_weight", "trigger", "sources"}


# ---- exchange_activity composite -----------------------------------------------------------

def test_exchange_composite_is_sub_weighted_mean_over_present_exchanges(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("exchange_volume", "A", 2.0, 1.0)       # binance +100, sub 40
    put_change("coinbase_volume", "A", 1.0, 1.0)       # coinbase 0, sub 25
    put_change("hyperliquid_volume", "A", 1.5, 1.0)    # hyperliquid +50, sub 20 (kraken absent)
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    ex = next(s for s in c.sources if s.source == "exchange_activity")
    assert ex.change == pytest.approx((40 * 100 + 25 * 0 + 20 * 50) / 85)
    assert c.covered_weight == 10 and not any(s.source == "coingecko" for s in c.sources)
    assert {m.source: m.as_of for m in ex.members} == {
        "binance": END.isoformat(), "coinbase": END.isoformat(), "hyperliquid": END.isoformat()}


def test_dropping_binance_rescales_without_a_jump(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("coinbase_volume", "A", 1.5, 1.0)       # +50
    put_change("kraken_volume", "A", 1.5, 1.0)         # +50
    before = next(s for s in coin(disc.build_discovery(30, today=TODAY), "ai", "A").sources
                  if s.source == "exchange_activity").change
    put_change("exchange_volume", "A", 1.5, 1.0)       # binance back, same +50
    after = next(s for s in coin(disc.build_discovery(30, today=TODAY), "ai", "A").sources
                 if s.source == "exchange_activity").change
    assert before == pytest.approx(50.0) and after == pytest.approx(50.0)


def test_raw_volumes_are_never_summed(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("exchange_volume", "A", 1e9, 1e9)       # huge, flat
    put_change("coinbase_volume", "A", 2e6, 1e6)       # tiny, +100
    ex = next(s for s in coin(disc.build_discovery(30, today=TODAY), "ai", "A").sources
              if s.source == "exchange_activity")
    assert ex.change == pytest.approx((40 * 0 + 25 * 100) / 65)    # a summed series would read about +0.1


def test_coingecko_fallback_when_no_exchange_has_data(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0)
    put_change("coingecko", "A", 1.5, 1.0)
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    by = {s.source: s for s in c.sources}
    assert "exchange_activity" not in by and by["coingecko"].change == pytest.approx(50.0)
    assert c.covered_weight == 35


def test_coingecko_not_used_when_any_exchange_has_data(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0)
    put_change("exchange_volume", "A", 1.0, 1.0)
    put_change("coingecko", "A", 9.0, 1.0)
    c = coin(disc.build_discovery(30, today=TODAY), "ai", "A")
    assert sorted(s.source for s in c.sources) == ["exchange_activity", "wikipedia"]
    assert c.covered_weight == 35 and c.raw_change == pytest.approx((25 * 100 + 10 * 0) / 35)
