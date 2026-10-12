---
name: plan:screener-batch5-equities
description: "S9 equities page at full parity with the crypto screener: equities API (cache-only board, chart, spaghetti, add/remove with a 30 cap), layout section 'equities', /equities page by parameterised reuse, e2e proof, market-hours-aware refresh tick and freshness strip. Five slices S9A-S9E, synthetic fixtures only, LSE live shape re-confirmed by the user's PC probe"
date: 12-10-26
feature: general-plans
---

# Screener Batch 5: Equities Page at Parity (S9A-S9E)

Date: 12-10-26
Status: VALIDATED (12-10-26, main `881a2fd`, PVL cycle 3); no envelope or worker before the user's "ENTER EXECUTE MODE". Verified baselines (counted 12-10-26): pytest 1018 collected = 1016 passed, 2 skipped, 5 deselected; vitest 400 in 50 files; `playwright test --list` 79 in 9 files (screener 10, layout 7, live-refresh 4, contrast 7, brussels-time 3, narrative 17, onchain 16, pairs 9, regime 6).
Complexity: COMPLEX (five sequential slices; new public API surface, a layout section, shared board components parameterised, a background thread)

**TL;DR:** The equities page gets every crypto-screener feature except intraday and reference lines: small charts with linked zoom, Brussels time, RSI, groups and layout edits, spaghetti, drill-down, Add button, private-use note, no verdicts. Reuse is by parameter (a `ScreenerVariant` context on the web, a section registry in `layout.py`), not by copying. Reads never fetch: the board is cache-only and a market-hours refresh job fills the cache after each US close. Estimate 21.5-34.0 USD [estimate] for all five slices against 30.6 USD left of the 100 USD ceiling; recommended cut is A-D (17.0-27.0), E only if the running total is at most 93.0 USD.

Sources: realignment SPEC `personal-tracker-realignment_SPEC_02-10-26.md` (US-9, outcome 11, outcome 18 line 89, AC-15 lines 173-174, AC-26 line 200, D9-D11 lines 308-310); research report `s9-research.md` (claims re-checked in code, cites below); `process/context/tests/all-tests.md`; batch 3 plan (shape and gate conventions); backlog `lse-live-shape-verification_NOTE_03-10-26.md`; real code at `881a2fd`. Router: `process/context/all-context.md`.

Context Envelope: general-plans | PLAN | S9 equities | claude/pensive-albattani-ou0cgv | /home/user/psychic-train | tests | api/, web/ | this file | pytest then vitest then playwright | contract pending.

## Overview

Goal: the user adds US tickers on `/equities`, sees them in groups with price, % change and RSI, zooms all small charts together, opens a drill-down, sees a spaghetti chart, and the page tells in Brussels time when the data is from and when it is next refreshed. Data is LSE daily and weekly bars only (D9), private use (D10, D11), never redistributed.

Verified facts (cites at `881a2fd`): no equities router, board, layout section or page exists (`api/main.py:91-98`); `fetch_equity_ohlcv` fetches through on a 6 h TTL (`lse_adapter.py:320-362`), so a board read could block on 30 serial GETs (web timeout 10 s, `web/lib/api/screener.ts:10`); `layout.py:35-37,168,251,305` hard-codes `SECTIONS=("crypto",)`, BTC/HYPE and the crypto watchlist; `equities_store.py` has no cap and `test_equities_store.py:50` asserts 45 tickers are accepted; the crypto stale rule (`freshness.py:81-83`) would flag every weekend; `ScreenerBoard` takes injectable fetchers (`ScreenerBoard.tsx:36-49`) but `CoinPanel.tsx:104`, `DrillDownView.tsx:68`, `ScreenerBoard.tsx:386`, `AddCoinForm.tsx:104` hard-code the five crypto timeframes and `MAX_COINS`; `ChartFreshness` prints a clock time (a UTC-midnight bar reads 02:00 CEST); `lib/api/layout.ts:8` hard-codes `/api/layout/crypto`; `LiveProvider` already accepts `fetchStatus`; `RefreshStatus` is key-checked against `status()` (`test_refresh_router.py:162`), so it is not edited.

Non-goals: intraday timeframes (D9 stays), reference lines on spaghetti, verdicts/flags/badges, scheduled task S10, group sort, any change to `lse_adapter.py` fetch logic or constants, to `ccxt_adapter.py`, `freshness.py`, `refresh_worker.py`, `cache.py`, `deploy/**`, `.github/**`, `.claude/**`.

SPEC lines this plan amends (text applied by the planner at UPDATE PROCESS; this plan edits no SPEC): outcome 18 (line 89) last sentence and AC-26 (line 200) last sentence: "The 30 cap applies to the crypto screener and, counted separately, to the equities page (API-enforced 409)." AC-15 (lines 173-174) gains parity proof (groups, spaghetti, drill-down, linked zoom, live polling) and the 30 cap. D9 (line 308) is kept: 1d/1w only (user decision 1 lists no intraday; open choice Q1). D10 and D11 unchanged.

## Decisions locked (user, binding)

1. Full parity with crypto except reference lines and verdicts: small charts with linked zoom, Brussels time, live polling plus freshness strip, RSI, groups and layout edits (add/remove, rename/move/reorder groups), spaghetti, drill-down, Add button, private-use note; the user draws conclusions.
2. Equities cap 30, API-enforced (409), counted apart from the crypto 30.
3. Live = a market-hours-aware server refresh job tied to the US close plus a page that re-reads every 60 s; the strip shows the last bar date and the next expected refresh (Brussels time) instead of the 15-minute proof; weekends and holidays are never overdue (rule in S9E, tested).
4. Reuse by parameter; crypto tests stay byte-identical; the only existing test files edited are in the table below.
5. Spaghetti has no reference lines (`references: []`).
6. Probe first: the user runs `process/general-plans/active/screener-batch1_03-10-26/s3-probe/lse_probe.py` (README beside it) and reports the live shape (P-S9-1). Slices A-E are built on synthetic fixtures and do not depend on the shape; the probe record below re-confirms the assumptions.
7. Synthetic fixtures only (public repo, LSE forbids redistribution); the key is read from `LSE_API_KEY` only, never logged, echoed or committed; `test_committed_lse_fixtures_are_synthetic_only` stays green.
8. Budget: ceiling 100 USD, about 69.4 spent, 15 USD cap per slice, workers measured by the planner after idle.

