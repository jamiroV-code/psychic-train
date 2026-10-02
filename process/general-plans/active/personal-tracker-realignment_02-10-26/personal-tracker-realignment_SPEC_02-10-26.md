---
name: spec:personal-tracker-realignment
description: "Realign my_site from a confidence/verdict screener to a personal-use data-display tracker: slimmer screener with RSI, groups and a spaghetti comparison chart, BTC leg strip, clean /narrative data built on user-defined coin baskets (equal-weight basket chart, share-of-total mindshare, daily rising/hottest view), user-picked LSE equities page, label purge, and a rewritten North Star + slimmed docs (Amendments 1, 2, 3 and 4 applied 02-10-26)"
date: 02-10-26
feature: general-plans
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Personal Tracker Realignment — SPEC

**TL;DR:** my_site stops telling the user what to think. It becomes a personal, Tailscale-only dashboard that shows clean data (price, % change, RSI, raw attention levels, BTC legs) so the user draws their own conclusions. All verdict-style output (confidence badges, bullish/bearish tags, scalp PASS/FAIL, trust weights, "triggered/confirmed" flags) is deleted, not hidden. The screener gets coin groups, an RSI row and a "spaghetti" chart comparing every coin's % change against BTC and HYPE. **Amendment 1:** the narrative tag on coin boxes is deferred until /narrative proves it is useful. **Amendment 3:** /narrative exists to show, daily, which narratives are RISING and which are HOTTEST; narratives become coin baskets the user builds from screener coins. **Amendment 4:** basket performance is equal-weight rebased to 100; one coin may sit in several narratives; mindshare is share-of-total per source, averaged across present sources. Which platforms and signals feed coin-level attention is still open (OQ-12) and needs a research pass first. Equities come in via LSE on their own page where the user picks the tickers. The docs get a new North Star and a slim, current entry point.

Status key used below: **Locked** = user decided, build to it. **Open** = needs a user answer before it can be planned. **SUPERSEDED by amendment** = kept for traceability, no longer a requirement (see `## Amendment 1`). **(A3)** / **(A4)** mark text changed or added by Amendments 3 and 4.

---

## Summary

The original product goal was "turn separate signals into one confidence level that drives position sizing." The user has replaced that goal. The app is now a **personal-use-only tracking system** whose job is to **show data as clearly as possible** so the user reaches their own market conclusions. The app must not compute or display any bullish/bearish call, confidence badge, signal-agreement, state/flag label or trust weight. "Open to other users later" is dropped, so redistribution/licensing stops being a design constraint (Tailscale-only access stays). The top-priority change is the screener: keep the small coin boxes, remove every verdict, add an RSI under each coin, and let the user manage coins and named groups from the UI. A BTC price-history strip with shaded legs sits at the top of the screener, and one spaghetti chart lets the user see every coin's % change from the start of the selected timeframe against BTC and HYPE reference lines (visual comparison only, no computed "outperforming" label). The narrative tag on coin boxes is deferred. **(A3)** The /narrative page has one job: let the user see, at a daily time scale, which narratives are rising and which are the hottest right now. A narrative is a basket the user defines by picking coins that are already on the screener and classifying them under a name of their choosing. The page starts with a spaghetti chart where each narrative's line is the performance of its basket (visual comparison only), and a second view shows mindshare per narrative. **(A4)** Decided: a basket line is the equal-weight average of its coins' performance, rebased to 100 at the window start; a coin can belong to several narratives; mindshare is each narrative's share of all narratives per source, averaged across the sources present, with raw per-source values always visible. Still open: which signals and platforms supply coin-level attention (a research pass must conclude first). Equities come in through LSE data on a separate page whose tickers the user adds. Finally, the project documents are rewritten so the new direction is the single clear source of truth.

## User Stories / Jobs To Be Done

- **US-1 (Locked) Clean data, no verdicts.** As a solo trader, I want every page to show numbers and charts only, so that my conclusions are mine and not nudged by a computed label.
- **US-2 (Locked) Fast, readable coin boxes.** When I open the screener, I want each coin box to show its price line, % change and RSI for the timeframe I picked, so I can scan many coins in seconds.
- **US-3 (Locked) My own coin groups.** As a trader, I want to create, rename and delete named groups, drag coins between and within groups, and sort each group by name, % change or RSI, so the board matches how I think about the market.
- **US-4 (Locked) Manage coins in the app.** I want to add and remove coins from the UI, so I never edit config files.
- **US-5 (SUPERSEDED by amendment — tag part deferred; editing part carried by US-5b) Narrative tags on coin boxes.** Original: see each coin's narrative name with its raw attention change on its box. Deferred: no tag until /narrative data shows whether trends give an actionable edge.
- **US-5b (Locked, A2: OQ-10 resolved; A3 refined) My own narratives, edited in the app.** I want to create, edit and delete narratives in the app, each being a name of my choosing plus coins I pick from my screener, so my own groupings are stored without editing files. The user confirmed (A2) the narrative section is still wanted: "very useful to track the narrative". **(A3)** Narratives are user-defined coin baskets; they are no longer keyword/category definitions.
- **US-6 (Locked, amended) Clean raw attention on /narrative.** I want /narrative to show only raw attention levels and changes per source, with missing, partial or insufficient data clearly marked, so I can trust what I see and judge the narrative myself.
- **US-7 (Locked) Where are we in the cycle.** I want a BTC price-history strip at the top of the screener with legs shaded and leg-boundary dates marked, so I see where we may be in history.
- **US-8 (Locked) Fresh without babysitting.** I want coin data to refresh when I open the page and it is more than 15 minutes old, so I need no background job running.
- **US-9 (Locked, amended) Equities in their own place, my tickers.** I want equities (LSE data) on a separate page where I add the tickers I care about with an Add button, so they never mix into my crypto groups and I am not stuck with a preset list.
- **US-10 (Locked) Docs that match reality.** As the owner (and as any future agent session), I want a rewritten North Star, a short current-state doc, a task registry and an archive index, so I do not need to read a 1,200-line changelog to know what the product is.
- **US-11 (Locked, new) See who beats HYPE and BTC at a glance.** When I look at the screener, I want one chart with a line per coin showing % change from the start of my selected timeframe, with BTC and HYPE as reference lines, so I can see by eye which coins are ahead of or behind HYPE and BTC.
- **US-12 (Locked, new) Declutter the comparison chart.** I want to switch each coin's line off and on individually and have that choice remembered, so I can focus on the coins I am comparing.
- **US-14 (Locked, A2, new) Hard cap of 30 coins.** As a trader, I want the screener to hold at most 30 coins and refuse a 31st with a clear message, so the board, the refresh on page load and the spaghetti chart stay fast and readable.
- **US-13 (Locked, new) Trust the narrative data.** When data for a source is missing, partial or insufficient, I want to see that stated plainly instead of a zero or a quietly wrong number, so my read of /narrative is not corrupted.
- **US-15 (Locked, A3, new) Which narratives are rising and hottest, daily.** When I open /narrative, I want to see at a daily time scale which of my narratives are rising and which are the hottest right now, so I know where attention and money are moving.
- **US-16 (Locked, A3, new; A4: equal-weight) Compare narrative baskets by eye.** I want a spaghetti chart where each narrative's line is the equal-weight performance of its grouped coins, rebased to 100 at the window start, so I can see visually which narrative is outperforming or underperforming without the app telling me.
- **US-17 (Locked, A3, new; A4: share-of-total) Mindshare per narrative.** I want a second view showing each narrative's share of attention, built up from the coins inside it, so I can tell when a narrative heats up before or after price moves.
- **US-18 (Locked, A3, new) Only coins I already track.** I want narratives to accept only coins that are on my screener, so every narrative coin has the same price data as the rest of my board.
- **US-19 (Locked, A4, new) Overlapping narratives.** As a trader, I want one coin to be able to sit in several narratives (for example both "AI" and "memecoins"), so my baskets reflect how the market actually overlaps.

