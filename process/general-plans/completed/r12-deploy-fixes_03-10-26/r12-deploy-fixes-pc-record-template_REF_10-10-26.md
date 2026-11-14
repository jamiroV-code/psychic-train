---
name: ref:r12-deploy-fixes-pc-record-template
description: "R12 deploy fixes: blank acceptance record for the user's PC check. The planner writes the filled copy (r12-deploy-fixes-pc-record_REPORT_10-10-26.md) from the user's chat results."
date: 10-10-26
feature: general-plans
---

# R12 PC acceptance record (template)

Fill from the user's chat results. A row is PASS only when the user reported it; a row the worker or planner could only infer stays "observed, user-reported, partial paste". No addresses or secrets in this file.

## Header

| Field | Value |
|---|---|
| Date and time, local | |
| Date and time, UTC | |
| PC name (no address) | |
| PowerShell version | |
| Windows version (`[System.Environment]::OSVersion.VersionString`) | |
| Branch head SHA | |
| `git rev-parse HEAD:deploy` (expected `65b61e510d3bc2c1d3278832ba8087fe7dbb6726`) | |
| Build id of the tested build | |
| Evidence kind seen at PC-10 (`marker-file` or `html`) | |

## Steps

Result is PASS, FAIL, SKIP, or "observed, user-reported, partial paste" (earlier W1/W2 reports). One line each plus the pasted log lines.

| Step | What | Result | One line and pasted log lines |
|---|---|---|---|
| PC-1 | environment (ip form, PowerShell 5.1, clean status) | | |
| PC-2 | tasks stopped, ports 3000/8000 free | | |
| PC-3 | branch checkout, head SHA, deploy tree | | |
| PC-4 | parser, five scripts, `0 errors` | | |
| PC-5 | dry runs, all `exit=0`, `DRY RUN: port 3000 is free; nothing would be stopped.` | | |
| PC-6 | refusal with no marker (`Stale build: no build marker`, exit 4) | | |
| PC-7 | decoy listener, dry run names its PID, nothing stopped | | |
| PC-8 | build stops the decoy by PID, marker written, `exit=0` | | |
| PC-9 | marker commit/web_tree/build_id match HEAD, HEAD:web, BUILD_ID | | |
| PC-10 | start: `Build is current`, `Smoke check ok`, HTTP 200, served marker equals PC-9 | | |
| PC-11 | replay of the incident (non-node decoy stopped, then smoke ok) | | |
| PC-12 | stale refusal after touching `web\app\page.tsx`, exit 4 | | |
| PC-13 | rebuild restores a fresh build, exit 0 | | |
| PC-14 | forced smoke failure: `Smoke check FAILED`, `exit=6`, no listener left | | |
| PC-15 | scheduled task start, smoke ok, no listener after `Stop-ScheduledTask` | | |
| PC-16 | restore, clean tree, both services up | | |

Known gap (not testable on the PC without editing code): smoke check "HTTP <code>" and "served build id does not match the marker" branches. Record as known gap, never PASS.

## Incidents or deviations

(none / list)

## Verdict

- Overall: APPROVE / APPROVE WITH CONCERNS / REJECT
- One sentence:
- User's name and date:
- Post-merge: `git rev-parse origin/main:deploy` equals the tested tree (yes / no):

## Mapping

Any FAIL means `rejected` and R12 returns to `in_progress`. SKIP of PC-11, PC-14 or PC-15 means `approved-with-concerns` at best. A merge changes the SHA, never the `deploy/` tree: the post-merge check compares trees.
