---
name: note:old-branches-review
description: "Backlog: per-branch review of the six remaining non-main branches; user decides delete or keep; none deleted"
date: 03-10-26
feature: general
---

# Old branches review (backlog note)

- **Problem:** six remote branches besides `main` and the session branch are still open. Review measured by a tester on 2026-10-03. None is an ancestor of main, so every DELETE-SAFE call rests on squash-merge PR records and is NOT tree-verified.
- **Decision pending (user):** per-branch delete or keep. None deleted; the planner cannot delete branches.

| Branch | Tip | Date | Ahead | PR | Content | Call |
|---|---|---|---|---|---|---|
| `exciting-meitner-hy50kn` | 08cd839 | 2026-09-24 | 7 | none | LSE data verification (EVL logs, verify_provider fix, ADOPT-WITH-LIMITS verdict, status board); 16 files +1200/-330; 2 of 3 spot paths identical to main | REVIEW, leaning delete |
| `inspiring-pasteur-awqxk3` | efe69aa | 2026-09-28 | 2 | open #5 | not summarised | REVIEW |
| `kind-tesla-tat3vo` | 4fd60bd | 2026-09-28 | 1 | #4, #3, #1 merged and closed | its commit also carried by inspiring-pasteur and split-all-context | probable DELETE-SAFE |
| `narrative-v2` | 2cf85a0 | 2026-09-28 | 3 | none | unique RFC-1 Stage 0 work plus resume handoff (plan says RFC-2 next); 18 files +658/-72 | KEEP |
| `pensive-dijkstra-ko69oi` | 18ffd4f | 2026-10-01 | 5 | #6 merged | 5 later MASTER-PLAN revisions (+313, one file); MASTER-PLAN differs from main | probable DELETE-SAFE only after confirming main holds a newer version (registry rebuilt from rev 6 at Gate 2, likely superseded, unverified) |
| `split-all-context` | bf65024 | 2026-09-28 | 2 | none | carries 4fd60bd plus the all-context -> context-changelog split (superseded by the Gate 2 router slimming, unverified) | REVIEW |

- **Fix option:** after the user decides, the user deletes the chosen branches in GitHub's UI; the planner re-checks with `git ls-remote --heads origin` and logs the result in the Approvals Log.
