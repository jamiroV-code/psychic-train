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
- **Status:** active.
