---
name: spec:narrative-baskets-weighted-signal
description: "T98: replace Discovery's min-2-sources rule with owner-weighted sources (percent, sum 100, rescaled per coin), a coin trigger, and a point-in-time history chart for backtesting entries. Docs only; no code changed."
date: 18-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Narrative Baskets: weighted signal + history chart (T98, 18-10-26)

Builds on S-F1 (Discovery API) and T96 (lag tolerance). "Momentum" means attention momentum, never price. Code references below were read on `main` at 39b698c unless marked UNVERIFIED.

## Goal

Discovery today says a coin is "gaining" when 2 independent source groups rise (`api/analytics/attention/discovery.py:63-64`, config `min_independent_sources` and `source_groups` in `api/data/discovery.json`). That treats a Wikipedia rise and a CoinGecko rise as equal, ignores how much of the signal exists, and gives no way to see in hindsight where a good entry was. This SPEC replaces the rule with owner-set source weights and a trigger, and adds a point-in-time history chart.

## Current behaviour (verified)

- `_source_change` (`discovery.py:38-56`): mean of last `recent_days` vs mean of the `window` days before; anchored to the source's own newest day; `None` if lag > `max_source_lag_days` (T96), too few points, or base mean <= 0.
- `_coin` (`discovery.py:59-69`): needs `need` usable sources; coin change is the plain mean of per-source changes; "rising" is `c > 0`.
- Winsorising per category at `winsor_percentile` (95): `discovery.py:112-114`. Category score = mean of winsorised changes, median beside.
- Sources come from `api/data/attention_weights.json` via `load_weights` (`score.py:10`): wikipedia, coingecko, exchange_volume, trends, reddit at 1.0, xsearch 0.25. Those are rank-score weights for another feature, not these percentages.
- `registry.read_series` (`api/data/attention/registry.py:36-51`) returns state `ok` only with >= `MIN_HISTORY_DAYS` = 90 points (`types.py:9`), and drops points on or after `today`. `hyperliquid_volume` is in `EXCLUDED_SOURCES` (`registry.py:23`).
- Trends stores ONE value per refresh (`trends.py:17-37`, state `insufficient-history`), so it has no real history yet. Its cross-coin comparability is undecided (`trends.py` docstring).
- UI: `DiscoveryTab.tsx` renders the window selector and `DiscoveryTable`; no per-coin view (`DiscoveryTab.tsx:67-69`). Payload: `api/models/discovery.py` (`DiscoveryCoin` has `gaining`, `sources_used`, `sources_gaining`). Router: `api/routers/discovery.py:19-24`, windows 7/30/90.

## Locked decisions (owner, 18-10-26)

1. **Weights.** Each source has a weight in percent in `api/data/discovery.json` (key `source_weights`), owner-editable. Starting: wikipedia 25, trends 25, reddit 20, xsearch 10, coingecko 10, github_dev 10. Binance `exchange_volume` and `hyperliquid_volume` carry no weight. `min_independent_sources` and `source_groups` are removed.
2. **Rescale.** A source with no usable value for a coin drops out; remaining weights are rescaled to that coin's available weight. Missing is never 0.
3. **Rising.** Source change over the window >= `rising_threshold_pct` (10).
4. **Trigger.** `rising_weight / covered_weight >= trigger_pct` (60) AND `covered_weight >= min_covered_weight` (30), where covered_weight is in points of the 100.
5. **Score.** Coin score = weighted mean of per-source changes over covered weight. Winsorise per category as today.
6. **Rows** expose `covered_weight`, `rising_weight`, `trigger`, and per source: `change`, `as_of`.
7. **T96** `max_source_lag_days` stays.
8. **History chart** for backtesting (below). **Detail columns** are a later web slice.

## Honest coverage today

Live and weighted sources are Wikipedia (25) and CoinGecko (10) only: max covered_weight is **35**. The 30 floor therefore needs Wikipedia present. A coin without a Wikipedia article reaches at most 10 and **can never trigger** until reddit, trends, xsearch or github_dev have data. With both live, a trigger needs rising_weight/35 >= 60%, i.e. Wikipedia alone (25/35 = 71%) is enough; CoinGecko alone is not. The trigger is effectively "Wikipedia is rising" until more sources land. The UI must say so (AC-W12). reddit, trends, xsearch are in the registry but whether their stores hold enough history to reach `ok` is UNVERIFIED (no parquet reader in this session; stores for them are not in the local cache listing).

