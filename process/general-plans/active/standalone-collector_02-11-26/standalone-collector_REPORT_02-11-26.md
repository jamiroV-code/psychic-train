# standalone-collector: completion report (02-11-26)

## 1 Task ID
standalone-collector (A-F). Branch `claude/standalone-collector`, draft PR #231 (https://github.com/jamiroV-code/psychic-train/pull/231). Base origin/main f32a00df.

## 2 Outcome
done. Linux CI on the final head is the judge; the result is in the PR checks.

## 3 Summary
- A: `python -m api.data.attention_collector` runs the existing worker through `start_from_env(mode="standalone")`. Pacing, budgets, evidence, the rotating log and the lazy X import are unchanged. It needs the flag (exit 2 without it) and stops cleanly on SIGINT, SIGTERM, SIGBREAK and the Windows console close, logoff and shutdown events.
- B: `collector_heartbeat.json` is written atomically at start, every 30 s and with `stopped: true` on a clean stop, in both modes. A start is refused while another process's heartbeat is fresh (< 90 s) and its pid is alive. A stale or stopped heartbeat, a dead pid and an unreadable file never block. `start_from_env` never raises.
- C: `GET /api/narrative/sources` gains an optional `collector` object: running, stopped, never_started or unknown, with a reason, times, age_s, mode, version and one xsearch/reddit summary that reuses the health fields. Files only.
- D: the `CollectorStatus` box appears above the collapsed Sources table (role=status, aria-live=polite). It shows Running, Stopped, Not started or unknown, and a missing object reads as unknown.
- E: `deploy/start-collector.ps1` and the README section "Collector (separate from the API)" (switchover steps C1-C5 and the `mysite-collector` task commands). Everything is UNRUN and nothing is registered.
- F: no change to coins, sources, `attention_queries.json`, dependencies, `.github/` or the `api/main.py` lifespan call.

## 4 Files changed
New: `api/data/attention_collector.py`, `api/data/attention/collector_heartbeat.py`, `web/components/narrative/CollectorStatus.tsx`, `deploy/start-collector.ps1`, `api/tests/data/attention/test_collector_heartbeat.py`, `api/tests/data/test_attention_pc_refresh_collector.py`, `api/tests/deploy/test_deploy_collector_shape.py`, `web/components/narrative/__tests__/CollectorStatus.test.tsx`, this folder's VALIDATE-CONTRACT and REPORT.
Changed: `api/data/attention_pc_refresh.py` (registry: guard, heartbeat, `mode`), `api/analytics/attention/sources.py` (`_collector_status`), `api/models/discovery.py` (`DiscoveryCollectorSource`, `DiscoveryCollectorStatus`, `collector` field), `web/lib/types/discovery.ts`, `web/lib/source-health.ts` (exports `utc`), `web/components/narrative/DiscoverySourcesPanel.tsx` (renders the box, 5 lines), `deploy/README.md`, `api/tests/analytics/attention/test_sources.py` and `api/tests/routers/test_discovery.py` (exact-key sets plus the collector cases), `api/tests/data/test_attention_pc_refresh_stream.py` (the worker fakes gain `streams = {}`).

## 5 Commits
`claude/standalone-collector`: 6972aa19 (red tests), e505751d (Python implementation), d28a39d4 (web box), d8c189b5 (red deploy guards), fb176adb (launcher and README), ecc27e6f (heartbeat path bound at start, Windows sharing-violation retry, stream fakes), then this report.

