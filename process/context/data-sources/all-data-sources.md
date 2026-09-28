---
name: context:data-sources
description: "Market-data providers, free-tier limits, licensing, and analytics library choices"
keywords: provider, data source, adapter, onchain, on-chain, growthepie, l2beat, dune, active addresses, chain, fred, liqtide, defillama, ccxt, farside, etf, coingecko, pytrends, reddit, api key, rate limit, licence, license, redistribution
date: 28-09-26
---

# Data Sources Context

Last updated: 2026-09-28 (On-chain activity section added — growthepie + L2BEAT adapters, Dune
recorded NOT-VIABLE, chain-growth plan; earlier, 2026-09-24: Hyperliquid exchange-attention adapter added, `hyperliquid_narrative_adapter.py`
— narrative-dashboard RFC-2; Farside spot-ETF adapter added, `etf_flows_adapter.py`; per-series
`max_gap_days` cadence pointer added — regime dashboard, RFC-003)

Canonical entrypoint for the `data-sources` context group in my_site.

Read `process/context/all-context.md` first, then this file, before choosing, adding or
changing any market-data provider or analytics library.

## Scope

This group covers:

- which market-data providers my_site can use, and what their free tiers actually allow
- which open-source libraries do the charting, indicator and statistical work
- the rules for adding a new provider or paying for one
- licensing and redistribution constraints that follow from the "public later" goal

It does not cover:

- the implementation of the adapter layer itself (that lives in code under `api/data/`)
- feature-specific analytics design (see the relevant `process/features/*/_GUIDE.md`)
- secrets or key values — never recorded here

## Read When

Read this file when:

- adding a new data provider or replacing an existing one
- a fetch is failing, rate-limited, or returning short history
- deciding whether to pay for data
- picking a library for indicators, cointegration, regime or charting work
- estimating whether a feature is feasible on free data

## Standing Rules

1. **Keyless and open-source first.** Prefer a provider that needs no API key and a library
   with a permissive licence. Every key is a secret to manage and a signup to maintain.
2. **Pay only against a proven limit.** Do not move to a paid tier on a hunch. Record which
   specific limit was hit (rate, history depth, symbol coverage, licence) before proposing it.
3. **One adapter per provider.** Everything goes behind `api/data/` with a common interface.
   No provider name should ever appear in a route handler, a component, or an analytics function.
4. **Cache by default.** Free tiers are small. Historical bars are immutable once closed — cache
   them locally and only fetch the tail.
5. **Check redistribution before it matters.** Personal use and public use are different
   licences at almost every equity vendor. Anything that might be served to other users later
   needs its terms checked now, not after launch.
6. **Never trust a free tier's "real-time" claim.** Several advertise real-time and deliver
   15–20 minute delays. Verify against a known quote before building on freshness.
7. **Tag redistribution rights at the adapter boundary.** Some free data is personal-use only.
   Record per-provider whether its output may be shown to other users, so the public-launch
   decision is a configuration question rather than an audit. See Licensing under Equity Providers.
8. **Cache every third-party composite on arrival.** For any provider that publishes a derived
   index rather than raw inputs, store each daily payload locally. Derived feeds disappear; their
   history is not recoverable after the fact.

## Crypto Providers

| Provider | Key needed | Free-tier limits | History | Notes |
|---|---|---|---|---|
| **ccxt** (library, not a vendor) | No, for public data | Whatever the exchange allows | Exchange-dependent, often years | MIT licence, unified API across 100+ exchanges. **Recommended default.** Swapping exchanges becomes a config change. |
| Binance / Coinbase public REST | No | Generous per-IP limits | Deep | Reached through ccxt rather than directly. Best OHLCV quality for free. |
| CoinGecko | Optional (keyless or free key) | ~10,000 calls/month, ~100/min with a free key | 1 year at daily / hourly / 5-minute | Best for cross-asset coverage, market caps and trending lists rather than precise bars |
| CoinPaprika | Yes | ~20,000 calls/month | 1 year daily; ~24h for hourly/OHLCV | Has a "people"/project endpoint that is unusual and possibly useful for narrative work |
| DexScreener | No | ~60 calls/min | None | On-chain pairs only; no history, so not usable for the screener |
| CryptoDataDownload | No | Bulk CSV downloads | Since 2017 | Not an API — use it for a one-time historical backfill, then keep current via ccxt |

