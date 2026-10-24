"""T115 U2: reasoned exclusion, label-only volume, exchange tokens IN. Fixture = a COPY of the 2026-10-18 universe
snapshot (F14); the live nightly cache is never read. Shipped config and narratives file, read-only."""
from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from api.analytics.attention import discovery as disc, sources as src, universe_classes as uc
from api.analytics.attention import universe as universe_mod
from api.data.attention import registry
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


def test_failed_venue_list_is_unknown_coin_stays_in():
    rows = [{"symbol": s} for s in ("BTC", "ETH")]
    partial = {"binance": {"BTC"}, "coinbase": None, "kraken": set(), "hyperliquid": set()}
    u = shipped(rows, partial)
    assert u.eligible == ["BTC", "ETH"] and u.tradeability == {"BTC": "tradeable", "ETH": "unverified"}
    assert uc.tradeability("ETH", partial) == "unknown"
    # every list built and none has it: no-market (U5); the stub has no lists, so nothing is cut today
    u = shipped(rows, {"binance": {"BTC"}, "coinbase": set(), "kraken": set(), "hyperliquid": set()})
    assert u.eligible == ["BTC"] and u.out["ETH"][0] == "no-market"
    assert set(uc.venue_lists().values()) == {None} and shipped(rows).tradeability == {
        "BTC": "unverified", "ETH": "unverified"}


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
    coins = {"USDT": 5e7, "W": 5e7, "F": 0, "X": 5e7, "NOCAT": 5e7, "HID": 5e7, "NODATA": 5e7, "A": 5e7, "B": None}
    world(tmp_path, monkeypatch, coins, cats={"ai": ["USDT", "W", "F", "X", "NODATA", "A", "B"], "defi": ["HID"]},
          min_narrative_coins=2, rules={"classes": {"stablecoin": ["USDT"], "wrapped_staked": ["W"],
                                                    "tokenized_fund": ["F"]}, "not_tradeable": {"X": "no venue"}})
    gain("A"), gain("B"), gain("HID")
    res = disc.build_discovery(30, today=TODAY)
    assert res.excluded_counts == {"stablecoin": 1, "wrapped-staked": 1, "no-market": 1, "not-tradeable-config": 1,
                                   "unassigned": 1, "hidden-narrative": 1, "no-source-data": 1}
    assert res.shown_size == 2 and res.universe_size == 9
    assert res.shown_size + sum(res.excluded_counts.values()) == res.universe_size
    assert {c.symbol: c.reason for c in res.excluded_coins}["HID"] == "hidden-narrative"
    assert res.excluded.model_dump() == {"exclusion_list": 4, "below_volume_floor": 0, "no_category": 2,
                                         "no_source_data": 1}


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
