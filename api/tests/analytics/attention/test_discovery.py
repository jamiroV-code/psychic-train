"""S-F1: Discovery rules on fixtures. Store only; every path redirected to tmp_path."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest

from api.analytics.attention import discovery as disc, narratives as narr_mod, score as score_mod
from api.analytics.attention import universe as universe_mod
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
    rules = {"min_narrative_coins": over.pop("min_narrative_coins", 1), "thin_volume_label_below_usd": 20_000_000,
             "classes": {"stablecoin": ["USDT"]}, **over.pop("rules", {})}
    base = {"source_weights": WEIGHTS, "exchange_sub_weights": SUB, "rising_threshold_pct": 10,
            "trigger_pct": 60, "min_covered_weight": 30, "min_history_days": 90,
            "winsor_percentile": 95, "recent_days": 7, "max_source_lag_days": 3,
            "universe_rules": rules}
    base.update(over)
    p = tmp_path / "discovery.json"
    p.write_text(json.dumps(base))
    return p


def write_narratives(tmp_path, cats, status="proposed", as_of="2026-10-14"):
    """Narratives fixture: the `cats` entries whose id is in CATS; a coin's first narrative is its primary."""
    names, seen, out = {c["id"]: c["name"] for c in CATS}, set(), []
    for cid, name in names.items():
        coins = []
        for s in (cats or {}).get(cid, []):
            coins.append({"symbol": s, "primary": s not in seen})
            seen.add(s)
        out.append({"id": cid, "name": name, "coins": coins})
    p = tmp_path / "attention_narratives.json"
    p.write_text(json.dumps({"status": status, "as_of": as_of, "narratives": out}))
    return p


def world(tmp_path, monkeypatch, coins, cats=None, **over):
    """coins: {SYM: volume}; cats: {category id: [SYM]} (None = no categories snapshot). The ids in CATS are
    also written as the narratives fixture (members = Discovery categories); other ids (e.g. "cex") only feed
    the CoinGecko snapshot, which nothing reads for eligibility since U2."""
    probe, w, u = write_configs(tmp_path, sources=PROBED, reference=())
    monkeypatch.setattr(registry, "PROBE_RECORDS_PATH", probe)
    monkeypatch.setattr(score_mod, "WEIGHTS_PATH", w)
    monkeypatch.setattr(universe_mod, "UNIVERSE_PATH", u)
    monkeypatch.setattr(disc, "CONFIG_PATH", cfg(tmp_path, **over))
    monkeypatch.setattr(narr_mod, "NARRATIVES_PATH", write_narratives(tmp_path, cats))
    id_map = tmp_path / "attention_narrative_id_map.json"
    id_map.write_text(json.dumps({"map": {"artificial-intelligence": {"narrative": "ai", "name": "AI"},
                                          "gaming": {"narrative": None, "name": "Gaming"}}}))
    monkeypatch.setattr(narr_mod, "ID_MAP_PATH", id_map)
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


def test_categories_snapshot_is_not_needed(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats=None)
    monkeypatch.setattr(narr_mod, "NARRATIVES_PATH", write_narratives(tmp_path, {"ai": ["A"]}))
    gain("A")
    res = disc.build_discovery(30, today=TODAY)
    assert (res.status, [c.symbol for c in cat(res, "ai").coins]) == ("ok", ["A"])


def test_universe_missing(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    (isolated_cache / "attention" / "universe.json").unlink()
    res = disc.build_discovery(30, today=TODAY)
    assert (res.status, res.reason) == ("no-data", "reference-missing")


def test_stablecoin_class_is_excluded_exchange_token_is_in(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "BNB": 5e7, "USDT": 5e7}, cats={"ai": ["A", "BNB", "USDT"]})
    for s in ("A", "BNB", "USDT"):
        gain(s)
    res = disc.build_discovery(30, today=TODAY)
    assert sorted(c.symbol for c in cat(res, "ai").coins) == ["A", "BNB"]
    assert [c.model_dump() for c in res.excluded_coins] == [
        {"symbol": "USDT", "reason": "stablecoin", "detail": "stablecoin"}]


def test_coingecko_category_tag_no_longer_excludes(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "T": 5e7}, cats={"ai": ["A", "T"], "cex": ["T"]})
    gain("A"), gain("T")
    res = disc.build_discovery(30, today=TODAY)
    assert sorted(c.symbol for c in cat(res, "ai").coins) == ["A", "T"]
    assert all(c.id != "cex" for c in res.categories)


