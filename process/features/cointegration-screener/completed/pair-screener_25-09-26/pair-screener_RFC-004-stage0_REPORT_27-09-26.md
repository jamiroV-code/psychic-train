---
name: report:pair-screener-rfc-004-stage0
description: "RFC-004 (web /pairs table + detail) Stage 0 — reuse points, route shape, types, formatting, banner copy, vitest plan, open UI decisions"
date: 27-09-26
metadata:
  node_type: memory
  type: report
  feature: cointegration-screener
  phase: RFC-004-stage0
---

# RFC-004 Stage 0 — Web /pairs table + pair detail

**Answer first:** the plan's shape works as written, with no new dependency and no change to screener, regime
or narrative files. The detail view is a separate route, `/pairs/[a]/[b]`, because the plan chose it. The
table is a plain `<table>` with one fixed sort order. Five small UI decisions need your approval (end of report).
The web baselines still hold: **vitest 110 passed / 16 files, `tsc --noEmit` exit 0**.

No app code was written, nothing was committed, and the plan checklist was not ticked.

## 1. Baselines (this worktree, `caa49ec`)

| Command (from `tests/all-tests.md`) | Result |
|---|---|
| `pnpm install --frozen-lockfile` (inside `web/`, fresh worktree) | done, 8.8 s |
| `pnpm --filter web test` | **16 files, 110 passed**, matching the expected numbers |
| `pnpm --filter web exec tsc --noEmit` | **exit 0** (`web/tsconfig.tsbuildinfo` restored with `git checkout` afterwards) |

## 2. Reuse points confirmed

| File | What RFC-004 reuses |
|---|---|
| `web/lib/api/regime.ts` | Copy of the `getJson` pattern: base-URL fallback, 10 s timeout, readable errors. The copy lives in `lib/api/pairs.ts`; `regime.ts` is not touched. |
| `web/components/screener/DeadDataNotice.tsx` | Use its **`message` variant** only: `{testId, message}`. Its `reason` variant is typed to the screener's closed union, so it is not used. The file is imported, never edited, the same way `RegimeDashboard` does it. |
| `web/lib/format-unavailable-reason.ts` | Not extended. The pairs API already sends human-readable `reason`, `johansen_reason` and `stale_reason` text, so the UI shows that text verbatim. No code-to-copy map is needed, and nothing in this file changes. |
| `web/lib/format-regime-value.ts` | Pattern only: one formatter module, `NO_VALUE` fallback, `Number.isFinite` guard, U+2212 minus sign. |
| `web/components/regime/ComponentPanel.tsx` | Chart lifecycle only: `createChart` → `addSeries(LineSeries)` → `chart.remove()` on unmount. |
| `web/test/mocks/lightweight-charts` + `vi.mock(...)` | Existing chart mock for component tests. |
| `RegimeDashboard`'s `fetchData?` prop | Injected-fetcher pattern for tests (success, error and 404 paths). |

## 3. Component breakdown

| File (all new) | Role |
|---|---|
| `web/lib/types/pairs.ts` | TS mirror of `api/models/pairs.py` (section 4) |
| `web/lib/api/pairs.ts` | `fetchPairs()` → `GET /api/pairs`; `fetchPairDetail(a, b)` → `GET /api/pairs/{a}/{b}`. The 404 and 422 `detail` text is kept in the thrown error. |
| `web/lib/format-pairs-value.ts` | All formatters, the default sort and the significance summary (sections 5 and 6). Pure functions; the only numeric logic is display rounding, ordering and counting. |
| `web/components/pairs/PairsTable.tsx` | Fetches on mount, draws the computation-status banner, the significance banner, the disclosure line and the table |
| `web/components/pairs/ComputationStatusBanner.tsx` | Shared by the table and the detail view: the `stale` / `results_unavailable` banner with `stale_reason` |
| `web/components/pairs/PairDetailView.tsx` | Detail layout (section 7) |
| `web/components/pairs/SpreadChart.tsx` | One `lightweight-charts` line over `spread[]` |
| `web/app/pairs/page.tsx` | `<h1>Pair screener</h1>` + `<PairsTable />` |
| `web/app/pairs/[a]/[b]/page.tsx` | `<PairDetailView a b />`. Next 15 route params are a Promise and must be awaited. |
| `web/app/page.tsx` | **One added `<Link href="/pairs">`**. The plan's Stage 5 says "link from `web/app/page.tsx`", so this is in scope. It is the only edit to an existing file. |

## 4. TS types (mirror of `api/models/pairs.py` as built)

