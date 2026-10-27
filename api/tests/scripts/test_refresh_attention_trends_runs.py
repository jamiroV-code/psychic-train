"""T197 Trends run file (per-coin outcomes per daily run) and the one-time retry of an `empty response`.
Fake TrendReq only; no network, no real sleeping."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from api.data import cache
from api.data.attention import store, trends, trends_keywords
from api.scripts import attention_extra, refresh_attention
from api.tests import trends_fixtures as fx
from api.tests.scripts.test_refresh_attention_trends import (
    KEYWORDS,
    TermClient,
    _day,
    _install,
    _main,
    _run,
    _zeros,
)

OUTCOMES = {"ok", "too-little-interest", "quiet-then-surge", "no-keyword", "skipped-unqualified", "failed",
            "capped", "time-budget"}
COIN_KEYS = {"outcome", "reason", "keyword_kind", "median", "zero_share_pct", "last7_vs_prior28_ratio",
             "attempts", "retried", "retry_skipped"}


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path, isolated_cache):
    fx.block_network(monkeypatch)
    path = tmp_path / "kw.json"
    path.write_text(json.dumps(KEYWORDS))
    monkeypatch.setattr(trends_keywords, "KEYWORDS_PATH", path)
    monkeypatch.setattr(refresh_attention, "_jitter", lambda: 0.0)
    return path


def run_file(day=fx.TODAY) -> Path:
    return cache.CACHE_ROOT / "attention" / "trends_runs" / f"{day.isoformat()}.json"


def load(day=fx.TODAY) -> dict:
    return json.loads(run_file(day).read_text(encoding="utf-8"))


EMPTY = pd.DataFrame()


# --- (a) the run file ---

def test_run_file_records_every_outcome(monkeypatch):
    surge = fx.daily_frame(["Arbitrum"], 100, values={"Arbitrum": [0] * 93 + [80] * 7})
    script = {"Injective": [_zeros("Injective")], "Arbitrum": [surge], "Optimism": [fx.forbidden()],
              "Celestia": [fx.too_many()]}
    _run(monkeypatch, ["AAVE", "INJ", "ARB", "OP", "TIA", "SOL", "LINK", "USDX", "ZZZ"], script)
    doc = load()
    assert set(doc) == {"run_started_utc", "run_finished_utc", "pytrends_version", "budget_s", "coins", "totals"}
    assert doc["budget_s"] == refresh_attention.TRENDS_TIME_BUDGET_S and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", doc["run_started_utc"])
    assert doc["run_started_utc"] <= doc["run_finished_utc"]
    coins = doc["coins"]
    assert set(coins) == {"AAVE", "INJ", "ARB", "OP", "TIA", "SOL", "LINK", "USDX", "ZZZ"}
    assert all(set(c) == COIN_KEYS and c["outcome"] in OUTCOMES for c in coins.values())
    got = {s: coins[s]["outcome"] for s in coins}
    assert got == {"AAVE": "ok", "INJ": "too-little-interest", "ARB": "quiet-then-surge", "OP": "failed",
                   "TIA": "capped", "SOL": "ok", "LINK": "skipped-unqualified", "USDX": "no-keyword",
                   "ZZZ": "no-keyword"}
    assert coins["AAVE"]["keyword_kind"] == "term" and coins["SOL"]["keyword_kind"] == "topic"
    assert coins["USDX"]["keyword_kind"] == "none" and coins["ZZZ"]["keyword_kind"] == "none"
    assert coins["OP"]["reason"] == "ResponseError(HTTP 403)" and coins["TIA"]["reason"].endswith("(HTTP 429)")
    assert coins["TIA"]["attempts"] == 4 and coins["TIA"]["retried"] is False
    assert coins["AAVE"]["attempts"] == 1 and coins["AAVE"]["retried"] is False
    assert coins["USDX"]["attempts"] == 0
    # numbers where computable: ok, too-little-interest, quiet-then-surge; null elsewhere
    for sym in ("AAVE", "INJ", "ARB"):
        c = coins[sym]
        assert isinstance(c["median"], (int, float)) and isinstance(c["zero_share_pct"], (int, float)), sym
    assert coins["INJ"]["median"] == 0 and coins["INJ"]["zero_share_pct"] == 100
    assert coins["INJ"]["last7_vs_prior28_ratio"] is None  # prior 28 days average 0: no ratio
    assert coins["ARB"]["median"] == 0 and coins["ARB"]["zero_share_pct"] == 93
    assert coins["ARB"]["last7_vs_prior28_ratio"] is None
    for sym in ("OP", "TIA", "LINK", "USDX"):
        assert (coins[sym]["median"], coins[sym]["zero_share_pct"], coins[sym]["last7_vs_prior28_ratio"]) == \
            (None, None, None)
    flat = fx.daily_frame(["Aave"], 100, end=fx.TODAY, values={"Aave": [10] * 93 + [20] * 7})
    _run(monkeypatch, ["AAVE"], {"Aave": [flat]}, today=fx.TODAY + timedelta(days=1))
    c = load(fx.TODAY + timedelta(days=1))["coins"]["AAVE"]
    assert c["median"] == 10 and c["zero_share_pct"] == 0 and c["last7_vs_prior28_ratio"] == 2.0
    t = doc["totals"]
    assert t["ok"] == 2 and t["failed"] == 1 and t["capped"] == 1 and t["no-keyword"] == 2
    assert t["too-little-interest"] == 1 and t["quiet-then-surge"] == 1 and t["skipped-unqualified"] == 1
    assert t["retried"] == 0 and t["recovered"] == 0 and t["retry_skipped"] == 0


def test_run_file_records_time_budget_outcome(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(refresh_attention, "_clock", lambda: t[0])
    monkeypatch.setattr(refresh_attention, "TRENDS_TIME_BUDGET_S", 100)
    _install(monkeypatch, TermClient(today=_day(0, 3)))

    def sleep(s):
        t[0] += 200.0
    refresh_attention._run_trends(["AAVE", "INJ", "ARB"], None, _day(0, 3), sleep)
    coins = load(_day(0, 3))["coins"]
    assert coins["AAVE"]["outcome"] == "ok" and coins["INJ"]["outcome"] == "ok"  # the budget is checked before a sleep
    assert coins["ARB"]["outcome"] == "time-budget" and coins["ARB"]["attempts"] == 0
    assert coins["ARB"]["reason"] == "time budget reached" and coins["ARB"]["keyword_kind"] == "term"


def test_second_run_same_day_appends_never_overwrites(monkeypatch):
    _run(monkeypatch, ["AAVE"])
    first = load()
    assert "runs" not in first
    _run(monkeypatch, ["AAVE", "INJ"])
    doc = load()
    assert len(doc["runs"]) == 2 and doc["runs"][0] == first
    assert set(doc["runs"][1]["coins"]) == {"AAVE", "INJ"}
    _run(monkeypatch, ["INJ"])
    doc = load()
    assert len(doc["runs"]) == 3 and doc["runs"][0] == first
    assert [set(r["coins"]) for r in doc["runs"]][2] == {"INJ"}


def test_other_day_is_another_file(monkeypatch):
    _run(monkeypatch, ["AAVE"])
    _run(monkeypatch, ["AAVE"], today=fx.TODAY + timedelta(days=1))
    assert run_file().exists() and run_file(fx.TODAY + timedelta(days=1)).exists()
    assert "runs" not in load()


def test_write_is_atomic_and_leaves_no_temp(monkeypatch):
    _run(monkeypatch, ["AAVE"])
    before = run_file().read_bytes()

    def boom(*_a, **_k):
        raise OSError("replace failed " + fx.SECRET)
    monkeypatch.setattr(os, "replace", boom)
    series = refresh_attention._run_trends(["AAVE", "INJ"], None, fx.TODAY, lambda s: None)
    assert {s.symbol: s.state for s in series} == {"AAVE": "ok", "INJ": "ok"}  # the pull itself is not lost
    assert run_file().read_bytes() == before  # the earlier run data is untouched
    assert not [p for p in run_file().parent.iterdir() if p.name.endswith(".tmp")]


def _block_run_file():
    """Make the run-file write fail without touching anything else: a directory sits on its path."""
    run_file().mkdir(parents=True)


def test_run_file_failure_is_store_failed_and_other_coins_stored(monkeypatch, capsys):
    _block_run_file()
    rc, _ = _main(monkeypatch, ["AAVE", "INJ"])
    assert len(store.read_points("trends", "AAVE")) == 100 and len(store.read_points("trends", "INJ")) == 100
    out = capsys.readouterr()
    text = out.out + out.err
    lines = [ln for ln in text.splitlines() if ln.startswith("trends:")]
    assert lines[0].startswith("trends: 2/2 ok, 200 rows written")
    assert lines[-1].startswith("trends: error store-failed: ") and lines[-1].endswith(" x1")
    assert attention_extra.classify("trends", lines[-1]).status == "failed" and rc == 1
    assert fx.SECRET not in text


def test_failed_run_file_write_does_not_stop_the_pull(monkeypatch):
    _block_run_file()
    out, client, _, _ = _run(monkeypatch, ["AAVE", "INJ", "SOL"], {"Injective": [fx.forbidden()]})
    assert out["AAVE"].state == "ok" and out["SOL"].state == "ok" and len(client.payloads) == 3


def test_reasons_never_carry_a_message_or_body(monkeypatch):
    script = {"Aave": [RuntimeError("boom " + fx.SECRET)], "Injective": [fx.forbidden()],
              "Arbitrum": [ConnectionError(fx.SECRET)]}
    _run(monkeypatch, ["AAVE", "INJ", "ARB"], script)
    text = run_file().read_text(encoding="utf-8")
    assert not any(bad in text for bad in fx.FORBIDDEN_IN_OUTPUT) and "boom" not in text
    coins = load()["coins"]
    assert coins["AAVE"]["reason"] == "RuntimeError" and coins["INJ"]["reason"] == "ResponseError(HTTP 403)"
    assert coins["ARB"]["reason"] == "ConnectionError"
    assert all(len(c["reason"] or "") <= 80 for c in coins.values())


def test_file_stays_small_for_a_full_universe(monkeypatch, _env):
    kw = {"_anchor": {"term": "Bitcoin", "label": "Bitcoin"}}
    kw.update({f"C{i}": {"term": f"coin number {i}", "label": f"C{i}"} for i in range(100)})
    _env.write_text(json.dumps(kw))
    syms = [f"C{i}" for i in range(100)]
    script = {f"coin number {i}": [EMPTY] for i in range(0, 100, 3)}
    _run(monkeypatch, syms, script)
    _run(monkeypatch, syms, script)
    assert run_file().stat().st_size < 40_000
    assert len(load()["runs"]) == 2


def test_run_file_is_read_by_no_store_logic(monkeypatch):
    _run(monkeypatch, ["AAVE"])
    assert store.read_points("trends", "AAVE") == []  # _run_trends alone stores nothing; the file is no series
    assert not (cache.CACHE_ROOT / "attention" / "trends" / f"{fx.TODAY.isoformat()}.json").exists()
    assert store.read_pull_archive("trends", fx.TODAY).keys() == {"AAVE"}


def test_coin_record_reason_is_cleaned_and_cut():
    from api.data.attention.types import SourceSeries
    hostile = "fetch-failed: " + "Err\n::error::{" + fx.SECRET + "}" * 30
    rec = refresh_attention._run_coin_record(SourceSeries("trends", "X", [], "unavailable", hostile), {})
    assert rec["reason"] and len(rec["reason"]) <= 80 and "::" not in rec["reason"]
    assert not set("\n{}") & set(rec["reason"])
    long = SourceSeries("trends", "X", [], "unavailable", "fetch-failed: " + "E" * 500)
    assert len(refresh_attention._run_coin_record(long, {})["reason"]) == 80
    assert rec["keyword_kind"] == "none" and rec["attempts"] == 0 and rec["retried"] is False
    ok = refresh_attention._run_coin_record(SourceSeries("trends", "X", [(fx.TODAY, 5.0)], "ok", ""), {})
    assert ok["outcome"] == "ok" and ok["reason"] is None


def test_series_stats_arithmetic():
    values = [1.0] * 20 + [0.0] * 10 + [30.0] * 63 + [60.0] * 7
    st = trends.series_stats(values)
    assert st["median"] == 30.0 and st["zero_share_pct"] == 10.0
    assert st["last7_vs_prior28_ratio"] == 2.0  # 60 over the 28 days of 30
    ramp = [10.0] * 65 + [float(i) for i in range(1, 29)] + [29.0] * 7  # a VARYING prior window pins its 28 days
    assert trends.series_stats(ramp)["last7_vs_prior28_ratio"] == 2.0  # 29 over a prior mean of 14.5
    assert trends.series_stats([0.0] * 100)["last7_vs_prior28_ratio"] is None
    assert trends.series_stats([5.0] * 20)["last7_vs_prior28_ratio"] is None  # fewer than 35 days


def test_fetch_alone_stats_are_per_call():
    client = TermClient({"Aave": [fx.daily_frame(["Aave"], 100), EMPTY]})
    stats: dict = {}
    trends.fetch_alone("AAVE", "Aave", client, today=fx.TODAY, stats=stats)
    assert stats["median"] is not None
    trends.fetch_alone("AAVE", "Aave", client, today=fx.TODAY, stats=stats)  # empty response
    assert stats == {}


# --- (b) the deferred retry of an `empty response` (T200): after the whole main pass, once per coin ---

def _ok(term, day):
    return fx.daily_frame([term], 100, end=day - timedelta(days=1))


def _many(path, n):
    """A keyword file with n term coins C000.. (term T000..) besides the anchor."""
    kw = {"_anchor": {"term": "Bitcoin", "label": "Bitcoin"}}
    kw.update({f"C{i:03d}": {"term": f"T{i:03d}", "label": f"T{i:03d}"} for i in range(n)})
    path.write_text(json.dumps(kw))
    return [f"C{i:03d}" for i in range(n)], [f"T{i:03d}" for i in range(n)]


class ClockClient(TermClient):
    """Every request takes `cost` fake seconds on the shared clock `t`."""

    def __init__(self, t, cost, *a, **k):
        super().__init__(*a, **k)
        self.t, self.cost = t, cost

    def interest_over_time(self):
        self.t[0] += self.cost
        return super().interest_over_time()


def _fake_clock(monkeypatch, budget=None):
    t = [0.0]
    monkeypatch.setattr(refresh_attention, "_clock", lambda: t[0])
    if budget is not None:
        monkeypatch.setattr(refresh_attention, "TRENDS_TIME_BUDGET_S", budget)

    def sleep(s):
        t[0] += s
        sleeps.append(s)
    sleeps: list[float] = []
    return t, sleep, sleeps


def test_empty_is_retried_after_the_main_pass_not_inline(monkeypatch, capsys):
    out, client, sleeps, _ = _run(monkeypatch, ["AAVE", "INJ"], {"Aave": [EMPTY, fx.daily_frame(["Aave"], 100)]},
                                  today=_day(0, 2))
    assert out["AAVE"].state == "ok" and len(out["AAVE"].points) == 100
    assert client.terms() == ["Aave", "Injective", "Aave"]  # the retry waits for INJ
    assert sleeps == [3.0, 10.0]  # usual spacing first, then the retry wait
    c = load(_day(0, 2))["coins"]["AAVE"]
    assert c["outcome"] == "ok" and c["attempts"] == 2 and c["retried"] is True and c["retry_skipped"] is None
    assert c["median"] is not None and c["zero_share_pct"] is not None  # the retry's own stats, not the empty pull's
    assert load(_day(0, 2))["coins"]["INJ"]["attempts"] == 1
    t = load(_day(0, 2))["totals"]
    assert t["retried"] == 1 and t["recovered"] == 1 and t["retry_skipped"] == 0
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("trends detail:"))
    assert line == "trends detail: ok 2, retried 1 (recovered 1, skipped 0)"


def test_recovered_coin_is_stored_like_an_ok_coin(monkeypatch):
    rc, _ = _main(monkeypatch, ["AAVE", "INJ"], {"Aave": [EMPTY, fx.daily_frame(["Aave"], 100)]})
    assert rc == 0 and len(store.read_points("trends", "AAVE")) == 100


def test_retry_wait_has_jitter(monkeypatch):
    monkeypatch.setattr(refresh_attention, "_jitter", lambda: 1.5)
    _, _, sleeps, _ = _run(monkeypatch, ["AAVE"], {"Aave": [EMPTY, fx.daily_frame(["Aave"], 100)]})
    assert sleeps == [11.5] and refresh_attention.TRENDS_EMPTY_RETRY_WAIT_S == 10


def test_empty_twice_is_failed_not_capped(monkeypatch, capsys):
    out, client, sleeps, _ = _run(monkeypatch, ["AAVE"], {"Aave": [EMPTY]})
    assert out["AAVE"].state == "unavailable" and out["AAVE"].reason == "empty response"
    assert client.terms() == ["Aave", "Aave"] and sleeps == [10.0]  # one retry only
    c = load()["coins"]["AAVE"]
    assert (c["outcome"], c["reason"], c["attempts"], c["retried"]) == ("failed", "empty response", 2, True)
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("trends detail:"))
    assert line == "trends detail: failed(empty response) 1, retried 1 (recovered 0, skipped 0)"
    assert load()["totals"]["retried"] == 1 and load()["totals"]["recovered"] == 0


def test_429_is_never_retried_by_the_empty_rule(monkeypatch):
    _, client, sleeps, _ = _run(monkeypatch, ["AAVE"], {"Aave": [fx.too_many()]})
    assert client.terms() == ["Aave"] * 4 and sleeps == [30, 60, 120]  # the existing backoff, no extra 10 s retry
    c = load()["coins"]["AAVE"]
    assert c["outcome"] == "capped" and c["retried"] is False and c["attempts"] == 4 and c["retry_skipped"] is None


@pytest.mark.parametrize("item", [
    fx.forbidden(), ConnectionError("refused"), RuntimeError("boom"),
    fx.daily_frame(["Aave"], 100, values={"Aave": [150] * 100}),                         # bad-value
    fx.daily_frame(["Aave"], 100, end=fx.TODAY - timedelta(days=5)),                      # not-current
    fx.daily_frame(["Aave"], 100, end=fx.TODAY + timedelta(days=3)),                      # out-of-range
    fx.weekly_frame(["Aave"]),                                                            # non-daily
    fx.daily_frame(["Other"], 100),                                                       # missing-column
    fx.daily_frame(["Aave"], 50),                                                         # insufficient-history
    _zeros("Aave"),                                                                       # too-little-interest
])
def test_other_failures_are_never_retried(monkeypatch, item):
    _, client, sleeps, _ = _run(monkeypatch, ["AAVE", "INJ"], {"Aave": [item]}, today=_day(0, 2))
    assert client.terms() == ["Aave", "Injective"] and sleeps in ([3.0], [3.0, 30], [3.0, 30, 60, 120])
    assert 10.0 not in sleeps
    c = load(_day(0, 2))["coins"]["AAVE"]
    assert c["retried"] is False and c["retry_skipped"] is None


def test_retry_skipped_when_the_budget_has_no_room(monkeypatch, capsys):
    t, sleep, sleeps = _fake_clock(monkeypatch, budget=100)
    client = ClockClient(t, 45.0, {"Aave": [EMPTY]}, _day(0, 2))
    _install(monkeypatch, client)
    series = refresh_attention._run_trends(["AAVE", "INJ"], None, _day(0, 2), sleep)
    out = {s.symbol: s for s in series}
    assert t[0] == 93.0 and sleeps == [3.0]  # 93 + 10 > 100: no retry wait is started
    assert client.terms() == ["Aave", "Injective"]
    assert out["AAVE"].state == "unavailable" and out["AAVE"].reason == "empty response"
    c = load(_day(0, 2))["coins"]["AAVE"]
    assert (c["outcome"], c["reason"], c["attempts"], c["retried"]) == ("failed", "empty response", 1, False)
    assert c["retry_skipped"] == "retry-skipped-budget"
    t_ = load(_day(0, 2))["totals"]
    assert t_["retried"] == 0 and t_["retry_skipped"] == 1
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("trends detail:"))
    assert line.endswith(", retried 0 (recovered 0, skipped 1)")


def test_retry_is_checked_against_the_budget_including_its_sleep(monkeypatch):
    t, sleep, _ = _fake_clock(monkeypatch, budget=106)
    client = ClockClient(t, 45.0, {"Aave": [EMPTY]}, _day(0, 2))
    _install(monkeypatch, client)
    monkeypatch.setattr(refresh_attention, "_jitter", lambda: 4.0)  # 93 + 10 + 4 = 107 > 106, though 93 + 10 fits
    refresh_attention._run_trends(["AAVE", "INJ"], None, _day(0, 2), sleep)
    assert client.terms() == ["Aave", "Injective"] and load(_day(0, 2))["coins"]["AAVE"]["retried"] is False


def _twenty_empties(monkeypatch, _env, budget=None):
    syms, terms = _many(_env, 92)
    t, sleep, _ = _fake_clock(monkeypatch, **({} if budget is None else {"budget": budget}))
    day = _day(0, 92)
    empties = set(syms[::4][:20])
    script = {terms[syms.index(s)]: [EMPTY, _ok(terms[syms.index(s)], day)] for s in empties}
    client = ClockClient(t, 2.0, script, day)
    _install(monkeypatch, client)
    out = {s.symbol: s for s in refresh_attention._run_trends(syms, None, day, sleep)}
    return syms, empties, out, t, load(day)["coins"]


def test_twenty_empties_among_92_all_retried_inside_the_real_budget(monkeypatch, _env):
    syms, empties, out, t, coins = _twenty_empties(monkeypatch, _env)  # the real budget (780 s)
    assert len(empties) == 20 and all(out[s].state == "ok" for s in syms)  # healthy and retried coins all stored
    assert t[0] <= refresh_attention.TRENDS_TIME_BUDGET_S  # the whole run, retries included, fits the budget
    assert all(coins[s]["retried"] and coins[s]["attempts"] == 2 and not coins[s]["retry_skipped"] for s in empties)


def test_twenty_empties_among_92_cost_no_healthy_coin_when_budget_is_tight(monkeypatch, _env):
    syms, empties, out, t, coins = _twenty_empties(monkeypatch, _env, budget=540)
    healthy = [s for s in syms if s not in empties]
    assert all(out[s].state == "ok" for s in healthy)  # no healthy coin lost
    assert t[0] <= 540 + 2.0  # at most the last request that started inside the budget
    retried = [s for s in syms if coins[s]["retried"]]
    skipped = [s for s in syms if coins[s]["retry_skipped"]]
    assert retried and skipped and len(retried) + len(skipped) == 20
    assert {coins[s]["retry_skipped"] for s in skipped} == {"retry-skipped-budget"}
    assert all(coins[s]["outcome"] == "ok" and coins[s]["attempts"] == 2 for s in retried)
    assert all(coins[s]["outcome"] == "failed" and coins[s]["reason"] == "empty response" for s in skipped)
    assert max(syms.index(s) for s in retried) < min(syms.index(s) for s in skipped)


def test_retries_are_capped_per_run(monkeypatch, _env):
    assert refresh_attention.TRENDS_MAX_RETRIES_PER_RUN == 20
    syms, terms = _many(_env, 25)
    monkeypatch.setattr(refresh_attention, "TRENDS_TIME_BUDGET_S", 10 ** 6)
    day = _day(0, 25)
    client = TermClient({t_: [EMPTY, _ok(t_, day)] for t_ in terms}, day)
    _install(monkeypatch, client)
    sleeps: list[float] = []
    refresh_attention._run_trends(syms, None, day, sleeps.append)
    coins = load(day)["coins"]
    assert client.terms() == terms + terms[:20] and sleeps.count(10.0) == 20
    assert [coins[s]["retried"] for s in syms] == [True] * 20 + [False] * 5
    assert {coins[s]["retry_skipped"] for s in syms[20:]} == {"retry-skipped-cap"}
    assert all(coins[s]["outcome"] == "failed" and coins[s]["attempts"] == 1 for s in syms[20:])
    t_ = load(day)["totals"]
    assert (t_["retried"], t_["recovered"], t_["retry_skipped"]) == (20, 20, 5)


def test_detail_line_counts_skipped(monkeypatch, capsys, _env):
    syms, terms = _many(_env, 22)
    monkeypatch.setattr(refresh_attention, "TRENDS_TIME_BUDGET_S", 10 ** 6)
    day = _day(0, 22)
    _install(monkeypatch, TermClient({t_: [EMPTY] for t_ in terms[:21]}, day))
    refresh_attention._run_trends(syms, None, day, lambda s: None)
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("trends detail:"))
    assert line == "trends detail: ok 1, failed(empty response) 21, retried 20 (recovered 0, skipped 1)"


def test_empty_twice_does_not_feed_the_429_breaker(monkeypatch):
    syms = ["AAVE", "INJ", "ARB", "OP", "TIA"]
    script = {t: [EMPTY] for t in ("Aave", "Injective", "Arbitrum", "Optimism", "Celestia")}
    out, client, _, _ = _run(monkeypatch, syms, script, today=_day(0, 5))
    assert client.terms() == ["Aave", "Injective", "Arbitrum", "Optimism", "Celestia"] * 2
    assert all(out[s].reason == "empty response" for s in syms)


def test_429_in_the_deferred_pass_ends_it(monkeypatch, capsys):
    syms = ["AAVE", "INJ", "ARB"]
    script = {t: [EMPTY, fx.too_many()] for t in ("Aave", "Injective", "Arbitrum")}
    out, client, sleeps, _ = _run(monkeypatch, syms, script, today=_day(0, 3))
    # one request for the 429 coin, no backoff, and no further retry
    assert client.terms() == ["Aave", "Injective", "Arbitrum", "Aave"] and sleeps == [3.0, 3.0, 10.0]
    coins = load(_day(0, 3))["coins"]
    assert out["AAVE"].state == "capped" and out["AAVE"].reason.endswith("(HTTP 429)")
    assert (coins["AAVE"]["outcome"], coins["AAVE"]["attempts"], coins["AAVE"]["retried"]) == ("capped", 2, True)
    for s in ("INJ", "ARB"):
        assert (coins[s]["outcome"], coins[s]["reason"], coins[s]["attempts"], coins[s]["retried"]) == \
            ("failed", "empty response", 1, False)
        assert coins[s]["retry_skipped"] == "retry-skipped-rate-limit"
    assert load(_day(0, 3))["totals"]["retried"] == 1


def test_main_pass_breaker_is_unchanged_by_the_deferred_pass(monkeypatch):
    syms = ["AAVE", "INJ", "ARB", "OP", "TIA"]
    script = {t: [fx.too_many()] for t in ("Aave", "Injective", "Arbitrum")}
    out, client, _, _ = _run(monkeypatch, syms, script, today=_day(0, 5))
    assert client.terms() == ["Aave"] * 4 + ["Injective"] * 4 + ["Arbitrum"] * 4
    assert all(out[s].reason == "skipped after repeated HTTP 429" for s in ("OP", "TIA"))


def test_detail_line_unchanged_without_retries(monkeypatch, capsys):
    _run(monkeypatch, ["AAVE", "INJ"], {"Injective": [_zeros("Injective")]})
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("trends detail:"))
    assert line == "trends detail: ok 1, too-little-interest 1"


def test_summary_line_for_attention_extra_unchanged_with_retries(monkeypatch, capsys):
    rc, _ = _main(monkeypatch, ["AAVE", "INJ"], {"Aave": [EMPTY, fx.daily_frame(["Aave"], 100)]})
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("trends:"))
    assert rc == 0 and line.startswith("trends: 2/2 ok, 200 rows written [ok 2]") and "retried" not in line
    assert attention_extra.classify("trends", line).status == "ok"


# --- the 2>&1 pipe: a run-file failure is the LAST `trends:` line even with block-buffered stdout ---

_DRIVER = r'''
import json, sys
from pathlib import Path
import httpx
from api.data import cache
from api.data.attention import trends_keywords
from api.scripts import refresh_attention as ra
from api.tests import trends_fixtures as fx
root = Path(sys.argv[1])
cache.CACHE_ROOT = root
kw = root / "kw.json"
kw.write_text(json.dumps({"_anchor": {"term": "Bitcoin", "label": "Bitcoin"},
                          "AAVE": {"term": "Aave", "label": "Aave"}, "INJ": {"term": "Injective", "label": "Inj"}}))
trends_keywords.KEYWORDS_PATH = kw
ra._jitter = lambda: 0.0
(root / "attention" / "trends_runs" / (fx.TODAY.isoformat() + ".json")).mkdir(parents=True)
frames = {"Aave": fx.daily_frame(["Aave"], 100), "Injective": fx.daily_frame(["Injective"], 100)}
class C:
    def build_payload(self, kw_list, **k): self.t = kw_list[0]
    def interest_over_time(self): return frames[self.t]
ra.TRENDREQ_FACTORY = C
c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
sys.exit(ra.main(["--sources", "trends", "--symbols", "AAVE,INJ"], client=c, today=fx.TODAY, sleep=lambda s: None))
'''


def test_run_file_failure_is_last_line_with_block_buffered_stdout(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    proc = subprocess.run([sys.executable, "-c", _DRIVER, str(tmp_path)], cwd=repo, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120, check=False)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("trends:")]
    assert len(lines) >= 2, proc.stdout[-2000:]
    assert re.fullmatch(r"trends: error store-failed: \w+ x1", lines[-1]), lines[-1]
    assert attention_extra.classify("trends", lines[-1]).status == "failed" and proc.returncode == 1
    _, _, failed = attention_extra.verify({"trends": proc.stdout}, tmp_path / "attention", fx.TODAY)
    assert "trends" in failed
