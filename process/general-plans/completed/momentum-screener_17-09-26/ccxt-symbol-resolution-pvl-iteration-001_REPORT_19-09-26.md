# PVL Iteration 001 — RFC-005 ccxt Symbol Resolution

**Date**: 19-09-26
**Cycle**: 1 of 10 (cap per `vc-autoresearch` §PVL Wiring)
**Plan**: `process/general-plans/active/momentum-screener_17-09-26/ccxt-symbol-resolution_PLAN_19-09-26.md`
**Loop status**: CONTINUE — re-validate from V1
**Saturation**: ACTIVE (first cycle, no plateau signal possible)

---

## Verdict That Triggered This Cycle

VALIDATE V3 net gate: **CONDITIONAL** — 2 FAIL-class, 2 CONCERN-class gaps, zero prior cycles.
Per `orchestration.md` §PVL/EVL Loop Routing and `CLAUDE.md` §Phase Transition Rules, a
first-pass CONDITIONAL routes to PLAN-supplement, never to EXECUTE. `PHASE_COMPLETE: VALIDATE`
was correctly withheld.

## Gaps Found

| ID | Class | Dimension | Finding |
|---|---|---|---|
| G1 | FAIL | Test coverage | AC-2 — the primary behavior the RFC exists to deliver — rested solely on an Agent-Probe gate. V3's vacuous-green ban forbids a terminal PASS where developed behavior has no Fully-Automated or Hybrid gate. |
| G2 | FAIL | Stage 1 feasibility | Checklist item 9 specified `threading.Lock` and deferred reentrancy to "non-reentrant path or `RLock`". `fetch_ohlcv(sym, "1w")` recurses into `"1d"`; a plain `Lock` held across the fetch self-deadlocks. `1w` is on the board's hot path, so the primary endpoint would hang on first use. |
| G3 | CONCERN | Infra fit | The `f"{ticker}/USDC:USDC"` fallback (item 6) activated only when `load_markets()` failed — i.e. precisely when it could not be verified — and contradicted the RFC's own thesis that the adapter should stop guessing about failure causes. |
| G4 | CONCERN | Test coverage | No gate proved the `load_markets()` failure mode at process start. |

## Fixes Applied

All four applied in-plan. None deferred, none backlogged, no out-of-scope residual.

| ID | Resolution | Plan items touched |
|---|---|---|
| G1 | Added `test_board_integration.py` — FastAPI `TestClient`, recorded markets fixture, stubbed OHLCV, asserts `chart.available is True` and non-empty `price`. Added opt-in `@pytest.mark.integration` network test running the same assertions against the real exchange. | 14a, 14b; Verification Evidence; AC-8 |
| G2 | Pinned to `threading.RLock` with scope narrowed to `_exchange()` construction and the `exchange.fetch_ohlcv(...)` call only, explicitly never across the `1w` recursion. Added a threaded 5s-timeout deadlock regression test, ordered *before* the implementation so it is seen to fail against a plain `Lock` first. | 9, 13a; Blast Radius item 2; AC-9 |
| G3 | Fallback deleted outright. Unresolvable ticker → `bad_symbol`; unloadable market list → `unavailable`. Test asserts on the outbound symbol, not just the status, so a reintroduced fabrication fails the suite. | 6, 13c; AC-10 |
| G4 | Added explicit failure semantics (item 9a: cache the failure for the process, degrade all symbols, retry on next process start only) plus a proving gate. | 9a, 13b; AC-10 |

## Net Change to the Plan

- **+3** Fully-Automated gates, **+1** Hybrid gate
- **+3** acceptance criteria (AC-9, AC-10; AC-8 revised 43 → 49 expected passing)
- **−1** code path (the symbol-format fallback)
- Blast Radius thread-safety decision revised `Lock` → `RLock` with narrowed scope

## Regression Flag

None. No previously-passing gate was weakened or removed. The only deletion is a code path that
had never been implemented or tested.

## Notes for the Next Cycle

If VALIDATE cycle 2 returns PASS, the contract is written at V6 and EXECUTE proceeds. Two
residuals will remain visible in the contract's "What this coverage does NOT prove" section and
are expected to stay there — they are genuinely out of this RFC's scope:

1. Correctness of `1w` weekly-close derivation against real daily bars (parent plan AC-1, never
   verified against real data — the shim made it unverifiable).
2. Concurrent board + legs request behavior under the new serializing lock. Single-user tool;
   acceptable, but unproven.

Neither is a gate this RFC can honestly claim.
