---
name: spec:t16-root-readme
description: "Worker brief T16: add a root README.md that satisfies validate-guide-sync and links to operating-instructions.md (RT0, Gate 5/6 worker pilot)"
date: 03-10-26
feature: general
---

# T16 - add a root README.md that satisfies validate-guide-sync (worker brief)

**TL;DR:** create one file, `README.md` at the repo root: a short orientation page that links to the real docs instead of copying commands, and lists all 15 agents and 33 skills in the exact format `validate-guide-sync.mjs` reads. Done = guide-sync 0 failures, other validators unchanged.

Registry row: T16 in `process/MASTER-PLAN.md` (you do not edit it). Envelope: `t16-root-readme_REF_03-10-26.md` in this folder.

## Why

The repo has no root README. `validate-guide-sync.mjs` fails with `README.md does not exist` (the one guide-sync baseline failure). The page also gives a human a front door: what the project is, where things live, where the commands are.

## Format constraints (what validate-guide-sync reads; break these and it fails)

- Agents: a heading `## Agents` (digits optional, for example `## 1 Agents`) whose section holds table cells that are a backticked name, one per agent, ending at the next `##` heading or a line starting `---`.
- Skills: the heading MUST carry a number (`## 2 Skills`; with `## Skills` a test run printed 33 failures), then inline backticked folder names; the section ends at the next `##` heading.
- Every agent or skill on disk that is missing from the README is a failure; extra names only warn.
- Generate both lists from disk, do not type them: `ls .claude/agents` (15 files; use the name without `.md`) and `ls .claude/skills` (33 folders). Agents as a table, one row per agent, the first cell the backticked name (a short purpose cell is optional; take it from each agent's `description:` frontmatter if you add one, kept to a few words).

## Content outline (keep it short)

1. Title and two sentences: what the project is (a personal crypto/market tracker web app with a Python API; take the wording from `process/context/north-star.md` and link to it).
2. Layout: `api/` (Python API and data pipeline), `web/` (web app), `deploy/` (home-PC launchers), `process/` (plans, context, protocols), `.github/workflows/` (CI and snapshot jobs). One line each.
3. Commands: one sentence linking to `process/context/operating-instructions.md`. Do NOT copy any command. Also link `api/scripts/BOOTSTRAP.md` (first-time setup) and `deploy/README.md` (deploy runbook).
4. How work is organised: one or two lines on RIPER-5 (link `CLAUDE.md`), the task board (`process/MASTER-PLAN.md`) and the worker protocol (`process/development-protocols/master-planner.md`).
5. `## 1 Agents` table (15 rows) and `## 2 Skills` list (33 names), as above.

## Rules

- Public repository: no secrets, tokens, IP addresses, host names, personal details beyond what north-star.md already says.
- At most 120 lines and 8,000 bytes.
- No command text: the README must not contain `uv run`, `pnpm --`, `pnpm install`, `pnpm test`, `pnpm build`, `pnpm exec`, `pytest`, `vitest` or `uvicorn` (gate 5 checks this).
- Every path you write in backticks must exist (the planner's check G5-4 tests backticked `api/`, `web/`, `deploy/`, `process/` paths and `*.md` / `*.ps1` names).

## Expected gate results

Gate 0 before writing: guide-sync 1 failure (`README.md does not exist`). After: guide-sync 0; kit-portability 0; context-discovery exactly 1 (`.agents/skills does not resolve to .claude/skills`, an accepted baseline gap); validate-all-context 0; command grep 0 and `operating-instructions.md` count at least 1; `git diff --check` clean; diff only owned files; CI green on head.

## Report requests

Heading 9: ask the Master Planner to move T16 to `accepted` and then `archived` with the merge SHA. Heading 10: say whether the guide-sync baseline failure cleared, and note that adding or removing an agent or skill later makes guide-sync fail again until the README is updated (by design).