```ts
export type PairStatus = "ok" | "insufficient_overlap" | "coin_unavailable";
export type ComputationStatus = "fresh" | "stale" | "results_unavailable";
export type HalfLifeState = "computed" | "not_mean_reverting";

export interface HalfLife { state: HalfLifeState; days: number | null }          // days null iff not_mean_reverting
export interface Johansen { trace_stat: number; crit_value_95: number; rank_at_least_1: boolean }
export interface EGDirection { dependent: string; independent: string; hedge_ratio: number; intercept: number; t_stat: number; p_value: number }
export interface SpreadPoint { date: string; spread: number; z_score: number }

export interface PairSummary {
  coin_a: string; coin_b: string; status: PairStatus; reason: string | null;
  overlap_days: number | null; sample_start: string | null; sample_end: string | null;
  eg_p_raw: number | null; eg_p_bh: number | null;
  eg_direction: string | null;            // "DEP~INDEP" of the lower-p direction
  eg_p_other_direction: number | null;
  johansen: Johansen | null; johansen_reason: string | null;
  half_life: HalfLife | null; z_score: number | null;
}
export interface PairDetail extends PairSummary {
  eg_a_on_b: EGDirection | null; eg_b_on_a: EGDirection | null;
  spread_direction: string | null; half_life_ar1_beta: number | null;
  spread: SpreadPoint[];                  // [] iff status != ok
}
interface Envelope {
  generated_utc: string; computed_at: string | null;
  computation_status: ComputationStatus; stale_reason: string | null;
  diagnostic_scope: "whole_history_in_sample"; diagnostic_disclosure: string;
}
export interface PairsResponse extends Envelope { universe_size: number; pair_count: number; min_overlap_days: number; pairs: PairSummary[] }
export interface PairDetailResponse extends Envelope { pair: PairDetail | null }
```

## 5. Formatting rules (`format-pairs-value.ts`)

All formatters return `"—"` plus the reason text for `null` or a non-finite value. They never show `NaN` or `0`.

