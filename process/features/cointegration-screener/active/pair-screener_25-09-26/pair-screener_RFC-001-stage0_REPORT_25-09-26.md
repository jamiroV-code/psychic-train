---
name: report:pair-screener-rfc-001-stage0
description: "RFC-001 Stage 0 findings — statsmodels add + smoke check, live Hyperliquid universe resolution, baseline suite"
date: 25-09-26
metadata:
  node_type: memory
  type: report
  feature: cointegration-screener
  phase: RFC-001-stage-0
phase: rfc-001-stage-0
status: COMPLETE
plan: process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md
---

# RFC-001 Stage 0 — Pre-Phase Research (STOP for user approval)

**Bottom line:** the dependency is in, all three statsmodels functions accept the arguments the ADRs
assume, all 18 proposed coins resolve to active Hyperliquid perps, and the full api suite is still
green (392 passed / 3 deselected). Three items need your decision before Stage 1 (listed at the end).

## What Was Done

1. `uv add --project api "statsmodels>=0.14"` — installed **statsmodels 0.15.0** (plus scipy 1.18.1,
   patsy 1.0.3, formulaic 1.2.2, interface-meta 2.0.1, narwhals 2.26.0, wrapt 2.4.1).
   `api/pyproject.toml` +1 line (`"statsmodels>=0.14"`), `api/uv.lock` updated. `arch` NOT added
   (confirmed absent from `pyproject.toml`).
2. Smoke check (cheap-local, scratchpad script, not committed).
3. Live universe resolution against Hyperliquid (one `load_markets()` call, no OHLCV fetch).
4. Read-only review of `fetch_ohlcv` signature, `watchlist.py`/`watchlist.json` shape,
   `backfill_primaries.py` pattern, current OHLCV cache contents.
5. Baseline: `uv run --project api pytest api/ -q` → **392 passed, 3 deselected** (5m24s). No regressions.

No source files under `api/` other than `pyproject.toml`/`uv.lock` were touched. No commits.

## statsmodels signature and output findings (statsmodels 0.15.0)

| Function | Signature | ADR assumption | Result |
|---|---|---|---|
| `statsmodels.tsa.stattools.coint` | `(y0, y1, trend='c', method='aeg', maxlag=None, autolag='aic', return_results=None)` | EG test, two directions | OK |
| `statsmodels.tsa.vector_ar.vecm.coint_johansen` | `(endog, det_order, k_ar_diff)` | `det_order=0, k_ar_diff=1` (ADR-5) | OK — both positional-or-keyword, no defaults (must be passed) |
| `statsmodels.stats.multitest.multipletests` | `(pvals, alpha=0.05, method='hs', maxiter=1, is_sorted=False, returnsorted=False)` | `method='fdr_bh'` (ADR-8) | OK — note default is `'hs'`, so `method='fdr_bh'` must always be explicit |

Output fields (synthetic cointegrated pair, seed 42, n=500):

- **`coint`** → returns a `CointResult` object in 0.15 (not a plain tuple), but it has length 3 and
  supports indexing/unpacking: `[0]` t-stat (`-20.70`), `[1]` p-value (`~0`), `[2]` crit values
  array `[1%, 5%, 10%]` = `[-3.919, -3.348, -3.053]`. Recommend RFC-002 unpack via index/unpacking
  and pin this in a test so a future return-type change fails loudly.
- **`coint_johansen`** → result object with attributes `lr1` (trace stat, per rank), `cvt` (trace
  crit values, shape `(k, 3)` = 90/95/99%), `lr2` (max-eigen stat), `cvm` (max-eigen crit values),
  `eig`, `evec`, `ind`, `meth`, `r0t`, `rkt`, and 0.15 aliases `trace_stat`,
  `trace_stat_crit_vals`, `max_eig_stat`, `max_eig_stat_crit_vals`. Sample: `lr1=[219.60, 7.33]`,
  `cvt[0]=[13.43, 15.49, 19.93]`.
- **`multipletests`** → 4-tuple; `[0]` reject (bool array), `[1]` pvals_corrected. Sample input
  `[0.01, 0.02, 0.2, 0.5]` → reject `[T, T, F, F]`, corrected `[0.04, 0.04, 0.267, 0.5]`
  (matches hand BH).

**Finding for RFC-002:** `coint_johansen` emitted `ComplexWarning: Casting complex values to real
discards the imaginary part` (vecm.py lines 717-718) on this near-perfectly-cointegrated synthetic
input. Values were still sensible. RFC-002 should decide whether to suppress/record this warning or
treat it as a diagnostic — not a Stage 0 blocker.

## Universe resolution (live, Hyperliquid, 819 markets loaded)

Markets were confirmed loaded (the adapter's `resolve_market_symbol` passes a ticker through
unchanged if markets fail to load, so the check aborted on an empty market list — it did not).

