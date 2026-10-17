import json
import logging
import re
import subprocess
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from api.data.attention import registry, xsearch
from api.tests.data.attention.conftest import TODAY, client_for

CANARY = "canary-xtoken-" + "9f3a7c"
ENV = ("X_LIVE", "X_MAX_READS_PER_RUN", "X_MAX_READS_PER_DAY", "X_MAX_USD_PER_DAY", "X_USD_PER_READ", "X_BEARER_TOKEN")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ENV:
        monkeypatch.delenv(k, raising=False)


def _live(monkeypatch, **kw):
    monkeypatch.setenv("X_LIVE", "1")
    monkeypatch.setenv("X_BEARER_TOKEN", CANARY)
    for k, v in kw.items():
        monkeypatch.setenv(k, str(v))


def _counts(counts):
    days = [TODAY - timedelta(days=len(counts) - i) for i in range(len(counts) + 1)]
    data = [{"start": f"{d}T00:00:00Z", "end": f"{d}T23:59:59Z", "tweet_count": c}
            for d, c in zip(days, counts + [1])]
    return {"data": data, "meta": {}}


class Stub:
    def __init__(self, payload=None, status=200):
        self.urls, self.headers = [], []
        self.payload, self.status = payload or _counts([10] * 7), status

    def __call__(self, r: httpx.Request):
        self.urls.append(str(r.url))
        self.headers.append(dict(r.headers))
        return httpx.Response(self.status, json=self.payload)


def _run(symbols, stub, run=None):
    run = run or xsearch.RunBudget()
    return [xsearch.fetch_series(s, client=client_for(stub), today=TODAY, run=run) for s in symbols]


def test_default_is_dry_run_zero_network(monkeypatch, isolated_cache):
    monkeypatch.setenv("X_BEARER_TOKEN", CANARY)

    def fail(r):
        raise AssertionError("dry run must not call the network")

    out = _run(["BTC", "ETH"], fail)
    assert all(s.state == "unavailable" and "dry-run" in s.reason for s in out)
    assert not (isolated_cache / "xsearch_usage").exists()


def test_estimate_zero_network_and_numbers(monkeypatch, isolated_cache):
    monkeypatch.setenv("X_MAX_READS_PER_RUN", "3")
    monkeypatch.setenv("X_USD_PER_READ", "0.5")
    monkeypatch.setenv("X_MAX_USD_PER_DAY", "10")
    e = xsearch.estimate(["A", "B", "C", "D", "E"], today=TODAY)
    assert e.planned_reads == 3 and e.usd == pytest.approx(1.5) and e.live is False


def test_no_token_live_is_unavailable(monkeypatch, isolated_cache):
    monkeypatch.setenv("X_LIVE", "1")
    stub = Stub()
    out = _run(["BTC"], stub)
    assert out[0].state == "unavailable" and stub.urls == []


def test_live_read_sends_token_only_in_header(monkeypatch, isolated_cache):
    _live(monkeypatch)
    stub = Stub()
    s = _run(["BTC"], stub)[0]
    assert stub.headers[0]["authorization"] == f"Bearer {CANARY}"
    assert CANARY not in stub.urls[0]
    assert s.state == "ok" and s.points == [(TODAY - timedelta(days=1), 10.0)]
    assert CANARY not in repr(s) and CANARY not in s.reason


def test_run_cap_stops(monkeypatch, isolated_cache):
    _live(monkeypatch, X_MAX_READS_PER_RUN=2)
    stub = Stub()
    out = _run(["A", "B", "C", "D"], stub)
    assert len(stub.urls) == 2
    assert [s.state for s in out] == ["ok", "ok", "capped", "capped"]


def test_day_cap_stops_and_persists(monkeypatch, isolated_cache):
    _live(monkeypatch, X_MAX_READS_PER_DAY=3)
    stub = Stub()
    _run(["A", "B"], stub)
    out = _run(["C", "D"], stub)  # fresh RunBudget, same day counter
    assert len(stub.urls) == 3
    assert [s.state for s in out] == ["ok", "capped"]


def test_usd_cap_stops(monkeypatch, isolated_cache):
    _live(monkeypatch, X_MAX_USD_PER_DAY="0.05", X_USD_PER_READ="0.02")
    stub = Stub()
    out = _run(["A", "B", "C"], stub)
    assert len(stub.urls) == 2
    assert out[2].state == "capped"


def test_failed_reads_still_count(monkeypatch, isolated_cache):
    _live(monkeypatch, X_MAX_READS_PER_RUN=1)
    stub = Stub(status=500)
    out = _run(["A", "B"], stub)
    assert out[0].state == "unavailable" and out[1].state == "capped" and len(stub.urls) == 1


def test_canary_never_leaks(monkeypatch, isolated_cache, caplog):
    _live(monkeypatch)
    caplog.set_level(logging.DEBUG)

    def boom(r: httpx.Request):
        raise RuntimeError(f"failed with {r.headers['authorization']}")

    out = _run(["A"], boom)
    assert out[0].state == "unavailable"
    blob = caplog.text + repr(out) + out[0].reason + repr(xsearch.estimate(["A"], today=TODAY))
    for f in Path(isolated_cache).rglob("*"):
        if f.is_file():
            blob += f.read_text(errors="ignore")
    assert CANARY not in blob
    assert not any(CANARY in str(v) for v in vars(xsearch).values())


def test_spam_flag_on_spike(monkeypatch, isolated_cache):
    _live(monkeypatch)
    s = _run(["A"], Stub(_counts([5, 5, 5, 5, 5, 5, 900])))[0]
    assert "spam" in s.reason


def test_x_is_low_weight_and_registered():
    assert "xsearch" in registry.FETCHERS and "reddit" in registry.FETCHERS
    assert 0 < xsearch.WEIGHT < 1


def test_no_bearer_pattern_in_tracked_files():
    root = Path(__file__).resolve().parents[4]
    files = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True).stdout.split()
    pat = re.compile(r"A{21}[A-Za-z0-9]*%[0-9A-Fa-f]{2}[A-Za-z0-9%]{20,}|Bearer [A-Za-z0-9%_\-]{30,}")
    hits = []
    for f in files:
        p = root / f
        try:
            if p.is_file() and p.stat().st_size < 2_000_000 and pat.search(p.read_text(errors="ignore")):
                hits.append(f)
        except OSError:
            pass
    assert hits == []
