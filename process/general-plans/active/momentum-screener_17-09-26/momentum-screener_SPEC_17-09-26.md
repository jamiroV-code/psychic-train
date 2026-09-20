---
name: spec:momentum-screener
description: "Relative-strength momentum screener spanning charting, macro-liquidity legs, and narrative rotation"
date: 17-09-26
metadata:
  node_type: memory
  type: plan
---

[MODE: SPEC]

## Summary

The user is entering a new BTC bull-run cycle and wants one screen that answers three questions at a glance for every coin on their own watchlist: is it currently outperforming the market (BTC, or HYPE once rotation has taken hold), is it trending, and is now a good moment to scalp into it. Rather than checking each coin one at a time, the user wants a single visual board — a grid of small charts, one per watchlist coin — showing price, a trend line, and momentum together, so coins can be compared side by side. Layered on top of that board, the user wants to know which of the roughly three legs of the current bull run they're in (using macro liquidity as the timing signal) and which narrative or sector actually has attention right now, so they're not holding a coin that's technically "in momentum" but has already been left behind by a rotation into a different theme. The tool is meant to build confidence for position sizing, not to issue buy/sell calls — it should show agreement and disagreement between signals, not hide it behind a single verdict.

## User Stories / Jobs To Be Done

**US-1 — Spot outperformers at a glance**
As a crypto trader building a watchlist-driven momentum board, I want to see every coin on my watchlist compared against a benchmark (BTC or HYPE, depending on where we are in the cycle) on both a daily and a weekly timeframe, so that I can immediately tell which coins are actually leading the market right now versus just moving with it.

**US-2 — Compare the whole watchlist visually, in one place**
As a trader who currently has to check coins one at a time, I want every watchlist coin shown as its own small chart panel on a single page — price, trend line, and momentum together — so that I can compare strength across my whole list at a glance instead of tab-switching between individual charts.

**US-3 — Confirm trend before acting on momentum**
As a trader who doesn't want to chase a momentum reading that's really just noise, I want a simple trend line on each coin's panel, so that I can see whether the coin's underlying trend actually supports the momentum signal before I act on it.

**US-4 — Time the scalp entry, not just the direction**
As a trader who already knows *which* coin to watch (it cleared the momentum filter), I want to drill into a faster, shorter-timeframe momentum reading for that one coin, so that I can time the actual entry rather than just knowing the coin is "in favor" on a multi-day basis.

**US-5 — Know which leg of the bull run I'm in**
As a trader who wants to be positioned ahead of each leg of the cycle rather than reacting after the fact, I want the board to reflect which leg of the current bull run we're likely in, based on macro liquidity conditions, so that I can judge whether the current setup is a "get in" moment or a "leg is aging" moment.

**US-6 — Avoid chasing a leg that's already rotated elsewhere**
As a trader who has been burned by holding a coin whose narrative lost attention mid-leg, I want to see which sector or narrative currently has the most mindshare, so that I can tell whether a coin's momentum reading is backed by real attention or is a straggler about to lag a rotation.

**US-7 — See confidence, not a false single verdict**
As a trader who sizes positions based on conviction rather than a single "buy" signal, I want the board to show how well the different signals (momentum, trend, leg timing, narrative attention) agree or disagree with each other for a given coin, so that I can size a position with an honest sense of how much the evidence actually lines up.

**US-8 — Rank the whole watchlist head-to-head, not just pass/fail** *(added after initial plan review)*
As a trader who wants to know not just which coins clear the momentum filter but which are actually winning against each other, I want a single chart showing every watchlist coin's performance normalized to the same starting point, with a toggle to switch between shorter and longer lookback windows, so that I can visually rank who's outperforming over whichever horizon I care about right now.

**US-9 — Zoom the whole board in or out together** *(added mid-VALIDATE)*
As a trader who wants to move from a broad multi-day read down to a fine-grained entry-timing read without losing side-by-side comparability, I want one control that switches every coin panel's chart to the same timeframe at once — from 15-minute up through weekly — so that I can scan the whole watchlist at whichever granularity matters right now, not just the fixed daily view.

