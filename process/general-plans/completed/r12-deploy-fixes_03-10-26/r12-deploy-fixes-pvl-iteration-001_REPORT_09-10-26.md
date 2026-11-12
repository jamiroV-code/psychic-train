---
domain: plan
iteration: 1
date: 2026-10-09
plan: r12-deploy-fixes_PLAN_09-10-26.md
gaps_found: 8
fail_count: 0
concern_count: 8
applied: 0
backlogged: 0
loop_status: validated_conditional
---

# PVL iteration 001 - r12-deploy-fixes (first-pass VALIDATE; results.tsv row 1)

Code under test: origin/main abda8e7 (`git diff 270f9ac origin/main -- api web deploy .github` is empty, so the code is identical to 270f9ac). Plan: 374 lines, 64,713 B. Validator `validate-plan-artifact.mjs`: 0 failures, 0 warnings. Fan-out strategy: sequential, one agent (signals S2 deploy/runtime surface, S6 high-risk class, S7 5+ files are present, but the review is read-only text work with no cross-talk and the plan caps the task at a 3-5 USD scale, so no team or subagents were spawned; cost guard not triggered).

## Verdict so far: CONDITIONAL (0 FAIL, 8 CONCERN). No `Gate: PASS` stamp. No goal block written.

User resolutions of 09-10-26 recorded as RESOLVED (not open): Q1 B (web-tree based stale rule; HEAD-only movement logs a note), Q2 A (first start without marker refuses, exit 4, until one rebuild), Q3 A (PC run on the PR branch, then merge), Q4 A (smoke check may use the PC's own Tailscale address), Q5 A (README M0 and Rollback name-based lines stay as operator text); the brief is confirmed; the user runs the PC verification with step-by-step help in chat. The plan body still shows all of this as OPEN: finding F8.

## Verified as correct (re-derived from real code, not from the plan)

| Claim | Result |
|---|---|
| Baseline | `UV_FROZEN=1 uv run --project api pytest api/tests/deploy -q`: 51 passed, 1 skipped (run once). `test_deploy_config_shape.py` has 24 `def test_` (counted). `command -v pwsh powershell`: nothing. Other baselines (951/2/5/0, vitest 251 in 34, tsc 0, islands 0) not re-run (earlier cycles; code unchanged since 270f9ac). |
| Test-count arithmetic | Tests 1-6 = C1 (6), 7-11 = C2 (5), 12-17 = C3 (6), total 17. pytest 951 -> 957 -> 962 -> 968; `api/tests/deploy` 51+1 skipped -> 57 -> 62 -> 68 (each +1 skipped). Red-run counts (6 failed; 5 failed + 6 pass; 6 failed + 11 pass) are consistent. |
| Exactly one existing assertion pins changed text | Grep of `confirmed_boundaries` outside `process/`: only `deploy/README.md:104-105` and `test_deploy_config_shape.py:258`. The only test file in `api/tests` that reads `.ps1` or the README is `test_deploy_config_shape.py`. The migration section is sliced `## Moving to a different PC` to the next `\n## ` (README line 201 `## Building the web app`); lines 104-105 are inside it; the new `has been removed` phrase on one line passes; `dead weight` is satisfied by the heading at README line 102. |
| Forbidden-word scan (every `.ps1`, comments included, lower-cased: `--force`, `reset --hard`, `stash`, `rebase`, `merge`, funnel words, `0.0.0.0`, stage-B job names) | No hit in the current seven deploy files except the unrelated `-Force` flags (`-Force` is not `--force`). Every backticked log string and token in plan lines 44-50 (121 strings) was scanned for those words, non-ASCII, `#`, unbalanced brackets: no hit. Worker comments are the residual risk (substrings such as "emerge" contain `merge`): folded into F7. |
| `start-web.ps1` first `-H` parse | In the current file the first `-H` is on line 16 (`'-H', $ip`), before any `Write-Host` (line 19). Planned order (D2: `$webArgs` first code line after the Tailscale wait; new `Write-Host` after it; helpers in `_common.ps1`; param line `param([switch]$DryRun, [int]$SmokeTimeoutSeconds = 0)` contains no `-H`) keeps it green. |
| Balance and ASCII tests (5, 6) | Measured on the base files: `_common.ps1` {24/24, 48/48, 21/21, `"` 14, `'` 36}, `build-web.ps1` {2/2, 10/10, 1/1, 16, 10}, `start-web.ps1` {2/2, 10/10, 2/2, 14, 18}; all ASCII, all even. `start-api.ps1` is NOT ASCII (an em dash in a comment) and is correctly not in test 5. |
| Existing `http://` forms | `build-web.ps1:17` and `start-api.ps1:22` are `http://${ip}`: test 17 and NET-scan pass on them. No existing `.ps1` has `$pid/$host/$args/$input/$error/$matches`, `Credential`, `password`, `Bearer`, `localhost`, `127.0.0.1`. |
| Stage A fact (D11) | `Invoke-StageAPull` runs only in `start-api.ps1:17-19` (`AutoPull`, not in `-DryRun`): a merge-first order would deploy unverified launchers at the next API start. D11 and Q3 A are right. |
| Root page has no fetch | `web/app/page.tsx` and `web/app/layout.tsx`: no `fetch`, `async`, `cookies`, `headers()`, `dynamic`, `revalidate`. `web/next.config.mjs` has only `reactStrictMode`; no middleware file. Smoke check on `/` does not depend on the API. `web/package.json` `build` = `pnpm build:islands && next build`, so `build-web.ps1`'s `pnpm --filter web build` clears and rebuilds `.next`. |
| Byte math (recomputed from the file with Python) | W1 20,020 / room 2,537; W2 19,367 / room 3,190; W3 19,016 / room 3,541. All three match the table exactly (no duplicate line numbers inside a range). CLAUDE.md 13,443 confirmed. Union of the three sets is 36,506 B, not 36,302 (advisory a). A drafted envelope (template 864 B + range list about 200 B + Q answers about 300 B) fits every room; the 8,000 B envelope cap is not binding. |
| Evidence pack | Scratch pack in the scratchpad dir with the plan's field lists: `validate-risk-artifacts.mjs` exits 1 with exactly one failure, `review-decision.json missing or invalid JSON object`, no warnings (G-R12-13 as written is right). The sibling `validate-evidence-pack.mjs` wants `<dir>/harness/`, all five files, and `APPROVE|REJECT`: the conflict (U9) is real and the plan's handling (authoritative = risk-artifacts, record the conflict, edit no validator) is right. `review-decision.json` is correctly the planner's. Note: the validator `JSON.parse`s without a try, so a malformed worker JSON gives a stack trace, not the single expected failure. |
| Scope commands dry-run (scratch shared clone of the repo, sample branch) | FORBIDDEN, FIXTURES, NET-scan, S-secret-scan, PS-secret-scan, ASCII-scan, `git diff --check` print nothing on a diff of the owned files (`_common.ps1`, `README.md` with `http://<ip>` and `http://${ip}` forms, the new test file, runbook, report, two harness files). Negative control: a README line with `http://100.64.1.2`, `Credential` and an em dash is caught by NET-scan, PS-secret-scan and ASCII-scan; `TOKEN = "abcdefghijkl123456"` by S-secret-scan (the gates are live, not vacuous). R12-scope printed an envelope file `r12-deploy-fixes-w2_REF_10-10-26.md`: F4. |
| Control-file rule and order (D11, D13, Phase Completion Rules) | PR branch -> vc-tester -> user reads the `deploy/` diff -> user runs the PC runbook on the branch with the planner in chat -> planner records -> user merges -> `accepted`. Matches master-planner.md section 5 item 5 and section 4(d). Worker never merges. `review-decision.json` planner-only. Correct. |
| Q1 B semantics | A merge that changes only `deploy/` leaves `HEAD:web` unchanged, so the marker built on the PR branch stays valid after the merge (note logged, no rebuild). The record template's tree compare (`git rev-parse HEAD:deploy`) is the right post-merge check. |

## Findings (numbered; each is a CONCERN that a supplement cycle can fold; none is a FAIL)

**F1 - CONCERN (high; infra) - `Get-NetTCPConnection` returns an error when nothing listens, and `_common.ps1:7` sets `$ErrorActionPreference = 'Stop'`.**
Evidence: `deploy/_common.ps1:7`; plan D2 (line 44) says "no listener: log ...nothing to stop" and, separately, "If `Get-NetTCPConnection` itself throws: fail closed, log, `exit 5`" with no `-ErrorAction` on the call; D3 (line 45) turns a throw into `DRY RUN: cannot list listeners`. In Windows PowerShell 5.1 a filtered call with no match (`-State Listen -LocalPort 3000`) writes a non-terminating ObjectNotFound error, which `Stop` turns into a terminating one. Literal implementation = every `build-web.ps1`/`start-web.ps1` run on a FREE port exits 5, and PC-5 prints `cannot list listeners` instead of `port 3000 is free`. The runbook's own PC-3 (line 155) already uses `-ErrorAction SilentlyContinue`, so the planner knew it for the runbook but not for D2. Unverifiable offline (no pwsh); the fix is cheap and safe either way.
Exact fix (D2 and D3): "`Get-WebPortListenerIds` calls `Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue` inside `try { } catch { }`; an empty or `$null` result means the port is free; only an exception (cmdlet missing, CIM failure) is 'cannot list listeners' (fail closed, exit 5; `DRY RUN: cannot list listeners: <message>` in `-ReportOnly`). The process name comes from `Get-Process -Id $listenerId -ErrorAction SilentlyContinue` and falls back to `(unknown)`. A `Stop-Process` error whose cause is 'process already gone' (re-check with `Get-Process -Id ... -ErrorAction SilentlyContinue`) counts as stopped and continues to the bounded wait." Add the token `-ErrorAction SilentlyContinue` to the assertions of test 1 (no new test, counts unchanged).

**F2 - CONCERN (medium; infra) - the stale check and marker paths are not working-directory independent.**
Evidence: `start-web.ps1:27` does `Set-Location $config.RepoRoot` only AFTER where D2 puts the stale check and the port stop (plan line 44: "stale check (D5), THEN stop, THEN start"); `build-web.ps1:30` likewise sets the location after where the stop and marker removal go. D4/D5 (lines 46-47) name `git rev-parse`, `git ls-files`, `web\.next\...` paths without `git -C` or an absolute path; `[System.IO.File]::GetLastWriteTimeUtc` resolves a relative path against the process directory, not the PowerShell location. Precedent: `_common.ps1:81` uses `git -C $Config.RepoRoot`. The PC runbook always starts with `cd <RepoRoot>`, so the PC run would not catch it; a manual run from another directory (or a task without the working directory) would answer `no build marker` or `cannot read git state` against the wrong tree.
Exact fix (D4, D5): "Every git call is `git -C $Config.RepoRoot ...`; `Get-WebBuildMarkerPath -Config $c` returns `Join-Path $c.RepoRoot 'web\.next\static\build-marker.json'` (same for `BUILD_ID`); paths from `git ls-files` are joined to `RepoRoot` before `GetLastWriteTimeUtc`; each native call sits in `try/catch` and its `$LASTEXITCODE` is checked; do not use `2>&1` on git (in 5.1 with `Stop`, stderr text becomes a terminating error)". Add `-C` and `RepoRoot` to the tokens of test 10.

**F3 - CONCERN (low-medium; infra) - D5 check 6 can refuse a fresh build because of sub-second file times.**
Evidence: plan line 47: `built_at_epoch` is integer UTC seconds, the comparison is "newest `LastWriteTime` (UTC epoch seconds)" with strict `>`; NTFS times have 100 ns resolution. `next build` rewrites tracked `web/next-env.d.ts` (and may touch `web/tsconfig.json`) in the last seconds; the marker is written right after. A file written at 100.7 s and a marker floored to 100 s gives `100.7 > 100` = false 'tracked web file newer than the build' unless both sides are floored.
Exact fix (D5 check 6): "Both values are integer epoch seconds, each obtained with `[int64][Math]::Floor(...)`; `built_at_epoch` is taken in `Write-WebBuildMarker` after the build command and before any git read; the comparison stays strict `-gt`." Add the word `Floor` to test 10's tokens.

**F4 - CONCERN (medium; test coverage / gate trap) - R12-scope prints the planner's envelope copies if they sit on the branch.**
Evidence: plan line 349 says the planner commits each envelope "on the branch or on `main`" and that "the R12-scope command ignores envelope files because they are not in the worker diff". `git diff --name-only origin/main...HEAD` (three dots) lists every commit on the branch, including the planner's. Reproduced in the scratch clone: with `r12-deploy-fixes-w2_REF_10-10-26.md` committed on the branch, the R12-scope command (plan line 294) prints that path, so G-R12-9 ("print nothing") fails for W2 and W3 for a reason the worker cannot fix (it must not delete the planner's file). Master-planner.md section 8: the envelope is sent as the first message and the file is only a record, so it can safely live on either side.
Exact fix: add `r12-deploy-fixes-w[123]_REF_[0-9-]+\.md` to the R12-scope allowlist group (plan line 294, inside the `process/general-plans/active/r12-deploy-fixes_03-10-26/(...)` alternation) AND reword line 349 to "committed by the planner on the branch or on main; the allowlist names the envelope files".

