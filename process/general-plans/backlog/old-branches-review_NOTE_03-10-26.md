---
name: note:old-branches-review
description: "Backlog: per-branch review of the six remaining non-main branches, tester facts and user decisions 03-10-26; three deletions by the user, three on hold until T31"
date: 03-10-26
feature: general
---

# Old branches review (backlog note)

- **Problem:** six remote branches besides `main` and the session branch. Tester review 2026-10-03 ~19:25Z (measured). None is an ancestor of main; DELETE calls rest on PR records, not tree diffs. The planner cannot delete branches; the user deletes in GitHub's UI, the planner re-checks with `git ls-remote --heads origin`.

| Branch | Tip | Facts | User decision 03-10-26 |
|---|---|---|---|
| `exciting-meitner-hy50kn` | 08cd839 | all content on main or superseded; only a 5-line addition to `backlog/yfinance-equity-source_24-09-26.md` is not (dropped by decision) | DELETED by the user (verified ~19:33Z) |
| `narrative-v2` | 2cf85a0 | code already on main via PR #7; only 3 RFC-001 reports plus a PLAN handoff edit not on main; model retired by baskets SPEC AC-11 (dropped by decision) | DELETED by the user (verified ~19:33Z) |
| `pensive-dijkstra-ko69oi` | 18ffd4f | PR #6 merged; MASTER-PLAN revisions superseded by the Gate 2 rebuild; not tree-diffed | DELETED by the user (verified ~19:33Z) |
| `kind-tesla-tat3vo` | 4fd60bd | its one commit (chain-growth closeout) is NOT on main. The earlier "probably DELETE-SAFE" call was WRONG | HOLD until T31 merges (still on origin) |
| `inspiring-pasteur-awqxk3` | efe69aa | carries 4fd60bd; PR #5 (open) targets base `kind-tesla-tat3vo`, 2 files +2/-2 (`growth.py` docstring, `probe_chain_sources.py:73` DEFAULT_OUT -> completed); merging it onto main would break the probe script path; no CI | HOLD until T31; PR #5 closed by the user ("T31 carries the rescue") |
| `split-all-context` | bf65024 | UNIQUE: chain-growth archive folder, CLOSEOUT note, 2 review-decision.json, and an "On-chain Activity" section in `all-data-sources.md` (main has 0 matches for growthepie); its other context edits are superseded | HOLD until T31 |

- **Rescue:** T31 (`active/t31-chain-growth-rescue_03-10-26/`, `approved`, not spawned) applies the unique content onto main fresh. After T31 merges, the three held branches are deletable.
