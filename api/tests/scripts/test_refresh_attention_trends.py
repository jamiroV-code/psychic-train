"""T100b Trends runner: one coin per request, keyword file, name-risk skip, spacing, 429 backoff, breaker,
rotation, time budget, summary. Fake TrendReq only; no network, no real sleeping."""
from __future__ import annotations

import json
from datetime import date, timedelta

import httpx
import pytest

from api.data.attention import store, trends, trends_keywords
from api.scripts import attention_extra, refresh_attention
from api.scripts.trends_cli_common import PytrendsMissing
from api.tests import trends_fixtures as fx

KEYWORDS = {
    "_anchor": {"term": "Bitcoin", "label": "Bitcoin"},
    "AAVE": {"term": "Aave", "label": "Aave"},
    "INJ": {"term": "Injective", "label": "Injective"},
    "ARB": {"term": "Arbitrum", "label": "Arbitrum"},
    "OP": {"term": "Optimism", "label": "Optimism"},
    "TIA": {"term": "Celestia", "label": "Celestia"},
    "SOL": {"topic": "/m/0sol", "label": "Solana"},
    "LINK": {"term": "Chainlink", "label": "Chainlink"},
    "USDX": {"no-keyword": True, "label": "USDX", "note": "stablecoin"},
}


def _day(start: int, n: int) -> date:
    """A day whose rotation start index over n fetched coins is `start`."""
    d = fx.TODAY
    while d.toordinal() % n != start:
        d += timedelta(days=1)
    return d


class TermClient:
    """Fake TrendReq answering per requested term: script[term] is a list consumed in order (the last item
    repeats); a missing term gets a healthy 100-day frame. An exception item is raised."""

    def __init__(self, script: dict | None = None, today: date = fx.TODAY):
        self.script = {t: list(v) for t, v in (script or {}).items()}
        self.today = today
        self.payloads: list[tuple[list[str], str]] = []

    def build_payload(self, kw_list, cat=0, timeframe="today 5-y", geo="", gprop=""):
        self.payloads.append((list(kw_list), timeframe))

    def interest_over_time(self):
        term = self.payloads[-1][0][0]
        items = self.script.get(term)
        if not items:
            return fx.daily_frame([term], days=100, end=self.today - timedelta(days=1))
        item = items.pop(0) if len(items) > 1 else items[0]
        if isinstance(item, BaseException):
            raise item
        return item

    def terms(self) -> list[str]:
        return [p[0][0] for p in self.payloads]


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path, isolated_cache):
    fx.block_network(monkeypatch)
    path = tmp_path / "kw.json"
    path.write_text(json.dumps(KEYWORDS))
    monkeypatch.setattr(trends_keywords, "KEYWORDS_PATH", path)
    monkeypatch.setattr(refresh_attention, "_jitter", lambda: 0.0)
    return path


def _install(monkeypatch, client):
    made = []

    def factory():
        made.append(1)
        return client
    monkeypatch.setattr(refresh_attention, "TRENDREQ_FACTORY", factory)
    return made


def _run(monkeypatch, symbols, script=None, today=fx.TODAY):
    client = TermClient(script, today)
    made = _install(monkeypatch, client)
    sleeps: list[float] = []
    series = refresh_attention._run_trends(symbols, None, today, sleeps.append)
    return {s.symbol: s for s in series}, client, sleeps, made


def _zeros(term, days=100, today=fx.TODAY):
    return fx.daily_frame([term], days=days, end=today - timedelta(days=1), values={term: 0})


def test_bad_keyword_file_all_unavailable(monkeypatch, _env):
    _env.write_text("{bad")
    out, client, _, made = _run(monkeypatch, ["AAVE", "INJ"])
    assert [s.reason for s in out.values()] == ["bad keyword file"] * 2
    assert all(s.state == "unavailable" and s.points == [] for s in out.values())
    assert client.payloads == [] and made == []


def test_no_keyword_costs_no_request(monkeypatch):
    out, client, sleeps, made = _run(monkeypatch, ["USDX", "ZZZ"])
    assert {s.reason for s in out.values()} == {"no keyword mapped"}
    assert client.payloads == [] and sleeps == [] and made == []


