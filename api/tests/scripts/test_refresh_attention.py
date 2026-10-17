import hashlib
from datetime import timedelta
from pathlib import Path

import httpx

from api.data.attention import store
from api.scripts import refresh_attention
from api.tests.data.attention.conftest import TODAY, chart_payload, wiki_payload

MARKETS = [{"id": "bitcoin", "symbol": "btc", "market_cap": 1}, {"id": "ethereum", "symbol": "eth", "market_cap": 2}]


def _handler(wiki_status=200, cg_status=200):
    def h(r: httpx.Request):
        u = str(r.url)
        if "wikimedia" in u:
            return httpx.Response(wiki_status, json=wiki_payload(100))
        if "coins/markets" in u:
            return httpx.Response(cg_status, json=MARKETS)
        if "market_chart" in u:
            return httpx.Response(cg_status, json=chart_payload(100))
        return httpx.Response(404)
    return h


def _run(argv, handler, **kw):
    c = httpx.Client(transport=httpx.MockTransport(handler))
    return refresh_attention.main(argv, client=c, today=TODAY, sleep=lambda x: None, **kw)


def test_run_writes_store_and_exit_0(isolated_cache):
    assert _run(["--symbols", "BTC,ETH"], _handler()) == 0
    assert len(store.read_points("wikipedia", "BTC")) == 100
    assert len(store.read_points("coingecko", "ETH")) == 99
    assert all(d < TODAY for d, _ in store.read_points("wikipedia", "BTC"))


def test_dry_run_writes_nothing_and_makes_no_network_call(isolated_cache):
    calls = []

    def fail_if_called(r: httpx.Request):
        calls.append(str(r.url))
        raise AssertionError("dry run must not call the network")

    assert _run(["--dry-run", "--symbols", "BTC"], fail_if_called) == 0
    assert calls == []
    assert not (isolated_cache / "attention").exists()


def test_sources_filter(isolated_cache):
    assert _run(["--sources", "wikipedia", "--symbols", "BTC"], _handler()) == 0
    assert store.read_points("coingecko", "BTC") == []
    assert store.read_points("wikipedia", "BTC")


def test_all_error_exit_1(isolated_cache):
    def h(r):
        raise httpx.ConnectError("x")
    assert _run(["--symbols", "BTC"], h) == 1


def test_no_ok_but_not_all_error_exit_2(isolated_cache):
    def h(r):
        if "wikimedia" in str(r.url):
            return httpx.Response(200, json={"items": []})
        return httpx.Response(429)
    assert _run(["--symbols", "BTC"], h) == 2


def test_per_source_isolation(isolated_cache):
    assert _run(["--symbols", "BTC"], _handler(cg_status=500)) == 0
    assert store.read_points("wikipedia", "BTC")
    assert store.read_points("coingecko", "BTC") == []


def test_unknown_source_exit_1(isolated_cache):
    assert _run(["--sources", "nope"], _handler()) == 1


def test_tmp_path_isolation_real_cache_untouched(isolated_cache):
    real = Path(refresh_attention.cache.DEFAULT_CACHE_ROOT)
    before = sorted(real.rglob("*")) if real.exists() else []
    _run(["--symbols", "BTC"], _handler())
    after = sorted(real.rglob("*")) if real.exists() else []
    assert before == after


def test_rerun_first_wins(isolated_cache):
    _run(["--sources", "wikipedia", "--symbols", "BTC"], _handler())
    first = store.read_points("wikipedia", "BTC")
    def h(r):
        p = wiki_payload(100)
        for it in p["items"]:
            it["views"] = 1
        return httpx.Response(200, json=p)
    _run(["--sources", "wikipedia", "--symbols", "BTC"], h)
    assert store.read_points("wikipedia", "BTC") == first


def test_default_sources_exclude_opt_in_volume_and_trends(isolated_cache):
    # default run must stay wikipedia + coingecko: no ccxt or pytrends (live) call
    assert refresh_attention.DEFAULT_SOURCES == ("wikipedia", "coingecko", "universe")
    assert {"exchange_volume", "hyperliquid_volume", "trends"} <= set(refresh_attention.RUNNERS)


def _universe_file(cache_root):
    return cache_root / "attention" / "universe.json"


def test_universe_source_writes_snapshot(isolated_cache):
    assert _run(["--sources", "universe"], _handler()) == 0
    from api.data.attention import universe_store
    snap = universe_store.read_latest()
    assert snap["date"] == TODAY.isoformat()
    assert [c["symbol"] for c in snap["coins"]] == ["BTC", "ETH"]


def test_universe_in_default_sources():
    assert "universe" in refresh_attention.DEFAULT_SOURCES


def test_universe_dry_run_writes_nothing(isolated_cache):
    def boom(r):
        raise AssertionError("no network in dry run")
    assert _run(["--dry-run", "--sources", "universe"], boom) == 0
    assert not _universe_file(isolated_cache).exists()


def test_universe_failure_keeps_old_file_and_counts_error(isolated_cache, capsys):
    from api.data.attention import universe_store
    universe_store.write_snapshot("2026-09-01", [{"id": "x", "symbol": "X", "market_cap": 1, "volume_24h": 1}])
    before = _universe_file(isolated_cache).read_bytes()
    assert _run(["--sources", "universe"], _handler(cg_status=500)) == 1
    assert _universe_file(isolated_cache).read_bytes() == before
