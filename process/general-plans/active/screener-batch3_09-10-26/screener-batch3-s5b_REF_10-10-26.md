ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions; load only the files below. Capped lane: at most 3 sonnet subagents, one level, listed in the report. Ask the planner above 7 USD.

Task: T41 (batch 3, slice S5b) - layout UI: groups, add/remove coins, rename, move, reorder, 30-coin cap, over the S5a layout API.
Acceptance: G-S5b-1..11 pass; seeded e2e G-S5b-9/10 required. If a count differs from the plan or you hit a blocker: set needs_input, STOP, do NOT merge, do NOT open a new PR, wait for the planner. P-S5b-1 is the user's probe.
Owned: the plan's S5b-scope list. Forbidden/Design/Tests: the plan's S5b section. ASCII only. Keep S11 live refresh and T44 shared zoom working. Names of buttons include the coin or group. No timer unless an add retry is pending. RsiChart must not mount for empty rsi.
Code reads: api/routers/layout.py, api/data/layout.py, api/routers/watchlist.py, web/lib/types/{layout,screener}.ts.
Base: main fc12f27 or later. Baselines: pytest 1016/2/5/0, vitest 335/43 files, e2e 72/8. Expected end: pytest 1016, vitest 400/50, e2e 79/9.
Branch: claude/t41-s5b-layout-ui (from main)
Read (re-derive with `grep -n '^## \|^### '`): process/general-plans/active/screener-batch3_09-10-26/screener-batch3_PLAN_09-10-26.md lines 60, 62, 64-65, 68, 132, 134-141, 143-148, 150-158, 160-169, 293, 297-307, 312-314, 319-320, 335-336, 338-339, 341-342, 344-347.
Tests: red run first; each gate once after the last edit; e2e from web/ with SCREENER_REFRESH_WORKER=0, PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome.
Budget 5.5-8 USD. 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch3_09-10-26/screener-batch3-s5b_REPORT_10-10-26.md, headings: Task ID, Outcome, Summary, Files, Commits, Tests run (SHA, UTC), Tests NOT run, Deviations, Blockers, Follow-up, Context cost.
Stop at review if: scope expansion, doubt, or a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, api/, web/islands/ or outside Owned.
Autonomy: edit Owned, gates, push, draft PR, CI. Never merge.
