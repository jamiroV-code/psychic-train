---
domain: plan
iteration: 2
date: 2026-10-09
plan: screener-batch3_PLAN_09-10-26.md
gaps_found: 8
fail_count: 0
concern_count: 8
applied: 8
backlogged: 1
loop_status: supplement_folded
---

# PVL iteration 002 - screener-batch3 (PLAN supplement cycle 1; results.tsv row 2)

Status: supplement folded; no `Gate: PASS` stamp; VALIDATE re-runs from V1 (PVL cycle 2). Plan now 459 lines, 85,271 B (was 455 lines, 80,606 B). `validate-plan-artifact.mjs`: 0 failures, 0 warnings; `git diff --check` clean; ASCII only. Counts unchanged: 45 pytest, 65 vitest, 7 Playwright (pytest 951 to 996, vitest 251 to 316 in 34 to 41 files, e2e 17 to 24 and 65 to 72). Every fold sits inside an existing test. The Validate Contract header (7 lines, 229-235) and the validation record (378-429) are untouched except the AC-8r row, the repeated gate text of G-S5b-11 and the proving-test cells of rows AC-S5a-1/3, AC-S5b-6/7 that must match the body; their internal "plan line N" citations are stale and are VALIDATE's to refresh. Source, deploy files and MASTER-PLAN untouched.

## Folded items (new plan line numbers)

| Item | New plan lines | What changed |
|---|---|---|
| F1 | 264 (row AC-8r, Known-Gap, D, CONDITIONAL), 174 (Later batches: about 3 web files, 0.7 USD, backlog), 192 (Acceptance Criteria link), 218 (Phase Completion Rules: AC-8 marked deferred, not delivered), 372 (coverage limits), 376 (Open gaps), 23, 35, 15 (wording) | backlog stub WRITTEN: `process/general-plans/backlog/screener-group-sort_NOTE_09-10-26.md` (what AC-8 promised, why deferred, dependencies on the S5b layout files, one-shot vs view-only design, estimate) |
| F2 | 11 (status), 15, 23, 35, 82, 220-225 (heading "Resolved questions", Q1 A and Q2 A with effect), 376, 444-448 (Resume and handoff refreshed; step 5 = run VALIDATE to PASS then wait for ENTER EXECUTE MODE) | no "open" wording left outside the PVL record |
| F3 | 299 (G-S5b-11) | G-S5b-1 red run: 92 tests in 11 files, 65 failed (59 + 6 stubs), 27 passed; full `pnpm test`: 316 in 41 files, 65 failed, 251 passed |
| F4 | 50 (C2), 52 (C4), 95 (design 2 `reset_layout`), 113 (test 13), 114 (test 7), 245 (AC-S5a-3 cell) | DELETE removes only the `crypto` section; file removed only when no section remains; tests assert a second section survives a save and a reset |
| F5 | 50 (C2), 95 (design 2), 113 (test 12), Name check row 45 | `.bad` move uses `os.replace`; test 12 pre-creates `.bad`, asserts the save succeeds, and the source text has `os.replace(` and no `os.rename(` |
| F6 | 94 (design 1), 115 (test 11), 243 (AC-S5a-1 cell), Name check row 44, 440 (Test Infra note on readers) | module-level `threading.Lock` around add/remove; 8 threads behind a `threading.Barrier` at 29 coins: one success, rest `watchlist_store.WatchlistFullError`, parsable file of 30 |
| F7 | 134 (U2), 137 (U5), 159-160 (ScreenerBoardLayout tests 1 and 3 wording), 162 (SpaghettiChart test 1: new array of equal content in another order, `vi.doMock` of `loadIslands`, one mount), 163 (layout.spec test 2: ctrl-wheel zoom, reorder, `data-zoomed` stays `true`), 166, 259 (AC-S5b-6 cell) | sorted joined key; spaghetti rendered only after board and layout settle; automated, reviewer check kept as second line |
| F8 | 127 (Goal), 160 (test 3: recorded order unchanged after a timeframe change and the add retry timers), 260 (AC-S5b-7 cell), 368 (coverage limits) | claim reworded to what the test proves |
| a | 436 (envelope sentence), 72 (split evidence figures), 450-459 | "under about 2,100 B"; union restated 36,200 B (13,643 B over; the old 34,268 figure included C5 and C7 for S5b) |
| b | 54 (C6), 98, 99, 143 | `RsiPoint {timestamp, value}` (TS `timestamp: string; value: number`), TS `length: number` |
| c | 110 (stay-green row: confidence ban is `test_screener_no_verdict_contract.py:29-33,168-175`; `test_no_verdict_symbols.py` scans TOKENS only; `test_exchange_attention.py:157`, `test_history.py:286` listed, checked by G-S5a-2), 152 (S5b stay-green row: `chart-palette`, `plot-ink`, `onchain-ink` tests parse `globals.css`) | |
| d | 68 (convention 10: comments in scanned files avoid the scanned words), 94 (`watchlist_store.<Name>` in test files too) | |
| e | 95 (`MAX_LIST = 64`, `MAX_SYMBOL_LEN = 15`), 114 (test 5 adds a list over 64 and a 16-char symbol) | |
| f | 143 (visible label `RSI 14 (<timeframe>)`, no `aria-label` on the role-less row), 134 (`board-announcer` from first render), 133 (drill-down closes when its coin is removed), 160 (test: closes the open drill-down), 163 (`exact: true`) | |
| g | 218 (T40 and T41 not yet registered: planner registers them in UPDATE PROCESS; MASTER-PLAN not edited), 174 (R12 note: custom `WatchlistPath` makes the layout a sibling file), 357 (Windows 500 reaches the browser as a network error), 218 (comma fix) | |

## Envelope table (re-derived last; independent script reparsed the table from the final file)

| Slice | Plan bytes | Room (22,557 - bytes) | Drafted envelope | Slack |
|---|---|---|---|---|
| S5a | 20,453 | 2,104 | 1,962 B | 142 B |
| S5b | 20,363 | 2,194 | 2,053 B | 141 B |

Ranges (final line numbers): S5a `50-54, 59-68, 88, 90-91, 93-100, 102, 104-110, 112-116, 267, 269-282, 304-326, 336-337, 339, 341, 343`; S5b `52, 60-68, 127, 129-130, 132-137, 139-144, 146-152, 154-163, 285, 287-299, 304-306, 311-312, 327-328, 330-331, 333-334, 336-339, 341, 343`. Union 36,200 B. To fit: C7 (seeded facts) left out of both sets, C5 left out of S5b (its cap message is now literal in S5b design 2, line 141), the S5a "Gates and probe" pointer line left out of S5a; no contract text was trimmed.

## Notes for VALIDATE and the planner

- The validation record cites cycle-1 plan lines; lines moved by +4. Refresh them in cycle 2.
- Planner steps: register S5a and S5b (T40, T41) in MASTER-PLAN; the backlog stub exists already.
- No gate was run in this cycle (documentation edits only).
