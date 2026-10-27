"""T189: venue lists and the per-symbol tradeability answer. Stored files only (isolated cache), no network."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from api.data import cache
from api.data.attention import store
from api.data.attention import tradeable_markets as tm
from api.data.attention.types import SourceSeries

TODAY = date(2026, 10, 26)


def ok(venue: str, volumes: dict) -> tm.VenueList:
    return tm.VenueList(venue, "ok", TODAY.isoformat(), volumes)


def gone(venue: str, state: str = "missing") -> tm.VenueList:
    return tm.VenueList(venue, state)


def both(binance: tm.VenueList, hyperliquid: tm.VenueList) -> dict:
    return {"binance": binance, "hyperliquid": hyperliquid}


def filler(venue: str, n: int | None = None) -> list[str]:
    """Distinct padding symbols so a test list reaches the venue's sanity minimum."""
    return [f"ZZFILL{i}" for i in range(tm.MIN_SYMBOLS[venue] if n is None else n)]


def real(vl: tm.VenueList) -> dict:
    return {k: v for k, v in vl.volumes.items() if not k.startswith("ZZFILL")}


def write_hl_list(names, day: date, pad: bool = True) -> None:
    cache.write_exchange_market_snapshot(day.isoformat(), list(names) + (filler("hyperliquid") if pad else []))


def write_hl_volume(symbol: str, day: date, value: float) -> None:
    store.write_series(SourceSeries(tm.HL_VOLUME_SOURCE, symbol, [(day, value)], "ok"), today=day + timedelta(days=1))


def write_store(venue: str, day: date, doc, pad: bool = True) -> Path:
    if pad and isinstance(doc, dict) and isinstance(doc.get("markets"), list):
        doc = {**doc, "markets": doc["markets"] + [{"symbol": s, "kind": "perp", "volume_24h": 1.0}
                                                   for s in filler(venue)]}
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
    assert real(hl) == {"BTC": 1e9, "PEPE": 4e6, "DEAD": 0.0, "NOVOL": None}
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
    assert real(tm.load_venues(TODAY)["hyperliquid"]) == {"ETH": None}


def test_stale_after_two_days(isolated_cache):
    write_hl_list(["BTC"], TODAY - timedelta(days=tm.STALE_AFTER_DAYS))
    assert tm.load_venues(TODAY)["hyperliquid"].state == "ok"
    assert tm.load_venues(TODAY + timedelta(days=1))["hyperliquid"].state == "stale"


def test_point_in_time_ignores_lists_dated_after_today(isolated_cache):
    write_hl_list(["BTC"], TODAY + timedelta(days=1))
    assert tm.load_venues(TODAY)["hyperliquid"].state == "missing"
    write_hl_list(["ETH"], TODAY - timedelta(days=1))
    assert set(real(tm.load_venues(TODAY)["hyperliquid"])) == {"ETH"}


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
    assert (b.state, real(b)) == ("ok", {"PEPE": 9e6, "LEO": None, "OLD": 0.0})


def test_markets_store_wins_over_the_narrative_list_for_hyperliquid(isolated_cache):
    write_hl_list(["BTC"], TODAY)
    write_store("hyperliquid", TODAY, {"status": "ok", "markets": [{"symbol": "ETH", "kind": "spot",
                                                                   "volume_24h": 1.0}]})
    assert real(tm.load_venues(TODAY)["hyperliquid"]) == {"ETH": 1.0}


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


# ---- Round 2 (T191 review): sanity minimum, invalid volumes, as_of staleness ---------------------------------

@pytest.mark.parametrize("n,state", [(0, "failed"), (3, "failed"), (tm.MIN_SYMBOLS["hyperliquid"] - 1, "failed"),
                                     (tm.MIN_SYMBOLS["hyperliquid"], "ok")])
def test_hyperliquid_list_below_the_minimum_is_failed(isolated_cache, n, state):
    write_hl_list(filler("hyperliquid", n), TODAY, pad=False)
    assert tm.load_venues(TODAY)["hyperliquid"].state == state


@pytest.mark.parametrize("n,state", [(0, "failed"), (3, "failed"), (tm.MIN_SYMBOLS["binance"] - 1, "failed"),
                                     (tm.MIN_SYMBOLS["binance"], "ok")])
def test_store_list_below_the_minimum_is_failed(isolated_cache, n, state):
    write_store("binance", TODAY, {"status": "ok", "markets": [{"symbol": s, "volume_24h": 1.0}
                                                               for s in filler("binance", n)]}, pad=False)
    assert tm.load_venues(TODAY)["binance"].state == state


def test_minimum_counts_distinct_coins_not_rows(isolated_cache):
    rows = [{"symbol": s, "kind": k, "volume_24h": 1.0} for s in filler("binance", tm.MIN_SYMBOLS["binance"] - 1)
            for k in ("spot", "perp")]
    write_store("binance", TODAY, {"status": "ok", "markets": rows}, pad=False)
    assert tm.load_venues(TODAY)["binance"].state == "failed"


