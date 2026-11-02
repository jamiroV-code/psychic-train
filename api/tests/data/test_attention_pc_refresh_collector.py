"""Standalone collector (A, B): `python -m api.data.attention_collector` runs the same worker as the API lifespan,
writes the shared heartbeat in both modes and refuses to start beside another live collector.

Fakes only (the W8e worker fakes: fake clock, fake X reader, `httpx.MockTransport` Reddit); socket connects off
the loopback are refused; every test leaves no worker, heartbeat or collector thread behind."""
from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.data import attention_collector as ac
from api.data import attention_pc_refresh as apr
from api.data.attention import collector_heartbeat as hb
from api.tests.data.test_attention_pc_refresh import T0, Clock, fakes

REPO = Path(__file__).resolve().parents[3]
OTHER_PID = 424242
FLAG_ON = {apr.FLAG_ENV: "1"}


@pytest.fixture(autouse=True)
def _isolated(isolated_cache, monkeypatch):
    real_connect = socket.socket.connect

    def refuse(self, address, *a, **k):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return real_connect(self, address, *a, **k)
        raise OSError("network blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    yield isolated_cache
    apr.stop_worker()
    assert _threads() == []


def _threads():
    return [t.name for t in threading.enumerate()
            if t.is_alive() and (t.name.startswith("attention-pc") or t.name == hb.THREAD_NAME)]


def _worker_kwargs():
    kwargs, _, _ = fakes(Clock(limit=T0 + timedelta(minutes=30)))
    return kwargs


def beat_doc() -> dict | None:
    return json.loads(hb.path().read_text(encoding="utf-8")) if hb.path().exists() else None


def plant_other(age_s: float = 5, *, pid: int = OTHER_PID) -> None:
    now = datetime.now(timezone.utc)
    hb.path().parent.mkdir(parents=True, exist_ok=True)
    hb.path().write_text(json.dumps({
        "pid": pid, "started_at": (now - timedelta(hours=2)).isoformat(),
        "last_beat": (now - timedelta(seconds=age_s)).isoformat(), "mode": "standalone",
        "sources": ["xsearch_web", "reddit_web"], "version": None, "stopped": False, "stopped_at": None}),
        encoding="utf-8")


def other_alive(monkeypatch, alive: bool = True) -> None:
    real = hb.pid_alive
    monkeypatch.setattr(hb, "pid_alive", lambda pid: alive if pid == OTHER_PID else real(pid))


def wait_for(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


# --- the API lifespan path (in_api) --------------------------------------------------------------------------------

def test_in_api_start_writes_heartbeat_and_stop_marks_it_stopped():
    worker = apr.start_from_env(env=FLAG_ON, **_worker_kwargs())
    assert worker is not None and worker.running
    d = beat_doc()
    assert d["pid"] == os.getpid() and d["mode"] == "in_api" and d["stopped"] is False
    assert d["sources"] == ["xsearch_web", "reddit_web"]
    assert hb.status(datetime.now(timezone.utc))["state"] == "running"
    apr.stop_worker()
    d = beat_doc()
    assert d["stopped"] is True and hb.status(datetime.now(timezone.utc))["state"] == "stopped"


def test_flag_off_writes_no_heartbeat():
    assert apr.start_from_env(env={}) is None
    assert beat_doc() is None


def test_start_refused_beside_live_collector(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    plant_other()
    other_alive(monkeypatch)
    before = hb.path().read_bytes()
    assert apr.start_from_env(env=FLAG_ON, **_worker_kwargs()) is None  # never raises
    assert apr.current_worker() is None and apr.disabled_reason() == "another-instance"
    assert _threads() == [] and hb.path().read_bytes() == before
    assert not [h for name in apr.LOG_LOGGERS for h in logging.getLogger(name).handlers
                if getattr(h, "attention_pc", False)]
    assert "another_instance" in caplog.text


@pytest.mark.parametrize("case", ["stale", "dead"])
def test_start_allowed_after_crash(monkeypatch, case):
    plant_other(age_s=120 if case == "stale" else 5)
    other_alive(monkeypatch, alive=case == "stale")
    worker = apr.start_from_env(env=FLAG_ON, **_worker_kwargs())
    assert worker is not None and beat_doc()["pid"] == os.getpid()


def test_api_lifespan_starts_fine_beside_live_standalone(monkeypatch):
    plant_other()
    other_alive(monkeypatch)
    monkeypatch.setenv(apr.FLAG_ENV, "1")
    from api.main import app
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert apr.current_worker() is None and apr.disabled_reason() == "another-instance"
    assert beat_doc()["pid"] == OTHER_PID


# --- the standalone runner -----------------------------------------------------------------------------------------

def _run_in_thread(**kw):
    out = {}
    stop = threading.Event()
    t = threading.Thread(target=lambda: out.setdefault("code", ac.run(**kw, stop=stop, install_signals=False)),
                         name="test-runner")
    t.start()
    return t, stop, out


def test_runner_refuses_without_flag(caplog):
    caplog.set_level(logging.INFO)
    for env in ({}, {apr.FLAG_ENV: "0"}, {apr.FLAG_ENV: "true"}):
        assert ac.run(env=env, stop=threading.Event(), install_signals=False) == ac.EXIT_FLAG_OFF
    assert apr.FLAG_ENV in caplog.text and beat_doc() is None and _threads() == []


def test_runner_runs_both_streams_until_stopped_then_cleans_up():
    t, stop, out = _run_in_thread(env=FLAG_ON, **_worker_kwargs())
    assert wait_for(lambda: beat_doc() is not None)
    d = beat_doc()
    assert d["mode"] == "standalone" and d["pid"] == os.getpid() and d["stopped"] is False
    assert d["sources"] == ["xsearch_web", "reddit_web"]
    assert sorted(n for n in _threads() if n.startswith("attention-pc")) == [
        "attention-pc-reddit_web", "attention-pc-xsearch_web"]
    assert hb.status(datetime.now(timezone.utc))["state"] == "running"
    stop.set()
    t.join(30)
    assert not t.is_alive() and out["code"] == ac.EXIT_OK
    assert beat_doc()["stopped"] is True and apr.current_worker() is None and _threads() == []
    assert not [h for name in apr.LOG_LOGGERS for h in logging.getLogger(name).handlers
                if getattr(h, "attention_pc", False)]


def test_runner_refuses_second_instance(monkeypatch):
    plant_other()
    other_alive(monkeypatch)
    assert ac.run(env=FLAG_ON, stop=threading.Event(), install_signals=False, **_worker_kwargs()) == ac.EXIT_REFUSED
    assert beat_doc()["pid"] == OTHER_PID and _threads() == []


def test_runner_start_failure_exit_code(monkeypatch):
    def broken(**_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(apr, "AttentionPcWorker", broken)
    assert ac.run(env=FLAG_ON, stop=threading.Event(), install_signals=False) == ac.EXIT_START_FAILED
    assert _threads() == []


@pytest.mark.skipif(threading.current_thread() is not threading.main_thread(), reason="signals need the main thread")
def test_sigint_stops_runner_cleanly_and_restores_handler():
    before = signal.getsignal(signal.SIGINT)
    fired = []

    def interrupt():
        if wait_for(lambda: beat_doc() is not None):
            fired.append(True)
            signal.raise_signal(signal.SIGINT)

    threading.Thread(target=interrupt, name="test-interrupt", daemon=True).start()
    code = ac.run(env=FLAG_ON, poll_seconds=0.05, **_worker_kwargs())
    assert fired and code == ac.EXIT_OK
    assert beat_doc()["stopped"] is True and _threads() == []
    assert signal.getsignal(signal.SIGINT) is before


def test_console_close_event_requests_stop_and_waits_for_cleanup():
    stop, done = threading.Event(), threading.Event()
    threading.Timer(0.05, done.set).start()
    assert ac.console_event(ac.CTRL_CLOSE_EVENT, stop, done, timeout=5) is True
    assert stop.is_set() and done.is_set()
    for event in (ac.CTRL_C_EVENT, ac.CTRL_BREAK_EVENT):
        s = threading.Event()
        assert ac.console_event(event, s, threading.Event(), timeout=0) is False  # Python's own SIGINT/SIGBREAK
        assert s.is_set()


def test_module_entry_refuses_without_flag(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != apr.FLAG_ENV}
    env["SCREENER_CACHE_ROOT"] = str(tmp_path)
    done = subprocess.run([sys.executable, "-m", "api.data.attention_collector"], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == ac.EXIT_FLAG_OFF
    assert apr.FLAG_ENV in done.stderr
    assert not (tmp_path / "attention" / "_pc_state" / "collector_heartbeat.json").exists()


def test_runner_keeps_twscrape_lazy():
    src = (REPO / "api" / "data" / "attention_collector.py").read_text(encoding="utf-8")
    assert "twscrape" not in src
