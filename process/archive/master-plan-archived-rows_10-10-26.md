---
name: master-plan-archived-rows_10-10-26
description: "Registry rows of fully archived tasks (T16, T18, T19, T20, PERF, T29, T30, T31, T8, T9, T10, T17, T24, T25) moved out of MASTER-PLAN.md on 10-10-26 to keep it under its size cap. Verbatim copies."
date: 10-10-26
---

# MASTER-PLAN archived rows (moved 10-10-26)

Verbatim registry rows, same 13 columns as MASTER-PLAN.md (ID, Objective, Prio, Status, Parent, Deps, Worker/session, Branch/worktree, Scope + acceptance, Test req/budget, Report + commit refs, Blockers/risks, Outcome / archive location). Some rows carry fewer cells than the header, as they did in the registry.

| ID | Objective | Prio | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T16 | root README | M | archived | — | PR #13 merged | worker (pilot B) | `claude/t16-root-readme` | owns `README.md`; guide-sync 0 | RT0, budget 0 | PR #14 `351f946`; vc-tester PASS | 0.7556444 USD | — |
| T18 | remove dead confirmed-boundaries helpers in `cache.py` | L | archived | — | — | worker, `session_01Ln4319nS2H3ig6bttKTYiJ` | `claude/t18-dead-boundaries` (merged) | delete helpers + 3 tests | RT3, budget 2 | PR #23 `42d8ca8`; vc-tester PASS; 0.8634002 USD | README mention to R12 | H6 |
| T19 | archive stale plans from `active/` | L | archived | — | — | worker, `session_01GvRG5Mffm2zKK3prSqd85Z` | `claude/t19-archive-stale-plans` (merged) | `momentum-screener_17-09-26` to `completed/` | RT0, budget 0 | PR #22 `5ace8b9`; vc-tester PASS; 0.868232 USD | old paths left as history | archive index |
| T20 | untrack `web/tsconfig.tsbuildinfo` | L | archived | — | PR #13 merged | worker (pilot A) | `claude/t20-untrack-tsbuildinfo` | untrack plus ignore line | RT0, budget 0 | PR #15 `54157e2`; vc-tester PASS | 0.882417 USD; home-PC step (E9) | — |
| PERF | performance baselines; measure only | L | accepted | — | after T18 merged (done) | worker `session_01CFvdvcHZF448EeYTXgpL8N` | `claude/perf-baselines` | offline timings | RT0 | PR #24 `487fa65`; vc-tester PASS; 0.9787132 USD | web rows measured by T30 | `completed/perf-baselines_03-10-26/` |
| T29 | backtest script report-dir segment `active` -> `completed` | L | archived | T19 | T19 merged | `session_015whvAW5yLin6CWDsDu8nXj` | `claude/t29-backtest-report-dir` | one segment | RT2, budget 1 | PR #26 `2f34fac`; PASS; 1.0054736 USD | — | `completed/t29-backtest-report-dir_03-10-26/` |
| T30 | PERF-web re-measure (test, tsc, island build, chunk gzip) | L | archived | PERF | PERF accepted | `session_01L5cLjw2rekuXBVPzWhiaof` | `claude/t30-perf-web-remeasure` | measure only | RT0, budget 0 | PR #28 `2eb6e25`; PASS; 0.9862586 USD | — | `completed/t30-perf-web-remeasure_03-10-26/` |
| T31 | chain-growth rescue onto main | L | archived | T23 | — | `session_01CRoKgnU2U1UcMyqAAKTHjy` | `claude/t31-chain-growth-rescue` | 2 api path files, `onchain-activity/**` | RT2, budget 1 | PR #30 `34e3bb3`; PASS; 0.5641288 USD | — | `completed/t31-chain-growth-rescue_03-10-26/` |
| T8 | refresh context docs | M | superseded by R2/R3 | — | — | — | — | folded into this program | — | — | — | R2, R3 |
| T9 | charting page | L | cancelled | — | — | — | — | realignment AC-17: charts page not built | — | REALIGN SPEC | — | — |
| T10 | cross-signal confidence view | L | cancelled | — | — | — | — | realignment AC-18: principle retired | — | REALIGN SPEC | — | decisions.md D-2 |
| T17 | `.agents/skills` duplicate | L | cancelled | — | — | — | — | H1 symlink | — | — | user 03-10-26: leave as is | backlog `agents-skills-symlink-windows_NOTE_02-10-26.md` |
| T24 | one status board | M | superseded by R2/R6 | — | — | — | — | MASTER-PLAN is the one board; exciting-meitner board dropped in R13 | — | decisions.md D-5 | — | this file |
| T25 | delete stale branches | L | accepted | — | T23 | user | — | seven deleted by the user 03-10-26 | — | `git ls-remote --heads origin` | planner cannot delete | Approvals Log |
