import hashlib
import json
import socket
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from api.data.attention import onboarding_store as ob
from api.data.attention import store, universe_store
from api.scripts import refresh_attention
from api.scripts import refresh_attention as ra
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
    assert refresh_attention.DEFAULT_SOURCES == ("wikipedia", "coingecko", "universe", "ledger", "signals")
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
    assert refresh_attention.DEFAULT_SOURCES == ("wikipedia", "coingecko", "universe", "ledger", "signals")
    assert set(refresh_attention.RUNNERS) == {
        "universe", "wikipedia", "coingecko", "exchange_volume", "hyperliquid_volume",
        "trends", "reddit", "xsearch", "categories", "signals", "ledger", "classify", "resolve_wiki", "resolve_trends"}
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
    """T113 U1 / T115 U2 (F1, AC-N7): the shipped config has no `categories` and no `exclude_category_ids`; the
    runner fetches the id-map ids only, names them from the map, and prints no ` error ` line the workflow would
    fail on."""
    import json
    from api.analytics.attention import discovery, narratives
    from api.data.attention import categories_store
    raw = json.loads(discovery.CONFIG_PATH.read_text())
    assert "categories" not in raw and "exclude_category_ids" not in raw
    asked = []

    def h(r: httpx.Request):
        if r.url.params.get("category"):
            asked.append(r.url.params["category"])
        return _cat_handler()(r)
    assert _run(["--sources", "categories"], h) == 0
    id_map = narratives.load_id_map()
    assert sorted(set(asked)) == sorted(id_map)
    snap = categories_store.read_latest()
    assert {c["id"]: c["name"] for c in snap["categories"]} == {k: v["name"] for k, v in id_map.items()}
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
    assert refresh_attention.DEFAULT_SOURCES == ("wikipedia", "coingecko", "universe", "ledger", "signals")


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


# --- U4 (T114): CoinGecko and Wikipedia take their symbol list and ids from the universe snapshot ---

UNIVERSE_ROWS = [
    {"id": "bitcoin", "symbol": "BTC", "market_cap": 3, "volume_24h": 1},
    {"id": "tether", "symbol": "USDT", "market_cap": 2, "volume_24h": 1},
    {"id": "wrapped-bitcoin", "symbol": "WBTC", "market_cap": 2, "volume_24h": 1},
    {"id": "solana-snapshot-id", "symbol": "SOL", "market_cap": 1, "volume_24h": 1},
]


def _write_universe(rows=UNIVERSE_ROWS):
    from api.data.attention import universe_store
    universe_store.write_snapshot("2026-10-18", rows)


def _recording(urls):
    def h(r: httpx.Request):
        urls.append(str(r.url))
        return _handler()(r)
    return h


def _line(out, src):
    return next(ln for ln in out.splitlines() if ln.startswith(src + ":"))


def test_symbols_from_universe_snapshot_not_wiki_keys(isolated_cache, capsys):
    _write_universe()
    assert refresh_attention._symbols(None) == ["BTC", "SOL"]
    assert _run(["--dry-run", "--sources", "coingecko,wikipedia"], _handler()) == 0
    out = capsys.readouterr().out
    assert "coingecko: dry run, would fetch 2 symbols" in out
    assert "wikipedia: dry run, would fetch 2 symbols" in out


def test_symbols_fall_back_to_wiki_keys_without_snapshot(isolated_cache):
    import json
    keys = list(json.loads(refresh_attention.WIKI_ARTICLES_PATH.read_text()))
    assert refresh_attention._symbols(None) == keys


def test_id_taken_from_snapshot_row(isolated_cache):
    _write_universe()
    urls = []
    assert _run(["--sources", "coingecko"], _recording(urls)) == 0
    assert not any("coins/markets" in u for u in urls)  # no extra markets call
    assert any("/coins/solana-snapshot-id/market_chart" in u for u in urls)
    assert len(store.read_points("coingecko", "SOL")) == 99


