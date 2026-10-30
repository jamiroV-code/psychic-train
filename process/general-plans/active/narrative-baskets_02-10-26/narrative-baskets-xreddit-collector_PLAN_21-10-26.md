---
name: plan:narrative-baskets-xreddit-collector
description: "T131 FAST MODE PLAN and VALIDATE for the T126 SPEC (X and Reddit PC-side collector, slow trickle, yesterday-only): slices W8a..W8h in the owner's order (Reddit first, X after probes), files, red tests, gates, models, USD, owner PowerShell probes, branches, dependencies. Docs only; no code changed."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# X and Reddit PC-side collector: PLAN (W8a..W8h)

[MODE: VALIDATE]

Date: 21-10-26
Complexity: COMPLEX (eight slices, two providers, a worker; each slice is one EXECUTE envelope)
Status: VALIDATED: Gate: PASS (re-validated T179; the PLAN artifact; per-slice execution gates are the contract for later EXECUTE)
Validation: T131 (FAST MODE: SPEC amendment, PLAN, VALIDATE in one session), 21-10-26, branch base `main` 007d53c. Next step: the owner's separate ENTER EXECUTE MODE per slice, starting with W8a. This session builds nothing.

**Summary:** **SPEC:** `narrative-baskets-xreddit-collector_SPEC_21-10-26.md` (T126, amended by T131, T133, T135, T136, T138, T139, T163, its two addenda, T166, T167, T168, T170 and T179; status APPROVED (locked) by the owner on 21-10-26, recorded on the planner's message; each slice still needs the owner's own ENTER EXECUTE MODE). Config pace (X default one coin unit per 3-6 min, Reddit one request per 60-120 s from the public RSS feeds, 150 per day (T138)), daily X read budget 800 posts with sample N 40 (about 20 coins per day), adaptive halving, yesterday-only values, pause on any warning, narrative coins only, throwaway X account, Reddit first (amended T133). Every provider (X, Reddit, API Anything) is unreachable from the build container: live behaviour is UNVERIFIED and proven only by owner probes.

## Overview and Context

Context router: `process/context/all-context.md`; tests: `process/context/tests/all-tests.md`. Phase Completion Rules: a slice is done when its red tests are green, its gates pass, its report lists the owner probes it needs, and (for X) the probes have been run by the owner.

**Generic W8 worker (T98 section W8, Q9): checked on 21-10-26, it does NOT exist on `main`.** `git ls-tree` of `origin/main` has no `attention_pc_refresh` module; a grep for `SCREENER_ATTENTION_PC_WORKER` and `fetch_side` in `api/*.py` finds nothing; `api/main.py:48-58` (lifespan) starts only `refresh_worker` and `equities_refresh`. So W8e builds the worker shell (modelled on `api/data/equities_refresh.py`: `PASS_LOCK` line 56, `_behind` 231, `start_from_env` 361, `stop_worker` 388) and plugs these two sources in. If the planner dispatches the T98 W8 slice first, W8e shrinks to "register the sources, add trickle and pause". Do not build two workers.

## 1. Goal and non-goals

**Goal.** Fill the `xsearch` (weight 10) and `reddit` (weight 15) slots of the weighted signal from the owner's PC without official APIs, as `pc_side` sources, by the SPEC's metrics (Annex A), pacing (Locked pacing rules) and failure rules (Annex D).

**Non-goals.** `.github/` (none of the slices touch it; see section 4), GitHub dev activity, Trends, exchanges, official X or GitHub APIs, the official Reddit API, sentiment, detection-evasion of any kind, installing or running API Anything in this session, editing the SPEC after the owner approves it.

## 2. Owner decisions binding on this PLAN

