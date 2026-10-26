"""T115 U2: reasoned exclusion, label-only volume, exchange tokens IN. Fixture = a COPY of the 2026-10-18 universe
snapshot (F14); the live nightly cache is never read. Shipped config and narratives file, read-only."""
from __future__ import annotations

import json
import shutil
import socket
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from api.analytics.attention import discovery as disc, sources as src, universe_classes as uc
from api.analytics.attention import universe as universe_mod
from api.data.attention import registry, tradeable_markets as tm
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import cfg_base, gain, good, world

FIXTURE = Path(__file__).parent / "fixtures" / "universe_2026-10-18.json"
STABLES = {"USDT", "USDC", "USDS", "USDE", "DAI", "USD1", "PYUSD", "USDD", "USDG", "RLUSD", "USDF", "BFUSD", "USDGO",
           "OUSD", "GHO", "U"}
FUNDS = {"USDY", "BUIDL", "USYC", "USTB", "EUTBL", "EURSAFO", "BCAP", "FIGR_HELOC"}
# attention_universe.json lists as on main (Baskets reference, Q-V1): a change here or in load_universe fails.
MAIN_LISTS = {"USDT", "USDC", "DAI", "USDE", "FDUSD", "TUSD", "USDD", "PYUSD", "USDS", "USD1", "WBTC", "WETH", "STETH",
              "WSTETH", "WEETH", "CBBTC", "WBETH", "BSC-USD", "WBNB", "LEO", "OKB", "CRO", "GT", "KCS", "BGB", "MX"}


@pytest.fixture
def snap(isolated_cache, tmp_path, monkeypatch):
    """The fixture snapshot as the only universe snapshot; `reference` override empty; shipped config."""
    dest = isolated_cache / "attention" / "universe.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE, dest)
    u = tmp_path / "attention_universe.json"
    u.write_text(universe_mod.UNIVERSE_PATH.read_text())
    monkeypatch.setattr(universe_mod, "UNIVERSE_PATH", u)
    return universe_mod.load_universe_rows()[0]


def shipped(rows, venues=None) -> uc.Universe:
    return disc.eligibility(disc.load_config(), rows, venues)


def reasons(u: uc.Universe, reason: str) -> set[str]:
    return {s for s, (r, _) in u.out.items() if r == reason}


def test_fixture_is_the_full_top_100(snap):
    assert len(snap) == 100 and snap[0]["symbol"] == "BTC"


def test_stablecoin_count_is_16_on_fixture_snapshot(snap):
    assert reasons(shipped(snap), "stablecoin") == STABLES


def test_leaked_stablecoins_usdg_rlusd_u_excluded(snap):
    u = shipped(snap)
    leaked = ("USDG", "RLUSD", "U")
    assert {s: u.out[s] for s in leaked} == {s: ("stablecoin", "stablecoin") for s in leaked}


def test_tokenized_funds_reason_no_market(snap):
    u = shipped(snap)
    assert reasons(u, "no-market") == FUNDS
    assert {u.out[s][1] for s in FUNDS} == {"tokenized fund"}


def test_wrapped_staked_excluded_with_reason():
    rows = [{"symbol": s, "volume_24h": 5e7} for s in ("WBTC", "STETH", "BTC")]
    u = shipped(rows)
    assert (u.out, u.eligible) == ({"WBTC": ("wrapped-staked", "wrapped or staked"),
                                    "STETH": ("wrapped-staked", "wrapped or staked")}, ["BTC"])


def venues(binance=None, hyperliquid=None) -> dict[str, tm.VenueList]:
    """None = that venue's list is missing; a dict = a fresh list (symbol -> 24h volume)."""
    return {name: tm.VenueList(name, "missing") if vols is None else tm.VenueList(name, "ok", "2026-10-25", vols)
            for name, vols in (("binance", binance), ("hyperliquid", hyperliquid))}


def test_failed_venue_list_is_unknown_coin_stays_in():
    rows = [{"symbol": s, "volume_24h": 5e7} for s in ("BTC", "ETH")]
    partial = venues(hyperliquid={"BTC": 1e9})
    u = shipped(rows, partial)
    assert u.eligible == ["BTC", "ETH"] and u.tradeability == {"BTC": "tradeable", "ETH": "unverified"}
    assert tm.tradeability("ETH", partial, 5e7).status == "unknown"
    # every tracked list loaded and fresh and none has it: not-tradeable (no listed market)
    u = shipped(rows, venues(binance={"BTC": 1e9}, hyperliquid={}))
    assert u.eligible == ["BTC"] and u.out["ETH"] == ("not-tradeable", tm.NO_MARKET)
    # nothing loaded at all: nothing is cut, every coin unverified
    assert shipped(rows, venues()).tradeability == {"BTC": "unverified", "ETH": "unverified"}


