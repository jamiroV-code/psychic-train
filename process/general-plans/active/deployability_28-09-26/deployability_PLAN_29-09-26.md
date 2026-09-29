---
name: plan:deployability
description: "P2 Phase 1 — run my_site on the author's own Windows PC, reachable only over Tailscale; main.py CORS/docstring fix, deploy/ launchers + runbook, config-shape tests, and a user-PC walkthrough"
date: 29-09-26
feature: none
---

# Deployability (P2, Phase 1) — PLAN

**Date**: 29-09-26
**Complexity**: COMPLEX-bounded (one plan, one lane; container work is small, the risk is in the user-PC half)
**Status**: PLANNED — VALIDATED 29-09-26 (Gate: CONDITIONAL, see Validate Contract). `CODE DONE` (section A green in the container) is NOT `VERIFIED`; `VERIFIED` only after the user confirms the section B walkthrough.
**Branch**: `claude/p2-deploy` · **Locked SPEC**: `process/general-plans/active/deployability_28-09-26/deployability_SPEC_28-09-26.md`
**Selected plan file (the one EXECUTE anchors on)**: `process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md`

> **TL;DR** — Split in two. **(A) Container work**: fix the `api/main.py` docstring that would become false, tighten CORS (safe: the web client never sends credentials), add a `deploy/` folder of Windows PowerShell launchers + runbook, and add ~35 offline tests that pin all of it. **(B) User-PC work**: a 17-step PowerShell checklist (Tailscale, build, Task Scheduler, phone test, reboot and downtime drills). The API and web app bind to the PC's **Tailscale IPv4 only**, so nothing ever listens on the LAN or the internet. Auto-resume after downtime is **two-stage**: `git pull` (safe, enabled now) and the recompute jobs (stay manual until P1's atomic parquet writes exist — a named, checkable gate). Cost: ~$0/month. Nothing paid or public is created.

---

## Overview

Context router: `process/context/all-context.md`; testing context `process/context/tests/all-tests.md` (the `tests/` group has only that one file, so the routing chain is fully loaded — no deeper test docs exist); planning context `process/context/planning/all-planning.md`. Locked decisions are in the SPEC's `## Decision Recorded (29-09-26)` and `## Phase 1 Operating Assumption — Intermittent Availability`; they are not reopened here.

### Locked decisions (from the SPEC — do not reopen)

| Question | Answer |
|---|---|
| Hosting | The author's own PC (~$0/month, electricity only) — the same machine that already holds the gitignored `ohlcv/`, `liquidity/`, `pairs/`, `legs/` caches |
| Access gate | Tailscale, free personal tier |
| Always on? | **No.** Intermittently available; design for downtime |

Consequences already worked out in the SPEC: no public endpoint ever exists; volume sizing is moot; the cache split-brain does not apply to Phase 1 (nothing to move).

### Research findings established this session (ground truth — cited, not re-derived)

| # | Finding | Evidence | What it changes in this plan |
|---|---|---|---|
| F1 | **The user's PC is Windows** (timezone Europe/Brussels). | `process/features/cycle-regime/completed/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md:891-892` (`where uv`, absolute `uv.exe` path, Windows Task Scheduler, daily 03:00 Brussels); RFC-001/RFC-006 phase reports use `powershell` blocks; `regime-dashboard-rfc002-stage0_REPORT_24-09-26.md:37` ("Windows allows click-only control of terminals"). | Every user-run step is PowerShell / Task Scheduler. No systemd, no bash. A WSL2 / Docker Desktop variant is mentioned only as an **unverified, secondary** idea (D2). |
| F2 | **`NEXT_PUBLIC_API_BASE_URL` is inlined at BUILD time.** `web/lib/api/{screener,regime,narrative,onchain,pairs}.ts` each do `process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"`, and Next.js inlines `NEXT_PUBLIC_*` during `next build`. | grep of `web/lib/api/*.ts` (this session, 5 hits). | **Resolves SPEC §8's open question.** The value must be set BEFORE the web build; changing the API address needs a REBUILD, not a restart. Recorded as requirement REQ-UI-1 to `claude/ui-shell`. Nothing under `web/` is edited. |
| F3 | **`allow_credentials=True` in `api/main.py` is unnecessary.** No `credentials: "include"` exists anywhere in `web/`; fetches pass only `signal`. The web client never issues POST/DELETE either (grep of `web/lib`, `web/components`, `web/app` for `"POST"`/`DELETE`/`Content-Type` returns nothing, non-test). | Same greps, this session. | CORS can be tightened without touching the real client (D5). |
| F4 | **`SCREENER_CACHE_ROOT` (`api/data/cache.py:33`) and `SCREENER_WATCHLIST_PATH` (`api/data/watchlist.py:42`) are read at module import**, and nothing loads a `.env`. | Read of both files. | The launcher must put them in the process environment BEFORE Python starts. On the Phase 1 box the defaults are already correct (same PC, same repo), so overriding is optional — the runbook says which is which. |
| F5 | **P1's atomic-write fix is PLANNED, not implemented.** `origin/claude/p1-pipeline` commit `df2c3c9` adds only a plan. Named interface: `cache._atomic_to_parquet(df: pd.DataFrame, path: Path) -> None` (private helper in `api/data/cache.py`; `mkstemp` in the same directory, write, fsync, `os.replace`). SPEC Open Question 10 makes it a HARD PREREQUISITE of automatic resume. | `git show origin/claude/p1-pipeline:process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-atomic-writes_PLAN_29-09-26.md` (read this session). | Auto-resume is designed two-stage and gated (D7). The gate is a named, checkable precondition (G-STAGEB). |
| F6 | **P1 owns `api/scripts/BOOTSTRAP.md`** and has added two workflows (`pairs-refresh-snapshot.yml` 19:17 UTC, `liquidity-backfill-snapshot.yml` 19:47 UTC). | `git show origin/claude/p1-pipeline:api/scripts/BOOTSTRAP.md` (read this session). | This lane's runbook REFERENCES BOOTSTRAP.md for the recompute commands and does not duplicate it. The resume script is a requirement addressed to P1 (REQ-P1-2). |
| F7 | **All four screens already degrade honestly on an empty cache.** A read-only probe this session (real `api.main:app`, `SCREENER_CACHE_ROOT` and `SCREENER_WATCHLIST_PATH` pointed at a temp dir) returned 200 for `/api/health`, `/api/screener/board`, `/api/regime/components`, `/api/regime/legs`, `/api/pairs` (`computation_status: results_unavailable`), `/api/narrative/categories`, `/api/narrative/history`, `/api/watchlist`, `/api/onchain/chains`. | Probe output, this session. | AC3's automated half is expected to pass without any router change; no out-of-lane edit is needed for it. |

### CORRECTION applied — the "~2h late" scheduler figure is wrong

The SPEC's lineage and P1's workflow comments (and the docstring of `api/tests/scripts/test_snapshot_workflow_schedules.py`, "observed up to ~2h20m") repeat that GitHub starts scheduled runs about 2h late. The planning session **measured** it:

| Night (UTC date of the scheduled slot) | Observed start delay |
|---|---|
| 09-26 | 2h03m |
| 09-27 | 3h06m |
| 09-28 | 5h01m |

Last night's narrative run started 23:18:44Z and committed 23:19:22Z — **41 minutes before UTC midnight**. Narrative points are dated by the UTC day the run executes, so the existing 3h buffer (`SCHEDULER_DELAY_BUFFER_MIN = 180`) is no longer a safe margin, and the delay is trending up. Arithmetic on the current crons (inference, NOT observation): a 5h01m delay applied to `liqtide-snapshot.yml` (18:47 UTC) would start it about 23:48Z, roughly 12 minutes before midnight. Per `all-context.md` LiqTide is keyed by `generated_utc[:10]`, so its risk is lower than narrative's; onchain's keying was not checked. Nothing in THIS plan depends on the "~2h" number. The scheduling fix (`.github/workflows/`, the guard test's constant) is **P1's lane** — recorded as REQ-P1-3, not touched here.

---

## Phase Completion Rules

- `CODE DONE`: every section A checklist step is done and its gate is green in the container.
- `VERIFIED`: only after the user runs section B and confirms steps B8-B14 (reachability, negative reachability, reboot, downtime and watchlist-persistence checks). Until then the plan stays in `active/`, exactly like the AC-11 / AC-12 / AC-14 precedents (`regime-dashboard_PLAN_24-09-26.md` §Resume and Execution Handoff).
- Cross-lane criteria (AC9, AC10 script half, AC12, AC13) do not block this lane's `VERIFIED` but stay CONDITIONAL until their owners land them. This lane never claims them.
- The container cannot run PowerShell, Tailscale, Task Scheduler, a build on the user's machine, or any live provider call. Those are agent-probe (user-run) gates, never asserted as green by an agent.

## Acceptance Criteria

Every SPEC criterion is carried with its proving scenario and exactly one strategy tag (`Fully-Automated` | `Hybrid` | `Agent-Probe`; Known-Gap is never a strategy — it is the residual, recorded in the gap table below). Gate ids (G1...) are defined under Verification Evidence and back-reference the criterion.