| # | Decision (owner via planner, T131) | Effect |
|---|---|---|
| 1 | Trickle with config pace: `x_query_delay_min_s`/`x_query_delay_max_s` (default 180/360), never faster than the configured minimum on catch-up; Reddit about one request per 60-120 s, 150 per day, public RSS feeds (T138) | W8b scheduler core and its tests; W8e uses it |
| 1b | Daily read budget `x_daily_post_budget` 800, sample `x_sample_n` 40, `x_sample_min` 20, `x_page_cap` 3; adaptive halving after a warning day, doubling after 7 clean days (T133) | W8b budget and adaptive state and tests (AC21, AC22); W8d spends it; W8e persists it |
| 1e | Owner answers (T136): SPEC APPROVED (locked) on 21-10-26; Q13 yes (rotation score = newest of the latest 3 stored values against the mean of the other 2; `x_rotation_max_lag_days` 7); Q14 yes (X and Reddit concurrent, per-source locks) | W8e, W8f; no longer open |
| 1d | Owner answers (T135): shorter 3-6 min delay confirmed; Q10 rotation mode for X (latest 3 stored values; locked, built in W8f); PC on about 1-3 h per day (pace and budget must fit; X about 90 min, Reddit concurrent); Reddit numbers unchanged. The owner is still reading the SPEC and has NOT approved it | W8b, W8e, W8f |
| 1f | Owner decision 24-10-26 (T163 addendum 1): a spare laptop running 24/7 is the target host; baseline schedule (X units spread over the day at a 3-6 min minimum spacing, Reddit searches spread over the day with `t=week`, comments feeds every 2 h, posts feeds every 6 h, enrichment once a day); the T135 small-window behaviour is DEGRADED MODE for outages and the interim; the X read budget (800 posts, N 40) stays the binding limit | W8b scheduler modes, W8c, W8c2, W8c3, W8d, W8e; new slice W8e2 |
| 1g | Owner principle 24-10-26 (T163 addendum 2): quality over speed; nothing dropped, shrunk, shortened or cut to fit a time budget; completeness reported per source-day; cross-source host profile is the separate audit task T164 | W8b evidence fields, W8e, W8e2, W8g; hard stop in section 7 |
| 1h | T166 (24-10-26): X design 'learn from both, make the best of it'; throwaway account only; ban and terms-of-service risk accepted; focus only on quality data; 24/7 server available. I chose twscrape as the X primary behind a reader interface and demoted API Anything to an optional fallback (not built unless twscrape fails); Q20 is recorded as recommended, awaiting owner | W8a2, W8d1, W8d2; AC41-AC48; the owner's approval of T166 is not recorded |
| 1i | T167 (24-10-26): the owner WANTS the twscrape account pool and rotation (2-3 throwaway accounts to start, cookie login); this reverses my T166 'single account' line; LRU or round-robin order logged; a ban or logout code marks that account inactive and the pool continues; pause the day only at zero active accounts; one unit by one account end to end, label in the sidecar; daily cross-account canary; the 800-post budget stays GLOBAL; clean restart on another account without double counting; startup lock cleanup; health active over total; P-X9 per account; still no proxy, no user-agent override, no curl backend, no auto-update | W8d1, W8d2, W8e2; AC41, AC46, AC47, AC49-AC52; the owner's approval of the T166 and T167 changes is not recorded |
| 1j | T168 (24-10-26, owner decisions): Q20 accept all four; Q25 two accounts now (third after a clean fortnight); Q26 least recently used; Q27 25 percent and 0.6; Q24 YES: twscrape's curl-cffi backend is allowed ONLY as a Cloudflare fallback behind the owner flag `x_allow_curl_backend` (default false), used once after a Cloudflare or HTML block on the default backend, never for anything else, logged in the evidence and the health line, then the UTC day is paused if still blocked; curl_cffi is vetted in W8a2 and pinned in the optional group by W8d2. This is the single narrow exception to the no-evasion lines | W8a2 (vetting, 3-4 USD), W8d1 (decision logic), W8d2 (6-8 USD); AC53; the owner's approval of the T166-T168 changes is not recorded |
| 1k | T170 (24-10-26): the W8a2 vetting report (T169, PR #169, VIABLE-WITH-CONDITIONS, SHA `63f61a518e576ea5c132f1156c03dda0520d76c1`) is applied: pin by commit id (the version string 0.20.1 is no guard); design A (one SQLite file and one API per account; failover only in our code); raising switches and the NoAccountError cause from the pool row; raw-page read accounting and `x-rate-limit-*` headers; our own LRU and UTC-day locks and no `reset_locks`; parse-drop guard; environment and files guard; wrapped surface; curl fallback in a separate process with the hash-pinned `curl_cffi==0.16.3` wheel and the `Blocked by Cloudflare` trigger only; P-X9 rewritten | W8d1 (6-7 USD), W8d2 (7-9 USD); AC41, AC43, AC46, AC47, AC49, AC50, AC52, AC53 reworded; AC54-AC55 |
| 1l | T179 (24-10-26, owner answers): Q29 decided BOTH (the host OS is not decided: the Windows and the Linux `curl_cffi==0.16.3` wheel hashes are both pinned; W8d2's installer picks by platform, the startup guard verifies the installed wheel hash against the matching entry and refuses an unknown platform; the W8e2 guide covers Windows and Linux, final choice there); the curl fallback trigger is Cloudflare OR HTML (Q30): `Blocked by HTML` also triggers it, with the same limits (flag default false, one retry in a separate process then pause the UTC day, never for rate-limit, login or ban codes, logged in the evidence and the health line) | W8d1 (decision logic wording), W8d2 (installer, startup guard, hash table), W8e2 (both OS); AC53; rule 19; the owner's approval of the T166-T179 changes is not recorded |
| 1c | Throwaway X account only; official X counts route is a recorded, unbuilt fallback (option D); Q10 rotation rule flagged to the owner, not implemented (T133) | W8d precondition; no code for option D or rotation |
| 2 | Yesterday-only, one day late, today's partial day never stored or shown | W8b window rule; AC1 |
| 3 | Rate-limit, login or suspension warning pauses that source for the rest of the day, no retries; pause persisted | W8b pause state; W8e restart test |
| 4 | Narrative coins only first (Q3); short backfill (Q2); Reddit first, X later after probes; self-repair spend cap 15 USD per month (Q4); both Reddit series kept separate, config picks (Q7) | slice order, W8b cap meter, W8f `source_impl` |
| 5 | No detection-evasion techniques | hard stop in section 7 |

**PLAN rulings where the SPEC is silent (the owner may overrule at EXECUTE approval):**
- R-1 Probe tool: `api/scripts/probe_pc_sources.py` is created in W8b with the argument parser and the reporting helpers (class name, HTTP status, numbers only, shared with the log scrubber); W8c adds Reddit modes; W8d adds X modes. W8a ships NO code (vetting report only, as the planner ordered); the SPEC's Annex H row for W8a that mentioned a probe skeleton is superseded by this ruling.
- R-2 Branches: `claude/<task-id>-<slug>` with the task id the planner assigns; proposed slugs per slice below.
- R-3 Evidence sidecar and pause state live under the cache root (`attention/<source>/_meta/`, `attention/_pc_state/`), which is git-ignored (`api/data/cache/*`, `.gitignore`), so no machine state is committed.
- R-4 API Anything is invoked only for X, through an adapter Protocol (`api/data/attention/pc_adapter.py`); tests use a fake adapter; the real adapter file is added in W8d only after W8a pins the commit. Reddit (W8c) is plain HTTP on the public RSS feeds with one honest user agent: no adapter, no API Anything, no login (T138).

## 3. Design summary (what each new file is; paths proposed, UNVERIFIED until EXECUTE)

| File (all new unless marked edit) | Slice | Content |
|---|---|---|
| `api/data/attention/density.py` | W8b | the SPEC A.1 formula (exact, capped, floor, page-cap, below-min), pure |
| `api/data/attention/pc_pace.py` | W8b | trickle scheduler core: next-unit time from a seeded RNG using config delays, daily read budget (posts read), adaptive effective budget (halve after warning, double after 7 clean days), priority queue (yesterday first, then backfill), pause state with persistence; injected clock |
| `api/data/attention/web_queries.py` and `api/data/attention_queries.json` | W8b | per-coin X query terms and Reddit terms, ambiguity list, subreddit list, and the collector config block (`x_query_delay_min_s`, `x_query_delay_max_s`, `x_daily_post_budget`, `x_sample_n`, `x_sample_min`, `x_page_cap`, `reddit_request_delay_min_s`, `reddit_request_delay_max_s`, `reddit_daily_request_budget`) with validator (positive numbers, min <= max, sample_min <= sample_n); coin set derived from `attention_narratives.json` |
| `api/data/attention/web_evidence.py` | W8b | evidence sidecar rows (n, span_hours, capped, pagecap, spike, method version, collected_at, backfilled) |
| `api/data/attention/pc_adapter.py` | W8b | adapter Protocol, error classes, fake adapter for tests, cost meter (monthly 15 USD cap) |
| `api/scripts/probe_pc_sources.py` | W8b (Reddit modes W8c, X modes W8d) | owner probe, prints numbers and class names only |
| `api/data/attention/reddit_web.py` | W8c | Reddit connector: plain HTTP on public RSS feeds, honest user agent constant, Atom parser with DOCTYPE/size/non-Atom rejection, per-day counts (A.2) |
| `api/data/attention_pc_refresh.py`, edit `api/main.py` lifespan, edit `api/data/discovery.json` (`fetch_side`) | W8e | worker shell, flag `SCREENER_ATTENTION_PC_WORKER`, `_behind` start, trickle, pause |
| edits to `api/analytics/attention/discovery.py`, `sources.py`, `api/data/attention/registry.py`, `api/models/discovery.py` | W8f | `source_impl`, `fetch_side` validation, reasons on the Sources row, backfilled flag |
| `web/components/narrative/` status text (edit only) | W8g | reason text and updating state |
| `api/data/attention/xsearch_web.py` | W8d | X connector (login command, hidden run, windows, canary, breaker) |

## 4. Slices, order, gates (Reddit first)

`.github/`: NO slice touches it. The two existing workflow guards (`api/tests/tooling_guards/test_attention_workflow_guard.py`, `api/tests/scripts/test_ci_workflow.py`) must stay green. If any slice finds it needs a `.github/` edit (for example to stop the GitHub job fetching a `pc_side` source), it stops and reports; the owner's approval comes first.

| Order | Slice | Branch (proposed) | Depends on | Owner ENTER EXECUTE MODE | Model, effort | USD (ask at 7, cap 15) |
|---|---|---|---|---|---|---|
| 1 | W8a vet API Anything (report only; gates X, W8d, only) | `claude/<id>-w8a-vet-apianything` | owner approves SPEC (done) | yes, own | sonnet, medium | 2-3 |
| 1b | W8a2 vet twscrape (report only) | `claude/<id>-w8a2-vet-twscrape` | owner approves the SPEC change (T166); Q21 answered | yes, own | sonnet, medium | 3-4 (DONE 24-10-26, T169, PR #169, VIABLE-WITH-CONDITIONS) |
| 2 | W8b pure core | `claude/<id>-w8b-collector-core` | none (can start now; W8a gates only W8d) | yes, own | opus, medium | 6-8 |
| 3 | W8c Reddit connector (incl. item ledger and mention metrics) | `claude/<id>-w8c-reddit-web` | W8b; none on W8a; probes P-R6, P-R3, P-R4, P-R7 (before, owner runs now), P-R2, P-R5 (after) | yes, own | opus, medium | 3-4 |
| 3b | W8c2 Reddit stream-and-count complement (posts and comments feeds) | `claude/<id>-w8c2-reddit-stream` | W8b, W8c (reuses its feed parser and ledger); none on W8a; Q17 answered | yes, own | opus, medium | 3-4 |
| 3c | W8c3 Reddit engagement enrichment via archive ids (optional) | `claude/<id>-w8c3-reddit-engagement` | W8c (posts); W8c2 for live comment enrichment; probe P-R8 passed; Q18 answered | yes, own | opus, medium | 3 |
| 4 | W8e worker wiring | `claude/<id>-w8e-pc-worker` | W8b, W8c (or an existing W8 worker) | yes, own | opus, medium | 4-6 |
| 5 | W8f Discovery wiring (incl. X rotation mode) | `claude/<id>-w8f-discovery-wiring` | W8e, W8c | yes, own | opus, medium | 3-4 |
| 5b | W8e2 server host guide and health line | `claude/<id>-w8e2-host-guide` | W8e, W8f | yes, own | sonnet for the guide (Windows and Linux), opus for the health code, medium | 3-5 |
| 6 | W8g web status text | `claude/<id>-w8g-web-status` | W8f | yes, own | opus, low | 1-2 |
| 7 | W8d1 X pure core for twscrape (incl. account-pool logic) | `claude/<id>-w8d1-x-core` | W8b; W8a2 verdict; Q21-Q23 and Q26-Q27 answered | yes, own | opus, medium | 6-7 |
| 7b | W8d2 X reader (twscrape wrapper, pinned optional group) | `claude/<id>-w8d2-x-reader` | W8d1, W8e, W8a2; P-X9 recorded; Q1, Q24 and Q25 answered; owner approval for `api/pyproject.toml` and `api/uv.lock` | yes, own | opus, high | 7-9 |
| 8 | W8h owner guide and closeout | `claude/<id>-w8h-closeout` | W8c live (Reddit) and, when built, W8d | yes, own | sonnet, low | 1 |

Total about 45-60 USD (thirteen slices: W8a, W8a2, W8b, W8c, W8c2, W8c3, W8d1, W8d2, W8e, W8e2, W8f, W8g, W8h; T166 replaced W8d by W8a2, W8d1 and W8d2; T163 widened W8c and W8c2, added W8c3, and its addenda added the 24/7 baseline, W8e2 and the quality-over-speed rule). W8b and W8c can start without waiting for W8a; W8a stays first only for X (W8d); W8c and W8d are independent after W8b; the order puts X last by the owner's decision. After W8g the Reddit source can be live while X does not exist yet.

### File ownership and collision proof

Slices touch disjoint new files except these shared edits, which are serialised by the order above: `api/data/discovery.json` (W8e adds `fetch_side`; W8f adds `source_impl`), `api/scripts/probe_pc_sources.py` (W8b creates, W8c and W8d append their own modes in separate functions), `api/main.py` (W8e only), `api/analytics/attention/discovery.py` and `sources.py` (W8f only). Open PRs touching those files at EXECUTE time must be checked by the planner at dispatch (`git diff --name-only origin/main...<branch>` against each open branch); this session did not check other open PRs.

## 5. Per-slice detail

### W8a: vet API Anything (report only, sonnet)

**T138 scope change:** W8a now gates only X (W8d). Reddit (W8b, W8c) does not wait for it.

**Envelope readiness (T136):** W8a is first (for X) and is READY to dispatch as a docs-only, report-only envelope (sonnet, medium, branch `claude/<id>-w8a-vet-apianything`, one draft PR, never merge), with one precondition: the owner pastes the output of the P-X2 commands below, because `goodnight000/api-anything` is outside the worker's GitHub scope (the planner may instead grant read access with `add_repo`, which is better). With only the paste, W8a can vet the commit SHA, the manifest hooks, the dependency list, the licence file name and the outbound-host and process-spawn greps; it cannot read the code paths the adapter will call, so the verdict is capped at `usable with changes` or `UNVERIFIED (code paths not read)` unless the repo is attached. The owner's separate ENTER EXECUTE MODE is still required. No `.github/` file is touched.

**Owner commands, again, exactly (PowerShell, from any folder; nothing from the package is installed or run):**
1. P-X1: `curl.exe -s -o NUL -w "%{http_code}\n" https://x.com/`
2. P-X2: `git ls-remote https://github.com/goodnight000/api-anything HEAD` then `git clone --no-checkout https://github.com/goodnight000/api-anything C:\vet\apianything` then `git -C C:\vet\apianything checkout --detach <SHA from ls-remote>` then `Get-ChildItem C:\vet\apianything -Recurse -Include package.json,pyproject.toml,setup.py,setup.cfg,requirements*.txt | Select-String -Pattern "postinstall|preinstall|prepare|cmdclass|console_scripts|bin"`
3. P-R1 (RECORDED 21-10-26, nothing to run): `search.json` = HTTP 403 with a block page of about 190 KB, so JSON is closed; Reddit now uses the public RSS feeds and W8a no longer covers Reddit (the owner's Reddit probes are P-R6, P-R3, P-R4 in section W8c).
4. P-X2b (optional, read-only, makes a paste-only vetting possible): `git -C C:\vet\apianything ls-tree -r --name-only HEAD` and `Get-ChildItem C:\vet\apianything -Recurse -File -Include *.py,*.js,*.ts | Where-Object FullName -notmatch "node_modules|\\\.git\\" | Select-String -Pattern "child_process|subprocess|os\.system|eval\(|exec\(|https?://" | Select-Object -First 200 Path,LineNumber,Line`

The owner pastes the output only; it contains file names, line numbers and source lines, never secrets.

**Inputs already known (T139; owner-run P-X2 paste on 21-10-26; INPUTS, NOT A VERDICT, to be confirmed by W8a):**
- The owner pinned commit `20cb677039fcfe92d3d9c777aa9362e30ff1fdb8` on 21-10-26. W8a's report states that every fact it uses comes from that SHA (the owner confirms with `git -C C:\vet\apianything rev-parse HEAD`).
- Language: Node and TypeScript. `package.json` has `bin` and `prepare` = `tsc -p tsconfig.build.json`; no `preinstall` and no `postinstall` hooks.
- `child_process` appears only in `src/import.ts` (`execFileSync`) and `src/publish.ts` (`execFile`). `src/registry.ts` pulls from `raw.githubusercontent.com`. `src/vet.ts` and `src/secrets.ts` exist and are unread.
- `sites/x.json` and `sites/x.md` ship a pre-learned X recipe. W8a reads `x.md` (the owner pastes its first 80 lines) but does NOT trust it: the recipe is relearned on the owner's PC.
- LICENSE is unread so far.
- Rules W8a must confirm against the code and the adapter must enforce (SPEC rule 12, AC27): registry pull and publish OFF (never call `registry.ts` or `publish.ts` paths; the wrapper refuses them; a guard test proves it); only self-learned recipes; when an install is needed, `npm ci --ignore-scripts` from the pinned commit, and the `prepare` build is run by the owner or a reviewed command, not as an install hook.
- Extra owner commands for the remaining unread pieces (read-only; paste the output): `git -C C:\vet\apianything rev-parse HEAD`; `Get-Content C:\vet\apianything\sites\x.md -TotalCount 80`; `Get-ChildItem C:\vet\apianything -Filter LICENSE* | ForEach-Object { $_.Name; Get-Content $_.FullName -TotalCount 5 }`; `Get-Content C:\vet\apianything\package.json`; `Get-Content C:\vet\apianything\src\registry.ts -TotalCount 80`; `Get-Content C:\vet\apianything\src\publish.ts -TotalCount 80`.

- **Files:** one report `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-w8a-apianything-vetting_REPORT_<dd-mm-yy>.md`. No code, no install, nothing from the repo is executed.
- **Method (SPEC Annex F):** write down one commit SHA; read the manifest(s) for install, postinstall, prepare, build hooks; list dependencies and versions; read only the code paths the adapter will call (request replay, tier 3 browser launch, self-repair network calls and any file, cookie or env access); list outbound hosts; licence; verdict `usable` / `usable with changes` / `not usable`; decide the adapter shape; answer "does self-repair call a paid LLM".
- **Red-first:** not applicable (docs). **Gate:** the report has the 8 vetting items filled or "UNVERIFIED because X"; `grep -rniE "xscrape|kloxeld|gunkonchi"` over the report finds the name only inside a "banned" sentence.
- **Owner probes (PowerShell, nothing executed from the package):**
  - P-X1: `curl.exe -s -o NUL -w "%{http_code}\n" https://x.com/`
  - P-X2: `git ls-remote https://github.com/goodnight000/api-anything HEAD` then `git clone --no-checkout https://github.com/goodnight000/api-anything C:\vet\apianything` then `git -C C:\vet\apianything checkout --detach <SHA>` then `Get-ChildItem C:\vet\apianything -Recurse -Include package.json,pyproject.toml,setup.py,setup.cfg,requirements*.txt | Select-String -Pattern "postinstall|preinstall|prepare|cmdclass|console_scripts|bin"`
  - P-R1: recorded (HTTP 403, block page); see W8c for the feed probes.
- **Note:** the worker session may not have GitHub scope for the API Anything repository (it did not in T126); the planner must grant `add_repo` for reading, or the owner pastes the P-X2 output.

### W8b: pure core (opus)

- **T163 addenda (24/7 host, quality over speed):** the scheduler core has two modes with injected clocks: BASELINE (24/7: X units spread over the day with `x_spread_over_day`, never closer than `x_query_delay_min_s`; Reddit searches spread at max(60 s, 24 h / coins); comments feeds every 7200 s; posts feeds every 21600 s; enrichment once a day; Reddit budget 250) and DEGRADED (T135 small window, Reddit budget 150). Evidence sidecar gains completeness fields (attempted, fetched, missing with reason counts, sample sizes, cap flags, freshness). Config keys added to `api/data/attention_queries.json`: `x_spread_over_day`, `reddit_search_time_filter` (week), `reddit_comments_poll_interval_s`, `reddit_posts_poll_interval_s`, `reddit_daily_request_budget` (250), `reddit_degraded_request_budget` (150), `reddit_ledger_retention_days` (400). Tests (AC37, AC38, AC40): `test_baseline_x_units_never_closer_than_min_delay`, `test_baseline_x_units_spread_over_utc_day_when_flag_true`, `test_x_units_clustered_when_flag_false`, `test_baseline_reddit_search_spacing_at_least_max_60s_or_day_over_coins`, `test_baseline_comments_polled_every_7200s_twelve_per_day`, `test_baseline_posts_polled_every_21600s`, `test_baseline_enrichment_once_per_day`, `test_degraded_mode_matches_t135_behaviour_budget_150`, `test_mode_follows_uptime_not_fixed_utc_hour`, `test_slow_clock_pass_continues_next_window_nothing_dropped`, `test_sample_and_page_cap_never_shrunk_for_time`, `test_evidence_has_completeness_fields`, `test_state_bounded_over_ninety_simulated_days`.

- **Files:** the W8b rows of section 3 plus tests `api/tests/data/attention/test_density.py`, `test_pc_pace.py`, `test_web_queries.py`, `test_web_evidence.py`, `test_pc_adapter.py`, `api/tests/scripts/test_probe_pc_sources.py`, `api/tests/tooling_guards/test_pc_collector_guards.py`.
- **Red-first tests (must fail before the code exists), each named for its SPEC criterion:**
  - AC1: `test_exact_count_when_window_start_reached`, `test_capped_rate_24_times_n_over_span`, `test_span_floor_quarter_hour`, `test_pagecap_uses_k`, `test_below_n_min_is_missing`, `test_boundary_k_equals_n_is_continuous`, `test_no_value_before_window_end_2359_vs_0000`, `test_newest_never_today`.
  - AC3/AC4: `test_failed_collection_stores_nothing`, `test_zero_needs_canary_and_low_median`, `test_second_collection_does_not_change_day`, `test_evidence_row_has_all_fields`.
  - AC8: `test_x_spacing_within_configured_min_max_seeded`, `test_x_spacing_follows_changed_config`, `test_reddit_spacing_within_configured_60_120_seconds_seeded`, `test_reddit_daily_budget_150`, `test_catch_up_never_faster_than_min_delay`, `test_few_hours_uptime_runs_at_configured_pace`, `test_yesterday_before_backfill`, `test_pace_config_rejects_min_above_max_and_nonpositive`.
  - AC21: `test_budget_counts_posts_loaded_including_dropped`, `test_page_load_refused_when_it_would_exceed_budget`, `test_unread_coin_days_missing_not_zero`, `test_unit_with_k_at_least_n_min_kept_when_budget_ends`, `test_budget_resets_at_utc_midnight`, `test_budget_count_survives_restart`.
  - AC22: `test_warning_day_halves_next_day_budget_floor_one_unit`, `test_seven_clean_days_double_once_up_to_configured`, `test_warning_resets_clean_count`, `test_no_activity_day_changes_nothing`, `test_adaptive_state_survives_restart`.
  - AC10: `test_429_pauses_until_next_utc_midnight`, `test_pause_persists_over_restart`, `test_no_retry_after_warning`, `test_suspension_and_login_expired_stay_paused`, `test_other_source_keeps_running`.
  - AC11/AC12: `test_logs_contain_class_and_status_only_with_planted_secrets`, `test_profile_path_is_gitignored_and_outside_repo`.
  - AC15/AC20: `test_ambiguous_coin_is_missing`, `test_coin_set_is_narrative_placed_symbols_minus_ambiguous`.
  - AC16: `test_dependency_pinned_and_banned_names_absent` (greps requirements, lock and code for xscrape, kloxeld, gunkonchi outside the guard's own constant list built from split strings).
  - AC27 (only if the optional API Anything fallback is ever built, T166): `test_adapter_refuses_registry_and_publish_calls`, `test_shipped_x_recipe_never_loaded`, `test_pinned_sha_constant_is_20cb677039fcfe92d3d9c777aa9362e30ff1fdb8`, `test_install_docs_use_npm_ci_ignore_scripts`.
  - AC19: `test_self_repair_refused_after_15_usd_in_month`, `test_cap_resets_next_month`.
- **Gates:** G-B1 `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/scripts/test_probe_pc_sources.py api/tests/tooling_guards/test_pc_collector_guards.py -q` (0 failed; at least baseline + the named tests); G-B2 attention suite unchanged; G-B3 file-set check (section 6, only the W8b files); G-B4 hygiene and secret scan; G-B5 no network import (`grep` for `requests|httpx|socket|urllib|playwright` import lines in the new pure modules prints nothing).
- **Owner probes:** none (pure).

### W8c: Reddit connector (opus), plain HTTP on the public RSS feeds (T138, widened T163)

- **T163 addenda:** per-coin `search.rss` requests are spread over the day (baseline) and use `reddit_search_time_filter` `week` (`t=day` reaches only 24 h back from the request and misses part of yesterday; P-R6 variant checks which `t` values are honoured). Tests: `test_search_request_uses_t_week_by_config`, `test_search_requests_spread_over_day_baseline`, `test_search_completeness_written_attempted_fetched_missing_reasons`, `test_budget_250_baseline_and_150_degraded` (the 150 test above is the degraded value). P-R6 variant (owner, PowerShell, one request): `curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code} %{size_download}\n" "https://www.reddit.com/r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new&t=week&limit=100"`.

Does not depend on W8a: no API Anything, no adapter, no login, no browser. Honest descriptive user agent constant only; JSON endpoints are not used (403 on the owner's PC); `old.reddit.com` is not usable (302 with no body).

- **Files:** `api/data/attention/reddit_web.py` (per-coin `search.rss`, sort=new, t=day, over the subreddit set), `api/data/attention/reddit_items.py` (item ledger by Reddit id: `t3_` posts, `t1_` comments, author hash with a salt kept outside the repo, subreddit, created time, `collected_at`, feed kind, matched coins; dedupe by id), `api/data/attention/reddit_metrics.py` (pure functions: mention matching with `name_only`, author cap, unique authors, low-volume rule, engagement-weighted sum, controversy, deleted-later removal), config keys in `api/data/attention_queries.json` (`name_only` flag on ETC, LINK, NEAR, HYPE, PI, PUMP, GT, CC; `reddit_author_cap` 3, `reddit_min_mentions` 3), additions to `probe_pc_sources.py` (`--source reddit`), tests `api/tests/data/attention/test_reddit_web.py`, `test_reddit_items.py`, `test_reddit_metrics.py`, and the guard `api/tests/tooling_guards/test_reddit_collector_guards.py` over the explicit file list `reddit_web.py`, `reddit_items.py`, `reddit_metrics.py`, `reddit_stream.py`, `reddit_engagement.py` (a file that does not exist yet is skipped until its slice adds it). Uses `httpx` (already a dependency) or stdlib; no new dependency, no `api/pyproject.toml` edit.
- **Red-first tests:** `test_parse_atom_entries_with_updated_timestamps`, `test_exact_count_when_feed_reaches_window_start`, `test_feed_capped_uses_density_over_covered_span`, `test_day_not_reached_is_missing`, `test_entries_after_window_end_ignored`, `test_below_reddit_sample_min_is_missing`, `test_search_rss_url_form_sort_new_t_day_and_subreddit_set`, `test_single_honest_user_agent_constant`, `test_no_browser_user_agent_string_in_module`, `test_html_block_page_is_not_parsed_and_pauses`, `test_403_pauses_rest_of_day_no_retry`, `test_429_pauses_rest_of_day_no_retry`, `test_feed_with_doctype_or_entity_rejected`, `test_oversize_body_rejected`, `test_ambiguity_list_skips_coin`, `test_value_written_only_for_completed_day`, `test_writes_reddit_web_store_not_reddit`, `test_evidence_row_written`, `test_budget_150_requests_per_day`, `test_logs_class_and_status_only_with_planted_secrets`, `test_no_json_endpoint_url_in_module`, `test_no_fixed_utc_hour_assumption_start_times_0030_0900_1700_2300`.
  - AC29: `test_ledger_dedupes_by_reddit_id_across_feeds_and_polls`, `test_ledger_row_has_id_author_hash_subreddit_created_collected_feed_kind_coins`, `test_username_never_stored_or_logged`.
  - AC31: `test_name_only_tickers_need_full_name_or_cashtag` (ETC, LINK, NEAR, HYPE, PI, PUMP, GT, CC), `test_bare_ticker_matches_for_other_coins`, `test_author_cap_three_per_coin_day`, `test_unique_authors_counts_distinct_hashes`.
  - AC32: `test_low_volume_below_three_mentions_change_missing`, `test_exactly_three_mentions_change_computed`.
  - AC35: `test_engagement_weighted_sum_posts_add_log1p_num_comments`, `test_comment_num_comments_not_added`, `test_controversy_boundaries_ratio_0_30_and_votes_9_10`, `test_deleted_later_removed_from_settled`.
  - AC36 (part): `test_guard_fails_on_browser_ua_json_endpoint_or_archive_search_path`.
- **Gates:** pytest on the new files and `api/tests/data/attention`; the guard test; scripts suite; file-set check; hygiene; banned-name grep.
- **Owner probes (PowerShell; the first four can run NOW, before any code; each prints counts and statuses only):**
  - P-R6 (feed depth, three requests one minute apart): `$ua="attention-probe/0.1"; foreach ($u in @("https://www.reddit.com/r/CryptoCurrency/new/.rss","https://www.reddit.com/r/CryptoCurrency/new/.rss?limit=100","https://www.reddit.com/r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new&limit=100")) { $x=[xml](curl.exe -s -A $ua $u); "{0} entries, newest {1}, oldest {2}" -f $x.feed.entry.Count, $x.feed.entry[0].updated, $x.feed.entry[-1].updated; Start-Sleep -Seconds 60 }` (the owner's 24-10-26 run: new.rss?limit=100 = 100 entries spanning about 8 days)
  - P-R3 (feed rate, one request per minute): `1..10 | ForEach-Object { curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code}\n" "https://www.reddit.com/r/CryptoCurrency/search.rss?q=solana&restrict_sr=1&sort=new"; Start-Sleep -Seconds 60 }` (stop with Ctrl+C at the first 403 or 429 and paste the output)
  - P-R4 (multi-subreddit feed): `curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code} %{size_download}\n" "https://www.reddit.com/r/CryptoCurrency+CryptoMarkets+altcoin/search.rss?q=solana&restrict_sr=1&sort=new"`
  - P-R7 (comments feed paging, two requests one minute apart; UNVERIFIED whether `after=` works): `$ua="attention-probe/0.1"; $u="https://www.reddit.com/r/CryptoCurrency/comments/.rss?limit=100"; $x=[xml](curl.exe -s -A $ua $u); $last=$x.feed.entry[-1].id; "page1 {0} entries, newest {1}, oldest {2}, last id {3}" -f $x.feed.entry.Count,$x.feed.entry[0].updated,$x.feed.entry[-1].updated,$last; Start-Sleep -Seconds 60; $y=[xml](curl.exe -s -A $ua ($u+"&after="+$last)); "page2 {0} entries, newest {1}, oldest {2}" -f $y.feed.entry.Count,$y.feed.entry[0].updated,$y.feed.entry[-1].updated`  PASS = page 2 newest is older than page 1 oldest; an empty page or an error means no paging.
  - P-R2 (after the build): `python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --feed-depth`
  - P-R5 (after the build): `python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --compare-scope`
- **Owner answers carried (T139):** Q15 yes (stream-and-count, W8c2), Q16 (PC hours vary, no UTC window); the depth limit of SPEC Annex A.2 means some coin-days are missing, never 0. W8c carries `test_no_fixed_utc_hour_assumption_start_times_0030_0900_1700_2300` (AC28).

### W8c2: Reddit stream-and-count complement incl. comments feeds (opus; Q15 yes T139, widened T163)

- **T163 addenda:** BASELINE polling is subreddit `comments/.rss` every 2 hours and posts `new.rss` every 6 hours (config); the one-poll-per-day behaviour of AC30 is DEGRADED mode only. Extra tests: `test_baseline_two_hourly_comments_polls_give_full_coverage`, `test_degraded_one_poll_per_day_below_0_80`, `test_stream_completeness_fields_written`, `test_stream_continues_next_window_without_dropping_feeds`.

Method id `reddit_stream`, stored apart from `reddit_web` and never spliced in one series (AC14); `reddit_impl_order` picks one method per window (default `reddit_stream`, `reddit_web`, so a day without comment coverage falls back to the posts-only series). Plain HTTP on the public `new.rss` and subreddit `comments/.rss` feeds, same honest user agent and pause rules as W8c; no API Anything. Reuses W8c's feed parser, item ledger and metric functions.

- **Files:** `api/data/attention/reddit_stream.py` (poll scheduler core, comments and posts coverage rule, mention counter over the ledger), config keys in `api/data/attention_queries.json` (`reddit_stream_subreddits` 4-6, `reddit_stream_poll_interval_s` 3600, `reddit_stream_polls_per_day_cap` 6, `reddit_stream_min_coverage` 0.8, `reddit_comments_paging` false, `reddit_impl_order`), tests `api/tests/data/attention/test_reddit_stream.py`; additions to `probe_pc_sources.py` (`--source reddit --stream-status`).
- **Red-first tests:** `test_poll_parses_feeds_and_stores_collected_at_and_timestamps`, `test_dedupe_by_entry_id_across_overlapping_polls`, `test_cross_feed_duplicate_entry_id_counted_once`, `test_mentions_counted_for_all_narrative_coins_from_same_entries`, `test_ambiguity_list_skips_coin`, `test_coverage_fraction_from_entry_timestamps`, `test_gap_uncovered_when_oldest_of_next_poll_newer_than_previous_newest`, `test_day_stored_at_coverage_0_80_flagged_partial`, `test_day_below_coverage_missing_not_zero`, `test_full_coverage_not_flagged_partial`, `test_newest_slice_bias_flag_in_evidence`, `test_stream_method_id_separate_store_from_reddit_web`, `test_methods_never_mixed_in_one_window_config_order`, `test_value_only_after_day_complete`, `test_poll_interval_and_daily_poll_cap`, `test_stream_requests_share_daily_budget_150`, `test_403_429_block_page_pauses_rest_of_day`, `test_stream_feed_count_must_be_4_to_6`, `test_pc_start_hours_vary_no_fixed_utc_window` (AC28).
  - AC30 (T163): `test_one_poll_per_day_comments_coverage_below_0_80_day_missing`, `test_two_polls_gap_under_feed_span_coverage_at_least_0_80`, `test_posts_plus_comments_day_needs_both_feed_kinds_covered`, `test_fallback_to_posts_only_series_when_comments_missing`, `test_paging_off_makes_no_after_request`, `test_paging_on_requests_after_t1_id_within_daily_budget`, `test_comments_feed_hundred_entries_over_fifteen_hours_fixture`.
  - AC29 (T163): `test_comment_items_enter_ledger_with_t1_id_and_author_hash`.
- **Gates:** pytest on the new file and `api/tests/data/attention`; guard test; scripts suite; file-set check; hygiene; banned-name grep.
- **Owner probe after the build:** `python -m api.scripts.probe_pc_sources --source reddit --stream-status` (prints polls today, entries seen, coverage per recent day for posts and comments feeds, partial and missing counts; numbers only). Pass: coverage per day is computed and the pace matches the config.
- **Open before it starts (owner):** Q17 (polling cadence versus PC uptime; recommended: run P-R7 first).

### W8c3: Reddit engagement enrichment via archive ids (opus, about 3 USD; T163; optional)

- **T163 addenda:** baseline runs the enrichment once a day for items older than 2 days; a run that cannot finish inside its window continues in the next one (no ids dropped, quality over speed); tests `test_enrichment_runs_once_per_day_baseline` and `test_unfinished_enrichment_continues_next_window_no_ids_dropped`.

Method id `reddit_engagement`, a SETTLED series separate from the provisional counts (never overwrites them). Depends on W8c (ledger and metric functions; posts); live comment enrichment needs W8c2 (comments in the ledger). The core mention series works without it (Q18, recommended optional and off by default until P-R8 passes).

- **Files:** `api/data/attention/reddit_engagement.py` (ID-only archive client with host and path allowlist, breaker, 3 s spacing, 40 requests per run, 500 ids per request, settled series writer by pull date, resolved-share rule), config keys in `api/data/attention_queries.json` (`reddit_engagement_enabled` false, `reddit_engagement_min_resolved` 0.8, `reddit_engagement_min_age_days` 2), tests `api/tests/data/attention/test_reddit_engagement.py`; additions to `probe_pc_sources.py` (`--source reddit --enrich-probe --n 10`, ids from the ledger).
- **Red-first tests (AC33-AC36):** `test_only_items_at_least_two_days_old_are_enriched`, `test_ids_batched_at_most_500_per_request`, `test_settled_series_stored_apart_and_never_overwrites_provisional`, `test_day_value_only_from_pull_dated_at_least_d_plus_3`, `test_each_pull_stored_by_pull_date_and_latest_at_or_before_asof_is_read`, `test_truncate_and_recompute_identical_point_in_time`, `test_resolved_share_below_0_8_day_missing_not_zero`, `test_timeout_text_maybe_slow_down_is_failure`, `test_non_json_body_is_failure`, `test_5xx_is_failure`, `test_failure_means_enrichment_missing_never_zero`, `test_no_retry_loop_request_count_stays_one_per_failure`, `test_requests_spaced_three_seconds_and_capped_at_forty_per_run`, `test_three_consecutive_failures_open_breaker_for_rest_of_day`, `test_breaker_persists_over_restart`, `test_archive_down_leaves_core_mention_series_intact`, `test_client_calls_only_ids_endpoints_on_archive_host`, `test_search_and_aggregate_paths_refused`, `test_honest_user_agent_only`, `test_deleted_later_and_removal_type_excluded_from_settled`, `test_engagement_weighted_value_matches_metric_function`, `test_controversy_series_separate`, `test_logs_class_and_status_only`.
- **Gates:** pytest on the new file, `api/tests/data/attention` and the guard test; scripts suite; file-set check; hygiene; banned-name grep.
- **Owner probes (PowerShell, run NOW; requests 3 s apart; print counts and numbers only):**
  - P-R8 (archive ID lookup; `comments/ids` is UNVERIFIED): `$ua="attention-probe/0.1"; $b="https://arctic-shift.photon-reddit.com"; $x=[xml](curl.exe -s -A $ua "https://www.reddit.com/r/CryptoCurrency/new/.rss?limit=100"); $ids=@($x.feed.entry | Where-Object { [datetime]$_.updated -lt (Get-Date).AddDays(-3) } | Select-Object -First 10 | ForEach-Object { $_.id -replace '^t3_','' }); "ids: " + ($ids -join ","); Start-Sleep -Seconds 3; $r=curl.exe -s -A $ua "$b/api/posts/ids?ids=$($ids -join ',')" | ConvertFrom-Json; "posts returned: " + $r.data.Count; $r.data | Select-Object id,score,num_comments,upvote_ratio,retrieved_on | Format-Table -AutoSize; Start-Sleep -Seconds 3; $a=(Get-Date).ToUniversalTime().AddDays(-5).ToString('yyyy-MM-dd'); $c=(curl.exe -s -A $ua "$b/api/comments/search?subreddit=CryptoCurrency&after=$a&limit=10" | ConvertFrom-Json).data; $cid=($c | ForEach-Object { $_.id }) -join ','; Start-Sleep -Seconds 3; $d=curl.exe -s -A $ua "$b/api/comments/ids?ids=$cid" | ConvertFrom-Json; "comments returned: " + $d.data.Count; $d.data | Select-Object id,score,link_id | Format-Table -AutoSize`
  - After the build and 3 or more days of collected items: `python -m api.scripts.probe_pc_sources --source reddit --enrich-probe --n 10` (ids from the owner's own ledger; prints resolved count, scores and lag only).
- **Open before it starts (owner):** Q18 (keep it optional; recommended yes).

### W8e: worker wiring (opus)

- **T163 addenda (24/7 host, quality over speed):** the worker is written to run unattended for weeks: log rotation (size cap and file count from config), bounded persisted state (pause state, counters, effective budget, ledger partitions with `reddit_ledger_retention_days`), no unbounded in-memory growth, restart or power cut resumes through `_behind` at the configured pace, UTC only. It runs the BASELINE schedule on a 24/7 host and DEGRADED mode otherwise. Tests (AC37, AC38, AC40): `test_log_rotation_size_and_count_from_config`, `test_state_files_bounded_after_ninety_simulated_days`, `test_memory_structures_do_not_grow_with_days`, `test_restart_at_any_tick_resumes_via_behind_no_burst`, `test_pass_that_cannot_finish_continues_in_next_window`, `test_no_coin_or_sample_dropped_to_fit_time`, `test_mode_switch_baseline_degraded`. The T135 uptime tests below are the DEGRADED-mode tests.

- **Files:** `api/data/attention_pc_refresh.py`, edit `api/main.py` (start in lifespan, stop in `finally`, same pattern as lines 48-58), edit `api/data/discovery.json` (`fetch_side` per source: `xsearch` and `reddit` `pc_side`, others `github`), tests `api/tests/data/test_attention_pc_refresh.py`.
- **T135 additions:** X and Reddit run as two concurrent streams with a per-source lock (locked by the owner's answer to Q14, T136); in rotation mode the X queue is ordered by oldest newest-stored day first; a coin-day unfinished when the PC stops stays queued for a later day; nothing is stored for PC-off time.
- **T133 additions:** the worker reads the collector config, runs X units only while budget remains, persists the effective budget and clean-day count with the pause state (cache `_pc_state`), and never starts a unit earlier than the configured minimum delay after the previous one, including right after a restart.
- **Red-first tests:** `test_flag_off_starts_no_thread`, `test_tests_and_runners_never_start_worker_by_default`, `test_behind_source_schedules_first_unit_20s_after_start`, `test_up_to_date_source_waits`, `test_pass_lock_prevents_overlap`, `test_worker_skips_github_side_sources`, `test_restart_keeps_pause_and_daily_counts`, `test_restart_keeps_effective_budget_and_clean_day_count`, `test_one_hour_uptime_runs_about_13_x_units_and_reddit_concurrently` (AC24), `test_three_hour_uptime_x_stops_at_budget`, `test_pc_off_stores_nothing`, `test_unfinished_coin_day_carries_over`, `test_rotation_queue_oldest_stored_first`, `test_x_and_reddit_streams_have_separate_locks`, `test_no_unit_before_min_delay_after_restart`, `test_worker_with_two_hours_uptime_stops_cleanly`, `test_stop_worker_joins_thread`, `test_unit_failure_never_crashes_the_api`, `test_lifespan_starts_and_stops_worker`, `test_no_network_in_tests`.
- **Gates:** pytest on the new file; `api/tests` routers and main-related tests unchanged; the two workflow guards green; G-file-set (only `api/main.py`, `discovery.json` and new files).
- **Owner probe after build:** P-W1 (amended 30-10-26: the first draft named `probe_pc_sources --source reddit --status`, which has no such flag in the code). Start the API with `SCREENER_ATTENTION_PC_WORKER=1` for 1 hour with only Reddit built, then read the Sources route `GET /api/narrative/sources` (files only, no provider call; PowerShell `Invoke-RestMethod`, the `sources[].health` fields exist once W8e2's code half is merged) and the end of `<cache>/attention/_logs/attention_pc.log`. Pass: request counts within the caps and unit times spaced as locked; the health summary alone does not prove caps or spacing, so compare the log's unit times and the counts with the configured pace. Exact commands: `narrative-baskets-server-host-guide_30-10-26.md` section 6.

### W8e2: server host guide and health line (T163 addendum 1; docs sonnet, code opus)

**T179 (host OS not decided, Q29 decided both):** the guide is written for BOTH Windows (auto-start task, `powercfg`, `w32tm`) and Linux (systemd service with `Restart=always`, `PrivateTmp=true`, the environment variables, masked sleep targets, `HandleLidSwitch=ignore`, `timedatectl`), as in SPEC Annex J items 1-11; the owner's final OS choice is made in this slice, and the installer picks the curl wheel by platform (W8d2). USD 3-5.

After W8e and W8f (it edits the Sources data that W8f also touches). The generic worker must already run unattended (W8e).

- **Files:** (docs, sonnet) `narrative-baskets-server-host-guide_<dd-mm-yy>.md` in the task folder, turning SPEC Annex J into steps the owner runs on the spare laptop (auto-start as a background task at startup or log-on under the user that holds the throwaway X session, no sleep or hibernate with `powercfg`, lid action, auto-logon trade-off, log and disk rotation, clock sync with `w32tm`, restart catch-up, remote viewing without a public port, UPS note, accounts and secrets stay only on that host); (code, opus) read-only health fields in `api/analytics/attention/sources.py` and `api/models/discovery.py`: last unit time, pause reason and its end, attempted and fetched counts, effective budget, stale flag, completeness text; tests `api/tests/analytics/attention/test_sources_health.py`.
- **Red-first tests (AC38, AC39):** `test_health_payload_has_last_unit_pause_reason_attempted_fetched_budget`, `test_paused_source_shows_reason_code_and_end`, `test_stale_after_twice_the_expected_gap`, `test_completeness_text_attempted_fetched_missing_reasons_capped_newest_age`, `test_health_reads_files_only_no_network`, `test_existing_sources_rows_unchanged_when_no_worker_state`.
- **Gates:** pytest on the new file and `api/tests/analytics/attention`; scripts suite; file-set check; hygiene; banned-name grep; doc check of the guide (no secrets, no real paths or cookie values, banned names absent).
- **Owner steps (PowerShell on the laptop, examples from SPEC Annex J; nothing was run here):** `powercfg /change standby-timeout-ac 0`; `powercfg /change hibernate-timeout-ac 0`; `w32tm /query /status`; the Task Scheduler registration and the auto-logon choice are the owner's, confirmed by the guide.

### W8f: Discovery wiring (opus)

- **Files (edits):** `api/analytics/attention/discovery.py` (config validation of `fetch_side` and `source_impl`; weighted sources read the chosen impl store), `api/analytics/attention/sources.py` (reason codes on the row, state mapping `insufficient-history` / `unavailable` with note), `api/data/attention/registry.py`, `api/models/discovery.py` if a field is added; tests under `api/tests/analytics/attention/`.
- **T135 item (rotation mode, owner answer to Q10; built here, not before approval):** `x_discovery_mode` (`rotation` default for X, `window` keeps today's rule) and `x_rotation_points` 3, `x_rotation_max_lag_days` 7 in the collector config; X change = newest of the latest 3 stored values against the mean of the 2 earlier ones (Q13 may change this); fewer than 3 points = X missing and weights rescale; the 3-point rule replaces `min_history_days` for X only; lag uses `x_rotation_max_lag_days` for X only; every other source keeps the 7-day window and `max_source_lag_days`.
- **Red-first tests:** `test_fetch_side_rejects_unknown_value`, `test_source_impl_reads_web_store`, `test_two_methods_never_spliced`, `test_pc_off_gap_rescales_not_zero` (AC6), `test_t96_lag_drops_source`, `test_point_in_time_truncate_recompute_identical` (AC5), `test_backfilled_flag_excludable`, `test_sources_row_shows_reason_code`, `test_rotation_three_points_scores` (AC23), `test_rotation_fewer_than_three_points_is_missing`, `test_rotation_lag_uses_x_rotation_max_lag_days`, `test_other_sources_keep_seven_day_window`, `test_window_mode_reproduces_current_x_behaviour`, `test_rotation_point_in_time_truncate_identical`.
- **Gates:** attention suite at least baseline plus the new tests with 0 failed; existing discovery and sources tests unchanged and green (any deleted or replaced test listed with its reason).
- **Owner probe:** none beyond W8c/W8e.

### W8g: web status text (opus, low)

- **T163 addenda:** the Sources panel text also shows the health line and the completeness text of SPEC rules 15-16 and AC38-AC39 (last unit time, pause reason, attempted/fetched/missing with reasons, capped count, newest age, stale flag); vitest cases for each text.

- **Files (edits):** `web/components/narrative/` Sources/updating text for reason codes and the "one day late" note; vitest additions. Gates: `pnpm` vitest and `tsc` per `process/context/tests/all-tests.md`; no `.github/`. **Owner probe:** look at the Sources page once.

### W8a2: vet twscrape at the pinned commit (report only, sonnet; T166)

**STATUS (T170): DONE.** Report `narrative-baskets-w8a2-twscrape-vetting_REPORT_24-10-26.md` (T169, PR #169): verdict VIABLE-WITH-CONDITIONS (planner scale: usable with changes), studied SHA `63f61a518e576ea5c132f1156c03dda0520d76c1`, conditions C1-C11 applied in SPEC rules 17-20 and AC41-AC55. The reference report of the other session never landed, so the cross-check against it is open; the owner's P-X9 below is the live check. Condition C10 of that report was amended by T179: the curl fallback triggers on Cloudflare OR HTML (`Blocked by Cloudflare` or `Blocked by HTML`), and both the Windows and the Linux wheel hashes are pinned (the host OS is not decided). The text below is the original W8a2 envelope kept for the record; the P-X9 paste at the end of this section is the CORRECTED version (T170).

Report only: nothing from twscrape is installed, built, imported or run by the worker. Reads the repository with `add_repo` (read access) at the commit the planner named, `63f61a5`, resolving its full 40-hex SHA, and records the verdict `usable` / `usable with changes` / `not usable`.

- **Files:** one report `narrative-baskets-w8a2-twscrape-vetting_REPORT_<dd-mm-yy>.md` in the task folder.
- **Method:** the W8a method of SPEC Annex F applied to twscrape: full SHA (`git rev-parse`), `pyproject.toml` build backend and any build or install hooks, dependency tree and versions, licence, every outbound host, the telemetry code (CLI-only; confirm the library path sends none and that `TWS_TELEMETRY=0` is honoured), the `curl` HTTP backend (curl-cffi) and what it impersonates (record it; the owner allows it only as the Cloudflare fallback behind a flag, SPEC rule 19), and the curl_cffi supply chain (PyPI project and maintainers, compiled wheels and the bundled impersonation binaries, exact version and hash, no install scripts and `--only-binary`, any import-time network, licence, near-names), the account database (plaintext cookies; path and permissions), the 0.21.0 raising semantics and options (`wait_timeout`, `raise_when_no_account`), the error codes 88, 326, 32 and bare 403, how the client transaction id and the GraphQL operation ids are obtained and what breaks on a new X web build, the `x-rate-limit-*` TRACE method for header numbers, the exact cookie upsert call, whether the pinned commit is on the 0.21.0 line, and whether `0.20.1` on PyPI differs. Read the reference report `narrative-baskets-twscrape-reference_REPORT_24-10-26.md` (branch `claude/t165-twscrape-reference`) when it exists and reconcile it with the code; where they differ, the code at the pinned SHA wins.
- **Gate:** the report has every item filled or marked UNVERIFIED with the reason; banned names appear only in "banned" sentences; `twscrape` is distinguished from `xscrape` in the report.
- **Owner steps after the verdict (PowerShell, read-only until the verdict is accepted):** `git ls-remote https://github.com/vladkens/twscrape HEAD`; `git clone --no-checkout https://github.com/vladkens/twscrape C:\vet\twscrape`; `git -C C:\vet\twscrape rev-parse 63f61a5` (prints the full SHA); `git -C C:\vet\twscrape checkout --detach 63f61a518e576ea5c132f1156c03dda0520d76c1`; ONLY after the owner accepts the verdict: `py -3.12 -m venv C:\vet\twvenv` and `C:\vet\twvenv\Scripts\python.exe -m pip install C:\vet\twscrape` (an install runs the package's build backend, which is why vetting comes first), then probe P-X9 below.
- **P-X9 PER ACCOUNT, corrected by T170 on the W8a2 report (owner, throwaway accounts only, one local cookie file per account and never printed, each account probed separately with its own database; reads at most 40 raw entries per query; prints the account label, counts, timestamps and the raw `x-rate-limit-*` header numbers only; exact paste; the labels `acct1`, `acct2`, `acct3` and the cookie files `C:\secrets\x_acct1.txt` and so on are examples the owner adapts). Before the probe the owner installs the dependencies in the throwaway venv `C:\vet\twvenv` at the versions the W8a2 report lists (the probe venv is throwaway; W8d2 pins them with hashes in our own lock) and then `C:\vet\twvenv\Scripts\python.exe -m pip install C:\vet\twscrape --no-deps`:**

```powershell
$env:TWS_TELEMETRY="0"; $env:DO_NOT_TRACK="1"; $env:TWS_LOG_LEVEL="WARNING"; $env:TWS_RAISE_WHEN_NO_ACCOUNT="1"
foreach ($v in "TWS_PROXY","HTTP_PROXY","HTTPS_PROXY","TWS_HTTP_BACKEND") { Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
git -C C:\vet\twscrape rev-parse HEAD
@'
import asyncio, os, datetime as dt
from twscrape import API
from twscrape.models import parse_tweets
async def run(api, q, tag):
    pages = raw = n = views = casht = casht_sol = ph = 0; dates = []
    try:
        async for rep in api.search_raw(q, limit=40):
            pages += 1; raw += rep.text.count('"entryId":"tweet-')
            print(tag, "page", pages, "x-rate-limit-remaining", rep.headers.get("x-rate-limit-remaining"), "x-rate-limit-limit", rep.headers.get("x-rate-limit-limit"))
            for t in parse_tweets(rep, -1):
                n += 1; dates.append(t.date); views += t.viewCount is not None
                casht += bool(t.cashtags); casht_sol += any(c.lstrip("$").upper() == "SOL" for c in t.cashtags); ph += (not t.user.profileImageUrl)
    except Exception as e:
        print(tag, "ERROR", type(e).__name__); return
    print(tag, "pages", pages, "raw_entries", raw, "parsed", n, "oldest", min(dates) if dates else None, "newest", max(dates) if dates else None, "with_views", views, "with_cashtags", casht, "with_cashtag_SOL", casht_sol, "placeholder_users", ph)
async def main():
    label = os.environ["X_PROBE_LABEL"]
    api = API(rf"C:\vet\tws_{label}.db", raise_when_no_account=True, wait_timeout=0)
    await api.pool.add_account_cookies(label, os.environ["X_PROBE_COOKIES"])
    print("account", label)
    d = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=1)
    a, b = int(d.timestamp()), int((d + dt.timedelta(days=1)).timestamp())
    base = '("$SOL" OR "Solana") -filter:replies -filter:retweets lang:en'
    await run(api, base + f" since_time:{a} until_time:{b}", "epoch")
    await run(api, base + f" since:{d:%Y-%m-%d} until:{(d + dt.timedelta(days=1)):%Y-%m-%d}", "dates")
asyncio.run(main())
'@ | Set-Content C:\vet\probe_x9.py
foreach ($l in "acct1","acct2","acct3") { $env:X_PROBE_LABEL=$l; $env:X_PROBE_COOKIES=(Get-Content "C:\secrets\x_$l.txt" -Raw).Trim(); C:\vet\twvenv\Scripts\python.exe C:\vet\probe_x9.py }
```

  The script differs from the T167 version as the W8a2 report requires: `add_account_cookies` instead of `add_account` with a password; `API(..., raise_when_no_account=True, wait_timeout=0)` plus `TWS_RAISE_WHEN_NO_ACCOUNT=1` so a locked or banned account raises instead of giving a silent empty result; each run is wrapped so that only the exception CLASS is printed (messages can hold the account name); cashtags are compared without `$` (the library's `cashtags` carry no `$`); `DO_NOT_TRACK=1`, `TWS_TELEMETRY=0`, `TWS_LOG_LEVEL=WARNING` and the proxy and backend variables cleared; raw `x-rate-limit-remaining` and `x-rate-limit-limit` per page from `search_raw` replace the TRACE method (which does not work as relayed); `git rev-parse HEAD` is recorded as the identity (the installed version string says 0.20.1). Pass: per account the line `account <label>`, per page the two header numbers, and per window (`epoch`, `dates`) one summary line: pages, raw entries, parsed tweets, oldest and newest timestamps, counts of viewCount, cashtags, the SOL cashtag and placeholder users, or `ERROR <class>`. The owner also compares the counts and timestamps across the accounts (they should agree within about 25 percent: a preview of the daily cross-account canary of SPEC rule 18). `parse_tweets(rep, -1)` and the other names come from the W8a2 report (found in the code) but were never run: UNVERIFIED until the owner's output.

### W8d1: X pure core for twscrape (opus, medium; T166)

Pure logic and fakes; nothing from twscrape is imported. Depends on W8b (pace, budget, pause, evidence core), W8a2's verdict and Q21-Q23.

- **Files:** `api/data/attention/x_window.py` (query and window builder, both syntaxes, timestamp filter), `api/data/attention/x_filters.py` (post-filters and quality metrics), `api/data/attention/x_density.py` (read-sample density, may extend `density.py`), `api/data/attention/x_raw.py` (raw page writer, retention, re-parse), `api/data/attention/x_reader.py` (`XReader` Protocol, error classes, reason mapping, canary logic, fake reader), `api/data/attention/x_pool.py` (account-pool logic: least-recently-used selection with registration-order ties, account states active, locked, inactive, suspect, unit integrity and restart accounting, cross-account canary comparison, global budget accounting, our own UTC-day lock state (never the library's locks and never `reset_locks`), per-page read accounting from raw pages, the parse-drop guard; pure, with a fake pool and fake raw pages), config keys in `api/data/attention_queries.json` (`x_lang`, `x_window_syntax`, `x_min_account_age_days`, `x_min_followers`, `x_max_cashtags`, `x_raw_retention_days`, `x_canary_query`, `x_canary_min_results`), tests `api/tests/data/attention/test_x_window.py`, `test_x_filters.py`, `test_x_density.py`, `test_x_raw.py`, `test_x_reader.py`.
- **Red-first tests (AC41-AC46):** `test_query_since_time_until_time_form`, `test_query_utc_date_form_until_exclusive`, `test_out_of_window_tweet_excluded_by_timestamp`, `test_latest_order_only`, `test_paging_stops_at_window_start_or_sample_or_page_cap`, `test_read_sample_density_exact_when_window_reached`, `test_read_sample_density_capped_24_k_over_span`, `test_span_floor_quarter_hour`, `test_retweets_and_replies_excluded_by_fields`, `test_lang_policy_default_en_and_override_and_any`, `test_cashtag_field_matching`, `test_name_only_tickers_etc_link_near_hype_pi_pump_gt_cc`, `test_placeholder_user_excluded`, `test_young_account_and_low_followers_and_protected_excluded`, `test_author_cap_three_and_duplicate_text_once`, `test_cashtag_spam_over_five_excluded`, `test_unique_authors_and_top_author_share`, `test_exclusions_counted_by_reason_in_evidence`, `test_engagement_sum_log1p_like_reply_quote_retweet`, `test_missing_view_count_not_zero_and_median_views_stored`, `test_read_age_hours_recorded`, `test_raw_page_gzipped_with_versions_and_no_cookies`, `test_reparse_identical_same_parser_version`, `test_new_parser_version_new_evidence_row_never_overwrites`, `test_raw_retention_deletes_old_pages`, `test_pool_selection_least_recently_used_ties_by_registration_order_not_alphabetical`, `test_pool_selection_deterministic_and_logged_by_label`, `test_ban_code_marks_one_account_inactive_pool_continues`, `test_zero_active_accounts_pauses_day_units_missing_never_zero`, `test_rate_limit_lock_ends_at_day_boundary_not_inactive`, `test_one_unit_one_account_end_to_end_label_in_evidence_no_cookies`, `test_ban_mid_unit_restarts_on_another_account_without_double_count`, `test_aborted_attempt_reads_count_against_global_budget`, `test_second_failure_gives_account_failed_missing`, `test_cross_account_canary_agree_passes`, `test_cross_account_canary_disagree_flags_smaller_account_suspect`, `test_canary_majority_of_three_decides`, `test_suspect_account_excluded_and_earlier_units_flagged_suspect_since`, `test_budget_and_spacing_global_across_pool`, `test_read_accounting_from_search_raw_pages_and_entries_not_parsed_counts`, `test_retries_counted_as_extra_pages_and_setup_overhead_recorded`, `test_parse_drop_page_with_entries_and_zero_parsed_is_layout_changed`, `test_parse_drop_rate_above_threshold_is_layout_changed`, `test_raw_archive_keeps_dropped_entries`, `test_cashtags_without_dollar_matching_case_folded`, `test_none_short_empty_exception_is_missing_never_zero`, `test_codes_88_326_32_403_pause_day_and_alert`, `test_cloudflare_block_flag_false_pauses_day_no_backend_switch`, `test_curl_fallback_decision_table`, `test_canary_must_pass_before_units`, `test_three_parse_failures_set_layout_changed`.
- **Gates:** pytest on the new files and `api/tests/data/attention`; scripts suite; file-set check; hygiene; banned-name grep; no network import in the pure modules.
- **Owner probes:** none beyond P-X9 (recorded in W8a2).

### W8d2: X reader, twscrape wrapper (opus, high; T166)

Depends on W8d1, W8e (worker), W8a2 verdict, P-X9 recorded, Q1 (throwaway account exists) and Q24 (decided 24-10-26: curl fallback allowed behind the flag `x_allow_curl_backend`). The envelope must carry the owner's explicit approval to edit `api/pyproject.toml` and `api/uv.lock` for the optional dependency group.

- **Files:** `api/data/attention/twscrape_reader.py` (lazy import, wrapper implementing `XReader`), edit `api/pyproject.toml` (optional group `xreader` with `twscrape @ git+https://github.com/vladkens/twscrape@<full SHA>`) and regenerate `api/uv.lock` with the repo tooling (never by hand), config keys (`x_accounts_db_path`, `x_pinned_commit`, `x_pinned_version`), additions to `probe_pc_sources.py` (`--source xsearch --reader-status`), tests `api/tests/data/attention/test_twscrape_reader.py`, `api/tests/tooling_guards/test_x_reader_guards.py`.
- **Red-first tests (AC41, AC46, AC47):** `test_default_env_does_not_install_or_import_twscrape`, `test_pinned_full_sha_required_short_sha_refused`, `test_only_package_name_twscrape_from_vladkens_url`, `test_near_names_and_banned_names_refused`, `test_installed_commit_id_must_equal_pinned_sha_and_version_string_is_not_a_guard`, `test_reader_options_wait_timeout_zero_raise_when_no_account_true_and_env_switch`, `test_one_sqlite_file_and_one_api_per_account`, `test_noaccounterror_cause_read_from_pool_row_inactive_locked_active_error`, `test_env_guard_refuses_start_for_each_wrong_variable`, `test_debug_true_never_used`, `test_private_tmpdir_and_twscrape_dump_cleaner`, `test_wrapped_surface_allowlist_and_no_cli_telemetry_import`, `test_curl_fallback_runs_in_separate_process_with_backend_env_only_there`, `test_blocked_by_cloudflare_and_blocked_by_html_both_trigger_fallback_with_flag_on`, `test_html_block_without_flag_pauses_day`, `test_curl_wheel_hash_table_has_win_amd64_manylinux_and_musllinux_entries`, `test_installer_picks_wheel_by_platform_and_records_hash`, `test_startup_verifies_installed_wheel_hash_against_matching_entry`, `test_unknown_platform_or_architecture_refused_fallback_off_and_health_says_so`, `test_curl_cffi_exactly_0_16_3_wheel_hash_only_sdist_refused`, `test_telemetry_env_set_to_zero`, `test_wrapper_refuses_proxy_and_ua_override_and_curl_unless_flag_and_block`, `test_curl_backend_off_by_default_flag_false`, `test_cloudflare_block_flag_true_retries_once_with_curl_then_pauses_day_if_still_blocked`, `test_curl_used_only_after_cloudflare_block_never_for_other_codes`, `test_curl_use_logged_in_evidence_and_health`, `test_next_unit_tries_default_backend_first`, `test_curl_reads_count_against_budget`, `test_no_ua_override_or_proxy_with_curl`, `test_curl_cffi_pinned_in_optional_group_and_lazy_import`, `test_curl_cffi_exact_name_guard`, `test_api_error_abort_req_no_account_mapped_to_reasons`, `test_ban_codes_pause_rest_of_day_and_set_persisted_alert`, `test_cloudflare_html_block_pauses_day`, `test_pool_size_within_configured_bounds_and_unknown_label_refused`, `test_cookie_refresh_is_add_account_cookies_upsert`, `test_start_does_not_call_reset_locks_and_keeps_our_utc_day_locks_across_restart`, `test_all_accounts_locked_pauses_day`, `test_health_active_over_total_with_label_last_used_state_cookie_age_no_secrets`, `test_daily_cross_account_canary_runs_on_two_accounts`, `test_accounts_db_path_outside_repo_required`, `test_accounts_db_permissions_checked_fake_fs`, `test_cookie_age_in_days_in_health`, `test_cookie_upsert_procedure_documented_and_guarded`, `test_logs_class_and_status_only_planted_secrets`, `test_no_auto_update_code_path`.
- **Gates:** pytest on the new files, `api/tests/data/attention` and the guards; `UV_FROZEN=1 uv sync --project api --frozen` still works without the optional group; scripts suite; file-set check (the two dependency files only with the owner's approval in the envelope); hygiene; banned-name grep.
- **Owner steps (account on the 24/7 host):** the accounts database on an encrypted disk outside the repository with permissions limited to the service user; cookie refresh by the documented upsert (exact call from the W8a2 report); never the owner's main or Premium account.
- **Fallback:** if twscrape fails the W8a2 vetting or P-X9, X stays paused and the owner chooses between the API Anything fallback (W8a report, AC27 conditional tests) and the official counts route (SPEC option D); neither is built unless chosen.

### W8h: owner guide and closeout (sonnet)

- **Files:** `narrative-baskets-xreddit-collector-owner-guide_<dd-mm-yy>.md` (one page: one-time login, what the Sources row messages mean, how to re-login, how to turn the worker off, what "one day late" means, honest ban risk), closeout report with pasted probe output and go/no-go; registry update request. **Gate:** doc check (no secrets, no real cookie or path values, banned names absent).

## 6. Test strategy and gates common to code slices

| Gate | Command | Pass |
|---|---|---|
| Slice tests | the named files of the slice, `UV_FROZEN=1 uv run --project api pytest <files> -q` | 0 failed; counts at least baseline + named tests |
| Attention suite | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention -q` | 0 failed; at least baseline until W8f, then baseline + W8f tests |
| Scripts + data/attention + guards | `UV_FROZEN=1 uv run --project api pytest api/tests/scripts api/tests/data/attention api/tests/tooling_guards -q` | 0 failed; skipped and deselected unchanged |
| Full API (once, by the tester) | `UV_FROZEN=1 uv run --project api pytest api -q` | 0 failed; skipped and deselected unchanged |
| File set | `git fetch origin main && git diff --name-only origin/main...HEAD \| sort` | exactly the slice's files; never `.github/`, `api/pyproject.toml`, `api/uv.lock`, `api/data/cache/` |
| Hygiene | `git diff --check origin/main...HEAD` and the secret scan of the Validate Contract (G8) | exit 0; prints nothing |
| Banned names | `git diff -U0 origin/main...HEAD \| grep -niE "xscrape\|kloxeld\|gunkonchi"` | prints nothing, except inside the guard test's split-string constants |

## 7. Hard stops (verbatim for each slice's /goal block)

- Any change under `.github/`, `api/data/cache/`, or to `api/pyproject.toml` or `api/uv.lock` (the only exception: W8d2 adds the optional `xreader` dependency group, and only when its envelope carries the owner's explicit approval): stop and report.
- Any code path or doc that adds or recommends a detection-evasion technique (fingerprint spoofing, proxies, fake or bought accounts, header forgery beyond a plain honest user-agent; the owner's own throwaway account pool of rule 18 is allowed): stop and report.
- Any use, install or mention as a dependency of `xscrape`, `kloxeld` or `gunkonchi`: stop and report.
- Any use of twscrape at any commit other than `63f61a518e576ea5c132f1156c03dda0520d76c1`, any install without the hash-pinned dependencies, any call of `reset_locks`, `login*`, `relogin*`, `add_account` with a password, IMAP, the CLI or an import of `twscrape.cli` or `twscrape.telemetry`, any `debug=True`, any `curl_cffi` other than `0.16.3` from the hash-pinned wheel (never the sdist, never a pre-release): stop and report.
- Any use or install of twscrape before the owner has accepted the W8a2 verdict (VIABLE-WITH-CONDITIONS) and the conditions are in the envelope; any use of the `curl` backend other than the owner-allowed Cloudflare fallback behind `x_allow_curl_backend` (SPEC rule 19, AC53), any proxy, user-agent override, or any account that is not a throwaway account created by the owner (never Premium, never the main account, never bought); a pool read budget or sample larger than the global config values; twscrape 0.20.1 (silent failures); any auto-update of twscrape; any raw page, log or file containing a cookie or request header: stop and report.
- Installing or running API Anything (optional fallback, not planned) before W8a's verdict is accepted by the owner; any install without `--ignore-scripts`; any use of a commit other than `20cb677039fcfe92d3d9c777aa9362e30ff1fdb8`; any call of the registry or publish paths; loading the shipped `sites/x.*` recipe as data: stop.
- A test, tool or log that prints an exception message, header, cookie, token, URL query or response body: stop and report.
- A speed-up of the locked pace (spacing below the configured minimum delay, a default faster than 180 s for X or 60 s for Reddit, a Reddit request with any user agent other than the single honest constant or through a proxy, a daily budget or sample size above the config values, or a halved budget not applied after a warning) or a stored same-day value: stop and report.
- A baseline on fresh main differs from section 8 by anything other than a merged earlier PR: stop and report the numbers.
- Any Reddit-archive call other than the ID endpoints (`/api/posts/ids`, `/api/comments/ids`), any search or aggregate call to it, any retry loop against it, any browser user-agent string, any reddit.com JSON endpoint, or storing a Reddit username: stop and report.
- Any pass, scheduler or config default that drops coins, shrinks `x_sample_n` or `x_page_cap`, shortens a window or cuts pages to fit a time budget (quality over speed, SPEC rule 16), or that lets the X daily read budget or the Reddit daily request budget be exceeded: stop and report.
- `needs_input`: stop; do not merge; never merge any PR. Slice cost at 7 USD: ask; hard cap 15 USD.

## 8. Acceptance criteria mapping (SPEC AC1..AC55 to slices)

| AC | Slice | Strategy |
|---|---|---|
| AC1, AC3, AC4 | W8b, W8c | Fully-Automated |
| AC2 | W8c | Fully-Automated |
| AC5, AC6, AC14 | W8f | Fully-Automated |
| AC7, AC8, AC10, AC13 | W8b (core), W8e (wiring) | Fully-Automated |
| AC9 | W8c (Reddit), W8d (X) | Fully-Automated |
| AC25 | W8c | Fully-Automated |
| AC26 | W8c2 | Fully-Automated |
| AC27 | W8b (wrapper and guards), W8d (use) | Fully-Automated |
| AC28 | W8c (M1), W8c2 (stream) | Fully-Automated |
| AC29 | W8c (ledger), W8c2 (comments into the ledger) | Fully-Automated |
| AC30 | W8c2 | Fully-Automated |
| AC31 | W8c (pure functions) | Fully-Automated |
| AC32 | W8c (pure rule), W8f (Discovery missing rule) | Fully-Automated |
| AC33 | W8c3 | Fully-Automated |
| AC34 | W8c3 | Fully-Automated |
| AC35 | W8c (pure functions), W8c3 (use) | Fully-Automated |
| AC36 | W8c (guard over file lists), W8c3 (allowlist), owner probes P-R7 and P-R8 | Fully-Automated (probes: Agent-Probe) |
| AC37 | W8b (scheduler modes), W8c, W8c2, W8c3, W8d, W8e (use) | Fully-Automated |
| AC38 | W8b (completeness fields), W8e (continue-next-window), W8e2 and W8g (panel text) | Fully-Automated |
| AC39 | W8e2 (payload), W8g (text) | Fully-Automated |
| AC40 | W8e (bounded state, rotation, restart), W8b (state bounds) | Fully-Automated |
| AC41 | W8d1 (interface, fake reader), W8d2 (wrapper, pin, guards) | Fully-Automated |
| AC42 | W8d1 | Fully-Automated |
| AC43 | W8d1 | Fully-Automated |
| AC44 | W8d1 | Fully-Automated |
| AC45 | W8d1 | Fully-Automated |
| AC46 | W8d1 (reason mapping, canary logic), W8d2 (pause, alert) | Fully-Automated |
| AC47 | W8d2 (pool and path checks), W8e2 (cookie age in health) | Fully-Automated |
| AC48 | W8a2, W8d2, owner probe P-X9 | Agent-Probe (owner output) |
| AC49 | W8d1 (selection and state machine), W8d2 (wiring) | Fully-Automated |
| AC50 | W8d1 | Fully-Automated |
| AC51 | W8d1 (comparison logic), W8d2 (daily run) | Fully-Automated |
| AC52 | W8d1 (global accounting), W8d2 (lock cleanup, health payload), W8e2 (health line) | Fully-Automated |
| AC53 | W8d1 (fallback decision logic), W8d2 (wrapper, flag, pin, guard), W8a2 (curl_cffi vetting, done) | Fully-Automated |
| AC54 | W8d1 (accounting and parse-drop logic with fake raw pages), W8d2 (real `search_raw` wiring) | Fully-Automated |
| AC55 | W8d2 (environment, files and wrapped-surface guards) | Fully-Automated |
| AC11, AC12, AC16 | W8b | Fully-Automated |
| AC15, AC20 | W8b | Fully-Automated |
| AC17 | W8c, W8d, W8h | Agent-Probe (owner output) |
| AC18 | W8e plus owner probe P-X7 | Hybrid |
| AC19 | W8b, W8d | Fully-Automated |
| AC21 | W8b (counter and enforcement), W8d (spends it), W8e (persists) | Fully-Automated |
| AC22 | W8b (state machine), W8e (persists) | Fully-Automated |
| AC23 | W8f (scoring), W8b (rotation queue order) | Fully-Automated |
| AC24 | W8e (concurrent streams, carry-over), W8b (pace core) | Fully-Automated |

## Implementation Checklist

Each item is its own EXECUTE envelope and needs the owner's separate ENTER EXECUTE MODE.

- [x] 0. Owner approved the SPEC on 21-10-26 (recorded by T136 on the planner's message); Q13 and Q14 answered yes.
- [ ] 1. W8a vet API Anything, report only (gates X only); owner pastes P-X1, P-X2.
- [ ] 2. W8b pure core (red tests first, then code).
- [ ] 3b. W8c2 Reddit stream-and-count complement incl. comments feeds (after W8c; no wait for W8a).
- [ ] 3c. W8c3 engagement enrichment via archive ids (optional; after W8c; live comment enrichment needs W8c2); owner runs P-R7 and P-R8 now.
- [ ] 3. W8c Reddit connector (plain HTTP, no wait for W8a); owner runs P-R6, P-R3, P-R4 now and P-R2, P-R5 after the build.
- [ ] 4. W8e worker wiring (shell or plug into the T98 W8 worker; written to run unattended for weeks); owner runs P-W1.
- [ ] 5b. W8e2 server host guide and health line (after W8f; before W8g).
- [ ] 5. W8f Discovery wiring.
- [ ] 6. W8g web status text.
- [ ] 6b. W8a2 vet twscrape at the pinned commit (report only); owner then runs P-X9.
- [ ] 7. W8d1 X pure core for twscrape (fake reader); then W8d2 X reader (pinned optional dependency group, owner approval needed for `api/pyproject.toml` and `api/uv.lock`), only after W8a2 and P-X9 and Q1, Q21-Q24; owner runs P-X3 style probes if the fallback is ever built.
- [ ] 8. W8h owner guide and closeout.

## Touchpoints

New files in section 3; edits listed in section 3 (`api/main.py`, `api/data/discovery.json`, `api/analytics/attention/discovery.py`, `sources.py`, `registry.py`, `api/models/discovery.py`, web status text). Read-only references verified on this checkout (`main` 007d53c ancestor): `api/data/attention/store.py` (completed UTC days only, first write wins), `api/data/attention/xsearch.py` and `reddit.py` (existing official-API paths, untouched), `api/data/equities_refresh.py` (pattern), `api/main.py:48-58`, `api/data/discovery.json` (no `fetch_side` yet), `api/data/attention_narratives.json` (75 placed symbols).

## Public Contracts

New config keys `fetch_side` and `source_impl` (W8e, W8f) with strict validation; new source ids `xsearch_web` and `reddit_web`; new env flag `SCREENER_ATTENTION_PC_WORKER` (default off); new Sources row reason codes; no HTTP route change expected (an `updating` status field is reused from T98 W8 if it exists, else added in W8g under owner approval).

## Blast Radius

Runtime: only when the flag is on, on the owner's PC. Tests: new files per slice. Edits to existing modules are confined to W8e (`main.py`, `discovery.json`) and W8f (Discovery and Sources), each with the existing suites as regression gates. No `.github/`, no dependency file.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Density, window and no-same-day tests (W8b) | Fully-Automated | AC1, AC3, AC4 |
| Trickle spacing, config pace, catch-up, priority tests (W8b, W8e) | Fully-Automated | AC8 |
| Daily read budget and adaptive halving tests (W8b, W8d, W8e) | Fully-Automated | AC21, AC22 |
| X rotation scoring and PC-hours window tests (W8f, W8e) | Fully-Automated | AC23, AC24 |
| Pause-on-warning and persistence tests (W8b, W8e) | Fully-Automated | AC10, AC9 |
| Discovery wiring, rescale, point-in-time tests (W8f) | Fully-Automated | AC5, AC6, AC14 |
| Log scrub, secrets, banned-name and pin guards (W8b) | Fully-Automated | AC11, AC12, AC16 |
| Owner probes P-R1 (recorded 403), P-R2..P-R8, P-X1..P-X7, P-W1 | Agent-Probe | AC17, AC18, AC36 |

Baselines measured on this checkout (base `main` 007d53c), `UV_FROZEN=1 uv sync --project api --frozen`, 21-10-26: attention suite 231 passed (28.4 s); scripts + data/attention + tooling_guards: 492 passed, 2 warnings, 62.0 s; rest of API: 1222 passed, 1 skipped, 5 deselected, 2 warnings, 132.2 s (the two groups total 1714 passed). Providers were not contacted; API Anything was not read or run.

## Test Infra Improvement Notes

(none identified yet) One candidate: a shared fake clock plus seeded RNG helper for the trickle tests, built in W8b and reused by W8e and W8d.

## Resume and Execution Handoff

1. Selected plan: this file.
2. Last completed step: SPEC amended and PLAN validated (T131), docs only.
3. Validate-contract status: written (below), Gate: PASS for the PLAN artifact.
4. Context loaded: SPEC (T126 amended), weighted-signal SPEC (T98), `api/main.py`, `equities_refresh.py`, `store.py`, `sources.py`, `discovery.json`, T121 plan (format).
5. Next: the owner's own ENTER EXECUTE MODE for W8a with the planner's envelope (sonnet, report only), after the owner pastes the P-X2 output (section 5, W8a).

## Validate Contract

Status: PASS
Date: 2026-10-21
generated-by: inline FAST MODE (T131)
Gate: PASS

Scope of this gate: the PLAN and the amended SPEC as documents. Per-slice code gates (sections 6 and 7) are the contract for later EXECUTE; they cannot be run now because no code exists. Method: two layers in one session: Layer 1 four dimensions on the PLAN; Layer 2 per-section feasibility with every cite re-read on this checkout.

### Baselines (this checkout, base main 007d53c)

| What | Command | Result |
|---|---|---|
| Attention suite | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention -q` | 231 passed, 2 warnings, 28.4 s |
| Scripts + data/attention + guards | `UV_FROZEN=1 uv run --project api pytest api/tests/scripts api/tests/data/attention api/tests/tooling_guards -q` | 492 passed, 2 warnings, 62.0 s |
| Rest of API | `UV_FROZEN=1 uv run --project api pytest api -q --ignore=api/tests/scripts --ignore=api/tests/data/attention --ignore=api/tests/tooling_guards` | 1222 passed, 1 skipped, 5 deselected, 2 warnings, 132.2 s (the two groups total 1714 passed) |

### Gates run for this PLAN (exact commands; all run in this session)

| Gate | Command | Pass criterion |
|---|---|---|
| V1 plan validator | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-xreddit-collector_PLAN_21-10-26.md` | `"failures": []` |
| V2 file set | `git diff --name-only origin/main...HEAD \| grep -vE "^process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-xreddit-collector_(SPEC\|PLAN\|REPORT)_21-10-26\.md$"` | prints nothing (docs only; no `.github/`, no code) |
| V3 no `.github` | `git diff --name-only origin/main...HEAD \| grep -c "^\.github/"` | prints 0 |
| V4 banned names | `grep -niE "xscrape\|kloxeld\|gunkonchi" process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-xreddit-collector_{SPEC,PLAN}_21-10-26.md` | every hit is inside a "banned/never/malware/guard" sentence (reviewed by hand, listed in the record) |
| V5 secret scan | `git diff -U0 origin/main...HEAD \| grep -nE "^\+.*(Bearer [A-Za-z0-9._-]{12,}\|(API_?KEY\|SECRET\|TOKEN\|PASSWORD)[A-Z_]* *[:=] *[\"'][A-Za-z0-9+/_-]{12,})"` | prints nothing |
| V6 whitespace | `git diff --check origin/main...HEAD` | exit 0 |
| V7 AC count and mapping | `grep -c "^- AC" <SPEC>` and every AC1..AC55 appears in section 8 | count 55 (above the skill's usual 20 by the planner's T133, T135, T138, T139, T163, T166, T167, T168 and T170 instructions); each AC mapped |
| V8 slice coverage | the thirteen slices W8a, W8a2, W8b, W8c, W8c2, W8c3, W8d1, W8d2, W8e, W8e2, W8f, W8g, W8h appear in sections 4 and 5, each with files, tests or doc gate, model, USD, probes (where relevant), branch, dependencies | all present |
| V9 cites | `ls api/main.py api/data/equities_refresh.py api/data/attention/store.py api/analytics/attention/sources.py api/data/discovery.json api/data/attention_narratives.json` and `grep -n "PASS_LOCK\|def _behind\|def start_from_env\|def stop_worker" api/data/equities_refresh.py` | all exist; lines 56, 231, 361, 388 as cited |
| V10 W8 existence | `git ls-tree -r origin/main --name-only \| grep -c attention_pc_refresh` and `grep -rn SCREENER_ATTENTION_PC_WORKER api --include=*.py \| wc -l` | both 0 (as stated in Overview) |

### Hard stops

Section 7, verbatim.

### Dimension findings

| Dimension | Status | Evidence |
|---|---|---|
| infra/setup-fit | PASS | baselines run; every cited file and line exists; `uv` offline-frozen sync works here |
| test-coverage | PASS | each SPEC AC maps to named red tests or an owner probe; live behaviour is a recorded known gap |
| breaking-changes | PASS | edits to existing files confined to W8e and W8f with existing suites as gates; no dependency file or `.github/` change |
| security-surface | PASS | no secrets in files; profile outside repo; log scrub test; banned-name guard; no evasion techniques; API Anything vetted before use |

### Open gaps

None blocking the PLAN. Recorded: (1) the SPEC is approved (T136); (2) W8a cannot read the API Anything repo (outside worker GitHub scope), so it needs the owner's P-X2 paste, and a code-path vetting from a paste alone is partial; (3) other open PRs touching the shared edit files were not checked; (4) the T98 W8 slice may land first, shrinking W8e; (5) every live provider behaviour is UNVERIFIED; (6) the X backfill capacity (about 50 days for 14 days of 75 coins at the locked pace) means X history accrues mostly forward.

### What This Coverage Does NOT Prove

The gates read committed documents and measure existing suites; none calls X, Reddit or API Anything, none proves the density estimate tracks true volume, that the paced requests avoid a limit or a ban (a slow pace lowers volume but does not remove the risk), that hidden mode works with X, or that API Anything's tiers do what the owner describes. Those are the owner probes.

### Accepted by

session (T131 worker, 21-10-26, docs only), on the planner's envelope; the owner approved the SPEC on 21-10-26 (relayed by the planner); no concern in this PLAN is separately accepted by the owner until each slice's ENTER EXECUTE MODE.

## Validation record (T131, 21-10-26)

Gates run in this session on branch `claude/t126-xreddit-collector-spec` (base `main` 007d53c; `origin/main` had moved to 24b1d5e, not merged in, docs only): V1 `"failures": []` (first run failed: no implementation checklist; fixed by adding the Implementation Checklist section); V2 prints nothing; V3 prints 0; V4 hits reviewed by hand, all inside ban or guard sentences (SPEC AC16, Safety constraint and supply-chain risk row; PLAN W8a gate, W8b AC16 test, section 6 gate row, section 7 stop, V4 row); V5 prints nothing; V6 exit 0; V7 count 20 and AC1..AC20 all mapped in section 8; V8 eight slices present; V9 files exist, lines 56, 231, 361, 388 as cited; V10 both 0. Verdict: Gate: PASS for the PLAN artifact.

## Validation record (T133, 21-10-26)

Re-validation after the T133 amendment (config pace, daily read budget, sample N 40, adaptive budget, throwaway account, option D recorded). Gates re-run on branch `claude/t126-xreddit-collector-spec`: V1 plan validator failures [] ; V2 prints nothing; V3 prints 0; V4 hits reviewed by hand, all in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 22 and AC1..AC22 mapped in section 8; V8 eight slices present, W8b USD 5-7, total 22-33; V9 and V10 unchanged (cites and absence of the generic W8 worker re-checked). No code exists, so no code gate ran. Verdict: Gate: PASS for the PLAN artifact. Not proven: the 1,000 posts per day figure is third-party and unofficial; whether a 3-6 minute pace at 800 posts per day triggers warnings is exactly what the adaptive rule and the owner probes are for.

## Validation record (T135, 21-10-26)

Re-validation after recording the owner's answers (shorter delay confirmed, Q10 rotation mode locked, Q11 PC 1-3 h/day, Q12 Reddit unchanged). The owner is still reading the SPEC and has NOT approved it. Gates re-run on branch `claude/t126-xreddit-collector-spec`: V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 24 and AC1..AC24 mapped in section 8; V8 eight slices, W8f USD 3-4, total 23-34. No code exists. Verdict: Gate: PASS for the PLAN artifact. New open items for the owner/planner: Q13 (exact rotation formula and the 7-day rotation lag default), Q14 (concurrent X and Reddit streams; sequential 1.5 h plus 2.5 h would not fit a 1-3 h PC window).

## Validation record (T136, 21-10-26)

Re-validation after the owner's approval of the SPEC (recorded on the planner's message; this session did not see the approval itself) and the answers Q13 (rotation formula and lag default 7) and Q14 (X and Reddit concurrent, per-source locks), now locked in the SPEC and this PLAN. W8a stays first; its envelope readiness and the owner's P-X1, P-X2, P-X2b, P-R1 commands are at the top of the W8a section. Gates re-run on branch `claude/t126-xreddit-collector-spec`: V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 24, AC1..AC24 mapped; V8 eight slices. No code exists. Verdict: Gate: PASS for the PLAN artifact. Not proven: that the owner pasted anything yet; that the API Anything repo is safe (that is W8a).

## Validation record (T138, 21-10-26)

Re-validation after the Reddit access change on the owner's probe evidence (P-R1 `search.json` = 403 with a block page; `new.rss` and `search.rss` = 200). SPEC Annex A.2 rewritten to the public RSS feeds over plain HTTP; Reddit pace 60-120 s and 150 requests per day; W8c no longer depends on W8a or API Anything, so W8b and W8c can start now while W8a gates only X (W8d); W8c USD 2-3, total 22-32; AC2, AC8, AC9, AC17 reworded, AC25 added (25 ACs); Q15 (stream-and-count) and Q16 (PC hours of day) raised; Q12 superseded in part. Gates re-run on branch `claude/t126-xreddit-collector-spec`: V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 25 and AC1..AC25 mapped; V8 eight slices. No code exists. Verdict: Gate: PASS for the PLAN artifact. Not proven: the entry count per feed request, the feed rate limit (about 1 per minute per IP is a third-party report), and how many hours one feed response reaches for a busy coin; probes P-R6, P-R3, P-R4 answer these. The SPEC approval of 21-10-26 covers the T136 text; the owner's approval of these T138 changes is not recorded here.

## Validation record (T139, 21-10-26)

Re-validation after the owner's approval of the T138 changes (recorded on the planner's message) and the answers Q15 (stream-and-count built as a complement: new slice W8c2, method `reddit_stream`, coverage rule 0.8), Q16 (PC hours vary, no UTC window) and the API Anything adapter rules (pinned commit `20cb677039fcfe92d3d9c777aa9362e30ff1fdb8`, registry and publish OFF, shipped X recipe not trusted, `npm ci --ignore-scripts`; the owner's preliminary vetting facts are recorded as inputs in the W8a section, not as a verdict). Gates re-run on branch `claude/t126-xreddit-collector-spec`: V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 28 and AC1..AC28 mapped; V8 nine slices (W8a..W8h and W8c2), total 24-35 USD. No code exists. Verdict: Gate: PASS for the PLAN artifact. Not proven: that the pinned commit is safe (W8a), that feeds return enough entries for a coverage of 0.8 on the days the PC is on (probes P-R6 and the stream status probe), or that the preliminary vetting facts hold (the owner's paste, not read by this session).

## Validation record (T163, 24-10-26)

Re-validation after widening Reddit to comments, votes and proper search without an official API, on the owner probe evidence of 24-10-26 (posts feed 100 entries about 8 days; comments feed 100 entries about 15 hours; `search.rss` works; `search.json` 403; `old.reddit.com` 302; the Arctic Shift archive answers `/api/comments/search` with a lag of about 36-48 h, `/api/posts/ids` works, `/api/posts/search` and `/aggregate` time out). SPEC Annex A.2b, rules 13-14, AC29-AC36, Q17-Q18, probes P-R7 and P-R8; PLAN W8c and W8c2 widened, new slice W8c3 (about 3 USD); total 29-40 USD; X unchanged. PR #153 was already merged, so this work is on a fresh branch `claude/t163-reddit-engagement-spec` from `origin/main` with one new draft PR. Gates re-run: V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 36 and AC1..AC36 mapped; V8 ten slices. No code exists. Verdict: Gate: PASS for the PLAN artifact. Not proven: that `comments/.rss` accepts paging (P-R7), that `/api/comments/ids` works (P-R8), the archive's availability and legality, or that Reddit mention volumes are enough for a useful signal (the minimum-volume rule makes thin coins missing, not zero). The owner's approval of the T163 changes is not recorded in this session.

## Validation record (T163 addenda, 24-10-26)

Re-validation after two planner addenda to T163, both owner decisions of 24-10-26 relayed by the planner (not seen directly in this session and not yet approved there): (1) a spare laptop that runs 24/7 is the target host, so SPEC rule 15 sets a BASELINE schedule (X units spread over the UTC day at a 3-6 minute minimum spacing, Reddit per-coin searches spread over the day with `t=week`, comments feeds every 2 hours, posts feeds every 6 hours, enrichment once a day, Reddit budget 250) and rule 10 keeps the T135 small-window behaviour only as DEGRADED MODE; the X read budget stays the binding limit; Q11 superseded; AC24 and AC30 reworded; AC37-AC40; Annex J (server host requirements); Q19 (Trends on the server) and Q20 (spread reading and Reddit budget); new slice W8e2 (host guide and health line); W8b 6-8 USD, W8e 4-6 USD, total 34-46 USD; (2) 'quality over speed' (rule 16, AC38, hard stop; the cross-source host profile is the separate audit task T164). Gates re-run on branch `claude/t163-reddit-engagement-spec`: V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 40 and AC1..AC40 mapped; V8 eleven slices. No code exists. Verdict: Gate: PASS for the PLAN artifact. Not proven: that the spare laptop will exist, that the Task Scheduler and power commands behave as written (examples, not run), that Reddit honours `t=week` on `search.rss`, or that a 24/7 pace stays inside X's unofficial caps (P-X6, P-X8).

## Validation record (T166, 24-10-26)

Re-validation after the X redesign (owner: "learn from both, make the best of it", throwaway account only, ban and terms-of-service risk accepted, focus only on quality data, 24/7 server available), planner instruction T166. Decision: twscrape is the X primary reader behind a reader interface, pinned to one full commit as an optional dependency group, 0.21.0 raising semantics only; API Anything is demoted to an optional fallback that is not built unless twscrape fails; the pure core of W8b is unchanged. SPEC rule 17, Annex A.1b, AC41-AC48 (48 ACs), Q21-Q24, Q20 recorded as recommended, awaiting owner, probe P-X9 (exact PowerShell), slices W8a2 (vet twscrape, sonnet, 2-3 USD), W8d1 (pure core, opus, 4-5 USD) and W8d2 (reader, opus high, 4-6 USD, owner approval needed for `api/pyproject.toml` and `api/uv.lock`); total 39-53 USD. The twscrape facts are the planner's relay of a reference by session "repo x"; the reference report had not landed (branch `claude/t165-twscrape-reference` absent on origin when checked) and nothing from twscrape was installed or run; W8a2 re-reads the code at the pinned commit. Gates re-run on branch `claude/t163-reddit-engagement-spec` (PR #167): V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 48 and AC1..AC48 mapped; V8 thirteen slices. No code exists. Verdict: Gate: PASS for the PLAN artifact. Not proven: the pinned SHA and its safety, that twscrape works with the throwaway account, that `since_time`/`until_time` or the date operators are honoured, the shape and presence of viewCount and cashtags, the real rate-limit headers, and the owner's approval of the T166 changes.

## Validation record (T167, 24-10-26)

Re-validation after the owner decision (relayed twice by the planner, T166 amendment and T167) that REVERSES the single-account line of T166: the owner WANTS the twscrape account pool and rotation (2-3 throwaway accounts to start, cookie login; throwaway only, never Premium or the main account; ban and terms-of-service risk accepted). SPEC rule 18 sets: selection least recently used with registration-order ties (logged by label); a ban or logout code (88 with remaining above 0, 326, 32, bare 403) marks THAT account inactive and the pool continues; pause the UTC day only at zero active accounts; one coin-day unit by one account end to end with the label (never cookies) in the sidecar; a unit interrupted by a ban restarts once on another account without double counting (aborted reads still count against the budget); a daily cross-account canary (two accounts, same query and window, tolerance 25 percent and overlap 0.6) flags a disagreeing account `suspect` and excludes it; the 800-post budget, sample size and spacing stay GLOBAL; locks older than 15 minutes cleared at start; health line active over total; P-X9 probes each account separately. Kept: no proxy (a per-account proxy is not designed), no user-agent override, no `curl` backend, no auto-update (Q24 stays an owner question). AC41, AC46, AC47 reworded, AC49-AC52 added (52 ACs); Q25-Q27 added; W8d1 5-6 USD, W8d2 5-7 USD, total 41-55 USD. The twscrape facts remain the planner's relay (the reference report had not landed); nothing from twscrape was installed or run. Gates re-run on branch `claude/t163-reddit-engagement-spec` (PR #167): V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 52 and AC1..AC52 mapped; V8 thirteen slices. No code exists. Verdict: Gate: PASS for the PLAN artifact. Not proven: that several throwaway accounts behave as designed (rotation, locks, the canary), that a shadow-limited account returns a measurably smaller result, that the pool does not raise the ban risk (more accounts mean more accounts that can be banned and X may link them; the budget stays global to keep the load constant), and the owner's approval of the T166 and T167 changes.

## Validation record (T168, 24-10-26)

Re-validation after the owner decisions relayed by the planner (T168): Q20 accept all four; Q25 two accounts now, owner creates them, third after a clean fortnight; Q26 least recently used default; Q27 25 percent and 0.6 defaults; Q24 YES: twscrape's curl-cffi backend is allowed ONLY as a Cloudflare fallback behind the owner-set flag `x_allow_curl_backend` (default false). SPEC rule 19 and AC53 define it: the default backend first for every unit; the curl backend only after a Cloudflare or HTML block on the default and only with the flag on; one retry, then the UTC day is paused for the whole pool; never for rate-limit, login or ban codes; no user-agent override, no proxy, no other disguise; every use logged in the evidence and the health line; reads count against the global budget; `curl_cffi` is a second supply chain (compiled wheels with bundled impersonation binaries) vetted in W8a2 and pinned with its hash in the optional dependency group, imported lazily only with the flag on, guarded by an exact-name check. Honest note: browser TLS impersonation is a detection-evasion technique that rules 5, 8 and 17 excluded; this is the single narrow exception the owner decided, accepting the ban and terms-of-service risk on throwaway accounts; the text of rules 8, 17 and 18 now says so instead of contradicting it. W8a2 3-4 USD, W8d2 6-8 USD, total 43-57 USD. Gates re-run on branch `claude/t163-reddit-engagement-spec` (PR #167): V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 53 and AC1..AC53 mapped; V8 thirteen slices. No code exists. Verdict: Gate: PASS for the PLAN artifact. Not proven: that the curl backend defeats the block or that curl_cffi is safe (W8a2), the twscrape API names, and the owner's approval of the T166, T167 and T168 changes.

## Validation record (T170, 24-10-26)

Re-validation after applying the W8a2 vetting report (T169, PR #169, `narrative-baskets-w8a2-twscrape-vetting_REPORT_24-10-26.md`, verdict VIABLE-WITH-CONDITIONS, studied SHA `63f61a518e576ea5c132f1156c03dda0520d76c1`; static reading, nothing installed or run) as the planner ordered in T170: (1) pin by the full commit id, not the version string (the package still reads 0.20.1; no 0.21.0 tag); (2) design A (one SQLite file and one API per account, one unit one account, failover only in our code, because the library silently rotates and continues the cursor); (3) `raise_when_no_account=True`, `wait_timeout=0`, `TWS_RAISE_WHEN_NO_ACCOUNT=1`, the `NoAccountError` cause read from the pool row; (4) read accounting from `search_raw` pages and entries and the `x-rate-limit-*` headers, and 'the library never sleeps' replaced by 'the worker never waits for a locked account'; (5) LRU and UTC-day locks are ours and `reset_locks` is not called at start (rules 18b and 18k fixed); (6) parse-drop guard; (7) environment guard (`TWS_TELEMETRY=0`, `DO_NOT_TRACK=1`, no proxy variables, no `TWS_HTTP_BACKEND` except in the fallback process, WARNING log level, private temporary directory with a cleaner, never `debug=True`); (8) the curl fallback as a separate process with `TWS_HTTP_BACKEND=curl`, `curl_cffi==0.16.3` from the hash-pinned wheel only, the flag `x_allow_curl_backend`, triggered only by `Blocked by Cloudflare`; (9) the wrapped surface list and cashtags without `$`; (10) P-X9 rewritten on the report's corrections. SPEC rules 17-20, AC41, AC43, AC46, AC47, AC49, AC50, AC52, AC53 reworded, AC54-AC55 added (55 ACs), Q28-Q29 added, Annex A.1b rewritten; W8d1 6-7 USD, W8d2 7-9 USD, total 45-59 USD. Gates re-run on branch `claude/t163-reddit-engagement-spec` (PR #167): V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 55 and AC1..AC55 mapped; V8 thirteen slices. No code exists. Verdict: Gate: PASS for the PLAN artifact. Not proven: every live behaviour (the report is static), the P-X9 script (names found in the code, never run), the wheel hashes (read from PyPI JSON as text, not re-checked), the owner's approval of the T166 to T170 changes, and the cross-check against the other session's reference report (never landed).

## Validation record (T179, 24-10-26)

Re-validation after two owner answers relayed by the planner (T179): (1) Q29 decided BOTH: the host OS is not decided, so the Windows and the Linux `curl_cffi==0.16.3` wheel hashes (win_amd64, manylinux x86_64, musllinux x86_64, from the W8a2 report section 9.2) are all pinned in SPEC rule 19; W8d2's installer picks by platform, the startup guard verifies the installed wheel's recorded hash against the matching entry and refuses an unknown platform or architecture (the fallback is then off and the health line says so); the W8e2 server guide covers Windows (auto-start task, powercfg, w32tm) and Linux (systemd) with the final choice at W8e2 (Annex J item 11; auto-login is needed on neither OS because twscrape uses cookies, not a browser session); (2) the curl fallback trigger is 'Cloudflare OR HTML': `Blocked by HTML` also triggers it, with the same limits as before; rule 19, AC46 and AC53 and the W8d1 decision logic wording are updated, and condition C10 of the W8a2 report is recorded as amended in the W8a2 section. Q29 marked decided: both, new Q30 (HTML trigger) decided. W8e2 3-5 USD, total 45-60 USD. Gates re-run on branch `claude/t163-reddit-engagement-spec` (PR #167): V1 plan validator failures []; V2 prints nothing; V3 prints 0; V4 hits only in ban or guard sentences; V5 prints nothing; V6 exit 0; V7 count 55 and AC1..AC55 mapped; V8 thirteen slices. No code exists. Verdict: Gate: PASS for the PLAN artifact. Not proven: that the wheel hashes are current (read from PyPI JSON as text by W8a2, not re-checked), that the Linux or Windows guide commands behave as written (examples, not run), and the owner's approval of the T166 to T179 changes.

## Decisions recorded 30-10-26 (owner decisions accepted in conversation, relayed by the planner; docs only, no test or merge claim)

Recorded on 30-10-26 from the owner's already-accepted answers in this conversation. The T212 W8d2 report (`narrative-baskets-xreddit-collector-t212-w8d2_REPORT_27-10-26.md`, heading 9) asked six questions; the answers are:

- **Q1:** accepted: the W8d2 group keeps the main lock's shared package versions and the two Windows-only transitive packages (heading 8.3 of that report), not the W8a2 report 9.1 versions.
- **Q2:** accepted: the curl_cffi binding (heading 8.4: hash table, `uv.lock` entry, installed `WHEEL` tag and version) is the rule 19(h) implementation. Explicitly NOT done: re-hashing the installed files.
- **Q3:** accepted: on Windows the ACL is not checked by code, it is reported as not checked in the health line, and the owner sets the ACL with `icacls` (host guide section 3). POSIX modes are enforced.
- **Q4:** accepted: the config keys `x_accounts` and `x_pool_max`; the pool size is `len(x_accounts)`, bounded by `x_pool_max`. Wherever the SPEC (rule 18(a), AC47) says `x_pool_size`, read `len(x_accounts)` with the `x_pool_max` bound.
- **Q5:** accepted: retries counted from drops of `x-rate-limit-remaining` between pages are exact only while no other process uses that account (an exclusive account process); otherwise they are an estimate.
- **Q6:** accepted: the config value stays `since_time` (the epoch form), not renamed `epoch`.
- **W8f:** accepted: PC-store reads bypass the probe-record gate (a stored file is the evidence the worker ran, `registry.PC_STORES`), and in X rotation mode the lag check applies to the newest rotation point only (`x_rotation_max_lag_days`).

Not proven by this record: any live behaviour, test result or merge state.
