---
slug: collector-identity-pool-reddit-research
date: 2026-11-06
type: REF
lane: read-only research (Part C input); no Part C PLAN, no execution authorized
author: agent://RedditResearch
---

# Reddit data routes after the 2026 lockdown: dates, surfaces, API, cookies, archives, ranked routes

Scope question (owner): daily mention counts of about 66 coins across about 12 subreddits, free, no official API application, one account per IP, home Wi-Fi untouched, accounts created by the owner.

This document is research only. No Reddit/X account was used, nothing was logged in, and no source file or plan was edited. Evidence classes:

- **PRIMARY**: Reddit-owned page read directly (Reddit Help Center article JSON, `developers.reddit.com`).
- **SECONDARY**: press or vendor writing about a Reddit post. Reddit's own `r/redditdev` and `r/modnews` posts could not be opened from this environment (Reddit answered the reader with "You've been blocked by network security"; this is itself observed evidence, see section 1).
- **CODE/ISSUE**: GitHub issue, PR or source of a project that talks to Reddit daily (Redlib and forks, Arctic Shift, agent-reach). These are the best public evidence of what Reddit serves right now.
- **OBSERVED**: I made the request myself on 2026-11-06 (times UTC).
- **INFERENCE**: my reasoning; not observed.

Vendor pages (bigideasdb.com, redditapis.com, think-pol.com, wappkit.com, ppc.land) sell Reddit access products. Their dated test tables are used as one-run observations only, never as policy statements.

## 0. Bottom line

1. **Dates are settled and all three numbers in the question are right, for different things.** RSS ends 2026-11-13; new API access requests ended 2026-10-31; removal of API access for unregistered/unengaged apps starts 2027-01-12; remaining public Data API access ends "March 2027" (no day given). Anonymous `.json` is not on that calendar at all: it was already switched off in stages (late May announced; hard blocks observed 2026-10-20 and 2026-10-28).
2. **Official free API route is closed for a new owner.** Self-service closed 2025-11-11; new requests closed 2026-10-31; the registration page only registers apps that already have API credentials. Even an existing key dies by March 2027. This matches the owner decision "no official application".
3. **Every anonymous web/JSON/RSS surface is either blocked, shut on a date, or degrading.** The one anonymous surface still working in public evidence on 2026-11-06 is the **Android app's GraphQL (`gql-fed.reddit.com`) with an app-only token**, used by the Redlib forks (public instance health badge "ok" at 2026-11-06). It is an impersonation of Reddit's own app, can be closed at any time, and has no subreddit-wide comment stream.
4. **Logged-in access is Reddit's declared future ("logged-in-only", Q3 2026 letter) and Reddit's declared enforcement point** ("by logging in, we get a lot more signal ... then we can block that traffic or enforce those accounts"). Cookie access works only if the TLS/HTTP fingerprint matches a real browser; listings and search were refused to cookie sessions in a November 2026 probe by the Redlib fork author, while a vendor reports real-Chrome logged-in listings/search working on 2026-10-18. The evidence conflicts and must be probed.
5. **The only free, live, sub-wide chronological source of posts and comments that needs no Reddit identity from us is Arctic Shift** (single-maintainer archive). OBSERVED live and current on 2026-11-06, with comment lag of 41-65 minutes median and up to 5.6 hours, completeness stated by its author as "90%+, ideally 95%" for comments after Reddit's October comment-ID change, no SLA, and an undecided future after March 2027.
6. **Recommended:** primary = Arctic Shift read with a 24-48 hour day-close delay and re-pull; fallback = owner-gated live collector (anonymous mobile GraphQL first, logged-in browser second) built only after the probes in section 9; cross-check/canary = ApeWisdom. Never merge the three; each is its own method (matches SPEC AC15/rule 14).

## 1. Observations made for this REF (2026-11-06)

| # | Request | Result | Meaning |
|---|---|---|---|
| O1 | `GET www.reddit.com/r/redditdev/comments/1wubcvf/.json` (anonymous, fetch tool) | HTTP 403 | Anonymous `.json` blocked from this egress. One IP, one run. |
| O2 | `GET www.reddit.com/r/redditdev/comments/...` HTML via reader proxy | body "You've been blocked by network security. To continue, log in to your Reddit account or use your developer token" | Block page names two ways in: login or "developer token". |
| O3 | `GET www.reddit.com/r/Bitcoin/new/.rss?limit=3` (one request) | HTTP 429 | RSS rate limits immediately from this egress. Not proof RSS is down everywhere. |
| O4 | `support.reddithelp.com/hc/en-us/articles/...` HTML | 403; the same articles via `/api/v2/help_center/en-us/articles/<id>.json` returned full text | Source of the PRIMARY quotes below. |
| O5 | Arctic Shift `status.arctic-shift.photon-reddit.com` | "Available"; rows New posts, New comments, API, Archiver, Clients, ID Notifier | Service up. |
| O6 | Arctic Shift `/api/posts/search?subreddit=CryptoCurrency&sort=desc&limit=2` | newest post created 2026-11-06 16:59:28Z, `retrieved_on` +9 s | Posts arrive near real time. |
| O7 | Arctic Shift `/api/comments/search?subreddit=Bitcoin&sort=desc&limit=1` at 17:57:13Z | newest comment created 17:09:33Z, `retrieved_on` 17:55:10Z | 45.6 min lag on that comment. |
| O8 | last 25 comments each, `created_utc` vs `retrieved_on` | r/CryptoCurrency: min 11 s, median 65 min, p90 201 min, max 337 min. r/Bitcoin: min 9 s, median 41 min, p90 59 min, max 82 min. `retrieved_on` values cluster (for example 1793982074, 1793983114, 1793984752, 1793986622) | Comment capture is batch/sweep based with late back-fill, n=25 per sub, one moment in time. |
| O9 | Arctic Shift comment aggregate r/Bitcoin, one UTC-ish day (2026-11-04): total 1115; `body=bitcoin` 136; `body=btc` 58. Local regex over the first 700 comments of the same day: bitcoin 12.6% (expect about 140), btc 5.6% (expect about 62) | Server keyword counts agree with a local whole-word regex within about 5% on this sample | Keyword aggregates are usable, with calibration. |
| O10 | Arctic Shift aggregates on busy subs | intermittent HTTP 422 with body `{"error":"Timeout. Maybe slow down a bit"}`; after a pause the same call returned 200 | Needs pacing and retry; README warns "very active users or subreddits have a high chance of timing out". |
| O11 | Aggregate day buckets | bucket labels `...T22:00:00Z` before 2026-10-25 and `...T23:00:00Z` after; date-only `after/before` gave one bucket per local day | INFERENCE: buckets and date-only bounds follow a Europe/Berlin-like server clock, not UTC. Must be verified before using a UTC-day metric (SPEC says UTC day). |
| O12 | ApeWisdom `all-crypto` | 99 tickers; BTC 116 mentions (24 h), ETH 20 | Far below the 136 comments/day mentioning "bitcoin" in r/Bitcoin alone (O9): different definition, see section 8. |

