"""Guard for the three nightly snapshot workflows' schedules and safety properties.

GitHub starts scheduled workflows ~2h late (observed up to ~2h20m). A run that
slips past UTC midnight dates its data as the next day, which is how the
narrative archive lost 2026-09-25. Every cron must therefore start at least
3h before midnight, and the three pushes to main stay staggered.
"""

from __future__ import annotations

import itertools
import re
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML ships transitively via uvicorn[standard]
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# workflow file -> the only cache directory it may stage
WORKFLOW_CACHE_DIRS = {
    "chain-growth-snapshot.yml": "api/data/cache/onchain/",
    "narrative-snapshot.yml": "api/data/cache/narrative/",
    "liqtide-snapshot.yml": "api/data/cache/liqtide/",
}

SCHEDULER_DELAY_BUFFER_MIN = 180
MIN_STAGGER_MIN = 20
MINUTES_PER_DAY = 1440


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _doc(name: str) -> dict:
    if yaml is None:
        pytest.skip("PyYAML unavailable; text checks still run")
    return yaml.safe_load(_text(name))


def _crons(name: str) -> list[str]:
    return re.findall(r'^\s*-\s*cron:\s*["\']?([^"\'\n]+?)["\']?\s*$', _text(name), re.M)


def _start_minute(cron: str) -> int:
    match = re.fullmatch(r"(\d{1,2}) (\d{1,2}) \* \* \*", cron.strip())
    assert match, f"unexpected cron shape {cron!r}; expected 'M H * * *'"
    minute, hour = int(match.group(1)), int(match.group(2))
    assert 0 <= minute < 60 and 0 <= hour < 24
    return hour * 60 + minute


@pytest.mark.parametrize("name", sorted(WORKFLOW_CACHE_DIRS))
def test_cron_starts_at_least_3h_before_utc_midnight(name: str) -> None:
    crons = _crons(name)
    assert len(crons) == 1, f"{name}: expected exactly one schedule, got {crons}"
    start = _start_minute(crons[0])
    assert start + SCHEDULER_DELAY_BUFFER_MIN < MINUTES_PER_DAY, (
        f"{name}: cron {crons[0]!r} leaves < 3h before UTC midnight for GitHub's scheduler delay"
    )


def test_crons_are_staggered() -> None:
    starts = {name: _start_minute(_crons(name)[0]) for name in WORKFLOW_CACHE_DIRS}
    for (a, sa), (b, sb) in itertools.combinations(starts.items(), 2):
        assert abs(sa - sb) >= MIN_STAGGER_MIN, f"{a} and {b} start {abs(sa - sb)} min apart"


@pytest.mark.parametrize("name", sorted(WORKFLOW_CACHE_DIRS))
def test_triggers_permissions_and_concurrency(name: str) -> None:
    doc = _doc(name)
    triggers = doc.get("on", doc.get(True))  # PyYAML parses a bare `on:` key as True
    assert isinstance(triggers, dict)
    assert "schedule" in triggers
    assert "pull_request" not in triggers
    assert "pull_request_target" not in triggers
    assert doc.get("permissions") == {"contents": "write"}
    concurrency = doc.get("concurrency")
    assert isinstance(concurrency, dict) and concurrency.get("group"), f"{name}: no concurrency group"
    assert concurrency.get("cancel-in-progress") is False


@pytest.mark.parametrize("name", sorted(WORKFLOW_CACHE_DIRS))
def test_commit_step_retries_push(name: str) -> None:
    text = _text(name)
    assert "git pull --rebase" in text
    assert "for attempt in 1 2 3" in text
    assert "nothing new to commit" in text


@pytest.mark.parametrize("name,cache_dir", sorted(WORKFLOW_CACHE_DIRS.items()))
def test_git_add_stages_only_own_cache_dir(name: str, cache_dir: str) -> None:
    add_lines = [ln.strip() for ln in _text(name).splitlines() if re.match(r"\s*git add\b", ln)]
    assert add_lines, f"{name}: no git add line"
    for line in add_lines:
        assert line == f"git add {cache_dir}", f"{name}: unexpected staging {line!r}"
