---
name: plan:daily-data-gap
description: "D18 screener daily gap disclosure: timestamp-derived summary, mirrored contracts and visible warning."
date: 02-11-26
feature: screener
---

# Daily data gap: implementation plan


Date: 02-11-26
Complexity: Simple
Context router: process/context/all-context.md.

## Acceptance Criteria

The seven criteria in daily-data-gap_SPEC_02-11-26.md are mandatory: exact missing intervals, multiple-gap totals, no false positives, cache/reload persistence, repair transition, unchanged history/calculations, and accessible rendering at all three widths. Each maps to a verification row below.
Status: VALIDATED after plan corrections; Gate: PASS for implementation readiness. Feature tests remain unrun.
Selected SPEC: daily-data-gap_SPEC_02-11-26.md in this folder.

## Overview

Preserve daily history and disclose internal UTC-day gaps on each crypto screener coin and drill-down. Detect from stored timestamps rather than the transient adapter note. Python computes; web only formats. No new provider calls, history mutation or indicator changes.

## Goals and Success Metrics

Meet SPEC AC1-AC7: accurate gap totals/ranges, cache and reload persistence, repair transitions, unchanged data/calculations, accessible responsive warning.

## Phase Completion Rules

PLANNED means no implementation. CODE DONE is not VERIFIED. Completion needs payload-to-screen integration, error/boundary cases, stored-data preservation, browser evidence and owner confirmation. Record commands/results honestly; missing browser evidence is a gap, not a pass.

## Execution Brief

1. Backend summary and contracts: compute daily internal intervals, expose them on board and drill-down responses. Test exact intervals and unchanged inputs.
2. Frontend disclosure: mirror contract, visible count on coin and ranges in drill-down. Test absent/no-gap/gap/repair states.
3. Integration and browser proof: seeded isolated cache, cache-hit/reload/repair transition, three widths, no live exchange requests. Owner reviews before live deployment.

## Scope

In: crypto daily input disclosure regardless of displayed timeframe. Out: backfill, extra exchange traffic, D7 backoff, indicator recalculation changes, pairs/regime warnings, equities calendar-gap classification.

## Assumptions and Constraints

Internal gaps only between earliest/latest observed daily candles. Daily candle timestamps are UTC; deduplicate and order timestamps without modifying the supplied dataframe. Consecutive observed days define missing inclusive date ranges. Empty/single-day/consecutive data yields no gaps. Never infer leading history or future candles. Do not treat equity weekends as crypto gaps. If timestamps violate the existing adapter contract, investigate rather than silently replacing unknown data with a clean result.

## Functional Requirements

Add a DailyDataGap summary with missing_days (integer >=0) and ranges of inclusive start/end UTC dates. Add daily_data_gap to CoinPanel and ChartView with a default null for non-crypto callers and existing fixtures. Crypto assembly supplies a summary, including zero/ranges=[] for checked continuous data. Null means not evaluated, not a gap-free assertion. Web tolerates older payloads missing the optional field.

## Touchpoints

Existing: api/models/screener.py; api/analytics/screener_board.py; web/lib/types/screener.ts; web/components/screener/CoinPanel.tsx; web/components/screener/DrillDownView.tsx.
New bounded files: api/analytics/daily_data_gap.py (pure interval summary), optional shared web/components/screener/DailyDataGapNotice.tsx for count/ranges without duplicated formatting.
Tests: locate existing screener analytics/contract tests and component tests before editing; add focused daily-gap behavior tests and one seeded browser scenario under web/e2e/ following existing screener fixture conventions. Existing equities assembly shares response types and must remain unaffected.

## Public Contracts

Board CoinPanel and drill-down ChartView gain optional daily_data_gap. Mirror Python/TypeScript types and update exact-key contract tests deliberately. Do not propagate a one-request note as durable truth. Build coin panel uses its already-fetched daily dataframe; drill-down uses the existing daily read if present, otherwise cache.read_ohlcv(symbol, '1d'), never another fetch solely for detection. Verify actual daily cache naming before implementing. Shared component displays 'Daily data gap: N missing days', explanatory indicator limitation, and drill-down inclusive UTC ranges. No new route or writes.

## Blast Radius

Backend and frontend screener contracts plus bounded tests. API additive-contract risk; no authentication, dependencies, background-worker or live-deployment changes. Read shared equities callers and preserve their behavior.

## Implementation Checklist

