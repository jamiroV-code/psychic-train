---
domain: plan
iteration: 2
date: 2026-10-14
plan: data-integration-tooling_PLAN_14-10-26.md
mode: VALIDATE re-validation (PVL cycle 2, after fix cycle 1)
gaps_found: 8
fail_count: 0
concern_count: 0
applied: 8
loop_status: validated_pass
---

# PVL iteration 002 - data-integration-tooling (results.tsv row 2)

Code under test: origin/main `20b65a2` plus the revised plan (commit `bcfcf87`). Plan read: 284 lines, 40,840 B before the contract. `validate-plan-artifact.mjs`: 0 failures, 1 warning (no clear closing instruction; advisory). Files written by this pass: the plan's `## Validate contract` section (plan body untouched, headings still at the same lines), this report, one row in `results.tsv`.

## Verdict: PASS (0 FAIL, 0 unresolved CONCERN, 8 advisories carried as binding envelope additions E1-E8 in the contract)

Why advisories are carried in the contract and not sent back: every one is a one-sentence worker instruction; editing the plan body shifts the slice line ranges and byte hints that iteration 1 F3 made correct, and would force a third round for no new safety. The contract is the binding artefact; the planner puts E1-E8 into the matching worker envelopes.

## Step 1: prior findings

| ID | Status | Evidence (revised plan) |
|---|---|---|
| F1 | RESOLVED | S-T0 `Owned` = SPEC only (l.79); gate = diff lists the SPEC (l.82); planner-side records l.185-187 (P9 umbrella row, D-15 with DIT-1..9, real path `process/context/decisions.md`); gate convention 6 (l.65) and l.74 forbid worker edits. D-15 free (ids D-1..D-14), P9 free (P1-P7 used). |
| F2 | RESOLVED | no `process/decisions` string left; l.187 Index row + D-15; DIT-n naming; no bare D1-D9 ids remain. |
| F3 | RESOLVED | measured below; headings match the slice index; hint arithmetic holds. |
| F4 | RESOLVED (1 advisory E1) | l.48, l.93: duckdb, src layout, hatchling `packages=["src/data_integration"]`, `_repo_root()`, wrapper under `src/`. Pins in `api/uv.lock`: pandas 3.0.6, pyarrow 25.0.1, duckdb 1.5.5. Scratch `uv lock` with those exact pins and `scrapling[fetchers]==0.4.15`: 36 packages resolved. No test enforces pin parity (E1). |
| F5 | RESOLVED | simulated on base: api deps = ccxt, duckdb, fastapi, httpx, numpy, pandas, pandas-ta-classic, pyarrow, pydantic, statsmodels, uvicorn; lock 64 packages; none of scrapling/playwright/patchright/rea-agents; hatch packages = analytics, data, models, routers; workflows contain no `tools/data-integration` or `data_integration`; `git ls-files` has no approval file; ci.yml:9 only has the word Playwright in a comment (exact-name scan does not see it). |
| F6 | RESOLVED | l.94, l.106, l.119: pass bound to host and pages, `permits(url)`, redirect and robots per hop, isinstance, import-boundary test in S-T1. |
| F7 | RESOLVED | l.106: regex `^[a-z0-9][a-z0-9_-]{0,63}$` before any path; TTY confirmation on `add`; UTC ISO `Z`; `bad_clock`. |
| F8 | RESOLVED | l.142 AC-6 in S-T4; l.143 step 3 unmarked stub-navigator test; l.119 robots fetch needs a pass and fails closed. |
| F9 | RESOLVED (E5) | l.155: frozenset, flag allow-list, regex, forbidden characters, `shell=False`, `npx.cmd`, evidence outside repo; l.70 documents the npx exception. |
| F10 | RESOLVED | `all-context.md` Task Routing Table (lines 70-93) is outside the GENERATED markers (53-68), hand-written; l.166-170 cap 3,500 B, validators in S-T5b; baseline: planner_fixed 53,040 of 56,000 (headroom 2,960), rc=1 pre-existing (current-state.md 11,465 B). Both validators exit 0 on base. |
| F11 | RESOLVED | l.93 isolated cache fixture and real-data guard; l.131 refuse when key holds data. `BTC-HIST` does not collide: `ohlcv_path` = `ohlcv/<SYMBOL upper>/<tf>.parquet`, adapter keys are bare tickers; the only directory enumerator (`api/scripts/check_weekly_anchor.py:51`, manual) prints "no 1w cache yet" for it. |
| F12 | RESOLVED | l.61: `UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env` tested under the hook (allowed); hook matches Write/Edit by path only. |
| F13 | RESOLVED | arithmetic below. |
| F14 | RESOLVED | l.65/158 worker-only diff gates; l.94 fetch_tier* in marker audit; l.117 fixture owner; l.177 REF types; l.82 grep rule; l.91 script owned. |

## Step 3 measured worker read bytes (sed -n | wc -c; CLAUDE.md 13,443; envelope 4,000; Common 6,060)

| Slice | Slice B | Files B | Total | Note |
|---|---|---|---|---|
| S-T0 | 1,151 | SPEC 5,917 | 30,571 | plan hint says 30,594 |
| S-T1 | 4,012 | cache.py 1-30 1,106; .gitignore 1,746 | 30,367 | hint 30,621 (uses 2,000 for .gitignore) |
| S-T2 | 2,808 | 3,900 E; layout 106-142 1,125 | 31,336 E | |
| S-T3a | 2,261 | 2,400 E; 1,500 E | 29,664 E | |
| S-T3b | 2,468 | 3,900 E; cache 118-131+158-187 1,789 | 31,660 E | max |
| S-T4 | 2,405 | 4,500 E; 900 E | 31,308 E | |
| S-T5a | 3,559 | 2,400 E | 29,462 E | min |
| S-T5b | 1,735 | all-data-sources 1-12+45-66 2,282; router rows 2,116 | 29,636 | hint 31,238 |
| S-T6 | 1,721 | 1,500 E; 3,500 E; cache 1-30 1,106 | 31,330 E | |

