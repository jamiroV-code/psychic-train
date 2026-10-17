# T78 (P5 S-F2) report

## 1 Task ID
T78, branch claude/t78-p5-s-f2-discovery-tab (created from origin/main; the old branch did not exist on origin).

## 2 Outcome
done (draft PR, not merged). Gate: screenshots need planner/owner check.

## 3 Summary
- Discovery tab replaces the placeholder: 7d/30d/90d selector, ranked table (Category, Score, Median, Coins used), coins expand, no legend, no badges.
- States with test ids: ok, no-data x3 (categories-missing, reference-missing, no-attention-data), loading, error with retry.
- Screener: added a visible role=status .board-notice line (data-testid board-announcement-visible); aria-live board-announcer kept. It shows every board announcement, not only removals.
- e2e removal-notice case now uses the new test id.
- Known limits: all announcements are visible, not just removals; the line has no reserved height, so it can shift the board slightly (same as layout-notice); coin rows show change and "n of N sources rising" only.

## 4 Files changed
web/components/narrative/{DiscoveryTab,DiscoveryTable,NarrativeTabs}.tsx, web/lib/{api,types}/discovery.ts, web/components/narrative/__tests__/{DiscoveryTab,ScreenerNotice,NarrativeTabs}.test.tsx, web/components/screener/ScreenerBoard.tsx (+3 lines), web/app/globals.css (+22, T74 block), web/e2e/narrative.spec.ts, screens_17-10-26 (21 PNG + index rows), this report.

## 5 Commits
Red tests commit, then implementation commit (a7def88), then screens and report.

## 6 Tests run
- vitest baseline on origin/main: 472 passed. After: 481 passed (60 files). Red count: 10 vitest cases (8 Discovery, 1 notice, 1 tab wiring). e2e cases were committed in the red commit but not run red.
- tsc --noEmit: clean.
- playwright full (narrative spec, contrast.spec.ts unedited): 86 passed (baseline 84 expected; -1 placeholder, +3 Discovery). Spend: about 0 USD provider; no cost tracking available.
- api pytest not run; git diff origin/main -- api is empty.

## 7 Tests NOT run
Lint (no lint script in web/package.json; `next lint` only prompted for config, nothing changed). api pytest. Baseline e2e on untouched main not measured separately.

## 8 Deviations
Read cap exceeded: extra reads of ScreenerBoardLayout.test.tsx, use-board-layout usage, wider globals.css and narrative.spec.ts ranges, NarrativeTabs.test.tsx. A new test file ScreenerNotice.test.tsx lives in narrative/__tests__. pnpm install --frozen-lockfile used per amendment; lockfile/package.json unchanged.

## 9 Blockers
None.

## 10 Follow-up
Owner to review screenshots at 375/768/1280. Consider limiting the visible line to removals and reserving its height.

## 11 Context cost
Over the 36,000 B cap (see 8); exact total not measured.
