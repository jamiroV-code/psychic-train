---
name: spec:personal-tracker-realignment
description: "Realign my_site from a confidence/verdict screener to a personal-use data-display tracker: slimmer screener with RSI, groups, 30-coin cap and a spaghetti comparison chart, BTC leg strip, lean 15-minute refresh, LSE equities page, verdict deletions and other-page label audits. Narrative work split out to narrative-baskets SPEC; documentation work moved to the master-planner-recovery plan (split applied 02-10-26)"
date: 02-10-26
feature: general-plans
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Personal Tracker Realignment — SPEC (product direction + screener)

**TL;DR:** my_site stops telling the user what to think. It becomes a personal, Tailscale-only dashboard that shows clean data (price, % change, RSI, BTC legs) so the user draws their own conclusions. All verdict-style output (confidence badges, bullish/bearish tags, scalp PASS/FAIL, "triggered/confirmed" flags) is deleted, not hidden. The screener gets coin groups, an RSI row, a 30-coin cap and a "spaghetti" chart comparing every coin's % change against BTC and HYPE. Equities come in via LSE on their own page where the user picks the tickers. **This SPEC was split on 02-10-26:** all /narrative requirements now live in `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets_SPEC_02-10-26.md`, and all documentation/process requirements moved to `process/general-plans/active/master-planner-recovery_02-10-26/` (Gate 1 housekeeping plan). IDs are unchanged; see `## Split note`.

Status key: **Locked** = user decided, build to it. **SUPERSEDED** = kept for traceability, no longer a requirement. **MOVED** = requirement now lives in another file (see `## Split note`). **(A1)** / **(A2)** / **(A5)** mark text added by Amendments 1, 2 and the 02-10-26 split.

Cross-link: narrative requirements are in `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets_SPEC_02-10-26.md`.

---

## Split note

The SPEC grew to 32 active criteria. On 02-10-26 the user approved splitting it. No ID was renumbered; every old ID keeps its number. Moved items stay in this file only as a one-line "MOVED" marker.

| Old ID range | New home |
|---|---|
| US-1, 2, 3, 4, 7, 8, 9, 11, 12, 14 | this file |
| US-5 (superseded) | this file |
| US-5b, 6, 13, 15, 16, 17, 18, 19 | narrative-baskets SPEC |
| US-10 | MOVED to `process/general-plans/active/master-planner-recovery_02-10-26/` (Gate 1 housekeeping plan) |
| Outcomes 1, 2, 3, 4, 8, 9, 10, 11, 12, 13, 14, 17, 18 | this file |
| Outcome 5 (superseded) | this file |
| Outcomes 6, 7, 15, 16, 19, 20, 21, 22, 23 | narrative-baskets SPEC |
| AC-1 to AC-8, AC-12 to AC-17, AC-18 (code part only), AC-21, AC-22, AC-23, AC-26 | this file |
| AC-10 (superseded) | this file |
| AC-9, AC-11, AC-24, AC-25, AC-27 to AC-33 | narrative-baskets SPEC |
| AC-18 (documentation part), AC-19, AC-20 | MOVED to `process/general-plans/active/master-planner-recovery_02-10-26/` (Gate 1 housekeeping plan) |
| OQ-1 to OQ-9 | this file (all resolved) |
| OQ-10 to OQ-17 | narrative-baskets SPEC |

Documentation/process work (North Star rewrite, `all-context.md` slimming, current-state doc, task registry, archive index, MASTER-PLAN) is removed from this product SPEC: **moved to process/general-plans/active/master-planner-recovery_02-10-26/ (Gate 1 housekeeping plan).** Judgement call to confirm: AC-18 is split, its documentation half moved and its code/comment half stays here.

---

## Summary

