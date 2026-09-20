# Backlog: Golden-value tests for `1w` weekly OHLC derivation

**Date raised**: 19-09-26
**Raised by**: RFC-005 VALIDATE cycle 2, gap-resolution D (named residual)
**Status**: ✅ CLOSED 19-09-26 — `process/general-plans/active/momentum-screener_17-09-26/weekly-ohlc-anchor_PLAN_19-09-26.md`, VERIFIED at 148 passed / 1 deselected.
**Origin plan**: `process/general-plans/active/momentum-screener_17-09-26/ccxt-symbol-resolution_PLAN_19-09-26.md`

## Why this exists

`ccxt_adapter._derive_weekly_from_daily` resamples daily bars into weekly ones
(`indexed.resample("W").agg({open:first, high:max, low:min, close:last, volume:sum})`) to satisfy
parent-plan AC-1's "real weekly closes" requirement. Hyperliquid offers no native weekly candle,
so every `1w` reading in the product comes from this function.

It has never been checked against known-good values. It could not have been: the EXECUTE sandbox
shimmed `ccxt`, so the `1w` path never fetched real daily bars, and the OHLCV cache is empty to
this day. RFC-005 makes the path reachable for the first time but deliberately does not verify
its arithmetic — RFC-005 gates only that the path does not deadlock (AC-9).

## Why it matters

This is precisely the failure class `process/context/tests/all-tests.md` flags as the highest-value
first target: *"indicator and cointegration output is the kind of thing that can be wrong by a
factor of two and still look plausible on a chart."* A weekly close that is silently off by one
period shifts the 60-period SMA and the weekly RSI leg of the dual-timeframe momentum filter —
the PASS/FAIL the whole screener is built on — and nothing on screen would look obviously wrong.

Two specific risks in the current implementation worth testing, not assuming:

1. **`resample("W")` anchors on Sunday by default** (`W-SUN`), labelling each bucket with its
   *right* edge. Exchange weekly candles conventionally open Monday. If the intended convention
   is Monday-open, this needs `W-MON` and `label="left"`, and today's output is shifted.
2. **Partial trailing week.** The most recent bucket is a still-forming week but is emitted as a
   completed bar with the same shape as closed ones, which collides with Standing Rule 4
   ("closed bars are immutable") and with `_cache_is_fresh`'s `1w` arithmetic.

## What a fix would need

- Golden-value fixture: a known span of real daily bars plus hand-verified expected weekly OHLCV,
  checked against a second independent source (TradingView weekly, or an exchange that publishes
  native weeklies).
- Explicit decision on week-anchor convention, recorded as an ADR — not left to a pandas default.
- A test asserting the partial trailing week is either excluded or explicitly flagged.

## Not blocking

RFC-005 ships without this. The gap is named in RFC-005's validate-contract under
"What This Coverage Does NOT Prove" and accepted by the user on 19-09-26.


---

## Resolution note (19-09-26)

Addressed by `weekly-ohlc-anchor_PLAN_19-09-26.md`. Two of this stub's own claims turned out to be
wrong and are corrected there rather than here being quietly overwritten:

- **Suspicion 1 (anchor) — half right.** `resample("W")` is indeed `W-SUN` right-labelled, but it
  groups Monday..Sunday correctly. Only the *label* was wrong, by +6 days. So the feared
  "every weekly RSI reading is shifted by a period" did **not** happen — indicators run over the
  close sequence, which never moved. The real symptom was a weekly bar stamped in the future.
- **Suspicion 2 (`_cache_is_fresh`) — wrong.** The `1w` branch returns before that check is
  reached; `_TIMEFRAME_SECONDS["1w"]` is dead for this purpose.

Of this stub's three requirements, two are met and one is not:

- ✅ **Golden-value fixture** — `api/tests/data/test_weekly_derivation.py`, 13 tests, every
  expected value hand-computed from the fixture rather than read back from the implementation.
- ✅ **Partial trailing week explicitly handled** — kept by decision (ADR-5), labelled with its
  Monday, with tests pinning both that it is present and that closing it leaves earlier weeks
  byte-identical.
- ❌ **Cross-check against a second independent source** — not done. Egress policy blocked every
  route to a native-weekly exchange this session. Monday-open is asserted from documented
  convention, not measured. Carried as residual 1 in the plan; one network call closes it.

Suite run: 148 passed, 1 deselected (baseline 135 — the delta is exactly this file's 13 tests).
The `isolated_cache` fixture is confirmed working by external evidence: `BTC/1d.parquet`'s mtime
was unchanged across the run, so the suite did not overwrite live data.