**Recommendation:** ccxt against a major exchange for all OHLCV; CoinGecko for cross-sectional
market data. Both are free and neither requires a key for what my_site needs.

### Hyperliquid — display-only narrative attention proxy (new, 24-09-26)

`api/data/hyperliquid_narrative_adapter.py` (narrative-dashboard RFC-2), a keyless wrapper around
the existing `ccxt_adapter._exchange()` singleton — no new provider identity, no new credential.
`fetch_daily_market_snapshot()` calls `_exchange().fetch_tickers(params={"type":"swap"})`, keeps
only active, non-HIP-3 perps, and never raises. Two derived series: per-category volume share
(denominator = all active non-HIP-3 perps + an explicit `unmapped` bucket, shares sum to 1) and a
new-listing count from a day-over-day market-list diff (`no-baseline-yet` on day one, never a bare
`0`). It is **display-only** — never wired into `trigger.compute_trigger` or
`GET /api/narrative/categories`, feeds only `GET /api/narrative/history`.

**Ticker keying:** meme perps use a `k`-prefixed base that ccxt upper-cases (`kPEPE` → `KPEPE`);
the resolver checks `base == SYM` or `baseName == "k"+SYM`. Confirmed against the installed `ccxt`
4.5.78 source (`parse_ticker` maps `dayNtlVlm` → `quoteVolume`) — not yet confirmed against a real
live payload (container egress blocks Hyperliquid; user-PC step).

**Licensing:** `redistributable=false`, pending — Hyperliquid's terms of use for redistributing
market data were not checked (egress blocked at RFC-2 Stage 0). `HYPERLIQUID_REDISTRIBUTABLE` is a
single constant in the adapter file; flip to `true` only after the user reads Hyperliquid's ToU/API
docs directly. Until then this data is personal-use-only by default, same posture as London
Strategic Edge.

## Macro Liquidity

### LiqTide (liqtide.com) — recommended for the cycle/regime feature

Open daily JSON. No authentication, no key, no rate limit stated. Attribution (a link back to
liqtide.com) is the only stated condition.

```
GET https://liqtide.com/data/latest.json
```

Refreshes daily around 22:45 UTC. Top-level keys include `generated_utc`, `data_quality`,
`tide_index` (value, label, score, components, weights), `tide_series` (historical date/value
pairs), `regime`, `regime_plain`, `signals`, `sectors`, `lead_chart`, `fng`, and `metrics` —
the last carrying time series for net liquidity, WALCL, TGA, RRP, reserves, dollar index,
central-bank holdings, stablecoin supply and BTC.

**The published methodology matters more than the endpoint.** The LiqTide Score is a 0–100
composite of six impulses, each normalised to −1…+1:

| Component | Weight | Underlying source |
|---|---|---|
| US net liquidity, 4-week change | 30% | Federal Reserve H.4.1 / FRED |
| Stablecoin supply, 7-day change | 25% | DefiLlama |
| Broad dollar, inverted, 1-month | 15% | Stooq |
| ON-RRP release, 4-week | 10% | NY Fed Markets API |
| Spot-ETF flows, 5-day | 10% | Farside Investors |
| BTC dominance rotation, inverted, 30-day | 10% | CoinGecko |

Core identity: `NET LIQUIDITY = WALCL − TGA − RRP`.

Every underlying source in that table is itself free. So LiqTide is usable two ways, and the
second is what de-risks it:

1. **Consume the endpoint** — one HTTP call gives a finished regime read. Fastest path to a
   working cycle dashboard.
2. **Reproduce the composite** from FRED, the NY Fed Markets API, DefiLlama, Stooq, Farside and
   CoinGecko. More work, but it removes the dependency, makes the weights tunable to this
   project's own view, and allows a deeper backfill than the endpoint's own history.

Start with (1) and treat (2) as a migration path, not a rewrite. Shape the adapter so the swap
is invisible to everything above it.

**Risk:** the product describes itself as beta and free "while it's beta". Terms can change and
the endpoint can move. Cache every daily payload locally from the first fetch, so that a
discontinuation costs the future rather than the history.

