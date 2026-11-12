---
name: report:narrative-dashboard-rfc-005-stage0
description: "RFC-5 Stage 0 — /narrative page design: layout, components, fetch/types, chart + gap approach, reason copy, tests, testids, plan conflicts. No code written."
date: 24-09-26
metadata:
  node_type: memory
  type: report
  feature: narrative-mindshare
  phase: RFC-5-stage0
---

# RFC-5 Stage 0 — `/narrative` page

**BLUF:** RFC-5 can be built entirely inside `web/` on the regime-dashboard pattern, with no backend change. There are 3 plan-text conflicts, all resolved below on technical grounds. Two small product choices are left for the user. No source or test files were touched.

## 1. Contract actually used (from `api/models/narrative.py`, not plan §11)

`GET /api/narrative/history?categories=a,b&start=&end=` → `NarrativeHistoryResponse`:
`generated_utc, redistributable_all, grid_dates, categories[], comparison{as_of, entries[]}, change_in_attention{window_days, baseline_tolerance_days, as_of, entries[]}`.
- category: `category_id, label, keywords, coins[{symbol, narrative_only}], series[], composite{status, reason, sources, min_sources, max_gap_days, points[{date, value, coverage, sources_present, trust_weight, mixed_scale, gap_before}]}`
- series: `source, label, variant ("nightly-7d"|"backfill-269d"|null), cache_key, redistributable, status, reason, first_date, last_date, max_gap_days, in_composite, points[{date, raw_value, normalized_value, point_status, reason, gap_before}]`
- comparison entry: `category_id, rank, value, mixed_scale, status, reason`; change entry adds `delta, baseline_date`.
- Sources: `pytrends, reddit, coingecko (legacy, in_composite=false), coingecko-narrative, exchange_volume_share, exchange_new_listings`. Composite slots: pytrends, reddit, coingecko-narrative, exchange_volume_share.
- `normalized_value` is within-series min-max (0..1). Composite is on the same 0..1 scale.

## 2. Page layout (text wireframe)

