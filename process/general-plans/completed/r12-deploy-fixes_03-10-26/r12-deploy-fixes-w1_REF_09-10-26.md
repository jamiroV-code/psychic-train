ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagents, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md.

Task: R12 session W1 (RT4 deploy class): commit C1 (port-scoped stop, README lines 104-105 reword, tests 1-6), then C2 (build marker + stale-build guard, tests 7-11).
Acceptance: C1 and C2 committed on the branch; gates G-R12-1..3 pass at 57 then 62 deploy tests; scans G-R12-9..12 run AFTER each commit (Gate convention 8), note the SHA.
Owned / Forbidden: plan lines 103-104. Design: D2-D5 and D10. Tests 1-11.
Resolved by the user: Q1 B = web-tree based stale rule (refuse on a changed web/ tree or a newer tracked web file; only a note when HEAD alone moved); Q2 A = no marker on first start: refuse, exit 4, until one rebuild.
Branch: claude/r12-deploy-fixes (from main). Push the branch; do NOT open a PR and NEVER merge.
Read (plan, re-derive with `grep -n '^## \|^### '`): process/general-plans/active/r12-deploy-fixes_03-10-26/r12-deploy-fixes_PLAN_09-10-26.md lines 44-47, 52, 71-74, 76-79, 103-104, 106-113, 115-121, 123-137, 222-228, 269-273, 279-282, 288-309, 313. Nothing else. operating-instructions.md: not named.
Commits: C1, C2 each followed by a docs commit (session report + harness/verification.json) before the push. verification.json: {"task":"R12","commands":[{"command":"","result":"","utc":"","sha":""}],"manualChecks":[],"result":"CONDITIONAL"}; W1 fills commands only.
Tests: UV_FROZEN=1 on every pytest; red run of the new test file first; each gate once after the last edit. Test 1: scope its -Force check to Stop-Process lines (New-Item -Force is legitimate).
Retry budget: 2 fix cycles; same failure twice stops. Budget 80 tool calls, 60 min, 1-2 USD.
Report: process/general-plans/active/r12-deploy-fixes_03-10-26/r12-deploy-fixes-w1_REPORT_09-10-26.md, 11 headings: 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (gate, SHA, UTC), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
Stop at review if: any step would kill a process other than the one on the configured port, need a secret, change Task Scheduler registration, be unbounded in time, any count differs from the plan arithmetic, a diff touching CLAUDE.md, AGENTS.md, README.md (root), .claude/ or .github/, or any needs_input/blocker is open.
Autonomy: edit owned files, commit and push the branch. No PowerShell exists here: never claim a script works.
