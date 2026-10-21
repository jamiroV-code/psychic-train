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
Status: VALIDATED: Gate: PASS (the PLAN artifact; per-slice execution gates are the contract for later EXECUTE)
Validation: T131 (FAST MODE: SPEC amendment, PLAN, VALIDATE in one session), 21-10-26, branch base `main` 007d53c. Next step: the owner's separate ENTER EXECUTE MODE per slice, starting with W8a. This session builds nothing.

**Summary:** **SPEC:** `narrative-baskets-xreddit-collector_SPEC_21-10-26.md` (T126, amended by T131, status "ready for owner review (amended T131)"; the owner has NOT approved it, so every slice below is conditional on that approval). Slow trickle (X one coin unit per 10-20 min, Reddit one request per 20-60 s), yesterday-only values, pause on any warning, narrative coins only, Reddit first. Every provider (X, Reddit, API Anything) is unreachable from the build container: live behaviour is UNVERIFIED and proven only by owner probes.

## Overview and Context

Context router: `process/context/all-context.md`; tests: `process/context/tests/all-tests.md`. Phase Completion Rules: a slice is done when its red tests are green, its gates pass, its report lists the owner probes it needs, and (for X) the probes have been run by the owner.

**Generic W8 worker (T98 section W8, Q9): checked on 21-10-26, it does NOT exist on `main`.** `git ls-tree` of `origin/main` has no `attention_pc_refresh` module; a grep for `SCREENER_ATTENTION_PC_WORKER` and `fetch_side` in `api/*.py` finds nothing; `api/main.py:48-58` (lifespan) starts only `refresh_worker` and `equities_refresh`. So W8e builds the worker shell (modelled on `api/data/equities_refresh.py`: `PASS_LOCK` line 56, `_behind` 231, `start_from_env` 361, `stop_worker` 388) and plugs these two sources in. If the planner dispatches the T98 W8 slice first, W8e shrinks to "register the sources, add trickle and pause". Do not build two workers.

## 1. Goal and non-goals

**Goal.** Fill the `xsearch` (weight 10) and `reddit` (weight 15) slots of the weighted signal from the owner's PC without official APIs, as `pc_side` sources, by the SPEC's metrics (Annex A), pacing (Locked pacing rules) and failure rules (Annex D).

**Non-goals.** `.github/` (none of the slices touch it; see section 4), GitHub dev activity, Trends, exchanges, official X or GitHub APIs, the official Reddit API, sentiment, detection-evasion of any kind, installing or running API Anything in this session, editing the SPEC after the owner approves it.

## 2. Owner decisions binding on this PLAN

| # | Decision (owner via planner, T131) | Effect |
|---|---|---|
| 1 | Slow trickle: X one coin unit per 10-20 min random, whole UTC day, never faster to catch up; Reddit one request per 20-60 s, 300 per day | W8b scheduler core and its tests; W8e uses it |
| 2 | Yesterday-only, one day late, today's partial day never stored or shown | W8b window rule; AC1 |
| 3 | Rate-limit, login or suspension warning pauses that source for the rest of the day, no retries; pause persisted | W8b pause state; W8e restart test |
| 4 | Narrative coins only first (Q3); short backfill (Q2); Reddit first, X later after probes; self-repair spend cap 15 USD per month (Q4); both Reddit series kept separate, config picks (Q7) | slice order, W8b cap meter, W8f `source_impl` |
| 5 | No detection-evasion techniques | hard stop in section 7 |

**PLAN rulings where the SPEC is silent (the owner may overrule at EXECUTE approval):**
- R-1 Probe tool: `api/scripts/probe_pc_sources.py` is created in W8b with the argument parser and the reporting helpers (class name, HTTP status, numbers only, shared with the log scrubber); W8c adds Reddit modes; W8d adds X modes. W8a ships NO code (vetting report only, as the planner ordered); the SPEC's Annex H row for W8a that mentioned a probe skeleton is superseded by this ruling.
- R-2 Branches: `claude/<task-id>-<slug>` with the task id the planner assigns; proposed slugs per slice below.
- R-3 Evidence sidecar and pause state live under the cache root (`attention/<source>/_meta/`, `attention/_pc_state/`), which is git-ignored (`api/data/cache/*`, `.gitignore`), so no machine state is committed.
- R-4 API Anything is invoked only through an adapter Protocol (`api/data/attention/pc_adapter.py`); tests use a fake adapter; the real adapter file is added in W8c (Reddit) and W8d (X) only after W8a pins the commit.

