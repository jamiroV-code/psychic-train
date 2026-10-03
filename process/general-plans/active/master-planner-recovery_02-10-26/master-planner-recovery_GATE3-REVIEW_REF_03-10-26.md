---
name: ref:master-planner-recovery-gate3-review
description: "Gate 3 review package: CLAUDE.md and AGENTS.md role-neutral rewrite, the shared ENTRY-SET block, rule-survival map, byte before/after, static gate outputs. For the user's review before any commit."
date: 03-10-26
---

# Gate 3 review package (working tree, uncommitted)

**Bottom line:** CLAUDE.md shrank from 28,903 to 13,304 bytes and AGENTS.md from 37,885 to 12,453 bytes. Both now carry one byte-identical ENTRY-SET block (2,842 bytes) that tells a session which role it is in and what to load. No `@`-imports remain. Every rule that lived only in these two files is either still there or moved to master-planner.md with a pointer. All static gates G3-1 to G3-9, C10 and C13 print nothing; validators equal the Gate 2 baseline. Nothing is committed. Undo: `git checkout -- CLAUDE.md AGENTS.md` (plus the four `process/` files listed below if you want a full revert).

Read the full diff with `git diff -- CLAUDE.md AGENTS.md`.

## Files changed

| File | Before (bytes) | After (bytes) | What |
|---|---|---|---|
| CLAUDE.md | 28,903 (440 lines) | 13,304 (154 lines) | role-neutral rewrite, ENTRY-SET block, no `@`-imports |
| AGENTS.md | 37,885 (704 lines) | 12,453 (139 lines) | same block; four false symlink statements replaced by the truth |
| process/development-protocols/master-planner.md | 12,705 | 13,588 | delegation list + trivial-question exception; execute-agent preflight (section 2) |
| process/context/decisions.md | 8,653 | 9,888 | D-9: removal of the "Before Any Substantial Task" `find` ritual |
| gate3-probe-brief_REF_03-10-26.md (new) | - | 2,979 | sample brief for probes P1/P2 and gate G3-C3 |
| gate3-probe-envelope_REF_03-10-26.md (new) | - | 1,132 | sample worker envelope, first line `ROLE: WORKER` |
| this file (new) | - | - | review package |

## Entry-set bytes (approximate tokens = bytes / 4; NOT counted: platform system prompt, SessionStart hook output, skill list)

| Set | Bytes | Cap | Approx. tokens |
|---|---|---|---|
| PLANNER (G3-C3, sample brief) | 50,343 | 64,000 | ~12,600 |
| PLANNER + master-planner.md (informational, read only when dispatching) | 63,931 | not a cap | ~16,000 |
| WORKER (G3-C4, no operating-instructions.md) | 17,415 | 36,000 | ~4,400 |
| WORKER with operating-instructions.md | 22,523 | 43,000 | ~5,600 |
| Before Gate 3, CLAUDE.md alone with its three `@`-imports | about 28,903 + imported files (unmeasured here) | - | - |

All token figures are unmeasured estimates. Real usage is measured only by the live probes (route A, run by an independent tester).

## The ENTRY-SET block (identical in both files)

````markdown
<!-- ENTRY-SET:BEGIN -->
## Session Entry Set and Role Selection

This block is byte-identical in CLAUDE.md and AGENTS.md. It decides what a session loads at start. Load only your set; open any other doc only when the task needs it.

**Your role is decided by the session's FIRST message only.**

- **WORKER:** the first message is a task envelope whose first line is exactly `ROLE: WORKER`. Work in the direct lane. The envelope is your EXECUTE approval: do not wait for ENTER EXECUTE MODE, do not orchestrate, do not spawn sessions or subagent chains, and load only the files the envelope names. The envelope overrides any orchestrator wording elsewhere in this file, but never the hard rules at the end of this block.
- **PLANNER:** any other first message (a session the user opened, or the Master Planner). Read the PLANNER set. Read master-planner.md only when dispatching, accepting or merging tasks, spawning workers or updating the registry. Rules in this file marked "In planner posture" apply to PLANNER sessions only.

**PLANNER set** (cap 64,000 bytes):