def test_zero_volume_coin_is_not_tradeable_with_detail():
    rows = [{"symbol": "BTC", "volume_24h": 5e7}, {"symbol": "JAAA", "volume_24h": 0},
            {"symbol": "NULL", "volume_24h": None}]
    u = shipped(rows, venues())
    assert u.out == {"JAAA": ("not-tradeable", "zero 24h volume")}
    assert u.eligible == ["BTC", "NULL"] and u.tradeability == {"BTC": "unverified", "NULL": "unverified"}


def test_class_reason_wins_over_zero_volume():
    """Tokenized funds keep their reason `no-market` (first match wins); only non-class coins get not-tradeable."""
    u = shipped([{"symbol": "BUIDL", "volume_24h": 0}, {"symbol": "USDT", "volume_24h": 0}], venues())
    assert u.out == {"BUIDL": ("no-market", "tokenized fund"), "USDT": ("stablecoin", "stablecoin")}


def test_force_include_beats_not_tradeable():
    c = disc.load_config()
    c["universe_rules"] = {**c["universe_rules"], "force_include": ["JAAA"]}
    u = disc.eligibility(c, [{"symbol": "JAAA", "volume_24h": 0}], venues(binance={}, hyperliquid={}))
    assert u.eligible == ["JAAA"] and u.tradeability == {"JAAA": "unverified"}


def test_exchange_tokens_with_a_market_stay_in():
    rows = [{"symbol": s, "volume_24h": 3e6} for s in ("LEO", "CRO", "BNB")]
    u = shipped(rows, venues(binance={"LEO": 4e6, "CRO": None}, hyperliquid={"BNB": 1e8}))
    assert u.eligible == ["LEO", "CRO", "BNB"] and set(u.tradeability.values()) == {"tradeable"}


def test_alias_pepe_shib_found_on_hyperliquid_k_names():
    rows = [{"symbol": "PEPE", "volume_24h": 5e8}, {"symbol": "SHIB", "volume_24h": 2e8}]
    hl = {tm.canonical("kPEPE"): 1e7, tm.canonical("kSHIB"): 3e6}
    assert shipped(rows, venues(hyperliquid=hl)).tradeability == {"PEPE": "tradeable", "SHIB": "tradeable"}


def test_eligibility_reads_the_stored_lists_point_in_time(isolated_cache):
    """No `venues` passed: the stored lists are read for `today` (here: none stored -> unknown, nothing cut)."""
    from api.data import cache
    cache.write_exchange_market_snapshot("2026-10-15", ["BTC"])
    rows = [{"symbol": "BTC", "volume_24h": 5e7}, {"symbol": "ETH", "volume_24h": 5e7}]
    c = disc.load_config()
    assert disc.eligibility(c, rows, today=TODAY).tradeability == {"BTC": "tradeable", "ETH": "unverified"}
    stale = TODAY + timedelta(days=tm.STALE_AFTER_DAYS + 1)
    assert disc.eligibility(c, rows, today=stale).tradeability == {"BTC": "unverified", "ETH": "unverified"}
    assert set(disc.eligibility(c, rows, today=TODAY).venues) == set(tm.TRACKED_VENUES)


def test_uni_jup_aero_cake_hype_eligible(snap):
    assert {"UNI", "JUP", "AERO", "CAKE", "HYPE", "ASTER"} <= set(shipped(snap).eligible)


def test_exchange_tokens_eligible_and_counts_on_fixture(snap):
    u = shipped(snap)
    assert {"BNB", "LEO", "CRO", "OKB", "BGB", "GT", "KCS", "WBT", "HTX"} <= set(u.eligible)
    assert len(u.eligible) == 76 and not reasons(u, "wrapped-staked")


def test_no_volume_reason_and_thin_label_on_fixture(snap):
    u = shipped(snap)
    assert set(r for r, _ in u.out.values()) <= set(uc.REASONS) and u.volume["LEO"] == 244429
    assert u.thin["LEO"] and not u.thin["BTC"]


def test_force_include_and_not_tradeable_both_is_config_error(tmp_path):
    p = tmp_path / "d.json"
    c = {**cfg_base(), **good()}
    c["universe_rules"].update(force_include=["XMR"], not_tradeable={"XMR": "delisted"})
    p.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="XMR in both force_include and not_tradeable"):
        disc.load_config(p)


