---
domain: plan
iteration: 3
date: 2026-10-09
plan: r12-deploy-fixes_PLAN_09-10-26.md
gaps_found: 1
fail_count: 0
concern_count: 1
applied: 0
backlogged: 0
loop_status: validated_conditional
---

# PVL iteration 003 - r12-deploy-fixes (re-VALIDATE from V1 after supplement cycle 1; results.tsv row 3)

Code under test: origin/main abda8e7 (`git diff origin/main --stat -- deploy api/tests/deploy` is empty: the working tree equals origin/main for those paths). Plan: 375 lines, 68,507 B (validator counts 376). `validate-plan-artifact.mjs`: 0 failures, 0 warnings. Strategy: sequential, one agent, read-only text work (no cross-talk, cost guard not triggered).

## Verdict: CONDITIONAL (0 FAIL, 1 CONCERN, 8 advisories). No `Gate: PASS` stamp. No goal block written.

F1-F8 and advisories a-h are folded and verified against the real files (table below). Hunting for new traps found one real gate trap (N1, blocking by the PASS rule, one-paragraph fix). Everything else is advisory.

## New finding

**N1 - CONCERN (gate trap; test coverage) - the scope, secret, network and ASCII scans read the COMMITTED diff, but the checklist runs them BEFORE the commit they are meant to cover, so every one of them is vacuous at that point.**

Evidence: command block lines 290-308 all use `git diff ... origin/main...HEAD` (three dots = merge-base to HEAD; the working tree and the index are ignored). Checklist order: line 225 (step 4) "G-R12-1 ..., G-R12-3 (57 passed, 1 skipped), scans G-R12-9..11; commit C1"; line 228 (step 7) "... scans; commit C2"; line 231 (step 10) "... scans G-R12-9..12; commit C3"; line 233 (step 12) "gates G-R12-9 ..., G-R12-13; commit C4". Line 78 and G-R12-11 (line 281) also say plain `git diff --check`, which sees only unstaged changes (empty after `git add`). Reproduced in a scratch repo (scratchpad `t/`): a new file containing an em dash printed nothing from `git diff main...HEAD | grep -nP '^\+[^+].*[^\x00-\x7F]'` while untracked, nothing after `git add`, and the hit only after `git commit`. Consequence: C1's, C2's, C3's and C4's added lines are never scanned by their own session; the README added lines of C3 (the F7 rule: NET, credential, ASCII scans) and the whole W3 runbook (the ASCII rule of advisory h) can carry an em dash or a `http://100.x` and the worker report would still say "G-R12-10/11 print nothing". Only the independent vc-tester (EVL) would catch it, after the worker reported a false green.
Exact fix (plan edits; then re-derive the envelope range table, see "Byte effect"):
1. Line 78 becomes: `8. git diff --check origin/main...HEAD exits 0 and the added lines are ASCII (commands below). Scans G-R12-9..12 read the COMMITTED diff (origin/main...HEAD; an uncommitted file is invisible to them): run them AFTER the commit they cover and note the SHA; on a hit fix in a new commit and rescan. LF line endings.` (keep the backticks of the original).
2. Line 281 (G-R12-11): `ASCII-scan` and `git diff --check origin/main...HEAD`.
3. Step 4 (line 225): `...G-R12-3 (57 passed, 1 skipped); commit C1; then scans G-R12-9..12 on the committed head.` Step 7 (line 228): `...G-R12-3 (62 passed, 1 skipped); commit C2; then scans G-R12-9..12; create harness/verification.json ...; commit both as a docs commit; rescan G-R12-9 and G-R12-11; push; reply DONE (no PR).` Step 10 (line 231): the pytest/vitest/tsc/islands/e2e gates stay before `commit C3`; add `then scans G-R12-9..12` after the commit and `rescan G-R12-9 and G-R12-11` after the docs commit. Step 12 (line 233): `commit C4; then gates G-R12-9, G-R12-10, G-R12-11 on the committed head; G-R12-13 any time`. Step 13 (line 234): add `rescan G-R12-9..11 after the docs commit, before the push and the PR`.

## Advisories (non-blocking; fold in the same supplement pass)

