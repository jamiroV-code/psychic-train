---
domain: plan
iteration: 3
date: 2026-10-04
plan: screener-batch2_PLAN_04-10-26.md
gaps_found: 2
fail_count: 0
concern_count: 2
applied: 0
backlogged: 0
loop_status: validated_conditional
---

# PVL iteration 003 - screener-batch2 (re-VALIDATE from V1 after supplement cycle 2; results.tsv row 3)

Verdict: CONDITIONAL (0 FAIL, 2 NEW CONCERN F8 and F9; cycle-1 F1-F7 and advisories a-d are verified folded). No `Gate: PASS` stamp and no goal block were written (the caller asked for both only at 0 FAIL and 0 CONCERN).

Code under test: origin/main 605424d (`git diff --name-only origin/main HEAD` lists only `process/` files). Plan after the VALIDATE edits: 581 lines. Validator `validate-plan-artifact.mjs`: 0 failures, 0 warnings. Cheap checks only: vitest in full once (245 passed in 33 files; it exposed F9), `pytest --collect-only` on every deleted or edited python test file, dry runs of the scope, symbol and secret commands in scratch trees and repos. Full pytest, tsc and islands were not re-run (docs-only since cycle 1).

## Cycle-1 findings: verified against the plan text and the real code

| Item | Result |
|---|---|
| F1 symbol gate | `S4-verdict` (plan line 372) dry-run in a scratch tree holding the planned test names, a `/api/screener/BTC/scalp` request and `fetchScalp`: prints nothing; without the two new `--exclude` flags it prints 3 hits; a stray `fetchScalp` elsewhere is still caught. Real tree: the 42 token files are all inside the `S4-scope` regex except the two allow-listed files. Carve-out (line 108) and skip-list (line 134) agree. |
| F2 RSI accounting | `test_momentum.py:59` is the only pure `compute_rsi` test (`:73` calls `compute_dual_timeframe_momentum`); `compute_rsi` returns `None` below `length` (`momentum.py:44`), so the new test name is accurate. `--collect-only` counts: badge 19, benchmark 6, momentum 12, integration 4, narrative contract 3, sma 5, lse 16, relative performance 3, regime 3, leg boundary 13. Pytest chain 963 -> 964 -> 929 -> 934 -> 951 holds; every test-name list counts to its stated number (6, 2, 2, 8, 10, 5, 6, 12, 5, 6, 6). |
| F3 cache-only wording | "BTC OHLCV read" plus the FRED and DefiLlama residual in the TL;DR, C8, S7 Goal, S7 Risks 5, AC-S7-4, AC-S7-4r and P-S7-1; no stale "answers from cache" text. Stubs (`build_*_composite`, `select_composite_variant`) and the `.df`-only fake match `test_leg_boundary.py:210-223` and `leg_boundary.py:140-165`; `refresh_worker.reads_cache_only_if_running` wraps ccxt only (`refresh_worker.py:422`). |
| F4 secret scan | `S-secret-scan` (line 366) dry-run in a scratch repo: fires on `API_KEY = "..."`, `Bearer ...`, `OPENAI_API_KEY="sk-..."`; silent on `fetchApiKey = ()`, `API_KEY: string = readConfig()` and a short value; silent on the real branch diff; named in G-S4-8 (314), G-S6-7 (331), G-S7-7 (348) and inside every envelope range set. |
| F5 DPR scope | Test 9 in its own `test.describe` with `test.use` inside (line 168); `screener.spec.ts` has 7 tests today (test 7 is the relative-performance chart, test 6 the drill-down), `playwright.config.ts:68` uses `devices["Desktop Chrome"]`. |
| F6 regime test | `test_regime.py:66-72`: the fake state carries one confirmed boundary dated `2024-06-01`, so `len(response.confirmed_boundaries) == 1` and its `date` are assertable; edit lines 19, 26-31, 45, 59, 71 are exactly the lines naming `select_active_benchmark` or `active_benchmark_reason`. |
| F7 Q1-Q6 and envelope math | Resolved everywhere (Status, TL;DR, Context Envelope, Q table, Open gaps, Resume); grep for open, pending, awaiting, unanswered finds nothing. Bytes recomputed from the file with the exact line numbers: S4 20,313, S6 17,405, S7 15,023 (CLAUDE.md 13,443 once), rooms 2,244 / 5,152 / 7,534; the ranges cover exactly the intended lines (conventions 1-8, gates without the PC probe, command-block lines per slice). |
| S4 envelope realism | A drafted S4 envelope (the 856 B template from master-planner.md section 8 filled with the S4 range list, gates, stop rules and autonomy) measured 1,609 B, so it fits the 2,244 B room with about 635 B to spare; naming `operating-instructions.md` would add 322 B of room. S7's room (7,534 B) is the binding limit, below the 8,000 B cap, as stated. |
| Contract consistency | Gate names and numbers in the criterion table, the legacy line, Verification Evidence, the Implementation Checklist (A gates `G-S4-1,3..8,10..12`) and the gate tables agree (G-S4-1 = 6 tests, G-S4-2 = 22 passed plus 1 skipped, pytest 964/929/934/951, S6 8 tests, S7 12 + 5). Touch counts re-derived: A 31, B 22 (14 distinct source files + 8 tests), 17 deletions, 53 of the 100 limit. Scope regexes S4, S6, S7 dry-run against the owned file lists print nothing and print stray files. `FIXTURE-EQ` on the unedited golden prints exactly the two `screener_narrative_state` blocks. |

