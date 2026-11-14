---
name: spec:btc-momentum-signals
description: "User-facing requirements for displaying Triple Momentum buy and sell signals on the existing BTC legs price chart."
date: 02-11-26
feature: charting-indicators
metadata:
  node_type: memory
  type: spec
---

# BTC Momentum Signals — SPEC (02-11-26)

## Summary

Add clear BUY and SELL markers to the existing BTC price chart so the user can see when the provided three-segment momentum model changes its BTC exposure direction. Keep the current BTC legs visualization unchanged for this step; the user will define leg boundaries and their future visualization later. This feature displays signals only: it does not place trades or show the strategy's backtest statistics.

## User Stories / Jobs To Be Done

- As the user, I want the BTC chart to mark the momentum model's buy and sell changes, so I can see those signals in the context of BTC price and the existing legs.
- As the user, I want the legs visualization to remain intact for now, so its later redesign can follow the drawing and definition I will provide.
- As the user, I want to see only the signals on the chart, so the strategy's performance table, equity curve and execution/backtest details do not obscure the price view.

## What The User Wants (Behavioral Outcomes)

- The existing BTC chart keeps its current price, leg boundaries/bands and leg-estimate presentation unchanged for this step.
- The chart shows a BUY marker when the model's target BTC allocation increases, and a SELL marker when it decreases. SELL includes a partial reduction as well as a move to zero; the model is long-only and never opens a short.
- Markers are dated on the signal bar close. The supplied script calculates the signal at that close and would fill its strategy order at the next bar's open. The chart presents signals only and does not execute those orders.
- The signal calculation follows the supplied script: three non-overlapping momentum segments using the selected chart's bars, a daily moving-average filter, and exposure changes determined by the score, vote scaling, maximum exposure and below-MA scale. Inputs and defaults follow the supplied script unless the user later changes them.
- A missing price or insufficient warm-up history does not produce a marker. Inactive date ranges do not produce signals.
- No equity curve, strategy statistics table, allocation values, trade list or execution simulation is added.
- The later user-provided leg definition and drawing may change the legs visualization, but that redesign is not part of this request.

## Flow / State Diagram

```text
BTC chart bars + daily close series
              |
              v
    Enough history and in date range?
       | no                 | yes
       v                    v
    no marker       Calculate three segment votes
                                |
                                v
                   Apply daily MA exposure filter
                                |
                                v
                Compare target with prior target
                   | greater     | lower      | same
                   v             v            v
                 BUY           SELL        no marker
              (signal bar close; no order is placed)
```

## Acceptance Criteria (Testable Outcomes)

- AC1: With known BTC closes, the three non-overlapping segment returns produce the same 0–3 positive-vote score as the supplied script.
  proven by: hand-calculated momentum segment golden-value scenarios across positive, negative and zero returns
  strategy: Fully-Automated
- AC2: The default horizon lengths, crypto bar-count auto behavior, daily MA filter, vote scaling, exposure cap and below-MA scale match the supplied script; invalid non-increasing segment endpoints are rejected.
  proven by: default and boundary input scenarios plus invalid horizon ordering
  strategy: Fully-Automated
- AC3: A BUY marker appears on the signal bar close when target allocation increases, including zero-to-positive and partial increases; it does not appear when target allocation is unchanged.
  proven by: target-transition scenarios for entry, increase and unchanged allocation
  strategy: Fully-Automated
- AC4: A SELL marker appears on the signal bar close when target allocation decreases, including partial reduction and reduction to zero; no short position or short marker is produced.
  proven by: target-transition scenarios for partial reduction, full exit and nonnegative target bounds
  strategy: Fully-Automated
- AC5: The signal-bar timestamp is used for markers; no marker is shifted to the next bar open, and signal computation does not use future bars.
  proven by: timestamp and no-lookahead scenarios with sequential bars
  strategy: Fully-Automated
- AC6: Insufficient history, missing required daily MA data, missing bars and out-of-date-range bars produce no signal marker rather than a zero-filled or fabricated signal.
  proven by: warm-up, missing-input and date-boundary scenarios
  strategy: Fully-Automated
- AC7: Signal computation uses the chart timeframe's bars for momentum and daily closes for the moving-average filter, as in the supplied script, including when the displayed chart timeframe is not daily.
  proven by: mixed-timeframe fixture scenarios comparing chart bars to daily MA input
  strategy: Fully-Automated
