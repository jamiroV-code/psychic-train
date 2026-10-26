"""T189: venue lists and the per-symbol tradeability answer. Stored files only (isolated cache), no network."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from api.data import cache
from api.data.attention import store, tradeable_markets as tm
from api.data.attention.types import SourceSeries

TODAY = date(2026, 10, 26)


def ok(venue: str, volumes: dict) -> tm.VenueList:
    return tm.VenueList(venue, "ok", TODAY.isoformat(), volumes)


def gone(venue: str, state: str = "missing") -> tm.VenueList:
    return tm.VenueList(venue, state)


def both(binance: tm.VenueList, hyperliquid: tm.VenueList) -> dict:
    return {"binance": binance, "hyperliquid": hyperliquid}


def write_hl_list(names, day: date) -> None:
    cache.write_exchange_market_snapshot(day.isoformat(), list(names))


def write_hl_volume(symbol: str, day: date, value: float) -> None:
    store.write_series(SourceSeries(tm.HL_VOLUME_SOURCE, symbol, [(day, value)], "ok"), today=day + timedelta(days=1))


def write_store(venue: str, day: date, doc) -> Path:
    path = cache.CACHE_ROOT.joinpath(*tm.MARKETS_DIR, venue, f"{day.isoformat()}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc if isinstance(doc, str) else json.dumps(doc))
    return path


# ---- aliases and case folding -------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,sym", [("kPEPE", "PEPE"), ("KPEPE", "PEPE"), ("kSHIB", "SHIB"), ("1000PEPE", "PEPE"),
                                     ("1000SHIB", "SHIB"), ("1MBABYDOGE", "BABYDOGE"), ("pepe", "PEPE"),
                                     (" btc ", "BTC"), ("KAS", "KAS"), ("KAITO", "KAITO"), ("kNEIRO", "NEIRO")])
def test_alias_and_case_folding(raw, sym):
    assert tm.canonical(raw) == sym


def test_alias_table_is_reviewed_and_never_maps_a_name_to_itself():
    assert all(k == k.upper() and v == v.upper() and k != v for k, v in tm.ALIASES.items())
    # a k-prefix is never stripped generically: real coins start with K
    assert "KAS" not in tm.ALIASES and "KAITO" not in tm.ALIASES


def test_hyperliquid_scaled_names_kpepe_matches_pepe():
    v = both(gone("binance"), ok("hyperliquid", {tm.canonical("kPEPE"): 5e6, tm.canonical("kSHIB"): None}))
    assert tm.tradeability("PEPE", v) == tm.Verdict("tradeable")
    assert tm.tradeability("shib", v) == tm.Verdict("tradeable")


# ---- the per-symbol answer ------------------------------------------------------------------------------------

def test_symbol_on_only_one_venue_is_tradeable():
    v = both(ok("binance", {"BTC": 1e9}), ok("hyperliquid", {"ETH": 1e9}))
    assert tm.tradeability("BTC", v).status == "tradeable" and tm.tradeability("ETH", v).status == "tradeable"


def test_listed_without_stored_volume_counts_as_tradeable():
    assert tm.tradeability("AAA", both(gone("binance"), ok("hyperliquid", {"AAA": None}))).status == "tradeable"


def test_missing_venue_gives_unknown_never_not_tradeable():
    v = both(gone("binance"), ok("hyperliquid", {"BTC": 1e9}))
    assert tm.tradeability("LEO", v, 3e6) == tm.Verdict("unknown", "Binance list missing")
    assert tm.tradeability("LEO", v, None).status == "unknown"


def test_every_list_fresh_and_none_has_it_is_no_market():
    v = both(ok("binance", {"BTC": 1e9}), ok("hyperliquid", {"BTC": 1e9}))
    assert tm.tradeability("JAAA", v, 5e6) == tm.Verdict("not_tradeable", tm.NO_MARKET)


def test_zero_volume_on_every_listing_is_no_market():
    v = both(ok("binance", {"DEAD": 0.0}), ok("hyperliquid", {"DEAD": 0.0}))
    assert tm.tradeability("DEAD", v, 5e6) == tm.Verdict("not_tradeable", tm.NO_MARKET)


def test_zero_snapshot_volume_is_not_tradeable_even_with_lists_missing():
    v = both(gone("binance"), gone("hyperliquid", "failed"))
    assert tm.tradeability("JAAA", v, 0) == tm.Verdict("not_tradeable", tm.ZERO_VOLUME)
    assert tm.tradeability("JAAA", v, 0.0) == tm.Verdict("not_tradeable", tm.ZERO_VOLUME)


def test_null_or_bad_snapshot_volume_is_not_zero():
    v = both(gone("binance"), gone("hyperliquid"))
    for vol in (None, False, float("nan"), -1.0):
        assert tm.tradeability("X", v, vol).status == "unknown"


def test_positive_venue_volume_beats_a_zero_snapshot_volume():
    v = both(gone("binance"), ok("hyperliquid", {"X": 2e6}))
    assert tm.tradeability("X", v, 0).status == "tradeable"


@pytest.mark.parametrize("state", ["stale", "failed", "missing"])
def test_stale_or_failed_venue_proves_nothing(state):
    """A non-fresh list neither confirms a market nor rules one out."""
    listed = tm.VenueList("binance", state, "2026-10-20", {"LEO": 1e7})
    v = both(listed, ok("hyperliquid", {"BTC": 1e9}))
    assert tm.tradeability("LEO", v, 3e6) == tm.Verdict("unknown", f"Binance list {state}")
    assert tm.tradeability("BTC", v).status == "tradeable"


def test_all_lists_missing_names_both():
    assert tm.tradeability("X", {}, 1.0) == tm.Verdict("unknown", "Binance list missing; Hyperliquid list missing")


# ---- loading the stored lists ---------------------------------------------------------------------------------

def test_nothing_stored_is_missing_for_both(isolated_cache):
    v = tm.load_venues(TODAY)
    assert {k: x.state for k, x in v.items()} == {"binance": "missing", "hyperliquid": "missing"}


def test_hyperliquid_perp_list_with_stored_volume(isolated_cache):
    day = TODAY - timedelta(days=1)
    write_hl_list(["BTC", "kPEPE", "DEAD", "NOVOL"], day)
    write_hl_volume("BTC", day, 1e9)
    write_hl_volume("PEPE", day, 4e6)
    write_hl_volume("DEAD", day, 0.0)
    v = tm.load_venues(TODAY)
    hl = v["hyperliquid"]
    assert (hl.state, hl.as_of) == ("ok", day.isoformat())
    assert hl.volumes == {"BTC": 1e9, "PEPE": 4e6, "DEAD": 0.0, "NOVOL": None}
    assert v["binance"].state == "missing"
    assert tm.tradeability("PEPE", v).status == "tradeable"
    assert tm.tradeability("DEAD", v, 1e6).status == "unknown"   # zero on HL, Binance unknown: kept


def test_symbols_limit_volume_reads_not_the_listing(isolated_cache):
    day = TODAY - timedelta(days=1)
    write_hl_list(["BTC", "ETH"], day)
    write_hl_volume("ETH", day, 0.0)
    hl = tm.load_venues(TODAY, symbols=["btc"])["hyperliquid"]
    assert hl.volumes == {"BTC": None}


def test_old_hyperliquid_volume_is_not_used(isolated_cache):
    day = TODAY - timedelta(days=1)
    write_hl_list(["ETH"], day)
    write_hl_volume("ETH", day - timedelta(days=tm.STALE_AFTER_DAYS + 1), 0.0)
    assert tm.load_venues(TODAY)["hyperliquid"].volumes == {"ETH": None}


def test_stale_after_two_days(isolated_cache):
    write_hl_list(["BTC"], TODAY - timedelta(days=tm.STALE_AFTER_DAYS))
    assert tm.load_venues(TODAY)["hyperliquid"].state == "ok"
    assert tm.load_venues(TODAY + timedelta(days=1))["hyperliquid"].state == "stale"


def test_point_in_time_ignores_lists_dated_after_today(isolated_cache):
    write_hl_list(["BTC"], TODAY + timedelta(days=1))
    assert tm.load_venues(TODAY)["hyperliquid"].state == "missing"
    write_hl_list(["ETH"], TODAY - timedelta(days=1))
    assert set(tm.load_venues(TODAY)["hyperliquid"].volumes) == {"ETH"}


def test_unreadable_hyperliquid_list_is_failed(isolated_cache):
    path = cache.exchange_market_snapshot_path(TODAY.isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json")
    assert tm.load_venues(TODAY)["hyperliquid"].state == "failed"


def test_markets_store_contract_merges_spot_and_perp(isolated_cache):
    write_store("binance", TODAY, {"venue": "binance", "as_of": TODAY.isoformat(), "status": "ok", "markets": [
        {"symbol": "PEPE", "kind": "spot", "volume_24h": 0.0},
        {"symbol": "1000PEPE", "kind": "perp", "volume_24h": 9e6},
        {"symbol": "LEO", "kind": "spot", "volume_24h": None},
        {"symbol": "OLD", "kind": "spot", "volume_24h": 0}]})
    b = tm.load_venues(TODAY)["binance"]
    assert (b.state, b.volumes) == ("ok", {"PEPE": 9e6, "LEO": None, "OLD": 0.0})


def test_markets_store_wins_over_the_narrative_list_for_hyperliquid(isolated_cache):
    write_hl_list(["BTC"], TODAY)
    write_store("hyperliquid", TODAY, {"status": "ok", "markets": [{"symbol": "ETH", "kind": "spot",
                                                                   "volume_24h": 1.0}]})
    assert tm.load_venues(TODAY)["hyperliquid"].volumes == {"ETH": 1.0}


@pytest.mark.parametrize("doc", [{"status": "failed", "reason": "HTTP 451"}, {"status": "ok"}, "{bad",
                                 {"status": "failed", "markets": [{"symbol": "LEO", "volume_24h": 1e7}]},
                                 {"status": "ok", "markets": [{"kind": "spot"}]}, "[]"])
def test_failed_or_malformed_store_file_is_failed_never_no_market(isolated_cache, doc):
    write_store("binance", TODAY, doc)
    write_store("hyperliquid", TODAY, {"status": "ok", "markets": [{"symbol": "BTC", "volume_24h": 1.0}]})
    v = tm.load_venues(TODAY)
    assert v["binance"].state == "failed"
    assert tm.tradeability("LEO", v, 3e6) == tm.Verdict("unknown", "Binance list failed")


def test_stale_store_file(isolated_cache):
    write_store("binance", TODAY - timedelta(days=3), {"status": "ok", "markets": []})
    assert tm.load_venues(TODAY)["binance"].state == "stale"


def test_module_has_no_network_code():
    src = Path(tm.__file__).read_text()
    assert not any(word in src for word in ("httpx", "ccxt", "requests", "urllib", "socket"))