The original product goal was "turn separate signals into one confidence level that drives position sizing." The user replaced that goal. The app is now a **personal-use-only tracking system** whose job is to **show data as clearly as possible** so the user reaches their own market conclusions. It must not compute or display any bullish/bearish call, confidence badge, signal-agreement, state/flag label or trust weight. "Open to other users later" is dropped, so redistribution/licensing stops being a design constraint (Tailscale-only access stays). The top-priority change is the screener: keep the small coin boxes, remove every verdict, add an RSI under each coin, cap the board at 30 coins, and let the user manage coins and named groups from the UI. A BTC price-history strip with shaded legs sits at the top, and one spaghetti chart shows every coin's % change from the start of the selected timeframe against BTC and HYPE reference lines (visual comparison only). The narrative tag on coin boxes is deferred. Equities come in through LSE data on a separate page whose tickers the user adds. The /narrative redesign is a separate SPEC; the documentation rewrite is a separate plan.

## User Stories / Jobs To Be Done

- **US-1 (Locked) Clean data, no verdicts.** As a solo trader, I want every page to show numbers and charts only, so that my conclusions are mine and not nudged by a computed label.
- **US-2 (Locked) Fast, readable coin boxes.** When I open the screener, I want each coin box to show its price line, % change and RSI for the timeframe I picked, so I can scan many coins in seconds.
- **US-3 (Locked) My own coin groups.** I want to create, rename and delete named groups, drag coins between and within groups, and sort each group by name, % change or RSI, so the board matches how I think about the market.
- **US-4 (Locked) Manage coins in the app.** I want to add and remove coins from the UI, so I never edit config files.
- **US-5 (SUPERSEDED) Narrative tags on coin boxes.** Deferred until /narrative data shows whether trends give an actionable edge. (Narrative editing part carried by US-5b in the narrative SPEC.)
- **US-5b MOVED** to the narrative-baskets SPEC.
- **US-6 MOVED** to the narrative-baskets SPEC.
- **US-7 (Locked) Where are we in the cycle.** I want a BTC price-history strip at the top of the screener with legs shaded and leg-boundary dates marked, so I see where we may be in history.
- **US-8 (Locked) Fresh without babysitting.** I want coin data to refresh when I open the page and it is more than 15 minutes old, so I need no background job running.
- **US-9 (Locked) Equities in their own place, my tickers.** I want equities (LSE data) on a separate page where I add the tickers I care about with an Add button, so they never mix into my crypto groups and I am not stuck with a preset list.
- **US-10 MOVED** to `process/general-plans/active/master-planner-recovery_02-10-26/` (Gate 1 housekeeping plan).
- **US-11 (Locked) See who beats HYPE and BTC at a glance.** I want one chart with a line per coin showing % change from the start of my selected timeframe, with BTC and HYPE as reference lines, so I can see by eye which coins are ahead of or behind HYPE and BTC.
- **US-12 (Locked) Declutter the comparison chart.** I want to switch each coin's line off and on individually and have that choice remembered.
- **US-13 MOVED** to the narrative-baskets SPEC.
- **US-14 (Locked, A2) Hard cap of 30 coins.** I want the screener to hold at most 30 coins and refuse a 31st with a clear message, so the board, the refresh on page load and the spaghetti chart stay fast and readable.
- **US-15 to US-19 MOVED** to the narrative-baskets SPEC.

## What The User Wants (Behavioral Outcomes)