## 3. Design summary (what each new file is; paths proposed, UNVERIFIED until EXECUTE)

| File (all new unless marked edit) | Slice | Content |
|---|---|---|
| `api/data/attention/density.py` | W8b | the SPEC A.1 formula (exact, capped, floor, page-cap, below-min), pure |
| `api/data/attention/pc_pace.py` | W8b | trickle scheduler core: next-unit time from a seeded RNG, daily caps, priority queue (yesterday first, then backfill), pause state with persistence; injected clock |
| `api/data/attention/web_queries.py` and `api/data/attention_queries.json` | W8b | per-coin X query terms and Reddit terms, ambiguity list, subreddit list, validator; coin set derived from `attention_narratives.json` |
| `api/data/attention/web_evidence.py` | W8b | evidence sidecar rows (n, span_hours, capped, pagecap, spike, method version, collected_at, backfilled) |
| `api/data/attention/pc_adapter.py` | W8b | adapter Protocol, error classes, fake adapter for tests, cost meter (monthly 15 USD cap) |
| `api/scripts/probe_pc_sources.py` | W8b (Reddit modes W8c, X modes W8d) | owner probe, prints numbers and class names only |
| `api/data/attention/reddit_web.py` | W8c | Reddit connector (listing walk, per-day counts, A.2) |
| `api/data/attention_pc_refresh.py`, edit `api/main.py` lifespan, edit `api/data/discovery.json` (`fetch_side`) | W8e | worker shell, flag `SCREENER_ATTENTION_PC_WORKER`, `_behind` start, trickle, pause |
| edits to `api/analytics/attention/discovery.py`, `sources.py`, `api/data/attention/registry.py`, `api/models/discovery.py` | W8f | `source_impl`, `fetch_side` validation, reasons on the Sources row, backfilled flag |
| `web/components/narrative/` status text (edit only) | W8g | reason text and updating state |
| `api/data/attention/xsearch_web.py` | W8d | X connector (login command, hidden run, windows, canary, breaker) |

## 4. Slices, order, gates (Reddit first)

`.github/`: NO slice touches it. The two existing workflow guards (`api/tests/tooling_guards/test_attention_workflow_guard.py`, `api/tests/scripts/test_ci_workflow.py`) must stay green. If any slice finds it needs a `.github/` edit (for example to stop the GitHub job fetching a `pc_side` source), it stops and reports; the owner's approval comes first.

| Order | Slice | Branch (proposed) | Depends on | Owner ENTER EXECUTE MODE | Model, effort | USD (ask at 7, cap 15) |
|---|---|---|---|---|---|---|
| 1 | W8a vet API Anything (report only) | `claude/<id>-w8a-vet-apianything` | owner approves SPEC | yes, own | sonnet, medium | 2-3 |
| 2 | W8b pure core | `claude/<id>-w8b-collector-core` | W8a verdict "usable" | yes, own | opus, medium | 4-6 |
| 3 | W8c Reddit connector | `claude/<id>-w8c-reddit-web` | W8b; probes P-R1 (before), P-R2..P-R5 (after) | yes, own | opus, medium | 3-5 |
| 4 | W8e worker wiring | `claude/<id>-w8e-pc-worker` | W8b, W8c (or an existing W8 worker) | yes, own | opus, medium | 3-5 |
| 5 | W8f Discovery wiring | `claude/<id>-w8f-discovery-wiring` | W8e, W8c | yes, own | opus, medium | 2-3 |
| 6 | W8g web status text | `claude/<id>-w8g-web-status` | W8f | yes, own | opus, low | 1-2 |
| 7 | W8d X connector | `claude/<id>-w8d-xsearch-web` | W8b, W8e; owner probes P-X1..P-X7 passed and Q1 answered | yes, own, only after the probes | opus, high | 5-7 |
| 8 | W8h owner guide and closeout | `claude/<id>-w8h-closeout` | W8c live (Reddit) and, when built, W8d | yes, own | sonnet, low | 1 |

Total about 21-32 USD. W8c and W8d are independent after W8b; the order puts X last by the owner's decision. After W8g the Reddit source can be live while X does not exist yet.

### File ownership and collision proof

Slices touch disjoint new files except these shared edits, which are serialised by the order above: `api/data/discovery.json` (W8e adds `fetch_side`; W8f adds `source_impl`), `api/scripts/probe_pc_sources.py` (W8b creates, W8c and W8d append their own modes in separate functions), `api/main.py` (W8e only), `api/analytics/attention/discovery.py` and `sources.py` (W8f only). Open PRs touching those files at EXECUTE time must be checked by the planner at dispatch (`git diff --name-only origin/main...<branch>` against each open branch); this session did not check other open PRs.

