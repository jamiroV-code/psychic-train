---
domain: plan
iteration: 3
date: 2026-10-10
plan: screener-batch4_PLAN_10-10-26.md
mode: VALIDATE re-validation from V1 after supplement cycle 1 (PVL cycle 3)
gaps_found: 0
fail_count: 0
concern_count: 0
applied: 0
loop_status: validated_pass
---

# PVL iteration 003 - screener-batch4 (re-VALIDATE after supplement cycle 1; results.tsv row 3)

Code under test: origin/main `1e7d337` (S1-S7 and S5a merged); local HEAD `a03e917` adds process files only (`git diff 1e7d337 HEAD --stat -- api web` is empty). Plan before the stamp: 401 lines, 71,864 B, ASCII only, `git diff --check` exit 0, `validate-plan-artifact.mjs` 0 failures, 0 warnings. Strategy: one sequential validator (score 3 of 7: S2 public endpoint field, S6 public API contract, S7 more than 5 files; nothing needed cross-talk; cost guard not triggered). Targeted runs only (the baselines stand): vitest `pnpm test` 251 passed in 34 files (re-run once, 12 s, per-file counts read from the JSON reporter), `playwright test --list` 65 in 6 files (screener 10, contrast 7), pytest not re-run (3 tests in `test_refresh_router.py`, 2 in `test_no_verdict_symbols.py`, counted by grep).

## Verdict: PASS (0 FAIL, 0 CONCERN). 10 advisories, none blocking, listed at the end.

| Layer 1 dimension | Status | Why |
|---|---|---|
| Infra fit | PASS | `status()` (`refresh_worker.py:428-443`), `ccxt_adapter._now` (`:110-112`), `freshness.iso_z` (`:55-58`), the island build, ports and the seeded e2e stack match the plan |
| Test coverage | PASS | F3, F4, F5, F6 now have tests that can fail; counts, red runs and goldens recounted and re-derived below |
| Breaking changes | PASS | F1 and F2 verified against the real files; the S5b hand-over lists every added or changed file the S5b plan also cites |
| Security surface | PASS | read-only GETs, a clock reading, no auth, key, secret or browser storage; backoff capped at 300 s, 10 s abort |

| Layer 2 section | Status | Why |
|---|---|---|
| S11a status field, module, labels | PASS | every golden, tick instant and label re-derived with zoneinfo (below); scope/utc/words regexes dry-run clean |
| S11b poller, strip, in-place updates | PASS | F1, F3, F6, F7 folded and consistent with the real component code; mechanism U1 proven in cycle 1 (and the TZ switch re-proven under jsdom here) |
| Hand-over to S5b | PASS | cited line numbers (batch-3 130, 148-150, 327-328) and the 396/49, 113/13, 79/9 arithmetic re-checked |
| Sequencing, budget, envelope bytes | PASS | bytes recomputed exactly; a realistic S11b envelope was drafted and measured (2,020 B, fits) |

Totals: 0 FAIL / 0 CONCERN / 8 PASS rows. Net gate: PASS (no developed behaviour rests on Known-Gap alone: AC-S11a-1r, AC-S11a-2r, AC-S11b-9r are Agent-Probe rows and AC-S11b-8r is a Hybrid row with a D residual; all keep named residuals, none is a proving strategy).

## Cycle 1 findings: where each landed and what I checked against the REAL code

