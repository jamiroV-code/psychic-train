"""Per-file lock and whole-line appends for the perp collector.

Implements VA-30 (lock, take-over), VA-44 (acquirer rule), VA-50..52 (pins,
denied operations). Public surface: `locked`, `Handle`, `LockHeld`,
`AppendResult`, `append_line`, `lock_path`, `guard_path`.

Every lock/guard file operation goes through the small `_read_bytes`,
`_create_excl`, `_unlink` and `_stat_exists` seams so tests can make a single
lock or guard path fail with PermissionError.
"""
from __future__ import annotations

import contextlib
import json
import os
import secrets
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

APPEND_LOCK_STALE_SECONDS = 30
OWN_DELETE_RETRY_SECONDS = 2.0
ACQUIRE_DENIAL_RETRY_SECONDS = 2.0
_POLL_SECONDS = 0.05

PROBLEM_RELEASE_DENIED = "lock-release-denied"
PROBLEM_GUARD_LEFT = "takeover-guard-left"
PROBLEM_TORN_LINE = "torn-line"
PROBLEM_READ_DENIED = "data-read-denied"
PROBLEM_WRITE_DENIED = "data-write-denied"

REFUSALS = frozenset({
    "guard-present",
    "guard-held",
    "token-lost-after-create",
    "lock-present",
    "lock-read-denied",
    "lock-create-denied",
    "lock-empty-or-unparseable",
    "lock-token-mismatch",
})


class LockHeld(Exception):
    """The lock could not be taken or kept. `reason` is from REFUSALS.

    `problems` holds problems recorded during the failed attempts (for example a
    take-over guard left behind), so a refused write still reports them.
    """

    def __init__(self, reason: str) -> None:
        if reason not in REFUSALS:
            raise ValueError(f"unknown refusal reason: {reason}")
        super().__init__(reason)
        self.reason = reason
        self.problems: tuple[str, ...] = ()


# Test seam for the VA-51 forced-order case: runs right after a lock create.
_after_create_hook: Callable[[Path], None] | None = None


def lock_path(path: Path) -> Path:
    return path.with_name(path.name + ".lock")


def guard_path(path: Path) -> Path:
    lock = lock_path(path)
    return lock.with_name(lock.name + ".takeover")


# --- file-operation seam (lock and guard paths only) -----------------------

def _read_bytes(p: Path) -> bytes:
    return p.read_bytes()


