---
name: report:t19-archive-stale-plans
description: "Worker report T19: momentum-screener_17-09-26 archived to completed/ with three backlog notes"
date: 03-10-26
feature: general
---

## 1 Task ID
T19

## 2 Outcome
done (pending CI green on head and self-merge; see heading 9)

## 3 Summary
- Re-checked the SPEC candidate table at start: evidence unchanged. The only `active/` commits since `5676ceb` are the T18/T19/PERF registry commits. The nine folders keep their verdicts; momentum-screener is the only move.
- Open items inside momentum-screener were exactly the three on the note list. The two RESOLVED stubs got no note.
- Wrote three backlog notes, then one `git mv` of the whole folder (27 files, name unchanged).
- validate-plan-inventory: 0 failures, same six warning kinds as before (only counts dropped). validate-context-discovery: only the baseline failure. `git diff --check` clean.
- 18 files outside the owned set still name the old path; listed in heading 9, none edited.

## 4 Files changed
- Moved (27 files): `process/general-plans/active/momentum-screener_17-09-26/**` to `process/general-plans/completed/momentum-screener_17-09-26/**`
- New: `process/general-plans/backlog/{dead-data-notice-unification,momentum-screener-rfc004-closeout,adapter-shared-contract-test}_NOTE_03-10-26.md`
- New: this report

## 5 Commits
Branch `claude/t19-archive-stale-plans` from main `56fb966`.
- `a68fec2` archive folder plus three notes
- report commit: head of the branch (the Master Planner records the merge SHA)

## 6 Tests run
- 2026-10-03T14:57:44Z, baseline at `56fb966`: `node .claude/skills/vc-audit-plans/scripts/validate-plan-inventory.mjs` gave 0 failures, 6 warnings (active count 107, completed 56). Source count `git ls-files` = 27.
- 2026-10-03T14:57:44Z, baseline at `56fb966`: `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` failed with only `.agents/skills does not resolve to .claude/skills`.
- After the move (staged, same tree as `a68fec2`): `ls process/general-plans/active/momentum-screener_17-09-26` gave "No such file or directory". `git ls-files process/general-plans/completed/momentum-screener_17-09-26 | wc -l` = 27. Source 27, destination 27.
- After the move: validate-plan-inventory gave 0 failures and the same 6 warning kinds (active 87, completed 76); the counts of affected files dropped. No new warning.
- After the move: validate-context-discovery gave exactly the baseline failure.
- 2026-10-03T14:58:19Z, `a68fec2`: `git diff --check origin/main..HEAD` printed nothing. `git diff --name-only origin/main..HEAD` names only the 27 moved paths plus the 3 notes.
- Gate 8 grep run on `a68fec2`; output in heading 9.
- Gate 9 (CI on head): see PR; recorded in the final reply.

## 7 Tests NOT run
pytest, vitest, Playwright: RT0 docs-only move, full-suite budget 0.

## 8 Deviations
None. Gate 8 hits include the three new notes (they name the new `completed/` path and the old name as a substring); they are owned files and need no action.

## 9 Blockers
Risks: `api/scripts/backtest_leg_boundaries.py:68` has `REPORT_DIR` pointing at `.../active/momentum-screener_17-09-26`. The next run of that script writes into a recreated `active/` folder. It is an `api/**` file, which is forbidden to me, so I did not edit it.

Fix cycles used: 0 of 2.

Registry-update request: set T19 to accepted, then archived with the merge SHA.

Referrers to the old location (gate 8, `git grep -c`, none edited; the planner decides which to update):
- `api/scripts/backtest_leg_boundaries.py` (1 matches)
- `process/MASTER-PLAN.md` (1 matches)
- `process/archive/master-plan-revisions_02-10-26.md` (1 matches)
- `process/context/context-changelog.md` (7 matches)
- `process/context/tests/all-tests.md` (2 matches)
- `process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md` (1 matches)
- `process/general-plans/active/personal-tracker-realignment_02-10-26/personal-tracker-realignment_SPEC_02-10-26.md` (1 matches)
- `process/general-plans/backlog/adapter-shared-contract-test_NOTE_03-10-26.md` (1 matches)
- `process/general-plans/backlog/board-endpoint-cold-start-latency_20-09-26.md` (1 matches)
- `process/general-plans/backlog/dead-data-notice-unification_NOTE_03-10-26.md` (1 matches)
- `process/general-plans/backlog/momentum-screener-rfc004-closeout_NOTE_03-10-26.md` (1 matches)
- `process/general-plans/backlog/sandbox-note-reconciliation_19-09-26.md` (1 matches)
- `process/general-plans/backlog/weekly-ohlc-golden-values_19-09-26.md` (2 matches)
- `process/general-plans/completed/vitest-config-e2e-exclude_19-09-26.md` (1 matches)
- `process/general-plans/reports/momentum-screener_17-09-26-RFC-001-phase-report.md` (8 matches)
- `process/general-plans/reports/momentum-screener_17-09-26-RFC-002-phase-report.md` (8 matches)
- `process/general-plans/reports/momentum-screener_17-09-26-RFC-003-phase-report.md` (9 matches)
- `process/general-plans/reports/momentum-screener_17-09-26-RFC-004-phase-report.md` (7 matches)

Of these, `process/general-plans/reports/momentum-screener_17-09-26-RFC-00{1,2,3,4}-phase-report.md` match mainly on their own file names and also carry `stub_path` and `backlog_note_path` links to the old folder. `process/archive/master-plan-revisions_02-10-26.md` is a historical record.

## 10 Follow-up
- Planner: update the 18 referrers above where wanted.
- Planner: fix `api/scripts/backtest_leg_boundaries.py:68`.
- Planner: registry T19 accepted, then archived with the merge SHA.
- Three new backlog notes exist for the user to prioritise.

## 11 Context cost
Files loaded: CLAUDE.md, the T19 SPEC, the momentum-screener PLAN (grep only, about 25 lines read), three stub headers, the DRAFT plan header, one backlog note as format example. About 45k tokens.
Tools present in my tool list: merge: `mcp__github__merge_pull_request`; PR-create: `mcp__github__create_pull_request`; session tools: `mcp__claude-code-remote__create_session`, `archive_session`, `send_message` and others (none used). The line that told me I am a WORKER: the first line of the task envelope, `ROLE: WORKER`.
