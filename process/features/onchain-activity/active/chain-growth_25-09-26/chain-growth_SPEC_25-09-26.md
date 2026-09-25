---
name: spec:chain-growth
description: "New /onchain-activity dashboard comparing daily active addresses, new addresses, and transaction count across major chains (incl. Robinhood Chain, Solana) to spot which chain bottoms then ramps"
date: 25-09-26
metadata:
  node_type: memory
  type: plan
  feature: onchain-activity
---

[MODE: SPEC]

## Summary

The user wants a chart that answers a simple question at a glance: across the major chains
(Ethereum, the leading L2s, BNB, Tron, Solana, and the newly-launched Robinhood Chain), which one
already hit its bottom in on-chain participant activity and is now ramping back up? Today there is
no view anywhere in my_site that tracks *chain-level* participant growth over time — the existing
dashboards cover price/liquidity/narrative, not raw on-chain usage. This feature adds a new
dashboard, `/onchain-activity`, that plots daily active addresses, new addresses, and transaction
count per chain, lets the user see them side by side on a common normalized scale so a bottom-then-
ramp pattern is visually obvious, and is honest everywhere a chain's data is thin, missing, or not
yet comparable (Robinhood Chain launched 2026-07-01 and has almost no history yet).

## User Stories / Jobs To Be Done

**US-1 — See which chain bottomed and is now ramping, at a glance**
As a trader trying to time exposure across chains, I want to see each major chain's participant
activity plotted on a common, comparable scale, so that I can visually spot which chain has already
found its floor and started ramping up again, without doing that comparison in my head.

**US-2 — Track more than one growth signal per chain**
As a trader who doesn't trust a single metric, I want daily active addresses, new addresses, and
transaction count for each chain, so that I can cross-check whether "growth" is real user adoption
(new + active addresses) or just transaction noise (bots, batching, airdrops farming).

**US-3 — See the real chain, not the exchange or L1 alone, when Robinhood is meant**
As the user who typed "Robinhood" while meaning the newly-launched Robinhood Chain (an Arbitrum
Orbit L2), I want the dashboard to track that specific chain from its actual mainnet launch
(2026-07-01), so that I'm comparing a real chain's participant growth, not Robinhood-the-company's
brokerage user count.

**US-4 — Trust the numbers or be told not to**
As a trader who knows different chains count "activity" differently (Solana signers vs. EVM
senders, one source's raw counts vs. another's), I want each chain's series labelled with its
source and counting method, and any chain/metric with too little history or a failed fetch shown as
explicitly unavailable, so that I never mistake an artifact of data collection for a real growth
signal.

**US-5 — Get the exact numbers, not just the shape**
As a trader who wants to confirm a visual "floor then ramp" read with real numbers, I want to hover
or drill into any chain's chart and see the raw daily values behind the curve, so that the picture
isn't just a shape I have to trust blindly.

**US-6 — Add or remove a chain without code changes**
As the user whose watchlist of chains will change over time (new L2s launch constantly), I want to
be able to add or remove a tracked chain by editing a config file, not by asking for a code change
each time, consistent with how the narrative dashboard's coin-to-category map already works.

