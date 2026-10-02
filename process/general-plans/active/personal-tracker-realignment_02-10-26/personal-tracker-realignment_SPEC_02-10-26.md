---
name: spec:personal-tracker-realignment
description: "Realign my_site from a confidence/verdict screener to a personal-use data-display tracker: slimmer screener with RSI, groups and a spaghetti comparison chart, BTC leg strip, clean /narrative data, user-picked LSE equities page, label purge, and a rewritten North Star + slimmed docs (Amendment 1 applied 02-10-26)"
date: 02-10-26
feature: general-plans
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Personal Tracker Realignment — SPEC

**TL;DR:** my_site stops telling the user what to think. It becomes a personal, Tailscale-only dashboard that shows clean data (price, % change, RSI, raw attention levels, BTC legs) so the user draws their own conclusions. All verdict-style output (confidence badges, bullish/bearish tags, scalp PASS/FAIL, trust weights, "triggered/confirmed" flags) is deleted, not hidden. The screener gets coin groups, an RSI row and a "spaghetti" chart comparing every coin's % change against BTC and HYPE. **Amendment 1:** the narrative tag on coin boxes is deferred until /narrative proves it is useful; the priority now is clean /narrative data. Equities come in via LSE on their own page where the user picks the tickers with an Add button. The docs get a new North Star and a slim, current entry point.

Status key used below: **Locked** = user decided, build to it. **Open** = needs a user answer before it can be planned. **SUPERSEDED by amendment** = kept for traceability, no longer a requirement (see `## Amendment 1`).

---

## Summary

The original product goal was "turn separate signals into one confidence level that drives position sizing." The user has replaced that goal. The app is now a **personal-use-only tracking system** whose job is to **show data as clearly as possible** so the user reaches their own market conclusions. The app must not compute or display any bullish/bearish call, confidence badge, signal-agreement, state/flag label or trust weight. "Open to other users later" is dropped, so redistribution/licensing stops being a design constraint (Tailscale-only access stays). The top-priority change is the screener: keep the small coin boxes, remove every verdict, add an RSI under each coin, and let the user manage coins and named groups from the UI. A BTC price-history strip with shaded legs sits at the top of the screener, and one spaghetti chart lets the user see every coin's % change from the start of the selected timeframe against BTC and HYPE reference lines (visual comparison only, no computed "outperforming" label). The narrative tag on coin boxes is deferred; instead /narrative is made a clean-data page ("hammer on clean data") with explicit handling of missing or partial data. Equities come in through LSE data on a separate page whose tickers the user adds. Finally, the project documents are rewritten so the new direction is the single clear source of truth.

## User Stories / Jobs To Be Done