| # | Where | Note and fix |
|---|---|---|
| A1 | envelope fit (lines 349-351, 365-375) | The byte math reproduces exactly (below). Honest fit test with real drafts: W3 envelope 1,714 B in room 2,011 (fits, 297 B slack). W1 is the tight one, not W3: a full W1 draft with the Q1/Q2 answers copied verbatim, the stop list, the commit rule and the `verification.json` shape is 2,157 B in room 2,152 (5 B over); citing plan lines 103-104 instead of repeating Owned/Forbidden gives 1,900 B (252 B slack). The N1 fix adds about 200-300 B to lines inside all three sets, so after it W1 slack is about 0-50 B. Reclaim when re-deriving: drop line 43 (D1, 888 B) from W1's set (the envelope states the session and the checklist the commits) and line 45 (D3, 661 B) from W3's set (PC-5 in the skeleton already carries the dry-run strings). State in line 375 that the W1 estimate carries the Q1/Q2 answers (about 330 B, not 150 B). |
| A2 | Blast Radius, line 196 | "plus three task-folder documents ... (13 touches)" is a leftover of the single-worker design: documents are now runbook, record template and three reports (5), so the count is 6 + 5 + 4 = 15 (18 with the three planner envelope files). Nothing gates on it. |
| A3 | runbook skeleton, line 149 and 170 | Abort-and-restore order: `Start-ScheduledTask mysite-web` comes before "if a build was interrupted run deploy\build-web.ps1 from main". Starting the old launcher on a half-built or rebuilding output makes it exit non-zero and Task Scheduler burns its 3 retries. Put the interrupted-build rebuild BEFORE the two `Start-ScheduledTask` calls. Also add to the PC-12 abort text: after the page.tsx touch, run `deploy\build-web.ps1` (the touched file makes any later start on the branch refuse with exit 4). |
| A4 | step 10, line 231 | "first `cd web && pnpm install --frozen-lockfile` if `web/node_modules` is absent": the worker cannot test that (Gate convention 6, the scout hook blocks commands naming `node_modules`). Say: run `cd web && pnpm install --frozen-lockfile` unconditionally (idempotent). |
| A5 | D4, line 46 | `Remove-WebBuildMarker` on a missing file throws under the global `$ErrorActionPreference = 'Stop'` (same class as F1) and PC-8 is a no-marker first build. Add: "guard with `Test-Path -LiteralPath` (no-op when absent)". PC-8 would catch it, but it costs the user a build cycle. |
| A6 | D2, line 44 | `-ErrorAction SilentlyContinue` also swallows a non-terminating CIM failure, so "cannot list listeners" fires only for a thrown exception and a silent listing failure reads as "port free" (fail open). Acceptable (the smoke check's `HasExited` / EADDRINUSE path exits 6), but add the scenario "listing fails silently" to the adversarial list (line 174). |
| A7 | wording | D11 title still says "(recommended, Q3)" (line 53); Q3 is resolved A. Resume lines 360-363 still say "PVL cycle 2 not yet run" and "no goal block was written": planner-owned, refresh after the PASS stamp. |
| A8 | W3 set | W3's set omits D4 (line 46), which holds the log string `Build marker written: ...`; the code wins by the checklist rule (step 11) and PC-8 line 160 carries the string, so no change needed. |

## Verified (re-derived from the real files at origin/main, not from the iteration-002 report)

| Item | Result |
|---|---|
| F1 | Plan line 44: `Get-NetTCPConnection ... -ErrorAction SilentlyContinue` inside try/catch, empty = free, only an exception is a failure; name via `Get-Process -Id ... -ErrorAction SilentlyContinue` else `(unknown)`; already-gone counts as stopped (`_common.ps1:7` sets Stop: the free-port path no longer exits 5). Test 1 (line 127) carries the token. D3 (line 45) keeps `cannot list listeners` for `-ReportOnly`. |
| F2 | Line 46: `git -C $Config.RepoRoot`, absolute marker and `BUILD_ID` paths, `try/catch` plus `$LASTEXITCODE`, no `2>&1` on git; line 47 joins ls-files paths to RepoRoot. `start-web.ps1:27` Set-Location sits after the planned stale check, so absolute paths are needed and present. Test 10 tokens `git -C`, `RepoRoot`. Existing precedent `_common.ps1:81` uses `git -C`. |
| F3 | Line 47 check 6: both sides `[int64][Math]::Floor(...)`, strict `-gt`; line 46: `built_at_epoch` taken after the build before any git read; test 10 token `Floor`. |
| F4 | Line 296 regex dry-run (scratch lists): all 18 planned paths (6 code/doc/test files, w1-w3 REPORT and REF incl. other dates, runbook, template, 4 harness JSON) print nothing; 13 stray paths all print (deploy/start-api.ps1, register-tasks.ps1, config.example.psd1, root README.md, review-decision.json, the PLAN, results.tsv, the PC record REPORT, w4 REF, w1 NOTE, a `.md.bak` suffix, web/app/page.tsx, conftest.py). Line 351 wording "the R12-scope allowlist names the envelope files" present. |
| F5 | Line 351 carries the `verification.json` shape (validator keys `task`, `commands`, `manualChecks`, `result`), the docs-commit rule and the branch order C1, C2, docs, C3, docs, C4, docs = seven commits; lines 12, 43 say "commits C1-C4 plus docs commits". Scratch pack with the plan's field lists: `validate-risk-artifacts.mjs` exit 1 with exactly the one expected failure `review-decision.json missing or invalid JSON object`, no warnings. |
| F6 | Line 156 PC-4: five lines (`deploy/` holds exactly 5 `.ps1`: `_common`, `build-web`, `register-tasks`, `start-api`, `start-web`; README B5 parses `deploy\*.ps1`). Line 149 Abort-and-restore block; line 170 per-step abort lines incl. PC-14 restore; line 163 PC-11 `Terminate batch job (Y/N)?`; PC-2 = stop tasks plus list port, PC-3 = fetch/switch. Reference sweep of every `PC-n` in the file: AC-R12-1r (255), U2 (324), lines 163/170 point at PC-2 as the listing command; no dangling PC-3 reference. |
| F7 | Line 147 README added-line rules present (URLs `http://<ip>` or `http://${ip}`, banned words, ASCII). Existing README has no `Credential/password/Authorization/Bearer` and its `http://` forms are `${ip}` only; README keeps its own em dashes on untouched lines (the ASCII scan reads added lines only). |
| F8 | Lines 57-67 Questions RESOLVED with a Resolution column; `grep -in open` leaves only unrelated uses (lines 77, 83, 234, 238, 345 "Open gaps"); stale wording only in the D11 title (A7). Byte math recomputed with Python from the saved file: W1 20,405 / room 2,152; W2 20,336 / 2,221; W3 20,546 / 2,011; union 39,477; no duplicate lines inside a range; CLAUDE.md 13,443 B (wc). Heading line numbers re-derived (`grep -n '^## \|^### '`): every range edge lands on the intended line (e.g. 222-228 W1 checklist, 229-231 W2, 232-234 W3, 269-273, 279-283, 288-309, 313). |
| Test arithmetic | 17 rows in the table (6 C1, 5 C2, 6 C3); pytest 951 -> 957 -> 962 -> 968; deploy dir 51+1 skipped -> 57 -> 62 -> 68 (+1 skipped). Baseline re-run once: `UV_FROZEN=1 uv run --project api pytest api/tests/deploy -q` = 51 passed, 1 skipped; `test_deploy_config_shape.py` has 24 `def test_`. Red-run counts (6 failed; 5 failed + 6 pass; 6 failed + 11 pass) consistent. |
| Forbidden words | Every backticked string and log line in plan lines 44-50, 52, 142, 147 scanned for `merge`, `stash`, `rebase`, `--force`, `reset --hard`, funnel words, `0.0.0.0`, the stage-B job names: no hit (the only hit is the README-rule meta text on line 147, which is plan prose, not script text). No non-ASCII and no trailing whitespace in the plan. |
| First `-H` parse | `test_start_web_uses_next_start_not_dev_and_binds_variable` takes the first `-H` in comment-stripped code; the planned `param([switch]$DryRun, [int]$SmokeTimeoutSeconds = 0)` has none, `$webArgs` stays the first code line after the Tailscale wait (D10, hidden breaker 1); `Write-Host` (contains `-H`) is confined to after it. |
| Existing assertions | Only `test_readme_migration_says_legs_cache_is_not_needed` pins changed text (README 104-105; grep of `confirmed_boundaries` confirms the only other occurrences are unrelated API fields). New phrase `has been removed` must sit on one line: stated. Migration slice ends at `## Building the web app` (README 201); the new section goes after it. M0 (README 155) and Rollback (269) name-based lines unchanged (Q5). |
| Contract tables | AC rows, gates, test numbers, PC numbers and the Unverified-facts owners agree with each other (AC-R12-7 -> tests 3, 4, 11, 15; AC-R12-4 -> 5, 6, 13, 17; U1 -> PC-4; U10 -> PC-13/PC-10). No contradiction introduced by the supplement. |
| Other traps hunted | Cross-session scans: R12-scope/FORBIDDEN/FIXTURES read all sessions' files by design and now allow the envelope files; the evidence validator runs only in W3; no gate scans a file a later session alone creates (apart from N1's ordering). Unbounded loops: Stop wait 10 s, smoke poll deadline, `-SmokeTimeoutSeconds` 5..600; the one deliberate unbounded `WaitForExit` is shown at P-R12-1. Kill paths: by port only, ids 4 and `$PID` protected, no `-Name`/`taskkill`/`-Force`. Restore paths exist for PC-2/3 (block), PC-7 (close decoy), PC-12 (PC-13 rebuild), PC-14 (rename back), PC-15/16 (block); ordering nit in A3. |

## Test coverage summary (V3 sections)

Layer 1: Infra fit PASS (paths, ports, 5.1 rules, Set-Location ordering); Test coverage CONCERN (N1); Breaking changes PASS (new file `/_next/static/build-marker.json` is non-secret, exit codes and one new parameter documented); Security surface PASS (no auth/secret; kill is port-scoped with protected PIDs; local trust boundary stated). Layer 2: sections C1, C2, C3, C4 PASS on mechanical feasibility and conflicts; highest-risk edit remains C3's child-process restructure (revertable alone, PC-14/PC-15). Net gate: CONDITIONAL (1 CONCERN). Known-Gap: none silent; runtime behaviours stay Hybrid (user PC) with the backlog stub as residual.

## Next step

Supplement cycle 2 (plan-agent, PVL-supplement mode): fold N1 (and A1-A7 where cheap), re-derive the envelope range table LAST, re-run `validate-plan-artifact.mjs`, then re-spawn VALIDATE from V1 (cheap checks: the N1 text, the byte math, a scratch run of the scans before/after a commit).
