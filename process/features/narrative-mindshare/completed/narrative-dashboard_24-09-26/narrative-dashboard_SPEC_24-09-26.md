---
name: spec:narrative-dashboard
description: "Standalone /narrative attention dashboard, graduating the momentum-screener RFC-003 narrative backend into its own feature with forward-archived history and two new attention proxies"
date: 24-09-26
metadata:
  node_type: memory
  type: plan
  feature: narrative-mindshare
---

[MODE: SPEC]

## Summary

The momentum screener already tracks narrative/sector "mindshare" (Google Trends, Reddit,
CoinGecko trending) as one input into its confidence badge, but that work only ever shows up as a
small strip on the `/screener` page and has never accumulated any history — every read is a
today-only snapshot. This SPEC turns narrative/mindshare into its own first-class feature: a
standalone `/narrative` dashboard where the user can see attention trends over time (not just
today's snapshot), compare sectors against each other, and see when attention is shifting —
without touching or slowing down the existing `/screener` page, which keeps working exactly as it
does today. Two new attention signals are added (exchange trading volume / new-listing activity,
and a wider coin-to-category map), and every value on the page is honest about how thin and
unofficial this data really is — a visible caveat, not a footnote.

## User Stories / Jobs To Be Done

**US-1 — See attention change over time, not just today's snapshot**
As a trader who wants to catch a narrative rotation early, I want to see each sector's attention
level plotted as a history, not just a single current reading, so that I can tell whether a
sector's mindshare is rising, falling, or flat rather than only seeing where it stands right now.

**US-2 — Compare sectors against each other on one screen**
As a trader tracking multiple narratives at once (AI, RWA, L2s, memecoins, and whatever else has
been added), I want all tracked sectors visible together on one dashboard, so that I can see which
narrative currently has the most relative attention without opening each one separately.

**US-3 — See a change-in-attention view, not just a level**
As a trader who cares about momentum in attention itself, I want to see which sectors are gaining
or losing attention fastest, not just which one currently reads highest, so that I can catch an
emerging rotation before it's obvious from the raw level alone.

**US-4 — Get an extra, price-independent attention signal from exchange activity**
As a trader who knows social-proxy data is noisy and unofficial, I want an additional attention
signal drawn from exchange trading volume and new-listing activity, so that I have at least one
proxy that isn't dependent on a scraped/unofficial API that could disappear at any time.

**US-5 — Track more of my own coins against a narrative, not just the three the screener knows about**
As a trader whose watchlist has grown past BTC/ETH/HYPE, I want the coin-to-category mapping this
feature uses to cover the coins I actually watch, so that narrative context is available for more
of my board, not just the three coins it happens to already know.

**US-6 — Know exactly how much to trust this data**
As a trader who understands this whole layer is built on free, unofficial proxies, I want an
explicit, visible caveat on the dashboard reminding me that these numbers are directionally
useful but not authoritative, so that I never mistake a shaky proxy reading for a confirmed signal.

**US-7 — Keep using the screener exactly as it works today**
As a trader who already relies on the `/screener` page's narrative strip for the confidence badge,
I want that existing behavior to keep working unchanged while the new dashboard is built, so that
nothing I already depend on breaks or shifts underneath me.

## What The User Wants (Behavioral Outcomes)

- A new page, `/narrative`, shows every tracked category (the existing curated seed list plus any
  auto-flagged emerging categories) as its own attention-history chart — not a single current
  number, a time series that grows a real day-by-day history from the day this feature ships
  forward.
- The dashboard lets the user compare sectors side by side (which currently has the most relative
  attention) and see a change-in-attention view (which sectors are rising/falling fastest right
  now), not only a snapshot ranking.
- History accumulates forward, day by day, from a scheduled daily job — it is not backfilled
  from any source that doesn't already have its own historical window. Where a source can supply
  some of its own past history (the Google-Trends-based source has this), that history seeds the
  chart's starting point; every other source's chart simply starts thin and grows from here.
- Google Trends, Reddit, and CoinGecko trending keep working exactly as they already do today
  (same normalization-within-source, same explicit `unavailable`/`stale`/`presumed-dead` states) —
  this SPEC does not change how any of the three existing sources compute a value, only how their
  values are archived and displayed.
- A new attention proxy derived from exchange trading volume and new-listing activity is added as
  a fourth signal, computed the same honest way as the other three (explicit unavailable state on
  failure, normalized within its own source, never compared as a raw level against the others).
- The coin-to-category mapping used to relate a specific coin to a narrative is widened to cover
  more of the user's actual watchlist, not just the three coins it covers today.
- Every view on the dashboard carries a visible, plain-language data-quality caveat — this is a
  page element the user sees, not a comment buried in code or docs.
- The `/screener` page's existing narrative strip, its confidence-badge input, and the
  `GET /api/narrative/categories` response shape are all unchanged by this work. A user who never
  visits `/narrative` should not notice anything different about `/screener`.
- If any one of the four attention sources fails to fetch, the dashboard shows that source (and
  anything downstream of it) as explicitly unavailable — it never goes blank, never silently drops
  to a zero-look reading, and never takes the rest of the page down.
- The dashboard never plots or compares raw attention levels across two different sources on the
  same axis — each source is normalized within itself; cross-source comparison, where shown at
  all, compares direction/change, not absolute magnitude.
- Narrative/mindshare readings continue to carry less weight than price-derived signals wherever
  they feed into any combined confidence read elsewhere in the app (the confidence-badge behavior
  itself does not change under this SPEC — that logic lives in the screener feature and is
  explicitly out of scope here).

## Flow / State Diagram

```
                    ┌───────────────────────────────────────┐
                    │   Nightly scheduled job (forward       │
                    │   archive, same pattern as              │
                    │   liqtide-snapshot.yml)                 │
                    └───────────────┬─────────────────────────┘
                                    │  fetches once/day, writes
                                    │  one row per (source, category)
                                    ▼
          ┌───────────────────────────────────────────────────────┐
          │              Four attention sources                    │
          │  ---------------------------------------------------   │
          │  Google Trends   Reddit     CoinGecko    Exchange       │
          │  (existing)      (existing) trending     volume/listing │
          │                             (existing)    (NEW)         │
          │  each: normalize-within-source, explicit                │
          │  unavailable / stale / presumed-dead on failure          │
          └───────────────┬─────────────┬──────────────┬────────────┘
                           │             │              │
                           ▼             ▼              ▼
          ┌───────────────────────────────────────────────────────┐
          │        Per-category attention history archive           │
          │   (forward-accumulating daily series, one per           │
          │    source x category; existing sources keep their       │
          │    current daily cache, now retained as growing history)│
          └───────────────┬───────────────────────────────────────┘
                           │
              ┌────────────┴─────────────┐
              │  Wider coin -> category   │
              │  map (beyond BTC/ETH/HYPE)│
              └────────────┬─────────────┘
                           │
                           ▼
          ┌───────────────────────────────────────────────────────┐
          │                 /narrative DASHBOARD (NEW)               │
          │  --------------------------------------------------------│
          │  [Category A history] [Category B history] [Category C]..│
          │   attention over time   attention over time   ...        │
          │                                                            │
          │  Side-by-side comparison view (relative mindshare)        │
          │  Change-in-attention view (who's rising/falling fastest)  │
          │  Visible data-quality caveat on every view                │
          └───────────────────────────────────────────────────────┘

  Branches / degraded states shown ON the dashboard itself, never hidden:
   - Any one of the 4 sources fails to fetch -> that source (and anything
     computed from it) reads "unavailable" for that day; the other 3
     sources' data and the rest of the page are unaffected.
   - Google Trends source goes presumed-dead (existing 7-day rule,
     unchanged) -> flagged distinctly from a single-day miss, same as today.
   - A coin has no category mapping -> explicit "no mapping" state, never
     silently grouped under a guessed category.

  Unchanged, parallel path (not touched by this SPEC):

    Existing RFC-003 narrative pipeline ─────────────► /screener page
    (pytrends/reddit/coingecko, trigger/confirm,        NarrativeStrip.tsx
     GET /api/narrative/categories)                     + confidence badge
    same code, same contract, same behavior              (byte-compatible,
                                                            no changes)
```

## Acceptance Criteria (Testable Outcomes)

**AC-1 — The screener's existing narrative contract is untouched.**
`GET /api/narrative/categories` returns the exact same response shape it does today, and the
`/screener` page's narrative strip and confidence-badge behavior are unaffected by any change made
under this SPEC.
proven by: narrative-categories-contract-unchanged
strategy: Fully-Automated

**AC-2 — Every tracked category shows a real, growing attention history, not just today.**
The `/narrative` dashboard renders a time-series chart per tracked category (seed + auto-flagged),
built from archived daily points rather than a single current reading.
proven by: narrative-history-archive-accumulation
strategy: Fully-Automated

**AC-3 — History accumulates forward daily via a scheduled job.**
A scheduled daily job (same nightly-archive pattern as the existing LiqTide snapshot workflow)
fetches and archives one point per (source, category) per day, so the chart's history grows over
time without requiring a manual trigger.
proven by: narrative-snapshot-workflow-dry-run
strategy: Hybrid (workflow logic Fully-Automated; the scheduled-trigger mechanism itself is
Agent-Probe — GitHub Actions cron execution cannot be verified from source code alone)

**AC-4 — Google Trends' own historical window seeds the chart where available.**
For categories where the Google-Trends-based source has its own retrievable history, that history
is used to pre-populate the chart's starting point rather than leaving it empty until the forward
archive catches up.
proven by: pytrends-historical-backfill
strategy: Fully-Automated

**AC-5 — Sectors can be compared side by side.**
The dashboard shows a view where every tracked category's current relative standing is visible
against every other tracked category at once, not only reachable one category at a time.
proven by: narrative-sector-comparison-view
strategy: Agent-Probe

**AC-6 — A change-in-attention view is available, not only a level.**
The dashboard shows which categories are gaining or losing attention fastest over a recent window,
distinct from simply ranking current levels.
proven by: narrative-change-in-attention-view
strategy: Agent-Probe

**AC-7 — A new exchange-volume/listing attention proxy exists and fails safely.**
A fourth attention source, derived from exchange trading volume and/or new-listing activity, is
computed with the same failure discipline as the other three: a fetch failure yields an explicit
`unavailable` state for that source, never a silent zero or a dropped chart.
proven by: exchange-attention-proxy-failure-degrades-explicitly
strategy: Fully-Automated

**AC-8 — The coin-to-category map covers more of the user's watchlist.**
The coin-to-category mapping used to relate a specific coin to a tracked narrative includes
entries beyond the current three (BTC, ETH, HYPE), and a coin with no mapping still shows an
explicit "no mapping" state rather than being silently grouped under a guessed category.
proven by: narrative-mapping-coverage-and-unmapped-state
strategy: Fully-Automated

**AC-9 — A single source failure never takes down the whole dashboard.**
If any one of the four attention sources fails to fetch for a given day, only that source's data
(and anything computed from it) reads as unavailable — the other three sources and the rest of the
dashboard continue to render normally.
proven by: narrative-dashboard-single-source-failure-isolation
strategy: Fully-Automated

**AC-10 — Values are never compared as raw levels across sources.**
Every attention value is normalized within its own source before display; any cross-source
comparison the dashboard shows (e.g. relative sector standing) compares normalized/derived values,
never a raw reading from one source plotted directly against a raw reading from another.
proven by: narrative-cross-source-normalization-boundary
strategy: Fully-Automated

**AC-11 — A visible data-quality caveat appears on every dashboard view.**
Every view on the `/narrative` dashboard (history charts, comparison view, change-in-attention
view) carries a plain-language, on-screen note that this data comes from free, unofficial proxies
and should be treated as directional context, not a confirmed signal.
proven by: narrative-data-quality-caveat-visible
strategy: Agent-Probe

**AC-12 — The real-machine walkthrough confirms the dashboard against live cached data.**
On a machine with real network access to Google Trends, Reddit, CoinGecko, and the chosen exchange
(this sandbox's egress proxy blocks these), the user opens `/narrative` against real accumulated
cache data and confirms: history charts render with real points, the comparison and
change-in-attention views reflect real relative standing, a source that is actually failing (e.g.
Reddit with no credentials configured) shows as visibly unavailable rather than silently missing,
and the data-quality caveat is visible throughout.
proven by: narrative-dashboard-real-cache-user-walkthrough
strategy: Agent-Probe (user, real machine — mirrors the regime dashboard's AC-11 walkthrough
precedent; this container's proxy blocks the same providers, so this cannot run here)

## Out Of Scope

- Any change to how the existing pytrends/Reddit/CoinGecko trigger-and-confirm logic computes a
  value, or to the confidence-badge weighting that consumes narrative state on `/screener` — this
  SPEC only adds history, a new page, a new proxy source, and a wider coin map around the existing
  RFC-003 backend; it does not redesign the backend's scoring math.
  logic.
- Backfilling real historical attention data for Reddit, CoinGecko trending, or the new
  exchange-volume/listing proxy — none of these sources has a usable historical endpoint; their
  history starts from whenever the forward archive first runs, same limitation the LiqTide archive
  already lives with.
- Any paid narrative/social-data vendor (LunarCrush, Santiment, etc.) — the project's standing
  rule (free proxies only until a proxy demonstrably changes a sizing decision) is unchanged.
- Automated buy/sell signals or a single directional call derived from narrative strength — this
  stays a confidence/context input, never a call, consistent with the rest of the app's philosophy.
- Backtesting narrative/mindshare against the 2017 or 2020-21 cycles — already ruled out
  (no free source retains usable history that far back; this was resolved in the momentum-screener
  SPEC and is not reopened here).
- Choosing or building the exchange volume/new-listing proxy's exact data source beyond "keyless,
  public, via the existing ccxt adapter pattern" — which exchange(s), and the exact
  volume/new-listing calculation, is an Open Question below.
- Moving or renaming any existing RFC-003 file under `api/` or `web/` — "graduating" this feature
  means the `narrative-mindshare` feature folder becomes the system of record for planning and
  docs going forward; it does not mean relocating already-shipped source files.

## Constraints

- **Numbers are never silently wrong (project-wide constraint, unchanged).** Any narrative value
  with a failed fetch, insufficient history, or a stale/presumed-dead source must show an explicit
  state — never a NaN rendered as valid, a zero-fill, or a value computed as if a missing source
  were neutral.
- **One source of numerical truth.** All narrative computation (normalization, trigger/confirm,
  the new exchange-attention proxy, any change-in-attention calculation) happens in Python; the
  frontend only formats and renders values it receives.
- **Normalize within source; never compare raw levels across providers.** This existing rule
  extends to the new exchange-volume/listing source and to any dashboard view that shows more than
  one source at once.
- **Narrative carries lower weight than price signals** wherever it feeds a combined confidence
  read elsewhere in the app — this SPEC does not change that weighting, only where and how
  narrative history is displayed on its own dashboard.
- **Redistribution flag is honored per source.** Every narrative data source (existing three plus
  the new exchange proxy) must be labelled for whether its output may be shown to other users
  later, matching the project's existing redistribution-safety posture.
- **A failed provider degrades to unavailable without taking the page down.** This applies
  per-source, per-category, per-day — one bad fetch never blanks the whole dashboard.
- **The existing `GET /api/narrative/categories` endpoint and `/screener` narrative strip stay
  byte-compatible.** No response-shape change, no behavior change, for any consumer of the
  existing endpoint.
- **History is forward-archived, not retroactively reconstructed** (locked user decision) — a
  nightly scheduled job in the same pattern as `.github/workflows/liqtide-snapshot.yml`. The
  Google-Trends-based source's own historical window is used to backfill its own chart where that
  history is available; no other source is backfilled beyond what it can supply itself.
- **The exchange volume/new-listing proxy must be keyless and public** (ccxt-based, consistent
  with the project's existing crypto-data pattern) — no new paid or authenticated exchange API.
- **This is a feature-folder graduation, not a rewrite** (locked user decision) — the existing
  RFC-003 backend code, its adapters, and its analytics modules are kept as-is; this feature folder
  becomes the planning/documentation owner for that surface going forward.

## Open Questions

**OQ-1 — Owner: next phase (INNOVATE/PLAN). Which categories does the dashboard track beyond the
current 4-item seed list (AI, RWA, L2s, memecoins), and does the coin-to-category map widen to
match?**
The current seed list and `COIN_CATEGORY_MAP` (BTC, ETH, HYPE only) were sized for the screener's
narrow integration need. US-5 asks for wider watchlist coverage, but the exact target category and
coin list is not specified by the user. Needs a concrete list before PLAN can size this work.

**OQ-2 — Owner: next phase (INNOVATE/PLAN). Which exchange(s) back the new volume/new-listing
attention proxy, and what exact calculation counts as "attention" (raw volume change? number of
new listings in a window? both)?**
The user specified the proxy type (exchange volume / new-listing activity, via ccxt, keyless) but
not the exact exchange or formula. The existing `ccxt_adapter.py` already resolves market symbols
against one exchange for OHLCV — whether the new proxy reuses that same exchange or needs another
is unresolved.

**OQ-3 — Owner: next phase (INNOVATE/PLAN). How does the nightly workflow handle Reddit
credentials — a GitHub Actions secret, or does the workflow simply skip Reddit (same as it does
today when `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` are unset) and rely on the other three
sources?**
The existing Reddit adapter already degrades to `unavailable` cleanly when credentials are absent,
so the nightly job "just working" without them is a real, low-risk option. But if the user wants
Reddit history archived from day one, the workflow needs the two secrets configured in the repo's
Actions settings — that's a manual, off-repo action this SPEC cannot resolve unilaterally.

## Background / Research Findings

- **The narrative backend already exists, built as momentum-screener RFC-003, not as its own
  feature.** Adapters: `api/data/pytrends_adapter.py` (unofficial Google Trends wrapper,
  `presumed-dead` flag after 7 days of failed fetches), `api/data/reddit_adapter.py` (needs
  `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`, degrades to `unavailable` when unset),
  `api/data/coingecko_adapter.py::fetch_trending()`. Analytics: `api/analytics/narrative/scoring.py`
  (within-source min-max normalization), `mapping.py` (`COIN_CATEGORY_MAP`, currently
  `{"BTC": "store-of-value", "ETH": "l2s", "HYPE": "l2s"}` — only 3 coins), `trigger.py`
  (rate-of-change-vs-baseline trigger, z-score ≥1.0, 10-day sustained-duration confirmation path,
  `trust_weight` capped when fewer than 2 sources are healthy). `GET /api/narrative/categories`
  (`api/routers/narrative.py`) returns `list[NarrativeCategory]` (`id`, `label`, `keywords`,
  `seed`, `triggered`, `confirmed`, `trust_weight`, `source_availability`) — a triggered-but-
  unconfirmed category is always included, never hidden. Seed categories live in
  `api/data/narrative_categories.json` (4 entries: ai, rwa, l2s, memecoins).
- **The only current consumer is the screener.** `web/components/screener/NarrativeStrip.tsx` on
  `/screener`, plus `screener_board.py`'s per-coin `narrative_state` (feeding the confidence
  badge). No standalone dashboard exists.
- **Narrative history is not currently retained as a time series for display.**
  `api/data/cache.py::narrative_series_path` already writes one Parquet file per
  (source, category) with columns `date, raw_value, normalized_value, source_status` — this is
  forward-accumulating storage that already exists and grows day by day every time the backend is
  queried; it has just never been surfaced as a chart. `write_trending_snapshot` for CoinGecko is a
  today-only overwrite snapshot, not itself a history.
- **Pytrends has its own historical window.** `pytrends_adapter.py::fetch_trend` already calls
  `pytrends.interest_over_time()`, which returns a real historical series (not just today's
  point) when it succeeds — this is the basis for AC-4's backfill.
- **The LiqTide nightly snapshot is the direct precedent for the forward-archive approach.**
  `.github/workflows/liqtide-snapshot.yml` runs on a `cron` schedule (`30 23 * * *`) plus
  `workflow_dispatch`, checks out the repo, runs a Python script via `uv`, and commits the archived
  output back to `main` — this is the pattern the user explicitly chose to replicate for narrative
  history.
- **No provider offers deep pre-existing history for the new exchange-based proxy or for
  Reddit/CoinGecko** — confirmed during RESEARCH. This is why the locked decision is forward
  archival, not backfill, for those sources.
- **Redistribution/licensing:** the data-sources context group flags narrative/mindshare as "the
  weakest link in the stack" — no strong free tier exists; the project's standing decision (free
  proxies only, explicitly labelled, no paid vendor until a proxy demonstrably changes a sizing
  decision) is unchanged and explicitly carried into this SPEC's Constraints.
- **Test infrastructure:** `pytest` (with an opt-in `integration` marker for real-network tests)
  and `vitest`/Playwright are the established runners (`process/context/tests/all-tests.md`). This
  container's egress proxy blocks FRED/DefiLlama/stablecoins.llama.fi with a 403 (per the regime
  dashboard's own AC-11 experience) — the same blockage is expected to apply to Google Trends,
  Reddit, and CoinGecko here, which is why AC-3 and AC-12 both carry an Agent-Probe/real-machine
  component rather than a pure Fully-Automated gate. Automated E2E for everything else should
  follow the regime dashboard's seeded-fixture-cache pattern (`seed_e2e_cache.py`,
  `regime.spec.ts`) so the suite never depends on real provider access.
- **Standing project-wide rules carried in from `all-context.md` and applied directly to this
  SPEC's Constraints:** "numbers are never silently wrong", "one source of numerical truth",
  "confidence over direction" (narrative informs sizing confidence, it does not issue a call), and
  the redistribution-safety posture required because the app intends to open to other users later.

**Status:** DONE
**Summary:** SPEC written for the narrative-mindshare feature's graduation to a standalone
`/narrative` dashboard: 7 user stories, 12 acceptance criteria (all with `proven by:`/`strategy:`,
including a real-machine walkthrough mirroring the regime dashboard's AC-11), one ASCII flow
diagram, explicit out-of-scope and constraints sections recording all three locked user decisions
verbatim (graduate + extend scope, forward-archive history, the three first-cut extras), and three
Open Questions left for INNOVATE/PLAN (category/coin-map scope, exchange proxy choice, Reddit
credential handling in the nightly workflow) since none of them are answerable from RESEARCH alone
and none block understanding of *what* is wanted, only *which exact values* fill in the design.

**Strategy recommendation for INNOVATE:** Sequential, single sonnet agent. Signal score 2/7 — this
extends an existing, well-understood backend (RFC-003) with one new page, one new proxy adapter,
and a scheduled workflow; there is no cross-package coordination need and no reason to fan out
parallel INNOVATE agents. An agent team would be overkill; a single vc-innovate-agent pass can
compare "reuse cache.py's existing narrative_series_path as-is" vs. "add a dedicated dashboard
aggregation layer" and the exchange-proxy source options directly.

`PHASE_COMPLETE: SPEC` — `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_SPEC_24-09-26.md` written and locked. Three Open Questions remain (OQ-1, OQ-2, OQ-3) but none require user resolution before INNOVATE can proceed — they are scoped as next-phase design inputs, not blocked intent. Proceed to INNOVATE.

---

## Post-EXECUTE Amendment (UPDATE PROCESS, 24-09-26)

This SPEC is frozen — the User Stories, Behavioral Outcomes, and all 12 Acceptance Criteria above
are unchanged and unnarrowed. This amendment records how the three Open Questions actually
resolved and confirms every AC's real disposition after all 6 RFCs shipped (code-complete,
EVL-confirmed, committed to branch `claude/kind-tesla-tat3vo` @ `7ef8eb3`). Full mechanism detail
lives in the plan's own `## Post-EXECUTE Amendments` section — this is the SPEC-level summary.

**OQ-1 (category/coin scope) resolved:** no new seed categories were added — the dashboard tracks
the existing 4 (ai, rwa, l2s, memecoins). The coin-to-category map widened via a new, user-editable
curated JSON (`api/data/narrative_category_map.json`, 32 entries) used **only** by `/history` and
`/narrative` — the existing 3-coin legacy map stays frozen and continues to drive
`/categories`/`/screener` exactly as this SPEC's AC-1 requires. This is "option B", the user's own
explicit choice once the RFC-1 Stage 0 finding surfaced that the naive design (one shared map)
would touch `/categories`' output.

**OQ-2 (exchange proxy) resolved:** Hyperliquid, via the existing keyless `ccxt_adapter._exchange()`
singleton — no new provider identity, no new secret. Volume-share denominator = all active,
non-HIP-3 perps plus an explicit `unmapped` bucket; new-listing detection diffs today's market list
against an append-only daily snapshot archive, with an explicit `no-baseline-yet` state on day one
(AC-7 preserved exactly). `redistributable` is recorded `False` pending the user's own Hyperliquid
terms check (a user-PC step) — this SPEC's Constraints already required a redistribution flag per
source; the flag exists and is honest, it simply resolved to the conservative value rather than the
plan's initial assumption of `true`.

**OQ-3 (Reddit nightly credentials) resolved:** no secret is required to ship — confirmed as this
SPEC anticipated. The mechanism differs from the plan's original design: when
`REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` are unset, the nightly job writes **no row at all** for
Reddit (rather than an explicit `unavailable` row), so the dashboard shows Reddit's absence as
"no archived data". This SPEC's "a failed provider degrades to unavailable without taking the page
down" constraint is still satisfied — the distinction between "fetched and failed" and "never
attempted" is itself an honest, typed state, consistent with "numbers are never silently wrong".

**AC-1 disposition:** proven exactly as specified — `GET /api/narrative/categories` is
byte-identical (contract snapshot test, including a newly-mapped-coin-in-trending scenario;
`git diff` on `trigger.py`/`screener_board.py`/`NarrativeStrip.tsx` is empty). **Not narrowed or
reinterpreted** — option B is precisely the mechanism that keeps AC-1 strict while still
satisfying US-5/AC-8's wider-coverage ask through a separate, new code path.

**AC-3 / AC-12 disposition:** both remain exactly what this SPEC always said they'd be — Hybrid /
Agent-Probe, user-machine-only for their live-provider portions. Their Fully-Automated portions are
proven (workflow dry-run + no-duplicate-on-rerun tests; `web/e2e/narrative.spec.ts`, 26/26 x2). The
live portions are pending on the user's own PC — see the plan's Resume and Execution Handoff for
the exact checklist. Both risk-pack manual-first review decisions (RFC-3's new public API, RFC-4's
new `contents: write` scheduled workflow) are also `PENDING` for the same reason.

**AC-2, AC-4 through AC-11:** all proven exactly as specified, no reinterpretation. A real defect
was found and fixed during RFC-6's E2E proof (a pandas `None`→`NaN` coercion bug in
`history.py`, 500ing `/history` from the second nightly archive day onward) — this is evidence the
AC-2/AC-9 gates worked as intended, not a scope change.

**One pre-existing backend bug, found but explicitly not fixed under this SPEC:**
`trigger.py::compute_narrative_categories` reads pytrends/Reddit history by category id, but those
adapters write under the keyword key — so `/categories`' own trigger effectively never sees
archived pytrends/Reddit history. This predates this SPEC (it's RFC-003 of momentum-screener) and
fixing it would change `/categories`' own output, requiring a deliberate, separately-scoped AC-1
re-baseline. Recorded here as an explicit Out-of-Scope confirmation, not silently absorbed.
