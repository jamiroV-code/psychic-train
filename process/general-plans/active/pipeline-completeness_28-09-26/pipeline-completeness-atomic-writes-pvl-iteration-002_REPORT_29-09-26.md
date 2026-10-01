---
name: pipeline-completeness-atomic-writes-pvl-iteration-002
description: "PVL supplement cycle 2 for the atomic-parquet-writes plan: three concerns from the V1 re-run folded in, including a gate that could never pass."
date: 29-09-26
metadata:
  node_type: report
  type: pvl-iteration
  domain: plan
  iteration: 2
  read_when: "auditing the PVL loop for the atomic-writes plan"
---

# PVL Iteration 002 — atomic-writes plan

**Plan:** `pipeline-completeness-atomic-writes_PLAN_29-09-26.md`. Rows in the shared `results.tsv` are labelled `[atomic-writes]`.

## Entry state
V1 re-run after cycle 1: cycle-1 fixes N1–N4 verified landed (N3 partly), **0 FAIL, 3 new fixable concerns**. Cycle 1 had itself been triggered by an independent second look at a plan that had passed its author's own inline validation.

## Gaps addressed (3 of 3)
| ID | Finding | Severity | Resolution |
|---|---|---|---|
| N6 | Gate G1 `grep -c "to_parquet(" cache.py` = 1 **could never pass**: it returns 11 after the change because the helper's own name `_atomic_to_parquet(` contains the substring (measured on a patched copy). Left as written, EXECUTE would either fail its own gate or weaken it to get past it. | high | Gate now `grep -c '\.to_parquet(' cache.py` = 1 and `grep -c '_atomic_to_parquet(' cache.py` = 10; docstring rule fixed; the no-dot pattern is explicitly barred as a gate |
| N7 | `write_liqtide_payload` interrupted-write test was vacuous: a new date targets a different file, so the original is never at risk and it passes on unmodified code | medium | Asserts the new-date path does not exist, no temp remains, date-1 file byte-identical. The plan states what this proves and what it does not (overwrite atomicity for this writer is covered only at helper level, because of its no-overwrite guard) |
| N8 | Mode lookup for the existing target unspecified; `exists()`-then-`stat()` races | low | `try: os.stat(path).st_mode & 0o7777 / except FileNotFoundError: 0o644` |

Also defined `$SCRATCH` (undefined in the plan) so EXECUTE cannot leave it empty.

## Verified by the validator (carried forward, not assumptions)
A 40-case scratch experiment against unmodified `cache.py`: a truncating Path-fake fails **8 of 9** real writers ("original corrupted"), while a handle-only fake passes **9 of 9 vacuously** — so the Path-truncating fake is essential. All nine writers produce byte-identical files before and after the swap. The `.gitignore` rule stages 6 real parquets and 0 temps in a throwaway repo.

## Exit state
`SUPPLEMENT_APPLIED` — 3 of 3, scope unwidened, validator clean. KG1–KG5 remain recorded, none accepted by a human. **Next:** re-spawn `vc-validate-agent` from V1.
