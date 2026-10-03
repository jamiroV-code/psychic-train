---
name: stub_rfc004-frontend-tests
feature: momentum-screener
phase: RFC-004 (follow-up)
date: 19-09-26
---

## Session Goal

RFC-004's frontend half (`ConfidenceBadge.tsx`, `SignalDetailPanel.tsx`, their two test files, and the `CoinPanel.tsx` wiring change) was written to spec but had never been executed this session — same npm-registry-blockage root cause as every prior RFC's frontend gap (see `momentum-screener_PLAN_17-09-26.md` → `## Deviations`, RFC-004 EXECUTE pass items 4 and 6). This stub tracks closing that gap on the user's own machine, mirroring `stub_rfc001-frontend-tests_18-09-26.md`'s shape.

## Status: PARTIALLY RESOLVED (19-09-26) — scoped vitest pass confirmed; full-suite EVL gate and Agent-Probe still open

## Implementation Checklist

- [x] Run `pnpm test -- ConfidenceBadge SignalDetailPanel` from `web/` — **user-confirmed passed** on their own machine, 19-09-26. First real execution of items 66-69 (both components + both test files).
- [ ] Run `pnpm --filter web test` (full suite) — item 71's frontend half of the EVL confirmation gate. Not yet reported.
- [ ] Run `uv run pytest api/` (full suite) — item 71's backend half. Not yet reported (backend scoped tests were already green in-sandbox this session; the full-suite real-dependency run is the remaining piece).
- [ ] Item 70's Agent-Probe: open `/screener` on a real/dev server, confirm two coins with differing narrative/trend/leg-timing show visibly distinct badges, and that tapping a badge on a touch-emulated or real mobile viewport reveals the per-signal detail panel. Not yet performed.

## Blast Radius

`web/components/screener/ConfidenceBadge.tsx`, `SignalDetailPanel.tsx`, their `__tests__/` files, `CoinPanel.tsx`'s wiring change.

## Verification Evidence

Exact commands still needed, from repo root: `uv run pytest api/` (full) and `pnpm --filter web test` (full), plus the Agent-Probe pass described above. Once all three land green/confirmed, RFC-004 upgrades from `DONE_WITH_CONCERNS` to `✅ VERIFIED` and this plan is ready for UPDATE PROCESS (per the plan's own "Order discipline" note in `## Resume and Execution Handoff`).
