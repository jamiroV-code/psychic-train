"""W8c guards for the Reddit collector modules (SPEC AC25, AC28, AC29, AC36; PLAN W8c; finish plan table H).

Static checks over every `reddit_*.py` and `browser_*.py` module under `api/data/attention/` (globs, so later Reddit
and browser modules are scanned without list edits); each module that needs one has its own narrow exemption below.
Nothing is run against a provider.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from api.tests.tooling_guards._common import API_DIR
from api.tests.tooling_guards.test_pc_collector_guards import (
    EVASION,
    fixed_hour_offenders,
    network_offenders,
)

ATTENTION = API_DIR / "data" / "attention"
GLOBS = ("reddit_*.py", "browser_*.py")
# Modules that may send HTTP through httpx (the connector and its later siblings); the ledger and metrics stay pure.
HTTP_ALLOWED = {"reddit_web.py", "reddit_stream.py", "reddit_engagement.py"}
# Pure modules of the Reddit live core (finish plan S-RCore-A): no network import at all.
LIVE_CORE_PURE = {"reddit_core.py", "reddit_surface.py", "reddit_live.py"}
# Narrow exemption: `reddit_core.py` resolves the `LiveMethod` factory table by lazy `importlib.import_module`
# (RC-9), exactly once; nothing else in it may import or run code by name.
FACTORY_IMPORT = {"reddit_core.py": 1}
# Finish plan table H amendment (S-Relay): the loopback CONNECT relay and the A19 self-test are the ONLY
# `browser_*` modules allowed network imports, each limited to exactly this set.
BROWSER_NETWORK = {"browser_relay.py": {"asyncio", "socket", "ssl"}, "browser_selftest.py": {"socket", "subprocess"}}
# S-RGQL: `reddit_gql.py` runs the hardened B2 async clients (`x_proxy_transport`) from its sync method, so it may
# import `asyncio` and nothing else network-capable (no httpx/socket/ssl of its own).
GQL_NETWORK = {"reddit_gql.py": {"asyncio"}}
BROWSER_UA = re.compile(r"Mozilla/|AppleWebKit|Chrome/\d|Safari/\d|Gecko/|Firefox/|Edg/|OPR/", re.IGNORECASE)
REDDIT_JSON = re.compile(r"reddit\.com\S*\.json|search\.json|/\.json|\.json\?|oauth\.reddit|api\.reddit|/api/v1/"
                         r"|old\.reddit")
ARCHIVE_SEARCH = re.compile(r"/api/(posts|comments|subreddits|users)/search|/aggregate|push" + r"shift",
                            re.IGNORECASE)
UA_LITERAL = re.compile(r"['\"]user-agent['\"]\s*:\s*['\"]|USER_AGENT\s*=\s*['\"]", re.IGNORECASE)
USERNAME_FIELD = re.compile(r"['\"](author|username|author_name|user_name)['\"]\s*:")
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}


def present() -> list[Path]:
    return sorted({p for g in GLOBS for p in ATTENTION.glob(g)})


def offenders(text: str) -> list[str]:
    """Every banned access pattern in one module's text: browser UA, Reddit JSON endpoint, archive search path."""
    out = []
    for label, pattern in (("browser user agent", BROWSER_UA), ("reddit json endpoint", REDDIT_JSON),
                           ("archive search or aggregate path", ARCHIVE_SEARCH), ("user agent literal", UA_LITERAL),
                           ("evasion", EVASION)):
        if pattern.search(text):
            out.append(label)
    return out


