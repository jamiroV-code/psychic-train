---
name: spec:narrative-baskets-xreddit-collector
description: "T126: collect X and Reddit attention on the owner's PC without the official X or Reddit APIs, via API Anything, as two pc_side sources (xsearch, reddit) of the weighted signal. Docs only; no approach built, nothing run."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

Status: ready for owner review (amended T131, 21-10-26). The owner has not approved this SPEC. T131 amended it with the owner's pacing decisions and answers (Locked pacing rules, Q2/Q3/Q4/Q7 answered, AC1/AC8/AC10 reworded, AC19-AC20 added, Annex C/D/F/H updated).

# Narrative Baskets: X and Reddit collector on the PC, no official APIs (T126, 21-10-26)

Builds on the weighted-signal SPEC (T98, W8 `fetch_side`) and T96 (`max_source_lag_days`). "Attention" means mentions, never price. Code was read on `main` at 007d53c. Everything about API Anything, X, Reddit and the owner's PC is UNVERIFIED: no provider is reachable from the sandbox and nothing from API Anything was read or run.

## Summary

Two Discovery inputs, X search (weight 10) and Reddit (weight 15), have no data today because the official APIs cost money (X) or await approval (Reddit). This SPEC defines how the owner's own PC fills them anyway: while the API runs on the PC, a hidden background worker reads the public X and Reddit sites the way a browser does, using the tool API Anything, and stores one number per coin per day in the existing daily store. On days the PC is off the source is simply missing for those days (never 0, never estimated). After a one-time login of a dedicated X account the owner does nothing. GitHub dev activity is parked.

## User Stories / Jobs To Be Done

- US1. As the owner, I want X and Reddit attention in the weighted signal without paying for X's API, so that two of the seven sources stop being dead weight.
- US2. As the owner, I want it fully automatic after one login, so that it costs me zero daily work.
- US3. As the owner, I want days the PC was off to show as "no data" and be filled in when the PC returns, so that I never see a fake zero or a fake drop.
- US4. As the owner, I want a clear reason on the Sources row when X or Reddit stops (login expired, account suspended, site layout changed, rate limited), so that I know whether to act.
- US5. As the owner, I want yesterday's value frozen once stored and the history usable for backtests, so that a chart for day D never changes later.
- US6. As the owner, I want a dependency I can trust, so that nothing from an unreviewed or malicious package ever runs on my PC.
- US7. As the owner, I want to swap Reddit to the official API later without corrupting the series, so that approval arriving does not break history.

## What The User Wants (Behavioral Outcomes)

- The Sources page shows `xsearch` and `reddit` as `ok` with newest day within the lag limit, after the PC has run the API for a day.
- Starting the API after days off triggers a quiet catch-up; the Narrative tabs show the existing "updating data" state meanwhile.
- When X login expires or the account is suspended, the X row says so in plain words and the worker stops touching X until the owner acts; other sources are unaffected.
- No window appears on the PC at any time after the one-time login.
- Coins whose names are ambiguous (e.g. a ticker that is also a common word) show as missing for that source, not as noisy numbers.

## Flow / State Diagram

```
API starts on PC --> [flag SCREENER_ATTENTION_PC_WORKER on?] --no--> (worker idle)
        |yes
        v
[per pc_side source: newest stored day < last completed UTC day?] --no--> sleep until next tick
        |yes (behind)
        v
[health gate: login ok? breaker open? canary query returns data?]
   |fail --> state failed(reason), stop this source, retry later / wait for owner
   |ok
   v
[per coin, oldest missing day -> newest: collect -> validate -> density formula]
   |HTTP 429 / page error --> back off, abort pass, coins not done stay missing
   |ok --> write frozen day (first write wins) + evidence row
   v
[Sources row: ok / insufficient-history / failed(reason)]
```

PC off: no pass runs, those days stay missing; next start catches up inside the backfill limits (Annex C).

## Locked pacing rules (owner decisions, T131, 21-10-26)