def _create_excl(p: Path, data: bytes) -> None:
    with open(p, "xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def _unlink(p: Path) -> None:
    p.unlink()


def _stat_exists(p: Path) -> bool:
    try:
        p.stat()
    except FileNotFoundError:
        return False
    return True


# --- lock state -------------------------------------------------------------

@dataclass(frozen=True)
class _LockState:
    state: str  # ok | missing | denied | unparseable
    token: str | None
    started: float | None  # epoch seconds, from started_utc or file mtime


def _epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def _file_started(lock: Path) -> float | None:
    try:
        return lock.stat().st_mtime
    except OSError:
        return None


def _read_lock(lock: Path) -> _LockState:
    """Read the lock. A transient OS error is retried within the denial bound."""
    deadline = time.monotonic() + ACQUIRE_DENIAL_RETRY_SECONDS
    while True:
        try:
            raw = _read_bytes(lock)
            break
        except FileNotFoundError:
            return _LockState("missing", None, None)
        except OSError:
            if time.monotonic() >= deadline:
                return _LockState("denied", None, None)
            time.sleep(_POLL_SECONDS)
    try:
        body = json.loads(raw.decode("utf-8"))
        token = body["token"]
        started = _epoch(body["started_utc"])
        if not isinstance(token, str) or not token:
            raise ValueError("empty token")
        return _LockState("ok", token, started)
    except (ValueError, KeyError, TypeError):
        return _LockState("unparseable", None, _file_started(lock))


def _is_stale(started: float | None, seconds: float = APPEND_LOCK_STALE_SECONDS) -> bool:
    return started is not None and time.time() - started > seconds


_HELD_FOR = {
    "ok": "lock-present",
    "unparseable": "lock-empty-or-unparseable",
    "denied": "lock-read-denied",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_lock(lock: Path) -> str:
    token = secrets.token_hex(16)
    body = json.dumps(
        {"pid": os.getpid(), "started_utc": _now_iso(), "token": token},
        separators=(",", ":"),
    ) + "\n"
    try:
        _create_excl(lock, body.encode("utf-8"))
    except FileExistsError:
        raise LockHeld("lock-present") from None
    except OSError:
        raise LockHeld("lock-create-denied") from None
    if _after_create_hook is not None:
        _after_create_hook(lock)
    return token


def _flag_guard(problems: list[str]) -> None:
    """VA-53: a guard on disk blocks every acquirer; report it once per run."""
    if PROBLEM_GUARD_LEFT not in problems:
        problems.append(PROBLEM_GUARD_LEFT)


def _check_guard(guard: Path, reason: str, problems: list[str]) -> None:
    try:
        exists = _stat_exists(guard)
    except OSError:
        raise LockHeld("guard-held") from None
    if exists:
        _flag_guard(problems)
        raise LockHeld(reason)


def _delete_own(path: Path) -> bool:
    """Delete a file this process created, retrying within the 2 s bound."""
    deadline = time.monotonic() + OWN_DELETE_RETRY_SECONDS
    while True:
        try:
            _unlink(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(_POLL_SECONDS)


def _release_own(lock: Path, token: str, problems: list[str]) -> None:
    """Delete the lock only while it still carries our token."""
    deadline = time.monotonic() + OWN_DELETE_RETRY_SECONDS
    while True:
        now = _read_lock(lock)
        if now.state == "missing" or (now.state == "ok" and now.token != token):
            return
        if now.state == "ok":
            try:
                _unlink(lock)
                return
            except FileNotFoundError:
                return
            except OSError:
                pass
        if time.monotonic() >= deadline:
            problems.append(PROBLEM_RELEASE_DENIED)
            return
        time.sleep(_POLL_SECONDS)


def _take_over(
    lock: Path, guard: Path, seen: _LockState, problems: list[str], stale_seconds: float
) -> str:
    """VA-30 take-over of a stale lock, guarded by our own guard file."""
    try:
        _create_excl(guard, b"")
    except FileExistsError:
        _flag_guard(problems)
        raise LockHeld("guard-present") from None
    except OSError:
        raise LockHeld("guard-held") from None
    try:
        now = _read_lock(lock)
        if now.state == "denied":
            raise LockHeld("lock-read-denied")
        if now.state == "missing":
            raise LockHeld("lock-present")
        if now.token != seen.token:
            raise LockHeld("lock-token-mismatch")
        if not _is_stale(now.started, stale_seconds):
            raise LockHeld(_HELD_FOR[now.state])
        try:
            _unlink(lock)
        except FileNotFoundError:
            pass
        except OSError:
            raise LockHeld("lock-present") from None
        return _create_lock(lock)
    finally:
        if not _delete_own(guard):
            problems.append(PROBLEM_GUARD_LEFT)


def _confirm(lock: Path, guard: Path, token: str, problems: list[str]) -> None:
    """VA-51 pin: check no guard first, then re-read our own token."""
    try:
        guard_there = _stat_exists(guard)
    except OSError:
        guard_there = True
    if guard_there:
        _flag_guard(problems)
        _release_own(lock, token, problems)
        raise LockHeld("guard-held")
    now = _read_lock(lock)
    if now.state != "ok" or now.token != token:
        raise LockHeld("token-lost-after-create")


def _acquire_once(
    path: Path, takeover: bool, problems: list[str], stale_seconds: float
) -> str:
    lock, guard = lock_path(path), guard_path(path)
    _check_guard(guard, "guard-present", problems)
    state = _read_lock(lock)
    if state.state == "missing":
        token = _create_lock(lock)
    elif not takeover or state.state == "denied" or not _is_stale(state.started, stale_seconds):
        raise LockHeld(_HELD_FOR[state.state])
    else:
        token = _take_over(lock, guard, state, problems, stale_seconds)
    _confirm(lock, guard, token, problems)
    return token


# --- public API -------------------------------------------------------------

class Handle:
    """Write handle held by `locked()`. Writes only while the lock is ours."""

    def __init__(self, path: Path, token: str, torn_suffix: str, problems: list[str]) -> None:
        self._path = path
        self._lock = lock_path(path)
        self._token = token
        self._torn_suffix = torn_suffix
        self.problems = problems

    def read_lines(self) -> list[str]:
        """Complete lines only. A torn final fragment is skipped and reported."""
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            return []
        except OSError:
            self.problems.append(PROBLEM_READ_DENIED)
            return []
        complete, _, tail = raw.decode("utf-8", errors="replace").rpartition("\n")
        if tail:
            self.problems.append(PROBLEM_TORN_LINE)
        return [line for line in complete.split("\n") if line]

    def _token_problem(self) -> str | None:
        now = _read_lock(self._lock)
        if now.state == "ok" and now.token == self._token:
            return None
        if now.state == "denied":
            return "lock-read-denied"
        if now.state == "unparseable":
            return "lock-empty-or-unparseable"
        return "lock-token-mismatch"

    def owns(self) -> bool:
        """True while the lock still carries our token. Records no problem."""
        return self._token_problem() is None

    def append(self, line: str) -> bool:
        """Append one whole line. Refuses, with bytes unchanged, if the lock is not ours."""
        if "\n" in line:
            raise ValueError("a line may not contain a newline")
        problem = self._token_problem()
        if problem is not None:
            self.problems.append(problem)
            return False
        try:
            prefix = (self._torn_suffix + "\n") if _ends_mid_line(self._path) else ""
            with open(self._path, "ab") as f:
                f.write((prefix + line + "\n").encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            self.problems.append(PROBLEM_WRITE_DENIED)
            return False
        return True


def _ends_mid_line(path: Path) -> bool:
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return False
    if size == 0:
        return False
    with open(path, "rb") as f:
        f.seek(-1, os.SEEK_END)
        return f.read(1) != b"\n"


@contextlib.contextmanager
def locked(
    path: Path | str,
    *,
    wait_seconds: float = 0.0,
    takeover: bool = True,
    torn_suffix: str = "",
    stale_seconds: float = APPEND_LOCK_STALE_SECONDS,
) -> Iterator[Handle]:
    """Hold the per-file lock for the body. Raises `LockHeld` if it cannot be taken."""
    path = Path(path)
    problems: list[str] = []
    denial_deadline = time.monotonic() + ACQUIRE_DENIAL_RETRY_SECONDS
    wait_deadline = time.monotonic() + wait_seconds
    while True:
        try:
            token = _acquire_once(path, takeover, problems, stale_seconds)
            break
        except LockHeld as held:
            denial_only = held.reason in {"lock-read-denied", "lock-create-denied"}
            deadline = denial_deadline if denial_only else wait_deadline
            if time.monotonic() >= deadline:
                held.problems = tuple(problems)
                raise
            time.sleep(min(_POLL_SECONDS, max(0.0, deadline - time.monotonic())))
    handle = Handle(path, token, torn_suffix, problems)
    try:
        yield handle
    finally:
        _release_own(lock_path(path), token, problems)


@dataclass(frozen=True)
class AppendResult:
    written: bool
    problems: tuple[str, ...]


def append_line(
    path: Path | str,
    line: str,
    *,
    wait_seconds: float = 0.0,
    takeover: bool = True,
    torn_suffix: str = "",
) -> AppendResult:
    """Lock, append one whole line, release. A refused lock is reported, never raised."""
    try:
        with locked(path, wait_seconds=wait_seconds, takeover=takeover,
                    torn_suffix=torn_suffix) as handle:
            written = handle.append(line)
    except LockHeld as held:
        return AppendResult(False, held.problems + (held.reason,))
    return AppendResult(written, tuple(handle.problems))
