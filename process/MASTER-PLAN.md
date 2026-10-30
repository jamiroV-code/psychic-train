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

**Last verified:** 2026-10-29 UTC at `origin/main` `4b3f70a` (PR #189 merge; nightly bot snapshot commits sit below it); PRs checked with `gh pr list --state all`; **built from:** revision 6 (`18ffd4f`) plus the T118 and T221 reconciliations. Gate reports: `process/general-plans/completed/master-planner-recovery_02-10-26/`.

**This file is the one board.** Each task has one row here; details live in its task folder. Revisions 1-6: `process/archive/master-plan-revisions_02-10-26.md`. Protocol: `process/development-protocols/master-planner.md`. Direction: north-star.md. State: current-state.md.

## Rules in one screen

- **Writer:** only the Master Planner session edits this file. Workers request updates in report headings 9 and 10.
- **Status vocabulary:** `proposed, approved, queued, in_progress, review, accepted, archived` plus `blocked, failed, cancelled, needs_input`. A status stronger than `review` needs independent evidence (an independent review report, CI on the merge SHA read with `gh`, vc-tester, or the owner); a merge alone is `review`. `UNVERIFIED` = not re-checked.
- **IDs:** `T#` historical tasks, `R#` recovery program, `P#` programs and product tasks. `Prio` is H / M / L. Test tiers are written RT0-RT4 (operating-instructions.md).
- **Lanes:** max 3 concurrent worker sessions, excluding the Master Planner. Owned globs never overlap; shared files have one owner at a time.
- **`approved`** = standing EXECUTE consent for that task only.

## Active lanes

Open PRs: none at the 29-10-26 read (`gh pr list --state open`), before the T221 EXECUTE draft PR was opened; that PR waits for the owner's merge (D-28). Lanes: T221 (this docs catch-up, in_progress), T117 (independent review of T115: no report found, UNVERIFIED). P10: U1 #145, U2 #146, U3 #151, U4 #144, U6 #160 merged; U5 UNVERIFIED. P9: first dataset (BTC-HIST) open; owner-run probes pending; P8 PAUSED. Worker and planner spend: about 188 of the 200 USD ceiling at 21-10-26 (planner figures); spend after 21-10-26 is UNVERIFIED.

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
| T32-T40, T42-T44 | screener batches 1-4 and zoom fix | H / M | review (T39, T44 accepted) | P4 | - | workers | merged | per SPEC | per SPEC | batches 1-4 merged, `bfb7793` | PC probes pending | verbatim row: `process/archive/master-plan-archived-rows_21-10-26.md` |
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
| P4 | realignment: delete verdict code, screener groups, 30-coin cap, spaghetti, BTC leg strip, 15-min refresh | H | in_progress | - | - | - | - | 19 ACs | per SPEC | `active/personal-tracker-realignment_02-10-26/` | batches 1-5 merged (T32-T51), S10 optional and not started; PC probes pending; worker spend 86.13 of 100 USD at 13-10-26 | verbatim row: `process/archive/master-plan-archived-rows_21-10-26.md` |
| P5 | narrative baskets: My baskets, attention score vs top-100 reference, Discovery tab, daily refresh; verdict/momentum code deleted | H | merged | - | P4 | - | `claude/t68..t86-*` | 12 active ACs | RT0-RT3 | `active/narrative-baskets_02-10-26/`; merged 16-17 Oct (T68-T86, T87 BNB, T88 #124, T89 #125, T90 #126, T91 #128, T92 report #127, T93 #129) | owner live probes; X key and caps in private env | D-17..D-20; verbatim row: `process/archive/master-plan-archived-rows_21-10-26.md` |
| P6 | LSE equities page with Add button, private-use note | M | review | - | P4 | - | - | realignment SPEC | per SPEC | REALIGN SPEC | built: T45-T51, accepted with known gaps (PRs #54-#60); open: P-S9-2 (on-PC page, real-close timing), P-S9-3 (phone/iPad); gaps: `equities-known-gaps_NOTE_13-10-26.md` | `active/screener-batch5-equities_12-10-26/` (not archived, needs the user's go) |
| P7 | protect pytrends partial-hour fix and nightly archive (guard tests) | M | proposed | P4 | — | — | — | BASKETS Decision 16, AC-25 | RT2 | BASKETS SPEC | — | — |
| P8 | Human-confirmed market framework | M | proposed, PAUSED by owner 14-10-26 | - | - | - | - | owner must decide which input fits which timeframe before resume | per SPEC | SPEC `active/market-framework_13-10-26/`; PR #63 | paused; its proposed exception text (labelled D-15 in the SPEC) is renumbered on resume | `active/market-framework_13-10-26/` |
| P9 | Data integration tooling: REA wrapper + Scrapling tiers 1-3, `tools/data-integration` | M | approved (owner 14-10-26) | - | - | workers | `claude/t53..t67-*` | PLAN PASS; programme built, merged 13-16 Oct (T53-T67, PRs #66-#95), D-15, D-16 | RT0-RT3; worker spend 97.66 USD | plan `active/data-integration-tooling_13-10-26/` | BTC-HIST open; owner probes AC-16/17/20 pending; tiers 2/3 not proven live; P8 stays PAUSED | verbatim row: `process/archive/master-plan-archived-rows_21-10-26.md` |
| P10 | weighted attention signal and tradeable universe | H | in_progress | P5 | - | workers per slice | `claude/t96..t118-*` | weighted scoring W1-W3, W9 done, weights v2 (#156); universe U1 #145, U2 #146, U3 #151, U4 #144, U6 #160 merged; U5 UNVERIFIED. Proposed, not approved: W4 detail table, W5 github_dev, W6 defillama, W7 exchange_activity (Coinbase, Kraken). Trends T100a, T100b, T100c and W8a-W8d2 merged, see board-2 | RT0-RT3; ceiling 200 USD | SPECs and PLAN in `active/narrative-baskets_02-10-26/` (`weighted-signal_SPEC`, `universe-narratives_SPEC`, `universe-narratives_PLAN`); rows T95-T118 below, T119-T221 in `process/MASTER-PLAN-board-2_29-10-26.md` | G-OWN review of the 11-narrative list passed by the owner 21-10-26 (planner-reported), merged as #148; Reddit and X access or enablement status UNVERIFIED (W8c #185 and W8d2 #186 code merged); weights are the owner's call (D-24); exchange tokens are IN as a narrative (D-27, #160); scheduled checks `trig_01L2U9sNDtrJ59DCjvXYdBVG` (2027-01-18 calibration) and `trig_015hASBMDARhqyxofVKv3Ghd` (2027-04-18 suggestions); T96-T107 skipped PLAN/VALIDATE/EVL (D-26) | D-22..D-28 |

### Weighted signal and universe tasks (T88-T118, compact rows)

Columns: ID · What · Status · PR / evidence · Cost. The 21-10-26 rows with their cost figures are verbatim in `process/archive/master-plan-archived-rows_29-10-26.md` (planner-measured costs are there; none is repeated or extended here). `review` = merged, not independently reviewed or EVL-gated. Report-only tasks have no PR. Tasks T119-T221: see `process/MASTER-PLAN-board-2_29-10-26.md`.

| ID | What | Status | PR / evidence | Cost |
|---|---|---|---|---|
| T88, T89, T93 | P5 refresh fix, verifier fix, extra hardening | review | #124, #125, #129 | see archive |
| T95, T97, T109, T116 | report-only: discovery data check, sources audit, reviews | review | report only | see archive |
| T96, T98, T99, T101, T102 | discovery lag fix, weighted-signal SPEC, wiki articles, W1 scoring, Wikipedia title checker | review | #131, #132, #133, #134, #135 | see archive |
| T103, T104, T105, T106, T107 | W2 history endpoint, W3 chart, W9 frozen snapshots, Discovery table, chart panels | review | #136, #138, #137, #140, #139 | see archive |
| T108, T111, T112 | universe-narratives SPEC, PLAN, VALIDATE (`Gate: PASS`) | review | #141, #142, #143 | see archive |
| T110 | small fixes on #140 | review | commit `d434621` inside #140 | see archive |
| T113 | U1 narratives file and loader | review | #145 (part merged before review), merged 2026-10-21 | see archive |
| T114 | U4 symbol source; owner probe P-CG passed 21-10-26 (planner-reported, see archive) | review | #144 (part merged before review), merged 2026-10-21 | see archive |
| T115 | U2 reasoned exclusions, label-only volume | review | #146, merged 2026-10-21, merge `911a703` | 3.75 (21-10-26 row) |
| T117 | independent review of T115 | UNVERIFIED | no report file found in the repo at 29-10-26; whether it ran is not recorded | unmeasured |
| T118 | docs catch-up T95-T117 | review | #147, merged 2026-10-21, merge `b616e45` | unmeasured |
| T100 | Trends backfill (original proposal); T100a, T100b, T100c merged, see board-2 | proposed | not approved as a single task | - |

Worker spend: about 188 of the 200 USD ceiling at 21-10-26 (planner figures); spend after 21-10-26 is UNVERIFIED.

### Recovery program (master-planner-recovery)

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R4 | master-planner.md protocol + templates | H | review | — | — | Gate 2 execute | same | F7, F11 | RT0, C7, C12 | `b78e652`; green | branch-delete unverified | `process/development-protocols/master-planner.md` |
| R8 | test policy into all-tests.md | M | review | — | R6 | Gate 4 execute + independent vc-tester | same | F12, planner budget pin | RT0, G4-1..G4-11 | `753db23`; green | needs user's Gate 4 acceptance | operating-instructions.md, all-tests.md |
| R9 | housekeeping (approved items only) | L | proposed | — | — | — | — | H1-H10 per approval | validators | — | user 03-10-26: H2 = T20, H8 = T16, H1 declined (T17), rest deferred | backlog `gate5-deferred-candidates_NOTE_03-10-26.md` |
| R10 | deploy path doc + stale-build guard proposal | M | proposed | — | — | — | — | RECOVERY section 8 | RT0 | — | — | Gate 5 |
| R11 | archive index + session triage | L | proposed | — | — | — | — | grow `process/archive/index.md` | RT0 | — | — | Gate 5 |
| R12 | deploy fixes: kill-by-port before build, stale-build guard in `start-web`, post-start smoke check | M | accepted | P2 | - | workers W1-W4 | `claude/r12-deploy-fixes` (merged) | owns `deploy/*.ps1`; user PC record 10-10-26 | RT4 | PR #45 `86ddebc` (code), PR #48 `a2fd4b5` (record); review-decision approved-with-concerns; W1 2.45 + W2 4.56 + W3 1.39 + W4 0.77 USD | ACCEPTED WITH KNOWN GAPS (W1-W4): HTTP non-200 and build-id-mismatch smoke branches shape-tested only; exit 6 seen only for process-exited; failed-smoke port stop could exit 5 first; invalid WebPort under -ReportOnly exits 2. W4 self-merged PR #48 despite NEVER merge | `active/r12-deploy-fixes_03-10-26/` (left in place; archive needs the user's go) |

## Carried notes

- Open backlog notes: all files in `process/general-plans/backlog/` (`<name>_NOTE_<dd-mm-yy>.md`; read `_GUIDE.md`). Closed: `lse-live-shape-verification` (12-10-26). New 13-10-26: `equities-known-gaps`, `lse-api-key-deploy-handling`.
- Envelope rule (from the 10-10-26 lapses, `process/archive/index.md`): workers get "needs_input means STOP, do not merge, do not open a new PR; cost is reported by the planner, not the worker"; the planner measures cost per session from the session record at report time and checks the 7 USD ask point (T41 passed it unrecorded).
- Known condition: `validate-backlog-notes` fails 45 notes (older schema).
- Linter/formatter: none configured (undone half of T13, not a task).

## Maintaining this file

At each planner session end: re-verify first (git log, file existence, `gh pr view`); never copy numbers from context docs; update `Last verified` and the base SHA; one row per task; move superseded narrative to the archive, never delete it.
