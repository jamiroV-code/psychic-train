---
name: spec:personal-tracker-realignment
description: "Realign my_site from a confidence/verdict screener to a personal-use data-display tracker: slimmer screener with RSI, groups and a spaghetti comparison chart, BTC leg strip, clean /narrative data built on user-defined coin baskets (daily rising/hottest view), user-picked LSE equities page, label purge, and a rewritten North Star + slimmed docs (Amendments 1, 2 and 3 applied 02-10-26)"
date: 02-10-26
feature: general-plans
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Personal Tracker Realignment — SPEC

**TL;DR:** my_site stops telling the user what to think. It becomes a personal, Tailscale-only dashboard that shows clean data (price, % change, RSI, raw attention levels, BTC legs) so the user draws their own conclusions. All verdict-style output (confidence badges, bullish/bearish tags, scalp PASS/FAIL, trust weights, "triggered/confirmed" flags) is deleted, not hidden. The screener gets coin groups, an RSI row and a "spaghetti" chart comparing every coin's % change against BTC and HYPE. **Amendment 1:** the narrative tag on coin boxes is deferred until /narrative proves it is useful. **Amendment 3:** /narrative exists to show, daily, which narratives are RISING and which are HOTTEST; narratives become coin baskets the user builds from screener coins (replacing the old keyword/category model), with a spaghetti chart of basket performance as the starting view and a per-narrative mindshare view second. How baskets and mindshare are aggregated, and which platforms to track, is still open pending a research pass. Equities come in via LSE on their own page where the user picks the tickers. The docs get a new North Star and a slim, current entry point.

Status key used below: **Locked** = user decided, build to it. **Open** = needs a user answer before it can be planned. **SUPERSEDED by amendment** = kept for traceability, no longer a requirement (see `## Amendment 1`). **(A3)** marks text changed or added by Amendment 3.

---

## Summary

The original product goal was "turn separate signals into one confidence level that drives position sizing." The user has replaced that goal. The app is now a **personal-use-only tracking system** whose job is to **show data as clearly as possible** so the user reaches their own market conclusions. The app must not compute or display any bullish/bearish call, confidence badge, signal-agreement, state/flag label or trust weight. "Open to other users later" is dropped, so redistribution/licensing stops being a design constraint (Tailscale-only access stays). The top-priority change is the screener: keep the small coin boxes, remove every verdict, add an RSI under each coin, and let the user manage coins and named groups from the UI. A BTC price-history strip with shaded legs sits at the top of the screener, and one spaghetti chart lets the user see every coin's % change from the start of the selected timeframe against BTC and HYPE reference lines (visual comparison only, no computed "outperforming" label). The narrative tag on coin boxes is deferred. **(A3)** The /narrative page has one job: let the user see, at a daily time scale, which narratives are rising and which are the hottest right now. A narrative is a basket the user defines by picking coins that are already on the screener and classifying them under a name of their choosing. The page starts with a spaghetti chart where each narrative's line is the performance of its basket (visual comparison only), and a second view shows mindshare per narrative derived from its coins. The aggregation methods and the platforms to track are open design questions answered after a research pass. Equities come in through LSE data on a separate page whose tickers the user adds. Finally, the project documents are rewritten so the new direction is the single clear source of truth.

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
- **US-16 (Locked, A3, new) Compare narrative baskets by eye.** I want a spaghetti chart where each narrative's line is the performance of its grouped coins, so I can see visually which narrative is outperforming or underperforming without the app telling me.
- **US-17 (Locked, A3, new) Mindshare per narrative.** I want a second view showing how much attention each narrative is getting, built up from the coins inside it, so I can tell when a narrative heats up before or after price moves.
- **US-18 (Locked, A3, new) Only coins I already track.** I want narratives to accept only coins that are on my screener, so every narrative coin has the same price data as the rest of my board.

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
19. **/narrative purpose and time scale (Locked, A3; replaces the A2 placeholder).** The page exists so the user can see which narratives are RISING and which are the HOTTEST at any given moment, at a DAILY time scale (one point per day per narrative). The page has two views, in this order: view 1 (starting point) the narrative spaghetti chart (outcome 20); view 2 the mindshare view (outcome 21). Which extra raw views, if any, stay or go, and how the figures are aggregated, remains under review (OQ-11 to OQ-14); AC-24 and AC-25 stay binding meanwhile.
20. **Narrative spaghetti chart — view 1 (Locked behaviour, A3, new; aggregation design Open per OQ-13).** One chart, one line per narrative. A narrative's line is the performance of its grouped coins as a basket, measured at daily resolution from the start of the selected window and anchored at 0%, so the user sees which narrative is outperforming or underperforming. Visual comparison only: no computed "outperforming" label, rank text or "rising/hottest" verdict (the user reads that from the chart). How coin performance is combined into one line (for example equal-weight % change from the window start) is an open design question.
21. **Narrative mindshare — view 2 (Locked behaviour, A3, new; aggregation design Open per OQ-12 and OQ-14).** For each narrative, show mindshare (attention) derived from each of its coins and combined into one figure per narrative (summed, or another logically sound aggregation, decided after a research pass), at daily resolution. Sources the user wants to keep using: CoinGecko, Google Trends, Reddit, and other big platforms ("etc."). Per-source raw values and explicit missing-data states (outcome 15) still apply; no flag, label or trust weight.
22. **Basket membership rule (Locked, A3, new).** A narrative can contain only coins that are currently on the screener. Adding any other coin to a narrative is refused, in the UI and in the API, with a clear message. The user picks the narrative name freely. Whether one coin may sit in several narratives is open (OQ-15); what happens to a narrative's membership when a coin is removed from the screener is open (OQ-16).
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
   +--> Create / rename / delete group
   +--> Failure: data unavailable --> box says "no data" (never 0 or blank number)

