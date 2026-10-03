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
