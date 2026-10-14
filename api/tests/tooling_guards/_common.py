"""Shared helpers for the tooling guards (stdlib only, never imports scrapling)."""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_DIR = REPO_ROOT / "tools" / "data-integration"
API_DIR = REPO_ROOT / "api"
WORKFLOWS = REPO_ROOT / (".git" + "hub") / "workflows"


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def req_name(spec: str) -> str:
    """Exact normalised distribution name of a PEP 508 requirement string."""
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    assert m, f"unparseable requirement: {spec!r}"
    return norm(m.group(1))


def walk_py(root: Path):
    """Yield .py files under root, pruning dot-directories and caches."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in {"__pycache__", "site-packages"}]
        for f in filenames:
            if f.endswith(".py"):
                yield Path(dirpath) / f
