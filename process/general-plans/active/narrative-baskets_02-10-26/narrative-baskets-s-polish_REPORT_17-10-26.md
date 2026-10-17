# T85 (P5 UI polish) report, 17-10-26

## 1 Task ID
T85, branch `claude/t85-p5-ui-polish`, base origin/main `cc33613`.

## 2 Outcome
`needs_input` on item 3 only (F-4, the no-route-mock e2e): it cannot be done without an api change. Everything else (items 1, 2a-2h, 4) is done, tested and screenshotted. Draft PR, not merged.

## 3 Summary
- BEFORE shots from untouched main (42 from the e2e run plus 3 as-shipped from a throwaway spec, since removed) in `screens_17-10-26/before/`; AFTER shots in `screens_17-10-26/`; `index.md` has before/after links and what changed. All 90 files <= 150 KB. I viewed the after shots at all three widths for ok, coin-expand, partial, ranking-off, as-shipped, error, discovery ok/error and fixed what I saw (bold axis text from a white halo stroke, a boxed legend from the shell's `[role=group]` rule, label and value pulled apart at 1280).
- (a) Chart panel, axis text and legend now on `--sh-1` / shell ink. Series use `CATEGORICAL` without indigo (2.06:1 on `--sh-1`; the other seven are >= 3.56:1), in `lib/attention-lines.ts`. `contrast.spec.ts` unedited and green. Comment in the T74 block records the decision; the shared `.analytic-plot` stays light for other charts.
- (b) Chevron on every basket and category row, rotates when open, row hover, `aria-expanded` kept.
- (c) Coin expand: human source names (map in `attention-lines.ts`, unknown ids capitalised), compact numbers (max 2 decimals), state word in a fixed third column, same grid at all widths, block capped at 34em.
- (d) No series for any basket: no legend, no chart, ONE line (`attention-nodata`, adds "Ranking is off..." when the reference is missing).
- (e) My baskets error: "Attention could not be loaded." + Retry (`attention-retry`), no API path. Discovery already had it.
- (f) Discovery: same title style ("Attention by category"), same joined 7d/30d/90d control (`basket-seg`), "as of" date, headers "Score (%)" / "Median (%)" with signed numbers, coin rows in a grid, categories with 0 coins used folded into one collapsed "N categories without data" line.
- (g) y label "Attention score, start = 100" above the plot and a faint 100 line (a flat series, `#4b5568`, literal because canvas cannot read CSS variables, same rule as `chart-palette.ts`).
- (h) Top-bar height: repro measured. Cause is `.app-shell` (`grid`, `min-height: 100dvh`, two implicit rows): when the page is shorter than the viewport the spare height is shared with the rail row. At 375 px the rail measured 353 px; with `grid-template-rows: auto 1fr` in the 760 px media query it measured 38 px. Shell CSS, not narrative-owned, so NOT fixed (see 10).
- Known limits: Discovery still has no chart (the standard says chart first; not in this task's list). The mobile rail stretch above still shows in short-page shots. Real-payload chart/table/coin render is unproven end to end (F-4). The as-shipped e2e case proves the real API plus UI for the empty state only. Defect 9 (removal notice) not touched (screener, out of scope).
- Red-first: the 4 existing vitest cases that encoded the old behaviour went red (error text, raw `1200`, raw `wiki`) after the code change and were updated; new cases added for retry, one-line empty, y label, labels/compact numbers, chevron, Discovery header and folded categories. Test edits and code are in one commit, so red is recorded here only.

## 4 Files changed
`web/app/globals.css` (T74 block only; removed the unused `.discovery-window` rules), `web/lib/attention-lines.ts`, `web/components/narrative/{BasketAttentionChart,BasketCoins,BasketTable,DiscoveryTab,DiscoveryTable,NarrativeTabs}.tsx`, tests `web/components/narrative/__tests__/{BasketAttention,BasketCoins,DiscoveryTab,NarrativeTabs}.test.tsx`, `web/e2e/narrative.spec.ts` (as-shipped state, retry and folded-category assertions, two idle categories in the Discovery fixture), screenshots and `index.md`, this report. `api/` untouched.

## 5 Commits
One commit on the branch (SHA in the PR).

## 6 Tests run
Base `cc33613`, UTC 2026-10-17.
| cmd | result |
|---|---|
| baseline `pnpm test` (web) | 481 passed |
| baseline `tsc --noEmit` | clean |
| baseline `pnpm test:e2e` (PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium, SCREENER_REFRESH_WORKER=0) | 86 passed |
| `pnpm install --frozen-lockfile` | ok, lockfile and package.json unchanged |
| after `pnpm test` | 489 passed (60 files; +8 new cases), 12:5x UTC |
| after `tsc --noEmit` | clean |
| after `pnpm test:e2e` full | 86 passed, 12:58 UTC; `contrast.spec.ts` unedited, green |
| `git diff --check` | clean |
| `git diff origin/main -- api` | empty |
Grep gate: no colour or font-size literal added in `.tsx`/css (the two canvas colours are in `attention-lines.ts`).

## 7 Tests NOT run
Real-payload chart/table/coin/Discovery e2e (F-4, see 9). `pnpm build:islands` and `pnpm build` (no island code changed; the e2e web server builds the islands). No live-provider or network run.

## 8 Deviations
- Read cap exceeded: CLAUDE.md plus the components, the T74 CSS block, the narrative spec, `contrast.spec.ts` and the report parts come to roughly 90 KB, well over 36,000 B. The files to touch alone do not fit the cap. I read by range where I could and read nothing else.
- Item 3 not done (needs_input); I continued the independent items instead of stopping everything. Nothing irreversible was done.
- Draft PR as the envelope says (the session default would be ready for review).
- Before shots of the as-shipped state were made with a throwaway spec on stashed main; it is deleted.

## 9 Blockers
F-4 needs api changes. The real attention API returns null scores and null series for any source without a record in `api/data/attention/probe_records.json`, which ships as `{}` (`registry.read_series` returns "not-probed"). The path is a module constant (`PROBE_RECORDS_PATH`), not env-driven, and `seed_e2e_cache.py` seeds no attention store. A real chart, row, coin expand or Discovery row therefore cannot be produced from the real API without (a) an env override for `PROBE_RECORDS_PATH` (one line in `api/data/attention/registry.py`, same for weights and universe paths) and (b) seeding parquet series plus a probe-records file into the e2e cache in `seed_e2e_cache.py` (the pytest builders `put`/`put_refs` in `api/tests/analytics/attention/conftest.py` show the shape). Decision needed: allow those api edits in a follow-up task.

## 10 Follow-up
- Shell fix (one rule, for the owner or planner): in the `@media (max-width: 760px)` block of `web/app/globals.css` add `.app-shell { grid-template-rows: auto 1fr; }`. Fixes the stretched rail on every short mobile page (measured 353 px to 38 px). Cross-page CSS, so not done here.
- F-4 as above.
- Discovery has no chart; add one if the standard's "chart first" should hold there.
- Removal notice (defect 9) is still quiet.

## 11 Context cost
About 90 KB of files read (see 8), 45 screenshots viewed selectively (about 12 images), three full e2e runs (two narrative+contrast, one full), plus one baseline full run. No subagents. No money spent beyond model usage; well under the 7 USD ask line.
