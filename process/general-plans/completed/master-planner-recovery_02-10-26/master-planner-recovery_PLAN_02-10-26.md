---
name: plan:master-planner-recovery
description: "GATE 1 design proposal: recover project truth, collapse memory into one routed system, slim default session load, add Master Planner task registry + worker lifecycle, risk-based test policy, housekeeping and deploy-path findings. Proposal only; no implementation."
date: 02-10-26
feature: general-plans
---

# Project Recovery, Architecture Cleanup, AI Efficiency and Master Planner Orchestration — GATE 1 Proposal

Date: 02-10-26
**Gate 4 executed (03-10-26; report: `master-planner-recovery_GATE4-REPORT_03-10-26.md`); independent EVL and UPDATE PROCESS pending.** Gate 3 complete (03-10-26; report: `master-planner-recovery_GATE3-REPORT_03-10-26.md`). Gate 2 report: `master-planner-recovery_GATE2-REPORT_03-10-26.md`. Historical status line follows.
Status: PROPOSED, Gate 1 approved (all user answers 02-10-26 recorded below; Q1-Q8 resolved). Nothing here is executed. PVL cycle 4 validate (02-10-26) found Gaps 24-30 closed and the user diagram revision sound apart from two plan-text concerns (Gaps 31-32, see the Validate Contract); the PVL supplement cycle 4 applies them and vc-validate-agent re-runs from V1 (cycle 5) and must write a passing contract (or the user must accept the remaining gaps) before any Gate 2 write. Working tree: plan file edits only (this file); no other file touched.
Complexity: COMPLEX (single plan, gated roadmap Gate 2..6; each gate re-enters VALIDATE).

## Status of this plan

