---
name: plan:narrative-baskets-quality-over-speed
description: "T164 AUDIT + PLAN (COMPLEX, docs only): every time budget, cap, skip rule and threshold in the attention pipeline, classified S/R/Q/T; a github/server host-profile design; per-source data-quality metrics for the Sources panel; prioritized slices. Owner directive 24-10-26: the pipeline will run on the owner's PC and later on a 24/7 laptop server, so runner limits must stop costing data quality."
date: 24-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# Quality over speed: attention pipeline audit and host-profile PLAN

Date: 24-10-26
Complexity: COMPLEX (audit, config design, metrics design, nine slices with different approvals; two need the owner's explicit approval before any `.github/` text is written)
Status: VALIDATED (docs only). Gate: PASS (see the Validate Contract). Nothing in this task builds code; the slices below each need their own envelope.
Validation: T164 worker, 24-10-26, on `origin/main` 7229a80. Open PRs read at their heads: #162 (b11bac8), #161 (691c923), #166 (e8e4362). No provider was contacted.

**Summary (plain language).** Many limits in the code were chosen for GitHub's once-a-day, time-boxed runner, not for data quality. The worst effects, in order of damage: (1) Google Trends, Reddit and X (60 of the 95 weight points that can ever be live) are not live, and without them the trigger rule cannot fire at all; (2) the slow sources run in a second job AFTER the daily Discovery snapshot has been frozen, so the frozen record never contains them; (3) a pass that is cut by a time budget or killed by a step timeout drops coin-days, and the scorer needs all 7 of the last 7 days, so one missing day removes the whole source for that coin; (4) X reads only about 10 coins a day and keeps 1 of the 7 days it pays for; (5) history is capped at 100 days and forward-only sources need 90 days of waiting. A server host removes (2), (3) and most of (1) and (4) by giving every pass the time it needs, spacing requests more widely (never closer), and continuing unfinished work in the next window instead of cutting it. The ban and rate-limit protections stay as they are or get slower. Scoring numbers are not touched by anything here.

## Overview and Context

Context router: `process/context/all-context.md`; tests: `process/context/tests/all-tests.md`. Direction: `north-star.md`. This is a WORKER task (T164): `ROLE: WORKER`, docs only, no code, no `.github/` edit, `api/data/trends_keywords.json` untouched. The owner's directive (24-10-26): the attention pipeline will run on the owner's PC and later on a spare laptop running 24/7 as a server; make sure every system has enough time and does not cut quality; focus on quality of data.

**What "main" contains.** The brief names several items (Trends 540 s budget, 3 s spacing, 429 backoff 30/60/120 s, rotation by UTC day, `pc_pace.py`, `density.py`, `web_queries.py`, `attention_queries.json`, the collector block) that are NOT on `origin/main` 7229a80. They live in open draft PRs. Every inventory row below says where its value is read: **main** (cited `file:line` on 7229a80), **#162** (Trends fetch, head b11bac8), **#161** (collector core, head 691c923) or **#166** (checker, head e8e4362). A row on a PR is design-ready but cannot be built on until that PR merges.

Phase Completion Rules: this task is done when the plan file and the report exist, the plan validator prints 0 failures, `git diff --check` is clean, the file set is exactly those two files, no secret is present, and the banned-name grep prints nothing. Each slice in section 7 has its own completion rule (red tests first, gates, report).

## 1. Goal and non-goals

**Goal.** Find every place where speed, budget or a runner limit reduces data quality, and design how a server host removes it without raising ban or rate-limit risk; define per-source quality metrics that make the remaining losses visible.

**Non-goals.** No code, no workflow text, no scoring or threshold change, no weights change, no provider call, no keyword-file edit. Thresholds that are statistics choices (class T) are listed and measured, not changed.

## 2. Method and classification

Read: `api/scripts/refresh_attention.py`, `api/data/attention/*.py`, `api/data/reddit_adapter.py`, `api/data/pytrends_adapter.py`, `api/analytics/attention/{discovery,sources,signal_snapshots,discovery_history}.py`, `api/data/discovery.json`, `api/data/attention/probe_records.json`, `.github/workflows/attention-refresh.yml` (read only), the checker and probe tools; and the PR heads above. Every cited line was read on the stated commit.

Classes: **S** safety (rate-limit or ban protection: KEEP; marked E if the value is backed by evidence in the repo, G if it is a guess). **R** runner-driven (exists because of GitHub's time or IP limits: LIFT or relax on a server). **Q** quality-reducing (drops coins, shrinks samples, cuts windows or history, truncates a pass, rounds, or marks missing because time ran out). **T** threshold or statistics choice (needs a backtest, not a time fix). A row can carry two letters.

Timing basis used for the arithmetic below: Trends request = 3 s spacing + 0 to 2 s jitter (mean 1 s) + 0.5 s latency (owner evidence of 21-10-26, quoted in the T100b PLAN) = **4.5 s mean**. 75 coins with a keyword = 338 s. A coin that meets a 429 and uses the full backoff costs 30 + 60 + 120 = 210 s plus four requests.

## 3. Inventory (cite = file:line)

### 3.1 Runner (`api/scripts/refresh_attention.py`, main unless marked)

| ID | Item and value | Cite | Class | Quality loss (example) and server-host value |
|---|---|---|---|---|
| P1 | `DEFAULT_SOURCES = wikipedia, coingecko, universe, signals`; volume, Trends, Reddit, X are opt-in and run in a second job | refresh_attention.py:31-32 | R | Slow sources arrive after the snapshot (see P8). Server: one ordered day plan, snapshot last. |
| P2 | `CIRCUIT_BREAKER_AFTER = 5`: after 5 consecutive 429s the rest of Wikipedia or CoinGecko is marked `capped`, never fetched | :34, :71-84 | S(G) + Q | 5 transient 429s on coins 3 to 7 leave the other ~70 coins without a value that day. Server: keep the streak, but after the cool-down requeue the skipped coins in a later slot instead of dropping them. |
| P3 | `SOURCE_TIME_BUDGET_S = 360`: opt-in sources stop when spent; the rest are `capped` "time budget reached" | :36, :92-114 | R + Q | Illustration at 5 s per coin: 360 / 5 = 72, so the last 6 of 78 coins get no value that day; each such coin-day is a hole in the 7-day window (D2). Server: no fixed deadline (section 5). |
| P4 | Series are written only after the whole source pass returns | :281-293 | R + Q | A killed step (8-min Trends timeout, sleeping laptop, power cut) loses every coin fetched in that pass. Server: write each coin as it arrives (atomic, idempotent). |
| P5 | `today` is fixed once at process start | :263 | R | A pass that crosses 00:00 UTC labels late coins with the old day. Server: take `today` per request; a coin whose response straddles midnight is requeued. |
| P6 | Exit code: a source is `ok` if at least one series is ok (1 of 78 counts as green) | :294, :306-308 | Q (blind) | A thin pass looks healthy. Server: the quality record (section 6) carries coverage; exit codes unchanged. |
| P7 | Per-source isolation; `signals` never fails the run | :231-247, :298-300 | S | Keep in both profiles. |
| P8 | `signals` snapshot runs in job 1; Trends, Reddit, X, volume run later in `refresh-extra`; `take_snapshot` never overwrites an existing record | refresh_attention.py:32; attention-refresh.yml:173, :189-230; signal_snapshots.py:124 | R + Q | The frozen point-in-time record for day D is computed before that day's slow sources exist, so it can never contain Trends, Reddit or X. Server: snapshot last, with a `sources_present` list in the record (slice HP4). |
| P9 | Wikipedia and CoinGecko fetch serially with no concurrency | :140-162 | S | Keep. |
| P10 | `xsearch` dry run unless `X_LIVE=1`; estimate printed | :196-201 | S | Keep. |

### 3.2 Google Trends

| ID | Item and value | Cite | Class | Loss and server value |
|---|---|---|---|---|
| T1 | main: one latest value per refresh from `pytrends_adapter.fetch_trend`, timeframe `now 7-d`; 3 tries, sleeps 1 and 2 s; new `TrendReq` per attempt; no spacing between coins | pytrends_adapter.py:34-36, :62, :77; refresh_attention.py:177-178 | Q | Superseded by #162; the 7-day relative timeframe returns sub-daily rows (UNVERIFIED), so the stored daily value is one sample (T3 in section 8). Needs 90 forward days. |
| T2 | #162: one coin per request, explicit 100-day daily range, at least 90 complete days, replace-series store, `MIN_REPLACE_DAYS = 90` | #162 trends.py:46-47; store.py:45 | Q (fixed) | Keep in both profiles. |
| T3 | #162: `TRENDS_INTERVAL_S = 3.0` plus 0 to 2 s jitter | #162 refresh_attention.py:43, :58, :277-278 | S(G) | Owner run of 23-10-26: every request after about 100 failed with ConnectionError at 3 s spacing, and the checker sent 137 before it stopped (#166 body). So 3 s is NOT proven safe at volume. Server: spacing can only go up. |
| T4 | #162: 429 backoff 30, 60, 120 s on the same coin, then `capped` | #162 refresh_attention.py:44, :220-232 | S(G) + Q | #166 tells the owner to wait 30 to 60 minutes after a refusal; waits of seconds burn requests and the coin. Server: first 429 pauses the whole source for a cool-down (minutes), then resumes. |
| T5 | #162: `TRENDS_BREAKER_AFTER = 3`; the code comment says it cannot fire at the production constants | #162 refresh_attention.py:45-47 | S | Keep. |
| T6 | #162: `TRENDS_TIME_BUDGET_S = 540`, also checked before each backoff wait | #162 refresh_attention.py:48, :270, :228 | R + Q | No 429: 75 x 4.5 = 338 s fits. One 429 episode: coins 1 and 2 use 420 s; coin 3 starts near 425 s and its first wait to 455 s is allowed, the next wait would end past 540 s, so it is capped, and the remaining ~72 coins get "time budget reached". Server: no pass deadline. |
| T7 | #162: coin order rotated by UTC day number so a budget stop starves different coins | #162 refresh_attention.py:255-256 | R | Only exists because of T6. Server: least-recently-pulled first (a carried-over coin goes first next window). |
| T8 | #162: too-little-interest rule: median below 3, or zero days at 40 % or more; quiet-then-surge 7 days, 3x | #162 trends.py:49-57 | T | Placeholders until owner probe P-RES. Not changed here. |
| T9 | #162: `NAME_RISK_SYMBOLS` bare names skipped without a request | #162 trends.py:63 | Q + T | Those coins are missing until a topic is pasted. Owner action, not time. |
| T10 | #162: per-pull archive `trends_pulls/<pull-date>.parquet`, first write per symbol and pull date wins | #162 store.py (`write_pull_archive`) | quality-positive | Keep; it is the evidence source for revised-value flags (section 6). |
| T11 | workflow: Trends step `timeout-minutes: 8` (480 s) is below the 540 s budget; job `refresh-extra` 40 min | attention-refresh.yml:204, :176 | R + Q | The step is killed before the budget ends, no `trends:` line is printed (`attention_extra` reports "step crashed or timed out"), and with P4 every fetched coin is lost. T100c (`.github/`, owner approval) raises it to 14. Server: n/a. |
| T12 | Trends 429 from cloud IPs is expected on GitHub | attention-refresh.yml:23 | R | Server on a residential IP avoids the cloud-IP block; the per-IP volume limit in T3 still applies. |
| T13 | `geo=""` worldwide, no language filter | #162 trends.py (`fetch_alone`) | T | Choice, not time. |

### 3.3 Wikipedia, CoinGecko, exchange volume

| ID | Item and value | Cite | Class | Loss and server value |
|---|---|---|---|---|
| W1 | `LOOKBACK_DAYS = 100` | wikipedia.py:17, :37 | Q | History stops at 100 days; no backtest of T-class thresholds. Server: one-time deep backfill (store is first-write-wins, so additive); daily pull stays 100. |
| W2 | `MIN_INTERVAL_SECONDS = 0.25` (about 4 calls/s) | wikipedia.py:22 | S(G) | Comment says "far under Wikimedia guidance"; not measured here. Keep. |
| W3 | 3 retries on 429, backoff base 1 s, Retry-After cap 30 s, timeout 10 s | wikipedia.py:18-21 | S(G) | Keep. A final 429 returns `capped` (coin-day missing); server requeues it. |
| W4 | No article mapped gives `no-article`; probe record: 29 of 92 coins reached 90+ days on 23-10-26 | wikipedia.py:33-34; probe_records.json:1 | structural | About 45 coins have no article (owner count). No config fixes this (section 8). |
| W5 | One fetch at about 07:23 UTC; values are first-write-wins, allowed lag 3 days | attention-refresh.yml:31; attention_freshness.py:11-12; store.py:41-47 | T + Q risk | If a provider revises yesterday's value later, the first value stays. Server MUST NOT fetch earlier than the github slot for first-write-wins sources until revision is measured (section 5, rule E3). |
| C1 | `MIN_INTERVAL_SECONDS = 6.0` | coingecko_attention.py:23 | S(G) | Comment cites vendor guidance of about 5 to 15 calls/min. 78 coins = 468 s. Keep. |
| C2 | 3 retries on 429, base 5 s, Retry-After cap 90 s | coingecko_attention.py:20-24 | S(G) | Keep. |
| C3 | `days: 100`, `interval: daily` | coingecko_attention.py:119 | Q | Same history cap. Server: deeper once (public-tier history limit UNVERIFIED, believed 365 days). |
| C4 | `CATEGORY_PAUSE_SECONDS = 2.0` (10 category calls) | coingecko_attention.py:30, :102 | S(G) | Keep. |
| C5 | Top-100 snapshot is the universe; stablecoin and wrapped lists duplicated here and in `discovery.json` | coingecko_attention.py:33-34; discovery.json:49-54 | T | Two lists can drift. Not time. |
| E1 | Binance `limit=100` daily bars, `LOOKBACK_DAYS = 100` | exchange_volume.py:18, :46 | Q | Same cap (ccxt allows more per call, UNVERIFIED). |
| E2 | `enableRateLimit: True` | exchange_volume.py:29 | S(E) | ccxt weights; keep. |
| E3 | "Quote volume" = close x base volume of each bar, an approximation | exchange_volume.py:1-7, :55 | Q (accuracy) + T | Not a time issue. Binance klines carry the exact quote volume; changing it mixes two definitions in one stored series, so it needs an owner decision (slice not scheduled). |
| E4 | Binance returns HTTP 451 from US runners; the step is `continue-on-error`, 4-min timeout | attention-refresh.yml:188-190 | R | Binance carries sub-weight 40 of the exchange slot (discovery.json:34); on GitHub that member is usually missing and the slot falls to the other exchanges or CoinGecko. Server on a normal IP: restored. |
| E5 | Hyperliquid: forward-only, one rolling-24h snapshot per refresh stored as "yesterday"; probe record shows 6 days of history | exchange_volume.py:1-6, :75; probe_records.json:1 | Q + R | A snapshot taken at about 07:30 UTC covers 07:30 to 07:30, not the calendar day, and the series needs 90 days (about mid-January 2027) before it counts. Server: snapshot at 00:02 UTC so the rolling window is the calendar day. It cannot create history faster. |
| E6 | Coinbase and Kraken have no fetcher | discovery.py:39-41 | Q | Dropped from the slot; future work. |
| E7 | `defillama` has weight 5 but no fetcher and no probe record | discovery.json:9; registry.py:12-20 | Q | Max live weight is 95, not 100. Not time. |

### 3.4 Reddit and X

| ID | Item and value | Cite | Class | Loss and server value |
|---|---|---|---|---|
| R1 | API search `t=day`, `limit=100` per coin, one subreddit (r/CryptoCurrency) | reddit_adapter.py:34, :77 | Q | A count of 100 is a cap, not a count. |
| R2 | The window is the last 24 h before the run, stored as "yesterday" | reddit.py:41-65 | Q | At a 07:23 UTC run the window is yesterday 07:23 to today 07:23; the day label is off by the run time. Superseded by the collector (exact UTC-day windows); not fixed on the API path. |
| R3 | Retries 3, backoff 1 and 2 s, `time.sleep` not injectable; no pacing between coins | reddit_adapter.py:35-36, :84; refresh_attention.py:190-193 | S(G) | 78 searches back to back; the pacing is a gap, not a cap. Server: pace. |
| R4 | Reddit step 8 min timeout; runs only with secrets | attention-refresh.yml:224, :210-222 | R | Keep or lift on a server. |
| R5 | #161: Reddit request delay 60 to 120 s, 150 requests/day, `reddit_sample_min 10`, 12 subreddits | #161 attention_queries.json (collector block); web_queries.py:38-41 | S(G) | SPEC "locked rules", no measured ban threshold. At a 90 s mean, 150 requests take 3.75 h, so the BUDGET binds, not time. Whether 150 requests cover 78 coins (about 1.9 per coin) is a W8c question. |
| X1 | `X_MAX_READS_PER_RUN 10`, `PER_DAY 50`, `USD_PER_DAY 1.0`, `USD_PER_READ 0.01`; the workflow runs the X step once a day | xsearch.py:54-57; attention-refresh.yml:85-90 | S (owner spend) + Q | One daily step with max 10 reads reads 10 of 78 coins; a coin is read about every 8 days. A gap in the 7-day window removes the source for that coin. Server: the daily cap of 50 stays (spend is an owner decision); reads are spread and the 7-day payload is fully stored (X2). |
| X2 | `counts/recent` returns 7 daily counts per read but only `done[-1]` is stored | xsearch.py:131-148 | Q | 6 paid days thrown away per read; storing all returned completed days fills 7-day gaps from one read at no extra cost (first-write-wins keeps the first value). Slice XS. |
| X3 | Spam flag at 10x median, text in the reason only | xsearch.py:29, :107-111 | T | Keep. |
| X4 | #161: delay 180 to 360 s per query, page gap 5 to 15 s, `x_daily_post_budget 800`, `x_sample_n 40`, `x_sample_min 20`, `x_page_cap 3`, `x_backfill_days 14` | #161 web_queries.py:29-37 | S(G) + Q | Sample of 40 posts gives about 16 % relative error per day (1/sqrt(40)); at the floor of 20, about 22 %. The 800-post budget covers 20 coins if every coin needs the full 40, and up to all 78 if most coins are quiet (an exact count costs only k < 40 posts). The real spread is UNMEASURED; measure before changing anything. |
| X5 | #161: budget halves after a warning day (floor 1 unit), doubles once after 7 clean days up to the configured value; pause for the rest of the UTC day or until the owner acts | #161 pc_pace.py:33, :196-200 | S(E-by-design) | Keep identical in both profiles. The ceiling stays at the configured value. |
| X6 | #161: 14 backfill days vs the 90-day history gate | #161 web_queries.py:37; types.py:10 | Q | A new X series needs about 76 more days of forward collection. Raising backfill raises the post budget use: an S decision, not a runner one. |

### 3.5 Discovery statistics (T unless noted)

| ID | Item and value | Cite | Class | Note |
|---|---|---|---|---|
| D1 | `MIN_HISTORY_DAYS = 90` is the live gate; `min_history_days: 30` in config is read only by the history chart | types.py:10; registry.py:49; sources.py:63; discovery.json:42; discovery_history.py:67 | T + Q | The scorer needs only recent 7 + base `window // 2` days: 10 days (window 7), 22 (30), 52 (90). A 60-day series is unusable for all windows today. Two gates disagree (90 vs 30). Needs a backtest. |
| D2 | `recent_days = 7`, strict: `len(now) < recent` returns no change | discovery.json:44; discovery.py:178 | T (amplifies Q) | One missing day in the last 7 drops the source for that coin. Every budget cut, rotation or skipped coin becomes a lost source. |
| D3 | `max_source_lag_days = 3`; each source scored on its own newest day | discovery.json:45; discovery.py:172-175 | T | Sources can be scored up to 3 days apart. |
| D4 | `winsor_percentile 95`, `rising_threshold_pct 10`, `trigger_pct 60` | discovery.json:39-41, :43; discovery.py:335 | T | Backtest. A 10 % rise is below the Poisson noise of a low-count source (section 8). |
| D5 | `min_covered_weight = 30`; `early_sources = trends, reddit, xsearch` must include a rising source for a trigger | discovery.json:15, :41; discovery.py:253-255 | T (but see effect) | Probe records show only Wikipedia, CoinGecko and Hyperliquid probed (probe_records.json:1). Live weight is at most exchange 15 + Wikipedia 10 = 25 < 30, and no early source is live: no coin can trigger today. Making Trends live (25) gives 50. |
| D6 | Weights: trends 25, reddit 20, xsearch 15, exchange 15, wikipedia 10, defillama 5; `search` group votes once | discovery.json:3-14 | T | Not touched. |
| D7 | `MAX_LAG_DAYS`: wikipedia 3, coingecko 2, exchange 2, reddit 2, trends 3 | attention_freshness.py:11-12 | T | Workflow staleness only. |
| D8 | Signal windows 7, 30, 90; snapshot first-write-wins with a config hash | signal_snapshots.py:49, :124 | T (+ P8) | Keep. |
| D9 | Sources panel shows state, history days, newest day, note; no coverage or sample information | sources.py:67-78, :123-126; DiscoverySourcesPanel.tsx:80-82 | Q (blind) | Section 6. |

### 3.6 Workflow (read only) and checker/probe tools

| ID | Item and value | Cite | Class | Note |
|---|---|---|---|---|
| K1 | One schedule, `23 7 * * *`; concurrency group `attention-refresh`, no cancel | attention-refresh.yml:31, :43-44 | R | One observation slot per day. Server: continuous trickle. |
| K2 | Job `refresh` has no timeout (default); `refresh-extra` 40 min; steps Binance 4, Hyperliquid 4, Trends 8, Reddit 8 min | :176, :190, :197, :204, :224 | R | See T11. |
| K3 | `continue-on-error` on every extra step and the X step | :85, :189, :196, :203, :223 | S | A slow source cannot block the others. Keep the idea in the tick design. |
| K4 | Verify step parses only `wikipedia`, `coingecko`, `universe` (+ `categories`) result lines and freshness for the first two | :106-135 | R | Extra sources are judged by `attention_extra.py` (warn, not fail). The server needs its own verifier, not a copy of the YAML. |
| K5 | Commit steps pull-rebase and push with 3 attempts | :149-170, :245-265 | R | A server that also writes the store needs a single-writer rule per source (owner decision O1). |
| H1 | Checker and probe spacing: `INTERVAL_SECONDS = 3.0` (checker, probe), `1.0` (wiki titles); main stops after 3 consecutive 429 | check_trends_keywords.py:54-55; probe_trends.py:35; check_wiki_titles.py:23 | S(E-partial) | The 3 s value met the real limit on 23-10-26. |
| H2 | #166: stop after 3 consecutive failures of any kind (exit 4); `--delay` can only go up from 3 s; pause 20 s every 40 requests; at most 4 queries per coin; variants opt-in | #166 check_trends_keywords.py:60-65, :93 | S(E) | Same shape as the server rule "spacing only goes up". |

## 4. What loses quality, ranked by payoff

1. **Trends, Reddit, X not live (D5, T1, X1, R5).** 60 weight points absent; trigger impossible. Fix path: #162 merges, T100c (owner), then server behaviour HP2. Payoff: very high.
2. **Snapshot frozen before slow sources (P8).** Even when the slow sources work, the point-in-time record misses them. Payoff: high, small change (slice HP4).
3. **Pass cut or killed (P3, P4, T6, T11) amplified by the strict 7-day rule (D2).** Payoff: high.
4. **X coverage (X1, X2, X4).** 10 coins/day and 1 of 7 days stored. Payoff: medium-high, XS is cheap and safe.
5. **Window mismatch (R2, E5).** Reddit API and Hyperliquid label a run-time 24 h window as a calendar day. Payoff: medium; Hyperliquid fixed by a 00:02 UTC slot.
6. **History depth (W1, C3, E1, D1, X6).** Cap at 100 days, 90-day wait for forward-only sources. Payoff: medium; unlocks backtests.
7. **Short, wasteful backoffs and skip-the-rest breakers (P2, T4).** Payoff: medium.
8. **Binance 451 on GitHub (E4).** Sub-weight 40 lost. Payoff: medium; automatic on a normal IP.
9. **Health-blind success (P6, D9).** Payoff: makes everything above visible.

## 5. Host profile design

**File.** `api/data/attention_host.json` (new; sits next to `attention_queries.json` of #161), loaded by a new `api/data/attention/host_profile.py` (pure, no network). Two named profiles, `github` and `server`, plus a `same_in_all_profiles` list kept as a documented, test-pinned set.

**Selection.** Environment variable `ATTENTION_HOST_PROFILE` (`github` or `server`). Unset = `github` = today's behaviour (a pin test compares every `github` value to the current constants). An unknown value exits 2 with a message (never silently falls back). The effective profile is printed as the first line of every run and written into each quality record. The workflow never sets it, so GitHub runs are unchanged.

**What the profiles may differ in (time and schedule only).**

| Key group | `github` (equals today) | `server` |
|---|---|---|
| Pass deadline | Default sources 360 s (:36); Trends 540 s (#162 :48) | `null`: none. The expected pass length is DERIVED: `n_todo x (interval + mean jitter + latency estimate) x 1.5 + breaker_after x sum(backoff)`. If it does not fit before 23:30 UTC the pass runs to its natural end and unfinished coins carry into the next window; nothing is capped for time. |
| Trends order | rotate by UTC day (#162 :255) | least-recently-pulled first (a state file `_host_state/trends.json`: pull date, last success per coin) |
| Trends pacing | 3 s + 0 to 2 s | trickle: one coin every 10 to 20 minutes (75 coins in about 15 to 25 h), jitter large. Spacing is a FLOOR of the github value: the loader rejects any `server` interval, jitter, backoff or pause value lower than `github`'s. |
| 429 handling | 30/60/120 s on the same coin, breaker 3 | keep the sequence; after the first final `capped` coin, pause the whole source for `cooldown_s` (starting at 1800, the #166 guidance) then resume the queue; breaker 3 unchanged |
| Write timing | after the pass | per coin, atomic |
| `today` | fixed at start | per request; a response that straddles 00:00 UTC is requeued |
| Schedule | the workflow's single 07:23 UTC slot | a tick (below) |
| Observation time (first-write-wins sources) | 07:23 UTC and later | NOT earlier than the github slot for Wikipedia and CoinGecko until revision is measured (rule E3); Hyperliquid at 00:02 UTC |
| Snapshot | job 1, before slow sources | last: after every source is done or at 23:30 UTC, with `sources_present` recorded |
| Reddit | API, no pacing | #161 collector (60 to 120 s, 150/day) plus `comments.rss` every 2 h (a poll with no overlap with the previous poll is recorded as a gap, because comments between polls were lost) |
| X | one daily step, 10 reads | spread over the day, same daily cap of 50 reads (owner spend), all 7 returned days stored; collector ceiling and adaptive budget unchanged |
| Archive id enrichment | n/a | once a day (the #161 archive step) |

**What stays identical in both profiles (test-pinned).** Request shapes (100-day explicit range, `geo ""`, one coin per request), the retry counts and 429 backoff sequence, every breaker streak, the User-Agent strings, the 0.25 s / 6 s / 3 s spacing floors, the X adaptive budget (halve after a warning day, double after 7 clean days, ceiling = configured), the pause rules, completed-UTC-days-only storage, first-write-wins and replace-series semantics, the interest rule constants, the density formula, the 90-day gate, and every Discovery threshold and weight. A profile can change WHEN and HOW LONG, never WHAT a stored number means.

**Tick design (no daemon).** `api/scripts/attention_host_tick.py`, run every 5 minutes by the OS scheduler (Task Scheduler or cron). Each tick reads the state files, decides which source is due under the active profile, does at most one unit of work, and exits. It is restart-safe and catches up after a laptop sleep because "due" comes from state (last success per source and coin), not from a timer. The clock and `sleep` are injected. One lock file prevents two ticks overlapping.

**Rules.**
- **E1.** A server pass never marks a coin missing because of time; it marks it `deferred` and keeps it first in the queue.
- **E2.** Safety first: nothing in `server` may reduce spacing, remove a breaker, raise a daily request cap above the configured ceiling, or retry after a warning.
- **E3.** Do not move observation time earlier for first-write-wins sources; add a re-check pass (for example at day +3) that stores the second observation as a `revised` flag and never overwrites the first value.
- **E4.** One writer per source (owner decision O1): the server profile owns a source only when the workflow step for it is disabled.
- **E5.** Missing is missing, never 0 (unchanged).

**Tests needed (injected clock, fake clients, no network).** Default profile is `github`; every `github` value equals the current constant; unknown profile exits 2; `server` cannot lower a floor key; a server pass over 75 fake coins with 3 injected 429s ends with all coins fetched or `deferred`, none `capped` for time; unfinished coins lead the next window after a restart; per-coin write survives a kill after coin 40; a response that straddles midnight is requeued; the cool-down pauses the whole source and then resumes; the tick does nothing when not due and one unit when due; the first-write-wins value is unchanged after a re-check.

## 6. Data-quality metrics (stored, shown, not scored)

**Principle.** Quality fields are evidence. Discovery scoring never reads them; a test asserts that `build_discovery` output is byte-identical with and without the quality files present.

**Per coin-day record** (one per source, coin and value date): `status` (`ok` or `missing`); `missing_reason` from a closed list (`no-article`, `no-keyword`, `name-ambiguous`, `too-little-interest`, `time-budget`, `rate-limited`, `budget-exhausted`, `deferred`, `paused`, `fetch-failed`, `not-run`); `attempts`; `http_429_count` and `backoff_s_total`; `sample_n` and `sample_cap` (`none`, `n-reached`, `pagecap`, `budget`) for X and Reddit; `collected_at` (UTC) and `lag_h = collected_at - (value_date + 1 day)`; `partial_day` (window start not reached, canary missing); `revised` (`none` or old/new value from a later re-check); `profile`.

**Per source-day aggregate:** `eligible` (coins in the universe that this source can ever cover), `structural_missing` (no article, no keyword, ambiguous, too little interest), `attempted`, `fetched`, `missing_by_reason`, **coverage** = fetched / (eligible - structural_missing) (operational), **structural coverage** shown beside it, **completeness** = coins with at least 90 stored days and no gap in the last 7 days / eligible, `sample_capped_share`, `retries`, `elapsed_s`, `stopped_by` (`none`, `breaker`, `pause`, `budget`, `deferred`), `revised_share`, and the **source health** state.

**Source health** (one closed state, deterministic precedence): `off` > `not-probed` > `blocked` (breaker or pause active) > `stale` (newest day beyond `max_source_lag_days`) > `partial` (operational coverage below 90 % or more than half of samples capped) > `healthy`. The 90 % and one-half figures are placeholders (class T), tuned after 14 days of data. A large structural gap (Wikipedia: 29 of 92 coins usable) shows as text beside `healthy`, never as an operational failure.

**Where it lives.** `<cache>/attention/<source>/_meta/quality/<run-date>.json`, one immutable file per source and run date, created atomically if absent (same first-write-wins pattern as `signal_snapshots.py:124`), under the same `_meta/` root that #161's `web_evidence.py` uses (coordinate the layout when W8b merges). The workflow's `git add -f api/data/cache/attention/` already commits it; the Wikipedia/CoinGecko verify globs `*.parquet` non-recursively, so a `_meta/` folder does not disturb them. Re-checks write `_meta/quality/revisions/<check-date>.json`; the original is never rewritten. **Point-in-time:** every field is stamped with `collected_at`; the panel reads the newest record whose `collected_at` is on or before the as-of time, so a past day shows what was known then.

**Web panel (text only; design).** One extra line per source row in `DiscoverySourcesPanel.tsx`, from a new optional `quality` object on `DiscoverySourceRow`:
`Google Trends: partial. Today 61 of 75 fetched (13 deferred for time, 1 rate-limited). 5 coins skipped by design. Newest value collected 6 h after day end. 2 values revised vs the earlier pull.`
`X search: partial. Samples capped on 31 of 40 coin-days (cap 40). Budget 800 posts, 790 used. Source paused until tomorrow.`
`Wikipedia: healthy. 29 of 29 usable fetched. 46 of 92 coins have no article (structural).`
No numbers beyond these fields; no score.

## 7. Prioritized slices

Sizes are estimates. Code slices run on opus (EXECUTE rule), docs on sonnet. "Start now" = no open PR touches its files.

| # | Slice | Files (new unless marked) | Red-first tests | Gates | Model | USD (ask / cap) | Approval | Blocked by | Start |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **QS1** quality record, reader, panel line | `api/data/attention/quality.py`; edit `api/analytics/attention/sources.py`, `api/models/discovery.py`; edit `web/components/narrative/DiscoverySourcesPanel.tsx`; tests `api/tests/data/attention/test_quality.py`, `api/tests/analytics/attention/test_sources_quality.py`, web panel test | `test_record_is_immutable_first_write_wins`, `test_missing_reason_is_from_closed_list`, `test_coverage_excludes_structural_missing`, `test_health_precedence_order`, `test_reader_returns_newest_record_at_or_before_as_of`, `test_discovery_output_identical_with_and_without_quality_files`, `panel shows health line and structural text` | pytest data/attention, analytics/attention, tooling_guards; web vitest of the panel; diff-check; file set | opus | 5 / 8 | Owner ENTER EXECUTE | none (the runner hook is slice 2) | yes |
| 2 | **QS2** runner records quality | edit `api/scripts/refresh_attention.py` (small hook per source), tests | `test_each_source_writes_one_quality_record`, `test_thin_pass_is_partial_not_ok`, `test_exit_codes_unchanged` | scripts + attention tests; G7-style frozen-file hashes | opus | 4 / 6 | Owner ENTER EXECUTE | #162 (same file), slice 1 | after #162 |
| 3 | **XS** store all returned X days | edit `api/data/attention/xsearch.py`, `api/tests/data/attention/test_xsearch.py` | `test_all_completed_days_returned_not_only_last`, `test_first_write_wins_keeps_earlier_value`, `test_one_read_counted_once` | data/attention tests | opus | 2 / 4 | Owner ENTER EXECUTE | none | yes |
| 4 | **HP4** snapshot last, `sources_present` | edit `api/analytics/attention/signal_snapshots.py`, runner order; tests | `test_snapshot_records_sources_present`, `test_existing_records_never_rewritten`, `test_config_hash_unchanged_by_new_field` | signals tests; frozen snapshot hashes (as G7 of the T100b PLAN) | opus | 3 / 5 | Owner ENTER EXECUTE | #162 (runner file) | after #162 |
| 5 | **HP1** host profile loader, JSON, selector, pins | `api/data/attention_host.json`, `api/data/attention/host_profile.py`, `api/tests/data/attention/test_host_profile.py`; guard in `tooling_guards` | the section 5 tests for default, pin, unknown, floors | data/attention + tooling_guards | opus | 4 / 6 | Owner ENTER EXECUTE | none (Trends keys added in slice 6) | yes |
| 6 | **HP2** Trends server behaviour: derived pass, carry-over, least-recently-pulled, cool-down, per-coin write, per-request `today` | edit `api/scripts/refresh_attention.py`, `api/data/attention/host_profile.py`, state helper; tests | `test_server_pass_defers_never_caps_for_time`, `test_carry_over_leads_next_window`, `test_cooldown_pauses_whole_source`, `test_per_coin_write_survives_kill`, `test_midnight_straddle_requeued` | scripts + data tests with injected clock | opus | 6 / 9 | Owner ENTER EXECUTE | #162, slices 2 and 5 | after #162 |
| 7 | **HIST** deeper history, additive | edit `wikipedia.py`, `coingecko_attention.py`, `exchange_volume.py`, tests | `test_deep_backfill_adds_only_missing_days`, `test_daily_pull_unchanged` | data/attention tests; no scoring file changes | opus | 3 / 5 | Owner ENTER EXECUTE; one provider probe by the owner for the limits | none | yes (probe first) |
| 8 | **TICK** tick runner and server schedules, single-writer ownership | `api/scripts/attention_host_tick.py`, state helpers, tests; docs for the OS scheduler | the tick tests of section 5 | scripts tests | opus | 6 / 9 | Owner ENTER EXECUTE + O1, O2 | slice 5, #162, #161 for Reddit/X units | after 5 |
| 9 | **WF** workflow text: T100c (Trends step timeout 8 to 14, `pytrends` install, failure class); disable a step when the server owns that source; set no profile | `.github/workflows/attention-refresh.yml`, guard tests | existing workflow guards updated | `test_attention_workflow_guard.py`, `test_ci_workflow.py` | sonnet | 3 / 5 | **Owner's explicit written approval of each `.github/` change BEFORE any text is written** | #162; O1 | no |
| 10 | **BT** backtest and noise-floor study of the T-class thresholds (D1 to D4, T8) | analysis report only (no scoring change) | n/a | n/a | sonnet | 4 / 6 | Owner | needs 30+ days of quality records and the Trends archive | later |

**Blocked by open PRs.** #162 (Trends fetch): slices 2, 4, 6, 9 and the Trends rows of the host profile. #161 (collector core) and the later collector slices W8c to W8f: the Reddit trickle and RSS unit and the X ceiling unit of slice 8. #166 changes only the checker and its tests and blocks nothing here. **Can start now:** 1, 3, 5, 7 (after the owner's provider probe).

## 8. Quality risks that no config can fix, and what to measure

| Risk | Why config cannot fix it | Measure |
|---|---|---|
| **Trends sampling noise and integer resolution** (values are 0 to 100 integers; Google samples requests, so the same request can return slightly different numbers; a quiet coin sits on a few integer levels) | The provider's resolution and sampling are fixed | Repeat-pull difference: the per-pull archive (#162) holds the same dates from successive pulls; record the daily absolute difference and how often the `rising` flag (>= 10 %) flips between two pulls of the same day, for 10 coins over 7 days. If the flip rate is high, the 10 % threshold is below the noise (class T, backtest). Also the share of coins with median below 3. |
| **X unofficial caps** (page loads, post budget, warning pages) | Set by X, not by us; the budget is a safety choice | Warning days per week, share of coin-days with `sample_cap` set, cost in posts per coin-day (the distribution that decides whether 800 posts cover 20 or 78 coins), canary failures. |
| **Reddit low volume** (about 12 posts and about 160 comments a day on r/CryptoCurrency, owner count) | There is little text to count | Per coin: posts and comments per day, share of coin-days below `reddit_sample_min`, share of zero days. Rule of thumb for the report: a count of n has a Poisson relative error of 1/sqrt(n), so seeing a 10 % change at about 2 sigma needs roughly 400 mentions in the window; most coins will have far fewer, so the source should carry a "thin" marker, not a score change. |
| **Wikipedia missing articles for about 45 coins** | No article exists | Structural coverage (usable / eligible) per day; the list of coins with no article; whether another-language article or a Wikidata-linked page exists (owner decision, not time). |
| Provider revisions after the first observation | First-write-wins freezes the first value | `revised_share` from the day +3 re-check (rule E3). |
| Home-IP limits | The IP is shared by every request from the host | Warning and refusal events per day and per source from the quality record; the #166 evidence (about 100 requests at 3 s) is the starting point. |

## 9. Owner decisions and approvals

- **O1.** One writer per source, and how server data reaches the repo that the web app reads (the server pushes the same commit step as the workflow, or the PC syncs). Until decided, both hosts must not write the same source.
- **O2.** The service manager on the PC and the laptop (Task Scheduler or cron), laptop sleep policy, and where `ATTENTION_HOST_PROFILE` is set.
- **O3.** Every `.github/` change (slice 9) needs the owner's explicit written approval first; this task wrote none.
- **O4.** X: daily read cap and post-budget ceiling stay as configured; raising either is an owner spend and account-risk decision, not a runner fix.
- **O5.** Whether to adopt exact Binance quote volume (mixes two definitions in one series).
- **O6.** Provider probes needed before slice 7: the real history limits of CoinGecko's public tier and the Binance bar limit.

## Acceptance Criteria

- **AC1** Every inventoried item has a `file:line` on `origin/main` 7229a80 or on a named PR head, a class (S, R, Q, T) and, for Q and R items, a concrete example and a server value. (Section 3, checked by the file-line citation check in the Validate Contract.)
- **AC2** The host profile design names the file, the selector variable and its default (`github`, no behaviour change), the keys that may differ, the keys that stay identical, the floor rule, the tick design and the tests with an injected clock. (Section 5.)
- **AC3** Quality metrics list every field asked for (coverage with reasons, completeness, sample size and cap flags, freshness, partial-day flags, retry and backoff counts, revised-value flags, one health state), where they are stored, how they stay point-in-time, and the panel text. (Section 6.)
- **AC4** Slices carry files, red-first test names, gates, model, USD, approval needs and blockers, in payoff order; `.github/` work is gated on explicit owner approval. (Section 7.)
- **AC5** The risks no config can fix are listed with what to measure. (Section 8.)
- **AC6** File set is exactly the plan and the report; `git diff --check`, secret scan and banned-name grep print nothing; the plan validator prints 0 failures.

## Implementation Checklist (phased delivery)

**Phase 1, now (owner ENTER EXECUTE per slice):** slice 1 (QS1), slice 3 (XS), slice 5 (HP1). **Phase 1b, owner probe:** O6, then slice 7 (HIST).
**Phase 2, after #162 merges:** slices 2 (QS2), 4 (HP4), 6 (HP2).
**Phase 3, decisions:** O1 and O2, then slice 8 (TICK) and, only with the owner's written approval, slice 9 (WF). Collector-dependent units of slice 8 wait for #161 and W8c to W8f.
**Phase 4, evidence:** run the server profile for 14 days, read the quality records, then slice 10 (BT) and the measurements of section 8.

## Touchpoints

`api/scripts/refresh_attention.py`, `api/data/attention/{quality,host_profile,xsearch,wikipedia,coingecko_attention,exchange_volume,store}.py`, `api/data/attention_host.json`, `api/analytics/attention/{sources,signal_snapshots}.py`, `api/models/discovery.py`, `web/components/narrative/DiscoverySourcesPanel.tsx`, new `api/scripts/attention_host_tick.py`; `.github/workflows/attention-refresh.yml` only in slice 9 with approval.

## Public Contracts

Unchanged by this task. For the slices: the `refresh_attention.py` CLI and exit codes stay; `ATTENTION_HOST_PROFILE` is new and optional; `DiscoverySourceRow` gains one optional `quality` field (existing clients ignore it); stored series formats are unchanged; the signal snapshot record gains an additive field.

## Blast Radius

This task: two new process files, nothing else. Slices: quality files are read only by the Sources panel; scoring output must stay byte-identical (tested). Profile `github` is the default, so the workflow behaves as today. The `server` profile only matters when the variable is set.

## Verification Evidence

Every cite was read on `origin/main` 7229a80 or on the PR head named in the row. The timing arithmetic uses the owner's measured 0.5 s latency (quoted in the T100b PLAN) and the code's constants. Not measured: any live provider behaviour (Google, Reddit, X, Wikimedia, CoinGecko history limits, Binance bar limit), hourly granularity of `now 7-d`, and the X post-cost distribution. These are marked UNVERIFIED where used.

## Resume and Execution Handoff

Handoff to the planner: choose the first envelope from section 7 (recommended: slice 1 QS1, then 3 XS and 5 HP1 in parallel branches that touch disjoint files). Slices 2, 4, 6 wait for #162. Slice 9 waits for the owner's written approval of the `.github/` text. The owner answers O1 to O6 when convenient; none blocks slices 1, 3, 5.

## Validate Contract

Status: PASS
Gate: PASS
Date: 2026-10-24
date: 2026-10-24
generated-by: outer-pvl
Code under test: this plan only (docs). Method: single worker, two layers read in one session: Layer 1 (infra, test coverage, breaking changes, security of the plan itself) and Layer 2 (every cite re-read on `origin/main` 7229a80 or the PR head named).

### Gates for this task (exact commands, repo root)

| Gate | Command | Pass criterion |
|---|---|---|
| G1 plan validator | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-quality-over-speed_PLAN_24-10-26.md` | 0 failures |
| G2 whitespace | `git diff --check origin/main...HEAD` | exit 0, prints nothing |
| G3 file set | `git diff --name-only origin/main...HEAD \| sort` | exactly the PLAN and the REPORT of this task |
| G4 no secrets | `git diff -U0 origin/main...HEAD \| grep -nE "Bearer [A-Za-z0-9._-]{12,}"` | prints nothing |
| G5 banned names | `git diff -U0 origin/main...HEAD \| grep -inE "x""scrape\|klo""xeld\|gun""konchi"` | prints nothing (the pattern is split so this file does not match itself) |
| G6 forbidden paths | `git diff --name-only origin/main...HEAD \| grep -E "^(\.github/\|api/data/trends_keywords.json\|api/\|web/)"` | prints nothing |

### Gates for the slices (baselines to be re-measured by each slice's own envelope on fresh main)

`UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/scripts api/tests/analytics/attention api/tests/tooling_guards -q` (0 failed; counts not below the baseline measured on the day), full API once by the tester, frozen signal-snapshot hash check for any slice touching `signal_snapshots.py`, web vitest for the panel in slice 1. Baseline numbers are not quoted here because the base moves with each merged PR.

### Hard stops (verbatim for the /goal block of any slice)

- Any change under `.github/` without the owner's written approval of that exact text: stop and report.
- Any change to `api/analytics/attention/discovery.py` scoring, `api/data/discovery.json` weights or thresholds, or `api/data/trends_keywords.json`: stop and report.
- Any `server` value lower than the matching `github` spacing, jitter, backoff, breaker or pause value: stop.
- Any test, tool or script that contacts a provider, prints a header, cookie, token or exception message: stop.
- A frozen snapshot hash differs: stop.
- Slice cost at its ask threshold: ask; never exceed the cap. Never merge any PR.

### Dimension findings

| Dimension | Status | Evidence |
|---|---|---|
| infra/setup-fit | PASS | all cited files and lines exist; PR heads fetched; dependency order (#162 before slices 2, 4, 6) stated |
| test-coverage | PASS | each slice lists named red tests; section 5 lists the clock-injected tests; live behaviour is a recorded known gap |
| breaking-changes | PASS | default profile `github` equals today; scoring byte-identity test; additive fields only |
| security-surface | PASS | quality records hold counts, reasons and timestamps only; reasons stay class and status only; no secret, header or cookie; profile file holds numbers |

### Findings of this validation

| # | Finding | Severity | Fix |
|---|---|---|---|
| F1 | Several brief items (540 s, pc_pace, density, collector block) are not on main | CONCERN | each row names its source (main, #162, #161, #166) |
| F2 | Running Wikipedia or CoinGecko earlier on a server would freeze unsettled values (first-write-wins) | CONCERN | rule E3: no earlier observation until revision is measured; re-check pass |
| F3 | Snapshot is frozen before slow sources arrive | CONCERN | slice 4 |
| F4 | "Server may lower spacing" would raise ban risk | CONCERN | floor rule E2 and loader rejection |
| F5 | X post-budget coverage claim depends on an unmeasured cost distribution | CONCERN | stated as 20 to 78 coins, measure first |

### Open gaps

None blocking. Known gaps: no live measurement (UNVERIFIED items above); thresholds of the health state are placeholders; owner decisions O1 to O6.

### What This Coverage Does NOT Prove

That Google, Reddit, X, Wikimedia, CoinGecko or Binance behave on a home IP as assumed; that 75 Trends requests spread over a day avoid the limit seen at about 100 requests in a burst; that the structural coverage of Reddit and X is enough for the 10 % threshold. The profile reduces burst volume and removes artificial cuts; it does not create signal where the provider has none.

### Accepted by

session (T164 worker, 24-10-26, docs only), on the planner's envelope. Not yet accepted by the owner: the profile design, the placeholder health thresholds, O1 to O6.

## Validation record (T164, 24-10-26)

Plan validator, diff checks and greps are recorded in the T164 report (heading 6).

**Next instruction for execution:** the planner sends the envelope for slice 1 (QS1) from section 7; no slice starts without its own envelope and the owner's ENTER EXECUTE MODE.