| AC | Criterion (short) | Lane | Strategy | Proven by (scenario) | Exact command / step |
|---|---|---|---|---|---|
| AC1 | Docstring/config no longer claims a localhost-only bind; documented default CORS origin is `http://localhost:3000` | **in-lane** | Fully-Automated | `test_docstring_no_longer_claims_localhost_only_bind`, `test_docstring_states_tailscale_posture_and_run_command_concern`, `test_default_origin_is_localhost_3000_when_env_unset` (G1) | `uv run --project api pytest api/tests/deploy/test_main_cors.py -q` |
| AC2 | An allow-listed second origin is accepted; a non-listed origin is rejected | **in-lane** | Fully-Automated | `test_allowlisted_origin_preflight_accepted`, `test_non_allowlisted_origin_preflight_rejected`, `test_import_time_wiring_honors_env` (G1) | same file as AC1 |
| AC3 | A fresh copy with an empty cache tells the truth about which of the 4 screens have data | **in-lane** | Hybrid | Automated half: `test_empty_cache_all_screen_endpoints_never_500`, `test_empty_cache_pairs_reports_results_unavailable`, `test_empty_cache_regime_components_reports_no_points` (G3). Agent-Probe half: step B7b (real API against an empty cache dir on the PC) | `uv run --project api pytest api/tests/deploy/test_fresh_deploy_degrade.py -q -k empty` ; step B7b |
| AC4 | Watchlist edits survive a redeploy | **in-lane** | Hybrid | Automated half: `test_watchlist_env_override_is_honored_at_import`, `test_watchlist_add_round_trips_to_env_path`, `test_cache_root_env_override_is_honored_at_import` (G3). Agent-Probe half: step B14 (add a coin, restart tasks, coin remains) | `uv run --project api pytest api/tests/deploy/test_fresh_deploy_degrade.py -q -k "env or round_trips"` ; step B14 |
| AC5 | `GET /api/health` returns exactly `{"status": "ok"}` | **in-lane** | Fully-Automated | `test_health_returns_exact_status_ok_body` (G2) | `uv run --project api pytest api/tests/deploy/test_health_endpoint.py -q` |
| AC6 | One clear hosting recommendation with a real monthly cost | in-lane (decision doc) | Agent-Probe | SPEC + `## Decision Recorded (29-09-26)`; the user's own answers (home PC, ~$0). Satisfied by the recorded decision; no code. | Human review already given 29-09-26 |
| AC7 | One clear access-privacy recommendation and what it does/doesn't protect | in-lane (decision doc) | Agent-Probe | SPEC §7 + Decision Recorded (Tailscale). The runbook ("What Tailscale does and does not protect") restates it for the operator. | Human review of that runbook section at step B0 |
| AC8 | No infrastructure, account, or public endpoint created by this lane; nothing committed outside allowed touchpoints | **in-lane** | Fully-Automated | `test_lane_scope_only_allowed_paths` (branch-gated to `claude/p2-deploy`) + gate command G7 | `git diff --name-only $(git merge-base HEAD origin/main)` compared to the allowlist in Blast Radius |
| AC9 | A night when the PC is off loses no narrative/liqtide/onchain data (workflows pinned `runs-on: ubuntu-latest`) | **OUT-OF-LANE — P1** (`claude/p1-pipeline` owns `.github/workflows/` and the schedule guard test) | Fully-Automated | P1 extends the schedule guard. This lane's PC-side half: `test_scheduled_scripts_never_run_stage_b_or_no_history_jobs` (G4) proves the PC's scheduled scripts can never run the no-history snapshots. | P1: `uv run --project api pytest api/tests/scripts/test_snapshot_workflow_schedules.py -q` ; this lane: G4 |
| AC10 | After downtime, recovery is a short documented sequence, ideally one command | **SPLIT.** Resume script + its pytest = **P1** (REQ-P1-2). Stage A wrapper + docs + drill = **in-lane** | Hybrid | In-lane: stage A inside `deploy/start-api.ps1` (git pull `--ff-only`, non-fatal, bounded) + `test_stage_a_is_ff_only_and_non_fatal` (G4); Agent-Probe: step B13 real downtime drill | G4 ; step B13 |
| AC11 | While caches are behind, every screen shows an honest stale/unavailable state, never wrong numbers | **in-lane** (tests) | Hybrid | Automated: `test_aged_cache_regime_and_screener_never_500_and_no_nan` (G3, finding clause in checklist step 5). Agent-Probe: step B13 on the real PC after a real power-off | G3 ; step B13 |
| AC12 | An interrupted write never corrupts an existing cache file | **OUT-OF-LANE — P1** (`api/data/cache.py`) | Fully-Automated | P1's `api/tests/data/test_cache_atomic_writes.py`. **Unmet until P1 lands.** This lane only defines the gate that keeps stage B off until then (G-STAGEB). | P1: `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` |
| AC13 | The intermittent-availability assumption is recorded project-wide | **BLOCKED — not satisfiable by this lane.** `process/context/all-context.md` is four-way contended (MASTER-PLAN T8, after T23) and SPEC §7 forbids this lane editing it. | Fully-Automated | `grep` after T8 lands. The required entry is a ready-to-paste handoff block in `## Requirements Handed To Other Lanes` (REQ-CTX-1). | after T8: `grep -c "intermittent" process/context/all-context.md` returns 1 or more |

**Residual gaps recorded, not silently dropped.** Known-Gap is a named residual, never a proving strategy; each item below has its behavior covered by an Agent-Probe or a backlog stub, so no developed behavior is PASS-able on Known-Gap alone:

| Residual | Why it is not provable here | How it is handled |
|---|---|---|
| PowerShell syntax and runtime behavior of `deploy/*.ps1` | The container has no `pwsh`/`powershell` (`which pwsh powershell` printed nothing this session). | Text-shape pinning tests (G4) in-container; real parse + `-DryRun` on the PC (B5, B6); backlog stub "PowerShell parser gate in CI" recorded in the final REPORT. Gate stays CONDITIONAL until B5/B6 are confirmed by the user. |
| Tailscale behavior, Windows Firewall inbound behavior on the tailnet interface, Task Scheduler behavior, sleep/wake behavior | Needs the user's machine. | Agent-Probe steps B8-B15. Firewall is a contingent step (R1). |
| Real on-disk cache size | Only `Get-ChildItem` on the user's PC can produce it. | Step B3 (informational; moot for sizing on own hardware). |
| Vendor pricing | Moot — no vendor on this path. | Not applicable. |
| Whether the web build bakes the Tailscale URL on the user's machine | Needs the user's toolchain. | Step B7 verifies by searching the built bundle for the baked address. |
| Live-provider calls (FRED, DefiLlama, Google Trends, Reddit, CoinGecko, Hyperliquid) | This container's egress proxy blocks all of them. | Not tested here; nothing in this lane calls a provider. |

---

## Architecture Decisions (Final)

### D1 — Bind to the Tailscale IPv4 explicitly (chosen) vs `0.0.0.0` plus a Windows Firewall rule (fallback)

| | **Chosen: bind to `100.x.y.z` (Tailscale IPv4)** | Fallback: bind `0.0.0.0` + Firewall rule |
|---|---|---|
| What listens where | The socket exists only on the Tailscale interface. LAN, Wi-Fi and WAN interfaces have no listener at all. | Listener exists on every interface; safety depends entirely on a rule being present, correct, and scoped. |
| Load-bearing control | The bind address itself (kernel-enforced, provable with `netstat -ano`). | A firewall rule the user must create and keep correct; Windows may also offer to auto-create a broad "allow on Private networks" rule at first run (known Windows prompt behavior, unverified here) that silently widens exposure. |
| Failure mode | Tailscale not yet up at boot means the bind fails. | Everything binds fine; a wrong or missing rule exposes the LAN. |
| Mitigation | Bounded wait-and-retry loop for the IP (`MaxWaitSeconds`, default 300, poll 5s), then a clear log line and non-zero exit; Task Scheduler restarts up to 3 times, 1 minute apart. | Scope the rule with `-RemoteAddress 100.64.0.0/10` and the Tailscale interface alias. |
| Provable? | Yes, by observation: `netstat -ano \| findstr :8000` shows only `100.x.y.z:8000` (step B10). | Only by testing from a LAN device and hoping the rule is right. |

**Decision: bind to the Tailscale IPv4.** It is strictly stronger (no listener on any other interface, so no firewall rule is load-bearing for privacy), at the price of a boot-ordering dependency that a bounded wait handles. **Rejected for Phase 1: `0.0.0.0` + firewall.** It stays documented in the runbook as a fallback only, with the scoped rule text, and no `deploy/*.ps1` file may contain `0.0.0.0` (pinned by test G4).

Residual: Windows Defender Firewall may STILL block inbound tailnet traffic to a Tailscale-bound socket. Whether it does on this machine is unverified. Step B9 detects it; the contingent fix is a rule scoped to `-RemoteAddress 100.64.0.0/10 -InterfaceAlias Tailscale -LocalPort 8000,3000 -Protocol TCP` — which does not open the LAN.

### D2 — How the services start: Task Scheduler "At log on" as the current user (chosen)

Rejected: **SYSTEM account "At startup"** (uv/pnpm/node/Tailscale live in the user profile; SYSTEM has a different PATH and home, and running the app as SYSTEM is a needless privilege — mirrors the house rule of absolute `uv.exe` paths because Task Scheduler ignores shell PATH); **NSSM / a Windows service** (third-party install, unverified here, more surface than a personal tool needs); **Docker Desktop / WSL2 variant** (mentioned only as an unverified secondary idea: WSL2 networking, Windows-filesystem access speed to the existing caches, and Tailscale-in-WSL binding are all unchecked, and the caches are already on the Windows filesystem). Consequence stated plainly: after a reboot with no user logon, the app is down. That matches "intermittently available" and is acceptable.

Settings chosen: trigger At log on (current user), run only when the user is logged on, no highest privileges, restart on failure 3 times at 1-minute intervals, no execution time limit, start when available, allowed on battery. The exact cmdlet parameter names come from repo-external knowledge and could not be confirmed with `vc-docs-seeker` in this session; EXECUTE writes them and steps B5/B11 on the PC confirm them (`Get-Help New-ScheduledTaskSettingsSet -Parameter *` is the fallback if a parameter name is rejected).

### D3 — Web production serve: `next build` + `next start -H <tailscale-ip> -p 3000` (chosen)

Rejected: `next dev` (HMR websocket and dev overlay exposed to the tailnet, slower, meant for one developer). The exact flag spelling (`-H`/`--hostname`, `-p`/`--port`) is confirmed by EXECUTE step 2 (`pnpm --filter web exec next start --help`) if `web/node_modules` can be installed in the container, else it stays an agent-probe at step B8.

### D4 — Two ports on the tailnet IP (chosen) vs a same-origin proxy (rejected FOR THIS LANE, proposed to ui-shell)

Phase 1 keeps the browser talking to two origins (`http://100.x:3000` page, `http://100.x:8000` API), which is why CORS must allow the web origin. A Next.js rewrite of `/api/*` to `127.0.0.1:8000` would let the API stay bound to loopback only, drop CORS from the picture, and remove the build-time URL problem (F2). That is strictly better, but it edits `web/` (owned by `claude/ui-shell`). Recorded as REQ-UI-2, not implemented; the plan works without it.

### D5 — CORS tightening (in `api/main.py`)

- `allow_credentials` becomes `False` (F3: no credentialed fetch exists).
- `allow_methods` becomes the explicit list the API actually serves: `GET`, `POST`, `DELETE` (the watchlist router serves POST/DELETE; every other route is GET). `OPTIONS` need not be listed — Starlette answers preflight itself.
- `allow_headers` becomes `["Content-Type"]` (the only header a JSON write would add; the web client currently sends none).
- `SCREENER_CORS_ORIGINS` stays the ONLY lever. No new environment variable, no new config plumbing (SPEC constraint).
- Behavior preserved exactly: env unset gives `["http://localhost:3000"]`; env set to an empty string gives an empty list (deny all — current behavior, pinned by a test so it cannot drift silently); entries are stripped and blanks dropped. Trailing slashes are NOT normalized (a browser `Origin` never has one; the launcher builds origins without one).
- Rejected: keeping `["*"]` (needless breadth once the API is on a tailnet); `allow_origin_regex` (a pattern is harder to reason about than an exact list); auto-adding origins in Python (the launcher, not the app, knows the Tailscale IP).

To make the parse testable without re-importing the app, `main.py` gains two tiny module-level helpers (in-lane refactor, no behavior change beyond D5): `_parse_cors_origins(raw)` (input: the raw env string or `None`; output: the list) and `_cors_options(origins)` (output: the keyword dict passed to `CORSMiddleware`). `CORS_ORIGINS` remains a module attribute computed at import from the helper, so existing consumers (the Playwright E2E via `SCREENER_CORS_ORIGINS`) are unchanged.

### D6 — Operator config lives OUTSIDE the repo: `%LOCALAPPDATA%\my_site\deploy.psd1`

`deploy/config.example.psd1` is committed; the real file is copied to `%LOCALAPPDATA%\my_site\deploy.psd1` and loaded with `Import-PowerShellDataFile` (data-only, no code execution). Reason: `.gitignore` is P1's lane, so a repo-local gitignored file is unavailable. Rejected: machine-wide environment variables (invisible state, hard to audit); editing root `.env.example` (see D8). No file holds a secret; Tailscale needs no key in this design.

Keys: `RepoRoot`, `UvPath`, `PnpmPath`, `TailscaleExe`, `ApiPort` (8000), `WebPort` (3000), `MaxWaitSeconds` (300), `AutoPull` (`$true`), `ExtraCorsOrigins` (default empty; add a MagicDNS-name origin here if used), optional `CacheRoot`, optional `WatchlistPath`. The CORS origin list is DERIVED by the launcher as `http://<tailscale-ip>:<WebPort>` plus extras, so it cannot drift from the bind address.

