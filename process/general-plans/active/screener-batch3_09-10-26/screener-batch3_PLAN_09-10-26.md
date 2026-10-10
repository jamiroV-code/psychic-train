---
name: plan:screener-batch3
description: "Screener realignment batch 3 (slice S5 split in two): S5a layout file API, 30-coin cap, RSI numbers and TS mirrors; S5b layout UI (groups, reorder buttons, move-to-group menu, add/remove coins), RSI on coin boxes and drill-down, spaghetti toggle persistence (AC-22). Sequential S5a then S5b; S9, S10 are later"
date: 09-10-26
feature: general-plans
---

# Screener Batch 3: Layout, Groups, 30-Coin Cap, RSI and Toggle Persistence (S5a, S5b)

Date: 09-10-26
Status: S5a VALIDATED PASS (PVL cycle 3) and merged; S5b VALIDATED PASS (PVL cycle 4, 10-10-26: re-validated against main fc12f27 after the S11 and T44 edits; see "Validation record (PVL cycle 4, S5b)" and "Changes since validation (S5b, 10-10-26)"). Q1 A and Q2 A RESOLVED by the user 09-10-26. Plan-time baselines (09-10-26, origin/main `270f9ac`; `abda8e7` adds process docs only): pytest 951 passed, 2 skipped, 5 deselected in 200 s; vitest 251 in 34 files; tsc 0; build:islands 0; `playwright test --list` 65 tests in 6 files; `test_main_cors.py` 10 passed. The S5b base is now main fc12f27 (T44 merged): pytest 1016/2/5, vitest 335 in 43 files, e2e 72 in 8 files.
Folder index: this plan; PVL reports `screener-batch3-pvl-iteration-NNN_REPORT_<dd-mm-yy>.md` (001-003) and `screener-batch3-s5b-pvl-iteration-NNN_REPORT_<dd-mm-yy>.md` (S5b, 004 onward) and `results.tsv` (written by VALIDATE); envelopes `screener-batch3-s{5a,5b}_REF_<dd-mm-yy>.md` and slice reports `screener-batch3-s{5a,5b}_REPORT_<dd-mm-yy>.md` (written by the planner and workers).
Complexity: COMPLEX (S5a then S5b, strictly sequential; RT3 response models, a new personal-data file, a public API surface, the shared board component)

**TL;DR:** The screener gets saved groups, ordering, a 30-coin cap, RSI on every coin box and in the drill-down, and spaghetti toggles that survive a reload. The saved layout lives in one server file `api/data/layout.json` (git-ignored, written atomically); the coin list stays in `watchlist.json`. S5 is split in two: S5a (API, file, cap, RSI numbers; 19 file touches) then S5b (web UI; 30 touches). The 100-touch rule alone would keep it one slice (49 touches); the worker read cap forces the split (see "S5 split evidence"). The web has no add/remove coin UI today, so S5b builds it (the cap needs it). Estimate 9.5-13.5 USD [estimate] for both (tester runs included), not the 3-6 USD of the INNOVATE table; accepted by the user (Q2 A). Group sort (AC-8) is deferred by the user (AC-8r). Every e2e gate must run before any merge.

Sources: SPEC `personal-tracker-realignment_SPEC_02-10-26.md` (D1-D11, AC-3..8, AC-22, AC-23, AC-26), INNOVATE `..._INNOVATE_03-10-26.md` (area G, slice S5), decisions.md D-2, D-3, D-14; backlog `spaghetti-toggle-persistence_NOTE_09-10-26.md`; batch 1 and 2 plans, reports and PVL iterations; `process/context/{current-state,architecture,operating-instructions}.md`; `process/context/tests/all-tests.md` (Standing Lessons 3, 7, 10, 11); real code at origin/main `270f9ac`. Router: `process/context/all-context.md`.

Context Envelope: general-plans | PLAN | batch 3 (S5) | claude/pensive-albattani-ou0cgv | /home/user/psychic-train | tests | api/, web/ | this file | pytest then vitest then playwright | contract PASS (cycle 4).

## Overview

Goal: a screener the user can arrange and trust: groups, order and hidden chart lines persist on the server; the board holds at most 30 coins (existing extras kept, new adds blocked); every box and the drill-down show RSI(14, Wilder) as plain numbers; coins can be added and removed from the page. User decisions (binding): server file, no second storage system; buttons plus a move-to-group menu, no drag-and-drop; cap 30; drill-down keeps price plus RSI chart; page refresh stays cached-first; data only, no verdicts. Non-goals: equities page (S9; the layout API has a section slot for it), scheduled task (S10), group sort (deferred by the user, AC-8r), drag-and-drop, a Reset-layout button, RSI/price zoom sync, any change to `deploy/**`, `api/scripts/**`, `api/tests/deploy/**`, `lse_adapter.py`, `equities_store.py`, `cache.py`, `ccxt_adapter.py`, `freshness.py`, `refresh_worker.py`, the chart island.

## Name check against INNOVATE / SPEC / reports (real code read 09-10-26)

| INNOVATE / SPEC / report says | Actual code | Plan consequence |
|---|---|---|
| G: "GET/PUT whole document" | `api/main.py::_cors_options` allows GET, POST, DELETE and `test_main_cors.py:95` pins exactly that set | save with `POST /api/layout/{section}` (C4); CORS untouched |
| G: file `{version, groups, hidden_lines}` | no layout code exists; equities (S9) must fit later | sectioned file with revision (C2) |
| US-4 / AC-6: add and remove coins "from the UI" | `api/routers/watchlist.py` exists; `grep api/watchlist web/` finds no client and no UI | S5b builds the add/remove UI; the cap is unreachable without it |
| D8 / AC-26: cap 30, keep extras, block new | `watchlist.add_coin` has no cap; 31 adds stored 31; an empty symbol is stored as `""` (red-today) | cap and symbol validation in the store (C5) |
| AC-3 RSI under each coin | `compute_rsi` exists (`rsi.py`); neither `CoinPanel` nor `ChartSeries` carries RSI | RSI reading and series (C6) |
| AC-22 / backlog note: toggles persist, S5 chooses storage | toggles are `SpaghettiChart` memory state (`hidden` set) | `hidden_lines` in the layout file (C2) |
| AC-7 drag-and-drop, AC-8 group sort | user decision 09-10-26: buttons plus menu, no drag | drag clause superseded by the user; group sort deferred by the user (AC-8r) |
| INNOVATE S5 files: `watchlist.py`, `layout.py`, `ScreenerBoard`, `CoinPanel` | the work touches 47 files in two surfaces | two slices (C1) |
| Seeded e2e data | `seed_e2e_cache.py::_bars` rises strictly, so seeded RSI is 100.0 on every coin and timeframe; THIN has 20 bars | e2e proves wiring and the N/A path, not the number |
| e2e test 1 counts `screener-board-grid > div` | groups become the direct children | listed edit (S5b table) |
| Gate command `pnpm --filter web ...` | prints "No projects matched the filters" here (T39 report) | gates run inside `web/` |
| Global CSS `.app-main [role="group"]` | makes any `role="group"` an inline-flex bordered segmented control | group sections are `<section>`, never `role="group"` |
| `test_fresh_deploy_degrade.py` runs `importlib.reload(watchlist_store)` twice and walks the board JSON for NaN and inf | `tests/deploy` runs before `tests/routers`, so an exception class imported by name into a router is stale in a later test (a 409 would surface as a 500); a NaN RSI would fail the walk | classes are used as `watchlist_store.<Name>` only; RSI skips NaN and inf (S5a design 1 and 5) |
| e2e test 5 asserts `getByRole("heading", { name: "Screener" })` (substring match) | a second heading containing "Screener" makes it ambiguous | no new heading contains "Screener" (gate convention 10) |
| the layout holds `hidden_lines` as an array, `SpaghettiChart` uses a Set | a fresh Set per render changes `lines` and re-mounts the island (zoom and pan lost) | U5 memoises the Set |
| `watchlist.add_coin` is a read-modify-write with no lock and a non-atomic `_save_raw`; the router is a sync `def` (thread pool) | PVL measured 40 threads: 4 of 41 coins kept and `JSONDecodeError` | module-level lock in `watchlist.py` (S5a design 1) |
| `os.rename` raises `FileExistsError` on Windows when the target exists (POSIX overwrites, so Linux tests cannot see it) | the `.bad` move of a second corrupt layout would fail the save | `os.replace` plus a source-text token check (C2, test 12) |

## Decisions locked for this batch

