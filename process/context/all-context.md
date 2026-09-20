# my_site - All Context

Last updated: 2026-09-20

This file is the root context entrypoint for the repo.

Use it for two things:

1. quick routing to the right context pack or root file
2. broad architecture and repository understanding

Start here before loading deeper context files.

---

## Changes Since Last Update (2026-09-17 → 2026-09-20)

The 2026-09-17 version of this file was written from the setup interview, before any code
existed, and said so explicitly ("no application code exists yet"). That is no longer true —
real application code has landed and this update replaces intentions with observations. `[Product]`

- `[Product]` `api/` (FastAPI, Python 3.12, uv) and `web/` (Next.js 15, pnpm) both exist and are
  substantially built out — see Repository Structure below.
- `[Product]` First real feature shipped: a relative-strength **momentum screener** board
  (`process/general-plans/active/momentum-screener_17-09-26/`), with a locked SPEC, a Complex
  plan, and multiple completed RFCs. It is tracked under `process/general-plans/`, not under any
  of the four `process/features/*` folders named below — see Open Questions.
- `[Product]` Seven provider adapters exist under `api/data/`: `ccxt_adapter.py`,
  `coingecko_adapter.py`, `defillama_adapter.py`, `fred_adapter.py`, `liqtide_adapter.py`,
  `pytrends_adapter.py`, `reddit_adapter.py` — all behind the common adapter pattern described
  under Key Patterns.
- `[Product]` Macro liquidity is no longer just "leading candidate: LiqTide" — RFC-002 built
  **both** paths the data-sources group described: consuming the LiqTide endpoint directly
  (`liqtide_adapter.py`) and reproducing the composite from FRED primaries
  (`fred_adapter.py`, WALCL/TGA/RRP/broad-dollar/reserves via FRED's **keyless** `fredgraph.csv`
  export — no API key, matching data-sources' Standing Rule 1).
- Testing strategy is resolved, not deferred: `pytest` for `api/` (with an `integration` marker
  gating real-network tests, deselected by default) and `vitest` + Playwright for `web/`. See
  `tests/all-tests.md`.
- Persistence (Parquet + DuckDB) and package managers (pnpm/uv) were already settled on
  2026-09-17 and are now confirmed in use (`api/data/cache.py`, `api/uv.lock`,
  `web/pnpm-lock.yaml`).
- Equity data provider remains genuinely unresolved — no equity adapter exists yet in `api/data/`.
- Deployment target remains genuinely unresolved — no `.github/workflows/` or other CI/deploy
  config exists.
- The repo is still **not a git repository** (`git rev-parse HEAD` fails) despite a non-trivial
  amount of code now existing — flagged again under Open Questions since this is now a real risk,
  not a fresh-scaffold detail.

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
Changes Since Last Update above) and seven live data-provider adapters. Repository Structure
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

## Current Context Groups

| Group | Entry point | Scope |
|---|---|---|
| planning | `process/context/planning/all-planning.md` | plan-shape calibration, SIMPLE vs COMPLEX, planning conventions |
| tests | `process/context/tests/all-tests.md` | test runners, commands, verification order, known gaps |
| data-sources | `process/context/data-sources/all-data-sources.md` | market-data providers, free-tier limits, licensing, open-source library choices |
<!-- /GENERATED:routing -->

## Task Routing Table

| If the task involves... | Load first | Then load |
|---|---|---|
| architecture or stack questions | `all-context.md` | this file is usually enough |
| picking or changing a market-data provider | `all-context.md`, `data-sources/all-data-sources.md` | the provider's own docs |
| adding or changing an indicator / statistical method | `all-context.md`, `data-sources/all-data-sources.md` | the relevant feature `_GUIDE.md` |
| charting work | `all-context.md` | `process/features/charting-indicators/_GUIDE.md` |
| pair / cointegration work | `all-context.md` | `process/features/cointegration-screener/_GUIDE.md` |
| regime or cycle work | `all-context.md` | `process/features/cycle-regime/_GUIDE.md` |
| narrative / mindshare work | `all-context.md`, `data-sources/all-data-sources.md` | `process/features/narrative-mindshare/_GUIDE.md` |
| creating a new plan | `all-context.md`, `planning/all-planning.md` | the example PRD that matches the plan size |
| testing or verification | `all-context.md`, `tests/all-tests.md` | the specific deeper testing doc once one exists |
| context maintenance | `all-context.md` | run `vc-audit-context` after edits |

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

Observed layout (2026-09-20), 2-3 levels deep on the parts that changed since setup:

```
my_site/
  web/                      -- Next.js 15.0.3 App Router frontend (TypeScript, React 19)
    app/                    -- app/page.tsx, app/layout.tsx, app/screener/page.tsx (only
                                route live so far — charts/regime/narrative routes not built yet)
    components/             -- chart/, screener/
    lib/                    -- api/, types/, format-unavailable-reason.ts, __tests__/
    e2e/                    -- Playwright specs
  api/                      -- FastAPI service (Python 3.12, uv-managed)
    routers/                -- screener.py, regime.py, narrative.py, watchlist.py
    analytics/              -- confidence/, indicators/, narrative/, regime/, screener_board.py
    data/                   -- ccxt_adapter.py, coingecko_adapter.py, defillama_adapter.py,
                                fred_adapter.py, liqtide_adapter.py, pytrends_adapter.py,
                                reddit_adapter.py, cache.py (DuckDB-over-Parquet), watchlist.py
    models/                 -- screener.py, regime.py, narrative.py (pydantic schemas)
    scripts/                -- refresh_cache.py, backfill_primaries.py, and diagnostic/backtest
                                one-offs (backtest_leg_boundaries.py, check_weekly_anchor.py, etc.)
    tests/                  -- analytics/, data/, routers/ — pytest, `integration` marker for
                                real-network tests (deselected by default)
  process/                  -- this agent harness
    context/                -- durable project knowledge (this file + groups)
    general-plans/          -- cross-cutting plans, incl. the momentum-screener feature (see
                                Changes Since Last Update)
    features/               -- feature-scoped plans and guides (charting-indicators,
                                cointegration-screener, cycle-regime, narrative-mindshare —
                                still only `_GUIDE.md` placeholders, no plans written yet)
    development-protocols/  -- RIPER-5 methodology docs
  .claude/ .codex/ .agents/ -- agent + skill surfaces
  .env.example               -- REDDIT_CLIENT_ID/SECRET, LIQTIDE_ATTRIBUTION_URL,
                                 API_BASE_URL, API_PORT (see Environment and Configuration)
```

