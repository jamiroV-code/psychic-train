"""The attention collector's heartbeat and single-instance guard (standalone-collector, 02-11-26).

The PC worker (`api.data.attention_pc_refresh`), inside the API (`in_api`) or as its own process
(`python -m api.data.attention_collector`, `standalone`), writes `<cache>/attention/_pc_state/collector_heartbeat.json`
through the cache's atomic JSON write: at start, every `BEAT_SECONDS` while it runs, and with `stopped: true` on a
clean stop. Fields: pid, started_at, last_beat (UTC ISO), mode, sources (the streams it runs), version (the git
commit when it can be read from files) and stopped / stopped_at.

- Guard (`blocking`): a start is refused while the file holds another process's heartbeat that is not stopped, is
  younger than `FRESH_SECONDS` and whose pid is alive (or cannot be checked), so two workers never spend the shared
  Reddit and X budgets twice. A stale or stopped heartbeat, a dead pid, the caller's own pid, a missing or an
  unreadable file never block. Residual: two starts inside the same moment can both pass the check (no OS lock).
- Status (`status`): running | stopped | never_started | unknown, read from the file only (no network), for the
  Sources API. A missing file is never_started, an unreadable one unknown; neither ever reads as running.
- The pid probe never signals a process: on Windows `os.kill(pid, 0)` would terminate it, so it asks the OS through
  `OpenProcess` / `GetExitCodeProcess` instead.

Logs carry a reason code and an exception class name only.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from api.data import cache

log = logging.getLogger(__name__)

BEAT_SECONDS = 30.0
FRESH_SECONDS = 90.0
STOP_JOIN_TIMEOUT_SECONDS = 5.0
MODES = ("standalone", "in_api")
NAME = "collector_heartbeat.json"
THREAD_NAME = "attention-collector-heartbeat"
_REPO = Path(__file__).resolve().parents[3]
_KEYS = {"pid", "started_at", "last_beat", "mode", "sources", "version", "stopped", "stopped_at"}


def path() -> Path:
    return cache.CACHE_ROOT / "attention" / "_pc_state" / NAME


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        raise ValueError("clock must be timezone-aware UTC")
    return t.astimezone(timezone.utc)


def _parse(value) -> datetime | None:
    try:
        t = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return t.astimezone(timezone.utc) if t.tzinfo is not None else None


# --- version (files only, no subprocess) ----------------------------------------------------------------------------

def _git_dir(root: Path) -> Path | None:
    dot = root / ".git"
    if dot.is_dir():
        return dot
    if dot.is_file():  # a worktree: "gitdir: <path>"
        text = dot.read_text(encoding="utf-8").strip()
        if text.startswith("gitdir:"):
            return (root / text.split(":", 1)[1].strip()).resolve()
    return None


def code_version(root: Path = _REPO) -> str | None:
    """The checked-out commit (short), read from the git files; None when it cannot be read cheaply."""
    try:
        git = _git_dir(root)
        if git is None:
            return None
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head[:12] or None
        ref = head.split(":", 1)[1].strip()
        common = git / "commondir"
        dirs = [git] + ([(git / common.read_text(encoding="utf-8").strip()).resolve()] if common.is_file() else [])
        for d in dirs:
            loose = d / ref
            if loose.is_file():
                return loose.read_text(encoding="utf-8").strip()[:12] or None
        for d in dirs:
            packed = d / "packed-refs"
            if packed.is_file():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    sha, _, name = line.partition(" ")
                    if name == ref:
                        return sha[:12]
    except (OSError, ValueError):
        return None
    return None


# --- pid probe ------------------------------------------------------------------------------------------------------

def _windows_alive(pid: int) -> bool | None:
    import ctypes
    from ctypes import wintypes

    query_limited, still_active, invalid_parameter, access_denied = 0x1000, 259, 87, 5
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(query_limited, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        return False if error == invalid_parameter else True if error == access_denied else None
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return None
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def pid_alive(pid) -> bool | None:
    """True or False when the OS answers, None when it cannot be checked. Never sends a signal on Windows."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        try:
            return _windows_alive(pid)
        except (OSError, AttributeError):
            return None
    try:
        os.kill(pid, 0)  # POSIX: signal 0 only checks existence and permission
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


# --- read side ------------------------------------------------------------------------------------------------------

def _valid(doc) -> bool:
    return (isinstance(doc, dict) and _KEYS <= set(doc)
            and isinstance(doc["pid"], int) and not isinstance(doc["pid"], bool)
            and _parse(doc["started_at"]) is not None and _parse(doc["last_beat"]) is not None
            and doc["mode"] in MODES and isinstance(doc["stopped"], bool)
            and isinstance(doc["sources"], list) and all(isinstance(s, str) for s in doc["sources"])
            and (doc["version"] is None or isinstance(doc["version"], str)))


