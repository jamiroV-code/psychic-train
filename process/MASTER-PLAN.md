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

**Last verified:** 2026-10-03 00:20 UTC · **base:** `origin/main` `5878b16` · **built from:** revision 6 (`18ffd4f`, branch `claude/pensive-dijkstra-ko69oi`) on branch `claude/pensive-albattani-ou0cgv` (Gate 2 of the master-planner-recovery plan).

**This file is the one board.** Each task has one row here; details live in its task folder. Revisions 1 to 6 (narrative history, lane reports, worktree plans, dependency graph) are preserved whole in `process/archive/master-plan-revisions_02-10-26.md`. Protocol (lifecycle, acceptance rule, envelope, report, archive operations): `process/development-protocols/master-planner.md`. Product direction: north-star.md. Observed state: current-state.md.

## Rules in one screen

- **Writer:** only the Master Planner session edits this file. Workers request updates in report headings 9 and 10.
- **Status vocabulary:** `proposed, approved, queued, in_progress, review, accepted, archived` plus `blocked, failed, cancelled, needs_input`. A status stronger than `review` needs independent evidence (merged PR, CI, vc-tester, user). `UNVERIFIED` marks a claim not re-checked this revision.
- **IDs:** `T#` historical tasks, `R#` recovery program, `P#` programs and product tasks. `Prio` is H / M / L. Test tiers are written RT0-RT4 (operating-instructions.md).
- **Lanes:** max 3 concurrent worker sessions, excluding the Master Planner. Owned globs never overlap; shared files (`.gitignore`, `process/context/all-context.md`, CLAUDE.md) have one owner at a time.
- **`approved`** = standing EXECUTE consent for that task only; the Master Planner may spawn a worker for it without asking again.

## Active lanes

