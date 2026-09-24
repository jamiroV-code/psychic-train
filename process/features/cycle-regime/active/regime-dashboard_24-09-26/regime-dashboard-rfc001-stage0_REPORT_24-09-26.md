# RFC-001 Stage 0 — Pre-Phase Research Findings

**Date**: 24-09-26
**Plan**: `regime-dashboard_PLAN_24-09-26.md` (RFC-001: LiqTide raw archive, history backfill + source research)
**Status**: 🧪 Stage 0 complete — awaiting user approval before Step 2 (no code written)

> **TL;DR** — LiqTide's formula is confirmed exactly: `score = Σ weight × component`, and
> `value = 50 + 50 × score` (the 0–100 index). Our archived `tide_score` is the −1..+1 `score`, not
> the 0–100 value. Today's payload carries ~2 years of *weekly* published index (112 points from
> 2024-09-04) and all six component impulses for today only — so the daily raw archive is the only
> way to build per-component LiqTide history. The −1..+1 normalisation is confirmed **not
> published** (ADR-5 stays an assumption). Farside has daily ETF flows from 2024-01-11 as an HTML
> table, "all rights reserved", no API; usable for personal use only and needs a live probe from
> your PC. No free deep BTC-dominance source exists. No existing test calls `fetch_latest`, so the
> raw write is safe (E2 cleared).

How this was gathered: the cloud sandbox's egress proxy blocks `liqtide.com` (CONNECT 403), so the
live payload and pages were read through the web-fetch tool (structured extraction, not raw bytes).
The exact raw JSON is captured for real in Step 3 by `fetch_latest` on your machine.

---

## 1. Live LiqTide payload (24-09-26)

**Top-level keys:** `generated_utc`, `data_quality`, `headline`, `tide_index`, `tide_series`,
`regime_plain`, `overnight`, `distance`, `talker`, `lead_chart`, `sectors`, `regime`, `signals`,
`metrics`, `gold`. (New since RFC-002 Stage 0 of the screener: `headline`, `overnight`, `distance`,
`talker`, `gold`.)

**`tide_index`:**

| Field | Value |
|---|---|
| `value` | 52 (the 0–100 index) |
| `label` | "SLACK WATER" |
| `plain` | "NO CLEAR FLOW" |
| `score` | 0.0427 (−1..+1) |
| `components` | net_liquidity_4w −0.3772 · stablecoin_7d 0.4669 · dollar_1m −0.4612 · rrp_release_4w −0.0006 · etf_flow_5d 0.9302 · rotation_30d 0.1536 |
| `weights` | 0.30 · 0.25 · 0.15 · 0.10 · 0.10 · 0.10 |

**Arithmetic check (done by hand):**
0.3(−0.3772) + 0.25(0.4669) + 0.15(−0.4612) + 0.1(−0.0006) + 0.1(0.9302) + 0.1(0.1536)
= **0.04269 ≈ 0.0427 = `score`** ✓, and 50 + 50 × 0.0427 = 52.1 → **52 = `value`** ✓.

Consequences:
- The composite formula in ADR-5 (`50 + 50 × Σw·x`) matches LiqTide exactly. Only the per-component
  normalisation to −1..+1 is unknown.
- `components` are **already signed** (the inversions for dollar and BTC-dominance rotation are
  applied inside the published value) — so the RFC-002 sign cross-check compares our signed
  contribution directly against these.
- The archived parquet column `tide_score` (−0.0701 on 2026-09-20) is `score`, not `value`. The
  published-index line on the dashboard must use `value` (0–100); the backfill and daily archive
  both carry it.

**`tide_series`:** 112 points, `[date, value]` pairs, first `["2024-09-04", 50]`, last
`["2026-09-16", 32]`. Dates are Wednesdays → **weekly**, aligned to the Fed H.4.1 release. So the
published index history is ~2 years, weekly — enough for the agreement stats (ADR-5), not for the 3y
default view (as expected — hence the reproduction).

