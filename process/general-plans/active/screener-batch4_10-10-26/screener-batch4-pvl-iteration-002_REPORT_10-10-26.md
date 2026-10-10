---
domain: plan
iteration: 2
date: 2026-10-10
plan: screener-batch4_PLAN_10-10-26.md
mode: PLAN supplement cycle 1 (folds PVL cycle 1 findings F1-F7 and advisories a-j)
gaps_found: 7
fail_count: 0
concern_count: 7
applied: 7
loop_status: supplement_folded
---

# Supplement cycle 1 - screener-batch4 (results.tsv row 2)

Input: `screener-batch4-pvl-iteration-001_REPORT_10-10-26.md` (CONDITIONAL, 0 FAIL, 7 CONCERN, 10 advisories). Result: all folded into the plan body (no overlay section); no Gate: PASS stamp; the Validate Contract header is unchanged (7 lines, now at lines 223-229); counts unchanged (17 vitest + 3 pytest + 3 e2e for S11a, 63 vitest + 4 e2e for S11b); the S5b plan was not edited. Plan now 401 lines, 71,864 B (was 397 lines, 67,820 B). ASCII only; `git diff --check` exit 0; `validate-plan-artifact.mjs` 0 failures, 0 warnings. PVL cycle 2 is next.

## Findings and advisories: where each landed (plan line numbers as saved now)

