"""Machine-local locations (outside the repo) and repo-root discovery."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Repo root (parents: data_integration, src, data-integration, tools). Put on sys.path for CLI/probe runs."""
    root = Path(__file__).resolve().parents[4]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


class PathInRepo(Exception):
    """A private folder resolves inside the checkout (message never names a path)."""


def _checkout_root() -> Path:
    """Side-effect-free repo root (unlike _repo_root it never edits sys.path)."""
    return Path(__file__).resolve().parents[4]


def _private(path: Path) -> Path:
    if path.resolve().is_relative_to(_checkout_root()):
        raise PathInRepo("folder must be outside the repository checkout")
    return path


def _local_base() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "my_site"
    return Path.home() / ".local" / "share" / "my_site"


def _dir(env: str, leaf: str) -> Path:
    override = os.environ.get(env)
    return Path(override) if override else _local_base() / leaf


def approvals_dir() -> Path:
    return _private(_dir("DIT_APPROVALS_DIR", "approvals"))


def scrape_dir() -> Path:
    return _private(_dir("DIT_SCRAPE_DIR", "scrape"))


def evidence_dir() -> Path:
    return _dir("DIT_EVIDENCE_DIR", "evidence")
