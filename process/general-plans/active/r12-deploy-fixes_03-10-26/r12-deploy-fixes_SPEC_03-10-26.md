---
name: spec:r12-deploy-fixes
description: "Brief R12 (blocked, HIGH-RISK deploy class, brief only): kill-by-port before build, stale-build guard in start-web, post-start smoke check; needs VALIDATE and the user's explicit confirmation; runtime verifiable only on the home PC"
date: 03-10-26
feature: general
---

# R12 - deploy fixes (brief only; HIGH-RISK deploy class)

**TL;DR:** Three small changes to the PowerShell launchers so a restart after a `web/` change cannot serve a stale build. Status `blocked`: no worker may start. Required first: VALIDATE, then the user's explicit confirmation of THIS brief (decision G5-K8 recorded that R12 becomes `approved` only on that confirmation), and a home-PC verification path (below).

Registry row: R12 in `process/MASTER-PLAN.md` (parent P2, supersedes P2b). Envelope after VALIDATE and confirmation (`r12-deploy-fixes_REF_03-10-26.md`). Class: deploy/runtime = RT4.

## Problem

The 2026-10-01 live incident: a web restart kept serving an old build because an old process held the port and no guard compared the served build to the source. Current launchers are in `deploy/` (`build-web.ps1`, `start-web.ps1`, `start-api.ps1`, `_common.ps1`, `register-tasks.ps1`, `README.md`).

## Changes (to be refined in VALIDATE)

1. **Kill-by-port before build:** before `build-web.ps1` builds and before `start-web.ps1` binds, find the process listening on `WebPort` (config) and stop it; log which PID was stopped; do nothing if the port is free; never kill by process name.
2. **Stale-build guard in `start-web`:** refuse to start (non-zero exit, clear message) when the built output is older than the newest tracked source under `web/` or its recorded commit differs from `git rev-parse HEAD`; mechanism (marker file written by `build-web.ps1` vs timestamp compare) decided in VALIDATE.
3. **Post-start smoke check:** after start, poll the configured URL for HTTP 200 within a bounded timeout and (if a build marker exists) confirm the served build id equals the marker; non-zero exit and log line on failure.

## Hard constraints

- No secrets in scripts or logs; no network calls beyond localhost; bounded loops and timeouts; `-DryRun` behaviour of existing scripts preserved.
- The existing shape tests (`api/tests/deploy/`) must stay green; new shape tests assert the script text only (they cannot prove runtime behaviour).

## Verification path (why it is blocked)

CI and the cloud container have no Windows, PowerShell or Tailscale; script text can be checked in CI, runtime cannot. Per master-planner.md section 5 item 5 the task stops at `review` and the user verifies on the home PC: backlog note `process/general-plans/backlog/deploy-runtime-user-pc-verification_NOTE_02-10-26.md` (run the `deploy/README.md` parse check and dry runs, then a real restart after a `web/` change, confirm the served build matches HEAD, record date, commit and result). R12 may not move past `review` without that record. Blocked until the user states the verification will be done (or a path is agreed).

## Acceptance (proposed)

Shape tests for the three behaviours pass in CI; `deploy/README.md` documents the three steps; the user's home-PC record exists (only then `accepted`).

## Ownership

- Owned: `deploy/build-web.ps1`, `deploy/start-web.ps1`, `deploy/_common.ps1`, `deploy/README.md`, `api/tests/deploy/test_deploy_config_shape.py` (new or changed tests in `api/tests/deploy/`), this task folder. After T18 merges, this task also rewords `deploy/README.md` lines ~104-105 and the matching assertion in `test_deploy_config_shape.py` (they name the removed `write/read_confirmed_boundaries`).
- Forbidden: `deploy/config.example.psd1` secrets-adjacent values beyond documented keys, `deploy/register-tasks.ps1` (Task Scheduler registration, separate decision), `api/data/**`, `web/**`, `.github/**` (CI), `CLAUDE.md`, `AGENTS.md`, `README.md`, `.claude/**`, `process/MASTER-PLAN.md`, validators.
- Overlap: none with T18 (T18 owns only cache.py and two data tests), T19, PERF.

## Tests

Tier RT4: all of RT3 (`uv run --project api pytest api/ -q`; `pnpm --filter web test`; `pnpm --filter web exec tsc --noEmit`; `cd web && pnpm build:islands`) + `cd web && pnpm test:e2e` + evidence pack (`vc-risk-evidence-pack`) + the user's home-PC record. Budget 2 full-suite runs plus one vc-tester confirmation.

## Stop and report at `review` if

Any step would kill a process other than the one on the configured port, require a secret, change Task Scheduler registration, or cannot be bounded in time.