## 5. Per-slice detail

### W8a: vet API Anything (report only, sonnet)

- **Files:** one report `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-w8a-apianything-vetting_REPORT_<dd-mm-yy>.md`. No code, no install, nothing from the repo is executed.
- **Method (SPEC Annex F):** write down one commit SHA; read the manifest(s) for install, postinstall, prepare, build hooks; list dependencies and versions; read only the code paths the adapter will call (request replay, tier 3 browser launch, self-repair network calls and any file, cookie or env access); list outbound hosts; licence; verdict `usable` / `usable with changes` / `not usable`; decide the adapter shape; answer "does self-repair call a paid LLM".
- **Red-first:** not applicable (docs). **Gate:** the report has the 8 vetting items filled or "UNVERIFIED because X"; `grep -rniE "xscrape|kloxeld|gunkonchi"` over the report finds the name only inside a "banned" sentence.
- **Owner probes (PowerShell, nothing executed from the package):**
  - P-X1: `curl.exe -s -o NUL -w "%{http_code}\n" https://x.com/`
  - P-X2: `git ls-remote https://github.com/goodnight000/api-anything HEAD` then `git clone --no-checkout https://github.com/goodnight000/api-anything C:\vet\apianything` then `git -C C:\vet\apianything checkout --detach <SHA>` then `Get-ChildItem C:\vet\apianything -Recurse -Include package.json,pyproject.toml,setup.py,setup.cfg,requirements*.txt | Select-String -Pattern "postinstall|preinstall|prepare|cmdclass|console_scripts|bin"`
  - P-R1: `curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code} %{size_download}\n" "https://www.reddit.com/r/CryptoCurrency/search.json?q=solana&restrict_sr=1&sort=new&limit=1"`
- **Note:** the worker session may not have GitHub scope for the API Anything repository (it did not in T126); the planner must grant `add_repo` for reading, or the owner pastes the P-X2 output.

### W8b: pure core (opus)