**F5 - CONCERN (medium; worker split) - the shape of `harness/verification.json` is in W3's lines only, but W1 creates it and W2 extends it.**
Evidence: checklist step 7 (line 226, W1 range 220-226) creates `harness/verification.json` "with the `commands` of steps 1-7" and step 10 (line 229, W2) extends it; the field list `{task, commands[{command, result, utc, sha}], manualChecks[...], result}` and the validator's required keys (`task`, `commands`, `manualChecks`, `result`; `validate-risk-artifacts.mjs` lines 47-49 and 64-70) sit only on line 172 (W3 range 149-172; neither W1 nor W2 reads it). W1 would invent a shape that W3 must rewrite. Also: steps 7 and 10 say "commit C2/C3 ... create verification.json ... write report ... push", so the report and JSON are uncommitted at push time; the plan says "four ordered commits".
Exact fix: (a) add the one-line shape (about 250 B) to the W1 and W2 envelopes through the "Worker envelope" paragraph (line 349, outside every range, so the table does not shift): `verification.json = {"task":"R12","commands":[{"command","result","utc","sha"}],"manualChecks":[],"result":"CONDITIONAL"}`, W1/W2 fill `commands` only; (b) state in the paragraph that report and `verification.json` are committed as a separate docs commit after the code commit and before the push, so the branch holds six commits (C1, C2, docs, C3, docs, C4). Rooms (2,537 / 3,190) hold it.