Not present: `.git/` (repo is not yet git-initialized), `.github/workflows/` (no CI/deploy config).

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
`api/.python-version`. No git repository yet, so `.gitignore` coverage hasn't mattered in
practice — worth setting up before this gets much bigger (see Open Questions).

## Open Decisions

Carry these into any plan that touches them. Do not resolve them silently.

| Decision | Status |
|---|---|
| Crypto data | Settled and implemented — ccxt against a major exchange, no key needed. See data-sources group |
| Macro liquidity / regime input | Implemented, both paths at once (RFC-002): `liqtide_adapter.py` consumes the LiqTide endpoint directly; `fred_adapter.py` reproduces net liquidity + broad dollar + reserves from FRED's keyless CSV export. `api/analytics/regime/liquidity_composite.py` picks a full vs. reduced composite per-date depending on which inputs are available. See data-sources group |
| Equity data provider | Still unresolved — no equity adapter exists in `api/data/` yet. London Strategic Edge remains the leading free candidate **pending verification**; its data is personal-use only, which collides with the public-later goal. See data-sources group |
| Persistence layer | Settled 2026-09-17, confirmed in use — Parquet + DuckDB (`api/data/cache.py`) |
| Narrative / mindshare data source | Implemented on the settled approach: CoinGecko, pytrends, Reddit adapters all exist under `api/data/`, feeding `api/analytics/narrative/`. Still free-proxy-only, still labelled low-confidence |
| Testing strategy | **Resolved** — `pytest` (api, `integration` marker gates real-network tests) + `vitest` + Playwright (web). See `tests/all-tests.md` |
| Deployment target | Still deliberately deferred — no CI/deploy config exists |
| Package managers | Settled 2026-09-17, confirmed in use — pnpm (web) + uv (api) |

**Redistribution is a first-class constraint, not a launch-day detail.** Some free data this
project may depend on is licensed for personal use only and may not be served to other users.
Because the app is intended to open up later, every provider adapter records whether its output
may be redistributed. See Licensing in `data-sources/all-data-sources.md`.

## Open Questions

- **Momentum screener lives under `process/general-plans/`, not `process/features/`.** It's
  the first and only shipped feature, and it draws on macro-liquidity and narrative work that
  overlaps `cycle-regime` and `narrative-mindshare`, but those four `process/features/*` folders
  are still empty `_GUIDE.md` placeholders. Is momentum-screener meant to eventually be split
  into those feature folders, or do they get superseded/consolidated? Don't guess — ask before
  restructuring either side.
- **No git repository yet**, despite `api/` and `web/` now holding a real, tested feature. This
  is no longer a fresh-scaffold non-issue — there's real work with no version history or revert
  safety net. Worth raising with the user rather than silently initializing one.
- **"Numbers are never silently wrong" has a known gap, found 2026-09-20.** `fred_adapter.py`
  had a live bug (CSV header mismatch) that made `fetch_series`/`fetch_net_liquidity` return
  `status="unavailable"` for every call. `api/analytics/regime/liquidity_composite.py`'s
  `build_reduced_composite()` degrades gracefully by design when one input is missing — but nothing
  distinguishes "one input among several is down" from "every FRED series failed on every call,
  repeatedly" (a broken adapter, not a normal degraded-data case). That silently produced at least
  three persisted, degraded backtest reports under
  `process/general-plans/active/momentum-screener_17-09-26/` dated 2026-09-19 (regenerate these
  now that the fetch is fixed). No fix has been designed yet — flagged here so the next session
  doesn't have to rediscover it.

## References

Source files this update was based on: `web/package.json`, `api/pyproject.toml`, `.env.example`,
`api/data/cache.py`, `api/data/fred_adapter.py`, `api/data/liqtide_adapter.py`,
`api/scripts/refresh_cache.py`, `api/scripts/backfill_primaries.py`,
`process/general-plans/active/momentum-screener_17-09-26/momentum-screener_PLAN_17-09-26.md`,
plus directory listings of `api/`, `web/`, and `process/features/*/`.

## Scan Metadata

- Generated: 2026-09-20 by `vc-generate-context` (delta update over the 2026-09-17 setup version)
- HEAD: not a git repository (`git rev-parse HEAD` fails — confirmed, not assumed)
- Mode: delta update from real repo scan (directory listings, `package.json`, `pyproject.toml`,
  `.env.example`, adapter/router/analytics source files, active plan folders) — not a line count
- Package managers: `pnpm` (web/, lockfile present), `uv` (api/, lockfile present)
- Source scanned: `api/` (routers, analytics, data, models, scripts, tests), `web/` (app,
  components, lib, e2e), `process/general-plans/active/momentum-screener_17-09-26/`,
  `process/features/*/` (confirmed placeholder-only), `.env.example`, no `.github/`
