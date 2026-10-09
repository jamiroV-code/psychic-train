---
name: plan:r12-deploy-fixes
description: "R12 deploy fixes (RT4, HIGH-RISK deploy class): port-scoped stop before build and start, stale-build guard via a build marker, post-start smoke check; three sequential worker sessions on one branch (W1 port stop and stale guard, W2 smoke check and final gates, W3 PC runbook, record template, evidence pack, PR), shape tests in CI, copy-paste PC runbook and acceptance record, stops at review for the user's diff check and PC record"
date: 09-10-26
feature: general-plans
---

# R12 Deploy Fixes: Port-Scoped Stop, Stale-Build Guard, Post-Start Smoke Check

Date: 09-10-26
Status: PLANNED 09-10-26 (PLAN only). VALIDATE (PVL) in progress (supplement cycle 2 folded; VALIDATE from V1 next); Q1-Q5 and the brief are RESOLVED by the user (09-10-26). Registry `blocked` -> `approved` is recorded by the planner after PASS; no envelope or worker before ENTER EXECUTE MODE. Code read at origin/main `abda8e7` (process-only commits since `270f9ac`; api/, web/, deploy/ identical).
Complexity: COMPLEX (RT4 high-risk deploy class; one task, three worker sessions, commits C1-C4 plus docs commits; runtime provable only on the user's Windows PC)

**TL;DR:** Three changes to the PowerShell launchers so a restart after a `web/` change cannot serve a stale build. (1) `build-web.ps1` and `start-web.ps1` stop only the process listening on `WebPort` (found by port, never by name; logged; nothing if free). (2) `build-web.ps1` writes a marker `web/.next/static/build-marker.json` after a successful build; `start-web.ps1` refuses (exit 4) when the marker is missing, the `web/` tree differs from the build, or a tracked web file is newer than the build. (3) `start-web.ps1` runs `next start` as a child process and polls its own Tailscale address for HTTP 200 plus a matching build id (exit 6 on failure). A sandbox without PowerShell checks script TEXT only (17 new shape tests); the runtime proof is the user's PC run, for which a worker writes a numbered copy-paste runbook and a record template. The 36,000 B worker read cap cannot hold the 39,477 B of plan lines the three sessions read between them, so the task runs as three sequential worker sessions on one branch (W1, W2, W3; fine sub-range table at the end). W3 opens the PR and the task stops at `review`; no worker merges. Order (confirmed by the user): user diff check, PC run on the branch, user merges, planner records `accepted`. Estimate 3-5 USD [estimate] (three sessions instead of the brief's single 2-4) against 25.27 USD left of the 60 USD ceiling.

Folder index: SPEC `r12-deploy-fixes_SPEC_03-10-26.md` (user-confirmed 09-10-26 as written); this plan; at spawn `r12-deploy-fixes-w{1,2,3}_REF_<dd-mm-yy>.md` (envelopes); worker deliverables `r12-deploy-fixes-pc-runbook_REF_<dd-mm-yy>.md`, `r12-deploy-fixes-pc-record-template_REF_<dd-mm-yy>.md`, `r12-deploy-fixes-w{1,2,3}_REPORT_<dd-mm-yy>.md`, `harness/` (evidence pack); later the user's record `r12-deploy-fixes-pc-record_REPORT_<dd-mm-yy>.md` (written by the planner from the user's chat results). The `_REF_`/`_REPORT_` tokens keep `vc-audit-plans` (`validate-plan-inventory.mjs`) from flagging the runbook and record as misplaced plans; only `_REPORT_`, `_REF_`, `_SPEC_` names are exempt.

Sources: SPEC; `deploy/{_common,build-web,start-web,start-api,register-tasks}.ps1`, `config.example.psd1`, `README.md`; `api/tests/deploy/*` (all read); `process/general-plans/backlog/deploy-runtime-user-pc-verification_NOTE_02-10-26.md`, `gate5-deferred-candidates_NOTE_03-10-26.md`; master-planner.md sections 3-5, 8-9; `process/context/operating-instructions.md` (RT4); skill `vc-risk-evidence-pack` and its two validators; PVL reports of screener batch 1 and 2 (hidden-breaker patterns). Router: `process/context/all-context.md`; tests router `process/context/tests/all-tests.md`.

Context Envelope: general-plans | PLAN | R12 deploy fixes | claude/pensive-albattani-ou0cgv | /home/user/psychic-train | tests | deploy/, api/tests/deploy/ | this file | pytest (deploy shape tests), vitest, tsc, islands, playwright | contract PENDING (skeleton below).

## Overview

Goal: after any `web/` change, restart procedures cannot leave an old process or an old build serving, and a failed start is loud (non-zero exit plus a log line). Non-goals: Task Scheduler registration (`register-tasks.ps1`, separate decision), `start-api.ps1`, any `web/**` change, a new HTTP route, config keys, rewording the operator-only name-based `Stop-Process` lines of the README (migration step M0, Rollback; Q5).

## Name check against the SPEC and the real files (read 09-10-26)

| SPEC / brief says | Actual | Plan consequence |
|---|---|---|
| "poll the configured URL for HTTP 200" | `start-web.ps1` binds `next start -H <Tailscale ip>`; nothing listens on 127.0.0.1, so a loopback URL cannot answer | the URL is `http://<ip>:<WebPort>/`, the PC's OWN Tailscale address; the packet never leaves the machine (D7, Q4) |
| "after start, poll" | `start-web.ps1` runs `& pnpm ... next start` in the FOREGROUND (line 28); nothing after it runs until the server exits | `next start` becomes a child (`Start-Process -PassThru -NoNewWindow`) so the poll can run beside it (D6) |
| "confirm the served build id equals the marker" | `web/**` has no build-id route or file (grep of `BUILD_ID`/`buildId` in `web/app`, `web/lib`, `web/e2e`: none); `next.config.mjs` has only `reactStrictMode` | a static marker the build script drops into the served build output (D4), plus an HTML fallback check (D7) |
| "recorded commit differs from `git rev-parse HEAD`" | local `main` had 70 commits in 14 days: 20 nightly bot commits touching only `api/data/cache/**`, 8 touching `web/`; Stage A pulls on every API start | a strict HEAD compare refuses the web start after about 62 of 70 commits with no web change: Q1 |
| "stale = built output older than newest tracked web source" | `next build` and `build:islands` (output `web/public/islands/`, gitignored) rewrite files during the build; `next-env.d.ts` and `tsconfig.json` are tracked under `web/` | the marker is written LAST, after the build; strict `>` compare on epoch seconds (D5) |
| README lines ~104-105 (T18) | verified: lines 104-105 name `cache.write_confirmed_boundaries` / `read_confirmed_boundaries`; the functions are gone from `api/` (grep) | reword; the only existing assertion that pins the old text is `test_readme_migration_says_legs_cache_is_not_needed` (one edit, below) |
| "never kill by process name" | README M0 (line 155) and Rollback (line 269) tell the OPERATOR to run `Get-Process uvicorn,node \| Stop-Process` | scripts never do it (shape test); README lines left as is (Q5) |
| "bounded loops and timeouts" | the foreground wait on the web server is by design unbounded (it is the service) | stated in D6; every poll and wait is deadline-bounded |
| "no network beyond localhost" | `Get-NetTCPConnection` is local; the smoke request goes to the PC's own Tailscale IPv4 | shape test: no literal remote host in any script |
| "`pwsh` in the sandbox" | `command -v pwsh powershell`: nothing found (09-10-26) | CI and the sandbox check TEXT only; parse and run are PC steps |

## Decisions locked for this task

