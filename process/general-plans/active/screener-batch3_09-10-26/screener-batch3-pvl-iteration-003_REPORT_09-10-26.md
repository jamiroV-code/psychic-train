---
domain: plan
iteration: 3
date: 2026-10-09
plan: screener-batch3_PLAN_09-10-26.md
gaps_found: 1
fail_count: 0
concern_count: 0
applied: 1
backlogged: 0
loop_status: validated_pass
---

# PVL iteration 003 - screener-batch3 (re-VALIDATE from V1 after supplement cycle 1; results.tsv row 3)

## Verdict: PASS (0 FAIL, 0 CONCERN outstanding)

One contract-schema CONCERN (N1) was found and resolved in place inside the VALIDATE-owned contract table (two cells; no plan-body line, no count and no envelope-range byte changed). Everything else the caller listed verified clean against the saved plan and the real code. `Gate: PASS` is stamped once, the `## Autonomous Goal Block` is written (BRANCH A: no umbrella plan with `## Stable Program Goal` exists), the range table was re-verified after the stamp edits.

Code under test: origin/main `abda8e7`; `git diff 270f9ac origin/main -- api web` is empty; working tree clean before and after every probe (local HEAD `9014d86` adds process files only). Plan before the stamp 459 lines, 85,271 B; after the stamp 481 lines (everything added sits after line 343). Strategy: one sequential validator, Layer 1 and Layer 2 inline, score 4 of 7 (S1 api plus web, S2 API surface, S6 new personal-data file and public routes, S7 more than 5 files); 1 agent, cost guard not triggered. V5 was a single gate: a PASS with no CONCERN to accept, and the caller's instruction set the PASS condition.

## Caller checks, one by one

| Check | Result | Evidence |
|---|---|---|
| F1 AC-8r row and backlog stub | OK | row AC-8r at plan 264 (D, CONDITIONAL); stub `process/general-plans/backlog/screener-group-sort_NOTE_09-10-26.md` exists and says deferred by the user (Q1 A), dependencies on the S5b layout files, one-shot design, about 3 web files and 0.7 USD; no sort work in S5a or S5b; also 23, 35, 174, 192, 218, 372, 376 |
| F2 Q1/Q2 resolved | OK | `grep` for open, pending, awaiting, Q1, Q2: hits are only the resolved table (220-225), "accepted by the user, Q2 A" (15, 82), AC-8r (264, 372, 376) and the cycle history; Resume step 5 says run VALIDATE to PASS then wait for ENTER EXECUTE MODE. Stale status text remains at 11, 19, 446-448 (advisory a) |
| F3 G-S5b-11 numbers | OK | `pnpm exec vitest run components/screener` printed 27 passed in 4 files (BtcLegChart 6, DrillDownView 6, ScreenerBoard 9, SpaghettiChart 6); new: 12+4+7 = 23 (lib), 7+9+15+5 = 36 (components), +3 +3 = 6; 65 stubs; 27+65 = 92 in 11 files (8 component files + 3 lib files); 59 failures sit in the 7 new files, 6 inside the DrillDownView and SpaghettiChart files; full run 316 in 41 files with 251 passing; item counts re-counted from the plan lists one by one |
| F4 DELETE | OK | C4 (52) and design 2 (95): only the `crypto` section, file removed only when no section remains; test 13 (113) survives a save and a reset; test_layout 7 (114) second section stays, file goes when none remains. Gap: DELETE on an unreadable file is unspecified (advisory c) |
| F5 os.replace | OK | 45, 50, 95, 113: `os.replace` for the temp swap and the `.bad` move, test 12 pre-creates `.bad`, asserts the save succeeds and the source has `os.replace(` and no `os.rename(` (Windows `FileExistsError` is invisible on Linux, hence the source-text check) |
| F6 lock and threaded test | OK, reproduced | scratch copy of `watchlist.py` (scratchpad `f6/`). Unlocked: 8 threads behind a Barrier at 29 coins stored 30 to 31 coins and raised `JSONDecodeError` in 5 of 5 trials; 40 threads from an empty list kept 0 to 3 coins. With the planned module-level `threading.Lock` around the whole read-modify-write: 5 of 5 trials gave exactly 1 success and 7 `WatchlistFullError`, a parsable file of 30; 40 threads from 0 kept exactly 30. Test 11 as written (one success, the rest `watchlist_store.WatchlistFullError`, file parses with 30) therefore fails without the lock and passes with it |
| F6 across processes | out of scope, measured | 3 processes x 12 threads, cap 30. Lock only (non-atomic write): 27 of 36 stored and a concurrent reader process saw 146 unparsable reads in 1.5 s. Lock plus temp file plus `os.replace`: reader saw 0 unparsable reads (the file is always valid), but only 19 of 36 stored: two writing processes still lose updates and the cap cannot be enforced across processes. A thread lock cannot fix that; one API process is the design, so it is out of scope (advisory f) |
| F7 no re-mount | OK, not vacuous | the specified SpaghettiChart test is red today (the `hidden` prop is ignored, so `aria-pressed` is wrong) and fails for a naive new-Set-per-render implementation (a second `mountSimpleLines`); the e2e test (zoom, reorder with a button, `data-zoomed` stays `true`; `data-zoomed` exists at `simple-lines.svelte:289`, read by `screener.spec.ts:280-345`) fails for the same naive implementation because the POST reply replaces the layout object and its `hidden_lines` array. Mechanics note: `vi.doMock` after a static import does not intercept the loader, the worker needs `vi.resetModules()` plus a dynamic import (advisory d). `workers: 1` and `fullyParallel: false` (`playwright.config.ts`) so layout.spec cannot race another spec |
| F8 order stability | OK | test 3 (160) records the order across a timeframe change and the retry timers; Goal (127) and coverage limits (368) reworded to "caused by this slice (layout shift is not measured)". Strengthening idea in advisory e |
| Advisories a-g | OK | MAX_LIST 64 and MAX_SYMBOL_LEN 15 (95, 114 test 5), `RsiPoint {timestamp, value}` and TS `length: number` (54, 98-99, 143), the confidence-word ban is at `test_screener_no_verdict_contract.py:29-33,168-175` (VERDICT_TS_NAMES 29-34, the test at 168; `test_no_verdict_symbols.py` scans TOKENS only), stay-green scans `test_exchange_attention.py:157` and `test_history.py:286` present in the stay-green row (110), three globals.css parsers in the S5b row (152), comment-word rule in convention 10 (68), `exact: true` (163), T40/T41 note (218) |