def test_one_venue_sane_one_empty_is_unknown_never_no_market(isolated_cache):
    write_store("binance", TODAY, {"status": "ok", "markets": []}, pad=False)
    write_hl_list(["BTC"], TODAY)
    v = tm.load_venues(TODAY)
    assert (v["binance"].state, v["hyperliquid"].state) == ("failed", "ok")
    assert tm.tradeability("LEO", v, 3e6) == tm.Verdict("unknown", "Binance list failed")
    assert tm.tradeability("BTC", v).status == "tradeable"


def test_both_venues_empty_excludes_nothing(isolated_cache):
    write_store("binance", TODAY, {"status": "ok", "markets": []}, pad=False)
    write_store("hyperliquid", TODAY, {"status": "ok", "markets": [{"symbol": "BTC", "volume_24h": 1.0}]}, pad=False)
    v = tm.load_venues(TODAY)
    assert {x.state for x in v.values()} == {"failed"}
    assert tm.tradeability("ETH", v, 5e8).status == "unknown"


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "-5", '"abc"', "true", "[]"])
def test_invalid_store_volume_gives_unknown_for_that_coin(isolated_cache, bad):
    pad = ",".join(f'{{"symbol": "{s}", "volume_24h": 1.0}}' for s in filler("binance"))
    write_store("binance", TODAY, f'{{"status": "ok", "markets": [{pad}, {{"symbol": "LEO", "volume_24h": {bad}}},'
                                  f' {{"symbol": "PEPE", "volume_24h": {bad}}}, {{"symbol": "PEPE", "volume_24h": 2.0}}]}}')
    write_hl_list(["BTC"], TODAY)
    v = tm.load_venues(TODAY)
    assert v["binance"].state == "ok" and "LEO" not in v["binance"].volumes and "LEO" in v["binance"].invalid
    assert tm.tradeability("LEO", v, 3e6) == tm.Verdict("unknown", "Binance volume invalid")
    assert tm.tradeability("PEPE", v).status == "tradeable"     # a valid market of the same coin still counts
    assert tm.tradeability("JAAA", v, 0) == tm.Verdict("not_tradeable", tm.ZERO_VOLUME)


def test_missing_or_null_store_volume_is_listed_not_invalid(isolated_cache):
    write_store("binance", TODAY, {"status": "ok", "markets": [{"symbol": "LEO"}, {"symbol": "CRO", "volume_24h": None}]})
    b = tm.load_venues(TODAY)["binance"]
    assert real(b) == {"LEO": None, "CRO": None} and not b.invalid


def test_stale_as_of_with_a_fresh_file_name_is_stale(isolated_cache):
    old = (TODAY - timedelta(days=tm.STALE_AFTER_DAYS + 1)).isoformat()
    write_store("binance", TODAY, {"status": "ok", "as_of": old, "markets": [{"symbol": "LEO", "volume_24h": 1.0}]})
    b = tm.load_venues(TODAY)["binance"]
    assert (b.state, b.as_of) == ("stale", old)


def test_fresh_as_of_two_days_old_is_ok_and_absent_as_of_uses_the_file_date(isolated_cache):
    edge = (TODAY - timedelta(days=tm.STALE_AFTER_DAYS)).isoformat()
    write_store("binance", TODAY, {"status": "ok", "as_of": edge, "markets": []})
    assert tm.load_venues(TODAY)["binance"].state == "ok"
    write_store("hyperliquid", TODAY, {"status": "ok", "markets": []})
    assert (tm.load_venues(TODAY)["hyperliquid"].state, tm.load_venues(TODAY)["hyperliquid"].as_of) == (
        "ok", TODAY.isoformat())


@pytest.mark.parametrize("as_of", ["yesterday", 20261026, None])
def test_unreadable_as_of_is_failed(isolated_cache, as_of):
    write_store("binance", TODAY, {"status": "ok", "as_of": as_of, "markets": []})
    assert tm.load_venues(TODAY)["binance"].state == "failed"


def test_as_of_after_the_file_date_does_not_make_a_stale_file_fresh(isolated_cache):
    day = TODAY - timedelta(days=tm.STALE_AFTER_DAYS + 1)
    write_store("binance", day, {"status": "ok", "as_of": TODAY.isoformat(), "markets": []})
    assert tm.load_venues(TODAY)["binance"].state == "stale"


def test_invalid_volume_beside_a_zero_volume_market_is_unknown_not_no_market(isolated_cache):
    pad = ",".join(f'{{"symbol": "{s}", "volume_24h": 1.0}}' for s in filler("binance"))
    write_store("binance", TODAY, f'{{"status": "ok", "markets": [{pad}, {{"symbol": "LEO", "kind": "spot", '
                                  f'"volume_24h": 0}}, {{"symbol": "LEO", "kind": "perp", "volume_24h": NaN}}]}}')
    write_hl_list(["BTC"], TODAY)
    v = tm.load_venues(TODAY)
    assert v["binance"].volumes["LEO"] == 0.0 and "LEO" in v["binance"].invalid
    assert tm.tradeability("LEO", v, 3e6) == tm.Verdict("unknown", "Binance volume invalid")
