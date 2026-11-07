"""Browser lifecycle: BP4 suspended/job launch, BP2 restricted pipes, A14 lock.

No browser is enabled by this module. Profile decisions and A19 admission both
fail closed. No argv, pipe frames, paths or exception details are logged.
"""
from __future__ import annotations

import contextlib
import ctypes
import hashlib
import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from api.data.attention import browser_profile as profiles
from api.data.attention.x_proxy_private import atomic_json

FRAME_LIMIT = 1048576
FEATURES = ("DnsOverHttps,AsyncDns,MediaRouter,DialMediaRouteProvider,CastMediaRouteProvider,"
            "GlobalMediaControls,msImplicitSignin,msEdgeAutoSignIn,msSingleSignOnOSForPrimaryAccountIsShared")
FIXED_FLAGS = (
    "--remote-debugging-pipe", "--proxy-bypass-list=<-loopback>",
    "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--disable-quic",
    "--webrtc-ip-handling-policy=disable_non_proxied_udp", "--media-router=0",
    "--disable-features=" + FEATURES, "--disable-extensions", "--disable-background-networking",
    "--disable-component-update", "--disable-sync", "--disable-domain-reliability",
    "--disable-breakpad", "--disable-client-side-phishing-detection", "--no-first-run",
    "--no-default-browser-check", "--safebrowsing-disable-auto-update", "--disable-reporting",
)
FLAG_DIGEST = hashlib.sha256(json.dumps(FIXED_FLAGS, separators=(",", ":")).encode()).hexdigest()
# Guard exemption: rejection vocabulary only, never emitted as launch flags.
REJECT_FLAGS = ("--remote-debugging-port", "--remote-allow-origins", "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-gpu-sandbox", "--disable-seccomp-filter-sandbox", "--enable-logging", "--log-net-log",
                "--trace-startup", "--v", "--vmodule", "--disable-web-security", "--ignore-certificate-errors")