## Envelope byte math (recomputed from the saved file, each line plus newline; before and after my stamp edits)

| Item | Value |
|---|---|
| CLAUDE.md | 13,443 B (AGENTS.md 12,572 B, so CLAUDE.md is the conservative one) |
| S5a ranges | 82 lines, 20,453 B, room 22,557 - 20,453 = 2,104 B |
| S5b ranges | 73 lines, 20,363 B, room 22,557 - 20,363 = 2,194 B |
| Union | 36,200 B, 13,643 B over the 22,557 B room even with a zero-byte envelope |
| operating-instructions.md | 6,678 B; naming it lifts the cap by 7,000 so the room grows by 322 B |

After the stamp, lines 1-343 are byte-identical to before except lines 231-234 and 263-264 (all outside both sets); the same script printed the same four figures on the stamped 481-line file. Every range edge lands on its intended line: S5a `50-54` = C2..C6 (C1 at 49 and C7 at 55 are outside), `59-68` = conventions 1-10, `88` Goal, `90-91` Owned/Forbidden, `93-100` Design 1-7, `102` and `104-110` existing-tests table, `112-116` tests, `267` and `269-282` gates G-S5a-1..12 (P-S5a-1 at 283 outside), `304-326` the command block through the blank line before S5b-scope, `336-337` CAP-MESSAGE comment and first grep, `339` fence, `341`, `343`; S5b `52` C4, `60-68` conventions 2-10, `127`, `129-130`, `132-137` UI rules U1-U5, `139-144`, `146-152`, `154-163` nine test items, `285`, `287-299` gates G-S5b-1..11 (P-S5b-1 at 300 outside), `304-306`, `311-312`, `327-328`, `330-331`, `333-334`, `336-339`, `341`, `343`.

Moving C5/C7 out loses nothing a worker needs: S5b's literal cap message is in design 2 (line 141, byte-equal to C5 line 53, one occurrence per line); C5's symbol rule is not used by the web (empty-input check only, 422 text from the server); C7's seeded facts matter only to e2e test 1 (163), which compares each box to the API value and names THIN as the N/A case, and the seeded watchlist comes from the manifest, so the 100.0 value is not needed by the worker. S5a loses only C7, the pointer line 118, and the lane/budget/risk/rollback lines, all restated by conventions 5 and 9 and by the envelope. What the S5b ranges do not carry is the wire detail of `POST /api/watchlist` (body keys `symbol`, `group_id`, 409 `detail`), which lives in C3 and C5: the S5b envelope should name `api/routers/watchlist.py` and `web/lib/types/{layout,screener}.ts` as code reads (advisory b).

