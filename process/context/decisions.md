---
name: context:decisions
description: "Decision log index: one entry per durable project decision with date, reason, alternatives, consequences and status (active or superseded), linking to the full record."
keywords: decision, decisions, adr, why, rationale, alternatives, consequences, superseded, policy, direction, consent, authorization
date: 03-10-26
---

# Decisions

One entry per durable decision. Each entry carries: **Decision**, **Date**, **Reason**, **Alternatives** (considered and rejected), **Consequences**, **Status** (`active` or `superseded by D-n`). Full detail lives in the linked source; this file is the index. Add new entries at the bottom; never edit an old one except to mark it superseded.

Abbreviations for sources: **RECOVERY** = `process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md`; **REALIGN** = the personal-tracker-realignment SPEC; **BASKETS** = the narrative-baskets SPEC (both in `process/general-plans/active/`).

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
