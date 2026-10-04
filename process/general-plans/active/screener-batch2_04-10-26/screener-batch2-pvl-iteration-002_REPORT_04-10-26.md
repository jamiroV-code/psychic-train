---
domain: plan
iteration: 2
date: 2026-10-04
plan: screener-batch2_PLAN_04-10-26.md
gaps_found: 7
fail_count: 0
concern_count: 7
applied: 7
backlogged: 0
loop_status: supplement_folded
---

# PVL iteration 002 - screener-batch2 (supplement cycle; results.tsv row 2)

PVL-supplement of the plan after cycle 1 (CONDITIONAL, 0 FAIL, 7 CONCERN F1-F7, 4 advisories). All items are folded into the plan body; no overlay section. The Validate Contract and the "Validation record (PVL cycle 1)" were not removed or rewritten. Only repeated names and wording inside the contract tables were updated (rows named in the SUPPLEMENT REQUEST). No PASS stamp was written; VALIDATE re-runs from V1.

Plan before: 526 lines, 86,099 B. Plan after: 531 lines, 86,958 B (the contract and record, which VALIDATE owns, are about 60 percent of the file; body prose was trimmed, no range was trimmed). Validator `validate-plan-artifact.mjs`: 0 failures, 0 warnings. ASCII only, no trailing whitespace, `git diff --check` clean.

## What was folded, and where (plan lines after this cycle)

| Item | Folded at |
|---|---|
| F1 | S4 section: new "Symbol-gate carve-out" paragraph (108); test-names line 134 (`test_no_verdict_symbols` skip-list now also names `test_screener_no_verdict_contract.py` and `screener-api.test.ts`); command block `S4-verdict` comment and `--exclude` flags (371-372) |
| F2 | break table row `test_momentum.py` (125: only the golden RSI test moves with `_reference_rsi` and `_make_daily_df`); test names (134: `test_rsi.py` (2) = 1 moved + 1 new `test_compute_rsi_returns_none_below_length`); checklist S4 step 7 (stub of the new test); Failing stubs paragraph (389). Counts (929, `22 passed`) unchanged |
| F3 | C8 reworded (48); S7 Goal (180); S7 Design 1 (`_leg_inputs` reads only `.df`, 186); S7 test names (194: both cache-only tests stub `liquidity_composite.build_*_composite` and `select_composite_variant` as `test_leg_boundary.py:210-223`); S7 Risks item 5 (200: accepted residual); AC-S7-4 and AC-S7-4r rows (301-302); P-S7-1 (351); the contract and record text already carried the residual |
| F4 | new `S-secret-scan` command (365-366, regex from the validation record, dry run fires on two samples, silent on `fetchApiKey = ()`); named in G-S4-8 (314), G-S6-7 (331), G-S7-7 (348); included in all three envelope range sets |
| F5 | S6 test names (168): test 9 in its own `test.describe` with `test.use({ deviceScaleFactor: 2 })` inside; tests 1-8 stay at DPR 1 |
| F6 | break table row `test_regime.py` (123): rename to `test_confirmed_boundary_is_passed_through_to_the_response`, asserts `len(response.confirmed_boundaries) == 1` and its `date`; still 3 tests (the old name appears nowhere else in the body or contract tables; the validation record keeps it as history) |
| F7 | Status line (11), TL;DR (14), Context Envelope (18), section "Questions Q1-Q6: RESOLVED by the user" replacing the open table (255-266), Open gaps (421), Handoff steps 2, 3, 5 (516-519); envelope table re-derived LAST (below) |
| Advisory a | C1 (41): `benchmark.py` is present and used by `routers/regime.py` until B |
| Advisory b | AC-S7-3 row (300): bands proven only by G-S7-8 E2E and P-S7-1 (jsdom never mounts the island) |
| Advisory c | C7 (47): age label compared in integers (`3 * age_days < median_days`, `3 * age_days < 2 * median_days`), history std is `Series.std()` ddof 1, NaN dropped; test names (194: integer comparisons, sample std ddof 1); P-S7-1 (351) hand calculation uses the sample std |
| Advisory d | S4 split evidence reproduce command (397): `git ls-files -z ... \| grep -zvE ... \| xargs -0 grep -lE ... \| wc -l`; dry run prints 42 |

Resolved by the user and recorded as resolved (not open): Q1 yes, edit the golden; Q2 RSI on boxes goes to S5; Q3 200 bars; Q4 in-memory toggles, AC-22 conditional with a backlog stub; Q5 0.5 x std flat and at least 3 earlier legs; Q6 state span, the user runs the backfill once.

## Trimmed prose (no ranges trimmed)

Sources line, Program budget, Costs follow-up line, Sequencing text, Risk Predictions, Worker envelopes paragraph, envelope-table note, C1 "measured 53" sentence, Gate conventions 2, 6, 7 and the S4 Goal, S4 Design B worker-text parenthesis. These cuts also brought the S4 envelope room above the 2.0 KB the record asks for (the folds had pushed it to 1.67 KB).

## Envelope line ranges (re-derived last; CLAUDE.md 13,443 B counted once)

| Slice | Plan ranges (lines) | Plan bytes | Room (cap 36,000) |
|---|---|---|---|
| S4 | 39, 41-44, 52, 54-61, 93-136, 280-289, 305, 307-318, 355-357, 359-360, 362-363, 365-366, 368-369, 371-372, 385, 387, 389 | 20,313 | 2,244 |
| S6 | 39, 45-46, 49-50, 52, 54-61, 141-172, 280-281, 290-297, 321, 323-335, 355-357, 359-360, 365-366, 374-375, 377-378, 385, 387, 389 | 17,405 | 5,152 |
| S7 | 39, 44, 47-50, 52, 54-61, 178-198, 280-281, 298-303, 338, 340-350, 355-357, 359-360, 365-366, 380-381, 383-385, 387, 389 | 15,023 | 7,534 |

S7's room (7,534 B) is now under the 8,000 B envelope cap, so the room is its binding limit; the plan note was corrected.

## Not done, by design

No test or gate was re-run (plan-only edits). The re-validation (V1 onward) is VALIDATE's job and the only place a PASS stamp can appear.
