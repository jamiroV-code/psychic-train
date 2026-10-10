---
name: report:r12-deploy-fixes-pc-record
description: "R12 deploy fixes: filled PC acceptance record from the user-reported results of 2026-10-10. Verdict APPROVE WITH CONCERNS (accepted with known gaps)."
date: 10-10-26
feature: general-plans
---

# R12 PC acceptance record

Every result below is user-reported: the user ran the runbook steps in Windows PowerShell 5.1 with the planner assisting in chat and pasted the console output. The worker (W4) did not run anything on the PC. "Full paste" means the user pasted the whole console output for that step. No addresses or secrets in this file; the Tailscale address is written as 100.x.

## Header

| Field | Value |
|---|---|
| Date and time, local | 2026-10-10 13:54 to 14:10 (+02:00), user-reported |
| Date and time, UTC | 2026-10-10 11:54 to 12:10 (converted from the local time) |
| PC name (no address) | DESKTOP-3QG46B4 |
| PowerShell version | Windows PowerShell 5.1.19041.6456 |
| Windows version | Windows NT 10.0.19045.0 |
| Branch head SHA | 7fd38ac4edff7649e9536108a0ce905053d9be03 |
| `git rev-parse HEAD:deploy` (expected `65b61e510d3bc2c1d3278832ba8087fe7dbb6726`) | 65b61e510d3bc2c1d3278832ba8087fe7dbb6726 (equal) |
| Build id of the tested build | v5K0mognZxyFRFiOIh_aP (built at 7fd38ac, web tree 3c5d2dc) |
| Evidence kind seen at PC-10 (`marker-file` or `html`) | marker-file (PC-11, PC-16) |

## Steps

Label for all rows: user-reported. The paste column says what the user pasted.

| Step | What | Result | One line and pasted log lines |
|---|---|---|---|
| PC-1 | environment | PASS (user-reported, full paste) | Tailscale IPv4 present (100.x). `git status` showed only 4 modified data files `api/data/cache/narrative/coingecko/{ai,l2s,memecoins,rwa}.parquet` (live API cache, left untouched by decision). No `deploy/` file modified. |
| PC-2 | tasks stopped, ports 3000/8000 free | PASS (user-reported, full paste) | `Stop-ScheduledTask` on mysite-web and mysite-api; listings of ports 3000 and 8000 empty. A first paste hit a trailing-pipe parser artefact in the typed command; the rerun was clean. |
| PC-3 | branch checkout, head SHA, deploy tree | PASS (user-reported, full paste) | `git switch claude/r12-deploy-fixes`, later `git merge --ff-only` to 7fd38ac. `git rev-parse HEAD:deploy` = 65b61e510d3bc2c1d3278832ba8087fe7dbb6726, equal to expected. |
| PC-4 | parser, five scripts, `0 errors` | PASS (user-reported, full paste) | Run at 44060ac (its deploy tree is identical to 7fd38ac): `_common.ps1`, `build-web.ps1`, `register-tasks.ps1`, `start-api.ps1`, `start-web.ps1`, each 0 errors. |
| PC-5 | dry runs, all `exit=0` | PASS (user-reported, full paste) | At 7fd38ac, all exit 0. `start-web -DryRun`: `DRY RUN (nothing started)`, host/port/command/smoke lines, `DRY RUN: Build is current: commit 44060ac web tree 3c5d2dc build id W1ZAw-8zQB5PN9FQpJZFC`, `DRY RUN: Note: HEAD 7fd38ac differs from the build commit 44060ac; web/ is unchanged.` (Q1 B rule observed: HEAD moved, web tree unchanged, a note and not a refusal), `DRY RUN: port 3000 is free; nothing would be stopped.` `build-web -DryRun`: `DRY RUN (nothing built)`, the command, port-free line. `start-api -DryRun`: the unchanged old lines. |
| PC-6 | refusal with no marker | PASS (user-reported, full paste) | The build marker file was renamed; real `start-web.ps1` logged `Stale build: no build marker. Run deploy\build-web.ps1, then start again.`, exit=4, nothing started. Marker restored, `Test-Path` True. |
| PC-7 | decoy listener, dry run names its PID, nothing stopped | PASS (user-reported, full paste) | Non-node decoy: a PowerShell TcpListener on the web port, PID 4252, process name powershell. `start-web -DryRun` printed `DRY RUN: would stop PID 4252 (powershell) listening on port 3000 (nothing stopped).`, exit=0; `Get-Process` showed the decoy alive. |
| PC-8 | build stops the decoy by PID, marker written, `exit=0` | PASS (user-reported, full paste) | `build-web.ps1` with the decoy listening: `Port 3000: stopping PID 4252 (powershell) listening on it.`, `Port 3000: free.`, `Build marker removed before the build.`, vite islands and next build (all routes built), `Web build exited with code 0`, `Build marker written: commit 7fd38ac web tree 3c5d2dc build id v5K0mognZxyFRFiOIh_aP`. exit=0. `Get-Process` on the decoy PID printed nothing (decoy window died). |
| PC-9 | marker commit/web_tree/build_id match HEAD, HEAD:web, BUILD_ID | PASS (user-reported, full paste) | Marker JSON: schema 1, commit 7fd38ac4edff7649e9536108a0ce905053d9be03, web_tree 3c5d2dc288bff4461fdf678fbaaba00ee2571554, dirty false, build_id v5K0mognZxyFRFiOIh_aP, built_at_utc 2026-10-10T11:55:27Z. `git rev-parse HEAD` and `HEAD:web` and `BUILD_ID` all equal the marker values. |
| PC-10 | start: `Build is current`, `Smoke check ok`, HTTP 200, served marker equals PC-9 | PASS (user-reported; observed inside PC-11 and PC-16, not a separate step) | The explicit `Invoke-WebRequest` outputs were seen in PC-11: GET / = 200, GET `/_next/static/build-marker.json` returned the PC-9 JSON. Evidence kind marker-file. |
| PC-11 | replay of the incident (non-node decoy stopped, then smoke ok) | PASS (user-reported, full paste) | Second decoy PID 16604 (powershell) on 3000. Real `start-web.ps1`: `Build is current: commit 7fd38ac web tree 3c5d2dc build id v5K0mognZxyFRFiOIh_aP`, `Port 3000: stopping PID 16604 (powershell) listening on it.` (matched the PID listed before), `Port 3000: free.`, `Starting web on 100.x:3000`, Next `Ready in 640ms`, `Smoke check ok: ... returned 200 and build id v5K0mognZxyFRFiOIh_aP matches the marker (evidence: marker-file).` Then listener PID 15368 (node) on 3000, GET / = 200, served marker JSON equal to PC-9 (evidence A confirmed: `next start` serves the marker file). Server stopped with Ctrl+C (Y). |
| PC-12 | stale refusal after touching `web\app\page.tsx`, exit 4 | PASS (user-reported earlier, with paste; W2 report heading 12) | `Stale build: tracked web file newer than the build: web/app/page.tsx`, exit code 4. Observed at 44060ac, before this session. |
| PC-13 | rebuild restores a fresh build, exit 0 | Not a separate step; covered by PC-8 (user-reported) | The PC-8 build wrote a fresh marker and PC-9 matched it. No distinct "touch then rebuild" run was pasted this session. |
| PC-14 | forced smoke failure: `Smoke check FAILED`, `exit=6`, no listener left | PASS for the process-died branch only (user-reported, full paste) | The `server` folder under the web build output was renamed to `server.off`; `start-web.ps1 -SmokeTimeoutSeconds 10`: `Build is current...`, `Port 3000: nothing listening; nothing to stop.`, Next failed with ENOENT on `server\pages-manifest.json`, `ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL`, `Smoke check FAILED: web process exited with code 1 before answering.`, `Smoke check failed; stopping the new web server.`, `Port 3000: nothing listening; nothing to stop.`, exit=6 (first time the value 6 was observed). Listing afterwards empty; folder renamed back, `Test-Path` True. HTTP non-200 and build-id mismatch branches NOT exercised (known gap). |
| PC-15 | scheduled task start, smoke ok, no listener after `Stop-ScheduledTask` | PASS (user-reported earlier, partial paste; W2 report heading 12) | Task start gave `Smoke check ok` (marker-file); after `Stop-ScheduledTask mysite-web` no listener on 3000. The two task command lines were not pasted. Re-seen in part at PC-16 (task start, smoke ok). |
| PC-16 | restore, clean tree, both services up | PASS (user-reported) | `Start-ScheduledTask` mysite-api and mysite-web; `web.log` tail: `Build is current: commit 7fd38ac ...`, `Port 3000: nothing listening; nothing to stop.`, `Starting web on 100.x:3000`, `Smoke check ok: ... (evidence: marker-file)`. Listeners: 8000 (PID 14648), 3000 (PID 8388). `git status` shows only the four parquet data files. HEAD 7fd38ac on `claude/r12-deploy-fixes`; the user stays on the branch until PR #45 is merged, then `git switch main`. The user reported "site running, all working". |

