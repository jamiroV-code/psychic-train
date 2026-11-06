"""Private B2 filesystem boundaries and bounded, non-reentrant state locking.

No network dependencies. Inspectors are injectable dependencies for synthetic ACL
coverage; production always uses the native inspector and never repairs permissions.
"""
from __future__ import annotations

import contextlib
import ctypes
import json
import os
import stat
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from api.data.attention.x_proxy import ProxyFailure, require

MODIFY = 0x1301BF
READ_EXECUTE = 0x1200A9
READ = 0x120089
DANGEROUS = 0x40000000 | 0x10000000 | 0x000D0156
KNOWN = 0x001F01FF | 0xF0000000
SYSTEM = "S-1-5-18"
ADMINS = "S-1-5-32-544"
_local = threading.local()


@dataclass(frozen=True)
class Ace:
    sid: str
    rights: int
    inherited: bool = False
    kind: int = 0


@dataclass(frozen=True)
class Acl:
    owner: str
    protected: bool
    aces: tuple[Ace, ...]


def inspect_windows_acl(path: Path | None = None, *, handle=None) -> Acl:
    """Read SID-based native DACL, refusing unsupported ACE representations."""
    require(os.name == "nt", "proxy_private")
    from ctypes import wintypes as w
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    adv.GetNamedSecurityInfoW.argtypes = [w.LPWSTR, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    adv.GetNamedSecurityInfoW.restype = w.DWORD
    adv.GetSecurityInfo.argtypes = [w.HANDLE, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    adv.GetSecurityInfo.restype = w.DWORD
    adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.LPWSTR)]
    adv.ConvertSidToStringSidW.restype = w.BOOL
    adv.GetSecurityDescriptorControl.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.WORD), ctypes.POINTER(w.DWORD)]
    adv.GetSecurityDescriptorControl.restype = w.BOOL
    adv.GetAce.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    adv.GetAce.restype = w.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    def sid_text(pointer):
        text = w.LPWSTR()
        require(bool(adv.ConvertSidToStringSidW(pointer, ctypes.byref(text))), "proxy_private")
        try:
            return text.value
        finally:
            kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))
    owner, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    if handle is None:
        result = adv.GetNamedSecurityInfoW(str(path), 1, 0x00000001 | 0x00000004, ctypes.byref(owner), None, ctypes.byref(dacl), None, ctypes.byref(descriptor))
    else:
        result = adv.GetSecurityInfo(handle, 1, 0x00000001 | 0x00000004, ctypes.byref(owner), None, ctypes.byref(dacl), None, ctypes.byref(descriptor))
    require(result == 0, "proxy_private")
    try:
        require(bool(owner.value) and bool(dacl.value), "proxy_private")
        control, revision = w.WORD(), w.DWORD()
        require(bool(adv.GetSecurityDescriptorControl(descriptor, ctypes.byref(control), ctypes.byref(revision))), "proxy_private")
        class ACL_HEADER(ctypes.Structure):
            _fields_ = [("revision", ctypes.c_ubyte), ("sbz1", ctypes.c_ubyte), ("size", w.WORD), ("count", w.WORD), ("sbz2", w.WORD)]
        header = ctypes.cast(dacl, ctypes.POINTER(ACL_HEADER)).contents
        require(header.revision in (2, 4) and header.count <= 4096, "proxy_private")
        aces = []
        for index in range(header.count):
            pointer = ctypes.c_void_p()
            require(bool(adv.GetAce(dacl, index, ctypes.byref(pointer))), "proxy_private")
            head = ctypes.string_at(pointer, 4)
            kind, flags, size = head[0], head[1], int.from_bytes(head[2:4], "little")
            require(kind == 0 and size >= 20 and flags & ~0x1F == 0, "proxy_private")
            rights = ctypes.c_uint32.from_address(pointer.value + 4).value
            aces.append(Ace(sid_text(ctypes.c_void_p(pointer.value + 8)), rights, bool(flags & 0x10), kind))
        return Acl(sid_text(owner), bool(control.value & 0x1000), tuple(aces))
    finally:
        kernel.LocalFree(descriptor)


