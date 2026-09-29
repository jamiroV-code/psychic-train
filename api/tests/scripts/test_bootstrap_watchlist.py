"""bootstrap_watchlist.py — idempotent fresh-checkout watchlist creation (AC-9).

SAFETY (T22): `_isolate` is module-level `autouse=True`, depends on
`isolated_cache` and redirects `watchlist_store.DEFAULT_WATCHLIST_PATH` to a
tmp file. That redirect is load-bearing here specifically: a bare
`bootstrap_watchlist.main([])` against the default target would CREATE the
developer's real `api/data/watchlist.json`.
"""
from __future__ import annotations

import json

import pytest

from api.data import cache, watchlist as watchlist_store
from api.scripts import bootstrap_watchlist


@pytest.fixture(autouse=True)
def _isolate(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    return isolated_cache


def test_isolated_cache_redirects_cache_root(tmp_path):
    """Canary: the autouse isolation is really in effect inside a test."""
    assert cache.CACHE_ROOT == tmp_path
    assert watchlist_store.DEFAULT_WATCHLIST_PATH == tmp_path / "watchlist.json"


def _example(tmp_path, coins=("BTC", "HYPE", "ETH", "SOL")):
    path = tmp_path / "watchlist.example.json"
    path.write_text(json.dumps({"coins": list(coins)}), encoding="utf-8")
    return path


def test_creates_target_from_example_when_absent(tmp_path, capsys):
    example = _example(tmp_path)
    target = tmp_path / "nested" / "watchlist.json"

    assert bootstrap_watchlist.main(["--example", str(example), "--target", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == example.read_text(encoding="utf-8")
    assert "created" in capsys.readouterr().out


def test_existing_target_is_never_overwritten(tmp_path, capsys):
    example = _example(tmp_path)
    target = tmp_path / "watchlist.json"
    target.write_text(json.dumps({"coins": ["ONLYMINE"]}), encoding="utf-8")

    assert bootstrap_watchlist.main(["--example", str(example), "--target", str(target)]) == 0
    assert json.loads(target.read_text())["coins"] == ["ONLYMINE"]
    assert "already present" in capsys.readouterr().out


def test_running_twice_is_idempotent(tmp_path):
    example = _example(tmp_path)
    target = tmp_path / "watchlist.json"
    args = ["--example", str(example), "--target", str(target)]

    assert bootstrap_watchlist.main(args) == 0
    first = target.read_bytes()
    assert bootstrap_watchlist.main(args) == 0
    assert target.read_bytes() == first


def test_missing_example_returns_one(tmp_path, capsys):
    target = tmp_path / "watchlist.json"
    code = bootstrap_watchlist.main(
        ["--example", str(tmp_path / "nope.json"), "--target", str(target)]
    )
    assert code == 1
    assert not target.exists()
    assert "not found" in capsys.readouterr().err


def test_default_target_is_read_at_call_time(tmp_path):
    """The redirected module attribute wins — no import-time path binding."""
    example = _example(tmp_path)
    assert bootstrap_watchlist.main(["--example", str(example)]) == 0
    assert (tmp_path / "watchlist.json").exists()
    assert watchlist_store.read_watchlist() == ["BTC", "HYPE", "ETH", "SOL"]


def test_bare_main_does_not_consume_pytest_argv(tmp_path):
    """C5/E7: `main()` with no args must not parse pytest's own sys.argv."""
    assert bootstrap_watchlist.main() == 0
    assert (tmp_path / "watchlist.json").exists()


def test_repo_example_file_exists_and_is_shaped_correctly():
    """The default source the runbook tells users to rely on is really there."""
    data = json.loads(bootstrap_watchlist.DEFAULT_EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert isinstance(data.get("coins"), list) and data["coins"]
