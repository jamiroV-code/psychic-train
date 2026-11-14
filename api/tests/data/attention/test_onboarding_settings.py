"""T223 O0: owner settings for coin onboarding (AC17)."""
from __future__ import annotations

import json

import pytest

from api.data.attention import onboarding_settings as os_


def shipped() -> dict:
    return json.loads(os_.SETTINGS_PATH.read_text(encoding="utf-8"))


def test_shipped_file_is_valid_and_shadow():
    s = os_.load()
    assert s.mode == "shadow" == os_.DEFAULT_MODE
    assert (s.probation_days, s.exit_band_rank, s.exit_days) == (14, 120, 7)
    assert (s.resolver_max_coins_per_run, s.classify_max_coins_per_run) == (5, 15)
    assert s.confirmed_classes == {} and s.blocked_sources == {}


def test_settings_drive_the_numbers(tmp_path):
    doc = {**shipped(), "probation_days": 3, "exit_days": 2, "mode": "enforce"}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(doc))
    s = os_.load(p)
    assert (s.mode, s.probation_days, s.exit_days) == ("enforce", 3, 2)


@pytest.mark.parametrize("patch, word", [
    ({"mode": "on"}, "mode"), ({"probation_days": 0}, "probation_days"), ({"exit_days": True}, "exit_days"),
    ({"exit_band_rank": 100}, "exit_band_rank"), ({"stable_band_pct": "2"}, "stable_band_pct"),
    ({"extra": 1}, "unknown keys"), ({"confirmed_classes": {"ABC": "unknown"}}, "confirmed_classes"),
    ({"confirmed_classes": {"abc": "normal"}}, "confirmed_classes"),
    ({"blocked_sources": {"ABC": ["google"]}}, "blocked_sources"), ({"blocked_sources": {"ABC": []}}, "blocked_sources"),
])
def test_bad_values_are_refused_with_a_plain_message(tmp_path, patch, word):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({**shipped(), **patch}))
    with pytest.raises(ValueError, match=word):
        os_.load(p)
    s, why = os_.safe_load(p)
    assert s is None and word in why


def test_missing_key_and_bad_json_and_absent_file(tmp_path):
    doc = shipped()
    del doc["exit_days"]
    p = tmp_path / "s.json"
    p.write_text(json.dumps(doc))
    assert "missing keys exit_days" in os_.safe_load(p)[1]
    p.write_text("{not json")
    assert os_.safe_load(p) == (None, "coin onboarding settings: the file is not valid JSON")
    assert os_.safe_load(tmp_path / "absent.json")[0] is None


def test_owner_maps(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({**shipped(), "confirmed_classes": {"ABC": "stablecoin"},
                             "blocked_sources": {"ABC": ["trends", "wikipedia"]}}))
    s = os_.load(p)
    assert s.confirmed_classes == {"ABC": "stablecoin"}
    assert s.blocked("ABC", "trends") and not s.blocked("ABC", "reddit_x") and not s.blocked("XYZ", "trends")
