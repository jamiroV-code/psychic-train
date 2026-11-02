---
name: spec:collector-identity-pool
description: "Daily data on every eligible coin from X and Reddit: a pool of throwaway accounts with their own browser sessions, automatic cookie refresh, per-account caps with sequential handoff, optional fixed per-account IPs, and a measured set of anti-ban measures."
date: 02-11-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Collector identity pool: daily data on all eligible coins (02-11-26)

Status: SPEC for owner review. Nothing here is built. All numbers come from measurements and arithmetic done on 01-11-26 and 02-11-26 (see Background). The local Camoufox lifecycle test was still running when this was written; its results will feed the open questions below.

## Summary

Today the X collector reads about 19 coins a day from two throwaway accounts whose login cookies the owner refreshes by hand, and the Reddit collector depends on public feeds that Reddit is reportedly ending. The owner wants a data source that covers **every eligible coin every day**. This SPEC describes a pool of throwaway accounts, each with its own stable browser identity and its own daily reading cap. Accounts take turns, cookies refresh without the owner, a lost account costs no data, and the status box shows each account's health. Anti-ban measures are in scope as switchable, measured features, because the owner accepts the risk on throwaway accounts. Reddit is a separate, later method with its own completeness rules. No money is spent; accounts use the home connection unless the owner later supplies a proxy.

## User Stories / Jobs To Be Done

- US1. As the owner, I want every eligible coin to get a daily X value, so that attention data is complete and comparable across coins.
- US2. As the owner, I want account login cookies to refresh without me, so that the collector keeps running while I do other things.
- US3. As the owner, I want each account to read only up to its own limit and then hand over to the next account, so that no single account looks busier than the others.
- US4. As the owner, I want to add accounts by changing settings, so that coverage grows with the number of coins.
- US5. As the owner, I want a lost or banned account to cost me nothing but that account, so that a ban never leaves a hole in the day.
- US6. As the owner, I want each account to look like one steady person, so that bans are as rare as practical.
- US7. As the owner, I want to see at a glance which accounts are healthy, so that I can act before data is lost.
- US8. As the owner, I want Reddit data to keep coming after its public feeds end, without mixing two different ways of counting.
- US9. As the owner, I want extra tools such as a proxy gateway used only when they are really needed, so that the setup stays simple.

## What The User Wants (Behavioral Outcomes)

1. Every account has its own saved browser session and its own fixed browser identity, the same on every start.
2. When an account's login cookies near expiry, the system renews them from that account's saved session without the owner. If renewal fails, that account is paused with a plain reason and the others carry on.
3. Each account has its own daily reading limit. When an account reaches it, or is locked or paused, the next coin-day goes to the next account. A coin-day is read by one account from start to finish, never split.
4. Accounts take turns, one at a time. A global daily ceiling stays on top of all accounts.
5. Adding an account is a settings change (name, profile, limit, optional fixed IP). The status box warns when the active accounts cannot finish the day's universe.
6. A new account rests for a set period of normal use by the owner before the collector may use it.
7. Only one browser runs at a time, and a browser is not started when the PC is short of memory.
8. Every account has its own fixed IP, taken from a list of proxies the owner supplies, and its own fixed user agent, the same on every start. The reader of each account uses only its own IP and identity. If an account's IP stops working, the account moves to the next healthy IP in the list after a cooldown and the owner is told. It never silently falls back to the home connection. With no proxy list configured, the home connection is used and the status box says so.
9. When a fixed IP is used, the account's language and time-zone headers and its user agent agree with that IP's region. A mismatch stops that account from starting.
10. The reader can present a browser-like connection style instead of the plain script style. It is switched on for the whole collector only after the installed files are verified, and the choice between the two styles is made from a recorded comparison on real accounts.
11. Every anti-ban measure (pinned identity, fixed IP, calm pacing, quiet hours, connection style) can be switched on or off, each with a health measure. Measures that show no benefit are removed.
12. The status box shows, per account: state, reads used against its limit, last login, cookie age, any challenge or shrinking-result signal, and proxy health.
13. A daily report states how many eligible coins have a stored value, how many are exact, estimated or missing, and why. Missing is never shown as zero.
14. Reddit browser reading, when built, is its own method with its own completeness rules and a hard daily request ceiling. It is never combined with values from the old feed method.
15. A proxy-gateway program (V2Ray) is optional and off by default. It is used only when the criteria in Constraints are met.
16. Cookies, profiles and proxy login details live outside the repository with restricted access and never appear in logs, the status box or reports.
17. Each account has its own daily rhythm: its own reading windows and quiet hours, so accounts do not all read at the same times.
18. A real session is not only searches: the reader also makes a small share of ordinary requests (a timeline, a profile, a single post), within the same budget and never counted as coin data.
19. Query shape varies a little (page size, pause lengths, order of coins) so the pattern is not a fixed script.
20. When an account shows a warning sign (content stripped from results, shrinking results, a login challenge, rate-limit counters near zero) it cools down automatically and its coin-days move to the other accounts, with a note in the status box.
21. A new account's daily reads start low and rise step by step toward its limit (a warm-up ladder), after its rest week.
22. Before a proxy is used for an account it passes an admission check: HTTPS works with a verified certificate and no proxy certificate is accepted, the exit address matches what was assigned and differs from the other accounts', the exit address is not on a cached blocklist and passes a free reputation check where one is configured, nothing is injected into a plain test page. A proxy that fails is quarantined; a replacement is recorded as an IP change.