def test_zero_volume_is_not_tradeable_null_and_low_volume_stay(isolated_cache, tmp_path, monkeypatch):
    """T189: exactly zero 24h volume = no trading market (excluded with a reason); null and low volume stay."""
    coins = {"ZERO": 0, "NULL": None, "LOW": 1.0, "HIGH": 9e8}
    world(tmp_path, monkeypatch, coins, cats={"ai": list(coins)})
    for s in coins:
        gain(s)
    res = disc.build_discovery(30, today=TODAY)
    assert sorted(c.symbol for c in cat(res, "ai").coins) == ["HIGH", "LOW", "NULL"]
    assert [(c.symbol, c.reason, c.detail) for c in res.excluded_coins] == [
        ("ZERO", "not-tradeable", "zero 24h volume")]
    assert coin(res, "ai", "NULL").volume_24h is None and res.excluded.exclusion_list == 1


def test_thin_volume_label_below_20m_only_label(isolated_cache, tmp_path, monkeypatch):
    coins = {"LOW": 19_999_999, "EDGE": 20_000_000, "HIGH": 9e8, "TINY": 1.0, "NULL": None}
    world(tmp_path, monkeypatch, coins, cats={"ai": list(coins)})
    for s in coins:
        gain(s)
    res = disc.build_discovery(30, today=TODAY)
    thin = {c.symbol: c.thin_volume for c in cat(res, "ai").coins}
    assert thin == {"LOW": True, "EDGE": False, "HIGH": False, "TINY": True, "NULL": False}
    assert coin(res, "ai", "LOW").volume_24h == 19_999_999 and res.shown_size == 5


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
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A"], "defi": ["B"]})
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


def test_shipped_config_has_no_exchange_token_exclusion():
    rules = json.loads(disc.CONFIG_PATH.read_text())["universe_rules"]
    listed = {s for syms in rules["classes"].values() for s in syms} | set(rules["not_tradeable"])
    assert not listed & {"BNB", "LEO", "OKB", "CRO", "GT", "KCS", "BGB", "MX"}
    assert rules["force_include"] == [] and "backup_floor_usd" not in rules


def test_bnb_and_leo_both_eligible_despite_exchange_category(isolated_cache, tmp_path, monkeypatch):
    coins = {"BNB": 5e7, "LEO": 5e7}
    world(tmp_path, monkeypatch, coins, cats={"ai": ["BNB", "LEO"], "cex": ["BNB", "LEO"]})
    for s in coins:
        gain(s)
    res = disc.build_discovery(30, today=TODAY)
    assert sorted(c.symbol for c in cat(res, "ai").coins) == ["BNB", "LEO"]


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
            "trigger_pct": 60, "min_covered_weight": 30, "min_history_days": 90,
            "universe_rules": {"min_narrative_coins": 1}, **over}


def test_shipped_config_is_valid():
    """Weights v2 (T130) live in test_weights_v2.py; WEIGHTS here mirror the shipped v1 history entry."""
    c = disc.load_config()
    assert sum(c["exchange_sub_weights"].values()) == pytest.approx(100)
    assert c["weights_history"][0]["source_weights"] == WEIGHTS and c["exchange_sub_weights"] == SUB
    assert (c["rising_threshold_pct"], c["trigger_pct"], c["min_covered_weight"], c["min_history_days"]) == (
        10, 60, 30, 30)
    assert "min_independent_sources" not in c


def _sw(**kw):
    return {**WEIGHTS, **kw}


@pytest.mark.parametrize("over", [
    {"source_weights": _sw(wikipedia=-1, trends=51)},
    {"source_weights": {k: 0 for k in WEIGHTS}},
    {"source_weights": _sw(wikipedia="25")},
    {"source_weights": {**WEIGHTS, "coingecko": 0}},
    {"source_weights": {**WEIGHTS, "exchange_volume": 0}},
    {"source_weights": {**WEIGHTS, "hyperliquid_volume": 0}},
    {"source_weights": {**WEIGHTS, "nonsense": 0}},
    {"exchange_sub_weights": {**SUB, "binance": 41}},
    {"exchange_sub_weights": {"binance": 101, "coinbase": -1}},
    {"exchange_sub_weights": {**SUB, "okx": 0}},
    {"min_history_days": 0},
    {"trigger_pct": 101},
    {"universe_rules": None},
    {"universe_rules": {}},
    {"universe_rules": {"min_narrative_coins": 0}},
    {"universe_rules": {"min_narrative_coins": -2}},
    {"universe_rules": {"min_narrative_coins": 2.5}},
    {"universe_rules": {"min_narrative_coins": True}},
    {"universe_rules": {"min_narrative_coins": "3"}},
    {"universe_rules": {"min_narrative_coins": None}},
])
def test_invalid_config_is_rejected(tmp_path, over):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({**cfg_base(), **good(), **over}))
    with pytest.raises(ValueError):
        disc.load_config(p)


