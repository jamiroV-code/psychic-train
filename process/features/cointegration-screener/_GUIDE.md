# cointegration-screener

<!-- Part of my_site -->

## Scope

Scans candidate pairs for a cointegrating relationship and ranks them for tradability. Covers pair universe selection, Engle-Granger and Johansen testing, spread construction, half-life of mean reversion, and current z-score of the spread. This is the most statistically demanding area of the app and the one most sensitive to data quality.

## Key Source Files

Shipped v1 (`/pairs`, pair-screener_25-09-26, ✅ VERIFIED 28-09-26 — see
`process/features/cointegration-screener/completed/pair-screener_25-09-26/`):

- `api/data/pairs_universe.json` -- hand-editable, 18-coin universe (BTC, ETH, SOL, HYPE, XRP,
  DOGE, ADA, AVAX, LINK, LTC, BCH, DOT, SUI, NEAR, APT, ARB, OP, ATOM); `api/data/pairs_universe.py`
  -- loader, honours `PAIRS_UNIVERSE_PATH` override for tests/E2E, does not import
  `api/data/watchlist.py`
- `api/scripts/backfill_pairs_universe.py` -- one-time/occasional manual deep-fetch script
  (`DEEP_LOOKBACK_LIMIT=5000`, explicit early `since`, defensive cap-hit pagination)
- `api/scripts/compute_pairs.py` -- manual, idempotent compute script; reads deep-fetched OHLCV via
  `cache.read_ohlcv` only (no network), writes the persisted results cache + provenance sidecar
- `api/analytics/cointegration/stats.py` -- pure per-pair statistics: log-price OLS hedge ratio
  (both directions), Engle-Granger both directions, Johansen (`coint_johansen`), AR(1) half-life
  (or `not_mean_reverting`), z-score, `MIN_OVERLAP_DAYS = 365` gate
- `api/analytics/cointegration/pairs_response.py` -- compute path (BH correction via
  `multipletests`, universe enumeration) + read path (staleness/provenance comparison, sort)
- `api/models/pairs.py` -- Pydantic response models, `PairStatus`/`HalfLifeState` enums,
  `computation_status`/`stale_reason`
- `api/routers/pairs.py` -- `GET /api/pairs` (table), `GET /api/pairs/{a}/{b}` (detail); registered
  additively in `api/main.py`
- `web/app/pairs/page.tsx` -- ranked table; `web/app/pairs/[a]/[b]/page.tsx` -- per-pair detail
  (spread chart, both EG directions, Johansen, half-life state, z-score, sample window)
- `web/components/pairs/*`, `web/lib/api/pairs.ts`, `web/lib/types/pairs.ts`,
  `web/lib/format-pairs-value.ts`
- `web/e2e/pairs.spec.ts` -- Playwright E2E on a seeded fixture universe (`seed_e2e_cache.py`'s
  `pairs` section)

**Isolation, provably unmodified:** `api/routers/screener.py`, `api/data/watchlist.py`,
`web/app/screener/**`, `api/analytics/regime/**` — hard blast-radius exclusion, confirmed empty via
`git diff --stat` at RFC-005.

## Design Summary

Crypto-only (v1). All statistics computed once, offline, by `compute_pairs.py` after a manual deep
fetch — the API only reads the persisted `results.parquet`/`provenance.json` cache and never
recomputes on request (a request-time compute was measured at ~46s for 153 pairs against a p95 < 3s
target; precompute was the user-approved fix). Staleness is detected by comparing provenance
against the current universe file, each coin's OHLCV cache, and the installed
`statsmodels`/`EG_AUTOLAG` — never silently served as fresh. Ranking is Benjamini-Hochberg-corrected
Engle-Granger p-value ascending; ties break on `(eg_p_bh, eg_p_raw, coin_a, coin_b)`. Johansen is
always shown as an independent second opinion, never merged into one score. Every pair with too
little history or an unfetchable coin still renders as one row with an explicit reason — no NaN, no
silent zero, no dropped row.

**Real-data result (18 coins, 153 pairs, all `ok`):** 21 pairs have raw EG p < 0.05; 0 are
significant after BH correction at the 5% level (closest is DOGE/BCH, raw 0.00057 → BH-corrected
0.087).

## Known Gaps

- Hyperliquid appears to have a daily-history floor around **2020-08-19** (BTC/ETH/DOGE/LTC/ATOM all
  start exactly there) — likely a server-side limit, not five coincident listing dates. Not yet
  confirmed against Hyperliquid's own documentation.
- Live cap-hit pagination (the 5000-bar response cap) has never been observed on real data — only
  proven via a mocked test. Bulk rate-limit/backoff behaviour across 18 sequential deep-fetch calls
  is likewise unstressed in practice (18/18 succeeded with no throttling seen).
- The Johansen-refused row and the "no pair significant" banner are unit-tested only — not
  reachable in the current E2E fixture set.
- One `pairs.spec.ts` case ("cointegrated pair detail") failed once out of 90+ repeat-each runs, not
  reproduced since; suspected cold `next dev` compile timing, not a product defect.

## Related Context

- `process/context/all-context.md` -- root router, stack decisions and open decisions
- `process/context/data-sources/all-data-sources.md` -- history depth is the binding constraint for this feature; see the Hyperliquid history-floor and explicit-`since` notes
- `process/context/tests/all-tests.md` -- runner commands, `isolated_cache` fixture, seeded-E2E patterns

## Notes

Data note: crypto history is free and deep via ccxt. Equity history is the constraint — most
free tiers cap it well short of what a credible test needs. London Strategic Edge is the leading
free candidate but is unverified and its data is personal-use only, so anything built on it
cannot be served to other users if the app opens up. See the data-sources group before choosing.
Equity pairs remain out of scope for this feature's v1 (crypto-only).

Two hazards deserve explicit guarding. First, multiple-testing: screening hundreds of pairs produces cointegrated-looking results by chance, so the ranking must account for how many pairs were tested rather than reporting raw p-values — this feature applies Benjamini-Hochberg correction across every pair with sufficient overlap, per-run. Second, sample length: free equity tiers that cap history at one year are not enough for a credible test — check the available history before trusting a verdict, and surface the sample length alongside every result (shipped: `overlap_days`/`sample_start`/`sample_end` on every row).

## Current Status

Status: v1 shipped, ✅ VERIFIED (28-09-26)

## Folder Contents

```
process/features/cointegration-screener/
  active/       -- in-progress plans for this feature (each task lives inside a {slug}_{date}/ task folder)
  completed/    -- archived completed plans (pair-screener_25-09-26/)
  backlog/      -- deferred/future plans
```

All artifacts (plans, specs, reports, references) colocate inside each `{slug}_{date}/` task folder. Do NOT create `reports/` or `references/` sibling dirs.
