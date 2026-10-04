---
domain: plan
iteration: 5
date: 2026-10-04
plan: screener-batch2_PLAN_04-10-26.md
gaps_found: 0
fail_count: 0
concern_count: 0
applied: 0
backlogged: 0
loop_status: validated_pass
---

# PVL iteration 005 - screener-batch2 (re-VALIDATE from V1 after supplement cycle 4; results.tsv row 5)

Verdict: PASS (0 FAIL, 0 CONCERN). F8 and F9 and advisories e-j from cycle 3 are verified folded; the new-defect hunt (gate traps of the F8 kind) found none. Four advisories (k-n) have no verdict effect. `Gate: PASS` is stamped once in the Validate Contract and the `## Autonomous Goal Block` is written (BRANCH A: no plan with a `## Stable Program Goal` exists for this work).

Code under test: HEAD fede962 = origin/main 605424d plus `process/` files only (`git diff --name-only origin/main HEAD` lists nothing outside `process/`). Cheap checks only, no full suite: vitest on the four deleted component test files (20 passed), static counts, grep and regex dry runs in a scratch tree under the scratchpad directory, byte math from the file. `validate-plan-artifact.mjs`: 0 failures, 0 warnings.

## (1) F8: refresh_worker.py line 4 versus S6-dangling and S4-verdict

