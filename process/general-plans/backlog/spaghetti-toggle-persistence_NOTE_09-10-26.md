# Spaghetti legend toggles: persistence across reloads (backlog note)

**Origin:** T37 / S6 (screener batch 2), named residual AC-S6-6 (= AC-22), user-accepted (Q4).
**Owner slice:** S5 (not in S6).

## What is missing

The spaghetti chart's per-coin legend toggles (`spaghetti-toggle-<SYM>`, `aria-pressed`) keep their state in memory only (`SpaghettiChart` `hidden` set). A reload shows every line again.

## Done when

- The hidden set survives a reload (storage choice is S5's decision).
- An S5 e2e test toggles a coin, reloads `/screener`, and reads `aria-pressed="false"` on the same toggle.
- AC-S6-6 moves from CONDITIONAL to PASS in the batch-2 plan.

## Pointers

- `web/components/screener/SpaghettiChart.tsx` (the `hidden` state and `toggle`).
- `web/lib/spaghetti-lines.ts` `buildSpaghettiLines(data, hidden)` already takes the set.
