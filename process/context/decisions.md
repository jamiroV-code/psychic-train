---
name: context:decisions
description: "Decision log index: one entry per durable project decision with date, reason, alternatives, consequences and status (active or superseded), linking to the full record."
keywords: decision, decisions, adr, why, rationale, alternatives, consequences, superseded, policy, direction, consent, authorization
date: 03-10-26
---

# Decisions

One entry per durable decision. Each entry carries: **Decision**, **Date**, **Reason**, **Alternatives** (considered and rejected), **Consequences**, **Status** (`active` or `superseded by D-n`). Full detail lives in the linked source; this file is the index. Add new entries at the bottom; never edit an old one except to mark it superseded.

Abbreviations for sources: **RECOVERY** = `process/general-plans/completed/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md`; **REALIGN** = the personal-tracker-realignment SPEC; **BASKETS** = the narrative-baskets SPEC (both in `process/general-plans/active/`).

## Index

| ID | Decision | Date | Status |
|---|---|---|---|
| D-1 | Personal use only | 02-10-26 | active |
| D-2 | Show data, not verdicts | 02-10-26 | active |
| D-3 | Hard cap of 30 screener coins | 02-10-26 | active |
| D-4 | Narratives are user-defined coin baskets | 02-10-26 | active |
| D-5 | MASTER-PLAN.md is the one board and task registry | 02-10-26 | active |
| D-6 | Workers may self-merge under mechanical conditions | 02-10-26 | active |
| D-7 | Standing consent to delete merged worker task branches | 02-10-26 | active |
| D-8 | Two role-based session entry sets | 02-10-26 | active |
| D-9 | Drop the "Before Any Substantial Task" `find` ritual from CLAUDE.md | 03-10-26 | active |
| D-10 | Worker sessions need no `[MODE:]` response prefix; no `[MODE: ORCHESTRATOR]` note restored | 03-10-26 | active |
| D-11 | Gate 3 live token probes by headless `claude -p` (route A), cap 1 USD per run | 03-10-26 | active |
| D-12 | Pinned planner budget, per-file ceilings and the same-failure stop | 03-10-26 | active |
| D-13 | Gate 4 test counts measured by installing frozen dependencies and running each suite once (G4-K1 = A) | 03-10-26 | active |
| D-15 | Data integration tooling: separate uv project, one approval gate, REA wrapper only (DIT-1..DIT-9) | 14-10-26 | active |
| D-16 | Data integration tooling: cloud run, resource hosts, outlines, bot checks (DIT-10..DIT-13) | 16-10-26 | active |
| D-17 | Narrative baskets: groups are baskets, percentile attention score | 17-10-26 | active |
| D-18 | Narrative baskets: sources and Discovery outlier rules | 17-10-26 | active |
| D-19 | Narrative baskets: daily refresh workflow; trust_weight kept | 17-10-26 | active |
| D-20 | Exchange-token exclusion list | 17-10-26 | superseded by D-27 |
| D-21 | Planner session shell can break with E2BIG in long sessions | 17-10-26 | active |
| D-22 | Weighted attention signal: sources, weights, rising rule | 18-10-26 | active |
| D-23 | exchange_activity composite: four venues, blended by change | 18-10-26 | proposed |
| D-24 | Frozen daily signal snapshots and the calibration plan | 18-10-26 | active |
| D-25 | Tradeable universe and narratives rules | 18-10-26 | active |
| D-26 | Return to full RIPER-5 for new slices; lapse note T96-T107 | 18-10-26 | active |
| D-27 | Exchange tokens are IN as a narrative (supersedes D-20) | 18-10-26 | active |
| D-28 | Nobody pushes to main; branch plus PR, owner merges | 29-10-26 | active |
| D-0 | Original goal: one confidence level that sizes positions | 17-09-26 | superseded by D-1, D-2 |

## Entries

