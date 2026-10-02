---
name: plan:master-planner-recovery
description: "GATE 1 design proposal: recover project truth, collapse memory into one routed system, slim default session load, add Master Planner task registry + worker lifecycle, risk-based test policy, housekeeping and deploy-path findings. Proposal only; no implementation."
date: 02-10-26
feature: general-plans
---

# Project Recovery, Architecture Cleanup, AI Efficiency and Master Planner Orchestration — GATE 1 Proposal

Date: 02-10-26
Status: PROPOSED, Gate 1 approved in part (user answers 02-10-26 recorded below). Nothing here is executed. VALIDATE must run before any Gate 2 write.
Complexity: COMPLEX (single plan, gated roadmap Gate 2..6; each gate re-enters VALIDATE).

## Status of this plan

Gate 1 approved in part on 02-10-26: Q1, Q2, Q3, Q5, Q6, Q7 are resolved (user answers, see section 13); Q4 and Q8 stay open. VALIDATE is the next phase. No Gate 2 write happens before VALIDATE writes a contract.

## TL;DR

- Today every session loads ~200 KB (~50k tokens) before work starts; ~65% of the biggest file is changelog. Target: a default entry set of ~25 KB (~6k tokens), a ~88% cut, by moving history out of default load, not by deleting it.
- No new doc system. Reuse `process/context/` + `all-context.md` routing, RIPER-5 task folders, `results.tsv`, closeout packets, `completed/` archival. Promote the existing, unreferenced `process/MASTER-PLAN.md` to the ONE task board and registry.
- Add only five small things: `north-star.md`, `current-state.md`, `decisions.md`, `process/archive/index.md`, worker envelope + report templates.
- Master Planner never marks a task `accepted` on a worker's word: acceptance needs independent evidence (CI, a spawned vc-tester, or the user) recorded in the registry. Under the user's standing authorization (section 4) a worker may self-merge and self-archive only when every mechanical safety condition holds; high-risk classes always stop at `review`.
- Four archive operations stay separate: archive docs, mark logically complete, archive a session (allowed only after the handover report is durable and merge verified), delete branch/worktree (never automatic; needs the registry marking `accepted` plus recorded user consent, not yet granted).
- 6 of 8 questions are resolved; 2 remain open (Q4 exciting-meitner, Q8 ref-only fetch). Nothing in Gate 2+ runs before VALIDATE.

---

## Context Envelope

| # | Field | Value |
|---|---|---|
| 1 | feature | general-plans (cross-cutting process) |
| 2 | phase | PLAN |
| 3 | session-goal | Gate 1 proposal for recovery + Master Planner |
| 4 | branch | claude/pensive-albattani-ou0cgv |
| 5 | worktree | /home/user/psychic-train |
| 6 | context-group | planning, tests |
| 7 | blast-radius-packages | process/, CLAUDE.md, AGENTS.md, .gitignore, web/tsconfig.tsbuildinfo (Gate 2+ only) |
| 8 | active-plan | this file |
| 9 | test-runner | uv run pytest | vitest (not triggered by docs work) |
| 10 | validate-contract | none (pending) |

Sources used (not re-audited): Gate 0 audit conclusions; session inventory; remote branch list; `process/MASTER-PLAN.md` (read in full this session, last verified 2026-09-28, stale); realignment SPEC (AC-19, AC-20 moved into this plan). Sandbox note: `git branch -a` here shows only `main` and one working branch; the 13-remote-branch picture is the user-supplied inventory and is NOT re-verified.

## Goals / Non-goals

Goals: (1) recover a verified current-state; (2) one memory system; (3) short default session load; (4) Master Planner with registry, lifecycle, acceptance rule; (5) token and test-cost discipline with measured baselines; (6) evidence-backed housekeeping list; (7) a safe deploy path description.

Non-goals: executing any product task (realignment, narrative baskets, equities); deleting branches/files in this plan; changing deploy config; installing anything; refactoring `cache.py`; touching `api/` or `web/` source (Gate 5 touches only `web/tsconfig.tsbuildinfo` tracking, and only with approval).

---

## 1. Reuse / Modify / New