- Real file line 4: "worker runs, board, scalp and relative-performance reads are cache-only"; it is the only `scalp` or `relative` word in `refresh_worker.py`.
- Scratch tree (`api/data/refresh_worker.py` with line 4 replaced by "worker runs, board and chart reads are cache-only", plus an empty `web/`): `S6-dangling` (plan line 378) prints nothing (rc 1); `S4-verdict` (line 372, with the allow-list filter) prints nothing (rc 1).
- Plan line 110 (S4 Design B) names the rewrite and the reason (S6's `S6-dangling` scans `api/`, S6 may not edit the file). `refresh_worker.py` is in S4 Owned commit B (line 98), in the `S4-scope` regex, absent from S4 Forbidden (line 99), present in S6 Forbidden (line 146) and absent from `S6-scope`. Touchpoints (line 210) says "comment only". No test reads that docstring.
- Real tree `S6-dangling` hits by file: `screener_board.py`, `refresh_worker.py` (the F8 line), `models/screener.py`, `routers/screener.py`, `test_board_integration.py`, `test_relative_performance.py`, `globals.css`, `screener/page.tsx`, `RelativePerformanceChart.tsx` and its test, `screener.spec.ts`, `simple-lines.svelte`, `lib/api/screener.ts`, `chart-palette.ts`, `format-unavailable-reason.ts`, `relative-performance-lines.ts`, `lib/types/screener.ts`: every file except `refresh_worker.py` is S6-owned, and `refresh_worker.py` is now cleared by S4.

## (2) F9: vitest chain 226 / 239 / 251 and 30 / 32 / 34 files

- Recomputed from the real test files: `ConfidenceBadge.test.tsx` 2 `it(` + 1 `it.each` over 4 states = 6; `SignalDetailPanel` 4; `LegTimelineBanner` 5; `NarrativeStrip` 5; total 20 (vitest run on the four files: 20 passed in 4 files). `DrillDownView` 7 `it(` (the scalp-label test at line 62 is the one deleted), `ScreenerBoard` 8, `RelativePerformanceChart` 9. Test files: 33 (find, e2e excluded as in `vitest.config.ts`).
- Chain: S4 245 - 20 - 1 + 2 = 226 in 33 - 4 + 1 = 30 files; S6 226 + 10 + 5 + 6 + 1 - 9 = 239 in 30 + 3 - 1 = 32; S7 239 + 12 = 251 in 34.
- Plan digits: 226 at lines 220, 312, 321, 397; 239 at 220, 327, 338; 251 at 220, 344; files 30 (312, 321), 32 (327, 338), 34 (344). Grep for 229, 242, 254: the only hits are line 116 (test line numbers "229-230"), line 578 (byte count 15,242) and the historical cycle-1 and cycle-3 records (lines 440, 526, 542), which quote the old digits as history. No stale digit in the body, the gate tables or the contract tables.
- Pytest chain untouched and re-derived: 963 -> 964 (963 - 4 - 1 + 6) -> 929 (964 - 19 - 6 - 12 + 2 - 2 + 2) -> 934 (+ 8 - 3) -> 951 (+ 17).

## (3) Advisories e-j and counts

e: line 129 (screener.spec.ts line 5 `fetchScalp`; real hits at lines 5, 40, 195-204). f: line 194 (four `S7-verdict-words` files, `web/lib/api/regime.ts:12` named as the non-target; real line 12 `signal: AbortSignal.timeout`). g: line 127. h: lines 138 and 206 now read Q2 = S5 resolved. i: line 41 (`trend.py` kept for `compute_sma` until B). j: lines 47 and 194 (NaN std gives N/A). Test-name lists count to their numbers: 6, 2, 2, 8, 10, 5, 6, 12, 5, 6, 6 (S4 contract 6, rsi 2, symbols 2, vitest 2; S6 8, 10, 5, 6; S7 12, 5, 6, 6). S4 owned files total 53 (31 + 22), S6 32 incl. report and backlog stub (28 base), S7 19 incl. report (18).

## (4) Envelope table (byte math from the file, exact line numbers)

CLAUDE.md 13,443 B counted once, cap 36,000 B. Recomputed with a script over the table's range lists (each line with its newline): S4 20,612 B (room 1,945), S6 17,405 B (room 5,152), S7 15,242 B (room 7,315), exactly as stated; no duplicate lines, all lines <= 389. Every range start and end points at the intended text (checked line by line: 39 Decisions heading; 41-44 C1-C4; 52 and 54-61 gate conventions; 93-136 and 141-172 and 178-198 the slice sections up to their Gates/Lane lines, Risks and Rollback excluded; 280-281 table header; 282-289, 290-297, 298-303 criteria rows; 305, 321, 338 gate headings; 307-318, 323-335, 340-350 gate rows without the PC probe; 355-357 fence plus FORBIDDEN; 359-360 FIXTURES; 362-363 FIXTURE-EQ; 365-366 secret scan; 368-369 and 371-372 S4 scope and verdict; 374-375 and 377-378 S6; 380-381 and 383-384 S7; 385 closing fence; 387 and 389 failing stubs). S4 room 1,945 B >= the drafted 1,609 B envelope (336 B spare; naming `operating-instructions.md` gives 2,267 B of room). S7's room (7,315 B) is the binding limit below the 8,000 B cap, as stated. This report's plan edits add lines only after line 389 and edit lines 11, 18, 270-273 and 565-568 in place, so no range or byte figure moves.

## (5) Contract consistency and validator

Gate names, criterion ids and counts agree across the criterion table, the legacy line, Verification Evidence, the Implementation Checklist (A gates `G-S4-1,3..8,10..12`) and the gate tables (G-S4-1 6 tests, G-S4-2 22 passed + 1 skipped, G-S6-1 8, G-S7-1 17). Commands on lines 355-385 are byte-identical to cycle 3 (`git diff 953e849 fede962` touches only lines 11, 41, 47, 110, 127, 129, 138, 194, 206, 220, 312, 321, 327, 338, 344, 397, 576, 578, 580). Validator: 0 failures, 0 warnings. `Gate: PASS` appeared 0 times before this cycle and appears once after it.

## (6) New-defect hunt (gate traps of the F8 kind), bounded

Method: dry runs against the real tree plus scratch simulations of each slice's end state; every repo-wide gate scan (`S4-verdict`, `S6-dangling`, `S7-verdict-words`, the symbol pytest test inside the S6 and S7 full runs, `FIXTURES`, `FORBIDDEN`) was traced to the files a different slice could leave behind.

- `S4-verdict` real tree: 42 token files; every one is S4-owned (edited or deleted) except the two allow-listed comment files. Per-hit check of the small files: `leg_boundary.py` lines 4 and 148, `models/regime.py` lines 11, 31, 39, 50, `routers/regime.py` lines 6, 17, 27, 32 (all docstring or code that Design B covers), `narrative.spec.ts` lines 17 and 350, `RelativePerformanceChart.test.tsx` line 124, `test_sma.py`, `test_regime.py`, `test_screener*.py`, `screener.spec.ts` lines 5, 40, 195-204: all inside the table's cited lines. `globals.css` 13 hits = 7 `.confidence-badge*` + 4 `.signal-detail-panel*` + 2 `:not(.confidence-badge)` terms, exactly the plan's list.
- Scope regexes: `S4-scope`, `S6-scope`, `S7-scope` extracted from the plan and run against the owned file lists written from the plan text (53, 32, 19 paths): print nothing; stray files (`web/islands/simple-lines.svelte` for S4, `refresh_worker.py` and `leg_boundary.py` for S6, `chart-viewport.ts` and `MiniChart.tsx` for S7) are printed. `FORBIDDEN` prints nothing on all owned files.
- Python tests that read `web/` text (`test_screener_gain_contract.py` for `GainChip`, `test_screener_freshness_payload.py` for `ChartSeries` and `ScreenerBoardResponse`, `test_screener_integration.py` deleted): the S4 TS and Python edits are lockstep, S6 does not change those two models. Vitest tests that read `globals.css` parse only the `--series-N` and plot-ink tokens, none inside the CSS S4 deletes. No other test walks source (`rglob` users are fixtures and cache dirs); `test_lane_scope.py` skips off its own branch.
- Imports of deleted modules (`indicators.momentum`, `trend`, `confidence.badge`, `regime.benchmark`): only owned files and listed tests; `api/scripts/**` and `seed_e2e_cache.py` do not import them (the seed file's `build_screener_board` mention is a comment). TS: no file outside S4 ownership imports `LegBoundary`, `LegBoundaryResponse`, `LiquidityCompositeVariant`, `NarrativeCategory`, `SourceAvailability`, `fetchLegs`, `fetchNarrativeCategories` or `fetchScalpView`. Test ids of the four deleted components (`leg-*`, `narrative-*`, `signal-detail-*`): the only outside users are `narrative.spec.ts` lines 353-355 (deleted by the S4 table) and `NarrativeDashboard`'s own `narrative-loading`.
- Route table: `/spaghetti` (one segment) cannot collide with `/{symbol}/chart` (two); build output `web/public/islands/` is excluded by the verdict gate; `web/playwright-report` and `web/test-results` hold only `.html` and `.json`.
- BtcLegChart can mount the island directly as `RelativePerformanceChart` does, so S7 needs no edit of `MiniChart.tsx` (not in `S7-scope`).
- Result: no gate in one slice scans a file only another slice may edit. Nothing found beyond the advisories below.

## Advisories (no verdict effect; copy into the envelopes)

(k) C7 with a zero standard deviation (constant composite): T = 0, so `change = 0` satisfies both "at or above +T" and "at or below -T"; the worker should treat `T = 0` as N/A with a reason (same branch as the NaN std). (l) S6 comments, test names and docstrings must not name the deleted chain (`relative-performance-lines.ts`, "relative performance") in any S6 file: `S6-dangling` is case-insensitive over `relative.performance` (the worker can fix it in its own files, so this is not a trap). (m) The S7 word-scan test lists `outperform|underperform` while the `S7-verdict-words` command also lists `outperforming|underperforming`; with whole-word matching the test is narrower, so the worker should use the command's full list in the test. (n) AC-S6-6 (toggle persistence) is a named residual (Q4 = A, user-accepted, gap-resolution D, hybrid proof lands with S5), not a developed behaviour of this batch; its backlog stub is an S6 checklist output, so S6's worker must write it (the PASS does not depend on it existing today).

## Edits VALIDATE made to the plan

Contract header lines 270-273 rewritten in place (note, `supersedes:`, `Status: PASS`, `Gate: PASS`); lines 11, 18 and 565-568 refreshed in place (status, context envelope, Resume pointers; no line added); a "Validation record (PVL cycle 5)" block and the `## Autonomous Goal Block` inserted before "Resolved questions". Lines 1-389 keep their numbers and bytes.

## Bookkeeping for the orchestrator

`results.tsv` row 5 appended (`wc -l` = 6). `PHASE_COMPLETE: VALIDATE` is legal: Gate PASS and 2 recorded fix cycles. The user's explicit ENTER EXECUTE MODE is still required; the planner then writes three envelopes and spawns S4 only.
