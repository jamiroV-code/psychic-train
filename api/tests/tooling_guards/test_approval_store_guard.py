"""Approval store guards (AC-21): no records in the repo, store folder ignored, gate stays stdlib-only."""
from __future__ import annotations

import ast
import os
import sys

from ._common import REPO_ROOT, TOOL_DIR

SRC = TOOL_DIR / "src" / "data_integration"
_SKIP = {"__pycache__", "site-packages", "node" + "_modules"}


def _repo_files():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP]
        for f in filenames:
            yield os.path.join(dirpath, f)


def _ignore_lines() -> list[str]:
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    return [ln.strip() for ln in text.splitlines()]


def test_no_approval_records_in_repo():
    found = [p for p in _repo_files() if p.endswith(".approval.json") or p.endswith(".approval.json.bad")]
    assert found == []


def test_gitignore_covers_approvals_pattern_and_folder():
    lines = _ignore_lines()
    assert "*.approval.json" in lines
    assert "**/approvals/" in lines


GUARDED = ("gate.py", "approvals.py", "approval_cli.py", "paths.py", "types.py", "status.py")


def non_stdlib_imports(source: str) -> list[str]:
    """Imported module names that are neither standard library nor this package, or are network clients."""
    bad = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods = [node.module]
        else:
            continue
        for mod in mods:
            root = mod.split(".")[0]
            if (root not in sys.stdlib_module_names and root != "data_integration") or mod in {
                "urllib.request", "http.client", "socket",
            }:
                bad.append(mod)
    return bad


def test_gate_modules_have_no_third_party_or_network_imports():
    for name in GUARDED:
        assert non_stdlib_imports((SRC / name).read_text(encoding="utf-8")) == [], name


def test_import_guard_flags_third_party_in_temp_module(tmp_path):
    mod = tmp_path / "fake_mod.py"
    mod.write_text("import json\nimport requests\nfrom pandas import DataFrame\nimport socket\n", encoding="utf-8")
    assert non_stdlib_imports(mod.read_text(encoding="utf-8")) == ["requests", "pandas", "socket"]
    clean = tmp_path / "clean_mod.py"
    clean.write_text("import json\nfrom data_integration import paths\n", encoding="utf-8")
    assert non_stdlib_imports(clean.read_text(encoding="utf-8")) == []


def test_fetchpass_constructor_token_not_exported():
    text = (SRC / "gate.py").read_text(encoding="utf-8")
    assert "_TOKEN = object()" in text
    assert "__all__" not in text or "_TOKEN" not in text.split("__all__", 1)[1].split("\n", 1)[0]
