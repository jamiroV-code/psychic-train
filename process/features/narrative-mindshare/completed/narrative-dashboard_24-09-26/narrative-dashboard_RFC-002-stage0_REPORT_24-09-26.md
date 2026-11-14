---
name: report:narrative-dashboard-rfc-002-stage0
description: "RFC-2 Stage 0 — Hyperliquid ticker keying, volume-share and new-listing formula, pytrends backfill rules; presented, STOPPED for user decisions"
date: 24-09-26
metadata:
  node_type: memory
  type: report
  feature: narrative-mindshare
  phase: RFC-2-stage0
phase: rfc-002-stage0
status: BLOCKED
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# RFC-2 Stage 0 — Exchange attention adapter + pytrends backfill

**BLUF:** RFC-2 can be built as planned, but 5 decisions are needed first. The main code finding:
ccxt names Hyperliquid's thousand-unit perps with an upper-case base (`KPEPE/USDC:USDC`,
base `KPEPE`). Only `baseName` keeps the original `kPEPE`. So neither a map symbol `PEPE` nor the
existing `ccxt_adapter.resolve_market_symbol` will find it, and a dedicated resolver is needed.
Also, the plan's storage table conflicts with its "no new cache surface" line. The exchange series
needs its own small writer. No source, data or test files were changed.

## 1. Hyperliquid keying (read from installed ccxt 4.5.78 `hyperliquid.py`, no live calls)

- **Perps (`fetch_swap_markets`, `parse_market`):** `base = safe_currency_code(name)`, which
  upper-cases the name (checked offline: `kPEPE -> KPEPE`). `baseName = name` keeps the raw name.
  Symbol is `BASE/USDC:USDC`. `active = not isDelisted`, so delisted perps stay in the list with
  `active=False`.
- **Spot (`fetch_spot_markets`):** base is taken from `spotCurrencyMapping` (for example
  `UBTC->BTC`, `USOL->SOL`, `UUUSPX->SPX`). Spot `BTC/USDC` would therefore overlap with the
  perp. Spot volume is small and noisy.
- **HIP-3 markets (builder-deployed dexes):** included by default because
  `options.fetchMarkets.types = ['spot','swap','hip3']`. Their bases look like `XYZ-TSLA`
  (equities and other non-crypto assets). A plain `fetch_tickers()` returns spot, perp and HIP-3
  markets together.
- **Tickers:** `quoteVolume = dayNtlVlm` (24-hour notional volume in USDC, rolling). The request
  carries no timestamp (`timestamp: None`).
- **Proposed resolution rule (runtime, reads the map on every run and never hard-codes coins).**
  For each map symbol `S`, look only at active, non-HIP-3 perps:
  1. `base == S`, else
  2. `baseName == "k" + S`, which marks it as a thousand-unit contract (`kPEPE`, `kBONK`, `kSHIB`,
     `kFLOKI`, ...).

  If nothing matches, the coin gets an explicit per-coin entry
  `{symbol, status: "unavailable", reason: "no-hyperliquid-market"}`. It is never dropped
  silently. Scaling does not affect the maths because `dayNtlVlm` is already a USDC amount.
- **Unverified (proxy returns 403):** the real list of `k` names, which map coins (for example
  POLYX, OM, MNT, AI16Z) actually have perps, and any `dayNtlVlm` quirks. The opt-in
  `-m integration -k hyperliquid` test is the only thing that can pin these.

## 2. Volume-share formula (proposed)

- **Inputs:** perps only, `params={'type':'swap'}`. That is one `metaAndAssetCtxs` call and it
  excludes both spot and HIP-3.
- `share(cat) = Σ quoteVolume(resolved perps mapped to cat) / Σ quoteVolume(all active non-HIP-3 perps)`.
  The unmapped perps count in the denominator, and an `"unmapped"` bucket reports their share.
  The shares add up to 1.0.
