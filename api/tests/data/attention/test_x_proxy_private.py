"""B2 E2/E6 synthetic SID/ACE snapshots and real temporary OS locks.

These do NOT probe or alter deployment permissions. Native deployment ACL evidence
remains a separate manual release gate.
"""
from __future__ import annotations

import os
import stat
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.data.attention import x_proxy as p
from api.data.attention import x_proxy_private as private

SERVICE = "S-1-5-21-1-2-3-1001"
OTHER = "S-1-5-32-545"


def good(directory=True):
    return private.Acl(SERVICE, True, (private.Ace(SERVICE, private.MODIFY),
        private.Ace(private.SYSTEM, private.READ_EXECUTE if directory else private.READ)))


def test_exact_private_root_and_file_acl_snapshots_pass():
    private.validate_acl(good(), SERVICE, directory=True)
    private.validate_acl(good(False), SERVICE, directory=False)


@pytest.mark.parametrize("acl", [replace(good(), owner=OTHER), replace(good(), protected=False),
    replace(good(), aces=(private.Ace(SERVICE, private.MODIFY, inherited=True), good().aces[1])),
    replace(good(), aces=(private.Ace(SERVICE, private.MODIFY, kind=1), good().aces[1])),
    replace(good(), aces=(private.Ace(SERVICE, private.MODIFY, kind=9), good().aces[1])),
    replace(good(), aces=(private.Ace(SERVICE, private.READ), good().aces[1])),
    replace(good(), aces=(*good().aces, private.Ace(OTHER, private.READ))),
    replace(good(), aces=(good().aces[0], good().aces[0])),
    replace(good(), aces=(good().aces[0], private.Ace(private.SYSTEM, private.MODIFY)))])
def test_private_acl_refuses_owner_inheritance_denies_unknown_and_extra_aces(acl):
    with pytest.raises(p.ProxyFailure, match="proxy_private"):
        private.validate_acl(acl, SERVICE, directory=True)


@pytest.mark.parametrize("rights", [2, 4, 16, 64, 256, 0x10000, 0x40000, 0x80000, 0x40000000, 0x10000000])
@pytest.mark.parametrize("sid", [SERVICE, OTHER])
def test_ancestor_any_group_write_or_control_rights_fail(rights, sid):
    acl = private.Acl(OTHER, False, (private.Ace(sid, rights),))
    with pytest.raises(p.ProxyFailure):
        private.validate_acl(acl, SERVICE, directory=True, ancestor=True)


def test_ancestor_read_traverse_only_and_privileged_sid_exceptions():
    acl = private.Acl(private.SYSTEM, False, (private.Ace(SERVICE, private.READ_EXECUTE),
        private.Ace(OTHER, private.READ), private.Ace(private.SYSTEM, 0x1F01FF),
        private.Ace(private.ADMINS, 0x10000000)))
    private.validate_acl(acl, SERVICE, directory=True, ancestor=True)
    for ace in (private.Ace(OTHER, 0x200), private.Ace(private.SYSTEM, 0, kind=1)):
        with pytest.raises(p.ProxyFailure):
            private.validate_acl(private.Acl(OTHER, False, (ace,)), SERVICE, directory=True, ancestor=True)


def test_unavailable_acl_inspector_and_actual_service_mismatch_fail(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    path = root / "policy"
    path.write_bytes(b"synthetic")
    def unavailable(_):
        raise OSError("SECRET")
    with pytest.raises(p.ProxyFailure) as error:
        private.verify_private(path, root, repo_root=tmp_path / "repo", service_sid=SERVICE,
            inspector=unavailable, service_identity=lambda: SERVICE, platform="nt")
    assert "SECRET" not in str(error.value)
    def inspect(item):
        return good(item.is_dir()) if item == root or root in item.parents else private.Acl(private.SYSTEM, False, (private.Ace(SERVICE, private.READ_EXECUTE),))
    with pytest.raises(p.ProxyFailure):
        private.verify_private(path, root, repo_root=tmp_path / "repo", service_sid=SERVICE,
            inspector=inspect, service_identity=lambda: OTHER, platform="nt")
    private.verify_private(path, root, repo_root=tmp_path / "repo", service_sid=SERVICE,
        inspector=inspect, service_identity=lambda: SERVICE, platform="nt")


def test_repo_containment_and_symlink_ambiguity_refuse(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    path = root / "policy"
    path.write_bytes(b"synthetic")
    with pytest.raises(p.ProxyFailure):
        private.verify_private(path, root, repo_root=root, service_sid=SERVICE)
    # A declared escaping path fails before platform inspection.
    with pytest.raises(p.ProxyFailure):
        private.verify_private(root / ".." / "outside", root, repo_root=tmp_path / "repo", service_sid=SERVICE)


def test_os_lock_is_bounded_nonreentrant_and_released(tmp_path):
    state = tmp_path / "pool.json"
    with private.state_lock(state, timeout=0.1):
        with pytest.raises(p.ProxyFailure, match="proxy_lock"):
            with private.state_lock(state, timeout=0.1):
                pytest.fail("nested nonreentrant lock acquired")
        errors = []
        def contend():
            try:
                with private.state_lock(state, timeout=0.05):
                    errors.append("acquired")
            except p.ProxyFailure as error:
                errors.append(error.reason)
        thread = threading.Thread(target=contend)
        thread.start()
        thread.join(timeout=2)
        assert not thread.is_alive() and errors == ["proxy_lock"]
    with private.state_lock(state, timeout=0.1):
        pass


def test_atomic_public_state_write_is_complete_and_temporary_removed(tmp_path):
    path = tmp_path / "state.json"
    private.atomic_json(path, {"day": None, "used": 0})
    assert p.strict_json(path.read_bytes()) == {"day": None, "used": 0}
    assert sorted(item.name for item in tmp_path.iterdir()) == ["state.json"]


@pytest.mark.parametrize("fault", [None, "file_mode", "root_mode", "wrong_owner", "writable_ancestor", "symlink", "reparse"])
def test_posix_privacy_synthetic_inspector(tmp_path, fault):
    root, path = tmp_path / "private", tmp_path / "private" / "policy"
    def inspect(item):
        mode = stat.S_IFREG | 0o600 if item == path else stat.S_IFDIR | (0o700 if item == root else 0o755)
        owner, attributes = 1000, 0
        if fault == "file_mode" and item == path: mode |= 0o040
        if fault == "root_mode" and item == root: mode |= 0o010
        if fault == "wrong_owner" and item == path: owner = 1001
        if fault == "writable_ancestor" and item == root.parent: mode |= 0o020
        if fault == "symlink" and item == path: mode = stat.S_IFLNK | 0o777
        if fault == "reparse" and item == root: attributes = 0x400
        return SimpleNamespace(st_mode=mode, st_uid=owner, st_file_attributes=attributes)
    kwargs = dict(repo_root=tmp_path / "repo", service_sid=SERVICE, platform="posix", uid=1000, stat_inspector=inspect)
    if fault is None:
        private.verify_private(path, root, **kwargs)
    else:
        with pytest.raises(p.ProxyFailure):
            private.verify_private(path, root, **kwargs)


def test_untrusted_ancestor_owner_cannot_gain_implicit_write_dac():
    acl = private.Acl(OTHER, False, (private.Ace(OTHER, private.READ_EXECUTE),))
    with pytest.raises(p.ProxyFailure, match="proxy_private"):
        private.validate_acl(acl, SERVICE, directory=True, ancestor=True)