### D-1 Personal use only
- **Decision:** my_site is a personal-use tracker for one user, reached only over Tailscale. The wider-audience goal is dropped.
- **Date:** 02-10-26. **Reason:** the user wants a private research tool, not a product for others.
- **Alternatives:** keep a wider-audience path open (rejected: it forced provider-term handling into every adapter for no current benefit).
- **Consequences:** provider terms matter only for private use (LSE used under its private-use terms); auth, billing, multi-tenancy and public deployment are out of scope; registry T15 demoted to low priority. Source: REALIGN Summary and Constraints; RECOVERY Q7.
- **Status:** active.

### D-2 Show data, not verdicts
- **Decision:** no page computes or shows bullish/bearish calls, confidence badges, signal agreement, trend/momentum tags, scalp PASS/FAIL, `triggered`/`confirmed` flags, narrative state labels or trust weights. They are deleted, not hidden.
- **Date:** 02-10-26. **Reason:** conclusions must be the user's, not nudged by a computed label.
- **Alternatives:** hide verdicts behind a toggle (rejected: verdict logic would survive and drift); keep a cross-signal confidence view (rejected; registry T10 cancelled).
- **Consequences:** realignment task P4 deletes verdict code; the charts/indicators page is not built (T9 cancelled); data-quality labels (pairs status, onchain floor/ramp) stay because they describe data, not the market. Source: REALIGN outcome 1, AC-17, AC-18.
- **Status:** active.

### D-3 Hard cap of 30 screener coins
- **Decision:** the crypto screener holds at most 30 coins; a 31st add is refused with a clear message. Equities are not capped.
- **Date:** 02-10-26 (REALIGN Amendment 2). **Reason:** keeps page-load refresh, the spaghetti chart and groups fast and readable.
- **Alternatives:** no cap (rejected: unbounded refresh cost); soft warning only (rejected: does not bound cost).
- **Consequences:** refresh sizing, tests and storage use 30 coins and about 200 bars of 15m data per coin. Source: REALIGN US-14, outcome 18, AC-26.
- **Status:** active.

### D-4 Narratives are user-defined coin baskets
- **Decision:** /narrative replaces the keyword/category model with narratives the user defines as baskets of screener coins; view 1 equal-weight basket performance rebased to 100, view 2 mindshare as share of total attention; daily resolution; raw data only.
- **Date:** 02-10-26. **Reason:** the hand-kept category model produced verdict-style fields and did not match how the user groups coins.
- **Alternatives:** keep the keyword categories (rejected); market-cap weighting (rejected: equal weight only).
- **Consequences:** task P5 depends on P4; each attention source needs a live probe on the user's PC before it is shown; the pytrends partial-hour fix stays protected (P7). Source: BASKETS Summary, outcomes 19-24.
- **Status:** active.

### D-5 MASTER-PLAN.md is the one board and task registry
- **Decision:** `process/MASTER-PLAN.md` holds the task registry (one row per task) and the lane table; no separate registry or status board exists.
- **Date:** 02-10-26 (RECOVERY Q1). **Reason:** the file already carried T1-T28 and the 3-lane cap; a second board recreates the split-brain registry T24 warned about.
- **Alternatives:** a new `task-registry.md` (rejected: two boards); a status board inside all-context.md (rejected; dropped in R13).
- **Consequences:** the Master Planner is the only registry writer; superseded revision text lives in `process/archive/master-plan-revisions_02-10-26.md`.
- **Status:** active.

### D-6 Workers may self-merge under mechanical conditions
- **Decision:** a worker may merge and archive its own task only when all conditions hold: CI green on the head commit, risk-tier tests passed and independently confirmed, diff inside declared ownership, no conflicts, completion report committed, registry updated by the Master Planner. No class exception (high-risk included). An unsure worker stops at `review`.
- **Date:** 02-10-26 (RECOVERY Q6, user: "no exceptions"). **Reason:** remove approval pauses for routine tasks while keeping evidence-based gates.
- **Alternatives:** exclude high-risk classes from self-merge (recommended, declined by the user); Master Planner merges everything (rejected: slower, same evidence).
- **Consequences:** nothing is platform-enforced (procedure only); post-merge main-CI check with a revert proposal; runtime behaviour that only the user's PC can show keeps a task at `review`. Control-surface self-merge is still an open user decision (RECOVERY Open Question 10). Source: RECOVERY section 4; master-planner.md.
- **Status:** active.