- **US-1 (Locked) Clean data, no verdicts.** As a solo trader, I want every page to show numbers and charts only, so that my conclusions are mine and not nudged by a computed label.
- **US-2 (Locked) Fast, readable coin boxes.** When I open the screener, I want each coin box to show its price line, % change and RSI for the timeframe I picked, so I can scan many coins in seconds.
- **US-3 (Locked) My own coin groups.** As a trader, I want to create, rename and delete named groups, drag coins between and within groups, and sort each group by name, % change or RSI, so the board matches how I think about the market.
- **US-4 (Locked) Manage coins in the app.** I want to add and remove coins from the UI, so I never edit config files.
- **US-5 (SUPERSEDED by amendment — tag part deferred; editing part carried by US-5b) Narrative tags on coin boxes.** Original: see each coin's narrative name with its raw attention change on its box. Deferred: no tag until /narrative data shows whether trends give an actionable edge.
- **US-5b (Open, see OQ-10) My own narratives, edited in the app.** I want to create, edit and delete narratives (a name plus a list of coins) in the app, so my own groupings of coins are stored without editing files. Kept as locked from the earlier round, but the user is asked to confirm it is still wanted now that the tag is deferred.
- **US-6 (Locked, amended) Clean raw attention on /narrative.** I want /narrative to show only raw attention levels and changes per source, with missing, partial or insufficient data clearly marked, so I can trust what I see and judge the narrative myself.
- **US-7 (Locked) Where are we in the cycle.** I want a BTC price-history strip at the top of the screener with legs shaded and leg-boundary dates marked, so I see where we may be in history.
- **US-8 (Locked) Fresh without babysitting.** I want coin data to refresh when I open the page and it is more than 15 minutes old, so I need no background job running.
- **US-9 (Locked, amended) Equities in their own place, my tickers.** I want equities (LSE data) on a separate page where I add the tickers I care about with an Add button, so they never mix into my crypto groups and I am not stuck with a preset list.
- **US-10 (Locked) Docs that match reality.** As the owner (and as any future agent session), I want a rewritten North Star, a short current-state doc, a task registry and an archive index, so I do not need to read a 1,200-line changelog to know what the product is.
- **US-11 (Locked, new) See who beats HYPE and BTC at a glance.** When I look at the screener, I want one chart with a line per coin showing % change from the start of my selected timeframe, with BTC and HYPE as reference lines, so I can see by eye which coins are ahead of or behind HYPE and BTC.
- **US-12 (Locked, new) Declutter the comparison chart.** I want to switch each coin's line off and on individually and have that choice remembered, so I can focus on the coins I am comparing.
- **US-13 (Locked, new) Trust the narrative data.** When data for a source is missing, partial or insufficient, I want to see that stated plainly instead of a zero or a quietly wrong number, so my read of /narrative is not corrupted.

## What The User Wants (Behavioral Outcomes)

1. **No verdicts anywhere.** No page shows a confidence badge, signal agreement, trend up/down tag, momentum PASS/FAIL tag, scalp PASS/FAIL view, leg tag, narrative state label ("in-focus", "rotated-out", etc.), `triggered`/`confirmed` flag, or `trust_weight`.
2. **Screener coin box (Locked).** Same small-box look as today. Contains: coin name, price line chart, % change for the active timeframe, and an RSI value (default period 14, Wilder smoothing) beneath it. The timeframe switch (15m / 1h / 4h / 1d / 1w) drives price line, % change and RSI together.
3. **Coin management (Locked).** Add and remove coins from the screener UI.
4. **Groups (Locked).** User-named groups: create, rename, delete. Drag coins between groups and reorder within a group. Each group has a quick sort: by name, % change, or RSI.
5. **Narrative tags on coin boxes (SUPERSEDED by amendment — deferred).** Coin boxes carry no narrative tag in this scope.
6. **Narrative editor (Locked pending OQ-10).** Create, edit, delete narratives (name + coin list) inside the app. The app persists them; the user never edits JSON.
7. **/narrative page (Locked, amended).** Per source, show raw attention level and change only. No flags, no trust weight. Missing, partial or insufficient data is shown explicitly (see items 15–16).
8. **BTC leg strip (Locked).** At the top of the screener: BTC price history, leg periods shaded, leg-boundary dates marked. The existing leg-boundary maths feeds it as plain data. The per-coin leg tag is deleted.
9. **Refresh (Locked).** On page load, any coin whose data is older than 15 minutes is refreshed. No background job is required for this.
10. **Lean data (Locked).** Keep about 2 days (~200 bars) of 15m history per coin. Other timeframes keep only what their RSI and price line need. Anything fetched or stored that no page displays is removed. Designed for up to ~50 coins (ceiling; actual count unconfirmed, OQ-1).
11. **Equities page (Locked, amended).** A separate section/page showing LSE equity data with an "Add" button; the user picks the tickers (no preset list). Used under LSE's private-use terms.
12. **Other pages stay (Locked, amended).** /regime, /narrative, /pairs, /onchain remain. Their data stays, including the /pairs significance banner and p-value ranking, the /regime composite liquidity index, and status/data-quality labels (onchain floor/ramp, pairs status banners). Only verdict-style outputs on the removed-list (item 1) go.
13. **Dropped (Locked).** The standalone charts/indicators page is not built; RSI on the screener replaces it.
14. **Spaghetti chart (Locked, new; replaces the benchmark relative-performance chart).** One chart, a line per coin, each showing % change from the start of the currently selected timeframe (each coin measured on its own window, anchored at 0%). BTC and HYPE appear as reference lines. All screener coins appear by default; each can be toggled off/on and the toggle state persists. A coin added to the screener appears automatically; a removed coin disappears. Switching timeframe re-anchors every line. Visual comparison only: no computed "outperforming" label or ranking text.
15. **Clean /narrative data (Locked, new).** Only raw attention levels/changes per source. Where a source has missing, partial or insufficient data, the view says so explicitly. No zero-fill, no silently wrong numbers.
16. **Data-quality guarantees kept in scope (Locked, new).** The pytrends partial-hour fix (incomplete current-hour readings never archived as real values) and the nightly archive of non-refetchable history stay in scope and must keep working.
17. **Scalp view removed (Locked, new).** Only the drill-down "Scalp PASS/FAIL" view is deleted (code, tests, docs). Drill-down price and RSI stay.

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
   +--> Add / remove coin
   +--> Create / rename / delete group
   +--> Failure: data unavailable --> box says "no data" (never 0 or blank number)

