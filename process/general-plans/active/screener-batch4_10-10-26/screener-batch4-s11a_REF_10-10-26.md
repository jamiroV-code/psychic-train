ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions; load only the files listed below; this overrides any orchestrator wording in CLAUDE.md. Capped lane (RT3): at most 3 sonnet subagents, one level, each listed in report heading 11; ask the planner if spend passes 5 USD.

Task: T42 (batch 4, slice S11a) - Brussels time everywhere on /screener (axis ticks, last-bar captions, chip tooltips, span lines), status server_time; no polling (that is S11b).
Acceptance: gates G-S11a-1..13 pass. Required: seeded e2e G-S11a-11 and G-S11a-12 (CI does not run Playwright); NOT-RUN stops at needs_input. Never merge with an open needs_input or blocker; a count that differs from the plan arithmetic stops you. P-S11-1 (real PC labels) stays the user's probe: status review, not claimed.
Owned / Forbidden / Design / Tests: the plan's S11a section. Clarifications: the 14-day tick step is anchored to Mondays since 1970-01-05; use a module-level Intl formatter; derive CET/CEST from the computed offset (en-US prints GMT+2).
Base: main (api/ and web/ as at 1e7d337, S1-S7 and S5a merged). Baselines pytest 996/2/5/0, vitest 251/34 files, e2e 65 (screener+contrast 17). Expected end: pytest 999; G-S11a-3 73 in 10 files (red run 37 failed, 36 passed).
Branch: claude/t42-s11a-brussels-time (from main)
Read (re-derive with `grep -n '^## \|^### '`): process/general-plans/active/screener-batch4_10-10-26/screener-batch4_PLAN_10-10-26.md lines 41-45, 49-51, 53-61, 81, 83-84, 86-90, 92, 94-105, 107-112, 257-271, 293-295, 297-298, 300-301, 303-304, 306-307, 309-310, 326, 330.
Tests: red run first on stubs; UV_FROZEN=1 on every pytest; each gate once after the last edit; e2e with SCREENER_REFRESH_WORKER=0 and PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome, run from web/ (pnpm install --frozen-lockfile first).
Budget: 110 tool calls, 90 min, 4 CI polls, 3.0-3.8 USD. Retry: 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch4_10-10-26/screener-batch4-s11a_REPORT_10-10-26.md, headings: 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (gate, SHA, UTC), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
Stop at review if: scope expansion, doubt, a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, api/scripts/, or a file outside Owned.
Autonomy: edit Owned, run gates, push, open PR, wait for CI. No deploy, no secrets.
