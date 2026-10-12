"""S9E: the equities market-hours worker. Fake clock, injected fetch and
bar dates; the threaded tests wait on Events, never on the real clock. No
real network or key."""
from __future__ import annotations

import json
import logging
import threading
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from api.data import equities_refresh, equities_store, lse_adapter
from api.data.equities_refresh import EquitiesRefreshWorker
from api.tests import equities_fixtures as fx

# Tuesday 13 Oct 2026, before the close (daylight time: close 20:00Z).
TUE_NOON = pd.Timestamp("2026-10-13T12:00:00Z")
STATUS_KEYS = {
    "running",
    "disabled_reason",
    "interval_seconds",
    "last_tick_started",
    "last_tick_finished",
    "last_tick_ok",
    "last_tick_failed",
    "next_tick_at",
    "queue_depth",
    "backoff_seconds",
    "server_time",
    "last_bar_date",
}


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(tmp_path / "equities.json"))
    monkeypatch.setenv("SCREENER_LAYOUT_PATH", str(tmp_path / "layout.json"))
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    equities_refresh.stop_worker()
    yield
    equities_refresh.stop_worker()
    assert equities_refresh.wait_until_idle(5.0)


class Clock:
    def __init__(self, now):
        self.now = pd.Timestamp(now)

    def __call__(self):
        return self.now


class Feed:
    """Bar dates per ticker; a fetch moves a ticker to `to`, or raises."""

    def __init__(self, bars, to=None, fail=()):
        self.bars = dict(bars)
        self.to = to
        self.fail = set(fail)
        self.calls = []

    def tickers(self):
        return list(self.bars)

    def bar_date(self, ticker, now):
        return self.bars.get(ticker)

    def fetch(self, ticker):
        self.calls.append(ticker)
        if ticker in self.fail:
            raise RuntimeError("boom")
        if self.to is not None:
            self.bars[ticker] = self.to
        return SimpleNamespace(symbol=ticker, status="ok")


def _worker(clock, feed, **kwargs):
    return EquitiesRefreshWorker(
        clock=clock, fetch=feed.fetch, tickers=feed.tickers, bar_date=feed.bar_date, **kwargs
    )


def test_first_tick_catch_up_after_20s():
    clock = Clock(TUE_NOON)
    feed = Feed({"AAA": date(2026, 10, 12), "BBB": date(2026, 10, 9)}, to=date(2026, 10, 12))
    worker = _worker(clock, feed)
    assert worker.schedule_first() == TUE_NOON + pd.Timedelta(seconds=20)
    assert worker.tick_session == date(2026, 10, 12)
    clock.now = worker.next_tick_at
    worker.run_tick()
    assert feed.calls == ["AAA", "BBB"]
    # Caught up: the next tick is Tuesday's close + 30 min.
    assert worker.next_tick_at == pd.Timestamp("2026-10-13T20:30:00Z")
    assert worker.retries == 0


def test_no_catch_up_when_current():
    feed = Feed({"AAA": date(2026, 10, 12)})
    worker = _worker(Clock(TUE_NOON), feed)
    assert worker.schedule_first() == pd.Timestamp("2026-10-13T20:30:00Z")
    assert worker.tick_session == date(2026, 10, 13)
    assert feed.calls == []


def test_tick_lands_at_close_plus_30():
    clock = Clock(TUE_NOON)
    feed = Feed({"AAA": date(2026, 10, 12)}, to=date(2026, 10, 13))
    worker = _worker(clock, feed)
    worker.schedule_first()
    assert worker.next_tick_at == pd.Timestamp("2026-10-13T20:30:00Z")
    clock.now = worker.next_tick_at
    assert worker.run_tick() == {"ok": 1, "failed": 0}
    assert worker.last_tick_started == pd.Timestamp("2026-10-13T20:30:00Z")
    assert worker.next_tick_at == pd.Timestamp("2026-10-14T20:30:00Z")
    # Winter time: the 16:00 Eastern close is 21:00Z, so the tick is 21:30Z.
    winter = _worker(Clock("2026-11-10T12:00:00Z"), Feed({"AAA": date(2026, 11, 9)}))
    assert winter.schedule_first() == pd.Timestamp("2026-11-10T21:30:00Z")


