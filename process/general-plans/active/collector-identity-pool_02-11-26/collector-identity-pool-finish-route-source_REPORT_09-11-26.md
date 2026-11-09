# Route source feeder slice report (09-11-26)

## 1. Status
CODE-COMPLETE, fixture-proven only (EXPERIMENT tier, D-33). Branch `claude/route-source-free-proxies` (from `claude/b2-validate` at bfe569f6). Not LIVE-READY: no real list host, proxy, ipapi.co, X or Reddit was contacted; live yield, ipapi availability/limits and list-host behavior are UNVERIFIED.

## 2. Scope delivered
- New `api/data/attention/route_source.py` (the producer B2 lacked) and CLI `python -m api.scripts.route_feeder --queries ABS (--once | --loop [--interval 300..86400]) [--dry-run]`.
- Fetch: owner-allowlisted https list URLs only, same-host https redirects only (max 3), 2 MiB / 50000 lines, timeouts. Candidates: numeric, `is_global` (`x_proxy.public_address`), credential-free HTTP proxies; SOCKS, HTTPS-with-credentials, hostnames, private addresses and mail/admin ports dropped; deduped.
- Prescreen (max 300 per pass, 16 in flight): raw CONNECT to the policy echo origin, real TLS verification (MITM fails `tls`), two echoes that must agree (`rotating`), 5 s latency cap (`slow`), policy baseline sha256 (`baseline`); dedupe by exit IP; quarantined exits refused.
- Country without money: ipapi.co keyless JSON (`x_proxy.IPAPI`, already the B2 metadata provider) fetched through the SAME verified tunnel; max 15 per pass, cached 7 days; unknown country = rejection. Must equal the label's B1 identity country, plus timezone when the policy selects `ipapi` (so B2's own ipapi check agrees). Region/timezone/accept_language written to the assignment come from the identity (X: `x_account_identities`; Reddit: `reddit_proxy_experiment_identities`), so `parse_assignments` coherence and B1 equality hold. Choice documented: the repo has no offline GeoIP data; tzdb country tables only validate coherence.
- Assignment: sticky for healthy routes; replacement only on X pool `proxy_health == quarantined` for the current ID or `FAILURE_THRESHOLD` (2) consecutive failed feeder probes; replacement is a distinct same-country spare, old exit quarantined for `x_proxy_quarantine_seconds`, alert `route_replaced` in the status file, opaque change record `{at, label, from, to, reason}` in private state. No spare → old route kept, `no_spare` alert, B2 refuses that account; never direct. A file missing any X label is never published (`x_labels_unassigned`).
- Publication: single writer under `state_lock`, `atomic_bytes` with `policy.service_sid` (existing owner/SYSTEM ACL helpers), list before assignments, slots the old file references are never rewritten (new routes take unreferenced slots, else append); the composed bytes are validated with the real `parse_assignments(required=True, identities=…)` before writing. Unmanaged labels, owner lines and IDs carried over unchanged.
- Doctor check `route_source` (read-only; counts-only status file `<cache>/attention/_reports/route_source.json`).
- Docs: deploy/README.md "Route source feeder" section; decisions D-33.

## 3. Interfaces for later slices
- `route_source.run_once(config_path, deps, dry_run=) -> Result`; `Deps(net=Net(dial, tls, timeout), opener, publish, write_state, write_status, now, new_id, cache_root, repo_root, log)`; `status_path(cache_root)`.
- `route_feeder.main(argv, out=, deps=, sleep=, max_runs=)`.
- `collector_doctor.check_route_source(d, c)`.

## 4. Pool keys and defaults
No pool keys. New owner collector keys (all default off/empty, strict): `route_source_enabled` false, `route_source_list_urls` [], `route_source_allowed_hosts` [], `route_source_spares_per_country` 2 (0..10), `x_proxy_experiment_labels` [] (subset of `x_accounts`, needs `x_identity_enabled`), `reddit_proxy_experiment_identities` {} (keys = Reddit browser labels, coherent region/timezone/language). Enabled requires URLs, at least one experiment label and the three B2 paths. Private state: `<policy cache_dir>/route_source/state.json`.