/narrative: raw attention level + change per source
   +--> source missing / partial / insufficient --> explicit label (never 0, never silent)
   +--> narrative editor (name + coins), pending OQ-10 confirmation

/equities (LSE): [Add ticker] --> user-picked tickers listed; private-use note shown

Separate pages: /narrative /regime /pairs /onchain /equities
Retired outputs: confidence, agreement, trend tag, momentum/scalp PASS/FAIL, leg tag,
                 narrative state flags, trust weight, narrative tag on coin boxes (deferred)
```

## Acceptance Criteria (Testable Outcomes)

Strategy tags: FA = Fully-Automated, HY = Hybrid, AP = Agent-Probe. Scenarios come from the existing test surfaces: pytest (`api/tests/{analytics,data,routers,scripts}`), vitest (`web/components/*/__tests__`, `web/lib/__tests__`), Playwright (`web/e2e/*.spec.ts`), plus the repo validators.

Note: the 20-criteria cap is exceeded by Amendment 1 (see Amendment 1 concerns). IDs are not renumbered; AC-10 is superseded, AC-21 to AC-25 are new.

**AC-1 (Locked) No verdict output in screener data.** The screener API response and page contain no confidence, leg_context, narrative_state, momentum state, trend direction, or narrative tag fields/labels.
- proven by: pytest contract test asserting absent fields; vitest render test; Playwright `screener.spec.ts` asserting no badge/tag elements. strategy: FA

**AC-2 (Locked, amended) Verdict code is deleted, not hidden.** The deletion targets in the Impact Surface table (including the drill-down scalp PASS/FAIL view and the old relative-performance chart) no longer exist in source, tests or docs; no dead imports remain.
- proven by: repo grep gate for removed symbols (ConfidenceBadge, SignalDetailPanel, confidence badge module, momentum/trend state, scalp PASS/FAIL view, trust_weight) returning zero hits outside archived history; `tsc --noEmit` and full pytest/vitest green. strategy: FA

**AC-3 (Locked) Coin box content.** Each box shows price line, % change and RSI for the active timeframe; RSI uses period 14 with Wilder smoothing (OQ-9 adopted).
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

**AC-9 (Locked pending OQ-10) Narratives CRUD in app.** User can create, edit, delete a narrative (name + coin list) in the UI; changes persist and need no file editing. Becomes SUPERSEDED if the user answers OQ-10 "not now".
- proven by: pytest router/persistence tests; Playwright CRUD flow. strategy: FA

**AC-10 (SUPERSEDED by amendment — narrative tag deferred) Narrative tags.** Original: every coin in a narrative shows a tag with narrative name and raw attention change. No longer required; AC-1 now asserts that no narrative tag appears on coin boxes.
- proven by: n/a (superseded; replaced by AC-1 absence assertion). strategy: FA

**AC-11 (Locked, amended) /narrative is raw-only.** The page and its API show per-source attention level and change; `triggered`, `confirmed`, `trust_weight` and any flag appear nowhere in responses, types or UI. Existing `/api/narrative/categories` verdict contract is retired with its snapshot test.
- proven by: pytest response-shape tests; vitest; `narrative.spec.ts`. strategy: FA

**AC-12 (Locked) BTC leg strip.** Top of the screener renders BTC price history with shaded legs and marked boundary dates; the per-coin leg tag is absent.
- proven by: pytest leg-strip payload test using existing leg-boundary maths; Playwright asserting strip present with shaded regions and date markers on seeded data. strategy: FA (visual correctness of shading: HY, user eyeball once)

**AC-13 (Locked) 15-minute refresh on load.** Loading the page refreshes only coins whose stored data is older than 15 minutes; fresher coins are not refetched.
- proven by: pytest staleness test with a controlled clock and mocked exchange adapter; Playwright with seeded stale/fresh coins. Live exchange behaviour at up to ~50 coins: agent-probe on user PC (rate-limit check). strategy: HY

**AC-14 (Locked) Lean storage.** Per coin, 15m history is capped near 200 bars (~2 days); other timeframes retain only what RSI and the price line need; no cache file exists for data no page displays. History that cannot be re-fetched (nightly snapshots, OQ-8 adopted) is exempt.
- proven by: pytest retention/trim tests; a repo-level check listing cache categories against displayed pages. strategy: FA

**AC-15 (Locked, amended) Equities page.** A separate equities page shows LSE data for tickers the user adds via an Add button; there is no preset ticker list; added tickers persist after reload; no equity appears in any crypto group; the page states the data is private-use.
- proven by: pytest LSE adapter and ticker-persistence tests on fixtures; Playwright add-ticker flow and page test. Live LSE fetch: agent-probe on user PC. strategy: HY

**AC-16 (Locked, amended) Other pages stay, verdict-free but data intact.** /regime, /pairs, /onchain, /narrative still load and render their data, including the /pairs significance banner and p-value ranking, the /regime composite index, and status/data-quality labels (onchain floor/ramp, pairs status banners); none of the removed verdict labels from AC-1/AC-11 appears on them.
- proven by: existing `regime.spec.ts`, `pairs.spec.ts`, `onchain.spec.ts`, `narrative.spec.ts` updated and green (asserting the kept data is still present); grep gate for removed label strings. strategy: FA

**AC-17 (Locked) Charts page not built.** No standalone charts/indicators route exists.
- proven by: route list check in Playwright/vitest. strategy: FA

**AC-18 (Locked) Principle retired.** No doc, code comment or plan states "confidence over direction" or plans a cross-signal confidence view (MASTER-PLAN T10 removed). The "numbers are never silently wrong" principle is not retired.
- proven by: grep gate over `process/` active docs and `web/`/`api/`. strategy: FA

**AC-19 (Locked) Rewritten North Star.** A single North Star doc exists stating: personal-use only, show-data-not-verdicts, Tailscale-only, the page list, and the explicit non-goals (including narrative tag on screener deferred); the old confidence/public-later language is gone from entry points.
- proven by: doc-structure check script (required headings) + user read-through at the gate. strategy: HY

**AC-20 (Locked) Docs slimmed and navigable.** (a) `all-context.md` is reduced to a router plus current state, with its changelog moved to a dated archive file (target: under ~300 lines; the 1,223-line, ~65% changelog shape is gone); (b) a current-state doc exists; (c) a task registry exists listing tasks, status and owner, with a worker report schema; (d) an archive index lists archived plans and changelogs; (e) `MASTER-PLAN.md` is either rewritten to match or retired, and is referenced from entry points either way.
- proven by: line-count and link-reachability check; `vc-audit-context` and `validate-context-discovery.mjs` green. strategy: FA

**AC-21 (Locked, new) Spaghetti chart content.** The screener shows one chart with a line per screener coin, each plotting % change from the start of the currently selected timeframe, with every line starting at 0%; BTC and HYPE are drawn as distinguishable reference lines; all screener coins are shown by default; no text label or ranking states that any coin is "outperforming" or "underperforming".
- proven by: pytest series-payload test (per-coin % change from its own window start, 0% anchor) on seeded bars; vitest chart render test (line count, reference lines, absence of comparative wording); Playwright asserting the chart and reference lines render on seeded data. strategy: FA (readability of the visual: HY, user eyeball once)

**AC-22 (Locked, new) Per-coin toggles persist.** The user can toggle each coin's line off and on individually; the choice survives a page reload.
- proven by: vitest toggle-state test; pytest or storage persistence test for the saved state; Playwright toggle, reload and assert. strategy: FA

**AC-23 (Locked, new) Chart follows the board and the timeframe.** A coin added to the screener appears on the spaghetti chart automatically; a removed coin disappears; switching timeframe re-anchors every line to 0% at the new window start; a coin with too little data for the window shows an explicit "no data" entry, not a flat zero line.
- proven by: Playwright add coin / remove coin / switch each timeframe on seeded data; pytest short-window case. strategy: FA

**AC-24 (Locked, new) /narrative data is clean and honest.** For each source, /narrative shows only raw level and change; any missing, partial or insufficient reading is shown with an explicit visible state and is never rendered as 0, filled in, or silently averaged; no flag or trust weight exists on the page or API.
- proven by: pytest tests with missing, partial and short-history fixtures per source; vitest render of each explicit state; `narrative.spec.ts` seeded with a gap scenario. strategy: FA

**AC-25 (Locked, new) Data-quality fix and archive stay intact.** An incomplete current-hour pytrends reading is never archived as a real value (it yields "unavailable", not 0), and the nightly archive of non-refetchable history still writes one point per source per day.
- proven by: existing and retained `api/tests/data/test_pytrends_adapter.py` partial-hour cases; archive-writer pytest tests in `api/tests/scripts/`; workflow-schedule guard test stays green. strategy: FA

## Impact Surface (what gets deleted / changed)

Names only, derived from reads. "Audit" = file likely carries verdict wording and must be checked in PLAN. Rows changed by Amendment 1 are marked (A1).

| Area | Item | Action |
|---|---|---|
| Web screener | `ConfidenceBadge.tsx` (+ test) | Delete |
| Web screener | `SignalDetailPanel.tsx` (+ test) | Delete |
| Web screener | `LegTimelineBanner.tsx` (+ test) | Replace by BTC leg strip |
| Web screener | `NarrativeStrip.tsx` (+ test) | **(A1) Delete** (no tag replaces it; narrative tag deferred) |
| Web screener | `CoinPanel.tsx`, `ScreenerBoard.tsx` | Change: remove tags, add RSI, groups, drag, sort, add/remove |
| Web screener | `DrillDownView.tsx` | **(A1) Change: delete the scalp PASS/FAIL view (code + tests + docs); keep price and RSI** |
| Web screener | `RelativePerformanceChart.tsx` | **(A1) Replace by the spaghetti chart** (new component; old benchmark chart and its tests removed) |
| Web screener | `DeadDataNotice.tsx` | Audit |
| Web screener | New spaghetti chart component + persisted per-coin toggle state | **(A1) Add** |
| Web types | `web/lib/types/screener.ts` | Change: drop MomentumState, TrendState, ConfidenceState, LegContextLiteral, NarrativeStateLiteral; add RSI, groups, spaghetti series |
| API models | `api/models/screener.py` | Change: same removals; add RSI, groups, spaghetti series |
| API analytics | `api/analytics/confidence/badge.py` | Delete |
| API analytics | `api/analytics/indicators/momentum.py`, `trend.py` | Delete or reduce (incl. scalp PASS/FAIL logic); add RSI (Wilder, 14) |
| API analytics | `api/analytics/screener_board.py`, `api/routers/screener.py` | Change (add per-coin start-of-window % change series for spaghetti) |
| API analytics | `api/analytics/regime/leg_boundary.py` | Keep as data for the BTC strip |
| API narrative | `api/analytics/narrative/trigger.py`, `scoring.py`, `mapping.py` | Delete/reduce trigger, confirmation, trust weight; mapping replaced by in-app narratives (if OQ-10 confirmed) |
| API narrative | `api/routers/narrative.py`, `api/models/narrative.py` | Change: remove triggered/confirmed/trust_weight; explicit missing/partial/insufficient states; narrative CRUD (pending OQ-10) |
| API narrative | `api/analytics/narrative/narrative_config.py`, `api/data/narratives.json`, `narrative_categories.json`, `narrative_category_map.json` | Change: app-managed store replaces hand-edited JSON (pending OQ-10) |
| API narrative | `momentum.py`, `mindshare.py` (+ `MomentumView.tsx`, `MindshareView.tsx`) | Audit for state labels and for silent zero/average handling (A1) |
| API data | `api/data/pytrends_adapter.py` and nightly archive scripts | **(A1) Keep: partial-hour fix and nightly archive are protected by AC-25** |
| Web narrative | `NarrativeDashboard.tsx`, `CategoryHistoryPanel.tsx`, `ComparisonView.tsx`, `ChangeInAttentionView.tsx`, `DataQualityCaveat.tsx` | Change/Audit: raw-only, explicit missing-data states (A1) |
| Web narrative | `RedistributionBadge.tsx` | Delete (licensing no longer a constraint; confirm in PLAN) |
| API data | `api/routers/watchlist.py`, `api/data/watchlist.py` | Change: groups, ordering |
| API data | `api/data/cache.py`, `ccxt_adapter.py` | Change: 15-min staleness, retention trim |
| API data | New LSE adapter + user-ticker store; `l2beat`/`hyperliquid`/`etf_flows`/others carrying redistribution flags | Add LSE (user adds tickers, no preset list, A1); drop redistribution flags (Audit) |
| API scripts | `refresh_cache.py`, `backfill_primaries.py`, nightly workflows in `.github/workflows/` | Audit: remove fetches nothing displays; keep nightly history snapshots (OQ-8 adopted) |
| Other pages | `FloorRampStateLabel.tsx` (onchain), `ComputationStatusBanner.tsx` (pairs) | **(A1) Keep as data-quality labels** (resolves OQ-4) |
| Other pages | /pairs significance banner + p-value ranking; /regime composite index | **(A1) Keep as data** (resolves OQ-2, OQ-3) |
| Tests | `web/e2e/screener.spec.ts`, `narrative.spec.ts`, narrative contract-snapshot and tripwire tests | Update/Delete with the code they guard; add spaghetti and equities specs |
| Docs | `process/context/all-context.md` (1,223 lines), `process/MASTER-PLAN.md` (T10, T12, T15), `process/general-plans/active/momentum-screener_17-09-26/` SPEC/PLAN | Slim / rewrite / mark superseded |
| Docs (new) | North Star, current-state, task registry + worker report schema, archive index | Create |

## Out Of Scope

- Any signal generation, scoring, ranking-as-advice, or bullish/bearish output.
- Auth, billing, multi-tenancy, or opening the app to other users.
- New data providers other than LSE (no yfinance, no paid feeds).
- Trade execution or order placement.
- A standalone charts/indicators page.
- Retroactive correction or deletion of already-archived narrative/LiqTide history files (history that cannot be refetched is kept unless the user says otherwise).
- Public deployment (Tailscale-only stays).
- **(A1) Narrative tag on screener coin boxes: deferred** until /narrative data shows whether trends give an actionable edge. Not built in this scope.
- **(A1) Any computed "outperforming/underperforming" label, score or ranking text** on the spaghetti chart; comparison is visual only.
- **(A1) A preset equities ticker list.**

## Constraints

- Personal use only; Tailscale-only access stays. LSE data is used under its private-use terms (ADOPT-WITH-LIMITS, per `process/MASTER-PLAN.md` T12; verdict lives on remote branch `claude/exciting-meitner-hy50kn`, not fetched here). The private-use note stays visible on the equities page.
- "Numbers are never silently wrong" stays: unavailable, partial or insufficient data shows an explicit state, never 0/NaN, never zero-filled (applies to the screener, spaghetti chart and /narrative).
- One source of numerical truth stays: RSI, % change, spaghetti series and leg data are computed in Python and rendered by the web app.
- Providers stay behind adapters under `api/data/`.
- Design target: up to ~50 coins (ceiling, OQ-1 still open); ~200 bars of 15m per coin.
- Every requirement above must remain testable; no verdict logic may be reintroduced under another name.
- Nightly snapshot jobs for sources with no history (narrative, liqtide, chain-growth) stay on their current schedule (OQ-8 adopted).
- RSI: Wilder smoothing, period 14 (OQ-9 adopted).
- **(A1) Priority order for /narrative work: data cleanliness first; any further narrative feature waits on what the clean data shows.**

## Open Questions

| # | Question | Owner | Status |
|---|---|---|---|
| OQ-1 | How many coins will you actually track? (Answer was ambiguous; design ceiling stays ~50.) Affects rate limits and refresh strategy on page load, and spaghetti chart legibility. | user | **Open** (ceiling ~50 adopted meanwhile) |
| OQ-2 | /pairs significance banner and p-value ranking. | user | **Resolved (A1): keep as data.** |
| OQ-3 | /regime composite liquidity index. | user | **Resolved (A1): keep as data.** |
| OQ-4 | /onchain `FloorRampStateLabel` and /pairs status banners. | user | **Resolved (A1): keep as data-quality labels.** |
| OQ-5 | Screener drill-down scalp PASS/FAIL view and BTC/HYPE benchmark relative-performance chart. | user | **Resolved (A1): scalp PASS/FAIL view deleted (price and RSI stay); benchmark chart replaced by the spaghetti chart with BTC and HYPE reference lines.** |
| OQ-6 | Exact narrative attention figure on the coin tag. | user | **Resolved (A1): moot — narrative tag deferred.** |
| OQ-7 | Equities tickers, timeframes, RSI/groups. | user | **Resolved (A1): user picks tickers with an Add button, no preset list.** Whether the equities page also needs timeframes/RSI/groups is not stated; PLAN assumes the same price, % change and RSI box as crypto unless the user says otherwise. |
| OQ-8 | Nightly narrative/liqtide/chain-growth snapshots. | user | **Resolved (A1, default adopted): keep nightly snapshots of history that cannot be re-fetched.** |
| OQ-9 | RSI smoothing method. | user | **Resolved (A1, default adopted): Wilder smoothing, period 14.** |
| OQ-10 | With the narrative tag deferred, do you still want in-app narrative create/edit/delete (name + coins) built now, or should it wait until /narrative proves useful? | user | **Open (new)** |

Handling: OQ-1 and OQ-10 remain open and are flagged for the confirm/push-back gate. Locked items above do not depend on them except US-5b/AC-9 (OQ-10) and the sizing note (OQ-1).

## Background / Research Findings

- Old product north star: "turn separate signals into a confidence level that drives position sizing"; audience "personal first, other users later." Both replaced by user decisions 1 and 7 of the first session.
- Today's screener contract (`web/lib/types/screener.ts`, `api/models/screener.py`) carries `momentum`, `trend`, `confidence`, `leg_context`, `narrative_state` per coin; these are the fields being removed. Per-coin chart, `percent_change_by_timeframe` and the five timeframes already exist and stay.
- A watchlist add/remove API already exists (`api/routers/watchlist.py`); groups and ordering do not.
- Narratives are currently defined in hand-edited `api/data/narratives.json` (from narrative-v2); `/narrative` and `/categories` expose `triggered`, `confirmed`, `trust_weight` (`api/analytics/narrative/trigger.py`).
- Leg-boundary maths lives in `api/analytics/regime/leg_boundary.py` and is reusable as chart data.
- No RSI indicator module currently exists under `api/analytics/indicators/` (only momentum and trend).
- `process/context/all-context.md` is 1,223 lines, ~65% changelog; `process/MASTER-PLAN.md` is stale and not linked from entry points; no task registry, worker report schema or archive index exists (Gate 0 audit).
- The earlier momentum-screener SPEC (`process/general-plans/active/momentum-screener_17-09-26/momentum-screener_SPEC_17-09-26.md`, esp. US-3, US-5, US-6, US-7) is superseded by this SPEC where they conflict; it should be marked so, not edited, until a later phase.
- Pytrends partial-hour fix and nightly archive exist from earlier work (2026-09-28 / 2026-10-01 entries in `all-context.md`); they are carried forward as protected guarantees (AC-25).
- User input, verbatim intent: "personal-use-only tracking system"; "show data as clearly as possible so the user draws market conclusions"; "must NOT compute or display bullish/bearish verdicts." Amendment 1: "hammer on clean data" (priority for /narrative before any narrative tag).

## Amendment 1 (02-10-26, user answers)

Source: user answers A to E of the amendment pass. These override earlier text where they conflict. No IDs were renumbered or deleted; superseded items are marked in place.

**What changed**

| Topic | Change |
|---|---|
| Verdict-like outputs on other pages (A) | Only the drill-down scalp PASS/FAIL view is removed (code, tests, docs; price and RSI stay). /pairs significance banner and p-value ranking, /regime composite index, and status/data-quality labels (onchain floor/ramp, pairs status banners) stay as data. AC-16 amended. Resolves OQ-2, OQ-3, OQ-4 and the scalp part of OQ-5. |
| Narrative tag (B) | Deferred. US-5, outcome 5 and AC-10 marked SUPERSEDED; AC-1 now asserts no narrative tag on boxes; `NarrativeStrip.tsx` is deleted with no replacement; OQ-6 moot. Added to Out Of Scope. |
| Narrative editing (B) | US-5b, outcome 6 and AC-9 kept as locked but conditional; new OQ-10 asks the user to confirm it is still wanted now. |
| /narrative cleanliness (B) | US-6 amended; new US-13, outcomes 15 and 16, AC-24 (raw-only, explicit missing/partial/insufficient states, no zero-fill) and AC-25 (pytrends partial-hour fix and nightly archive protected). AC-11 amended. |
| Spaghetti chart (C) | Replaces the benchmark relative-performance chart. New US-11, US-12, outcome 14, AC-21 to AC-23. Rest of OQ-5 resolved. |
| Equities (D) | Separate section with an Add button; user picks tickers; no preset list. US-9, outcome 11 and AC-15 amended; LSE private-use note kept. Resolves OQ-7 (with the small assumption noted in the table). |
| Defaults (E) | OQ-1 stays open with the ~50 ceiling; OQ-8 nightly snapshots kept; OQ-9 Wilder smoothing, period 14. AC-3, AC-14 and Constraints updated. |
| Impact Surface / Out Of Scope / Constraints | Updated as marked "(A1)" above. |

**Superseded by this amendment:** US-5, outcome 5, AC-10, OQ-2/3/4/5/6 as open questions (now resolved), the `NarrativeStrip.tsx` "replace by tag" action, the `RelativePerformanceChart.tsx` "audit" action.

**Concerns:** (1) The 20-criteria cap is exceeded (24 active criteria after AC-10 is superseded). Recommended: accept at the confirm gate, since the scope grew by user request, or split into two SPECs. (2) Deferring the narrative tag leaves much of the narrative backend (CRUD, mapping replacement) without a visible consumer; OQ-10 exists to settle that. (3) Equities page features beyond the Add button (timeframes, RSI, groups) are assumed, not confirmed.

**Remaining open questions:** OQ-1 (coin count; ceiling ~50 adopted) and OQ-10 (confirm in-app narrative editing is still wanted now).
