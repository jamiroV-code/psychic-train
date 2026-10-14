"""AC-2: network-capable imports are confined to the fetch tiers; API never imports the tooling."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from api.tests.tooling_guards._common import API_DIR, TOOL_DIR, WORKFLOWS, walk_py

NETWORK_ROOTS = {
    "scrapling", "urllib.request", "http.client", "httpx", "requests", "socket", "playwright", "curl_cffi", "patchright",
}
ALLOWED_FILES = {"fetch_tier1.py", "fetch_tier2.py", "fetch_tier3.py", "robots.py"}
# Second allow-list: the parser files may import ONLY scrapling.parser (Selector; no networking).
PARSER_FILES = {"parse.py", "adaptive.py"}
PARSER_ROOT = "scrapling.parser"
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


def is_parser_module(mod: str) -> bool:
    return mod == PARSER_ROOT or mod.startswith(PARSER_ROOT + ".")


def flagged_imports(file_name: str, source: str) -> list[str]:
    """Network-capable imports in `source`; parse.py/adaptive.py may import scrapling.parser only."""
    parser_file = file_name in PARSER_FILES
    return sorted(m for m in imported_modules(source) if is_network(m) and not (parser_file and is_parser_module(m)))


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
        bad = flagged_imports(path.name, path.read_text(encoding="utf-8"))
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


def test_parser_files_may_import_scrapling_parser_only():
    ok = "from scrapling.parser import Selector\nimport scrapling.parser"
    assert flagged_imports("parse.py", ok) == []
    assert flagged_imports("adaptive.py", ok) == []
    assert flagged_imports("pipeline.py", ok) != []


@pytest.mark.parametrize(
    "src",
    [
        "from scrapling.fetchers import Fetcher",
        "import scrapling",
        "from scrapling import Selector",
        "import scrapling.engines",
        "import curl_cffi",
        "from playwright.sync_api import sync_playwright",
        "import patchright",
        "import httpx\nimport requests",
        "import socket",
        "from urllib.request import urlopen",
        "from scrapling.parser import Selector\nfrom scrapling.fetchers import Fetcher",
    ],
)
def test_parser_files_still_flag_everything_else(src):
    assert flagged_imports("parse.py", src) != []
    assert flagged_imports("adaptive.py", src) != []
