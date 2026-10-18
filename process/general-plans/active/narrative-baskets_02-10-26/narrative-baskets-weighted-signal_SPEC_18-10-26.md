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

1. **Weights.** Each source has a weight in percent in `api/data/discovery.json` (key `source_weights`), owner-editable. Starting (revised twice by the planner, 18-10-26): wikipedia 25, trends 25, reddit 15, xsearch 10, exchange_activity 10, github_dev 8, defillama 7 (sum 100). github_dev, defillama and exchange_activity are new, unbuilt (exchange_activity only partly), and inert until each has data. `coingecko` has no weight of its own: it stays for universe/eligibility and as the fallback volume source (decision 9). `min_independent_sources` and `source_groups` are removed.
2. **Rescale.** A source with no usable value for a coin drops out; remaining weights are rescaled to that coin's available weight. Missing is never 0.
3. **Rising.** Source change over the window >= `rising_threshold_pct` (10).
4. **Trigger.** `rising_weight / covered_weight >= trigger_pct` (60) AND `covered_weight >= min_covered_weight` (30), where covered_weight is in points of the 100.
5. **Score.** Coin score = weighted mean of per-source changes over covered weight. Winsorise per category as today.
6. **Rows** expose `covered_weight`, `rising_weight`, `trigger`, and per source: `change`, `as_of`.
7. **T96** `max_source_lag_days` stays.
9. **exchange_activity (composite).** ONE source, ONE weight (10), one source group, built from four exchanges: Binance, Coinbase, Kraken, Hyperliquid. Config `exchange_sub_weights` in `discovery.json`, owner-editable, sum 100. Starting sub-weights are a PROPOSAL, all UNVERIFIED: Binance 40, Coinbase 25, Kraken 15, Hyperliquid 20. Per coin: compute each exchange's own volume change over the window, then the sub-weighted average over exchanges that have data, sub-weights RESCALED over those present. Raw volumes are never summed across exchanges (an outage such as Binance HTTP 451 would fake a jump). Missing is never 0. Participation is meant to be derived from a published share of spot volume or CoinGecko exchange volume for the four; no figure was read in the repo, so none is claimed.
10. **CoinGecko fallback.** If exchange_activity has no usable exchange for a coin, CoinGecko volume (the existing `coingecko` series) feeds that slot at exchange_activity's weight (10). The row's source label is `coingecko`, not `exchange_activity`, so the owner sees which fed it. This keeps Discovery working while Binance is blocked and the other exchanges' reachability from US runners is UNVERIFIED. Binance stays, inside the composite (Q7 closed).
11. **History chart** for backtesting (below). **Detail columns** are a later web slice.

## Honest coverage today

Live today: Wikipedia (25) and volume (10, fed by the CoinGecko fallback until exchange_activity has data, since `exchange_volume` is blocked from US runners per the planner): max covered_weight is **35**. The 30 floor therefore needs Wikipedia present. A coin without a Wikipedia article reaches at most 10 (volume only) and **can never trigger** until reddit, trends, xsearch, github_dev or defillama have data. With both live, a trigger needs rising_weight/35 >= 60%, i.e. Wikipedia alone (25/35 = 71%) is enough; volume alone is not. The trigger is effectively "Wikipedia is rising" until more sources land. The UI must say so (AC-W12). reddit, trends, xsearch are in the registry but whether their stores hold enough history to reach `ok` is UNVERIFIED (no parquet reader in this session; stores for them are not in the local cache listing).

## Acceptance criteria

- **AC-W1** `discovery.json` loads `source_weights`; load fails with a clear error if any weight < 0, the sum is outside 100 +/- 0.01, or a key is not a known source (known = `exchange_activity`, `wikipedia`, `trends`, `reddit`, `xsearch`, `github_dev`, `defillama`; `coingecko` is not a weighted key).
- **AC-W2** `exchange_volume` and `hyperliquid_volume` are rejected as top-level weighted keys; they enter scoring only as exchange_activity members. `exchange_sub_weights` validates like AC-W1 (>= 0, sum 100 +/- 0.01, known exchanges only).
- **AC-W2b** exchange_activity: per-exchange change then sub-weighted mean rescaled over exchanges with data; test that dropping Binance (HTTP 451) rescales rather than producing a jump, and that raw volumes are never summed. Per-exchange `as_of` appears in row details.
- **AC-W2c** Fallback: no exchange has data for a coin, CoinGecko feeds the slot at weight 10 and the row source label is `coingecko`. When any exchange has data, CoinGecko is not used.
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

## New sources W5 and W6 (design notes)

Both need: fetcher, `FETCHERS` entry (`registry.py:12-20`), probe record, history behaviour, a mapping file. Both cover only mapped coins; a coin with no mapping drops the source and is rescaled, never 0. That makes their coverage partial, and `defillama` is meaningful only for DeFi, L1 and L2 coins.