- **Files:** the W8b rows of section 3 plus tests `api/tests/data/attention/test_density.py`, `test_pc_pace.py`, `test_web_queries.py`, `test_web_evidence.py`, `test_pc_adapter.py`, `api/tests/scripts/test_probe_pc_sources.py`, `api/tests/tooling_guards/test_pc_collector_guards.py`.
- **Red-first tests (must fail before the code exists), each named for its SPEC criterion:**
  - AC1: `test_exact_count_when_window_start_reached`, `test_capped_rate_24_times_n_over_span`, `test_span_floor_quarter_hour`, `test_pagecap_uses_k`, `test_below_n_min_is_missing`, `test_boundary_k_equals_n_is_continuous`, `test_no_value_before_window_end_2359_vs_0000`, `test_newest_never_today`.
  - AC3/AC4: `test_failed_collection_stores_nothing`, `test_zero_needs_canary_and_low_median`, `test_second_collection_does_not_change_day`, `test_evidence_row_has_all_fields`.
  - AC8: `test_x_spacing_between_10_and_20_minutes_seeded`, `test_reddit_spacing_between_20_and_60_seconds_seeded`, `test_daily_caps_x100_reddit300`, `test_catch_up_same_pace`, `test_units_spread_over_day_not_front_loaded`, `test_yesterday_before_backfill`.
  - AC10: `test_429_pauses_until_next_utc_midnight`, `test_pause_persists_over_restart`, `test_no_retry_after_warning`, `test_suspension_and_login_expired_stay_paused`, `test_other_source_keeps_running`.
  - AC11/AC12: `test_logs_contain_class_and_status_only_with_planted_secrets`, `test_profile_path_is_gitignored_and_outside_repo`.
  - AC15/AC20: `test_ambiguous_coin_is_missing`, `test_coin_set_is_narrative_placed_symbols_minus_ambiguous`.
  - AC16: `test_dependency_pinned_and_banned_names_absent` (greps requirements, lock and code for xscrape, kloxeld, gunkonchi outside the guard's own constant list built from split strings).
  - AC19: `test_self_repair_refused_after_15_usd_in_month`, `test_cap_resets_next_month`.
- **Gates:** G-B1 `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/scripts/test_probe_pc_sources.py api/tests/tooling_guards/test_pc_collector_guards.py -q` (0 failed; at least baseline + the named tests); G-B2 attention suite unchanged; G-B3 file-set check (section 6, only the W8b files); G-B4 hygiene and secret scan; G-B5 no network import (`grep` for `requests|httpx|socket|urllib|playwright` import lines in the new pure modules prints nothing).
- **Owner probes:** none (pure).

### W8c: Reddit connector (opus)

- **Files:** `api/data/attention/reddit_web.py`, real adapter wrapper for API Anything (file name fixed by W8a), additions to `probe_pc_sources.py` (`--source reddit`), tests `api/tests/data/attention/test_reddit_web.py`.
- **Red-first tests:** `test_walk_back_counts_exact_day_when_window_start_reached`, `test_capped_day_uses_density_with_flag`, `test_day_not_reached_is_missing`, `test_multi_subreddit_query_form`, `test_ambiguity_list_skips_coin`, `test_http_429_pauses_source_no_retry`, `test_403_blocked_reason`, `test_value_written_only_for_completed_day`, `test_writes_reddit_web_store_not_reddit`, `test_evidence_row_written`, `test_budget_300_requests_per_day`.
- **Gates:** pytest on the new file and `api/tests/data/attention`; scripts suite; file-set check; hygiene.
- **Owner probes after the build (PowerShell, from the repo root; each prints numbers and statuses only):**
  - P-R2 `python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --walk`
  - P-R3 `python -m api.scripts.probe_pc_sources --source reddit --symbols SOL,ETH,BTC,AVAX,LINK --paced` (paced at the locked 20-60 s: takes about 5 minutes per 5 requests)
  - P-R4 `curl.exe -s -A "attention-probe/0.1" -o NUL -w "%{http_code} %{size_download}\n" "https://www.reddit.com/r/CryptoCurrency+CryptoMarkets+altcoin/search.json?q=solana&restrict_sr=1&sort=new&limit=1"`
  - P-R5 `python -m api.scripts.probe_pc_sources --source reddit --symbol SOL --compare-scope`

### W8e: worker wiring (opus)

- **Files:** `api/data/attention_pc_refresh.py`, edit `api/main.py` (start in lifespan, stop in `finally`, same pattern as lines 48-58), edit `api/data/discovery.json` (`fetch_side` per source: `xsearch` and `reddit` `pc_side`, others `github`), tests `api/tests/data/test_attention_pc_refresh.py`.
- **Red-first tests:** `test_flag_off_starts_no_thread`, `test_tests_and_runners_never_start_worker_by_default`, `test_behind_source_schedules_first_unit_20s_after_start`, `test_up_to_date_source_waits`, `test_pass_lock_prevents_overlap`, `test_worker_skips_github_side_sources`, `test_restart_keeps_pause_and_daily_counts`, `test_stop_worker_joins_thread`, `test_unit_failure_never_crashes_the_api`, `test_lifespan_starts_and_stops_worker`, `test_no_network_in_tests`.
- **Gates:** pytest on the new file; `api/tests` routers and main-related tests unchanged; the two workflow guards green; G-file-set (only `api/main.py`, `discovery.json` and new files).
- **Owner probe after build:** P-W1 `$env:SCREENER_ATTENTION_PC_WORKER="1"; python -m uvicorn api.main:app --port 8000` run for 1 hour with only Reddit built, then `python -m api.scripts.probe_pc_sources --source reddit --status` (prints stored days, last unit time, pause state, request counts for today). Pass: counts within the caps and spaced as locked.

### W8f: Discovery wiring (opus)

- **Files (edits):** `api/analytics/attention/discovery.py` (config validation of `fetch_side` and `source_impl`; weighted sources read the chosen impl store), `api/analytics/attention/sources.py` (reason codes on the row, state mapping `insufficient-history` / `unavailable` with note), `api/data/attention/registry.py`, `api/models/discovery.py` if a field is added; tests under `api/tests/analytics/attention/`.
- **Red-first tests:** `test_fetch_side_rejects_unknown_value`, `test_source_impl_reads_web_store`, `test_two_methods_never_spliced`, `test_pc_off_gap_rescales_not_zero` (AC6), `test_t96_lag_drops_source`, `test_point_in_time_truncate_recompute_identical` (AC5), `test_backfilled_flag_excludable`, `test_sources_row_shows_reason_code`.
- **Gates:** attention suite at least baseline plus the new tests with 0 failed; existing discovery and sources tests unchanged and green (any deleted or replaced test listed with its reason).
- **Owner probe:** none beyond W8c/W8e.

### W8g: web status text (opus, low)

- **Files (edits):** `web/components/narrative/` Sources/updating text for reason codes and the "one day late" note; vitest additions. Gates: `pnpm` vitest and `tsc` per `process/context/tests/all-tests.md`; no `.github/`. **Owner probe:** look at the Sources page once.

### W8d: X connector (opus, high; only after the owner probes)

- **Preconditions:** W8a verdict usable; Q1 answered (dedicated account); P-X1 and P-X2 pasted; the owner then runs the probe below on W8b's tool before W8d code is accepted.
- **Files:** `api/data/attention/xsearch_web.py`, adapter wrapper for tier 3, additions to `probe_pc_sources.py` (`--source xsearch`), tests `api/tests/data/attention/test_xsearch_web.py`.
- **Red-first tests:** `test_unit_is_one_coin_one_day_at_most_p_pages`, `test_query_has_cashtag_lang_and_filters_and_utc_window`, `test_dedupe_text_and_three_per_author`, `test_canary_failure_pauses_rest_of_day`, `test_login_expired_state_and_pause`, `test_suspension_state_stays_paused`, `test_layout_change_after_3_bad_shapes_attempts_one_repair`, `test_repair_refused_when_cap_spent`, `test_no_value_written_for_today`, `test_value_matches_density_formula`, `test_hidden_flag_passed_to_adapter`, `test_logs_class_and_status_only`.
- **Owner probes (PowerShell, repo root):**
  - P-X3 `python -m api.scripts.probe_pc_sources --source xsearch --symbol SOL --login` once, then `python -m api.scripts.probe_pc_sources --source xsearch --symbol SOL`
  - P-X4 `python -m api.scripts.probe_pc_sources --source xsearch --symbol SOL --hidden` (owner states whether any window appeared)
  - P-X5 `python -m api.scripts.probe_pc_sources --source xsearch --symbol SOL --days-back 1,7,14` (depth beyond 14 days is not needed under the short-backfill decision)
  - P-X6 `python -m api.scripts.probe_pc_sources --source xsearch --symbols SOL,ETH,BTC --paced` (paced at the locked 10-20 min: takes about 45 minutes; the owner leaves it running)
  - P-X7 rerun the second line of P-X3 after 3 days idle
  - Probes P-X3..P-X7 need the W8b probe tool and a connector, so they run after W8b (tool) and, for the full flow, W8d; P-X1 and P-X2 run first.

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

- Any change under `.github/`, `api/pyproject.toml`, `api/uv.lock`, `api/data/cache/`: stop and report.
- Any code path or doc that adds or recommends a detection-evasion technique (fingerprint spoofing, proxy rotation, extra or fake accounts, header forgery beyond a plain honest user-agent): stop and report.
- Any use, install or mention as a dependency of `xscrape`, `kloxeld` or `gunkonchi`: stop and report.
- Installing or running API Anything before W8a's verdict is accepted by the owner and the SHA is pinned: stop.
- A test, tool or log that prints an exception message, header, cookie, token, URL query or response body: stop and report.
- A speed-up of the locked pace (spacing below 10 min for X, below 20 s for Reddit, caps raised) or a stored same-day value: stop and report.
- A baseline on fresh main differs from section 8 by anything other than a merged earlier PR: stop and report the numbers.
- `needs_input`: stop; do not merge; never merge any PR. Slice cost at 7 USD: ask; hard cap 15 USD.

## 8. Acceptance criteria mapping (SPEC AC1..AC20 to slices)

| AC | Slice | Strategy |
|---|---|---|
| AC1, AC3, AC4 | W8b, W8c | Fully-Automated |
| AC2 | W8c | Fully-Automated |
| AC5, AC6, AC14 | W8f | Fully-Automated |
| AC7, AC8, AC10, AC13 | W8b (core), W8e (wiring) | Fully-Automated |
| AC9 | W8c (Reddit), W8d (X) | Fully-Automated |
| AC11, AC12, AC16 | W8b | Fully-Automated |
| AC15, AC20 | W8b | Fully-Automated |
| AC17 | W8c, W8d, W8h | Agent-Probe (owner output) |
| AC18 | W8e plus owner probe P-X7 | Hybrid |
| AC19 | W8b, W8d | Fully-Automated |

## Implementation Checklist

Each item is its own EXECUTE envelope and needs the owner's separate ENTER EXECUTE MODE.

- [ ] 0. Owner reads PR #153 and approves the SPEC (not yet given).
- [ ] 1. W8a vet API Anything, report only; owner pastes P-X1, P-X2, P-R1.
- [ ] 2. W8b pure core (red tests first, then code).
- [ ] 3. W8c Reddit connector; owner runs P-R2..P-R5.
- [ ] 4. W8e worker wiring (shell or plug into the T98 W8 worker); owner runs P-W1.
- [ ] 5. W8f Discovery wiring.
- [ ] 6. W8g web status text.
- [ ] 7. W8d X connector, only after the owner's X probes and Q1; owner runs P-X3..P-X7.
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
| Trickle spacing, caps, catch-up, priority tests (W8b, W8e) | Fully-Automated | AC8 |
| Pause-on-warning and persistence tests (W8b, W8e) | Fully-Automated | AC10, AC9 |
| Discovery wiring, rescale, point-in-time tests (W8f) | Fully-Automated | AC5, AC6, AC14 |
| Log scrub, secrets, banned-name and pin guards (W8b) | Fully-Automated | AC11, AC12, AC16 |
| Owner probes P-R1..P-R5, P-X1..P-X7, P-W1 | Agent-Probe | AC17, AC18 |

Baselines measured on this checkout (base `main` 007d53c), `UV_FROZEN=1 uv sync --project api --frozen`, 21-10-26: attention suite 231 passed (28.4 s); scripts + data/attention + tooling_guards: 492 passed, 2 warnings, 62.0 s; rest of API: 1222 passed, 1 skipped, 5 deselected, 2 warnings, 132.2 s (the two groups total 1714 passed). Providers were not contacted; API Anything was not read or run.

## Test Infra Improvement Notes

(none identified yet) One candidate: a shared fake clock plus seeded RNG helper for the trickle tests, built in W8b and reused by W8e and W8d.

## Resume and Execution Handoff

1. Selected plan: this file.
2. Last completed step: SPEC amended and PLAN validated (T131), docs only.
3. Validate-contract status: written (below), Gate: PASS for the PLAN artifact.
4. Context loaded: SPEC (T126 amended), weighted-signal SPEC (T98), `api/main.py`, `equities_refresh.py`, `store.py`, `sources.py`, `discovery.json`, T121 plan (format).
5. Next: the owner reads PR #153 and approves the SPEC; then the owner's own ENTER EXECUTE MODE for W8a with the planner's envelope (sonnet, report only).

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
| V7 AC count and mapping | `grep -c "^- AC" <SPEC>` and every AC1..AC20 appears in section 8 | count 20 (max 20); each AC mapped |
| V8 slice coverage | the eight slices W8a..W8h appear in sections 4 and 5, each with files, tests or doc gate, model, USD, probes (where relevant), branch, dependencies | all present |
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

None blocking the PLAN. Recorded: (1) the SPEC is not yet approved by the owner; (2) whether a GitHub-scope grant for the API Anything repo is available to W8a; (3) other open PRs touching the shared edit files were not checked; (4) the T98 W8 slice may land first, shrinking W8e; (5) every live provider behaviour is UNVERIFIED; (6) the X backfill capacity (about 50 days for 14 days of 75 coins at the locked pace) means X history accrues mostly forward.

### What This Coverage Does NOT Prove

The gates read committed documents and measure existing suites; none calls X, Reddit or API Anything, none proves the density estimate tracks true volume, that the paced requests avoid a limit or a ban (a slow pace lowers volume but does not remove the risk), that hidden mode works with X, or that API Anything's tiers do what the owner describes. Those are the owner probes.

### Accepted by

session (T131 worker, 21-10-26, docs only), on the planner's envelope; the owner has not accepted the SPEC or this PLAN yet.

## Validation record (T131, 21-10-26)

Gates run in this session on branch `claude/t126-xreddit-collector-spec` (base `main` 007d53c; `origin/main` had moved to 24b1d5e, not merged in, docs only): V1 `"failures": []` (first run failed: no implementation checklist; fixed by adding the Implementation Checklist section); V2 prints nothing; V3 prints 0; V4 hits reviewed by hand, all inside ban or guard sentences (SPEC AC16, Safety constraint and supply-chain risk row; PLAN W8a gate, W8b AC16 test, section 6 gate row, section 7 stop, V4 row); V5 prints nothing; V6 exit 0; V7 count 20 and AC1..AC20 all mapped in section 8; V8 eight slices present; V9 files exist, lines 56, 231, 361, 388 as cited; V10 both 0. Verdict: Gate: PASS for the PLAN artifact.
