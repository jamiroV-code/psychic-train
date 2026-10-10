---
name: ref:r12-deploy-fixes-pc-runbook
description: "R12 deploy fixes: copy-paste runbook for the user's Windows PC. Only the steps still needed after the W1/W2 PC checks; log strings quoted from the shipped scripts."
date: 10-10-26
feature: general-plans
---

# R12 PC runbook (C4)

## TL;DR

- Who: the user, in Windows PowerShell 5.1 (not pwsh, not admin). The planner assists in chat.
- What is still open after the W1 and W2 PC checks: the real exit code 6 value, a non-node process (decoy) on the web port being stopped, the dry-run lines and marker values as pasted evidence, and the parser at the final head. The smoke-check "HTTP non-200" and "build id mismatch" branches cannot be forced on the PC without editing code; they stay a known gap (see the end).
- Time: about 30 minutes (one build).
- Scripts under test: `deploy\_common.ps1`, `deploy\build-web.ps1`, `deploy\start-web.ps1`. Tested tree: `git rev-parse HEAD:deploy` must print `65b61e510d3bc2c1d3278832ba8087fe7dbb6726` (the planner confirms it if the branch moved).
- Step numbers PC-1..PC-16 match the acceptance record. Steps not listed below as a step were observed already (table "Already observed").
- Log lines start with a timestamp and `[web]` or `[build-web]`; the expected text below is the part after that.

## Stop and ask the planner

- Any listener on port 3000 or 8000 whose owner you do not recognise.
- Any step that fails twice.
- Any message you do not understand. Paste it, do not guess.

## Abort and restore (safe at any point)

Run these in order. Nothing outside `web\.next`, the branch checkout and the two task states is ever changed.

1. Close any decoy window (press Enter in it).
2. If the folder `web\.next\server.off` exists:

```powershell
Rename-Item web\.next\server.off server
```

3. Go back to main:

```powershell
git switch main
```

4. If a build was interrupted, run the build once from `main` (old behaviour), and only THEN start the tasks (an old launcher started on a half-built output exits non-zero and Task Scheduler burns its 3 retries):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\build-web.ps1
Start-ScheduledTask mysite-web
Start-ScheduledTask mysite-api
```

If no build was interrupted, only the two `Start-ScheduledTask` lines are needed.

## Already observed (user-reported, W1 and W2, partial paste; not a PASS by the worker)

| Step | What was reported | Pasted | Not pasted |
|---|---|---|---|
| PC-3/PC-4 (W1, at 314bc0a) | checkout ok; parser: no errors on the three files | no | all output |
| PC-5 (W1, 314bc0a) | `start-web.ps1 -DryRun`: stale-check and port lines, exit 0 | no | all output |
| PC-10 (W2, 44060ac) | `Starting web on 100.x:3000`, `Smoke check ok ... (evidence: marker-file)` about 2 s after start; HTTP 200 implied by the check | log lines | the two `Invoke-WebRequest` outputs |
| PC-11 partial (W2) | real stop of a node server on 3000 by PID (`Port 3000: stopping PID 12284 (node) listening on it.`, `Port 3000: free.`), then start and smoke ok | web.log lines | decoy (non-node) variant |
| PC-12 (W2) | `Stale build: tracked web file newer than the build: web/app/page.tsx. ...`, exit code 4 | yes | none |
| PC-14 partial (W2) | `web\.next\server` renamed, `-SmokeTimeoutSeconds 10`: `Smoke check FAILED: web process exited with code 1 before answering.`, `Smoke check failed; stopping the new web server.`, `Port 3000: nothing listening; nothing to stop.` | log lines | the exit code (script was not run via `powershell -File`) |
| PC-15 (W2) | task start: smoke ok; after `Stop-ScheduledTask mysite-web` no listener on 3000 | web.log and empty listing | the two task command lines |
| exit-code passthrough (W2) | node stopped from a second window: `Web process exited with code 1`, exit code 1 | yes | the stop command |

Not observed anywhere: exit code 6 as a number, the smoke check "HTTP <code>" and "served build id does not match the marker" branches, `build-web.ps1 -DryRun` and `start-api.ps1 -DryRun` output, the missing-marker refusal (`Stale build: no build marker`), and the build-web decoy stop.

## PC-1 Environment

```powershell
cd <RepoRoot>
$ts = "C:\Program Files\Tailscale\tailscale.exe"
$ip = (& $ts ip -4 | Select-Object -First 1).Trim()
$ip
$PSVersionTable.PSVersion.ToString()
[System.Environment]::OSVersion.VersionString
$env:COMPUTERNAME
git status --short
```

- Expect: `100.x.y.z`; `5.1.x`; a Windows version string; the PC name; status empty or untracked files only.
- Paste back: all five outputs (the PC name is for the record; no address).
- If it fails / abort: nothing was changed. Paste the output and stop. Tracked files modified: stop and ask.

## PC-2 Stop the services, check the ports

```powershell
Stop-ScheduledTask mysite-web -ErrorAction SilentlyContinue
Stop-ScheduledTask mysite-api -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Get-NetTCPConnection -State Listen -LocalPort 3000,8000 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess
```

- Expect: no rows.
- Paste back: the output.
- If it fails / abort: a row is a leftover listener. Paste it and stop (do not kill it yourself).

## PC-3 Branch and tested tree

```powershell
git fetch origin
git switch claude/r12-deploy-fixes
git log -1 --format="%H %s"
git rev-parse HEAD:deploy
```

- Expect: a head SHA equal to the one the planner gives; the tree line `65b61e510d3bc2c1d3278832ba8087fe7dbb6726`.
- Paste back: both lines.
- If it fails / abort: if the tree differs, stop and ask. Nothing was changed beyond the branch checkout; run the Abort and restore block.

## PC-4 Parser at the final head

```powershell
Get-ChildItem deploy\*.ps1 | ForEach-Object { $e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$null,[ref]$e); "$($_.Name): $($e.Count) errors" }
```

- Expect: five lines (`_common.ps1`, `build-web.ps1`, `register-tasks.ps1`, `start-api.ps1`, `start-web.ps1`), each `0 errors`.
- Paste back: the output.
- If it fails / abort: any error count above 0: paste the output and stop. Nothing was started.

## PC-5 Dry runs (nothing started, nothing stopped)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-web.ps1 -DryRun; "exit=$LASTEXITCODE"
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\build-web.ps1 -DryRun; "exit=$LASTEXITCODE"
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-api.ps1 -DryRun; "exit=$LASTEXITCODE"
```

