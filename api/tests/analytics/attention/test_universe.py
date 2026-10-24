import json

from api.analytics.attention import universe
from api.analytics.attention.universe import load_reference, load_universe
from api.data.attention import universe_store


def _cfg(tmp_path, **kw):
    base = {"reference": [], "stablecoins": ["USDT"], "wrapped": ["WBTC"], "exchange_tokens": ["BNB"]}
    base.update(kw)
    p = tmp_path / "u.json"
    p.write_text(json.dumps(base))
    return p


def _coin(sym, cap):
    return {"id": sym.lower(), "symbol": sym, "market_cap": cap, "volume_24h": 1}


def test_snapshot_used_sorted_and_exclusions_applied(isolated_cache, tmp_path):
    universe_store.write_snapshot("2026-10-01", [
        _coin("ETH", 50), _coin("BTC", 100), _coin("USDT", 90), _coin("BNB", 40),
        _coin("WBTC", 30), _coin("SOL", 20)])
    syms, reason = load_universe(_cfg(tmp_path))
    assert syms == ["BTC", "ETH", "SOL"] and reason == "snapshot"


def test_cut_at_100_before_exclusions(isolated_cache, tmp_path):
    coins = [_coin(f"X{i}", 1000 - i) for i in range(99)] + [_coin("USDT", 500), _coin("LATE", 1)]
    universe_store.write_snapshot("2026-10-01", coins)
    syms, _ = load_universe(_cfg(tmp_path))
    assert len(syms) == 99 and "LATE" not in syms and "USDT" not in syms


def test_override_wins_over_snapshot(isolated_cache, tmp_path):
    universe_store.write_snapshot("2026-10-01", [_coin("BTC", 1)])
    syms, reason = load_universe(_cfg(tmp_path, reference=["eth", "SOL", "usdt"]))
    assert syms == ["ETH", "SOL"] and reason == "override"


def test_missing_snapshot_and_corrupt_config(isolated_cache, tmp_path):
    assert load_universe(_cfg(tmp_path)) == ([], "reference-missing")
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    assert load_universe(bad) == ([], "reference-missing")
    assert load_universe(tmp_path / "absent.json") == ([], "reference-missing")


def test_load_reference_still_returns_list(isolated_cache, tmp_path):
    universe_store.write_snapshot("2026-10-01", [_coin("BTC", 2), _coin("ETH", 1)])
    assert load_reference(_cfg(tmp_path)) == ["BTC", "ETH"]
    assert universe.load_reference(tmp_path / "absent.json") == []


def test_shipped_config_has_exchange_tokens():
    cfg = json.loads(universe.UNIVERSE_PATH.read_text())
    assert cfg["exchange_tokens"] == ["LEO", "OKB", "CRO", "GT", "KCS", "BGB", "MX"]
