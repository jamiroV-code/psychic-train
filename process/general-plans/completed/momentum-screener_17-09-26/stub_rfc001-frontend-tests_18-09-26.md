---
name: stub_rfc001-frontend-tests
feature: momentum-screener
phase: RFC-001 (follow-up)
date: 18-09-26
---

## Session Goal

RFC-001's entire `web/` stack (11 files: layout/page/ScreenerBoard/CoinPanel/DrillDownView/RelativePerformanceChart/MiniChart + 3 test files + types/api client) was written to spec but has NEVER been executed — `pnpm install` could not run in this cloud sandbox (total package-registry blockage, see `momentum-screener_PLAN_17-09-26.md` → `## Deviations`). This stub closes that gap. This is the larger of the two RFC-001 follow-ups (the backend gap is comparatively narrow); until this closes, RFC-001 cannot be classified "Ready for UPDATE PROCESS archival" under the Hard E2E gate rule — frontend is developed behavior with zero automated gate coverage right now.

## Status: RESOLVED for automated gates (18-09-26) — Agent-Probe (item 70, RFC-004 scope) still open, non-blocking

## Implementation Checklist

- [x] In an environment with real network access to npm, run `pnpm install` from `web/`.
- [x] Run `pnpm --filter web test` — **10 passed** (3 test files: `ScreenerBoard.test.tsx`, `DrillDownView.test.tsx`, `RelativePerformanceChart.test.tsx`), user-confirmed on their own machine.
- [x] First real run found a genuine config bug (not the components themselves): `vitest.config.ts` was missing `@vitejs/plugin-react`, so every test failed with `ReferenceError: React is not defined` (classic-vs-automatic JSX transform mismatch). Fixed — added the plugin to `web/package.json` and wired it into `vitest.config.ts`. Re-run after the fix: all 10 passed. See `momentum-screener_PLAN_17-09-26.md` → `## Deviations` item 12.
- [x] `lightweight-charts` v5 `addSeries` API usage — covered implicitly by `RelativePerformanceChart.test.tsx`'s passing `createChart`-spy test (item 29d); no separate confirmation needed now that the suite runs for real.
- [ ] Item 70's Agent-Probe (full end-to-end visual + touch pass on a real dev server) — **not done, but this is RFC-004 scope, not RFC-001's**; left open, doesn't block RFC-001 or RFC-002/003 starting.
- [x] Automated gates all pass — RFC-001's frontend half is verified.

## Blast Radius

`web/` only.

## Verification Evidence

Exact command that must go green: `pnpm --filter web test` (from repo root, after `pnpm install` in `web/`). Agent-Probe: `pnpm --filter web dev`, manual tap-to-expand check on a mobile viewport, per PLAN item 70.
