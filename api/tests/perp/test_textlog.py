"""Stage 1 store tests: lock, take-over, whole-line appends, denied operations.

Synthetic temp files only. No network, no real cache or log paths.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from api.data.perp import textlog
from api.data.perp.textlog import AppendResult, LockHeld, append_line, locked

STALE = "2000-01-01T00:00:00+00:00"
REPO = Path(__file__).resolve().parents[3]


def _plant(data: Path, *, token: str = "old-token", started: str = STALE) -> Path:
    lock = textlog.lock_path(data)
    lock.write_text(json.dumps({"pid": 1, "started_utc": started, "token": token}) + "\n",
                    encoding="utf-8")
    return lock


def _is_lock_path(p: Path) -> bool:
    return p.name.endswith(".lock")


def test_append_then_read_back_and_lock_removed(tmp_path):
    data = tmp_path / "log.jsonl"
    with locked(data) as handle:
        assert handle.append("one")
        assert handle.append("two")
        assert handle.read_lines() == ["one", "two"]
    assert not textlog.lock_path(data).exists()
    assert not textlog.guard_path(data).exists()


def test_torn_fragment_is_skipped_reported_and_closed_before_next_append(tmp_path):
    data = tmp_path / "log.csv"
    data.write_bytes(b"one\ntwo")
    with locked(data, torn_suffix=",!TORN") as handle:
        assert handle.read_lines() == ["one"]
        assert "torn-line" in handle.problems
        assert handle.append("three")
    assert data.read_bytes() == b"one\ntwo,!TORN\nthree\n"


def test_held_lock_refuses_without_writing(tmp_path):
    data = tmp_path / "log.jsonl"
    with locked(data):
        with pytest.raises(LockHeld) as held:
            with locked(data):
                pass
        assert held.value.reason == "lock-present"
        result = append_line(data, "blocked")
    assert result == AppendResult(False, ("lock-present",))
    assert not data.exists()


def test_stale_lock_is_taken_over(tmp_path):
    data = tmp_path / "log.jsonl"
    _plant(data)
    with locked(data, takeover=True) as handle:
        assert handle.append("new")
    assert data.read_text(encoding="utf-8") == "new\n"
    assert not textlog.lock_path(data).exists()
    assert not textlog.guard_path(data).exists()


def test_handle_refuses_write_after_lock_taken_away(tmp_path):
    data = tmp_path / "log.jsonl"
    lock = textlog.lock_path(data)
    with locked(data) as handle:
        lock.write_text(json.dumps({"pid": 2, "started_utc": "2026-01-01T00:00:00+00:00",
                                    "token": "other"}) + "\n", encoding="utf-8")
        assert handle.append("x") is False
        assert "lock-token-mismatch" in handle.problems
    assert not data.exists()
    assert "other" in lock.read_text(encoding="utf-8")


def test_two_takers_one_winner_over_50_rounds(tmp_path):
    data = tmp_path / "log.jsonl"
    for round_no in range(50):
        if data.exists():
            data.unlink()
        _plant(data)
        start = threading.Barrier(2)
        done = threading.Barrier(2)
        outcomes: list[str] = []
        guard = threading.Lock()

        def taker(tag: str) -> None:
            start.wait()
            try:
                with locked(data, takeover=True) as handle:
                    handle.append(tag)
                    with guard:
                        outcomes.append("won")
                    done.wait(timeout=10)
            except LockHeld as held:
                with guard:
                    outcomes.append(held.reason)
                done.wait(timeout=10)

        threads = [threading.Thread(target=taker, args=(t,)) for t in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        assert outcomes.count("won") == 1, f"round {round_no}: {outcomes}"
        assert len(data.read_text(encoding="utf-8").splitlines()) == 1


def test_contenders_never_hold_at_once_over_50_rounds(tmp_path):
    data = tmp_path / "log.jsonl"
    for _ in range(50):
        if data.exists():
            data.unlink()
        _plant(data)
        start = threading.Barrier(2)

        def holder(tag: str) -> None:
            start.wait()
            try:
                with locked(data, takeover=True) as handle:
                    handle.append(f"begin {tag}")
                    time.sleep(0.005)
                    handle.append(f"end {tag}")
            except LockHeld:
                pass

        threads = [threading.Thread(target=holder, args=(t,)) for t in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        lines = data.read_text(encoding="utf-8").splitlines() if data.exists() else []
        assert len(lines) % 2 == 0
        for begin, end in zip(lines[0::2], lines[1::2]):
            assert begin.startswith("begin ") and end == begin.replace("begin", "end", 1)


def test_left_behind_guard_blocks_takeover_and_is_not_removed(tmp_path):
    data = tmp_path / "log.jsonl"
    lock = _plant(data)
    guard = textlog.guard_path(data)
    guard.write_bytes(b"")
    before = lock.read_bytes()
    with pytest.raises(LockHeld) as held:
        with locked(data, takeover=True):
            pass
    assert held.value.reason == "guard-present"
    assert lock.read_bytes() == before
    assert guard.exists()


def test_takeover_false_never_takes_over_a_stale_lock(tmp_path):
    data = tmp_path / "log.jsonl"
    lock = _plant(data)
    before = lock.read_bytes()
    with pytest.raises(LockHeld) as held:
        with locked(data, takeover=False):
            pass
    assert held.value.reason == "lock-present"
    assert lock.read_bytes() == before


def test_acquirer_refused_on_guard_creates_no_lock_and_keeps_data(tmp_path):
    data = tmp_path / "log.jsonl"
    data.write_bytes(b"keep\n")
    textlog.guard_path(data).write_bytes(b"")
    with pytest.raises(LockHeld) as held:
        with locked(data, takeover=True):
            pass
    assert held.value.reason == "guard-present"
    assert not textlog.lock_path(data).exists()
    assert data.read_bytes() == b"keep\n"


def test_forced_order_gives_one_successful_acquire(tmp_path, monkeypatch):
    """VA-51: a taker completes between the acquirer's create and its token re-read."""
    data = tmp_path / "log.jsonl"
    fired: list[bool] = []
    taker: dict = {}

    def hook(lock_file: Path) -> None:
        if fired:
            return
        fired.append(True)
        _plant(data, token="stale")
        cm = locked(data, takeover=True)
        taker["cm"] = cm
        taker["handle"] = cm.__enter__()

    monkeypatch.setattr(textlog, "_after_create_hook", hook)
    with pytest.raises(LockHeld) as held:
        with locked(data, takeover=True):
            pass
    assert held.value.reason == "token-lost-after-create"
    assert taker["handle"].append("taker")
    taker["cm"].__exit__(None, None, None)
    assert data.read_text(encoding="utf-8") == "taker\n"


