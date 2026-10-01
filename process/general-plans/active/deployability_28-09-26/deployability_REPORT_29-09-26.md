---
phase: deployability-section-a
date: 2026-09-29
status: COMPLETE_WITH_GAPS
feature: none
plan: process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md
---

# Deployability (P2 Phase 1) — Section A EXECUTE Report

**TL;DR** — Section A (steps 1-9) is **CODE DONE, not VERIFIED**. All container gates are green:
G1-G5 and G7, plus G6 (Playwright 55/55) which turned out to be runnable. Full suite is
714 baseline + 38 new passing + 1 strict-xfail = **752 passed / 5 deselected / 1 xfailed, 0
failures**. One real finding: an aged price cache on `/api/screener/board` has no staleness
marker (recorded as xfail(strict), handed to the screener's owner). Nothing in Section B has been
run or is claimed; the `.ps1` files are only text-checked (no PowerShell in the container).

## What Was Done

| Step | Result |
|---|---|
| 1 Baseline | Branch `claude/p2-deploy`. `uv run --project api pytest api/ -q` = **714 passed, 5 deselected** (160s) — matches VALIDATE's number exactly. |
| 2 Read-only facts | (a) `credentials` in `web/lib web/components web/app` (non-test): 1 hit, `web/lib/format-unavailable-reason.ts:51` — a user-facing string "Reddit credentials not configured…", not a fetch option; no `credentials: "include"` exists. (b) POST/DELETE/PUT/PATCH/Content-Type (non-test): 0 hits. (c) `uvicorn --help` shows `--host` and `--port`. (d) `pnpm install --frozen-lockfile` worked; `next start --help` confirms `-H, --hostname` and `-p, --port`. Note: `next start`'s default hostname is `0.0.0.0`, so the explicit `-H $ip` in `start-web.ps1` is load-bearing. |
| 3 Red tests | 7 test files in `api/tests/deploy/` (plus conftest). Red run: **24 failed, 14 passed, 1 xfailed** — all CORS/docstring (10) and deploy-shape (13) tests red as planned, plus the aged-cache test (a wrong ChartBar key in the test itself, fixed: the model field is `close`). Health and env-override tests green as predicted. |
| 4 `api/main.py` | Docstring rewritten (run-command concern, Tailscale posture, `deploy/README.md`); `_parse_cors_origins`, `_cors_options` added; `allow_credentials=False`, methods `GET/POST/DELETE`, headers `Content-Type`. G1+G2: green. |
| 5 Empty/aged cache | Empty-cache tests green with no code change (F7 confirmed). Aged cache: regime serves `broad_dollar` as `status: stale` with a reason — honest. Screener: **finding**, see below. G3: green (1 strict xfail). |
| 6 `deploy/` | README, config example, `_common.ps1`, `start-api.ps1`, `start-web.ps1`, `build-web.ps1`, `register-tasks.ps1`. G4: 14/14 green. |
| 7 Scope | `test_lane_scope.py` ran on-branch (not skipped): pass. G7 command: every changed/untracked path is under `api/main.py`, `deploy/`, `api/tests/deploy/`, or this task folder. |
| 8 Regression | See Test Gate Outcomes. Plan validator: 0 failures, 0 warnings. |

### Red-then-green evidence

| Run | Result |
|---|---|
| `pytest api/tests/deploy -q` before `main.py`/`deploy/` | 24 failed, 14 passed, 1 xfailed |
| after `main.py` edit (G1/G2/G3 files) | 22 passed, 1 xfailed |
| after `deploy/` files (first try) | 37 passed, 1 failed (`register-tasks.ps1` comment said "SYSTEM"; comment reworded), 1 xfailed |
| final `pytest api/tests/deploy -q` | **38 passed, 1 xfailed** |

## Findings

1. **Aged OHLCV cache has no staleness marker on `/api/screener/board` (plan step 5 / R9 / gap G-D).**
   With a 30-day-old cache and the exchange unreachable, the adapter correctly reports status
   `unavailable`, but `screener_board._chart_series` sets `reason` only when `available` is false,
   and `ChartSeries` has no `as_of`/stale field. Observed response: `"available": true, "reason": null`.
   The screen shows old prices with no sign they are old. Not fixed (router/model are out of lane).
   Pinned as `test_aged_cache_regime_and_screener_never_500_and_no_nan[screener_chart_carries_staleness_marker]`
   with `xfail(strict=True)` — it will turn red (XPASS) the day the owner adds a marker, so the
   xfail is then removed. **Requirement to the screener's owning lane (momentum-screener /
   `claude/ui-shell` for rendering):** carry the adapter's `stale`/`unavailable` status, or the
   last bar's date, into `ChartSeries` when cached bars are served after a failed refresh.
   AC11 stays CONDITIONAL. The regime half of AC11 is honest (`status: stale`, a reason, `last_date`).
2. `next start` binds `0.0.0.0` by default — the launcher always passes `-H <tailscale-ip>`; a shape test pins it.

## Test Gate Outcomes

