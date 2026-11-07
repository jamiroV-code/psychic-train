# S-Relay slice report (07-11-26)

## 1. Status
CODE-COMPLETE on loopback fixtures and the spawned fake browser. LIVE-READY: NO. BG-1 stays FAIL (`containment_residual_unaccepted`, recorded 07-11-26 from BP1c on Edge 157.0.4341.42); the A19 self-test was NOT run on the installed Edge in this slice (see 9). Default off: nothing constructs a relay for collection yet; collection `launch()` still requires a matching admission record. Branch `claude/b2-validate`, not pushed.

## 2. Scope
Plan §S-Relay: A5-A9 (`browser_relay.py`), A19 (`browser_selftest.py`), browser guard chain link, firewall notes (read-only attestation only).

## 3. Changed paths
New: `api/data/attention/browser_relay.py`, `api/data/attention/browser_selftest.py`, `api/tests/data/attention/test_browser_relay.py`, `api/tests/data/attention/test_browser_selftest.py`.
Edited: `api/data/attention/browser_host.py` (Main-approved narrow split: `launch()` → `_launch(..., admission_run)`), `api/tests/tooling_guards/test_browser_host_guards.py` (relay/self-test guards), `api/tests/tooling_guards/test_reddit_collector_guards.py` (Main-directed table-H amendment).

## 4. What was built
- Relay: per-account, per-session, in-process asyncio server on the literal `127.0.0.1:0` only; modes `proxy|direct` (constructor refuses `refuse`, and `proxy` without a `PrivateRoute`); `select_mode(config, route, admitted)` = the B2 predicate (`direct` only when `x_proxy_required` is False, all three paths None and no route; partial/missing → `refuse`). CONNECT-only (other methods 405); strict authority (hostname, port 443; IP literals, userinfo, brackets, trailing dot, malformed → 403); effective allowlist = given surface hosts (explicit `.suffix` entries) or `BOOTSTRAP_HOSTS`; resolution through the injected resolver then REAL `x_proxy.public_address` (pins one address); `direct` dials the numeric address; `proxy` dials the resolved upstream, optional verified proxy TLS (CERT_REQUIRED enforced), then a numeric CONNECT built through B2 `ConnectFrame` (BP7: reused read-only) with relay-side `Proxy-Authorization` from the in-memory route. TLS stays end-to-end. Admission snapshot (revision, expiry, quarantine) checked before each CONNECT and polled every 50 ms while tunnels are open: failure aborts all tunnels and pins `proxy_admission_expired`/`proxy_quarantined`; upstream failure → 502, never direct. A6c `BROWSER_BACKGROUND["edge"]` suffixes → `background_refused` counts; refusal metadata hostnames only, ≤50 entries (overflow counted as `refused_other`). `write_health` writes the S-StatusAPI `_pc_state/browser_health.json` layout.
- Self-test (A19): `run(host, cache_root, enumerator, firewall, window)` launches the host's profile store `selftest` profile via `host._launch(admission_run=True)` through a relay with an EMPTY allowlist (forwards nothing), runs `CdpClient(pipe,"session_check",...).version()` (failure → `cdp_pipe_unavailable`, no record), keeps loopback TCP+UDP sentinels, polls `GetExtendedTcpTable` (IPv4+IPv6, owner PID) filtered to `job.pids()` for the whole window with owner type (browser/child). Outcomes: `contained` (attested rule + zero Established; non-Established = `blocked_attempts`), `tested_clean`, `accepted_residual` (only `vendor_cloud_443` with a matching hash-bound record, re-verified by `read_admission`), else `containment_residual_unaccepted`. Sentinel hit or forwarded CONNECT → `browser_unadmitted` (no record). Code-owned classes: `vendor_cloud_443` (Microsoft ranges incl. BP1c 52.97.x/40.99.x [INFERENCE: range ownership]), `lan_device`, `unclassified`. CLI `python -m api.data.attention.browser_selftest --binary --cache-root [--window]` (disposable temp profiles dir, removed after, `OWNER_DECISIONS` policy so it refuses until O-1/O-1b) and `--accept-residual D --approve D` (digest recomputed from the record's own classes; must be exactly `vendor_cloud_443`). Firewall attestation = read-only `Get-NetFirewallRule ... | Get-NetFirewallApplicationFilter` through an injected runner; never writes firewall state.