def test_two_processes_lose_no_line(tmp_path):
    data = tmp_path / "shared.jsonl"
    code = (
        "import sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from api.data.perp import textlog\n"
        "path, tag = sys.argv[2], sys.argv[3]\n"
        "for i in range(2000):\n"
        "    r = textlog.append_line(path, f'{tag}-{i}', wait_seconds=60)\n"
        "    assert r.written, r.problems\n"
    )
    procs = [subprocess.Popen([sys.executable, "-c", code, str(REPO), str(data), tag])
             for tag in ("a", "b")]
    for proc in procs:
        assert proc.wait(timeout=1500) == 0
    lines = data.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4000
    assert len(set(lines)) == 4000
    assert all(re.fullmatch(r"[ab]-\d+", line) for line in lines)


def test_denied_lock_read_refuses_and_leaves_lock(tmp_path, monkeypatch):
    data = tmp_path / "log.jsonl"
    lock = _plant(data)
    before = lock.read_bytes()
    real = textlog._read_bytes

    def deny(p: Path) -> bytes:
        if _is_lock_path(p):
            raise PermissionError(13, "denied", str(p))
        return real(p)

    monkeypatch.setattr(textlog, "_read_bytes", deny)
    with pytest.raises(LockHeld) as held:
        with locked(data, takeover=True):
            pass
    assert held.value.reason == "lock-read-denied"
    monkeypatch.undo()
    assert lock.read_bytes() == before
    assert not textlog.guard_path(data).exists()


def test_transient_read_denial_on_append_recheck_does_not_drop_line(tmp_path, monkeypatch):
    data = tmp_path / "log.jsonl"
    real_read = textlog._read_bytes
    with textlog.locked(data) as handle:
        failed = {"once": False}

        def one_sharing_violation(p):
            if not failed["once"]:
                failed["once"] = True
                raise PermissionError("sharing violation")
            return real_read(p)

        monkeypatch.setattr(textlog, "_read_bytes", one_sharing_violation)
        assert handle.append("a-1") is True
        assert handle.problems == []
    assert data.read_text(encoding="utf-8") == "a-1\n"


