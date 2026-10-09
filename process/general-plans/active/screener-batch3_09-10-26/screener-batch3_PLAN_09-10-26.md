---
name: plan:screener-batch3
description: "Screener realignment batch 3 (slice S5 split in two): S5a layout file API, 30-coin cap, RSI numbers and TS mirrors; S5b layout UI (groups, reorder buttons, move-to-group menu, add/remove coins), RSI on coin boxes and drill-down, spaghetti toggle persistence (AC-22). Sequential S5a then S5b; S9, S10 are later"
date: 09-10-26
feature: general-plans
---

# Screener Batch 3: Layout, Groups, 30-Coin Cap, RSI and Toggle Persistence (S5a, S5b)

Date: 09-10-26
Status: PLANNED, validate-contract PENDING (PVL not run). Code read at origin/main `270f9ac` (`abda8e7` adds process docs only). Open questions for the user: Q1 and Q2 only (see "Open questions for the user"). Hardened 09-10-26: every claim below was re-checked against the code, and the baselines were re-run (pytest 951 passed, 2 skipped, 5 deselected in 200 s; vitest 251 in 34 files; tsc 0; build:islands 0; `playwright test --list` 65 tests in 6 files; `test_main_cors.py` 10 passed).
Folder index: this plan; PVL reports `screener-batch3-pvl-iteration-NNN_REPORT_<dd-mm-yy>.md` and `results.tsv` (written by VALIDATE); envelopes `screener-batch3-s{5a,5b}_REF_<dd-mm-yy>.md` and slice reports `screener-batch3-s{5a,5b}_REPORT_<dd-mm-yy>.md` (written by the planner and workers).
Complexity: COMPLEX (S5a then S5b, strictly sequential; RT3 response models, a new personal-data file, a public API surface, the shared board component)

**TL;DR:** The screener gets saved groups, ordering, a 30-coin cap, RSI on every coin box and in the drill-down, and spaghetti toggles that survive a reload. The saved layout lives in one server file `api/data/layout.json` (git-ignored, written atomically); the coin list stays in `watchlist.json`. S5 is split in two: S5a (API, file, cap, RSI numbers; 19 file touches) then S5b (web UI; 28 touches). The 100-touch rule alone would keep it one slice (47 touches); the worker read cap forces the split (see "S5 split evidence"). The web has no add/remove coin UI today, so S5b builds it (the cap needs it). Estimate 9.5-13.5 USD [estimate] for both (tester runs included), not the 3-6 USD of the INNOVATE table. Every e2e gate must run before any merge.

Sources: SPEC `personal-tracker-realignment_SPEC_02-10-26.md` (D1-D11, AC-3..8, AC-22, AC-23, AC-26), INNOVATE `..._INNOVATE_03-10-26.md` (area G, slice S5), decisions.md D-2, D-3, D-14; backlog `spaghetti-toggle-persistence_NOTE_09-10-26.md`; batch 1 and 2 plans, reports and PVL iterations; `process/context/{current-state,architecture,operating-instructions}.md`; `process/context/tests/all-tests.md` (Standing Lessons 3, 7, 10, 11); real code at origin/main `270f9ac`. Router: `process/context/all-context.md`.

Context Envelope: general-plans | PLAN | batch 3 (S5) | claude/pensive-albattani-ou0cgv | /home/user/psychic-train | tests | api/, web/ | this file | pytest then vitest then playwright | contract PENDING.

## Overview

Goal: a screener the user can arrange and trust: groups, order and hidden chart lines persist on the server; the board holds at most 30 coins (existing extras kept, new adds blocked); every box and the drill-down show RSI(14, Wilder) as plain numbers; coins can be added and removed from the page. User decisions (binding): server file, no second storage system; buttons plus a move-to-group menu, no drag-and-drop; cap 30; drill-down keeps price plus RSI chart; page refresh stays cached-first; data only, no verdicts. Non-goals: equities page (S9; the layout API has a section slot for it), scheduled task (S10), group sort (Q1), drag-and-drop, a Reset-layout button, RSI/price zoom sync, any change to `deploy/**`, `api/scripts/**`, `api/tests/deploy/**`, `lse_adapter.py`, `equities_store.py`, `cache.py`, `ccxt_adapter.py`, `freshness.py`, `refresh_worker.py`, the chart island.

## Name check against INNOVATE / SPEC / reports (real code read 09-10-26)

| INNOVATE / SPEC / report says | Actual code | Plan consequence |
|---|---|---|
| G: "GET/PUT whole document" | `api/main.py::_cors_options` allows GET, POST, DELETE and `test_main_cors.py:95` pins exactly that set | save with `POST /api/layout/{section}` (C4); CORS untouched |
| G: file `{version, groups, hidden_lines}` | no layout code exists; equities (S9) must fit later | sectioned file with revision (C2) |
| US-4 / AC-6: add and remove coins "from the UI" | `api/routers/watchlist.py` exists; `grep api/watchlist web/` finds no client and no UI | S5b builds the add/remove UI; the cap is unreachable without it |
| D8 / AC-26: cap 30, keep extras, block new | `watchlist.add_coin` has no cap; 31 adds stored 31; an empty symbol is stored as `""` (red-today) | cap and symbol validation in the store (C5) |
| AC-3 RSI under each coin | `compute_rsi` exists (`rsi.py`); neither `CoinPanel` nor `ChartSeries` carries RSI | RSI reading and series (C6) |
| AC-22 / backlog note: toggles persist, S5 chooses storage | toggles are `SpaghettiChart` memory state (`hidden` set) | `hidden_lines` in the layout file (C2) |
| AC-7 drag-and-drop, AC-8 group sort | user decision 09-10-26: buttons plus menu, no drag | drag clause superseded by the user; sort is Q1 |
| INNOVATE S5 files: `watchlist.py`, `layout.py`, `ScreenerBoard`, `CoinPanel` | the work touches 47 files in two surfaces | two slices (C1) |
| Seeded e2e data | `seed_e2e_cache.py::_bars` rises strictly, so seeded RSI is 100.0 on every coin and timeframe; THIN has 20 bars | e2e proves wiring and the N/A path, not the number |
| e2e test 1 counts `screener-board-grid > div` | groups become the direct children | listed edit (S5b table) |
| Gate command `pnpm --filter web ...` | prints "No projects matched the filters" here (T39 report) | gates run inside `web/` |
| Global CSS `.app-main [role="group"]` | makes any `role="group"` an inline-flex bordered segmented control | group sections are `<section>`, never `role="group"` |
| `test_fresh_deploy_degrade.py` runs `importlib.reload(watchlist_store)` twice and walks the board JSON for NaN and inf | `tests/deploy` runs before `tests/routers`, so an exception class imported by name into a router is stale in a later test (a 409 would surface as a 500); a NaN RSI would fail the walk | classes are used as `watchlist_store.<Name>` only; RSI skips NaN and inf (S5a design 1 and 5) |
| e2e test 5 asserts `getByRole("heading", { name: "Screener" })` (substring match) | a second heading containing "Screener" makes it ambiguous | no new heading contains "Screener" (gate convention 10) |
| the layout holds `hidden_lines` as an array, `SpaghettiChart` uses a Set | a fresh Set per render changes `lines` and re-mounts the island (zoom and pan lost) | U5 memoises the Set |

## Decisions locked for this batch