## Acceptance criteria

- **AC-W1** `discovery.json` loads `source_weights`; load fails with a clear error if any weight < 0, the sum is outside 100 +/- 0.01, or a key is not a known source (known = `FETCHERS` keys minus `EXCLUDED_SOURCES`, plus `github_dev`).
- **AC-W2** `exchange_volume` and `hyperliquid_volume` are rejected as weighted keys; their data is unused by scoring.
- **AC-W3** A source whose series state is not `ok`, or whose change is `None`, is absent from that coin's covered_weight. A 0 value is never substituted.
- **AC-W4** Rescaling: score = sum(w_i * c_i) / covered_weight over available sources. Test: weights 25/10 both present gives (25a+10b)/35; Wikipedia only gives a.
- **AC-W5** A source is rising iff change >= 10.0 (boundary: 10.0 rising, 9.99 not). Constant comes from config, not code.
- **AC-W6** trigger true iff rising_weight/covered_weight >= 0.60 AND covered_weight >= 30. Tests for each side of both boundaries, plus 25 covered (no trigger even if 100% rising).
- **AC-W7** Coins with covered_weight below the floor still get a score and row but `trigger=false`; coins with zero available sources are omitted as today.
- **AC-W8** `DiscoveryCoin` gains `covered_weight`, `rising_weight`, `trigger`, `sources: [{source, change, as_of}]`. `gaining`, `sources_used`, `sources_gaining` are removed or kept as derived aliases (open question Q3). `gaining_count` becomes trigger count.
- **AC-W9** Winsorising per category and T96 lag behaviour are unchanged (existing tests stay green).
- **AC-W10** `GET /api/narrative/discovery/history?symbol=X&window=30` returns a daily series `[{date, score, covered_weight, rising_weight, trigger}]` for the coin; `?category=id` returns the category aggregate (mean of winsorised coin scores that day, and `triggered_count`).
- **AC-W11** Point-in-time: day D uses only points with date <= D; changing or deleting stored points after D does not change the value for D. Test: truncate the store at D and recompute D; results must be identical to the full-history result for D.
- **AC-W12** The 90-day gate is handled per AC-W13; the response carries `history_days` per source and the UI shows covered_weight as a band so thin days look thin. A text line states the max weight currently live.
- **AC-W13** Point-in-time scoring does not use `registry.read_series` state for day D (it checks the whole series length, a lookahead on data availability). Rule: a source counts on day D only if it has >= `MIN_HISTORY_DAYS` points ending at or before D, otherwise it drops out. Consequence: with about 99 days stored (owner figure, UNVERIFIED), a source with 90+ days of history only becomes usable on day ~90, so only about the last 9 days are scorable at window 30/7 on a 99-day store. Window 7 needs 7 + 7 days, window 30 needs 7 + 30, window 90 needs 7 + 90 beyond the first point. The gate is a config key `min_history_days` (default 90); owner may lower it for backtests (Q2).
- **AC-W14** Web chart (W3): coin price line on the same date axis, trigger days marked, covered_weight shown as a band. Price comes from the daily OHLCV cache (below). A coin with no price data renders the score chart and says price is unavailable.
- **AC-W15** Empty and error states follow the existing Discovery pattern (`DiscoveryTab.tsx:44-69`): loading, retry, plain no-data line.
- **AC-W16** No lookahead in the chart: the trigger flag plotted on day D is the stored/computed value for D, never recomputed with later data.

## Price series source

`cache.read_ohlcv(symbol, "1d")` (`api/data/cache.py:122-131`), path `ohlcv/<SYMBOL>/1d.parquet` (`cache.py:118-119`), `Timeframe` includes `1d` (`cache.py:20`), refreshed by `api/scripts/refresh_cache.py` (UNVERIFIED which symbols). It is cheap (local parquet, no network). Not verified: coverage for the top-100 universe and whether the 1d cache is stored in this repo at all (`api/data/cache/ohlcv` is absent in this checkout). If a symbol lacks it, the smallest fallback is a close-only daily series from CoinGecko market chart for the chart's date range, fetched on demand and not stored (Q4).

## Backtesting traps

