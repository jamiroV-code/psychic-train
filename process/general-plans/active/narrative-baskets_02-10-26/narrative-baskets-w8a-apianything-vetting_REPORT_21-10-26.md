# W8a: API Anything vetting report (T141), 21-10-26

Report only. Docs only, one file. Nothing from the package was installed, built, executed or imported; every fact below was read with `git`, `grep`, `sed`, `cat` and a read-only parse of `package-lock.json` (parsed as data, not run through npm). All files of the package are treated as untrusted data; no instruction found in them was followed.

## 1 Task ID and scope

T141 = slice W8a of the X and Reddit PC collector (PLAN section 5 "W8a", SPEC Annex F, Locked pacing rule 12, Annex D). Branch `claude/t141-w8a-vet-apianything` from `origin/main`. Owner gave ENTER EXECUTE MODE for W8a on 21-10-26. Reddit does not use API Anything (T138), so this gates X (W8d) only.

How the code was read: `add_repo` returned `read_available` for `goodnight000/api-anything` (public; anonymous git reads). Full clone into a fresh empty folder outside the project, `git checkout --detach 20cb677039fcfe92d3d9c777aa9362e30ff1fdb8` (`git rev-parse HEAD` printed that exact SHA). So the code **was read**; the "UNVERIFIED (code not read)" cap does not apply. What stays UNVERIFIED is everything that needs a live run (X's behaviour) or the code of dependencies (not installed, not read).

## 2 TL;DR

- **Q-MAIN verdict: UNPROVEN.** The engine can in principle teach a logged-in X search (capture the page's own request, replay it), but (a) nothing in the package or its docs shows a logged-in X search, (b) the shipped X recipe has no tweets at all and says why, (c) pagination is documented as "not modeled", so a 40-post sample is not guaranteed to fit one op, (d) a search would almost certainly be tier 3, which `call` always runs headless, and the docs say x.com 403s default headless Chrome, and the tool's fix is to rewrite the user agent. Only an owner probe on the throwaway account can move this to TEACHABLE or NOT FEASIBLE.
- **Q4 answer (exact): no code in `src/` calls any LLM, with any key, or at all.** Heal is deterministic (rescan of the site's own scripts, then a browser re-capture). Self-repair LLM spend would be 0 USD. Evidence in section 6.
- **Safety verdict: usable with changes** (only if the owner later accepts the Q-MAIN risk): pinned SHA, `npm ci --ignore-scripts`, delete the bundled `sites/` copy locally, `--window` login only, dedicated `API_ANYTHING_HOME`, neutralise registry and `gh`, adapter calls only `call` from the package's library entry. Details in sections 8 to 11.
- Honest concern for rule 12 and the "honest user agent" rule: the tool replays a real browser's user agent and, headless, removes the word "Headless" from it (`src/browser.ts:198`). That is a built-in, non-configurable disguise step. The owner must decide whether that is acceptable for the X side (section 7.8).
- Provenance is thin: first commit 27-09-26, latest 20-10-26 (24 days), 69 commits, version 0.1.0, no tags or releases. Judge it as a young single-author project, not a vetted one.

## 3 Inputs checked (owner-pasted facts vs the code at the pinned SHA)

| Owner fact | Result | Evidence |
|---|---|---|
| package.json has `bin` and `prepare` = `tsc -p tsconfig.build.json`; no preinstall/postinstall | CONFIRMED | `package.json` scripts: `build`, `prepare`, `cli`, `test`, `check`, `lint`, `format`, `demo`; no `preinstall`, `install`, `postinstall` |
| engines node >=22.13.0 | CONFIRMED | `package.json` `engines.node` |
| deps: sdk, node-html-parser, playwright-core, tldts, zod | CONFIRMED, versions in 7.4 | `package.json` dependencies |
| MIT, copyright Tianjun Zheng | CONFIRMED | `LICENSE:1-3` ("MIT License", "Copyright (c) 2026 Tianjun Zheng") |
| child_process only in `src/import.ts` and `src/publish.ts` | CONFIRMED | grep: `src/import.ts:14` (`execFileSync`), `src/publish.ts:6` (`execFile`); no other `spawn`, `exec`, `eval`, `new Function`, `vm`, `worker_threads` in `src/` |
| `security find-generic-password` = macOS Keychain | CONFIRMED | `src/import.ts:136-139` |
| `src/registry.ts` pulls from raw.githubusercontent.com | CONFIRMED | `src/registry.ts:15-16` (`REGISTRY = https://raw.githubusercontent.com/goodnight000/api-anything/main`) |
| `src/vet.ts`, `src/secrets.ts` exist | CONFIRMED and read | vet.ts = rules for shared specs; secrets.ts = credential scan |
| `sites/x.json`, `sites/x.md`: getUser, getProfile, no tweets | CONFIRMED | `sites/x.md:1,60-61` ("No tweets", "Logged out, `UserOriginalsTimeline` returns an empty 404"); `sites/x.json` has exactly two ops |
| browser-like UA and X's public bearer | CONFIRMED | `sites/x.json` ops carry `user-agent`, `sec-ch-ua*` and a literal `authorization`; `sites/x.md:27-30,46-48` |

## 4 Q-MAIN: can it learn and replay a logged-in X search on a throwaway account?

### 4.1 What the login flow does

| Question | Answer | Evidence |
|---|---|---|
| Default `login x` | tries to IMPORT cookies from the owner's everyday browser (reads its cookie DB, decrypts with the OS key) before any window | `src/cli.ts:310-312`, `src/login.ts:2-4,72-83`, `docs/REFERENCE.md` "Logging in" |
| On Windows | Chromium import is NOT supported (app-bound encryption); `browserRoots()` returns nothing for win32, so `login` falls back to the window | `src/import.ts:131-133` |
| Window flow | `login x --window`: opens a visible (headed) Chrome/Edge on api-anything's own profile at the site URL, polls cookies every 1 s, ends when the window is closed or Enter is pressed in the terminal; cookies of that site only are kept | `src/browser.ts:1240-1261`, `src/cli.ts:296` |
| Where it is stored | (1) `~/.api-anything/sessions/<site>.json`: cookies as plain JSON (name, value, domain, expiry), plus captured session values (tokens/headers); (2) `~/.api-anything/profile/`: the Chrome profile itself (Chrome's own cookie store, encrypted by Chrome/OS on Windows); (3) `~/.api-anything/captures/*.json`: full response bodies and the run's cookie values, newest 20, none older than 24 h | `src/session.ts:49,146,208,123-144`, `src/heal.ts:42,396` |
| Encryption of the session file | NONE by the tool (plain JSON) | `src/session.ts:208` |
| File permissions | dirs 0700, files 0600 via `mkdir`/`chmod`/`writeFile` mode. On Windows these mode bits do not give POSIX protection (NTFS ACL of the user profile applies): UNVERIFIED, Node behaviour, not tested | `src/session.ts:60-72` |
| Location override | `API_ANYTHING_HOME` | `src/session.ts:49` |
| Logs | cookie NAMES only are printed, never values | `src/login.ts:145-146` |

Consequence for us: the owner logs in by hand once with `--window` on the throwaway account. Never run `login x` without `--window` and never `--profile`: those read the owner's real browser cookies (section 10).

### 4.2 How a search op would be taught

Teaching is a human-run CLI step, not an adapter step (`docs/REFERENCE.md`, "Creating an operation from captured traffic"):

1. `api-anything capture "https://x.com/search?q=<example>&f=live" --example q=<value>` (runs the page in a browser under the throwaway session, lists candidate requests).
2. `api-anything add x searchTweets --trigger "https://x.com/search?q={q}&f=live" --example q=<a> --example2 q=<b> --match <host/path/graphql op> --extract <path> --pick <fields>`. Two examples are required so the learner can tell params from nonces; example values must be at least 3 characters and must appear in the request (`docs/REFERENCE.md:182`).
3. A date window must be encoded inside `q` (for example `$SOL since:2026-10-20 until:2026-10-21`), because params are substituted into the page URL. Whether X honours UTC day windows with those operators is an X fact, UNVERIFIED (SPEC A.1 already marks it a probe).
4. `add` learns the request from the browser's own traffic, so the page itself computes any per-request signature (nothing is reverse-engineered by the tool).

### 4.3 Which tier a search needs

Tiers (`docs/DESIGN.md:452-458`): 1 = Node `fetch` with the stored template and cookie jar; 2 = `fetch()` inside a real page; 3 = run the trigger in the browser and read the site's own response.

Evidence that X search is tier 3, not 1 or 2: the package's own probe notes say X's timeline GraphQL returned an empty 404 at tier 1 (with full headers and with a borrowed `x-client-transaction-id`) and at tier 2, "inference (unverified): this op needs a valid per-request `x-client-transaction-id`", and that only the SSR document or tier 3 got the timeline (`docs/research/live-probes.md:149-160`). The tool treats `x-client-transaction-id` as a session header (`src/secrets.ts:13`). A logged-in SearchTimeline call is the same family. My judgement: **tier 3, with high probability** (UNVERIFIED for search; nobody ran it).

### 4.4 Headless or hidden?

- `call` has no headed option. `openBrowser` defaults to `headless = true` (`src/browser.ts:241`); the only headed call site is the login window (`src/browser.ts:1261`). grep finds no `headless`/`headed` in `cli.ts`, `execute.ts`, `heal.ts`, `mcp.ts`. So tiers 2 and 3 always run headless.
- The docs say x.com blocks default headless: "Default headless is detectable, and x.com blocks it. The default headless UA is `HeadlessChrome/153...`, and `x.com/nasa` answers the document with 403" (`docs/research/live-probes.md:36-37`). The tool's countermeasure: it starts the browser once, reads its UA, and replaces `HeadlessChrome` with `Chrome` (`src/browser.ts:191-198`), caches it in `~/.api-anything/chrome-ua.json` (`src/browser.ts:210-230`) and passes it as `userAgent` for every headless context (`src/browser.ts:251-255`).
- Probed logged-out only, on a US IP, 27-09-26. Logged-in headless on X: UNVERIFIED. `docs/DESIGN.md:794` also warns that an imported session is the same session as the everyday browser and "heavy headless automation on it is avoided"; that is why `--window` (independent session) is the right choice for us.
- "Hidden" in the sense of no window: yes, headless is hidden. A visible window during collection is not available through `call`.

### 4.5 Cost of one replay (budget impact)

| Path | HTTP requests / page loads | Evidence |
|---|---|---|
| Tier 1 (only if the op were tier 1) | 1 request, per-site minimum gap 1 s inside one process | `docs/DESIGN.md:599`, `src/execute.ts:46-55` (`minIntervalMs`) |
| Tier 3 (expected for search) | 1 headless page load of the trigger URL; the page itself makes the many requests an X page makes (the docs' capture example for another site lists 38 requests (illustrative), and the package's probe measured a 3.18 MB document on x.com/nasa) | `docs/REFERENCE.md` capture example; `docs/research/live-probes.md:110` |
| Browser start | cold start of Chrome/Edge per call unless reused; the MCP server closes it after 3 s idle; the first headless call adds one extra browser start to learn the UA | `src/browser.ts:22,210-230` |
| Failure path | tier-1 replay + one resend of a read + replay of the example args + heal (rescan: fetch the page and up to 40 of its scripts, `src/heal.ts:947-951`; recapture: browser) + tier 3. Heal CANNOT be switched off by an option; `maxTier: 1` removes only the browser steps | `docs/DESIGN.md:436-446`, `src/execute.ts:373`, `src/heal.ts:1086-1098` |

Per call you get ONE response (pagination not modeled: `docs/REFERENCE.md:203`; an arg derived from another request such as a page-2 cursor "cannot be substituted", `docs/REFERENCE.md:179`; "an op extracts one value from one request", `docs/REFERENCE.md` limits). If one X result page holds about 20 posts (UNVERIFIED), a 40-post sample needs a scroll step in the trigger or a second op, neither shown anywhere in the package for X. The adapter must count posts from the returned `data` itself (our `x_daily_post_budget`), not trust the tool: the browser may load more posts than it returns.

### 4.6 What it returns

`CallResult { ok, class, data?, truncated?, tier?, healed?, ms, reason?, next? }` (`src/execute.ts:57-68`). `data` is whatever the op's `--extract`/`--pick` recipe selects, capped (`truncated` says so); fields are chosen at teach time. Whether tweet id, author, time, text and a language field can all be picked from SearchTimeline is UNVERIFIED.

### 4.7 Block, rate-limit and login-expiry signals (can our adapter get a reliable warning?)

Every call is classified into `ok | drift | auth | rate | blocked | input | error` (`src/classify.ts:6`); `refused` is added by `call`.

| Situation | What the tool reports | Evidence | Reliability for us |
|---|---|---|---|
| HTTP 429 / "rate limit" / "too many requests" text | `rate`, with Retry-After if sent | `src/classify.ts:89,222,370-372,480` | good for 429; X's own GraphQL rate error text matching the regex is UNVERIFIED |
| Bot wall (Cloudflare, Akamai, DataDome, PerimeterX, AWS WAF, reCAPTCHA, title wording) and a bare 403 | `blocked` | `src/classify.ts:35-62` and `docs/DESIGN.md:410` | good; X's own challenge pages are not in the vendor list: they would show as bare 403 = `blocked`, or as `drift`/`error` (UNVERIFIED) |
| Login expired / logged out | `auth` (401, login wording such as "Bad Authentication data", sign-in form, login redirect) | `docs/DESIGN.md:408`, `src/classify.ts:76-120` | good. Self-heal re-import applies only to sessions imported from a browser; a `window` session is NOT re-imported, so `auth` stays `auth` and the call returns a login hint (`src/login.ts:112-123`) |
| Suspension or account lock | no X-specific detection (grep for suspend/locked/unusual finds nothing in `classify.ts`) | `src/classify.ts` | weak: expect `auth`, `blocked`, `drift` or `error`; treat ANY non-`ok` class as a warning |
| Empty result | `ok` with `[]` only if the page shows structurally an empty list; otherwise `drift` with a "missing data" flag | `docs/DESIGN.md:406` | an empty search is ambiguous; adapter must treat "0 posts for a busy coin" as suspicious |
| Soft failure (HTTP 200 with a different page) | observed on Instagram: "Failure shows up as HTTP 200 with HTML, not as an error status" | `docs/research/live-probes.md` (Instagram table note) | the adapter needs its own canary: a result must have the expected fields, else treat as a warning |

Answer: **yes, the adapter gets a usable warning signal**, but only if it treats `class != "ok"` plus `healed == true` plus a shape/zero-count canary as warnings. It must not depend on the text of `reason`.

### 4.8 Drift (heal)

Order: replay stored template; on `drift`, replay the op's example args once to rule out "no such data"; then **rescan** (browserless: fetch the trigger page and up to 40 referenced scripts of the site, find the rotated id next to its anchor; skipped when the op has no volatile values, `src/heal.ts:932`); then **recapture** (run the trigger again in the browser and re-learn); a healed template is saved only after a replay succeeds, logged to `~/.api-anything/heals.jsonl`; loop guards: identical template is not drift, a second failure within 10 minutes marks the op stale for 30 minutes (`docs/REFERENCE.md` "Replay, fallback and repair"; `docs/DESIGN.md:445-447`). Heal is local and deterministic and talks only to the site (page, its scripts, the browser). It does **not** call an LLM (section 6). For us: `CallResult.healed === true` or repeated `stale` replies = one warning; a heal also costs extra page loads that count against the daily budget.

### 4.9 Verdict on Q-MAIN: UNPROVEN

| For | Against | Unknown (owner probe needed) |
|---|---|---|
| The engine is built for "learn from the browser's own traffic", which suits per-request signatures (tier 3) | The only shipped X recipe has no tweets and the notes say tweets are unreachable logged out (`sites/x.md:60-61`) | Does logged-in headless x.com/search work for a throwaway account (UA rewrite, 403)? |
| Window login works on Windows (import does not, window does) | Pagination is "not modeled" (`docs/REFERENCE.md:203`); 40-post sample may not fit one op | How many posts one result holds; can a scroll step or second op fetch more? |
| Tier/classification gives rate, blocked, auth signals | Tier 3 is headless-only via `call`; docs say x.com blocks default headless | Does `since:`/`until:` honour UTC day windows? |
| No LLM, no phone-home found | Project is 24 days old, v0.1.0, one active author | Does X lock or challenge the throwaway account after the first headless load? |

Not NOT FEASIBLE, because nothing read proves it cannot work. Not TEACHABLE, because no evidence anywhere shows a logged-in search recipe. Recommendation: run owner probes P-X3 and P-X4 (section 12) BEFORE W8d is dispatched.

## 5 SAFETY vetting items (SPEC Annex F)

| # | Item | Result |
|---|---|---|
| 1 | SHA pinned | `20cb677039fcfe92d3d9c777aa9362e30ff1fdb8`, committed 2026-10-20 18:32:27 -0700, "Share specs through the registry: pull what others learned, publish what you learned (#31)". `git rev-parse HEAD` in the clone printed this SHA. |
| 2 | Manifest hooks | Only `package.json` (no `pyproject`, `setup.py`). Hooks: `prepare` = `tsc -p tsconfig.build.json` (runs on a plain `npm install` in a git checkout and on `npm ci`; skipped by `--ignore-scripts`). No `preinstall`/`install`/`postinstall`. Lockfile flags `hasInstallScript` on `esbuild@0.28.2` (dev, via tsx) and `fsevents@2.3.3` (macOS optional) only; neither is a production dependency. |
| 3 | Dependencies | Production: `@modelcontextprotocol/sdk ^1.32.1` (locked 1.32.1), `node-html-parser ^9.0.4` (9.0.4), `playwright-core ^1.63.0` (1.63.0), `tldts ^7.4.16` (7.4.16), `zod ^4.6.5` (4.6.5); 108 production packages in the lock in total. Dev: `typescript ^7.0.2` (7.0.2), `tsx ^4.23.15` (4.23.15), `@biomejs/biome 2.5.15`, `@types/node ^26.6.3`. Dependency code was not read (not installed). |
| 4 | Lockfile | `package-lock.json`, lockfileVersion 3, 169 package entries: every entry has `integrity`; every entry has `resolved`; all 169 `resolved` URLs are on `https://registry.npmjs.org`. No git, file or other-host URLs. |
| 5 | Outbound hosts in `src/` | Literal hosts: `raw.githubusercontent.com` only (`src/registry.ts:16`; replaceable by `API_ANYTHING_REGISTRY`, https or localhost only, `src/registry.ts:19-24`). Computed hosts: whatever site a spec names (for X: `x.com`, `api.x.com`, and the hosts X's page itself loads in the browser); `gh api` talks to `api.github.com`/`github.com` (publish only). No analytics, telemetry or update host. |
| 6 | File / env / cookie reads and writes | See table 5.1. |
| 7 | Process spawning | See table 5.2. |
| 8 | Secret handling and logging | See section 7. |
| 9 | Licence | MIT, `LICENSE:1-3`. |
| 10 | Provenance | See section 5.3. |

### 5.1 Reads and writes

| Path / source | Read or write | By | Evidence |
|---|---|---|---|
| `~/.api-anything/` (or `API_ANYTHING_HOME`) | both | everything | `src/session.ts:49` |
| `sessions/<site>.json` (cookies plain JSON + session values) | both | login, call, heal | `src/session.ts:146,208` |
| `profile/` (Chrome profile) | both | tier 2/3, login | `src/heal.ts:42` |
| `captures/*.json` (bodies + cookie values, 20 max, 24 h) | both | capture, heal | `src/session.ts:126-144`, `src/heal.ts:396` |
| `sites/<site>.json` (user specs), `registry/` (pulled specs) | both | add, heal, pull | `src/store.ts:12-14,79-90`, `src/registry.ts:120-122` |
| `state.json`, `heals.jsonl`, `chrome-ua.json` | write | call, heal | `src/store.ts:129,148`, `src/browser.ts:228` |
| `outbox/` | write | publish | `src/publish.ts:123-124` |
| Other browsers' profile dirs and cookie DBs (Chrome, Brave, Edge, Arc, Vivaldi, Firefox) | READ (copies the DB to a temp dir `aa-cookies-*`, opens read-only with `node:sqlite`) | import only | `src/import.ts:103-133,149` |
| macOS Keychain "Safe Storage" password | READ | import only | `src/import.ts:136-139` |
| Chrome `Local State` (profile name, Google account email) | READ | import only | `src/import.ts:350-354` |
| A cookies file passed by `--cookies` | READ | login `--cookies` | `src/login.ts:78-79` |
| Environment | `API_ANYTHING_HOME`, `API_ANYTHING_BROWSER`, `API_ANYTHING_BROWSER_ROOTS` (tests), `API_ANYTHING_GH`, `API_ANYTHING_REGISTRY`, `HOME`, `XDG_CONFIG_HOME`, `LOCALAPPDATA`, `PROGRAMFILES`, `PROGRAMFILES(X86)` | | grep `process.env` in `src/` |

### 5.2 Process spawning

| Where | Runs | When | Evidence |
|---|---|---|---|
| `src/import.ts:139` | `security find-generic-password -w -s "<Browser> Safe Storage"` | cookie import from the everyday browser on macOS only | `execFileSync`, fixed argv |
| `src/publish.ts:151` | `gh api ...` (GitHub CLI, body on stdin), binary from `API_ANYTHING_GH` or `gh` | `publish` only; opens a public pull request under the owner's GitHub account | `src/publish.ts:3-4,136,147-158` |
| `src/browser.ts:67-71,194-195` (via playwright-core) | the installed Chrome/Edge/Brave/etc. executable, found at standard paths or `API_ANYTHING_BROWSER` | login window, tier 2/3, heal recapture, one extra start to read the headless UA | `src/browser.ts:82-157` |
| `src/cli.ts:887` | in-process MCP server over stdio (`serve`) | only if the owner runs `serve`; not a child process | `src/cli.ts:887` |

No other spawn, shell, `eval`, `new Function`, `vm` or worker usage in `src/`.

### 5.3 Provenance (honest)

| Fact | Value |
|---|---|
| First commit / latest commit | 2026-09-27 / 2026-10-20 (24 days) |
| Commits at the pinned SHA | 69 |
| Authors in git | `goodnight000` (44), `Tianjun Zheng` (22, one shared e-mail with a third name `Charles Zheng`, 1), `mxlogy-00` (2). The first three look like one person with several identities (inference, UNVERIFIED); one outside contributor. |
| Tags / releases | none (`git tag` empty); `package.json` version 0.1.0 |
| npm registry publication | UNVERIFIED (not checked; the package is meant to be used from the git checkout) |
| Self-description | early release; "Individual real sites vary and are not continuously verified" (`docs/REFERENCE.md`, Status) |
| CI | one workflow (`.github/workflows/ci.yml`), lint/typecheck/tests on Node 22 and 24; no security scanning seen |

Judgement: legitimate-looking, readable, defensive code (credential scanning, 0600 files, arg-vector spawns), but young, single-maintainer, no release discipline. That is why the SHA pin and a code-diff before every upgrade (Annex F) are mandatory.

## 6. Q4: does anything call a paid LLM or any network service? (exact answer)

- **LLM: none.** `grep -rniE 'anthropic|openai|claude|llm|gpt|sampling|createMessage|ANTHROPIC|api[_-]?key|telemetry|sentry|posthog|auto-?update|npm view'` over `src/` finds: the credential-name regexes in `src/secrets.ts:24` (detection only), analytics URL filters in `src/learn.ts:157-158,171,200,255,620` (used to IGNORE analytics beacons when learning), `src/outline.ts:3` ("Deterministic, no LLM"), and comments in `browser.ts`, `execute.ts`, `cli.ts`. No SDK client, no API key variable, no HTTP call to a model host. `src/mcp.ts` exposes tools to a calling agent and contains no model call. Repair is `rescan` then `recapture` (`src/heal.ts:1020-1098`), both deterministic. Any LLM cost would come from an AI agent that DRIVES the tool (the package ships `skills/api-anything/SKILL.md` for such agents); our adapter is code, not an agent, so self-repair LLM spend = 0 USD and the 15 USD monthly cap is not needed for this tool.
- **Network from heal:** the site's pages and scripts (rescan, at most 40 scripts, `src/heal.ts:947-951`) and the browser. Nothing else.
- **Phone home / telemetry / auto-update:** none found in `src/` (no host literal other than `raw.githubusercontent.com`, no update check, no counter). Caveat: the dependency code (notably `playwright-core`) was not read; its telemetry status is UNVERIFIED. `playwright-core` does not download browsers (the project says "no browser download", `docs/DESIGN.md` Browser section).

## 7. Secrets, logging, user agent and headers

### 7.1 Secret handling
Credentials are turned into references (`cookie:ct0`, `session:<name>`) in specs; the save-time scan refuses a spec that contains a live credential (`src/heal.ts:637-640`, `src/secrets.ts`); session values go only back to the host they were captured from (`src/session.ts:24-30`); `export` strips example values (`docs/REFERENCE.md` Safety). Cookie names only are printed (`src/login.ts:145-146`).

### 7.2 What can leak (not secret-safe)
- `captures/*.json` hold full response bodies and the run's cookie values for up to 24 h (`src/session.ts:123-144`).
- `sessions/<site>.json` holds cookie values in plain JSON.
- `heals.jsonl` and `CallResult.reason`/`next` carry URL paths and response snippets (160 chars, `src/classify.ts:snippet`); whether a query string with the search term appears is UNVERIFIED. Our adapter must log class, tier, healed flag and counts only, never `reason`/`next`/`data` text, and the project's log scrubber must run over any `reason` it keeps.
- stdout of CLI commands is JSON of results (`src/cli.ts:161`).

### 7.3 User agent and headers (rule: "honest user agent only for our own code")
| Layer | What it sends | Configurable? | Evidence |
|---|---|---|---|
| Tier 1 (Node fetch) | the headers stored in the op, which were copied from the browser that taught it: `user-agent`, `sec-ch-ua*`, `sec-fetch-*`, `accept*`, `accept-language`, plus X's public `authorization` bearer. The tool adds no UA of its own. | only by hand-editing the spec JSON; no flag or env var | `sites/x.json` headers; `src/learn.ts:505-511` (browser-computed headers kept as literals); live probe: Node's own default UA got a 404 (`docs/research/live-probes.md:149-153`) |
| Tier 2 / 3 headed | the installed browser's own UA | no | `src/browser.ts:254-256` |
| Tier 2 / 3 headless (always, via `call`) | the browser's real UA with `HeadlessChrome` rewritten to `Chrome` | NO (hard-coded `replace`, no env var or option) | `src/browser.ts:191-198,251-255` |

Conflict with our rule: X access through API Anything is by construction a real-browser identity, not an honest descriptive agent, and the headless rewrite removes the marker that announces automation. Our own code (Reddit feeds, probes) keeps `attention-probe/...`-style honest agents; the X side cannot. This is within what the owner already accepted for X (SPEC rule 8: no detection-evasion technique is part of the SPEC), but the rewrite is a detection-relevant step inside the tool. **The owner must explicitly accept this one behaviour, or X stays unbuilt.** I did no research on evasion and recommend none.

## 8. Registry, publish and import: how to guarantee the adapter never calls them

Library entry point (`package.json` `exports` allows only `"."` = `dist/index.js`; `src/index.ts:3-21` exports): `browserAvailable`, `browserChoice`, `closeBrowser`, `classify`, `call`, `heal`, `addOperation`, `capturePage`, `healOperation`, `learnOperation`, `rankCandidates`, `createServer`, `serveStdio`, spec types, `exportSite`, `listSites`, `loadSite`, `saveSite`. It does NOT export `pull`, `publish` (`plan`, `submit`), `importSession`, `login` or `logout`. Those are reachable only through the CLI (`src/cli.ts:22-27`, commands `login`, `pull`, `publish`) or by deep-importing a `dist/` file, which the `exports` map forbids for package imports.

| Allowed for the adapter | Never for the adapter |
|---|---|
| `call(site, op, args, { maxTier, allowWrites: false, timeoutMs, minIntervalMs })` from `dist/index.js` | the CLI `pull`, `publish`, `login` (without `--window`), `serve`, `heal`, `add`, `capture` |
| `closeBrowser()` after a unit | `addOperation`, `capturePage`, `healOperation`, `heal` (teach/repair belongs to the owner, run by hand) |
| `browserAvailable()` as a preflight | `createServer`, `serveStdio`, `saveSite`, `exportSite` |
| | any import of `registry`, `publish`, `import`, `vet` files |

Guarantees to build in W8b/W8d (the wrapper, a guard test per SPEC AC27):
1. A fixed allowlist of one site name and one op name (for example `x` / `searchTweets`); refuse anything else, including the bundled `getUser`/`getProfile`.
2. Always `allowWrites: false`.
3. Run Node with `API_ANYTHING_REGISTRY=http://127.0.0.1:9` (accepted by `src/registry.ts:19-24` because loopback http is allowed, so a stray pull cannot reach GitHub) and `API_ANYTHING_GH=<path that does not exist>` (so a stray publish fails at spawn, `src/publish.ts:136,156`).
4. Dedicated `API_ANYTHING_HOME` (own folder on the owner's PC) and `API_ANYTHING_BROWSER` pinned to the installed Chrome or Edge path (`src/browser.ts:159-190`).
5. Delete the bundled `sites/` JSON and notes in the owner's working copy before the build, so no pre-learned recipe can be called or silently become the base of the learned spec (`src/store.ts:22-26,29-57,79-90`: lookup order is user, registry, bundled; `updateSite` copies the bundled spec into the user copy when an op is added to site `x`). The code tolerates a missing/empty folder (`existsSync` checks, `src/store.ts:70-78`; behaviour with an empty dir not run: UNVERIFIED).
6. Treat `class != "ok"`, `healed == true`, `tier` above the expected one, and a zero/short result as warnings (section 4.7).

## 9. Install plan

| Step | Detail |
|---|---|
| Node | `>=22.13.0` required (`package.json` engines; `node:sqlite` used by import only). The owner's Node version is UNKNOWN: probe P-X5. |
| Fetch | `git clone --no-checkout`, then `git checkout --detach 20cb677039fcfe92d3d9c777aa9362e30ff1fdb8`, then compare `git rev-parse HEAD`. |
| Install | `npm ci --ignore-scripts` is feasible: the lock is complete and registry-only. With scripts disabled `prepare` does not run, `esbuild`'s optional install script is skipped (it only optimises; tsx may then be slower or fail to use the native binary: UNVERIFIED, irrelevant because tsx is not needed to run `dist`), and `fsevents` is macOS-only. `npm ci` includes dev dependencies, which the build needs (`typescript`). |
| Build | separate reviewed step by the owner: `node node_modules\typescript\bin\tsc -p tsconfig.build.json` (TypeScript 7.0.2; whether that path exists in TS 7 is UNVERIFIED, else `npm run build`, which runs only `tsc -p tsconfig.build.json`). This executes the dev-dependency compiler, not package install hooks; the compiled `dist/` is then the code that runs. |
| Audit before use | `npm audit signatures` or compare the `integrity` hashes already in the lock; read `git diff <oldSHA> <newSHA> -- src package.json package-lock.json` before any upgrade. |
| Browser | `playwright-core` ships no browser and the tool launches the owner's installed Chrome or Edge by path (`src/browser.ts:82-157`; Windows paths under `LOCALAPPDATA`/`PROGRAMFILES`/`PROGRAMFILES(X86)` for Chrome, Edge, Chromium). No download. Pin with `API_ANYTHING_BROWSER`. |
| Run isolation | first run in Windows Sandbox or a throwaway VM with no secrets (Annex F), then on the PC with a dedicated `API_ANYTHING_HOME`. Chrome locks its profile to one process; a second process waits 15 s then fails (`docs/REFERENCE.md:196`), so X units must be serialized. |
| Windows notes | cookie import unsupported (window login only); POSIX file modes are not an access control on NTFS (UNVERIFIED); do not run `login` without `--window`. |
| Disk | not measured (not installed). Estimate 150 to 300 MB for dependencies plus the Chrome profile and captures; UNVERIFIED. |

## 10. Verdict

**Safety: usable with changes. Capability: UNPROVEN.** Together: do not dispatch W8d until the owner probes P-X3 and P-X4 pass. If they fail, X falls to the unbuilt official-API option D already recorded in SPEC Annex E.

Changes required (all listed above; none requires editing package code):
1. Pin `20cb677039fcfe92d3d9c777aa9362e30ff1fdb8`; install with `npm ci --ignore-scripts`; build as a separate reviewed step.
2. Remove the bundled `sites/` copy in the local checkout; relearn on the throwaway account.
3. `login x --window` only; never `login x`, never `--profile`, never `--cookies` of the main account.
4. Dedicated `API_ANYTHING_HOME`; `API_ANYTHING_BROWSER` pinned; `API_ANYTHING_REGISTRY` loopback; `API_ANYTHING_GH` invalid.
5. Wrapper calls only `call` (plus `closeBrowser`, `browserAvailable`) with an allowlist; guard test (AC27).
6. Owner accepts, or rejects, the headless user-agent rewrite (section 7.3). If rejected, X is not built through this tool.
7. No logging of `reason`, `next`, `data` text; counts and classes only; purge `captures/` after each day.

## 11. What the adapter wrapper (`api/data/attention/pc_adapter.py` Protocol, W8b) must enforce

| Rule | Why |
|---|---|
| Protocol method returns a small typed result: `status` (one of `ok`, `rate`, `blocked`, `auth`, `drift`, `input`, `error`, `refused`), `posts` (id, UTC time, language, author id, text length or hash; no cookies, no URLs with queries), `healed`, `tier`, `n_loaded`; tests use a fake adapter | AC26 to AC28 |
| Any non-`ok`, any `healed`, any empty/short result on a coin that normally has volume = warning: pause X for the rest of the UTC day, persist, no retry | Locked pacing rule 3, Annex D |
| Daily budget counted from posts returned by the adapter, plus a fixed allowance per heal | section 4.5 |
| One unit at a time, single process, own lock, `closeBrowser()` after each unit | profile lock, rule 10 |
| Refuse every op name except the allowlist; refuse registry/publish/import/login/serve paths; `allowWrites` hard-coded false | rule 12, AC27 |
| Environment set by the wrapper (items 3 and 4 of section 8) and asserted in a test | defence in depth |
| Never read `~/.api-anything/sessions` or `profile` | secret hygiene |
| `login` and teaching are owner-run manual steps, not wrapper functions | scope |

## 12. Owner probes still needed (PowerShell; nothing from the package is executed, only git and system commands)

Already recorded: P-X1 and P-X2 (inputs). New, in order:

- **P-X5 (Node and disk):** `node --version` and `Get-PSDrive C | Select-Object Used,Free`. Needs Node 22.13 or newer.
- **P-X6 (SHA and lock, read-only; replaces trust in section 5):**
  `git -C C:\vet\apianything rev-parse HEAD` must print `20cb677039fcfe92d3d9c777aa9362e30ff1fdb8`, then
  `(Get-Content C:\vet\apianything\package-lock.json | Select-String '"resolved"' | Where-Object { $_ -notmatch 'registry.npmjs.org' }).Count` must print `0`, then
  `(Get-Content C:\vet\apianything\package-lock.json | Select-String '"integrity"').Count` must print `169`.
- **P-X7 (browser):** `Test-Path "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"`, `Test-Path "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"`, `Test-Path "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"`. At least one `True`.
- **P-X3 (can the throwaway see a search at all; no package):** in the browser on the PC, signed in to the throwaway account ONLY, open `https://x.com/search?q=%24SOL%20since%3A2026-10-20%20until%3A2026-10-21&f=live` once, by hand. Report: do posts show, how many before scrolling, are they newest first, and do `since:`/`until:` appear to follow UTC days. (Facts the vetting could not read from the package.)
- **P-X4 (teach and replay, only after the owner accepts section 7.3 and 10 items 1 to 7, ideally in Windows Sandbox):** after `git checkout --detach 20cb677...`, deletion of `sites\*`, `npm ci --ignore-scripts`, reviewed build, with `$env:API_ANYTHING_HOME="C:\aa-home"`, `$env:API_ANYTHING_REGISTRY="http://127.0.0.1:9"`, `$env:API_ANYTHING_GH="C:\nope\gh.exe"`, `$env:API_ANYTHING_BROWSER="<chrome or msedge path>"`: `node C:\vet\apianything\dist\cli.js login https://x.com --window` (sign in with the throwaway), then `capture` and `add ... searchTweets` per section 4.2, then `call` the op three times with different `q` and report only: `ok`, `class`, `tier`, `healed`, `ms`, and the number of posts. Do not paste cookies, tokens or post text.
- **P-X8 (headless block check):** repeat one `call` and note whether `class` is `blocked` or `auth` on the first headless call (the UA-rewrite question). Stop at the first non-`ok` and report; no retries.

## 13. Gates (run before the PR)

- The banned-names grep from the envelope over this report: no hits (the names are not written anywhere in it).
- `git diff --name-only origin/main...HEAD`: this file only.
- No secrets in the file (no cookie, token, key or private URL; the public bearer in `sites/x.json` is NOT reproduced).
- No `.github/` file touched.

## 14. UNVERIFIED list (consolidated)

1. Any live X behaviour: logged-in search, headless acceptance, `since:`/`until:` UTC windows, posts per result page, field availability, lock or challenge after first load.
2. X's own rate/challenge wording matching `classify.ts` patterns.
3. Dependency code (playwright-core, sdk, others): not read; telemetry status unknown.
4. NTFS protection of `sessions/*.json` and `profile/`.
5. Behaviour with an empty `sites/` directory and with `tsc` in TypeScript 7 via the path shown.
6. Disk footprint; the owner's Node version.
7. Whether the three git identities are one person; whether the package is on npm.
8. Whether a search term appears in `reason`/`heals.jsonl` text.