class BrowserFailure(RuntimeError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def require(ok, reason="browser_launch_failed"):
    if not ok:
        raise BrowserFailure(reason)


def build_argv(binary, profile, relay_port, handles, *, headless=False):
    require(Path(binary).is_absolute() and Path(profile).is_absolute())
    require(type(relay_port) is int and 1 <= relay_port <= 65535, "proxy_not_admitted")
    argv = [str(binary), *FIXED_FLAGS, f"--user-data-dir={profile}",
            f"--proxy-server=http://127.0.0.1:{relay_port}",
            f"--remote-debugging-io-pipes={handles[0]},{handles[1]}"]
    if headless:
        argv.append("--headless=new")
    argv.append("about:blank")
    validate_argv(argv)
    return argv


def validate_argv(argv):
    keys = [a.split("=", 1)[0] for a in argv[1:] if a.startswith("--")]
    require(len(keys) == len(set(keys)), "browser_argv_invalid")
    require(not set(keys).intersection(REJECT_FLAGS), "browser_argv_invalid")
    require(all(flag in argv for flag in FIXED_FLAGS), "browser_argv_invalid")
    allowed = {a.split("=", 1)[0] for a in FIXED_FLAGS} | {
        "--user-data-dir", "--proxy-server", "--remote-debugging-io-pipes", "--headless"}
    require(set(keys) <= allowed, "browser_argv_invalid")


def _kernel():
    from ctypes import wintypes as w
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CloseHandle.argtypes = [w.HANDLE]
    k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    k.WaitForSingleObject.restype = w.DWORD
    return w, k


def executable_version(binary):
    require(Path(binary).is_absolute() and Path(binary).is_file(), "browser_unadmitted")
    if os.name != "nt":
        # Content identity is exact on platforms without PE version resources.
        with open(binary, "rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    from ctypes import wintypes as w
    v = ctypes.WinDLL("version", use_last_error=True)
    v.GetFileVersionInfoSizeW.argtypes = [w.LPCWSTR, ctypes.POINTER(w.DWORD)]
    v.GetFileVersionInfoW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p]
    v.VerQueryValueW.argtypes = [ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(w.UINT)]
    size = v.GetFileVersionInfoSizeW(str(binary), None)
    require(0 < size <= 1048576, "browser_unadmitted")
    data = ctypes.create_string_buffer(size)
    require(v.GetFileVersionInfoW(str(binary), 0, size, data), "browser_unadmitted")
    value, length = ctypes.c_void_p(), w.UINT()
    require(v.VerQueryValueW(data, "\\", ctypes.byref(value), ctypes.byref(length)) and length.value >= 16,
            "browser_unadmitted")
    words = ctypes.cast(value, ctypes.POINTER(w.DWORD))
    require(words[0] == 0xFEEF04BD, "browser_unadmitted")
    return ".".join(str(n) for n in (words[2] >> 16, words[2] & 65535, words[3] >> 16, words[3] & 65535))


def _digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def admission_digest(binary, version):
    return _digest((os.path.normcase(os.path.realpath(binary)), version, FLAG_DIGEST))


def residual_digest(binary, version, destination_classes):
    return _digest((os.path.normcase(os.path.realpath(binary)), version, FLAG_DIGEST, sorted(destination_classes)))


def write_admission(cache_root, binary, version, *, outcome, destination_classes):
    """A19 self-test writer; caller supplies its own observed classes, never config seeds."""
    require(outcome in {"tested_clean", "containment_residual_unaccepted", "accepted_residual", "contained"},
            "browser_unadmitted")
    require(isinstance(destination_classes, list) and all(isinstance(c, str) for c in destination_classes),
            "browser_unadmitted")
    digest = admission_digest(binary, version)
    path = Path(cache_root) / "attention" / "_probes" / f"browser_admission_{digest}.json"
    atomic_json(path, {"schema": 1, "digest": digest, "version": version, "flag_digest": FLAG_DIGEST,
                       "tested_at": datetime.now(timezone.utc).isoformat(), "outcome": outcome,
                       "destination_classes": sorted(set(destination_classes))})
    return digest


def read_admission(cache_root, binary, version):
    digest = admission_digest(binary, version)
    root = Path(cache_root) / "attention" / "_probes"
    try:
        path = root / f"browser_admission_{digest}.json"
        require(path.stat().st_size <= 16384, "browser_unadmitted")
        value = json.loads(path.read_bytes())
        require(value.get("schema") == 1 and value.get("digest") == digest and value.get("version") == version
                and value.get("flag_digest") == FLAG_DIGEST, "browser_unadmitted")
        classes, outcome = value["destination_classes"], value["outcome"]
        require(isinstance(classes, list) and all(isinstance(c, str) for c in classes), "browser_unadmitted")
        datetime.fromisoformat(value["tested_at"])
        if outcome in ("tested_clean", "contained"):
            require(not classes, "browser_unadmitted")
            return value
        require(outcome in ("containment_residual_unaccepted", "accepted_residual"), "browser_unadmitted")
        require(classes == ["vendor_cloud_443"], "containment_residual_unaccepted")
        acceptance = root / f"residual_acceptance_{residual_digest(binary, version, classes)}.json"
        require(acceptance.exists() and acceptance.stat().st_size <= 16384, "containment_residual_unaccepted")
        accepted = json.loads(acceptance.read_bytes())
        require(accepted.get("schema") == 1 and accepted.get("browser_version") == version
                and accepted.get("flag_digest") == FLAG_DIGEST
                and accepted.get("residual_kind") == "browser_process_direct_tcp"
                and accepted.get("destination_classes") == classes and accepted.get("accepted_utc"),
                "containment_residual_unaccepted")
        return dict(value, outcome="accepted_residual")
    except BrowserFailure:
        raise
    except Exception:
        raise BrowserFailure("browser_unadmitted") from None


_local_lock = threading.Lock()


class MachineLock:
    def __init__(self):
        self.handle = None
        self.owned = False
        self.wait_result = None

    def acquire(self):
        require(_local_lock.acquire(blocking=False), "browser_busy")
        self.owned = True
        try:
            if os.name == "nt":
                w, k = _kernel()
                k.CreateMutexW.argtypes = [ctypes.c_void_p, w.BOOL, w.LPCWSTR]
                k.CreateMutexW.restype = w.HANDLE
                name = "Global\\mysite-collector-browser-" + hashlib.sha256(profiles.token_sid().encode()).hexdigest()[:16]
                self.handle = k.CreateMutexW(None, False, name)
                require(self.handle, "browser_busy")
                self.wait_result = k.WaitForSingleObject(self.handle, 0)
                require(self.wait_result in (0, 128), "browser_busy")
            else:
                import fcntl
                path = Path.home() / ".my_site" / "locks" / "browser.lock"
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                self.handle = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.wait_result = 0
            return self
        except Exception:
            self.close()
            raise BrowserFailure("browser_busy") from None

    def close(self):
        if self.handle is not None:
            if os.name == "nt":
                w, k = _kernel()
                k.ReleaseMutex.argtypes = [w.HANDLE]
                if self.wait_result in (0, 128):
                    k.ReleaseMutex(self.handle)
                k.CloseHandle(self.handle)
            else:
                os.close(self.handle)
            self.handle = None
        if self.owned:
            self.owned = False
            _local_lock.release()

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *args):
        self.close()