Range 29.5-31.7 KB confirmed (cap 36,000). Even with an 8,000 B envelope the maximum is 35,660 B. Slice-index ranges match all headings (40, 76, 88, 101, 114, 126, 138, 150, 163, 174, 185). Router part of `all-context.md` 5,831 B (cap 7,000).

## Step 2 fresh pass

**AC coverage:** 23 ACs, 0 orphans. CI-run (API job): 2, 4, 15, 21. Tooling venv (EVL/tester): 1, 3, 6-14, 19, 22, 23. Sandbox/validators: 5, 18. Owner: 16, 17, 20. Every AC has a slice (l.92, 105, 118, 130, 142, 154, 167, 178) and a row in Verification Evidence.

**Hidden breaks:** none. `api/tests/__init__.py` exists, so `tooling_guards/__init__.py` is right; `test_lane_scope.py` is branch-gated (skips); `test_no_verdict_symbols.py` walks api/web and skips the environment folder; ci.yml has `paths-ignore` only for `api/data/cache/**`; no test enumerates top-level folders. Full API suite on base measured: 1143 passed, 1 skipped, 5 deselected (307 s); git tree clean afterwards.

**Cost:** lows 0.8+3.0+2.5+2.5+3.0+4.0+3.5+1.5+2.5 = 23.3; highs 1.5+5.0+4.0+4.0+5.0+7.0+6.0+3.0+5.0 = 40.5; midpoint 31.9; per-slice figures match each slice section. Waves 1+2 = 8.8-14.5, above the 13.9 left at the top end. Risk of passing the 7 USD ask point: S-T3b (high = 7.0), S-T4 (6.0); the rest <= 5.0. The plan says plainly that the owner must set a new ceiling.

**Concurrency / order:** W1 S-T0 (SPEC) + S-T1; W2 S-T2 + S-T5a; W3 S-T3a + S-T3b; W4 S-T4 + S-T5b; W5 S-T6. Owned globs are disjoint inside every wave (SPEC | tools/pyproject, src core, scripts, api guards, .gitignore || approvals/gate/approval_cli + 3 tests + store guard | rea/ + 2 tests + rea guard || tier1/robots/politeness/logging/response_cache + fixture server tests | parse..pipeline + fixtures || tier2/3 + js_page + probes + README append | process/context docs). Cross-wave: README.md (S-T1 then S-T4 append) and tests/fixtures (S-T3b then js_page) are sequential. Dependencies all met by the preceding waves; max 2 workers (limit is 3).

**Stated plainly (checked):** tiers 2/3 not proven live (l.202); scrapling tooling tests outside CI (l.202, l.191, risks l.221); Windows and Python 3.12 unverified (l.202); environment 676 MB vs 581 MB, not lighter (l.202); spend ceiling decision, 86.13 of 100, about 13.9 left (l.14, l.36, l.226). SPEC consistency: `setup` appears only as rejected (l.14, 44, 53, 81-82, 157, 159, 196); no old D1-D9 ids; no worker-owned registry file; Farside untouched (l.168, 192; refresh at `components.py:484` via `regime.py:57` verified).

**Security review:** pass is host- and page-bound with redirect and robots checks, source names validated before any path, TTY on add, UTC expiry, fail-closed robots, exact wrapper allow-list with flag allow-list, `shell=False`, ignore-scripts, evidence outside the repo, redaction. Residuals (accepted, documented in the contract): the private token is convention; approval records are plain files any local process can write (E6); `npx -y` downloads a pinned but unhashed package (dev/tester-only exception).

## Advisories (non-blocking, carried as E1-E8 in the contract)

| ID | Severity | Item | Wanted |
|---|---|---|---|
| E1 | minor | no check that pandas/pyarrow/duckdb pins equal `api/uv.lock`; tree scans may walk `api/.venv` | parity assertion in test_skeleton; scans skip the env folder |
| E2 | minor | `permits()` tests cover host only; invalid source outcome (Refused vs exception) unstated | add userinfo/scheme/port cases; bad name gives Refused |
| E3 | minor | S-T3b hint omits `cache.py` line 36 (`OHLCV_COLUMNS`) | read it (about 90 B) |
| E4 | minor | marker audit would force a deselecting marker on tier 2/3 gating tests that import `fetch_tier*` | use `fixture_server` so they run by default |
| E5 | minor | wrapper regex rejects backslash, so a Windows drive path fails | test and convert; owner probe |
| E6 | minor | S-T5b hint lacks evidence template, approval field list, wrapper usage (still < 36,000 B); approval-file forgeability not in Known limits | add reads; one docs sentence |
| E7 | minor | S-T6 step 1 (REA via wrapper on public pages) conflicts with the "no live network" rule | worker never runs npx/live REA; ASSUMED or needs_input |
| E8 | minor | P9 row timed after S-T0 merge but a registry row is needed at dispatch; trust-boundary class suggests a risk evidence pack | row at dispatch; pack in `harness/` at EVL |

Not verified by this pass: REA 6.4.0 command names on a live `npx` call (no network call made, by the plan's own rule); Windows behaviour; browser tests in the cloud.
