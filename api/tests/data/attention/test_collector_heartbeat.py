"""Standalone collector (B): the heartbeat file, its refresh and stop mark, the single-instance guard and the
status read. Files only, under the throwaway cache root; clocks are injected; no network, no process is signalled."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from api.data import cache
from api.data.attention import collector_heartbeat as hb

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
OTHER_PID = 424242


@pytest.fixture(autouse=True)
def _isolated(isolated_cache):
    yield isolated_cache
    assert not [t for t in threading.enumerate() if t.name == hb.THREAD_NAME and t.is_alive()]


class Clock:
    def __init__(self, t: datetime = NOW):
        self.t = t

    def __call__(self) -> datetime:
        return self.t


def doc() -> dict:
    return json.loads(hb.path().read_text(encoding="utf-8"))


def plant(*, pid=OTHER_PID, beat=NOW, stopped=False, mode="standalone", **extra) -> None:
    hb.path().parent.mkdir(parents=True, exist_ok=True)
    body = {"pid": pid, "started_at": (beat - timedelta(hours=1)).isoformat(), "last_beat": beat.isoformat(),
            "mode": mode, "sources": ["xsearch_web", "reddit_web"], "version": None, "stopped": stopped,
            "stopped_at": beat.isoformat() if stopped else None, **extra}
    hb.path().write_text(json.dumps(body), encoding="utf-8")


def test_constants_and_path():
    assert hb.BEAT_SECONDS <= 30 and hb.FRESH_SECONDS == 90
    assert hb.path() == cache.CACHE_ROOT / "attention" / "_pc_state" / "collector_heartbeat.json"
    assert hb.MODES == ("standalone", "in_api")


def test_start_writes_heartbeat_atomically_with_every_field(monkeypatch):
    writes = []
    real = cache._atomic_write_json
    monkeypatch.setattr(cache, "_atomic_write_json", lambda obj, p: (writes.append(p), real(obj, p)))
    beat = hb.Heartbeat(mode="standalone", sources=["xsearch_web", "reddit_web"], clock=Clock(), interval=3600)
    beat.start()
    try:
        d = doc()
        assert writes and writes[0] == hb.path()
        assert set(d) == {"pid", "started_at", "last_beat", "mode", "sources", "version", "stopped", "stopped_at"}
        assert (d["pid"], d["mode"], d["sources"], d["stopped"], d["stopped_at"]) == (
            os.getpid(), "standalone", ["xsearch_web", "reddit_web"], False, None)
        assert d["started_at"] == d["last_beat"] == NOW.isoformat()
        assert d["version"] is None or (isinstance(d["version"], str) and len(d["version"]) >= 7)
    finally:
        beat.stop()


def test_beat_refreshes_last_beat_and_keeps_started_at():
    clock = Clock()
    beat = hb.Heartbeat(mode="in_api", sources=["reddit_web"], clock=clock, interval=3600)
    beat.beat()
    clock.t = NOW + timedelta(seconds=30)
    beat.beat()
    d = doc()
    assert d["started_at"] == NOW.isoformat() and d["last_beat"] == (NOW + timedelta(seconds=30)).isoformat()
    assert d["mode"] == "in_api" and d["stopped"] is False


def test_thread_refreshes_on_its_interval_then_stop_marks_stopped_and_joins():
    clock = Clock()
    beat = hb.Heartbeat(mode="standalone", sources=[], clock=clock, interval=0.01)
    beat.start()
    clock.t = NOW + timedelta(seconds=45)
    deadline = time.monotonic() + 5
    while doc()["last_beat"] != clock.t.isoformat() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert doc()["last_beat"] == clock.t.isoformat()
    thread = beat.thread
    clock.t = NOW + timedelta(seconds=50)
    beat.stop()
    assert thread is not None and not thread.is_alive()
    d = doc()
    assert d["stopped"] is True and d["stopped_at"] == clock.t.isoformat()
    beat.stop()  # idempotent


def test_stop_never_marks_another_process_heartbeat():
    beat = hb.Heartbeat(mode="standalone", sources=[], clock=Clock(), interval=3600)
    beat.start()
    plant(pid=OTHER_PID, beat=NOW)  # another process replaced the file (a race the guard could not see)
    beat.stop()
    d = doc()
    assert d["pid"] == OTHER_PID and d["stopped"] is False


def test_write_failure_is_logged_never_raised(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    def boom(_obj, _p):
        raise PermissionError("PLANTED-detail")

    monkeypatch.setattr(cache, "_atomic_write_json", boom)
    beat = hb.Heartbeat(mode="standalone", sources=[], clock=Clock(), interval=3600)
    beat.start()
    beat.stop()
    assert "PermissionError" in caplog.text and "PLANTED-detail" not in caplog.text


def test_naive_clock_refused():
    with pytest.raises(ValueError):
        hb.Heartbeat(mode="standalone", sources=[], clock=lambda: datetime(2026, 11, 2), interval=1).beat()


def test_unknown_mode_refused():
    with pytest.raises(ValueError):
        hb.Heartbeat(mode="sideways", sources=[])


# --- pid probe -----------------------------------------------------------------------------------------------------

def test_pid_alive_own_dead_and_invalid():
    assert hb.pid_alive(os.getpid()) is True
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=30)
    assert hb.pid_alive(child.pid) is False
    for bad in (0, -1, True, "12", None):
        assert hb.pid_alive(bad) is False


def test_pid_probe_never_signals_on_windows():
    source = open(hb.__file__, encoding="utf-8").read()
    assert "os.kill(" not in source.split("def _windows_alive", 1)[1].split("\ndef ", 1)[0]


# --- guard ---------------------------------------------------------------------------------------------------------

def alive_if(pid_set):
    return lambda pid: pid in pid_set


def test_fresh_live_other_process_blocks():
    plant(beat=NOW - timedelta(seconds=89))
    other = hb.blocking(NOW, alive=alive_if({OTHER_PID}))
    assert other is not None and other["pid"] == OTHER_PID and other["mode"] == "standalone"


def test_uncheckable_pid_with_fresh_beat_blocks():
    plant(beat=NOW - timedelta(seconds=5))
    assert hb.blocking(NOW, alive=lambda _pid: None) is not None


@pytest.mark.parametrize("case", ["stale", "dead", "own", "stopped", "missing", "unreadable"])
def test_start_allowed(case):
    if case == "stale":
        plant(beat=NOW - timedelta(seconds=90))
    elif case == "dead":
        plant(beat=NOW - timedelta(seconds=5))
    elif case == "own":
        plant(pid=os.getpid(), beat=NOW - timedelta(seconds=5))
    elif case == "stopped":
        plant(beat=NOW - timedelta(seconds=5), stopped=True)
    elif case == "unreadable":
        hb.path().parent.mkdir(parents=True, exist_ok=True)
        hb.path().write_text("{not json", encoding="utf-8")
    alive = alive_if({os.getpid()}) if case != "stale" else alive_if({OTHER_PID})
    assert hb.blocking(NOW, alive=alive) is None


# --- status (read by the Sources API) ------------------------------------------------------------------------------

def test_status_never_started_without_file():
    s = hb.status(NOW)
    assert (s["state"], s["reason"], s["last_beat"], s["age_s"], s["mode"]) == (
        "never_started", "no_heartbeat", None, None, None)


def test_status_running_when_fresh_and_alive():
    plant(beat=NOW - timedelta(seconds=12), mode="in_api")
    s = hb.status(NOW, alive=alive_if({OTHER_PID}))
    assert (s["state"], s["reason"], s["age_s"], s["mode"]) == ("running", "", 12.0, "in_api")
    assert s["started_at"] == (NOW - timedelta(seconds=12, hours=1)).isoformat()
    assert s["sources"] == ["xsearch_web", "reddit_web"]


@pytest.mark.parametrize("beat,stopped,alive,reason", [
    (NOW - timedelta(seconds=91), False, {OTHER_PID}, "heartbeat_stale"),
    (NOW - timedelta(seconds=5), True, {OTHER_PID}, "stopped_cleanly"),
    (NOW - timedelta(seconds=5), False, set(), "process_gone"),
])
def test_status_stopped(beat, stopped, alive, reason):
    plant(beat=beat, stopped=stopped)
    s = hb.status(NOW, alive=alive_if(alive))
    assert (s["state"], s["reason"]) == ("stopped", reason)
    assert s["age_s"] == round((NOW - beat).total_seconds(), 1)


@pytest.mark.parametrize("body", ["{not json", "[]", json.dumps({"pid": "x"}),
                                  json.dumps({"pid": 1, "started_at": "2026-11-02T10:00:00", "last_beat": "nope",
                                              "mode": "standalone", "sources": [], "version": None,
                                              "stopped": False, "stopped_at": None})])
def test_status_unknown_when_unreadable(body):
    hb.path().parent.mkdir(parents=True, exist_ok=True)
    hb.path().write_text(body, encoding="utf-8")
    s = hb.status(NOW)
    assert (s["state"], s["reason"], s["age_s"]) == ("unknown", "unreadable", None)


def test_status_unknown_when_beat_far_in_the_future():
    plant(beat=NOW + timedelta(minutes=10))
    s = hb.status(NOW, alive=alive_if({OTHER_PID}))
    assert (s["state"], s["reason"]) == ("unknown", "unreadable")
