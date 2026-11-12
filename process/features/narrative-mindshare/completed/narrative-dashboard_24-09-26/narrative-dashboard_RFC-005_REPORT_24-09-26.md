---
phase: rfc-005-narrative-page
date: 2026-09-24
status: COMPLETE_WITH_GAPS
feature: narrative-mindshare
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# RFC-5 execute report — `/narrative` page

**BLUF:** `/narrative` is built (Stages 1–5), web-only. The web suite is green: **109 tests passed in 16 files** (75 before, +34 new). `tsc --noEmit` exits 0. The screener code, including `NarrativeStrip.tsx` and its test, is unchanged. Nothing is committed. Still open: the manual browser walkthrough and AC-11 user confirmation.

## What Was Done

- **Stage 1**
  - `web/lib/types/narrative.ts` mirrors `api/models/narrative.py` field-for-field.
  - `web/lib/api/narrative.ts` provides `fetchNarrativeHistory({categories,start,end})`, using the regime `getJson` pattern.
- **Stage 2** (`web/components/narrative/`)
  - `CategoryHistoryPanel.tsx`
    - Has its own independent chart and shows full history (`fitContent`).
    - Draws the composite plus each normalised source line.
    - pytrends nightly-7d (solid) and backfill-269d (dashed) are separate lines.
    - `gap_before` breaks lines via `toSegmentedSeriesData`.
    - `mixed_scale` points are drawn as orange marker dots, with a count note.
    - The legacy CoinGecko count and the Hyperliquid new-listings count are shown as text ("legacy-map count … excluded from the composite"), not plotted.
    - Narrative-only coins are labelled.
    - Per-series stale/unavailable/presumed-dead notices use the `DeadDataNotice` message variant.
    - Each panel shows a personal-use badge.
  - `ComparisonView.tsx` and `ChangeInAttentionView.tsx`: ranked tables. A null rank, value or delta shows "—" plus a reason and sorts last, never as 0.
  - `DataQualityCaveat.tsx` and `RedistributionBadge.tsx`.
- **Stage 3**
  - `NarrativeDashboard.tsx` fetches once with an injectable fetcher and handles loading, error and empty states.
  - Layout is one scrolling page: caveat at the top, then History, Comparison and Change stacked, each with its own caveat.
  - Soft cap of 10 panels, with a "+N more categories" overflow that opens panels on demand.
- **Stage 4:** `web/app/narrative/page.tsx`. `web/app/page.tsx` gets a link (`home-link-narrative`).
- **Stage 5:** `formatNarrativeReason` is added to `web/lib/format-unavailable-reason.ts`. Its copy covers:
  - `credentials-not-configured` (kept for later, as instructed), `no-baseline-yet`, `no-hyperliquid-market` and `no-archived-data`.
  - The rank reasons, the exchange reasons, and the `last-point-N-days-old`, `fetch-failed:`/`parse-failed:`, legacy-map and backfill prefixes.
  - Unknown codes are shown verbatim.
- **Reddit when no credentials are set:** the RFC-4 job writes no row, so `/history` sends `status: unavailable, reason: no-archived-data`. The panel renders this as "Reddit [unavailable]: Unavailable — no archived data for this source yet" (tested).
- **Helper:** `web/lib/narrative-view-model.ts` holds layout-only helpers: soft-cap split, per-panel date union, rank ordering. It computes no numbers.

## Test Gate Outcomes

| Gate | Result |
|---|---|
| `pnpm --filter web test` | **16 files, 109 passed, 0 failed** |
| `pnpm --filter web exec tsc --noEmit` | exit 0 (tracked `web/tsconfig.tsbuildinfo` restored afterwards) |
| `git diff -- web/components/screener` | empty (`NarrativeStrip.tsx` + its test unchanged) |
| pytest | not run by instruction (RFC-4 editing api/); EVL runs it |
| Manual walkthrough `/narrative` | not run (Verification Checklist items open) |

New or extended vitest files:
- `components/narrative/__tests__/NarrativeDashboard.test.tsx` (7 tests)
- `CategoryHistoryPanel.test.tsx` (9 tests)
- `RankViews.test.tsx` (2 tests)
- `lib/__tests__/narrative-view-model.test.ts` (5 tests)
- `format-unavailable-reason.test.ts` (+11 test cases, 15 total)
- Shared fixtures: `components/narrative/__tests__/fixtures.ts`

## Plan Deviations