def test_name_risk_term_skipped_topic_fetched(monkeypatch):
    out, client, _, _ = _run(monkeypatch, ["LINK", "SOL"])
    assert out["LINK"].state == "unavailable" and out["LINK"].reason == trends.NAME_AMBIGUOUS
    assert out["SOL"].state == "ok" and len(out["SOL"].points) == 100
    assert client.terms() == ["/m/0sol"]


def test_one_request_per_keyword_coin(monkeypatch):
    out, client, _, made = _run(monkeypatch, ["AAVE", "INJ", "SOL"])
    assert sorted(client.terms()) == ["/m/0sol", "Aave", "Injective"]
    assert all(len(kw) == 1 for kw, _ in client.payloads)
    assert not any("Bitcoin" in kw for kw, _ in client.payloads)
    assert {tf for _, tf in client.payloads} == {trends.explicit_timeframe(fx.TODAY)}
    assert made == [1] and all(s.state == "ok" for s in out.values())


def test_spacing_uses_injected_sleep(monkeypatch):
    monkeypatch.setattr(refresh_attention, "_jitter", lambda: 1.5)
    _, client, sleeps, _ = _run(monkeypatch, ["AAVE", "INJ", "SOL"])
    assert len(client.payloads) == 3
    assert sleeps == [refresh_attention.TRENDS_INTERVAL_S + 1.5] * 2
    assert refresh_attention.TRENDS_INTERVAL_S == 3.0
    monkeypatch.undo()
    assert all(0.0 <= refresh_attention._jitter() <= 2.0 for _ in range(200))


def test_rotation_start_depends_on_day(monkeypatch):
    syms = ["AAVE", "INJ", "SOL"]
    _, c0, _, _ = _run(monkeypatch, syms, today=_day(0, 3))
    _, c1, _, _ = _run(monkeypatch, syms, today=_day(1, 3))
    _, c2, _, _ = _run(monkeypatch, syms, today=_day(2, 3))
    assert c0.terms() == ["Aave", "Injective", "/m/0sol"]
    assert c1.terms() == ["Injective", "/m/0sol", "Aave"]
    assert c2.terms() == ["/m/0sol", "Aave", "Injective"]


def test_429_backoff_30_60_120_then_capped(monkeypatch):
    out, client, sleeps, _ = _run(monkeypatch, ["AAVE"], {"Aave": [fx.too_many()]})
    assert client.terms() == ["Aave"] * 4 and sleeps == [30, 60, 120]
    assert out["AAVE"].state == "capped" and "HTTP 429" in out["AAVE"].reason and out["AAVE"].points == []
    out, client, sleeps, _ = _run(monkeypatch, ["AAVE"], {"Aave": [fx.too_many(), fx.daily_frame(["Aave"], 100)]})
    assert client.terms() == ["Aave"] * 2 and sleeps == [30] and out["AAVE"].state == "ok"


def test_three_capped_in_a_row_stops_source(monkeypatch):
    syms = ["AAVE", "INJ", "ARB", "OP", "TIA"]
    script = {t: [fx.too_many()] for t in ("Aave", "Injective", "Arbitrum", "Optimism", "Celestia")}
    out, client, _, _ = _run(monkeypatch, syms, script, today=_day(0, 5))
    assert client.terms() == ["Aave"] * 4 + ["Injective"] * 4 + ["Arbitrum"] * 4
    assert all(out[s].state == "capped" for s in syms)
    assert all("skipped after repeated HTTP 429" == out[s].reason for s in ("OP", "TIA"))


def test_one_failure_does_not_touch_other_coins(monkeypatch):
    out, client, _, _ = _run(monkeypatch, ["AAVE", "INJ", "SOL"], {"Injective": [fx.forbidden()]})
    assert out["INJ"].state == "unavailable" and out["INJ"].reason == "fetch-failed: ResponseError(HTTP 403)"
    assert out["AAVE"].state == "ok" and out["SOL"].state == "ok" and len(client.payloads) == 3


def _main(monkeypatch, symbols, script=None, today=fx.TODAY):
    client = TermClient(script, today)
    _install(monkeypatch, client)
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    return refresh_attention.main(["--sources", "trends", "--symbols", ",".join(symbols)], client=c, today=today,
                                  sleep=lambda s: None), client


