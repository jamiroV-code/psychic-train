---
domain: plan
iteration: 2
date: 2026-11-02
gaps_found: 2
fail_count: 0
concern_count: 2
applied_count: 2
backlogged_count: 2
all_clear: false
consecutive_all_clear: 0
saturation_status: ACTIVE
new_gaps: 2
loop_status: CONTINUE
---

# PVL Iteration 002 — BTC Momentum Signals

## Summary

The second plan supplement addressed the prior strict-consumer concern and specified the core date-range, pre-start warm-up, completion-cutoff, invalid-row and re-warm behavior. The plan artifact validator returned 0 failures and 0 warnings. Independent revalidation found three PASS dimensions and two remaining CONCERNs (0 FAILs): the bare Pine date literals still need a precise UTC interpretation for daily-bar comparisons, and an invalid-price or duplicate row at the exclusive end boundary must be explicitly barred from emitting an exit event. The concern count remains two; no plateau has been reached.

No source or test files changed. No code tests, builds, provider calls, or network calls were run.

## Research Agent Findings

### PVL3Infra — PASS

Prior infrastructure/setup concerns remain resolved: touchpoints, UTC serialization/completion cutoff, the existing screener E2E and Playwright config, PowerShell command, fixture network blocking, and implementation-time feature-guide refresh align with repository seams. No remaining gap in this dimension.

### PVL3Coverage — CONCERN

### GAP-I2-UTC-RANGE-BOUNDARIES — Convert model date literals to explicit UTC instants
- **SEVERITY:** CONCERN
- **LOCATION:** Plan §3.5 and RFC-001 date-range verification
- **GAP:** The plan names the source date values and UTC bar timestamps but does not define the timezone conversion for the bare Pine literals. The `23:59` end is not itself a daily bar-open boundary, so “first bar at/after end” needs a concrete UTC interpretation and test oracle.
- **RESOLUTION:** Carry forward: define `2006-01-01T00:00:00Z` inclusive and `2170-12-31T23:59:00Z` exclusive for this UTC daily series; assert the last in-range daily open and first out-of-range daily open, including the one-time end SELL behavior.
- **STATUS:** BACKLOG (carried into the next PVL cycle; not deferred out of scope)

Prior coverage concerns are resolved: the plan requires exact event/schema tests, complete fixture migration, accessibility, live prop updates, both marker kinds, chart preservation, and seeded network-blocked browser verification.

### PVL3Breaking — PASS

The strict-consumer concern is resolved. The plan states that `default=[]` is not wire compatibility, requires an external-consumer inventory and release notice, and requires an owner pause if strict clients would reject the new field; no unapproved shim/versioning path is allowed. In-repository migrations and the narrow vocabulary-guard exception remain explicit. No remaining gap.

### PVL3Security — PASS

The security and product boundary remains resolved: existing BTC endpoint/chart only, constrained event fields, isolated/no-fetch-through test fixture, no unrelated signal output or trading, and D-2 exception remains narrow. No remaining gap.

### PVL3RFC — CONCERN

### GAP-I2-INVALID-END-ROW — Reject ambiguous end-boundary rows
- **SEVERITY:** CONCERN
- **LOCATION:** Plan §3.5 and RFC-001 invalid-row/end-boundary tests
- **GAP:** Invalid prices and duplicates are generally defined as data breaks, but the plan does not explicitly state whether a valid timestamp with an invalid price can trigger the end-range SELL, nor whether all rows sharing a duplicate timestamp/date are invalidated before sorting/selection. Either ambiguity could fabricate an exit at an untrusted close or make the chosen duplicate order affect output.
- **RESOLUTION:** Carry forward: require a valid, finite-positive close and one unique UTC daily row for an end-boundary SELL; a bad-price or duplicate-date group is a data break, emits no event, resets the baseline, and is never silently selected/deduplicated. Add explicit tests for invalid-price and duplicate groups at the end boundary.
- **STATUS:** BACKLOG (carried into the next PVL cycle; not deferred out of scope)

Other feasibility concerns are resolved: pre-start valid history warms indicators without signals, end-boundary exit is one-time when data is valid, cutoff equality matches `freshness.is_partial`, and the existing API/island/browser seams are suitable.

## Regression Flags

No new FAILs. The previous strict-consumer concern is closed. Two edge details remain within the broader range/input-boundary area; the total concern count remains two, so this is the first cycle without gap-count reduction, not a plateau.

## Files Updated

- `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/btc-momentum-signals_PLAN_02-11-26.md` — second supplement: strict-consumer caveat/release gate and Pine range/input-sequence semantics.
- `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/results.tsv` — PVL bookkeeping, baseline plus cycles 1–2 after each report.
- This iteration report — PVL audit trail.

## Saturation Signal

Two concerns remain; count unchanged from cycle 1 and no FAILs. This is not a plateau (only one cycle without reduction). Continue with one precise plan-only supplement, then repeat independent validation.

## Next Iteration

- Define the Pine start/end literals as explicit UTC instants for the UTC daily series and identify the final in-range/first out-of-range bar opens in tests.
- Require valid-price, unique daily rows for end-boundary SELL; invalidate all rows in a duplicate UTC-date group and suppress events on invalid rows.
- Re-run the five independent plan reviewers from V1 after the supplement.
- Keep execution unapproved; no residual concern has been accepted by the user.