## What The User Wants (Behavioral Outcomes)

1. **No verdicts anywhere.** No page shows a confidence badge, signal agreement, trend up/down tag, momentum PASS/FAIL tag, scalp PASS/FAIL view, leg tag, narrative state label ("in-focus", "rotated-out", etc.), `triggered`/`confirmed` flag, or `trust_weight`.
2. **Screener coin box (Locked).** Same small-box look as today. Contains: coin name, price line chart, % change for the active timeframe, and an RSI value (default period 14, Wilder smoothing) beneath it. The timeframe switch (15m / 1h / 4h / 1d / 1w) drives price line, % change and RSI together.
3. **Coin management (Locked).** Add and remove coins from the screener UI.
4. **Groups (Locked).** User-named groups: create, rename, delete. Drag coins between groups and reorder within a group. Each group has a quick sort: by name, % change, or RSI.
5. **Narrative tags on coin boxes (SUPERSEDED by amendment — deferred).** Coin boxes carry no narrative tag in this scope.
6. **Narrative editor (Locked, A2: OQ-10 resolved; A3 refined).** Create, edit, delete narratives inside the app: a user-chosen name plus coins picked from the screener. The app persists them; the user never edits JSON. **(A3)** A coin can be put in a narrative only if it is currently on the screener; the app refuses anything else with a clear message (see outcome 22).
7. **/narrative page (Locked, amended).** Per source, show raw attention level and change only. No flags, no trust weight. Missing, partial or insufficient data is shown explicitly (see items 15–16).
8. **BTC leg strip (Locked).** At the top of the screener: BTC price history, leg periods shaded, leg-boundary dates marked. The existing leg-boundary maths feeds it as plain data. The per-coin leg tag is deleted.
9. **Refresh (Locked).** On page load, any coin whose data is older than 15 minutes is refreshed. No background job is required for this.
10. **Lean data (Locked).** Keep about 2 days (~200 bars) of 15m history per coin. Other timeframes keep only what their RSI and price line need. Anything fetched or stored that no page displays is removed. **(A2) Hard cap: the crypto screener holds NOT MORE THAN 30 coins at any moment (OQ-1 resolved); refresh sizing, spaghetti chart, groups and tests all use 30.**
11. **Equities page (Locked, amended).** A separate section/page showing LSE equity data with an "Add" button; the user picks the tickers (no preset list). Used under LSE's private-use terms.
12. **Other pages stay (Locked, amended).** /regime, /narrative, /pairs, /onchain remain. Their data stays, including the /pairs significance banner and p-value ranking, the /regime composite liquidity index, and status/data-quality labels (onchain floor/ramp, pairs status banners). Only verdict-style outputs on the removed-list (item 1) go.
13. **Dropped (Locked).** The standalone charts/indicators page is not built; RSI on the screener replaces it.
14. **Spaghetti chart (Locked, new; replaces the benchmark relative-performance chart).** One chart, a line per coin, each showing % change from the start of the currently selected timeframe (each coin measured on its own window, anchored at 0%). BTC and HYPE appear as reference lines. All screener coins appear by default; each can be toggled off/on and the toggle state persists. A coin added to the screener appears automatically; a removed coin disappears. Switching timeframe re-anchors every line. Visual comparison only: no computed "outperforming" label or ranking text.
15. **Clean /narrative data (Locked, new).** Only raw attention levels/changes per source. Where a source has missing, partial or insufficient data, the view says so explicitly. No zero-fill, no silently wrong numbers.
16. **Data-quality guarantees kept in scope (Locked, new).** The pytrends partial-hour fix (incomplete current-hour readings never archived as real values) and the nightly archive of non-refetchable history stay in scope and must keep working.
17. **Scalp view removed (Locked, new).** Only the drill-down "Scalp PASS/FAIL" view is deleted (code, tests, docs). Drill-down price and RSI stay.
18. **30-coin cap (Locked, A2, new).** Adding a 31st coin to the crypto screener is refused with a clear message (for example "Screener is full: 30 coins maximum. Remove a coin to add another."); nothing is added and the board is unchanged. The cap applies to the crypto screener only; the LSE equities section is not capped and its size stays unspecified.
19. **/narrative purpose and time scale (Locked, A3; replaces the A2 placeholder).** The page exists so the user can see which narratives are RISING and which are the HOTTEST at any given moment, at a DAILY time scale (one point per day per narrative). The page has two views, in this order: view 1 (starting point) the narrative spaghetti chart (outcome 20); view 2 the mindshare view (outcome 21). Which extra raw views, if any, stay or go remains under review (OQ-11); AC-24 and AC-25 stay binding meanwhile.
20. **Narrative spaghetti chart — view 1 (Locked, A3; A4: aggregation decided).** One chart, one line per narrative. **(A4)** A narrative's line is the equal-weight average of its member coins' performance, with every coin counting the same, rebased to 100 at the start of the selected daily window. Market-cap weighting is not offered. A coin with shorter history than the window, or with no price data (no OHLCV), is NOT silently dropped: the basket states how many of its member coins it covers and which are missing. Visual comparison only: no computed "outperforming" label, rank text or "rising/hottest" verdict.
21. **Narrative mindshare — view 2 (Locked, A3; A4: aggregation decided; inputs Open per OQ-12).** **(A4)** At daily resolution, per source: each narrative's attention value is expressed as its share of the total across all narratives that day. The per-narrative figure is the average of those shares across the sources that are present that day (the same method as today's mindshare view). Raw per-source values are always visible alongside the share. Per-source raw values and explicit missing-data states (outcome 15) still apply; no flag, label or trust weight. What each source measures per coin (coin-level versus keyword-level) and which sources are used is open: OQ-12.
22. **Basket membership rule (Locked, A3; A4: overlap and removal decided).** A narrative can contain only coins that are currently on the screener. Adding any other coin to a narrative is refused, in the UI and in the API, with a clear message. The user picks the narrative name freely. **(A4)** One coin may belong to several narratives at the same time; each narrative is computed independently and the app never sums figures across narratives. **(A4)** When a coin is removed from the screener, it is removed from every narrative that contained it, and the UI tells the user which narratives were affected (the rule "narratives only hold screener coins" always holds).
23. **Old narrative model replaced (Locked direction, A3; design Open).** The earlier keyword/category-based narrative model (the hand-maintained category map and the seed categories ai, rwa, l2s, memecoins) is replaced by user-defined coin baskets. See the Impact Surface item marked "direction locked, design open".

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
   +--> Add / remove coin  (A2: 31st coin --> refused, "30 coins maximum" message, board unchanged)
   |        (A4: remove coin --> also removed from ALL narratives, UI lists which)
   +--> Create / rename / delete group
   +--> Failure: data unavailable --> box says "no data" (never 0 or blank number)