def test_failed_coin_keeps_previous_series(monkeypatch):
    d1, d2 = fx.TODAY, fx.TODAY + timedelta(days=1)
    _main(monkeypatch, ["AAVE", "INJ"], today=d1)
    before = store.read_points("trends", "INJ")
    assert len(before) == 100
    new = fx.daily_frame(["Aave"], 100, end=d2 - timedelta(days=1), values={"Aave": [50 + i % 7 for i in range(100)]})
    _main(monkeypatch, ["AAVE", "INJ"], {"Aave": [new], "Injective": [fx.forbidden()]}, today=d2)
    assert store.read_points("trends", "INJ") == before
    aave = store.read_points("trends", "AAVE")
    assert len(aave) == 100 and aave[-1][0] == d1 and [v for _, v in aave] == [50.0 + i % 7 for i in range(100)]


def test_time_budget_caps_the_rest(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(refresh_attention, "_clock", lambda: t[0])
    client = TermClient()
    _install(monkeypatch, client)

    def sleep(s):
        t[0] += 200.0
    syms = ["AAVE", "INJ", "ARB", "OP", "TIA"]
    series = refresh_attention._run_trends(syms, None, _day(0, 5), sleep)
    out = {s.symbol: s for s in series}
    assert refresh_attention.TRENDS_TIME_BUDGET_S == 540
    assert client.terms() == ["Aave", "Injective", "Arbitrum", "Optimism"]  # 0, 200, 400 < 540; 600 stops
    assert out["TIA"].state == "capped" and out["TIA"].reason == "time budget reached"
    assert all(out[s].state == "ok" for s in ("AAVE", "INJ", "ARB", "OP"))
    assert refresh_attention.trends_summary(series) == "ok 4, time-budget 1"


def test_summary_line_counts_every_outcome(monkeypatch, capsys):
    script = {"Injective": [_zeros("Injective")], "Arbitrum": [fx.weekly_frame(["Arbitrum"])],
              "Optimism": [fx.daily_frame(["Optimism"], 50)], "/m/0sol": [fx.too_many()],
              "Celestia": [RuntimeError("boom " + fx.SECRET)]}
    _run(monkeypatch, ["AAVE", "INJ", "ARB", "OP", "SOL", "TIA", "LINK", "USDX"], script)
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("trends detail:")]
    assert lines == [("trends detail: ok 1, too-little-interest 1, skipped-unqualified 1, no-keyword 1, non-daily 1, "
                      "rate-limited 1, insufficient-history 1, failed(RuntimeError) 1")]
    assert fx.SECRET not in lines[0]


def test_exit_code_success_with_rate_limited_count(monkeypatch, capsys):
    rc, _ = _main(monkeypatch, ["AAVE", "SOL"], {"/m/0sol": [fx.too_many()]})
    out = capsys.readouterr().out
    line = next(ln for ln in out.splitlines() if ln.startswith("trends:"))
    assert rc == 0 and line.startswith("trends: 1/2 ok, 100 rows written") and "rate-limited 1" in line
    assert attention_extra.classify("trends", line).status == "ok"


def test_all_rate_limited_line_is_unavailable_never_zero_rows(monkeypatch, capsys):
    rc, _ = _main(monkeypatch, ["AAVE", "INJ"], {"Aave": [fx.too_many()], "Injective": [fx.too_many()]})
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("trends:"))
    assert line.startswith("trends: 0/2 ok, 0 rows written") and "rate-limited 2" in line
    assert attention_extra.classify("trends", line).status == "unavailable" and rc == 2
    assert store.read_points("trends", "AAVE") == []


def test_pytrends_missing_marks_fetchable_coins_unavailable(monkeypatch, capsys):
    def factory():
        raise PytrendsMissing("pytrends")
    monkeypatch.setattr(refresh_attention, "TRENDREQ_FACTORY", factory)
    series = refresh_attention._run_trends(["AAVE", "USDX"], None, fx.TODAY, lambda s: None)
    out = {s.symbol: s for s in series}
    assert out["AAVE"].reason == "pytrends not installed" and out["USDX"].reason == "no keyword mapped"
    line = "trends: 0/2 ok, 0 rows written [other 2] reasons: no keyword mapped x1; pytrends not installed x1"
    assert attention_extra.classify("trends", line).status == "unavailable"


