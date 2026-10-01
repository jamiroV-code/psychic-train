"""refresh_cache.py exit-code policy, per-item isolation and D7 universe fan-out.

SAFETY (T22): `_isolate` below is module-level `autouse=True`. It depends on
`isolated_cache` (redirects `cache.CACHE_ROOT`) AND redirects
`watchlist_store.DEFAULT_WATCHLIST_PATH`, so every test in this file — not
just the ones that name a fixture — is structurally unable to touch the
developer's real `api/data/cache/**` or `api/data/watchlist.json`.
`write_ohlcv` replaces whole series, so a miss here would destroy real data.
All fetchers are stubbed; nothing here reaches the network.
"""
from __future__ import annotations

import pytest

from api.data import cache, watchlist as watchlist_store
from api.data.pairs_universe import UniverseFileError
from api.scripts import refresh_cache


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    return isolated_cache


def test_isolated_cache_redirects_cache_root(tmp_path):
    """Canary: the autouse isolation is really in effect inside a test."""
    assert cache.CACHE_ROOT == tmp_path
    assert watchlist_store.DEFAULT_WATCHLIST_PATH == tmp_path / "watchlist.json"


class _Result:
    def __init__(self, status="ok", bars=500, insufficient_history=False):
        self.status = status
        self.df = list(range(bars))
        self.insufficient_history = insufficient_history


def _summary(symbol="BTC", timeframe="1d", **kw):
    return refresh_cache._summary(symbol, timeframe, _Result(**kw))


def _error(symbol="BTC", timeframe="1d"):
    return refresh_cache.FetchSummary(symbol, timeframe, ok=False, status="error")


# ---------------------------------------------------------------- exit_code

def test_exit_code_zero_when_any_fetch_ok():
    assert refresh_cache.exit_code([_summary(), _summary(status="unavailable")]) == 0


def test_exit_code_two_when_every_fetch_is_unavailable_or_insufficient():
    """AC-5: ran, nothing qualified -> warn, do not fail."""
    summaries = [_summary(status="unavailable", bars=0), _summary(status="stale")]
    assert refresh_cache.exit_code(summaries) == 2


def test_exit_code_two_when_only_fetch_is_insufficient_history():
    """E4: `insufficient_history` is not a usable fetch, so it is not `ok`."""
    s = _summary(status="ok", insufficient_history=True)
    assert s.ok is False
    assert refresh_cache.exit_code([s]) == 2


def test_exit_code_two_for_empty_summary_list():
    assert refresh_cache.exit_code([]) == 2


def test_exit_code_one_when_every_item_errors():
    """C3: total failure is a crash-class outcome, not a degraded one."""
    assert refresh_cache.exit_code([_error("BTC"), _error("HYPE")]) == 1


def test_exit_code_zero_when_one_errors_and_others_are_ok():
    assert refresh_cache.exit_code([_error("BTC"), _summary("HYPE")]) == 0


# ------------------------------------------------------------- run / main

def _stub_fetch(monkeypatch, calls, result_for=lambda s, tf: _Result()):
    def fake(symbol, timeframe, *a, **k):
        calls.append((symbol, timeframe))
        return result_for(symbol, timeframe)
    monkeypatch.setattr(refresh_cache.ccxt_adapter, "fetch_ohlcv", fake)
    return calls


def test_main_fetches_watchlist_all_timeframes_and_universe_daily_only(monkeypatch, capsys):
    """D7: universe-only coins get `1d` only; watchlist/benchmark coins keep all five."""
    monkeypatch.setattr(refresh_cache, "load_universe", lambda: ["BTC", "XRP", "DOGE"])
    calls: list[tuple[str, str]] = []
    _stub_fetch(monkeypatch, calls)

    assert refresh_cache.main() == 0

    by_symbol: dict[str, set[str]] = {}
    for symbol, tf in calls:
        by_symbol.setdefault(symbol, set()).add(tf)
    assert by_symbol["BTC"] == set(refresh_cache.TIMEFRAMES)
    assert by_symbol["HYPE"] == set(refresh_cache.TIMEFRAMES)
    assert by_symbol["XRP"] == {"1d"}
    assert by_symbol["DOGE"] == {"1d"}
    assert len(calls) == len(refresh_cache.TIMEFRAMES) * 2 + 2

    out = capsys.readouterr().out
    assert "XRP" in out and "insufficient_history=False" in out


