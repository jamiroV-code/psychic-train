---
phase: gate-4-token-and-test-efficiency
date: 2026-10-03
status: COMPLETE_WITH_GAPS
feature: general-plans
plan: process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md
---

# Gate 4 Report: token and test efficiency (docs only)

**TL;DR:** Gate 4 is implemented and every execute-side gate is green (G4-1 to G4-9, plus G4-11 for the last pushed SHA). Installs were run under G4-K1 = A. pytest, vitest and tsc each ran once at `753db23`: 873 passed, 223 passed, exit 0. Planner fixed part is 47,699 B of 56,000. The independent EVL by vc-tester (iteration 002) was green at cycle 0; the user's acceptance of R8 and AC-R9 is still pending (UPDATE PROCESS closeout below).

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
| G4-11 | `gh run list`: run 37098862216 at `ee72237`, completed, success (newest pushed SHA at execute; the EVL later saw `cc0c7f6` green too) |

## Token figures (AC-R9 labels)

- Entry-set bytes (47,699 fixed; 55,699 with an 8,000 B brief; 63,945 with master-planner.md): MEASURED bytes.
- Tokens as bytes/4 (fixed part about 11.9k): ESTIMATED.
- Whole-session usage, retry waste, repeated-test cost: UNMEASURED. No probe and no spend in Gate 4.

## Plan Deviations

1. The contract's E1 says "do not commit". The orchestrator told me to commit locally after each step, so I did. Nothing was pushed by me.
2. `ee72237` was committed and pushed by something other than this agent, with message "checkpoint", between my edit and my own commit attempt. It holds exactly my operating-instructions.md edit. I did not push.
3. MASTER-PLAN.md was 17,693 B at execute (193 B over the 17,500 target) and 17,819 B after the closeout: under the 19,000 ceiling, 319 B over the target.

## Test Infra Gaps Found

- CI gives pass or fail only, not counts (job logs are not readable here).
- Compliance with the retry, same-failure and no-re-run rules is visible only at the Gate 6 pilot (AC-R7).

## Closeout Packet

- Plan: the plan path in the frontmatter (stays in `active/`; Gates 5 and 6 remain).
- Classification: **Keep in active/testing** (plan-level: Gates 5-6 remain; Gate 4 itself is verified). Not archivable: R8 stays `review` until CI on the newest head is confirmed and the user accepts; AC-R9 token claims are hybrid and await the user's review.
- Validate-contract: present (Gate 4 section of the plan, now CONSUMED). SPEC: the program has no single frozen SPEC for these gates; acceptance criteria AC-R1, AC-R5, AC-R8, AC-R9 were scored through G4-1..G4-11 (met by automated gates, except AC-R9 token claims: unmet pending user review, backlog `token-usage-telemetry_NOTE_02-10-26.md`).
- Follow-up stubs created: none (branch A ran, so no `test-counts-remeasure` stub). Stub wording of the token-usage-telemetry note refreshed at closeout.

## Independent EVL result (UPDATE PROCESS review, 03-10-26)

vc-tester EVL iteration 002 (`master-planner-recovery-evl-iteration-002_REPORT_03-10-26.md`, `results-evl.tsv`): HALTED_SUCCESS at cycle 0 at HEAD `d09d92e`. G4-1..G4-9 matched, G4-1 recomputed independently (47,699 / 56,000 / 8,301), `git diff --quiet 753db23 HEAD -- api web` rc=0 so the recorded counts stay current, validators equal baseline, scope outside `process/` is exactly CLAUDE.md and AGENTS.md from Gate 3. CI: `ee72237` and `cc0c7f6` fully green; `d09d92e` web job green, api job pending at check time.

Accuracy review of this report against the EVL: byte figures, test counts, scope and CI claims agree. Corrections made at closeout: status line and TL;DR (EVL no longer pending), G4-11 note (CI also green at `cc0c7f6`), the MASTER-PLAN size, the current-state size.

## UPDATE PROCESS closeout

- Drift score: MEDIUM (3 signals: more than 1 file touched; `process/development-protocols/master-planner.md` changed; 3 or more memory-worthy decisions D-12, D-13 and the retry single home). Recommend UPDATE PROCESS -- significant changes detected.
- Closeout edits: current-state.md refreshed to `0004d5b` (6,028 B, ceiling 8,000); MASTER-PLAN.md R8 row and stamp (17,819 B, under the 19,000 ceiling, 319 B over the 17,500 target); decisions.md D-12 indexed and D-13 added (G4-K1 = A approved by the user, 03-10-26); master-planner.md section 6 retry line now points to operating-instructions.md "Bounded retry", the single home (2 fix cycles per failing gate, same failure twice stops, 10-cycle outer ceiling); token-usage-telemetry note wording; plan Status, Resume and contract CONSUMED marker. Planner fixed part after closeout: 48,346 B of 56,000 (headroom 7,654 B; the closeout added 647 B).
- R8 acceptance check (acceptance rule (a)-(d)): (b) independent re-run done by vc-tester, but CI on the head SHA of the newest pushed commit is not confirmed; (d) no user-visible behavior, but the plan's G4-7 contract pins the R8 row at `review`. Result: R8 stays `review`; AC-R9 not marked accepted.
- Validators after closeout: equal to the baseline (context-discovery 1, skills 1, guide-sync 1, parity 0 failures and 18 warnings, plan-inventory 0 and 6, the rest 0); no new failure; routing block in sync.
- Next: confirm CI on the newest head; the user reviews AC-R5, AC-R6, AC-R9; Gate 5 re-enters VALIDATE, then the user's explicit ENTER EXECUTE MODE (several approvals needed: H1 symlink, tsbuildinfo untrack, R12 deploy fixes). Commit checkpoint: process commits only; nothing pushed.

## Forward Preview

### Test Infra Found
uv 0.8.17 and pnpm 10.28.0 installs work behind the proxy; dependencies are now installed in this container.

### Blast Radius Changes
None outside `process/`.

### Commands to Stay Green
The section 12 block in master-planner.md; G4-3 to G4-9.

### Dependency Changes
None. Gate 5: tsc with incremental on rewrites the tracked `web/tsconfig.tsbuildinfo`. Use `--incremental false`, or restore it, until the untrack. Keep `UV_FROZEN=1` so `uv.lock` stays clean. The README links to operating-instructions.md and does not copy commands.
