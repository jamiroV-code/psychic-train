"""AC-4 / AC-21: the API install must never pick up the scraping tooling."""
from __future__ import annotations

import re
import shutil
import subprocess
import tomllib

import pytest

from api.tests.tooling_guards._common import API_DIR, REPO_ROOT, WORKFLOWS, norm, req_name

FORBIDDEN = {"scrapling", "playwright", "patchright", "rea-agents"}


def test_api_pyproject_has_no_tooling_dependency():
    data = tomllib.loads((API_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    names = {req_name(s) for s in data["project"]["dependencies"]}
    for group in data.get("dependency-groups", {}).values():
        names |= {req_name(s) for s in group if isinstance(s, str)}
    assert not names & FORBIDDEN


def test_api_lock_has_no_tooling_package():
    text = (API_DIR / "uv.lock").read_text(encoding="utf-8")
    names = {norm(m) for m in re.findall(r'^name = "([^"]+)"', text, flags=re.M)}
    assert not names & FORBIDDEN


def test_api_wheel_packages_unchanged():
    data = tomllib.loads((API_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["analytics", "data", "models", "routers"]


def mentions_tooling_dir(text: str) -> bool:
    """Case-insensitive, slash-direction-insensitive match of the tooling path."""
    return "tools/data-integration" in text.lower().replace("\\", "/")


def test_tooling_dir_detector_catches_spellings():
    for spelling in (
        "tools/data-integration",
        "tools\\data-integration",
        "Tools/Data-Integration",
        "TOOLS\\DATA-INTEGRATION\\src",
        "run: uv sync --project tools/data-integration",
    ):
        assert mentions_tooling_dir(spelling), spelling
    for clean in ("tools/other", "data-integration", "run: uv sync --project api"):
        assert not mentions_tooling_dir(clean), clean


def test_workflows_do_not_mention_tooling_dir():
    for wf in sorted(WORKFLOWS.glob("*.y*ml")):
        assert not mentions_tooling_dir(wf.read_text(encoding="utf-8")), wf.name


def test_ignore_file_carries_approval_pattern():
    lines = {ln.strip() for ln in (REPO_ROOT / (".git" + "ignore")).read_text(encoding="utf-8").splitlines()}
    assert "*.approval.json" in lines


def test_no_tracked_approval_files():
    if shutil.which("git") is None or not (REPO_ROOT / ".git").exists():
        pytest.skip("git checkout not available")
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    assert [p for p in out.splitlines() if p.endswith(".approval.json")] == []
