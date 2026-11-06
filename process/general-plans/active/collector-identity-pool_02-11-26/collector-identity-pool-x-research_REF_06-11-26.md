# X (twscrape) collection: research reference, 06-11-26

Author: XResearch (read-only research worker). Date of research: 2026-11-06 (UTC). Scope: the four questions in the assignment. No source, plan, config, dependency or lock file was edited. This is the only file written.

## 0. How to read this, and what was and was not done

Evidence labels used throughout:

- **[OBS]** observed by me first-hand: I read the primary source (code, issue, official doc) or ran a local offline check.
- **[3P]** reported by a third party (issue reporter, blog, hobby project). Real but unverified by me; the reporter's reliability is noted where it matters.
- **[VENDOR]** from a company that sells an alternative product (twitterapi.io, UScraper, Postory). Useful for facts that can be cross-checked, not for risk claims.
- **[INF]** my inference. Never to be treated as fact.
- **[LIVE]** can only be verified with live accounts (or live X); listed again in section 6.

What I did:

- Cloned `vladkens/twscrape` into a temp directory (outside the repo), diffed pin `63f61a5` against `main`, read the relevant issues/PRs through the GitHub API.
- Read X's official docs, changelog, developer-community posts and help pages where Cloudflare allowed (two X help pages answered HTTP 403 "Just a moment", so I only have search-engine snippets of the locked/limited-accounts page).
- Ran a handful of small offline Python snippets (query-ID comparison, regex check, cookie-jar behaviour) from a temp directory using the repo's locked environment (`curl_cffi 0.16.3`) and the pinned twscrape sources; no repo file was touched.
- Made **no request with any account, cookie or token.** I did make **seven unauthenticated plain GETs to X's public static surface** (`x.com/i/embed`, `abs.twimg.com` JS chunks) to compare GraphQL query IDs and the signing-script regex against the pin (section 2.4). My fetch tools also hit `help.x.com` several times and were answered 403 by Cloudflare. Disclosing this because the brief says "no live X requests with accounts"; none used accounts, but they were live requests from this machine's IP.
- Did not retain any cookie value: one public GitHub file with exported cookies was inspected for cookie **names and expiry timestamps only**.

Reliability warning on sources: the largest body of "how accounts die" evidence is GitHub issue threads from 2024 (older X behaviour). 2026 evidence is thinner and mostly single-reporter. Where a claim rests on one person, it says so.

---

## 1. Executive summary and ranked recommendations

Ranked by (impact on a working, finished collector) x (confidence in the evidence) / (cost and ban risk of acting). "Act" means a change to our code or process; none of it requires upgrading twscrape.

