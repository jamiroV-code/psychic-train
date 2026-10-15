---
name: report:data-integration-tooling-pvl-iteration-006
description: "PVL of Amendment A2 (S-T8 cloud-run support, T64) vs origin/main c55a83d"
date: 15-10-26
metadata:
  node_type: memory
  type: report
  feature: data-integration-tooling
---

# PVL 006: Amendment A2 (S-T8, T64)

**Verdict: BLOCKED (1 FAIL, 8 CONCERN).** The FAIL is a one-line scope fix. No plan edit, no Gate stamp. Checked against origin/main c55a83d, plan lines 345-362.

## FAIL

**F1. Path guard on evidence breaks an existing test (plan 354, 360).** `paths.evidence_dir()` is called at `rea/wrapper.py:112`, before the wrapper's own `_within` check (113). `test_rea_wrapper.py:231-238` (`test_evidence_inside_repo_refused`) sets `DIT_EVIDENCE_DIR` inside the repo and expects `Refusal("evidence_in_repo")`; it would get an uncaught `PathInRepo`. The test and wrapper are forbidden files, so "fix the fixture" (360) is impossible. Fix: guard `approvals_dir()` and `scrape_dir()` only; evidence keeps the wrapper guard. Other repo-touching tests (`test_adaptive.py:26`, `test_skeleton.py:76`, `test_cli.py:31,535`) use tmp_path or the outside default: safe.

## CONCERN

1. **TTY rule (353).** Give the 4-row matrix: statement+TTY refuse; statement+no TTY allowed; no statement+TTY interactive (unchanged, `approval_cli.py:46-58`); no statement+no TTY refuse (unchanged). The statement path never calls `input_fn`. "any `--host`" is ambiguous: require source AND every host. Refuse unless `DIT_APPROVALS_DIR` is explicitly set, so a test or CI job cannot write the default store. Add a guard: no workflow, script or `api/` file contains `--owner-statement` or `scrapling install`.
2. **Forgery control (357).** The honest limit is stated. Strengthen the control: the statement is the owner's message pasted verbatim, and the worker report quotes it with the message time. Say who runs it. CLAUDE.md planner posture forbids inline execution, so a worker whose envelope quotes the owner message runs it, not "the planner".
3. **`_repo_root()` (`paths.py:9-14`) inserts into `sys.path`.** Use a side-effect-free checkout-root helper in `_dir()`. `PathInRepo` carries a fixed message, no path. `approval_cli` catches it and exits 2 (`cli.py:265` prints only the type name).
4. **Install (355).** S-T4 (plan ~146) says never run `playwright install`, and cloud has `/opt/pw-browsers`. Use that Chromium first; `scrapling install` only if absent and the owner asked for a tier 2/3 run.
5. **Docs scope (352, 356).** Still contradictory and unowned: `all-data-sources.md:415` ("owner-run... Workers never run live commands"), step 4 line 421 (needs `--owner-statement`), `decisions.md:147` ("owner's PC only"), plan Safety rules 68-71 and S-T6 step 4 ("never in the cloud", lines 174-184), SPEC L5. Own 415 and 421; record the rest as planner-side edits.
6. **Read list (361).** `approvals.py` 12-17, 59-75 is wrong; the worker must edit `ApprovalRecord` and `_from_dict`: use 51-72 and 81-100 (1,597 B). Measured: CLAUDE.md 13,443 + envelope 4,000 + Common 58-75 3,011 + subsection 3,521 + approval_cli 44-end 2,167 + approvals 1,597 + paths 983 + docs section 2,192 = 30,914 B (<= 35,000). Disjoint: S-T4 owns fetch_tier2/3 and README; S-T6 owns notes only. Add baselines: tooling >= 523, guards >= 49, API >= 1192/1/5 (verified in the S-T7 report).
7. **AC-27 guard is not red-first (359).** Base text is "stay on the owner's PC" and already names `DIT_APPROVALS_DIR`. Assert that "stay on the owner's PC" is absent and "owner-statement" is present. The no-tracked-record guard already exists (green on base).
8. **Scraped data (6).** Output goes to `api/data/cache/ohlcv/` (gitignored, `.gitignore` 18-19) and is lost when the session ends. Add a guard that the cache path is ignored. Farside is untouched. gate.py is unchanged, and no refusal widens.

## Pass

gate.py unchanged (AC-26). Cost 1.2-2.5 USD; 97.66 + T59 6.0 + T61 5.0 + T64 2.5 = 111 of 130 USD.

## DIT-10 (plan 362)

The format matches `decisions.md:138-146`. Add "the statement cannot prove a human wrote it" and "executed by a worker, not inline by the planner". Also append "(cloud: DIT-10)" to line 147.
