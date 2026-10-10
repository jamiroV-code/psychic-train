# R12 W2 report (09-10-26)

## 1 Task ID
R12 session W2 (RT4 deploy class): commit C3, then the final full gates. Branch `claude/r12-deploy-fixes`, continued from the W1 head `7f58c9b`.

## 2 Outcome
DONE (code and gates). Overall R12 result stays CONDITIONAL: no PowerShell here, so nothing proves the scripts run on PowerShell 5.1 until the user's PC record (Gate convention 9).

## 3 Summary
- `deploy/start-web.ps1`: new parameter `-SmokeTimeoutSeconds` (0 = default 90 s, 5..600, anything else logs and exits 2, checked before the Tailscale wait). After the stale check and the port stop, `next start` runs via `Start-Process ... -NoNewWindow -PassThru` and `$null = $proc.Handle`. `Invoke-WebSmokeCheck` runs next; on failure: log, `Stop-WebPortListener` (the node grandchild), `Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue`, `exit 6`. On success: `$proc.WaitForExit()` (unbounded by design, D6; shown to the user here for P-R12-1), log `Web process exited with code <n>`, exit with that code (1 when null). The dry run also prints the smoke URL and limit. `$webArgs` is still the first code line after the Tailscale wait.
- `deploy/_common.ps1`: `Get-WebSmokeResponse` (one GET, `-UseBasicParsing -TimeoutSec 5`, status read from the exception for non-200, `Response` presence checked first for StrictMode, byte content decoded as UTF-8) and `Invoke-WebSmokeCheck` (D7: `http://${Ip}:<WebPort>/`, 2 s polls, `$deadline`, early stop on `.HasExited`, evidence A marker file then evidence B HTML, the D7 log strings). Marker path comes from the existing `Get-WebBuildMarkerPath`; the D4/D5 code and the stale-check call order are untouched.
- `deploy/README.md`: new section `## Restarting safely after a web change (R12 guards)` between the rebuild rule and Task Scheduler (procedure a, guard lines b, exit-code table c, marker file and URL d, hand-start warning e, first-start rebuild f); the two "What this is" rows and the rebuild bullet updated. M0 and Rollback lines left as operator text (Q5).
- Tests 12-17 in `api/tests/deploy/test_deploy_r12_guards_shape.py`.

## 4 Files changed
- `deploy/start-web.ps1`
- `deploy/_common.ps1`
- `deploy/README.md`
- `api/tests/deploy/test_deploy_r12_guards_shape.py`
- this report, `harness/verification.json` (13 command entries added)

## 5 Commits
- `c090f72` R12 C3: start-web runs next start as a child with a smoke check
- docs commit: this report and `verification.json` (SHA in the push; scans re-run after it, see 6)

## 6 Tests run (gate, SHA, UTC)
G-R12-1..8 ran on the working tree after the last edit, then the tree was committed unchanged as `c090f72` (no edit between the gates and the commit).

| Gate | SHA | UTC | Result |
|---|---|---|---|
| baseline `pytest api/tests/deploy` | 7f58c9b | 2026-10-09T18:09:10Z | 62 passed, 1 skipped |
| `command -v pwsh` | 7f58c9b | 2026-10-09T18:09:10Z | nothing |
| G-R12-1 red, C3 stubs | 7f58c9b + stubs | 2026-10-09T18:09:30Z | 6 failed, 11 passed |
| G-R12-1 | c090f72 | 2026-10-09T18:11:45Z | 17 passed |
| G-R12-2 | c090f72 | 2026-10-09T18:11:53Z | 24 passed |
| G-R12-3 | c090f72 | 2026-10-09T18:11:53Z | 68 passed, 1 skipped |
| G-R12-4 | c090f72 | 2026-10-09T18:14:53Z | 968 passed, 2 skipped, 5 deselected, 0 xfailed |
| `pnpm install --frozen-lockfile` | c090f72 | 2026-10-09T18:14:59Z | done |
| G-R12-5 | c090f72 | 2026-10-09T18:14:59Z | 251 passed in 34 files |
| G-R12-6 tsc | c090f72 | 2026-10-09T18:15:23Z | exit 0 |
| G-R12-7 islands | c090f72 | 2026-10-09T18:15:23Z | exit 0 |
| G-R12-8 e2e whole suite | c090f72 | 2026-10-09T18:18:12Z | 65 passed |
| G-R12-9..12 on committed C3 | c090f72 | 2026-10-09T18:18:26Z | all print nothing; diff --check exit 0; pwsh absent |

Full suites used one run each (budget 2). No fix cycles were needed.