### D-7 Standing consent to delete merged worker task branches
- **Decision:** after a verified merge, a committed report and a registry entry of `accepted` then `archived`, the Master Planner may delete that worker's remote task branch (`claude/<task-id>-<slug>`, created for a registry task), writing an Approvals Log row first.
- **Date:** 02-10-26 (user: "delete merged task branches after verified merge and saved report"). **Reason:** stop branch sprawl without per-branch prompts.
- **Alternatives:** per-branch approval for every deletion (kept for every other branch); never delete (rejected: sprawl was the main problem in MASTER-PLAN rev 3a).
- **Consequences:** the 12 pre-existing remote branches and every local worktree still need per-branch user approval; the delete mechanism is unverified until the Gate 6 pilot; if none works the branch stays. Log: `process/archive/index.md`.
- **Status:** active.

### D-8 Two role-based session entry sets
- **Decision:** a PLANNER set (CLAUDE.md, north-star.md, current-state.md, MASTER-PLAN.md, the all-context router section, the task brief; cap 64,000 bytes) and a WORKER set (CLAUDE.md, the task envelope starting `ROLE: WORKER`, the task PLAN or SPEC; cap 36,000 bytes, 43,000 when the envelope names operating-instructions.md). CLAUDE.md becomes role-neutral.
- **Date:** 02-10-26 (RECOVERY Open Question 11). **Reason:** every session loaded about 200 KB before work; spawned workers must not re-read planner context or behave as orchestrators.
- **Alternatives:** one shared slim set (rejected: workers would still load planner rules); keep `@`-imports (rejected: the main cost).
- **Consequences:** CLAUDE.md and AGENTS.md rewrite at Gate 3; orchestrator rules move to master-planner.md; caps are provisional until measured.
- **Status:** active.

### D-0 Original goal (history)
- **Decision:** turn separate signals into one confidence level that drives position sizing; personal first with a wider audience later.
- **Date:** 17-09-26 (setup). **Reason:** original project brief.
- **Alternatives:** n/a. **Consequences:** shaped the momentum screener's confidence badge and adapter provider-term flags.
- **Status:** superseded by D-1 and D-2 (02-10-26). History: context-changelog.md.

### D-9 Drop the "Before Any Substantial Task" `find` ritual from CLAUDE.md
- **Decision:** CLAUDE.md no longer orders two full `find` listings of `process/context/` and `process/development-protocols/` (a "mandatory gate") before any context is loaded. The ENTRY-SET block (PLANNER and WORKER file lists) replaces it.
- **Date:** 03-10-26 (RECOVERY Gate 3, validate-contract instruction E6). **Reason:** the ritual contradicts the minimal entry sets of D-8 and adds a large listing to every session; the `vc-context-discovery` skill already performs discovery when a task needs it.
- **Alternatives:** keep the ritual (rejected: costs every session, including workers); keep it for planners only (rejected: planners already read the router section of all-context.md, which routes to every group).
- **Consequences:** sessions load only their entry set and open deeper docs on demand. The removed text stays recoverable from git (CLAUDE.md at commit 3faeff4, section "Before Any Substantial Task"). AGENTS.md had no such section; its "consult before substantial work" list is replaced by the same ENTRY-SET block.
- **Status:** active.

### D-10 Worker sessions need no `[MODE:]` response prefix
- **Decision:** the "every response MUST begin with `[MODE: MODE_NAME]`" rule in CLAUDE.md and AGENTS.md applies to PLANNER sessions only; a WORKER (first line `ROLE: WORKER`) does not use it. The `[MODE: ORCHESTRATOR]` informational note from the old files is not restored (accepted omission). The worker report format is master-planner.md section 9; the worker lane is section 6.
- **Date:** 03-10-26 (user decision while reviewing the Gate 3 diff; applied in commit `0b3c9bf`). **Reason:** a worker executes its own task directly under its envelope; a mode banner adds output and implies a RIPER mode a worker is not in.
- **Alternatives:** keep the prefix for every role (rejected by the user: noise for workers); restore the `[MODE: ORCHESTRATOR]` note (rejected: informational only, no rule depended on it).
- **Consequences:** the planner prefix rule stays in CLAUDE.md and AGENTS.md `### Core Protocol` and is scoped by the ENTRY-SET role selection. Open Question 12 (worker lane confirmation) is still open and non-blocking.
- **Status:** active.