| Ticker | Resolved symbol | swap | active |
|---|---|---|---|
| BTC | BTC/USDC:USDC | yes | yes |
| ETH | ETH/USDC:USDC | yes | yes |
| SOL | SOL/USDC:USDC | yes | yes |
| HYPE | HYPE/USDC:USDC | yes | yes |
| XRP | XRP/USDC:USDC | yes | yes |
| DOGE | DOGE/USDC:USDC | yes | yes |
| ADA | ADA/USDC:USDC | yes | yes |
| AVAX | AVAX/USDC:USDC | yes | yes |
| LINK | LINK/USDC:USDC | yes | yes |
| LTC | LTC/USDC:USDC | yes | yes |
| BCH | BCH/USDC:USDC | yes | yes |
| DOT | DOT/USDC:USDC | yes | yes |
| SUI | SUI/USDC:USDC | yes | yes |
| NEAR | NEAR/USDC:USDC | yes | yes |
| APT | APT/USDC:USDC | yes | yes |
| ARB | ARB/USDC:USDC | yes | yes |
| OP | OP/USDC:USDC | yes | yes |
| ATOM | ATOM/USDC:USDC | yes | yes |

18/18 resolve, 0 failures → C(18,2) = 153 pairs. Network egress to Hyperliquid works from this
machine, so the RFC-001 real deep-fetch run can likely run here rather than as a user-PC step.
Consequence: the AC-12 `bad_symbol` path is **not** exercised by the real universe at Stage 0 —
it will only be covered by the mocked/fixture tests (RFC-002/003/005).

## Other Stage 0 reads

- **`fetch_ohlcv(symbol, timeframe, since=None, limit=None, exchange=None)`** — matches the
  feasibility VERDICT mechanism; explicit `since` + `limit=5000` (`DEEP_LOOKBACK_LIMIT = 5000`
  already exists in the adapter) needs no adapter change. `ccxt_adapter.py` untouched.
- **Universe JSON shape:** `watchlist.json` is `{"coins": [...]}` and `watchlist.py` reads
  `data["coins"]`. Recommend `pairs_universe.json` use the same `{"coins": [...]}` shape, in its own
  file, with its own loader that does not import `watchlist.py` (AC-9).
- **Script pattern:** `backfill_primaries.py` = no CLI args, `backfill_all()` loops sources, prints a
  per-series coverage line via `_coverage(df)`. `backfill_pairs_universe.py` will mirror this.
- **Current OHLCV cache:** only BTC, ETH, HYPE, SOL present (the shallow ~501-bar set); the other 14
  coins have no cache yet.

## Plan Deviations

None in implementation. **Plan-text inconsistency found (not acted on):** RFC-001 Stages item 3
still says `fetch_ohlcv(symbol, "1d", limit=DEEP_LOOKBACK_LIMIT)` with no `since`, which contradicts
the PVL-cycle-1 Stage 0 mechanism (explicit early `since`, never `since=None`). Stage 0 text is the
newer, validated one; I will follow it in Stage 1+ unless you say otherwise. Recommend a one-line
plan fix at UPDATE PROCESS.

## Decisions needing user approval (STOP)

1. **Universe:** accept all 18 coins as-is (all resolve), or swap/drop any?
2. **JSON shape:** `{"coins": [...]}` for `api/data/pairs_universe.json` (recommended), or a flat array?
3. **Early `since` value:** epoch 0 vs a fixed date (e.g. `2020-01-01`) — the plan allows either;
   recommend `2020-01-01` UTC (predates Hyperliquid, avoids a pathological epoch-0 request).
4. Confirm Stages item 3 follows the Stage 0 explicit-`since` mechanism (see Plan Deviations).

Field-list and perf-threshold proposals belong to RFC-003 Stage 0 per the plan — not decided here.

## Test Gate Outcomes

| Gate | Result |
|---|---|
| statsmodels smoke check | PASS |
| Live market resolution | PASS (18/18) |
| `uv run --project api pytest api/ -q` | PASS — 392 passed, 3 deselected (baseline unchanged) |

## Test Infra Gaps Found

None new. Known-gaps from the feasibility VERDICT (live cap behavior, real listing dates,
rate-limit/backoff) remain open until the Stage 1+ real deep-fetch run.

## Closeout Packet

- Plan: `process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md`
- Finished: Stage 0 of RFC-001 only.
- Verified: dependency install, signatures/fields, live resolution, full api suite.
- Unverified: everything in RFC-001 Stages 1-3 (not started).
- Next valid state: user approves the 4 decisions above → RFC-001 Stage 1.

## Forward Preview

### Test Infra Found
`isolated_cache` fixture (`api/tests/conftest.py`) for any test touching `fetch_ohlcv`.

### Blast Radius Changes
`api/pyproject.toml`, `api/uv.lock` only.

### Commands to Stay Green
`uv run --project api pytest api/ -q` (392 passed / 3 deselected baseline; ~5.5 min).

### Dependency Changes
`statsmodels==0.15.0` (+ scipy, patsy, formulaic, interface-meta, narwhals, wrapt). No `arch`.
