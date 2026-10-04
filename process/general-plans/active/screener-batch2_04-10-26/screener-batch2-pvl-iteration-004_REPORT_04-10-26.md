---
domain: plan
iteration: 4
date: 2026-10-04
plan: screener-batch2_PLAN_04-10-26.md
gaps_found: 2
fail_count: 0
concern_count: 2
applied: 2
backlogged: 0
loop_status: supplement_folded
---

# PVL iteration 004 - screener-batch2 (supplement cycle 2 folding F8-F9 and advisories e-j; results.tsv row 4)

Verdict: supplement folded into the plan body (no overlay). No `Gate: PASS` stamp; re-VALIDATE (V1) is pending. The Validate Contract and the validation records were not edited.

## Items folded (plan line numbers unchanged; no line added or removed, 580 lines)

| Item | Plan line | Change |
|---|---|---|
| F8 | 110 | S4 Design B: `leg_boundary.py` docstrings stop naming deleted symbols; `refresh_worker.py` line 4 reads "board and chart reads are cache-only" (no `scalp`, no `relative-performance`) |
| F9 | 220, 312, 321, 327, 338, 344 | vitest chain 226 (S4, 30 files; 245 - 20 - 1 + 2), 239 (S6, 32 files), 251 (S7, 34 files) |
| F9 | 397 | split-evidence paragraph explains the `it.each` in `ConfidenceBadge.test.tsx` (6 tests, so 6 + 4 + 5 + 5 = 20) |
| (e) | 129 | S4 table row for `web/e2e/screener.spec.ts` now lists line 5 (`fetchScalp` in the header comment) |
| (f) | 194 | word-scan test scans exactly the four `S7-verdict-words` files; `web/lib/api/regime.ts:12` named as the non-target |
| (g) | 127 | `ScreenerBoard.test.tsx` row: no-verdict check by text or counts, not the removed test ids |
| (h) | 138, 206 | Q2 worded as resolved (Q2 = S5) |
| (i) | 41 | C1: `trend.py` kept for `compute_sma` until B |
| (j) | 47, 194 | C7: fewer than 2 historical changes (NaN std) gives N/A with a reason, never `flat`; asserted inside the existing `test_unavailable_composite_makes_composite_part_na_never_flat` (test counts unchanged) |
| status | 11 | header Status names cycle 1 F1-F7 and cycle 3 F8-F9 plus e-j as folded |

## Envelope table (re-derived last, exact line numbers)

CLAUDE.md 13,443 B counted once; cap 36,000 B.

| Slice | Plan bytes | Room |
|---|---|---|
| S4 | 20,612 | 1,945 (2,267 with `operating-instructions.md` named; drafted S4 envelope 1,609 B fits) |
| S6 | 17,405 | 5,152 |
| S7 | 15,242 | 7,315 |

Ranges unchanged (the table stays the last block). S4 prose was trimmed inside its ranges (no contract text) to keep room above 1.9 KB.

## Checks

`git diff --check` clean; ASCII only; no trailing whitespace; `validate-plan-artifact.mjs` 0 failures, 0 warnings. Plan 580 lines, 98,298 B.
