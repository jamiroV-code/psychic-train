---
name: spec:narrative-baskets
description: "Rebuild /narrative around user-defined coin baskets taken from screener coins: equal-weight basket spaghetti chart, share-of-total mindshare, daily rising/hottest view, clean honest data, signals v1 (Hyperliquid volume, Wikipedia pageviews, Google Trends, Reddit, CoinGecko trending) gated on live probes. Split out of personal-tracker-realignment SPEC on 02-10-26"
date: 02-10-26
feature: general-plans
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Narrative Baskets (/narrative) — SPEC

**TL;DR:** /narrative exists so the user can see, once a day, which narratives are RISING and which are the HOTTEST. A narrative is a basket the user builds from coins already on the screener. View 1 is a spaghetti chart of basket performance (equal weight, rebased to 100). View 2 is mindshare per narrative (share of total per source, averaged over the sources present). All data is shown raw and honest: missing or partial data is labelled, never zero-filled. Signals for v1 are Hyperliquid volume, Wikipedia pageviews, Google Trends, Reddit and CoinGecko trending, but **none is admitted until a live probe has run**, because every provider is unreachable from the build sandbox; probes run on the user's PC (or after a network allow-list). The app never says "rising", "hottest" or "outperforming" itself.

Status key: **Locked** = user decided, build to it. **Open** = needs an answer or probe result before planning that part. **MOVED** = lives in another file. **(A1)** to **(A4)** mark the amendment that set the text; **(A5)** marks changes made in the 02-10-26 split.

Cross-link: product direction, screener, equities and label audits are in `process/general-plans/active/personal-tracker-realignment_02-10-26/personal-tracker-realignment_SPEC_02-10-26.md`. Documentation/process work is in `process/general-plans/active/master-planner-recovery_02-10-26/` (Gate 1 housekeeping plan).

---

## Split note

This file holds ALL narrative requirements split out of `personal-tracker-realignment_SPEC_02-10-26.md`. No ID was renumbered. New in this file: outcome 24 and AC-34 (live-probe gate, A5).

| Old ID | File |
|---|---|
| US-5b, US-6, US-13, US-15, US-16, US-17, US-18, US-19 | this file |
| US-1 to 4, 5, 7 to 9, 11, 12, 14 | personal-tracker-realignment SPEC |
| US-10 | MOVED to `process/general-plans/active/master-planner-recovery_02-10-26/` (Gate 1 housekeeping plan) |
| Outcomes 6, 7, 15, 16, 19, 20, 21, 22, 23 (+ new 24) | this file |
| Outcomes 1 to 5, 8 to 14, 17, 18 | personal-tracker-realignment SPEC |
| AC-9, AC-11, AC-24, AC-25, AC-27 to AC-33 (+ new AC-34) | this file |
| AC-1 to 8, 10, 12 to 18, 21 to 23, 26 | personal-tracker-realignment SPEC |
| AC-19, AC-20 | MOVED to `process/general-plans/active/master-planner-recovery_02-10-26/` (Gate 1 housekeeping plan) |
| OQ-10, OQ-11, OQ-12, OQ-13, OQ-14, OQ-15, OQ-16, OQ-17 | this file |
| OQ-1 to OQ-9 | personal-tracker-realignment SPEC |

Shared-surface rule: removing a screener coin is a screener action (cap and watchlist rules live in the other SPEC) but its effect on narratives (outcome 22, AC-32) is owned here.

---

## Summary

The /narrative page today runs on a hand-maintained keyword/category model and shows verdict-style fields (`triggered`, `confirmed`, `trust_weight`, state labels). The user wants it replaced by something more useful and more honest: narratives the user defines themselves as baskets of coins from the screener, shown at daily resolution. View 1 is a spaghetti chart where each narrative's line is the equal-weight performance of its coins, rebased to 100 at the window start. View 2 is mindshare, each narrative's share of attention. The page shows raw data only and states plainly when any source or coin has missing, partial or insufficient data. The pytrends partial-hour fix and the nightly archive of non-refetchable history stay protected. Attention signals for v1 are Hyperliquid volume, Wikipedia pageviews, Google Trends, Reddit and CoinGecko trending; each must pass a live probe before being admitted. A coin may sit in several narratives; removing a screener coin removes it from all narratives and tells the user which.

