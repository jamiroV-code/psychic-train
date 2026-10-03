---
name: context:operating-instructions
description: "Day-to-day operating rules: dev, test, build and deploy commands, env names, risk-tier test rules RT0-RT4, branch/worktree/merge rules, session start and end checklist."
keywords: commands, run, dev, test, build, deploy, pytest, vitest, playwright, tsc, uv, pnpm, risk tier, test policy, branch, worktree, merge, commit, session start, session end, env
date: 03-10-26
---

# Operating Instructions

**Run the API with `uv run --project api`, the web app with `pnpm --filter web`; pick tests by risk tier (RT0-RT4); workers use their own branch, everyone else commits on `main` only when asked.** Full test detail: `process/context/tests/all-tests.md`. Worker and merge protocol: master-planner.md.

## Commands

| Task | Command |
|---|---|
| Install web deps (fresh checkout) | `cd web && pnpm install --frozen-lockfile` (inside `web/`, never the repo root) |
| Run API (dev) | `uv run --project api uvicorn api.main:app --reload --host 127.0.0.1 --port 8000` |
| Run web (dev) | `pnpm --filter web dev` |
| Backend tests | `uv run --project api pytest api/ -q` (network tests opt-in: `-m integration`) |
| Frontend unit tests | `pnpm --filter web test` |
| Typecheck | `pnpm --filter web exec tsc --noEmit` |
| Chart islands | `pnpm --filter web build:islands` |
| Full web build | `pnpm --filter web build` (islands, then `next build`) |
| E2E | `cd web && pnpm test:e2e` (cloud container: set `PLAYWRIGHT_CHROMIUM_PATH` first, see all-tests.md) |
| Populate caches | runbook `api/scripts/BOOTSTRAP.md` |

**Deploy (user's home PC, Tailscale only):** pull, rebuild with `deploy/build-web.ps1` after any `web/` change, then restart the `mysite-api` / `mysite-web` scheduled tasks. Runbook and hard stops (no Funnel, no port forwarding, no `0.0.0.0`): `deploy/README.md`. Script behaviour on Windows is verifiable only on the PC.

**Env names** (values never in git): `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `LIQTIDE_ATTRIBUTION_URL`, `API_BASE_URL`, `API_PORT`; deploy also sets `SCREENER_CORS_ORIGINS` and `NEXT_PUBLIC_API_BASE_URL`.

## Risk-tier test rules (RT0-RT4)

RT = risk tier; T# is always a registry task. Run once, after the last edit.

| Tier | Change type | Required | Not required |
|---|---|---|---|
| RT0 Docs / low | markdown, process files, comments | `validate-plan-artifact.mjs <plan>` for plans; `validate-context-discovery.mjs` for context edits; `git diff --check` | pytest, vitest, Playwright |
| RT1 Localized UI | one component or page in `web/` | `pnpm --filter web test` (affected file, then suite); `tsc --noEmit` | pytest; Playwright unless a route or flow changed |
| RT2 Localized backend | one module or router in `api/` | pytest on the touched file, then `pytest api/ -q` once | vitest, Playwright |
| RT3 Shared logic | `cache.py`, response models, adapters used by 2+ routes | full pytest, full vitest, `tsc`, `build:islands`; contract snapshots unmodified | Playwright unless a route changed |
| RT4 High risk | auth, secrets, schema, public API, deploy/runtime, destructive data ops | all of RT3 + Playwright + evidence pack (`vc-risk-evidence-pack`) + user acceptance or a recorded agent-probe | none |

Validator scripts live under `.claude/skills/*/scripts/`. Budget: full-suite runs RT0 0, RT1/RT2 1, RT3 2, RT4 2 plus one vc-tester confirmation. Re-run only if files changed since the recorded SHA. A failing gate gets at most 2 fix cycles, then `blocked` or `needs_input`. One isolated re-run may classify a flake; log it as a backlog note. Live-provider checks are user-PC steps (container egress is blocked). CI (`ci.yml`) runs pytest, vitest, `tsc` and the island build; it has no e2e or lint job.

## Branch, worktree and merge rules

- **Default:** the Master Planner session and direct user work commit on `main`, and only when the user asks.
- **Workers:** branch `claude/<task-id>-<slug>`, one branch per registry task, open a PR. A worker may self-merge only when every condition in master-planner.md holds (CI green on head, tier tests independently confirmed, diff inside ownership, no conflicts, report committed, registry updated by the Master Planner). Unsure means stop at `review`.
- **Worktrees:** git worktrees exist only on the user's PC and are user-driven. Cloud sessions are isolated by container plus branch. No session removes a worktree.
- **Branch deletion:** only merged worker task branches, under the 02-10-26 standing consent, with an Approvals Log row in `process/archive/index.md` first. Every other branch needs per-branch user approval.
- **Shared files** (`.gitignore`, all-context.md, CLAUDE.md): one owning lane at a time.
- **Commits:** conventional prefix (`feat|fix|docs|spec|process|phase|chore|refactor|test`).

## Session start and end

Start: read your role's entry set (master-planner.md); check current-state.md for staleness; read the task row in `process/MASTER-PLAN.md` and the task brief; confirm owned files.

End: refresh current-state.md (planner only); update the registry row (planner only); write the report; commit or list any uncommitted work.
