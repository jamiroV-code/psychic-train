---
name: plan:master-planner-recovery
description: "GATE 1 design proposal: recover project truth, collapse memory into one routed system, slim default session load, add Master Planner task registry + worker lifecycle, risk-based test policy, housekeeping and deploy-path findings. Proposal only; no implementation."
date: 02-10-26
feature: general-plans
---

# Project Recovery, Architecture Cleanup, AI Efficiency and Master Planner Orchestration — GATE 1 Proposal

Date: 02-10-26
Status: PROPOSED, Gate 1 approved (all user answers 02-10-26 recorded below; Q1-Q8 resolved). Nothing here is executed. VALIDATE is next and must run before any Gate 2 write. Working tree: plan file edits only (this file); no other file touched.
Complexity: COMPLEX (single plan, gated roadmap Gate 2..6; each gate re-enters VALIDATE).

## Status of this plan

Gate 1: approved (02-10-26). Q1-Q8 are all resolved (user answers, section 13); Q4 and Q8 are now Resolved. VALIDATE is the next phase. No Gate 2 write happens before VALIDATE writes a contract. Working tree: only this plan file was edited in this supplement.

## TL;DR

- Today every session loads ~200 KB (~50k tokens) before work starts; ~65% of the biggest file is changelog. Target: a default entry set of ~25 KB (~6k tokens), a ~88% cut, by moving history out of default load, not by deleting it.
- No new doc system. Reuse `process/context/` + `all-context.md` routing, RIPER-5 task folders, `results.tsv`, closeout packets, `completed/` archival. Promote the existing, unreferenced `process/MASTER-PLAN.md` to the ONE task board and registry.
- Add only five small things: `north-star.md`, `current-state.md`, `decisions.md`, `process/archive/index.md`, worker envelope + report templates.
- Master Planner never marks a task `accepted` on a worker's word: acceptance needs independent evidence (CI, a spawned vc-tester, or the user) recorded in the registry. Under the user's standing authorization (section 4, "no exceptions", including high-risk classes) a worker may self-merge and self-archive only when every mechanical safety condition holds and it is sure; a worker that is unsure, or whose conditions cannot be verified from the cloud container or CI, stops at `review`.
- Four archive operations stay separate: archive docs, mark logically complete, archive a session (allowed only after the handover report is durable and merge verified), delete branch/worktree (never automatic; needs the registry marking `accepted` plus recorded user consent, not yet granted).
- All 8 questions are resolved (Q4: salvage exciting-meitner selectively; Q8: ref-only fetch done, measured results in section 7). One new HIGH-PRIORITY item surfaced: branch `pensive-dijkstra` holds an unmerged, newer MASTER-PLAN (rev 6 vs main's rev 3a); Gate 2 must start from it. Nothing in Gate 2+ runs before VALIDATE.

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

Sources used (not re-audited): Gate 0 audit conclusions; session inventory; remote branch list; `process/MASTER-PLAN.md` (read in full this session, last verified 2026-09-28, stale); realignment SPEC (AC-19, AC-20 moved into this plan). Sandbox note: `git branch -a` here shows only `main` and one working branch; the remote-branch picture is now MEASURED by a ref-only fetch (02-10-26, user-approved; results in section 7), not re-verified by this container's `git branch -a`.

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
| T11 | lying plan status strips | approved (salvage via R13) | fix lives on unmerged `claude/exciting-meitner-hy50kn` (7 ahead of main, measured 02-10-26); salvage selectively |
| T12 | equity provider decision | proposed -> superseded in part | LSE verdict ADOPT-WITH-LIMITS on unmerged exciting-meitner (salvage via R13); realignment SPEC adopts LSE private-use equities page (queued as P6) |
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
| T23 | reconcile branches | in_progress | ref-only fetch DONE 02-10-26; raw and content-level results in section 7; per-file review still required before any deletion |
| T24 | one status board | superseded by R2/R6 | decided here: MASTER-PLAN is the one board |
| T25 | delete stale branches | proposed | deletion needs per-branch user approval; only `compassionate-goldberg` is a safe-to-delete candidate (0 files differ from main) |
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
| R12 | Deploy fixes (Q3 resolved 02-10-26): stop the old web process (kill-by-port) before build; stale-build guard in `start-web`; post-start smoke check. Own task, high-risk class (deploy/runtime/proxy). Eligible for self-merge under the standing authorization ("no exceptions") only if every mechanical condition holds; the PowerShell/Task Scheduler/Tailscale runtime behaviour cannot be verified from the cloud container, so a worker cannot truthfully be sure and in practice stops at `review` (see section 4, verifiability consequence) | proposed (decision to build recorded; becomes `approved` on confirmation of its task brief) | 5 |
| R13 | Salvage `claude/exciting-meitner-hy50kn` selectively (Q4 resolved 02-10-26): bring over the LSE verdict (ADOPT-WITH-LIMITS) and the plan status-strip fixes; DROP its duplicate status board section in `all-context.md`; branch not deleted | proposed | 2 |
| R14 | HIGH PRIORITY: reconcile `pensive-dijkstra`'s `process/MASTER-PLAN.md` revision 6 (CI wired, uvicorn fix; 5 ahead / 3 behind main, main has rev 3a) into the registry rebuild. Gate 2 (R5) must start from rev 6, not main's rev 3a | proposed | 2 |

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

`accepted` requires ALL of: (a) report has all 11 fields; (b) tests named in the task's test requirement were re-run by a party other than the implementer (spawned vc-tester or the user) and results recorded with command + timestamp; (c) changed-file list matches the task's file ownership; (d) for tasks with user-visible behavior, user acceptance or a recorded agent-probe. A worker saying "done" yields `review` only; the standing authorization lets a worker self-merge only under the mechanical conditions in the Standing authorization subsection (this applies to every task including high-risk classes; there is no class exclusion). Absence of any tier-required evidence keeps the task `review` and is recorded as a gap (vacuous-green ban: known-gap cannot be PASS).

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
3. No exceptions (user decision 02-10-26): the user declined the high-risk exclusion. Workers may self-merge and self-archive ANY task, including high-risk classes (deploy/runtime/proxy, schema/migration, public API contract, auth/identity, billing, secrets/trust boundary), provided ALL mechanical conditions in item 2 hold. Non-negotiable fail-safes the user did not remove: (i) a worker that is unsure stops at `review`; (ii) every item-2 condition must be evidenced (CI green on head, risk-tier tests passed, diff inside declared ownership, no conflicts, completion report committed, registry updated); (iii) the verifiability consequence below; (iv) branch deletion standing consent is NOT granted.
4. The four archive operations stay separate. A session may be archived (`archive_session`) only after its handover report is durable and the merge is verified. Branches are never deleted and worktrees never removed automatically unless the registry marks the task `accepted` AND the user's standing consent for branch deletion is recorded; that consent is NOT granted by this answer.
5. The Master Planner, not the worker, writes the registry and `current-state.md` updates after each merge.
6. Fail-safe: any worker that is unsure stops at `review`.

Tension with the acceptance rule ("never mark accepted because a worker says done") and its resolution: item 2 does not rest on the worker's say-so. Self-merge requires independent evidence (CI on the head commit, or a re-run by a party other than the implementer) plus mechanical diff-ownership and report checks. If any evidence is missing, the task stays `review`. So "worker is sure" is a necessary trigger, never a sufficient one.

#### Verifiability consequence (documented consequence, not a new restriction)

Some tasks change behaviour that cannot be observed from the cloud container or CI: Windows PowerShell deploy scripts (`deploy/*.ps1`), Windows Task Scheduler registration, Tailscale reachability, the live home PC. For such tasks:

| Condition | Verifiable from cloud/CI? | How |
|---|---|---|
| Shape/parse of scripts and configs | Yes | existing shape tests (e.g. `api/tests/deploy/test_deploy_config_shape.py`), PowerShell parse check where tooling exists, `.github/workflows/ci.yml` green on head |
| Diff inside declared ownership, no conflicts, report committed, registry updated | Yes | git and registry checks |
| Script runtime behaviour on Windows (kill-by-port, stale-build guard, smoke check), Task Scheduler, Tailscale, live-PC serving | NO | only the user's PC can show this |

Consequence: an unverifiable runtime condition means the worker cannot truthfully be "sure", so under fail-safe (i) it stops at `review` and the user runs the PC verification. This follows from the standing authorization's own "if it's sure" wording; it adds no restriction beyond it. If a deploy task's runtime behaviour were proven by CI or a shape test alone, self-merge remains allowed.

#### Risk accepted by user

| Item | Detail |
|---|---|
| Decision | User chose "no exceptions" on 02-10-26: high-risk classes may self-merge when all mechanical conditions hold |
| What can go wrong | An auto-merged deploy, migration, API, auth, billing or secrets change passes shape tests and CI but breaks the live PC or data (for example a deploy script that parses but misbehaves on Windows) |
| Mitigations | Post-start smoke check (R12); documented revert-commit procedure (`git revert <merge sha>`, recorded in the report and registry row); max 3 concurrent workers; evidenced mechanical conditions; fail-safe (i) unsure means `review`; verifiability consequence above; no branch deletion consent |
| Residual | Cloud cannot observe the live PC; a bad merge can reach `main` before the user notices. Accepted by the user |

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
| H3 | Remote branches (kind-tesla, compassionate-goldberg, narrative-v2, p1-pipeline, p2-deploy, ui-shell, vigilant-hamilton, fix/narrative-sufficiency-gating-rfc1, inspiring-pasteur, pensive-dijkstra) | MEASURED 02-10-26, see the measured table below | deleting an unmerged branch loses work; large all-differ counts are confounded by files archived/moved on main | yes, per branch, after a per-file review; only compassionate-goldberg is a safe-to-delete candidate |
| H4 | split-all-context (2 ahead / 38 behind; 35 of 35 files differ) | holds the context-changelog split commit bf65024 (unique `context-changelog.md`) | losing it before salvage | salvage first, delete never without approval |
| H5 | exciting-meitner (7 ahead / 87 behind) | 7 unique commits of LSE-verification work (script fixes, EVL logs, ADOPT-WITH-LIMITS verdict, status board) | do not delete; Q4 resolved: salvage selectively as R13 (LSE verdict + status-strip fixes; drop duplicate status board section in `all-context.md`) | branch deletion: yes |
| H6 | Dead `cache.write_confirmed_boundaries/read_confirmed_boundaries` | MASTER-PLAN says zero callers | static search misses dynamic use and scripts | needs grep over `api/scripts` + tests, plus run full pytest; user approval |
| H7 | Stale entries in `process/general-plans/active/` (e.g. momentum-screener_17-09-26 with verified sub-plans) | MASTER-PLAN T19 | archiving moves history; reversible via git | yes, via archive index |
| H8 | No root README | Gate 0 | none | no (additive) |
| H9 | AGENTS.md vs CLAUDE.md drift | sizes differ 37.9 vs 28.9 KB; drift unmeasured | silent divergence | measure in Gate 3 |
| H10 | Scout-block hook blocks commands containing `.next`/`node_modules`/`.venv` | Gate 0 | may hinder build/clean steps in Gate 5 | document, no change without approval |

---

### Measured branch state (Q8 resolved 02-10-26: ref-only fetch approved and done)

Method: `git fetch` (refs only; no merge, no deletion), then per-branch comparison against `origin/main` (main is at the 40e66e9-era plus session-branch commits; session branch `claude/pensive-albattani-ou0cgv` is 6 ahead / 0 behind). Raw ahead/behind counts commits not reachable from main; squash-merged PRs inflate "ahead". Content-level check = files each branch changed since its merge-base that still differ from main.

| Branch | Ahead / behind (raw) | Files still differing from main | Reading |
|---|---|---|---|
| compassionate-goldberg | 0 / 90 | 0 of 0 | fully on main; safe-to-delete candidate (still needs user approval) |
| exciting-meitner | 7 / 87 | 16 of 16 | LSE-verification work; salvage target (R13) |
| inspiring-pasteur (PR #5, open draft) | 2 / 38 | 36 of 36 | needs per-file review |
| kind-tesla | 1 / 38 | 34 of 34 | needs per-file review |
| narrative-v2 | 3 / 42 | 18 of 18 | needs per-file review |
| p1-pipeline | 16 / 15 | 2 of 39 (`.gitignore`, `all-context.md`) | likely main's later edits; unverified per file |
| p2-deploy | 9 / 15 | 2 of 20 (`api/tests/deploy/test_deploy_config_shape.py`, `deploy/start-api.ps1`) | likely main's later edits; unverified per file |
| pensive-dijkstra | 5 / 3 | 1 of 1 (`process/MASTER-PLAN.md`) | holds MASTER-PLAN revision 6 (6 later revisions on branch); HIGH PRIORITY reconcile (R14) |
| split-all-context | 2 / 38 | 35 of 35 | holds context-changelog split commit bf65024; salvage before any deletion |
| ui-shell | 12 / 18 | 2 of 77 (`.gitignore`, `web/tsconfig.tsbuildinfo`) | likely main's later edits; unverified per file |
| vigilant-hamilton | 5 / 22 | 3 of 7 (`pytrends_adapter.py`, `test_pytrends_adapter.py`, `all-context.md`) | likely main's later edits; unverified per file |
| fix/narrative-sufficiency-gating-rfc1 | 11 / 21 | 9 of 51 | needs per-file review |

Caveats (must travel with these numbers): (1) "still differ" means the file differs from main's CURRENT content, which includes edits made on main after the PR merged, so small counts (p1, p2, ui-shell, vigilant) are most likely main's later edits, NOT unmerged work, but this is unverified per file. (2) Large all-differ counts (kind-tesla, inspiring-pasteur, narrative-v2, split-all-context, exciting-meitner) are confounded by files archived or moved on main and need a per-file review before any deletion. (3) pensive-dijkstra's MASTER-PLAN revision 6 (CI wired, uvicorn fix) is NEWER than main's rev 3a and unmerged: Gate 2 must start from rev 6 (task R14). (4) No branch is deleted by this plan without user approval.

## 8. Performance and Deploy Path

Performance: no baselines exist. Rule: no optimization task is approved without a recorded baseline (command, input size, timestamp). Existing measured figures to adopt as starting points, labelled by source: `compute_pairs.py` ~56 s for 153 pairs; `/api/pairs` read p95 135-232 ms; island entry chunk 185 kB gzipped. Unmeasured: screener refresh time at 30 coins, page load, build time, test suite wall time.

Windows deployment path (from `deploy/` and the 2026-10-01 incident):

`source (git pull on PC) -> test (pytest/vitest/tsc as tier requires) -> build (pnpm build:islands then next build, i.e. pnpm build) -> deploy (restart API and web tasks) -> smoke`

Rebuild requirement: any `web/` change needs `build-web.ps1` (or `pnpm build`) before restart; pulling source alone does not update the served app. Known issue: on 2026-10-01 the live PC served a stale build because `Stop-ScheduledTask` did not kill the node process. Gaps: no auto rebuild after pull, no stale-build guard, no deployed smoke test. This plan only documents the path and proposes the fixes (guard comparing build id/commit to HEAD, kill-by-port in the restart script, a one-request smoke check); Q3 resolved 02-10-26: the fixes will be built as task R12 (own task, Gate 5, high-risk deploy class). Under the "no exceptions" authorization R12 may self-merge only if all mechanical conditions hold; Windows runtime behaviour is not verifiable from cloud/CI, so the worker cannot be sure and stops at `review` (section 4, verifiability consequence). The deploy script itself never runs unattended from the cloud.

---

## 9. Gate Roadmap

| Gate | Deliverable | Verification | Needs explicit user approval |
|---|---|---|---|
| 0 | audit (done) | n/a | done |
| 1 | this proposal | user review | approve/modify plan, answer Q1-Q8 |
| 2 | R1-R5: current-state.md (re-verified), north-star.md, decisions.md, context-changelog.md, slimmed all-context.md, master-planner.md, MASTER-PLAN registry, archive index skeleton | VALIDATE first; `wc -l all-context.md` <= 300; `validate-context-discovery.mjs`; `vc-audit-context`; check every moved changelog line exists in F4 (line-count + diff); grep no remaining "confidence over direction"/"public later" in entry points | VALIDATE contract; no source edits; ref-only fetch for branch facts requires approval |
| 3 | R6, R7: CLAUDE.md/AGENTS.md rewrite, protocol router update, byte baselines, sampled session token baseline | `wc -c` before/after table; `validate-agent-parity.mjs --strict`, `validate-protocol-wiring.mjs`, `validate-guide-sync.mjs`; a fresh session must reach a task brief reading only the entry set | CLAUDE.md/AGENTS.md edits (high-visibility, user review before commit) |
| 4 | R8: test policy in all-tests.md, re-measured test counts | run the three suites once (measured, timestamped) | none beyond Gate approval; installs need approval |
| 5 | R9-R14: housekeeping (approved items), README, deploy-path doc/guard proposal, session triage + archive index; R13 exciting-meitner salvage and R14 MASTER-PLAN rev 6 reconcile (these two run in Gate 2 ahead of R5) | per-item evidence re-check; validators; no deletion without per-item approval; R12 verified on the user's PC (hybrid) | branch deletion, `archive_session`, `.agents/skills` replacement, tsbuildinfo untrack, deploy-script changes, any installs |
| 6 | Master Planner pilot: dispatch ONE low-risk task (e.g. P7 guard test or R-level docs task) through the registry end-to-end; then start approved product tasks | pilot task reaches `accepted` through the rule in section 4; report has 11 fields | each product task `approved` by user; spawning workers for `approved` tasks is covered by the standing authorization (section 4, max 3 concurrent); high-risk tasks are covered too ("no exceptions"), but self-merge needs every mechanical condition and the worker being sure; unverifiable runtime conditions mean `review` |

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
| Self-merge ships a bad change (RISK ACCEPTED BY USER, 02-10-26, "no exceptions", includes high-risk classes) | med | all six mechanical conditions required and evidenced; independent CI/re-run evidence; unsure means `review`; unverifiable runtime conditions mean `review`; smoke check; revert-commit procedure; 3-worker cap; no branch deletion consent |
| Auto-merged deploy change breaks the live PC (RISK ACCEPTED BY USER) | low-med | R12 smoke check; revert procedure (`git revert <merge sha>`); shape tests + ci.yml; cloud cannot observe the PC so worker stops at `review` for runtime behaviour |
| Newer MASTER-PLAN rev 6 on `pensive-dijkstra` is overwritten by a rebuild from main's rev 3a | med | R14 high priority; Gate 2 R5 starts from rev 6 |
| Parallel lanes collide on `all-context.md`/`.gitignore` | med | single-owner rule for shared files |
| Token savings overstated | med | bytes measured, tokens approximate, usage unmeasured |

Assumptions: Gate 0 numbers are accurate; MASTER-PLAN facts dated 09-28 may be stale and are labelled; realignment and baskets SPECs are the North Star source; repo policy (commit directly on `main` only on request) applies.

## 13. Open Questions

Resolved 02-10-26 (user answers, authoritative):

1. Q1 RESOLVED 02-10-26: `process/MASTER-PLAN.md` is the single board and task registry (reconciled and wired into session start).
2. Q2 RESOLVED 02-10-26: CLAUDE.md target up to ~20 KB.
3. Q3 RESOLVED 02-10-26: build the 3 deploy fixes (stop old web process before build / kill-by-port, stale-build guard in `start-web`, post-start smoke check) as own task R12 (high-risk deploy class).
4. Q5 RESOLVED 02-10-26: realignment SPEC split into `personal-tracker-realignment_02-10-26` (19 active ACs) and `narrative-baskets_02-10-26` (12 active ACs); docs/process criteria owned here as AC-R3/AC-R4.
5. Q6 RESOLVED 02-10-26: standing authorization recorded verbatim in section 4; the high-risk exclusion was declined by the user ("no exceptions").
6. Q7 RESOLVED 02-10-26: T15 demoted to low priority; licensing is no longer a design constraint (personal use).

Still OPEN:

7. Q4 RESOLVED 02-10-26: salvage `claude/exciting-meitner-hy50kn` selectively (LSE verdict + status-strip fixes; drop the duplicate status board section in `all-context.md`) as registry task R13.
8. Q8 RESOLVED 02-10-26: ref-only fetch approved and done; measured results recorded in section 7 (replacing the earlier UNVERIFIED branch statements).
9. Self-merge guardrail RESOLVED 02-10-26: "No exceptions" (user declined the high-risk exclusion); fail-safes and the verifiability consequence are in section 4. The earlier "flagged for confirmation" item is closed.

Still OPEN: none blocking. Standing consent for branch deletion remains NOT granted (separate, future decision; no deletion by this plan without per-branch approval).

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

Status: CONDITIONAL
Date: 02-10-26
date: 2026-10-02
generated-by: outer-pvl
Scope: this contract gates the START of Gate 2 only (F1-F8, R13, R14). Gates 3-6 each re-enter VALIDATE (plan rule); the Gate 3+ findings below are carried forward as requirements, not as approval.

Parallel strategy: sequential (single validate session; Layer 1 and Layer 2 checks ran inline as read-only commands, no sub-agent spawn tool was available to this session)
Rationale: signal score 2/7 (S6 high-risk class named in plan: deploy/secrets/auth under the self-merge authorization; S7 14 files in blast radius). MEDIUM band would normally recommend parallel read-only subagents; dominant signal is S7. Findings below are evidence-based (validators were read and run read-only; remote refs and repo settings were queried read-only).

Baseline measured 02-10-26 (read-only runs on branch claude/pensive-albattani-ou0cgv, before any Gate 2 write). Every Gate 2/3 validator gate is "no NEW failure vs this baseline", not "exit 0":

| Validator | Baseline failures | Cause |
|---|---|---|
| validate-context-discovery.mjs | 1: `.agents/skills does not resolve to .claude/skills` | `.agents/skills` is 339 tracked regular files (mode 100644), not a symlink |
| validate-skills.mjs | 1: same message | same cause |
| validate-guide-sync.mjs | 1: `README.md does not exist` | no root README (F13 is Gate 5) |
| validate-agent-parity.mjs --strict | 18 (all "normalized body differs" / "descriptions differ") | pre-existing Claude/Codex agent drift; non-strict run = 0 failures, 18 warnings |
| validate-protocol-wiring.mjs, validate-kit-portability.mjs, validate-agent-frontmatter.mjs, validate-skill-invocation-wiring.mjs, validate-protocol-discovery.mjs, validate-all-context.mjs, `discover-context.mjs --check-routing`, `git diff --check`, validate-plan-artifact.mjs (this plan) | 0 | clean |

Test gates (C3 5-column table; Gate 2 start scope; Gate 3+ rows are carried forward):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-R2 | all-context.md reduced to the line cap | Fully-Automated | `test "$(wc -l < process/context/all-context.md)" -le 300` | B (plan must add the disposition table, Gap 2, to make the cap reachable) |
| AC-R2 | changelog block preserved whole in context-changelog.md | Fully-Automated | pinned `comm -23` of sorted changelog block (base all-context.md lines 33-568) vs sorted context-changelog.md = empty (exact command to be written by Gap 2) | B |
| AC-R4 | context docs indexed and routing intact, no new failures | Fully-Automated | `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` -> failures exactly equal the 1-item baseline | B (baseline-aware wording, Gap 1) |
| AC-R4 | all-context.md keeps validator-required sections | Fully-Automated | `node .claude/skills/vc-generate-context/scripts/validate-all-context.mjs` -> 0 failures; `node .claude/skills/vc-context-discovery/scripts/discover-context.mjs --check-routing` -> in sync | B (not in plan today, Gap 2) |
| AC-R4 | master-planner.md wired and discoverable in the same gate it is created | Fully-Automated | `node .claude/skills/vc-audit-vc/scripts/validate-protocol-wiring.mjs` and `node .claude/skills/vc-audit-context/scripts/validate-protocol-discovery.mjs` -> 0 failures | B (F11 moves to Gate 2, Gap 5) |
| AC-R3/AC-R4 | no non-portable concrete context path in protocols or entry files | Fully-Automated | `node .claude/skills/vc-audit-vc/scripts/validate-kit-portability.mjs` -> 0 failures | B (Gap 4) |
| AC-R4 | agent parity not worsened | Fully-Automated | `node .claude/skills/vc-audit-vc/scripts/validate-agent-parity.mjs` (non-strict) -> 0 failures | B (plan says --strict, Gap 1) |
| AC-R3 | retired wording gone from entry points | Fully-Automated | `grep -niE "confidence over direction\|open it to other users\|redistribution-safe\|redistribution is a first-class" CLAUDE.md AGENTS.md process/context/all-context.md process/context/north-star.md` -> no matches | B (pattern set, Gap 13) |
| AC-R1 | default load no longer imports big files | Fully-Automated | `grep -nE '(^\|[ (])@[A-Za-z./_-]+\.md' CLAUDE.md` -> no matches; `wc -c` entry-set table at or under the numeric cap (Gate 3) | B (Gap 3, Gap 13) |
| AC-R8 | product code untouched | Fully-Automated | `git diff --stat <gate-base-sha>..HEAD` lists only `process/`, `CLAUDE.md`, `AGENTS.md` | B (base SHA pinned, Gap 13) |
| all | whitespace and conflict markers | Fully-Automated | `git diff --check` -> exit 0 | A |
| AC-R4/AC-R7 | plan structure valid | Fully-Automated | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <this plan>` -> 0 failures, 0 warnings (verified 02-10-26) | A |
| AC-R4 (Gate 3) | README/guide sync | Fully-Automated | `node .claude/skills/vc-audit-vc/scripts/validate-guide-sync.mjs` -> baseline-aware; cannot pass until a README with an Agents table and a Skills section exists | C (decision Gap 1, Gate 3 or 5) |
| AC-R5 | registry reconciled against evidence | Hybrid | user review of registry vs plan section 3 + `git log`/file-existence re-checks of UNVERIFIED rows; precondition: rev 6 base loaded | B (T26-T28 rows, Gap 7) |
| AC-R6 | nothing removed without approval | Hybrid | approvals log vs `git`/session state diff; precondition: an approvals-log location exists | B (Gap 13) |
| AC-R9 | token claims labelled measured/unmeasured | Hybrid | user review of Gate 3 report | A |
| AC-R1 | fresh session reaches a task brief on the entry set only | Agent-Probe | fresh session reads only entry set and states task brief | A (Gate 3) |
| AC-R7 | acceptance rule not satisfied by worker say-so | Agent-Probe | Gate 6 pilot report + registry history | C (Gate 6) |

Failing stub:
test("should keep all-context.md at or under the line cap", () => { throw new Error("NOT IMPLEMENTED - TDD stub: all-context.md reduced to the line cap") })
Failing stub:
test("should preserve the changelog block whole in context-changelog.md", () => { throw new Error("NOT IMPLEMENTED - TDD stub: changelog block preserved whole") })
Failing stub:
test("should show no new validate-context-discovery failures versus baseline", () => { throw new Error("NOT IMPLEMENTED - TDD stub: no new validate-context-discovery failures") })
Failing stub:
test("should pass validate-all-context and routing check after slimming", () => { throw new Error("NOT IMPLEMENTED - TDD stub: validate-all-context and check-routing clean") })
Failing stub:
test("should wire master-planner.md into the protocol router with discovery frontmatter", () => { throw new Error("NOT IMPLEMENTED - TDD stub: protocol wiring and discovery clean") })
Failing stub:
test("should pass validate-kit-portability with new entry-set references", () => { throw new Error("NOT IMPLEMENTED - TDD stub: kit portability clean") })
Failing stub:
test("should have no retired wording in entry points", () => { throw new Error("NOT IMPLEMENTED - TDD stub: retired wording absent") })
Failing stub:
test("should have no @-imports of large files in CLAUDE.md", () => { throw new Error("NOT IMPLEMENTED - TDD stub: no @-imports of large files") })
Failing stub:
test("should limit Gates 2-4 diff to process/ CLAUDE.md AGENTS.md", () => { throw new Error("NOT IMPLEMENTED - TDD stub: diff scope limited") })

C-4 reconciliation: the `strategy` column carries only Fully-Automated / Hybrid / Agent-Probe. Known-Gap is never a strategy; it appears only as the named residuals below (gap-resolution D).

Legacy line form:
- all-context slimming: [Fully-automated: wc -l, validate-all-context, validate-context-discovery (baseline-aware), --check-routing]
- protocol docs: [Fully-automated: validate-protocol-wiring, validate-protocol-discovery, validate-kit-portability]
- entry files (Gate 3): [Fully-automated: @-import grep, wc -c table, retired-wording grep] | [agent-probe: fresh-session probe]
- registry/archive: [hybrid: user review + git log/file-existence re-checks]
- master planner lifecycle (Gate 6): [agent-probe: pilot task]
- worker self-merge conditions: [known-gap: platform enforcement unavailable, documented below, gap-resolution D]

Dimension findings:
- Infra fit: CONCERN - all cited paths exist or are creatable (verified: MASTER-PLAN rev 6 on origin/claude/pensive-dijkstra-ko69oi = 751 lines with Revision 4/5/6 sections; bf65024 exists; ci.yml, deploy/, api/tests/deploy exist; process/archive and README.md are creatable), but: validators carry baseline failures (table above); `@`-imports at CLAUDE.md lines 20, 36, 48 are the real mechanism of the ~200 KB load and the plan never names them; validate-kit-portability blocks backticked `process/context/<new file>` refs in CLAUDE.md, AGENTS.md and protocols; F11 sits one gate after F7; F14's `.gitignore` line already exists.
- Test coverage: CONCERN - every AC has a command, but 4 gate commands are wrong as written (`--strict` parity = 18 baseline failures; guide-sync cannot pass before a README with Agents/Skills sections exists; context-discovery/skills fail on baseline), validate-all-context and --check-routing are missing from Gate 2, AC-R2 preservation and AC-R6 approvals-log have no concrete command or artifact, AC-R1/AC-R3 thresholds are vague.
- Breaking changes: CONCERN - slimming CLAUDE.md 28.9 KB -> 20 KB and AGENTS.md 37.9 KB -> 20 KB can drop hard rules other docs rely on (no-inline-execution, PVL/EVL gates, commit-on-main, model policy) with no section-by-section disposition; validators that grep these files: validate-context-discovery (both must contain `process/context/all-context.md`, stale-pattern scan, concrete-ref existence), validate-kit-portability (both scanned), validate-agent-parity (only normalizes the names). No hook greps CLAUDE.md content (hooks only count it). all-context.md must keep `## Repository Structure`, `## Technology Stack`, `## Context Group Lifecycle`, `Last updated: YYYY-MM-DD` and the GENERATED:routing block, or validate-all-context / validate-context-discovery FAIL.
- Security surface: CONCERN - the self-merge authorization (accepted by user, not re-litigated) is enforced only by convention: repo is private on a plan where branch protection returns HTTP 403, `allow_auto_merge` is false, `.claude/settings.json` has no permissions block, so CI-green, ownership diff, 3-worker cap, report-committed and archive-after-merge are procedure checks, not platform gates. Fail-safe set has gaps: undefined "independent" re-run, worker-vs-planner registry-write contradiction, no up-to-date-with-main/merge serialization, control-surface self-edit (ci.yml, master-planner.md, validators), no post-merge detective control.
- Section 2 / Gate 2 file set (F1-F8) feasibility: CONCERN - mechanical: all targets creatable/modifiable. Gaps: ordered Gate 2 checklist absent (F4 before F5; R14 -> R13 -> R3; all share all-context.md); F5 <= 300 lines is unreachable without further condensing (measured: changelog block lines 33-568 = 536 lines, 45 KB = 44% of lines / 48% of bytes, not 65%; kept sections 569-966 = about 398 lines before Open Questions 139, References 61, Scan Metadata 56). Highest-risk edit: F5 (loses validator-required sections or routing block). Mitigation: disposition table + run validate-all-context and --check-routing after the edit.
- Section 3 registry / R14 feasibility: CONCERN - rev 6 contains T26, T27, T28; plan reconciles T1-T25 only. Rev 6 (751 lines, 43 KB) -> F6 ~250 lines needs a content-preservation rule. Highest-risk edit: F6 rebuild overwriting rev 6 content from main's rev 3a (plan already mitigates via R14).
- Section 4 lifecycle spec: CONCERN - contradicts CLAUDE.md "commit directly on main / branch only when asked" and "never start EXECUTE without explicit approval" without reconciling; session-start staleness rule (`stamp == git rev-parse HEAD`) is always stale because nightly bot commits advance main daily.
- R13 salvage: CONCERN - 16 files changed on exciting-meitner vs merge-base including `process/context/data-sources/all-data-sources.md` (+67) and two Python files under `lse-data-verification_17-09-26/`; none listed in F1-F14 or Touchpoints. Highest-risk edit: copying all-context.md changes (plan says drop them).
- Section 7 housekeeping H1/H2: CONCERN - H2 `.gitignore` line already present; H1 fix needs exact commands and Windows `core.symlinks` precondition (known gap, unverified).
- Items verified OK: AGENTS.md/Codex parity IS planned (F10) but only by pointer and with no mechanical drift check (Gap 6); 15 agents and 33 skills counts correct; `process/context/all-context.md` string requirement is satisfiable; no hook or validator reads MASTER-PLAN.md, so rebuilding it breaks none; `api/tests/deploy/test_deploy_config_shape.py` and `.github/workflows/ci.yml` exist; plan structure validator passes.

Open gaps:
- real per-session token usage is unmeasured: known-gap: documented, backlog stub due at Gate 2 (gap-resolution D)
- symlinked `.agents/skills` on the user's Windows PC is unverified: known-gap: documented, backlog stub due at Gate 2 (gap-resolution D)
- R12 deploy runtime behaviour (PowerShell, Task Scheduler, Tailscale) verifiable only on the user's PC: known-gap: documented, hybrid user-run (gap-resolution D)
- MCP tool names named by the plan (`create_session`, `archive_session`, `list_events`, `set_session_tags`, `subscribe_pr_activity`, the merge tool) were not verifiable from this session: CONCERN, resolved by Gate 2 R4 step (Gap 8 (vii))
- platform enforcement of self-merge conditions is unavailable on this repo plan: documented residual, compensating controls requested (Gap 8)

What this coverage does NOT prove:
- wc -l / validate-all-context / validate-context-discovery: not that the slimmed all-context.md still contains every current-truth fact needed by agents (only structure, routing and line count), and not that nothing was lost from the kept sections (only the changelog block is covered by the preservation check)
- validate-protocol-wiring / validate-protocol-discovery / validate-kit-portability: not that master-planner.md content is correct or that its rules are mechanically enforceable
- baseline-aware validator gates: not that the 18 agent-parity warnings or the `.agents/skills` failure are harmless; they only prove no regression
- @-import grep and wc -c: not that a fresh Claude session actually follows the new entry set (only the agent-probe shows that, at Gate 3) and not real token usage
- retired-wording grep: not that the North Star content is correct, only that old phrasing is absent from named files
- git diff --stat scope check: not that the contents of process/ files are accurate
- registry hybrid review: not that every UNVERIFIED T-row is true; only rows re-checked are evidenced
- none of the gates proves that a worker honours the standing-authorization conditions; they are procedure, not platform controls, until a pilot (Gate 6) and a post-merge audit are in place

SUPPLEMENT REQUEST (exact items; section ids are slugs of `##`/`###` headings in this plan):
- Gap 1: Section 9-gate-roadmap + 10-acceptance-criteria-this-program | Concern: validator gates are not achievable as written (`validate-agent-parity --strict` has 18 baseline failures; `validate-guide-sync` fails because README.md is absent and F13's 60-line runbook README cannot satisfy its Agents-table/Skills-section checks; validate-context-discovery and validate-skills fail on the `.agents/skills` realpath check until H1) | Severity: CONCERN | Suggested addition: record the baseline table above in the plan, change every validator gate to "no new failure vs baseline", use non-strict parity, and decide README scope (satisfy guide-sync at Gate 3, or accept the baseline failure until Gate 5)
- Gap 2: Section 2-exact-file-set (F4, F5) + 10-acceptance-criteria-this-program (AC-R2) | Concern: <=300 lines unreachable without a disposition table; required headings and routing block unnamed; F4 content undefined; preservation check has no command | Severity: CONCERN | Suggested addition: add an F5 section-by-section disposition table with line budgets; list required headings (`# ` title, `## Repository Structure`, `## Technology Stack`, `## Context Group Lifecycle`, `Last updated: YYYY-MM-DD`, GENERATED:routing block intact, each new root doc named by basename); define F4 = changelog block (+ Open Questions/References/Scan Metadata if moved) and pin the `comm -23` command; add validate-all-context.mjs and discover-context.mjs --check-routing to Gate 2 verification
- Gap 3: Section 2-exact-file-set (F9, F10) + 5-token-efficiency-plan | Concern: the default load is driven by three `@`-imports in CLAUDE.md (lines 20, 36, 48: all-context.md, all-development-protocols.md, orchestration.md); no CLAUDE.md section disposition; TL;DR "~25 KB" contradicts the table (43-48 KB with a 20 KB CLAUDE.md) | Severity: CONCERN | Suggested addition: F9 must remove those @-imports (AGENTS.md has none); add a CLAUDE.md/AGENTS.md section disposition table keeping or relocating-with-pointer each hard rule; correct the TL;DR arithmetic
- Gap 4: Section 2-exact-file-set (F7, F9, F10) + public-contracts | Concern: validate-kit-portability fails on backticked `process/context/<file>` refs in CLAUDE.md, AGENTS.md and process/development-protocols/*.md other than all-context.md, tests/all-tests.md, generated-skills-catalog.json | Severity: CONCERN | Suggested addition: reference north-star.md, current-state.md, decisions.md, context-changelog.md via markdown links or bare names (no backticked `process/context/` prefix), or add an explicit approved scope item to widen the validator allowlist; add validate-kit-portability to Gate 2 and Gate 3 verification
- Gap 5: Section 2-exact-file-set (F11) + 9-gate-roadmap | Concern: validate-protocol-wiring requires all-development-protocols.md to list master-planner.md by basename and validate-protocol-discovery requires protocol frontmatter; F11 is Gate 3 but F7 is Gate 2 | Severity: CONCERN | Suggested addition: move F11 into Gate 2 and specify F7 frontmatter (`name: protocol:master-planner`, metadata node_type/type/read_order/required/read_when, date)
- Gap 6: Section 2-exact-file-set (F10) + 12-risk-predictions | Concern: no mechanical CLAUDE.md vs AGENTS.md drift check (validate-agent-parity compares .claude/agents vs .codex/agents only); AGENTS.md is structurally different (704 vs 440 lines) and falsely says `.agents/skills` is a symlink | Severity: CONCERN | Suggested addition: define a shared delimited entry-set block present byte-identically in both files plus a diff command as the drift check; fix or qualify the symlink statement
- Gap 7: Section 3-task-registry-schema-and-initial-population | Concern: T26, T27, T28 (present in rev 6) missing; F6 ~250 lines vs rev 6 751 lines with no preservation rule | Severity: CONCERN | Suggested addition: add T26 (open finding), T27 and T28 (fixed by P1, status review) rows; state that superseded revision text is moved to the archive index/changelog, not dropped
- Gap 8: Section 4-master-planner-lifecycle-spec (Standing authorization) | Concern: enforceability and fail-safe completeness: (i) add an enforcement table (platform-enforced vs convention: repo is private, branch protection HTTP 403, auto-merge off, no permissions block); (ii) resolve item 2(f) vs item 5 registry-write contradiction; (iii) define "independent" re-run and CI check names/conclusions (`api - pytest`, `web - vitest, tsc, island build`, pending = not green); (iv) add up-to-date-with-main plus serialized merges; (v) address control-surface self-edit (ci.yml, master-planner.md, validators) as forbidden-for-self-merge or an explicit user-accepted residual, plus a post-merge detective control (planner checks main CI on the merge SHA, proposes revert on red); (vi) state that a denied/prompting merge or archive call means stop at `review`; (vii) add a Gate 2 R4 step to verify MCP tool names against the live tool list | Severity: CONCERN | Suggested addition: the above as one subsection "Enforcement and compensating controls" in section 4
- Gap 9: Section 4-master-planner-lifecycle-spec | Concern: worker model conflicts with CLAUDE.md "commit directly on main; branch only when asked" and "never start EXECUTE without explicit approval"; no worker lane (quick/fast/full) or per-task VALIDATE rule | Severity: CONCERN | Suggested addition: in master-planner.md state that `approved` = standing EXECUTE consent for that task, name the worker lane rule and require the worker's own validate-contract before EXECUTE, and add the worker-branch exception to the commit-policy statement
- Gap 10: Section 4-master-planner-lifecycle-spec (Session start/end) | Concern: staleness rule `stamp == git rev-parse HEAD` is always true-stale (nightly bot commits to main, and the commit that adds current-state.md) | Severity: CONCERN | Suggested addition: define staleness as stamp commit not an ancestor of HEAD, or non-chore commits since stamp (`git log <stamp>..HEAD --oneline -- . ':(exclude)api/data/cache'`) above a stated threshold
- Gap 11: Section 2-exact-file-set (R13, F14) + touchpoints | Concern: R13 file set (16 files incl. all-data-sources.md and 2 .py files under process/) not enumerated or ordered against R14/R3; F14 `.gitignore` line already present | Severity: CONCERN | Suggested addition: list R13 files taken vs dropped, add the Gate 2 order (R14 -> R13 -> F4 -> F5 ...), change F14 to `git rm --cached` only
- Gap 12: Section 7-housekeeping-candidates-no-deletion-on-static-search-alone (H1) | Concern: no exact fix commands; 339 tracked regular files; Windows symlink precondition | Severity: CONCERN | Suggested addition: add the exact git commands (remove tracked copy, add mode-120000 symlink) and the `core.symlinks` precondition; keep gated by user approval
- Gap 13: Section 10-acceptance-criteria-this-program (AC-R1, AC-R3, AC-R5, AC-R6, AC-R8) | Concern: vague thresholds and missing artifacts: AC-R1 "~45 KB", AC-R3 grep set lacks redistribution wording, no approvals-log location for AC-R6, AC-R8 diff has no base SHA, no mechanical 11-field report check | Severity: CONCERN | Suggested addition: numeric byte cap, extended grep (case-insensitive) set, approvals-log location (a section of MASTER-PLAN or archive index), `git diff --stat <gate-base-sha>..HEAD`, and a grep that counts the 11 report headings

Gate: CONDITIONAL (0 FAILs, 13 CONCERNs; first-pass, routes to a PVL supplement cycle; not terminal, EXECUTE is not legal yet)
Accepted by: none yet. First-pass CONDITIONAL; no concern has been accepted. Acceptance is recorded after the supplement cycle (or by explicit user acceptance), listing each accepted concern by name.

## Autonomous Goal Block

SESSION GOAL: Master Planner recovery program, Gate 2 (docs/process only): re-verified current-state.md, north-star.md, decisions.md, context-changelog.md, slimmed all-context.md, master-planner.md protocol, MASTER-PLAN.md registry rebuilt from origin/claude/pensive-dijkstra-ko69oi rev 6, archive index skeleton, R13 selective salvage of exciting-meitner.
Charter + umbrella plan: N/A - single plan (process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md)
Autonomy: only what plan section 4 (Standing authorization) records: spawn workers for registry tasks already `approved` (max 3 concurrent, excluding the planner); self-merge/self-archive only when every mechanical condition holds and the worker is sure, otherwise stop at `review`. Branch/worktree deletion consent is NOT granted. Gate 2 may not start until Gate: PASS, or CONDITIONAL after at least one PVL supplement cycle or explicit user acceptance. See feedback_autonomous_phase_execution.md for autonomy removing approval pauses only.
Hard stops / safety constraints:
- Any write outside process/ in Gates 2-4 (CLAUDE.md and AGENTS.md edits are Gate 3 and need user review before commit)
- Deleting any branch, file or session; archive_session before the handover report is durable and the merge is verified
- Installs, product code (api/, web/) edits, deploy script changes, network use beyond approved ref-only fetch
- Starting Gate N+1 before VALIDATE writes a contract for it
- Any validator showing a NEW failure versus the recorded baseline in the Validate Contract
Next phase: PVL supplement cycle (vc-plan-agent applies the SUPPLEMENT REQUEST, then re-spawn vc-validate-agent from V1); after Gate: PASS: EXECUTE Gate 2 via vc-execute-agent (opus), scoped to F1-F8 + R13 + R14
Validate contract: inline in plan (## Validate Contract)
Execute start: wc -l all-context <=300 | validate-context-discovery (failures == baseline) | validate-all-context | discover-context --check-routing | validate-protocol-wiring | validate-protocol-discovery | validate-kit-portability | validate-agent-parity non-strict | git diff --check | retired-wording grep | e2e spec: none | probe: none until Gate 3 | high-risk pack: no (Gate 5 R12 only)

## Resume and Execution Handoff

1. Selected plan: `/home/user/psychic-train/process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md`
2. Last completed step: PLAN supplement 2 (Gate 1 approved; Q4, Q8 resolved; "no exceptions" guardrail recorded; branch measurements recorded; no implementation). Working tree: plan file edits only.
3. Validate-contract: written 02-10-26, Gate: CONDITIONAL (first pass, 0 FAILs, 13 CONCERNs; SUPPLEMENT REQUEST inside the contract). Next: PVL supplement cycle, then re-validate from V1.
4. Context loaded: CLAUDE.md, all-context.md, orchestration.md, MASTER-PLAN.md (full), realignment SPEC (AC grep), repo branch list.
5. Next step: ENTER VALIDATE MODE (all questions resolved); then Gate 2 via vc-execute-agent (opus) scoped to F1-F8 plus R13 and R14; start MASTER-PLAN work from `pensive-dijkstra` rev 6; re-verify every remaining UNVERIFIED registry item first.

## Phase Completion Rules

- A gate is complete only when its Verification Evidence rows are green and recorded with command, timestamp, and commit SHA.
- Status words: `PROPOSED` (this plan), `CODE DONE` (files written, not independently verified), `VERIFIED` (independent re-run, e.g. spawned vc-tester or user). Known-gap alone never yields VERIFIED.
- No gate starts before VALIDATE writes a contract for it and the user approves; archive/delete/session-termination steps need separate explicit approval.