def cfg_base():
    return {"winsor_percentile": 95, "recent_days": 7, "max_source_lag_days": 3}


def test_source_weights_need_not_sum_to_100(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({**cfg_base(), **good(source_weights=_sw(wikipedia=24.5))}))
    assert disc.load_config(p)["source_weights"]["wikipedia"] == 24.5


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
    assert set(row) == {"symbol", "change", "raw_change", "covered_weight", "rising_weight", "trigger", "sources",
                        "primary", "volume_24h", "thin_volume", "tradeability"}


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


# ---- T106: ranked-category rule and exclusion counts ---------------------------------------

def test_shipped_min_narrative_coins_is_three():
    c = disc.load_config()
    assert c["universe_rules"]["min_narrative_coins"] == 3 and "min_category_coins" not in c


def test_missing_min_narrative_coins_is_rejected(tmp_path):
    p = tmp_path / "d.json"
    c = {**cfg_base(), **good()}
    del c["universe_rules"]["min_narrative_coins"]
    p.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="min_narrative_coins"):
        disc.load_config(p)


def test_category_below_minimum_is_unranked_but_keeps_its_score(isolated_cache, tmp_path, monkeypatch):
    coins = {"A": 5e7, "B": 5e7, "C": 5e7, "D": 5e7, "E": 5e7}
    world(tmp_path, monkeypatch, coins, cats={"ai": ["A", "B", "C"], "defi": ["A", "D", "E"]}, min_narrative_coins=3)
    for s in "ABC":
        gain(s, factor=1.2)
    res = disc.build_discovery(30, today=TODAY)
    assert res.min_category_coins == 3
    assert (cat(res, "ai").ranked, cat(res, "ai").coins_used) == (True, 3)
    d = cat(res, "defi")
    assert (d.ranked, d.coins_used) == (False, 1) and d.score is not None


def test_minimum_is_inclusive(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]}, min_narrative_coins=2)
    gain("A"), gain("B")
    assert cat(disc.build_discovery(30, today=TODAY), "ai").ranked is True


def test_coins_without_usable_data_do_not_count_toward_the_minimum(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7, "C": 5e7}, cats={"ai": ["A", "B", "C"]}, min_narrative_coins=3)
    gain("A"), gain("B")
    c = cat(disc.build_discovery(30, today=TODAY), "ai")
    assert (c.coins_used, c.ranked) == (2, False)


def test_unranked_sit_after_ranked_whatever_their_score(isolated_cache, tmp_path, monkeypatch):
    coins = {"A": 5e7, "B": 5e7, "C": 5e7, "D": 5e7, "E": 5e7, "F": 5e7}
    world(tmp_path, monkeypatch, coins, cats={"ai": ["A", "B", "C"], "defi": ["D", "E", "F"]}, min_narrative_coins=3)
    for s in "ABC":
        gain(s, factor=1.1)
    gain("D", factor=5.0)
    res = disc.build_discovery(30, today=TODAY)
    assert [(c.id, c.ranked) for c in res.categories if c.id in ("ai", "defi")] == [("ai", True), ("defi", False)]
    assert cat(res, "defi").score > cat(res, "ai").score


def test_ranked_order_is_unchanged_by_the_rule(isolated_cache, tmp_path, monkeypatch):
    coins = {s: 5e7 for s in "ABCDEF"}
    world(tmp_path, monkeypatch, coins, cats={"ai": ["A", "B", "C"], "defi": ["D", "E", "F"]}, min_narrative_coins=3)
    for s in "ABC":
        gain(s, factor=1.2)
    for s in "DEF":
        gain(s, factor=3.0)
    assert [c.id for c in disc.build_discovery(30, today=TODAY).categories if c.ranked] == ["defi", "ai"]


