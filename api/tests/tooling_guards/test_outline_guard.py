"""AC-36: the page outline stays pure, the docs line names it. Stdlib only."""
from __future__ import annotations

import ast

from api.tests.tooling_guards._common import REPO_ROOT, TOOL_DIR

PARSE = TOOL_DIR / "src" / "data_integration" / "parse.py"
DOCS = REPO_ROOT / "process" / "context" / "data-sources" / "all-data-sources.md"
IO_NAMES = {"open", "print", "input", "exec", "eval", "compile", "__import__", "Path", "socket", "urlopen", "requests", "httpx",
            "subprocess", "os", "sys", "write_text", "write_bytes", "read_text", "read_bytes"}
OUTLINE_FUNCS = {"outline", "render_outline"}
# measured on origin/main before the edit (bytes, "New dataset workflow" heading to the next level-2 heading)
DOCS_BASELINE = 3397


def outline_names() -> set[str]:
    tree = ast.parse(PARSE.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and (node.name in OUTLINE_FUNCS or node.name.startswith("_outline")):
            for n in ast.walk(node):
                if isinstance(n, ast.Name):
                    names.add(n.id)
                elif isinstance(n, ast.Attribute):
                    names.add(n.attr)
    return names


def test_outline_code_exists_and_has_no_io_names():
    names = outline_names()
    assert names, "outline functions not found"
    assert names.isdisjoint(IO_NAMES), sorted(names & IO_NAMES)


def test_parse_imports_stay_parser_only():
    tree = ast.parse(PARSE.read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    assert not any(m.split(".")[0] in {"socket", "requests", "httpx", "subprocess", "playwright"} or m.startswith("urllib.request")
                   or (m.startswith("scrapling") and m != "scrapling.parser") for m in mods), sorted(mods)


def test_docs_section_names_the_outline_within_budget():
    text = DOCS.read_text(encoding="utf-8")
    start = text.index("## New dataset workflow")
    end = text.find("\n## ", start + 5)
    section = text[start: end if end != -1 else len(text)]
    assert "page outline" in section
    assert len(section.encode("utf-8")) <= DOCS_BASELINE + 200