1. **No verdicts anywhere.** No page shows a confidence badge, signal agreement, trend up/down tag, momentum PASS/FAIL tag, scalp PASS/FAIL view, leg tag, narrative state label ("in-focus", "rotated-out", etc.), `triggered`/`confirmed` flag, or `trust_weight`.
2. **Screener coin box (Locked).** Same small-box look as today. Contains: coin name, price line chart, % change for the active timeframe, and an RSI value (period 14, Wilder smoothing) beneath it. The timeframe switch (15m / 1h / 4h / 1d / 1w) drives price line, % change and RSI together.
3. **Coin management (Locked).** Add and remove coins from the screener UI.
4. **Groups (Locked).** User-named groups: create, rename, delete. Drag coins between groups and reorder within a group. Each group has a quick sort: by name, % change, or RSI.
5. **Narrative tags on coin boxes (SUPERSEDED, deferred).** Coin boxes carry no narrative tag in this scope.
6. **MOVED** to the narrative-baskets SPEC (narrative editor).
7. **MOVED** to the narrative-baskets SPEC (/narrative raw page).
8. **BTC leg strip (Locked).** At the top of the screener: BTC price history, leg periods shaded, leg-boundary dates marked. The existing leg-boundary maths feeds it as plain data. The per-coin leg tag is deleted.
9. **Refresh (Locked).** On page load, any coin whose data is older than 15 minutes is refreshed. No background job is required for this.
10. **Lean data (Locked, A2).** Keep about 2 days (~200 bars) of 15m history per coin. Other timeframes keep only what their RSI and price line need. Anything fetched or stored that no page displays is removed. **Hard cap: the crypto screener holds NOT MORE THAN 30 coins at any moment; refresh sizing, spaghetti chart, groups and tests all use 30.**
11. **Equities page (Locked).** A separate section/page showing LSE equity data with an "Add" button; the user picks the tickers (no preset list). Used under LSE's private-use terms.
12. **Other pages stay (Locked).** /regime, /narrative, /pairs, /onchain remain. Their data stays, including the /pairs significance banner and p-value ranking, the /regime composite liquidity index, and status/data-quality labels (onchain floor/ramp, pairs status banners). Only verdict-style outputs on the removed-list (outcome 1) go. What /narrative itself shows is governed by the narrative-baskets SPEC.
13. **Dropped (Locked).** The standalone charts/indicators page is not built; RSI on the screener replaces it.
14. **Spaghetti chart (Locked).** One chart, a line per coin, each showing % change from the start of the currently selected timeframe (each coin measured on its own window, anchored at 0%). BTC and HYPE appear as reference lines. All screener coins appear by default; each can be toggled off/on and the toggle state persists. A coin added appears automatically; a removed coin disappears. Switching timeframe re-anchors every line. Visual comparison only: no computed "outperforming" label or ranking text.
15. **MOVED** to the narrative-baskets SPEC (clean /narrative data).
16. **MOVED** to the narrative-baskets SPEC (pytrends fix and nightly archive guarantees).
17. **Scalp view removed (Locked).** Only the drill-down "Scalp PASS/FAIL" view is deleted (code, tests, docs). Drill-down price and RSI stay.
18. **30-coin cap (Locked, A2).** Adding a 31st coin to the crypto screener is refused with a clear message (for example "Screener is full: 30 coins maximum. Remove a coin to add another."); nothing is added and the board is unchanged. The cap applies to the crypto screener only; the LSE equities section is not capped. (Narrative interaction on coin removal: see narrative-baskets SPEC outcome 22 / AC-32.)
19. to 23. **MOVED** to the narrative-baskets SPEC.

## Flow / State Diagram

```
Open /screener
   |
   v
[BTC leg strip loads] ---- BTC history + shaded legs + boundary dates
   |
   v
[For each coin: data age > 15 min?]
   |-- yes --> refresh that coin (15m ~200 bars; other TFs minimal) --> render
   |-- no  --> render from stored data
   v
Spaghetti chart: one line per coin, % change from START of selected TF (0% anchor)
   BTC + HYPE = reference lines | per-coin toggle (persisted)
   coin added -> line appears | coin removed -> line gone | TF switch -> all re-anchor
   |
   v
Board: Group A | Group B | ... (user-named, drag to reorder / move)
  each coin box:  name | price line | % change(TF) | RSI14 Wilder(TF)   (no narrative tag)
   |
   +--> Timeframe switch (15m/1h/4h/1d/1w) --> price, %chg, RSI, spaghetti all follow
   +--> Group sort (name | %chg | RSI)
   +--> Add / remove coin  (31st coin --> refused, "30 coins maximum", board unchanged)
   |        (removal also updates narratives: see narrative-baskets SPEC AC-32)
   +--> Create / rename / delete group
   +--> Failure: data unavailable --> box says "no data" (never 0 or blank number)

/equities (LSE): [Add ticker] --> user-picked tickers listed; private-use note shown

Separate pages: /narrative (own SPEC) /regime /pairs /onchain /equities
Retired outputs: confidence, agreement, trend tag, momentum/scalp PASS/FAIL, leg tag,
                 narrative state flags, trust weight, narrative tag on coin boxes (deferred)
```