## 7 Tests NOT run
- Any PowerShell parse or run: `pwsh` is absent. PC checks still open: parser on the three files at the C3 head; step 5 from W1 (real build then start); the smoke check passing with evidence A or B (U3/U4), a smoke failure giving exit 6, and the exit-code passthrough when the server ends.

## 8 Deviations
- `-SmokeTimeoutSeconds` is validated right after `Import-MySiteConfig`, before the Tailscale wait, so a bad value fails fast. It logs with `Write-MySiteLog` (no `-H` text before `$webArgs`).
- Helper name beyond the plan: `Get-WebSmokeResponse` in `_common.ps1` (owned).
- An unreadable marker during the smoke check is treated as no marker (logged as `no build marker, build id not checked`). The stale check has already refused an unreadable marker before the start, so this path should not occur.
- The scout hook blocks Bash commands that contain the word for the web compile step, so the `.ps1` and README edits were made with the editor tools; no gate command was changed.

## 9 Blockers
None.

## 10 Follow-up
- W3: PC runbook and record template, PR. The PC record must cover: the parser on the C3 head; a real `build-web.ps1` then `start-web.ps1` with `Smoke check ok` and which evidence (marker-file or html) held; `-SmokeTimeoutSeconds 7` with the API down still passes (the root page needs no API); a forced smoke failure gives exit 6 and leaves the port free; `Stop-ScheduledTask mysite-web` makes the log show `Web process exited with code <n>`.
- `Start-Process` on a `pnpm.cmd` PnpmPath runs through `cmd.exe`; `Stop-Process` of the parent after a failed smoke check relies on the port stop having already ended the node grandchild. Check on the PC.

## 11 Context cost
Read: CLAUDE.md (session), the envelope, the named plan line ranges, W1 report headings 8, 10 (and the 6/11/12 tail while extending the record format). No other docs opened. About 30 tool calls.

## 12 PC check (added after the session, user report 2026-10-10)
The user ran the check on the PC at `44060ac` (the log says `Build is current: commit 44060ac`) and pasted the console output of three `start-web.ps1` runs and the `web.log` tail. NOT pasted: steps 1-4 output (checkout, parser, dry run, `build-web.ps1`), the command used in the second window, and the `Get-NetTCPConnection` output from step 9.

| Step | Result | Evidence pasted |
|---|---|---|
| 1-4 checkout, parser, dry run, build | Not pasted. Implied by what was pasted: the PC was at 44060ac, `start-web.ps1` and `_common.ps1` parsed and ran, and a real build wrote a marker (build id changed `8_pAGY...` to `W1ZAw...`, still `Build is current`). Not an explicit parser record. | no |
| 5 real start and smoke check | PASS. `Starting web on 100.x:3000`, Next `Ready in 1029ms`, `Smoke check ok: ... returned 200 and build id ... matches the marker (evidence: marker-file)` about 2 s after the start. Same at 08:54:12 and 08:56:08. Evidence A holds (U3: `next start` serves the marker file); B was not needed. This also covers W1 step 5. | yes |
| 6 exit-code passthrough | PASS. Node stopped from a second window; pnpm printed `ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL`; script logged `Web process exited with code 1` and `exit code: 1`. The pnpm error is pnpm reporting the stopped child, expected. | output yes, stop command no |
| 7 stale refusal | PASS. `Stale build: tracked web file newer than the build: web/app/page.tsx. ...`, `exit code: 4`. | yes |
| extra: real port-scoped stop | PASS. The 08:56:06 run (the scheduled task, per the user) logged `Port 3000: stopping PID 12284 (node) listening on it.`, `Port 3000: free.`, then started and passed. The hand-started instance from 08:54 then logged `Web process exited with code 1`. This is the README hand-start warning in action: a second copy stops the running server and the first script exits non-zero. | log yes |
| 8 forced smoke failure (exit 6) | NOT RUN (the user identified the 08:56:06 run as step 9). With Next ready in about 1 s, `-SmokeTimeoutSeconds 5` would not force a failure anyway. | n/a |
| 9 scheduled task, listener after Stop-ScheduledTask | PASS. Task start at 08:56:06: smoke ok 08:56:08 (marker-file). After `Stop-ScheduledTask mysite-web`, `Get-NetTCPConnection -State Listen -LocalPort 3000` printed nothing: no orphaned node server. No `Web process exited` line after the stop, expected (the task stop ends the script itself). | listener check and log yes; the two task command lines no |

Open for the PC record (W3 runbook): the exit-6 path (smoke failure, cleanup of the node listener and the pnpm parent, port left free) needs a way to make `next start` fail or not answer, not a short timeout. Until then AC-R12-3's failure half stays CONDITIONAL. AC-R12-5 is text only and unaffected.