def actual_service_sid() -> str:
    """Resolve the process token user; never trust an environment identity string."""
    require(os.name == "nt", "proxy_private")
    from ctypes import wintypes as w
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    adv.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    adv.GetTokenInformation.argtypes = [w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.LPWSTR)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    token = w.HANDLE()
    require(bool(adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token))), "proxy_private")
    try:
        needed = w.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        require(0 < needed.value <= 65536, "proxy_private")
        buf = ctypes.create_string_buffer(needed.value)
        require(bool(adv.GetTokenInformation(token, 1, buf, needed.value, ctypes.byref(needed))), "proxy_private")
        sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p)).contents
        text = w.LPWSTR()
        require(bool(adv.ConvertSidToStringSidW(sid, ctypes.byref(text))), "proxy_private")
        try:
            return text.value
        finally:
            kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))
    finally:
        kernel.CloseHandle(token)


def validate_acl(acl: Acl, service_sid: str, *, directory: bool, ancestor: bool = False):
    if ancestor:
        require(acl.owner in (service_sid, SYSTEM, ADMINS), "proxy_private")
        for ace in acl.aces:
            require(ace.kind == 0 and ace.rights & ~KNOWN == 0, "proxy_private")
            if ace.sid not in (SYSTEM, ADMINS):
                require(ace.rights & DANGEROUS == 0, "proxy_private")
        return
    require(acl.owner == service_sid and acl.protected, "proxy_private")
    expected = {service_sid: MODIFY, SYSTEM: READ_EXECUTE if directory else READ}
    require(len(acl.aces) == 2, "proxy_private")
    seen = set()
    for ace in acl.aces:
        require(ace.kind == 0 and not ace.inherited and ace.sid in expected and ace.sid not in seen
                and ace.rights == expected[ace.sid], "proxy_private")
        seen.add(ace.sid)


def verify_private(path: Path, root: Path, *, repo_root: Path, service_sid: str,
                   inspector=inspect_windows_acl, service_identity=actual_service_sid,
                   platform: str = os.name, uid=None, stat_inspector=None):
    require(path.is_absolute() and root.is_absolute() and ".." not in path.parts
            and (path == root or root in path.parents), "proxy_private")
    require(repo_root != path and repo_root not in path.parents, "proxy_private")
    try:
        for item in (path, *path.parents):
            info = stat_inspector(item) if stat_inspector is not None else item.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "proxy_private")
            if platform == "nt":
                if item == root or root in item.parents:
                    validate_acl(inspector(item), service_sid, directory=stat.S_ISDIR(info.st_mode))
                else:
                    validate_acl(inspector(item), service_sid, directory=True, ancestor=True)
            elif item == root or root in item.parents:
                require(info.st_uid == (os.getuid() if uid is None else uid)
                        and info.st_mode & 0o077 == 0, "proxy_private")
            else:
                # Sticky world-writable temporary roots are not private production ancestors.
                require(info.st_mode & 0o022 == 0, "proxy_private")
        if platform == "nt":
            require(service_identity() == service_sid, "proxy_private")
    except OSError:
        raise ProxyFailure("proxy_private") from None


def read_bounded(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        require(len(data) <= limit, "proxy_private")
        return data
    except OSError:
        raise ProxyFailure("proxy_private") from None


def verified_open(path: Path, root: Path, *, repo_root: Path, service_sid: str):
    """Pin immutable input bytes: no writer or replacement may share the handle."""
    return _verified_open(path, root, repo_root=repo_root, service_sid=service_sid, share_write=False)


def verified_database_open(path: Path, root: Path, *, repo_root: Path, service_sid: str):
    """Inspect live SQLite files while allowing its writer, but never replacement."""
    return _verified_open(path, root, repo_root=repo_root, service_sid=service_sid, share_write=True)


@contextlib.contextmanager
def _verified_open(path: Path, root: Path, *, repo_root: Path, service_sid: str, share_write: bool):
    verify_private(path, root, repo_root=repo_root, service_sid=service_sid)
    stream = None
    try:
        if os.name == "nt":
            from ctypes import wintypes as w
            import msvcrt
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
            kernel.CreateFileW.restype = w.HANDLE
            handle = kernel.CreateFileW(str(path), 0x80020080, 3 if share_write else 1, None, 3, 0x00200000, None)
            require(handle not in (None, ctypes.c_void_p(-1).value), "proxy_private")
            try:
                validate_acl(inspect_windows_acl(handle=handle), service_sid, directory=False)
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            except BaseException:
                kernel.CloseHandle.argtypes = [w.HANDLE]
                kernel.CloseHandle(handle)
                raise
        else:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        stream = os.fdopen(fd, "rb")
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "proxy_private")
        if os.name == "posix":
            require(info.st_uid == os.getuid() and info.st_mode & 0o077 == 0, "proxy_private")
        # Containment was checked component-by-component without following links.
        require(path.resolve(strict=True) == path.absolute(), "proxy_private")
        current = path.lstat()
        require((info.st_dev, info.st_ino) == (current.st_dev, current.st_ino), "proxy_private")
        yield stream
    except OSError:
        raise ProxyFailure("proxy_private") from None
    finally:
        if stream is not None:
            stream.close()


