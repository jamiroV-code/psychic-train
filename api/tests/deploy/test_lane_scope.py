"""AC8 (gate G7, committed half): this lane changes nothing outside its
allowlist. Branch-gated (plan D12): once merged, a diff against the base would
fail on every later branch, so it only runs on `claude/p2-deploy` with an
`origin/main` that resolves."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LANE_BRANCH = "claude/p2-deploy"
ALLOWED_PREFIXES = (
    "api/main.py",
    "deploy/",
    "api/tests/deploy/",
    "process/general-plans/active/deployability_28-09-26/",
)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def test_lane_scope_only_allowed_paths():
    branch = _git("branch", "--show-current")
    if branch.returncode != 0 or branch.stdout.strip() != LANE_BRANCH:
        pytest.skip(f"lane scope check only runs on {LANE_BRANCH}")
    base = _git("merge-base", "HEAD", "origin/main")
    if base.returncode != 0 or not base.stdout.strip():
        pytest.skip("origin/main does not resolve")

    changed = _git("diff", "--name-only", base.stdout.strip()).stdout.splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").stdout.splitlines()
    paths = sorted({p for p in changed + untracked if p.strip()})
    outside = [p for p in paths if not p.startswith(ALLOWED_PREFIXES)]
    assert not outside, f"files outside the deployability lane allowlist: {outside}"
