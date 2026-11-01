"""Atomic watchlist save: a failure mid-write must not truncate the file."""
from __future__ import annotations

import json
import os

import pytest

from api.data import watchlist as wl


def _files(d):
    return sorted(p.name for p in d.iterdir())


def test_json_dump_failure_mid_write_keeps_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "watchlist.json"
    wl._save_raw(path, {"coins": ["BTC", "ETH"]})
    before = path.read_bytes()
    real_dump = json.dump

    def boom(obj, fp, **kw):
        fp.write('{"coins": [')  # partial output, then crash
        raise OSError("disk died")

    monkeypatch.setattr(wl.json, "dump", boom)
    with pytest.raises(OSError):
        wl._save_raw(path, {"coins": ["BTC", "ETH", "SOL"]})
    monkeypatch.setattr(wl.json, "dump", real_dump)
    assert path.read_bytes() == before
    assert _files(tmp_path) == ["watchlist.json"]


def test_replace_failure_keeps_previous_file_and_no_temp(tmp_path, monkeypatch):
    path = tmp_path / "watchlist.json"
    wl._save_raw(path, {"coins": ["BTC"]})
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(wl.os, "replace", boom)
    with pytest.raises(OSError):
        wl._save_raw(path, {"coins": ["BTC", "SOL"]})
    assert path.read_bytes() == before
    assert _files(tmp_path) == ["watchlist.json"]


def test_success_format_unchanged(tmp_path):
    path = tmp_path / "sub" / "watchlist.json"
    data = {"coins": ["BTC", "ETH"], "note": "x"}
    wl._save_raw(path, data)
    assert path.read_text(encoding="utf-8") == json.dumps(data, indent=2) + "\n"
    assert _files(path.parent) == ["watchlist.json"]


def test_missing_file_loads_empty(tmp_path):
    assert wl._load_raw(tmp_path / "nope.json") == {"coins": []}