def test_missing_id_is_counted_no_id_outcome(isolated_cache, capsys):
    _write_universe(UNIVERSE_ROWS + [{"id": None, "symbol": "NOID", "market_cap": 1, "volume_24h": 1}])
    urls = []
    assert _run(["--sources", "coingecko"], _recording(urls)) == 0
    line = _line(capsys.readouterr().out, "coingecko")
    assert line.startswith("coingecko: 2/3 ok") and "no-id 1" in line
    assert not any("noid" in u.lower() for u in urls)
    from api.data.attention.types import SourceSeries
    assert refresh_attention.outcome_summary(
        [SourceSeries("coingecko", "X", [], "unavailable", "no-id")]) == "no-id 1"


def test_explicit_symbols_arg_still_wins(isolated_cache, capsys):
    _write_universe()
    assert refresh_attention._symbols("btc, eth") == ["BTC", "ETH"]
    urls = []
    assert _run(["--sources", "coingecko", "--symbols", "BTC"], _recording(urls)) == 0
    assert [u for u in urls if "market_chart" in u] and all("/coins/bitcoin/" in u for u in urls)
    assert _line(capsys.readouterr().out, "coingecko").startswith("coingecko: 1/1 ok")


def test_stablecoin_not_requested(isolated_cache, capsys):
    _write_universe()
    urls = []
    assert _run(["--sources", "coingecko,wikipedia"], _recording(urls)) == 0
    assert not any("tether" in u or "wrapped-bitcoin" in u for u in urls)
    assert "USDT" not in refresh_attention._symbols(None)
    capsys.readouterr()
    # an explicit stablecoin is not requested either: it has no id in the filtered universe
    assert _run(["--sources", "coingecko", "--symbols", "USDT"], _recording(urls)) == 1
    assert not any("tether" in u for u in urls)
    assert "no-id 1" in _line(capsys.readouterr().out, "coingecko")


def test_coingecko_result_line_keeps_n_of_m_ok_prefix(isolated_cache, capsys):
    # the workflow verify step: lines starting "<src>:", FAILED on " error ", else ^<src>: (\d+)/(\d+) ok with N > 0
    import re
    _write_universe(UNIVERSE_ROWS + [{"symbol": "NOID", "market_cap": 1, "volume_24h": 1}])
    assert _run(["--sources", "wikipedia,coingecko"], _handler()) == 0
    out = capsys.readouterr().out
    for src in ("wikipedia", "coingecko"):
        line = _line(out, src)
        m = re.match(rf"{src}: (\d+)/(\d+) ok", line)
        assert m and int(m.group(1)) > 0, line
        assert " error " not in line + " "


# --- T223 O1: the `ledger` step (seeding, advance, symbol cap, exit code, fixed-token stdout) and O3 `classify` ---
# No network: every client is a MockTransport; `no_net` also blocks the default transport and sockets.

@pytest.fixture
def no_net(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("an onboarding step must not reach the network")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)


def led_rows(placed: dict[str, int] | None = None, n: int = 120) -> list[dict]:
    order = [f"fill-{i}" for i in range(1, n + 1)]
    for cid, rank in (placed or {}).items():
        order.insert(rank - 1, cid)
    order = order[:n]
    return [{"id": c, "symbol": c.upper().replace("-", "_"), "name": c, "market_cap": 10_000 - i,
             "volume_24h": 1, "rank": i + 1} for i, c in enumerate(order)]


def _fail_net(r):
    raise AssertionError("no network")


def led_run(argv, day=TODAY, handler=_fail_net):
    c = httpx.Client(transport=httpx.MockTransport(handler))
    return ra.main(argv, client=c, today=day, sleep=lambda x: None)


def led_write(day, placed=None, n=120):
    universe_store.write_snapshot(day.isoformat(), led_rows(placed, n))