Design decisions (planner, to confirm at VALIDATE): D-1 reads are cache-only: the board, chart and spaghetti never call the network; fills come from add-triggered fetch, `POST /api/equities/refresh` and the S9E tick. D-2 the market calendar is pure code with a hand-rolled US Eastern rule (2nd Sunday March to 1st Sunday November), no `zoneinfo` or new dependency. D-3 gain chips keep the crypto meaning (newest candle, open to latest); only 1d and 1w exist. D-4 equities `stale` and `is_partial` come from the calendar, not `freshness.py`. D-5 the equities worker and status are separate from the crypto worker (own file, own endpoint, same JSON keys) so the crypto worker is untouched; `SCREENER_REFRESH_WORKER=0` turns both off. D-6 web reuse is one React context, `ScreenerVariant` (default crypto, so no provider means today's behaviour), plus client factories with the old exports kept.

## Gate conventions (all slices)

1. Every pytest gate runs with `UV_FROZEN=1 uv run --project api pytest ... -q`. Full run: `UV_FROZEN=1 uv run --project api pytest api/ -q`.
2. Web gates run inside `web/`: `pnpm exec vitest run <paths>`, `pnpm exec tsc --noEmit --incremental false`, `pnpm build:islands`. Log each gate run (SHA, UTC time) in report heading 6.
3. Seeded e2e (CI does NOT run Playwright), from `web/`: `SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e <specs>` (no `--`). Required on the head SHA before any merge of S9C, S9D, S9E; NOT-RUN stops at `needs_input`.
4. Red-first: write the slice's new tests as failing stubs, run the first gate on the untouched base, record the red count in heading 6, then write real tests. New tests are plain functions (no `it.each`, no `parametrize`).
5. Hidden-break rule: an existing test file may be edited only as listed in the table below; any other failing existing test stops the worker at `needs_input`. Max 2 fix cycles per gate; the same failure twice stops.
6. A count that differs from the slice arithmetic stops the worker at `needs_input`. Workers branch from `main` as `claude/<task-id>-<slice>-<slug>`; a diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/`, `uv.lock`, `api/pyproject.toml` stops at `review`.
7. Personal data: new tests redirect `SCREENER_EQUITIES_PATH`, `SCREENER_LAYOUT_PATH`/`DEFAULT_WATCHLIST_PATH` and the cache root (`isolated_cache`) to `tmp_path` and `delenv("LSE_API_KEY")` in a module autouse fixture (a test that reaches refresh code injects its fetch or transport; none may reach the network or a real key). REAL-DATA after the gates: `find api/data -maxdepth 4 -newer /tmp/s9-stamp \( -name equities.json -o -name layout.json -o -name watchlist.json -o -path '*cache/equities*' \)` prints nothing (`touch /tmp/s9-stamp` first).
8. SECRET: command `S-secret` prints nothing; tests assert the key never appears in logs (`caplog`), status JSON or errors.
9. Gate traps: new files avoid every token of `api/tests/analytics/test_no_verdict_symbols.py::TOKENS`; no new testid starts with `coin-panel-`; no new container uses `role="group"`; no new heading contains "Screener"; UI copy avoids Momentum, Trend, Benchmark, Confidence, Narrative; no verdict words, flags or badges; the word UTC never appears on the page or in added source lines (say Brussels time); no browser storage.
10. `git diff --check origin/main...HEAD` exits 0; plan, report and envelope files are ASCII. Every scan command (section "Scope and scan commands") reads `git diff origin/main...HEAD`, so it runs AFTER the commit. Known-Gap is a residual (backlog stub, gate stays CONDITIONAL), never a PASS. Probes (P-*) are the user's and never claimed by a worker.
11. Envelope text (every slice, verbatim): "After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR." Spend cap 15 USD per slice; stop and ask above it.

### Existing test files that may be edited (complete list; nothing else)

| Slice | File | Edit | Count effect |
|---|---|---|---|
| S9A | `api/tests/data/test_equities_store.py` | replace `test_more_than_thirty_accepted` (line 50) by a 31st-refused test; add 2 tests (a 31-ticker file is kept, a NEW ticker is refused, an existing one re-adds; at 30 a new ticker is refused, after a remove it is accepted) | +2 net |
| S9B | `api/tests/routers/test_layout.py` | line 177: `layout_store.SECTIONS == ("crypto", "equities")` | 0 |
| S9D | `web/e2e/contrast.spec.ts` | add the `/equities` route to its route list | +1 e2e |

No vitest file is edited. Web slices add tests in new files only.

## Probe record (P-S9-1, user PC; the user fills the last column and reports before S9E merges)

| Assumption (today) | Where it bites | Re-confirmed by probe | Probe result |
|---|---|---|---|
| base URL, path, params (`lse_adapter.py:40-42`) | live fetch only; not edited here | yes | ____ |
| auth `Authorization: Bearer <key>` | live fetch only | yes | ____ |
| response wrapper (list or under data/candles/rows/results) | `parse_candles` | yes | ____ |
| bar date = UTC date of `timestamp` | calendar `last_bar_date`, stale and partial rules | yes | ____ |
| today's bar absent or partial before the close | `bar_is_partial`, `BAR_DUE_AFTER_MINUTES` (60) | yes | ____ |
| day's bar final at close + 30 min | `REFRESH_DELAY_MINUTES` (30) in S9E | yes | ____ |
| `1w` served (adapter derives weekly anyway) | none | no impact | ____ |

Independence: S9A-S9D never read the live shape. S9E uses two named constants whose defaults are estimates; a blank record keeps AC-S9E-1 CONDITIONAL on those constants, not blocked. A contradicting probe becomes a follow-up fix task for `lse_adapter.py`; no slice is blocked by it.

## S9A: equities API, cache-only board, calendar, minimal refresh (RT3)

Depends: none. Live-shape independent. Owned (new): `api/data/equities_calendar.py`, `api/data/equities_refresh.py`, `api/analytics/equities_board.py`, `api/routers/equities.py`, `api/tests/equities_fixtures.py`, tests `api/tests/data/{test_equities_calendar,test_lse_cached_read,test_equities_refresh}.py`, `api/tests/analytics/test_equities_board.py`, `api/tests/routers/test_equities_router.py`. Owned (edit): `api/main.py` (one import, one `include_router`), `api/data/equities_store.py`, `api/data/lse_adapter.py` (ADD two functions, no existing line changes), `api/tests/data/test_equities_store.py` (table). Forbidden: everything else, notably `api/models/*`, `layout.py`, `refresh_worker.py`, `ccxt_adapter.py`, `freshness.py`, `cache.py`.

Design:
- `equities_store`: `MAX_TICKERS = 30`, `CAP_MESSAGE = "Equities list is full: 30 tickers maximum. Remove a ticker to add another."`, `TickerLimitError`; `add_ticker` raises for a NEW ticker at 30 or more, idempotent otherwise; an over-cap file is kept (as crypto D8); add and remove hold one module lock (as `watchlist.py`), so concurrent adds cannot pass the cap or lose a ticker (a router test adds 35 from threads: exactly 30 stored).
- `lse_adapter` gains two functions. `read_cached_equity(symbol, timeframe, now=None) -> tuple[EquityOhlcvResult, Timestamp | None]`: validates ticker and timeframe like `fetch_equity_ohlcv`, reads the parquet and sidecar `fetched_at`, never touches the network or the key; no file gives `unavailable/no-data`; newest bar older than `STALE_AFTER` gives `stale`. `refresh_equity(symbol, transport=None, now=None) -> EquityOhlcvResult`: `fetch_equity_ohlcv` minus its 6 h fresh-cache branch (key check, one GET, writes 1d and 1w, closed reasons, never raises); without it a tick or manual refresh within 6 h of the last fetch returns the cache (`_is_fresh`).
- `equities_calendar` (pure, UTC): `session_close_utc(d)` = 16:00 US Eastern (EDT 20:00Z, EST 21:00Z); `BAR_DUE_AFTER_MINUTES = 60`; `last_due_session(now)` = newest NYSE session whose close + 60 min <= now (uses `lse_adapter.is_nyse_session`); `bar_is_stale(last_bar_date, now)` = last bar before `last_due_session`, None is not stale; `bar_is_partial(last_bar_date, now)` = that session is not yet due; for `1w` the bar date is the newest DAILY bar's date (as crypto B5) and a weekly bar is partial while any session of its week is not yet due; `REFRESH_DELAY_MINUTES = 30`; `next_refresh_at(now)` = first session close + 30 min strictly after now (skips weekends and holidays). Early closes and special closures are not modelled (residual AC-S9-r2).
- `equities_board`: `build_board(timeframe, now)`, `build_chart_view(ticker, timeframe)`, `build_spaghetti(timeframe)`. Panels reuse `ChartSeries`/`CoinPanel`/`RSI` models and `sma`, `rsi`; chips for 1d and 1w only, built here: 1d from the newest daily bar, 1w from the newest derived weekly bar (open of the week's first session, so a Monday holiday does not blank it; `compute_gain_chip` is not used for 1w, it answers N/A when the Monday bar is missing); `stale` and `is_partial` come from the calendar; failure reasons map onto the closed `UnavailableReason` (bad_symbol -> bad-symbol; no file, no key or any other failure -> source-unavailable; under 60 bars -> insufficient-history), no model change; `server_time` from the injectable clock; skew fields null/False; spaghetti windows 200 (1d) and 28 (1w) bars, `references=[]`; order = store order.
- `equities_refresh`: `refresh_ticker(t, fetch=...)` (default `lse_adapter.refresh_equity`, looked up at call time), `refresh_all(...)` (sequential, per-ticker isolation, never raises, no key or URL in logs, one module lock that S9E reuses), `request_refresh_now()` (background thread; a request during a pass sets a pending flag and one more pass follows, so a ticker added mid-pass is not missed), `status()` (S9A form: `running=False`, `disabled_reason` `missing-key` or `not-started`, `interval_seconds` 86400, ticks null, `server_time`, `last_bar_date`).
- `routers/equities` (prefix `/api/equities`): `GET ""`, `POST ""` (body `symbol`, optional `group_id`; 422 invalid, 409 cap; a new ticker triggers one background refresh; layout upkeep is best effort and logged, as `routers/watchlist.py`), `DELETE /{ticker}` (404 missing), `GET /board`, `GET /spaghetti`, `GET /{ticker}/chart` (all three take `timeframe: Literal["1d","1w"]`, anything else 422), `GET /status`, `POST /refresh` (202 `{accepted, already_running}`). No `ccxt_adapter` import.

Tests (new, plain functions): calendar 16, cached read 6, refresh 8, board 14, router 18 = 62; plus +2 net in `test_equities_store.py` = +64. Arithmetic: pytest 1016 + 64 = 1080 passed, 2 skipped, 5 deselected (1082 collected). Red run (G-S9A-0, base plus stubs): 62 failed in the five new files; the three changed store tests each assert a refusal, so they fail on the base too. Board tests include a 1w chip in the Labor Day week (a number) and the reason mapping; refresh tests include a refresh inside the 6 h window that still fetches and a request during a pass that is not lost.
Calendar cases (2026): Sat 10-10 and Sun 10-11 with a Fri 10-09 bar not stale; Mon 10-12 10:00Z not stale; Mon 10-12 21:30Z stale with a Fri bar, not with a Mon bar; Labor Day Mon 09-07 23:00Z and Tue 09-08 12:00Z not stale with a Fri 09-04 bar; close 20:00Z Fri 10-30, 21:00Z Mon 11-02 (edge Nov 1), 21:00Z Fri 03-06, 20:00Z Mon 03-09 (edge Mar 8); `next_refresh_at(Fri 10-09 21:00Z)` = Mon 10-12 20:30Z, `(Fri 09-04 21:00Z)` = Tue 09-08 20:30Z; Thanksgiving 11-26 and Good Friday 04-03 skipped.
Gates: G-S9A-1 `pytest api/tests/data/test_equities_calendar.py api/tests/data/test_lse_cached_read.py api/tests/data/test_equities_refresh.py api/tests/data/test_equities_store.py -q`; G-S9A-2 `pytest api/tests/analytics/test_equities_board.py api/tests/routers/test_equities_router.py -q`; G-S9A-3 full pytest = 1080/2/5; G-S9A-4 `pytest api/tests/deploy/test_main_cors.py api/tests/data/test_lse_adapter.py -q` all passed, both files unedited (includes `test_committed_lse_fixtures_are_synthetic_only`); G-S9A-5 REAL-DATA, `S-secret`, `git diff --check`, `FORBIDDEN`, `FIXTURES`, `S9A-scope`, `S9-words`.
Hidden-break: `test_lse_adapter.py` unedited and green (only added functions); `test_onchain_activity_router.py::test_existing_routes_unchanged` unedited; crypto router tests unedited. Regression guard: crypto board, watchlist and layout pytest files green at old counts.
Files: 14 (10 new, 4 edited). ACs: AC-S9A-1..7.

## S9B: layout section "equities" (RT3)

Depends: S9A merged (its integration tests call A's router). No file overlap with A, so cost-neutral. Live-shape independent. Owned (edit): `api/data/layout.py`, `api/tests/routers/test_layout.py` (table). Owned (new): `api/tests/data/test_layout_equities.py`, `api/tests/routers/test_equities_layout_router.py`. Forbidden: `api/routers/*`, `api/models/*`, `watchlist*.py`, `equities_store.py`.

Design: replace the hard-coded crypto source by a registry `_SECTION_SOURCES = {"crypto": watchlist_store.read_watchlist (looked up at call time), "equities": equities_store.load_tickers}` and `_SECTION_REFERENCES = {"crypto": REFERENCE_SYMBOLS, "equities": ()}`; `SECTIONS = tuple(registry)`. `_reconcile(groups, hidden, coins, references=REFERENCE_SYMBOLS)` keeps its signature and default; `_layout`, `save_layout`, `drop_coin` pass the section's members and references. `GROUP_ID_RE`, `MAX_GROUPS`, `MAX_GROUP_NAME`, file name, revision rules and recovery are shared. Crypto results are unchanged; equities `hidden_lines` keep tickers only (no BTC/HYPE).
Tests: data 12 (SECTIONS tuple; default equities layout from the store; crypto and equities members never mix, so no equity lands in a crypto group; removed ticker reconciled out; place and drop; revision 409; invalid 422 paths; hidden lines keep tickers only and refuse BTC; reset equities leaves crypto; corrupt file recovers equities; `_reconcile` default still keeps BTC/HYPE; save of equities leaves the stored crypto section byte-equal) + router 8 (GET default; POST then GET; stale 409; invalid 422; add with `group_id` places the ticker; remove drops it; no equity in `/api/layout/crypto` after adds; DELETE resets only equities) = +20. Arithmetic: 1080 + 20 = 1100 passed, 2 skipped, 5 deselected.
Gates: G-S9B-1 `pytest api/tests/data/test_layout_equities.py api/tests/routers/test_equities_layout_router.py -q` (20 passed; red run first: 20 failed); G-S9B-2 crypto guard `pytest api/tests/data/test_layout_store.py api/tests/routers/test_layout.py api/tests/routers/test_watchlist.py api/tests/routers/test_watchlist_cap.py api/tests/routers/test_board_integration.py -q` all pass at old counts (15, 10, and the rest unchanged); G-S9B-3 full pytest 1100/2/5; G-S9B-4 REAL-DATA, `S-secret`, `git diff --check`, `FORBIDDEN`, `FIXTURES`, `S9B-scope`, `S9-words`.
Hidden-break: `test_layout_store.py` lines 171-176 already store an `equities` section as "other"; it stays green because the crypto save does not touch it. Cost: 2.0-3.5 USD. ACs: AC-S9B-1..3.

## S9C: /equities page by parameterised reuse (RT1-RT3 web)

Depends: S9A, S9B merged. Live-shape independent. Owned (new): `web/lib/screener-variant.ts`, `web/lib/equities-freshness.ts`, `web/lib/api/equities.ts`, `web/components/screener/VariantProvider.tsx`, `web/components/equities/EquitiesScreener.tsx`, `web/app/equities/page.tsx`, tests `web/lib/__tests__/{screener-variant,equities-api,equities-freshness}.test.ts`, `web/components/screener/__tests__/ScreenerVariant.test.tsx`, `web/components/equities/__tests__/EquitiesScreener.test.tsx`. Owned (edit): `web/components/screener/{ScreenerBoard,CoinPanel,CoinGroup,DrillDownView,AddCoinForm}.tsx`, `web/components/chart/ChartFreshness.tsx`, `web/lib/api/{screener,watchlist,layout,refresh}.ts`, `web/components/shell/AppNav.tsx`. Forbidden: all existing tests, `web/lib/types/*`, `live-poll.ts`, `use-board-layout.ts`, `layout-state.ts`, `FreshnessStrip.tsx`, `SpaghettiChart.tsx`, `web/islands/**`, `globals.css` unless a class is missing (then `needs_input`).

Design:
- `ScreenerVariant` = `{id, timeframes, initialTimeframe, drillDownTimeframe, noun, nounPlural, capMessage, dateOnlyBars}`; `CRYPTO_VARIANT` carries today's literals (five timeframes, "coin", the existing cap message); `EQUITIES_VARIANT` = `["1d","1w"]`, "ticker", the equities cap message, `dateOnlyBars: true`. `useVariant()` returns crypto outside a provider; the context lives in a `"use client"` module; `MAX_COINS` (30) and `isFull` stay in `layout-state.ts` and serve both variants (the variant carries text only).
- Edits read the variant for: board toolbar and default timeframe, empty/loading text; chip row; group count text and empty text; drill-down toggle and default (equities opens on 1d); add form labels, count text and cap message; `ChartFreshness` caption and the gain-chip tooltip (date-only, no clock time: `Latest daily bar 2026-10-09`, `Latest weekly bar, week of 2026-10-05` for 1w, plus "(forming)" and the plain `stale` marker; chip title `1d candle from 2026-10-09`).
- Client factories: `createScreenerClient(base)`, `createWatchlistClient(base)`, `createLayoutClient(section)`, `createStatusFetcher(path)`; the old named exports stay and are bound to the crypto paths, same errors, same timeouts (`screener.ts` keeps the `export function fetchChartView` declaration form: `screener-api.test.ts` reads the source for that string). The equities fetchers are module-level constants: a new function per render would re-fire the board effect, whose deps include `fetchBoard`. `equities.ts` binds them to `/api/equities`, section `equities`, `/api/equities/status`; the add client sends `{symbol, group_id}` and maps 409/422 to the existing error classes.
- `EquitiesScreener` (client): `VariantProvider` + `LiveProvider(fetchStatus=equities status)` + `FreshnessStrip` + a plain note ("Private use only. Prices come from London Strategic Edge under a personal licence and are not shared or redistributed. Prices are split-adjusted only; delisted tickers have no data.") + `ScreenerBoard` with the equities fetchers. `page.tsx` is a server page (`title: "Equities"`, `<h1>Equities</h1>`). `AppNav` gets `{href:"/equities", label:"Equities"}`. No `BtcLegChart`.

Tests: variant 6, equities-api 12, equities-freshness 6, ScreenerVariant 14 (toolbar 1d/1w, chips 1d/1w, nouns, cap text, group text, drill-down default, date-only caption, RSI row, no BTC/HYPE, shared zoom in the variant, layout save through injected equities client, no provider = crypto text), EquitiesScreener 8 (note text, strip polls the equities status at 60 000 ms, add flow, fetch spy sees only `/api/equities*`, never `/api/screener|/api/watchlist|/api/layout/crypto|/api/refresh`, no "Screener" heading) = +46. Arithmetic: vitest 400 + 46 = 446 in 55 files. Red run: the 5 new files fail (46).
Gates: G-S9C-1 `pnpm exec vitest run lib/__tests__/screener-variant.test.ts lib/__tests__/equities-api.test.ts lib/__tests__/equities-freshness.test.ts components/screener/__tests__/ScreenerVariant.test.tsx components/equities` (46 passed); G-S9C-2 crypto guard `pnpm exec vitest run --exclude 'components/equities/**' --exclude '**/{ScreenerVariant,screener-variant,equities-api,equities-freshness}.test.ts*'` = 400 passed in 50 files, every pre-existing file unedited; G-S9C-3 full vitest 446/55, tsc 0, islands 0; G-S9C-4 e2e crypto guard `... pnpm test:e2e e2e/screener.spec.ts e2e/layout.spec.ts e2e/live-refresh.spec.ts e2e/contrast.spec.ts e2e/brussels-time.spec.ts` = 31 passed (10+7+4+7+3), none edited; G-S9C-5 pytest not run (no api change): `git diff --name-only origin/main...HEAD | grep '^api/'` prints nothing; `S-secret`, `git diff --check`, `FORBIDDEN`, `FIXTURES`, `S9C-scope`, `S9-words`, `S9-utc`, `S9-nostore`, `S9-clock`.
Hidden-break: any edit that changes a crypto string or testid fails an existing test: STOP, do not edit the test. T44 linked zoom: `ScreenerBoardLinkedZoom.test.tsx` (3) and e2e test 8 stay green. S11 live: `ScreenerBoardLive` (12), `live-poll` (12), `refresh-strip` (10), `FreshnessStrip` (8) unedited. S5b: `ScreenerBoardLayout` (15), `layout-state`, `layout-api` unedited.
Files: 22 (11 new, 11 edited). Cost: 6.0-9.5 USD. ACs: AC-S9C-1..6.

## S9D: equities end-to-end proof, spaghetti and drill-down (RT1)

Depends: S9C merged. Live-shape independent. Owned (new): `api/scripts/seed_e2e_equities.py`, `api/tests/scripts/test_seed_e2e_equities.py`, `web/e2e/equities.spec.ts`, `web/components/equities/__tests__/{EquitiesSpaghetti,EquitiesDrillDown}.test.tsx`. Owned (edit): `web/playwright.config.ts` (chain `seed_e2e_cache.py && seed_e2e_equities.py && uvicorn` in that order, the first removes the cache root; set `SCREENER_EQUITIES_PATH` to a temp file in `E2E_CACHE_ROOT` and `LSE_API_KEY` to the empty string so the API cannot reach LSE), `web/e2e/contrast.spec.ts` (table). Conditional (only if a D test is red against merged C and the fix is at most 20 lines, else `needs_input`): `web/components/screener/{DrillDownView,SpaghettiChart}.tsx`, `web/lib/spaghetti-lines.ts`. Forbidden: everything else, `seed_e2e_cache.py`.

Design: the seeder refuses to run unless `SCREENER_CACHE_ROOT` is set and not the real root and `SCREENER_EQUITIES_PATH` is set and not `api/data/equities.json` (as `seed_e2e_cache.py`); it writes synthetic bars for `SYNA`, `SYNB`, `SYNC` (420 sessions each, 88 weekly bars, clear of the 60-bar rule, ending on the newest NYSE session due) and `SYNTHIN` (20 bars) through `lse_adapter._write_cache`, tagged `redistributable=false`, plus `equities.json` and a manifest entry. Names are obviously synthetic; no real price series.
Tests: pytest 5 (refuses without env; refuses real paths; files and sidecars written; last bar is the newest due session and bars are NYSE sessions; names and manifest); vitest Spaghetti 6 (no BTC/HYPE in legend or lines, ticker lines at width 1.5, toggle saves `hidden_lines` through the equities client, 1d/1w span text in Brussels dates, unavailable ticker note, empty series) + DrillDown 6 (opens on 1d, 1d/1w toggle, price and RSI chart, RSI N/A when flat, unavailable reason, refetch on live tick) = +12; e2e `equities.spec.ts` 10 + contrast +1 = +11. Arithmetic: pytest 1100 + 5 = 1105; vitest 446 + 12 = 458 in 57 files; e2e 79 + 11 = 90 in 10 files (`equities.spec.ts` 10, `contrast` 8).
E2E cases: (1) page loads, "Equities" heading, private-use note, seeded tickers in a group; (2) Add a ticker, it shows, survives reload; (3) remove it; (4) no equity in any crypto group (`/api/layout/crypto` and the crypto page); (5) 31st ticker refused with the cap text in the UI and 409 from the API, count stays 30; (6) new group, rename, move ticker, reorder groups, persisted after reload; (7) linked zoom: ctrl-wheel on one small chart zooms the others; (8) spaghetti has no BTC/HYPE legend entry and a toggle persists after reload; (9) drill-down opens on 1d with RSI, switches to 1w; (10) Brussels time: captions are date-only, the axis labels are dates, no whole word UTC on the page. Each test restores the seeded state (afterEach).
Gates: G-S9D-1 `pytest api/tests/scripts/test_seed_e2e_equities.py api/tests/scripts/test_seed_e2e_cache.py -q`; G-S9D-2 `pnpm exec vitest run components/equities` (20 passed in 3 files: C's 8 plus D's 12); G-S9D-3 `... pnpm test:e2e e2e/equities.spec.ts e2e/contrast.spec.ts` = 18 passed; G-S9D-4 full e2e 90 passed in 10 files; G-S9D-5 full pytest 1105/2/5, full vitest 458/57, tsc, islands; REAL-DATA, `S-secret`, `git diff --check`, `FORBIDDEN`, `FIXTURES`, `S9D-scope`, `S9-words`, `S9-utc`, `S9-nostore`.
Hidden-break: the seeder must not change the crypto seed or `.fixture-manifest.json` keys other specs read (add a key only). Files: 7 (5 new, 2 edited). Cost: 4.0-6.5 USD. ACs: AC-S9D-1..5.

## S9E: market-hours refresh tick and freshness strip (RT3)

Depends: S9D merged and spend gate (below). Soft-depends on the probe record (two constants). Owned (edit): `api/data/equities_refresh.py`, `api/routers/equities.py` (`/refresh` wakes the worker when running), `api/main.py` (lifespan start/stop of the equities worker after the crypto one), `web/components/screener/FreshnessStrip.tsx` (optional `model` prop, default `stripModel`), `web/components/equities/EquitiesScreener.tsx`. Owned (new): `web/lib/equities-strip.ts`, `web/lib/types/equities.ts` (`EquitiesStatus extends RefreshStatus` with `last_bar_date`), tests `api/tests/data/test_equities_refresh_worker.py`, `api/tests/routers/test_equities_status_router.py`, `web/lib/__tests__/equities-strip.test.ts`, `web/components/screener/__tests__/FreshnessStripModel.test.tsx`, `web/e2e/equities-live.spec.ts`. Forbidden: `refresh_worker.py`, `refresh-strip.ts`, `types/refresh.ts`, `live-poll.ts`, `lse_adapter.py`.

Design: `EquitiesRefreshWorker` (daemon thread, injectable clock, wait Event, fetch, tickers) loops: first tick 20 s after start only if some ticker's newest bar is behind `last_due_session` (catch-up), then sleeps until `next_refresh_at(now)`; a tick runs `refresh_all`; if a ticker is still behind the session this tick is for (not `last_due_session(now)`, still the previous session until close + 60 min) it retries every 30 min up to 3 times, then waits for the next close; all-unavailable ticks back off (double, cap 3600 s) as crypto; `request_now` wakes it; with no `LSE_API_KEY` it does not start (`disabled_reason="missing-key"`); `SCREENER_REFRESH_WORKER=0` keeps it off. `status()` returns the `RefreshStatus` keys with `next_tick_at` = the worker's stored wake instant, set when it computes its sleep as `next_refresh_at(clock())` (non-session days are skipped by the server), advanced when the tick starts, never recomputed per call (a sliding value could never read overdue) and `last_bar_date` (newest bar date over the tickers, `YYYY-MM-DD`).
Overdue rule (stated, tested at both layers): the client treats a refresh as overdue only when the worker is running, has finished a tick, and the server clock is more than 300 s past `next_tick_at`; because `next_tick_at` is always the next market-close refresh, a Saturday, Sunday or US holiday has `next_tick_at` on the next session and can never be overdue; a weekday evening is overdue only 300 s after the missed close + 30 min.
`equitiesStripModel(status, nowMs)` reuses `stripModel`, `isOverdue`, `stripTime` and replaces the help text; it adds "Latest daily bar 2026-10-09" (date-only), "Next expected refresh Mon 12 Oct 22:30 CEST" (Brussels, from the server instant, so 21:30 CET appears in the weeks the US and Europe are on different clocks), and plain wording for off/missing-key. No 15-minute proof text.
Tests: worker 14 (first tick and catch-up, no catch-up when current, tick lands at close + 30 min, retry 3 x 30 min, weekend and holiday skipped, per-ticker isolation, backoff, missing key, env 0, stop, wake, status keys, `last_bar_date`, no key in logs) + router 3 (running through the `TestClient(app)` lifespan with a fake fetch, off, missing-key) ; vitest strip 14 (waiting, off, missing-key, Friday evening normal, Saturday not overdue, Sunday not overdue, holiday Monday not overdue, weekday overdue past 300 s, exactly 300 s not overdue, failed, last-bar text, next time CEST and CET, backoff note, help text) + FreshnessStripModel 4 = +18 vitest; e2e `equities-live.spec.ts` 2 (strip shows the latest bar date and the off reason with the worker off; no overdue element). Arithmetic: pytest 1105 + 17 = 1122; vitest 458 + 18 = 476 in 59 files; e2e 90 + 2 = 92 in 11 files.
Gates: G-S9E-1 `pytest api/tests/data/test_equities_refresh_worker.py api/tests/routers/test_equities_status_router.py api/tests/data/test_equities_calendar.py -q`; G-S9E-2 crypto and startup guard `pytest api/tests/data/test_refresh_worker.py api/tests/routers/test_refresh_router.py api/tests/deploy/test_refresh_startup.py api/tests/deploy/test_main_cors.py -q` unedited and green; G-S9E-3 `pnpm exec vitest run lib/__tests__/equities-strip.test.ts components/screener/__tests__/FreshnessStripModel.test.tsx components/screener/__tests__/FreshnessStrip.test.tsx lib/__tests__/refresh-strip.test.ts lib/__tests__/live-poll.test.ts`; G-S9E-4 full pytest 1122/2/5, vitest 476/59, tsc, islands; G-S9E-5 e2e `e2e/equities-live.spec.ts e2e/live-refresh.spec.ts e2e/equities.spec.ts` then full 92/11; G-S9E-6 REAL-DATA, `S-secret`, `git diff --check`, `FORBIDDEN`, `FIXTURES`, `S9E-scope`, `S9-words`, `S9-utc`, `S9-nostore`, `S9-clock`. Hidden-break: the S11 strip, poller and `test_refresh_status_ts_interface...` stay unedited. Files: 12 (7 new, 5 edited). Cost: 4.5-7.0 USD. ACs: AC-S9E-1..5.

## Touchpoints

Each slice section lists its Owned (new and edit) and Forbidden files; they are the touchpoint set. Read only: `live-poll.ts`, `use-board-layout.ts`, `layout-state.ts`, `SpaghettiChart.tsx`, `spaghetti-lines.ts`, `freshness.py`, `refresh_worker.py`.

## Public Contracts

New HTTP: `/api/equities` (GET, POST), `/api/equities/{ticker}` (DELETE), `/api/equities/board`, `/spaghetti`, `/{ticker}/chart` (responses are the existing `ScreenerBoardResponse`, `SpaghettiResponse`, `ChartView`; no model change, TS mirrors unchanged), `/api/equities/status` (the `RefreshStatus` keys plus `last_bar_date`), `/api/equities/refresh` (202). Layout API gains section `equities` (404 for unknown sections unchanged). New behaviour: 409 at 30 tickers. Web: `ScreenerVariant` context, client factories with the old exports intact, optional `FreshnessStrip` `model` prop. No change to `/api/screener`, `/api/watchlist`, `/api/layout/crypto`, `/api/refresh`. Security (STRIDE quick pass): the only secret is `LSE_API_KEY`, read from env at call time and sent only by the adapter (its existing request path, reached through `refresh_equity`); routers, status, logs and errors carry closed-enum reasons only; CORS methods unchanged; tickers pass `TICKER_RE` before any path or URL use (no path traversal into cache dirs).

## Blast Radius

59 file touches: S9A 14, S9B 4, S9C 22 (11 new, 11 edited), S9D 7, S9E 12. Risk class: public API surface plus shared board components (RT3). Crypto behaviour is the regression surface: guarded by the unedited crypto pytest, vitest and 31 crypto e2e tests listed per slice. Rollback: one PR per slice; reverting S9E leaves a working page without live refresh, S9C removes the page, S9A and S9B are additive.

## Acceptance Criteria

| ID | Behaviour | proven by | strategy | SPEC link |
|---|---|---|---|---|
| AC-S9A-1 | add/list/remove; 31st refused 409 with message, count stays 30; re-add at cap ok; remove then add ok | `test_equities_router`, `test_equities_store` | Fully-Automated | AC-26 (amended), outcome 18 |
| AC-S9A-2 | board/chart read the cache only (transport that raises is never used); price, 1d/1w chips (1w also in a Monday-holiday week), RSI 14, plain unavailable reasons | `test_equities_board`, `test_lse_cached_read` | Fully-Automated | AC-15, D9 |
| AC-S9A-3 | weekends and holidays are not stale; stale after the due bar (1w judged on its daily leg); partial before due | `test_equities_calendar` | Fully-Automated | decision 3 |
| AC-S9A-4 | key never in logs, status, errors; missing key = unavailable; fixtures synthetic | `test_equities_refresh`, synthetic guard, SECRET | Fully-Automated | D10, decision 7 |
| AC-S9A-5 | spaghetti: percent from window start, windows 200/28, no references | `test_equities_board` | Fully-Automated | decision 5 |
| AC-S9A-6 | crypto API unchanged | full pytest at old counts | Fully-Automated | regression |
| AC-S9A-7 | a refresh always fetches (no 6 h skip); a request during a pass is not lost | `test_equities_refresh` | Fully-Automated | decision 3 |
| AC-S9B-1 | equities section independent; no equity in a crypto group | `test_layout_equities`, `test_equities_layout_router` | Fully-Automated | AC-15 |
| AC-S9B-2 | group edits, order and hidden lines persist; revision 409; 422 | same | Fully-Automated | decision 1 |
| AC-S9B-3 | crypto layout results identical | `test_layout_store`, `test_layout` unchanged | Fully-Automated | regression |
| AC-S9C-1 | page shows groups, 1d/1w chips, RSI, add/remove, private-use note | `ScreenerVariant`, `EquitiesScreener` vitest | Fully-Automated | AC-15 |
| AC-S9C-2 | crypto render and strings unchanged | 11 existing component files, 31 crypto e2e | Fully-Automated + Hybrid | regression |
| AC-S9C-3 | linked zoom works in the variant | `ScreenerVariant` zoom test, `ScreenerBoardLinkedZoom` unchanged | Fully-Automated | decision 1, T44 |
| AC-S9C-4 | date-only bar captions, Brussels axis | `equities-freshness`, `ScreenerVariant` | Fully-Automated | decision 1 |
| AC-S9C-5 | equities page calls only `/api/equities*` | fetch-spy test | Fully-Automated | decision 4 |
| AC-S9C-6 | page re-checks every 60 s | `EquitiesScreener` interval test | Fully-Automated | decision 3 |
| AC-S9D-1 | add flow, persists on reload, no equity in crypto groups, private-use note | `equities.spec` 1-4 | Hybrid | AC-15 |
| AC-S9D-2 | spaghetti has no reference lines; toggle persists | `EquitiesSpaghetti`, `equities.spec` 8 | Hybrid | decision 5 |
| AC-S9D-3 | drill-down 1d/1w with RSI | `EquitiesDrillDown`, `equities.spec` 9 | Hybrid | decision 1 |
| AC-S9D-4 | 31st refused in UI and API | `equities.spec` 5 | Hybrid | AC-26 (amended) |
| AC-S9D-5 | groups edits, linked zoom, Brussels time, contrast on /equities | `equities.spec` 6, 7, 10, `contrast` | Hybrid | decision 1 |
| AC-S9E-1 | refresh tick at close + 30 min, catch-up, retries | `test_equities_refresh_worker`, `test_equities_calendar` | Fully-Automated | decision 3 |
| AC-S9E-2 | weekends and holidays never overdue (server skip + 300 s client rule) | worker, router and `equities-strip` tests | Fully-Automated | decision 3 |
| AC-S9E-3 | strip shows latest bar date and next expected refresh in Brussels time | `equities-strip`, `equities-live.spec` | Fully-Automated + Hybrid | decision 3 |
| AC-S9E-4 | failure, backoff and missing key visible in plain words | worker and strip tests | Fully-Automated | D10 |
| AC-S9E-5 | crypto worker, strip and startup unchanged | S11 and startup tests unedited | Fully-Automated | regression |
| AC-S9-r1 | real LSE fetch, auth, wrapper, timestamp, partial bar | P-S9-1 and P-S9-2 on the PC | Agent-Probe; Known-Gap residual, gates stay CONDITIONAL | AC-15 live part |
| AC-S9-r2 | early closes (13:00 ET) and special closures not modelled | none; backlog stub | Known-Gap residual | decision 3 |

Backlog stubs to file at UPDATE PROCESS (residuals, CONDITIONAL): `equities-live-pc-check_NOTE_12-10-26.md` (AC-S9-r1, test-building: record the probe fixture and a contract test), `equities-early-close-calendar_NOTE_12-10-26.md` (AC-S9-r2).

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G-S9A-1..3 calendar, cached read, refresh, board, router, store, full pytest | Fully-Automated | AC-26 (amended), AC-15 data half, D9, D10 (AC-S9A-1..7) |
| G-S9B-1..3 layout section and crypto guard | Fully-Automated | AC-15 (no equity in a crypto group), decision 1 (AC-S9B-1..3) |
| G-S9C-1..3 vitest, tsc, islands | Fully-Automated | AC-15 page, decisions 1 and 3 (AC-S9C-1..6) |
| G-S9C-4 crypto e2e guard (31 tests) | Hybrid | regression of crypto board, layout, live, contrast (AC-S9C-2) |
| G-S9D-3, G-S9D-4 equities and full e2e | Hybrid | AC-15 Playwright add flow, AC-26 (amended) (AC-S9D-1..5) |
| G-S9E-1..4 worker, status, strip, full counts | Fully-Automated | decision 3 live and weekend rule (AC-S9E-1..5) |
| G-S9E-5 e2e live strip | Hybrid | decision 3 strip content (AC-S9E-3) |
| P-S9-1 probe record, P-S9-2 on-PC page check | Agent-Probe | AC-15 live LSE fetch (AC-S9-r1) |

User probes: P-S9-1 live shape (run `lse_probe.py` with `LSE_API_KEY` set for the shell session only; fill the Probe record; copy the sanitised fixture as the backlog note says). P-S9-2 on the PC after S9C and again after S9E: open `/equities`, add 2 real tickers, wait for a refresh, check the strip, Brussels times, a weekend or holiday view, reload persistence, no key in any log or page. P-S9-3 phone/iPad reachability of `/equities` (as P-S5b-1). Probes are never claimed by workers; each slice stays at `review` until its probe.

## Risk Predictions (condensed)

Highest: (1) parameterising shared components breaks a crypto string or testid (variant defaults to crypto, no existing test edited, 31 crypto e2e at C and D). (2) A read that fetches blocks the board (cache-only reads, spy test). (3) Calendar edges: DST weeks, holidays, early closes (dated cases above; early close is a residual). (4) A thread in the `main.py` lifespan (env 0 in tests, startup tests unedited). (5) Layout reconciled against the wrong source (registry, mixed-membership tests). Edge cases: `BRK.B` in URLs (encode), ticker removed with its drill-down open (existing close logic), cold ticker after Add (existing 4 s and 12 s board retry), invalid key (`auth-rejected`, plain text).

## Program budget and costs

Ceiling 100 USD (user), spent about 69.4, 30.6 left. Estimates are worker plus one tester run (about 0.5 USD); planner and validate sessions are not metered (Q4). Reference: S11b 7.74 USD, T32-T38 4.2-5.6 USD each.

| Slice | Files | New tests | Estimate [USD] | Basis |
|---|---|---|---|---|
| S9A | 14 | 64 pytest | 5.0-7.5 | 6 new source/test modules, 2 full pytest runs (3.5 min each), 120 tool calls |
| S9B | 4 | 20 pytest | 2.0-3.5 | one module refactor, 2 test files, 1 full run |
| S9C | 22 | 46 vitest | 6.0-9.5 | 9 edited components/clients, 5 test files, e2e guard twice, 170 tool calls |
| S9D | 7 | 5 pytest, 12 vitest, 11 e2e | 4.0-6.5 | seeder, 1 spec, 2 vitest files, full e2e twice |
| S9E | 12 | 17 pytest, 18 vitest, 2 e2e | 4.5-7.0 | thread worker with fake clock, strip model, e2e twice |
| Total | 59 | pytest +106, vitest +76, e2e +13 | 21.5-34.0 | mid about 27.8 |

Where it lands against 100: spent 69.4 + A-D = 86.4 to 96.4 (mid 91.4); with E = 90.9 to 103.4 (mid 97.2). The high case overshoots by 3.4 USD, so E is gated: spawn E only when the measured total after D is at most 93.0 USD (E's high 7.0 then still fits under 100) and the user says go. Calibration: S5b (the closest precedent, shared board edits) cost 9.99 USD against an 8.0 high, +25%; the same overrun on A-D would reach 103.2, so each slice is spawned only after the previous one's measured cost is known, and D only when the measured total after C is at most 93.0 USD (D's high 6.5 then fits). Per-slice cap 15 USD is not reached by any high figure. The rest of the programme (S10, AC-8 group sort, contrast notes) shares what is left and is not planned here.

Recommended cut lines: (1) after A+B: API and layout usable by curl; (2) after C: usable page, data refreshed only on Add and `POST /api/equities/refresh` (known gap until E); (3) after D (recommended cut, 86.4-96.4): AC-15 and amended AC-26 proven by Playwright; (4) after E: live. If the spend after D leaves less than 7.0 USD, stop at (3) and file E as a follow-up.

## Phase Completion Rules

`CODE DONE` = PR open, gates green in the report. `VERIFIED` = independent tester or CI on the head SHA, the tester's e2e run (S9C-S9E) and the slice's PC probe. Merge only when every gate including e2e is green, CI is green and report heading 9 has no open `needs_input` or `blocker`. S9A and S9B stay at `review` until the first P-S9-2 (after S9C); S9C, S9D and S9E until their P-S9-2 run. Known-Gap residuals keep the live gates CONDITIONAL. Pre-spawn: the planner re-counts the baselines on the current `main`, checks MASTER-PLAN spend, and assigns task ids (this plan edits no MASTER-PLAN).

## Open choices (not decided here)

Q1 Intraday for equities (assumed none, D9). Q2 Gain chip meaning: newest candle open to latest (parity, chosen) versus change from the previous close. Q3 The static note carries two caveats (split-adjusted, delisted); cut them if "no flags" is strict. Q4 Whether planner, validate and tester sessions count toward the 100 USD. Q5 The spend gate of 93.0 USD before E (and before D, after C). Q6 A visible "Refresh now" button (not planned; `POST /api/equities/refresh` only). Q7 Early-close days accepted as a residual. Q8 Ticker format (`.` and `-` allowed by `TICKER_RE`) until the probe shows LSE's symbols. Q9 Whether the `/equities` nav link ships in S9C (planned yes; the home page card list is not touched). Q10 Merge order against the pending PC probes P-S5a-1, P-S5b-1.

## Test Infra Improvement Notes

(none identified yet) Candidates: a CI job for seeded Playwright specs (S9C-S9E rely on local e2e); one shared synthetic-OHLCV builder for the pytest helper and the seeder (duplicated by design today).

## Implementation Checklist (atomic; one slice per worker)

Order: S9A, S9B, S9C, S9D, then S9E after the spend gate. Per slice: red-first stubs and the red run, source changes in the order of the slice's Design list, real tests, gates G-S9x-n in order, report. The Design and Tests lines of each slice section are the atomic steps.

## Scope and scan commands (repo root, after the commit; each prints nothing when clean; gates cite these labels)

```
# FORBIDDEN (all slices; the stop-at-review set of gate 6; every other forbidden file is outside each scope list)
git diff --name-only origin/main...HEAD | grep -E '^(CLAUDE\.md|AGENTS\.md|README\.md|\.claude/|\.github/|deploy/|uv\.lock|api/pyproject\.toml)'
# FIXTURES (all slices)
git diff --name-only origin/main...HEAD | grep -E '/fixtures/'
# S-secret (all slices; added lines)
git diff origin/main...HEAD | grep -nE "^\+.*(Bearer [A-Za-z0-9._-]{12,}|(API_?KEY|SECRET|TOKEN|PASSWORD)[A-Z_]* *[:=] *[\"'][A-Za-z0-9+/_-]{12,})"
# S9A-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/(main\.py|data/(equities_(calendar|refresh|store)|lse_adapter)\.py|analytics/equities_board\.py|routers/equities\.py|tests/(equities_fixtures\.py|data/test_(equities_(calendar|refresh|store)|lse_cached_read)\.py|analytics/test_equities_board\.py|routers/test_equities_router\.py))|process/.*-s9a_REPORT_[0-9-]+\.md)$'
# S9B-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/(data/layout\.py|tests/(routers/test_layout\.py|data/test_layout_equities\.py|routers/test_equities_layout_router\.py))|process/.*-s9b_REPORT_[0-9-]+\.md)$'
# S9C-scope
git diff --name-only origin/main...HEAD | grep -vE '^(web/(lib/(screener-variant|equities-freshness)\.ts|lib/api/(equities|screener|watchlist|layout|refresh)\.ts|lib/__tests__/(screener-variant|equities-api|equities-freshness)\.test\.ts|components/screener/(VariantProvider|ScreenerBoard|CoinPanel|CoinGroup|DrillDownView|AddCoinForm)\.tsx|components/screener/__tests__/ScreenerVariant\.test\.tsx|components/chart/ChartFreshness\.tsx|components/equities/(EquitiesScreener\.tsx|__tests__/EquitiesScreener\.test\.tsx)|components/shell/AppNav\.tsx|app/equities/page\.tsx)|process/.*-s9c_REPORT_[0-9-]+\.md)$'
# S9D-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/(scripts/seed_e2e_equities\.py|tests/scripts/test_seed_e2e_equities\.py)|web/(playwright\.config\.ts|e2e/(equities|contrast)\.spec\.ts|components/equities/__tests__/(EquitiesSpaghetti|EquitiesDrillDown)\.test\.tsx|components/screener/(DrillDownView|SpaghettiChart)\.tsx|lib/spaghetti-lines\.ts)|process/.*-s9d_REPORT_[0-9-]+\.md)$'
# S9E-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/(data/equities_refresh\.py|routers/equities\.py|main\.py|tests/(data/test_equities_refresh_worker|routers/test_equities_status_router)\.py)|web/(lib/(equities-strip\.ts|types/equities\.ts|__tests__/equities-strip\.test\.ts)|components/(screener/FreshnessStrip\.tsx|equities/EquitiesScreener\.tsx|screener/__tests__/FreshnessStripModel\.test\.tsx)|e2e/equities-live\.spec\.ts)|process/.*-s9e_REPORT_[0-9-]+\.md)$'
# S9-words (added source lines, tests and e2e excluded)
git diff -U0 origin/main...HEAD -- api web ':(exclude)api/tests' ':(exclude)web/e2e' ':(exclude)*__tests__*' | grep -E '^\+[^+]' | grep -niwE 'bullish|bearish|buy|sell|overbought|oversold|confidence|momentum|trend|benchmark|narrative|(out|under)perform(ing)?|favorable|healthy|verdict|badge|rating|score'
# S9-utc (web only)
git diff -U0 origin/main...HEAD -- web ':(exclude)web/e2e' ':(exclude)*__tests__*' | grep -E '^\+[^+]' | grep -nw UTC | grep -v 'Date\.UTC'
# S9-nostore (web only)
git diff -U0 origin/main...HEAD -- web ':(exclude)web/e2e' ':(exclude)*__tests__*' | grep -E '^\+[^+]' | grep -nE 'localStorage|sessionStorage|indexedDB|document\.cookie'
# S9-clock (the server clock only)
grep -nE 'Date\.now\(|new Date\(\)' web/lib/equities-*.ts
```

## Validate Contract

Status: PASS
Gate: PASS
Date: 12-10-26
date: 2026-10-12
generated-by: outer-pvl
Code under test: main `881a2fd` (branch `claude/pensive-albattani-ou0cgv`, merged with main; `git diff 881a2fd -- api web` is empty). Evidence: `screener-batch5-equities-pvl-iteration-001_REPORT_12-10-26.md` (CONDITIONAL, F1-F12), `-002` (fold), `-003` (PASS) and `results.tsv` rows 1-3.
Parallel strategy: sequential (score 3 of 7: S2 new public endpoints, S6 secret handling, S7 59 file touches; no cross-talk needed; one validator ran Layer 1 and Layer 2 inline against the real code; 1 agent, cost guard not triggered)
Rationale: dominant signal S2 (a new public API plus shared board components); every check was a read of one plan against real files plus targeted runs. EXECUTE strategy for the planner: sequential, one opus worker per slice in the order A, B, C, D, E (E after the spend gate), one sonnet tester at EVL per slice, about 10 agents in all; parallel subagents add nothing (A to E are dependent and C, E share `EquitiesScreener.tsx`), a workflow (5 steps x 2 agents x 1 = 10) only scripts the same order, an agent team (2 members x 5 rounds = 10) has nothing to coordinate.

Test gates (5-column table; strategy values Fully-Automated | Hybrid | Agent-Probe only; Known-Gap is never a strategy). gap-resolution: A proven now (baseline re-counted at VALIDATE), B gate added by this plan's checklist (runs at EXECUTE), C deferred to a user probe, D backlog stub.

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-S9A-1 | add, list, remove; 31st refused 409; concurrent adds capped at 30 | Fully-Automated | G-S9A-1 `test_equities_store.py` (3 changed tests), G-S9A-2 `test_equities_router.py` | B |
| AC-S9A-2, 5 | cache-only board, chart, spaghetti; 1d/1w chips incl. the Labor Day week; RSI; closed reasons; windows 200/28 | Fully-Automated | G-S9A-1 `test_lse_cached_read.py`, G-S9A-2 `test_equities_board.py` | B |
| AC-S9A-3 | weekend and holiday not stale; weekly judged on its daily leg; DST edges Mar 8, Nov 1; next refresh | Fully-Automated | G-S9A-1 `test_equities_calendar.py` | B |
| AC-S9A-4, 7 | key never in logs, status, errors; a refresh inside 6 h still fetches; a request during a pass is kept | Fully-Automated | G-S9A-1 `test_equities_refresh.py`; G-S9A-4 `test_lse_adapter.py` unedited; `S-secret` | B |
| AC-S9A-6 | crypto API unchanged | Fully-Automated | G-S9A-3 full pytest 1080/2/5 (baseline 1018 collected re-counted) | A |
| AC-S9B-1, 2 | equities layout section independent, edits persist, 409/422 | Fully-Automated | G-S9B-1 (20) | B |
| AC-S9B-3 | crypto layout identical | Fully-Automated | G-S9B-2, G-S9B-3 1100/2/5 | A |
| AC-S9C-1, 3, 4, 5, 6 | page, linked zoom, date-only captions, only `/api/equities*`, 60 s re-check | Fully-Automated | G-S9C-1 (46 in 5 files) | B |
| AC-S9C-2 | crypto render and strings unchanged | Fully-Automated + Hybrid | G-S9C-2 (400 in 50), G-S9C-4 (31 crypto e2e) | A |
| AC-S9D-1..5 | add flow, no BTC/HYPE, drill-down, 31st refused, groups, zoom, Brussels dates, contrast | Hybrid | G-S9D-3 (18), G-S9D-4 (90 in 10); precondition Chromium plus seeded stack, CI does not run Playwright | B |
| AC-S9E-1, 2, 4 | tick at close + 30 min, catch-up, retries, never overdue off-session, failure wording | Fully-Automated | G-S9E-1, G-S9E-3 | B |
| AC-S9E-3 | strip shows latest bar date and next refresh in Brussels time | Fully-Automated + Hybrid | G-S9E-3, G-S9E-5 (92 in 11) | B |
| AC-S9E-5 | crypto worker, strip, startup unchanged | Fully-Automated | G-S9E-2, G-S9E-3 | A |
| AC-S9-r1 | real LSE fetch, auth, wrapper, timestamp, partial bar | Agent-Probe | P-S9-1, P-S9-2 on the PC | C |
| AC-S9-r2 | early closes (13:00 ET) and special closures | Agent-Probe | P-S9-2 on 2026-11-27 or 2026-12-24 | D (`equities-early-close-calendar_NOTE`) |

Legacy line form:
- API (AC-S9A-1..7): [Fully-automated: G-S9A-1..3, `S9A-scope`, `S-secret`] | [agent-probe: P-S9-1] | [known-gap: AC-S9-r1, AC-S9-r2 documented]
- Layout (AC-S9B-1..3): [Fully-automated: G-S9B-1..3]
- Page (AC-S9C-1..6): [Fully-automated: G-S9C-1..3, `S9-words`, `S9-utc`, `S9-nostore`, `S9-clock`] | [hybrid: G-S9C-4]
- E2E (AC-S9D-1..5): [hybrid: G-S9D-3, G-S9D-4]
- Live (AC-S9E-1..5): [Fully-automated: G-S9E-1..4] | [hybrid: G-S9E-5] | [agent-probe: P-S9-2 after S9C and S9E, P-S9-3]
Failing stubs: one per Tests-list entry (gate convention 4), pytest `raise NotImplementedError("NOT IMPLEMENTED - TDD stub: <behaviour>")`, vitest and Playwright `throw new Error(...)`; not repeated under the rows so no envelope range moves (precedent: batch 4 PVL cycle 3).

Dimension findings:
- Infra fit: PASS - `main.py:91-98`, `layout.py:35-38,168,251,305`, `lse_adapter.py:320-363`, `equities_store.py`, `refresh_worker.status()` keys, the web files and line cites match the real code; the S9A/S9B file-overlap claim (none) holds; `refresh_equity` closes the 6 h TTL hole (F1).
- Test coverage: PASS - counts recounted: S9A 62 + 2 net, S9B 20, S9C 46, S9D 5 + 12 + 11, S9E 17 + 18 + 2; totals +106 pytest, +76 vitest, +13 e2e; end 1122 / 476 in 59 files / 92 in 11; baselines re-run (pytest 1018 collected of 1023, vitest 400 in 50, e2e 79 in 9); every AC maps to a named gate; every command in "Scope and scan commands" dry-run clean on owned paths and catching strays.
- Breaking changes: PASS - additive endpoints only; the unedited crypto tests that read source or enumerate (`screener-api.test.ts`, `test_layout.py` route list, `test_refresh_router.py` key parse, `test_onchain_activity_router.py` route set, `test_refresh_startup.py`) stay green by the stated rules.
- Security surface: PASS - `LSE_API_KEY` env only, header only inside the adapter, closed reason strings, tickers pass `TICKER_RE`, tests delenv the key and cannot reach the network, e2e API gets an empty key.
- S9A feasibility: PASS - highest-risk edit `equities_board` weekly and reason rules (F2, F4) and the refresh pass lock (F5).
- S9B feasibility: PASS - highest-risk edit the registry looked up at call time (`test_screener_rsi.py` monkeypatches `read_watchlist`).
- S9C feasibility: PASS - highest-risk edit the five shared components (variant default = crypto text, 11 component files and 31 e2e as guard); fetchers are module constants (F7).
- S9D feasibility: PASS - highest-risk edit the seed order and the empty key in `playwright.config.ts` (F8).
- S9E feasibility: PASS - highest-risk edit the worker's stored `next_tick_at` and retry reference (F3), then the lifespan wiring (now tested).
- Envelopes: PASS - recomputed from the saved file: CLAUDE.md 13,443 B; rooms in the final table (every row at least 8,000 B).

Findings folded by PVL cycle 2 (all verified present in the saved plan by cycle 3):
| # | Finding (cycle 1) | Fold |
|---|---|---|
| F1 | `fetch_equity_ohlcv` returns the cache for 6 h, so a tick or manual refresh within 6 h of the last fetch was a no-op | S9A design: second adapter function `refresh_equity`; `refresh_ticker` uses it; AC-S9A-7 |
| F2 | `compute_gain_chip` answers N/A for 1w when the Monday bar is missing (reproduced: Labor Day week); weekly stale/partial would read the Monday label | S9A design: chips built in `equities_board`; weekly rules on the daily leg |
| F3 | S9E retry compared against `last_due_session(now)` (still the previous session at close + 30 min) and `next_tick_at` could slide, so a missed tick never read overdue | S9E design: retry vs the tick's own session; stored `next_tick_at` |
| F4 | no mapping onto the closed `UnavailableReason`; board and spaghetti timeframes unvalidated | S9A design: mapping, `Literal["1d","1w"]` on all three reads |
| F5 | a refresh request during a pass could be dropped; two writers (thread and worker) without a shared lock; store add had no lock | S9A design: pending flag, one module lock, store lock |
| F6 | the scan commands named in the gates did not exist (only an S9A scope that would flag the worker's own report); scans read `main...` before the commit | section "Scope and scan commands", tested; conventions 7, 8, 9, 10 |
| F7 | S9C traps: `screener-api.test.ts` reads `screener.ts` for `export function fetchChartView`; per-render fetcher functions re-fire the board effect; chip tooltip and 1w caption would show a clock time or "daily"; G-S9C-2 was not a runnable command | S9C design and gates |
| F8 | S9D: seed order after `seed_e2e_cache.py` (it removes the cache root), no key guard for the e2e API, 300 sessions leave 63 weekly bars (limit 60) | S9D design: order, empty `LSE_API_KEY`, 420 sessions |
| F9 | the lifespan wiring in `main.py` (S9E) had no test | router test 3 now runs through `TestClient(app)` (count-neutral) |
| F10 | the 3 changed store tests were said to fail on the base although two of them pass there | each now asserts a refusal |
| F11 | budget: mid values 91.2 and 96.9 were 91.4 and 97.2 (mid 27.8); S9C could overrun like S5b (+25%) | budget text: calibration and a spend gate before D |
| F12 | worker ranges: 13,377 B and S9A/S9E too tight once F1-F6 landed; rows dropped from the common set | final table below; common = line 11 and 30-66, criteria rows left to PVL and the tester |

Advisories (none blocks):
A1. Envelope room is thin for S9A (8,057 B) and S9E (8,154 B): any later edit inside their ranges is byte-neutral; a realistic envelope is 2-3 KB.
A2. `equities_store.load_tickers` raises on a corrupt JSON file, so the equities reads would answer 500; the worker may catch it in the source function and read no tickers (logged). Not tested.
A3. An unknown ticker (LSE 404) stays in the list, counts toward 30 and reads "Symbol configuration issue"; the user removes it.
A4. Between the S9A and S9B merges the add/remove layout upkeep logs a caught UnknownSectionError warning; harmless.
A5. The S9E worker starts only when `LSE_API_KEY` is set at API start; setting it later needs a restart. After a restart the strip reads "Server has not finished its first refresh" until the next tick.
A6. The seeded e2e must not assert the absence of the `stale` marker: a run that crosses a session's due time (close + 60 min) makes the seeded last bar one session old.
A7. Early-close days (13:00 ET: 2026-11-27, 2026-12-24) show the bar "forming" and refresh about 3 h late; residual AC-S9-r2.
A8. `ScreenerVariant` 14 and `EquitiesScreener` 8 list 12 and 6 behaviours by name; the counts bind, the worker adds the rest.
A9. The home page card list (`app/page.tsx`) is not extended; the nav link only (Q9).
A10. `S-secret` is a heuristic (a literal `KEY = "..."` of 12+ characters or a `Bearer` token); tests use a constant and assert its absence from logs.
A11. A pre-D spend gate was added (93.0 USD after C); S9C is the slice most likely to overrun.

Open gaps: AC-S9-r1 (real LSE shape, auth, timestamp, partial bar: probes P-S9-1 and P-S9-2, gap-resolution C; backlog `equities-live-pc-check_NOTE_12-10-26.md` filed at UPDATE PROCESS), AC-S9-r2 (early closes, gap-resolution D); probe P-S9-3; advisories A1-A11. None is a FAIL or an unresolved CONCERN.

### What This Coverage Does NOT Prove
What this coverage does NOT prove: the live LSE request, auth scheme, response wrapper, timestamp convention and the partial-bar rule (synthetic fixtures only; probes P-S9-1, P-S9-2); the market-close timing against the real feed (`REFRESH_DELAY_MINUTES` 30, `BAR_DUE_AFTER_MINUTES` 60 are estimates until the probe); early closes and special closures; the real Chromium behaviour of the page on the user's display, phone and iPad (P-S9-2, P-S9-3); a wedged but alive worker thread (the overdue rule reads the stored `next_tick_at`, tested with a fake clock only); CI never runs Playwright, so S9C to S9E e2e is a worker and tester run; neither CI nor the gates run `next build` for `/equities`; the 1w chip rule in a Monday-holiday week is tested on synthetic bars; the 30-ticker cap under two browser tabs racing is covered by the store lock test, not by a browser test.

Accepted by: n/a - no CONCERN outstanding (0 FAIL, 0 CONCERN after the fold); the residuals AC-S9-r1 and AC-S9-r2 are named, not accepted concerns; the user's decisions 1-8 and the open choices Q1-Q10 stand as written in the plan.

## Autonomous Goal Block

SESSION GOAL: screener batch 5 - the /equities page at parity with the crypto screener. S9A API, cache-only board, calendar and minimal refresh; S9B layout section; S9C page by parameterised reuse; S9D e2e proof; S9E market-hours refresh tick and freshness strip. One opus worker per slice, strictly in the order A, B, C, D, E; D and E only after their spend gates.
Charter + umbrella plan: N/A - single plan (user decisions 1-8 are in the plan; no umbrella plan with a Stable Program Goal exists).
Autonomy: validated PASS (PVL cycles 1-3: CONDITIONAL, fold, PASS). EXECUTE needs the user's explicit "ENTER EXECUTE MODE". The planner then re-counts the baselines on main (pytest 1018 collected, vitest 400 in 50 files, e2e 79 in 9), checks MASTER-PLAN spend, registers the task, writes the S9A envelope (master-planner.md section 8, at most 8,000 B, pointers to the "Envelope line ranges" table; S9A room 8057 B, so measure with wc -c and re-measure CLAUDE.md, 13,443 B) saved as `screener-batch5-equities-s9a_REF_<dd-mm-yy>.md`, and spawns S9A only. Each later envelope follows the previous merge SHA and an independent tester pass.
Hard stop conditions / safety constraints:
- No envelope or worker before "ENTER EXECUTE MODE"; no slice in parallel; no slice before the previous one is merged and tested.
- Spend: ceiling 100 USD, about 69.4 spent, 15 USD per slice; S9D only if the measured total after S9C is at most 93.0 USD; S9E only if the measured total after S9D is at most 93.0 USD and the user says go.
- A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/`, `uv.lock`, `api/pyproject.toml` stops at review; the scan commands run after the commit.
- needs_input means STOP: do NOT merge, do NOT open a new PR; the seeded e2e (S9C-S9E) runs on the head SHA before any merge, NOT-RUN stops at needs_input.
- LSE_API_KEY is read from the environment only and never logged, echoed or committed; fixtures are synthetic only; probes P-S9-1..3 are the user's and never claimed by a worker.
- Push, merge, deploy, branch deletion or spend above the caps needs the user's approval.
Next phase: EXECUTE: process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities_PLAN_12-10-26.md
Validate contract: process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities_PLAN_12-10-26.md (inline, PASS, PVL cycle 3)
Execute start: S9A: `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_equities_calendar.py api/tests/data/test_lse_cached_read.py api/tests/data/test_equities_refresh.py api/tests/data/test_equities_store.py api/tests/analytics/test_equities_board.py api/tests/routers/test_equities_router.py -q` red run on the untouched base with stubs (62 failed in the five new files, the 3 changed store tests failed too), then the code and all gates once | probes: P-S9-1..3 on the user PC | high-risk pack: no

## Worker envelopes

Written by the planner after the user's "ENTER EXECUTE MODE": one per slice, at most 8,000 bytes, pointers to the ranges table, saved as `screener-batch5-equities-s9<x>_REF_<dd-mm-yy>.md` here. Each repeats gate convention 11, its Owned/Forbidden lists, the editable-test table and "e2e NOT-RUN stops at needs_input".

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities_PLAN_12-10-26.md`
2. Last completed step: PLAN written 12-10-26 on main `881a2fd`; PVL cycle 1 CONDITIONAL (F1-F12), cycle 2 folded them, cycle 3 PASS (results.tsv rows 1-3); no code touched.
3. Validate-contract status: stamped PASS 12-10-26 (PVL cycle 3; section Validate Contract above; goal block after it).
4. Context loaded: CLAUDE.md, research report `s9-research.md`, realignment SPEC lines cited above, batch 3 plan shape, real code in `api/` and `web/` as cited.
5. Next step: the user's "ENTER EXECUTE MODE" (P-S9-1 is optional before A-D); the planner re-counts the baselines, checks MASTER-PLAN spend, writes the S9A envelope and spawns one worker (opus). Re-validate with `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <plan-path>`.

## Envelope line ranges (re-derive with `grep -n '^## \|^### '` at spawn time; worker cap 36,000 B = CLAUDE.md 13,443 + envelope cap 8,000 + plan ranges, so ranges stay at or under 14,557 B)

Line numbers refer to this file as saved. Every range ends before the Validate Contract, so the contract, goal block and this table move no range line; if any earlier line is edited, re-derive the numbers with the grep named in the heading and recount bytes (each line plus its newline), keeping edits inside a range byte-neutral. Common = line 11 and lines 30-66. The criteria header and rows (155-186) are left out of every set: PVL and the tester use them and each slice section names its ACs. Command lines: 242-250 (heading, fence, FORBIDDEN, FIXTURES, S-secret) plus the slice's own scope pair (A 251-252, B 253-254, C 255-256, D 257-258, E 259-260), the words pair 261-262, the utc and nostore pairs 263-266 (web slices), the clock pair 267-268 (C, E) and the closing fence 269.

| Slice | Plan ranges (lines) | Plan bytes | Envelope room (cap 36,000 - 13,443 - plan bytes) |
|---|---|---|---|
| S9A | 11, 30-66, 81-98, 242-252, 261-262, 269 | 14500 | 8057 |
| S9B | 11, 30-66, 99-107, 242-250, 253-254, 261-262, 269 | 10302 | 12255 |
| S9C | 11, 30-66, 108-122, 242-250, 255-256, 261-269 | 13789 | 8768 |
| S9D | 11, 30-66, 123-132, 242-250, 257-258, 261-266, 269 | 11831 | 10726 |
| S9E | 11, 30-66, 67-80, 133-142, 242-250, 259-260, 261-269 | 14403 | 8154 |

Every row leaves at least 8,000 B for the envelope, so an envelope may use its full cap (a realistic one is 2-3 KB). S9A and S9E have the least room (A1 in the Validate Contract).
