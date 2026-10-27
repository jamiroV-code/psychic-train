"""W8c guards for the Reddit collector modules (SPEC AC25, AC28, AC29, AC36; PLAN W8c).

Static checks over the explicit file list of the Reddit collector; a file whose slice has not landed yet (W8c2
`reddit_stream.py`, W8c3 `reddit_engagement.py`) is skipped until it exists. Nothing is run against a provider.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from api.tests.tooling_guards._common import API_DIR
from api.tests.tooling_guards.test_pc_collector_guards import EVASION, fixed_hour_offenders, network_offenders

ATTENTION = API_DIR / "data" / "attention"
REDDIT_FILES = [ATTENTION / f for f in
                ("reddit_web.py", "reddit_items.py", "reddit_metrics.py", "reddit_stream.py", "reddit_engagement.py")]
# Modules that may send HTTP (the connector and its later siblings); the ledger and the metrics stay pure.
HTTP_ALLOWED = {"reddit_web.py", "reddit_stream.py", "reddit_engagement.py"}
BROWSER_UA = re.compile(r"Mozilla/|AppleWebKit|Chrome/\d|Safari/\d|Gecko/|Firefox/|Edg/|OPR/", re.IGNORECASE)
REDDIT_JSON = re.compile(r"reddit\.com\S*\.json|search\.json|/\.json|\.json\?|oauth\.reddit|api\.reddit|/api/v1/"
                         r"|old\.reddit")
ARCHIVE_SEARCH = re.compile(r"/api/(posts|comments|subreddits|users)/search|/aggregate|push" + r"shift",
                            re.IGNORECASE)
UA_LITERAL = re.compile(r"['\"]user-agent['\"]\s*:\s*['\"]|USER_AGENT\s*=\s*['\"]", re.IGNORECASE)
USERNAME_FIELD = re.compile(r"['\"](author|username|author_name|user_name)['\"]\s*:")
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}


def present() -> list[Path]:
    return [p for p in REDDIT_FILES if p.exists()]


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


def test_file_list_is_explicit_and_w8c_files_exist():
    names = {p.name for p in present()}
    assert {"reddit_web.py", "reddit_items.py", "reddit_metrics.py"} <= names


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


def test_ledger_and_metrics_are_pure_and_connector_uses_httpx_only():
    for path in present():
        bad = network_offenders(path.read_text(encoding="utf-8"))
        if path.name in HTTP_ALLOWED:
            assert set(bad) <= {"httpx"}, (path.name, bad)
        else:
            assert bad == [], (path.name, bad)


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