| Need | Existing mechanism | Decision | Reason |
|---|---|---|---|
| Memory routing | `process/context/all-context.md` + `all-{group}.md` | MODIFY (slim, split changelog) | Already the router; problem is size, not design |
| Task board + registry | `process/MASTER-PLAN.md` (T1..T25, lanes, 3-lane cap) | MODIFY (add schema, reconcile, wire into CLAUDE.md) | Single home; a sibling registry would recreate the split-brain MASTER-PLAN itself warns about (T24) |
| Per-task artifacts | RIPER-5 task folders `{slug}_{dd-mm-yy}/` (PLAN, SPEC, REPORT, REF) | REUSE | Worker report lives at `{task folder}/{slug}_REPORT_{date}.md` (existing convention), not a new `tasks/` tree |
| Loop evidence log | `results.tsv` + per-cycle iteration reports (`vc-autoresearch`) | REUSE | Bounded retry counter already specified |
| Closeout / completion | closeout packet (`vc-generate-closeout`), EVL HANDOFF SUMMARY | REUSE, extend with the 11-field report schema | No parallel report format |
| Archival | `completed/` + `backlog/` folders, UPDATE PROCESS agent | REUSE; add `process/archive/index.md` as an index only | Index, not a second store |
| Changelog | branch `claude/split-all-context` (bf65024) `context-changelog.md` | SALVAGE by cherry-pick or re-derive | Only unique contribution of that branch |
| Worker spawn / monitor | MCP: `create_session`, `send_message`, `list_sessions`, `list_events`, `set_session_tags`, `archive_session`, `subscribe_pr_activity` | REUSE | Cloud session = container + branch = the isolation unit |
| Agent roles | 15 agents, 33 skills | REUSE; Master Planner is a role of the main session, not a 16th agent | Avoid more always-loaded surface |
| Decision memory | scattered ADRs in plan files | NEW `process/context/decisions.md` (index + 1 entry each, links to full ADR) | No single decision log exists |
| North Star | scattered across all-context.md "What This Project Is" | NEW `process/context/north-star.md` | AC-19 |
| Current state | none | NEW `process/context/current-state.md` | Needs timestamped observed facts |
| Worker envelope/report templates | none | NEW `process/development-protocols/master-planner.md` (+ templates section) | One protocol file, not six |
| Test policy | `tests/all-tests.md` | MODIFY (add risk tier table) | Already the test router |

## 2. Exact File Set

| # | Path | Action | Size target | Gate |
|---|---|---|---|---|
| F1 | `process/context/north-star.md` | create | ~100 lines (~4 KB) | 2 |
| F2 | `process/context/current-state.md` | create | ~80 lines (~4 KB), every fact stamped (branch, commit, UTC time, command) | 2 |
| F3 | `process/context/decisions.md` | create | index ~60 lines; fields: decision / date / reason / alternatives / consequences / status active-or-superseded | 2 |
| F4 | `process/context/context-changelog.md` | create (move) | whole current changelog (~60 KB), NOT in default load | 2 |
| F5 | `process/context/all-context.md` | modify | <= 300 lines (from 1,223); keep routing, architecture, patterns, stack, open decisions; replace history with one-line pointers to F4 | 2 |
| F6 | `process/MASTER-PLAN.md` | modify | ~250 lines: registry table, lifecycle summary, lane table, reconciled T-list | 2 |
| F7 | `process/development-protocols/master-planner.md` | create | ~200 lines: lifecycle, acceptance rule, envelope, report schema, isolation, archival semantics | 2 |
| F8 | `process/archive/index.md` | create | table by date/task/status/branch/commit/location; grows by row | 2 |
| F9 | `CLAUDE.md` | modify | session-start section rewritten to the short entry set (target <= 20 KB, from 28.9 KB) | 3 |
| F10 | `AGENTS.md` | modify | same pointer rewrite so Codex and Claude cannot drift (<= 20 KB, from 37.9 KB) | 3 |
| F11 | `process/development-protocols/all-development-protocols.md` | modify | add master-planner.md row; mark orchestration.md as on-demand, not default | 3 |
| F12 | `process/context/tests/all-tests.md` | modify | add risk-tier table (section 6) and fix stale counts after measured re-run | 4 |
| F13 | `README.md` (root) | create | ~60 lines: start API/web, runbook pointers | 5 |
| F14 | `web/tsconfig.tsbuildinfo` | `git rm --cached` + `.gitignore` line | approval required | 5 |

Home decision for the registry: inside `process/MASTER-PLAN.md`. Justification: it already exists, already carries T1..T25, lanes and the 3-lane cap, and is the file sessions already cite informally. A sibling file would give two boards. Risk: it is a large file; mitigation: registry holds one row per task (<= 3 lines), details live in each task folder.

Orchestration.md (71 KB) stays unchanged this program; it is moved out of the default load by routing, not by editing. Slimming it is a candidate follow-up task (see registry R-5), unmeasured.

### Default session entry set (the load after Gate 3)

| File | Size | Why default |
|---|---|---|
| CLAUDE.md (rewritten) | <= 20 KB | harness entry |
| north-star.md | ~4 KB | direction |
| current-state.md | ~4 KB | observed truth |
| task brief (from MASTER-PLAN row + task folder PLAN) | ~3-8 KB | the work |
| all-context.md router section only | ~12 KB for 300 lines | routing; deeper files on demand |

Total ~45 KB worst case, ~25-30 KB typical. Honest framing: CLAUDE.md remains the largest default file; trimming it below 20 KB is a Gate 3 measurement, not a promise.

---

## 3. Task Registry Schema and Initial Population

### Schema (columns in MASTER-PLAN.md registry table)

`ID | Objective | Pri (P0-P3) | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location`

Status values: `proposed, approved, queued, in_progress, review, accepted, archived` plus `blocked, failed, cancelled, needs_input`. IDs: keep historical `T#` for reconciled items; new work uses `R#` (recovery program) and `P#` (product tasks from SPECs).

### Initial population (reconciliation of T1..T25 against current reality)

Rule: a status stronger than `review` is written only where independent evidence exists (merged PR, file present). "Evidence" below is from the supplied inputs and MASTER-PLAN; items marked UNVERIFIED must be re-checked in Gate 2 before being written (re-check method: `git log`, file existence, `gh pr view`).