| Item | Plan line(s) | What changed |
|---|---|---|
| F1 | 131 (P3), 146 (Live test 6), 245 and 247 (AC-S11b-2, AC-S11b-4) | `DrillDownView` shows `drilldown-error` above the retained chart when `view` exists (replaces the ternary at `DrillDownView.tsx:69-82`; alone only with no `view`); `ScreenerBoard` renders it with `key={drillDownSymbol}`; test 6 gains a failed tick refetch keeping `mini-chart` beside `drilldown-error` and another coin's "Drill down" re-mounting the island (mock called twice); no count change; `DrillDownView.tsx` was already S11b-owned |
| F2 | 215-216 (Hand-over to S5b) | `spaghetti-lines` added to S5b's forbidden sentence (batch-3 line ~130); new bullet: `ScreenerBoardLive.test.tsx` (12 renders of `ScreenerBoard`) needs `fetchLayout={fetchLayoutStub}`, must go into S5b's break table (batch-3 ~150), Owned list and `S5b-scope` (~328); G-S5b-1/2 counts unchanged; `live-refresh.spec.ts` and `brussels-time.spec.ts` covered by G-S5b-10 only; the S5b plan is NOT edited |
| F3 | 129 (P1), 141 (live-poll tests 3, 11), 146 (Live test 12), 246 (AC-S11b-3) | an abort from `stop()` or a hidden tab is neither a failure nor a settled check (snapshots unchanged); only the 10 s timeout and a rejected or non-OK answer fail; asserted in live-poll 3 and 11; Live test 12 runs inside `<StrictMode>` with no second board fetch and no `Could not check the server`; no count change |
| F4 | 109 (chart-time-format test 5) | month-step case (2026-01-01T00:00Z to 2026-10-01T00:00Z, 1w: ticks 03-31T22:00Z, 06-30T22:00Z, 09-30T22:00Z, labels `["01 Apr","01 Jul","01 Oct"]`) plus the 24-month year-rule axis labels `["Jan 25","Jan 26"]` |
| F5 | 43 (C3), 109 (test 9) | rule reworded to "wall time not later than the previous kept tick's wall time, whatever the step"; test 9 gains the 15m case (2026-10-25T00:30Z to 01:30Z: ticks 00:30Z and 00:45Z, labels `["25 Oct","02:45"]`) |
| F6 | 111 (pytest test 5), 130 (P2), 141 (live-poll test 6), 142 (strip "waiting" row) | server: `server_time` is `None` with the other 10 keys intact when the patched `ccxt_adapter._now` raises; client: a success with a null or unparsable `server_time` counts for `tick` and `dataVersion`, does not sync the clock (`lastGood.serverMs` unchanged, `useLiveClock()` null, captions use the payload), the strip prints `Page checked n/a` and no age |
| F7 | 148 (e2e description), 129 (P1 names `document.visibilityState`), 153 (Risk 2), 341 (U2 row) | without `page.clock`, trigger a check by overriding `document.visibilityState` to `hidden`, then `visible`, and dispatching `visibilitychange` in `page.evaluate`; test 4 uses it for failure and recovery (no 120 s wait); only test 2 keeps the real 61 s wait; the rule now sits where the S11b worker reads it |
| a | 132 (P4), 108 (test 6), 340 and 342 (U1, U3 rows), 358, 382 | reset `$effect` reads `range` inside `untrack`; `TZ` restored in a `finally`; U1 and U3 recorded as proven in scratch runs (real LayerChart island still e2e only); does-not-prove line and Test Infra note added |
| b | 108, 342 | as above (vitest 2.1.9 forks, non-vacuous) |
| c | 392-401 | S11b margin stated; the 11 report headings must be inline in the envelope |
| d | 194 (checklist step 10), 357 | `pnpm exec next build` offline, if it runs, is a report line, not a gate |
| e | 43 (C3) | the 2-day step keeps Brussels days with an even number since 1970-01-01, said in the module comment |
| f | 129 (P1), 151 (Lane reviewer list) | the poller constructor touches no `document` or `window` (SSR) |
| g | none | no action, as the report said |
| h | 163 (Public Contracts) | the board GET repeats every minute (plus the open drill-down GET; spaghetti and BTC once per server refresh) |
| i | 42 (C2) | one module-level `Intl.DateTimeFormat` instance |
| j | 198 (Phase Completion Rules) | planner may mention `server_time` at `current-state.md` line 48 |
| Q1 RESOLVED | 11 (status), 15 (TL;DR), 69, 75, 77 (budget: ceiling 75 USD, about 45.1 spent, 29.9 left, 20.4 left at the top S11 figure, stop at 75 in total), 204 and 206 (questions), 378 (open gaps), 387 and 390 (resume) | estimates unchanged: S11a 3.0-3.8, S11b 4.2-5.7 USD; the user's other resolutions (60 s quiet poll, strip plus last-bar line, Europe/Brussels with offset, S11 before S5b) recorded in one line at 206 |
| Other consistency | 50-52 (convention 2 split into the shared rule, S11a baselines, S11b start so each slice skips the other's line), 65 (split evidence bytes), 138 (S11b "Existing tests that break" shortened; the stay-green list moved to Risk 5 at 153) | |

Also kept in step (Validate Contract section, body-consistency only, header untouched): AC-S11b-2/3/4 rows (245-247), U1/U2/U3 rows (340-342), one new does-not-prove line (358), Open gaps (378), Resume items 2 and 5 (387, 390). No gate name, count or regex changed.

## Byte math (S11b was byte-neutral by trimming wording; ranges re-derived LAST by script)

Folding F1, F3, F6, F7 and the advisories first put S11b at 21,322 B (room 1,235 B), 865 B too much. Trimmed inside the S11b ranges, rationale and duplicates only, never contract text: convention 1, 3, 9, 10, 11 parentheticals (e2e-counts-it notes, the `@/` alias aside, the `pnpm --filter` message), Goal, Forbidden (read-hint dropped; the envelope still names `brussels-time.ts` and `types/refresh.ts`), P1/P2/P3 wording of the new rules, P3 "(an unchanged coin keeps its identity)", P4 "(latest props live in a ref, so ...)", P8 "(S5b reuses it)", the "Existing tests that break" line (stay-green list moved to Risk 5, outside the ranges), Owned "7 new and 2 edited", fence comment labels, Failing stubs wording; and convention 2 was split so S11b skips the S11a baseline numbers.

| Slice | Plan ranges (lines, as saved) | Plan bytes | Envelope room (cap 36,000 - 13,443 - bytes) | Slack vs a 2,100 B filled envelope |
|---|---|---|---|---|
| S11a | 41-45, 49-51, 53-61, 81, 83-84, 86-90, 92, 94-105, 107-112, 257-271, 293-295, 297-298, 300-301, 303-304, 306-307, 309-310, 326, 330 | 17,924 | 4,633 | 2,533 |
| S11b | 49-50, 52-61, 123, 125-126, 128-136, 138, 140-148, 276-288, 293-295, 297-298, 300-301, 312-313, 315-316, 318-319, 321-322, 324-326, 330 | 20,435 | 2,122 | 22 |

Union 34,940 B over 120 lines (12,383 B over the 22,557 B a worker can take). The method was checked first against the OLD plan at the git HEAD copy: it reproduces 17,678 B and 20,096 B exactly. The ranges were found by content anchors (not by number) with a script, and the first and last line of every S11b range was printed and checked by eye (convention 1 to 11 minus the S11a baseline line, Goal 123, Owned/Forbidden 125-126, Rules 128-136, existing-tests 138, Tests 140-148, gate table 276-288, fence 293 and 326, comment/command pairs, stubs 330). S11b slack is only 22 B: the final block (lines 392-401) says every later edit inside an S11b range must be byte-neutral.

## Gates run on the edited plan

| Check | Result |
|---|---|
| `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <plan>` | 0 failures, 0 warnings (402 lines counted by the validator) |
| `git diff --check` | exit 0 |
| non-ASCII / trailing whitespace in the plan and `results.tsv` | none |
| Validate Contract header (`## Validate Contract` to `generated-by`) | unchanged, 7 lines, Status and Gate still PENDING |
| `Gate: PASS` stamp / goal block | none written |
| `results.tsv` | `wc -l` = 3 (header, row 1, row 2), every row has 9 tab fields; row 1 untouched |
| source files, other plan folders, S5b plan | untouched (`git status` shows only this folder) |

## Left for VALIDATE (PVL cycle 2)

Re-derive the contract tables and gates; re-run the independent expected values for F4, F5 (they come from the PVL report's zoneinfo oracle, not from code); confirm S11b envelope slack (22 B) is acceptable or request a further byte-neutral trim; Gate PASS exactly once, the goal block and `PHASE_COMPLETE: VALIDATE` only if the results.tsv rule allows it. Nothing was committed or pushed.
