---
phase: rfc-004-web
date: 2026-09-28
status: COMPLETE
feature: cointegration-screener
plan: process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md
name: report:pair-screener-rfc-004
description: "RFC-004 execute report — /pairs table + /pairs/[a]/[b] detail, vitest, mutation check, live walkthrough on the real cache"
---

# RFC-004 — Web /pairs table + pair detail

**Answer first:** RFC-004 is code-complete and green:

- `pnpm --filter web test`: **153 passed / 19 files**, which is 110 + 43 new, with 0 failed.
- `tsc --noEmit`: **exit 0**.
- Mutation check: **37 of 37** mutations killed.

The live walkthrough on the real cache shows:

- **153 rows** and **21 "raw only" tags**;
- the banner **"No pair is significant after correcting for 153 tests (5% level). Closest: DOGE/BCH,
  corrected p 0.087."**;
- a rendered spread chart on `/pairs/DOGE/BCH`.

There was one small wording deviation, fixed during the walkthrough; see Plan Deviations.

Not done yet: nothing is committed, and the plan's "User confirmed working" box is left for you.

## What Was Done

| File | Change |
|---|---|
| `web/lib/types/pairs.ts` | new — mirror of `api/models/pairs.py` |
| `web/lib/api/pairs.ts` | new — `fetchPairs`, `fetchPairDetail`. Same `getJson` pattern as `regime.ts`, plus it keeps the API's `detail` text on 404/422 |
| `web/lib/format-pairs-value.ts` | new — formatters, `SIGNIFICANCE_LEVEL = 0.05`, `sortPairs`, `isRawOnlySignificant`, `significanceSummary`, and the optimism-note copy |
| `web/components/pairs/ComputationStatusBanner.tsx` | new — the stale / results_unavailable banner, plus `ApiUnavailableNotice` |
| `web/components/pairs/PairsTable.tsx` | new — fixed-order table; non-ok rows use `DeadDataNotice` (the message variant) |
| `web/components/pairs/PairDetailView.tsx` | new — the detail layout from the Stage 0 report, section 7 |
| `web/components/pairs/SpreadChart.tsx` | new — one `lightweight-charts` line series (spread only) |
| `web/app/pairs/page.tsx`, `web/app/pairs/[a]/[b]/page.tsx` | new routes |
| `web/app/page.tsx` | **+5 lines:** a "Open the pair screener" link (`data-testid="home-link-pairs"`). It is the only edit to an existing file. |
| `web/lib/__tests__/format-pairs-value.test.ts` | new — 20 tests |
| `web/components/pairs/__tests__/{fixtures.ts, PairsTable.test.tsx, PairDetailView.test.tsx}` | new — 12 table tests + 11 detail tests |
| `rfc-004-walkthrough/*.png` | screenshots from the live walkthrough |

Unchanged: everything under `web/app/{screener,regime,narrative}`, `web/components/{screener,regime,narrative}`,
`web/lib/api/{regime,screener,narrative}.ts` and `format-unavailable-reason.ts`, and all of `api/`. Confirmed with
`git status --short`.

TypeScript does no statistics. The only numeric logic is display rounding, the fixed sort, the 5%
comparison, and counting rows that have a corrected p.

## Test Gate Outcomes

| Gate | Result |
|---|---|
| `pnpm --filter web test` | **19 files, 153 passed, 0 failed** (baseline was 110/16) |
| `pnpm --filter web exec tsc --noEmit` | **exit 0**; `web/tsconfig.tsbuildinfo` restored afterwards |
| Mutation check: one mutation per distinct render/logic branch, restored after each run | **37/37 killed**, listed below |
| Agent-probe: manual table + detail walkthrough | **done**, see Live Walkthrough |

The 37 mutations, one per branch:

- **p-value format:** floor, 2 significant figures, 3 decimals, null guard.
- **Half-life:** not-mean-reverting text, below-10 decimal.
- **z-score:** the minus sign.
- **Sort:** group order, ascending order, raw-p tie-break, non-ok group order.
- **Raw-only tag predicate:** the corrected-p side and the raw-p side.
- **Summary banner:** the some-significant, none-significant and no-tests branches, and the denominator.
- **Table:** non-ok row, Johansen reason, raw-only tag, error notice, disclosure, banner, results_unavailable hides the table.
- **Freshness banner:** stale and results_unavailable.
- **Detail view:**
  - the second EG block and the "used for ranking" marker;
  - Johansen reason, not-mean-reverting banner, non-ok body, null pair;
  - optimism note, error notice, z-score.
- **Chart:** the chart plots spread, not z-score.
- **Error notice:** the HTTP-error vs unreachable split (2 mutations).

## Live Walkthrough (real cache, this worktree)

- API: `uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8000`
- Web: `pnpm --filter web dev`
- Pages loaded in headless Chromium through the installed `@playwright/test`, driven by an ad-hoc script. That script is not a test file and was not added to the repo.
- Both servers were stopped afterwards, and ports 3000 and 8000 were confirmed free.

