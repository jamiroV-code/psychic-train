# Screener group sort by name, % change or RSI (backlog note)

**Origin:** screener batch 3 (S5a, S5b), residual AC-8r (SPEC AC-8, Locked), user decision Q1 A on 09-10-26.
**Owner slice:** a small follow-up slice after the S5b merge and its PC probe (P-S5b-1). Not part of S5a or S5b.

## What AC-8 promised

Sort each coin group by name, % change or RSI, with unavailable values placed last and labelled (SPEC US-3, AC-8).

## Why it is deferred

The user chose manual order plus buttons for S5 and asked to judge sorting after using the groups. Q1 was resolved as A: defer. Until this note is done AC-8 is a named residual, not delivered, and the batch 3 gate stays CONDITIONAL on it.

## Dependencies

- The S5b layout files: `web/lib/layout-state.ts` (pure moves), `web/lib/use-board-layout.ts` (serial save queue), `web/components/screener/{CoinGroup,ScreenerBoard}.tsx`, the saved layout from `GET/POST /api/layout/crypto`.
- RSI and % change values come from the board payload (`CoinPanel.rsi`, the gain chips), so no API change is expected.

## Suggested design

- Preferred: one-shot "Sort group by" actions (name, % change, RSI) that rewrite the saved coin order through the existing save path, so a sort persists and the buttons keep working afterwards.
- Alternative: a view-only sort that resets on reload (no saved state, but then the order shown differs from the stored order).
- Unavailable values (N/A RSI, unavailable chart) sort last and keep their reason label.
- No verdict wording; tests as plain functions; the sort is a pure function in `layout-state.ts`.

## Estimate

About 3 web files plus tests, about 0.7 USD [estimate]. Programme ceiling 60 USD; re-check the spend before spawning.

## Done when

- Each of the three sorts orders a group correctly, unavailable values last and labelled (vitest, pure function and component).
- One seeded e2e test sorts a group and reads the new order after a reload (one-shot design).
- AC-8r moves from CONDITIONAL to PASS in the batch 3 plan.