1. this file (CLAUDE.md or AGENTS.md)
2. north-star.md: direction
3. current-state.md: observed truth, stamped with commit and time
4. `process/MASTER-PLAN.md`: the task registry
5. `process/context/all-context.md`, from the top through the line before `## Context Group Lifecycle`: the router
6. the task brief (the task folder's PLAN or SPEC)

**WORKER set** (cap 36,000 bytes; 43,000 when the envelope names operating-instructions.md):

1. this file (CLAUDE.md or AGENTS.md)
2. the task envelope (at most 8,000 bytes)
3. the task PLAN or SPEC the envelope names
4. operating-instructions.md, only when the envelope names it

**On demand, either role:** architecture.md (layout, runtimes, data flow), operating-instructions.md (commands, test tiers RT0-RT4, worktree, branch and merge rules), decisions.md, master-planner.md, context-changelog.md, orchestration.md and the other protocols in `process/development-protocols/`. The root context docs above live next to all-context.md. A worker that opens one notes it in report heading 11.

**Hard rules for every role:**

- Phase locking: stay inside your phase or task scope; no file edits in RESEARCH or INNOVATE; no scope expansion.
- Approval gates: no implementation without approval. For a PLANNER that is the user's explicit ENTER EXECUTE MODE; for a WORKER it is its envelope. Irreversible or outward-facing actions (push, merge, deploy, deletion, spend) need the approval the envelope names or the user's.
- Commit policy: a PLANNER session and direct user work commit only when the user asks, directly on `main`. A WORKER commits on its own branch `claude/<task-id>-<slug>` and opens a PR.
- No secrets in files, commits, prompts or logs.
- When unsure, stop and report instead of guessing.
<!-- ENTRY-SET:END -->
````

## Old section -> new location (bytes are the old section's size)

### CLAUDE.md

| Old section | Bytes | Disposition | New location |
|---|---|---|---|
| Bootstrap Guard | 403 | kept | CLAUDE.md `## Bootstrap Guard` |
| Before Any Substantial Task (`find` ritual + two `@`-imports) | 820 | removed with reason | replaced by `## Session Start` + ENTRY-SET block; decisions.md D-9 |
| Shared Development Protocols (`@`-import) | 797 | pointer | `## RIPER-5 ...` pointer list to the protocol router |
| Orchestrator Role (`@`-import, "You are the orchestrator") | 1,003 | moved | master-planner.md section 2 (delegation list, trivial-question exception); CLAUDE.md `### Planner posture` keeps the scoped no-inline-execution sentence |
| /goal Block | 1,556 | scoped pointer | "In planner posture, after every VALIDATE emit the /goal block" -> `08-validate.md`, autopilot.md |
| Strategy-Compare, Pre-Spawn Strategy | 854 + 1,055 | scoped pointer | Planner posture bullet -> `vc-agent-strategy-compare`, orchestration.md §Two-Tier Fan-Out |
| Autonomous /goal Phase Program Execution | 705 | pointer | "autonomy removes approval pauses only" kept in Planner posture; full: orchestration.md §Autonomy Mode |
| Model Selection Policy | 1,029 | kept, shortened | `### Model Selection Policy` (EXECUTE = opus) |
| Communication Principles | 564 | kept, shortened | `### Communication Principles` -> communication-standards.md |
| Repository Context, Technology Stack | 712 + 128 | pointer | `## Session Start` (all-context.md router, architecture.md) |
| Core Protocol (mode prefix, RIPER-5 Phase Table) | 2,459 | kept | `### Core Protocol` |
| Mode Detection | 462 | pointer | `## Routing` -> orchestration.md §Intent Routing |
| QUICK FIX Lane | 2,415 | kept trigger + scope guard | `### Core Protocol` QUICK FIX paragraph; detail orchestration.md |
| Shared Process Folder (incl. autopilot prepend) | 2,193 | pointer | plan-lifecycle.md; autopilot.md (prepend kept as a scoped bullet) |
| Available Workflow Skills, Core Skills | 661 + 620 | pointer | `discover-skills.mjs` (generated catalog covers all skills) |
| Mode Agents, validator registry, Tier-1 audits | 2,639 | pointer | `.claude/agents/`; all-context.md; `12-reference.md` |
| Routing | 893 | kept | `## Routing` (heading kept; orchestration.md cites it) |
| Phase Transition Rules + PVL/EVL gates | 3,566 | kept | `## Phase Transition Rules` (no-inline-execution scoped "In planner posture") |
| Commit branch policy (was inside a section) | - | kept + worker exception | `## Commit Branch Policy` |
| Key Principles | 647 | kept | `## Key Principles` ("Never start EXECUTE without explicit approval" scoped: planner = ENTER EXECUTE MODE, worker = envelope) |
| Quick Start, Resources | 488 + 643 | pointer | `## Where Moved Sections Live` |
| PostToolUse Hooks and Context Envelope | 1,356 | pointer | `.claude/settings.json`; `vc-context-discovery` §Context Envelope |

### AGENTS.md

| Old section | Bytes | Disposition | New location |
|---|---|---|---|
| Title, bootstrap guard, symlink paragraph | ~1,800 | kept / corrected | bootstrap kept; `## Codex Surfaces` states the truth: `.agents/skills/` is a tracked copy (339 regular files, identical today) until task H1 |
| Shared Development Protocols | 1,178 | pointer | `## RIPER-5 ...` pointer list |
| Orchestrator Role | 1,438 | moved | master-planner.md section 2; `### Planner posture` |
| Repository Context, Technology Stack | 1,051 + 123 | pointer | `**Session start:**` line; all-context.md |
| Core Protocol | 1,620 | kept, compressed | `### Core Protocol` + RIPER-5 Phase Table (original "should begin with `[MODE:`" wording kept) |
| Mode Detection, Large program rule | 2,138 | pointer | `## Routing`; orchestration.md, phase-programs.md |
| Engineering Standards | 453 | pointer | implementation-standards.md |
| Shared Process Folder (general-plans, context, features, lifecycle, legacy dirs) | 76+483+1,213+1,208+1,328+475 | pointer | `## Shared Process Folder` -> plan-lifecycle.md; the dangling "Current features list above" reference is dropped (the list never existed; all-context.md has the feature list) |
| Workflow Ownership, Core Skills, Skill Registry table | 1,478 + 678 + 3,741 | pointer | `discover-skills.mjs` |
| Mode Agents, Available Agents, Specialist Agents | 647 + 2,312 + 2,152 | compressed | `### Core Protocol` agent list; `spawn_agent` note in `## Codex Surfaces` |
| Discovery Note (false symlink claim) | 373 | corrected | `## Codex Surfaces` |
| Detect Intent, Gather Context, Route, Monitor | 2,803 + 778 + 326 + 190 | pointer | `## Routing`; orchestration.md §Intent Routing |
| Phase Transition Rules (incl. preflight, closeout packet, drift scoring) | 3,916 | kept gates; moved detail | `## Phase Transition Rules`; preflight -> master-planner.md; closeout/drift -> orchestration.md §Post-EXECUTE Cleanup Checkpoint, `vc-generate-closeout` |
| Key Principles (Phase Locking, Safety, Efficiency) | 19+267+218+240 | kept | `## Key Principles` |
| Success Metrics | 372 | removed (descriptive, no rule) | - |
| Quick Start, Troubleshooting, Resources, Porting Notes | 924+754+561+420 | compressed | `## Where Moved Sections Live`, troubleshooting line, `## Codex Surfaces` |
| `.claude/memory/MEMORY.md` note | (in Repository Context) | removed | Claude-only note; Codex has no equivalent |

## Rules moved into master-planner.md (section 2)

1. Delegation list: a session in orchestrator posture never researches, brainstorms, plans, implements or updates rules itself; it delegates to the RIPER-5 agents.
2. Trivial-question exception: a trivial question with no mode-specific work may be answered directly.
3. Execute-agent preflight: exactly one plan file, path passed explicitly, ask the user when several exist, never let the agent infer the plan from ambient state.

## Rules kept in place (anchors checked by G3-7)

Mode prefix, one mode per response, never skip to implementation, never start EXECUTE without explicit approval (scoped), commit policy directly on `main` (+ worker exception), `## Routing`, RIPER-5 Phase Table, Bootstrap Guard, PVL "MUST NOT be emitted", PVL gate (b) `wc -l < results.tsv`, EVL `vc-tester`, No inline execution (scoped), QUICK_FIX_ABORT, EXECUTE = opus, and pointers to orchestration.md, autopilot.md, plan-lifecycle.md, communication-standards.md, discover-skills.mjs.

## Static gate outputs (run 03-10-26, working tree)

- G3-1 (no `@`-imports): no output
- G3-2 (role-neutral): no output
- G3-3: `CLAUDE.md 13304`, `AGENTS.md 12453`, no OVER-CAP
- G3-C3: `total=50343`, `rc=0`
- G3-C4: `total=17415 cap=36000 rc=0`; with operating-instructions.md `total=22523 cap=43000 rc=0`; envelope first line `ROLE: WORKER`
- C10: exit 0; G3-5: no MISSING-TOKEN, block 2,842 bytes in both files
- G3-6: 4 and 4 literal `process/context/all-context.md`
- G3-7 (rule survival): **no output**
- G3-8 (symlink claims): no output (the same regex prints 5 lines on the HEAD version)
- G3-9 (scoped planner rules): **no output**
- C9 Gate 3 form and C13: no output
- G3-10 validators: equal to the Gate 2 baseline (context-discovery 1 failure, skills 1, guide-sync 1; all others 0). Only counts changed: context-discovery `checkedConcreteRefs` 241 -> 233 (fewer backticked paths in AGENTS.md), plan-inventory `activePlans` 92 -> 95 (the three new `_REF_` files; same warning text).

## For your decision

Commit Gate 3? (Accept / Revise / Revert). The live probes P1 and P2 (route A) are still to be run by an independent tester; prefer merging PR #13 only after they pass.
