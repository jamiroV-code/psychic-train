# Playwright E2E — SIMPLE Plan

**Date**: 19-09-26
**Slug**: `playwright-e2e`
**Parent program**: `momentum-screener_17-09-26` — inner-loop RFC, SPEC governed by `momentum-screener_SPEC_17-09-26.md`
**Phases run**: RESEARCH → INNOVATE → PLAN → EXECUTE → DEBUG → EVL → UPDATE PROCESS
**Status**: ✅ VERIFIED — all 6 specs pass (`pnpm test:e2e`), reported directly by the user

---

## EVL — what actually happened

EXECUTE landed the three additive touchpoints (`cache.py`/`watchlist.py`/`main.py` env overrides,
the `ccxt_adapter.fetch_ohlcv` reorder) plus the new seed script, config and specs, all exactly as
scoped. First run: **5 of 6 specs failed.**

All five failures shared one root cause, and it was not in any file this plan's Touchpoints table
named. `seed_e2e_cache.py` wrote the watchlist fixture as a bare JSON array
(`json.dumps(WATCHLIST)` → `["BTC","ETH","THIN"]`). `watchlist.py::_load_raw` — unmodified,
pre-existing code — expects `{"coins": [...]}`: it does `json.load(f)` then
`data.setdefault("coins", [])`. `json.load` on a bare array returns a `list`, and `list` has no
`.setdefault` — `AttributeError`, raised on `read_watchlist()`'s first line, which is
`build_screener_board()`'s first line too. Every board request 500'd identically regardless of
`timeframe` or symbol, which is exactly the signature all five failures showed (spec 3's direct
`request` fixture surfaced the 500 itself; specs 1/2/4/6 saw it only as a browser-level "Failed to
fetch", because Starlette's CORS middleware does not attach headers to an unhandled-exception
response, so a CORS-header-less 500 throws as a generic network error in `fetch()`).

Found by reading `build_coin_panel`'s and `build_screener_board`'s full call graph outward from the
router — every adapter it reaches (`fred_adapter`, `defillama_adapter`, `pytrends_adapter`,
`reddit_adapter`, `coingecko_adapter`, `liqtide_adapter`) — and confirming each one degrades to a
typed `unavailable`/`stale` result rather than raising, before reaching `watchlist.py` and finding
the one place a raw exception could actually surface. No traceback was used; this was static
tracing against the two file shapes (`watchlist.example.json` vs. what the seed script wrote), which
disagreed outright once placed side by side.

Fixed in `seed_e2e_cache.py`: `json.dumps(WATCHLIST)` → `json.dumps({"coins": WATCHLIST})`. One
line. Re-run: **6 of 6 pass**, confirmed by the user directly (`pnpm test:e2e`).

## Verification

```
cd web
pnpm install
pnpm exec playwright install chromium
pnpm test:e2e
```

