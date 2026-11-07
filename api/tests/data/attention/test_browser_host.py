"""S-BrowserHost native lifecycle acceptance. No installed browser is launched."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from api.data.attention import browser_host as h
from api.data.attention import browser_profile as p
from api.tests.data.attention.fixture_seams import spawn_launcher

FAKE = "api.tests.data.attention.browser_fake_main"
POLICY = p.ProfilePolicy(True, True)
# uv's Python redirector has no PE version resource (1813). This binary is only
# inspected; the constructor spawn seam launches Python, never cmd or a browser.
BINARY = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"


def fake_spawn(argv):
    return spawn_launcher(FAKE, *argv[1:])


def host(tmp_path, **kw):
    binary = BINARY
    h.write_admission(tmp_path, binary, h.executable_version(binary), outcome="tested_clean", destination_classes=[])
    return h.BrowserHost(binary, tmp_path / "profiles", cache_root=tmp_path, policy=POLICY,
                         spawn=fake_spawn, memory=lambda: 9999, **kw)


def exchange(session, method="Browser.getVersion", params=None):
    session.pipe.send(json.dumps({"id": 1, "method": method, "params": params or {}}).encode())
    return json.loads(session.pipe.receive(timeout=5))


def wait_dead(pid):
    deadline = time.monotonic() + 5
    while h.process_creation(pid) is not None and time.monotonic() < deadline:
        time.sleep(.02)
    assert h.process_creation(pid) is None


def test_argv_fixed_flags_and_rejects_weaker_or_duplicate_flags(tmp_path):
    argv = h.build_argv(Path(sys.executable), tmp_path / "profile", 12345, (111, 222))
    assert sum(a.startswith("--disable-features=") for a in argv) == 1
    assert "--proxy-bypass-list=<-loopback>" in argv
    assert "--webrtc-ip-handling-policy=disable_non_proxied_udp" in argv
    assert "--remote-debugging-io-pipes=111,222" in argv
    for extra in ("--disable-features=Other", "--remote-debugging-port=0", "--no-sandbox", "--enable-logging",
                  "--proxy-bypass-list=", "--disable-setuid-sandbox"):
        with pytest.raises(h.BrowserFailure):
            h.validate_argv(argv + [extra])


def test_default_policy_and_missing_admission_refuse(tmp_path):
    with pytest.raises(h.BrowserFailure, match="profile_policy_unsatisfied"):
        h.BrowserHost(Path(sys.executable), tmp_path / "profiles", cache_root=tmp_path).launch("a", "a", 12345)
    with pytest.raises(h.BrowserFailure, match="browser_unadmitted"):
        h.read_admission(tmp_path, Path(sys.executable), "no-such-version")


def test_admission_revision_and_residual_acceptance_fail_closed(tmp_path):
    binary = BINARY
    version = h.executable_version(binary)
    h.write_admission(tmp_path, binary, version, outcome="tested_clean", destination_classes=[])
    assert h.read_admission(tmp_path, binary, version)["outcome"] == "tested_clean"
    with pytest.raises(h.BrowserFailure, match="browser_unadmitted"):
        h.read_admission(tmp_path, binary, version + ".changed")
    h.write_admission(tmp_path, binary, version, outcome="containment_residual_unaccepted",
                      destination_classes=["vendor_cloud_443"])
    with pytest.raises(h.BrowserFailure, match="containment_residual_unaccepted"):
        h.read_admission(tmp_path, binary, version)


def test_low_or_unreadable_memory_refuses_before_spawn(tmp_path):
    b = host(tmp_path)
    for value in (None, 1535):
        b.memory = lambda: value
        with pytest.raises(h.BrowserFailure, match="low_memory"):
            b.launch("a", "a", 12345)


def test_spawn_pipe_flattened_session_and_restart_persistence(tmp_path, capsys):
    b = host(tmp_path)
    identities = []
    for _ in range(2):
        with b.launch("a", "a", 12345) as session:
            result = exchange(session)["result"]
            identities.append(result["fakeIdentity"])
            grandchild = result["grandchild"]
            assert h.process_creation(grandchild)
            session.pipe.send(b'{"id":2,"sessionId":"s1","method":"Page.enable","params":{}}')
            assert json.loads(session.pipe.receive(timeout=5))["sessionId"] == "s1"
            pid = session.pid
        wait_dead(pid)
        wait_dead(grandchild)
    assert identities[0] == identities[1]
    assert capsys.readouterr() == ("", "")


def test_rss_ceiling_kills_whole_tree(tmp_path):
    state = {"value": 10}
    b = host(tmp_path, rss=lambda job: state["value"])
    with b.launch("a", "a", 12345) as session:
        grandchild = exchange(session)["result"]["grandchild"]
        state["value"] = 1201
        with pytest.raises(h.BrowserFailure, match="browser_rss_exceeded"):
            session.check()
        wait_dead(session.pid)
        wait_dead(grandchild)


def test_pipe_frame_ceiling_and_deadline(tmp_path):
    with host(tmp_path).launch("a", "a", 12345) as session:
        with pytest.raises(h.BrowserFailure, match="cdp_frame_too_large"):
            session.pipe.send(b"x" * (h.FRAME_LIMIT + 1))
        with pytest.raises(h.BrowserFailure, match="cdp_timeout"):
            session.pipe.receive(timeout=.05)


def test_machine_lock_is_cache_independent_and_abandoned(tmp_path):
    code = "from api.data.attention.browser_host import MachineLock; import time; l=MachineLock(); l.acquire(); print('ready',flush=True); time.sleep(60)"
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        start = time.monotonic()
        with pytest.raises(h.BrowserFailure, match="browser_busy"):
            h.MachineLock().acquire()
        assert time.monotonic() - start < .5
        child.kill()
        child.wait(timeout=5)
        with h.MachineLock() as lock:
            assert lock.wait_result in (0, 128)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        child.stdout.close()


def test_launcher_death_kills_browser_and_grandchild(tmp_path):
    command = [sys.executable, "-m", "api.tests.data.attention.browser_lifecycle_fixture", str(tmp_path)]
    parent = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    try:
        record = json.loads(parent.stdout.readline())
        assert h.process_creation(record["pid"]) and h.process_creation(record["grandchild"])
        parent.kill()
        parent.wait(timeout=5)
        wait_dead(record["pid"])
        wait_dead(record["grandchild"])
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()
        parent.stdout.close()


def test_orphan_creation_time_mismatch_never_kills_unrelated_process(tmp_path):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        created = h.process_creation(child.pid)
        assert created
        assert not h.terminate_recorded(child.pid, created + 1)
        assert child.poll() is None
        assert h.terminate_recorded(child.pid, created)
        child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_watchdog_enforces_deadline_without_client_activity(tmp_path):
    with host(tmp_path, timeout=.3).launch("a", "a", 12345) as session:
        wait_dead(session.pid)
        with pytest.raises(h.BrowserFailure, match="browser_timeout"):
            session.check()


def test_native_rss_enumerates_the_owned_job_not_other_browsers(tmp_path):
    with host(tmp_path).launch("a", "a", 12345) as session:
        grandchild = exchange(session)["result"]["grandchild"]
        assert {session.pid, grandchild} <= set(session.job.pids())
        assert h.tree_rss_mb(session.job) > 0


def test_secret_markers_never_enter_host_state_or_diagnostics(tmp_path, capsys):
    with host(tmp_path).launch("a", "a", 12345) as session:
        marker = "SECRET-cookie-value-123"
        session.pipe.send(json.dumps({"id": 1, "method": "Page.enable", "params": {"value": marker}}).encode())
        session.pipe.receive(timeout=5)
    for path in (tmp_path / "attention").rglob("*.json"):
        assert marker not in path.read_text()
        assert str(tmp_path / "profiles") not in path.read_text()
    assert capsys.readouterr() == ("", "")
