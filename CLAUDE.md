# CLAUDE.md

## Bootstrap Guard

**If `process/context/all-context.md` does not exist**, the harness has not been set up yet. (Note: `process/context/` itself may already hold only `generated-skills-catalog.json` from install; that alone does NOT count as set up.) Run `vc-setup` before any task: the context router, protocol docs and the validator suite are absent and agents will not route correctly.

## Session Start

Load the entry set for your role (block below) and nothing else by default. `process/context/all-context.md` is the context router: its routing tables lead to deeper docs, which you open only when the task needs them. Never hardcode file paths; discover them from the routers. Project coding preferences and conventions: all-context.md and architecture.md.

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
- Approval gates: no implementation without approval. For a PLANNER that is the user's explicit ENTER EXECUTE MODE; for a WORKER it is its envelope. Push and merge follow the standing owner permissions below. Deploy, deletion and spend still require approval in the worker envelope or explicit user approval; never bypass these gates.
- Commit policy: nobody pushes directly to `main`. A PLANNER session and direct user work commit on a branch (`claude/<task-id>-<slug>` or a short descriptive branch) and open a PR; a WORKER commits on its own task branch. Eligible PRs may be merged by the responsible agent/session under the standing owner permission below.
- No secrets in files, commits, prompts or logs.
- When unsure, stop and report instead of guessing.
<!-- ENTRY-SET:END -->

## Owner standing permissions (owner, 2026-11-11; merge authorization)

These permissions apply to future sessions unless the user explicitly withholds them for a task:

- Agents may push their task branches and may mark their own PR ready and merge it without another confirmation, but only after all merge gates are evidenced: PR is non-draft; CI is green on the exact head SHA; required task gates pass or are within an explicitly saved baseline; an independent review is complete and all findings are fixed; no other open PR overlaps its files; and the PR is mergeable/up to date. Changes to `CLAUDE.md` or `AGENTS.md` also require the user's diff check before merge. Unknown or failing evidence means do not merge.
- Never push directly to `main`, force-push, or bypass a PR. A merge through GitHub is authorized only when the gates above pass. After merge, verify CI on the merge SHA and report any failure.
- GitHub `main` is canonical. Keep the PC checkout fast-forwarded at least daily using `scripts/pc-sync/sync-main.ps1` (the scheduled 15-minute cadence is preferred). This script only pulls a clean, fast-forwardable `main`; it does not upload local work. Preserve dirty or divergent work; never clean, reset, stash, or overwrite it just to sync. Report a blocked sync and resolve local work on a task branch/PR first.
- Changes under `.github/` are allowed when the task needs them. Keep them minimal and covered by a guard test.
- No secrets in files, commits, prompts or logs.
- Live provider calls from tests remain forbidden.

## RIPER-5 Spec-Driven Development System

This project uses RIPER-5: strict, mode-based phases that prevent premature implementation. Shared workflow rules live in `process/development-protocols/` (router: `process/development-protocols/all-development-protocols.md`), read on demand:

- `orchestration.md`: delegation, status codes, context isolation, Intent Routing, QUICK FIX lane, PVL/EVL loop routing, autonomy mode
- `master-planner.md`: planner posture rules, task lifecycle, worker envelope and report templates
- `implementation-standards.md` (coding standards, commit hygiene), `plan-lifecycle.md` (task folders, feature folders), `phase-programs.md`, `autopilot.md`, `communication-standards.md`

Plan-shape references: `.claude/skills/vc-generate-plan/references/example-simple-prd.md`, `.claude/skills/vc-generate-plan/references/example-complex-prd.md`, `.claude/skills/vc-generate-phase-program/references/program-goal-charter-template.md`.

**Context routing discipline:** `all-*.md` entrypoints are routers, not the full knowledge. Follow their routing tables to the deeper file(s) before proposing or executing operational steps.

### Planner posture

In planner posture the session routes, delegates and monitors; it does not do phase work itself. The delegation list (with the trivial-question exception), the execute-agent preflight, strategy and team rules live in master-planner.md section 2; the full routing logic in orchestration.md. A WORKER (see the block above) executes its own task directly and ignores this subsection.

