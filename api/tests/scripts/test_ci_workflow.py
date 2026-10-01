"""Guard for `.github/workflows/ci.yml` (MASTER-PLAN T13).

The five snapshot workflows have their own guard (`test_snapshot_workflow_schedules.py`), which is
parametrized over an explicit dict and deliberately does not see this file. CI has the opposite
safety profile to a snapshot job — it must NOT be able to write to the repo, and it SHOULD cancel
superseded runs — so the properties worth pinning are different ones.

No network, no YAML round-trip beyond a parse: this reads the file the way the sibling guard does.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

CI = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"


def _doc() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def _triggers(doc: dict) -> dict:
    # PyYAML parses a bare `on:` key as the boolean True, not the string "on".
    return doc[True] if True in doc else doc["on"]


def test_ci_workflow_exists():
    assert CI.is_file(), "ci.yml is the only thing gating PRs; it must exist"


def test_ci_is_read_only():
    """CI runs on pull_request, so it must never hold write access.

    A `pull_request` trigger with `contents: write` is the shape that lets a PR from anywhere
    mutate the repo. The snapshot workflows need write and therefore deliberately have no
    pull_request trigger; this one is the mirror image.
    """
    doc = _doc()
    assert doc.get("permissions") == {"contents": "read"}, (
        "ci.yml must declare exactly `permissions: contents: read`"
    )
    text = CI.read_text(encoding="utf-8")
    assert "secrets." not in text, "ci.yml needs no secrets; none of its checks hit a keyed provider"
    assert "git push" not in text and "git commit" not in text, "CI must not write to the repo"


def test_ci_runs_on_pull_requests_and_main():
    triggers = _triggers(_doc())
    assert "pull_request" in triggers, "the whole point is gating PRs"
    assert "push" in triggers
    assert triggers["push"]["branches"] == ["main"]
    # Data-only bot commits prove nothing and should not burn minutes.
    assert "api/data/cache/**" in triggers["push"]["paths-ignore"]


def test_ci_cancels_superseded_runs():
    """Opposite of the snapshot workflows, which must never cancel mid-archive."""
    doc = _doc()
    assert doc["concurrency"]["cancel-in-progress"] is True


def test_ci_runs_every_local_gate():
    """The four commands a contributor runs before pushing."""
    text = CI.read_text(encoding="utf-8")
    for fragment in (
        "uv run --project api pytest api/ -q",
        "pnpm --filter web test",
        "pnpm --filter web exec tsc --noEmit",
        "pnpm build:islands",
    ):
        assert fragment in text, f"ci.yml must run `{fragment}`"


def test_web_install_runs_inside_web_dir():
    """`pnpm install` from the repo root does not work — there is no root package.json."""
    doc = _doc()
    steps = doc["jobs"]["web"]["steps"]
    install = [s for s in steps if "pnpm install" in str(s.get("run", ""))]
    assert len(install) == 1, "expected exactly one pnpm install step"
    assert install[0].get("working-directory") == "web", (
        "pnpm install must run in web/, not the repo root"
    )
