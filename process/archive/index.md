# Archive Index

**Index only, not a second store.** One row per archived item: where it went, when, and at which commit. Archived documents themselves stay in their `completed/` folders or under `process/archive/`. The Approvals Log below records every approval that permits an archive, move or removal; an empty log means no removal is permitted (plan AC-R6). Protocol: `process/development-protocols/master-planner.md` (section 10, the four archive operations).

## Archived items

| Date | Task | Status | Branch | Commit | Location |
|---|---|---|---|---|---|
| 2026-10-03 | R13 / T12: LSE data verification task folder moved `active/` -> `completed/` (operation A) | archived (verdict ADOPT-WITH-LIMITS) | salvaged from `claude/exciting-meitner-hy50kn` (`08cd839`) onto `claude/pensive-albattani-ou0cgv` | `448b10c` | `process/general-plans/completed/lse-data-verification_17-09-26/` |
| 2026-10-03 | R14 / R5: MASTER-PLAN revisions 1 to 6 relocated when the registry was rebuilt | archived (history) | revision 6 from `claude/pensive-dijkstra-ko69oi` (`18ffd4f`) | `dafa781` | `process/archive/master-plan-revisions_02-10-26.md` |
| 2026-10-03 | R3: all-context.md changelog, Open Questions, References, Scan Metadata and retired text moved | archived (history) | `claude/pensive-albattani-ou0cgv` | `bcb62e4` | `process/context/context-changelog.md` |

## Approvals Log

One row per approval: date, what was approved, approver quote, status. Each later automatic branch deletion under the standing consent adds a row (date, branch, merge SHA, report path, 'standing consent 02-10-26', status `pending`, then `done`, `failed` or `deletion deferred`), written before the deletion.

| Date | What | Approver quote | Status |
|---|---|---|---|
| 02-10-26 | Archive operation A: move `lse-data-verification_17-09-26` from `process/general-plans/active/` to `process/general-plans/completed/` as part of the selective salvage of `claude/exciting-meitner-hy50kn` (R13); branch not deleted | User answer to Q4, 02-10-26, as recorded in the master-planner-recovery plan: "salvage `claude/exciting-meitner-hy50kn` selectively (LSE verdict + status-strip fixes; drop the duplicate status board section in `all-context.md`)" | done 2026-10-03, commit `448b10c` |
| 02-10-26 | Standing consent for branch deletion, scope: merged worker task branches only (`claude/<task-id>-<slug>` created by the Master Planner for a registry task), after verified merge, committed report and registry `accepted` then `archived`; not the 12 pre-existing branches, not worktrees | User, 02-10-26: "delete merged task branches after verified merge and saved report" | active (no deletion performed yet) |
| 03-10-26 | Gate 5 prep: ENTER EXECUTE MODE for Gate 5 prep; T20 and T16 `approved` as the worker pilot; T17 (H1) cancelled; R12 stays `proposed` (deferred) | User, 03-10-26, as relayed by the Master Planner: "ENTER EXECUTE MODE for Gate 5 prep"; H1 "LEAVE AS IS"; deploy fixes R12 "deferred" | done (registry updated at commit after `ebf36ac`) |
| 03-10-26 | G5-K1 = B: the user merges PR #13 first; workers branch from and target `main` after that | User, 03-10-26: "G5-K1 = B (the user merges PR #13 first; workers start from main after that)" | active (PR #13 not merged yet) |
| 03-10-26 | G5-K2: spend ceiling for the pilot (estimate 8-24 USD, labelled estimate) | User, 03-10-26: "spend ceiling up to $40 for the pilot" | active |
| 03-10-26 | G5-K3: the planner may commit and push `process/` bookkeeping to the session branch only (never `main`, never merging PR #13) | User, 03-10-26: "planner may commit/push process/ bookkeeping to the session branch only" | active |
| 03-10-26 | G5-K7: direct worker lane (no quick-fix subagent for these RT0 tasks); the planner may merge for a worker that lacks a merge tool ONCE, only if its own REST checks show CI green on the head, only owned files changed, no conflicts, report committed, logged here | User, 03-10-26: "direct worker lane confirmed ... the planner may merge for a worker that lacks a merge tool ONCE" | active (not used yet) |
| 03-10-26 | G5-K9: Gate 6 folded into the Gate 5 contract | User, 03-10-26: "Gate 6 folded into this contract" | active |
| 03-10-26 | G5-K4 = A: accept GitHub `delete_branch_on_merge` for worker branches; log a row right after each merge | User, 03-10-26: "G5-K4 = A accept GitHub's delete_branch_on_merge and log the Approvals Log row right after the merge" | active (no merge yet) |
| 03-10-26 | Pilot workers T20 and T16 spawned from `main` under the G5-K2 ceiling of 40 USD (platform-reported cost 0.88 + 0.76 = 1.64 USD); workers did not use the session tools their envelopes forbade | G5-K1 = B, G5-K2, G5-K7 above | done |
| 03-10-26 | T16 (PR #14, `351f946`) and T20 (PR #15, `54157e2`) squash-merged, CI green, independently verified by vc-tester on `54157e2` (2026-10-03T06:33Z, all gates PASS); no branch deletion logged (repo setting `delete_branch_on_merge` unverified); archive_session and task-folder archival not yet done | G5-K4 = A, G5-K7 above | done (merge, verification); archival pending |
| 03-10-26 | Branch-deletion PROPOSAL for six branches (`claude/compassionate-goldberg-o2iq49`, `claude/p1-pipeline`, `claude/p2-deploy`, `claude/ui-shell`, `claude/vigilant-hamilton-grr18c`, `fix/narrative-sufficiency-gating-rfc1`) and the guarded deletion probe | User, 03-10-26: proposal allowed; final OK (G5-K6) and probe approval (G5-K5) not given | pending (nothing deleted, probe not run) |
