---
name: note:gate5-deferred-candidates
description: "Backlog: Gate 5 candidates the user did not choose on 03-10-26 (deploy fixes, docs, triage, branches, housekeeping, performance baselines, telemetry)"
date: 03-10-26
feature: general
---

# Gate 5 deferred candidates (backlog note)

**TL;DR:** On 03-10-26 the user chose only T20 and T16 (as the worker pilot), declined H1 and allowed a six-branch deletion proposal. Everything below was not chosen and stays deferred; nothing here is approved work. Source: master-planner-recovery plan, Validate Contract Gate 5, instruction E4.

Each item: not chosen by the user on 03-10-26.

- **R12 deploy fixes** (kill-by-port before build, stale-build guard in `start-web`, post-start smoke check): MOVED TO THE REGISTRY 03-10-26 as `blocked` (high-risk deploy class; brief `process/general-plans/active/r12-deploy-fixes_03-10-26/`); becomes `approved` only on VALIDATE plus the user's confirmation of the brief.
- **R10** deploy-path doc plus stale-build guard proposal.
- **R11** archive index growth and session triage.
- **Pre-existing branches outside the six-branch proposal:** `kind-tesla`, `narrative-v2`, `inspiring-pasteur` (PR #5 open), `pensive-dijkstra`, `exciting-meitner`, `split-all-context`: each needs a per-branch review and the user's approval before any deletion.
- **H4 and H5** salvage state of older branches.
- **H6 / T18** dead `write/read_confirmed_boundaries` functions in `cache.py`: MOVED TO THE REGISTRY 03-10-26 as `proposed` (brief `active/t18-dead-boundaries_03-10-26/`).
- **H7 / T19** stale plans in `active/` to archive: MOVED TO THE REGISTRY 03-10-26 as `proposed` (brief `active/t19-archive-stale-plans_03-10-26/`).
- **H10** scout-hook note.
- **Performance baselines** (plan section 8 list): MOVED TO THE REGISTRY 03-10-26 as `PERF`, `proposed` (brief `active/perf-baselines_03-10-26/`).
- **T21** `cache.py` refactor; **T22** cache-isolation trap in tests.
- **Token-usage telemetry** (`token-usage-telemetry_NOTE_02-10-26.md`): the pilot report adds platform-reported per-session cost.

Declined, not deferred: **H1 / T17** `.agents/skills` symlink (user: leave as is; accepted gap, see `agents-skills-symlink-windows_NOTE_02-10-26.md`).

**Update 03-10-26:** the user turned R12, T18, T19 and PERF into registry tasks with briefs (none approved; no worker may start). Items still deferred here: R10, R11, the six other branches, H4/H5, H10, T21, T22, telemetry.

**How to close:** pick an item with the user, give it a registry row and brief, run VALIDATE for it.
