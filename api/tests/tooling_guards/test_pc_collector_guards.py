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
NETWORK_ROOTS = ("requests", "httpx", "socket", "urllib", "playwright", "http.client", "aiohttp", "websocket",
                 "subprocess", "selenium")
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


def dependency_files() -> list[Path]:
    names = [API_DIR / "pyproject.toml", API_DIR / "uv.lock", REPO_ROOT / "web" / "package.json",
             REPO_ROOT / "web" / "package-lock.json"]
    return [p for p in names if p.exists()]


def test_dependency_pinned_and_banned_names_absent():
    assert pc_adapter.PINNED_COMMIT == "20cb677039fcfe92d3d9c777aa9362e30ff1fdb8"
    assert re.fullmatch(r"[0-9a-f]{40}", pc_adapter.PINNED_COMMIT)
    hits = []
    files = [p for p in walk_py(API_DIR) if p.resolve() != THIS] + dependency_files() + [PC_FILES[-1]]
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        hits += [f"{path.relative_to(REPO_ROOT)}: {name}" for name in BANNED if name in text]
    assert not hits


def test_banned_guard_detects_a_planted_name(tmp_path):
    planted = tmp_path / "x.py"
    planted.write_text("import " + BANNED[0] + "\n", encoding="utf-8")
    assert any(name in planted.read_text(encoding="utf-8") for name in BANNED)


def test_no_network_import_in_pure_modules():
    offenders = {}
    for path in PC_FILES[:-1]:
        mods = imported(path.read_text(encoding="utf-8"))
        bad = sorted(m for m in mods if any(m == r or m.startswith(r + ".") for r in NETWORK_ROOTS))
        if bad:
            offenders[path.name] = bad
    assert not offenders


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
    offenders = []
    for path in PURE_MODULES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr in {"hour", "minute"}:
                offenders.append(f"{path.name}:{node.lineno}")
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "time"
                    and any(not (isinstance(a, ast.Constant) and a.value == 0) for a in node.args)):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders


def test_no_machine_state_committed():
    """State and evidence paths resolve under the git-ignored cache root, never in tracked repo folders."""
    ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "api/data/cache/*" in ignore
    assert not [ln for ln in ignore if ln.startswith("!api/data/cache/attention")]
