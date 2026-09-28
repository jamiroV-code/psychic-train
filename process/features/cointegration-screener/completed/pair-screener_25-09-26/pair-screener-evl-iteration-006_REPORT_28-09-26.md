---
name: pair-screener-evl-iteration-006
date: 2026-09-28
domain: tests
iteration: 6
loop_status: CONTINUE
---

# Pair Screener — EVL Iteration 006 (RFC-005 final gates)

**Result:** 1 failing gate (a flaky vitest test). Every other gate is green.

| Gate | Result |
|---|---|
| pytest | 484 passed / 3 deselected |
| tsc | exit 0 |
| Playwright | 35/35, run twice (5.8 min, 4.6 min) |
| Isolation diff vs 35e646f | clean |
| vitest | **failed 1 of 3 full runs**, and 1 of 2 runs of the file alone |

## Failing test

- **Test:** `web/components/pairs/__tests__/PairDetailView.test.tsx`, "plots every spread point unchanged, over the sample window (AC-7 unit level)".
- **Failure:** `expect(mockCharts).toHaveLength(1)` at line 53 received 0.
- **Likely cause:** a race in the test. `findByTestId` resolves as soon as the chart div exists. `createChart` runs later, in `SpreadChart.tsx`'s `useEffect`.
- **Origin:** added in RFC-004 (`970a433`); RFC-005 did not change it.

**Fix:** wait for the chart mock (for example with `waitFor`) before asserting. Test-only change, no component logic change. Then run vitest repeatedly to prove it is stable.

## Also found (not a gate failure)

The API and the page order rows that tie on corrected p differently. The API sorts by coin name; the page sorts by raw p, then name. No written contract covers ties. This goes to the user to decide.

TL;DR: one flaky test from RFC-004; fix it in the test and prove it is stable.