**US-7 — Know this actually works against real data before trusting it**
As the user who has been burned before by dashboards that look right in tests but break against
real provider data (see the regime and narrative dashboards' own real-cache walkthroughs), I want
someone to confirm this dashboard renders correctly against real, live-fetched chain data before I
rely on it, not just against synthetic test fixtures.

## What The User Wants (Behavioral Outcomes)

- A new page shows one participant-growth panel per tracked chain (Ethereum, Robinhood Chain,
  Base, Arbitrum, Optimism, Polygon, BNB Chain, Tron, Solana at launch), each carrying three daily
  series: active addresses, new addresses, transaction count.
- A comparison view puts every tracked chain on one shared, normalized scale (e.g. indexed to a
  common baseline or a rolling high/low), so a chain that has hit a floor and started climbing back
  is visually distinguishable from one still declining or one still climbing from an earlier peak —
  without the user needing to eyeball wildly different raw magnitudes (Ethereum's daily address
  count vs. Robinhood Chain's) against each other.
- The dashboard marks, per chain, where activity appears to have bottomed and where it has started
  ramping back up, using a stated, consistent rule — but only once a chain has enough history for
  that rule to mean anything; a brand-new chain (Robinhood Chain) shows its raw series without a
  floor/ramp call until it has accumulated enough days to support one.
- Robinhood Chain is visible on the dashboard from day one of tracking, clearly labelled "launched
  2026-07-01 — limited history", rather than hidden until it has a full history window.
- Hovering or drilling into any chain's panel reveals the exact raw daily numbers behind the plotted
  line — the visual is never the only way to read the data.
- Every chain/metric that is missing, unavailable (fetch failed), or has a shorter history than the
  rest is shown as an explicit state on the dashboard — never a blank gap, a silently zero-filled
  day, or a curve that pretends continuity it doesn't have.
- Each chain's series is labelled with which data source computed it and what counting method that
  source uses (so a Solana "active address" count, built on signers, is never visually implied to
  mean the same thing as an EVM "active address" count built on senders, without the user being able
  to see that difference).
- Each data source used is tagged with whether its output may be shown to other users later
  (redistribution flag), matching the project's existing standing rule.
- No provider API key is ever present in anything the browser loads — any keyed source (expected
  for Solana/BNB/Tron coverage) is called from the backend only, with its key stored in environment
  configuration / GitHub Actions secrets, never shipped to the client.
- The user can add or remove a tracked chain by editing a config file, without needing a new
  deployment or a plan/EXECUTE cycle for each chain-list change.
- This is a brand-new page — it does not change the behavior, endpoints, or output of `/regime`,
  `/narrative`, or `/screener` in any way.

## Flow / State Diagram

```
                    ┌────────────────────────────────────────────┐
                    │  Chain list config (user-editable file,      │
                    │  same pattern as narrative_category_map.json)│
                    │  Ethereum / Robinhood Chain / Base / Arbitrum │
                    │  / Optimism / Polygon / BNB / Tron / Solana   │
                    └───────────────────┬────────────────────────┘
                                        │ drives which chains get fetched
                                        ▼
        ┌──────────────────────────────────────────────────────────────┐
        │             Per-chain provider adapter(s)  (api/data/)         │
        │  ------------------------------------------------------------  │
        │  keyless sources (growthepie / L2BEAT-style, EVM L2s)          │
        │  free-keyed sources (Etherscan V2 for 60+ EVM chains,           │
        │  Dune for chains a keyless source can't reach, incl. Solana)   │
        │  Each adapter: same shape, labelled source + counting method    │
        │  per chain, explicit unavailable/stale/insufficient-history     │
        └───────────────────┬─────────────────────────────────────────┘
                            │  one row per (chain, metric, day)
                            ▼
        ┌──────────────────────────────────────────────────────────────┐
        │      Per-chain daily series: DAA, new addresses, tx count       │
        │      (raw values retained; history depth per chain tracked)    │
        └───────────────┬─────────────────────┬──────────────────────┘
                        │                     │
                        ▼                     ▼
        ┌───────────────────────┐   ┌───────────────────────────────┐
        │  Per-chain raw panel   │   │  Normalized/indexed overlay    │
        │  (hover/drill-down     │   │  view -- all tracked chains on  │
        │  shows raw numbers)    │   │  one comparable scale, floor/   │
        │                        │   │  ramp markers once a chain has  │
        │                        │   │  enough history                │
        └───────────────────────┘   └───────────────────────────────┘
                            │                     │
                            └──────────┬──────────┘
                                        ▼
                    ┌────────────────────────────────────────────┐
                    │        /onchain-activity DASHBOARD (NEW)      │
                    │  Robinhood Chain flagged "launched 2026-07-01,│
                    │  limited history" until it has enough days     │
                    │  for a floor/ramp read                         │
                    └────────────────────────────────────────────┘

  Degraded / edge states shown ON the dashboard, never hidden:
   - One chain's source fails to fetch for a day -> that chain/metric reads
     "unavailable" for that day; every other chain is unaffected.
   - A chain has too little history for a floor/ramp call -> raw series
     still shown, no floor/ramp marker drawn, explicit "not enough history
     yet" note.
   - A chain is removed from the config file -> it stops appearing; its
     already-archived history is not deleted.
   - Two chains use different counting methods (e.g. Solana signers vs.
     EVM senders) -> both labelled with their method; never silently
     implied to be the same measurement.
```

## Acceptance Criteria (Testable Outcomes)

**AC-1 — Every tracked chain shows all three participant-growth metrics.**
The dashboard shows daily active addresses, daily new addresses, and daily transaction count for
every chain in the config list (Ethereum, Robinhood Chain, Base, Arbitrum, Optimism, Polygon, BNB
Chain, Tron, Solana).
proven by: chain-growth-per-chain-three-metrics
strategy: Fully-Automated

**AC-2 — Each chain's series is labelled with its source and counting method.**
Every rendered series carries a visible source + method label (e.g. "Etherscan V2, unique sender
addresses" vs. "Dune, unique signer addresses"), so no two differently-defined counts are shown as
if directly comparable without disclosure.
proven by: chain-growth-source-method-labelling
strategy: Fully-Automated

**AC-3 — A normalized comparison view makes floor-then-ramp visually obvious across chains.**
The dashboard offers a view that puts every tracked chain's activity on one shared, normalized
scale (not raw counts side by side), so a chain that bottomed and is climbing is visually
distinguishable from one still declining.
proven by: chain-growth-normalized-overlay-view
strategy: Agent-Probe

**AC-4 — Floor/ramp markers apply a stated, consistent rule, and only appear once a chain has
enough history.**
A chain with sufficient history gets a floor/ramp marker computed by one documented rule applied
identically to every chain; a chain without enough history (e.g. a newly-added chain) shows its raw
series with no marker and an explicit "not enough history yet" note instead.
proven by: chain-growth-floor-ramp-marker-history-gate
strategy: Hybrid (marker placement logic Fully-Automated; the "does this look right on real data"
visual read is Agent-Probe)

**AC-5 — Raw values are available on hover/drill-down for every chain and metric.**
Interacting with any chain's panel (hover or drill-down) reveals the exact raw daily numbers behind
the plotted line.
proven by: chain-growth-drilldown-raw-values
strategy: Agent-Probe

**AC-6 — Robinhood Chain is visible from day one with a limited-history flag.**
Robinhood Chain appears on the dashboard immediately once tracking starts, explicitly labelled
"launched 2026-07-01, limited history," and is not held back or hidden pending a full history
window.
proven by: chain-growth-robinhood-chain-launch-flag
strategy: Fully-Automated

**AC-7 — A missing or failed fetch is always shown as an explicit state, never silently wrong.**
Any chain/metric/day with a failed fetch, no data yet, or insufficient history shows an explicit
unavailable / no-data / insufficient-history state — never a blank gap, a zero-filled value, or an
interpolated line presented as real.
proven by: chain-growth-honest-missing-states
strategy: Fully-Automated

**AC-8 — History depth per chain is disclosed.**
The dashboard (or its drill-down) shows how far back each chain's series actually goes, so the user
can tell a chain with 3 months of history from one with 3 years without guessing from the chart
alone.
proven by: chain-growth-history-depth-disclosure
strategy: Fully-Automated

**AC-9 — Each data source is tagged with a redistribution flag.**
Every provider adapter backing this feature records whether its output may be shown to other users
later, following the project's existing redistribution-flag convention.
proven by: chain-growth-redistribution-flag-per-source
strategy: Fully-Automated

**AC-10 — No provider API key is ever present in client-loaded code or responses.**
Any keyed source (expected for chains needing Etherscan V2 or Dune) is called only from the
backend; no key appears in any file shipped to the browser or in any API response body.
proven by: chain-growth-no-client-side-secrets
strategy: Fully-Automated

**AC-11 — The tracked-chain list is editable via a config file, not code.**
Adding or removing a chain from the dashboard is done by editing a single config file (same pattern
as the narrative feature's coin-to-category map), with no source-code change required to add a
chain already supported by an existing adapter.
proven by: chain-growth-config-driven-chain-list
strategy: Fully-Automated

**AC-12 — A single chain/source failure never takes down the rest of the dashboard.**
If one chain's data source fails entirely for a day (or longer), every other tracked chain
continues to render normally; only the failing chain shows a degraded state.
proven by: chain-growth-single-chain-failure-isolation
strategy: Fully-Automated

**AC-13 — Cross-chain comparison never plots raw, unnormalized counts against each other.**
The comparison/overlay view only ever shows chains against each other after normalization; raw
counts from two chains are never plotted directly on the same shared axis without normalization.
proven by: chain-growth-cross-chain-normalization-boundary
strategy: Fully-Automated

**AC-14 — The real-machine walkthrough confirms the dashboard against live provider data.**
On a machine with real network access to the chosen chain-activity providers (this sandbox's
egress proxy blocks them), the user opens `/onchain-activity` against real fetched/cached data and
confirms: every tracked chain renders its three metrics, the normalized comparison view produces a
sensible floor/ramp read on at least one chain with enough history, Robinhood Chain shows its
limited-history flag, a genuinely failing source (e.g. a missing or revoked API key) shows as
visibly unavailable rather than silently missing, and hover/drill-down shows correct raw numbers.
proven by: chain-growth-real-cache-user-walkthrough
strategy: Agent-Probe (user, real machine — mirrors the regime dashboard's AC-11 and the narrative
dashboard's AC-12 walkthrough precedent; this container cannot reach these providers)

## Out Of Scope

- Robinhood-the-company's own brokerage/app user counts — this feature tracks Robinhood Chain (the
  Arbitrum Orbit L2), not Robinhood's retail brokerage business.
- Equity or traditional-market participant metrics — this is an on-chain (crypto) activity feature.
- Any paid data vendor or paid tier of a source used here (e.g. Dune credits beyond the free
  monthly allowance, Artemis paid API) — free sources only, per the user's locked decision.
- Automated buy/sell signals, position sizing, or any directional call derived from "this chain
  bottomed" — this dashboard shows a pattern for the user to read, it does not decide anything for
  them, consistent with the rest of the app's confidence-over-direction philosophy.
- Backfilling history for a chain/source beyond whatever historical window that specific source can
  natively supply — no source is backfilled from data it doesn't already retain.
- Sybil/bot address filtering or deduplication beyond whatever a chosen source already applies
  natively — this feature does not build its own bot-detection layer.
- Choosing the exact data source per chain (growthepie vs. L2BEAT vs. Etherscan V2 vs. Dune for
  each specific chain) — the sources are known and free-tier-eligible, but the per-chain mapping is
  an INNOVATE/PLAN decision, not locked here.
- Designing the exact floor/ramp detection algorithm (rebased index vs. drawdown-from-high vs. %
  off N-day low vs. some combination) — the requirement is that one consistent, stated rule exists
  and is gated by history depth; the specific formula is an INNOVATE/PLAN decision.
- Designing whether/how a nightly archive job is needed for chains whose source lacks its own deep
  history — left to INNOVATE, same as the requirement that history is disclosed and never silently
  reconstructed.
- Any change to `/regime`, `/narrative`, or `/screener` — this is a new, standalone page.

## Constraints

- **Free sources only — no paid vendor**, per the user's locked decision. Any source needing a paid
  tier for the chains/history this feature needs is out of scope until a proxy demonstrably earns
  it (same standing bar as the narrative feature).
- **One source of numerical truth.** All chain-activity computation (normalization, floor/ramp
  detection, comparison/indexing) happens in Python/backend; the frontend only formats and renders.
- **Numbers are never silently wrong** (project-wide constraint). Missing, failed, or
  insufficient-history data must always render as an explicit state.
- **Providers live behind adapters**, one per provider, under `api/data/` — no chain-specific
  provider name appears in a route, component, or analytics function.
- **Redistribution flag is honored per source**, matching the project's existing standing rule 7 in
  `data-sources/all-data-sources.md`.
- **No secrets in the client.** Any keyed source is called server-side only; keys live in
  environment configuration and, for the scheduled/CI path, GitHub Actions secrets — never in a
  response body or bundled frontend code.
- **Chain list is config-file-driven**, consistent with the narrative feature's
  `narrative_category_map.json` "option B" pattern (user-editable curated list).
- **Rate/credit limits are a real design constraint**, not a detail — the one keyed free-tier
  source expected for Solana/BNB/Tron coverage (e.g. Dune) has a known free-tier ceiling (per
  research: ~40 requests/min, ~2,500 credits/month) that must be respected by caching, not by
  assuming unlimited calls.
- **Definitions differ across account models and must be disclosed, never silently blended.**
  Solana's signer-based activity counting is not the same measurement as an EVM chain's
  sender-based counting; any source's specific counting method must be visible per chain, and no
  two differently-defined counts may be shown as directly equivalent without that label.
- **This is a feature-folder-scoped, standalone addition** — it must not alter the behavior,
  response shape, or test coverage of any existing endpoint (`/api/regime/*`, `/api/narrative/*`,
  `/api/screener/*`) or page (`/regime`, `/narrative`, `/screener`).

## Open Questions

**OQ-1 — Owner: next phase (INNOVATE/PLAN). Which specific source backs each specific chain?**
Research surfaced four candidate free sources (growthepie and L2BEAT's activity API for Ethereum +
L2s, Etherscan V2 for 60+ EVM chains including BNB, and Dune for any chain via SQL including
Solana), but none were live-probed (this sandbox's egress proxy blocks all of them) and no
per-chain assignment has been made. Needs a concrete source-per-chain mapping before PLAN can size
adapter work.

**OQ-2 — Owner: next phase (INNOVATE/PLAN). Who maintains the Dune query/queries this feature
depends on, and how is query drift (Dune SQL changes, schema renames) monitored?**
Dune is SQL-defined and free-tier-limited (~40 req/min, ~2,500 credits/month per the user's
decision note) — a query that stops matching Dune's underlying table schema fails silently unless
something checks it. The exact query ownership/maintenance model is undecided.

**OQ-3 — Owner: next phase (INNOVATE/PLAN). What is Robinhood Chain's chain ID, and which of the
candidate sources (if any) already index it?**
Robinhood Chain (Arbitrum Orbit L2) launched mainnet 2026-07-01 — very recently. Whether
growthepie, L2BEAT, or Etherscan V2 has picked it up yet is unconfirmed; it may need direct
RPC/explorer access instead of an existing aggregator, which changes the adapter design.

**OQ-4 — Owner: next phase (INNOVATE/PLAN). What are the exact redistribution terms for
growthepie, L2BEAT's activity API, Etherscan V2, and Dune?**
None of these four candidate sources' terms of use have been checked for whether their derived
output may later be shown to other users (the project's public-later goal). Each source needs its
`redistributable` flag set from an actual terms read, not assumed, before AC-9 can be marked
correct for that source.

**OQ-5 — Owner: next phase (INNOVATE/PLAN). What exact floor/ramp detection rule is used (rebased
index, drawdown-from-high, % off N-day low, or a blend), and what history-depth threshold gates it?**
The user wants the pattern to be "clearly visible," not a specific formula. The formula and its
minimum-history gate (relevant for Robinhood Chain, which will be the last chain to qualify for a
floor/ramp call) are INNOVATE-level design decisions, not locked by this SPEC.

## Background / Research Findings

- **No on-chain participant-growth or chain-activity provider exists yet anywhere in
  `process/context/data-sources/all-data-sources.md`.** The current provider table covers crypto
  OHLCV (ccxt, CoinGecko), macro liquidity (LiqTide, FRED, Farside), and narrative/social proxies
  (pytrends, Reddit, CoinGecko trending, Hyperliquid) — chain-level activity metrics (DAA, new
  addresses, tx count) are a new provider category for this project.
- **Candidate free sources identified by research, none yet verified live** (this sandbox's egress
  proxy blocks all of them; must be confirmed on the user's machine or in GitHub Actions, same
  constraint the regime and narrative dashboards hit with their own providers):
  - **growthepie** — keyless; covers Ethereum + major L2s; daily active addresses defined as
    unique `from` addresses, plus transaction counts.
  - **L2BEAT activity API** — keyless; tx-count/UOPS (user operations) for L2s.
  - **Etherscan V2** — free API key; unified across 60+ EVM-compatible chains (covers BNB Chain
    and, pending OQ-3, potentially Robinhood Chain); returns raw counts, no derived metrics.
  - **Dune** — free API key; SQL-queryable against any indexed chain including non-EVM chains
    (Solana); free tier is rate/credit-limited (~40 req/min, ~2,500 credits/month).
  - **Artemis** — has purpose-built DAU metrics, but its free-tier API scope was not confirmed by
    research; not assumed usable without verification.
  - **DefiLlama** — confirmed to have no activity/participant metrics; ruled out for this feature.
- **Definitions differ structurally across account models**, not just across vendors: Solana's
  activity is naturally counted by unique transaction *signers*, while EVM chains are naturally
  counted by unique *senders* (`from` address). Bot/sybil activity (airdrop farming, batch
  transactions) can inflate either. This is why per-chain method disclosure is a hard constraint,
  not a nice-to-have — silently blending these into one "active addresses" number across chains
  would misrepresent what's being compared.
- **Floor/ramp detection needs within-chain normalization first.** Research names several
  candidate techniques (rebased index to a common start, drawdown-from-recent-high, % off the
  N-day rolling low, or a smoothed combination) without picking one — left to INNOVATE per the
  user's framing ("see clearly which one hit a floor before it ramps up again" describes the
  *outcome*, not the *method*).
- **User-locked decisions (2026-09-25), carried into this SPEC as constraints, not open
  questions:** "Robinhood" means Robinhood Chain (Arbitrum Orbit L2, mainnet 2026-07-01), not the
  brokerage; all three metrics (DAA, new addresses, tx count) are in scope; all nine named chains
  (Ethereum, Robinhood Chain, Base, Arbitrum, Optimism, Polygon, BNB Chain, Tron, Solana) are in
  scope, including non-EVM (implying at least one free-tier keyed source, most likely Dune, with
  the user creating their own free account/API key as a setup step); Robinhood Chain shows from
  launch with a limited-history flag, and floor/ramp markers wait for sufficient history; free
  sources only, no paid vendor.
- **Precedent for the real-machine walkthrough AC**: both the regime dashboard (AC-11) and the
  narrative dashboard (AC-12) required a user-run walkthrough against real provider data because
  this sandbox's egress proxy blocks the relevant providers, and in both cases the real-cache run
  caught something a synthetic-fixture E2E suite could not (see `tests/all-tests.md` Standing
  Lesson table, narrative-dashboard RFC-6 entry, for the concrete example: a pandas
  `None`→`NaN` coercion bug that only a real multi-day cache boundary surfaced). This feature's
  AC-14 follows the same shape deliberately.
- **Test-strategy grounding** (from `process/context/tests/all-tests.md`): `pytest` (`api/`,
  isolated-cache fixture required for anything touching real cache-like writes, opt-in
  `integration` marker for real-network tests) is the Fully-Automated backend tier; `vitest` +
  component tests are the Fully-Automated frontend-unit tier; Playwright (`web/e2e/`) against a
  seeded fixture cache is the Fully-Automated/Hybrid E2E tier for view-level behavior (comparison
  view, drill-down, honest-state rendering); anything requiring live provider network access or
  genuine human visual judgment is Agent-Probe, consistent with how AC-3/AC-4/AC-5/AC-14 above are
  tagged. No existing test scenario names apply directly (this is a new feature with no prior
  test surface) — the `proven by:` scenario names above are the new scenarios PLAN/EXECUTE must
  create, following the same naming and tiering convention already established by the narrative
  and regime dashboards' own test suites.
- **Regime and narrative dashboard precedent for config-driven, user-editable lists**: the
  narrative dashboard's `api/data/narrative_category_map.json` ("option B" pattern) is the direct
  precedent for AC-11's config-file-driven chain list — same mechanism, different domain.