- [ ] Confirm clean isolated worktree from current origin/main and overlapping PR ownership; preserve parent local account config and X test processes.
- [ ] Read SPEC, actual model/assembler callers and current fixture conventions; obtain references before changing exported symbols if LSP is available.
- [ ] Add regression scenarios for one/multiple gaps, duplicates/order, UTC and month/year boundaries, continuous/empty/short/stale-only data.
- [ ] Order/deduplicate timestamp values only (O(n log n) worst case), then scan intervals in O(n); allocate no per-missing-day arrays and do not modify the supplied dataframe.
- [ ] Add mirrored optional summary contract; integrate board using existing daily data and drill-down with a local daily cache read.
- [ ] Prove cached responses and repair transitions; verify stored bars and current indicator outputs unchanged.
- [ ] Add component behavior tests then render warning/count and UTC ranges, preserving existing no-gap layout.
- [ ] Add seeded reload/repair integration scenario with no provider calls and isolated files.
- [ ] Exercise actual rendered screen at 375/768/1280 and observe wrapping/accessibility; capture evidence.
- [ ] Run consolidated targeted tests/typecheck and CI once changes settle; fix genuine regressions.
- [ ] Update D18 backlog status after smoke proof, write completion report, open draft PR if authorized; no merge/deploy.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Exact gap intervals, multiple ranges and UTC calendar boundaries | Fully-Automated | AC1, AC2 |
| Empty/short/continuous and stale-only classification | Fully-Automated | AC3 |
| Board/drill-down cached payloads with provider calls disabled; reload | Fully-Automated | AC1, AC4 |
| Replace isolated daily series with repaired fixture and refresh | Fully-Automated | AC5 |
| Input timestamps/values and indicators unchanged | Fully-Automated | AC6 |
| Seeded browser warning and ranges at 375/768/1280 | Fully-Automated | AC7 |

Concrete commands and expanded ownership are specified in the Validate Contract below; they replace this draft's previously unbound test commands.

## Risks and Mitigations

Fetch notes disappear on cache hits: compute from timestamps. Added daily read may regress request cost: reuse loaded daily data or local cache only. Shared equities types: optional field, no equity gap inference. Long range lists: wrap visible drill-down content, no fixed-height clipping. Gap disclosure does not repair indicator assumptions: state limitation explicitly.

## Test Infra Improvement Notes

Validation found a shared E2E temp root and inherited worker/layout flags. The execution-owned E2E setup must isolate root/ports/layout and fail closed on backend provider access before seeding or starting servers.

## Validate Contract

Gate: PASS after incorporating the corrections below. Two independent Codex reviewers evaluated contracts/security and test/runtime fit. Initial concerns were plan gaps, not implementation failures. Parent subsequently proved browser launch using installed Edge 156.0.4314.58 through Playwright: an in-memory page rendered "D18 validation" and the browser closed successfully. No site or provider was contacted. The existing plan structure validator must remain green.

### Bound contracts and caller migrations

- `DailyDataGapRange`: inclusive UTC date-only `start`/`end`, serialized `YYYY-MM-DD`. `DailyDataGap`: nonnegative integer `missing_days`, ordered disjoint `ranges`. Python parent fields default to null; TypeScript parent fields are optional and nullable. Mirror both nested types and parents.
- Board source: existing `dfs_by_tf["1d"]`. Drill-down source: `display.df` for 1d, existing `daily_ref` for 1w, exactly one local `cache.read_ohlcv(symbol, "1d")` for intraday. Bare ticker cache path: `ohlcv/<SYMBOL>/1d.parquet`. No added adapter call, refresh enqueue or write solely for detection.
- Shared equities assemblers retain default null; no crypto gap inference on trading calendars. Add equities regression assertions for board/chart responses.
- Early-return checked-zero for empty input, including an empty dataframe without columns. Nonempty data missing timestamp or containing null/NaT/unparseable timestamps is an explicit contract error, not dropped rows or a zero-gap result. Match `freshness.as_utc` naive-as-UTC convention; normalize to UTC before counting calendar dates.
- Update exact-key assertions in `api/tests/routers/test_screener_no_verdict_contract.py`; preserve removed-verdict checks. Include nested schema/nullability checks and unchanged equities results.
- Render notices outside chart-availability branches. Display date-only UTC ranges without Brussels datetime conversion. Existing structural sharing already compares new fields: no memoization rewrite. Prove summary-only repair updates the notice with unchanged chart data.

### Expanded test ownership and isolation

Allowed test infrastructure edits: `web/playwright.config.ts`, `api/scripts/seed_e2e_cache.py`, and bounded test-only server/fixture helpers if necessary. No production offline mode, new dependency, external request or live deployment is authorized.

