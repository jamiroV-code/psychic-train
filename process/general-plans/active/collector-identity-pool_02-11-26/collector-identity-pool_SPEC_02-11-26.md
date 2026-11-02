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

Part B status (02-11-26 revision): **PLANNED, VALIDATE v2 pending**, after BLOCKED validation. Part A is unchanged; B1 transport, B2 proxy admission/lifecycle and B3 measured behaviour are separately gated in the PLAN. This is not evidence of implemented identity or live Reddit availability.

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
8. Every proxy-enabled account has its own fixed IP from an owner-supplied private one-proxy-per-line list and a separate opaque-ID assignment file, plus its own literal wire-verified user agent. A failed proxy is quarantined; replacement must be admitted, distinct and coherent, with alert and opaque change record. Proxy-required paths (including bootstrap, redirects and fallback child) never go direct. With proxy mode explicitly disabled and no files configured, direct connection is reported; empty or broken configuration is not direct mode.
9. Expected region, language and IANA timezone are explicitly owner-declared and checked against admission metadata and actual supported outgoing fields; unknown/mismatched required region blocks startup. A timezone is not an invented HTTP header and a UA does not prove geography.
10. Browser-like transport is collector-wide, selected and verified before any client creation, with restart required to change mode. The installed-distribution check compares name/version, wheel tag, platform and recorded lock/allowlist hash; it does not hash installed binaries. A separate recorded real-account comparison determines the default.
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
- AC9. Proxy-required accounts retain a distinct admitted route and never go direct on missing, empty, unavailable or quarantined assignment, including GraphQL, bootstrap, redirects and fallback child. Sequential bounded admission checks verified HTTPS, expected unique exit, fresh blocklists, configured reputation provider and plain-page integrity; unresolved required checks fail closed. Quarantine/replacement is atomic at a unit boundary with alert, wake-up, same-identity child and canary rerun after change; spent reads remain charged.
  proven by: sticky-ip/admission-cache-provider-timeout scenarios; loopback-no-direct scenario; quarantine-migration-rollback scenario; identity-change-canary-handoff scenario.
  strategy: Hybrid (offline fake clients/loopback prove contracts; real route/provider and host ACL properties need separately approved evidence)
- AC10. Explicit region/language/timezone metadata and observed supported headers are coherent with the assigned exit; mismatched or unknown required region blocks that account with a reason. Evidence distinguishes owner configuration, provider observations and actual wire fields, without claiming UA geography or a timezone HTTP header.
  proven by: identity-ip-coherence scenario; outgoing-field/provenance scenario.
  strategy: Hybrid (automated contract tests; live geolocation accuracy is not established by fixtures)
