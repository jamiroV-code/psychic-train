# T73 (P5 S-E1) report

## 1 Task ID
T73, P5 S-E1. Branch claude/t73-p5-s-e1-attention-ui, base origin/main 471f687.

## 2 Outcome
partial: code and tests written; NOT verified (no web deps here), no screenshots. Do not accept yet.

## 3 Summary
New standalone components on injected data (no fetch, dashboard untouched): BasketAttentionChart (header with 7d/30d/90d, one legend that is the basket filter, line per basket, gap split at null, "membership as of <date>", states loading/error/empty+screener link/partial/ranking-off) and BasketTable (five columns, ranked by score nulls last, coins expand with "n of N sources" and raw per source, "no data" never 0). Plus lib/api/attention.ts, lib/types/attention.ts, lib/attention-lines.ts. Colours come from CATEGORICAL in chart-palette; no literals.
- Known limits: (a) I may not edit globals.css/e2e, so styling reuses existing classes (spaghetti-chart, plot-legend) and the table is unstyled beyond defaults; "well organised and clean" is NOT proven and needs a CSS pass (a follow-up task owning css). (b) Selector/table/note use plain elements, no new css. (c) Old verdict views not removed (dashboard is forbidden). (d) Partial = a one-line "no data: names" note.

## 4 Files changed
web/components/narrative/{BasketAttentionChart,BasketTable}.tsx, web/components/narrative/__tests__/BasketAttention.test.tsx, web/lib/{api,types}/attention.ts, web/lib/attention-lines.ts, web/lib/__tests__/attention-lines.test.ts, this report.

## 5 Commits
5ee9f4f tests (red-first); implementation commit follows on the branch.

## 6 Tests run
Only: grep for colour/px/font-size literals in new files (none), old verdict words (none), git diff --check (clean), git diff origin/main -- api (empty). Spend: small, well under cap. Red count: not measured (tests could not run).

## 7 Tests NOT run
Web deps (node_modules) not installed here, so NOT run: pnpm --filter web test (and baseline on origin/main), tsc --noEmit, pnpm build:islands, Playwright at 375/768/1280 (scrollWidth<=clientWidth, contrast.spec.ts). No screenshots exist. Planner/owner must check, at 375, 768 and 1280 px: header+selector, chart, legend, membership line, table five columns, coin expand, and the states loading, error, empty (link to /screener), partial, ranking-off; plus before/after shots. Repo CI re-runs the unit gates. Unverified risks: types of testing-library matchers/imports, `React` namespace in the test, Link import in a vitest env.

## 8 Deviations
No red run recorded; no baseline measured.

## 9 Blockers
No installed web deps; css not owned.

## 10 Follow-up
CSS/layout pass, wire into NarrativeDashboard and remove old views (separate task), screenshots.

## 11 Context cost
Read about 31 KB: CLAUDE.md, the code files listed (plus 2 small greps of island-loader/SpaghettiChart/globals). No other docs opened.
