# R12 W1 session report

## 1 Task ID
R12 session W1 (RT4 deploy class): C1 port-scoped stop, README legs wording, tests 1-6; C2 build marker and stale-build guard, tests 7-11. Branch `claude/r12-deploy-fixes` from `origin/main` 7ead516.

## 2 Outcome
DONE (text-shape level). C1 and C2 committed; G-R12-1..3 at 57 then 62 deploy tests as the plan arithmetic says; scans G-R12-9..12 clean after each commit. Branch pushed; no PR opened, nothing merged. Every runtime criterion stays CONDITIONAL until the user's PC record (no PowerShell here; no claim that any script runs).

## 3 Summary
- `_common.ps1`: `Get-WebPortListenerIds` (listen sockets on one port, by PID), `Stop-WebPortListener` (validates WebPort 1-65535 and different from ApiPort, else exit 2; refuses PID 4 or less and `$PID`; `Stop-Process -Id ... -ErrorAction Stop`, no name, no -Force; re-checks with `Get-Process -Id` on error; 10 s bounded wait in 0.5 s steps; fail-closed exit 5; `-ReportOnly` prints `DRY RUN:` lines and never exits except on a config error). C2 adds `Get-WebBuildMarkerPath`, `Get-WebBuildIdPath`, `Get-ShortSha`, `ConvertTo-MySiteEpoch`, `Invoke-MySiteGit` (`git -C RepoRoot`, exit code checked, stderr not redirected), `Remove-WebBuildMarker`, `Write-WebBuildMarker` (D4 fields, UTF-8 without BOM, exit 7 on any failure), `Test-WebBuildFresh` (D5 checks 1-7 in order, Q1 B: HEAD alone moving is a note; Q2 A: no marker refuses with exit 4).
- `build-web.ps1`: dry run reports the stop only; real run: stop, remove marker, build, write marker only on `$code -eq 0`, `exit $code`.
- `start-web.ps1`: `$webArgs` stays the first code line after the Tailscale wait; dry run prints the stale-check result and the stop report, exits 0; real run: stale check (exit 4), then stop, then start.
- `deploy/README.md` lines 104-105 reworded as the plan specifies; the one allowed assertion edit in `test_deploy_config_shape.py`.

## 4 Files changed
- `deploy/_common.ps1`, `deploy/build-web.ps1`, `deploy/start-web.ps1`, `deploy/README.md`
- `api/tests/deploy/test_deploy_config_shape.py` (one assertion replaced by two, as listed)
- `api/tests/deploy/test_deploy_r12_guards_shape.py` (new, 11 tests)
- `process/general-plans/active/r12-deploy-fixes_03-10-26/harness/verification.json` (new, commands only), this report

## 5 Commits
- C1 `1cc96d2` R12 C1: port-scoped web stop before build and start
- docs `601380f` interim report and verification after C1
- C2 `5b68192` R12 C2: build marker and stale-build guard for start-web
- docs: this commit (final report, verification.json)

## 6 Tests run (gate, SHA, UTC)
| Gate | SHA | UTC | Result |
|---|---|---|---|
| baseline `pytest api/tests/deploy` | 7ead516 | 2026-10-09T11:59:30Z | 51 passed, 1 skipped |
| `command -v pwsh` | 7ead516 | 2026-10-09T11:59:30Z | nothing |
| G-R12-1 red, C1 stubs | pre-C1 | 2026-10-09T12:00:27Z | 6 failed |
| G-R12-2 red, legs assertion before README edit | pre-C1 | 2026-10-09T12:00:27Z | 1 failed, 23 passed |
| G-R12-1 / 2 / 3 (C1) | 1cc96d2 | 2026-10-09T12:03:14Z | 6 passed / 24 passed / 57 passed, 1 skipped |
| G-R12-9..12 (C1) | 1cc96d2 | 2026-10-09T12:03:14Z | all empty, diff --check exit 0, pwsh absent |
| G-R12-1 red, C2 stubs | 601380f + stubs | 2026-10-09T12:03:29Z | 5 failed, 6 passed |
| G-R12-1 / 2 / 3 (C2) | 5b68192 | 2026-10-09T12:05:27Z | 11 passed / 24 passed / 62 passed, 1 skipped |
| G-R12-9..12 (C2) | 5b68192 | 2026-10-09T12:05:34Z | all empty, diff --check exit 0, pwsh absent |
| G-R12-9, G-R12-11 rescan after this docs commit | see push note | after commit | recorded in the session reply |

All pytest runs used `UV_FROZEN=1`. Gates ran on the working tree that was then committed unchanged (git status clean apart from the committed files).

## 7 Tests NOT run
- Any PowerShell parse or run (pwsh absent; G-R12-12). Runtime behaviour of `Get-NetTCPConnection` with `-ErrorAction SilentlyContinue` on a free port under the global Stop preference, `Stop-Process`, marker write and stale check are unverified until the PC record.
- Full pytest suite, vitest, tsc, islands: not named for W1.

## 8 Deviations
- Base: local `main` was stale (766e6a3, missing the plan commit d054755). The branch was first cut from it; C1 (`16498ed`) was moved onto `origin/main` 7ead516 before any push (no deploy or test file differs between the two bases) and all C1 gates and scans were re-run on `1cc96d2`.
- Docs commits: the envelope asks for a docs commit after each code commit; the plan step 7 lists one. Did both: interim after C1, final after C2.
- Helper names beyond the plan: `Get-WebBuildIdPath`, `Get-ShortSha`, `ConvertTo-MySiteEpoch`, `Invoke-MySiteGit` (all in `_common.ps1`, owned).
- Invalid WebPort under `-ReportOnly` prints a `DRY RUN:` line instead of writing the log file, then still exits 2 (config error).

## 9 Blockers
None. No needs_input open.

## 10 Follow-up
- W2/W3: C3 (smoke cleanup, README guard section after "Building the web app: the rebuild rule", PC runbook and record template), tests 12-17.
- PC record must cover: free-port dry run (no false "cannot list listeners"), stop of a real `next start`, first start without a marker refused with exit 4, marker written after a build, HEAD-only move gives the note.

## 11 Context cost
Read: CLAUDE.md (session), the envelope, the named plan line ranges only. No other docs opened. About 40 tool calls.

## 12 PC check (added after the session, user report 2026-10-09)
The user ran on the PC, at branch head 314bc0a, and reported all four as success (output not pasted into the session):
1. checkout of `claude/r12-deploy-fixes`;
2. PowerShell parser on `_common.ps1`, `build-web.ps1`, `start-web.ps1`: no parse errors;
3. `Get-NetTCPConnection -State Listen -LocalPort 65000 -ErrorAction SilentlyContinue` under `$ErrorActionPreference = 'Stop'`: no throw on a free port, so the D2 free-port risk named in heading 10 is cleared;
4. `start-web.ps1 -DryRun`: stale-check and port report lines, exit 0.

NOT run yet: step 5, the real `build-web.ps1` then `start-web.ps1` (marker write, `Build is current`, real port stop, server start). Overall result stays CONDITIONAL until that runs.