## User Stories / Jobs To Be Done

- **US-5b (Locked) My own narratives, edited in the app.** I want to create, edit and delete narratives in the app, each a name of my choosing plus coins I pick from my screener, so my groupings are stored without editing files. Confirmed (A2): the narrative section is wanted ("very useful to track the narrative"). Narratives are user-defined coin baskets, not keyword/category definitions.
- **US-6 (Locked) Clean raw attention on /narrative.** I want /narrative to show only raw attention levels and changes per source, with missing, partial or insufficient data clearly marked, so I can trust what I see and judge the narrative myself.
- **US-13 (Locked) Trust the narrative data.** When data for a source is missing, partial or insufficient, I want to see that stated plainly instead of a zero or a quietly wrong number.
- **US-15 (Locked) Which narratives are rising and hottest, daily.** When I open /narrative, I want to see at a daily time scale which of my narratives are rising and which are the hottest right now, so I know where attention and money are moving.
- **US-16 (Locked, equal weight) Compare narrative baskets by eye.** I want a spaghetti chart where each narrative's line is the equal-weight performance of its grouped coins, rebased to 100 at the window start, so I can see visually which narrative is outperforming or underperforming without the app telling me.
- **US-17 (Locked, share-of-total) Mindshare per narrative.** I want a second view showing each narrative's share of attention, built up from the coins inside it, so I can tell when a narrative heats up before or after price moves.
- **US-18 (Locked) Only coins I already track.** I want narratives to accept only coins on my screener, so every narrative coin has the same price data as the rest of my board.
- **US-19 (Locked) Overlapping narratives.** I want one coin to be able to sit in several narratives (for example both "AI" and "memecoins"), so my baskets reflect how the market actually overlaps.

## What The User Wants (Behavioral Outcomes)

6. **Narrative editor (Locked).** Create, edit, delete narratives inside the app: a user-chosen name plus coins picked from the screener. The app persists them; the user never edits JSON. A coin can be put in a narrative only if it is currently on the screener; anything else is refused with a clear message (outcome 22).
7. **/narrative page is raw-only (Locked).** Per source, show raw attention level and change only. No flags, no trust weight, no state labels. Missing, partial or insufficient data is shown explicitly (outcomes 15 and 16).
15. **Clean /narrative data (Locked).** Only raw attention levels/changes per source. Where a source has missing, partial or insufficient data, the view says so explicitly. No zero-fill, no silently wrong numbers.
16. **Data-quality guarantees kept in scope (Locked).** The pytrends partial-hour fix (an incomplete current-hour reading is never archived as a real value) and the nightly archive of non-refetchable history stay in scope and must keep working.
19. **Purpose and time scale (Locked).** The page lets the user see which narratives are RISING and which are the HOTTEST at any moment, at a DAILY time scale (one point per day per narrative). Two views, in this order: view 1 the narrative spaghetti chart (outcome 20); view 2 the mindshare view (outcome 21). Whether any extra raw views stay beyond these is under review (OQ-11); AC-24 and AC-25 stay binding meanwhile.
20. **Narrative spaghetti chart, view 1 (Locked).** One chart, one line per narrative. A narrative's line is the equal-weight average of its member coins' performance, every coin counting the same, rebased to 100 at the start of the selected daily window. Market-cap weighting is not offered. A coin with shorter history than the window, or with no price data, is NOT silently dropped: the basket states how many of its member coins it covers and which are missing. Visual comparison only: no computed "outperforming" label, rank text or "rising/hottest" verdict.
21. **Narrative mindshare, view 2 (Locked aggregation; inputs gated per OQ-12 and outcome 24).** At daily resolution, per source: each narrative's attention value is expressed as its share of the total across all narratives that day. The narrative's figure is the average of those shares across the sources present that day. Raw per-source values are always visible alongside the share. Explicit missing-data states (outcome 15) apply; no flag, label or trust weight.
22. **Basket membership rule (Locked).** A narrative can contain only coins currently on the screener. Adding any other coin is refused, in the UI and in the API, with a clear message. The user picks the narrative name freely. One coin may belong to several narratives; each is computed independently and the app never sums figures across narratives. When a coin is removed from the screener, it is removed from every narrative that contained it, and the UI tells the user which narratives were affected.
23. **Old narrative model replaced (Locked direction, design Open).** The keyword/category-based model (hand-maintained category map and the seed categories ai, rwa, l2s, memecoins) is replaced by user-defined coin baskets. Storage shape and per-coin source mapping are PLAN decisions, gated by OQ-12.
24. **Signals v1 and the live-probe gate (Locked, A5, new).** The v1 attention signals are: Hyperliquid volume, Wikipedia pageviews, Google Trends, Reddit, and CoinGecko trending (KEPT; the user confirmed it stays as a source). X, YouTube and Telegram are not in v1. A signal is shown on /narrative only after a live probe, run on the user's PC (or after the sandbox network allow-list is opened), has recorded that it is reachable, what history depth it gives, whether it is per-coin or per-keyword, and whether values are comparable across coins. A signal that fails its probe is left out and the page says that source is unavailable; it is never filled with fake or zero data.