## 5. Tests (red first)
`api/tests/data/attention/test_route_source.py` (loopback TLS origin + fake CONNECT proxies, synthetic public tokens mapped by the injected dialer, socket guard refuses non-loopback): candidate parsing, non-verifying TLS refused, redirect rules, prescreen rejects dead/non-CONNECT/MITM/rotating, wrong-country rejected, strict config, default off dials nothing, `--once` output accepted by the REAL `load_snapshot` and REAL `ProxyRuntime.admit` (request seam synthetic), stickiness, pool-quarantine replacement with change record and owner label untouched, probe-failure replacement after threshold, no-spare keeps route, missing X label never published, dry run, loop bounds, doctor states. Deviation: the module skeleton was written before the test file, so the red phase was not separately observed (see 7).

## 6. Verification commands
`uv run --project api --frozen python -m pytest api/tests/data/attention/test_route_source.py api/tests/data/attention/test_web_queries.py api/tests/scripts/test_collector_doctor.py api/tests/data/attention/test_x_proxy_snapshot.py api/tests/data/attention/test_x_proxy_policy.py api/tests/data/attention/test_x_proxy_admission.py api/tests/data/attention/test_x_proxy_runtime.py api/tests/data/attention/test_x_proxy_reddit.py api/tests/deploy api/tests/data/attention/test_x_window.py api/tests/tooling_guards -q`
Result (09-11-26, Windows, one run): 704 passed, 1 skipped, 0 failed (128.78 s); `test_route_source.py` alone: 45 passed.

## 7. Deviations and review blockers
- Red-first not observed as a separate failing run (tests written right after the module); review should treat the tests on their assertions.
- `test_web_queries.py::test_finish_keys_declared_optional_with_contract_defaults` key-set assertion extended with the new key group (additive).
- Reddit pool quarantine is not read (only X `x_pool.json`); Reddit managed routes rotate on feeder probe failures only.
- Owner credentialed/HTTPS routes on a managed label are not probed by the feeder (pool quarantine still applies).
- Any publication changes the raw list, which by the existing B2 raw-change rule re-revisions every account once; publication happens only on a real change.
- No scheduled task registration was added (deploy scripts untouched); the runbook gives the `--loop` / `--once` commands.

## 8. Rollback
Set `route_source_enabled` false; the last published files stay valid B2 input. Restore the owner's own list/assignment backup if wanted. Code revert: drop the branch.

## 9. Risks
High ban risk (datacenter/burned exits), short route life, ipapi.co free-tier limits or blocks through public proxies (then no country → no spare), list hosts changing format, exit-country spoof by a proxy is not possible over verified TLS but ipapi accuracy is not verified.

## 10. Owner actions
Add `https://ipapi.co` to the policy `allowed_origins`; pick list URLs and allowed hosts; name disposable experiment labels; run `--once --dry-run`, then `--once`, then `--loop` as the collector identity; watch `route_source` in the doctor.

## 11. Changed paths
api/data/attention/route_source.py (new), api/scripts/route_feeder.py (new), api/data/attention/web_queries.py, api/scripts/collector_doctor.py, api/tests/data/attention/test_route_source.py (new), api/tests/data/attention/test_web_queries.py, deploy/README.md, process/context/decisions.md, this report.

## v2 (09-11-26): bank, whole-list scanner, site check, smart assignment, schedule

### Why
Owner (jamir) wants free proxies tested, a self-adapting pool that replaces breaking proxies automatically and a list kept up to date autonomously, at no cost. Measured live 09-11-26 on the home PC with a THROWAWAY script that called the feeder's own `prescreen` (not the feeder; policy at the owner's private path): 5946 candidates from 3 lists (monosans http 623, TheSpeedX http 2430, proxifly http 4610 lines); a random 400 prescreened with 16 threads took 180 s and passed 3 (0.75%); rejections dead 305 (connection failures/timeouts dominated wall time), tls 28, no_connect 28, closed 19, slow 17; 2 of the 3 passers were already dead minutes later at the country lookup; the survivor was NL, 0.5-3.5 s latency. v1 (300 candidates, 16 in flight, only when short) cannot keep a pool alive at that yield and lifetime.

