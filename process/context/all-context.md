# my_site - All Context

Last updated: 2026-10-03 (master-planner-recovery Gate 2: slimmed to a router; history moved to
context-changelog.md; layout, stack and patterns moved to architecture.md; commands and test tiers
moved to operating-instructions.md). Base commit for the move: `5878b16`.

This file is the root context router. Read it first, pick the smallest relevant doc from the tables
below, then load only that. It is not the full knowledge: follow its routes.

Current observed state (branch, commit, validator results): current-state.md. Task registry and
board: `process/MASTER-PLAN.md`. Decisions: decisions.md.

---

**History:** every former "Changes Since Last Update" entry (2026-09-17 to 2026-10-01) now lives
whole in context-changelog.md (history only, not default load).

## What This Project Is

my_site is a personal-use data-tracking tool for one trader, reached only over Tailscale on the
user's home PC. It shows data as clearly as possible (price, % change, RSI, attention, liquidity,
pair statistics) so the user draws their own conclusions: data, not verdicts.

Full direction, pages, invariants and non-goals: north-star.md. Why it changed (02-10-26):
decisions.md (D-0 to D-2).

## How This File Works (the `all-*.md` Convention)

Every `process/context/` directory has one `all-*.md` entrypoint that routes for its domain. This
file is the top-level router; context groups (`data-sources/`, `planning/`, `tests/`) each have
their own `all-{group}.md`. Root docs sit directly in `process/context/`.

Quick start for any substantial task:

1. read this file first
2. choose the smallest relevant root doc or group entrypoint from the tables below
3. only then load deeper files; never load the whole `process/context/` tree

Each `all-{group}.md` states its scope, read-when rules, quick procedures, deeper sources, update
triggers and routing. Root docs: north-star.md (direction), current-state.md (observed state),
decisions.md (decision log), architecture.md (layout, runtimes, data flow, patterns),
operating-instructions.md (commands, RT0-RT4 test tiers, branch and merge rules),
context-changelog.md (history).

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

## Task Routing Table

| If the task involves... | Load first | Then load |
|---|---|---|
| product scope, a page's purpose, whether a feature belongs | `all-context.md` | north-star.md, then decisions.md |
| what is true right now (branch, commit, tests, validators) | `all-context.md` | current-state.md (check its staleness rule) |
| what to work on next, task status, lanes | `all-context.md` | `process/MASTER-PLAN.md` |
| why something was decided | `all-context.md` | decisions.md |
| architecture, layout, stack, runtimes or data flow | `all-context.md` | architecture.md |
| commands, test tiers, worktree/branch/merge rules | `all-context.md` | operating-instructions.md |
| picking or changing a market-data provider | `all-context.md`, `data-sources/all-data-sources.md` | the provider's own docs |
| adding or changing an indicator / statistical method | `all-context.md`, architecture.md | `data-sources/all-data-sources.md`, the feature `_GUIDE.md` |
| charting work | `all-context.md`, architecture.md | `process/features/charting-indicators/_GUIDE.md` |
| pair / cointegration work | `all-context.md` | `process/features/cointegration-screener/_GUIDE.md` |
| regime or cycle work | `all-context.md` | `process/features/cycle-regime/_GUIDE.md` |
| narrative / mindshare work | `all-context.md`, `data-sources/all-data-sources.md` | `process/features/narrative-mindshare/_GUIDE.md` |
| creating a new plan | `all-context.md`, `planning/all-planning.md` | the example PRD that matches the plan size |
| testing or verification | `all-context.md`, operating-instructions.md | `tests/all-tests.md` |
| fresh checkout to populated cache / manual refresh runbook | `all-context.md` | `api/scripts/BOOTSTRAP.md` |
| deploying to the home PC | `all-context.md`, operating-instructions.md | `deploy/README.md` |
| Master Planner posture, worker envelope, report template | `all-context.md` | `process/development-protocols/master-planner.md` |
| history of a change or a past finding | `all-context.md` | context-changelog.md |
| context maintenance | `all-context.md` | run `vc-audit-context` after edits |

## Context Group Lifecycle

Context groups are durable knowledge domains, not feature folders. Create a group when a topic has
3+ durable docs, a single doc passes roughly 800 lines with separable subtopics, agents repeatedly
need only one slice of a large file, or the topic maps to a stable operational domain (tests, infra,
UI, workflows). Do not create one for temporary reports, plan or execution artifacts, or
feature-specific content (that belongs in `process/features/...`). Move or split one group at a
time and run the `vc-audit-context` skill after every context organization change.

## Naming Convention

There are no `README.md` files inside `process/context/`. Canonical entrypoints use `all-*.md`:
root `process/context/all-context.md`, group `process/context/{group}/all-{group}.md`. Root docs
use a kebab-case name and carry frontmatter (`name: context:<slug>`, `description`, `keywords`,
`date`).