## Flow / State Diagram

```
/narrative   purpose: which narratives are RISING / HOTTEST, daily
   |
   +--> Narrative editor: [New narrative] name + pick coins
   |        coin ON screener  --> added to basket (same coin may be in several narratives)
   |        coin NOT on screener --> refused, clear message, basket unchanged
   |
   +--> VIEW 1 (start): narrative spaghetti chart
   |        one line per narrative = EQUAL-WEIGHT average of member coins' performance
   |        rebased to 100 at window start, daily points, window 7d / 30d / 90d (default 30d)
   |        basket says "covers N of M coins" + lists missing / short-history coins
   |        visual only, no "outperforming / rising / hottest" label
   |
   +--> VIEW 2: mindshare per narrative
   |        per source: narrative value / total of all narratives that day = share
   |        figure = average of shares over sources PRESENT that day
   |        raw per-source values always visible
   |        sources: Hyperliquid vol | Wikipedia views | Google Trends | Reddit | CoinGecko trending
   |
   +--> source / coin missing, partial, insufficient --> explicit label (never 0, never silent)

Screener removes a coin --> removed from ALL narratives --> UI lists affected narratives
Empty narrative --> explicit empty state (not auto-deleted)

Signal admission (gate):
  candidate signal --> live probe on user PC (or after network allow-list)
        |-- reachable + history + per-coin/keyword + comparable --> admitted to view 2
        |-- fails any check --> left out; page says "source unavailable"
```

## Acceptance Criteria (Testable Outcomes)

Strategy tags: FA = Fully-Automated, HY = Hybrid, AP = Agent-Probe. Scenarios come from the existing test surfaces: pytest (`api/tests/{analytics,data,routers,scripts}`, including `api/tests/data/test_pytrends_adapter.py` and `api/tests/scripts/`), vitest (`web/components/narrative/__tests__`, `web/lib/__tests__`), Playwright (`web/e2e/narrative.spec.ts`), plus the repo validators.

**Active criteria in this file: 12** (AC-9, AC-11, AC-24, AC-25, AC-27 to AC-34), under the 20 cap. Screener and equities criteria are in the other SPEC. AC-10, AC-19, AC-20 and the rest are not here (see `## Split note`).

**AC-9 (Locked) Narratives CRUD in app.** User can create, edit, delete a narrative (a user-chosen name plus a list of screener coins) in the UI; changes persist and need no file editing. Coin membership follows AC-27.
- proven by: pytest router/persistence tests; Playwright CRUD flow. strategy: FA

**AC-11 (Locked) /narrative is raw-only.** The page and its API show per-source attention level and change; `triggered`, `confirmed`, `trust_weight` and any flag or state label appear nowhere in responses, types, code or UI. The existing `/api/narrative/categories` verdict contract is retired with its snapshot test and tripwire tests. The verdict-field deletion targets (trigger, scoring, mapping logic) no longer exist in source, tests or docs.
- proven by: pytest response-shape tests; repo grep gate for `trust_weight`, `triggered`, `confirmed` and the trigger module returning zero hits outside archived history; vitest; `narrative.spec.ts`. strategy: FA

