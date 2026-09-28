# my_site - All Context

Last updated: 2026-09-28 (onchain-activity `/onchain` chain participant growth page shipped and
verified — see the first Changes entry below; older entries — 2026-09-17 through 2026-09-25,
covering momentum-screener, regime, narrative and keyword-keying closeouts — moved out to
`process/context/context-changelog.md` in a same-day context-maintenance split)

This file is the root context entrypoint for the repo.

Use it for two things:

1. quick routing to the right context pack or root file
2. broad architecture and repository understanding

Start here before loading deeper context files.

---

## Changes Since Last Update (2026-09-25 → 2026-09-28, onchain-activity)

The chain participant growth program (`process/features/onchain-activity/completed/chain-growth_25-09-26/`)
shipped all 6 RFCs, merged to `main` at `4110e3f`, and is ✅ VERIFIED: the user passed the AC-14
real-archive walkthrough and approved both risk packs on 2026-09-28. First real code in
`onchain-activity/`. The plan's `## Post-EXECUTE Amendments` reconciles its original text.

- `[Product]` New route **`/onchain`** (`web/app/onchain/page.tsx`, `web/components/onchain/`,
  `web/lib/{api,types}/onchain.ts`): six synced per-chain panels (Ethereum, Base, Arbitrum,
  Optimism, Polygon, Robinhood Chain) with floor/ramp markers, an index-100/log comparison overlay,
  "source unavailable" cards for Solana/BNB/Tron, and the growthepie CC BY attribution footer.
- `[Product]` New API: **`GET /api/onchain/growth?metric=&start=`** and **`GET /api/onchain/chains`**
  (`api/routers/onchain_activity.py`, `api/models/onchain_activity.py`,
  `api/analytics/onchain/{growth,comparison,response}.py`). Metrics: `active_addresses`,
  `transactions`. Floor/ramp on EMA28 (N=180, R=0.25, M=14, S=180, 194-day history gate).
- `[Product]` Two new adapters: **`growthepie_adapter.py`** (primary, keyless, CC BY 4.0,
  redistributable) and **`l2beat_adapter.py`** (display-only cross-check, `redistributable=False`);
  chain list in `api/data/chains.json`. Dune was NOT-VIABLE — no API key anywhere. See
  `data-sources/all-data-sources.md` §On-chain Activity.
- `[Product]` **Third nightly workflow**: `.github/workflows/chain-growth-snapshot.yml` (`0 22 * * *`)
  runs `api/scripts/snapshot_chain_growth.py`, merging into `api/data/cache/onchain/` (new
  `.gitignore` carve-out) via `cache.merge_onchain_series` with a 14-day revision window.
- Testing: **516 pytest passed / 5 deselected, 138 vitest (19 files), 42/42 Playwright run twice**
  (new `web/e2e/onchain.spec.ts`, 16 scenarios). See `tests/all-tests.md`.
- In progress elsewhere, not on this branch: the narrative-v2 program, on branch
  `claude/narrative-v2`, RFC-1 of 7 done.

Older "Changes Since Last Update" entries (2026-09-17 → 2026-09-25) now live in
`process/context/context-changelog.md`.

---

## What This Project Is

my_site is a personal market-research web app for a solo trader. Four product areas:
charts with technical indicators, a cointegration / pair screener, a cycle & macro regime
dashboard, and narrative / mindshare tracking.

The point of the app is not signal generation for its own sake. The four areas exist to turn
separate signals into a **confidence level** that drives position sizing. Design decisions
should favour showing how strong a read is, and how much it disagrees with the other reads,
over showing a single directional call.

**Audience:** built for the author's own use first, with the explicit intent to open it to
other users later. That means: no hard-coded personal assumptions, no credentials in the
client, and data-provider licensing has to stay redistribution-safe from the start — but
auth, billing and multi-tenancy are deliberately out of scope until the research tooling works.

**Status as of 2026-09-20: real application code exists and is under active development.**
`api/` and `web/` are both built out, with one shipped feature (the momentum screener — see
Changes Since Last Update above, now in `context-changelog.md`) and seven live data-provider
adapters. Repository Structure
and Technology Stack below now describe what's actually there, not a target. A few items are
still genuinely OPEN DECISION — do not invent an answer for those; ask.

---

## How This File Works (the `all-*.md` Convention)

Every `process/context/` directory has one `all-*.md` entrypoint that acts as an attachable quick router for that domain. This root file (`all-context.md`) is the top-level router. Context groups each have their own `all-{group}.md` entrypoint.

**The pattern:**

```
process/context/
  all-context.md                      <-- THIS FILE: root router
  planning/
    all-planning.md                   <-- group router for planning
  tests/
    all-tests.md                      <-- group router for tests
  data-sources/
    all-data-sources.md               <-- group router for market data providers
```

**How agents use it:**

1. Agent reads `all-context.md` first (this file)
2. Finds the relevant context group from the routing tables below
3. Reads that group's `all-{group}.md` entrypoint
4. Only then loads the specific deep doc needed