def test_retry_three_times_every_30_min():
    clock = Clock("2026-10-13T20:30:00Z")
    feed = Feed({"AAA": date(2026, 10, 13), "BBB": date(2026, 10, 12)})
    worker = _worker(clock, feed)
    worker.next_tick_at, worker.tick_session = clock.now, date(2026, 10, 13)
    for n in range(1, 4):
        worker.run_tick()
        assert worker.retries == n
        assert worker.next_tick_at == clock.now + pd.Timedelta(minutes=30)
        assert worker.tick_session == date(2026, 10, 13)
        clock.now = worker.next_tick_at
    worker.run_tick()
    # Three retries spent: wait for the next close.
    assert worker.retries == 0
    assert worker.next_tick_at == pd.Timestamp("2026-10-14T20:30:00Z")
    assert len(feed.calls) == 8


def test_weekend_and_holiday_skipped():
    friday_evening = Clock("2026-10-09T21:00:00Z")
    worker = _worker(friday_evening, Feed({"AAA": date(2026, 10, 9)}))
    assert worker.schedule_first() == pd.Timestamp("2026-10-12T20:30:00Z")
    saturday = Clock("2026-10-10T12:00:00Z")
    worker = _worker(saturday, Feed({"AAA": date(2026, 10, 9)}))
    assert worker.schedule_first() == pd.Timestamp("2026-10-12T20:30:00Z")
    # Thanksgiving (Thu 26 Nov) has no session: Wednesday's tick waits for Friday.
    clock = Clock("2026-11-25T21:30:00Z")
    feed = Feed({"AAA": date(2026, 11, 24)}, to=date(2026, 11, 25))
    worker = _worker(clock, feed)
    worker.next_tick_at, worker.tick_session = clock.now, date(2026, 11, 25)
    worker.run_tick()
    assert worker.next_tick_at == pd.Timestamp("2026-11-27T21:30:00Z")


def test_per_ticker_isolation():
    clock = Clock("2026-10-13T20:30:00Z")
    feed = Feed(
        {"AAA": date(2026, 10, 12), "BBB": date(2026, 10, 12), "CCC": date(2026, 10, 12)},
        to=date(2026, 10, 13),
        fail={"BBB"},
    )
    worker = _worker(clock, feed)
    worker.next_tick_at, worker.tick_session = clock.now, date(2026, 10, 13)
    assert worker.run_tick() == {"ok": 2, "failed": 1}
    assert feed.calls == ["AAA", "BBB", "CCC"]
    assert worker.last_tick_ok == 2 and worker.last_tick_failed == 1
    assert feed.bars["CCC"] == date(2026, 10, 13)
    # Only BBB is behind: a retry follows.
    assert worker.retries == 1


def test_all_failed_backs_off():
    clock = Clock("2026-10-13T20:30:00Z")
    feed = Feed({"AAA": date(2026, 10, 12)}, fail={"AAA"})
    worker = _worker(clock, feed)
    worker.next_tick_at, worker.tick_session = clock.now, date(2026, 10, 13)
    worker.run_tick()
    assert worker.backoff_seconds == 3600.0
    assert worker.next_tick_at == clock.now + pd.Timedelta(seconds=3600)
    clock.now = worker.next_tick_at
    worker.run_tick()
    assert worker.backoff_seconds == 3600.0  # capped
    feed.fail.clear()
    feed.to = date(2026, 10, 13)
    clock.now = worker.next_tick_at
    worker.run_tick()
    assert worker.backoff_seconds == 0.0
    assert worker.next_tick_at == pd.Timestamp("2026-10-14T20:30:00Z")


def test_missing_key_does_not_start():
    assert equities_refresh.start_from_env(env={}) is None
    assert equities_refresh.current_worker() is None
    body = equities_refresh.status(now=TUE_NOON)
    assert body["running"] is False and body["disabled_reason"] == "missing-key"


def test_env_zero_keeps_it_off(monkeypatch):
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)
    env = {"SCREENER_REFRESH_WORKER": "0", "LSE_API_KEY": fx.SYNTHETIC_CREDENTIAL}
    assert equities_refresh.start_from_env(env=env) is None
    assert equities_refresh.current_worker() is None
    body = equities_refresh.status(now=TUE_NOON)
    assert body["running"] is False
    assert body["disabled_reason"] == "SCREENER_REFRESH_WORKER=0"