**Per-series data-cadence reference (added 24-09-26):** every regime-dashboard series carries a
declared `max_gap_days` (its normal release cadence plus holiday slack) so real data holes can be
flagged (`gap_before: bool` per point) instead of silently interpolated. The authoritative table of
these values and their reasons lives in code, not here — `api/analytics/regime/components.py`'s
`MAX_GAP_DAYS_REASONS` — because the values are re-checked against live cadence and should not
drift out of sync with a duplicated doc copy. See `GET /api/regime/components` (§11 of
`process/features/cycle-regime/completed/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`)
for the response shape that carries these flags.

### Farside Investors — spot-BTC ETF daily flows

New adapter, `api/data/etf_flows_adapter.py` (added 24-09-26, regime dashboard RFC-003). Scrapes
Farside's public flows table with stdlib `html.parser` — no API, no key. Cached, cache-first;
**at most one request per UTC day** (LiqTide's own archived index fills any gap between fetches,
so a missed day is not a data hole). `redistributable: false` — **personal use only**, per Standing
Rule 7 — checked at the RFC-001 Stage 0 gate before building (see
`regime-dashboard-farside_FEASIBILITY_24-09-26.md`). Data starts 2024-01-11 (the day US spot BTC
ETFs launched); no dates before that are meaningful for this series, and the regime dashboard marks
them `not_applicable` rather than `unavailable` — a real, structural distinction, not a gap.
Real-data check at RFC-003: cached 2024-01-11 → 2026-09-23 (677 days), only US holidays and the
current day missing.

**Standing Rule 8 implemented, 2026-09-20.** `api/scripts/snapshot_liqtide.py` archives each
day's payload to `api/data/cache/liqtide/` (now git-tracked via a `.gitignore` negation carve-out
— see `process/context/all-context.md` Environment and Configuration). Confirmed operationally,
not just in theory: LiqTide has no historical endpoint, so this archive is genuinely the only way
to ever get pre-today LiqTide history, and it can only grow one day at a time from whenever the
script is actually run. As of this note the archive holds a single day. A downstream consumer
(`api/scripts/compare_composite_variants.py`, checking full-vs-reduced liquidity-composite
agreement) needs materially more history than that before it can produce a meaningful answer —
see the Open Questions entry in `all-context.md` for the current state of that question.

## Equity Providers

There is no free equity feed with the quality of the free crypto feeds. This is a structural
difference, not a search failure — with one possible exception, below.

| Provider | Free-tier limits | Caveats |
|---|---|---|
| **London Strategic Edge** | One free API key, "no paywall, no credit card". Streaming and downloads share a single allowance, checkable at `GET /vault/usage` | **Redistribution prohibited — see Licensing below.** Claims 133bn ticks / 118,000 datasets / 30+ years, 14 candle resolutions, options chains with greeks, macro series for 194 countries, bond yields, bulk Parquet export. Python client `lse-data` on GitHub (MIT, ~160 stars, active) |
| Alpaca | Free tier with IEX-sourced data; key required | Practical starting point; IEX-only coverage is thinner than a consolidated feed |
| Finnhub | ~60 calls/min | Advertised as real-time; approximately 20-minute delay in practice. Limited history |
| Alpha Vantage | 5 calls/min | Daily bars only, ~15-minute delay. Reliable but too slow for a screener |
| Twelve Data | ~800 calls/day | Reported delays of several hours on the free tier |
| Polygon | Real-time is paid only | Free tier capped at 1 year of history — a hard limit for cointegration work, which needs long samples |
| Tiingo | Small free tier | Worth evaluating; end-of-day coverage is decent |

**Avoid:**

- **Yahoo Finance** (and the unofficial wrappers around it) — no supported API; rate limits are
  enforced without warning and calls fail unpredictably. Acceptable for a throwaway experiment,
  never as a dependency.
- **IEX Cloud** — sunset in 2025. Do not build on it.

