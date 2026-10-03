---
phase: gate-4-token-and-test-efficiency
date: 2026-10-03
status: COMPLETE
feature: general-plans
plan: process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md
---

# Gate 4 Report: token and test efficiency (docs only)

**TL;DR:** Gate 4 is implemented and every execute-side gate is green (G4-1 to G4-9, plus G4-11 for the last pushed SHA). Installs were run under G4-K1 = A. pytest, vitest and tsc each ran once at `753db23`: 873 passed, 223 passed, exit 0. Planner fixed part is 47,699 B of 56,000. The independent EVL by vc-tester and the user's acceptance are still pending.

## What Was Done

| E-item | File | Bytes before -> after | Commit |
|---|---|---|---|
| E3, E4 RT rows with full commands, bounded retry, same-failure stop, test budget, skip check | process/context/operating-instructions.md | 5,108 -> 6,148 (58 -> 66 lines) | `ee72237` |
| E2 section 12 PLANNER-BUDGET block, brief cap, trim rule, section 11 end line, envelope line `Retry budget: 2 fix cycles; same failure twice stops` | process/development-protocols/master-planner.md | 13,588 -> 16,246 | `753db23` |
| E6 link to the RT table, `## Current evidence (Gate 4)` block (1,190 B), old state section labelled historical | process/context/tests/all-tests.md | 31,619 -> about 32,900 | `cc0c7f6` |
| E5 rewrite in place, Gate 3 narrative replaced by report links, reconciliation sentence | process/context/current-state.md | 8,879 -> 5,507 | `253f703` |
| E5 R6, R7, R8 rows (R8 to `review`), shorter R-row cells, stamp | process/MASTER-PLAN.md | 18,577 -> 17,693 | `253f703` |
| E1 D-12 | process/context/decisions.md | 12,363 -> about 13,800 | `a96d7b3` |
| Plan text: Status lines, section 5 lever status cells, bounded retry, method text; section 6 `cd web && pnpm build:islands` and retry text; section 9 Gate 4 row; section 10 AC-R1 and AC-R9 | the plan | edited in place | this closeout commit |

G4-1 output (also the section 12 block output, same text on two runs):
```
planner_fixed=47699 cap=56000 headroom=8301
info_with_master_planner=63945 info_worst_case_brief=71945 gated_worst_case_brief=55699 of 64000
rc=0
```

## Installs and test runs (G4-K1 = A; each suite once; `UV_FROZEN=1`)

| Step | Command | Result | UTC |
|---|---|---|---|
| install | `uv sync --project api --frozen` | ok | 05:08:56Z |
| install | `cd web && pnpm install --frozen-lockfile` | ok (4.9 s) | about 05:09Z |
| pytest | `uv run --project api pytest api/ -q` | 873 passed, 1 skipped, 5 deselected, 1 xfailed | 05:09:08Z to 05:11:54Z |
| vitest | `pnpm --filter web test` | 30 files, 223 tests passed | 05:11:57Z to 05:12:07Z |
| tsc | `pnpm --filter web exec tsc --noEmit --incremental false` | exit 0 | 05:12:10Z |

All at commit `753db23` (api/ and web/ unchanged since `96d2d18`). After the runs `git status --porcelain` printed nothing: neither `web/tsconfig.tsbuildinfo` nor `uv.lock` was dirtied, so nothing was restored.

## What Was Skipped or Deferred

- Island build and Playwright: not run locally. The user's approval named only pytest, vitest and tsc, and section 9 says three suites. The island build is green on CI. Playwright: 6 specs exist; the last local run was 35/35 on 4 specs (28-09-26), now labelled `not re-measured`.
- Updating the token-usage-telemetry stub wording (stale item f): left for UPDATE PROCESS, as the contract says.

## Test Gate Outcomes

| Gate | Observed |
|---|---|
| G4-1 | as above, no OVER-CAP line, rc=0 |
| G4-2 | markers 1 and 1, no MISSING line, two runs identical (cmp ok) |
| G4-3 | no output |
| G4-4 | no output |
| G4-5 | no output |
| G4-6 | no output |
| G4-7 | no output |
| G4-8 | no output |
| G4-9 | C10 rc=0; G3-1, G3-2, G3-6, G3-8, G3-9 no output; C11 no output; C12 = 11; C13 no output; operating-instructions.md 66 lines, 6,148 B; C14 rev 6 preservation no output; validator output identical to the pre-edit run (diffed) |
| G4-10 | run once, see above |
| G4-11 | `gh run list`: run 37098862216 at `ee72237`, completed, success (newest pushed SHA; later commits are local) |

## Token figures (AC-R9 labels)

- Entry-set bytes (47,699 fixed; 55,699 with an 8,000 B brief; 63,945 with master-planner.md): MEASURED bytes.
- Tokens as bytes/4 (fixed part about 11.9k): ESTIMATED.
- Whole-session usage, retry waste, repeated-test cost: UNMEASURED. No probe and no spend in Gate 4.

## Plan Deviations

1. The contract's E1 says "do not commit". The orchestrator told me to commit locally after each step, so I did. Nothing was pushed by me.
2. `ee72237` was committed and pushed by something other than this agent, with message "checkpoint", between my edit and my own commit attempt. It holds exactly my operating-instructions.md edit. I did not push.
3. MASTER-PLAN.md is 17,693 B: under the 19,000 ceiling, 193 B over the 17,500 target.

## Test Infra Gaps Found

- CI gives pass or fail only, not counts (job logs are not readable here).
- Compliance with the retry, same-failure and no-re-run rules is visible only at the Gate 6 pilot (AC-R7).

## Closeout Packet

- Plan: the plan path in the frontmatter. Classification: Keep in active/testing until the independent EVL runs and the user accepts. Next: vc-tester (sonnet) runs G4-1 to G4-9 and G4-11, and confirms with `git diff --quiet 753db23 HEAD -- api web` instead of re-running suites. Then UPDATE PROCESS.
- Follow-up stubs created: none (branch A ran, so no `test-counts-remeasure` stub).

## Forward Preview

### Test Infra Found
uv 0.8.17 and pnpm 10.28.0 installs work behind the proxy; dependencies are now installed in this container.

### Blast Radius Changes
None outside `process/`.

### Commands to Stay Green
The section 12 block in master-planner.md; G4-3 to G4-9.

### Dependency Changes
None. Gate 5: tsc with incremental on rewrites the tracked `web/tsconfig.tsbuildinfo`. Use `--incremental false`, or restore it, until the untrack. Keep `UV_FROZEN=1` so `uv.lock` stays clean. The README links to operating-instructions.md and does not copy commands.