/narrative  (A3)  purpose: which narratives are RISING / HOTTEST, daily
   |
   +--> Narrative editor: [New narrative] name + pick coins
   |        coin ON screener  --> added to basket
   |        coin NOT on screener --> refused, clear message, basket unchanged
   |        (multi-membership: OQ-15 | coin removed from screener: OQ-16)
   |
   +--> VIEW 1 (start): narrative spaghetti chart
   |        one line per narrative = performance of its coin basket
   |        daily points, 0% anchor at window start (aggregation: OQ-13)
   |        visual only, no "outperforming" label
   |
   +--> VIEW 2: mindshare per narrative
   |        per-coin attention --> combined per narrative (sum or other: OQ-14)
   |        sources: CoinGecko, Google Trends, Reddit, others (OQ-12)
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

Note: the 20-criteria cap is exceeded by Amendments 1, 2 and 3 (see their concerns). IDs are not renumbered; AC-10 is superseded, AC-21 to AC-25 are new (A1), AC-26 is new (A2), AC-27 to AC-29 are new (A3).

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

**AC-28 (Locked behaviour, A3, new; aggregation per OQ-13) Narrative spaghetti chart.** /narrative shows, as its first view, one chart with one line per narrative, each line plotting the performance of that narrative's coin basket at daily resolution over the selected window, anchored at 0% at the window start; adding, editing or deleting a narrative updates the chart; a narrative with no coins or insufficient data shows an explicit state, not a flat line; no label, ranking text or colour state asserts that a narrative is "outperforming", "underperforming", "rising" or "hottest".
- proven by: pytest basket-series payload test on seeded daily bars (line per narrative, 0% anchor, daily points; the numeric expectation is fixed once OQ-13 is answered); vitest chart render test (line count, absence of comparative wording, empty and insufficient states); Playwright `narrative.spec.ts` creating narratives from seeded screener coins and asserting the lines render. strategy: FA (readability of the visual: HY, user eyeball once)

**AC-29 (Locked behaviour, A3, new; aggregation per OQ-12 and OQ-14) Narrative mindshare view.** /narrative shows, as its second view, a mindshare figure per narrative at daily resolution, built from the attention of each coin in the narrative and combined into one figure per narrative; each figure keeps its per-source and per-coin raw values visible or reachable; any coin or source with missing, partial or insufficient data is marked explicitly and the figure states how many of the narrative's coins it covers; no flag, state label or trust weight appears.
- proven by: pytest per-coin-to-narrative combination test on seeded per-coin attention series (including a missing-coin case; the numeric expectation is fixed once OQ-14 is answered); vitest render of the coverage and explicit-gap states; Playwright `narrative.spec.ts` on seeded attention data with a gap scenario. Live per-coin attention availability from CoinGecko, Google Trends, Reddit and others: agent-probe on user PC (the sandbox egress proxy blocks these providers; see OQ-12). strategy: HY