def log_offenders(text: str) -> list[str]:
    """Logging calls other than `pc_adapter.log_failure` (class name and status only)."""
    bad = []
    for node in ast.walk(ast.parse(text)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LOG_METHODS
                and isinstance(node.func.value, ast.Name) and node.func.value.id in {"log", "logger", "logging"}):
            bad.append(f"line {node.lineno}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            bad.append(f"print line {node.lineno}")
    return bad


def test_file_globs_cover_w8c_and_the_live_core():
    names = {p.name for p in present()}
    assert {"reddit_web.py", "reddit_items.py", "reddit_metrics.py"} <= names
    assert LIVE_CORE_PURE <= names
    assert "reddit.py" not in names  # the official-API fetcher has its own guards


def test_no_browser_ua_json_endpoint_archive_search_or_evasion():
    bad = {p.name: hits for p in present() if (hits := offenders(p.read_text(encoding="utf-8")))}
    assert not bad


def test_guard_fails_on_browser_ua_json_endpoint_or_archive_search_path(tmp_path):
    planted = {
        "ua.py": 'H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36"}\n',
        "json.py": 'URL = "https://www.reddit.com/r/CryptoCurrency/search.json?q=sol"\n',
        "json2.py": 'URL = "https://www.reddit.com/r/x/new/.json"\n',
        "old.py": 'URL = "https://old.reddit.com/r/x/new/"\n',
        "archive.py": 'URL = "https://arctic-shift.photon-reddit.com/api/posts/search?title=sol"\n',
        "agg.py": 'URL = "https://arctic-shift.photon-reddit.com/api/comments/search/aggregate"\n',
        "ualit.py": 'USER_AGENT = "my-agent/1.0"\n',
    }
    for name, text in planted.items():
        assert offenders(text), name
    clean = ('from api.data.attention.web_queries import HONEST_USER_AGENT as USER_AGENT\n'
             'URL = "https://www.reddit.com/r/x/search.rss"\nIDS = "https://arctic-shift.photon-reddit.com/api/posts/ids"\n'
             'P = f"{1}.json"\n')
    assert offenders(clean) == []


def _exempted(name: str, bad: list[str]) -> list[str]:
    """Drop a module's narrow exemption: the factory table's one lazy `importlib` call (RC-9), or the
    relay/self-test network import set."""
    if name in BROWSER_NETWORK or name in GQL_NETWORK:
        allowed_set = BROWSER_NETWORK.get(name) or GQL_NETWORK[name]
        return [b for b in bad if b not in allowed_set]
    allowed = FACTORY_IMPORT.get(name, 0)
    if not allowed:
        return bad
    dynamic = [b for b in bad if b.startswith("dynamic import or exec")]
    rest = [b for b in bad if b != "importlib" and b not in dynamic]
    return rest if len(dynamic) == allowed else bad


def test_ledger_and_metrics_are_pure_and_connector_uses_httpx_only():
    for path in present():
        bad = _exempted(path.name, network_offenders(path.read_text(encoding="utf-8")))
        if path.name in HTTP_ALLOWED:
            assert set(bad) <= {"httpx", "urllib.parse"}, (path.name, bad)  # urllib.parse: string quoting only
        else:
            assert bad == [], (path.name, bad)


def test_factory_exemption_is_narrow():
    one = "import importlib\nm = importlib.import_module(name)\n"
    assert _exempted("reddit_core.py", network_offenders(one)) == []
    two = one + "n = importlib.import_module(other)\n"
    assert _exempted("reddit_core.py", network_offenders(two))
    assert _exempted("reddit_core.py", network_offenders(one + "import httpx\n")) == ["httpx"]
    assert _exempted("reddit_live.py", network_offenders(one))


def test_browser_network_exemption_is_narrow():
    relay = "import asyncio\nimport socket\nimport ssl\n"
    assert _exempted("browser_relay.py", network_offenders(relay)) == []
    assert _exempted("browser_relay.py", network_offenders(relay + "import httpx\n")) == ["httpx"]
    assert _exempted("browser_selftest.py", network_offenders("import socket\nimport subprocess\n")) == []
    assert _exempted("browser_selftest.py", network_offenders("import ssl\n"))
    for other in ("browser_host.py", "browser_cdp.py", "browser_profile.py", "browser_session.py", "reddit_web.py",
                  "reddit_core.py"):
        assert _exempted(other, network_offenders(relay)), other


def test_gql_network_exemption_is_narrow():
    assert _exempted("reddit_gql.py", network_offenders("import asyncio\n")) == []
    for extra in ("httpx", "socket", "ssl", "subprocess"):
        assert _exempted("reddit_gql.py", network_offenders(f"import asyncio\nimport {extra}\n")) == [extra]
    for other in ("reddit_live.py", "reddit_core.py", "reddit_browser.py"):
        assert _exempted(other, network_offenders("import asyncio\n")), other


def test_no_fixed_utc_hour_in_reddit_modules():
    bad = {p.name: hits for p in present() if (hits := fixed_hour_offenders(p.read_text(encoding="utf-8")))}
    assert not bad


def test_reddit_modules_log_through_the_class_and_status_helper_only():
    bad = {p.name: hits for p in present() if (hits := log_offenders(p.read_text(encoding="utf-8")))}
    assert not bad
    assert log_offenders('import logging\nlog = logging.getLogger(1)\nlog.warning("x %s", e)\n')
    assert log_offenders('print("x")\n')


def test_no_username_field_in_stored_rows():
    bad = [p.name for p in present() if USERNAME_FIELD.search(p.read_text(encoding="utf-8"))]
    assert not bad
    assert USERNAME_FIELD.search('row = {"author": name}')