- **github_dev:** commits and stars per project via the GitHub REST API. Key and rate limits: UNVERIFIED (unauthenticated limits are low; a token is likely needed, kept in env, never in files). One-call backfill: UNVERIFIED (commit activity may be available as weekly aggregates, stars history typically is not); if no backfill, history accrues one day at a time and the 90-day gate applies.
- **defillama:** TVL and fees, free API. Key and rate limits: UNVERIFIED. Historical TVL is publicly charted by DefiLlama, so a one-call backfill per protocol is plausible: UNVERIFIED, no provider was called. Fees history, same.
- **Daily fetch wiring:** `DEFAULT_SOURCES` in `api/scripts/refresh_attention.py:32` is `("wikipedia", "coingecko", "universe")`, and a test pins it (`api/tests/scripts/test_refresh_attention.py:103`). The workflow also hardcodes a source list for probe recording (`.github/workflows/attention-refresh.yml:106`). So adding a source likely touches `.github/`, which needs owner approval, beyond `DEFAULT_SOURCES`. Mark each slice's envelope accordingly.

## exchange_activity facts (W7)

- Binance already pulls `LOOKBACK_DAYS = 100` daily bars (`exchange_volume.py:18`, `fetch_ohlcv` at line 46) and stores quote volume as close * base volume (lines 55-56, an approximation). Source name `exchange_volume` (line 16).
- Hyperliquid keeps only a rolling 24h snapshot stored as the previous UTC day (`exchange_volume.py:75`), so it is forward-only, one point per refresh. A ccxt OHLCV backfill may be possible: UNVERIFIED live.
- Coinbase and Kraken have no adapter; ccxt is already the Binance client (`make_binance`, line 27). History per call and reachability from US runners: UNVERIFIED.
- History/point-in-time: each exchange is gated and anchored on its own series (AC-W13 per exchange); an exchange with under the gate's days drops out of that day's composite and sub-weights rescale. Hyperliquid will be absent in backtests for roughly its first 90 days, so early composites are Binance/Coinbase/Kraken only. The 90-day state gate in `_classify` (`exchange_volume.py:35`) mirrors `registry.py:49`.
- Wiring: `refresh_attention.py:196` maps source names to runners and `.github/workflows/attention-refresh.yml:193,200` runs `exchange_volume` and `hyperliquid_volume` as separate extra jobs, with a hardcoded source list at line 106. New sources (Coinbase, Kraken) therefore very likely need `.github/` edits (owner approval, Q8) as well as `refresh_attention.py` entries.

## W8: in-API fetch for sources GitHub runners cannot reach (design, revised by the planner, owner decision)

Why: some providers block GitHub runners (Binance HTTP 451 per the planner; Trends and Reddit reachability UNVERIFIED). The earlier Windows scheduled task design is DROPPED. The API itself fetches `pc_side` sources while it runs on the owner's PC, which is not on every day.

- **Side per source:** config key `fetch_side` per source in `discovery.json`, `github` or `pc_side`, owner-editable. Candidates for `pc_side`: Binance volume, Google Trends, Reddit only if blocked. Evidence (planner, run 4, 2026-10-18): Hyperliquid volume stored about 60 symbols from the GitHub runner, so it stays `github`. I read no run logs; Binance and Trends results are UNVERIFIED.
- **Pattern to reuse:** the lifespan starts workers (`api/main.py:48-58`: `refresh_worker.start_from_env()` and `equities_refresh.start_from_env()`, stopped in `finally`). The OHLCV worker is `api/data/refresh_worker.py` (T35/S8, env flags `SCREENER_REFRESH_WORKER` and `SCREENER_REFRESH_INTERVAL_SECONDS`, lines 49-50, tri-state at 342-346). The equities worker (S9E, `api/data/equities_refresh.py`) is a daemon thread (`EquitiesRefreshWorker`, line 154; thread started at 211) with `PASS_LOCK` (line 56) for one pass at a time, `start_from_env`/`stop_worker` (lines 361, 388), and the T51 catch-up rule `_behind` (line 231) used by `schedule_first` (lines 267+: catch-up 20 s after start when behind, else normal schedule).
- **Design:** a third worker, proposed `api/data/attention_pc_refresh.py`, started from the same lifespan. On API start it runs a catch-up in a background thread for `pc_side` sources, then repeats every few hours while the API is up. Idempotent (existing store merge, `store.py:41-56`), a lock so passes never overlap, per-provider rate limits, silent logging. A `_behind`-style check compares each source's newest stored day with the newest completed UTC day and fetches only if behind.
- **Catch-up:** backfillable sources fill the whole gap of days the site was not live: Binance (100 bars, `exchange_volume.py:18`), Kraken/Coinbase OHLCV, Hyperliquid OHLCV (UNVERIFIED live), Trends `today 3-m` with replace-whole-series semantics (needs a new write mode since `write_series` is first-wins; one normalised pull per coin to avoid the scale-mixing trap). Forward-only sources (Reddit) CANNOT catch up: gaps remain for days the API was off, so they stay on GitHub unless blocked; if blocked, gaps show as thin `covered_weight` days.
- **Non-blocking:** requests are never held. The API serves stored data immediately and marks the response as updating while a pass runs. A status payload (new field on Discovery/history responses, or a `/api/narrative/freshness` route) carries `updating: bool` and `last_stored_day` per source.
- **Web (owner accepts a visible wait):** Narrative tabs show an "updating data" state with last stored day per source, and refetch when the catch-up finishes (poll the status while `updating` is true). Files: `web/components/narrative/DiscoveryTab.tsx` plus the My baskets tab, and a shared status line component. UNVERIFIED which hook the baskets tab uses.
- **Stores:** the worker writes to the existing attention cache (`store.py:18`, `cache.CACHE_ROOT / "attention"`). The PC cache is not committed; the GitHub job and this worker could both write the same source, so a source is assigned to exactly one side by `fetch_side` and each worker skips sources of the other side. No shared file is written by both.
- **Scope:** touches `api/` and `web/`. Not `deploy/`: `deploy/start-api.ps1:33` runs `python -m uvicorn api.main:app`, so the lifespan runs on every start with no script change. Not `.github/`. (The worker must also not run in the GitHub runner or tests: use an env flag like `SCREENER_ATTENTION_PC_WORKER`, off in tests.)
- **Verification:** tests use fakes and an injected clock (RT2, RT3 for the web state); real provider behaviour needs owner PC probes after the build. Cost 4-6 USD.