## Flow / State Diagram

```text
 [new account added] --> [rest period: owner uses it by hand, collector off]
                                   |
                          [owner marks it ready]
                                   v
 [account active] --> [turn comes] --> {under its daily limit and healthy?}
        ^                                   | yes                    | no
        |                                   v                        v
        |                        [read one coin-day]        [skip, next account]
        |                                   |
        |                         {cookies near expiry?} --yes--> [renew from saved session]
        |                                   |                          | fails
        |                                   no                         v
        |                                   |                  [account paused: reason shown]
        |                                   v                          |
        +-------------------------- [next coin-day] <--- [coin-day retried by another account]

 [any account lost] --> [its coin-day goes to another account] --> [owner alerted in status box]
 [fixed IP fails]   --> [cooldown] --> [next healthy IP] --> [alert]  (never silent home-IP fallback)
```

## Acceptance Criteria (Testable Outcomes)

- AC1. Each account keeps one browser identity across restarts; two accounts never share an identity, cookies or storage.
  proven by: identity-stable-across-restart scenario; two-account-isolation scenario.
  strategy: Fully-Automated
- AC2. A near-expiry cookie renews from the account's saved session with no owner action and the reader uses the new cookie on the next read; no cookie value appears in any log or file in the repository.
  proven by: cookie-renewal-handoff scenario with a fake session; secret-scan-of-logs scenario.
  strategy: Fully-Automated
- AC3. A failed renewal or login challenge pauses only that account with a reason code and shows it in the status box; the other accounts keep reading; there is no retry storm.
  proven by: account-paused-others-continue scenario; retry-backoff scenario.
  strategy: Fully-Automated
- AC4. An account at its own limit is skipped; no coin-day is split between accounts; the total never exceeds the global ceiling.
  proven by: per-account-cap-handoff scenario; no-split-coin-day scenario; global-ceiling scenario.
  strategy: Fully-Automated
- AC5. Adding an account needs only a settings change; with too few accounts for the universe the status box warns, naming the shortfall.
  proven by: add-account-by-settings scenario; sizing-warning scenario.
  strategy: Fully-Automated
- AC6. When an account is locked, logged out or banned mid-day, its unfinished coin-day is read by another account and counted once.
  proven by: account-loss-failover scenario; no-double-count scenario.
  strategy: Fully-Automated