### D7 — Auto-resume is two-stage and gated (SPEC OQ9/OQ10)

| Stage | What | Now? | Where |
|---|---|---|---|
| A | `git pull --ff-only` at start-up. Git-safe: never merges, never touches untracked files, refuses on divergence or dirty conflicts. Bounded, non-fatal: a failed pull is logged and the app still starts. | **Enabled now** | `deploy/_common.ps1` function called from `deploy/start-api.ps1` (config `AutoPull`) |
| B | Recompute: `refresh_cache.py`, `backfill_primaries.py`, `compute_pairs.py` (per `api/scripts/BOOTSTRAP.md`; the one-time `backfill_pairs_universe.py` is NEVER part of any automatic path) | **Disabled/manual** until the gate below is true | Runbook manual commands now; a P1 resume script later (REQ-P1-2). This lane ships NO stage B automation and a test pins that. |

**Gate G-STAGEB (named, checkable precondition for enabling stage B) — ALL of:**
1. `uv run --project api python -c "from api.data import cache; import sys; sys.exit(0 if hasattr(cache, '_atomic_to_parquet') else 3)"` exits 0 (P1's atomic helper exists on the checked-out code);
2. `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` passes (P1's AC12 interrupted-write test);
3. P1's resume script exists and is idempotent and safe to interrupt (REQ-P1-2).

Until all three hold, stage B is manual. Stage A never modifies any parquet cache, so it is safe under a mid-resume shutdown.

Caveats stated plainly: stage A does not run `uv sync` or rebuild the web build output; a pull that changes `web/` sources needs a manual `deploy\build-web.ps1` before the change appears, and a pull that changes dependencies is picked up by `uv run` at the next API start (network needed then). If the user's own local edits, or a locally produced tracked cache file (for example under `api/data/cache/liqtide/`), conflict, the pull refuses and logs it; the app still starts on the old code.

### D8 — Docs and env example placement

Runbook is `deploy/README.md` (the repo has no root README). Root `.env.example` is NOT edited: ownership is unclear and nothing in this design reads a `.env` (F4), so an env example would be a dead artifact; `deploy/config.example.psd1` is the real, consumed example. (`.env.example` was not read this session — the harness privacy hook gates it and it is not needed.)

### D9 — Bind-safety is checked by observation, not assumption

Step B10 requires `netstat -ano | findstr :8000` and `:3000` to show only the `100.x.y.z` address, plus a failed request to the PC's LAN IP. That is the proof of D1.

### D10 — Address form: Tailscale IPv4 literal (chosen) vs MagicDNS name

IP literal is the default (fewer moving parts; the CORS origin and baked URL are trivially identical). A MagicDNS name works if the user prefers, by adding its origin to `ExtraCorsOrigins` and building with that URL. Whether Chrome's Private Network Access rules treat a page served from `100.64.0.0/10` as private (and so allow its calls to another `100.x` address) is unverified; step B9 is the probe.

### D11 — HARD STOP: no publicly reachable endpoint, no paid infrastructure

`tailscale funnel`, `tailscale serve --funnel`, subnet routers, exit nodes, port forwarding, dynamic DNS, and any cloud host are forbidden. The runbook states this in a bordered warning, no `deploy/*.ps1` may mention `funnel`, and a test pins both (G4). If a future step would need any of these, stop and surface it; do not write the step.

### D12 — AC8 scope check is a branch-gated committed test plus a gate command

A committed test that diffs against the base would fail on every later branch once merged to `main`; so it is skipped unless the current branch is exactly `claude/p2-deploy` and `origin/main` resolves. Gate command G7 runs the same comparison in EVL.

---

## Risk Predictions (5-persona pre-implementation debate, condensed)

| Persona | Prediction | Mitigation in this plan |
|---|---|---|
| Security | Tailscale account compromise exposes everything; a stray `funnel` would be public; the API has no auth by design. | D11 hard stop + test; runbook advises Tailscale 2FA and device approval (advice only, the user's account setup is unknown); bind is tailnet-only. |
| Operator (Windows) | Task Scheduler PATH and profile differences; execution policy; Tailscale not up at logon; firewall blocks inbound. | Absolute paths in config; `-ExecutionPolicy Bypass` scoped to the process; bounded IP wait; contingent scoped firewall rule; `-DryRun` on every launcher. |
| Data integrity | Boot-time recompute during an unclean shutdown truncates a gitignored parquet with no git copy. | Stage B disabled behind G-STAGEB; a test pins that no scheduled script runs it. |
| Test | Text-shape tests can pass while the script is wrong (green does not mean verified — `all-tests.md` Standing Lesson). | The tests are labeled shape guards only; script correctness is proven ONLY by the user-PC steps; gate stays CONDITIONAL until B5/B6/B8-B10 confirmed. |
| Maintainer | The `main.py` helper refactor could change CORS behavior; tightened CORS could break the Playwright E2E. | Behavior-preserving helpers with pinned tests (unset, empty, override); regression gate G5 runs the full pytest and G6 runs Playwright if the container can. |

### Edge cases for the three highest-risk checklist items (vc-scenario, condensed)

1. **`api/main.py` CORS change** — env value with spaces around commas; trailing slash on an origin (never matches a browser `Origin`; documented, not normalized); env set but empty (deny-all, preserved); origin listed twice; `HEAD` requests; preflight for a disallowed method returns 400. Each maps to a test in `test_main_cors.py`.
2. **Launcher IP wait** — Tailscale installed but logged out (`tailscale ip -4` errors), output has only an IPv6 line, output has two lines, or the wait times out at boot. `_common.ps1` must accept only a `100.64.0.0/10` IPv4, take the first valid line, and fail loudly on timeout. Pinned as text shape (pattern present, timeout variable present, non-zero exit); behavior proven at B6/B12.
3. **Stage A pull** — no network at boot, detached HEAD, no upstream, dirty tree, merge needed. Every one must end with the app starting and a log line, never a hung or failed launch. Pinned as text shape (`--ff-only`, error handling, none of `--force`/`reset --hard`/`stash`/`rebase`/`merge`); proven at B12/B13.

---

## Touchpoints

**Edited (1 existing source file):** `api/main.py`.

**Created (container, section A):**

| Path | Purpose |
|---|---|
| `deploy/README.md` | The operator runbook: what this is, the hard stop, Tailscale install/login (PC and phone), config, build (F2), start, Task Scheduler, verification, downtime recovery ("pull, then optionally recompute"), the D1 fallback, what Tailscale does and does not protect, rollback |
| `deploy/config.example.psd1` | Example operator config (D6); no secrets |
| `deploy/_common.ps1` | Shared helpers: load config, bounded Tailscale IP wait (100.64.0.0/10 IPv4 only), logging to `%LOCALAPPDATA%\my_site\logs`, stage A pull |
| `deploy/start-api.ps1` | Waits for the IP, runs stage A, sets `SCREENER_CORS_ORIGINS` (+ optional `SCREENER_CACHE_ROOT`/`SCREENER_WATCHLIST_PATH`) in the process environment, then runs `uv run --project api uvicorn api.main:app --host <ip> --port <ApiPort>` from `RepoRoot`. No `--reload`. Supports `-DryRun` |
| `deploy/start-web.ps1` | Waits for the IP, runs `pnpm --filter web exec next start -H <ip> -p <WebPort>`. Supports `-DryRun` |
| `deploy/build-web.ps1` | Discovers the IP, sets `NEXT_PUBLIC_API_BASE_URL=http://<ip>:<ApiPort>` BEFORE `pnpm --filter web build`. Supports `-DryRun` |
| `deploy/register-tasks.ps1` | Creates (or, with `-Remove`, deletes) scheduled tasks `mysite-api` and `mysite-web` per D2. Idempotent |
| `api/tests/deploy/__init__.py` | New test package |
| `api/tests/deploy/test_main_cors.py` | AC1, AC2 |
| `api/tests/deploy/test_health_endpoint.py` | AC5 |
| `api/tests/deploy/test_fresh_deploy_degrade.py` | AC3, AC4, AC11 automated halves |
| `api/tests/deploy/test_deploy_config_shape.py` | Shape guards on `deploy/` (G4) |
| `api/tests/deploy/test_lane_scope.py` | AC8 |
| `process/general-plans/active/deployability_28-09-26/deployability_REPORT_29-09-26.md` | EXECUTE report incl. test-building backlog stubs and any findings |

**Read-only (never edited):** `api/data/cache.py`, `api/data/watchlist.py`, `api/analytics/cointegration/pairs_response.py` (honest-degrade reference), `api/tests/scripts/test_snapshot_workflow_schedules.py` (pattern only), `api/tests/conftest.py`, `api/tests/pairs_fixtures.py`, all `api/routers/*` and `api/models/*`, `web/**` (grep only), `process/MASTER-PLAN.md`, `api/scripts/BOOTSTRAP.md` (on P1's branch; referenced, not copied).

## Public Contracts

- **`api/main.py` module surface**: `app`, `CORS_ORIGINS` (list of str, computed at import), `GET /api/health` returning exactly `{"status": "ok"}`; NEW private helpers `_parse_cors_origins`, `_cors_options`. `SCREENER_CORS_ORIGINS` semantics are unchanged (comma-separated, stripped, blanks dropped; unset = default; empty = deny-all).
- **HTTP behavior change (deliberate, safe per F3):** responses no longer send `Access-Control-Allow-Credentials: true`; preflight for methods other than GET/POST/DELETE or headers other than `Content-Type` is now rejected. The real web client is unaffected.
- **Operator contract**: config file location and keys (D6); scheduled task names `mysite-api`, `mysite-web`; log directory `%LOCALAPPDATA%\my_site\logs`; ports 8000/3000 by default.
- **No change** to any router, model, cache path, or web contract.

## Blast Radius

- **Risk class:** LOW for the code (one existing file, roughly 30 lines net; deploy files are new and inert until the user runs them); MEDIUM operational risk on the user's PC (Task Scheduler entries, Tailscale) — contained by a `-Remove` rollback and by nothing being registered from the container.
- **Allowed-path allowlist (the AC8 test and gate G7 compare against exactly this):** `api/main.py`, `deploy/`, `api/tests/deploy/`, `process/general-plans/active/deployability_28-09-26/`.
- **HARD OUT OF SCOPE (other lanes; needs become written requirements, never edits):**
  - `web/` — `claude/ui-shell`
  - `api/scripts/`, `.github/workflows/`, `.gitignore`, `api/data/cache.py` — `claude/p1-pipeline`
  - `api/data/pytrends_adapter.py` — pending PR #6 / narrative work
  - `process/context/all-context.md` — four-way contended (MASTER-PLAN T8, after T23); SPEC §7 forbids editing it now
  - root `.env.example` — ownership unclear (D8)
  - `process/MASTER-PLAN.md` and other plans' files
- **HARD STOP (D11):** no paid infrastructure, no publicly reachable endpoint, no Tailscale Funnel. Never created by this plan.

---

## Implementation Checklist

### Section A — container-executable (EXECUTE agent, opus, TDD-first)

Per-section test-gate loop: run each section's gate immediately after the section, fix inline, then continue. All commands run from the repo root.

1. **Confirm the baseline first.** `git branch --show-current` must print `claude/p2-deploy`; `git status --short` must be clean of source edits. Run `uv run --project api pytest api/ -q` and record the exact passed/deselected numbers in the REPORT (measured at VALIDATE 29-09-26 on this branch, which differs from origin/main only by the SPEC doc: **714 passed / 5 deselected**; still re-run and record the actual number — it is the no-regression anchor). No regression allowed against the recorded number.
2. **Confirm read-only facts** (record each result in the REPORT): (a) `grep -rn "credentials" web/lib web/components web/app` returns no non-test hit; (b) `grep -rnE '"(POST|DELETE|PUT|PATCH)"|Content-Type' web/lib web/components web/app` returns no non-test hit; (c) `uv run --project api uvicorn --help` shows `--host` and `--port`; (d) if `cd web && pnpm install --frozen-lockfile` works in this container (best effort; egress may block it) then `pnpm --filter web exec next start --help` confirms `-H`/`-p` — otherwise mark it unverified and rely on step B8. Do not edit any `web/` file; only `web/node_modules` may appear.
3. **Write the failing tests first** (red before green). All offline; all use `isolated_cache` and temp paths (never the real `api/data/cache` or `api/data/watchlist.json` — the Standing-Lesson data-loss trap; every reloaded module attribute is restored in a fixture teardown):
   - Create `api/tests/deploy/__init__.py`.
   - `api/tests/deploy/test_main_cors.py`, scenarios named verbatim: `test_docstring_no_longer_claims_localhost_only_bind` (module docstring contains neither "binds to 127.0.0.1 only" nor "never 0.0.0.0"), `test_docstring_states_tailscale_posture_and_run_command_concern` (mentions Tailscale and that the bind address is set by the run command), `test_default_origin_is_localhost_3000_when_env_unset` (helper called with `None`), `test_empty_env_value_denies_all_origins`, `test_override_env_is_parsed_comma_separated_and_stripped`, `test_allowlisted_origin_preflight_accepted` (throwaway FastAPI app built with `_cors_options`; a `100.x` origin on the list gets its origin echoed, status 200), `test_non_allowlisted_origin_preflight_rejected` (status 400, no allow-origin header), `test_cors_options_no_credentials_no_wildcards` (credentials False; `*` in neither methods nor headers), `test_import_time_wiring_honors_env` (reload `api.main` with `SCREENER_CORS_ORIGINS` set, inspect the real `CORSMiddleware` options on `app.user_middleware`; reload again after undoing the env in teardown so later tests see the default), `test_no_credentials_header_on_real_app_response`.
   - `api/tests/deploy/test_health_endpoint.py`: `test_health_returns_exact_status_ok_body` (200 and JSON equal to exactly `{"status": "ok"}`), `test_health_is_get_only` (POST returns 405).
   - `api/tests/deploy/test_fresh_deploy_degrade.py`: `test_empty_cache_all_screen_endpoints_never_500` (parametrized over the four screens' primary endpoints: screener board, pairs, regime components, narrative history — status 200 and a JSON body against an empty isolated cache and a temp watchlist path; F7 says all four already return 200), `test_empty_cache_pairs_reports_results_unavailable` (`computation_status == "results_unavailable"`), `test_empty_cache_regime_components_reports_no_points` (empty `grid_dates`), `test_aged_cache_regime_and_screener_never_500_and_no_nan` (see step 5), `test_watchlist_env_override_is_honored_at_import` (reload `api.data.watchlist` with `SCREENER_WATCHLIST_PATH`), `test_watchlist_add_round_trips_to_env_path` (POST a coin through the real router with the module attribute pointed at a temp file, then read that file back — the boundary round-trip the Standing Lesson demands), `test_cache_root_env_override_is_honored_at_import` (reload `api.data.cache` with `SCREENER_CACHE_ROOT`, restore).
   - `api/tests/deploy/test_deploy_config_shape.py` (text-shape guards, mirroring `test_snapshot_workflow_schedules.py`; they read files as text and never execute PowerShell): `test_expected_deploy_files_exist`, `test_no_deploy_script_binds_all_interfaces`, `test_readme_zero_zero_zero_zero_only_in_scoped_firewall_fallback`, `test_start_api_sets_cors_env_before_uvicorn_and_never_reloads`, `test_start_api_host_is_a_variable_not_a_literal`, `test_start_web_uses_next_start_not_dev_and_binds_variable`, `test_build_web_sets_next_public_api_base_url_before_build`, `test_scheduled_scripts_never_run_stage_b_or_no_history_jobs` (no `refresh_cache`, `compute_pairs`, `backfill_primaries`, `backfill_pairs_universe`, `snapshot_narrative`, `snapshot_liqtide`, `snapshot_chain_growth` in any `.ps1`; the README may name them as manual steps), `test_stage_a_is_ff_only_and_non_fatal` (contains `--ff-only`; contains none of `--force`, `reset --hard`, `stash`, `rebase`, `merge`), `test_register_tasks_at_logon_current_user_no_elevation` (AtLogOn present; no `SYSTEM`, no `RunLevel Highest`; restart settings present; supports `-Remove`), `test_ip_wait_is_bounded_and_cgnat_only` (a `MaxWaitSeconds`-driven timeout, the `100.64.0.0/10` pattern, non-zero exit on timeout), `test_no_funnel_or_public_exposure_anywhere` (no `.ps1` or `.psd1` contains "funnel", "ngrok", "cloudflared", "port forward", "exit node" or "advertise-routes" case-insensitively, and no firewall rule with `-RemoteAddress Any`/`0.0.0.0`; every README line containing "funnel" also contains a prohibition word), `test_config_example_has_required_keys_and_no_secrets`, `test_readme_pins_required_operator_facts` (contains `NEXT_PUBLIC_API_BASE_URL` alongside the word "rebuild", `Task Scheduler`, `Tailscale`, `_atomic_to_parquet` as the stage B gate, and a "pull, then optionally recompute" sentence).
   - `api/tests/deploy/test_lane_scope.py`: `test_lane_scope_only_allowed_paths` (skipped unless the branch is `claude/p2-deploy` and `origin/main` resolves; diffs the working tree and untracked files against the merge base and fails on any path outside the Blast Radius allowlist).
   - **Isolation and offline rules added at VALIDATE 29-09-26 (hard, per checks 1 and offline):** (i) `GET /api/screener/board` is NOT offline by itself: it calls `narrative_trigger.assemble_narrative_categories()` (which calls `coingecko_adapter.fetch_trending`, `pytrends_adapter.fetch_trend`, `reddit_adapter.fetch_mentions` and writes narrative points to `CACHE_ROOT`) and `ccxt_adapter.fetch_ohlcv`. Every test that hits the board, the scalp view or `/api/narrative/*` must stub those adapters (for ccxt use the `test_board_integration.py` pattern: `monkeypatch.setattr(ccxt_adapter.ccxt, "hyperliquid", ...)` + `ccxt_adapter.reset_exchange_cache()` before and after; for the three narrative adapters monkeypatch to their existing unavailable result shape, read the adapter first). No test may make a live provider call. (ii) Any test that POSTs/DELETEs the watchlist or reads the board requests `isolated_cache` AND patches `watchlist_store.DEFAULT_WATCHLIST_PATH` to a `tmp_path` file BEFORE building the client (the pattern in `api/tests/routers/test_watchlist.py`). (iii) A test that reloads `api.data.cache` or `api.data.watchlist` must set the env var with `monkeypatch.setenv`, must NOT request `isolated_cache` in the same test (its `monkeypatch.setattr(cache, "CACHE_ROOT", ...)` undo would restore a stale value after the reload), and must record the original `CACHE_ROOT` / `DEFAULT_WATCHLIST_PATH` / `CORS_ORIGINS` and reassign them in a `finally`/fixture teardown (env-undo-then-reload alone is acceptable only if a final assertion shows the attribute equals the recorded original). A final autouse-in-package check `test_real_data_paths_untouched` asserts, at module teardown, that the real `api/data/watchlist.json` and `api/data/cache/` file listings/mtimes are unchanged (skip if they do not exist). (iv) `SCREENER_CORS_ORIGINS`, `SCREENER_CACHE_ROOT` and `SCREENER_WATCHLIST_PATH` are set only through `monkeypatch.setenv`.
   - **Gate:** `uv run --project api pytest api/tests/deploy -q` — expect RED for the CORS/docstring/deploy-shape tests, GREEN for health and env-override tests. Record the red state in the REPORT. (Failing stubs for each Fully-Automated scenario are generated verbatim from these names at VALIDATE, per `vc-test-coverage-plan`.)
4. **Edit `api/main.py`** (behavior per D5):
   - Rewrite the module docstring: state that the bind address is a run-command concern (no `.run()` call exists in this file); Phase 1 posture is "reachable only over the Tailscale interface", the launcher binds to the Tailscale IPv4; local development keeps `--host 127.0.0.1`; CORS is scoped to an explicit origin list (default `http://localhost:3000`, overridable through `SCREENER_CORS_ORIGINS`); point to `deploy/README.md`. It must not contain the retired claims.
   - Add `_parse_cors_origins(raw)` and `_cors_options(origins)`; compute `CORS_ORIGINS` from the helper with the same default constant; pass `**_cors_options(CORS_ORIGINS)` to `add_middleware`. Keep the existing NOTE comments, `GZipMiddleware`, router includes, and `health()` untouched.
   - **Gate G1/G2:** `uv run --project api pytest api/tests/deploy/test_main_cors.py api/tests/deploy/test_health_endpoint.py -q` all green; then the full suite `uv run --project api pytest api/ -q` must equal the step-1 baseline plus only this lane's new tests.
5. **Empty-cache and aged-cache tests to green.** The empty-cache tests should pass with no code change (F7). For `test_aged_cache_regime_and_screener_never_500_and_no_nan`: seed a deliberately aged cache through the real `cache.write_*` functions (reuse `api/tests/pairs_fixtures.py` and `isolated_cache`; read `api/models/screener.py` and `api/models/regime.py` first and assert ONLY what those models already promise: 200, no NaN or zero stand-ins, every affected series carrying its explicit unavailable/insufficient/as-of marker). **Finding clause:** if an aged cache is served with no staleness marker at all, that is a real finding, not a test to weaken. Do NOT edit the router or model (out of lane): record it in the REPORT as a requirement to the owning lane, mark that assertion `xfail(strict=True)` with the reason, and leave the AC11 gate CONDITIONAL. **Gate G3:** `uv run --project api pytest api/tests/deploy/test_fresh_deploy_degrade.py -q`.
6. **Create the `deploy/` files** (Touchpoints table). Content requirements the shape tests pin, so no creative decisions remain: `_common.ps1` loads config with `Import-PowerShellDataFile`, fails with a named message if the file is missing, waits for a `100.64.0.0/10` IPv4 from `& <TailscaleExe> ip -4` (first valid line) until `MaxWaitSeconds` then logs and exits non-zero, appends timestamped lines to `%LOCALAPPDATA%\my_site\logs\<name>.log`, and exposes the stage A pull (a single `git pull --ff-only` in `RepoRoot`, errors caught and logged, never fatal). `start-api.ps1` builds `SCREENER_CORS_ORIGINS` from the derived IP and `WebPort` plus `ExtraCorsOrigins`, exports optional cache/watchlist overrides, and launches uvicorn with the derived host; `-DryRun` prints the resolved host, port, origins, overrides and the command and exits 0 without starting anything. `start-web.ps1` and `build-web.ps1` as in Touchpoints; `build-web.ps1` prints the baked URL and a reminder that changing the address needs a rebuild. `register-tasks.ps1` per D2 and `-Remove`. `deploy/README.md` follows the section list in Touchpoints and includes: the D11 warning box, the section B checklist (condensed, pointing to this plan for the full version), the D7 gate text, the D1 fallback with the scoped firewall rule, the F2 rebuild rule, the R1 contingent firewall rule, and the sentence "pull, then optionally recompute". `api/scripts/BOOTSTRAP.md` does NOT exist on this branch or `main` (it lands with P1's branch `claude/p1-pipeline`): the README must say so, link it as "available once P1 merges", and must not copy its commands; until it exists, step B13's manual-recompute half is conditional on P1 having merged. `config.example.psd1` lists the D6 keys with comments and no secret.
   - **Gate G4:** `uv run --project api pytest api/tests/deploy/test_deploy_config_shape.py -q` green.
7. **Scope test to green.** `uv run --project api pytest api/tests/deploy/test_lane_scope.py -q` (passes, or is skipped off-branch). **Gate G7 (command):** `git diff --name-only $(git merge-base HEAD origin/main); git ls-files --others --exclude-standard` — every line must start with an allowlisted prefix (Blast Radius). Any other path is a hard failure: revert it and write a requirement instead.
8. **Regression gates.** (a) Full suite `uv run --project api pytest api/ -q` = baseline + new tests, zero failures. (b) `git diff --check` clean. (c) CORS-change regression (G6): `cd web && PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e` (the documented cloud-container workaround in `all-tests.md`) if `web/node_modules` and the browser are available; if not, record "not run" and rely on steps 2a/2b plus `test_allowlisted_origin_preflight_accepted` — that leaves the real-browser CORS regression as a Hybrid gate that stays CONDITIONAL, with a backlog stub for a container-runnable check. (d) `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md` (structure only).
9. **Write the REPORT** `process/general-plans/active/deployability_28-09-26/deployability_REPORT_29-09-26.md`: baseline numbers, red-then-green evidence, findings from steps 2 and 5, the test-building backlog stubs (PowerShell parser gate in CI; container-runnable real-browser CORS check), and an explicit statement that section A is `CODE DONE`, not `VERIFIED`. Do not commit unless asked.

### Section B — USER-PC ONLY (Windows PowerShell). The USER runs these; no agent will.

Run from a normal (non-elevated) PowerShell in the repo root, on the PC that holds the caches, on `main`, after this lane has merged. House style follows the AC-11/AC-12/AC-14 precedents: command, expected observable, what to do if it fails. Report results back; on confirmation the plan moves toward `VERIFIED`. `<ip>` means your Tailscale address from B1 (starts with `100.`).

| Step | Command | Expected | If it fails |
|---|---|---|---|
| **B0** Update and read | `git pull --ff-only`, then open `deploy\README.md` and read the warning box and "What Tailscale does and does not protect" | Pull succeeds; you have read the box. Decision on record: home PC + Tailscale, ~$0 | Pull refuses (local edits): commit or stash your work first, then retry |
| **B1** Install Tailscale on the PC | Install from `https://tailscale.com/download/windows`, sign in. Then `& "C:\Program Files\Tailscale\tailscale.exe" ip -4` | Prints one address starting `100.` | Empty or error: not logged in — sign in from the tray icon. Different install path: note the real path for B4 |
| **B2** Install Tailscale on the phone | Install the Tailscale app, sign in with the SAME account, leave it on. On the PC: `& "C:\Program Files\Tailscale\tailscale.exe" status` | Both the PC and the phone are listed | Phone missing: different account, or the VPN toggle is off |
| **B3** Measure the real cache (informational) | `(Get-ChildItem api\data\cache -Recurse -File \| Measure-Object Length -Sum).Sum / 1MB` | A number in MB; write it down. Nothing to provision | None — informational only |
| **B4** Create the config | `New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\my_site"; Copy-Item deploy\config.example.psd1 "$env:LOCALAPPDATA\my_site\deploy.psd1"`, then edit it: `RepoRoot` (`(Get-Location).Path`), `UvPath` (`where.exe uv`), `PnpmPath` (`where.exe pnpm`), `TailscaleExe` (from B1) | File exists with absolute paths; leave `CacheRoot`/`WatchlistPath` unset (defaults are correct on this PC) | A `where.exe` prints nothing: that tool is not installed — install it first |
| **B5** Parse-check the scripts | `Get-ChildItem deploy\*.ps1 \| ForEach-Object { $e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$null,[ref]$e); "$($_.Name): $($e.Count) errors" }` | Every script prints `0 errors` | Any count above 0: stop and send the output back — the container could not check syntax |
| **B6** Dry run | `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-api.ps1 -DryRun`, and the same for `start-web.ps1` | Prints host = your `100.x.y.z`, the ports, `SCREENER_CORS_ORIGINS=http://<ip>:3000`, and the command. It must NOT show `0.0.0.0`. Exit 0 | "Timed out waiting for Tailscale IP": Tailscale is not connected. Wrong host: recheck B1 |
| **B7** Build the web app with the API address baked in | `cd web; pnpm install --frozen-lockfile; cd ..; powershell -NoProfile -ExecutionPolicy Bypass -File deploy\build-web.ps1`. Then verify: `Select-String -Path "web\.next\static\*" -Pattern 'http://100\.' -Recurse -List` | The build succeeds; at least one file contains your `http://<ip>:8000` | No hit: the variable was not set before the build — rebuild via the script (F2). Build error: send the last 30 lines back |
| **B7b** Empty-cache honesty probe (AC3) | Window 1: `$env:SCREENER_CACHE_ROOT="$env:TEMP\mysite_empty"; $env:SCREENER_WATCHLIST_PATH="$env:TEMP\mysite_wl.json"; uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8011`. Window 2: `foreach($p in '/api/health','/api/pairs','/api/regime/components','/api/screener/board','/api/narrative/history'){ "$p " + (Invoke-WebRequest "http://127.0.0.1:8011$p" -UseBasicParsing).StatusCode }`. Then stop the server and `Remove-Item Env:SCREENER_CACHE_ROOT, Env:SCREENER_WATCHLIST_PATH` | Every line ends `200`; `/api/pairs` body says `results_unavailable`. Loopback only, temp dirs — your real cache is untouched | A 500 anywhere is a real finding — send the output back |
| **B8** Run both services in the foreground | Window 1: `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\start-api.ps1`. Window 2: same with `start-web.ps1`. Window 3: `Invoke-RestMethod "http://<ip>:8000/api/health"`; open `http://<ip>:3000/pairs` in the PC browser | Health prints `status ok`; the page loads and shows real data or an honest state | Bind error: the IP is wrong — redo B6. Page loads but panels show errors: `Get-Content "$env:LOCALAPPDATA\my_site\logs\api.log" -Tail 30` and look for a 400 preflight (CORS/baked-URL mismatch — rebuild with B7) |
| **B9** Phone over Tailscale, Wi-Fi OFF | With Tailscale on and phone Wi-Fi off (cellular), open `http://<ip>:3000/screener` | Page loads and data appears | Timeout: Windows Firewall is likely blocking the tailnet interface — run the CONTINGENT rule in an elevated PowerShell: `New-NetFirewallRule -DisplayName "my_site tailnet" -Direction Inbound -Protocol TCP -LocalPort 8000,3000 -RemoteAddress 100.64.0.0/10 -InterfaceAlias Tailscale -Action Allow`, then retry. Page loads with no data: the browser may be blocking the cross-address call (Private Network Access) — note the browser and send it back |
| **B10** Prove it is NOT reachable elsewhere | (a) `netstat -ano \| findstr ":8000 :3000"`; (b) from the PC: `Invoke-WebRequest "http://<PC LAN IP>:8000/api/health" -TimeoutSec 5` (`ipconfig` for the LAN IP); (c) phone with Tailscale OFF on cellular: open the same URL | (a) only `<ip>:8000` and `<ip>:3000` in LISTENING, no `0.0.0.0`; (b) fails or times out; (c) fails to load | Any `0.0.0.0`, or a LAN success: STOP — do not register tasks; send the output back |
| **B11** Register start-on-logon | `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-tasks.ps1`, then `Get-ScheduledTask mysite-* \| Select TaskName,State` | `mysite-api` and `mysite-web` listed, state Ready | Access denied: re-run once in an elevated PowerShell. A parameter-name error: send it back |
| **B12** Reboot drill | Stop the foreground windows, reboot, log on, wait 2 minutes. `Invoke-RestMethod "http://<ip>:8000/api/health"` and read `api.log` | `status ok` from the PC and from the phone; the log shows the stage A pull result (ok, or a logged non-fatal refusal) | Not up: `Get-ScheduledTask mysite-* \| Get-ScheduledTaskInfo` for the last result; the log says whether Tailscale timed out |
| **B13** Downtime drill (AC10, AC11) | Shut the PC down across at least one UTC midnight, boot, log on. `git log -1 --format="%h %an %ad"`; open `/pairs`, `/regime`, `/screener` | A newer `github-actions[bot]` commit is present (stage A pulled it); screens show honest stale/unavailable states, never blank or wrong numbers. Then recompute MANUALLY per `api/scripts/BOOTSTRAP.md` steps 2, 3 and 5 (never step 4) and reload | Wrong numbers on any screen: send screenshots. NEVER enable automatic recompute (gate G-STAGEB) |
| **B14** Watchlist persistence (AC4) | The web app has NO add-coin control (no watchlist write UI exists in `web/`; VALIDATE 29-09-26 finding), so use the API. This WRITES YOUR REAL watchlist: `Invoke-RestMethod -Method Post -Uri "http://<ip>:8000/api/watchlist" -ContentType "application/json" -Body '{"symbol":"ZZTEST"}'`, then `Stop-ScheduledTask mysite-api; Start-ScheduledTask mysite-api`, then `Invoke-RestMethod "http://<ip>:8000/api/watchlist"`. Clean up afterwards: `Invoke-RestMethod -Method Delete -Uri "http://<ip>:8000/api/watchlist/ZZTEST"` | The list still contains `ZZTEST` after the restart; removed after cleanup | Reset to default: the watchlist path differs from what the API reads — send `api.log` |
| **B15** Sleep/wake (informational; behavior unverified) | Put the PC to sleep 10 minutes, wake it, reload from the phone | Loads. If not: `Start-ScheduledTask mysite-api; Start-ScheduledTask mysite-web` | Record the result either way; a repeat failure becomes a follow-up requirement |
| **B16** Rollback (any time) | `powershell -NoProfile -ExecutionPolicy Bypass -File deploy\register-tasks.ps1 -Remove`; stop leftover windows; optionally sign out of Tailscale | Tasks gone; nothing listens on the tailnet IP | A process lingers: `Get-Process uvicorn,node -ErrorAction SilentlyContinue \| Stop-Process` |
| **B17** Report back | Tell the agent which steps passed; paste any failure output | On confirmation of B8-B14 the plan is marked `VERIFIED` | — |

---

## Verification Evidence

Commands and runners per `process/context/tests/all-tests.md`: `uv run --project api pytest api/ -q` (integration tests deselected by default); Playwright only with the documented `PLAYWRIGHT_CHROMIUM_PATH` workaround. Baseline: **714 passed / 5 deselected** (measured at VALIDATE 29-09-26 on this branch, which differs from origin/main only by the SPEC doc); EXECUTE step 1 re-confirms it.

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G1 `pytest api/tests/deploy/test_main_cors.py -q` | Fully-Automated | AC1, AC2 |
| G2 `pytest api/tests/deploy/test_health_endpoint.py -q` | Fully-Automated | AC5 |
| G3 `pytest api/tests/deploy/test_fresh_deploy_degrade.py -q` (empty-cache, aged-cache, env-override, watchlist round-trip) | Hybrid (automated half; probe halves B7b, B13, B14) | AC3, AC4, AC11 |
| G4 `pytest api/tests/deploy/test_deploy_config_shape.py -q` (shape only; does NOT prove the scripts work) | Fully-Automated | AC9 (PC-side half), AC10 (stage A half), D1/D11 safety pins |
| G5 full suite `uv run --project api pytest api/ -q` equals baseline plus new tests; `git diff --check` clean | Fully-Automated | no-regression (supports AC1-AC5) |
| G6 `cd web && PLAYWRIGHT_CHROMIUM_PATH=... pnpm test:e2e` (real cross-origin fetches after the CORS tightening) | Hybrid (needs `web/node_modules` + browser) | AC2 (real-client regression) |
| G7 allowlist diff (`git diff --name-only $(git merge-base HEAD origin/main)` + untracked) and `test_lane_scope.py` | Fully-Automated | AC8 |
| G-STAGEB the three-part gate in D7 | Fully-Automated once P1 lands; a checklist precondition run by whoever enables stage B | AC12 (P1's), AC10 (auto-resume safety) |
| B5 parse check, B6 dry run | Agent-Probe (user-PC) | script validity behind AC10 |
| B7 baked-URL search, B8 reachability | Agent-Probe (user-PC) | AC2 (real deployment), F2 |
| B9 phone over Tailscale, B10 bind-scope + negative reachability | Agent-Probe (user-PC) | AC8 spirit (no public exposure), D1 |
| B11 Task Scheduler registration, B12 reboot | Agent-Probe (user-PC) | AC10 |
| B13 downtime drill | Agent-Probe (user-PC) | AC10, AC11 |
| B14 watchlist persistence | Agent-Probe (user-PC) | AC4 |
| SPEC / Decision Recorded human review | Agent-Probe (human) | AC6, AC7 |
| Post-T8 `grep -c "intermittent" process/context/all-context.md` | Fully-Automated (blocked on T8) | AC13 |

### Per-area coverage tiers

**Area: `api/main.py`** — Fully-Automated: CORS parse/defaults/override/deny/reject/no-credentials (G1), health shape (G2). Hybrid: real-browser CORS regression (G6, precondition: `web/node_modules` + chromium). Does NOT prove: behavior from a real phone (B9).

**Area: `deploy/*.ps1`, `deploy/README.md`, `deploy/config.example.psd1`** — Fully-Automated: text-shape guards only (G4). Agent-Probe: parse, dry run, foreground run, bind scope, task registration, reboot (B5-B12). Does NOT prove: any script actually runs correctly on Windows until the user confirms B5/B6/B8/B10. Gate stays CONDITIONAL until then.

**Area: cache/watchlist env wiring (read-only)** — Fully-Automated: env override honored at import and a write round-trip (G3). Agent-Probe: survives a restart on the real PC (B14).

**Area: honest degradation on empty/aged caches (read-only)** — Fully-Automated: empty-cache endpoints never 500 (G3). Hybrid: aged cache (G3 + B13). Potential finding recorded in step 5.

**Area: cross-lane requirements** — no proof here; each has a named owner and interface below.

### Gap resolution options

| Gap | Resolution options |
|---|---|
| No PowerShell in the container | A) Add a CI parser gate (P1 lane, `.github/workflows/`). B) Install `pwsh` in the container image (infra). C) Accept: covered by B5/B6 agent-probe (chosen). D) Backlog stub in the REPORT (chosen, required by the vacuous-green rule). |
| Real-browser CORS regression may not run in the container | A) Get `web/node_modules` + chromium working and run G6 (chosen if possible). B) Rely on grep + preflight tests (fallback, leaves CONDITIONAL). C) Accept as known residual only with D. D) Backlog stub for a container-runnable check. |
| Firewall/tailnet/wake behavior unknowable here | A) Not testable in-container. B) Not testable in-container. C) Accept as agent-probe steps B9, B15 (chosen). D) Follow-up requirement if B15 fails. |

