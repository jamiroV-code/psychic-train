---
domain: plan
iteration: 1
date: 2026-11-02
gaps_found: 2
fail_count: 0
concern_count: 2
applied_count: 8
backlogged_count: 2
all_clear: false
consecutive_all_clear: 0
saturation_status: ACTIVE
new_gaps: 2
loop_status: CONTINUE
---

# PVL Iteration 001 — BTC Momentum Signals

## Summary

The user accepted the eight proposed plan updates. The plan was supplemented in the first PVL cycle; the revised plan artifact validator returned 0 failures and 0 warnings. Independent revalidation found three PASS dimensions and two remaining CONCERNs (0 FAILs): strict external response consumers are not addressed, and the treatment of out-of-range/invalid bars is not fully specified. The gate remains CONDITIONAL. The two concerns are carried into the next supplement cycle, not accepted as residuals or deferred out of scope.

No source or test files changed. No code tests, builds, providers, or network calls were run.

## Research Agent Findings

### PVL2Infra — PASS

Prior setup concern resolved: the plan names `web/islands/entry.js` live-prop registration, `web/e2e/screener.spec.ts`, existing Playwright configuration, a Windows PowerShell invocation, fresh now-anchored cache data with fetch-through blocked, and the feature guide refresh during authorized implementation. The reviewer found these seams in the repository. No remaining gap.

### PVL2Coverage — PASS

Prior coverage concerns resolved: the plan pins model boundaries, event/schema parity and validation, fixture migration, island updates/accessibility, exact endpoint JSON, both marker kinds, candle anchoring, existing chart preservation, and zoom/pan. No remaining gap.

### PVL2Breaking — CONCERN

### GAP-I1-STRICT-CONSUMERS — Additive response may break strict external clients
- **SEVERITY:** CONCERN
- **LOCATION:** Plan §3 Final implementation choices; Public Contracts; Blast Radius
- **GAP:** The `signals` field is additive for clients that ignore unknown fields, but `default=[]` only protects response construction. It does not make the serialized response safe for strict consumers that reject unknown properties. The plan does not yet specify consumer inventory or release communication.
- **RESOLUTION:** Carry forward to the next plan supplement: explicitly qualify wire compatibility, require checking known out-of-repository consumers before deployment, and stop for owner decision if a strict consumer would break. Do not add a new endpoint/versioning path without authorization.
- **STATUS:** BACKLOG (carried into the next PVL cycle; not deferred out of scope)

Resolved prior concerns: in-repository fixture migration, Pydantic/TypeScript parity, constrained event validation, narrow vocabulary-guard allowance, and preservation of existing chart behavior are explicit in the revised plan.

### PVL2Security — PASS

Prior security/D-2 concerns resolved: the event remains limited to the existing BTC route/chart and kind/time/price; plan requirements retain the private boundary, event validation, no-leak vocabulary guard, fixture isolation, and no other signal surfaces or trading behavior. No remaining gap.

### PVL2RFC — CONCERN

### GAP-I1-BAR-BOUNDARIES — Specify indicator inputs versus signal eligibility
- **SEVERITY:** CONCERN
- **LOCATION:** Plan §3.5 Model warm-up/date range/forming bars/gaps; RFC-001 checklist
- **GAP:** The plan gives date bounds and invalid-input handling but does not say whether pre-start bars remain available for Pine lookback/SMA warm-up, what happens at the end boundary, or whether an invalid/duplicate bar is rejected as a whole versus treated as a sequence break. These choices affect first eligible and post-gap events.
- **RESOLUTION:** Carry forward to the next plan supplement: define the active interval and signal behavior, preserve pre-start history for rolling indicators as the Pine code does, and state deterministic handling for invalid, duplicate, and discontinuous bars (including reset/re-warm behavior). Keep the user-approved no-fabricated-exit behavior on data gaps.
- **STATUS:** BACKLOG (carried into the next PVL cycle; not deferred out of scope)

Resolved prior concerns: the plan specifies the relevant date/cutoff/warm-up/gap requirements, existing calculation seams, response event contract, live prop path, and browser verification. The exact boundary behavior above remains open.

## Regression Flags

No new FAILs. Three original dimension concerns are resolved. Two distinct plan-precision concerns remain; they are not regressions from an earlier PASS state.

## Files Updated

- `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/btc-momentum-signals_PLAN_02-11-26.md` — accepted P1–P8 plan supplement; restored `## Public Contracts`; replaced the POSIX E2E command with a PowerShell invocation.
- `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/results.tsv` — PVL bookkeeping, baseline plus this cycle after report creation.
- This iteration report — PVL audit trail.

## Saturation Signal

Two actionable concerns remain after one supplement cycle; no plateau and no severity escalation. The set is not saturated. Continue with one scoped plan supplement and re-run the independent validation fan-out.

## Next Iteration

- Carry forward strict external-consumer compatibility and release-decision handling.
- Specify pre-start indicator history, end-boundary behavior, invalid/duplicate timestamp handling, and gap reset/re-warm semantics.
- Re-run the five independent plan reviewers from V1 after the supplement.
- Do not write a terminal PASS contract or authorize EXECUTE until the revised plan resolves the concerns or the user explicitly accepts residual concerns after a completed supplement cycle.