### Delivered
- **Bank** (private state v2, `<cache_dir>/route_source/state.json`, atomic, owner/SYSTEM ACL via `write_state`): per candidate `first_seen`, `last_listed`, `last_probe`, `last_ok`, `ok_streak`, `fail_streak`, `exit_ip`, `country`, `timezone`, `latency` (EWMA 0.3), `dead_until`, `reach{site}`, `reach_at`. Dead backoff: never-ok 6 h, once-ok 30 min, doubling per failure, max 24 h. Bounded: 20000 entries; unlisted for 3 days and not live in 2 h is forgotten, then lowest score. A v1 state migrates (owned IDs, quarantine, geo cache, change log kept). No secrets: candidates are public list entries.
- **Scanner** (`route_source.scan`): every pass fetches all lists and scans the whole bank in order assigned -> never-probed -> known by score, skipping dead-until; at most `route_source_scan_concurrency` (default 96, 1..256) in flight; no probe starts after `route_source_scan_budget_seconds` (default 240, 10..3600; unstarted counted `scan_budget`, they lead the next pass). Proxy dials use `Net.connect_timeout` 3 s; I/O keeps 8 s; byte/line caps and verified-TLS rules unchanged. Known candidates get one echo recheck of their exit instead of the full prescreen. ipapi lookups max 60 per pass, cached 7 days.
- **Site check** (`route_source_site_checks`, default `{"x": true, "reddit": true}`, only for exits in an identity country): through the proxy, verified TLS CONNECT to x.com:443 / www.reddit.com:443, `GET /` without cookies, status must be 200 and the first 256 KiB must not contain a block/interstitial marker; refusals count `reach_x` / `reach_reddit`, rechecked hourly; assigned routes every pass.
- **Smart assignment**: score = ok streak, bank age, latency EWMA, recent failures. Usable = verified this pass, identity country (+timezone under `ipapi`), site check passed, distinct exit, not assigned/quarantined. Pre-emptive replacement on pool quarantine, first probe failure (`probe_failed`), site block (`site_blocked`) or latency EWMA > 3 s (`degraded`, only when a candidate exists); healthy routes never churn; all replacements are one publication; change record + `route_replaced` alert as v1. Then `route_source_spares_per_country` best usable per identity country are kept and refilled each pass. No usable candidate -> `no_spare:<country>` alert/reason; route kept; never a home-IP fallback.
- **Status/doctor**: status `bank` block (counts only): `size`, `verified_live`, `spares_per_country`, `no_spare`, `last_scan_seconds`, `scanned`, `oldest_assigned_age_hours`. Doctor PASS reason `experiment_assigned_N_of_M_spares_K_bank_B_live_L`; WARN `route_source_no_spare:<C>`. Feeder status line adds `bank= live=`.
- **Coverage**: `route_feeder --coverage` (read-only, no network/lock/write) prints verified distinct exits per country from the bank (last 2 h).
- **Schedule**: `deploy/register-route-feeder-task.ps1` (`mysite-route-feeder`, at logon, Interactive/Limited, refuses elevation and a token SID different from the policy `service_sid` with exit 4, runs `uv run --project api --frozen python -m api.scripts.route_feeder --queries <abs> --loop --interval <600>`, restart 3x1 min, one instance, no time limit, `-Remove`). Default loop interval 1800 -> 600.

### Fixture-proven (tests, red first: the new tests failed on `Net(connect_timeout=...)` before the module change)
`test_route_source.py` (60 tests): bank persistence across passes and dead-TTL skipping with growing backoff; 120 blackholed hosts + 1 good scanned inside the budget with only the short connect timeout (concurrency 64, 0.25 s: under 8 s vs 30 s serial); budget stops new probes and the next pass resumes with never-probed first; site check rejects a 403 and a Cloudflare interstitial and is switchable per site; spares kept per country and refilled while the assigned route stays; pre-emptive replacement of one label in one publication with change record while the other label's healthy route stays; all-dead keeps the files, `no_spare:US`, no direct target dial; bank summary counts only; coverage CLI read-only and empty before a scan; default off dials nothing; doctor shows bank counts. `api/tests/deploy/test_deploy_collector_shape.py`: scheduler script and README text-shape guards (no PowerShell executed).

### Only measured live / UNVERIFIED
- The feeder itself (v1 or v2) has NOT run live; the numbers above come from a throwaway script reusing `prescreen`.
- Real scan duration at 96 in flight / 3 s connect on the home connection and router (NAT table, Windows socket limits) is unmeasured.
- x.com / www.reddit.com landing-page behaviour through public proxies (status codes, redirects, interstitial wording) and the `BLOCK_MARKERS` list are unverified; x.com may answer `GET /` with a redirect, which v2 treats as a refusal (then every X candidate fails `reach_x`; the owner can switch the X check off).
- ipapi.co keyless limits through many public exits are unverified (60 lookups per pass worst case).
- Score weights, 3 s degradation threshold and backoff values are judgement, not measured.
- The scheduled task script is UNRUN (no PowerShell executed).

### Deviations
- Reddit pool quarantine still not read (unchanged from v1).
- A wrong-country exit is no longer a rejection: it stays in the bank for `--coverage`.