- **Lookahead (data).** Computing "today's" score over the full stored series then plotting it on past days is wrong. Each day must be rebuilt from points <= that day (AC-W11).
- **Lookahead (availability).** The 90-day gate (`registry.py:49`) looks at total stored length. Using it unchanged makes a source "ok" on every past day, including days before it had 90 days (AC-W13).
- **Lookahead (anchoring).** T96 lag is measured against `end`; for past day D use `end = D`, not today.
- **Trends scale mixing.** Trends values are relative per query and rescale between pulls (cross-coin comparability undecided, `trends.py` docstring). A backfill (T100) must be one normalised pull per coin (or anchored overlap stitching); stitching separate pulls changes the scale mid-series and fakes rises. Until T100 lands, Trends has one point per coin and drops out via the gate. Do not backfill inside this work.
- **Survivorship.** The universe is today's top-100; delisted or fallen coins are missing, so hit rates are optimistic.
- **Sample.** About 99 days, one or two regimes. Treat trigger hit rates as anecdotes, not statistics.

## Out of scope

Forward returns after triggers (later optional step, W2b: for each trigger day report close-to-close return at +N days, N configurable, excluding triggers with < N days of price after them, shown as a table beside the chart); new source code for github_dev (W5); T99 wiki article mapping fixes; T100 Trends backfill; detail table design beyond the column list; changes to `.github/`, My baskets tab, or rank-score weights in `attention_weights.json`.

## Proposed slices

| Slice | Content | Files (proposed) | Tier | USD |
|---|---|---|---|---|
| W1 | Weighted scoring, config validation, new row fields, tests, fixtures | `api/analytics/attention/discovery.py`, `api/data/discovery.json`, `api/models/discovery.py`, `web/lib/types/discovery.ts` (shape only), `api/tests/...` | RT2 | 2-3 |
| W2 | Point-in-time history endpoint (coin + category), no-lookahead tests | `api/analytics/attention/discovery_history.py` (new), `api/routers/discovery.py`, `api/models/discovery.py`, tests | RT2 | 2-3 |
| W2b (optional) | Forward return N days after trigger | same module | RT2 | 1 |
| W3 | Web chart: score, price overlay, trigger marks, covered band | `web/components/narrative/DiscoveryHistoryChart.tsx` (new), `web/lib/api/discovery.ts`, `DiscoveryTab.tsx` | RT3 | 3-4 |
| W4 | Dense detail table: per-source value and arrow, last stored day, days of history, raw vs capped change, covered weight, trigger badge | `DiscoveryTable.tsx` and a detail component | RT3 | 2-3 |
| W5 | New source `github_dev` (fetcher, store, probe record, registry entry); weight inert until data exists | `api/data/attention/github_dev.py` (new), `registry.py` | RT2 | 2-3 |
| T99, T100 | Wiki article fixes; Trends backfill | separate tasks | | |

Order: W1, W2, W3, then W4; W5 and T99/T100 are independent and raise real max coverage. Total about 12-17 USD without W2b.

## Risks

- With 35 live weight the trigger is "Wikipedia rising" in practice; the owner may read it as a multi-source signal. Mitigation: show covered_weight on every row (AC-W8, W12).
- Wikipedia spikes (events, bots) trigger alone. Winsorising limits the score, not the trigger.
- Backtest on a 99-day store with a 90-day gate leaves almost no scorable days (AC-W13). The chart may be near-empty until history grows or the gate is lowered.
- Per-day recompute cost: up to 100 coins x sources x ~99 days; fine in memory per request, but cache the history per (symbol, window) if slow (UNVERIFIED, not measured).
- `attention_weights.json` has similar-looking source keys with different meaning; name the new key `source_weights` and keep both documented.

## Open questions for the owner

- **Q1** Should rising use the raw change or the winsorised one? (Proposed: raw, since the threshold is a per-source level.)
- **Q2** May the backtest gate be lowered below 90 (e.g. 30) so the chart is useful now, accepting noisier early days? (Proposed: config key, default 90, chart shows a "thin" marker.)
- **Q3** Keep `gaining` and `sources_*` as aliases for one release, or remove?
- **Q4** Price overlay if a coin lacks a 1d OHLCV cache: accept "price unavailable" or fetch from CoinGecko on demand?
- **Q5** Category aggregate: mean of winsorised coin scores (consistent with today) or share of coins triggered? (Proposed: both, score as line, share as secondary.)
- **Q6** Should `github_dev` weight sit idle at 10 and silently rescale away until live? (Proposed yes; covered_weight shows it.)
