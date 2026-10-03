---
name: note:gate5-deferred-candidates
description: "Backlog: Gate 5 candidates the user did not choose on 03-10-26 (deploy fixes, docs, triage, branches, housekeeping, performance baselines, telemetry)"
date: 03-10-26
feature: general
---

# Gate 5 deferred candidates (backlog note)

**TL;DR:** On 03-10-26 the user chose only T20 and T16 (as the worker pilot), declined H1 and allowed a six-branch deletion proposal. Everything below was not chosen and stays deferred; nothing here is approved work. Source: master-planner-recovery plan, Validate Contract Gate 5, instruction E4.

Each item: not chosen by the user on 03-10-26.

- **R12 deploy fixes** (kill-by-port before build, stale-build guard in `start-web`, post-start smoke check): high-risk deploy class; stays `proposed`; becomes `approved` only on confirmation of its brief.
- **R10** deploy-path doc plus stale-build guard proposal.
- **R11** archive index growth and session triage.
- **Pre-existing branches outside the six-branch proposal:** `kind-tesla`, `narrative-v2`, `inspiring-pasteur` (PR #5 open), `pensive-dijkstra`, `exciting-meitner`, `split-all-context`: each needs a per-branch review and the user's approval before any deletion.
- **H4 and H5** salvage state of older branches.
- **H6 / T18** dead `write/read_confirmed_boundaries` functions in `cache.py`.
- **H7 / T19** stale plans in `active/` to archive.
- **H10** scout-hook note.
- **Performance baselines** (plan section 8 list).
- **T21** `cache.py` refactor; **T22** cache-isolation trap in tests.
- **Token-usage telemetry** (`token-usage-telemetry_NOTE_02-10-26.md`): the pilot report adds platform-reported per-session cost.

Declined, not deferred: **H1 / T17** `.agents/skills` symlink (user: leave as is; accepted gap, see `agents-skills-symlink-windows_NOTE_02-10-26.md`).

**How to close:** pick an item with the user, give it a registry row and brief, run VALIDATE for it.
