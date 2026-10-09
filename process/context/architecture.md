---
name: context:architecture
description: "Essential architecture of my_site: repo layout, runtimes and their boundaries, data flow from providers to pages, and the patterns every change must keep."
keywords: architecture, layout, repository structure, stack, runtimes, fastapi, nextjs, svelte, islands, layerchart, adapters, cache, parquet, duckdb, data flow, patterns, invariants
date: 03-10-26
---

# Architecture

**Two halves split by the maths: a Python API (FastAPI) computes every number; a Next.js web app renders them, with charts as Svelte islands. Data comes from providers through adapters into a Parquet cache, then through analytics and routers to the pages.** Product direction: north-star.md. Commands and test rules: operating-instructions.md.

Carved out of all-context.md on 03-10-26. The earlier long-form layout, stack and pattern text is preserved in git history and in context-changelog.md.

## Repo layout

| Path | Holds |
|---|---|
| `web/app/` | Next.js App Router pages: `screener/`, `regime/`, `narrative/`, `pairs/` (plus `pairs/[a]/[b]/` detail), `onchain/`, root `page.tsx` and `layout.tsx` |
| `web/components/` | React components per page (`screener/`, `regime/`, `narrative/`, `pairs/`, `onchain/`), plus `shell/` (app nav), `brand/` (OwlMark), `chart/` |
| `web/islands/` | Svelte 5 chart islands (LayerChart): regime, narrative, onchain, spread chart, shared panel sync |
| `web/lib/chart-viewport.ts` | custom chart viewport: Ctrl/Cmd+wheel and pinch zoom, drag pan, double-click reset; vector axis text over Canvas lines; `screener/SpaghettiChart.tsx` replaced the relative-performance chart |
| `web/lib/` | API clients (`api/`), types, formatters, `island-loader.ts`, view models |
| `web/e2e/` | Playwright specs (screener, regime, narrative, pairs, onchain, contrast) |
| `api/routers/` | `screener.py`, `regime.py`, `narrative.py`, `pairs.py`, `onchain_activity.py`, `watchlist.py` |
| `api/analytics/` | `indicators/` (`gain.py`, `rsi.py`, `sma.py`; verdict, confidence, benchmark and momentum modules removed in S4), `regime/` (`/api/regime/legs` and `/btc-legs` read BTC OHLCV cache-only), `narrative/`, `cointegration/`, `onchain/`, `screener_board.py` |
| `api/data/` | provider adapters (`*_adapter.py`; `lse_adapter.py` and `equities_store.py` are private-use, non-redistributable), `cache.py`, `freshness.py` (pure staleness rules; `fetched_at` sidecar `<tf>.meta.json`; 200-bar sub-daily retention), `refresh_worker.py` (background refresh, env `SCREENER_REFRESH_WORKER` 0/1/unset = on), config JSON (watchlist, pairs universe, narratives, chains) |
| `api/models/` | pydantic response models per router |
| `api/scripts/` | refresh, backfill, snapshot, compute and diagnostic scripts; `BOOTSTRAP.md` runbook |
| `api/tests/` | pytest: `analytics/`, `data/`, `routers/`, `scripts/`, `deploy/` |
| `api/data/cache/` | Parquet cache. Only `liqtide/`, `narrative/` (minus `coingecko_trending.parquet`) and `onchain/` (chain growth) are tracked in git; the rest is local and gitignored |
| `deploy/` | PowerShell launchers and runbook for the home PC (`start-api.ps1`, `start-web.ps1`, `build-web.ps1`, `register-tasks.ps1`, `README.md`) |
| `.github/workflows/` | `ci.yml` plus five nightly snapshot/refresh jobs |
| `process/` | agent harness: context, protocols, plans, `MASTER-PLAN.md` registry, archive index |

## Runtimes and boundaries

| Runtime | Role | Boundary |
|---|---|---|
| Python 3.12, FastAPI, uvicorn (managed by `uv`) | All data fetching, caching and maths | Binds `127.0.0.1` in dev; on the home PC `start-api.ps1` binds the Tailscale IP; CORS is an explicit origin list |
| Next.js 15 App Router, React 19, TypeScript (managed by `pnpm`) | Pages, layout, non-chart UI, formatting | Never computes an indicator or statistic |
| Svelte 5 islands with LayerChart, built by vite (`build:islands`) | Charts only | Mounted into React pages via `island-loader.ts`; no ordinary UI in Svelte |

**Why two runtimes.** Cointegration, regime and statistical work (`statsmodels`, pandas) have no serious JavaScript equivalent; the good charting libraries are browser libraries. The split follows the maths. Charts moved from `lightweight-charts` to LayerChart islands on 01-10-26 (Direction D); the reason for the split did not change. Cost recorded then: island entry chunk 185 kB gzipped vs 54 kB before.

**Key libraries:** pandas, numpy, pandas-ta-classic, pydantic, httpx, statsmodels (Engle-Granger, Johansen, Benjamini-Hochberg), ccxt, duckdb, pyarrow; Tailwind 4 and Skeleton for styling. `arch` is deliberately not installed.

## Data flow

```
providers (ccxt/Hyperliquid, FRED, DefiLlama, LiqTide, Farside, CoinGecko,
           pytrends, Reddit, L2BEAT, growthepie)
   -> adapters (api/data/*_adapter.py: common shape, ok / unavailable / stale status)
   -> cache.py (Parquet files, read with DuckDB; atomic temp-then-rename writes)
   -> analytics (api/analytics/*: indicators, regime, narrative, cointegration, onchain)
   -> routers (api/routers/*, pydantic models in api/models/)
   -> web (web/lib/api clients -> React pages -> Svelte chart islands)
```

- **Writers:** request-time fetches (cache-first), manual scripts in `api/scripts/`, and the scheduled jobs in `.github/workflows/`.
- **Precompute:** pair statistics are computed offline by `compute_pairs.py` and only read by the router.
- **Archives:** sources that keep no history (narrative attention, LiqTide, chain growth) are snapshotted nightly and committed, because a missed day cannot be re-fetched.
- **Deployment:** the user's home PC, reached only over Tailscale; the web app is a built bundle, so any `web/` change needs a rebuild before it shows. Details: operating-instructions.md and `deploy/README.md`.

## Patterns and invariants

1. **One source of numerical truth.** Every number is computed in Python and sent as data. TypeScript formats and renders; two implementations of one calculation is the most likely way to get quietly wrong numbers.
2. **Providers behind adapters.** No route, component or analytics function calls a vendor directly. Swapping a provider is a one-file change.
3. **Free tiers are a constraint.** Fetching is cached and rate-limited in the adapter layer; assume every limit will be hit.
4. **Numbers are never silently wrong.** Insufficient data, failed convergence or a stale cache returns an explicit state the UI shows as such. No NaN, no zero-fill, no silently shortened lookback.
5. **Data, not verdicts.** Analytics return data and data-quality states; they do not return market calls (north-star.md).
6. **Atomic cache writes.** Parquet writes in `cache.py` go through a temp file and `os.replace`. Known exception: `etf_flows_adapter.merge_into_cache`.

**Naming:** kebab-case files in `web/`, PascalCase React components, snake_case in `api/`.

## Deeper docs (on demand)

- north-star.md: product direction, pages, non-goals.
- operating-instructions.md: commands, test tiers RT0-RT4, branch and merge rules.
- `process/context/data-sources/all-data-sources.md`: providers, limits, terms, library choices.
- `process/context/tests/all-tests.md`: test runners and known gaps.
- Feature guides: `process/features/*/_GUIDE.md`.