@contextlib.contextmanager
def profile_lock(path):
    fd = os.open(path / ".browser.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if not os.fstat(fd).st_size:
            os.write(fd, b"0")
        os.lseek(fd, 0, 0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BrowserFailure("browser_busy") from None
        yield
    finally:
        os.close(fd)


def free_memory_mb():
    try:
        if os.name == "nt":
            w, k = _kernel()
            class Status(ctypes.Structure):
                _fields_ = [("length", w.DWORD), ("load", w.DWORD)] + [(n, ctypes.c_ulonglong) for n in (
                    "total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
            value = Status()
            value.length = ctypes.sizeof(value)
            require(k.GlobalMemoryStatusEx(ctypes.byref(value)), "low_memory")
            return value.available / 1048576
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1048576
    except Exception:
        return None


def process_creation(pid):
    w, k = _kernel()
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    handle = k.OpenProcess(0x1000 | 0x100000, False, pid)
    if not handle:
        return None
    try:
        if k.WaitForSingleObject(handle, 0) == 0:
            return None
        stamps = (ctypes.c_ulonglong * 4)()
        k.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.c_void_p] * 4
        require(k.GetProcessTimes(handle, *(ctypes.byref(stamps, i * 8) for i in range(4))))
        return stamps[0]
    finally:
        k.CloseHandle(handle)


def process_tree(root_pid):
    """Toolhelp ancestry plus creation time; unrelated/reused PIDs are excluded."""
    w, k = _kernel()
    class Entry(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD),
                    ("heap", ctypes.c_size_t), ("module", w.DWORD), ("threads", w.DWORD),
                    ("parent", w.DWORD), ("priority", ctypes.c_long), ("flags", w.DWORD),
                    ("exe", w.WCHAR * 260)]
    k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    k.CreateToolhelp32Snapshot.restype = w.HANDLE
    k.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    k.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    snapshot = k.CreateToolhelp32Snapshot(2, 0)
    require(snapshot not in (None, ctypes.c_void_p(-1).value))
    parents = {}
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        more = k.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            parents[entry.pid] = entry.parent
            more = k.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        k.CloseHandle(snapshot)
    root_created = process_creation(root_pid)
    if root_created is None:
        return {}
    owned = {root_pid: root_created}
    pending = [root_pid]
    while pending:
        parent = pending.pop()
        for pid, ppid in parents.items():
            if ppid == parent and pid not in owned:
                created = process_creation(pid)
                if created is not None and created >= owned[parent]:
                    owned[pid] = created
                    pending.append(pid)
        require(len(owned) <= 1024)
    return owned


def terminate_recorded(pid, creation):
    if process_creation(pid) != creation:
        return False
    owned = process_tree(pid)
    if owned.get(pid) != creation or process_creation(pid) != creation:
        return False
    for child, created in sorted(owned.items(), key=lambda item: item[1], reverse=True):
        _terminate_one(child, created)
    return True


def _terminate_one(pid, creation):
    """Re-open and compare the same handle before termination: PID reuse is not ownership."""
    w, k = _kernel()
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    handle = k.OpenProcess(0x1001 | 0x100000, False, pid)
    if not handle:
        return False
    try:
        stamps = (ctypes.c_ulonglong * 4)()
        k.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.c_void_p] * 4
        require(k.GetProcessTimes(handle, *(ctypes.byref(stamps, i * 8) for i in range(4))))
        if stamps[0] != creation:
            return False
        k.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
        require(k.TerminateProcess(handle, 1))
        k.WaitForSingleObject(handle, 5000)
        return True
    finally:
        k.CloseHandle(handle)


class PipeTransport:
    def __init__(self):
        self.read_fd, child_write = os.pipe()
        child_read, self.write_fd = os.pipe()
        self.child_fds = (child_read, child_write)
        self.buffer = bytearray()
        if os.name == "nt":
            import msvcrt
            self.child_handles = tuple(msvcrt.get_osfhandle(fd) for fd in self.child_fds)
        else:
            self.child_handles = self.child_fds
        self.closed = False

    def close_child(self):
        for fd in self.child_fds:
            os.close(fd)
        self.child_fds = ()

    def send(self, frame):
        require(isinstance(frame, bytes) and len(frame) <= FRAME_LIMIT, "cdp_frame_too_large")
        require(b"\0" not in frame and not self.closed, "cdp_pipe_unavailable")
        view = memoryview(frame + b"\0")
        try:
            while view:
                count = os.write(self.write_fd, view)
                require(count > 0, "cdp_pipe_unavailable")
                view = view[count:]
        except OSError:
            raise BrowserFailure("cdp_pipe_unavailable") from None

    def receive(self, *, timeout=10):
        deadline = time.monotonic() + timeout
        while True:
            index = self.buffer.find(0)
            if index >= 0:
                require(index <= FRAME_LIMIT, "cdp_frame_too_large")
                result = bytes(self.buffer[:index])
                del self.buffer[:index + 1]
                return result
            require(len(self.buffer) <= FRAME_LIMIT, "cdp_frame_too_large")
            require(time.monotonic() < deadline, "cdp_timeout")
            if os.name == "nt":
                import msvcrt
                w, k = _kernel()
                k.PeekNamedPipe.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.c_void_p,
                                           ctypes.POINTER(w.DWORD), ctypes.c_void_p]
                available = w.DWORD()
                require(k.PeekNamedPipe(msvcrt.get_osfhandle(self.read_fd), None, 0, None,
                                         ctypes.byref(available), None), "cdp_pipe_unavailable")
                ready = available.value
            else:
                import select
                ready = 65536 if select.select([self.read_fd], [], [], 0)[0] else 0
            if ready:
                chunk = os.read(self.read_fd, min(ready, 65536, FRAME_LIMIT + 1 - len(self.buffer)))
                require(chunk, "cdp_pipe_unavailable")
                self.buffer.extend(chunk)
            else:
                time.sleep(.005)

    def close(self):
        if not self.closed:
            self.closed = True
            self.close_child()
            os.close(self.read_fd)
            os.close(self.write_fd)
            self.buffer.clear()