**AC-24 (Locked) /narrative data is clean and honest.** For each source, /narrative shows only raw level and change; any missing, partial or insufficient reading is shown with an explicit visible state and is never rendered as 0, filled in, or silently averaged; no flag or trust weight exists on the page or API. A narrative whose coins have missing or partial data in a day shows that state explicitly, and a basket or mindshare figure is never silently computed over fewer coins than the narrative contains without saying so.
- proven by: pytest tests with missing, partial and short-history fixtures per source (and per-coin gaps inside a narrative); vitest render of each explicit state; `narrative.spec.ts` seeded with a gap scenario. strategy: FA

**AC-25 (Locked) Data-quality fix and archive stay intact.** An incomplete current-hour pytrends reading is never archived as a real value (it yields "unavailable", not 0), and the nightly archive of non-refetchable history still writes one point per source per day.
- proven by: existing and retained `api/tests/data/test_pytrends_adapter.py` partial-hour cases; archive-writer pytest tests in `api/tests/scripts/`; workflow-schedule guard test stays green. strategy: FA

**AC-27 (Locked) Narrative coins must be on the screener.** A coin can be added to a narrative only if it is currently on the screener. Attempting to add any other coin is refused with a clear message, in the UI and in the API; the narrative is unchanged. The user can name a narrative anything; names are not limited to a fixed list.
- proven by: pytest narrative router test (screener coin accepted, non-screener coin rejected with a clear error and no change, free-text name accepted); vitest message render; Playwright add-coin-to-narrative flow on a seeded board including a non-screener coin attempt. strategy: FA

**AC-28 (Locked) Narrative spaghetti chart.** /narrative shows, as its first view, one chart with one line per narrative, each plotting the equal-weight basket performance of that narrative's coins (AC-30) at daily resolution over the selected window, rebased to 100 at the window start; adding, editing or deleting a narrative updates the chart; a narrative with no coins or insufficient data shows an explicit state, not a flat line; no label, ranking text or colour state asserts that a narrative is "outperforming", "underperforming", "rising" or "hottest".
- proven by: pytest basket-series payload test on seeded daily bars (line per narrative, rebased to 100, daily points); vitest chart render test (line count, absence of comparative wording, empty and insufficient states); Playwright `narrative.spec.ts` creating narratives from seeded screener coins and asserting the lines render. strategy: FA (readability of the visual: HY, user eyeball once)

**AC-29 (Locked) Narrative mindshare view.** /narrative shows, as its second view, a mindshare figure per narrative at daily resolution, computed as in AC-33; each figure keeps its per-source and per-coin raw values visible or reachable; any coin or source with missing, partial or insufficient data is marked explicitly and the figure states how many of the narrative's coins it covers; no flag, state label or trust weight appears.
- proven by: pytest per-coin-to-narrative combination test on seeded per-coin attention series (including a missing-coin case); vitest render of the coverage and explicit-gap states; Playwright `narrative.spec.ts` on seeded attention data with a gap scenario. Live per-coin attention availability: covered by AC-34 probes on the user's PC. strategy: HY

**AC-30 (Locked) Equal-weight basket arithmetic and honest coverage.** For a seeded narrative, each day's basket value equals the simple mean of its covered member coins' price rebased to 100 at the window start (identical weight per covered coin; no market-cap weighting anywhere); a coin whose history is shorter than the window, or that has no OHLCV, is not silently dropped: the basket shows "covers N of M coins" and names the missing coins, and the figure is computed over the covered coins only with that statement visible. A basket with zero covered coins shows an explicit "no data" state.
- proven by: pytest basket test with hand-computed expected values for a 3-coin narrative (full coverage), the same narrative with one short-history coin and with one no-OHLCV coin (expected mean over covered coins plus the coverage count and missing-coin list), and a zero-coverage case; vitest render of the "covers N of M" text and missing-coin list; Playwright on a seeded narrative with one missing coin. strategy: FA

**AC-31 (Locked) One coin in several narratives.** The same screener coin can be added to two or more narratives; each narrative's basket and mindshare figures are computed independently and include that coin; no figure in the API or UI sums values across narratives; the editor and charts render overlapping narratives without error.
- proven by: pytest narrative router and basket tests (coin accepted into two narratives, each basket includes it, no cross-narrative total in any payload); vitest overlap render; Playwright creating two narratives sharing a coin and asserting both lines render. strategy: FA