| Item | Plan lines | Verified against | Result |
|---|---|---|---|
| F1 drill-down error keeps the chart, keyed by symbol | 131, 146, 245, 247 | `DrillDownView.tsx:69-82` is the ternary `error ? <DeadDataNotice drilldown-error/> : view?.chart.available ? <MiniChart/>... : <DeadDataNotice unavailable/>`, `:31` clears the error at every effect run; `ScreenerBoard.tsx:87-93` renders `<DrillDownView symbol=...>` with no key; `MiniChart.tsx:56` effect keyed on the arrays, so with `mountKey` `timeframe\|height` another coin would update in place and keep the zoom | folded and correct. Test 6 can fail on the old code twice over: the old ternary drops `mini-chart` beside `drilldown-error`, and without `key={drillDownSymbol}` the island would update instead of re-mount. The three existing error tests (`DrillDownView.test.tsx:82-122`) all have no `view` when the error shows, so the new "error alone only with no view" rule leaves them green |
| F2 hand-over | 215-217 | S5b plan: forbidden line 130 (`web/lib/{chart-viewport,island-loader,spaghetti-lines}.ts`), break table 148-150 (9 renders), `S5b-scope` 327-328 (test list lacks `ScreenerBoardLive`); G-S5b-1 92/11, G-S5b-2 316/41, G-S5b-9 24, G-S5b-10 72/7 | folded and correct; 331+65 = 396 in 49, 48+42+23 = 113 in 13, 72+7 = 79 in 9 |
| F3 abort is neither failure nor settled | 129, 141, 146, 246 | `reactStrictMode` double effects; poller text P1 | folded; tests live-poll 3 and 11 and Live 12 (in `<StrictMode>`) carry it |
| F4 month step | 109 test 5 | zoneinfo + scratch C3 port (below) | instants 03-31T22:00Z, 06-30T22:00Z, 09-30T22:00Z and labels `["01 Apr","01 Jul","01 Oct"]` reproduced exactly; 24-month axis `["Jan 25","Jan 26"]` reproduced |
| F5 repeated hour | 43, 109 test 9 | scratch C3 port (below) | 15m window 2026-10-25T00:30Z..01:30Z gives ticks 00:30Z and 00:45Z only, labels `["25 Oct","02:45"]`; the "not later than the previous kept tick" rule keeps every axis monotonic (sweep below) |
| F6 null `server_time` | 111, 130, 141, 142 | `status()` builds the dict with no `server_time` today; the router returns it unchanged (`api/routers/refresh.py:20`) | server (pytest 5), client (P2, live-poll 6, strip waiting row) all present and consistent with C5 |
| F7 `visibilityState` fallback | 129, 148, 153, 341 | P1 names `document.visibilityState`, read in `start()` and on `visibilitychange`; hidden cancels timer and in-flight check, visible checks at once with no failure-count gate | the override (`Object.defineProperty(document, "visibilityState", ...)` then `visibilitychange`) can trigger an immediate check; test 4 recovery needs no 120 s wait. Real 61 s wait: `playwright.config.ts` sets no test timeout (30 s default; expect timeout 15 s), and the plan sets `test.setTimeout(150_000)` on test 2 only (lines 148, 341) |
| a-j | 42-43, 108, 129, 132, 151, 163, 194, 198, 340-342, 357-358, 382 | grep of each | all present |

Contract tables vs body after the supplement: criterion rows 237-253 (5 columns, strategy values only Fully-Automated / Hybrid / Agent-Probe, gap-resolution A-D) reference tests that exist in the Tests lists; gate numbers G-S11a-1..13 and G-S11b-1..11 match; convention 2 is three lines (49-52 ranges per slice); the body, the Blast Radius line 169 and the TL;DR agree on 25 + 35 touches, 17 + 3 + 3 and 63 + 4.

## Independent date and tick derivation (Python zoneinfo; scratch only: `scratchpad/c3.py`, `sweep.py`)