## 5. Interfaces
- `browser_relay.Relay(site, label, mode, *, revision, admission, hosts=None, route=None, browser="edge", resolver=None, dialer=None, proxy_context=None, clock)`; `.start() -> port`, `.close()`, context manager, `.health()`, `.failure`; `Admission(revision, expires_at, quarantined)`; `select_mode`; `write_health(cache_root, relay, profile_state=)`; `RelayFailure.reason`.
- Dialer contract kept from S-Fixtures: sync `dial(host, port, *, timeout)`; resolver async `(host, port) -> str`.
- `browser_selftest.run(...) -> dict` (`outcome`, `admission_digest`, `residual_digest`, `destination_classes`, `blocked_attempts`, `owners`, `product`, refusals); `accept_residual`; `classify`; `tcp_table`; `firewall_attested`.
- S-Cookie-C: construct `Relay` (guard currently allows only `browser_selftest.py`; S-Cookie-C extends the guard set with its own module), then `host.launch(label, profile, relay.port)`.

## 6. Tests run
Red first (run): `test_browser_relay.py` with the module absent → collection ImportError; `test_browser_selftest.py` + guards with the self-test absent → collection ImportError. Green (`UV_FROZEN=1 uv run --project api --frozen --group xreader pytest ... -q -rs`): `test_browser_relay.py` 30 passed; an intermediate run found 1 failure (CLI exit code on refusal), fixed. Final combined run `test_browser_selftest.py test_browser_relay.py test_browser_host_guards.py test_reddit_collector_guards.py test_browser_host.py test_browser_cdp.py` → 150 passed, 0 skipped, 0 failed (120 s). Real Edge never launched.

## 7. Data verification
Fixture runs write only under pytest tmp: `_probes/browser_admission_<digest>.json`, `_probes/residual_acceptance_<digest>.json`, `_pc_state/browser_health.json`, `_pc_state/browser_launches/selftest.json`. Health contains hostnames and counts only; credentials asserted absent from health/repr.

## 8. Error handling
Closed reasons: `proxy_not_admitted`, `relay_config`, `relay_start`, `relay_authority`, `proxy_admission_expired`, `proxy_quarantined`, `proxy_transport`, `cdp_pipe_unavailable`, `browser_unadmitted`, `containment_residual_unaccepted`, `tcp_table_unreadable`. Exceptions raised `from None`; nothing logged or printed except the CLI's one JSON line.

## 9. Deviations
- Host edit (approved by Main): `BrowserHost.launch()` now delegates to private `_launch(..., admission_run)`; only `browser_selftest` passes `admission_run=True` (guard-tested); collection launch still refuses without a matching record (guard test).
- A9 "constructed only by browser_host": the host does not construct the relay (S-BrowserHost passes the port in); the guard asserts the relay is constructed only in `browser_selftest.py` for now.
- Table-H guard amendment (Main-directed): `test_reddit_collector_guards.py` gains `BROWSER_NETWORK` = exact allowed network imports for `browser_relay.py` {asyncio, socket, ssl} and `browser_selftest.py` {socket, subprocess}, plus a planted-code test that other `browser_*`/`reddit_*` modules still fail.
- Stage 0 BP1c re-run and the A19 run on the installed Edge were NOT executed: the envelope forbids external network, and Edge's browser process itself makes direct TCP 443 connections (BP1c), and `launch` refuses under `OWNER_DECISIONS` until O-1/O-1b. BP7 is covered by the relay's live use of `ConnectFrame` in the proxy-mode tests.
- The production self-test's hostile pages (IP-literal/localhost/redirect/WebSocket/service-worker pages, relay outage) cannot be driven through the A3-restricted CDP client; the production run uses passive loopback sentinels + relay refusal counts + TCP table. Hostile host cases are proven on the wire by the fake-browser and raw-socket relay tests (relay enforcement, not Chromium behaviour).
- Vendor range table is code-owned and partly [INFERENCE].

## 10. Gate honesty
BG-1: FAIL (recorded `containment_residual_unaccepted`, Edge 157.0.4341.42); not re-run. BG-2: still pending on 157 (A19 `version()` round trip proven only on the fake). Live relay use remains blocked by `browser_unadmitted` / `containment_residual_unaccepted` / `profile_policy_unsatisfied`; O-2 decides acceptance or the firewall route.

## 11. Next
Owner: decide O-1/O-1b/O-2, then run `python -m api.data.attention.browser_selftest --binary "<msedge.exe>" --cache-root <cache>` and record the outcome as the BG-1/BG-2 evidence. S-Cookie-C constructs `Relay` per session and extends the constructor guard. S-OpsDeploy OD-5 generates the firewall text that `firewall_attested` reads.
