---
name: spec:pair-screener
description: "Cointegration / pair screener v1 — ranked pair table + per-pair spread detail for a hand-curated crypto universe"
date: 25-09-26
feature: cointegration-screener
---

# Pair Screener v1 — SPEC

## Summary

This adds a new screen, `/pairs`, that scans a hand-picked list of ~15-20 large, liquid crypto
coins, tests every possible pair of them for a genuine long-term statistical relationship
("cointegration" — plain-English: do these two coins' prices tend to stay a stable distance apart
over time, so that when they drift apart it's likely to be temporary?), and shows the results as a
ranked table. Clicking into a pair shows the underlying spread chart so the user can see the
relationship for themselves, not just trust a number.

This is a new, independent feature area. It does not touch the existing momentum screener
(`/screener`) in any way — different code, different route, different data list. The point is to
give the user a second, statistically rigorous lens for finding pairs worth watching for mean-
reversion trades, with the app's existing house rule applied throughout: show how strong the
evidence is and how much the tests disagree, rather than collapsing everything into one verdict.

## User Stories / Jobs To Be Done

- As a trader looking for pair-trade candidates, I want to see every pair from my coin list ranked
  by how statistically solid its cointegration evidence is, so that I can focus my research on the
  strongest candidates first instead of eyeballing charts.
- As a trader, I want to see two independent statistical opinions (Engle-Granger and Johansen) side
  by side for each pair, so that I can see when they agree (higher confidence) and when they
  disagree (lower confidence) rather than being handed a single hidden verdict.
- As a trader, I want to see how much history each pair's test was actually based on, so that I
  don't mistake a thin, unreliable result for a strong one.
- As a trader, I want pairs with too little shared history to say so plainly instead of showing a
  misleading statistic, so I never mistake "no data" for "no relationship."
- As a trader, I want to open a pair and see its spread over time, plus how "stretched" that spread
  is right now (its z-score) and roughly how fast it tends to snap back (half-life), so I can judge
  whether a pair is worth watching today.
- As the person maintaining my own coin list, I want to edit which coins are included by hand, so
  the universe reflects coins I actually consider liquid and tradable rather than an automated
  top-N list that might include something I don't want.

## What The User Wants (Behavioral Outcomes)

- A new page (`/pairs`) lists every pair formed from the hand-curated coin list (all c(n,2)
  combinations — for 15-20 coins, roughly 100-190 pairs).
- Every pair appears as one row, always — a pair is never silently dropped from the table, even
  when it has too little data or fails the test.
- Each row shows, at minimum: the two coins, the corrected significance level (see below), the
  Johansen "second opinion," an estimate of how fast the spread tends to revert (half-life), the
  current z-score of the spread, and how many days of overlapping history the pair's test used.
- The table's primary sort is by the multiple-testing-corrected significance level (most
  statistically convincing pairs first). This is described in plain terms in the UI, not just as a
  bare statistic — see Acceptance Criteria.