### D-11 Gate 3 live token probes by headless `claude -p` (route A)
- **Decision:** the Gate 3 before/after context measurement and the planner/worker role-behaviour checks use headless `claude -p` runs on scratch copies, capped at 1 USD per run (about 0.5 to 4 USD total expected; actual 0.617 USD including a 0.037 USD smoke call).
- **Date:** 03-10-26 (user answered the single V5 question G3-K1 with route A). **Reason:** it is the only way to measure real first-request context without telemetry; sessions and merge tools were not needed.
- **Alternatives:** routes B and C (alternatives named in the Gate 3 contract probe design, section "Probe design"; not chosen); static byte estimates only (kept as the pinned gate, but not real tokens).
- **Consequences:** results are single-run samples, and about 32k tokens of each run is the fixed headless system prompt, not CLAUDE.md. Hook output and the skill listing are unmeasured. Real per-session usage stays a backlog item (`token-usage-telemetry_NOTE_02-10-26.md`). Standing authorization does not cover probes: any new probe needs fresh approval.
- **Status:** active.

### D-12 Pinned planner budget, per-file ceilings and the same-failure stop
- **Decision:** one PLANNER-BUDGET block in master-planner.md section 12 is the only planner byte formula: fixed part (router section + CLAUDE.md + north-star.md + current-state.md + MASTER-PLAN.md) <= 56,000 B, so a task brief <= 8,000 B keeps the 64,000 B cap. Ceilings: CLAUDE.md 16,000; north-star.md 6,000; current-state.md 8,000; MASTER-PLAN.md 19,000; router 7,000; plus a trim rule below 3,000 B headroom. Retry: a worker gets 2 fix cycles; the same failure (same test or gate id and same first error line) twice in a row stops at once; the 10-cycle EVL ceiling is the outer bound. No re-run of unchanged tests (skip check by `git diff --quiet` against the recorded SHA).
- **Date:** 03-10-26 (RECOVERY Gate 4, validate-contract instructions E2-E4). **Reason:** the Gate 3 planner totals could not be reproduced (testers used different sums), and the real margin was 4,045 B, not 9,408 B; three retry numbers disagreed.
- **Alternatives:** keep an informational total only (rejected: not reproducible); raise the cap (rejected: needs the user); a third retry number per gate (rejected: one worker number plus the EVL ceiling).
- **Consequences:** current-state.md and MASTER-PLAN.md were trimmed at Gate 4; compliance with the retry and re-run rules is observable only at the Gate 6 pilot. Rules live in operating-instructions.md (single home of the retry wording; master-planner.md points there); the envelope carries the retry line.
- **Status:** active.

### D-13 Gate 4 test counts measured by install-and-run (G4-K1 = A)
- **Decision:** for Gate 4 the user approved installing frozen dependencies (`uv sync --project api --frozen`, `cd web && pnpm install --frozen-lockfile`) and running pytest, vitest and `tsc --noEmit --incremental false` once each, so the counts in all-tests.md are measured and stamped rather than estimated.
- **Date:** 03-10-26 (user answer to the single V5 question G4-K1). **Reason:** the earlier counts were stale estimates; measured numbers are the only basis for the no-re-run rule.
- **Alternatives:** keep estimates labelled as such (branch B, not chosen).
- **Consequences:** at `753db23`: pytest 873 passed, 1 skipped, 5 deselected, 1 xfailed; vitest 223 in 30 files; tsc exit 0. The island build and Playwright were not in the approval and are not re-measured locally. Standing authorization does not cover installs: any new install needs fresh approval.
- **Status:** active.

