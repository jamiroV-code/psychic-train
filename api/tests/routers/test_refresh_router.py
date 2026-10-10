"""T35 / S8: GET /api/refresh/status and POST /api/refresh/now.

No lifespan here (plain `TestClient(app)`): each test installs its own
worker in the registry, and nothing reaches the network.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.data import ccxt_adapter, refresh_worker
from api.data.refresh_worker import RefreshWorker
from api.main import app

NOW = pd.Timestamp("2026-10-04T12:07:00Z")
ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
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
}


class Result:
    def __init__(self, status):
        self.status = status


@pytest.fixture(autouse=True)
def _clean_registry():
    refresh_worker.stop_worker()
    yield
    refresh_worker.stop_worker()
    ccxt_adapter.set_refresh_hook(None)


def _worker(fetch, **kwargs) -> RefreshWorker:
    return RefreshWorker(
        clock=lambda: NOW,
        fetch=fetch,
        symbols=lambda: ["ETH"],
        retry_markets=lambda: False,
        is_fresh=lambda *a: False,
        first_delay_seconds=3600,
        **kwargs,
    )


def test_status_endpoint_shape_and_counts():
    def fetch(symbol, timeframe, exchange=None):
        return Result("unavailable" if (symbol, timeframe) == ("ETH", "4h") else "ok")

    worker = _worker(fetch, interval_seconds=900)
    worker.run_tick()  # synchronous: 12 planned pairs, one unavailable
    refresh_worker.install_worker(worker)
    worker.request_refresh("SOL", "1h")
    worker._run_mutex.acquire()  # keep the queued pair visible
    try:
        body = TestClient(app).get("/api/refresh/status").json()
    finally:
        worker._run_mutex.release()

    assert set(body) == STATUS_KEYS
    assert body["running"] is True and body["disabled_reason"] is None
    assert body["interval_seconds"] == 900
    assert body["last_tick_ok"] == 11 and body["last_tick_failed"] == 1
    for key in ("last_tick_started", "last_tick_finished", "next_tick_at"):
        assert ISO_Z.match(body[key]), (key, body[key])
    assert body["queue_depth"] == 1
    assert body["backoff_seconds"] == 0

    refresh_worker.stop_worker()
    after = TestClient(app).get("/api/refresh/status").json()
    assert set(after) == STATUS_KEYS
    assert after["running"] is False and after["disabled_reason"] == "stopped"


def test_refresh_now_returns_202_queues_one_pending_run_without_fetching():
    fetched: list = []
    worker = _worker(lambda s, tf, exchange=None: fetched.append((s, tf)) or Result("ok"))
    refresh_worker.install_worker(worker)
    client = TestClient(app)

    # Holding the run mutex: the woken loop cannot start the run yet, so any
    # fetch observed here would have come from the request itself.
    worker._run_mutex.acquire()
    try:
        first = client.post("/api/refresh/now")
        second = client.post("/api/refresh/now")
        assert first.status_code == 202 and second.status_code == 202
        assert first.json() == {"accepted": True, "already_pending": False}
        assert second.json() == {"accepted": True, "already_pending": True}
        assert fetched == []
        assert worker._now_requested is True
    finally:
        worker._run_mutex.release()

    refresh_worker.stop_worker()
    assert worker.ticks <= 1  # the two requests made at most one run


def test_refresh_now_returns_503_worker_not_running_when_off():
    assert refresh_worker.start_from_env({"SCREENER_REFRESH_WORKER": "0"}) is None
    client = TestClient(app)

    response = client.post("/api/refresh/now")
    assert response.status_code == 503
    assert response.json() == {"detail": "worker-not-running"}

    body = client.get("/api/refresh/status").json()
    assert body["running"] is False
    assert body["disabled_reason"] == "SCREENER_REFRESH_WORKER=0"



def test_status_server_time_is_iso_z_and_equals_the_worker_clock():
    refresh_worker.install_worker(_worker(lambda s, tf, exchange=None: Result("ok")))

    body = TestClient(app).get("/api/refresh/status").json()

    assert ISO_Z.match(body["server_time"]), body["server_time"]
    assert body["server_time"] == "2026-10-04T12:07:00Z"


def test_status_server_time_without_worker_uses_adapter_clock_and_is_none_when_it_raises(monkeypatch):
    monkeypatch.setattr(ccxt_adapter, "_now", lambda: pd.Timestamp("2026-10-05T08:30:15Z"))
    body = TestClient(app).get("/api/refresh/status").json()
    assert body["server_time"] == "2026-10-05T08:30:15Z"

    def broken():
        raise RuntimeError("clock unavailable")

    monkeypatch.setattr(ccxt_adapter, "_now", broken)
    body = TestClient(app).get("/api/refresh/status").json()
    assert set(body) == STATUS_KEYS
    assert body["server_time"] is None
    assert body["running"] is False and body["queue_depth"] == 0


_TS_PATH = Path(__file__).resolve().parents[3] / "web" / "lib" / "types" / "refresh.ts"
NULLABLE = {"disabled_reason", "last_tick_started", "last_tick_finished", "next_tick_at", "server_time"}


def _ts_interface(source: str, name: str) -> dict[str, str]:
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.S)
    assert match, f"interface {name} not found in {_TS_PATH}"
    return dict(re.findall(r"^\s*(\w+\??):\s*([^;]+);", match.group(1), re.M))


def test_refresh_status_ts_interface_matches_status_keys_and_nullability():
    fields = _ts_interface(_TS_PATH.read_text(), "RefreshStatus")

    assert set(fields) == STATUS_KEYS == set(refresh_worker.status())
    assert {k for k, v in fields.items() if "null" in v} == NULLABLE
