"""Guard for the five nightly snapshot workflows' schedules and safety properties.

GitHub starts scheduled workflows ~2h late (observed up to ~2h20m). A run that
slips past UTC midnight dates its data as the next day, which is how the
narrative archive lost 2026-09-25. Every cron must therefore start at least
3h before midnight, and the five pushes to main stay staggered.

Two of the five (`pairs-refresh-snapshot.yml`, `liquidity-backfill-snapshot.yml`)
own directories that are GITIGNORED under pipeline-completeness D1 and may not
exist at all on a fresh runner. A bare `git add` exits 128 (missing path) or 1
(present but ignored) and would fail those jobs every night, so they use the
tolerant staging form. The three older workflows keep the strict legacy form —
their checks are not relaxed by this reshape.
"""

from __future__ import annotations

import itertools
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML ships transitively via uvicorn[standard]
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# workflow file -> the cache directories it may stage (and no others)
WORKFLOW_CACHE_DIRS: dict[str, list[str]] = {
    "chain-growth-snapshot.yml": ["api/data/cache/onchain/"],
    "narrative-snapshot.yml": ["api/data/cache/narrative/"],
    "liqtide-snapshot.yml": ["api/data/cache/liqtide/"],
    "pairs-refresh-snapshot.yml": ["api/data/cache/ohlcv/", "api/data/cache/pairs/"],
    "liquidity-backfill-snapshot.yml": ["api/data/cache/liquidity/"],
}

# Workflows whose owned directories are gitignored (D1), so their `git add`
# must not be able to fail the job.
TOLERANT_STAGING = {"pairs-refresh-snapshot.yml", "liquidity-backfill-snapshot.yml"}