| Lane | Task | Branch / worktree | Owns | Must not touch |
|---|---|---|---|---|
| (none) | P1, P2, P3 lanes merged 2026-10-01 (PRs #11, #10, #9) | — | — | — |

Merge token: free.

## Registry

Columns: ID · Objective · Prio · Status · Parent · Deps · Worker/session · Branch/worktree · Scope + acceptance · Test req/budget · Report + commit refs · Blockers/risks · Outcome / archive location. A dash means none or not applicable.

### Historical tasks (reconciled from revision 6)

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | pytrends partial-hour zeros in `_fetch_live` | H | accepted | — | — | — | merged | `isPartial` rows dropped before last point | done | PR #8; guard at `pytrends_adapter.py` lines 66-67 on main (re-checked 03-10-26) | — | `process/features/narrative-mindshare/completed/pytrends-partial-hour-fix_28-09-26/` |
| T1b | `isPartial` guard in batched path `_fetch_batch_live` | H | accepted | T1 | — | — | merged | same guard in the batched fetch | done | PR #6/#7; guard at `pytrends_adapter.py` lines 204-205 on main (re-checked 03-10-26, was UNVERIFIED); live values 3 nights (rev 4) | — | on main |
| T3 | narrative-v2 (PR #7) | H | review | — | T1b | — | merged | RFC-1..6 VERIFIED, RFC-7 CODE DONE | RT4-style user walkthrough | PR #7 | AC-14 user walkthrough outstanding: `needs_input` | `process/features/narrative-mindshare/active/narrative-v2_25-09-26/` |
| T4 | Reddit secrets, or drop Reddit | M | needs_input | — | — | user | — | add repo secrets plus workflow env mapping, or drop the source | — | rev 6 | user said leave for now; Reddit archives nothing | — |
| T5 | `/pairs` automation | M | review | — | — | — | merged | nightly refresh then compute | CI | `pairs-refresh-snapshot.yml` (P1, PR #11) | CODE DONE not VERIFIED; commit step inert on Actions | — |
| T7 | narrative-dashboard v1 closeout | M | needs_input | — | T3 | user PC | — | 2 PENDING review decisions; AC-3/AC-12 | user PC | `harness/review-decision.json`, `harness/rfc-004/review-decision.json` still PENDING (re-checked 03-10-26) | user PC only | `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/` |
| T8 | refresh context docs | M | superseded by R2/R3 | — | — | — | — | folded into this program | — | — | — | R2, R3 |
| T9 | charting page | L | cancelled | — | — | — | — | realignment AC-17: charts page not built | — | REALIGN SPEC | — | — |
| T10 | cross-signal confidence view | L | cancelled | — | — | — | — | realignment AC-18: principle retired | — | REALIGN SPEC | — | decisions.md D-2 |
| T11 | lying plan status strips | L | review | — | R13 | — | this branch | fixed strips in liqtide-snapshot-tooling and momentum-screener plans | RT0 | R13 commit `448b10c` (salvaged from `exciting-meitner`) | chain-growth strip fix was PR #5 (UNVERIFIED on main) | — |
| T12 | equity provider decision | M | proposed -> superseded in part | — | R13 | — | — | LSE verdict ADOPT-WITH-LIMITS, private use | — | `process/general-plans/completed/lse-data-verification_17-09-26/VERDICT.md` (R13) | equities page is P6 | P6 |
| T13 | CI | M | accepted | — | — | — | merged | pytest, vitest, `tsc`, island build on PRs and main pushes | — | `.github/workflows/ci.yml` (jobs `api — pytest`, `web — vitest, tsc, island build`) | no e2e, no linter/formatter | on main |
| T14 | UI shell | M | review | P3 | — | — | merged | Direction D shell | user visual acceptance | PR #9 | no human visual acceptance recorded | `process/general-plans/active/ui-shell_28-09-26/` |
| T15 | adapter provider-term flags | L | proposed | — | — | — | — | demoted 02-10-26: provider terms no longer shape design (personal use) | — | RECOVERY Q7 | — | — |
| T16 | root README | M | proposed | — | — | — | — | runbook README | RT0 | no root README (re-checked 03-10-26) | guide-sync baseline failure until done | F13 (Gate 5) |
| T17 | `.agents/skills` duplicate | L | proposed | — | user approval | — | — | replace 339 tracked files with a symlink (H1) | validators before/after | — | Windows symlink behaviour unverified | H1 (Gate 5) |
| T18 | dead `write/read_confirmed_boundaries` | L | proposed | — | — | — | — | delete after evidence | full pytest | grep 03-10-26: defined in `cache.py` 370/376, no non-test caller | static search misses dynamic use | H6 |
| T19 | archive stale plans from `active/` | L | proposed | — | — | — | — | e.g. momentum-screener_17-09-26 | RT0 | — | moves history (reversible) | archive index, Gate 5 |
| T20 | `web/tsconfig.tsbuildinfo` tracked | L | proposed | — | user approval | — | — | untrack and ignore (F14) | RT0 | still tracked (re-checked 03-10-26) | — | F14 (Gate 5) |
| T21 | `cache.py` refactor | L | proposed | — | everything merged | — | solo | six near-identical path/read/write triplets | RT3 | — | low value vs personal-use goal | — |
| T22 | cache-isolation trap in tests | L | proposed | — | — | — | — | not a live bug | — | rev 6 | — | — |
| T23 | reconcile branches | M | in_progress | — | — | Master Planner | — | ref-only fetch done 02-10-26; per-file review before any deletion | — | RECOVERY section 7 | 12 pre-existing branches need per-branch approval | — |
| T24 | one status board | M | superseded by R2/R6 | — | — | — | — | MASTER-PLAN is the one board; exciting-meitner board dropped in R13 | — | decisions.md D-5 | — | this file |
| T25 | delete stale branches | L | proposed | — | T23 | — | — | per-branch user approval; `compassionate-goldberg` is the only safe candidate (0 files differ) | — | — | standing consent does not cover these | — |
| T26 | pytrends 0.0 questions: `layer 2 crypto`/`l2s` reads 0.0 nightly; `pytrends-blended/rwa` wrote 0.0 as `fresh` on a night `pytrends/RWA crypto` read 74.0 (same shape as the T1 bug); confirm RFC-1 sufficiency gating surfaces these as `insufficient` | M | needs_input | — | T3 | — | — | open finding, not fixed | — | rev 6 ("T26 revised") | data quality | — |
| T27 | snapshot cron timing: all five crons at 11:17-13:17 UTC plus a midnight-crossing warning | M | review | P1 | — | — | merged | crons fire before UTC midnight | `gh run list` over 2-3 nights | PR #11; snapshot commits on main 2026-10-02 17:53Z, 18:04Z, 18:26Z | run start times not checked this revision | — |
| T28 | non-atomic parquet writes | H | review | P1 | — | — | merged | `cache.py` temp-then-rename | full pytest (P1 EVL) | PR #11 (`ba82986`) | `etf_flows_adapter.merge_into_cache` still non-atomic (backlog note) | — |
| T2, T6 | not present in any revision | — | n/a | — | — | — | — | numbering gaps, recorded as unknown, not invented | — | — | — | — |

### Programs and product tasks

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | pipeline completeness | M | review | — | — | — | merged | scheduled refresh jobs, atomic writes, cron timing | CI | PR #11; closeout in `pipeline-completeness_28-09-26/` | real cron firing unverified; etf_flows write non-atomic; inert commits | `process/general-plans/active/pipeline-completeness_28-09-26/` |
| P2 | deployability (home PC + Tailscale) | M | review | — | — | — | merged | `deploy/` launchers, CORS, runbook | user PC | PR #10 | runtime only verifiable on the user's PC | `process/general-plans/active/deployability_28-09-26/` |
| P2b | stale-build guard | M | superseded by R12 | P2 | — | — | — | gap from the 2026-10-01 live incident | — | — | — | R12 |
| P3 | UI Direction D | M | review | — | — | — | merged | same as T14 | user visual acceptance | PR #9 | — | `process/general-plans/active/ui-shell_28-09-26/` |
| P4 | realignment: delete verdict code; screener RSI, groups, 30-coin cap, spaghetti chart, BTC leg strip, 15-min refresh, lean storage | H | proposed | — | — | — | — | 19 active ACs | per SPEC | `process/general-plans/active/personal-tracker-realignment_02-10-26/` | — | — |
| P5 | narrative baskets: user-defined baskets, equal-weight view, mindshare share-of-total, raw-only /narrative | H | proposed | — | P4 | — | — | 12 active ACs | per SPEC | `process/general-plans/active/narrative-baskets_02-10-26/` | live probe per signal on user PC | — |
| P6 | LSE equities page with Add button, private-use note | M | proposed | — | P4 | — | — | realignment SPEC | per SPEC | REALIGN SPEC | — | — |
| P7 | protect pytrends partial-hour fix and nightly archive (guard tests) | M | proposed | P4 | — | — | — | BASKETS Decision 16, AC-25 | RT2 | BASKETS SPEC | — | — |

### Recovery program (master-planner-recovery)

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | re-verify ground truth, write current-state.md | H | in_progress | — | — | Gate 2 execute | `claude/pensive-albattani-ou0cgv` | F2 | RT0, C14 | `3562deb` | awaiting independent Gate 2 confirmation | — |
| R2 | north-star.md + decisions.md | H | in_progress | — | — | Gate 2 execute | same | F1, F3 | RT0, C8, C14 | `3562deb` | same | — |
| R3 | slim all-context.md, create context-changelog.md | H | in_progress | — | — | Gate 2 execute | same | F4, F5, F16, F17 | RT0, C5, C6, C7 | `0e593cd`, `bcb62e4`, `5a73705` | same | — |
| R4 | master-planner.md protocol + templates | H | in_progress | — | — | Gate 2 execute | same | F7, F11 | RT0, C7, C12 | `b78e652`; step (vii) tool check run by the orchestrator session | same | — |
| R5 | registry rewrite in this file | H | in_progress | — | R14 | Gate 2 execute | same | F6, F8 | RT0, C11, C14 | this revision | same | — |
| R6 | CLAUDE.md / AGENTS.md role-neutral rewrite, ENTRY-SET drift check | H | proposed | — | Gate 2 | — | — | F9, F10 | C1, C2, C9, C10 | — | re-enters VALIDATE | Gate 3 |
| R7 | token baseline measurement | M | proposed | — | R6 | — | — | C3, C4, sampled sessions | — | — | — | Gate 3 |
| R8 | test policy into all-tests.md | M | proposed | — | — | — | — | F12 | three suites once | — | — | Gate 4 |
| R9 | housekeeping (approved items only) | L | proposed | — | — | — | — | H1-H10 per approval | validators | — | — | Gate 5 |
| R10 | deploy path doc + stale-build guard proposal | M | proposed | — | — | — | — | RECOVERY section 8 | RT0 | — | — | Gate 5 |
| R11 | archive index + session triage | L | proposed | — | — | — | — | grow `process/archive/index.md` | RT0 | — | — | Gate 5 |
| R12 | deploy fixes: kill-by-port before build, stale-build guard in `start-web`, post-start smoke check | M | proposed (decision to build recorded; becomes `approved` on confirmation of its task brief) | P2 | — | — | — | high-risk deploy class | RT4 | — | Windows runtime unverifiable from cloud: worker stops at `review` | Gate 5 |
| R13 | salvage `claude/exciting-meitner-hy50kn` selectively | H | in_progress | — | — | Gate 2 execute | same | TAKE: LSE folder moved `active/` -> `completed/` (verdict, findings, EVL/PVL reports, results.tsv, both Python files as-is), status-strip fixes, data-sources LSE hunks; DROP: duplicate status board in all-context.md | RT0, C14 | `448b10c`; Approvals Log row (operation A) | unreviewed, not taken: the other all-context.md changelog hunks of that branch, the yfinance backlog note edit; branch not deleted | `process/general-plans/completed/lse-data-verification_17-09-26/` |
| R14 | adopt `pensive-dijkstra` MASTER-PLAN rev 6 as registry base | H | in_progress | — | — | Gate 2 execute | same | rev 6 pinned `18ffd4f014f4e5ea0f5d654688875a9300b30ab4`, tip unchanged at Gate 2 start | C14 rev 6 preservation | `c33fa96` | branch not deleted | `process/archive/master-plan-revisions_02-10-26.md` |

## Carried notes

- Backlog notes still open: `screener-weekly-bars-flake_NOTE_28-09-26.md`, `mapping-tripwire-gap_NOTE_28-09-26.md`, `pipeline-etf-flows-atomic-write_NOTE_29-09-26.md`, `pipeline-cron-firing-confirmation_NOTE_01-10-26.md`, plus the three Gate 2 stubs (`token-usage-telemetry`, `agents-skills-symlink-windows`, `deploy-runtime-user-pc-verification`, all `_NOTE_02-10-26.md`), in `process/general-plans/backlog/`.
- Accepted known gaps (not tasks): listed in the revisions archive, section "Known Gaps Carried Forward".
- Linter/formatter: none configured; the half of T13 left undone, not yet a task.

## Maintaining this file

On every planner session end: re-verify before writing (git log, file existence, `gh pr view`); never copy numbers from context docs; update the `Last verified` line and the base SHA; keep one row per task; move superseded narrative to the archive, never delete it. A task earns a row only if it has real project impact.