## Impact Surface (what gets deleted / changed)

Names only, derived from reads. "Audit" = file likely carries verdict wording and must be checked in PLAN. Rows changed by Amendment 1 are marked (A1); by Amendment 3, (A3).

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
| API narrative | `api/routers/narrative.py`, `api/models/narrative.py` | Change: remove triggered/confirmed/trust_weight; explicit missing/partial/insufficient states; narrative CRUD (A2: no longer pending). **(A3)** CRUD enforces "coin must be on the screener"; new daily basket-performance and per-narrative mindshare payloads |
| API narrative | **(A3) Narrative model: `api/analytics/narrative/narrative_config.py`, `api/data/narratives.json`, `narrative_categories.json`, `narrative_category_map.json`, the seed categories ai/rwa/l2s/memecoins** | **(A3) Replace the keyword/category-based model with user-defined coin baskets stored by the app. Direction locked, design open** (storage shape, aggregation per OQ-13/OQ-14, source mapping per OQ-12, multi-membership OQ-15, coin-removal behaviour OQ-16). Previously-archived keyword/category history is not deleted (see Out Of Scope) |
| API narrative | `momentum.py`, `mindshare.py` (+ `MomentumView.tsx`, `MindshareView.tsx`) | Audit for state labels and for silent zero/average handling (A1). **(A3) The momentum view and the mindshare view are the natural homes for view 1 (basket spaghetti) and view 2 (per-narrative mindshare); whether they are reworked or replaced is open until OQ-11 to OQ-14 are answered** |
| API data | `api/data/pytrends_adapter.py` and nightly archive scripts | **(A1) Keep: partial-hour fix and nightly archive are protected by AC-25.** (A3) Per-coin attention may need new fetch/archive paths; open (OQ-12) |
| Web narrative | `NarrativeDashboard.tsx`, `CategoryHistoryPanel.tsx`, `ComparisonView.tsx`, `ChangeInAttentionView.tsx`, `DataQualityCaveat.tsx` | Change/Audit: raw-only, explicit missing-data states (A1). **(A3) Add: narrative editor (name + screener-coin picker) and the two views above** |
| Web narrative | `RedistributionBadge.tsx` | Delete (licensing no longer a constraint; confirm in PLAN) |
| API data | `api/routers/watchlist.py`, `api/data/watchlist.py` | Change: groups, ordering; **(A2) enforce 30-coin cap with a clear refusal message**; **(A3) expose the screener coin list for narrative membership checks** |
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

## Constraints