1. **Slow trickle.** X collects ONE coin unit every 10-20 minutes (random, uniform), spread over the whole UTC day. A unit is one coin for one day: at most P page loads, spaced 5-15 s apart inside the unit. A full pass over the narrative coins takes many hours (75 coins at a 15 min mean is about 19 h). No bursts; the worker never speeds up to catch up, after a restart, after a pause or after days off. Hard cap: 100 X units per UTC day. Reddit is gentler than the first numbers: one request every 20-60 s (random), at most 300 requests per UTC day (was 400 per pass), one stream at a time.
2. **Yesterday-only.** A day's value is collected only after that UTC day is complete and is shown one day late (one day gap accepted by the owner; trend detection works over days). Today's partial day is never stored and never shown. Forward work (yesterday, all coins) always has priority; backfill days use only the units left over.
3. **Pause on warning.** Any rate-limit, login or suspension warning pauses that source for the rest of that UTC day, with no retries and no growing backoff. The pause is persisted, so restarting the API does not lift it. Suspension and login-expired stay paused beyond the day until the owner acts (new account, re-login).
4. **Scope and spend.** Coin set first is narrative coins only; backfill is short; build order is Reddit first, X later after the owner probes; self-repair LLM spend is capped at 15 USD per month; both Reddit series (web and the future official one) stay separate, config picks, never spliced. See Open Questions (answered).
5. **Honest limit.** A slow pace lowers request volume; it does not remove ban risk (Annex F). No detection-evasion technique is part of this SPEC or any slice: no fingerprint spoofing, no proxy rotation, no extra or fake accounts.

## Acceptance Criteria (Testable Outcomes)

All tests use fakes and an injected clock; live behaviour is proven only by owner probes (Annex G).

- AC1. X density formula and yesterday-only: for a completed UTC day with k tweets collected, N target, oldest tweet time t_old: if the window start is reached with k < N the value is k (exact); if k hits N first the value is 24 * N / span_hours with span = window end minus t_old, floored at 0.25 h; with the page cap hit and N_min <= k < N the same formula uses k; below N_min the day is missing. A value is stored only when the injected clock is at or after the window end (00:00 UTC of D+1); a request for today's date stores nothing and the Sources `newest` never equals today.
  proven by: density-formula table test (exact, capped, floor, below-min, boundary k = N); no-same-day-value test with injected clock at 23:59 and 00:00
  strategy: Fully-Automated
- AC2. Reddit uses the same formula over posts in the window (Annex A.2); a day is exact only when the walk reached the window start.
  proven by: reddit-walk-back fake-listing test
  strategy: Fully-Automated
- AC3. Missing is never 0: a failed, rate-limited, login-expired or partial collection stores nothing for that coin-day. A zero count is stored only when the same pass's canary query returned data and the coin's trailing median is below 5; otherwise the coin-day is failed.
  proven by: no-zero-on-failure test; canary-gated-zero test
  strategy: Fully-Automated
- AC4. Frozen: a second collection for a stored day does not change it; only completed UTC days are stored; each value has an evidence row (n, span_hours, capped, method, collected_at, backfilled).
  proven by: first-write-wins and evidence-row tests (existing store semantics)
  strategy: Fully-Automated
- AC5. Point-in-time: day D scored from points dated <= D is identical on a store truncated after D (W11 rule); backfilled days are flagged and can be excluded from a "known at the time" backtest.
  proven by: truncate-and-recompute test with a backfilled-flag case
  strategy: Fully-Automated
- AC6. T96: a source whose newest day is older than `max_source_lag_days` drops out of that coin's covered weight and weights rescale; PC-off gaps give thin `covered_weight`, not zeros.
  proven by: pc-off-gap rescale test using the existing discovery scoring tests
  strategy: Fully-Automated
- AC7. `fetch_side` per source loads from config (`github` or `pc_side`), rejects unknown values, and a source is fetched by exactly one side; the GitHub job and the worker each skip the other's sources.
  proven by: config validation test; side-skip test
  strategy: Fully-Automated