def test_universe_coin_already_in_watchlist_is_not_double_fetched(monkeypatch, tmp_path):
    """E3: BTC is both a benchmark and a universe member — fetched once per timeframe."""
    watchlist_store.add_coin("XRP")
    monkeypatch.setattr(refresh_cache, "load_universe", lambda: ["BTC", "XRP"])
    calls: list[tuple[str, str]] = []
    _stub_fetch(monkeypatch, calls)

    refresh_cache.main()

    assert len(calls) == len(set(calls))
    assert sorted(tf for s, tf in calls if s == "XRP") == sorted(refresh_cache.TIMEFRAMES)


def test_empty_universe_fetches_base_symbols_only(monkeypatch):
    """E3: an empty universe is not an error, it just adds no work."""
    monkeypatch.setattr(refresh_cache, "load_universe", lambda: [])
    calls: list[tuple[str, str]] = []
    _stub_fetch(monkeypatch, calls)

    assert refresh_cache.main() == 0
    assert {s for s, _ in calls} == {"BTC", "HYPE"}


def test_bad_universe_file_is_recorded_and_base_symbols_still_fetched(monkeypatch, capsys):
    def boom():
        raise UniverseFileError("universe file not found: /nope.json")
    monkeypatch.setattr(refresh_cache, "load_universe", boom)
    calls: list[tuple[str, str]] = []
    _stub_fetch(monkeypatch, calls)

    assert refresh_cache.main() == 0  # base fetches still ok
    assert {s for s, _ in calls} == {"BTC", "HYPE"}
    summaries = refresh_cache.run_refresh()
    assert any(s.symbol == "universe" and s.status == "error" for s in summaries)
    assert "universe unavailable" in capsys.readouterr().err


def test_main_returns_two_when_every_fetch_is_unavailable(monkeypatch):
    monkeypatch.setattr(refresh_cache, "load_universe", lambda: [])
    _stub_fetch(monkeypatch, [], lambda s, tf: _Result(status="unavailable", bars=0))
    assert refresh_cache.main() == 2


def test_main_returns_one_when_every_fetch_raises(monkeypatch, capsys):
    """C3: every item raised -> exit 1, the workflow fails the job."""
    monkeypatch.setattr(refresh_cache, "load_universe", lambda: [])

    def boom(*a, **k):
        raise RuntimeError("exchange down")
    monkeypatch.setattr(refresh_cache.ccxt_adapter, "fetch_ohlcv", boom)

    assert refresh_cache.main() == 1
    assert "exchange down" in capsys.readouterr().err


def test_main_returns_zero_when_one_fetch_raises_and_others_succeed(monkeypatch):
    monkeypatch.setattr(refresh_cache, "load_universe", lambda: [])

    def flaky(symbol, timeframe, *a, **k):
        if (symbol, timeframe) == ("BTC", "1d"):
            raise RuntimeError("one bad fetch")
        return _Result()
    monkeypatch.setattr(refresh_cache.ccxt_adapter, "fetch_ohlcv", flaky)

    assert refresh_cache.main() == 0


def test_main_with_no_args_does_not_consume_pytest_argv(monkeypatch):
    """C5: `main()` must not parse pytest's own sys.argv."""
    monkeypatch.setattr(refresh_cache, "load_universe", lambda: [])
    _stub_fetch(monkeypatch, [])
    assert refresh_cache.main() == 0
    assert refresh_cache.main([]) == 0


def test_refresh_all_wrapper_returns_summaries(monkeypatch):
    monkeypatch.setattr(refresh_cache, "load_universe", lambda: [])
    _stub_fetch(monkeypatch, [])
    summaries = refresh_cache.refresh_all()
    assert summaries and all(isinstance(s, refresh_cache.FetchSummary) for s in summaries)


def test_spacing_sleeps_between_items_when_configured(monkeypatch):
    monkeypatch.setattr(refresh_cache, "load_universe", lambda: [])
    _stub_fetch(monkeypatch, [])
    slept: list[float] = []
    summaries = refresh_cache.run_refresh(sleep=slept.append, spacing=1.5)
    assert slept == [1.5] * len(summaries)


def test_default_spacing_never_sleeps(monkeypatch):
    monkeypatch.setattr(refresh_cache, "load_universe", lambda: [])
    _stub_fetch(monkeypatch, [])

    def fail(_):
        raise AssertionError("default spacing must not sleep")
    refresh_cache.run_refresh(sleep=fail)
