---
name: report:data-integration-tooling-pvl-iteration-007
description: "PVL 007 of Amendment A2 (S-T8 cloud-run support, T64) vs origin/main c55a83d"
date: 15-10-26
metadata:
  node_type: memory
  type: report
  feature: data-integration-tooling
---

# PVL 007: Amendment A2 (S-T8, T64)

**Verdict: CONDITIONAL (0 FAIL, 6 CONCERN).** Plan lines 345-362 vs origin/main c55a83d. `Gate: PASS` count in the plan is 1 (line 324, old). No plan edit, no stamp.

## Prior items

F1 fixed: evidence is unguarded (354); `test_evidence_inside_repo_refused` (`test_rea_wrapper.py:231`) stays green. Fixed: TTY matrix (353), forgery control (357), install rule (355, `/opt/pw-browsers` first), planner checklist separate (362), ignored-cache guard (`.gitignore:18` ignores `api/data/cache/ohlcv/x`, verified), baselines 523/49/1192 (S-T7 report 25-27), cost 97.66+6+5+2.5 = 111.2 of 130 USD.

## CONCERN

1. **Line 353 logic.** "unless the text is ... or unless `DIT_APPROVALS_DIR` is set" is an OR: an env var alone defeats the statement check. Change "or unless" to "AND".
2. **Docs scope (352, 356, 358).** Step 4 is line 420; 421 is blank (422 is Exit codes). Unowned and contradictory: Rules bullet 427 ("stay on the owner's PC") and Known-limits 439, where step D wants the new limit. Own 415, 420, 427, 439. AC-27 is not red-first: 415 does not contain "stay on the owner's PC" on base. Assert instead: "Workers never run live commands" absent; "--owner-statement", "connection_failed", "scrapling install" present; "stay on the owner's PC" absent in 413-443.
3. **Text-ban guard scope (359).** `tools/data-integration/README.md:11` and `scripts/probe_tier2.py:3` already say `scrapling install`; the new guard file also holds the needles. Scan only `api/` (skip the `tooling_guards` dir), `deploy/`, `.github/workflows`, like `test_cli_guard._scan_files`; build needles by concatenation.
4. **`_dir` wording (354).** `evidence_dir()` also calls `_dir()`. Say: guard inside `approvals_dir()` and `scrape_dir()`; `_dir` and `evidence_dir()` unchanged.
5. **Catch and load (354, 353).** `_status` (`approval_cli.py:22`) also calls `approvals_dir()`: catch `PathInRepo` there too (exit 2). Non-string `owner_statement` must raise ValueError (StoreCorrupt). These files are stdlib-only (`GUARDED` in `test_approval_store_guard.py`).
6. **Read list (361).** "3,521 B" is stale: lines 350-361 measure 4,112 B. Total 31,505 B (32,979 B if 345-362), both <= 35,000. Name the lines.

## Pass

Disjoint from S-T4/S-T6; gate.py untouched; DIT-10 text complete (362).
