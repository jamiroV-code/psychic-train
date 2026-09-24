"""RFC-2: exchange attention maths + cache round-trips. isolated_cache only."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import pytest

from api.analytics.narrative import exchange_attention as ea
from api.data import cache, hyperliquid_narrative_adapter as hl

MAP = {"BTC": "store-of-value", "PEPE": "memecoins", "DOGE": "memecoins", "FET": "ai", "OM": "rwa"}


def perps(**vols):
    return [hl.PerpMarket(base=n.upper(), base_name=n, quote_volume=v) for n, v in vols.items()]


def snap(date="2026-09-24", **vols):
    return hl.ExchangeSnapshotResult(status="ok", as_of=date, perps=perps(**vols))


def test_k_prefix_resolution_and_no_market_is_explicit():
    ps = perps(BTC=1.0, kPEPE=1.0, FET=1.0)
    assert ea.resolve_symbol("PEPE", ps).base_name == "kPEPE"
    assert ea.resolve_symbol("btc", ps).base_name == "BTC"
    assert ea.resolve_symbol("OM", ps) is None
    r = ea.compute_exchange_attention(snap(BTC=1.0, kPEPE=1.0, FET=1.0), MAP, None)
    coins = {c.symbol: c for c in r.coins}
    assert coins["PEPE"].market == "kPEPE" and coins["PEPE"].status == "ok"
    assert coins["OM"].status == "unavailable" and coins["OM"].reason == "no-hyperliquid-market"
    assert coins["DOGE"].reason == "no-hyperliquid-market"
    assert set(coins) == set(MAP)  # nothing silently dropped
    rwa = r.categories["rwa"]
    assert rwa.volume_share is None and rwa.volume_reason == "no-hyperliquid-market"


def test_golden_volume_share_denominator_is_all_perps():
    r = ea.compute_exchange_attention(snap(BTC=600.0, kPEPE=100.0, DOGE=50.0, FET=150.0, SOL=100.0), MAP, None)
    c = r.categories
    assert c["store-of-value"].volume_share == pytest.approx(0.6)
    assert c["memecoins"].volume_share == pytest.approx(0.15)
    assert c["ai"].volume_share == pytest.approx(0.15)
    assert c["unmapped"].volume_share == pytest.approx(0.10)  # SOL is in the total
    total = sum(x.volume_share for x in c.values() if x.volume_share is not None)
    assert total == pytest.approx(1.0)


def test_none_volume_excluded_not_zeroed_and_zero_total_unavailable():
    r = ea.compute_exchange_attention(snap(BTC=100.0, FET=None), MAP, None)
    assert r.categories["ai"].volume_share == 0.0 and r.categories["ai"].volume_status == "ok"
    r0 = ea.compute_exchange_attention(snap(BTC=0.0, FET=None), MAP, None)
    assert all(x.volume_share is None and x.volume_reason == "zero-total-volume" for x in r0.categories.values())


def test_failed_snapshot_makes_everything_unavailable_never_zero():
    bad = hl.ExchangeSnapshotResult(status="unavailable", as_of="2026-09-24", reason="fetch-failed: RequestTimeout")
    r = ea.compute_exchange_attention(bad, MAP, ("2026-09-23", ["BTC"]))
    assert r.status == "unavailable"
    for x in r.categories.values():
        assert x.volume_share is None and x.new_listing_count is None
        assert x.volume_status == x.listing_status == "unavailable"


def test_day1_no_baseline_is_null_not_zero():
    r = ea.compute_exchange_attention(snap(BTC=1.0), MAP, None)
    for x in r.categories.values():
        assert x.new_listing_count is None
        assert x.listing_status == "unavailable" and x.listing_reason == "no-baseline-yet"
        assert x.baseline_date is None


def test_genuine_zero_diff_is_ok_zero_and_distinguishable():
    r = ea.compute_exchange_attention(snap(BTC=1.0, FET=1.0), MAP, ("2026-09-23", ["BTC", "FET"]))
    ai = r.categories["ai"]
    assert ai.new_listing_count == 0 and ai.listing_status == "ok" and ai.baseline_date == "2026-09-23"


def test_new_listing_diff_attribution_and_unmapped_bucket():
    r = ea.compute_exchange_attention(
        snap(BTC=1.0, kPEPE=1.0, FET=1.0, NEWCOIN=1.0), MAP, ("2026-09-20", ["BTC"])
    )
    c = r.categories
    assert c["memecoins"].new_listing_count == 1 and c["memecoins"].new_listings == ["kPEPE"]
    assert c["ai"].new_listing_count == 1
    assert c["unmapped"].new_listing_count == 1 and c["unmapped"].new_listings == ["NEWCOIN"]
    assert c["store-of-value"].new_listing_count == 0
    assert all(x.baseline_date == "2026-09-20" for x in c.values())


class FakeEx:
    def __init__(self, names):
        self.names = names

    def fetch_tickers(self, symbols=None, params={}):
        return {f"{n.upper()}/USDC:USDC": {"quoteVolume": 10.0, "info": {"name": n}} for n in self.names}


def test_run_daily_round_trip_through_real_cache(isolated_cache):
    day1 = datetime(2026, 9, 23, 23, 59, 59, tzinfo=timezone.utc)
    day2 = datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc)
    r1 = ea.run_daily(exchange=FakeEx(["BTC", "FET"]), now=day1, category_map=MAP)
    assert r1.as_of == "2026-09-23"
    assert cache.read_exchange_market_snapshot("2026-09-23") == ["BTC", "FET"]
    s = cache.read_exchange_series("ai")
    assert len(s) == 1 and pd.isna(s.iloc[0]["new_listing_count"])
    assert s.iloc[0]["listing_reason"] == "no-baseline-yet"

    r2 = ea.run_daily(exchange=FakeEx(["BTC", "FET", "kPEPE"]), now=day2, category_map=MAP)
    assert r2.as_of == "2026-09-24"  # one second later, a different UTC day
    assert r2.categories["memecoins"].new_listing_count == 1
    mem = cache.read_exchange_series("memecoins")
    assert list(mem["date"].astype(str)) == ["2026-09-23", "2026-09-24"]
    assert int(mem.iloc[1]["new_listing_count"]) == 1 and mem.iloc[1]["baseline_date"] == "2026-09-23"
    assert mem.iloc[1]["volume_share"] == pytest.approx(1 / 3)
    assert (isolated_cache / "narrative" / "exchange" / "markets" / "2026-09-24.json").exists()


def test_same_day_rerun_is_append_only(isolated_cache):
    now = datetime(2026, 9, 24, 8, tzinfo=timezone.utc)
    ea.run_daily(exchange=FakeEx(["BTC"]), now=now, category_map=MAP)
    ea.run_daily(exchange=FakeEx(["BTC", "FET"]), now=now, category_map=MAP)
    assert cache.read_exchange_market_snapshot("2026-09-24") == ["BTC"]
    assert len(cache.read_exchange_series("store-of-value")) == 1
    assert cache.write_exchange_market_snapshot("2026-09-24", ["X"]) is False


def test_baseline_is_latest_earlier_snapshot_across_gap(isolated_cache):
    cache.write_exchange_market_snapshot("2026-09-18", ["BTC"])
    cache.write_exchange_market_snapshot("2026-09-20", ["BTC", "FET"])
    cache.write_exchange_market_snapshot("2026-09-25", ["BTC"])  # future: ignored
    assert ea.latest_baseline_before("2026-09-24") == ("2026-09-20", ["BTC", "FET"])
    assert ea.latest_baseline_before("2026-09-18") is None


def test_symbols_read_from_map_at_run_time(isolated_cache, monkeypatch):
    calls = []
    monkeypatch.setattr(ea.mapping, "load_category_map", lambda: calls.append(1) or {"WIF": "memecoins"})
    r = ea.run_daily(exchange=FakeEx(["WIF"]), now=datetime(2026, 9, 24, tzinfo=timezone.utc))
    assert calls and r.categories["memecoins"].volume_share == 1.0


def test_real_map_file_loads_and_resolves_thousand_unit_coins():
    from api.analytics.narrative import mapping

    cmap = mapping.load_category_map()
    r = ea.compute_exchange_attention(snap(kPEPE=1.0, kBONK=1.0, kSHIB=1.0), cmap, None)
    got = {c.symbol: c.market for c in r.coins if c.market}
    assert got == {"PEPE": "kPEPE", "BONK": "kBONK", "SHIB": "kSHIB"}


def test_display_only_not_imported_by_trigger_or_screener():
    import pathlib

    root = pathlib.Path(ea.__file__).resolve().parents[2]
    for rel in ["analytics/narrative/trigger.py", "analytics/screener_board.py", "routers/narrative.py"]:
        text = (root / rel).read_text(encoding="utf-8")
        assert "exchange_attention" not in text and "hyperliquid_narrative_adapter" not in text
