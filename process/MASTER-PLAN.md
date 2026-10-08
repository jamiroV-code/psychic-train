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

**Last verified:** 2026-10-04 UTC at `origin/main` `605424d` (batch 1 S1, S2, S3, S8 merged as T32-T35; R12 blocked) · **built from:** revision 6 (`18ffd4f`). Gate reports: `process/general-plans/completed/master-planner-recovery_02-10-26/`.

**This file is the one board.** Each task has one row here; details live in its task folder. Revisions 1-6 are preserved whole in `process/archive/master-plan-revisions_02-10-26.md`. Protocol (lifecycle, acceptance rule, envelope, report, archive operations): `process/development-protocols/master-planner.md`. Direction: north-star.md. State: current-state.md.

## Rules in one screen

- **Writer:** only the Master Planner session edits this file. Workers request updates in report headings 9 and 10.
- **Status vocabulary:** `proposed, approved, queued, in_progress, review, accepted, archived` plus `blocked, failed, cancelled, needs_input`. A status stronger than `review` needs independent evidence (merged PR, CI, vc-tester, user). `UNVERIFIED` marks a claim not re-checked this revision.
- **IDs:** `T#` historical tasks, `R#` recovery program, `P#` programs and product tasks. `Prio` is H / M / L. Test tiers are written RT0-RT4 (operating-instructions.md).
- **Lanes:** max 3 concurrent worker sessions, excluding the Master Planner. Owned globs never overlap; shared files (`.gitignore`, `process/context/all-context.md`, CLAUDE.md) have one owner at a time.
- **`approved`** = standing EXECUTE consent for that task only; the Master Planner may spawn a worker for it without asking again.

## Active lanes

No worker lane active. Merge token: free.

## Registry

Columns: ID · Objective · Prio · Status · Parent · Deps · Worker/session · Branch/worktree · Scope + acceptance · Test req/budget · Report + commit refs · Blockers/risks · Outcome / archive location. A dash means none or not applicable.

