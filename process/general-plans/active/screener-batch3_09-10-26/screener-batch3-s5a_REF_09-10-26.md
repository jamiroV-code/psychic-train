ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md. Capped lane (RT3): at most 3 sonnet subagents, 15 USD, one level, listed in report heading 11.

Task: T40 (batch 3, slice S5a) - layout file API, 30-coin cap, symbol validation, RSI numbers, TS mirrors.
Acceptance: G-S5a-1..12 pass; P-S5a-1 stays a user probe (review). Seeded e2e (G-S5a-12) is required: NOT-RUN stops at needs_input. No merge with an open needs_input or blocker; a count that differs from the plan arithmetic stops you.
Owned / Forbidden / Design / Tests: the plan's S5a section. Clarification: DELETE /api/layout/crypto on an unreadable layout.json moves it to .bad (os.replace) and returns the default; assert it inside existing test_layout test 7 or 12 (no count change).
Base: main (source 270f9ac). Baselines pytest 951/2/5/0, vitest 251/34 files; expected end pytest 996.
Branch: claude/t40-s5a-layout-api (from main)
Read (re-derive with `grep -n '^## \|^### '`): process/general-plans/active/screener-batch3_09-10-26/screener-batch3_PLAN_09-10-26.md lines 50-54, 59-68, 88, 90-91, 93-100, 102, 104-110, 112-116, 267, 269-282, 304-326, 336-337, 339, 341, 343.
Tests: red run G-S5a-1 first (45 failed); UV_FROZEN=1 on every pytest; each gate once after the last edit; e2e with SCREENER_REFRESH_WORKER=0, PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome.
Budget: 130 tool calls, 100 min, 4 CI polls, 4-5.5 USD. Retry: 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch3_09-10-26/screener-batch3-s5a_REPORT_09-10-26.md, headings: 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (gate, SHA, UTC), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
Stop at review if: scope expansion, doubt, a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, api/scripts/, or a file outside Owned.
Autonomy: edit Owned, run gates, push, open PR, wait for CI. No deploy, no secrets.
