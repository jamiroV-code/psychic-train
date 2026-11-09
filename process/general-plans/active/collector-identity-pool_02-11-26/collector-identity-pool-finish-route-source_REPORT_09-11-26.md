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
