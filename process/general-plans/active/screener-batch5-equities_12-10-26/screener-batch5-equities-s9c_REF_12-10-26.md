ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions; load only the files below. Capped lane: at most 3 sonnet subagents, one level, listed in the report. Spend cap 15 USD; ask the planner above 7 USD.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.

Task: T47 (batch 5, slice S9C) - /equities page by parameterised reuse (ScreenerVariant context + client factories); crypto page unchanged.
Acceptance: G-S9C-1..5 pass; AC-S9C-1..6; seeded e2e on the HEAD SHA is REQUIRED before you report PASS (NOT-RUN stops at needs_input). If a count differs from the plan or you hit a blocker: set needs_input, STOP, do NOT merge. No real LSE call, no key in tests.
Owned/Forbidden/Design/Tests: the plan's S9C section and gate conventions 1-11. No existing web test file may be edited (hidden break: STOP, do not edit the test, report needs_input). Keep T44 shared zoom, S11 live polling and S5b layout behaviour working. ASCII only; no verdict words; no UTC; no web storage.
Base: main 23d7e43 or later (S9A and S9B merged; git fetch, branch from origin/main). Baselines: pytest 1100/2/5 (api untouched), vitest 400 in 50 files, e2e 79 in 9. Expected end: vitest 446 in 55 files.
Branch: claude/t47-s9c-equities-page (from main)
Read: process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities_PLAN_12-10-26.md lines 11, 30-66, 108-122, 242-250, 255-256, 261-269 (re-derive with `grep -n '^## \|^### '`). The plan is on branch claude/pensive-albattani-ou0cgv: `git fetch origin claude/pensive-albattani-ou0cgv`, then read it with `git show origin/claude/pensive-albattani-ou0cgv:<path>`; do not commit anything from that branch.
Tests: red run first; each gate once after the last edit; scan commands only after the commit; e2e from web/ with SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome.
Report: process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities-s9c_REPORT_12-10-26.md, headings: Task ID, Outcome, Summary, Files, Commits, Tests run (SHA, UTC), Tests NOT run, Deviations, Blockers, Follow-up, Context cost.
Stop at review if: scope expansion, doubt, or a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, uv.lock, api/ or outside Owned.
Autonomy: edit Owned, gates, push, draft PR. Never merge.
