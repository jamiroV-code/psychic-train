---
name: note:deploy-runtime-user-pc-verification
description: "Backlog: R12 deploy fixes (kill-by-port, stale-build guard, smoke check) can only be verified at runtime on the user's PC"
date: 02-10-26
feature: general
---

# Verify the R12 deploy fixes on the user's PC (backlog note)

**TL;DR:** Registry task R12 adds a kill-by-port step before build, a stale-build guard in `start-web` and a post-start smoke check. CI and shape tests can only check the scripts' text; their real behaviour shows only on the Windows home PC.

- **What is unproven:** that the old web process is stopped, that a stale build is refused, that the smoke check catches a failed start, and that Task Scheduler and Tailscale behave as the runbook says.
- **Why:** no Windows, PowerShell or Tailscale on a CI runner or in the cloud container. The 2026-10-01 stale-build incident and the uvicorn trampoline fix were both found only on the PC.
- **How to close:** after R12 merges, the user runs the `deploy/README.md` parse check and dry runs, then a real restart after a `web/` change, and confirms the served build matches HEAD; record date, commit and result. Until then R12 stays at `review`.
- **Source:** master-planner-recovery plan, sections 4 and 8 and Verification Evidence known gaps; F15.