## 6 Tests run
All on the local Windows host. Threads were capped at 1 for BLAS.
- Red: `pytest api/tests/data/attention/test_collector_heartbeat.py api/tests/data/test_attention_pc_refresh_collector.py ...` failed with 2 collection errors (missing modules), 02-11-26 ~02:12Z. `vitest run components/narrative/__tests__/CollectorStatus.test.tsx` failed (module missing), ~02:19Z. `pytest api/tests/deploy/test_deploy_collector_shape.py`: 4 failed, 1 passed, ~02:23Z.
- Gate: `pytest api/tests/analytics/attention api/tests/data/attention api/tests/data/test_attention_pc_refresh.py api/tests/data/test_attention_pc_refresh_stream.py api/tests/data/test_attention_pc_refresh_collector.py api/tests/tooling_guards api/tests/deploy api/tests/routers/test_discovery.py` at fb176adb + the uncommitted heartbeat fixes: 1931 passed, 22 failed, 3 skipped, ~02:53Z. 13 failures are the known host quirk ("handler must not reach the network": 12 routers/test_discovery and 1 test_universe_classes end-to-end). The other 9 were `test_stream_flag_only_exact_one_enables`: its worker fake had no `streams`. Fixed in ecc27e6f. `test_attention_pc_refresh_stream.py` then passed 89 of 89 (~02:57Z) and `test_collector_heartbeat.py` passed 28 of 28 three times in a row.
- An earlier gate run found a heartbeat test that could leak its thread on Windows. That thread then wrote a heartbeat into this worktree's own `api/data/cache`, which tripped `test_zz_real_data_guard`. Fixed: the test always stops the thread, the heartbeat binds its path at start, and reads and writes retry a sharing violation. The stray file in this worktree was removed. The live cache was never touched.
- Web at ecc27e6f: `pnpm exec vitest run` passed 67 files / 630 tests, `pnpm exec tsc --noEmit` was clean, ~02:59Z.
- PowerShell: `Parser::ParseFile(deploy\start-collector.ps1)` gave 0 errors. Parse only; the script was not run.
- Isolated smoke at fb176adb, ~02:27Z (a script outside the repo; temp cache root; `fetch_side` gave no PC source; sockets blocked by a `sitecustomize`, with a child probe printing "network blocked in smoke"):
  - Status through the real route (`TestClient`, no lifespan): `never_started/no_heartbeat` before the start.
  - Child `ac.run()` with real signal handlers: the heartbeat appeared (`mode standalone`, `sources []`, `version fb176adbb185`) and the status read `running`, age 0.1 s.
  - A second `python -m api.data.attention_collector` with the flag exited 3 (`another-instance`).
  - CTRL+BREAK to the child: log `stopping: signal=SIGBREAK`, exit 0, heartbeat `stopped: true`, status `stopped/stopped_cleanly`.
  - The module entry without the flag exited 2 with the message.
  - Restarted after the clean stop, it ran. After a hard kill (TerminateProcess) the status read `stopped/process_gone`.
  - Only `attention_pc.log` and the heartbeat were written under the temp root.
- Browser (bounded): the box's static markup with `app/globals.css`, in Edge through Playwright (one browser, file URL, no server) at 375/768/1280. The running, stopped and missing states wrapped with `scrollWidth == viewport` (375/768/1280). The screenshot at 375 is readable.

## 7 Tests NOT run
- Linux CI results: the PR checks are the judge; the result is in the hand-off message.
- A real CTRL+C keypress in a console and a real console window close. Covered instead by `signal.raise_signal(SIGINT)` in-process, CTRL+BREAK to a child process, and a unit test of `console_event`. The `SetConsoleCtrlHandler` registration itself is unproven against a real close.
- The full /narrative page in a browser: there was about 1.1 GB free RAM, so no Next server and API were started. The width check covered only the box with the app CSS, not its place inside the Discovery panel's light surface.
- Any PowerShell launch, `-DryRun` included (it would read the live deploy config). No task was registered and no live process was touched.
- The real collector with real sources (forbidden by scope).

## 8 Deviations
- The box is rendered by `DiscoverySourcesPanel`, above its collapsed `<details>`, and not by `DiscoveryTab` directly. This reuses the single `/sources` fetch, and `DiscoveryTab.tsx` is unchanged. To keep the diff small, the panel's existing JSX was not re-indented inside the new fragment.
- `start-api.ps1` is unchanged: removing the flag from the API env is an owner step (C2). Clearing it in the launcher would stop collection at the next API restart, before the collector is set up.
- The heartbeat records a short `version` (the commit, read from the git files with no subprocess) and `running_sources`. Both are additive.
- Residual race: two starts in the same instant can both pass the heartbeat check, because there is no OS lock (documented in the module docstring).

## 9 Blockers
None. Risks:
- Until C2 is done, a user-level flag lets the API and the collector compete: whichever starts first wins and the other refuses. This is safe (no double spending) but can surprise.
- Whether `Stop-ScheduledTask` also ends the `uv`/python child is unverified ([INFERENCE]). The README gives the heartbeat pid as the fallback.

## 10 Follow-up
- The owner runs README steps C1-C5 and optionally registers `mysite-collector`, then reports the box text.
- The host guide `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-server-host-guide_30-10-26.md` still describes the in-API worker. It needs a doc refresh (planner's call).

## 11 Context cost
Loaded: AGENTS.md (entry set and permissions), master-planner.md sections 6 and 9 and one existing VALIDATE-CONTRACT as a format example, attention_pc_refresh.py, sources.py, models/discovery.py, the related tests, DiscoveryTab/DiscoverySourcesPanel/source-health/types, deploy scripts, README and guards. About 160k tokens. Tools: read, bash, edit, write, grep, glob, eval; no subagents.