**AC-32 (Locked) Removing a screener coin cascades to all narratives.** When a coin is removed from the screener, it is removed from every narrative that contained it, in the same operation and enforced by the API (not only the UI); the UI shows a visible notice naming the narratives affected; afterwards no narrative contains a coin that is not on the screener, and a narrative left with no coins shows the explicit empty state (it is not auto-deleted). If the coin was in no narrative, no notice about narratives is shown.
- proven by: pytest watchlist/narrative router test (remove a coin held by two narratives: both updated, response lists them, invariant holds; remove a coin in no narrative: no narratives touched); vitest notice render; Playwright removing a shared coin and asserting the notice and the updated baskets. strategy: FA

**AC-33 (Locked) Share-of-total mindshare arithmetic.** For each day and each source present that day, a narrative's value is its attention for that source divided by the sum of all narratives' values for that source that day (a share of 0 to 100%); the narrative's mindshare figure is the mean of its shares over the sources present that day (a source absent for the day is excluded and named as absent, not counted as zero); raw per-source values stay visible beside the shares. A day with no source present shows an explicit "no data" state.
- proven by: pytest combination test with hand-computed expectations (3 narratives, 3 sources; then one source absent; then no source present); vitest render of shares plus raw values and the absent-source note; Playwright on seeded attention data with a gap scenario. strategy: FA

**AC-34 (Locked, A5, new) Signals are admitted only after a live probe.** Each v1 signal (Hyperliquid volume, Wikipedia pageviews, Google Trends, Reddit, CoinGecko trending) has a recorded probe result, produced on the user's PC or after the network allow-list, stating: reachable yes/no, history depth, per-coin or per-keyword, refetchable yes/no, comparable across coins yes/no, personal-use terms noted. A signal without a passing probe result does not feed view 2; the page shows that source as unavailable (never zero). The probe result is stored with the task artifacts. In the sandbox, the signal adapters are tested only against saved fixtures, and the specification does not claim live behaviour from them.
- proven by: pytest tests that a signal with no probe record (or a failed one) is excluded and reported "unavailable" in the mindshare payload, using fixtures; Playwright seeded scenario with one unavailable source showing the explicit label; the live probe itself is an agent-probe on the user's PC, with the result recorded in the task folder. strategy: AP for the live probe, FA for the exclusion behaviour (overall HY)

## Impact Surface (what gets deleted / changed)

Names only, derived from reads. "Audit" = file likely carries verdict wording and must be checked in PLAN.

| Area | Item | Action |
|---|---|---|
| API narrative | `api/analytics/narrative/trigger.py`, `scoring.py`, `mapping.py` | Delete/reduce trigger, confirmation, trust weight; mapping replaced by in-app narratives |
| API narrative | `api/routers/narrative.py`, `api/models/narrative.py` | Change: remove triggered/confirmed/trust_weight; explicit missing/partial/insufficient states; narrative CRUD enforcing "coin must be on the screener"; daily basket-performance payload (equal weight, rebased to 100, coverage count + missing-coin list); per-narrative mindshare payload (share-of-total averaged over present sources, raw values kept); a coin may be in several narratives; no cross-narrative totals; source-unavailable state for unprobed signals |
| API narrative | `api/analytics/narrative/narrative_config.py`, `api/data/narratives.json`, `narrative_categories.json`, `narrative_category_map.json`, seed categories ai/rwa/l2s/memecoins | Replace the keyword/category model with user-defined coin baskets stored by the app. Direction locked, design open. Archived keyword/category history is not deleted (see Out Of Scope) |
| API narrative | `momentum.py`, `mindshare.py` (+ `MomentumView.tsx`, `MindshareView.tsx`) | Audit for state labels and silent zero/average handling. These are the natural homes for view 1 and view 2; rework vs replace is a PLAN decision |
| API data | `api/data/pytrends_adapter.py` and nightly archive scripts | Keep: partial-hour fix and nightly archive protected by AC-25. Per-coin attention may need new fetch/archive paths (gated by OQ-12 and AC-34) |
| API data | Adapters for Hyperliquid volume, Google Trends, Reddit, CoinGecko trending (existing) and Wikipedia pageviews (new) | Probe first (AC-34); adapters stay behind the `api/data/` adapter pattern |
| API data | `api/routers/watchlist.py`, `api/data/watchlist.py` (narrative side only) | Expose the screener coin list for membership checks; removing a coin also removes it from all narratives and reports which. (The 30-coin cap and groups are in the other SPEC.) |
| Web narrative | `NarrativeDashboard.tsx`, `CategoryHistoryPanel.tsx`, `ComparisonView.tsx`, `ChangeInAttentionView.tsx`, `DataQualityCaveat.tsx` | Change/Audit: raw-only, explicit missing-data states; add narrative editor (name + screener-coin picker) and the two views |
| Web narrative | `RedistributionBadge.tsx` | Delete (licensing no longer a constraint; confirm in PLAN) |
| Tests | `web/e2e/narrative.spec.ts`, narrative contract-snapshot and tripwire tests | Rewrite for user-defined baskets / delete with the code they guard |

