"""S-T5a guards: the API never touches the REA wrapper; no REA dependency or agent config appears."""
from __future__ import annotations

import ast
import re

from ._common import API_DIR, REPO_ROOT, TOOL_DIR, walk_py

REA_DIR = TOOL_DIR / "src" / "data_integration" / "rea"
PKG = "data" + "_integration"


def _imports(path):
    mods = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module)
    return mods


def test_api_files_do_not_import_the_wrapper():
    bad = []
    for f in walk_py(API_DIR):
        if f.name == "test_rea_guards.py":
            continue
        for m in _imports(f):
            if m == PKG or m.startswith(PKG + ".") or m == "rea" or m.startswith("rea."):
                bad.append(f"{f.relative_to(REPO_ROOT)}: {m}")
    assert not bad, bad


def test_rea_agents_absent_from_api_dependencies():
    for name in ("uv.lock", "pyproject.toml"):
        text = (API_DIR / name).read_text(encoding="utf-8").lower()
        assert "rea-agents" not in text and "rea_agents" not in text, name


def test_no_mcp_config_in_repo():
    assert not (REPO_ROOT / (".mcp" + ".json")).exists()


def test_wrapper_sources_never_enable_a_shell_or_setup():
    for f in REA_DIR.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert not re.search(r"shell\s*=\s*True", src), f.name
        assert "os.system" not in src and "os.popen" not in src, f.name
    wrapper_src = (REA_DIR / "wrapper.py").read_text(encoding="utf-8")
    assert "shell=False" in wrapper_src
    assert "npm_config_ignore_scripts" in wrapper_src


def test_allowlist_has_no_forbidden_commands():
    tree = ast.parse((REA_DIR / "allowlist.py").read_text(encoding="utf-8"))
    strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for banned in ("setup", "update", "uninstall", "mcp", "completions"):
        assert banned not in strings, banned


SUBCOMMAND_RE = re.compile(r"rea-agents(@[\w.]+)?\s+(setup|update|uninstall|mcp|completions)\b", re.IGNORECASE)
EXEMPT_WORDS = ("rejected", "superseded")


def flagged_constants(source: str) -> list[str]:
    """String constants naming `rea-agents <banned subcommand>`, unless the text says rejected or superseded."""
    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if SUBCOMMAND_RE.search(text) and not any(w in text.lower() for w in EXEMPT_WORDS):
                hits.append(text)
    return hits


def test_no_rea_py_constant_names_a_banned_subcommand():
    bad = {f.name: flagged_constants(f.read_text(encoding="utf-8")) for f in REA_DIR.glob("*.py")}
    assert REA_DIR.joinpath("wrapper.py").exists()
    assert not any(bad.values()), bad


def test_subcommand_scan_flags_a_temp_file(tmp_path):
    for sub in ("setup", "update", "uninstall", "mcp", "completions", "SETUP"):
        f = tmp_path / "bad.py"
        f.write_text(f'X = "rea-agents {sub}"\n', encoding="utf-8")
        assert flagged_constants(f.read_text(encoding="utf-8")), sub
    f.write_text('X = "npx -y rea-agents@6.4.0 setup"\n', encoding="utf-8")
    assert flagged_constants(f.read_text(encoding="utf-8"))
    f.write_text('X = "rea-agents setup is rejected"\nY = "rea-agents compare"\n', encoding="utf-8")
    assert flagged_constants(f.read_text(encoding="utf-8")) == []
