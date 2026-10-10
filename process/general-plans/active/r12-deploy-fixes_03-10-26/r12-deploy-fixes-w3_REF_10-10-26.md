ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn anything; load only the files listed below; this overrides any orchestrator wording in CLAUDE.md.

Task: R12 session W3 (docs only): C4 = PC runbook, acceptance-record template, evidence pack under harness/, then open the PR.
Acceptance: runbook, record template, evidence pack written, PR open, stopped at review.
Base: the EXISTING branch claude/r12-deploy-fixes at its pushed head (W1, W2 done). Push it; open the PR to main; NEVER merge.
Read (re-derive with `grep -n '^## \|^### '`): process/general-plans/active/r12-deploy-fixes_03-10-26/r12-deploy-fixes_PLAN_09-10-26.md lines 44, 47-50, 77-79, 103, 149-174, 232-234, 269-270, 279-281, 283, 288-309; and W2 report heading 12 plus W1 report heading 12 (user-reported PC results, read these two only).
Facts to use: the user already ran many PC steps with W1/W2. Record them in the template as "observed, user-reported, partial paste" rows (what was and was not pasted), never as your own PASS. Still open: exit code 6 value, HTTP non-200 and build-id mismatch branches, parser at the final head. Runbook: ASCII only, numbered, each step command / expected / what to paste back / abort advice; only steps still needed plus a short "already observed" table.
Files (task folder): r12-deploy-fixes-pc-runbook_REF_10-10-26.md, r12-deploy-fixes-pc-record_REPORT_10-10-26.md (template), harness/ (4 of 5 artifacts; review-decision.json is the planner's), r12-deploy-fixes-w3_REPORT_10-10-26.md with 11 headings: Task ID, Outcome, Summary, Files changed, Commits, Tests run, Tests NOT run, Deviations, Blockers, Follow-up, Context cost.
Tests: scans G-R12-9..11 AFTER each commit; validate-risk-artifacts.mjs: exactly one expected failure (review-decision.json). Budget 60 tool calls, 1-2 USD.
Stop at review if: a deploy/ or api/ edit seems needed, a count differs, or any blocker is open. Never claim a script works.