- Personal use only; Tailscale-only access stays. LSE data is used under its private-use terms (ADOPT-WITH-LIMITS, per `process/MASTER-PLAN.md` T12; verdict lives on remote branch `claude/exciting-meitner-hy50kn`, not fetched here). The private-use note stays visible on the equities page.
- "Numbers are never silently wrong" stays: unavailable, partial or insufficient data shows an explicit state, never 0/NaN, never zero-filled (applies to the screener, spaghetti charts and /narrative).
- One source of numerical truth stays: RSI, % change, spaghetti series, basket and mindshare figures and leg data are computed in Python and rendered by the web app.
- Providers stay behind adapters under `api/data/`.
- **(A2) Hard cap: the crypto screener holds not more than 30 coins; a 31st add is refused (OQ-1 resolved).** Design target: 30 coins; ~200 bars of 15m per coin. The cap does not apply to the LSE equities section, whose size stays unspecified.
- Every requirement above must remain testable; no verdict logic may be reintroduced under another name.
- Nightly snapshot jobs for sources with no history (narrative, liqtide, chain-growth) stay on their current schedule (OQ-8 adopted).
- RSI: Wilder smoothing, period 14 (OQ-9 adopted).
- **(A1) Priority order for /narrative work: data cleanliness first; any further narrative feature waits on what the clean data shows.** **(A3) Refinement:** the daily rising/hottest purpose and the two views above are now Locked behaviour; their aggregation designs wait on the research pass (OQ-11 to OQ-14).
- **(A2) /narrative content is under review (OQ-11); AC-24 and AC-25 stay binding in the meantime (A3: unchanged).**
- **(A3) Narrative time scale is daily: one point per day per narrative. Narrative coins must be on the screener, so the 30-coin cap also bounds the total coins a narrative can use.**
- **(A3) Visual comparison only on /narrative: no computed outperforming, rising or hottest label.**

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
| OQ-11 | Narrative data design: which raw views/sources should the /narrative page show to be genuinely useful? (User: "maybe we have to think deeper on what data it's showing".) | user, after research | **Open (A2; A3: refined and linked to OQ-12 to OQ-16).** A3 locks the page's purpose (which narratives are rising and hottest, daily), the narratives-as-coin-baskets direction, view 1 (basket spaghetti) and view 2 (mindshare). Still open: the aggregation methods, platforms and the membership edge cases below. Answered after a read-only research pass on narrative data (current quality and per-coin availability) is returned. |
| OQ-12 | (A3, new) Which platforms and which behaviours on them make sense to track for mindshare? The user keeps CoinGecko, Google Trends and Reddit, adds "other big platforms (etc.)", and asked what behaviour is worth tracking. Includes the feasibility question of whether each source can give per-coin (not only per-keyword) attention on a daily basis, and its history/refetch limits. | research, then user | **Open (A3).** Answered after the research pass. Recommended default if the user wants to skip: keep CoinGecko, Google Trends, Reddit as today and add further platforms only if the research shows free, per-coin, daily-resolution data. |
| OQ-13 | (A3, new) How is a narrative's basket line computed on the spaghetti chart, and over which windows? Candidate: equal-weight average of each coin's % change from the window start (every coin counts the same, simple, no hidden weights). Alternatives: market-cap-weighted, or median. Also which daily windows to offer (for example 7d / 30d / 90d). | user (default offered), design in INNOVATE | **Open (A3).** Recommended: equal-weight % change from the window start, because it is the simplest and matches the screener spaghetti chart's per-coin anchoring; cap-weighting would let one large coin dominate a basket. Coins with insufficient data for the window are shown as excluded, per AC-24. |
| OQ-14 | (A3, new) How is per-coin mindshare combined into a per-narrative figure? Candidate: sum of per-coin attention (user's proposal); alternatives: average, or sum of each coin's change-from-start so large coins do not drown small ones. Also how to handle a coin with missing data for a day. | user, after research | **Open (A3).** Decided after the research pass (it depends on what per-coin data exists and its scale). Constraint already locked: coverage stated, gaps explicit (AC-29). |
| OQ-15 | (A3, new) May one coin belong to several narratives (for example a coin in both "AI" and "memecoins")? | user | **Open (A3).** Recommended: allow it, since real narratives overlap and each narrative is computed independently; the cost is that totals across narratives double count, which the page never sums. If the user prefers one coin per narrative, AC-27 gains a rejection rule. |
| OQ-16 | (A3, new) When a coin is removed from the screener, what happens to the narratives that contain it? | user | **Open (A3).** Recommended: the coin is removed from those narratives automatically with a visible notice, so the "narratives only hold screener coins" rule (AC-27) always holds. Alternative: block removing a coin that is in a narrative until the user detaches it. |

Handling (A3): OQ-11 and OQ-12 to OQ-16 are open. OQ-12 and OQ-14 depend on a read-only research pass (current narrative data quality and per-coin availability). None of them blocks the Locked screener, spaghetti, equities, cap or docs work; they gate only the narrative aggregation design (basket line, mindshare figure) and any change to what /narrative displays beyond AC-24 and AC-25.

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
- User input, verbatim intent: "personal-use-only tracking system"; "show data as clearly as possible so the user draws market conclusions"; "must NOT compute or display bullish/bearish verdicts." Amendment 1: "hammer on clean data" (priority for /narrative before any narrative tag).
- Amendment 3 user intent (paraphrased from the answers): the /narrative section exists to see which narratives are rising and which are the hottest at any given moment, daily; narratives are chosen by the user, who picks coins from the screener and classifies them under a narrative of their choosing; view 1 is a spaghetti chart of narrative baskets (visual comparison only); view 2 is mindshare per narrative derived from each coin and summed up or aggregated another logically sound way; keep CoinGecko, Google Trends, Reddit and "etc." and tell the user which platform behaviour makes sense to track.

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