## Test Infra Improvement Notes

- The `tests/` context group has only `all-tests.md`; there is no doc for testing deployment/launcher artifacts. After EXECUTE, add a short "config-shape guards vs. real behavior" entry to `all-tests.md` (deferred to T8/UPDATE PROCESS, contended file).
- No `pwsh` in the container means `.ps1` files are only text-checked. A parser gate in CI would close it (backlog stub; needs `.github/workflows/`, P1's lane).
- A reusable "reload module and restore" fixture (used here for `api.main`, `api.data.watchlist`, `api.data.cache`) may be worth promoting to `api/tests/conftest.py` later; it is kept local to `api/tests/deploy/` now to stay in lane.
- `SCHEDULER_DELAY_BUFFER_MIN = 180` in the workflow-schedule guard no longer reflects observed reality (REQ-P1-3).

---

## Requirements Handed To Other Lanes

Each is a requirement with a named interface. This lane implements none of them.

| ID | To | Requirement | Named interface / evidence |
|---|---|---|---|
| **REQ-UI-1** | `claude/ui-shell` (`web/`) | `NEXT_PUBLIC_API_BASE_URL` is inlined at build time (F2). The web app must be built with the deployed API address; the silent fallback to `http://127.0.0.1:8000` means a phone would call its own loopback. Ask: document the build-time rule in `web/`'s own docs, and consider failing the production build (or showing an explicit banner) when the variable is unset for a non-dev build. | `web/lib/api/{screener,regime,narrative,onchain,pairs}.ts`; runbook step B7 |
| **REQ-UI-2** | `claude/ui-shell` | Proposal, not a demand: proxy `/api/*` through Next.js rewrites to `127.0.0.1:8000` so the API can stay loopback-only, CORS becomes moot, and the build-time URL disappears (D4). | `next.config` rewrites; would let `deploy/` drop the API tailnet bind |
| **REQ-P1-1** | `claude/p1-pipeline` | Land atomic parquet writes: `cache._atomic_to_parquet(df: pd.DataFrame, path: Path) -> None` plus the AC12 test `api/tests/data/test_cache_atomic_writes.py`. It is the hard prerequisite of stage B (D7, SPEC OQ10). Status: planned, not implemented (F5). | Gate G-STAGEB parts 1-2 |
| **REQ-P1-2** | `claude/p1-pipeline` | A resume script in `api/scripts/`, e.g. `resume_after_downtime.py`, invoked as `uv run --project api python -m api.scripts.resume_after_downtime`. Stage A (`git pull --ff-only`) is already done by `deploy/`, so the script covers stage B only: `refresh_cache`, `backfill_primaries`, `compute_pairs` in the `BOOTSTRAP.md` order, NEVER `backfill_pairs_universe`. Must be idempotent and safe to interrupt; must refuse to run (exit non-zero with a named reason) when `cache._atomic_to_parquet` does not exist; exit codes follow the P1 convention (0 = at least one item succeeded, 2 = nothing succeeded, 1 = crash); must have its own pytest against a fixture cache (AC10). Reference `api/scripts/BOOTSTRAP.md` rather than duplicating it. | Gate G-STAGEB part 3 |
| **REQ-P1-3** | `claude/p1-pipeline` | The 180-minute scheduler buffer no longer covers reality. Observed start delays: 2h03m (09-26), 3h06m (09-27), 5h01m (09-28); the 09-28 narrative run started 23:18:44Z and committed 23:19:22Z, 41 minutes before UTC midnight; delays are rising. Update `SCHEDULER_DELAY_BUFFER_MIN` in `api/tests/scripts/test_snapshot_workflow_schedules.py`, its "~2h / ~2h20m" docstring, and the same claim in the workflow comments, and re-time the crons. Arithmetic to weigh (inference, not observation): the 18:47 liqtide slot plus a 5h01m delay is about 23:48Z. Also pin `runs-on: ubuntu-latest` on the three no-history workflows (AC9). Decide the buffer from the observed maximum plus margin. | `.github/workflows/*.yml`; the guard test |
| **REQ-P1-4** | `claude/p1-pipeline` | Keep `api/scripts/BOOTSTRAP.md` the single source of recompute commands; this lane's runbook links to it. If P1 renames or reorders the commands, update BOOTSTRAP.md only — the runbook will not duplicate them. | `api/scripts/BOOTSTRAP.md` |
| **REQ-CTX-1** | Whoever executes MASTER-PLAN T8 (after T23) | Ready-to-paste entry for `process/context/all-context.md` (this lane is forbidden to edit it; AC13 cannot be closed here). Suggested text: "**Deployment posture (Phase 1, decided 29-09-26):** the app runs on the author's own Windows PC (the same machine that holds the gitignored `ohlcv/`, `liquidity/`, `pairs/`, `legs/` caches), reachable only over Tailscale; ~$0/month; no public endpoint exists. The PC is intermittently available. The three nightly snapshot workflows run on GitHub (`ubuntu-latest`), so PC downtime loses no archived data. Design rule: jobs whose source keeps no history (narrative, liqtide) stay on GitHub Actions; only backfillable or derived jobs may move to the PC. Known risk: parquet writes in `api/data/cache.py` are not atomic until P1's `_atomic_to_parquet` lands; automatic recompute at boot is gated on it, and only `git pull --ff-only` runs automatically. `NEXT_PUBLIC_API_BASE_URL` is baked at `next build` time, so changing the API address needs a rebuild. GitHub's real scheduler delay was 2h03m, 3h06m and 5h01m on 09-26 to 09-28 (not '~2h'). Launchers and runbook: `deploy/README.md`. Phase 2 (a true always-on box on a different machine) re-opens the cache-migration problem." | Verify after T8: `grep -c "intermittent" process/context/all-context.md` returns 1 or more |

---

## Risks

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R1 | Windows Firewall blocks inbound tailnet traffic even to a Tailscale-bound socket | Medium / blocks phone access, not a safety issue | B9 detects; contingent scoped rule (never opens the LAN) |
| R2 | Sleep/wake drops or re-creates the Tailscale interface and the listener stops answering | Unknown / annoyance | B15 probe; documented `Start-ScheduledTask` recovery; Task Scheduler restarts on failure only, not on wake (unverified) |
| R3 | The Tailscale IP changes (device re-added), so the baked web URL and CORS origin go stale | Low / rebuild needed | `build-web.ps1` prints the baked URL; runbook states "address change = rebuild" |
| R4 | Stage A pull refused by local edits or divergence | Medium / stale code, app still runs | Non-fatal by design; logged |
| R5 | A pull changes `web/` but the web build output is stale | Medium / old UI | Documented; manual `build-web.ps1` |
| R6 | Tightened CORS breaks the Playwright E2E or a client the grep missed | Low / medium | G6 if runnable; greps in step 2; behavior-preserving helpers; rollback is a one-file revert |
| R7 | Chrome Private Network Access blocks page-to-API calls between tailnet addresses | Unknown / blocks data | B9 probe; REQ-UI-2 (same-origin proxy) is the structural fix |
| R8 | Text-shape tests give false confidence about the `.ps1` files | Medium / wasted user time | Labeled shape-only; B5/B6 first; gate CONDITIONAL until confirmed |
| R9 | An aged cache is served with no staleness marker on `/screener` or `/regime` | Unknown / an honesty gap | Step 5 finding clause; recorded, not silently fixed |
| R10 | Nightly runs slip past UTC midnight (real, measured) | High / permanent narrative gaps | REQ-P1-3; not this lane's files |
| R11 | Tailscale account compromise reaches the app (no app auth by design) | Low / high | Advice in the runbook (2FA, device approval); scope stays personal |
| R12 | Task Scheduler cmdlet parameter names or `Register-ScheduledTask` privilege differ from what this plan assumes | Medium / small | B11 failure path; `Get-Help` fallback; flagged as unconfirmed in D2 |

## Dependencies and Ordering

- Section A steps run in order 1 to 9 (tests before code, code before deploy files). Section A has no dependency on P1 or ui-shell landing; stage B and AC12 depend on P1 (REQ-P1-1/2). Section B depends on section A being merged into the checkout the user runs.
- Verified ordering (no step depends on a later step's output): step 2 facts feed step 3 tests; step 3 tests define step 4 behavior; step 4 precedes step 5 (the app must be importable) and step 6 (the docstring points to `deploy/`); G7 runs last over everything.

## Change Management

Scope changes: classify, list impacted files, update this plan's decisions and Status. Most likely triggers: Task Scheduler parameter names differ (edit `register-tasks.ps1` only); B9/B10 show the firewall or Private Network Access blocks access (choose the contingent rule or move to REQ-UI-2); P1 lands atomic writes (enable stage B through a separate, small follow-up plan, not by editing this one).

## Validate Contract

Status: CONDITIONAL
Date: 29-09-26
date: 2026-09-29
generated-by: outer-pvl

Parallel strategy: sequential
Rationale: score 2/7 (S6 partial: trust-boundary/network-exposure surface; S7 no: 1 edited source file + ~13 new files, single lane, single opus execute leg). Dominant signal: one source file with tests-before-code ordering; no independent slices worth fanning out. Model: opus for the single vc-execute-agent leg, sonnet for the EVL vc-tester and every other agent. Agent count: 1 execute + 1 tester = 2.

Test gates (C3 table; strategy column carries only proving strategies, Known-Gap is never a strategy):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC1 | Docstring drops localhost-only claim; default origin is localhost:3000 | Fully-Automated | `uv run --project api pytest api/tests/deploy/test_main_cors.py -q` (`test_docstring_no_longer_claims_localhost_only_bind`, `test_docstring_states_tailscale_posture_and_run_command_concern`, `test_default_origin_is_localhost_3000_when_env_unset`) | B |
| AC2 | Listed origin accepted, unlisted rejected, tightened CORS options, import-time env wiring | Fully-Automated | same file (`test_empty_env_value_denies_all_origins`, `test_override_env_is_parsed_comma_separated_and_stripped`, `test_allowlisted_origin_preflight_accepted`, `test_non_allowlisted_origin_preflight_rejected`, `test_cors_options_no_credentials_no_wildcards`, `test_import_time_wiring_honors_env`, `test_no_credentials_header_on_real_app_response`) | B |
| AC2 (real client) | Real browser cross-origin fetches still work after tightening | Hybrid | G6 `cd web && PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e` (precondition: `web/node_modules` + chromium); fallback = step-2 greps + preflight tests, stays CONDITIONAL | D (backlog stub: container-runnable real-browser CORS check) |
| AC5 | `/api/health` returns exactly `{"status": "ok"}`, GET-only | Fully-Automated | `uv run --project api pytest api/tests/deploy/test_health_endpoint.py -q` (`test_health_returns_exact_status_ok_body`, `test_health_is_get_only`) | B |
| AC3 | Empty cache: all 4 screens honest, never 500 | Hybrid | G3 `uv run --project api pytest api/tests/deploy/test_fresh_deploy_degrade.py -q -k empty` (adapters STUBBED, see E1) + user step B7b | A (automated half) / C (B7b user-run) |
| AC4 | Watchlist/cache env overrides honored, write round-trips to the env path | Hybrid | G3 `-k "env or round_trips"` + user step B14 (API POST, not UI) | A / C |
| AC11 | Aged cache never 500, never NaN, explicit marker | Hybrid | `test_aged_cache_regime_and_screener_never_500_and_no_nan` (xfail(strict) + REPORT finding if no marker) + user step B13 | B / C |
| AC8 | No file outside allowlist changed | Fully-Automated | `uv run --project api pytest api/tests/deploy/test_lane_scope.py -q` + G7 `git diff --name-only $(git merge-base HEAD origin/main); git ls-files --others --exclude-standard` | B |
| AC9 (PC half), AC10 (stage A half), D1/D11 pins | `deploy/` text-shape: no 0.0.0.0, no funnel/public exposure, ff-only pull, CGNAT-only bounded IP wait, no stage-B script in any `.ps1`, README facts | Fully-Automated (SHAPE ONLY, does not prove scripts run) | `uv run --project api pytest api/tests/deploy/test_deploy_config_shape.py -q` | B |
| AC10 / D2 / D3 / B-steps | `.ps1` parse validity, dry run, tailnet-only bind, Task Scheduler registration, reboot, downtime, sleep/wake, phone reachability | Agent-Probe (USER-RUN on Windows only) | B5, B6, B7, B7b, B8, B9, B10, B11, B12, B13, B14, B15 | C (user-run; Windows/Tailscale/Task Scheduler cmdlet and parameter names are unconfirmed and are ACCEPTED as agent-probe under B5/B11; no pwsh in the container) |
| AC12 | Interrupted write never corrupts a cache file | (out of lane: P1) | P1 `api/tests/data/test_cache_atomic_writes.py`; gate G-STAGEB keeps stage B off | C (P1 owns; unmet) |
| AC9 (workflows), AC10 (resume script), AC13 | Nightly workflows on ubuntu-latest; resume script; project-wide context entry | (out of lane: P1 / T8) | REQ-P1-2/3, REQ-CTX-1; after T8 `grep -c "intermittent" process/context/all-context.md` >= 1 | C |
| AC6, AC7 | Hosting and access-privacy decision on record | Agent-Probe (human review, already given 29-09-26) | SPEC + Decision Recorded | A |

Legacy line form:
- api/main.py CORS + health: [Fully-automated: `uv run --project api pytest api/tests/deploy/test_main_cors.py api/tests/deploy/test_health_endpoint.py -q`] | [hybrid: G6 Playwright, precondition web/node_modules + chromium] | [agent-probe: step B9 phone] | [known-gap: none]
- deploy/*.ps1 + README + psd1: [Fully-automated: `uv run --project api pytest api/tests/deploy/test_deploy_config_shape.py -q` (shape only)] | [hybrid: none] | [agent-probe: B5-B12 on the user's Windows PC] | [known-gap: PowerShell runtime behavior, backlog stub "PowerShell parser gate in CI"]
- Cache/watchlist env + honest degradation: [Fully-automated: `uv run --project api pytest api/tests/deploy/test_fresh_deploy_degrade.py -q`] | [hybrid: B7b, B13] | [agent-probe: B14] | [known-gap: none]
- Scope: [Fully-automated: `uv run --project api pytest api/tests/deploy/test_lane_scope.py -q` + G7] | [known-gap: none]
- Full regression G5: `uv run --project api pytest api/ -q` must equal 714 passed / 5 deselected PLUS only this lane's new tests; `git diff --check` clean.

Failing stubs (Fully-Automated scenarios, names verbatim from the plan; hybrid/agent-probe rows get none):
```
test("should test_docstring_no_longer_claims_localhost_only_bind", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_docstring_no_longer_claims_localhost_only_bind") })
test("should test_docstring_states_tailscale_posture_and_run_command_concern", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_docstring_states_tailscale_posture_and_run_command_concern") })
test("should test_default_origin_is_localhost_3000_when_env_unset", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_default_origin_is_localhost_3000_when_env_unset") })
test("should test_empty_env_value_denies_all_origins", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_empty_env_value_denies_all_origins") })
test("should test_override_env_is_parsed_comma_separated_and_stripped", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_override_env_is_parsed_comma_separated_and_stripped") })
test("should test_allowlisted_origin_preflight_accepted", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_allowlisted_origin_preflight_accepted") })
test("should test_non_allowlisted_origin_preflight_rejected", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_non_allowlisted_origin_preflight_rejected") })
test("should test_cors_options_no_credentials_no_wildcards", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_cors_options_no_credentials_no_wildcards") })
test("should test_import_time_wiring_honors_env", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_import_time_wiring_honors_env") })
test("should test_no_credentials_header_on_real_app_response", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_no_credentials_header_on_real_app_response") })
test("should test_health_returns_exact_status_ok_body", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_health_returns_exact_status_ok_body") })
test("should test_health_is_get_only", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_health_is_get_only") })
test("should test_expected_deploy_files_exist", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_expected_deploy_files_exist") })
test("should test_no_deploy_script_binds_all_interfaces", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_no_deploy_script_binds_all_interfaces") })
test("should test_readme_zero_zero_zero_zero_only_in_scoped_firewall_fallback", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_readme_zero_zero_zero_zero_only_in_scoped_firewall_fallback") })
test("should test_start_api_sets_cors_env_before_uvicorn_and_never_reloads", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_start_api_sets_cors_env_before_uvicorn_and_never_reloads") })
test("should test_start_api_host_is_a_variable_not_a_literal", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_start_api_host_is_a_variable_not_a_literal") })
test("should test_start_web_uses_next_start_not_dev_and_binds_variable", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_start_web_uses_next_start_not_dev_and_binds_variable") })
test("should test_build_web_sets_next_public_api_base_url_before_build", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_build_web_sets_next_public_api_base_url_before_build") })
test("should test_scheduled_scripts_never_run_stage_b_or_no_history_jobs", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_scheduled_scripts_never_run_stage_b_or_no_history_jobs") })
test("should test_stage_a_is_ff_only_and_non_fatal", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_stage_a_is_ff_only_and_non_fatal") })
test("should test_register_tasks_at_logon_current_user_no_elevation", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_register_tasks_at_logon_current_user_no_elevation") })
test("should test_ip_wait_is_bounded_and_cgnat_only", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_ip_wait_is_bounded_and_cgnat_only") })
test("should test_no_funnel_or_public_exposure_anywhere", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_no_funnel_or_public_exposure_anywhere") })
test("should test_config_example_has_required_keys_and_no_secrets", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_config_example_has_required_keys_and_no_secrets") })
test("should test_readme_pins_required_operator_facts", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_readme_pins_required_operator_facts") })
test("should test_lane_scope_only_allowed_paths", () => { throw new Error("NOT IMPLEMENTED — TDD stub: test_lane_scope_only_allowed_paths") })
```
(Python-side equivalent for execute-agent: each named function first body is `raise NotImplementedError("NOT IMPLEMENTED — TDD stub: <name>")`, run RED, then implement.)
Hybrid-tier named tests (no stubs): `test_empty_cache_all_screen_endpoints_never_500`, `test_empty_cache_pairs_reports_results_unavailable`, `test_empty_cache_regime_components_reports_no_points`, `test_aged_cache_regime_and_screener_never_500_and_no_nan`, `test_watchlist_env_override_is_honored_at_import`, `test_watchlist_add_round_trips_to_env_path`, `test_cache_root_env_override_is_honored_at_import`, plus new `test_real_data_paths_untouched` (isolation guard, added at VALIDATE).

Plan updates applied at VALIDATE (29-09-26):
- P1: baseline corrected 717 -> 714 passed / 5 deselected in Implementation Checklist step 1 and the Verification Evidence preamble (measured this session on this branch: 714 passed, 5 deselected, 2m46s).
- P2: step 3 gained an Isolation-and-offline rules bullet: screener board / scalp / narrative endpoints call coingecko/pytrends/reddit/ccxt and write narrative points, so the adapters MUST be stubbed; watchlist patched to tmp before any client is built; reload hygiene (no reload under `isolated_cache`, recorded originals restored); env only via `monkeypatch.setenv`; new `test_real_data_paths_untouched` guard for real `api/data/watchlist.json` and `api/data/cache/`.
- P3: `test_no_funnel_or_public_exposure_anywhere` widened to ngrok, cloudflared, port forward, exit node, advertise-routes, and `-RemoteAddress Any`/`0.0.0.0`.
- P4: step B14 corrected: the web app has no add-coin UI (grep of `web/` finds no watchlist write path); the step now uses `Invoke-RestMethod` POST/DELETE against the API and warns it touches the real watchlist.
- P5: README requirement added: `api/scripts/BOOTSTRAP.md` does not exist on this branch or main (lands with P1); link as "available once P1 merges", never copy its commands; B13's recompute half is conditional on P1 merged.

Execute-agent instructions:
- E1: Read each narrative adapter's unavailable result shape before stubbing; never let a test reach the network (a live call in the container is blocked and will hang or flake; with network it would call real providers).
- E2: All tests use `tmp_path`/`isolated_cache`/temp watchlist. The real `api/data/cache/` (liqtide parquet files are git-tracked) and `api/data/watchlist.json` must be byte- and mtime-identical before and after the full suite; check with `git status --short api/data` and `test_real_data_paths_untouched`. Any diff there is a hard failure: revert and stop.
- E3: `api/main.py` is the ONLY existing source file edited. CORS methods list is exactly GET, POST, DELETE (verified against `api/routers/*`: only `@router.get`, one `@router.post` and one `@router.delete` on the watchlist router; no PUT/PATCH/HEAD routes). If any router later serves another method, extend the list, do not use `*`.
- E4: If `pnpm install`/Playwright cannot run, record "G6 not run" plainly; do not claim the real-browser regression proven.
- E5: Never run or claim any section B step. No `pwsh` exists in the container: never assert PowerShell syntax validity; the shape tests are labeled shape-only in their docstrings and in the REPORT.
- E6: Windows/Tailscale/Task Scheduler cmdlet and parameter names (`New-ScheduledTaskSettingsSet`, `Register-ScheduledTask` restart params, Tailscale CLI `ip -4`, `New-NetFirewallRule -InterfaceAlias`) are unconfirmed; write them as planned, flag them in the REPORT as unconfirmed, and leave their proof to B5/B11.
- E7: No commit unless asked. REPORT records baseline 714/5, red-then-green evidence, findings, backlog stubs (PowerShell parser gate in CI; container-runnable real-browser CORS check), and states section A is CODE DONE, not VERIFIED.

Dimension findings:
- Infra fit: CONCERN — bind-to-tailnet-IP, Task Scheduler at-logon and next start flags are unverifiable in-container (no pwsh/Tailscale/Windows); accepted as agent-probe (B5, B6, B8, B10, B11), confirmed sound in design; F2 baked-URL and CORS-two-origin design consistent with the code.
- Test coverage: CONCERN — 714/5 baseline confirmed; automated halves are real, but `.ps1` correctness rests on shape tests plus user-run probes; board/narrative tests would have touched live providers (fixed by plan update P2); real-browser CORS gate G6 may not run in the container.
- Breaking changes: PASS — served methods verified as GET/POST/DELETE only (`api/routers/*`); web/ (incl. e2e) has no `credentials`, no custom headers, no POST/DELETE (fetches pass only `signal`), so dropping credentials and wildcards is safe; no router/model/cache contract touched.
- Security surface: PASS — bind is tailnet-IPv4-only (D1), no funnel/public/paid infra (D11 pinned by test, widened by P3), no secrets, no app auth by design and Tailscale account is the boundary (advice-only, R11); data-loss trap (MASTER-PLAN T22) covered by P2 hard rules and `test_real_data_paths_untouched`.
- Section A step 1-9 feasibility: PASS — mechanically feasible; helper refactor of main.py is behavior-preserving; highest-risk edit = `api/main.py` CORS options (mitigated by preserved-behavior tests and G6/G5).
- Section B feasibility: CONCERN — B14 was unexecutable as written (no watchlist UI) and is corrected by P4; B13's BOOTSTRAP.md exists only on P1's branch (P5); cmdlet parameter names unconfirmed (accepted agent-probe, E6).
- Lane allowlist (api/main.py, deploy/, api/tests/deploy/, task folder): PASS — Touchpoints and Blast Radius list nothing outside it; `git diff` vs merge-base currently shows only the SPEC doc (in allowlist) plus the untracked plan.

Open gaps:
- G-A: PowerShell parse/runtime behavior of `deploy/*.ps1`: known-gap: documented as NEW PLAN REQUIRED (backlog stub "PowerShell parser gate in CI", P1 lane); covered meanwhile by agent-probe B5/B6 (user-run).
- G-B: real-browser CORS regression possibly not runnable in-container: backlog stub "container-runnable real-browser CORS check"; covered by G6 if runnable, else CONDITIONAL.
- G-C: AC9 workflows, AC10 resume script, AC12 atomic writes, AC13 context entry: out of lane, owners P1 / T8 (REQ-P1-1/2/3, REQ-CTX-1); unmet until they land, this lane claims none.
- G-D: possible aged-cache-without-staleness-marker honesty gap on /screener or /regime (R9): recorded as finding, xfail(strict), not fixed here.
- G-E: no Windows/Tailscale behavior is proven; VERIFIED requires the user to confirm B8-B14.

What This Coverage Does NOT Prove:
- G1/G2 (pytest CORS + health) do not prove behavior from a real phone, a real browser Private Network Access decision, or Windows firewall behavior.
- G3 automated halves use stubbed adapters and temp dirs: they do not prove real provider behavior, real cache contents, or persistence across a real process restart on the user's PC (B14).
- G4 (deploy shape tests) proves only that certain text is present or absent; it does NOT prove any `.ps1` parses, runs, binds the right address, or registers a task.
- G5 full suite proves no Python regression only; nothing about `web/`.
- G6 (if run) proves the local Playwright CORS path only, not the tailnet deployment.
- G7 proves file scope, not correctness.
- Nothing here proves Tailscale reachability, non-reachability from LAN (B10), reboot/sleep/downtime recovery (B12, B13, B15), or that stage B is safe (G-STAGEB, P1's atomic writes are not implemented).

Gate: CONDITIONAL (0 FAILs, 3 CONCERN dimensions; mandatory 717->714 fix and hard checks 1-5 satisfied or corrected in plan; no first-pass PHASE_COMPLETE)
Accepted by: user, 2026-09-29 (chat: "accept") — concerns: infra-fit, test-coverage (shape-only .ps1), section B cmdlet names / BOOTSTRAP.md dangling until P1 merges

## Deviations

Recorded at EXECUTE 29-09-26 (all within the allowlist; full detail in `deployability_REPORT_29-09-26.md`):

- Added `api/tests/deploy/conftest.py` (offline stubs, socket guard, real-data snapshot) and `api/tests/deploy/test_zz_real_data_guard.py` (hosts `test_real_data_paths_untouched`). Impact: none outside the lane.
- The step-5 strict xfail is a parametrize case of `test_aged_cache_regime_and_screener_never_500_and_no_nan`, so only the marker assertion is xfailed. Finding: the screener chart has no staleness marker on an aged cache (AC11 stays CONDITIONAL).
- Offline stubs also cover FRED, DefiLlama and Farside (reached by `/api/regime/components`), not only ccxt and the narrative adapters.

**Section A status (29-09-26): CODE DONE, not VERIFIED.** Section B not run.

## Autonomous Goal Block

```
SESSION GOAL: Deployability P2 Phase 1 - run my_site on the author's Windows PC, reachable only over Tailscale (section A in container; section B is user-run)
Charter + umbrella plan: N/A - single plan (process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md; SPEC same folder)
Autonomy: proceed without approval pauses on reversible steps; subagent delegation stays mandatory (feedback_autonomous_phase_execution.md); never claim a user-PC step passed.
Hard stop conditions / safety constraints:
- No paid infrastructure, no publicly reachable endpoint, no Tailscale Funnel, no 0.0.0.0 bind (D11, D1).
- Edit ONLY api/main.py, deploy/, api/tests/deploy/, and the task folder; anything else is reverted and written as a requirement.
- Tests must never touch the real api/data/cache or api/data/watchlist.json (isolated_cache + temp watchlist; no live provider calls).
- Stage B (automatic recompute) stays off until gate G-STAGEB (P1 atomic writes) holds.
- Section B (Windows PowerShell) is run by the USER only; do not mark VERIFIED until they confirm B8-B14.
Next phase: EXECUTE: process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md (one vc-execute-agent, opus, section A steps 1-9)
Validate contract: inline in the plan (Gate: CONDITIONAL; concerns need acceptance or a supplement cycle before EXECUTE)
Execute start: baseline `uv run --project api pytest api/ -q` = 714 passed / 5 deselected | `uv run --project api pytest api/tests/deploy -q` | G6 Playwright if runnable | probe: user steps B5-B14 | high-risk pack: no
```

## Resume and Execution Handoff

1. **Selected plan file**: `process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md` (supporting: the locked SPEC in the same folder).
2. **Last completed phase or step**: PLAN written 29-09-26; nothing executed.
3. **Validate-contract status**: pending (placeholder above). PVL must run before EXECUTE; a first-pass CONDITIONAL routes to a plan supplement, never straight to EXECUTE.
4. **Supporting context files loaded**: `CLAUDE.md`, `process/context/all-context.md`, `process/context/tests/all-tests.md` (the only file in the tests group), `process/context/planning/all-planning.md` (routed, not deep-read: this plan follows the `vc-generate-plan` contract directly), `process/MASTER-PLAN.md` (grep-read for P2/T8/T23/T22 context), the SPEC, `api/main.py`, `api/tests/scripts/test_snapshot_workflow_schedules.py`, `api/data/cache.py:25-45`, `api/data/watchlist.py:30-50`, `api/analytics/cointegration/pairs_response.py:205-285`, P1's `api/scripts/BOOTSTRAP.md` and atomic-writes plan (read via `git show origin/claude/p1-pipeline:...`, never checked out), `regime-dashboard_PLAN_24-09-26.md` (house style for real-machine handoffs).
5. **Next step for a fresh agent**: run VALIDATE on this plan; then EXECUTE section A from step 1 (confirm the pytest baseline first). Recommended strategy: sequential, one `vc-execute-agent` (opus — the code-execution leg) because only one source file and a handful of new files are touched; every other phase runs sonnet. After EXECUTE, an independent `vc-tester` (sonnet) EVL run must reproduce G1-G5 and G7 (and G6 if runnable). Then hand section B to the user; do not mark `VERIFIED` until they confirm B8-B14.
6. **Validator expectations**: `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md`. Agent-surface parity validators are not affected (no agent or skill files touched).
7. **Hard stops for any agent picking this up**: never create paid infrastructure or a publicly reachable endpoint; never edit files outside the allowlist; never enable stage B before G-STAGEB; never claim a user-PC step as passed.

## Next Step

Say **ENTER VALIDATE MODE** to validate this plan. Do not enter EXECUTE until a validate-contract exists.