**F6 - CONCERN (medium; runbook safety and correctness) - PC runbook skeleton: one wrong count, no per-step abort advice, no global restore.**
Evidence: plan lines 149-170. (a) PC-4 (line 156) says "seven lines, each `0 errors`": `Get-ChildItem deploy\*.ps1` finds five scripts (`_common`, `build-web`, `register-tasks`, `start-api`, `start-web`; `ls deploy` at abda8e7), so the user would look for two missing lines. (b) Line 149 promises "command(s), expected output, and a Paste back line" but the user's requirement also needs rollback or abort advice, and there is none per step or overall. Destructive-looking steps and their restores: PC-3 stops both scheduled tasks (restored only at PC-15 and PC-16); PC-7/PC-11 decoy window (killed by the script, or closed by hand); PC-12 changes the timestamp of `web\app\page.tsx` (restored in effect by PC-13's rebuild); PC-14 renames `web\.next\server` (restored by the last command of the same step, no instruction if the window is closed or the step is aborted halfway). (c) PC-11 uses Ctrl+C on a server started through `pnpm.cmd`: `cmd.exe` asks "Terminate batch job (Y/N)?"; answering N or closing the window can leave `node` listening. (d) Minor: PC-2 switches the branch (line 154) before PC-3 stops the tasks (line 155); stop the tasks first.
Exact fix (runbook skeleton, line 149 and the PC rows): "five lines"; add an "If it fails / abort" line to every step; add a top block 'Abort and restore (safe at any point)': close any decoy window; `Rename-Item web\.next\server.off server` if it exists; `git switch main`; `Start-ScheduledTask mysite-web`; `Start-ScheduledTask mysite-api`; if a build was interrupted run `deploy\build-web.ps1` (main's copy, old behaviour) once; state that nothing outside `web\.next`, the branch checkout and the task states is ever changed; PC-11: 'answer Y to Terminate batch job; then list port 3000 (a leftover listener is stopped by the next start)'; PC-14: 'if you stopped here, run `Rename-Item web\.next\server.off server`, or rebuild with `build-web.ps1`'; swap PC-2 and PC-3.

**F7 - CONCERN (low-medium; test coverage / gate trap) - README added lines are inside the NET and credential scans, and the README work paragraph does not say so.**
Evidence: NET-scan and PS-secret-scan use the pathspec `-- deploy` (plan lines 300 and 303), which includes `deploy/README.md`; ASCII-scan covers every added line. Reproduced in the scratch clone (negative control above): a README line `http://100.64.1.2:3000`, the word `Credential` or an em dash fails G-R12-10/11. Plan line 147 lists only the forbidden words `0.0.0.0`, `funnel`, `port forward`, `exit node` and ASCII. The new README section naturally wants a served-URL example and a 'the marker holds no password or credential' sentence.
Exact fix (README work, line 147): "Added README lines: URLs only as `http://<ip>:...` or `http://${ip}:...`; never the words Authorization, Bearer, Credential, SecureString, password, tskey, apikey; ASCII only." Also add to hidden breaker 2 (line 108) that substrings count ("emerge", "submerge" contain `merge`).

**F8 - CONCERN (procedural) - Q1-Q5 and the brief confirmation are resolved but still shown open; the range table must be re-derived last.**
Evidence: line 11 ("Q1-Q5 below are OPEN and Q1 blocks the worker"), lines 57-67 (section title and table), line 59, D5 check 7 text (line 47: "per Q1 (default B ... option A ...)"), lines 349 and 359-361 (Resume: "get the user's answers to Q1-Q5 and the confirmation of the brief"). The user resolved all five on 09-10-26 and confirmed the brief.
Exact fix: retitle the section "Questions (RESOLVED by the user 09-10-26)" and fill a Resolution column (Q1 B, Q2 A, Q3 A, Q4 A, Q5 A; brief confirmed; user will run the PC verification with the planner's step-by-step help in chat); line 11 -> "VALIDATE in progress; registry `blocked` -> `approved` is recorded by the planner after PASS; no envelope or worker before ENTER EXECUTE MODE"; D5 check 7 -> the Q1 B behaviour as final text; Resume item 5 -> drop the question step. After all edits above, re-derive the "Envelope line ranges" table LAST (lines 47, 108 in W1/W2/W3 sets, 147 in W2, 294 in all three change bytes; line count must stay stable or the table is re-derived from `grep -n '^## \|^### '`).

## Advisories (no fold needed; for the envelopes or the diff check)

a. Plan line 14 and D1 say the union of the three sets is 36,302 B; the file gives 36,506 B (immaterial, the split conclusion is unchanged).
b. Test 2's `$deadline` plus `Start-Sleep` assertion must be made on the helper body (extract `function Stop-WebPortListener`), else it passes vacuously from `Wait-TailscaleIPv4` (`_common.ps1:55,71`).
c. Evidence-pack snippets should cite the final line numbers of the changed files, not the base lines 16-28 / 23-31.
d. The marker does not record the baked API address; a changed Tailscale IP with an unchanged `web/` tree is not detected by the guard (the README rebuild rule stays the control). Worth one follow-up backlog line, not this slice.
e. D6's unbounded `WaitForExit` is a deliberate deviation from the brief's "bounded loops" and from its review-stop rule 'cannot be bounded in time'; the plan states it (Name check row, D6). Surface it explicitly to the user at the diff check.
f. `Invoke-WebRequest` throws a `WebException` for any non-200 in 5.1: the smoke code must catch it and read `$_.Exception.Response.StatusCode` guarded (StrictMode errors on a property absent from non-web exceptions). It also honours a system proxy: the 'packet stays on the machine' statement assumes none; harmless on the home PC (B10 already uses it).
g. The 60 USD programme ceiling is not in `process/MASTER-PLAN.md` (P4 still says 45); the planner records it with the registry update.
h. The ASCII-scan covers every added line, including the W3 documents (runbook, template, reports, JSON): tell W3 explicitly (no typographic dashes or arrows).

## Layer 1 and Layer 2 summary

| Layer 1 dimension | Status |
|---|---|
| Infra fit | CONCERN (F1, F2, F3) |
| Test coverage | CONCERN (F4, F5, F7; counts, hidden breakers and evidence validator verified) |
| Breaking changes | PASS (one existing assertion, listed; 24 and 51+1 baselines confirmed; no other consumer of the changed text) |
| Security surface | PASS (kill by port only, PID <= 4 and `$PID` refused, no `-Force`, no name-based kill in scripts, no secret, non-secret marker, request to the machine's own address; advisory f) |

| Layer 2 section | Status |
|---|---|
| C1 port-scoped stop (D2, D3, tests 1-6) | CONCERN (F1) |
| C2 marker and stale guard (D4, D5, tests 7-11) | CONCERN (F2, F3) |
| C3 child process and smoke check (D6, D7, tests 12-17, README) | PASS with advisories e, f (F7 for the README lines) |
| C4 runbook, record template, evidence pack | CONCERN (F6); evidence pack PASS |
| Worker split, ranges, envelopes | CONCERN (F4, F5, F8); byte math PASS |

Totals: 0 FAIL / 8 CONCERN. Net gate: CONDITIONAL (first pass, zero fix cycles recorded: not terminal).

## What the coverage still does NOT prove (unchanged by this cycle)

Everything PowerShell at runtime: parse, port discovery, process stop, `Start-Process` exit codes, Task Scheduler interplay, Tailscale binding, `next start` serving the marker, the HTML build id, Windows file times. The 17 shape tests prove text and order only. Runtime criteria stay CONDITIONAL until the user's PC record (backlog stub `deploy-runtime-user-pc-verification_NOTE_02-10-26.md` exists). Probes U3/U4 (marker file served, build id in HTML) and U5/U7 stay PC-decided.

SUPPLEMENT REQUEST:
- Gap 1: Section decisions-locked-for-this-task | Concern: F1 Get-NetTCPConnection no-match error under global Stop; empty result must mean free port | Severity: CONCERN | Suggested addition: D2/D3 text per F1 plus the `-ErrorAction SilentlyContinue` token in test 1
- Gap 2: Section decisions-locked-for-this-task | Concern: F2 git -C and absolute marker/BUILD_ID paths; no 2>&1 on git | Severity: CONCERN | Suggested addition: D4/D5 text per F2 plus tokens in test 10
- Gap 3: Section decisions-locked-for-this-task | Concern: F3 floor both epoch values | Severity: CONCERN | Suggested addition: D5 check 6 text per F3
- Gap 4: Section validate-contract | Concern: F4 R12-scope allowlist lacks the envelope files | Severity: CONCERN | Suggested addition: add `r12-deploy-fixes-w[123]_REF_[0-9-]+\.md` to the R12-scope regex (line 294) and reword the envelope-location sentence
- Gap 5: Section worker-envelope | Concern: F5 verification.json shape and docs commits missing from W1/W2 | Severity: CONCERN | Suggested addition: one-line shape plus docs-commit rule in the Worker envelope paragraph
- Gap 6: Section the-slice-r12-rt4-three-sequential-worker-sessions-no-subagents | Concern: F6 runbook count, abort advice, restore block, Ctrl+C prompt, PC-2/PC-3 order | Severity: CONCERN | Suggested addition: runbook skeleton edits per F6
- Gap 7: Section the-slice-r12-rt4-three-sequential-worker-sessions-no-subagents | Concern: F7 README added-line scans | Severity: CONCERN | Suggested addition: README work sentence per F7
- Gap 8: Section open-questions-for-the-user | Concern: F8 Q1-Q5 and brief confirmation shown open; Resume and line 11 stale | Severity: CONCERN | Suggested addition: mark resolved per F8, then re-derive the envelope line-range table LAST

## Next step

Orchestrator: spawn vc-plan-agent (PVL-supplement mode) with the SUPPLEMENT REQUEST above, then re-spawn vc-validate-agent from V1 (cycle 2). Cheap checks suffice for cycle 2: re-run the byte math from the file, re-run the scratch scope commands, confirm F1-F8 folded, hunt for new gate traps. Expected cycle 2 verdict PASS if the folds are clean (all findings are text edits; no design change).
