ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions; load only the files below. Capped lane: at most 3 sonnet subagents, one level, listed in the report. Spend cap 15 USD; ask the planner above 6 USD.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.

Task: T48 (batch 5, slice S9D) - equities end-to-end proof: seeder for synthetic equities, Playwright spec, spaghetti and drill-down vitest.
Acceptance: G-S9D-1..5 pass; AC-S9D-1..5; seeded e2e on the HEAD SHA is REQUIRED before you report PASS (NOT-RUN stops at needs_input). If a count differs from the plan or you hit a blocker: set needs_input, STOP, do NOT merge. No real LSE call, no key; synthetic data only; the seeder must refuse real cache and real equities paths.
Owned/Forbidden/Design/Tests: the plan's S9D section and gate conventions 1-11. Editable existing files: only web/playwright.config.ts and web/e2e/contrast.spec.ts (+1 e2e) as the plan's table says; the crypto seed and the manifest keys other specs read must not change (add a key only). ASCII only; no verdict words; no whole-word UTC; no web storage.
Base: main 4ec0cd0 or later (S9C merged; git fetch, branch from origin/main). Baselines: pytest 1100/2/5, vitest 446 in 55 files, e2e 79 in 9. Expected end: pytest 1105/2/5, vitest 458 in 57 files, e2e 90 in 10.
Branch: claude/t48-s9d-equities-e2e (from main)
Read: process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities_PLAN_12-10-26.md lines 11, 30-66, 123-132, 242-250, 257-258, 261-266, 269 (re-derive with `grep -n '^## \|^### '`). The plan is on branch claude/pensive-albattani-ou0cgv: `git fetch origin claude/pensive-albattani-ou0cgv`, then read it with `git show origin/claude/pensive-albattani-ou0cgv:<path>`; do not commit anything from that branch.
Tests: red run first; each gate once after the last edit; scan commands only after the commit; e2e from web/ with SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome.
Report: process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities-s9d_REPORT_12-10-26.md, headings: Task ID, Outcome, Summary, Files, Commits, Tests run (SHA, UTC), Tests NOT run, Deviations, Blockers, Follow-up, Context cost.
Stop at review if: scope expansion, doubt, or a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, uv.lock, api/pyproject.toml or outside Owned.
Autonomy: edit Owned, gates, push, draft PR. Never merge.
