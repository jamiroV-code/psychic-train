"""S-T1 skeleton: importability, pins, closed status set, paths, cache isolation."""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

TOOL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOL_DIR.parents[1]
EXPECTED_STATUSES = {
    "ok", "refused", "robots_blocked", "timeout", "connection_failed", "http_error",
    "challenge_page", "changed", "uncertain", "invalid", "cache_hit",
}


def _api_lock_version(name: str) -> str:
    text = (REPO_ROOT / "api" / "uv.lock").read_text(encoding="utf-8")
    m = re.search(rf'^name = "{name}"\nversion = "([^"]+)"', text, flags=re.M)
    assert m, name
    return m.group(1)


def _pins() -> dict[str, str]:
    data = tomllib.loads((TOOL_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    pins = {}
    for spec in data["project"]["dependencies"]:
        m = re.match(r"([A-Za-z0-9_.-]+)(\[[^\]]*\])?==([^\s;]+)", spec)
        assert m, f"dependency must be an exact pin: {spec}"
        pins[m.group(1).lower()] = m.group(3)
    return pins


def test_package_imports():
    import data_integration

    assert data_integration.__name__ == "data_integration"


def test_pins_match_api_lock_and_scrapling():
    pins = _pins()
    assert pins["scrapling"] == "0.4.15"
    for name in ("pandas", "pyarrow", "duckdb"):
        assert pins[name] == _api_lock_version(name)
    assert (pins["pandas"], pins["pyarrow"], pins["duckdb"]) == ("3.0.6", "25.0.1", "1.5.5")


def test_pyproject_layout():
    data = tomllib.loads((TOOL_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["build-system"]["build-backend"] == "hatchling.build"
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/data_integration"]
    pt = data["tool"]["pytest"]["ini_options"]
    assert pt["pythonpath"] == ["../..", "src"]
    assert pt["addopts"] == "-m 'not integration and not browser and not antibot'"
    assert {m.split(":")[0] for m in pt["markers"]} >= {"integration", "browser", "antibot"}


def test_status_set_is_closed():
    from data_integration import status

    assert set(status.ALL_STATUSES) == EXPECTED_STATUSES
    assert status.is_status("ok") and not status.is_status("nope")


def test_types_exist():
    from data_integration import types

    assert hasattr(types, "FetchOutcome") and hasattr(types, "ParsedTable") and hasattr(types, "Fetcher")


def test_paths_env_overrides(monkeypatch, tmp_path):
    from data_integration import paths

    monkeypatch.setenv("DIT_APPROVALS_DIR", str(tmp_path / "a"))
    monkeypatch.setenv("DIT_SCRAPE_DIR", str(tmp_path / "s"))
    monkeypatch.setenv("DIT_EVIDENCE_DIR", str(tmp_path / "e"))
    assert paths.approvals_dir() == tmp_path / "a"
    assert paths.scrape_dir() == tmp_path / "s"
    assert paths.evidence_dir() == tmp_path / "e"


def test_repo_root_on_sys_path_and_api_cache_importable():
    from data_integration import paths

    assert paths._repo_root() == REPO_ROOT
    assert str(REPO_ROOT) in sys.path
    from api.data import cache

    assert cache.OHLCV_COLUMNS


def test_cache_root_isolated(isolated_cache):
    from api.data import cache

    assert Path(cache.CACHE_ROOT) == isolated_cache
    assert Path(cache.CACHE_ROOT).resolve() != cache.DEFAULT_CACHE_ROOT.resolve()


def test_api_modules_not_leaked():
    assert "fastapi" not in sys.modules


@pytest.mark.parametrize("name", ["scrapling", "playwright", "patchright", "rea-agents"])
def test_api_pyproject_untouched_by_tooling(name):
    text = (REPO_ROOT / "api" / "pyproject.toml").read_text(encoding="utf-8")
    assert not re.search(rf'^\s*"{name}[^"]*"', text, flags=re.M)