- **C1 Two slices, sequential.** S5a = API, layout file, cap, RSI numbers, TS mirrors. S5b = web UI, add/remove UI, RSI display, toggle persistence. S5b branches from `main` after the S5a merge. Reason: worker read cap.
- **C2 Layout store.** `api/data/layout.json`: `{"version":1,"sections":{"crypto":{"revision":N,"saved_at":"<Z>","groups":[{"id","name","coins"}],"hidden_lines":[...]}}}`. Path: env `SCREENER_LAYOUT_PATH`, else the sibling `layout.json` of the watchlist path, resolved at CALL time (never a default argument; Standing Lesson 3), so every test and the seeded e2e that redirect the watchlist also redirect the layout. Git-ignored. Atomic write: temp file in the same directory (prefix `.layout.json.`, suffix `.tmp`), flush, fsync, `os.replace`, under one process lock; no in-memory cache. A read never writes. Unreadable JSON, wrong shape or `version != 1` reads as the default with `source:"recovered"`; the next save first moves it to `layout.json.bad` with `os.replace` (it replaces an older `.bad`; `os.rename` fails on Windows). A missing file or section reads as the default (`source:"default"`). Other sections survive a save and a reset (S9 adds `equities`). Sections are a registry: `crypto` now (members = the watchlist, cap 30, references BTC and HYPE); any other name is 404. `hidden_lines` persist the spaghetti toggles (AC-22), BTC and HYPE included.
- **C3 Membership truth stays `watchlist.json`** (worker, scripts, seed and board read it); the layout holds grouping, order and hidden lines. Reconcile (every read and after every save): coins off the watchlist are dropped; watchlist coins in no group go to the LAST group (a group `main` named `Main` is made if there is none); `hidden_lines` keep BTC, HYPE and current members only. `POST /api/watchlist` with a `group_id` places the new coin there and saves the layout even when no file exists yet (the default layout is saved with the coin moved); no or unknown `group_id`: reconcile puts it in the last group; `DELETE /api/watchlist/{symbol}` drops the coin from the groups and `hidden_lines` (BTC and HYPE stay hidden) only when a layout file exists. Both bump the layout revision when they write, so the web refetches the layout after every add or remove. A layout failure is logged and never fails the add or remove. No guarantee spans the two files at once.
- **C4 Layout API.** `GET`, `POST`, `DELETE /api/layout/crypto`. `POST` body `{revision, groups, hidden_lines}`; `revision` must equal the stored one (0 for the default) else 409 `layout changed elsewhere`; success stores revision+1 and returns the reconciled `Layout`. 422: no group, more than 12, ids not `^[a-z0-9][a-z0-9-]{0,39}$` or repeated, names (trimmed) not 1-40 chars or repeated ignoring case, a coin in two groups; unknown coins are dropped, not an error. `DELETE` removes only the `crypto` section (the file only when no section remains), returns the default, is idempotent. `Layout` = `{version, section, revision, saved_at (Z or null), source, groups, hidden_lines}`.
- **C5 Cap and symbols.** `MAX_COINS = 30` in `watchlist.py`. A NEW symbol is refused with HTTP 409 and `detail` exactly `Screener is full: 30 coins maximum. Remove a coin to add another.` (this string appears once in `watchlist.py` and once in `web/lib/layout-state.ts`; comments must not repeat it) when the list holds 30 or more; an existing symbol is a no-op 200; a file already over 30 is kept; removal works at any size; adds unblock only below 30. Symbols are stripped, upper-cased and must match `^[A-Z0-9][A-Z0-9._-]{0,14}$` else 422. `POST /api/watchlist` gains optional `group_id`; its response stays `{"coins": [...]}` (`test_watchlist.py` pins it).
- **C6 RSI.** RSI(14, Wilder) from the unchanged `compute_rsi`, on the displayed timeframe's own frame (1w: the derived weekly frame), forming candle included (the chart's `is_partial` says so). One availability rule: RSI exists iff the frame has at least 60 bars (the chart's rule, `sma.SMA_LENGTH`) and the last value is defined; otherwise `value=None` with the chart's reason (`insufficient-history`, `bad-symbol`, `source-unavailable`) or `flat-price` (60+ bars with no price change give no defined RSI; verified). `CoinPanel.rsi: RsiReading {value, length=14 (TS `length: number`), as_of (last bar, Z), reason}` (default all-None); `ChartSeries.rsi` (a list of `RsiPoint {timestamp, value}`; default `[]`) is filled only by `build_chart_view` (board charts keep `[]`) with Z timestamps (price and SMA keep their format). Web shows one decimal; no 30/70 lines and no overbought or oversold wording.
- **C7 Gate facts.** Seeded bars rise strictly, so seeded RSI is 100.0 for BTC, ETH and HYPE on every timeframe and THIN (20 bars) is N/A; seeded watchlist is `[BTC, ETH, THIN]`, the seeder (forbidden) never writes a layout; per-timeframe RSI numbers are proven by pytest with non-monotone frames.

## Gate conventions (all slices; batch-1 and batch-2 conventions kept)

1. Every pytest gate runs with `UV_FROZEN=1`. No slice edits a fixture (`FIXTURES` prints nothing).
2. Baselines on main fc12f27, T44 merged (re-record at spawn): pytest 1016 passed/2 skipped/5 deselected; vitest 335 in 43 files; tsc 0; islands 0; e2e screener 10 + contrast 7 + brussels-time 3 + live-refresh 4, full suite 72 in 8 files. A count that differs from the plan arithmetic stops the worker at `needs_input`. New tests are plain functions (no `it.each`).
3. Web gates run inside `web/` (`pnpm --filter web` fails here with "No projects matched the filters"). Log each gate run in heading 6 with SHA and UTC time.
4. Seeded e2e (CI does NOT run Playwright): `cd web && SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e <specs>` (no `--`). REQUIRED on the head SHA before any merge; NOT-RUN stops at `needs_input`, no merge. Never merge with an open `needs_input` or `blocker` in heading 9 (PR #40).
5. Red-first: write the slice's new tests as stubs, run the first gate on the untouched base, record the red run in heading 6, then write the real tests.
6. Hidden-break rule: an existing test may be edited only as listed in the slice's table; any other failing existing test stops the worker at `needs_input`.
7. Workers branch from `main`; max 2 fix cycles per gate, the same failure twice stops. A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` stops at `review`.
8. `git diff --check` exits 0; ASCII only in plan and report files. Probes (P-*) are never claimed by a worker. Known-Gap is a residual (backlog stub, gate stays CONDITIONAL), never a PASS.
9. Personal data: tests never touch the real `api/data/layout.json` or `watchlist.json`. Every new test that can reach them has a module-level autouse fixture redirecting `watchlist_store.DEFAULT_WATCHLIST_PATH` to `tmp_path` (the layout follows it); the `REAL-DATA` command proves no real file was created or changed on the machine that ran the gates.
10. Gate-trap rules: new files must not contain any token of `api/tests/analytics/test_no_verdict_symbols.py::TOKENS` (for example `leg_context`, `fetchScalp`); no new testid starts with `coin-panel-`; no new container uses `role="group"`; no new heading contains `Screener` (e2e test 5); UI copy must not contain `Momentum`, `Trend`, `Benchmark`, `Confidence` or `Narrative` (`ScreenerBoard.test.tsx` asserts their absence). Comments in scanned files avoid the scanned words (S5b adds `UTC`).

## S5 split evidence and sequencing

Touches: S5a 19 (9 api source/config incl. `.gitignore`, 2 TS mirrors, 4 new pytest files, 3 edited test files, 1 report); S5b 30 (14 web source incl. `globals.css`, 8 new test files, 6 edited test files, 1 backlog stub, 1 report); total 49, under the 100 split threshold. The split is forced by the worker read cap (36,000 B = CLAUDE.md 13,443 + envelope + plan ranges): the sub-range table (last block) holds S5a at 20,238 B and S5b at 20,429 B of plan ranges against 22,557 B (36,000 - 13,443) less the envelope, and the union of both sets is 38,240 B, 15,683 B over the cap even with a zero-byte envelope, so one worker cannot read one combined slice. The split also gives two proof boundaries: the API contract and the personal-data file are proven by pytest and contract tests before any UI exists, and the UI e2e then runs against a merged API. Sequencing: S5a, merge, S5b, merge; never parallel (S5b imports the S5a types and routes). S9 starts only after the S5b merge. R12 (deploy fixes) is file-disjoint: it edits `deploy/**` and `api/tests/deploy/**` only and merely reads `.gitignore`; S5a owns `.gitignore` (three lines) while it runs. Touch counts were re-counted from the owned lists on 09-10-26: S5a 9 + 2 + 4 + 3 + 1 = 19, S5b 14 + 8 + 6 + 2 = 30 (recount 10-10-26: `ScreenerBoardLive.test.tsx` and, after T44, `ScreenerBoardLinkedZoom.test.tsx` added).

## Program budget and costs

Programme ceiling 60 USD (user, 09-10-26); spent 34.73 USD; 25.27 USD remain. Comparable slices cost T32 5.58, T34 4.99, T35 4.15, T36 5.44, T37 4.97, T38 4.75 USD (worker spend only; the registry does not meter tester runs, so the tester line below is an addition).

| Slice | Worker (opus) | Subagents (sonnet) | EVL tester | Total [estimate] | Basis |
|---|---|---|---|---|---|
| S5a | 3-4.5 | 0.3-0.5 | 0.5 | 4-5.5 | 19 touches, 45 new pytest, 2 full pytest runs (3.5 min each), e2e twice, 130 tool calls |
| S5b | 4.5-6.5 | 0.5-1 | 0.5 | 5.5-8 | 30 touches, 65 new vitest, 7 e2e, global CSS, 2 full runs, e2e three times, 180 tool calls; the largest UI slice so far |
| S5 | | | | 9.5-13.5 | against the INNOVATE 3-6 (accepted by the user, Q2 A) |

After S5, 12-16 USD remain for S9 (1-4) and S10 (3-8). All three at their top figure would total 25.5 USD, 0.2 over the 25.27 left; S10 (RT4, waits on R12) is the least certain figure, so re-check before the S10 spawn. Stop and ask above 15 USD for one slice or 60 USD in total; re-check before each spawn.

## S5a: layout file API, 30-coin cap, RSI numbers, TS mirrors (RT3, capped subagent lane: yes)

**Goal:** the server stores and serves a layout, refuses a 31st coin, validates symbols, and every board panel and chart view carries RSI numbers; the TS mirrors match. No UI change. Starts from `main` at the plan merge.

**Owned (exact):** `api/data/{layout,watchlist}.py`, `api/models/{layout,screener}.py`, `api/routers/{layout,watchlist}.py`, `api/analytics/screener_board.py`, `api/main.py` (router include and one comment), `.gitignore` (three lines: `api/data/layout.json`, `api/data/layout.json.bad`, `api/data/.layout.json.*.tmp`); `web/lib/types/{screener,layout}.ts`; new tests `api/tests/data/test_layout_store.py`, `api/tests/routers/{test_layout,test_watchlist_cap,test_screener_rsi}.py`; edited `api/tests/routers/test_screener_no_verdict_contract.py`, `web/components/screener/__tests__/{ScreenerBoard,DrillDownView}.test.tsx`; report `screener-batch3-s5a_REPORT_<dd-mm-yy>.md` (`layout.py`, `models/layout.py`, `routers/layout.py`, `layout.ts` are new).
**Forbidden:** the FORBIDDEN list (command block), every other web file, S5b files.

**Design:**
1. `watchlist.py` (C5): `MAX_COINS`, `CAP_MESSAGE`, `SYMBOL_RE`, `WatchlistFullError`, `InvalidSymbolError`, `normalize_symbol`; `add_coin(symbol, path=None)` keeps its signature and return, normalizes, refuses a new symbol at 30 or more; `add_coin` and `remove_coin` run their whole read-modify-write (the cap check inside) under one module-level `threading.Lock` (unlocked, 40 threads kept 4 of 41 coins); `_save_raw` untouched (the watchlist write stays non-atomic; see Test Infra notes). Every exception class and constant is used as `watchlist_store.<Name>` (module attribute at call time), never imported by name (test files too): `api/tests/deploy/test_fresh_deploy_degrade.py` reloads the module, and `tests/deploy` runs before `tests/routers`, so a class imported by name would be stale in a later test.
2. `models/layout.py` (C2, C4): `LayoutGroup`, `Layout`, `LayoutUpdate`, `LayoutSource`, `MAX_GROUPS = 12`, `MAX_GROUP_NAME = 40`, `MAX_LIST = 64`, `MAX_SYMBOL_LEN = 15` (`max_length` on `groups[].coins`, `hidden_lines` and each symbol; more is a 422). `data/layout.py`: `layout_path()`, `read_layout(section)`, `save_layout(section, update)`, `reset_layout(section)` (drops only that section; the file only when none remains), `place_coin(section, symbol, group_id)`, `drop_coin(section, symbol)`, errors `UnknownSectionError`, `StaleRevisionError`, `InvalidLayoutError`; it reads the watchlist through `watchlist_store.read_watchlist()` at call time (tests monkeypatch it); `REFERENCE_SYMBOLS = ("BTC", "HYPE")`; the atomic write is a local helper in the `equities_store._write` pattern (copied, not imported: that file is forbidden), and the `.bad` move uses `os.replace` too; `saved_at` is `freshness.iso_z` of a patchable clock.
3. `routers/layout.py`, `main.py`: `GET`, `POST`, `DELETE /api/layout/{section}`; 404 unknown section, 409 `StaleRevisionError` (detail `layout changed elsewhere`), 422 `InvalidLayoutError`. `main.py` only includes the router and corrects the comment "serves only GET plus the watchlist's POST/DELETE"; `_cors_options` is not edited.
4. `routers/watchlist.py`: 409 with `CAP_MESSAGE`, 422 for an invalid symbol, optional `group_id`; `place_coin` only for a new coin with a `group_id`, `drop_coin` only after a successful remove, each in try/except with a logged warning; response models unchanged.
5. `models/screener.py`: `RsiReason`, `RsiReading`, `RsiPoint`, `ChartSeries.rsi`, `CoinPanel.rsi`. `screener_board.py`: `_rsi_reading(df, available, status)` and an RSI series builder (Z timestamps via `freshness.iso_z`); `build_coin_panel` fills `rsi` from the displayed frame; `build_chart_view` also fills `chart.rsi`. `rsi.py` and `compute_rsi` are not edited. A non-finite RSI (NaN or inf) becomes `value=None` and the series builder skips undefined points, so the board JSON never carries NaN (`test_fresh_deploy_degrade.py` walks it).
6. TS mirrors: `screener.ts` gets `RsiReason`, `RsiReading` (`length: number`), `RsiPoint {timestamp: string; value: number}`, `ChartSeries.rsi`, `CoinPanel.rsi`; `layout.ts` gets `LayoutSource`, `LayoutGroup`, `Layout`, `LayoutUpdate`; fields one per line, each interface closed by a line `}` at column 0 (the contract tests parse them).
7. Tests as listed; run `REAL-DATA` around the full pytest run.

**Existing tests that break (exact edits allowed):**

| Test | Why | Edit |
|---|---|---|
| `test_screener_no_verdict_contract.py:77` `test_coin_panel_has_no_verdict_fields` | asserts the exact payload key set | add `"rsi"` |
| `ScreenerBoard.test.tsx` `makeCoin` (tsc only) | `CoinPanel.rsi` is required, so `makeBoard(tf, coins)` fails to type-check | add `rsi: { value: 61.3, length: 14, as_of: null, reason: null }` to the object `makeCoin` returns |
| `ScreenerBoard.test.tsx` `NO_FRESHNESS`, lines 168-169 (tsc only) | `ChartSeries.rsi` is required; `NO_FRESHNESS` is spread into every chart literal, 168-169 spread `freshness` | add `rsi: []` to `NO_FRESHNESS` and to the two inline literals |
| `DrillDownView.test.tsx` `NO_FRESHNESS` (tsc only) | same | add `rsi: []` (every chart literal in the file spreads it) |
| stay green unedited | pinned shapes and scans (G-S5a-2 checks) | `test_watchlist.py` (`{"coins": [...]}`), `test_watchlist_store.py`, `test_board_integration.py` and `tests/scripts/test_refresh_cache.py` (valid symbols only), `test_main_cors.py` (10 tests), `test_screener_freshness_payload.py` and `test_screener_gain_contract.py` (names and nullability against `screener.ts`: `rsi` defaults to a non-null value, so the TS fields carry no `\| null`), `test_spaghetti.py`, regime tests, `test_no_verdict_symbols.py` (scans `TOKENS` only), `test_screener_no_verdict_contract.py:29-33,168-175` (the lowercase word `confidence` is banned in `screener.ts` non-comment lines, so the new TS lines avoid it), the source-text scans of `screener_board.py` in `test_exchange_attention.py:157` and `test_history.py:286` (no new import of those modules), `api/tests/deploy/**` |

**Tests (45; plain functions; the worker chooses snake_case names that state the behaviour):**
- `test_layout_store.py` (15): default is one `main` group in watchlist order; a read of a missing file creates nothing; save round trip (revision+1, `saved_at` Z); stale revision refused, file unchanged; reconcile drops coins off the watchlist; reconcile appends unplaced coins to the last group; save drops unknown coins; save rejects a coin in two groups and bad shapes (no group, empty or 41-char name, bad id); save rejects duplicate names (any case) and a 13th group; hidden lines keep BTC/HYPE and drop removed coins, `REFERENCE_SYMBOLS` equals `screener_board.SPAGHETTI_REFERENCES`; interrupted write keeps the old file and leaves no temp file; corrupt or `version != 1` file reads as `recovered` default and is moved to `.bad` on the next save (a pre-existing `.bad` is replaced and the save succeeds; the source text has `os.replace(` and no `os.rename(`); other sections survive a save and a reset; path follows the watchlist path and the env override wins; unknown section name refused.
- `test_layout.py` (10): GET default for the current watchlist; GET never writes; POST then GET (revision+1, `source` file); stale POST 409, file unchanged; invalid bodies 422 (duplicate coin, no groups, bad id, a list over 64 items, a 16-char symbol); unknown section 404 on GET, POST, DELETE; DELETE resets only the `crypto` section (a second section stays; the file goes when none remains) and is idempotent; `saved_at` is Z; `Layout`, `LayoutGroup`, `LayoutUpdate` match `layout.ts` (names, types, nullability); `/api/layout` routes use only GET, POST, DELETE.
- `test_watchlist_cap.py` (11): 30 accepted and the 31st refused 409 with the exact message; a refusal leaves watchlist and layout unchanged; removing one at 30 allows exactly one add; re-adding an existing coin at 30 is a no-op 200; a file already over 30 is kept and new adds blocked; from 32, removing to 30 still blocks and 29 allows; invalid symbols (empty, spaces, 16 chars, `!`) 422 and nothing stored; add with `group_id` places in that group, with a saved layout and with no file yet (the file is then created); remove drops the coin from groups and hidden lines but keeps a hidden BTC; a failing layout write does not fail the add; store-level `add_coin` enforces cap and validation, and 8 threads behind a `threading.Barrier` adding new symbols at 29 coins give one success, the rest `watchlist_store.WatchlistFullError`, and a parsable file of 30.
- `test_screener_rsi.py` (9): board RSI equals an independent loop-based Wilder reference (copied into the file; non-monotone closes); each timeframe gets its own value; short history and failed sources give null value plus reason, never 0 or NaN; a flat window gives `flat-price`; `as_of` is the last bar in Z; chart view carries the RSI series and board charts carry `[]`; series points are Z and the last point equals the reading; the 60-bar rule matches the chart's; `RsiReading` and `RsiPoint` match `screener.ts`.

**Gates and probe:** "S5a exact gates" (G-S5a-1..12, P-S5a-1). Reds on the untouched base: all 45 new tests (stubs).
**Lane:** capped lane yes: one read-only reviewer (Python/TS lockstep, atomic write, reconcile, CORS untouched), tester at EVL. **Budget [estimate]:** 130 tool calls, 100 minutes, 4 CI polls, 4-5.5 USD, 2 full pytest runs, e2e twice.

**Risks:** (1) a test that reaches the real `api/data/layout.json` is a data-loss bug: autouse redirect plus `REAL-DATA`. (2) `screener_board.py` edits must not change existing chart, chip or spaghetti output: those tests stay unedited. (3) Windows `os.replace` fails if another program holds `layout.json` open: the save returns 500 and the UI rolls back (P-S5b-1). (4) The cap lives in the store, so any future caller gets it.

**Rollback:** revert the PR; `layout.json` is only created by a save, delete it by hand.

## S5b: layout UI, add/remove coins, RSI display, toggle persistence (RT3, capped subagent lane: yes)

Status: VALIDATED PASS (PVL cycle 4, 10-10-26). Edited 10-10-26 against main fc12f27 after S5a, R12, S11a, S11b and T44 (PR #50, linked zoom on the small charts) merged, then re-checked against the real code (see "Validation record (PVL cycle 4, S5b)" and "Changes since validation (S5b)" before the envelope table).

**Goal:** groups in saved order with reorder buttons, a move-to-group menu, group create/rename/delete, add/remove coin, RSI on every box and in the drill-down, persistent spaghetti toggles; clear loading, empty and error states; no panel reordering caused by this slice; the shared small-chart zoom of T44 survives every edit (U7). Base: main fc12f27 or later (S5a, R12, S11a, S11b, T44 merged).

**Owned (exact):** `web/components/screener/{ScreenerBoard,CoinPanel,DrillDownView,SpaghettiChart}.tsx`; new `web/components/screener/{CoinGroup,AddCoinForm,CoinActions,RsiChart}.tsx`, `web/lib/{layout-state,rsi-format,use-board-layout}.ts`, `web/lib/api/{layout,watchlist}.ts`; `web/app/globals.css`; new tests `web/lib/__tests__/{layout-state,rsi-format,layout-api}.test.ts`, `web/components/screener/__tests__/{CoinActions,AddCoinForm,ScreenerBoardLayout,CoinPanel}.test.tsx`, `web/e2e/layout.spec.ts`; edited `web/components/screener/__tests__/{ScreenerBoard,ScreenerBoardLive,ScreenerBoardLinkedZoom,DrillDownView,SpaghettiChart}.test.tsx`, `web/e2e/screener.spec.ts` (test 1); backlog stub `process/general-plans/backlog/screener-ondemand-states-contrast_NOTE_<dd-mm-yy>.md`; report `screener-batch3-s5b_REPORT_<dd-mm-yy>.md`.
**Forbidden:** FORBIDDEN list, `api/**`, `web/lib/types/*` (S5a mirrors; a missing field stops the worker at `needs_input`), `web/islands/**`, the T44 files `simple-lines.svelte`, `entry.js`, `MiniChart.tsx`, `island-loader.ts`, `chart-viewport.test.ts` (S5b needs none), `web/app/screener/page.tsx`, `web/components/chart/**`, `LiveProvider`, `FreshnessStrip`, `BtcLegChart`, every other `web/lib` file (S11 live-poll, same-data, use-simple-lines and the rest), S5a files.

**UI rules (locked):**
- **U1 Structure.** Groups are `<section aria-labelledby>` (never `role="group"`): `h2` name, coin count, Rename, Move group up/down, Delete group; coins in a grid per group; `screener-board-grid` stays on the groups container. Coin actions (a `CoinPanel` `actions` slot): Move earlier, Move later, a native `<select>` "Move to group", Remove with inline Confirm/Cancel. Edge buttons use `aria-disabled="true"` (not `disabled`) and do nothing. After a move the same control is refocused and the polite live region `board-announcer` states the result; after a Confirm-remove or group delete focus goes to the heading (`tabIndex={-1}`) of the group that holds or received the coins; after an add it stays in the cleared input. Rename and New group use an inline input (Enter saves, Escape cancels, errors in `role="alert"`). Deleting a group moves its coins to the previous group (next if first); the last group stays; names unique ignoring case, 1-40 chars; at most 12 groups.
- **U2 Loading and shift.** Panels render only after the first board answer AND the first layout answer or failure (fixed-height `board-loading` skeleton, `aria-busy`); later refetches never hide them. The RSI row is always rendered (same height for a number and N/A); `layout-notice`, `layout-save-error` and `board-announcer` exist from first render. Layout load failure: one default group, a notice, Retry, editing controls `aria-disabled`. `recovered`: its own notice. Empty watchlist: `board-empty` plus the add form. Board failure: before any success `board-error` and no groups; after one the panels stay and `board-error` shows above them until the next success clears it.
- **U3 Save.** Optimistic, serial queue, each save carries the last revision; failure rolls back and shows `layout-save-error`; 409 refetches the layout and shows "Layout changed elsewhere; reloaded."
- **U4 Add and remove.** Add form: symbol input, group select (default last), "Add coin", `coin-count` text `n / 30 coins`. At 30 or more the button is `aria-disabled` and the full message (C5) shows permanently; a click shows it and sends nothing; a 409, 422 or network error shows in `role="alert"`. After a successful add or Confirm-remove, `fetchBoard(timeframe)` and `fetchLayout` run once and the spaghetti `reloadToken` is bumped; while the new coin's chart is unavailable the board is refetched at +4 s and +12 s (at most twice).
- **U5 Toggles (AC-22).** `SpaghettiChart` takes optional `hidden`, `onToggle`, `reloadToken`: given `hidden` it is controlled (otherwise in-memory as today; its 6 tests stay unedited); `reloadToken` joins `dataVersion` in the fetch effect deps, so an added or removed coin appears or goes at once (AC-23). The board passes `layout.hidden_lines` (`hidden?: readonly string[]`), saves on toggle, bumps the token after every add or remove, renders the chart only after board and layout settled and builds the list once per layout change (`useMemo`). `SpaghettiChart` keys its own Set on the SORTED joined list: an equal list in any order keeps the Set, `lines` and island props, so `useSimpleLines` neither re-mounts nor calls `update` and zoom and pan stay.
- **U6 Live behaviour kept (S11b).** (a) Order is derived (`useMemo` over `board.coins` and the layout), not stored; a tick (60 s; board and open drill-down only, not the layout) keeps `shareStructure` identity, so give the `memo` `CoinPanel` stable props (stable callbacks, memoised `actions`). (b) Keep the `SpaghettiChart` container mounted (no changing `key`): islands update in place; hiding a line changes the line keys and resets zoom by design, reorder, move and group edits must not. (c) A failed refetch keeps what shows (panels with `board-error`; drill-down chart and RSI with `drilldown-error`; spaghetti with `spaghetti-error`; last layout with `layout-save-error`). (d) New effects drop an answer after cleanup (cancelled flag as in the board); retry timers and queued saves are cleared on unmount. (e) Times are Brussels (S11a): the RSI title uses `formatDateTimeZone` of `@/lib/brussels-time`, never `UTC`. (f) Reuse `.visually-hidden`; declare no `.freshness-strip*` rule.
- **U7 Shared small-chart zoom (T44).** `ScreenerBoard.tsx` keeps `sharedRange` (L41-49: state plus the render-time reset on a timeframe change) at board level, above the loading gate, and passes `range={sharedRange}` `onRangeChange={setSharedRange}` (L101-102) to every `CoinPanel`, through `CoinGroup`; `CoinPanel.tsx` keeps those props (L15-17) and the `MiniChart` pass-through (L56-62). Never in a group, panel, layout hook or file, or storage. Reorder, move (the remounted chart adopts the range at mount), group edits, add (the new chart adopts it), remove (no reset), layout refetch or rollback and ticks leave it alone; only a timeframe change clears it. Drill-down and spaghetti stay unlinked.

**Design:**
1. `web/lib/api/layout.ts`: `fetchLayout()`, `saveLayout(update)` (POST JSON), `LayoutConflictError` on 409, a 10 s `AbortSignal.timeout` of their own (`getJson` is private to `screener.ts`). `web/lib/api/watchlist.ts`: `addCoin(symbol, groupId?)`, `removeCoin(symbol)`, `WatchlistFullError` (server `detail`), `InvalidSymbolError` (422), else an Error naming the status.
2. `layout-state.ts` (pure): `arrange` (mirrors the server reconcile: drop symbols not on the board, append unplaced coins to the last group, make `Main` if no group), `moveCoin`, `moveCoinToGroup`, `addGroup`, `renameGroup`, `deleteGroup`, `moveGroup`, `toggleLine`, `validateGroupName`, `isFull`, `MAX_COINS`, `CAP_MESSAGE` (exactly `Screener is full: 30 coins maximum. Remove a coin to add another.`, once in this file, never in a comment); id generator injectable. `rsi-format.ts`: one decimal, reason copy, Brussels-time title. `use-board-layout.ts`: U2, U3, announcer text. The `Layout` shape is in `web/lib/types/layout.ts` (S5a).
3. `ScreenerBoard.tsx`: new injectable props `fetchLayout`, `saveLayout`, `addCoin`, `removeCoin` (defaults: the real clients); existing props, the `useLiveData` board effect (deps `[timeframe, fetchBoard, tick]`, cancelled flag, `shareStructure`) and the `DrillDownView` mount stay, and so does the T44 shared zoom (U7); a timeframe change refetches the board only.
4. `CoinPanel.tsx`: RSI row `rsi-readout-<SYM>` between the freshness caption and the chips (visible label `RSI 14 (<timeframe>)`, one decimal or `N/A` with the reason as `title`; reasons `insufficient-history`, `bad-symbol`, `source-unavailable`, `flat-price`; no 30/70 lines, no overbought or oversold wording) and an optional `actions` slot in the header; existing testids and classes unchanged. `DrillDownView.tsx`: below the price chart `RsiChart` (`drilldown-rsi-chart`, one series from `RsiPoint {timestamp, value}`, via `useSimpleLines(ref, props, timeframe)`, memoised props, so a tick updates in place) and `drilldown-rsi-value`; an available chart with an empty RSI series shows `drilldown-rsi-na` ("RSI 14: N/A, price did not change in this window"); an unavailable chart shows only the existing notice. Price and RSI zoom independently.
5. `globals.css`: tokens only; classes for groups, actions, add form, notices, skeleton, RSI row; `[aria-disabled="true"]` keeps the text colour (no opacity), dashed border, `cursor: not-allowed`; `:focus-visible` outline as `.spaghetti-chart__toggle`; inputs and selects coloured with tokens (no system colours); RSI row and status region have `min-height`. A contrast failure is fixed with existing tokens, never by exempting text.

**Existing tests that break (exact edits allowed):**

| Test | Why | Edit |
|---|---|---|
| `ScreenerBoard.test.tsx` (10 renders) | the board now also calls `fetchLayout` (default: a real fetch) | add one stub const next to `fetchSpaghetti` (revision 0, one group `main`, no coins; the board appends unplaced coins) and pass `fetchLayout={fetchLayoutStub}` in all 10 `render(<ScreenerBoard ...>)` calls |
| `ScreenerBoardLive.test.tsx` (12 tests) | same default fetch; `setup` renders `<ScreenerBoard` twice | one stable stub, `fetchLayout={fetchLayoutStub}` at both sites, nothing else |
| `ScreenerBoardLinkedZoom.test.tsx` (T44, 3 tests) | renders `<ScreenerBoard` at 3 sites (lines 119, 148, 158) without `fetchLayout`; a real fetch under fake timers shows panels late or never | the same `fetchLayoutStub`, `fetchLayout={fetchLayoutStub}` at the 3 sites, no assertion changed; panels missing after `advance(0)` stops at `needs_input` |
| `screener.spec.ts` test 1 | `screener-board-grid > div` now counts group sections | count `[data-testid^="coin-panel-"]` inside the grid, expect `manifest.watchlist.length` (`live-refresh`, `brussels-time` and `contrast` specs stay unedited and green) |
| stay green unedited | tests parse `globals.css` | `chart-palette`, `plot-ink`, `onchain-ink` tests read `--series-N:`, `--an-*:` and the `.analytic-plot`, `.spread-chart text` blocks: redeclare none; T44 `chart-viewport.test.ts`, `live-refresh.spec.ts`, the `screener.spec.ts` zoom test unedited |

**Tests (65 vitest + 7 Playwright; plain functions; the worker chooses names that state the behaviour):**
- `layout-state.test.ts` (12): arrange drops unknown and appends unplaced to the last group; arrange makes `Main` when no group; move earlier/later; edge move is a no-op; move to group; add group (trims; rejects empty, duplicate in any case, 13th, 41 chars); rename; delete (coins go to the previous group, next if first); last group undeletable; move group clamps; toggle line; `isFull` at 30 and over, exact `CAP_MESSAGE`.
- `rsi-format.test.ts` (4): one decimal (61.34 gives `61.3`, 100 gives `100.0`); copy for each reason; null is `N/A`, never `0` or `NaN`; title has the Brussels time and zone, no `UTC`.
- `layout-api.test.ts` (7): fetch URL and parse; save POSTs JSON with the revision; 409 gives `LayoutConflictError`; other failure names the status; `addCoin` 409 gives `WatchlistFullError` with the server text; 422 gives `InvalidSymbolError`; `removeCoin` DELETE, encoded symbol.
- `CoinActions.test.tsx` (7): names include coin and group; edge buttons `aria-disabled`, clicks do nothing; clicks call `onMove(-1)`, `onMove(1)`; select lists all groups, change calls `onMoveToGroup`; only Confirm calls `onRemove`; Escape cancels and refocuses Remove; buttons are native (Enter and Space click).
- `AddCoinForm.test.tsx` (9): labelled input, select, button; submit trims and upper-cases; empty input gives an inline error, no request; at 30 the full message shows, button `aria-disabled`, click sends nothing; server 409 text in `role="alert"`; 422 message; network error message; success clears the input, calls `onAdded`; pending blocks a second submit.
- `ScreenerBoardLayout.test.tsx` (15): no panel and no spaghetti chart until board and layout both resolve (`board-announcer` present from the start); groups in layout order with headings, counts, empty-group message; coin order follows the layout and is unchanged after a timeframe change, an identical-payload tick and the add retry timers (fake timers, recorded order compared); layout failure (default group, notice, disabled controls, Retry); recovered notice; move earlier saves with the current revision, reorders, announces (U7, folded into the move, move-to-group, remove/add and timeframe items: with the island mock of `ScreenerBoardLinkedZoom` copied in, a zoom set on one chart stays every chart's `linkedRange`, a moved or added chart gets it in its first props, a timeframe change clears it); failed save rolls back with `layout-save-error`; 409 refetches and notices; create, rename (validation message), delete a group; move to group by select; remove after Confirm and add both refetch board, layout and spaghetti, and remove closes that coin's drill-down; add retries the board at 4 s and 12 s while the new coin is unavailable (fake timers); a spaghetti toggle saves `hidden_lines`, initial hidden comes from the layout, count text updates; empty watchlist shows `board-empty` and the form; first board failure shows `board-error`, no groups, and a later one keeps the groups until the next success.
- `CoinPanel.test.tsx` (5): RSI row shows `RSI 14` and the value; N/A carries the reason as title; row present for an unavailable chart; the label text names the timeframe; the actions slot renders.
- `DrillDownView.test.tsx` (+3): RSI chart and value render; empty RSI series on an available chart shows `drilldown-rsi-na`; value equals the last RSI point. `SpaghettiChart.test.tsx` (+3): controlled `hidden` sets `aria-pressed`, and a re-render with a new array of equal content in another order mounts the island once and calls `update` never (`vi.resetModules()`, `vi.doMock("@/lib/island-loader")`, dynamic import; `mountSimpleLines` returns `Object.assign(dispose, { update })`); `onToggle` gets the symbol, local state unchanged; a changed `reloadToken` refetches.
- Playwright `layout.spec.ts` (hybrid, 7; `afterEach` removes every watchlist symbol, re-adds the manifest symbols in order, calls `DELETE /api/layout/crypto`; a 60 s poll tick may refetch the board mid-test and must not change the order; groups found by `getByRole("region", { name, exact: true })`): (1) RSI on every box equals the API value, THIN is N/A with a reason, RSI rows of BTC and THIN have equal height, drill-down shows RSI chart and value; (2) ctrl-wheel zoom the spaghetti plot and BTC's small plot (ETH's follows, also after the reorder), reorder with the buttons and `data-zoomed` stays `true`, reload keeps the order, Enter on a focused button keeps focus on it; (3) create a group, rename it, move ETH into it by menu, reload, delete the group, ETH moves back; (4) remove ETH (Confirm) and add it back: `3 / 30 coins` to `2 / 30 coins` and back, its panel and `spaghetti-toggle-ETH` vanish and return without a reload (AC-23); (5) 31st add: after load add 27 filler symbols by API, add SOL in the UI: 409 message shows, panels stay 3, API holds 30 (fillers deleted in `finally`; no reload meanwhile); (6) hide ETH on the spaghetti chart, reload: `spaghetti-toggle-ETH` is `aria-pressed="false"` (AC-22); (7) garbage in the e2e `layout.json` (`<os tmpdir>/screener-e2e-cache/layout.json`; first assert the sibling `watchlist.json` exists), reload: recovered notice, 3 panels.

**Gates and probe:** "S5b exact gates" (G-S5b-1..11, P-S5b-1). Reds on the untouched base: all 65 vitest stubs and the 7 e2e tests.
**Lane:** capped lane yes: one read-only reviewer (accessible names, focus, global-CSS traps, word scan, no island re-mount or update on an equal hidden list (also tested), U6), tester at EVL. **Budget [estimate]:** 180 tool calls, 150 minutes, 5 CI polls, 5.5-8 USD, 2 full-suite runs, e2e three times (own specs, then the full suite once).

**Risks:** (1) Focus after a move: jsdom cannot prove it; e2e test 2 does. (2) The page layout moves again (T38 precedent): tests 8-9 are run, not assumed. (3) Native `<select>` and input rendering differ on Windows/Edge and phones (P-S5b-1). (4) Browser POST/DELETE has never run through a real browser against the deployed origin (no UI called them before): e2e proves the seeded origin only. (5) A freshly added coin may show "Data source unavailable" until the worker fetches it; the retry covers the common case, P-S5b-1 measures it.

**Rollback:** revert the PR; the S5a API stays and the board returns to a flat grid; `layout.json` stays unused.

## Later batches (dependencies only)

S9 equities page (needs S5b: box, RSI row, layout section for equities); S10 optional scheduled task (`deploy/**`, RT4, S8, R12); group sort (AC-8r, deferred by the user: about 3 web files, 0.7 USD [estimate], backlog `screener-group-sort_NOTE_09-10-26.md`) and RSI/price zoom sync are follow-ups. Handoff to R12: `deploy/README.md` migration and backup notes should name `api\data\layout.json` as personal data next to `watchlist.json`, and say it follows a custom `WatchlistPath` of `deploy/config.example.psd1` as a sibling file (not done here: `deploy/**` is forbidden).

## Touchpoints

Changed: the owned files of S5a and S5b. Read only: `api/data/{freshness,equities_store}.py`, `api/analytics/indicators/rsi.py`, `api/scripts/seed_e2e_cache.py` (seeded stack: watchlist `[BTC, ETH, THIN]`, HYPE seeded, rising bars), `web/playwright.config.ts` (E2E root `/tmp/screener-e2e-cache`, API port 8001, web port 3100), `web/e2e/contrast.spec.ts`, `web/islands/simple-lines.svelte` (RSI y-domain re-fit; a constant series gets a 2-unit domain, so it draws).

## Public Contracts

- Added: `GET`, `POST`, `DELETE /api/layout/crypto` (`Layout`, `LayoutUpdate`); `CoinPanel.rsi` (`RsiReading`); `ChartSeries.rsi` (chart view only); `POST /api/watchlist` optional `group_id` and new 409 and 422 responses; git-ignored `api/data/layout.json` (personal data).
- Layout reads are a local file read: no provider call, so the page stays cached-first. Unchanged: `{"coins": [...]}` watchlist responses, the CORS allow-list (GET, POST, DELETE), board, spaghetti and chart-view fields, all timestamps already shipped. New timestamps (`saved_at`, `rsi[].timestamp`, `rsi.as_of`) are ISO UTC with a trailing `Z`. TS mirrors in `screener.ts` and `layout.ts` with contract tests.
- Security scan (STRIDE, quick): no auth, key or secret surface; Tailscale-only API; new writes are bounded (12 groups, 40-char names, 30 coins) and validated server-side; names and symbols render as React text (no HTML injection); a corrupt file is set aside, never executed; tampering by someone with file access is out of scope (personal use).

## Blast Radius

S5a 19 files, S5b 30 files (49 of the 100 limit); RT3: response models, a new personal-data file, one public route family, the shared board component. Other `fetch_ohlcv` consumers, the refresh worker, pairs, regime, narrative and onchain pages are untouched. Test-count effect: pytest 951 to 996, vitest 251 to 316 (34 to 41 files), seeded e2e screener+contrast 17 to 24, full e2e suite 65 to 72. S5b alone, from main fc12f27: pytest 1016 unchanged, vitest 335 to 400 (43 to 50 files), seeded e2e screener+contrast 17 to 24 (own gate), full e2e 72 to 79 (8 to 9 files).

## Acceptance Criteria

The criterion table (id, behaviour, strategy, proving test, gap-resolution) is in the Validate Contract skeleton; every id is linked to its gate and to its SPEC criterion. SPEC links: AC-S5a-1,2 = AC-26, D8; AC-S5a-3..5 = D2, AC-7 (persistence), AC-22 (store half); AC-S5a-6,7 = AC-3, AC-5, D5, D7; AC-S5b-1 = AC-3, AC-4, AC-5; AC-S5b-2 = D7; AC-S5b-3,4 = AC-7 (buttons instead of drag, user decision); AC-S5b-5 = AC-6, AC-23, AC-26; AC-S5b-6 = AC-22 (closes AC-S6-6); AC-S5b-11 = S11b live behaviour (U6) and AC-S5b-12 = T44 linked zoom (U7), neither has a SPEC criterion; AC-8r = AC-8 (group sort): Known-Gap residual, deferred by the user (Q1 A), backlog stub `screener-group-sort_NOTE_09-10-26.md`, gate stays CONDITIONAL.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G-S5a-1 store, router, cap, RSI tests | Fully-Automated | AC-26, D2, D8, AC-3, AC-5, AC-7 persistence (AC-S5a-1..8) |
| G-S5a-2..5 full pytest, vitest, tsc, islands | Fully-Automated | no regression, lockstep mirrors (AC-S5a-8, AC-S5a-9) |
| G-S5a-9, G-S5a-10 ignore rule, real-data guard | Fully-Automated | D2 personal data (AC-S5a-4) |
| G-S5a-12 e2e screener and contrast on the new API | Hybrid | board still renders with the new fields (AC-S5a-10) |
| P-S5a-1 PC check of routes and file location | Agent-Probe | D2 on the real stack (AC-S5a-4r) |
| G-S5b-1, G-S5b-2 vitest | Fully-Automated | AC-3, AC-4, AC-5, AC-6, AC-7, AC-22, AC-23, AC-26, D7 (AC-S5b-1..8, 11, 12) |
| G-S5b-9, G-S5b-10 e2e layout, screener, contrast, full suite | Hybrid | AC-6, AC-7, AC-22, AC-23, AC-26 end to end (AC-S5b-1..9, 11, 12) |
| P-S5b-1 PC, phone, keyboard, screen reader | Agent-Probe | usability on the real device and origin (AC-S5b-10r) |

## Risk Predictions (condensed 5-persona pass)

Security: the new write surface is small and validated; CORS unchanged. Performance: one file read per layout GET; RSI is one vectorised pass per displayed frame; the payload grows by one small object per coin. Data integrity: atomic file write, revision check, reconcile heals the two-file gap, a corrupt file is set aside, an over-30 list is untouched. User: every refusal has visible text, destructive actions need Confirm, keyboard users get focus and announcements. Maintainability: the sections registry gives S9 a slot, mirrors have contract tests, layout functions are pure and unit-tested.

## Implementation Checklist (atomic; one slice per worker)

**S5a:** 1 baseline (pytest, vitest, tsc, islands, e2e 17). 2 stubs for the 45 new tests, red run G-S5a-1. 3 `watchlist.py` cap and symbols. 4 `models/layout.py`, `data/layout.py`. 5 `routers/layout.py`, `main.py`. 6 `routers/watchlist.py`. 7 `models/screener.py`, `screener_board.py`. 8 TS mirrors, `.gitignore`. 9 real tests and the three listed test-file edits. 10 gates G-S5a-1..12 once after the last edit, `REAL-DATA` before and after the full pytest run. 11 report, PR, CI, tester.
**S5b** (after S5a merged): 1 baseline. 2 stubs for the 65 vitest and 7 e2e tests, red run G-S5b-1. 3 `layout-state.ts`, `rsi-format.ts` and tests. 4 `api/layout.ts`, `api/watchlist.ts` and tests. 5 `use-board-layout.ts`. 6 `CoinActions`, `AddCoinForm`, `CoinGroup`, `RsiChart`, `CoinPanel`, `DrillDownView`, `SpaghettiChart`. 7 `ScreenerBoard`, CSS. 8 existing-test edits (table), `ScreenerBoardLayout` and `CoinPanel` tests. 9 `layout.spec.ts`, `screener.spec.ts` test 1. 10 gates G-S5b-1..11 once after the last edit. 11 backlog stub, report, PR, CI, tester.

## Phase Completion Rules

`CODE DONE` = PR open with green gates in the report; `VERIFIED` only after independent confirmation (tester or CI on the head SHA, plus the tester's e2e run) AND the slice's PC probe. A slice may merge only when every gate including the e2e gates is green, CI is green on the head SHA and report heading 9 holds no open `needs_input` or `blocker`; otherwise it stops at `review`. S5a stays at `review` until P-S5a-1, S5b until P-S5b-1. A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` stops at `review`. After the S5b EVL the planner moves AC-S6-6 in the batch-2 plan from CONDITIONAL to PASS, marks the backlog note `spaghetti-toggle-persistence_NOTE_09-10-26.md` done, notes in the SPEC that drag-and-drop was replaced by buttons and that AC-8 is deferred, not delivered (AC-8r, backlog `screener-group-sort_NOTE_09-10-26.md`), and updates T40 and T41 in MASTER-PLAN in its UPDATE PROCESS (both are registered; planner steps, not slice files; this plan does not edit MASTER-PLAN).

## Resolved questions (answered by the user 09-10-26)

| # | Question | Answer | Effect |
|---|---|---|---|
| Q1 | SPEC US-3 / AC-8 also promise sorting each group by name, % change or RSI. Include it in S5? | RESOLVED A: defer to a small follow-up after the PC probe (pure web, about 3 files, 0.7 USD) | AC-8r named residual (Known-Gap, CONDITIONAL); backlog `screener-group-sort_NOTE_09-10-26.md`; no sort in S5a or S5b |
| Q2 | The estimate for S5 is 9.5-13.5 USD (two slices, tester included) against 3-6 USD in the INNOVATE table. Accept? | RESOLVED A: accept | fits the 60 USD ceiling (25.27 USD left; 12-16 USD would remain for S9 and S10); re-check before each spawn |

Decided without asking (reversible): layout save is `POST` not `PUT` (CORS pin); RSI needs the same 60 bars as the chart; unplaced coins go to the last group; deleting a group moves its coins to the previous group; groups max 12; native select as the menu; no 30/70 lines; the watchlist file write stays non-atomic.

## Validate Contract

(skeleton by the planner, completed by vc-validate-agent in PVL cycle 3, 09-10-26, and re-validated for S5b in PVL cycle 4, 10-10-26; the full records are "Validation record (PVL cycle 3)" and "Validation record (PVL cycle 4, S5b)" after the Open gaps below; verdict history in iteration reports 001 to 003 and s5b 004 to 006 and results.tsv; the two Known-Gap residual rows carry a proving strategy, never Known-Gap)
supersedes: 2026-10-09 (outer-pvl, PVL cycle 3, PASS; it had superseded cycle 1, CONDITIONAL F1-F8) - cycle 4 (2026-10-10) re-validated S5b against main fc12f27 after the S11 and T44 rebases; S5a is merged
Status: PASS (re-VALIDATE, PVL cycle 4, 10-10-26, S5b; 0 FAIL, 0 CONCERN outstanding after 4 CONCERNs were resolved in place; named residuals AC-8r, AC-S5b-8r, AC-S5a-4r, AC-S5b-10r)
Gate: PASS
generated-by: outer-pvl

### Test gates

gap-resolution: A proven now / B added by this plan's checklist / C deferred to a named later step / D backlog stub (residual, keep-active).

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-S5a-1 | cap 30: the 31st is refused 409 with the exact message; remove-then-add works; an existing coin is a no-op; a file over 30 is kept and new adds are blocked | Fully-Automated | G-S5a-1 `test_watchlist_cap.py` tests 1-6, 11 (8 threads) | B |
| AC-S5a-2 | invalid symbols are refused 422 and not stored (today `""` is stored) | Fully-Automated | G-S5a-1 `test_watchlist_cap.py` tests 7, 11 | B |
| AC-S5a-3 | layout store and API: default, recovered, round trip, revision conflict, validation, reconcile, hidden lines, other sections kept across save and reset, GET never writes, atomic write | Fully-Automated | G-S5a-1 `test_layout_store.py`, `test_layout.py` | B |
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
| AC-S5b-6 | a spaghetti toggle survives a reload (AC-22), stored in the server layout file and in no browser storage; closes AC-S6-6 | Fully-Automated | G-S5b-1 SpaghettiChart (+3), ScreenerBoardLayout; G-S5b-8 `S5b-nostore`; hybrid tests 2 (zoom kept), 6 | B (run: C) |
| AC-S5b-7 | no panel before board and layout settle, panel order stable after a timeframe change and the add retries; each failure and empty state has visible text; RSI row height equal for a number and N/A | Fully-Automated | G-S5b-1 ScreenerBoardLayout; hybrid tests 1, 7 | B (run: C) |
| AC-S5b-8 | every new control has an accessible name and works by keyboard; the default state passes the contrast audit; no verdict wording | Fully-Automated | G-S5b-1 role queries, G-S5b-8; hybrid G-S5b-9 | B (run: C) |
| AC-S5b-9 | no regression: the 10 screener e2e tests (test 1 edited) and 7 contrast routes | Hybrid | G-S5b-9, G-S5b-10 | B (run: C) |
| AC-S5b-11 | the S11 behaviour survives: a tick or an equal payload makes no island update, a failed refetch keeps panels, drill-down chart and RSI, the RSI title is Brussels time without `UTC` | Fully-Automated | G-S5b-1 `ScreenerBoardLive` (unedited assertions), `ScreenerBoardLayout`, `SpaghettiChart` test 1, `rsi-format`; G-S5b-8 `S5b-words`; hybrid G-S5b-9, G-S5b-10 (`live-refresh`, `brussels-time`) | B (run: C) |
| AC-S5b-12 | the T44 shared small-chart zoom survives every layout edit: reorder, move to a group, add and remove keep the one `sharedRange`; an added or moved chart adopts it; only a timeframe change clears it (U7; group edits, layout refetch and a rolled-back save cannot touch it: the state lives in `ScreenerBoard`, not in the layout) | Fully-Automated | G-S5b-1 `ScreenerBoardLayout` (U7 assertions folded in), `ScreenerBoardLinkedZoom` (unedited assertions); hybrid `layout.spec` test 2, G-S5b-10 (`live-refresh`, `screener` zoom test) | B (run: C) |
| AC-S5b-8r | on-demand states (rename input, remove confirm, open drill-down) pass the contrast audit | Hybrid | none today (Known-Gap residual): backlog `screener-ondemand-states-contrast_NOTE` (written by S5b); the audit reads the default state only | D (CONDITIONAL) |
| AC-8r | group sort by name, % change or RSI, unavailable values last and labelled (SPEC AC-8) | Hybrid | none in S5 (Known-Gap residual, deferred by the user, Q1 A): follow-up slice after S5b, vitest plus one seeded e2e; backlog `screener-group-sort_NOTE_09-10-26.md` (exists) | D (CONDITIONAL) |
| AC-S5b-10r | phone, keyboard-only and screen-reader use; Edge select/input look; deployed-origin POST/DELETE; 30-coin refresh; new-coin fill-in | Agent-Probe | P-S5b-1 | C |

### S5a exact gates (repo root; baselines 951 pytest, 251 vitest in 34 files)

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

### S5b exact gates (base main fc12f27, S11b and T44 merged: pytest 1016, vitest 335 in 43 files, e2e 72 in 8 files)

| Gate | Command | Expected |
|---|---|---|
| G-S5b-1 | `cd web && pnpm exec vitest run components/screener lib/__tests__/layout-state.test.ts lib/__tests__/rsi-format.test.ts lib/__tests__/layout-api.test.ts` | 116 passed in 14 files (51 existing in 7 files + 42 new in 4 under `components/screener`, plus 12 + 4 + 7) |
| G-S5b-2 | `cd web && pnpm test` | 400 passed in 50 files (335 + 59 + 3 + 3; 43 + 7) |
| G-S5b-3 | `cd web && pnpm exec tsc --noEmit --incremental false` | exit 0 |
| G-S5b-4 | `cd web && pnpm build:islands` | exit 0 |
| G-S5b-5 | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/test_no_verdict_symbols.py -q` | 2 passed (scans the new web files) |
| G-S5b-6 | `git diff --check` | exit 0, no output |
| G-S5b-7 | `S5b-scope` (it also excludes every fixture path), `FORBIDDEN`, `S-secret-scan` | print nothing |
| G-S5b-8 | `S5b-words`, `S5b-nostore`, `CAP-MESSAGE` (both lines) | `S5b-words` and `S5b-nostore` print nothing; `CAP-MESSAGE` prints 1 twice |
| G-S5b-9 | Gate convention 4 with `screener.spec.ts contrast.spec.ts layout.spec.ts` | 24 passed (10 + 7 + 7) |
| G-S5b-10 | Gate convention 4, no spec argument (full suite), once, after G-S5b-9 | all passed; 79 tests in 9 files (72 in 8 per `playwright test --list` at spawn, plus 7) |
| G-S5b-11 | red-first (convention 5): write the stubs, run G-S5b-1 on the untouched base, record the red run in report heading 6 | expected: 116 in 14 files, 65 failed, 51 passed; full `pnpm test`: 400 in 50, 65 failed, 335 passed |
| P-S5b-1 | user PC after pull, `deploy/build-web.ps1`, restart both tasks: arrange groups and reload; restart the API and reload; add and remove a disposable coin and note how long its box takes to fill; with 30 coins try a 31st; use keyboard only; open on a phone; check select and input look in Edge | layout survives both; refusal text shows; the box fills within one refresh; every control is reachable and readable |

### Scope and secret-hygiene commands (run from the repo root; the labels above refer to these)

```
# FORBIDDEN (every slice): nothing may match
git diff --name-only origin/main...HEAD | grep -E '^(CLAUDE\.md|AGENTS\.md|README\.md|\.claude/|\.github/|deploy/|api/scripts/|api/tests/deploy/|api/data/(lse_adapter|equities_store|cache|ccxt_adapter|freshness|refresh_worker)\.py|web/islands/|web/components/chart/|web/lib/(chart-viewport|island-loader)\.ts|process/MASTER-PLAN\.md|process/context/current-state\.md|process/archive/)'

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
git diff --name-only origin/main...HEAD | grep -vE '^(web/components/screener/(ScreenerBoard|CoinPanel|DrillDownView|SpaghettiChart|CoinGroup|AddCoinForm|CoinActions|RsiChart)\.tsx|web/lib/(layout-state|rsi-format|use-board-layout)\.ts|web/lib/api/(layout|watchlist)\.ts|web/app/globals\.css|web/components/screener/__tests__/(ScreenerBoard(Layout|Live|LinkedZoom)?|DrillDownView|SpaghettiChart|CoinPanel|CoinActions|AddCoinForm)\.test\.tsx|web/lib/__tests__/(layout-state|rsi-format|layout-api)\.test\.ts|web/e2e/(screener|layout)\.spec\.ts|process/general-plans/(active/screener-batch3_09-10-26/screener-batch3-s5b_REPORT|backlog/screener-ondemand-states-contrast_NOTE)_[0-9-]+\.md)$'

# S5b-words (S5b): nothing may match (`UTC` included, S11a; web/lib/api/*.ts left out: AbortSignal would match)
grep -niwE 'bullish|bearish|bull|bear|buy|sell|overbought|oversold|confidence|(out|under)perform(ing)?|risk-(on|off)|favorable|UTC' web/components/screener/{ScreenerBoard,CoinPanel,DrillDownView,SpaghettiChart,CoinGroup,AddCoinForm,CoinActions,RsiChart}.tsx web/lib/{layout-state,rsi-format,use-board-layout}.ts

# S5b-nostore (S5b): nothing may match (server file only, buttons and a menu, no drag-and-drop)
grep -nE 'localStorage|sessionStorage|indexedDB|document\.cookie|draggable|onDrag|onDrop' web/components/screener/{ScreenerBoard,CoinPanel,DrillDownView,SpaghettiChart,CoinGroup,AddCoinForm,CoinActions,RsiChart}.tsx web/lib/{layout-state,rsi-format,use-board-layout}.ts web/lib/api/{layout,watchlist}.ts

# CAP-MESSAGE (S5a runs the first line, S5b both): each prints 1 (S5b: a mismatch is a defect to report, not to fix)
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
| U5 | `os.replace` over `layout.json` on Windows while another program has it open | not measurable offline | P-S5a-1 | the save returns 500 (the browser sees a network error: a 500 carries no CORS header), the UI rolls back |
| U6 | whether coin boxes already grow when the chart island mounts (a shift this slice does not change) | not measured | none | not claimed; see "What this coverage does NOT prove" |
| U7 | whole-suite e2e count | 72 in 8 files at main fc12f27 (T44 changed e2e tests but added none; `playwright test --list`; 65 in 6 at `270f9ac`) | S5b worker | re-record at spawn; a differing baseline stops the worker |

### Not verifiable offline

Live Hyperliquid; real display, phone and keyboard-only use; Edge/Windows control rendering; the deployed origin; the PC cache and refresh timing; GitHub CI; every new test.

### What this coverage does NOT prove

- Seeded e2e proves the RSI row and drill-down are wired to the API value (100.0 for every seeded coin) and the N/A path (THIN); the per-timeframe numbers are proven by pytest with non-monotone frames, not by the browser.
- Layout shift is not measured. The tests prove that the panel order is unchanged by a timeframe change and the add retries (ScreenerBoardLayout test 3), that the RSI row height is equal for a number and for N/A, and that notices have a reserved region; any growth of coin boxes when the chart island mounts is pre-existing and unchanged.
- The contrast audit reads the default state only; the rename input, remove confirm and open drill-down are not audited (AC-S5b-8r, backlog stub, gate stays CONDITIONAL).
- Atomic write means a reader never sees a half-written `layout.json` and a crash keeps the previous file; it does not make `watchlist.json` atomic and does not cover the two files together.
- `REAL-DATA` proves no real personal file was created or changed on the machine that ran the gates; on the PC it is only as strong as the autouse redirects.
- Group sort (AC-8, now AC-8r) is deferred by the user (Q1 A), not dropped; drag-and-drop is replaced by buttons and a menu (user decision).

### Open gaps

No open questions (Q1 A and Q2 A resolved by the user 09-10-26). AC-8r (group sort, backlog `screener-group-sort_NOTE_09-10-26.md`) and AC-S5b-8r (on-demand states contrast, backlog stub) are named residuals. known-gap: real device and browser behaviour: probes P-S5a-1, P-S5b-1.

### Validation record (PVL cycle 3)

Status: PASS
Date: 09-10-26
date: 2026-10-09
generated-by: outer-pvl
supersedes: 2026-10-09 (outer-pvl, PVL cycle 1, CONDITIONAL, F1-F8) - cycle 3 has current evidence (the folded plan, re-read against the real code)
Code under test: origin/main `abda8e7` (`git diff 270f9ac origin/main -- api web` is empty, so api/ and web/ equal `270f9ac`; local HEAD `9014d86` adds process files only). Plan before the stamp: 459 lines, 85,271 B. Full evidence: `screener-batch3-pvl-iteration-003_REPORT_09-10-26.md`, `results.tsv` row 3; history in iteration 001 (verdict CONDITIONAL) and 002 (supplement fold).
Parallel strategy: sequential (one validator agent ran Layer 1 and Layer 2 inline; score 4 of 7: S1 api plus web, S2 API surface, S6 new personal-data file and public routes, S7 more than 5 files; no cross-talk needed; 1 agent, cost guard not triggered)
Rationale: dominant signal S6 (new write surface and personal data); every check was a read of the saved plan against real files plus targeted runs, so extra agents would only have re-read the same 85 KB.
Validators and targeted runs (no full suite; the cycle-1 baselines stand: pytest 951/2/5/0, vitest 251 in 34 files, tsc 0, build:islands 0, e2e 65): `validate-plan-artifact.mjs` 0 failures, 0 warnings before and after the stamp; `vitest run components/screener` 27 passed in 4 files (6+6+9+6); `playwright test --list` 65 in 6 files (contrast 7, narrative 17, onchain 16, pairs 9, regime 6, screener 10); pytest 22 passed (`test_main_cors.py` 10, `test_watchlist.py`, `test_watchlist_store.py`, `test_no_verdict_symbols.py` 2); scratch race reproduction of the cap check (below); scope, forbidden, secret and word regexes dry-run on the planned owned files and on stray files.

Resolved by the user 09-10-26 (recorded, not open): Q1 A (group sort AC-8 deferred; named residual AC-8r, backlog `screener-group-sort_NOTE_09-10-26.md` exists), Q2 A (the S5 estimate 9.5-13.5 USD accepted; programme ceiling 60 USD, 34.73 spent, 25.27 left, re-check before each spawn). Binding earlier decisions hold: server layout file, buttons plus menu (no drag-and-drop), cap 30 keep all and block new adds, RSI on boxes and drill-down, toggle persistence in the layout file, cached-first refresh, no verdicts.

Test gates (legacy line form; the 5-column table above is the contract; strategy values Fully-Automated | Hybrid | Agent-Probe only; Known-Gap is a named residual via gap-resolution D, never a strategy):
- Cap and symbols (AC-S5a-1, 2): [Fully-automated: G-S5a-1 `test_watchlist_cap.py` tests 1-7 and 11 (8 threads behind a Barrier)]
- Layout store, API, add/remove placement (AC-S5a-3, 4, 5): [Fully-automated: G-S5a-1 `test_layout_store.py`, `test_layout.py`, `test_watchlist_cap.py` tests 8-10; G-S5a-9, G-S5a-10]
- RSI numbers and mirrors (AC-S5a-6, 7, 8): [Fully-automated: G-S5a-1 `test_screener_rsi.py`, mirror tests `test_layout.py` 9 and `test_screener_rsi.py` 9; G-S5a-4]
- S5a regression (AC-S5a-9, 10): [Fully-automated: G-S5a-2..4] | [hybrid: G-S5a-12 seeded e2e 17; precondition Chromium plus seeded stack, runner the worker, CI does not run Playwright]
- S5b UI (AC-S5b-1..8, 11, 12): [Fully-automated: G-S5b-1, G-S5b-2 (65 new vitest, 400 in 50 files)] | [hybrid: G-S5b-9 `layout.spec.ts` 7 plus screener 10 plus contrast 7 (24)]
- S5b regression (AC-S5b-9): [hybrid: G-S5b-9, G-S5b-10 (79 in 9 files)]
- PC use: [agent-probe: P-S5a-1, P-S5b-1]
- [known-gap: documented] AC-8r group sort (deferred by the user, backlog `screener-group-sort_NOTE_09-10-26.md`), AC-S5b-8r contrast of on-demand states (backlog stub written by S5b), real device and browser behaviour (probes); each is gap-resolution D or C, none is a PASS claim.

Dimension findings:
- Infra fit: PASS - paths, env names (`SCREENER_LAYOUT_PATH`, call-time path rule), the e2e `rmtree` of the cache root, CORS set (`test_main_cors.py` 10 passed), `workers: 1` (layout.spec runs alone, afterEach restores the watchlist) and the reload hazard of `test_fresh_deploy_degrade.py` match real code.
- Test coverage: PASS - counts re-derived item by item: 15+10+11+9 = 45 pytest (951 to 996), 12+4+7 + 7+9+15+5 + 3+3 = 65 vitest (251 to 316, 34 to 41 files; G-S5b-1 = 27 existing + 65 = 92 in 11 files, recounted from the four real test files), 7 Playwright (17 to 24, 65 to 72); F7 and F8 tests are specified so they can fail; contract rows match the body.
- Breaking changes: PASS - every consumer of the changed symbols, routes and payload fields found by grep is listed or unaffected (pinned shapes `test_screener_no_verdict_contract.py:73-77,168-175`, `test_screener_freshness_payload.py`, `test_screener_gain_contract.py`, the two source-text scans, the three globals.css parsers, the 9 renders and e2e test 1).
- Security surface: PASS - no auth, key or secret surface; writes validated and bounded (12 groups, 40-char names, 64-item lists, 15-char symbols, 30 coins); Tailscale-only; a corrupt file is set aside, never executed.
- S5a feasibility: PASS - mechanically executable; highest-risk edit `screener_board.py` (must not change chart, chip or spaghetti output; stay-green tests listed) and the reload-safe use of `watchlist_store.<Name>`.
- S5b feasibility: PASS - highest-risk edit the controlled-hidden wiring of `SpaghettiChart` and `ScreenerBoard` (sorted key, gated on the layout; two automated tests plus the reviewer), then the global CSS against the contrast audit and the three CSS parsers.
- Envelopes: PASS - recomputed from the saved file: S5a 82 lines 20,453 B (room 2,104 B), S5b 73 lines 20,363 B (room 2,194 B), union 36,200 B (13,643 B over), CLAUDE.md 13,443 B; every range edge lands on its intended line; independent drafts that cite lines measure 1,860 B (S5a) and 1,988 B (S5b), the plan's drafts 1,962 B and 2,053 B.

Findings history (cycle 1, folded by supplement cycle 1, verified in cycle 3 against the saved file; line numbers are the saved file's):
| # | Fold verified at | Cycle 3 evidence |
|---|---|---|
| F1 AC-8 residual | row AC-8r 264, 23, 35, 174, 192, 218, 372, 376; stub `process/general-plans/backlog/screener-group-sort_NOTE_09-10-26.md` exists | the stub says deferred by the user (Q1 A), dependencies, one-shot design, 0.7 USD; no sort work in either slice |
| F2 Q1/Q2 | 11, 82, 220-225, 376, 448 | no "open" wording outside the cycle-1/2 history; the range table was re-derived last |
| F3 G-S5b-11 | 299 | recounted: 27 existing (6+6+9+6, `vitest run components/screener` printed 27 in 4 files) + 65 stubs = 92 in 11 files; full 316 in 41 |
| F4 DELETE | 50, 52, 95, 113, 114, 245 | only the `crypto` section, file removed only when none remains; tests 13 and 7 assert it |
| F5 .bad | 45, 50, 95, 113 | `os.replace` plus the source-text check (`os.replace(` present, `os.rename(` absent) in test 12 |
| F6 cap race | 44, 94, 115, 243, 440 | scratch reproduction: unlocked, 8 threads at 29 coins stored 30 to 31 coins with JSONDecodeError in 5 of 5 trials; the planned lock gives exactly 1 success, 7 `WatchlistFullError`, a parsable file of 30 in 5 of 5; 40 threads from 0 keep exactly 30 |
| F7 no re-mount | 134, 137, 160, 162, 163, 166, 259 | sorted key, gated on the layout; vitest mount-count test and the e2e zoom-survives-reorder test can fail (see report) |
| F8 order stable | 127, 160, 260, 368 | claim reworded; test 3 records the order across a timeframe change and the retry timers |
| a-g | 54, 68, 94, 95, 98-99, 110, 114, 133-134, 143, 152, 163, 174, 218, 357, 436, 450-459 | `RsiPoint`, `length: number`, MAX_LIST 64 and MAX_SYMBOL_LEN 15, confidence-word ban at `test_screener_no_verdict_contract.py:29-33,168-175`, stay-green scans `test_exchange_attention.py:157` and `test_history.py:286`, comment-word rule, `exact: true`, T40/T41 note |

Cycle 3 finding N1 (CONCERN, resolved in place, VALIDATE-owned table): rows AC-S5b-8r and AC-8r (lines 263-264) carried "Known-Gap residual" in the `strategy` column, which the contract schema forbids (Known-Gap is a named residual via gap-resolution D, never a strategy; batch 2 AC-S6-6 and R12 carry a real strategy). Both cells now read `Hybrid` (the planned proving type) and the proving-test cell says "none today (Known-Gap residual)" with the backlog stub. No plan-body line, no count and no envelope-range byte changed.

Advisories (none blocks; planner or worker notes):
a. Line 11, line 19 and Resume lines 446-448 still describe the pre-stamp state ("no PASS stamp", "PVL cycle 2 pending", "contract PENDING"); the planner refreshes them after this stamp (R12 precedent). They sit outside every envelope range.
b. Envelope: cite lines, never copy; measure with `wc -c` before spawn and re-measure CLAUDE.md (the S5b slack of about 141 B is lost if CLAUDE.md grows by that much before the S5b spawn); trimming order is the budget line, then the autonomy line, never a range. The S5b envelope should also name `api/routers/watchlist.py` (body keys `symbol`, `group_id`, 409 `detail`) and `web/lib/types/{layout,screener}.ts` as extra code reads, because C3 and C5 are outside the S5b ranges (code files do not count against the plan-byte cap).
c. `DELETE /api/layout/crypto` on an unreadable file is not specified (C2 reads it as `recovered`; reset of a corrupt file could raise or leave it). Say "moves it to `.bad` (or removes it) and returns the default" and assert it in test 12 or `test_layout.py` 7; e2e test 7's afterEach calls this DELETE on a garbage file and the S5b worker cannot edit `api/**`.
d. SpaghettiChart test 1: `vi.doMock` after a static import does not intercept `loadIslands`; the worker needs `vi.resetModules()` plus a dynamic `await import(...)` of the component (or `vi.spyOn` on the module) inside that test. The test is red today (the `hidden` prop is ignored, so `aria-pressed` is wrong) and fails for a naive new-Set-per-render implementation (two mounts), so it is not vacuous.
e. ScreenerBoardLayout test 3: make the board stub return a different coin order for the second timeframe, so an implementation that follows the board order (not the layout) fails.
f. `watchlist.py` `_save_raw` stays non-atomic: with the planned lock, a second PROCESS reading while an add writes saw 146 unparsable reads in 1.5 s; with temp file plus `os.replace` it saw 0. Atomic replace keeps the file valid for readers but cannot stop two writing processes from losing updates (3 processes x 12 threads: 27 of 36 stored with lock only, 19 with lock plus replace, cap not enforceable across processes), which is out of scope (one API process). Optional 7-line hardening, already a Test Infra note.
g. A legacy watchlist of more than 64 coins would make every layout POST a 422 (`MAX_LIST = 64`); not realistic for a 30-coin product. AC-S5a-9 label A ("proven now") is the baseline only; the gates G-S5a-2..4 re-prove it at EXECUTE. Neither CI nor the gates run `next build`.

What This Coverage Does NOT Prove (additions from PVL cycle 3): no automated test exercises two real processes writing `watchlist.json` (threads in one process only); the island's zoom survival is proven only in the seeded browser (e2e test 2) plus the mocked mount count, never in a real island under jsdom; Windows `os.replace` behaviour with another program holding the file open is a PC probe (P-S5a-1, U5); the 65-test e2e baseline was measured on one machine; seeded RSI is 100.0 on every coin so per-timeframe numbers are proven by pytest only; group sort is not delivered (AC-8r); contrast of the rename input, remove confirm and open drill-down is not audited (AC-S5b-8r).

Open gaps: AC-8r (group sort, backlog `screener-group-sort_NOTE_09-10-26.md`), AC-S5b-8r (on-demand contrast, backlog stub written by S5b), probes P-S5a-1 and P-S5b-1 (named residuals, user PC); advisories a-g above; none is a FAIL or an unresolved CONCERN.
Accepted by: n/a - no CONCERN outstanding to accept (0 FAIL, 0 CONCERN after N1 was resolved in place); the residuals are named, not accepted concerns; the user's Q1 A and Q2 A answers are recorded above.

### Validation record (PVL cycle 4, S5b re-validation)

Status: PASS
Date: 10-10-26
date: 2026-10-10
generated-by: outer-pvl
supersedes: 2026-10-09 (outer-pvl, PVL cycle 3, PASS) - cycle 4 re-validated the S5b section after the S11 and T44 rebases; the S5a text and the cycle 3 record above are history (S5a is merged)
Code under test: main fc12f27 (T44 merged); the checkout `claude/pensive-albattani-ou0cgv` adds process files only (`git diff fc12f27 HEAD -- api web` is empty). Plan before the cycle 4 fixes: 519 lines, 99,423 B. Full evidence: `screener-batch3-s5b-pvl-iteration-004_REPORT_10-10-26.md` (first pass), 005 (fix cycle), 006 (re-verification); `results.tsv` rows 4 to 6.
Parallel strategy: sequential (one validator ran Layer 1 and Layer 2 inline; score 2 of 7: S6 a public API surface and a personal-data file consumed, S7 30 files; no cross-talk needed; 1 agent, cost guard not triggered)
Rationale: dominant signal S7; every check was a read of the saved plan against the real files plus counted runs, so extra agents would only have re-read the same 99 KB.
Runs (read-only, nothing committed, no source edit): `validate-plan-artifact.mjs` 0 failures, 0 warnings before and after; `vitest run components/screener` 51 passed in 7 files (6 + 6 + 8 + 10 + 3 + 12 + 6); `pnpm test` 335 passed in 43 files; `playwright test --list` 72 tests in 8 files (contrast 7, brussels-time 3, live-refresh 4, narrative 17, onchain 16, pairs 9, regime 6, screener 10); full pytest 1016 passed, 2 skipped, 5 deselected, no xfail (272 s; `api/data/layout.json` and `watchlist.json` were not created); `tsc --noEmit` exit 0; `S5b-words` and `S5b-nostore` print nothing on the four existing files; `CAP-MESSAGE` first line prints 1; `S5b-scope` and `FORBIDDEN` dry-run on the 30 planned files print nothing, and `S5b-scope` prints all of 30 stray T44/S11/api/process files (`FORBIDDEN` alone misses `chart-viewport.test.ts` and `live-refresh.spec.ts`, which `S5b-scope` catches); `git diff --check` 0; ASCII only.

Test gates: the 5-column table above is the contract (AC-S5b-1..12 unchanged in strategy); counts re-derived on fc12f27: 12 + 4 + 7 + 7 + 9 + 15 + 5 + 3 + 3 = 65 vitest (335 to 400, 43 to 50 files; G-S5b-1 = 51 in 7 + 42 + 23 = 116 in 14; red run 116 in 14 with 65 failed, 51 passed), 7 Playwright (G-S5b-9 24; G-S5b-10 72 to 79 in 8 to 9 files), pytest 1016/2/5 unchanged.
- S5b UI (AC-S5b-1..8, 11, 12): [Fully-automated: G-S5b-1, G-S5b-2] | [hybrid: G-S5b-9]
- S5b regression (AC-S5b-9): [hybrid: G-S5b-9, G-S5b-10]
- PC use: [agent-probe: P-S5b-1]
- [known-gap: documented] AC-8r, AC-S5b-8r, real device and browser behaviour (named residuals, gap-resolution D or C, none is a PASS claim)

Dimension findings:
- Infra fit: PASS - the cited lines of `ScreenerBoard.tsx` (L41-49, 58-72, 94-105 with the T44 props at 101-102, 107, 110-117) and `CoinPanel.tsx` (L15-17, 36, 56-62) match the file; `LiveProvider`, `FreshnessStrip`, `use-simple-lines`, `island-loader`, `MiniChart`, `simple-lines.svelte` (`linkedRange` applied at mount through `keepRange`, resetting only on a timeframe or line-key change) behave as U6 and U7 say; `api/routers/layout.py`, `watchlist.py`, `web/lib/types/{layout,screener}.ts` carry the S5a shapes; the seeded e2e root and the sibling `layout.json` rule match `playwright.config.ts`; `reset_layout` on a garbage file moves it to `.bad` and returns the default (advisory c of cycle 3 is closed by the merged S5a).
- Test coverage: PASS - arithmetic above; stub sites counted in the real files: `ScreenerBoard.test.tsx` 10 renders, `ScreenerBoardLive.test.tsx` 12 tests and 2 `<ScreenerBoard` sites in `setup`, `ScreenerBoardLinkedZoom.test.tsx` 3 tests and 3 render sites (the first `render(` at line 119, its `<ScreenerBoard` at 121); no other file renders `ScreenerBoard`; every bullet's semicolon clauses equal its declared count after F1; AC-S5b-11 and AC-S5b-12 each name a gate (G-S5b-1 files, G-S5b-8, G-S5b-9, G-S5b-10).
- Breaking changes: PASS - the breaks table matches the real set (10 + 2 + 3 stub sites, `screener.spec.ts` test 1 `> div`); stay-green: `chart-viewport.test.ts`, `live-refresh.spec.ts`, `brussels-time.spec.ts` (`main` text has no `UTC` word; the RSI title is an attribute), `contrast.spec.ts`, the `globals.css` parsers; hidden-break traps are listed in advisory c.
- Security surface: PASS - unchanged from cycle 3: no auth, key or secret surface; the new web clients only call GET, POST, DELETE routes the CORS allow-list already holds.
- S5b feasibility: PASS - highest-risk edit the loading gate and the controlled-hidden wiring in `ScreenerBoard` (hooks and the render-time `sharedRange` reset stay above the gate; sorted key in `SpaghettiChart`), then the global CSS against the contrast audit; U2, U4, U5, U6 and U7 are implementable on the real code (see advisories c and e).
- Envelopes: PASS - recomputed from the saved file: S5b ranges `60, 62, 64-65, 68, 132, 134-141, 143-148, 150-158, 160-169, 293, 297-307, 312-314, 319-320, 335-336, 338-339, 341-342, 344-347` = 66 lines, 20,429 B, room 36,000 - 13,443 - 20,429 = 2,128 B (2,450 B with operating-instructions.md, 6,678 B, cap 43,000); CLAUDE.md 13,443 B (`wc -c`); S5a set (merged) re-mapped to this file 20,238 B; union 38,240 B, 15,683 B over the cap. No goal, verdict or signal wording sits in any S5b range (scanned).

Findings (all resolved in place before the stamp; the fix cycle is iteration 005):
| # | Class | Finding | Fix |
|---|---|---|---|
| F1 | CONCERN | The `ScreenerBoardLayout` bullet (line 166) listed 17 semicolon clauses against a declared 15 while every other bullet matches clause for clause; the S11 rebase had split the remove/add clause and the board-failure clause without raising the count, so a worker writing 17 tests would see 402, not 400, and stop at `needs_input` | two pairs joined with ", and" (+8 B in the S5b ranges); clause count 15 |
| F2 | CONCERN | Stale contract state: the header still carried the cycle 3 stamp over an S5b marked NEEDS RE-VALIDATION; lines 11, 19, 127, Resume 3 and 5 and the goal block described older states; line 224 said T40 and T41 are unregistered (MASTER-PLAN lists both); AC-S5b-11 and AC-S5b-12 were missing from Verification Evidence, the legacy line form and the SPEC-link list | refreshed in place; one stamp line remains in the header; goal block re-issued as an update for S5b |
| F3 | CONCERN | The envelope pointer for C4 named `api/routers/layout.py`, which holds no 422 rule; the group id pattern `GROUP_ID_RE`, the 12-group and name rules live in `api/data/layout.py`, and S5b generates group ids | pointer names both files (line 512, outside every range) |
| F4 | CONCERN | The AC-S5b-12 row claimed group edits, layout refetch and a rolled-back save keep the range, but the U7 folds cover move, move-to-group, add/remove and timeframe | row says those cases hold by construction (the range is `ScreenerBoard` state, never layout state); proof stays the folds, `ScreenerBoardLinkedZoom`, `layout.spec` test 2 |

Advisories (none blocks; planner or worker notes):
a. U1 no longer says accessible names include the coin or group. Coin controls are covered (`CoinActions` test 1); group buttons (Rename, Move group, Delete group) have no naming test. The S5b envelope should say "names include the coin or group".
b. The envelope should say what the backlog stub holds: the contrast of the rename input, the remove confirm and the open drill-down is not audited (AC-S5b-8r).
c. Hidden-break traps for the worker: `ScreenerBoardLive` test 1 asserts `vi.getTimerCount()` is 0 (no timer exists unless an add retry is pending); the Live drill-down test asserts the island mounts in `drilldown-view` grow by exactly 1 (design 4 mounts `RsiChart` only for a non-empty RSI series; the fixture has `rsi: []`, so the empty-series path must not mount a chart).
d. The `S5b-words` note "AbortSignal would match" is wrong: the real hazard is `Date.UTC(` (matches `UTC` as a word, as in `brussels-time.ts`); no S5b file needs it and `web/lib/api/*.ts` stays out of the scan. Harmless.
e. AC-S5b-11 "a failed refetch keeps ... RSI": the existing Live test proves the price chart stays beside `drilldown-error`; the RSI chart reads the same `view` state, and no test names it. By construction, not by test.
f. CLAUDE.md is 13,443 B; the S5b spare is 128 B against the 2,000 B envelope guide, so re-measure with `wc -c` before the spawn.
g. P-S5a-1 (T40 at review) is a PC probe outstanding for S5a; it does not gate the S5b spawn.
h. The cycle 3 "Findings history" line numbers and advisory a describe the cycle 3 file; advisory a of cycle 3 is closed by the refresh above.

What This Coverage Does NOT Prove (additions from PVL cycle 4): no S5b test or file exists yet, so every S5b vitest and Playwright figure is arithmetic from the plan against counted base runs (51 in 7, 335 in 43, 72 in 8), not an observed run; the island's zoom survival under reorder and move is proven only by the mocked island in jsdom plus the seeded browser (`layout.spec` test 2), never in a real island under jsdom; group-button names and the RSI chart staying beside `drilldown-error` are not named by any test (advisories a and e); the S5b worker's own read set was measured, not tried (the envelope is not written).

Open gaps: AC-8r (group sort, backlog `screener-group-sort_NOTE_09-10-26.md`), AC-S5b-8r (on-demand contrast, backlog stub written by S5b), probes P-S5a-1 and P-S5b-1 (named residuals, user PC); advisories a-h above; none is a FAIL or an unresolved CONCERN.
Accepted by: n/a - no CONCERN outstanding to accept (0 FAIL; the 4 CONCERNs F1-F4 were resolved in place and re-verified); the residuals are named, not accepted concerns; the user's Q1 A and Q2 A answers stand.

## Autonomous Goal Block

SESSION GOAL: (UPDATE - S5b) screener batch 3, S5b only: layout UI, add/remove coins, RSI display and spaghetti toggle persistence, on main fc12f27 or later (S5a merged a3ffd98; S11a, S11b and T44 merged); one worker, opus, capped subagent lane; group sort (AC-8) is deferred by the user and is not part of this goal
Charter + umbrella plan: N/A - single plan (SPEC personal-tracker-realignment_SPEC_02-10-26.md; no umbrella plan with a Stable Program Goal)
Autonomy: S5b validated PASS (PVL cycle 4, 10-10-26, after PVL cycles 1 and 3 for the whole plan). EXECUTE needs the user's explicit "ENTER EXECUTE MODE". The planner then writes the S5b envelope (master-planner.md section 8, at most 8,000 bytes, a pointer list citing the "Envelope line ranges" table; it names the S5b-scope regex as the Owned list and the code reads api/routers/layout.py, api/data/layout.py, api/routers/watchlist.py and web/lib/types/{layout,screener}.ts; S5b room 2,128 B, envelope under about 2,000 B; measure with wc -c and re-measure CLAUDE.md at spawn), saved as `screener-batch3-s5b_REF_<dd-mm-yy>.md`, and spawns S5b only (opus; subagents sonnet, capped lane: 3 subagents, 15 USD, one level). The worker runs gates once after the last edit, records the red run, runs the seeded e2e (CI does not run Playwright) before any merge, and stops at needs_input when an observed count differs from the plan arithmetic or the same failure occurs twice.
Hard stop conditions / safety constraints:
- No envelope or worker before the user's "ENTER EXECUTE MODE".
- A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` stops at review; S5b edits no `api/**`, `web/islands/**`, `web/lib/types/*`, T44 or S11 file (S5b-scope and FORBIDDEN print nothing).
- No worker merges with an open needs_input or blocker; the seeded e2e gates (G-S5b-9, G-S5b-10) run on the head SHA before any merge, NOT-RUN stops at needs_input.
- Push, merge, deploy, branch deletion, or spend above 15 USD per slice or 60 USD in total (25.27 USD left at plan time; re-check in MASTER-PLAN before the spawn) needs the user's approval.
- PC probe P-S5b-1 is the user's and is never claimed by a worker; S5b stays at review until its probe.
Next phase: EXECUTE: process/general-plans/active/screener-batch3_09-10-26/screener-batch3_PLAN_09-10-26.md
Validate contract: process/general-plans/active/screener-batch3_09-10-26/screener-batch3_PLAN_09-10-26.md (inline, validated PASS, PVL cycle 4 for S5b)
Execute start: S5b: `cd web && pnpm exec vitest run components/screener lib/__tests__/layout-state.test.ts lib/__tests__/rsi-format.test.ts lib/__tests__/layout-api.test.ts` red run on the untouched base with the stubs (G-S5b-11: 116 in 14 files, 65 failed, 51 passed), then the code and all gates once | e2e: G-S5b-9, G-S5b-10 | probe: P-S5b-1 on the user PC | high-risk pack: no

## Worker envelopes

Written by the planner AFTER the user's explicit ENTER EXECUTE MODE: one per slice, at most 8,000 bytes, a pointer list citing the sub-range table below, saved as `screener-batch3-s{5a,5b}_REF_<dd-mm-yy>.md` in this task folder (master-planner.md section 8). S5b's envelope is issued after the S5a merge SHA exists. Each envelope repeats: the e2e gates are required and NOT-RUN stops at `needs_input`; no merge with an open `needs_input` or `blocker`; counts that differ from the plan arithmetic stop the worker; the lane (3 sonnet subagents, 15 USD, one level) and the budget line of the slice. Each envelope names the 11 report headings inline (the template file is outside the read set), names the S5b-scope regex as the Owned list, cites the plan by the line numbers of the table below instead of copying text, and stays within the room in the table (S5b room 2,128 B; say under about 2,000 B).

## Test Infra Improvement Notes

(none identified yet) Candidates: a reader of `watchlist.json` can still see a half-written file during an add (the lock covers only the writers; an atomic `_save_raw` would close it); a CI job for the seeded Playwright specs (three UI slices have now needed local e2e runs that CI cannot confirm); an atomic write for `watchlist.json` (`_save_raw` is non-atomic, pre-existing); a Playwright project at DPR 2 and a layout-shift (CLS) check; a shared fake-exchange module.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/screener-batch3_09-10-26/screener-batch3_PLAN_09-10-26.md`
2. Last completed step: PLAN supplement cycle 1 (09-10-26) folded PVL cycle 1 findings F1-F8 and advisories a-g (S5 split into S5a and S5b, hardened against the code at `270f9ac`); backlog stub `process/general-plans/backlog/screener-group-sort_NOTE_09-10-26.md` written; counts unchanged (45, 65, 7).
3. Validate-contract status: PASS (PVL cycle 3 for the whole plan, 09-10-26; PVL cycle 4 re-validated S5b on 10-10-26 after the S11 and T44 rebases); the goal block is below. Named residuals AC-8r, AC-S5b-8r, AC-S5a-4r, AC-S5b-10r.
4. Context loaded: SPEC, INNOVATE, decisions.md, current-state.md, architecture.md, operating-instructions.md, all-tests.md, batch-2 plan (and the batch-1 shape), batch-2 PVL iterations 001, 003, 005 and the S6 and T39 reports, backlog notes, the PVL iteration reports of this task, real code at origin/main `270f9ac` (watchlist store and router, screener router/board/models, ScreenerBoard, CoinPanel, DrillDownView, SpaghettiChart, island props, seeder, Playwright config, e2e specs, CORS and real-data tests).
5. Next step for a fresh agent: S5a is merged (a3ffd98); S5b was edited after the S11b and T44 merges (see "Changes since validation (S5b)") and re-validated in PVL cycle 4. Wait for the user's explicit "ENTER EXECUTE MODE", then the planner writes the S5b envelope (see "Worker envelopes" and the last table) and spawns S5b only (T41 is registered in MASTER-PLAN as proposed).

## Changes since validation (S5b, 10-10-26)

Edited after the PASS stamp above, against main fc12f27 (S5a a3ffd98, R12, S11a, S11b, T44 merged; item 9 is the T44 sub-list; sources: batch-4 plan "Hand-over to S5b", S11b report, the merged code). The validator re-checks these and re-stamps; S5a text, the validation record and the stamp were not touched.
1. Baselines: gate convention 2, the S5b gates heading, U7, Blast Radius and the two coverage lines now read pytest 1016/2/5, vitest 331 in 42 files, e2e 72 in 8 files, re-based to 335 in 43 by item 9 (the old 999, 251/34, 316/41, 65/6 and 72/7 figures are gone from S5b text).
2. Owned and touches: `ScreenerBoardLive.test.tsx` added to Owned, `S5b-scope`, the breaks table; S5b was 29 touches (14 + 8 + 5 + 2), total 48 (30 and 49 after item 9) (TL;DR, touches, budget table and Blast Radius lines). Forbidden now names the S11 files (live-poll, same-data, use-simple-lines, spaghetti-lines, brussels-time, chart-freshness, api/screener and api/refresh, components/chart, LiveProvider, FreshnessStrip, BtcLegChart).
3. U2, U4, U5 reworded for the live board (settled once, failure keeps panels, `reloadToken` in the effect deps, `useSimpleLines` update in place); new U6 lists the S11 interactions to keep (derived order, stable `memo` props, in-place island update and zoom, failed refresh keeps chart, abort/cancel, Brussels time, reuse `.visually-hidden`).
4. Design 1-4: own 10 s timeout (`getJson` is private), `ScreenerBoard` keeps its `useLiveData` effect, `RsiChart` uses `useSimpleLines`, RSI title is Brussels time (`formatDateTimeZone`), no `UTC`; `CoinPanel` stays `memo`.
5. Breaks table: ScreenerBoard.test has 10 renders (not 9); new row for ScreenerBoardLive (stub at both `setup` sites); screener.spec row notes `live-refresh`, `brussels-time`, `contrast` stay unedited.
6. Tests: counts unchanged (65 + 7). rsi-format title check, ScreenerBoardLayout tick/failure assertions (folded into existing items), SpaghettiChart test 1 (resetModules, dynamic import, zero `update` calls) and layout.spec poll-tick note reworded.
7. New gate text: `UTC` added to the `S5b-words` pattern (G-S5b-8, convention 10 note), criterion row AC-S5b-11 (contract table, proven by G-S5b-1, G-S5b-8, G-S5b-9, G-S5b-10; `S5b-scope` adds `ScreenerBoardLive`).
8. Envelope line ranges and byte figures (lines 72, 444, the table) re-derived from this saved file (line 72, the autonomy line, the envelope paragraph and the table; S5a and S5b sets both shifted; S5b no longer reads the Goal, C4, conventions 3, 8 and 9, or Failing stubs, and S5a keeps its old content). The S5b envelope should say ASCII only and name the code reads above.
9. T44 (PR #50, merge fc12f27; sources: `screener-zoom-sync_REPORT_10-10-26.md`, the merged diff of the 11 files):
   a. Baselines: vitest 331 in 42 to 335 in 43 files (+3 `ScreenerBoardLinkedZoom.test.tsx`, +1 `chart-viewport.test.ts`); e2e stays 72 in 8 (T44 edited the `screener.spec.ts` zoom test and `live-refresh.spec.ts`, added none); pytest 1016/2/5 (nothing under api/). Re-based in convention 2, the S5b gates heading, G-S5b-1, G-S5b-2, G-S5b-11, U7 (fact), Blast Radius, the coverage line and the arithmetic below.
   b. Code lines re-cited from the merged files (the plan carried none before; they now live in U7): `ScreenerBoard.tsx` `sharedRange` and the timeframe reset L41-49, `useLiveData` board effect L58-72, group container and `CoinPanel` call L94-105 (T44 props L101-102), `SpaghettiChart` L107, `DrillDownView` L110-117; `CoinPanel.tsx` props L15-17, `memo` signature L36, `MiniChart` call L56-62. `simple-lines.svelte` applies a `linkedRange` when an island mounts (clamped by `keepRange`), so a remounted or added panel adopts the shared zoom with no island change.
   c. New rule U7 (shared zoom lives at board level; reorder, move, group edits, add and remove must not reset it; a new coin adopts it; a timeframe change clears it), design 3 pointer, criterion row AC-S5b-12. Proof is folded into existing tests, so the counts stay: `ScreenerBoardLayout` 15 (move, move-to-group, remove/add and timeframe items) and `layout.spec.ts` 7 (test 2: ETH follows a BTC zoom, also after the reorder).
   d. `ScreenerBoardLinkedZoom.test.tsx` is in the G-S5b-1 subset (it sits under `components/screener`): 48 in 6 files becomes 51 in 7, so G-S5b-1 is 116 in 14 and its red run 116 in 14 with 65 failed. It renders `<ScreenerBoard` 3 times without `fetchLayout`, so it joins Owned and the breaks table with the same `fetchLayoutStub` (3 sites, no assertion changed); it is in `S5b-scope`.
   e. Forbidden names the T44 files (`simple-lines.svelte`, `entry.js`, `MiniChart.tsx`, `island-loader.ts`, `chart-viewport.test.ts`; S5b needs none) and the FORBIDDEN command adds `web/components/chart/`. Unedited and must stay green: `chart-viewport.test.ts`, `live-refresh.spec.ts`, the `screener.spec.ts` zoom test.
   f. Touches: S5b 30 (14 + 8 + 6 + 2), total 49 (TL;DR, line 72, budget table, Blast Radius). Read-set: Owned (line 131) and the conv 5 line leave the S5b worker set (the `S5b-scope` regex is the exact owned list; G-S5b-11 carries red-first); wording trimmed in U1, U5, conv 10, design 2 and 4, G-S5b-5, 10, 11; the envelope ranges below were re-derived from this saved file: S5b 20,421 B, room 2,136 B (was 20,327 and 2,230), S5a set recomputed 20,238 B, union 38,232 B. Validator cycle 4 (F1 fix, +8 B): S5b 20,429 B, room 2,128 B, union 38,240 B.

Arithmetic, re-based on main fc12f27 (S5b new tests: lib 12 + 4 + 7 = 23; components 7 + 9 + 15 + 5 = 36; added to existing files 3 + 3 = 6; total 65 in 7 new files):

| Gate | Base | Added | Expected end |
|---|---|---|---|
| G-S5b-2 vitest | 335 in 43 files | 23 + 36 + 6 = 65 tests, 3 + 4 = 7 files | 400 in 50 files |
| G-S5b-1 vitest subset | 51 in 7 files (6 BtcLeg + 6 DrillDown + 8 FreshnessStrip + 10 ScreenerBoard + 3 ScreenerBoardLinkedZoom + 12 ScreenerBoardLive + 6 Spaghetti) | 36 + 6 = 42 tests, 4 files; lib 23 in 3 files | 51 + 42 + 23 = 116 in 7 + 4 + 3 = 14 files |
| G-S5b-11 red run (stubs, untouched base) | subset 51 passing in 7 files; full 335 in 43 | 65 stub tests fail | subset 116 in 14 (65 failed, 51 passed); full 400 in 50 (65 failed, 335 passed) |
| G-S5b-9 e2e own specs | 10 + 7 | layout 7 | 24 (brussels-time 3 and live-refresh 4 run only in G-S5b-10) |
| G-S5b-10 e2e full | 72 in 8 files | 7 in 1 file | 79 in 9 files |
| pytest | 1016/2/5 | 0 | 1016/2/5 |

## Envelope line ranges (re-derive with `grep -n '^## \|^### '` at spawn time; worker cap 36,000 B = CLAUDE.md 13,443 counted once + envelope (cap 8,000) + plan bytes)

Line numbers refer to this file as saved. This table is the last block, so editing it moves no earlier line; if any earlier line is edited, re-derive the numbers with the grep named in the heading and recount the bytes (each line plus its newline). Each set holds: the decision lines the slice needs, Gate conventions 1-10 (S5b: 2, 4, 6, 7, 10; convention 8 ASCII-only and probe rules go in the S5b envelope), the slice Goal (S5a only), Owned and Forbidden lines (S5b: the Forbidden line only; its Owned list is the `S5b-scope` regex), its design, existing-tests-that-break and tests lines, its exact gates without the PC probe, the command-block lines it uses, and (S5a only) Failing stubs; for S5b convention 5 and G-S5b-11 carry the red-first rule. A worker never needs: Name check, Costs, Risks, Rollback, the criteria rows (PVL and the tester use them), PC probes, Red-today evidence, Resolved questions. Decisions: S5a reads C2-C6 (lines 50-54); S5b reads no decision line (10-10-26: C4, line 52, would cost 684 B): its design lines restate the cap message (design 2), and the envelope names the code reads `api/routers/layout.py` and `api/data/layout.py` (C4: the 422 rules, `GROUP_ID_RE`), `api/routers/watchlist.py` (C3, C5: body keys `symbol`, `group_id`, 409 `detail`) and `web/lib/types/{layout,screener}.ts`; code files do not count against the plan-byte cap.

| Slice | Plan ranges (lines) | Plan bytes | Envelope room (cap 36,000) |
|---|---|---|---|
| S5a | merged (a3ffd98); its ranges are no longer maintained and only feed the union figure in line 72 | 20,238 | n/a |
| S5b | 60, 62, 64-65, 68, 132, 134-141, 143-148, 150-158, 160-169, 293, 297-307, 312-314, 319-320, 335-336, 338-339, 341-342, 344-347 | 20,429 | 2,128 |

Computed as 36,000 - 13,443 (CLAUDE.md) - plan bytes. A filled envelope stays under about 2,000 B (the template alone is 864 B; the earlier S5b draft of 2,053 B no longer fits and is trimmed, budget line first, then the autonomy line; it names the S5b-scope regex as the Owned list instead of listing files), so S5b keeps about 128 B spare (S5a is merged); an envelope that would not fit is trimmed, never the ranges. Naming operating-instructions.md (6,678 B) lifts the cap to 43,000 and the room to 2,450 B (322 B more than without it), so name it only if the slice needs it. The union of both sets is 38,240 B: not readable by one worker, which is why S5 is two slices.