def _quote(arg):
    # Windows CRT argv quoting, including backslashes immediately before quotes/end.
    result, slashes = '"', 0
    for char in arg:
        if char == "\\":
            slashes += 1
        else:
            result += "\\" * (slashes * 2 + 1 if char == '"' else slashes) + char
            slashes = 0
    return result + "\\" * (slashes * 2) + '"'


class NativeJob:
    def __init__(self, argv, pipe):
        w, k = _kernel()
        self.handle = self.process = None
        self.pid = None
        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong), ("flags", w.DWORD),
                        ("min", ctypes.c_size_t), ("max", ctypes.c_size_t), ("active", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", ctypes.c_ulonglong * 6), ("process_mem", ctypes.c_size_t),
                        ("job_mem", ctypes.c_size_t), ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]
        class Startup(ctypes.Structure):
            _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR), ("title", w.LPWSTR),
                        ("x", w.DWORD), ("y", w.DWORD), ("xs", w.DWORD), ("ys", w.DWORD),
                        ("xc", w.DWORD), ("yc", w.DWORD), ("fill", w.DWORD), ("flags", w.DWORD),
                        ("show", w.WORD), ("cbres", w.WORD), ("res", ctypes.c_void_p),
                        ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]
        class StartupEx(ctypes.Structure):
            _fields_ = [("startup", Startup), ("attrs", ctypes.c_void_p)]
        class ProcessInfo(ctypes.Structure):
            _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        k.CreateJobObjectW.restype = w.HANDLE
        k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        k.ResumeThread.argtypes = [w.HANDLE]
        k.ResumeThread.restype = w.DWORD
        k.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_size_t)]
        k.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.c_size_t, ctypes.c_void_p,
                                               ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
        k.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
        k.SetHandleInformation.argtypes = [w.HANDLE, w.DWORD, w.DWORD]
        k.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL,
            w.DWORD, ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(StartupEx), ctypes.POINTER(ProcessInfo)]
        attributes = None
        info = ProcessInfo()
        try:
            self.handle = k.CreateJobObjectW(None, None)
            require(self.handle)
            limits = Extended()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
            require(k.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
            needed = ctypes.c_size_t()
            k.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(needed))
            attributes = ctypes.create_string_buffer(needed.value)
            require(k.InitializeProcThreadAttributeList(attributes, 1, 0, ctypes.byref(needed)))
            handles = (w.HANDLE * 2)(*pipe.child_handles)
            for handle in handles:
                require(k.SetHandleInformation(handle, 1, 1))
            require(k.UpdateProcThreadAttribute(attributes, 0, 0x20002, handles, ctypes.sizeof(handles), None, None))
            startup = StartupEx()
            startup.startup.cb = ctypes.sizeof(startup)
            startup.attrs = ctypes.cast(attributes, ctypes.c_void_p)
            command = ctypes.create_unicode_buffer(" ".join(_quote(a) for a in argv))
            # Explicit application and restricted HANDLE_LIST; no inherited stdio or job handle.
            require(k.CreateProcessW(argv[0], command, None, None, True, 0x80000 | 4 | 0x08000000,
                                      None, None, ctypes.byref(startup), ctypes.byref(info)))
            self.process, self.pid = info.process, info.pid
            require(k.AssignProcessToJobObject(self.handle, self.process))
            require(k.ResumeThread(info.thread) != 0xFFFFFFFF)
        except Exception:
            if info.process:
                k.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
                k.TerminateProcess(info.process, 1)
            self.close()
            raise BrowserFailure("browser_launch_failed") from None
        finally:
            if info.thread:
                k.CloseHandle(info.thread)
            if attributes is not None:
                k.DeleteProcThreadAttributeList(attributes)
            for handle in pipe.child_handles:
                k.SetHandleInformation(handle, 1, 0)
            pipe.close_child()

    def pids(self):
        w, k = _kernel()
        k.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
        buf = ctypes.create_string_buffer(8 + ctypes.sizeof(ctypes.c_size_t) * 1024)
        require(k.QueryInformationJobObject(self.handle, 3, buf, len(buf), None), "browser_rss_unreadable")
        count = int.from_bytes(buf.raw[4:8], "little")
        require(count <= 1024, "browser_rss_unreadable")
        return list((ctypes.c_size_t * count).from_buffer(buf, 8))

    def close(self):
        w, k = _kernel()
        if self.handle:
            k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
            k.TerminateJobObject(self.handle, 1)
            k.CloseHandle(self.handle)
            self.handle = None
        if self.process:
            k.WaitForSingleObject(self.process, 5000)
            k.CloseHandle(self.process)
            self.process = None


