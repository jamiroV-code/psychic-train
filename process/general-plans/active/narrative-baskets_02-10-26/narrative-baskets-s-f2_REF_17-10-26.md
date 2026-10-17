ROLE: WORKER
Direct lane: no spawning; read only below.

Task: T78 (P5 S-F2) - Discovery tab, plus visible screener removal notice. RT3. Base origin/main. Branch: claude/t78-p5-s-f2-discovery-tab
Acceptance: process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets_PLAN_16-10-26.md lines 23-32 (Common rules), 87-89 (UI standard), 108-110 (S-F2). ACs: AC-40, AC-42. Payload: narrative-baskets-s-f1_REPORT_17-10-26.md lines 7-19 (GET /api/narrative/discovery?window=7|30|90, DiscoveryResponse).
Owned: web/components/narrative/Discovery*.tsx (+ tests in web/components/narrative/__tests__), web/lib/api/discovery.ts, web/lib/types/discovery.ts (create if absent), tab wiring in NarrativeTabs.tsx (own tab after the baskets tab, replacing the one-line placeholder), Discovery cases in web/e2e/narrative.spec.ts, narrow css in the T74 block of web/app/globals.css, screens under process/general-plans/active/narrative-baskets_02-10-26/screens_17-10-26/ (+ index.md rows).
Also owned: web/components/screener/ScreenerBoard.tsx lines 398-420 only: make the basket-removal notice visible to sighted users (today it sits only in a visually-hidden aria-live paragraph, data-testid board-announcer, ~line 416). Keep the aria-live element and its test id; add a visible role=status line using the existing .board-notice style. See narrative-baskets-s-e2b_REPORT_17-10-26.md lines 18-19 (known limit).
Forbidden: api/**, CLAUDE.md, AGENTS.md, .claude/, .github/, process/ (except screens and the report), process/MASTER-PLAN.md, decisions.md, any .env/key file, web/e2e/contrast.spec.ts.
Read (hard cap 36,000 B for EVERYTHING; est. 35,400), stop at each cap, over = needs_input:
 1. CLAUDE.md 13,443 B
 2. plan 3,563 + F1 payload 1,500 + e2b limits 800
 3. code 12,600: web/components/narrative/NarrativeTabs.tsx (2,733); BasketTable.tsx (2,553, as the table pattern); web/lib/api/attention.ts (1,001); web/e2e/narrative.spec.ts lines 1-90 and 109-130 (3,000 cap); web/app/globals.css tokens + T74 block (2,000 cap); ScreenerBoard.tsx 398-420 (800 cap)
Unread: SPEC, all-context, other components.
UI (AC-42): clean, uncluttered; header with 7d/30d/90d selector, ranked category table (name, score, median, coins used), coins expand; one plain label per number; no badges; one legend at most; data-testids on every state. No colour or font-size literal in new tsx/css (tokens only).
States, each shown: ok; no-data with each reason (categories-missing, reference-missing, no-attention-data), each with one plain line; loading; error (with retry). Screenshots at 375, 768, 1280 under screens_17-10-26/ for ok, every no-data reason, loading, error (route-mocked in Playwright); also one of the visible removal notice. scrollWidth <= clientWidth at all three widths.
Red-first: write vitest cases (one legend, no badge class, every state renders, window switch refetches, notice visible and aria-live kept) and e2e cases; commit failing; record red count.
Baselines: measure on untouched origin/main, no hard-coding: expect api 1402 passed/1 skipped/5 deselected, vitest 472, e2e 84.
Gates (commands per process/context/tests/all-tests.md): api pytest unchanged (git diff origin/main -- api empty); vitest, tsc, lint; Playwright e2e incl. contrast.spec.ts unedited and green; protected AC-25 tests green and unedited; git diff --check origin/main...HEAD; diff empty for forbidden files.
Must NOT: secrets, live network or provider calls; edit outside Owned; merge.
Cap 15 USD; ask at 7 (needs_input). needs_input means STOP. One draft PR against main; never merge; after the report stop, do not wait on CI. ASCII.
Report: process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-s-f2_REPORT_17-10-26.md
Headings (11): 1 Task ID, 2 Outcome, 3 Summary (with a "Known limits" bullet), 4 Files changed, 5 Commits, 6 Tests run (cmd, result, UTC, SHA, red count, spend), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