def test_summary_counts_quiet_then_surge(monkeypatch, capsys):
    surge = fx.daily_frame(["Aave"], 100, values={"Aave": [0] * 93 + [80] * 7})
    out, _, _, _ = _run(monkeypatch, ["AAVE", "INJ"], {"Aave": [surge]})
    assert out["AAVE"].reason == trends.QUIET_THEN_SURGE and out["AAVE"].points == []
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("trends detail:")]
    assert lines == ["trends detail: ok 1, quiet-then-surge 1"]
    assert store.read_pull_archive("trends", fx.TODAY).keys() == {"INJ"}  # missing coins are never archived


def test_replace_mode_pinned_to_trends_only(monkeypatch, isolated_cache):
    """Only the Trends source writes with replace-series; every other source keeps first-write-wins."""
    from api.tests.data.attention.conftest import wiki_payload
    assert refresh_attention.WRITE_MODES == {"trends": "replace-series"}
    calls = []
    real = store.write_series

    def spy(s, today=None, **kw):
        calls.append((s.source, kw.get("mode", "first")))
        return real(s, today=today, **kw)
    monkeypatch.setattr(refresh_attention.store, "write_series", spy)
    _install(monkeypatch, TermClient())

    def handler(r):
        return httpx.Response(200, json=wiki_payload(100, end=fx.TODAY - timedelta(days=1)))
    c = httpx.Client(transport=httpx.MockTransport(handler))
    refresh_attention.main(["--sources", "wikipedia,trends", "--symbols", "BTC,AAVE"], client=c, today=fx.TODAY,
                           sleep=lambda s: None)
    assert ("wikipedia", "first") in calls and ("trends", "replace-series") in calls
    assert {m for src, m in calls if src != "trends"} == {"first"}
    assert {m for src, m in calls if src == "trends"} == {"replace-series"}


def test_time_budget_checked_inside_backoff(monkeypatch):
    """A backoff wait that would end past the budget is not started: the coin and the rest are capped."""
    t = [0.0]
    monkeypatch.setattr(refresh_attention, "_clock", lambda: t[0])
    monkeypatch.setattr(refresh_attention, "TRENDS_TIME_BUDGET_S", 100)
    client = TermClient({"Aave": [fx.too_many()]})
    _install(monkeypatch, client)
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        t[0] += s
    series = refresh_attention._run_trends(["AAVE", "INJ"], None, _day(0, 2), sleep)
    out = {s.symbol: s for s in series}
    assert sleeps == [30, 60] and client.terms() == ["Aave"] * 3  # 90 + 120 > 100: the third wait never starts
    assert out["AAVE"].state == "capped" and out["AAVE"].reason == "time budget reached"
    assert out["INJ"].state == "capped" and out["INJ"].reason == "time budget reached"


@pytest.mark.parametrize("trx, apt, fetched", [
    ("Tron", "Aptos", []),                                    # bare names: skipped, no request
    ("tron crypto", "Aptos Crypto", ["tron crypto", "Aptos Crypto"]),   # qualified-term fallback: pulled
])
def test_risky_symbol_bare_term_skipped_qualified_term_fetched(monkeypatch, _env, capsys, trx, apt, fetched):
    kw = dict(KEYWORDS, TRX={"term": trx, "label": "TRON", "note": "qualified-term fallback"},
              APT={"term": apt, "label": "Aptos"})
    _env.write_text(json.dumps(kw))
    out, client, _, _ = _run(monkeypatch, ["TRX", "APT", "SOL"], today=_day(0, len(fetched) + 1))
    assert client.terms() == fetched + ["/m/0sol"]  # a topic entry is always fetched
    for s in ("TRX", "APT"):
        assert (out[s].state == "ok") == bool(fetched)
        assert bool(fetched) or out[s].reason == trends.NAME_AMBIGUOUS
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("trends detail:"))
    assert line == ("trends detail: ok 3" if fetched else "trends detail: ok 1, skipped-unqualified 2")


def test_factory_returning_none_marks_coins_unavailable(monkeypatch):
    monkeypatch.setattr(refresh_attention, "TRENDREQ_FACTORY", lambda: None)
    series = refresh_attention._run_trends(["AAVE"], None, fx.TODAY, lambda s: None)
    assert series[0].state == "unavailable" and series[0].reason == "session-failed: no client"


def test_duplicate_symbols_cost_one_request(monkeypatch):
    out, client, _, _ = _run(monkeypatch, ["AAVE", "aave", "Aave", "INJ"])
    assert sorted(client.terms()) == ["Aave", "Injective"] and set(out) == {"AAVE", "INJ"}


