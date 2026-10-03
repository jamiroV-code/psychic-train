# my_site

A personal-use data tracker for one trader: a web app backed by a Python API that shows market data, not verdicts. Direction and non-goals: [north-star.md](process/context/north-star.md).

## Layout

- `api/`: Python API and data pipeline.
- `web/`: web app.
- `deploy/`: home-PC launchers and scheduled tasks.
- `process/`: plans, context docs and development protocols.
- `.github/workflows/`: CI and snapshot jobs.

## Setup and commands

Build, test and run commands live in [operating-instructions.md](process/context/operating-instructions.md). First-time setup: [BOOTSTRAP.md](api/scripts/BOOTSTRAP.md). Deploy runbook: [deploy/README.md](deploy/README.md).

## How work is organised

Work follows the RIPER-5 phases described in [CLAUDE.md](CLAUDE.md). The task board is [MASTER-PLAN.md](process/MASTER-PLAN.md) and the worker protocol is [master-planner.md](process/development-protocols/master-planner.md).

## 1 Agents

| Agent | Purpose |
|---|---|
| `vc-code-reviewer` | Code review |
| `vc-code-simplifier` | Code simplification |
| `vc-debugger` | Root-cause debugging |
| `vc-execute-agent` | EXECUTE phase |
| `vc-fast-mode-agent` | Compressed workflow |
| `vc-git-manager` | Commits and pushes |
| `vc-innovate-agent` | INNOVATE phase |
| `vc-plan-agent` | PLAN phase |
| `vc-quick-fix-agent` | Quick-fix lane |
| `vc-research-agent` | RESEARCH phase |
| `vc-spec-agent` | SPEC phase |
| `vc-tester` | Testing |
| `vc-ui-ux-designer` | UI/UX work |
| `vc-update-process-agent` | UPDATE PROCESS phase |
| `vc-validate-agent` | VALIDATE phase |

## 2 Skills

`vc-agent-browser` `vc-agent-strategy-compare` `vc-audit-context` `vc-audit-plans` `vc-audit-vc` `vc-autopilot` `vc-autoresearch` `vc-context-discovery` `vc-debug` `vc-docs-seeker` `vc-feasibility-test` `vc-frontend-design` `vc-generate-closeout` `vc-generate-context` `vc-generate-phase-program` `vc-generate-plan` `vc-generate-spec` `vc-intent-clarify` `vc-plan-discovery` `vc-predict` `vc-problem-solving` `vc-publish` `vc-review-situation` `vc-risk-evidence-pack` `vc-scenario` `vc-scout` `vc-security` `vc-sequential-thinking` `vc-setup` `vc-test-coverage-plan` `vc-update` `vc-validate-findings` `vc-web-testing`

## 3 Notes

Commands, test tiers and branch rules: [operating-instructions.md](process/context/operating-instructions.md).