- AC8. Trickle and catch-up: with an injected clock and a seeded random source, X units are spaced 10-20 min apart and Reddit requests 20-60 s apart; X never exceeds 100 units and Reddit 300 requests per UTC day; a worker started after days off is scheduled ~20 s later (T51 `_behind` pattern) but its pace is identical (no burst, no speed-up), and the daily caps hold on catch-up; units spread across the day rather than front-loaded; yesterday units run before backfill units; passes never overlap (lock); the flag off means no thread.
  proven by: injected-clock trickle-spacing test; daily-cap test; catch-up-same-pace test; priority-order test (mirrors the equities worker tests)
  strategy: Fully-Automated
- AC9. Failure handling per Annex E: login expired, suspension, layout change after failed self-repair, rate limit each set a distinct reason on the Sources row, stop only the affected source, never write values, and never crash the API.
  proven by: four fake-transport failure tests plus a Sources-row note test
  strategy: Fully-Automated
- AC10. Pause on warning: any HTTP 429, rate page, login prompt or suspension signal stops that source at once; no retry is sent; no further request to that source is made until 00:00 UTC of the next day (suspension and login-expired: until the owner acts); the pause survives a worker or API restart; other sources keep running.
  proven by: pause-rest-of-day test (fake 429 at 10:00, no request until next-day 00:00); pause-persists-over-restart test; no-retry test (request count stays 1)
  strategy: Fully-Automated
- AC11. Logging: every collector log line contains only the exception class name and the HTTP status; a test greps captured logs for a planted cookie, header value, URL query and exception message and finds none.
  proven by: log-scrub test with planted secrets
  strategy: Fully-Automated
- AC12. No secrets in files: cookies, profile and tokens live in an owner profile folder outside the repo (git-ignored path check) and are never printed, committed or put in env files in the repo.
  proven by: repo-scan test for the profile path ignore rule; secret-pattern grep over new files
  strategy: Fully-Automated
- AC13. The worker never starts under tests or on GitHub runners (flag default off; tests assert no network).
  proven by: flag-default test; no-network guard
  strategy: Fully-Automated
- AC14. Method separation: `xsearch_web` and `reddit_web` series are stored apart from any future `reddit_api` series; Discovery reads one per source via config and never splices two methods in one series.
  proven by: method-config test with two stores
  strategy: Fully-Automated
- AC15. Ambiguous-coin list: coins in the owner-editable ambiguity list are never collected for that source and show as missing.
  proven by: ambiguity-list test
  strategy: Fully-Automated
- AC16. Dependency vetting is recorded before use: pinned commit SHA, reviewed code paths, no install scripts, hash-pinned install; a guard test fails if the dependency is unpinned or the banned names (xscrape, kloxeld, gunkonchi) appear anywhere in requirements or code.
  proven by: dependency-pin guard test; banned-name grep test
  strategy: Fully-Automated