## New findings

| # | Sev | Evidence | Exact fix |
|---|---|---|---|
| F8 | CONCERN | `api/data/refresh_worker.py:4`: "worker runs, board, scalp and relative-performance reads are cache-only". Dry run of `S6-dangling` (plan line 378) minus the S6-scope regex prints `api/data/refresh_worker.py:4` as the only file outside S6's ownership. S4 owns the file but its instruction (line 110) says only "docstrings stop naming deleted symbols", and `relative-performance` is deleted by S6. After a literal S4 edit G-S6-9 prints that line, and S6 cannot fix it: `refresh_worker.py` is Forbidden for S6 (line 146) and absent from `S6-scope` (G-S6-7 would fail on the edit). | S4 Design commit B (line 110): replace "`leg_boundary.py`, `refresh_worker.py` docstrings stop naming deleted symbols" by "`leg_boundary.py` docstrings stop naming deleted symbols; `refresh_worker.py` line 4 reads \"board and chart reads are cache-only\" (no `scalp`, no `relative-performance`: S6's `S6-dangling` scans `api/` and S6 may not edit that file)". +155 B on an S4 range line: S4 20,468 B, room 2,089 B (2,411 B with `operating-instructions.md`); re-derive the envelope table last. |
| F9 | CONCERN | The four deleted component tests hold 20 vitest tests, not 17: `ConfidenceBadge.test.tsx` 6 (`it.each` over 4 states + 2), `SignalDetailPanel` 4, `LegTimelineBanner` 5, `NarrativeStrip` 5 (vitest on the four files: 20 passed; full run 245 in 33 files; DrillDownView 7, ScreenerBoard 8, RelativePerformanceChart 9). The plan (and cycle-1's "3+4+5+5 = 17", a grep of `it(`) misses the `it.each`. Correct vitest chain: S4 245 - 20 - 1 + 2 = 226 in 30 files; S6 226 + 10 + 5 + 6 + 1 - 9 = 239 in 32; S7 239 + 12 = 251 in 34. Gate convention 2 stops a worker at `needs_input` when the observed delta differs, so G-S4-4 would stop S4 on a correct result. Pytest counts are right. | Digits only (same bytes, ranges unchanged): line 220 "245 to 229 to 242 to 254" -> "245 to 226 to 239 to 251"; line 312 "229 passed in 30 files (245 - 17 - 1 + 2; 33 - 4 + 1)" -> "226 passed in 30 files (245 - 20 - 1 + 2; 33 - 4 + 1)"; line 321 "229 vitest" -> "226 vitest"; line 327 "242 passed in 32 files (229 + 10 + 5 + 6 + 1 - 9; 30 + 3 - 1)" -> "239 passed in 32 files (226 + 10 + 5 + 6 + 1 - 9; 30 + 3 - 1)"; line 338 "242 vitest" -> "239 vitest"; line 344 "254 passed in 34 files (242 + 12; 32 + 2)" -> "251 passed in 34 files (239 + 12; 32 + 2)". Explain the `it.each` in the split-evidence paragraph (line 397, outside every range). |

Advisories (no verdict effect): (e) `web/e2e/screener.spec.ts:5` header comment names `fetchScalp`, not in the S4 table; `S4-verdict` flags it and the worker rewords it. (f) `test_btc_legs_sources_contain_no_verdict_words` must scan exactly the four `S7-verdict-words` files; `web/lib/api/regime.ts:12` has `signal: AbortSignal.timeout(...)`. (g) The `ScreenerBoard.test.tsx` "no verdict element" check must not use the removed test ids as literals (the symbol gate scans that file). (h) Line 138 "Q2 decides where it returns" and line 206 "if Q2 = S5" read as open; Q2 is resolved A (S5). (i) C1 calls `trend.py` "unused" after A; `screener_board` still imports `compute_sma` from it until B. (j) A NaN sample std (fewer than 2 historical changes) must give an N/A composite part, never `flat`.

## Edits VALIDATE made to the plan (nothing else touched)

Contract header lines 270-273 rewritten in place (same line count: note, `supersedes:`, `Status: CONDITIONAL`, `Gate: CONDITIONAL`), and a "Validation record (PVL cycle 3)" block inserted before "Resolved questions" (plan lines 501-548). Lines 1-389 keep their numbers and bytes, so the envelope table (S4 20,313 / S6 17,405 / S7 15,023) stays exact until the F8 supplement adds 155 B to line 110. The plan header Status line (11), Resume (562-566) and the cycle-1 record were not edited; the supplement cycle refreshes them.

## Bookkeeping for the orchestrator

`results.tsv` now has the header plus rows 1, 2, 3 (`wc -l` = 4). Do NOT read that as a cleared EXECUTE gate: the verdict is CONDITIONAL with two open concerns that are cheap to fold (one sentence, six digit edits). Recommended: one more supplement cycle (F8, F9), then re-VALIDATE; the re-validate needs only the cheap checks (vitest count, `S6-dangling` and `S4-verdict` dry runs, envelope bytes). The user's ENTER EXECUTE MODE is still required afterwards.