Ran by the user (session constraint below, unchanged): **6 passed**. Plus unchanged:
`uv run --project api pytest api/ -q` — 165 passed, 1 deselected (last reported before this EXECUTE
cycle's own additions; not yet re-run against the final state, see Next in the phase report).

---

## TL;DR

Stand up Playwright against a **real** stack — real browser, real `fetch`, real CORS, real FastAPI,
real DuckDB — with the data layer seeded from fixture Parquet so runs are deterministic and offline.
Three small source changes are needed to make the API pointable at a fixture cache without touching
the network. The suite's job is to cover the boundaries the existing 155 backend + 7 frontend tests
structurally cannot.

---

## Why this, and why now

Two defects landed today (ADR-5, ADR-6) that a green suite could not have caught, both for the same
reason: the tests sat one layer above the boundary where the data actually changed. The frontend has
the same shape, worse:

`ScreenerBoard` takes `fetchBoard`/`fetchScalp` as **injectable props**, and all seven vitest suites
pass fakes. `web/lib/api/screener.ts` — the real client, the real URL construction, the real JSON
decode — has **never been executed by a test**. Neither has CORS, the Next.js runtime, or the
response shape contract between FastAPI and TypeScript.

This is not a request for more UI coverage. It is a request for the first test that crosses the
frontend/backend boundary at all.

## Research findings

**Instrumentation already exists.** Every hook an E2E needs is in the components:
`screener-board`, `screener-board-grid`, `timeframe-toggle`, `timeframe-button-{tf}`,
`coin-panel-{symbol}`, `momentum-state`, `trend-direction`, `gain-chip-{tf}`, `gain-readout-row`,
`chart-unavailable`, `board-error`, `open-drilldown-{symbol}`, `active-benchmark`. No test-only
markup needs adding.

**CORS is origin-exact.** `api/main.py` allows `http://localhost:3000` only; the client targets
`http://127.0.0.1:8000`. A Playwright `baseURL` of `http://127.0.0.1:3000` fails every request on
CORS, for reasons unrelated to the assertion. Pinned deliberately in config, with a comment.

**`getJson` has four call sites, not one.** `ScreenerBoard` catches into `board-error`;
`LegTimelineBanner`, `NarrativeStrip` and `RelativePerformanceChart` each call `getJson` with no
catch and no timeout. That is RFC-006's scope, not this plan's — but the E2E should *observe* the
current behaviour so RFC-006 has a before/after, not silently paper over it.

**The workspace root is `web/`, not the repo root.** `web/pnpm-workspace.yaml` exists; there is no
root `package.json`. So `all-tests.md`'s documented `pnpm --filter web test` only works from inside
`web/`. Verify, don't assume — this is the third documented-but-never-run command found today.

**`_exchange()` is constructed before the freshness check.** In `fetch_ohlcv`, the
`if not injected: exchange = _exchange()` block runs first, and `_cache_is_fresh` is consulted much
later. A fully warm cache therefore still pays a `load_markets()` round trip. This blocks an offline
E2E, and it is a real performance defect independent of testing.

## Design decision (INNOVATE)

**Chosen: real API against a seeded fixture cache.** Both servers run for real; only the exchange is
absent. Deterministic, offline, exact assertions, and every layer between the browser and Parquet is
the production one.

**Rejected: mock at the browser boundary** (`page.route` returning canned JSON). Fastest and most
stable, and it reproduces exactly the mistake this plan exists to correct — it would test the UI
against a fixture of what we *believe* the API returns, adding a browser but not a boundary.

**Rejected as the default: live exchange.** Proves the real contract but is slow (RFC-005 measured a
32s cold board), flaky, and assertions cannot be exact against moving data. Belongs behind an opt-in
marker like the backend's existing `-m integration`, and is explicitly Future Work here.

## Touchpoints

| File | Change |
|---|---|
| `api/data/cache.py` | `CACHE_ROOT` reads `SCREENER_CACHE_ROOT` env var, falling back to today's path. Resolved at **call time**, not import — the RFC-005 watchlist lesson |
| `api/data/watchlist.py` | same treatment for `SCREENER_WATCHLIST_PATH`, so the E2E controls the symbol set |
| `api/data/ccxt_adapter.py` | move the cache-fresh early return **above** exchange construction, so a warm cache needs no network. Also the fix for the pointless `load_markets()` on every warm call |
| `api/scripts/seed_e2e_cache.py` | **new** — writes deterministic fixture OHLCV for a fixed symbol set into `SCREENER_CACHE_ROOT`, including one deliberately thin-history symbol |
| `web/playwright.config.ts` | **new** — `webServer` array starting `next dev` and `uvicorn`; `baseURL` pinned to `http://localhost:3000` |
| `web/e2e/*.spec.ts` | **new** — the specs below |
| `web/package.json` | add `@playwright/test`; `test:e2e` script |
| `.gitignore` | `web/test-results/`, `web/playwright-report/`, the E2E cache dir |
| `process/context/tests/all-tests.md` | third runner row, commands, Known Gaps update |

**Blast radius**: the three API changes are all additive fallbacks — absent the env vars, behaviour
is byte-identical to today. The `ccxt_adapter` reorder is the only real behaviour change, and it
strictly removes a network call that could not have affected the result.

## What the specs must prove

Written as gates, each naming what it would catch that current tests cannot:

1. **The board renders from the real API.** Load `/screener`, assert one `coin-panel-{symbol}` per
   seeded symbol with exact values from the fixture. *Catches: any break in the real client, URL
   construction, CORS, or the FastAPI↔TypeScript response shape — none of which any test touches.*
2. **The timeframe toggle drives a real refetch.** Click `timeframe-button-1w`, assert the board
   re-renders with the 1w fixture's distinct values. *Catches: a toggle that changes local state
   without issuing a request — invisible to a vitest suite injecting a fake.*
3. **Weekly bars are Monday-anchored end to end.** With daily fixtures at 00:00 UTC, assert the 1w
   view's values match the hand-computed weekly aggregate. *Catches ADR-5 and ADR-6 from the
   browser, on the machine's own timezone — the assertion neither the 13 nor the 13 could make.*
4. **Thin history degrades honestly.** The deliberately-short symbol shows `chart-unavailable` and
   `N/A` chips, never `0%`. *Catches a regression of AC-20, which is currently proven only against
   an injected fixture.*
5. **A dead API degrades honestly.** Stop the API (or route it to failure), assert `board-error`
   renders and the page does not white-screen. *Catches the uncaught-rejection overlay — and gives
   RFC-006 its before/after.*
6. **Drill-down opens on demand.** Click `open-drilldown-{symbol}`, assert the scalp view fetches
   and renders. *Catches AC-7's on-demand contract against a real request.*

**Session constraint, throughout**: this session had no shell on the user's machine (only the
device-file bridge — stage/edit/commit, no execution) and the cloud sandbox has npm and pypi
blocked. Every gate here was written unrun and executed by the user; the EVL section above is
that execution's actual result, not authorship's claim of one.

## Named risks

1. **`pnpm exec playwright install chromium` needs network.** If the corporate proxy blocks the
   Playwright CDN, this plan stops at step one. Worth testing before anything else is written.
2. **Two servers under `webServer` means two failure modes.** A port already in use (a dev server or
   the uvicorn instance already running from today) will look like a test failure. Config sets
   `reuseExistingServer: false` in CI and documents the local case.
3. **The seeded cache must not be the real one.** `SCREENER_CACHE_ROOT` pointing at the default by
   accident would have the E2E overwrite live market data. The seed script refuses to run unless the
   env var is set and differs from the default — an explicit guard, given this is the third
   live-data hazard in two days.
4. **Fixture drift.** Golden values live in both the seed script and the specs. **Materialized, but
   not as predicted**: the drift that actually broke the suite wasn't a golden *value* going stale
   between the two files, it was the watchlist fixture's *shape* disagreeing with its reader's
   parsing contract — a risk this list didn't name because `.fixture-manifest.json` (the mechanism
   built to prevent value drift) was itself read correctly by the specs; the untyped hand-off was
   the raw `SCREENER_WATCHLIST_PATH` file, which nothing cross-checked against `watchlist.py`'s own
   format. Residual, carried to the phase report.

## Resolved at EXECUTE

Spec 5 (dead API) was written asserting today's behaviour, as this section leaned toward, and
passed in the same run as the other five. Not amended for RFC-006 — that RFC is still queued.