**Recommendation:** history depth, not rate limit, is the binding constraint for equities —
cointegration needs long samples and most free tiers cap history short. London Strategic Edge
is the only free option found that plausibly solves that, so **evaluate it first, but verify
before committing**: pull a known symbol over a long window and check it against a second
source for gaps, splits and adjustment handling. "133 billion ticks, free" is a strong claim
from a small operator and deserves one afternoon of verification rather than trust. If it
verifies, Alpaca becomes the fallback; if it does not, plan a one-time paid historical pull
rather than a monthly subscription.

### Licensing — the constraint that decides this

The `lse-data` client is MIT, but **the data is not**: it may be used for personal research and
trading and **may not be redistributed or resold to third parties**.

That splits my_site's two phases:

- **Personal use (now):** fully usable. Screener, backtests, research — all fine.
- **Public later (stated goal):** serving LSE-derived values to other users is redistribution.
  A public my_site cannot ship LSE data to its users without separate permission.

This is exactly why providers sit behind adapters. Keep every LSE-derived series flowing through
one adapter and tag it as non-redistributable at the boundary, so that the day the app opens up,
the question is "which adapter do we swap" and not "which of these numbers are we allowed to
show". Crypto via ccxt and exchange public endpoints does not carry this restriction; LiqTide
requires attribution but permits use.

Re-read the actual terms before the public launch decision — this note is a summary, not a
licence.

## Narrative / Mindshare Data

This is the weakest link in the stack and should be treated as an open risk.

- There is no strong free tier for social/narrative data. LunarCrush is effectively paid.
  Santiment has a limited free tier. The vendors that do this well price accordingly.
- Free-ish partial substitutes: Google Trends (via the unofficial `pytrends`, which breaks
  periodically), CoinGecko trending endpoints, Reddit's API free tier, and exchange volume /
  new-listing data as a crude attention proxy.
**Decision, 2026-09-17: free proxies only, explicitly labelled.** Build the feature on Google
Trends (via the unofficial `pytrends`), the Reddit API free tier, CoinGecko trending endpoints,
and exchange volume / new-listing activity as a crude attention proxy. Every narrative value is
rendered with a visible data-quality caveat and carries less weight than price-derived signals in
any combined confidence read.

No paid vendor is bought until the signal has demonstrated, on this project's own history, that it
changes a sizing decision. That is the bar — not whether the chart looks interesting.

Practical consequences of building on proxies:

- `pytrends` is unofficial and breaks periodically. Treat a failed narrative fetch as a normal
  condition: the feature degrades to "unavailable", it does not take the dashboard down.
- Proxy series are not comparable across sources. Normalise within a source and compare changes
  over time, not levels across providers.
- Cache aggressively. These sources are the most likely to rate-limit or disappear without notice.

**pytrends backfill scale caveat (added 24-09-26, narrative-dashboard RFC-2/RFC-3):**
`api/scripts/backfill_pytrends_history.py` uses `pytrends.interest_over_time()` to pull one
269-day daily window per category on day one (`pytrends` is not a project dependency — every
invocation needs `uv run --project api --with pytrends ...`). Each Google Trends request is
independently rescaled 0-100 on its own request window, so a `backfill-269d` point and a
`nightly-7d` point (the daily forward-archive window) are **not on the same scale** even though
both come from the same source. Any consumer (composite maths, UI) must flag values spanning the
two variants as `mixed_scale` rather than treat them as directly comparable — do not silently mix
them into one line.

**Reddit-in-CI stance (added 24-09-26, narrative-dashboard RFC-4):** the nightly narrative-snapshot
workflow deliberately ships with **zero** secrets mapped into its job `env`. When
`REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` are unset (the CI default), the nightly script writes
**no row at all** for Reddit that day — not an explicit `unavailable` row — so downstream readers
see Reddit's absence as "no archived data", distinct from a fetch that ran and failed. Turning
Reddit history on later needs **two** manual changes together, not one: adding the two GitHub
Actions repo secrets, AND a two-line `env:` mapping edit to the workflow file itself. Secrets alone
do nothing — this is a deliberate two-step gate, not an oversight.

## On-chain Activity

Added 2026-09-28 (chain-growth plan, `process/features/onchain-activity/completed/chain-growth_25-09-26/`;
RFC-1 VERDICT `chain-growth-feasibility_FEASIBILITY_25-09-26.md`). Feeds the `/onchain` page.
Chain list: `api/data/chains.json`. Cache: `api/data/cache/onchain/{source}/{chain}/{metric}.parquet`
(git-tracked carve-out), written nightly by `chain-growth-snapshot.yml` (22:00 UTC).