Is about 140 B of slack robust? Honest answer: adequate, not generous. I drafted both envelopes independently, citing plan lines instead of copying, with every item the plan requires (task, acceptance, branch and baselines, read ranges, gates and the e2e rule, blocker rule, budget, lane, retry, the 11 report headings, stop clause, autonomy, probe disclaimer): S5a 1,860 B and S5b 1,988 B (slack 244 B and 206 B); the plan's own drafts are 1,962 B and 2,053 B (slack 142 B and 141 B). The margin disappears if the envelope copies text, or if CLAUDE.md grows by about 140 B before the S5b spawn (S5b is issued after the S5a merge). The failure is benign (trim the budget line, then the autonomy line; never a range) and the cap is guidance, not enforcement. Advisory: `wc -c` the envelope and `CLAUDE.md` at each spawn.

## Regex and scope dry-runs (exact commands from plan lines 306, 312, 315, 325, 328, 331, 334)

- S5a-scope on the 19 planned S5a paths and S5b-scope on the 28 planned S5b paths: nothing printed (report-name regex `screener-batch3-s5a_REPORT_[0-9-]+\.md` matches `..._09-10-26.md`; the backlog stub path matches in S5b-scope). FORBIDDEN on all 47 owned paths: nothing.
- Strays printed as intended: `api/tests/routers/__init__.py`, `web/package.json`, `web/e2e/contrast.spec.ts`, `web/app/screener/page.tsx`, `api/data/cache.py`, `deploy/x.ps1`, `api/scripts/seed_e2e_cache.py`, `web/islands/simple-lines.svelte`, `CLAUDE.md`, `README.md`, `.github/workflows/ci.yml`, `.claude/settings.json`, `api/tests/deploy/test_main_cors.py`, `process/MASTER-PLAN.md`, `web/e2e/.fixture-manifest.json` (git-ignored) against S5a-scope and S5b-scope; `web/lib/types/screener.ts` is printed by S5b-scope (forbidden for S5b) and allowed for S5a; FORBIDDEN catches the deploy, control, script and island strays.
- S5a-words on the four existing S5a source files, S5b-words and S5b-nostore on the four existing S5b components: nothing. S-secret-scan regex runs clean over `git diff 270f9ac`. `git check-ignore` with the three planned patterns in a scratch excludes file prints all three paths (and a `mkstemp(prefix=".layout.json.", suffix=".tmp")` name matches); today `git check-ignore api/data/layout.json` exits 1 as the red-today text says. `git diff --check` exits 0; the plan has 0 non-ASCII bytes.
- Gate traps checked and clear: `test_no_verdict_symbols.py` TOKENS contain none of the new names or testids; `api/tests` is a package everywhere (no basename collisions for the four new test files); `rsi-readout-*`, `drilldown-rsi-*` do not start with `coin-panel-`; `workers: 1`; the reload hazard of `test_fresh_deploy_degrade.py` is handled by `watchlist_store.<Name>` use; `_ts_interface` regexes need one field per line ending in `;` (design 6 says so); `rsi` defaults are non-None so the TS fields carry no `| null`; the two `ScreenerBoard.test.tsx` inline literals at 168-169 and `NO_FRESHNESS` at 12 and DrillDownView 9 are the complete tsc edit set (every other chart literal spreads `NO_FRESHNESS`).

## Contract tables versus body

Counts: pytest 15+10+11+9 = 45 (951 to 996); vitest 65 new (251 to 316, 34 to 41 files); Playwright 7 new (screener 10 + contrast 7 + layout 7 = 24; full suite 65 in 6 files, `playwright test --list` printed contrast 7, narrative 17, onchain 16, pairs 9, regime 6, screener 10, plus 7 = 72 in 7 files). Touch counts S5a 9+2+4+3+1 = 19, S5b 14+8+4+2 = 28, total 47. Cost arithmetic 4-5.5 + 5.5-8 = 9.5-13.5; 25.27 left; 11.77 to 15.77 remain (plan "12-16", rounded); all three at the top 25.5 USD, 0.23 over. Criterion rows back-reference the right list positions (cap tests 1-6 and 11 / 7 and 11 / 8-10; rsi 1-5 and 8 / 6-7; mirror tests `test_layout` 9 and `test_screener_rsi` 9; hybrid layout tests 1-7 match their content). The supplement's edits to AC-8r, G-S5b-11 and the proving-test cells match the body.