| # | Recommendation | Why (evidence) | Confidence |
|---|---|---|---|
| 1 | **Do not upgrade the twscrape pin. Add a read-only query-ID drift sentinel instead.** Compare the pin's `OP_SearchTimeline` etc. against the current public bundle; alert a human, do not auto-patch. | Today (06-11-26) the public bundle's `SearchTimeline` ID is `vLHjqbDv7TPFMBkIIO1nOA`; the pin (and upstream HEAD) still has `BYppgupFFS2yqVmmRNjlsw`. Of the 12 pinned operations present in that bundle, 10 differ; `UserByScreenName`/`UserByRestId` are unchanged. Upstream updated IDs 8 times between 2026-05-20 and 2026-10-21 (about every 2-3 weeks) and has not since. [OBS] | High that IDs moved; **[LIVE]** whether the old IDs still answer |
| 2 | **Treat an empty-body 404 on `SearchTimeline` as ambiguous** (stale query ID, bad transaction ID, or a per-account endpoint restriction), and separate the three before the existing drift stop (`DRIFT_STOP=3`) pauses the whole stream. | twscrape maps every 404 to "regenerate transaction ID x3, then abort". Flaburgan (upstream #367/#368, 03-11 to 06-11) found one account that gets a 404 on `SearchTimeline` with a valid ID, and showed the 404 is byte-identical to the bad-ID 404. The maintainer could not reproduce it on three older accounts. [3P, one reporter + maintainer counter-evidence] | Medium |
| 3 | **Classify error `(64) Your account is suspended` ourselves.** The pin does not deactivate on `(64)`; upstream HEAD does. Our `INACTIVE_CODES` has 88/326/32 only. Read the code list from `ApiError.errors` (the pin keeps it) instead of upgrading. | `queue_client.py` at pin has no `(64)` branch; HEAD adds it (commit `43177d2`). [OBS] | High |
| 4 | **Do not build automated login. Keep Stage 2 gated** by its existing trigger. If the trigger fires, build a *harvest-only* helper (reads cookies from an already logged-in, per-account real-Chrome profile; never types credentials) and keep every login/challenge manual. | The HTTP login flow twscrape drives is retired by X (twifork verified live 29-07; upstream maintainer 21-10). The replacement flow needs a Castle device token that only a real, headful Chrome minted in one third party's tests; a failed attempt can itself flag the account ("temporarily limited your login"). Locked accounts now reach a palm-scan liveness check that cannot be automated (twikit #430, 07-2026). Cookie `Expires` is not the limiting factor (section 3.2). [OBS/3P] | High on "login is dead/hostile"; low on how often renewal will be needed **[LIVE]** |
| 5 | **Keep one account = one IP = one browser profile, never shared; never log two accounts in from one environment.** | X's head of product on 14-02-26: if a human is not tapping the screen, "the account and all associated accounts will likely be suspended". Association mechanism is not public. [3P: quoted by press; original post not readable by me] | Medium |
| 6 | **Add a completeness canary for the Latest tab.** | Three 2026 behaviours make Latest silently incomplete: `(0) Dependency: Unspecified` with 200 and few/no tweets (twscrape #294, 02-2026); Latest hiding the last 7 days for some keywords while Top works (roboin, 04-2026); posts >= 7 days old with zero likes dropped (roboin, 08-2026). [3P] | Medium |
| 7 | **Keep pacing modest and measured; do not invest in "quiet hours" or "warm-up".** | No primary or reproducible evidence for either (section 4.3). What is documented: rate-limit headers, per-account budgets, and that low volume did *not* prevent bans in 2024 reports. | High that the evidence is absent |
| 8 | **Check our own cookie jar for the duplicate `ct0` pattern** (old domain-less cookie plus a new `.x.com` cookie). | Offline: with the pinned curl path and with our `CurlRouteClient` pattern (`Cookies(cookies)` then `.update(session.cookies)`), the jar sends `ct0=OLD; ct0=NEW`. HEAD fixed this in twscrape (PR #363). Whether X ever rotates `ct0` on GraphQL responses is **[LIVE]**. [OBS offline; INF for real wire] | Medium |
| 9 | **No free "counts" route exists on the web path.** Do not plan on volume counts; the official counts endpoint is paid ($0.005/request recent) and 7-day only. | The public web bundle contains `SearchTimeline` but no counts operation; X docs and pricing read 06-11-26. [OBS] | High |
| 10 | **Treat 7 days as the practical ceiling of search history**, even though old posts sometimes appear. | Official recent search/counts are 7-day; the new search index was "backfilled for the last 7 days" (Bier, 28-02-26); X's own Help Center says older posts may not display "because of indexing capacity restrictions". [OBS/3P] | High |

---

## 2. Question 1: twscrape pin `63f61a5`

### 2.1 State of the repo today [OBS]

- Pin `63f61a518e576ea5c132f1156c03dda0520d76c1` is commit "ci: release from a release commit through vladkens/actions (#360)", **2026-10-21**. It is the last commit before the 21-10 cleanup wave; it contains `c48eb91` (gql operations update, same day) and `187d278` (review fixes before v0.21.0: `ApiError` instead of silent empty results, deduped pages, stuck-cursor stop).
- Latest PyPI release is still `0.20.1` (2026-08-25). `v0.21.0` has not been tagged. `main` is `v0.20.1-28-gdd4c06c`. The lock file's "0.20.1" is the package metadata of the pinned commit.
- **Eight commits exist after the pin** (2026-10-30 to 2026-11-06):

| Commit | What | Relevance to us |
|---|---|---|
| `e874596` | docs: sponsor, readme images | none |
| `40e9525` | docs: agents.md | none |
| `1bf8002` (#363) | **curl-cffi is now a required dependency and the default backend**; `Account.user_agent` is not sent on curl; cookies scoped to `.x.com` ("a new `ct0` replaces the old one"); only connect failures retried with backoff (`_CURL_RETRY_DELAY=0.5`); TLS failures map to `ConnectError`; `socks5://` becomes `socks5h://` (DNS on the proxy); the curl profile now strips `accept`, `accept-encoding`, `connection` headers too; `HttpxClient`/`CurlClient` constructors lose the `cookies=` argument (set on the client afterwards) | Behaviour differences against our B1/B2 adapter contract; see 2.5 |
| `43177d2` (#364) | **rotate on 429 / headerless `(88)` / `(64)` suspended**; HTML 429 no longer treated as "Blocked by HTML"; `ParseError` for single-object parsers | See 2.3 |
| `243f4d0` (#361) | expose retweeted/quoted tweet IDs | none (we use `search_raw`) |
| `b8990cf` (#373) | tests: mock telemetry distinct id | none |
| `9b2b888` (#371) | trends: pad explore tab timeline IDs | none |
| `dd4c06c` (#370) | media metadata on photos/videos/gifs | none |

- `git diff 63f61a5..HEAD` touches only `http.py`, `queue_client.py`, `xclid.py` (cookie pass-through only), `api.py` (trend IDs only), `utils.py`, `models.py`, `cli.py`. **`api.py`'s GraphQL operation IDs are identical at pin and HEAD**; the signing/bootstrap logic in `xclid.py` is functionally unchanged.

### 2.2 Open issues and breakage reports since October 2026 [OBS]

Open at read time (2026-11-06), relevant ones only:

| # | Date | What | Status / our exposure |
|---|---|---|---|
| #351 | 05-10 | `SearchTimeline` does not rotate after a rate limit; hypothesis: an HTML-bodied 429 is classified "Blocked by HTML" and aborts | Still shown open, but PR #364 (merged ~05-11) claims to fix it. At the pin this is real: an HTML 429 raises `AbortReqError`. Our wrapper already reads the status from the `Blocked by ...: 429` message (`_STATUS_RE`) and treats 429 as rate-limit evidence, so we are covered without upgrading. |
| #367 / PR #368 | 03-11 | A `SearchTimeline` (and `UsersByRestIds`) GET returns 404 with an empty body for one old account while the same call works in a normal account and in the browser UI of a healthy account; first thought "phone not verified"; the maintainer then tested three old accounts (two without phone) and **could not reproduce**. On 06-11 the reporter showed the restricted-account 404 (valid transaction ID) is **identical** (status, empty body, headers, `x-rate-limit-*` decremented) to a healthy account's 404 with a garbage transaction ID. PR #368 (filter by phone) is not accepted as designed; the maintainer proposes detecting it from the response and marking per-account per-endpoint. | **Directly relevant** (recommendation 2). Single reporter, one account; mechanism unknown. |
| #337 | 12-09, active to 06-11 | `UserByRestId` 403 from Cloudflare with the httpx backend; cured by the curl backend | We use `curl` style or our own transport; covered. |
| #372 / #374 | 06-11 | telemetry raises when `py-machineid` returns no ID; `displayTextRange` mismatch on rebuilt retweet text | No effect: the pin sends PostHog telemetry unless `TWS_TELEMETRY=0` or `DO_NOT_TRACK=1`; our child allow-list already carries both variables. |
| #349 / #348 | 04-10 | expose why a user lookup returned none; parse errors become `None` | Addressed by #364 on HEAD; we do not call those methods. |

Closed in the 21-10 cleanup wave (all closed as stale, "fixed in v0.19.2/v0.20.x" or "if still relevant, reopen"); none were reopened as of today:

- #330 (2026-08-25): `X web scripts not found` on authenticated sessions. Root cause per the reporter: X changed legacy chunk hashes from 7 to 16 hex digits (about 24 Aug); fixed in v0.20.1; two users confirmed (one with 87 accounts) end to end. The Cloudflare-challenge theory in the original report was withdrawn by its author. [3P]
- #340, #298, #322, #320, #312, #305, #306: successive `x-client-transaction-id`/bootstrap breakages (see 2.4).
- #295: search duplicates/stuck cursor since the 28-02 search migration; maintainer: stuck cursors now stop pagination (v0.20.0), repeated items dropped (#332), **"X still caps how many results a search returns."**
- #294: `(0) Dependency: Unspecified` on 200 with 0-few tweets (02-2026); now raised as `ApiError` (#347). The pin includes this.
- #278, #285: scripted login blocked; maintainer 21-10-26: "X blocks scripted login now, so the reliable way is to add accounts from browser cookies ... Browser automation for login is out of scope for twscrape."
- #274: 429/(88) ban wave of 11-2025, "an older wave".

No issue after 21-10 reports a new `x-client-transaction-id` or query-ID failure. That is weak evidence (low traffic; reporters may be on older releases), not proof that nothing broke (see 2.4).

### 2.3 Rate-limit behaviour at the pin vs HEAD [OBS, code read]

At the pin (`queue_client.py::_check_rep`):

1. `text/html` and status >= 400 -> `AbortReqError("Blocked by Cloudflare|HTML: <status> - ...")`. Aborts the whole call, locks nothing. **This catches HTML 429s.** (Our wrapper turns it into an abort with the status.)
2. `x-rate-limit-remaining == 0` and `x-rate-limit-reset > 0` -> lock that account for that queue until reset, rotate.
3. `(88) Rate limit exceeded` with `remaining > 0` -> **treated as a ban**, account marked inactive.
4. `(326) Authorization: Denied by access control` and `(32) Could not authenticate you` -> inactive.
5. Bare 403 with no error text -> "Session expired or banned", **inactive** (permanent in twscrape's DB; one bare 403 deactivates).
6. `(336)` missing features -> self-heals once by setting the named flags true.
7. `(-1) LoadShed` / `DeadlineExceeded` -> retry same account with 2^n s backoff (budget 3 per kind, 4 total), no penalty.
8. Any other non-OK, no data -> `ApiError` with the code list in `.errors` (not silent). 200-with-data plus a warning is returned.
9. Any other HTTP error -> lock the account 15 minutes. Transport errors: retry with backoff, then cool 60 s. Unknown exception: 3-4 tries then 15 minutes.
10. 404 (before `_check_rep`): `Ctx.req` regenerates the transaction-ID generator up to three times, one second apart, then raises `AbortReqError("Failed to get XClIdGen ...")`. Each regeneration re-fetches `x.com` and the signing script **with the account's cookies and proxy** (extra requests per failure).

HEAD changes (`43177d2`): any 429 (even HTML) and headerless `(88)` lock that account for that queue until `x-rate-limit-reset` or 15 minutes and rotate; `(88)` **with data** returns the data; `(88)` without data and `remaining > 0` is still a ban; **`(64)` suspended deactivates**. We do not need these as a library upgrade: our wrapper already treats 429 as rate-limit evidence and, per recommendation 3, can add `(64)`. Because we run one account per unit, rotation inside the library is moot anyway (it would just produce `NoAccountError`).

Limits observed or reported: our own measurement (SPEC, 31-10-26) is about 50 `SearchTimeline` requests per 15 min per account; twikit's `ratelimits.md` and emusks' measured table also say 50 [3P]. One Go client seeds 187 "measured from the header" [3P, outlier, unverified]. The header should be read per account **[LIVE]**; do not hard-code.

### 2.4 Query-ID and transaction-ID drift

**Query IDs.** Hard-coded constants in `api.py`, refreshed by a manual script (`scripts/update-gql-ops.py`) that scrapes X's public JS bundles; **no runtime refresh**. Update cadence in git history (`api.py`): 2026-05-20, 06-08, 06-15, 06-26, 07-21, 08-07, 08-25, 10-21 [OBS], i.e. roughly every 2-3 weeks. A Go client (`go-twitter`) does refresh IDs at runtime [3P], so runtime refresh is a known design, but it also adds requests and parsing risk we would own.

Today's check [OBS, 7 unauthenticated GETs]: the public logged-out legacy bundle `main.7e80395699a4329fa.js` (1,212,557 bytes) lists 104 operations; 12 of the 22 operations the pin defines appear in it. Against the pin:

| Operation | Pin | Bundle today |
|---|---|---|
| SearchTimeline | BYppgupFFS2yqVmmRNjlsw | **vLHjqbDv7TPFMBkIIO1nOA** |
| UserTweets | OdBLACRZ0-9NikpJotaT7g | D6z-FJI2pKuwEeYYxVIGbg |
| TweetDetail | wjV7NuWEsHgTBFfW3zYKzQ | dQDdKtt882nl-Km98FJGSQ |
| Followers / Following | sO2htFYgDpQopDNVjDcf1Q / 9l9tzqLGQU9eutAJffqqMw | Xe3y9_ndZ9-RtWz8zd_wpg / eDqlbOS46zda8jDT8dEQ_Q |
| UserByScreenName | AMIBMjtxEEATh4z8V9GtRg | same |
| UserByRestId | mxaYWwt52eAb6OAzYHMVzg | same |

Caveats: this is the **logged-out** bundle (the same source upstream's script uses, per its own comment), not the authenticated app. Whether X still answers the old IDs is unknown; X is reported to keep old persisted-query IDs alive for a while in some periods and to answer 404 in others (#306, 05-2026, mixed with a transaction-ID cause). **[LIVE]** (needs one real request).

What a stale ID looks like to us: a 404 with an empty body, indistinguishable from a bad transaction ID (upstream #306, #367). The pin then burns three bootstrap fetches and aborts with `Failed to get XClIdGen`; our reader maps this to `not_found`, which counts toward `DRIFT_STOP`. That is the right outcome for real drift, the wrong one for a per-account restriction (recommendation 2).

**Transaction IDs (`x-client-transaction-id`).** Computed client-side from the x.com page (verification key, animation SVG) and the `ondemand.s` signing script. Break history (issues): Jan 2026 (#289), Mar (#298), May (#305/#306/#312), Jul (#320/#322), **24-25 Aug** (#327/#330: 7 -> 16 hex chunk hashes), 30 Sep (#340). Each was fixed upstream within hours to days. That is five or six breaks in ten months; none reported after the 21-10 release commit.

Mechanism-level check today [OBS]: the pinned `INDICES_REGEX` extracts 4 indices from the current public `ondemand.s.5c59a8528597f736a.js` (19,077 bytes), found through the current chunk map. So the signing script's shape still matches the pinned regex on the logged-out build. The authenticated build can differ (the #330 reporter saw a different, 289 KB page for authenticated sessions) **[LIVE]**.

Other drift defences at the pin: `(336)` missing-feature self-healing; `XClIdAccountError` (logged-out page) locks the account 15 min; `XClIdParseError` raises and closes the context. None refreshes query IDs.

### 2.5 Does HEAD have fixes we need? (report only; no upgrade)

| HEAD change | Needed? | Why |
|---|---|---|
| Rotate on 429 / headerless `(88)` | No | wrapper already classifies 429; one account per unit |
| `(64)` suspended deactivates | **Replicate in our classifier** | pin leaves a suspended account "active" and returns a generic `ApiError` each time |
| Cookies scoped to `.x.com` / `ct0` replacement | **Verify** our own client | recommendation 8; our adapter owns the curl jar |
| curl default, header stripping (`accept`, `accept-encoding`, `connection`), `socks5h` | Not needed; **would change** the B1 wire contract and our proven proxy/identity tests if adopted | adapter sets backend explicitly |
| Retry loop rewrite (`_CURL_MAX_RETRIES`) | Not needed | at HEAD `_CURL_MAX_RETRIES=0` still means one wire attempt, so our B2 "one attempt" rule would survive [INF]; but would need re-proof |
| `ParseError`, media metadata, trends, telemetry mocks | No | unused paths |
| Query-ID update | **Not at HEAD either** | upstream has not updated since 21-10; see 2.4 |

Net: **nothing at HEAD is required**; the two items worth copying (`(64)`, cookie semantics) are small wrapper changes. The one time-sensitive risk (query IDs) is not fixed upstream yet.

---

## 3. Question 2: safe cookie renewal for throwaway accounts

### 3.1 Routes compared

| Route | Status 2026-11 | Evidence | Verdict |
|---|---|---|---|
| **twscrape `login_accounts`** (HTTP `onboarding/task.json`, `flow_name=login`, TOTP via `pyotp`, email code via IMAP) | **Dead.** Code at pin still drives the classic flow (`LoginJsInstrumentationSubtask`, `LoginEnterPassword`, `LoginTwoFactorAuthChallenge`, `LoginAcid`). X answers `366 flow name LoginFlow is currently not accessible` or `399 Could not log you in now`. | twifork README, "verified against live x.com on 2026-07-29": `/i/flow/login` redirects to `/i/jf/onboarding/web`, the site posts to `/i/jfapi/onboarding/web/actions/begin_login`, which needs a ~4-5 KB `$castle_token` from obfuscated in-page JS and offers passkey/WebAuthn as first factor. emusks docs: same, plus Castle token details. upstream #278/#285 closed with the maintainer's 21-10 statement. [3P x3, consistent] | **Reject** (also already excluded by the safety review) |
| **Real Chrome/Edge, headful, per-account persistent profile** (Playwright `channel="chrome"` or nodriver or raw CDP) | The only mode with any evidence of passing the new login's device check. | emusks: Castle tokens are bound to the minting browser (canvas/WebGL/audio, x.com origin, `m.castle.io` handshake); `node:vm`, **headless Chrome and stealth Firefox (Camoufox) were soft-rejected** with "We've temporarily limited your login", only real non-headless Chrome worked. Single hobby project, undated (written after the 29-07 flow change, [INF] 2H 2026). | Only viable automated login; **highest ban risk of anything in this report** |
| **Camoufox** | Releases continue (`v158.0.1-beta.41`, 2026-11-01, still beta) | Our own probe: about 630 MB, slow start, unstable canvas fingerprint, hangs on double-open (SPEC). emusks: fails Castle. Camoufox README: "under development". | Not for X login. (Stage 4 Reddit is a separate decision.) |
| **nodriver** | Active (`0.50.99`, 2026-10-26) | No X-specific evidence. Chromium over CDP. | Option for the Chrome driver; no evidence it passes or fails Castle |
| **Playwright (bundled Chromium or Chrome channel)** | Active | No X-specific evidence. Automation flags are a known detection surface [INF]. | Same as above; prefer the installed Chrome channel |
| **Manual login by the owner, cookies copied** (`auth_token`+`ct0`) | Works; the upstream-recommended path ("most stable") | upstream readme; twifork; emusks | **Baseline today**; already supported by `--refresh-cookies` |

### 3.2 How often do `auth_token` / `ct0` expire in practice?

No primary source documents a session lifetime. What I can state:

- **The cookie `Expires` attribute is not the limit.** A public GitHub file of cookies exported from a real browser (`musk1n/Twitter-data-scraping`, committed 2025-04-01) shows `auth_token` and `ct0` with `Expires = 2026-05-02T09:55Z` while the guest-token cookies imply capture at about 2025-03-28T09:55Z. That is exactly 400 days, which matches Chrome's cookie lifetime cap (known Chrome behaviour, not re-verified here [INF]). So the server asks for >= 400 days and Chrome clamps it. [OBS, names and timestamps only; capture time derived [INF]]. An LLM-generated "auth flows" note on GitHub that says "`ct0`: session, `auth_token`: ~5 years" is not evidence and I disregarded it.
- **Sessions die server-side**, by: password change/logout (obvious), `(32) Could not authenticate you`, a bare 403, `(326)` lock, `(64)` suspension, or X invalidating a "suspicious" session. Reports of the *rate* are all failure stories from bulk setups in 2024 (#175: bans of hundreds of accounts within days; "3 weeks no loss then all banned at once"; JonasBirk: 95% of 3,000 accounts read-only). Those say how accounts are *lost*, not how often a healthy session needs renewing. [3P]
- **No evidence that a healthy, lightly used cookie account is forced to re-login on a schedule.** Our own collector has run the same hand-loaded cookies since at least 31-10 (SPEC measurement) with no renewal. The Stage 2 trigger in the SPEC (cookies expire or force a login more than once every two weeks) is not yet observed. [OBS via SPEC]
- Our reader already records the refresh time (`cookie_ages`), so the **only missing measurement is the cause and age at the moment of failure** (recommendation 4).
- **`ct0` rotation is unknown.** The pin copies the DB's `ct0` into both the cookie jar and the `x-csrf-token` header for every new client and never writes a rotated value back (`Account.make_client`; no cookie persistence in `accounts_pool`). A Go client's docs describe code 353 "CSRF mismatch" recoveries that adopt a new `ct0` from `Set-Cookie` [3P], which implies X can rotate it. **[LIVE]**: does any GraphQL response carry `Set-Cookie: ct0`, and does a fresh process using the stored (old) value still work?

### 3.3 2FA, email challenge, detection risk (browser login)

- **TOTP:** twscrape stores the base32 seed in `mfa_code` and uses `pyotp`; usable only in the dead HTTP flow. In a browser flow the same seed can type a code, but the new Jetfuel flow's DOM and action IDs (`login_enter_two_factor`, `login_acid`, `login_enter_alternate_identifier` per emusks) are not stable public knowledge; selectors would be **[LIVE]**. A stored TOTP seed plus the mailbox password makes the account fully recoverable by anyone who reads our private files, so it widens the secret blast radius.
- **Email challenge:** twscrape's `imap.py` reads the "confirmation code" mail. New-device logins now hit `verify_code`/`knowledge_check` screens and an "alternate identifier" step that asks for username, email **or phone** (emusks). A throwaway with no phone attached may hit a dead end. [3P]
- **Detection risk, stated plainly:**
  - X documents that scripting the website is prohibited ("Use non-API-based forms of automation, such as scripting the X website. The use of these techniques may result in the permanent suspension of your account", Automation rules, updated April 2026). [OBS] This is a policy fact, not a detection fact. The owner has already accepted the evasion route; it should still be in the risk register.
  - Bier, 14-02-26: if a human is not tapping the screen, "the account and all associated accounts will likely be suspended -- even if you're just experimenting". [3P, press quote]
  - A failed Castle login is not neutral: emusks reports a flagged account gets "temporarily limited your login" for a while "even from a new IP", and `begin_login` is throttled per account and per IP. [3P]
  - Locked accounts: one twikit reporter (#430, 04-07-26) was sent to `x.com/i/palm-liveness`, a palm scan that needs the official phone app; a second user (15-07) hit the same. Appeal-only otherwise. For a throwaway, a lock is functionally a loss. [3P]
  - 12-14 March 2026: a new spam filter wrongly suspended a subset of normal accounts for about 12 hours (Bier says 99% reinstated). Not specific to scrapers, but shows enforcement is volatile. [3P press]

### 3.4 Chrome constraints that shape any browser design [OBS, Chrome for Developers, 2025-03-17]

- Chrome 136+ ignores `--remote-debugging-port` and `--remote-debugging-pipe` for the **default** user-data directory. A **non-default** `--user-data-dir` (which we want anyway, one per account) still works.
- App-Bound Encryption (Chrome 127+) on Windows blocks external reading of the cookie database; cookies have to be read through CDP or the DevTools UI, not by opening the `Cookies` SQLite file. [INF for upstream "unjar" on current Chrome: unverified]
- Chrome's `--proxy-server` does not take credentials; per-account authenticated proxies need Playwright's proxy option, a local forwarder, or a CDP auth handler [INF, standard Chrome behaviour]. One-account-one-IP means the browser must use the account's own route (and our B2 route admission), not the home connection.

### 3.5 Recommended minimal-risk renewal design (fits 8 GiB, one browser)

Principle: **automation never types a credential and never solves a challenge.** It only moves a cookie from an already-authenticated profile into the pool, and it stops at the first sign of trouble.

1. **Now (no new code):** keep the owner-run `--refresh-cookies` path. Add to the health line: cookie age and the reason class at the moment an account goes `x_login_required` (32/403) versus `x_account_suspended` (326/64/88). That data answers the SPEC trigger with evidence.
2. **If the trigger fires, build a "harvest-only" helper, one command, owner-initiated or on a pause reason `x_login_required`:**
   - Launch the **installed real Chrome**, headful, with a per-account non-default `--user-data-dir`, through that account's assigned route (same IP as the reader). Never the home connection.
   - Open `x.com/home` in the existing profile. If the page lands on the logged-in app: read `auth_token` and `ct0` for `.x.com` through CDP, hand them to `refresh_cookies` (existing upsert), close the browser. If it lands on a login or challenge screen: **stop, pause that account with reason `x_login_required`, notify the owner, do nothing else.**
   - The owner performs any login/2FA/email/captcha/palm step by hand in that visible profile, from that route.
   - Why this is lower risk: a returning logged-in profile loading its home page is ordinary browser traffic; no Castle login, no credential entry, no token minting. [INF]
3. **Hard limits:** at most one harvest per account per day; one account at a time; never while that account's collector unit is running; never retry; never switch IP to retry; no login attempt counts beyond the owner's manual one. Circuit-breaker design reference: a Go client refuses further relogins for 30 minutes after three consecutive failures [3P]; ours should be stricter (stop at the first failure).
4. **RAM:** serialize the browser behind a single mutex (shared with any Stage 4 Reddit browser); launch only for the harvest, exit immediately after; the collector itself is HTTP-only. Camoufox measured about 630 MB here; real Chrome headful memory is **unmeasured**, a typical single window with one x.com tab is several hundred MB [INF]. Measure RSS locally and set a ceiling before enabling.
5. **Unattended login (TOTP/IMAP) is out.** If the owner later wants it, it needs: opt-in per account, a private secret store with the B2 ACL model, a proven real-Chrome Castle path, a one-attempt-per-day breaker, and an explicit acceptance that a "temporarily limited your login" result is treated as a lost account.
6. **Cookie hygiene:** log only age and reason class, never values (existing SPEC AC2); handle the duplicate-`ct0` check from recommendation 8 before building anything that re-saves cookies from a running session.

---

## 4. Question 3: ban and challenge signals; what mitigations are evidence-based

### 4.1 Signals, with the evidence for each

| Signal | What it means | Source / evidence |
|---|---|---|
| `x-rate-limit-remaining: 0` with `x-rate-limit-reset` | ordinary per-account per-endpoint 15-min window; ~50 for `SearchTimeline` | our measurement; twikit; emusks [OBS/3P] |
| HTTP 429 (JSON or HTML), `(88) Rate limit exceeded` | rate limit; with `remaining > 0` historically a restricted/"read-only" account | twscrape code; ExHix 2024: restricted accounts get ~11-13 searches per 24 h window and the headers stop being reliable [3P, 2024] |
| `(32) Could not authenticate you`; bare 403 (no error text, not HTML) | dead session or ban (twscrape deactivates on both) | code [OBS] |
| `(326) Authorization: Denied by access control` | locked/limited; unlock needs a browser challenge (captcha) and now sometimes palm liveness | code; X help snippet "we may lock it and request that you pass a captcha"; twikit #430 |
| `(64) Your account is suspended` | suspended (terminal) | twscrape HEAD |
| `(226) This request looks like it might be automated` | automation flag, mostly on writes; a Go client benches the account on first sight | go-twitter docs [3P] |
| 404, empty body, on `SearchTimeline`/`UsersByRestIds` with a good request | stale query ID, bad transaction ID, **or per-account endpoint restriction** | #306, #367; indistinguishable on the wire |
| 200 with `(0) Dependency: Unspecified` and few/no tweets | silent degradation (seen 02-2026) | #294 [3P] |
| 200 with `LoadShed` / `DeadlineExceeded` | X overloaded; not an account penalty | code |
| HTML 403 from Cloudflare | TLS-fingerprint block (httpx on `UserByRestId`) | #337, PR #363 [OBS] |
| Login: `366`, `399`, "temporarily limited your login" | classic flow retired / Castle token rejected / login throttle | twifork, emusks |
| Unlock via `x.com/i/palm-liveness` | flagged-as-automated lock | twikit #430 [3P] |

"Shadow search degradation" for a *reading* account has no public, reproducible definition. The closest documented items are (a) the restricted "read-only" state with a low search budget (2024), (b) the silent `(0) Dependency` 200s above, and (c) a per-account 404. There is no documented signal that distinguishes "your reads are being throttled quietly" from "the index is just incomplete". That is why recommendation 6 is a canary, not a rule.

### 4.2 Evidence-based mitigations (strongest first)

1. **Browser-grade TLS/HTTP fingerprint** (curl_cffi impersonation): reproduced fix for the Cloudflare 403 (#337); maintainer then made it the default (#363). [OBS]
2. **Obey the rate-limit headers and lock until reset**; do not retry through a limit. Universal practice; library and Go client both do. [OBS]
3. **Reuse sessions; do not re-login.** twikit's maintainers: logins "are closely monitored"; emusks: `begin_login` throttled per account and IP. [3P]
4. **Dedicated, clean IP per account; no shared residential/proxy pool with spammers.** One long-term operator (two years semi-production): "you don't want to share the same IP with a twitter spammer"; login failures with `ct0 not in cookies` were cured by changing the proxy; bans did not correlate with rotation at the limit. [3P, anecdote]
5. **Do not link accounts** (shared IP, profile, device), given the "associated accounts" statement. [3P]
6. **Read-only behaviour.** X's rules and bans concentrate on writes/follows/likes. A Go client documents `226` as mostly a write signal. [3P]
7. **Treat locks as terminal and stop.** Retrying a locked account is what escalates it (go-twitter breaker; emusks "flagged account ... temporarily limited"). [3P]

### 4.3 What is not evidence-based

- **Quiet hours / time-of-day avoidance:** I found nothing, primary or anecdotal, that measures it. Treat as speculation.
- **Warm-up ramps** for new throwaways: no measurement. One 2024 operator reported 20-30 searches/day/account with random account order and a long back-off: "back to losing 1-2% per day", then "3 weeks with no bans, then yesterday all banned" (#175). That is consistent with *no* pacing being sufficient. ExHix (2024): a 5-requests/15-min cap still got accounts banned, "no matter how low frequency you scrape".
- **Specific jitter ranges** (0.8-2.0 s, etc.): a Go client's defaults, not measured thresholds.
- **"DOM mode (Selenium) never gets suspended, HTTP does"** (Jwom, 2024, one tester): untested by others, predates `x-client-transaction-id` support in twscrape, and conflicts with a later reporter whose Selenium account was banned. Not usable as a rule.
- **Account age, Premium, phone verification as protective:** claims exist; none has a reproducible test. Phone verification as a *prerequisite for `SearchTimeline`* was a hypothesis that the maintainer's counter-test contradicted (#367/#368).
- **Account-creation or captcha-solving tricks:** out of scope (owner creates accounts; we never solve captchas).

Net: pacing guidance should stay at "stay well below the header limits, one request in flight per account, stop on any challenge", with the numbers tuned from our own B3 measurements, not imported folklore.

---

## 5. Question 4: search behaviour changes in 2026

### 5.1 The web path our collector uses (`SearchTimeline`, Latest)

| Date | Change | Evidence |
|---|---|---|
| 21 Feb | X "almost done with the full rewrite of legacy Twitter search (and also bot detection)"; search "has been getting hammered by AI agents and has been choking at scale" (Bier, 21-02). On 14-02 Bier also announced more automation/spam detection (section 3.3) | Social Media Today 22-02 [3P press quote] |
| 28 Feb | "New Top & Latest tab has been rolled out to 100% and backfilled for the last 7 days" (Bier). Complaints begin the same evening: irrelevant posts in Latest, exact-match quotes failing, `(0) Dependency` partial responses | roboin 01-03; twscrape #295 [3P] |
| March | "Latest only shows about 20 results"; Top paginates but returns <50% of matches | #295 comments (congosto, 15-03) citing a Reddit thread I could not open [3P, secondhand] |
| Early April | For some keywords the Latest tab hides the last 7 days (only older posts shown) while Top is fine; `since:` within 7 days then returns 0 in Latest | roboin 13-04 [3P, one tester] |
| 29 May | `source:` operator in Latest returns nothing | roboin [3P] |
| 8 Aug | Posts >= 7 days old with **zero likes** no longer appear; zero-reply and zero-repost posts of any age do; 6-day-old zero-like posts do | roboin 09-08 [3P, one tester, Android app]; X Help Center: "posts more than a week old may fail to display ... because of indexing capacity restrictions" (archived Sept 2023) |
| 21 Oct | Maintainer: stuck cursors stop pagination; repeated items dropped; "X still caps how many results a search returns" | #295 [OBS] |
| 31 Oct - 2 Nov | **Our own run:** two accounts read 18-20 coin-days per 800-read budget with Latest day windows; rollover, canary, clean stop worked | SPEC [OBS] |

Interpretation: Latest pagination works in our measurements as of 31-10 (so the March "20 results" cap is not reproduced by our run, though our windows are narrow per-coin days), but **completeness is not guaranteed** and the failure modes are silent. The practical ceiling for any history is about 7 days.

Page size: about 20 tweets per page (twikit `count=20`; a vendor measured 20 on 75 of 75 pages). The repo accepts only `product=Latest` (`x_window.py`).

### 5.2 Counts endpoint

- **No web counts operation.** The public bundle's 104 operations include `SearchTimeline`, `BookmarkSearchTimeline`, `ListSearchTimeline`, `GlobalCommunities*PostSearchTimeline`, `TrendHistory`, but no search-counts operation. [OBS, logged-out bundle only; authenticated app **[LIVE]**] twscrape has none either.
- **Official X API (paid, for reference):** `GET /2/tweets/counts/recent` "Retrieves the count of Posts from the last 7 days", `start_time` "Must be within the last 7 days", granularity `minute|hour|day`; `counts/all` full archive. Pay-per-use price: counts recent $0.005 per request, counts all $0.010; reads $0.005 per post; cap 3 M post reads/month; rate 300/15 min for counts. [OBS, docs.x.com, read 06-11-26]. The owner's no-spend rule excludes this; useful only to know what exists.

### 5.3 Official recent search changes (relevant if the 7-day claim is quoted anywhere)

- **4 May 2026:** `/2/tweets/search/recent|all` and `/2/tweets/counts/recent|all` moved to the new core search index: fewer 503s, new `min_likes:`, `min_replies:`, `min_reposts:` operators (they had been deprecated on 19-01), and **retweets are no longer returned in keyword search** (the Filtered Stream is unchanged). [OBS, X dev community post + changelog]
- Limits [OBS, docs.x.com rate-limits page]: recent search 450/15 min app, 300 user, 10 default/100 max results; full archive 1/s and 500 max; counts 300/15 min. The same page lists a 512-char query limit for recent search while the OpenAPI shows `maxLength: 4096` on the counts query; X's own docs disagree, so do not rely on either for the web path. Our child accepts up to 4,096 bytes (`twscrape_reader.py`); the web limit is **[LIVE]**.
- Effect on us: none directly (we do not use the official API). It does show that X's *own* index now treats 7 days as the supported recent horizon.

---

## 6. What only live accounts (or live X) can verify

1. Does the pinned `SearchTimeline` ID (`BYppgupFFS2yqVmmRNjlsw`) and the other differing IDs still return 200? One request per operation on one healthy account.
2. Does the pinned bootstrap parse the **authenticated** page (verification key, animation data, `ondemand.s` indices)? #330 showed the authenticated page differs from the logged-out one.
3. Per-account `SearchTimeline` capability: 404-with-valid-request on any account. Compare each account on a known-good query once, and compare with `UserByScreenName` on the same account.
4. Actual `x-rate-limit-limit` per account and operation (our 50 vs a third party's 187).
5. Does X set a new `ct0` on GraphQL responses; does an old stored `ct0` keep working in a fresh process; what do duplicate `ct0` cookies do? (recommendation 8)
6. Server-side session lifetime and what actually forces a re-login (needs weeks of the cookie-age instrumentation).
7. Whether a browser-minted cookie used from a curl_cffi client of a different impersonation target on the same IP draws extra challenges. (The current hand-loaded cookies have worked for several days; that is the only evidence.)
8. Whether Latest hides the last 7 days or returns partial pages for our actual queries; compare Latest versus Top over the same window, rate-limit headers, and entry counts.
9. Any login-side behaviour (Castle, 2FA, email, passkey, palm liveness) on an owner-created throwaway. The owner performs logins; we never create accounts or solve captchas.
10. Real Chrome headful memory for one x.com tab under the 8 GiB constraint, and Chrome proxy-auth behaviour for the B2 routes.
11. Whether the web search query length limit is 512, 4,096 or something else.
12. Whether headerless `(88)`/429 or `(0) Dependency` responses occur on our accounts today.

---

## 7. Source register

Primary / first-hand:

- twscrape repo, pin and HEAD (cloned 2026-11-06): https://github.com/vladkens/twscrape (commits `63f61a5`, `1bf8002`, `43177d2`, `c48eb91`), PRs #363 https://github.com/vladkens/twscrape/pull/363, #364 https://github.com/vladkens/twscrape/pull/364, #368 https://github.com/vladkens/twscrape/pull/368; issues #337, #351, #367, #330, #295, #294, #278, #285, #274, #306, #298, #340, #175, #268, #269, #372, #374 under https://github.com/vladkens/twscrape/issues/
- X API changelog (read 2026-11-06): https://docs.x.com/changelog ; rate limits https://docs.x.com/x-api/fundamentals/rate-limits ; pricing https://docs.x.com/x-api/getting-started/pricing ; counts https://docs.x.com/x-api/posts/get-count-of-recent-posts
- X dev community, search index migration, 2026-05-04: https://devcommunity.x.com/t/important-update-x-api-search-endpoints-migrating-to-new-search-index/264595
- X Automation rules, updated April 2026: https://help.x.com/en/rules-and-policies/x-automation
- Chrome for Developers, remote debugging changes, 2025-03-17: https://developer.chrome.com/blog/remote-debugging-port
- X public bundle and signing script, fetched 2026-11-06 (unauthenticated): `https://x.com/i/embed`, `https://abs.twimg.com/responsive-web/client-web/main.7e80395699a4329fa.js`, `.../ondemand.s.5c59a8528597f736a.js`
- Camoufox releases (feed read 2026-11-06): https://github.com/daijro/camoufox/releases ; nodriver PyPI feed: https://pypi.org/rss/project/nodriver/releases.xml
- Repo evidence read: `api/data/attention/{twscrape_reader,x_reader,x_pool,x_proxy_curl,x_proxy_transport,x_window}.py`; `api/pyproject.toml`, `api/uv.lock`; SPEC/PLAN in this folder.

Third party (labelled [3P] above):

- twifork README (login retired, verified 2026-07-29): https://github.com/PawiX25/twifork/blob/main/README.md
- emusks docs, Castle and login flow; authentication; rate limits: https://emusks.tiago.zip/internals/castle , https://emusks.tiago.zip/getting-started/authentication , https://emusks.tiago.zip/more/rate-limits
- twikit #430 palm liveness (2026-07-04): https://github.com/d60/twikit/issues/430 ; twikit "To protect your account": https://github.com/d60/twikit/blob/main/ToProtectYourAccount.md
- go-twitter error and rate-limit docs: https://github.com/anatolykoptev/go-twitter (docs/errors.md, docs/rate-limits.md)
- Social Media Today, 2026-02-22: https://www.socialmediatoday.com/news/x-formerly-twitter-rewrites-search-discovery-ai-bots/812792
- roboin.io: 2026-03-01 https://roboin.io/article/en/2026/03/01/x-search-malfunction-exact-match-queries-failing-causes-and-fixes-explained ; 2026-04-13 https://roboin.io/article/en/2026/04/13/how-to-fix-x-latest-tab-not-showing-posts-from-the-last-7-days ; 2026-05-29 https://roboin.io/article/en/2026/05/29/how-to-fix-x-search-source-command-not-working-issues ; 2026-08-09 https://roboin.io/article/en/2026/08/09/why-x-search-is-not-showing-older-posts
- PiunikaWeb, 2026-03-14 (ban wave, Bier quote of 2026-02-14): https://piunikaweb.com/2026/03/14/x-users-report-wave-of-bans-for-inauthentic-behaviors
- Public cookie export used only for expiry arithmetic: https://github.com/musk1n/Twitter-data-scraping/blob/main/twitter_cookies.json

Vendor (labelled [VENDOR]; used only to cross-check page size and list open issues): https://twitterapi.io/blog/twscrape , https://twitterapi.io/blog/twikit , https://uscraper.io/blog/get-twitter-cookies-how-to , https://postory.io/blog/twitter-bot-purge

Could not read: X Help Center "Help with locked or limited account" and "X search policies" (Cloudflare 403; only search snippets seen), Bier's original posts on x.com (tool failures), the Reddit thread on the "20 results" cap (blocked). Claims resting on them are marked press/secondhand.
