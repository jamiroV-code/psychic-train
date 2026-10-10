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

**Last verified:** 2026-10-10 UTC at `origin/main` `fc12f27` (T32-T44 merged; R12 accepted with known gaps) ; **built from:** revision 6 (`18ffd4f`). Gate reports: `process/general-plans/completed/master-planner-recovery_02-10-26/`.

**This file is the one board.** Each task has one row here; details live in its task folder. Revisions 1-6: `process/archive/master-plan-revisions_02-10-26.md`. Protocol: `process/development-protocols/master-planner.md`. Direction: north-star.md. State: current-state.md.

## Rules in one screen

- **Writer:** only the Master Planner session edits this file. Workers request updates in report headings 9 and 10.
- **Status vocabulary:** `proposed, approved, queued, in_progress, review, accepted, archived` plus `blocked, failed, cancelled, needs_input`. A status stronger than `review` needs independent evidence (merged PR, CI, vc-tester, user). `UNVERIFIED` = not re-checked.
- **IDs:** `T#` historical tasks, `R#` recovery program, `P#` programs and product tasks. `Prio` is H / M / L. Test tiers are written RT0-RT4 (operating-instructions.md).
- **Lanes:** max 3 concurrent worker sessions, excluding the Master Planner. Owned globs never overlap; shared files have one owner at a time.
- **`approved`** = standing EXECUTE consent for that task only.

## Active lanes

No worker lane active. Merge token: free.

## Registry

Columns: ID · Objective · Prio · Status · Parent · Deps · Worker/session · Branch/worktree · Scope + acceptance · Test req/budget · Report + commit refs · Blockers/risks · Outcome / archive location. A dash means none or not applicable.

