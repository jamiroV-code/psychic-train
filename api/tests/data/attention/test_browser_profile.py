"""S-BrowserHost: browser profile ACL policy A10-A12 (finish plan; probes BP3a, BP3c)."""
from __future__ import annotations

import _winapi
import json
import os
from pathlib import Path

import pytest

from api.data.attention import browser_profile as bp
from api.tests.data.attention.fixture_seams import require_permitted

pytestmark = pytest.mark.skipif(os.name != "nt", reason="native Windows ACL policy")

# BP3c: the one capability SID Edge Stable put on every profile (PROBES-2 §BP3c).
BP3C_SID = ("S-1-15-3-1024-3239966617-1410756637-3494353204-65451782-2225605771-3526040376-"
            "1730753648-3419555762")
OWNER = "S-1-5-21-1-2-3-1001"
APPROVED = bp.ProfilePolicy(ce1_approved=True, ce2_approved=True)
INH = bp.INHERITED_ACE
EXT = "abcdefghijklmnopabcdefghijklmnop"


def owner_aces(directory: bool):
    return (bp.NativeAce(OWNER, bp.FULL_ACCESS, INH | (bp.OI | bp.CI if directory else 0)),)


class TreeInspector:
    """acl_inspector seam: scripted ACLs by relative path; default = owner-only inherited."""

    def __init__(self, base: Path, overrides: dict[str, tuple] | None = None):
        require_permitted("acl_inspector")
        self.base, self.overrides = base, {k.casefold(): v for k, v in (overrides or {}).items()}

    def __call__(self, path: Path) -> bp.NativeAcl:
        if path == self.base or path == self.base.parent:
            return bp.NativeAcl(OWNER, True, (bp.NativeAce(OWNER, bp.FULL_ACCESS, bp.OI | bp.CI),))
        rel = path.relative_to(self.base).as_posix().casefold()
        extra = self.overrides.get(rel, ())
        return bp.NativeAcl(OWNER, False, owner_aces(path.is_dir()) + tuple(extra))


def ce1_anchor():
    return (bp.NativeAce(BP3C_SID, bp.CE1_OBJECT_MASK, 0), bp.NativeAce(BP3C_SID, bp.CE1_INHERIT_MASK, bp.OI | bp.CI | bp.IO))


def ce1_child_dir():
    return (bp.NativeAce(BP3C_SID, bp.CE1_OBJECT_MASK, INH),
            bp.NativeAce(BP3C_SID, bp.CE1_INHERIT_MASK, INH | bp.OI | bp.CI | bp.IO))


def ce1_child_file():
    return (bp.NativeAce(BP3C_SID, bp.CE1_OBJECT_MASK, INH),)


def everyone(mask=32, flags=0):
    return (bp.NativeAce(bp.EVERYONE, mask, flags),)


def edge_tree(tmp_path: Path) -> Path:
    root = tmp_path / "profiles"
    profile = root / "acct1"
    for rel in ("Default/Network", "Default/Cache/Cache_Data", "Default/Shared Dictionary",
                "Default/Local Storage/leveldb", "Default/Session Storage",
                f"Default/Storage/ext/{EXT}/def/Network", f"Default/Storage/ext/{EXT}/def/Local Storage/leveldb"):
        (profile / rel).mkdir(parents=True, exist_ok=True)
    for rel in ("Local State", "Default/Preferences", "Default/Network/Cookies", "Default/Cache/Cache_Data/index",
                "Default/Local Storage/leveldb/000003.log", "Default/Session Storage/CURRENT",
                f"Default/Storage/ext/{EXT}/def/Local Storage/leveldb/LOG"):
        (profile / rel).write_bytes(b"x")
    (profile / bp.PROFILE_RECORD).write_text(json.dumps(
        {"schema": 1, "creator_version": bp.CREATOR_VERSION, "root_identity": bp.root_identity(profile), "label": "acct1"}))
    return profile


EDGE_OVERRIDES = {
    "Default/Network": ce1_anchor(), "Default/Network/Cookies": ce1_child_file(),
    "Default/Cache": ce1_anchor(), "Default/Cache/Cache_Data": ce1_child_dir(),
    "Default/Cache/Cache_Data/index": ce1_child_file(), "Default/Shared Dictionary": ce1_anchor(),
    f"Default/Storage/ext/{EXT}/def/Network": ce1_anchor(),
    "Default/Local Storage/leveldb/000003.log": everyone(), "Default/Session Storage/CURRENT": everyone(),
    f"Default/Storage/ext/{EXT}/def/Local Storage/leveldb/LOG": everyone(),
}


