# W8g report: Sources panel health text

## 1 Task ID
W8g (plan narrative-baskets-xreddit-collector_PLAN_21-10-26.md, lines 238-242; SPEC rules 15-16, AC38, AC39, AC47, AC52). Branch `claude/w8g-web-status`.

## 2 Outcome
review. Code, tests and draft PR done; owner visual probe of the Sources page still open.

## 3 Summary
- `web/lib/types/discovery.ts`: `DiscoverySourceRow` gains optional `reason`, `impl`, `health`; new `DiscoverySourceHealth` and `DiscoveryAccountHealth` match `api/models/discovery.py` field for field (nullable fields typed `| null`).
- `web/lib/source-health.ts`: `sourceHealthLines(row)` formats only (no computation besides unit display): reason code text, method (impl), last unit time in UTC, paused (reason, until UTC end or "owner action needed" when `pause_until` is null), stale flag, today's attempted/fetched, budget used of effective (", spent"), completeness text plus attempted/fetched/missing with reasons/capped/newest age for `completeness_day`, mode, X accounts active of total with each label's state, reason and cookie age, a "one day late" note, free disk (GB). Every null shows "unknown"; never 0, NaN or blank. Returns null for rows without `health`.
- `DiscoverySourcesPanel.tsx`: rows with `health` get a second full-width row (`colSpan=7`) with a wrapping visible list; no tooltips. Rows without `health` render unchanged.
- `clock_sync_age_seconds` is typed but not shown (always null per contract; not in the requested list).

## 4 Files changed
- web/lib/types/discovery.ts
- web/lib/source-health.ts (new)
- web/components/narrative/DiscoverySourcesPanel.tsx
- web/lib/__tests__/source-health.test.ts (new)
- web/components/narrative/__tests__/DiscoverySourcesPanel.test.tsx (new)
- this report

## 5 Commits
1. `test(w8g): red vitest cases ...` (types + stub helper + failing tests; 8 failed / 3 passed at commit).
2. `feat(w8g): Sources panel health and completeness text ...`.
3. report commit.

## 6 Tests run
- Red: the two new files, 8 failed as expected before implementation.
- Green: `pnpm test` in web/: 591 passed, 1 failed: `lib/__tests__/plot-ink.test.ts` ("globals.css has no rule for .spread-chart .tick text"). Not touched by this slice (globals.css unchanged); fails locally on this Windows checkout, see CI result in the PR for the Linux run.
- `pnpm exec tsc --noEmit --incremental false`: clean. tsconfig.tsbuildinfo not modified.
- CI on PR #197 (run 41048488312): `web — vitest, tsc, island build` pass (incl. plot-ink, so its local failure is specific to Windows); `api — pytest` pass.

## 7 Tests NOT run
- No visual check at 375/768/1280; overflow safety is by construction (single colSpan cell, `white-space: normal`, `overflow-wrap: anywhere`, table inside the existing `.discovery-scroll`) and unproven in a browser.
- Playwright e2e: not run (PLAYWRIGHT_CHROMIUM_PATH not set; no seeded spec found for the health block).

## 8 Deviations
- Wrap styles are inline in the component because globals.css is outside the allowed file list.
- The X accounts line shows for row id `x` or whenever account data is present; Reddit rows without a pool omit it.

## 9 Blockers
None.

## 10 Follow-up
- Owner probe: open the Sources panel once on phone and desktop width.
- plot-ink local failure if CI also shows it (pre-existing, outside scope).

## 11 Context and cost
Single worker pass; read the panel, types, API model, plan section and existing panel test only.
