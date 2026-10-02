---
name: plan:master-planner-recovery
description: "GATE 1 design proposal: recover project truth, collapse memory into one routed system, slim default session load, add Master Planner task registry + worker lifecycle, risk-based test policy, housekeeping and deploy-path findings. Proposal only; no implementation."
date: 02-10-26
feature: general-plans
---

# Project Recovery, Architecture Cleanup, AI Efficiency and Master Planner Orchestration — GATE 1 Proposal

Date: 02-10-26
Status: PROPOSED, Gate 1 approved (all user answers 02-10-26 recorded below; Q1-Q8 resolved). Nothing here is executed. PVL supplement cycle 3 (Gaps 24-30, on top of cycle 2's Gaps 14-23 and the user-approved role-based entry-set refinement) is applied; vc-validate-agent re-runs from V1 next (cycle 4) and must write a passing contract before any Gate 2 write. Working tree: plan file edits only (this file); no other file touched.
Complexity: COMPLEX (single plan, gated roadmap Gate 2..6; each gate re-enters VALIDATE).

## Status of this plan

Gate 1: approved (02-10-26). Q1-Q8 are all resolved (user answers, section 13); Q4 and Q8 are now Resolved. PVL supplement cycle 3 is applied; VALIDATE re-runs from V1 next (cycle 4). No Gate 2 write happens before VALIDATE writes a passing contract. Working tree: only this plan file was edited in this supplement.

## TL;DR

- Today every session loads ~200 KB (~50k tokens) before work starts, driven by three `@`-imports in CLAUDE.md (all-context.md, all-development-protocols.md, orchestration.md). In all-context.md the changelog block is ~44% of lines and ~48% of bytes (536 of 1,223 lines, 45 KB of 93.7 KB); with Open Questions, References and Scan Metadata the non-durable share is higher. Target: TWO role-based entry sets, reached by moving history out of default load, not by deleting it. PLANNER (Master Planner or interactive session) <= 64 KB provisional (typical 50-58 KB, about a 71-74% cut); WORKER <= 36 KB (CLAUDE.md <= 20 KB + task envelope <= 8 KB + task file <= 8 KB; typical ~30 KB, about an 85% cut). The earlier 43-48 KB figure is withdrawn: it budgeted the all-context router at 40 bytes/line, but the kept sections measure 62.5 bytes/line. Tokens are bytes/4, approximate.
- No new doc system. Reuse `process/context/` + `all-context.md` routing, RIPER-5 task folders, `results.tsv`, closeout packets, `completed/` archival. Promote the existing, unreferenced `process/MASTER-PLAN.md` to the ONE task board and registry.
- Add only five small things: `north-star.md`, `current-state.md`, `decisions.md`, `process/archive/index.md`, worker envelope + report templates.
- Master Planner never marks a task `accepted` on a worker's word: acceptance needs independent evidence (CI, a spawned vc-tester, or the user) recorded in the registry. Under the user's standing authorization (section 4, "no exceptions", including high-risk classes) a worker may self-merge and self-archive only when every mechanical safety condition holds and it is sure; a worker that is unsure, or whose conditions cannot be verified from the cloud container or CI, stops at `review`.
- Workers do not inherit the planner's context: every new session loads CLAUDE.md by itself, and today CLAUDE.md says "You are the orchestrator, not the worker" (AGENTS.md line 56 likewise), so a worker would orchestrate with full RIPER-5 ceremony. CLAUDE.md becomes role-neutral; orchestrator rules move to master-planner.md; the worker envelope starts `ROLE: WORKER` and overrides orchestrator wording. Only the Master Planner session has the session and merge tools (verified 02-10-26; vc-* subagents do not).
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
| Worker spawn / monitor | MCP: `create_session`, `send_message`, `list_sessions`, `list_events`, `set_session_tags`, `archive_session`, `subscribe_pr_activity` | REUSE | Cloud session = container + branch = the isolation unit; these tools exist only in the Master Planner (orchestrator) session's tool list (verified 02-10-26), not in vc-* subagents, so only the Master Planner session spawns and archives |
| Agent roles | 15 agents, 33 skills | REUSE; Master Planner is a role of the main session, not a 16th agent | Avoid more always-loaded surface |
| Session role (planner vs worker) | CLAUDE.md "Orchestrator Role" applies to every session | MODIFY: role-neutral CLAUDE.md; orchestrator rules move to master-planner.md; worker envelope states `ROLE: WORKER` | A spawned session loads CLAUDE.md by itself and would otherwise orchestrate; user-approved refinement 02-10-26 |
| Decision memory | scattered ADRs in plan files | NEW `process/context/decisions.md` (index + 1 entry each, links to full ADR) | No single decision log exists |
| North Star | scattered across all-context.md "What This Project Is" | NEW `process/context/north-star.md` | AC-19 |
| Current state | none | NEW `process/context/current-state.md` | Needs timestamped observed facts |
| Worker envelope/report templates | none | NEW `process/development-protocols/master-planner.md` (+ templates section) | One protocol file, not six |
| Test policy | `tests/all-tests.md` | MODIFY (add risk tier table) | Already the test router |

## 2. Exact File Set

| # | Path | Action | Size target | Gate |
|---|---|---|---|---|
| F1 | `process/context/north-star.md` | create | ~100 lines (~4 KB); written in new wording (personal use, data not verdicts, Tailscale-only, page list, non-goals) that avoids every phrase checked by command C8 | 2 |
| F2 | `process/context/current-state.md` | create | ~80 lines (~4 KB), every fact stamped (branch, commit, UTC time, command) | 2 |
| F3 | `process/context/decisions.md` | create | index ~60 lines; fields: decision / date / reason / alternatives / consequences / status active-or-superseded | 2 |
| F4 | `process/context/context-changelog.md` | create (move) | the changelog block (base all-context.md, today lines 33-568, 536 lines / 45 KB; the range is recomputed with `grep -n '^## '` at Gate 2 start, never hard-coded) PLUS the moved Open Questions, References and Scan Metadata sections, whole and unedited, under one `# ` title and a short header; NOT in default load; defined in the F4/F5 subsection below | 2 |
| F5 | `process/context/all-context.md` | modify | <= 300 lines (from 1,223; about 18-19 KB at the measured 62.5 bytes/line; the planner entry set loads only its router section, defined in the entry-set subsection) per the F5 disposition table below; keep routing, architecture, patterns, stack, open decisions; replace history with one-line pointers to F4; required headings and routing block listed below | 2 |
| F6 | `process/MASTER-PLAN.md` | modify | ~250 lines: registry table, lifecycle summary, lane table, reconciled T-list; built FROM rev 6 (R14); all superseded revision text (rev 1-6 narrative, ~500 lines) is moved whole to `process/archive/master-plan-revisions_02-10-26.md` (created in Gate 2, linked from F8) - preservation rule: nothing from rev 6 is dropped, only relocated; checked by command C14 against the pinned rev 6 commit 18ffd4f014f4e5ea0f5d654688875a9300b30ab4 (record `git rev-parse origin/claude/pensive-dijkstra-ko69oi` at Gate 2 start; if the tip has moved, the user decides which revision is the base) | 2 |
| F7 | `process/development-protocols/master-planner.md` | create | ~200 lines: lifecycle, acceptance rule, envelope, report schema, isolation, archival semantics, worker lane + commit-policy rules (section 4); frontmatter exactly: `name: protocol:master-planner`, `description: ...`, `date: 02-10-26`, block-style nested metadata exactly as in autopilot.md: a line `metadata:` followed by five two-space-indented lines `node_type: protocol`, `type: protocol`, `read_order: 10`, `required: false`, `read_when: "Master Planner posture or worker spawn"` (validate-protocol-discovery does NOT parse a flow-style `{...}` map: verified 02-10-26 on a scratch repo, it fails with metadata.required and metadata.read_when missing). The file also holds the Master Planner posture section (the orchestrator rules moved out of CLAUDE.md) and the report template, whose 11 headings are written as `## 1 Task ID` ... `## 11 Context cost` and used nowhere else in the file (command C12 counts them); the worker envelope template inside it starts with the literal line `ROLE: WORKER` (command C14 checks it) | 2 |
| F8 | `process/archive/index.md` | create | table by date/task/status/branch/commit/location; grows by row; ALSO a `## Approvals Log` section (exactly one such heading; one row per approval: date, what, approver quote; Gate 2 writes the row for the R13 move naming `lse-data-verification_17-09-26` with the user's Q4 answer of 02-10-26 as the quote; command C14 checks it) | 2 |
| F9 | `CLAUDE.md` | modify | session-start section rewritten to the short entry set; REMOVE the three `@`-imports (all-context.md line 20, all-development-protocols.md lines 20 and 36, orchestration.md line 48) - AC-R1 fails otherwise; follow the section disposition table below; target <= 20 KB (from 28.9 KB); ROLE-NEUTRAL (the Orchestrator Role section is removed from it; orchestrator rules move to master-planner.md with a short role-selection pointer left behind); contains the shared ENTRY-SET block listing both entry sets; the rewrite MUST keep the literal `process/context/all-context.md` (validate-context-discovery requires it in both CLAUDE.md and AGENTS.md; validate-kit-portability allows it) | 3 |
| F10 | `AGENTS.md` | modify | same entry-set rewrite via the byte-identical ENTRY-SET block (drift check below), <= 20 KB (from 37.9 KB, 704 lines), with the same role-neutral rewrite (the sentence "You are the orchestrator, not the worker" at AGENTS.md line 56 goes); the false statement that `.agents/skills` is a symlink is corrected to: tracked copy until H1 lands; keeps the literal `process/context/all-context.md` as in F9 | 3 |
| F11 | `process/development-protocols/all-development-protocols.md` | modify | add master-planner.md row listed by basename (validate-protocol-wiring); mark orchestration.md as on-demand, not default; moved to Gate 2 with F7 | 2 |
| F12 | `process/context/tests/all-tests.md` | modify | add risk-tier table (section 6) and fix stale counts after measured re-run | 4 |
| F13 | `README.md` (root) | create | ~60 lines: start API/web, runbook pointers | 5 |
| F14 | `web/tsconfig.tsbuildinfo` and `.gitignore` | untrack AND ignore: `git rm --cached web/tsconfig.tsbuildinfo` (file still tracked, 171,544 bytes) PLUS add the line `web/tsconfig.tsbuildinfo` to `.gitignore` (the line is absent today on main, HEAD and ui-shell; `git log -S tsbuildinfo -- .gitignore` is empty, so untracking alone would leave an untracked file that every tsc run recreates). `.gitignore` is a shared file: this lane is its single owner at Gate 5; approval required | 1 line added | 5 |
| F15 | `process/general-plans/backlog/token-usage-telemetry_NOTE_02-10-26.md`, `process/general-plans/backlog/agents-skills-symlink-windows_NOTE_02-10-26.md`, `process/general-plans/backlog/deploy-runtime-user-pc-verification_NOTE_02-10-26.md` | create three backlog stubs, one per known gap named in Verification Evidence: real per-session token usage (unmeasured); behavior of a symlinked `.agents/skills` on the user's Windows PC; R12 deploy runtime behavior verifiable only on the user's PC; each ~10-15 lines (what is unproven, why, how to close it); required by the vacuous-green ban | ~3 x 1 KB | 2 |

Home decision for the registry: inside `process/MASTER-PLAN.md`. Justification: it already exists, already carries T1..T25, lanes and the 3-lane cap, and is the file sessions already cite informally. A sibling file would give two boards. Risk: it is a large file; mitigation: registry holds one row per task (<= 3 lines), details live in each task folder.

Orchestration.md (71 KB) stays unchanged this program; it is moved out of the default load by routing, not by editing. Slimming it is a candidate follow-up task (see registry R-5), unmeasured.

### Session entry sets (the load after Gate 3): TWO role-based sets

Verified facts (02-10-26): every new session and every subagent loads CLAUDE.md automatically, including its `@`-imports; a spawned session does NOT inherit the planner's context. What a worker loads is therefore decided by CLAUDE.md plus its first message, not by the planner. Only the Master Planner session needs the heavy protocol context, so there are two sets (measured by commands C3 and C4 in section 10).

PLANNER entry set (the Master Planner session, and an interactive user session):

| File | Size (bytes) | Why default |
|---|---|---|
| CLAUDE.md (rewritten, role-neutral) | <= 20,000 | harness entry |
| north-star.md | ~4,000 | direction |
| current-state.md | ~4,000 | observed truth |
| MASTER-PLAN.md (registry) | <= 20,000 (rev 6 is 43,484 bytes / 751 lines; F6 targets ~250 lines, about 14-16 KB at the same density; fixed by measurement at Gate 2 close) | task board |
| all-context.md router section | ~5,000-6,000, cap 8,000 | routing; deeper files on demand |
| task brief (task folder PLAN or SPEC) | 3,000-8,000 | the work |

Planner total: <= 64,000 bytes provisional (typical 50-58 KB, about 13-15k tokens, about a 71-74% cut from ~200 KB). On demand, not default: master-planner.md (~10 KB, read in Master Planner posture), orchestration.md (71 KB), context-changelog.md, other protocols.

WORKER entry set (a spawned worker session):

| File | Size (bytes) | Why default |
|---|---|---|
| CLAUDE.md (same role-neutral file) | <= 20,000 | loaded automatically; cannot be avoided |
| task envelope (first message; also saved as `{slug}_REF_{dd-mm-yy}.md` in the task folder) | <= 8,000 | states `ROLE: WORKER`, objective, ownership, tests, report path |
| task PLAN or SPEC named in the envelope | <= 8,000 | the work |

Worker total: <= 36,000 bytes provisional (typical ~30 KB, about 7-9k tokens, about an 85% cut). NOT in the worker default set: north-star.md, current-state.md, MASTER-PLAN.md, the all-context.md router, orchestration.md (the envelope links north-star.md and current-state.md; the worker opens them only if the task needs them, and notes it in report field 11).

Router section definition: from line 1 of all-context.md through the line before the `## Context Group Lifecycle` heading (title, pointer line, project summary, how-this-file-works, entry and group tables, Task Routing Table). The base Quick Start section is merged into How This File Works so the range stays contiguous. Budget 90 lines (the F5 table rows through Task Routing Table: 15+3+10+15+25+22; ~5-6 KB at 62.5 bytes/line; the base equivalent, lines 1-32 plus 569-680, is 144 lines / 7,709 bytes before condensing). Command C3 measures it with `sed`, so the definition is mechanical, not a judgment.

Honest arithmetic: the earlier "43-48 KB" entry-set claim is withdrawn. It budgeted all-context.md at ~12 KB for 300 lines (40 bytes/line), but the kept sections measure 62.5 bytes/line (base lines 569-966 = 398 lines = 24,895 bytes), so a 288-300 line F5 is ~18-19 KB; the planner loads only its ~5-6 KB router section, but the registry now joins the planner set, which is why the planner cap is 64,000. CLAUDE.md remains the largest default file for both roles; trimming it below 20 KB is a Gate 3 measurement, not a promise. The caps above are provisional: at Gate 2 close the measured bytes of F1, F2, the F5 router section and F6 are recorded in the Gate 2 report and the caps are confirmed or tightened; a cap may be raised only with user approval.

Role-neutral CLAUDE.md and AGENTS.md (F9, F10): CLAUDE.md line 50 ("You are the orchestrator, not the worker") and line 59 ("You do NOT") would make a spawned worker orchestrate with full RIPER-5 ceremony, and AGENTS.md has the same at lines 56 and 65. The Orchestrator Role section therefore moves to master-planner.md (Master Planner posture section) and the on-demand orchestration.md. The ENTRY-SET block carries a short Role Selection paragraph instead (specified after the disposition table below).

### Gate 2 order, R13 file list, F4/F5 definition, F9/F10 dispositions

**Gate 2 execution order (all-context.md is shared, so strictly serial):** R14 (rebuild registry base from `origin/claude/pensive-dijkstra-ko69oi` rev 6) -> R13 (salvage, list below) -> F1, F2, F3 (they do not touch all-context.md, and F5's summary is written from north-star.md, so they come first) -> F4 (create changelog from the base all-context.md, `<base>` = HEAD at Gate 2 start) -> F5 (slim all-context.md) -> F7 + F11 (together) -> F6 -> F8 -> F15 (three backlog stubs) -> **R4 step (vii)**, run by the Master Planner (orchestrator) session itself, NOT by the vc-execute-agent subagent (verified 02-10-26: the claude-code-remote tools `create_session`, `archive_session`, `send_message`, `list_sessions`, `list_events`, `set_session_tags`, `subscribe_pr_activity`, `get_session`, `interrupt_session` and `mcp__github__merge_pull_request` / `mcp__github__enable_pr_auto_merge` are in the orchestrator session's tool list; vc-* subagents do not see them): check every tool name this plan relies on against the live tool list, AND verify behaviour, not just names, with one read-only dry-run call such as `list_sessions` (it must return a session list; nothing is spawned, archived or merged). The orchestrator records the result in the Gate 2 report and hands it to the execute agent; any name that does not exist or call that fails is corrected in master-planner.md before the gate closes.

**R13 files** (exciting-meitner changed 16 files vs merge-base; the task brief re-lists them with `git diff --name-status $(git merge-base origin/main origin/claude/exciting-meitner-hy50kn) origin/claude/exciting-meitner-hy50kn` at Gate 2 start): TAKE: the LSE ADOPT-WITH-LIMITS verdict artifact(s), the plan status-strip fixes, `process/context/data-sources/all-data-sources.md` (+67 lines, LSE findings; reviewed hunk by hunk, kept only where it does not contradict main). DROP: the duplicate `## Where We Are` status-board section in all-context.md (T24: one board), EVL logs/status-board scratch. The two Python files under `lse-data-verification_17-09-26/` are process-folder artifacts: TAKE as-is into the same task folder path (they are evidence for the verdict, not product code) or DROP with a recorded reason; they are never edited. Anything not in TAKE or DROP is recorded as `unreviewed` in the registry row, not silently skipped. **R13 destinations (named):** the branch moves `process/general-plans/active/lse-data-verification_17-09-26/` to `process/general-plans/completed/lse-data-verification_17-09-26/` (git shows `VERDICT.md`, `findings.md`, two EVL reports, `results.tsv`, `test_verify_provider.py` and renames of the PVL report, the PLAN and `verify_provider.py` landing in `completed/`, with the five `active/` files deleted). TAKEN artifacts land in `completed/`; the five `active/` copies are removed as part of that move. The move is archive operation A and is logged as one row in the `## Approvals Log` of `process/archive/index.md` (date, what, approver quote = the user's Q4 answer of 02-10-26). Touchpoints therefore also include `process/context/data-sources/all-data-sources.md` and both lse-data-verification folders.

**F4/F5 definition.** F4 holds the base changelog block (today lines 33-568; recomputed at Gate 2 start by command C6, never hard-coded) plus the sections moved out of F5 (Open Questions resolved items, References, Scan Metadata), verbatim. F5 required to survive (validate-context-discovery, validate-all-context): a `# ` title; `Last updated: YYYY-MM-DD`; the literal string `process/context/all-context.md`; `## Repository Structure`; `## Technology Stack`; `## Context Group Lifecycle`; the GENERATED:routing block intact (rebuilt with `--emit-routing` only if a root doc is added; must pass `--check-routing`); every new root doc (north-star.md, current-state.md, decisions.md, context-changelog.md) named by basename in the routing tables, not as a backticked `process/context/<file>` path (see portability rule below).

| F5 section (base) | Disposition | Line budget |
|---|---|---|
| Title, Last updated, intro | keep, rewrite short | 15 |
| Changes Since Last Update (lines 33-568) | MOVE whole to F4; leave one pointer line | 3 |
| What This Project Is | replace with pointer to north-star.md + 3-line summary written from north-star.md (today's line 582 `redistribution-safe` goes with the replaced text) | 10 |
| How This File Works | condense; the base Quick Start section (lines 630-639) is merged into it | 15 |
| Root Entry Points / Context Groups (GENERATED block) | keep intact | 25 |
| Task Routing Table | keep, add rows for new root docs and README runbook | 22 |
| Context Group Lifecycle, Naming, Update Protocol | keep, condense | 25 |
| Repository Structure | keep, drop dated parentheticals | 45 |
| Technology Stack | keep, drop dated parentheticals | 40 |
| Key Patterns | keep, but DROP the `Confidence over direction` paragraph (today line 910; the principle is retired, realignment AC-18 and T10 cancelled) | 25 |
| Environment and Configuration | keep | 20 |
| Open Decisions | keep, trim to current; DROP or reword today's line 957 (the `redistributable` wording in the narrative data-source row), line 955 (the Equity data provider row: remove `collides with the public-later goal` and restate it with the LSE ADOPT-WITH-LIMITS verdict) and the stale Deployment target row (line 959: replace with the resolved home PC plus Tailscale path); DROP lines 962-964 (the `Redistribution is a first-class constraint` paragraph, whole) | 25 |
| Open Questions | MOVE resolved/historical items to F4; keep only still-open ones as one-liners, reworded so none carries a retired phrase (today's line 1020 `redistributable` stays only in F4); current facts go to current-state.md | 15 |
| References, Scan Metadata | MOVE to F4; one pointer line | 3 |
| Total | | 288 (12 lines reserve under the 300 cap) |

**Retired wording is dropped, not kept (AC-R3, command C8).** Of the 11 hits today (lines 95, 373, 446, 581, 582, 910, 955, 957, 962, 964, 1020): lines 95, 373 and 446 sit in the changelog block and 1020 in Open Questions (all move whole to F4, where they are allowed); lines 581 and 582 (the wrapped `open it to / other users later` and `redistribution-safe`) go with the replaced What This Project Is text; lines 910, 955, 957, 962 and 964 are in kept sections and are dropped or reworded per the table above (955 and 964 are the `public-later` / `open up later` wording; 964 sits inside the 962-964 paragraph that is dropped whole). History of those phrases survives only in context-changelog.md (realignment AC-17/AC-18, T10 cancelled). north-star.md is written to avoid the retired phrases (F1 row).

**Changelog-preservation command (pinned, AC-R2): command C6 in the fenced block in section 10.** It recomputes the changelog range and each moved section's range from the base with `grep -n '^## '` (today: changelog 33-568, Open Questions 967-1105, References 1106-1166, Scan Metadata 1167-1223), then runs `comm -23` of the sorted unique base lines against the sorted unique F4 lines; it must print nothing. A dropped line prints exactly that line (negative case verified on a scratch copy). `<base>` is `git rev-parse HEAD` recorded when Gate 2 starts.

**Portability rule (validate-kit-portability).** The validator fails on backticked concrete `process/context/<file>` references outside {all-context.md, tests/all-tests.md, generated-skills-catalog.json} in CLAUDE.md, AGENTS.md and `process/development-protocols/*.md`. Therefore north-star.md, current-state.md, decisions.md and context-changelog.md are referenced in those files by bare name or markdown link only (never a backticked `process/context/` prefix). No allowlist widening is proposed. validate-kit-portability runs at Gates 2 and 3.

**CLAUDE.md / AGENTS.md section disposition (F9/F10).**

| CLAUDE.md section | Disposition |
|---|---|
| Bootstrap Guard, Before Any Substantial Task | keep short; replace the three `@`-imports with plain bare-name pointers to the two entry sets |
| Orchestrator Role (incl. no-inline-execution) | relocate to master-planner.md (Master Planner posture section) and the on-demand orchestration.md; CLAUDE.md keeps the short Role Selection paragraph (below) and ONE role-scoped sentence: a session in orchestrator posture never edits source or runs gate commands itself, while a WORKER executes its own task directly |
| /goal Block, Strategy-Compare, Pre-Spawn Strategy, Autonomous /goal | relocate: one-line pointers to orchestration.md and the vc-agent-strategy-compare skill |
| Model Selection Policy | keep 4 lines (EXECUTE = opus, all else sonnet) + pointer |
| Communication Principles | keep pointer to communication-standards.md |
| Core Protocol, RIPER-5 Phase Table, Phase Transition Rules, PVL/EVL gates | keep (hard rules) |
| Mode Detection, QUICK FIX lane detail | relocate: pointer to orchestration.md (Intent Routing, QUICK FIX Lane); keep trigger line + scope guard sentence |
| Commit branch policy | keep (hard rule), plus the worker-branch exception (section 4) |
| Shared Process Folder, Autopilot, Lanes | relocate: pointers to plan-lifecycle.md and autopilot.md |
| Available Workflow Skills, Mode Agents, Specialist agents, Validator registry | relocate: pointer to discover-skills.mjs, `.claude/agents/`, and the all-context validator registry |
| Key Principles, Quick Start, Hooks/Envelope, Resources | keep Key Principles; relocate the rest by pointer |

**Role Selection paragraph (inside the ENTRY-SET block, about 8 lines, byte-identical in CLAUDE.md and AGENTS.md).** (1) If the session's first message begins with a task envelope whose first line is `ROLE: WORKER`, you are a WORKER: direct lane, do not orchestrate, do not spawn sessions or subagent chains, load only the files the envelope names; the envelope overrides any orchestrator wording elsewhere. (2) Otherwise (a user-opened or Master Planner session) you are in planner posture: read the PLANNER entry set, and read master-planner.md for the orchestrator rules. (3) Hard rules that apply to every role stay in the block: commit policy (with the worker-branch exception), phase locking, approval gates, no secrets.

AGENTS.md gets the same dispositions; its extra sections (704 vs 440 lines) are relocated by pointer, none of its hard rules are dropped. **Drift check (replaces the nonexistent CLAUDE-vs-AGENTS parity validator; validate-agent-parity compares `.claude/agents` with `.codex/agents` only):** both files carry one block delimited by `<!-- ENTRY-SET:BEGIN -->` and `<!-- ENTRY-SET:END -->` holding both entry-set lists (PLANNER and WORKER), the Role Selection paragraph and the hard rules (role-scoped no-inline-execution, commit policy, approval gates); it must be byte-identical. The check is command C10 in section 10: it first asserts exactly one `ENTRY-SET:BEGIN` marker in each file (a bare `diff` of the two extracted blocks exits 0 when both markers are missing, a vacuous pass), then diffs the blocks; run at Gate 3.

---

## 3. Task Registry Schema and Initial Population

### Schema (columns in MASTER-PLAN.md registry table)

`ID | Objective | Prio (H/M/L) | Status | Parent | Deps | Worker/session | Branch/worktree | Scope + acceptance | Test req/budget | Report + commit refs | Blockers/risks | Outcome / archive location`

Status values: `proposed, approved, queued, in_progress, review, accepted, archived` plus `blocked, failed, cancelled, needs_input`. IDs: keep historical `T#` for reconciled items; new work uses `R#` (recovery program) and `P#` (programs and product tasks from SPECs). The priority column is `Prio` with values H / M / L (never P0-P3 or Q1-Q4, which would collide with the P# task IDs and the Q1-Q8 open-question labels). Naming rule: T# always means a registry task (T1, T3 and T4 are real tasks); a test risk tier is written RT0-RT4 (section 6), so no tier label collides with a task ID.

### Initial population (reconciliation of T1..T25 against current reality)

Rule: a status stronger than `review` is written only where independent evidence exists (merged PR, file present). "Evidence" below is from the supplied inputs and MASTER-PLAN; items marked UNVERIFIED must be re-checked in Gate 2 before being written (re-check method: `git log`, file existence, `gh pr view`).

Registry rows are rebuilt from rev 6 (R14), so T26-T28 and any other rev 6 row are carried, not re-derived. F6 preservation rule: superseded revision narrative (rev 1-6, ~500 of rev 6's 751 lines) is relocated whole to `process/archive/master-plan-revisions_02-10-26.md` (indexed in F8), never dropped; the registry keeps one row per task.

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
| T15 | redistribution flags | proposed (Prio L) | Q7 resolved 02-10-26: demoted; licensing is no longer a design constraint (personal use) |
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
| T26 | pytrends 0.0 questions: `layer 2 crypto`/`l2s` reads 0.0 nightly; `pytrends-blended/rwa` wrote 0.0 as `fresh` on a night `pytrends/RWA crypto` read 74.0 (same shape as the T1 bug); confirm RFC-1 sufficiency gating surfaces these as `insufficient` | needs_input (open finding, not fixed) | rev 6 on `origin/claude/pensive-dijkstra-ko69oi` (T26 revised there); verify the exact text against that branch when the row is written in Gate 2 |
| T27 | snapshot cron timing (all five crons moved to 11:17-13:17 UTC, midnight-crossing warning) | review | fixed by P1 (PR #11, merged); rev 6 marks it fixed; real firing unverified until `gh run list` over 2-3 nights; verify against rev 6 text at Gate 2 |
| T28 | non-atomic parquet writes | review | fixed by P1 (`cache.py` temp-then-rename); `etf_flows_adapter.merge_into_cache` still non-atomic (backlog note); verify against rev 6 text at Gate 2 |
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
| R4 | master-planner.md protocol (incl. the Master Planner posture moved out of CLAUDE.md) + templates (worker envelope with the `ROLE: WORKER` line, 11-heading report) | proposed | 2 |
| R5 | Registry rewrite in MASTER-PLAN.md | proposed | 2 |
| R6 | CLAUDE.md / AGENTS.md session-start rewrite, drift check | proposed | 3 |
| R7 | Token baseline measurement | proposed | 3 |
| R8 | Test policy into all-tests.md | proposed | 4 |
| R9 | Housekeeping (approved items only) | proposed | 5 |
| R10 | Deploy path doc + stale-build guard proposal | proposed | 5 |
| R11 | Archive index + session triage | proposed | 5 |
| R12 | Deploy fixes (Q3 resolved 02-10-26): stop the old web process (kill-by-port) before build; stale-build guard in `start-web`; post-start smoke check. Own task, high-risk class (deploy/runtime/proxy). Eligible for self-merge under the standing authorization ("no exceptions") only if every mechanical condition holds; the PowerShell/Task Scheduler/Tailscale runtime behaviour cannot be verified from the cloud container, so a worker cannot truthfully be sure and in practice stops at `review` (see section 4, verifiability consequence) | proposed (decision to build recorded; becomes `approved` on confirmation of its task brief) | 5 |
| R13 | Salvage `claude/exciting-meitner-hy50kn` selectively (Q4 resolved 02-10-26): bring over the LSE verdict (ADOPT-WITH-LIMITS) and the plan status-strip fixes; DROP its duplicate status board section in `all-context.md`; destination `process/general-plans/completed/lse-data-verification_17-09-26/` (moved from `active/`; archive operation A, logged in the approvals log); branch not deleted | proposed | 2 |
| R14 | HIGH PRIORITY: reconcile `pensive-dijkstra`'s `process/MASTER-PLAN.md` revision 6 (CI wired, uvicorn fix; 5 ahead / 3 behind main, main has rev 3a) into the registry rebuild. Gate 2 (R5) must start from rev 6, not main's rev 3a | proposed | 2 |

Queued product tasks (from SPECs; `proposed`, NOT executed, NOT approved):

| ID | Objective | Source | Status |
|---|---|---|---|
| P4 | Realignment (screener + product): delete verdict code, screener RSI/groups/30-coin cap, charts, BTC leg strip, 15-min refresh, lean storage | `process/general-plans/active/personal-tracker-realignment_02-10-26/` (19 active ACs) | proposed |
| P5 | Narrative baskets (user-defined, equal-weight basket view, mindshare share-of-total, /narrative raw-only) | `process/general-plans/active/narrative-baskets_02-10-26/` (12 active ACs) | proposed, deps P4 |
| P6 | LSE equities page with Add button, private-use note | realignment SPEC (personal-tracker-realignment_02-10-26) | proposed, deps P4 |
| P7 | Protect pytrends partial-hour fix + nightly archive (guard tests) | `narrative-baskets_SPEC_02-10-26.md` (Decision 16 and AC-25, in `process/general-plans/active/narrative-baskets_02-10-26/`) | proposed, rides with P4 |

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

`accepted` requires ALL of: (a) report has all 11 fields; (b) tests named in the task's test requirement were re-run by a party other than the implementer (a spawned vc-tester, the user, or CI on the head SHA per Enforcement (iii)) and results recorded with command + timestamp; (c) changed-file list matches the task's file ownership; (d) for tasks with user-visible behavior, user acceptance or a recorded agent-probe. A worker saying "done" yields `review` only; the standing authorization lets a worker self-merge only under the mechanical conditions (a)-(f) in the Standing authorization subsection (this applies to every task including high-risk classes; there is no class exclusion). Absence of any tier-required evidence keeps the task `review` and is recorded as a gap (vacuous-green ban: known-gap cannot be PASS).

**Precedence (merge versus accept):** merge follows the Standing authorization conditions (a)-(f); `accepted` is recorded by the Master Planner only if this acceptance rule (a)-(d) holds; a task that needs user acceptance or an agent-probe (rule (d), and RT4 in section 6) stays `review` after the merge until that evidence exists. If the user instead wants RT4 or other high-risk tasks to bypass user acceptance, that is the user's call and is recorded as an extension of Open Question 10; this plan does not assume it.

### Decomposition rules

One task = one objective, one acceptance statement, <= ~15 files or one blast-radius area, one owning branch. Split when: files cross `api/` and `web/` ownership, a schema/contract change is involved (own task, lands first), or acceptance needs a user decision (separate `needs_input` task). Each task states deps; no task starts with an unmet dep.

### Worker context envelope (what a worker receives; <= 8 KB)

0. First line `ROLE: WORKER`, then: "You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagent chains, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md or elsewhere." 1. Task ID, objective, acceptance statement. 2. Exact files owned and files forbidden. 3. Branch name. 4. Links (not contents) to the task PLAN/SPEC and, only if the task needs them, north-star.md and current-state.md. 5. Test requirement + budget (section 6). 6. Retry budget (default 2 fix cycles). 7. Report destination path and the 11-field schema. 8. Stop conditions (irreversible/outward actions, scope expansion). 9. Autonomy statement. The envelope is also saved in the task folder as `{slug}_REF_{dd-mm-yy}.md` so its size is checkable (command C4). Workers load deeper context on demand via the router, not by default; the registry, north-star.md and current-state.md are not in the worker default set.

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
| Control-surface self-edit (recommended-against, written default follows the user's 'no exceptions') | A worker edits ci.yml, validators, master-planner.md, CLAUDE.md/AGENTS.md or `.claude/` and self-merges past weakened checks. Awaiting the user's explicit accept/decline (Open Questions item 10). Compensating control: post-merge main-CI check with revert proposal |

#### Worker lane, consent and commit-policy rules (written into master-planner.md)

- `approved` on a registry row means standing EXECUTE consent for that task only (this reconciles with the CLAUDE.md rule 'never start EXECUTE without explicit approval'); it does not extend to other tasks.
- Worker lane rule: the envelope names the lane, risk-tiered. A WORKER is a direct-lane session: it does not orchestrate, spawn sessions or run the multi-agent RIPER chain. Tiny tasks (RT0/RT1, <= ~100 lines, no schema/auth/API/billing/migration surface) use the QUICK FIX lane; every other worker writes a compact per-task validate-contract itself (the gate list from the envelope's test requirement, in its own task folder) before editing, then edits and runs its declared gates directly. Independent confirmation of those gates comes from CI or a vc-tester the Master Planner spawns, never from the worker (acceptance rule (b)). The no-inline-execution rule in CLAUDE.md is scoped to a session in orchestrator/Master Planner posture; the envelope's "you are a WORKER" line is the explicit override (user-approved refinement, 02-10-26). The user's confirmation of this lane (direct lane, compact self-written validate-contract; one vc-quick-fix-agent spawn for a tiny task is not a subagent chain) is Open Question 12.
- Commit-policy exception: CLAUDE.md says commit directly on `main` and branch only when asked. Worker sessions are the explicit, user-authorized exception (the user's standing authorization names worker sessions that merge their own branch): workers use `claude/<task-id>-<slug>` branches and PRs; the Master Planner session itself and all direct user work still commit on `main` per policy.

#### Enforcement and compensating controls

(i) What is enforced where. Verified 02-10-26: private repo, branch protection returns HTTP 403, `allow_auto_merge` is false, `.claude/settings.json` has no permissions block.

| Condition | Platform-enforced? | Actual mechanism |
|---|---|---|
| CI green on head | NO | convention: worker/planner reads check results |
| Diff inside declared ownership | NO | convention: `git diff --name-only` vs ownership globs |
| 3-worker cap | NO | convention: planner counts `list_sessions` |
| Report committed, registry updated | NO | convention + AC-R10 grep |
| Archive only after merge | NO | convention |
| (anything) | nothing is platform-enforced | all controls below are procedure; a Known-Gap (D), not a PASS |

(ii) Registry writer: ONE writer, the Master Planner (item 5 wins). Item 2(f) is amended: a worker does not edit the registry; it commits its report with the registry-update request in field 9/10, and the Master Planner records `accepted`/`archived` with commit refs. A worker may only archive its session after the Master Planner (or the report's merge-verified evidence) confirms the registry write; if the planner is unreachable the worker stops at `review`.

(iii) 'Independent' re-run means a party other than the implementing worker session: a spawned vc-tester, the user, or CI. 'CI green' means both ci.yml jobs concluded `success` on the head SHA: `api — pytest` and `web — vitest, tsc, island build` (the separator is an em dash U+2014, exactly as the `name:` values at ci.yml lines 41 and 57). There is no e2e or lint job. Pending, queued, skipped or neutral conclusions count as NOT green; any non-success keeps the task at `review`.

(iv) Up-to-date and serialized merges: the branch must contain the current `origin/main` tip (rebased/merged, CI re-run after) before merging; only one self-merge at a time (the planner holds a merge token in the registry `Worker/session` column); a later worker re-checks after the earlier merge lands.

(v) Control-surface files (`.github/workflows/ci.yml`, master-planner.md, the validators under `.claude/skills/*/scripts/`, CLAUDE.md, AGENTS.md, anything under `.claude/`): a worker could weaken the very checks that gate its merge. RECOMMENDATION (not applied): forbid self-merge for diffs touching these files, stopping at `review`. The user said 'no exceptions'; this plan does NOT narrow that decision. Open Questions item 10 asks for the user's explicit accept/decline. Until the user answers, the written default follows the user's decision, and the residual is recorded as a USER-ACCEPTED risk row (Risk accepted by user table: 'control-surface self-edit'), compensated by a post-merge detective control: after every self-merge the Master Planner checks CI on the merge SHA on main; on red it opens a revert proposal (`git revert <merge sha>`) and halts further self-merges until the user responds.

(vi) A denied or permission-prompting merge or archive tool call means the worker stops at `review` and reports; it never retries around the prompt.

(vii) Tool-name and tool-placement verification. Verified 02-10-26 in the Master Planner (orchestrator) session: `create_session`, `archive_session`, `send_message`, `list_sessions`, `list_events`, `set_session_tags`, `subscribe_pr_activity`, `get_session`, `interrupt_session` (the claude-code-remote server) and `mcp__github__merge_pull_request` / `mcp__github__enable_pr_auto_merge` exist in that session's tool list; vc-* subagents (research, plan, validate) do NOT see them. Consequences: (1) only the Master Planner session spawns and archives sessions (default operating rule; the planner may call `archive_session` for a worker's session once the handover report is durable and the merge is verified, operation C below); (2) `enable_pr_auto_merge` is unusable while the repo's `allow_auto_merge` is false; (3) whether a spawned worker's own tool list contains the merge and archive tools is UNVERIFIED and is checked by the Gate 6 pilot (the pilot worker records the tools it has in report field 11); a worker without a merge tool stops at `review`, and whether the Master Planner may merge on a worker's behalf is not covered by the standing authorization, so it is recorded as an extension of Open Question 10 for the user to decide. Gate 2 step R4 (vii) (section 2) re-checks names AND behaviour (one read-only `list_sessions` dry-run, nothing spawned) from the Master Planner session itself, because a vc-execute-agent subagent cannot call these tools.

### Completion lifecycle and the four separate operations

| Operation | What it means | Tool / supported? | Approval |
|---|---|---|---|
| A. Archive documents | move task folder to `completed/`, add row to `process/archive/index.md` | file move via UPDATE PROCESS | normal task flow, user-visible |
| B. Mark logically complete | registry status `accepted` then `archived` | registry edit | only after acceptance rule |
| C. Terminate/archive a session | `archive_session` MCP | supported | Allowed under the standing authorization only after the handover report is durable and merge verified (item 2/4); otherwise explicit user approval; sessions with unresolved asks are never archived |
| D. Remove branch/worktree | `git push --delete`, `git worktree remove` | not run automatically | Needs registry `accepted` AND recorded user standing consent for deletion (not yet granted); otherwise explicit approval per branch; merged-state check first |

Report wording rule: the planner says "report file written" for A, "registry updated" for B, and states C/D only if the tool call actually returned success. Never claim a session ended because a file was written. Archival never discards active work: an unmerged branch or a session with unresolved asks blocks D/C.

### Session start / end protocols

Start (Master Planner): read the PLANNER entry set (a worker reads only its envelope plus the worker set); run `vc-review-situation`; check staleness: `current-state.md` is stale when its stamped commit is NOT an ancestor of HEAD (`git merge-base --is-ancestor <stamp> HEAD` fails) or when non-chore commits since the stamp exceed 10 (`git log <stamp>..HEAD --oneline -- . ':(exclude)api/data/cache' | wc -l`); nightly bot commits to main therefore do not make it stale by themselves; if stale, re-verify before trusting; read the task row + brief; confirm lane and file ownership. End: write/refresh `current-state.md` (branch, commit, uncommitted work, test results with timestamps, next action); update the registry row; write report; leave uncommitted work either committed to the task branch or listed explicitly.

---

## 5. Token-Efficiency Plan

Baseline (from Gate 0, bytes; tokens estimated at ~4 bytes/token and therefore approximate):

| Item | Bytes | ~Tokens |
|---|---|---|
| CLAUDE.md | 28.9 KB | 7k |
| all-context.md | 93.7 KB (1,223 lines; changelog block lines 33-568 = 536 lines / 45 KB = ~44% of lines, ~48% of bytes; Open Questions 139 + References 61 + Scan Metadata 57 lines are further non-durable) | 23k |
| orchestration.md | 71.3 KB | 18k |
| Mandatory load total | ~200 KB | ~50k |
| AGENTS.md (Codex copy) | 37.9 KB | drift unmeasured |
| .agents/skills | 17 MB duplicate | not loaded by default; discovery noise |

Measures:

| Lever | Expected effect | Status |
|---|---|---|
| Move changelog out of default load (F4/F5) | all-context 93.7 KB -> ~18-19 KB at 288-300 lines (62.5 bytes/line measured); the planner loads only its ~5-6 KB router section | designed; measure after Gate 2 |
| Two role-based entry sets (F9) | default ~200 KB -> planner <= 64 KB (typical 50-58 KB), worker <= 36 KB (typical ~30 KB); workers stop re-reading planner context | designed; measure after Gate 3 (commands C3, C4) |
| Direct path for trivial changes (existing QUICK FIX / trivial-fix lane) | skip RESEARCH/PLAN for <= ~100 lines, no schema/auth/API | reuse; enforce in master-planner.md |
| Bounded retries | max 2 fix cycles per task, 3 per gate before `blocked`; existing 10-cycle PVL/EVL cap stays as a ceiling | design |
| Concise reports | 11-field schema, summary <= 10 lines | design |
| Selective context | worker envelope links, not contents; worker set excludes north-star.md, current-state.md, MASTER-PLAN.md, the all-context router and orchestration.md | design |
| De-duplicate `.agents/skills` | removes discovery noise, not session tokens | housekeeping H1 |

Measurement method: commands C3 and C4 (byte totals of the planner and worker entry sets, before/after; deterministic); tokens approximated as bytes/4 and labelled approximate. Per-session real token usage: UNMEASURED (no usage telemetry in repo); report field 11 captures a per-task estimate; `list_events` transcripts could be sampled in Gate 3 to get a real baseline for 3-5 past sessions. Unmeasured and kept unmeasured: per-agent token cost, retry waste, cost of repeated test runs, AGENTS.md vs CLAUDE.md drift.

---

## 6. Risk-Based Test Policy

Commands are those named in the repo (all-tests.md, ci.yml, SPEC). Re-confirmed against `all-tests.md` in Gate 4 before being written there. Naming: RT0-RT4 are risk tiers; T# is always a registry task.

| Tier | Change type | Required (run once, after the last edit) | Not required |
|---|---|---|---|
| RT0 Docs / low | markdown, process files, comments | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <plan>` for plans; `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` for context edits; `git diff --check` | pytest, vitest, Playwright |
| RT1 Localized UI | one component/page in `web/` | `pnpm --filter web test` (affected file first, then suite), `pnpm --filter web exec tsc --noEmit` | pytest; Playwright only if a route or flow changed |
| RT2 Localized backend | one module/router in `api/` | `uv run --project api pytest <touched test file>` then `uv run --project api pytest api/ -q` once | vitest, Playwright |
| RT3 Shared interfaces / business logic | `cache.py`, response models, adapters used by 2+ routes | full pytest, full vitest, `tsc --noEmit`, `pnpm build:islands`; contract-snapshot tests unmodified | Playwright unless a route's behavior changed |
| RT4 High risk | auth, secrets, schema/migration, public API contract, deploy/proxy/runtime, destructive data ops | all of RT3 + Playwright (`cd web && pnpm test:e2e`) + hybrid/agent-probe evidence pack (`vc-risk-evidence-pack`) + user acceptance or a recorded agent-probe (acceptance rule (d); bypassing user acceptance for RT4 is the user's call, see the precedence note in section 4) | none skipped |

Test budget rule: each task declares its tier and the max number of full-suite runs (RT0: 0, RT1/RT2: 1, RT3: 2, RT4: 2 plus one EVL confirmation by a spawned vc-tester). No re-running unchanged tests: record in the report the commit SHA each result applies to; a run is repeated only if files changed after that SHA. Bounded retry: a failing gate gets at most 2 fix cycles by the same worker, then escalates to `blocked`/`needs_input`; flake handling: one isolated re-run is allowed to classify a flake, and the flake is logged as a backlog note rather than retried again (consistent with the screener flake note). Environment limits recorded, not hidden: container blocks live provider egress, so live-data checks are user-PC steps (hybrid, `needs_input`). CI (`ci.yml`) is the shared proving ground for RT1-RT3 on PRs; it does not run e2e or lint, so RT4 UI/route changes still need local Playwright.

Known-gap policy: any developed behavior proven only by a known-gap stays CONDITIONAL and gets a backlog stub (vacuous-green ban).

---

## 7. Housekeeping Candidates (no deletion on static search alone)

| ID | Candidate | Evidence | Risk | Needs approval |
|---|---|---|---|---|
| H1 | `.agents/skills` (17 MB) duplicate of `.claude/skills` | Gate 0; fails `validate-skills.mjs`/`validate-context-discovery.mjs` per MASTER-PLAN | Codex discovery might rely on it; symlink behavior on the Windows PC unverified | yes (replace with symlink or doc), validators before/after |
| H2 | `web/tsconfig.tsbuildinfo` tracked | Gate 0 | low; untrack (`git rm --cached`) and ignore (add `web/tsconfig.tsbuildinfo` to `.gitignore`, where it is absent today) | yes |
| H3 | Remote branches (kind-tesla, compassionate-goldberg, narrative-v2, p1-pipeline, p2-deploy, ui-shell, vigilant-hamilton, fix/narrative-sufficiency-gating-rfc1, inspiring-pasteur, pensive-dijkstra) | MEASURED 02-10-26, see the measured table below | deleting an unmerged branch loses work; large all-differ counts are confounded by files archived/moved on main | yes, per branch, after a per-file review; only compassionate-goldberg is a safe-to-delete candidate |
| H4 | split-all-context (2 ahead / 38 behind; 35 of 35 files differ) | holds the context-changelog split commit bf65024 (unique `context-changelog.md`) | losing it before salvage | salvage first, delete never without approval |
| H5 | exciting-meitner (7 ahead / 87 behind) | 7 unique commits of LSE-verification work (script fixes, EVL logs, ADOPT-WITH-LIMITS verdict, status board) | do not delete; Q4 resolved: salvage selectively as R13 (LSE verdict + status-strip fixes; drop duplicate status board section in `all-context.md`) | branch deletion: yes |
| H6 | Dead `cache.write_confirmed_boundaries/read_confirmed_boundaries` | MASTER-PLAN says zero callers | static search misses dynamic use and scripts | needs grep over `api/scripts` + tests, plus run full pytest; user approval |
| H7 | Stale entries in `process/general-plans/active/` (e.g. momentum-screener_17-09-26 with verified sub-plans) | MASTER-PLAN T19 | archiving moves history; reversible via git | yes, via archive index |
| H8 | No root README | Gate 0 | none | no (additive) |
| H9 | AGENTS.md vs CLAUDE.md drift | sizes differ 37.9 vs 28.9 KB; drift unmeasured | silent divergence | measure in Gate 3 |
| H10 | Scout-block hook blocks commands containing `.next`/`node_modules`/`.venv` | Gate 0 | may hinder build/clean steps in Gate 5 | document, no change without approval |

---

### H1 exact commands (gated by user approval; nothing runs without it)

Precondition (Windows PC, unverified known-gap): `git config core.symlinks` must be `true` there and Developer Mode or an elevated checkout must allow symlinks, otherwise a pulled mode-120000 entry materializes as a text file and the validators fail on the PC. Commands (run from the repo root on a Linux/macOS checkout):

1. `git rm -r --cached .agents/skills` (removes the 339 tracked regular files from the index)
2. `rm -rf .agents/skills` (removes the working copy; only after the user approves, and not matched by the scout-block hook patterns)
3. `ln -s ../.claude/skills .agents/skills` (relative link; verify it resolves to the `.claude/skills` realpath)
4. `git add .agents/skills` and confirm `git ls-files -s .agents/skills` shows mode 120000
5. re-run validate-skills.mjs and validate-context-discovery.mjs: the baseline `.agents/skills does not resolve` failure must disappear and no new failure appear.

Rollback: `git revert` the commit. AGENTS.md's symlink statement is corrected in F10 regardless of whether H1 is approved.

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
| 2 | R14, R13, R1-R5 in the order in section 2 (F1-F8 + F11): current-state.md (re-verified), north-star.md, decisions.md, context-changelog.md, slimmed all-context.md, master-planner.md (block-style frontmatter, Master Planner posture, envelope and report templates) wired into all-development-protocols.md, MASTER-PLAN registry from rev 6, archive index skeleton (with the Approvals Log), R4 step (vii) tool-name and behaviour check run by the orchestrator session | VALIDATE first; commands C5 (line cap), C6 (changelog and moved sections preserved), C7 (validator set, failures == baseline), C8 (retired wording), C9 (scope), C11 (every registry ID has a row), C12 (11 report headings, run against master-planner.md), C13 (whitespace and conflict markers in tracked, staged and untracked files) and C14 (Gate 2 deliverables, approvals log, `ROLE: WORKER`, north-star topics, R13 outcome, rev 6 preservation, F15 stubs); the measured bytes of F1, F2, F6 and the F5 router section (the informational `wc -c` lines of C14) are recorded to confirm the entry-set caps | VALIDATE contract; no source edits; ref-only fetch for branch facts requires approval |
| 3 | R6, R7: CLAUDE.md/AGENTS.md rewrite (F9, F10; role-neutral), byte baselines for BOTH entry sets, sampled session token baseline | commands C1 (no @-imports), C2 (role-neutral), C3 (planner bytes), C4 (worker bytes), C9 (scope, Gate 3 form allows CLAUDE.md and AGENTS.md), C10 (ENTRY-SET); validate-kit-portability.mjs, validate-protocol-wiring.mjs, validate-agent-parity.mjs non-strict (0 failures; the 18 warnings are baseline); validate-guide-sync.mjs: baseline-aware, README decision below; two agent-probes: a fresh PLANNER session reaches a task brief reading only the planner set, and a fresh WORKER session given only a sample envelope states ROLE: WORKER, spawns nothing and reaches its task reading only the worker set | CLAUDE.md/AGENTS.md edits (high-visibility, user review before commit) |
| 4 | R8: test policy in all-tests.md, re-measured test counts | run the three suites once (measured, timestamped) | none beyond Gate approval; installs need approval |
| 5 | R9-R12: housekeeping (approved items), README, deploy-path doc/guard proposal, session triage + archive index (R13 and R14 are Gate 2 work, ahead of R5, and are not repeated here) | per-item evidence re-check; validators; no deletion without per-item approval; R12 verified on the user's PC (hybrid) | branch deletion, `archive_session`, `.agents/skills` replacement, tsbuildinfo untrack, deploy-script changes, any installs |
| 6 | Master Planner pilot: dispatch ONE low-risk task (e.g. P7 guard test or R-level docs task) through the registry end-to-end; then start approved product tasks | pilot task reaches `accepted` through the rule in section 4; report has 11 fields (command C12 against the pilot report); the pilot worker records in report field 11 which session and merge tools its own tool list contains (section 4, (vii)) | each product task `approved` by user; spawning workers for `approved` tasks is covered by the standing authorization (section 4, max 3 concurrent); high-risk tasks are covered too ("no exceptions"), but self-merge needs every mechanical condition and the worker being sure; unverifiable runtime conditions mean `review` |

Each gate ends with a closeout (UPDATE PROCESS) and a commit on `main` only when you ask (repo policy).

### Validator baseline and README scope (measured 02-10-26, before any Gate 2 write)

Every validator gate in this plan means **no NEW failure versus this baseline**, not exit 0:

| Validator | Baseline failures | Cause |
|---|---|---|
| validate-context-discovery.mjs | 1 | `.agents/skills` is 339 tracked regular files, not a symlink (cleared by H1) |
| validate-skills.mjs | 1 | same cause |
| validate-guide-sync.mjs | 1 | no root README |
| validate-agent-parity.mjs --strict | 18 | pre-existing Claude/Codex agent drift; non-strict = 0 failures, 18 warnings; this plan uses NON-strict |
| protocol-wiring, kit-portability, agent-frontmatter, skill-invocation-wiring, protocol-discovery, validate-all-context, `discover-context.mjs --check-routing`, `git diff --check` | 0 | clean |
| validate-plan-inventory.mjs (in C7 because Gate 2 moves a plan folder, R13) | 0 failures, 6 warnings | baseline; no new failure or warning allowed |

README scope decision: F13 stays Gate 5 and is a ~60-line runbook README; validate-guide-sync (needs an Agents table and a Skills section) is NOT satisfied at Gate 3 and is accepted at its baseline failure (1) until Gate 5; at Gate 5 the README gains the two sections or the 1-failure baseline is carried as a recorded known-gap. This is stated, not hidden.

---

## 10. Acceptance Criteria (this program)

| ID | Criterion | proven by | strategy |
|---|---|---|---|
| AC-R1 | TWO role-based entry sets (caps provisional, confirmed at Gate 2 close): PLANNER (CLAUDE.md + north-star.md + current-state.md + MASTER-PLAN.md + all-context.md router section + task brief) <= 64,000 bytes; WORKER (CLAUDE.md + task envelope <= 8,000 + task PLAN/SPEC) <= 36,000 bytes. Neither set loads the changelog or orchestration.md; CLAUDE.md has no `@`-imports and is role-neutral | commands C1 (no output after Gate 3; 3 lines today), C2 (no output after Gate 3; 8 lines today), C3 and C4 (byte totals), plus a fresh-session probe for each role at Gate 3 | Fully-Automated + Agent-Probe |
| AC-R2 | all-context.md <= 300 lines; changelog and moved sections fully preserved in context-changelog.md | commands C5 (line cap) and C6 (preservation; prints nothing) | Fully-Automated |
| AC-R3 (=AC-19) | Single North Star doc exists with personal-use, data-not-verdicts, Tailscale-only, page list, non-goals; old confidence/public-later/redistribution wording gone from entry points (history lives only in context-changelog.md) | command C8 -> no output after Gate 2 (11 hits today, all in all-context.md); case-insensitive | Fully-Automated |
| AC-R4 (=AC-20) | Current-state, task registry, archive index, MASTER-PLAN reconciled and referenced from CLAUDE.md/AGENTS.md/all-context | link/grep check + validator set C7 (failures == baseline) + command C10 at Gate 3 | Fully-Automated |
| AC-R5 | Registry holds all T-tasks (T1, T1b, T3-T5, T7-T28; T2 and T6 are recorded as unknown, not invented), with T26-T28 from rev 6, each with a status and evidence note; unverified items labelled UNVERIFIED | review of registry vs section 3 + command C11 (checks each ID individually; a row count is not used because other tables also start with `| T`: counts today are 18 on main and 20 on rev 6) | Hybrid (user review) |
| AC-R6 | No branch, session, or file removed without recorded approval | git/session state diff vs the approvals log, which is the `## Approvals Log` section of `process/archive/index.md` (one row per approval: date, what, approver quote); an empty log means no removal is permitted | Hybrid |
| AC-R7 | Acceptance rule demonstrated: pilot task not `accepted` on worker word alone | pilot report + registry history | Agent-Probe |
| AC-R8 | Product code untouched by Gates 2-4 | command C9 (`git status --porcelain` based, sees uncommitted and untracked files; no output at Gate 2 and Gate 4, Gate 3 form allows CLAUDE.md and AGENTS.md); `<gate-base-sha>` = `git rev-parse HEAD` recorded when the gate starts, used only for the post-commit form of C9 | Fully-Automated |
| AC-R9 | Token claims labelled measured/unmeasured | review of Gate 3 report | Hybrid |
| AC-R10 | Worker completion reports carry all 11 fields | command C12 equals 11, run against the report template inside master-planner.md at Gate 2 (the first real worker report exists only at Gate 6) and against the pilot report at Gate 6 | Fully-Automated |

### Pinned gate commands (all gate commands live here; run in bash from the repo root)

Pipes are safe in a fenced block and are NOT used in table cells (a pipe inside a markdown table cell has to be escaped, and an escaped pipe inside `grep -E` is a literal pipe, which made earlier forms vacuous). "Expected today" was measured 02-10-26 before any Gate 2 write: a gate whose result cannot differ from today's is vacuous.

```
# C1  AC-R1: no @-imports in CLAUDE.md
grep -nE '[[:space:](]@[A-Za-z./_-]+\.md' CLAUDE.md
# expected today: 3 lines (CLAUDE.md lines 20, 36, 48). After Gate 3: no output (grep exit 1).
# (the retired form with an escaped pipe inside -E printed 0 lines today: vacuous)

# C2  AC-R1: CLAUDE.md and AGENTS.md are role-neutral
grep -nE 'You are the orchestrator|You do NOT|Your responsibilities|Orchestrator Role' CLAUDE.md AGENTS.md
# expected today: 8 lines (CLAUDE.md 46, 50, 52, 59; AGENTS.md 50, 56, 58, 65). After Gate 3: no output; the one role-scoped
# sentence the plan keeps in CLAUDE.md must avoid these literals.

# C3  AC-R1: PLANNER entry set bytes (after Gate 3). TASK = the task PLAN or SPEC being worked
TASK=<path>
MISS=0; for f in CLAUDE.md process/context/north-star.md process/context/current-state.md process/MASTER-PLAN.md "$TASK"; do test -s "$f" || { echo "MISSING $f"; MISS=1; }; done
ROUTER=$(sed '/^## Context Group Lifecycle/,$d' process/context/all-context.md | wc -c)
REST=$(cat CLAUDE.md process/context/north-star.md process/context/current-state.md process/MASTER-PLAN.md "$TASK" 2>/dev/null | wc -c)
total=$((ROUTER + REST)); echo total=$total
test "$MISS" -eq 0 && test "$total" -le 64000; echo rc=$?
# must print rc=0 (provisional cap 64000). Today (verified 02-10-26 with TASK = this plan): prints MISSING for north-star.md and
# current-state.md, total=240454 and rc=1. The earlier `cat | wc -c` form printed 234253 with two stderr errors because a failing
# cat does not fail wc, which is why the file check comes first. The router range still contains the 45 KB changelog today.

# C4  AC-R1: WORKER entry set bytes (after Gate 3). ENVELOPE = the saved envelope file, TASK = its task PLAN/SPEC
ENVELOPE=<path>; TASK=<path>
test "$(wc -c < "$ENVELOPE")" -le 8000 && cat CLAUDE.md "$ENVELOPE" "$TASK" | wc -c
# must print a number <= 36000 (provisional). Not runnable today (no envelope exists yet).

# C5  AC-R2: all-context.md line cap
test "$(wc -l < process/context/all-context.md)" -le 300; echo rc=$?
# expected today: rc=1 (1,223 lines). At Gate 2 close: rc=0.

# C6  AC-R2: changelog and moved sections preserved whole (BASE = git rev-parse HEAD recorded when Gate 2 starts)
BASE=<gate2-base-sha>; TMPDIR=${TMPDIR:-/tmp}
f() { git show "$BASE:process/context/all-context.md"; }
sec() { f | awk -v h="$1" 'index($0,"## "h)==1{p=1;print;next} /^## /{p=0} p'; }
f | grep -n '^## '
{ f | awk '/^## Changes Since Last Update/{p=1} /^## What This Project Is/{p=0} p'; sec "Open Questions"; sec "References"; sec "Scan Metadata"; } | sort -u > "$TMPDIR/base-moved.txt"
sort -u process/context/context-changelog.md > "$TMPDIR/f4.txt"
comm -23 "$TMPDIR/base-moved.txt" "$TMPDIR/f4.txt"
# must print nothing. Today the changelog block is lines 33-568 (536 lines) and the moved sections are
# Open Questions 967-1105, References 1106-1166, Scan Metadata 1167-1223; context-changelog.md does not exist yet.
# Negative case verified on a scratch copy: one dropped line prints exactly that line.

# C7  validator set (every result means "no NEW failure versus baseline", not exit 0)
node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs
node .claude/skills/vc-generate-context/scripts/validate-all-context.mjs
node .claude/skills/vc-context-discovery/scripts/discover-context.mjs --check-routing
node .claude/skills/vc-audit-vc/scripts/validate-protocol-wiring.mjs
node .claude/skills/vc-audit-context/scripts/validate-protocol-discovery.mjs
node .claude/skills/vc-audit-vc/scripts/validate-kit-portability.mjs
node .claude/skills/vc-audit-vc/scripts/validate-agent-parity.mjs
node .claude/skills/vc-audit-plans/scripts/validate-plan-inventory.mjs
# expected today: validate-context-discovery 1 failure (the .agents/skills symlink baseline); all others 0 failures;
# validate-plan-inventory 0 failures and 6 warnings (baseline; Gate 2 moves a plan folder in R13, so no new failure or warning is allowed).
# Gate 3 only: grep -c 'process/context/all-context.md' CLAUDE.md AGENTS.md must print a count >= 1 for BOTH files (today 9 and 12);
# validate-context-discovery requires the literal path in each.

# C8  AC-R3: retired wording absent from entry points (case-insensitive)
grep -niE 'confidence over direction|open it to other users|public[ -]later|open up later|other users later|intended to open|redistribution-safe|redistribution is a first-class|redistributab|licens(e|ing) is a design constraint' CLAUDE.md AGENTS.md process/context/all-context.md process/context/north-star.md
# expected today: 11 hits, all in all-context.md (lines 95, 373, 446, 581, 582, 910, 955, 957, 962, 964, 1020; verified 02-10-26). After Gate 2: no output.
# The widened alternatives catch the hyphenated `public-later` (line 955), the wrapped `open it to / other users later` (580-581) and `open up later` (964).
# (the same pattern written with escaped pipes printed 0 hits today: vacuous)

# C9  AC-R8: scope check that also sees uncommitted and untracked files
git status --porcelain | cut -c4- | grep -vE '^process/'
# Gates 2 and 4: no output (grep exit 1). Today: no output (clean tree). Gate 3 form:
git status --porcelain | cut -c4- | grep -vE '^(process/|CLAUDE\.md$|AGENTS\.md$)'
# Gate 5 form (README, ignore-file and tsbuildinfo untrack only; deploy/ and `.agents/skills` paths are added to the filter only when the user approves R12 or H1):
git status --porcelain | cut -c4- | grep -vE '^(process/|README\.md$|\.gitignore$|web/tsconfig\.tsbuildinfo$)'
# after a commit, the post-commit form is: git diff --name-only <gate-base-sha>..HEAD (same filters)

# C10  AC-R4: ENTRY-SET block identical in CLAUDE.md and AGENTS.md (Gate 3; needs bash for <( ))
test "$(grep -c 'ENTRY-SET:BEGIN' CLAUDE.md)" -eq 1 && test "$(grep -c 'ENTRY-SET:BEGIN' AGENTS.md)" -eq 1 && test "$(grep -c 'ENTRY-SET:END' CLAUDE.md)" -eq 1 && test "$(grep -c 'ENTRY-SET:END' AGENTS.md)" -eq 1 && diff <(sed -n '/ENTRY-SET:BEGIN/,/ENTRY-SET:END/p' CLAUDE.md) <(sed -n '/ENTRY-SET:BEGIN/,/ENTRY-SET:END/p' AGENTS.md)
# expected today: exit 1 at the first test (0 markers in both files; the bare diff would exit 0). Gate 3: exit 0.

# C11  AC-R5: every registry ID present as a row (IDs checked individually)
for id in T1 T1b T3 T4 T5 T7 T8 T9 T10 T11 T12 T13 T14 T15 T16 T17 T18 T19 T20 T21 T22 T23 T24 T25 T26 T27 T28; do
  n=$(grep -cE "^\| $id \|" process/MASTER-PLAN.md); [ "$n" -ge 1 ] || echo "MISSING $id"
done
# expected today: prints MISSING for T1 T1b T3 T4 T5 T7 T8 T23 T26 T27 T28 (main, rev 3a). After Gate 2: no output.

# C12  AC-R10: the report template/report carries the 11 headings
grep -cE '^(#+ )?(1 Task ID|2 Outcome|3 Summary|4 Files changed|5 Commits|6 Tests run|7 Tests NOT run|8 Deviations|9 Blockers|10 Follow-up|11 Context cost)' process/development-protocols/master-planner.md
# Gate 2: must print 11 (template lives in master-planner.md). Gate 6: same grep on the pilot report, must print 11.
# Verified on a full fixture (11) and a partial one (8). Today master-planner.md does not exist.

# C13  whitespace, conflict markers and plan structure (tracked, staged AND untracked files)
git diff --check
git diff --cached --check
for f in $(git ls-files --others --exclude-standard); do git diff --check --no-index /dev/null "$f"; done
node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md
# expected: NO OUTPUT from the first three lines; the gate is "no output", not an exit code (git diff --check --no-index exits 1 for any
# added file). Plain `git diff --check` is blind to untracked and staged-only files, which is every new Gate 2 file: verified on a scratch
# repo, a new file with trailing whitespace and a conflict marker left it at exit 0, while the loop printed both offending lines, a clean
# file printed nothing, and `git diff --cached --check` caught a staged-only file. Today: no output (clean tree); plan validator 0 failures.

# C14  AC-R3, AC-R5, AC-R6, AC-R10: Gate 2 deliverables exist and carry their required parts (no MISSING/FAIL line and no comm output = pass)
for f in process/context/north-star.md process/context/current-state.md process/context/decisions.md process/context/context-changelog.md process/development-protocols/master-planner.md process/archive/index.md process/archive/master-plan-revisions_02-10-26.md process/general-plans/backlog/token-usage-telemetry_NOTE_02-10-26.md process/general-plans/backlog/agents-skills-symlink-windows_NOTE_02-10-26.md process/general-plans/backlog/deploy-runtime-user-pc-verification_NOTE_02-10-26.md; do
  test -s "$f" || echo "MISSING $f"
done
test "$(grep -c '^## Approvals Log' process/archive/index.md 2>/dev/null)" -eq 1 || echo "FAIL approvals-log heading"
test "$(sed -n '/^## Approvals Log/,$p' process/archive/index.md 2>/dev/null | grep -c 'lse-data-verification')" -ge 1 || echo "FAIL approvals-log lse row"
test "$(grep -c 'ROLE: WORKER' process/development-protocols/master-planner.md 2>/dev/null)" -ge 1 || echo "FAIL ROLE: WORKER"
for t in 'personal[- ]use' 'not verdicts' 'tailscale' '^#+ .*pages' '^#+ .*non-goals'; do
  test "$(grep -ciE "$t" process/context/north-star.md 2>/dev/null)" -ge 1 || echo "FAIL north-star topic $t"
done
test -d process/general-plans/completed/lse-data-verification_17-09-26 || echo "FAIL R13 completed/ folder missing"
test ! -d process/general-plans/active/lse-data-verification_17-09-26 || echo "FAIL R13 active/ folder still present"
REV6=18ffd4f014f4e5ea0f5d654688875a9300b30ab4; TMPDIR=${TMPDIR:-/tmp}
git show "$REV6:process/MASTER-PLAN.md" | sort -u > "$TMPDIR/rev6.txt"
cat process/MASTER-PLAN.md process/archive/master-plan-revisions_02-10-26.md 2>/dev/null | sort -u > "$TMPDIR/f6.txt"
comm -23 "$TMPDIR/rev6.txt" "$TMPDIR/f6.txt" | grep -vE '^\| (T|P)'
# informational, for the Gate 2 report (confirms or tightens the provisional caps; a cap is raised only with user approval):
wc -c process/context/north-star.md process/context/current-state.md process/MASTER-PLAN.md
sed '/^## Context Group Lifecycle/,$d' process/context/all-context.md | wc -c
# expected today (measured 02-10-26): 10 MISSING lines (7 deliverables + 3 stubs), 10 FAIL lines (approvals-log heading, approvals-log
# lse row, ROLE: WORKER, 5 north-star topics, R13 completed/ missing, R13 active/ still present) and 210 comm lines (rev 6 lines absent
# from today's rev 3a MASTER-PLAN.md), followed by the three informational byte lines (213 output lines in all). After Gate 2: no MISSING, no FAIL, no comm output. Verified on a scratch tree: a complete fixture
# prints nothing, and one dropped non-row rev 6 line prints exactly that line. Residual: the `| T`/`| P` filter lets re-expressed
# registry rows through (C11 checks each ID by name), so a dropped row is caught by C11, not here. The F5 router-section byte line uses the
# same sed range as C3.
```

## Verification Evidence

Commands C1-C14 are the fenced block in section 10.

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G2 command C5 (all-context.md <= 300 lines) | Fully-Automated | AC-R2 |
| G2 command C6 (changelog and moved sections preserved, prints nothing) | Fully-Automated | AC-R2 |
| G2 command C7 validator set (validate-context-discovery failures == the 1-item baseline; all-context, routing check, protocol wiring, protocol discovery, kit portability, agent parity non-strict at 0 failures) | Fully-Automated | AC-R4 |
| G2 command C8 (retired wording absent from entry points) | Fully-Automated | AC-R3 |
| G2 command C9 (scope: only process/ changed) | Fully-Automated | AC-R8 |
| G2 command C12 against the report template inside master-planner.md (after F7) | Fully-Automated | AC-R10 |
| G2 R4 (vii): tool names and one read-only list_sessions dry-run, run by the orchestrator session | Agent-Probe | AC-R7 |
| G2/G5 registry reviewed against evidence, command C11 | Hybrid | AC-R5 |
| G2 command C13 (whitespace and conflict markers in tracked, staged and untracked files; no output) | Fully-Automated | AC-R4 |
| G2 command C14 (deliverables exist; `## Approvals Log` with the R13 row; `ROLE: WORKER`; north-star topics; R13 outcome; rev 6 preserved in F6 plus the archive file; F15 stubs) | Fully-Automated | AC-R3, AC-R5, AC-R6, AC-R10 |
| G3 commands C1 and C2 (no @-imports, role-neutral) | Fully-Automated | AC-R1 |
| G3 commands C3 and C4 (planner and worker byte tables; tokens labelled approximate) | Fully-Automated | AC-R1, AC-R9 |
| G3 two fresh-session probes (PLANNER reaches a task brief on the planner set; WORKER given only a sample envelope states ROLE: WORKER, spawns nothing, reaches its task on the worker set) | Agent-Probe | AC-R1 |
| G3 validator subset (kit portability, protocol wiring, agent parity non-strict; guide-sync at baseline) | Fully-Automated | AC-R4 |
| G3 command C10 (ENTRY-SET block identical, one marker per file) | Fully-Automated | AC-R4 |
| G3 command C9, Gate 3 form | Fully-Automated | AC-R8 |
| G5 approvals log vs state diff | Hybrid | AC-R6 |
| G6 pilot task end-to-end | Agent-Probe | AC-R7 |
| G6 command C12 against the pilot report | Fully-Automated | AC-R10 |
| G4 command C9 (scope) | Fully-Automated | AC-R8 |

Known gaps (named residuals, keep gates CONDITIONAL): real per-session token usage; behavior of a symlinked `.agents/skills` on the user's Windows PC; deploy fixes verified only on the user's PC (hybrid, user-run). Backlog stubs for these are written at Gate 2 as F15 (checked by command C14).

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
| A spawned worker loads an orchestrator-flavoured CLAUDE.md and orchestrates (spawns agents, full RIPER-5 ceremony) | med-high | CLAUDE.md role-neutral (C2); envelope first line `ROLE: WORKER` overrides; worker probe at Gate 3 and the Gate 6 pilot |
| Planner entry set grows past its cap because the registry joins it | med | MASTER-PLAN F6 target ~250 lines with one row per task; caps confirmed from measured bytes at Gate 2 close and raised only with user approval |
| Token savings overstated | med | bytes measured, tokens approximate, usage unmeasured |

Assumptions: Gate 0 numbers are accurate; MASTER-PLAN facts dated 09-28 may be stale and are labelled; realignment and baskets SPECs are the North Star source; repo policy (commit directly on `main` only on request) applies.

## 13. Open Questions

Resolved 02-10-26 (user answers, authoritative; numbering kept stable because other sections cite item 10):

1. Q1 RESOLVED 02-10-26: `process/MASTER-PLAN.md` is the single board and task registry (reconciled and wired into session start).
2. Q2 RESOLVED 02-10-26: CLAUDE.md target up to ~20 KB.
3. Q3 RESOLVED 02-10-26: build the 3 deploy fixes (stop old web process before build / kill-by-port, stale-build guard in `start-web`, post-start smoke check) as own task R12 (high-risk deploy class).
4. Q5 RESOLVED 02-10-26: realignment SPEC split into `personal-tracker-realignment_02-10-26` (19 active ACs) and `narrative-baskets_02-10-26` (12 active ACs); docs/process criteria owned here as AC-R3/AC-R4.
5. Q6 RESOLVED 02-10-26: standing authorization recorded verbatim in section 4; the high-risk exclusion was declined by the user ("no exceptions").
6. Q7 RESOLVED 02-10-26: T15 demoted to low priority; licensing is no longer a design constraint (personal use).
7. Q4 RESOLVED 02-10-26: salvage `claude/exciting-meitner-hy50kn` selectively (LSE verdict + status-strip fixes; drop the duplicate status board section in `all-context.md`) as registry task R13.
8. Q8 RESOLVED 02-10-26: ref-only fetch approved and done; measured results recorded in section 7 (replacing the earlier UNVERIFIED branch statements).
9. Self-merge guardrail RESOLVED 02-10-26: "No exceptions" (user declined the high-risk exclusion); fail-safes and the verifiability consequence are in section 4. The earlier "flagged for confirmation" item is closed.
11. Role-based entry sets RESOLVED 02-10-26 (user-approved refinement): only the Master Planner session needs the heavy protocol context; spawned worker sessions must not re-read it. Verified facts: every new session and subagent loads CLAUDE.md automatically including its `@`-imports; spawned sessions do not inherit the planner's context. Recorded in section 2 (two entry sets, role-neutral CLAUDE.md), section 4 (envelope, worker lane) and AC-R1.

Still OPEN:

10. OPEN (needs the user's explicit accept or decline): control-surface self-merge. Recommendation: forbid self-merge for diffs that touch ci.yml, validators, master-planner.md, CLAUDE.md/AGENTS.md or `.claude/`, stopping at `review`. This does not override 'no exceptions'; until answered the plan follows the user's decision and records the residual as user-accepted with a post-merge main-CI check and revert proposal (section 4, Enforcement and compensating controls). Non-blocking for Gate 2 start. Two related extensions are also recorded here for the user's call, neither assumed by this plan: (a) whether RT4 / high-risk tasks may bypass user acceptance (section 4 precedence note); (b) whether the Master Planner may merge a worker's PR when the worker's own tool list lacks a merge tool (section 4, (vii)).

12. OPEN, user decision, non-blocking for Gate 2 start: confirm the worker lane as a DIRECT lane. A worker does not run the multi-agent RIPER chain; it writes a compact per-task validate-contract itself and runs its declared gates directly (section 4, worker lane rule). Clarification: one vc-quick-fix-agent spawn for a tiny task is not a subagent chain, so it does not conflict with the Role Selection text "do not spawn sessions or subagent chains". Until answered, the plan follows this lane as user-approved on 02-10-26.

Still OPEN: none blocking. Standing consent for branch deletion remains NOT granted (separate, future decision; no deletion by this plan without per-branch approval).

---

## Touchpoints

Gate 2-5 writes: `process/context/*` (new and slimmed), `process/MASTER-PLAN.md`, `process/archive/index.md`, `process/development-protocols/master-planner.md`, `all-development-protocols.md`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `web/tsconfig.tsbuildinfo` (untrack), `.gitignore` (add the tsbuildinfo ignore line; single owner at Gate 5), `process/context/data-sources/all-data-sources.md`, `process/archive/master-plan-revisions_02-10-26.md`, three backlog stubs under `process/general-plans/backlog/` (F15: `token-usage-telemetry_NOTE_02-10-26.md`, `agents-skills-symlink-windows_NOTE_02-10-26.md`, `deploy-runtime-user-pc-verification_NOTE_02-10-26.md`) and the lse-data-verification task folder (R13: moved from `process/general-plans/active/` to `process/general-plans/completed/`). Reads: git state, MCP session list, `deploy/`. This plan itself writes only its own file.

## Public Contracts

Behavior contracts other sessions rely on: the default entry set; the task status vocabulary; the acceptance rule; the 11-field report path/schema; the four archive operations. No API, schema, or runtime contract changes.

## Blast Radius

Docs/process only through Gate 4 (risk class: RT0). Gate 5 adds git-index and ignore changes (RT0-RT1) and optional deploy script changes (RT4, separately approved). No product code.

## Test Infra Improvement Notes

(none identified yet) Candidate noted: no token-usage telemetry; no deployed smoke test; ci.yml lacks lint/e2e.

## Validate Contract

Status: CONDITIONAL
Date: 02-10-26
date: 2026-10-02
generated-by: outer-pvl
supersedes: 2026-10-02 (outer-pvl) - outer PVL cycle 3 has current evidence (re-validation of the cycle-2 supplement, Gaps 14-23 plus the role-based entry sets, against the live repo and a scratch copy)
Scope: this contract gates the START of Gate 2 only (F1-F8, F11, R13, R14). Gates 3-6 each re-enter VALIDATE (plan rule); the Gate 3+ findings below are carried forward as requirements, not as approval.

Parallel strategy: sequential (single validate session; Layer 1 and Layer 2 checks ran inline as read-only commands, no sub-agent spawn tool was available to this session)
Rationale: signal score 2/7 (S6 high-risk class named in plan: deploy/secrets/auth under the self-merge authorization; S7 14+ files in blast radius). MEDIUM band would normally recommend parallel read-only subagents; dominant signal is S7. Findings below are evidence-based: in cycle 3 every pinned command C1-C13 was actually run against the live tree (or a scratch copy for the ones that need Gate 2 files), validators were re-run read-only, remote refs and the exciting-meitner / pensive-dijkstra diffs were queried read-only, repo settings were re-read with `gh api`, and the F7 frontmatter and the ENTRY-SET diff were exercised on scratch repos in the session scratchpad (no repo state changed).

Baseline measured 02-10-26 (read-only runs on branch claude/pensive-albattani-ou0cgv, before any Gate 2 write; RE-CONFIRMED in cycle 3, unchanged). Every Gate 2/3 validator gate is "no NEW failure vs this baseline", not "exit 0":

| Validator | Baseline failures | Cause |
|---|---|---|
| validate-context-discovery.mjs | 1: `.agents/skills does not resolve to .claude/skills` | `.agents/skills` is 339 tracked regular files (mode 100644), not a symlink |
| validate-skills.mjs | 1: same message | same cause |
| validate-guide-sync.mjs | 1: `README.md does not exist` | no root README (F13 is Gate 5) |
| validate-agent-parity.mjs --strict | 18 (all "normalized body differs" / "descriptions differ") | pre-existing Claude/Codex agent drift; non-strict run = 0 failures, 18 warnings (re-run cycle 3: failures=0 warnings=18) |
| validate-protocol-wiring.mjs, validate-kit-portability.mjs, validate-agent-frontmatter.mjs, validate-skill-invocation-wiring.mjs, validate-protocol-discovery.mjs, validate-all-context.mjs, `discover-context.mjs --check-routing`, `git diff --check`, validate-plan-artifact.mjs (this plan, re-run cycle 3: 0 failures, 0 warnings) | 0 | clean |
| validate-plan-inventory.mjs (not in the plan's baseline table; Gate 2 moves a plan folder, R13) | 0 failures, 6 warnings (measured cycle 3) | add to C7 with this baseline (Gap 30) |

Cycle-1 gap re-verification (13 prior gaps, each re-checked against the live repo, cycle 2; unchanged in cycle 3): Gaps 1, 3 (residual 16 closed in cycle 3), 4, 7, 10, 12 CLOSED; Gaps 2, 5, 6, 8, 9, 11, 13 CLOSED with the residuals that cycle 2 raised as Gaps 14-23, all re-checked below.

Cycle-2 gap re-verification (Gaps 14-23, each re-checked live in cycle 3):

| Gap | Result | Evidence (cycle 3, executed) |
|---|---|---|
| 14 vacuous AC-R1 / AC-R3 commands | CLOSED (residuals Gaps 28, 29) | C1 prints exactly 3 lines today (CLAUDE.md lines 20, 36, 48); C8 prints exactly 8 hits today, all in all-context.md at lines 95, 373, 446, 582, 910, 957, 962, 1020; both match the stated expected-today output |
| 15 AC-R8 vacuous before commit | CLOSED (residual Gap 27) | C9 prints nothing today (grep exit 1, clean tree) |
| 16 entry-set arithmetic, router section | CLOSED (residuals Gaps 29, 30) | F5 table sums to 288 lines; kept sections measure 398 lines = 24,895 bytes = 62.5 B/line; base router equivalent (lines 1-32 + 569-680) = 144 lines / 7,709 bytes; the C3 router `sed` range measures 680 lines / 52,734 bytes today (includes the changelog, as the plan says); PLANNER cap 64,000 = 20,000 + 4,000 + 4,000 + 20,000 + 8,000 + 8,000; WORKER cap 36,000 = 20,000 + 8,000 + 8,000; both are sums of the table caps, consistent with the TL;DR. Rev 6 T-rows average 223 bytes, so the F6 cap of 20,000 is plausible but tight for a 13-column schema: provisional, measured at Gate 2 close, raise only with user approval (already stated) |
| 17 F5 retired wording, ranges recomputed | CLOSED with a residual (Gap 28) | C6 end to end on a scratch F4 built from the base: faithful copy prints 0 lines, one dropped line prints exactly that line; recomputed ranges 33-568, 967-1105, 1106-1166, 1167-1223; lines 910, 957, 962 are dropped by the table, but line 955 survives (see Gap 28) |
| 18 F7 block-style frontmatter | CLOSED | scratch repo: block-style `metadata:` with five indented lines gives 0 failures; the flow-style `{...}` map fails with metadata.type, node_type, read_order, required, read_when missing; `read_order: 10` is also used by references/program-goal-charter-template.md and a duplicate is not a validator failure |
| 19 registry priority collision | CLOSED for P-IDs (new residual Gap 24) | no `Pri (P0-P3)` left; `Prio (H/M/L)`; but test tiers T0-T4 collide with task IDs T1-T28 |
| 20 acceptance rule vs standing authorization | CLOSED | acceptance rule (b) counts CI on the head SHA; precedence sentence present; T4 row says "user acceptance or a recorded agent-probe"; consistent with Open Question 10(a) |
| 21 ENTRY-SET marker assertion | CLOSED | C10 run on scratch files: identical blocks exit 0, differing blocks exit 1, missing markers exit 1 at the first test; on today's tree exit 1 at the first test |
| 22 AC-R10 heading grep timing | CLOSED | C12 prints 11 on a full scratch fixture; today master-planner.md does not exist, grep exits 2 with an error (not a silent 0 and not a pass) |
| 23 small accuracy fixes (a)-(f) | CLOSED | (a) ci.yml lines 41 and 57 contain the em dash; (b) narrative-baskets SPEC has Decision 16 and AC-25; (c) exciting-meitner vs merge-base is exactly 16 files, 5 of them in `active/lse-data-verification_17-09-26/` removed or renamed, destinations in `completed/`, matching the plan; (d) Gate 5 reads R9-R12; (e) resolved items moved; (f) C11 prints MISSING for exactly T1 T1b T3 T4 T5 T7 T8 T23 T26 T27 T28 on main, rev 6 has 20 T-rows and main 18 |

Role-neutral CLAUDE.md breakage check (asked explicitly): no validator, hook or agent depends on the "You are the orchestrator" wording. Searched `.claude/hooks`, `.claude/agents`, `.codex`, all validator scripts under `.claude/skills/*/scripts`, `process/development-protocols` and `process/context`: no hit for "You are the orchestrator", "Orchestrator Role", "Your responsibilities" outside CLAUDE.md and AGENTS.md themselves; hooks reference CLAUDE.md only to count config files. Validators that do read CLAUDE.md or AGENTS.md: validate-context-discovery (requires the literal `process/context/all-context.md` in both files and scans them for stale patterns), validate-kit-portability (rejects backticked `process/context/<file>` outside three survivors), validate-seeds (no CLAUDE.md content check). New Gate 3 requirement carried forward (Gap 30): the rewritten CLAUDE.md and AGENTS.md must keep the literal `process/context/all-context.md`.

Test gates (C3 5-column table; Gate 2 start scope; Gate 3+ rows are carried forward):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-R2 | all-context.md reduced to the line cap | Fully-Automated | command C5: `test "$(wc -l < process/context/all-context.md)" -le 300` (rc=1 today, rc=0 at close) | B (disposition table added, cycle 1) |
| AC-R2 | changelog block and moved sections preserved whole in context-changelog.md | Fully-Automated | command C6 (`comm -23`; verified positive and negative on a scratch copy in cycle 3); ranges recomputed with `grep -n '^## '` at Gate 2 start | B |
| AC-R4 | context docs indexed and routing intact, no new failures | Fully-Automated | `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` -> failures exactly equal the 1-item baseline | B |
| AC-R4 | all-context.md keeps validator-required sections | Fully-Automated | `node .claude/skills/vc-generate-context/scripts/validate-all-context.mjs` -> 0 failures; `node .claude/skills/vc-context-discovery/scripts/discover-context.mjs --check-routing` -> in sync | B |
| AC-R4 | master-planner.md wired and discoverable in the same gate it is created | Fully-Automated | `node .claude/skills/vc-audit-vc/scripts/validate-protocol-wiring.mjs` and `node .claude/skills/vc-audit-context/scripts/validate-protocol-discovery.mjs` -> 0 failures (F7 block-style frontmatter verified in cycle 3) | B |
| AC-R3/AC-R4 | no non-portable concrete context path in protocols or entry files | Fully-Automated | `node .claude/skills/vc-audit-vc/scripts/validate-kit-portability.mjs` -> 0 failures | B |
| AC-R4 | agent parity not worsened | Fully-Automated | `node .claude/skills/vc-audit-vc/scripts/validate-agent-parity.mjs` (non-strict) -> 0 failures | B |
| AC-R4 | plan inventory not worsened by the R13 folder move | Fully-Automated | `node .claude/skills/vc-audit-plans/scripts/validate-plan-inventory.mjs` -> failures stay 0 (baseline 0 failures, 6 warnings) | B (pending Gap 30) |
| AC-R3 | retired wording gone from entry points | Fully-Automated | command C8 -> no output after Gate 2 (8 hits today, all in all-context.md) | B (pending Gap 28: pattern blind to `public-later`, line 955 survives F5) |
| AC-R1 | default load no longer imports big files | Fully-Automated | command C1 -> no output after Gate 3 (3 lines today); C3/C4 byte totals at Gate 3 | B (pending Gap 29: C3 prints a number even when an input file is missing) |
| AC-R8 | product code untouched | Fully-Automated | command C9 -> no output at Gate 2 (verified empty today) | A |
| all | whitespace and conflict markers | Fully-Automated | command C13 `git diff --check` -> exit 0 | B (pending Gap 27: blind to untracked new files, which is every new Gate 2 file) |
| Gate 2 deliverables | F1, F2, F3, F4, F7, F8, the F6 archive file and the R13 move exist and carry their required parts | Fully-Automated | NOT YET PINNED: no command today proves F1/F2/F3/F8 exist, that `## Approvals Log` exists, that rev 6 content is preserved in F6, that the R13 move happened, or that the envelope template carries `ROLE: WORKER` | B (pending Gap 26) |
| AC-R4/AC-R7 | plan structure valid | Fully-Automated | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <this plan>` -> 0 failures, 0 warnings (re-run 02-10-26, cycle 3) | A |
| AC-R4 (Gate 3) | README/guide sync | Fully-Automated | `node .claude/skills/vc-audit-vc/scripts/validate-guide-sync.mjs` -> baseline failure (1) accepted until Gate 5 (decision recorded in plan section 9) | C (decided: Gate 5) |
| AC-R4 (Gate 3) | CLAUDE.md and AGENTS.md carry one identical ENTRY-SET block | Fully-Automated | command C10 (verified on scratch files in cycle 3) | A |
| AC-R5 | registry reconciled against evidence | Hybrid | user review of registry vs plan section 3 + command C11 (prints MISSING for 11 IDs today, none after Gate 2); precondition: rev 6 base loaded | B |
| AC-R6 | nothing removed without approval | Hybrid | `## Approvals Log` in `process/archive/index.md` vs `git`/session state diff; empty log means no removal permitted | B (pending Gap 26: F8 row does not mention the log) |
| AC-R9 | token claims labelled measured/unmeasured | Hybrid | user review of Gate 3 report | A |
| AC-R1 | fresh PLANNER and WORKER sessions reach their task on their own entry set only | Agent-Probe | two fresh-session probes at Gate 3 | A (Gate 3) |
| AC-R10 | worker report carries all 11 headings | Fully-Automated | command C12 equals 11 (verified on a scratch fixture) against the template at Gate 2 and the pilot report at Gate 6 | A |
| AC-R7 | acceptance rule not satisfied by worker say-so | Agent-Probe | Gate 6 pilot report + registry history | C (Gate 6) |

Cycle-3 live run of the pinned commands (section 10, C1-C13), 02-10-26, HEAD b6651e2, clean tree:

| Command | Expected today (plan) | Observed | Match |
|---|---|---|---|
| C1 | 3 lines (20, 36, 48) | 3 lines (20, 36, 48) | yes |
| C2 | 2 lines (CLAUDE.md:50, AGENTS.md:56) | 2 lines | yes (but the pattern is narrow, Gap 29: 8 orchestrator-role lines exist today) |
| C3 | "cannot run to completion" | runs and PRINTS 234253 while `cat` errors twice on the missing north-star.md and current-state.md | NO: the plan note is inaccurate and the gate can under-count silently (Gap 29) |
| C4 | not runnable | fails at the first test (envelope missing) | yes |
| C5 | rc=1 (1,223 lines) | rc=1 | yes |
| C6 | prints the whole base set while F4 is absent; prints nothing once F4 is faithful | mechanics verified on a scratch F4: 0 lines faithful, exactly 1 line when one line is dropped | yes |
| C7 | context-discovery 1 failure, others 0 | context-discovery 1, skills 1, guide-sync 1, parity non-strict 0 failures / 18 warnings, wiring 0, discovery 0, portability 0, frontmatter 0, invocation-wiring 0, all-context 0, routing in sync | yes |
| C8 | 8 hits, all in all-context.md | 8 hits (95, 373, 446, 582, 910, 957, 962, 1020) | yes (widened pattern finds 11, Gap 28) |
| C9 | no output | no output (grep exit 1) | yes |
| C10 | exit 1 at the first test | exit 1 | yes |
| C11 | MISSING for T1 T1b T3 T4 T5 T7 T8 T23 T26 T27 T28 | exactly that list | yes |
| C12 | file absent today | grep: No such file, exit 2 | yes |
| C13 | no output, plan validator 0 failures | no output; 0 failures, 0 warnings | yes (but blind to untracked files, Gap 27) |

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
test("should keep plan inventory failures at the baseline after the R13 move", () => { throw new Error("NOT IMPLEMENTED - TDD stub: validate-plan-inventory failures stay 0") })
Failing stub:
test("should have no retired wording in entry points", () => { throw new Error("NOT IMPLEMENTED - TDD stub: retired wording absent") })
Failing stub:
test("should have no @-imports of large files in CLAUDE.md", () => { throw new Error("NOT IMPLEMENTED - TDD stub: no @-imports of large files") })
Failing stub:
test("should limit Gates 2-4 diff to process/ CLAUDE.md AGENTS.md", () => { throw new Error("NOT IMPLEMENTED - TDD stub: diff scope limited") })
Failing stub:
test("should find no whitespace errors or conflict markers in new untracked files", () => { throw new Error("NOT IMPLEMENTED - TDD stub: untracked-file whitespace check") })
Failing stub:
test("should have every Gate 2 deliverable present with its required parts", () => { throw new Error("NOT IMPLEMENTED - TDD stub: Gate 2 deliverable existence and content check") })

C-4 reconciliation: the `strategy` column carries only Fully-Automated / Hybrid / Agent-Probe. Known-Gap is never a strategy; it appears only as the named residuals below (gap-resolution D).

Legacy line form:
- all-context slimming: [Fully-automated: wc -l, validate-all-context, validate-context-discovery (baseline-aware), --check-routing]
- protocol docs: [Fully-automated: validate-protocol-wiring, validate-protocol-discovery, validate-kit-portability]
- entry files (Gate 3): [Fully-automated: @-import grep (C1), role-neutral grep (C2), wc -c tables (C3, C4), retired-wording grep (C8), ENTRY-SET diff (C10)] | [agent-probe: fresh-session probe per role]
- registry/archive: [hybrid: user review + git log/file-existence re-checks + C11]
- master planner lifecycle (Gate 6): [agent-probe: pilot task]
- worker self-merge conditions: [known-gap: platform enforcement unavailable, documented below, gap-resolution D]

Dimension findings (cycle 3):
- Infra fit: CONCERN - baseline re-confirmed; every cited path, branch SHA (pensive-dijkstra 18ffd4f, exciting-meitner 08cd839, split-all-context bf65024), CI job name (em dash, ci.yml lines 41 and 57), repo setting (private, allow_auto_merge false, branch protection unavailable on this plan, no permissions block in .claude/settings.json) and count (15 agents, 33 skills, 339 tracked `.agents/skills` files) verified. New: F14 and H2 say the `.gitignore` line for `web/tsconfig.tsbuildinfo` already exists; it does not (absent on main, HEAD and ui-shell, and `git log -S tsbuildinfo -- .gitignore` is empty), so `git rm --cached` alone leaves an untracked file after the next tsc run (Gap 25).
- Test coverage: CONCERN - the two role-based entry sets and their caps are arithmetically consistent and every cycle-2 command works as stated. Remaining: several Gate 2 deliverables (F1 F2 F3 F8, the F6 rev-6 preservation claim, the R13 move, the `ROLE: WORKER` envelope line, the backlog stubs, the Gate 2 byte record) have no pinned non-vacuous command (Gap 26); C13 is blind to untracked new files (Gap 27); C8 cannot see `public-later` and wrapped phrases and the F5 table keeps line 955 (Gap 28); C3 silently under-counts, C2 is narrow (Gap 29).
- Breaking changes: PASS - role-neutral CLAUDE.md breaks no validator, hook or agent (checked above); the literal `process/context/all-context.md` must stay in CLAUDE.md and AGENTS.md (validate-context-discovery), carried to Gate 3 as a requirement (Gap 30).
- Security surface: PASS (plan consistency) - enforcement facts re-verified live; compensating controls (i)-(vii) present; acceptance rule and standing authorization reconciled by the precedence sentence. Control-surface self-merge (Open Question 10) and the worker-lane confirmation are USER DECISIONS, non-blocking for Gate 2 start; standing consent for branch deletion remains NOT granted.
- Section 2 / Gate 2 file set (F1-F8, F11): CONCERN - mechanically feasible; F7 frontmatter, F4/F5 arithmetic, C6, C10 verified. Remaining: F5 row 955 (Gap 28); the Gate 2 order puts F5 before F1 although F5's summary is "written from north-star.md" (Gap 30); no file-set entry or check for the backlog stubs promised in Verification Evidence (Gap 26).
- Section 3 registry / R14 feasibility: CONCERN - rows and statuses verified against the branch; the test-tier labels T0-T4 (section 6, section 4 worker lane, AC-R1/Open Question 10 wording) collide with registry task IDs T1-T28 (T1, T3, T4 exist as tasks) (Gap 24).
- Section 4 lifecycle spec: PASS - acceptance rule (a)-(d), standing authorization (a)-(f), registry-writer rule (ii), worker lane and the verifiability consequence read consistently; no new contradiction found.
- R13 salvage: PASS - destinations, the 16-file list and the five removed `active/` copies match the branch diff exactly; the outcome check is part of Gap 26.
- Section 7 housekeeping H1/H2: CONCERN for H2 only (Gap 25); H1 commands unchanged and PASS.
- Items verified OK this cycle: F5 sum 288, router `sed` definition, 62.5 B/line, 144 lines / 7,709 bytes, planner and worker cap sums, F7 block-style vs flow-style on a scratch repo, C6 positive and negative, C10 three cases, C12 fixture, validate-kit-portability scope (product-name regex plus three-file survivor list), validate-context-discovery indexing rule (bare basename in the router is enough for root docs), the GENERATED routing block lists group entry points only (root docs never change it), validate-protocol-wiring basename rule, R13 file list, T-row counts, rev 6 labelling (Revision 6 present; T28 is a heading section, not a table row, which is fine because C11 checks the rebuilt registry).

Open gaps:
- real per-session token usage is unmeasured: known-gap: documented, backlog stub due at Gate 2 (gap-resolution D; the stub is not yet in the file set, Gap 26)
- symlinked `.agents/skills` on the user's Windows PC is unverified: known-gap: documented, backlog stub due at Gate 2 (gap-resolution D; Gap 26)
- R12 deploy runtime behaviour (PowerShell, Task Scheduler, Tailscale) verifiable only on the user's PC: known-gap: documented, hybrid user-run (gap-resolution D; Gap 26)
- MCP tool names named by the plan: unverifiable from this session; resolved by Gate 2 R4 step (vii) run by the orchestrator session (non-blocking, already in the plan's Gate 2 order)
- platform enforcement of self-merge conditions is unavailable on this repo plan: documented residual with compensating controls (done in cycle 1)
- USER DECISION, non-blocking for Gate 2 start: Open Question 10 (control-surface self-merge; T4 bypass; Master Planner merging on a worker's behalf); the worker lane as a direct lane with a compact self-written validate-contract (reported as needing the user's confirmation but not yet recorded in the plan's Open Questions, Gap 30); standing consent for branch deletion remains NOT granted
- orchestrator bookkeeping note (not a plan gap): `results.tsv` has no `# domain: plan` legend line, so validate-autoresearch-log.mjs reports "domain field must be exactly plan or tests"; sibling task folders have the same shape; the orchestrator adds the legend when it appends the cycle 3 row
- plan-text concerns Gaps 24-30 below (cycle 3 SUPPLEMENT REQUEST)

What this coverage does NOT prove (What This Coverage Does NOT Prove):
- wc -l / validate-all-context / validate-context-discovery: not that the slimmed all-context.md still contains every current-truth fact needed by agents (only structure, routing and line count), and not that nothing was lost from the kept sections (only the changelog block and the moved sections are covered by the preservation check; the check is set-based, so it does not prove order or duplicate-line counts)
- validate-protocol-wiring / validate-protocol-discovery / validate-kit-portability: not that master-planner.md content is correct or that its rules are mechanically enforceable
- baseline-aware validator gates: not that the 18 agent-parity warnings or the `.agents/skills` failure are harmless; they only prove no regression
- @-import grep, role-neutral grep and wc -c: not that a fresh Claude session actually follows the new entry set or behaves as a worker (only the two Gate 3 agent-probes show that) and not real token usage
- retired-wording grep: not that the North Star content is correct, only that the listed phrases are absent from the named files (a synonym or a wrapped phrase passes)
- scope check (C9): not that the contents of process/ files are accurate
- registry hybrid review and C11: not that every UNVERIFIED T-row is true; C11 proves an ID has a row, not that its status or evidence is right
- `git diff --check` as written: not that new untracked files are clean (Gap 27)
- none of the gates proves that a worker honours the standing-authorization conditions; they are procedure, not platform controls, until a pilot (Gate 6) and a post-merge audit are in place

SUPPLEMENT REQUEST (PVL cycle 3; exact items; section ids are slugs of `##`/`###` headings in this plan; all are plan-text edits, none needs the user):
- Gap 24: 6-risk-based-test-policy (tier labels) + 4-master-planner-lifecycle-spec (worker lane, precedence note) + 10-acceptance-criteria-this-program (AC-R1 area) + 13-open-questions (item 10) + blast-radius | Concern: the test tiers are named T0-T4 while the registry task IDs are T1-T28 and "keep historical T#"; T1 (pytrends zeros), T3 (narrative-v2) and T4 (Reddit secrets) are real tasks. "T4" in section 4, section 6, Open Question 10(a) and the worker lane ("T0/T1") is ambiguous, and a registry row's `Test req/budget` column would hold a tier label that reads as a task ID. Gap 19 removed the P-ID collision but left this one | Severity: CONCERN | Suggested addition: rename the tiers to a prefix that collides with no ID scheme in the plan (for example RT0-RT4 for "risk tier", NOT L-anything because L is a Prio value and NOT P/Q/R/F/H/C), apply it at every occurrence (section 4 precedence note and worker lane, section 6 table and budget rule, Open Question 10(a), blast-radius line, Section 5 if present), and state once that T# means a registry task and RT# a risk tier
- Gap 25: 2-exact-file-set (F14) + 7-housekeeping-candidates-no-deletion-on-static-search-alone (H2) + touchpoints | Concern: F14 says the `.gitignore` line `web/tsconfig.tsbuildinfo` already exists. It does not: the line is absent on main, on HEAD and on ui-shell, and `git log -S tsbuildinfo -- .gitignore` is empty; `web/tsconfig.tsbuildinfo` is tracked (171,544 bytes). `git rm --cached` alone would leave an untracked file that every tsc run recreates and `git status` would show it (and C9-style scope checks would see it) | Severity: CONCERN | Suggested addition: F14 = `git rm --cached web/tsconfig.tsbuildinfo` PLUS add the line `web/tsconfig.tsbuildinfo` to `.gitignore` (shared file: single owner at Gate 5, listed in the Gate 5 touchpoints and the Gate 5 C9 form), remove the false parenthetical, and make H2 say "untrack and ignore"
- Gap 26: 10-acceptance-criteria-this-program (new pinned command C14) + 2-exact-file-set (F6, F8, new F15) + verification-evidence + 9-gate-roadmap (Gate 2 row) + touchpoints | Concern: Gate 2 deliverables with no non-vacuous pinned command: (a) F1, F2, F3, F8 existence (a missing north-star.md only makes C8 print a stderr line; C8 only proves absence of old phrases, not that the North Star exists with personal-use, data-not-verdicts, Tailscale-only, page list, non-goals); (b) F8's `## Approvals Log` heading and the R13 row (the F8 row never mentions the log although AC-R6 depends on it); (c) the F6 claim "nothing from rev 6 is dropped, only relocated" (about 500 lines) has no preservation command, unlike the changelog (C6), and rev 6 is the HIGH PRIORITY unmerged item; (d) the R13 move outcome (`active/lse-data-verification_17-09-26` gone, `completed/` copy present); (e) the `ROLE: WORKER` first line in the envelope template inside master-planner.md (the whole worker design rests on it; C12 only counts report headings); (f) Verification Evidence says backlog stubs for the three known gaps are "written at Gate 2" but no file-set row, touchpoint or check exists for them (vacuous-green ban requires the stub); (g) "measured bytes of F1, F2, F6 and the F5 router section are recorded" has no pinned command | Severity: CONCERN | Suggested addition: add command C14 in the section 10 fenced block with expected-today output, covering at least: `test -s` on north-star.md, current-state.md, decisions.md, context-changelog.md, master-planner.md, process/archive/index.md and process/archive/master-plan-revisions_02-10-26.md (print MISSING per file; today all 7 print MISSING); `grep -c '^## Approvals Log' process/archive/index.md` equals 1 and the log has a row naming lse-data-verification; `grep -c 'ROLE: WORKER' process/development-protocols/master-planner.md` at least 1; north-star.md contains the five required topics (one `grep -ciE` per topic, each at least 1); R13 outcome (`test -d` on the `completed/` folder and `test ! -d` on the `active/` one); F6 preservation as a `comm -23` of `git show <rev6-sha>:process/MASTER-PLAN.md` (record `git rev-parse origin/claude/pensive-dijkstra-ko69oi`, today 18ffd4f01..., at Gate 2 start) against the sorted union of the new MASTER-PLAN.md and the archive file, filtered so only re-expressed registry rows (`| T`, `| P` lines) may remain, expected no other output (verify positive and negative on a scratch copy as was done for C6); a `wc -c` line printing F1, F2, F6 and the F5 router-section bytes for the Gate 2 report. Add F15 (three backlog stub notes under `process/general-plans/backlog/`, named, `_NOTE_02-10-26.md`) to the file set and touchpoints, add a `test -s` per stub to C14, name C14 and C11 in the Gate 2 row of section 9 and in Verification Evidence, and extend the F8 row with the `## Approvals Log` section
- Gap 27: 10-acceptance-criteria-this-program (command C13) + 9-gate-roadmap | Concern: `git diff --check` ignores untracked files and checks only unstaged changes, so it is a vacuous pass for every new Gate 2 file (north-star.md, current-state.md, decisions.md, context-changelog.md, master-planner.md, process/archive files), the very files most likely to carry trailing whitespace or marker lines (demonstrated on a scratch repo: a new file with trailing whitespace and a `<<<<<<<` line leaves `git diff --check` at exit 0) | Severity: CONCERN | Suggested addition: add a second line to C13: `for f in $(git ls-files --others --exclude-standard); do git diff --check --no-index /dev/null "$f"; done` (verified: prints nothing for a clean file, prints the offending lines for a bad one; the exit code is 1 for any added file so the gate is "no output", not the exit code) and, because staged-only changes (for example a `git mv`) are also missed, add `git diff --cached --check`; state expected no output
- Gap 28: 10-acceptance-criteria-this-program (command C8, AC-R3) + 2-exact-file-set (F5 disposition table, Open Decisions row) | Concern: C8 cannot see (1) the hyphenated form `public-later` and (2) phrases that wrap across a line (`open it to` / `other users later` at lines 580-581). All-context.md line 955 (the Equity data provider row of Open Decisions, a KEPT section) says "collides with the public-later goal"; the F5 table drops lines 957 and 962 but not 955, so Gate 2 would pass C8 while a retired concept survives, contradicting AC-R3's own text ("old confidence/public-later/redistribution wording gone"). The same row and the Deployment-target row ("still deliberately deferred") are stale facts anyway (LSE verdict and deploy path are resolved in the plan) | Severity: CONCERN | Suggested addition: widen C8 to `public[ -]later|open up later|other users later|intended to open` in addition to the current alternatives (verified today: 11 hits in all-context.md, lines 95, 373, 446, 581, 582, 910, 955, 957, 962, 964, 1020), update the "8 hits today" statements to the new count in C8, AC-R3 and the C8 retired-wording subsection, add line 955 (and the stale Deployment-target row) to the F5 Open Decisions disposition as dropped or reworded without the retired phrase, and note that history survives only in context-changelog.md
- Gap 29: 10-acceptance-criteria-this-program (commands C2, C3) | Concern: (a) C3 is described as "cannot run to completion today" but it runs and prints 234253 because a failing `cat` of a missing file only writes to stderr and `wc -c` still succeeds, so at Gate 3 a missing or misnamed input silently under-counts and still looks under the cap; the gate also has no pass/fail test (it only echoes); (b) C2 greps one phrase while CLAUDE.md line 59 `**You do NOT**:`, line 52 `Your responsibilities:`, the heading `Orchestrator Role` (CLAUDE.md:46, AGENTS.md:50, :58, :65) are the other orchestrator-flavoured lines the plan itself calls out | Severity: CONCERN | Suggested addition: C3: assert each input with `test -s` first (print MISSING and stop) and finish with `test "$total" -le 64000; echo rc=$?`; correct the expected-today note ("prints 234253 with two missing-file errors today, which is why the file check is first"); C2: use `grep -nE 'You are the orchestrator|You do NOT|Your responsibilities|Orchestrator Role' CLAUDE.md AGENTS.md` (8 lines today: CLAUDE.md 46, 50, 52, 59 and AGENTS.md 50, 56, 58, 65, run in cycle 3), expected no output after Gate 3, noting that the role-scoped sentence the plan keeps must avoid these literals
- Gap 30: bundle of small consistency fixes | Concern: (a) Gate 2 order runs F5 before F1, but F5's "What This Project Is" row says the 3-line summary is "written from north-star.md" (a dependency on a file not yet written); (b) the Gate 2 row of section 9 omits C11 although Verification Evidence and AC-R5 rely on it at Gate 2; (c) the router-section budget is "~87 lines" in the definition paragraph but the table rows through Task Routing Table sum to 90 (15+3+10+15+25+22); (d) section 5 says Scan Metadata is 56 lines, measured 57 (lines 1167-1223); (e) the worker lane (direct lane, compact self-written validate-contract, QUICK FIX only for tiny tasks, one vc-quick-fix-agent spawn versus the Role Selection text "do not spawn subagent chains") was reported as needing the user's confirmation but is not listed in Open Questions, so the user will not see it; (f) validate-plan-inventory.mjs is not in the baseline table or C7 although Gate 2 moves a plan folder (baseline 0 failures, 6 warnings); (g) validate-context-discovery requires the literal `process/context/all-context.md` in both CLAUDE.md and AGENTS.md (assertContains), which the F9/F10 rewrite must keep (kit-portability allows it) but the plan never states | Severity: CONCERN | Suggested addition: (a) put F1, F2, F3 before F5 in the Gate 2 order (they do not touch all-context.md) or say the summary is written from the SPEC sources and reconciled with north-star.md afterwards; (b) add C11 to the Gate 2 row; (c) change "~87" to 90 or adjust the table; (d) 57; (e) add Open Question 12 "OPEN, user decision, non-blocking for Gate 2 start: confirm the worker lane as a direct lane with a compact self-written validate-contract and clarify that one vc-quick-fix-agent spawn for a tiny task is not a subagent chain"; (f) add the validator to C7 with its baseline; (g) add the literal-path requirement to the F9/F10 rows and to C7's Gate 3 note

Plan updates applied (PVL cycle 1, 02-10-26; verified against the live repo in cycles 2 and 3):
- Gap 1: baseline table and README scope recorded in section 9; all validator gates read 'no NEW failure vs baseline'; parity uses non-strict. Supersedes the `--strict` wording in the cycle-0 C3 table and Verification Evidence. VERIFIED.
- Gap 2: F4 defined, F5 disposition table (288 of 300 lines) and required headings added, `comm -23` command pinned, validate-all-context and --check-routing added to Gate 2; '>=65%' corrected to ~44% lines / ~48% bytes. VERIFIED (cycle 3: sum 288, C6 positive and negative).
- Gap 3: F9 removes the three `@`-imports; CLAUDE.md/AGENTS.md disposition table added; TL;DR and entry-set arithmetic corrected (the 43-48 KB figure was later withdrawn in cycle 2). VERIFIED.
- Gap 4: portability rule added (bare names/links, no allowlist widening); kit-portability at Gates 2 and 3. VERIFIED.
- Gap 5: F11 moved to Gate 2; F7 frontmatter specified. VERIFIED.
- Gap 6: ENTRY-SET byte-identical block and diff drift check defined; AGENTS.md symlink statement corrected (AGENTS.md lines 11, 420 and 674). VERIFIED.
- Gap 7: T26, T27, T28 added; F6 preservation rule (archive file) added. VERIFIED (preservation command still missing, Gap 26).
- Gap 8: 'Enforcement and compensating controls' subsection (i)-(vii) added; registry-writer contradiction resolved (planner only); control-surface residual recorded as a recommendation awaiting the user's explicit acceptance (Open Questions item 10). VERIFIED.
- Gap 9: worker consent, lane, per-task validate-contract and commit-policy exception rules added to section 4 and F7. VERIFIED.
- Gap 10: staleness rule redefined (ancestor check + non-chore commit threshold). VERIFIED.
- Gap 11: R13 TAKE/DROP list, Gate 2 order, F14 as `git rm --cached` only. VERIFIED (F14's `.gitignore` claim is wrong, Gap 25).
- Gap 12: H1 exact commands and `core.symlinks` precondition added. VERIFIED.
- Gap 13: AC-R1 numeric cap, AC-R3 extended case-insensitive grep, AC-R6 approvals-log location, AC-R8 base SHA, AC-R10 11-heading grep added. VERIFIED in cycle 3.

Plan updates applied (PVL cycle 2, 02-10-26, vc-plan-agent PVL-supplement; every changed command was run read-only; RE-VERIFIED by vc-validate-agent in cycle 3, see the cycle-2 re-verification table above):
- Gap 14: all gate commands moved into the fenced block in section 10 (C1-C13); AC-R1 command prints 3 lines today, AC-R3 prints 8 hits today. VERIFIED.
- Gap 15: AC-R8 is `git status --porcelain | cut -c4- | grep -vE '^process/'` (C9). VERIFIED.
- Gap 16: entry-set arithmetic restated; two role-based entry sets (PLANNER <= 64,000, WORKER <= 36,000); router section defined mechanically; role-neutral CLAUDE.md/AGENTS.md, Role Selection paragraph, `ROLE: WORKER` envelope. VERIFIED (small residuals in Gaps 29, 30).
- Gap 17: F5 drops lines 910, 957, 962 and reworks 582; ranges recomputed at Gate 2 start. VERIFIED (line 955 survives, Gap 28).
- Gap 18: F7 frontmatter block-style. VERIFIED on a scratch repo in cycle 3.
- Gap 19: `Prio (H/M/L)`. VERIFIED (tier-label collision remains, Gap 24).
- Gap 20: acceptance rule (b) counts CI; precedence sentence; T4 row. VERIFIED.
- Gap 21: C10 marker-count assertion. VERIFIED (three cases).
- Gap 22: C12 against the template at Gate 2 and the pilot report at Gate 6. VERIFIED.
- Gap 23: (a)-(f) accuracy fixes. VERIFIED.
- Additional verified fact recorded (orchestrator session, 02-10-26): the claude-code-remote session tools and the GitHub merge tools are in the Master Planner (orchestrator) session's tool list and not visible to vc-* subagents; Gate 2 step R4 (vii) runs in the orchestrator session. Consistent with what this validate session can see (no session or merge tools).

Plan updates applied (PVL cycle 3, 02-10-26, vc-plan-agent PVL-supplement; every new or changed command was run read-only, positive and negative cases on scratch copies; NOT yet re-verified by vc-validate-agent, which re-runs from V1 as cycle 4):
- Gap 24: risk tiers renamed RT0-RT4 at every occurrence outside this contract's history (section 4 precedence note and worker lane, section 6 table and budget rule, Open Question 10(a), Blast Radius); naming rule stated in section 3 and section 6 (T# = registry task, RT# = risk tier); `L` not used (it is a Prio value).
- Gap 25: F14 = `git rm --cached` PLUS adding `web/tsconfig.tsbuildinfo` to `.gitignore` (verified absent today); false parenthetical removed; H2, Touchpoints and a Gate 5 form of C9 updated.
- Gap 26: command C14 added (deliverable existence, `## Approvals Log` with an lse-data-verification row, `ROLE: WORKER`, five north-star topics, R13 outcome, rev 6 preservation pinned to 18ffd4f014f4e5ea0f5d654688875a9300b30ab4, informational byte lines); expected today 10 MISSING + 10 FAIL + 210 comm lines; positive and negative verified on a scratch tree; F15 (three backlog stubs) added to the file set, Touchpoints and C14; F8 row extended with the Approvals Log; Gate 2 row and Verification Evidence name C11 and C14.
- Gap 27: C13 now also runs `git diff --cached --check` and the untracked-file loop; the gate is "no output"; verified on a scratch repo.
- Gap 28: C8 widened (`public[ -]later|open up later|other users later|intended to open`): 11 hits today (lines 95, 373, 446, 581, 582, 910, 955, 957, 962, 964, 1020); every "8 hits" statement outside this contract's history updated; line 955 (Equity data provider row), the stale Deployment target row (line 959) and lines 962-964 added to the F5 drop/reword list.
- Gap 29: C3 asserts each input with `test -s`, ends with `test "$total" -le 64000; echo rc=$?`, expected-today note corrected (240454 / rc=1, not "cannot run"); C2 widened to `You are the orchestrator|You do NOT|Your responsibilities|Orchestrator Role` (8 lines today).
- Gap 30: (a) Gate 2 order now F1, F2, F3 before F4 and F5; (b) section 9 Gate 2 row names C11, C13, C14; (c) router budget 90 lines (sum of table rows); (d) Scan Metadata 57 lines; (e) Open Question 12 added (worker lane confirmation, non-blocking); (f) validate-plan-inventory.mjs added to C7 and the baseline table (0 failures, 6 warnings); (g) F9/F10 rows and C7 require the literal `process/context/all-context.md` (counts today 9 and 12).

Gate: CONDITIONAL (0 FAILs, 7 CONCERNs (Gaps 24-30, all plan-text); PVL cycle 3; EXECUTE of Gate 2 is not legal yet; PHASE_COMPLETE: VALIDATE is NOT emitted; routes to PVL supplement cycle 3 then a re-spawn of vc-validate-agent from V1)
Accepted by: none yet. No concern has been accepted by the user. Acceptance, if any, is recorded after the next supplement cycle (or by explicit user acceptance), listing each accepted concern by name. User decisions pending but non-blocking for Gate 2 start: Open Question 10 (control-surface self-merge; T4 bypass; Master Planner merging on a worker's behalf); the worker-lane confirmation; standing consent for branch deletion.

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
Next phase: PVL supplement cycle 3 applied (Gaps 24-30); re-spawn vc-validate-agent from V1 (cycle 4); after Gate: PASS: EXECUTE Gate 2 via vc-execute-agent (opus), scoped to F1-F8 + F11 + R13 + R14
Validate contract: inline in plan (## Validate Contract)
Execute start: wc -l all-context <=300 | validate-context-discovery (failures == baseline) | validate-all-context | discover-context --check-routing | validate-protocol-wiring | validate-protocol-discovery | validate-kit-portability | validate-agent-parity non-strict | git diff --check | retired-wording grep | e2e spec: none | probe: none until Gate 3 | high-risk pack: no (Gate 5 R12 only)

## Resume and Execution Handoff

1. Selected plan: `/home/user/psychic-train/process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md`
2. Last completed step: PVL cycle 3 validate (re-run from V1 after the cycle-2 supplement of Gaps 14-23): Gaps 14-23 verified closed live; 7 new plan-text concerns (Gaps 24-30). No implementation. Working tree: plan file edits only.
3. Validate-contract: written 02-10-26 (cycle 3), Gate: CONDITIONAL, 0 FAIL, 7 CONCERN (Gaps 24-30, see its SUPPLEMENT REQUEST). PVL supplement cycle 3 is applied (Gaps 24-30); next: re-spawn vc-validate-agent from V1 (cycle 4).
4. Context loaded: CLAUDE.md, all-context.md, orchestration.md, MASTER-PLAN.md (full), realignment SPEC (AC grep), repo branch list.
5. Next step: ENTER VALIDATE MODE (all questions resolved); then Gate 2 via vc-execute-agent (opus) scoped to F1-F8 plus R13 and R14; start MASTER-PLAN work from `pensive-dijkstra` rev 6; re-verify every remaining UNVERIFIED registry item first.

## Phase Completion Rules

- A gate is complete only when its Verification Evidence rows are green and recorded with command, timestamp, and commit SHA.
- Status words: `PROPOSED` (this plan), `CODE DONE` (files written, not independently verified), `VERIFIED` (independent re-run, e.g. spawned vc-tester or user). Known-gap alone never yields VERIFIED.
- No gate starts before VALIDATE writes a contract for it and the user approves; archive/delete/session-termination steps need separate explicit approval.
