# T76 (P5 S-E2b) report

## 1 Task ID
T76, branch claude/t76-p5-s-e2b-screens, base origin/main 087ca81.

## 2 Outcome
done. Contrast blocker cleared; seeded states captured at 375/768/1280 (24 PNGs, 388,886 B total, max each <= 150 KB); visual defects fixed; all gates green.

## 3 Summary
- Contrast: line 124 ready selector now `[data-testid="attention-chart"]`; added one case (narrative with a basket, rows, coin expand). No assertion touched.
- Seeded fixture: baskets created via real API, attention numbers via routed fixture JSON (shape web/lib/types/attention.ts). One test per width walks ok, coin expand, partial, ranking-off, loading, error, empty and asserts scrollWidth <= clientWidth; removal notice has its own per-width test.
- Defects found by viewing all 24 images (before fix), then fixed in the T74 css block / BasketTable:
  1. Legend: a stray 1px vertical divider between toggles (button right border) and uneven padding. Fixed (border/padding 0).
  2. Empty state showed two lines ("No baskets yet" and "No baskets to rank"). Second now hidden by css class.
  3. Coin sources: name, value and state not aligned. Now a 3-column grid, value right-aligned tabular.
  4. Dead selector for the 7d/30d/90d divider (`.basket-seg__btn + .basket-seg .basket-seg__btn` never matched). Fixed.
  5. First partial/ranking-off shots at 375/768 were taken before the chart painted. Spec now waits for the canvas.
- Known limits:
  - The screener removal notice ("Basket Majors no longer counts it") is rendered only in a `visually-hidden` aria-live paragraph (ScreenerBoard.tsx ~416), so sighted users never see it. Forbidden file; needs a follow-up. removal-notice PNGs therefore show the board, not a visible notice.
  - At 375 on short pages the shell top nav stretches in full-page captures (shell css, not T74). Not fixed.
  - The chart panel and legend stay on the light surface by documented design (contrast comment in globals.css); not changed.
  - RedistributionBadge.tsx still holds colour/font-size literals; it is used by onchain, not the narrative tab; untouched.
  - Screenshots use fixture numbers, not provider data.

## 4 Files changed
web/e2e/contrast.spec.ts (line 124 + 1 case); web/e2e/narrative.spec.ts; web/app/globals.css (T74 block); web/components/narrative/BasketTable.tsx (one class); screens_17-10-26/ (24 PNG + index.md); this report.

## 5 Commits
44e7762 test (red-first). ee36296 style/polish + screens + report.

## 6 Tests run
Baselines on untouched origin/main 087ca81: vitest 58 files, 472 passed, 0 skipped; e2e 83 passed, 1 failed (contrast narrative, the blocker).
- Red run (old selector, new cases) e2e narrative+contrast: 9 passed, 1 failed. Red count 1 (the stale selector); the new seeded and rows cases were green on first run, so they are regression guards rather than red-to-green. 2026-10-17 ~07:35Z, SHA 44e7762.
- Final, SHA ee36296 (+report), ~07:47Z: `pnpm test` 58 files 472 passed 0 skipped; `tsc --noEmit` clean; `pnpm build:islands` ok; `pnpm test:e2e` (PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium, SCREENER_REFRESH_WORKER=0) 84 passed 0 failed incl. contrast; `git diff origin/main -- api` empty; `git diff --check` clean; PNG sizes checked.
- Spend: well under the 15 USD cap.

## 7 Tests NOT run
No Firefox/WebKit; no live provider data (by rule); no visual diff tooling.

## 8 Deviations
Red-first yielded one red, not several (see 6). Screenshots compressed by 96-colour quantisation. Removal-notice captured as viewport, not full page.

## 9 Blockers
None for this task. Follow-up needed outside scope: visible removal notice.

## 10 Follow-up
Make the screener removal notice visible (ScreenerBoard.tsx / CoinActions). Shell nav height at 375 in full-page captures. Optional: delete or tokenise RedistributionBadge literals.

## 11 Context cost
Read within caps except extra reads: ScreenerBoard.tsx (grep and 9 lines), globals.css legend lines ~80 lines beyond the T74 block, narrative.spec.ts full tail. Planner may judge these overage; no other docs opened.