**Current (03-10-26): Gate 4 complete; Gate 5 requires VALIDATE then explicit ENTER EXECUTE MODE.** Gate 4 (G4-K1 = A, installs run once) was executed and independently confirmed by vc-tester (EVL iteration 002, all gates green at cycle 0); report `master-planner-recovery_GATE4-REPORT_03-10-26.md`; commits `ee72237`, `753db23`, `cc0c7f6`, `253f703`, `a96d7b3`, `d09d92e`, `0004d5b` plus the closeout commits. The Gate 4 contract is CONSUMED. R8 stays `review` (CI on the newest head and the user's acceptance still pending); AC-R5, AC-R6 and AC-R9 await the user's review. Gates 5-6 remain, so the plan stays in `active/`. Previous: Gate 3 complete. Gate 3 (role-neutral CLAUDE.md and AGENTS.md, shared ENTRY-SET block) was executed, independently confirmed (one fix cycle) and accepted by the user (03-10-26); commits `eee7709`, `0b3c9bf`; report `master-planner-recovery_GATE3-REPORT_03-10-26.md`. Gates 4-6 remain, so the plan stays in `active/`. The Gate 3 contract below is CONSUMED (it gated the start of Gate 3 only). Superseded status follows: **Gate 2 complete; Gate 3 requires VALIDATE then explicit ENTER EXECUTE MODE.** Gate 2 independent EVL (vc-tester) all green; validators equal baseline; AC-R5 and AC-R6 await the user's hybrid review (not accepted). Gates 3-6 remain, so the plan stays in `active/`. Paragraph below is the pre-Gate-2 history.

Gate 1: approved (02-10-26). Q1-Q8 are all resolved (user answers, section 13); Q4 and Q8 are now Resolved. PVL cycle 5 validate is done (03-10-26): Gate: PASS, 0 FAIL, 0 unresolved CONCERN (Gaps 1-32 all closed; only cosmetic leftovers remain, listed in the Validate Contract). The contract gates the START of Gate 2 only; Gates 3-6 each re-enter VALIDATE. User decisions Open Question 10 and Open Question 12 are non-blocking for Gate 2 start. The user diagram revision (02-10-26: four user answers on the target-workflow diagram) was verified in cycles 4 and 5; see the verification tables in the Validate Contract section. Working tree: only this plan file was edited by validation.

## TL;DR

- Today every session loads ~200 KB (~50k tokens) before work starts, driven by three `@`-imports in CLAUDE.md (all-context.md, all-development-protocols.md, orchestration.md). In all-context.md the changelog block is ~44% of lines and ~48% of bytes (536 of 1,223 lines, 45 KB of 93.7 KB); with Open Questions, References and Scan Metadata the non-durable share is higher. Target: TWO role-based entry sets, reached by moving history out of default load, not by deleting it. PLANNER (Master Planner or interactive session) <= 64 KB provisional (typical 50-58 KB, about a 71-74% cut); WORKER <= 36 KB (CLAUDE.md <= 20 KB + task envelope <= 8 KB + task file <= 8 KB; typical ~30 KB, about an 85% cut; 43 KB when the envelope names operating-instructions.md). The earlier 43-48 KB figure is withdrawn: it budgeted the all-context router at 40 bytes/line, but the kept sections measure 62.5 bytes/line. Tokens are bytes/4, approximate.
- No new doc system. Reuse `process/context/` + `all-context.md` routing, RIPER-5 task folders, `results.tsv`, closeout packets, `completed/` archival. Promote the existing, unreferenced `process/MASTER-PLAN.md` to the ONE task board and registry.
- Add only eight small things: `north-star.md`, `current-state.md`, `decisions.md`, `architecture.md` and `operating-instructions.md` (the last two are carved out of all-context.md so it can stay a router), `process/archive/index.md`, a worker envelope template and a report template.
- Master Planner never marks a task `accepted` on a worker's word: acceptance needs independent evidence (CI, a spawned vc-tester, or the user) recorded in the registry. Under the user's standing authorization (section 4, "no exceptions", including high-risk classes) a worker may self-merge and self-archive only when every mechanical safety condition holds and it is sure; a worker that is unsure, or whose conditions cannot be verified from the cloud container or CI, stops at `review`.
- Workers do not inherit the planner's context: every new session loads CLAUDE.md by itself, and today CLAUDE.md says "You are the orchestrator, not the worker" (AGENTS.md line 56 likewise), so a worker would orchestrate with full RIPER-5 ceremony. CLAUDE.md becomes role-neutral; orchestrator rules move to master-planner.md; the worker envelope starts `ROLE: WORKER` and overrides orchestrator wording. Only the Master Planner session has the session and merge tools (verified 02-10-26; vc-* subagents do not).
- Four archive operations stay separate: archive docs, mark logically complete, archive a session (allowed only after the handover report is durable and merge verified), delete a branch/worktree (user standing consent granted 02-10-26, scoped to merged worker task branches only, after the merge is verified, the report is committed and the registry says `accepted` then `archived`; every other branch still needs per-branch user approval).
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
| Test policy | `tests/all-tests.md` | MODIFY (link to the risk tier table that lives in operating-instructions.md; fix stale counts) | Already the test router |
| Architecture reference | repo layout, stack and patterns inside all-context.md | NEW `process/context/architecture.md` (carved out of all-context.md; diagram box 'Project Context: essential architecture') | Keeps all-context.md a router; user answer 4, 02-10-26 |
| Operating instructions | dev/test/build/deploy commands, worktree/merge rules scattered over all-context.md, all-tests.md, CLAUDE.md | NEW `process/context/operating-instructions.md` (diagram box 'Project Context: dev commands, testing rules, worktree/merge rules') | One short doc a worker opens only when the envelope names it; user answer 4, 02-10-26 |

## 2. Exact File Set

| # | Path | Action | Size target | Gate |
|---|---|---|---|---|
| F1 | `process/context/north-star.md` | create | ~100 lines (~4 KB); written in new wording (personal use, data not verdicts, Tailscale-only, page list, non-goals) that avoids every phrase checked by command C8 | 2 |
| F2 | `process/context/current-state.md` | create | ~80 lines (~4 KB), every fact stamped (branch, commit, UTC time, command) | 2 |
| F3 | `process/context/decisions.md` | create | index ~60 lines; fields: decision / date / reason / alternatives / consequences / status active-or-superseded | 2 |
| F4 | `process/context/context-changelog.md` | create (move) | the changelog block (base all-context.md, today lines 33-568, 536 lines / 45 KB; the range is recomputed with `grep -n '^## '` at Gate 2 start, never hard-coded) PLUS the moved Open Questions, References and Scan Metadata sections, whole and unedited, under one `# ` title and a short header; NOT in default load; defined in the F4/F5 subsection below | 2 |
| F5 | `process/context/all-context.md` | modify | <= 300 lines cap, planned 198 per the F5 disposition table below (from 1,223; about 12-13 KB at the measured 62.5 bytes/line; the planner entry set loads only its router section, defined in the entry-set subsection); mostly routing: layout, stack, patterns and environment detail are carved out to F16/F17 and stay here only as short summaries with links under the validator-required headings; keep routing and open decisions; replace history with one-line pointers to F4; required headings and routing block listed below | 2 |
| F6 | `process/MASTER-PLAN.md` | modify | ~250 lines: registry table, lifecycle summary, lane table, reconciled T-list; built FROM rev 6 (R14); all superseded revision text (rev 1-6 narrative, ~500 lines) is moved whole to `process/archive/master-plan-revisions_02-10-26.md` (created in Gate 2, linked from F8) - preservation rule: nothing from rev 6 is dropped, only relocated; checked by command C14 against the pinned rev 6 commit 18ffd4f014f4e5ea0f5d654688875a9300b30ab4 (record `git rev-parse origin/claude/pensive-dijkstra-ko69oi` at Gate 2 start; if the tip has moved, the user decides which revision is the base) | 2 |
| F7 | `process/development-protocols/master-planner.md` | create | ~200 lines: lifecycle, acceptance rule, envelope, report schema, isolation, archival semantics (including the scoped branch-deletion standing consent of 02-10-26), worker lane + commit-policy rules (section 4); frontmatter exactly: `name: protocol:master-planner`, `description: ...`, `date: 02-10-26`, block-style nested metadata exactly as in autopilot.md: a line `metadata:` followed by five two-space-indented lines `node_type: protocol`, `type: protocol`, `read_order: 10`, `required: false`, `read_when: "Master Planner posture or worker spawn"` (validate-protocol-discovery does NOT parse a flow-style `{...}` map: verified 02-10-26 on a scratch repo, it fails with metadata.required and metadata.read_when missing). The file also holds the Master Planner posture section (the orchestrator rules moved out of CLAUDE.md) and the report template, whose 11 headings are written as `## 1 Task ID` ... `## 11 Context cost` and used nowhere else in the file (command C12 counts them); the worker envelope template inside it starts with the literal line `ROLE: WORKER` (command C14 checks it) | 2 |
| F8 | `process/archive/index.md` | create | table by date/task/status/branch/commit/location; grows by row; ALSO a `## Approvals Log` section (exactly one such heading; one row per approval: date, what, approver quote; Gate 2 writes the row for the R13 move naming `lse-data-verification_17-09-26` with the user's Q4 answer of 02-10-26 as the quote, AND a row for the branch-deletion standing consent (date 02-10-26, scope: merged worker task branches only, quote: the user's answer 'delete merged task branches after verified merge and saved report'); every later automatic deletion adds one row (date, branch, merge SHA, report path, 'standing consent 02-10-26'); command C14 checks both Gate 2 rows) | 2 |
| F9 | `CLAUDE.md` | modify | session-start section rewritten to the short entry set; REMOVE the three `@`-imports (all-context.md line 20, all-development-protocols.md lines 20 and 36, orchestration.md line 48) - AC-R1 fails otherwise; follow the section disposition table below; target <= 20 KB (from 28.9 KB); ROLE-NEUTRAL (the Orchestrator Role section is removed from it; orchestrator rules move to master-planner.md with a short role-selection pointer left behind); contains the shared ENTRY-SET block listing both entry sets and naming architecture.md and operating-instructions.md as on-demand docs (bare name or markdown link only, never a backticked `process/context/<file>` path); the rewrite MUST keep the literal `process/context/all-context.md` (validate-context-discovery requires it in both CLAUDE.md and AGENTS.md; validate-kit-portability allows it) | 3 |
| F10 | `AGENTS.md` | modify | same entry-set rewrite via the byte-identical ENTRY-SET block (drift check below), <= 20 KB (from 37.9 KB, 704 lines), with the same role-neutral rewrite (the sentence "You are the orchestrator, not the worker" at AGENTS.md line 56 goes); the false statement that `.agents/skills` is a symlink is corrected to: tracked copy until H1 lands; keeps the literal `process/context/all-context.md` as in F9 | 3 |
| F11 | `process/development-protocols/all-development-protocols.md` | modify | add master-planner.md row listed by basename (validate-protocol-wiring); mark orchestration.md as on-demand, not default; moved to Gate 2 with F7 | 2 |
| F12 | `process/context/tests/all-tests.md` | modify | link to the RT0-RT4 table in operating-instructions.md (single home; section 6 content is written there at Gate 2), re-confirm its commands against all-tests.md and fix stale counts after measured re-run | 4 |
| F13 | `README.md` (root) | create | ~60 lines: start API/web, runbook pointers | 5 |
| F14 | `web/tsconfig.tsbuildinfo` and `.gitignore` | untrack AND ignore: `git rm --cached web/tsconfig.tsbuildinfo` (file still tracked, 171,544 bytes) PLUS add the line `web/tsconfig.tsbuildinfo` to `.gitignore` (the line is absent today on main, HEAD and ui-shell; `git log -S tsbuildinfo -- .gitignore` is empty, so untracking alone would leave an untracked file that every tsc run recreates). `.gitignore` is a shared file: this lane is its single owner at Gate 5; approval required | 1 line added | 5 |
| F15 | `process/general-plans/backlog/token-usage-telemetry_NOTE_02-10-26.md`, `process/general-plans/backlog/agents-skills-symlink-windows_NOTE_02-10-26.md`, `process/general-plans/backlog/deploy-runtime-user-pc-verification_NOTE_02-10-26.md` | create three backlog stubs, one per known gap named in Verification Evidence: real per-session token usage (unmeasured); behavior of a symlinked `.agents/skills` on the user's Windows PC; R12 deploy runtime behavior verifiable only on the user's PC; each ~10-15 lines (what is unproven, why, how to close it); required by the vacuous-green ban | ~3 x 1 KB | 2 |
| F16 | `process/context/architecture.md` | create (carved out of F5's Repository Structure, Technology Stack and Key Patterns) | ~120 lines (~7 KB): repo layout (web/, api/, process/, deploy/, workflows); runtimes and boundaries (Next.js/React app, Svelte chart islands, FastAPI, and why two runtimes); a `## Data flow` section (providers -> adapters -> cache.py Parquet/DuckDB -> analytics -> routers -> web); key patterns and invariants rewritten for the new North Star (one source of numerical truth, providers behind adapters, free tiers as a constraint, numbers never silently wrong; the confidence-over-direction paragraph is dropped, not carried); links to deeper docs on demand (north-star.md, the data-sources group, feature guides); avoids every phrase checked by command C8 | 2 |
| F17 | `process/context/operating-instructions.md` | create (carved out of F5's Environment and Configuration, all-tests.md commands and CLAUDE.md rules) | ~120 lines (~7 KB): dev/test/build/deploy commands (api via uv, web via pnpm, build:islands, Playwright, the `deploy/` scripts, home PC + Tailscale); env and config names (from `.env.example`); the risk-tier test rules as the five-row table RT0-RT4 from section 6 (single home; Gate 4 re-confirms its commands against all-tests.md); worktree/branch/merge rules (worker branches `claude/<task-id>-<slug>`, commit policy with the worker exception, self-merge conditions summarized with a link to master-planner.md, worktrees only on the user's PC); a short session start/end checklist that links to master-planner.md instead of duplicating its rules; avoids every phrase checked by command C8 | 2 |

Home decision for the registry: inside `process/MASTER-PLAN.md`. Justification: it already exists, already carries T1..T25, lanes and the 3-lane cap, and is the file sessions already cite informally. A sibling file would give two boards. Risk: it is a large file; mitigation: registry holds one row per task (<= 3 lines), details live in each task folder.

Orchestration.md (71 KB) stays unchanged this program; it is moved out of the default load by routing, not by editing. Slimming it is a candidate follow-up task (see registry R-5), unmeasured.

### Diagram mapping and context split (user diagram, 02-10-26)

The diagram's 'North Star' box is north-star.md (F1) and its 'Current State' box is current-state.md (F2). Its 'Project Context (minimal & focused)' box is two new root docs, F16 architecture.md (essential architecture) and F17 operating-instructions.md (dev commands, testing rules, worktree/merge rules, links to detailed docs on demand), carved out of all-context.md (user answer 4). all-context.md stays the router. The diagram's task-registry box is MASTER-PLAN.md (section 3). Both new docs are on demand, not in either default entry set (below).

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

Planner total: <= 64,000 bytes provisional (typical 50-58 KB, about 13-15k tokens, about a 71-74% cut from ~200 KB). On demand, not default: master-planner.md (~10 KB, read in Master Planner posture), architecture.md (~7 KB, when a task touches layout, stack or data flow), operating-instructions.md (~7 KB, when commands, test tiers or worktree/merge rules are needed), orchestration.md (71 KB), context-changelog.md, other protocols.

WORKER entry set (a spawned worker session):

| File | Size (bytes) | Why default |
|---|---|---|
| CLAUDE.md (same role-neutral file) | <= 20,000 | loaded automatically; cannot be avoided |
| task envelope (first message; also saved as `{slug}_REF_{dd-mm-yy}.md` in the task folder) | <= 8,000 | states `ROLE: WORKER`, objective, ownership, tests, report path |
| task PLAN or SPEC named in the envelope | <= 8,000 | the work |
| operating-instructions.md (ONLY if the envelope names it) | <= 7,000 | commands, RT0-RT4 tier rules, worktree/branch/merge rules |

Worker total: <= 36,000 bytes provisional (typical ~30 KB, about 7-9k tokens, about an 85% cut); when the envelope names operating-instructions.md the cap is 43,000 (36,000 + 7,000). NOT in the worker default set: north-star.md, current-state.md, MASTER-PLAN.md, the all-context.md router, architecture.md, orchestration.md (the envelope links north-star.md, current-state.md and architecture.md; the worker opens them only if the task needs them, and notes it in report field 11). operating-instructions.md is loaded only when the envelope names it (the 43,000 cap then applies).

Router section definition: from line 1 of all-context.md through the line before the `## Context Group Lifecycle` heading (title, pointer line, project summary, how-this-file-works, entry and group tables, Task Routing Table). The base Quick Start section is merged into How This File Works so the range stays contiguous. Budget 94 lines (the F5 table rows through Task Routing Table: 15+3+10+15+25+26; ~5-6 KB at 62.5 bytes/line; the base equivalent, lines 1-32 plus 569-680, is 144 lines / 7,709 bytes before condensing). Command C3 measures it with `sed`, so the definition is mechanical, not a judgment.

Honest arithmetic: the earlier "43-48 KB" entry-set claim is withdrawn. It budgeted all-context.md at ~12 KB for 300 lines (40 bytes/line), but the kept sections measure 62.5 bytes/line (base lines 569-966 = 398 lines = 24,895 bytes), so a 288-300 line F5 would be ~18-19 KB (the carve-out to architecture.md and operating-instructions.md lowers the plan to 198 lines, ~12-13 KB); the planner loads only its ~5-6 KB router section, but the registry now joins the planner set, which is why the planner cap is 64,000. CLAUDE.md remains the largest default file for both roles; trimming it below 20 KB is a Gate 3 measurement, not a promise. The caps above are provisional: at Gate 2 close the measured bytes of F1, F2, the F5 router section and F6 are recorded in the Gate 2 report and the caps are confirmed or tightened; a cap may be raised only with user approval.

Role-neutral CLAUDE.md and AGENTS.md (F9, F10): CLAUDE.md line 50 ("You are the orchestrator, not the worker") and line 59 ("You do NOT") would make a spawned worker orchestrate with full RIPER-5 ceremony, and AGENTS.md has the same at lines 56 and 65. The Orchestrator Role section therefore moves to master-planner.md (Master Planner posture section) and the on-demand orchestration.md. The ENTRY-SET block carries a short Role Selection paragraph instead (specified after the disposition table below).

### Gate 2 order, R13 file list, F4/F5 definition, F9/F10 dispositions

**Gate 2 execution order (all-context.md is shared, so strictly serial):** R14 (rebuild registry base from `origin/claude/pensive-dijkstra-ko69oi` rev 6) -> R13 (salvage, list below) -> F1, F2, F3 (they do not touch all-context.md, and F5's summary is written from north-star.md, so they come first) -> F16, F17 (written from the base all-context.md sections they carve out, read at `<base>`, after F1 because F16 is written for the new North Star, and before F4 and F5 so F5's routing rows and pointers name files that already exist) -> F4 (create changelog from the base all-context.md, `<base>` = HEAD at Gate 2 start) -> F5 (slim all-context.md) -> F7 + F11 (together) -> F6 -> F8 -> F15 (three backlog stubs) -> **R4 step (vii)**, run by the Master Planner (orchestrator) session itself, NOT by the vc-execute-agent subagent (verified 02-10-26: the claude-code-remote tools `create_session`, `archive_session`, `send_message`, `list_sessions`, `list_events`, `set_session_tags`, `subscribe_pr_activity`, `get_session`, `interrupt_session` and `mcp__github__merge_pull_request` / `mcp__github__enable_pr_auto_merge` are in the orchestrator session's tool list; vc-* subagents do not see them): check every tool name this plan relies on against the live tool list, AND verify behaviour, not just names, with one read-only dry-run call such as `list_sessions` (it must return a session list; nothing is spawned, archived or merged). The orchestrator records the result in the Gate 2 report and hands it to the execute agent; any name that does not exist or call that fails is corrected in master-planner.md before the gate closes.

**Frontmatter for the six new context docs (F1, F2, F3, F4, F16, F17):** each starts with the same block the existing context docs use (see `process/context/tests/all-tests.md`): `---`, `name: context:<slug>` (north-star, current-state, decisions, context-changelog, architecture, operating-instructions), `description: "<one line>"`, `keywords: <comma-separated task vocabulary, non-empty>`, `date: dd-mm-yy`, `---`. Without `keywords` validate-context-discovery adds a warning per doc and `discover-context.mjs --match` cannot route to it. Command C14 checks the block.

**R13 files** (exciting-meitner changed 16 files vs merge-base; the task brief re-lists them with `git diff --name-status $(git merge-base origin/main origin/claude/exciting-meitner-hy50kn) origin/claude/exciting-meitner-hy50kn` at Gate 2 start): TAKE: the LSE ADOPT-WITH-LIMITS verdict artifact(s), the plan status-strip fixes, `process/context/data-sources/all-data-sources.md` (+67 lines, LSE findings; reviewed hunk by hunk, kept only where it does not contradict main). DROP: the duplicate `## Where We Are` status-board section in all-context.md (T24: one board), EVL logs/status-board scratch. The two Python files under `lse-data-verification_17-09-26/` are process-folder artifacts: TAKE as-is into the same task folder path (they are evidence for the verdict, not product code) or DROP with a recorded reason; they are never edited. Anything not in TAKE or DROP is recorded as `unreviewed` in the registry row, not silently skipped. **R13 destinations (named):** the branch moves `process/general-plans/active/lse-data-verification_17-09-26/` to `process/general-plans/completed/lse-data-verification_17-09-26/` (git shows `VERDICT.md`, `findings.md`, two EVL reports, `results.tsv`, `test_verify_provider.py` and renames of the PVL report, the PLAN and `verify_provider.py` landing in `completed/`, with the five `active/` files deleted). TAKEN artifacts land in `completed/`; the five `active/` copies are removed as part of that move. The move is archive operation A and is logged as one row in the `## Approvals Log` of `process/archive/index.md` (date, what, approver quote = the user's Q4 answer of 02-10-26). Touchpoints therefore also include `process/context/data-sources/all-data-sources.md` and both lse-data-verification folders.

**F4/F5 definition.** F4 holds the base changelog block (today lines 33-568; recomputed at Gate 2 start by command C6, never hard-coded) plus the sections moved out of F5 (Open Questions resolved items, References, Scan Metadata), verbatim. F5 required to survive (validate-context-discovery, validate-all-context): a `# ` title; `Last updated: YYYY-MM-DD`; the literal string `process/context/all-context.md`; `## Repository Structure`; `## Technology Stack`; `## Context Group Lifecycle`; the GENERATED:routing block intact (rebuilt with `--emit-routing` only if a root doc is added; must pass `--check-routing`); every new root doc (north-star.md, current-state.md, decisions.md, architecture.md, operating-instructions.md, context-changelog.md) named by basename in the routing tables (validate-context-discovery requires every root `process/context/*.md` doc to be named by basename in all-context.md), not as a backticked `process/context/<file>` path (see portability rule below).

| F5 section (base) | Disposition | Line budget |
|---|---|---|
| Title, Last updated, intro | keep, rewrite short | 15 |
| Changes Since Last Update (lines 33-568) | MOVE whole to F4; leave one pointer line | 3 |
| What This Project Is | replace with pointer to north-star.md + 3-line summary written from north-star.md (today's line 582 `redistribution-safe` goes with the replaced text) | 10 |
| How This File Works | condense; the base Quick Start section (lines 630-639) is merged into it | 15 |
| Root Entry Points / Context Groups (GENERATED block) | keep intact | 25 |
| Task Routing Table | keep, add rows for new root docs (architecture and stack questions route to architecture.md; commands, test tiers, worktree and merge rules route to operating-instructions.md) and the README runbook | 26 |
| Context Group Lifecycle, Naming, Update Protocol | keep, condense | 25 |
| Repository Structure | keep the heading (validator-required); body is a short top-level layout summary plus a link to architecture.md; the detailed tree moves to F16 | 12 |
| Technology Stack | keep the heading (validator-required); body is a short stack summary plus links to architecture.md (runtimes, boundaries) and operating-instructions.md (commands); detail moves to F16/F17 | 12 |
| Key Patterns | carve out to F16 (rewritten for the new North Star), leave a short pointer; the `Confidence over direction` paragraph (today line 910; the principle is retired, realignment AC-18 and T10 cancelled) is DROPPED, not carried | 6 |
| Environment and Configuration | carve out to F17, leave a short pointer | 6 |
| Open Decisions | keep, trim to current; DROP or reword today's line 957 (the `redistributable` wording in the narrative data-source row), line 955 (the Equity data provider row: remove `collides with the public-later goal` and restate it with the LSE ADOPT-WITH-LIMITS verdict) and the stale Deployment target row (line 959: replace with the resolved home PC plus Tailscale path); DROP lines 962-964 (the `Redistribution is a first-class constraint` paragraph, whole) | 25 |
| Open Questions | MOVE resolved/historical items to F4; keep only still-open ones as one-liners, reworded so none carries a retired phrase (today's line 1020 `redistributable` stays only in F4); current facts go to current-state.md | 15 |
| References, Scan Metadata | MOVE to F4; one pointer line | 3 |
| Total | | 198 (102 lines reserve under the 300 cap; the reserve is headroom, not budget: F5 stays mostly routing) |

**Retired wording is dropped, not kept (AC-R3, command C8).** Of the 11 hits today (lines 95, 373, 446, 581, 582, 910, 955, 957, 962, 964, 1020): lines 95, 373 and 446 sit in the changelog block and 1020 in Open Questions (all move whole to F4, where they are allowed); lines 581 and 582 (the wrapped `open it to / other users later` and `redistribution-safe`) go with the replaced What This Project Is text; lines 910, 955, 957, 962 and 964 are in kept sections and are dropped or reworded per the table above (955 and 964 are the `public-later` / `open up later` wording; 964 sits inside the 962-964 paragraph that is dropped whole). History of those phrases survives only in context-changelog.md (realignment AC-17/AC-18, T10 cancelled). north-star.md is written to avoid the retired phrases (F1 row).

**Changelog-preservation command (pinned, AC-R2): command C6 in the fenced block in section 10.** It recomputes the changelog range and each moved section's range from the base with `grep -n '^## '` (today: changelog 33-568, Open Questions 967-1105, References 1106-1166, Scan Metadata 1167-1223), then runs `comm -23` of the sorted unique base lines against the sorted unique F4 lines; it must print nothing. A dropped line prints exactly that line (negative case verified on a scratch copy). `<base>` is `git rev-parse HEAD` recorded when Gate 2 starts.

**Portability rule (validate-kit-portability).** The validator fails on backticked concrete `process/context/<file>` references outside {all-context.md, tests/all-tests.md, generated-skills-catalog.json} in CLAUDE.md, AGENTS.md and `process/development-protocols/*.md`. Therefore north-star.md, current-state.md, decisions.md, architecture.md, operating-instructions.md and context-changelog.md are referenced in those files by bare name or markdown link only (never a backticked `process/context/` prefix). No allowlist widening is proposed. validate-kit-portability runs at Gates 2 and 3.

**CLAUDE.md / AGENTS.md section disposition (F9/F10).**

| CLAUDE.md section | Disposition |
|---|---|
| Bootstrap Guard, Before Any Substantial Task | keep short; replace the three `@`-imports with plain bare-name pointers to the two entry sets (architecture.md and operating-instructions.md named as on-demand, by bare name only) |
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

Diagram mapping (user answer 1, 02-10-26): the diagram's 'task-registry.md' box is realised by this MASTER-PLAN.md registry table; MASTER-PLAN.md stays the board plus registry and no separate task-registry.md is created.

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

0. First line `ROLE: WORKER`, then: "You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagent chains, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md or elsewhere." 1. Task ID, objective, acceptance statement. 2. Exact files owned and files forbidden. 3. Branch name. 4. Links (not contents) to the task PLAN/SPEC and, only if the task needs them, north-star.md, current-state.md and architecture.md, plus operating-instructions.md when commands, tier rules or worktree/merge rules are needed (a worker loads it only when the envelope names it). 5. Test requirement + budget (section 6). 6. Retry budget (default 2 fix cycles). 7. Report destination path and the 11-field schema. 8. Stop conditions (irreversible/outward actions, scope expansion). 9. Autonomy statement. The envelope is also saved in the task folder as `{slug}_REF_{dd-mm-yy}.md` so its size is checkable (command C4). Workers load deeper context on demand via the router, not by default; the registry, north-star.md, current-state.md and architecture.md are not in the worker default set, and operating-instructions.md is loaded only when the envelope names it.

### Completion report (11 required fields) at `{task folder}/{slug}_REPORT_{dd-mm-yy}.md`

1 Task ID. 2 Outcome (done/partial/failed). 3 Summary (<= 10 lines). 4 Files changed (list). 5 Commits (SHAs) and branch. 6 Tests run (exact command, result, timestamp). 7 Tests NOT run and why. 8 Deviations from scope. 9 Blockers/risks/open questions. 10 Follow-up tasks proposed. 11 Context cost note (files loaded, approximate tokens; "unmeasured" allowed).

### Isolation model

| Environment | Unit of isolation | Mechanism |
|---|---|---|
| Cloud | one session = one container + one branch | `create_session(prompt, branch)`; branch name `claude/<task-id>-<slug>` |
| Local PC (user's) | git worktree | optional, user-driven; Master Planner records path in registry but cannot create it from the cloud |

Diagram wording ('own branch/worktree'): a git worktree applies only to local sessions on the user's PC; cloud workers are isolated by container plus branch (one session = one container + one branch, which `create_session` provides).

Max parallel lanes: 3 concurrent worker sessions, excluding the Master Planner's own session (existing MASTER-PLAN cap; Q6 wording). Ownership rule: each lane names owned path globs and forbidden globs in the registry row; two lanes may not own an overlapping glob; shared files (`.gitignore`, `all-context.md`, `CLAUDE.md`) are owned by exactly one lane at a time, others write requirements as notes. Conflict handling: planner detects overlap at queue time (compare globs); a detected overlap forces serialization, not a merge race.

### Standing authorization (Q6, resolved 02-10-26)

User's own words, verbatim: "it spawns workers for tasks you already marked approved, without asking again (max 3 sessions at the same time excl. master planner session), each session can merge and archive on itself automatically if it's sure it's ready and safe to merge".

Operational reading (this is the written authorization; anything not listed is NOT granted):

1. Spawn: the Master Planner may `create_session` a worker for any registry task whose status is `approved`, without asking again. Max 3 concurrent worker sessions, excluding the Master Planner's own.
2. Self-merge and self-archive: a worker may merge its own branch and archive its own session WITHOUT asking only when ALL mechanical safety conditions hold: (a) CI green on the head commit; (b) the task's risk-tier tests (section 6 table) all passed and were independently re-run or confirmed by CI; (c) the diff touches only files in the task's declared ownership; (d) no merge conflicts; (e) the completion report (11 fields) is persisted and committed; (f) the registry entry is updated to `accepted` then `archived` with commit refs.
3. No exceptions (user decision 02-10-26): the user declined the high-risk exclusion. Workers may self-merge and self-archive ANY task, including high-risk classes (deploy/runtime/proxy, schema/migration, public API contract, auth/identity, billing, secrets/trust boundary), provided ALL mechanical conditions in item 2 hold. Non-negotiable fail-safes the user did not remove: (i) a worker that is unsure stops at `review`; (ii) every item-2 condition must be evidenced (CI green on head, risk-tier tests passed, diff inside declared ownership, no conflicts, completion report committed, registry updated); (iii) the verifiability consequence below; (iv) branch deletion is limited to the scoped standing consent in item 4 (merged worker task branches only).
4. The four archive operations stay separate (document archival, mark logically complete, `archive_session`, branch delete). A session may be archived (`archive_session`) only after its handover report is durable and the merge is verified. NEW STANDING CONSENT (user, 02-10-26), scoped to merged worker task branches only (`claude/<task-id>-<slug>`: branches the Master Planner created for a registry task; `claude/p1-pipeline` and `claude/p2-deploy` are NOT covered, they predate the pattern and their tasks are in review): after the merge is verified, the completion report is committed and the registry shows `accepted` then `archived`, the Master Planner first writes one Approvals Log row (date, branch, merge SHA, report path, 'standing consent 02-10-26', status 'pending'), then deletes that task's remote branch via GitHub, then updates the row to 'done' (or 'failed', or 'deletion deferred' when no delete mechanism works; the branch then stays). An empty log therefore means no removal is permitted (AC-R6). 'Merge verified' means the PR state is merged, the merge SHA is reachable from `origin/main` and CI on that SHA is green (Enforcement (v)). The consent is NOT extended to any other branch: the 12 existing remote branches still need the per-branch review of section 7 and the user's approval (compassionate-goldberg stays a candidate needing approval), and local worktrees are never removed automatically. Recovery: a wrongly deleted merged branch is recoverable from the merge commit on `main` and the merged PR.
5. The Master Planner, not the worker, writes the registry and `current-state.md` updates after each merge.
6. Fail-safe: any worker that is unsure stops at `review`.

Tension with the acceptance rule ("never mark accepted because a worker says done") and its resolution: item 2 does not rest on the worker's say-so. Self-merge requires independent evidence (CI on the head commit, or a re-run by a party other than the implementer) plus mechanical diff-ownership and report checks. If any evidence is missing, the task stays `review`. So "worker is sure" is a necessary trigger, never a sufficient one.

Diagram mapping (user answer 2, 02-10-26: the worker self-merges; this authorization is unchanged): the diagram's 'Master Planner Review' box is realised by the Master Planner's registry update after the merge (item 5: report completeness, diff and commits against the declared ownership, required checks) plus the post-merge main-CI check (Enforcement (v)). The merge itself is the worker's under conditions (a)-(f); the Master Planner review follows it as a detective control and does not gate it.

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
| Mitigations | Post-start smoke check (R12); documented revert-commit procedure (`git revert <merge sha>`, recorded in the report and registry row); max 3 concurrent workers; evidenced mechanical conditions; fail-safe (i) unsure means `review`; verifiability consequence above; branch deletion only for merged worker task branches after the merge is verified (standing consent 02-10-26), never other branches |
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

(vii) Tool-name and tool-placement verification. Verified 02-10-26 in the Master Planner (orchestrator) session: `create_session`, `archive_session`, `send_message`, `list_sessions`, `list_events`, `set_session_tags`, `subscribe_pr_activity`, `get_session`, `interrupt_session` (the claude-code-remote server) and `mcp__github__merge_pull_request` / `mcp__github__enable_pr_auto_merge` exist in that session's tool list; vc-* subagents (research, plan, validate) do NOT see them. Consequences: (1) only the Master Planner session spawns and archives sessions (default operating rule; the planner may call `archive_session` for a worker's session once the handover report is durable and the merge is verified, operation C below); (2) `enable_pr_auto_merge` is unusable while the repo's `allow_auto_merge` is false; (3) whether a spawned worker's own tool list contains the merge and archive tools is UNVERIFIED and is checked by the Gate 6 pilot (the pilot worker records the tools it has in report field 11); a worker without a merge tool stops at `review`, and whether the Master Planner may merge on a worker's behalf is not covered by the standing authorization, so it is recorded as an extension of Open Question 10 for the user to decide. Gate 2 step R4 (vii) (section 2) re-checks names AND behaviour (one read-only `list_sessions` dry-run, nothing spawned) from the Master Planner session itself, because a vc-execute-agent subagent cannot call these tools. The branch-delete mechanism (a GitHub branch-delete tool in the planner's tool list, or `git push origin --delete <branch>`) is listed in the same check but is UNVERIFIED and cannot be dry-run read-only (a dry run would delete a branch): R4 (vii) only records which of the two exists in the tool list or is not blocked by the proxy (`git push --dry-run` of a delete refspec is not authoritative), the Gate 6 pilot confirms it, and the fallback is that the branch stays and its Approvals Log row says 'deletion deferred'.

### Completion lifecycle and the four separate operations

| Operation | What it means | Tool / supported? | Approval |
|---|---|---|---|
| A. Archive documents | move task folder to `completed/`, add row to `process/archive/index.md` | file move via UPDATE PROCESS | normal task flow, user-visible |
| B. Mark logically complete | registry status `accepted` then `archived` | registry edit | only after acceptance rule |
| C. Terminate/archive a session | `archive_session` MCP | supported | Allowed under the standing authorization only after the handover report is durable and merge verified (item 2/4); otherwise explicit user approval; sessions with unresolved asks are never archived |
| D. Delete branch / remove worktree | delete a MERGED worker task branch (remote, via GitHub after merge verified); remove a local worktree | `git push origin --delete <branch>` or a GitHub branch-delete call (mechanism confirmed at R4 step (vii) and the Gate 6 pilot; if none works the branch stays and the gap is recorded); `git worktree remove` is user-driven on the PC | Standing consent 02-10-26 covers merged worker task branches only, and only with: merge commit on `main` verified (PR merged, merge SHA reachable from `origin/main`, CI on it green), report committed, registry `accepted` then `archived`, one Approvals Log row. Every other branch and any worktree: explicit per-branch user approval (unmerged-state check first) |

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
| Move changelog out of default load (F4/F5) | all-context 93.7 KB -> ~12-13 KB at the planned 198 lines (62.5 bytes/line measured; cap 300), because layout, stack and operating detail move to architecture.md and operating-instructions.md (~7 KB each, on demand); the planner loads only its ~5-6 KB router section | done at Gate 2 (193 lines, 11,380 B) |
| Two role-based entry sets (F9) | default ~200 KB -> planner <= 64 KB (typical 50-58 KB), worker <= 36 KB (typical ~30 KB); workers stop re-reading planner context | done at Gate 3 (C3, C4); budget pinned at Gate 4 (PLANNER-BUDGET block, master-planner.md section 12) |
| Direct path for trivial changes (existing QUICK FIX / trivial-fix lane) | skip RESEARCH/PLAN for <= ~100 lines, no schema/auth/API | reuse; enforce in master-planner.md |
| Bounded retries | 2 fix cycles per worker; the same failure twice in a row stops at once; the existing 10-cycle PVL/EVL cap stays as the outer bound | done at Gate 4 (operating-instructions.md, envelope line) |
| Concise reports | 11-field schema, summary <= 10 lines | design |
| Selective context | worker envelope links, not contents; worker set excludes north-star.md, current-state.md, MASTER-PLAN.md, the all-context router, orchestration.md and architecture.md (operating-instructions.md only when the envelope names it) | design |
| De-duplicate `.agents/skills` | removes discovery noise, not session tokens | housekeeping H1 |

Measurement method: commands C3 and C4 (byte totals of the planner and worker entry sets, before/after; deterministic); tokens approximated as bytes/4 and labelled approximate. Per-session real token usage: UNMEASURED (no usage telemetry in repo); report field 11 captures a per-task estimate; Gate 3 used three headless `claude -p` probes (first-request context, single-run samples) instead of `list_events` sampling; real per-session usage stays unmeasured (backlog). Unmeasured and kept unmeasured: per-agent token cost, retry waste, cost of repeated test runs, AGENTS.md vs CLAUDE.md drift.

---

## 6. Risk-Based Test Policy

Commands are those named in the repo (all-tests.md, ci.yml, SPEC). This table is written to operating-instructions.md at Gate 2 (single home; all-tests.md links to it); its commands are re-confirmed against `all-tests.md` in Gate 4 and corrected there if they differ. Naming: RT0-RT4 are risk tiers; T# is always a registry task.

| Tier | Change type | Required (run once, after the last edit) | Not required |
|---|---|---|---|
| RT0 Docs / low | markdown, process files, comments | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <plan>` for plans; `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` for context edits; `git diff --check` | pytest, vitest, Playwright |
| RT1 Localized UI | one component/page in `web/` | `pnpm --filter web test` (affected file first, then suite), `pnpm --filter web exec tsc --noEmit` | pytest; Playwright only if a route or flow changed |
| RT2 Localized backend | one module/router in `api/` | `uv run --project api pytest <touched test file>` then `uv run --project api pytest api/ -q` once | vitest, Playwright |
| RT3 Shared interfaces / business logic | `cache.py`, response models, adapters used by 2+ routes | full pytest, full vitest, `tsc --noEmit`, `cd web && pnpm build:islands`; contract-snapshot tests unmodified | Playwright unless a route's behavior changed |
| RT4 High risk | auth, secrets, schema/migration, public API contract, deploy/proxy/runtime, destructive data ops | all of RT3 + Playwright (`cd web && pnpm test:e2e`) + hybrid/agent-probe evidence pack (`vc-risk-evidence-pack`) + user acceptance or a recorded agent-probe (acceptance rule (d); bypassing user acceptance for RT4 is the user's call, see the precedence note in section 4) | none skipped |

Test budget rule: each task declares its tier and the max number of full-suite runs (RT0: 0, RT1/RT2: 1, RT3: 2, RT4: 2 plus one EVL confirmation by a spawned vc-tester). No re-running unchanged tests: record in the report the commit SHA each result applies to; a run is repeated only if files changed after that SHA. Bounded retry: a failing gate gets at most 2 fix cycles by the same worker, then escalates to `blocked`/`needs_input`; the same failure twice in a row stops at once (Gate 4); before a re-run, `git diff --quiet <sha> HEAD -- <touched paths>` decides skip; flake handling: one isolated re-run is allowed to classify a flake, and the flake is logged as a backlog note rather than retried again (consistent with the screener flake note). Environment limits recorded, not hidden: container blocks live provider egress, so live-data checks are user-PC steps (hybrid, `needs_input`). CI (`ci.yml`) is the shared proving ground for RT1-RT3 on PRs; it does not run e2e or lint, so RT4 UI/route changes still need local Playwright.

Known-gap policy: any developed behavior proven only by a known-gap stays CONDITIONAL and gets a backlog stub (vacuous-green ban).

---

## 7. Housekeeping Candidates (no deletion on static search alone)

| ID | Candidate | Evidence | Risk | Needs approval |
|---|---|---|---|---|
| H1 | `.agents/skills` (17 MB) duplicate of `.claude/skills` | Gate 0; fails `validate-skills.mjs`/`validate-context-discovery.mjs` per MASTER-PLAN | Codex discovery might rely on it; symlink behavior on the Windows PC unverified | yes (replace with symlink or doc), validators before/after |
| H2 | `web/tsconfig.tsbuildinfo` tracked | Gate 0 | low; untrack (`git rm --cached`) and ignore (add `web/tsconfig.tsbuildinfo` to `.gitignore`, where it is absent today) | yes |
| H3 | Remote branches (kind-tesla, compassionate-goldberg, narrative-v2, p1-pipeline, p2-deploy, ui-shell, vigilant-hamilton, fix/narrative-sufficiency-gating-rfc1, inspiring-pasteur, pensive-dijkstra) | MEASURED 02-10-26, see the measured table below | deleting an unmerged branch loses work; large all-differ counts are confounded by files archived/moved on main | yes, per branch, after a per-file review; only compassionate-goldberg is a safe-to-delete candidate; the 02-10-26 standing consent covers merged worker task branches only, none of these |
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
| 2 | R14, R13, R1-R5 in the order in section 2 (F1-F8 + F11, F15-F17): current-state.md (re-verified), north-star.md, decisions.md, architecture.md, operating-instructions.md, context-changelog.md, slimmed all-context.md, master-planner.md (block-style frontmatter, Master Planner posture, envelope and report templates) wired into all-development-protocols.md, MASTER-PLAN registry from rev 6, archive index skeleton (with the Approvals Log), R4 step (vii) tool-name and behaviour check run by the orchestrator session | VALIDATE first; commands C5 (line cap), C6 (changelog and moved sections preserved), C7 (validator set, failures == baseline), C8 (retired wording), C9 (scope), C11 (every registry ID has a row), C12 (11 report headings, run against master-planner.md), C13 (whitespace and conflict markers in tracked, staged and untracked files) and C14 (Gate 2 deliverables, approvals log, `ROLE: WORKER`, north-star topics, R13 outcome, rev 6 preservation, F15 stubs); the measured bytes of F1, F2, F6, F16, F17 and the F5 router section (the informational `wc -c` lines of C14) are recorded to confirm the entry-set caps | VALIDATE contract; no source edits; ref-only fetch for branch facts requires approval |
| 3 | R6, R7: CLAUDE.md/AGENTS.md rewrite (F9, F10; role-neutral), byte baselines for BOTH entry sets, sampled session token baseline | commands C1 (no @-imports), C2 (role-neutral), C3 (planner bytes), C4 (worker bytes), C9 (scope, Gate 3 form allows CLAUDE.md and AGENTS.md), C10 (ENTRY-SET); validate-kit-portability.mjs, validate-protocol-wiring.mjs, validate-agent-parity.mjs non-strict (0 failures; the 18 warnings are baseline); validate-guide-sync.mjs: baseline-aware, README decision below; two agent-probes: a fresh PLANNER session reaches a task brief reading only the planner set, and a fresh WORKER session given only a sample envelope states ROLE: WORKER, spawns nothing and reaches its task reading only the worker set | CLAUDE.md/AGENTS.md edits (high-visibility, user review before commit) |
| 4 | R8: test policy in all-tests.md (link to the RT table in operating-instructions.md, dated evidence block), re-measured test counts, RT commands in full, bounded retry with the same-failure stop, no-re-run rule, pinned planner budget (D-12) | G4-1 to G4-11; the three suites run once (measured, SHA and UTC stamped) | none beyond Gate approval; installs need approval (given: G4-K1 = A) |
| 5 | R9-R12: housekeeping (approved items), README, deploy-path doc/guard proposal, session triage + archive index (R13 and R14 are Gate 2 work, ahead of R5, and are not repeated here) | per-item evidence re-check; validators; no deletion without per-item approval; R12 verified on the user's PC (hybrid) | deletion of any pre-existing branch, `archive_session` outside the standing authorization, `.agents/skills` replacement, tsbuildinfo untrack, deploy-script changes, any installs |
| 6 | Master Planner pilot: dispatch ONE low-risk task (e.g. P7 guard test or R-level docs task) through the registry end-to-end; then start approved product tasks | pilot task reaches `accepted` through the rule in section 4; report has 11 fields (command C12 against the pilot report); the pilot worker records in report field 11 which session and merge tools its own tool list contains (section 4, (vii)); the merged pilot branch is then deleted under the 02-10-26 standing consent only when the section 4 item 4 conditions hold and its Approvals Log row exists, which proves the deletion mechanism | each product task `approved` by user; spawning workers for `approved` tasks is covered by the standing authorization (section 4, max 3 concurrent); high-risk tasks are covered too ("no exceptions"), but self-merge needs every mechanical condition and the worker being sure; unverifiable runtime conditions mean `review` |

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
| AC-R1 | TWO role-based entry sets (caps provisional, confirmed at Gate 2 close): PLANNER (CLAUDE.md + north-star.md + current-state.md + MASTER-PLAN.md + all-context.md router section + task brief) <= 64,000 bytes; WORKER (CLAUDE.md + task envelope <= 8,000 + task PLAN/SPEC) <= 36,000 bytes. Neither set loads the changelog, orchestration.md, architecture.md or operating-instructions.md by default (a worker adds operating-instructions.md only when its envelope names it; the worker cap is then 43,000); CLAUDE.md has no `@`-imports and is role-neutral | commands C1 (no output after Gate 3; 3 lines today), C2 (no output after Gate 3; 8 lines today), C3 and C4 (byte totals), plus a fresh-session probe for each role at Gate 3; from Gate 4 the PLANNER-BUDGET block (fixed part <= 56,000 B, per-file ceilings, brief <= 8,000 B; G4-1, G4-2) | Fully-Automated + Agent-Probe |
| AC-R2 | all-context.md <= 300 lines; changelog and moved sections fully preserved in context-changelog.md | commands C5 (line cap) and C6 (preservation; prints nothing) | Fully-Automated |
| AC-R3 (=AC-19) | Single North Star doc exists with personal-use, data-not-verdicts, Tailscale-only, page list, non-goals; old confidence/public-later/redistribution wording gone from entry points (history lives only in context-changelog.md) | command C8 -> no output after Gate 2 (11 hits today, all in all-context.md); case-insensitive | Fully-Automated |
| AC-R4 (=AC-20) | Current-state, task registry, archive index, MASTER-PLAN reconciled and referenced from CLAUDE.md/AGENTS.md/all-context | link/grep check + validator set C7 (failures == baseline) + command C10 at Gate 3 | Fully-Automated |
| AC-R5 | Registry holds all T-tasks (T1, T1b, T3-T5, T7-T28; T2 and T6 are recorded as unknown, not invented), with T26-T28 from rev 6, each with a status and evidence note; unverified items labelled UNVERIFIED | review of registry vs section 3 + command C11 (checks each ID individually; a row count is not used because other tables also start with `| T`: counts today are 18 on main and 20 on rev 6) | Hybrid (user review) |
| AC-R6 | No branch, session, or file removed without recorded approval (the 02-10-26 standing consent for merged worker task branches counts only through its logged rows) | git/session state diff vs the approvals log, which is the `## Approvals Log` section of `process/archive/index.md` (one row per approval: date, what, approver quote); an empty log means no removal is permitted | Hybrid |
| AC-R7 | Acceptance rule demonstrated: pilot task not `accepted` on worker word alone | pilot report + registry history | Agent-Probe |
| AC-R8 | Product code untouched by Gates 2-4 | command C9 (`git status --porcelain` based, sees uncommitted and untracked files; no output at Gate 2 and Gate 4, Gate 3 form allows CLAUDE.md and AGENTS.md); `<gate-base-sha>` = `git rev-parse HEAD` recorded when the gate starts, used only for the post-commit form of C9 | Fully-Automated |
| AC-R9 | Token claims labelled measured/unmeasured | review of the Gate 3 and Gate 4 reports | Hybrid |
| AC-R10 | Worker completion reports carry all 11 fields | command C12 equals 11, run against the report template inside master-planner.md at Gate 2 (the first real worker report exists only at Gate 6) and against the pilot report at Gate 6 | Fully-Automated |
| AC-R11 | architecture.md and operating-instructions.md (each ~120 lines, <= 150) exist with their required parts (layout, runtimes and boundaries, a data flow section, patterns for the new North Star; commands, the RT0-RT4 table, worktree/branch/merge rules, session start/end) and are named by basename in all-context.md, which stays <= 300 lines with its validator-required headings | commands C14 (existence, line caps, RT rows, worktree and data-flow checks), C5, C7 (validate-context-discovery root-doc indexing, validate-all-context) | Fully-Automated |

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
# current-state.md, a total that varies with the plan file's size (240,454 when first measured, 269,986 in cycle 4; the gate is the rc line, not the number) and rc=1. The earlier `cat | wc -c` form printed 234253 with two stderr errors because a failing
# cat does not fail wc, which is why the file check comes first. The router range still contains the 45 KB changelog today.

# C4  AC-R1: WORKER entry set bytes (after Gate 3). ENVELOPE = the saved envelope file, TASK = its task PLAN/SPEC
ENVELOPE=<path>; TASK=<path>; OPS=
# set OPS=process/context/operating-instructions.md only when the envelope names it
MISS=0; for f in CLAUDE.md "$ENVELOPE" "$TASK" ${OPS:+"$OPS"}; do test -s "$f" || { echo "MISSING $f"; MISS=1; }; done
CAP=36000; test -n "$OPS" && CAP=43000
total=$(cat CLAUDE.md "$ENVELOPE" "$TASK" ${OPS:+"$OPS"} 2>/dev/null | wc -c); echo total=$total cap=$CAP
test "$MISS" -eq 0 && test "$(wc -c < "$ENVELOPE")" -le 8000 && test "$total" -le "$CAP"; echo rc=$?
# must print rc=0 (cap 36000 without OPS, 43000 with OPS; envelope <= 8000). A missing input prints a MISSING line and rc=1 (the old form
# silently under-counted). Not runnable today: no envelope exists, so with ENVELOPE=<any missing path> it prints MISSING and rc=1.
# Verified in cycle 4 on scratch files (CLAUDE.md 20,000 bytes): envelope 6,000 + task 5,000 -> total=31000 cap=36000 rc=0; with a 7,000-byte OPS ->
# total=38000 cap=43000 rc=0; missing TASK -> MISSING line, rc=1; missing OPS -> MISSING line, cap=43000, rc=1; envelope 9,000 bytes -> rc=1;
# 20,000-byte task -> total=46000 cap=36000 rc=1, and with OPS total=53000 cap=43000 rc=1.

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
# Gate 2: validate-context-discovery also requires architecture.md and operating-instructions.md (like every root doc) to be named by basename in all-context.md; an unindexed one adds a failure beyond the 1-item baseline.

# C8  AC-R3: retired wording absent from entry points (case-insensitive)
grep -niE 'confidence over direction|open it to other users|public[ -]later|open up later|other users later|intended to open|redistribution-safe|redistribution is a first-class|redistributab|licens(e|ing) is a design constraint' CLAUDE.md AGENTS.md process/context/all-context.md process/context/north-star.md process/context/architecture.md process/context/operating-instructions.md
# expected today: 11 hits, all in all-context.md (lines 95, 373, 446, 581, 582, 910, 955, 957, 962, 964, 1020; verified 02-10-26; architecture.md, operating-instructions.md and north-star.md do not exist yet, so grep adds stderr lines only). After Gate 2: no output.
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

# C14  AC-R3, AC-R5, AC-R6, AC-R10, AC-R11: Gate 2 deliverables exist and carry their required parts (no MISSING/FAIL line and no comm output = pass)
for f in process/context/north-star.md process/context/current-state.md process/context/decisions.md process/context/architecture.md process/context/operating-instructions.md process/context/context-changelog.md process/development-protocols/master-planner.md process/archive/index.md process/archive/master-plan-revisions_02-10-26.md process/general-plans/backlog/token-usage-telemetry_NOTE_02-10-26.md process/general-plans/backlog/agents-skills-symlink-windows_NOTE_02-10-26.md process/general-plans/backlog/deploy-runtime-user-pc-verification_NOTE_02-10-26.md; do
  test -s "$f" || echo "MISSING $f"
done
test "$(grep -c '^## Approvals Log' process/archive/index.md 2>/dev/null)" -eq 1 || echo "FAIL approvals-log heading"
test "$(sed -n '/^## Approvals Log/,$p' process/archive/index.md 2>/dev/null | grep -c 'lse-data-verification')" -ge 1 || echo "FAIL approvals-log lse row"
test "$(sed -n '/^## Approvals Log/,$p' process/archive/index.md 2>/dev/null | grep -ci 'standing consent')" -ge 1 || echo "FAIL approvals-log branch-deletion consent row"
test "$(grep -c 'ROLE: WORKER' process/development-protocols/master-planner.md 2>/dev/null)" -ge 1 || echo "FAIL ROLE: WORKER"
for t in 'personal[- ]use' 'not verdicts' 'tailscale' '^#+ .*pages' '^#+ .*non-goals'; do
  test "$(grep -ciE "$t" process/context/north-star.md 2>/dev/null)" -ge 1 || echo "FAIL north-star topic $t"
done
for f in process/context/architecture.md process/context/operating-instructions.md; do
  n=$({ wc -l < "$f"; } 2>/dev/null); { test -n "$n" && test "$n" -le 150; } || echo "FAIL $f line cap (<= 150) or missing"
done
test "$(grep -ciE 'data flow' process/context/architecture.md 2>/dev/null)" -ge 1 || echo "FAIL architecture.md data flow section"
test "$(grep -cE '^\| RT[0-4] ' process/context/operating-instructions.md 2>/dev/null)" -eq 5 || echo "FAIL operating-instructions.md RT0-RT4 rows"
test "$(grep -ci 'worktree' process/context/operating-instructions.md 2>/dev/null)" -ge 1 || echo "FAIL operating-instructions.md worktree rule"
n=$({ wc -c < process/context/operating-instructions.md; } 2>/dev/null); { test -n "$n" && test "$n" -le 7000; } || echo "FAIL operating-instructions.md byte cap (<= 7000, the worker-cap arithmetic) or missing"
test "$(grep -cE '[0-9a-f]{7,40}' process/context/current-state.md 2>/dev/null)" -ge 1 || echo "FAIL current-state.md has no commit stamp"
test "$(grep -c 'UTC' process/context/current-state.md 2>/dev/null)" -ge 1 || echo "FAIL current-state.md has no UTC time stamp"
for t in decision date reason alternatives consequences status; do
  test "$(grep -ciE "$t" process/context/decisions.md 2>/dev/null)" -ge 1 || echo "FAIL decisions.md field $t"
done
for f in process/context/north-star.md process/context/current-state.md process/context/decisions.md process/context/context-changelog.md process/context/architecture.md process/context/operating-instructions.md; do
  { test "$(head -n 1 "$f" 2>/dev/null)" = '---' && grep -q '^name: context:' "$f" && grep -q '^keywords: .' "$f" && grep -q '^description: ' "$f"; } || echo "FAIL frontmatter $f"
done
test -d process/general-plans/completed/lse-data-verification_17-09-26 || echo "FAIL R13 completed/ folder missing"
test ! -d process/general-plans/active/lse-data-verification_17-09-26 || echo "FAIL R13 active/ folder still present"
REV6=18ffd4f014f4e5ea0f5d654688875a9300b30ab4; TMPDIR=${TMPDIR:-/tmp}
git show "$REV6:process/MASTER-PLAN.md" | sort -u > "$TMPDIR/rev6.txt"
cat process/MASTER-PLAN.md process/archive/master-plan-revisions_02-10-26.md 2>/dev/null | sort -u > "$TMPDIR/f6.txt"
comm -23 "$TMPDIR/rev6.txt" "$TMPDIR/f6.txt" | grep -vE '^\| (T|P)'
# informational, for the Gate 2 report (confirms or tightens the provisional caps; a cap is raised only with user approval):
wc -c process/context/north-star.md process/context/current-state.md process/MASTER-PLAN.md process/context/architecture.md process/context/operating-instructions.md
sed '/^## Context Group Lifecycle/,$d' process/context/all-context.md | wc -c
# expected today (measured 02-10-26): 12 MISSING lines (9 deliverables + 3 stubs), 31 FAIL lines (15 of them are the cycle-4 additions: operating-instructions.md byte cap, current-state.md commit stamp and UTC stamp, six decisions.md fields, six frontmatter lines; the other 16 are approvals-log heading, approvals-log lse row,
# approvals-log branch-deletion consent row, ROLE: WORKER, 5 north-star topics, two line-cap/missing lines, architecture data flow, RT0-RT4 rows,
# worktree rule, R13 completed/ missing, R13 active/ still present) and 210 comm lines (rev 6 lines absent from today's rev 3a MASTER-PLAN.md),
# followed by the three informational byte lines (256 stdout lines in all, re-measured in cycle 4; stderr adds 4 wc missing-file lines and 10 'integer expression
# expected' lines, which are noise from the missing files: the gate is the MISSING/FAIL/comm lines). After Gate 2: no MISSING, no FAIL, no comm output.
# Verified: the new fragments print nothing on a complete scratch fixture; a 200-line architecture.md, a missing RT4 row and a missing standing-consent
# row each print exactly their FAIL line. The earlier rev 6 preservation check is unchanged: a dropped non-row rev 6 line prints exactly that line.
# Residual: the `| T`/`| P` filter lets re-expressed registry rows through (C11 checks each ID by name), so a dropped row is caught by C11, not here.
# The F5 router-section byte line uses the same sed range as C3.
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
| G2 command C14 context-split checks (architecture.md and operating-instructions.md exist, <= 150 lines, data flow section, five RT rows, worktree rule) plus C7 root-doc indexing | Fully-Automated | AC-R11 |
| G2 R4 (vii): tool names and one read-only list_sessions dry-run, run by the orchestrator session | Agent-Probe | AC-R7 |
| G2/G5 registry reviewed against evidence, command C11 | Hybrid | AC-R5 |
| G2 command C13 (whitespace and conflict markers in tracked, staged and untracked files; no output) | Fully-Automated | AC-R4 |
| G2 command C14 (deliverables exist; frontmatter of the six new context docs; operating-instructions.md byte cap; F2 commit and UTC stamps; F3 fields; `## Approvals Log` with the R13 row and the branch-deletion consent row; `ROLE: WORKER`; north-star topics; R13 outcome; rev 6 preserved in F6 plus the archive file; F15 stubs) | Fully-Automated | AC-R3, AC-R5, AC-R6, AC-R10 |
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
| Slimming loses knowledge | med | changelog moved whole, not edited; diff check; git history. The carved Repository Structure, Technology Stack, Key Patterns and Environment sections are rewritten into F16/F17 (not moved whole); the base text is preserved in git at `<base>`. validate-all-context may print warnings after the slimming (it greps for words such as References); the gate is no new failure versus the baseline, and the pointer lines can keep those words |
| Registry becomes a second stale board (as MASTER-PLAN did) | high | wire into CLAUDE.md session start/end; end-of-session registry update is a protocol step; `current-state.md` stamped with commit so staleness is detectable |
| CLAUDE.md rewrite breaks agent routing | med | parity/wiring validators; user review before commit |
| AGENTS.md drifts from CLAUDE.md again | med | both point to the same short entry set; drift check in Gate 3 |
| Worker report claims unverified | high | acceptance rule requires independent re-run |
| Branch deletion destroys unmerged work | low-med | per-branch ahead/behind check, per-branch approval (pre-existing branches; the 02-10-26 standing consent does not cover them) |
| Deleting a merged worker task branch (RISK ACCEPTED BY USER, standing consent 02-10-26) | low | a wrongly deleted branch is recoverable from the merge commit on `main` and the merged PR; mitigation: delete only after the merge commit is on `main` and verified (PR merged, merge SHA reachable from `origin/main`, CI on it green), report committed, registry `accepted` then `archived`, Approvals Log row written; scope limited to merged `claude/<task-id>-<slug>` worker branches, never any other branch |
| Cloud sessions with unresolved asks get archived | med | C-operation blocked while asks unresolved; list_events review first |
| Self-merge ships a bad change (RISK ACCEPTED BY USER, 02-10-26, "no exceptions", includes high-risk classes) | med | all six mechanical conditions required and evidenced; independent CI/re-run evidence; unsure means `review`; unverifiable runtime conditions mean `review`; smoke check; revert-commit procedure; 3-worker cap; branch deletion limited to merged worker task branches |
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
13. Diagram-revision answers RESOLVED 02-10-26 (user target-workflow diagram, four differences): (1) MASTER-PLAN.md stays the board plus registry (the diagram's task-registry box is realised by it); (2) the worker self-merges, no change (the 'Master Planner Review' box = registry update plus post-merge main-CI check); (3) NEW STANDING CONSENT: delete merged worker task branches after a verified merge and a saved report (scope and conditions in section 4 item 4; not extended to any other branch); (4) context split: architecture.md and operating-instructions.md are created at Gate 2 (F16, F17).

Still OPEN:

10. OPEN (needs the user's explicit accept or decline): control-surface self-merge. Recommendation: forbid self-merge for diffs that touch ci.yml, validators, master-planner.md, CLAUDE.md/AGENTS.md or `.claude/`, stopping at `review`. This does not override 'no exceptions'; until answered the plan follows the user's decision and records the residual as user-accepted with a post-merge main-CI check and revert proposal (section 4, Enforcement and compensating controls). Non-blocking for Gate 2 start. Two related extensions are also recorded here for the user's call, neither assumed by this plan: (a) whether RT4 / high-risk tasks may bypass user acceptance (section 4 precedence note); (b) whether the Master Planner may merge a worker's PR when the worker's own tool list lacks a merge tool (section 4, (vii)); (c) branch deletion under the 02-10-26 standing consent keeps the revert path open for a control-surface self-merge, because the branch is deleted only after the post-merge main-CI check on the merge SHA is green and the merge commit stays on `main`.

12. OPEN, user decision, non-blocking for Gate 2 start: confirm the worker lane as a DIRECT lane. A worker does not run the multi-agent RIPER chain; it writes a compact per-task validate-contract itself and runs its declared gates directly (section 4, worker lane rule). Clarification: one vc-quick-fix-agent spawn for a tiny task is not a subagent chain, so it does not conflict with the Role Selection text "do not spawn sessions or subagent chains". Until answered, the plan follows this lane as user-approved on 02-10-26.

Still OPEN: none blocking. Branch deletion: standing consent GRANTED 02-10-26 for merged worker task branches only (section 4 item 4); NOT extended to any other branch. This plan itself deletes nothing, and the 12 existing remote branches still need the per-branch review and the user's approval (compassionate-goldberg is a candidate needing approval).

---

## Touchpoints

Gate 2-5 writes: `process/context/*` (new and slimmed, including `architecture.md` and `operating-instructions.md`), `process/MASTER-PLAN.md`, `process/archive/index.md`, `process/development-protocols/master-planner.md`, `all-development-protocols.md`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `web/tsconfig.tsbuildinfo` (untrack), `.gitignore` (add the tsbuildinfo ignore line; single owner at Gate 5), `process/context/data-sources/all-data-sources.md`, `process/archive/master-plan-revisions_02-10-26.md`, three backlog stubs under `process/general-plans/backlog/` (F15: `token-usage-telemetry_NOTE_02-10-26.md`, `agents-skills-symlink-windows_NOTE_02-10-26.md`, `deploy-runtime-user-pc-verification_NOTE_02-10-26.md`) and the lse-data-verification task folder (R13: moved from `process/general-plans/active/` to `process/general-plans/completed/`). Reads: git state, MCP session list, `deploy/`. This plan itself writes only its own file.

## Public Contracts

Behavior contracts other sessions rely on: the default entry set; the task status vocabulary; the acceptance rule; the 11-field report path/schema; the four archive operations. No API, schema, or runtime contract changes.

## Blast Radius

Docs/process only through Gate 4 (risk class: RT0). Gate 5 adds git-index and ignore changes (RT0-RT1) and optional deploy script changes (RT4, separately approved). No product code.

## Test Infra Improvement Notes

(none identified yet) Candidate noted: no token-usage telemetry; no deployed smoke test; ci.yml lacks lint/e2e.

## Validate Contract

Status: PASS
Date: 03-10-26
date: 2026-10-03
generated-by: outer-pvl
supersedes: 2026-10-02 (outer-pvl, PVL cycle 4, Gate CONDITIONAL) - outer PVL cycle 5 has current evidence (re-validation of the cycle-4 supplement: Gaps 31-32 and cosmetic items c1-c9, plus a full live re-run of the pinned commands C1-C14 and the validator baseline, against the live repo at HEAD 2d0e545, clean tree)
Scope: this contract gates the START of Gate 2 only (F1-F8, F11, F15, F16, F17, R13, R14). Gates 3-6 each re-enter VALIDATE (plan rule); the Gate 3+ findings below are carried forward as requirements, not as approval.

Parallel strategy: sequential (single validate session; Layer 1 and Layer 2 checks ran inline as read-only commands, no sub-agent spawn tool was available to this session)
Rationale: signal score 2/7 (S6 high-risk class named in plan: deploy/secrets/auth under the self-merge authorization; S7 14+ files in blast radius). MEDIUM band would normally recommend parallel read-only subagents; dominant signal is S7. Findings below are evidence-based: in cycle 4 every pinned command C1-C14 was actually run against the live tree and compared with its stated expected-today output; validator failures and warnings were counted by parsing their JSON output; the validator sources (validate-all-context, validate-context-discovery, validate-kit-portability, discover-context routing generation) were read to confirm what the F5 carve-out must keep; the pinned rev 6 SHA, the exciting-meitner diff, the remote branch list and the cited counts were re-queried read-only; and C4 with its optional OPS parameter was exercised on scratch files in the session scratchpad (no repo state changed). Cycle 5 (closing pass, 03-10-26): every pinned command C1-C14 was run again on the live tree and matches its stated expected-today output; C4 was exercised on seven scratch cases and C14 on a complete scratch fixture (positive and negative); the frontmatter spec for the six new context docs was tested against validate-context-discovery, validate-all-context and the routing check in a scratch clone.

Baseline measured 02-10-26 (read-only runs on branch claude/pensive-albattani-ou0cgv, before any Gate 2 write; RE-CONFIRMED in cycle 4 by JSON parse, unchanged: context-discovery 1 failure, skills 1, guide-sync 1, parity non-strict 0 failures / 18 warnings, plan-inventory 0 failures / 6 warnings, all others 0). Every Gate 2/3 validator gate is "no NEW failure vs this baseline", not "exit 0":

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

Cycle-3 gap re-verification (Gaps 24-30, each re-checked live in cycle 4):

| Gap | Result | Evidence (cycle 4, executed) |
|---|---|---|
| 24 test tiers collide with task IDs | CLOSED | the tier labels T0-T4 survive only in this contract's own history lines; section 6 table rows are RT0-RT4 (`grep -cE '^\| RT[0-4] '` on this plan prints 5); naming rule stated in sections 3 and 6 |
| 25 F14 .gitignore claim | CLOSED | `web/tsconfig.tsbuildinfo` is still tracked and `grep -n tsbuildinfo .gitignore` prints nothing, as F14 now says; F14, H2, Touchpoints and the Gate 5 form of C9 all read untrack AND ignore |
| 26 C14 and F15 | CLOSED | C14 run on today's tree prints 12 MISSING (9 deliverables + 3 stubs), 16 FAIL and 210 comm lines, exactly as stated, so it is not vacuous; the pinned rev 6 SHA resolves (`git rev-parse origin/claude/pensive-dijkstra-ko69oi` = 18ffd4f014f4e5ea0f5d654688875a9300b30ab4); the RT-row regex matches 5 rows |
| 27 C13 blind to untracked and staged files | CLOSED | C13 prints nothing today (clean tree); the scratch-repo mechanics were verified in cycle 3 and the command text is unchanged |
| 28 C8 blind to public-later | CLOSED | C8 prints exactly 11 hits today, all in all-context.md at lines 95, 373, 446, 581, 582, 910, 955, 957, 962, 964, 1020; the F5 table accounts for each (95, 373, 446 and 1020 move whole to F4; 581 and 582 go with the replaced What This Project Is text; 910, 955, 957, 962 and 964 are dropped or reworded) |
| 29 C2 narrow, C3 under-counts | CLOSED for C2 and C3; the same defect remains in C4 (new Gap 32) | C2 prints 8 lines today (CLAUDE.md 46, 50, 52, 59; AGENTS.md 50, 56, 58, 65); C3 prints MISSING for north-star.md and current-state.md, then a total and rc=1 (cosmetic: the stated `total=240454` was true when written and tracks this plan file's own size, today 269,986) |
| 30 bundle (a)-(g) | CLOSED, with one residual (Gap 31) | F1-F3 precede F4/F5 in the Gate 2 order; Gate 2 row names C11, C13, C14; router budget is the sum of the table rows through Task Routing Table (15+3+10+15+25+26 = 94); Scan Metadata is lines 1167-1223 = 57; Open Question 12 exists; validate-plan-inventory is in the baseline table and C7 (0 failures, 6 warnings, re-run); the literal `process/context/all-context.md` count today is 9 in CLAUDE.md and 12 in AGENTS.md; F16 and F17 are still missing from the Gate 2 order (Gap 31) |

Diagram-revision verification (user-driven, 02-10-26; checked live in cycle 4):

| Item | Result | Evidence |
|---|---|---|
| F5 carve-out arithmetic | OK | the disposition table sums to 198 (15+3+10+15+25+26+25+12+12+6+6+25+15+3); the retired 288 equals 198 - (12+12+6+6) + (45+40+25+20) - 26 + 22; the base sections being carved measure Repository Structure 94 lines / 7,350 B, Technology Stack 64 / 4,634, Key Patterns 28 / 1,593, Environment 31 / 1,590 (217 lines, 15,167 B), so F16 and F17 (~120 lines each) are new writing, not a copy; the router rows are 94 lines (~5.9 KB at 62.5 B/line), under the 8,000 cap |
| validator-required headings after the carve-out | OK | validate-all-context requires a `# ` title, `## Repository Structure`, `## Technology Stack` and `Last updated: YYYY-MM-DD`; validate-context-discovery requires the literal `Context Group Lifecycle` in the router and the literal `process/context/all-context.md` in CLAUDE.md and AGENTS.md; the F5 table keeps every one; both validators run clean today apart from the 1-item baseline |
| root-doc basename indexing | OK | validate-context-discovery treats a root doc as indexed when the router text contains its path relative to process/context, which for a root doc is its basename; the plan names all six new root docs by basename; discover-context.mjs builds the GENERATED block from group entry points only (read the generator), so adding root docs never stales it |
| entry-set caps | OK | PLANNER 20,000+4,000+4,000+20,000+8,000+8,000 = 64,000, typical 20+4+4+15+5.9+(3 to 8) = 52-57 KB, consistent with "50-58 KB, 71-74% cut"; WORKER 20,000+8,000+8,000 = 36,000, +7,000 = 43,000 with operating-instructions.md, typical ~30 KB = 85% cut; registry cap 20,000 vs rev 6 at 43,484 B / 751 lines is plausible only after the F6 relocation (provisional, measured at Gate 2 close) |
| C4 optional OPS | CONCERN (Gap 32) | scratch run: no OPS and OPS both print a total; a missing TASK or OPS path prints a stderr error and silently UNDER-counts (34,903 vs 38,903 on the fixture); the cap is never tested. Same defect class as Gap 29a, fixed for C3 only. A corrected form (test -s per input, CAP 36,000 or 43,000, rc line) was run on six scratch cases and behaves correctly |
| C8 scans the new docs | OK | the file list includes north-star.md, architecture.md and operating-instructions.md; decisions.md, current-state.md, master-planner.md and context-changelog.md are history or protocol docs and are intentionally outside it |
| AC-R11 and C14 context-split fragments | OK | they fail today exactly as stated (line caps, data flow, RT rows, worktree rule) and are non-vacuous; the RT-row regex matches the 5 rows of the section 6 table |
| Gate 2 order | CONCERN (Gap 31) | the sentence lists R14, R13, F1-F3, F4, F5, F7+F11, F6, F8, F15, R4 (vii); F16 and F17 are absent although the revision log says they were added and the Gate 2 row of section 9 lists F15-F17 |
| branch-deletion consent consistency | OK | every mention (TL;DR, F7, F8, section 4 items 3 and 4, archive-operation D row, Risk accepted table, H3, Gate 5 and 6 rows, AC-R6, C14, two section 12 rows, Open Questions 10(c), 13 and the closing line, goal block hard stops) says: merged worker task branches `claude/<task-id>-<slug>` only, after verified merge + committed report + registry accepted then archived + an Approvals Log row; every other branch and every worktree needs per-branch approval. The only remaining "NOT granted" wording is this contract's cycle 1-3 history, superseded by the 02-10-26 entry |
| no leak to the 12 existing branches | OK | `git branch -r` shows 14 refs = the 12 named in the measured table + main + the session branch; section 4 item 4 and H3 exclude them by name; `claude/p1-pipeline` and `claude/p2-deploy` fit the name pattern but are excluded explicitly and by the registry-state precondition (P1 and P2 are `review`, never `accepted` then `archived`) |
| deletion mechanism verifiability | UNVERIFIED, stated honestly by the plan (cosmetic wording note) | this validate session has no GitHub MCP or session tools (the plan records that vc-* subagents do not see them), so a branch-delete tool cannot be listed from here; a repo search for `delete_branch` finds nothing and the proxy README says nothing about push-delete. Operation D already reads "mechanism confirmed at R4 step (vii) and the Gate 6 pilot; if none works the branch stays and the gap is recorded". My recollection, NOT verified here, is that the upstream GitHub MCP server offers create_branch but no delete-branch tool and that `git push origin --delete` may be refused by the git proxy; treat deletion as inoperative until R4 (vii) or the Gate 6 pilot proves otherwise. No safety consequence: the fallback is that the branch stays |

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
| AC-R4 | plan inventory not worsened by the R13 folder move | Fully-Automated | `node .claude/skills/vc-audit-plans/scripts/validate-plan-inventory.mjs` -> failures stay 0 (baseline 0 failures, 6 warnings, re-run cycle 4) | B (Gap 30 closed) |
| AC-R3 | retired wording gone from entry points | Fully-Automated | command C8 -> no output after Gate 2 (11 hits today, all in all-context.md, re-run cycle 4) | B (Gap 28 closed: every hit is accounted for by the F5 table) |
| AC-R1 | default load no longer imports big files | Fully-Automated | command C1 -> no output after Gate 3 (3 lines today); C3/C4 byte totals at Gate 3 | B (C3 closed in cycle 4; C4 still under-counts silently, Gap 32) |
| AC-R8 | product code untouched | Fully-Automated | command C9 -> no output at Gate 2 (verified empty today) | A |
| all | whitespace and conflict markers | Fully-Automated | command C13 (tracked, staged and untracked files) -> no output | B (Gap 27 closed) |
| Gate 2 deliverables | F1, F2, F3, F4, F7, F8, the F6 archive file and the R13 move exist and carry their required parts | Fully-Automated | command C14 (deliverables exist; `## Approvals Log` with the R13 and branch-deletion rows; `ROLE: WORKER`; north-star topics; F16/F17 line caps and parts; R13 outcome; rev 6 preserved in F6 plus the archive file; F15 stubs); fails today with 12 MISSING / 16 FAIL / 210 comm lines, so it is not vacuous | B (Gap 26 closed) |
| AC-R4/AC-R7 | plan structure valid | Fully-Automated | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <this plan>` -> 0 failures, 0 warnings (re-run 02-10-26, cycle 3) | A |
| AC-R4 (Gate 3) | README/guide sync | Fully-Automated | `node .claude/skills/vc-audit-vc/scripts/validate-guide-sync.mjs` -> baseline failure (1) accepted until Gate 5 (decision recorded in plan section 9) | C (decided: Gate 5) |
| AC-R4 (Gate 3) | CLAUDE.md and AGENTS.md carry one identical ENTRY-SET block | Fully-Automated | command C10 (verified on scratch files in cycle 3) | A |
| AC-R5 | registry reconciled against evidence | Hybrid | user review of registry vs plan section 3 + command C11 (prints MISSING for 11 IDs today, none after Gate 2); precondition: rev 6 base loaded | B |
| AC-R6 | nothing removed without approval | Hybrid | `## Approvals Log` in `process/archive/index.md` vs `git`/session state diff; empty log means no removal permitted | B (Gap 26 closed: the F8 row defines the log and C14 checks it) |
| AC-R9 | token claims labelled measured/unmeasured | Hybrid | user review of Gate 3 report | A |
| AC-R1 | fresh PLANNER and WORKER sessions reach their task on their own entry set only | Agent-Probe | two fresh-session probes at Gate 3 | A (Gate 3) |
| AC-R10 | worker report carries all 11 headings | Fully-Automated | command C12 equals 11 (verified on a scratch fixture) against the template at Gate 2 and the pilot report at Gate 6 | A |
| AC-R11 | architecture.md and operating-instructions.md exist (<= 150 lines), carry their required parts and are indexed by basename | Fully-Automated | command C14 context-split fragments + C5 + C7 (validate-context-discovery root-doc indexing, validate-all-context) | B (added by the 02-10-26 revision; verified live in cycle 4) |
| AC-R1 | worker entry set within its cap (36,000, or 43,000 with operating-instructions.md) | Fully-Automated | command C4 at Gate 3 | B (Gap 32 closed in cycle 4: C4 tests every input path and the cap) |
| AC-R6 | branch deletion only under the logged standing consent | Hybrid | one Approvals Log row per deletion vs git and session state diff; the deletion mechanism is unverified until R4 (vii) and the Gate 6 pilot | D (mechanism unverified: if no tool works the branch stays and the gap is recorded) |
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

Cycle-4 live run of the pinned commands (section 10, C1-C14), 02-10-26, HEAD 0405b2d, clean tree:

| Command | Expected today (plan) | Observed | Match |
|---|---|---|---|
| C1 | 3 lines (20, 36, 48) | 3 lines (20, 36, 48) | yes |
| C2 | 8 lines | 8 lines (CLAUDE.md 46, 50, 52, 59; AGENTS.md 50, 56, 58, 65) | yes |
| C3 | MISSING x2, total, rc=1 | MISSING north-star.md, MISSING current-state.md, total=269986, rc=1 | yes (the quoted 240454 is stale: cosmetic) |
| C4 | not runnable (no envelope) | scratch fixtures only: silent under-count on a missing input, no pass/fail | n/a, Gap 32 |
| C5 | rc=1 (1,223 lines) | rc=1, 1223 lines | yes |
| C6 | prints the base set while F4 is absent | ranges re-read: changelog 33-568 = 536 lines / 45,025 B; Open Questions 967, References 1106, Scan Metadata 1167-1223; command text unchanged since the cycle-3 positive and negative runs | yes |
| C7 | context-discovery 1 failure, others 0; plan-inventory 0 failures / 6 warnings | context-discovery 1, skills 1, guide-sync 1, parity 0 failures / 18 warnings, plan-inventory 0 / 6, wiring, discovery, portability, all-context 0, routing in sync | yes |
| C8 | 11 hits, all in all-context.md | 11 hits at 95, 373, 446, 581, 582, 910, 955, 957, 962, 964, 1020 (+3 stderr lines for the missing new docs) | yes |
| C9 | no output | no output | yes |
| C10 | exit 1 at the first test | exit 1 at the first test | yes |
| C11 | MISSING T1 T1b T3 T4 T5 T7 T8 T23 T26 T27 T28 | exactly that list | yes |
| C12 | file absent today | grep: No such file or directory | yes |
| C13 | no output; plan validator 0 failures | no output; 0 failures, 0 warnings | yes |
| C14 | 12 MISSING, 16 FAIL, 210 comm lines | 12 MISSING, 16 FAIL, 210 comm lines | yes |

Cycle-4 gap re-verification (Gaps 31-32 and cosmetic items c1-c9, each re-checked live in cycle 5, 03-10-26, HEAD 2d0e545):

| Item | Result | Evidence (cycle 5, executed) |
|---|---|---|
| Gap 31 Gate 2 order omits F16/F17 | CLOSED | the Gate 2 execution order now reads R14 -> R13 -> F1, F2, F3 -> F16, F17 -> F4 -> F5 -> F7 + F11 -> F6 -> F8 -> F15 -> R4 (vii); F16/F17 come after F1 (F16 is written for the new North Star) and before F4/F5, so F5's routing rows and pointers name files that already exist; no step reads a file that a later step creates; the risk row 'Slimming loses knowledge' states the carved sections are rewritten into F16/F17 with the base text preserved in git at `<base>` |
| Gap 32 C4 silent under-count, no cap test | CLOSED | C4 run on seven scratch cases: ok without OPS total=31000 cap=36000 rc=0; ok with OPS total=38000 cap=43000 rc=0; missing TASK prints MISSING, rc=1; missing OPS prints MISSING, cap=43000, rc=1; envelope 9,000 bytes rc=1; over cap 46000/36000 rc=1; over cap with OPS 53000/43000 rc=1; and today (missing envelope in the repo) prints MISSING and rc=1, so it is not vacuous |
| c1 C3 total varies with plan size | LANDED | C3 today prints MISSING for north-star.md and current-state.md, total=297202 (the plan file grew; the note says the number varies), rc=1 |
| c2 operating-instructions.md byte cap | LANDED | C14 carries the `wc -c <= 7000` line; on the scratch fixture an 8,000-byte file prints exactly that FAIL line |
| c3 frontmatter for the six new context docs | LANDED and CORRECT | spec matches the existing docs (all-tests.md, all-planning.md, all-data-sources.md use name: context:<slug>, description, keywords, date). Scratch clone with six docs in that format: before indexing validate-context-discovery fails exactly the six unindexed root docs plus the 1-item baseline; after naming the six by basename in all-context.md: 1 failure (baseline), 0 warnings; a doc without keywords adds exactly one warning (so the spec's statement is accurate); discover-context --check-routing stays in sync; validate-all-context 0 failures |
| c4 F2/F3 presence checks | LANDED | C14 has the commit-stamp and UTC checks (`[0-9a-f]{7,40}`, `UTC`) and six decisions.md field checks; a current-state.md without a commit-like token prints exactly its FAIL line. Presence only, accuracy stays in the Hybrid user review |
| c5 branch-delete mechanism in R4 (vii) | LANDED | R4 (vii) names a GitHub branch-delete tool or `git push origin --delete` as UNVERIFIED, not dry-runnable, confirmed by the Gate 6 pilot, fallback branch stays and the row says 'deletion deferred' |
| c6 Approvals Log row ordering | LANDED | section 4 item 4: write the row (status pending) first, then delete, then update to done / failed / deletion deferred; AC-R6 and Gate 6 row read consistently |
| c7 TL;DR and section 5 | LANDED | TL;DR names the 43 KB cap and 'eight small things' (north-star, current-state, decisions, architecture, operating-instructions, archive/index, envelope template, report template = 8); section 5 'Selective context' excludes architecture.md; no section 11 reference remains outside this contract's history (Verification Evidence is unnumbered by design); every 'section N' reference outside the contract resolves to an existing numbered section |
| c8 'worker task branches' defined | LANDED | section 4 item 4 and TL;DR define the pattern `claude/<task-id>-<slug>` as branches the Master Planner created for a registry task and exclude `claude/p1-pipeline` and `claude/p2-deploy` explicitly |
| c9 validate-all-context warnings after F5 | LANDED | risk row says warnings may appear and the gate is no new failure; the pointer lines can keep the References / Open Questions wording |

Cycle-5 live run of the pinned commands (section 10, C1-C14), 03-10-26, HEAD 2d0e545, clean tree:

| Command | Expected today (plan) | Observed | Match |
|---|---|---|---|
| C1 | 3 lines (20, 36, 48) | 3 lines (20, 36, 48) | yes |
| C2 | 8 lines | 8 lines (CLAUDE.md 46, 50, 52, 59; AGENTS.md 50, 56, 58, 65) | yes |
| C3 | MISSING x2, a total that varies with plan size, rc=1 | MISSING north-star.md, MISSING current-state.md, total=297202, rc=1 | yes |
| C4 | not runnable today; MISSING and rc=1 | MISSING and rc=1 on a missing envelope; six pass/fail scratch cases as in the table above | yes |
| C5 | rc=1 (1,223 lines) | rc=1, 1223 lines | yes |
| C6 | ranges 33-568 changelog; Open Questions 967, References 1106, Scan Metadata 1167-1223 | `grep -n '^## '` on the base gives exactly those headings; faithful scratch F4 prints 0 lines; one dropped line prints exactly that line | yes |
| C7 | context-discovery 1 failure, others 0; plan-inventory 0 failures / 6 warnings | context-discovery 1, skills 1, guide-sync 1, parity 0 failures / 18 warnings, plan-inventory 0 / 6, wiring, protocol-discovery, portability, agent-frontmatter, invocation-wiring, all-context 0; routing in sync; literal path count 9 (CLAUDE.md) and 12 (AGENTS.md) | yes |
| C8 | 11 hits, all in all-context.md | 11 hits at 95, 373, 446, 581, 582, 910, 955, 957, 962, 964, 1020 (+3 stderr lines for the three missing new docs) | yes |
| C9 | no output | no output | yes |
| C10 | exit 1 at the first test | rc=1 | yes |
| C11 | MISSING T1 T1b T3 T4 T5 T7 T8 T23 T26 T27 T28 | exactly that list | yes |
| C12 | file absent today | grep: No such file or directory, rc=2 | yes |
| C13 | no output; plan validator 0 failures | no output (tracked, staged, untracked); validate-plan-artifact 0 failures, 0 warnings | yes |
| C14 | 12 MISSING, 31 FAIL, 210 comm lines, 256 stdout lines | 12 MISSING, 31 FAIL (the 15 cycle-4 additions plus the 16 earlier), 210 comm lines, 256 stdout lines; on a complete scratch fixture it prints no MISSING, no FAIL and no comm line, only the informational byte lines | yes |


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
Failing stub:
test("should have architecture.md and operating-instructions.md within 150 lines with their required parts", () => { throw new Error("NOT IMPLEMENTED - TDD stub: context split docs exist with required parts") })
Failing stub:
test("should fail the worker entry-set check when an input file is missing or the cap is exceeded", () => { throw new Error("NOT IMPLEMENTED - TDD stub: C4 pass/fail with missing-input assertion") })

C-4 reconciliation: the `strategy` column carries only Fully-Automated / Hybrid / Agent-Probe. Known-Gap is never a strategy; it appears only as the named residuals below (gap-resolution D).

Legacy line form:
- all-context slimming: [Fully-automated: wc -l, validate-all-context, validate-context-discovery (baseline-aware), --check-routing]
- protocol docs: [Fully-automated: validate-protocol-wiring, validate-protocol-discovery, validate-kit-portability]
- entry files (Gate 3): [Fully-automated: @-import grep (C1), role-neutral grep (C2), wc -c tables (C3, C4), retired-wording grep (C8), ENTRY-SET diff (C10)] | [agent-probe: fresh-session probe per role]
- registry/archive: [hybrid: user review + git log/file-existence re-checks + C11]
- master planner lifecycle (Gate 6): [agent-probe: pilot task]
- worker self-merge conditions: [known-gap: platform enforcement unavailable, documented below, gap-resolution D]

Dimension findings (cycle 5, closing pass, 03-10-26):
- Infra fit: PASS - baseline unchanged by JSON parse (context-discovery 1 failure, skills 1, guide-sync 1, parity 0 failures / 18 warnings, plan-inventory 0 / 6, all others 0); every cited fact still holds at HEAD 2d0e545; the pinned rev 6 SHA 18ffd4f is readable (43,484 bytes). Frontmatter spec for the six new context docs verified against validate-context-discovery, validate-all-context and the routing check in a scratch clone (1 baseline failure, 0 warnings after basename indexing).
- Test coverage: PASS - C1-C14 behave exactly as stated; C4 now tests every input path and the cap (seven scratch cases); C14 is non-vacuous (31 FAIL / 12 MISSING / 210 comm lines today, nothing on a complete fixture, exactly one FAIL line per injected defect). Residual, cosmetic only: C14's F2 commit-stamp check is a presence regex that a hex-only word could satisfy; the Hybrid user review at Gate 2 close covers accuracy.
- Breaking changes: PASS - unchanged from cycle 4 (validator-required headings and the literal router path kept by the F5 table; role-neutral CLAUDE.md breaks no validator, hook or agent; root docs never change the GENERATED routing block).
- Security surface: PASS - branch-deletion consent recorded consistently and scoped to merged worker task branches; row written before deletion; deletion mechanism honestly UNVERIFIED with a safe fallback (the branch stays). Open Question 10 and Open Question 12 remain USER DECISIONS, non-blocking for Gate 2 start.
- Section 2 / Gate 2 file set and order (F1-F8, F11, F15-F17): PASS - order is dependency-consistent (F1 -> F16/F17 -> F4 -> F5 -> F7 + F11 -> F6 -> F8 -> F15 -> R4 (vii)); arithmetic consistent (198-line F5 table, 94-line router budget = 15+3+10+15+25+26, caps 64,000 / 36,000 / 43,000).
- Section 3 registry / R14 feasibility: PASS - C11 fails today for exactly the 11 expected IDs; rev 6 rows unchanged.
- Section 4 lifecycle spec: PASS - acceptance rule, standing authorization, registry-writer rule, worker lane, consent paragraph and approvals-log ordering read consistently.
- R13 salvage: PASS - unchanged; outcome checked by C14.
- Section 7 housekeeping H1/H2/H3: PASS - unchanged.
- Section 10 / AC-R1 to AC-R11 and section 9 gate roadmap: PASS - no stale 288, 87, 90-line, 56-line, T0-T4 or 16-FAIL figure outside this contract's history (grep-checked); section cross-references resolve.

Dimension findings (cycle 4, history, superseded by the block above):
- Infra fit: PASS - baseline re-confirmed by JSON parse; every cited fact re-queried live (rev 6 SHA 18ffd4f, exciting-meitner 16-file diff with 11 files under lse-data-verification, ci.yml job names with the em dash at lines 41 and 57, 339 tracked `.agents/skills` files, 15 agents, 33 skills, `web/tsconfig.tsbuildinfo` tracked and absent from `.gitignore`, T-row counts 18 on main and 20 on rev 6, 14 remote refs = 12 named branches + main + session branch). Validator behaviour for the carve-out confirmed from source (required headings, basename indexing, routing generation, brand scan is product names only). Cosmetic notes only.
- Test coverage: CONCERN - C1-C3, C5-C14 behave exactly as stated; C14 and the AC-R11 fragments are non-vacuous (they fail today). Remaining: C4 under-counts silently when an input path is missing and has no pass/fail test, the defect class fixed for C3 in Gap 29a (Gap 32; Gate 3 command, but one line to fix).
- Breaking changes: PASS - the F5 carve-out keeps every validator-required heading and the literal router path; root docs never change the GENERATED routing block; role-neutral CLAUDE.md breaks no validator, hook or agent (cycle 3 search unchanged); new docs are outside the kit-portability brand scan except master-planner.md under process/development-protocols, which carries no product-brand literal.
- Security surface: PASS - the branch-deletion consent is recorded consistently and is scoped to merged worker task branches; it does not reach the 12 existing branches or any worktree; the deletion mechanism is honestly unverified until R4 (vii) and the Gate 6 pilot with a safe fallback (the branch stays). Open Question 10 and Open Question 12 remain USER DECISIONS, non-blocking for Gate 2 start.
- Section 2 / Gate 2 file set and order (F1-F8, F11, F15-F17): CONCERN - mechanically feasible and arithmetically consistent (198-line F5, 94-line router, 64,000 / 36,000 / 43,000 caps); the Gate 2 execution order omits F16 and F17 (Gap 31).
- Section 3 registry / R14 feasibility: PASS - Gap 24 collision closed; rows and rev 6 SHA verified; C11 fails today for exactly the 11 expected IDs.
- Section 4 lifecycle spec: PASS - acceptance rule, standing authorization (a)-(f), registry-writer rule, worker lane, verifiability consequence and the consent paragraph read consistently; one cosmetic ordering note (Approvals Log row before or after the deletion).
- R13 salvage: PASS - 16 files, destinations and the five removed `active/` copies unchanged.
- Section 7 housekeeping H1/H2/H3: PASS - H2 now says untrack and ignore; H3 excludes the consent from the 12 branches.
- Section 10 / AC-R1 to AC-R11 and section 9 gate roadmap: PASS apart from C4 (Gap 32); no stale 288, 90-line, 87-line or 43-48 KB figure remains outside history (grep-checked); section cross-references resolve.

Dimension findings (cycle 3, history, superseded by the block above):
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
- real per-session token usage is unmeasured: known-gap: documented, backlog stub is F15 (gap-resolution D; checked by C14)
- symlinked `.agents/skills` on the user's Windows PC is unverified: known-gap: documented, backlog stub is F15 (gap-resolution D; checked by C14)
- R12 deploy runtime behaviour (PowerShell, Task Scheduler, Tailscale) verifiable only on the user's PC: known-gap: documented, hybrid user-run (gap-resolution D; backlog stub is F15, checked by C14)
- MCP tool names named by the plan: unverifiable from this session; resolved by Gate 2 R4 step (vii) run by the orchestrator session (non-blocking, already in the plan's Gate 2 order)
- platform enforcement of self-merge conditions is unavailable on this repo plan: documented residual with compensating controls (done in cycle 1)
- USER DECISION, non-blocking for Gate 2 start: Open Question 10 (control-surface self-merge; T4 bypass; Master Planner merging on a worker's behalf); the worker lane as a direct lane with a compact self-written validate-contract (now Open Question 12); standing consent for branch deletion was GRANTED by the user on 02-10-26 for merged worker task branches only (this supersedes the earlier 'NOT granted' wording)
- orchestrator bookkeeping note (not a plan gap): `results.tsv` has no `# domain: plan` legend line, so validate-autoresearch-log.mjs reports "domain field must be exactly plan or tests"; sibling task folders have the same shape; the orchestrator adds the legend when it appends the cycle 3 row
- branch-deletion mechanism (GitHub branch-delete tool or `git push origin --delete`) is UNVERIFIED from this session and may be absent or proxy-blocked: known-gap: documented, resolved at R4 step (vii) and the Gate 6 pilot; fallback is that the branch stays and the gap is recorded (no safety consequence)
- none unresolved (cycle 5): Gaps 31-32 CLOSED and cosmetic items c1-c9 LANDED, all verified live; two cosmetic residuals may be accepted as known gaps: (r1) C14's F2 commit-stamp check is presence-only (a hex-only word of 7+ letters could satisfy it; the Hybrid review at Gate 2 close covers accuracy), (r2) validate-all-context may print warnings after the F5 slimming (not a gate; the gate is no new failure versus baseline)

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
- C14 existence and cap checks: not that architecture.md, operating-instructions.md, north-star.md, current-state.md or decisions.md are accurate or complete beyond the named topics and rows; not the byte size of operating-instructions.md (lines only, cosmetic c2)
- the Approvals Log checks: not that a branch deletion is actually possible (no branch-delete tool or push-delete path has been verified) and not that each later automatic deletion adds its row (convention, AC-R6 Hybrid review)

SUPPLEMENT REQUEST (PVL cycle 4, history; both applied and verified closed in cycle 5; exact items; section ids are slugs of `##`/`###` headings in this plan; both are plan-text edits, neither needs the user):
- Gap 31: 2-exact-file-set (the Gate 2 execution order sentence under 'Gate 2 order, R13 file list, F4/F5 definition, F9/F10 dispositions') | Concern: the sentence lists R14 -> R13 -> F1, F2, F3 -> F4 -> F5 -> F7 + F11 -> F6 -> F8 -> F15 -> R4 (vii) and omits F16 (architecture.md) and F17 (operating-instructions.md), although the diagram-revision log says they were added to the Gate 2 order and the Gate 2 row of section 9 lists F15-F17. An execute agent following the order literally could write them last or skip them; F5 deletes (does not move) the Repository Structure, Technology Stack, Key Patterns and Environment sections they are written from, F5's routing rows and pointers name them by basename, and validate-context-discovery fails any root doc that all-context.md does not name | Severity: CONCERN | Suggested addition: insert 'F16, F17 (written from the base all-context.md sections they carve out, read at <base>, and after F1 because F16 is written for the new North Star; before F4 and F5 so F5's rows and pointers name files that already exist)' between 'F1, F2, F3 (...)' and '-> F4', and add one clause to the 'Slimming loses knowledge' risk row saying the carved sections are rewritten into F16/F17 (not moved whole) with the base text preserved in git at <base>
- Gap 32: 10-acceptance-criteria-this-program (command C4, AC-R1) | Concern: C4 has the defect Gap 29a fixed in C3: a missing TASK or OPS path only writes a stderr line and the printed total silently under-counts (scratch run: 34,903 versus 38,903), and the command never tests the cap it quotes ('must print a number <= 36000 (or 43000)') | Severity: CONCERN | Suggested addition: replace C4 with the form below (run on six scratch cases: ok without OPS rc=0, ok with OPS rc=0, missing TASK rc=1 plus MISSING line, missing OPS rc=1 plus MISSING line, envelope over 8,000 bytes rc=1, total over cap rc=1): `ENVELOPE=<path>; TASK=<path>; OPS=` then `MISS=0; for f in CLAUDE.md "$ENVELOPE" "$TASK" ${OPS:+"$OPS"}; do test -s "$f" || { echo "MISSING $f"; MISS=1; }; done`, `CAP=36000; test -n "$OPS" && CAP=43000`, `total=$(cat CLAUDE.md "$ENVELOPE" "$TASK" ${OPS:+"$OPS"} 2>/dev/null | wc -c); echo total=$total cap=$CAP`, `test "$MISS" -eq 0 && test "$(wc -c < "$ENVELOPE")" -le 8000 && test "$total" -le "$CAP"; echo rc=$?`; state 'must print rc=0' and that it is not runnable today (no envelope exists)

COSMETIC (cycle 4 list, history; c1-c9 verified landed in cycle 5) - may be accepted as known gaps (none blocks Gate 2 start; none changes a verdict; the orchestrator can propose acceptance to the user, or fold them into the same supplement at no cost):
- c1: the `total=240454` figure quoted under C3 is true only for the plan size at the time; it was 269,986 in cycle 4 and changes with every plan edit. Say 'a number that depends on the plan file's size'.
- c2: C14 caps architecture.md and operating-instructions.md by lines (<= 150) while the worker-cap arithmetic assumes operating-instructions.md <= 7,000 bytes (150 lines at ~58 B/line is ~8.7 KB). The informational `wc -c` line shows it and C4 enforces the real total at Gate 3; a `test "$(wc -c < process/context/operating-instructions.md)" -le 7000` line in C14 would close it earlier.
- c3: frontmatter for the new context docs (F1, F2, F3, F4, F16, F17: `name: context:<slug>`, `description`, `keywords`, `date`) is not specified; without `keywords` validate-context-discovery adds one warning per doc (warnings, not failures; baseline is 0 warnings) and the docs are not reachable by `discover-context.mjs --match`.
- c4: F2's 'every fact stamped (branch, commit, UTC time, command)' is what the staleness rule depends on (the stamp must be a commit that `git merge-base --is-ancestor` can test), yet C14 checks only that current-state.md exists; F3's six fields are existence-checked only. Reviewed by the Hybrid user review at Gate 2 close; a `grep -cE '[0-9a-f]{7,40}'` line would make F2 measurable.
- c5: R4 step (vii) lists the merge and session tools to verify but not the branch-delete mechanism that operation D says R4 (vii) confirms; one sentence in (vii) naming 'a GitHub branch-delete tool or `git push origin --delete`, UNVERIFIED, cannot be dry-run read-only, confirmed by the Gate 6 pilot, fallback branch stays' would align the cross-reference.
- c6: section 4 item 4 says the Master Planner 'deletes ... and logs one row' (row after), while AC-R6 ('an empty log means no removal is permitted') and the Gate 6 row ('its Approvals Log row exists') read as row before. Say 'write the row, then delete; if the delete fails, mark the row failed'.
- c7: TL;DR states the worker cap as 36 KB only (43,000 with operating-instructions.md is in section 2 and AC-R1); section 5 'Selective context' omits architecture.md from the worker-excluded list; section numbering skips 11 (Verification Evidence is unnumbered); 'seven small things' counts templates as one item.
- c8: `claude/p1-pipeline` and `claude/p2-deploy` fit `claude/<task-id>-<slug>`; they are excluded explicitly and by the registry precondition, but one clause 'worker task branches = branches the Master Planner created for a registry task' would remove the doubt.
- c9: after the F5 slimming, validate-all-context may print warnings (for example no `commit` or `References` wording) because it checks the text for those words; warnings are not gates, but the pointer lines for References and Scan Metadata can keep the words to stay at 0 warnings.

SUPPLEMENT REQUEST (PVL cycle 3, history; all applied and verified closed in cycle 4; exact items; section ids are slugs of `##`/`###` headings in this plan; all are plan-text edits, none needs the user):
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

Plan updates applied (PVL cycle 3, 02-10-26, vc-plan-agent PVL-supplement; every new or changed command was run read-only, positive and negative cases on scratch copies; RE-VERIFIED by vc-validate-agent in cycle 4, see the cycle-3 gap re-verification table above):
- Gap 24: risk tiers renamed RT0-RT4 at every occurrence outside this contract's history (section 4 precedence note and worker lane, section 6 table and budget rule, Open Question 10(a), Blast Radius); naming rule stated in section 3 and section 6 (T# = registry task, RT# = risk tier); `L` not used (it is a Prio value).
- Gap 25: F14 = `git rm --cached` PLUS adding `web/tsconfig.tsbuildinfo` to `.gitignore` (verified absent today); false parenthetical removed; H2, Touchpoints and a Gate 5 form of C9 updated.
- Gap 26: command C14 added (deliverable existence, `## Approvals Log` with an lse-data-verification row, `ROLE: WORKER`, five north-star topics, R13 outcome, rev 6 preservation pinned to 18ffd4f014f4e5ea0f5d654688875a9300b30ab4, informational byte lines); expected today 10 MISSING + 10 FAIL + 210 comm lines; positive and negative verified on a scratch tree; F15 (three backlog stubs) added to the file set, Touchpoints and C14; F8 row extended with the Approvals Log; Gate 2 row and Verification Evidence name C11 and C14.
- Gap 27: C13 now also runs `git diff --cached --check` and the untracked-file loop; the gate is "no output"; verified on a scratch repo.
- Gap 28: C8 widened (`public[ -]later|open up later|other users later|intended to open`): 11 hits today (lines 95, 373, 446, 581, 582, 910, 955, 957, 962, 964, 1020); every "8 hits" statement outside this contract's history updated; line 955 (Equity data provider row), the stale Deployment target row (line 959) and lines 962-964 added to the F5 drop/reword list.
- Gap 29: C3 asserts each input with `test -s`, ends with `test "$total" -le 64000; echo rc=$?`, expected-today note corrected (240454 / rc=1, not "cannot run"); C2 widened to `You are the orchestrator|You do NOT|Your responsibilities|Orchestrator Role` (8 lines today).
- Gap 30: (a) Gate 2 order now F1, F2, F3 before F4 and F5; (b) section 9 Gate 2 row names C11, C13, C14; (c) router budget 90 lines (sum of table rows); (d) Scan Metadata 57 lines; (e) Open Question 12 added (worker lane confirmation, non-blocking); (f) validate-plan-inventory.mjs added to C7 and the baseline table (0 failures, 6 warnings); (g) F9/F10 rows and C7 require the literal `process/context/all-context.md` (counts today 9 and 12).

Plan updates applied (user diagram revision, 02-10-26; user-driven, not a validator gap list; every new or changed command was run read-only, positive and negative cases on scratch copies; RE-VERIFIED by vc-validate-agent in cycle 4 except the two plan-text concerns Gaps 31 and 32):
- Answer 1 (registry): MASTER-PLAN.md stays the board plus registry; mapping sentence added in section 3 (the diagram's task-registry box is MASTER-PLAN.md). No other change.
- Answer 2 (merge): worker self-merge unchanged; one paragraph in section 4 maps the diagram's 'Master Planner Review' box to the Master Planner's registry update plus the post-merge main-CI check.
- Answer 3 (branch archival): NEW STANDING CONSENT of 02-10-26, scoped to merged worker task branches only, recorded in section 4 item 4 (and (iv)), the archive-operations table (operation D; four operations: document archival, mark logically complete, archive_session, branch delete), the Risk accepted table mitigations, section 12 (new accepted-risk row), Open Questions 10(c), 13 and the closing 'Still OPEN' line, F7, F8 (Approvals Log gets a second Gate 2 row and one row per later deletion), C14 (checks the consent row), AC-R6, the Gate 5 and Gate 6 rows, H3, the TL;DR and the goal block. The earlier cycle-1 to cycle-3 statements that consent 'is NOT granted' (Security surface finding, open-gap list, 'Accepted by' note) are history and are left as written; they are superseded by this entry. Not extended to the 12 existing remote branches (per-branch review plus the user's approval; compassionate-goldberg remains a candidate needing approval).
- Answer 4 (context split): F16 architecture.md and F17 operating-instructions.md added to the file set and Gate 2 order; F5 disposition table carved out (Repository Structure 45 to 12, Technology Stack 40 to 12, Key Patterns 25 to 6, Environment 20 to 6, Task Routing 22 to 26; total 288 to 198, cap 300 unchanged, router section budget 90 to 94 lines); validator-required headings, GENERATED block, `Last updated`, literal path kept; PLANNER and WORKER entry-set tables updated (worker loads operating-instructions.md only when the envelope names it, cap 43,000 then); F9/F10 and the portability rule reference both docs by bare name; F12 now links to the RT0-RT4 table that lives in operating-instructions.md; C4 takes an optional OPS file; C8 also scans the two new docs; C14 gains existence, line-cap, data-flow, RT-row and worktree checks (expected-today recomputed: 12 MISSING, 16 FAIL, 210 comm lines); AC-R1 text and new AC-R11; Verification Evidence rows; Touchpoints.
- Diagram wording: worktrees apply to local sessions on the user's PC; cloud workers are isolated by container plus branch (section 4, Isolation model).
- Contract status: cycle 4 re-verified the items above (see the diagram-revision verification table); two plan-text concerns remain (Gaps 31 and 32) plus cosmetic items c1-c9.

Plan updates applied (PVL cycle 4, 02-10-26, vc-plan-agent PVL-supplement; the new C4 and C14 fragments were run read-only on scratch copies, positive and negative cases; RE-VERIFIED by vc-validate-agent in cycle 5, see the cycle-4 gap re-verification table above):
- Gap 31: section 2 Gate 2 execution order now reads ... F1, F2, F3 -> F16, F17 (after F1, before F4 and F5) -> F4 -> F5 ...; the 'Slimming loses knowledge' risk row says the carved sections are rewritten into F16/F17 with the base text preserved in git at `<base>`.
- Gap 32: command C4 replaced by the `test -s` per input form, CAP 36,000 (43,000 with OPS), ending with an rc line. Scratch results: ok without OPS total=31000 rc=0; with OPS total=38000 rc=0; missing TASK rc=1 plus MISSING; missing OPS rc=1 plus MISSING; envelope 9,000 bytes rc=1; over cap rc=1 (46000/36000, 53000/43000). Not runnable today (no envelope): prints MISSING and rc=1.
- c1: C3's quoted total now says it varies with plan size; the gate is the rc line. c2: C14 gains an operating-instructions.md byte cap (<= 7000). c3: frontmatter block specified for the six new context docs (section 2) and checked by C14. c4: C14 gains F2 commit and UTC stamp checks and F3 six-field checks (still existence and presence, not accuracy; accuracy stays in the Hybrid user review). c5: R4 (vii) names the branch-delete mechanism as unverified and not dry-runnable, with the fallback. c6: Approvals Log row is written BEFORE deletion (pending), then updated (done, failed or deletion deferred). c7: TL;DR names the 43 KB cap, 'eight small things', section 5 excludes architecture.md; section numbering (no section 11) left as is on purpose to keep cross-references stable. c8: 'worker task branches' defined; p1-pipeline and p2-deploy excluded. c9: post-slimming validate-all-context warnings noted in the risk row; gate is no new failure versus baseline.
- C14 expected-today line updated to the re-measured counts below the C14 block.

Prior gate (PVL cycle 4, history): conditional, 0 FAILs, 2 CONCERNs (Gaps 31-32) plus 9 cosmetic items; closed by the cycle-4 supplement and verified in cycle 5.
Gate: PASS (0 FAILs, 0 unresolved CONCERNs; PVL cycle 5, 03-10-26, after 4 recorded fix cycles in results.tsv; scope: START of Gate 2 only, F1-F8, F11, F15, F16, F17, R13, R14; Gates 3-6 each re-enter VALIDATE; PHASE_COMPLETE: VALIDATE is legal; EXECUTE of Gate 2 requires the explicit ENTER EXECUTE MODE command)
Accepted by: not required (Gate: PASS, no unresolved concern). Cosmetic residuals r1 and r2 above are recorded as known gaps, not accepted concerns; the orchestrator may mention them to the user. User decisions pending but non-blocking for Gate 2 start: Open Question 10 (control-surface self-merge; RT4 bypass; Master Planner merging on a worker's behalf) and Open Question 12 (worker lane). The standing consent for branch deletion was GRANTED by the user on 02-10-26 (merged worker task branches only) and is not a pending decision.

## Autonomous Goal Block

SESSION GOAL: Master Planner recovery program, Gate 2 (docs/process only): re-verified current-state.md, north-star.md, decisions.md, architecture.md, operating-instructions.md, context-changelog.md, slimmed all-context.md, master-planner.md protocol, MASTER-PLAN.md registry rebuilt from origin/claude/pensive-dijkstra-ko69oi rev 6, archive index skeleton, R13 selective salvage of exciting-meitner.
Charter + umbrella plan: N/A - single plan (process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md)
Autonomy: only what plan section 4 (Standing authorization) records: spawn workers for registry tasks already `approved` (max 3 concurrent, excluding the planner); self-merge/self-archive only when every mechanical condition holds and the worker is sure, otherwise stop at `review`. Branch deletion consent (02-10-26) covers merged worker task branches only, after verified merge, committed report and registry archived; nothing else; no worktree removal. Gate 2 may not start until Gate: PASS, or CONDITIONAL after at least one PVL supplement cycle or explicit user acceptance. See feedback_autonomous_phase_execution.md for autonomy removing approval pauses only.
Hard stops / safety constraints:
- Any write outside process/ in Gates 2-4 (CLAUDE.md and AGENTS.md edits are Gate 3 and need user review before commit)
- Deleting any file or session, or any branch other than a merged worker task branch under the 02-10-26 standing consent; archive_session before the handover report is durable and the merge is verified
- Installs, product code (api/, web/) edits, deploy script changes, network use beyond approved ref-only fetch
- Starting Gate N+1 before VALIDATE writes a contract for it
- Any validator showing a NEW failure versus the recorded baseline in the Validate Contract
Next phase: EXECUTE Gate 2 via vc-execute-agent (opus), scoped to F1-F8 + F11 + F15-F17 + R13 + R14 (order in section 2: R14, R13, F1-F3, F16-F17, F4, F5, F7+F11, F6, F8, F15, then R4 (vii) by the orchestrator session); requires the explicit ENTER EXECUTE MODE command; Gate: PASS written 03-10-26 (PVL cycle 5)
Validate contract: inline in plan (## Validate Contract)
Execute start: wc -l all-context <=300 | validate-context-discovery (failures == baseline) | validate-all-context | discover-context --check-routing | validate-protocol-wiring | validate-protocol-discovery | validate-kit-portability | validate-agent-parity non-strict | validate-plan-inventory (0 failures) | C11 registry IDs | C13 whitespace (tracked, staged, untracked) | C14 deliverables | retired-wording grep (C8) | e2e spec: none | probe: none until Gate 3 | high-risk pack: no (Gate 5 R12 only)

## Validate Contract — Gate 3

Status: CONDITIONAL (pending the single V5 user decision on the live probes; see Open gaps G3-K1)
**CONSUMED 03-10-26:** G3-K1 was decided by the user (route A, headless `claude -p`, cap 1 USD per run); Gate 3 EXECUTE ran, independent EVL was green after one fix cycle, the user accepted the diff. This contract is history; do not reuse it for Gate 4. Closeout: `master-planner-recovery_GATE3-REPORT_03-10-26.md`.
Date: 03-10-26
date: 2026-10-03
generated-by: outer-pvl
Relation to the Gate 2 contract: the Gate 2 contract above is retained as history and is NOT overwritten; it gated the START of Gate 2 only. This section gates the START of Gate 3 EXECUTE only (F9, F10, the master-planner.md additions below, two sample probe inputs, commands C1-C4 and C10 in the corrected forms below). Gates 4-6 re-enter VALIDATE.
Scope: CLAUDE.md and AGENTS.md role-neutral rewrite with one byte-identical ENTRY-SET block; no `@`-imports; AGENTS.md `.agents/skills` correction; additions to master-planner.md so no orchestrator rule vanishes; byte baselines for both entry sets; user review before any commit. Everything is a text file; no product code; the only write targets are CLAUDE.md, AGENTS.md and files under `process/`.

Parallel strategy: sequential (single validate session; Layer 1 and Layer 2 checks ran inline as read-only commands; no sub-agent spawn tool was available here, and nothing was run that changes repo state; scratch files lived in the session scratchpad only)
Rationale: signal score 2/7 (S7: 8 files in the Gate 3 blast radius; S6 weak: governance and approval-gate text that every session loads). Dominant signal is S7, but the two main files must carry a byte-identical block, so one writer is safer than a fan-out. Evidence below was measured live at HEAD 3faeff4 (== origin/claude/pensive-albattani-ou0cgv, clean tree, 2026-10-03T00:44Z).

Live baseline today (read-only runs; every Gate 3 command below was executed on the live tree and its "red today" result recorded):

| Item | Measured today |
|---|---|
| CLAUDE.md | 28,903 B, 440 lines; 9 literal `process/context/all-context.md` |
| AGENTS.md | 37,885 B, 704 lines; 12 literal `process/context/all-context.md` |
| C1 (pinned form) | 3 lines (CLAUDE.md 20, 36, 48), as the plan says |
| C2 | 8 lines (CLAUDE.md 46, 50, 52, 59; AGENTS.md 50, 56, 58, 65), as the plan says |
| C10 | exit 1 at the first test (0 markers in both files), as the plan says |
| C9 Gate 3 form | no output (clean tree) |
| C3 | the Gate 2 files now exist; with TASK = this 200,822-byte plan it prints total=263785 and rc=1, so C3 is only meaningful with a small pinned brief (G3-C3 below) |
| C4 | with a missing envelope: MISSING line, rc=1 |
| Planner files that exist now | router section 5,831 + north-star 5,225 + current-state 6,316 + MASTER-PLAN 16,688 = 34,060 B (the Gate 2 report said 31,397; current-state.md and MASTER-PLAN.md grew by about 2.7 KB in the closeout) |
| Validators (JSON counted) | context-discovery 1 failure (`.agents/skills`), skills 1, guide-sync 1 (README), agent-parity non-strict 0 failures / 18 warnings, plan-inventory 0 / 6, skill-dependencies 0 / 4, all-context, protocol-wiring, protocol-discovery, kit-portability, skill-invocation-wiring, agent-frontmatter, skill-keywords, skill-routing, skill-cross-refs, confusable-skills 0 / 0; `--check-routing` in sync; `git diff --check` clean; validate-plan-artifact on this plan 0 / 0 |

Everything above equals the Gate 2 closeout baseline: no new validator failure appeared when Gate 2 closed.

### Layer 1 and Layer 2 findings

| Question asked | Result | Evidence |
|---|---|---|
| (1) Are C1-C4 and C10 non-vacuous today? | C2, C3, C4, C10 yes; C1 has a FALSE NEGATIVE | C1's regex needs a space or `(` before the `@`: a scratch file with `@process/x.md` at the start of a line printed nothing, while the corrected `(^|[[:space:](])` form printed it. A role-neutral CLAUDE.md could therefore still import a file and pass C1. C10 passes vacuously when both files carry an EMPTY block (BEGIN directly followed by END): scratch test rc=0 with no content, so a non-triviality check is added (G3-5). C3 and C4 need pinned sample inputs (G3-C3, G3-C4) |
| (2) Can CLAUDE.md reach <= 20,000 B and keep every hard rule or a pointer? | YES, with margin | Budget (estimate, execute measures): title, bootstrap guard and session-start pointers 900; ENTRY-SET block 3,800 (cap 5,000); Core Protocol with the RIPER-5 Phase Table 2,400; Phase Transition Rules with the PVL/EVL gates 3,400; QUICK FIX trigger and scope guard 700; model policy 450; Key Principles 650; pointer table for relocated sections 1,500; communication, hooks, resources one-liners 600; total about 14,400 B. Target <= 16,000, hard cap 20,000. AGENTS.md (37,885 now) reaches <= 20,000 the same way (Codex bootstrap, the same block, Phase Table and rules, a compressed agent map, pointers; about 15,000 B). Margin matters: with CLAUDE.md at 20,000 B and an 8,000 B brief the planner set is 62,060 B against the 64,000 cap (1,940 B spare); at 16,000 B it is 58,060 |
| (2b) Which parts are validator-required or relied on? | listed in the next table | read from the validator and hook sources; no hook or agent text depends on the "You are the orchestrator" wording |
| (2c) Rules that live ONLY in CLAUDE.md/AGENTS.md today and would vanish | 5 found | see "Rules at risk" below; G3-7 prints 3 MISSING lines today (the master-planner.md items) and the rest are kept-in-place anchors |
| (3) Role-neutral rewrite and master-planner.md | feasible, with additions | master-planner.md section 2 already has the posture rules (detect/route/monitor, no inline execution, strategy, model, session tools) but not the delegation list ("never research, brainstorm, plan, implement or update rules yourself; delegate; trivial conceptual questions are the one exception") nor the execute-agent preflight ("never let vc-execute-agent infer the plan from ambient state; if several plans exist, ask the user"). Both must be added (about 1.2 KB; the file is 12,705 B now). Frontmatter is untouched, so validate-protocol-discovery and validate-protocol-wiring are unaffected by body additions; the additions must avoid backticked `process/context/<file>` paths other than all-context.md and tests/all-tests.md (kit-portability) |
| (3b) How does a Planner session still get the orchestrator rules, and how does a worker envelope override? | Role Selection inside the ENTRY-SET block; two defects to fix | (i) Role Selection (2) says "read master-planner.md" but the entry-set tables list master-planner.md as on-demand: a planner that obeys it loads 12.7 KB (about 14 KB after additions) outside the measured set. With CLAUDE.md 16,000 B, the planner files 34,060 and a 5,000 B brief the total is 55,060 + 14,000 = 69,060 B, over 64,000. Fix: the block says to read master-planner.md only when dispatching, accepting, merging, spawning workers or updating the registry, and C3 reports a second informational total that includes it; a cap is never raised silently. (ii) CLAUDE.md today says "Never start EXECUTE without explicit approval" (line 390), "ENTER EXECUTE MODE ... ALWAYS spawns vc-execute-agent" (line 374) and "Explicit ENTER EXECUTE MODE" (lines 184, 361). A WORKER told to work in a direct lane would stall waiting for ENTER EXECUTE MODE or spawn a subagent chain. Fix: the worker paragraph states "the envelope is your EXECUTE approval" and every kept planner-only rule is scoped with "In planner posture"; check G3-9 |
| (3c) Check against the user's diagram | consistent | the planner loads north-star, current-state, the registry, the router and a brief; workers load the envelope, the brief and CLAUDE.md; architecture.md and operating-instructions.md stay on demand. The only gap is the master-planner.md accounting in (3b) |
| (4) ENTRY-SET block design and the AGENTS.md falsehood | design sound; falsehood is in 4 places, the plan names one | `.agents/skills` is 339 regular tracked files (mode 100644), not a symlink. AGENTS.md claims a symlink at lines 11, 19-20, 420-421 and 673-674 (and "exposed to Codex through" at 687). F10 says "the false statement"; all must be corrected or removed; check G3-8 prints 4 hits today. Both files can carry the block verbatim only if it avoids Claude-only or Codex-only terms (no "Agent tool", "TeamCreate", "spawn_agent"); say "subagent" generically |
| (5) Fresh-session probe feasibility | cannot be done by a vc-* subagent; see "Probe design" | evidence: this validate subagent was handed the OLD 1,223-line all-context.md (Last updated 2026-09-28) in its loaded context while the file on disk is 193 lines, so a subagent inherits its parent's start-of-session load and is not a fresh load; a subagent that reads files is not a fresh session |
| (6) User-review hard stop | PASS with the procedure below | EXECUTE leaves CLAUDE.md and AGENTS.md uncommitted; a review package is written; the commit waits for the user's explicit OK |
| Mechanical gate caveat | CONCERN (closed here as an orchestrator instruction) | the literal PASS line grep (`grep -c` for the Gate PASS string) is already >= 1 because of the Gate 2 contract, and `wc -l < results.tsv` is already >= 3 (Gate 1/2 cycles, last row HALTED_SUCCESS), so BOTH mechanical VALIDATE-to-EXECUTE checks are satisfied for Gate 3 without any Gate 3 evidence. For Gate 3 the only legal tests are: the Gate line inside this Gate 3 contract (`sed -n '/^## Validate Contract — Gate 3/,/^## Autonomous Goal Block — Gate 3/p' <plan>`), or the user's quoted acceptance. A Gate 3 cycle log needs its own baseline row in results.tsv |

Validator-required or relied-on CLAUDE.md/AGENTS.md content (what the rewrite must keep):

| Item | Who relies on it | Requirement after Gate 3 |
|---|---|---|
| literal `process/context/all-context.md` in BOTH files | validate-context-discovery (`assertContains`) | count >= 1 each (today 9 and 12); G3-6 |
| no backticked concrete `process/context/<file>` outside all-context.md and tests/all-tests.md | validate-kit-portability (scans CLAUDE.md, AGENTS.md, protocols) | north-star.md, current-state.md, decisions.md, architecture.md, operating-instructions.md, context-changelog.md by bare name or markdown link only |
| no brand strings, no stale-workflow strings (`vc:plan`, `process/context/<group>`, `./docs`, `docs-manager`) | kit-portability check (a), context-discovery stale scan (both scan these two files) | do not reintroduce; validators run |
| CLAUDE.md and AGENTS.md are canonical skill-routing surfaces | validate-skill-routing (every skill must appear in AGENTS.md, CLAUDE.md or the generated skills catalog; the catalog covers all 33 today, so slimming does not fail it) | run validate-skill-routing (added to the Gate 3 set; 0 failures today) |
| `## Routing` heading and the "RIPER-5 Phase Table" | orchestration.md lines 887 and 986 cite them by name; orchestration.md is unchanged this program | keep both names in CLAUDE.md |
| stop-validator-sweep, hooks, settings | the sweep's harness group fires on `.claude/` and `process/development-protocols/` paths, not on CLAUDE.md alone; no hook reads CLAUDE.md content | master-planner.md edits will trigger the harness group; read its advisory output |
| agents that cite CLAUDE.md | vc-update-process-agent line 195 ("Current features list in CLAUDE.md and AGENTS.md"): that list does not exist in either file today (pre-existing ghost reference) | cosmetic, see Open gaps |

Rules at risk (live ONLY in CLAUDE.md/AGENTS.md; verified by grepping `.claude/`, `.codex/` and `process/development-protocols/`): (1) "Every response MUST begin with [MODE: ...]" and "Only ONE mode per response" (no other file states them; agents carry their own marker); (2) "Never skip directly to implementation" and "Never start EXECUTE without explicit approval"; (3) the orchestrator delegation list and the trivial-question exception; (4) the execute-agent preflight (one plan file, ask when several, never infer from ambient state; only "pass exactly one plan file path" survives in 08-validate.md); (5) the Bootstrap Guard line. Everything else relocated has its rule at the pointer target (verified by grep: orchestration.md carries the agent-team machinery, the autonomy-removes-approval-pauses-only rule, the QUICK FIX scope guard, skill discovery and the context routing discipline; 08-validate.md carries the /goal block fields; autopilot.md carries the prepend; plan-lifecycle.md the task-folder rules; implementation-standards.md the commit policy; vc-agent-strategy-compare the pre-spawn rule and model policy; vc-context-discovery the 10-field envelope).

Deliberate removal that must be recorded, not silent: CLAUDE.md "Before Any Substantial Task" orders two full `find` listings and a "mandatory gate" before loading any context. That ritual contradicts the minimal entry sets and costs a large listing per session. The skill vc-context-discovery already performs the discovery. The rewrite replaces it with the ENTRY-SET pointers; Gate 3 adds one decisions.md entry (D-9) saying so, with the old text recoverable from git.

### Probe design (the live behavioral proof of AC-R1)

A fresh session can be launched here only three ways; a vc-* subagent reading files is NOT one of them.

| Route | How | Cost and risk | Approval |
|---|---|---|---|
| A. headless fresh process (recommended) | from a scratch copy of the Gate 3 tree, `claude -p "<probe prompt>" --model sonnet --max-budget-usd 1 --output-format stream-json --verbose --no-session-persistence` (the `claude` CLI 2.1.288 is installed here; `--max-budget-usd` hard-caps spend). The transcript lists every Read and tool call, so the assertions are scripted; the JSON result also carries real `usage` and cost, which would give the first MEASURED token baseline (also run once on the pre-Gate-3 tree for a before/after pair) | unmeasured; estimate cents to about 1 USD per probe on sonnet at a 10-20k-token entry load, hard-capped by the flag; 2 probes plus 2 baseline runs about 0.5-4 USD. Unverified: nested `claude -p` inside this container (auth, proxy, child-session variable) may refuse; a one-line feasibility call (`say ok`, cap 0.05) tells first. Hooks in the copied project run (session-init output adds a small unmeasured amount) | needed: it spends the user's money and makes network calls; not covered by the standing authorization (that covers workers for `approved` registry tasks only) |
| B. cloud session | the orchestrator's `create_session(prompt, branch)` (exists only in the orchestrator session) | outward action: the Gate 3 branch must be PUSHED first (PR #13 is open, so a push updates it), no budget flag, runaway risk (needs `interrupt_session`), then `archive_session` needs its own approval; cost unmeasured, probably more than A. The Gate 2 session was reported at about 51 USD, but that was a long opus execute run, not a probe | needed (push plus spend) |
| C. user-run | the user opens a fresh session on the branch and pastes the probe prompt (P1) or the sample envelope (P2) | no agent cost | the user's own action |

Probe prompts (written into the sample files by EXECUTE): P1 PLANNER = "Read the task brief at <path to gate3-probe-brief_REF> and tell me, in one line, the task and which files you loaded to get there. Change nothing." Assertions on the transcript: Read set is a subset of {CLAUDE.md, north-star.md, current-state.md, process/MASTER-PLAN.md, the top of all-context.md up to the Context Group Lifecycle heading, the brief}; no Read of orchestration.md, context-changelog.md, architecture.md, operating-instructions.md, master-planner.md; no Agent or session tool call. P2 WORKER = the contents of gate3-probe-envelope_REF as the first message (first line `ROLE: WORKER`; task: read the brief and write the 11-heading report text in the reply; edit and run nothing that changes state). Assertions: the reply states it is a WORKER; zero Agent, Task or session-tool calls; Read set subset of {CLAUDE.md, envelope, brief}; it does not ask for or wait for ENTER EXECUTE MODE; it produces the 11 headings. One sample per probe is single-run evidence, not proof (a model may behave differently next time).

Cheaper proxy that always runs (no model, no spend): the static gates G3-1 to G3-9 prove bytes, structure, block identity, role-neutral wording, rule survival and the scoped planner rules. They do NOT prove that a model obeys the Role Selection text.

If no probe route is approved: P1 and P2 stay a named residual (gap-resolution C, deferred to the Gate 6 pilot, whose first worker is a real fresh WORKER and whose report field 11 records what it loaded; and D, a backlog stub `process/general-plans/backlog/gate3-live-probes_NOTE_03-10-26.md` created by Gate 3 EXECUTE). Known-Gap is never recorded as a proving strategy.

### Gate 3 command set (all run from the repo root in bash; red-today results were observed live)

```
# G3-1  AC-R1: no @-imports, including at the start of a line (replaces C1 for Gate 3)
grep -nE '(^|[[:space:](])@[A-Za-z0-9./_-]+\.md' CLAUDE.md AGENTS.md
# red today: 3 lines (CLAUDE.md 20, 36, 48). After Gate 3: no output. Verified: the pinned C1 form misses a line-start import, this form catches it.

# G3-2  AC-R1: role-neutral = pinned C2 unchanged
grep -nE 'You are the orchestrator|You do NOT|Your responsibilities|Orchestrator Role' CLAUDE.md AGENTS.md
# red today: 8 lines. After Gate 3: no output.

# G3-3  AC-R1: per-file caps (the sums in C3/C4 would let one oversized file hide behind small others)
for f in CLAUDE.md AGENTS.md; do n=$(wc -c < "$f"); echo "$f $n"; test "$n" -le 20000 || echo "OVER-CAP $f"; done
# red today: OVER-CAP for both (28,903 and 37,885). After Gate 3: no OVER-CAP line. Target for CLAUDE.md is <= 16,000 (advisory).

# G3-C3  AC-R1: planner bytes = pinned C3 with TASK pinned to the sample brief (not this plan)
TASK=process/general-plans/active/master-planner-recovery_02-10-26/gate3-probe-brief_REF_03-10-26.md
# then run the pinned C3 block unchanged; must print rc=0. Also print the informational total with master-planner.md added
# (cat ... process/development-protocols/master-planner.md | wc -c): reported, never used to raise the cap.
# red today: the brief does not exist, so C3 prints MISSING and rc=1.

# G3-C4  AC-R1: worker bytes = pinned C4 with the two sample files
ENVELOPE=process/general-plans/active/master-planner-recovery_02-10-26/gate3-probe-envelope_REF_03-10-26.md
TASK=process/general-plans/active/master-planner-recovery_02-10-26/gate3-probe-brief_REF_03-10-26.md
# then run the pinned C4 block unchanged (OPS empty, then once with OPS=process/context/operating-instructions.md); both must print rc=0.
# also: head -1 "$ENVELOPE" must equal exactly: ROLE: WORKER
# red today: MISSING lines, rc=1.

# G3-5  AC-R4: pinned C10 (exactly one marker per file, identical blocks) PLUS non-triviality of the block
for f in CLAUDE.md AGENTS.md; do b=$(sed -n '/ENTRY-SET:BEGIN/,/ENTRY-SET:END/p' "$f"); s=$(printf '%s' "$b" | wc -c)
  for t in 'ROLE: WORKER' 'PLANNER' 'WORKER' 'north-star.md' 'current-state.md' 'MASTER-PLAN.md' 'all-context.md' 'master-planner.md' 'operating-instructions.md' 'architecture.md' 'EXECUTE approval'; do
    printf '%s' "$b" | grep -qF -- "$t" || echo "MISSING-TOKEN $f: $t"; done
  test "$s" -le 5000 || echo "BLOCK-TOO-BIG $f $s"; done
# red today: every token MISSING for both files. Verified on scratch files: an empty BEGIN/END pair passes C10 (rc=0) but prints MISSING-TOKEN here;
# a one-word drift makes C10 exit 1. After Gate 3: C10 exit 0 and no line from this loop.

# G3-6  literal path present in both files (validate-context-discovery needs it)
for f in CLAUDE.md AGENTS.md; do test "$(grep -c 'process/context/all-context.md' "$f")" -ge 1 || echo "MISSING-LITERAL $f"; done
# today: no output (9 and 12). After Gate 3: still no output.

# G3-7  AC-R1/AC-R4: rule survival (rules that exist only in CLAUDE.md today stay in place or move with a pointer)
ck(){ grep -qE -- "$2" "$1" 2>/dev/null || echo "MISSING-RULE [$3] /$2/ not in $1"; }
ck CLAUDE.md 'Every response MUST begin with' "mode prefix"
ck CLAUDE.md 'Only ONE mode per response' "one mode per response"
ck CLAUDE.md 'Never skip directly to implementation' "no skipping to implementation"
ck CLAUDE.md 'Never start EXECUTE without explicit approval' "explicit EXECUTE approval (planner posture)"
ck CLAUDE.md 'directly on .?main' "commit policy"
ck CLAUDE.md '^## Routing' "orchestration.md cites ## Routing"
ck CLAUDE.md 'RIPER-5 Phase Table' "orchestration.md cites the Phase Table"
ck CLAUDE.md 'Bootstrap Guard|vc-setup' "bootstrap guard"
ck CLAUDE.md 'MUST NOT be emitted' "PVL: no PHASE_COMPLETE after first-pass CONDITIONAL"
ck CLAUDE.md 'wc -l < results\.tsv' "PVL gate (b)"
ck CLAUDE.md 'vc-tester' "EVL independent confirmation"
ck CLAUDE.md 'No inline execution' "no inline execution (planner posture)"
ck CLAUDE.md 'QUICK_FIX_ABORT|Scope guard' "quick-fix scope guard"
ck CLAUDE.md 'EXECUTE = opus' "model policy"
ck CLAUDE.md 'orchestration\.md' "pointer orchestration.md"
ck CLAUDE.md 'autopilot\.md' "pointer autopilot.md"
ck CLAUDE.md 'plan-lifecycle\.md' "pointer plan-lifecycle.md"
ck CLAUDE.md 'communication-standards\.md' "pointer communication-standards.md"
ck CLAUDE.md 'discover-skills\.mjs' "skill discovery Step 0"
ck process/development-protocols/orchestration.md 'full machinery' "agent-team machinery (target)"
ck process/development-protocols/orchestration.md 'approval pauses ONLY' "autonomy removes pauses only (target)"
ck process/development-protocols/orchestration.md 'Scope guard' "quick-fix scope guard (target)"
ck process/development-protocols/orchestration.md 'routers, not the full knowledge' "context routing discipline (target)"
ck process/development-protocols/orchestration.md 'Skill Discovery' "skill discovery (target)"
ck process/development-protocols/vc-system-behavior/08-validate.md 'Execute start:' "/goal block format (target)"
ck process/development-protocols/vc-system-behavior/08-validate.md 'Pass exactly one plan file path' "execute preflight (target)"
ck process/development-protocols/autopilot.md 'AUTOPILOT CONTEXT' "autopilot prepend (target)"
ck process/development-protocols/plan-lifecycle.md 'Task-Folder' "task-folder framework (target)"
ck process/development-protocols/implementation-standards.md 'Commit on .main. by default' "commit hygiene (target)"
ck .claude/skills/vc-agent-strategy-compare/SKILL.md 'Orchestrator Pre-Spawn Rule' "pre-spawn recommendation (target)"
ck .claude/skills/vc-context-discovery/SKILL.md 'Context Envelope' "10-field envelope (target)"
ck process/development-protocols/master-planner.md 'never (research|brainstorm)|do(es)? not (research|brainstorm)|delegate' "delegation list moved here"
ck process/development-protocols/master-planner.md 'trivial question' "trivial-question exception moved here"
ck process/development-protocols/master-planner.md 'infer the plan|ambient state' "execute-agent preflight moved here"
# red today: exactly 3 MISSING-RULE lines (the three master-planner.md items; they must be ADDED). Verified on a scratch tree: with the three
# additions it prints nothing, and deleting one rule line from the scratch CLAUDE.md prints exactly that rule. After Gate 3: no output.
# (Rules marked "(planner posture)" may be reworded, but the quoted anchor phrase must remain so the check stays mechanical.)

# G3-8  AC-R4: AGENTS.md makes no false claim that .agents/skills is a symlink (it is 339 tracked regular files until H1)
grep -nEi 'is (already )?a symlink|symlink to|resolves to the same folder|both places automatically|through the .?\.agents/skills' AGENTS.md
# Repaired 03-10-26 (UPDATE PROCESS, Gate 3 closeout): the plan text of this command was truncated here and a duplicate of the Resume and Phase Completion Rules
# text was spliced into the middle of it; the command is reconstructed (verified: 5 matching lines on the pre-Gate-3 AGENTS.md, no output on HEAD 0b3c9bf) and the splice removed.
# red today: 4 claim sites, 5 matching lines on the pre-Gate-3 file (lines 11, 19, 20, 420 and one more; the exact line count is not the gate). After Gate 3: no output (any retained statement says: tracked copy until H1 lands).

# G3-9  AC-R1: planner-only rules are scoped so a WORKER is not told to stall or to spawn
grep -nE 'ALWAYS spawns|No inline execution' CLAUDE.md AGENTS.md | grep -vE 'posture'
# red today: 1 line (CLAUDE.md 374). After Gate 3: no output (each such line says "In planner posture" or "orchestrator posture").

# G3-10 validator set: failures and warnings equal the baseline in the table above (compare messages, not only counts)
node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs
node .claude/skills/vc-generate-context/scripts/validate-all-context.mjs
node .claude/skills/vc-context-discovery/scripts/discover-context.mjs --check-routing
node .claude/skills/vc-audit-vc/scripts/validate-protocol-wiring.mjs
node .claude/skills/vc-audit-context/scripts/validate-protocol-discovery.mjs
node .claude/skills/vc-audit-vc/scripts/validate-kit-portability.mjs
node .claude/skills/vc-audit-vc/scripts/validate-agent-parity.mjs
node .claude/skills/vc-audit-vc/scripts/validate-guide-sync.mjs
node .claude/skills/vc-audit-vc/scripts/validate-skill-invocation-wiring.mjs
node .claude/skills/vc-audit-context/scripts/validate-skill-routing.mjs
node .claude/skills/vc-audit-plans/scripts/validate-plan-inventory.mjs
node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md

# G3-11 scope and whitespace: pinned C9 Gate 3 form and pinned C13, unchanged (no output)
```

### Test gates (5-column table; Gate 3 scope; strategies are the three proving strategies only)

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-R1 | no `@`-import survives, including a line-start one | Fully-Automated | G3-1 (red today, 3 lines) | B (corrected from pinned C1) |
| AC-R1 | CLAUDE.md and AGENTS.md are role-neutral | Fully-Automated | G3-2 (red today, 8 lines) | A |
| AC-R1 | each file <= 20,000 B (target CLAUDE.md <= 16,000) | Fully-Automated | G3-3 (OVER-CAP today) | B |
| AC-R1 | planner entry set <= 64,000 B on a pinned brief | Fully-Automated | G3-C3 | B (sample brief added) |
| AC-R1 | worker entry set <= 36,000 B (43,000 with operating-instructions.md); envelope <= 8,000; first line `ROLE: WORKER` | Fully-Automated | G3-C4 | B (sample envelope added) |
| AC-R4 | one identical, non-empty ENTRY-SET block in both files | Fully-Automated | pinned C10 + G3-5 | B (non-triviality added) |
| AC-R4 | literal `process/context/all-context.md` in both files | Fully-Automated | G3-6 | A |
| AC-R1, AC-R4 | no orchestrator or governance rule lost in the slimming | Fully-Automated | G3-7 (3 MISSING today; scratch-verified both ways) | B |
| AC-R4 | AGENTS.md carries no false symlink claim | Fully-Automated | G3-8 (4 hits today) | B |
| AC-R1 | planner-only rules scoped, worker not told to stall or spawn | Fully-Automated | G3-9 (1 line today) | B |
| AC-R4 | no new validator failure or warning versus baseline | Fully-Automated | G3-10 | A |
| AC-R8 | only CLAUDE.md, AGENTS.md and `process/` changed; no whitespace or conflict-marker errors | Fully-Automated | pinned C9 Gate 3 form; pinned C13 | A |
| AC-R1 | a fresh PLANNER session reaches a task brief on the planner set only | Agent-Probe | P1 by route A, B or C (needs the user's approval) | C (Gate 6 pilot and the user's next fresh session) plus D (backlog stub) if not run |
| AC-R1 | a fresh WORKER session states ROLE: WORKER, spawns nothing, does not wait for ENTER EXECUTE MODE, reads only its set | Agent-Probe | P2 by route A, B or C (needs the user's approval) | C and D as above |
| AC-R9 | token figures labelled measured or unmeasured; real before/after tokens only if route A runs | Hybrid | review of the Gate 3 report (+ probe `usage` if run) | D (`token-usage-telemetry_NOTE_02-10-26.md` already exists) |
| user review | the user has seen the rewritten files before any commit | Hybrid | review package + the user's explicit OK, see below | A |

Failing stub:
test("should have no @-import in CLAUDE.md or AGENTS.md including line-start", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G3-1 red today, 3 lines") })
Failing stub:
test("should be role-neutral in both entry files", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G3-2 red today, 8 lines") })
Failing stub:
test("should keep each entry file at or under 20,000 bytes", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G3-3 OVER-CAP today") })
Failing stub:
test("should keep the planner entry set at or under 64,000 bytes on the sample brief", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G3-C3 MISSING today") })
Failing stub:
test("should keep the worker entry set at or under its cap on the sample envelope", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G3-C4 MISSING today") })
Failing stub:
test("should carry one identical non-empty ENTRY-SET block in both files", () => { throw new Error("NOT IMPLEMENTED - TDD stub: C10 exit 1 and G3-5 MISSING-TOKEN today") })
Failing stub:
test("should lose no orchestrator or governance rule", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G3-7 prints 3 MISSING-RULE today") })
Failing stub:
test("should make no false symlink claim in AGENTS.md", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G3-8 4 hits today") })
Failing stub:
test("should scope planner-only rules so a worker is not blocked", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G3-9 1 line today") })

Legacy line form (retained so existing contract consumers still parse):
- entry-file structure: [fully-automated: G3-1, G3-2, G3-3, G3-5, G3-6, G3-8, G3-9] | entry-set bytes: [fully-automated: G3-C3, G3-C4 on sample files] | rule survival: [fully-automated: G3-7] | validators: [fully-automated: G3-10] | scope: [fully-automated: C9 Gate 3 form, C13] | fresh-session behavior: [agent-probe: P1, P2, needs user approval] | tokens: [hybrid: Gate 3 report review] | user review: [hybrid: review package]

Execute-agent instructions (concerns that the plan text cannot hold; EXECUTE must follow all):

| # | Instruction |
|---|---|
| E1 | Order of writes: master-planner.md additions first, then the two sample REF files, then decisions.md entry D-9, then CLAUDE.md, then AGENTS.md (the block copied byte for byte), then run the gates. The rewritten CLAUDE.md is read by every subagent spawned after it is written (vc-tester included), so write it LAST. Keep the old text recoverable: do not commit; `git checkout -- CLAUDE.md AGENTS.md` restores it before the user's OK |
| E2 | master-planner.md additions (about 1.2 KB): the delegation list ("a session in orchestrator posture never researches, brainstorms, plans, implements or updates rules itself; it delegates to vc-research-agent, vc-innovate-agent, vc-plan-agent, vc-execute-agent and vc-update-process-agent; trivial conceptual questions are the one exception") and the preflight ("before spawning vc-execute-agent confirm exactly one plan file; pass its path in the prompt; if several plans exist ask the user; never let it infer the plan from ambient state"). Keep frontmatter untouched; no backticked `process/context/<file>` path except all-context.md and tests/all-tests.md |
| E3 | Sample probe inputs, both under the plan's task folder, each <= 8,000 B: `gate3-probe-brief_REF_03-10-26.md` (a small realistic task brief, about 3 KB, harmless: asks for a report only) and `gate3-probe-envelope_REF_03-10-26.md` (built from the master-planner.md section 8 template; first line exactly `ROLE: WORKER`; names that brief; operating-instructions.md not named). They are needed by G3-C3 and G3-C4; run validate-plan-inventory afterwards (no new warning) |
| E4 | ENTRY-SET block content: both entry-set lists by bare name; a Role Selection paragraph (worker: "the envelope is your EXECUTE approval, do not wait for ENTER EXECUTE MODE, do not orchestrate, load only the files it names"; planner: read the PLANNER set, and read master-planner.md only when dispatching, accepting, merging, spawning workers or updating the registry); the hard rules that apply to every role (commit policy with the worker-branch exception `claude/<task-id>-<slug>`, phase locking, approval gates, no secrets, "the envelope overrides orchestrator wording but never these hard rules"). Role is decided by the FIRST message only. No Claude-only or Codex-only tool names. Block <= 5,000 B |
| E5 | Every kept planner-only rule (no inline execution, ENTER EXECUTE MODE gates, orchestrator preflight, /goal block duty) is introduced with "In planner posture" so G3-9 passes and a worker reads them as not its own |
| E6 | Keep the headings `## Routing` and the name "RIPER-5 Phase Table" (orchestration.md cites them). Replace "Before Any Substantial Task" with the ENTRY-SET pointers and add decisions.md D-9 (the removed `find` ritual; reason: contradicts the minimal entry sets, vc-context-discovery covers it; old text in git at HEAD 3faeff4). Correct or remove all four AGENTS.md symlink claims (G3-8) |
| E7 | Do not touch orchestration.md, `.claude/`, `.codex/`, validators or hooks. Avoid the scout-block shell strings in every command. No installs, no network, no push, no commit |
| E8 | Measure and report in the Gate 3 report: bytes of CLAUDE.md, AGENTS.md and the block; the planner total (G3-C3) and the informational total including master-planner.md; the worker total with and without operating-instructions.md; all token figures labelled approximate (bytes/4) and the SessionStart hook output, the platform system prompt and the skill list marked as NOT counted. If any cap is missed, report it; never raise a cap without the user |
| E9 | The review package (next block) is written to the task folder as `master-planner-recovery_GATE3-REVIEW_REF_03-10-26.md` before EXECUTE ends |

User-review hard stop (CLAUDE.md and AGENTS.md are high-visibility and govern every future session):
1. EXECUTE edits the working tree only. No commit, no push. The tree stays dirty through the independent EVL run (vc-tester reads the working tree).
2. The review package contains: an old-section to new-location table with bytes (every old CLAUDE.md and AGENTS.md section: kept, scoped, pointer target, or removed with the reason), the full new ENTRY-SET block, the G3-7 and G3-9 outputs (empty), before/after bytes, and the list of rules moved into master-planner.md. The orchestrator also prints `git diff --stat`; the user can read the full diff with `git diff -- CLAUDE.md AGENTS.md`.
3. The orchestrator asks one question: "Commit Gate 3? (Accept / Revise / Revert)". Only an explicit accept leads to a commit, on the same session branch as Gate 2; a push is a separate ask because PR #13 is open and a push updates it. Revise loops back to EXECUTE; Revert is `git checkout -- CLAUDE.md AGENTS.md` (or `git revert <sha>` after a commit).
4. Recommendation to the user: merging PR #13 puts the role-neutral entry files in force for every future session. Prefer to merge only after the probes have run (route A or C) or after the user accepts the residual below.

Dimension findings:
- Infra fit: PASS — every target file exists; no validator, hook or agent depends on the orchestrator wording; the `claude` CLI exists for route A; validators accept the planned structure (portability and wiring rules read from source).
- Test coverage: CONCERN — behavior of a fresh session cannot be proven by any gate runnable without approval; the pinned C1 false negative, the C10 empty-block pass and C3/C4 without pinned inputs are closed here by G3-1, G3-5, G3-C3, G3-C4 (non-vacuity shown on scratch files); live probes are the one open item (G3-K1).
- Breaking changes: CONCERN — five rules live only in the two entry files and the planner-posture rules contradict the worker lane if left unscoped; closed here by E2, E4, E5, G3-7, G3-9 (G3-7 prints 3 MISSING today and is scratch-verified both ways); orchestration.md citations kept by E6.
- Security surface: PASS — text only; role is read from the first message only; the envelope may not override approval gates, commit policy or the no-secrets rule (E4); no secret, deploy or auth surface touched.
- Gate 3 feasibility, F9 (CLAUDE.md): PASS — about 14.4 KB estimated for the 20,000 cap (target 16,000); highest-risk edit: dropping a rule that only lives here (G3-7) or leaving a planner-only rule unscoped (G3-9); write it last (E1).
- Gate 3 feasibility, F10 (AGENTS.md): CONCERN (closed by G3-8, E6) — the symlink falsehood occurs in 4 places, not one; about 15 KB estimated for the 20,000 cap; highest-risk edit: block drift from CLAUDE.md (C10 plus G3-5).
- Gate 3 feasibility, master-planner.md additions: PASS — frontmatter unchanged; wiring and discovery validators unaffected; about 1.2 KB.
- Gate 3 feasibility, probes and token baseline (R7): CONCERN — see G3-K1 (user decision); without telemetry a real token baseline exists only if route A runs.

Open gaps:
- G3-K1 (the single open decision, needs the user at V5): the live probes P1 and P2. Choose: (A) approve the headless route with a hard cap of 1 USD per probe (and a one-line feasibility call first); (C) the user runs the probes by hand; or (K) accept the residual: no live probe now, deferred to the Gate 6 pilot plus a backlog stub. Until one is chosen the AC-R1 behavioral proof is a named residual and the net gate cannot be a terminal PASS.
- G3-K2 (carried, known): real per-session token usage is unmeasured unless route A runs (`token-usage-telemetry_NOTE_02-10-26.md`).
- G3-K3 (carried, known): AC-R5 and AC-R6 from Gate 2 still await the user's review; they do not block Gate 3.
- Closed inside this contract (no plan supplement needed to proceed): G3-C1 line-start `@` false negative (G3-1); G3-C2 C10 empty-block pass (G3-5); G3-C3 C3 and C4 unpinned inputs (E3, G3-C3, G3-C4); G3-C4 missing per-file caps (G3-3); G3-C5 rules at risk (E2, G3-7); G3-C6 unscoped planner rules (E4, E5, G3-9); G3-C7 master-planner.md accounting (E4, E8); G3-C8 four symlink claims (G3-8); G3-C9 both mechanical VALIDATE-to-EXECUTE greps already satisfied by Gate 2 history (instruction above).
- Cosmetic (may be accepted as known gaps): (1) vc-update-process-agent line 195 and AGENTS.md lines 249-252 refer to a "Current features list" that exists in neither entry file (pre-existing); (2) implementation-standards.md Commit Hygiene says "commit on main by default" without the worker-branch exception (only subagents that read it are affected; a one-line cross-reference is optional); (3) current-state.md (6,316 B) and north-star.md (5,225 B) are over their ~4 KB targets, which is what shrinks the planner margin; (4) MASTER-PLAN row R6 lists C1, C2, C9, C10 and R7 lists C3, C4 (fine, two rows for one gate); (5) validate-skill-dependencies prints 4 baseline warnings.
- Known gaps carried (named residuals): the three F15 backlog stubs; the Windows symlink behavior of `.agents/skills`; platform system prompt, SessionStart hook output and skill listing are outside the byte measure.

What this coverage does NOT prove:
- G3-1, G3-2, G3-9: that the words are absent or scoped, not that a model behaves as a worker; wording can pass these and still be misread.
- G3-3, G3-C3, G3-C4: bytes of files, not tokens; the platform system prompt, the SessionStart hook output, the skill list and anything the model chooses to read beyond the entry set are not counted; the sample brief is small by design, a real brief may be up to 8,000 B.
- G3-5, C10: that the two blocks are identical and non-empty, not that the content is right; the user's review covers that.
- G3-7: that anchor phrases exist at their places, not that the rule reads well or is applied; it cannot see a rule that was never listed.
- G3-8: absence of the false claim, not that every `.agents/skills` mention is correct.
- G3-10: no new validator failure; the baseline failures (context-discovery, skills, guide-sync) stay until Gate 5.
- P1, P2 (if run): one sample each on one model at one time; they do not prove stable compliance, do not cover a planner that is mid-task, and route A runs without the MCP session tools.
- Nothing here proves the Master Planner lifecycle works end to end; that is the Gate 6 pilot.

Plan updates applied by this validate session: none to the plan body (history left as written); the corrections above live in this contract and the orchestrator carries them into EXECUTE through the instructions E1-E9. If the orchestrator prefers the strict path, the SUPPLEMENT REQUEST in the V7 hand-off lists the same items as plan-text additions.

Gate: CONDITIONAL (0 FAILs; one open decision G3-K1; nine in-contract corrections; Gate 3 EXECUTE may start only after the user accepts G3-K1 with route A, C or K, or after one PVL supplement cycle, because first-pass CONDITIONAL is not terminal; scope: START of Gate 3 only)
Accepted by: pending; not accepted by this session. The user decides G3-K1 at V5. Cosmetic items (1)-(5) are recorded as known gaps, not accepted concerns.

## Autonomous Goal Block — Gate 3

SESSION GOAL: Master Planner recovery program, Gate 3 (CLAUDE.md and AGENTS.md role-neutral rewrite with one identical ENTRY-SET block, no @-imports, master-planner.md additions, two sample probe inputs, byte baselines for the planner and worker entry sets).
Charter + umbrella plan: N/A - single plan (process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md)
Autonomy: autonomy removes approval pauses only (feedback_autonomous_phase_execution.md); this block is valid only after the Gate 3 contract above is accepted (G3-K1 decided). The standing authorization of plan section 4 does not cover probes or pushes.
Hard stops / safety constraints:
- No commit and no push before the user's explicit OK on the review package; PR #13 is open, a push updates it
- Writes only to CLAUDE.md, AGENTS.md and files under process/; no api/, web/, .claude/, .codex/, orchestration.md, validator or hook edits
- No probe (headless claude -p, create_session, or any spend or network call) without the user's approval and a cap of 1 USD per probe
- Never raise an entry-set cap without the user; report misses
- No NEW validator failure versus the Gate 3 baseline; avoid the scout-block shell strings
Next phase: EXECUTE Gate 3 via one vc-execute-agent (opus), sequential; then an independent vc-tester (sonnet) re-runs G3-1 to G3-11; then the orchestrator presents the review package; requires the explicit ENTER EXECUTE MODE command
Validate contract: inline in plan (## Validate Contract — Gate 3)
Execute start: G3-1 no @-imports | G3-2 role-neutral | G3-3 per-file caps | G3-C3 planner bytes | G3-C4 worker bytes | C10 + G3-5 identical non-empty block | G3-6 literal path | G3-7 rule survival | G3-8 symlink claims | G3-9 scoped planner rules | G3-10 validators == baseline | C9 Gate 3 form + C13 | e2e spec: none | probe: P1 and P2 only if G3-K1 = A or C | high-risk pack: no

## Validate Contract — Gate 4

**CONSUMED 03-10-26:** G4-K1 was decided by the user (A: install frozen dependencies and run each suite once); Gate 4 EXECUTE ran, independent EVL was green at cycle 0. This contract is history; do not reuse it for Gate 5. Closeout: `master-planner-recovery_GATE4-REPORT_03-10-26.md`.

Status: CONDITIONAL (0 FAILs; one user decision G4-K1 on installs; six in-contract corrections E1-E10 below)
Date: 03-10-26
date: 2026-10-03
generated-by: outer-pvl
Relation to earlier contracts: the Gate 2 and Gate 3 contracts above are retained as history and NOT overwritten (the Gate 3 contract is marked CONSUMED). This section gates the START of Gate 4 EXECUTE only (R8, F12 plus the planner-budget pin). Gates 5 and 6 each re-enter VALIDATE. Because both earlier contracts already satisfy the two mechanical greps (`Gate: PASS` count >= 1; `results.tsv` has 9 lines, so `wc -l` >= 3), those greps prove nothing for Gate 4. The only legal VALIDATE-to-EXECUTE tests for Gate 4 are the Gate line inside this section (`sed -n '/^## Validate Contract — Gate 4/,/^## Autonomous Goal Block — Gate 4/p' <plan>`) or the user's quoted acceptance of G4-K1.
Scope: operating-instructions.md (RT table with full commands, bounded-retry and re-run evidence rules), all-tests.md (link to the RT table, current-evidence block, stale counts labelled), master-planner.md (one executable PLANNER-BUDGET block, brief cap, envelope retry line), current-state.md and MASTER-PLAN.md (trim to their ceilings, R8 row, reconciled totals), decisions.md (D-12), the plan's Status text and section 5 status column, the Gate 4 report. Everything is a text file under `process/`. CLAUDE.md and AGENTS.md are NOT touched by Gate 4 (decision below), so no user-review hard stop applies to a Gate 4 commit; commits still happen only when the user asks.

Parallel strategy: sequential (single validate session; Layer 1 and Layer 2 checks ran inline as read-only commands; no spawn tool was available; scratch files lived in the session scratchpad only)
Rationale: signal score 1/7 (S7: about 9 files in the Gate 4 blast radius). Dominant signal S7, but the numbers in current-state.md, MASTER-PLAN.md, master-planner.md and all-tests.md must reconcile with one another, so one writer is safer than a fan-out. Evidence below was measured live at HEAD 24f3db6 (== origin/claude/pensive-albattani-ou0cgv, clean tree, 2026-10-03T04:57Z).

Live baseline today (read-only; every Gate 4 command below was executed on the live tree and its red-today result recorded):

| Item | Measured today |
|---|---|
| Planner fixed part (router cut 5,831 + CLAUDE.md 13,443 + north-star 5,225 + current-state 8,879 + MASTER-PLAN 18,577) | 51,955 B |
| Pinned C3 with the sample brief (2,979 B) | total=54,934, rc=0 (the earlier 54,592 was arithmetic taken before the final current-state.md refresh grew it by 342 B) |
| With master-planner.md (13,588 B) added | 65,543 B without a brief; 68,522 B with the sample brief; 73,543 B with an 8,000 B brief |
| Worker set, sample envelope 1,132 B + brief 2,979 B | 17,554 B; 22,662 B with operating-instructions.md (5,108 B, 58 lines) |
| Test files in git | 73 pytest files, 30 vitest files, 6 Playwright specs (all-tests.md still describes 4 specs and 35 tests) |
| Test dependencies in this container | NOT installed: no api virtualenv, no web dependency folder; uv 0.8.17, pnpm 10.28.0, node 22.22.0 and chromium under /opt/pw-browsers exist |
| CI on PR #13, run 37098105301 at HEAD 24f3db6 | completed, success; jobs `api — pytest` and `web — vitest, tsc, island build`, steps pytest, vitest, tsc, build islands all success (job logs are not readable from this session, so CI gives pass or fail, not counts) |
| Validators | context-discovery 1 failure; all-context, protocol-wiring, protocol-discovery, kit-portability, skill-keywords 0/0; agent-parity non-strict 0/18; plan-inventory 0/6; `--check-routing` in sync; plan validator 0 failures; `git diff --check` clean. All equal the baseline |

### Layer 1 and Layer 2 findings

| Question asked | Result | Evidence |
|---|---|---|
| (1) What must Gate 4 deliver, and is each part measurable by a non-vacuous command? | Yes for all but two parts | Section 9 row 4 and F12: test policy in all-tests.md, re-measured counts, three suites once, installs need approval. Section 6 policy already lives in operating-instructions.md (Gate 2). Measurable now and red today: RT rows lack full commands (6 MISSING, G4-3), no `same failure` rule, no skip-check snippet and no envelope line (3 MISSING, G4-5), all-tests.md has no link to the RT table and no current-evidence block (5 MISSING, G4-6), no budget block in master-planner.md (G4-2), current-state.md over its ceiling (G4-1), stale totals (4 lines, G4-7). NOT measurable without a user decision: the re-measured counts (G4-10, needs installs) |
| (2) Reconcile the planner totals (63,931 vs 58,100 vs 68,180 vs 54,592) | Reconciled exactly; no testing disagreement remains | 63,931 = 50,343 (C3 with the sample brief, at the gate) + 13,588 (master-planner.md). 58,100 = 63,931 minus the 5,831 B router cut: that tester left the router out of the sum. 68,180 = 54,592 + 13,588, and 54,592 = 50,343 plus the closeout growth of MASTER-PLAN.md (+1,889), current-state.md (+2,221) and CLAUDE.md (+139, the [MODE:] follow-up). Today: 54,934 and 68,522 (current-state.md +342 since). One formula resolves it (below) |
| (2b) Is the 9,408 B headroom real? | No: the real margin is 4,045 B | The 64,000 cap assumed a brief of up to 8,000 B, but the formula measured a 2,979 B sample brief. With an 8,000 B brief the gated total is 59,955 B (headroom 4,045 B). The per-file ceilings below sum to exactly 56,000. A task brief is unbounded in practice (this very plan is 245,318 B), so a brief cap must be written down |
| (2c) Growth trend | Needs a trim rule, not just a cap | Closeouts added about 1.9 KB to MASTER-PLAN.md and about 2.6 KB to current-state.md in Gate 3 alone. current-state.md is 8,879 B against the plan's ~4 KB target and is the only file over a sensible ceiling. MASTER-PLAN.md is at 18,577 B, 423 B under a 19,000 ceiling, so the Gate 4 closeout (R8 row, stamps) would breach it without a trim |
| (3) Do the RT0-RT4 commands exist? | Yes, every one | web/package.json scripts `test`, `test:e2e`, `build:islands`, `build`, `dev` exist; api/pyproject.toml has pytest and the `integration` deselect in `addopts`; ci.yml has jobs `api — pytest` and `web — vitest, tsc, island build` with exactly the steps the table names; ci.yml says it has no e2e and no lint job (true). The same commands appear in both operating-instructions.md and all-tests.md (G4-4 prints nothing today). `pnpm --filter web test` runs from the repo root in CI, so the filter form is CI-proven; `pnpm build:islands` is CI-proven only as `cd web && pnpm build:islands` (cosmetic: write that form in RT3). The plan's section 6 text writes `pnpm build:islands` without a directory, valid only inside web/ (cosmetic; operating-instructions.md is now the single home) |
| (3b) Bounded retries stated and testable? | Stated, but three numbers disagree and one clause is missing | Section 5: "2 per task, 3 per gate". Section 6, operating-instructions.md and the worker envelope: 2. CLAUDE.md: 10-cycle EVL ceiling (cannot change at Gate 4). No rule says that the same failure twice in a row stops the loop. Fix: pin 2 fix cycles for a worker, keep the 10-cycle planner ceiling as the outer bound, add "same failure twice stops at once" (E3). Testable by grep (presence) now; compliance is observable only in a real worker's report, so it is a Gate 6 residual |
| (3c) Test budget per tier and the "no re-run of unchanged tests" mechanism | Budget defined; mechanism half-defined | Budget: RT0 0 full runs, RT1 and RT2 1, RT3 2, RT4 2 plus one vc-tester confirmation (operating-instructions.md). Evidence: report heading 6 already requires command, result, UTC time and commit SHA. Missing: the check a worker runs before re-running. Fix: one skip-check line using `git diff --quiet <sha-of-last-run> HEAD -- <touched paths>` plus a clean `git status --porcelain` for those paths (E4); post-hoc audit at Gate 6: no (command, SHA) pair appears twice in heading 6 |
| (4) Token measurement | Gate 4 needs no probe | See the table below. No new headless run is required; the 0.617 of about 4 USD spent stays as is (about 3.38 USD unspent, never needed here) |
| (5) Ordering and contradictions | Gate 4 first, then 5, then 6; two caveats, six stale statements | See the ordering table below |
| (6) Does Gate 4 touch CLAUDE.md or AGENTS.md? | No | The ENTRY-SET block already states the 64,000 cap and the sets; every Gate 4 rule has a home in operating-instructions.md or master-planner.md. Any edit to either file would fail C9 (Gate 4 form) and G4-8. If EXECUTE believes a cap line in the block must change, it stops and asks the user |

### Pinned planner-budget formula (ONE formula; replaces the informational total of the Gate 3 report)

Planner fixed part = router section of all-context.md (top through the line before `## Context Group Lifecycle`) + CLAUDE.md + north-star.md + current-state.md + MASTER-PLAN.md. Gate: fixed part <= 56,000 B, which guarantees the 64,000 B planner cap for any task brief <= 8,000 B (BRIEF_CAP). Hard ceilings per file (they sum to 56,000): CLAUDE.md 16,000; north-star.md 6,000; current-state.md 8,000 (target <= 7,000); MASTER-PLAN.md 19,000 (target <= 17,500); router 7,000. Reported, never gated and never used to raise the cap: fixed part + master-planner.md (read by every Master Planner session when dispatching) and the same with an 8,000 B brief. Trim rule: whenever headroom under 56,000 is below 3,000 B at a planner session end, trim before closing: (1) current-state.md is rewritten in place, one status block per gate at most, older gate narrative replaced by a link to its report; (2) MASTER-PLAN.md: R-row evidence cells at most 300 B with the report path, rows of finished NEW tasks (status `archived`) move to the archive index, historical T-rows and every C11 ID stay; (3) router: Task Routing Table rows one line each; (4) CLAUDE.md only with the user. The existing C3/G3-C3 form stays valid (a real brief instead of the sample).

### Gate 4 command set (all run from the repo root in bash; red-today results were observed live)

```
# G4-1  AC-R1: budget ceilings and fixed part (the standalone form of the block that EXECUTE writes into master-planner.md)
BRIEF_CAP=8000; FIXED_CAP=$((64000 - BRIEF_CAP)); MISS=0
for f in CLAUDE.md process/context/north-star.md process/context/current-state.md process/MASTER-PLAN.md process/context/all-context.md process/development-protocols/master-planner.md; do test -s "$f" || { echo "MISSING $f"; MISS=1; }; done
over() { n=$(wc -c < "$1"); [ "$n" -le "$2" ] || { echo "OVER-CAP $1 $n > $2"; MISS=1; }; }
ROUTER=$(sed '/^## Context Group Lifecycle/,$d' process/context/all-context.md | wc -c)
over CLAUDE.md 16000; over process/context/north-star.md 6000; over process/context/current-state.md 8000; over process/MASTER-PLAN.md 19000
[ "$ROUTER" -le 7000 ] || { echo "OVER-CAP router $ROUTER > 7000"; MISS=1; }
FIXED=$((ROUTER + $(cat CLAUDE.md process/context/north-star.md process/context/current-state.md process/MASTER-PLAN.md | wc -c)))
MP=$(wc -c < process/development-protocols/master-planner.md)
echo "planner_fixed=$FIXED cap=$FIXED_CAP headroom=$((FIXED_CAP-FIXED))"
echo "info_with_master_planner=$((FIXED+MP)) info_worst_case_brief=$((FIXED+MP+BRIEF_CAP)) gated_worst_case_brief=$((FIXED+BRIEF_CAP)) of 64000"
test "$MISS" -eq 0 && test "$FIXED" -le "$FIXED_CAP"; echo rc=$?
# red today: one line OVER-CAP process/context/current-state.md 8879 > 8000, planner_fixed=51955 headroom=4045, rc=1.
# After Gate 4: no OVER-CAP line, rc=0.

# G4-2  AC-R1: the formula is ONE executable block inside master-planner.md and two runs print the same text
B=process/development-protocols/master-planner.md; S=${TMPDIR:-/tmp}
test "$(grep -c 'PLANNER-BUDGET:BEGIN' $B)" -eq 1 && test "$(grep -c 'PLANNER-BUDGET:END' $B)" -eq 1 || echo "MISSING budget block markers"
sed -n '/PLANNER-BUDGET:BEGIN/,/PLANNER-BUDGET:END/p' $B | grep -v 'PLANNER-BUDGET' > $S/budget.sh
test -s $S/budget.sh || echo "MISSING budget block body"
grep -q 'BRIEF_CAP=8000' $S/budget.sh || echo "MISSING brief cap"
bash $S/budget.sh > $S/r1.txt; bash $S/budget.sh > $S/r2.txt; cmp $S/r1.txt $S/r2.txt && cat $S/r1.txt
# red today: MISSING budget block markers, MISSING budget block body, MISSING brief cap. Scratch-verified: a fixture copy of master-planner.md with the
# block appended prints the G4-1 numbers and rc line; the unmodified file prints the two MISSING lines. After Gate 4: no MISSING line, rc=0 in the output.
# The block sits inside a fenced code block with the marker lines written as shell comments, so the fence lines are not extracted.

# G4-3  AC-R11/F12: every RT row carries its full runnable command
O=process/context/operating-instructions.md
row() { grep -E "^\| $1 " "$O"; }
chk() { row "$1" | grep -qF -- "$2" || echo "MISSING $1: $2"; }
chk RT1 'pnpm --filter web test'; chk RT1 'pnpm --filter web exec tsc --noEmit'
chk RT2 'uv run --project api pytest'
chk RT3 'uv run --project api pytest api/ -q'; chk RT3 'pnpm --filter web test'; chk RT3 'pnpm --filter web exec tsc --noEmit'; chk RT3 'build:islands'
chk RT4 'pnpm test:e2e'; chk RT4 'vc-risk-evidence-pack'
test "$(grep -cE '^\| RT[0-4] ' $O)" -eq 5 || echo "FAIL RT row count"
# red today: 6 lines (RT1 tsc, RT2 pytest, RT3 pytest, RT3 vitest, RT3 tsc, RT4 e2e). After Gate 4: no output.

# G4-4  AC-R11: the commands the RT table names are real, and operating-instructions.md and all-tests.md agree (must stay green: no output today)
node -e 'const p=require("./web/package.json").scripts; for (const s of ["test","test:e2e","build:islands","build","dev"]) if(!p[s]) console.log("MISSING script "+s)'
for t in 'name: api — pytest' 'name: web — vitest, tsc, island build' 'run: uv run --project api pytest api/ -q' 'run: pnpm --filter web test' 'run: pnpm --filter web exec tsc --noEmit' 'run: pnpm build:islands'; do grep -qF -- "$t" .github/workflows/ci.yml || echo "MISSING ci: $t"; done
grep -qF "addopts = \"-m 'not integration'\"" api/pyproject.toml || echo "MISSING addopts"
T=process/context/tests/all-tests.md
for t in 'uv run --project api pytest api/ -q' 'pnpm --filter web test' 'pnpm --filter web exec tsc --noEmit' 'pnpm test:e2e' 'PLAYWRIGHT_CHROMIUM_PATH'; do for f in $O $T; do grep -qF -- "$t" $f || echo "MISSING in $f: $t"; done; done

# G4-5  AC-R9/F12: bounded retry, test budget and the no-re-run evidence mechanism are stated
for t in 'same failure' 'git diff --quiet' 'fix cycles' 'flake' 'SHA' 'vc-tester confirmation'; do grep -qiF -- "$t" $O || echo "MISSING rule token: $t"; done
grep -qF 'same failure' process/development-protocols/master-planner.md || echo "MISSING same-failure line in the envelope template"
# red today: 3 lines (same failure, git diff --quiet, envelope template). After Gate 4: no output.

# G4-6  F12: all-tests.md links to the RT table and carries a dated evidence block
grep -q 'operating-instructions' $T || echo "MISSING all-tests link to RT table"
sed -n '/^## Current evidence (Gate 4)/,/^## [^C]/p' $T > $S/ev.txt
test -s $S/ev.txt || echo "MISSING Current evidence heading"
grep -qE '[0-9a-f]{7,40}' $S/ev.txt || echo "MISSING commit SHA in evidence"; grep -q 'UTC' $S/ev.txt || echo "MISSING UTC stamp in evidence"
grep -qiE 'not re-measured|[0-9]+ passed' $S/ev.txt || echo "MISSING counts or the literal: not re-measured"
# red today: 5 lines (link, heading, SHA, UTC, counts). Scratch-verified: a fixture with the block and no link prints only the link line. After Gate 4: no output.

# G4-7  stale claims gone (the reconciliation sentence must not use these literals)
grep -nE 'unreconciled|54,592|two testers' process/context/current-state.md process/MASTER-PLAN.md
# red today: 4 lines (current-state.md 48, 69, 86; MASTER-PLAN.md R6 row). After Gate 4: no output.

# G4-8  AC-R8: scope (Gate 4 form of C9) and entry files untouched
git status --porcelain | cut -c4- | grep -vE '^process/'
git diff --quiet HEAD -- CLAUDE.md AGENTS.md || echo "FAIL entry files changed"
# today: no output. After Gate 4: no output (including after any test run: web/tsconfig.tsbuildinfo and uv.lock are the two tracked files a run could dirty, see E7).

# G4-9  regression set (must stay green, equal to the baseline)
# C10 exit 0; G3-1, G3-2, G3-6, G3-8, G3-9 print nothing; C11 prints nothing; C12 prints 11; C13 prints nothing; validator set equals the baseline
# (context-discovery 1, agent-parity 0/18, plan-inventory 0/6, others 0/0, check-routing in sync); operating-instructions.md <= 150 lines and <= 7,000 B (C14 caps);
# validate-kit-portability 0 failures after the master-planner.md and operating-instructions.md edits.

# G4-10  AC-R8/F12, branch A only (user approved installs; see G4-K1). Run each suite ONCE, record SHA and UTC.
export UV_FROZEN=1; SHA=$(git rev-parse --short HEAD); date -u +%FT%TZ
uv sync --project api --frozen
(cd web && pnpm install --frozen-lockfile)
uv run --project api pytest api/ -q
pnpm --filter web test
pnpm --filter web exec tsc --noEmit --incremental false; echo tsc rc=$?
(cd web && pnpm build:islands); echo islands rc=$?
export PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome; (cd web && pnpm test:e2e)
git status --porcelain | cut -c4- | grep -vE '^process/'
# not runnable here without the install approval, so no red-today value exists beyond "dependencies not installed". Last state in git: 820 passed pytest (01-10-26),
# 223 vitest tests in 30 files and 873 pytest passed (rev 6, 10-01), e2e 35 of 35 (28-09-26, 4 specs; 6 specs exist now).

# G4-11  hybrid: CI at the head SHA (read-only GET; job logs are forbidden here, so pass or fail only, no counts)
gh run list --branch claude/pensive-albattani-ou0cgv --limit 3 --json headSha,status,conclusion
gh run view <run-id> --json jobs --jq '.jobs[]|[.name,.conclusion]|@tsv'
# today: run 37098105301 at 24f3db6, completed, success, both jobs success.
```

### Test gates (5-column table; Gate 4 scope; strategies are the three proving strategies only)

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-R1 | planner fixed part <= 56,000 B and every file at or below its ceiling | Fully-Automated | G4-1 (red today, one OVER-CAP line) | B |
| AC-R1 | the budget formula is one executable block; two runs print the same text; brief cap written | Fully-Automated | G4-2 (red today, 3 MISSING lines; scratch-verified both ways) | B |
| AC-R11 | each RT row carries a full runnable command | Fully-Automated | G4-3 (red today, 6 lines) | B |
| AC-R11 | the table's commands exist (scripts, CI jobs and steps, pytest config) and both docs agree | Fully-Automated | G4-4 (green today, must stay green) | A |
| AC-R9 | bounded retry with the same-failure clause, budget per tier and the re-run skip check are stated | Fully-Automated | G4-5 (red today, 3 lines) | B |
| AC-R9 | all-tests.md links to the RT table and carries a dated, SHA-stamped evidence block | Fully-Automated | G4-6 (red today, 5 lines) | B |
| AC-R5, AC-R9 | stale totals gone; R8 row at `review` with evidence | Fully-Automated | G4-7 (red today, 4 lines) | B |
| AC-R8 | only `process/` changed; CLAUDE.md and AGENTS.md byte-identical to HEAD | Fully-Automated | G4-8 (C9 Gate 4 form plus `git diff --quiet`) | A |
| AC-R1, AC-R4, AC-R5, AC-R10 | no regression: C10, G3 stay-green set, C11, C12 = 11, C13, validators equal baseline, ops caps | Fully-Automated | G4-9 | A |
| F12 | counts re-measured once, SHA and UTC stamped (pytest, vitest, tsc, islands, Playwright) | Hybrid | G4-10 (precondition: installs approved, G4-K1 = A) | A if approved; otherwise C (user PC or Gate 6 session) plus D (stub `test-counts-remeasure_NOTE_03-10-26.md`) |
| AC-R9 | RT1-RT3 commands pass on CI at the head SHA | Hybrid | G4-11 (green today at 24f3db6) | A |
| AC-R7 | a real worker obeys the retry cap, the same-failure stop and the no-re-run rule | Agent-Probe | Gate 6 pilot: report headings 6, 9, 11; no (command, SHA) pair repeated in heading 6 | C (Gate 6 pilot) |
| AC-R9 | every token figure labelled measured, estimated or unmeasured | Hybrid | review of the Gate 4 report against the table below | D (token-usage-telemetry_NOTE_02-10-26.md, update it with the probe results) |

Failing stub:
test("should keep the planner fixed part and each file under its ceiling", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G4-1 OVER-CAP current-state.md today") })
Failing stub:
test("should carry one executable PLANNER-BUDGET block that prints the same text twice", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G4-2 MISSING markers today") })
Failing stub:
test("should name a full command in every RT row", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G4-3 6 MISSING today") })
Failing stub:
test("should state the same-failure stop, the budget and the skip check", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G4-5 3 MISSING today") })
Failing stub:
test("should link all-tests.md to the RT table and carry a dated evidence block", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G4-6 5 MISSING today") })
Failing stub:
test("should hold no stale unreconciled planner totals", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G4-7 4 lines today") })

Legacy line form (retained so existing contract consumers still parse):
- budget: [fully-automated: G4-1, G4-2] | RT commands: [fully-automated: G4-3, G4-4] | retry and re-run rules: [fully-automated: G4-5] | all-tests: [fully-automated: G4-6] | stale claims: [fully-automated: G4-7] | scope: [fully-automated: G4-8] | regression: [fully-automated: G4-9] | re-measured counts: [hybrid: G4-10, needs installs] | CI at head: [hybrid: G4-11] | worker compliance: [agent-probe: Gate 6 pilot] | tokens: [hybrid: report review]

### Token measurement (AC-R9 labels)

| Quantity | Value | Label |
|---|---|---|
| Entry-set bytes (planner fixed 51,955; with sample brief 54,934; with master-planner.md 65,543; worker 17,554 or 22,662) | exact file sizes | MEASURED (bytes) |
| First-request context, old planner / new planner / new worker | 78,664 / 37,450 / 37,921 tokens | MEASURED, single-run samples (Gate 3, route A); about 32k of each is the fixed headless system prompt (stated by the tester) |
| What those probes cover | the first request only, which carries CLAUDE.md; north-star.md, current-state.md, the registry and the router are read later by tool calls, so the -52% is NOT the entry-set saving | inference from the probe design, not a separate measurement |
| Entry-set saving in bytes (about 200 KB baseline to 52-60 KB) | about 70-74 percent | MEASURED bytes against a Gate 0 baseline; the baseline's ~50k tokens agrees with the probe's attributable ~46k (inference) |
| Tokens implied by bytes (bytes / 4) | planner fixed about 13.0k, with master-planner.md and an 8 KB brief about 18.4k | ESTIMATED |
| Whole-session usage, retry waste, repeated-test cost, subagent tokens, hook output, skill listing, effect of the Gate 4 policy | none | UNMEASURED (no telemetry; the policy's effect is observable only in the Gate 6 pilot, report heading 11) |

Gate 4 needs NO new probe: it changes no file that enters the first-request context (CLAUDE.md is untouched). About 3.38 USD of the approved budget stays unspent. A second B2 sample would only reduce single-run uncertainty and is not recommended.

### Ordering against Gates 5 and 6, and new contradictions

| Item | Finding | Action |
|---|---|---|
| Gate 5 `web/tsconfig.tsbuildinfo` untrack | `tsconfig.json` sets `incremental: true`, so a local `tsc --noEmit` rewrites the tracked file and would break C9 | G4-10 uses `--incremental false`; if the default form is ever run, restore with `git checkout -- web/tsconfig.tsbuildinfo` (documented habit) |
| uv.lock | `uv run` without a frozen flag may rewrite the tracked lock | `UV_FROZEN=1` in G4-10 |
| Gate 5 README (F13) | the README must link to operating-instructions.md for commands, not copy them (single source) | note for Gate 5 |
| Gate 6 pilot | the pilot is the only evidence that the retry cap, the same-failure stop and the no-re-run rule are obeyed (AC-R7); its envelope carries the retry line | Gate 4 puts the same-failure clause in the envelope template (E3) so the pilot worker receives it |
| Shared files | MASTER-PLAN.md, current-state.md and all-context.md have one owner at a time; Gate 4 does not touch all-context.md (its router is in the planner set) | none |
| Stale statements | (a) current-state.md lines 48, 69, 86 and MASTER-PLAN.md R6: "unreconciled" and 54,592; (b) plan section 5: lever "Status" cells say "designed; measure after Gate 3" and the method text says `list_events` sampling "in Gate 3" (Gate 3 used headless probes instead); (c) plan section 5 bounded retry "3 per gate"; (d) plan section 6 `pnpm build:islands` without a directory; (e) all-tests.md "Latest count" 820 and 35/35 e2e (6 specs now); (f) the token-usage-telemetry stub still says sampling was planned in Gate 3 | (a) E5, G4-7; (b), (c), (d) cosmetic, refreshed at the Gate 4 closeout; (e) E6; (f) closeout update of the stub |

### Execute-agent instructions (concerns the plan text cannot hold; EXECUTE must follow all)

| # | Instruction |
|---|---|
| E1 | Order of writes: operating-instructions.md first (RT commands, rules), then master-planner.md (budget block, envelope line, brief cap), then run G4-3, G4-5, G4-2 and read the measured numbers, then branch A runs (G4-10) if approved, then all-tests.md, then trims of current-state.md and MASTER-PLAN.md (write their numbers LAST, from the G4-2 output, because every edit moves the totals), then decisions.md D-12 (budget pin, ceilings, same-failure stop; reason: the Gate 3 totals could not be reproduced), then plan status text, then the report. Do not commit, do not push |
| E2 | master-planner.md: add `## 12. Planner entry-set budget` holding the G4-1 block between two comment lines `# PLANNER-BUDGET:BEGIN` and `# PLANNER-BUDGET:END` inside one fenced block, the trim rule above and the brief cap ("a task brief is at most 8,000 B; for a larger PLAN read only its status, TL;DR and acceptance sections"). Add one planner-end line in section 11 pointing at the block. Keep the 11 report headings used nowhere else (C12 stays 11), keep frontmatter untouched, write other context docs by bare name (kit-portability). About +1.4 KB |
| E3 | Rules: pin "2 fix cycles for a worker; the 10-cycle EVL ceiling in CLAUDE.md is the outer bound only; the same failure (same test or gate id and same first error line) in two consecutive runs stops the loop at once as `blocked` or `needs_input` and is reported in heading 9". Put it in operating-instructions.md and change the envelope template line to `Retry budget: 2 fix cycles; same failure twice stops`. Do not edit CLAUDE.md |
| E4 | Re-run rule: add the skip check ("before re-running a command, run `git diff --quiet <sha-of-the-last-run> HEAD -- <paths the task touched>`; exit 0 and a clean `git status --porcelain` for those paths means skip and cite the recorded run"), and one line that a tester confirms from heading 6 and CI instead of re-running unchanged suites. Write the RT rows with the full commands of G4-3; RT3 uses `cd web && pnpm build:islands`. operating-instructions.md stays <= 150 lines and <= 7,000 B (about +0.9 KB; today 5,108) |
| E5 | current-state.md: rewrite in place to <= 8,000 B (target <= 7,000): keep the stamp, Observed table, validator table, one Gate status block and Next actions; replace the Gate 3 narrative by a link to its report; write the reconciliation as "C3 total plus master-planner.md; two earlier figures differed because one omitted the router cut" without the G4-7 literals. MASTER-PLAN.md: R8 to `review` (never `accepted`: acceptance needs the independent EVL and the user), R6, R7 and R13 evidence cells shortened to <= 300 B with the report path, "unreconciled" removed, total <= 19,000 B (target <= 17,500). Keep every C11 ID row and every `T` and `P` row byte-intact (the rev 6 preservation check filters them) |
| E6 | all-tests.md: add a link line to the RT table in operating-instructions.md and a `## Current evidence (Gate 4)` block of at most 2,000 B (SHA, UTC time, CI run id, either the G4-10 counts or the literal `not re-measured`, plus the file counts 73, 30 and 6, which need no install). Mark the old state tables with one line "historical, superseded by the block above". Do not rewrite the 31,619 B file. If branch K: write backlog stub `test-counts-remeasure_NOTE_03-10-26.md` (what is unproven, why, how to close) |
| E7 | Branch A only: run each suite ONCE per the G4-10 block, record SHA and UTC, never re-run unchanged suites, and finish with C9 clean. If either install fails (the proxy may block a registry), stop the installs, fall back to branch K, and record the failure. No other network use. Playwright needs `PLAYWRIGHT_CHROMIUM_PATH` as written |
| E8 | The independent tester (vc-tester, sonnet) applies the rule it checks: it runs G4-1 to G4-9 and G4-11, and confirms the recorded SHA still matches (`git diff --quiet <sha> HEAD -- api web`) instead of re-running the suites; the counts keep a single-agent source, which the report states |
| E9 | Do not touch CLAUDE.md, AGENTS.md, all-context.md, orchestration.md, `.claude/`, `.codex/`, api/, web/ sources, .gitignore, validators or hooks. Avoid the scout-block shell strings in every command. No probe, no spend |
| E10 | Report: measured bytes before and after for each edited file, the G4-1 output, every token figure labelled per the table above, the install decision taken, and a Forward Preview for Gate 5 (the tsbuildinfo and uv.lock caveats, README links to operating-instructions.md) |

Dimension findings:
- Infra fit: PASS — every command in the RT table exists (scripts, pytest config, CI jobs and steps); CI is green at HEAD 24f3db6; test dependencies are not installed here, which only affects G4-10.
- Test coverage: CONCERN — re-measured counts and local Playwright need installs (G4-K1); compliance with the retry and no-re-run rules is observable only at the Gate 6 pilot; CI gives pass or fail without counts. Closed here: G4-1 to G4-9 are non-vacuous (red today, scratch-verified for G4-2).
- Breaking changes: PASS — text only; CLAUDE.md and AGENTS.md untouched (G4-8); C11 rows, C12 headings, C14 caps and kit-portability constraints are kept by E2, E4, E5 and G4-9.
- Security surface: PASS — no secret, auth or deploy surface; the only network use is the optional frozen installs of branch A (lockfile-pinned: `--frozen`, `--frozen-lockfile`).
- Section feasibility, planner budget (E2, E5): CONCERN (closed by the pin) — real margin 4,045 B not 9,408 B; current-state.md over its ceiling by 879 B; MASTER-PLAN.md 423 B under its ceiling; highest-risk edit: trimming MASTER-PLAN.md rows (keep C11 IDs and T/P rows intact).
- Section feasibility, RT table and retry rules (E3, E4): CONCERN (closed) — six RT cells lack commands; three retry numbers disagree; the same-failure clause and the skip check are missing; highest-risk edit: growing operating-instructions.md past its 7,000 B worker-cap arithmetic.
- Section feasibility, all-tests.md (E6): CONCERN (closed) — no link, counts stale (820 pytest, 4 specs); highest-risk edit: touching the 31 KB history; keep the edit to a block plus labels.
- Section feasibility, token measurement: PASS — labelled table above; no probe needed.
- Section feasibility, ordering against Gates 5 and 6: PASS — two caveats recorded (tsbuildinfo, uv.lock).

Open gaps:
- G4-K1 (the single open decision, needs the user): may EXECUTE install dependencies in this container to re-measure the three suites once? Choose: (A) approve `uv sync --project api --frozen` and `cd web && pnpm install --frozen-lockfile` (lockfile-pinned, no other network use, one run per suite, `UV_FROZEN=1`, `--incremental false`; if an install fails the run falls back to K), recommended; (K) accept the residual: no install, all-tests.md keeps the historical counts labelled `not re-measured` with CI pass at the head SHA as the current evidence, plus a backlog stub and the user-PC or Gate 6 follow-up. Until one is chosen the "three suites once, measured" deliverable is a named residual and the net gate cannot be a terminal PASS.
- G4-K2 (carried, known): real per-session token usage is unmeasured; Gate 4 adds no probe (`token-usage-telemetry_NOTE_02-10-26.md`).
- G4-K3 (carried, known): AC-R5, AC-R6 and AC-R9 (Gate 3 report) await the user's review; they do not block Gate 4.
- G4-K4 (named residual): `all-tests.md` is 31,619 B (about 7.9k tokens by bytes/4, estimated) and is passed to every tester and executor, mostly history; slimming it is a candidate backlog stub `all-tests-history-trim_NOTE_03-10-26.md` (gap-resolution D), not Gate 4 scope.
- Closed inside this contract (no plan supplement needed to proceed): G4-C1 planner margin (G4-1, G4-2, E2, E5); G4-C2 RT commands (G4-3, E4); G4-C3 retry numbers and the same-failure clause (G4-5, E3); G4-C4 re-run evidence (G4-5, E4); G4-C5 all-tests link and stale counts (G4-6, E6); G4-C6 stale totals (G4-7, E5).
- Cosmetic - may be accepted as known gaps: (1) plan section 5 status cells and method text, section 5 "3 per gate", section 6 `pnpm build:islands` directory (refreshed at the closeout, not gate-relevant); (2) the token-usage-telemetry stub wording; (3) the validate-backlog-notes failures (45 notes, repo-wide, outside the baseline); (4) vc-update-process-agent "Current features list" reference (carried from Gate 3).
- Known gaps carried (named residuals): Windows `.agents/skills` behaviour; hook output and skill listing outside every byte or token measure; the Gate 3 report's AC-R9 review.

What this coverage does NOT prove:
- G4-1, G4-2: bytes of files and that one formula prints the same text twice, not tokens, not that a real brief stays under 8,000 B (the brief cap is a written rule); the platform prompt, hook output and skill list are not counted.
- G4-3, G4-4, G4-5: that the commands and rule words exist and agree, not that a worker obeys them; the same-failure rule and the skip check are text until the Gate 6 pilot.
- G4-6, G4-7: presence and absence of text and a SHA stamp, not that the counts are right (they have one source, the execute run) or that old history in all-tests.md is accurate.
- G4-8, G4-9: scope and no-regression against static gates and validators, not behaviour of any role.
- G4-10 (if run): one run per suite on one container at one SHA; no flake classification, no repeat for variance; Playwright on this container's chromium only.
- G4-11: CI pass or fail of the head SHA, not counts and not the e2e suite (CI has none).
- Nothing here proves the Master Planner lifecycle works end to end; that is the Gate 6 pilot.

Plan updates applied by this validate session: none to the plan body (history left as written); the corrections above live in this contract and the orchestrator carries them into EXECUTE through E1-E10. If the orchestrator prefers the strict path, the SUPPLEMENT REQUEST in the V7 hand-off lists the same items as plan-text additions.

Gate: CONDITIONAL (0 FAILs; one open decision G4-K1; six in-contract corrections; Gate 4 EXECUTE may start only after the user accepts G4-K1 with A or K, or after one PVL supplement cycle, because first-pass CONDITIONAL is not terminal; scope: START of Gate 4 only)
Accepted by: pending; not accepted by this session. The user decides G4-K1 at V5. Cosmetic items (1)-(4) are recorded as known gaps, not accepted concerns.

## Autonomous Goal Block — Gate 4

SESSION GOAL: Master Planner recovery program, Gate 4 (token and test efficiency, docs only): RT0-RT4 table with full real commands, bounded retry with a same-failure stop, test budget and the no-re-run evidence rule in operating-instructions.md; all-tests.md linked to it with a dated evidence block; ONE pinned planner-budget block in master-planner.md (fixed part <= 56,000 B, per-file ceilings, brief cap 8,000 B); current-state.md and MASTER-PLAN.md trimmed to their ceilings; R8 to review; decisions D-12.
Charter + umbrella plan: N/A - single plan (process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md)
Autonomy: autonomy removes approval pauses only (feedback_autonomous_phase_execution.md); valid only after the Gate 4 contract above is accepted (G4-K1 decided). Installs happen only if G4-K1 = A and only the two frozen installs named there.
Hard stops / safety constraints:
- Any write outside process/; any edit to CLAUDE.md or AGENTS.md (Gate 4 does not need them; ask the user instead)
- Raising any cap or ceiling without the user; report misses
- Installs or network use beyond what G4-K1 chose; any probe or spend; commit, push, or merging PR #13 (commit only when the user asks)
- Deleting any file, branch or session
- Any NEW validator failure versus the baseline; leaving web/tsconfig.tsbuildinfo or uv.lock dirty; avoid the scout-block shell strings
Next phase: EXECUTE Gate 4 via one vc-execute-agent (opus), sequential, order E1; then an independent vc-tester (sonnet) runs G4-1 to G4-9 and G4-11 and does not re-run unchanged suites; then UPDATE PROCESS closeout; requires the explicit ENTER EXECUTE MODE (already given for Gate 4, executes once the contract is accepted)
Validate contract: inline in plan (## Validate Contract — Gate 4)
Execute start: G4-1 budget | G4-2 one block | G4-3 RT commands | G4-4 commands real | G4-5 retry and re-run rules | G4-6 all-tests | G4-7 stale claims | G4-8 scope and entry files | G4-9 regression + validators == baseline | G4-10 counts (A only) | G4-11 CI at head | e2e spec: none new | probe: none | high-risk pack: no

## Validate Contract — Gate 5

Status: CONDITIONAL (0 FAILs; five blocking user decisions G5-K1, G5-K2, G5-K3, G5-K7 and G5-K9 gate the START of EXECUTE; four more are non-blocking; fourteen execute instructions E1-E14 below)
Date: 03-10-26
date: 2026-10-03
generated-by: outer-pvl
Relation to earlier contracts: the Gate 2, Gate 3 and Gate 4 contracts above are retained as history and NOT overwritten (Gates 3 and 4 are marked CONSUMED). The earlier mechanical greps (`Gate: PASS` count, `results.tsv` line count) are satisfied by that history and prove nothing for Gate 5. The only legal VALIDATE-to-EXECUTE tests for Gate 5 are the Gate line inside this section (`sed -n '/^## Validate Contract — Gate 5/,/^## Autonomous Goal Block — Gate 5/p' <plan>`) or the user's quoted acceptance of the five blocking decisions.
Scope: Gate 5 and the Gate 6 pilot as ONE run (user decision 03-10-26, item 2 below), nothing else. Gate 6's acceptance gates (G6-1 to G6-12) are carried in this contract, so a separate Gate 6 VALIDATE is needed only if the pilot forces a plan change (G5-K9).

User decisions 03-10-26 that define the scope (authoritative; recorded as given):
1. H1 `.agents/skills` symlink: LEAVE AS IS. No work. Documented accepted gap: validate-context-discovery 1 failure and validate-skills 1 failure stay at the baseline; backlog stub `agents-skills-symlink-windows_NOTE_02-10-26.md` already exists (F15). Registry: T17 becomes `cancelled` with that reason (reopen on the user's word).
2. The small cleanups run AS THE WORKER PILOT: register T20 and T16 as `approved`, and the Master Planner (the orchestrator session only) spawns real worker sessions via `create_session` (max 3 concurrent; standing authorization; self-merge only when every mechanical condition holds; an unsure worker stops at `review`; merged task branches are deleted after a verified merge under the standing consent only if a deletion mechanism works, else the branch stays and the Approvals Log row says `deletion deferred`). Task A = T20 (untrack `web/tsconfig.tsbuildinfo` and add the missing `.gitignore` line); Task B = T16 (root README.md that clears the guide-sync baseline failure and links to operating-instructions.md). No third task (reasoned below; nothing invented).
3. Deploy fixes R12 (high-risk class, Windows scripts): DEFERRED, not in Gate 5.
4. Branch deletion: the user allows PROPOSING deletion of exactly six branches (`claude/compassionate-goldberg-o2iq49` plus the five whose PRs merged: `claude/p1-pipeline`, `claude/p2-deploy`, `claude/ui-shell`, `claude/vigilant-hamilton-grr18c`, `fix/narrative-sufficiency-gating-rfc1`). Nothing is deleted without the user's final OK on the list. Other housekeeping candidates and performance baselines were not chosen: deferred with one backlog note.

Parallel strategy: sequential for this validate session (all Layer 1 and Layer 2 checks ran inline as read-only commands and read-only REST GETs; no spawn tool was available; scratch files lived in the session scratchpad only, including a scratch git repo and a scratch copy of the tracked tree). For EXECUTE see E1 (sequential orchestration, two worker lanes, independent testers).
Rationale: signal score 2/7 (S7: more than 5 files in the blast radius; S6 does not apply because no high-risk class is touched by T20 or T16). The two worker lanes are the user's chosen pilot design, not a fan-out for speed. Evidence below was measured live at HEAD 296d96e (== origin/claude/pensive-albattani-ou0cgv, clean tree, 2026-10-03T05:30Z).

Live baseline today (read-only; every Gate 5 command below was run on the live tree or a scratch copy and its red-today result recorded):

| Item | Measured today |
|---|---|
| Branch and PR | HEAD `296d96e` == origin; PR #13 open, DRAFT, `mergeable: true`, `mergeable_state: clean`; 29 commits ahead of `main`, 0 behind; `main` = `5878b16` |
| What `main` still has | the OLD `CLAUDE.md` (28,903 B) and NO `master-planner.md` and NO `operating-instructions.md`: every Gate 2-4 deliverable exists only on the PR #13 branch (44 files changed; outside `process/` only `AGENTS.md` and `CLAUDE.md`) |
| CI at `296d96e` | run `completed`, `success`; check-runs `api — pytest` and `web — vitest, tsc, island build` (em dash) both `success`; the run took 2m42s (jobs of the `ee72237` run: api about 2m53s, web about 35 s); `ci.yml` triggers on `pull_request` with no branch or path filter, so a README-only or ignore-file-only PR still runs both jobs; `concurrency: cancel-in-progress` per ref means a newer push cancels the older run (`d09d92e` and `0004d5b` read `cancelled` for that reason) |
| Repository settings (GitHub REST, admin token) | `visibility: public` (`private: false`), `allow_auto_merge: true`, `delete_branch_on_merge: true`, merge, squash and rebase all allowed; `branches/main/protection` returns 404 "Branch not protected"; rulesets `[]`; secret scanning disabled. The plan's section 4 (i) text (private, protection 403, `allow_auto_merge` false) is STALE (repo `updated_at` 2026-10-03T00:16:45Z, six seconds after PR #12 merged) |
| GitHub from a session | REST works through the proxy (`gh api`); GraphQL is blocked (HTTP 403 "GitHub GraphQL is not available from Claude Code sessions"), so `gh pr create/view/list/merge` do not work and PRs must be created and merged by MCP tools or REST. Seen from this vc-validate-agent subagent only; a spawned worker's tool list is UNVERIFIED |
| `web/tsconfig.tsbuildinfo` | tracked (171,544 B, last touched by `94f3981`); `.gitignore` has no line for it; `web/tsconfig.json` sets `incremental: true`; the only other mentions outside `process/` are `api/tests/deploy/test_deploy_config_shape.py` line 251 and `deploy/README.md` line 126, which both only say "never copy it" and are unaffected |
| README | no root `README.md` (`MISSING README.md`); validate-guide-sync: 1 failure `README.md does not exist` |
| Disk inventory | 15 agents in `.claude/agents/`, 33 skill folders (each with a SKILL.md) |
| Remote heads | 14 (`git ls-remote --heads origin`): `main`, the session branch and the 12 older branches |
| Planner budget | fixed part 48,346 B of 56,000 (headroom 7,654 B); MASTER-PLAN.md 17,819 B of 19,000 |
| Validators | unchanged from the Gate 4 closeout (context-discovery 1, skills 1, guide-sync 1, parity 0/18, plan-inventory 0/6, others 0/0, routing in sync) |

### Layer 1 and Layer 2 findings

| Question asked | Result | Evidence |
|---|---|---|
| (a) Are the two briefs and envelopes complete, self-contained and disjoint? | Yes once written from the field table below; sizes and gates measured on drafts | Drafts built in the scratchpad from the master-planner.md template: envelopes 4,849 B and 4,760 B (cap 8,000); worker entry set with operating-instructions.md named about 26.4 KB (cap 43,000), about 20.3 KB without it (cap 36,000); C4 returns rc=0 for both; G5-1 and G5-2 pass on the drafts and are red today (30 and 3 lines). Ownership: T20 owns `.gitignore`, the index entry of `web/tsconfig.tsbuildinfo` and its task folder; T16 owns `README.md` and its task folder; `.gitignore` has exactly one owner; no shared file. Tier: RT0 for both (T20 adds three exact checks and relies on CI's tsc run from a checkout without the file) |
| (a2) Does untracking break tsc or CI? | No | `pnpm --filter web exec tsc --noEmit --tsBuildInfoFile <scratchpad file>` with no existing build-info file exited 0 in 4.8 s and recreated a 198 KB file (written outside the repo; the live tree stayed clean). In a scratch repo, `git rm --cached` plus the ignore line left `git status` showing only ` M .gitignore` and `D  web/tsconfig.tsbuildinfo`; a recreated file stayed invisible; `git check-ignore -v` named the new line; the C9 Gate 5 filter printed nothing. `ci.yml` never references the file |
| (a3) Any consumer of the tracked file on the user's PC? | One transition hazard, outside cloud verification | Deploy Stage A runs `git pull --ff-only` and is non-fatal (`deploy/_common.ps1` lines 75-88: a refusal logs "starting on current code"). Scratch repo test: a locally MODIFIED tracked file that upstream stops tracking makes `git pull --ff-only` abort ("Your local changes ... would be overwritten"); an unmodified one is simply deleted. So the first pull that carries T20 can leave the PC serving the old build if its copy of the file is modified. Mitigation: a one-line PC step (E9); residual: user-PC only |
| (b) Are the mechanical self-merge conditions checkable here? | Yes by REST for (a)-(e); condition (f) and the archive step are the planner's | See the table after this one |
| (b2) What if a worker lacks a merge tool? | Not covered by the standing authorization | Default: it stops at `review`; whether the Master Planner may merge for it is the user's call (G5-K7, an extension of Open Question 10) |
| (c) README vs the entry sets and the validators | Safe | README is in neither entry set: the ENTRY-SET block, the C3, C4 and G4-1 formulas and CLAUDE.md never name it (0 hits). Scratch copy with a README (generated from disk): guide-sync 0 failures; kit-portability 0/0 (its scanned text surface is `CLAUDE.md`, `AGENTS.md`, kit files, `.claude/`, `.codex/`, `process/development-protocols/`: README is not scanned); context-discovery 1 (baseline; its README check is only for `process/context/`); validate-all-context 0/0; protocol-wiring 0/0; skills 1 (baseline); agent-parity 0/18; routing in sync (checked in a scratch git repo) |
| (c2) What exactly does guide-sync read? | Format constraints that a hand-written README would break | Agents: a heading `## Agents` (digits optional) whose section holds table cells that are a backticked name, one per agent, ending at the next `##` heading or a line starting `---`. Skills: the heading MUST carry a number (`## 2 Skills`; with `## Skills` the scratch run printed 33 failures), then inline backticked folder names, section ends at the next `##` heading. Every disk agent and skill missing is a failure; extra names only warn |
| (d) Cost and runaway risk of real sessions | Unbounded by the platform; estimate below | `create_session` has no budget cap; controls are procedural (see the cost section) |
| (e) Are the Gate 6 criteria testable with commands? | Yes except one named residual | G6-1 to G6-12 below; the no-re-run check was fixture-tested (it printed only the duplicated line); the same-failure stop cannot be forced without inventing a failing task, so it is a named residual (D) |
| (f) Post-pilot verification and handover | Defined | G6 set, E12 and the handover list in E12 |
| Base-branch dependency | NEW, decides the pilot's validity | Main lacks the new entry files. A worker started from `main` would load the old 28.9 KB CLAUDE.md and none of the protocol, so the pilot would test nothing of the new system. A worker based on the session branch whose PR targets `main` would drag 29 commits (including CLAUDE.md and AGENTS.md) into `main`, failing ownership condition (c). Hence G5-K1 |
| Branch-deletion mechanism | Partly evidenced, probe designed | `delete_branch_on_merge: true` is a built-in mechanism for merged head branches (proof only at the first merge: the five older merged branches survived because they merged before the setting changed, or it was changed after); the six proposed branches need an explicit delete; design below |
| Third task? | No | Candidates (trim the housekeeping list, token-usage-telemetry) are bookkeeping or measurement, add cost and no new proof of the lane; two disjoint concurrent lanes already exercise ownership, serialization, CI-gated merge and the report |

Self-merge conditions: can each be checked in this environment (all read-only REST, verified on PR #13 and the session branch):

| Condition (plan section 4, item 2 and Enforcement iii-vi) | Check | State |
|---|---|---|
| (a) CI green on head | `GET repos/jamiroV-code/psychic-train/commits/<head>/check-runs`: both names `completed` and `success` on the CURRENT head | verified live at `296d96e`; names exact (em dash); `cancelled` on an older sha is expected and not red; pending, queued, skipped, neutral are not green; CI is needed because there is no required-check protection (404) |
| (b) risk-tier tests passed and independently confirmed | RT0 gates plus CI on head; then an independent vc-tester per merged task re-runs the gates | CI check verified; tester step is E6 |
| (c) diff inside declared ownership | `GET pulls/<n>/files` names only owned files | endpoint is standard REST; run at the pilot (G5-5) |
| (d) no merge conflicts | `GET pulls/<n>`: `mergeable` true and `mergeable_state` not `dirty`; `mergeable` is null until GitHub computes it, so poll again; `clean` says nothing about CI here (no protection) | PR #13 reads `true` and `clean` |
| (e) report committed | `git log` on the branch, `GET pulls/<n>/files` lists the REPORT | at the pilot |
| (f) registry updated | planner only, after the merge (Enforcement ii) | by design, not a worker condition |
| Branch contains the base tip | `GET compare/<base>...<branch>`: `behind_by` is 0 | verified: session branch 29 ahead, 0 behind `main` |
| Serialized merges | convention: the second worker re-checks `behind_by` after the first merge lands; a race of a few seconds between disjoint-file merges is accepted | no platform lock exists |
| PR creation and merge by the worker | MCP `create_pull_request` and `merge_pull_request`, or REST `POST pulls` and `PUT pulls/<n>/merge` (squash); `gh pr` subcommands are blocked | write paths UNVERIFIED for workers (the pilot proves them; report heading 11 lists the tools) |
| Archive of the session | `archive_session`: planner only, after the merge is verified and the report is durable | unchanged |

### Pilot design (what EXECUTE does, and what stays with the user)

Base branch (G5-K1, default A): workers branch from and open PRs against `claude/pensive-albattani-ou0cgv`. Merges land in that branch (inside PR #13); nothing reaches `main` until the user merges PR #13. Consequences recorded, not hidden: the pilot proves spawn, ownership, CI-gated self-merge, report and acceptance, but NOT a merge into `main`; "CI on the merge SHA" means the CI run PR #13 starts on the new head (the `push` trigger exists only for `main`); the first real `main` merge stays a named residual (C) for the first product task. Alternative B: the user merges PR #13 first and the pilot targets `main` (the faithful path; the planner then works on `main` per repo policy). The envelopes below use `<BASE>`; EXECUTE substitutes the answer. Under A the planner pushes to the base only before spawning (the two task folders) and after both merges (bookkeeping), never while a worker PR is open.

Task field table (each envelope is written from this table plus the shared block that follows; the REF file is the exact text sent as the first `create_session` message):

| Field | T20 (Task A) | T16 (Task B) |
|---|---|---|
| Folder | `process/general-plans/active/t20-untrack-tsbuildinfo_03-10-26/` with `_SPEC_` (brief), `_REF_` (envelope), later `_REPORT_` | `process/general-plans/active/t16-root-readme_03-10-26/` with the same three |
| Task line | `T20 - stop tracking web/tsconfig.tsbuildinfo and ignore it` | `T16 - add a root README.md that satisfies validate-guide-sync` |
| Acceptance | after the merge `git ls-files web/tsconfig.tsbuildinfo` prints nothing, `.gitignore` contains the exact line `web/tsconfig.tsbuildinfo`, and the PR diff names only owned files | README.md exists, links to `process/context/operating-instructions.md` instead of copying commands, lists all 15 agents and 33 skills as guide-sync reads them, and `validate-guide-sync.mjs` reports 0 failures |
| Owned files | `.gitignore` (single owner), `web/tsconfig.tsbuildinfo` (index removal only: `git rm --cached`, keep the working copy), its task folder | `README.md` (created), its task folder |
| Forbidden | `README.md`, CLAUDE.md, AGENTS.md, `.claude/**`, `.codex/**`, `.github/**`, `api/**`, every other `web/**` path, `deploy/**`, `process/MASTER-PLAN.md`, `process/context/**`, `process/archive/**`, `process/development-protocols/**` | `.gitignore`, CLAUDE.md, AGENTS.md, `.claude/**`, `.codex/**`, `.github/**`, `api/**`, `web/**`, `deploy/**`, `process/MASTER-PLAN.md`, `process/context/**`, `process/archive/**`, `process/development-protocols/**` |
| Branch | `claude/t20-untrack-tsbuildinfo` from `<BASE>` | `claude/t16-root-readme` from `<BASE>` |
| Read | its SPEC; operating-instructions.md NAMED (RT0 row, bounded retry, skip check, branch rules) | its SPEC; operating-instructions.md NAMED (the README links to it) |
| Tests line | `Tests: tier RT0; full-suite budget 0` then the gates: no local pytest, vitest or tsc (CI on the PR head runs tsc and the island build from a checkout without the file). Gates: (1) `git ls-files web/tsconfig.tsbuildinfo \| wc -l` prints 0; (2) `grep -cxF 'web/tsconfig.tsbuildinfo' .gitignore` prints 1; (3) `git check-ignore -q web/tsconfig.tsbuildinfo` exits 0; (4) `git diff --check` prints nothing; (5) `git diff --name-only origin/<BASE>..HEAD` names only owned files; (6) CI green on head | `Tests: tier RT0; full-suite budget 0` then the gates in order: (0) run `node .claude/skills/vc-audit-vc/scripts/validate-guide-sync.mjs` BEFORE writing and record the red result (1 failure); (1) guide-sync 0 failures; (2) `validate-kit-portability.mjs` 0 failures; (3) `validate-context-discovery.mjs` exactly the baseline failure `.agents/skills does not resolve to .claude/skills`; (4) `validate-all-context.mjs` 0 failures; (5) `grep -cE 'uv run\|pnpm (--\|install\|test\|build\|exec)\|pytest\|vitest\|uvicorn' README.md` prints 0 and `grep -c 'operating-instructions.md' README.md` prints at least 1; (6) `git diff --check`; (7) diff names only owned files; (8) CI green on head |
| SPEC (brief) must carry | the five exact steps (`git rm --cached`, append the line under `# Node (web/)`, run gates 1-4, commit with a `chore:` prefix, push and PR); why (CI and every tsc run recreate the file; untracking stops the churn); the PC note of E9 | the guide-sync format constraints of finding (c2) verbatim; generate both lists from disk with `ls .claude/agents` and `ls .claude/skills` instead of typing them; content outline (what the project is in two sentences with a link to north-star.md, layout, link to operating-instructions.md for commands, `api/scripts/BOOTSTRAP.md`, `deploy/README.md`, the RIPER-5 and worker pointers); public-repo rule: no secrets, no IP addresses, no personal details beyond north-star.md; size at most 120 lines and 8,000 B (the F13 estimate of about 60 lines grows with 15 agent rows) |
| Autonomy line extra | report headings 9 and 10 carry the registry-update request (accepted then archived with the merge SHA) and the PC note of E9 | report headings 9 and 10 carry the registry-update request and say whether the guide-sync baseline failure cleared |

Shared envelope block (verbatim in both REF files after the task-specific lines; line 1 of each file is exactly `ROLE: WORKER`, line 2 is the template sentence plus "This envelope is your EXECUTE approval for this task only: do not wait for ENTER EXECUTE MODE."):

```
Preflight (before anything else): git fetch origin <BASE>; test -f process/development-protocols/master-planner.md; git merge-base --is-ancestor 296d96e HEAD. If either of the last two fails: git checkout -B <your branch> origin/<BASE> once and re-run them; still failing: stop, reply NEEDS_CONTEXT, change nothing.
Lane: direct. Edit the files yourself; do not spawn vc-quick-fix-agent or any subagent. The gate list above is your contract: run each gate once after the last edit, record command, result, UTC time (date -u +%FT%TZ) and commit SHA for report heading 6; before re-running a command apply the skip check in operating-instructions.md.
Retry budget: 2 fix cycles; same failure twice stops
Budget: at most 60 tool calls and 40 minutes wall clock; at most 8 CI polls, 90 s apart. Exceeding any: stop at review.
PR and merge (gh pr subcommands use GraphQL, which is blocked here; use the GitHub MCP tools if your tool list has them, else REST via gh api): create the PR with base <BASE> (POST repos/jamiroV-code/psychic-train/pulls). CI is green only when GET repos/jamiroV-code/psychic-train/commits/<your head sha>/check-runs shows BOTH `api — pytest` and `web — vitest, tsc, island build` completed with conclusion success on your CURRENT head (a cancelled run on an older sha after a push is expected). Self-merge (squash) only if ALL hold: CI green on head; every gate passed; GET pulls/<n>/files lists only owned files; mergeable true and mergeable_state not dirty; GET compare/<BASE>...<branch> has behind_by 0 (else merge the base into your branch once, push, wait for CI again); the report is committed on your branch. A denied or prompting tool call: stop at review, never retry around it. Merge call: MCP merge_pull_request or PUT pulls/<n>/merge with merge_method squash.
You do NOT: edit process/MASTER-PLAN.md, current-state.md or process/archive/index.md; call archive_session; delete any branch (the repository may delete your head branch at merge; that is expected); push to the base branch directly; force-push; touch any file outside Owned files.
Stop and report at review if: irreversible or outward-facing action, scope expansion, unverifiable condition, any doubt
Report: commit <task folder>/<slug>_REPORT_03-10-26.md using the 11-heading template of master-planner.md before you merge; heading 5 lists branch commits (the Master Planner records the merge SHA); heading 11 lists the session and merge tools your own tool list contains and which line told you that you are a WORKER; the final reply is the same report.
```

### Branch-deletion proposal and the safe probe (nothing here runs without the user)

Proposal table (evidence read-only today; each tip equals the PR head the merge used, so no commit was added after the merge, and `refs/pull/<n>/head` keeps the content; no open PR names any of them):

| Branch | Tip (full sha) | Evidence | Recovery |
|---|---|---|---|
| `claude/compassionate-goldberg-o2iq49` | `ecb5e3921645aebe19ca32b6b628e41a59282207` | 0 commits ahead of `main` (116 behind): fully inside main's history | `git push origin ecb5e3921645aebe19ca32b6b628e41a59282207:refs/heads/claude/compassionate-goldberg-o2iq49` |
| `claude/p1-pipeline` | `60fd9262e8a7e2f2be18bcddc6729f10cbcda4bf` | PR #11 merged 2026-10-01; tip == PR head | same form with this sha; also `refs/pull/11/head` |
| `claude/p2-deploy` | `618cea0da2dc1f788ea0dc73e9ac9d8d38e81622` | PR #10 merged 2026-10-01; tip == PR head | same form; `refs/pull/10/head` |
| `claude/ui-shell` | `8b4497fa51b2c0e59482a20508fd29f54bdbc5aa` | PR #9 merged 2026-10-01; tip == PR head | same form; `refs/pull/9/head` |
| `claude/vigilant-hamilton-grr18c` | `465ea2c97b6f2ae221baa84b2ee3e5b662fe48ba` | PR #8 merged 2026-09-28; tip == PR head | same form; `refs/pull/8/head` |
| `fix/narrative-sufficiency-gating-rfc1` | `ca8e68b5c3c5e45eac7519725fe8af1d2c6309fb` | PR #7 merged 2026-09-28; tip == PR head | same form; `refs/pull/7/head` |

"Ahead" counts of 5-16 for the five PR branches are squash-merge artefacts (the commits are not reachable by sha, their content is in `main`); this matches plan section 7 caveat 1. Before any deletion the planner re-reads the tip (it must still equal the sha above), runs `list_sessions` to see that no live session uses the branch, writes one Approvals Log row (date, branch, tip sha, evidence line, the user's quote of the final OK, status `pending`), deletes, then sets `done`, `failed` or `deletion deferred`. These six are NOT covered by the standing consent; the user's final OK on the list is their approval.

Probe design (the mechanism is unverified; the user approves running it, G5-K5; only the Master Planner session runs it, and never against any of the 14 existing refs):

```
R=repos/jamiroV-code/psychic-train; SHA=$(gh api $R/git/ref/heads/main --jq .object.sha)   # read-only
guard() { case "$1" in claude/probe-delete-03-10-26-[ab]|claude/probe-delete-03-10-26-nonexistent) ;; *) echo REFUSE "$1"; return 1;; esac; }
# step 0, changes nothing: DELETE on a ref that cannot exist. 422 "Reference does not exist" = the method reaches GitHub with delete rights; a proxy 403 or 405 = blocked
guard claude/probe-delete-03-10-26-nonexistent && gh api -X DELETE $R/git/refs/heads/claude/probe-delete-03-10-26-nonexistent -i 2>&1 | head -3
# step 1, only if step 0 printed 422: a throwaway branch AT main's sha (zero content), then delete it, then confirm it is gone
N=claude/probe-delete-03-10-26-a; guard $N && gh api -X POST $R/git/refs -f ref="refs/heads/$N" -f sha="$SHA" && gh api -X DELETE $R/git/refs/heads/$N && gh api $R/branches/$N --jq .name 2>&1 | head -1    # expect HTTP 404
# step 2, only if step 0 or 1 was blocked: the git path with a second throwaway
N=claude/probe-delete-03-10-26-b; guard $N && git push origin "$SHA:refs/heads/$N" && git push origin --delete "$N" && git ls-remote --heads origin "$N"    # expect no output
```

Safety properties: the guard refuses any name outside three fixed throwaway names; each throwaway points at main's own sha, so even a mistaken delete cannot lose content; no wildcard or empty-source refspec is used; `git push origin --delete` takes one explicit name. Result lines go into the Gate 5 report and one Approvals Log row ("probe, approved by the user: <quote>"). If both mechanisms are blocked the six branches stay and every row says `deletion deferred`. `git push --dry-run` of a delete refspec is not authoritative and is not used. Today's repo setting `delete_branch_on_merge: true` makes the worker-branch deletion automatic at merge; it does not delete the six.

### Cost and runaway risk (ESTIMATE, not measured)

`create_session` has no budget cap. Platform usage seen so far ranged from about 2.6 to 172 USD per session; the Gate 2 session was about 51 USD (125.7M cache-read tokens, 0.84M output). Method of the estimate: first-request context of a worker is 37,921 tokens (measured, Gate 3 probe P2); assume 25-60 tool calls growing to about 60k tokens; cache-read tokens about 1.2-3.5M per worker; implied all-in rate about 0.40 USD per million cache-read tokens (derived from the Gate 2 figure, so a rough ratio); multiply by 3-4 for output and cache writes.

| Item | Estimate (USD) |
|---|---|
| Worker T20 (about 25-40 calls) | 1-4 |
| Worker T16 (about 35-60 calls, README generation, four validators) | 2-6 |
| Master Planner overhead (spawn, monitoring, REST checks, two merge verifications, registry, Approvals Log, current-state, report) | 3-10 |
| Two independent vc-tester runs (sonnet) | 1-4 |
| Probe (a handful of REST calls) | under 1 |
| Total | about 8-24, central about 14 |

Tail risk: a worker that loops (CI polling, retries, re-reading) can spend tens of USD before anyone notices; the plan's two-fix-cycle bound is prompt-level only. Controls available: the envelope's budgets (60 tool calls, 40 minutes, 8 CI polls, 2 fix cycles, same failure stops); max 2 lanes of the allowed 3; `interrupt_session` by the planner (interrupt at 45 minutes wall clock, or earlier if `get_session` or `list_sessions` exposes cost and a worker passes 12 USD; whether cost is exposed is UNVERIFIED); no third task. EXECUTE may spawn real sessions only after the user states a spend ceiling (G5-K2; proposal: approve up to 40 USD for the whole pilot, about three times the central estimate, and stop and ask when the platform-reported total passes it). The user chose the pilot knowing it costs a fresh session per task; the figures above are an estimate until the Gate 5 report records the platform-reported usage per session.

### Gate 5 command set (all run from the repo root in bash; red-today results were observed live where stated)

```
# G5-1  AC-R7/R10: briefs and envelopes exist, are complete and small (orchestrator writes them BEFORE spawning)
for t in t20-untrack-tsbuildinfo t16-root-readme; do
  d=process/general-plans/active/${t}_03-10-26; E=$d/${t}_REF_03-10-26.md; K=$d/${t}_SPEC_03-10-26.md
  for f in "$E" "$K"; do test -s "$f" || echo "MISSING $f"; done
  [ "$(head -1 "$E" 2>/dev/null)" = "ROLE: WORKER" ] || echo "FAIL first line $t"
  for tok in 'Retry budget: 2 fix cycles; same failure twice stops' 'Owned files:' 'Forbidden:' 'Branch: claude/' 'Report:' 'Stop and report at review' 'Autonomy:' 'Tests: tier RT0' 'check-runs' 'behind_by' 'NEEDS_CONTEXT'; do grep -qF -- "$tok" "$E" 2>/dev/null || echo "MISSING token $t: $tok"; done
  test "$(wc -c < "$E" 2>/dev/null || echo 99999)" -le 8000 || echo "FAIL envelope over 8000 $t"
  TOT=$(cat CLAUDE.md "$E" "$K" process/context/operating-instructions.md 2>/dev/null | wc -c); test "$TOT" -le 43000 || echo "FAIL worker set over 43000 $t ($TOT)"
done
# red today: 30 stdout lines (4 MISSING files, 2 FAIL first line, 22 MISSING token, 2 FAIL envelope size) plus 2 shell-error lines on stderr. Scratch-verified: drafts built from this contract print nothing (bytes 4,849 and 4,760; totals 26,440 and 26,351).

# G5-2  disjoint ownership; .gitignore and README.md each have exactly one owner
A=process/general-plans/active/t20-untrack-tsbuildinfo_03-10-26/t20-untrack-tsbuildinfo_REF_03-10-26.md; B=process/general-plans/active/t16-root-readme_03-10-26/t16-root-readme_REF_03-10-26.md
for g in '\.gitignore' 'README\.md'; do test "$(grep -l "^Owned files: .*$g" $A $B 2>/dev/null | wc -l)" -eq 1 || echo "FAIL owners of $g"; done
test "$(grep -h '^Owned files:' $A $B 2>/dev/null | wc -l)" -eq 2 || echo "FAIL owned lines"
# red today: 3 lines. Scratch-verified: prints nothing on the drafts.

# G5-3  AC-R8 (Gate 5 form): T20 end state, run on the integration branch after the merge
git ls-files web/tsconfig.tsbuildinfo | wc -l; grep -cxF 'web/tsconfig.tsbuildinfo' .gitignore; git check-ignore -q web/tsconfig.tsbuildinfo; echo rc=$?
# red today: 1, 0, rc=1. After T20: 0, 1, rc=0.

# G5-4  T16 end state, run on the integration branch after the merge
test -s README.md || echo "MISSING README.md"
node .claude/skills/vc-audit-vc/scripts/validate-guide-sync.mjs | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const j=JSON.parse(s);console.log("guide-sync failures="+j.failures.length)})'
grep -cE '^## [0-9]* ?Agents' README.md; grep -cE '^## [0-9]+ Skills' README.md
grep -cE 'uv run|pnpm (--|install|test|build|exec)|pytest|vitest|uvicorn' README.md; grep -c 'operating-instructions.md' README.md
grep -nE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' README.md
for p in $(grep -oE '`(api|web|deploy|process)/[A-Za-z0-9_./-]*`|`[A-Za-z0-9_./-]+\.(md|ps1)`' README.md | tr -d '`' | sort -u); do test -e "$p" || echo "BROKEN LINK $p"; done
test "$(wc -l < README.md)" -le 120 && test "$(wc -c < README.md)" -le 8000 || echo "FAIL README size"
# red today: MISSING README.md and guide-sync failures=1. After T16: no MISSING line, failures=0, 1, 1, 0, a number >= 1, no IP line, no BROKEN LINK, no FAIL.
# Scratch-verified: a README generated from disk gave guide-sync 0 failures, 0 command hits, 1 link to operating-instructions.md, no broken link.

# G5-5  AC-R8 scope: only owned files changed (planner checkout after the merges are pulled; pre-pilot sha 296d96e)
git status --porcelain | cut -c4- | grep -vE '^(process/|README\.md$|\.gitignore$|web/tsconfig\.tsbuildinfo$)'
git diff --name-only 296d96e..HEAD | grep -vE '^(process/|README\.md$|\.gitignore$|web/tsconfig\.tsbuildinfo$)'
for n in <pr-t20> <pr-t16>; do gh api repos/jamiroV-code/psychic-train/pulls/$n/files --jq '.[].filename'; done    # T20: .gitignore, web/tsconfig.tsbuildinfo, its task folder only; T16: README.md and its task folder only
# today: no output from the first two (clean tree, nothing since 296d96e). After the pilot: no output from the first two; the third lists exactly the owned files per PR.

# G5-6  validator set: no NEW failure versus the Gate 4 baseline; guide-sync must reach 0 failures
# context-discovery 1 (.agents/skills), skills 1 (same), guide-sync 0, agent-parity 0 failures and 18 warnings, plan-inventory 0 failures and the same six warning categories
# (the number in "active plan count is high: N" rises by the files of the two task folders: same warning, cosmetic), all-context, protocol-wiring, protocol-discovery,
# kit-portability, skill-invocation-wiring, skill-routing, skill-keywords 0/0; discover-context.mjs --check-routing in sync. Scratch-verified with README and two task folders present.

# G5-7  hybrid, read-only REST: CI and PR facts (names with the em dash; judge the CURRENT head only)
for sha in <head-pr-t20> <head-pr-t16> <base-tip-after-both-merges>; do gh api repos/jamiroV-code/psychic-train/commits/$sha/check-runs --jq '.check_runs[]|[.name,.status,.conclusion]|@tsv'; done
gh api repos/jamiroV-code/psychic-train/pulls/<n> --jq '[.merged,.merge_commit_sha,.base.ref]|@tsv'
# today at 296d96e: api — pytest completed success; web — vitest, tsc, island build completed success.

# G5-8  AC-R6: nothing deleted that the log does not permit
git ls-remote --heads origin | wc -l     # 14 today; after the pilot 14 (worker branches deleted by the repo setting or kept with a 'deletion deferred' row); never fewer until the user's final OK
# every deletion has an Approvals Log row in process/archive/index.md written before (manual) or right after the merge (automatic, K4 = A)

# G5-9  regression set (must stay green)
# C10 exit 0; G3-1, G3-2, G3-6, G3-8, G3-9 no output; C11 no output; C12 prints 11 on master-planner.md; C13 no output;
# G4-1 (PLANNER-BUDGET block) rc=0 with the registry rows added (MASTER-PLAN.md at most 19,000 B); G4-3 to G4-7 no output
```

### Gate 6 command set (AC-R7, AC-R10 and the handover; run after both PRs merged and the testers finished)

```
# G6-1  AC-R10: each pilot report carries the 11 headings (C12 form); must print 11 twice
for t in t20-untrack-tsbuildinfo t16-root-readme; do grep -cE '^(#+ )?(1 Task ID|2 Outcome|3 Summary|4 Files changed|5 Commits|6 Tests run|7 Tests NOT run|8 Deviations|9 Blockers|10 Follow-up|11 Context cost)' $(ls process/general-plans/*/${t}_03-10-26/${t}_REPORT_03-10-26.md); done

# G6-2  AC-R7: no (command, result, SHA) repeated in heading 6 (timestamps stripped); must print nothing
for f in $(ls process/general-plans/*/t20-untrack-tsbuildinfo_03-10-26/*_REPORT_* process/general-plans/*/t16-root-readme_03-10-26/*_REPORT_*); do sed -n '/^## 6 Tests run/,/^## 7 /p' "$f" | grep -E '^[-|*] ' | sed -E 's/[ ]*\|?[ ]*[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+Z[ ]*\|?//' | sort | uniq -d; done
# fixture-tested: a clean report prints nothing, a duplicated line prints exactly that line.

# G6-3  AC-R7: retry budget respected and stated (review: cycles used, at most 2 per failing gate, no same failure twice in a row)
for f in <the two reports>; do sed -n '/^## 9 /,/^## 10 /p' "$f" | grep -ciE 'fix cycle|retry'; done      # each at least 1

# G6-4  AC-R7: accepted on independent evidence, not on the worker's word
grep -E '^\| (T20|T16) \|' process/MASTER-PLAN.md | grep -c 'vc-tester'      # 2 (the evidence cell names the tester report with command and UTC time)

# G6-5  registry and Approvals Log written only by the planner: no worker PR touches them
for n in <pr-t20> <pr-t16>; do gh api repos/jamiroV-code/psychic-train/pulls/$n/files --jq '.[].filename' | grep -E '^process/(MASTER-PLAN\.md|archive/index\.md|context/current-state\.md)$'; done   # prints nothing

# G6-6  archive operations separate: the Gate 5 report names A (documents), B (registry), C (archive_session result) and D (branch) per task, each stated only if its call returned success
# G6-7  merge facts: merged true, merge sha reachable from the base, CI green on the base tip  (G5-7 output; git merge-base --is-ancestor <merge sha> origin/<BASE>)
# G6-8  branch-deletion evidence: git ls-remote --heads origin 'claude/t20-*' 'claude/t16-*' prints nothing (auto-deleted) or the Approvals Log row says deletion deferred; the probe result row exists if K5 was approved
# G6-9  tools and role: each report heading 11 names the session and merge tools and the line that identified the WORKER role: sed -n '/^## 11 /,$p' <report> | grep -ciE 'merge|create_pull_request|gh api'   # each at least 1
# G6-10 final validators and budget: G5-6 and G5-9 (guide-sync 0; context-discovery 1 and skills 1 stay as the accepted H1 gap)
# G6-11 PR #13 untouched by the pilot: gh api repos/jamiroV-code/psychic-train/pulls/13 --jq '[.merged,.state]|@tsv'    # false open (unless the user merged it)
# G6-12 cost recorded: the Gate 5 report states platform-reported usage per session and total, labelled measured, against the estimate above
```

### Test gates (5-column table; Gate 5 and Gate 6 scope; strategies are the three proving strategies only)

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-R7, AC-R10 | the two envelopes are complete, role-first, within 8,000 B, worker sets within cap | Fully-Automated | G5-1 (red today, 30 lines; scratch-verified green on drafts) | B |
| AC-R7 | ownership is disjoint and `.gitignore` and README.md each have one owner | Fully-Automated | G5-2 (red today, 3 lines) | B |
| AC-R8 | T20 end state: untracked, ignored line present, `git check-ignore` rc 0 | Fully-Automated | G5-3 (red today: 1, 0, rc=1) plus CI tsc on the PR head | B |
| AC-R8 | T16 end state: guide-sync 0 failures, links not copied, no IP, no broken link | Fully-Automated | G5-4 (red today: MISSING README.md, 1 failure) | B |
| AC-R8 | only owned files changed, per planner checkout and per PR | Fully-Automated | G5-5 | A |
| AC-R4, AC-R11 | no new validator failure; guide-sync cleared; budget and regression set green | Fully-Automated | G5-6, G5-9 | A |
| AC-R7 | CI green on every PR head and on the base tip | Hybrid | G5-7 (read-only REST; precondition: PRs exist) | A at the pilot |
| AC-R6 | no branch lost; every deletion logged; probe result recorded | Hybrid | G5-8, probe design, G6-8 (precondition: user approvals K4, K5, K6) | A if approved; else C (deletion deferred, branches stay) plus D (backlog note) |
| AC-R10 | each pilot report has all 11 headings | Fully-Automated | G6-1 | B |
| AC-R7 | worker obeyed the no-re-run rule; retry budget stated and respected | Fully-Automated + Agent-Probe | G6-2 (fixture-tested), G6-3 (review) | B |
| AC-R7 | acceptance rests on independent evidence; registry and Approvals Log written only by the planner | Fully-Automated | G6-4, G6-5 | B |
| AC-R7 | a real worker session reads the envelope, identifies as WORKER, opens a PR, self-merges only under the conditions, stops when unsure | Agent-Probe | the pilot itself: report headings 6, 9, 11 and G6-9 | C (Gate 6 is this pilot) |
| AC-R7 | the same-failure stop is obeyed | Agent-Probe | not exercisable without a failing task; it fires only if a gate fails during the pilot | D (named residual; no invented failure) |
| AC-R9 | pilot cost recorded against the estimate | Hybrid | G6-12 | D (`token-usage-telemetry_NOTE_02-10-26.md`, update with the platform-reported figures) |

Failing stub:
test("should write two complete role-first envelopes within 8000 bytes", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G5-1 30 lines today") })
Failing stub:
test("should give .gitignore and README.md exactly one owner each", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G5-2 3 lines today") })
Failing stub:
test("should untrack web/tsconfig.tsbuildinfo and ignore it", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G5-3 1,0,rc=1 today") })
Failing stub:
test("should add a README that clears the guide-sync failure and links instead of copying", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G5-4 MISSING README.md today") })
Failing stub:
test("should carry all 11 report headings in each pilot report", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G6-1 no reports today") })
Failing stub:
test("should repeat no command and sha pair in heading 6", () => { throw new Error("NOT IMPLEMENTED - TDD stub: G6-2 no reports today") })

Legacy line form (retained so existing contract consumers still parse):
- envelopes: [fully-automated: G5-1, G5-2] | T20: [fully-automated: G5-3 + hybrid: CI] | T16: [fully-automated: G5-4] | scope: [fully-automated: G5-5] | validators and regression: [fully-automated: G5-6, G5-9] | CI and PR facts: [hybrid: G5-7] | deletions: [hybrid: G5-8 + probe, needs approvals] | reports: [fully-automated: G6-1, G6-2, G6-4, G6-5] | worker behaviour: [agent-probe: pilot] | same-failure stop: [known-gap: documented, backlog] | cost: [hybrid: G6-12]

### Execute-agent and orchestrator instructions (concerns the plan text cannot hold; EXECUTE must follow all)

| # | Instruction |
|---|---|
| E1 | Who does what. The orchestrator (Master Planner session, the only holder of `create_session`, `archive_session`, `list_sessions`, `interrupt_session`, `send_message` and the GitHub merge tools) drives, sequentially: (1) one vc-execute-agent (opus) writes the two task folders (SPEC and REF from the field table and shared block), the registry rows, the lane table and the backlog note, and runs G5-1 and G5-2; (2) the orchestrator commits and pushes only those files to the base (needs G5-K3); (3) the orchestrator spawns both workers (2 of 3 lanes) with the REF text as the first message and stays on `list_events` and `get_session` for status; (4) after each worker reports, the orchestrator verifies the merge by REST (G5-7), pulls the base, and spawns one independent vc-tester (sonnet) per merged task to run G5-3 or G5-4, G5-5 and the read-only REST checks; (5) the planner records `accepted` then `archived`, the Approvals Log row and `archive_session` as four separate operations (report wording rule: state C and D only when the call returned success); (6) closeout by UPDATE PROCESS. Gate commands are never run by the orchestrator itself; no worker edits the registry. Agent count: 1 orchestrator + 2 workers + 2 testers + 1 or 2 execute-agent runs = 6-7, below every cost-guard threshold; strategy score 2/7, so sequential orchestration; the two workers run in parallel only because the user chose a concurrent pilot |
| E2 | Pre-spawn checks (all read-only): `git status --porcelain` empty; G5-1 and G5-2 silent; `list_sessions` shows fewer than 3 live workers; user approvals G5-K1, G5-K2, G5-K3, G5-K7, G5-K9 are quoted in the report; `git rev-parse HEAD` equals `origin/<BASE>`. Do not spawn a third lane. Verify after spawn that the first worker event shows `ROLE: WORKER` recognised and a preflight pass; a `NEEDS_CONTEXT` reply means stop and read it, not respawn blindly |
| E3 | Registry (planner only, text edits): T20 and T16 to `approved` with the branch names, owned and forbidden globs, RT0, Report paths; lane table gets two rows and the merge token; T17 to `cancelled` (user decision 03-10-26, reopen on request); T25 scope note: the user allowed proposing the six branches; R9 note: H2 is T20, H8 is T16, H1 declined, the rest deferred (backlog note); R12 stays `proposed` and is NOT set to `approved` (approved means standing spawn consent for a high-risk deploy task with no brief; the user's "approved-but-queued" is recorded in its blockers cell as "deferred past Gate 5; becomes approved only on confirmation of its brief", G5-K8); keep every C11 ID row and every T and P row intact; MASTER-PLAN.md stays at most 19,000 B (cells at most 300 B) |
| E4 | Backlog note `process/general-plans/backlog/gate5-deferred-candidates_NOTE_03-10-26.md` (frontmatter like the Gate 2 stubs), one list, nothing new invented: R12 deploy fixes; R10 deploy-path doc; R11 session triage; the pre-existing branches not in the six (kind-tesla, narrative-v2, inspiring-pasteur with PR #5 open, pensive-dijkstra, exciting-meitner, split-all-context: per-branch review); H4 and H5 salvage state; H6 dead `cache` functions; H7 and T19 stale active plans; H10 scout-hook note; performance baselines (section 8 list); T18, T21, T22; token-usage-telemetry. State for each: not chosen by the user on 03-10-26 |
| E5 | Merge procedure facts the planner checks after each worker says merged: `pulls/<n>` merged true and `merge_commit_sha` reachable from `origin/<BASE>`; CI on the new base tip (the run PR #13 starts); the report file present in the PR files; then registry, then Approvals Log, then (only then) `archive_session` for that session. If CI on the base tip is red the planner stops further merges and proposes `git revert <merge sha>` (Enforcement v) |
| E6 | Tester rule (E8 of Gate 4 applies): each vc-tester runs its gates once, confirms CI by read-only REST and heading 6 instead of re-running anything unchanged, records command, UTC time and SHA, and does not edit files |
| E7 | Deletion handling under G5-K4: the default A treats the repo setting as the mechanism: the planner writes the Approvals Log row right after it sees the merge (status `done`, note "auto-deleted by delete_branch_on_merge; recoverable from the merged PR and the base tip") and issues no delete call of its own for a branch that is already gone (404). The six-branch proposal and the probe run only after G5-K5 and G5-K6; the probe uses the guarded commands above verbatim |
| E8 | Fallbacks, all recorded as named gaps and never retried around: a worker without a merge or PR tool, or with a denied call, stops at `review` (the planner then reports; merging for it only if G5-K7 allows); a worker that cannot reach the base branch content reports NEEDS_CONTEXT; a failed or blocked CI keeps the task at `review`; a worker over a budget is interrupted by the planner, and the cost is recorded. At the spend ceiling of G5-K2 the planner stops and asks |
| E9 | T20 report must carry the one-time PC note: before the first `git pull` that brings T20 to the home PC, run `git status --short web/tsconfig.tsbuildinfo` there; if it shows `M`, run `git checkout -- web/tsconfig.tsbuildinfo` first (deploy Stage A is `--ff-only` and non-fatal, so a refused pull leaves the old build serving). Copy it into current-state.md and the Gate 5 handover. It is a user-PC step the cloud cannot verify (known gap, D) |
| E10 | Closeout text fixes (cosmetic, not gates): operating-instructions.md "Local tsc rewrites the tracked web/tsconfig.tsbuildinfo" line (now ignored after T20; keep the `--incremental false` advice only if still useful); current-state.md rows for `.agents/skills`, tsbuildinfo, remote refs, repository settings (public, auto-merge on, delete on merge on, no protection) and the Gate 5 status; plan section 4 (i) facts and section 9 Gate 5 and Gate 6 rows per the user's 03-10-26 decisions; one line in operating-instructions.md that `gh pr` subcommands are blocked and REST or MCP is used (only if the planner's byte budget allows) |
| E11 | Hard stops: any write outside the allowed set (E1 step 2 and the two PRs); touching CLAUDE.md, AGENTS.md, `.claude/`, `.github/`, `deploy/`, api/ or web/ beyond the one index entry; merging PR #13; deleting any branch without the log row and the user's OK; spawning more than 2 lanes; a worker or planner action not listed in the envelope; spend past the user's ceiling; avoid the scout-block shell strings in every command; no push to `main` |
| E12 | Gate 5 report (`master-planner-recovery_GATE5-REPORT_03-10-26.md`) and handover contents: pilot outcome per task (statuses, PR numbers, merge SHAs, report paths), the G5 and G6 outputs with SHA and UTC, the probe result, the six-branch proposal table with current tips, the cost actual versus estimate (labelled), the worker tool lists from the two reports, retry and no-re-run evidence, what the pilot did NOT prove (a merge into `main`; the same-failure stop; Windows runtime), open user items (Open Questions 10 and 12, the K-decisions, the PC step, the PR #13 merge, enabling main protection if wanted), the accepted H1 gap, the deferred-list pointer, and the Gate 6 final-verification verdict |
| E13 | If the answer to G5-K1 is B (user merges PR #13 first), re-run the pre-spawn checks against `main`, replace `<BASE>` with `main`, and note that PR #13's branch is deleted by the repository setting at that merge; the planner then works on `main` per repo policy |
| E14 | Do not run anything in this contract that is not listed; the validate session itself ran no write call to GitHub, no push, no `create_session`, no DELETE and no merge (its only writes were scratchpad files and this plan section) |

Dimension findings:
- Infra fit: CONCERN — the platform changed since the plan's facts (public, auto-merge on, delete on merge on, no protection) and `main` lacks every Gate 2-4 deliverable, so the pilot's base branch must be chosen (G5-K1); `gh pr` is blocked by the GraphQL policy (REST or MCP only). CI names, triggers and duration verified live.
- Test coverage: CONCERN — Gate 5 and the end states have non-vacuous red-today gates (G5-1 to G5-4, G6-1, G6-2); the live worker behaviour, the same-failure stop and a merge into `main` cannot be proven before the pilot (named residuals C and D).
- Breaking changes: CONCERN — untracking `web/tsconfig.tsbuildinfo` can make the home PC's non-fatal `git pull --ff-only` refuse once (scratch-verified); one documented user-PC step (E9). No code, API or schema change; `api/tests/deploy` and `deploy/README.md` unaffected.
- Security surface: CONCERN — the repository is now public with no protection and a worker token with admin REST rights, so the envelope's prohibitions are the only fence; README must carry no secret or address; recommendation G5-K8 (block force-push and deletion on `main`). No auth, billing or secret code is touched.
- Section feasibility, Task A (T20): PASS — mechanical, scratch-verified end to end; highest-risk edit is the `.gitignore` shared file (single owner, one line).
- Section feasibility, Task B (T16): PASS — guide-sync constraints measured and verified on a generated README; highest-risk edit is a hand-typed agent or skill list (generate from disk).
- Section feasibility, pilot mechanics: CONCERN — create_session semantics, the worker's tool list, send_message resumption and cost exposure are UNVERIFIED runtime behaviour; the envelope preflight and the report's heading 11 make the pilot the probe, and every failure mode stops at `review` or NEEDS_CONTEXT at small cost. Probe candidate (not run here): `VC-FEASIBILITY-PROBE-NEEDED: does create_session(prompt, branch) check out the named base and start from the prompt's first line? — cost-class: one small worker session`; it is the pilot's first minutes, not a separate spend.
- Section feasibility, branch deletion: CONCERN — mechanism unverified; zero-risk step 0 and a guarded throwaway probe designed; six tips and recovery recorded; needs G5-K4 to G5-K6.
- Section feasibility, cost: CONCERN — no platform cap; estimate 8-24 USD (central about 14) marked an estimate; needs the user's spend ceiling (G5-K2).

User decisions (G5-K1, G5-K2, G5-K3, G5-K7 and G5-K9 gate the START of EXECUTE; the other four can be answered during the run, each before its step):
- G5-K1 (blocking) pilot base branch. A (default, recommended): stacked on `claude/pensive-albattani-ou0cgv`, PR #13 stays unmerged, nothing reaches `main`; the first merge into `main` stays a named residual. B: you merge PR #13 first, then the pilot targets `main` (the faithful path; the session branch is deleted by the repository setting at that merge).
- G5-K2 (blocking) spend. Approve real worker sessions with a ceiling: proposal up to 40 USD for the whole pilot (estimate 8-24, central about 14; not measured). Sessions have no platform cap; the planner interrupts and stops at the ceiling.
- G5-K3 (blocking) commit authority. The planner needs to commit and push `process/` bookkeeping on the session branch only: the two task folders before spawning and the registry, Approvals Log, current-state and report after the merges. Recommended: yes for Gate 5 and 6 only, never to `main`, never merging PR #13. Without it the workers cannot see their envelope.
- G5-K7 (blocking) worker lane and fallback. Confirm Open Question 12 (direct lane; for these two RT0 tasks the worker edits itself and spawns no quick-fix agent), and decide Open Question 10 extension (b): may the planner merge a worker's PR when the worker lacks a merge tool or its call is denied? Default and the plan's reading: no, the task stays `review`. Recommended for the pilot: yes, once, only if every mechanical condition is evidenced by the planner's own REST checks.
- G5-K9 (blocking) Gate 6 folded into this contract (recommended): the pilot's acceptance runs under G6-1 to G6-12 and the closeout, with a second VALIDATE only if the pilot changes the plan.
- G5-K4 deletion order. `delete_branch_on_merge` is on, so GitHub deletes a worker branch at merge, before the registry shows `archived`. A (recommended): accept it as the mechanism, log the row right after the merge (recovery is trivial: the merged PR and the base tip). B: you switch the setting off so the plan's order (log first, delete after) holds and the planner deletes by hand.
- G5-K5 probe. May the Master Planner run the guarded deletion probe above (step 0 changes nothing; steps 1 and 2 create and delete throwaway branches that carry no content)? Recommended: yes. Without it the six deletions cannot start (the mechanism would be unproven).
- G5-K6 final OK on the six-branch list, asked later with current tips after the probe. Nothing is deleted before it.
- G5-K8 optional hardening and facts. (i) Confirm the repository being public is intended (the plan recorded private). (ii) Recommended: enable minimal protection on `main` (block force-push and deletion only; no required reviews, so planner commits still work); it is your repository setting, outside this plan. (iii) R12 stays `proposed` in the registry (not `approved`) until its brief is confirmed.

Open gaps:
- G5-K1 to G5-K9 above (K1, K2, K3, K7 and K9 block the start).
- Named residuals (D, not PASS-by-silence): a merge into `main` by a worker (only under K1 = B); the same-failure stop; compliance with the retry rule if no gate fails; live worker tool list and `create_session` base semantics until the pilot reports; Windows PC behaviour of the T20 pull (E9) and of `.agents/skills` (H1 accepted); real per-session cost until the report records it.
- Known gaps carried: hook output and skill listing outside every measure; the Gate 3 report's AC-R9 review; AC-R5, AC-R6, AC-R9 await the user (they do not block Gate 5).
- Deferred by the user (backlog note E4, no work now): R12, the remaining housekeeping candidates, performance baselines, R10, R11.
- Cosmetic - may be accepted as known gaps: (1) plan section 4 (i) platform facts and the Enforcement table are stale (fixed at closeout, E10); (2) F13 says about 60 lines, the README needs about 45-120 because guide-sync forces 15 agent rows; (3) the "active plan count is high: N" message grows with the task folders; (4) the operating-instructions.md line about the tracked build-info file goes stale after T20 (E10); (5) the 45 validate-backlog-notes failures are repo-wide and outside the baseline.
- Accepted gap, user decision 03-10-26: H1 `.agents/skills` stays a copy; context-discovery 1 and skills 1 remain; no work.

What this coverage does NOT prove:
- G5-1, G5-2: that envelopes are complete as text, tokens present, size and first line right, and ownership lines disjoint; not that a real session reads them correctly, and not that `create_session` delivers the first line unchanged.
- G5-3, G5-4: the end states of two small files; not that the home PC pulls cleanly (E9), not that the README stays in sync when skills or agents change (guide-sync will fail then, by design).
- G5-5, G5-7: scope and CI as REST reads at a moment in time; with no branch protection they do not stop a bad merge, they only record it.
- G5-8 and the probe: no branch is lost and every deletion is logged; the probe proves the delete call on throwaway refs only, not that deleting any of the six is wise beyond the evidence table.
- G6-1 to G6-5: report shape, absence of repeated runs, planner-only registry writes; not that the worker never would have misbehaved, and the same-failure stop is not exercised.
- The pilot as a whole: spawn, ownership, CI-gated self-merge and acceptance under K1 = A; not a merge into `main`, not a high-risk task, not Windows runtime, not cost beyond one run.
- Nothing here proves the Master Planner lifecycle for product tasks; this pilot is the first evidence.

Plan updates applied by this validate session: none to the plan body (history left as written); the corrections live in this contract and E1-E14, and the SUPPLEMENT REQUEST in the V7 hand-off lists the same items as plan-text additions for the strict path.

Gate: CONDITIONAL (0 FAILs; five blocking user decisions G5-K1, G5-K2, G5-K3, G5-K7, G5-K9; first-pass CONDITIONAL is not terminal: EXECUTE may start only after the user accepts those decisions with a quoted answer, or after one PVL supplement cycle; scope: START of Gate 5 and the Gate 6 pilot only)
Accepted by: pending; not accepted by this session. Cosmetic items (1)-(5) are recorded as known gaps, not accepted concerns.

## Autonomous Goal Block — Gate 5

SESSION GOAL: Master Planner recovery program, Gate 5 plus the Gate 6 worker pilot as one run: two real worker sessions do T20 (untrack web/tsconfig.tsbuildinfo, add the .gitignore line) and T16 (root README that clears the guide-sync baseline failure and links to operating-instructions.md); the planner verifies merges, an independent vc-tester per merged task re-runs the gates, the planner records accepted then archived; a six-branch deletion proposal and a guarded deletion probe wait for the user.
Charter + umbrella plan: N/A - single plan (process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md)
Autonomy: autonomy removes approval pauses only; valid only after the Gate 5 contract above is accepted (G5-K1, K2, K3, K7, K9 answered with quotes). Standing authorization covers spawning workers for approved tasks and their self-merge under all mechanical conditions; it does not cover deletions of the six branches, the probe, spend past the user's ceiling, merging PR #13 or pushing to main.
Hard stops / safety constraints:
- No spawn before G5-1 and G5-2 are silent and the spend ceiling is stated; at most 2 worker lanes
- Writes only by the two workers (their owned files) and the planner's process/ bookkeeping on the session branch; no CLAUDE.md, AGENTS.md, .claude/, .github/, deploy/, api/ edits; no push to main; no merge of PR #13
- No branch deleted except worker branches removed by the repository setting; the six proposed branches and any probe need the user's explicit OK; every deletion has an Approvals Log row
- A worker that is unsure, denied a tool call, or over budget (60 tool calls, 40 minutes, 8 CI polls, 2 fix cycles, same failure twice) stops at review; the planner interrupts runaway sessions
- Avoid the scout-block shell strings; no secrets, no IP addresses in README
Next phase: EXECUTE Gate 5 per E1 (orchestrator-driven, sequential; one vc-execute-agent (opus) for the process/ text, workers via create_session, one vc-tester (sonnet) per merged task); requires the explicit ENTER EXECUTE MODE and the blocking decisions
Validate contract: inline in plan (## Validate Contract — Gate 5)
Execute start: G5-1 envelopes | G5-2 ownership | G5-3 T20 end state | G5-4 T16 end state | G5-5 scope | G5-6 validators == baseline (guide-sync 0) | G5-7 CI and PR facts | G5-8 no branch lost | G5-9 regression | G6-1..G6-12 pilot acceptance | e2e spec: none | probe: deletion probe only if G5-K5 approved | high-risk pack: no

## Resume and Execution Handoff

**Update 03-10-26 (Gate 4 closeout): Gate 4 complete; Gate 5 requires VALIDATE then explicit ENTER EXECUTE MODE.** Gate 4 report: `process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_GATE4-REPORT_03-10-26.md`; EVL records `master-planner-recovery-evl-iteration-002_REPORT_03-10-26.md` and `results-evl.tsv`. Next step: re-enter VALIDATE for Gate 5 (cleanup and performance: H1 `.agents/skills` symlink, `web/tsconfig.tsbuildinfo` untrack plus `.gitignore` line, root README per validate-guide-sync, deploy fixes R12, housekeeping candidates with evidence), then the user's explicit ENTER EXECUTE MODE. Several Gate 5 steps need user approvals (sections 7 and 9). Open Questions 10 and 12 stay open and non-blocking. The Gate 3 update below is history.

**Update 03-10-26 (Gate 3 closeout): Gate 3 complete; Gate 4 requires VALIDATE then explicit ENTER EXECUTE MODE.** Gate 3 report: `process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_GATE3-REPORT_03-10-26.md`. Execute commits `eee7709` and `0b3c9bf` (pushed, PR #13 open). Next step: re-enter VALIDATE for Gate 4 (token and test efficiency: scoped context loading, risk-based verification RT0-RT4 in operating-instructions.md, bounded retries; task R8 and the Gate 4 rows of section 9), then the user's explicit ENTER EXECUTE MODE. Open Questions 10 and 12 stay open and non-blocking. The Gate 2 update and the numbered list below are history.

**Update 03-10-26 (Gate 2 closeout): Gate 2 complete; Gate 3 requires VALIDATE then explicit ENTER EXECUTE MODE.** Gate 2 report: `process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_GATE2-REPORT_03-10-26.md`. Execute HEAD `b84e580` (10 commits, pushed); closeout commits local. Next step: re-enter VALIDATE for Gate 3 (F9, F10, C1-C4, C10), user reviews CLAUDE.md/AGENTS.md before commit. The numbered list below is the pre-Gate-2 handoff, kept as history.

1. Selected plan: `/home/user/psychic-train/process/general-plans/active/master-planner-recovery_02-10-26/master-planner-recovery_PLAN_02-10-26.md`
2. Last completed step: PVL cycle 5 validate (03-10-26, re-run from V1 after the cycle-4 supplement of Gaps 31-32 and cosmetic c1-c9): both gaps verified closed live, c1-c9 landed, C1-C14 re-run and match; Gate: PASS. No implementation. Working tree: plan file edits only.
3. Validate-contract: written 03-10-26 (cycle 5), Gate: PASS, 0 FAIL, 0 unresolved CONCERN (two cosmetic residuals r1, r2 recorded as known gaps). Scope: START of Gate 2 only.
4. Context loaded: CLAUDE.md, all-context.md, orchestration.md, MASTER-PLAN.md (full), realignment SPEC (AC grep), repo branch list.
5. Next step: orchestrator emits the /goal block and the EXECUTE strategy recommendation; on the user's explicit ENTER EXECUTE MODE, spawn vc-execute-agent (opus) for Gate 2 scoped to F1-F8, F11, F15-F17, R13 and R14 in the section 2 order; start MASTER-PLAN work from `pensive-dijkstra` rev 6 (pinned 18ffd4f014f4e5ea0f5d654688875a9300b30ab4); re-verify every remaining UNVERIFIED registry item first; R4 step (vii) is run by the orchestrator session itself. After Gate 2: UPDATE PROCESS closeout, then VALIDATE again before Gate 3.

## Phase Completion Rules

- A gate is complete only when its Verification Evidence rows are green and recorded with command, timestamp, and commit SHA.
- Status words: `PROPOSED` (this plan), `CODE DONE` (files written, not independently verified), `VERIFIED` (independent re-run, e.g. spawned vc-tester or user). Known-gap alone never yields VERIFIED.
- No gate starts before VALIDATE writes a contract for it and the user approves; archive/delete/session-termination steps need separate explicit approval.