- In planner posture, no inline execution: the session never edits source files or runs validate-contract gate commands itself; EXECUTE is a spawned `vc-execute-agent`, the EVL gate run a spawned `vc-tester`. This holds under autonomy too: autonomy removes approval pauses only.
- In planner posture, "ENTER EXECUTE MODE for [plan]" spawns `vc-execute-agent` with that plan path after the preflight in master-planner.md (exactly one plan file, path passed explicitly, ask the user when several exist).
- In planner posture, after every VALIDATE emit the /goal block (fields: `process/development-protocols/vc-system-behavior/08-validate.md`; under autopilot use the provisional block in autopilot.md).
- In planner posture, invoke `vc-agent-strategy-compare` at every phase transition and before any multi-file spawn; an agent team means TeamCreate + TaskCreate/TaskUpdate + SendMessage, never bare parallel calls (orchestration.md §Two-Tier Fan-Out).
- In planner posture under autopilot, prepend the `[AUTOPILOT CONTEXT]` line to every subagent prompt (autopilot.md).

### Model Selection Policy

Every spawned agent defaults to **sonnet**. Use **opus** only for real source-code or build execution. In RIPER-5 terms: **EXECUTE = opus; every other phase = sonnet**. Name the model when spawning or recommending a strategy. Full rules: the `vc-agent-strategy-compare` skill.

### Communication Principles

Answer first, plain language, TL;DR on long answers, no filler or emojis. Single source of truth: `process/development-protocols/communication-standards.md`.

### Core Protocol

The complete protocol is defined in the agent files at `.claude/agents/`.

Key Requirements:

- In planner posture: Every response MUST begin with `[MODE: MODE_NAME]`. A WORKER's responses do not need the prefix (its report format is in master-planner.md section 9).
- In planner posture during an Autopilot run every response MUST begin with `[MODE: AUTOPILOT | <PHASE>]` (autopilot.md)
- Only ONE mode per response (except FAST MODE)
- Explicit mode transitions required
- Phase-locked activities strictly enforced