## Out Of Scope

- Any computed "outperforming", "underperforming", "rising" or "hottest" label, score or ranking text; the user reads these from the charts.
- Narratives containing coins that are not on the screener, and a preset or fixed narrative list (the old seed categories ai/rwa/l2s/memecoins are not kept as defaults).
- Market-cap weighting (or median) of narrative baskets. Equal weight is the only method.
- Summing or ranking figures across narratives (overlap would double count).
- The narrative tag on screener coin boxes (deferred; see the other SPEC).
- X, YouTube and Telegram as v1 signals.
- Retroactive correction or deletion of already-archived narrative/keyword/LiqTide history files.
- Any signal admitted without a live probe (AC-34).
- Documentation/process rewrites (moved to `process/general-plans/active/master-planner-recovery_02-10-26/`).
- Auth, billing, multi-tenancy, public deployment.

## Constraints

- Personal use only; Tailscale-only. "Numbers are never silently wrong": unavailable, partial or insufficient data shows an explicit state, never 0/NaN, never zero-filled.
- One source of numerical truth: basket and mindshare figures are computed in Python and rendered by the web app. Providers stay behind adapters under `api/data/`.
- **Priority order: data cleanliness first; any further narrative feature waits on what the clean data shows.**
- Narrative time scale is daily: one point per day per narrative. Narrative coins must be on the screener, so the screener's 30-coin cap also bounds the coins a narrative can use.
- Visual comparison only on /narrative.
- Basket method: equal weight rebased to 100 at the window start. Mindshare: share-of-total per source, averaged over present sources, raw per-source values always visible. A coin may be in several narratives; removing a screener coin removes it from all narratives and the UI says so.
- **Live-probe gate (A5):** the sandbox egress proxy blocks Google Trends, Reddit, CoinGecko, Hyperliquid and Wikipedia. No claim about live provider behaviour is made from the sandbox. Probes run on the user's PC or after the network allow-list is opened; until then the signals are tested on saved fixtures only.
- Nightly snapshots for sources with no history (narrative, liqtide, chain-growth) stay on their current schedule.
- Known risk, Google Trends: values are on a relative 0-100 scale per request, at most 5 terms per request, and cross-request comparison needs anchor-chaining, which can rescale a term to near 0 against a larger anchor (the repo already saw a `0.0` meaning "below the anchor's resolution"). The probe must test per-coin comparability before Trends feeds view 2.
- CoinGecko trending is a trending list, not a per-coin time series; the probe must establish how it maps to per-coin or per-narrative daily values before it is admitted.
- Every requirement must remain testable; no verdict logic under another name.

## Open Questions