### growthepie — primary source (`api/data/growthepie_adapter.py`)

- **Keyless.** Host `https://api.growthepie.xyz`.
- Endpoints: per-chain `/v1/metrics/chains/{chain}/{metric}.json`; bulk `/v1/export/{metric}.json`;
  `master.json` for the supported chain/metric list. `/v1/metrics/{metric}.json` returns 403 — don't use it.
- Chain keys used: `ethereum`, `base`, `arbitrum`, `optimism`, **`polygon_pos`** (Polygon),
  `robinhood` (Robinhood Chain, launched 2026-07-01). Metric keys `daa` → `active_addresses`,
  `txcount` → `transactions`. Full history comes back in one call, so there is no backfill script.
- **Licence: CC BY 4.0 → `redistributable=True`**, on condition of the attribution, verbatim and
  shown once per page: **"Source: growthepie, https://www.growthepie.com."**

### L2BEAT — cross-check only (`api/data/l2beat_adapter.py`)

- **Keyless.** Activity (transactions) for base, arbitrum, optimism and robinhood; Optimism's slug is
  **`op-mainnet`**; request full history with **`range=max`**.
- **Personal use → `redistributable=False`.** Raw values are archived but never served; the API
  exposes only a divergence % against growthepie (display-only).

### Rejected

- **Dune — NOT-VIABLE** (RFC-1): every API execute returned **HTTP 402** (datapoint limit), the
  user's free account is **read-only**, and Dune's terms make API output personal/internal only.
  No `DUNE_API_KEY` exists anywhere in the repo.
- **Etherscan V2, Artemis** — rejected as paid-gated for the needed volume/chains.
- **Consequence:** Solana, BNB Chain and Tron have **no free keyless source**; they stay in
  `chains.json` and render as "source unavailable". New-addresses is not tracked (no free source).

## Libraries

All free and open-source. Licences checked at setup on 2026-09-17.

| Purpose | Library | Licence | Notes |
|---|---|---|---|
| Charting | `tradingview/lightweight-charts` v5 | Apache-2.0 | Canvas-based, built for financial series. Not to be confused with TradingView's separate Charting Library, whose terms are different |
| Exchange access | `ccxt` | MIT | Unified API across 100+ exchanges |
| Statistics | `statsmodels` | BSD-3 | `coint` for Engle-Granger, `coint_johansen` (under `tsa.vector_ar.vecm`) for Johansen. The reason Python is in this stack |
| Volatility / GARCH | `arch` | NCSA | Volatility modelling, useful for regime work |
| Indicators | `pandas-ta` | MIT | Current line is a 0.4.x beta; pin the version deliberately |
| Indicators (alt) | `pandas-ta-classic` | MIT | Maintained community fork, 250+ indicators; the safer choice if `pandas-ta` beta instability bites |
| Indicators (alt) | `TA-Lib` | BSD | Fastest, C-based, but has real install friction. Only if profiling justifies it |

**Do not write a second implementation of an indicator in TypeScript** to avoid a round trip.
See "One source of numerical truth" in `all-context.md`.

## Source Paths

Deeper docs in this group, as they are created:

- (none yet — this entrypoint is currently self-contained)

Related:

- `process/context/all-context.md` — Open Decisions table tracks the unresolved provider choices
- `process/features/cointegration-screener/_GUIDE.md` — the feature most constrained by history depth
- `process/features/narrative-mindshare/_GUIDE.md` — the feature most constrained by data availability

## Update Triggers

Update this group when:

- a provider is chosen, added, dropped or replaced
- a free-tier limit changes, or one is hit in practice (record which, and when)
- a library is added, pinned to a new major version, or replaced
- a licence changes, or the public-launch plan changes what redistribution is needed
- a provider is deprecated or sunset

## Canonical Notes

Provider facts age quickly — limits and tiers on this page were checked in September 2026 and
should be re-verified before any decision that depends on an exact number. When one turns out
to be stale, correct it here rather than in a plan file.