/narrative  (A3/A4)  purpose: which narratives are RISING / HOTTEST, daily
   |
   +--> Narrative editor: [New narrative] name + pick coins
   |        coin ON screener  --> added to basket (same coin may be in several narratives, A4)
   |        coin NOT on screener --> refused, clear message, basket unchanged
   |
   +--> VIEW 1 (start): narrative spaghetti chart
   |        one line per narrative = EQUAL-WEIGHT average of member coins' performance
   |        rebased to 100 at window start, daily points (A4)
   |        basket says "covers N of M coins" + lists missing / short-history coins
   |        visual only, no "outperforming" label
   |
   +--> VIEW 2: mindshare per narrative
   |        per source: narrative value / total of all narratives that day = share
   |        figure = average of shares over sources PRESENT that day (A4)
   |        raw per-source values always visible; inputs per OQ-12 (open)
   |
   +--> source / coin missing, partial, insufficient --> explicit label (never 0, never silent)

/equities (LSE): [Add ticker] --> user-picked tickers listed; private-use note shown

Separate pages: /narrative /regime /pairs /onchain /equities
Retired outputs: confidence, agreement, trend tag, momentum/scalp PASS/FAIL, leg tag,
                 narrative state flags, trust weight, narrative tag on coin boxes (deferred),
                 keyword/category narrative model (replaced by coin baskets, A3)