- Expect: `start-web`: `DRY RUN (nothing started)`, host/port/command/smoke lines, then `DRY RUN: Build is current: ...` or `DRY RUN: Stale build: ...`, then `DRY RUN: port 3000 is free; nothing would be stopped.`, `exit=0`. `build-web`: `DRY RUN (nothing built)`, the command line, `DRY RUN: port 3000 is free; nothing would be stopped.`, `exit=0`. `start-api`: unchanged old lines, `exit=0`.
- Paste back: all three outputs.
- If it fails / abort: nothing was started. Paste and stop.

## PC-7 Decoy listener (a non-node process on the web port)

Window 2 (a second Windows PowerShell 5.1 window):

```powershell
$ip = (& "C:\Program Files\Tailscale\tailscale.exe" ip -4 | Select-Object -First 1).Trim()
$l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Parse($ip), 3000)
$l.Start()
"decoy PID=$PID"
Read-Host "leave this window open"
```

If Windows Firewall shows a prompt for the decoy, choose Cancel (a local bind is enough). Leave this window open.

Window 1:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 3000 | Select-Object LocalAddress,LocalPort,OwningProcess
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-web.ps1 -DryRun; "exit=$LASTEXITCODE"
Get-Process -Id <decoy PID>
```

- Expect: the decoy PID in the listing; the dry run says `DRY RUN: would stop PID <decoy PID> (powershell) listening on port 3000 (nothing stopped).` and `exit=0`; `Get-Process -Id <decoy PID>` still answers.
- Paste back: both outputs and the decoy PID.
- If it fails / abort: close the decoy window with Enter, or `Stop-Process -Id <decoy PID>`. A different process name than `powershell` is fine; paste it.

## PC-8 Build with the decoy still listening

Window 1 (takes minutes):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\build-web.ps1; "exit=$LASTEXITCODE"
Get-Process -Id <decoy PID> -ErrorAction SilentlyContinue
Get-Content "$env:LOCALAPPDATA\my_site\logs\build-web.log" -Tail 8
```

