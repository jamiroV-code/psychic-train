---
name: report:r12-deploy-fixes-w4
description: "R12 W4 report: PC acceptance record, review-decision.json and verification.json from the user-reported PC results."
date: 10-10-26
feature: general-plans
---

# R12 W4 report

## 1 Task ID
R12 (r12-deploy-fixes), session W4, docs only.

## 2 Outcome
DONE. The PC record is filled, `harness/review-decision.json` is written (approved-with-concerns), `harness/verification.json` is updated, and the evidence pack validator passes with exit 0. Stopped at review; nothing merged.

## 3 Summary
- PR #45 was already merged into `main` and its remote branch `claude/r12-deploy-fixes` was deleted, so the envelope's "push to the existing branch, do not open a new PR" could not be followed as written. Per the session git rules, the local branch was reset to the latest `origin/main` (same name) and the W4 commits sit on it as a fresh change. Details under heading 8.
- Post-merge tree check: `git rev-parse origin/main:deploy` = 65b61e510d3bc2c1d3278832ba8087fe7dbb6726, equal to the tested tree. This is a repository check by the worker, not a PC result.
- Every PC row is labelled user-reported. PC-12 and PC-15 are earlier user-reported results (W2 heading 12). PC-13 has no separate run (covered by PC-8). PC-10 was observed inside PC-11 and PC-16.
- Known gaps stay known gaps: smoke check non-200 and build-id mismatch branches, exit 6 only for the process-died branch, the possible exit 5 before exit 6, invalid WebPort under `-ReportOnly`. The unbounded `WaitForExit` (`start-web.ps1` line 61) is recorded as user-accepted.
- `verification.json`: `manualChecks` now has one entry per PC step (PC-1 to PC-16) with the user-reported result; `result` is `ACCEPTED_WITH_KNOWN_GAPS` (the validator does not constrain the value; a `resultNote` explains it). `legacyUserReportedChecks` is kept unchanged.

## 4 Files changed
All under `process/general-plans/active/r12-deploy-fixes_03-10-26/`:
- `r12-deploy-fixes-pc-record_REPORT_10-10-26.md` (new; the template is untouched)
- `harness/review-decision.json` (new)
- `harness/verification.json` (manualChecks, result, resultNote)
- `r12-deploy-fixes-w4_REPORT_10-10-26.md` (this report)

No change to `deploy/`, `api/` or `web/`.

## 5 Commits
See the branch log: one docs commit with the record and the evidence pack, one with this report if the report needed a later edit. Scans ran on the committed diff `git diff origin/main...HEAD`.

## 6 Tests run
- `node .claude/skills/vc-risk-evidence-pack/scripts/validate-risk-artifacts.mjs <task folder>/harness`: exit 0, no warnings, no failures.
- On the committed diff: `git diff --check`, ASCII scan, NET scan (no `http://` plus 100.x), secret scan, FORBIDDEN scan: results under heading 8 where not clean.
- `git rev-parse origin/main:deploy` compared with the tested tree: equal.

## 7 Tests NOT run
- The pytest deploy suite, pnpm and e2e: not in scope (docs only, no code changed).
- Nothing on the PC: no PowerShell in the sandbox. All PC results are user-reported.

## 8 Deviations
- Branch and PR: PR #45 is merged and the remote branch is gone. I recreated `claude/r12-deploy-fixes` from `origin/main` (same name, as the session rules require for follow-up work after a merge). A new PR is required by the session rules; the envelope said not to open one on the assumption that #45 was still open. The branch holds only the W4 docs commits.
- R12-scope scan: the plan's R12-scope regex allowlists only `w[123]_(REPORT|REF)`, `pc-(runbook|record-template)_REF` and the four harness JSON files. It therefore rejects the new files `r12-deploy-fixes-pc-record_REPORT_10-10-26.md`, `r12-deploy-fixes-w4_REPORT_10-10-26.md` and `harness/review-decision.json`, as expected. The plan was not edited. All three files are inside the task folder; the allowlist needs those names added if the scan is a merge gate.
- `verification.json` `result` is `ACCEPTED_WITH_KNOWN_GAPS`, which the validator accepts because it does not check the field.

## 9 Blockers
None.

## 10 Follow-up
- Planner: update the registry to `review`, and add the three new file names to the R12-scope allowlist if that scan is a gate.
- User: after the new PR merges, `git switch main` on the PC and re-check `git rev-parse HEAD:deploy` (expected 65b61e510d3bc2c1d3278832ba8087fe7dbb6726).
- Open known gaps for a later task: bounded `WaitForExit`, and a way to exercise the HTTP non-200 and build-id mismatch smoke branches.

## 11 Context cost
About 16 tool calls, well under the 40-call budget. Read: CLAUDE.md, the template, the harness JSON files, the validator, W2 heading 12, the W3 report lines and the plan's scan block. Beyond the envelope, no other protocol docs were opened.