This layered routing keeps context windows small. Never load the whole `process/context/` tree.

**What each `all-{group}.md` must contain:**

- Scope (what the group covers and does NOT cover)
- Read-when rules (when an agent should load this group)
- Quick procedures or decision rules
- Source paths (list of deeper docs in the group)
- Update triggers (when to refresh this group's content)
- Routing to deeper docs within the group

---

## Quick Start

For most substantial tasks:

1. read this file first
2. choose the smallest relevant root file or context group from the tables below
3. only then load deeper files

---

## Current Root Entry Points

<!-- The two tables below (Root Entry Points + Context Groups) are GENERATED from each
     context doc's frontmatter by `discover-context.mjs --emit-routing`. Do NOT hand-edit
     between the GENERATED markers — your edits will be overwritten on the next rebuild.
     To change a row, edit the owning doc's frontmatter (description / keywords) and re-emit.
     `--check-routing` fails lint if this block drifts from the frontmatter on disk. -->

<!-- GENERATED:routing -->
| File | Read when |
|---|---|
| `process/context/all-context.md` | any substantial planning, research, review, or implementation task |
| `process/context/data-sources/all-data-sources.md` | Market-data providers, free-tier limits, licensing, and analytics library choices |
| `process/context/planning/all-planning.md` | Plan-shape calibration, SIMPLE vs COMPLEX conventions, planning references |
| `process/context/tests/all-tests.md` | Test runners, commands, verification order, debugging reference, and known gaps |

## Current Context Groups

| Group | Entry point | Scope |
|---|---|---|
| `data-sources/` | `process/context/data-sources/all-data-sources.md` | Market-data providers, free-tier limits, licensing, and analytics library choices |
| `planning/` | `process/context/planning/all-planning.md` | Plan-shape calibration, SIMPLE vs COMPLEX conventions, planning references |
| `tests/` | `process/context/tests/all-tests.md` | Test runners, commands, verification order, debugging reference, and known gaps |
<!-- /GENERATED:routing -->

**Additional root file (not a group entrypoint, so not part of the generated table above):**

| File | Read when |
|---|---|
| `process/context/context-changelog.md` | project history / why a past decision was made / what changed in an earlier session |

## Task Routing Table

| If the task involves... | Load first | Then load |
|---|---|---|
| architecture or stack questions | `all-context.md` | this file is usually enough |
| picking or changing a market-data provider | `all-context.md`, `data-sources/all-data-sources.md` | the provider's own docs |
| adding or changing an indicator / statistical method | `all-context.md`, `data-sources/all-data-sources.md` | the relevant feature `_GUIDE.md` |
| charting work | `all-context.md` | `process/features/charting-indicators/_GUIDE.md` |
| pair / cointegration work | `all-context.md` | `process/features/cointegration-screener/_GUIDE.md` |
| regime or cycle work | `all-context.md` | `process/features/cycle-regime/_GUIDE.md` |
| on-chain activity / chain growth (`/onchain`) | `all-context.md`, `data-sources/all-data-sources.md` | `process/features/onchain-activity/_GUIDE.md` |
| narrative / mindshare work | `all-context.md`, `data-sources/all-data-sources.md` | `process/features/narrative-mindshare/_GUIDE.md` |
| creating a new plan | `all-context.md`, `planning/all-planning.md` | the example PRD that matches the plan size |
| testing or verification | `all-context.md`, `tests/all-tests.md` | the specific deeper testing doc once one exists |
| context maintenance | `all-context.md` | run `vc-audit-context` after edits |
| project history / why a past decision was made | `all-context.md` | `context-changelog.md` |

## Context Group Lifecycle

Context groups are durable knowledge domains, not feature folders.

Create a group when:

- a topic has 3+ durable docs
- a single doc exceeds roughly 800 lines with separable subtopics
- multiple agents repeatedly need only one slice of a large context file
- the topic maps to a stable operational domain (tests, infra, database, auth, UI, workflows, etc.)

Do not create a group when:

- the content is a temporary report
- the content is a plan or execution artifact
- the topic is feature-specific and belongs in `process/features/...`

Move or split one group at a time. Use `all-{group}.md` entrypoints. Run the `vc-audit-context` skill after every context organization change.

## Naming Convention

There are no `README.md` files inside `process/context/`.

Canonical entrypoints use `all-*.md`:

- root: `process/context/all-context.md`
- group: `process/context/{group}/all-{group}.md`

Each `all-{group}.md` file should act as the attachable quick router for that domain:

- tell the agent what the group covers
- give quick procedures and decision rules
- route to smaller deeper files

## Context Update Protocol

When durable project knowledge changes:

1. update the smallest relevant context file
2. update this file if routing, ownership, naming, or groups changed
3. update the owning `all-{group}.md` entrypoint when a group exists
4. run `vc-audit-context`

**Standing trigger for this repo:** the first time real application code lands, re-run
`vc-setup` (or `vc-generate-context`) so that Repository Structure, Technology Stack and
Key Patterns below are replaced by observations instead of intentions.

---

## Repository Structure

Observed layout (2026-09-28), 2-3 levels deep on the parts that changed since setup:

```
my_site/
  web/                      -- Next.js 15.0.3 App Router frontend (TypeScript, React 19)
    app/                    -- app/page.tsx, app/layout.tsx, app/screener/page.tsx,
                                app/regime/page.tsx, app/narrative/page.tsx, app/onchain/page.tsx
                                (charting route not
                                built yet)
    components/             -- chart/, screener/, regime/ (RegimeDashboard, ComponentPanel,
                                Readout, DrillDown + __tests__/), narrative/ (NarrativeDashboard,
                                CategoryHistoryPanel, ComparisonView, ChangeInAttentionView,
                                DataQualityCaveat, RedistributionBadge + __tests__/), onchain/ (OnchainDashboard,
                                ChainPanel, ComparisonOverlay, UnavailableChainCard, … + __tests__/)
    lib/                    -- api/ (incl. regime.ts, narrative.ts, onchain.ts), types/ (same), format-unavailable-reason.ts,
                                format-regime-value.ts, regime-chart-sync.ts,
                                regime-line-segments.ts, narrative-view-model.ts, __tests__/
    e2e/                    -- Playwright specs (screener, regime, narrative, onchain .spec.ts)
  api/                      -- FastAPI service (Python 3.12, uv-managed)
    routers/                -- screener.py, regime.py, narrative.py, onchain_activity.py, watchlist.py
    analytics/              -- confidence/, indicators/, screener_board.py,
                                regime/ (liquidity_composite.py, leg_boundary.py, components.py,
                                components_response.py -- a second maths path alongside the
                                composite/leg-boundary one, not a replacement),
                                narrative/ (scoring.py, trigger.py, mapping.py -- RFC-003
                                original, unchanged behavior; history.py, exchange_attention.py
                                -- new 24-09-26, narrative-dashboard RFC-2/RFC-3),
                                onchain/ (growth.py, comparison.py, response.py -- 27-09-26)
    data/                   -- ccxt_adapter.py, coingecko_adapter.py, defillama_adapter.py,
                                fred_adapter.py, liqtide_adapter.py, pytrends_adapter.py,
                                reddit_adapter.py, etf_flows_adapter.py (8th adapter, Farside),
                                hyperliquid_narrative_adapter.py (9th adapter, new 24-09-26,
                                narrative-dashboard RFC-2), growthepie_adapter.py + l2beat_adapter.py
                                (on-chain, 26-09-26), chains.json, cache.py (DuckDB-over-Parquet,
                                gained exchange-snapshot helpers 24-09-26), watchlist.py
    models/                 -- screener.py, regime.py, narrative.py, onchain_activity.py (pydantic schemas;
                                narrative.py gained additive history models 24-09-26)
    scripts/                -- refresh_cache.py, backfill_primaries.py, backfill_liqtide_series.py,
                                seed_e2e_cache.py (gained build_narrative_fixture/seed_narrative
                                24-09-26), snapshot_narrative.py, backfill_pytrends_history.py
                                (both new 24-09-26, narrative-dashboard RFC-2/RFC-4),
                                snapshot_chain_growth.py, probe_chain_sources.py (on-chain), and
                                diagnostic/backtest one-offs (backtest_leg_boundaries.py,
                                check_weekly_anchor.py, snapshot_liqtide.py,
                                compare_composite_variants.py, etc.)
    tests/                  -- analytics/, data/, routers/, scripts/ -- pytest,
                                `integration` marker for real-network tests (deselected by default)
  process/                  -- this agent harness
    context/                -- durable project knowledge (this file + groups)
    general-plans/          -- cross-cutting plans, incl. the momentum-screener feature (see
                                Changes Since Last Update, now in `context-changelog.md`)
    features/               -- feature-scoped plans and guides. `cycle-regime/` and
                                `narrative-mindshare/` both now have real task folders
                                (`regime-dashboard_24-09-26/`, `narrative-dashboard_24-09-26/`,
                                all RFCs code-done, see Changes Since Last Update, now in
                                `context-changelog.md`);
                                `narrative-mindshare/completed/` also holds
                                `narrative-keyword-keying_25-09-26/`; `onchain-activity/completed/`
                                holds `chain-growth_25-09-26/` (verified 28-09-26); still-empty
                                `_GUIDE.md` placeholders: charting-indicators,
                                cointegration-screener
    development-protocols/  -- RIPER-5 methodology docs
  .github/workflows/        -- liqtide-snapshot.yml (nightly 23:30 UTC), narrative-snapshot.yml
                                (nightly 23:00 UTC, new 24-09-26), chain-growth-snapshot.yml
                                (nightly 22:00 UTC, new 26-09-26) -- all snapshot + commit to
                                main, see Changes Since Last Update (now in `context-changelog.md`)
  .claude/ .codex/ .agents/ -- agent + skill surfaces
  .env.example               -- REDDIT_CLIENT_ID/SECRET, LIQTIDE_ATTRIBUTION_URL,
                                 API_BASE_URL, API_PORT (see Environment and Configuration)
```

Deployment CI/CD (beyond the three nightly snapshot workflows -- liqtide, narrative, chain-growth) remains not present -- see Open Decisions.

The web/api split is deliberate: see the first entry under Key Patterns.

## Technology Stack

Confirmed installed/configured as of 2026-09-20 (versions from `web/package.json` /
`api/pyproject.toml`), not just decided.

- **Frontend:** Next.js 15.0.3 (App Router), React 19, TypeScript
- **Charts:** `lightweight-charts` ^5.0.0 (Apache-2.0, canvas-based)
- **Backend:** Python >=3.12 with FastAPI >=0.115, uvicorn[standard]
- **Data/analytics libs in use:** `pandas`>=2.2, `numpy`>=1.26, `pandas-ta-classic`>=0.8.32,
  `pydantic`>=2.8, `httpx`>=0.27. `statsmodels`/`arch` (for cointegration/regime work) are named
  in the original plan but not yet in `api/pyproject.toml` — add them when that analytics work
  actually starts, don't assume they're installed.
- **Market data access:** `ccxt`>=4.3 (MIT) as the unified crypto exchange client — no API key
  for public OHLCV
- **Storage:** Parquet files queried with DuckDB (`duckdb`>=1.0, `pyarrow`>=17.0) via
  `api/data/cache.py`. No database server. Postgres/Timescale remains the migration target if
  the app ever needs concurrent multi-user writes.
- **Package managers:** `pnpm` for `web/` (`pnpm-lock.yaml`, `pnpm-workspace.yaml`), `uv` for
  `api/` (`uv.lock`, `.python-version`)
- **Deployment:** still OPEN DECISION — no `.github/workflows/` or other CI/deploy config exists
- **Testing:** resolved — `pytest`>=8.3 for `api/` (testpaths=`tests`, `integration` marker for
  real-network tests, deselected by default via `addopts = "-m 'not integration'"`); `vitest`
  ^2.1.4 (unit) + `@playwright/test` ^1.48.0 (e2e) for `web/`. See `tests/all-tests.md` for
  exact commands.

### Why two runtimes

Cointegration testing (Engle-Granger, Johansen), regime modelling and volatility models have
no serious JavaScript equivalent — `statsmodels` and `arch` are the reason Python is in the
stack. Charting is the reverse: `lightweight-charts` is the best free financial charting
library and it is a browser library. The split follows the maths, not preference.

## Key Patterns and Conventions

These were decisions made at setup and are now observed in the codebase (`api/data/*_adapter.py`,
`api/data/cache.py`, `api/analytics/`).

**One source of numerical truth.** Every indicator, statistic and derived number is computed
in Python and sent to the frontend as data. TypeScript formats and renders; it never
re-implements an indicator for display. Two implementations of the same calculation is the
single most likely way this project produces quietly wrong numbers.

**Providers live behind adapters.** No route, component or analytics function talks to an
exchange or vendor API directly. Every provider is wrapped in an adapter under `api/data/`
exposing the same shape, so swapping a provider is a one-file change. This matters because
the data-provider decision is deliberately unresolved — see `data-sources/all-data-sources.md`.

**Free tiers are a design constraint, not a detail.** Fetching is cached and rate-limited at
the adapter layer. Assume every provider limit will be hit during development.

**Numbers are never silently wrong.** A calculation with insufficient data, a failed
convergence, or a stale cache returns an explicit "insufficient/unavailable" state that the
UI renders as such. No NaN, no zero-filled series, no silently truncated lookback.

**Confidence over direction.** Where a feature could show either a call or a confidence,
prefer the confidence, and show the disagreement between signals rather than hiding it.

**Naming:** kebab-case files in `web/`, PascalCase React components, snake_case throughout
`api/`.

## Environment and Configuration

`.env.example` exists at repo root (names only, never real values, matches Security Posture):

```
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
LIQTIDE_ATTRIBUTION_URL=
API_BASE_URL=http://127.0.0.1:8000
API_PORT=8000
```

- Market data (equities): still no variable — no equity adapter exists yet (see Open Decisions)
- Market data (crypto): none required — ccxt public OHLCV
- Macro liquidity (FRED): none required — keyless `fredgraph.csv` export, by design (Standing
  Rule 1 in `data-sources/all-data-sources.md`)
- Macro liquidity (LiqTide): none required to fetch; `LIQTIDE_ATTRIBUTION_URL` exists for the
  attribution condition LiqTide's terms require
- Narrative / social data: `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` required for the Reddit
  adapter; CoinGecko and pytrends need no key
- App: `API_BASE_URL`, `API_PORT`

Config files present: `web/package.json`, `web/tsconfig.json`, `api/pyproject.toml`,
`api/.python-version`. Git repository initialized 2026-09-20; `.gitignore` excludes `.venv/`,
`node_modules/`, `__pycache__/`, `.next/`, and (added at init time) `.env` and
`.claude/hooks/.logs/`. **`api/data/cache/` changed 20-09-26** from a blanket ignore to
`api/data/cache/*` + `!api/data/cache/liqtide/` (negation line after the broader ignore) — every
other cache subfolder stays untracked, but `api/data/cache/liqtide/` is now git-tracked so the
daily LiqTide archive survives (one file present as of this update: `2026-09-20.parquet`). See
the 18:47 Amendment above and `data-sources/all-data-sources.md` Standing Rule 8.

## Open Decisions

Carry these into any plan that touches them. Do not resolve them silently.

| Decision | Status |
|---|---|
| Crypto data | Settled and implemented — ccxt against a major exchange, no key needed. See data-sources group |
| Macro liquidity / regime input | Implemented, both paths at once (RFC-002): `liqtide_adapter.py` consumes the LiqTide endpoint directly; `fred_adapter.py` reproduces net liquidity + broad dollar + reserves from FRED's keyless CSV export. `api/analytics/regime/liquidity_composite.py` picks a full vs. reduced composite per-date depending on which inputs are available. See data-sources group |
| Equity data provider | Still unresolved — no equity adapter exists in `api/data/` yet. London Strategic Edge remains the leading free candidate **pending verification**; its data is personal-use only, which collides with the public-later goal. See data-sources group |
| Persistence layer | Settled 2026-09-17, confirmed in use — Parquet + DuckDB (`api/data/cache.py`) |
| Narrative / mindshare data source | Implemented on the settled approach: CoinGecko, pytrends, Reddit adapters all exist under `api/data/`, feeding `api/analytics/narrative/`. Still free-proxy-only, still labelled low-confidence. Widened 24-09-26 with a 9th adapter (Hyperliquid, keyless, display-only, `redistributable=False` pending user terms check) and a standalone `/narrative` history dashboard — see Changes Since Last Update, now in `context-changelog.md` |
| Testing strategy | **Resolved** — `pytest` (api, `integration` marker gates real-network tests) + `vitest` + Playwright (web). See `tests/all-tests.md` |
| Deployment target | Still deliberately deferred — the only CI/scheduling config that exists is three single-purpose nightly workflows, `liqtide-snapshot.yml`, `narrative-snapshot.yml` and `chain-growth-snapshot.yml` (see Repository Structure); no app deploy pipeline |
| Package managers | Settled 2026-09-17, confirmed in use — pnpm (web) + uv (api) |

**Redistribution is a first-class constraint, not a launch-day detail.** Some free data this
project may depend on is licensed for personal use only and may not be served to other users.
Because the app is intended to open up later, every provider adapter records whether its output
may be redistributed. See Licensing in `data-sources/all-data-sources.md`.

## Open Questions

- **New, 2026-09-28: Solana, BNB Chain and Tron have no free on-chain activity source.** Dune (the
  only candidate) is NOT-VIABLE on a free read-only account; Etherscan V2/Artemis are paid. They
  render as "source unavailable" on `/onchain`. Revisit only if a free keyless source appears.
- **New, 2026-09-28: GitHub scheduled crons run ~2 hours late** (observed on the nightly snapshot
  workflows). Harmless today; a suggested follow-up task exists: "Move nightly snapshot crons
  earlier in the UTC day".

- **Momentum screener lives under `process/general-plans/`, not `process/features/`.** It's
  the first shipped feature, and it draws on macro-liquidity and narrative work that overlaps
  `cycle-regime` and `narrative-mindshare`. **Partially resolved, 24-09-26, for narrative only:**
  the narrative surface (`api/analytics/narrative/`, the pytrends/reddit/coingecko/hyperliquid
  adapters, `api/routers/narrative.py`) is now explicitly planning/documentation-owned by
  `narrative-mindshare/`, per the narrative-dashboard plan's ADR-1 — no source files moved.
  `cycle-regime/` reached the same real-code state independently (the regime dashboard). Still
  open: whether the *rest* of momentum-screener (screener board, confidence badges, leg-boundary/
  liquidity-composite regime maths) ever splits out of `process/general-plans/`, or stays there
  permanently as the cross-cutting integration layer these three features feed into. Don't guess
  — ask before restructuring momentum-screener itself.
- **New, 24-09-26: known pre-existing keying bug in `/categories`' trigger, found but explicitly
  not fixed.** `trigger.py::compute_narrative_categories` reads pytrends/Reddit archived history by
  category id, but `pytrends_adapter.py`/`reddit_adapter.py` write under the keyword key instead
  (e.g. `pytrends/AI crypto.parquet`, not `pytrends/ai.parquet`) — so `/categories`' trigger never
  actually reads back archived pytrends/Reddit history; it effectively runs on CoinGecko alone.
  Predates the narrative-dashboard program (this is RFC-003 of momentum-screener); found during
  narrative-dashboard RFC-3. Fixing it changes `/categories`' own output and needs a deliberate,
  separately-scoped AC-1 re-baseline plus user sign-off — queued as a follow-up plan, not absorbed
  into the narrative-dashboard program. Don't fix ad hoc.
- **New, 24-09-26: Hyperliquid's terms of use for redistributing market data are unverified.**
  `HYPERLIQUID_REDISTRIBUTABLE = False` in `api/data/hyperliquid_narrative_adapter.py` pending the
  user reading Hyperliquid's ToU/API docs — a one-line flip once confirmed. Also unverified: real
  Hyperliquid ticker shapes for `k`-prefixed meme perps beyond what the installed `ccxt` source
  shows (this sandbox's egress proxy blocks the live call). See the narrative-dashboard plan's
  Resume and Execution Handoff for the exact user-PC steps.
- ~~No git repository yet~~ **Resolved 2026-09-20** — `git init` done, initial baseline commit
  captures pre-fix state (including the 3 contaminated backtest reports, preserved for diffing),
  second commit holds the fix below.
- ~~"Numbers are never silently wrong" gap — consumer-level~~ **Fixed 2026-09-20.**
  `build_reduced_composite()`'s `composite_available` now derives from realized weight coverage
  (60% of intended weight, see `COMPONENT_WEIGHTS`/`AVAILABILITY_WEIGHT_THRESHOLD` in
  `liquidity_composite.py`) instead of "at least one component returned data." Re-run against live
  data confirms the old 2020-21 confirmed leg boundaries (`2020-04-07`, `2020-04-21`) do not
  survive with real inputs — they were artifacts of the bug, not real signal. Contamination check:
  those dates never reached any screener config or feature file (`write_confirmed_boundaries()` in
  `cache.py` has no caller), so nothing downstream needs correcting.
- **New, adapter-level half still open (not yet designed):** the consumer-level fix above closes
  the *symptom* (a composite silently claiming availability from a sliver of its inputs) but not
  the *cause* (an adapter — any of the 7 under `api/data/`, not just FRED — going to
  100%-`unavailable` across consecutive calls, with nothing distinguishing that from ordinary
  per-item missing data). Research done 2026-09-20: all 7 adapters share a typed
  `ok`/`unavailable`/`stale` convention, but no failure-counting/circuit-breaker state exists
  anywhere in `api/` (the closest precedent, `pytrends_adapter`'s `presumed-dead`, is time-since-
  last-success, not call-count, and is per-keyword). No scheduler exists in this repo at all —
  every adapter call is either router→analytics request-scoped or a manually-run script — so
  "consecutive calls" only accumulates when something happens to trigger a fetch. Needs a proper
  INNOVATE pass before implementation; do not patch this ad hoc.
- **New finding, 2026-09-20: the 2017 leg-boundary backtest window is largely untestable as
  currently scoped.** The reduced composite has zero usable (≥60%-coverage) dates before
  2018-01-11 — DefiLlama's stablecoin-supply series doesn't start until 2017-11-29, and net
  liquidity + dollar alone (56.25% of intended weight) sits just under the 60% floor. The
  `2017` cycle backtest (`process/general-plans/active/momentum-screener_17-09-26/`,
  `--cycle 2017`) is effectively testing ~7 weeks of early 2018, not the 2017 cycle it's named
  for. Undecided: accept this as a structural limit and document it in the backtest's own output,
  or find another approach for pre-2017-11 dates. Don't guess — ask.
  **Sharpened, still unresolved, 2026-09-20 18:47:** the post-ADR-1-Amendment confirming backtest
  (`leg-boundary-backtest-report-20260920-184700.json`) reproduces exactly this — 2017 → 0
  candidates / 0 confirmed against 34 in-window composite points, unchanged by either ADR-1 fix.
  This rules out "the ROC bug/threshold was masking 2017 signal" as an explanation: the 2017 gap is
  purely the pre-2018 coverage floor described above, not a downstream effect of the amendments.
  The choice between accepting the structural limit vs. finding another pre-2017-11 approach is
  still open — this evidence narrows the cause, it does not answer the question.
- **New, 2026-09-20 18:47: the full-vs-reduced liquidity composite agreement question (the
  LiqTide snapshot tooling's actual purpose) remains unanswered, and may stay that way for a long
  time.** `api/data/cache/liqtide/` now holds one archived day (`2026-09-20.parquet`); LiqTide has
  no historical endpoint, so the archive can only grow forward one day at a time, and
  `compare_composite_variants.py`'s `full.available` stays `false` over the 2024-01-11..2026-09-20
  window until there's materially more than one day of history to compare against. Not a code
  defect — see the 18:47 Amendment above for the mechanics and the corrected reduced-composite
  candidate count. **Update, 2026-09-24: this is not the same composite as the one below, and
  stays open on its own terms** — `compare_composite_variants.py` compares `liquidity_composite.py`'s
  reduced vs. full variant (the leg-boundary input), which is unaffected by the regime dashboard
  work. The archive-accumulation constraint described here is unchanged; don't conflate it with
  the regime dashboard's ADR-1 reproduction, which is a separate module (`components.py`) built to
  sidestep exactly this multi-year wait for a different (but related) purpose. Still undecided:
  whether to accept the wait, backfill LiqTide history from its six underlying sources, or drop
  this specific comparison as a goal. Don't guess — ask.
- **New, 2026-09-24, mostly resolved: does the regime dashboard's reproduced composite agree with
  LiqTide's published index?** Yes, closely, on the overlap window that exists — a real-data check
  during RFC-002 found 5 of 6 components exact and Pearson r = 0.964 between the reproduced and
  published composite. This is a different, narrower question than the `compare_composite_variants.py`
  one above (that one needs the archive to grow for years; this one only needs the overlap that
  already exists between LiqTide's own publish window and our primaries). Not fully closed:
  the exact overlap window is short (LiqTide's own history is ~2024-09 at best) and the 1/6
  mismatched component hasn't been root-caused — see the RFC-002 phase report for the specific
  component and its residual.
- ~~AC-11 real-cache user walkthrough for `/regime` has not run.~~ **Resolved 2026-09-24 (2nd
  UPDATE PROCESS pass).** The user ran the walkthrough on their own PC against the real cache (3y
  default range, zoom/hover/drill-down sync, ETF "not applicable before 2024-01-11" note, ~2000+
  point performance) and confirmed "all seems fine". One question — a blank stretch on the
  BTC-dominance panel — was explained and accepted as correct honest-gap behaviour, not a bug (see
  the two-depth-limits entry below). The regime-dashboard plan and its task folder are archived at
  `process/features/cycle-regime/completed/regime-dashboard_24-09-26/`.
- **Two component depth limits, accepted, not solved (BTC-dominance limit sharpened 2026-09-24).**
  BTC-dominance history has no free, keyless source deeper than LiqTide's own `metrics.btc_dom.series`
  (~2025-06 at best; CoinGecko's historical global market cap, which would let this be reproduced
  independently like the other five components, is paid-tier only). That series also has a real,
  permanent 209-day hole, **2025-12-07 → 2026-07-04** (161 points on either side, otherwise 1-3 day
  steps) — confirmed during the user's AC-11 walkthrough, who noticed the BTC-dominance panel's
  30-day change resumes only on 2026-08-03 (the as-of value 30 days earlier would be the stale
  pre-hole December reading). The nightly archive (RFC-001) prevents any *new* hole from forming;
  this specific historical gap is not backfillable from any known free source and the user chose to
  leave it. Spot-ETF flows separately, structurally cannot exist before 2024-01-11 (product launch
  date). Both panels show honest "no data" / "not applicable" states rather than any fill. Revisit
  only if a free deeper BTC-dominance source appears — don't invent one.

## References

Source files this update was based on: `web/package.json`, `api/pyproject.toml`, `.env.example`,
`api/data/cache.py`, `api/data/fred_adapter.py`, `api/data/liqtide_adapter.py`,
`api/scripts/refresh_cache.py`, `api/scripts/backfill_primaries.py`,
`process/general-plans/active/momentum-screener_17-09-26/momentum-screener_PLAN_17-09-26.md`,
plus directory listings of `api/`, `web/`, and `process/features/*/`.

**Added at the 18:47 amendment (UPDATE PROCESS closeout of two 20-09-26 threads):**
`api/analytics/regime/leg_boundary.py` (via the plan's ADR-1 Amendment + Amendment #2 text, read
directly), `api/scripts/snapshot_liqtide.py`, `api/scripts/compare_composite_variants.py`,
`process/general-plans/active/momentum-screener_17-09-26/leg-boundary-backtest-report-20260920-184700.json`,
`process/general-plans/active/liqtide-snapshot-tooling_20-09-26/liqtide-snapshot-tooling_REPORT_20-09-26.md`,
`process/general-plans/active/liqtide-snapshot-tooling_20-09-26/composite-variant-agreement-20260920-180830.json`
and `...-183336.json`, a `device_list_dir` of `api/data/cache/liqtide/` (one file:
`2026-09-20.parquet`), and
`process/general-plans/active/momentum-screener_17-09-26/update-process-closeout_20-09-26.md`.

**Added at the 2026-09-24 UPDATE PROCESS closeout (regime dashboard, RFC-001..006):**
`process/features/cycle-regime/completed/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`
(full plan incl. Status Strip, ADRs, Validate Contract, Resume and Execution Handoff), all six
`regime-dashboard_24-09-26-RFC-00N-phase-report.md` files in that task folder, the Stage-0 reports
for RFC-001/RFC-002, the Farside `regime-dashboard-farside_FEASIBILITY_24-09-26.md`, the
`regime-dashboard-validate_REPORT_24-09-26.md`, `.github/workflows/liqtide-snapshot.yml`, and
`git log`/`git status` at `db8d854`.

**Added at the 2026-09-24 UPDATE PROCESS closeout (narrative-mindshare `/narrative` dashboard,
RFC-1..6):**
`process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
(incl. the new `## Post-EXECUTE Amendments` section), `narrative-dashboard_SPEC_24-09-26.md` (incl.
its `## Post-EXECUTE Amendment`), all six `narrative-dashboard_RFC-00N_REPORT_24-09-26.md` files
and both `*-stage0_REPORT_*.md` files in that task folder,
`narrative-dashboard-pvl-iteration-001_REPORT_24-09-26.md`,
`narrative-dashboard-evl-iteration-001_REPORT_24-09-26.md`, `results.tsv`, `.github/workflows/
narrative-snapshot.yml`, and `git log`/`git status`/`git show --stat` at `7ef8eb3` on branch
`claude/kind-tesla-tat3vo`.

**Added at the same-day 2nd UPDATE PROCESS pass (AC-11 confirmed, regime plan archived):** the
plan's Status Strip (all six RFCs ✅ VERIFIED), `regime-dashboard_CLOSEOUT_24-09-26.md` (updated
classification), and `git log --oneline -- api/data/cache/liqtide/*.parquet` (4 consecutive
automated `github-actions[bot]` commits, 09-21..09-24, cited as evidence the nightly schedule
mechanism runs unattended).

## Scan Metadata

- 2026-09-28 context-maintenance split (docs only, no source code): the four oldest "Changes
  Since Last Update" entries (2026-09-17 → 2026-09-25) were moved byte-identical out of this file
  into the new root context file `process/context/context-changelog.md`, to bring this file back
  under the ~800-line guideline (was 842 lines). Newest entry (2026-09-25 → 2026-09-28,
  onchain-activity) stays here. No facts, paths, or numbers changed — see
  `process/context/context-changelog.md` for the moved history.
- Generated: 2026-09-20 by `vc-generate-context` (delta update over the 2026-09-17 setup version);
  amended same day after `git init` + the composite availability-floor fix; amended again 18:47
  by `vc-update-process-agent` closing out the ADR-1 leg-boundary and liqtide-snapshot-tooling
  threads; amended again 2026-09-24 by `vc-update-process-agent` closing out the regime dashboard
  program; amended a further time the same day (2026-09-24, 2nd pass) after the user confirmed
  AC-11 on their PC and the regime task folder was archived to `completed/`; amended a third time
  same day (24-09-26) by `vc-update-process-agent` closing out the narrative-mindshare
  `/narrative` dashboard program (no `vc-generate-context` re-run for any of these amendments —
  targeted UPDATE PROCESS edits per this file's own Context Update Protocol); this version is
  further the result of merging two independent same-day sessions' branches together
- HEAD (pre-merge): `7ef8eb3` (branch `claude/kind-tesla-tat3vo`, narrative-dashboard closeout) and
  `ecb5e39` (branch `claude/compassionate-goldberg-o2iq49`, regime-dashboard AC-11-confirmed
  closeout) — two independent branches/sessions, reconciled here via a `git merge` commit rather
  than a single linear history
- Mode: delta update from real repo scan (directory listings, `package.json`, `pyproject.toml`,
  `.env.example`, adapter/router/analytics source files, active plan folders) — not a line count.
  18:47 and both 2026-09-24 amendments were targeted reads (the plan file(s), their RFC phase
  reports, `git log`/`git status`/`git show --stat`, and directory listings of the new source
  paths for that program) — not a full repo re-scan each time
- Package managers: `pnpm` (web/, lockfile present), `uv` (api/, lockfile present)
- Source scanned (narrative-dashboard amendment): `api/analytics/narrative/{history,
  exchange_attention}.py`, `api/data/hyperliquid_narrative_adapter.py`,
  `api/data/narrative_category_map.json`, `api/routers/narrative.py`, `api/models/narrative.py`,
  `api/scripts/{snapshot_narrative.py,backfill_pytrends_history.py}`,
  `web/app/narrative/`, `web/components/narrative/`, `web/lib/{api,types}/narrative.ts`,
  `web/e2e/narrative.spec.ts`, `.github/workflows/narrative-snapshot.yml`,
  `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/` (plan, SPEC, all RFC
  reports, results.tsv), `git diff 7ef8eb3~9..7ef8eb3 --stat` (58 files, +5536/-4)
- Source scanned (regime-dashboard amendment, unchanged from prior entry): `api/` (routers,
  analytics incl. `regime/`, data incl. `etf_flows_adapter.py`, models, scripts, tests), `web/`
  (app incl. `regime/`, components incl. `regime/`, lib, e2e),
  `process/general-plans/active/momentum-screener_17-09-26/`,
  `process/features/cycle-regime/completed/regime-dashboard_24-09-26/`, `process/features/*/` (the
  other three still placeholder-only), `.env.example`, `.github/workflows/liqtide-snapshot.yml`
- 2026-09-25 amendment: `vc-update-process-agent` closeout of the narrative-keyword-keying
  fix (targeted edits; `api/analytics/narrative/trigger.py` + its tests), then merged into
  `claude/kind-tesla-tat3vo`
- 2026-09-28 amendment: `vc-update-process-agent` closeout of the onchain-activity chain-growth
  program (targeted edits from the plan, its RFC-001..006 reports and the directory listings of
  the new onchain source paths; `main` at `4110e3f`)