@pytest.mark.parametrize("rules", [
    {"classes": {"stablecoin": "USDT"}}, {"classes": {"gold": ["XAUT"]}}, {"not_tradeable": ["XMR"]},
    {"not_tradeable": {"../X": "bad"}}, {"force_include": ["btc"]}, {"thin_volume_label_below_usd": -1},
    {"classes": {"stablecoin": ["X"], "tokenized_fund": ["X"]}}, {"backup_floor_usd": 5_000_000},
])
def test_invalid_universe_rules_rejected(tmp_path, rules):
    p = tmp_path / "d.json"
    c = {**cfg_base(), **good()}
    c["universe_rules"].update(rules)
    p.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="universe_rules|classes"):
        disc.load_config(p)


@pytest.mark.parametrize("key, value", [("min_volume_24h_usd", 20_000_000), ("exclude", ["LEO"]),
                                        ("exclude_category_ids", ["exchange-based-tokens"]),
                                        ("include_despite_category", ["BNB"])])
def test_removed_config_keys_rejected(tmp_path, key, value):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({**cfg_base(), **good(), key: value}))
    with pytest.raises(ValueError, match=f"{key} is no longer read"):
        disc.load_config(p)


def test_shipped_config_has_no_removed_keys_or_floor():
    raw = disc.CONFIG_PATH.read_text()
    assert all(k not in json.loads(raw) for k in uc.REMOVED_KEYS) and "backup_floor_usd" not in raw
    assert json.loads(raw)["universe_rules"]["thin_volume_label_below_usd"] == 20_000_000


def test_not_tradeable_config_reason_and_force_include(snap):
    c = disc.load_config()
    c["universe_rules"] = {**c["universe_rules"], "not_tradeable": {"XMR": "delisted on all four venues"},
                           "force_include": ["PAXG", "USDC"]}
    u = disc.eligibility(c, snap)
    assert u.out["XMR"] == ("not-tradeable-config", "delisted on all four venues")
    assert "USDC" in u.eligible and "PAXG" in u.eligible


def test_excluded_counts_sum_to_universe_minus_shown(isolated_cache, tmp_path, monkeypatch):
    coins = {"USDT": 5e7, "W": 5e7, "F": 0, "X": 5e7, "NOCAT": 5e7, "HID": 5e7, "NODATA": 5e7, "A": 5e7, "B": None,
             "Z": 0}
    world(tmp_path, monkeypatch, coins, cats={"ai": ["USDT", "W", "F", "X", "NODATA", "A", "B", "Z"],
                                              "defi": ["HID"]},
          min_narrative_coins=2, rules={"classes": {"stablecoin": ["USDT"], "wrapped_staked": ["W"],
                                                    "tokenized_fund": ["F"]}, "not_tradeable": {"X": "no venue"}})
    gain("A"), gain("B"), gain("HID")
    res = disc.build_discovery(30, today=TODAY)
    assert res.excluded_counts == {"stablecoin": 1, "wrapped-staked": 1, "no-market": 1, "not-tradeable-config": 1,
                                   "not-tradeable": 1, "unassigned": 1, "hidden-narrative": 1, "no-source-data": 1}
    assert res.shown_size == 2 and res.universe_size == 10
    assert res.shown_size + sum(res.excluded_counts.values()) == res.universe_size
    assert {c.symbol: c.reason for c in res.excluded_coins}["HID"] == "hidden-narrative"
    assert res.excluded.model_dump() == {"exclusion_list": 5, "below_volume_floor": 0, "no_category": 2,
                                         "no_source_data": 1}
    assert {c.symbol: (c.reason, c.detail) for c in res.excluded_coins}["Z"] == ("not-tradeable", "zero 24h volume")
    assert res.shown_size + sum(res.excluded.model_dump().values()) == res.universe_size


def test_basket_reference_unchanged_on_fixture(snap):
    """Q-V1 / AC-N8: Baskets scores depend on `load_reference` and `basket.py` (untouched); the reference on the
    fixture is the top 100 minus main's three lists, exchange tokens still out."""
    expect = [r["symbol"] for r in snap if r["symbol"] not in MAIN_LISTS]
    assert universe_mod.load_reference() == expect and len(expect) == 86
    assert json.loads(universe_mod.UNIVERSE_PATH.read_text())["exchange_tokens"] == [
        "LEO", "OKB", "CRO", "GT", "KCS", "BGB", "MX"]


def test_sources_eligible_size_is_the_in_set(snap, tmp_path, monkeypatch):
    probe = tmp_path / "probe.json"
    probe.write_text("{}")
    monkeypatch.setattr(registry, "PROBE_RECORDS_PATH", probe)
    src.clear_cache()
    res = src.build_sources(TODAY)
    assert (res.universe_size, res.eligible_size) == (100, 76)


