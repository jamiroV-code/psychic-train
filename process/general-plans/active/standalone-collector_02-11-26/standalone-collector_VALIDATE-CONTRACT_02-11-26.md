# standalone-collector — validate contract (direct lane)

Scope: A-F of the envelope (standalone attention collector process, heartbeat + single-instance guard, read-only
`collector` status on GET /api/narrative/sources, small status box in the Discovery tab, launcher + README). No change
to pacing, budgets, evidence, X reader, coins or `api/data/attention_queries.json`; no dependency or .github edits.

Gates:
1. Red first: new tests committed failing before the implementation commit (runner, heartbeat, guard, status object,
   exact-key contract, web component states).
2. Runner (`python -m api.data.attention_collector`): flag `SCREENER_ATTENTION_PC_WORKER=1` required, else exit
   non-zero with a clear message and no thread; refuses (exit non-zero) when another fresh, live heartbeat exists;
   stops cleanly on SIGINT/SIGTERM/CTRL+C/console close (worker stopped, threads joined, heartbeat marked stopped,
   log handler removed). Tests use a fake worker/clock; no network, no leaked threads.
3. Heartbeat `<cache>/attention/_pc_state/collector_heartbeat.json`: written atomically (cache helper) at start and
   every <= 30 s; fields pid, started_at, last_beat (UTC ISO), mode (standalone|in_api), sources, version, stopped;
   stopped=true on clean stop. Same file for the in-API worker.
4. Guard: fresh (< 90 s) + other pid + pid alive -> refuse (reason code, `start_from_env` never raises, API lifespan
   unaffected). Stale heartbeat, stopped heartbeat, dead pid or own pid -> start allowed. Pid probe never signals
   a process (no `os.kill(pid, 0)` on Windows).
5. API: `collector` object on DiscoverySourcesResponse (optional, default None, always filled by build_sources):
   running | stopped | never_started | unknown from files only; per-source summary for xsearch and reddit reusing the
   health fields; missing state is null, never 0 or healthy. Exact-key tests updated deliberately.
6. Web: CollectorStatus box (role=status, aria-live=polite) next to the Sources panel; Running / Stopped / Not started /
   unknown; missing collector object -> unknown, never OK; per-source lines; web only formats. Vitest per state + tsc.
7. deploy/start-collector.ps1 (-DryRun, env guards, no secrets, no forbidden git words) + README section; every
   PowerShell command marked UNRUN; nothing registered or started.
8. Gates run once at the end: api/tests/analytics/attention, api/tests/data/attention,
   api/tests/data/test_attention_pc_refresh*.py, api/tests/tooling_guards, api/tests/deploy, routers discovery tests,
   web vitest + tsc (known Windows-host failures excepted); Linux CI on the draft PR is the judge.
9. Isolated smoke: temp cache root, no PC sources (fake discovery fetch_side or fakes), heartbeat appears, second start
   refused, CTRL+C stops cleanly, status object running -> stopped. No live process, cache or provider touched.