- Expect: the log has `Port 3000: stopping PID <decoy PID> (powershell) listening on it.`, `Port 3000: free.`, `Web build exited with code 0`, `Build marker written: commit <7> web tree <7> build id <id>`; `exit=0`; `Get-Process` prints nothing and the decoy window is gone.
- Paste back: the log tail, the exit line, the `Get-Process` result.
- If it fails / abort: Ctrl+C the window (answer Y at `Terminate batch job (Y/N)?`; N or closing the window can leave `node` listening: list port 3000 with the PC-2 command, the next start stops a leftover), then run the Abort and restore block.

## PC-9 Marker matches the build

```powershell
Get-Content web\.next\static\build-marker.json
git rev-parse HEAD
git rev-parse HEAD:web
Get-Content web\.next\BUILD_ID
```

- Expect: marker `commit` equals HEAD, `web_tree` equals HEAD:web, `build_id` equals BUILD_ID, `dirty` false.
- Paste back: all four outputs.
- If it fails / abort: paste and stop. Nothing was started.

## PC-11 Replay the incident with a non-node decoy

Window 3: start the PC-7 decoy again (the same four lines; note the new PID). Window 2: close the old one if still open, then

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-web.ps1
```

(it stays running).

- Expect: in window 2, `Build is current: commit <7> web tree <7> build id <id>`, `Port 3000: stopping PID <decoy PID> (powershell) listening on it.`, `Port 3000: free.`, `Starting web on <ip>:3000`, then `Smoke check ok: http://<ip>:3000/ returned 200 and build id <id> matches the marker (evidence: marker-file)` (or `html`). The decoy window is gone.
- Paste back: the window 2 text and, in window 1, the output of the PC-2 listing command (one row, the node server).
- If it fails / abort: Ctrl+C window 2 (Y), list port 3000, then the Abort and restore block.

Then, in window 1, the PC-10 values (optional, not pasted before):

```powershell
(Invoke-WebRequest "http://${ip}:3000/" -UseBasicParsing).StatusCode
(Invoke-WebRequest "http://${ip}:3000/_next/static/build-marker.json" -UseBasicParsing).Content
```

- Expect: `200`; the marker JSON equals PC-9. Paste both. Then stop window 2 with Ctrl+C (answer Y) and run the PC-2 listing: expect no rows or a leftover node (paste its PID; the next start stops it).

## PC-14 Forced smoke failure and the exit code 6 value

```powershell
Rename-Item web\.next\server server.off
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-web.ps1 -SmokeTimeoutSeconds 10; "exit=$LASTEXITCODE"
Get-NetTCPConnection -State Listen -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess
Rename-Item web\.next\server.off server
```

- Expect: `Smoke check FAILED: web process exited with code 1 before answering.` (or `Smoke check FAILED: no answer after 10s.`), `Smoke check failed; stopping the new web server.`, `Port 3000: nothing listening; nothing to stop.` (or a stop line), and `exit=6`; the listing is empty; the rename back succeeds. The `exit=` line must appear: run the script exactly as above, with `powershell -File`.
- Paste back: the whole output including `exit=`.
- If it fails / abort: if you stopped after the first rename, run `Rename-Item web\.next\server.off server`, or rebuild with `deploy\build-web.ps1`.

## PC-16 Restore and finish

```powershell
git switch main
Start-ScheduledTask mysite-api
Start-ScheduledTask mysite-web
Start-Sleep -Seconds 45
Get-Content "$env:LOCALAPPDATA\my_site\logs\web.log" -Tail 6
git status --short
```

The tasks run the scripts from the checked-out branch. After `git switch main` they run main's old scripts; stay on the branch instead if you want the new scripts live until the PR is merged, and say so in the record.

- Expect: a clean tree (or untracked files only); both services up; with the new scripts, `Smoke check ok` in `web.log`.
- Paste back: the final lines.
- If it fails / abort: run the Abort and restore block.

Then fill the acceptance record (`r12-deploy-fixes-pc-record_REPORT_10-10-26.md` is written by the planner from your chat results; the blank template is `r12-deploy-fixes-pc-record-template_REF_10-10-26.md`).

## Known gap (not testable on the PC without editing code)

- Smoke check "HTTP <code>" and "served build id does not match the marker": the stale check refuses a build whose `BUILD_ID` differs from the marker before the server starts, and the root HTML carries the build id as a second evidence, so neither branch can be forced with files or ports alone. They stay covered by the shape tests only; mark them "known gap" in the record, not PASS.
- Mapping: any FAIL means `rejected` and R12 returns to `in_progress`; SKIP of PC-11, PC-14 or PC-15 means `approved-with-concerns` at best.
