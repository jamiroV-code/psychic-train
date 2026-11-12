---
domain: plan
iteration: 2
date: 2026-10-09
plan: r12-deploy-fixes_PLAN_09-10-26.md
mode: PVL-supplement (cycle 1 fold of iteration 001)
gaps_found: 8
applied: 8
loop_status: supplement_folded
---

# PVL iteration 002 - supplement fold of F1-F8 (plan-agent, PVL-supplement mode)

Start state: plan 373 lines, 64,713 B, results.tsv 2 lines. End state: plan 375 lines, 68,507 B, results.tsv 3 lines. No overlay sections: every fix is edited into the plan body. Validate Contract section and validation records untouched except repeated gate names (AC-R12-1r and U2 now cite PC-2 after the PC-2/PC-3 swap) and the R12-scope regex. No Gate: PASS stamp. MASTER-PLAN, source and deploy files untouched. Nothing committed or pushed. `validate-plan-artifact.mjs`: 0 failures, 0 warnings; no non-ASCII, no trailing whitespace.

## Where each item landed (new plan line numbers)

| Item | New plan line(s) | Edit |
|---|---|---|
| F1 | 44 (D2), test 1 at 127, test 2 at 128 | `-ErrorAction SilentlyContinue` inside try/catch, empty = free, only an exception is a failure; name via `Get-Process -Id ... -ErrorAction SilentlyContinue` else `(unknown)`; already-gone process counts as stopped; token added to test 1 |
| F2 | 46 (D4), 47 (D5), 52 (D10), test 10 at 136 | `git -C $Config.RepoRoot` in try/catch with `$LASTEXITCODE`, no `2>&1`; absolute marker and BUILD_ID paths; ls-files paths joined to RepoRoot; tokens `git -C`, `RepoRoot` |
| F3 | 46, 47 (check 6), test 10 at 136 | both epoch values floored (`[int64][Math]::Floor`), strict `-gt`, marker time taken after the build before any git read; token `Floor` |
| F4 | 296 (R12-scope regex now `w[123]_(REPORT\|REF)_`), 351 | envelope files allowlisted; sentence reworded ("the R12-scope allowlist names the envelope files") |
| F5 | 351 (Worker envelope paragraph, outside every range), 12 and 43 (commit wording), 228, 231, 234 | one-line `verification.json` shape; docs-commit rule; branch order C1, C2, docs, C3, docs, C4, docs (seven commits: W3's report also needs a docs commit) |
| F6 | 149 (header, Abort and restore block, ASCII rule), 154-155 (PC-2 and PC-3 swapped), 156 (five lines), 163 (PC-11 batch-job prompt, PC-2 command), 170 (per-step abort lines, incl. PC-14 restore) | as the finding asked; AC-R12-1r and U2 renumbered PC-3 to PC-2 |
| F7 | 147 (README added-line rules), 108 (substrings count) | NET/credential/ASCII scans cover README via the `-- deploy` pathspec |
| F8 | 11, 57-67 (Questions RESOLVED with a Resolution column), 47 (check 7 final text), 347, 351, 357-363 (Resume), 365-375 (table, derived last) | no OPEN wording left (`grep OPEN` empty) |
| a | 14, 43, 375 | union now 39,477 B (the sets changed, so the old 36,302/36,506 figure no longer applies) |
| b | 128 | test 2 asserts on the extracted body of `function Stop-WebPortListener` |
| c | 174 | evidence-pack snippets cite FINAL line numbers on the branch head |
| d | 347 | follow-up backlog line (baked API address not in the marker); not folded into D4 because it needs a config key |
| e | 48 (D6), 214 (P-R12-1 row) | deliberate unbounded `WaitForExit` shown to the user at the diff check |
| f | 49 (D7) | WebException caught, `Response` checked before `StatusCode` (StrictMode), system-proxy note |
| g | 347 | 60 USD ceiling missing from MASTER-PLAN noted for the planner's UPDATE PROCESS; not edited here |
| h | 149 | ASCII rule for every W3 document and JSON |

## Envelope table (re-derived LAST from the saved file, method verified on the old file: 20,020)

| Session | Plan bytes | Room (36,000 - 13,443 - plan bytes) |
|---|---|---|
| W1 | 20,405 | 2,152 |
| W2 | 20,336 | 2,221 |
| W3 | 20,546 | 2,011 |

Union of the three sets 39,477 B. The fold added about 3.9 KB to the file, mostly inside ranges, so to keep every room above the draft envelope (about 1.8-2.0 KB with the verification.json shape and commit rule) the sets drop section headings, the goal line (101), the D8 line for W1 (exit codes are in D2/D4/D5), the counts line for W1, the Forbidden line for W3, G-R12-12 and the PC-* row for W3, and the command-block heading. Content-bearing lines are unchanged. Line shifts: only the abort-lines insertion at 170-171 moves later lines (+2).

## Notes for PVL cycle 2

Cheap checks: re-run the byte math from the file (script method: sum of line UTF-8 length + 1 over the listed lines), confirm F1-F8 text, re-run the scratch scope commands (R12-scope now has the envelope pattern). W3's room (2,011 B) is the tightest; the envelope text, not the ranges, is trimmed if it does not fit. The seven-commit branch order is stated once in the Worker envelope paragraph (351).
