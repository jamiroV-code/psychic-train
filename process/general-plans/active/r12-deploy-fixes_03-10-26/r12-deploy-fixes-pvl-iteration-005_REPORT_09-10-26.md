---
domain: plan
iteration: 5
date: 2026-10-09
plan: r12-deploy-fixes_PLAN_09-10-26.md
gaps_found: 0
fail_count: 0
concern_count: 0
applied: 0
backlogged: 0
loop_status: validated_pass
---

# PVL iteration 005 - r12-deploy-fixes (re-VALIDATE from V1 after supplement cycle 2; results.tsv row 5)

Code under test: origin/main abda8e7 (`git diff origin/main --stat -- deploy api/tests/deploy` empty). Plan before the stamp: 375 lines, 70,463 B (the plan agent's figure reproduced; `wc` 375 lines, validator counts 376). `validate-plan-artifact.mjs`: 0 failures, 0 warnings (run in-session). Strategy: sequential, one agent, read-only text work (cost guard not triggered).

## Verdict: PASS (0 FAIL, 0 CONCERN, 5 advisories). Gate stamped once; Autonomous Goal Block written (BRANCH A: no umbrella plan with a Stable Program Goal for R12).

## Checks re-run by this agent (nothing taken from the plan agent's report)

| Item | Result |
|---|---|
| N1 order, line 78 (convention 8) | Text now: `git diff --check origin/main...HEAD`; scans G-R12-9..12 read the COMMITTED diff; run AFTER the commit they cover; note the SHA; on a hit fix in a new commit and rescan. |
| N1 G-R12-11 (line 281) | `ASCII-scan` and `git diff --check origin/main...HEAD`. |
| N1 command-block heading (line 286) | "run from the repo root AFTER the commit they cover: they read origin/main...HEAD". |
| N1 checklist order | Step 4 (line 225): pytest gates, commit C1, THEN scans G-R12-9..12 on the committed head. Step 7 (228): gates, commit C2, THEN scans; docs commit; rescan G-R12-9 and G-R12-11; push. Step 10 (231): all pytest/vitest/tsc/islands/e2e gates, commit C3, THEN scans; docs commit; rescan G-R12-9 and G-R12-11; push. Step 12 (233): G-R12-13 (reads the working tree, any time), commit C4, THEN G-R12-9, 10, 11. Step 13 (234): docs commit, rescan G-R12-9..11 before the push and the PR. Every scan now follows the commit it covers. |
| N1 reproduction (scratch repo, scratchpad `t5/`) | A README line with an em dash and `http://100.1.2.3:3000`: ASCII-scan and NET-scan print NOTHING while the change is unstaged and still nothing after `git add`; both print the hit after `git commit` (`git diff --check` exit 0 on that content). So the old order was vacuous and the new order is the only one that sees the lines. |
| A1 byte math (from the saved file, exact line numbers, Python over `split(b'\n')`) | W1 20,024 / room 2,533; W2 19,168 / 3,389; W3 20,605 / 1,952; union 39,617; no duplicate line inside any range; max line 313 (W1, W2) and 309 (W3); `wc -c CLAUDE.md` 13,443. All match the table at lines 371-373. W3 draft envelope 1,714 B < 1,952 (slack 238); W1 draft 2,157 B < 2,533 (slack 376). |
| A1 range edges | Printed every edge line: 44 D2, 47 D5 (W1 only), 48-50 D6-D8, 52 D10, 71-74 and 76-79 conventions (75 = convention 5, W2 only), 103-104 Owned/Forbidden, 106-113 hidden breakers, 115-121 existing-test table, 123-137 tests header to test 11, 138-143 tests 12-17, 145 counts, 147 README work, 149-174 runbook to evidence pack, 222-228 / 229-231 / 232-234 checklist per session, 250-253 legend and table header, 258/261 AC rows, 269-282 gates (283 = G-R12-13, W3 only), 288-309 fenced command block, 313 Failing stubs paragraph. Line count unchanged by supplement cycle 2 (375), so no edit moved text across a boundary. |
| A1 dropping D5 (line 47, 1,449 B) from W2 | Loses nothing W2 needs to WRITE: D5 is C2 code already on the branch; W2 only keeps the call order (D2 states it: stale check, then stop, then start), writes the README section (tokens in test 16: task commands, `build-marker.json`, `-SmokeTimeoutSeconds`, exit codes 4-7, which D8 carries) and tests 12-17. One soft loss: README work (line 147 b) says "log lines of D2/D5/D7" and W2 would copy the two D5 log lines (`Stale build: ...`, `Build is current: ...`) from `_common.ps1` on the branch (it edits that file anyway; code files are not part of the read cap). See advisory B1. D5 would fit (room 3,389 less a 1,800 B draft leaves about 1,590 B vs 1,449 B), so it is an option, not a need. |
| A2 touch count | Line 196: 6 + 5 + 4 = 15 (18 with the three envelope files). Correct. |
| A3 | Line 149: rebuild from `main` BEFORE the two `Start-ScheduledTask` calls; line 170 PC-12 abort says run `deploy\build-web.ps1` (PC-13) before any start. Present. |
| A4 | Line 231: `cd web && pnpm install --frozen-lockfile`, "run unconditionally; it is idempotent". Present; no `node_modules` word in any Bash gate. |
| A5 | Line 46: `Remove-WebBuildMarker` guarded with `Test-Path -LiteralPath` (no-op when absent); line 134 test 8 token `Test-Path -LiteralPath`. Present. |
| A6 | Line 174 adversarial list: "port listing that fails silently (reads as port free; the smoke check exit 6 path still catches the clash)". Present. |
| A7 stale wording | `grep -niE 'recommended|not yet run|cycle 2|open question|to be decided|TBD|pending|awaiting'`: D11 title reads "(resolved, Q3 A)"; no "recommended"; remaining hits are the skeleton Status/Gate PENDING (completed by this stamp), `pending-user` (a JSON value), line 11 "VALIDATE in progress" and Resume lines 360-361 ("no PASS stamp ... yet"): planner-owned, refresh after the stamp (advisory B4). |
| Forbidden words | `grep -noiE '(--force|reset --hard|stash|rebase|merge)'` over the plan: every hit is plan prose (README-rule meta text, worker/user "merges", record template line 172, PC steps); none inside a planned `.ps1` string or log line (D2-D8 strings re-read). `.ps1` scan test covers `.ps1` only; the README is not scanned for these words. |
| First `-H` parse | Real `start-web.ps1`: `param([switch]$DryRun)` has no `-H`; `$webArgs` line 16 is the first code line after the Tailscale wait and holds `'-H', $ip`; the planned `param([switch]$DryRun, [int]$SmokeTimeoutSeconds = 0)` adds none. Regex of the existing test checked against the real file (first match `'-H', $ip`). |
| Base files for tests 5, 6 | Measured on comment-stripped code: `_common.ps1` `{`/`}` 24/24, `(`/`)` 48/48, `[`/`]` 21/21, `"` 14, `'` 36; `build-web.ps1` 2/2, 10/10, 1/1, 16, 10; `start-web.ps1` 2/2, 10/10, 2/2, 14, 18; all ASCII; no assignment to `$pid/$host/$args/$input/$error/$matches` in any `.ps1`; no existing `Get-Process`, `Stop-Process`, `taskkill`; the only `-Force` hits are `New-Item` (`_common.ps1:17`) and `Register-ScheduledTask` (`register-tasks.ps1:50`), so test 1's "`-Force` after Stop-Process" must stay scoped to Stop-Process lines (advisory B3). |
| Contract tables and counts | 17 test rows (6 C1, 5 C2, 6 C3); AC rows map to tests 1-17 with none uncovered; pytest 951 -> 957 -> 962 -> 968; `api/tests/deploy` 51 + 1 skipped -> 57 -> 62 -> 68. Baselines re-run this cycle: `UV_FROZEN=1 uv run --project api pytest api/tests/deploy -q` = 51 passed, 1 skipped; `test_deploy_config_shape.py` has 24 `def test_`; full `pytest api/ -q` = 951 passed, 2 skipped, 5 deselected (193 s). `pwsh`/`powershell` absent. |
| Existing test that must change | Only `test_readme_migration_says_legs_cache_is_not_needed` (lines 255-259); the helper names are gone from `api/src` (grep); README lines 104-105 match the plan's quoted text. Migration slice ends at `## Building the web app` (README 201); the new section goes before `## Starting it automatically` (213). |
| Evidence pack validator | Scratch pack (`pack5/`) with the plan's field lists: `validate-risk-artifacts.mjs` exit 1, exactly one failure `review-decision.json missing or invalid JSON object`, no warnings. |
| Gate-trap hunt (bounded) | Hunted: test red/green counts per commit (stubs 6 / 5+6 / 6+11 consistent), call-order tests 3, 4, 9, 11, 15 against the D2/D3 orders (consistent), the third `Stop-WebPortListener` after `Start-Process` (allowed by test 4, not counted by test 3 which targets `build-web.ps1`), three-dot scans when `main` advances between sessions (merge-base unaffected), `git diff --check` scope, README scan sets (`funnel` etc. absent from the planned README text), first `-H`, quote balance. No blocking defect found. |

## Advisories (non-blocking; the planner copies B1-B3 into the envelopes)

- B1 (W2 envelope): add "D4/D5 log strings and the marker path function: read `_common.ps1` at the branch head (C2 code); quote them verbatim in the README section". Alternative: keep D5 in W2's set (1,449 B; slack about 140 B on the 1,800 B draft estimate, still above the 100 B floor); dropping it is fine.
- B2: after each docs commit only G-R12-9 and G-R12-11 are rescanned, not G-R12-10; the docs commits add only reports and `verification.json` under the task folder (no `deploy/` lines, so the PS-secret and NET scans have nothing to read; the S-secret-scan needs a 12-character token after `Bearer` or `*_KEY=`). W3 rescans G-R12-9..11 at step 13. Acceptable.
- B3 (W1 envelope): test 1 must scope "`-Force`" to lines containing `Stop-Process` (existing `New-Item -Force` and `Register-ScheduledTask -Force` lines are legitimate and would fail a blanket check).
- B4 (planner): refresh line 11 (Status), Resume lines 360-361 and 363 after this stamp; they sit outside every envelope range, so editing them moves no range. Not edited by VALIDATE.
- B5: the Q&A statement "line numbers refer to this file as saved by supplement cycle 2" stays true for lines 1-313 (the stamp inserted its block after line 313); lines beyond move. The ranges reference only lines up to 313, so the table needs no re-derivation; re-derive with the grep if any earlier line is edited.

## Test coverage summary (V3 sections)

Layer 1: Infra fit PASS (paths, ports, PS 5.1 rules, Set-Location ordering, real-file brackets and quotes); Test coverage PASS (N1 fixed; scans follow the commit; runtime criteria stay Hybrid via the user's PC record with the backlog stub as the named residual, so no vacuous green); Breaking changes PASS (new non-secret `/_next/static/build-marker.json`, exit codes 4-7, one new parameter, one edited assertion); Security surface PASS (no auth/secret; kill by port with protected PIDs). Layer 2: C1, C2, C3, C4 PASS on mechanical feasibility and conflicts; highest-risk edit stays C3's child-process restructure (revertable alone; PC-14, PC-15). Net gate PASS.

## Stamp record (final)

Edited in place, line count unchanged: plan lines 242 (contract intro), 244 (`Status: PASS ...`), 245 (the single gate line), 246 (`generated-by: outer-pvl`). Inserted after line 313: `### Validate contract completed (PVL cycle 5, outer-pvl)` (Date, date, Parallel strategy, legacy test-gate lines, Dimension findings, Open gaps, coverage pointer, Accepted by) at lines 315-348, and `## Autonomous Goal Block` (3,006 chars, BRANCH A) at lines 383-399, before `## Worker envelope`. `git diff -U0` shows only those hunks. Plan now 427 lines (validator count), 78,790 B. Range table re-verified from the saved file after the stamp: W1 20,024 / 2,533, W2 19,168 / 3,389, W3 20,605 / 1,952, union 39,617, max referenced line 313 (unchanged text). Completeness greps: `Gate: PASS` 1, `## Autonomous Goal Block` 1, `generated-by:` 1, `What This Coverage Does NOT Prove` 1, `Accepted by:` 1, `Dimension findings` 1. Validator 0 failures, 0 warnings; ASCII and trailing whitespace clean. Nothing committed.
