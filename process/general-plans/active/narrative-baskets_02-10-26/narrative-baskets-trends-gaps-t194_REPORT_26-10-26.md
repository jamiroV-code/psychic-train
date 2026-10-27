## Owner summary (plain language)

- **Trends today:** 44 coins have a stored Trends series (the log said 42 ok; see 3 for the 2 extra). 27 more have a keyword but no series. 21 have no keyword at all (14 of those are stablecoins/funds that are excluded anyway; 5 are tickers PR #178 will fix; 2 are PYTH and JAAA with no entry).
- **The 6 "empty response" coins are NOT stored anywhere.** The per-coin reason is only counted, never saved. Best evidence: ENA, OKB, ETC, ZRO had good series yesterday and vanished today, so they are very likely 4 of the 6. The other 2 cannot be named from the repo.
- **Correction to the premise: some coins CAN trigger today.** The exchange slot (15) falls back to CoinGecko, so coins with Trends+Wikipedia reach covered weight 50 and Trends-only coins reach 40. On the stored snapshot (scored 26-10-26): **5 coins trigger on the 7-day window, 3 on 30, 1 on 90 (8 distinct)**. The early-source gate is the main filter, not the 30-weight floor. Reddit, X search, DefiLlama are not probed, so max covered is 50 of 85.
- **Wikipedia:** 63 no-article = 14 excluded + 6 mapped with a title that gives 404 + 43 unmapped/null. About 20 plausibly have an article; a one-off check_wiki_titles run is the fix.
- **Hyperliquid volume** has 9 days; the 90-day bar is reached about 2027-01-14. Binance needs non-US egress.
- **Timing:** Wikipedia is NOT the slow part (about 46 requests at 0.25 s). CoinGecko (6 s per call x 92) and universe/categories dominate. It does not matter yet (limit is 40 min).

## 1 Task ID
T194: read-only analysis of data gaps after the first real daily run (26-10-26). Worker, sonnet.

## 2 Outcome
done. Analysis only; no code, data or network. One docs file.

## 3 Summary: Trends per coin

Where things live: the daily run prints only counts (`trends detail: ...` in `refresh_attention.py _run_trends`). `store.py` keeps only `ok` series (`trends/<SYM>.parquet`, 100 days) and `trends_pulls/<date>.parquet` (ok series only). `probe_records.json` holds one line per source (trends: coins_ok 48 counts stale files within lag). **Failed coins' reasons (too-little-interest, quiet-then-surge, empty response) are not stored per coin anywhere.** The classes below for non-ok coins are therefore partly inferred.

Reconciliation: 92 coins = 71 keyworded + 21 no-keyword. Log: ok 42 + too-little 16 + surge 7 + failed 6 = 71. Stored pull of 26-10-26 holds 44 ok symbols: 2 more than the log (probably a second run the same day that added symbols; the archive keeps first write per symbol; not provable from the repo). So up to 2 of the "6 empty" may have been recovered by it and now sit in the ok table; 27 keyworded coins are non-ok in the store.

### 3.1 The 44 coins with a stored series (class ok; last-week/baseline = mean of last 7 days / mean of the earlier 93)

| coin | keyword kind | median | zero-day % | last-week/baseline |
|---|---|---|---|---|
| BTC | topic | 38 | 0 | 0.66 |
| ETH | topic | 37 | 0 | 0.5 |
| BNB | topic | 49.5 | 0 | 0.83 |
| XRP | topic | 36 | 0 | 0.66 |
| SOL | topic | 33 | 0 | 0.45 |
| TRX | term | 31.5 | 36 | 0.7 |
| ZEC | topic | 13 | 0 | 0.68 |
| HYPE | topic | 25 | 0 | 0.8 |
| DOGE | topic | 45 | 0 | 0.6 |
| XMR | topic | 31 | 0 | 0.74 |
| LINK | topic | 25 | 0 | 0.26 |
| ADA | topic | 37 | 0 | 0.51 |
| NEAR | topic | 32 | 0 | 0.67 |
| XLM | topic | 34.5 | 0 | 0.68 |
| BCH | topic | 28 | 0 | 0.53 |
| LTC | topic | 47.5 | 0 | 0.66 |
| UNI | topic | 26 | 0 | 0.3 |
| CC | term | 20.5 | 38 | 0.49 |
| AVAX | term | 17 | 28 | 0.2 |
| SUI | term | 26.5 | 2 | 0.14 |
| HBAR | topic | 21.5 | 0 | 0.29 |
| SHIB | topic | 39 | 0 | 0.38 |
| AAVE | topic | 36.5 | 0 | 0.44 |
| ONDO | term | 30 | 4 | 0.15 |
| PUMP | topic | 46 | 0 | 1.37 |
| PEPE | term | 25 | 0 | 0.76 |
| DOT | topic | 33 | 0 | 0.46 |
| WLFI | topic | 19.5 | 0 | 0.23 |
| WLD | topic | 31 | 0 | 0.57 |
| SKY | term | 20 | 7 | 0.12 |
| ICP | topic | 23 | 10 | 0.27 |
| HTX | topic | 48.5 | 0 | 1.01 |
| ARB | topic | 14.5 | 0 | 0.33 |
| JST | term | 27 | 1 | 0.44 |
| POL | term | 13 | 38 | 0.52 |
| ALGO | topic | 23.5 | 0 | 0.33 |
| JUP | term | 19 | 31 | 0.3 |
| RENDER | term | 33.5 | 15 | 0.12 |
| PI | topic | 30.5 | 0 | 0.57 |
| NEXO | topic | 49 | 16 | 0.89 |
| INJ | topic | 13 | 3 | 0.27 |
| FIL | topic | 24 | 0 | 0.4 |
| CAKE | topic | 23 | 0 | 0.37 |
| XDC | topic | 37 | 10 | 0.56 |

### 3.2 The 27 keyworded coins without a series (class: too-little-interest / quiet-then-surge / empty response, per-coin class NOT stored)

| coin | keyword | stored evidence |
|---|---|---|
| WBT | WhiteBIT Coin | not stored (no series) |
| LEO | unus sed leo crypto | not stored (no series) |
| XAUT | topic | not stored (no series) |
| QNT | quant crypto | not stored (no series) |
| TAO | topic | not stored (no series) |
| ENA | ethena crypto | yesterday ok: median 22, 0% zero, ratio 0.25 |
| CRO | cronos crypto | not stored (no series) |
| OKB | okb token | yesterday ok: median 65, 1% zero, ratio 0.93 |
| M | memecore crypto | not stored (no series) |
| PAXG | pax gold crypto | not stored (no series) |
| ASTER | aster crypto | not stored (no series) |
| MNT | mantle crypto | not stored (no series) |
| MORPHO | morpho crypto | not stored (no series) |
| BGB | topic | not stored (no series) |
| VVV | topic | not stored (no series) |
| ETC | ethereum classic crypto | yesterday ok: median 18.5, 10% zero, ratio 0.23 |
| KCS | topic | not stored (no series) |
| GT | topic | not stored (no series) |
| KAS | topic | not stored (no series) |
| ATOM | cosmos crypto | not stored (no series) |
| ZRO | layerzero crypto | yesterday ok: median 20, 4% zero, ratio 0.21 |
| DASH | dash crypto | not stored (no series) |
| PEARL | pearl crypto | not stored (no series) |
| NIGHT | midnight crypto | not stored (no series) |
| ETHFI | ether fi crypto | not stored (no series) |
| APT | aptos crypto | not stored (no series) |
| BDX | beldex crypto | not stored (no series) |

Counts to match: 16 too-little + 7 surge + 6 empty = 29 in the log run; 27 now (2 recovered, see above). ENA, OKB, ETC, ZRO have a series with last row 24-10 (kept, within the 3-day lag, so Discovery still reads them) and were in the 25-10 pull: their medians (22, 65, 18.5, 20) rule out too-little-interest. Surge is implausible for a coin that was mid-range yesterday. **They are the best candidates for `empty response`** (4 of 6). The other 23 never had a series in any stored pull; no way to tell which 2 are empty.

Hypotheses for empty responses (all untested, no network): (a) Google returns an empty frame for a transient/throttled request that is not a 429 (ENA, ETC, ZRO, OKB are all plain `term` keywords: 'ethena crypto', 'ethereum classic crypto', 'layerzero crypto', 'okb token'); (b) a rare multi-word term below Google's anonymity threshold returns an empty frame on some days and data on others; (c) an invalid topic id returns empty (the 7 unsolved topic coins: XAUT, TAO, BGB, VVV, KCS, GT, KAS; but 6 of them are checker PASS, so least likely). Check: the 25-10 vs 26-10 diff above shows the same coin with data one day and empty the next, favouring (a)/(b).

**Smallest change to store per-coin reasons (NOT implemented):** in `_run_trends` after `series` is built, write one small `api/data/cache/attention/trends_last_run.json` (symbol -> outcome string from `_trends_outcome`, plus median/zero%/ratio for too-little and surge) and commit it with the cache. About 15 lines plus 1 test, no schema change. Alternative: print one line per non-ok coin in the log (`trends coin: ENA empty response`): 5 lines, but not committed.

### 3.3 The 21 no-keyword coins

| coin | status | Discovery-eligible? | note |
|---|---|---|---|
| AKE, BTW, GRAM, LIT, RAIN | no-keyword (unidentified allowlist) | yes | named by owner in PR #178 (draft, not in main) |
| PYTH | no-entry | yes | no entry in the keyword file (not in PR #178 list); needs a term |
| JAAA | no-entry | yes (config gap) | tokenized fund 'janus-henderson-anemoy-aaa-clo-fund' is missing from `tokenized_fund` class in discovery.json; likely should be excluded |
| FIGR_HELOC, BUIDL, USYC, USDY, USTB, EURSAFO | no-entry | no: tokenized_fund | |
| USDG, RLUSD, USDF, U, BFUSD, USDGO, OUSD, GHO | no-entry | no: stablecoin | |

PR #178 keys 9 entries (AKE, BTW, GRAM, LIT, RAIN, PRL, STABLE; replaces PEARL and OKB terms). Only AKE, BTW, GRAM, LIT, RAIN are in today's 92; PRL and STABLE are not in the snapshot. Note OKB's term in PR #178 changes ('okb token' -> 'okb crypto'), relevant to the empty-response hypothesis.

## 4 Files changed
Only this report.

## 5 Commits
Branch `claude/t194-trends-gaps-analysis`, one commit (SHA in the PR).

## 6 Tests run
No test suite (read-only analysis). Python snippets under `uv run --project api python -I` read parquet/json and called `discovery._coin` / `registry.read_series` with `today=2026-10-26`. They are in the session scratchpad, not the repo. `git status` clean apart from this file.

## 7 Tests NOT run
Anything with network. Per-coin claims about Wikipedia articles (section 8.2) are from names only, not verified.

## 8 Answers to the questions

### 8.1 Trends + Wikipedia and covered weight (question 2)

- Eligible Discovery coins in the snapshot: 78. Trends readable: 48 (44 fresh + 4 stale-within-lag). Wikipedia readable: 29. **Trends AND Wikipedia: 27.**
- Group scoring (code, `discovery._rising_weight`): `search` = trends + wikipedia votes ONCE: it is rising if its rising members hold at least half of the group's available weight; then it adds the whole group weight (35) to the rising weight. Covered weight and the score still count each source.
- Probed and usable sources today: trends 25, wikipedia 10, coingecko 15 (fallback for `exchange_activity` because exchange_volume is not-probed, Hyperliquid is insufficient-history (registry needs 90 days), coinbase/kraken have no fetcher). Reddit, xsearch, defillama, github_dev: not-probed.
- Covered weight distribution (all 3 windows identical): 50 = 27 coins (trends+wiki+cg); 40 = 21 (trends+cg); 25 = 2 (wiki+cg); 15 = 27 (cg only); none = 1. **48 coins reach min_covered_weight 30** (50 or 40).
- Trigger rule: rising >= 60% of covered, covered >= 30, AND one early source (trends/reddit/xsearch) rising (>=10%). Because the exchange slot silently becomes CoinGecko, **coins CAN trigger today:**

| window | triggers | coins (trends/wiki/coingecko change %) |
|---|---|---|
| 7d | 5 | ZEC (42/40/-7), XMR (19/36/68), PUMP (31/-/-5), PEPE (39/-6/66), HTX (38/-/-5) |
| 30d | 3 | TRX (44/-8/-16), HTX (12/-/33), NEXO (38/-/-27) |
| 90d | 1 | PUMP (35/-/-14) |

Gate funnel: early (Trends) rising >=10%: 5 / 3 / 1 coins; rising weight >=60% of covered: 15 / 7 / 5 coins. So the early-source gate is what limits triggers (most coins have Trends falling; last-week/baseline is below 1 for almost all), not the weight floor. Why the envelope's premise ("none can") fails: it assumed no exchange_activity; the CoinGecko fallback supplies 15. Note the 4 stale coins (ENA, OKB, ETC, ZRO) are scored from a 24-10 series; ENA/ZRO are falling.

### 8.2 Wikipedia no-article (question 3)

63 = 14 excluded (stablecoin/fund) + 49 eligible. By cause in `wiki_articles.json`: **6 mapped but 404** (LEO `UNUS_SED_LEO`, NEAR `Near_Protocol`, CRO `Cronos_(blockchain)`, AAVE `Aave_(blockchain_platform)`, ICP `Internet_Computer`, ATOM `Cosmos_(blockchain)`: titles wrong, never had a file); **explicit null (count not verified)** (owner/earlier check said none): HYPE, SUI, XAUT, QNT, TAO, ENA, OKB, ONDO, PAXG, MNT, MORPHO, BGB, ARB, JUP, RENDER, ZRO, XDC, APT, PYTH and others; **rest not in the map**.

Classification from names only (UNVERIFIED, no web):

| class | coins |
|---|---|
| likely has article (needs title mapping or fix) | NEAR, LEO, CRO, AAVE, ICP, ATOM (fix the 6 titles); SUI, APT, ARB, TAO, RENDER, QNT (already in `wiki_articles_candidates.json`, unchecked); WLFI, PI, NEXO, PAXG, ONDO, HYPE, JUP, ENA (plausible) |
| unlikely (too new/small/unnamed) | WBT, RAIN, CC, M, BTW, PUMP, ASTER, SKY, HTX, MORPHO, BGB, VVV, JST, KCS, GT, LIT, AKE, ZRO, XDC, PEARL, NIGHT, ETHFI, BDX, MNT, OKB, XAUT, PYTH, GRAM, JAAA |
| excluded anyway | FIGR_HELOC, USDG, RLUSD, USYC, USDY, BUIDL, USDF, EURSAFO, U, BFUSD, USDGO, OUSD, USTB, GHO |

How titles get found: `api/scripts/check_wiki_titles.py` reads a symbol -> title JSON (default `wiki_articles_candidates.json`), calls the Wikipedia REST summary endpoint at 1 req/s, prints PASS/FAIL per coin (needs a crypto word in the extract) and paste-ready JSON; it writes nothing. Data task: owner (or a networked session) runs it on ~20 candidates (the 6 fixed titles + the 6 in candidates + ~8 plausible), pastes PASS entries into `wiki_articles.json`. About 1 hour of owner time, near 0 USD.

### 8.3 Hyperliquid and Binance (question 4)

- Stored `hyperliquid_volume`: 82 files; 73 start 17-10-26, 9 start 20-10-26. 54 have last day 25-10 with 9 days (17-10..25-10, consecutive); 25 stopped at 19-10 (3 days, symbol later not listed); 3 odd. The run log's "1 day" is the single day fetched, not what is stored. `probe_records.json`: hyperliquid max_days 9, state insufficient-history.
- The registry hard-codes `MIN_HISTORY_DAYS = 90` (types.py); `min_history_days: 30` in discovery.json is not what gates this source. 90 days reached on **2027-01-14** for the 17-10 starters if no day is missed (later for gaps: a missed daily run adds a day).
- Non-US egress needed: Binance (`exchange_volume`, HTTP 451 from US runners; code even labels it expected). Also likely Coinbase and Kraken fetchers when built. Hyperliquid, Wikipedia, CoinGecko, Trends worked from the runner (Trends is 429-prone from cloud IPs). Fix options: self-hosted/non-US runner, proxy, or a different exchange source.

### 8.4 Timing (question 5)

Constants: Wikipedia pacing 0.25 s/request and only coins with a mapped, non-null title are requested (about 46) = under 1 min. CoinGecko `MIN_INTERVAL_SECONDS` 6 s, 92 per-coin calls = about 9-10 min plus 5-90 s retry waits; categories (10 calls at 6 s + 2 s pause) = about 1.5-2 min; universe 1-2 calls; signals snapshot is CPU. Trends step: 71 requests at 3-5 s = about 4-6 min (budget 540 s, step timeout 14 min). No per-step times are in the repo, so these are estimates: **CoinGecko dominates, Wikipedia does not.** It does not matter: the job limit is 40 min and the run is daily at 07:23 UTC; headroom is about 12 min. It would matter if Reddit/xsearch/GitHub are added (xsearch alone is paced in minutes by design) or if more coins get Trends terms (3-5 s each).

## 9 Blockers
None. Limits: failed-coin classes and the 2 unaccounted ok coins are not recoverable from the repo; the Actions run logs were not read.

## 10 Follow-up tasks (priority order)

| # | task | owner decision? | est USD | model |
|---|---|---|---|---|
| 1 | Store per-coin Trends outcome (trends_last_run.json, ~15 lines + test) | no | 1 | sonnet |
| 2 | Owner runs check_wiki_titles on ~20 candidates, then data task pastes PASS titles | yes: owner runs the tool (needs network) | 1 | sonnet |
| 3 | Merge PR #178 (9 keywords) and owner probe of the new terms | yes | 0.5 | sonnet |
| 4 | Retry-once for `empty response` in `_trends_fetch` (same coin, after 10 s) if task 1 shows the 4 coins repeat | yes (policy) | 1.5 | sonnet |
| 5 | Add JAAA to `tokenized_fund`; decide PYTH term (or exclude) | yes | 0.5 | sonnet |
| 6 | Decide whether CoinGecko-as-exchange fallback should count toward trigger today (it enables the 8 triggers; arguably volume is not "exchange activity") | yes: product call | 0 | n/a |
| 7 | Binance non-US egress (runner/proxy) | yes: spend | 3 | opus |
| 8 | Re-run this analysis after 7 days of Trends pulls (stability of which coins are empty) | no | 2 | sonnet |
| 9 | Add Reddit/xsearch to the daily run so early-source gate has more than Trends | yes: spend + keys | 5+ | sonnet |

## 11 Context cost
Loaded CLAUDE.md, the envelope, store.py, trends.py (incl. fetch_alone), refresh_attention.py (excerpts), discovery.py (excerpts), registry.py/exchange_volume.py/types.py/wikipedia.py/coingecko_attention.py (grep excerpts), discovery.json, probe_records.json, keyword and wiki JSON, attention-refresh.yml (excerpt), PR #178 diff (read once, large). No operating-instructions.md. About 120k tokens, well under 3 USD.