I wrote a port of the C3 text (15-minute UTC grid for sub-day steps, wall minutes a multiple of the step, skip when the wall time is not later than the previous kept tick's; Brussels midnights by `midnightOf(day)` = UTC midnight of that date minus the offset in force 3 h before it; Mondays; even day number for the 2-day step; month index step) and compared it with `zoneinfo`, never with the planned code.

| Case | Window / frame | Result (matches the plan) |
|---|---|---|
| test 1 | 21:00Z-23:30Z 3 Oct, 15m | 21:00Z, 22:00Z, 23:00Z: `["03 Oct","04 Oct","01:00"]` |
| test 2 | 3 Oct 00:00Z-04 Oct 00:00Z, 4h | 04:00Z, 10:00Z, 16:00Z, 22:00Z: `["03 Oct","12:00","18:00","04 Oct"]` |
| test 3 | 2026-10-23T22:00Z-27T00:00Z, 1d | 10-23T22:00Z, 10-24T22:00Z, 10-25T23:00Z, 10-26T23:00Z (24, 25, 24 h): `24 Oct`..`27 Oct` |
| test 4 | 5 Oct 2026 | Monday; Brussels midnight 2026-10-04T22:00Z |
| test 5 year rule | 2024-10-01T00:00Z-2026-10-01T00:00Z, 1d | 2024-12-31T23:00Z, 2025-12-31T23:00Z: `["Jan 25","Jan 26"]` |
| test 5 month step (F4) | 2026-01-01T00:00Z-2026-10-01T00:00Z, 1w | 2026-03-31T22:00Z, 2026-06-30T22:00Z, 2026-09-30T22:00Z: `["01 Apr","01 Jul","01 Oct"]` (Brussels 1 Jan = 2025-12-31T23:00Z is before the window, so no `01 Jan`) |
| test 7 spring, 3 h | 28 Mar 22:00Z-29 Mar 04:00Z | 23:00Z, 01:00Z, 04:00Z: `["29 Mar","03:00","06:00"]` |
| test 8 spring, 1 h | 29 Mar 00:00Z-03:00Z | 00:00Z, 01:00Z, 02:00Z, 03:00Z: `["29 Mar","03:00","04:00","05:00"]`, no `02:00` |
| test 9 autumn, 1 h | 24 Oct 23:00Z-25 Oct 03:00Z | 23:00Z, 00:00Z, 02:00Z, 03:00Z (01:00Z skipped): `["25 Oct","02:00","03:00","04:00"]` |
| test 9 autumn, 15m (F5) | 2026-10-25T00:30Z-01:30Z | 00:30Z, 00:45Z only: `["25 Oct","02:45"]` |
| `midnightOf` | 28/29/30 Mar and 24/25/26 Oct 2026 | 03-27T23:00Z, 03-28T23:00Z, 03-29T22:00Z and 10-23T22:00Z, 10-24T22:00Z, 10-25T23:00Z; day lengths 24, 23, 24 and 24, 25, 24 h; the plan's 3 h rule equals the true Brussels midnight for every date 2020-2035 (0 mismatches over 5,844 days) |

Monotonic-axis sweep: 12,000 random windows (spans from 30 minutes to 800 days, starts up to one span before each of the 8 clock changes of 2025-2028): 0 violations (ticks strictly increasing in instant AND in wall time, no two adjacent identical labels in sub-day axes). The EU dates hold: 29 Mar 2026 and 25 Oct 2026 are Sundays (23 Mar and 5 Oct are Mondays).

Also re-run in the repo's own vitest 2.1.9 with `environment: "jsdom"` (scratch dir, nothing in the repo touched): switching the process zone between UTC, America/Los_Angeles and Asia/Tokyo changed `getHours()` of 2026-10-03T22:30Z to 22 / 15 / 7 while the Brussels formatter stayed `00:30`, so brussels-time test 6 is non-vacuous under the real jsdom config (U3 holds there too).

## Test arithmetic, recounted from the listed test names (no `it.each` anywhere; convention 1)

S11a: brussels-time 8 (items 1-8), chart-time-format 12 (1-12) replacing 10, chart-freshness +2, ScreenerBoard +1, spaghetti-lines +3, btc-leg-lines +1 = 8 + 2 + 2 + 1 + 3 + 1 = 17 vitest; pytest +3 (tests 4-6); Playwright 3. Existing counts confirmed by the JSON reporter: chart-time-format 10, chart-freshness 5, spaghetti-lines 5, btc-leg-lines 6, chart-viewport 10, ChartFreshness 3, BtcLeg 6, DrillDown 6, ScreenerBoard 9, Spaghetti 6.
S11b: live-poll 12 + refresh-strip 10 + same-data 5 + refresh-api 3 + use-simple-lines 7 + FreshnessStrip 8 + ScreenerBoardLive 12 + keepRange 4 + chart-freshness 2 = 63 vitest in 7 new files; Playwright 4.
Totals: pytest 996 to 999 (and G-S11b-5 = 2 + 6 = 8); vitest 251 to 268 to 331, files 34 to 35 to 42; e2e 65 to 68 to 72, files 6 to 7 to 8.

| Gate | Recount | Plan |
|---|---|---|
| G-S11a-1 | 3 existing + 3 new = 6; red: 3 stubs + the `STATUS_KEYS` test fail, 2 pass | 6 (4 failed, 2 passed) |
| G-S11a-3 | 8 + 12 + 7 + 8 + 7 + 3 + (6 + 6 + 10 + 6 = 28) = 73 in 5 lib + 1 chart + 4 screener = 10 files; red: 27 stubs (8 + 12 + 2 + 1 + 3 + 1) + 10 changed goldens (4 + 2 + 1 + 1 + 1 + 1) = 37 failed; passes 1 + 5 + 6 + 1 + 23 = 36 | 73 in 10 files, 37 failed / 36 passed |
| G-S11a-4 | 251 + 17 = 268; 34 + 1 = 35 files; red 37 failed | 268 in 35 |
| G-S11a-11 / 12 | 10 + 7 + 3 = 20; 65 + 3 = 68 in 7 files | 20; 68 in 7 |
| G-S11b-1 | 12 + 10 + 5 + 3 + 7 + (10 + 4) + (7 + 2) + 3 + (28 + 8 + 12 = 48) = 111 in 5 + 2 + 1 + 6 = 14 files; red: 63 failed, 48 passed (10 + 7 + 3 + 28) | 111 in 14, 63 / 48 |
| G-S11b-2 | 268 + 63 = 331; 35 + 7 = 42 | 331 in 42 |
| G-S11b-9 / 10 | 10 + 7 + 3 + 4 = 24; 68 + 4 = 72 in 8 files | 24; 72 in 8 |

Existing goldens (line numbers read in the real tests): chart-freshness 23, 29, 39, 44; ChartFreshness 11, 18; DrillDown 20 (title) and 35; ScreenerBoard 160 (title) and 179; Spaghetti 62-67; BtcLeg 71; `screener.spec.ts:252` is test 7 of 10 (list order); `test_refresh_router.py` STATUS_KEYS lines 20-31, uses at 73 and 84. The new expected texts follow from the fixtures (`open_ts` 2026-10-03T00:00:00Z gives 02:00 CEST; window 2026-03-23..2026-09-28 plus 6 days gives 2026-10-04; BTC 2026-01-01..2026-10-08 unchanged).

## Envelope byte math, recomputed from the saved file (each line plus its newline; script `scratchpad/bytes.py`)

| Slice | Plan ranges (lines, as saved) | Lines | Plan bytes | Room (36,000 - 13,443 - bytes) |
|---|---|---|---|---|
| S11a | 41-45, 49-51, 53-61, 81, 83-84, 86-90, 92, 94-105, 107-112, 257-271, 293-295, 297-298, 300-301, 303-304, 306-307, 309-310, 326, 330 | 74 | 17,924 | 4,633 |
| S11b | 49-50, 52-61, 123, 125-126, 128-136, 138, 140-148, 276-288, 293-295, 297-298, 300-301, 312-313, 315-316, 318-319, 321-322, 324-326, 330 | 66 | 20,435 | 2,122 |

Union 120 lines = 34,940 B (12,383 B over the 22,557 B a worker can take). CLAUDE.md is 13,443 B. The plan agent's figures are exact. Every range edge printed and read: S11a starts C1 (41) and ends C5 (45); conventions 1-2 (49-51), 3-11 (53-61); S11b skips the S11a baseline line 51 and C1-C5; 276-288 is the S11b gate table through G-S11b-11 and stops before the PC probe row; 293 and 326 are the fences; the comment/command pairs land on their own commands (301, 304, 307, 310, 313, 316, 319, 322, 325); 330 is Failing stubs.

**Realistic S11b envelope, drafted and measured** (`scratchpad/env-s11b-full.txt`, ASCII): the master-planner section 8 template (ROLE line, task, acceptance, owned/forbidden pointing at plan lines 125-126, branch and base SHA, the read list citing the 17 S11b ranges, extra code reads `web/lib/brussels-time.ts` and `web/lib/types/refresh.ts`, tests and the budget with the full-suite budget, retry budget, a budget line, the report path with all 11 headings inline, the stop rules, the autonomy line, and one line each for the two backlog stubs) is **2,020 B**. 13,443 + 20,435 + 2,020 = 35,898 B, 102 B under the cap; the 2,100 B reference is met with 102 B spare at that size (the plain 1,825 B draft without the stub lines leaves 297 B). It fits because owned and forbidden are cited by line (the template says "links, not contents"); inlining the 35 owned paths (about 700 B) would NOT fit and is not needed. Recorded as ADVISORY A1 below, not a CONCERN: the planner trims envelope text (stub lines, then the autonomy wording), never the ranges.

## Scope, forbidden, secret and word regexes (dry-run on the 25 and 35 owned paths and strays)

Extracted verbatim from the plan's command block (lines 293-326) and run with `cat <list>` in place of `git diff --name-only`:

| Command | S11a 25 paths | S11b 35 paths | Strays |
|---|---|---|---|
| `FORBIDDEN` | nothing | nothing | `api/data/ccxt_adapter.py` printed (correct) |
| `FIXTURES` | nothing | nothing | nothing |
| `S11a-scope` | nothing | prints the 29 S11b-only paths (expected: it is not S11b's gate) | prints all 10 strays |
| `S11b-scope` | prints the S11a-only paths (expected) | nothing | prints the 11 strays (incl. `spaghetti-lines.ts`, forbidden to S11b) |

Strays tested: `web/lib/types/screener.ts`, `web/islands/panel-sync.svelte.js`, `web/vitest.config.ts`, `web/e2e/contrast.spec.ts`, `web/lib/types/refresh.tsx`, `web/playwright.config.ts`, a `.bak` file, the REF file and `results.tsv`. No gate in one slice scans a file only the other slice may edit: `S11a-utc` lists chart-freshness, spaghetti-lines, btc-leg-lines (S11a), CoinPanel, ChartFreshness, simple-lines.svelte (shared) and leaves out `MiniChart.tsx` and `island-loader.ts`; `S11b-utc` lists only S11b-owned or shared files; the words, nostore and clock commands list only their own slice's new files plus `chart-freshness.ts` (shared) and `ChartFreshness.tsx` (shared). Against today's tree `S11a-utc` prints 11 hits (`chart-freshness.ts:9,10,36`, `spaghetti-lines.ts:109,118,128`, `btc-leg-lines.ts:108,111`, `CoinPanel.tsx:10`, `ChartFreshness.tsx:5`, `simple-lines.svelte:97`) and `S11b-utc` 7 (the S11a files plus `MiniChart.tsx:20`): red where the plan says, and every hit is a comment or caption S11a/S11b rewords. `S11a-words` prints nothing on the existing files; `test_no_verdict_symbols.py` (TOKENS, all `.ts/.tsx/.svelte/.js/.css/.py` under `api/` and `web/`) cannot match any planned text. The `-w UTC` scan would match `Date.UTC` in a scanned file, which the S11a-utc comment already says (brussels-time.ts and chart-time-format.ts, the only files that may use it, are not scanned).

## Hidden-breaker / gate-trap hunt (bounded)

No blocking defect found. Looked at: the three existing `DrillDownView` error tests against the new error rule; `screener.spec.ts` tests 1, 2, 5, 6 against the strip and the poller (grid child count, heading by name, request waits, chart request); the vitest path filters `components/chart` and `components/screener` (only the intended files match); `reactStrictMode`; `page.tsx` (server page rendering a client provider with default props, no functions across the boundary); `SpaghettiChart.tsx` effect deps and the `aria-label` that embeds the span text (e2e matches a prefix regex); the S11b-words list against the planned copy (`lastGood` is not a whole word); `S11-clock` (`performance.now` and `new Date(ts)` are not matched). Everything else is an advisory.

## Advisories (none blocks; none changes a count or a range)

A1. S11b envelope slack is thin: a complete envelope measures 2,020 B against 2,122 B of room (102 B spare); the plan's 22 B figure is against a 2,100 B reference. The planner trims the stub lines first, then autonomy wording; re-measure CLAUDE.md (13,443 B) at spawn.
A2. Line 394 (outside every range) still says "the fence lines 276 and 322"; the fences are 293 and 326. Byte-neutral fix for the planner: "276 and 322" becomes "293 and 326". The table above it is correct and governs.
A3. P1 does not name the listener target. Say `document.addEventListener("visibilitychange", ...)`, and have the e2e fallback dispatch on `document` (a listener on `window` would not see a non-bubbling event). Put it in the S11b envelope (about 60 B of the spare).
A4. E2E test 2 with `page.clock`: await the baseline check (the strip shows a time) before `runFor(61_000)`; otherwise the fake 10 s abort timer can fire on a first check that is still in flight and the test fails for the wrong reason. About 85 B for the envelope (102 B spare).
A5. E2E test 3 must use an answer that really changes (one more BTC bar, as in test 2) and assert that a board request happened; with an identical answer `shareStructure` returns `prev`, no `update` runs and the zoom check is vacuous. The real-island update path (U1) is proven only here.
A6. Live test 6's "mock called twice" must count only the drill-down's mounts (the board's coin panels also mount `mini-chart`; use a before/after delta or `within(drilldown-view)`); Live test 12 in `<StrictMode>` should compare board fetch counts before and after the first status check, because StrictMode itself runs the board's own fetch effect twice.
A7. C3 gives no parity for the 14-day step (the 2-day step is specified). Anchor it to Mondays since 1970-01-05, as the old `utcTicks` did, and say so in the module comment. No golden depends on it.
A8. The plan's lane stops ("ask above 5 USD (S11a) or 7 USD (S11b)") and the programme hard stop ("spend above 15 USD per slice or 75 USD in total needs the user's approval") are two tiers; the goal block states both.
A9. `S11a-scope` and `S11b-scope` would print the envelope REF file and `results.tsv` if they were committed on the worker's branch; the planner commits the REF on `main` before spawning (as for batch 3), so they stay out of `origin/main...HEAD`.
A10. Cosmetic: "first in `page.tsx`" for the strip leaves open whether it sits above or below the `h1`; either is fine for the tests (heading match is by name, the strip has no heading).

## Stamp edits and post-stamp re-verification

Edits (VALIDATE-owned, all outside every envelope range): line 11 status (still one line), line 19 context envelope tail, Validate Contract header lines 223-229 rewritten in place (still 7 lines: `Date`, `date: 2026-10-10`, `Status: PASS`, `Gate: PASS`, `generated-by: outer-pvl`; no supersedes line because no earlier stamped contract existed); a "Stamp" subsection (parallel strategy, rationale, validators, legacy test-gate lines, dimension findings, findings history, advisories A1-A10, does-not-prove additions, open gaps, accepted-by) inserted after the "Failing stubs" paragraph; `## Autonomous Goal Block` (BRANCH A: no plan with a `## Stable Program Goal` exists; 3,051 chars) inserted after "### Open gaps"; Resume items 2, 3, 5. Lines changed at or before line 330: 11, 19, 225-229 only.

Re-verified after the stamp: the 120 range lines are byte-identical to the pre-stamp copy (script comparison, 0 differing lines); byte math re-run on the stamped file: S11a 74 lines 17,924 B (room 4,633), S11b 66 lines 20,435 B (room 2,122), union 34,940 B; `validate-plan-artifact.mjs` 0 failures, 0 warnings (477 lines counted); `git diff --check` exit 0; ASCII only (0 non-ASCII lines); `Gate: PASS` appears exactly once (the header); the pre-emit greps return 1 each for `What This Coverage Does NOT Prove`, `Accepted by:`, `generated-by:`, `## Autonomous Goal Block`, and `Dimension findings:` is present; the plan is now 476 lines, 84,880 B. `results.tsv` has 4 lines (header + rows 1-3), 9 tab fields per row; rows 1 and 2 untouched. No source file, other plan folder or the S5b plan was edited; nothing was committed or pushed.

PHASE_COMPLETE rule: Gate = PASS, so `PHASE_COMPLETE: VALIDATE` is legal (condition a). No first-pass-CONDITIONAL rule applies.