## Context Update Protocol

When durable project knowledge changes:

1. update the smallest relevant context file (current facts go to current-state.md, decisions to
   decisions.md, history to context-changelog.md)
2. update this file if routing, ownership, naming, or groups changed
3. update the owning `all-{group}.md` entrypoint when a group exists
4. run `vc-audit-context`

## Repository Structure

Top level: `web/` (Next.js app, Svelte chart islands, Playwright e2e), `api/` (FastAPI: routers,
analytics, data adapters plus Parquet cache, models, scripts, tests), `deploy/` (home-PC PowerShell
launchers), `.github/workflows/` (`ci.yml` plus five nightly snapshot/refresh jobs), `process/`
(agent harness: context, protocols, plans, `MASTER-PLAN.md`, archive index), `.claude/`, `.codex/`,
`.agents/` (agent and skill surfaces).

Pages: `/screener`, `/regime`, `/narrative`, `/pairs`, `/onchain` (shipped); `/equities` queued.

Detailed layout per folder: architecture.md (Repo layout).

## Technology Stack

- Backend: Python 3.12, FastAPI, uvicorn, managed by `uv`; pandas, numpy, pandas-ta-classic,
  statsmodels, pydantic, httpx, ccxt.
- Frontend: Next.js 15 App Router, React 19, TypeScript, Tailwind 4 with Skeleton, managed by
  `pnpm`; charts are Svelte 5 islands with LayerChart, built by vite.
- Storage: Parquet files read with DuckDB through `api/data/cache.py`; no database server.
- Tests: pytest (`api/`), vitest and Playwright (`web/`); CI runs pytest, vitest, `tsc` and the
  island build.
- Deployment: the user's home PC, reachable only over Tailscale.

Runtimes and boundaries: architecture.md. Commands: operating-instructions.md.

## Key Patterns and Conventions

One source of numerical truth (Python computes, the web renders), providers behind adapters, free
tiers as a constraint, numbers never silently wrong, data not verdicts. Full text: architecture.md
(Patterns and invariants). Naming: kebab-case in `web/`, PascalCase components, snake_case in
`api/`.

## Environment and Configuration

Env and config names (values never in git), and the deploy variables: operating-instructions.md.
The example env file at the repo root lists names only.

## Open Decisions

Carry these into any plan that touches them. Do not resolve them silently.

| Decision | Status |
|---|---|
| Product direction | Settled 02-10-26: personal-use tracker, data not verdicts (north-star.md) |
| Crypto data | Settled and implemented: ccxt (Hyperliquid), no key |
| Macro liquidity / regime input | Implemented both ways: LiqTide endpoint and FRED-based reproduction |
| Equity data provider | Settled: London Strategic Edge, verdict ADOPT-WITH-LIMITS (2026-09-24), used under its private-use terms; no adapter yet; the equities page is queued as registry task P6 |
| Persistence layer | Settled and in use: Parquet + DuckDB |
| Narrative / mindshare data | Free proxies (CoinGecko, pytrends, Reddit, Hyperliquid volume); redesign to user-defined coin baskets queued as P5; each v1 signal needs a live probe on the user's PC |
| Testing strategy | Settled: pytest + vitest + Playwright; risk tiers RT0-RT4 in operating-instructions.md |
| Deployment target | Settled 01-10-26: home PC plus Tailscale, `deploy/` launchers; deploy fixes queued as R12 |
| Package managers | Settled: pnpm (web) + uv (api) |
| Control-surface self-merge, worker lane | Open user decisions (master-planner-recovery plan, Open Questions 10 and 12) |

## Open Questions

Still open, one line each (history and resolved items: context-changelog.md):

- `layer 2 crypto` / `l2s` pytrends values read 0.0 every night; `pytrends-blended/rwa` once wrote
  0.0 as `fresh` (registry T26).
- Whether the five snapshot crons fire on time at their 11:17-13:17 UTC slots (registry T27).
- `web/e2e/screener.spec.ts:103` flake, not yet reproduced against a clean base.
- `mapping.py` tripwire test is weaker than `trigger.py`'s.
- Hyperliquid's apparent daily-history floor (~2020-08-19) and its data terms are unverified.
- No adapter-level failure counting or circuit breaker exists (needs INNOVATE before any code).
- The 2017 leg-boundary backtest window has no usable composite coverage before 2018-01-11.
- The full-vs-reduced liquidity composite comparison waits on the LiqTide archive growing.
- One of six regime components still differs from LiqTide's published value; not root-caused.

## References

Former References and Scan Metadata (source files per amendment, HEAD notes): context-changelog.md.
This version was written on 2026-10-03 from all-context.md at commit `5878b16`, the two 02-10-26
SPECs and the master-planner-recovery plan.