## Acceptance Criteria (Testable Outcomes)

Strategy tags: FA = Fully-Automated, HY = Hybrid, AP = Agent-Probe. Scenarios come from the existing test surfaces: pytest (`api/tests/{analytics,data,routers,scripts}`), vitest (`web/components/*/__tests__`, `web/lib/__tests__`), Playwright (`web/e2e/*.spec.ts`), plus the repo validators.

**Active criteria in this file: 19** (AC-1 to AC-8, AC-12 to AC-18, AC-21 to AC-23, AC-26), under the 20 cap. AC-10 is superseded. Moved IDs are listed at the end of this section.

**AC-1 (Locked) No verdict output in screener data.** The screener API response and page contain no confidence, leg_context, narrative_state, momentum state, trend direction, or narrative tag fields/labels.
- proven by: pytest contract test asserting absent fields; vitest render test; Playwright `screener.spec.ts` asserting no badge/tag elements. strategy: FA

**AC-2 (Locked, A5 narrowed) Screener verdict code is deleted, not hidden.** The screener-side deletion targets in the Impact Surface table (confidence badge, signal detail panel, momentum/trend state, drill-down scalp PASS/FAIL view, old relative-performance chart, narrative strip) no longer exist in source, tests or docs; no dead imports remain. (Narrative-side symbols such as `trust_weight` and the trigger logic are verified under narrative-baskets AC-11.)
- proven by: repo grep gate for removed screener symbols (ConfidenceBadge, SignalDetailPanel, NarrativeStrip, confidence badge module, momentum/trend state, scalp PASS/FAIL view) returning zero hits outside archived history; `tsc --noEmit` and full pytest/vitest green. strategy: FA

**AC-3 (Locked) Coin box content.** Each box shows price line, % change and RSI for the active timeframe; RSI uses period 14 with Wilder smoothing.
- proven by: pytest RSI calculation test against a known Wilder reference series; vitest box render; Playwright asserting RSI text present. strategy: FA

**AC-4 (Locked) Timeframe switch drives all three.** Switching 15m/1h/4h/1d/1w changes price line, % change and RSI together.
- proven by: Playwright switching each timeframe on seeded data and asserting all three values change per fixture. strategy: FA

**AC-5 (Locked) Insufficient data is explicit.** If a coin lacks enough bars for RSI, the box shows an explicit "no data/insufficient" state, never 0 or NaN.
- proven by: pytest short-series case; vitest render. strategy: FA

**AC-6 (Locked) Coin add/remove from the UI.** Adding or removing a coin persists and the board reflects it after reload.
- proven by: pytest watchlist router tests; Playwright add/remove flow. strategy: FA

**AC-7 (Locked) Groups.** User can create, rename, delete groups; drag coins between and within groups; order persists after reload.
- proven by: pytest persistence tests; Playwright drag-and-drop flow. strategy: HY (drag gesture feel verified by user; persistence automated)

**AC-8 (Locked) Group sorting.** Sort by name, % change, RSI orders a group correctly, with unavailable values placed last and labelled.
- proven by: vitest sort tests; Playwright. strategy: FA

**AC-9 MOVED** to the narrative-baskets SPEC (narratives CRUD).

**AC-10 (SUPERSEDED — narrative tag deferred) Narrative tags.** Original: every coin in a narrative shows a tag. No longer required; AC-1 asserts no narrative tag on coin boxes.
- proven by: n/a (superseded; replaced by AC-1 absence assertion). strategy: FA

**AC-11 MOVED** to the narrative-baskets SPEC (/narrative raw-only).

**AC-12 (Locked) BTC leg strip.** Top of the screener renders BTC price history with shaded legs and marked boundary dates; the per-coin leg tag is absent.
- proven by: pytest leg-strip payload test using existing leg-boundary maths; Playwright asserting strip present with shaded regions and date markers on seeded data. strategy: FA (visual correctness of shading: HY, user eyeball once)