- AC7. A new account is not used by the collector before its rest period has passed and the owner has marked it ready.
  proven by: rest-period-gate scenario.
  strategy: Fully-Automated
- AC8. At most one browser runs at a time, and a browser start is refused when free memory is below the configured floor.
  proven by: single-browser scenario; low-memory-refusal scenario.
  strategy: Fully-Automated
- AC9. With fixed IPs configured, each account keeps its own; a proxy must pass the admission check before use; a dead or failing IP moves the account to the next admitted one after the cooldown with an alert and an IP-change record; it never silently uses the home connection.
  proven by: sticky-ip scenario; proxy-admission-check scenario; dead-ip-failover scenario; no-silent-home-fallback scenario.
  strategy: Fully-Automated
- AC10. With a fixed IP, the account's language and time-zone headers and its user agent agree with that IP's region; a mismatch blocks that account's start with a reason.
  proven by: identity-ip-coherence scenario.
  strategy: Fully-Automated
- AC11. The comparison of the standard client and the browser-imitating backend runs on real accounts, records challenge and result counts, and the chosen default is written down with its evidence.
  proven by: transport-comparison probe output.
  strategy: Agent-Probe (justified: needs live accounts and the owner's PC; no automatable substitute)
- AC12. Every anti-ban measure (daily rhythm, mixed traffic, query variety, adaptive cool-down, warm-up ladder, fixed IP, connection style) has an on/off setting and a health measure; the adaptive cool-down moves a warned account's coin-days to the others; with all optional measures off the collector runs with the current behaviour.
  proven by: measure-switch scenario; warning-cooldown-handoff scenario; warm-up-ladder scenario; all-off-baseline scenario.
  strategy: Fully-Automated
- AC13. The status box shows per account: state, reads against limit, last login, cookie age, challenge or shrinkage signals and proxy health; unknown values read "unknown", never healthy or zero.
  proven by: status-box-states scenario; unknown-never-ok scenario.
  strategy: Fully-Automated
- AC14. The daily report lists eligible, stored, exact, estimated and missing coins with reasons; missing never appears as zero; 100% stored coverage is reported only when every eligible coin has a stored value.
  proven by: coverage-report scenario; missing-not-zero scenario.
  strategy: Fully-Automated
- AC15. The Reddit browser method uses its own method name, its own completeness rules and a hard daily request ceiling, and never merges with feed-method values.
  proven by: reddit-method-separation scenario; request-ceiling scenario.
  strategy: Fully-Automated
- AC16. The proxy gateway is off by default; the collector runs without it; enabling it needs an explicit setting.
  proven by: gateway-off-by-default scenario; run-without-gateway scenario.
  strategy: Fully-Automated
- AC17. Secrets (cookies, profiles, proxy logins) are stored outside the repository with restricted access and never appear in logs, reports or the status box.
  proven by: secrets-outside-repo guard scenario; log-scrub scenario.
  strategy: Fully-Automated
- AC18. Existing protections stay: global ceiling, daily canary, pause rules, exact versus estimated labelling, UTC-day completeness and first-write-wins history.
  proven by: existing collector regression suites unchanged and green.
  strategy: Fully-Automated

- AC19. Each account keeps one fixed user agent across restarts; two accounts never share both an IP and a user agent; the reader of an account sends only its own.
  proven by: user-agent-stable-across-restart scenario; no-shared-identity scenario.
  strategy: Fully-Automated
- AC20. The browser-like connection style is off until the installed files are verified; when on, every account's reads use it; the plain style stays available; the choice and its evidence are recorded.
  proven by: connection-style-switch scenario; unverified-install-refused scenario; comparison probe output.
  strategy: Hybrid (switch and refusal are automated; the comparison needs live accounts)

## Out Of Scope

- Creating accounts, buying accounts, or solving captchas by service; account creation stays manual with genuine throwaway accounts.
- Paying for proxies, VPNs or servers; free options only unless the owner changes this.
- Changing which coins are eligible, the daily value definition, or scoring and ranking.
- Using the owner's main or premium accounts.
- Redistributing the browser or any of its bundled files.
- Official paid data products and approval applications (a separate decision track).

## Constraints

- Owner decisions (02-11-26): personal use only; ban risk on throwaway accounts accepted; anti-ban measures (including fixed IPs and identity measures) are in scope but switchable and measured; no money spent; home Wi-Fi must not be disturbed; per-account daily limit decided after the lifecycle test; a new account rests one week; transports compared before one is chosen; free proxies are allowed only as an experiment on a disposable account first.
- Earlier locked rules that this SPEC changes, to be amended by the owner as a deliverable of the PLAN: the ban on any proxy variable in the X process (the environment guard refuses to start X with one), the rule that the browser-like connection style is only a Cloudflare fallback in a separate process, and the ban on detection-evasion measures. The owner's decision of 02-11-26 allows a fixed proxy and a fixed user agent per account and a browser-like connection style for all reads.
- Hardware: about 8 GiB of memory, shared with the live site and the collector. One browser at a time. Camoufox's own memory claim (about 200 MB) is unmeasured until the lifecycle test reports.
- Fonts bundled with the browser carry a non-commercial licence caveat; accepted for personal use, never redistributed.
- Camoufox is, by its own README, "under development" and "may not be suitable for stable production use"; it needs a pinned version and recorded file hashes.
- The daily reads use an HTTP reader, not the browser. The browser handles login and cookie renewal only unless the connection-style comparison says otherwise.
- Real limits seen on 31-10-26: X allows about 50 search requests per 15 minutes per account; the full universe needs about 146 requests a day. The binding limit today is our own 800-read daily budget, not X's.
- Reading all 72 X coins at the usual sample size takes about 2,920 reads a day (about 4,360 worst case); with a per-account limit of 800 that is about 4 accounts (6 worst case). This is arithmetic, not a measurement.
- A proxy-gateway program (V2Ray, use the maintained fork `v2fly/v2ray-core`, not the old `v2ray/v2ray-core`) may be enabled only if at least one of these holds, with measured evidence: (a) more accounts need distinct outbound routes than the built-in proxy list can manage, or (b) the only available routes are in its format. Otherwise it stays off.
- Source tools ruled out for this project, with reasons recorded: a hardware-ID spoofer (not used by these sites, needs a kernel driver on the live PC) and a source-address-spoofing tunnel (replies never return to a forged address; needs two servers and a host that allows spoofing).
- Reddit: its public feeds are reportedly ending on 13-11-26 (press reports; Reddit's own post could not be read) and public API access in March 2027 (Reddit's registration page). A Reddit browser reader is a later, separate method.
- All shared work happens in separate worktrees with separate caches and ports; the live API, site and collector are not restarted by tests.

## Build Order: build what the goal needs, and no more (owner instruction 02-11-26)

The big goal is daily data on every eligible coin. The owner's rules: be clever and build only what is needed to avoid account bans, and each account must have its own IP and identity. The acceptance criteria above are the full target. They are built in stages; the first two are fixed by the owner's decision, the later ones start only when their trigger is observed in real data.

| Stage | What is built | Why | Trigger |
|---|---|---|---|
| 0. Calm and per-account | Per-account daily limit, sequential handoff, rest period for new accounts, per-account status, loss failover, coverage report (AC4, AC5, AC6, AC7, AC12, AC13, AC14, AC18) | Behaviour is the strongest ban signal; most of the pool exists; it also measures how many accounts the universe needs | Always |
| 1. Identity per account | Fixed proxy per account with an admission check, health checks and failover, fixed user agent per account, browser-like connection style with a measured comparison, plus the switchable behaviour measures: daily rhythm, mixed traffic, query variety, adaptive cool-down, warm-up ladder (AC9, AC10, AC11, AC12, AC19, AC20) | Owner decision: each account must have its own IP and identity. This needs no browser: the reader of each account already accepts its own proxy and user agent, and the library has a browser-imitating backend | Owner decision 02-11-26 (built now, right after Stage 0) |
| 2. Cookie renewal | Automatic cookie renewal from a saved browser session (AC1, AC2, AC3, AC8, AC17) | The browser probe found Camoufox heavy (about 630 MB, slow start, unstable canvas fingerprint, hangs on a double-open); worth it for X only if cookies expire often. The browser it needs is also what Stage 4 uses | Cookies expire or force a login more than once every two weeks, or Stage 4 starts |
| 3. Proxy gateway | V2Ray gateway (AC16) | Only if the built-in proxy list cannot cope | Stage 1 shows the built-in list cannot manage the accounts' routes, with measured evidence |
| 4. Reddit browser method | Separate method with its own rules, using the same identity layer and a browser, one at a time (AC15) | Owner decision 02-11-26: no application for official Reddit access; the identity and evasion route is chosen, because the public feeds are reportedly ending about 13-11-26 | Owner decision made; built after Stage 1; needs its own design addendum (reader, paging, completeness rules) before the PLAN |

Rules for every stage: each measure has an on/off setting and a health measure; a measure that shows no benefit after a trial is removed; nothing in a later stage is built "just in case". The status box records the trigger signals (challenges, shrinking results, cookie age, limits hit, proxy health) so the next step is decided from data.

## Open Questions

Answered by the owner on 02-11-26:
- Q5: no application for official Reddit access; Reddit uses the identity and evasion route (Stage 4).
- Q2: accounts share the load evenly (least recently used).
- Q7: the proxy list lives in a private file outside the repository, one proxy per line; the owner supplies the list; credentials never enter the repository.
- Q8: the browser-like connection style becomes the default for all accounts if the recorded comparison shows no extra challenges.

Still open:
- Q9 (owner): the Reddit zero rule. Options are being written up: keep strict; allow a stored zero when the canary passed and the feed is short and the coin has some history; allow it for coins with no history too.
- Q1 (owner): the per-account daily limit. Default proposal 800 reads, chosen from the measured health signals after Part A has run.
- Q3 (owner): confirmed by the lifecycle test that only one browser fits at a time; relevant only if Stage 2 is triggered.
- Q4 (owner): which free proxy list, if any, goes into the disposable-account experiment.
- Q6 (research): the default connection style for daily reads, decided by the comparison and Q8's rule.

## Background / Research Findings

- Camoufox (https://github.com/daijro/camoufox): latest browser release v158.0.1-beta.41 (29-10-26); Python package 0.5.9. Persistent profiles keep cookies but do not by themselves pin the device identity. Its IP features change what a page can read (WebRTC address, location, time zone, language); they do not change the address traffic leaves from. Residential proxies are its own recommendation.
- Measured on 31-10-26 to 02-11-26: two accounts read 18 to 20 coin-days per 800-read budget; the day rollover, budget reset, canary and clean stop worked; a hard kill during a request is handled with a short wait, not a day lock.
- X's reader is twscrape (pinned commit); cookies are loaded by hand today. twscrape does not renew cookies itself, and its own login features were excluded by the safety review.
- Coverage arithmetic, current universe (75 placed coins; 72 eligible on X, 66 on Reddit): see the repository analysis dated 02-11-26. Stream and search values for Reddit are separate methods and never merge.
- Official access routes (read 02-11-26): X recent search and counts cover 7 days; X full-archive counts are priced per request and X's policy has a clause on measuring platform usage that needs written confirmation; Reddit's free API is approval-gated at 100 queries per minute per client. Distinct browser profiles do not create quotas on either site.
- Owner input, verbatim intent: "we will need as much accounts needed to reach all data we need everyday"; "we need max evasion to really avoid account ban as much possible"; "i won't spend money and all should work automatically without messing my home wifi"; "free public proxies is an option … use a fallback system … only if you have no better free option"; "yes spec it, only use if we really need it" (the proxy gateway).
