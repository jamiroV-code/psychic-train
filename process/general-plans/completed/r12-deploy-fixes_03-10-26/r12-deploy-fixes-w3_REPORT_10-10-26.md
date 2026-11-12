# R12 W3 report (10-10-26)

## 1 Task ID
R12 session W3 (docs only): commit C4 = PC runbook, acceptance-record template, evidence pack (4 of 5 artifacts). Branch `claude/r12-deploy-fixes`, continued from the W2 head `6d8e3b2`. Worker, direct lane, no subagents.

## 2 Outcome
DONE for the docs scope: runbook, record template and 4 harness artifacts written, gates clean, PR opened to `main`, not merged. Overall R12 result stays CONDITIONAL: no PowerShell here, nothing below proves a script works. Stopped at review.

## 3 Summary
- Runbook `r12-deploy-fixes-pc-runbook_REF_10-10-26.md`: ASCII, numbered steps (PC-1..PC-5, PC-7, PC-8, PC-9, PC-11, PC-14, PC-16), each with command, expected, paste back and abort advice; an Abort and restore block above PC-1; an "Already observed" table (user-reported, partial paste) for the W1/W2 checks; a known-gap note. Log strings quoted from `_common.ps1` and `start-web.ps1` at the branch head.
- Record template `r12-deploy-fixes-pc-record-template_REF_10-10-26.md`: header fields, PC-1..PC-16 table with result options including "observed, user-reported, partial paste", verdict, post-merge tree check, mapping.
- Evidence pack in `harness/`: `risk-gate.json`, `context-snippets.json` (final line numbers on the head, 17 test names), `adversarial-validation.json` (12 scenarios), `verification.json` (`commands` kept; `manualChecks` now PC-1..PC-16 `pending-user`; the earlier user-reported entries moved unchanged to `legacyUserReportedChecks`; `result` CONDITIONAL). `review-decision.json` is the planner's.
- Still open on the PC: the exit code 6 value (runbook PC-14 uses `powershell -File` and prints `exit=`), a non-node decoy stop (PC-7, PC-8, PC-11), pasted dry-run and marker output (PC-5, PC-9), the parser at the final head (PC-4). Not testable on the PC without code edits: smoke check "HTTP <code>" and "build id mismatch" branches (known gap).

## 4 Files changed
All under `process/general-plans/active/r12-deploy-fixes_03-10-26/`: `r12-deploy-fixes-pc-runbook_REF_10-10-26.md`, `r12-deploy-fixes-pc-record-template_REF_10-10-26.md`, `harness/{risk-gate,context-snippets,adversarial-validation,verification}.json`, this report. No `deploy/`, `api/`, `web/` change; `git rev-parse HEAD:deploy` is `65b61e510d3bc2c1d3278832ba8087fe7dbb6726` before and after.

## 5 Commits
- `31d7388` process: R12 C4 PC runbook, record template, evidence pack
- docs commit for this report (SHA in the PR)
Earlier (W1, W2): through `6d8e3b2`.

## 6 Tests run (gate, SHA, UTC)
| Gate | SHA | Result |
|---|---|---|
| G-R12-9 (R12-scope, FORBIDDEN, FIXTURES) | 31d7388 | printed nothing |
| G-R12-10 (S-secret, PS-secret, NET) | 31d7388 | printed nothing |
| G-R12-11 (ASCII-scan, `git diff --check origin/main...HEAD`) | 31d7388 | nothing, exit 0 |
| G-R12-13 `validate-risk-artifacts.mjs` | 31d7388 | exit 1, exactly one failure: `review-decision.json missing or invalid JSON object` (expected) |
G-R12-9..11 rescanned after the docs commit: see the PR description.

## 7 Tests NOT run
- Any PowerShell parse or run (`pwsh` absent). Every PC step in the runbook is untested by the worker.
- `pytest api/tests/deploy`: not run (no code change in W3).

## 8 Deviations
- The template is named `r12-deploy-fixes-pc-record-template_REF_10-10-26.md` (the plan's name, inside the G-R12-9 allowlist), not `..._pc-record_REPORT_...`: a `_REPORT_` record file would print under R12-scope. `r12-deploy-fixes-pc-record_REPORT_10-10-26.md` stays the planner's filled copy.
- `verification.json` `manualChecks` replaced by the 16 `pending-user` items as the plan requires; the 13 earlier user-reported entries are kept verbatim under a new key `legacyUserReportedChecks`.
- Runbook steps PC-6, PC-10, PC-12, PC-13, PC-15 are not separate steps: PC-10/12/15 were observed (table), PC-13 is covered by the PC-8 build, PC-6 (missing-marker refusal) is listed as not observed. PC-10's two `Invoke-WebRequest` lines sit at the end of PC-11.
- Skill text and validator disagree on the pack (`validate-evidence-pack.mjs` wants `APPROVE|REJECT`); the validator `validate-risk-artifacts.mjs` was followed, no validator edited.
- Strings checked against the plan: all quoted log strings match the shipped code; the DRY RUN stale line and `Port 3000: free.` appear as in the code.

## 9 Blockers
None open. Request to the planner: registry update to `review`; the open item is the PC record (user results of the runbook, written as `r12-deploy-fixes-pc-record_REPORT_10-10-26.md`) and `harness/review-decision.json`.

## 10 Follow-up
- Planner: write `review-decision.json` after the user's record; confirm the head SHA to the user for PC-3.
- Known gap to keep in the record: smoke check HTTP non-200 and build-id mismatch branches.
- PowerShell 5.1 behaviour of the new code is user-reported only for the lines listed in the runbook table.

## 11 Context cost
About 22 tool calls, one worker session, no subagents; well under the 60-call and 1-2 USD budget. Files opened beyond the envelope: the two scripts and README sections (to quote strings), the validator head, the W2 report headings 1-12.
