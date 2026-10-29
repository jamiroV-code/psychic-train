---
name: context:omp-setup
description: "How the repo's agents, skills and model policy map to omp (oh-my-pi) on the owner's PC, the PC git flow, and the worker model. Expectations are UNVERIFIED until the owner probes them."
keywords: omp, oh-my-pi, local agent, pc, planner, git flow, draft pr, sync, model roles, smol, slow, plan, task tool, skills inheritance, worker
date: 29-10-26
---

# omp setup note (T217)

**UNVERIFIED.** Everything under "Mapping" is an expectation from omp's documented ideas, not something this repo has run. The owner tests it on the PC; live provider behaviour is proven only by owner probes.

## Git flow (decided, D-28)

- omp runs on the owner's PC only for now; the server laptop joins later with the same rules.
- The PC may push task branches and open DRAFT PRs automatically. It never pushes to `main`.
- Planner and direct-user sessions commit on a branch plus PR. The owner merges every PR.
- `main` on the PC is kept current by `scripts/pc-sync/sync-main.ps1` (fast-forward only); task branches go up through `scripts/pc-sync/push-task-branch.ps1`. See `scripts/pc-sync/README.md`.
- Branch protection will be a GitHub ruleset with github-actions[bot] as bypass actor, set by the owner in GitHub settings, tested in audit mode through one daily refresh first. Until then it is procedure only. The daily data workflows push to `main` as github-actions[bot] and must stay unaffected.
- Secrets and cookie files stay outside the repo.

## Mapping (UNVERIFIED)

| Repo idea | Expected omp idea | To test |
|---|---|---|
| `.claude/agents/*` (research, plan, validate, execute, tester) | the `task` tool spawning a subagent with a role prompt | does omp load `.claude/agents` or need copies? |
| `.claude/skills/*` | omp skills inheritance from `.claude` | do `vc-*` skills show up and trigger? |
| Model policy: EXECUTE = opus, every other phase = sonnet | model roles: `smol` (cheap), `slow` (strong), `plan` (planning) | map EXECUTE to the strongest code model and the rest to the mid model; confirm the role names in the installed version |
| `CLAUDE.md` / `AGENTS.md` entry set | omp reads `AGENTS.md` | confirm the entry block loads and the worker/planner role split holds |

## Workers on the PC

Workers on the PC are local subagents or separate omp sessions, not cloud sessions. Each still gets a task envelope, works on `claude/<task-id>-<slug>` and ends with a draft PR. Cloud-session behaviours (container egress block, proxy) do not apply there, so do not assume them either way.