- Pairs whose two coins don't share enough trading history are still shown as a row, clearly marked
  as not having enough data (for example: "not enough overlapping history — 240 days available,
  need 365"), with no statistics computed or displayed for that row.
- Clicking any row opens a per-pair detail view containing: a chart of the spread over time, the
  current z-score, the half-life estimate, both test results (Engle-Granger and Johansen) with
  their own numbers, and the sample window (start date, end date, day count) the test was run on.
- Nothing on this screen is ever a blank, a zero, or a silently wrong number. Anything that
  couldn't be computed says so, in the same style as the rest of the app (e.g. the regime
  dashboard's "not applicable" / "insufficient data" treatment).
- History is refreshed via a one-time deep fetch per coin (using the full history ccxt/Hyperliquid
  will return), not the shallow window the momentum screener already caches. The two screens do
  not share a data footprint or a coin list.

## Flow / State Diagram

```
User opens /pairs
        |
        v
+--------------------------+
| Pair table loads          |
| (all pairs from the       |
|  curated coin list)       |
+--------------------------+
        |
        | for each pair, per-pair state:
        v
   +-----------------------------+        +--------------------------------+
   | Enough shared history?      |--NO--->| Row shows:                      |
   | (>= minimum overlap window) |        | "not enough overlapping history |
   +-----------------------------+        |  (N days, need M)" - no stats   |
        |YES                              +--------------------------------+
        v
   +-----------------------------+
   | Row shows: BH-corrected     |
   | p-value, Johansen result,   |
   | half-life, current z-score, |
   | sample length (days)        |
   +-----------------------------+
        |
        | user clicks row
        v
   +-----------------------------------------+
   | Per-pair detail view                     |
   | - spread chart over the sample window    |
   | - current z-score (highlighted)          |
   | - half-life estimate                     |
   | - Engle-Granger result (raw + corrected) |
   | - Johansen result (second opinion)       |
   | - sample window: start, end, day count   |
   +-----------------------------------------+

Table-level sort:
   default order = ascending BH-corrected p-value
   (most statistically convincing pair first;
    insufficient-history rows sort to the bottom,
    excluded from the correction entirely)
```

## Acceptance Criteria (Testable Outcomes)

1. **Every pair from the curated coin list appears as exactly one row in the table** — for a list
   of N coins, the table has exactly N×(N-1)/2 rows, no duplicates, no missing pairs.
   - proven by: pair-enumeration unit test comparing table row count to the curated list's
     combinatorial pair count
   - strategy: Fully-Automated

2. **A pair with fewer overlapping days than the minimum required shows an explicit
   "insufficient history" state naming the available and required day counts, and displays no
   statistics (no p-value, no Johansen result, no half-life, no z-score).**
   - proven by: integration test seeding two coins with a short overlapping window and asserting
     the row's rendered state and absence of stat fields
   - strategy: Fully-Automated

3. **Every displayed statistic (Engle-Granger p-value, BH-corrected p-value, Johansen result,
   half-life, spread z-score) matches a hand-computed reference value within a documented
   tolerance**, per this project's Standing Lesson on golden-value tests.
   - proven by: golden-value unit tests per statistic, computed against a fixed synthetic price
     series with a known, hand-derived answer
   - strategy: Fully-Automated

4. **The table's default sort order is ascending BH-corrected p-value**, and reordering the
   underlying data changes the sort order accordingly (i.e. the sort is live-computed, not
   hardcoded to input order).
   - proven by: unit test asserting sort order across a shuffled synthetic pair-result set
   - strategy: Fully-Automated

5. **The multiple-testing correction (Benjamini-Hochberg) is applied across all pairs that had
   enough data to be tested in a given run — insufficient-history pairs are excluded from the
   correction's denominator**, matching the documented BH procedure.
   - proven by: golden-value test with a known set of raw p-values and a hand-computed expected
     BH-adjusted set, confirming insufficient-history pairs are excluded from N
   - strategy: Fully-Automated

6. **The Johansen result is always shown alongside Engle-Granger for any pair with sufficient
   data — never hidden, never combined into a single score.** When the two tests disagree (one
   suggests cointegration, the other doesn't), this is visible in the row/detail view rather than
   resolved silently in favor of one test.
   - proven by: integration test asserting both fields are present and independently rendered for
     a pair where the two methods are seeded to disagree
   - strategy: Fully-Automated

7. **The per-pair detail view's spread chart renders using the pair's full available overlapping
   history (the sample window used by the statistics), and the displayed sample window (start
   date, end date, day count) matches the actual data range used to compute the statistics shown
   on the same page.**
   - proven by: e2e test (Playwright) asserting the chart's date range and the displayed sample
     window text agree, against seeded cache fixtures
   - strategy: Fully-Automated

8. **No row, chart, or statistic ever displays `NaN`, a silent zero, or a value computed from a
   partial/incomplete sample without disclosure** — any calculation failure or data gap renders an
   explicit unavailable/insufficient state instead.
   - proven by: integration test seeding a gap/failure condition (e.g. one coin's cache adapter
     returns `unavailable`) and asserting the row renders the explicit state, not a fallback number
   - strategy: Fully-Automated

9. **The pair universe is read from a separate, hand-editable list — not the momentum screener's
   watchlist and not an automatically-selected top-N — and editing that list changes which pairs
   appear on next load without touching any momentum-screener file.**
   - proven by: unit test loading the pairs universe from its own config/source and asserting it
     is structurally distinct from (does not import or read) `api/data/watchlist.py`
   - strategy: Fully-Automated

10. **The existing momentum screener (`/screener` route, `api/routers/screener.py`,
    `api/data/watchlist.py`) is provably unmodified in behavior** — its existing test suite passes
    unchanged after this feature ships, and no shared runtime state (cache keys, config, in-memory
    singletons) is introduced between the two features.
    - proven by: full existing momentum-screener pytest + vitest + Playwright suites re-run green,
      plus a diff review confirming no edits to screener.py/watchlist.py/screener e2e specs
    - strategy: Fully-Automated

11. **The one-time deep history fetch retrieves the maximum available history per coin (up to the
    adapter's deep-lookback limit) and this is a distinct, separately-triggered operation from the
    momentum screener's existing shallow cache refresh** — running one does not implicitly run or
    invalidate the other.
    - proven by: integration test triggering the deep fetch and asserting the momentum screener's
      existing cache file(s) are untouched (mtime/content unchanged)
    - strategy: Fully-Automated

12. **A coin missing from the exchange, delisted, or otherwise unfetchable is excluded from
    pair-testing with an explicit reason surfaced somewhere the user can see it (e.g. a visible
    notice or a per-row reason on any pair involving that coin) — it is never silently dropped
    with no trace.**
    - proven by: integration test seeding one coin as `bad_symbol`/`unavailable` and asserting
      every pair involving it shows an explicit reason, not a missing row
    - strategy: Fully-Automated

## Out Of Scope

- Equity pairs. This ships crypto-only; equities wait on the LSE data-verification plan's verdict
  (`process/general-plans/active/lse-data-verification_17-09-26/`).
- Any change to the momentum screener (`/screener`, `api/routers/screener.py`,
  `api/data/watchlist.py`) — it must remain byte-for-byte behaviorally unchanged.
- Automatic/algorithmic selection of the coin universe (e.g. "top 20 by market cap," "top 20 by
  volume"). The list is hand-edited by the user; v1 does not build tooling to auto-generate or
  auto-refresh it.
- A single combined "tradability score" or any other collapse of the two test results and
  half-life/z-score into one ranking number. The project's confidence-over-direction principle
  applies directly here — show the evidence, not a verdict.
- Trade execution, alerting, or position-sizing recommendations of any kind.
- Backtesting historical pair-trade performance (entry/exit simulation). v1 is a screening and
  research tool, not a backtester.
- Continuous/scheduled re-screening (e.g. a cron job that recomputes results automatically). How
  and when the screen recomputes is left to INNOVATE/PLAN as an open item, but scope for v1 is
  request-triggered or manually-triggered computation at minimum, not a live streaming pipeline.
- Stablecoins in the universe (a pair between two stablecoins, or a coin vs. a stablecoin, is
  statistically meaningless for this purpose and is excluded from the curated list by convention).
- Any UI for editing the coin list from the browser. Editing is a hand-edit of a config/source
  file; a UI editor is not built in v1.

## Constraints

- **Data source:** crypto only, via the existing ccxt/Hyperliquid adapter (`api/data/ccxt_adapter.py`).
  No new provider is introduced for v1.
- **New route, new router:** `/pairs` (web) and a new, separate API router — must not add routes to
  or import from `api/routers/screener.py`.
- **Separate coin universe:** a new, hand-editable list of ~15-20 coins, distinct from
  `api/data/watchlist.py`. Producing ~100-190 pairs (C(15,2)=105 to C(20,2)=190).
- **History depth:** one-time deep fetch using the existing but currently-unused
  `DEEP_LOOKBACK_LIMIT = 5000` constant in `api/data/ccxt_adapter.py`. Each pair's test uses the
  full overlap of its two coins' available histories, not a fixed lookback window.
- **Minimum overlap:** a pair needs approximately one year of shared daily bars to be tested at
  all; below that threshold the row shows the explicit "insufficient history" state instead of
  statistics. The exact minimum-day count (M) is confirmed with justification in INNOVATE — this
  SPEC only locks the "~1 year" order of magnitude and the requirement that the threshold be a
  named, documented constant (following the `MIN_BARS_REQUIRED` precedent in `ccxt_adapter.py`).
- **Ranking:** primary sort is the Benjamini-Hochberg-corrected p-value from the Engle-Granger test,
  computed across all pairs tested in a given run. Johansen is always shown as a second, independent
  opinion — never merged into the primary ranking. Half-life and current spread z-score are shown
  alongside every tested pair, not folded into any composite score.
- **New dependency requirement:** `statsmodels` and `arch` are not currently in
  `api/pyproject.toml` / `uv.lock` and must be added. This SPEC records the requirement; the
  specific pinned versions and packaging are a PLAN-level detail.
- **One source of numerical truth:** all statistics (EG p-value, BH correction, Johansen, half-life,
  z-score) are computed in Python and sent to the frontend as data. The frontend formats and renders
  only — it must never re-derive or re-compute any of these numbers.
- **Numbers are never silently wrong:** every computation with insufficient data, non-convergence, a
  stale/unavailable adapter result, or a delisted/missing symbol must produce an explicit,
  human-readable unavailable/insufficient state — never `NaN`, never a zero-filled series, never a
  result computed from a truncated sample without disclosure.
- **Testing convention:** every statistic requires a hand-computed golden-value test (per
  `process/context/tests/all-tests.md` Standing Lesson #4). Any test that drives `fetch_ohlcv` must
  use the `isolated_cache` fixture rather than touching the real cache.
- **Feature isolation:** the momentum screener's code, cache footprint, config, and runtime state
  must remain fully untouched by this feature (see Acceptance Criteria 10 and 11).

## Open Questions

These are intentionally left for INNOVATE to resolve with justification, not decided here:

- Half-life estimation method (OLS regression of the change in spread on the lagged spread is the
  standard approach — INNOVATE confirms whether this project uses that or an alternative, and why).
- Hedge-ratio estimation and direction: which coin is the dependent variable in the Engle-Granger
  regression, and how is that chosen per pair (symmetric test, or a fixed convention)?
- Log prices vs. raw price levels for the cointegration regression — SPEC establishes only that a
  single, declared, documented choice must be made and applied consistently; INNOVATE picks it.
- The exact minimum-overlap day count (M) for the "insufficient history" threshold — SPEC locks
  "~1 year" as the order of magnitude; INNOVATE confirms the precise number with justification.
- Pairs-specific status vocabulary: should this feature reuse ccxt's flat `ok`/`unavailable`/
  `stale`/`bad_symbol` vocabulary, or adopt the regime dashboard's richer `not_applicable`/
  `no_data` style states? INNOVATE decides based on what best serves the "insufficient history"
  and "coin unavailable" cases described in this SPEC.
- When and how the deep fetch and pair-screen recomputation run: on-demand per user request, a
  manually-triggered backend script (following the regime/momentum precedent of manual refresh
  scripts), or something else. SPEC's Out Of Scope only rules out an always-on scheduled job.
- Response size / pagination strategy for the per-pair spread series (a year+ of daily bars across
  up to ~190 pairs) — left to INNOVATE/PLAN for a technical sizing decision.

No open question in this list blocks writing this SPEC — all are locked as "INNOVATE decides,"
per the user's explicit direction this session. None are blocking SPEC completion.

## Background / Research Findings

**User-locked decisions (confirmed in chat, treated as fixed inputs to this SPEC, not re-opened):**
crypto-only universe via ccxt/Hyperliquid; new `/pairs` route and its own API router, momentum
screener untouched; v1 scope is a ranked table plus per-pair detail with a spread chart; a separate
hand-edited coin list of ~15-20 large liquid coins (~100-190 pairs), not the momentum watchlist and
not an auto top-N; one-time deep fetch using the existing unused `DEEP_LOOKBACK_LIMIT=5000`, full
pairwise overlap, sample length shown on every row; insufficient-overlap pairs still appear as a
row with an explicit message and no stats, minimum ≈1 year of shared daily bars; ranking is by
BH-corrected Engle-Granger p-value with Johansen as a second opinion and half-life/z-score shown
alongside — no combined "tradability score."

**From this session's RESEARCH:**
- `api/data/ccxt_adapter.py` is a Hyperliquid singleton adapter with a typed `OhlcvResult`
  (`status: ok | unavailable | stale | bad_symbol`), timeframes 15m/1h/4h/1d (1w derived from daily
  via real resampling, cached). `MIN_BARS_REQUIRED = 60` is explicitly momentum-specific (tied to
  the 60-day SMA) — the pair screener needs its own, separately-justified minimum. `DEEP_LOOKBACK_LIMIT
  = 5000` exists but is currently unused anywhere in the codebase — this feature is its first
  consumer. Cache layout: `api/data/cache/ohlcv/{SYMBOL}/{tf}.parquet`; currently only 501 daily
  bars cached for BTC/ETH/HYPE/SOL (shallow momentum-screener depth, not the deep history this
  feature needs).
- `statsmodels` and `arch` — the libraries the original project plan named for cointegration/regime
  work — are NOT present in `api/pyproject.toml` or `uv.lock`. They must be added; this is recorded
  as a constraint, not decided as a design choice here.
- Closest existing precedent for a new analytics + router + web feature: the regime dashboard
  (`api/routers/regime.py`, `api/analytics/regime/components*.py`, `api/models/regime.py`,
  `web/components/regime/*`, `web/e2e/regime.spec.ts`, `api/scripts/seed_e2e_cache.py`) — same
  "new route, new router, new analytics module, explicit unavailable states, gzip'd typed response"
  pattern this feature should follow at PLAN time.
- Project principles carried into this SPEC as hard requirements: one source of numerical truth (all
  stats computed in Python, TypeScript only formats/renders); numbers are never silently wrong
  (explicit unavailable/insufficient states, no NaN, no zero-fill, no undisclosed truncation);
  confidence over direction (show strength and disagreement between Engle-Granger and Johansen,
  don't collapse to one verdict).
- Statistical hazards flagged by research and folded into this SPEC as constraints/open questions:
  multiple testing across O(n²) pairs (addressed via BH correction, locked); sample length must be
  surfaced per pair (locked, AC-1/AC-3); unequal coin listing dates create unequal overlap windows
  per pair (addressed via per-pair full-overlap computation, locked); look-ahead bias in hedge-ratio
  estimation (flagged as an INNOVATE open item); log vs. level prices (flagged as an INNOVATE open
  item); delisted/unavailable markets must not silently vanish from the table (AC-12); no
  stablecoins in the universe (locked, Out Of Scope).
- Testing requirement carried from `process/context/tests/all-tests.md` Standing Lesson #4: every
  statistic (EG p-value, Johansen, BH correction, half-life, z-score) needs its own hand-computed
  golden-value test; any test exercising `fetch_ohlcv` must use the `isolated_cache` fixture.
- **Stale doc correction (out-of-band note for UPDATE PROCESS, not actioned in this SPEC):**
  `process/features/cointegration-screener/_GUIDE.md` (lines ~14-16, "Key Source Files") still says
  no application code exists yet and points at `api/routers/screener.py` / `web/app/screener/` as
  this feature's target locations — those are actually the momentum screener's files, a naming
  collision predating this SPEC. UPDATE PROCESS should correct the `_GUIDE.md` to point at this
  feature's actual new files once PLAN/EXECUTE name them.