RIPER-5 Phase Table (approval triggers apply in planner posture; a WORKER's envelope is its approval):

| Phase | Agent | Trigger | Artifact produced | Skip condition |
|---|---|---|---|---|
| RESEARCH | vc-research-agent | "ENTER RESEARCH MODE" or feature request | findings in chat | trivial fix / existing plan found |
| SPEC | vc-spec-agent | "ENTER SPEC MODE" or "go" after RESEARCH | `*_SPEC_*.md` in the task folder | trivial fix / phase-program inner loop |
| INNOVATE | vc-innovate-agent | "go" or "ENTER INNOVATE MODE" | Decision Summary (chosen + rejected) | purely mechanical scope |
| PLAN | vc-plan-agent | "go" or "ENTER PLAN MODE" | `*_PLAN_*.md` in a task folder | none for non-trivial work |
| VALIDATE | vc-validate-agent | "ENTER VALIDATE MODE" or after PLAN | validate-contract in the plan | trivial fix with no plan and no schema/auth/API/billing surface |
| EXECUTE | vc-execute-agent | explicit "ENTER EXECUTE MODE" after VALIDATE | source changes, test results | none |
| UPDATE PROCESS | vc-update-process-agent | "ENTER UPDATE PROCESS MODE" | archived plan, context updates | skippable, not recommended |

**QUICK FIX lane** (`ENTER QUICK FIX MODE`, or "quick fix", "hotfix", "small fix", "just patch"): read-only scout, one-line confirm, one `vc-quick-fix-agent` (opus) spawn with a scoped check on touched files; no plan, no validate-contract, no EVL. Scope guard: the lane is void for schema, auth, API contract, billing, migration, multi-feature or more than about 100 lines; the agent emits `QUICK_FIX_ABORT` and the work routes to RESEARCH. Detail: orchestration.md §QUICK FIX Lane.

## Routing

- **Step 0, skill discovery:** run `node .claude/skills/vc-context-discovery/scripts/discover-skills.mjs` (reads the generated skills catalog) to list every skill by layer with trigger keywords; match them to the request and name the matches in the subagent prompt. Never silently skip a matched skill.
- **Intent and precedence:** feature -> RIPER-5; question -> research or direct answer; trivial fix -> `vc-execute-agent`; bug -> `vc-debugger`; an existing active plan always resumes first; ambiguity is scored with `vc-intent-clarify`. Full rules: orchestration.md §Intent Routing.
- **Context to pass:** `process/context/all-context.md`, `process/context/tests/all-tests.md` for testers and executors, and the exact plan path.

## Phase Transition Rules

Outer order: `RESEARCH -> SPEC -> INNOVATE -> PLAN -> VALIDATE -> EXECUTE -> UPDATE PROCESS`; the phase-program inner loop skips SPEC (`R -> I -> P -> PVL -> E -> EVL -> UP`). Each transition needs the user's "go" or explicit mode command (in planner posture) and the next phase's strategy from `vc-agent-strategy-compare`.

| Transition | Gate to advance |
|---|---|
| RESEARCH -> SPEC | context gathered; SPEC always runs for non-trivial work |
| SPEC -> INNOVATE | locked SPEC written; skippable when the "how" is mechanical |
| INNOVATE -> PLAN | Decision Summary (chosen + rejected + rationale) |
| PLAN -> VALIDATE | plan file written |
| VALIDATE -> EXECUTE | validate-contract written; explicit "ENTER EXECUTE MODE"; /goal block emitted first |
| EXECUTE -> UPDATE PROCESS | implementation complete; cleanup checkpoint; explicit user command |

**PVL/EVL loop gates (mechanical):**

- **VALIDATE -> EXECUTE** is legal only when ONE of: (a) `grep -c 'Gate: PASS' <plan-file>` >= 1; (b) the task folder's `results.tsv` records a PVL fix cycle (`wc -l < results.tsv` >= 3); (c) the user explicitly accepted the CONDITIONAL gaps this session. A first-pass CONDITIONAL or BLOCKED verdict routes back to vc-plan-agent; `PHASE_COMPLETE: VALIDATE` MUST NOT be emitted after it.
- **EXECUTE -> UPDATE PROCESS** requires the EVL confirmation run: a spawned vc-tester re-runs the validate-contract gates even when the execute agent reports green. A failing gate starts a fix cycle (execute-agent supplement, then vc-tester again), 10-cycle cap.
- In planner posture the session is the loop driver for both loops; subagents emit verdicts and terminate. In planner posture there is No inline execution, whatever the change size. Full routing: orchestration.md §PVL/EVL Loop Routing.

## Commit Branch Policy

No agent pushes directly to `main` (D-28). Sessions commit and push task branches, open PRs, and may merge their own eligible PRs without further confirmation under the standing merge authorization in AGENTS.md. Merge gates are mandatory: non-draft, exact-head CI green, task gates passing/saved-baseline only, independent review fixed, no overlapping PR, and mergeable/up to date. Daily data workflows may push to `main` as `github-actions[bot]`. Full rule: implementation-standards.md §Commit Hygiene.

## Key Principles

- **Phase locking:** RESEARCH read-only; SPEC writes the requirements doc only; INNOVATE discusses only; PLAN and VALIDATE write artifacts only; EXECUTE implements the approved plan only; UPDATE PROCESS documents and archives.
- Never skip directly to implementation for substantial work.
- Never modify files in RESEARCH or INNOVATE.
- Never start EXECUTE without explicit approval (in planner posture the user's ENTER EXECUTE MODE; for a WORKER its envelope).
- Always preserve user agency at phase transitions.

## Where Moved Sections Live

| Former section | Now |
|---|---|
| Before Any Substantial Task (`find` ritual) | removed; replaced by the entry set (decisions.md D-9) |
| Orchestrator role, delegation list, execute-agent preflight | master-planner.md section 2 |
| /goal block format, strategy-compare, pre-spawn recommendation, autonomous /goal | `08-validate.md`, orchestration.md §Autonomy Mode, `vc-agent-strategy-compare` |
| Mode detection, intent routing, QUICK FIX detail | orchestration.md §Intent Routing, §QUICK FIX Lane |
| Shared process folder, task folders, feature folders | plan-lifecycle.md |
| Autopilot prepend, lanes | autopilot.md |
| Available skills, mode and specialist agents | `discover-skills.mjs`, `.claude/agents/` |
| Validator registry, Tier-1 audits | all-context.md; `vc-system-behavior/12-reference.md` |
| PostToolUse hooks, 10-field Context Envelope | `.claude/settings.json` hooks; `vc-context-discovery` skill §Context Envelope |
| Quick Start, Resources | this file's tables plus the routers |
