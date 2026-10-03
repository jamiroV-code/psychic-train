# RFC-005 Phase Report — ccxt Unified-Symbol Resolution + Adapter Failure Honesty

**Date**: 19-09-26
**Plan**: `process/general-plans/active/momentum-screener_17-09-26/ccxt-symbol-resolution_PLAN_19-09-26.md`
**Status**: ✅ VERIFIED — all gates green except AC-6 (accepted), user confirmed UI
**Phases run**: RESEARCH → INNOVATE → PLAN → PVL(2 cycles) → EXECUTE → EVL → UPDATE PROCESS
**SPEC**: skipped — inner-loop RFC governed by `momentum-screener_SPEC_17-09-26.md`

---

## Outcome

The screener was returning HTTP 200 with empty data on every market endpoint, and the board
never returned at all. Root cause was a single inherited assumption: bare watchlist tickers
(`"BTC"`) passed to real ccxt, which requires unified symbols (`"BTC/USDC:USDC"`). The resulting
`BadSymbol` was swallowed by a blanket `except Exception` and reported as `unavailable` — "the
exchange is down." It was not down; Hyperliquid measured 548ms away.

| Endpoint | Before | After |
|---|---|---|
| `/api/screener/board?timeframe=1d` | never returned (>4 min) | 32.1s cold / 4.3s warm, 4 coins × 500 bars |
| `/api/regime/legs` | 14.5s | 1.4s |
| `/api/screener/relative-performance` | 47.5s, all empty | 272ms, all available |
| `/api/screener/{sym}/scalp` | 13.9s, empty | 97ms, RSI 76.90 |

Backend suite: 135 passed, 0 failed, 1 deselected. 20 Parquet files now exist under
`api/data/cache/ohlcv/` — the first cached market data in this project's history.

## What the process caught that a straight fix would not have

**VALIDATE caught a deadlock in the plan before any code was written.** Checklist item 9
originally specified `threading.Lock` and left reentrancy as "non-reentrant path or `RLock`".
`fetch_ohlcv(sym, "1w")` recurses into `"1d"`, and `1w` is on the board's hot path — a plain
`Lock` would have self-deadlocked and hung the primary endpoint on first use. Found at V2, fixed
in PVL cycle 1, and the regression test was deliberately ordered *before* the implementation so
it could be seen failing first.

**The vacuous-green ban did real work.** AC-2 — the behavior the whole RFC exists to deliver —
originally had only an Agent-Probe gate. V3's ban forced a CONDITIONAL and a supplement cycle,
which produced `test_board_integration.py`. That gate is now the thing that actually proves AC-2,
since the browser probe turned out to be unavailable.

**Stage 0 was worth its own gate.** It confirmed ccxt 4.5.78 and that `baseName` and `base` carry
the same value on Hyperliquid, making the hedge in `resolve_market_symbol` harmless. Confirmed
rather than assumed — which is exactly the step whose omission caused deviations #8, #9 and #13.

## Deviations

Full detail in the plan's `## EXECUTE Results`. Summary:

1. **`api/data/watchlist.py` rewritten** (not in Touchpoints). Pre-existing defect: default
   arguments bound `DEFAULT_WATCHLIST_PATH` at import, so the test fixture's monkeypatch
   redirected nothing and the watchlist router tests wrote the real file. `test_remove_coin`
   **deleted BTC from the user's live watchlist** during the first real run. Restored; path
   resolution moved to call time.
2. **Parent plan's "43 passed" baseline was stale.** Real pre-RFC baseline ~116; AC-8 corrected.
3. **AC-6 missed** — cold 32.1s vs <30s, warm 4.3s vs <3s. Accepted. The warm figure is pandas
   computing indicators across 20 frames, not I/O, and is out of scope.
4. **The DuckDB/PyArrow shim did not produce a bug**, contrary to the plan's own prediction.
   Recorded so the next reader calibrates on outcomes rather than on the prediction.
5. **UI probe could not be automated** — browser pane blocks cross-origin to `127.0.0.1:8000`;
   Chrome extension not connected. Closed by user confirmation.

## Context updated

- `process/context/tests/all-tests.md` — **rewritten.** It claimed "no test surface exists" while
  the backend had had passing tests since 18-09-26. Its own Update Trigger had fired and gone
  unactioned. Now carries real commands, counts, a debugging table, and a Standing Lesson section
  recording all five green-but-wrong incidents.

## Backlog raised

- `process/general-plans/backlog/weekly-ohlc-golden-values_19-09-26.md` — `_derive_weekly_from_daily`
  has never been checked against known-good values, and two specific suspicions are worth testing:
  `resample("W")` defaults to `W-SUN` with right-edge labelling while exchange weeklies
  conventionally open Monday, and the trailing partial week is emitted with the same shape as a
  closed bar. If the anchor is wrong, every weekly RSI reading in the dual-timeframe filter is
  shifted by a period and nothing on screen would look wrong.

## Open observation

The four `1w.parquet` files carry mtimes ~31s later than their siblings, which does not match the
fetch order in `build_coin_panel`. Weekly data was definitely produced (momentum returned `PASS`,
which requires it). Unexplained rather than rationalised; touches the same function as the backlog
item above and should be looked at with it.

## Next

- **RFC-006** (planned, not started): frontend renders the new `reason` values; `getJson` gains a
  timeout and a catch — a slow request is currently an uncaught rejection and a Next.js error
  overlay; unify the three different dead-data renderings.
- **Playwright E2E** — deferred during this session on purpose, now unblocked by real data.
- RFC-001 can finally move toward archival: `stub_rfc001-frontend-tests_18-09-26.md` is the
  remaining open item.