| ID | Objective (short) | Status | Evidence / note |
|---|---|---|---|
| T1 | pytrends partial-hour zeros | accepted | PR #8 merged to main (MASTER-PLAN) |
| T1b | isPartial guard in batched path | accepted | PR #6/#7 landed per user input; UNVERIFIED on main, confirm via grep in `pytrends_adapter.py::_fetch_batch_live` |
| T3 | narrative-v2 (PR #7) | review | merged; RFC-7 CODE DONE, AC-14 user walkthrough outstanding -> `needs_input` for walkthrough |
| T4 | Reddit secrets or drop | needs_input | user action; MASTER-PLAN says leave for now |
| T5 | /pairs automation | review | done by P1 (`pairs-refresh-snapshot.yml`), but CODE DONE not VERIFIED; commit step inert on Actions |
| T7 | narrative-dashboard v1 closeout | needs_input | 2 PENDING review decisions; AC-3/AC-12 never run; user PC |
| T8 | refresh context docs | superseded by R2/R3 | folded into this program |
| T9 | charting page | cancelled | realignment AC-17: charts page not built |
| T10 | cross-signal confidence view | cancelled | realignment AC-18: principle retired |
| T11 | lying plan status strips | proposed | fix lives on unmerged `exciting-meitner`; UNVERIFIED |
| T12 | equity provider decision | proposed -> superseded in part | LSE verdict ADOPT-WITH-LIMITS on unmerged branch; realignment SPEC adopts LSE private-use equities page (queued as P4) |
| T13 | CI | accepted | `.github/workflows/ci.yml` exists (pytest + vitest/tsc/island build; no e2e/lint) |
| T14 | UI shell | review | Direction D merged (PR #9); no human visual acceptance recorded |
| T15 | redistribution flags | proposed (P3, low priority) | Q7 resolved 02-10-26: demoted; licensing is no longer a design constraint (personal use) |
| T16 | root README | proposed | no root README (Gate 0); scheduled as F13 |
| T17 | `.agents/skills` duplicate | proposed | 17 MB duplicate; symlink fix is housekeeping H1 |
| T18 | dead `write/read_confirmed_boundaries` | proposed | needs grep + test evidence before deletion (H4) |
| T19 | archive stale plans from `active/` | proposed | candidate for the archive index in Gate 5 |
| T20 | tsbuildinfo tracked | proposed | confirmed tracked (Gate 0) |
| T21 | cache.py refactor | proposed | solo task, deferred; low value vs personal-use goal |
| T22 | cache-isolation trap | proposed | not a live bug |
| T23 | reconcile branches | in_progress -> partially done | five branches sit at merged-PR heads; needs ref-only fetch for ahead/behind (approval) |
| T24 | one status board | superseded by R2/R6 | decided here: MASTER-PLAN is the one board |
| T25 | delete stale branches | proposed | deletion needs approval (H-list) |
| T2, T6 | not present in MASTER-PLAN 09-28 | n/a | numbering gaps; recorded as unknown, not invented |
| P1 | pipeline completeness | review | PR #11 merged; CODE DONE, three CONDITIONAL gaps (real cron firing unverified, etf_flows write non-atomic, inert commits) |
| P2 | deployability (home PC + Tailscale) | review | PR #10 merged; Q3 resolved 02-10-26: build the 3 deploy fixes as R12 |
| P2b | stale-build guard | superseded by R12 | gap from 2026-10-01 live incident; folded into R12 |
| P3 | UI Direction D | review | same as T14 |

New recovery tasks (this program):

| ID | Objective | Status | Gate |
|---|---|---|---|
| R1 | Re-verify ground truth, write current-state.md | proposed | 2 |
| R2 | north-star.md + decisions.md | proposed | 2 |
| R3 | Slim all-context.md, create context-changelog.md | proposed | 2 |
| R4 | master-planner.md protocol + templates | proposed | 2 |
| R5 | Registry rewrite in MASTER-PLAN.md | proposed | 2 |
| R6 | CLAUDE.md / AGENTS.md session-start rewrite, drift check | proposed | 3 |
| R7 | Token baseline measurement | proposed | 3 |
| R8 | Test policy into all-tests.md | proposed | 4 |
| R9 | Housekeeping (approved items only) | proposed | 5 |
| R10 | Deploy path doc + stale-build guard proposal | proposed | 5 |
| R11 | Archive index + session triage | proposed | 5 |
| R12 | Deploy fixes (Q3 resolved 02-10-26): stop the old web process (kill-by-port) before build; stale-build guard in `start-web`; post-start smoke check. Own task, high-risk class (deploy/runtime/proxy): never self-merged, stops at `review`, user runs deploy-script verification on the PC | proposed (decision to build recorded; becomes `approved` on confirmation of its task brief) | 5 |

Queued product tasks (from SPECs; `proposed`, NOT executed, NOT approved):

| ID | Objective | Source | Status |
|---|---|---|---|
| P4 | Realignment (screener + product): delete verdict code, screener RSI/groups/30-coin cap, charts, BTC leg strip, 15-min refresh, lean storage | `process/general-plans/active/personal-tracker-realignment_02-10-26/` (19 active ACs) | proposed |
| P5 | Narrative baskets (user-defined, equal-weight basket view, mindshare share-of-total, /narrative raw-only) | `process/general-plans/active/narrative-baskets_02-10-26/` (12 active ACs) | proposed, deps P4 |
| P6 | LSE equities page with Add button, private-use note | realignment SPEC (personal-tracker-realignment_02-10-26) | proposed, deps P4 |
| P7 | Protect pytrends partial-hour fix + nightly archive (guard tests) | owning SPEC to be confirmed at VALIDATE (personal-tracker-realignment or narrative-baskets) | proposed, rides with P4 |

Q5 resolved 02-10-26: the realignment SPEC was split into the two SPECs above. The old AC-19 (North Star) and AC-20 (docs/process) are owned by THIS plan as AC-R3 and AC-R4 (via R2/R3/R5) and are outside both product SPECs.

---

## 4. Master Planner Lifecycle Spec

Role: the main Claude session in "Master Planner" posture. It plans, registers, dispatches, monitors, and accepts. It does not implement.

### Status transitions

```
proposed -> approved (user) -> queued (deps met, lane free) -> in_progress (worker spawned)
in_progress -> review (worker report received) -> accepted (independent evidence) -> archived
in_progress|review -> failed (retry budget exhausted) | blocked (named blocker) | needs_input (user question)
any pre-accepted state -> cancelled (user or planner with reason)
review -> in_progress (acceptance rejected, with reasons; counts against retry budget)
```

### Acceptance rule (hard)

`accepted` requires ALL of: (a) report has all 11 fields; (b) tests named in the task's test requirement were re-run by a party other than the implementer (spawned vc-tester or the user) and results recorded with command + timestamp; (c) changed-file list matches the task's file ownership; (d) for tasks with user-visible behavior, user acceptance or a recorded agent-probe. A worker saying "done" yields `review` only; the standing authorization lets a worker self-merge only under the mechanical conditions in the Standing authorization subsection, and never for high-risk classes. Absence of any tier-required evidence keeps the task `review` and is recorded as a gap (vacuous-green ban: known-gap cannot be PASS).

### Decomposition rules

One task = one objective, one acceptance statement, <= ~15 files or one blast-radius area, one owning branch. Split when: files cross `api/` and `web/` ownership, a schema/contract change is involved (own task, lands first), or acceptance needs a user decision (separate `needs_input` task). Each task states deps; no task starts with an unmet dep.

### Worker context envelope (what a worker receives; <= ~10 KB)

1. Task ID, objective, acceptance statement. 2. Exact files owned and files forbidden. 3. Branch name. 4. Links (not contents) to north-star.md, current-state.md, the task PLAN/SPEC. 5. Test requirement + budget (section 6). 6. Retry budget (default 2 fix cycles). 7. Report destination path and the 11-field schema. 8. Stop conditions (irreversible/outward actions, scope expansion). 9. Autonomy statement. Workers load deeper context on demand via the router, not by default.

### Completion report (11 required fields) at `{task folder}/{slug}_REPORT_{dd-mm-yy}.md`

1 Task ID. 2 Outcome (done/partial/failed). 3 Summary (<= 10 lines). 4 Files changed (list). 5 Commits (SHAs) and branch. 6 Tests run (exact command, result, timestamp). 7 Tests NOT run and why. 8 Deviations from scope. 9 Blockers/risks/open questions. 10 Follow-up tasks proposed. 11 Context cost note (files loaded, approximate tokens; "unmeasured" allowed).

### Isolation model

| Environment | Unit of isolation | Mechanism |
|---|---|---|
| Cloud | one session = one container + one branch | `create_session(prompt, branch)`; branch name `claude/<task-id>-<slug>` |
| Local PC (user's) | git worktree | optional, user-driven; Master Planner records path in registry but cannot create it from the cloud |

Max parallel lanes: 3 concurrent worker sessions, excluding the Master Planner's own session (existing MASTER-PLAN cap; Q6 wording). Ownership rule: each lane names owned path globs and forbidden globs in the registry row; two lanes may not own an overlapping glob; shared files (`.gitignore`, `all-context.md`, `CLAUDE.md`) are owned by exactly one lane at a time, others write requirements as notes. Conflict handling: planner detects overlap at queue time (compare globs); a detected overlap forces serialization, not a merge race.

### Standing authorization (Q6, resolved 02-10-26)

User's own words, verbatim: "it spawns workers for tasks you already marked approved, without asking again (max 3 sessions at the same time excl. master planner session), each session can merge and archive on itself automatically if it's sure it's ready and safe to merge".

Operational reading (this is the written authorization; anything not listed is NOT granted):

1. Spawn: the Master Planner may `create_session` a worker for any registry task whose status is `approved`, without asking again. Max 3 concurrent worker sessions, excluding the Master Planner's own.
2. Self-merge and self-archive: a worker may merge its own branch and archive its own session WITHOUT asking only when ALL mechanical safety conditions hold: (a) CI green on the head commit; (b) the task's risk-tier tests (section 6 table) all passed and were independently re-run or confirmed by CI; (c) the diff touches only files in the task's declared ownership; (d) no merge conflicts; (e) the completion report (11 fields) is persisted and committed; (f) the registry entry is updated to `accepted` then `archived` with commit refs.
3. Excluded: tasks in a high-risk class (auth/identity, billing, schema/data migration, public API contract, deploy/runtime/proxy, secrets/trust boundary) are excluded from self-merge. They stop at `review` and need the user. FLAGGED FOR USER CONFIRMATION: the user may loosen this.
4. The four archive operations stay separate. A session may be archived (`archive_session`) only after its handover report is durable and the merge is verified. Branches are never deleted and worktrees never removed automatically unless the registry marks the task `accepted` AND the user's standing consent for branch deletion is recorded; that consent is NOT granted by this answer.
5. The Master Planner, not the worker, writes the registry and `current-state.md` updates after each merge.
6. Fail-safe: any worker that is unsure stops at `review`.

Tension with the acceptance rule ("never mark accepted because a worker says done") and its resolution: item 2 does not rest on the worker's say-so. Self-merge requires independent evidence (CI on the head commit, or a re-run by a party other than the implementer) plus mechanical diff-ownership and report checks. If any evidence is missing, the task stays `review`. So "worker is sure" is a necessary trigger, never a sufficient one.

### Completion lifecycle and the four separate operations

| Operation | What it means | Tool / supported? | Approval |
|---|---|---|---|
| A. Archive documents | move task folder to `completed/`, add row to `process/archive/index.md` | file move via UPDATE PROCESS | normal task flow, user-visible |
| B. Mark logically complete | registry status `accepted` then `archived` | registry edit | only after acceptance rule |
| C. Terminate/archive a session | `archive_session` MCP | supported | Allowed under the standing authorization only after the handover report is durable and merge verified (item 2/4); otherwise explicit user approval; sessions with unresolved asks are never archived |
| D. Remove branch/worktree | `git push --delete`, `git worktree remove` | not run automatically | Needs registry `accepted` AND recorded user standing consent for deletion (not yet granted); otherwise explicit approval per branch; merged-state check first |

Report wording rule: the planner says "report file written" for A, "registry updated" for B, and states C/D only if the tool call actually returned success. Never claim a session ended because a file was written. Archival never discards active work: an unmerged branch or a session with unresolved asks blocks D/C.

### Session start / end protocols

Start: read entry set; run `vc-review-situation`; compare `current-state.md` stamp with `git rev-parse HEAD` (stale if different, then re-verify before trusting); read the task row + brief; confirm lane and file ownership. End: write/refresh `current-state.md` (branch, commit, uncommitted work, test results with timestamps, next action); update the registry row; write report; leave uncommitted work either committed to the task branch or listed explicitly.

---

## 5. Token-Efficiency Plan

Baseline (from Gate 0, bytes; tokens estimated at ~4 bytes/token and therefore approximate):

| Item | Bytes | ~Tokens |
|---|---|---|
| CLAUDE.md | 28.9 KB | 7k |
| all-context.md | 93.7 KB (1,223 lines, >= 65% changelog) | 23k |
| orchestration.md | 71.3 KB | 18k |
| Mandatory load total | ~200 KB | ~50k |
| AGENTS.md (Codex copy) | 37.9 KB | drift unmeasured |
| .agents/skills | 17 MB duplicate | not loaded by default; discovery noise |

Measures:

| Lever | Expected effect | Status |
|---|---|---|
| Move changelog out of default load (F4/F5) | all-context 93.7 -> ~25 KB | designed; measure after Gate 2 |
| Short entry set (F9) | default ~200 KB -> ~25-45 KB | designed; measure after Gate 3 |
| Direct path for trivial changes (existing QUICK FIX / trivial-fix lane) | skip RESEARCH/PLAN for <= ~100 lines, no schema/auth/API | reuse; enforce in master-planner.md |
| Bounded retries | max 2 fix cycles per task, 3 per gate before `blocked`; existing 10-cycle PVL/EVL cap stays as a ceiling | design |
| Concise reports | 11-field schema, summary <= 10 lines | design |
| Selective context | worker envelope links, not contents | design |
| De-duplicate `.agents/skills` | removes discovery noise, not session tokens | housekeeping H1 |

Measurement method: `wc -c` on the default entry set before/after (bytes, deterministic); tokens approximated as bytes/4 and labelled approximate. Per-session real token usage: UNMEASURED (no usage telemetry in repo); report field 11 captures a per-task estimate; `list_events` transcripts could be sampled in Gate 3 to get a real baseline for 3-5 past sessions. Unmeasured and kept unmeasured: per-agent token cost, retry waste, cost of repeated test runs, AGENTS.md vs CLAUDE.md drift.

---

## 6. Risk-Based Test Policy

Commands are those named in the repo (all-tests.md, ci.yml, SPEC). Re-confirmed against `all-tests.md` in Gate 4 before being written there.

| Tier | Change type | Required (run once, after the last edit) | Not required |
|---|---|---|---|
| T0 Docs / low | markdown, process files, comments | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <plan>` for plans; `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` for context edits; `git diff --check` | pytest, vitest, Playwright |
| T1 Localized UI | one component/page in `web/` | `pnpm --filter web test` (affected file first, then suite), `pnpm --filter web exec tsc --noEmit` | pytest; Playwright only if a route or flow changed |
| T2 Localized backend | one module/router in `api/` | `uv run --project api pytest <touched test file>` then `uv run --project api pytest api/ -q` once | vitest, Playwright |
| T3 Shared interfaces / business logic | `cache.py`, response models, adapters used by 2+ routes | full pytest, full vitest, `tsc --noEmit`, `pnpm build:islands`; contract-snapshot tests unmodified | Playwright unless a route's behavior changed |
| T4 High risk | auth, secrets, schema/migration, public API contract, deploy/proxy/runtime, destructive data ops | all of T3 + Playwright (`cd web && pnpm test:e2e`) + hybrid/agent-probe evidence pack (`vc-risk-evidence-pack`) + user acceptance | none skipped |

Test budget rule: each task declares its tier and the max number of full-suite runs (T0: 0, T1/T2: 1, T3: 2, T4: 2 plus one EVL confirmation by a spawned vc-tester). No re-running unchanged tests: record in the report the commit SHA each result applies to; a run is repeated only if files changed after that SHA. Bounded retry: a failing gate gets at most 2 fix cycles by the same worker, then escalates to `blocked`/`needs_input`; flake handling: one isolated re-run is allowed to classify a flake, and the flake is logged as a backlog note rather than retried again (consistent with the screener flake note). Environment limits recorded, not hidden: container blocks live provider egress, so live-data checks are user-PC steps (hybrid, `needs_input`). CI (`ci.yml`) is the shared proving ground for T1-T3 on PRs; it does not run e2e or lint, so T4 UI/route changes still need local Playwright.

Known-gap policy: any developed behavior proven only by a known-gap stays CONDITIONAL and gets a backlog stub (vacuous-green ban).

---

## 7. Housekeeping Candidates (no deletion on static search alone)

| ID | Candidate | Evidence | Risk | Needs approval |
|---|---|---|---|---|
| H1 | `.agents/skills` (17 MB) duplicate of `.claude/skills` | Gate 0; fails `validate-skills.mjs`/`validate-context-discovery.mjs` per MASTER-PLAN | Codex discovery might rely on it; symlink behavior on the Windows PC unverified | yes (replace with symlink or doc), validators before/after |
| H2 | `web/tsconfig.tsbuildinfo` tracked | Gate 0 | low; `git rm --cached` + ignore | yes |
| H3 | Remote branches: kind-tesla-tat3vo, compassionate-goldberg-o2iq49 (on main per PRs #1/#3/#4), narrative-v2 (duplicate of PR #7 RFC-1), merged-PR branches p1-pipeline, p2-deploy, ui-shell, vigilant-hamilton, fix/narrative-sufficiency-gating-rfc1 | MASTER-PLAN 09-28, NOT re-verified | deleting an unmerged branch loses work; must check ahead/behind and PR state per branch | yes, per branch; first a ref-only fetch (needs approval) |
| H4 | split-all-context (bf65024) | holds unique `context-changelog.md` | losing it before salvage | salvage first, delete never without approval |
| H5 | exciting-meitner | holds unmerged LSE verdict and plan-strip fixes | do not delete; merge or salvage decision (Q4) | yes |
| H6 | Dead `cache.write_confirmed_boundaries/read_confirmed_boundaries` | MASTER-PLAN says zero callers | static search misses dynamic use and scripts | needs grep over `api/scripts` + tests, plus run full pytest; user approval |
| H7 | Stale entries in `process/general-plans/active/` (e.g. momentum-screener_17-09-26 with verified sub-plans) | MASTER-PLAN T19 | archiving moves history; reversible via git | yes, via archive index |
| H8 | No root README | Gate 0 | none | no (additive) |
| H9 | AGENTS.md vs CLAUDE.md drift | sizes differ 37.9 vs 28.9 KB; drift unmeasured | silent divergence | measure in Gate 3 |
| H10 | Scout-block hook blocks commands containing `.next`/`node_modules`/`.venv` | Gate 0 | may hinder build/clean steps in Gate 5 | document, no change without approval |

---

## 8. Performance and Deploy Path

Performance: no baselines exist. Rule: no optimization task is approved without a recorded baseline (command, input size, timestamp). Existing measured figures to adopt as starting points, labelled by source: `compute_pairs.py` ~56 s for 153 pairs; `/api/pairs` read p95 135-232 ms; island entry chunk 185 kB gzipped. Unmeasured: screener refresh time at 30 coins, page load, build time, test suite wall time.

Windows deployment path (from `deploy/` and the 2026-10-01 incident):

`source (git pull on PC) -> test (pytest/vitest/tsc as tier requires) -> build (pnpm build:islands then next build, i.e. pnpm build) -> deploy (restart API and web tasks) -> smoke`

Rebuild requirement: any `web/` change needs `build-web.ps1` (or `pnpm build`) before restart; pulling source alone does not update the served app. Known issue: on 2026-10-01 the live PC served a stale build because `Stop-ScheduledTask` did not kill the node process. Gaps: no auto rebuild after pull, no stale-build guard, no deployed smoke test. This plan only documents the path and proposes the fixes (guard comparing build id/commit to HEAD, kill-by-port in the restart script, a one-request smoke check); Q3 resolved 02-10-26: the fixes will be built as task R12 (own task, Gate 5, high-risk deploy class: stops at `review`, never self-merged). Deploy changes never run unattended.

---

## 9. Gate Roadmap

| Gate | Deliverable | Verification | Needs explicit user approval |
|---|---|---|---|
| 0 | audit (done) | n/a | done |
| 1 | this proposal | user review | approve/modify plan, answer Q1-Q8 |
| 2 | R1-R5: current-state.md (re-verified), north-star.md, decisions.md, context-changelog.md, slimmed all-context.md, master-planner.md, MASTER-PLAN registry, archive index skeleton | VALIDATE first; `wc -l all-context.md` <= 300; `validate-context-discovery.mjs`; `vc-audit-context`; check every moved changelog line exists in F4 (line-count + diff); grep no remaining "confidence over direction"/"public later" in entry points | VALIDATE contract; no source edits; ref-only fetch for branch facts requires approval |
| 3 | R6, R7: CLAUDE.md/AGENTS.md rewrite, protocol router update, byte baselines, sampled session token baseline | `wc -c` before/after table; `validate-agent-parity.mjs --strict`, `validate-protocol-wiring.mjs`, `validate-guide-sync.mjs`; a fresh session must reach a task brief reading only the entry set | CLAUDE.md/AGENTS.md edits (high-visibility, user review before commit) |
| 4 | R8: test policy in all-tests.md, re-measured test counts | run the three suites once (measured, timestamped) | none beyond Gate approval; installs need approval |
| 5 | R9-R12: housekeeping (approved items), README, deploy-path doc/guard proposal, session triage + archive index | per-item evidence re-check; validators; no deletion without per-item approval; R12 verified on the user's PC (hybrid) | branch deletion, `archive_session`, `.agents/skills` replacement, tsbuildinfo untrack, deploy-script changes, any installs |
| 6 | Master Planner pilot: dispatch ONE low-risk task (e.g. P7 guard test or R-level docs task) through the registry end-to-end; then start approved product tasks | pilot task reaches `accepted` through the rule in section 4; report has 11 fields | each product task `approved` by user; spawning workers for `approved` tasks is covered by the standing authorization (section 4, max 3 concurrent); high-risk tasks stop at `review` |

Each gate ends with a closeout (UPDATE PROCESS) and a commit on `main` only when you ask (repo policy).

---

## 10. Acceptance Criteria (this program)

| ID | Criterion | proven by | strategy |
|---|---|---|---|
| AC-R1 | Default session entry set <= ~45 KB and reaches a task brief without loading changelog or orchestration.md | byte table (Gate 3) + fresh-session probe | Fully-Automated (`wc -c`) + Agent-Probe |
| AC-R2 | all-context.md <= 300 lines; changelog fully preserved in context-changelog.md | `wc -l`; diff of moved content | Fully-Automated |
| AC-R3 (=AC-19) | Single North Star doc exists with personal-use, data-not-verdicts, Tailscale-only, page list, non-goals; old confidence/public-later wording gone from entry points | grep of CLAUDE.md, AGENTS.md, all-context.md, north-star.md | Fully-Automated |
| AC-R4 (=AC-20) | Current-state, task registry, archive index, MASTER-PLAN reconciled and referenced from CLAUDE.md/AGENTS.md/all-context | link/grep check + `validate-context-discovery.mjs` | Fully-Automated |
| AC-R5 | Registry holds all T-tasks with a status and evidence note; unverified items labelled UNVERIFIED | review of registry vs section 3 | Hybrid (user review) |
| AC-R6 | No branch, session, or file removed without recorded approval | git/session state diff vs approvals log | Hybrid |
| AC-R7 | Acceptance rule demonstrated: pilot task not `accepted` on worker word alone | pilot report + registry history | Agent-Probe |
| AC-R8 | Product code untouched by Gates 2-4 | `git diff --stat` shows only `process/`, `CLAUDE.md`, `AGENTS.md` | Fully-Automated |
| AC-R9 | Token claims labelled measured/unmeasured | review of Gate 3 report | Hybrid |

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G2 `wc -l process/context/all-context.md` <= 300 | Fully-Automated | AC-R2 |
| G2 changelog content diff/line preservation | Fully-Automated | AC-R2 |
| G2 `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` | Fully-Automated | AC-R4 |
| G2 grep for retired wording in entry points | Fully-Automated | AC-R3 |
| G3 `wc -c` entry set before/after table | Fully-Automated | AC-R1, AC-R9 |
| G3 fresh-session probe reaches task brief on entry set only | Agent-Probe | AC-R1 |
| G3 `validate-agent-parity.mjs --strict`, `validate-protocol-wiring.mjs`, `validate-guide-sync.mjs` | Fully-Automated | AC-R4 |
| G2/G5 registry reviewed against evidence | Hybrid | AC-R5 |
| G5 approvals log vs state diff | Hybrid | AC-R6 |
| G6 pilot task end-to-end | Agent-Probe | AC-R7 |
| G2-G4 `git diff --stat` scope check | Fully-Automated | AC-R8 |

Known gaps (named residuals, keep gates CONDITIONAL): real per-session token usage; behavior of a symlinked `.agents/skills` on the user's Windows PC; deploy fixes verified only on the user's PC (hybrid, user-run). Backlog stubs for these are written at Gate 2.

## 12. Risk Predictions

| Risk | Likelihood | Mitigation |
|---|---|---|
| Slimming loses knowledge | med | changelog moved whole, not edited; diff check; git history |
| Registry becomes a second stale board (as MASTER-PLAN did) | high | wire into CLAUDE.md session start/end; end-of-session registry update is a protocol step; `current-state.md` stamped with commit so staleness is detectable |
| CLAUDE.md rewrite breaks agent routing | med | parity/wiring validators; user review before commit |
| AGENTS.md drifts from CLAUDE.md again | med | both point to the same short entry set; drift check in Gate 3 |
| Worker report claims unverified | high | acceptance rule requires independent re-run |
| Branch deletion destroys unmerged work | low-med | per-branch ahead/behind check, per-branch approval |
| Cloud sessions with unresolved asks get archived | med | C-operation blocked while asks unresolved; list_events review first |
| Self-merge ships a bad change | med | all six mechanical conditions required; independent CI/re-run evidence; high-risk classes excluded; unsure means `review`; user may tighten or loosen |
| Parallel lanes collide on `all-context.md`/`.gitignore` | med | single-owner rule for shared files |
| Token savings overstated | med | bytes measured, tokens approximate, usage unmeasured |

Assumptions: Gate 0 numbers are accurate; MASTER-PLAN facts dated 09-28 may be stale and are labelled; realignment and baskets SPECs are the North Star source; repo policy (commit directly on `main` only on request) applies.

## 13. Open Questions

Resolved 02-10-26 (user answers, authoritative):

1. Q1 RESOLVED 02-10-26: `process/MASTER-PLAN.md` is the single board and task registry (reconciled and wired into session start).
2. Q2 RESOLVED 02-10-26: CLAUDE.md target up to ~20 KB.
3. Q3 RESOLVED 02-10-26: build the 3 deploy fixes (stop old web process before build / kill-by-port, stale-build guard in `start-web`, post-start smoke check) as own task R12 (high-risk deploy class).
4. Q5 RESOLVED 02-10-26: realignment SPEC split into `personal-tracker-realignment_02-10-26` (19 active ACs) and `narrative-baskets_02-10-26` (12 active ACs); docs/process criteria owned here as AC-R3/AC-R4.
5. Q6 RESOLVED 02-10-26: standing authorization recorded verbatim in section 4; high-risk exclusion flagged for user confirmation.
6. Q7 RESOLVED 02-10-26: T15 demoted to low priority; licensing is no longer a design constraint (personal use).

Still OPEN:

- Q4: exciting-meitner (LSE verdict, status-strip fixes): merge, salvage selectively, or leave?
- Q8: approve a ref-only fetch to measure ahead/behind for all remote branches (no merge, no deletion)?
- Confirm (new, from Q6): are high-risk classes to stay excluded from self-merge, or loosen? Also, is standing consent for branch deletion to be granted later? (Neither is granted now.)

---

## Touchpoints

Gate 2-5 writes: `process/context/*` (new and slimmed), `process/MASTER-PLAN.md`, `process/archive/index.md`, `process/development-protocols/master-planner.md`, `all-development-protocols.md`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `web/tsconfig.tsbuildinfo` (untrack), `.gitignore`. Reads: git state, MCP session list, `deploy/`. This plan itself writes only its own file.

## Public Contracts

Behavior contracts other sessions rely on: the default entry set; the task status vocabulary; the acceptance rule; the 11-field report path/schema; the four archive operations. No API, schema, or runtime contract changes.

## Blast Radius

Docs/process only through Gate 4 (risk class: T0). Gate 5 adds git-index and ignore changes (T0-T1) and optional deploy script changes (T4, separately approved). No product code.

## Test Infra Improvement Notes

(none identified yet) Candidate noted: no token-usage telemetry; no deployed smoke test; ci.yml lacks lint/e2e.

## Validate Contract

(placeholder - vc-validate-agent writes this section before EXECUTE). VALIDATE must run before any Gate 2 write; gate must be `Gate: PASS` (or user-accepted CONDITIONAL after a supplement cycle).

## Resume and Execution Handoff

1. Selected plan: `/home/user/psychic-train/process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md`
2. Last completed step: PLAN (Gate 1 proposal written; no implementation).
3. Validate-contract: pending.
4. Context loaded: CLAUDE.md, all-context.md, orchestration.md, MASTER-PLAN.md (full), realignment SPEC (AC grep), repo branch list.
5. Next step: ENTER VALIDATE MODE (Q4 and Q8 still open; they do not block VALIDATE); then Gate 2 via vc-execute-agent (opus) scoped to F1-F8; re-verify every UNVERIFIED registry item first.

## Phase Completion Rules

- A gate is complete only when its Verification Evidence rows are green and recorded with command, timestamp, and commit SHA.
- Status words: `PROPOSED` (this plan), `CODE DONE` (files written, not independently verified), `VERIFIED` (independent re-run, e.g. spawned vc-tester or user). Known-gap alone never yields VERIFIED.
- No gate starts before VALIDATE writes a contract for it and the user approves; archive/delete/session-termination steps need separate explicit approval.