**AC-13 (Locked, A2: 30 coins) 15-minute refresh on load.** Loading the page refreshes only coins whose stored data is older than 15 minutes; fresher coins are not refetched.
- proven by: pytest staleness test with a controlled clock and mocked exchange adapter; Playwright with seeded stale/fresh coins. Live exchange behaviour at the 30-coin cap: agent-probe on user PC (rate-limit check). strategy: HY

**AC-14 (Locked, A2: sized for 30 coins) Lean storage.** Per coin, 15m history is capped near 200 bars (~2 days); other timeframes retain only what RSI and the price line need; no cache file exists for data no page displays. History that cannot be re-fetched (nightly snapshots) is exempt.
- proven by: pytest retention/trim tests; a repo-level check listing cache categories against displayed pages. strategy: FA

**AC-15 (Locked) Equities page.** A separate equities page shows LSE data for tickers the user adds via an Add button; there is no preset ticker list; added tickers persist after reload; no equity appears in any crypto group; the page states the data is private-use.
- proven by: pytest LSE adapter and ticker-persistence tests on fixtures; Playwright add-ticker flow and page test. Live LSE fetch: agent-probe on user PC (sandbox egress is blocked). strategy: HY

**AC-16 (Locked) Other pages stay, verdict-free but data intact (label audit).** /regime, /pairs, /onchain, /narrative still load and render their data, including the /pairs significance banner and p-value ranking, the /regime composite index, and status/data-quality labels (onchain floor/ramp, pairs status banners); none of the removed verdict labels from outcome 1 appears on them. (Narrative page content beyond "loads and is verdict-free" is under the narrative-baskets SPEC.)
- proven by: existing `regime.spec.ts`, `pairs.spec.ts`, `onchain.spec.ts`, `narrative.spec.ts` updated and green (asserting the kept data is still present); grep gate for removed label strings. strategy: FA

**AC-17 (Locked) Charts page not built.** No standalone charts/indicators route exists.
- proven by: route list check in Playwright/vitest. strategy: FA

**AC-18 (Locked, A5 narrowed to code) Principle retired in code.** No code comment or product text in `web/` or `api/` states "confidence over direction" or implements a cross-signal confidence view. The "numbers are never silently wrong" principle is not retired. (The documentation half of this criterion, including MASTER-PLAN T10 removal, MOVED to `process/general-plans/active/master-planner-recovery_02-10-26/`.)
- proven by: grep gate over `web/` and `api/`. strategy: FA

**AC-19 MOVED** to `process/general-plans/active/master-planner-recovery_02-10-26/` (Gate 1 housekeeping plan).

**AC-20 MOVED** to `process/general-plans/active/master-planner-recovery_02-10-26/` (Gate 1 housekeeping plan).

**AC-21 (Locked, A2: legible at 30 coins) Spaghetti chart content.** The screener shows one chart with a line per screener coin, each plotting % change from the start of the currently selected timeframe, with every line starting at 0%; BTC and HYPE are drawn as distinguishable reference lines; all screener coins are shown by default; no text label or ranking states that any coin is "outperforming" or "underperforming".
- proven by: pytest series-payload test (per-coin % change from its own window start, 0% anchor) on seeded bars; vitest chart render test (line count, reference lines, absence of comparative wording); Playwright asserting the chart and reference lines render on seeded data. strategy: FA (readability of the visual: HY, user eyeball once)

**AC-22 (Locked) Per-coin toggles persist.** The user can toggle each coin's line off and on individually; the choice survives a page reload.
- proven by: vitest toggle-state test; pytest or storage persistence test for the saved state; Playwright toggle, reload and assert. strategy: FA

**AC-23 (Locked) Chart follows the board and the timeframe.** A coin added to the screener appears on the spaghetti chart automatically; a removed coin disappears; switching timeframe re-anchors every line to 0% at the new window start; a coin with too little data for the window shows an explicit "no data" entry, not a flat zero line.
- proven by: Playwright add coin / remove coin / switch each timeframe on seeded data; pytest short-window case. strategy: FA

