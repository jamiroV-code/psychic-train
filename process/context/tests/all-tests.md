---
name: context:all-tests
description: "Test runners, commands, verification order, debugging reference, and known gaps"
keywords: pytest, vitest, playwright, test, e2e, runner, coverage, fixture, debugging, isolated_cache, gate
date: 24-09-26
---

# my_site - All Tests

Last updated: 2026-09-25 (narrative-keyword-keying fix EVL — counts below; the 2026-09-24 counts
were the regime dashboard's own RFC-001..006, a separate closed program)

Attach this file first when the task involves testing, verification, or test debugging.

This is the fast operator guide for the testing surface:

- which runner to use
- what command to start with
- how to quickly debug common failures
- which deeper file to read next

Do not load the whole `process/context/tests/` folder by default. Start here, then drill down.

---

## Status: three runners, all green (backend + frontend + E2E) as of the narrative-keyword-keying fix

**This file previously said "no test surface exists" and was stale from 18-09-26 to 19-09-26.**
Its own Update Trigger ("a test runner is added to either `web/` or `api/`") fired when RFC-001
landed pytest and vitest, and nothing actioned it. Corrected during RFC-005 UPDATE PROCESS.

| Package | Runner | Command | State (25-09-26, narrative-keyword-keying EVL) |
|---|---|---|---|
| `api/` | pytest | `uv run --project api pytest api/ -q` | **381 passed, 3 deselected** (final EVL run — deselected are the opt-in `integration`-marked tests) |
| `api/` (network) | pytest | `uv run --project api pytest api/ -m integration` | opt-in, hits real providers (exchange, Farside) |
| `web/` | vitest | `pnpm --filter web test` | **75 passed, 12 files, 0 failed files** (same EVL run) — `vitest.config.ts` excludes `e2e/**`, so Playwright specs are never collected by vitest |
| `web/` (E2E) | Playwright | `cd web && pnpm test:e2e` | **12/12 passed, run twice (24-09-26, regime dashboard RFC-006)** — `e2e/screener.spec.ts` (6) + `e2e/regime.spec.ts` (6, new). The seeder writes every `/api/regime/components` input (FRED, DefiLlama, Farside + today's `.last_attempt` ok marker, LiqTide raw + daily rows) so the API never reaches a real provider. **Cloud-container note (persists — same fix needed every fresh container):** `@playwright/test` 1.63 wants chromium build 1243 but only `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` is present, so set `PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome` before running (no-op on a machine with a matching browser, e.g. the user's PC after `pnpm exec playwright install chromium`). This container's egress proxy also blocks FRED/DefiLlama/stablecoins.llama.fi (403) — the seeded-fixture E2E run above never needs them, but a real-cache walkthrough (AC-11 in the regime plan) cannot run here at all and must happen on the user's PC |

Live-cache spot check (reads only, no runner): `uv run --project api python api/scripts/check_weekly_anchor.py`
— reports the week anchor of every cached `1w` series. The unit tests run against an isolated
cache and say nothing about the real Parquet files.

`uv` must be invoked as `uv run --project api` — `pyproject.toml` and `.venv` live in `api/`,
not at repo root, while module paths (`api.main:app`) resolve from the root.

**Fresh-worktree frontend install note (found 25-09-26):** `pnpm install` from the repo root does
NOT work in this repo — there is no root-level `package.json`/`pnpm-workspace.yaml` for it to
resolve against. Run `pnpm install --frozen-lockfile` **inside `web/`** instead (i.e. `cd web &&
pnpm install --frozen-lockfile`) before the first `pnpm --filter web test` / `pnpm test:e2e` in a
fresh worktree. `pnpm --filter web ...` commands themselves resolve fine from the repo root once
`web/node_modules` exists — only the initial install needs the `cd web` step.

---

## How This File Works

This is the `all-tests.md` entrypoint for the `tests/` context group. Agents read
`all-context.md` first and get routed here for testing tasks.

## Read This When

- running tests after implementation
- deciding between test runners
- debugging failing tests
- deciding whether a green suite actually proves anything (see Standing Lesson below)

## Standing Lesson: green does not mean verified

The single most expensive recurring failure in this project is a test suite that passes against
something other than the real dependency. Eight instances so far. The first five are recorded in
`momentum-screener_PLAN_17-09-26.md` `## Deviations`; the sixth and seventh in
`weekly-ohlc-anchor_PLAN_19-09-26.md`; the eighth in `playwright-e2e_19-09-26-phase-report.md`:

| # | What passed | What was actually true |
|---|---|---|
| 8 | `import pandas_ta` | real package imports as `pandas_ta_classic` |
| 9 | insufficient-history return shape | real library returned a DataFrame row, not a scalar |
| 12 | component tests | `vitest.config.ts` had no React JSX plugin; 10/10 failed on first real run |
| 13 | `fetch_ohlcv("BTC", ...)` | real ccxt needs `BTC/USDC:USDC`; bare ticker raises `BadSymbol` |
| RFC-005 Dev #1 | watchlist router tests | fixture patched a module constant already bound as a default arg — tests wrote the REAL watchlist file and deleted a live entry |
| ADR-5 | `_derive_weekly_from_daily` (135 green, incl. a `1w` deadlock test) | the `1w` path had NO test of its output values at all — the suite proved it did not hang, never that it was right. Bars were stamped with the week's close, and the newest one with a date in the future |
| ADR-6 | ADR-5's 13 golden-value tests, all green | the tests called `_derive_weekly_from_daily` directly on tz-aware UTC fixtures and never crossed the Parquet/DuckDB boundary. DuckDB converts TIMESTAMPTZ to the SESSION timezone on read, so the live cache came back `Europe/Brussels` and the weekly anchor sat on Brussels midnight — Monday locally, **Sunday 22:00 UTC**. The suite could not have caught it: the conversion happens one layer below where every test lived |
| Playwright E2E | 165 backend tests + 7 vitest suites, all green | none of them ever executed the real frontend/backend boundary at all — vitest injects `fetchBoard`/`fetchScalp` fakes, pytest never runs FastAPI. The actual defect (`seed_e2e_cache.py` wrote the watchlist fixture as a bare JSON array; `watchlist.py` expects `{"coins": [...]}`, raising `AttributeError` on every board request) was in code no existing suite touched at all — a new fixture script, unchecked against a pre-existing reader's format |

Four of the eight came from RFC-001's sandbox shims (`pandas_ta`, `ccxt`, `duckdb`/`pyarrow`).
The fifth was a fixture that never isolated anything. The sixth had real coverage of its
*liveness* and none of its *output*. The seventh is the sharpest: coverage that was genuine,
thorough and hand-computed, sitting one layer above the boundary where the data actually changed.
The eighth wasn't a wrong test at all — it was the total absence of one, at the one boundary
(frontend↔backend) every other layer's coverage structurally cannot reach.
The DuckDB/PyArrow shim is the only one that turned out to be faithful — and note that the
seventh defect is a DuckDB behaviour the shim had hidden all along.

Practical rules that follow:

1. **Pin the real contract, not the mock's.** Every adapter should have at least one opt-in
   network test asserting the real library's shape. `test_board_integration.py::test_board_against_real_exchange`
   is the template. Run after any dependency upgrade.
2. **A fixture that patches a module constant proves nothing if the constant is a default
   argument.** Python binds defaults once, at import. Resolve inside the function instead.
   Worth grepping `api/` for `= DEFAULT_` in signatures.
3. **Tests that touch real user files are a data-loss bug, not a hygiene issue.** Deviation #1
   deleted a coin from the user's live watchlist. As of 19-09-26 `api/tests/conftest.py`
   provides an opt-in `isolated_cache` fixture; any test that drives `fetch_ohlcv` must request
   it, or it writes over the user's real Parquet series. It is **not** autouse — a test that
   forgets it fails silently by succeeding.
4. **"Does it crash?" is not "is it right?"** Ask what a gate would still pass with if the
   arithmetic were wrong. ADR-5's bug survived a suite that already exercised the `1w` path
   under concurrency. Any function producing numbers a human reads off a chart needs at least
   one hand-computed golden value, not just a smoke test.
5. **Test at the boundary the data actually crosses.** A function tested on hand-built inputs is
   tested on inputs that never touched the store. ADR-6's defect lived entirely in the Parquet ->
   DuckDB round trip, so 13 correct tests of the function above it were all green while the
   product was wrong. If a value is written and read back before it is used, at least one test
   must write it and read it back. `test_cache_timezone.py` is the template.
6. **When two checks disagree, believe the one asserting the external contract.**
   `check_weekly_anchor.py` (UTC) said `Sun`; a diagnostic written afterwards read the *local*
   weekday, said `Mon`, and printed "Nothing wrong" over a still-broken cache. The external
   contract is that an exchange weekly opens Monday 00:00 UTC — the check that encoded it was
   right, and the newer, more elaborate tool was wrong.
7. **A fixture writer must be checked against its reader's actual parsing contract, not against
   what looks right.** `seed_e2e_cache.py` wrote `json.dumps(WATCHLIST)` — a plausible-looking
   watchlist file — against `watchlist.py::_load_raw`, which expects `{"coins": [...]}` and calls
   `.setdefault` on whatever it loads. Nothing that runs typechecks a `SCREENER_*_PATH` hand-off at
   write time. Before writing fixture data for an *existing* reader, read that reader's own format
   (or its `*.example.json`) first, or better, call the reader's own writer function instead of
   hand-rolling the shape.
8. **A green suite that never crosses a boundary is not evidence about that boundary.** 165 backend
   tests and 7 frontend suites were green while `/api/screener/board` 500'd on every request — none
   of them executed FastAPI and the real browser client in the same process. The absence of a test
   at a boundary is itself a finding, not a neutral default; RFC-005/ADR-5/ADR-6 all had *some*
   coverage that was merely misplaced, this one had none at all.

## Default Verification Order

1. run the narrowest existing automated test
2. unit/integration before browser tests
3. end-to-end only when the real UI is the thing being verified
4. for anything that crosses a library boundary, run the opt-in integration gate too

## Debugging Quick Reference

| Symptom | Likely cause |
|---|---|
| `ReferenceError: React is not defined` in vitest | `@vitejs/plugin-react` missing from `vitest.config.ts` (Deviation #12) |
| `ModuleNotFoundError: pandas_ta` | import name is `pandas_ta_classic` (Deviation #8) |
| Endpoint returns 200 with `available: false` everywhere | check `reason` — `bad-symbol` means a config error, `source-unavailable` means the provider |
| Screener UI shows "Symbol configuration issue" / "Data source unavailable" / "Not enough history…" on a chart or relative-performance note | this is the frontend now rendering `ChartSeries`/`RelativePerformanceSeries.reason` directly (RFC-006 `reason-value-rendering` slice, `web/lib/format-unavailable-reason.ts`) — read the on-screen text itself to know which of the three it is; every such element also carries a `data-reason` attribute with the raw value for automated checks |
| Watchlist tests fail against real coins | fixture isolation; should be fixed as of 19-09-26 |
| `uv` can't find the project | use `--project api` |
| Weekly candle plotted ~6 days late, or a weekly bar dated in the future | pre-ADR-5 `1w.parquet` still cached; restart the API and re-request the board, then `uv run --project api python api/scripts/check_weekly_anchor.py` |
| Cached timestamps come back with a local tz (e.g. `datetime64[us, Europe/Brussels]`), or daily bars read at 01:00/02:00 instead of 00:00 | a DuckDB read bypassing `cache._connect()`. Every read in `cache.py` must use it — a bare `duckdb.connect()` converts TIMESTAMPTZ to the session timezone (ADR-6) |
| A cached series looks right locally but wrong in UTC | evaluate weekdays with `pd.to_datetime(..., utc=True)`. Monday 00:00 local is Sunday 22:00/23:00 UTC |
| Playwright browser specs show `Failed to fetch` / a generic network error, never an HTTP status | the API 500'd and Starlette's CORS middleware doesn't attach headers to an unhandled-exception response — the browser can't see the status. Reproduce with Playwright's `request` fixture directly (bypasses the browser and CORS) to get the real status, or curl the endpoint by hand |
| E2E board request 500s regardless of `timeframe` or symbol | check `SCREENER_WATCHLIST_PATH`'s actual content against `watchlist.py::_load_raw`'s expected shape (`{"coins": [...]}`, not a bare array) — `read_watchlist()` is the first line of `build_screener_board()`, so a bad watchlist file fails every board request identically |
| ~~`pnpm test` (vitest) reports `e2e/screener.spec.ts` as a failed test file~~ (fixed 24-09-26: `e2e/**` excluded) — historically, even though `pnpm test:e2e` (Playwright) passes it | `vitest.config.ts` does not exclude the `e2e/` directory from vitest's own test collection, so vitest tries to execute a Playwright-fixture-style spec (`test(name, async ({ page }) => ...)`) that only Playwright's runner can execute — fails at the first `page.goto(...)` call, before any assertion. Not a regression; see Known Gaps and `vitest-config-e2e-exclude_19-09-26.md` |
| A Playwright board spec times out or fails only on the very first request against a freshly-started backend, and passes on every subsequent run/request in the same process | Cold-start latency, not a real failure: `ccxt_adapter._exchange()` calls `ex.load_markets()` lazily on first use (~12.5s, `api/data/ccxt_adapter.py:117`) with no startup pre-warm, and `build_coin_panel`/`build_screener_board` fetch every (coin, timeframe) pair fully serially (`api/analytics/screener_board.py:134-146,190-193`) — up to 16 sequential live OHLCV calls (~8s) on a cold cache. ~23.7s cold vs. ~3.3-3.6s warm; Playwright's default 5s `expect` timeout only trips on the very first request against a fresh process. Not test-order-stable — whichever spec runs first pays the cost. See `board-endpoint-cold-start-latency_20-09-26.md` |

## Known Gaps

- ~~**`1w` weekly-close correctness is unverified.**~~ **Closed 19-09-26** by ADR-5
  (`test_weekly_derivation.py`, 13 tests) **and ADR-6** (`test_cache_timezone.py`, 7 tests —
  the UTC pin at the cache read boundary). ADR-5 alone was not enough: the suite was green while
  the live weekly series was still Sunday-anchored in UTC. Two residuals remain: the week-anchor
  convention is asserted from documented exchange behaviour rather than measured against a
  native-weekly source (egress policy blocked the check), and `isolated_cache` is opt-in rather
  than autouse. See
  `process/general-plans/active/momentum-screener_17-09-26/weekly-ohlc-anchor_PLAN_19-09-26.md`.
- **Other cached series have not been re-checked since the UTC pin.** ADR-6 moved timestamps for
  liquidity, liqtide, narrative and legs reads too, not just OHLCV. The suite is green, but no
  test asserts the tz contract for those readers specifically.
- ~~**No E2E/browser suite.**~~ **Closed 19-09-26.** `web/e2e/screener.spec.ts`, 6 specs, real API +
  real browser + seeded fixture cache. First run found a real defect the rest of the suite
  structurally could not reach (Standing Lesson #8); second run, 6/6 green. See
  `process/general-plans/active/momentum-screener_17-09-26/playwright-e2e_19-09-26-phase-report.md`.
- **Provider adapter layer** beyond ccxt (liqtide, fred, pytrends, reddit, coingecko, defillama)
  has mocked-failure contract tests but no real-contract pins.
- **`api/analytics/` golden values.** Indicator and cointegration output can be wrong by a factor
  of two and still look plausible on a chart. Still the highest-value first target.
- ~~**`vitest.config.ts` does not exclude `e2e/` from vitest's collection**~~ **Closed 24-09-26** (regime RFC-006; note moved to `general-plans/completed/`). Was: — `web/e2e/screener.spec.ts`
  is picked up and fails at the vitest layer (unrelated to Playwright, which passes it correctly).
  One-line fix, not yet applied. See backlog note `vitest-config-e2e-exclude_19-09-26.md`.
- **Screener board endpoint pays a ~23.7s cold-start cost on the first request after a process
  start** — an uncached, lazy `ccxt_adapter._exchange()` `load_markets()` call (~12.5s, no startup
  pre-warm) plus fully serial per-(coin, timeframe) OHLCV fetching (~8s, up to 16 sequential live
  calls, no concurrency anywhere in `screener_board.py`/`ccxt_adapter.py`) — causes exactly one
  Playwright spec to fail whenever it happens to be the first real request in a run; not a
  correctness bug, not yet fixed. A secondary, currently-dormant risk was flagged alongside it:
  neither the pytrends nor the Reddit narrative adapter checks cache freshness before attempting a
  live call, unlike the ccxt adapter — costs ~0s today (missing lib / unset creds) but could add real
  latency once those are configured for real. See backlog note
  `board-endpoint-cold-start-latency_20-09-26.md`.
- **The "SANDBOX NOTE — written but never executed" disclosures at the top of every file in
  `web/components/screener/__tests__/` are now confirmed stale by at least one data point** —
  `vitest.config.ts`'s own comment references a real `pnpm test` run on 18-09-26 (the one that
  surfaced and fixed the `ReferenceError: React is not defined` issue, already recorded as Standing
  Lesson Deviation #12 in this same file) — and now a second real run on 19-09-26 (this plan's EVL).
  These notes need a reconciliation pass to say what has and hasn't actually run, file by file,
  rather than a single boilerplate disclaimer copy-pasted everywhere. See backlog note
  `sandbox-note-reconciliation_19-09-26.md`.

## Update Triggers

Update this file when:

- a test runner is added to either `web/` or `api/`
- the passing-test counts above drift
- a class of failure recurs often enough to be worth a debugging note
- a new real-contract integration gate is added
- a defect is found that the existing suite structurally could not have caught (add it to the
  Standing Lesson table with *why* the coverage missed it, not just what broke)
