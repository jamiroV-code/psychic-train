"""T36 / S4: no verdict symbol survives in api/ or web/ source.

The same token list as the plan's `S4-verdict` grep, plus the old home-page
phrase. Skipped: build and dependency folders, this file and the two
carve-out tests that name the removed symbols on purpose
(`test_screener_no_verdict_contract.py`, `screener-api.test.ts`). The
allow-list holds the two hits outside S4's ownership; each entry must still
match, so a stale entry fails too.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ROOTS = ("api", "web")
EXTENSIONS = {".py", ".ts", ".tsx", ".svelte", ".css", ".js"}
SKIP_DIRS = {".venv", "node_modules", ".next", "public", "__pycache__"}
SKIP_FILES = {"test_no_verdict_symbols.py", "test_screener_no_verdict_contract.py", "screener-api.test.ts"}

TOKENS = (
    "ConfidenceBadge", "SignalDetailPanel", "NarrativeStrip", "LegTimelineBanner", "compute_badge",
    "derive_leg_context", "derive_narrative_state", "select_active_benchmark", "BenchmarkSelection",
    "active_benchmark", "MomentumState", "TrendState", "ConfidenceState", "ScalpView",
    "compute_scalp_momentum", "compute_dual_timeframe_momentum", "classify_momentum", "compute_trend",
    "momentum-state", "trend-direction", "confidence-badge", "signal-detail-panel", "scalp-rsi-reading",
    "/scalp", "fetchScalp", "leg_context", "narrative_state", "confidence over direction",
)
PATTERN = re.compile("|".join(re.escape(t) for t in TOKENS))

# Files outside S4's ownership that keep one removed name (path -> token).
ALLOW_LIST = {
    "api/analytics/narrative/mapping.py": "narrative_state",
    "api/scripts/seed_e2e_cache.py": "NarrativeStrip",
}


def _source_files():
    for root in ROOTS:
        for dirpath, dirnames, filenames in os.walk(REPO_ROOT / root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if name in SKIP_FILES or Path(name).suffix not in EXTENSIONS:
                    continue
                yield Path(dirpath) / name


def test_no_verdict_symbol_in_api_or_web_source():
    hits = []
    for path in _source_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in PATTERN.finditer(line):
                if ALLOW_LIST.get(rel) == match.group(0):
                    continue
                hits.append(f"{rel}:{lineno}: {match.group(0)}")
    assert not hits, "verdict symbols left behind:\n" + "\n".join(hits)


def test_allow_list_entries_still_match_something():
    for rel, token in ALLOW_LIST.items():
        path = REPO_ROOT / rel
        assert path.is_file(), f"allow-listed file is gone: {rel}"
        assert token in path.read_text(encoding="utf-8"), f"stale allow-list entry: {rel} no longer names {token}"