**AC-24 and AC-25 MOVED** to the narrative-baskets SPEC.

**AC-26 (Locked, A2) Hard cap of 30 coins.** With 30 coins on the screener, attempting to add a 31st is refused with a clear, visible message; the coin is not added, the board, groups and spaghetti chart are unchanged, and the refusal is also enforced by the API (not only the UI). Removing a coin then allows an add again. The cap does not apply to the LSE equities page.
- proven by: pytest watchlist router test (30 accepted, 31st rejected with a clear error, count stays 30, remove-then-add succeeds); vitest message render; Playwright add-31st flow on a seeded 30-coin board. strategy: FA

**AC-27 to AC-33 MOVED** to the narrative-baskets SPEC.

## Impact Surface (what gets deleted / changed)

Names only, derived from reads. "Audit" = file likely carries verdict wording and must be checked in PLAN. Narrative-owned rows (narrative model, narrative router/models/analytics, narrative web components) MOVED to the narrative-baskets SPEC; documentation rows MOVED to `process/general-plans/active/master-planner-recovery_02-10-26/` (Gate 1 housekeeping plan).

| Area | Item | Action |
|---|---|---|
| Web screener | `ConfidenceBadge.tsx` (+ test) | Delete |
| Web screener | `SignalDetailPanel.tsx` (+ test) | Delete |
| Web screener | `LegTimelineBanner.tsx` (+ test) | Replace by BTC leg strip |
| Web screener | `NarrativeStrip.tsx` (+ test) | Delete (no tag replaces it; narrative tag deferred) |
| Web screener | `CoinPanel.tsx`, `ScreenerBoard.tsx` | Change: remove tags, add RSI, groups, drag, sort, add/remove |
| Web screener | `DrillDownView.tsx` | Change: delete the scalp PASS/FAIL view (code + tests + docs); keep price and RSI |
| Web screener | `RelativePerformanceChart.tsx` | Replace by the spaghetti chart (new component; old benchmark chart and tests removed) |
| Web screener | `DeadDataNotice.tsx` | Audit |
| Web screener | New spaghetti chart component + persisted per-coin toggle state | Add |
| Web types | `web/lib/types/screener.ts` | Change: drop MomentumState, TrendState, ConfidenceState, LegContextLiteral, NarrativeStateLiteral; add RSI, groups, spaghetti series |
| API models | `api/models/screener.py` | Change: same removals; add RSI, groups, spaghetti series |
| API analytics | `api/analytics/confidence/badge.py` | Delete |
| API analytics | `api/analytics/indicators/momentum.py`, `trend.py` | Delete or reduce (incl. scalp PASS/FAIL logic); add RSI (Wilder, 14) |
| API analytics | `api/analytics/screener_board.py`, `api/routers/screener.py` | Change (add per-coin start-of-window % change series for spaghetti) |
| API analytics | `api/analytics/regime/leg_boundary.py` | Keep as data for the BTC strip |
| API data | `api/routers/watchlist.py`, `api/data/watchlist.py` | Change: groups, ordering; enforce 30-coin cap with a clear refusal message. (Narrative membership check and removal cascade: narrative-baskets SPEC.) |
| API data | `api/data/cache.py`, `ccxt_adapter.py` | Change: 15-min staleness, retention trim |
| API data | New LSE adapter + user-ticker store; `l2beat`/`hyperliquid`/`etf_flows`/others carrying redistribution flags | Add LSE (user adds tickers, no preset list); drop redistribution flags (Audit) |
| API scripts | `refresh_cache.py`, `backfill_primaries.py`, nightly workflows in `.github/workflows/` | Audit: remove fetches nothing displays; keep nightly history snapshots |
| Other pages | `FloorRampStateLabel.tsx` (onchain), `ComputationStatusBanner.tsx` (pairs) | Keep as data-quality labels |
| Other pages | /pairs significance banner + p-value ranking; /regime composite index | Keep as data |
| Tests | `web/e2e/screener.spec.ts` | Update with the code it guards; add spaghetti and equities specs |

## Out Of Scope