def store(tmp_path, overrides=None, policy=APPROVED, **kw):
    profile = tmp_path / "profiles" / "acct1"
    return bp.ProfileStore(tmp_path / "profiles", cache_root=tmp_path / "cache", owner_sid=OWNER, policy=policy,
                           ce1_sid=BP3C_SID, inspector=TreeInspector(profile, overrides), **kw)


def reason(excinfo) -> str:
    return excinfo.value.reason


def test_ce1_is_derived_at_runtime_and_equals_the_bp3c_sid():
    assert bp.derive_capability_sid(bp.CE1_CAPABILITY) == BP3C_SID
    assert bp.derive_capability_sid("lpacEdgeBetaNetworkSandbox") != BP3C_SID


def test_native_secure_create_root_and_account_inherit_owner_only(tmp_path):
    sid = bp.token_sid()
    s = bp.ProfileStore(tmp_path / "profiles", cache_root=tmp_path / "cache", owner_sid=sid, policy=APPROVED)
    profile = s.prepare("acct1", "acct1")
    for path in (tmp_path / "profiles", profile):
        acl = bp.inspect_native_acl(path)
        assert acl.owner == sid and acl.protected
        assert acl.aces == (bp.NativeAce(sid, bp.FULL_ACCESS, bp.OI | bp.CI),)
    (profile / "Default").mkdir()
    (profile / "Default" / "Preferences").write_bytes(b"{}")
    child = bp.inspect_native_acl(profile / "Default" / "Preferences")
    assert not child.protected and child.aces == (bp.NativeAce(sid, bp.FULL_ACCESS, INH),)
    assert s.prepare("acct1", "acct1") == profile  # existing profile re-admitted recursively
    assert (profile / bp.PROFILE_RECORD).exists()


def test_full_edge_shape_is_admitted_and_pinned_by_the_post_session_sweep(tmp_path):
    edge_tree(tmp_path)
    s = store(tmp_path, EDGE_OVERRIDES)
    profile = tmp_path / "profiles" / "acct1"
    report = s.sweep("acct1", profile)
    pin = json.loads((tmp_path / "cache/attention/_pc_state/profile_records/acct1.json").read_text())
    assert pin["ce1_sid"] == BP3C_SID and not pin["drift"]
    assert "default/local storage/leveldb/000003.log" in pin["ce2_locations"]
    assert report["default/network/cookies"] == "present"
    assert report["default/cookies"] == "absent"  # an absent file is never reported protected
    assert s.prepare("acct1", "acct1") == profile


@pytest.mark.parametrize("overrides", [
    {"Default/Network": (bp.NativeAce(BP3C_SID, bp.CE1_OBJECT_MASK, 0),)},  # one of the pair missing
    {"Default/Network": ce1_anchor() + (bp.NativeAce(BP3C_SID, 0x1F01FF, 0),)},  # extra ACE
    {"Default/Network": (bp.NativeAce(BP3C_SID, 0x1F01FF, 0), ce1_anchor()[1])},  # wrong mask
    {"Default/Preferences": ce1_child_file()},  # CE-1 outside its locations
    {"Default/Network": (bp.NativeAce("S-1-15-3-1024-1-2-3", bp.CE1_OBJECT_MASK, 0),)},  # other capability SID
    {"Default/Local Storage/leveldb/000003.log": everyone(33)},  # CE-2 mask not exactly 32
    {"Default/Preferences": everyone()},  # Everyone outside CE-2 locations
    {"Default/Local Storage/leveldb": everyone()},  # CE-2 on a directory
    {"Default/Session Storage/CURRENT": everyone(32, INH)},  # CE-2 must be explicit
    {"Default/Preferences": (bp.NativeAce("S-1-5-32-545", 0x1200A9, INH),)},  # Users
    {"Default/Preferences": (bp.NativeAce("S-1-15-2-1", 0x1200A9, INH),)},  # ALL APPLICATION PACKAGES
    {"Default/Preferences": (bp.NativeAce(OWNER, 0x10000, 0, kind=1),)},  # deny ACE
    {"Default/Preferences": (bp.NativeAce(OWNER, bp.FULL_ACCESS, 0, kind=9),)},  # conditional/callback ACE
    {f"Default/Storage/ext/{EXT}/def/Local Storage/leveldb": ce1_anchor()},  # CE-1 in ext but wrong dir
])
def test_any_other_principal_mask_or_location_is_refused(tmp_path, overrides):
    edge_tree(tmp_path)
    with pytest.raises(bp.ProfileFailure) as e:
        store(tmp_path, overrides).prepare("acct1", "acct1")
    assert reason(e) == "profile_acl_unverified"


