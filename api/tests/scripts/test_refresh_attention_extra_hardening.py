"""M1/L2 hardening of the extra sources: circuit breaker, partial store, one Reddit token, one HL snapshot."""
from __future__ import annotations

import httpx

from api.data import ccxt_adapter
from api.data.attention import reddit
from api.data.attention.types import SourceSeries
from api.scripts import attention_extra, refresh_attention
from api.tests.data.attention.conftest import TODAY

SYMS = [f"S{i}" for i in range(20)]


def _guarded(results):
    """A fake fetch for _collect_guarded (shared by the opt-in sources) returning scripted SourceSeries."""
    calls = []

    def fetch(sym):
        calls.append(sym)
        state, reason = results(len(calls))
        return SourceSeries("reddit", sym, [(TODAY, 1.0)] if state == "ok" else [], state, reason)
    return fetch, calls


def test_guarded_breaker_stops_after_5_blocks_and_keeps_earlier_series():
    fetch, calls = _guarded(lambda n: ("ok", "") if n <= 3 else ("unavailable", "HTTP 503"))
    series = refresh_attention._collect_guarded(SYMS, fetch, "reddit")
    assert len(calls) == 3 + 5 and len(series) == len(SYMS)
    assert [s.state for s in series[:3]] == ["ok"] * 3
    assert all(s.state == "capped" and "skipped" in s.reason and s.points == [] for s in series[8:])


def test_guarded_code_errors_do_not_trip_breaker():
    fetch, calls = _guarded(lambda n: ("unavailable", "fetch-failed: TypeError"))
    series = refresh_attention._collect_guarded(SYMS, fetch, "reddit")
    assert len(calls) == len(SYMS) and all(s.reason == "fetch-failed: TypeError" for s in series)


def test_time_budget_stops_cleanly_and_keeps_fetched(monkeypatch):
    t = [0.0]

    def results(n):
        t[0] += 100.0
        return "ok", ""
    fetch, _ = _guarded(results)
    monkeypatch.setattr(refresh_attention, "_clock", lambda: t[0])
    series = refresh_attention._collect_guarded(SYMS, fetch, "reddit")
    assert len([s for s in series if s.state == "ok"]) == 4 and len(series) == len(SYMS)  # 360 s: stops after 400 s
    assert all(s.state == "capped" and "time budget" in s.reason for s in series[4:])
    assert attention_extra.classify("trends", "trends: 0/20 ok, 4 rows written [x] reasons: time budget reached x16").status == "ok"


def _reddit_env(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")


def _reddit_client(token_status=200, search=lambda n: 200):
    seen = {"token": 0, "search": 0, "bearers": []}

    def h(r: httpx.Request):
        if "access_token" in str(r.url):
            seen["token"] += 1
            return httpx.Response(token_status, json={"access_token": f"tok{seen['token']}"})
        seen["search"] += 1
        seen["bearers"].append(r.headers["authorization"])
        code = search(seen["search"])
        return httpx.Response(code, json={"data": {"children": [1, 2]}})
    return httpx.Client(transport=httpx.MockTransport(h)), seen


def test_reddit_token_fetched_once_per_run(isolated_cache, monkeypatch):
    _reddit_env(monkeypatch)
    c, seen = _reddit_client()
    series = refresh_attention._run_reddit(SYMS, c, TODAY, lambda s: None)
    assert seen["token"] == 1 and seen["search"] == len(SYMS)
    assert all(s.state == "ok" for s in series)


def test_reddit_refreshes_token_once_on_401(isolated_cache, monkeypatch):
    _reddit_env(monkeypatch)
    c, seen = _reddit_client(search=lambda n: 401 if n == 3 else 200)
    series = refresh_attention._run_reddit(SYMS, c, TODAY, lambda s: None)
    assert seen["token"] == 2 and all(s.state == "ok" for s in series)
    assert seen["bearers"][3] == "Bearer tok2"


def test_reddit_persistent_401_refreshes_only_once(isolated_cache, monkeypatch):
    _reddit_env(monkeypatch)
    c, seen = _reddit_client(search=lambda n: 401)
    series = refresh_attention._run_reddit(SYMS, c, TODAY, lambda s: None)
    assert seen["token"] == 2
    assert sum(s.state == "capped" for s in series) == len(SYMS) - 5 and seen["search"] <= 2 * 5 + 1


def test_reddit_token_failure_stops_after_5_with_one_token_request(isolated_cache, monkeypatch):
    _reddit_env(monkeypatch)
    c, seen = _reddit_client(token_status=403)
    series = refresh_attention._run_reddit(SYMS, c, TODAY, lambda s: None)
    assert seen["token"] == 1 and seen["search"] == 0
    assert [s.reason for s in series[:5]] == ["token unavailable"] * 5
    assert all(s.state == "capped" for s in series[5:])


def test_reddit_search_blocks_trip_breaker(isolated_cache, monkeypatch):
    _reddit_env(monkeypatch)
    c, seen = _reddit_client(search=lambda n: 403)
    series = refresh_attention._run_reddit(SYMS, c, TODAY, lambda s: None)
    assert seen["search"] == 5 and sum(s.state == "capped" for s in series) == len(SYMS) - 5


def test_reddit_single_series_without_session_still_works(monkeypatch):
    _reddit_env(monkeypatch)
    c, seen = _reddit_client()
    assert reddit.fetch_series("BTC", client=c, today=TODAY).state == "ok" and seen["token"] == 1


class _Ex:
    def __init__(self):
        self.calls = 0

    def fetch_tickers(self, params=None):
        self.calls += 1
        return {f"S{i}/USDC:USDC": {"quoteVolume": 100.0 + i, "info": {}, "symbol": f"S{i}/USDC:USDC"}
                for i in range(3)}


def test_hyperliquid_fetches_snapshot_once_for_all_symbols(isolated_cache, monkeypatch):
    ex = _Ex()
    monkeypatch.setattr(ccxt_adapter, "_exchange", lambda: ex)
    from api.data import hyperliquid_narrative_adapter as h
    monkeypatch.setattr(h, "parse_tickers", lambda t: [h.PerpMarket(base=f"S{i}", base_name=f"S{i}", quote_volume=100.0 + i)
                                                       for i in range(3)])
    series = refresh_attention._run_hyperliquid_volume([f"S{i}" for i in range(103)], None, TODAY, lambda s: None)
    assert ex.calls == 1 and len(series) == 103
    assert series[1].points == [(TODAY.replace(day=TODAY.day - 1), 101.0)]
    assert series[50].reason == "symbol not listed or no volume"


def test_hyperliquid_failed_snapshot_is_one_call_and_unavailable(isolated_cache, monkeypatch):
    class Bad:
        calls = 0

        def fetch_tickers(self, params=None):
            Bad.calls += 1
            raise TimeoutError("x")
    monkeypatch.setattr(ccxt_adapter, "_exchange", lambda: Bad())
    series = refresh_attention._run_hyperliquid_volume(SYMS, None, TODAY, lambda s: None)
    assert Bad.calls == 1 and all(s.state == "unavailable" for s in series)


def test_badsymbol_is_a_data_outcome_not_a_code_error():
    line = "exchange_volume: 0/103 ok, 0 rows written [other 103] reasons: fetch-failed: BadSymbol x103"
    assert attention_extra.classify("exchange_volume", line).status == "unavailable"