| Value | Rule | Real examples |
|---|---|---|
| p-value (raw, BH, other direction, per-direction) | `p ≥ 0.01` → 3 decimals; `0.0001 ≤ p < 0.01` → 2 significant figures; `p < 0.0001` → `"< 0.0001"` | 0.087 → `0.087`; 0.723 → `0.723`; 0.00057 → `0.00057`; 0.0017 → `0.0017` |
| half-life | `computed`: `N d`, a whole number of days when ≥ 10, one decimal when < 10. `not_mean_reverting`: the text "Not mean-reverting — no half-life" | 114 → `114 d`; 7.4 → `7.4 d` |
| z-score | 2 decimals, signed, with U+2212 for minus | −0.12 → `−0.12`; 0.44 → `+0.44` |
| Johansen | trace and 95% critical value to 2 decimals, plus "Yes" or "No" from `rank_at_least_1` (the API's boolean, not recomputed) | `18.31 vs 15.49 — Yes` |
| EG direction | `"ETH~BTC"` → `"ETH on BTC"` | — |
| hedge ratio / t-stat | 3 / 2 decimals | — |
| sample window | `2021-01-01 → 2026-09-24 (1,820 days)` from `sample_start`, `sample_end` and `overlap_days` | — |

## 6. Table

**Default order (fixed, no sort controls):**

1. `ok` rows, sorted ascending by `eg_p_bh`. Ties break on `eg_p_raw`, then `coin_a/coin_b` alphabetically, so the order is deterministic.
2. Then a separate group of non-`ok` rows (`insufficient_overlap`, then `coin_unavailable`), in alphabetical order.

The non-`ok` group is never part of the p-value sort. It is not sorted as `Infinity`.

**Columns:** Pair (link to detail) · Status · Overlap days · Raw p · BH-corrected p · Direction · Johansen (yes/no) · Half-life · z-score.

**Row flag:** an `ok` row with `eg_p_raw < 0.05` and `eg_p_bh ≥ 0.05` gets a visible tag, "passes raw, not after correction". The row is not hidden. On real data this tags 21 rows.

**Non-`ok` rows:** the stat cells span one cell, rendered through `DeadDataNotice` (`message` = the API's `reason`, verbatim). `overlap_days` shows when it is not null: 240 for insufficient overlap, "—" for an unavailable coin.

**Johansen refusal on an `ok` row:** the cell reads "—" with the `johansen_reason` text under it. The row stays `ok` and keeps its place in the sort.

**Significance banner** (always shown when `pairs` is not empty). It is built from API data only:

- the number of tests is the count of rows with `eg_p_bh != null`, which is the BH denominator; `pair_count` is not used here;
- the count of significant pairs is the rows with `eg_p_bh < 0.05`;
- the closest pair is the row with the minimum `eg_p_bh`.

Wording:

- None significant: **"No pair is significant after correcting for 153 tests (5% level). Closest: DOGE/BCH, corrected p 0.087."**
- Some significant: **"3 of 153 pairs are significant after correcting for 153 tests (5% level)."**
- No `ok` rows: **"No pair has enough data to test."**

**Disclosure line** under the banner: the API's `diagnostic_disclosure`, verbatim.

**Computation-status banner** (above everything):

- `stale`: **"These results are out of date: {stale_reason}. Showing the last computed results from {computed_at}."** The table still renders.
- `results_unavailable`: **"No pair results available: {stale_reason}."** No table is drawn.
- Fetch error or API down: **"Pair screener unavailable — could not reach the API ({error message})."** No blank table.

## 7. Detail view (`/pairs/[a]/[b]`)

The sections render top to bottom:

1. **Computation-status banner** (same component as the table).
2. **Heading** `A / B`, the status, and the sample window line.
3. **Disclosure:** `diagnostic_disclosure` verbatim, in a persistent banner (ADR-2c).
4. **Spread chart:** one line over `spread[]` for `spread_direction`, the lower-p direction as the API chose it. The caption states the plotted date range; AC-7 is checked against the sample window line. Latest z-score shown next to the chart.
5. **Engle-Granger, both directions side by side:** `eg_a_on_b` and `eg_b_on_a`, each with p, hedge ratio and t-stat. The used direction is marked. Optimism-bias note (static UI copy; the API does not send one): **"The table ranks each pair by the better of these two tests. Picking the better of two related tests makes the result look slightly more significant than a single test chosen in advance."**
6. **Johansen block, separate from EG, never merged:** trace vs the 95% critical value, then "Cointegrated at 95% (rank ≥ 1): Yes/No". When refused: "—" plus `johansen_reason`.
7. **Half-life:** the value, or the not-mean-reverting banner.

**Other detail states:**

- A non-`ok` pair returns 200 with `spread: []`. The view shows the status, the `reason` in a `DeadDataNotice`, and no chart or stats.
- 404 (unknown ticker) and 422 (self-pair) show the API's `detail` text.
- A fetch error shows the same API-down notice as the table.

Back link: "← All pairs".

## 8. Vitest plan (`pnpm --filter web test`)

| File | Cases |
|---|---|
| `web/lib/__tests__/format-pairs-value.test.ts` | p-value golden values for each band, including exact boundaries (0.01, 0.0001) and null / NaN / Infinity → "—"; half-life (computed ≥ 10, < 10, not_mean_reverting text); z-score sign and U+2212; direction text; sample window. **AC-4:** a shuffled fixture sorts by BH ascending, the tie-break holds, and non-ok rows come last and are never interleaved. Significance summary: 0 significant (exact banner string), N significant, and no ok rows; denominator = non-null `eg_p_bh` count. Raw-not-corrected flag predicate. |
| `web/components/pairs/__tests__/PairsTable.test.tsx` | C(n,2) rows from a fixture; insufficient and unavailable rows show the reason text and no stat cells; the Johansen-refused `ok` row shows `johansen_reason` and stays in the sorted group; the flag tag appears; the banner text is exact; the disclosure is verbatim; the stale banner shows `stale_reason` and the table stays; `results_unavailable` shows the banner and no table; the injected-fetcher error shows the explicit notice (AC-8); no `NaN` anywhere in rendered text. |
| `web/components/pairs/__tests__/PairDetailView.test.tsx` | Both EG directions and the Johansen block render at the same time (AC-6); optimism note present; not_mean_reverting banner; the chart mock gets `spread.length` points, and the first/last dates equal `sample_start`/`sample_end` (AC-7 unit level); non-ok pair shows the reason and no chart; 404 message; error path. |
| `web/components/pairs/__tests__/fixtures.ts` | A small hand-built response. Values are copied from real RFC-003 output where possible, such as DOGE~BCH 0.00057 / 0.087. |

After green, mutation-check each distinct render branch, following the RFC-4/5 standing lesson in `all-tests.md`. Expected result: about 3 new files and roughly 30–40 tests on top of 110.

## 9. Open UI decisions (need your approval)

1. **The 5% level is a UI constant.** The API sends no alpha, so the banner and the row flag use `SIGNIFICANCE_LEVEL = 0.05`, defined once in `format-pairs-value.ts`. This compares numbers; it does not compute a statistic. **Recommend: accept.** The alternative is an `alpha` field on the API, which is an RFC-003 contract change.
2. **Sorting.** Section 7 of the plan says "sortable"; your lock says there is no toggle to sort by raw p. **Recommend: v1 has one fixed order and no column-sort controls at all.** This is the simplest reading of both.
3. **p-value display bands** as in section 5, especially the `"< 0.0001"` floor. Real minimum raw p is 0.00057, so nothing on real data hits the floor today.
4. **The optimism-bias wording** in section 7 is static UI copy, because the API has no field for it. Accept the wording, or give me your own.
5. **The spread chart plots `spread` only.** A z-score overlay is not included; the z-score is shown as a single latest number. Adding the z-score series is easy, but it is not in the plan.

The home-page link is **not** an open item: plan Stage 5 names it explicitly.

## What Was Skipped or Deferred

Stages 1–5, as instructed.

TL;DR: Stage 0 is done, with no app code and no commits. The design uses the route `/pairs/[a]/[b]`, a
plain fixed-order table, API reason text shown verbatim, and 3 vitest files. The baselines are
110/16 and tsc 0. Five small decisions are waiting for your approval.