```
/narrative
┌───────────────────────────────────────────────────────────────┐
│ Narrative attention            generated 2026-09-24 UTC       │
│ [personal-use only] badge (redistributable_all=false)          │
│ DataQualityCaveat (page-level)                                 │
├── tabs/sections (all rendered, anchor links) ─────────────────┤
│ 1. History                                                     │
│   DataQualityCaveat                                            │
│   grid of CategoryHistoryPanel (top 10 by latest composite,    │
│   seeds always included)                                       │
│   ┌ panel: label · status · coins (HYPE, XYZ*narrative-only) ┐ │
│   │ legend: composite ▬  pytrends 7d ▬  pytrends 269d ┄      │ │
│   │         reddit ▬  cg-narrative ▬  HL vol share ▬        │ │
│   │ chart (composite bold; ▲ markers on mixed_scale points)  │ │
│   │ notes: per-series status/reason (DeadDataNotice)         │ │
│   │ legacy-map count: 3 (excluded from composite)            │ │
│   │ HL new listings: "not enough history yet…" / count       │ │
│   │ badge: personal-use (per series redistributable=false)   │ │
│   └──────────────────────────────────────────────────────────┘ │
│   [+N more categories] → expandable list, same panel on click  │
│ 2. Comparison (as of D)  DataQualityCaveat                     │
│   rank · category · composite value · mixed-scale flag         │
│   unranked rows at bottom: "—" + reason text (never last place)│
│ 3. Change in attention (7d, baseline D-7..D-9) Caveat          │
│   rank · category · delta · baseline date · flags / reason     │
└───────────────────────────────────────────────────────────────┘
```
No reserved right column (regime's insights column is regime-specific).

## 3. Components (all new, `web/components/narrative/`)

| Component | Role |
|---|---|
| `NarrativeDashboard.tsx` | Fetch once (injectable `fetchData`, regime pattern), loading/error, soft cap + overflow, renders 3 sections |
| `CategoryHistoryPanel.tsx` | One `createChart` per category; composite + source lines; notices; legacy count; new-listings line; coins |
| `ComparisonView.tsx` | Ranked table from `comparison` |
| `ChangeInAttentionView.tsx` | Ranked table from `change_in_attention` |
| `DataQualityCaveat.tsx` | Static plain-language caveat (4 points: unofficial free proxies; normalised within each source; levels not comparable across providers; weighted below price signals) |
| `RedistributionBadge.tsx` (small) | "Personal use only — not redistributable" when flag false |

Reused unchanged: `DeadDataNotice` (message variant), `lib/regime-line-segments.ts` (`toSegmentedSeriesData`). `NarrativeStrip.tsx` and all `/screener` code untouched.

New lib files: `web/lib/types/narrative.ts`, `web/lib/api/narrative.ts`, `web/lib/narrative-view-model.ts` (pure: soft-cap selection, per-panel date union, series ordering — no maths), additions to `web/lib/format-unavailable-reason.ts`.

## 4. Data fetching

- `lib/api/narrative.ts`: own `getJson` copy (same as `lib/api/regime.ts`: base URL fallback, 10 s timeout, readable errors), `fetchNarrativeHistory({categories?, start?, end?})`.
- Types mirror the pydantic models field-for-field; `reason` stays `string | null` (backend reasons are open strings incl. `last-point-N-days-old`, `fetch-failed: X`).
- One call, full history, no polling. 422 → error state with message.

## 5. Chart approach (lightweight-charts)

- Per panel: build the panel's date union from composite + series points (category start dates differ; `grid_dates` is global and would pad young categories with blank space). Map each line onto it and call `toSegmentedSeriesData(times, values, gapBefore)` so `gap_before` breaks lines exactly as on `/regime`.
- Plotted: composite (bold) + each source's `normalized_value` (all 0..1). pytrends `nightly-7d` solid, `backfill-269d` dashed, separate series — never joined.
- `mixed_scale` composite points: series markers (small triangle, "mixed scale" tooltip text in legend) plus a note line "N points use backfilled pytrends (different scale)".
- Not plotted: legacy `coingecko` count (shown as text "legacy-map count: X — excluded from composite") and `exchange_new_listings` (a count, shown as text). Keeps the chart one scale.
- Independent panels, no sync: confirmed. Categories start on different dates and the SPEC asks for no cross-panel comparison on the time axis; comparison is done in the Comparison view instead. No reason found to reconsider.
- Hover: per-panel crosshair shows date + raw_value/normalized per source in a small readout inside the panel (formatting only).

## 6. Empty / error / degraded states

| Case | Render |
|---|---|
| loading | `narrative-loading` |
| fetch fails | `narrative-error` with message (DeadDataNotice message variant) |
| zero categories | `narrative-empty`: "No narrative categories tracked yet" |
| composite `unavailable` | panel shows notice with reason copy; chart still shows any source lines |
| series stale / unavailable / presumed-dead | per-series notice with reason copy; stale = badge, else gap |
| null rank/delta/value | "—" plus reason copy; row sorted after ranked rows; never `0` |
| `no-baseline-yet` | "Not enough history yet to detect new listings" |
| `credentials-not-configured` | "Reddit credentials not configured on the nightly job — source skipped" |

## 7. `format-unavailable-reason.ts` additions (owned by RFC-5)

Add a **sibling** export `formatNarrativeReason(reason: string | null): string | null` (see conflict C1). Cases:
`no-archived-data`, `no-baseline-yet`, `no-hyperliquid-market` ("Not listed on Hyperliquid"), `exchange-unavailable`, `zero-total-volume`, `empty-market-list`, `credentials-not-configured`, `no-keyword`, `stale`, `presumed-dead`, `no-composite-data`, `no-composite-on-as-of`, `no-baseline-in-window`; prefixes `last-point-N-days-old` → "Last data N days old", `fetch-failed:`/`parse-failed:` → "Source fetch failed"; the legacy-map reason and the pytrends backfill reason pass through as their own labels; unknown → "Unavailable (code)" (raw code shown, never hidden). Existing `formatUnavailableReason` unchanged.

## 8. vitest list

`web/lib/__tests__/`
1. `format-unavailable-reason.test.ts` (extend): each narrative case; `credentials-not-configured` and `no-baseline-yet` not equal to generic text; unknown code shown; existing screener cases unchanged.
2. `narrative-view-model.test.ts`: soft cap 10 by latest composite; seeds always kept (can exceed 10 → overflow shrinks); null composite sorted last not dropped; date union; nightly vs backfill kept separate.

`web/components/narrative/__tests__/` (chart mocked as in `RegimeDashboard.test.tsx`)
3. `NarrativeDashboard.test.tsx`: one panel per category up to cap; "+N more" opens remaining panels; caveat on all 3 views; injected fetcher reject → error notice; empty response → empty state; personal-use badge shown when `redistributable_all=false`.
4. `CategoryHistoryPanel.test.tsx`: legacy-map label + excluded text; narrative-only coin label; mixed-scale note/markers; stale/presumed-dead/unavailable notices; `gap_before` passed to segmenter; `no-baseline-yet` copy not `0`.
5. `ComparisonView.test.tsx` / `ChangeInAttentionView.test.tsx`: order by rank; null rank → "—" + reason, after ranked rows; mixed_scale flag; baseline date shown.
6. `/screener` guard: existing `NarrativeStrip.test.tsx` passes unchanged.
Command: `pnpm --filter web test`.

## 9. data-testids for RFC-6 Playwright

`narrative-dashboard`, `narrative-loading`, `narrative-error`, `narrative-empty`, `narrative-caveat-{history|comparison|change}` (plus `narrative-caveat-page`), `narrative-redistribution-badge`, `narrative-panel-{category_id}`, `narrative-chart-{category_id}`, `narrative-legend-{category_id}-{source}[-{variant}]`, `narrative-notice-{category_id}-{source}[-{variant}]`, `narrative-composite-notice-{category_id}`, `narrative-mixed-scale-{category_id}`, `narrative-legacy-count-{category_id}`, `narrative-new-listings-{category_id}`, `narrative-coin-{category_id}-{symbol}` (with `data-narrative-only`), `narrative-overflow-toggle`, `narrative-overflow-list`, `narrative-overflow-item-{category_id}`, `narrative-comparison`, `narrative-comparison-row-{category_id}` (`data-rank`), `narrative-change`, `narrative-change-row-{category_id}`, home link `home-link-narrative`.

## 10. Nav link

Yes: `web/app/page.tsx` has one `<Link>` per page (screener, regime). Add "Open the narrative dashboard" → `/narrative` (plan Stage 4).

## 11. Plan-text conflicts (resolved, technical)

- **C1** Plan Stage 5 says add `case` arms to `formatUnavailableReason`'s switch. That function is typed to the screener's `UnavailableReason` union; widening it changes `lib/types/screener.ts` and the screener's render sites. Resolution: sibling `formatNarrativeReason` in the same file. Same file, same ownership, screener untouched.
- **C2** ADR-9 says "synced-panel pattern reused" in its title but "independent (non-synced)" in the body. Resolution: independent, per the body (see §5).
- **C3** Plan §7 says gap states via `DeadDataNotice`. Its reason variant only takes screener reasons. Resolution: use its `message` variant with `formatNarrativeReason` text. No change to `DeadDataNotice`.
- Note: `credentials-not-configured` is not emitted by the backend yet (RFC-4 adds it). RFC-5 only formats it; fixtures cover it.

## 12. Decisions needed from the user

1. **Default time range per panel:** full history (recommended; narrative history is short, ~269d max) or last 90 days with zoom-out?
2. **Section layout:** all three views stacked on one scrolling page (recommended; simplest, caveat visible on each) or tabs?

Everything else above is decided on technical grounds.

TL;DR: Web-only design is ready; 3 plan-text conflicts resolved without touching screener code; two small product choices (default range, stacked vs tabs) needed before Stage 1.