## Out of scope

Forward returns after triggers (later optional step, W2b: for each trigger day report close-to-close return at +N days, N configurable, excluding triggers with < N days of price after them, shown as a table beside the chart); new source code for github_dev and defillama (W5, W6) and exchange_activity (W7); the in-API fetch is W8; T99 wiki article mapping fixes; T100 Trends backfill; detail table design beyond the column list; changes to `.github/` (needs owner approval, see Q8), My baskets tab, or rank-score weights in `attention_weights.json`.

## Proposed slices

| Slice | Content | Files (proposed) | Tier | USD |
|---|---|---|---|---|
| W1 | Weighted scoring, config validation, new row fields, tests, fixtures | `api/analytics/attention/discovery.py`, `api/data/discovery.json`, `api/models/discovery.py`, `web/lib/types/discovery.ts` (shape only), `api/tests/...` | RT2 | 2-3 |
| W2 | Point-in-time history endpoint (coin + category), no-lookahead tests | `api/analytics/attention/discovery_history.py` (new), `api/routers/discovery.py`, `api/models/discovery.py`, tests | RT2 | 2-3 |
| W2b (optional) | Forward return N days after trigger | same module | RT2 | 1 |
| W3 | Web chart: score, price overlay, trigger marks, covered band | `web/components/narrative/DiscoveryHistoryChart.tsx` (new), `web/lib/api/discovery.ts`, `DiscoveryTab.tsx` | RT3 | 3-4 |
| W4 | Dense detail table: per-source value and arrow, last stored day, days of history, raw vs capped change, covered weight, trigger badge | `DiscoveryTable.tsx` and a detail component | RT3 | 2-3 |
| W5 | New source `github_dev` (commits, stars per project): fetcher, registry entry, probe record, coin to repo map `api/data/github_repos.json` (new) | `api/data/attention/github_dev.py` (new), `registry.py`, `api/scripts/refresh_attention.py` | RT2 | 3-5 |
| W6 | New source `defillama` (TVL and fees, DeFi/L1/L2 coins only): same pieces, coin to protocol slug map `api/data/defillama_slugs.json` (new) | `api/data/attention/defillama.py` (new), `registry.py`, `refresh_attention.py` | RT2 | 3-5 |
| W7 | `exchange_activity` composite: Coinbase and Kraken adapters (ccxt, about 40 lines each, planner estimate), composite reader, `exchange_sub_weights` config, CoinGecko fallback, per-exchange `as_of` in rows, point-in-time handling | `api/data/attention/exchange_volume.py`, new `coinbase`/`kraken` fetchers, `registry.py`, `refresh_attention.py`, `discovery.py` | RT2 | 4-6 |
| W8 | In-API background fetch for sources GitHub runners cannot reach (design below): worker, `fetch_side` config, freshness status, web updating state | `api/data/attention_pc_refresh.py` (new), `api/main.py`, `discovery.json`, `api/routers/discovery.py`, `DiscoveryTab.tsx` | RT2 + RT3 + owner PC probes (RT4) | 4-6 |
| T99, T100 | Wiki article fixes; Trends backfill | separate tasks | | |

Order: W1 (includes the fallback and composite reader against existing Binance data), W2, W3, then W4; W5, W6, W7 and T99/T100 are independent and raise real max coverage. Total about 26-39 USD without W2b. Worker ceiling 185 USD (informational); per-slice cap 15 USD, planner asks the owner at 7 USD.

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
- **Q7** CLOSED by the planner: Binance stays, inside exchange_activity.
- **Q10** W8 runs a background thread inside the API on the owner PC: accept a visible 'updating' state on Narrative tabs while catch-up runs, and the env flag name?
- **Q9** Approve the exchange_sub_weights proposal (40/25/15/20), or give a participation figure and source?
- **Q8** May W5/W6 slices edit `.github/workflows/attention-refresh.yml` (needed to record probes for new sources)?
- **Q6** Should the `github_dev` (8) and `defillama` (7) weights sit idle and silently rescale away until live? (Proposed yes; covered_weight shows it.)
