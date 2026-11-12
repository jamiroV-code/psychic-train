---
name: spec:narrative-v2
description: "narrative dashboard v2 — real-data fixes (no flat fake values), file-editable narratives with user coins, a momentum view, and a daily social-mindshare view, on top of the v1 /narrative dashboard"
date: 25-09-26
metadata:
  node_type: memory
  type: plan
  feature: narrative-mindshare
---

[MODE: SPEC]

## Summary

The `/narrative` dashboard shipped (v1, 24-09-26) and the user tried it against real data on
25-09-26. Most of it works, but three things are wrong or missing: (1) almost every chart shows
only one dotted line because most sources still have one data point or none, and the composite
score is silently faking a tied 0.50 for every category instead of admitting it doesn't have
enough data yet; (2) there is no way to add, rename, or remove a narrative, or to say which coins
belong to it, without a code change; (3) the dashboard doesn't make it obvious, at a glance, which
narrative is gaining momentum, which is slowing down, and which narrative is getting the most
social-media attention on a given day — the exact three questions the feature exists to answer.
This SPEC captures what needs to be true to fix that. It does not choose how to fix it — that is
the next phase's job.

## User Stories / Jobs To Be Done

**US-1 — See every line that has real data, and never see a fake flat line**
As a trader looking at a narrative's attention chart, I want to see every source's line that
actually has data plotted on the chart, and I want any source or composite that doesn't have
enough history yet to say so plainly instead of drawing a flat or default value, so that I never
mistake "not enough data" for "no attention" or a tied ranking.

**US-2 — Edit which narratives exist and which coins belong to them, without a code change**
As a trader whose watchlist and interests change over time, I want to add, rename, or remove a
narrative and set my preferred coins for it by editing a file, so that the dashboard tracks the
narratives I actually care about without needing an engineer or a redeploy.

**US-3 — See at a glance which narrative is gaining momentum and which is slowing down**
As a trader scanning the dashboard quickly, I want a clear view that ranks or highlights which
narratives are accelerating and which are decelerating, so that I can catch a rotation starting or
ending without reading every chart line by line.

**US-4 — See which narrative is getting the most social-media mindshare on a given day**
As a trader who wants to know where attention is concentrated right now, I want a daily view that
shows each narrative's share of social/search attention relative to the others, for any day I
pick, so that I can tell which story is dominating the conversation today versus a month ago.

**US-5 — See the data-quality caveat once, not on every panel**
As a trader who already understands this data is a free, unofficial proxy, I want the caveat shown
once, prominently, rather than repeated on every chart, so that the page stays readable and the
warning still registers instead of becoming visual noise.

**US-6 — Trust that nothing else on the app changed**
As a trader who relies on `/screener`'s narrative strip and confidence badge, and on
`GET /api/narrative/categories` staying frozen, I want this v2 work to leave those completely
alone, so that fixing `/narrative` never risks the parts of the app I already depend on daily.

## What The User Wants (Behavioral Outcomes)

- Every chart on `/narrative` plots every source series that has 2 or more real data points. A
  source with 0 or 1 points is shown as explicitly "not enough history yet" — never as a flat
  0.50, never silently omitted without explanation, never counted into a ranking as if it were a
  real reading.
- The composite/rank calculation never produces the same value for multiple categories as an
  artifact of insufficient data. When two or more categories are tied only because they're both
  running on too little history, the dashboard says so instead of presenting a false tie as a real
  reading. Early-days values (e.g. the first week after a source starts archiving) are visibly
  marked as provisional/thin, distinct from a mature reading.
