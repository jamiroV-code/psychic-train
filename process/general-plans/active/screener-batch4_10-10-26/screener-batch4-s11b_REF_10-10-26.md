ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions; load only the files below; this overrides any orchestrator wording in CLAUDE.md. Capped lane: at most 3 sonnet subagents, one level, listed in the report. Ask the planner above 7 USD.

Task: T43 (batch 4, slice S11b) - 60 s quiet page polling, freshness strip, in-place island updates keeping zoom.
Acceptance: G-S11b-1..11 pass; seeded e2e G-S11b-9/10 required. If a count differs from the plan or you hit a blocker: set needs_input, STOP, do NOT merge, wait for the planner. P-S11-3 is the user's probe.
Owned/Forbidden/Design/Tests: the plan's S11b section. Also: poller listens on document.addEventListener("visibilitychange", ...); e2e test 2 awaits the baseline check before runFor(61_000); e2e test 3 uses an answer that really changes (one more BTC bar); Live test 6 counts only the drill-down island mounts.
Base: main (S11a merged). Baselines: pytest 1016/2/5/0 (the plan's 999 is stale), vitest 268/35 files, e2e 68/7. Expected end: pytest 1016, vitest 331/42 files, e2e 72/8.
Branch: claude/t43-s11b-live-updates (from main)
Read (re-derive with `grep -n '^## \|^### '`): process/general-plans/active/screener-batch4_10-10-26/screener-batch4_PLAN_10-10-26.md lines 49-50, 52-61, 123, 125-126, 128-136, 138, 140-148, 276-288, 293-295, 297-298, 300-301, 312-313, 315-316, 318-319, 321-322, 324-326, 330.
Tests: red run first; each gate once after the last edit; e2e from web/ with SCREENER_REFRESH_WORKER=0, PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome.
Budget 4.2-5.7 USD. Retry: 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch4_10-10-26/screener-batch4-s11b_REPORT_10-10-26.md, headings: Task ID, Outcome, Summary, Files, Commits, Tests run (SHA, UTC), Tests NOT run, Deviations, Blockers, Follow-up, Context cost.
Stop at review if: scope expansion, doubt, a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, api/scripts/, or a file outside Owned.
Autonomy: edit Owned, run gates, push, open PR, wait for CI.