# workflow file -> the api.scripts module(s) it must invoke, in order
WORKFLOW_MODULES: dict[str, list[str]] = {
    "pairs-refresh-snapshot.yml": ["api.scripts.refresh_cache", "api.scripts.compute_pairs"],
    "liquidity-backfill-snapshot.yml": ["api.scripts.backfill_primaries"],
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


def _steps(name: str) -> list[dict]:
    jobs = _doc(name)["jobs"]
    assert len(jobs) == 1, f"{name}: expected exactly one job, got {sorted(jobs)}"
    return list(jobs["snapshot"]["steps"])


def _step_index(steps: list[dict], *, step_id: str | None = None, name_contains: str | None = None) -> int:
    for i, step in enumerate(steps):
        if step_id is not None and step.get("id") == step_id:
            return i
        if name_contains is not None and name_contains.lower() in str(step.get("name", "")).lower():
            return i
    raise AssertionError(f"no step matching id={step_id!r} name~{name_contains!r}")


def _crons(name: str) -> list[str]:
    return re.findall(r'^\s*-\s*cron:\s*["\']?([^"\'\n]+?)["\']?\s*$', _text(name), re.M)


def _start_minute(cron: str) -> int:
    match = re.fullmatch(r"(\d{1,2}) (\d{1,2}) \* \* \*", cron.strip())
    assert match, f"unexpected cron shape {cron!r}; expected 'M H * * *'"
    minute, hour = int(match.group(1)), int(match.group(2))
    assert 0 <= minute < 60 and 0 <= hour < 24
    return hour * 60 + minute


def _add_lines(name: str) -> list[str]:
    return [ln.strip() for ln in _text(name).splitlines() if re.match(r"\s*git add\b", ln)]


def _staged_dirs(name: str) -> list[str]:
    """The directories each `git add` line stages, with the per-workflow form
    enforced: tolerant for the gitignored-dir workflows, strict legacy
    otherwise."""
    lines = _add_lines(name)
    assert lines, f"{name}: no git add line"
    dirs: list[str] = []
    for line in lines:
        if name in TOLERANT_STAGING:
            m = re.fullmatch(r"git add -A -- (\S+) 2>/dev/null \|\| true", line)
            assert m, f"{name}: staging line is not the tolerant form: {line!r}"
        else:
            m = re.fullmatch(r"git add (\S+)", line)
            assert m, f"{name}: staging line is not the strict legacy form: {line!r}"
        dirs.append(m.group(1))
    return dirs


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
    assert "workflow_dispatch" in triggers, f"{name}: no manual trigger (AC-1)"
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


@pytest.mark.parametrize("name,cache_dirs", sorted(WORKFLOW_CACHE_DIRS.items()))
def test_git_add_stages_only_own_cache_dirs(name: str, cache_dirs: list[str]) -> None:
    staged = _staged_dirs(name)
    assert len(staged) == len(set(staged)), f"{name}: duplicate staging line {staged}"
    assert set(staged) == set(cache_dirs), f"{name}: unexpected staging {staged}"


@pytest.mark.parametrize("name", sorted(WORKFLOW_CACHE_DIRS))
def test_no_force_add(name: str) -> None:
    """Force-adding would bypass the D1 decision that nothing new is committed."""
    for line in _add_lines(name):
        assert not re.search(r"\s(-f|--force)\b", line), f"{name}: force-add {line!r}"


# ------------------------------------------------------ new workflow structure


@pytest.mark.parametrize("name,modules", sorted(WORKFLOW_MODULES.items()))
def test_new_workflows_run_the_expected_module(name: str, modules: list[str]) -> None:
    text = _text(name)
    for module in modules:
        assert f"python -m {module}" in text, f"{name}: does not invoke {module}"


def test_pairs_workflow_orders_refresh_before_compute() -> None:
    """AC-2: one job, refresh strictly before compute, so compute sees this
    run's bars."""
    steps = _steps("pairs-refresh-snapshot.yml")
    refresh = _step_index(steps, step_id="refresh")
    compute = _step_index(steps, step_id="compute")
    assert refresh < compute
    assert "api.scripts.refresh_cache" in steps[refresh]["run"]
    assert "api.scripts.compute_pairs" in steps[compute]["run"]


def test_pairs_workflow_compute_runs_regardless_of_refresh_exit_code() -> None:
    """AC-2: compute is unconditional, and neither run-block exits early.

    E1: `exit` is matched as a shell STATEMENT, never as a substring —
    `exit_code=$code` is required and legitimate. The commit step keeps the
    template's own `exit 0` / `exit 1`, so this check is scoped to the two
    run-blocks only.
    """
    steps = _steps("pairs-refresh-snapshot.yml")
    compute = steps[_step_index(steps, step_id="compute")]
    assert "if" not in compute, "compute step must not be conditional on the refresh outcome"

    for step_id in ("refresh", "compute"):
        run = steps[_step_index(steps, step_id=step_id)]["run"]
        assert "set +e" in run, f"{step_id}: must not abort the step on a non-zero code"
        assert 'echo "exit_code=$code" >> "$GITHUB_OUTPUT"' in run
        assert re.search(r"(?m)^\s*exit\b", run) is None, f"{step_id}: run-block exits early"


@pytest.mark.parametrize("name,ids", [
    ("pairs-refresh-snapshot.yml", ["refresh", "compute"]),
    ("liquidity-backfill-snapshot.yml", ["backfill"]),
])
def test_crash_skips_commit_and_fails_job(name: str, ids: list[str]) -> None:
    """C1: the 0/2 contract is an allow-list — 137, 124 or an empty recorded
    code must skip the commit AND fail the job."""
    steps = _steps(name)
    commit = _step_index(steps, name_contains="commit")
    fail = _step_index(steps, name_contains="fail the job")
    assert commit < fail, f"{name}: the fail step must come after the commit step"

    commit_if = steps[commit]["if"]
    for step_id in ids:
        assert f"steps.{step_id}.outputs.exit_code == '0'" in commit_if
        assert f"steps.{step_id}.outputs.exit_code == '2'" in commit_if

    fail_if = steps[fail]["if"]
    for step_id in ids:
        assert f"steps.{step_id}.outputs.exit_code != '0'" in fail_if
        assert f"steps.{step_id}.outputs.exit_code != '2'" in fail_if
    assert re.search(r"(?m)^\s*exit 1\b", steps[fail]["run"]), f"{name}: fail step does not exit 1"


@pytest.mark.parametrize("name", sorted(WORKFLOW_MODULES))
def test_warn_step_fires_only_on_exit_two(name: str) -> None:
    warns = [s for s in _steps(name) if "::warning::" in str(s.get("run", ""))]
    assert warns, f"{name}: no warning step for the degraded (exit 2) case"
    for step in warns:
        assert re.fullmatch(r"steps\.\w+\.outputs\.exit_code == '2'", step["if"].strip())


# ------------------------------------------------- tolerant staging, for real


@pytest.mark.parametrize("name", sorted(TOLERANT_STAGING))
@pytest.mark.parametrize("scenario", ["absent", "present_and_ignored"])
def test_tolerant_git_add_exits_zero_when_path_missing_or_ignored(
    tmp_path, name: str, scenario: str
) -> None:
    """AC-3 / AC-11a: the real git failure modes (128 missing, 1 ignored) are
    neutralized, and nothing is staged either way.

    E5: every subprocess is pinned to the temp repo via `cwd`, and the repo
    root is asserted before the extracted line runs — this must never touch
    the real tree. The ignore rule is a MINIMAL local one, not a copy of the
    live `.gitignore`, so a future P2 un-ignore cannot make this misleading.
    """
    if shutil.which("git") is None or shutil.which("bash") is None:
        pytest.skip("git and bash are required for the tolerant-staging subprocess check")

    repo = tmp_path / "repo"
    repo.mkdir()

    def run(*args, **kw):
        return subprocess.run(args, cwd=repo, capture_output=True, text=True, **kw)

    assert run("git", "init", "-q").returncode == 0
    run("git", "config", "user.email", "t@example.com")
    run("git", "config", "user.name", "t")
    (repo / ".gitignore").write_text("api/data/cache/*\n", encoding="utf-8")
    assert run("git", "add", ".gitignore").returncode == 0

    toplevel = run("git", "rev-parse", "--show-toplevel").stdout.strip()
    assert os.path.realpath(toplevel) == os.path.realpath(repo), (
        "refusing to run the extracted git add outside the temp repo"
    )

    for cache_dir in WORKFLOW_CACHE_DIRS[name]:
        if scenario == "present_and_ignored":
            target = repo / cache_dir
            target.mkdir(parents=True, exist_ok=True)
            (target / "seed.parquet").write_bytes(b"x")

    for line in _add_lines(name):
        proc = run("bash", "-e", "-c", line)
        assert proc.returncode == 0, f"{name}: {line!r} exited {proc.returncode}: {proc.stderr}"

    staged = run("git", "diff", "--staged", "--name-only").stdout.split()
    assert staged == [".gitignore"], f"{name}: unexpectedly staged {staged}"
