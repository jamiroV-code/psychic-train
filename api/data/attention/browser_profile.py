"""A10-A12: private browser trees; BP3a creation and BP3c enumerated exceptions.

No ACL repair. Owner-session access remains trusted. Owner decisions default off.
Native ACL flags are retained: the B2 file projection cannot prove tree inheritance.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from api.data.attention.x_proxy_private import actual_service_sid, atomic_json

OI, CI, IO, INHERITED_ACE = 1, 2, 8, 16
FULL_ACCESS = 0x1F01FF
CE1_OBJECT_MASK, CE1_INHERIT_MASK = 0x1301BF, 0xE0010000
SYSTEM, EVERYONE = "S-1-5-18", "S-1-1-0"
CE1_CAPABILITY = "lpacEdgeStableNetworkSandbox"
PROFILE_RECORD = "profile_record.json"
CREATOR_VERSION = 3
_NAME = re.compile(r"[a-z0-9_]{1,24}\Z")
_EXT = re.compile(r"[a-p]{32}\Z")


class ProfileFailure(RuntimeError):
    def __init__(self, reason="profile_acl_unverified"):
        self.reason = reason
        super().__init__(reason)


def _require(ok, reason="profile_acl_unverified"):
    if not ok:
        raise ProfileFailure(reason)


@dataclass(frozen=True)
class NativeAce:
    sid: str
    rights: int
    flags: int
    kind: int = 0


@dataclass(frozen=True)
class NativeAcl:
    owner: str
    protected: bool
    aces: tuple[NativeAce, ...]


@dataclass(frozen=True)
class ProfilePolicy:
    ce1_approved: bool = False
    ce2_approved: bool = False


# Owner decisions 07-11-26: O-1 (CE-1) and O-1b (CE-2) ACCEPTED; recorded in the finish STATUS doc.
OWNER_DECISIONS = ProfilePolicy(ce1_approved=True, ce2_approved=True)


def token_sid():
    try:
        return actual_service_sid() if os.name == "nt" else str(os.getuid())
    except Exception:
        raise ProfileFailure() from None


def _native():
    from ctypes import wintypes as w
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.LPWSTR)]
    adv.ConvertSidToStringSidW.restype = w.BOOL
    return w, adv, kernel


def _sid_text(pointer, w, adv, kernel):
    text = w.LPWSTR()
    _require(adv.ConvertSidToStringSidW(pointer, ctypes.byref(text)))
    try:
        return text.value
    finally:
        kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))


def derive_capability_sid(name=CE1_CAPABILITY):
    """Derive, never infer the allowed SID from an observed ACL."""
    w, adv, kernel = _native()
    base = ctypes.WinDLL("kernelbase", use_last_error=True)
    fn = base.DeriveCapabilitySidsFromName
    array = ctypes.POINTER(ctypes.c_void_p)
    fn.argtypes = [w.LPCWSTR, ctypes.POINTER(array), ctypes.POINTER(w.DWORD),
                   ctypes.POINTER(array), ctypes.POINTER(w.DWORD)]
    fn.restype = w.BOOL
    groups, caps = array(), array()
    ng, nc = w.DWORD(), w.DWORD()
    result = fn(name, ctypes.byref(groups), ctypes.byref(ng), ctypes.byref(caps), ctypes.byref(nc))
    try:
        _require(bool(result) and nc.value == 1, "profile_policy_unsatisfied")
        return _sid_text(caps[0], w, adv, kernel)
    finally:
        for items, count in ((groups, ng.value), (caps, nc.value)):
            if items:
                for i in range(count):
                    kernel.LocalFree(items[i])
                kernel.LocalFree(items)


def inspect_native_acl(path):
    w, adv, kernel = _native()
    adv.GetNamedSecurityInfoW.argtypes = [w.LPWSTR, w.DWORD, w.DWORD,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    adv.GetNamedSecurityInfoW.restype = w.DWORD
    adv.GetSecurityDescriptorControl.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.WORD), ctypes.POINTER(w.DWORD)]
    adv.GetAce.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    owner, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    _require(adv.GetNamedSecurityInfoW(str(path), 1, 5, ctypes.byref(owner), None,
                                      ctypes.byref(dacl), None, ctypes.byref(descriptor)) == 0)
    try:
        _require(owner.value and dacl.value)
        control, rev = w.WORD(), w.DWORD()
        _require(adv.GetSecurityDescriptorControl(descriptor, ctypes.byref(control), ctypes.byref(rev)))
        header = ctypes.string_at(dacl, 8)
        count = int.from_bytes(header[4:6], "little")
        _require(header[0] in (2, 4) and count <= 4096)
        aces = []
        for i in range(count):
            pointer = ctypes.c_void_p()
            _require(adv.GetAce(dacl, i, ctypes.byref(pointer)))
            head = ctypes.string_at(pointer, 8)
            _require(head[0] in (0, 1) and int.from_bytes(head[2:4], "little") >= 20 and head[1] & ~31 == 0)
            aces.append(NativeAce(_sid_text(pointer.value + 8, w, adv, kernel),
                                  int.from_bytes(head[4:8], "little"), head[1], head[0]))
        return NativeAcl(_sid_text(owner, w, adv, kernel), bool(control.value & 0x1000), tuple(aces))
    finally:
        kernel.LocalFree(descriptor)


def secure_create(path, owner_sid):
    """Create with the final inheritable descriptor, not mkdir followed by repair."""
    if os.name != "nt":
        path.mkdir(mode=0o700)
        return
    w, adv, kernel = _native()
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [w.LPCWSTR, w.DWORD,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    descriptor = ctypes.c_void_p()
    _require(adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        f"O:{owner_sid}D:P(A;OICI;FA;;;{owner_sid})", 1, ctypes.byref(descriptor), None))
    class SA(ctypes.Structure):
        _fields_ = [("length", w.DWORD), ("descriptor", ctypes.c_void_p), ("inherit", w.BOOL)]
    attrs = SA(ctypes.sizeof(SA), descriptor, False)
    kernel.CreateDirectoryW.argtypes = [w.LPCWSTR, ctypes.POINTER(SA)]
    try:
        _require(kernel.CreateDirectoryW(str(path), ctypes.byref(attrs)))
    finally:
        kernel.LocalFree(descriptor)


def root_identity(path):
    info = path.stat()
    return hashlib.sha256(f"{info.st_dev}:{info.st_ino}".encode("ascii")).hexdigest()


def _parts(rel):
    return tuple(rel.casefold().replace("\\", "/").split("/"))


def _anchor(parts):
    prefix = ("default",)
    if len(parts) >= 6 and parts[:3] == ("default", "storage", "ext") and _EXT.fullmatch(parts[3]) and parts[4] == "def":
        prefix = parts[:5]
    n = len(prefix)
    if parts[:n] == prefix and len(parts) > n and parts[n] in ("network", "cache", "shared dictionary"):
        return n + 1
    return None


def _leveldb_file(parts):
    return (len(parts) > 3 and parts[:3] == ("default", "local storage", "leveldb")
            or len(parts) > 2 and parts[:2] == ("default", "session storage")
            or len(parts) > 7 and parts[:3] == ("default", "storage", "ext") and _EXT.fullmatch(parts[3])
            and parts[4:7] == ("def", "local storage", "leveldb")
            or len(parts) > 6 and parts[:3] == ("default", "storage", "ext") and _EXT.fullmatch(parts[3])
            and parts[4:6] == ("def", "session storage"))


def validate_acl(acl, *, owner_sid, ce1_sid, policy, rel, directory, root=False):
    _require(acl.owner == owner_sid and bool(acl.aces))
    own, cap, world = [], [], []
    for ace in acl.aces:
        _require(ace.kind in (0, 1) and ace.flags & ~31 == 0)
        if ace.sid in (owner_sid, SYSTEM):
            _require(ace.kind == 0)
            own.append(ace)
            _require(ace.rights == FULL_ACCESS)
            _require(ace.flags == (OI | CI if root else INHERITED_ACE | (OI | CI if directory else 0)))
        elif ace.sid == ce1_sid:
            _require(ace.kind == 0)
            cap.append(ace)
        elif ace.sid == EVERYONE:
            # Edge 157 writes Everyone as a DENY (execute, mask 32) on LevelDB files (re-probe 09-11-26):
            # a deny only removes access. An Everyone ALLOW is never accepted.
            _require(ace.kind == 1)
            world.append(ace)
        else:
            raise ProfileFailure()
    _require(any(a.sid == owner_sid for a in own) and len({a.sid for a in own}) == len(own))
    if root:
        _require(acl.protected and not cap and not world)
    parts = _parts(rel)
    if cap:
        _require(policy.ce1_approved, "profile_policy_unsatisfied")
        anchor = _anchor(parts)
        _require(anchor is not None)
        if len(parts) == anchor:
            _require(directory)
            expected = {(CE1_OBJECT_MASK, 0), (CE1_INHERIT_MASK, OI | CI | IO)}
        else:
            expected = {(CE1_OBJECT_MASK, INHERITED_ACE)}
            if directory:
                expected.add((CE1_INHERIT_MASK, INHERITED_ACE | OI | CI | IO))
        _require(len(cap) == len(expected) and {(a.rights, a.flags) for a in cap} == expected)
    if world:
        _require(policy.ce2_approved, "profile_policy_unsatisfied")
        _require(not directory and _leveldb_file(parts) and len(world) == 1
                 and world[0].rights == 32 and world[0].flags == 0 and world[0].kind == 1)
    return bool(cap), bool(world)


class ProfileStore:
    def __init__(self, root, *, cache_root, owner_sid=None, policy=OWNER_DECISIONS,
                 ce1_sid=None, inspector=inspect_native_acl, max_entries=20000, max_depth=12):
        self.root, self.cache_root = Path(root), Path(cache_root)
        self.owner_sid = token_sid() if owner_sid is None else owner_sid
        self.policy = policy
        self.ce1_sid = (derive_capability_sid() if os.name == "nt" else "") if ce1_sid is None else ce1_sid
        self._derive_each_session = ce1_sid is None and os.name == "nt"
        self.inspector = inspector
        self.max_entries, self.max_depth = min(max_entries, 20000), min(max_depth, 12)

    def _pin(self, label):
        _require(isinstance(label, str) and _NAME.fullmatch(label))
        return self.cache_root / "attention" / "_pc_state" / "profile_records" / (label + ".json")

    def _load(self, path):
        _require(path.stat().st_size <= 1024 * 1024)
        obj = json.loads(path.read_bytes())
        _require(isinstance(obj, dict))
        return obj

    def _check(self, path, rel, *, root=False):
        info = path.lstat()
        _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
                 and (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)))
        if os.name != "nt":
            _require(info.st_uid == os.getuid() and info.st_mode & 0o077 == 0)
            return False, False
        return validate_acl(self.inspector(path), owner_sid=self.owner_sid, ce1_sid=self.ce1_sid,
                            policy=self.policy, rel=rel, directory=stat.S_ISDIR(info.st_mode), root=root)

    def _scan(self, path):
        self._check(self.root, "", root=True)
        self._check(path, "", root=True)
        stack, count, cap, world, present = [(path, 0)], 0, False, [], set()
        cap_paths = set()
        while stack:
            parent, depth = stack.pop()
            with os.scandir(parent) as entries:
                for entry in entries:
                    count += 1
                    _require(count <= self.max_entries and depth + 1 <= self.max_depth)
                    child = Path(entry.path)
                    rel = child.relative_to(path).as_posix().casefold()
                    has_cap, has_world = self._check(child, rel)
                    cap |= has_cap
                    if has_cap:
                        cap_paths.add(rel)
                    if has_world:
                        world.append(rel)
                    present.add(rel)
                    if entry.is_dir(follow_symlinks=False):
                        stack.append((child, depth + 1))
        for rel in cap_paths:
            parts = _parts(rel)
            anchor = _anchor(parts)
            _require("/".join(parts[:anchor]) in cap_paths)
        return cap, sorted(world), present

    def prepare(self, label, name):
        try:
            _require(isinstance(name, str) and _NAME.fullmatch(name) and self.root.is_absolute())
            if self._derive_each_session:
                self.ce1_sid = derive_capability_sid()
            repo = Path(__file__).resolve().parents[3]
            resolved = self.root.resolve()
            _require(resolved != repo and repo not in resolved.parents)
            pin_path = self._pin(label)
            if not self.root.exists():
                secure_create(self.root, self.owner_sid)
            self._check(self.root, "", root=True)
            path = self.root / name
            _require(os.path.normcase(os.path.realpath(self.root)) == os.path.normcase(str(self.root)))
            _require(os.path.normcase(os.path.realpath(path)) == os.path.normcase(str(path)))
            if not path.exists():
                secure_create(path, self.owner_sid)
                atomic_json(path / PROFILE_RECORD, {"schema": 1, "creator_version": CREATOR_VERSION,
                                                    "root_identity": root_identity(path), "label": label})
            cap, world, _ = self._scan(path)
            record = self._load(path / PROFILE_RECORD)
            _require(record.get("schema") == 1 and record.get("creator_version") == CREATOR_VERSION
                     and record.get("root_identity") == root_identity(path) and record.get("label") == label)
            pin = self._load(pin_path) if pin_path.exists() else None
            if pin:
                _require(not pin.get("drift"), "profile_acl_drift")
                _require(pin.get("root_identity") == root_identity(path)
                         and pin.get("ce1_sid") in (None, self.ce1_sid))
            if cap or world:
                _require(pin is not None and pin.get("ce1_sid") == (self.ce1_sid if cap else None)
                         and pin.get("ce2_locations") == world)
            return path
        except ProfileFailure:
            raise
        except Exception:
            raise ProfileFailure() from None

    def sweep(self, label, path):
        pin_path = self._pin(label)
        try:
            cap, world, present = self._scan(path)
            atomic_json(pin_path, {"schema": 1, "root_identity": root_identity(path), "drift": False,
                                  "ce1_sid": self.ce1_sid if cap else None, "ce2_locations": world})
            sensitive = {"default/network", "default/network/cookies", "default/cache", "default/shared dictionary",
                         "local state", "default/preferences", "default/cookies", "default/local storage/leveldb",
                         "default/session storage", "default/storage/ext"}
            sensitive.update(p for p in present if "/" not in p or p.startswith("default/storage/ext/"))
            return {p: "present" if p in present else "absent" for p in sorted(sensitive)}
        except Exception:
            atomic_json(pin_path, {"schema": 1, "root_identity": root_identity(path), "drift": True})
            raise ProfileFailure("profile_acl_drift") from None
