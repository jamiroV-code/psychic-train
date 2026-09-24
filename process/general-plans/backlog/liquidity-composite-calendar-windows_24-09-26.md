# Backlog NOTE — liquidity composite uses row-count windows, not calendar windows

**Date**: 24-09-26
**Status**: backlog (NEW PLAN REQUIRED)
**Found by**: VALIDATE of `process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`

## Finding

`api/analytics/regime/liquidity_composite.py::_roc` is `series.pct_change(periods=window_days)`.
The constants are commented as calendar days (`NET_LIQUIDITY_ROC_DAYS = 28  # ~4wk change, calendar days`,
`DOLLAR_ROC_DAYS = 30`), but the inputs have one row per **business day**:

- `fred_adapter.fetch_net_liquidity` is indexed on RRPONTSYD's daily business-day rows.
- DTWEXBGS is a business-day series.

So "28 days" is ~28 business days (~5.5 weeks) and "30 days" is ~6 weeks. Stablecoin supply
(DefiLlama, calendar-daily) is unaffected.

## Why it matters

The reduced composite feeds `leg_boundary.detect_candidate_boundaries`; ADR-1 Amendment #2 tuned
`SUSTAINED_DAYS=2` against the current (row-based) behaviour. Changing the window changes the
composite and therefore the backtested boundaries, so this must be its own plan with a re-run of
`api/scripts/backtest_leg_boundaries.py`, not a drive-by fix.

## Proposed approach

Replace row-based `pct_change` with an as-of lookup (`merge_asof(direction="backward")` against
`date − N calendar days`) — the same helper the regime dashboard's `components.py` will introduce —
then re-run the 2017 / 2020-21 backtest and compare candidate/confirmed counts to the
20-09-26 baseline (`leg-boundary-backtest-report-20260920-184700.json`).

## Addendum (24-09-26, RFC-002 of the regime dashboard)

- `fetch_net_liquidity` uses **WTREGEN** (TGA weekly *average*) carried as-of onto RRP's daily
  rows. LiqTide's net liquidity is **WALCL − WDTGAL − RRPONTSYD×1000 on the Wednesday grid**
  (WDTGAL = TGA Wednesday level) — exact match on 4 dates checked; the WTREGEN version was $115bn
  off on 2026-09-16. `api/analytics/regime/components.py` uses the WDTGAL definition; the leg path
  still uses WTREGEN. A future plan should move the leg path to the same definition and re-run
  the backtest.
- LiqTide's per-component normalisation is `sign × tanh(impulse/scale)` (see the RFC-002 Stage 0
  report); the reduced composite's expanding z-scores could adopt it too.