def handle_bytes(stream, limit: int) -> bytes:
    require(os.fstat(stream.fileno()).st_size <= limit, "proxy_private")
    data = stream.read(limit + 1)
    require(len(data) <= limit, "proxy_private")
    return data


def _windows_create(path: Path, service_sid: str, *, directory: bool):
    """Create a NEW object with its final protected DACL; never repair an old ACL."""
    from ctypes import wintypes as w
    import msvcrt
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [w.LPCWSTR, w.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = w.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    descriptor = ctypes.c_void_p()
    system_rights = READ_EXECUTE if directory else READ
    sddl = f"O:{service_sid}D:P(A;;0x{MODIFY:x};;;{service_sid})(A;;0x{system_rights:x};;;SY)"
    require(bool(adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None)), "proxy_private")
    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("length", w.DWORD), ("descriptor", ctypes.c_void_p), ("inherit", w.BOOL)]
    attrs = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
    try:
        if directory:
            kernel.CreateDirectoryW.argtypes = [w.LPCWSTR, ctypes.POINTER(SecurityAttributes)]
            require(bool(kernel.CreateDirectoryW(str(path), ctypes.byref(attrs))), "proxy_private")
            return None
        kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.POINTER(SecurityAttributes), w.DWORD, w.DWORD, w.HANDLE]
        kernel.CreateFileW.restype = w.HANDLE
        handle = kernel.CreateFileW(str(path), 0x40020000, 0, ctypes.byref(attrs), 1, 0x80, None)
        require(handle not in (None, ctypes.c_void_p(-1).value), "proxy_private")
        try:
            return msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle.argtypes = [w.HANDLE]
            kernel.CloseHandle(handle)
            raise
    finally:
        kernel.LocalFree(descriptor)


def secure_directory(path: Path, *, service_sid: str):
    if not path.exists():
        secure_directory(path.parent, service_sid=service_sid)
        if os.name == "nt":
            _windows_create(path, service_sid, directory=True)
        else:
            path.mkdir(mode=0o700)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400, "proxy_private")
    if os.name == "nt":
        validate_acl(inspect_windows_acl(path), service_sid, directory=True)
    else:
        require(info.st_uid == os.getuid() and info.st_mode & 0o077 == 0, "proxy_private")


def atomic_bytes(path: Path, data: bytes, *, service_sid: str | None = None):
    if service_sid is None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    else:
        secure_directory(path.parent, service_sid=service_sid)
    temporary = path.with_name("." + path.name + "." + str(uuid4()))
    try:
        fd = (_windows_create(temporary, service_sid, directory=False)
              if os.name == "nt" and service_sid is not None else
              os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    except OSError:
        raise ProxyFailure("proxy_private") from None
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, value, *, service_sid: str | None = None):
    atomic_bytes(path, json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"), service_sid=service_sid)


@contextlib.contextmanager
def state_lock(state_path: Path, *, timeout: float = 5.0):
    """Exclusive OS lock, bounded and explicitly non-reentrant in each thread."""
    key = str(state_path.absolute())
    owned = getattr(_local, "owned", set())
    require(key not in owned, "proxy_lock")
    lock_path = Path(str(state_path) + ".proxy-provider-budget.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    stream = None
    acquired = False
    deadline = time.monotonic() + timeout
    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        stream = os.fdopen(fd, "r+b", buffering=0)
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"0")
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                elif os.name == "posix":
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    raise ProxyFailure("proxy_lock")
                acquired = True
                break
            except (OSError, BlockingIOError):
                require(time.monotonic() < deadline, "proxy_lock")
                time.sleep(min(0.025, max(0, deadline - time.monotonic())))
        _local.owned = owned | {key}
        yield key
    except OSError:
        raise ProxyFailure("proxy_lock") from None
    finally:
        if acquired:
            _local.owned = owned
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            finally:
                stream.close()
        elif stream is not None:
            stream.close()