**`metrics.*.series` (thinned, roughly weekly or less):**

| Key | Points | First | Last (as_of) |
|---|---|---|---|
| net_liquidity | 113 | 2024-09-04 | 2026-09-16 |
| walcl | 113 | 2024-09-04 | 2026-09-16 |
| tga | 121 | 2024-09-03 | 2026-09-21 |
| rrp | 144 | 2024-09-03 | 2026-09-22 |
| reserves | 113 | 2024-09-04 | 2026-09-16 |
| dollar | 161 | 2024-09-03 | 2026-09-18 |
| ecb_usd | 104 | 2024-09-06 | 2026-09-18 |
| boj_usd | 24 | 2024-09-01 | 2026-08-01 |
| stables | 155 | 2024-09-03 | 2026-09-22 |
| btc | 226 | 2025-09-24 | 2026-09-23 |
| **btc_dom** | **183** | **2025-06-10** | 2026-09-23 |
| fng | 91 | 2026-06-26 | 2026-09-23 |

- **No per-component history is published** — `tide_index.components` is today only. The only way
  to accumulate LiqTide's own component values is the daily raw archive (ADR-4). Confirms the
  archive is the priority of RFC-001.
- `btc_dom` history starts 2025-06-10 at ~2–3-day spacing — this is the best available source for
  the BTC-dominance panel (see §4).
- `signals` also carries `etf_flow5` = 1,660,000,000 (5-day ETF flow, USD) and `rrp_d4w`,
  `rrp_level` — worth keeping in the raw archive; `etf_flow5` gives a daily ETF cross-check going
  forward.
- **ON-RRP is near zero:** `rrp` = $0.45bn (from $349.8bn on 2024-09-03), and
  `rrp_release_4w` ≈ 0. The ON-RRP panel will be nearly flat since the facility drained in 2025.
  That is the real data, not a bug — worth a line in its drill-down.

## 2. LiqTide methodology (`liqtide.com/method.html`)

- Published: the net-liquidity identity, the 6-weight table, the data sources (FRED/H.4.1, US
  Treasury FiscalData, NY Fed Markets API, DefiLlama, Farside, CoinGecko, Stooq), and the label
  bands: **0–19 RIP TIDE · 20–39 EBB TIDE · 40–59 SLACK WATER · 60–79 FLOOD TIDE · 80–100 SPRING TIDE**.
- **Not published:** the −1..+1 normalisation (formula, lookbacks, clipping), sign conventions, API
  terms/rate limits/history. The page says the score is a "proprietary blend, open methodology".
- Attribution: the embed must keep its link to LiqTide.com. No API licence text found.
- → ADR-5's normalisation (expanding z, clip ±3, /3, 90-obs warm-up) remains a documented
  assumption; agreement stats vs `tide_series` make the gap visible.
- Note: the 2026-09-20 archive row has `generated_utc` 00:25 UTC, later than the ~22:45 UTC refresh
  noted in the data-sources doc. A 02:00 Brussels run (00:00 UTC in summer) could run before that
  day's payload exists. **Proposed: schedule at 03:00 Brussels** (01:00 UTC summer / 02:00 UTC
  winter). Each generated date is still captured once either way.

## 3. Farside (spot-BTC ETF daily flows)

| Question | Finding |
|---|---|
| Format | HTML table, US$m, one column per ETF (IBIT, FBTC, BITB, ARKB, BTCO, EZBC, BRRR, HODL, BTCW, MSBT, GBTC, BTC) + `Total` |
| History | `https://farside.co.uk/bitcoin-etf-flow-all-data/` starts **11 Jan 2024** (the fetch tool truncated the page, so the live end date must be confirmed by a real request); `/btc/` shows the last ~2 weeks |
| API / CSV | None found |
| robots.txt | Only a `Twitterbot` rule with empty `Disallow` — no restriction for other agents |
| Terms | "© 2025 Farside Investors. All rights reserved." No reuse licence |
| Feasibility risk | Farside is commonly behind bot protection; can't be tested from this sandbox (proxy). Needs a live probe from your PC with `httpx` |