def test_denied_lock_create_is_held(tmp_path, monkeypatch):
    data = tmp_path / "log.jsonl"
    real = textlog._create_excl

    def deny(p: Path, body: bytes) -> None:
        if _is_lock_path(p):
            raise PermissionError(13, "denied", str(p))
        real(p, body)

    monkeypatch.setattr(textlog, "_create_excl", deny)
    with pytest.raises(LockHeld) as held:
        with locked(data):
            pass
    assert held.value.reason == "lock-create-denied"
    assert not textlog.lock_path(data).exists()
    assert not textlog.guard_path(data).exists()


def test_denied_stale_lock_delete_leaves_no_acquired_lock(tmp_path, monkeypatch):
    data = tmp_path / "log.jsonl"
    lock = _plant(data)
    before = lock.read_bytes()

    def deny(p: Path) -> None:
        if _is_lock_path(p):
            raise PermissionError(13, "denied", str(p))
        p.unlink()

    monkeypatch.setattr(textlog, "_unlink", deny)
    with pytest.raises(LockHeld) as held:
        with locked(data, takeover=True):
            pass
    assert held.value.reason == "lock-present"
    monkeypatch.undo()
    assert lock.read_bytes() == before
    assert not textlog.guard_path(data).exists()

def test_denied_create_retries_only_denial_for_two_seconds_with_fake_clock(tmp_path, monkeypatch):
    data = tmp_path / "retry.jsonl"
    clock = [0.0]
    sleeps = []
    monkeypatch.setattr(textlog.time, "monotonic", lambda: clock[0])
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(textlog.time, "sleep", sleep)
    calls = []
    def denied(p, body):
        calls.append(p)
        raise PermissionError(13, "denied", str(p))
    monkeypatch.setattr(textlog, "_create_excl", denied)
    with pytest.raises(LockHeld) as held:
        with locked(data):
            pass
    assert held.value.reason == "lock-create-denied"
    assert len(calls) > 1 and clock[0] <= 2.05


def test_empty_lock_file_is_held_and_untouched(tmp_path):
    data = tmp_path / "log.jsonl"
    lock = textlog.lock_path(data)
    lock.write_bytes(b"")
    with pytest.raises(LockHeld) as held:
        with locked(data, takeover=True):
            pass
    assert held.value.reason == "lock-empty-or-unparseable"
    assert lock.read_bytes() == b""


def test_denied_token_reread_refuses_append_and_keeps_data(tmp_path, monkeypatch):
    data = tmp_path / "log.jsonl"
    real = textlog._read_bytes
    with locked(data) as handle:
        def deny(p: Path) -> bytes:
            if _is_lock_path(p):
                raise PermissionError(13, "denied", str(p))
            return real(p)

        monkeypatch.setattr(textlog, "_read_bytes", deny)
        assert handle.append("x") is False
        monkeypatch.undo()
    assert "lock-read-denied" in handle.problems
    assert not data.exists()


def test_denied_own_delete_is_bounded_and_reported(tmp_path, monkeypatch):
    data = tmp_path / "log.jsonl"

    def deny(p: Path) -> None:
        if _is_lock_path(p):
            raise PermissionError(13, "denied", str(p))
        p.unlink()

    start = time.monotonic()
    with locked(data) as handle:
        monkeypatch.setattr(textlog, "_unlink", deny)
    elapsed = time.monotonic() - start
    monkeypatch.undo()
    assert "lock-release-denied" in handle.problems
    assert 1.5 <= elapsed < 10
    textlog.lock_path(data).unlink()


def test_refused_takeover_keeps_the_guard_left_problem(tmp_path, monkeypatch):
    """A left-behind take-over guard is reported even when the write is refused."""
    import datetime as dt

    data = tmp_path / "log.jsonl"
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
    textlog.lock_path(data).write_text(
        json.dumps({"pid": 1, "started_utc": old, "token": "stale"}), encoding="utf-8")
    real_delete_own = textlog._delete_own

    def keep_guard(p):
        if p.name.endswith(".takeover"):
            return False
        return real_delete_own(p)

    monkeypatch.setattr(textlog, "_delete_own", keep_guard)
    result = append_line(data, "line")
    assert result.written is False
    assert "takeover-guard-left" in result.problems
    assert "guard-held" in result.problems
    assert not data.exists() or data.read_text(encoding="utf-8") == ""