def test_legacy_excluded_object_still_sums(isolated_cache, tmp_path, monkeypatch):
    coins = {"USDT": 5e7, "W": 5e7, "F": 0, "LOW": 1e6, "NOCAT": 5e7, "NODATA": 5e7, "A": 5e7, "UNK": None}
    world(tmp_path, monkeypatch, coins, cats={"ai": ["USDT", "W", "F", "LOW", "NODATA", "A", "UNK"]},
          rules={"classes": {"stablecoin": ["USDT"], "wrapped_staked": ["W"], "tokenized_fund": ["F"]}})
    gain("A"), gain("LOW"), gain("UNK")
    res = disc.build_discovery(30, today=TODAY)
    assert res.universe_size == 8 and res.shown_size == 3
    assert res.excluded.model_dump() == {"exclusion_list": 3, "below_volume_floor": 0, "no_category": 1,
                                         "no_source_data": 1}
    assert res.shown_size + sum(res.excluded.model_dump().values()) == res.universe_size


def test_response_carries_thresholds(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    gain("A")
    res = disc.build_discovery(30, today=TODAY)
    assert (res.rising_threshold_pct, res.min_covered_weight) == (10, 30)


# ---- T113 U1: Discovery categories are the narratives file ---------------------------------------------------

def test_discovery_uses_narratives_not_categories(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A"]})
    monkeypatch.setattr(narr_mod, "NARRATIVES_PATH", write_narratives(tmp_path, {"ai": ["A", "B"], "defi": ["B"]}))
    gain("A"), gain("B")
    res = disc.build_discovery(30, today=TODAY)
    assert sorted(c.symbol for c in cat(res, "ai").coins) == ["A", "B"]
    assert [c.symbol for c in cat(res, "defi").coins] == ["B"]
    assert (coin(res, "ai", "B").primary, coin(res, "defi", "B").primary, coin(res, "ai", "A").primary) == (
        True, False, True)


def test_min_narrative_coins_drives_hidden_and_min_category_coins_field(isolated_cache, tmp_path, monkeypatch):
    coins = {"A": 5e7, "B": 5e7, "C": 5e7, "D": 5e7}
    world(tmp_path, monkeypatch, coins, cats={"ai": ["A", "B", "C"], "defi": ["C", "D", "OUT"]},
          min_narrative_coins=3)
    for s in coins:
        gain(s)
    res = disc.build_discovery(30, today=TODAY)
    assert res.min_category_coins == 3
    assert [c.id for c in res.categories] == ["ai"]
    assert [h.model_dump() for h in res.hidden_narratives] == [{"id": "defi", "name": "DeFi", "coins": ["C", "D"]}]


def test_unassigned_new_coin_listed_not_error(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "NEW": 5e7}, cats={"ai": ["A"]})
    gain("A"), gain("NEW")
    res = disc.build_discovery(30, today=TODAY)
    assert res.status == "ok" and res.unassigned == ["NEW"]
    assert res.excluded.no_category == 1


def test_response_carries_narratives_status_and_as_of(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    gain("A")
    res = disc.build_discovery(30, today=TODAY)
    assert (res.narratives_status, res.categories_as_of) == ("proposed", "2026-10-14")
    monkeypatch.setattr(narr_mod, "NARRATIVES_PATH",
                        write_narratives(tmp_path, {"ai": ["A"]}, status="reviewed", as_of="2026-10-15"))
    res = disc.build_discovery(30, today=TODAY)
    assert (res.narratives_status, res.categories_as_of) == ("reviewed", "2026-10-15")


def test_invalid_narratives_file_fails_loudly(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    bad = tmp_path / "bad.json"
    coins = [{"symbol": "../X", "primary": True}]
    bad.write_text(json.dumps({"status": "proposed", "as_of": "2026-10-14",
                               "narratives": [{"id": "ai", "name": "AI", "coins": coins}]}))
    monkeypatch.setattr(narr_mod, "NARRATIVES_PATH", bad)
    with pytest.raises(ValueError, match=r"\.\./X"):
        disc.build_discovery(30, today=TODAY)


@pytest.mark.parametrize("key, value", [("categories", CATS), ("min_category_coins", 3)])
def test_removed_keys_categories_and_min_category_coins_rejected(tmp_path, key, value):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({**cfg_base(), **good(), key: value}))
    with pytest.raises(ValueError, match=key):
        disc.load_config(p)


def test_shipped_config_has_no_categories_key():
    raw = json.loads(disc.CONFIG_PATH.read_text())
    assert "categories" not in raw and "min_category_coins" not in raw
    assert raw["universe_rules"]["min_narrative_coins"] == 3