| Gate | Command | Result |
|---|---|---|
| G1 | `uv run --project api pytest api/tests/deploy/test_main_cors.py -q` | 10 passed |
| G2 | `uv run --project api pytest api/tests/deploy/test_health_endpoint.py -q` | 2 passed |
| G3 | `uv run --project api pytest api/tests/deploy/test_fresh_deploy_degrade.py -q` | 10 passed, 1 xfailed (finding 1) |
| G4 | `uv run --project api pytest api/tests/deploy/test_deploy_config_shape.py -q` | 14 passed — **shape only, does not prove the scripts run** |
| G5 | `uv run --project api pytest api/ -q` | **752 passed, 5 deselected, 1 xfailed** (714 + 38 + 1 xfail), 0 failures; `git diff --check` clean |
| G6 | `cd web && PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e` | **55 passed** (2.1 min), one run — the tightened CORS did not break the real client |
| G7 | `git diff --name-only $(git merge-base HEAD origin/main); git ls-files --others --exclude-standard` + `test_lane_scope.py` | all paths in allowlist; test passed (ran, not skipped) |
| isolation | `test_real_data_paths_untouched` + `git status --short api/data` before/after full suite | unchanged / empty both times |
| B5-B15 | user-run on Windows | **NOT RUN — not claimed** |

## What Was Skipped or Deferred

- Section B (all user-PC steps) — by design; the user runs it.
- AC9 workflows, AC10 resume script, AC12 atomic writes, AC13 context entry — other lanes (REQ-P1-1..4, REQ-CTX-1).

## Plan Deviations

All within the blast radius (allowlisted paths only):

1. **Extra test-support files** `api/tests/deploy/conftest.py` (offline stubs, socket guard, real-data snapshot) and `api/tests/deploy/test_zz_real_data_guard.py` (hosts `test_real_data_paths_untouched`, named `zz` so it runs last). The plan named the guard but not its file.
2. **The step-5 xfail is a parametrize case** of the named test `test_aged_cache_regime_and_screener_never_500_and_no_nan` (cases `never_500_and_no_nan`, passing; `screener_chart_carries_staleness_marker`, strict xfail), so the test name stays verbatim while only the marker assertion is xfailed.
3. **Offline stubbing went wider than the plan listed**: besides ccxt + the three narrative adapters, the regime endpoint reaches FRED, DefiLlama and Farside, so `fred_adapter.fetch_series`/`fetch_net_liquidity`, `defillama_adapter.fetch_stablecoin_supply` and `etf_flows_adapter.fetch_btc_spot_flows` are stubbed with their own failure shapes (FRED serves cached data as `stale`, exactly like the real adapter after a failed fetch). A socket guard rejects any non-loopback connect.
4. `test_scheduled_scripts_never_run_stage_b_or_no_history_jobs` passed vacuously in the red run (no `.ps1` existed yet); it is meaningful only after step 6. Noted for honesty.

## Test Infra Gaps Found

- No PowerShell in the container: `.ps1` validity rests on shape tests + user steps B5/B6. **Backlog stub: "PowerShell parser gate in CI"** (needs `.github/workflows/`, P1's lane; e.g. a `windows-latest` job running `[System.Management.Automation.Language.Parser]::ParseFile` over `deploy/*.ps1`).
- **Backlog stub: "container-runnable real-browser CORS check"** — G6 did run this session (55/55), but it depends on `pnpm install` and the browser path being available; a Playwright spec that fetches from a second origin against the tightened allow-list would make the CORS regression explicit rather than incidental.
- Unconfirmed names (E6), written as planned, proof left to B5/B11: `New-ScheduledTaskSettingsSet -RestartCount/-RestartInterval/-ExecutionTimeLimit/-StartWhenAvailable/-AllowStartIfOnBatteries/-DontStopIfGoingOnBatteries`, `New-ScheduledTaskPrincipal -LogonType Interactive -RunLevel Limited`, `New-ScheduledTaskTrigger -AtLogOn -User`, `Register-ScheduledTask -Force`, Tailscale CLI `ip -4`, `New-NetFirewallRule -InterfaceAlias Tailscale`.
- CONTEXT_PARTIAL: none.

## Closeout Packet

- Selected plan: `process/general-plans/active/deployability_28-09-26/deployability_PLAN_29-09-26.md`
- Finished: Section A steps 1-9.
- Verified in container: G1-G7. Unverified: every Section B step; PowerShell parse/runtime; Tailscale/firewall/Task Scheduler behavior.
- Remaining: EVL confirmation run (vc-tester), commit (orchestrator), then the user's Section B walkthrough; REQ handoffs incl. finding 1.
- Classification: **Keep in active/testing** — Section A is CODE DONE, not VERIFIED.
- Follow-up plan stubs created: none (backlog stubs recorded above, per plan step 9).

## Forward Preview

### Test Infra Found
- `api/tests/deploy/conftest.py::offline_providers` stubs every provider reachable from the four screen endpoints; reusable for any future endpoint test.
### Blast Radius Changes
- `api/main.py` CORS: no credentials header; preflight for methods other than GET/POST/DELETE or headers other than Content-Type is rejected.
### Commands to Stay Green
- `uv run --project api pytest api/ -q` → 752 passed / 5 deselected / 1 xfailed
- `uv run --project api pytest api/tests/deploy -q` → 38 passed / 1 xfailed
### Dependency Changes
- None (no new Python or web dependency).