- AC11. The comparison of the standard client and the browser-imitating backend runs on real accounts, records challenge and result counts, and the chosen default is written down with its evidence.
  proven by: transport-comparison probe output.
  strategy: Agent-Probe (justified: needs live accounts and the owner's PC; no automatable substitute)
- AC12. Pinned identity, route, connection style and all five behaviour measures each have an independent on/off switch and health signal. Quiet hours affect `_next_due`; mixed traffic uses only approved `user_by_login`, `tweet_details`, `user_tweets` calls with account/global charge units and no coin writes; bounded page/pause/order variation preserves UTC/filter semantics; cooldown consumes authoritative stripped-page strikes and explicit shrink/challenge/rate signals without proxy rotation; warm-up follows rest and ready eligibility. With all optional measures off, Part A behaviour remains unchanged.
  proven by: each-measure-independent-switch-and-health scenario; quiet-midnight-DST-next-due scenario; mixed-allowlist-budget scenario; variation-bounds scenario; warning-cooldown-handoff scenario; post-ready-warmup-migration scenario; all-off-baseline scenario.
  strategy: Fully-Automated
- AC13. The status box shows per account: state, reads against limit, last login, cookie age, challenge or shrinkage signals and proxy health; unknown values read "unknown", never healthy or zero.
  proven by: status-box-states scenario; unknown-never-ok scenario.
  strategy: Fully-Automated
- AC14. The daily report lists eligible, stored, exact, estimated and missing coins with reasons; missing never appears as zero; 100% stored coverage is reported only when every eligible coin has a stored value.
  proven by: coverage-report scenario; missing-not-zero scenario.
  strategy: Fully-Automated
- AC15. Reddit browser observation has its own method/completeness rules and hard request ceiling, never merges feed values, and labels the explicitly defined visible surface. A justified daily value requires validated fields and successful traversal; short DOM or possible cap is not completeness, and blocked/truncated data is not zero. “66 coins complete” is not every Reddit mention.
  proven by: reddit-method-separation scenario; request-ceiling scenario; day-boundary-versus-cap scenario; per-lane-canary-and-zero scenario (Part C research must define these before PLAN).
  strategy: Fully-Automated
- AC16. The proxy gateway is off by default; the collector runs without it; enabling it needs an explicit setting.
  proven by: gateway-off-by-default scenario; run-without-gateway scenario.
  strategy: Fully-Automated
- AC17. Cookies, profiles and proxy credentials stay outside the repo under verified restricted access. Credentials are absent from account DB proxy fields, pool state, status, logs including upstream warnings, reports, exception chains, child argv/environment and captured output. Private assignment contains opaque IDs, never URLs; unverified ACLs refuse proxy mode.
  proven by: secrets-outside-repo/ACL-refusal scenario; upstream-log-exception-child-output marker scenarios; safe-state-and-assignment scenario.
  strategy: Fully-Automated
- AC18. Existing protections stay: global ceiling, daily canary, pause rules, exact versus estimated labelling, UTC-day completeness and first-write-wins history.
  proven by: existing collector regression suites unchanged and green.
  strategy: Fully-Automated

- AC19. Enabled identity mode gives each account one fixed outgoing identity across restarts and refresh, on GraphQL and transaction-ID bootstrap, including redirects and the fallback child, proven on the wire in both backends: with the plain backend the identity is the account's literal user agent; with the browser-like backend it is the account's fixed impersonation target (browser family and exact version), and the user agent sent comes from that target (measured 02-11-26: the browser-like backend ignores a supplied user agent). Two enabled accounts never share both route and observed (IP, user agent); the bootstrap cache is identity-scoped and invalidated on change. A maintained wrapper applies the target to both client paths; unsupported pinned-library hooks block startup. This proves enumerated request identity, not complete browser fingerprint stability or ban prevention.
  proven by: wire-identity scenario on loopback for both backends and both client paths; restart-and-refresh scenario; bootstrap-cache-scope scenario; fallback-child-identity scenario; no-shared-identity scenario.
  strategy: Fully-Automated
- AC20. Collector-wide backend selection and installed-distribution verification precede every client creation; unverified curl refuses startup. No installed-binary hash claim is made. Plain remains available with its existing bounded daily curl fallback; normal curl has no curl-on-curl fallback. Real-account comparison records challenges, counts and canary agreement; curl becomes default if no extra challenges, as the owner decided.
  proven by: pre-client-mode-verification scenario; launcher-and-backend-retry scenario; comparison probe output.
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
- Dated superseding decision (02-11-26), deliverable of PLAN B1/B2: amend canonical collector SPEC rules 5, 8, 17–20, AC41, AC46, AC53, AC55, proxy/evasion non-goals and Q24/Q30 while preserving historical text. Allow only deliberate per-account private routing/identity and verified process-lifetime normal curl, narrow B3 approved-call/scheduler exceptions, and lazy reader networking; retain the global proxy-environment ban, pure cores, login/debug/telemetry protections, global ceiling and completeness rules. B1 owns transport/bootstrap/launcher wording; B2 owns admission, secrets, exact-key state/rollback and `sources[xsearch].health.accounts` status. The PLAN includes the exact superseding contract and deliberate guard/test amendment checklist; these canonical amendments are not claimed applied here.
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
| 1. Identity per account | B1 maintained transport adapter/wire feasibility; B2 private fixed proxies/admission/quarantine; B3 switchable measured behaviour (AC9–AC13, AC17–AC20) | The library has account-level identity fields; the application wrapper must deliberately provision and reconcile them. Curl strips supplied UA and bootstrap creates its own client/cache, so wire identity must be established, not inferred from DB values. No browser is needed for this stage. | Owner decision 02-11-26; after Stage 0, VALIDATE v2 and explicit execution approval; each part has its own gates |
| 2. Cookie renewal | Automatic cookie renewal from a saved browser session (AC1, AC2, AC3, AC8, AC17) | The browser probe found Camoufox heavy (about 630 MB, slow start, unstable canvas fingerprint, hangs on a double-open); worth it for X only if cookies expire often. The browser it needs is also what Stage 4 uses | Cookies expire or force a login more than once every two weeks, or Stage 4 starts |
| 3. Proxy gateway | V2Ray gateway (AC16) | Only if the built-in proxy list cannot cope | Stage 1 shows the built-in list cannot manage the accounts' routes, with measured evidence |
| 4. Reddit browser method | Separate method with its own rules, using the same identity layer and a browser, one at a time (AC15) | Owner decision 02-11-26: no application for official Reddit access; the identity and evasion route is chosen, because the public feeds are reportedly ending about 13-11-26 | Owner decision made; built after Stage 1; needs its own design addendum (reader, paging, completeness rules) before the PLAN |

Rules for every stage: each measure has an on/off setting and a health measure; a measure that shows no benefit after a trial is removed; nothing in a later stage is built "just in case". The status box records the trigger signals (challenges, shrinking results, cookie age, limits hit, proxy health) so the next step is decided from data.

## Open Questions

Answered by the owner on 02-11-26:
- Q5: no application for official Reddit access; Reddit uses the identity and evasion route (Stage 4).
- Q9: Reddit zero rule: a zero may be stored when the canary passed, the search feed was clearly complete (short) and the coin has some history (option B of 02-11-26). To be applied to the existing feed method too, as its own small change.
- Q2: accounts share the load evenly (least recently used).
- Q7: the proxy list lives in a private file outside the repository, one proxy per line; the owner supplies the list; credentials never enter the repository.
- Q8: the browser-like connection style becomes the default for all accounts if the recorded comparison shows no extra challenges.

Still open:
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

## Part C research addendum (02-11-26; no execution PLAN)

The chosen Reddit route is identity/browser observation, not an official API application. Preferred design is one chronological collection per subreddit (posts and comments separately) for all 66 coins, followed by local matching/deduplication/author caps. Search is a separate labelled metric/cross-check, not invisible supplementation. “Complete daily data for 66 coins” means justified values from one explicitly defined, successfully traversed visible surface across the chosen 12 subreddits and UTC interval—not every mention ever created, private/removed content or guaranteed search recall. Access/field/traversal failures remain missing/partial.

Research reports conflict on logged-out Shreddit search and comments; HTTP 200 may be an empty app shell. June comment-fragment functionality is not November availability. Old Reddit is not a dependable logged-out fallback; mobile GraphQL observations do not prove web GraphQL. [Redlib October observations](https://github.com/redlib-org/redlib/issues/591), [search implementation](https://github.com/mvanhorn/last30days-skill/blob/main/skills/last30days/scripts/lib/reddit_search.py) and [selector reference](https://github.com/six-ddc/browser-cli/blob/main/skills/browser-cli/references/sites/reddit.com.md) are implementation/issue evidence, not service guarantees.

RSS ending **13-11-26** is reported by [MediaNama (01-10-26)](https://www.medianama.com/2026/10/223-reddit-rss-feeds-public-api-bots/) and [TechRepublic (02-10-26)](https://www.techrepublic.com/article/news-reddit-rss-public-api-shutdown/); direct primary announcement was not read. The [primary Reddit registration page](https://developers.reddit.com/app-registration) says removal for unregistered/unengaged access starts **12 January 2027**, and remaining public API access ends **March 2027** (no precise March day). These are distinct deadlines with different source quality.

Before a Part C PLAN: obtain logged-out/authenticated availability matrix per subreddit/lane/profile; stable post/comment IDs, full text, absolute timestamps and author/deletion evidence; chronological cursor traversal to UTC day start; explicit exhaustion versus cap/lazy-load/DOM loss; comments made on old posts; canary per lane; measured logical-load and actual HTTP fan-out budgets; and profile/route/background-network isolation. A short page or possible 1,000-item cap is not completeness. Existing feed rules/estimators cannot simply move to rendered pages.

Shared collection avoids 66 repeated searches: separate searches cost `66*12*kinds*pages+details+controls` logical loads, while shared feeds cost the sum of post/comment pages over subreddits/polls plus details/controls, independent of coin count. Actual asset/fragment/telemetry requests must also be measured. Camoufox's roughly 632 MB idle/0.69–0.92 GB peak, slow launch, changing canvas, hung duplicate-profile launch and observed background traffic mean single-browser/profile-lock-before-launch and bounded isolated lifecycle are evidence gates, not solved properties.

Open decisions: posts only versus posts+comments; chronological-visible versus search-index metric; authenticated fallback; per-subreddit versus combined scope; page/request/browser-time ceilings and day-close delay; missing-author/deleted treatment; browser zero/estimator evidence; archives as cross-check only and unresolved terms. Owner zero **option B** is recorded: passed canary + clearly complete short feed + some coin history. Current feed code instead uses canary plus trailing median <5; changing it is a separate explicit amendment, not implemented by these docs and not automatically sufficient for a browser lane.

Owner decisions retained: evasion/identity in scope, no money, private one-proxy-per-line list and separate assignments, public proxies only on a disposable account first, real-account style comparison then browser-like default if no extra challenges, independently switchable/measured behaviour, Reddit identity route/no API application, zero option B, even account load, one-week rest and only evidence-needed construction. The PLAN research addendum carries detailed findings and gates; no Part C implementation steps are authorized.
