"""Approval record store: validation, atomic write, corrupt handling."""
from __future__ import annotations

import json
import os

import pytest

from data_integration import approvals
from data_integration.approvals import ApprovalStore, StoreCorrupt, StoreMissing, RecordMissing
from _helpers import NOW, make_record


def test_valid_source_names():
    for ok in ["ab", "a", "a-b_c", "x" * 64, "0src"]:
        assert approvals.valid_source(ok), ok


def test_bad_source_names():
    for bad in ["../x", "a.b", "CON", "con", "nul", "com1", "", "-a", "a/b", "a\\b", "x" * 65, "A", "a b", "a\n", None, 5]:
        assert not approvals.valid_source(bad), bad


def test_bad_source_never_builds_path(tmp_path):
    store = ApprovalStore(tmp_path)
    with pytest.raises(ValueError):
        store.path_for("../x")


def test_utc_helpers():
    assert approvals.format_utc(NOW) == "2026-01-10T12:00:00Z"
    assert approvals.parse_utc("2026-01-10T12:00:00Z") == NOW
    for bad in ["2026-01-10T12:00:00", "2026-01-10T12:00:00+00:00", "garbage", "", None]:
        with pytest.raises(ValueError):
            approvals.parse_utc(bad)


def test_missing_store_dir(tmp_path):
    with pytest.raises(StoreMissing):
        ApprovalStore(tmp_path / "nope").read("example-src")


def test_missing_file(tmp_path):
    with pytest.raises(RecordMissing):
        ApprovalStore(tmp_path).read("example-src")
    assert list(tmp_path.iterdir()) == []  # never creates a default record


def test_write_read_roundtrip_and_revision(tmp_path):
    store = ApprovalStore(tmp_path / "ap")
    rec = store.write(make_record())
    assert rec.revision == 1
    assert store.path_for("example-src").name == "example-src.approval.json"
    assert store.read("example-src") == rec
    rec2 = store.write(make_record(owner="owner-b"))
    assert rec2.revision == 2
    assert store.read("example-src").owner == "owner-b"


def test_corrupt_file_renamed_bad(tmp_path):
    store = ApprovalStore(tmp_path)
    (tmp_path / "example-src.approval.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(StoreCorrupt):
        store.read("example-src")
    assert not (tmp_path / "example-src.approval.json").exists()
    assert (tmp_path / "example-src.approval.json.bad").exists()


def test_wrong_shape_and_naive_timestamp_are_corrupt(tmp_path):
    store = ApprovalStore(tmp_path)
    store.write(make_record())
    p = store.path_for("example-src")
    data = json.loads(p.read_text(encoding="utf-8"))
    data["expiry"] = "2026-03-01T00:00:00"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StoreCorrupt):
        store.read("example-src")


def test_source_name_mismatch_is_corrupt(tmp_path):
    store = ApprovalStore(tmp_path)
    store.write(make_record())
    os.replace(store.path_for("example-src"), tmp_path / "other.approval.json")
    with pytest.raises(StoreCorrupt):
        store.read("other")


def test_tier_out_of_range_is_corrupt(tmp_path):
    store = ApprovalStore(tmp_path)
    store.write(make_record())
    p = store.path_for("example-src")
    data = json.loads(p.read_text(encoding="utf-8"))
    data["allowed_tier"] = 4
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StoreCorrupt):
        store.read("example-src")


def test_atomic_write_failure_leaves_no_partial(tmp_path, monkeypatch):
    store = ApprovalStore(tmp_path)
    store.write(make_record())
    before = store.path_for("example-src").read_text(encoding="utf-8")

    def boom(*a, **k):
        raise OSError("disk")

    monkeypatch.setattr(approvals.os, "replace", boom)
    with pytest.raises(OSError):
        store.write(make_record(owner="owner-b"))
    assert store.path_for("example-src").read_text(encoding="utf-8") == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["example-src.approval.json"]


def test_list_sources(tmp_path):
    store = ApprovalStore(tmp_path)
    store.write(make_record("src-a"))
    store.write(make_record("src-b"))
    (tmp_path / "junk.txt").write_text("x", encoding="utf-8")
    assert store.list_sources() == ["src-a", "src-b"]
    assert ApprovalStore(tmp_path / "nope").list_sources() == []