- Any signal generation, scoring, ranking-as-advice, or bullish/bearish output.
- Auth, billing, multi-tenancy, or opening the app to other users.
- New market-price data providers other than LSE (no yfinance, no paid feeds). Attention-signal providers for /narrative are governed by the narrative-baskets SPEC.
- Trade execution or order placement.
- A standalone charts/indicators page.
- Retroactive correction or deletion of already-archived narrative/LiqTide history files.
- Public deployment (Tailscale-only stays).
- Narrative tag on screener coin boxes: deferred until /narrative data shows whether trends give an actionable edge.
- Any computed "outperforming/underperforming" label, score or ranking text on the spaghetti chart; comparison is visual only.
- A preset equities ticker list.
- All /narrative redesign work (narrative-baskets SPEC) and all documentation/process rewrites (`process/general-plans/active/master-planner-recovery_02-10-26/`, Gate 1 housekeeping plan).

## Constraints

- Personal use only; Tailscale-only access stays. LSE data is used under its private-use terms (ADOPT-WITH-LIMITS, per `process/MASTER-PLAN.md` T12; verdict lives on remote branch `claude/exciting-meitner-hy50kn`, not fetched here). The private-use note stays visible on the equities page.
- "Numbers are never silently wrong" stays: unavailable, partial or insufficient data shows an explicit state, never 0/NaN, never zero-filled.
- One source of numerical truth stays: RSI, % change, spaghetti series and leg data are computed in Python and rendered by the web app.
- Providers stay behind adapters under `api/data/`.
- Hard cap: the crypto screener holds not more than 30 coins; a 31st add is refused. Design target: 30 coins; ~200 bars of 15m per coin. The cap does not apply to the LSE equities section.
- Every requirement must remain testable; no verdict logic may be reintroduced under another name.
- Nightly snapshot jobs for sources with no history (narrative, liqtide, chain-growth) stay on their current schedule.
- RSI: Wilder smoothing, period 14.
- Live providers (exchange, LSE) are unreachable from the build sandbox: live checks are agent-probes run on the user's PC (or after a network allow-list), never claimed as automated here.

## Open Questions

| # | Question | Owner | Status |
|---|---|---|---|
| OQ-1 | How many coins will you actually track? | user | **Resolved (A2): hard cap of 30 crypto coins; 31st add refused (AC-26). Not applied to LSE equities.** |
| OQ-2 | /pairs significance banner and p-value ranking. | user | **Resolved (A1): keep as data.** |
| OQ-3 | /regime composite liquidity index. | user | **Resolved (A1): keep as data.** |
| OQ-4 | /onchain `FloorRampStateLabel` and /pairs status banners. | user | **Resolved (A1): keep as data-quality labels.** |
| OQ-5 | Drill-down scalp PASS/FAIL view and BTC/HYPE benchmark chart. | user | **Resolved (A1): scalp view deleted (price and RSI stay); benchmark chart replaced by the spaghetti chart.** |
| OQ-6 | Exact narrative attention figure on the coin tag. | user | **Resolved (A1): moot, tag deferred.** |
| OQ-7 | Equities tickers, timeframes, RSI/groups. | user | **Resolved (A1): user picks tickers with an Add button, no preset list.** Assumption kept: PLAN uses the same price, % change and RSI box as crypto unless the user says otherwise. |
| OQ-8 | Nightly narrative/liqtide/chain-growth snapshots. | user | **Resolved (default adopted): keep nightly snapshots of history that cannot be re-fetched.** |
| OQ-9 | RSI smoothing method. | user | **Resolved (default adopted): Wilder, period 14.** |
| OQ-10 to OQ-17 | Narrative questions. | | **MOVED** to the narrative-baskets SPEC. |

**Remaining open questions in this file: none.** One PLAN-time note (not a block): if the current watchlist already holds more than 30 coins, PLAN must decide how existing extras are handled (the user has not said).

## Background / Research Findings

