---
name: report:screener-batch3-s5b-pvl-iteration-005
description: "PVL cycle 4 fix cycle: minimal plan edits folding F1-F4 of iteration 004 into the screener batch 3 plan"
date: 10-10-26
metadata:
  node_type: memory
  type: report
  feature: general-plans
  phase: "S5b"
---

# PVL iteration 005 (S5b, fix cycle 1 of 2): F1-F4 folded

Plan-agent role, minimal edits in place, ASCII, `git diff --check` clean. Line count unchanged by the fixes (519), so no S5b range moved; only line 166 changed bytes.

| Fix | Edit | Bytes |
|---|---|---|
| F1 | line 166: "spaghetti; remove closes" to "spaghetti, and remove closes"; "no groups; a later one" to "no groups, and a later one"; clause count now 15 (checked by script) | +8 in the S5b set |
| F2 | line 12 folder index (s5b report names); lines 198, 209, 210, 405 (AC-S5b-11 and AC-S5b-12 mapped); line 224 (T40 and T41 registered); the status, header, Resume and goal-block refresh was deferred to the stamp step | 0 in ranges |
| F3 | line 512: code reads for C4 are `api/routers/layout.py` and `api/data/layout.py` (422 rules, `GROUP_ID_RE`) | 0 in ranges |
| F4 | AC-S5b-12 row (line 270) reworded | 0 in ranges |

Figures re-derived from the saved file after the edits: S5b 20,429 B (66 lines), room 2,128 B (2,450 B with operating-instructions.md), spare about 128 B against the 2,000 B envelope guide, S5a (merged) 20,238 B, union 38,240 B, 15,683 B over the cap. Updated in line 72, the envelope paragraph (room 2,128), the table row and the paragraph after it; the planner's history item f carries a one-line cycle 4 note.

Not edited: any source file, MASTER-PLAN, current-state, the archive index, S5a text, the cycle 3 record.