## 2. Q1: what exactly is shutting down, and when (PRIMARY where marked)

| Item | Date | Evidence |
|---|---|---|
| Self-service Data API closed; new access needs approval; `prefs/apps` stops issuing client ID/secret | 2025-11-11 | CODE/ISSUE: [jordanburke/reddit-mcp-server#29](https://github.com/jordanburke/reddit-mcp-server/issues/29) (2026-09-27) quotes the r/redditdev post "Starting today, self-service access to Reddit's public data API will be closed." and says current access was unaffected. A developer in the 2026-09-30 thread says requests have been "rarely" accepted since 2025-11-11 (SECONDARY, [bigideasdb](https://bigideasdb.com/reddit-api-shutdown-2027), 2026-10-27). |
| Responsible Builder Policy: approval required before any API access; no masking; no multiple accounts/requests for one use | policy page updated 2026-10-05 | PRIMARY: [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) |
| Unauthenticated `.json` "shutting down"; "Logged-in and authenticated access won't be impacted"; Rule 8 rewritten | announced late May / June 2026 (post "Protecting communities from scrapers and platform abuse"); **no date given for the switch** | SECONDARY: [PPC Land 2026-10-04](https://ppc.land/reddit-to-halt-public-data-api-access-in-march-2027-as-14-000-apps-register), [THINKPOL 2026-07-05](https://think-pol.com/blogs/reddit-is-closing) quoting the post |
| Old Reddit requires login (rolled out "over the next month") | announced 2026-06-30; live July | SECONDARY: [Ars Technica 2026-06-30](https://arstechnica.com/gadgets/2026/06/reddit-will-require-you-to-log-in-to-use-old-reddit-com/). Boat-botany quote: "By logging in, we get a lot more signal that allows us to detect whether an account is breaking the rules, and then we can block that traffic or enforce those accounts." |
| Old Reddit further limited to moderators and logged-in users who used it in the previous 6 months | "in the next few months" (post 2026-09-30; window changed from 90 days to 6 months after publication) | SECONDARY: [TechCrunch 2026-09-30](https://techcrunch.com/2026/09/30/reddit-is-killing-rss-feeds-ending-public-api-access-because-of-ai-bots/), [Ars 2026-09](https://arstechnica.com/gadgets/2026/09/reddit-will-block-old-reddit-com-from-people-who-havent-used-it-in-6-months/). A newly created account has no history: INFERENCE (PPC Land notes the same) that it cannot qualify. |
| **New requests for public API access stop** | **2026-10-31** | PRIMARY: [Reddit Help changelog 2026-10-08](https://support.reddithelp.com/hc/en-us/articles/54353370049684-Changelog-October-8-2026) (read through the Help Center JSON API) |
| Migration progress update | 2026-11-10 | SECONDARY: PPC Land |
| **RSS support ends** | **2026-11-13**; "If you use RSS for feeds outside of a community you moderate, there is no replacement." | PRIMARY: same changelog; also TechCrunch/TNW/PPC Land |
| Bounty registration closes | 2026-11-30 | PRIMARY: [developers.reddit.com/app-registration](https://developers.reddit.com/app-registration) |
| **API access removal begins for apps and users that have not registered or responded** | **2027-01-12** | PRIMARY: registration page and changelog |
| Migration update | 2027-02-23 | SECONDARY: PPC Land |
| **Remaining public API access ends** | **"March 2027"**; no day given | PRIMARY: registration page and changelog. Exemptions only for partners with written agreements (admin quote via PPC Land). |
| Comment IDs become 13-character, non-monotonic | announced 2026-05-11, postponed, reminder 2026-09-15, rolled out early October, 100% by 2026-10-21 | SECONDARY: [redditapis.com 2026-10-24](https://www.redditapis.com/blogs/reddit-comment-ids-13-characters-2026) quoting the admin posts; CODE/ISSUE: [arctic_shift#53](https://github.com/ArthurHeitmann/arctic_shift/issues/53): "As of today all comments have the new ids" (2026-10-21). Consequence: ID-range scans are dead; use `created_utc`. |
| Logged-in-only Reddit: tests start in "select markets outside the U.S." in Q4 2026; front page and the page a search result points to stay open for now; "It also allows us to protect access to Reddit's extremely valuable corpus of data" | Q3 letter 2026-10-29 | PRIMARY-ish: [Q3-26 letter](https://investor.redditinc.com/files/doc_financials/2026/q3/v2/Q3-26-Shareholder-Letter.pdf) quoted in [redlib#609](https://github.com/redlib-org/redlib/issues/609); [BleepingComputer 2026-10-31](https://www.bleepingcomputer.com/news/security/reddit-to-lock-content-behind-logins-to-fight-scrapers/) |

**Observed block escalation (CODE/ISSUE):**

- 2026-10-20 ~18:40Z: `/r/<sub>/comments/...` JSON returns the HTML "blocked by network security" page for anonymous app tokens while listings still work ([redlib#591](https://github.com/redlib-org/redlib/issues/591)). Blocked paths listed by the investigator: `/r/<sub>/comments…`, `/comments/…`, `/api/info`, `/api/morechildren`, comments `.rss`; unaffected: listings, `about.json`, `/by_id/`, `/user/<name>/comments.json`. A `%2f` encoding workaround worked for about three days; the Nachtalb fork later removed it because "Reddit decodes the path before blocking it, so it only marked requests as coming from Redlib" ([FORK.md](https://raw.githubusercontent.com/Nachtalb/redlib/main/FORK.md)).
- 2026-10-28: "Since 2026-10-28 Reddit answers every anonymous JSON API request (listings, about, by_id, users, search) and /svc/shreddit/ with a 403 'blocked by network security' page" ([polak14/redlib commit 29f1835](https://github.com/polak14/redlib/commit/29f18352cf54be4ffe579f773552acd0c45cdd08)); "Redlib is currently unusable because Reddit is blocking anonymous JSON API requests" ([redlib#603](https://github.com/redlib-org/redlib/pull/603), 2026-10-29).
- 2026-11-05: upstream Redlib image does not work; the Nachtalb fork works with a session cookie plus GraphQL ([redlib#609](https://github.com/redlib-org/redlib/issues/609) comments 2026-11-05).

## 3. Q2: which surfaces are readable now

Reliability column: **G** works in the latest dated evidence, **Y** conditional/conflicting, **R** blocked, **?** unknown.

| Surface | Logged out | Logged in (cookie/session) | Evidence and date |
|---|---|---|---|
| `www/.../*.json` listings, search, about, by_id (anonymous OAuth or no token) | **R** since 2026-10-28 (comments since 2026-10-20) | see next row | polak14 commit; redlib#591, #603; O1; vendor test 2026-10-18 and 2026-10-24: 0 of 7 and 3 of 3 JSON requests failed, 189,908-byte block page ([bigideasdb](https://bigideasdb.com/how-to-scrape-reddit)) |
| Same `.json` with a `reddit_session` cookie on `www.reddit.com` via an emulated-browser HTTP client | n/a | **Y**: comments/user/by_id accepted; "Subreddit listings and search are refused to sessions on every fingerprint (probe, November 2026)" | Nachtalb `cookied_json.rs` source comment (read 2026-11-06) |
| Same with a real logged-in Chrome | n/a | **Y**: listing, search and thread JSON returned 200 on 2026-10-18 (vendor, n=1, one account, before the 2026-10-28 block) | [bigideasdb 2026-10-18](https://bigideasdb.com/how-to-scrape-reddit); unverified after 2026-10-28 |
| `oauth.reddit.com` with a signed-in bearer from the app | n/a | **Y**: a signed-in bearer made the blocked comments request work on 2026-10-20 | redlib#591 comment by zImPatrick (MITM of the app); status after 2026-10-28 unknown |
| Mobile app GraphQL `POST https://gql-fed.reddit.com/` with persisted-query hashes, app-only OAuth token (no account) | **G** (2026-10-23 to 2026-11-06): subreddit feeds, posts by ID, post comments (up to 200 per request, 10 levels), search tabs, about, user pages | not needed | Nachtalb `gql.rs`; polak14 commit; redlib#603; public instance health badge `https://r.naa.gg/healthz/reddit.json` = "ok" (OBSERVED 2026-11-06). Token budget "600 per token". Persisted hashes are copied from Android builds (2026.33-2026.42) and can break per release. |
| Shreddit fragments `/svc/shreddit/...` | **R** since 2026-10-28 (anonymous) | **?** | polak14 commit; scraped fallback returned 403 for some users already on 2026-10-23 (redlib#591) |
| New-Reddit HTML page, logged out | shell of about 8 KB, zero post links, HTTP 200; or about 357 KB client app shell with no embedded data | n/a | vendor test 2026-10-18; redlib#591 (cute-johnny, 2026-10-20) |
| Old Reddit HTML and `.json` | **R** (302 to login; 6-month activity rule coming) | **Y** only for accounts with 6 months of activity or moderators; old.reddit "load more" returned 403 on 2026-10-23 | vendor test; Ars; redditapis (moderator report) |
| RSS (`.rss`) | **Y** until 2026-11-13: subreddit/top listing 200 with post body (2026-10-18), search RSS 429 on first call, about 1 request/min measured; **O3: 429** here today | n/a | vendor test; jordanburke#29 ("About 1 request per minute. Titles, links and authors only"); O3 |
| Official `oauth.reddit.com` with a registered script app | n/a | **R for new owners**; **G** for pre-2025-11-11 apps until Jan/Mar 2027 | section 4 |
| `r/all.json` | 403 (retired) but `/r/all+.json` still served the same feed (as of the fork's note) | n/a | Nachtalb CONFIGURATION.md |

Other points that matter for counting:

- **There is no subreddit-wide chronological comment stream in the live surfaces seen so far.** Redlib's backend kinds are POST, COMMENTS (comments of one post), LISTING, ALL, SUBREDDIT, USER, SEARCH, WIKI, DUPLICATES. A live counter must either (a) open every post that is new or has new comments (the PLAN already notes opening only new posts misses comments on old posts), or (b) use search tabs (index recall unknown), or (c) probe whether a logged-in `/r/<sub>/comments.json` works (not documented anywhere I found; probe P3).
- Redlib's per-instance health and the many "currently working instances" lists degrade within days (redlib#604 list, "This didn't age well", 2026-10-29): treat every live surface as perishable.
- PRAW itself has no 2026 breakage reports I could find beyond "cannot create an app"; PRAW needs an approved app, so it is moot for a new owner.

## 4. Q3: official API, free tier, approval, registration page

PRIMARY facts ([Reddit Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki), updated 2026-11-03; [Developer Platform & Accessing Reddit Data](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data), updated 2026-11-03):

- Free access limit: **100 queries per minute per OAuth client ID**, averaged over a 10-minute window; chat limits 2,000 per recipient and 3,000 per day.
- "Clients must authenticate with a registered OAuth token. We can and will freely throttle or block unidentified Data API users." "Traffic not using OAuth or login credentials will be blocked."
- "If you're accessing Reddit from an IP address in a hosted service provider's netblock, you will be required to have a valid OAuth token or be logged in." (relevant to datacenter/free proxies, section 6).
- "You must remove any user content in your possession that has been deleted from Reddit"; recommended purge within 48 hours. Keeping only per-coin counts avoids holding deleted content.
- "To use Reddit's Data API for non-commercial purposes, you need to sign-up here [support form]." No instant self-service.
- Commercial: "any use of our services by a business or on behalf of a business or as part of a monetized product or service", including "Free product features available for upsell", "Search or website ads", "Publishing content from Reddit on monetized websites or apps with ads". Commercial needs permission and a contract. Whether a public coin-attention site counts is the owner's risk; I make no legal claim.
- Research through developer tools is declared a violation; only the Reddit for Researchers program (academic, non-commercial; vendor summary: BigQuery, five-year history with a six-month delay, university affiliation and ethics letter) qualifies.
- Responsible Builder Policy, "Other Prohibited Practices": "This extends to commercial and non-commercial mining, scraping, or using data for purposes like ads targeting or to train machine learning or AI models." Rule 8 ([Don't break the site](https://support.reddithelp.com/hc/en-us/articles/360043512931-Don-t-break-the-site), updated 2026-11-05) lists "Bypassing security, safety, or technical guardrails, including evading enforcement", "Scraping Reddit or its services without an authorized agreement", and "Creating accounts through automated or agentic means". The owner's evasion route is covered by the first two bullets; enforcement per the policy is token revocation and suspension of the account and "associated accounts, bots, domains or subreddits". Practical consequence: account and IP loss, not criminal exposure (INFERENCE; not legal advice). Reddit litigated against commercial-scale scrapers (SerpApi, Oxylabs, AWMProxy, Perplexity, 2025-10-22; Anthropic, 2025-06) per [PPC Land](https://ppc.land/reddit-to-halt-public-data-api-access-in-march-2027-as-14-000-apps-register).
- Current registration page text (PRIMARY, read 2026-11-06): "Starting January 12, 2027, we'll begin removing API access for apps and users that haven't registered or engaged with the Reddit Developer Platform Team. Remaining public API access will end in March 2027. To continue, you'll need the account information associated with your API app and a personal Reddit account you'd like to register your apps with. ... You'll need a human Reddit account to register." It is a registration form for **existing** apps. It does not create apps.
- Creating a new script app: reports from r/redditdev in 2026 (search-result snippets only; I could not open them): `prefs/apps` redirects to the Responsible Builder Policy, "Create app" silently fails, HTTP 500, "Already registered my app but still can't create an application - keeps showing policy page". [bigideasdb 2026-10-24](https://bigideasdb.com/how-to-get-reddit-api-key) reads 39 recent threads and finds the same pattern. With new requests closed on 2026-10-31 and the whole public API ending in March 2027, **a new personal read-only script app is not obtainable**, and one obtained before today would live at most four months.
- Devvit (the replacement for approved apps): JavaScript/TypeScript only, installed per subreddit by moderators, triggers fire only in installing subreddits; no site-wide read for an outside process. Not a counting route for 12 subreddits the owner does not moderate.

## 5. Q4: logged-in cookie access, HTTP vs browser, detection, fixed IP

Evidence on how Reddit's edge decides (CODE/ISSUE, dated):

1. **The decision is made at the edge by path and by client fingerprint before token scopes matter.** cute-johnny (redlib#591, 2026-10-20): same token, same IP, same second: `/r/politics/hot.json` 200, `/r/politics/comments/.../.json` 403; varying User-Agent, Authorization, Host, Referer and query strings changed nothing.
2. **A valid cookie is not enough; the TLS/HTTP stack must look like a real browser.** [Panniantong/agent-reach#642](https://github.com/Panniantong/agent-reach/issues/642) (2026-08-21 to 2026-10-23): same machine, same valid `reddit_session`, same URL `https://www.reddit.com/api/me.json?raw_json=1`: `urllib` 200; `curl`, `requests`, `httpx` 403. A second user: Python 3.12 + OpenSSL 3.0 403, Python 3.14 + OpenSSL 3.5 200. A third user shows anonymous requests get 403 in all clients, including with a Chrome User-Agent. Their conclusion: JA3/JA4-style fingerprint plus client library. Nachtalb's source comment says the same from the other side: the emulation sends "the TLS, HTTP/2 and default headers Reddit expects next to a session cookie, and a mismatch between them is what gets a cookie refused." Redirects must not be followed: an expired session is redirected to the login page.
3. **Fingerprint allow-lists churn.** The Nachtalb fork emulates a random browser from a fixed list "mostly versions Reddit serves anonymous JSON to", removes a blocked one for hours, and runs a Fingerprints workflow that asks Reddit about every emulable browser; zImPatrick (2026-10-29) reports "just switch to another TLS fingerprint, it'll work again".
4. **Session budgets and lifetime.** `reddit_session` "lasts about six months"; sessions have an `x-ratelimit-remaining`/`x-ratelimit-reset` budget (429 when spent; the code rests a session up to 10 minutes) and sessions count as twice as expensive as anonymous calls. The fork's own instruction: "Use a throwaway account ... Reddit may ban it." A vendor FAQ says throwaway accounts used for high-volume or automated access "get flagged quickly" (low quality, unverified).
5. **Cookies are not rotated by Reddit for free.** A single `reddit_session` copied from DevTools is HttpOnly; copying it from the Network tab is the documented manual step ([cookie_setup.md](https://github.com/laokaoya/reddit_scrape_2026_skill/blob/main/cookie_setup.md): "Session cookies expire after a few days to a couple of weeks", which conflicts with the Redlib six-month figure; treat lifetime as unmeasured).

Real browser vs HTTP client:

| Factor | HTTP client with browser emulation (curl_cffi/wreq/urllib-class) | Real browser (Camoufox/Chrome) |
|---|---|---|
| Cost per page | tens of KB, milliseconds | PLAN research: about 632 MB idle, 0.69-0.92 GB peak, 13.4-33.3 s typical launch |
| Fingerprint risk | must keep TLS, HTTP/2 settings, header order and cookie in one consistent identity; stack updates can silently break (agent-reach: Python/OpenSSL version flipped 403 to 200) | genuine stack; but Camoufox "regenerates seeds per launch" so a returning login sees a changed device; open issue [daijro/camoufox#442](https://github.com/daijro/camoufox/issues/442) (per [scalebrowser 2026-09-25](https://scalebrowser.net/blog/camoufox)) |
| Maintenance | Camoufox itself is maintained: Firefox 158 betas 2026-10-19 and 2026-11-01, v0.5.9b6 2026-10-29 ([releases](https://github.com/daijro/camoufox/releases)) | same |
| Surfaces reachable | JSON/GraphQL paths only | everything the user sees, including lazy fragments; but logged-out new-Reddit HTML is an empty shell and `/svc/shreddit/` is blocked to anonymous clients, so a browser must be logged in or fall back to GraphQL calls it makes itself |
| Detection signals named in evidence | path rule at the edge; TLS fingerprint; client library; request budget; expired-session redirect; IP class (below) | account behavior signal after login (Reddit's stated reason for login walls); device identity drift; headless markers (INFERENCE, not Reddit-confirmed) |
| Chronological completeness | needs endpoint knowledge; listing/search refused to cookie sessions on emulated fingerprints per the November probe | scroll depth, lazy-load failure and "short DOM" ambiguity per PLAN gates; old.reddit not available to young accounts |

**Per-account fixed IP implications:**

- Reddit's own help text treats hosting-provider IP ranges as requiring OAuth or login; free public proxies are datacenter or residential-abused ranges (INFERENCE), so they sit in the worst reputation class even when the account is valid. A vendor test of an IP change did not change a logged-out 403 ("the rule appears to apply to the request type, not the address", [bigideasdb](https://bigideasdb.com/reddit-json-403-forbidden), one report), so for anonymous paths the IP is not the main lever; for logged-in paths IP/account consistency is the lever.
- The Responsible Builder Policy prohibits "registering multiple accounts or submitting multiple requests for the same use case"; Rule 8 prohibits evading enforcement. A pool of throwaway accounts reading the same subreddits is the pattern those lines describe. Redlib deploys "several sessions rotating" from a single server IP, and reports bans as an accepted cost.
- One-account-one-IP is consistent with the owner decision and costs only proxy lifetime: a dead free proxy must not cause an account to appear from another IP mid-session (existing B2 admission rules already require this; no change).
- The anonymous GraphQL route has no account at all; its only identity is an app token (loid) plus IP, so one-account-one-IP does not apply, but per-IP request budgets do ("600 per token").

## 6. Q5: archives and Pushshift successors

| Source | Status on 2026-11-06 | Evidence | Use |
|---|---|---|---|
| **Arctic Shift API** (`arctic-shift.photon-reddit.com`) | Up and current (O5-O8). Posts near real time; comments sweep-based, median 41-65 min, tail 5.6 h; aggregate endpoint gives per-day/hour counts with keyword filters; "No uptime or performance guarantees"; keyword search needs a `subreddit`/`author`/`link_id` and busy subs time out | O1-O11; [API README](https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md) | Primary candidate. Author on completeness after the ID change: "In terms of comments completeness it will be 90%+ complete, ideally 95%" (2026-10-02); "from now on comment data will not be 100% complete" (2026-10-17) ([#53](https://github.com/ArthurHeitmann/arctic_shift/issues/53)). On the post-March-2027 future: "Not sure yet what exactly will happen." ([#76](https://github.com/ArthurHeitmann/arctic_shift/issues/76), 2026-10-09) |
| **Arctic Shift monthly dumps** | Monthly zst torrents on Academic Torrents; 2026-09 released 2026-10-11, 2026-08 on 2026-09-12; so October is expected about 2026-11-10 to 11-12 (INFERENCE from cadence) | [releases feed](https://github.com/ArthurHeitmann/arctic_shift/releases), [download_links.md](https://github.com/ArthurHeitmann/arctic_shift/blob/master/download_links.md) | Ground truth to reconcile API counts, 10-40 day lag. Seeders: one user reported zero seeders on the 2005-2025 aggregate; the author seeds monthly files from 2024-04. |
| Academic Torrents reddit dumps (Watchful1 aggregates) | Taken down on Reddit's request 2026-07-23 ([SciOp record](https://sciop.net/datasets/reddit); [arctic_shift#42](https://github.com/ArthurHeitmann/arctic_shift/issues/42) 2026-08-05) | CODE/ISSUE | History only. Reddit is actively pressuring dump hosting: a risk to the whole archive chain. |
| Hugging Face `open-index/arctic` Parquet | "2005-12 through 2026-02", last update 2026-08-07 | [ModelScope card](https://www.modelscope.cn/datasets/open-index/arctic) | Stale for daily use. |
| **PullPush** | `api.pullpush.io` returned Cloudflare 521 "Web server is down" in search-result snapshots dated 2026-11-04 (several queries, 03:25Z to 23:31Z). Vendor: ingestion stopped May 2025, newest content May 2025 when tested 2026-07-30, rate cap about 30/min, outages frequent | search snapshots; [THINKPOL 2026-08-19](https://think-pol.com/blogs/reddit-archive-api) | Not usable. |
| Pushshift | Moderator-verified only since 2023; "Pushshift has updated how they ingest data ... and will continue to work after this change" (admin, 2026-09-15, via redditapis) | THINKPOL; redditapis | Not usable without a verified moderator account. |
| THINKPOL and similar paid archives | EUR 0.15 per query down to EUR 0.03, EUR 2,000 monthly minimum at the starter tier | THINKPOL (vendor) | Violates "no money". |
| Reddit for Researchers | academic only, delayed | PRIMARY articles above | Not eligible. |

Dependency chain risk (INFERENCE): the archive needs an ingest path from Reddit; Arctic Shift's author already rewrote ingest once after the ID change ("I have ways to work around this change. It is not as fast or efficient as simple comment id scans, but it works", 2026-10-02) and has not said how March 2027 or the logged-in-only shift will be handled.

## 7. Ranked viable routes for daily mention counts (66 coins, about 12 subreddits)

Rank is for "most defensible complete count per UTC day for the least identity/ban risk", given the owner constraints. "Completeness" says what a reported count actually means.

| Rank | Route | Completeness limit (what a number means) | Main risks | Reddit identity needed |
|---|---|---|---|---|
| **1** | **Arctic Shift API** (posts + comments per subreddit, local matching or server keyword aggregates), reconciled monthly against the dump | "Items Arctic Shift captured and still holds", not "visible on Reddit now". Comments stated 90-95% complete after 2026-10-21; early reads under-count because of sweep lag (median 41-65 min, tail 5.6 h on 25-sample); possible removals-before-capture; deleted-later content may remain in the archive (Reddit policy says deleted content must not be used, so define the metric as at-capture and say so). Posts effectively complete near real time. | Single maintainer; no SLA; 422 timeouts on busy subs; day buckets in a non-UTC server zone (O11); March 2027 and Reddit takedown pressure unknown; unofficial reuse of scraped Reddit data. | **None from us** |
| **2** | **Own live collection over anonymous mobile GraphQL** (subreddit `new` feeds, `PostComments` for new/active threads, search tabs as canary) | Complete for the posts lane if the `new` feed can be traversed to day start. Comments only for threads we open: comments on old posts are missed unless threads are re-opened by activity (PLAN already states this); 200 comments per request, depth 10, "more" cursors; search recall unmeasured. | Impersonates Reddit's Android app (copied client id, persisted hashes, version spoof): a clear Rule 8 violation and the surface Reddit is most likely to close next; hashes drift per release; per-token 600 budget. Worked 2026-10-23 to 2026-11-06 in public forks. | App-only token, no account |
| **3** | **Logged-in real browser** (Camoufox/Chrome, one global browser, fixed profile and IP per account) reading new-Reddit `new` feeds and threads, or intercepting the page's own GraphQL | Best fidelity to "what a logged-in user sees"; same comment-lane problem as rank 2; short DOM/virtual-scroll ambiguity; session budgets. | Heaviest; fingerprint-per-launch drift; accounts are the enforcement target; old.reddit unavailable to new accounts; logged-in-only rollout may make this the only live route but also the most policed. | Throwaway accounts, one per IP |
| **4** | Logged-in cookie HTTP (browser-emulating client, `reddit_session`) on `.json`/GraphQL paths | Same lanes as rank 3 where accepted; listings and search reported refused to cookie sessions on emulated fingerprints (November probe); comments/user/by_id accepted | Fingerprint match required (urllib vs curl vs requests flipped results); session budget; account ban. B2's transport work applies here. | Throwaway accounts |
| 5 | Search-based per-coin queries (GraphQL search tabs or logged-in search) | Cost `66*K*P` (combined scope) or `792*K*P` (per subreddit) logical loads per day from the PLAN; rolling windows, not UTC days; index recall unknown; never equal to a traversal | Rate budget; ticker collisions | as above |
| 6 | **ApeWisdom API** (free, `https://apewisdom.io/api/v1.0/filter/{filter}`) | Rolling 24 h only, no history; scans 15 subs twice an hour; counts a ticker once per post/comment and only uppercase or `$`-prefixed tickers; only tickers listed on its own market-cap site; O12 shows mentions of BTC 116 vs 136 comments mentioning "bitcoin" in a single subreddit | Different definition; depends on its own Reddit access; can vanish | None |
| 7 | Monthly dumps | History and reconciliation only | Hosting takedown, lag | None |

Not viable now: anonymous `.json`/Shreddit fragments (403), RSS (ends 2026-11-13; 429 observed), official API (closed to new owners; ends March 2027), PullPush, Pushshift, Devvit, Reddit for Researchers, paid archives and vendors (no money).

## 8. Recommendation and design consequences

**Primary: rank 1.** It is the only free source with a sub-wide chronological comment lane and zero Reddit identity exposure; the account/IP machinery from B1/B2 stays reserved for X and for the live fallback. Define the Reddit metric as "mentions captured by the archive for UTC day D in subreddits S, finalised after day-close delay". Implementation notes for a later PLAN (not authorized here):

- **Day-close delay of at least 24 h, preferably 48 h, plus a re-pull of D-1 and D-2 each day**: observed comment lag reaches 5.6 h in a 25-sample and sweeps cluster; counts must be idempotent and overwritten by the later, larger value (never summed).
- **Use `created_utc`, never comment IDs**, for paging and watermarks (IDs are non-monotonic since 2026-10-21; old and new formats co-occur in replies).
- **Verify the time zone**: aggregate day buckets look like Europe/Berlin days (O11). Either page raw items by explicit epoch/ISO-Z bounds and bucket locally (also keeps the existing local matcher, word-boundary and ticker disambiguation rules), or verify that explicit Z bounds are honoured.
- **Prefer raw paging + local matching over server keyword aggregates** (cost: r/Bitcoin was about 1,115 comments in a local day, 12 pages of 100; bigger subs unmeasured), because aggregates for busy subs time out and use the server's tokenization (calibrated within about 5% on one sample, O9). Throttle politely and cache; this is a one-person free service.
- **Reconcile**: compare each completed month against the monthly dump (about 10-12 days after month end) and record the shortfall as the method's measured completeness. The first reconciliation is October 2026, expected about 2026-11-10 to 11-12.
- **Keep method separation**: archive counts, live GraphQL counts and ApeWisdom counts are three methods with their own labels and never merged (SPEC AC15/rule 14). ApeWisdom is a trend canary only.
- **Fallback trigger conditions** (from the SPEC style "measure then escalate"): archive lag above 6 h for two consecutive days, ingest stall (newest comment older than 3 h on three monitored subs), status page not "Available", API 5xx above a threshold, dump reconciliation shortfall above a chosen percentage, or any announcement that ingest stops. Then enable the live fallback behind the owner-approved switch.
- **Deletion compliance**: store counts only, not text or author IDs (Reddit rule: content deleted on Reddit must be removed; the archive can hold text Reddit later removed).

**Fallback: rank 2 then rank 3,** only after probes P1-P3 pass, run once per subreddit per poll window as the SPEC's cost formulas already describe (about 288 logical loads per day for 12 polls x 12 subreddits x posts and comments, independent of coin count).

## 9. What the owner must probe live (nothing here was probed with an account)

Each probe records status code, content type, body size and signature (the vendor-reported block page is 189,908 bytes, `<body class=theme-beta>`), `x-ratelimit-*` headers and whether 200 is an empty shell.

| Probe | What to run | Pass criterion | Decides |
|---|---|---|---|
| P1, no account | From the intended egress IP class: mint an app-only token and call GraphQL `SubredditFeedElements` (new) for each of the 12 subreddits, `PostComments` for a thread with over 200 comments, the search tabs for 5 coins, and `about`. Repeat 24 h later and after the 2026-11-13 RSS end | Feed reaches the previous UTC day start with stable `t3_` ids, absolute timestamps and full text; comments pages continue via cursors; no block page for 48 h | Rank 2 viability; whether a free proxy exit class is blocked at the edge |
| P2, one owner account, real browser | Open each subreddit sorted by new; scroll to the previous UTC day start; open one busy thread; record network calls (do `/svc/shreddit/...` and `gql` calls succeed logged in?); relaunch with the same profile and compare device signals | Reaches day start without a gate or cap; comments load; no extra challenge on relaunch | Rank 3; Camoufox identity-per-launch issue #442 |
| P3, same account, cookie over HTTP | With a browser-emulating client matching the real browser: `/r/<sub>/new.json`, `/r/<sub>/comments.json` (sub-wide comment stream), `/search.json`, `/by_id`, thread JSON; compare with P2 | Which return JSON vs block/redirect; comment stream exists or not | Rank 4 and whether any chronological live comment lane exists |
| P4, no account | Arctic Shift: for the 12 subreddits and the last 7 days, page raw comments by explicit Z bounds and compare with aggregates; sample 3 hours against a manual browser view; measure lag over 48 h; compare October API counts with the dump when it appears | Lag and shortfall numbers; time-zone behaviour of bounds | Rank 1 parameters (day-close delay, reconciliation threshold, buckets) |
| P5, proxy | For each candidate free proxy exit: the P1 request and a datacenter-class check; record Reddit's block signature | Exit class and survival time | Whether free proxies can serve the fallback at all |
| P6, durability | 7 days of low-rate read-only use on one disposable account and IP; log challenges, 429s, budget headers, forced re-login | No ban or forced challenge | Account lifetime assumption for the one-week-rest rule |

Re-run P1-P3 after these dates: 2026-11-13 (RSS end), 2027-01-12 (removal begins), 2027-03 (public API end) and when Reddit starts the logged-in-only test (Q4 2026, markets outside the US first).

## 10. Corrections to what the SPEC/PLAN currently say

- Part C PLAN states the direct Reddit announcement of the RSS date was not read. The dates are now confirmed from a Reddit-owned page: [Reddit Help changelog 2026-10-08](https://support.reddithelp.com/hc/en-us/articles/54353370049684-Changelog-October-8-2026) (RSS 2026-11-13; new requests ended 2026-10-31; removal 2027-01-12; end March 2027). The r/modnews and r/redditdev originals remain unreadable from here.
- The PLAN says "Arctic Shift ... no uptime guarantee; PullPush freshness, current availability and terms remain unverified". Now: Arctic Shift live and measured (section 1); PullPush down (521 on 2026-11-04) and ingestion reportedly stopped May 2025. Terms of Arctic Shift data use are still unaddressed.
- The PLAN says "mobile gql-fed evidence does not establish web GraphQL". Still true; but gql-fed is now the only anonymous surface seen working, and `/svc/shreddit/` is blocked to anonymous clients since 2026-10-28.
- The PLAN says the Camoufox report found "changing canvas despite pinned config"; this agrees with open issue #442 (fingerprint seeds per launch).
- The SPEC's "Reddit's free API is approval-gated at 100 queries per minute per client" is correct but incomplete: approval is no longer obtainable (new requests ended 2026-10-31) and all access ends in March 2027.
- Evidence conflicts to keep open: logged-in listing/search JSON works in a real browser (vendor, 2026-10-18) versus refused to cookie sessions on emulated fingerprints (Redlib fork probe, November 2026); a vendor guide (wappkit, 2026-11-01) says `.json` still works "for some subreddits": contradicted by O1, every dated test above, and the fork authors, so disregarded.

## 11. Sources (all read 2026-11-06 unless stated)

PRIMARY (Reddit-owned)

- [Developer Platform registration](https://developers.reddit.com/app-registration)
- [Reddit Help changelog 2026-10-08](https://support.reddithelp.com/hc/en-us/articles/54353370049684-Changelog-October-8-2026)
- [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) (updated 2026-10-05)
- [Reddit Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki) (2026-11-03)
- [Developer Platform & Accessing Reddit Data](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data) (2026-11-03)
- [Don't break the site (Rule 8)](https://support.reddithelp.com/hc/en-us/articles/360043512931-Don-t-break-the-site) (2026-11-05)
- [Public Content Policy](https://support.reddithelp.com/hc/en-us/articles/26410290525844-Public-Content-Policy) (2026-11-06)
- [Q3 2026 shareholder letter](https://investor.redditinc.com/files/doc_financials/2026/q3/v2/Q3-26-Shareholder-Letter.pdf) (2026-10-29), as quoted in redlib#609

CODE/ISSUE

- [redlib#591](https://github.com/redlib-org/redlib/issues/591), [#603](https://github.com/redlib-org/redlib/pull/603), [#604](https://github.com/redlib-org/redlib/issues/604), [#609](https://github.com/redlib-org/redlib/issues/609), [#612](https://github.com/redlib-org/redlib/issues/612)
- [Nachtalb/redlib CONFIGURATION.md](https://raw.githubusercontent.com/Nachtalb/redlib/main/CONFIGURATION.md), [FORK.md](https://raw.githubusercontent.com/Nachtalb/redlib/main/FORK.md), [cookied_json.rs](https://raw.githubusercontent.com/Nachtalb/redlib/main/src/backends/cookied_json.rs), [gql.rs](https://raw.githubusercontent.com/Nachtalb/redlib/main/src/backends/gql.rs), commits through 2026-11-04
- [polak14/redlib commit 29f1835 (2026-10-28)](https://github.com/polak14/redlib/commit/29f18352cf54be4ffe579f773552acd0c45cdd08)
- [Panniantong/agent-reach#642](https://github.com/Panniantong/agent-reach/issues/642)
- [jordanburke/reddit-mcp-server#29](https://github.com/jordanburke/reddit-mcp-server/issues/29), [karanb192/reddit-mcp-buddy#39](https://github.com/karanb192/reddit-mcp-buddy/issues/39)
- [arctic_shift README/API/download_links/releases and issues #42, #53, #76](https://github.com/ArthurHeitmann/arctic_shift)
- [daijro/camoufox releases](https://github.com/daijro/camoufox/releases)

SECONDARY

- [TechCrunch 2026-09-30](https://techcrunch.com/2026/09/30/reddit-is-killing-rss-feeds-ending-public-api-access-because-of-ai-bots/), [TNW 2026-09-30](https://thenextweb.com/news/reddit-rss-feeds-shut-down-old-reddit-ai-scraping), [PPC Land 2026-10-04](https://ppc.land/reddit-to-halt-public-data-api-access-in-march-2027-as-14-000-apps-register), [BleepingComputer 2026-10-31](https://www.bleepingcomputer.com/news/security/reddit-to-lock-content-behind-logins-to-fight-scrapers/), [Ars 2026-06-30](https://arstechnica.com/gadgets/2026/06/reddit-will-require-you-to-log-in-to-use-old-reddit-com/)
- Vendors (bias disclosed): [bigideasdb how-to-scrape-reddit 2026-10-18](https://bigideasdb.com/how-to-scrape-reddit), [reddit-json-403](https://bigideasdb.com/reddit-json-403-forbidden), [api-shutdown-2027](https://bigideasdb.com/reddit-api-shutdown-2027), [how-to-get-reddit-api-key](https://bigideasdb.com/how-to-get-reddit-api-key); [redditapis comment IDs 2026-10-24](https://www.redditapis.com/blogs/reddit-comment-ids-13-characters-2026); [THINKPOL archive API 2026-08-19](https://think-pol.com/blogs/reddit-archive-api); [scalebrowser Camoufox review 2026-09-25](https://scalebrowser.net/blog/camoufox); [ApeWisdom API](https://apewisdom.io/api/) and [methodology](https://apewisdom.io/methodology/)

Not readable from this environment (Reddit blocked the reader): the r/redditdev posts [1wubcvf](https://www.reddit.com/r/redditdev/comments/1wubcvf/), [1vgbm9c](https://www.reddit.com/r/redditdev/comments/1vgbm9c/), [1whal6a](https://www.reddit.com/r/redditdev/comments/1whal6a/), r/modnews [1wubgvt](https://www.reddit.com/r/modnews/comments/1wubgvt/), [1tq9vxo](https://www.reddit.com/r/modnews/comments/1tq9vxo/), [1ujtebf](https://www.reddit.com/r/modnews/comments/1ujtebf/) and r/pushshift [1v50ved](https://www.reddit.com/r/pushshift/comments/1v50ved/). Their content is taken from the Help Center changelog, the registration page and the secondary/vendor quotations above.
