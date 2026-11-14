---
domain: plan
iteration: 4
date: 2026-10-09
plan: r12-deploy-fixes_PLAN_09-10-26.md
gaps_found: 1
fail_count: 0
concern_count: 1
applied: 1
backlogged: 0
loop_status: supplement_folded
---

# PVL iteration 004 - supplement cycle 2 (PVL-supplement of iteration 003: N1 and A1-A8)

Status: edits folded; results below.

## Edit plan (all in place, no overlay sections, no new lines inside ranges)

| Item | Plan location | Edit |
|---|---|---|
| N1 | Gate convention 8 (line 78) | text per the report: `--check origin/main...HEAD`, scans read the committed diff, run AFTER the commit, note the SHA |
| N1 | G-R12-11 (line 281) | `ASCII-scan` and `git diff --check origin/main...HEAD` |
| N1 | command block heading (line 286) | says: run after the commit they cover |
| N1 | checklist steps 4, 7, 10, 12, 13 (lines 225, 228, 231, 233, 234) | gates before the commit, scans after it, rescan G-R12-9 and G-R12-11 after each docs commit and before the push |
| A1 | line 375 text and range table | drop line 43 from W1, line 45 from W3; Q1/Q2 answers about 330 B; table re-derived LAST |
| A2 | Blast Radius (line 196) | real touch count |
| A3 | runbook lines 149, 170 | rebuild before the two Start-ScheduledTask calls; PC-12 abort says run build-web.ps1 |
| A4 | step 10 (line 231) | unconditional `pnpm install --frozen-lockfile` |
| A5 | D4 (line 46) and test 8 (line 134) | Test-Path -LiteralPath guard in Remove-WebBuildMarker, test token |
| A6 | adversarial list (line 174) | add silent listing failure scenario |
| A7 | D11 title (line 53), Resume lines 360-363 | resolved wording, refreshed state |
| A8 | none | the code wins (step 11); no change |

## Results (plan now 375 lines, 70,463 B; line count unchanged, so all earlier line numbers hold)

| Item | New plan line |
|---|---|
| N1 | 78 (convention 8), 281 (G-R12-11), 286 (command block heading says run AFTER the commit), steps 4/7/10/12/13 at 225/228/231/233/234 (gates before the commit, scans after, rescan G-R12-9 and G-R12-11 after each docs commit and before the push), 351 (envelope common fields) |
| A1 | 375 text and 371-373 table, re-derived last: W1 20,024 / room 2,533 (slack 376 vs the 2,157 B draft); W2 19,168 / 3,389 (D5 line 47 dropped, it is C2 code; slack about 1,590); W3 20,605 / 1,952 (slack 238 vs 1,714); union 39,617; D1 line 43 out of W1, D3 line 45 out of W3; Q1/Q2 answers stated as about 330 B |
| A2 | 196 (15 touches, 18 with envelopes) |
| A3 | 149 (rebuild first, then the two Start-ScheduledTask), 170 (PC-12 abort: run build-web.ps1) |
| A4 | 231 (unconditional pnpm install --frozen-lockfile) |
| A5 | 46 (Test-Path -LiteralPath guard), 134 (test 8 token) |
| A6 | 174 (silent listing failure scenario) |
| A7 | 53 (D11 resolved), 11 (status), 360-363 (Resume refreshed) |
| A8 | no change (code wins, step 11) |

Also: line 361 says "no PASS stamp" (not the literal gate string, so the mechanical `grep -c 'Gate: PASS'` stays 0). Validator: 0 failures, 0 warnings. ASCII and trailing whitespace clean. results.tsv row 4 appended (5 lines). Nothing committed.