def test_one_store_failure_keeps_storing_the_others(monkeypatch, capsys):
    real = store.write_series

    def flaky(s, today=None, **kw):
        if s.symbol == "INJ":
            raise OSError("disk " + fx.SECRET)
        return real(s, today=today, **kw)
    monkeypatch.setattr(refresh_attention.store, "write_series", flaky)
    rc, _ = _main(monkeypatch, ["AAVE", "INJ", "ARB"])
    assert len(store.read_points("trends", "AAVE")) == 100 and len(store.read_points("trends", "ARB")) == 100
    assert store.read_points("trends", "INJ") == []
    out = capsys.readouterr()
    text = out.out + out.err
    lines = [ln for ln in text.splitlines() if ln.startswith("trends:")]
    assert lines[0].startswith("trends: 2/3 ok, 200 rows written") and "store-failed: OSError x1" in lines[0]
    assert lines[-1] == "trends: error store-failed: OSError x1"
    assert attention_extra.classify("trends", lines[-1]).status == "failed" and rc == 1
    assert fx.SECRET not in text


# --- T159: a store failure must be the LAST line of its source even when stdout is block-buffered (CI pipes
# `2>&1 | tee` without PYTHONUNBUFFERED), so the verifier, which reads the last `<source>:` line, goes red. ---

_DRIVER = r'''
import json, sys
from pathlib import Path
import httpx
from api.data import cache
from api.data.attention import http_retry, store, trends_keywords, wikipedia
from api.scripts import refresh_attention as ra
from api.tests import trends_fixtures as fx
from api.tests.data.attention.conftest import wiki_payload
source, root = sys.argv[1], Path(sys.argv[2])
cache.CACHE_ROOT = root
wikipedia.PACER = http_retry.Pacer(0)
kw = root / "kw.json"
kw.write_text(json.dumps({"_anchor": {"term": "Bitcoin", "label": "Bitcoin"},
                          "AAVE": {"term": "Aave", "label": "Aave"}, "INJ": {"term": "Injective", "label": "Inj"}}))
trends_keywords.KEYWORDS_PATH = kw
ra._jitter = lambda: 0.0
frames = {"Aave": fx.daily_frame(["Aave"], 100), "Injective": fx.daily_frame(["Injective"], 100)}
class C:
    def build_payload(self, kw_list, **k): self.t = kw_list[0]
    def interest_over_time(self): return frames[self.t]
ra.TRENDREQ_FACTORY = C
real = store.write_series
def flaky(s, today=None, **k):
    if s.symbol in ("ETH", "INJ"):
        raise OSError("disk full")
    return real(s, today=today, **k)
store.write_series = flaky
end = fx.TODAY - __import__("datetime").timedelta(days=1)
c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=wiki_payload(100, end=end))))
syms = "BTC,ETH" if source == "wikipedia" else "AAVE,INJ"
sys.exit(ra.main(["--sources", source, "--symbols", syms], client=c, today=fx.TODAY, sleep=lambda s: None))
'''


@pytest.mark.parametrize("source", ["wikipedia", "trends"])
def test_store_failure_is_last_line_with_block_buffered_stdout(tmp_path, source):
    import os
    import subprocess
    import sys
    from pathlib import Path
    repo = Path(__file__).resolve().parents[3]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    proc = subprocess.run([sys.executable, "-c", _DRIVER, source, str(tmp_path)], cwd=repo, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120, check=False)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith(source + ":")]
    assert len(lines) >= 2, proc.stdout[-2000:]
    assert lines[-1] == f"{source}: error store-failed: OSError x1"
    assert attention_extra.classify(source, lines[-1]).status == "failed"
    assert proc.returncode == 1 and "disk full" not in proc.stdout
    if source == "trends":  # the workflow verify step on this log
        out, _, failed = attention_extra.verify({"trends": proc.stdout}, tmp_path / "attention", fx.TODAY)
        assert "trends" in failed and any(o.startswith("summary trends: failed") for o in out)


def test_store_failed_reason_is_a_code_reason():
    assert attention_extra.reason_kind("store-failed: OSError") == "code"
    line = "trends: 0/2 ok, 0 rows written [other 2] reasons: store-failed: OSError x2"
    assert attention_extra.classify("trends", line).status == "failed"  # all stores failed: red, not a warning