def test_stop_joins_thread():
    feed = Feed({"AAA": date(2026, 10, 12)})
    worker = _worker(Clock(TUE_NOON), feed)
    worker.start()
    assert worker.running
    worker.stop()
    assert not worker.running and not worker._thread.is_alive()
    worker.stop()  # idempotent
    assert feed.calls == []


def test_request_now_wakes():
    fetched = threading.Event()
    feed = Feed({"AAA": date(2026, 10, 12)})
    inner = feed.fetch

    def fetch(ticker):
        result = inner(ticker)
        fetched.set()
        return result

    worker = EquitiesRefreshWorker(
        clock=Clock(TUE_NOON), fetch=fetch, tickers=feed.tickers, bar_date=feed.bar_date
    )
    worker.start()
    try:
        assert worker.request_now() is True
        assert fetched.wait(5.0)
    finally:
        worker.stop()
    assert feed.calls == ["AAA"]
    # A woken pass leaves the schedule alone.
    assert worker.next_tick_at == pd.Timestamp("2026-10-13T20:30:00Z")


def test_status_keys(monkeypatch):
    feed = Feed({"AAA": date(2026, 10, 12)})
    env = {"LSE_API_KEY": fx.SYNTHETIC_CREDENTIAL}
    worker = equities_refresh.start_from_env(
        env=env, clock=Clock(TUE_NOON), fetch=feed.fetch, tickers=feed.tickers, bar_date=feed.bar_date
    )
    assert worker is not None and equities_refresh.current_worker() is worker
    deadline = threading.Event()
    for _ in range(100):
        if worker.next_tick_at is not None:
            break
        deadline.wait(0.01)
    body = equities_refresh.status()
    assert set(body) == STATUS_KEYS
    assert body["running"] is True and body["disabled_reason"] is None
    assert body["interval_seconds"] == 86400
    assert body["next_tick_at"] == "2026-10-13T20:30:00Z"
    assert body["server_time"] == "2026-10-13T12:00:00Z"
    assert body["last_tick_finished"] is None
    equities_refresh.stop_worker()
    assert equities_refresh.status(now=TUE_NOON)["running"] is False


def test_last_bar_date_in_status():
    equities_store.add_ticker("AAPL")
    equities_store.add_ticker("MSFT")
    fx.seed("AAPL", date(2026, 10, 9), 80)
    fx.seed("MSFT", date(2026, 10, 12), 80)
    worker = EquitiesRefreshWorker(clock=Clock(TUE_NOON), fetch=lambda t: None)
    # The default bar dates read the cache: MSFT is current, AAPL is behind.
    assert worker.schedule_first() == TUE_NOON + pd.Timedelta(seconds=20)
    assert equities_refresh.status(now=TUE_NOON)["last_bar_date"] == "2026-10-12"


def test_no_key_in_logs(caplog, monkeypatch):
    monkeypatch.setenv("LSE_API_KEY", fx.SYNTHETIC_CREDENTIAL)
    clock = Clock("2026-10-13T20:30:00Z")

    def leaky(ticker):
        raise RuntimeError(f"GET {lse_adapter.BASE_URL}?k={fx.SYNTHETIC_CREDENTIAL}")

    def leaky_bar(ticker, now):
        raise ValueError(fx.SYNTHETIC_CREDENTIAL)

    worker = EquitiesRefreshWorker(clock=clock, fetch=leaky, tickers=lambda: ["AAA"], bar_date=leaky_bar)
    worker.next_tick_at, worker.tick_session = clock.now, date(2026, 10, 13)
    with caplog.at_level(logging.DEBUG):
        worker.run_tick()
    assert "RuntimeError" in caplog.text and "ValueError" in caplog.text
    assert fx.SYNTHETIC_CREDENTIAL not in caplog.text
    assert lse_adapter.BASE_URL not in caplog.text
    assert fx.SYNTHETIC_CREDENTIAL not in json.dumps(equities_refresh.status(now=clock.now))