**US-10 — Zoom the drill-down chart itself, not just read a fixed scalp number** *(added mid-VALIDATE)*
As a trader deciding on scalp entry timing, I want the drill-down view's own chart to move across the same range of timeframes rather than being locked to one fixed interval, so that I can zoom in and out while I actually decide on the entry, not just read a single pre-picked reading.

**US-11 — Know who's winning across timeframes without toggling back and forth** *(added mid-VALIDATE)*
As a trader scanning the whole board, I want each coin's panel to show its percentage gain at every timeframe (15-minute through weekly) side by side, so that I can immediately see which coins are winning short-term versus long-term without switching the chart's timeframe back and forth one at a time.

## What The User Wants (Behavioral Outcomes)

- For every coin on the user's watchlist, the board shows, at a glance: whether the coin currently qualifies as "in momentum" against the active benchmark, its trend state, and a rough confidence read combining the available signals.
- "In momentum" is a pass/fail state driven by two timeframes at once — a coin only counts as in the user's favor when both hold true together, not when just one does.
- The benchmark a coin is measured against is not fixed — it reflects which phase of the cycle the market is in (BTC-led early in a leg vs. HYPE once rotation into alts is confirmed), and the board makes clear which benchmark is currently active and why.
- The board is a single page. Every watchlist coin gets its own small chart panel, and all panels use the same visual scale/format so coins can be scanned and compared side by side rather than opened one at a time.
- Each coin's panel shows enough on its own to answer "is this coin trending, and is it in momentum" without leaving the page.
- From any coin's panel, the user can drill down to a faster view of that single coin to judge a near-term entry — this is a secondary, on-demand view, not something cluttering the overview grid.
- Separately from individual coins, the board surfaces two pieces of market-wide context that inform how much weight to put on any single coin's reading: (a) which leg of the bull run the market is likely in right now, derived from macro liquidity conditions, and (b) which narrative/sector currently has the most attention, including newly emerging ones the user didn't think to add themselves.
- These two pieces of context are not separate reports the user has to go read elsewhere — they inform the confidence shown per coin on the same board (e.g., a coin passing the momentum filter but belonging to a narrative that's lost attention should visibly read as lower-confidence, not identical to a coin whose narrative currently has the spotlight).
- If any indicator can't be computed reliably — not enough history yet, a data source failed, or a benchmark itself is too new to have the history needed — the board says so plainly (an explicit "not enough data" / "unavailable" state) rather than showing a number that looks normal but isn't trustworthy.
- Nothing on the board collapses all of this into one single buy/sell verdict. The point is to show the trader where the signals agree and where they disagree, so sizing decisions reflect actual conviction.
- Separately from the per-coin board, the user can see all watchlist coins on one shared comparison chart, each normalized to percentage change from the same starting point, so relative winners and laggards are visible directly against each other rather than inferred by scanning individual panels. A timeframe toggle lets the user re-normalize to a shorter or longer window without leaving the view. This chart shows watchlist coins only — the active benchmark is not plotted on it (benchmark comparison already lives in the per-coin momentum filter).
- One global timeframe control sits above the screener board and switches every coin panel's chart (price + trend line) to the selected interval at once — 15-minute, 1-hour, 4-hour, daily, or weekly — so the user can move the whole board from a short-term read to a long-term read with one action, not one panel at a time.
- This display toggle only changes what's drawn. It never changes which coins pass or fail the momentum filter — that stays computed from real daily and weekly readings regardless of which timeframe the chart is currently showing, so a coin can display on a 15-minute chart while its PASS/FAIL badge still reflects the daily+weekly rule.
- The trend line reads consistently at every zoom level: it's always a 60-bar average of whichever timeframe is currently on screen (60 daily bars on the daily view, 60 weekly bars on the weekly view, and so on), not a fixed 60-calendar-day window pinned to one interval.
- The drill-down view's own chart is not locked to a single fixed interval either — it supports the same short-to-long timeframe range as the board, so the user can zoom in and out while actually deciding on an entry. The faster scalp-timing reading itself stays clearly labeled with its own timeframe so it's never confused with whichever timeframe the chart happens to be zoomed to at that moment.
- Each coin's panel also shows its percentage gain at every one of the five timeframes at once — 15m, 1h, 4h, 1D, and 1W side by side — not only whichever single interval the chart is currently zoomed to, so the user can tell at a glance which coins are winning short-term versus long-term without toggling through each timeframe individually. A timeframe with too little history for that coin shows as explicitly unavailable in that one slot, never a zero or a blank that looks like a real 0% reading.

## Flow / State Diagram

```
                    ┌─────────────────────────────┐
                    │   User's Watchlist (coins)   │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
              ┌──────────────────────────────────────────┐
              │        Per-coin signal computation        │
              │  ------------------------------------------│
              │  Daily RSI   Weekly RSI   60-day trend line│
              └───────┬───────────┬────────────┬───────────┘
                      │           │            │
                      ▼           ▼            ▼
              ┌─────────────────────────────────────┐
              │   Momentum Filter (per coin, per      │
              │   active benchmark)                   │
              │   PASS only if:                       │
              │     daily reading > midline   AND     │
              │     weekly reading > midline          │
              │   else -> "not in favor" (or          │
              │   "unavailable" if data insufficient) │
              └───────────────┬───────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────────┐
        │   Market-wide context (computed once,           │
        │   applied to every coin on the board)            │
        │  ------------------------------------------------│
        │  Which BENCHMARK is active right now?             │
        │    BTC-dominant / early-leg  -> benchmark = BTC   │
        │    rotation-into-alts confirmed -> benchmark=HYPE │
        │                                                    │
        │  Which LEG of the bull run are we likely in?      │
        │    derived from macro liquidity conditions         │
        │                                                    │
        │  Which NARRATIVE/sector has mindshare right now?  │
        │    seed categories (user-defined) + auto-flagged   │
        │    emerging categories                              │
        └─────────────────────┬─────────────────────────────┘
                              │  (feeds confidence, not a
                              │   separate screen)
                              ▼
              ┌───────────────────────────────────────────┐
              │        SCREENER BOARD (single page)         │
              │  ------------------------------------------- │
              │  [Coin A panel]  [Coin B panel]  [Coin C]... │
              │   price+trend      price+trend    price+... │
              │   daily/weekly     daily/weekly   daily/... │
              │   momentum: PASS   momentum: FAIL  UNAVAIL. │
              │   confidence: hi   confidence: lo  confid:? │
              │   (narrative:      (narrative:     (bench.  │
              │    in-focus)        rotated-out)    too new)│
              └───────────────────┬───────────────────────┘
                                  │  user selects one coin
                                  │  that passed the filter
                                  ▼
              ┌───────────────────────────────────────────┐
              │     DRILL-DOWN: single-coin scalp view       │
              │  Fast (short-interval) momentum reading      │
              │  used to time the actual entry                │
              └───────────────────────────────────────────┘

  Branches / degraded states shown ON the board itself, never hidden:
   - Insufficient history for a coin or the active benchmark -> "unavailable",
     not zero/blank/wrong.
   - Narrative/mindshare source fails to fetch -> narrative shown as
     "unavailable" for that coin, confidence read degrades accordingly
     rather than silently omitting the narrative factor.
   - Coin passes momentum filter but its narrative has rotated out ->
     shown as lower confidence alongside the PASS, not overridden into a FAIL.

  A second, complementary view (not shown above — sits alongside the board, not
  inside the PASS/FAIL flow):

    SCREENER BOARD (per-coin panels)          RELATIVE PERFORMANCE CHART
    watchlist coins ─────────────────►        watchlist coins, all normalized
    each measured against the                 to % change from the same start
    active benchmark, PASS/FAIL                point, on one shared chart —
    per coin                                   ranked against EACH OTHER, not
                                                the benchmark. Timeframe toggle
                                                (short <-> long) re-normalizes.
                                                No benchmark line on this chart.
```

## Acceptance Criteria (Testable Outcomes)

**AC-1 — Weekly momentum reading reflects true weekly price action.**
The weekly momentum reading for a coin is calculated from actual weekly closing prices, not from averaging or resampling a daily reading — so a coin's weekly signal reflects the weekly candle structure, not a daily-derived approximation.
proven by: weekly-momentum-from-resampled-closes
strategy: Fully-Automated

**AC-2 — "In momentum" requires both timeframes to agree, including edge cases.**
A coin is marked "in favor" only when its daily reading and its weekly reading both clear the midline threshold at the same time. A reading sitting exactly on the threshold, or a reading that can't be computed yet (not enough history), never silently counts as a pass.
proven by: dual-timeframe-filter-boundary-logic
strategy: Fully-Automated

**AC-3 — The active benchmark is visibly correct for the market regime.**
Every coin's momentum reading is measured against the correct benchmark for the current regime — BTC while BTC is dominant / early in a leg, switching to HYPE once rotation into alts is confirmed for that leg — and the board makes clear which benchmark is currently in effect.
proven by: regime-dependent-benchmark-switch
strategy: Fully-Automated

**AC-4 — Every watchlist coin appears as its own comparable panel on one page.**
The screener board renders one small chart panel per watchlist coin, all on a single page, each showing price, the 60-day trend line, and both momentum readings, in a shared visual format so coins can be compared side by side.
proven by: screener-board-grid-data-binding + screener-board-visual-layout
strategy: Fully-Automated (data binding) / Agent-Probe (visual layout correctness)

**AC-5 — Each panel's values belong to the right coin.**
For every panel on the board, the price, trend line, and momentum values shown are the correct values for that specific coin — no panel shows another coin's data due to a mismatch.
proven by: screener-board-grid-data-binding
strategy: Fully-Automated

**AC-6 — The trend line reflects the 60-day simple average.**
Each coin's panel shows a trend line computed as a 60-day simple moving average, giving the user a stable, complementary read on trend direction alongside the momentum readings.
proven by: screener-board-grid-data-binding
strategy: Fully-Automated

**AC-7 — Drilling into a coin surfaces a faster entry-timing read.**
From any coin's panel, the user can open a focused, faster-interval momentum view for that single coin, intended for timing a near-term scalp entry once the coin has already cleared the daily/weekly momentum filter. This view is reached on demand and does not appear as its own tile in the overview grid.
proven by: screener-board-grid-data-binding
strategy: Fully-Automated

**AC-8 — The board reflects which leg of the bull run is likely active.**
The board surfaces a current best-estimate of which of the roughly three legs of the bull run the market is in, derived from macro liquidity conditions, and this estimate uses the correct underlying calculation for the date range in question (see AC-9).
proven by: leg-boundary-composite-variant-selection-by-date
strategy: Fully-Automated

**AC-9 — The correct liquidity calculation is used for the correct period.**
When the leg-timing estimate is derived or backtested for a given date, the system selects the liquidity calculation that is actually valid for that date range (the full multi-part composite only where every part of it has data available; a reduced version otherwise) rather than applying one formula uniformly across periods where its inputs don't exist yet.
proven by: leg-boundary-composite-variant-selection-by-date
strategy: Fully-Automated

**AC-10 — A coin's narrative/mindshare standing is visible on its panel.**
Each coin's panel (or its confidence read) reflects whether the coin's sector/narrative currently has market attention, so a coin that is technically "in momentum" but belongs to a narrative that has rotated out of focus reads as lower confidence rather than identical to a coin whose narrative is currently in focus.
proven by: narrative-fetch-failure-degrades-explicitly
strategy: Fully-Automated

**AC-11 — A narrative data failure degrades honestly instead of silently.**
If the source used to determine narrative/mindshare fails to return data for a coin, the board shows that narrative factor as explicitly unavailable and reflects that in the coin's confidence read — it never shows stale data, a blank that looks intentional, or a confidence score computed as if the narrative factor were neutral/zero.
proven by: narrative-fetch-failure-degrades-explicitly
strategy: Fully-Automated

**AC-12 — Insufficient history never silently produces a number.**
Any indicator — momentum reading, trend line, or a benchmark switched to that doesn't yet have enough of its own price history (e.g., right after its listing) — that lacks the data it needs shows an explicit "not enough data" / "unavailable" state. It never shows a zero, a blank cell that looks like a real reading, or a value computed from a silently shortened lookback window.
proven by: dual-timeframe-filter-boundary-logic
strategy: Fully-Automated

**AC-13 — The board shows agreement/disagreement, not one verdict.**
For a given coin, the board displays the individual signal states (momentum pass/fail, trend direction, leg-timing context, narrative standing) rather than collapsing them into a single directional call — so two coins that both "pass momentum" but disagree on narrative or trend are visibly distinguishable from each other.
proven by: screener-board-grid-data-binding
strategy: Fully-Automated

**AC-14 — All watchlist coins appear on one shared, normalized comparison chart.**
Every coin on the watchlist is plotted as its own line on a single chart, each normalized to percentage change from the same starting point, so coins can be ranked against each other directly rather than inferred from separate panels.
proven by: relative-performance-chart-normalization
strategy: Fully-Automated

**AC-15 — The timeframe toggle re-normalizes correctly.**
Switching the chart's timeframe (shorter vs. longer lookback) re-normalizes every coin's line to percentage change from that window's own starting point, not the previously selected window's start — and a coin without enough history for the selected window shows as explicitly unavailable for that window rather than a wrong or truncated line.
proven by: relative-performance-chart-normalization
strategy: Fully-Automated

**AC-16 — The global board timeframe toggle switches every panel together, without touching PASS/FAIL.** *(Amendment 2)*
Switching the board-wide timeframe control (15m / 1h / 4h / 1D / 1W) re-renders every coin panel's price chart and trend line at the newly selected interval. The momentum PASS/FAIL badge for every coin stays exactly as it was before the switch, since it is always computed from real daily and weekly readings regardless of which interval the chart is currently displaying.
proven by: board-timeframe-toggle-global-switch
strategy: Fully-Automated

**AC-17 — The trend line re-scales to the active timeframe.** *(Amendment 2)*
The trend line shown on a coin's panel is always a 60-bar average of whichever timeframe the board is currently displaying — verifiably different (and correctly calculated) at, at minimum, two different timeframes for the same coin — rather than staying pinned to a fixed 60-calendar-day window regardless of the active interval.
proven by: sma-period-rescales-with-timeframe
strategy: Fully-Automated

**AC-18 — The drill-down chart supports the same timeframe range as the board.** *(Amendment 2)*
The drill-down view's own chart can be switched across the same 15m / 1h / 4h / 1D / 1W range, re-rendering that single coin's chart at the newly selected interval. The scalp-entry reading itself remains labeled with its own explicit timeframe at all times, so it is never visually mistaken for whatever interval the chart is currently zoomed to.
proven by: drilldown-chart-timeframe-range
strategy: Fully-Automated

**AC-19 — A coin without history at a newly selected timeframe shows as unavailable, not wrong.** *(Amendment 2)*
If a coin lacks enough cached history at a timeframe the user switches to (e.g., a thinly-listed coin viewed on 15-minute bars), the board shows that coin's panel as explicitly unavailable for that timeframe rather than a truncated, wrong, or default-substituted chart — consistent with the project's existing insufficient-history rule (AC-12).
proven by: board-timeframe-toggle-insufficient-history
strategy: Fully-Automated

**AC-20 — Each panel shows % gain across all timeframes at once, not just the active chart interval.** *(Amendment 2)*
Every coin's panel displays its percentage change at every one of the five timeframes (15m, 1h, 4h, 1D, 1W) simultaneously, independent of which single timeframe the panel's chart is currently zoomed to — so the user can compare short-term versus long-term winners across the whole watchlist at a glance. A timeframe the coin lacks sufficient history for shows as explicitly unavailable in that slot only, never a 0% or omitted figure that could be mistaken for a real reading.
proven by: per-coin-multi-timeframe-gain-readout
strategy: Fully-Automated

## Out Of Scope

- Scanning the full market for candidates — the screener only ever evaluates coins the user has already added to their own watchlist; there is no discovery/auto-add of new coins to watch.
- Automated trade execution, order placement, or any direct exchange connectivity — this is a decision-support board only.
- A single automated buy/sell recommendation or alert — the tool shows signal agreement/disagreement for the user to size positions with; it does not issue calls.
- Backtested historical validation of the narrative/mindshare layer against the 2017 or 2020-21 cycles — no free historical data path exists for this layer; it is built and validated by live observation going forward only (user-confirmed, see Open Questions).
- Portfolio-level position sizing math or risk management (stop-loss placement, position sizing formulas) — the board informs sizing confidence; it does not calculate position size.
- Any benchmark or coin outside the user's own watchlist and the two named benchmarks (BTC, HYPE).
- Backtesting or leg-detection for any bull cycle other than 2017 and 2020-21 (these two are the validation baseline; no other historical cycle is in scope).

## Constraints

- **Universe is the user's manually maintained watchlist**, not a market-wide scan. Adding/removing coins from the watchlist is a manual action by the user.
- **Momentum filter is fixed as dual-timeframe**: a coin only counts as "in favor" when its daily reading AND its weekly reading are both above the midline threshold at the same time. Neither timeframe alone is sufficient.
- **Trend layer is a 60-day simple average**, not an exponential or weighted average — this is a settled choice, not a tunable default at this stage.
- **Scalp-entry timing uses a faster, shorter-interval reading** (roughly a 4-hour cadence) and is explicitly a drill-down from a coin that has already passed the daily/weekly filter — it is not shown as a standalone tile on the main board.
- **The board must be a single page** showing every watchlist coin as its own small panel (a "small multiples" layout) so coins are visually comparable against each other, not a list of links to individual full-size charts.
- **Benchmark selection is regime-dependent, not fixed**: BTC while BTC-dominant/early in a leg, HYPE once rotation into alts is confirmed for that leg. This switch logic is a settled design decision, not open for re-litigation in this document.
- **Leg-boundary derivation must be backtested against the 2017 and 2020-21 BTC cycles before any live leg-detection rule is trusted going forward**, using macro liquidity as the underlying signal.
- **Narrative/mindshare tracking combines a user-defined seed list of categories** (e.g., AI, RWA, L2s, memecoins) **with system auto-flagging of emerging categories**, sourced only from free-tier data sources.
- **"Numbers are never silently wrong" (project-wide constraint).** Any indicator with insufficient history, a failed data fetch, or a stale cache must show an explicit "insufficient" / "unavailable" state — never a NaN rendered as if valid, a zero-fill, or a result computed from a silently truncated lookback window. This applies to every indicator on the board, including a benchmark that itself lacks enough history right after being switched to.
- **Overall philosophy**: the board's purpose is to produce a confidence level that informs position sizing, not a single directional call. Signal agreement and disagreement must both be visible — the system must not resolve disagreement into one hidden verdict.
- **The relative-performance ("spaghetti") chart is watchlist-coins-only** — the active benchmark is deliberately not plotted on it (user-confirmed); it ranks watchlist coins against each other, not against BTC/HYPE. Benchmark comparison stays the job of the per-coin momentum filter.
- **The chart's timeframe is a selectable toggle** (e.g. short/medium/long lookback windows), not a fixed single window — each selection re-normalizes every coin's line to % change from that window's own start.
- **The board's per-coin timeframe control is global, not per-panel** *(Amendment 2, user-confirmed)* — one control switches every coin's chart together (15m / 1h / 4h / 1D / 1W), not an independent toggle per panel.
- **The board-wide timeframe toggle changes display only** *(Amendment 2)* — it never changes the dual-timeframe daily+weekly momentum PASS/FAIL determination (still governed solely by Constraint "Momentum filter is fixed as dual-timeframe" above), and it never changes the 4h cadence used for the scalp-entry reading itself, which stays its own separately-labeled value even while the drill-down chart is zoomed to a different interval.
- **The trend line's 60-bar window re-scales with the active timeframe** *(Amendment 2, resolved directly at request time — flagged for override)* — 60 bars of whichever interval is on screen, not a fixed 60-calendar-day window pinned to daily. This keeps the trend read consistent at every zoom level; if a fixed calendar window was actually intended instead, this is the one line to correct.
- **The per-panel multi-timeframe % gain readout is separate from the relative-performance chart** *(Amendment 2)* — the readout shows one coin's own gain across all five timeframes at once (a per-coin scorecard); the relative-performance chart (Amendment 1) shows all coins ranked against each other at one selected timeframe at a time (a cross-coin ranking view). Both are kept because they answer different questions — neither replaces the other.

## Open Questions

**OQ-1 — Owner: user. What standard should the 2017 / 2020-21 leg-boundary backtest be held to, given the full liquidity calculation can't be reconstructed that far back?**
The full macro-liquidity composite the user wants to use for leg-timing has a data component (spot-BTC-ETF flows) that simply did not exist before US spot ETFs launched in January 2024. That means the 2017 and 2020-21 cycles — the two cycles this project is supposed to backtest leg-boundaries against — can only be tested using a reduced version of the liquidity calculation (net liquidity, and possibly a dollar-strength measure and BTC's market-share trend), not the full formula the user described. One additional input to that reduced version (a stablecoin-supply history) has enough free historical depth to check directly but that check has not yet been done.
**Resolved:** user confirmed the recommended resolution. The 2017/2020-21 leg-boundary backtest runs on the reduced liquidity calculation; the full six-part composite is treated as validated only from 2024 onward, once live spot-ETF data exists.

**OQ-2 — Owner: user. How should the narrative/mindshare layer be treated, given it has no historical data path at all for backtesting?**
Unlike the liquidity gap above (which at least has a reduced fallback), the narrative/mindshare layer has no way to be checked against the 2017 or 2020-21 cycles using any free source under consideration — none of them retain usable historical attention data that far back, and one of them (a commonly used free search-trend tool) has effectively been discontinued as of April 2025. This means the narrative layer cannot be backtest-validated at all, only observed once it's running live.
**Resolved:** user confirmed live-only. The narrative/mindshare layer is built and runs live going forward, explicitly without historical backtested validation; this is not a gap to close later, it's the accepted shape of this layer.

## Background / Research Findings

- **User's original request, in their own words:** wants to screen for outperformers against BTC or HYPE (coins need to show momentum on both weekly and daily RSI — both above 50 — to count as "in their favor"); uses 4h RSI to time scalp entries once a coin clears that filter; uses a 60-day simple moving average as a complementary trend indicator; wants everything for the watchlist shown visually on one page (a grid of small charts, each with its indicators) so coins can be compared against each other at a glance; times entries into each of the ~3 legs of a BTC bull run using macro liquidity; within each leg wants to be sure they're positioned in whichever narrative/sector actually has mindshare that period, since some coins lag a leg due to rotation elsewhere.
- **Locked design decisions from prior clarification** (carried into this SPEC as settled Constraints/Behavioral Outcomes, not re-opened here): watchlist-only universe; regime-dependent BTC/HYPE benchmark switch; dual-timeframe (daily+weekly) momentum filter; 60-day simple moving average trend layer; faster-interval scalp-entry drill-down (not a main-board tile); single-page small-multiples screener board; leg-boundary derivation backtested on 2017 and 2020-21 before going live; narrative layer combining a user-defined seed list with system auto-flagging via free data sources; project-wide "confidence, not a single call" philosophy.
- **Macro-liquidity backtest gap (drives OQ-1):** the full six-part liquidity composite the user wants (net liquidity, stablecoin supply, dollar index, a Fed reverse-repo measure, spot-ETF flows, and BTC's market-share trend) can only be fully reconstructed from January 11, 2024 onward, because the spot-ETF-flow component didn't exist before US spot ETFs launched. The 2017 and 2020-21 cycles can only be tested against a reduced version (net liquidity, and possibly the dollar-strength and market-share components) — one further input's historical depth (a stablecoin-supply data source) hasn't been directly checked yet and needs a probe before it can be counted on.
- **Narrative/mindshare historical gap (drives OQ-2):** none of the free sources chosen for tracking sector/narrative attention retain usable history back to 2017 or 2020-21. One commonly used free search-trend tool has been unmaintained/effectively discontinued since April 2025; a commonly used free-tier social-discussion source has had no historical query capability since 2023; a commonly used current-trending-coins source is current-only by nature. This is a harder gap than the liquidity one — there is no reduced fallback, only "no historical validation is possible for this layer."
- **Secondary, non-blocking finding (not an open question — a settled research recommendation for later phases):** a widely used technical-indicator calculation library the project might otherwise default to has an unresolved maintainer-trust concern (its public package history was wiped during a maintainer transition). A community-maintained fork exists specifically because of this concern and should be treated as the default going forward for computing the indicators this SPEC describes. This does not require user resolution — it is background for whoever picks the implementation approach next.
- **Testing-strategy caveat:** a full, formal test-scenario discovery against this repo's test-context router was not run during RESEARCH, because this repo's overall testing strategy (which test runner to standardize on) is itself an explicitly deferred, still-open decision. The `proven by:` references in this SPEC's Acceptance Criteria are grounded in RESEARCH's preliminary test-gap analysis instead — six specific gaps were already identified and tiered as Fully-Automated (five of them) or a Fully-Automated/Agent-Probe split (the sixth, covering the screener board's data correctness and its visual layout separately). Full formal scenario enumeration against a chosen test runner remains pending until that testing-strategy decision is made in a later phase.
- **Project-wide constraint carried in from existing context** (not new to this feature): "numbers are never silently wrong" — any indicator with insufficient data, a failed fetch, or a stale cache must show an explicit insufficient/unavailable state, never a NaN, a zero-fill, or a silently truncated lookback. This SPEC applies that rule directly to the narrative layer's failure mode and to any indicator (including a newly switched-to benchmark) that doesn't yet have enough of its own history.

## Open Questions Status

`## Open Questions` is **resolved** — both OQ-1 and OQ-2 were confirmed by the user against the recommended resolution (see each item above). No unresolved items remain.

## Amendment Log

**Amendment 1 (post-PLAN review, 17-09-26):** user requested a relative-performance ("spaghetti") comparison chart while reviewing the written PLAN, before EXECUTE began. Added US-8, two Behavioral Outcomes bullets, a second flow diagram, AC-14/AC-15, and two Constraints bullets. Two design questions were resolved directly with the user at request time (not left open): timeframe is a selectable toggle (not a fixed window or multiple side-by-side charts), and the chart is watchlist-coins-only (the benchmark is not plotted on it). This amendment did not touch any of the original 13 acceptance criteria, the resolved OQ-1/OQ-2, or any other locked decision — it is a pure addition. Per this repo's Frozen Document Rules, a SPEC is normally locked once INNOVATE/PLAN begins; this amendment is made anyway because EXECUTE has not started and the user caught this during their own PLAN review, which is a legitimate, explicit amendment rather than a silently-discovered gap.

**Amendment 2 (mid-VALIDATE, 18-09-26):** user requested that the main screener board's per-coin charts be switchable across a full short-to-long timeframe range — 15m / 1h / 4h / daily / weekly — via one global control (not per-panel), plus the same range on the drill-down view's own chart (previously fixed to a single 4h scalp read), plus a per-coin % gain readout across all five timeframes at once so winners are visible without toggling. Added US-9, US-10, US-11, five Behavioral Outcomes bullets, AC-16 through AC-20, and four Constraints bullets. One design question was resolved directly with the user at request time (global toggle, not per-panel — user explicitly chose "1 toggle on the main screener for all"). One further design decision was made without a separate round-trip and is flagged for the user to override if wrong: the 60-bar trend line re-scales to the active timeframe (60 bars of whatever interval is on screen) rather than staying pinned to a fixed 60-calendar-day window — this was chosen because a fixed-calendar SMA would mean something different (and mostly meaningless) on a 15-minute chart than on a weekly one, so a period-based window was treated as the only design that stays useful across the whole range. This amendment does not touch the dual-timeframe daily+weekly momentum filter (AC-2 — still the sole PASS/FAIL determinant, explicitly reaffirmed as unaffected by this display toggle) or any other previously locked decision.

**Status:** DONE
**Summary:** SPEC written in full per the required section order with one ASCII flow diagram, 20 acceptance criteria each carrying `proven by:`/`strategy:` (13 original + 2 from Amendment 1 + 5 from Amendment 2), and both RESEARCH-driven gaps surfaced as Open Questions, then resolved by explicit user confirmation.
**PHASE_COMPLETE: SPEC** — `process/general-plans/active/momentum-screener_17-09-26/momentum-screener_SPEC_17-09-26.md` written, locked, and amended twice. PLAN must be updated to match (see Amendment 2) before VALIDATE re-runs.