| Check | Result |
|---|---|
| `GET /api/pairs` | `computation_status: fresh`, 153 pairs, 153 with a corrected p, 0 below 5%, 21 raw-only |
| `/pairs` rows | **153** |
| Significance banner | **"No pair is significant after correcting for 153 tests (5% level). Closest: DOGE/BCH, corrected p 0.087."** |
| Raw-only tags | **21** (matches the API count) |
| Freshness banner | none (fresh) |
| First rows | DOGE/BCH (raw 0.00057, BH 0.087, 114 d, −0.12), ETH/BCH (0.0017, 0.128, 95 d, +0.44), ETH/LINK (0.0044, 0.128, 140 d, +0.44). Same as the RFC-003 report's top rows. |
| `/pairs/DOGE/BCH` | Sample 2020-10-04 → 2026-09-25 (2,183 days). **Chart renders:** canvas present, 1384×260 px, "Plotted: 2020-10-04 → 2026-09-25 (2,183 points)", so the chart range equals the sample window (AC-7 spot check). |
| Detail values | DOGE on BCH p 0.00057 (used for ranking); BCH on DOGE p 0.562; BH 0.087; Johansen 24.75 vs 15.49 → Yes; half-life 114 d; z −0.12. The disclosure and the optimism note are both present. |
| `/pairs/DOGE/ZZZ` | "Pair screener request failed (… 404: ZZZ is not in the pair-screener universe)." |
| `/pairs/BTC/btc` | "Pair screener request failed (… 422: a and b must be different coins)." |
| API stopped, then `/pairs` | "Pair screener unavailable — could not reach the API (Failed to fetch)." |
| NaN / Infinity / undefined | none in visible text or `<main>` on either page. A first body-text check matched Next's inline `<script>` payload; that was a false alarm. |

Screenshots are in `rfc-004-walkthrough/`: `pairs-table.png`, `pairs-detail-DOGE-BCH.png`, `pairs-api-down.png`.

## Plan Deviations

1. **The error notice has two wordings instead of one.** On the live 404 page, the approved Stage 0 text
   "could not reach the API" was false: the API answered. HTTP errors now say "Pair screener request failed (…)".
   Real network failures keep the approved wording. The change is within the RFC-004 blast radius, and a test
   covers each wording.
2. **The plan's manual step asks to click into an `insufficient_overlap` pair live, but real data has none**
   (153/0/0). That state is proven by vitest only; RFC-005's seeded E2E can cover it in a browser.
3. **Red-first was not literal.** Tests were written alongside the code. The mutation check stands in as proof
   that the tests actually bite.

## What Was Skipped or Deferred

- RFC-005 (Playwright `pairs.spec.ts`, isolation proof) was not started, as instructed.
- No commits.
- The "User confirmed working" box is unticked.

## Test Infra Gaps Found

- None new. Each vitest run takes about 35–90 s on this machine, mostly jsdom environment setup, so the
  37-mutation loop took about 25 minutes. Scoping each mutation run to the three pairs test files kept that
  manageable.

## Closeout Packet

- **Plan:** `process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md`.
  The RFC-004 status strip says CODE-COMPLETE; all checklist and verification boxes are ticked except "User confirmed working".
- **Verified:** vitest, tsc, mutation check, and the live walkthrough on the real cache (table, detail, 404/422, API down).
- **Not verified:** your own review of the table and the detail view; a live non-ok row (none on real data).
- **Classification:** keep in `active/`, awaiting your review. Next: RFC-005.
- **Follow-up stubs:** none. **CONTEXT_PARTIAL:** none.

## Forward Preview

### Test Infra Found

- `web/components/pairs/__tests__/fixtures.ts` provides `tablePairs()` (6 rows covering every state), `tableResponse()`, `okDetail()` and `detailResponse()`.
- Stable `data-testid`s for RFC-005's `pairs.spec.ts`:
  - `pairs-table`, `pairs-row-{A}-{B}` (with `data-status`), `pairs-raw-only-*`;
  - `pairs-significance-banner`, `pairs-status-banner` (with `data-status`), `pairs-api-error` (with `data-kind`);
  - `pairs-spread-chart`, `pairs-chart-range`, `pairs-sample-window`;
  - `pairs-eg-a-on-b`, `pairs-eg-b-on-a`, `pairs-johansen-block`;
  - `home-link-pairs`.

### Blast Radius Changes

- The new files listed above, plus 5 lines in `web/app/page.tsx`.

### Commands to Stay Green

- `pnpm --filter web test`
- `pnpm --filter web exec tsc --noEmit`, then `git checkout -- web/tsconfig.tsbuildinfo`

### Dependency Changes

- None. `node_modules` was installed with `pnpm install --frozen-lockfile` inside `web/`; the lockfile is unchanged.

TL;DR: `/pairs` and `/pairs/[a]/[b]` are built and green: 153/19 vitest, tsc 0, 37/37 mutations killed. Live on
the real cache: 153 rows, 21 raw-only tags, the exact banner, and the DOGE/BCH chart renders over its full
2,183-day window. One deviation: 404/422 now say "request failed" rather than "could not reach the API". Waiting for your review.
