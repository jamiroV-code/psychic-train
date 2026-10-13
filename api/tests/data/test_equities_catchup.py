"""T51: start-up catch-up when the cached bar for the due session is a
still-forming bar (fetched before that session's bar was due). Fake clock,
injected bar dates and fetch times; no network, no key."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from api.data import equities_calendar, equities_refresh, lse_adapter
from api.data.equities_refresh import EquitiesRefreshWorker

TUE_NOON = pd.Timestamp("2026-10-13T12:00:00Z")
MON = date(2026, 10, 12)
MON_DUE = pd.Timestamp("2026-10-12T21:00:00Z")  # 20:00Z close + 60 min


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, monkeypatch):
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    equities_refresh.stop_worker()
    yield
    equities_refresh.stop_worker()


class Clock:
    def __init__(self, now):
        self.now = pd.Timestamp(now)

    def __call__(self):
        return self.now


class Feed:
    def __init__(self, fetched, final_on_fetch=True):
        self.fetched = dict(fetched)
        self.final_on_fetch = final_on_fetch
        self.clock = None
        self.calls = []

    def tickers(self):
        return list(self.fetched)

    def bar_date(self, ticker, now):
        return MON

    def fetched_at(self, ticker, now):
        return self.fetched.get(ticker)

    def fetch(self, ticker):
        self.calls.append(ticker)
        if self.final_on_fetch:
            self.fetched[ticker] = self.clock()
        return SimpleNamespace(symbol=ticker, status="ok")


def _worker(clock, feed):
    feed.clock = clock
    return EquitiesRefreshWorker(
        clock=clock, fetch=feed.fetch, tickers=feed.tickers,
        bar_date=feed.bar_date, fetched_at=feed.fetched_at,
    )


def test_bar_due_at_public_helper():
    assert equities_calendar.bar_due_at(MON) == MON_DUE


def test_forming_bar_from_missed_close_catches_up():
    clock = Clock(TUE_NOON)
    feed = Feed({"AAA": pd.Timestamp("2026-10-12T18:00:00Z")})
    worker = _worker(clock, feed)
    assert worker.schedule_first() == TUE_NOON + pd.Timedelta(seconds=20)
    assert worker.tick_session == MON
    clock.now = worker.next_tick_at
    worker.run_tick()
    assert feed.calls == ["AAA"]
    assert worker.retries == 0
    assert worker.next_tick_at == pd.Timestamp("2026-10-13T20:30:00Z")


def test_final_bar_is_not_behind():
    clock = Clock(TUE_NOON)
    feed = Feed({"AAA": MON_DUE + pd.Timedelta(minutes=5)})
    worker = _worker(clock, feed)
    assert worker.schedule_first() == pd.Timestamp("2026-10-13T20:30:00Z")


def test_no_sidecar_is_behind():
    clock = Clock(TUE_NOON)
    feed = Feed({"AAA": None})
    worker = _worker(clock, feed)
    assert worker.schedule_first() == TUE_NOON + pd.Timedelta(seconds=20)
    assert lse_adapter.cached_fetched_at("NOPE", "1d") is None


def test_unreadable_fetch_time_is_behind():
    clock = Clock(TUE_NOON)

    def boom(ticker, now):
        raise RuntimeError("x")

    worker = EquitiesRefreshWorker(
        clock=clock, tickers=lambda: ["AAA"], bar_date=lambda t, n: MON, fetched_at=boom
    )
    assert worker.schedule_first() == TUE_NOON + pd.Timedelta(seconds=20)


def test_tick_that_fetched_only_forming_bar_retries():
    # Monday's tick ran before the bar was due: the fetch got a forming bar.
    clock = Clock(pd.Timestamp("2026-10-12T20:30:00Z"))
    feed = Feed({"AAA": pd.Timestamp("2026-10-12T19:00:00Z")})
    worker = _worker(clock, feed)
    worker.tick_session = MON
    worker.next_tick_at = clock.now
    worker.run_tick()
    assert worker.retries == 1
    assert worker.next_tick_at == clock.now + pd.Timedelta(seconds=1800)
    assert worker.tick_session == MON
    # After the bar is due, a retry fetches the final bar and stops retrying.
    clock.now = worker.next_tick_at + pd.Timedelta(minutes=30)
    worker.run_tick()
    assert worker.retries == 0
    assert worker.next_tick_at == pd.Timestamp("2026-10-13T20:30:00Z")


def test_retries_capped_at_three():
    clock = Clock(pd.Timestamp("2026-10-12T20:30:00Z"))
    feed = Feed({"AAA": pd.Timestamp("2026-10-12T19:00:00Z")}, final_on_fetch=False)
    worker = _worker(clock, feed)
    worker.tick_session = MON
    for expected in (1, 2, 3):
        worker.run_tick()
        assert worker.retries == expected
        clock.now = worker.next_tick_at
    worker.run_tick()
    assert worker.retries == 0
    assert worker.next_tick_at == pd.Timestamp("2026-10-13T20:30:00Z")
