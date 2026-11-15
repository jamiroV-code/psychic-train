"""Perp data stays local and out of CI (RFC-001 Stage 4; VA-proofs P-2 and C2).

Static checks plus `git ls-files` / `git check-ignore`; no network, nothing written.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from api.tests.tooling_guards._common import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def test_no_perp_cache_file_is_tracked():
    tracked = _git("ls-files", "api/data/cache/perp").stdout.strip()
    assert tracked == ""


def test_perp_snapshot_path_is_ignored():
    result = _git("check-ignore", "api/data/cache/perp/hl_snapshot/BTC/2026-11.jsonl")
    assert result.returncode == 0, result.stderr


def test_gitignore_names_the_perp_cache_explicitly():
    lines = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "api/data/cache/perp/" in lines
    assert "!api/data/cache/perp/" not in lines


def test_no_workflow_runs_or_mentions_the_perp_collector():
    if not WORKFLOWS.is_dir():
        return
    for path in WORKFLOWS.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "collect_perp" not in text, path.name
        assert "cache/perp" not in text, path.name
