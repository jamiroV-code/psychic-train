# AGENTS.md

**Bootstrap guard:** If `process/context/all-context.md` does not exist, the harness has not been set up yet (a bare `process/context/` holding only `generated-skills-catalog.json` from install does NOT count). Run `vc-setup` before any task: the context router and protocol docs are absent and agents will not route correctly.

This file is the Codex compatibility layer for the `.claude/` system. Keep it aligned with [CLAUDE.md](CLAUDE.md); the ENTRY-SET block below is byte-identical in both files.

**Session start:** load the entry set for your role (block below). `process/context/all-context.md` is the context router; its routing tables lead to deeper docs, which you open only when the task needs them.

## Codex Surfaces

- `.claude/skills/` is the canonical source for shared skills (real `SKILL.md` files with YAML frontmatter; no agent-wrapper skills).
- `.agents/skills/` is where Codex discovers project skills. Today it is a tracked copy of `.claude/skills/` (339 regular files in git, currently identical), not a link. Until the separate, approval-gated task H1 replaces the copy, a skill added or changed under `.claude/skills/` must also be copied to `.agents/skills/` for Codex to see it.
- `.claude/agents/` is the canonical source for RIPER-5 mode agents and specialist agents; `.codex/agents/*.toml` mirrors them for Codex subagent roles. Claude's YAML `tools:` allowlists are not guaranteed to be enforced by Codex TOML.
- Codex agent triggering is manual: use `spawn_agent` with the matching `agent_type` when the user asks for delegation, a RIPER-5 mode or parallel agent work and the tool is available.
- `.codex/config.toml` holds project-level Codex configuration.

Prefer updating `.claude/` first, then mirror the Codex surface when needed.

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

## RIPER-5 Spec-Driven Development System

This project uses RIPER-5: strict, mode-based phases that prevent premature implementation. Shared workflow rules live in [process/development-protocols/all-development-protocols.md](process/development-protocols/all-development-protocols.md) (router), read on demand:

- [orchestration.md](process/development-protocols/orchestration.md): delegation, status codes (`DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, `NEEDS_CONTEXT`), context isolation, Intent Routing, QUICK FIX lane, PVL/EVL loop routing
- [master-planner.md](process/development-protocols/master-planner.md): planner posture rules, task lifecycle, worker envelope and report templates
- [implementation-standards.md](process/development-protocols/implementation-standards.md), [plan-lifecycle.md](process/development-protocols/plan-lifecycle.md), [phase-programs.md](process/development-protocols/phase-programs.md), [context-maintenance.md](process/development-protocols/context-maintenance.md), [autopilot.md](process/development-protocols/autopilot.md), [communication-standards.md](process/development-protocols/communication-standards.md)

Plan-shape references: `.claude/skills/vc-generate-plan/references/example-simple-prd.md`, `.claude/skills/vc-generate-plan/references/example-complex-prd.md`, `.claude/skills/vc-generate-phase-program/references/program-goal-charter-template.md`.

**Context routing discipline:** `all-*.md` entrypoints are routers, not the full knowledge. Follow their routing tables to the deeper file(s) before proposing or executing operational steps.

### Planner posture

In planner posture the session routes, delegates and monitors; it does not do phase work itself. The delegation list (with the trivial-question exception), the execute-agent preflight, strategy and model rules live in master-planner.md section 2; the full routing logic in orchestration.md. A WORKER (see the block above) executes its own task directly and ignores this subsection.

- In planner posture, no inline execution: the session never edits source files or runs validate-contract gate commands itself; EXECUTE is a spawned `vc-execute-agent`, the EVL gate run a spawned `vc-tester`.
- In planner posture, before spawning `vc-execute-agent`, run the preflight in master-planner.md: exactly one plan file, its path passed explicitly; ask the user when several exist.
- In planner posture, invoke `vc-agent-strategy-compare` at every phase transition. Model policy: EXECUTE = opus; every other phase = sonnet.

### Core Protocol

The complete protocol is defined in the agent files under `.claude/agents/` (mirrored in `.codex/agents/`): `vc-research-agent`, `vc-spec-agent`, `vc-innovate-agent`, `vc-plan-agent`, `vc-validate-agent`, `vc-execute-agent`, `vc-fast-mode-agent`, `vc-update-process-agent`, `vc-quick-fix-agent`. Specialists: `vc-tester`, `vc-debugger`, `vc-code-reviewer`, `vc-code-simplifier`, `vc-ui-ux-designer`, `vc-git-manager`.

Key Requirements:

- In planner posture every response in an explicit RIPER-5 workflow should begin with `[MODE: MODE_NAME]`. A WORKER's responses do not need the prefix (its report format is in master-planner.md section 9).
- Only one mode per response, except FAST MODE
- Explicit mode transitions are required
- Phase-locked activities are strictly enforced

RIPER-5 Phase Table (approval triggers apply in planner posture; a WORKER's envelope is its approval):

| Phase | Agent | Trigger | Artifact |
|---|---|---|---|
| RESEARCH | vc-research-agent | "ENTER RESEARCH MODE" or feature request | findings in chat |
| SPEC | vc-spec-agent | "ENTER SPEC MODE" or "go" | `*_SPEC_*.md` in the task folder |
| INNOVATE | vc-innovate-agent | "go" or "ENTER INNOVATE MODE" | Decision Summary |
| PLAN | vc-plan-agent | "go" or "ENTER PLAN MODE" | `*_PLAN_*.md` in a task folder |
| VALIDATE | vc-validate-agent | "ENTER VALIDATE MODE" or after PLAN | validate-contract in the plan |
| EXECUTE | vc-execute-agent | explicit "ENTER EXECUTE MODE" | source changes, test results |
| UPDATE PROCESS | vc-update-process-agent | "ENTER UPDATE PROCESS MODE" | archive, context updates |

QUICK FIX lane (`ENTER QUICK FIX MODE`, "quick fix", "hotfix"): read-only scout, one-line confirm, one `vc-quick-fix-agent`, scoped check; no plan, no EVL. Scope guard: void for schema, auth, API contract, billing, migration, multi-feature or more than about 100 lines (`QUICK_FIX_ABORT`). Detail: orchestration.md §QUICK FIX Lane.

## Routing

- **Step 0, skill discovery:** run `node .claude/skills/vc-context-discovery/scripts/discover-skills.mjs` (reads the generated skills catalog) to list every skill by layer with trigger keywords; match them to the request and name the matches in the subagent prompt. Never silently skip a matched skill.
- **Intent and precedence:** feature -> RIPER-5; question -> research or direct answer; trivial fix -> `vc-execute-agent`; bug -> `vc-debugger`; an existing active plan always resumes first. Full rules: orchestration.md §Intent Routing.
- **Context to pass:** `process/context/all-context.md`, `process/context/tests/all-tests.md` for testers and executors, the exact plan path, and the active-plan folders to avoid duplicate plans.

## Phase Transition Rules

Outer order: RESEARCH -> SPEC -> INNOVATE -> PLAN -> VALIDATE -> EXECUTE -> UPDATE PROCESS; the phase-program inner loop skips SPEC. Each transition needs the user's "go" or the explicit mode command, and the next phase's strategy from `vc-agent-strategy-compare`.

- PLAN -> VALIDATE -> EXECUTE: EXECUTE is legal only after `Gate: PASS`, a recorded PVL fix cycle (`wc -l < results.tsv` >= 3) or the user's explicit acceptance of CONDITIONAL gaps. `PHASE_COMPLETE: VALIDATE` MUST NOT be emitted after a first-pass CONDITIONAL or BLOCKED verdict.
- EXECUTE -> UPDATE PROCESS: an independent `vc-tester` re-runs the validate-contract gates even when the execute agent reports green; then a closeout packet and the user's explicit command.
- Full rules: orchestration.md §PVL/EVL Loop Routing.

## Shared Process Folder

Codex and Claude share `process/`. Plans live in task folders `{slug}_{dd-mm-yy}/` under `process/general-plans/active/` or `process/features/{feature}/active/`, with reports and references inside the same folder. The feature list is in all-context.md. Rules: plan-lifecycle.md (§Task-Folder Framework, §Feature Folder Lifecycle).

## Key Principles

- Phase locking: RESEARCH read-only; SPEC writes the requirements doc only; INNOVATE discusses only; PLAN and VALIDATE write artifacts only; EXECUTE implements the approved plan only; UPDATE PROCESS documents and archives.
- Never skip directly to implementation for substantial work.
- Never modify files in RESEARCH or INNOVATE.
- Never start EXECUTE without explicit approval (in planner posture the user's ENTER EXECUTE MODE; for a WORKER its envelope).
- Always preserve user agency at phase transitions.
- Communication: answer first, plain language, TL;DR: communication-standards.md.

## Where Moved Sections Live

| Former section | Now |
|---|---|
| Orchestrator role, delegation list, preflight | master-planner.md section 2 |
| Mode detection, intent routing, closeout packet, drift scoring | orchestration.md (§Intent Routing, §Post-EXECUTE Cleanup Checkpoint) and the `vc-generate-closeout` skill |
| Skill registry table, workflow ownership layers | `discover-skills.mjs` (generated catalog) |
| Agent list and tool notes | `.claude/agents/`, `.codex/agents/` |
| Validator registry, Tier-1 audits | all-context.md and `process/development-protocols/vc-system-behavior/12-reference.md` |
| Feature folder lifecycle, legacy sibling dirs | plan-lifecycle.md |

Troubleshooting: missing subagent -> check `.claude/agents/` and `.codex/agents/`; missing skill for Codex -> check that `.agents/skills/` holds the same folder as `.claude/skills/`; plan conflicts -> date-stamped names, check `git status`.
