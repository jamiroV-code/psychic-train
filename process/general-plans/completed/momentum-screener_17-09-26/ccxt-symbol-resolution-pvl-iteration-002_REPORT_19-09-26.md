# PVL Iteration 002 — RFC-005 ccxt Symbol Resolution

**Date**: 19-09-26
**Cycle**: 2 of 10
**Plan**: `process/general-plans/active/momentum-screener_17-09-26/ccxt-symbol-resolution_PLAN_19-09-26.md`
**Loop status**: HALTED_SUCCESS — converged, contract written
**Saturation**: SATURATED

---

## Verdict

VALIDATE re-run from V1 after cycle 1's supplement. Net gate: **CONDITIONAL** — 0 FAILs,
2 accepted residual CONCERNs. Contract and `## Autonomous Goal Block` written at V6.

`PHASE_COMPLETE: VALIDATE` is legal here per `CLAUDE.md` §PVL/EVL loop gates condition (b):
`results.tsv` records 1 completed PVL fix cycle (4 lines — header + baseline + 2 cycle rows),
and condition (c) also holds (user explicitly accepted the CONDITIONAL gaps this session).

## Cycle 1 Gaps — All Closed

| ID | Cycle 1 class | Cycle 2 verdict | Evidence |
|---|---|---|---|
| G1 | FAIL | CLOSED | AC-2 now carries a Fully-Automated `TestClient` gate plus a Hybrid real-contract gate. Vacuous-green ban no longer triggers. |
| G2 | FAIL | CLOSED | `RLock` pinned with narrowed scope; AC-9 regression test ordered before implementation. |
| G3 | CONCERN | CLOSED | Fallback code path deleted; AC-10 asserts on the outbound symbol so reintroduction fails the suite. |
| G4 | CONCERN | CLOSED | Explicit `load_markets()` failure semantics (item 9a) with a proving gate. |

Zero regressions: no previously-passing gate was weakened or removed.

## Residual Concerns — Accepted, Not Closed

| Residual | Resolution class | Justification |
|---|---|---|
| `1w` weekly-close correctness vs real daily bars | **D** — backlog test-building stub | `_derive_weekly_from_daily` is unmodified by this RFC but becomes reachable for the first time. Needs golden-value fixtures and an ADR on week-anchor convention. Stub written to `process/general-plans/backlog/weekly-ohlc-golden-values_19-09-26.md`. |
| Concurrent board + legs under the serializing `RLock` | **C** — deferred to named later phase | Single-user personal tool; contention is not a current requirement. |

Both are named in the contract's "What This Coverage Does NOT Prove" section. Neither is silently
green — this is why the gate is CONDITIONAL rather than PASS. Moving them into a
`## Known Gaps (Resolved via Backlog)` exclusion bucket would have produced a nominal PASS and was
deliberately not done: the exclusion mechanism exists for out-of-scope gaps, not as a route to a
cleaner-looking gate.

## Why CONDITIONAL and not PASS

Gate Definitions require PASS to have "no FAILs, **no unresolved CONCERNs**." Two CONCERNs remain
unresolved-but-accepted. CONDITIONAL with documented acceptance is the honest classification, and
it routes to EXECUTE identically.

## Next

EXECUTE, sequential, single agent, opus (Model Selection Policy: EXECUTE is the only opus leg).
Stage 0 items 1–4 first, with a hard stop if any watchlist ticker fails to resolve.
