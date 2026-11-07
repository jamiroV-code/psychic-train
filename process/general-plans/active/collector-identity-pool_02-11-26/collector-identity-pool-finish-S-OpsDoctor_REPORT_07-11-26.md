# S-OpsDoctor slice report (07-11-26)

## 1. Status
CODE-COMPLETE (targeted tests green). Stage 11, branch `claude/b2-validate`, committed locally, not pushed. Not LIVE-READY: no owner run of `deploy/doctor.ps1`, and `--live` reports every live probe `needs_probe` until owner-approved records exist.

## 2. Scope delivered (OD-1)
- New `api/scripts/collector_doctor.py`: `python -m api.scripts.collector_doctor [--queries ABS] [--json] [--live] [--selftest]`.
  - States PASS/WARN/FAIL/UNKNOWN, each with a reason code and a fix hint. Missing owner input → WARN. Broken or unsafe input → FAIL. Absent or unreadable evidence → UNKNOWN, which is never PASS.
  - Exit codes: 2 any FAIL, 1 any WARN/UNKNOWN, 0 only when all PASS. The overall state is ordered FAIL > WARN > UNKNOWN > PASS.
- **Checks:**
  - Config and X: `config` (strict `web_queries.load`), `x_env`, `x_pin`, `x_curl`, `x_accounts` (sizing: about 4, worst 6), `x_backfill` (> 7 → WARN), `x_rest_ready`, `x_cookies` (ages and harvest state).
  - Proxies: `proxy_files` (missing files listed by key), `private_acl` (B2 `verify_private`), `proxy_admission` (freshness), `proxy_quarantine`, `proxy_distinct`.
  - `query_ids`.
  - Browser: `browser_path`, `profile_acl` (A10 root), `profile_unique` (A11 across both sites), `relay_refusals`, `browser_live` (`blocked(<reason>)` from `browser_host.read_admission`), `containment`, `firewall_rule`, `memory` (against `browser_memory_floor_mb`), `kernel_lock`.
  - Reddit: `reddit_accounts` (ready/locked), `reddit_live_gates` or `reddit_surface` (`probe_owner.verify_gate` per enabled section), `gate_<section>` (StatusAPI `<store>_health.json`), `feed_methods` (stale from 13-11-26).
  - Ops: `stage3_trigger`, `disk`, `scheduled_tasks`, `heartbeat`, `daily_report` (yesterday's completeness), `facts_retention`.
  - `--live`: `live_PX1..PX6`, `live_PR1`/`live_PR2` (verify), `live_PR5` from `probe_owner.latest_record`. These gate LIVE-READY only.
  - `--selftest`: `selftest`.
- **Stage 3 trigger (AC16):** "gateway not built: trigger met/not met" is measured from the `x_pool.json` route evidence. The trigger is met when every configured routed account is quarantined, which means the built-in list cannot manage any route. It is UNKNOWN (`trigger_unmeasured`) when routing is not in use or there is no evidence.
- **`firewall_rule`:** `present|absent|unknown` through the injected `query_runner`, using a read-only `Get-NetFirewallRule` count. Scheduled tasks use a read-only `Get-ScheduledTask` count. Off Windows the answer is `unknown`.
- **`--selftest`:** calls the injected `selftest_runner(argv) -> exit code` with `[python, -m, api.tests.cycle.acceptance]`. A pass never turns a pending live check into PASS.
- **Output:** writes `<cache>/attention/_reports/doctor.json` in the S-StatusAPI §7 layout `{state, checked_at, failures, warnings}`, plus `checks[{name, state, reason}]`. The `warnings` list contains the WARN and UNKNOWN names. The doctor never prints a value, path, IP, hostname or label.
- New `deploy/doctor.ps1` (`-QueriesPath -Json -Live -SelfTest`). It sets the collector's cache and X environment, clears proxy variables, and passes the exit code through. It is marked UNRUN.

## 3. Interfaces for later slices
- `collector_doctor.Deps` holds injectable `query_runner`, `selftest_runner`, `private_verifier`, `profile_verifier`, `machine_lock`, `memory`, `browser_version`, `disk_free_mb` and `dist_lookup`.
- Functions: `run_checks(deps, live=, selftest=)`, `document`, `exit_code`, `overall`, `doctor_path`, `main(argv, out=, deps=)`.
- S-E2E-Cycle C13 passes the real runner (`default_selftest_runner`) or calls `main`.
- S-OpsDeploy: `start-collector.ps1 -Doctor` can call `deploy\doctor.ps1`. The firewall rule display name constant is `FIREWALL_RULE_NAME`.

## 4. Pool keys and defaults
None. The doctor is read-only. Its only write is `_reports/doctor.json`.

## 5. Tests (red first)
- **Red:** `api/tests/scripts/test_collector_doctor.py` was run with the module absent and gave a collection ImportError (1 error).
- **Green:** 13 tests in the new file cover:
  - exit codes, and UNKNOWN never counting as PASS
  - the no-config doctor.json read back through the real `sources._doctor`
  - invalid config → FAIL with no echo
  - the full check set
  - pending evidence never PASS even after the selftest passed
  - firewall present/absent/unknown, with the query verified read-only
  - the selftest injected runner and its argv
  - the Stage-3 trigger states
  - feed methods stale after 13-11-26
  - paths and secret marker never printed, and a missing browser → FAIL
  - proxy missing files listed by key
  - socket connect refused for the whole run
  - the ps1 shape
- **Gate:** the new file plus `test_sources_finish_status.py` gave 41 passed.

## 6. Verification commands
`UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/scripts/test_collector_doctor.py api/tests/analytics/attention/test_sources_finish_status.py -q -rs`

A real local smoke run (no `--queries`) exited 1. It showed `config` WARN, `firewall_rule: absent`, `stage3_trigger` UNKNOWN, `scheduled_tasks registered_1_of_2`, `heartbeat never_started`, no daily report, and `facts_retention` UNKNOWN.

## 7. Deviations and review blockers
- **`--live`:** the envelope forbids network use, so `--live` reads recorded live probe evidence offline. It does not send requests. Live requests stay with `probe_owner --approve`.
- **`profile_acl`:** this check calls `ProfileStore._check(root, "", root=True)`, a private method of S-BrowserHost that is read-only. No public wrapper was added because the file is not owned by this slice.
- **`proxy_distinct`:** it compares X `proxy_id`s from `x_pool.json` only. Reddit route ids are not in a nonsecret state file, and the doctor does not open the private assignments file.
- **`kernel_lock`:** it does a non-blocking acquire and an immediate release. A collector that tries to launch at that same moment would get `browser_busy` once.
- **`x_cookies`:** it reads the nonsecret cookie-age file through `twscrape_reader.cookie_ages`, and harvest state from `x_pool.json`. `profile_logged_in` cannot be checked offline and has no separate check; the session check reports it.
- **Thresholds:** the Stage-3 trigger rule (all routed accounts quarantined) and the disk thresholds (1 GB FAIL, 5 GB WARN) are this slice's choices. The SPEC says "measured evidence" and gives no number.

## 8. Rollback
Revert this commit. Then delete `_reports/doctor.json`; the status box omits the doctor once the file is gone.

## 9. Risks
- The OS queries spawn PowerShell, which takes about 1–3 s each on Windows.
- The doctor exits 1 until every owner input and all evidence exist. That is by design.

## 10. Owner actions
- Run `deploy\doctor.ps1 -QueriesPath <private file>` once and record the result.
- Run `-Live` after the approved probes.

## 11. Changed paths
api/scripts/collector_doctor.py, api/tests/scripts/test_collector_doctor.py, deploy/doctor.ps1, this report.