- Use a separate execution worktree. The current seeder deletes its selected root: require a unique D18 run directory beneath temp and reject any general/shared/live cache root. Current fixed `screener-e2e-cache` is not safe for concurrent worktrees. Isolate fixture manifest writes in the execution checkout.
- Parameterize E2E root and ports with existing defaults preserved for other specs. Before starting inspect listeners; candidates 18001/13100 are not reservations. Align bind/readiness/baseURL/CORS/NEXT_PUBLIC_API_BASE_URL and focused spec; keep reuseExistingServer false. Never stop another listener.
- Explicit child env: UV_FROZEN=1; SCREENER_REFRESH_WORKER=0; SCREENER_ATTENTION_PC_WORKER=0; SCREENER_ATTENTION_REDDIT_STREAM=0; SPOT_VOLUME_REFRESH=0; LSE_API_KEY empty. Redirect watchlist/layout/universe/narratives/equities paths into the unique root; SCREENER_LAYOUT_PATH must override inherited live paths.
- Fresh fixtures are not proof of offline behavior. A test-only real-app server entrypoint must fail fast on exchange/provider construction and record attempted calls. Assertions require zero such attempts; no fake successful provider response. Backend regression tests separately verify unchanged adapter-call counts, including absent/stale daily cache during intraday drill-down.
- Write/repair fixtures with actual cache writers, restore in finally, and never modify live cache. API tests explicitly depend on isolated_cache plus isolated watchlist/layout. Browser evidence must cross real storage -> API -> rendered screen, not route-mocked payloads.
- Browser executable verified: `C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`. Set PLAYWRIGHT_CHROMIUM_PATH explicitly. AC7 still requires actual seeded-screen evidence at 375/768/1280; blank-page readiness does not prove the feature.

### Exact gates for EXECUTE

New files: `api/tests/analytics/test_daily_data_gap.py`, `api/tests/routers/test_screener_daily_data_gap.py`, `web/e2e/daily-data-gap.spec.ts`.

1. Root: `uv run --project api pytest api/tests/analytics/test_daily_data_gap.py api/tests/routers/test_screener_daily_data_gap.py api/tests/routers/test_screener_no_verdict_contract.py api/tests/data/test_ccxt_tail_fetch.py api/tests/analytics/test_equities_board.py -q`.
2. In web/: `pnpm exec vitest run components/screener/__tests__/CoinPanel.test.tsx components/screener/__tests__/DrillDownView.test.tsx components/screener/__tests__/ScreenerBoardLive.test.tsx`; add summary-only transition assertions here or the existing same-data test if required.
3. In web/: `pnpm test` and `pnpm exec tsc --noEmit --incremental false`.
4. With isolated env/ports/root and offline server guard, in web/: `pnpm exec playwright test e2e/daily-data-gap.spec.ts --project=chromium --workers=1`. If actual config project name differs, use its verified name rather than dropping the gate.
5. Run `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/daily-data-gap_02-11-26/daily-data-gap_PLAN_02-11-26.md`.

AC1/2: pure exact counts/ranges and real rendered payload; AC3: empty/short/continuous/stale-only plus missing/invalid input boundaries; AC4: cache hit/reload with zero extra provider attempts; AC5: real fixture repair, refresh and summary-only change; AC6: unchanged stored bars and indicator outputs with existing gap-kept retention regression; AC7: screenshots/overflow and accessible visible text at all three widths. CI does not run Playwright: local screen evidence is mandatory. Runtime tests execute only after source implementation approval.

### Validation disposition

Infra/setup, test coverage, breaking changes and security: PASS for the corrected plan. Backend, frontend and integrated proof sections: PASS for feasibility with the mandatory gates above. No feature execution is claimed. Recheck current-main ownership before EXECUTE; changes since this review require reconciliation, not silent omission of tests.

## Resume and Execution Handoff

Selected plan: process/general-plans/active/daily-data-gap_02-11-26/daily-data-gap_PLAN_02-11-26.md.
Last completed phase: VALIDATE, plan gaps corrected.
Validate-contract status: written above; Gate PASS for readiness, no source changes authorized yet.
Supporting context: SPEC, D18 note, API models/assemblers/shared equities callers, frontend data-sharing/components, process/context/tests/all-tests.md, process/context/operating-instructions.md and existing Playwright/seeder conventions.
Next step: user approval via ENTER EXECUTE MODE, then one isolated Codex execution owner. Do not alter running X/Reddit tests or the main deployment.

## Cursor and RIPER-5 Guidance

One plan only. VALIDATE is complete for the corrected plan. Source changes require explicit execute approval. Do not create another plan or silently remove AC7.
