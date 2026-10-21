---
name: spec:narrative-baskets-xreddit-collector
description: "T126: collect X and Reddit attention on the owner's PC without the official X or Reddit APIs, via API Anything (X) and public RSS feeds over plain HTTP (Reddit, T138), as two pc_side sources (xsearch, reddit) of the weighted signal. Docs only; no approach built, nothing run."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

Status: APPROVED (locked) by the owner on 21-10-26 for the T136 text (recorded on the planner's message; this session did not see the approval itself). T138 then amended the Reddit access method (Annex A.2, C, D, E, F, G, H, rules 1, 10, 11, AC2, AC8, AC9, AC17, AC25, Q15, Q16) on new owner probe evidence, at the planner's instruction; the owner's approval of the T138 changes is not recorded in this session. A scope gap goes to the phase report under `## SPEC Gaps` and to the backlog. Change log: Annex I. The SPEC has 25 acceptance criteria, above the skill's usual 20, on the planner's instruction.

# Narrative Baskets: X and Reddit collector on the PC, no official APIs (T126, 21-10-26)

Builds on the weighted-signal SPEC (T98, W8 `fetch_side`) and T96 (`max_source_lag_days`). "Attention" means mentions, never price. Code was read on `main` at 007d53c. Everything about API Anything, X, Reddit and the owner's PC is UNVERIFIED: no provider is reachable from the sandbox and nothing from API Anything was read or run.

## Summary

Two Discovery inputs, X search (weight 10) and Reddit (weight 15), have no data today because the official APIs cost money (X) or await approval (Reddit). This SPEC defines how the owner's own PC fills them anyway: while the API runs on the PC, a hidden background worker reads X through the tool API Anything and Reddit through its public RSS feeds over plain HTTP (no login, no browser, T138), and stores one number per coin per day in the existing daily store. On days the PC is off the source is simply missing for those days (never 0, never estimated). After a one-time login of a dedicated X account the owner does nothing. GitHub dev activity is parked.

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

## Locked pacing rules (owner decisions, T131 and T133, 21-10-26)

1. **Trickle, pace is config.** X collects ONE coin unit at a time with a random delay between units drawn uniformly from `x_query_delay_min_s` to `x_query_delay_max_s`. Default proposal 180 to 360 s (3 to 6 minutes, mean 4.5 min); the owner can make it slower or faster only by editing config. A unit is one coin for one completed day: at most `x_page_cap` page loads, spaced 5-15 s apart inside the unit. The owner chose this shorter delay (3 to 6 minutes, confirmed) over the original 10-20 minutes; the delay is not the real cap, the daily post budget in rule 6 is. The trickle runs over the hours the PC is on; there are no catch-up bursts: after a restart, a pause, or days off, the pace is never faster than the configured minimum delay. Reddit (T138): about one request per minute at most, config `reddit_request_delay_min_s` 60 and `reddit_request_delay_max_s` 120 (defaults), at most `reddit_daily_request_budget` (default 150) requests per UTC day, one stream at a time.
2. **Yesterday-only.** A day's value is collected only after that UTC day is complete and is shown one day late (one day gap accepted by the owner; trend detection works over days). Today's partial day is never stored and never shown. Forward work (yesterday) always has priority; backfill uses only what is left of the budget (for X that is usually nothing, see rule 6).
3. **Pause on warning.** Any rate-limit, login or suspension warning pauses that source for the rest of that UTC day, with no retries and no growing backoff. The pause is persisted, so restarting the API does not lift it. Suspension and login-expired stay paused beyond the day until the owner acts (new account, re-login).
4. **Scope and spend.** Coin set first is narrative coins only; backfill is short; build order is Reddit first, X later after the owner probes; self-repair LLM spend is capped at 15 USD per month; both Reddit series (web and the future official one) stay separate, config picks, never spliced.
5. **Account.** X uses a throwaway dedicated account only, never the owner's main or Premium account. The official X API route was not chosen; it is recorded as an unbuilt no-ban fallback (Annex E option D).
6. **Daily read budget (the real limit).** The delay is not the real limit; reading volume is. Third-party, unofficial reports say a regular logged-in X account can read about 1,000 posts per day (about 500 for a new account, about 10,000 for Premium); X does not publish it, so it is UNVERIFIED. Config `x_daily_post_budget` (default 800) counts every post loaded from X results (kept or dropped by dedupe); the worker enforces it before each page load; when it is spent X stops for the rest of the UTC day and the unread coin-days are missing (never 0). Sample size is small so more coins fit: config `x_sample_n` 40, `x_sample_min` 20, `x_page_cap` 3. Resulting capacity: about 800 / 40 = 20 coins per day (more when a coin has fewer than 40 matching posts). With the 75 narrative coins that is a rotation of about 4 days per coin; at the default pace 20 units take about 90 minutes of PC time, so the budget and pace work with only a few hours of PC uptime per day (rule 1 has no daily time window). Rotation changes what Discovery sees for X (sparse points); see Q10.
7. **Adaptive budget.** After any warning day the next day's effective X budget is halved (floor: one unit, `x_sample_n`); after 7 consecutive clean days (a UTC day on which X ran at least one unit with no warning) the effective budget may double once, back up to the configured value, and the clean-day count restarts. Days with no X activity change nothing. The effective budget and counters are persisted.
8. **Honest limit.** A slower pace or a smaller volume lowers ban risk; it does not remove it, and a faster pace or higher volume raises it. The account is throwaway and the owner accepted the risk. No detection-evasion technique is part of this SPEC or any slice: no fingerprint spoofing, no proxy rotation, no extra or fake accounts, no stealth.
9. **Discovery for X uses rotation mode (owner answer to Q10).** Because the daily read budget refreshes only about 20 of the 75 narrative coins per day, an X series has points only on a coin's rotation days. For X, Discovery therefore replaces the 7-day window with the latest 3 stored X values: change = (newest of the 3 minus the mean of the 2 earlier ones) divided by that mean, in percent, with the same "base mean must be above 0" rule as other sources (config `x_discovery_mode` = `rotation`, `x_rotation_points` = 3; `window` keeps today's rule). A coin with fewer than 3 stored X points has X missing (never 0, weights rescale). The history gate for X in rotation mode is these 3 points (not `min_history_days`). Staleness: a rotation coin is refreshed about every 4 days, so the T96 lag limit for X in rotation mode is `x_rotation_max_lag_days` (default 7) instead of `max_source_lag_days`. The coin queue in rotation mode is ordered by oldest newest-stored X day first. All other sources (Reddit and the rest) keep the 7-day window. This is a locked rule recorded now; it is NOT implemented in this task (slice W8f). Locked reading (owner answer to Q13, T136): the rotation score is the newest of the latest 3 stored values against the mean of the other 2, and `x_rotation_max_lag_days` defaults to 7.
10. **PC-hours window (owner answer to Q11).** The PC is on about 1 to 3 hours per day. The pace and the budget must fit that window: X needs about 90 minutes at the default pace to spend its 800-post budget (about 20 units), so on a 3-hour day X finishes its budget in half the window, and on a 1-hour day X completes about 13 units and stops when the PC stops. Reddit uses the remainder and runs as a separate stream at the same time as X (different provider, own per-source lock; locked by the owner's answer to Q14, T136): at 60-120 s per request (mean 90 s) about 40 requests fit in one hour, about 40 coins (one search.rss request per coin, UNVERIFIED until probe P-R6), about 120 in three hours; all 75 narrative coins need about 75 requests, about 112 minutes. Depth, not pace, is the sharper Reddit limit: see Annex A.2. What is skipped: when the PC is off nothing runs and nothing is stored for those days (no 0, no estimate); a coin-day not finished before the PC stops stays in the queue and is collected on a later PC day inside the backfill limits, yesterday first, else it stays missing.
11. **Reddit access (T138, owner probe evidence 21-10-26).** The owner's PC probe with the honest user agent `attention-probe/0.1` showed `search.json` = HTTP 403 with a block page of about 190 KB: plain JSON access is closed from this PC. The public reader feeds work: `r/CryptoCurrency/new/.rss` = 200 (52 KB) and `r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new` = 200 (53 KB). So Reddit is collected from those feeds with plain HTTP (stdlib or httpx), one honest descriptive user agent, no login, no API Anything, no browser, no proxy, no disguise. Any 403, 429 or block page pauses Reddit for the rest of the UTC day, no retries (rule 3). Yesterday-only, logging and per-source locks are unchanged. The official Reddit API (approval pending) remains the later replacement as a separate series (Q7).

## Acceptance Criteria (Testable Outcomes)

All tests use fakes and an injected clock; live behaviour is proven only by owner probes (Annex G).

- AC1. X density formula and yesterday-only: for a completed UTC day with k tweets collected, N target, oldest tweet time t_old: if the window start is reached with k < N the value is k (exact); if k hits N first the value is 24 * N / span_hours with span = window end minus t_old, floored at 0.25 h; with the page cap hit and N_min <= k < N the same formula uses k; below N_min the day is missing (defaults N = 40, N_min = 20, page cap 3, all config). A value is stored only when the injected clock is at or after the window end (00:00 UTC of D+1); a request for today's date stores nothing and the Sources `newest` never equals today.
  proven by: density-formula table test (exact, capped, floor, below-min, boundary k = N); no-same-day-value test with injected clock at 23:59 and 00:00
  strategy: Fully-Automated
- AC2. Reddit feed counting: from an Atom feed response (newest first, entries with `updated`/`published` timestamps), a completed UTC day is counted as the exact number of entries in the window when the oldest entry in the response is older than the window start; otherwise, with at least `reddit_sample_min` (default 10) entries in the window, the A.1 density formula over the covered span (flag `capped`); otherwise the coin-day is missing; entries newer than the window end are ignored; a day the feed depth does not reach is missing, never 0.
  proven by: feed-parse and counting table test (exact, capped, below-min, entries-after-window, depth-not-reached)
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
- AC8. Trickle and catch-up: with an injected clock and a seeded random source, X units are spaced by a delay drawn from `x_query_delay_min_s`..`x_query_delay_max_s` (defaults 180-360 s) and Reddit requests by `reddit_request_delay_min_s`..`reddit_request_delay_max_s` (defaults 60-120 s), both read from config; X stops when `x_daily_post_budget` is spent and Reddit at `reddit_daily_request_budget` (default 150) requests per UTC day; a worker started after days off is scheduled ~20 s later (T51 `_behind` pattern) but its pace is identical (never faster than the configured minimum delay, no catch-up burst), and the daily budgets hold on catch-up; with only 2 hours of PC uptime in an injected clock the units still run at the configured pace and stop when the clock stops; yesterday units run before backfill units; passes of one source never overlap (per-source lock), while the X and Reddit streams may run at the same time; the flag off means no thread.
  proven by: injected-clock trickle-spacing test (config values changed in the test); daily-cap test; catch-up-same-pace test; few-hours-uptime test; priority-order test (mirrors the equities worker tests)
  strategy: Fully-Automated
- AC9. Failure handling per Annex D: login expired, suspension, layout change after failed self-repair, rate limit, and a Reddit 403, 429 or block page each set a distinct reason on the Sources row, stop only the affected source, never write values, and never crash the API.
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
- AC17. Live behaviour (login, hidden run, X search depth, caps, real rate limits, Reddit feed shape, entry count and depth) is proven by owner probes P-X1.., P-R1.. with pasted output; the build is not "done" for live purposes before those pass.
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

- AC21. Daily read budget: with a fake adapter reporting posts per page, the worker counts every post loaded (kept or dropped), refuses the next page load that would exceed `x_daily_post_budget` (default 800), stops X for the rest of the UTC day, stores nothing for unread coin-days (never 0), keeps a unit whose count already reached `x_sample_min`, and resets at 00:00 UTC; the count survives a restart.
  proven by: budget-enforced test; budget-reset-and-restart test; unread-coins-missing test
  strategy: Fully-Automated
- AC22. Adaptive budget: after a warning day the next day's effective budget is half (floor one unit); 7 consecutive clean days double it once up to the configured value; a warning resets the clean count; days with no X activity change nothing; state survives restart.
  proven by: adaptive-halving test and 7-clean-days-doubling test with injected clock; no-activity-day-no-change test
  strategy: Fully-Automated

- AC23. X rotation mode: with `x_discovery_mode` = `rotation`, a coin with exactly 3 stored X points on rotation days gets an X change from them (newest against the mean of the other two) and X contributes its weight; a coin with 2 or fewer stored X points has X missing (weights rescale, never 0); X points older than `x_rotation_max_lag_days` drop out; the 7-day window and `max_source_lag_days` still apply unchanged to every other source; `window` mode reproduces today's X behaviour; point-in-time: day D uses only X points dated up to D.
  proven by: rotation-three-points-scores test; fewer-than-three-missing test; rotation-lag test; other-sources-unchanged regression test; point-in-time truncate test
  strategy: Fully-Automated
- AC24. PC-hours window: with an injected clock giving 1 hour of uptime, the X stream runs units at the configured pace (about 13 at the default) and the Reddit stream runs concurrently within its own pace, both stop when the clock stops, and nothing is stored for hours or days the PC is off; with 3 hours X stops when its post budget is spent; coin-days not finished stay queued, are collected on a later day inside the backfill limits (yesterday first), and are otherwise missing, never 0.
  proven by: one-hour-uptime test; three-hour-budget-stop test; pc-off-nothing-stored test; unfinished-queue-carry-over test
  strategy: Fully-Automated

- AC25. Reddit access rules: Reddit requests go over plain HTTP to the public feed URLs only (no JSON endpoint, no login, no API Anything), with one honest descriptive user agent constant and no browser user-agent string; any 403, 429 or block page (an HTML or non-Atom body) is never parsed as data, pauses Reddit for the rest of the UTC day with no retry, and sets reason `reddit_blocked` or `rate_limited`; a response with a DOCTYPE or entity declaration or above the size cap is rejected before parsing; logs hold only the exception class and HTTP status.
  proven by: fake-http tests (URL form, user-agent constant, 403/429/block-page pause, no-retry request count, DOCTYPE rejection, log scrub)
  strategy: Fully-Automated

## Out Of Scope

- GitHub dev activity (parked), DefiLlama, Trends, exchange sources.
- Official X and GitHub APIs (the official X counts route is recorded as an unbuilt fallback, Annex E option D); the official Reddit API (pending separately; only the method-swap rule is specified).
- Building or running anything, installing API Anything, `.github/` changes, any web UI beyond the existing Sources status text and "updating data" state.
- Sentiment, comment counts, impressions, likes, influencer weighting.
- Using the owner's main X account, buying proxies or accounts, and any detection-evasion technique (fingerprint spoofing, proxy rotation, extra or fake accounts).
- Same-day (partial-day) values, speeding up to catch up.
- Implementing the X rotation rule for Discovery now (it is locked here and built only in slice W8f after the owner approves the SPEC); building the official X API counts route (option D, fallback only); using the owner's main or Premium X account.
- Changing source weights or the trigger rule.

## Constraints

- Owner-locked: API Anything for X (Reddit uses plain HTTP on the public RSS feeds, T138); runs on the owner's PC hidden, inside the API as a worker like the equities refresh worker; dedicated separate X account, ban risk accepted; no official X or GitHub API; cookies cannot be imported on Windows, login happens once in API Anything's own window.
- Output must plug into the source model: daily series per symbol, state ok / insufficient-history / failed, missing never 0, frozen days, point-in-time, T96.
- Safety: the `xscrape` library (also `kloxeld`, `gunkonchi`) is malware and is never used, installed or referenced as a dependency. Any dependency is pinned and reviewed first.
- Logging: exception class and HTTP status only.
- Fits existing code: store keeps only completed UTC days, first write wins (`api/data/attention/store.py`); Sources status is read-only from files (`api/analytics/attention/sources.py`); worker pattern is `api/data/equities_refresh.py` (daemon thread, `PASS_LOCK`, `_behind`, env flag).
- Existing `xsearch` code is an official-API path gated by `X_LIVE` and a bearer token; the new path must not require either.

## Open Questions

| # | Question | Owner | Needed by |
|---|---|---|---|
| Q1 | PARTLY ANSWERED (owner): throwaway dedicated account only, never the main or Premium account. STILL OPEN: who creates it, with what email/phone, and is a phone number required for login (affects hidden re-login)? | owner | W8d |
| Q2 | ANSWERED (owner): short backfill: X up to 14 days if search honours day windows, Reddit as far as its listing reaches; both only from leftover units (Locked pacing rules). | owner | closed |
| Q3 | ANSWERED (owner): narrative coins only first; widening later by config. | owner | closed |
| Q4 | ANSWERED (owner): self-repair LLM spend cap 15 USD per month. Whether it calls a paid LLM at all stays UNVERIFIED (probe P-X2). | owner | closed |
| Q5 | Is the API process already hidden on the PC (no console window), or does the worker's browser need extra hiding? | owner (probe P-X4) | W8e |
| Q6 | SUPERSEDED by the Locked pacing rules (config pace, yesterday-only). | planner | closed |
| Q7 | ANSWERED (owner): keep BOTH series separate, config picks, never spliced. | owner | closed |
| Q8 | Reddit subreddit list in Annex A.2: edit before build? | owner | W8c |
| Q9 | Relation to W8 (generic PC worker, T98 SPEC): checked 21-10-26, the generic W8 worker does NOT exist on `main` (no `attention_pc_refresh` module, no `SCREENER_ATTENTION_PC_WORKER` in code). The PLAN plugs these slices into the T98 W8 design and builds the minimal worker shell inside W8e; if the planner dispatches W8 first, W8e only adds the sources. | planner | PLAN |
| Q10 | ANSWERED (owner, T135): Discovery for X uses the latest 3 stored X values against the earlier stored values (rotation mode) instead of the 7-day window; the 7-day window stays for all other sources; locked as Locked pacing rule 9, AC23; built in W8f, not now. | owner | closed |
| Q11 | ANSWERED (owner, T135): the PC is on about 1 to 3 hours a day; pace and budget must fit that window (Locked pacing rule 10, AC24); probe P-W2 stays as an optional check. | owner | closed |
| Q12 | ANSWERED (owner, T135): keep the Reddit numbers as planned (20-60 s per request, 300 per day). SUPERSEDED IN PART by T138 on new probe evidence: Reddit pace is now 60-120 s per request and 150 requests per day (planner instruction), and the access method is the public feeds. | owner | closed |
| Q13 | ANSWERED yes (owner, T136): X rotation score = newest of the latest 3 stored values against the mean of the other 2; `x_rotation_max_lag_days` default 7. Locked in Locked pacing rule 9 and AC23. | owner | closed |
| Q14 | ANSWERED yes (owner, T136): X and Reddit run concurrently with per-source locks. Locked in Locked pacing rule 10, AC8 and AC24. | owner | closed |
| Q15 | NEW (T138): add the stream-and-count variant for Reddit (Annex A.2 M2) as a complement to per-coin search.rss? It polls a few subreddit `new.rss` feeds a few times per PC window and counts ticker/name mentions for all narrative coins from the same entries: far fewer requests (about 36 against about 75), newest-slice bias, and days complete only when consecutive polls overlap. Recommended as a complement; not built unless the owner chooses. | owner | before W8c closes |
| Q16 | NEW (T138): at what UTC hours is the PC usually on? A feed returns only its newest entries, so a busy coin's yesterday is reachable only if the request happens soon after UTC midnight (Annex A.2). Evidence: probe P-W2 (times) and the owner's own answer. | owner | before W8c |

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

Constants (config, owner-editable): `x_sample_n` N = 40, `x_sample_min` N_min = 20, `x_page_cap` P = 3 pages/scroll steps, span floor 0.25 h, canary query `bitcoin` (the canary's own posts count against the daily read budget). Earlier T131 values were N 100, N_min 30, P 8; they were cut so more coins fit the daily read budget. The formula is unchanged.

Value for day D (tweets per day):
- window start reached with k < N: value = k (exact count), capped = false.
- k reaches N first: value = 24 * N / span_hours, span_hours = (window end - oldest counted tweet time) in hours, floor 0.25; capped = true.
- page cap hit with N_min <= k < N: same as capped with N replaced by k; flag `pagecap`.
- k < N_min and window not exhausted: the coin-day is missing.

Properties: continuous at k = N (a 24 h span gives about N); the capped estimate reads the end of the UTC day, so its time-of-day bias is the same every day and cancels in the window-over-window change Discovery uses; relative noise about 16% at N = 40 if tweets were Poisson (was about 10% at N = 100), more when bursty; a smaller sample trades precision for coverage, and Discovery's window averaging softens it. Cap and rate-limit rules: Annex E. Spam spike: reuse the existing `SPAM_SPIKE_RATIO` (10): a day above 10x the trailing median is stored but flagged `spike` for the owner, not dropped.

### A.2 Reddit: posts mentioning the coin per day (`reddit_web`), public RSS feeds (rewritten T138)

**Evidence (owner probes, 21-10-26, PowerShell on the owner's PC, honest user agent `attention-probe/0.1`, no disguise).** P-R1: `search.json` = HTTP 403 with a block page of about 190 KB (JSON endpoints are recorded as blocked and are not used). The reader feeds answer: `https://www.reddit.com/r/CryptoCurrency/new/.rss` = 200, 52 KB; `https://www.reddit.com/r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new` = 200, 53 KB. Third-party reports say the public feeds are limited to about 1 request per minute per IP (UNVERIFIED, probe P-R3).

**Access.** Plain HTTP (stdlib or httpx), one honest descriptive user agent constant, no login, no API Anything, no browser, no proxy. Atom feeds list posts (not comments), newest first, each entry with `updated` and `published` timestamps. Entries per request: UNVERIFIED (Reddit's default is believed to be 25; `limit=100` may be honoured), probe P-R6 measures the count with and without `limit=100` and whether `after=` paging works. The official Reddit API (approval pending) later replaces this as a separate `reddit_api` series (Q7).

**M1 (primary): one search.rss request per coin.** URL form `https://www.reddit.com/r/<A+B+C...>/search.rss?q=<terms>&restrict_sr=1&sort=new[&limit=100]` over the subreddit set (the `+` path form is UNVERIFIED, probe P-R4); terms from the owner file (ticker and name in quotes). Ambiguous tickers are listed as ambiguous and missing.

**Counting for a completed UTC day D** (window = D 00:00 to D+1 00:00): keep entries with a timestamp inside the window; ignore newer ones.
- If the oldest entry in the response is older than the window start, the response covers the window: value = number of entries in the window (exact), capped = false.
- Otherwise, if at least `reddit_sample_min` (default 10) entries are in the window: the A.1 density formula over the covered span, value = 24 * k / span_hours with k the entries in the window and span = window end minus the oldest entry in the window (floor 0.25 h), flag `capped`.
- Otherwise the coin-day is missing. Never 0 for a failed or unreached day (AC3).

**Depth limit (the sharp one).** Older days are reached only as far as the feed depth goes; a request returns only the newest L entries. For a quiet coin (fewer than L entries over several days) a response can cover several days. For a busy coin L entries may cover only hours, so yesterday is reachable only if the request is made soon after UTC midnight; collected later in the day it is missing. The owner's PC is on 1 to 3 hours per day at unknown UTC hours (Q16), so some busy coins will be missing on some days. Backfill is whatever one response reaches; no extra paging unless P-R6 shows `after=` works (then each page costs a request from the daily budget).

Proposed subreddit set (owner edits, Q8; activity UNVERIFIED): CryptoCurrency, CryptoMarkets, altcoin, CryptoMoonShots, SatoshiStreetBets, defi, CryptoTechnology, ethtrader, ethereum, solana, Bitcoin, binance. Coin-own subreddits (e.g. r/solana) are a later add-on per coin.

**M2 (option, recommended as a complement, Q15): stream and count.** Poll a few subreddit `new.rss` feeds (for example 12) a few times inside the PC window (about 36 requests a day against about 75 for M1), de-duplicate entries by id, and count ticker and name mentions in titles (and any content snippet) for all narrative coins from the same entries. Far fewer requests. Newest-slice bias: a poll sees only the posts since the previous poll, up to the feed depth. A day is counted only when consecutive polls overlap (the oldest entry of a poll is not newer than the newest entry of the previous poll), which a PC that is off most of the day usually cannot guarantee, so without overlap the day is missing. Mention matching has the same ambiguity problem as M1 and uses the same ambiguity list. Not built unless the owner chooses it.

**Safety of the parser.** Feeds are untrusted XML: a body with a DOCTYPE or entity declaration, a body that is not Atom (an HTML block page), or a body above the size cap is rejected before parsing and treated as a block (pause for the rest of the day).

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
- X pace (config, T133): one unit after a random delay of `x_query_delay_min_s`..`x_query_delay_max_s` (default 180-360 s), page loads inside a unit spaced 5-15 s; `x_daily_post_budget` (default 800) counts posts read and ends X for the day when spent; adaptive halving and doubling per Locked pacing rule 7. Reddit pace (T138): one request every 60-120 s (config, defaults), at most 150 per UTC day. Same pace after a restart or after days off; a catch-up never raises the rate.
- Capacity check (arithmetic, not measured): 800 posts / `x_sample_n` 40 = about 20 coin-units per day (more for coins with few matching posts); 20 units at a 4.5 min mean take about 90 minutes, so a few PC hours per day suffice. The 75 narrative coins therefore rotate about every 4 days (75 / 20), unless the coin set is cut to about 20 (Q10). The delay is not the limit: at 4.5 min a 24 h PC could start 320 units, but the read budget stops X after about 20. After a warning day the effective budget is 400 (about 10 units), then 200, down to one unit; recovery takes 7 clean days per doubling. X backfill needs units beyond yesterday's: with a rotation there are none left, so X backfill is effectively off unless the coin set is small; history accrues forward only, and the 30-day `min_history_days` gate is met per coin after about 30 days of its own points (a rotating coin has about 8 points in 30 days, so Q10's rule matters). Reddit (T138): about 75 forward requests (one search.rss per coin, UNVERIFIED until P-R6), about 112 minutes at the 90 s mean delay, against a daily budget of 150, leaving about 75 requests for retries of missing coin-days; there is no listing walk-back.
- PC window (T135): the PC is on about 1-3 h per day (owner). X units (about 90 min at the default pace for 20 units) and Reddit requests run as two concurrent streams, each with its own lock; short days finish fewer coin-days, which carry over (Locked pacing rule 10). Nothing is stored or estimated for PC-off hours or days.
- Start: `_behind` per source (newest stored day < yesterday) schedules the first unit about 20 s after start, then the trickle. Reddit requests should run as early after 00:10 UTC as the PC allows, busiest coins first, because a feed reaches back only its newest entries (Annex A.2); coins whose feed does not reach into yesterday are missing.
- Hidden: login once in API Anything's own window (owner command); afterwards no visible window (headless, else off-screen/minimised; P-X4). If X refuses hidden mode the fallback is a documented minimised run, still no owner action.
- PC off: those days are missing; no estimate. Backfill on return, limits:
  - X: only as far as search honours the day window (depth UNVERIFIED, P-X5); up to 14 days for narrative coins, leftover units only.
  - Reddit: whatever one feed response reaches (depth UNVERIFIED, P-R6); days not reached stay missing; no JSON, no time filters.
  - Never by interpolation.

## Annex D: Failure and ban handling

| Event | Detection | Response | Row reason |
|---|---|---|---|
| Account suspended/locked | suspension/lock page or flag in response, HTTP 403 pattern | pause X until the owner acts (new dedicated account, config reset); no retries, no automatic health re-check; persisted | `x_account_suspended` |
| Login expired | redirect to login, logged-out marker, HTTP 401 | stop X; wait for owner re-login command; no stored values | `x_login_required` |
| Layout/API change | parser/validator rejects shape on 3 consecutive coins | one self-repair attempt per source per day, only while the monthly 15 USD cap (Q4) is not spent; if still failing, stop source, keep stored data | `layout_changed` |
| Read budget spent | worker counter reaches `x_daily_post_budget` | stop X for the rest of the UTC day; unread coin-days missing; not a warning, no halving | `budget_spent` (info) |
| Rate limit | HTTP 429 or rate page | pause the source until 00:00 UTC next day, no retry, no growing backoff (Locked pacing rule 3); the pause is persisted; coins not done stay missing; next day's X budget is halved (rule 7) | `rate_limited` |
| Silent empty results | canary query returns nothing | treated as a warning: pause the source for the rest of the day, no zeros | `empty_results` |
| Cap hit | N, P, daily budget, or ~1000-item listing | A.1/A.2 estimate or missing, flagged in evidence | none |
| Network off/PC asleep | connect errors | skip pass, retry next tick | `offline` (transient) |
| Reddit blocked/403 | HTTP 403 or 429, an HTML or non-Atom body, a DOCTYPE/entity body, or a body above the size cap, on a feed URL | pause Reddit for the rest of the UTC day, no retry, body never parsed as data; if paused 3 days in a row, `blocked` shown | `reddit_blocked` (403, block page) or `rate_limited` (429) |

Every failure keeps previously stored days untouched. Sources row: `ok` when coins have data within lag, `insufficient-history` below the gate, failed reasons above as `unavailable` plus note (or `failed`, W8f).

## Annex E: Options (INNOVATE preview, no approach chosen)

| Option | Pros | Cons |
|---|---|---|
| A. Direct HTTP (httpx), no login for Reddit | no extra dependency; used for Reddit's public RSS feeds (T138) | X login/anti-bot is heavy and brittle; every site change is a code change |
| B. API Anything (owner lock) | learns requests, tiers, self-repair, fewer code changes | young unvetted dependency; self-repair may cost LLM money; tier 3 is a real browser run (heavy); behaviour unproven here |
| C. Browser automation (Playwright with a persistent profile) | well known, controllable, visible fallback | selectors break on layout change; heavier; more custom code |

| D. Official X API counts route (not chosen, not built) | no account ban risk, official numbers | pay per request (reported 0.005 USD per request, about 1.5-11 USD per month for 10-75 coins at one call per coin per day, UNVERIFIED); top-up minimum and lookback UNVERIFIED; whether it works for this use is UNCONFIRMED |

Owner one-call test for D (PowerShell, token only in the environment, the command prints only a status code; the owner never pastes the token): `$env:X_BEARER_TOKEN="<token>"; curl.exe -s -o NUL -w "%{http_code}\n" -H "Authorization: Bearer $env:X_BEARER_TOKEN" "https://api.x.com/2/tweets/counts/recent?query=solana&granularity=day"` (200 means the route answers; 401/402/403 and the reason are recorded in the report, nothing else).

Recommendation (T138): B (API Anything) for X only, behind a thin adapter interface so X can move to C without touching scoring or storage; Reddit uses A, plain HTTP on the public RSS feeds, no adapter and no dependency on W8a. First prove B in W8a; if P-X3 or P-X4 fail, report to the owner with C as the next choice. Reddit access options considered: per-coin search.rss (M1, primary), stream-and-count of subreddit new.rss (M2, complement, Q15), JSON endpoints (blocked, 403), API Anything (not needed), official Reddit API (approval pending, later, separate series).

## Annex F: Cost and risk

| Item | Estimate | Note |
|---|---|---|
| Build, slices W8a-W8h | about 22-32 USD | Annex H; per-slice cap 15 USD, planner asks at 7 USD |
| Self-repair LLM calls | at most 15 USD per month (owner cap) | whether any LLM call happens is UNVERIFIED (P-X2) |
| Running cost | 0 USD cash, plus the capped self-repair above | |
| Owner time | one login, probes, then none | AC18 |
| X account ban | still possible and now somewhat higher, accepted by the owner | the T133 pace (3-6 min between queries) is faster than T131's and the read volume (800 posts per day by default) is real; a faster pace or higher volume raises the ban risk, a slower pace or lower volume lowers it but never removes it; the account is throwaway and the owner accepted the risk; no evasion technique is used; the adaptive rule halves the budget after any warning; series gaps, not zeros |
| Official X counts route (option D) | about 1.5-11 USD per month, UNVERIFIED | no-ban fallback if the throwaway account dies; not built; one-call owner test in Annex E |
| X/Reddit terms of service | automated reading breaches both | owner-accepted for X; Reddit has pending official route |
| Reddit feeds | third-party reports say about 1 request per minute per IP (UNVERIFIED); JSON is already blocked (403) | 60-120 s delay and 150 requests per day by default; any 403, 429 or block page pauses Reddit for the rest of the day; a plain honest user agent only, no browser strings, no proxy; official Reddit API (approval pending) is the later replacement |
| Supply chain | an unvetted dependency runs on the owner's PC with a logged-in browser | vetting in Annex G; pin; no install scripts; never xscrape |
| Delay | values are one day late by design | trend detection works over days (owner accepted) |
| Coverage | about 20 X coins per day, each narrative coin about every 4 days | Q10 rotation rule locked; Reddit about 40 coins per PC hour, but a feed returns only its newest entries, so busy coins collected late in the day are missing (Annex A.2) |
| Data quality | bots, spam, ambiguous tickers, capped estimates | dedupe, per-author limit, ambiguity list, evidence flags |
| Reliability | PC off, sleep, site change | missing-not-zero, catch-up, breakers |
| Sandbox | cannot prove any live behaviour | owner probes |

Vetting API Anything before first use (owner command list in P-X2): resolve and write down one commit SHA; clone to a fresh empty folder without running anything; read the manifest(s) for install/postinstall/prepare scripts and refuse any; list dependencies and their versions, install only from a hash-pinned lock file into an isolated environment; read the code paths the adapter will call (request replay, tier 3 browser launch, self-repair network calls, anything that reads files, cookies or env); note every outbound host; check the licence; first run in Windows Sandbox or a throwaway VM with no secrets and the dedicated X account only; compare the same commit before every upgrade. The adapter then calls only that pinned version.

## Annex G: What the sandbox cannot prove, and owner probes

Not provable here: that X or Reddit answer from the PC; login and hidden run; X search depth and operators; real caps and rate limits; Reddit feed entry count and depth, the feed rate limit; API Anything's actual behaviour and self-repair cost. Tests prove only logic with fakes. Probes print only numbers, statuses and class names; the owner pastes the output. Commands run in PowerShell on the PC. `probe_pc_sources` is built in W8a/W8b and prints counts, statuses and timestamps only (AC11).

| Probe | Command | Pass looks like |
|---|---|---|
| P-X1 reachability | `curl.exe -s -o NUL -w "%{http_code}\n" https://x.com/` | a number such as 200 or a redirect code, not 000/403 |
| P-X2 vet API Anything (nothing executed) | `git ls-remote https://github.com/goodnight000/api-anything HEAD` then `git clone --no-checkout https://github.com/goodnight000/api-anything C:\vet\apianything` then `git -C C:\vet\apianything checkout --detach <SHA from ls-remote>` then `Get-ChildItem C:\vet\apianything -Recurse -Include package.json,pyproject.toml,setup.py,setup.cfg,requirements*.txt \| Select-String -Pattern "postinstall\|preinstall\|prepare\|cmdclass\|console_scripts\|bin"` | SHA written down; match list pasted for review; no install hooks |
| P-X3 login and one search | `python -m api.scripts.probe_pc_sources --source xsearch --symbol SOL --login` once (opens API Anything's window), then `... --source xsearch --symbol SOL` | prints tier used, HTTP status, k, N, span_hours, capped, no text |
| P-X4 hidden run | `python -m api.scripts.probe_pc_sources --source xsearch --symbol SOL --hidden` | same output, no window appeared (owner states yes/no) |
| P-X5 depth and operators | `python -m api.scripts.probe_pc_sources --source xsearch --symbol SOL --days-back 1,7,14,30,60,90` | per day k, span_hours, capped; shows how far back results exist |
| P-X6 caps and rate | `python -m api.scripts.probe_pc_sources --source xsearch --symbols SOL,ETH,BTC,AVAX,LINK,DOT,ADA,XRP,DOGE,NEAR --paced` | status histogram, elapsed minutes, any 429 count |
| P-X7 stays logged in | rerun P-X3 line 2 after 3 days with the worker idle | still ok, no login prompt |
| P-X8 official counts route (optional, option D) | the Annex E one-call command | a status code; owner records 200 or the error class only |
| P-W2 PC hours | `Get-WinEvent -FilterHashtable @{LogName='System'; Id=6005,6006; StartTime=(Get-Date).AddDays(-7)} \| Select-Object TimeCreated,Id` and `(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime` | event times (6005 = start, 6006 = stop) and current uptime; shows typical daily PC hours (Q11) |
| P-R1 Reddit JSON (RECORDED 21-10-26) | `curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code} %{size_download}\n" "https://www.reddit.com/r/CryptoCurrency/search.json?q=solana&restrict_sr=1&sort=new&limit=1"` | RESULT: HTTP 403, block page about 190 KB: JSON is closed; not used |
| P-R2 coin feed depth (after W8c) | `python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --feed-depth` | entries returned, oldest and newest timestamps, per-day counts, exact/capped flags |
| P-R3 feed rate (run now, one request per minute) | `1..10 \| ForEach-Object { curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code}\n" "https://www.reddit.com/r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new"; Start-Sleep -Seconds 60 }` | ten status codes, expected all 200; any 429 or 403 recorded (stop the loop with Ctrl+C on the first one) |
| P-R4 multi-subreddit feed (run now) | `curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code} %{size_download}\n" "https://www.reddit.com/r/CryptoCurrency+CryptoMarkets+altcoin/search.rss?q=solana&restrict_sr=1&sort=new"` | 200 and size above 0 |
| P-R5 set vs site-wide (after W8c) | `python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --compare-scope` | entry counts for the subreddit set vs site-wide feed, same hour |
| P-R6 feed depth (run now, three requests one minute apart) | `$ua="attention-probe/0.1"; foreach ($u in @("https://www.reddit.com/r/CryptoCurrency/new/.rss","https://www.reddit.com/r/CryptoCurrency/new/.rss?limit=100","https://www.reddit.com/r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new&limit=100")) { $x=[xml](curl.exe -s -A $ua $u); "{0} entries, newest {1}, oldest {2}" -f $x.feed.entry.Count, $x.feed.entry[0].updated, $x.feed.entry[-1].updated; Start-Sleep -Seconds 60 }` | three lines with entry count and newest and oldest `updated` timestamps; shows the count with and without `limit=100` and how many hours one response reaches (if a response is an HTML block page the line is empty or an error: record that) |

## Annex H: Proposed PLAN slices (amended T131; detail in the PLAN file)

Model rule: code execution = opus, docs/vetting = sonnet. USD are planner-style estimates, UNVERIFIED. Build order: Reddit first (W8b, W8c need no wait for W8a), X after W8a and the owner probes P-X1..P-X7.

| Order | Slice | Content | Tier | Model / effort | USD |
|---|---|---|---|---|---|
| 1 | W8a | Vet API Anything per Annex F (report only, no code), pin SHA, adapter interface decision; owner runs P-X1, P-X2; gates X (W8d) only, not Reddit | docs + RT2 | sonnet, medium | 2-3 |
| 2 | W8b | Pure core (now includes config pace, daily read budget, adaptive budget): density formula, yesterday-only window rule, trickle scheduler core (spacing, caps, pause state), query/ambiguity/subreddit files, parsers, evidence sidecar, stores, guards, fakes, `probe_pc_sources` tool skeleton | RT2 | opus, medium | 5-7 |
| 3 | W8c | Reddit connector, plain HTTP on the public RSS feeds (no adapter, no API Anything, no login), honest user agent, feed parser and day counts (A.2), pause on 403/429/block page; probes P-R6, P-R3, P-R4 first (now), P-R2, P-R5 after; can start without waiting for W8a | RT2 + owner probes | opus, medium | 2-3 |
| 4 | W8e | Worker wiring: shell (if W8 absent), `fetch_side`, `_behind` start, trickle, pause persistence, flag | RT2 | opus, medium | 3-5 |
| 5 | W8f | Discovery wiring: `source_impl`, Sources reasons, backfilled flag in point-in-time, X rotation mode (`x_discovery_mode`, latest 3 stored values, rotation lag and history gate) | RT2 | opus, medium | 3-4 |
| 6 | W8g | Web: Sources/updating-data text for reasons | RT3 | opus, low | 1-2 |
| 7 | W8d | X connector via adapter after owner probes P-X1..P-X7 and the Q10 decision (budget spend, sample N 40, rotation hook): login command, hidden run, search windows, canary, breaker | RT2 + owner probes | opus, high | 5-7 |
| 8 | W8h | Owner guide + probe closeout, go/no-go | docs | sonnet, low | 1 |

Reddit can go live before X exists. If W8e lands before W8c, the worker idles (no source).

## Annex I: Change log

| Date | Task | Change |
|---|---|---|
| 21-10-26 | T126 | first SPEC (metrics, flow, failure handling, probes, slices) |
| 21-10-26 | T131 | Locked pacing rules; Q2/Q3/Q4/Q7 answered; AC1/AC8/AC10 reworded; AC19, AC20 added |
| 21-10-26 | T133 | config pace, daily read budget, sample N 40, adaptive budget, throwaway account, option D; AC21, AC22; Q10-Q12 raised |
| 21-10-26 | T135 | owner answers Q10 (rotation mode), Q11 (PC 1-3 h/day), Q12 (Reddit unchanged), delay confirmed; AC23, AC24; Q13, Q14 raised |
| 21-10-26 | T136 | owner approval recorded (SPEC locked); Q13 and Q14 answered yes; no requirement text changed beyond marking them locked |
| 21-10-26 | T138 | Reddit access moved to the public RSS feeds over plain HTTP on owner probe evidence (JSON 403); A.2 rewritten; Reddit pace 60-120 s, 150 per day; W8c no longer depends on W8a or API Anything; AC2, AC8, AC9, AC17 reworded, AC25 added; Q15, Q16 raised; Q12 superseded in part |