- **Alternative denominator:** mapped coins only, as the ADR-6 wording says ("total across all
  tracked coins"). With that choice, BTC (`store-of-value`) and ETH dominate the share. The
  denominator choice is **Decision D1**.
- **Failure handling:** if the fetch fails, or the total is 0 or None, the result is
  `status="unavailable"` for every category, never a share of 0. A category whose mapped coins all
  resolve to no market is also `unavailable` (`no-hyperliquid-market`), not 0.
- **Date:** the UTC calendar date at fetch time (`datetime.now(timezone.utc).date()`). The value
  is a rolling 24-hour window, not a closed UTC day. This needs a test at the tz boundary: a fetch
  at 23:59:59 UTC and one at 00:00:00 UTC must land on different dates.

## 3. New-listing detection

- **Snapshot storage:** a new file `cache/narrative/exchange/markets/{YYYY-MM-DD}.json` holding the
  sorted list of active non-HIP-3 perp `baseName`s. It is append-only and no-overwrite, like
  `write_liqtide_raw`. Proposed helpers: `write_exchange_market_snapshot(date, names) -> bool` and
  `read_exchange_market_snapshot(date)`. Whether a new cache helper is allowed is **Decision D2**.
- **Diff rule:** `new = today − latest snapshot strictly before today`. Each new name is converted
  back to a map symbol (strip a leading `k` when the rest is upper-case and present in the map),
  then assigned to its category, or to `"unmapped"`. Unmapped listings are never dropped.
- **Day 1 (E2):** no prior snapshot gives `new_listing_count: null`, `status: "unavailable"`,
  `reason: "no-baseline-yet"`. A genuine zero diff gives `0` with `status: "ok"`.
- **Gap days:** diffing against the latest earlier snapshot means a multi-day gap collapses
  several days of listings into one count. Proposal: record `baseline_date` alongside the count so
  the gap is visible. This is **Decision D3**.

## 4. Hyperliquid terms / redistribution

`data-sources/all-data-sources.md` has no Hyperliquid entry. Terms were not checked (no web access
from here). ADR-6 assumes `redistributable=true`, but that is not confirmed. **Recommendation:**
ship `redistributable=false` until the user checks Hyperliquid's terms, which is the conservative
default used for Farside and LSE. This is **Decision D4**. It is display-only data today, so the
flag has no effect until the app goes public.

## 5. pytrends backfill

- **`pytrends` is not installed in `api/.venv`.** It is not in `pyproject.toml`, on purpose, per
  the adapter docstring. The backfill therefore cannot run here, and the tests must use a stub
  `TrendReq`.
- **Shape (from the library docs, not observed here):** a DataFrame indexed by date, with one
  column per keyword (0–100) plus an `isPartial` column.
- **Granularity:** a window of ~269 days or less returns daily points. Longer windows (up to about
  5 years) return weekly points, and beyond that monthly. Every request is normalised to 0–100
  **within its own window**. Stitching several 270-day windows together therefore produces
  values that are not comparable, unless the windows overlap and are re-scaled (and that
  re-scaling would be invented maths).
- **Keyword:** reuse `trigger.py`'s rule (`keywords[0]` of each seed). Backfill covers the four
  seeds only. `store-of-value` is not a seed and has no keyword.
- **Proposal:** one daily window (`today-269d today`) per seed, with rows written as
  `source_status="backfilled"`. Rows with `isPartial=True` are dropped. Weekly history would be
  optional and marked `source_status="backfilled-weekly"`, dated on the week-start date. It would
  still be a separate window with its own normalisation, which conflicts with ADR-5's per-date
  maths. This is **Decision D5**.
- **Read-before-write:** read `read_narrative_series` once and build the set of dates whose
  `source_status != "backfilled"`. Skip those dates. Only then call `write_narrative_point` (the
  writer itself gives no priority guarantee, per the RFC-1 finding). Re-running replaces earlier
  backfilled rows with new backfilled rows, which is idempotent. Note that the writer rewrites the
  whole file on each call, so the cost is O(n²) over ~270 rows. That is acceptable.
- **Scale caveat:** pytrends' existing forward value is the last point of a `now 7-d` window, which
  is hourly-normalised. A backfilled daily value comes from a different normalisation, so the two
  are not on the same scale. This needs a `DataQualityCaveat` in RFC-5. Flagged here and not
  solved.

## 6. Files and tests (after decisions)

Create:
- `api/data/hyperliquid_narrative_adapter.py`: `fetch_daily_market_snapshot()` returns an
  `ExchangeSnapshotResult` with fields `status`, `reason`, `as_of` (UTC date),
  `perps: list[{base, baseName, quote_volume}]` and `redistributable`. It never raises. It reuses
  `ccxt_adapter._exchange()` and uses `fetch_tickers(params={'type':'swap'})`.
- `api/analytics/narrative/exchange_attention.py`: symbol resolution, volume share, new-listing
  diff, and the E2 state. Map symbols come from `load_category_map()`.
- `api/scripts/backfill_pytrends_history.py`
- The three planned test files, plus: `isolated_cache` round-trips through the real snapshot
  writer/reader and `write_narrative_point`/`read_narrative_series`; the `k`-prefix resolution
  (`PEPE -> kPEPE`); the no-market coin giving explicit `unavailable`; the HIP-3/spot exclusion;
  the UTC 23:59/00:00 boundary; E2 day 1 versus a real zero; and the forward-written date that is
  skipped.

Modify:
- `api/data/cache.py`: add the market-snapshot helpers (D2), plus an exchange-series
  writer/reader for the §12b schema.

## Conflicts with plan text

1. The §1.5 RFC-2 brief says "writes through `cache.write_narrative_point` (no new cache
   surface)". But §12b defines `cache/narrative/exchange/{category}.parquet` with columns
   `date, volume_share, new_listing_count, status`, which is not `write_narrative_point`'s schema.
   Neither text mentions the market-list snapshot. **Decision D2:** (a) add new cache helpers
   (recommended), or (b) squeeze the data into `write_narrative_point` as two pseudo-sources
   (`exchange_volume`, `exchange_listings`). Option (b) cannot represent `null` plus a reason
   cleanly.
2. ADR-6's "total across all tracked coins" versus the market-wide denominator (D1).
3. ADR-6's `redistributable=true` is stated as if confirmed, but it is not (D4).
4. The ADR-6 "confirmed during VALIDATE from ccxt source" note did not catch the upper-casing of
   the `k` base. The existing `resolve_market_symbol` would return `None` for `PEPE`, `BONK` and
   `SHIB`.

## Decisions needed from the user

- **D1:** denominator. Market-wide with an "unmapped" bucket (recommended) or mapped coins only?
- **D2:** add new `cache.py` helpers for the exchange series and market snapshots (recommended)?
- **D3:** on a gap day, diff against the latest earlier snapshot and record `baseline_date`
  (recommended), or report `unavailable` when yesterday's snapshot is missing?
- **D4:** set `redistributable=false` until you have checked Hyperliquid's terms (recommended)?
- **D5:** pytrends backfill. Daily ≤269 days only (recommended), or also weekly history as
  `backfilled-weekly`? Also, should `pytrends` be installed for the Verify run (on your PC, since
  Google is likely blocked here)?

TL;DR: The design works. The fixes are a `baseName == "k"+SYM` resolver and a perp-only, HIP-3-free
fetch, plus a new cache helper. Five user decisions (D1–D5) are needed before Stage 1.
