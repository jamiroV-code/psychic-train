"""AC-2: network-capable imports are confined to the fetch tiers; API never imports the tooling."""
from __future__ import annotations

import ast
from pathlib import Path

from api.tests.tooling_guards._common import API_DIR, TOOL_DIR, WORKFLOWS, walk_py

NETWORK_ROOTS = {"scrapling", "urllib.request", "http.client", "httpx", "requests", "socket", "playwright"}
ALLOWED_FILES = {"fetch_tier1.py", "fetch_tier2.py", "fetch_tier3.py", "robots.py"}
THIS_DIR = Path(__file__).resolve().parent


def imported_modules(source: str) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module)
            mods |= {f"{node.module}.{a.name}" for a in node.names}
    return mods


def is_network(mod: str) -> bool:
    return any(mod == r or mod.startswith(r + ".") for r in NETWORK_ROOTS)


def test_boundary_detector_flags_network_imports():
    assert any(is_network(m) for m in imported_modules("import socket"))
    assert any(is_network(m) for m in imported_modules("from urllib import request\nfrom urllib.request import urlopen"))
    assert any(is_network(m) for m in imported_modules("from scrapling.fetchers import Fetcher"))
    assert not any(is_network(m) for m in imported_modules("import json\nfrom pathlib import Path"))


def test_only_fetch_tiers_import_network_modules():
    src = TOOL_DIR / "src"
    assert src.is_dir()
    offenders = []
    for path in walk_py(src):
        if path.name in ALLOWED_FILES:
            continue
        bad = sorted(m for m in imported_modules(path.read_text(encoding="utf-8")) if is_network(m))
        if bad:
            offenders.append((path.name, bad))
    assert offenders == []


def test_api_code_never_references_data_integration():
    offenders = [
        str(p.relative_to(API_DIR))
        for p in walk_py(API_DIR)
        if THIS_DIR not in p.parents and "data_integration" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == []


def test_workflows_never_reference_data_integration():
    for wf in sorted(WORKFLOWS.glob("*.y*ml")):
        assert "data_integration" not in wf.read_text(encoding="utf-8"), wf.name
