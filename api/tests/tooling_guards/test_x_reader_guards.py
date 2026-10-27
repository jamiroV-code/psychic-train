"""W8d2 guards for the X reader (SPEC rules 17-20, AC41, AC53, AC55; PLAN section 7 hard stops).

Static checks over the reader module and the project files only: nothing is installed, the X library is never
imported, nothing is run against a provider.
"""
from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

from api.data.attention import twscrape_reader as tr
from api.data.attention import x_reader as xr
from api.tests.tooling_guards._common import API_DIR, walk_py
from api.tests.tooling_guards.test_pc_collector_guards import (
    EVASION,
    NETWORK_ROOTS,
    imported,
    lock_reset_or_debug_offenders,
)

READER = API_DIR / "data" / "attention" / "twscrape_reader.py"
SOURCE = READER.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
PYPROJECT = tomllib.loads((API_DIR / "pyproject.toml").read_text(encoding="utf-8"))
LOCK = tomllib.loads((API_DIR / "uv.lock").read_text(encoding="utf-8"))
# Built from split strings so this file never holds the names it bans.
BANNED = ("x" + "scrape", "klox" + "eld", "gunk" + "onchi")
LIBRARY_ROOTS = ("twscrape", "curl_cffi")
# The wrapped surface of the library (rule 20g); every other attribute named on a library object is refused.
REFUSED_ATTR = re.compile(r"^(login\w*|relogin\w*|add_account|reset_locks|user_by_\w+|tweet_details|search|imap\w*"
                          r"|set_log_level|mark_inactive|set_active|reactivate|delete_\w+|lock_until|unlock)$")


def _module_level_imports(tree: ast.Module) -> set[str]:
    mods = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module)
    return mods


def _function_imports(tree: ast.Module) -> dict[str, set[str]]:
    """Imports made inside each top-level function or method, by its name."""
    out: dict[str, set[str]] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(fn):
                if isinstance(node, ast.Import):
                    out.setdefault(fn.name, set()).update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    out.setdefault(fn.name, set()).add(node.module)
    return out


def _roots(mods, roots) -> set[str]:
    return {m for m in mods if any(m == r or m.startswith(r + ".") for r in roots)}


def xreader_group() -> list[str]:
    return PYPROJECT["dependency-groups"][tr.GROUP]


def lock_package(name: str) -> dict:
    return next(p for p in LOCK["package"] if p["name"] == name)


