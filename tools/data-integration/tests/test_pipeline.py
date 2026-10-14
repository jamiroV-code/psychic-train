"""pipeline.py: fake Fetcher + a FetchPass from request_access; writes only after every check passes."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.data import cache
from data_integration import status
from data_integration.approvals import ApprovalStore
from data_integration.gate import request_access
from data_integration.pipeline import run
from data_integration.provenance import read_records
from data_integration.types import FetchOutcome

from _helpers import fixed_clock, make_record

FIX = Path(__file__).parent / "fixtures"
URL = "https://a.example.test/data/prices"
SEL = "table.prices"


class FakeFetcher:
    def __init__(self, name="ok.html", st=status.OK):
        self.name, self.st, self.calls = name, st, 0

    def fetch(self, url, pass_):
        self.calls += 1
        body = (FIX / self.name).read_bytes() if self.st == status.OK else b""
        return FetchOutcome(self.st, url, 200 if self.st == status.OK else None, body)


@pytest.fixture
def fpass(tmp_path):
    store = ApprovalStore(tmp_path / "ap")
    store.write(make_record())
    return request_access("example-src", 2, store, fixed_clock())


@pytest.fixture
def db(tmp_path):
    return tmp_path / "scrape" / "adaptive.sqlite"


def _run(fetcher, fpass, db, **kw):
    args = dict(url=URL, selector=SEL, symbol="BTC-HIST", timeframe="1d", adaptive_path=db, clock=fixed_clock())
    args.update(kw)
    return run(fetcher, fpass, **args)


def _cache_files():
    root = cache.CACHE_ROOT / "ohlcv"
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


def test_first_run_is_uncertain_and_writes_nothing(fpass, db):
    r = _run(FakeFetcher(), fpass, db)
    assert r.status == status.UNCERTAIN
    assert _cache_files() == [] and not db.exists()


def test_accept_baseline_writes_data_provenance_and_baseline(fpass, db):
    r = _run(FakeFetcher(), fpass, db, accept_baseline=True)
    assert r.status == status.OK and r.rows == 4
    assert len(cache.read_ohlcv("BTC-HIST", "1d")) == 4
    recs = read_records("BTC-HIST", "1d")
    assert len(recs) == 1 and recs[0]["source"] == "example-src"
    assert db.is_file()


def test_rerun_unchanged_is_cache_hit_no_new_provenance(fpass, db):
    _run(FakeFetcher(), fpass, db, accept_baseline=True)
    data = cache.ohlcv_path("BTC-HIST", "1d").read_bytes()
    r = _run(FakeFetcher(), fpass, db)
    assert r.status == status.CACHE_HIT
    assert cache.ohlcv_path("BTC-HIST", "1d").read_bytes() == data
    assert len(read_records("BTC-HIST", "1d")) == 1


def test_changed_layout_yields_changed_and_empty_cache_dir(fpass, db):
    # baseline learned from the old layout in a throwaway cache, then an empty cache dir is used
    _run(FakeFetcher(), fpass, db, accept_baseline=True)
    for p in sorted((cache.CACHE_ROOT / "ohlcv").rglob("*"), reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    r = _run(FakeFetcher("changed.html"), fpass, db)
    assert r.status == status.CHANGED
    assert _cache_files() == []


def test_invalid_data_writes_nothing(fpass, db):
    r = _run(FakeFetcher("bad_range.html"), fpass, db, accept_baseline=True)
    assert r.status == status.INVALID
    assert _cache_files() == [] and not db.exists()


def test_no_table_is_invalid(fpass, db):
    assert _run(FakeFetcher("no_table.html"), fpass, db, accept_baseline=True).status == status.INVALID


def test_fetch_failure_status_passes_through(fpass, db):
    assert _run(FakeFetcher(st=status.TIMEOUT), fpass, db).status == status.TIMEOUT
    assert _cache_files() == []


def test_non_empty_key_refused_unless_replace(fpass, db):
    _run(FakeFetcher(), fpass, db, accept_baseline=True)
    r = _run(FakeFetcher("ok_v2.html"), fpass, db)
    assert r.status == status.REFUSED
    assert cache.read_ohlcv("BTC-HIST", "1d")["close"].iloc[-1] == 111
    r = _run(FakeFetcher("ok_v2.html"), fpass, db, replace=True)
    assert r.status == status.OK
    assert cache.read_ohlcv("BTC-HIST", "1d")["close"].iloc[-1] == 113
    assert len(read_records("BTC-HIST", "1d")) == 2


def test_url_outside_pass_refused_before_fetch(fpass, db):
    f = FakeFetcher()
    r = _run(f, fpass, db, url="https://other.example.test/data/prices")
    assert r.status == status.REFUSED and f.calls == 0


def test_statuses_are_in_closed_set(fpass, db):
    assert status.is_status(_run(FakeFetcher(), fpass, db).status)