Known gaps (stay known gaps, never PASS):

- Smoke check `HTTP <code>` (non-200) and `served build id does not match the marker` branches cannot be forced on the PC without editing code. Covered by shape tests only.
- Exit code 6 was observed only for the `process exited before answering` branch.
- A failed-smoke `Stop-WebPortListener` could itself exit 5 before the exit 6 line (EVL note, not observed).
- An invalid WebPort under `-ReportOnly` still exits 2 (harmless, nothing killed).
- Steps 1-4 of the earlier W1/W2 sessions were partial pastes; they are now covered by the full pastes above (PC-1 to PC-5).
- PC-13 has no separate run (see the row).

## Incidents or deviations

- PC-2: the first paste hit a trailing-pipe parser artefact in the typed command (a typing artefact, not a script fault); the rerun was clean.
- PC-1 and PC-16: four tracked parquet files under `api/data/cache/narrative/coingecko/` show as modified. They are the live API cache; left untouched by decision. No `deploy/` file was modified.
- PC-4 ran at 44060ac, not 7fd38ac; the `deploy/` tree is identical (65b61e51...), so the result holds for the tested head.

## Verdict

- Overall: APPROVE WITH CONCERNS (user verdict: ACCEPTED WITH KNOWN GAPS)
- One sentence: All PC steps that can be run without editing code passed in Windows PowerShell 5.1, and the user accepted the named known gaps and the single unbounded `WaitForExit` in `start-web.ps1` (line 61) as a design choice.
- User's name and date: the user (name not recorded in this file), 2026-10-10; decision recorded via the planner. The user read the `deploy/` diff of PR #45 (diff check done).
- Post-merge: `git rev-parse origin/main:deploy` equals the tested tree: yes. W4 checked it on 2026-10-10 (PR #45 is already merged into main; `origin/main:deploy` = 65b61e510d3bc2c1d3278832ba8087fe7dbb6726). This is a worker check from the repository, not a PC result.

## Mapping

No FAIL. No SKIP of PC-11, PC-14 or PC-15. PC-14 covers one of three smoke-failure branches, so `approved-with-concerns` is the matching value. A merge changes the SHA, never the `deploy/` tree: the post-merge check compares trees.