def test_default_env_does_not_install_or_import_twscrape(monkeypatch):
    groups = PYPROJECT["dependency-groups"]
    default = PYPROJECT.get("tool", {}).get("uv", {}).get("default-groups", ["dev"])
    assert tr.GROUP not in default and default == ["dev"]
    names = " ".join(PYPROJECT["project"]["dependencies"] + groups["dev"]).lower()
    assert "twscrape" not in names and "curl" not in names
    # The default lock root depends on the group only through the optional group.
    api = lock_package("api")
    assert "twscrape" not in {d["name"] for d in api.get("dependencies", [])}
    assert "twscrape" in {d["name"] for d in api["dev-dependencies"][tr.GROUP]}
    # Importing the reader module imports neither the library nor its HTTP backend.
    for name in ("twscrape", "twscrape.models", "curl_cffi"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.delitem(sys.modules, tr.__name__)
    __import__(tr.__name__)
    assert not {"twscrape", "curl_cffi"} & set(sys.modules)
    # Only the reader module names the library in an import, and only inside functions (lazy).
    others = [p for p in walk_py(API_DIR) if p.resolve() != READER.resolve()
              and "tests" not in p.relative_to(API_DIR).parts and ".venv" not in p.parts]
    assert not [p.name for p in others if _roots(imported(p.read_text(encoding="utf-8")), LIBRARY_ROOTS)]
    assert not _roots(_module_level_imports(TREE), LIBRARY_ROOTS)
    lazy = {fn for fn, mods in _function_imports(TREE).items() if _roots(mods, LIBRARY_ROOTS)}
    assert lazy == {"load_library"}


def test_no_network_import_at_module_level_and_subprocess_only_in_the_child_runner():
    top = _module_level_imports(TREE)
    assert not _roots(top, NETWORK_ROOTS + LIBRARY_ROOTS), sorted(top)
    by_fn = _function_imports(TREE)
    assert {fn for fn, mods in by_fn.items() if "subprocess" in mods} == {"run_child"}
    assert {fn for fn, mods in by_fn.items() if _roots(mods, ("asyncio",))} <= {"__init__", "refresh_cookies"}


def test_pinned_full_sha_required_short_sha_refused():
    assert tr.PINNED_COMMIT == xr.TWSCRAPE_PINNED_COMMIT == "63f61a518e576ea5c132f1156c03dda0520d76c1"
    group = xreader_group()
    assert tr.requirement_problems(group) == []
    short = [s.replace(tr.PINNED_COMMIT, tr.PINNED_COMMIT[:7]) for s in group]
    assert tr.requirement_problems(short) == ["twscrape:short_or_other_sha"]
    for ref in ("main", "v0.20.1", "0" * 40):
        bad = [s.replace(tr.PINNED_COMMIT, ref) for s in group]
        assert tr.requirement_problems(bad) == ["twscrape:short_or_other_sha"], ref
    assert tr.requirement_problems([s for s in group if "twscrape" not in s]) == ["twscrape:missing"]
    assert tr.requirement_problems(["twscrape==0.20.1"] + [s for s in group if "twscrape" not in s]) == [
        "twscrape:short_or_other_sha"]
    # The lock holds the git source at the full commit.
    assert lock_package("twscrape")["source"]["git"].endswith("#" + tr.PINNED_COMMIT)
    assert PYPROJECT["tool"]["uv"]["build-constraint-dependencies"] == ["hatchling==1.32.4"]


def test_only_package_name_twscrape_from_vladkens_url():
    group = xreader_group()
    assert [s for s in group if s.startswith("twscrape")] == [tr.REQUIREMENT]
    assert tr.REQUIREMENT == "twscrape @ git+https://github.com/vladkens/twscrape@" + tr.PINNED_COMMIT
    other_url = [s.replace("github.com/vladkens/", "github.com/someone/") for s in group]
    assert tr.requirement_problems(other_url) == ["twscrape:short_or_other_sha"]
    extra = group + ["requests==2.32.3"]
    assert tr.requirement_problems(extra) == ["requests:unknown"]
    assert set(tr.GROUP_PINS) | {"twscrape"} == {tr.req_name(s) for s in group}


def test_near_names_and_banned_names_refused():
    for name in ("tw-scrape", "twscraper", "twscrape2", "twsrcape", "tvvscrape", "py-twscrape"):
        assert tr.name_problem(name, "twscrape") == "near_name", name
    for name in BANNED + tuple(n.upper() for n in BANNED) + ("py-" + BANNED[0],):
        assert tr.name_problem(name, "twscrape") == "banned", name
    assert tr.name_problem("twscrape", "twscrape") is None
    assert tr.name_problem("Twscrape", "twscrape") is None
    assert tr.name_problem("loguru", "twscrape") == "unknown"
    group = xreader_group()
    assert tr.requirement_problems(group + [BANNED[1] + "==1.0"]) == [BANNED[1] + ":banned"]
    # No project file, lock entry or python file names a banned package.
    lock_names = {p["name"] for p in LOCK["package"]}
    assert not {n for n in lock_names if any(b in n.replace("-", "") for b in BANNED)}


def test_debug_true_never_used():
    assert lock_reset_or_debug_offenders(SOURCE) == []
    calls = [n for n in ast.walk(TREE) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "API"]
    assert calls and all({k.arg for k in c.keywords} == {"raise_when_no_account", "wait_timeout"} for c in calls)
    for c in calls:
        kw = {k.arg: k.value.value for k in c.keywords}
        assert kw == {"raise_when_no_account": True, "wait_timeout": 0}


def test_wrapped_surface_allowlist_and_no_cli_telemetry_import():
    mods = imported(SOURCE)
    assert _roots(mods, LIBRARY_ROOTS) == {"twscrape", "twscrape.models"}
    attrs = {n.attr for n in ast.walk(TREE) if isinstance(n, ast.Attribute)}
    assert not {a for a in attrs if REFUSED_ATTR.match(a)}
    assert {"add_account_cookies", "get", "search_raw", "parse_tweets", "API"} <= attrs
    for planted in ("api.pool.reset_locks()", "api.pool.login_all()", "api.pool.relogin(['a'])",
                    "api.pool.add_account('a', 'p', 'e', 'ep')", "api.user_by_login('x')", "api.search('q')",
                    "api.tweet_details(1)", "imap_login()"):
        tree = ast.parse(planted)
        assert {n.attr if isinstance(n, ast.Attribute) else n.id for n in ast.walk(tree)
                if isinstance(n, (ast.Attribute, ast.Name)) and REFUSED_ATTR.match(
                    n.attr if isinstance(n, ast.Attribute) else n.id)}, planted
    assert "twscrape.cli" not in mods and "twscrape.telemetry" not in mods
    assert not [ln for ln in SOURCE.splitlines() if EVASION.search(ln)]


def test_curl_wheel_hash_table_has_win_amd64_manylinux_and_musllinux_entries():
    assert set(tr.CURL_WHEELS) == {"win_amd64", "manylinux_x86_64", "musllinux_x86_64"}
    expect = {"win_amd64": "fe87b66e324ed7318166698e02169f3208dbda32b872a27d2bc61a9c19b335eb",
              "manylinux_x86_64": "a875a661e2f9a949be29454880bbb9553307a487c4c08819738298cf5c1622e2",
              "musllinux_x86_64": "20a7b1b473371cfaf2118958034977e457c6fa279fbd11543c9e0ab58be9eedd"}
    assert {k: v[1] for k, v in tr.CURL_WHEELS.items()} == expect
    wheels = {w["url"].rsplit("/", 1)[1]: w["hash"] for w in lock_package("curl-cffi")["wheels"]}
    for key, (wheel, sha) in tr.CURL_WHEELS.items():
        assert wheels[wheel] == "sha256:" + sha, key
        assert wheel.startswith("curl_cffi-0.16.3-cp310-abi3-")


def test_curl_cffi_exactly_0_16_3_wheel_hash_only_sdist_refused():
    pkg = lock_package("curl-cffi")
    assert pkg["version"] == "0.16.3" == tr.CURL_VERSION == xr.CURL_CFFI_PIN
    assert "curl-cffi" in PYPROJECT["tool"]["uv"]["no-build-package"]
    assert pkg["sdist"]["hash"] == "sha256:" + tr.CURL_SDIST_SHA  # recorded, never built (no-build-package)
    for pre in ("curl-cffi==0.16.4b1", "curl-cffi==0.17.0b1", "curl-cffi>=0.16.3", "curl-cffi==0.16.2"):
        bad = [pre if s.startswith("curl-cffi") else s for s in xreader_group()]
        assert tr.requirement_problems(bad) == ["curl-cffi:not_exact_pin"], pre


def test_curl_cffi_pinned_in_optional_group_and_lazy_import():
    assert "curl-cffi==0.16.3" in xreader_group()
    assert "curl" not in " ".join(PYPROJECT["project"]["dependencies"]).lower()
    # Our code never imports curl_cffi: the library imports it inside the fallback child only.
    assert not _roots(imported(SOURCE), ("curl_cffi",))
    assert "curl_cffi" not in sys.modules


def test_curl_cffi_exact_name_guard():
    for name in ("curl-cff", "curlcffi", "curl-cffi2", "curl_cfi", "curl-cffy"):
        assert tr.name_problem(name, "curl-cffi") == "near_name", name
    assert tr.name_problem("curl_cffi", "curl-cffi") is None
    group = [s.replace("curl-cffi", "curl-cffy") for s in xreader_group()]
    assert tr.requirement_problems(group) == ["curl-cffi:missing", "curl-cffy:near_name"]


def test_no_auto_update_code_path():
    lower = SOURCE.lower()
    for word in ("pip install", "uv add", "uv lock", "--upgrade", "git pull", "git fetch", "self_update",
                 "auto_update"):
        assert word not in lower, word
    calls = {getattr(n.func, "attr", getattr(n.func, "id", None)) for n in ast.walk(TREE) if isinstance(n, ast.Call)}
    assert not calls & {"system", "popen", "Popen", "check_call", "check_output", "call"}


def test_cookie_upsert_procedure_documented_and_guarded():
    doc = ast.get_docstring(TREE) or ""
    assert "add_account_cookies" in doc and "X_REFRESH_COOKIES" in doc and "--refresh-cookies" in doc
    attrs = [n.attr for n in ast.walk(TREE) if isinstance(n, ast.Attribute)]
    assert attrs.count("add_account_cookies") == 1 and "add_account" not in attrs
    # Cookies come from an environment variable, never from the command line or a file in the repo.
    assert '"X_REFRESH_COOKIES"' in SOURCE and "argv" not in re.sub(r"argv: list\[str\] \| None", "", SOURCE)
