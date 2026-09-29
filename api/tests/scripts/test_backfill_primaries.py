"""backfill_primaries.py exit-code policy, per-series isolation, no-op determinism.

SAFETY (T22): `_isolate` is module-level `autouse=True`, depends on
`isolated_cache` and redirects `watchlist_store.DEFAULT_WATCHLIST_PATH`, so
no test here can reach the real `api/data/cache/**` or the developer's real
`api/data/watchlist.json`. FRED is stubbed; nothing reaches the network.
"""
from __future__ import annotations

import hashlib

import pandas as pd
import pytest

from api.data import cache, watchlist as watchlist_store
from api.scripts import backfill_primaries


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    return isolated_cache


def test_isolated_cache_redirects_cache_root(tmp_path):
    """Canary: the autouse isolation is really in effect inside a test."""
    assert cache.CACHE_ROOT == tmp_path
    assert watchlist_store.DEFAULT_WATCHLIST_PATH == tmp_path / "watchlist.json"


def _frame(n=3):
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"][:n]),
        "value": [1.0, 2.0, 3.0][:n],
    })


class _Result:
    def __init__(self, series_id="WALCL", status="ok", df=None):
        self.series_id = series_id
        self.status = status
        self.df = _frame() if df is None else df


def _summary(status="ok", label="walcl"):
    return backfill_primaries.SeriesSummary(label, "WALCL", ok=status == "ok", status=status)


def _error(label="walcl"):
    return backfill_primaries.SeriesSummary(label, "WALCL", ok=False, status="error")


# ---------------------------------------------------------------- exit_code

def test_exit_code_zero_when_any_series_ok():
    assert backfill_primaries.exit_code([_summary("ok"), _summary("unavailable")]) == 0


def test_exit_code_two_when_no_series_is_ok():
    """AC-5: `stale` and `unavailable` do NOT count as ok."""
    summaries = [_summary("stale"), _summary("unavailable")]
    assert backfill_primaries.exit_code(summaries) == 2


def test_exit_code_two_for_empty_summary_list():
    assert backfill_primaries.exit_code([]) == 2


def test_exit_code_one_when_every_series_errors():
    assert backfill_primaries.exit_code([_error("a"), _error("b")]) == 1


def test_exit_code_zero_when_one_errors_and_others_are_ok():
    assert backfill_primaries.exit_code([_error("a"), _summary("ok", "b")]) == 0


# ------------------------------------------------------------- run / main

def _stub(monkeypatch, fn):
    monkeypatch.setattr(backfill_primaries.fred_adapter, "fetch_series", fn)


def test_main_prints_one_line_per_series_and_returns_zero(monkeypatch, capsys):
    seen: list[str] = []

    def fake(series_id, *a, **k):
        seen.append(series_id)
        return _Result(series_id)
    _stub(monkeypatch, fake)

    assert backfill_primaries.main() == 0
    assert seen == list(backfill_primaries.PRIMARY_SERIES.values())
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == len(backfill_primaries.PRIMARY_SERIES)
    assert "status=ok" in out[0] and "first=2026-01-01" in out[0] and "last=2026-01-03" in out[0]


def test_main_returns_two_when_every_series_is_stale(monkeypatch):
    _stub(monkeypatch, lambda sid, *a, **k: _Result(sid, "stale"))
    assert backfill_primaries.main() == 2


def test_main_returns_two_when_every_series_is_unavailable(monkeypatch):
    _stub(monkeypatch, lambda sid, *a, **k: _Result(sid, "unavailable", pd.DataFrame(
        {"date": pd.to_datetime([]), "value": []})))
    assert backfill_primaries.main() == 2


def test_main_returns_one_when_every_series_raises(monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("fred down")
    _stub(monkeypatch, boom)
    assert backfill_primaries.main() == 1
    assert "fred down" in capsys.readouterr().err


def test_main_returns_zero_when_one_series_raises_and_others_succeed(monkeypatch):
    def flaky(series_id, *a, **k):
        if series_id == backfill_primaries.PRIMARY_SERIES["tga"]:
            raise RuntimeError("one bad series")
        return _Result(series_id)
    _stub(monkeypatch, flaky)
    assert backfill_primaries.main() == 0


def test_main_with_no_args_does_not_consume_pytest_argv(monkeypatch):
    """C5: `main()` must not parse pytest's own sys.argv."""
    _stub(monkeypatch, lambda sid, *a, **k: _Result(sid))
    assert backfill_primaries.main() == 0
    assert backfill_primaries.main([]) == 0


def test_backfill_all_wrapper_returns_summaries(monkeypatch):
    _stub(monkeypatch, lambda sid, *a, **k: _Result(sid))
    summaries = backfill_primaries.backfill_all()
    assert len(summaries) == len(backfill_primaries.PRIMARY_SERIES)
    assert all(isinstance(s, backfill_primaries.SeriesSummary) for s in summaries)


def test_empty_frame_reports_na_coverage():
    empty = pd.DataFrame({"date": pd.to_datetime([]), "value": []})
    assert backfill_primaries._coverage(empty) == ("n/a", "n/a")


def test_spacing_sleeps_between_series_when_configured(monkeypatch):
    _stub(monkeypatch, lambda sid, *a, **k: _Result(sid))
    slept: list[float] = []
    backfill_primaries.run_backfill(sleep=slept.append, spacing=0.5)
    assert slept == [0.5] * len(backfill_primaries.PRIMARY_SERIES)


# ------------------------------------------------------------------ AC-11b

def test_rewriting_the_same_series_is_byte_identical():
    """AC-11b: a quiet night produces no diff for the liquidity cache."""
    df = _frame()
    cache.write_liquidity_series("WALCL", df)
    path = cache.liquidity_series_path("WALCL")
    first = hashlib.sha256(path.read_bytes()).hexdigest()
    cache.write_liquidity_series("WALCL", df.copy())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == first