- Old product north star: "turn separate signals into a confidence level that drives position sizing"; audience "personal first, other users later." Both replaced by user decisions in the first session.
- Today's screener contract (`web/lib/types/screener.ts`, `api/models/screener.py`) carries `momentum`, `trend`, `confidence`, `leg_context`, `narrative_state` per coin; these are the fields being removed. Per-coin chart, `percent_change_by_timeframe` and the five timeframes already exist and stay.
- A watchlist add/remove API already exists (`api/routers/watchlist.py`); groups, ordering and the cap do not.
- Leg-boundary maths lives in `api/analytics/regime/leg_boundary.py` and is reusable as chart data.
- No RSI indicator module currently exists under `api/analytics/indicators/` (only momentum and trend).
- The earlier momentum-screener SPEC (`process/general-plans/active/momentum-screener_17-09-26/momentum-screener_SPEC_17-09-26.md`) is superseded by this SPEC where they conflict; it should be marked so, not edited, until a later phase (a documentation task, handled in the housekeeping plan).
- User input, verbatim intent: "personal-use-only tracking system"; "show data as clearly as possible so the user draws market conclusions"; "must NOT compute or display bullish/bearish verdicts."

## Decision history (condensed)

| Amendment | What it decided for this file |
|---|---|
| 1 | Only drill-down scalp view removed; /pairs banner, /regime composite and status labels stay; narrative tag deferred; spaghetti chart replaces benchmark chart (US-11, US-12, AC-21 to AC-23); equities page with Add button and no preset list; RSI Wilder 14; nightly snapshots kept. |
| 2 | Hard cap of 30 coins (US-14, outcome 18, AC-26); cap applies to crypto only. |
| 3 and 4 | Narrative decisions: moved in full to the narrative-baskets SPEC. |
| Split (02-10-26) | Narrative requirements moved out; documentation requirements moved to the housekeeping plan; AC-18 split; IDs kept stable. |

## Decisions 03-10-26 (after RESEARCH)

User answers (AskUserQuestion, all recommended options). Research facts: backlog note `screener-research-findings_NOTE_03-10-26.md`.

1. **D1 benchmark:** REMOVE the automatic BTC/HYPE benchmark switch and label (`select_active_benchmark`, the 'Benchmark:' label, `BenchmarkSelection`/`active_benchmark`). BTC and HYPE are always fixed reference lines on the spaghetti chart.
2. **D2 saved layout** (groups, coin order, per-coin chart toggles): a SERVER FILE next to `watchlist.json` (survives browser clearing, shared across devices).
3. **D3 page load:** show cached data immediately and refresh behind it when data is older than 15 minutes (not blocking).
4. **D4 leg strip:** confirmed legs only (confirmed boundary to next confirmed boundary), over ALL available BTC daily history, boundary dates marked.
5. **D5 history kept:** about 200 bars per timeframe (15m about 2 days). RSI(14, Wilder) is computed per selected timeframe from that timeframe's own bars. Weekly bars stay DERIVED from daily (about 200 daily bars, about 28 weekly bars, enough for weekly RSI(14)).
6. **D6 spaghetti span:** same bars as the board per timeframe (15m ~2 days, 1h ~8 days, 4h ~33 days, 1d ~200 days). TENSION flagged: 1w derived from ~200 daily bars gives ~28 weeks, not 200. PLAN must resolve this.
7. **D7 drill-down:** keeps its own timeframe toggle, price chart and RSI; the scalp view is dropped; an SMA(60) line is optional.
8. **D8 over 30 coins:** keep all existing coins, BLOCK new adds with a clear message until under 30 (API-enforced); nothing is removed automatically.
9. **D9 equities:** daily and weekly only (1d/1w), same coin box (price, % change, RSI); no intraday until verified from the user's PC. LSE = London Strategic Edge (not the London Stock Exchange; see `VERDICT.md`).
10. **D10 LSE key:** an environment variable on the user's PC, never in the repo or any file; a missing key shows the equities section as unavailable.
11. **D11 equities cache:** local parquet on the user's PC, git-ignored, tagged `redistributable=false`.

**Open after RESEARCH:** none of the 11 research questions remains open except the D6 tension and the P4/P6 split into slices; both are handled in INNOVATE.