- AC8: The BTC chart continues to render its existing legs, boundaries, estimate and price alongside signal markers, with leg appearance unchanged.
  proven by: BTC legs chart component scenario asserting existing overlays remain alongside markers
  strategy: Fully-Automated
- AC9: No orders, equity/backtest statistics, equity curve or allocation display are introduced; the user sees BUY/SELL markers only for the new signal layer.
  proven by: chart interaction/surface scenario and API contract test for signal-only payload
  strategy: Fully-Automated

## Out Of Scope

- Changing what constitutes a BTC leg or redesigning leg boundaries, bands, labels or the estimate. The user will provide a drawing and definition later.
- Executing or simulating trades, routing orders, shorting BTC, or displaying position sizes.
- Strategy performance/backtest outputs: equity curve or multiple, CAGR, volatility, Sharpe, Sortino, drawdown, time in market, average exposure, rebalances or trade list.
- Replacing or removing the existing BTC price history or legs chart.
- Applying FDM as an additional statistical correlation-matrix weighting scheme. The supplied Pine code explicitly calls its `sqrt(3)` vote scaling a simplified vote-to-exposure mapping, not full volatility-targeted or correlation-adjusted FDM; this request follows the executable script rather than adding an unstated formula.

## Constraints

- User decisions: both the existing BTC legs visualization and momentum signals appear on one chart; keep the existing legs display unchanged for now; signals only; signal timing follows the supplied script; signal definitions follow the script; later the user will provide the leg drawing/definition.
- The script is long-only: BUY indicates target allocation rises; SELL indicates target allocation falls, and may be partial. It never opens a short.
- Momentum segment returns use the selected chart timeframe's bars; the trend filter uses daily bars and the daily moving average. On non-daily chart timeframes this is intentionally mixed-timeframe behavior from the script.
- The script calculates at bar close and fills at next open; chart markers represent the signal close, not the hypothetical fill.
- Existing BTC legs chart code is in the screener/chart surface; BTC leg data comes from a cache-only API path while the refresh worker is running.
- Product policy D-2 currently forbids generated bullish/bearish calls. This user request explicitly overrides that policy for this BTC momentum chart only; it does not authorize signals elsewhere or trade execution. Record the scoped exception in the decision log during planning/implementation.
- Project invariant: all numerical calculations belong in Python; frontend charts render returned data. Signal values must not be recomputed independently in JavaScript/Svelte.
- No network access in tests. Tests that touch cache paths must use isolated fixtures. Full chart behavior needs a browser-level scenario crossing the API and rendered chart boundary; the test router says CI does not run Playwright.
- This SPEC is requirements-only; no implementation approach or schema is prescribed.

## Open Questions

None. Resolved with the user: signals mean increases/decreases in target allocation; use the supplied script's calculation and timing; retain existing legs visualization unchanged for now; keep the new surface to BUY/SELL markers only.

## Background / Research Findings

- User-provided script is titled `Segment Momentum (3 Votes)`. It uses non-overlapping 3-, 6- and 12-month segments by default, a default 21 bars per month (crypto auto uses 30 when the input is zero), positive-segment votes, a `sqrt(3)`-like vote scale (default 1.73), a 98% exposure cap, and a daily 200-day moving-average filter that halves exposure below the MA by default.
- The code turns changed target allocation into long order deltas; it closes when target reaches zero and never opens a short. Orders are calculated on close and filled on the next open (`process_orders_on_close=false`).
- User explicitly says the chart should display only BUY/SELL signals, not the strategy's statistics. The full model will be retained as technical background; the user-facing chart remains signal-only.
- Existing chart surface: `web/components/screener/BtcLegChart.tsx` renders BTC price, existing leg bands/boundaries and estimate; backend route is `/api/regime/btc-legs`. The screener's selectable chart timeframe currently applies to its coin panels/spaghetti view; whether/how it controls the BTC legs chart is an implementation question for INNOVATE/PLAN.
- Test context: API pytest, web Vitest and TypeScript checks run in CI; Playwright is the browser E2E runner and is not run by CI. The project's test guidance requires golden-value tests for numeric calculations and at least one end-to-end check across real data boundaries, with cache isolation.