def tree_rss_mb(job):
    w, k = _kernel()
    ps = ctypes.WinDLL("psapi", use_last_error=True)
    class Counters(ctypes.Structure):
        _fields_ = [("cb", w.DWORD), ("faults", w.DWORD)] + [(n, ctypes.c_size_t) for n in (
            "peak", "working", "quota_peak_paged", "quota_paged", "quota_peak_nonpaged", "quota_nonpaged", "pagefile", "peak_pagefile")]
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    ps.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Counters), w.DWORD]
    total = 0
    for pid in job.pids():
        handle = k.OpenProcess(0x410, False, pid)
        require(handle, "browser_rss_unreadable")
        try:
            value = Counters()
            value.cb = ctypes.sizeof(value)
            require(ps.GetProcessMemoryInfo(handle, ctypes.byref(value), value.cb), "browser_rss_unreadable")
            total += value.working
        finally:
            k.CloseHandle(handle)
    return total / 1048576


class BrowserSession:
    def __init__(self, host, label, profile, stack, pipe, job, record):
        self.host, self.label, self.profile = host, label, profile
        self.stack, self.pipe, self.job, self.record = stack, pipe, job, record
        self.pid = job.pid
        self.started = time.monotonic()
        self.closed = False
        self.failure = None
        self._guard = threading.Lock()
        self._stop = threading.Event()
        self._watcher = threading.Thread(target=self._watch, name="collector-browser-budget", daemon=True)
        self._watcher.start()

    def _watch(self):
        while not self._stop.wait(min(.25, self.host.timeout)):
            try:
                self.check()
            except BrowserFailure:
                return

    def check(self):
        with self._guard:
            if self.failure:
                raise BrowserFailure(self.failure)
            require(not self.closed, "cdp_pipe_unavailable")
            try:
                require(time.monotonic() - self.started < self.host.timeout, "browser_timeout")
                rss = self.host.rss(self.job)
                require(isinstance(rss, (int, float)) and math.isfinite(rss) and rss >= 0, "browser_rss_unreadable")
                require(rss <= self.host.rss_ceiling, "browser_rss_exceeded")
            except Exception as exc:
                self.failure = exc.reason if isinstance(exc, BrowserFailure) else "browser_rss_unreadable"
                self.job.close()
                raise BrowserFailure(self.failure) from None

    def close(self):
        if self.closed:
            return
        self.closed = True
        self._stop.set()
        self._watcher.join()
        try:
            self.pipe.close()
            self.job.close()
            self.host.profiles.sweep(self.label, self.profile)
            self.record.unlink(missing_ok=True)
        finally:
            self.stack.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class BrowserHost:
    def __init__(self, binary, profiles_dir, *, cache_root, policy=profiles.OWNER_DECISIONS,
                 spawn=None, memory=free_memory_mb, rss=tree_rss_mb, memory_floor=1536,
                 rss_ceiling=1200, timeout=180, acl_inspector=profiles.inspect_native_acl):
        self.binary, self.cache_root = Path(binary), Path(cache_root)
        self.policy, self.spawn = policy, spawn
        self.memory, self.rss = memory, rss
        self.memory_floor, self.rss_ceiling, self.timeout = memory_floor, rss_ceiling, timeout
        require(0 < timeout <= 300 and memory_floor >= 512 and rss_ceiling >= 400)
        self.profiles = profiles.ProfileStore(profiles_dir, cache_root=cache_root, policy=policy, inspector=acl_inspector)

    def launch(self, label, profile_name, relay_port, *, headless=False):
        return self._launch(label, profile_name, relay_port, headless=headless, admission_run=False)

    def _launch(self, label, profile_name, relay_port, *, headless=False, admission_run):
        # admission_run=True is passed ONLY by browser_selftest (A19, guard-tested): the
        # self-test produces the admission record, so it cannot require one.
        require(self.policy.ce1_approved and self.policy.ce2_approved, "profile_policy_unsatisfied")
        # Only the probed Stable channel is admitted. Constructor spawn is the test seam.
        if self.spawn is None:
            normal = str(self.binary).replace("\\", "/").casefold()
            require(normal.endswith("/microsoft/edge/application/msedge.exe"), "profile_policy_unsatisfied")
        version = executable_version(self.binary)
        if admission_run is not True:
            read_admission(self.cache_root, self.binary, version)
        try:
            memory = self.memory()
        except Exception:
            memory = None
        require(isinstance(memory, (int, float)) and math.isfinite(memory) and memory >= self.memory_floor, "low_memory")
        stack = contextlib.ExitStack()
        pipe = job = None
        try:
            stack.enter_context(MachineLock())
            profile = self.profiles.prepare(label, profile_name)
            stack.enter_context(profile_lock(profile))
            record = self.cache_root / "attention" / "_pc_state" / "browser_launches" / (label + ".json")
            if record.exists():
                require(record.stat().st_size <= 4096)
                previous = json.loads(record.read_bytes())
                require(previous.get("root_identity") == profiles.root_identity(profile))
                terminate_recorded(previous["pid"], previous["creation"])
            pipe = PipeTransport()
            argv = build_argv(self.binary, profile, relay_port, pipe.child_handles, headless=headless)
            command = self.spawn(argv) if self.spawn else argv
            job = NativeJob(command, pipe)
            atomic_json(record, {"schema": 1, "pid": job.pid, "creation": process_creation(job.pid),
                                 "root_identity": profiles.root_identity(profile), "version": version})
            return BrowserSession(self, label, profile, stack, pipe, job, record)
        except Exception:
            if job:
                job.close()
            if pipe:
                pipe.close()
            stack.close()
            raise