def test_discovery_end_to_end_on_fixture(snap, tmp_path, monkeypatch):
    from api.main import app
    from api.routers import discovery as router_mod
    probe = tmp_path / "probe.json"
    probe.write_text(json.dumps({s: {"probed": True} for s in ("wikipedia", "coingecko", "trends")}))
    monkeypatch.setattr(registry, "PROBE_RECORDS_PATH", probe)
    monkeypatch.setattr(router_mod, "utc_today", lambda: TODAY)
    for s in shipped(snap).eligible:
        gain(s)

    def boom(*a, **k):
        raise AssertionError("handler must not reach the network")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    body = TestClient(app).get("/api/narrative/discovery", params={"window": 30}).json()
    counts = body["excluded_counts"]
    assert body["status"] == "ok" and body["universe_size"] == 100 and body["eligible_size"] == 76
    assert (counts["stablecoin"], counts["no-market"], counts["unassigned"], counts["wrapped-staked"]) == (16, 8, 1, 0)
    assert body["unassigned"] == ["M"] and set(counts) == set(uc.REASONS)
    assert body["shown_size"] + sum(counts.values()) == 100
    assert body["excluded"]["below_volume_floor"] == 0 and body["excluded"]["exclusion_list"] == 24
    shown = {c["symbol"]: c for n in body["categories"] for c in n["coins"]}
    assert {"LEO", "CRO", "GT", "PI", "NEXO", "BNB"} <= set(shown)
    assert shown["LEO"]["thin_volume"] is True and shown["LEO"]["tradeability"] == "unverified"
    assert shown["BTC"]["thin_volume"] is False and shown["BTC"]["volume_24h"] == 16391057565


def test_leo_cro_gt_pi_nexo_shown_without_force_include(snap):
    c = disc.load_config()
    assert c["universe_rules"]["force_include"] == []
    assert {"LEO", "CRO", "GT", "PI", "NEXO"} <= set(disc.eligibility(c, snap).eligible)


def test_discovery_on_fixture_with_zero_volume_fund_and_failed_venue_file(snap, isolated_cache, tmp_path, monkeypatch):
    """The 18-10 fixture plus a JAAA-like zero-volume fund (not in any class), a failed Binance store file and a
    fresh Hyperliquid perp list: JAAA is the only new exclusion; coins off Hyperliquid stay in, unverified."""
    from api.data import cache
    from api.data.attention import universe_store
    assert snap[-1]["symbol"] == "EUTBL"   # the 100th coin (a tokenized fund) makes room for JAAA at its cap
    rows = [*snap[:-1], {"id": "janus-henderson-anemoy-aaa-clo-fund", "symbol": "JAAA",
                         "market_cap": snap[-1]["market_cap"], "volume_24h": 0}]
    universe_store.write_snapshot("2026-10-19", rows)   # newer than the fixture copy
    hl = [r["symbol"] for r in snap if r["symbol"] not in {"LEO", "CRO", "GT", "PEPE", "SHIB"}] + ["kPEPE", "kSHIB"]
    cache.write_exchange_market_snapshot((TODAY - timedelta(days=1)).isoformat(), hl)
    failed = cache.CACHE_ROOT.joinpath(*tm.MARKETS_DIR, "binance", f"{TODAY.isoformat()}.json")
    failed.parent.mkdir(parents=True, exist_ok=True)
    failed.write_text(json.dumps({"venue": "binance", "status": "failed", "reason": "HTTP 451"}))
    probe = tmp_path / "probe.json"
    probe.write_text(json.dumps({s: {"probed": True} for s in ("wikipedia", "coingecko", "trends")}))
    monkeypatch.setattr(registry, "PROBE_RECORDS_PATH", probe)
    for s in shipped(snap).eligible:
        gain(s)
    res = disc.build_discovery(30, today=TODAY)
    out = {c.symbol: (c.reason, c.detail) for c in res.excluded_coins}
    assert out["JAAA"] == ("not-tradeable", "zero 24h volume") and res.excluded_counts["not-tradeable"] == 1
    assert res.universe_size == 100 and res.eligible_size == 76 and res.excluded_counts["no-market"] == 7
    assert res.shown_size + sum(res.excluded_counts.values()) == res.universe_size
    assert res.excluded.exclusion_list == 16 + 7 + 1
    shown = {c.symbol: c for n in res.categories for c in n.coins}
    assert {"LEO", "CRO", "GT"} <= set(shown)
    assert {s: shown[s].tradeability for s in ("LEO", "PEPE", "SHIB", "BTC")} == {
        "LEO": "unverified", "PEPE": "tradeable", "SHIB": "tradeable", "BTC": "tradeable"}
    assert res.tradeability_unknown == sum(c.tradeability == "unverified" for c in shown.values()) >= 3
    assert [(v.venue, v.status) for v in res.venue_lists] == [("binance", "failed"), ("hyperliquid", "ok")]