- **C1 Two slices, sequential.** S5a = API, layout file, cap, RSI numbers, TS mirrors. S5b = web UI, add/remove UI, RSI display, toggle persistence. S5b branches from `main` after the S5a merge. Reason: worker read cap.
- **C2 Layout store.** `api/data/layout.json`: `{"version":1,"sections":{"crypto":{"revision":N,"saved_at":"<Z>","groups":[{"id","name","coins"}],"hidden_lines":[...]}}}`. Path: env `SCREENER_LAYOUT_PATH`, else the sibling `layout.json` of the watchlist path, resolved at CALL time (never a default argument; Standing Lesson 3), so every test and the seeded e2e that redirect the watchlist also redirect the layout. Git-ignored. Atomic write: temp file in the same directory (prefix `.layout.json.`, suffix `.tmp`), flush, fsync, `os.replace`, under one process lock; no in-memory cache. A read never writes. Unreadable JSON, wrong shape or `version != 1` reads as the default with `source:"recovered"`; the next save first renames the file to `layout.json.bad`. A missing file or section reads as the default (`source:"default"`). Unknown sections survive a save (S9 adds `equities`). Sections are a registry: `crypto` now (members = the watchlist, cap 30, references BTC and HYPE); any other name is 404. `hidden_lines` persist the spaghetti toggles (AC-22), BTC and HYPE included.
- **C3 Membership truth stays `watchlist.json`** (worker, scripts, seed and board read it); the layout holds grouping, order and hidden lines. Reconcile (every read and after every save): coins off the watchlist are dropped; watchlist coins in no group go to the LAST group (a group `main` named `Main` is made if there is none); `hidden_lines` keep BTC, HYPE and current members only. `POST /api/watchlist` with a `group_id` places the new coin there and saves the layout even when no file exists yet (the default layout is saved with the coin moved); no or unknown `group_id`: reconcile puts it in the last group; `DELETE /api/watchlist/{symbol}` drops the coin from the groups and `hidden_lines` (BTC and HYPE stay hidden) only when a layout file exists. Both bump the layout revision when they write, so the web refetches the layout after every add or remove. A layout failure is logged and never fails the add or remove. No guarantee spans the two files at once.
- **C4 Layout API.** `GET`, `POST`, `DELETE /api/layout/crypto`. `POST` body `{revision, groups, hidden_lines}`; `revision` must equal the stored one (0 for the default) else 409 `layout changed elsewhere`; success stores revision+1 and returns the reconciled `Layout`. 422: no group, more than 12, ids not `^[a-z0-9][a-z0-9-]{0,39}$` or repeated, names (trimmed) not 1-40 chars or repeated ignoring case, a coin in two groups; unknown coins are dropped, not an error. `DELETE` removes the file, returns the default, is idempotent. `Layout` = `{version, section, revision, saved_at (Z or null), source, groups, hidden_lines}`.
- **C5 Cap and symbols.** `MAX_COINS = 30` in `watchlist.py`. A NEW symbol is refused with HTTP 409 and `detail` exactly `Screener is full: 30 coins maximum. Remove a coin to add another.` (this string appears once in `watchlist.py` and once in `web/lib/layout-state.ts`; comments must not repeat it) when the list holds 30 or more; an existing symbol is a no-op 200; a file already over 30 is kept; removal works at any size; adds unblock only below 30. Symbols are stripped, upper-cased and must match `^[A-Z0-9][A-Z0-9._-]{0,14}$` else 422. `POST /api/watchlist` gains optional `group_id`; its response stays `{"coins": [...]}` (`test_watchlist.py` pins it).
- **C6 RSI.** RSI(14, Wilder) from the unchanged `compute_rsi`, on the displayed timeframe's own frame (1w: the derived weekly frame), forming candle included (the chart's `is_partial` says so). One availability rule: RSI exists iff the frame has at least 60 bars (the chart's rule, `sma.SMA_LENGTH`) and the last value is defined; otherwise `value=None` with the chart's reason (`insufficient-history`, `bad-symbol`, `source-unavailable`) or `flat-price` (60+ bars with no price change give no defined RSI; verified). `CoinPanel.rsi: RsiReading {value, length=14, as_of (last bar, Z), reason}` (default all-None); `ChartSeries.rsi` (default `[]`) is filled only by `build_chart_view` (board charts keep `[]`) with Z timestamps (price and SMA keep their format). Web shows one decimal; no 30/70 lines and no overbought or oversold wording.
- **C7 Gate facts.** Seeded bars rise strictly, so seeded RSI is 100.0 for BTC, ETH and HYPE on every timeframe and THIN (20 bars) is N/A; seeded watchlist is `[BTC, ETH, THIN]`, the seeder (forbidden) never writes a layout; per-timeframe RSI numbers are proven by pytest with non-monotone frames.

## Gate conventions (all slices; batch-1 and batch-2 conventions kept)

1. Every pytest gate runs with `UV_FROZEN=1`. No slice edits a fixture (`FIXTURES` prints nothing).
2. Baselines at `270f9ac` (re-record at spawn): pytest 951 passed/2 skipped/5 deselected/0 xfailed; vitest 251 in 34 files; tsc 0; islands 0; e2e screener 10 + contrast 7 (full suite 65 in 6 files). A count that differs from the plan arithmetic stops the worker at `needs_input`. New tests are plain functions (no `it.each`, no parametrize).
3. Web gates run inside `web/` (`pnpm --filter web` fails here with "No projects matched the filters"). Log each gate run in heading 6 with SHA and UTC time.
4. Seeded e2e (CI does NOT run Playwright): `cd web && SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e <specs>` (no `--`). REQUIRED on the head SHA before any merge; NOT-RUN stops at `needs_input`, no merge. Never merge with an open `needs_input` or `blocker` in heading 9 (PR #40).
5. Red-first: write the slice's new tests as stubs, run the first gate on the untouched base, record the red run in heading 6, then write the real tests.
6. Hidden-break rule: an existing test may be edited only as listed in the slice's table; any other failing existing test stops the worker at `needs_input`.
7. Workers branch from `main`; max 2 fix cycles per gate, the same failure twice stops. A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` stops at `review`; no slice touches `deploy/**`, `api/scripts/**`, `api/tests/deploy/**`.
8. `git diff --check` exits 0; ASCII only in plan and report files. Live providers, phones and real displays are probes (P-*), never claimed by a worker. Known-Gap is a residual (backlog stub, gate stays CONDITIONAL), never a PASS.
9. Personal data: tests never touch the real `api/data/layout.json` or `watchlist.json`. Every new test that can reach them has a module-level autouse fixture redirecting `watchlist_store.DEFAULT_WATCHLIST_PATH` to `tmp_path` (the layout follows it); the `REAL-DATA` command proves no real file was created or changed on the machine that ran the gates.
10. Gate-trap rules: new files must not contain any token of `api/tests/analytics/test_no_verdict_symbols.py::TOKENS` (for example `leg_context`, `fetchScalp`); no new testid starts with `coin-panel-` (e2e counts that prefix); no new container uses `role="group"`; no new heading contains `Screener` (e2e test 5 matches headings by substring); UI copy must not contain `Momentum`, `Trend`, `Benchmark`, `Confidence` or `Narrative` (`ScreenerBoard.test.tsx` asserts their absence); no browser storage, cookies or drag attributes (`S5b-nostore`).

## S5 split evidence and sequencing

Touches: S5a 19 (9 api source/config incl. `.gitignore`, 2 TS mirrors, 4 new pytest files, 3 edited test files, 1 report); S5b 28 (14 web source incl. `globals.css`, 8 new test files, 4 edited test files, 1 backlog stub, 1 report); total 47, under the 100 split threshold. The split is forced by the worker read cap (36,000 B = CLAUDE.md 13,443 + envelope + plan ranges): the sub-range table (last block) holds S5a at 19,612 B and S5b at 20,124 B of plan ranges against 22,557 B (36,000 - 13,443) less the envelope, and the union of both sets is 34,271 B, 11,714 B over the cap even with a zero-byte envelope, so one worker cannot read one combined slice. The split also gives two proof boundaries: the API contract and the personal-data file are proven by pytest and contract tests before any UI exists, and the UI e2e then runs against a merged API. Sequencing: S5a, merge, S5b, merge; never parallel (S5b imports the S5a types and routes). S9 starts only after the S5b merge. R12 (deploy fixes) is file-disjoint: it edits `deploy/**` and `api/tests/deploy/**` only and merely reads `.gitignore`; S5a owns `.gitignore` (three lines) while it runs. Touch counts were re-counted from the owned lists on 09-10-26: S5a 9 + 2 + 4 + 3 + 1 = 19, S5b 14 + 8 + 4 + 2 = 28.

## Program budget and costs

Programme ceiling 60 USD (user, 09-10-26); spent 34.73 USD; 25.27 USD remain. Comparable slices cost T32 5.58, T34 4.99, T35 4.15, T36 5.44, T37 4.97, T38 4.75 USD (worker spend only; the registry does not meter tester runs, so the tester line below is an addition).

| Slice | Worker (opus) | Subagents (sonnet) | EVL tester | Total [estimate] | Basis |
|---|---|---|---|---|---|
| S5a | 3-4.5 | 0.3-0.5 | 0.5 | 4-5.5 | 19 touches, 45 new pytest, 2 full pytest runs (3.5 min each), e2e twice, 130 tool calls |
| S5b | 4.5-6.5 | 0.5-1 | 0.5 | 5.5-8 | 28 touches, 65 new vitest, 7 e2e, global CSS, 2 full runs, e2e three times, 180 tool calls; the largest UI slice so far |
| S5 | | | | 9.5-13.5 | against the INNOVATE 3-6 (see Q2) |

After S5, 12-16 USD remain for S9 (1-4) and S10 (3-8). All three at their top figure would total 25.5 USD, 0.2 over the 25.27 left; S10 (RT4, waits on R12) is the least certain figure, so re-check before the S10 spawn. Stop and ask above 15 USD for one slice or 60 USD in total; re-check before each spawn.

## S5a: layout file API, 30-coin cap, RSI numbers, TS mirrors (RT3, capped subagent lane: yes)

**Goal:** the server stores and serves a layout, refuses a 31st coin, validates symbols, and every board panel and chart view carries RSI numbers; the TS mirrors match. No UI change. Starts from `main` at the plan merge.

**Owned (exact):** `api/data/{layout,watchlist}.py`, `api/models/{layout,screener}.py`, `api/routers/{layout,watchlist}.py`, `api/analytics/screener_board.py`, `api/main.py` (router include and one comment), `.gitignore` (three lines: `api/data/layout.json`, `api/data/layout.json.bad`, `api/data/.layout.json.*.tmp`); `web/lib/types/{screener,layout}.ts`; new tests `api/tests/data/test_layout_store.py`, `api/tests/routers/{test_layout,test_watchlist_cap,test_screener_rsi}.py`; edited `api/tests/routers/test_screener_no_verdict_contract.py`, `web/components/screener/__tests__/{ScreenerBoard,DrillDownView}.test.tsx`; report `screener-batch3-s5a_REPORT_<dd-mm-yy>.md` (`layout.py`, `models/layout.py`, `routers/layout.py`, `layout.ts` are new).
**Forbidden:** the FORBIDDEN list (command block), every other web file, S5b files.

**Design:**
1. `watchlist.py` (C5): `MAX_COINS`, `CAP_MESSAGE`, `SYMBOL_RE`, `WatchlistFullError`, `InvalidSymbolError`, `normalize_symbol`; `add_coin(symbol, path=None)` keeps its signature and return, normalizes, refuses a new symbol at 30 or more; `remove_coin` unchanged; `_save_raw` untouched (the watchlist write stays non-atomic; see Test Infra notes). Every exception class and constant is used as `watchlist_store.<Name>` (module attribute at call time), never imported by name: `api/tests/deploy/test_fresh_deploy_degrade.py` reloads the module, and `tests/deploy` runs before `tests/routers`, so a class imported by name would be stale in a later test.
2. `models/layout.py` (C2, C4): `LayoutGroup`, `Layout`, `LayoutUpdate`, `LayoutSource`, `MAX_GROUPS = 12`, `MAX_GROUP_NAME = 40`. `data/layout.py`: `layout_path()`, `read_layout(section)`, `save_layout(section, update)`, `reset_layout(section)`, `place_coin(section, symbol, group_id)`, `drop_coin(section, symbol)`, errors `UnknownSectionError`, `StaleRevisionError`, `InvalidLayoutError`; it reads the watchlist through `watchlist_store.read_watchlist()` at call time (tests monkeypatch it); `REFERENCE_SYMBOLS = ("BTC", "HYPE")`; the atomic write is a local helper in the `equities_store._write` pattern (copied, not imported: that file is forbidden); `saved_at` is `freshness.iso_z` of a patchable clock.
3. `routers/layout.py`, `main.py`: `GET`, `POST`, `DELETE /api/layout/{section}`; 404 unknown section, 409 `StaleRevisionError` (detail `layout changed elsewhere`), 422 `InvalidLayoutError`. `main.py` only includes the router and corrects the comment "serves only GET plus the watchlist's POST/DELETE"; `_cors_options` is not edited.
4. `routers/watchlist.py`: 409 with `CAP_MESSAGE`, 422 for an invalid symbol, optional `group_id`; `place_coin` only for a new coin with a `group_id`, `drop_coin` only after a successful remove, each in try/except with a logged warning; response models unchanged.
5. `models/screener.py`: `RsiReason`, `RsiReading`, `ChartSeries.rsi`, `CoinPanel.rsi`. `screener_board.py`: `_rsi_reading(df, available, status)` and an RSI series builder (Z timestamps via `freshness.iso_z`); `build_coin_panel` fills `rsi` from the displayed frame; `build_chart_view` also fills `chart.rsi`. `rsi.py` and `compute_rsi` are not edited. A non-finite RSI (NaN or inf) becomes `value=None` and the series builder skips undefined points, so the board JSON never carries NaN (`test_fresh_deploy_degrade.py` walks it).
6. TS mirrors: `screener.ts` gets `RsiReason`, `RsiReading`, `ChartSeries.rsi`, `CoinPanel.rsi`; `layout.ts` gets `LayoutSource`, `LayoutGroup`, `Layout`, `LayoutUpdate`; fields one per line, each interface closed by a line `}` at column 0 (the contract tests parse them).
7. Tests as listed; run `REAL-DATA` around the full pytest run.

**Existing tests that break (exact edits allowed):**

| Test | Why | Edit |
|---|---|---|
| `test_screener_no_verdict_contract.py:77` `test_coin_panel_has_no_verdict_fields` | asserts the exact payload key set | add `"rsi"` |
| `ScreenerBoard.test.tsx` `makeCoin` (tsc only) | `CoinPanel.rsi` is required, so `makeBoard(tf, coins)` fails to type-check | add `rsi: { value: 61.3, length: 14, as_of: null, reason: null }` to the object `makeCoin` returns |
| `ScreenerBoard.test.tsx` `NO_FRESHNESS`, lines 168-169 (tsc only) | `ChartSeries.rsi` is required; `NO_FRESHNESS` is spread into every chart literal, 168-169 spread `freshness` | add `rsi: []` to `NO_FRESHNESS` and to the two inline literals |
| `DrillDownView.test.tsx` `NO_FRESHNESS` (tsc only) | same | add `rsi: []` (every chart literal in the file spreads it) |
| stay green unedited | pinned shapes | `test_watchlist.py` (`{"coins": [...]}`), `test_watchlist_store.py`, `test_board_integration.py` and `tests/scripts/test_refresh_cache.py` (valid symbols only), `test_main_cors.py` (10 tests, GET/POST/DELETE), `test_screener_freshness_payload.py` and `test_screener_gain_contract.py` (`ChartSeries` and `CoinPanel` names and nullability against `screener.ts`: `rsi` defaults to a non-null value, so the TS fields carry no `\| null`), `test_spaghetti.py`, `test_no_verdict_symbols.py` (its `screener.ts` scan bans the word `confidence`, so the new TS lines avoid it), regime tests, `api/tests/deploy/**` (`test_fresh_deploy_degrade.py` reloads `watchlist_store` and walks the board JSON for NaN) |

**Tests (45; plain functions; the worker chooses snake_case names that state the behaviour):**
- `test_layout_store.py` (15): default is one `main` group in watchlist order; a read of a missing file creates nothing; save round trip (revision+1, `saved_at` Z); stale revision refused, file unchanged; reconcile drops coins off the watchlist; reconcile appends unplaced coins to the last group; save drops unknown coins; save rejects a coin in two groups and bad shapes (no group, empty or 41-char name, bad id); save rejects duplicate names (any case) and a 13th group; hidden lines keep BTC/HYPE and drop removed coins, `REFERENCE_SYMBOLS` equals `screener_board.SPAGHETTI_REFERENCES`; interrupted write keeps the old file and leaves no temp file; corrupt or `version != 1` file reads as `recovered` default and is renamed `.bad` on the next save; unknown sections survive a save; path follows the watchlist path and the env override wins; unknown section name refused.
- `test_layout.py` (10): GET default for the current watchlist; GET never writes; POST then GET (revision+1, `source` file); stale POST 409, file unchanged; invalid bodies 422 (duplicate coin, no groups, bad id); unknown section 404 on GET, POST, DELETE; DELETE resets and is idempotent; `saved_at` is Z; `Layout`, `LayoutGroup`, `LayoutUpdate` match `layout.ts` (names, types, nullability); `/api/layout` routes use only GET, POST, DELETE.
- `test_watchlist_cap.py` (11): 30 accepted and the 31st refused 409 with the exact message; a refusal leaves watchlist and layout unchanged; removing one at 30 allows exactly one add; re-adding an existing coin at 30 is a no-op 200; a file already over 30 is kept and new adds blocked; from 32, removing to 30 still blocks and 29 allows; invalid symbols (empty, spaces, 16 chars, `!`) 422 and nothing stored; add with `group_id` places in that group, with a saved layout and with no file yet (the file is then created); remove drops the coin from groups and hidden lines but keeps a hidden BTC; a failing layout write does not fail the add; store-level `add_coin` enforces cap and validation.
- `test_screener_rsi.py` (9): board RSI equals an independent loop-based Wilder reference (copied into the file; non-monotone closes); each timeframe gets its own value; short history and failed sources give null value plus reason, never 0 or NaN; a flat window gives `flat-price`; `as_of` is the last bar in Z; chart view carries the RSI series and board charts carry `[]`; series points are Z and the last point equals the reading; the 60-bar rule matches the chart's; `RsiReading` matches `screener.ts`.

**Gates and probe:** "S5a exact gates" (G-S5a-1..12, P-S5a-1). Reds on the untouched base: all 45 new tests (stubs).
**Lane:** capped lane yes: one read-only reviewer (Python/TS lockstep, atomic write, reconcile, CORS untouched), tester at EVL. **Budget [estimate]:** 130 tool calls, 100 minutes, 4 CI polls, 4-5.5 USD, 2 full pytest runs, e2e twice.

**Risks:** (1) a test that reaches the real `api/data/layout.json` is a data-loss bug: autouse redirect plus `REAL-DATA`. (2) `screener_board.py` edits must not change existing chart, chip or spaghetti output: those tests stay unedited. (3) Windows `os.replace` fails if another program holds `layout.json` open: the save returns 500 and the UI rolls back (P-S5b-1). (4) The cap lives in the store, so any future caller gets it.

**Rollback:** revert the PR; `layout.json` is only created by a save, delete it by hand.

## S5b: layout UI, add/remove coins, RSI display, toggle persistence (RT3, capped subagent lane: yes)

**Goal:** groups in saved order with reorder buttons, a move-to-group menu, group create/rename/delete, add/remove coin, RSI on every box and in the drill-down, persistent spaghetti toggles; clear loading, empty and error states; no panel reordering or space jumps caused by this slice (page-level layout shift is not measured). Starts after the S5a merge (merge SHA = base).

**Owned (exact):** `web/components/screener/{ScreenerBoard,CoinPanel,DrillDownView,SpaghettiChart}.tsx`; new `web/components/screener/{CoinGroup,AddCoinForm,CoinActions,RsiChart}.tsx`, `web/lib/{layout-state,rsi-format,use-board-layout}.ts`, `web/lib/api/{layout,watchlist}.ts`; `web/app/globals.css`; new tests `web/lib/__tests__/{layout-state,rsi-format,layout-api}.test.ts`, `web/components/screener/__tests__/{CoinActions,AddCoinForm,ScreenerBoardLayout,CoinPanel}.test.tsx`, `web/e2e/layout.spec.ts`; edited `web/components/screener/__tests__/{ScreenerBoard,DrillDownView,SpaghettiChart}.test.tsx`, `web/e2e/screener.spec.ts` (test 1); backlog stub `process/general-plans/backlog/screener-ondemand-states-contrast_NOTE_<dd-mm-yy>.md`; report `screener-batch3-s5b_REPORT_<dd-mm-yy>.md`.
**Forbidden:** FORBIDDEN list, `api/**`, `web/lib/types/*` (S5a mirrors; a missing field stops the worker at `needs_input`), `web/islands/**`, `web/lib/{chart-viewport,island-loader,spaghetti-lines}.ts`, `web/app/screener/page.tsx`, S5a files.

**UI rules (locked):**
- **U1 Structure.** Groups are `<section aria-labelledby>` (never `role="group"`): `h2` name, coin count, Rename, Move group up/down, Delete group; coins in a grid per group; `screener-board-grid` stays on the groups container. Coin actions (a `CoinPanel` `actions` slot): Move earlier, Move later, a native `<select>` "Move to group", Remove with inline Confirm/Cancel. Edge buttons use `aria-disabled="true"` (not `disabled`: focus stays) and do nothing. After a move the same control is refocused and the polite live region `board-announcer` states the result; after a Confirm-remove or a group delete focus moves to the heading (`tabIndex={-1}`) of the group that holds the coin or received the coins; after an add focus stays in the cleared input. Rename and New group use an inline text input (Enter saves, Escape cancels, errors in `role="alert"`). Accessible names include the coin or group. Deleting a group moves its coins to the previous group (next if first); the last group cannot be deleted; names unique ignoring case, 1-40 chars; at most 12 groups.
- **U2 Loading and shift.** Panels render only after BOTH board and layout settled (fixed-height `board-loading` skeleton, `aria-busy`); the RSI row is always rendered (same height for a number and N/A); the status region (`layout-notice`, `layout-save-error`) exists from first render. Layout load failure: one default group, a notice, Retry, editing controls `aria-disabled`. `recovered`: its own notice. Empty watchlist: `board-empty` plus the add form. Board failure: `board-error`, no groups.
- **U3 Save.** Optimistic, serial queue, each save carries the last revision; failure rolls back and shows `layout-save-error`; 409 refetches the layout and shows "Layout changed elsewhere; reloaded."
- **U4 Add and remove.** Add form: symbol input, group select (default last), "Add coin", `coin-count` text `n / 30 coins`. At 30 or more the button is `aria-disabled` and the full message (C5) shows permanently; a click shows it and sends nothing; a 409, 422 or network error shows in `role="alert"`. After a successful add or Confirm-remove, board, layout and spaghetti are refetched; while the new coin's chart is unavailable the board is refetched at +4 s and +12 s (at most twice).
- **U5 Toggles (AC-22).** `SpaghettiChart` takes optional `hidden`, `onToggle`, `reloadToken`: given `hidden` it is controlled (otherwise in-memory as today; its 6 tests stay unedited); a changed `reloadToken` refetches, so an added or removed coin appears or goes at once (AC-23). The board passes `layout.hidden_lines` (`hidden?: readonly string[]`), saves on toggle, bumps the token after every add or remove. The board builds its list once per layout change (`useMemo`) and `SpaghettiChart` keys its own Set on the joined list, so an equal list never changes `lines` and never re-mounts the island (zoom and pan are kept); the reviewer checks this because jsdom never mounts the island. Closes AC-S6-6.

**Design:**
1. `web/lib/api/layout.ts`: `fetchLayout()`, `saveLayout(update)` (POST JSON), `LayoutConflictError` on 409, 10 s timeout like `getJson`. `web/lib/api/watchlist.ts`: `addCoin(symbol, groupId?)`, `removeCoin(symbol)`, `WatchlistFullError` (server `detail`), `InvalidSymbolError` (422), else an Error naming the status.
2. `layout-state.ts` (pure): `arrange` (mirrors the server reconcile: drop symbols not on the board, append unplaced coins to the last group, make `Main` if no group), `moveCoin`, `moveCoinToGroup`, `addGroup`, `renameGroup`, `deleteGroup`, `moveGroup`, `toggleLine`, `validateGroupName`, `isFull`, `MAX_COINS`, `CAP_MESSAGE` (the C5 string); id generator injectable. `rsi-format.ts`: one decimal, reason copy, UTC title. `use-board-layout.ts`: U2, U3, announcer text. The `Layout` shape is in `web/lib/types/layout.ts` (S5a).
3. `ScreenerBoard.tsx`: injectable props `fetchLayout`, `saveLayout`, `addCoin`, `removeCoin` (defaults: the real clients); a timeframe change refetches the board only.
4. `CoinPanel.tsx`: RSI row `rsi-readout-<SYM>` between the freshness caption and the chips (label `RSI 14`, one decimal or `N/A` with the reason as `title`; reasons `insufficient-history`, `bad-symbol`, `source-unavailable`, `flat-price`; `aria-label` names the timeframe; no 30/70 lines, no overbought or oversold wording) and an optional `actions` slot in the header; existing testids and classes unchanged. `DrillDownView.tsx`: below the price chart `RsiChart` (`drilldown-rsi-chart`, one series, island `mountSimpleLines`) and `drilldown-rsi-value`; an available chart with an empty RSI series shows `drilldown-rsi-na` ("RSI 14: N/A, price did not change in this window"); an unavailable chart shows only the existing notice. Price and RSI zoom independently.
5. `globals.css`: tokens only; classes for groups, actions, add form, notices, skeleton, RSI row, `.visually-hidden`; `[aria-disabled="true"]` keeps the text colour (no opacity), dashed border, `cursor: not-allowed`; `:focus-visible` outline as `.spaghetti-chart__toggle`; inputs and selects coloured with tokens (no system colours); RSI row and status region have `min-height`. A contrast failure is fixed with existing tokens, never by exempting text.

**Existing tests that break (exact edits allowed):**

| Test | Why | Edit |
|---|---|---|
| `ScreenerBoard.test.tsx` (9 renders) | the board now also calls `fetchLayout` (default: a real fetch) | add one stub const next to `fetchSpaghetti` (revision 0, one group `main`, no coins; the board appends unplaced coins) and pass `fetchLayout={fetchLayoutStub}` in all 9 `render(<ScreenerBoard ...>)` calls |
| `screener.spec.ts` test 1 | `screener-board-grid > div` now counts group sections | count `[data-testid^="coin-panel-"]` inside the grid, expect `manifest.watchlist.length` |

**Tests (65 vitest + 7 Playwright; plain functions; the worker chooses names that state the behaviour):**
- `layout-state.test.ts` (12): arrange drops unknown and appends unplaced to the last group; arrange makes `Main` when no group; move earlier/later; edge move is a no-op; move to group; add group (trims; rejects empty, duplicate in any case, 13th, 41 chars); rename; delete (coins go to the previous group, next if first); last group undeletable; move group clamps; toggle line; `isFull` at 30 and over, exact `CAP_MESSAGE`.
- `rsi-format.test.ts` (4): one decimal (61.34 gives `61.3`, 100 gives `100.0`); copy for each reason; null is `N/A`, never `0` or `NaN`; title has the UTC time.
- `layout-api.test.ts` (7): fetch URL and parse; save POSTs JSON with the revision; 409 gives `LayoutConflictError`; other failure names the status; `addCoin` 409 gives `WatchlistFullError` with the server text; 422 gives `InvalidSymbolError`; `removeCoin` DELETE, encoded symbol.
- `CoinActions.test.tsx` (7): names include coin and group; edge buttons `aria-disabled`, clicks do nothing; clicks call `onMove(-1)`, `onMove(1)`; select lists all groups, change calls `onMoveToGroup`; only Confirm calls `onRemove`; Escape cancels and refocuses Remove; buttons are native (Enter and Space click).
- `AddCoinForm.test.tsx` (9): labelled input, select, button; submit trims and upper-cases; empty input gives an inline error, no request; at 30 the full message shows, button `aria-disabled`, click sends nothing; server 409 text in `role="alert"`; 422 message; network error message; success clears the input, calls `onAdded`; pending blocks a second submit.
- `ScreenerBoardLayout.test.tsx` (15): no panel until board and layout both resolve; groups in layout order with headings, counts, empty-group message; coin order follows the layout; layout failure (default group, notice, disabled controls, Retry); recovered notice; move earlier saves with the current revision, reorders, announces; failed save rolls back with `layout-save-error`; 409 refetches and notices; create, rename (validation message), delete a group; move to group by select; remove after Confirm refetches board, layout, spaghetti; add does the same and retries the board at 4 s and 12 s while the new coin is unavailable (fake timers); a spaghetti toggle saves `hidden_lines`, initial hidden comes from the layout, count text updates; empty watchlist shows `board-empty` and the form; board failure shows `board-error`, no groups.
- `CoinPanel.test.tsx` (5): RSI row shows `RSI 14` and the value; N/A carries the reason as title; row present for an unavailable chart; `aria-label` names the timeframe; the actions slot renders.
- `DrillDownView.test.tsx` (+3): RSI chart and value render; empty RSI series on an available chart shows `drilldown-rsi-na`; value equals the last RSI point. `SpaghettiChart.test.tsx` (+3): controlled `hidden` sets `aria-pressed`; `onToggle` gets the symbol, local state unchanged; a changed `reloadToken` refetches.
- Playwright `layout.spec.ts` (hybrid, 7; `afterEach` removes every watchlist symbol, re-adds the manifest symbols in order, calls `DELETE /api/layout/crypto`; groups found by `getByRole("region", { name })`): (1) RSI on every box equals the API value, THIN is N/A with a reason, RSI rows of BTC and THIN have equal height, drill-down shows RSI chart and value; (2) reorder with buttons, reload keeps the order, Enter on a focused button keeps focus on it; (3) create a group, rename it, move ETH into it by menu, reload, delete the group, ETH moves back; (4) remove ETH (Confirm) and add it back: `3 / 30 coins` to `2 / 30 coins` and back, its panel and `spaghetti-toggle-ETH` vanish and return without a reload (AC-23); (5) 31st add: after load add 27 filler symbols by API, add SOL in the UI: 409 message shows, panels stay 3, API holds 30 (fillers deleted in `finally`; no reload meanwhile); (6) hide ETH on the spaghetti chart, reload: `spaghetti-toggle-ETH` is `aria-pressed="false"` (AC-22); (7) garbage in the e2e `layout.json` (`<os tmpdir>/screener-e2e-cache/layout.json`; first assert the sibling `watchlist.json` exists), reload: recovered notice, 3 panels.

**Gates and probe:** "S5b exact gates" (G-S5b-1..11, P-S5b-1). Reds on the untouched base: all 65 vitest stubs and the 7 e2e tests.
**Lane:** capped lane yes: one read-only reviewer (accessible names, focus, global-CSS traps, word scan, no island re-mount on an equal hidden list), tester at EVL. **Budget [estimate]:** 180 tool calls, 150 minutes, 5 CI polls, 5.5-8 USD, 2 full-suite runs, e2e three times (own specs, then the full suite once).

**Risks:** (1) Focus after a move: jsdom cannot prove it; e2e test 2 does. (2) The page layout moves again (T38 precedent): tests 8-9 are run, not assumed. (3) Native `<select>` and input rendering differ on Windows/Edge and phones (P-S5b-1). (4) Browser POST/DELETE has never run through a real browser against the deployed origin (no UI called them before): e2e proves the seeded origin only. (5) A freshly added coin may show "Data source unavailable" until the worker fetches it; the retry covers the common case, P-S5b-1 measures it.

**Rollback:** revert the PR; the S5a API stays and the board returns to a flat grid; `layout.json` stays unused.

## Later batches (dependencies only)

S9 equities page (needs S5b: box, RSI row, layout section for equities); S10 optional scheduled task (`deploy/**`, RT4, S8, R12); group sort (Q1) and RSI/price zoom sync are follow-ups. Handoff to R12: `deploy/README.md` migration and backup notes should name `api\data\layout.json` as personal data next to `watchlist.json` (not done here: `deploy/**` is forbidden).

## Touchpoints

Changed: the owned files of S5a and S5b. Read only: `api/data/{freshness,equities_store}.py`, `api/analytics/indicators/rsi.py`, `api/scripts/seed_e2e_cache.py` (seeded stack: watchlist `[BTC, ETH, THIN]`, HYPE seeded, rising bars), `web/playwright.config.ts` (E2E root `/tmp/screener-e2e-cache`, API port 8001, web port 3100), `web/e2e/contrast.spec.ts`, `web/islands/simple-lines.svelte` (RSI y-domain re-fit; a constant series gets a 2-unit domain, so it draws).

## Public Contracts

- Added: `GET`, `POST`, `DELETE /api/layout/crypto` (`Layout`, `LayoutUpdate`); `CoinPanel.rsi` (`RsiReading`); `ChartSeries.rsi` (chart view only); `POST /api/watchlist` optional `group_id` and new 409 and 422 responses; git-ignored `api/data/layout.json` (personal data).
- Layout reads are a local file read: no provider call, so the page stays cached-first. Unchanged: `{"coins": [...]}` watchlist responses, the CORS allow-list (GET, POST, DELETE), board, spaghetti and chart-view fields, all timestamps already shipped. New timestamps (`saved_at`, `rsi[].timestamp`, `rsi.as_of`) are ISO UTC with a trailing `Z`. TS mirrors in `screener.ts` and `layout.ts` with contract tests.
- Security scan (STRIDE, quick): no auth, key or secret surface; Tailscale-only API; new writes are bounded (12 groups, 40-char names, 30 coins) and validated server-side; names and symbols render as React text (no HTML injection); a corrupt file is set aside, never executed; tampering by someone with file access is out of scope (personal use).

## Blast Radius

S5a 19 files, S5b 28 files (47 of the 100 limit); RT3: response models, a new personal-data file, one public route family, the shared board component. Other `fetch_ohlcv` consumers, the refresh worker, pairs, regime, narrative and onchain pages are untouched. Test-count effect: pytest 951 to 996, vitest 251 to 316 (34 to 41 files), seeded e2e screener+contrast 17 to 24, full e2e suite 65 to 72.

## Acceptance Criteria

The criterion table (id, behaviour, strategy, proving test, gap-resolution) is in the Validate Contract skeleton; every id is linked to its gate and to its SPEC criterion. SPEC links: AC-S5a-1,2 = AC-26, D8; AC-S5a-3..5 = D2, AC-7 (persistence), AC-22 (store half); AC-S5a-6,7 = AC-3, AC-5, D5, D7; AC-S5b-1 = AC-3, AC-4, AC-5; AC-S5b-2 = D7; AC-S5b-3,4 = AC-7 (buttons instead of drag, user decision); AC-S5b-5 = AC-6, AC-23, AC-26; AC-S5b-6 = AC-22 (closes AC-S6-6).

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G-S5a-1 store, router, cap, RSI tests | Fully-Automated | AC-26, D2, D8, AC-3, AC-5, AC-7 persistence (AC-S5a-1..8) |
| G-S5a-2..5 full pytest, vitest, tsc, islands | Fully-Automated | no regression, lockstep mirrors (AC-S5a-8, AC-S5a-9) |
| G-S5a-9, G-S5a-10 ignore rule, real-data guard | Fully-Automated | D2 personal data (AC-S5a-4) |
| G-S5a-12 e2e screener and contrast on the new API | Hybrid | board still renders with the new fields (AC-S5a-10) |
| P-S5a-1 PC check of routes and file location | Agent-Probe | D2 on the real stack (AC-S5a-4r) |
| G-S5b-1, G-S5b-2 vitest | Fully-Automated | AC-3, AC-4, AC-5, AC-6, AC-7, AC-22, AC-23, AC-26, D7 (AC-S5b-1..8) |
| G-S5b-9, G-S5b-10 e2e layout, screener, contrast, full suite | Hybrid | AC-6, AC-7, AC-22, AC-23, AC-26 end to end (AC-S5b-1..9) |
| P-S5b-1 PC, phone, keyboard, screen reader | Agent-Probe | usability on the real device and origin (AC-S5b-10r) |

## Risk Predictions (condensed 5-persona pass)

Security: the new write surface is small and validated; CORS unchanged. Performance: one file read per layout GET; RSI is one vectorised pass per displayed frame; the payload grows by one small object per coin. Data integrity: atomic file write, revision check, reconcile heals the two-file gap, a corrupt file is set aside, an over-30 list is untouched. User: every refusal has visible text, destructive actions need Confirm, keyboard users get focus and announcements. Maintainability: the sections registry gives S9 a slot, mirrors have contract tests, layout functions are pure and unit-tested.

## Implementation Checklist (atomic; one slice per worker)

**S5a:** 1 baseline (pytest, vitest, tsc, islands, e2e 17). 2 stubs for the 45 new tests, red run G-S5a-1. 3 `watchlist.py` cap and symbols. 4 `models/layout.py`, `data/layout.py`. 5 `routers/layout.py`, `main.py`. 6 `routers/watchlist.py`. 7 `models/screener.py`, `screener_board.py`. 8 TS mirrors, `.gitignore`. 9 real tests and the three listed test-file edits. 10 gates G-S5a-1..12 once after the last edit, `REAL-DATA` before and after the full pytest run. 11 report, PR, CI, tester.
**S5b** (after S5a merged): 1 baseline. 2 stubs for the 65 vitest and 7 e2e tests, red run G-S5b-1. 3 `layout-state.ts`, `rsi-format.ts` and tests. 4 `api/layout.ts`, `api/watchlist.ts` and tests. 5 `use-board-layout.ts`. 6 `CoinActions`, `AddCoinForm`, `CoinGroup`, `RsiChart`, `CoinPanel`, `DrillDownView`, `SpaghettiChart`. 7 `ScreenerBoard`, CSS. 8 existing-test edits (table), `ScreenerBoardLayout` and `CoinPanel` tests. 9 `layout.spec.ts`, `screener.spec.ts` test 1. 10 gates G-S5b-1..11 once after the last edit. 11 backlog stub, report, PR, CI, tester.

## Phase Completion Rules

`CODE DONE` = PR open with green gates in the report; `VERIFIED` only after independent confirmation (tester or CI on the head SHA, plus the tester's e2e run) AND the slice's PC probe. A slice may merge only when every gate including the e2e gates is green, CI is green on the head SHA and report heading 9 holds no open `needs_input` or `blocker`; otherwise it stops at `review`. S5a stays at `review` until P-S5a-1, S5b until P-S5b-1. A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` stops at `review`. After the S5b EVL the planner moves AC-S6-6 in the batch-2 plan from CONDITIONAL to PASS marks the backlog note `spaghetti-toggle-persistence_NOTE_09-10-26.md` done, and notes in the SPEC that drag-and-drop was replaced by buttons (planner steps, not slice files).

## Open questions for the user

| # | Question | Options | Recommendation |
|---|---|---|---|
| Q1 | SPEC US-3 / AC-8 also promise sorting each group by name, % change or RSI. It was not in the S5 list you gave. Include it? | A) defer to a small follow-up after the PC probe (pure web, about 3 files, 0.7 USD); B) one-shot "Sort group by" actions that rewrite the saved order, inside S5b (+3 touches, +6 tests, +0.7 USD); C) a view-only sort that resets on reload | A: manual order plus buttons already covers "reordering"; sorting is easier to judge after you have used the groups |
| Q2 | The honest estimate for S5 is 9.5-13.5 USD (two slices, tester included), against 3-6 USD in the INNOVATE table; comparable slices cost 4-5.6 USD each. It fits the 60 USD ceiling (25.27 left; 12-16 USD would remain for S9 and S10, whose own estimates add up to 4-12 USD). Accept? | A) accept; B) trim S5b (drop the remove confirm and the new-coin retry; saves about 0.7 USD, worse UX); C) stop after S5a and decide again | A |

Decided without asking (reversible): layout save is `POST` not `PUT` (CORS pin); RSI needs the same 60 bars as the chart; unplaced coins go to the last group; deleting a group moves its coins to the previous group; groups max 12; native select as the menu; no 30/70 lines; the watchlist file write stays non-atomic.

## Validate Contract

(PVL not run. vc-validate-agent writes the verdict; the tables below are the contract as planned.)
supersedes: none
Status: PENDING
Gate: PENDING
generated-by: plan-agent (skeleton for outer-pvl)

### Test gates

gap-resolution: A proven now / B added by this plan's checklist / C deferred to a named later step / D backlog stub (residual, keep-active).

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-S5a-1 | cap 30: the 31st is refused 409 with the exact message; remove-then-add works; an existing coin is a no-op; a file over 30 is kept and new adds are blocked | Fully-Automated | G-S5a-1 `test_watchlist_cap.py` tests 1-6 | B |
| AC-S5a-2 | invalid symbols are refused 422 and not stored (today `""` is stored) | Fully-Automated | G-S5a-1 `test_watchlist_cap.py` tests 7, 11 | B |
| AC-S5a-3 | layout store and API: default, recovered, round trip, revision conflict, validation, reconcile, hidden lines, unknown sections kept, GET never writes, atomic write | Fully-Automated | G-S5a-1 `test_layout_store.py`, `test_layout.py` | B |
| AC-S5a-4 | `layout.json` is git-ignored; no test creates or changes a real personal file | Fully-Automated | G-S5a-9, G-S5a-10 | B |
| AC-S5a-5 | add places and remove drops the coin in the layout; a layout failure never fails them | Fully-Automated | G-S5a-1 `test_watchlist_cap.py` tests 8-10 | B |
| AC-S5a-6 | board RSI equals an independent Wilder reference, follows the timeframe, is N/A with a reason (never 0 or NaN), one 60-bar rule | Fully-Automated | G-S5a-1 `test_screener_rsi.py` tests 1-5, 8 | B |
| AC-S5a-7 | the RSI series is in the chart view only, Z timestamps, last point equals the reading | Fully-Automated | G-S5a-1 `test_screener_rsi.py` tests 6-7 | B |
| AC-S5a-8 | Python models and TS interfaces match (names, types, nullability); new timestamps are Z | Fully-Automated | G-S5a-1 mirror tests (`test_layout.py` 9, `test_screener_rsi.py` 9), G-S5a-4 | B |
| AC-S5a-9 | no regression: CORS methods, watchlist shape, board, chart, spaghetti, symbol gate | Fully-Automated | G-S5a-2..4 | A |
| AC-S5a-10 | the seeded stack still serves the board with the new fields | Hybrid | G-S5a-12 | B (run: C) |
| AC-S5a-4r | the PC writes `layout.json` beside `watchlist.json` and keeps it across a restart | Agent-Probe | P-S5a-1 | C |
| AC-S5b-1 | RSI on every box: value or N/A with reason, follows the timeframe, row always present | Fully-Automated | G-S5b-1 CoinPanel, rsi-format; hybrid layout test 1 (seeded value 100.0) | B (run: C) |
| AC-S5b-2 | drill-down: price chart plus RSI chart and value; flat-price shows N/A | Fully-Automated | G-S5b-1 DrillDownView (+3); hybrid layout test 1 | B (run: C) |
| AC-S5b-3 | groups in saved order; create, rename, delete (coins move), last group undeletable, unique names | Fully-Automated | G-S5b-1 layout-state, ScreenerBoardLayout; hybrid test 3 | B (run: C) |
| AC-S5b-4 | reorder buttons and move-to-group menu persist across reload; edge buttons `aria-disabled`; focus kept; announcements | Fully-Automated | G-S5b-1 CoinActions, ScreenerBoardLayout; hybrid tests 2, 3 | B (run: C) |
| AC-S5b-5 | add and remove from the page; count; full message (proactive and server); spaghetti follows (AC-23) | Fully-Automated | G-S5b-1 AddCoinForm, layout-api, ScreenerBoardLayout; hybrid tests 4, 5 | B (run: C) |
| AC-S5b-6 | a spaghetti toggle survives a reload (AC-22), stored in the server layout file and in no browser storage; closes AC-S6-6 | Fully-Automated | G-S5b-1 SpaghettiChart (+3), ScreenerBoardLayout; G-S5b-8 `S5b-nostore`; hybrid test 6 | B (run: C) |
| AC-S5b-7 | no panel before board and layout settle; each failure and empty state has visible text; RSI row height equal for a number and N/A | Fully-Automated | G-S5b-1 ScreenerBoardLayout; hybrid tests 1, 7 | B (run: C) |
| AC-S5b-8 | every new control has an accessible name and works by keyboard; the default state passes the contrast audit; no verdict wording | Fully-Automated | G-S5b-1 role queries, G-S5b-8; hybrid G-S5b-9 | B (run: C) |
| AC-S5b-9 | no regression: the 10 screener e2e tests (test 1 edited) and 7 contrast routes | Hybrid | G-S5b-9, G-S5b-10 | B (run: C) |
| AC-S5b-8r | on-demand states (rename input, remove confirm, open drill-down) pass the contrast audit | Known-Gap residual | backlog `screener-ondemand-states-contrast_NOTE`; the audit reads the default state only | D (CONDITIONAL) |
| AC-S5b-10r | phone, keyboard-only and screen-reader use; Edge select/input look; deployed-origin POST/DELETE; 30-coin refresh; new-coin fill-in | Agent-Probe | P-S5b-1 | C |

### S5a exact gates (repo root; counts are arithmetic from 951 pytest, 251 vitest in 34 files)

| Gate | Command | Expected |
|---|---|---|
| G-S5a-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_layout_store.py api/tests/routers/test_layout.py api/tests/routers/test_watchlist_cap.py api/tests/routers/test_screener_rsi.py -q` | 45 passed (15 + 10 + 11 + 9) |
| G-S5a-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q` (inside `REAL-DATA`) | 996 passed (951 + 45), 2 skipped, 5 deselected, 0 xfailed |
| G-S5a-3 | `cd web && pnpm test` | 251 passed in 34 files (unchanged) |
| G-S5a-4 | `cd web && pnpm exec tsc --noEmit --incremental false` | exit 0 |
| G-S5a-5 | `cd web && pnpm build:islands` | exit 0 |
| G-S5a-6 | `git diff --check` | exit 0, no output |
| G-S5a-7 | `S5a-scope`, `FORBIDDEN`, `S-secret-scan` (command block) | print nothing |
| G-S5a-8 | `FIXTURES` | prints nothing |
| G-S5a-9 | `S5-ignore` | the three ignored paths, then nothing from `git ls-files` |
| G-S5a-10 | `REAL-DATA` around G-S5a-2, plus `UV_FROZEN=1 uv run --project api pytest api/tests/deploy/test_main_cors.py -q` | before and after outputs identical; 10 passed |
| G-S5a-11 | `S5a-words`, `CAP-MESSAGE` (first line) | `S5a-words` prints nothing; `CAP-MESSAGE` prints 1 |
| G-S5a-12 | Gate convention 4 with `screener.spec.ts contrast.spec.ts` | 17 passed; NOT-RUN is not allowed |
| P-S5a-1 | user PC after pull and API restart: `curl -s http://127.0.0.1:8000/api/layout/crypto`; `curl -s "http://127.0.0.1:8000/api/screener/board?timeframe=1d"`; `curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d '{"symbol":"bad symbol!"}' http://127.0.0.1:8000/api/watchlist` | one `Main` group with your coins and `source` `default`; every coin has an `rsi` object (value 0-100 or a reason); the POST returns 422 and the watchlist is unchanged |

### S5b exact gates (S5a merge SHA recorded as the base; counts relative to 996 pytest, 251 vitest in 34 files)

| Gate | Command | Expected |
|---|---|---|
| G-S5b-1 | `cd web && pnpm exec vitest run components/screener lib/__tests__/layout-state.test.ts lib/__tests__/rsi-format.test.ts lib/__tests__/layout-api.test.ts` | 92 passed in 11 files (69 in the 8 `components/screener` files, BtcLegChart 6 included, plus 12 + 4 + 7) |
| G-S5b-2 | `cd web && pnpm test` | 316 passed in 41 files (251 + 59 + 3 + 3; 34 + 7) |
| G-S5b-3 | `cd web && pnpm exec tsc --noEmit --incremental false` | exit 0 |
| G-S5b-4 | `cd web && pnpm build:islands` | exit 0 |
| G-S5b-5 | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/test_no_verdict_symbols.py -q` | 2 passed (the symbol gate scans the new web files; no api change) |
| G-S5b-6 | `git diff --check` | exit 0, no output |
| G-S5b-7 | `S5b-scope` (it also excludes every fixture path), `FORBIDDEN`, `S-secret-scan` | print nothing |
| G-S5b-8 | `S5b-words`, `S5b-nostore`, `CAP-MESSAGE` (both lines) | `S5b-words` and `S5b-nostore` print nothing; `CAP-MESSAGE` prints 1 twice |
| G-S5b-9 | Gate convention 4 with `screener.spec.ts contrast.spec.ts layout.spec.ts` | 24 passed (10 + 7 + 7); NOT-RUN is not allowed |
| G-S5b-10 | Gate convention 4, no spec argument (full suite), once, after G-S5b-9 | all passed; 72 tests in 7 files (65 in 6 files from `pnpm exec playwright test --list`, re-recorded at spawn, plus 7) |
| G-S5b-11 | red-first: report heading 6 holds the G-S5b-1 red run | 59 new stubs + 6 added tests failing, 251 existing passing |
| P-S5b-1 | user PC after pull, `deploy/build-web.ps1`, restart both tasks: arrange groups and reload; restart the API and reload; add and remove a disposable coin and note how long its box takes to fill; with 30 coins try a 31st; use keyboard only; open on a phone; check select and input look in Edge | layout survives both; refusal text shows; the box fills within one refresh; every control is reachable and readable |

### Scope and secret-hygiene commands (run from the repo root; the labels above refer to these)

```
# FORBIDDEN (every slice): nothing may match
git diff --name-only origin/main...HEAD | grep -E '^(CLAUDE\.md|AGENTS\.md|README\.md|\.claude/|\.github/|deploy/|api/scripts/|api/tests/deploy/|api/data/(lse_adapter|equities_store|cache|ccxt_adapter|freshness|refresh_worker)\.py|web/islands/|web/lib/(chart-viewport|island-loader)\.ts|process/MASTER-PLAN\.md|process/context/current-state\.md|process/archive/)'

# FIXTURES (every slice): nothing may match
git diff --name-only --diff-filter=MDR origin/main...HEAD | grep -E '/fixtures/'

# S-secret-scan (every slice): nothing may match (added lines only)
git diff origin/main...HEAD | grep -nE "^\+.*(Bearer [A-Za-z0-9._-]{12,}|(API_KEY|SECRET|TOKEN|PASSWORD)[A-Z_]* *[:=] *[\"'][A-Za-z0-9+/_-]{12,})"

# S5a-scope: nothing may match
git diff --name-only origin/main...HEAD | grep -vE '^(api/data/(layout|watchlist)\.py|api/models/(layout|screener)\.py|api/routers/(layout|watchlist)\.py|api/analytics/screener_board\.py|api/main\.py|\.gitignore|web/lib/types/(screener|layout)\.ts|web/components/screener/__tests__/(ScreenerBoard|DrillDownView)\.test\.tsx|api/tests/data/test_layout_store\.py|api/tests/routers/(test_layout|test_watchlist_cap|test_screener_rsi|test_screener_no_verdict_contract)\.py|process/general-plans/active/screener-batch3_09-10-26/screener-batch3-s5a_REPORT_[0-9-]+\.md)$'

# S5-ignore (S5a): the first prints the three paths, the second prints nothing
git check-ignore api/data/layout.json api/data/layout.json.bad api/data/.layout.json.x.tmp
git ls-files api/data/layout.json api/data/layout.json.bad

# REAL-DATA (S5a): run before and after G-S5a-2; the outputs must be identical (absent files print nothing, and the full run must not create them)
ls -l --time-style=+%s api/data/layout.json api/data/watchlist.json 2>/dev/null; sha256sum api/data/layout.json api/data/watchlist.json 2>/dev/null

# S5a-words (S5a): nothing may match
grep -niwE 'bullish|bearish|bull|bear|buy|sell|overbought|oversold|confidence|(out|under)perform(ing)?|risk-(on|off)|favorable' api/data/layout.py api/models/layout.py api/routers/layout.py api/models/screener.py api/analytics/screener_board.py api/data/watchlist.py api/routers/watchlist.py

# S5b-scope: nothing may match
git diff --name-only origin/main...HEAD | grep -vE '^(web/components/screener/(ScreenerBoard|CoinPanel|DrillDownView|SpaghettiChart|CoinGroup|AddCoinForm|CoinActions|RsiChart)\.tsx|web/lib/(layout-state|rsi-format|use-board-layout)\.ts|web/lib/api/(layout|watchlist)\.ts|web/app/globals\.css|web/components/screener/__tests__/(ScreenerBoard|ScreenerBoardLayout|DrillDownView|SpaghettiChart|CoinPanel|CoinActions|AddCoinForm)\.test\.tsx|web/lib/__tests__/(layout-state|rsi-format|layout-api)\.test\.ts|web/e2e/(screener|layout)\.spec\.ts|process/general-plans/(active/screener-batch3_09-10-26/screener-batch3-s5b_REPORT|backlog/screener-ondemand-states-contrast_NOTE)_[0-9-]+\.md)$'

# S5b-words (S5b): nothing may match (web/lib/api/*.ts are left out on purpose: AbortSignal would match a wider list)
grep -niwE 'bullish|bearish|bull|bear|buy|sell|overbought|oversold|confidence|(out|under)perform(ing)?|risk-(on|off)|favorable' web/components/screener/{ScreenerBoard,CoinPanel,DrillDownView,SpaghettiChart,CoinGroup,AddCoinForm,CoinActions,RsiChart}.tsx web/lib/{layout-state,rsi-format,use-board-layout}.ts

# S5b-nostore (S5b): nothing may match (user decisions: server file only, buttons and a menu, no drag-and-drop)
grep -nE 'localStorage|sessionStorage|indexedDB|document\.cookie|draggable|onDrag|onDrop' web/components/screener/{ScreenerBoard,CoinPanel,DrillDownView,SpaghettiChart,CoinGroup,AddCoinForm,CoinActions,RsiChart}.tsx web/lib/{layout-state,rsi-format,use-board-layout}.ts web/lib/api/{layout,watchlist}.ts

# CAP-MESSAGE (S5a runs the first line, S5b both): each prints 1 (the S5a cap test pins the server text; in S5b a mismatch is a defect to report, not to fix here)
grep -c 'Screener is full: 30 coins maximum. Remove a coin to add another.' api/data/watchlist.py
grep -c 'Screener is full: 30 coins maximum. Remove a coin to add another.' web/lib/layout-state.ts
```

### Failing stubs

Each test in a slice's Tests list starts as `def test_x(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: <behaviour>")` (vitest and Playwright: `throw new Error(...)`); the worker runs the slice's first gate on the untouched base, records the red run in heading 6, then writes the real tests. The six tests added to existing vitest files (DrillDownView +3, SpaghettiChart +3) are stubbed inside those files.

### Red-today evidence (origin/main 270f9ac; read-only checks run 09-10-26, nothing committed)

AC-S5a-1/2: a scratch run adding 31 coins to a temp watchlist stored 31, and `add_coin("")` stored `""`. AC-S5a-3: `GET /api/layout/crypto` through the app returns 404; `git check-ignore -v api/data/layout.json` exits 1 (not ignored). AC-S5a-6: `"rsi" in CoinPanel.model_fields` and `"rsi" in ChartSeries.model_fields` are both False. AC-S5a-9: `_cors_options` allows exactly GET, POST, DELETE. AC-S5b-5: `grep -rn "api/watchlist" web/` (ts, tsx) finds nothing: no client and no add/remove UI. C6: `compute_rsi` on 60 equal closes returns all NaN; 60 rising closes give 46 defined values ending at 100.0; 15 closes give one defined value. Seeded data: `seed_e2e_cache._bars` rises by 1 per bar. Baselines run 09-10-26: vitest 251 in 34 files; seeded e2e screener+contrast 17 passed (1.9 min); `playwright test --list` 65 tests in 6 files; `test_main_cors.py` 10 collected. Re-run at hardening 09-10-26: the full pytest (951 passed, 2 skipped, 5 deselected, no xfail), tsc 0, build:islands 0, `test_main_cors.py` 10 passed, seeded e2e screener + contrast 17 passed (1.4 min).

### Unverified facts: owner and deterministic fallback

| # | Fact | Status | Owner | Fallback |
|---|---|---|---|---|
| U1 | focus stays on the pressed control after a reorder in a real browser | jsdom cannot prove it | S5b e2e layout test 2 | refocus by ref in an effect; the e2e decides |
| U2 | browser POST/DELETE through the deployed Tailscale origin passes CORS | seeded origin only; web never called these routes before | P-S5b-1 | the allow-list already lists both methods and `Content-Type` |
| U3 | new-coin box fill-in time with the worker running | not measurable offline | P-S5b-1 | the board retries at 4 s and 12 s |
| U4 | native select/input rendering in Edge on Windows and on phones | not measurable offline | P-S5b-1 | tokens set colour and background explicitly |
| U5 | `os.replace` over `layout.json` on Windows while another program has it open | not measurable offline | P-S5a-1 | the save returns 500, the UI rolls back |
| U6 | whether coin boxes already grow when the chart island mounts (a shift this slice does not change) | not measured | none | not claimed; see "What this coverage does NOT prove" |
| U7 | whole-suite e2e count | 65 in 6 files at `270f9ac` (`playwright test --list`) | S5b worker | re-record at spawn; a differing baseline stops the worker |

### Not verifiable offline

Live Hyperliquid; real display, phone and keyboard-only use; Edge/Windows control rendering; the deployed origin; the PC cache and refresh timing; GitHub CI; every new test.

### What this coverage does NOT prove

- Seeded e2e proves the RSI row and drill-down are wired to the API value (100.0 for every seeded coin) and the N/A path (THIN); the per-timeframe numbers are proven by pytest with non-monotone frames, not by the browser.
- Page-level layout shift is not measured. The tests prove that panels never reorder after first render, that the RSI row height is equal for a number and for N/A, and that notices have a reserved region; any growth of coin boxes when the chart island mounts is pre-existing and unchanged.
- The contrast audit reads the default state only; the rename input, remove confirm and open drill-down are not audited (AC-S5b-8r, backlog stub, gate stays CONDITIONAL).
- Atomic write means a reader never sees a half-written `layout.json` and a crash keeps the previous file; it does not make `watchlist.json` atomic and does not cover the two files together.
- `REAL-DATA` proves no real personal file was created or changed on the machine that ran the gates; on the PC it is only as strong as the autouse redirects.
- Group sort and drag-and-drop are not delivered (Q1, user decision).

### Open gaps

Q1 and Q2 (above). AC-S5b-8r (on-demand states contrast) is a named residual with a backlog stub. known-gap: real device and browser behaviour: probes P-S5a-1, P-S5b-1.

## Autonomous Goal Block

(Not emitted. The planner emits the /goal block after VALIDATE passes, per CLAUDE.md.)

## Worker envelopes

Written by the planner AFTER the user's explicit ENTER EXECUTE MODE: one per slice, at most 8,000 bytes, a pointer list citing the sub-range table below, saved as `screener-batch3-s{5a,5b}_REF_<dd-mm-yy>.md` in this task folder (master-planner.md section 8). S5b's envelope is issued after the S5a merge SHA exists. Each envelope repeats: the e2e gates are required and NOT-RUN stops at `needs_input`; no merge with an open `needs_input` or `blocker`; counts that differ from the plan arithmetic stop the worker; the lane (3 sonnet subagents, 15 USD, one level) and the budget line of the slice. Each envelope names the 11 report headings inline (the template file is outside the read set), cites the plan by the line numbers of the table below instead of copying text, and stays under 2,000 B so the room in the table holds.

## Test Infra Improvement Notes

(none identified yet) Candidates: a CI job for the seeded Playwright specs (three UI slices have now needed local e2e runs that CI cannot confirm); an atomic write for `watchlist.json` (`_save_raw` is non-atomic, pre-existing); a Playwright project at DPR 2 and a layout-shift (CLS) check; a shared fake-exchange module.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/screener-batch3_09-10-26/screener-batch3_PLAN_09-10-26.md`
2. Last completed step: PLAN 09-10-26 (S5 split into S5a and S5b), hardened 09-10-26 against the code at `270f9ac`; validate-contract PENDING; PVL not run.
3. Validate-contract status: pending (VALIDATE writes it; this plan carries the skeleton above). No /goal block yet.
4. Context loaded: SPEC, INNOVATE, decisions.md, current-state.md, architecture.md, operating-instructions.md, all-tests.md, batch-2 plan (and the batch-1 shape), batch-2 PVL iterations 001, 003, 005 and the S6 and T39 reports, backlog notes, real code at origin/main `270f9ac` (watchlist store and router, screener router/board/models, ScreenerBoard, CoinPanel, DrillDownView, SpaghettiChart, island props, seeder, Playwright config, e2e specs, CORS and real-data tests).
5. Next step for a fresh agent: answer or accept Q1 and Q2 with the user, run VALIDATE (PVL) on this file, wait for the user's explicit "ENTER EXECUTE MODE", then the planner writes the S5a envelope and spawns S5a only; S5b's envelope follows the S5a merge SHA.

## Envelope line ranges (re-derive with `grep -n '^## \|^### '` at spawn time; worker cap 36,000 B = CLAUDE.md 13,443 counted once + envelope (cap 8,000) + plan bytes)

Line numbers refer to this file as saved. This table is the last block, so editing it moves no earlier line; if any earlier line is edited, re-derive the numbers with the grep named in the heading and recount the bytes (each line plus its newline). Each set holds: the decision lines the slice needs, Gate conventions 1-10 (S5b: 2-10), the slice Goal, Owned and Forbidden lines, its design, existing-tests-that-break and tests lines, its exact gates without the PC probe, the command-block lines it uses, and Failing stubs. A worker never needs: Name check, Costs, Risks, Rollback, the criteria rows (PVL and the tester use them), PC probes, Red-today evidence, Open questions. Decisions: S5a reads C2-C7 (lines 48-53); S5b reads C4, C5, C7 (lines 50-51, 53) because its own design lines restate the rest.

| Slice | Plan ranges (lines) | Plan bytes | Envelope room (cap 36,000) |
|---|---|---|---|
| S5a | 48-53, 57-66, 86, 88-89, 91-98, 100, 102-108, 110-114, 116, 263, 265-278, 300-322, 332-333, 335, 337, 339 | 19,612 | 2,945 |
| S5b | 50-51, 53, 58-66, 125, 127-128, 130-135, 137-142, 144-149, 151-160, 281, 283-295, 300-302, 307-308, 323-324, 326-327, 329-330, 332-335, 337, 339 | 20,124 | 2,433 |

Computed as 36,000 - 13,443 (CLAUDE.md) - plan bytes. A filled envelope stays under 2,000 B (the template alone is 864 B), so S5a keeps about 900 B and S5b about 400 B spare; S5b is the tight one, and an envelope that would not fit is trimmed, never the ranges. Naming operating-instructions.md (6,678 B) lifts the cap to 43,000 and leaves the room within about 330 B of the figures above, so name it only if the slice needs it. The union of both sets is 34,271 B: not readable by one worker, which is why S5 is two slices.