```

## Acceptance Criteria (Testable Outcomes)

Strategy tags: FA = Fully-Automated, HY = Hybrid, AP = Agent-Probe. Scenarios come from the existing test surfaces: pytest (`api/tests/{analytics,data,routers,scripts}`), vitest (`web/components/*/__tests__`, `web/lib/__tests__`), Playwright (`web/e2e/*.spec.ts`), plus the repo validators.

Note: the 20-criteria cap is exceeded by Amendments 1 to 4 (see their concerns). IDs are not renumbered; AC-10 is superseded, AC-21 to AC-25 are new (A1), AC-26 is new (A2), AC-27 to AC-29 are new (A3), AC-30 to AC-33 are new (A4).

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

**AC-9 (Locked, A2: no longer pending; A3 refined) Narratives CRUD in app.** User can create, edit, delete a narrative (a user-chosen name plus a list of coins from the screener) in the UI; changes persist and need no file editing. OQ-10 resolved: the user wants the narrative section. **(A3)** Coin membership follows AC-27.
- proven by: pytest router/persistence tests; Playwright CRUD flow. strategy: FA

**AC-10 (SUPERSEDED by amendment — narrative tag deferred) Narrative tags.** Original: every coin in a narrative shows a tag with narrative name and raw attention change. No longer required; AC-1 now asserts that no narrative tag appears on coin boxes.
- proven by: n/a (superseded; replaced by AC-1 absence assertion). strategy: FA

**AC-11 (Locked, amended) /narrative is raw-only.** The page and its API show per-source attention level and change; `triggered`, `confirmed`, `trust_weight` and any flag appear nowhere in responses, types or UI. Existing `/api/narrative/categories` verdict contract is retired with its snapshot test.
- proven by: pytest response-shape tests; vitest; `narrative.spec.ts`. strategy: FA

**AC-12 (Locked) BTC leg strip.** Top of the screener renders BTC price history with shaded legs and marked boundary dates; the per-coin leg tag is absent.
- proven by: pytest leg-strip payload test using existing leg-boundary maths; Playwright asserting strip present with shaded regions and date markers on seeded data. strategy: FA (visual correctness of shading: HY, user eyeball once)

**AC-13 (Locked) 15-minute refresh on load.** Loading the page refreshes only coins whose stored data is older than 15 minutes; fresher coins are not refetched.
- proven by: pytest staleness test with a controlled clock and mocked exchange adapter; Playwright with seeded stale/fresh coins. Live exchange behaviour at the 30-coin cap (A2): agent-probe on user PC (rate-limit check). strategy: HY

**AC-14 (Locked, A2: sized for 30 coins) Lean storage.** Per coin, 15m history is capped near 200 bars (~2 days); other timeframes retain only what RSI and the price line need; no cache file exists for data no page displays. History that cannot be re-fetched (nightly snapshots, OQ-8 adopted) is exempt.
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

**AC-21 (Locked, new; A2: legible at 30 coins) Spaghetti chart content.** The screener shows one chart with a line per screener coin, each plotting % change from the start of the currently selected timeframe, with every line starting at 0%; BTC and HYPE are drawn as distinguishable reference lines; all screener coins are shown by default; no text label or ranking states that any coin is "outperforming" or "underperforming".
- proven by: pytest series-payload test (per-coin % change from its own window start, 0% anchor) on seeded bars; vitest chart render test (line count, reference lines, absence of comparative wording); Playwright asserting the chart and reference lines render on seeded data. strategy: FA (readability of the visual: HY, user eyeball once)

**AC-22 (Locked, new) Per-coin toggles persist.** The user can toggle each coin's line off and on individually; the choice survives a page reload.
- proven by: vitest toggle-state test; pytest or storage persistence test for the saved state; Playwright toggle, reload and assert. strategy: FA

**AC-23 (Locked, new) Chart follows the board and the timeframe.** A coin added to the screener appears on the spaghetti chart automatically; a removed coin disappears; switching timeframe re-anchors every line to 0% at the new window start; a coin with too little data for the window shows an explicit "no data" entry, not a flat zero line.
- proven by: Playwright add coin / remove coin / switch each timeframe on seeded data; pytest short-window case. strategy: FA

**AC-24 (Locked, new) /narrative data is clean and honest.** For each source, /narrative shows only raw level and change; any missing, partial or insufficient reading is shown with an explicit visible state and is never rendered as 0, filled in, or silently averaged; no flag or trust weight exists on the page or API. **(A3)** This also binds the new views: a narrative whose coins have missing or partial data in a day shows that state explicitly, and a basket or mindshare figure is never silently computed over fewer coins than the narrative contains without saying so.
- proven by: pytest tests with missing, partial and short-history fixtures per source (and per-coin gaps inside a narrative); vitest render of each explicit state; `narrative.spec.ts` seeded with a gap scenario. strategy: FA

**AC-25 (Locked, new) Data-quality fix and archive stay intact.** An incomplete current-hour pytrends reading is never archived as a real value (it yields "unavailable", not 0), and the nightly archive of non-refetchable history still writes one point per source per day.
- proven by: existing and retained `api/tests/data/test_pytrends_adapter.py` partial-hour cases; archive-writer pytest tests in `api/tests/scripts/`; workflow-schedule guard test stays green. strategy: FA

**AC-26 (Locked, A2, new) Hard cap of 30 coins.** With 30 coins on the screener, attempting to add a 31st is refused with a clear, visible message; the coin is not added, the board, groups and spaghetti chart are unchanged, and the refusal is also enforced by the API (not only the UI). Removing a coin then allows an add again. The cap does not apply to the LSE equities page.
- proven by: pytest watchlist router test (30 accepted, 31st rejected with a clear error, count stays 30, remove-then-add succeeds); vitest message render; Playwright add-31st flow on a seeded 30-coin board. strategy: FA

**AC-27 (Locked, A3, new) Narrative coins must be on the screener.** A coin can be added to a narrative only if it is currently on the screener. Attempting to add a coin that is not on the screener is refused with a clear message, in the UI and in the API; the narrative is unchanged. The user can name a narrative anything; narrative names are not limited to a fixed list.
- proven by: pytest narrative router test (screener coin accepted, non-screener coin rejected with a clear error and no change, free-text name accepted); vitest message render; Playwright add-coin-to-narrative flow on a seeded board including a non-screener coin attempt. strategy: FA

**AC-28 (Locked, A3; A4: aggregation fixed) Narrative spaghetti chart.** /narrative shows, as its first view, one chart with one line per narrative, each line plotting the equal-weight basket performance of that narrative's coins (AC-30) at daily resolution over the selected window, rebased to 100 at the window start; adding, editing or deleting a narrative updates the chart; a narrative with no coins or insufficient data shows an explicit state, not a flat line; no label, ranking text or colour state asserts that a narrative is "outperforming", "underperforming", "rising" or "hottest".
- proven by: pytest basket-series payload test on seeded daily bars (line per narrative, rebased to 100 at window start, daily points); vitest chart render test (line count, absence of comparative wording, empty and insufficient states); Playwright `narrative.spec.ts` creating narratives from seeded screener coins and asserting the lines render. strategy: FA (readability of the visual: HY, user eyeball once)

**AC-29 (Locked, A3; A4: aggregation fixed; inputs per OQ-12) Narrative mindshare view.** /narrative shows, as its second view, a mindshare figure per narrative at daily resolution, computed as in AC-33; each figure keeps its per-source and per-coin raw values visible or reachable; any coin or source with missing, partial or insufficient data is marked explicitly and the figure states how many of the narrative's coins it covers; no flag, state label or trust weight appears.
- proven by: pytest per-coin-to-narrative combination test on seeded per-coin attention series (including a missing-coin case); vitest render of the coverage and explicit-gap states; Playwright `narrative.spec.ts` on seeded attention data with a gap scenario. Live per-coin attention availability from the OQ-12 signals: agent-probe on user PC (the sandbox egress proxy blocks these providers). strategy: HY

**AC-30 (Locked, A4, new) Equal-weight basket arithmetic and honest coverage.** For a seeded narrative, each day's basket value equals the simple mean of its covered member coins' price rebased to 100 at the window start (every covered coin has identical weight; no market-cap weighting exists anywhere); a coin whose history is shorter than the window, or that has no OHLCV, is not silently dropped: the basket shows "covers N of M coins" and names the missing coins, and the figure is computed over the covered coins only with that statement visible. A basket with zero covered coins shows an explicit "no data" state.
- proven by: pytest basket test with hand-computed expected values for a 3-coin narrative (full coverage), the same narrative with one short-history coin and with one no-OHLCV coin (expected mean over the covered coins plus the coverage count and missing-coin list), and a zero-coverage case; vitest render of the "covers N of M" text and missing-coin list; Playwright on a seeded narrative with one missing coin. strategy: FA

**AC-31 (Locked, A4, new) One coin in several narratives.** The same screener coin can be added to two or more narratives; each narrative's basket and mindshare figures are computed independently and include that coin; no figure in the API or UI sums values across narratives; the editor and charts render overlapping narratives without error.
- proven by: pytest narrative router and basket tests (coin accepted into two narratives, each basket includes it, no cross-narrative total in any payload); vitest overlap render; Playwright creating two narratives sharing a coin and asserting both lines render. strategy: FA

**AC-32 (Locked, A4, new) Removing a screener coin cascades to all narratives.** When a coin is removed from the screener, it is removed from every narrative that contained it, in the same operation and enforced by the API (not only the UI); the UI shows a visible notice naming the narratives affected; afterwards no narrative contains a coin that is not on the screener, and a narrative left with no coins shows the explicit empty state (it is not auto-deleted). If the coin was in no narrative, no notice about narratives is shown.
- proven by: pytest watchlist/narrative router test (remove a coin held by two narratives: both updated, response lists them, invariant holds; remove a coin in no narrative: no narratives touched); vitest notice render; Playwright removing a shared coin and asserting the notice and the updated baskets. strategy: FA

**AC-33 (Locked, A4, new) Share-of-total mindshare arithmetic.** For each day and each source present that day, a narrative's value is its attention for that source divided by the sum of all narratives' values for that source that day (a share of 0 to 100%); the narrative's mindshare figure is the mean of its shares over the sources present that day (a source absent for the day is excluded and named as absent, not counted as zero); raw per-source values stay visible beside the shares. A day with no source present shows an explicit "no data" state.
- proven by: pytest combination test with hand-computed expectations (3 narratives, 3 sources; then one source absent; then no source present); vitest render of shares plus raw values and the absent-source note; Playwright on seeded attention data with a gap scenario. strategy: FA

## Impact Surface (what gets deleted / changed)

Names only, derived from reads. "Audit" = file likely carries verdict wording and must be checked in PLAN. Rows changed by Amendment 1 are marked (A1); by Amendment 3, (A3); by Amendment 4, (A4).

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
| API narrative | `api/analytics/narrative/trigger.py`, `scoring.py`, `mapping.py` | Delete/reduce trigger, confirmation, trust weight; mapping replaced by in-app narratives (OQ-10 resolved: wanted, A2) |
| API narrative | `api/routers/narrative.py`, `api/models/narrative.py` | Change: remove triggered/confirmed/trust_weight; explicit missing/partial/insufficient states; narrative CRUD (A2: no longer pending). **(A3)** CRUD enforces "coin must be on the screener"; new daily basket-performance and per-narrative mindshare payloads. **(A4)** Basket payload is equal-weight rebased to 100 with a coverage count and missing-coin list; mindshare payload is share-of-total averaged over present sources with raw values; a coin may be in several narratives; no cross-narrative totals |
| API narrative | **(A3) Narrative model: `api/analytics/narrative/narrative_config.py`, `api/data/narratives.json`, `narrative_categories.json`, `narrative_category_map.json`, the seed categories ai/rwa/l2s/memecoins** | **(A3) Replace the keyword/category-based model with user-defined coin baskets stored by the app. Direction locked, design open** (storage shape, source mapping per OQ-12). **(A4)** Aggregation, overlap and coin-removal behaviour are now decided (see outcomes 20, 21, 22). Previously-archived keyword/category history is not deleted (see Out Of Scope) |
| API narrative | `momentum.py`, `mindshare.py` (+ `MomentumView.tsx`, `MindshareView.tsx`) | Audit for state labels and for silent zero/average handling (A1). **(A3) The momentum view and the mindshare view are the natural homes for view 1 (basket spaghetti) and view 2 (per-narrative mindshare); whether they are reworked or replaced is decided in PLAN, since the aggregation rules are now fixed (A4)** |
| API data | `api/data/pytrends_adapter.py` and nightly archive scripts | **(A1) Keep: partial-hour fix and nightly archive are protected by AC-25.** (A3) Per-coin attention may need new fetch/archive paths; open (OQ-12) |
| Web narrative | `NarrativeDashboard.tsx`, `CategoryHistoryPanel.tsx`, `ComparisonView.tsx`, `ChangeInAttentionView.tsx`, `DataQualityCaveat.tsx` | Change/Audit: raw-only, explicit missing-data states (A1). **(A3) Add: narrative editor (name + screener-coin picker) and the two views above** |
| Web narrative | `RedistributionBadge.tsx` | Delete (licensing no longer a constraint; confirm in PLAN) |
| API data | `api/routers/watchlist.py`, `api/data/watchlist.py` | Change: groups, ordering; **(A2) enforce 30-coin cap with a clear refusal message**; **(A3) expose the screener coin list for narrative membership checks**; **(A4) removing a coin also removes it from all narratives and reports which** |
| API data | `api/data/cache.py`, `ccxt_adapter.py` | Change: 15-min staleness, retention trim |
| API data | New LSE adapter + user-ticker store; `l2beat`/`hyperliquid`/`etf_flows`/others carrying redistribution flags | Add LSE (user adds tickers, no preset list, A1); drop redistribution flags (Audit) |
| API scripts | `refresh_cache.py`, `backfill_primaries.py`, nightly workflows in `.github/workflows/` | Audit: remove fetches nothing displays; keep nightly history snapshots (OQ-8 adopted) |
| Other pages | `FloorRampStateLabel.tsx` (onchain), `ComputationStatusBanner.tsx` (pairs) | **(A1) Keep as data-quality labels** (resolves OQ-4) |
| Other pages | /pairs significance banner + p-value ranking; /regime composite index | **(A1) Keep as data** (resolves OQ-2, OQ-3) |
| Tests | `web/e2e/screener.spec.ts`, `narrative.spec.ts`, narrative contract-snapshot and tripwire tests | Update/Delete with the code they guard; add spaghetti and equities specs. **(A3) Narrative spec and tests rewritten for user-defined baskets** |
| Docs | `process/context/all-context.md` (1,223 lines), `process/MASTER-PLAN.md` (T10, T12, T15), `process/general-plans/active/momentum-screener_17-09-26/` SPEC/PLAN | Slim / rewrite / mark superseded |
| Docs (new) | North Star, current-state, task registry + worker report schema, archive index | Create |

## Out Of Scope

- Any signal generation, scoring, ranking-as-advice, or bullish/bearish output.
- Auth, billing, multi-tenancy, or opening the app to other users.
- New data providers other than LSE (no yfinance, no paid feeds). **(A3) Clarification:** this bars new market-price providers; which attention/mindshare platforms to use for /narrative is open (OQ-12) and is not decided by this line.
- Trade execution or order placement.
- A standalone charts/indicators page.
- Retroactive correction or deletion of already-archived narrative/LiqTide history files (history that cannot be refetched is kept unless the user says otherwise).
- Public deployment (Tailscale-only stays).
- **(A1) Narrative tag on screener coin boxes: deferred** until /narrative data shows whether trends give an actionable edge. Not built in this scope. **(A3) Still deferred.**
- **(A1) Any computed "outperforming/underperforming" label, score or ranking text** on the spaghetti chart; comparison is visual only. **(A3) Same for the narrative spaghetti chart and for "rising"/"hottest": the user reads these from the charts; the app computes no verdict.**
- **(A1) A preset equities ticker list.**
- **(A3) Narratives containing coins that are not on the screener, and a preset or fixed narrative list** (the old seed categories ai/rwa/l2s/memecoins are not kept as defaults).
- **(A4) Market-cap weighting (or median) of narrative baskets.** Equal weight is the only basket method.
- **(A4) Summing or ranking figures across narratives** (overlapping narratives would double count; the page never totals them).

## Constraints

- Personal use only; Tailscale-only access stays. LSE data is used under its private-use terms (ADOPT-WITH-LIMITS, per `process/MASTER-PLAN.md` T12; verdict lives on remote branch `claude/exciting-meitner-hy50kn`, not fetched here). The private-use note stays visible on the equities page.
- "Numbers are never silently wrong" stays: unavailable, partial or insufficient data shows an explicit state, never 0/NaN, never zero-filled (applies to the screener, spaghetti charts and /narrative).
- One source of numerical truth stays: RSI, % change, spaghetti series, basket and mindshare figures and leg data are computed in Python and rendered by the web app.
- Providers stay behind adapters under `api/data/`.
- **(A2) Hard cap: the crypto screener holds not more than 30 coins; a 31st add is refused (OQ-1 resolved).** Design target: 30 coins; ~200 bars of 15m per coin. The cap does not apply to the LSE equities section, whose size stays unspecified.
- Every requirement above must remain testable; no verdict logic may be reintroduced under another name.
- Nightly snapshot jobs for sources with no history (narrative, liqtide, chain-growth) stay on their current schedule (OQ-8 adopted).
- RSI: Wilder smoothing, period 14 (OQ-9 adopted).
- **(A1) Priority order for /narrative work: data cleanliness first; any further narrative feature waits on what the clean data shows.** **(A3) Refinement:** the daily rising/hottest purpose and the two views are Locked behaviour. **(A4)** Their aggregation rules are now Locked too; only the coin-level signal choice (OQ-12) waits on the research pass.
- **(A2) /narrative content is under review (OQ-11); AC-24 and AC-25 stay binding in the meantime (A3: unchanged).**
- **(A3) Narrative time scale is daily: one point per day per narrative. Narrative coins must be on the screener, so the 30-coin cap also bounds the total coins a narrative can use.**
- **(A3) Visual comparison only on /narrative: no computed outperforming, rising or hottest label.**
- **(A4) Basket method is equal weight rebased to 100 at the window start; mindshare is share-of-total per source averaged over present sources; raw per-source values are always visible; a coin may be in several narratives; removing a screener coin removes it from all narratives and the UI says so.**
- **(A4) No coin-level attention signal is chosen until the OQ-12 research pass has concluded** (free-tier availability, history depth, comparability across coins, personal-use terms).

## Open Questions

| # | Question | Owner | Status |
|---|---|---|---|
| OQ-1 | How many coins will you actually track? | user | **Resolved (A2): hard cap of 30 crypto coins at any moment; a 31st add is refused (AC-26). Not applied to LSE equities.** |
| OQ-2 | /pairs significance banner and p-value ranking. | user | **Resolved (A1): keep as data.** |
| OQ-3 | /regime composite liquidity index. | user | **Resolved (A1): keep as data.** |
| OQ-4 | /onchain `FloorRampStateLabel` and /pairs status banners. | user | **Resolved (A1): keep as data-quality labels.** |
| OQ-5 | Screener drill-down scalp PASS/FAIL view and BTC/HYPE benchmark relative-performance chart. | user | **Resolved (A1): scalp PASS/FAIL view deleted (price and RSI stay); benchmark chart replaced by the spaghetti chart with BTC and HYPE reference lines.** |
| OQ-6 | Exact narrative attention figure on the coin tag. | user | **Resolved (A1): moot — narrative tag deferred.** |
| OQ-7 | Equities tickers, timeframes, RSI/groups. | user | **Resolved (A1): user picks tickers with an Add button, no preset list.** Whether the equities page also needs timeframes/RSI/groups is not stated; PLAN assumes the same price, % change and RSI box as crypto unless the user says otherwise. |
| OQ-8 | Nightly narrative/liqtide/chain-growth snapshots. | user | **Resolved (A1, default adopted): keep nightly snapshots of history that cannot be re-fetched.** |
| OQ-9 | RSI smoothing method. | user | **Resolved (A1, default adopted): Wilder smoothing, period 14.** |
| OQ-10 | With the narrative tag deferred, do you still want in-app narrative create/edit/delete? | user | **Resolved (A2): yes, the narrative section is wanted ("very useful to track the narrative"); in-app create/edit/delete stays Locked. The screener narrative TAG remains deferred.** |
| OQ-11 | Narrative data design: which raw views/sources should the /narrative page show to be genuinely useful? | user, after research | **Open (A2; A3 linked; A4 narrowed).** A3 locked purpose and the two views; A4 locked basket weighting, mindshare aggregation, overlap and removal behaviour. What remains is only the signal/platform choice (OQ-12) plus whether any extra raw views stay beyond the two views and AC-24/AC-25. |
| OQ-12 | (A3, new; A4: scope fixed) Which signals can supply coin-level attention, and in what form (per coin, or per keyword mapped to a coin)? **Exact scope of the research pass (A4):** (1) Hyperliquid volume, (2) Google Trends per coin, (3) Reddit mentions, (4) X, YouTube and Telegram. For each: free-tier availability, history depth and refetchability, comparability across coins, and personal-use terms. | research, then user | **Open (A4).** A research pass must conclude before any signal is chosen. **Known risk flagged:** Google Trends per-coin comparability. Trends values are on a relative 0-100 scale per request, at most 5 terms per request, and cross-request comparison needs anchor-chaining, which can rescale a term to near 0 against a larger anchor (the repo already saw a `0.0` that meant "below the anchor's resolution"). Per-coin Trends figures may therefore not be comparable across coins; the research must test this before Trends is chosen. CoinGecko is not in the user's list for this pass; whether it stays as a source is not decided here. Recommended default if the user wants to skip: keep the existing sources as they are and add a signal only if the research shows free, per-coin, daily data. |
| OQ-13 | (A3) How is a narrative's basket line computed? | user | **Resolved (A4): equal weight, rebased to 100 at the window start; coins with shorter history or no OHLCV are not silently dropped (coverage stated, missing coins named); market-cap weighting out of scope (outcome 20, AC-28, AC-30).** The daily window choices (for example 7d / 30d / 90d) are split off as OQ-17. |
| OQ-14 | (A3) How is per-coin mindshare combined into a per-narrative figure? | user | **Resolved (A4): share of total. Per source, each narrative's value as a share of all narratives that day; the figure is the average of shares across the sources present; raw per-source values always visible (outcome 21, AC-29, AC-33).** The per-coin versus per-keyword input question stays open inside OQ-12. |
| OQ-15 | (A3) May one coin belong to several narratives? | user | **Resolved (A4): yes, overlap allowed (outcome 22, US-19, AC-31).** |
| OQ-16 | (A3) When a coin is removed from the screener, what happens to the narratives that contain it? | user | **Resolved (A4, stricter behaviour picked by the SPEC author from the user's two stated options): the removal removes the coin from ALL narratives in the same operation, enforced by the API, AND the UI states which narratives were affected (AC-32).** Chosen because it keeps the "narratives only hold screener coins" rule always true and is fully testable; the user can override at the confirm gate. |
| OQ-17 | (A4, new, minor) Which daily windows does the narrative spaghetti chart offer? | user | **Open (A4).** Recommended default: 7d, 30d and 90d, switchable, with 30d as the starting window. PLAN uses this default unless the user says otherwise. |

Handling (A4): only OQ-11 (narrowed), OQ-12 (research-gated) and OQ-17 (minor, defaulted) remain open. None of them blocks the Locked screener, spaghetti, equities, cap or docs work, nor the basket chart, overlap and removal work. They gate only the choice of coin-level attention signals for the mindshare view's inputs.

## Background / Research Findings

- Old product north star: "turn separate signals into a confidence level that drives position sizing"; audience "personal first, other users later." Both replaced by user decisions 1 and 7 of the first session.
- Today's screener contract (`web/lib/types/screener.ts`, `api/models/screener.py`) carries `momentum`, `trend`, `confidence`, `leg_context`, `narrative_state` per coin; these are the fields being removed. Per-coin chart, `percent_change_by_timeframe` and the five timeframes already exist and stay.
- A watchlist add/remove API already exists (`api/routers/watchlist.py`); groups and ordering do not.
- Narratives are currently defined in hand-edited `api/data/narratives.json` (from narrative-v2) and a keyword/category map with seed categories ai, rwa, l2s, memecoins; `/narrative` and `/categories` expose `triggered`, `confirmed`, `trust_weight` (`api/analytics/narrative/trigger.py`). Existing adapters archive pytrends and Reddit history keyed by keyword, not by coin (`all-context.md`), which is why per-coin attention availability is a research question (OQ-12).
- Leg-boundary maths lives in `api/analytics/regime/leg_boundary.py` and is reusable as chart data.
- No RSI indicator module currently exists under `api/analytics/indicators/` (only momentum and trend).
- `process/context/all-context.md` is 1,223 lines, ~65% changelog; `process/MASTER-PLAN.md` is stale and not linked from entry points; no task registry, worker report schema or archive index exists (Gate 0 audit).
- The earlier momentum-screener SPEC (`process/general-plans/active/momentum-screener_17-09-26/momentum-screener_SPEC_17-09-26.md`, esp. US-3, US-5, US-6, US-7) is superseded by this SPEC where they conflict; it should be marked so, not edited, until a later phase.
- Pytrends partial-hour fix and nightly archive exist from earlier work (2026-09-28 / 2026-10-01 entries in `all-context.md`); they are carried forward as protected guarantees (AC-25).
- Pytrends anchor-chaining is already used in the repo (batched fetch with an anchor term, 5 terms per request); `all-context.md` records a case where `pytrends/RWA crypto` was 74.0 while the blended RWA figure was 0.0 written as fresh. This is the concrete basis for the Google Trends per-coin comparability risk in OQ-12.
- User input, verbatim intent: "personal-use-only tracking system"; "show data as clearly as possible so the user draws market conclusions"; "must NOT compute or display bullish/bearish verdicts." Amendment 1: "hammer on clean data" (priority for /narrative before any narrative tag).
- Amendment 3 user intent (paraphrased from the answers): the /narrative section exists to see which narratives are rising and which are the hottest at any given moment, daily; narratives are chosen by the user, who picks coins from the screener and classifies them under a narrative of their choosing; view 1 is a spaghetti chart of narrative baskets (visual comparison only); view 2 is mindshare per narrative derived from each coin and aggregated.
- Amendment 4 user answers (authoritative): basket performance is equal weight, rebased to 100 at the window start, market-cap weighting out of scope; a coin may be in several narratives; mindshare is share of total per source, averaged across present sources, raw per-source values always visible (same method as today's mindshare view); signals to research for coin-level attention are Hyperliquid volume, Google Trends per coin, Reddit mentions, and X/YouTube/Telegram.

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

## Amendment 2 (02-10-26, user answers)

Source: two user answers. They override earlier text where they conflict. No IDs renumbered; changes are marked "(A2)" in place.

**What changed**

| Topic | Change |
|---|---|
| Coin cap (OQ-1 resolved) | The crypto screener holds NOT MORE THAN 30 coins at any moment. The earlier ~50 design ceiling is replaced everywhere by a hard cap of 30 (outcome 10, AC-13, AC-14, AC-21, Constraints). A 31st add is refused with a clear message: new outcome 18, new US-14, new AC-26 (also enforced by the API). Refresh sizing, spaghetti chart, groups and tests use 30. |
| Cap scope | Crypto screener only. The LSE equities section is not capped; its size stays unspecified. |
| Narrative section (OQ-10 resolved) | The user still wants the /narrative page ("very useful to track the narrative"). In-app narrative create/edit/delete stays Locked ("pending OQ-10" removed from US-5b, outcome 6, AC-9, Impact Surface). The screener narrative TAG remains deferred. |
| Narrative data design (new OQ-11) | The user said "maybe we have to think deeper on what data it's showing". OQ-11 asks which raw views/sources /narrative should show to be genuinely useful; Open until a read-only research pass on current narrative data quality is returned. |

**Narrative data deep-dive (placeholder requirement).** The narrative page's content is under review. Until OQ-11 is answered, no narrative view is added or removed by this SPEC, and the data-cleanliness criteria AC-24 (clean, honest, explicit missing/partial/insufficient states) and AC-25 (pytrends partial-hour fix and nightly archive intact) stay binding. A later amendment will replace this placeholder with concrete requirements once the research is in. **(A3: partly replaced, see Amendment 3.)**

**Concerns:** (1) Active criteria now 25 (AC-1 to AC-9, AC-11 to AC-26), well above the 20 cap; recommend accepting at the confirm gate or splitting into two SPECs (screener vs narrative). (2) Equities page size is unspecified, so its refresh load is unbounded by this SPEC; PLAN should note a sensible fetch strategy. (3) A 30-coin cap vs a larger existing watchlist: if the current watchlist already exceeds 30, PLAN must decide how existing extras are handled (not stated by the user).

**Remaining open questions:** OQ-11 only.

## Amendment 3 (02-10-26, user answers)

Source: user answers refining OQ-11 and the narrative requirements. They override earlier text where they conflict. No IDs renumbered or deleted; changes are marked "(A3)" in place.

**What changed**

| Topic | Change |
|---|---|
| Purpose and time scale | /narrative exists to show which narratives are RISING and which are the HOTTEST at any moment, at a DAILY time scale. New US-15, outcome 19 (replaces the A2 placeholder). |
| User-defined narratives | A narrative is a user-named basket of coins picked from the screener. US-5b, outcome 6, AC-9 refined; new US-18, outcome 22 and AC-27 (a coin may be in a narrative only if it is on the screener; enforced in UI and API; free-text names). |
| View 1: narrative spaghetti | Starting view: one line per narrative = performance of its coin basket, daily, 0% anchor, visual comparison only (no computed "outperforming" label). New US-16, outcome 20, AC-28. Aggregation (for example equal-weight % change from the window start) is open: OQ-13. |
| View 2: mindshare | Per-narrative mindshare derived from each coin and combined (sum or another sound aggregation). Sources kept: CoinGecko, Google Trends, Reddit and others. New US-17, outcome 21, AC-29. Aggregation and platforms open: OQ-12, OQ-14, after a research pass. |
| Old model replaced | The keyword/category-based narrative model (category map, seed categories ai/rwa/l2s/memecoins) is replaced by user-defined coin baskets. Added to Impact Surface as "direction locked, design open"; outcome 23; Out Of Scope updated. |
| Screener narrative tag | Still deferred. |
| Data cleanliness | AC-24 and AC-25 stay binding; AC-24 extended to cover per-coin gaps inside narratives. |
| Open questions | OQ-11 stays open and is linked to new OQ-12 (platforms and feasibility), OQ-13 (basket aggregation and windows), OQ-14 (mindshare aggregation), OQ-15 (one coin in several narratives; recommended: allow), OQ-16 (coin removed from screener; recommended: auto-remove with notice). |

**Superseded by this amendment:** outcome 19's A2 "placeholder, no new views" wording (replaced by the two locked views); the keyword/category narrative model as a design basis.

**Concerns:** (1) Active criteria are now 28 (AC-1 to AC-9, AC-11 to AC-29), far above the 20 cap; strongly recommend splitting the narrative work (US-5b, US-6, US-13, US-15 to US-18, AC-9, AC-11, AC-24 to AC-25, AC-27 to AC-29) into its own SPEC and plan, since its design is still open while the screener work is ready to plan. (2) AC-28 and AC-29 lock behaviour but not numbers; their numeric expectations are fixed only after OQ-13 and OQ-14 are answered, so PLAN for the narrative part should wait for that. (3) Per-coin attention may not exist at daily resolution on the free sources (the current archive is keyed by keyword, not coin); if the research pass shows it does not, view 2 may have to use a keyword-per-coin approach or fewer sources. A feasibility probe may be needed on the user's PC because the sandbox blocks these providers. (4) The 30-coin cap bounds narrative size; existing seeded narratives and archived keyword history are not migrated or deleted by this SPEC.

**Remaining open questions:** OQ-11 (linked), OQ-12, OQ-13, OQ-14, OQ-15, OQ-16.

## Amendment 4 (02-10-26, user answers)

Source: four user answers resolving the open narrative questions. They override earlier text where they conflict. No IDs renumbered or deleted; changes are marked "(A4)" in place.

**What changed**

| Topic | Change |
|---|---|
| Basket performance (OQ-13) | Locked: equal weight, rebased to 100 at the window start. Market-cap weighting is out of scope. Coins with shorter history or no OHLCV are not silently dropped; the basket states how many member coins it covers and which are missing. Outcome 20, AC-28 amended; new AC-30 (arithmetic and coverage). Window choices split off as OQ-17. |
| Overlap (OQ-15) | Locked: one coin may belong to several narratives. New US-19, outcome 22 amended, new AC-31. No cross-narrative totals. |
| Coin removal (OQ-16) | Stricter testable behaviour chosen: removing a screener coin removes it from ALL narratives (API-enforced) and the UI names the affected narratives. New AC-32. Marked as the SPEC author's pick between the user's two options, overridable at the confirm gate. |
| Mindshare aggregation (OQ-14) | Locked: share of total. Per source, each narrative's value as a share of all narratives that day; averaged across the sources present; raw per-source values always visible. Outcome 21, AC-29 amended; new AC-33. The per-coin versus per-keyword input question stays inside OQ-12. |
| Attention signals (OQ-12) | Stays OPEN with this exact research scope: Hyperliquid volume, Google Trends per coin, Reddit mentions, X/YouTube/Telegram. A research pass (free-tier availability, history, comparability across coins, personal-use terms) must conclude before any signal is chosen. Google Trends per-coin comparability (0-100 relative scale, 5-term batching, anchor-chaining) flagged as a known risk. |
| Impact Surface / Out Of Scope / Constraints / Flow diagram | Updated as marked "(A4)" above. Out Of Scope gains market-cap weighting and cross-narrative totals. |

**Superseded by this amendment:** the A3 "aggregation open" wording on outcomes 20 and 21, AC-28, AC-29 and the Impact Surface rows; OQ-13, OQ-14, OQ-15, OQ-16 as open questions (now resolved).

**Concerns:** (1) Active criteria are now 32 (AC-1 to AC-9, AC-11 to AC-33), far above the 20 cap; the earlier recommendation stands: split the narrative work into its own SPEC and plan. Its design is now mostly decided, so that split is cheap. (2) The user's research list for OQ-12 omits CoinGecko, which the earlier answers kept as a source; PLAN must not drop it silently. Confirm whether it stays. (3) Share-of-total with overlapping narratives means a coin's attention counts in every narrative containing it; this is intended (no totals are shown across narratives) but means shares are relative within the user's own narrative set, not market-wide. (4) The mindshare view's figures cannot be filled with real data until OQ-12 concludes; AC-33's arithmetic is testable on seeded data now, but the live-data probe is on the user's PC (sandbox blocks the providers).

**Remaining open questions:** OQ-11 (narrowed to extra raw views only), OQ-12 (research-gated), OQ-17 (minor, defaulted to 7d/30d/90d).