N1 (CONCERN, resolved): rows AC-S5b-8r and AC-8r (263-264) had "Known-Gap residual" in the `strategy` column; the contract schema (and batch 2 AC-S6-6, R12) allow only Fully-Automated, Hybrid or Agent-Probe there, with Known-Gap carried as a named residual via gap-resolution D. Both cells now read `Hybrid` (the planned proving type, as the stub says) and the proving-test cell begins "none today (Known-Gap residual)". Vacuous-green check: no developed behavior rests on Known-Gap alone (AC-8r develops nothing in S5; AC-S5b-8r's behaviors are covered functionally, only their contrast is a residual with a stub), so a terminal PASS is allowed.

## Bounded hidden-breaker hunt (this cycle)

No FAIL-class or CONCERN-class defect found beyond N1. Probed and clear: CORS (`_cors_options` allows GET, POST, DELETE; `test_main_cors.py` 10 passed); no test enumerates routes (`test_onchain_activity_router.py:173` only checks named paths); `lib/api/screener.ts` is untouched so `screener-api.test.ts` source scans hold; the CI file runs pytest, vitest, tsc and the island build, never Playwright (hence the e2e rule); the existing `ScreenerBoard.test.tsx` timeframe-change test asserts panels right after the board refetch, which constrains the implementation not to blank the grid (the plan's "refetches the board only" already says so); e2e test 6 and the failing-API test survive (`board-error` kept); `contrast.spec.ts` runs before `layout.spec.ts` alphabetically and the afterEach restores state before `screener.spec.ts`.

## Advisories (none blocks; planner or worker notes)

a. Lines 11, 19 and Resume 446-448 still say "no PASS stamp", "PVL cycle 2 pending", "contract PENDING". Planner refreshes after the stamp (R12 precedent); outside every range. Fix: set line 11 to "VALIDATED PASS (PVL cycle 3)".
b. Envelope hygiene as above; add `api/routers/watchlist.py` and `web/lib/types/{layout,screener}.ts` as extra code reads for S5b; `wc -c` at each spawn.
c. Specify DELETE on an unreadable `layout.json` (C2/C4): "moves it to `.bad` and returns the default" (or removes it), asserted in test 12 or `test_layout` 7. e2e test 7's afterEach issues this DELETE on a garbage file and the S5b worker cannot edit `api/**`; an implementation that raises there turns the S5b afterEach red.
d. SpaghettiChart +3 test 1: say `vi.resetModules()` plus dynamic import after `vi.doMock`, or `vi.spyOn(module, "loadIslands")`.
e. ScreenerBoardLayout test 3: have the board stub return another coin order on the second timeframe call.
f. Optional hardening: `_save_raw` via temp file plus `os.replace` (7 lines) removes the half-written read hazard (measured 146 bad reads vs 0); it cannot fix cross-process lost updates.
g. Legacy watchlist over 64 coins would 422 every layout POST (`MAX_LIST = 64`); AC-S5a-9 label A is the baseline only (gates re-prove at EXECUTE); neither CI nor the gates run `next build`.

## Gate commands run this cycle (targeted; no full suites)

`validate-plan-artifact.mjs` (0 failures, 0 warnings, before and after); `pnpm exec vitest run components/screener` (27 passed, 4 files); `pnpm exec playwright test --list` (65, 6 files); `UV_FROZEN=1 uv run --project api pytest` on `test_main_cors.py`, `test_watchlist.py`, `test_watchlist_store.py`, `test_no_verdict_symbols.py` (22 passed); scratch Python for the cap race and the two-process read check (scratchpad only); the regex dry-runs above; the range-byte script before and after the stamp; independent envelope drafts. Cycle-1 baselines stand (pytest 951/2/5/0, vitest 251 in 34 files, tsc 0, build:islands 0, e2e 65 passed), api/ and web/ unchanged since.

## Files written by VALIDATE

The plan (lines 231-234 header, 263-264 two cells, the validation record rewritten as "Validation record (PVL cycle 3)", the goal block body), `results.tsv` row 3, this report. Source files, deploy files, MASTER-PLAN untouched; nothing committed or pushed. P-S5a-1 and P-S5b-1 are the user's and are not claimed.