### Historical tasks (reconciled from revision 6)

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | pytrends partial-hour zeros in `_fetch_live` | H | accepted | — | — | — | merged | `isPartial` rows dropped | done | PR #8 | — | `narrative-mindshare/completed/pytrends-partial-hour-fix_28-09-26/` |
| T1b | `isPartial` guard in batched path `_fetch_batch_live` | H | accepted | T1 | — | — | merged | same guard in the batched fetch | done | PR #6/#7 | — | on main |
| T3 | narrative-v2 (PR #7) | H | review | — | T1b | — | merged | RFC-1..6 VERIFIED, RFC-7 CODE DONE | user walkthrough | PR #7 | AC-14 walkthrough outstanding | `narrative-mindshare/active/narrative-v2_25-09-26/` |
| T4 | Reddit secrets, or drop Reddit | M | needs_input | — | — | user | — | add secrets or drop the source | — | rev 6 | user: leave for now | — |
| T5 | `/pairs` automation | M | review | — | — | — | merged | nightly refresh then compute | CI | PR #11 | CODE DONE not VERIFIED; commit inert on Actions | — |
| T7 | narrative-dashboard v1 closeout | M | needs_input | — | T3 | user PC | — | 2 PENDING review decisions; AC-3/AC-12 | user PC | two PENDING decisions | user PC only | `narrative-mindshare/active/narrative-dashboard_24-09-26/` |
| T8-T10, T17, T24, T25 | superseded, cancelled or done housekeeping | L | cancelled / superseded / accepted | - | - | - | - | see archive | - | - | - | verbatim rows: `process/archive/master-plan-archived-rows_10-10-26.md` |
| T11 | lying plan status strips | L | review | — | R13 | — | this branch | fixed strips in two plans | RT0 | R13 `448b10c` | PR #5 fix UNVERIFIED on main | — |
| T12 | equity provider decision | M | proposed -> superseded in part | — | R13 | — | — | LSE ADOPT-WITH-LIMITS, private use | — | `completed/lse-data-verification_17-09-26/VERDICT.md` | page is P6 | P6 |
| T13 | CI | M | accepted | — | — | — | merged | pytest, vitest, `tsc`, island build | — | `.github/workflows/ci.yml` | no e2e, no linter | on main |
| T14 | UI shell | M | review | P3 | — | — | merged | Direction D shell | user visual acceptance | PR #9 | no visual acceptance recorded | `active/ui-shell_28-09-26/` |
| T15 | adapter provider-term flags | L | proposed | — | — | — | — | demoted 02-10-26 (personal use) | — | RECOVERY Q7 | — | — |
| T16, T18-T20, PERF, T29-T31 | root README, dead helpers, stale-plan archive, tsbuildinfo, perf baselines and three small fixes | L | archived | - | - | workers | merged | all done | RT0-RT3 | PRs #14, #23, #22, #15, #24, #26, #28, #30; vc-tester PASS each | - | verbatim rows: `process/archive/master-plan-archived-rows_10-10-26.md` |
| T21 | `cache.py` refactor | L | proposed | — | everything merged | — | solo | six near-identical path/read/write triplets | RT3 | — | low value vs personal-use goal | — |
| T22 | cache-isolation trap in tests | L | proposed | — | — | — | — | not a live bug | — | rev 6 | — | — |
| T23 | reconcile branches | M | in_progress | — | — | Master Planner | — | seven branches deleted by user 03-10-26 | — | RECOVERY section 7 | 3 left | — |
| T26 | pytrends 0.0 questions (`layer 2 crypto`, `l2s`, `pytrends-blended/rwa`); confirm RFC-1 gating marks them `insufficient` | M | needs_input | — | T3 | — | — | open finding | — | rev 6 | data quality | — |
| T27 | snapshot cron timing: all five crons at 11:17-13:17 UTC plus a midnight-crossing warning | M | review | P1 | — | — | merged | crons fire before UTC midnight | `gh run list` | PR #11 | start times unchecked | — |
| T28 | non-atomic parquet writes | H | review | P1 | — | — | merged | `cache.py` temp-then-rename | full pytest (P1 EVL) | PR #11 `ba82986` | `etf_flows` write non-atomic (backlog) | — |
| T32 | S1 freshness core: `freshness.py`, `fetched_at` sidecar, 200-bar sub-daily retention, tail fetch | H | review | P4 | — | `session_014QEGDPvhtypW82WNmy9KeE` | `claude/t32-s1-freshness-core` (merged) | S1 | RT3 | PR #34 `161e7be`; EVL PASS; 5.5794842 USD | P-S1-1 PC probe outstanding | `active/screener-batch1_03-10-26/` |
| T33 | S3 LSE equities adapter + ticker store (`lse_adapter.py`, `equities_store.py`), private use | M | review | P6 | — | `session_01PcmprWjrPALpocq7NwWJEg` | `claude/t33-s3-lse-adapter` (merged) | S3 | RT3 | PR #33 `dc0cbb3`; EVL CONDITIONAL; 2.883962 USD | G-S3-6 skipped until the user runs `s3-probe/lse_probe.py`; backlog `lse-live-shape-verification_NOTE_03-10-26.md` | `active/screener-batch1_03-10-26/` |
| T34 | S2 current-candle gain chips + UTC axis labels | H | review | P4 | T32 | `session_012TMn5iay2D3tq1Erh5efta` | `claude/t34-s2-chips-labels` (merged) | S2 | RT3 | PR #36 `605424d`; EVL PASS; 4.9869365 USD | P-S2-1 PC probe outstanding | `active/screener-batch1_03-10-26/` |
| T35 | S8 in-process background refresh worker (`SCREENER_REFRESH_WORKER`) | H | review | P4 | T32 | `session_01L2cTTiPVtJY6ewkc1oSkfF` | `claude/t35-s8-refresh-worker` (merged) | S8 | RT3 | PR #35 `d10aebf`; EVL PASS (+20 api tests); 4.1521902 USD | P-S8-1 overnight PC probe outstanding. User 04-10-26: (a) done in T38; (b), (c) accepted limits | `active/screener-batch1_03-10-26/` |
| T36 | S4 staged verdict removal (commit A contract+web, B dead backend/CSS/copy) | H | review | P4 | T35 | `session_01LV7EvHumB89R7kHBZ7rvhB` | `claude/t36-s4-verdict-removal` (merged) | S4 | RT3 | PR #38 `69fedd2`; EVL PASS (pytest 929/2/5/0, vitest 226 in 30 files); 5.438936 USD | P-S4-1 (deploy web and API together) is the user's; G-S4-10 e2e not run by tester | `active/screener-batch2_04-10-26/` |
| T37 | S6 chart interaction (Ctrl/Cmd+wheel zoom, pinch, drag pan, double-click reset; vector axis text; spaghetti chart replaces relative-performance) | H | review | P4 | T36 | `session_01JAKoPe7ZX5YwfcAHdnmFB3` | `claude/t37-s6-chart-interaction` (merged) | S6 | RT3 | PR #39 `8858469`; EVL PASS (pytest 934, vitest 239 in 32 files, e2e 16); 4.9652188 USD | P-S6-1 (DPR 2 display, phone) is the user's; AC-S6-6 CONDITIONAL until S5 (backlog `spaghetti-toggle-persistence_NOTE_09-10-26.md`) | `active/screener-batch2_04-10-26/` |
| T38 | S7 BTC leg chart + D-14 estimate label + regime cache-only fix | H | review | P4 | T37 | `session_01Ksxq9nUNTvjAcYyf22MpJM` | `claude/t38-s7-btc-leg-chart` (merged) | S7 | RT3 | PR #40 `38fe860`; EVL PASS (pytest 951/2/5/0, vitest 251 in 34 files, e2e 17); 4.7511942 USD | P-S7-1 (user: run the deep BTC backfill once, then check) is the user's; FRED/DefiLlama may still fetch on TTL expiry (accepted). LAPSE: merged with worker report `needs_input`; main red on an e2e until T39 | `active/screener-batch2_04-10-26/` |
| T39 | one-line e2e fix after S7 layout (`exerciseZoom` re-reads plot position, `scrollIntoViewIfNeeded`) | H | accepted | T38 | T38 | `session_01FWism1FLg7f172tHwFypMp` | `claude/t39-fix-zoom-e2e` (merged) | e2e helper | RT3 | PR #41 `270f9ac`; EVL PASS; 1.9678292 USD | CI has no Playwright | `active/screener-batch2_04-10-26/` |
| T40 | S5a layout API (server layout file, groups, 30-coin cap) | H | review | P4 | T39 | worker | `claude/t40-s5a-layout-api` (merged) | S5a | RT3 | PR #44 `2a2f3b6`; tester PASS; 3.40 USD | P-S5a-1 PC probe outstanding; AC-8 group sort deferred (`screener-group-sort_NOTE_09-10-26.md`) | `active/screener-batch3_09-10-26/` |
| T41 | S5b layout web side | H | proposed | P4 | T40, S11 | - | - | S5b | RT3 | plan rebased on S11 (`a5fcb16`); not started | plan re-validation pending | `active/screener-batch3_09-10-26/` |
| T42 | S11a Brussels time (axis and labels) | H | review | P4 | T40 | worker | `claude/t42-s11a-brussels-time` (merged) | S11a | RT3 | PR #47 `68c24d9`; tester PASS; 4.40 USD | P-S11-2 (25 Oct 2026 DST) outstanding; pytest 1016 verified (996+17 R12+3); worker flagged needs_input on the count, merged anyway | `active/screener-batch4_10-10-26/` |
| T43 | S11b 60 s live polling, freshness strip, in-place chart updates | H | review | P4 | T42 | worker | `claude/t43-s11b-live-updates` (merged) | S11b | RT3 | PR #49 `960758a`, user merge 13:13Z; tester PASS WITH_GAPS; 7.74 USD | contrast notes `screener-live-ondemand-states-contrast_NOTE_10-10-26.md`, `screener-passive-polls_NOTE_10-10-26.md`; 7 USD ask threshold passed unrecorded | `active/screener-batch4_10-10-26/` |
| T44 | zoom fix: small charts share one zoom; reset button gone on small charts only (user-requested fast lane) | M | accepted | P4 | T43 | one execute agent | `claude/t44-zoom-sync-fix` (merged) | zoom | RT3 | PR #50 `fc12f27`; tester PASS; cost not recorded in worker report | none; user confirmed it works on the PC | `active/screener-zoom-sync_10-10-26/` |
| T2, T6 | not present in any revision | — | n/a | — | — | — | — | numbering gaps, recorded as unknown, not invented | — | — | — | — |

### Programs and product tasks

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | pipeline completeness | M | review | — | — | — | merged | scheduled refresh jobs, atomic writes, cron timing | CI | PR #11; closeout in `pipeline-completeness_28-09-26/` | cron firing unverified; inert commits | `active/pipeline-completeness_28-09-26/` |
| P2 | deployability (home PC + Tailscale) | M | review | — | — | — | merged | `deploy/` launchers, CORS, runbook | user PC | PR #10 | verifiable on user PC only | `active/deployability_28-09-26/` |
| P2b | stale-build guard | M | superseded by R12 | P2 | — | — | — | gap from the 2026-10-01 live incident | — | — | — | R12 |
| P3 | UI Direction D | M | review | — | — | — | merged | same as T14 | user visual acceptance | PR #9 | — | `active/ui-shell_28-09-26/` |
| P4 | realignment: delete verdict code; screener RSI, groups, 30-coin cap, spaghetti chart, BTC leg strip, 15-min refresh, lean storage | H | in_progress | - | - | - | - | 19 ACs | per SPEC | `active/personal-tracker-realignment_02-10-26/` | batches 1-2 (T32-T39), S5a (T40), S11a/b (T42, T43) and zoom fix (T44) merged, `fc12f27`; S5b (T41) planned; S9 later; S10 optional, now unblocked; PC probes pending; workers about 59.0 USD of 75 (ceiling 45 -> 60 -> 75), T44 and testers unmetered | - |
| P5 | narrative baskets: user-defined baskets, equal-weight view, mindshare share-of-total, raw-only /narrative | H | proposed | — | P4 | — | — | 12 active ACs | per SPEC | `process/general-plans/active/narrative-baskets_02-10-26/` | live probe per signal on user PC | — |
| P6 | LSE equities page with Add button, private-use note | M | in_progress | — | P4 | — | — | realignment SPEC | per SPEC | REALIGN SPEC | S3 adapter merged (T33, probe pending); S9 page unplanned, needs S5 | — |
| P7 | protect pytrends partial-hour fix and nightly archive (guard tests) | M | proposed | P4 | — | — | — | BASKETS Decision 16, AC-25 | RT2 | BASKETS SPEC | — | — |

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
| R12 | deploy fixes: kill-by-port before build, stale-build guard in `start-web`, post-start smoke check | M | accepted | P2 | - | workers W1-W4 | `claude/r12-deploy-fixes` (merged) | owns `deploy/*.ps1`; user PC record 10-10-26 | RT4 | PR #45 `86ddebc` (code), PR #48 `a2fd4b5` (record); review-decision approved-with-concerns; W1 2.45 + W2 4.56 + W3 0.91 + W4 0.77 USD | ACCEPTED WITH KNOWN GAPS (W1-W4): HTTP non-200 and build-id-mismatch smoke branches shape-tested only; exit 6 seen only for process-exited; failed-smoke port stop could exit 5 first; invalid WebPort under -ReportOnly exits 2. W4 self-merged PR #48 despite NEVER merge | `active/r12-deploy-fixes_03-10-26/` (left in place; archive needs the user's go) |
| R13 | salvage `claude/exciting-meitner-hy50kn` selectively | H | accepted | — | — | Gate 2 execute | same | TAKE: LSE folder, strip fixes; DROP: duplicate board | RT0, C14 | `448b10c`; vc-tester green; user accepted AC-R6 | other hunks not taken | `process/general-plans/completed/lse-data-verification_17-09-26/` |
| R14 | adopt `pensive-dijkstra` MASTER-PLAN rev 6 as registry base | H | accepted | — | — | Gate 2 execute | same | rev 6 `18ffd4f` | C14 | `c33fa96`; green | — | `process/archive/master-plan-revisions_02-10-26.md` |

## Carried notes

- Open backlog notes (`process/general-plans/backlog/<name>_NOTE_<dd-mm-yy>.md`): `screener-weekly-bars-flake`, `mapping-tripwire-gap`, `pipeline-etf-flows-atomic-write`, `pipeline-cron-firing-confirmation`, `token-usage-telemetry`, `agents-skills-symlink-windows`, `deploy-runtime-user-pc-verification`, `gate5-deferred-candidates`, `old-branches-review`, `p3-ui-open-decisions`, `screener-research-findings`, `lse-live-shape-verification`, `spaghetti-toggle-persistence`, `screener-group-sort`, `screener-live-ondemand-states-contrast`, `screener-passive-polls`.
- Envelope rule (from the 10-10-26 lapses, `process/archive/index.md`): workers get "needs_input means STOP, do not merge, do not open a new PR; cost is reported by the planner, not the worker"; the planner measures cost per session.
- Known condition: `validate-backlog-notes` fails 45 notes (older schema).
- Linter/formatter: none configured (undone half of T13, not a task).

## Maintaining this file

At each planner session end: re-verify first (git log, file existence, `gh pr view`); never copy numbers from context docs; update `Last verified` and the base SHA; one row per task; move superseded narrative to the archive, never delete it.
