---
name: pipeline-completeness-atomic-writes-pvl-iteration-001
description: "PVL supplement cycle 1 for the atomic-parquet-writes plan (P2 handoff, Open Question 9): independent second-look findings folded into the plan."
date: 29-09-26
metadata:
  node_type: report
  type: pvl-iteration
  domain: plan
  iteration: 1
  read_when: "auditing the PVL loop for the atomic-writes plan"
---

# PVL Iteration 001 — atomic-writes plan

**Plan:** `pipeline-completeness-atomic-writes_PLAN_29-09-26.md` (separate from the P1 plan; this folder's `results.tsv` is shared, so its rows are labelled `[atomic-writes]`).

## Entry state
Fast-mode inline validate: `Gate: CONDITIONAL`, 0 FAIL, 2 CONCERN, both structural. An independent `vc-validate-agent` second look then found the gate was not merely structural: **0 FAIL, 3 fixable concerns + 1 scope finding** (N1–N3, N4).

## Gaps addressed (4 of 4)
| ID | Finding | Resolution |
|---|---|---|
| N1 | `etf_flows_adapter.merge_into_cache` (`:103-111`) writes a gitignored cache parquet directly, in the request path of `/api/regime/components` — a bypass of the planned helper | **Scope ruling: recorded, not widened.** KG5 + backlog stub + G1/AC(a) reworded to "`cache.py` only" + explicit statement that P2 AC12 is NOT fully met until that writer is also atomic. Follow-up needs a user scope decision. |
| N2 | `chmod 0644` "preserves the previous mode" only under umask 022; loosens a 0600 file under umask 077 | Copy the existing target's mode when present, else 0o644; caveat documented; `test_mode_handling` added |
| N3 | Test-plan traps: a handle-only fake passes vacuously on old code; second calls may not reach the write; no isolation canary; global `os.replace` fake; docstring could break the `to_parquet(` count | All five fixed in checklist step 2 |
| N4 | Hash-only snapshot misses an identical-content rewrite (parquet is deterministic) | Snapshot now includes size + mtime + `watchlist.json`, alongside sha256 |

## Verified by the validator (not assumptions)
Handle-based and path-based `to_parquet` give **byte-identical** files for six frames (tz-aware UTC, None, Arrow-string/Int64, bool/NaN, empty typed, sorted index); exception paths leave the original byte-identical with zero fd leak; every reader glob is `*.parquet`/`*.json` or an exact path so cannot match the temp name; `git check-ignore` proves the `.gitignore` rule in tracked dirs with a throwaway repo.

## Exit state
`SUPPLEMENT_APPLIED` — 4 of 4 addressed, scope unwidened, plan validator clean. KG1 (real power loss) and KG2 (Windows open-reader `os.replace`) remain structural known-gaps; no human accepted them. **Next:** re-spawn `vc-validate-agent` from V1.
