# RFC-002 Phase Report — Component maths

**Date**: 24-09-26
**Plan**: `regime-dashboard_PLAN_24-09-26.md` (ADR-5 amended — tanh normalisation, user-approved)
**Status**: 🔨 CODE DONE — real-data verified in the sandbox; not ✅ VERIFIED until the user confirms

## What changed

| File | Change |
|---|---|
| `api/analytics/regime/components.py` | new — six component builders, `normalise` (sign × tanh(impulse/scale)), calendar `asof_lookup`, reproduced composite with coverage + 60% floor + per-component freshness, published index (weekly history + daily archive), agreement stats, `build_regime_components()` orchestrator. Cache/adapters only; never calls `fetch_latest` |
| `api/data/fred_adapter.py` | new constant `TGA_WEDNESDAY = "WDTGAL"` (additive; `fetch_net_liquidity` untouched) |
| `api/data/liqtide_adapter.py` | `extract_history_series` + `read_history_series` (union of all archived raw payloads) moved here from the backfill script so analytics doesn't import a script |
| `api/scripts/backfill_liqtide_series.py` | re-exports the moved extraction under its old names |
| `api/scripts/check_component_reproduction.py` | new — per archived payload: our `normalise()` on LiqTide's own impulses, and our components from primary data on LiqTide's `as_of` dates, vs its published components; coverage table; agreement stats |
| `api/tests/analytics/test_components.py` | new — 31 tests (live golden values, calendar windows incl. holiday gap, staleness, Wednesday grid, ETF window gaps, renormalisation, 60% floor, freshness, partial DefiLlama day, published merge, agreement, no-network orchestrator) |
| `api/data/cache/liquidity/*.parquet` | refreshed through the adapters with today's FRED + DefiLlama downloads; `WDTGAL.parquet` added |

## Deviations

- ADR-5 amended (tanh instead of z-score) — approved at Stage 0.
- Net liquidity uses `WDTGAL` on the Wednesday grid instead of the as-of daily WTREGEN series (P5
  superseded): exact match with LiqTide. Starts 2008-10-22 (RRP coverage), not 2002.
- DefiLlama's point for the current UTC day is excluded — it is a live, still-moving total and
  pulled the stablecoin component from 0.6113 to 0.4346 on 2026-09-24.
- `ComponentSpec.fresh_days` added: how old a component's latest value may be and still enter the
  composite (FRED H.4.1/H.10 lag ~1 week; 10 days for net liquidity and dollar).

## What was tested

- Full suite in the sandbox: **234 passed, 1 deselected** (was 203 after RFC-001). Pyflakes clean.
- Real data (FRED CSVs + DefiLlama downloaded via the browser pane on the user's PC, fed through
  the real adapters; LiqTide archive of 2026-09-20 + 2026-09-24):

**Component check vs the 2026-09-24 payload** (`check_component_reproduction.py`, exit 0):

| Component | as_of | Published | Our formula on LiqTide's impulse | Ours from primary data |
|---|---|---|---|---|
| net_liquidity | 2026-09-16 | −0.3772 | −0.3772 | −0.3772 |
| stablecoin_supply | 2026-09-23 | 0.6122 | 0.6122 | 0.6113 |
| broad_dollar | 2026-09-18 | −0.4612 | −0.4612 | −0.4612 |
| rrp_release | 2026-09-23 | 0.0032 | 0.0032 | 0.0032 |
| etf_flows | 2026-09-23 | 0.9816 | 0.9816 | 0.9816 |
| btc_dominance | 2026-09-24 | 0.2190 | 0.2190 | 0.2190 |

**Coverage (real cache):**

| Component | First | Last | Points |
|---|---|---|---|
| net_liquidity | 2008-10-22 | 2026-09-16 | 683 (weekly) |
| stablecoin_supply | 2017-12-06 | 2026-09-23 | 3,214 |
| broad_dollar | 2006-02-01 | 2026-09-18 | 5,171 |
| rrp_release | 2008-10-22 | 2026-09-23 | 3,258 |
| etf_flows | 2026-09-14 | 2026-09-23 | 8 (LiqTide archive only — Farside backfill is RFC-003) |
| btc_dominance | 2025-07-12 | 2026-09-24 | 117 |

**Reproduced vs published index** (108 overlapping weekly dates, 2024-09-04 → 2026-09-24):
Pearson r = **0.964**; mean absolute difference by coverage:

| Coverage | Dates | Mean abs diff | Max abs diff |
|---|---|---|---|
| 100% | 2 | 0.38 | 0.46 |
| 90% (no ETF) | 28 | 0.60 | 1.47 |
| 80% (no ETF, no BTC dom) | 78 | 2.17 | 21.2 |

2026-09-24: reproduced 54.54 → rounds to **55 = published**. The large 80%-coverage misses are in
Sep–Nov 2024, when ETF flows (saturating near ±1) are missing and the remaining weights are
renormalised — RFC-003's Farside history is what closes that gap.

## Not tested / user steps

- `pytest` on the PC (terminals are click-only for me). Expected: ~234 passed.
- `uv run --project api python api/scripts/check_component_reproduction.py` on the PC should print
  the same table.

## Verification checklist

- [x] Manual test passed (real-data run above)
- [x] Data verified (coverage table + component check pasted)
- [x] Error handling confirmed (unavailable/no_data/stale paths in tests; no NaN/inf outputs)
- [ ] User confirmed working

**What's Functional Now**: all six components and both index lines computable from the cache,
matching LiqTide to 4 decimals where inputs coincide.
**Ready For**: RFC-003 (Farside ETF history) — or RFC-004 if you prefer the endpoint first.