@pytest.mark.usefixtures("no_net")
class TestLedgerStep:
    def test_first_run_seeds_rank_1_to_100_only(self, isolated_cache, capsys):
        led_write(TODAY, {"edge": 110})
        assert led_run(["--sources", "ledger"]) == 0
        led, st = ob.read_ledger()
        assert st == "ok" and len(led["coins"]) == 100 and "edge" not in led["coins"]
        assert {(e["state"], e["class"], e["class_source"]) for e in led["coins"].values()} == {
            ("member", "normal", "owner")}
        assert "ledger: ok seeded 100" in capsys.readouterr().out
        assert ob.read_log(TODAY.isoformat())["entries"][0]["action"] == "seeded"

    def test_present_ledger_is_advanced_not_reseeded(self, isolated_cache, capsys):
        led_write(TODAY - timedelta(days=1))
        led_run(["--sources", "ledger"], TODAY - timedelta(days=1))
        capsys.readouterr()
        led_write(TODAY, {"newc": 30})
        assert led_run(["--sources", "ledger"]) == 0
        led, _ = ob.read_ledger()
        assert led["coins"]["newc"]["state"] == "watching" and led["last_advanced_date"] == TODAY.isoformat()
        out = capsys.readouterr()
        assert "ledger: ok advanced, entered 1" in out.out
        assert "newc" not in out.out.lower() + out.err.lower()

    def test_same_day_rerun_counts_once(self, isolated_cache):
        led_write(TODAY - timedelta(days=1))
        led_run(["--sources", "ledger"], TODAY - timedelta(days=1))
        led_write(TODAY, {"newc": 30})
        led_run(["--sources", "ledger"])
        before = ob.ledger_path().read_bytes()
        led_run(["--sources", "ledger"])
        assert ob.ledger_path().read_bytes() == before

    def test_corrupt_ledger_is_refused_and_kept(self, isolated_cache, capsys):
        led_write(TODAY)
        ob.ledger_path().parent.mkdir(parents=True, exist_ok=True)
        ob.ledger_path().write_text("{broken")
        assert led_run(["--sources", "ledger"]) == 0
        assert ob.ledger_path().read_text() == "{broken"
        assert "ledger: unavailable corrupt ledger" in capsys.readouterr().out

    def test_lost_ledger_reseeds_once_with_a_loud_line(self, isolated_cache, capsys):
        led_write(TODAY - timedelta(days=1))
        led_run(["--sources", "ledger"], TODAY - timedelta(days=1))
        ob.ledger_path().unlink()
        led_write(TODAY)
        led_run(["--sources", "ledger"])
        assert "ledger: warning re-seeded, probation progress lost" in capsys.readouterr().err
        assert ob.read_ledger()[1] == "ok"

    def test_stale_snapshot_is_skipped(self, isolated_cache, capsys):
        led_write(TODAY - timedelta(days=1))
        assert led_run(["--sources", "ledger"]) == 0
        assert ob.read_ledger() == (None, "absent")
        assert "ledger: skipped, stale snapshot" in capsys.readouterr().out

    def test_short_snapshot_is_unavailable(self, isolated_cache, capsys):
        led_write(TODAY, n=100)
        led_run(["--sources", "ledger"])
        assert ob.read_ledger() == (None, "absent")
        assert "ledger: unavailable short snapshot" in capsys.readouterr().out

    def test_no_snapshot_is_unavailable(self, isolated_cache, capsys):
        led_run(["--sources", "ledger"])
        assert "ledger: unavailable no snapshot" in capsys.readouterr().out

    def test_bad_settings_skip_the_step(self, isolated_cache, capsys, tmp_path, monkeypatch):
        from api.data.attention import onboarding_settings
        bad = tmp_path / "s.json"
        bad.write_text("{}")
        monkeypatch.setattr(onboarding_settings, "SETTINGS_PATH", bad)
        led_write(TODAY)
        led_run(["--sources", "ledger"])
        assert ob.read_ledger() == (None, "absent")
        assert "ledger: unavailable settings" in capsys.readouterr().out

    def test_ledger_never_decides_the_exit_code(self, isolated_cache, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("ledger broke")
        monkeypatch.setitem(ra.RUNNERS, "ledger", boom)
        assert led_run(["--sources", "ledger"]) == 0
        led_write(TODAY)
        assert led_run(["--sources", "ledger,universe"]) == 1   # universe errors (no network); ledger adds nothing

    def test_failed_universe_step_skips_the_ledger(self, isolated_cache, capsys):
        led_write(TODAY - timedelta(days=1))
        assert led_run(["--sources", "universe,ledger"]) == 1
        assert ob.read_ledger() == (None, "absent")
        assert "ledger: skipped, universe step failed" in capsys.readouterr().out

    def test_ledger_runs_after_universe_and_before_signals(self):
        d = ra.DEFAULT_SOURCES
        assert d.index("universe") < d.index("ledger") < d.index("signals")

    def test_dry_run_writes_no_ledger(self, isolated_cache, capsys):
        led_write(TODAY)
        assert led_run(["--dry-run", "--sources", "ledger"]) == 0
        assert ob.read_ledger() == (None, "absent")
        assert "ledger: dry run" in capsys.readouterr().out

    def test_runner_symbols_are_capped_at_top_100_plus_band_members(self, isolated_cache):
        led_write(TODAY - timedelta(days=1), {"bandm": 50})
        led_run(["--sources", "ledger"], TODAY - timedelta(days=1))      # seeds bandm as a member
        led_write(TODAY, {"bandm": 115})
        led_run(["--sources", "ledger"])
        syms = ra._symbols(None)
        assert len(syms) == 101 and "BANDM" in syms
        assert len(ra._universe_rows()) == 101

    def test_runner_symbols_without_a_ledger_are_the_top_100(self, isolated_cache):
        led_write(TODAY)
        assert len(ra._symbols(None)) == 100

    def test_old_rankless_snapshot_keeps_every_row(self, isolated_cache):
        universe_store.write_snapshot(TODAY.isoformat(), [{"id": "a", "symbol": "A", "market_cap": 1}])
        assert ra._symbols(None) == ["A"]


def cls_entry(symbol, state="watching", cls="unknown", source="auto"):
    return {"symbol": symbol, "state": state, "first_seen": "2026-10-10", "last_in_top100": "2026-10-15",
            "last_in_top120": "2026-10-15", "consecutive_top100": 3, "consecutive_outside120": 0, "class": cls,
            "class_evidence": {}, "class_source": source, "seeded": False, "updated": "2026-10-15"}


def cls_handler(calls, detail_status=200, cats=("Layer 1 (L1)",)):
    def h(r: httpx.Request):
        path = r.url.raw_path.decode()
        calls.append(path.split("?")[0])
        if path.split("?")[0].endswith("/market_chart"):
            return httpx.Response(200, json={"prices": [[i * 86_400_000, 1.0 + i] for i in range(30)]})
        if detail_status != 200:
            return httpx.Response(detail_status)
        return httpx.Response(200, json={"categories": list(cats), "name": "Some Name", "asset_platform_id": None})
    return h


def cls_settings(tmp_path, monkeypatch, **over):
    from api.data.attention import onboarding_settings
    s = json.loads(onboarding_settings.SETTINGS_PATH.read_text())
    p = tmp_path / "onb.json"
    p.write_text(json.dumps({**s, **over}))
    monkeypatch.setattr(onboarding_settings, "SETTINGS_PATH", p)


@pytest.mark.usefixtures("no_net")
class TestClassifyStep:
    def ledger(self, **coins):
        ob.write_ledger({"last_advanced_date": TODAY.isoformat(), "seeded_at": "2026-10-01", "coins": coins})

    def test_watching_unknown_first_and_capped_per_run(self, isolated_cache, tmp_path, monkeypatch, capsys):
        cls_settings(tmp_path, monkeypatch, classify_max_coins_per_run=2)
        self.ledger(**{"m-1": cls_entry("MONE", "member"), "w-1": cls_entry("WONE"), "w-2": cls_entry("WTWO"),
                       "n-1": cls_entry("NORM", "member", "normal", "owner"), "i-1": cls_entry("GONE", "inactive")})
        calls = []
        assert led_run(["--sources", "classify"], handler=cls_handler(calls)) == 0
        coins = ob.read_ledger()[0]["coins"]
        assert (coins["w-1"]["class"], coins["w-2"]["class"], coins["m-1"]["class"]) == ("normal", "normal", "unknown")
        assert coins["w-1"]["class_source"] == "auto" and coins["w-1"]["class_evidence"]["n_days"] == 30
        assert "prices" not in json.dumps(coins["w-1"]["class_evidence"])
        assert len(calls) == 4 and all("/coins/" in c for c in calls)
        out = capsys.readouterr()
        assert "classify: ok 2/2" in out.out
        assert not any(s in (out.out + out.err).lower() for s in ("wone", "wtwo", "w-1", "some name"))

    def test_429_stops_the_step_and_leaves_the_rest_unknown(self, isolated_cache, capsys):
        self.ledger(**{"w-1": cls_entry("WONE"), "w-2": cls_entry("WTWO")})
        calls = []
        led_run(["--sources", "classify"], handler=cls_handler(calls, detail_status=429))
        coins = ob.read_ledger()[0]["coins"]
        assert {c["class"] for c in coins.values()} == {"unknown"}
        assert len({c for c in calls}) == 1
        assert "classify: ok 0/0, stopped on HTTP 429" in capsys.readouterr().out

    def test_failed_fetch_stays_unknown_with_a_reason(self, isolated_cache, capsys):
        self.ledger(**{"w-1": cls_entry("WONE")})
        led_run(["--sources", "classify"], handler=cls_handler([], detail_status=503))
        e = ob.read_ledger()[0]["coins"]["w-1"]
        assert e["class"] == "unknown" and e["class_evidence"]["reason"] == "unavailable"
        assert "classify: ok 0/1" in capsys.readouterr().out

    def test_owner_list_and_confirmed_class_win_without_a_fetch(self, isolated_cache, tmp_path, monkeypatch):
        cls_settings(tmp_path, monkeypatch, confirmed_classes={"CONF": "normal"})
        self.ledger(**{"tether": cls_entry("USDT"), "c-1": cls_entry("CONF")})
        led_run(["--sources", "classify"])                           # any request would fail the test
        coins = ob.read_ledger()[0]["coins"]
        assert (coins["tether"]["class"], coins["tether"]["class_source"]) == ("stablecoin", "owner")
        assert (coins["c-1"]["class"], coins["c-1"]["class_source"]) == ("normal", "confirmed")

    def test_no_ledger_is_unavailable_and_never_decides_the_exit_code(self, isolated_cache, capsys):
        assert led_run(["--sources", "classify"]) == 0
        assert "classify: unavailable no ledger" in capsys.readouterr().out

    def test_classify_is_not_a_default_source(self):
        assert "classify" not in ra.DEFAULT_SOURCES and "classify" in ra.RUNNERS


@pytest.mark.usefixtures("no_net")
class TestResolveStep:
    def setup_coin(self, symbol="ZZNEW", name="New Coin"):
        ob.write_ledger({"last_advanced_date": TODAY.isoformat(), "seeded_at": TODAY.isoformat(),
                         "coins": {"new": cls_entry(symbol)}})
        universe_store.write_snapshot(TODAY.isoformat(), [{"id": "new", "symbol": symbol, "name": name}])

    def test_wiki_and_queries_apply_and_log_through_refresh(self, isolated_cache, capsys):
        self.setup_coin()
        def handler(request):
            if "wikimedia" in str(request.url):
                return httpx.Response(200, json=wiki_payload(100))
            return httpx.Response(200, json={"title": "New Coin", "type": "standard",
                                           "extract": "New Coin is a cryptocurrency."})
        assert led_run(["--sources", "resolve_wiki"], handler=handler) == 0
        assert ob.read_json("wiki_articles_auto.json")["entries"]["ZZNEW"]["title"] == "New Coin"
        assert ob.read_json("attention_queries_auto.json")["entries"]["ZZNEW"]["cashtag_only"] is True
        assert {e["source"] for e in ob.read_log(TODAY.isoformat())["entries"]} == {"wikipedia", "reddit_x"}
        assert "New Coin" not in capsys.readouterr().out

    def test_wiki_redirect_waits_without_overlay(self, isolated_cache):
        self.setup_coin()
        def handler(request):
            if "wikimedia" in str(request.url):
                return httpx.Response(200, json=wiki_payload(100))
            return httpx.Response(200, json={"title": "Other Coin", "type": "standard",
                                           "extract": "New Coin is a cryptocurrency."})
        led_run(["--sources", "resolve_wiki"], handler=handler)
        assert "ZZNEW" not in ob.read_json("wiki_articles_auto.json")["entries"]
        assert ob.read_json("pending.json")["coins"]["ZZNEW"]["wikipedia"]["reason"] == "redirect to another title"

    def test_strict_trends_applies_with_stored_volume_and_logs(self, isolated_cache, monkeypatch):
        from api.data.attention import onboarding_sources as src
        from api.data.attention.types import SourceSeries
        self.setup_coin()
        points = [(TODAY - timedelta(days=100-i), float(10+i+i % 3)) for i in range(100)]
        volumes = [(day, 1000.0*(10+i)) for i, (day, _) in enumerate(points)]
        store.write_series(SourceSeries("coingecko", "ZZNEW", volumes, "ok", ""), today=TODAY)
        class Fake:
            def suggestions(self, name):
                return [{"mid": "/g/new_coin", "title": name, "type": "Cryptocurrency"}]
        monkeypatch.setattr(ra, "TRENDREQ_FACTORY", Fake)
        monkeypatch.setattr(src, "fetch_topic_series", lambda *a, **k: (points, "ok"))
        led_run(["--sources", "resolve_trends"])
        assert ob.read_json("trends_keywords_auto.json")["entries"]["ZZNEW"]["topic"] == "/g/new_coin"
        event = ob.read_log(TODAY.isoformat())["entries"][-1]
        assert event["action"] == "applied" and event["evidence"]["volume_days"] >= 60
        assert event["previous"] is None

    def test_short_volume_waits_and_rechecks_on_next_run(self, isolated_cache, monkeypatch):
        from api.data.attention import onboarding_sources as src
        self.setup_coin()
        class Fake:
            def suggestions(self, name):
                return [{"mid": "/g/new_coin", "title": name, "type": "Cryptocurrency"}]
        monkeypatch.setattr(ra, "TRENDREQ_FACTORY", Fake)
        points = [(TODAY-timedelta(days=i+1), float(i+10)) for i in range(90)]
        monkeypatch.setattr(src, "fetch_topic_series", lambda *a, **k: (points, "ok"))
        led_run(["--sources", "resolve_trends"])
        assert ob.read_json("pending.json")["coins"]["ZZNEW"]["trends"]["reason"].startswith("volume history")
        assert ob.read_json("trends_keywords_auto.json")["entries"] == {}
        before = len(ob.read_log(TODAY.isoformat())["entries"])
        led_run(["--sources", "resolve_trends"])
        assert len(ob.read_log(TODAY.isoformat())["entries"]) == before + 1

    def test_first_429_stops_following_network_sources(self, isolated_cache, monkeypatch, capsys):
        self.setup_coin()
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429)
        def forbidden():
            raise AssertionError("following provider must not be called after 429")
        monkeypatch.setattr(ra, "TRENDREQ_FACTORY", forbidden)
        led_run(["--sources", "resolve_wiki,resolve_trends"], handler=handler)
        assert len(calls) == 1
        assert "resolve_trends: unavailable rate-limit" in capsys.readouterr().out
        assert ob.read_json("pending.json")["coins"]["ZZNEW"]["wikipedia"]["reason"] == "rate limited; retry next run"

    def test_bad_snapshot_name_never_enters_stdout(self, isolated_cache, capsys):
        self.setup_coin(name="::warning::\u202esecret")
        led_run(["--sources", "resolve_wiki"], handler=lambda r: httpx.Response(404))
        text = capsys.readouterr().out
        assert "::" not in text and "secret" not in text

    def test_colliding_overlay_entry_is_quarantined_to_pending_and_logged(self, isolated_cache, monkeypatch):
        from api.data.attention import trends_keywords as tk
        self.setup_coin()
        owner_topic = next(e["topic"] for e in tk.load().entries.values() if "topic" in e)
        ob.write_json("trends_keywords_auto.json", {"entries": {"ZZNEW": {"topic": owner_topic, "label": "Dup"}}})
        class Fake:
            def suggestions(self, name):
                return []
        monkeypatch.setattr(ra, "TRENDREQ_FACTORY", Fake)
        led_run(["--sources", "resolve_trends"])
        assert ob.read_json("trends_keywords_auto.json")["entries"] == {}
        assert ob.read_json("pending.json")["coins"]["ZZNEW"]["trends"]["reason"] == "collides with another keyword"
        assert any(e.get("previous") == {"topic": owner_topic, "label": "Dup"}
                   for e in ob.read_log(TODAY.isoformat())["entries"])