def test_owner_decisions_gate_each_exception_separately(tmp_path):
    edge_tree(tmp_path)
    for policy in (bp.ProfilePolicy(ce1_approved=False, ce2_approved=True),
                   bp.ProfilePolicy(ce1_approved=True, ce2_approved=False)):
        with pytest.raises(bp.ProfileFailure) as e:
            store(tmp_path, EDGE_OVERRIDES, policy=policy).prepare("acct1", "acct1")
        assert reason(e) == "profile_policy_unsatisfied"
    assert bp.OWNER_DECISIONS == bp.ProfilePolicy(ce1_approved=False, ce2_approved=False)


def test_existing_directory_without_our_record_is_refused(tmp_path):
    profile = edge_tree(tmp_path)
    (profile / bp.PROFILE_RECORD).unlink()
    with pytest.raises(bp.ProfileFailure) as e:
        store(tmp_path).prepare("acct1", "acct1")
    assert reason(e) == "profile_acl_unverified"


def test_ce_class_aces_without_a_pin_or_with_a_different_pinned_sid_are_refused(tmp_path):
    edge_tree(tmp_path)
    s = store(tmp_path, EDGE_OVERRIDES)
    with pytest.raises(bp.ProfileFailure) as e:
        s.prepare("acct1", "acct1")  # CE ACEs seen before any post-session pin
    assert reason(e) == "profile_acl_unverified"
    s.sweep("acct1", tmp_path / "profiles" / "acct1")
    pin = tmp_path / "cache/attention/_pc_state/profile_records/acct1.json"
    data = json.loads(pin.read_text())
    pin.write_text(json.dumps(dict(data, ce1_sid="S-1-15-3-1024-9")))
    with pytest.raises(bp.ProfileFailure) as e:
        s.prepare("acct1", "acct1")
    assert reason(e) == "profile_acl_unverified"


def test_reparse_points_anywhere_are_refused(tmp_path):
    profile = edge_tree(tmp_path)
    target = tmp_path / "elsewhere"
    target.mkdir()
    _winapi.CreateJunction(str(target), str(profile / "Default" / "Storage" / "ext" / "junction"))
    with pytest.raises(bp.ProfileFailure) as e:
        store(tmp_path).prepare("acct1", "acct1")
    assert reason(e) == "profile_acl_unverified"


def test_profile_directory_itself_must_be_its_final_real_path(tmp_path):
    root = tmp_path / "profiles"
    target = tmp_path / "real"
    target.mkdir()
    root.mkdir()
    _winapi.CreateJunction(str(target), str(root / "acct1"))
    with pytest.raises(bp.ProfileFailure) as e:
        store(tmp_path).prepare("acct1", "acct1")
    assert reason(e) == "profile_acl_unverified"


def test_entry_cap_and_depth_cap_refuse(tmp_path):
    edge_tree(tmp_path)
    with pytest.raises(bp.ProfileFailure) as e:
        store(tmp_path, max_entries=5).prepare("acct1", "acct1")
    assert reason(e) == "profile_acl_unverified"
    deep = tmp_path / "profiles" / "acct1" / "/".join(["d"] * 13)
    deep.mkdir(parents=True)
    with pytest.raises(bp.ProfileFailure) as e:
        store(tmp_path).prepare("acct1", "acct1")
    assert reason(e) == "profile_acl_unverified"


def test_post_session_drift_marks_and_the_next_launch_refuses(tmp_path):
    profile = edge_tree(tmp_path)
    store(tmp_path).prepare("acct1", "acct1")
    drifted = store(tmp_path, {"Default/Network/Cookies": (bp.NativeAce("S-1-5-11", 0x1200A9, INH),)})
    with pytest.raises(bp.ProfileFailure) as e:
        drifted.sweep("acct1", profile)
    assert reason(e) == "profile_acl_drift"
    with pytest.raises(bp.ProfileFailure) as e:
        store(tmp_path).prepare("acct1", "acct1")
    assert reason(e) == "profile_acl_drift"


def test_failures_never_carry_the_profile_path(tmp_path):
    profile = edge_tree(tmp_path)
    (profile / bp.PROFILE_RECORD).unlink()
    with pytest.raises(bp.ProfileFailure) as e:
        store(tmp_path).prepare("acct1", "acct1")
    assert str(tmp_path).casefold() not in str(e.value).casefold() and "acct1" not in str(e.value)


def test_two_labels_cannot_share_one_directory(tmp_path):
    s = bp.ProfileStore(tmp_path / "profiles", cache_root=tmp_path / "cache", policy=APPROVED)
    s.prepare("first", "shared")
    with pytest.raises(bp.ProfileFailure, match="profile_acl_unverified"):
        s.prepare("second", "shared")