### D-14 Narrow exception: estimated leg label on the BTC chart only
- **Decision:** 03-10-26 the user allows a computed estimated leg label (with its numbers visible) on the screener BTC leg chart only; no other page or coin box; the no-verdicts principle is unchanged. **Source:** REALIGN SPEC `## Defect findings and decisions 03-10-26`, F5. **Status:** active.

### D-15 Data integration tooling
- **Decision:** the owner accepted (14-10-26) developer-run data integration tooling: allow-listed REA wrapper plus Scrapling tiers 1-3. Sub-decisions (plan `process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling_PLAN_14-10-26.md`, Common rules):
  - DIT-1 separate uv project `tools/data-integration/` (pinned `scrapling[fetchers]==0.4.15`, pandas/pyarrow/duckdb equal to `api/uv.lock`), never imported by the API, not in CI. Rejected: dependencies in `api/pyproject.toml`.
  - DIT-2 one gate `request_access(...) -> FetchPass | Refused`, host- and page-bound, refusal before any HTTP client exists. Rejected: per-fetcher checks.
  - DIT-3 `<dataset>.provenance.json` beside the data; `cache.py` and `.meta.json` untouched. Rejected: extending `.meta.json`.
  - DIT-4 adaptive SQLite store machine-local, outside repo and site-packages, written only after validation. Rejected: store inside the repo.
  - DIT-5 mocks plus a loopback fixture server; markers `browser`, `antibot`; tier 3 not proven on any real site. Rejected: tests against real sites.
  - DIT-6 REA wrapper only: `setup` never run, no MCP, no `.mcp.json`, no agent-config change. Rejected: `rea-agents setup`.
  - DIT-7 docs: one section in `all-data-sources.md`, one row in the Task Routing Table of `all-context.md`. Rejected: a new context group.
  - DIT-8 approvals: one `<source>.approval.json` per source under the local app-data folder (env `DIT_APPROVALS_DIR` for tests). Rejected: approvals in the repo.
  - DIT-9 first dataset: long BTC history under new cache key `BTC-HIST`, never replacing the existing BTC series. Rejected: overwriting the BTC key.
- **Owner-level:** Scrapling tiers 1-3 are all built, gated per source by a local approval record only (no per-use go for tier 3); approval records live on the owner's PC only (cloud: DIT-10); REA is wrapper-only because setup writes user-scope config and exposes 127 commands; Farside is untouched; the first dataset is long BTC history. Spend ceiling raised 100 -> 130 USD (14-10-26).
- **Date:** 14-10-26. **Reason:** new data sources need a safe, repeatable, approval-bound path. **Alternatives:** see each DIT line.
- **Consequences:** tiers 2-3 and REA web modes are unproven live; Windows/Python 3.12 unverified until the owner probes AC-16/AC-17. The paused market-framework SPEC's proposed exception text (labelled D-15 inside that SPEC) will be renumbered when it resumes.
- **Status:** active.

