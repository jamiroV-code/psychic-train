"""S-T8 guards (file-only): private-path guard exists, no approval record tracked, cloud-only commands not wired
into the API, deploy scripts or workflows, scrape cache is git-ignored."""
from __future__ import annotations

import os
import subprocess

from api.tests.tooling_guards._common import API_DIR, REPO_ROOT, TOOL_DIR, WORKFLOWS

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
NEEDLES = ("--owner" + "-statement", "scrapling" + " install")
_SKIP = {"__pycache__", "site-packages"}


def _scan():
    for root in (API_DIR, REPO_ROOT / "deploy", WORKFLOWS):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP]
            if os.path.abspath(dirpath) == THIS_DIR:
                dirnames[:] = []
                continue
            for f in filenames:
                yield os.path.join(dirpath, f)


def test_paths_has_path_in_repo():
    text = (TOOL_DIR / "src" / "data_integration" / "paths.py").read_text(encoding="utf-8")
    assert "class PathInRepo" in text


def test_no_approval_record_tracked():
    out = subprocess.run(["git", "ls-files", "*.approval.json"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert out.returncode == 0
    assert out.stdout.strip() == ""


def test_cloud_commands_not_wired():
    hits = []
    for path in _scan():
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if any(n in text for n in NEEDLES):
            hits.append(os.path.relpath(path, REPO_ROOT))
    assert hits == [], hits


def test_scrape_cache_is_ignored():
    out = subprocess.run(["git", "check-ignore", "api/data/cache/ohlcv/x"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert out.returncode == 0
