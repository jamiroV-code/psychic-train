"""T217 guards (file-only): the entry block is identical in CLAUDE.md and AGENTS.md, no doc still says planners
commit straight to main, and the PC sync scripts never merge, rebase, reset or force."""

from __future__ import annotations

import re

from api.tests.tooling_guards._common import REPO_ROOT

START = "## Session Entry Set and Role Selection"
END = "## RIPER-5 Spec-Driven Development System"
SCRIPTS = REPO_ROOT / "scripts" / "pc-sync"
DOCS = (
    "CLAUDE.md",
    "AGENTS.md",
    "process/development-protocols/implementation-standards.md",
    "process/development-protocols/master-planner.md",
    "process/context/operating-instructions.md",
)
OLD_RULES = (
    re.compile(
        r"commit\w*\s+(only when the user asks,\s+)?directly on `main`", re.IGNORECASE
    ),
    re.compile(r"commit on `main` by default", re.IGNORECASE),
    re.compile(r"commit on `main`,? only when", re.IGNORECASE),
    re.compile(r"everyone else commits on `main`", re.IGNORECASE),
    re.compile(r"direct user work commit on `main`", re.IGNORECASE),
)


def _block(name: str) -> str:
    text = (REPO_ROOT / name).read_text(encoding="utf-8")
    return text[text.index(START) : text.index(END)]


def test_entry_block_identical():
    assert _block("CLAUDE.md") == _block("AGENTS.md")


def test_no_doc_says_planners_commit_to_main():
    for name in DOCS:
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        for rx in OLD_RULES:
            assert not rx.search(text), (
                f"{name} still states the old main-commit rule: {rx.pattern}"
            )


def test_new_policy_stated():
    text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "owner merges" in text.lower() and "nobody pushes to `main`" in text


def test_pc_scripts_exist_and_have_whatif():
    for name in ("sync-main.ps1", "push-task-branch.ps1"):
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "[switch]$WhatIf" in text, name
    assert (SCRIPTS / "README.md").is_file()


def test_pc_scripts_never_rewrite_history():
    banned = re.compile(
        r"--force|--force-with-lease|git\s+push\b.*\s-f\b|git\s+(merge(?!-base)|rebase|reset|push\s+origin\s+main)\b",
        re.IGNORECASE,
    )
    for p in SCRIPTS.glob("*.ps1"):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            assert not banned.search(line), f"{p.name}:{n}: {line.strip()}"


def test_pc_scripts_hold_no_secrets():
    rx = re.compile(
        r"(\d{1,3}\.){3}\d{1,3}|ghp_|github_pat_|cookie\s*=|password\s*=", re.IGNORECASE
    )
    for p in SCRIPTS.iterdir():
        assert not rx.search(p.read_text(encoding="utf-8")), p.name
