"""Exact allow-list for the REA wrapper. Case-sensitive, first token only, no prefix or regex matching."""
from __future__ import annotations

import re

REA_VERSION = "6.4.0"
REA_PACKAGE = f"rea-agents@{REA_VERSION}"

STATIC_COMMANDS: frozenset[str] = frozenset(
    {
        "analyze-javascript-application",
        "recover-javascript-sources",
        "compare-javascript-export-shapes",
        "compare-application-versions",
        "compare-source-to-bundle",
        "trace-javascript-semantics",
        "trace-application-feature",
        "inspect-analysis-view",
        "inspect-evidence-bundle",
        "compare",
        "compare-web-captures",
        "compare-web-screenshots",
        "inspect-web-network-capture",
        "trace-web-module-imports",
        "trace-web-source-location",
        "export-web-scripts",
    }
)

# Live-browser group: runs only with --confirm-source <name> listed in a findings file.
LIVE_COMMANDS: frozenset[str] = frozenset(
    {"analyze-web-bundle", "capture-web-screenshot", "capture-browser-scenario", "inspect-web-page"}
)

ALLOWED_COMMANDS: frozenset[str] = STATIC_COMMANDS | LIVE_COMMANDS

_BASE_FLAGS: frozenset[str] = frozenset({"--json", "--source", "--output"})
ALLOWED_FLAGS: dict[str, frozenset[str]] = {cmd: _BASE_FLAGS for cmd in ALLOWED_COMMANDS}

ARG_RE = re.compile(r"^[A-Za-z0-9._/:@=-]{1,200}$")
FORBIDDEN_CHARS = frozenset('"%^&|<>')
