---
name: context:omp-setup
description: "How the repo's agents, skills and model policy map to omp (oh-my-pi) on the owner's PC: model routing, the three user-level agents, phase-to-agent table, isolation, the PC git flow. Tagged OBSERVED (owner probe 2026-10-29), DOCUMENTED or UNVERIFIED."
keywords: omp, oh-my-pi, local agent, pc, planner, git flow, draft pr, sync, model roles, smol, slow, plan, task tool, skills inheritance, worker, riper-sonnet, riper-opus, grok-review, agent definition, model pin, isolation, plan mode
date: 29-10-26
---

# omp setup note (T217, rewritten T221)

Tags: **OBSERVED** = seen in the owner PC probe of 2026-10-29 (four children: one per agent plus a nameless spawn); **DOCUMENTED** = omp docs, not tested; **UNVERIFIED** = not checked. Live provider behaviour is proven only by owner probes.

## Model routing (OBSERVED)

- The `task` tool wire schema has no per-spawn model field. The model comes from the agent definition frontmatter or from a role.
- A spawn with no agent name lands on the TASK role, a Grok model (`xai-oauth/grok-4.7`). Rule: **never spawn without naming an agent.**

## User-level agents (OBSERVED)

Created by the owner outside the repo, in the owner's omp agents folder under the home directory; the files are not in git.

| Agent | Model | Allowed use | Probe result |
|---|---|---|---|
| `riper-sonnet` | `@default` (Sonnet 5.5) | every non-EXECUTE phase, reviews, docs | context block read `anthropic/claude-sonnet-5-5` |
| `riper-opus` | `@slow` (Opus 5.5) | EXECUTE only | context block read `anthropic/claude-opus-5-5` (self-reported; the `resolvedModel` field was not read: UNVERIFIED) |
| `grok-review` | `@task` (Grok) | reviews only, read-only tools `read`, `grep`, `glob`; NOT for code until the owner approves | `xai-oauth/grok-4.7` |

## Phase to agent

| Phase or job | Agent |
|---|---|
| RESEARCH, SPEC, INNOVATE, PLAN, VALIDATE, UPDATE PROCESS | `riper-sonnet` |
| EXECUTE (code or build slice) | `riper-opus` |
| EXECUTE of a docs-only (RT0) slice | `riper-sonnet` (owner decision for T221; Opus is for real code and build) |
| Independent read-only review | `riper-sonnet` or `grok-review` (`grok-review` never writes) |
| Anything else, or no agent name | not allowed |

## What omp does not load

- `.claude/agents` and `.codex/agents` are skipped by omp agent discovery (DOCUMENTED); their `model:` pins are inert. `vc-*` agents are not usable as omp agents.
- Children do not see `CLAUDE.md` or `AGENTS.md` (OBSERVED: all four probes saw none). An envelope must carry the role line and the hard rules inline. The 8,000-byte envelope cap stays a repo rule (master-planner.md section 8).
- `vc-*` skills are listed in a child's context (OBSERVED in the T221 PLAN session, not by the owner probe). Whether they trigger is UNVERIFIED.

## Plan mode (DOCUMENTED, not tested)

omp plan mode uses the PLAN role (Opus 5.5 for the owner); `--plan-yolo` executes on the smol role (Haiku). Rule: never use omp plan mode or `--plan-yolo` for RIPER phases or EXECUTE.

## Workers and isolation

- Local workers are subagents or separate sessions on the owner PC, not cloud containers: same disk, same credentials. Isolation is an isolated checkout or worktree plus a `claude/*` branch. Cloud behaviours (egress block, proxy) do not apply; do not assume them either way.
- `task.isolation.enabled=true` is saved in the owner config (OBSERVED); `isolated: true` gives a separate checkout; not available in omp plan mode (DOCUMENTED).
- `task.isolation.apply = true` (default, OBSERVED 2026-10-29): successful isolated worker changes are auto-applied into the parent checkout as untracked or modified files; the worker's own branch and commit do not exist there. A worker therefore publishes from its own isolated checkout (commit on its `claude/*` branch, push, ONE draft PR) and the planner must not publish the auto-applied copy again.
- Observed in the T221 PLAN session: the isolated checkout has a detached HEAD, no git remote at first, and `gh` needs `-R` with the repo slug. Publishing path: add `origin` from the planner-pasted public URL, fetch, push only the worker's own `claude/*` branch. Windows isolation backend behaviour beyond this is UNVERIFIED.

## Git flow (decided, D-28)

- omp runs on the owner's PC only for now; the server laptop joins later with the same rules.
- The PC pushes `claude/*` task branches and opens DRAFT PRs; it never pushes to `main`. Planner and direct-user sessions commit on a branch plus PR. The owner merges every PR.
- `main` on the PC is kept current by `scripts/pc-sync/sync-main.ps1` (fast-forward only); task branches go up through `scripts/pc-sync/push-task-branch.ps1`. See `scripts/pc-sync/README.md`.
- Branch protection is a GitHub ruleset with github-actions[bot] as bypass actor, set by the owner in GitHub settings. The daily data workflows push to `main` as github-actions[bot] and must stay unaffected.
- Secrets and cookie files stay outside the repo.

## UNVERIFIED list

- The `resolvedModel` field of each agent.
- The Windows isolation backend behaviour.
- The PowerShell scripts in `scripts/pc-sync` (never run; the owner runs `-WhatIf`).
- Ruleset Evaluate mode on a public free repo.
- Whether `vc-*` skills trigger.
- Plan mode and `--plan-yolo` behaviour.
- Worker and planner spend after 21-10-26.