- C1–C3 were applied as approved in Stage 0: a sibling formatter, independent panels, and the `DeadDataNotice` message variant.
- **D1: seed categories are not force-included in the soft cap.** `/history` returns only seed categories, and the response carries no `seed` flag. Pinning seeds would therefore switch the cap off. The cap ranks by latest composite; categories with no composite sort last. The overflow never drops a category, so the ADR-9 intent (nothing hidden) holds. This stays within blast radius.
- **D2: no per-panel hover readout.** Stage 0 mentioned one as optional. The chart's own crosshair and price labels are used instead. Raw values stay available through the API only.
- **D3: mixed-scale markers use a dots-only line series, not `createSeriesMarkers`.** It works with the shared chart mock and matches the dots approach already used in the gap-breaking helper.

## What Was Skipped or Deferred

- Playwright spec: RFC-6 owns it. The data-testids are in place.
- Manual browser walkthrough and user confirmation of AC-5, AC-6 and AC-11: pending.

## Test Infra Gaps Found

None new. Charts are verified against the shared `test/mocks/lightweight-charts` mock only. Real-canvas rendering waits for RFC-6 Playwright.

## Closeout Packet

- Plan: `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
- **Verified:** the web vitest suite and the typecheck.
- **Not yet verified:** the manual walkthrough, real-canvas rendering, and live data.
- Classification: **Keep in active/testing** until EVL and the manual walkthrough are done.
- Next: EVL confirmation run (vc-tester, full suites once RFC-4 lands), then RFC-6.
- Follow-up stubs: none. CONTEXT_PARTIAL: none.

## Forward Preview

- **Test Infra Found:** `web/components/narrative/__tests__/fixtures.ts` has response builders that RFC-6 can reuse.
- **Blast Radius Changes:**
  - New: `web/app/narrative/`, `web/components/narrative/`, `web/lib/{types,api}/narrative.ts`, `web/lib/narrative-view-model.ts`.
  - Edited: `web/lib/format-unavailable-reason.ts` (additive), `web/app/page.tsx` (one link).
- **Commands to Stay Green:** `pnpm --filter web test`; `pnpm --filter web exec tsc --noEmit`.
- **Dependency Changes:** none.
- **testids for RFC-6:**
  - Page and states: `narrative-dashboard`, `narrative-loading`, `narrative-error`, `narrative-empty`, `narrative-history`, `narrative-caveat-{page|history|comparison|change}`, `narrative-redistribution-badge`.
  - Per panel: `narrative-panel-{id}`, `narrative-chart-{id}` (`data-points`), `narrative-chart-empty-{id}`, `narrative-legend-{id}-{composite|source[-variant]}`, `narrative-notice-{id}-{source[-variant]}`, `narrative-composite-notice-{id}`, `narrative-mixed-scale-{id}` (`data-count`), `narrative-legacy-count-{id}`, `narrative-new-listings-{id}`, `narrative-coin-{id}-{SYMBOL}` (`data-narrative-only`), `narrative-redistribution-{id}`.
  - Overflow: `narrative-overflow-toggle`, `narrative-overflow-list`, `narrative-overflow-item-{id}`.
  - Rank views: `narrative-comparison`, `narrative-comparison-row-{id}` (`data-rank`), `narrative-comparison-mixed-{id}`, `narrative-comparison-empty`, `narrative-change`, `narrative-change-row-{id}`, `narrative-change-mixed-{id}`, `narrative-change-empty`.
  - Home link: `home-link-narrative`.

TL;DR: `/narrative` is built and green (109/109 vitest, tsc clean, screener untouched), uncommitted. Next are the EVL confirmation run and the manual walkthrough.

## EVL fix cycle 1

- Gap (evl-iteration-001): no assertion proved ChangeInAttentionView renders a null delta as "—" rather than 0.
- Fix: added `data-testid="change-delta-{category_id}"` on the delta `<td>` (no behaviour change) and a new test in `RankViews.test.tsx` asserting the null-delta cell is exactly "—", contains no "0", its row shows the reason text, and a non-null delta cell is exactly "+0.25".
- Mutation proof: null-delta render changed to `0` -> new test failed (1 failed / 2 passed); reverted byte-identically (`cmp` clean) -> 3/3 passed.
- Gates: `pnpm --filter web test` 16 files / 110 tests passed, 0 failed; `pnpm --filter web exec tsc --noEmit` exit 0; `web/tsconfig.tsbuildinfo` restored via git checkout. Nothing under `api/` touched; not committed.