def load(p: Path | None = None) -> tuple[str, dict | None]:
    """("missing", None), ("unreadable", None) or ("ok", heartbeat)."""
    p = p or path()
    if not p.exists():
        return "missing", None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "unreadable", None
    return ("ok", doc) if _valid(doc) else ("unreadable", None)


def _assess(doc: dict, now: datetime, alive: Callable) -> tuple[str, str, float | None]:
    """(state, reason, age in seconds) of a valid heartbeat at `now`."""
    age = (_utc(now) - _parse(doc["last_beat"])).total_seconds()
    if age < -FRESH_SECONDS:  # written by a clock far ahead of this one: no reading can be trusted
        return "unknown", "unreadable", None
    age = round(max(0.0, age), 1)
    if doc["stopped"]:
        return "stopped", "stopped_cleanly", age
    if age >= FRESH_SECONDS:
        return "stopped", "heartbeat_stale", age
    if alive(doc["pid"]) is False:
        return "stopped", "process_gone", age
    return "running", "", age


def status(now: datetime, *, alive: Callable | None = None) -> dict:
    """The collector's state at `now` from the heartbeat file only (no network)."""
    out = {"state": "never_started", "reason": "no_heartbeat", "started_at": None, "last_beat": None, "age_s": None,
           "mode": None, "version": None, "sources": []}
    found, doc = load()
    if found == "missing":
        return out
    if doc is None:
        return {**out, "state": "unknown", "reason": "unreadable"}
    state, reason, age = _assess(doc, now, alive or pid_alive)
    if state == "unknown":
        return {**out, "state": state, "reason": reason}
    return {**out, "state": state, "reason": reason, "started_at": doc["started_at"], "last_beat": doc["last_beat"],
            "age_s": age, "mode": doc["mode"], "version": doc["version"], "sources": list(doc["sources"])}


def blocking(now: datetime, *, own_pid: int | None = None, alive: Callable | None = None) -> dict | None:
    """Another live collector's heartbeat that forbids a start now, or None (start allowed)."""
    _found, doc = load()
    if doc is None or doc["pid"] == (own_pid or os.getpid()):
        return None
    state, _reason, _age = _assess(doc, now, alive or pid_alive)
    return doc if state == "running" else None


# --- write side -----------------------------------------------------------------------------------------------------

class Heartbeat:
    """Writes the heartbeat at start, every `interval` seconds on its own thread, and the stop mark on `stop`."""

    def __init__(self, *, mode: str, sources: list[str], clock: Callable[[], datetime] | None = None,
                 interval: float = BEAT_SECONDS, pid: int | None = None, version: str | None = None):
        if mode not in MODES:
            raise ValueError("unknown collector mode")
        self.mode, self.sources, self.clock, self.interval = mode, list(sources), clock or _now, interval
        self.pid = pid or os.getpid()
        self.version = version if version is not None else code_version()
        self.started_at: str | None = None
        self.thread: threading.Thread | None = None
        self._stopping = threading.Event()

    def _doc(self, *, stopped: bool) -> dict:
        now = _utc(self.clock()).isoformat()
        if self.started_at is None:
            self.started_at = now
        return {"pid": self.pid, "started_at": self.started_at, "last_beat": now, "mode": self.mode,
                "sources": self.sources, "version": self.version, "stopped": stopped,
                "stopped_at": now if stopped else None}

    def _write(self, doc: dict) -> None:
        try:
            path().parent.mkdir(parents=True, exist_ok=True)
            cache._atomic_write_json(doc, path())
        except OSError as exc:  # a missed beat is logged; the collector keeps running
            log.warning("attention collector heartbeat not written: %s", type(exc).__name__)

    def beat(self) -> None:
        self._write(self._doc(stopped=False))

    def _loop(self) -> None:
        while not self._stopping.wait(self.interval):
            self.beat()

    def start(self) -> None:
        self.beat()
        self.thread = threading.Thread(target=self._loop, name=THREAD_NAME, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        """Stop beating and mark this process's heartbeat stopped (idempotent; never another process's file)."""
        self._stopping.set()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(STOP_JOIN_TIMEOUT_SECONDS)
        if self.started_at is None:
            return
        _found, doc = load()
        if doc is not None and doc["pid"] != self.pid:
            return
        if doc is not None and doc["stopped"]:
            return
        self._write(self._doc(stopped=True))