### D-16 Data integration tooling: cloud run, resource hosts, outlines, bot checks
- **Decision:** owner decisions 15-16 Oct 2026 extending D-15 (plan Amendments A2-A5):
  - DIT-10 cloud-run: the owner may have the cloud session run the scrape tooling when the owner names a recipe and has approved the site per site in chat. The approval record is made with `approvals add --owner-statement` (non-interactive; refused with a TTY or without an explicit `DIT_APPROVALS_DIR`; the statement must name the source and every host and resource host). Records live in a private store outside the checkout and are never committed. A worker (not the planner inline) runs it and quotes the owner message with its time. The statement cannot prove a human wrote it (known limit). No background scraping. The browser tier uses `/opt/pw-browsers` first; `scrapling install` only on an owner-requested tier 2/3 run. Rejected: owner-PC-only runs.
  - DIT-11 resource-host allowance: optional `resource_hosts` on tier 2/3 approvals: exact https hosts, max 8, sub-resource types only, never navigations; robots checked for the page host only; the listed hosts' terms are the owner's call. Rejected: wildcard or unlisted hosts.
  - DIT-12 outlines: on a selector miss or missing columns the CLI prints a bounded outline of the already-fetched page (counts, host names, link paths, id/class tokens, table header names), never page text or data rows. Rejected: dumping page content.
  - DIT-13 bot-check policy: the tooling stops on bot checks and challenge pages; no solving, no stealth bypass (owner decision 16-10-26, after the owner's request to get past one was declined). Rejected: bypass support.
- **Date:** 16-10-26. **Reason:** live cloud runs needed to prove the tiers on real pages without weakening the gate. **Alternatives:** see each DIT line.
- **Consequences:** live runs (owner-approved per site, cloud): bitbo.io page stopped at a Cloudflare bot check (tier 1 HTTP 428; tier 2 needed outside hosts incl. a challenge host), not bypassed; zorinaq.com/price fetched at tiers 1 and 2 (with resource host cdnjs.cloudflare.com) but has no table, dropped; digrin.com needed the www host and has one table (Date, Adjusted price, Real price, 196 rows) without OHLCV, dropped. No dataset stored; BTC-HIST stays open (options: public data via the normal adapter, or close-only scrape support, which needs design). Owner-run probes AC-16/17/20 still outstanding.
- **Status:** active.

### D-17 Narrative baskets: groups are baskets, percentile attention score
- **Decision:** (P5, 16-17 Oct 2026) groups ARE baskets: one coin per basket, cap 12, renaming a group renames the basket (D-1). A coin's attention is ranked by percentile against a top-100 market-cap reference that excludes stablecoins, wrapped and staked tokens (D-3); ratio = mean(last 7)/mean(last 90) daily.
- **Date:** 17-10-26. **Reason:** one simple, explainable score; no verdict labels. **Alternatives:** separate basket objects, raw z-scores (rejected).
- **Consequences:** missing data is a state (not-probed, unavailable, insufficient-history), never 0. Trigger and momentum code was deleted (T80).
- **Status:** active.

### D-18 Narrative baskets: sources and Discovery outlier rules
- **Decision:** core sources Wikipedia, CoinGecko, exchange volume (incl. Hyperliquid), Google Trends; plus Reddit and X. X is low-trust (weight 0.25), reads insufficient-history until 90 own days, key only in a private environment variable. Discovery: top 100, minimum 24h volume 20M USD, a category counts as gaining only if >= 2 independent source groups agree, 7d vs window baseline, winsorize at the 95th percentile, median shown beside the mean.
- **Date:** 17-10-26. **Reason:** resist single-source spikes and thin coins. **Alternatives:** mean only, no volume floor (rejected).
- **Consequences:** provider shapes are fixture-tested only until the owner runs the probe guide.
- **Status:** active.

### D-19 Narrative baskets: daily refresh workflow; trust_weight kept
- **Decision:** the attention store refreshes through a scheduled GitHub workflow (owner choice 17-10-26) that fails loudly on dark sources. `trust_weight` stays in the `/history` composite (D1/D2 decision) although plan AC-11 text says it should go; removal needs router, models and web checks.
- **Date:** 17-10-26. **Reason:** keep `/history` JSON byte-identical. **Alternatives:** drop the field now (rejected).
- **Consequences:** the workflow was never run live; `record_probe.py` is owner-run, not automated.
- **Status:** active.

### D-20 Exchange-token exclusion list
- **Decision:** owner confirmed 2026-10-17: BNB kept, LEO OKB CRO GT KCS BGB MX excluded (editable in `attention_universe.json` and `discovery.json`; BNB is allowed past the exchange-based-tokens category via `include_despite_category`).
- **Date:** 17-10-26. **Reason:** exchange tokens track their venue, not a narrative. **Alternatives:** keep them all in (rejected for all but BNB).
- **Status:** superseded by D-27.

### D-21 Planner session shell can break with E2BIG in long sessions
- **Decision:** observed 2026-10-17. Every Bash call failed to start with `Could not start /bin/bash: ... exceed the OS exec argument limit (E2BIG)` (command line ~150-170 KB across 3 args), even for `git status`, for a whole long planner session (many compactions). The environment was ~8 KB, so the harness-built command line is the oversized part. Unconfirmed hypotheses: the shell wrapper/snapshot grows with session age, or the shell-init snapshot from the user profile.
  - Effect: stop hook `stop-hook-git-check.sh` kept reporting "untracked files" (checkout not inspectable); they were already merged or on the remote.
  - Workarounds: GitHub MCP tools for repo reads/writes; all edits and test runs in worker sessions from create_session (clean shells). Agent subagents inherit the broken shell and failed.
  - Fix: start a fresh planner session (the repo holds all state). Mitigation: past ~6 hours, many compactions, or the first E2BIG, hand over instead of working around it.
- **Date:** 17-10-26. **Reason:** owner asked to remember this; it will come back. **Alternatives:** keep working around it (rejected).
- **Status:** active.

### D-22 Weighted attention signal: sources, weights, rising rule
- **Decision:** (owner answers in the T98 SPEC, 18-10-26; built in T101 W1) the Discovery signal is a weighted blend. Weights: wikipedia 25, trends 25, reddit 15, xsearch 10, exchange_activity 10, github_dev 8, defillama 7, rescaled over the weight that is available. A source is rising at +10 percent on raw change. A coin triggers when the rising weight is at least 60 percent of the covered weight and the covered weight is at least 30. The history chart needs `min_history_days` 30. CoinGecko volume is the fallback for the exchange_activity slot.
- **Date:** 18-10-26. **Reason:** the earlier per-source-group count made every coin read under 2 sources after the per-source lag finding (T95, fixed in T96). **Alternatives:** keep the 2-group count (rejected).
- **Consequences:** X stays off. Reddit API access was requested by the owner on 18-10-26 and awaits approval. Weights are the owner's to change, never automatically (D-24).
- **Status:** active.

### D-23 exchange_activity composite: four venues, blended by change
- **Decision:** PROPOSAL, unverified: exchange_activity = Binance, Coinbase, Kraken, Hyperliquid with sub-weights 40/25/15/20, blended by each venue's own change, never by summing volumes. The Coinbase and Kraken adapters (W7) are proposed, not approved.
- **Date:** 18-10-26. **Reason:** a summed volume is dominated by the largest venue. **Alternatives:** summed volume (rejected).
- **Status:** proposed.

### D-24 Frozen daily signal snapshots and the calibration plan
- **Decision:** (T105 W9) the daily job stores one frozen signal snapshot per window per day under `api/data/cache/attention/signals/`, first write wins. Calibration plan: a 3-month report, then 6-month weight suggestions (scheduled reminders for 2027-01-18 and 2027-04-18: calibration check and suggestion check). The owner decides every weight change; nothing is applied automatically.
- **Date:** 18-10-26. **Reason:** the signal can only be judged against what it said at the time. **Alternatives:** recompute history on read only (rejected).
- **Consequences:** the file count under `signals/` grows daily; the three 2026-10-17 files are pinned by sha256 in the universe-narratives PLAN gate G8.
- **Status:** active.

### D-25 Tradeable universe and narratives rules
- **Decision:** (owner, 18-10-26; SPEC T108, PLAN T111) Discovery covers the top 100 coins with reasoned exclusions (closed reason list). No volume floor and no volume cut: volume under 20M USD only adds a label. 11 narratives with multi-membership and a 3-coin minimum; coins in no narrative go to an Unassigned bucket. Baskets stays on the old universe lists (Q-V1). The exchange-token question (D-20) is left untouched here; slice U6 writes its entry.
- **Date:** 18-10-26. **Reason:** exclude by reason, not by a volume cut. **Alternatives:** keep the 20M floor (rejected).
- **G-OWN review:** planner-reported (not verified by this task): on 2026-10-21 the owner passed the review of the 11-narrative coin list in `api/data/attention_narratives.json` as on main (75 placed; NEAR, ICP, INJ primary Layer 1 accepted; M left Unassigned; the UNVERIFIED placements RAIN, GRAM, BTW, WLFI, PRL, AKE, STABLE, NIGHT and NEXO DeFi membership accepted as is). The file's `status` field is still `proposed`; a separate small worker task flips it to `reviewed` (pending).
- **Consequences:** slices U1 (T113, #145) and U4 (T114, #144) merged; U2 (T115, PR #146) is an open draft in review; U3 and U5 queued; U6 done in D-27.
- **Status:** active.

### D-26 Return to full RIPER-5 for new slices; lapse note T96-T107
- **Decision:** (owner, 18-10-26) new slices run SPEC, PLAN, VALIDATE (contract and /goal block), an explicit ENTER EXECUTE MODE, an independent review before the owner merges, and EVL gates after each slice. Opus for code slices, sonnet otherwise.
- **Lapse note:** T96-T107 and part of T113 and T114 were merged by the owner before the independent review; T96-T107 skipped PLAN, VALIDATE and EVL.
- **Date:** 18-10-26. **Reason:** speed cost review coverage. **Alternatives:** keep the fast lane (rejected).
- **Status:** active.

### D-27 Exchange tokens are IN as a narrative (supersedes D-20)
- **Decision:** (owner, 18-10-26; slice U6 of the universe-narratives PLAN, T146) exchange tokens (BNB, WBT, LEO, CRO, OKB, HTX, BGB, GT, KCS and later ones) are IN the Discovery universe as the narrative "Exchange tokens"; HYPE, PUMP and NEXO have it as primary (placement in `api/data/attention_narratives.json`). There is no exchange-token exclusion, no volume floor and no volume cut: volume under `thin_volume_label_below_usd` 20000000 (in `universe_rules` of `api/data/discovery.json`) only adds a "thin volume" label. Exclusions stay the closed reason list of D-25 (per D-25: stablecoins, tokenized funds, wrapped/staked copies, coins with no market on Binance, Coinbase, Kraken or Hyperliquid); in code today `universe_rules` has the classes stablecoin, wrapped_staked and tokenized_fund and `not_tradeable` is empty. Each exclusion shows its reason.
- **Date:** 18-10-26. **Reason:** the goal is attention on coins the owner can trade; exchange tokens are tradeable and have their own attention. **Alternatives:** keep the D-20 exclusion list (rejected by the owner); keep a 5M backup floor (rejected).
- **Consequences:** thin exchange tokens will often read "low data". `exclude`, `exclude_category_ids`, `include_despite_category` and the volume floor are gone from `discovery.json`. The Baskets tab keeps the old universe lists of `attention_universe.json` for its reference (its scores are unchanged); moving Baskets to the new universe is a separate decision (Q-V1). Does not change D-22..D-26. The weight numbers listed in D-22 are superseded by weights v2 (PR #156, merged: trends 25, reddit 20, xsearch 15, exchange_activity 15, wikipedia 10, defillama 5, github_dev 0; trends and wikipedia count as one search group; early-source rule); D-22's text is kept as history. The X/Reddit PC-side collector is planned only: its SPEC (PR #153) is approved by the owner (21-10-26) and merged, but no collector code is shipped.
- **Status:** active.

### D-28 Nobody pushes to main; branch plus PR, owner merges
- **Decision:** (owner, 29-10-26; T217) planner and direct-user sessions no longer commit straight to `main`. They commit on a branch (`claude/<task-id>-<slug>` or a short descriptive branch) and open a PR; the owner merges every PR. The planner is moving to an omp agent on the owner's PC (PC only for now; the server laptop joins later with the same rules). The PC may push task branches and open DRAFT PRs automatically, never push to `main`. Branch protection will be a GitHub ruleset with github-actions[bot] as bypass actor, set by the owner in GitHub settings and tested in audit mode through one daily refresh first (not yet in place; whether ruleset Evaluate mode is available on a public free repo is unverified, the owner checks in GitHub settings).
- **Date:** 29-10-26. **Reason:** GitHub stays the shared source of truth while more than one machine works on the repo. **Alternatives:** keep committing on `main` locally (rejected: diverges from the PC agent's pushes).
- **Consequences:** supersedes the old "commit on main" rule in CLAUDE.md, AGENTS.md, implementation-standards.md, master-planner.md and operating-instructions.md. The daily data workflows push to `main` as github-actions[bot] and are untouched. Tooling: `scripts/pc-sync/`. omp mapping notes (UNVERIFIED): `process/context/omp-setup.md`.
- **Status:** active.