| # | Question | Owner | Status |
|---|---|---|---|
| OQ-10 | Do you still want in-app narrative create/edit/delete with the screener tag deferred? | user | **Resolved (A2): yes ("very useful to track the narrative").** |
| OQ-11 | Which raw views, if any, stay beyond the two views and AC-24/AC-25? | user, after research | **Open (narrowed).** Not blocking: PLAN builds the two views and keeps nothing else new. |
| OQ-12 | Which signals supply coin-level attention, and in what form (per coin, or per keyword mapped to a coin)? | user probe on own PC | **Open, signal list decided (A5), probe-gated.** v1 list: Hyperliquid volume, Wikipedia pageviews, Google Trends, Reddit, CoinGecko trending (kept). Remaining: the live probe of each (AC-34), including how Wikipedia pageviews map to a coin (one article per coin) and how CoinGecko trending becomes a daily per-coin value. Recommended default if the probe is not run yet: build the mindshare view on seeded data and show every unprobed source as "unavailable". |
| OQ-13 | How is a narrative's basket line computed? | user | **Resolved (A4): equal weight, rebased to 100; shorter-history or no-OHLCV coins not silently dropped (coverage stated); market-cap weighting out of scope.** |
| OQ-14 | How is per-coin mindshare combined into a per-narrative figure? | user | **Resolved (A4): share of total per source, averaged over sources present, raw values always visible.** |
| OQ-15 | May one coin belong to several narratives? | user | **Resolved (A4): yes.** |
| OQ-16 | What happens to narratives when a coin is removed from the screener? | user | **Resolved (A4, SPEC-author pick between the user's two options, overridable): removal cascades to ALL narratives, API-enforced, UI names the affected narratives (AC-32).** |
| OQ-17 | Which daily windows does the basket chart offer? | user | **Open (minor, defaulted).** PLAN uses 7d, 30d and 90d, switchable, starting at 30d, unless the user says otherwise. |

Remaining open: OQ-11 (not blocking), OQ-12 (probe-gated, needs the user's PC), OQ-17 (defaulted). None blocks the editor, basket chart, overlap, cascade or arithmetic work; they gate only which live signals feed view 2.

## Background / Research Findings

- Narratives are currently defined in hand-edited `api/data/narratives.json` (from narrative-v2) and a keyword/category map with seed categories ai, rwa, l2s, memecoins; `/narrative` and `/categories` expose `triggered`, `confirmed`, `trust_weight` (`api/analytics/narrative/trigger.py`).
- Existing adapters archive pytrends and Reddit history keyed by keyword, not by coin (`all-context.md`), which is why per-coin attention availability is a probe question (OQ-12, AC-34).
- Pytrends anchor-chaining is already used in the repo (batched fetch with an anchor term, 5 terms per request); `all-context.md` records `pytrends/RWA crypto` at 74.0 while the blended RWA figure was 0.0 written as fresh. Concrete basis for the Google Trends comparability risk.
- The pytrends partial-hour fix and the nightly archive exist from earlier work (2026-09-28 / 2026-10-01 entries in `all-context.md`); carried forward as protected guarantees (AC-25).
- The existing mindshare view already averages per-source figures; the new share-of-total method keeps that averaging idea.
- User intent (A3, paraphrased): the /narrative section exists to see which narratives are rising and which are the hottest at any given moment, daily; narratives are chosen by the user from screener coins; view 1 is a spaghetti chart of baskets (visual only); view 2 is mindshare per narrative derived from each coin and aggregated.
- User answers (A4, authoritative): equal weight rebased to 100; market-cap weighting out of scope; a coin may be in several narratives; share-of-total mindshare averaged over present sources with raw values visible; signals to research were Hyperliquid volume, Google Trends per coin, Reddit mentions, X/YouTube/Telegram.
- User answer (split, 02-10-26): v1 signals are Hyperliquid volume, Wikipedia pageviews, Google Trends, Reddit and CoinGecko trending (kept); providers are unreachable from the sandbox, so probes run on the user's PC or after a network allow-list.
- "Hammer on clean data" (A1): data cleanliness comes before any further narrative feature.

## Decision history (condensed)

| Amendment | What it decided |
|---|---|
| 1 | Narrative tag deferred; /narrative raw-only with explicit missing/partial/insufficient states (US-6, US-13, outcomes 15 and 16, AC-11, AC-24, AC-25). |
| 2 | Narrative section still wanted; in-app CRUD Locked (OQ-10 resolved); content under review (OQ-11). |
| 3 | Purpose: daily rising/hottest; narratives are user-defined baskets of screener coins; two views; old keyword/category model replaced; AC-27 to AC-29. |
| 4 | Equal-weight basket, share-of-total mindshare, overlap allowed, removal cascades to all narratives; AC-30 to AC-33; signals research scope set. |
| Split (02-10-26) | Narrative requirements moved here; signals v1 fixed; live-probe gate added (outcome 24, AC-34); CoinGecko trending kept; IDs stable. |