- The user can open a plain configuration file, add a new narrative (name + search/social keywords
  + a list of the user's preferred coins for it), rename an existing narrative, or remove one —
  and the dashboard picks up the change without a code change or a redeploy. This file governs
  `/narrative` only; it never changes `/api/narrative/categories`, the `/screener` narrative strip,
  or the confidence badge, which all keep using the existing frozen category set.
- The editable narrative set supports at least 6 and up to 15 narratives at once (the user's
  stated expected range), and every cross-narrative comparison (ranking, share-of-attention,
  momentum) works correctly at that count — not just at the original 4.
- Editing the file with a mistake (e.g. a typo, an empty name, a duplicate) produces an explicit,
  readable error and does not crash the dashboard or silently drop the narrative.
- Renaming or removing a narrative has defined, stated behavior for that narrative's already-
  archived history (what happens to old data under the old name) — the user is never left
  wondering where history went or seeing it silently vanish without explanation.
- The dashboard has a dedicated momentum view: for each tracked narrative, the user can see whether
  its attention is currently rising or falling (momentum) and whether that rise/fall is speeding up
  or slowing down (a rate-of-change-of-momentum / acceleration read), over a clearly stated time
  window. This view is usable from day one wherever a source already has enough backfilled history
  (the Google-Trends-based source), and clearly marks any narrative where there isn't yet enough
  history to compute momentum.
- The dashboard has a dedicated daily social-mindshare view: for any single day the user picks
  (including today), each tracked narrative's share of social/search attention is shown relative
  to every other tracked narrative that day, using only free sources, clearly labelled as a proxy
  (not a precise or authoritative measurement), and correct whether there are 6 or 15 narratives
  being compared that day.
- The data-quality caveat appears once on the page, prominently, rather than once per chart/panel.
- The display-only exchange-volume/new-listing proxy, per-source redistribution flags, the
  "numbers are never silently wrong" rule, and a real-machine verification pass (mirroring v1's
  AC-12, since this sandbox's egress proxy still blocks every narrative data provider) all carry
  forward unchanged from v1.
- `GET /api/narrative/categories`, the `/screener` narrative strip, and the confidence badge it
  feeds are untouched — byte-compatible, behavior-compatible, exactly as v1 already locked down.

## Flow / State Diagram

```
                 ┌─────────────────────────────────────────────┐
                 │  Narrative config FILE (NEW, user-editable)   │
                 │  name, keywords, preferred coins — per        │
                 │  narrative; 6-15 narratives supported          │
                 └───────────────────┬───────────────────────────┘
                                     │ drives /narrative only
                                     ▼
     ┌──────────────────────────────────────────────────────────────┐
     │         Four attention sources (unchanged adapters)            │
     │   Google Trends   Reddit   CoinGecko trending   Exchange vol.  │
     │   (backfilled ~269d)  (0 rows, no creds)   (1 pt)   (1 pt)      │
     └───────────────────┬─────────────────────────────────────────┘
                         │ per-source series, real point counts vary
                         ▼
     ┌──────────────────────────────────────────────────────────────┐
     │   Data-sufficiency gate (NEW)                                  │
     │   < 2 points  -> "not enough history yet" (never 0.50, never   │
     │                   silently dropped, never counted in ranks)    │
     │   >= 2 points -> real series, provisional flag while thin      │
     └───────┬───────────────────┬───────────────────┬────────────────┘
             │                   │                   │
             ▼                   ▼                   ▼
   ┌──────────────────┐ ┌──────────────────┐ ┌─────────────────────────┐
   │ Per-narrative     │ │ Momentum view     │ │ Daily social-mindshare   │
   │ history chart      │ │ (NEW): rising/     │ │ view (NEW): share of    │
   │ (v1, now honest     │ │ falling +          │ │ attention per narrative │
   │  about gaps)        │ │ accelerating/       │ │ for a picked day,       │
   │                      │ │ decelerating,       │ │ 6-15 narratives         │
   │                      │ │ defined window(s)   │ │ compared fairly         │
   └──────────────────────┘ └─────────────────────┘ └─────────────────────────┘
             │                   │                   │
             └───────────────────┴───────────────────┘
                                 ▼
                 ┌───────────────────────────────────┐
                 │  ONE prominent caveat (not per-     │
                 │  panel) + display-only exchange     │
                 │  proxy + redistribution flags       │
                 │  (all unchanged from v1)             │
                 └───────────────────────────────────┘

     Untouched, frozen path (unchanged from v1):
     legacy category map -> /api/narrative/categories -> /screener strip -> confidence badge
```

## Acceptance Criteria (Testable Outcomes)

**AC-1 — No source line with fewer than 2 real points is ever silently plotted as data or folded
into a ranking as a real value.**
proven by: unit/contract test asserting a 0- or 1-point series returns an explicit
insufficient-data state, not a numeric value; a rendering test asserting the chart shows an
explicit "not enough history" marker for that source instead of a line.
strategy: Fully-Automated

**AC-2 — The composite/rank calculation never produces a same-value tie across categories caused
only by insufficient underlying data.**
proven by: a test that reproduces today's real-data shape (pytrends backfilled, others 0-1 points)
and asserts the composite for each category is either a real computed value or an explicit
insufficient-data state — never a shared default (e.g. 0.50) presented as a rank-worthy number.
strategy: Fully-Automated

**AC-3 — Provisional/thin data is visibly distinguished from a mature reading.**
proven by: a rendering test asserting a category whose real point count is below a stated
"mature" threshold carries a visible provisional marker distinct from categories with full history.
strategy: Fully-Automated

**AC-4 — Narratives are addable, renameable, and removable via a config file, with no code change
needed to see the effect on `/narrative`.**
proven by: an integration test that edits the config file (add/rename/remove a narrative), calls
the dashboard's data endpoint(s) without restarting the process (or with only the same
re-read-on-modified-time mechanism v1's coin map already uses), and asserts the change is reflected.
strategy: Fully-Automated

**AC-5 — The config file lets the user set preferred coins per narrative, and those coins show up
associated with that narrative wherever coin-level narrative context is surfaced on `/narrative`.**
proven by: a contract test asserting a coin added under a narrative in the config file appears
tagged with that narrative in the dashboard's coin-level response.
strategy: Fully-Automated

**AC-6 — Editing the config file with a mistake (empty name, duplicate name, malformed entry)
produces an explicit, readable error and never crashes the dashboard or silently drops a
narrative.**
proven by: unit tests covering each malformed-input case (empty name, duplicate name, invalid
keyword/coin entry), each asserting a structured error/validation result and no unhandled
exception; an integration test confirming `/narrative` still renders the last-known-good
configuration when the file is currently invalid.
strategy: Fully-Automated

**AC-7 — Renaming or removing a narrative has stated, non-surprising behavior for its already-
archived history — the user can find out what happened to it, it is never silently deleted or
silently orphaned without documentation.**
proven by: a test asserting the documented rename/remove behavior actually occurs (e.g. history is
retained and re-associated, or retained under the old key and explicitly labelled as archived —
whichever behavior INNOVATE/PLAN selects) plus a written note in the dashboard or docs describing it.
strategy: Fully-Automated

**AC-8 — The editable narrative set correctly supports 6 to 15 simultaneous narratives across
every cross-narrative view (comparison, ranking, daily share, momentum).**
proven by: a test seeding 15 narratives with varied data-completeness and asserting the
comparison/ranking/share/momentum views all render correctly and no view silently truncates,
mis-sorts, or breaks past the original 4-narrative count.
strategy: Fully-Automated

**AC-9 — A momentum view shows, per narrative, whether attention is rising or falling and whether
that trend is accelerating or decelerating, over a clearly stated time window, usable from day one
wherever backfilled history exists.**
proven by: a golden-value test computing momentum/acceleration by hand against a fixture series
with a known trend shape (rising-then-flattening, falling-then-reversing) and asserting the
computed direction and acceleration/deceleration state match; a rendering test asserting the view
is populated (not blank) for a narrative with pytrends-backfilled history.
strategy: Fully-Automated

**AC-10 — A narrative with insufficient history for momentum/acceleration shows an explicit
"not enough history for momentum yet" state in the momentum view, never a fabricated trend.**
proven by: a test asserting a narrative with 0-1 real points in the momentum-relevant source
returns an explicit insufficient-data state from the momentum view's data path.
strategy: Fully-Automated

**AC-11 — A daily social-mindshare view shows, for any day the user selects (including today),
each tracked narrative's share of social/search attention relative to every other tracked
narrative that day, built only from free sources, and clearly labelled as a proxy.**
proven by: a golden-value test asserting shares across narratives sum to a known total (e.g. 100%
or 1.0, with an explicit accounting for narratives excluded that day due to missing data) for a
fixture day with mixed data availability; a rendering test asserting the labelled-proxy caveat is
present on this view.
strategy: Fully-Automated

**AC-12 — The data-quality caveat appears exactly once on the page, prominently, not once per
panel/chart.**
proven by: a rendering test asserting a single instance of the caveat element exists on the
`/narrative` page regardless of how many category panels are rendered.
strategy: Fully-Automated

**AC-13 — `GET /api/narrative/categories`, the `/screener` narrative strip, and the confidence
badge it feeds remain byte-for-byte and behavior-identical to their state before this SPEC.**
proven by: the existing v1 contract-snapshot test for `/categories` re-run unmodified and still
passing; no new test needed beyond confirming the existing suite is untouched and green.
strategy: Fully-Automated

**AC-14 — A real-machine walkthrough confirms the fixed dashboard against live data: multiple
visible lines where sources have history, no fake ties, the config file actually changing what's
tracked, the momentum view populated, and the daily mindshare view populated for at least one real
day with more than one narrative having data.**
proven by: a written walkthrough checklist the user runs on their own machine (this container's
egress proxy blocks Google Trends/Reddit/CoinGecko/Hyperliquid, same constraint as v1's AC-12),
mirroring the format of v1's real-cache walkthrough.
strategy: Agent-Probe

## Out Of Scope

- Any change to how `GET /api/narrative/categories`, the frozen legacy coin-category map, the
  `/screener` narrative strip, or the confidence badge compute or display values — all stay exactly
  as v1 locked them down.
- Adding a paid social/narrative data vendor (LunarCrush, Santiment, X/Twitter API, etc.) — user
  decision, free sources only, unchanged from the project's standing rule.
- An in-app narrative editor UI (add/rename/remove narratives from a form on the page) — the user
  explicitly chose file-based editing, not an in-app editor, for this pass.
- Backfilling real historical data for Reddit, CoinGecko trending, or the exchange-volume proxy —
  none of these sources has a usable historical endpoint; only the Google-Trends-based source can
  seed its own chart from its own history, same limitation as v1.
- Turning on Reddit data by configuring credentials — remains a manual, off-repo action the user
  may do separately; not part of this SPEC's scope.
- Any change to which exchange or exact volume/listing formula backs the existing exchange-volume
  proxy — that proxy's calculation is unchanged from v1; this SPEC only asks for its output to be
  treated honestly by the sufficiency gate like every other source.
- Backtesting momentum or mindshare against the 2017 or 2020-21 cycles — no free source has usable
  history that far back; already ruled out in the v1 SPEC and not reopened here.
- Automated buy/sell signals or a single directional call derived from momentum or mindshare —
  stays a confidence/context input, consistent with the rest of the app's "confidence over
  direction" philosophy.

## Constraints

- **Numbers are never silently wrong (project-wide, unchanged).** No flat/default value may stand
  in for missing or insufficient data anywhere on `/narrative` — this is the direct requirement
  behind AC-1/AC-2/AC-10.
- **One source of numerical truth.** All sufficiency-gating, composite, momentum, and daily-share
  math happens in Python; the frontend only formats and renders values it receives.
- **Normalize within source; never compare raw levels across providers**, unchanged from v1 — the
  daily mindshare view's cross-narrative comparison must respect this (compare normalized
  shares/changes, not raw provider units).
- **Free sources only** (locked user decision) — no paid vendor for social mindshare.
- **File-editable narratives, not an in-app editor** (locked user decision) — the config file is
  the only mechanism for adding/renaming/removing a narrative and setting its coins in this pass.
- **The narrative config file governs `/narrative` only** (locked user decision, same "option B"
  framing as v1's coin map) — `/api/narrative/categories` and `/screener` keep using the frozen
  legacy category/coin map; AC-1 of v1 must continue to hold.
- **Must correctly support 6 to 15 simultaneous narratives** (locked user decision) — any design
  that only works cleanly at the original 4-narrative count does not satisfy this SPEC.
- **Redistribution flag is honored per source**, unchanged from v1.
- **A failed or thin provider degrades to an explicit state without taking the page down**,
  unchanged from v1 — this now explicitly includes "too few points to compute a value," not only
  "fetch failed."
- **This container's egress proxy blocks every narrative data provider** (Google Trends, Reddit,
  CoinGecko, Hyperliquid) — any acceptance criterion depending on live provider behavior needs a
  real-machine step, same as v1's AC-3/AC-12; automated coverage otherwise uses seeded fixtures
  through the real cache/storage boundary, per the Standing Lesson in `tests/all-tests.md` about
  what a fixture-free suite structurally cannot catch.

## Open Questions

**OQ-1 — Owner: next phase (INNOVATE/PLAN). What exact method extends Google Trends comparison
beyond 5 simultaneous keywords for a 6-15-narrative set — anchor-keyword chaining, batched
requests, or another approach — and what does it cost in extra fetches/rate-limit risk?**
pytrends currently queries one keyword per request; Google Trends supports up to 5 terms per
request on one shared 0-100 scale, and the locked 6-15-narrative range exceeds that. Not needed to
understand what the user wants (a working comparison at 6-15 narratives), only how to build it.

**OQ-2 — Owner: next phase (INNOVATE/PLAN). Is the l2s category's pytrends keyword ("layer 2
crypto") being replaced or supplemented, given its series is spiky with many zero days?**
This is a per-narrative config/tuning question, resolvable once the config file exists (the user
can simply edit the keyword) — but whether the migration replaces the current seed value or leaves
it for the user to fix themselves after the file ships is undecided.

**OQ-3 — Owner: next phase (INNOVATE/PLAN). Does this SPEC's work include prompting for or wiring
Reddit credentials, or does the dashboard remain fully functional (with Reddit shown as an
explicit zero-source state) without them?**
Out of Scope says turning on Reddit stays a manual user action, but the momentum/mindshare views
need to be correct with 0 Reddit rows in the interim — PLAN should confirm the sufficiency gate and
momentum/mindshare math are correct in that exact real-world state, not just in a fixture with
Reddit populated.

**OQ-4 — Owner: next phase (INNOVATE/PLAN). What is the exact rename/remove history behavior
(retain-and-relink vs. retain-under-old-key-and-label-archived), and does it require a migration
step or run automatically on next read?**
The SPEC requires defined, non-surprising behavior (AC-7) but does not choose between the two
plausible mechanisms — that is a design decision for INNOVATE.

## Background / Research Findings

- **Confirmed data state, 25-09-26 (from RESEARCH):** only the pytrends backfill series has real
  history (~269 days); nightly-7d, coingecko-narrative, and Hyperliquid volume share each have
  exactly 1 point (the nightly job has run once since v1 shipped); Reddit has 0 rows (no
  credentials configured). `scoring.normalize_within_source` flattens any 1-point or constant
  series to 0.5, and `build_composite` needs at least 2 populated source slots to produce a real
  value — so every date before 09-24 has no composite at all, and 09-24 itself produces a flat 0.50
  composite for all 4 categories, which then tie at rank 1. This is a fake value presented as real,
  a direct violation of "numbers are never silently wrong," and is the root cause of the user's
  "only one dotted line" and "which narrative is getting momentum" complaints — there was never
  enough real data plotted or ranked in the first place.
- **The legacy CoinGecko trending count shows as "stale, 5 days"** because nothing writes it
  nightly by design (the nightly job writes `coingecko-narrative`, a different slot, not the legacy
  trending snapshot) — separate from, but related to, the sparse-data problem above.
- **The caveat currently repeats per view/panel** rather than appearing once — directly named by
  the user as something to fix.
- **`api/data/narrative_category_map.json` (v1's "option B") already establishes the precedent
  this SPEC extends**: a user-editable JSON file, re-read on file-modification-time change, no
  restart needed, bad entries skipped with a warning rather than crashing, and scoped to drive
  `/narrative`/`/history` only while `/categories`/`/screener` stay on the separate, frozen
  `LEGACY_COIN_CATEGORY_MAP` in `mapping.py`. The user's locked decision to keep `/categories`
  frozen while making `/narrative` file-editable follows this exact shape — extending it to also
  cover full narrative add/rename/remove (not just coin-to-existing-category mapping) is the new
  work, not a new pattern.
- **pytrends currently queries one keyword per request** (`pytrends_adapter.py`); Google Trends
  itself supports up to 5 terms sharing one 0-100 scale per request. The user's locked 6-15
  narrative range exceeds 5, so some chaining/batching approach is needed — flagged as OQ-1,
  non-blocking for this SPEC.
- **CoinGecko trending membership is naturally a same-day, cross-narrative share already** (which
  categories' coins appear in CoinGecko's trending list on a given day) — a plausible building
  block for the daily social-mindshare view (US-4/AC-11), though which sources compose that view
  and how is an INNOVATE/PLAN decision, not fixed here.
- **Reddit needs both free credentials and a workflow env edit** to start archiving
  (`process/context/data-sources/all-data-sources.md` "Reddit-in-CI stance") — a deliberate
  two-step gate from v1, not an oversight; still not flipped as of this SPEC.
- **Test infrastructure is unchanged from v1**: `pytest` (api, opt-in `integration` marker),
  `vitest` + Playwright (web), current green baseline 392 pytest / 110 vitest / 26 Playwright (see
  `process/context/tests/all-tests.md`). The seeded-fixture-through-real-cache-boundary pattern
  (`seed_e2e_cache.py`) is the established way to get automated E2E coverage without live provider
  access, and should extend naturally to a 6-15-narrative fixture for AC-8's testing.
- **v1's locked-and-shipped constraints this v2 inherits unchanged:** "numbers are never silently
  wrong," "one source of numerical truth," "normalize within source, never compare raw levels
  across providers," "narrative carries lower weight than price signals," redistribution flagging
  per source, `/categories`/`/screener` byte-compatibility, and the project's free-proxies-only
  narrative-data rule (`process/context/all-context.md`, `process/context/data-sources/
  all-data-sources.md`, v1's own SPEC and PLAN `## Post-EXECUTE Amendments`).
- **v1's own Open Questions (category/coin-map scope, exchange-proxy exact source, Reddit
  credential wiring)** were resolved during v1's INNOVATE/PLAN and are not reopened here except
  where this SPEC's new user feedback directly touches them (the config file now supersedes v1's
  OQ-1 "which categories" question by making it user-editable rather than a fixed list).
