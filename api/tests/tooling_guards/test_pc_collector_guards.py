"""W8b guards for the PC-side X and Reddit collector core (SPEC AC11, AC12, AC16, AC27; PLAN section 7).

Static checks only: no module under test is run against a provider, nothing is installed.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from api.data.attention import pc_adapter, web_queries
from api.tests.tooling_guards._common import API_DIR, REPO_ROOT, walk_py

THIS = Path(__file__).resolve()
# Built from split strings so this file never holds the names it bans.
BANNED = ("x" + "scrape", "klox" + "eld", "gunk" + "onchi")
PURE_MODULES = [API_DIR / "data" / "attention" / f for f in
                ("density.py", "pc_pace.py", "web_queries.py", "web_evidence.py", "pc_adapter.py")]
PC_FILES = PURE_MODULES + [API_DIR / "scripts" / "probe_pc_sources.py", API_DIR / "data" / "attention_queries.json"]
NETWORK_ROOTS = ("requests", "httpx", "socket", "ssl", "urllib", "http", "asyncio", "importlib", "playwright",
                 "aiohttp", "websocket", "websockets", "subprocess", "selenium", "ftplib", "smtplib")
# Builtins that load or run code by name; flagged as bare calls (so `re.compile` stays allowed).
DYNAMIC_BUILTINS = {"__import__", "exec", "eval", "compile", "import_module"}
HOUR_DIRECTIVES = re.compile(r"%[HIMp]")
# Detection-evasion vocabulary (PLAN section 7). A plain honest user agent is the only identity the core knows.
EVASION = re.compile(r"stealth|undetect|fingerprint|proxy[_ -]?rotat|rotat\w*[_ -]proxy|spoof|user[_ -]?agent[_ -]?pool"
                     r"|random[_ -]?user[_ -]?agent|Mozilla/|AppleWebKit|Chrome/\d", re.IGNORECASE)


def imported(source: str) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module)
    return mods


def network_offenders(source: str) -> list[str]:
    """Network-capable imports, and any dynamic import or exec that could hide one."""
    bad = sorted(m for m in imported(source) if any(m == r or m.startswith(r + ".") for r in NETWORK_ROOTS))
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            bare = isinstance(node.func, ast.Name) and node.func.id in DYNAMIC_BUILTINS
            attr = isinstance(node.func, ast.Attribute) and node.func.attr in {"import_module", "__import__"}
            if bare or attr:
                bad.append(f"dynamic import or exec, line {node.lineno}")
    return bad


def _is_zero(node) -> bool:
    return isinstance(node, ast.Constant) and node.value == 0


def fixed_hour_offenders(source: str) -> list[str]:
    """Anything that reads or builds an hour or minute of the day; only the 00:00 UTC day boundary is allowed."""
    bad = []
    for node in ast.walk(ast.parse(source)):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Attribute) and node.attr in {"hour", "minute", "timetuple", "utctimetuple"}:
            bad.append(f".{node.attr} line {line}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and HOUR_DIRECTIVES.search(node.value):
            bad.append(f"hour format line {line}")
        elif isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if any(k.arg in {"hour", "minute"} and not _is_zero(k.value) for k in node.keywords):
                bad.append(f"hour= line {line}")
            if name == "time" and any(not _is_zero(a) for a in node.args):
                bad.append(f"time() line {line}")
            if name == "datetime" and any(not _is_zero(a) for a in node.args[3:5]):
                bad.append(f"datetime() line {line}")
    return bad


def banned_hits(paths) -> list[str]:
    hits = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8", errors="replace").lower()
        hits += [f"{Path(path).name}: {name}" for name in BANNED if name in text]
    return hits


def dependency_files() -> list[Path]:
    names = [API_DIR / "pyproject.toml", API_DIR / "uv.lock", REPO_ROOT / "web" / "package.json",
             REPO_ROOT / "web" / "package-lock.json"]
    return [p for p in names if p.exists()]


def test_dependency_pinned_and_banned_names_absent():
    assert pc_adapter.PINNED_COMMIT == "20cb677039fcfe92d3d9c777aa9362e30ff1fdb8"
    assert re.fullmatch(r"[0-9a-f]{40}", pc_adapter.PINNED_COMMIT)
    files = [p for p in walk_py(API_DIR) if p.resolve() != THIS] + dependency_files() + [PC_FILES[-1]]
    assert not banned_hits(files)


def test_banned_guard_detects_a_planted_name(tmp_path):
    for i, name in enumerate(BANNED):
        planted = tmp_path / f"planted{i}.py"
        planted.write_text("import " + name.upper() + "\n", encoding="utf-8")
        assert banned_hits([planted]) == [f"planted{i}.py: {name}"]
    clean = tmp_path / "clean.py"
    clean.write_text("import json\n", encoding="utf-8")
    assert banned_hits([clean]) == []


def test_no_network_import_in_pure_modules():
    offenders = {p.name: bad for p in PC_FILES[:-1] if (bad := network_offenders(p.read_text(encoding="utf-8")))}
    assert not offenders


def test_network_guard_detects_planted_imports():
    planted = ("import ssl", "import asyncio", "from asyncio import open_connection", "from http import client",
               "import importlib", "importlib.import_module('socket')", "__import__('socket')",
               "exec('import socket')", "import urllib.request", "from requests import get")
    for src in planted:
        assert network_offenders(src), src
    assert network_offenders("import json\nimport re\nX = re.compile('a')\nfrom pathlib import Path\nimport os") == []


def test_no_detection_evasion_in_collector_files():
    hits = []
    for path in PC_FILES:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if EVASION.search(line):
                hits.append(f"{path.name}:{n}")
    assert not hits


def test_single_honest_user_agent_constant():
    assert web_queries.HONEST_USER_AGENT == "attention-probe/0.1"
    defs = [p.name for p in PC_FILES[:-1] if "HONEST_USER_AGENT =" in p.read_text(encoding="utf-8")]
    assert defs == ["web_queries.py"]


def test_install_docs_use_npm_ci_ignore_scripts():
    assert pc_adapter.INSTALL_COMMAND == "npm ci --ignore-scripts"
    bad = []
    for path in PC_FILES:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bnpm\s+(ci|install|i)\b", line) and "--ignore-scripts" not in line:
                bad.append(f"{path.name}:{n}")
    assert not bad


def test_wrapper_and_fake_expose_no_registry_publish_or_cookie_import():
    for obj in (pc_adapter.XAdapter, pc_adapter.FakeAdapter, pc_adapter.SafeAdapter):
        assert not [n for n in dir(obj) if not n.startswith("_") and pc_adapter.is_refused_name(n)]
    for name in ("registry", "publish", "cookie", "import_cookies", "pullRegistry"):
        assert pc_adapter.is_refused_name(name)
    for name in ("search_page", "self_repair", "page_size"):
        assert not pc_adapter.is_refused_name(name)


def test_collector_logs_use_class_and_status_helper_only():
    """Every logging call in the pure modules goes through `log_failure` (class name and status, nothing else)."""
    offenders = []
    for path in PURE_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"debug", "info", "warning", "error", "exception", "critical"}
                    and isinstance(node.func.value, ast.Name) and node.func.value.id in {"log", "logger", "logging"}):
                scrubbed = path.name == "pc_adapter.py" and node.func.attr != "exception" and not any(
                    k.arg == "exc_info" for k in node.keywords)
                if not scrubbed:
                    offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders


def test_no_fixed_utc_hour_in_pure_modules():
    """AC28 (pure part): nothing compares the clock to an hour of the day; only the 00:00 UTC day boundary exists."""
    offenders = {p.name: bad for p in PURE_MODULES if (bad := fixed_hour_offenders(p.read_text(encoding="utf-8")))}
    assert not offenders


def test_fixed_hour_guard_detects_planted_uses():
    planted = ("x = now.strftime('%H')", "h = now.timetuple()[3]", "now.replace(hour=9)", "time(9)",
               "datetime(2026, 1, 1, 9)", "if now.hour > 8: pass", "f'{now:%H}'", "datetime.time(17)",
               "now.utctimetuple()", "datetime(2026, 1, 1, 0, 30)", "now.strftime('%I %p')")
    for src in planted:
        assert fixed_hour_offenders(src), src
    clean = ("time(0)", "timedelta(hours=3)", "datetime.min.time()", "now.strftime('%Y-%m')",
             "datetime(2026, 1, 1)", "datetime(2026, 1, 1, 0, 0)", "datetime.combine(d, time(0), tzinfo=tz)")
    for src in clean:
        assert fixed_hour_offenders(src) == [], src


def test_no_machine_state_committed():
    """State and evidence paths resolve under the git-ignored cache root, never in tracked repo folders."""
    ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "api/data/cache/*" in ignore
    assert not [ln for ln in ignore if ln.startswith("!api/data/cache/attention")]