**Proposed verdict: `build`, personal use only** — adapter flagged `redistributable=false`, fetch
at most once a day, parse the `Total` column only, cache-first, and degrade to `unavailable` with
a reason if the page blocks or changes. Before a public launch this source must be replaced or
licensed. A first-request probe runs at the start of RFC-003; if it's blocked, RFC-003 becomes
`skip` and the ETF panel shows "unavailable — source blocked" (from 2024-01-11) while the raw
LiqTide archive keeps `signals.etf_flow5` going forward.

## 4. BTC dominance — deeper free sources

| Source checked | Result |
|---|---|
| CoinGecko `/global/market_cap_chart` | paid tier only (already known from RFC-002) |
| Coinranking `stats/bitcoin-dominance-history` | requires the Professional plan; free plan capped at 1 year |
| CoinMarketCap historical global metrics | paid API |
| LiqTide `metrics.btc_dom.series` | free, from **2025-06-10**, ~2–3-day spacing |

**None found.** The panel uses the LiqTide `btc_dom` backfill + daily archive, starting 2025-06-10,
with "no data before 2025-06-10 (no free deep history source)" as its gap reason.

## 5. Repo checks

- `.gitignore`: `api/data/cache/*` + `!api/data/cache/liqtide/` → `raw/` and `backfill_*.parquet`
  inside it are tracked. ✓
- **E2 (validate-contract):** no test in `api/tests/` calls `fetch_latest` or writes the LiqTide
  archive (`test_liquidity_composite.py` monkeypatches `read_liqtide_history`;
  `test_snapshot_liqtide.py` tests pure helpers only). The only caller of `fetch_latest` is
  `api/scripts/snapshot_liqtide.py`. Adding the raw write is safe; new tests still use
  `isolated_cache`. ✓ cleared.
- `snapshot_liqtide.py` already has an arithmetic check against `WEIGHTS` — the §1 identity can be
  asserted there on every run.

## 6. Proposed Step 2 (detailed plan for RFC-001), pending approval

1. `cache.py`: `liqtide_raw_path(date)`, `write_liqtide_raw(date, raw)` (no-overwrite, compact
   UTF-8 JSON), `read_liqtide_raw(date)`, `list_liqtide_raw_dates()`.
2. `liqtide_adapter.fetch_latest`: on a fresh parse and not `dry_run`, also call
   `write_liqtide_raw`. Also add `tide_value` (0–100) and `tide_label` as **new last** columns of
   the archive row (additive; `tide_score` unchanged for existing readers).
3. `api/scripts/backfill_liqtide_series.py`: from the newest raw JSON, write
   `cache/liqtide/backfill_{date}.parquet` with rows `series_key, date, value` for `tide_series`
   (key `tide_value`) and every `metrics.*.series`; idempotent; skips missing keys (no zeros).
4. Tests (`isolated_cache`): raw written once; same-date second write is a no-op; `dry_run` writes
   nothing; malformed payload writes nothing; backfill rows match a synthetic payload; missing
   series skipped.
5. Ops Runbook: Task Scheduler at **03:00** Brussels, absolute `uv.exe` path.
6. Run on your machine: `uv run --project api pytest api/ -q`, then
   `uv run --project api python api/scripts/snapshot_liqtide.py` (twice) and the backfill script;
   paste the DuckDB coverage query into the RFC-001 phase report.

## Decisions needed

1. Farside verdict: build for personal use (proposed) or skip.
2. Snapshot time: 03:00 Brussels (proposed) instead of the plan's 02:00.
3. Archive row gains `tide_value` + `tide_label` columns (proposed, additive).