- **D1 One task, three sequential worker sessions on one branch, no subagents, commits C1-C4 plus docs commits.** W1 (opus) = C1 port-scoped stop (`_common.ps1`, call sites in `build-web.ps1` and `start-web.ps1`), README lines 104-105 reword, tests 1-6, then C2 build marker and stale-build guard, tests 7-11. W2 (opus) = C3 child process plus smoke check, README guard section and exit-code table, tests 12-17, then the final full gates. W3 (sonnet, documents and JSON only) = C4 PC runbook, record template, evidence pack, report, PR. Why split: the union of the three sessions' plan ranges is 39,477 B, far above the about 22,500 B one session can read (36,000 minus CLAUDE.md 13,443, before the envelope); each session checks out the branch holding the earlier commits. Each commit passes its own deploy gates; C3 can be reverted alone if the PC run shows the restructure misbehaves.
- **D2 Port stop.** `Get-WebPortListenerIds` = unique `OwningProcess` of `Get-NetTCPConnection -State Listen -LocalPort <WebPort> -ErrorAction SilentlyContinue` inside `try { } catch { }` (under the global `$ErrorActionPreference = 'Stop'` a no-match call throws on a FREE port); empty or `$null` = port free; only an exception (cmdlet missing, CIM failure) is a failure. `Stop-WebPortListener -Config <c> [-ReportOnly]`: validate `[int]$Config.WebPort` in 1..65535 and different from `ApiPort` (else log and `exit 2`); no listener: log `Port <p>: nothing listening; nothing to stop.`; otherwise for each id: refuse and `exit 5` when the id is 4 or less (System/Idle) or equals `$PID` (this script); log `Port <p>: stopping PID <id> (<name>) listening on it.` (name from `Get-Process -Id $listenerId -ErrorAction SilentlyContinue`, else `(unknown)`; log only); stop with `Stop-Process -Id <id> -ErrorAction Stop` (no `-Name`, no `taskkill`, no `-Force`); on error, unless a re-check with `Get-Process -Id <id> -ErrorAction SilentlyContinue` finds the process already gone (counts as stopped, go on to the wait), `Port <p>: could not stop PID <id>: <message>.` and `exit 5`; then wait at most 10 s (0.5 s steps, `$deadline`) for the port to clear, else `Port <p>: still in use after 10s; not continuing.` and `exit 5`. If `Get-NetTCPConnection` itself throws: fail closed, log, `exit 5`. Order in `build-web.ps1`: config, Tailscale wait, dry-run block, THEN stop, THEN remove marker, THEN build. Order in `start-web.ps1`: config, Tailscale wait, `$webArgs`, dry-run block, stale check (D5), THEN stop, THEN start (a refused start leaves the running server untouched).
- **D3 Dry run is report-only.** With `-DryRun` both scripts keep their current lines and exit 0, and add read-only lines using `Write-Host` (no log file write, nothing stopped, no marker written): `DRY RUN: port <p> is free; nothing would be stopped.` or `DRY RUN: would stop PID <id> (<name>) listening on port <p> (nothing stopped).`; `start-web.ps1 -DryRun` also prints `DRY RUN: <the stale-check result line>` and still exits 0 even when the build is stale. In `-ReportOnly` a protected PID prints `DRY RUN: would refuse to stop PID <id> (protected)` and a throwing `Get-NetTCPConnection` prints `DRY RUN: cannot list listeners: <message>`; neither exits.
- **D4 Marker.** Path `Join-Path $Config.RepoRoot 'web\.next\static\build-marker.json'` (`Get-WebBuildMarkerPath -Config`; `BUILD_ID` likewise absolute, because the stale check runs before the script's `Set-Location`): inside the build output (every `next build` clears it, `.gitignore` already ignores `web/.next/`), and served by `next start` at `/_next/static/build-marker.json`. Written by `Write-WebBuildMarker` only when the build exited 0, as the LAST step; removed by `Remove-WebBuildMarker` before the build starts (a failed or running build leaves no marker, so `start-web.ps1` refuses); guarded with `Test-Path -LiteralPath` (no-op when absent: a missing file would throw under the global `Stop`, and PC-8 is a first build with no marker). UTF-8 without BOM (`New-Object System.Text.UTF8Encoding($false)`). Fields: `schema` 1, `commit` (`git rev-parse HEAD`), `web_tree` (`git rev-parse HEAD:web`), `dirty` (true when `git status --porcelain -- web` prints anything), `build_id` (trimmed `web\.next\BUILD_ID`), `built_at_epoch` (UTC seconds, integer, floored, taken in `Write-WebBuildMarker` after the build and before any git read), `built_at_utc` (`yyyy-MM-ddTHH:mm:ssZ`, informational, never parsed: PowerShell 5.1 `ConvertFrom-Json` turns date strings into local DateTime). No API URL, no Tailscale address, nothing secret. Every git call is `git -C $Config.RepoRoot ...` in `try/catch` with `$LASTEXITCODE` checked, never `2>&1` (in 5.1 under `Stop` stderr text becomes a terminating error). Missing `BUILD_ID`, a failed git read or a failed write: log and `exit 7`. After the write log `Build marker written: commit <7> web tree <7> build id <id>`.
- **D5 Stale rule, first failing check wins, in this order** (`Test-WebBuildFresh -Config <c> [-ReportOnly]`; failure logs `Stale build: <reason>. Run deploy\build-web.ps1, then start again.` and `exit 4`; with `-ReportOnly` it prints `DRY RUN: ...` and returns): (1) marker file missing: `no build marker`; (2) unreadable JSON or a missing field: `build marker unreadable`; (3) `web\.next\BUILD_ID` missing or different from `build_id`: `build output missing or differs from the marker`; (4) git unreadable (`git` missing, `rev-parse` fails): `cannot read git state`; (5) `git rev-parse HEAD:web` differs from `web_tree`: `web/ sources changed since the build (built tree <7>, current <7>)`; (6) the newest write time among files listed by `git -C $Config.RepoRoot -c core.quotepath=off ls-files -- web` (each path joined to `RepoRoot` before `[System.IO.File]::GetLastWriteTimeUtc`; missing files skipped), as integer UTC epoch seconds via `[int64][Math]::Floor(...)`, is strictly `-gt` `built_at_epoch` (also floored; NTFS times have 100 ns resolution, so unfloored values refuse a fresh build): `tracked web file newer than the build: <relative path>`; (7) HEAD versus `commit` (Q1 B, resolved): log `Note: HEAD <7> differs from the build commit <7>; web/ is unchanged.` and pass; never refuse on this check. Pass logs `Build is current: commit <7> web tree <7> build id <id>`. A `dirty` marker adds `Note: built from uncommitted web/ changes.`
- **D6 Child process.** After the stale check and the port stop, `start-web.ps1` logs `Starting web on <ip>:<port>` and runs `Start-Process -FilePath $config.PnpmPath -ArgumentList $webArgs -WorkingDirectory $config.RepoRoot -NoNewWindow -PassThru`, then `$null = $proc.Handle` (caches the exit code). Smoke ok: `$proc.WaitForExit()`, log `Web process exited with code <n>`, `exit` with that code (1 when null). Smoke failed: log, `Stop-WebPortListener` (cleans the node grandchild), `Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue`, `exit 6`. The wait for the server to end is unbounded by design (it is the service, as `& pnpm` was). This deliberately departs from the brief's bounded-loops wording; the user is shown it at the diff check (P-R12-1).
- **D7 Smoke check.** `Invoke-WebSmokeCheck -Config <c> -Ip <ip> -Process <proc> -TimeoutSeconds <n>`: default 90 s; `start-web.ps1 -SmokeTimeoutSeconds <5..600>` overrides (0 = default; other values `exit 2` with a message); poll every 2 s with `Invoke-WebRequest -UseBasicParsing -TimeoutSec 5` against `http://<ip>:<WebPort>/` where `<ip>` is the script's own Tailscale address (the root page `web/app/page.tsx` has no fetch or async code, verified, so the check does not depend on the API being up at logon); stop early with `web process exited with code <n> before answering` when `$proc.HasExited`. On HTTP 200: no marker file -> pass with `Smoke check ok: <url> returned 200 (no build marker, build id not checked).`; else evidence A = GET `/_next/static/build-marker.json`, JSON `build_id` equals the marker's; evidence B = the root HTML contains the marker's `build_id`; either passes and the log says which: `Smoke check ok: <url> returned 200 and build id <id> matches the marker (evidence: marker-file|html).` Deadline passed: `Smoke check FAILED: <last reason> after <n>s.` (reasons: `no answer`, `HTTP <code>`, `served build id does not match the marker`) and return false. A is deterministic but relies on `next start` serving that file (U3); B relies on the app-router HTML carrying the build id (U4); the PC run decides which holds, either is enough. 5.1 notes: `Invoke-WebRequest` throws a `WebException` for any non-200, so the call sits in `try/catch` and reads `$_.Exception.Response.StatusCode` only after checking `Response` exists (StrictMode errors on an absent property); it honours a system proxy, so 'the packet stays on the machine' assumes none (true on the home PC).
- **D8 Exit codes.** 2 config (existing, plus bad `WebPort`/`-SmokeTimeoutSeconds`), 3 Tailscale timeout (existing), 4 stale or missing build, 5 port not freed or protected PID, 6 smoke failed, 7 marker could not be written. A build failure keeps pnpm's own code.
- **D9 No config change.** No new required key, `config.example.psd1` and every user `deploy.psd1` stay valid; defaults live in `_common.ps1`.
- **D10 PowerShell 5.1 rules** (the PC runs Windows PowerShell 5.1, the task action calls `powershell.exe`): ASCII only in the three changed `.ps1` files; no `&&`, `||`, ternary, `2>&1` on git, `??`, `ConvertFrom-Json -AsHashtable`, `Get-Process -Name`; never assign `$pid`, `$host`, `$args`, `$input`, `$error`, `$matches` (read-only or automatic: use `$listenerId`, `$ip`); wrap results in `@()` (StrictMode); no apostrophe inside a double-quoted string, no `#` inside any string, and balanced brackets inside strings (the shape tests strip `#` and count quotes and brackets); in `start-web.ps1` no `-H` substring (`Write-Host`, `-Host`, `-Headers`) before the `$webArgs` line (see Hidden breakers).
- **D11 Verification order (resolved, Q3 A).** Worker PR (no merge) -> vc-tester confirmation -> user reads the diff -> user runs the PC runbook ON THE BRANCH with the planner assisting in chat -> record -> user merges. Why: Stage A (`git pull --ff-only` at every API start) would deploy unverified launchers from `main` to the PC at the next logon.
- **D12 Evidence pack** under `harness/` (validator `validate-risk-artifacts.mjs`, real schema below); the PC record becomes `verification.json` `manualChecks` and `review-decision.json`.
- **D13 The worker never merges, pushes only its own branch, and stops at `review`.** A diff touching `deploy/` always stops at `review`; RT4 needs the user's PC record before `accepted`.

## Questions (RESOLVED by the user 09-10-26)

All five answered and the brief confirmed on 09-10-26; the user runs the PC verification with the planner's step-by-step help in chat. Nothing is open.

| # | Question | Resolution |
|---|---|---|
| Q1 | Meaning of "recorded commit differs from HEAD" (nightly bot commits and Stage A pulls move HEAD without touching `web/`) | B: refuse on a changed `web/` tree or a tracked web file newer than the build; HEAD-only movement logs a note and starts (D5 check 7) |
| Q2 | No marker after merge | A: refuse with exit 4 until one `build-web.ps1` run |
| Q3 | Order of verification and merge | A: PC run on the PR branch, then merge |
| Q4 | Smoke URL is the PC's own Tailscale address | A: accepted (packets stay on the machine) |
| Q5 | README M0 and Rollback name-based `uvicorn,node` lines | A: leave as operator text |

## Gate conventions

1. Every pytest gate runs with `UV_FROZEN=1`. Snapshot rule: `git diff --name-only --diff-filter=MDR origin/main...HEAD | grep -E '/fixtures/'` prints nothing.
2. Baselines at origin/main (each worker re-records at spawn; given by the brief for `270f9ac`, process-only since): pytest 951 passed, 2 skipped, 5 deselected, 0 xfailed; vitest 251 passed in 34 files; tsc exit 0; islands exit 0. Measured by the planner 09-10-26: `api/tests/deploy` 51 passed, 1 skipped; `test_deploy_config_shape.py` 24 tests. Slice counts are arithmetic from these; a worker stops at `needs_input` when an observed count differs.
3. Red-first per commit: write that commit's tests as stubs (`raise NotImplementedError("NOT IMPLEMENTED - TDD stub: <behaviour>")`), run the commit's first gate on the untouched state, record the red run in report heading 6, then write the real tests.
4. Hidden-break rule: an existing test may be edited only as listed in "Existing tests that assert text we change"; any other failing existing test stops the worker at `needs_input`.
5. The seeded E2E runs once, at the end, as the whole suite: `cd web && SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e` (no `--`, no spec filter). CI does not run Playwright. The diff touches no `web/` file, so a failure is first classified by name; record counts, stop at `needs_input` on any failure.
6. Bash gates must not name `.next`, `node_modules` or `.venv`: the scout hook blocks such commands. Text assertions about the marker path live in pytest, not in Bash greps.
7. Workers branch from `main`; this plan, the SPEC and the envelope must be on `main` first. Branch `claude/r12-deploy-fixes`. W2 and W3 check out the existing branch (it holds the earlier commits and reports). Every worker pushes only that branch; only W3 opens the PR; no worker merges or pushes `main`. Max 2 fix cycles per failing gate; the same failure twice stops the worker. No needs_input or blocker may be open when a worker reports DONE.
8. `git diff --check origin/main...HEAD` exits 0 and the added lines are ASCII (commands below). Scans G-R12-9..12 read the COMMITTED diff (origin/main...HEAD; an uncommitted file is invisible to them): run them AFTER the commit they cover and note the SHA; on a hit fix in a new commit and rescan. LF line endings.
9. PowerShell cannot run in the sandbox (`pwsh` absent): no worker claims a script "works". Known-Gap is a residual (backlog stub `deploy-runtime-user-pc-verification_NOTE_02-10-26.md` exists), never a PASS: every runtime criterion stays CONDITIONAL until the user's PC record.

## Sequencing and parallelism

Strictly sequential, three sessions: W1 (C1 then C2), then W2 (C3), then W3 (C4); each starts only after the previous one reported DONE and pushed (C2 reads helpers from C1, C3 reads the marker from C2, C4 quotes the log strings of the final code). No parallel lane: all code files are shared (`_common.ps1`, `start-web.ps1`, `build-web.ps1`, `README.md`). R12 overlaps no other open task (T18, T19 merged or file-disjoint). S10 (scheduled task) waits on R12.

## Program budget and costs [estimate]

Programme ceiling now 60 USD (spent 34.73, 25.27 left); 15 USD per slice cap not at risk.

| Session | Model | Cost | Basis |
|---|---|---|---|
| W1 | opus | 1.0-1.8 | 2 commits, 11 tests, deploy-dir gates only, about 50 tool calls |
| W2 | opus | 1.0-1.8 | 1 commit, 6 tests, 1 full pytest, vitest, tsc, islands, e2e |
| W3 | sonnet | 0.3-0.6 | 3 documents and 4 JSON files, scans, PR |
| EVL tester | sonnet | 0.5-1 | independent re-run of the changed-path gates |
| Total | | 2.8-5.2 (planned 3-5) | the brief's single-worker 2-4 USD does not fit the read cap |

Re-check before the spawn; stop and ask above 15 USD.

## The slice: R12 (RT4, three sequential worker sessions, no subagents)

**Goal:** the three behaviours of the confirmed brief exist as script text, are covered by shape tests, are documented, and the user has a runbook that proves them on the PC.

**Owned (exact):** `deploy/_common.ps1`, `deploy/build-web.ps1`, `deploy/start-web.ps1`, `deploy/README.md`, `api/tests/deploy/test_deploy_config_shape.py`, new `api/tests/deploy/test_deploy_r12_guards_shape.py`, in this task folder `r12-deploy-fixes-pc-runbook_REF_<dd-mm-yy>.md`, `r12-deploy-fixes-pc-record-template_REF_<dd-mm-yy>.md`, `r12-deploy-fixes-w{1,2,3}_REPORT_<dd-mm-yy>.md` (one per session), `harness/{risk-gate,context-snippets,verification,adversarial-validation}.json` (`verification.json` is created by W1 with its `commands` entries, extended by W2, completed by W3).
**Forbidden:** `deploy/register-tasks.ps1`, `deploy/start-api.ps1`, `deploy/config.example.psd1`, `api/data/**`, `api/scripts/**`, `web/**`, `.github/**`, `CLAUDE.md`, `AGENTS.md`, root `README.md`, `.claude/**`, `process/MASTER-PLAN.md`, `process/context/**`, validators, `harness/review-decision.json` (the user's decision, written by the planner).

**Hidden breakers in the existing tests (all verified by reading the tests; keep them green):**
1. `test_start_web_uses_next_start_not_dev_and_binds_variable`: takes the FIRST `-H` in the comment-stripped code of `start-web.ps1` and requires the next token to start with `$`. Any earlier `-H` text (`Write-Host`, `-Host`, `-Headers`, `Get-Help`) before the `$webArgs` line breaks it. Keep `$webArgs` as the first code line after the Tailscale wait; new `Write-Host` lines go after it; helpers live in `_common.ps1`. It also forbids `next dev` in code.
2. `test_stage_a_is_ff_only_and_non_fatal` scans EVERY `.ps1` (comments included, lower-cased) for `--force`, `reset --hard`, `stash`, `rebase`, `merge`: no such word in any new comment or string ("merged", "stashed" too; substrings count: "emerge" contains `merge`).
3. `test_scheduled_scripts_never_run_stage_b_or_no_history_jobs`: none of `refresh_cache`, `compute_pairs`, `backfill_primaries`, `backfill_pairs_universe`, `snapshot_narrative`, `snapshot_liqtide`, `snapshot_chain_growth` in any `.ps1`.
4. `test_no_funnel_or_public_exposure_anywhere` and `test_no_deploy_script_binds_all_interfaces`: no `funnel`, `ngrok`, `cloudflared`, `port forward`, `exit node`, `advertise-routes`, `0.0.0.0` in any script; the same words in README only on a line that prohibits them (new README lines: avoid them).
5. `test_ip_wait_is_bounded_and_cgnat_only`: `_common.ps1` keeps `MaxWaitSeconds`, `100.64.0.0/10`, `-4` and an `exit <1-9>`.
6. `test_readme_*` migration tests slice the README from `## Moving to a different PC` to the next `\n## `: the new guard section must be a separate `## ` section AFTER "Building the web app: the rebuild rule" (never inside the migration section, never a row `| M<n> |`); `test_readme_pins_required_operator_facts` needs the phrases it already finds.
7. `Stop-Process`/`$pid` traps in D10; the scout hook trap (Gate convention 6).

**Existing tests that assert text we change (exact allowed edits):** exactly ONE.

| Test (`test_deploy_config_shape.py`) | Why it breaks | Allowed edit |
|---|---|---|
| `test_readme_migration_says_legs_cache_is_not_needed` | asserts `"write_confirmed_boundaries" in section` (README lines 104-105 name the removed functions) | keep the `api\data\cache\legs` assert and the `dead weight` assert; replace the `write_confirmed_boundaries` assert by `assert "write_confirmed_boundaries" not in section and "read_confirmed_boundaries" not in section, "the removed helpers must not be named"` and `assert "has been removed" in section`; README lines 104-105 become: "`api\data\cache\legs\`. Nothing reads it, and the code that wrote it has been removed, so an existing folder is leftover data. Skip it." Wrap the first line after `so an`: the phrase `has been removed` must sit on ONE line (the test searches the raw text). |

No other existing test changes; the other 23 tests in that file and the rest of `api/tests/deploy` must pass unedited (24 and 51+1 skipped at the start).

**New tests (file `api/tests/deploy/test_deploy_r12_guards_shape.py`, 17, text-shape only; helpers `_read`, `_code_lines` copied locally, no import from the other test module):**

| # | Commit | Test | Asserts (tokens are text, searched in the stated file) |
|---|---|---|---|
| 1 | C1 | `test_common_selects_listener_by_port_never_by_name` | `_common.ps1` has `Get-NetTCPConnection`, `-State Listen`, `-LocalPort`, `Stop-Process -Id`, `-ErrorAction SilentlyContinue`; no `.ps1` code line has `Stop-Process -Name`, `taskkill`, `Get-Process -Name`, `-Force` after Stop-Process, or `Get-Process` not followed by `-Id` |
| 2 | C1 | `test_stop_helper_protects_system_pids_and_is_bounded` | `$listenerId -le 4`, `$PID`, `exit 5`, a `$deadline` plus `Start-Sleep` inside the extracted body of `function Stop-WebPortListener` (`Wait-TailscaleIPv4` has the same tokens), `-ErrorAction Stop`; no `foreach ($pid`, no assignment to `$pid`/`$host`/`$args`/`$input` (case-insensitive) in any `.ps1` |
| 3 | C1 | `test_build_web_stops_port_listener_before_build_and_dry_run_is_report_only` | `Stop-WebPortListener` exactly twice: first with `-ReportOnly` before the dry-run `exit 0`, second (real) after that `exit 0` and before `& $config.PnpmPath @buildArgs`; dry-run block has no `Remove-WebBuildMarker` |
| 4 | C1 | `test_start_web_stops_port_listener_before_bind_and_dry_run_is_report_only` | same shape in `start-web.ps1`: the first `Stop-WebPortListener` call carries `-ReportOnly` and precedes the dry-run `exit 0`; the second (real) follows that `exit 0` and, once C3 adds `Start-Process`, precedes it; a third call (smoke cleanup, C3) is allowed after `Start-Process` |
| 5 | C1 | `test_changed_ps1_files_are_ascii_only` | `_common.ps1`, `build-web.ps1`, `start-web.ps1`: `text.isascii()` |
| 6 | C1 | `test_changed_ps1_files_have_balanced_brackets_and_quotes` | in the comment-stripped code of those three files: counts of `{`/`}`, `(`/`)`, `[`/`]` equal; `"` count even; `'` count even (base files pass today: measured) |
| 7 | C2 | `test_build_web_clears_marker_before_build_and_writes_it_only_after_success` | `Remove-WebBuildMarker` before `& $config.PnpmPath @buildArgs`; `Write-WebBuildMarker` after it and inside an `if` on `$code -eq 0`; `exit $code` kept |
| 8 | C2 | `test_marker_records_commit_web_tree_build_id_and_time_without_bom` | `_common.ps1` has `build-marker.json`, `static`, `BUILD_ID`, `rev-parse`, `HEAD:web`, `commit`, `web_tree`, `build_id`, `built_at_epoch`, `UTF8Encoding($false)`, `exit 7`, `Test-Path -LiteralPath` |
| 9 | C2 | `test_start_web_refuses_stale_or_missing_build_with_exit_4` | in `start-web.ps1` the first `Test-WebBuildFresh` call WITHOUT `-ReportOnly` precedes the first `Stop-WebPortListener` call WITHOUT `-ReportOnly`; `_common.ps1` has `Stale build:`, `exit 4`, `build-web.ps1` in the message |
| 10 | C2 | `test_stale_check_covers_web_tree_and_newest_tracked_source_mtime` | `_common.ps1` has `ls-files`, `GetLastWriteTimeUtc`, `-gt $marker.built_at_epoch` (or equivalent `built_at_epoch`), `HEAD:web`, `no build marker`, `git -C`, `RepoRoot`, `Floor` |
| 11 | C2 | `test_stale_check_is_report_only_in_dry_run` | `start-web.ps1` dry-run block calls `Test-WebBuildFresh ... -ReportOnly` before its `exit 0`; `_common.ps1` `-ReportOnly` branch has no `exit 4` |
| 12 | C3 | `test_start_web_runs_next_as_child_with_exit_code_passthrough` | `Start-Process`, `-PassThru`, `-NoNewWindow`, `$proc.WaitForExit()`, `$proc.ExitCode`; the old foreground `& $config.PnpmPath @webArgs` is gone; `exit 6` |
| 13 | C3 | `test_smoke_check_is_bounded_and_polls_own_tailscale_address_only` | `_common.ps1`: `Invoke-WebRequest`, `-UseBasicParsing`, `-TimeoutSec`, `$deadline`, `Start-Sleep -Seconds 2`, `.HasExited`, `StatusCode -eq 200`; URL built from `$Ip` and `WebPort`; no `localhost`/`127.0.0.1` literal needed |
| 14 | C3 | `test_smoke_compares_served_build_id_with_marker_and_exits_6_on_failure` | `_next/static/build-marker.json`, `build_id`, `evidence`, `Smoke check FAILED:`, `Smoke check ok:`; `start-web.ps1` calls `Invoke-WebSmokeCheck` before `WaitForExit` and `-SmokeTimeoutSeconds` is a param |
| 15 | C3 | `test_start_web_dry_run_prints_and_exits_before_any_start_or_stop` | in `start-web.ps1` the strings `DRY RUN (nothing started)` and the first `exit 0` come before `Start-Process`; no real `Stop-WebPortListener` (without `-ReportOnly`) before that `exit 0` |
| 16 | C3 | `test_readme_documents_r12_guards_exit_codes_and_restart_procedure` | README has the heading `## Restarting safely after a web change (R12 guards)` after `## Building the web app: the rebuild rule` and before `## Starting it automatically`; inside it: `Stop-ScheduledTask mysite-web`, `build-web.ps1`, `Start-ScheduledTask mysite-web`, `build-marker.json`, `-SmokeTimeoutSeconds`, exit codes `4`, `5`, `6`, `7`, and the warning not to run `start-web.ps1` by hand while the task runs |
| 17 | C3 | `test_no_credentials_or_literal_remote_hosts_in_deploy_scripts` | in the code lines of all `.ps1`: no `Authorization`, `Bearer`, `Credential`, `SecureString`, `password` (case-insensitive); every `http(s)://` is followed by `$` |

Counts: C1 +6, C2 +5, C3 +6 = 17 new tests; pytest 951 -> 957 -> 962 -> 968; `api/tests/deploy` 51 passed + 1 skipped -> 57 -> 62 -> 68 passed.

**README work (C1 and C3).** C1: lines 104-105 per the table above. C3: a new section `## Restarting safely after a web change (R12 guards)` between "Building the web app: the rebuild rule" and "Starting it automatically": (a) the supported procedure `Stop-ScheduledTask mysite-web`, `git pull --ff-only`, `deploy\build-web.ps1`, `Start-ScheduledTask mysite-web`, then read `%LOCALAPPDATA%\my_site\logs\web.log` for `Smoke check ok`; (b) what each guard does in one sentence (port-scoped stop, marker and stale refusal, smoke check) with the log lines of D2/D5/D7; (c) the exit-code table (D8); (d) the marker file and its URL; (e) a warning: run `start-web.ps1` by hand only while the `mysite-web` task is stopped (a killed server makes the old script exit non-zero and Task Scheduler restarts it a minute later, which would stop the new server); (f) the first start after this change needs one rebuild (no marker yet). Also: the two "What this is" rows for `start-web.ps1` and `build-web.ps1` mention the guards; the rebuild-rule bullet "If a `git pull` changes anything under `web\`" ends with "`start-web.ps1` now refuses a stale build (exit 4)". Added-line rules (NET, credential and ASCII scans cover README added lines through the `-- deploy` pathspec): URLs only as `http://<ip>:...` or `http://${ip}:...` (never `http://100.x`); never the words Authorization, Bearer, Credential, SecureString, password, tskey, apikey; ASCII only (no em dash or arrow); no `0.0.0.0`, `funnel`, `port forward`, `exit node`.

**PC runbook (C4, W3 deliverable) `r12-deploy-fixes-pc-runbook_REF_<dd-mm-yy>.md`.** The worker writes it from this skeleton, using the final log strings of the code (a mismatch with the shipped strings is a bug). Header: frontmatter, TL;DR, who runs what (user in Windows PowerShell 5.1, not pwsh and not admin; planner assists in chat), a Stop-and-ask list (any unexpected listener owner, any step failing twice), expected total time about 45 minutes (two builds). Every step has: command(s), expected output, a "Paste back" line and an "If it fails / abort" line. Above PC-1 sits an 'Abort and restore (safe at any point)' block: close any decoy window (Enter in it); `Rename-Item web\.next\server.off server` if `web\.next\server.off` exists; `git switch main`; if a build was interrupted run `deploy\build-web.ps1` once from `main` (old behaviour) and only THEN `Start-ScheduledTask mysite-web` and `Start-ScheduledTask mysite-api` (an old launcher started on a half-built output exits non-zero and Task Scheduler burns its 3 retries); nothing outside `web\.next`, the branch checkout and the two task states is ever changed. ASCII only: no typographic dashes, quotes or arrows in any document or JSON the worker writes (the ASCII scan covers all added lines). Render each step as a heading plus a fenced code block for the commands (never table cells: pipes and quotes copy badly); the table below is the skeleton, not the layout. `<RepoRoot>` and `$ip` as in PC-1.

| Step | Do (commands) | Expect | Paste back |
|---|---|---|---|
| PC-1 | `cd <RepoRoot>`; `$ts = "C:\Program Files\Tailscale\tailscale.exe"`; `$ip = (& $ts ip -4 \| Select-Object -First 1).Trim()`; `$ip`; `$PSVersionTable.PSVersion.ToString()`; `git status --short` | `100.x.y.z`; `5.1.x`; status empty or untracked only | the three outputs |
| PC-2 | `Stop-ScheduledTask mysite-web -ErrorAction SilentlyContinue`; `Stop-ScheduledTask mysite-api -ErrorAction SilentlyContinue`; `Start-Sleep -Seconds 3`; `Get-NetTCPConnection -State Listen -LocalPort 3000,8000 -ErrorAction SilentlyContinue \| Select-Object LocalAddress,LocalPort,OwningProcess` | no rows (a row = a leftover listener: paste it and stop) | output |
| PC-3 | `git fetch origin`; `git switch claude/r12-deploy-fixes`; `git log -1 --format="%H %s"`; `git rev-parse HEAD:deploy` | head SHA equals the SHA the planner gives | both lines |
| PC-4 | the README B5 parse command | five lines (`_common`, `build-web`, `register-tasks`, `start-api`, `start-web`), each `0 errors` | output |
| PC-5 | `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-web.ps1 -DryRun; "exit=$LASTEXITCODE"`; the same for `build-web.ps1 -DryRun` and `start-api.ps1 -DryRun` | the old lines plus `DRY RUN: port 3000 is free; nothing would be stopped.`; start-web also `DRY RUN: Stale build: no build marker...`; every `exit=0`; start-api unchanged | output |
| PC-6 | `powershell ... deploy\start-web.ps1; "exit=$LASTEXITCODE"` | `Stale build: no build marker`, `exit=4`, nothing listening on 3000 | output |
| PC-7 | window 2: `$ip = (& "C:\Program Files\Tailscale\tailscale.exe" ip -4 \| Select-Object -First 1).Trim(); $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Parse($ip), 3000); $l.Start(); "decoy PID=$PID"; Read-Host "leave this window open"`. Window 1: `Get-NetTCPConnection -State Listen -LocalPort 3000 \| Select-Object LocalAddress,LocalPort,OwningProcess`, then `start-web.ps1 -DryRun` | decoy PID listed; dry run says `DRY RUN: would stop PID <decoy PID> (powershell) listening on port 3000 (nothing stopped).`; `Get-Process -Id <decoy PID>` still answers | both outputs, decoy PID |
| PC-8 | window 1: `build-web.ps1; "exit=$LASTEXITCODE"` (minutes); then `Get-Process -Id <decoy PID> -ErrorAction SilentlyContinue`; `Get-Content "$env:LOCALAPPDATA\my_site\logs\build-web.log" -Tail 8` | log has `Port 3000: stopping PID <decoy PID> (powershell) listening on it.`, `Web build exited with code 0`, `Build marker written: commit ...`; `exit=0`; the decoy window is gone | log tail and exit |
| PC-9 | `Get-Content web\.next\static\build-marker.json`; `git rev-parse HEAD`; `git rev-parse HEAD:web`; `Get-Content web\.next\BUILD_ID` | `commit` = HEAD, `web_tree` = HEAD:web, `build_id` = BUILD_ID | output |
| PC-10 | window 2: `powershell ... deploy\start-web.ps1` (stays running). Window 1: `(Invoke-WebRequest "http://${ip}:3000/" -UseBasicParsing).StatusCode`; `(Invoke-WebRequest "http://${ip}:3000/_next/static/build-marker.json" -UseBasicParsing).Content` | window 2 shows `Build is current`, `Starting web on`, `Smoke check ok: ... (evidence: marker-file)` or `(evidence: html)`; 200; the marker JSON equals PC-9 | window 2 text, both outputs |
| PC-11 | stop window 2 with Ctrl+C (answer Y to `Terminate batch job (Y/N)?`); list port 3000 (PC-2 command); then replay the incident: start the PC-7 decoy again (window 3), run `start-web.ps1` in window 2 | `Port 3000: stopping PID <decoy PID>` then `Smoke check ok` | text and listing |
| PC-12 | Ctrl+C window 2; `(Get-Item web\app\page.tsx).LastWriteTime = Get-Date`; `start-web.ps1; "exit=$LASTEXITCODE"` | `Stale build: tracked web file newer than the build: web/app/page.tsx`, `exit=4`, nothing started | output |
| PC-13 | `build-web.ps1; "exit=$LASTEXITCODE"` (restores a fresh build) | `exit=0`, new marker | tail of the log |
| PC-14 | `Rename-Item web\.next\server server.off`; `start-web.ps1 -SmokeTimeoutSeconds 10; "exit=$LASTEXITCODE"`; port 3000 listing; `Rename-Item web\.next\server.off server` | `Smoke check FAILED: ...`, `exit=6`, no listener left | output |
| PC-15 | `Start-ScheduledTask mysite-web`; `Start-Sleep -Seconds 45`; `Get-Content "$env:LOCALAPPDATA\my_site\logs\web.log" -Tail 6`; `Stop-ScheduledTask mysite-web`; `Start-Sleep -Seconds 5`; port 3000 listing; `Start-ScheduledTask mysite-web` | `Smoke check ok` in the log; after the stop no listener (a surviving listener: paste its PID, the next start stops it); task running again | outputs |
| PC-16 | `git switch main`; `Start-ScheduledTask mysite-api`; `git status --short`; fill the record template | clean tree, both services up | final lines |

Per-step abort lines: PC-1 to PC-6: nothing was started or changed beyond the branch and task states; paste the output and stop. PC-7: close the decoy window with Enter, or `Stop-Process -Id <decoy PID>`. PC-8 to PC-13: Ctrl+C the window (answer Y at `Terminate batch job (Y/N)?`; N or closing the window can leave `node` listening: list port 3000 with the PC-2 command, the next start stops a leftover), then run the Abort and restore block. PC-12: the touched `web\app\page.tsx` makes every later start on the branch refuse with exit 4; run `deploy\build-web.ps1` (PC-13) before any start. PC-14: if you stopped after the rename, run `Rename-Item web\.next\server.off server`, or rebuild with `deploy\build-web.ps1`. PC-15 and PC-16: run the Abort and restore block.

PC-7 note for the runbook: if Windows Firewall shows a prompt for the decoy, choose Cancel (a local bind is enough). **Record template (C4, W3 deliverable) `r12-deploy-fixes-pc-record-template_REF_<dd-mm-yy>.md`** (the filled copy is `r12-deploy-fixes-pc-record_REPORT_<dd-mm-yy>.md`, written by the planner from the user's chat results): date and time local and UTC; PC name (no address); PowerShell version; Windows version (`[System.Environment]::OSVersion.VersionString`); branch head SHA and `git rev-parse HEAD:deploy` tree (a merge changes the SHA, never the `deploy/` tree: the post-merge check compares trees); build id of the tested build; a table PC-1..PC-16 with PASS / FAIL / SKIP and one line each plus the pasted log lines; the evidence kind seen at PC-10 (`marker-file` or `html`); incidents or deviations; overall verdict APPROVE / APPROVE WITH CONCERNS / REJECT with one sentence; the user's name and date; post-merge line: `git rev-parse origin/main:deploy` equals the tested tree (yes/no). Mapping: any FAIL -> `rejected` and R12 returns to `in_progress`; SKIP of PC-11, PC-14 or PC-15 -> `approved-with-concerns` at best.

**Evidence pack (`harness/`, C4, W3; `verification.json` `commands` already holds the W1 and W2 runs).** The skill text and the shipped validator disagree; the validator `.claude/skills/vc-risk-evidence-pack/scripts/validate-risk-artifacts.mjs` is authoritative (its sibling `validate-evidence-pack.mjs` wants `APPROVE|REJECT` and the same five names: record the conflict in the report, do not edit validators). Required fields: `risk-gate.json` {task, planPath, riskLevel `high`, riskClasses [`deploy/runtime`], mustStopBeforeFinalize true, humanApprovalRequired true, why}; `context-snippets.json` {task, snippets[{file, lines, description, content}]} citing `_common.ps1` Tailscale wait, the changed regions of `start-web.ps1` and `build-web.ps1` with their FINAL line numbers on the branch head (not the base lines 16-28 / 23-31), the reworded README lines and the 17 test names; `verification.json` {task, commands[{command, result, utc, sha}], manualChecks[{id PC-1..PC-16, result `pending-user`}], result `CONDITIONAL`}; `adversarial-validation.json` {scenarios[{scenario, ruled_out, rationale}]} covering at least: wrong process on the port, system PID, self PID, port reused by another user's process, decoy that survives Stop-Process, port listing that fails silently (reads as port free; the smoke check exit 6 path still catches the clash), stale marker surviving a rebuild, marker from a failed build, first start with no marker, restart loop between an old script instance and a new one, smoke false positive from a stale process, smoke request leaving the machine, secrets in the marker or logs. `review-decision.json` {task, decision, blockingFindings, nonBlockingFindings, notes} is NOT written by the worker: the validator reports exactly one failure (`review-decision.json missing or invalid JSON object`) until the planner writes it from the user's record (`approved` | `approved-with-concerns` | `rejected`).

**Design notes for the three highest-risk steps (scenarios folded into the contract):** (1) Stop by port: dual-stack sockets list the same PID twice (unique), a listener owned by another user fails `Stop-Process` (exit 5, never a retry loop), System PID 4 owns kernel listeners (refused), a decoy of the same process family as the task (`powershell.exe`) is stopped only because it is the listener. (2) Child process: `.cmd` through `Start-Process` returns the `cmd.exe` PID, the real listener is its `node` grandchild (hence port-based cleanup), `ExitCode` can be `$null` without the cached handle (hence `$null = $proc.Handle` and a `1` default), an early crash is caught by `HasExited` instead of waiting out the deadline. (3) Stale guard: a git pull that moves only HEAD must not refuse (Q1 B), a `git switch` rewrites only differing files (mtime), a build that edits `next-env.d.ts` still precedes the marker, git absent under Task Scheduler fails closed with a clear reason (the Stage A pull already assumes `git` on PATH; U6).

## Later work (not in this plan)

S10 (optional scheduled task) waits on R12. `register-tasks.ps1` stays as is. A PowerShell parser in CI (for example a Windows runner) is a Test Infra note, not part of this slice.

## Touchpoints

Changed: `deploy/_common.ps1` (7 new functions), `deploy/build-web.ps1`, `deploy/start-web.ps1`, `deploy/README.md`, `api/tests/deploy/test_deploy_config_shape.py` (one assertion), new `api/tests/deploy/test_deploy_r12_guards_shape.py`; task-folder deliverables and `harness/`. Read only: `deploy/start-api.ps1`, `register-tasks.ps1`, `config.example.psd1`, `api/tests/deploy/conftest.py`, `.gitignore`, `.github/workflows/ci.yml`, `web/package.json`, `web/next.config.mjs`.

## Public Contracts

- Script parameters: `-DryRun` unchanged on both scripts; new `start-web.ps1 -SmokeTimeoutSeconds <int>` (0 = default 90, else 5..600).
- Exit codes: D8. Log lines: D2, D5, D7 (the runbook and README quote them).
- New HTTP-visible file: `GET /_next/static/build-marker.json` on the tailnet-only web port (commit SHA, tree SHA, build id, build time: non-secret; the repo is public).
- Unchanged: ports, bind address (Tailscale IPv4 only), `deploy.psd1` keys, Task Scheduler tasks, the API.
- Security scan (STRIDE, quick): no auth, key or secret surface. Spoofing/tampering: a local user can edit the marker (local trust boundary, not a security boundary). Denial: killing the wrong process is the main risk (selection by port only, protected PIDs, current-user rights, no elevation); restart loops are bounded by Task Scheduler (3 retries, 1 minute). Information disclosure: marker content is non-secret. Elevation: none.

## Blast Radius

Six owned code and doc files (`_common.ps1`, `build-web.ps1`, `start-web.ps1`, `README.md`, two test files) plus five task-folder documents (runbook, record template, three session reports) and four `harness/` JSON files (15 touches, 18 with the three planner envelope files); RT4 high-risk deploy/runtime class; CI cannot run the scripts; runtime effect limited to the user's PC web service. Rollback: revert the PR (C3 alone, then C2, then C1 if needed); a PC left on the branch: `git switch main`.

## Acceptance Criteria

Table in the Validate Contract skeleton below (id, behaviour, strategy, proving test, gap-resolution, SPEC link). SPEC links: AC-R12-1 = change 1; AC-R12-2 = change 2; AC-R12-3 = change 3; AC-R12-4 = acceptance line 1 and hard constraints; AC-R12-5 = acceptance line 2; AC-R12-6 = "existing shape tests stay green"; AC-R12-7 = DryRun constraint; AC-R12-8 = T18 reword (ownership); AC-R12-9 = acceptance line 3 (the user's record).

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G-R12-1 new shape tests (17) | Fully-Automated (text only) | changes 1-3 as script text; hard constraints (AC-R12-1..4, AC-R12-7) |
| G-R12-2 existing shape file (24) | Fully-Automated | existing shape tests stay green; T18 reword (AC-R12-6, AC-R12-8) |
| G-R12-3, G-R12-4 deploy dir and full pytest | Fully-Automated | no regression (AC-R12-6) |
| G-R12-5..7 vitest, tsc, islands | Fully-Automated | RT3 floor unchanged |
| G-R12-8 whole E2E | Hybrid (NOT-RUN with reason allowed) | RT4 floor, no web regression |
| G-R12-9..12 scope, secret, network, ASCII scans, `diff --check` | Fully-Automated | ownership, no secrets, no network beyond the PC, bounded text (AC-R12-4) |
| G-R12-13 evidence pack validator | Fully-Automated | RT4 evidence pack (one expected failure until the user's record) |
| PC-5..PC-16 (user runbook) | Hybrid (precondition: Windows PowerShell 5.1 PC with Tailscale; runner: user) | changes 1-3 at runtime, DryRun, Task Scheduler interplay (AC-R12-1..3, AC-R12-7, AC-R12-9) |
| P-R12-1 diff check by the user | Agent-Probe (human read) | control-file rule for `deploy/`; the user is also shown D6's deliberate unbounded `WaitForExit` |

## Risk Predictions (condensed 5-persona pass)

Security: no secret or auth surface; the kill is port-scoped with protected PIDs. Performance: one `git ls-files` plus about 140 stat calls per start. Data integrity: no data touched (caches, watchlist, `api/data/**` untouched). User: the first start after the change needs one rebuild (Q2); a refused start leaves the old server running (check before stop). Operations: the biggest unknown is the child-process restructure under Task Scheduler (U5, U7): C3 is revertable alone and PC-15 tests it. Maintainability: 17 text tests pin the contract; they prove text, not behaviour (see "What this coverage does NOT prove").

## Implementation Checklist (atomic; sessions W1, W2, W3)

W1 (opus): 1 Baseline: `git fetch`, record origin/main SHA, run `UV_FROZEN=1 uv run --project api pytest api/tests/deploy -q` (expect 51 passed, 1 skipped); `command -v pwsh` (expect nothing); branch `claude/r12-deploy-fixes` from `main`.
2 C1 stubs: create `test_deploy_r12_guards_shape.py` with tests 1-6 as stubs; run G-R12-1, record the red run (6 failed).
3 C1 code: `_common.ps1` `Get-WebPortListenerIds`, `Stop-WebPortListener`; `build-web.ps1` and `start-web.ps1` call sites (D2, D3, order in D2); reword README lines 104-105; edit the one existing assertion; write tests 1-6 for real.
4 C1 gates: G-R12-1 (6 passed), G-R12-2 (24), G-R12-3 (57 passed, 1 skipped); commit C1; then scans G-R12-9..12 on the committed head (note the SHA).
5 C2 stubs for tests 7-11, red run (5 failed, 6 pass).
6 C2 code: `Get-WebBuildMarkerPath`, `Remove-WebBuildMarker`, `Write-WebBuildMarker`, `Test-WebBuildFresh` (D4, D5, Q1 answer in the envelope); `build-web.ps1` marker calls; `start-web.ps1` stale check before the stop, report-only in the dry-run block; tests 7-11.
7 C2 gates: G-R12-1 (11 passed), G-R12-2, G-R12-3 (62 passed, 1 skipped); commit C2; then scans G-R12-9..12. Create `harness/verification.json` with the `commands` of steps 1-7; write report `r12-deploy-fixes-w1_REPORT_<dd-mm-yy>.md` (11 headings); commit both as a docs commit; rescan G-R12-9 and G-R12-11; push the branch; reply `DONE` (no PR).
W2 (opus): 8 Check out `claude/r12-deploy-fixes`; confirm HEAD holds C1 and C2 and G-R12-3 shows 62 passed; C3 stubs for tests 12-17, red run (6 failed, 11 pass).
9 C3 code: `Invoke-WebSmokeCheck`; `start-web.ps1` child process, `-SmokeTimeoutSeconds`, exit 6 (D6, D7); README section and row edits; tests 12-17.
10 C3 gates, final and once after the last edit (first `cd web && pnpm install --frozen-lockfile`, run unconditionally; it is idempotent): G-R12-1 (17), G-R12-2, G-R12-3 (68), G-R12-4 (968), G-R12-5..8; commit C3; then scans G-R12-9..12; extend `harness/verification.json` `commands`; report `r12-deploy-fixes-w2_REPORT_<dd-mm-yy>.md`; commit both as a docs commit; rescan G-R12-9 and G-R12-11; push the branch; reply `DONE` (no PR).
W3 (sonnet): 11 Check out the branch. Write the PC runbook and the record template from the skeleton, quoting the log strings found in `_common.ps1` and `start-web.ps1` (a string that differs from the plan is reported in heading 8, the code wins).
12 Write `harness/{risk-gate,context-snippets,adversarial-validation}.json`, complete `verification.json` (`manualChecks` PC-1..PC-16 `pending-user`, `result` `CONDITIONAL`); gate G-R12-13; commit C4; then gates G-R12-9 (R12-scope), G-R12-10, G-R12-11 on the committed head.
13 Report `r12-deploy-fixes-w3_REPORT_<dd-mm-yy>.md` (11 headings; heading 9 requests the registry update to `review` and names the open PC record; heading 11 context cost); commit it as a docs commit; rescan G-R12-9..11 (after the docs commit, before the push and the PR); push; open the PR to `main`; do NOT merge; reply `DONE` or `needs_input`.

## Phase Completion Rules

`CODE DONE` = W3's PR open, all offline gates green in the three reports. `VERIFIED` only after (1) independent confirmation (a spawned vc-tester or CI on the head SHA), (2) the user's diff check, and (3) the user's PC record with verdict APPROVE (or APPROVE WITH CONCERNS accepted by the user). Until the record exists R12 stays `review` (master-planner.md section 5 item 5 and section 4(d)); a merged task that still needs the record stays `review` after the merge. A diff touching `deploy/` stops at `review`.

## Validate Contract

(skeleton by the planner 09-10-26, completed by vc-validate-agent in PVL cycle 5, 09-10-26; verdict record in iteration-005; the remaining contract fields sit after the Failing stubs paragraph below)
supersedes: none
Status: PASS (re-VALIDATE, PVL cycle 5; 0 FAIL, 0 CONCERN)
Gate: PASS
generated-by: outer-pvl

### Test gates

gap-resolution: A proven now / B added by this plan's checklist / C deferred to a named later step / D backlog stub (residual, keep CONDITIONAL).

| criterion id | behavior | strategy | proving test (proven by) | gap-resolution | SPEC link |
|---|---|---|---|---|---|
| AC-R12-1 | build-web and start-web stop only the port listener (by port, protected PIDs, bounded wait), log PID, do nothing when free | Fully-Automated (text) | G-R12-1 tests 1-4 | B | change 1 |
| AC-R12-1r | the listener on the web port is really stopped, an unrelated process is not, nothing is stopped when free | Hybrid (user PC) | PC-2, PC-5, PC-7, PC-8, PC-11 | C (PC record); D `deploy-runtime-user-pc-verification_NOTE_02-10-26.md` | change 1 |
| AC-R12-2 | marker written last after a successful build; start-web refuses with exit 4 on missing marker, tree change, newer tracked file | Fully-Automated (text) | G-R12-1 tests 7-11 | B | change 2 |
| AC-R12-2r | a missing marker and a touched web file refuse; a fresh build starts | Hybrid (user PC) | PC-6, PC-9, PC-12, PC-13 | C | change 2 |
| AC-R12-3 | start-web runs next as a child, polls its own address for 200 and the build id, exit 6 plus log on failure, bounded | Fully-Automated (text) | G-R12-1 tests 12-14 | B | change 3 |
| AC-R12-3r | smoke ok on a good build, exit 6 and a clean port on a broken one, Task Scheduler start/stop leaves no listener | Hybrid (user PC) | PC-10, PC-14, PC-15 | C | change 3 |
| AC-R12-4 | no secrets, no remote host, ASCII, balanced brackets, bounded loops, no forbidden git words | Fully-Automated | G-R12-1 tests 5, 6, 13, 17; G-R12-9..12 | B | hard constraints |
| AC-R12-5 | README documents the three steps, exit codes, restart procedure, rebuild after this change | Fully-Automated (text) | G-R12-1 test 16 | B | acceptance 1-2 |
| AC-R12-6 | the 24 existing shape tests and the rest of `api/tests/deploy` stay green with exactly one edited assertion | Fully-Automated | G-R12-2, G-R12-3, G-R12-4 | A (after C1) | existing tests |
| AC-R12-7 | `-DryRun` of both scripts prints, kills nothing, exits 0 | Fully-Automated (text) + Hybrid | G-R12-1 tests 3, 4, 11, 15; PC-5, PC-7 | B, C | DryRun constraint |
| AC-R12-8 | README lines 104-105 no longer name the removed functions | Fully-Automated | G-R12-2 (`test_readme_migration_says_legs_cache_is_not_needed`) | B | ownership (T18) |
| AC-R12-9 | the user's PC record exists with a verdict | Hybrid (user) | the filled `r12-deploy-fixes-pc-record_REPORT_<dd-mm-yy>.md` | C (R12 stays `review` until then) | acceptance 3 |

### Exact gates (repo root; counts are arithmetic from the baselines)

| Gate | Command | Expected |
|---|---|---|
| G-R12-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/deploy/test_deploy_r12_guards_shape.py -q` | C1: 6 passed; C2: 11 passed; C3: 17 passed |
| G-R12-2 | `UV_FROZEN=1 uv run --project api pytest api/tests/deploy/test_deploy_config_shape.py -q` | 24 passed (every commit) |
| G-R12-3 | `UV_FROZEN=1 uv run --project api pytest api/tests/deploy -q` | C1: 57 passed; C2: 62; C3: 68; each 1 skipped |
| G-R12-4 | `UV_FROZEN=1 uv run --project api pytest api/ -q` (once, after C3) | 968 passed (951 + 17), 2 skipped, 5 deselected, 0 xfailed |
| G-R12-5 | `pnpm --filter web test` | 251 passed in 34 files |
| G-R12-6 | `pnpm --filter web exec tsc --noEmit --incremental false` | exit 0 |
| G-R12-7 | `cd web && pnpm build:islands` | exit 0 |
| G-R12-8 | hybrid, Gate convention 5 (whole suite) | all passed; NOT-RUN with a stated reason allowed; record the counts |
| G-R12-9 | `R12-scope`, `FORBIDDEN`, `FIXTURES` (command block) | print nothing |
| G-R12-10 | `S-secret-scan`, `PS-secret-scan`, `NET-scan` (command block) | print nothing |
| G-R12-11 | `ASCII-scan` and `git diff --check origin/main...HEAD` | print nothing / exit 0 |
| G-R12-12 | `command -v pwsh` | prints nothing (if it prints a path, the worker may additionally run a parse of the three files and record it as extra, never as the PS 5.1 proof) |
| G-R12-13 | `node .claude/skills/vc-risk-evidence-pack/scripts/validate-risk-artifacts.mjs process/general-plans/active/r12-deploy-fixes_03-10-26/harness` | exit 1 with exactly one failure: `review-decision.json missing or invalid JSON object` (expected until the user's record) |
| PC-* | the runbook | the user's record |

### Scope and secret-hygiene commands (run from the repo root AFTER the commit they cover: they read origin/main...HEAD; the labels above refer to these)

```
# FORBIDDEN: nothing may match
git diff --name-only origin/main...HEAD | grep -E '^(CLAUDE\.md|AGENTS\.md|README\.md|\.claude/|\.github/|web/|api/data/|api/scripts/|process/MASTER-PLAN\.md|process/context/|process/archive/|deploy/(register-tasks\.ps1|start-api\.ps1|config\.example\.psd1))'

# FIXTURES: nothing may match
git diff --name-only --diff-filter=MDR origin/main...HEAD | grep -E '/fixtures/'

# R12-scope: nothing may match (owned allowlist, including the planner's envelope files)
git diff --name-only origin/main...HEAD | grep -vE '^(deploy/(_common|build-web|start-web)\.ps1|deploy/README\.md|api/tests/deploy/(test_deploy_config_shape|test_deploy_r12_guards_shape)\.py|process/general-plans/active/r12-deploy-fixes_03-10-26/(r12-deploy-fixes-w[123]_(REPORT|REF)_[0-9-]+\.md|r12-deploy-fixes-pc-(runbook|record-template)_REF_[0-9-]+\.md|harness/(risk-gate|context-snippets|verification|adversarial-validation)\.json))$'

# S-secret-scan: nothing may match (added lines only)
git diff origin/main...HEAD | grep -nE "^\+.*(Bearer [A-Za-z0-9._-]{12,}|(API_KEY|SECRET|TOKEN|PASSWORD)[A-Z_]* *[:=] *[\"'][A-Za-z0-9+/_-]{12,})"

# PS-secret-scan: nothing may match (deploy added lines)
git diff -U0 origin/main...HEAD -- deploy | grep -niE '^\+.*(Authorization|Bearer |Credential|SecureString|password|tskey|apikey|api_key)'

# NET-scan: nothing may match (a URL in deploy added lines must start with $ or <)
git diff -U0 origin/main...HEAD -- deploy | grep -E '^\+' | grep -nE 'https?://' | grep -vE 'https?://(\$|<)'

# ASCII-scan: nothing may match (non-ASCII in any added line)
git diff -U0 origin/main...HEAD | grep -nP '^\+[^+].*[^\x00-\x7F]'
```

### Failing stubs

Each new test starts as `def test_x(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: <behaviour>")` in the commit that introduces it; the worker runs G-R12-1 on that state, records the red run in heading 6, then writes the real assertions. The edited legs assertion is red against the unedited README: write the new assertions first, run G-R12-2 (expect 1 failed), then reword the README.

### Validate contract completed (PVL cycle 5, outer-pvl)

Date: 09-10-26
date: 2026-10-09
(The header above carries generated-by outer-pvl and supersedes none: the earlier text was a skeleton, Status PENDING, not a completed contract.)

Parallel strategy: sequential
Rationale: 7-signal score 2/7 (S6 deploy/runtime high-risk class, S7 five or more files in the blast radius), dominant signal S6; the threshold alone would suggest parallel subagents, but the fit rule wins: all code files are shared (`_common.ps1`, `build-web.ps1`, `start-web.ps1`, `README.md`) and each session reads the commits of the previous one (D1), so the execution is three sequential worker sessions plus one EVL tester. Agent count: 3 workers (W1 opus, W2 opus, W3 sonnet) + 1 vc-tester (sonnet) = 4, no subagents; cost guard not triggered (estimate 3-5 USD against 25.27 USD left). This validation itself ran as one sequential read-only agent (no cross-talk needed).

Test gates: the 5-column table above is the contract (strategy values Fully-Automated | Hybrid | Agent-Probe only; Known-Gap is a named residual via gap-resolution D, never a strategy). Legacy line form:
- Port-scoped stop (change 1): [Fully-automated: G-R12-1 tests 1-4] | [hybrid: PC-2, PC-5, PC-7, PC-8, PC-11; precondition Windows PowerShell 5.1 PC with Tailscale, runner the user]
- Build marker and stale guard (change 2): [Fully-automated: G-R12-1 tests 7-11] | [hybrid: PC-6, PC-9, PC-12, PC-13]
- Child process and smoke check (change 3): [Fully-automated: G-R12-1 tests 12-14] | [hybrid: PC-10, PC-14, PC-15]
- Dry run and regression: [Fully-automated: G-R12-1 tests 3, 4, 11, 15; G-R12-2, G-R12-3, G-R12-4 (968)] | [hybrid: PC-5, PC-7] | RT3 floor G-R12-5..7 | [hybrid: G-R12-8 whole E2E, NOT-RUN with a reason allowed]
- Hard constraints: [Fully-automated: tests 5, 6, 13, 17; G-R12-9..12]; evidence pack G-R12-13 (one expected failure until the user's record)
- Diff check P-R12-1: [agent-probe: the user reads the deploy/ diff incl. D6's unbounded WaitForExit]
- [known-gap: documented] PowerShell parse and run, process stop, Task Scheduler, `next start` serving the marker and the HTML build id; residual stub `deploy-runtime-user-pc-verification_NOTE_02-10-26.md` (gap-resolution D), closed only by the user's PC record (AC-R12-9)
Failing stubs (Fully-Automated rows): each of the 17 tests starts as `def test_<name>(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: <behaviour>")` per the Failing stubs paragraph above and the red-first rule (Gate convention 3); the table of tests and their stub names is the plan section "New tests".

Dimension findings:
- Infra fit: PASS - paths, ports, PowerShell 5.1 rules, Set-Location ordering and the existing first -H parse verified against the real files at origin/main abda8e7
- Test coverage: PASS - N1 fixed (every scan follows the commit it covers; reproduced in a scratch repo); counts 951/957/962/968 and 51/57/62/68 reproduce; baseline re-run (51 passed, 1 skipped; full 951 passed, 2 skipped, 5 deselected); runtime criteria stay Hybrid with a named residual, not a vacuous green
- Breaking changes: PASS - one new non-secret static file, exit codes 4-7, one new parameter, one edited assertion; no contract of other consumers changes
- Security surface: PASS - no auth or secret surface; kill by port only with protected PIDs, no -Name/taskkill/-Force; marker non-secret
- Section C1 port stop: PASS - mechanically feasible; highest-risk edit the Get-NetTCPConnection no-match path (F1 folded)
- Section C2 marker and stale guard: PASS - absolute paths and git -C (F2), floored epoch compare (F3), Test-Path guard (A5)
- Section C3 child process and smoke check: PASS - highest-risk edit of the task (Start-Process restructure); revertable alone; PC-14, PC-15
- Section C4 runbook, record template, evidence pack: PASS - abort order (A3), validator expectation reproduced on a scratch pack

Open gaps: the user's PC record (AC-R12-9; R12 stays `review` until then); follow-up backlog line (marker does not record the baked API address); planner UPDATE PROCESS item (MASTER-PLAN lacks the 60 USD ceiling). Advisories B1-B5 of iteration-005 (W2 envelope: read D4/D5 strings from `_common.ps1` at the branch head; test 1 `-Force` check scoped to Stop-Process lines; planner refreshes line 11 and Resume lines 360-363 after this stamp). None blocks.
What This Coverage Does NOT Prove: see the section "What this coverage does NOT prove" below; in short, the 17 shape tests prove script TEXT and its order, not that any script parses, stops the right process, refuses a stale build or reports a failed start; the balance test catches truncation, not PowerShell syntax errors.
Accepted by: n/a - no CONCERN to accept (0 FAIL, 0 CONCERN); the runtime criteria are a named residual (AC-R12-1r, -2r, -3r, -9: hybrid, user PC), not accepted concerns.
Range-table check after this stamp: lines 1-313 changed only at 242, 244, 245, 246 (outside every envelope range); everything else was inserted after line 313; the range table at the end of the file (W1 20,024 / room 2,533, W2 19,168 / 3,389, W3 20,605 / 1,952) was recomputed from the saved file and is unchanged.

### Red-today evidence (origin/main abda8e7; read-only checks, nothing committed)

Change 1: `_common.ps1`, `build-web.ps1`, `start-web.ps1` contain no `Get-NetTCPConnection`, `Stop-Process` or `build-marker` (counts 0); `start-web.ps1` line 28 and `build-web.ps1` line 31 run pnpm in the foreground with no prior stop. Change 2: no marker is written anywhere; `start-web.ps1` has no freshness check. Change 3: `start-web.ps1` line 28 blocks until the server exits, so nothing can poll; no `Invoke-WebRequest` in any script. README: no R12 section; lines 104-105 name `write_confirmed_boundaries`. Not run: any PowerShell (none in the sandbox); the full pytest suite (given by the brief: 951/2/5/0).

### Unverified facts: owner and deterministic fallback

| # | Fact | Status | Owner | Fallback |
|---|---|---|---|---|
| U1 | `pwsh`/`powershell` in the sandbox | verified absent 09-10-26 | worker re-checks (G-R12-12) | text tests, balance test, PC parse step PC-4 |
| U2 | `Get-NetTCPConnection` lists the listener, `Stop-Process -Id` stops it, under PS 5.1 and non-elevated | unverifiable offline | PC-2, PC-7, PC-8 | fail closed with exit 5; replace by `netstat -ano` parsing in a follow-up |
| U3 | `next start` 15.0.3 serves a file added to the build's static folder at `/_next/static/build-marker.json` | unverifiable offline (scout hook blocks `node_modules`; no build run) | PC-10 | evidence B (HTML contains the build id) already accepted; else follow-up |
| U4 | the app-router HTML of this build embeds the build id string | unverifiable offline | PC-10 | evidence A; if both fail the smoke check fails loudly and a follow-up fixes it |
| U5 | `Stop-ScheduledTask` ends the child `node` too | unverifiable offline | PC-15 | the port stop at the next start; the finding goes in the record |
| U6 | `git` resolves under Task Scheduler (Stage A already assumes it) | unverifiable offline | PC-15 (`web.log`), B12 `api.log` | stale check fails closed with `cannot read git state` |
| U7 | `Start-Process -PassThru` then `WaitForExit()` yields `ExitCode` | unverifiable offline | PC-14, PC-15 | default exit 1 when null |
| U8 | `ConvertFrom-Json`, `[DateTimeOffset]` casts behave as assumed on 5.1 | unverifiable offline | PC-9, PC-10 | epoch integer avoids the date quirk |
| U9 | the two evidence validators disagree on the decision vocabulary | verified by reading both | planner (this plan) | `validate-risk-artifacts.mjs` is authoritative |
| U10 | `next-env.d.ts` / `tsconfig.json` rewritten by the build precede the marker | by construction | PC-13 then PC-10 | strict `>` compare |

### Not verifiable offline

Everything PowerShell: parse, run, port discovery, process stop, Start-Process behaviour, Task Scheduler, Tailscale address binding, `next start` serving the marker, the HTML build id, Windows file times.

### What this coverage does NOT prove

- The 17 shape tests prove that certain TEXT is present and ordered, NOT that any script parses, stops the right process, refuses a stale build or reports a failed start. All runtime criteria stay CONDITIONAL until the user's PC record.
- The balance test catches a truncated edit, NOT a PowerShell syntax error in balanced text.
- A smoke check served from a file on disk cannot tell a stale process from a fresh one; the design avoids the case by stopping the port holder first and by watching `HasExited`.
- The decoy in PC-7 and PC-11 stands in for the old process of the 2026-10-01 incident; it proves the stop mechanism, not that Next 15.0.3 holds the port the same way.

### Open gaps

Q1-Q5 resolved (09-10-26). The user's PC record (AC-R12-9). Follow-up backlog line (not this slice): the marker does not record the baked API address, so a changed Tailscale IP with an unchanged `web/` tree is not detected (the README rebuild rule is the control). For the planner's UPDATE PROCESS: `process/MASTER-PLAN.md` lacks the 60 USD programme ceiling (P4 still says 45); this plan does not edit it. Test Infra: a Windows CI runner with a PowerShell parse step. Backlog stub exists: `process/general-plans/backlog/deploy-runtime-user-pc-verification_NOTE_02-10-26.md`.

## Autonomous Goal Block

SESSION GOAL: R12 deploy fixes - port-scoped stop before build and start, stale-build guard via a build marker, post-start smoke check; three sequential worker sessions on one branch (W1 opus: C1 port stop then C2 marker and stale guard; W2 opus: C3 child process, smoke check, README section, final gates; W3 sonnet: C4 PC runbook, record template, evidence pack, PR); no worker merges; the task stops at review
Charter + umbrella plan: N/A - single plan (SPEC r12-deploy-fixes_SPEC_03-10-26.md; no umbrella plan with a Stable Program Goal)
Autonomy: validated PASS after 2 supplement cycles and 3 verdict passes (PVL cycles 1, 3, 5). EXECUTE needs the user's explicit "ENTER EXECUTE MODE". The planner then records registry blocked -> approved, writes the W1 envelope (master-planner.md section 8, at most 8,000 bytes, a pointer list citing the "Envelope line ranges" table; W1 room 2,533 B, drafted W1 envelope 2,157 B), saved as `r12-deploy-fixes-w{1,2,3}_REF_<dd-mm-yy>.md`, and spawns W1 only (opus, no subagents). W2 follows after W1 reported DONE and pushed, W3 after W2 (rooms 3,389 B and 1,952 B; drafted W3 envelope 1,714 B). Workers run gates once after the last edit, run the scans G-R12-9..12 AFTER the commit they cover, record red runs, and stop at needs_input when an observed count differs from the plan arithmetic or the same failure occurs twice. The user runs the PC runbook on the PR branch with the planner's help in chat.
Hard stop conditions / safety constraints:
- No envelope or worker before the user's "ENTER EXECUTE MODE".
- W2 only after W1 is done and pushed, W3 only after W2; the sessions are never parallel.
- A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/` stops at review; the `deploy/` diff always goes to the user for a diff check (P-R12-1, including D6's unbounded WaitForExit).
- No worker merges or pushes `main`; workers push only `claude/r12-deploy-fixes`; only W3 opens the PR.
- No run of deploy scripts outside tests (no PowerShell in the sandbox); no worker claims a script works.
- Push, merge, deploy, branch deletion, or spend above 15 USD per slice or 60 USD in total (about 25.27 USD left at plan time) needs the user's approval.
- The PC runbook PC-1..PC-16 is the user's and is never claimed by a worker; R12 stays at review until the user's record exists.
Next phase: EXECUTE: process/general-plans/active/r12-deploy-fixes_03-10-26/r12-deploy-fixes_PLAN_09-10-26.md
Validate contract: process/general-plans/active/r12-deploy-fixes_03-10-26/r12-deploy-fixes_PLAN_09-10-26.md (inline, validated PASS, PVL cycle 5)
Execute start: W1: `UV_FROZEN=1 uv run --project api pytest api/tests/deploy -q` baseline (51 passed, 1 skipped), then C1 stubs red run of `api/tests/deploy/test_deploy_r12_guards_shape.py` (G-R12-1, 6 failed), then C1 code and gates, then C2 | probes: PC-1..PC-16 on the user PC | high-risk pack: yes (harness/ written by W3; review-decision.json by the planner from the user's record)

## Worker envelope

Written by the planner AFTER VALIDATE passes, registry `approved` and the explicit "ENTER EXECUTE MODE" (Q1-Q5 and the brief are already resolved): three envelopes, one per session, each at most 8,000 bytes, a pointer list citing its row of the range table below, saved as `r12-deploy-fixes-w{1,2,3}_REF_<dd-mm-yy>.md`. W2's envelope is written after W1 reported DONE, W3's after W2 (committed by the planner on the branch or on `main` before the spawn; the R12-scope allowlist names the envelope files). Common fields: Task R12 (scans G-R12-9..12 run after the commit they cover, Gate convention 8); Branch `claude/r12-deploy-fixes`; operating-instructions.md not named; retry budget 2; Stop and report at `review` if any step would kill a process other than the one on the configured port, require a secret, change Task Scheduler registration, cannot be bounded in time, any count differs from the arithmetic, or any needs_input or blocker is open; Autonomy: edit owned files, commit on the branch, push the branch; never merge. Commits: C1-C4, plus the session report and `harness/verification.json` as a separate docs commit after the code commit and before the push (branch order C1, C2, docs, C3, docs, C4, docs). Shape of `harness/verification.json` (W1 creates, W2 extends, W3 completes; W1 and W2 fill `commands` only; validator keys `task`, `commands`, `manualChecks`, `result`): `{"task":"R12","commands":[{"command":"","result":"","utc":"","sha":""}],"manualChecks":[],"result":"CONDITIONAL"}`. W1: acceptance "C1 and C2 committed, gates G-R12-1..3 at 57 then 62 passed"; Q1 B and Q2 A copied verbatim. W2: acceptance "C3 committed, final gates green"; full-suite budget 2 runs. W3: model sonnet; acceptance "runbook, record template, evidence pack, PR open, stopped at review"; opens the PR.

## Test Infra Improvement Notes

(none identified yet) Candidates: a Windows CI job that parses every `deploy/*.ps1` with `System.Management.Automation.Language.Parser` (CI is ubuntu-only today); a tiny shared helper for the comment-stripping text assertions used by two test files; the two evidence-pack validators disagree on the decision words.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/r12-deploy-fixes_03-10-26/r12-deploy-fixes_PLAN_09-10-26.md`
2. Last completed step: PLAN 09-10-26; PVL cycle 1 CONDITIONAL (8 CONCERN), supplement cycle 1 folded F1-F8 and advisories a-h (report iteration-002); PVL cycle 3 CONDITIONAL (1 CONCERN N1, advisories A1-A8; report iteration-003); supplement cycle 2 folded N1 and A1-A7 (report iteration-004).
3. Validate-contract status: pending (skeleton above, Status PENDING, Gate PENDING); no PASS stamp and no goal block yet.
4. Context loaded: SPEC, `deploy/*`, `api/tests/deploy/*`, README, backlog notes, master-planner.md sections 3-5 and 8-9, operating-instructions.md RT rules, `vc-risk-evidence-pack` skill and validators, screener batch 1 and 2 plans and PVL reports, `web/package.json`, `web/next.config.mjs`, `ci.yml`, `.gitignore`.
5. Next step for a fresh agent: re-spawn VALIDATE from V1 (cheap checks: the N1 text, the byte math from the file, a scratch run of the scans before and after a commit, hunt new gate traps); on PASS the planner records registry `blocked` -> `approved` (Q1-Q5 and the brief are already resolved: no question step); only then, on "ENTER EXECUTE MODE", write the W1 envelope and spawn W1 (W2 and W3 follow one at a time). The PC verification is run by the user with the planner assisting in chat; fill the PC record, then `harness/review-decision.json`, then ask the user to merge; the planner records `accepted` only with the record and a green CI on the merge SHA, and checks `git rev-parse origin/main:deploy` equals the tested tree.

## Envelope line ranges (re-derive with `grep -n '^## \|^### '` at spawn time; worker cap 36,000 B = CLAUDE.md 13,443 counted once + envelope (cap 8,000) + plan bytes)

Same mechanism as the screener batches. Line numbers refer to this file as saved by supplement cycle 2; the table is the last block, so editing it moves no earlier line (re-derive with the grep above if any earlier line is edited). Each blank line inside a range counts one byte. A set = the decisions the session needs, the gate conventions it uses, the slice lines of its commits, its tests, its exact gates and the command block, plus its checklist lines; section headings, the goal line and the counts line are left out where the neighbouring lines already carry the content. A worker never needs: Name check, Questions (the planner copies the answers into the envelope), Sequencing, Costs, Touchpoints, Public Contracts, Blast Radius, Verification Evidence, Risks, Red-today evidence, Unverified facts, Resume.

| Session | Plan ranges (lines) | Plan bytes | Envelope room (cap 36,000) |
|---|---|---|---|
| W1 | 44-47, 52, 71-74, 76-79, 103-104, 106-113, 115-121, 123-137, 222-228, 269-273, 279-282, 288-309, 313 | 20,024 | 2,533 |
| W2 | 44, 48-50, 52, 71-79, 103-104, 106-113, 123-126, 138-143, 145, 147, 229-231, 250, 252-253, 258, 261, 269-282, 288-309, 313 | 19,168 | 3,389 |
| W3 | 44, 47-50, 77-79, 103, 149-174, 232-234, 269-270, 279-281, 283, 288-309 | 20,605 | 1,952 |

Computed as 36,000 - 13,443 (CLAUDE.md) - plan bytes; the union of the three sets is 39,617 B. W1: decisions D2-D5 and D10 (D1 omitted: the envelope states the session and the checklist the commits; exit codes 4, 5, 7 are stated inside D2, D4, D5); conventions 1-4 and 6-9 (not 5, the E2E); tests 1-11; checklist steps 1-7; gates G-R12-1..3 and 9..12. W2: decisions D2, D6-D8, D10 (D5 omitted: the stale check is C2 code already on the branch, W2 only leaves its call order untouched); all nine conventions; tests 12-17 with the README work; checklist steps 8-10; gates G-R12-1..12; criteria rows AC-R12-3 and AC-R12-5. W3: decisions D2, D5-D8 (the log strings the runbook quotes; D3 omitted: PC-5 in the skeleton carries the dry-run strings); conventions 7-9; the runbook, record template and evidence-pack lines; checklist steps 11-13; gates G-R12-9..11 and 13. Fit test with real drafts: W1 is the tight one. A full W1 draft with the Q1 B and Q2 A answers verbatim (about 330 B, not 150 B), the stop list, the commit rule and the `verification.json` shape is 2,157 B against room 2,533 (slack 376 B); W2 about 1,800 B against 3,389 (slack about 1,590 B); W3 about 1,714 B against 1,952 (slack 238 B). A drafted envelope must fit every room with some slack; if a draft leaves under about 100 B, trim prose inside that session's ranges, never the contract. The envelope cap of 8,000 B is not binding. Naming `operating-instructions.md` (6,678 B) would move the cap to 43,000 B; no session needs it. If an envelope would not fit, trim the envelope text, never the ranges.