### Historical tasks (reconciled from revision 6)

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | pytrends partial-hour zeros in `_fetch_live` | H | accepted | — | — | — | merged | `isPartial` rows dropped | done | PR #8; guard `pytrends_adapter.py:66-67` | — | `narrative-mindshare/completed/pytrends-partial-hour-fix_28-09-26/` |
| T1b | `isPartial` guard in batched path `_fetch_batch_live` | H | accepted | T1 | — | — | merged | same guard in the batched fetch | done | PR #6/#7; guard `pytrends_adapter.py:204-205`; live 3 nights | — | on main |
| T3 | narrative-v2 (PR #7) | H | review | — | T1b | — | merged | RFC-1..6 VERIFIED, RFC-7 CODE DONE | RT4-style user walkthrough | PR #7 | AC-14 user walkthrough outstanding: `needs_input` | `narrative-mindshare/active/narrative-v2_25-09-26/` |
| T4 | Reddit secrets, or drop Reddit | M | needs_input | — | — | user | — | add repo secrets plus workflow env mapping, or drop the source | — | rev 6 | user said leave for now; Reddit archives nothing | — |
| T5 | `/pairs` automation | M | review | — | — | — | merged | nightly refresh then compute | CI | PR #11 | CODE DONE not VERIFIED; commit inert on Actions | — |
| T7 | narrative-dashboard v1 closeout | M | needs_input | — | T3 | user PC | — | 2 PENDING review decisions; AC-3/AC-12 | user PC | two `review-decision.json` PENDING | user PC only | `narrative-mindshare/active/narrative-dashboard_24-09-26/` |
| T8 | refresh context docs | M | superseded by R2/R3 | — | — | — | — | folded into this program | — | — | — | R2, R3 |
| T9 | charting page | L | cancelled | — | — | — | — | realignment AC-17: charts page not built | — | REALIGN SPEC | — | — |
| T10 | cross-signal confidence view | L | cancelled | — | — | — | — | realignment AC-18: principle retired | — | REALIGN SPEC | — | decisions.md D-2 |
| T11 | lying plan status strips | L | review | — | R13 | — | this branch | fixed strips in two plans | RT0 | R13 commit `448b10c` | chain-growth strip fix: PR #5 (UNVERIFIED on main) | — |
| T12 | equity provider decision | M | proposed -> superseded in part | — | R13 | — | — | LSE verdict ADOPT-WITH-LIMITS, private use | — | `completed/lse-data-verification_17-09-26/VERDICT.md` | equities page is P6 | P6 |
| T13 | CI | M | accepted | — | — | — | merged | pytest, vitest, `tsc`, island build on PRs and pushes | — | `.github/workflows/ci.yml` | no e2e, no linter/formatter | on main |
| T14 | UI shell | M | review | P3 | — | — | merged | Direction D shell | user visual acceptance | PR #9 | no human visual acceptance recorded | `active/ui-shell_28-09-26/` |
| T15 | adapter provider-term flags | L | proposed | — | — | — | — | demoted 02-10-26: provider terms no longer shape design (personal use) | — | RECOVERY Q7 | — | — |
| T16 | root README | M | archived | — | PR #13 merged | worker (pilot B) | `claude/t16-root-readme` | owns `README.md`; guide-sync 0 | RT0, budget 0 | PR #14 `351f946`; vc-tester PASS | 0.7556444 USD | — |
| T17 | `.agents/skills` duplicate | L | cancelled | — | — | — | — | H1 symlink | — | — | user 03-10-26: leave as is (accepted gap; reopen on request) | backlog `agents-skills-symlink-windows_NOTE_02-10-26.md` |
| T18 | remove dead confirmed-boundaries helpers in `cache.py` | L | archived | — | — | worker, `session_01Ln4319nS2H3ig6bttKTYiJ` | `claude/t18-dead-boundaries` (merged) | delete helpers + 3 tests | RT3, budget 2 | PR #23 `42d8ca8`; vc-tester PASS; pytest 873->870; 0.8634002 USD | accepted deviation; README mention to R12 | H6 |
| T19 | archive stale plans from `active/` | L | archived | — | — | worker, `session_01GvRG5Mffm2zKK3prSqd85Z` | `claude/t19-archive-stale-plans` (merged) | `momentum-screener_17-09-26` to `completed/` | RT0, budget 0 | PR #22 `5ace8b9`; 27 files moved; vc-tester PASS; 0.868232 USD | 18 files name old path: left as history | archive index, Gate 5 |
| T20 | untrack `web/tsconfig.tsbuildinfo` | L | archived | — | PR #13 merged | worker (pilot A) | `claude/t20-untrack-tsbuildinfo` | untrack plus ignore line | RT0, budget 0 | PR #15 `54157e2`; vc-tester PASS | 0.882417 USD; home-PC step (E9) | — |
| T21 | `cache.py` refactor | L | proposed | — | everything merged | — | solo | six near-identical path/read/write triplets | RT3 | — | low value vs personal-use goal | — |
| T22 | cache-isolation trap in tests | L | proposed | — | — | — | — | not a live bug | — | rev 6 | — | — |
| T23 | reconcile branches | M | in_progress | — | — | Master Planner | — | seven branches deleted by user 03-10-26 (merged per PRs #7-#11) | — | RECOVERY section 7 | 3 left (kind-tesla, inspiring-pasteur, split-all-context): user may delete | — |
| T24 | one status board | M | superseded by R2/R6 | — | — | — | — | MASTER-PLAN is the one board; exciting-meitner board dropped in R13 | — | decisions.md D-5 | — | this file |
| T25 | delete stale branches | L | accepted | — | T23 | user | — | six approved plus probe deleted by the user in GitHub's UI 03-10-26 | — | `git ls-remote --heads origin`: all seven names 0 | planner cannot delete | Approvals Log |
| T26 | pytrends 0.0 questions (`layer 2 crypto`, `l2s`, `pytrends-blended/rwa`); confirm RFC-1 gating marks them `insufficient` | M | needs_input | — | T3 | — | — | open finding, not fixed | — | rev 6 | data quality | — |
| T27 | snapshot cron timing: all five crons at 11:17-13:17 UTC plus a midnight-crossing warning | M | review | P1 | — | — | merged | crons fire before UTC midnight | `gh run list` | PR #11; snapshot commits on main 02-10-26 | start times unchecked | — |
| T28 | non-atomic parquet writes | H | review | P1 | — | — | merged | `cache.py` temp-then-rename | full pytest (P1 EVL) | PR #11 (`ba82986`) | `etf_flows_adapter.merge_into_cache` non-atomic (backlog) | — |
| PERF | performance baselines; measure only | L | accepted | — | after T18 merged (done) | worker `session_01CFvdvcHZF448EeYTXgpL8N` | `claude/perf-baselines` | offline timings | RT0 | PR #24 `487fa65`; vc-tester PASS: api 870/1/5/1, 296.30 s; 0.9787132 USD | web rows measured by T30 (test 12.53 s, tsc 4.40 s, build 7.30 s); heading 11 abbreviated | `completed/perf-baselines_03-10-26/` |
| T29 | backtest script report-dir segment `active` -> `completed` | L | archived | T19 | T19 merged | `session_015whvAW5yLin6CWDsDu8nXj` | `claude/t29-backtest-report-dir` | one segment | RT2, budget 1 | PR #26 `2f34fac`; vc-tester PASS; 1.0054736 USD | — | `completed/t29-backtest-report-dir_03-10-26/` |
| T30 | PERF-web re-measure (test, tsc, island build, chunk gzip) | L | archived | PERF | PERF accepted | `session_01L5cLjw2rekuXBVPzWhiaof` | `claude/t30-perf-web-remeasure` | measure only | RT0, budget 0 | PR #28 `2eb6e25`; vc-tester PASS; chunk 184,870 B gz; 0.9862586 USD | — | `completed/t30-perf-web-remeasure_03-10-26/` |
| T31 | chain-growth rescue onto main | L | archived | T23 | — | `session_01CRoKgnU2U1UcMyqAAKTHjy` | `claude/t31-chain-growth-rescue` | 2 api path files, `onchain-activity/**` | RT2, budget 1 | PR #30 `34e3bb3`; vc-tester PASS; 0.5641288 USD | accepted doc deviations | `completed/t31-chain-growth-rescue_03-10-26/` |
| T32 | S1 freshness core: `freshness.py`, `fetched_at` sidecar, 200-bar sub-daily retention, tail fetch | H | review | P4 | — | `session_014QEGDPvhtypW82WNmy9KeE` | `claude/t32-s1-freshness-core` (merged) | S1 | RT3 | PR #34 `161e7be`; EVL PASS (pytest 931/2/5/0 after S1+S3); 5.5794842 USD | P-S1-1 PC probe outstanding | `active/screener-batch1_03-10-26/` |
| T33 | S3 LSE equities adapter + ticker store (`lse_adapter.py`, `equities_store.py`), private use | M | review | P6 | — | `session_01PcmprWjrPALpocq7NwWJEg` | `claude/t33-s3-lse-adapter` (merged) | S3 | RT3 | PR #33 `dc0cbb3`; EVL CONDITIONAL; 2.883962 USD | G-S3-6 `test_probe_fixture_parses` skipped until the user runs `s3-probe/lse_probe.py` (`LSE_API_KEY`) and copies the fixture to `api/tests/data/fixtures/lse_candles_probe_shape.json`; backlog `lse-live-shape-verification_NOTE_03-10-26.md` | `active/screener-batch1_03-10-26/` |
| T34 | S2 current-candle gain chips + UTC axis labels | H | review | P4 | T32 | `session_012TMn5iay2D3tq1Erh5efta` | `claude/t34-s2-chips-labels` (merged) | S2 | RT3 | PR #36 `605424d`; EVL PASS (U3 axis spike ok, no fallback); 4.9869365 USD | P-S2-1 PC probe outstanding; rightmost tick label can clip (left for S6) | `active/screener-batch1_03-10-26/` |
| T35 | S8 in-process background refresh worker (`SCREENER_REFRESH_WORKER`) | H | review | P4 | T32 | `session_01L2cTTiPVtJY6ewkc1oSkfF` | `claude/t35-s8-refresh-worker` (merged) | S8 | RT3 | PR #35 `d10aebf`; EVL PASS (+20 api tests); 4.1521902 USD | P-S8-1 overnight PC probe outstanding; G-S2-8 e2e not run (U-4). User decided 04-10-26: (a) `/api/regime/*` BTC 1d inline: fold into S7; (b) non-watchlist scalp queues a fetch per tick: accept; (c) latch recovery up to 3600 s: accept | `active/screener-batch1_03-10-26/` |
| T2, T6 | not present in any revision | — | n/a | — | — | — | — | numbering gaps, recorded as unknown, not invented | — | — | — | — |

### Programs and product tasks

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | pipeline completeness | M | review | — | — | — | merged | scheduled refresh jobs, atomic writes, cron timing | CI | PR #11; closeout in `pipeline-completeness_28-09-26/` | real cron firing unverified; etf_flows write non-atomic; inert commits | `active/pipeline-completeness_28-09-26/` |
| P2 | deployability (home PC + Tailscale) | M | review | — | — | — | merged | `deploy/` launchers, CORS, runbook | user PC | PR #10 | runtime only verifiable on the user's PC | `active/deployability_28-09-26/` |
| P2b | stale-build guard | M | superseded by R12 | P2 | — | — | — | gap from the 2026-10-01 live incident | — | — | — | R12 |
| P3 | UI Direction D | M | review | — | — | — | merged | same as T14 | user visual acceptance | PR #9 | — | `active/ui-shell_28-09-26/` |
| P4 | realignment: delete verdict code; screener RSI, groups, 30-coin cap, spaghetti chart, BTC leg strip, 15-min refresh, lean storage | H | in_progress | — | — | — | — | 19 ACs | per SPEC | `active/personal-tracker-realignment_02-10-26/` | batch 1 (S1, S2, S8 = T32, T34, T35) merged `605424d`, probes pending; S4-S7, S9, S10 not yet planned; spend 17.6025729 USD workers (T32-T35) plus two unmetered EVL runs, of 45 USD; S10 waits on R12 | — |
| P5 | narrative baskets: user-defined baskets, equal-weight view, mindshare share-of-total, raw-only /narrative | H | proposed | — | P4 | — | — | 12 active ACs | per SPEC | `process/general-plans/active/narrative-baskets_02-10-26/` | live probe per signal on user PC | — |
| P6 | LSE equities page with Add button, private-use note | M | in_progress | — | P4 | — | — | realignment SPEC | per SPEC | REALIGN SPEC | S3 adapter merged (T33, live-shape probe pending); S9 page not yet planned, needs S5 | — |
| P7 | protect pytrends partial-hour fix and nightly archive (guard tests) | M | proposed | P4 | — | — | — | BASKETS Decision 16, AC-25 | RT2 | BASKETS SPEC | — | — |

### Recovery program (master-planner-recovery)

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | re-verify ground truth, write current-state.md | H | accepted | — | — | Gate 2 execute | `claude/pensive-albattani-ou0cgv` | F2 | RT0, C14 | `3562deb`; vc-tester green | docs-only | `process/context/current-state.md` |
| R2 | north-star.md + decisions.md | H | accepted | — | — | Gate 2 execute | same | F1, F3 | RT0, C8, C14 | `3562deb`; vc-tester green | — | `process/context/north-star.md`, `process/context/decisions.md` |
| R3 | slim all-context.md, create context-changelog.md | H | accepted | — | — | Gate 2 execute | same | F4, F5, F16, F17 | RT0, C5, C6, C7 | `0e593cd`, `bcb62e4`, `5a73705`; vc-tester green; 1,223 -> 193 lines | — | `process/context/` root docs |
| R4 | master-planner.md protocol + templates | H | review | — | — | Gate 2 execute | same | F7, F11 | RT0, C7, C12 | `b78e652`; vc-tester green | branch-delete mechanism unverified | `process/development-protocols/master-planner.md` |
| R5 | registry rewrite in this file | H | accepted | — | R14 | Gate 2 execute | same | F6, F8 | RT0, C11, C14 | `dafa781`, `b36a0da`; C11 green | user accepted AC-R5, AC-R6 (03-10-26); caveat: probe branch delete failed | this file; `process/archive/index.md` |
| R6 | CLAUDE.md / AGENTS.md role-neutral rewrite, ENTRY-SET drift check | H | accepted | — | Gate 2 | Gate 3 execute | `claude/pensive-albattani-ou0cgv` | F9, F10 | RT0, C1, C2, C9, C10 (G3-1..G3-11) | `eee7709`, `0b3c9bf`; user accepted 03-10-26 | none open (budget: master-planner.md s.12) | decisions D-9, D-10 |
| R7 | token baseline measurement | M | accepted | — | R6 | Gate 3 execute + independent vc-tester | same | C3, C4, live probes B1, B2, P2 (route A, D-11) | cap 1 USD per run; 0.617 USD spent | first request: old planner 78,664 tokens, new 37,450, worker 37,921 | single-run samples; user accepted AC-R9 (03-10-26) | Gate 3 report |
| R8 | test policy into all-tests.md | M | review | — | R6 | Gate 4 execute + independent vc-tester | same | F12, planner budget pin | RT0, G4-1..G4-11; three suites once | `753db23`; tester green; CI green | needs user's Gate 4 acceptance | operating-instructions.md, all-tests.md |
| R9 | housekeeping (approved items only) | L | proposed | — | — | — | — | H1-H10 per approval | validators | — | user 03-10-26: H2 = T20, H8 = T16, H1 declined (T17), rest deferred | backlog `gate5-deferred-candidates_NOTE_03-10-26.md` |
| R10 | deploy path doc + stale-build guard proposal | M | proposed | — | — | — | — | RECOVERY section 8 | RT0 | — | — | Gate 5 |
| R11 | archive index + session triage | L | proposed | — | — | — | — | grow `process/archive/index.md` | RT0 | — | — | Gate 5 |
| R12 | deploy fixes: kill-by-port before build, stale-build guard in `start-web`, post-start smoke check | M | blocked | P2 | VALIDATE + user confirms brief | — | — | HIGH-RISK deploy class, brief only; owns `deploy/*.ps1`, `api/tests/deploy/` | RT4, budget 2 | brief `active/r12-deploy-fixes_03-10-26/` | no worker until VALIDATE and user confirms brief | backlog `gate5-deferred-candidates_NOTE_03-10-26.md` |
| R13 | salvage `claude/exciting-meitner-hy50kn` selectively | H | accepted | — | — | Gate 2 execute | same | TAKE: LSE folder, status-strip fixes, LSE hunks; DROP: duplicate status board | RT0, C14 | `448b10c`; vc-tester green; user accepted AC-R6 | other hunks not taken | `process/general-plans/completed/lse-data-verification_17-09-26/` |
| R14 | adopt `pensive-dijkstra` MASTER-PLAN rev 6 as registry base | H | accepted | — | — | Gate 2 execute | same | rev 6 pinned `18ffd4f` | C14 rev 6 preservation | `c33fa96`; vc-tester green | — | `process/archive/master-plan-revisions_02-10-26.md` |

## Carried notes

- Open backlog notes (`process/general-plans/backlog/<name>_NOTE_<dd-mm-yy>.md`): `screener-weekly-bars-flake`, `mapping-tripwire-gap`, `pipeline-etf-flows-atomic-write`, `pipeline-cron-firing-confirmation`, `token-usage-telemetry`, `agents-skills-symlink-windows`, `deploy-runtime-user-pc-verification`, `gate5-deferred-candidates`, `old-branches-review`, `p3-ui-open-decisions`, `screener-research-findings`, `lse-live-shape-verification`.
- Known condition: `validate-backlog-notes` fails 45 notes (older schema).
- Linter/formatter: none configured (undone half of T13, not a task).

## Maintaining this file

At each planner session end: re-verify first (git log, file existence, `gh pr view`); never copy numbers from context docs; update `Last verified` and the base SHA; one row per task; move superseded narrative to the archive, never delete it.
