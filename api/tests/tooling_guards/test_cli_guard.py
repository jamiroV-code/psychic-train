"""S-T7 CLI guards (file-only, stdlib): no code execution in the CLI modules, lazy heavy imports, CLI not wired
into the API, workflows, schedulers or deploy scripts, recipes carry no secret or address."""
from __future__ import annotations

import ast
import os
import re

from api.tests.tooling_guards._common import API_DIR, REPO_ROOT, TOOL_DIR, WORKFLOWS

SRC = TOOL_DIR / "src" / "data_integration"
CLI_MODULES = ("__main__.py", "cli.py", "recipe.py")
BANNED = {"eval", "exec", "compile", "pickle", "marshal", "yaml", "shelve", "subprocess"}
LAZY_ROOTS = ("data_integration.fetch_tier", "data_integration.pipeline", "data_integration.rea", "scrapling")
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SKIP_DIRS = {"__pycache__", "site-packages"}


def banned_uses(source: str) -> list[str]:
    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id in BANNED:
            hits.append(node.id)
        elif isinstance(node, ast.Attribute):
            if node.attr in BANNED:
                hits.append(node.attr)
            if node.attr == "system" and isinstance(node.value, ast.Name) and node.value.id == "os":
                hits.append("os.system")
        elif isinstance(node, ast.Import):
            hits += [a.name for a in node.names if a.name.split(".")[0] in BANNED]
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in BANNED:
            hits.append(node.module)
    return sorted(hits)


def module_level_imports(source: str) -> list[str]:
    """Imports executed at import time: anything outside a function or class body."""
    found: list[str] = []

    def visit(nodes):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(node, ast.Import):
                found.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.append(node.module)
                found.extend(f"{node.module}.{a.name}" for a in node.names)
            visit(ast.iter_child_nodes(node))

    visit(ast.parse(source).body)
    return found


def test_detector_flags_banned_constructs():
    assert banned_uses("eval('1')") == ["eval"]
    assert banned_uses("import pickle") == ["pickle"]
    assert banned_uses("import os\nos.system('x')") == ["os.system"]
    assert banned_uses("import re\nre.compile('x')") == ["compile"]
    assert banned_uses("from subprocess import run") == ["subprocess"]
    assert banned_uses("import json\njson.loads('1')") == []


def test_cli_modules_exist_and_use_no_code_execution():
    for name in CLI_MODULES:
        path = SRC / name
        assert path.is_file(), name
        assert banned_uses(path.read_text(encoding="utf-8")) == [], name


def test_lazy_import_detector():
    assert module_level_imports("import os\ndef f():\n    import scrapling\n") == ["os"]
    assert "scrapling" in module_level_imports("import scrapling")
    assert "data_integration.pipeline" in module_level_imports("from data_integration import pipeline")


def test_cli_modules_import_heavy_parts_lazily():
    for name in CLI_MODULES:
        eager = module_level_imports((SRC / name).read_text(encoding="utf-8"))
        bad = [m for m in eager if m.startswith(LAZY_ROOTS)]
        assert bad == [], f"{name} imports {bad} at module level"


def _scan_files():
    roots = [API_DIR, REPO_ROOT / "deploy", WORKFLOWS]
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP_DIRS]
            if os.path.abspath(dirpath) == THIS_DIR:
                dirnames[:] = []
                continue
            for f in filenames:
                if f.endswith((".py", ".toml", ".cfg", ".ini", ".json", ".yml", ".yaml", ".ps1", ".psd1", ".md", ".txt", ".sh", ".bat", ".cmd")):
                    yield os.path.join(dirpath, f)


def test_nothing_outside_the_tool_references_the_cli():
    needles = ("data_integration", "data-integration")
    hits = []
    for path in _scan_files():
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if any(n in text for n in needles):
            hits.append(os.path.relpath(path, REPO_ROOT))
    assert hits == [], hits


_SECRET = re.compile(r"(?i)(api[_-]?key|secret|token|passw(or)?d|bearer|authorization|cookie)\s*[\"']?\s*[:=]")
_CREDS_IN_URL = re.compile(r"://[^/\s\"']*:[^/\s\"']*@")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_LONG_TOKEN = re.compile(r"[A-Za-z0-9+/_-]{40,}")


def recipe_problems(text: str) -> list[str]:
    problems = []
    for label, pat in (("secret", _SECRET), ("url credentials", _CREDS_IN_URL), ("ip address", _IPV4), ("long token", _LONG_TOKEN)):
        if pat.search(text):
            problems.append(label)
    return problems


def test_recipe_checker_flags_bad_text():
    assert recipe_problems('{"api_key": "x"}') == ["secret"]
    assert recipe_problems('{"url": "https://u:p@example.test/"}') == ["url credentials"]
    assert recipe_problems('{"url": "http://10.0.0.1/"}') == ["ip address"]
    assert recipe_problems('{"url": "https://example.test/data/"}') == []


def test_recipes_have_no_secret_or_address_pattern():
    folder = TOOL_DIR / "recipes"
    assert folder.is_dir()
    for path in sorted(folder.glob("*.json")):
        assert recipe_problems(path.read_text(encoding="utf-8")) == [], path.name


def test_example_recipe_is_synthetic():
    text = (TOOL_DIR / "recipes" / "example.recipe.json").read_text(encoding="utf-8")
    hosts = re.findall(r"https?://([^/\"']+)", text)
    assert hosts and all(h == "example.test" for h in hosts)