- AC17. Live behaviour (login, hidden run, X search depth, caps, real rate limits, Reddit endpoint shape) is proven by owner probes P-X1.., P-R1.. with pasted output; the build is not "done" for live purposes before those pass.
  proven by: owner probe output recorded in the slice report
  strategy: Agent-Probe (justified: providers unreachable from the sandbox and need the owner's login)
- AC18. Zero daily owner work: after the one-time login there is no prompt, window or manual command in normal operation, and the owner sees only status text on the Sources row.
  proven by: worker end-to-end test with fake transport (no input needed); owner probe P-X7 after 3 days
  strategy: Hybrid

- AC19. Self-repair spend cap: a fake cost meter proves self-repair is refused once 15 USD is spent in the calendar month (UTC), restarts at the next month, and a refused repair leaves the source `layout_changed` with no value written.
  proven by: monthly-cap test with injected clock and fake meter
  strategy: Fully-Automated
- AC20. Narrative-coins scope: the collected coin set equals the narrative coins (the placed symbols of the narratives file) minus the ambiguity list; widening needs a config change, not code.
  proven by: coin-set-from-narratives test
  strategy: Fully-Automated

## Out Of Scope

- GitHub dev activity (parked), DefiLlama, Trends, exchange sources.
- Official X and GitHub APIs; the official Reddit API (pending separately; only the method-swap rule is specified).
- Building or running anything, installing API Anything, `.github/` changes, any web UI beyond the existing Sources status text and "updating data" state.
- Sentiment, comment counts, impressions, likes, influencer weighting.
- Using the owner's main X account, buying proxies or accounts, and any detection-evasion technique (fingerprint spoofing, proxy rotation, extra or fake accounts).
- Same-day (partial-day) values, speeding up to catch up.
- Changing source weights or the trigger rule.

## Constraints

- Owner-locked: API Anything; runs on the owner's PC hidden, inside the API as a worker like the equities refresh worker; dedicated separate X account, ban risk accepted; no official X or GitHub API; cookies cannot be imported on Windows, login happens once in API Anything's own window.
- Output must plug into the source model: daily series per symbol, state ok / insufficient-history / failed, missing never 0, frozen days, point-in-time, T96.
- Safety: the `xscrape` library (also `kloxeld`, `gunkonchi`) is malware and is never used, installed or referenced as a dependency. Any dependency is pinned and reviewed first.
- Logging: exception class and HTTP status only.
- Fits existing code: store keeps only completed UTC days, first write wins (`api/data/attention/store.py`); Sources status is read-only from files (`api/analytics/attention/sources.py`); worker pattern is `api/data/equities_refresh.py` (daemon thread, `PASS_LOCK`, `_behind`, env flag).
- Existing `xsearch` code is an official-API path gated by `X_LIVE` and a bearer token; the new path must not require either.

## Open Questions

| # | Question | Owner | Needed by |
|---|---|---|---|
| Q1 | OPEN (X comes later): dedicated X account: who creates it, with what email/phone, and is a phone number required for login (affects hidden re-login)? | owner | W8d |
| Q2 | ANSWERED (owner): short backfill: X up to 14 days if search honours day windows, Reddit as far as its listing reaches; both only from leftover units (Locked pacing rules). | owner | closed |
| Q3 | ANSWERED (owner): narrative coins only first; widening later by config. | owner | closed |
| Q4 | ANSWERED (owner): self-repair LLM spend cap 15 USD per month. Whether it calls a paid LLM at all stays UNVERIFIED (probe P-X2). | owner | closed |
| Q5 | Is the API process already hidden on the PC (no console window), or does the worker's browser need extra hiding? | owner (probe P-X4) | W8e |
| Q6 | SUPERSEDED by the Locked pacing rules (trickle spread over the day, yesterday-only). | planner | closed |
| Q7 | ANSWERED (owner): keep BOTH series separate, config picks, never spliced. | owner | closed |
| Q8 | Reddit subreddit list in Annex A.2: edit before build? | owner | W8c |
| Q9 | Relation to W8 (generic PC worker, T98 SPEC): checked 21-10-26, the generic W8 worker does NOT exist on `main` (no `attention_pc_refresh` module, no `SCREENER_ATTENTION_PC_WORKER` in code). The PLAN plugs these slices into the T98 W8 design and builds the minimal worker shell inside W8e; if the planner dispatches W8 first, W8e only adds the sources. | planner | PLAN |

## Background / Research Findings

- Weights: `xsearch` 10 and `reddit` 15 in `api/data/discovery.json`; `min_history_days` is 30 there today. Rule: a source with no usable value drops out and weights rescale; missing is never 0 (T98 decisions 2, 3, AC-W3).
- `fetch_side` (github|pc_side) and the in-API worker design are in T98 section W8; forward-only sources cannot catch up (Reddit's official search is forward-only); this SPEC adds a way to walk backwards by listing order, see Annex C.
- `xsearch.py` today: official counts endpoint, dry run unless `X_LIVE=1`, stores one daily row, logs exception type only. `reddit.py` today: OAuth, needs `REDDIT_CLIENT_ID/SECRET`, one point per run. Both stay as they are; the new methods write to separate stores (AC14).
- Store: `write_series` only keeps `date < today`, first write wins; `registry.read_series` needs `MIN_HISTORY_DAYS` (90) for `ok`; point-in-time uses the config gate (T98 AC-W13).
- Sources status already has states `ok`, `unavailable`, `insufficient-history`, `off`, `not-probed`; there is no `failed`. Mapping: insufficient = `insufficient-history`; failed = `unavailable` with a reason code in `note` (or a new `failed` state, open for W8f).
- Equities worker: `_behind(session, now)` and `schedule_first` give the catch-up 20 s after start (T51); daemon thread, one pass at a time.
- Owner description of API Anything (not verified by reading its code): learns a site's internal requests and replays them over HTTP; tier 1 plain fetch, tier 2 in-page fetch, tier 3 full page run; self-repair when a site changes; X likely needs tier 3.

## Annex A: Metric definitions

### A.1 X: tweet rate per coin per day (`xsearch_web`)

Query form (per coin, from an owner-editable query file; cashtag first): `("$SOL" OR "Solana") lang:en -filter:replies -filter:retweets`, plus the window as `since_time:<unix start> until_time:<unix end>` for the UTC day (operator names UNVERIFIED; probe P-X5). Ambiguous tickers use the cashtag only or are listed as ambiguous (missing).

Collection (Latest/live ordering, newest first): start at window end, read results until N unique tweets are counted or the window start is passed or the page cap P is hit. Unique means identical text dropped and at most 3 tweets per author counted (bot/spam damping).

Constants (config, owner-editable): N = 100, N_min = 30, P = 8 pages/scroll steps, span floor 0.25 h, canary query `bitcoin`.

Value for day D (tweets per day):
- window start reached with k < N: value = k (exact count), capped = false.
- k reaches N first: value = 24 * N / span_hours, span_hours = (window end - oldest counted tweet time) in hours, floor 0.25; capped = true.
- page cap hit with N_min <= k < N: same as capped with N replaced by k; flag `pagecap`.
- k < N_min and window not exhausted: the coin-day is missing.

Properties: continuous at k = N (a 24 h span gives about N); the capped estimate reads the end of the UTC day, so its time-of-day bias is the same every day and cancels in the window-over-window change Discovery uses; relative noise about 10% at N = 100 if tweets were Poisson, more when bursty. Cap and rate-limit rules: Annex E. Spam spike: reuse the existing `SPAM_SPIKE_RATIO` (10): a day above 10x the trailing median is stored but flagged `spike` for the owner, not dropped.

### A.2 Reddit: posts mentioning the coin per day (`reddit_web`)

Primary: one multi-subreddit search per coin through the site's own search request (public listing, `sort=new`, `restrict_sr=1` over a `+` joined subreddit set; UNVERIFIED, probe P-R1/P-R4). Count posts (not comments) with `created_utc` inside the UTC day. Query text from the same owner file as X: ticker and name in quotes, title and body.

Proposed subreddit set (owner edits, Q8; activity UNVERIFIED): CryptoCurrency, CryptoMarkets, altcoin, CryptoMoonShots, SatoshiStreetBets, defi, CryptoTechnology, ethtrader, ethereum, solana, Bitcoin, binance. Coin-own subreddits (e.g. r/solana) are a later add-on per coin.

Walk: read listing pages (up to 100 items per page, cursor) newest first until items are older than the earliest wanted day start or the listing ends (about 1000 items per query, UNVERIFIED). Per day: window start reached means exact count; otherwise, if at least M_min = 50 items fall inside the window, use the A.1 formula with the same N semantics (N = 300, estimate over the covered span, flag `capped`); else missing.

### A.3 Shared rules

Daily value positive or zero only under AC3; never negative. Units differ (tweets/day vs posts/day) and that is fine: Discovery uses the percent change per source. Query or mapping change = new method version recorded in the evidence rows; a change in query form starts a new series (never splice).

## Annex B: Data flow and storage

```
worker tick -> health gate -> API Anything adapter (transport) -> parser/validator
   -> density formula -> store.write_series (first wins) + evidence row -> Sources status reads files
```

- Series: `attention/xsearch_web/<SYMBOL>.parquet`, `attention/reddit_web/<SYMBOL>.parquet` (date, value), same schema as other sources. Discovery reads them under the weighted ids `xsearch` and `reddit` through a config map `source_impl` (e.g. `reddit: reddit_web | reddit_api`, `xsearch: xsearch_web`). Never both in one series (AC14).
- Evidence sidecar per source and symbol (date, n, span_hours, capped flag, pagecap, spike, method version, collected_at, backfilled) for audit and the point-in-time rule; frozen with the value.
- Owner files outside the repo: API Anything profile/cookies folder (git-ignored path, never read by repo code except through the adapter).
- Repo config: `fetch_side` and `source_impl` in `api/data/discovery.json`; query/ambiguity/subreddit lists in a new JSON file; none holds secrets.
- Point-in-time: a value is "known at D+1" only if `collected_at` is within a day of D; backfilled values carry `backfilled = true` and a backtest may exclude them.

## Annex C: Scheduling, catch-up, backfill (amended T131, follows Locked pacing rules)

- Worker: a third worker next to the OHLCV and equities workers (T98 W8: `api/data/attention_pc_refresh.py`, flag `SCREENER_ATTENTION_PC_WORKER`, off in tests), daemon thread, `PASS_LOCK`, silent logging. The generic W8 worker does not exist on `main` yet (Q9).
- Work queue per source: items are (coin, completed UTC day). Order: yesterday for every narrative coin first; then older missing days inside the backfill window, newest first. Nothing for today is ever queued.
- X pace: one unit every 10-20 min (uniform random), at most 100 units per UTC day, page loads inside a unit spaced 5-15 s. Reddit pace: one request every 20-60 s, at most 300 per UTC day. Same pace after a restart or after days off; a catch-up never raises the rate.
- Capacity check (arithmetic, not measured): 75 narrative coins at a 15 min mean is about 19 h of X per day, so yesterday's pass fits in one day with about 21 units of 96 left for backfill; X backfill of 14 days x 75 coins (1050 units) would take about 50 days. So X history accrues mainly by forward days; the 30-day `min_history_days` gate is reached by forward collection in about 30 days anyway. Reddit: about 75 x 3 = 225 forward requests, about 2.5 h at a 40 s mean, leaving about 75 requests of the 300 for backfill; walk-back reuses the same listing pages.
- Start: `_behind` per source (newest stored day < yesterday) schedules the first unit about 20 s after start, then the trickle. Reddit passes should start after 00:10 UTC so the listing walk-back prefix (posts since the day's end) stays short.
- Hidden: login once in API Anything's own window (owner command); afterwards no visible window (headless, else off-screen/minimised; P-X4). If X refuses hidden mode the fallback is a documented minimised run, still no owner action.
- PC off: those days are missing; no estimate. Backfill on return, limits:
  - X: only as far as search honours the day window (depth UNVERIFIED, P-X5); up to 14 days for narrative coins, leftover units only.
  - Reddit: whatever the ~1000-item listing walk reaches; days not reached stay missing; time filters (`t=week/month/year`) are not used for counting.
  - Never by interpolation.

## Annex D: Failure and ban handling

| Event | Detection | Response | Row reason |
|---|---|---|---|
| Account suspended/locked | suspension/lock page or flag in response, HTTP 403 pattern | pause X until the owner acts (new dedicated account, config reset); no retries, no automatic health re-check; persisted | `x_account_suspended` |
| Login expired | redirect to login, logged-out marker, HTTP 401 | stop X; wait for owner re-login command; no stored values | `x_login_required` |
| Layout/API change | parser/validator rejects shape on 3 consecutive coins | one self-repair attempt per source per day, only while the monthly 15 USD cap (Q4) is not spent; if still failing, stop source, keep stored data | `layout_changed` |
| Rate limit | HTTP 429 or rate page | pause the source until 00:00 UTC next day, no retry, no growing backoff (Locked pacing rule 3); the pause is persisted; coins not done stay missing | `rate_limited` |
| Silent empty results | canary query returns nothing | treated as a warning: pause the source for the rest of the day, no zeros | `empty_results` |
| Cap hit | N, P, or ~1000-item listing | A.1/A.2 estimate or missing, flagged in evidence | none |
| Network off/PC asleep | connect errors | skip pass, retry next tick | `offline` (transient) |
| Reddit blocked/403 | HTTP 403/429 on public JSON | same as rate limit (pause rest of day, no retry); if paused 3 days in a row, `blocked` shown | `reddit_blocked` |

Every failure keeps previously stored days untouched. Sources row: `ok` when coins have data within lag, `insufficient-history` below the gate, failed reasons above as `unavailable` plus note (or `failed`, W8f).

## Annex E: Options (INNOVATE preview, no approach chosen)

| Option | Pros | Cons |
|---|---|---|
| A. Direct HTTP with own login (httpx) | no extra dependency; simplest for Reddit's public listing | X login/anti-bot is heavy and brittle; every site change is a code change |
| B. API Anything (owner lock) | learns requests, tiers, self-repair, fewer code changes | young unvetted dependency; self-repair may cost LLM money; tier 3 is a real browser run (heavy); behaviour unproven here |
| C. Browser automation (Playwright with a persistent profile) | well known, controllable, visible fallback | selectors break on layout change; heavier; more custom code |

Recommendation: keep the owner's lock, B for both sources behind a thin adapter interface, so Reddit can drop to A (public listing, no login) and X to C without touching scoring or storage. First prove B in W8a; if P-X3 or P-X4 fail, report to the owner with C as the next choice.

## Annex F: Cost and risk

| Item | Estimate | Note |
|---|---|---|
| Build, slices W8a-W8h | about 20-32 USD | Annex H; per-slice cap 15 USD, planner asks at 7 USD |
| Self-repair LLM calls | at most 15 USD per month (owner cap) | whether any LLM call happens is UNVERIFIED (P-X2) |
| Running cost | 0 USD cash, plus the capped self-repair above | |
| Owner time | one login, probes, then none | AC18 |
| X account ban | still possible, accepted | a slow pace (one unit per 10-20 min, 100 per day) lowers request volume; it does NOT remove the ban risk, and no evasion technique is used; use a throwaway; series gaps, not zeros |
| X/Reddit terms of service | automated reading breaches both | owner-accepted for X; Reddit has pending official route |
| Supply chain | an unvetted dependency runs on the owner's PC with a logged-in browser | vetting in Annex G; pin; no install scripts; never xscrape |
| Delay | values are one day late by design | trend detection works over days (owner accepted) |
| Data quality | bots, spam, ambiguous tickers, capped estimates | dedupe, per-author limit, ambiguity list, evidence flags |
| Reliability | PC off, sleep, site change | missing-not-zero, catch-up, breakers |
| Sandbox | cannot prove any live behaviour | owner probes |

Vetting API Anything before first use (owner command list in P-X2): resolve and write down one commit SHA; clone to a fresh empty folder without running anything; read the manifest(s) for install/postinstall/prepare scripts and refuse any; list dependencies and their versions, install only from a hash-pinned lock file into an isolated environment; read the code paths the adapter will call (request replay, tier 3 browser launch, self-repair network calls, anything that reads files, cookies or env); note every outbound host; check the licence; first run in Windows Sandbox or a throwaway VM with no secrets and the dedicated X account only; compare the same commit before every upgrade. The adapter then calls only that pinned version.

## Annex G: What the sandbox cannot prove, and owner probes

Not provable here: that X or Reddit answer from the PC; login and hidden run; X search depth and operators; real caps and rate limits; Reddit endpoint shape and listing depth; API Anything's actual behaviour and self-repair cost. Tests prove only logic with fakes. Probes print only numbers, statuses and class names; the owner pastes the output. Commands run in PowerShell on the PC. `probe_pc_sources` is built in W8a/W8b and prints counts, statuses and timestamps only (AC11).

| Probe | Command | Pass looks like |
|---|---|---|
| P-X1 reachability | `curl.exe -s -o NUL -w "%{http_code}\n" https://x.com/` | a number such as 200 or a redirect code, not 000/403 |
| P-X2 vet API Anything (nothing executed) | `git ls-remote https://github.com/goodnight000/api-anything HEAD` then `git clone --no-checkout https://github.com/goodnight000/api-anything C:\vet\apianything` then `git -C C:\vet\apianything checkout --detach <SHA from ls-remote>` then `Get-ChildItem C:\vet\apianything -Recurse -Include package.json,pyproject.toml,setup.py,setup.cfg,requirements*.txt \| Select-String -Pattern "postinstall\|preinstall\|prepare\|cmdclass\|console_scripts\|bin"` | SHA written down; match list pasted for review; no install hooks |
| P-X3 login and one search | `python -m api.scripts.probe_pc_sources --source xsearch --symbol SOL --login` once (opens API Anything's window), then `... --source xsearch --symbol SOL` | prints tier used, HTTP status, k, N, span_hours, capped, no text |
| P-X4 hidden run | `python -m api.scripts.probe_pc_sources --source xsearch --symbol SOL --hidden` | same output, no window appeared (owner states yes/no) |
| P-X5 depth and operators | `python -m api.scripts.probe_pc_sources --source xsearch --symbol SOL --days-back 1,7,14,30,60,90` | per day k, span_hours, capped; shows how far back results exist |
| P-X6 caps and rate | `python -m api.scripts.probe_pc_sources --source xsearch --symbols SOL,ETH,BTC,AVAX,LINK,DOT,ADA,XRP,DOGE,NEAR --paced` | status histogram, elapsed minutes, any 429 count |
| P-X7 stays logged in | rerun P-X3 line 2 after 3 days with the worker idle | still ok, no login prompt |
| P-R1 Reddit reachability | `curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code} %{size_download}\n" "https://www.reddit.com/r/CryptoCurrency/search.json?q=solana&restrict_sr=1&sort=new&limit=1"` | 200 and size above 0 |
| P-R2 listing depth | `python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --walk` | number of items reached, oldest date, per-day counts |
| P-R3 rate | `python -m api.scripts.probe_pc_sources --source reddit --symbols SOL,ETH,BTC,AVAX,LINK --paced` | status histogram, elapsed seconds, any 429 |
| P-R4 multi-subreddit | same as P-R1 with `r/CryptoCurrency+CryptoMarkets+altcoin` in the path | 200, size above 0 |
| P-R5 own-site vs site-wide | `python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --compare-scope` | counts for the set vs site-wide, same day |

## Annex H: Proposed PLAN slices (amended T131; detail in the PLAN file)

Model rule: code execution = opus, docs/vetting = sonnet. USD are planner-style estimates, UNVERIFIED. Build order: Reddit first, X after the owner probes P-X1..P-X7.

| Order | Slice | Content | Tier | Model / effort | USD |
|---|---|---|---|---|---|
| 1 | W8a | Vet API Anything per Annex F (report only, no code), pin SHA, adapter interface decision; owner runs P-X1, P-X2, P-R1 | docs + RT2 | sonnet, medium | 2-3 |
| 2 | W8b | Pure core: density formula, yesterday-only window rule, trickle scheduler core (spacing, caps, pause state), query/ambiguity/subreddit files, parsers, evidence sidecar, stores, guards, fakes, `probe_pc_sources` tool skeleton | RT2 | opus, medium | 4-6 |
| 3 | W8c | Reddit connector via adapter: listing walk, day counts, backfill from leftover requests; probes P-R2..P-R5 | RT2 + owner probes | opus, medium | 3-5 |
| 4 | W8e | Worker wiring: shell (if W8 absent), `fetch_side`, `_behind` start, trickle, pause persistence, flag | RT2 | opus, medium | 3-5 |
| 5 | W8f | Discovery wiring: `source_impl`, Sources reasons, backfilled flag in point-in-time | RT2 | opus, medium | 2-3 |
| 6 | W8g | Web: Sources/updating-data text for reasons | RT3 | opus, low | 1-2 |
| 7 | W8d | X connector via adapter after owner probes P-X1..P-X7: login command, hidden run, search windows, canary, breaker | RT2 + owner probes | opus, high | 5-7 |
| 8 | W8h | Owner guide + probe closeout, go/no-go | docs | sonnet, low | 1 |

Reddit can go live before X exists. If W8e lands before W8c, the worker idles (no source).
