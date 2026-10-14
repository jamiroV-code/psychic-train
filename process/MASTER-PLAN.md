---
name: master-plan
description: "Single board and task registry for my_site: one row per task with status, dependencies, ownership, test requirement and evidence; lane table; lifecycle summary. Maintained only by the Master Planner session."
date: 03-10-26
metadata:
  node_type: root
  type: master-plan
  read_when: "starting any planner session; deciding what to work on next; before creating a new plan artifact or spawning a worker"
---

# my_site — Master Plan (board and task registry)

**Last verified:** 2026-10-14 UTC at `origin/main` `2ec34bb` (waves 1-3 and 3.5 of P9 merged incl. T63 PR #76 and follow-up PR #77; PR #60: T45-T51; R12 accepted with known gaps; PR #63 market SPEC) ; **built from:** revision 6 (`18ffd4f`). Gate reports: `process/general-plans/completed/master-planner-recovery_02-10-26/`.

**This file is the one board.** Each task has one row here; details live in its task folder. Revisions 1-6: `process/archive/master-plan-revisions_02-10-26.md`. Protocol: `process/development-protocols/master-planner.md`. Direction: north-star.md. State: current-state.md.

## Rules in one screen

- **Writer:** only the Master Planner session edits this file. Workers request updates in report headings 9 and 10.
- **Status vocabulary:** `proposed, approved, queued, in_progress, review, accepted, archived` plus `blocked, failed, cancelled, needs_input`. A status stronger than `review` needs independent evidence (merged PR, CI, vc-tester, user). `UNVERIFIED` = not re-checked.
- **IDs:** `T#` historical tasks, `R#` recovery program, `P#` programs and product tasks. `Prio` is H / M / L. Test tiers are written RT0-RT4 (operating-instructions.md).
- **Lanes:** max 3 concurrent worker sessions, excluding the Master Planner. Owned globs never overlap; shared files have one owner at a time.
- **`approved`** = standing EXECUTE consent for that task only.

## Active lanes

No worker lane active. Merge token: free. Wave 4 of P9 (T59) about to be dispatched.

## Registry

Columns: ID · Objective · Prio · Status · Parent · Deps · Worker/session · Branch/worktree · Scope + acceptance · Test req/budget · Report + commit refs · Blockers/risks · Outcome / archive location. A dash means none or not applicable.

### Historical tasks (reconciled from revision 6)

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1, T1b, T13 | pytrends partial-hour fix (PR #6/#7/#8) and CI workflow | H / M | accepted | - | - | - | merged | done | - | verbatim rows: `process/archive/master-plan-archived-rows_10-10-26.md` | - | on main |
| T3 | narrative-v2 (PR #7) | H | review | — | T1b | — | merged | RFC-1..6 VERIFIED, RFC-7 CODE DONE | user walkthrough | PR #7 | AC-14 walkthrough outstanding | `narrative-mindshare/active/narrative-v2_25-09-26/` |
| T4 | Reddit secrets, or drop Reddit | M | needs_input | — | — | user | — | add secrets or drop the source | — | rev 6 | user: leave for now | — |
| T5 | `/pairs` automation | M | review | — | — | — | merged | nightly refresh then compute | CI | PR #11 | CODE DONE not VERIFIED; commit inert on Actions | — |
| T7 | narrative-dashboard v1 closeout | M | needs_input | — | T3 | user PC | — | 2 PENDING review decisions; AC-3/AC-12 | user PC | two PENDING decisions | user PC only | `narrative-mindshare/active/narrative-dashboard_24-09-26/` |
| T8-T10, T17, T24, T25 | superseded, cancelled or done housekeeping | L | cancelled / superseded / accepted | - | - | - | - | see archive | - | - | - | verbatim rows: `process/archive/master-plan-archived-rows_10-10-26.md` |
| T11 | lying plan status strips | L | review | — | R13 | — | this branch | fixed strips in two plans | RT0 | R13 `448b10c` | PR #5 fix UNVERIFIED on main | — |
| T12 | equity provider decision | M | proposed -> superseded in part | — | R13 | — | — | LSE ADOPT-WITH-LIMITS, private use | — | `completed/lse-data-verification_17-09-26/VERDICT.md` | page is P6 | P6 |
| T14 | UI shell | M | review | P3 | — | — | merged | Direction D shell | user visual acceptance | PR #9 | no visual acceptance recorded | `active/ui-shell_28-09-26/` |
| T15 | adapter provider-term flags | L | proposed | — | — | — | — | demoted 02-10-26 (personal use) | — | RECOVERY Q7 | — | — |
| T16, T18-T20, PERF, T29-T31 | root README, dead helpers, stale-plan archive, tsbuildinfo, perf baselines and three small fixes | L | archived | - | - | workers | merged | all done | RT0-RT3 | PRs #14, #23, #22, #15, #24, #26, #28, #30; vc-tester PASS each | - | verbatim rows: `process/archive/master-plan-archived-rows_10-10-26.md` |
| T21 | `cache.py` refactor | L | proposed | — | everything merged | — | solo | six near-identical path/read/write triplets | RT3 | — | low value vs personal-use goal | — |
| T22 | cache-isolation trap in tests | L | proposed | — | — | — | — | not a live bug | — | rev 6 | — | — |
| T23 | reconcile branches | M | in_progress | — | — | Master Planner | — | seven branches deleted by user 03-10-26 | — | RECOVERY section 7 | 3 left | — |
| T26 | pytrends 0.0 questions (`layer 2 crypto`, `l2s`, `pytrends-blended/rwa`); confirm RFC-1 gating marks them `insufficient` | M | needs_input | — | T3 | — | — | open finding | — | rev 6 | data quality | — |
| T27 | snapshot cron timing: all five crons at 11:17-13:17 UTC plus a midnight-crossing warning | M | review | P1 | — | — | merged | crons fire before UTC midnight | `gh run list` | PR #11 | start times unchecked | — |
| T28 | non-atomic parquet writes | H | review | P1 | — | — | merged | `cache.py` temp-then-rename | full pytest (P1 EVL) | PR #11 `ba82986` | `etf_flows` write non-atomic (backlog) | — |
| T32-T40, T42-T44 | screener batches 1-4 and zoom fix: S1, S3, S2, S8, S4, S6, S7, e2e fix, S5a, S11a, S11b, T44 | H / M | review (T39, T44 accepted) | P4 | realignment: delete verdict code; screener RSI, groups, 30-coin cap, spaghetti chart, BTC leg strip, 15-min refresh, lean storage | H | in_progress | - | - | - | - | 19 ACs | per SPEC | `active/personal-tracker-realignment_02-10-26/` | batches 1-4 (T32-T44), equities batch 5 (T45-T51) merged, `bfb7793`; S10 optional, not started, needs its own estimate and go; PC probes pending; worker spend 86.13 USD of the 100 ceiling (user raised 75 -> 100 on 12-10-26): 69.43 before batch 5 + 3.62 + 1.72 + 3.38 + 3.38 + 1.01 + 3.59, about 13.9 left; T51, planner, validator and tester sessions unmetered | - |
| T41 | S5b layout web side (groups, add/remove, 30-coin cap, RSI) | H | accepted | P4 | T40, S11 | worker `session_01MTJTEUo9ug2o7oyRTp9ApS` | `claude/t41-s5b-layout-ui` (merged) | S5b | RT3 | PR #51 `20e9f20`, user merge 11-10-26 15:07Z; code `71e90e4`, report `1b2dc70`; tester PASS WITH_GAPS (pytest 1016/2/5/0, vitest 400 in 50 files, e2e 79 in 9); 9.99 USD read from archived session | P-S5b-1 PC probe open; AC-8r group sort, AC-S5b-8r contrast (`screener-ondemand-states-contrast_NOTE_10-10-26.md`); worker passed 7 USD ask point unrecorded | `active/screener-batch3_09-10-26/` (accepted with known gaps; not archived, needs the user's go) |
| T45 | S9A equities API: cache-only board, chart, spaghetti, add/remove with 30 cap, calendar | H | accepted | P6 | T41 | `session_01D3a21vGbbh7Jm7kYCxe5vR` | `claude/t45-s9a-equities-api` (merged) | S9A | RT3 | PR #54 `6aee5e2`; tester PASS; 3.62 USD | none | `active/screener-batch5-equities_12-10-26/` |
| T46 | S9B layout section `equities` | H | accepted | P6 | T45 | `session_01M9p9gPbZqhgVZapoadX5eQ` | `claude/t46-s9b-equities-layout` (merged) | S9B | RT3 | PR #55 `23d7e43`; tester PASS; 1.72 USD | hidden break in `test_layout_failure_is_logged_not_failed` fixed with planner approval | same |
| T47 | S9C `/equities` page by parameterised reuse | H | accepted | P6 | T46 | `session_01R8x2RhVF7MTRhzVtG6NP8W` | `claude/t47-s9c-equities-page` (merged) | S9C | RT1-RT3 | PR #56 `4ec0cd0`; tester PASS (vitest 446 in 55 files); 3.38 USD | P-S9-3 phone/iPad open | same |
| T48 | S9D equities e2e, spaghetti, drill-down | H | accepted | P6 | T47 | `session_01Hcd3ZQPzPN1s6om5zoQobY` | `claude/t48-s9d-equities-e2e` (merged) | S9D | RT1 | PR #57 `d7f3ee9`; tester PASS (pytest 1105/2/5, e2e 90 in 10); 3.38 USD | none | same |
| T49 | S9F LSE adapter live-shape fix (added outside the plan after the user's probe) | H | review | P6 | T48 | `session_01BJ52mKHgXHYs8DPELeHpdc` | `claude/t49-lse-live-shape` (merged) | S9F | RT3 | PR #58 `2223e95`; CI + planner diff read only, no tester (user's decision, near usage limit); 1.01 USD | no live call run by an agent | same |
| T50 | S9E market-hours refresh worker + equities freshness strip | H | review | P6 | T49 | `session_01YHqbhmpwYL18wnvzvSFDta` | `claude/t50-s9e-equities-refresh` (merged) | S9E | RT3 | PR #59 `7de6dea`; tester PASS (pytest 1127/1/5, vitest 476 in 59, e2e 92 in 11); 3.59 USD | AC-S9E-1 CONDITIONAL: 30/60 min constants unmeasured (P-S9-2) | same |
| T51 | equities catch-up fix after downtime (fast lane) | M | review | P6 | T50 | one execute agent in the planner session | `claude/t51-equities-catchup-fix` (merged) | worker `_behind` rule | RT3 | PR #60 `bfb7793`; pytest 1134/1/5 (worker); CI + planner diff read only, no tester (user's decision); cost not metered | none | same, report `-t51_REPORT_13-10-26.md` |
| T2, T6 | not present in any revision | — | n/a | — | — | — | — | numbering gaps, recorded as unknown, not invented | — | — | — | — |

### Programs and product tasks

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | pipeline completeness | M | review | — | — | — | merged | scheduled refresh jobs, atomic writes, cron timing | CI | PR #11; closeout in `pipeline-completeness_28-09-26/` | cron firing unverified; inert commits | `active/pipeline-completeness_28-09-26/` |
| P2 | deployability (home PC + Tailscale) | M | review | — | — | — | merged | `deploy/` launchers, CORS, runbook | user PC | PR #10 | verifiable on user PC only | `active/deployability_28-09-26/` |
| P2b | stale-build guard | M | superseded by R12 | P2 | — | — | — | gap from the 2026-10-01 live incident | — | — | — | R12 |
| P3 | UI Direction D | M | review | — | — | — | merged | same as T14 | user visual acceptance | PR #9 | — | `active/ui-shell_28-09-26/` |
| P4 | realignment: delete verdict code; screener RSI, groups, 30-coin cap, spaghetti chart, BTC leg strip, 15-min refresh, lean storage | H | in_progress | - | - | - | - | 19 ACs | per SPEC | `active/personal-tracker-realignment_02-10-26/` | batches 1-3 (T32-T41), S11a/b (T42, T43) and zoom fix (T44) merged, `20e9f20`; S9 later; S10 optional; PC probes pending; workers 69.43 USD of 75 (34.73 through T39 + 34.70 since; ceiling 45 -> 60 -> 75), about 5.57 left, S9 and S10 each need a fresh estimate and the user's go, a slice may no longer fit without raising the ceiling (user decides); T44 and testers unmetered | - |
| P5 | narrative baskets: user-defined baskets, equal-weight view, mindshare share-of-total, raw-only /narrative | H | proposed | — | P4 | — | — | 12 active ACs | per SPEC | `process/general-plans/active/narrative-baskets_02-10-26/` | live probe per signal on user PC | — |
| P6 | LSE equities page with Add button, private-use note | M | review | - | P4 | - | - | realignment SPEC | per SPEC | REALIGN SPEC | built: T45-T51, accepted with known gaps (PRs #54-#60); open: P-S9-2 (on-PC page, real-close timing), P-S9-3 (phone/iPad); gaps: `equities-known-gaps_NOTE_13-10-26.md` | `active/screener-batch5-equities_12-10-26/` (not archived, needs the user's go) |
| P7 | protect pytrends partial-hour fix and nightly archive (guard tests) | M | proposed | P4 | — | — | — | BASKETS Decision 16, AC-25 | RT2 | BASKETS SPEC | — | — |
| P8 | Human-confirmed market framework | M | proposed, PAUSED by owner 14-10-26 | - | - | - | - | owner must decide which input fits which timeframe before resume | per SPEC | SPEC `active/market-framework_13-10-26/`; PR #63 | paused; its proposed exception text (labelled D-15 in the SPEC) is renumbered on resume | `active/market-framework_13-10-26/` |
| P9 | Data integration tooling: REA allow-listed wrapper + Scrapling tiers 1-3, separate uv project `tools/data-integration` | M | approved (owner 14-10-26) | - | - | workers per wave | `claude/t53..t63-*` | PLAN PASS (PVL 2). Waves 1-3 done+merged: T53 #66, T54 #67, T55 #70, T56 #69, supplements #71 #72, T57 #75, T58 #74. Wave 3.5 T63 (S-T3c provenance completeness + fetch hardening) done: PR #76 + follow-up PR #77 merged; independent tester PASS_WITH_GAPS then fixed; AC-10 and AC-22 complete; known limit: size caps are checked after the client returns the whole body; cost 1.10 USD. Amendment A1 (S-T7 CLI, T62) validated CONDITIONAL after both fix cycles: 7 text concerns G1-G7 are binding envelope additions; the owner must explicitly accept them when T62 is dispatched. Order: W4 T59 (S-T4 tiers 2-3), W5 T62 (S-T7 CLI), W6 T60 (S-T5b docs), W7 T61 (S-T6 BTC-HIST); max 2 workers. Rule: recompute the API baseline from origin/main before writing envelopes | RT0-RT3; est 24.8-43.5 USD plus T63; actual spend far below estimates so far; ceiling 130 USD (owner); worker spend 94.40 USD; ask 7, cap 15 USD per slice | plan `active/data-integration-tooling_13-10-26/` | limits: tiers 2/3 not proven live; scrapling-importing tests outside CI; Windows/Py 3.12 unverified until owner probes AC-16/17; REA web modes unverified | - |

### Recovery program (master-planner-recovery)

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | re-verify ground truth, write current-state.md | H | accepted | — | — | Gate 2 execute | `claude/pensive-albattani-ou0cgv` | F2 | RT0, C14 | `3562deb`; vc-tester green | docs-only | `process/context/current-state.md` |
| R2 | north-star.md + decisions.md | H | accepted | — | — | Gate 2 execute | same | F1, F3 | RT0, C8, C14 | `3562deb`; vc-tester green | — | `process/context/north-star.md`, `process/context/decisions.md` |
| R3 | slim all-context.md, create context-changelog.md | H | accepted | — | — | Gate 2 execute | same | F4, F5, F16, F17 | RT0, C5, C6, C7 | `0e593cd`, `bcb62e4`, `5a73705`; vc-tester green | — | `process/context/` root docs |
| R4 | master-planner.md protocol + templates | H | review | — | — | Gate 2 execute | same | F7, F11 | RT0, C7, C12 | `b78e652`; green | branch-delete unverified | `process/development-protocols/master-planner.md` |
| R5 | registry rewrite in this file | H | accepted | — | R14 | Gate 2 execute | same | F6, F8 | RT0, C11, C14 | `dafa781`, `b36a0da` | user accepted AC-R5, AC-R6 | this file; `process/archive/index.md` |
| R6 | CLAUDE.md / AGENTS.md role-neutral rewrite, ENTRY-SET drift check | H | accepted | — | Gate 2 | Gate 3 execute | `claude/pensive-albattani-ou0cgv` | F9, F10 | RT0, C1, C2, C9, C10 (G3-1..G3-11) | `eee7709`, `0b3c9bf`; user accepted | — | decisions D-9, D-10 |
| R7 | token baseline measurement | M | accepted | — | R6 | Gate 3 execute + independent vc-tester | same | C3, C4, probes B1, B2, P2 | cap 1 USD; 0.617 spent | planner 78,664 -> 37,450 tokens | single-run; user accepted AC-R9 | Gate 3 report |
| R8 | test policy into all-tests.md | M | review | — | R6 | Gate 4 execute + independent vc-tester | same | F12, planner budget pin | RT0, G4-1..G4-11 | `753db23`; green | needs user's Gate 4 acceptance | operating-instructions.md, all-tests.md |
| R9 | housekeeping (approved items only) | L | proposed | — | — | — | — | H1-H10 per approval | validators | — | user 03-10-26: H2 = T20, H8 = T16, H1 declined (T17), rest deferred | backlog `gate5-deferred-candidates_NOTE_03-10-26.md` |
| R10 | deploy path doc + stale-build guard proposal | M | proposed | — | — | — | — | RECOVERY section 8 | RT0 | — | — | Gate 5 |
| R11 | archive index + session triage | L | proposed | — | — | — | — | grow `process/archive/index.md` | RT0 | — | — | Gate 5 |
| R12 | deploy fixes: kill-by-port before build, stale-build guard in `start-web`, post-start smoke check | M | accepted | P2 | - | workers W1-W4 | `claude/r12-deploy-fixes` (merged) | owns `deploy/*.ps1`; user PC record 10-10-26 | RT4 | PR #45 `86ddebc` (code), PR #48 `a2fd4b5` (record); review-decision approved-with-concerns; W1 2.45 + W2 4.56 + W3 1.39 + W4 0.77 USD | ACCEPTED WITH KNOWN GAPS (W1-W4): HTTP non-200 and build-id-mismatch smoke branches shape-tested only; exit 6 seen only for process-exited; failed-smoke port stop could exit 5 first; invalid WebPort under -ReportOnly exits 2. W4 self-merged PR #48 despite NEVER merge | `active/r12-deploy-fixes_03-10-26/` (left in place; archive needs the user's go) |
| R13 | salvage `claude/exciting-meitner-hy50kn` selectively | H | accepted | — | — | Gate 2 execute | same | TAKE: LSE folder, strip fixes; DROP: duplicate board | RT0, C14 | `448b10c`; vc-tester green; user accepted AC-R6 | other hunks not taken | `process/general-plans/completed/lse-data-verification_17-09-26/` |
| R14 | adopt `pensive-dijkstra` MASTER-PLAN rev 6 as registry base | H | accepted | — | — | Gate 2 execute | same | rev 6 `18ffd4f` | C14 | `c33fa96`; green | — | `process/archive/master-plan-revisions_02-10-26.md` |

## Carried notes

- Open backlog notes: all files in `process/general-plans/backlog/` (`<name>_NOTE_<dd-mm-yy>.md`; read `_GUIDE.md`). Closed: `lse-live-shape-verification` (12-10-26). New 13-10-26: `equities-known-gaps`, `lse-api-key-deploy-handling`.
- Envelope rule (from the 10-10-26 lapses, `process/archive/index.md`): workers get "needs_input means STOP, do not merge, do not open a new PR; cost is reported by the planner, not the worker"; the planner measures cost per session from the session record at report time and checks the 7 USD ask point (T41 passed it unrecorded).
- Known condition: `validate-backlog-notes` fails 45 notes (older schema).
- Linter/formatter: none configured (undone half of T13, not a task).

## Maintaining this file

At each planner session end: re-verify first (git log, file existence, `gh pr view`); never copy numbers from context docs; update `Last verified` and the base SHA; one row per task; move superseded narrative to the archive, never delete it.
