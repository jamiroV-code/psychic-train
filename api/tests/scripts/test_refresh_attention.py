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
    assert refresh_attention.DEFAULT_SOURCES == ("wikipedia", "coingecko", "universe", "signals")
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


def test_default_sources_and_runners_are_pinned():
    assert refresh_attention.DEFAULT_SOURCES == ("wikipedia", "coingecko", "universe", "signals")
    assert set(refresh_attention.RUNNERS) == {
        "universe", "wikipedia", "coingecko", "exchange_volume", "hyperliquid_volume",
        "trends", "reddit", "xsearch", "categories", "signals"}
    for key, fn in refresh_attention.RUNNERS.items():
        assert fn.__name__ == "_run_" + key


def test_default_run_hits_only_wikipedia_coingecko_universe(isolated_cache):
    urls = []

    def h(r: httpx.Request):
        urls.append(str(r.url))
        return _handler()(r)

    _run(["--symbols", "BTC"], h)
    assert urls
    assert all("wikimedia" in u or "coingecko" in u for u in urls)


def _cat_handler(status=200):
    def h(r: httpx.Request):
        if "coins/markets" in str(r.url) and r.url.params.get("category"):
            return httpx.Response(status, json=[{"symbol": "fet"}])
        return httpx.Response(404)
    return h


def _categories_file(cache_root):
    return cache_root / "attention" / "categories.json"


def test_categories_source_writes_dated_snapshot(isolated_cache):
    from api.data.attention import categories_store
    assert _run(["--sources", "categories"], _cat_handler()) == 0
    snap = categories_store.read_latest()
    assert snap["date"] == TODAY.isoformat()
    assert snap["categories"] and all(c["symbols"] == ["FET"] for c in snap["categories"])
    assert all(set(c) == {"id", "name", "symbols"} for c in snap["categories"])


def test_run_categories_works_without_removed_config_keys(isolated_cache, capsys):
    """T113 U1 (F1, AC-N7): the shipped config has no `categories`; the runner fetches the id-map ids plus
    `exclude_category_ids`, names them from the map, and prints no ` error ` line the workflow would fail on."""
    import json
    from api.analytics.attention import discovery, narratives
    from api.data.attention import categories_store
    assert "categories" not in json.loads(discovery.CONFIG_PATH.read_text())
    asked = []

    def h(r: httpx.Request):
        if r.url.params.get("category"):
            asked.append(r.url.params["category"])
        return _cat_handler()(r)
    assert _run(["--sources", "categories"], h) == 0
    id_map = narratives.load_id_map()
    expect = list(id_map) + discovery.load_config()["exclude_category_ids"]
    assert sorted(set(asked)) == sorted(expect)
    snap = categories_store.read_latest()
    assert {c["id"]: c["name"] for c in snap["categories"]} == {
        **{k: v["name"] for k, v in id_map.items()}, "exchange-based-tokens": "exchange-based-tokens"}
    out = capsys.readouterr()
    assert " error " not in out.out + out.err and "categories: snapshot written" in out.out


def test_categories_not_in_default_sources():
    assert "categories" not in refresh_attention.DEFAULT_SOURCES


def test_categories_dry_run_writes_nothing(isolated_cache):
    def boom(r):
        raise AssertionError("no network in dry run")
    assert _run(["--dry-run", "--sources", "categories"], boom) == 0
    assert not _categories_file(isolated_cache).exists()


def test_categories_failure_keeps_old_file(isolated_cache):
    from api.data.attention import categories_store
    categories_store.write_snapshot("2026-09-01", [{"id": "x", "name": "X", "symbols": ["X"]}])
    before = _categories_file(isolated_cache).read_bytes()
    assert _run(["--sources", "categories"], _cat_handler(status=500)) == 1
    assert _categories_file(isolated_cache).read_bytes() == before


def test_reason_summary_counts_distinct_reasons_and_skips_ok():
    from api.data.attention.types import SourceSeries
    from api.scripts.refresh_attention import reason_summary
    series = [SourceSeries("x", "A", [], "unavailable", "fetch-failed: E HTTP 451"),
              SourceSeries("x", "B", [], "unavailable", "fetch-failed: E HTTP 451"),
              SourceSeries("x", "C", [], "unavailable", "empty response"),
              SourceSeries("x", "D", [], "ok", "")]
    assert reason_summary(series) == "fetch-failed: E HTTP 451 x2; empty response x1"


def _signals_world(tmp_path, monkeypatch):
    from api.tests.analytics.attention.test_discovery import gain, world
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    gain("A")


def test_signals_option_writes_snapshot(isolated_cache, tmp_path, monkeypatch, capsys):
    from api.analytics.attention import signal_snapshots
    _signals_world(tmp_path, monkeypatch)
    assert _run(["--sources", "signals"], lambda r: (_ for _ in ()).throw(AssertionError("no network"))) == 0
    assert len(list((isolated_cache / "attention" / "signals").glob("*.json"))) == 3
    assert signal_snapshots.read_snapshots(TODAY - timedelta(days=1), TODAY - timedelta(days=1), 7)
    assert "signals: 3 written" in capsys.readouterr().out


def test_signals_is_last_default_source():
    assert refresh_attention.DEFAULT_SOURCES == ("wikipedia", "coingecko", "universe", "signals")


def test_signals_dry_run_writes_nothing(isolated_cache, tmp_path, monkeypatch):
    _signals_world(tmp_path, monkeypatch)
    assert _run(["--dry-run", "--sources", "signals"], _handler()) == 0
    assert not (isolated_cache / "attention" / "signals").exists()


def test_signals_failure_never_changes_exit_code(isolated_cache, monkeypatch, capsys):
    from api.analytics.attention import signal_snapshots

    def boom(today):
        raise RuntimeError("snapshot broke")
    monkeypatch.setattr(signal_snapshots, "take_snapshot", boom)
    assert _run(["--symbols", "BTC,ETH"], _handler()) == 0           # default run: same as without signals
    assert _run(["--sources", "signals"], _handler()) == 0
    cap = capsys.readouterr()
    assert "signals: error" in cap.err
    # all other sources failing still exits 1: signals is not counted as a success
    assert _run(["--symbols", "BTC"], lambda r: (_ for _ in ()).throw(httpx.ConnectError("x"))) == 1


def test_signals_line_is_ignored_by_the_verify_step_parse(isolated_cache, tmp_path, monkeypatch, capsys):
    # the workflow verify step only looks at lines starting with a source it lists (wikipedia, coingecko, universe, categories)
    _signals_world(tmp_path, monkeypatch)
    _run(["--sources", "signals"], _handler())
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("signals:")]
    assert len(lines) == 1 and not any(lines[0].startswith(s + ":") for s in ("wikipedia", "coingecko", "universe", "categories"))
