---
name: report:collector-identity-pool-b2-backend-acceptance
description: "Independent locked backend acceptance: full run failed, exact execution evidence and snapshot/proof limitations."
date: 04-11-26
metadata:
  node_type: memory
  type: report
  feature: collector-identity-pool
  phase: B2
---

# Collector identity pool B2 — independent backend acceptance

## 1. Task ID

B2BackendAcceptance. Run one complete locked backend acceptance and the authorized tracked whitespace check; own this report only. Implementation and regression expectations were not edited by this tester.

| Context field | Value |
|---|---|
| feature | collector-identity-pool |
| phase | EVL — independent backend acceptance |
| session-goal | Independently exercise the complete locked B2 backend without feature cuts, live traffic or waived required cases |
| branch | claude/b2-validate |
| worktree | C:/Users/jamir/.herdr/worktrees/my_site/wt-b2-validate |
| context-group | operating-instructions; tests/all-tests |
| blast-radius-packages | api source/tests; read-only deploy/process contracts |
| active-plan | process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md — B2 |
| test-runner | pytest, frozen xreader group |
| validate-contract | sibling collector-identity-pool_VALIDATE-B2_03-11-26.md |

Loaded skills: vc-context-discovery, vc-plan-discovery, vc-debug and vc-risk-evidence-pack. No web/browser work was performed in this lane. Context routing identified operating-instructions.md and tests/all-tests.md; selected PLAN B2 and VALIDATE §9 control the command and evidence boundary.

## 2. Outcome

**FAIL — complete backend acceptance is not established.**

The single full command completed normally, exit 1: **53 failed, 4058 passed, 8 skipped, 5 deselected, 57 warnings in 1385.69 seconds**. JUnit records 4119 executed cases, 0 collection/runtime errors outside test failures. This is not a timeout or a partially collected run.

- All **280 new backend `test_x_proxy*` cases passed**, including actual wire/TLS, native temporary SQLite, crash recovery, spawned child, runtime/revision, policy/private boundary and shared-state cases.
- New public-health suite: **47 passed, 8 failed**. All eight actual GET regressions stopped in Windows event-loop plumbing before the endpoint executed.
- Existing identity transport: **8 passed**. Existing twscrape reader: **44 passed, 1 legacy POSIX-mode skip**.
- **Zero REQUIRED B2 skips** were observed. This does not turn failed GET/tooling acceptance into PASS.
- Two B2 tooling guards failed on newly introduced maintained lazy boundaries and the bounded child `Popen` path. Source owner reported corrections after the run; this report does not claim those corrections passed.
- Forty-three additional failures were source-grounded to unchanged baseline test/implementation files. They remain failures, not silently waived baseline exceptions.
- The input was **not one immutable whole-task snapshot**: `api/tests/collector_status_e2e.py` changed while the full command ran. No production/backend source file changed during that interval according to the recorded manifest comparison. The result cannot accept the final consumer fixture snapshot.

**Live operation/release remains BLOCKED and was not authorized or exercised.** Synthetic success is not proof about real X/Reddit accounts, proxies, provider behavior, deployment ancestor ACLs or provider terms.

## 3. Summary and tested revision

Baseline: `febe7f44cfdfc08965fca0a721a8cbc83bf22b5a`, with the existing full-task uncommitted implementation, tests and documents. Initial status evidence is preserved at `artifact://1113`; this was not a clean-baseline run.

At command start, a sorted SHA-256 manifest covered **434** API `.py`, `.toml` and `.lock` files, excluding `.venv`, caches and bytecode. Aggregate SHA-256 of the sorted JSON mapping:

`87fe37f7dd01545dea0439ed8959828806a7b08091dca154e16d5af70a2b1f47`

Individual hashes are retained in `C:/Users/jamir/AppData/Local/Temp/b2-backend-acceptance-w87gqzlc/source-before.json`.

| File | Run-start SHA-256 | Run-end SHA-256 |
|---|---|---|
| api/tests/collector_status_e2e.py | `fe39fba1d88463bc7e7f411f4c94ec8c6fe336d043721a9e34cb6a3a061616cb` | `2128bd312b2c0de1d68bc9672e1a4fa9f18973953f455213f5dbd9003b4c25d7` |

The exact moment the running process imported the changed helper is not established. The eight GET failures occurred before handler execution, so they prove neither old nor revised helper output through the actual endpoint. Parent explicitly notified this lane that consumer harness work was concurrent; the caveat is retained rather than hidden.

The backend owner subsequently changed `api/tests/tooling_guards/test_x_reader_guards.py`: run-start/run-end SHA-256 `74a588cea44d686e2af5506705f88a2ed633fc2064772599420dd39c1263fe25`, post-run observed SHA-256 `8ef2981c6a384386f115e589aae18265bd03d64e0fc054bf93bbc07a0ff715cd`. These later edits were not part of the full run. Later owner-reported direct-fallback regression enhancements likewise have no execution evidence in this report.

## 4. Files changed and safety boundary

Only permanent tester-owned deliverable: this report. Temporary stdout, JUnit, preflight and manifest artifacts were retained outside the repository. Pytest's normal cache output was not used as a substitute for actual execution evidence.

No implementation/test-expectation edits, dependency changes, reinstall, build, formatter, lint, live provider/proxy/account requests, deployment/restart, commit, push, PR or merge was performed. The frozen preflight used offline package resolution against the already prepared environment. Subsequent pytest used `UV_NO_SYNC=1` to avoid shared-venv mutation. Integration-marked live tests were deselected by the repository's existing `-m 'not integration'` default, not by new selection changes.

B2 wire fixtures use newly created loopback TLS origin/proxy listeners and ephemeral synthetic roots. Their resolvers reject non-fixture names; configured spawned-child tests inject test-only file/distribution inspectors and trust/DNS endpoints. Native SQLite tests operate on fresh temporary DB/journal files with synthetic ancestor policy. No existing service was reused or killed. This lane did not instrument every legacy case with an additional global egress firewall, and does not claim a host-wide socket audit.

## 5. Commits

None. HEAD remains the named baseline; acceptance concerns its uncommitted full-task source, not a new committed revision.

## 6. Tests run and exact evidence

All times below are UTC.

| Command | UTC start | UTC end | Result |
|---|---|---|---|
| Frozen xreader import/version preflight, expanded below | 2026-11-04T14:36:00.872538+00:00 | 2026-11-04T14:36:02.362127+00:00 | PASS, exit 0 |
| `uv run --project api --frozen --group xreader pytest api/ -q -rs` | 2026-11-04T14:36:52.494453+00:00 | 2026-11-04T15:00:07.109464+00:00 | FAIL, exit 1; 53 failed / 4058 passed / 8 skipped / 5 deselected / 57 warnings |
| `git diff --check` | 2026-11-04T15:02:59.476647+00:00 | 2026-11-04T15:02:59.724248+00:00 | PASS, exit 0, no output; tracked whitespace only, not untracked content or runtime acceptance |

The full suite had a **3600-second subprocess deadline** and completed without a timeout. No second full suite, unchanged narrow smoke or failing-case retry was run. `git diff --check` followed the reported backend guard correction; subsequent consumer/helper/test enhancements are outside that static-check timestamp. It is not a claim that the final source snapshot was frozen or retested.

Exact dependency preflight:

```text
uv run --project api --frozen --group xreader python -c "import twscrape, curl_cffi, httpx, httpcore; import importlib.metadata as m, sys, sqlite3; print(\"python=\"+sys.version); print(\"sqlite3=\"+sqlite3.sqlite_version); [print(n+\"=\"+m.version(n)) for n in (\"twscrape\",\"curl_cffi\",\"httpx\",\"httpcore\")]"
```

Observed output:

```text
python=3.12.14 (main, Sep 29 2026, 15:00:58) [MSC v.1944 64 bit (AMD64)]
sqlite3=3.53.1
twscrape=0.20.1
curl_cffi=0.16.3
httpx=0.28.1
httpcore=1.0.9
```

Environment for full run:

```text
UV_FROZEN=1
UV_OFFLINE=1
UV_NO_SYNC=1
SCREENER_REFRESH_WORKER=0
SCREENER_ATTENTION_PC_WORKER=0
SCREENER_ATTENTION_REDDIT_STREAM=0
SPOT_VOLUME_REFRESH=0
PYTEST_ADDOPTS=--junitxml=<temporary evidence path>
```

Only additive JUnit reporting was selected through `PYTEST_ADDOPTS`; command test selection was unchanged. Pytest's environment-option parsing removed Windows path separators from the initial XML filename, so the generated XML was located and moved to the intended temporary evidence directory, without rerunning tests. No XML artifact is intentionally left at repository root.

### Complete retained artifacts

- Full captured output with all 53 failure traces and warnings: `C:/Users/jamir/AppData/Local/Temp/b2-backend-acceptance-w87gqzlc/backend-full-output.txt` (321,902 bytes); transcript copy with metadata: **`artifact://1118`**. On-screen elision is not missing captured output.
- JUnit with exact executed case IDs and per-case outcomes: `C:/Users/jamir/AppData/Local/Temp/b2-backend-acceptance-w87gqzlc/backend-junit.xml`.
- Command/UTC/environment/source-change metadata: `C:/Users/jamir/AppData/Local/Temp/b2-backend-acceptance-w87gqzlc/run-metadata.json`.
- Preflight output: `C:/Users/jamir/AppData/Local/Temp/b2-backend-acceptance-w87gqzlc/preflight.txt`.
- Start-source manifest: `C:/Users/jamir/AppData/Local/Temp/b2-backend-acceptance-w87gqzlc/source-before.json`.
- Extracted exact failure/skip inventory transcript: `artifact://1141`.
- Screenshots: not applicable to backend-only pytest; none captured.

| Artifact | SHA-256 |
|---|---|
| backend-full-output.txt | `aa5f91378d0cc50f433c1232681f2e7ac6cb5ff5dd5a07e5a4a1367c98943167` |
| backend-junit.xml | `bd07173799ef9ba3caf5f3fbbe4b641a77f556f164ee22365ddf51911679839b` |
| source-before.json | `2296b58a0da979cc634ea4efe8519e2350b811311b619d41d55584e67ad4d56a` |

### Required backend file execution counts

These are results from the **one integrated run**, not added smoke totals.

| Module | PASS | FAIL | SKIP |
|---|---:|---:|---:|
| `tests.analytics.attention.test_sources_proxy_health` | 47 | 8 | 0 |
| `tests.data.attention.test_identity_transport` | 8 | 0 | 0 |
| `tests.data.attention.test_twscrape_reader` | 44 | 0 | 1 |
| `tests.data.attention.test_x_proxy` | 25 | 0 | 0 |
| `tests.data.attention.test_x_proxy_admission` | 8 | 0 | 0 |
| `tests.data.attention.test_x_proxy_dispatch` | 3 | 0 | 0 |
| `tests.data.attention.test_x_proxy_policy` | 62 | 0 | 0 |
| `tests.data.attention.test_x_proxy_private` | 43 | 0 | 0 |
| `tests.data.attention.test_x_proxy_resolver` | 1 | 0 | 0 |
| `tests.data.attention.test_x_proxy_runtime` | 4 | 0 | 0 |
| `tests.data.attention.test_x_proxy_snapshot` | 36 | 0 | 0 |
| `tests.data.attention.test_x_proxy_spawn` | 9 | 0 | 0 |
| `tests.data.attention.test_x_proxy_sqlite` | 8 | 0 | 0 |
| `tests.data.attention.test_x_proxy_state` | 27 | 0 | 0 |
| `tests.data.attention.test_x_proxy_transport` | 54 | 0 | 0 |

Supporting integrated modules also executed without failure: `test_x_pool` 32; `test_x_reader` 73; `test_web_queries` 127; `test_attention_pc_refresh` 54; `test_attention_pc_refresh_stream` 89; `test_attention_pc_refresh_collector` 14; `test_sources` 29; `test_sources_health` 20; `test_probe_pc_sources` 12. Router failures are not hidden by these supporting successes.

Permanent helper modules `proxy_child_fixture.py` and `proxy_wire_fixture.py` were imported/invoked by collected tests; they are helpers, not additional pytest cases. The real child fixture delegates to production `tr.main(["--curl-fallback"])` with bounded stdin/capture and test-only dependencies.

### Exact REQUIRED B2 test IDs executed

The following inventory is taken from JUnit, including every parameter ID. Each subsection uses the displayed file path plus `::` plus the exact name in its block. PASS means this integrated execution, not a claim that every contract dimension is adequately asserted.

#### `api/tests/analytics/attention/test_sources_proxy_health.py`

```text
PASS test_legacy_json_retains_nulls_and_omits_unavailable_proxy_fields
PASS test_all_proxy_states_round_trip_actual_json[direct]
PASS test_all_proxy_states_round_trip_actual_json[unknown]
PASS test_all_proxy_states_round_trip_actual_json[healthy]
PASS test_all_proxy_states_round_trip_actual_json[quarantined]
PASS test_all_proxy_states_round_trip_actual_json[blocked]
PASS test_new_fields_refuse_untrusted_text[https://user:SECRET@proxy.invalid/path-proxy_id]
PASS test_new_fields_refuse_untrusted_text[https://user:SECRET@proxy.invalid/path-proxy_state]
PASS test_new_fields_refuse_untrusted_text[https://user:SECRET@proxy.invalid/path-proxy_reason]
PASS test_new_fields_refuse_untrusted_text[https://user:SECRET@proxy.invalid/path-proxy_checked_at]
PASS test_new_fields_refuse_untrusted_text[https://user:SECRET@proxy.invalid/path-proxy_quarantine_until]
PASS test_new_fields_refuse_untrusted_text[https://user:SECRET@proxy.invalid/path-region]
PASS test_new_fields_refuse_untrusted_text[https://user:SECRET@proxy.invalid/path-connection_style]
PASS test_new_fields_refuse_untrusted_text[https://user:SECRET@proxy.invalid/path-identity_revision]
PASS test_new_fields_refuse_untrusted_text[192.0.2.1-proxy_id]
PASS test_new_fields_refuse_untrusted_text[192.0.2.1-proxy_state]
PASS test_new_fields_refuse_untrusted_text[192.0.2.1-proxy_reason]
PASS test_new_fields_refuse_untrusted_text[192.0.2.1-proxy_checked_at]
PASS test_new_fields_refuse_untrusted_text[192.0.2.1-proxy_quarantine_until]
PASS test_new_fields_refuse_untrusted_text[192.0.2.1-region]
PASS test_new_fields_refuse_untrusted_text[192.0.2.1-connection_style]
PASS test_new_fields_refuse_untrusted_text[192.0.2.1-identity_revision]
PASS test_new_fields_refuse_untrusted_text[C:\\private\\SECRET-proxy_id]
PASS test_new_fields_refuse_untrusted_text[C:\\private\\SECRET-proxy_state]
PASS test_new_fields_refuse_untrusted_text[C:\\private\\SECRET-proxy_reason]
PASS test_new_fields_refuse_untrusted_text[C:\\private\\SECRET-proxy_checked_at]
PASS test_new_fields_refuse_untrusted_text[C:\\private\\SECRET-proxy_quarantine_until]
PASS test_new_fields_refuse_untrusted_text[C:\\private\\SECRET-region]
PASS test_new_fields_refuse_untrusted_text[C:\\private\\SECRET-connection_style]
PASS test_new_fields_refuse_untrusted_text[C:\\private\\SECRET-identity_revision]
PASS test_new_fields_refuse_untrusted_text[/private/SECRET-proxy_id]
PASS test_new_fields_refuse_untrusted_text[/private/SECRET-proxy_state]
PASS test_new_fields_refuse_untrusted_text[/private/SECRET-proxy_reason]
PASS test_new_fields_refuse_untrusted_text[/private/SECRET-proxy_checked_at]
PASS test_new_fields_refuse_untrusted_text[/private/SECRET-proxy_quarantine_until]
PASS test_new_fields_refuse_untrusted_text[/private/SECRET-region]
PASS test_new_fields_refuse_untrusted_text[/private/SECRET-connection_style]
PASS test_new_fields_refuse_untrusted_text[/private/SECRET-identity_revision]
PASS test_existing_account_reason_is_not_reclassified_as_proxy_state
FAIL test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[None-configured]
FAIL test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[None-direct]
FAIL test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[proxy_reason-configured]
FAIL test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[proxy_reason-direct]
FAIL test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[proxy_checked_at-configured]
FAIL test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[proxy_checked_at-direct]
FAIL test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[state-configured]
FAIL test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[state-direct]
PASS test_public_proxy_metadata_rejects_noncanonical_or_unclosed_values[identity_revision-12345678-1234-1234-8234-123456789abd]
PASS test_public_proxy_metadata_rejects_noncanonical_or_unclosed_values[proxy_id-12345678-1234-4234-8234-123456789ABC]
PASS test_public_proxy_metadata_rejects_noncanonical_or_unclosed_values[proxy_checked_at-2026-11-03T12:00:00]
PASS test_public_proxy_metadata_rejects_noncanonical_or_unclosed_values[proxy_quarantine_until-2026-11-03T12:00:00+01:00]
PASS test_public_proxy_metadata_rejects_noncanonical_or_unclosed_values[proxy_reason-new_unknown_upstream_error]
PASS test_public_proxy_metadata_rejects_noncanonical_or_unclosed_values[proxy_state-active]
PASS test_public_proxy_metadata_rejects_noncanonical_or_unclosed_values[region-US California]
PASS test_public_proxy_metadata_rejects_noncanonical_or_unclosed_values[connection_style-chrome]
```

#### `api/tests/data/attention/test_identity_transport.py`

```text
PASS test_both_factory_paths_send_account_identity[plain]
PASS test_both_factory_paths_send_account_identity[curl]
PASS test_bootstrap_cache_isolated_by_label_and_fresh
PASS test_refresh_preserves_account_state_and_reconciles_identity
PASS test_incompatible_upstream_factory_is_refused
PASS test_restart_and_identity_change_invalidate_bootstrap_cache
PASS test_candidate_target_wire_headers
PASS test_fallback_child_uses_configured_target_on_both_paths
```

#### `api/tests/data/attention/test_x_proxy.py`

```text
PASS test_duplicate_json_never_accepts_last_value
PASS test_origins_reject_ambiguous_or_insecure_values[http://example.com]
PASS test_origins_reject_ambiguous_or_insecure_values[https://u:p@example.com]
PASS test_origins_reject_ambiguous_or_insecure_values[https://example.com/a]
PASS test_origins_reject_ambiguous_or_insecure_values[https://example.com?x=1]
PASS test_origins_reject_ambiguous_or_insecure_values[https://example.com#x]
PASS test_origin_normalization
PASS test_proxy_schemes_and_plaintext_auth_fail_closed[http://user:secret@proxy.example:80]
PASS test_proxy_schemes_and_plaintext_auth_fail_closed[socks5://proxy.example]
PASS test_proxy_schemes_and_plaintext_auth_fail_closed[http://proxy.example/path]
PASS test_proxy_schemes_and_plaintext_auth_fail_closed[https://proxy.example?x=secret]
PASS test_https_proxy_credentials_not_represented
PASS test_production_address_rejection[127.0.0.1]
PASS test_production_address_rejection[10.0.0.1]
PASS test_production_address_rejection[169.254.169.254]
PASS test_production_address_rejection[::1]
PASS test_production_address_rejection[224.0.0.1]
PASS test_production_address_rejection[192.0.2.1]
PASS test_connect_rewrites_only_complete_validated_frame
PASS test_connect_ambiguity_rejected[GET / HTTP/1.1\r\nHost: example.com:443\r\n\r\n]
PASS test_connect_ambiguity_rejected[CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\nHost: example.com:443\r\n\r\n]
PASS test_connect_ambiguity_rejected[CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\nContent-Length: 0\r\n\r\n]
PASS test_connect_ambiguity_rejected[CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\nextra]
PASS test_connect_header_bounded
PASS test_failure_cannot_carry_arbitrary_reason
```

#### `api/tests/data/attention/test_x_proxy_admission.py`

```text
PASS test_unselected_provider_zero_requests_order_cache_reload_and_expiry
PASS test_selected_provider_is_one_serial_request_before_baseline
PASS test_selected_provider_failure_never_owner_fallback_or_baseline
PASS test_selected_provider_unknown_or_mismatched_observation_never_owner_fallback[observed0]
PASS test_selected_provider_unknown_or_mismatched_observation_never_owner_fallback[observed1]
PASS test_selected_provider_unknown_or_mismatched_observation_never_owner_fallback[observed2]
PASS test_selected_provider_unknown_or_mismatched_observation_never_owner_fallback[observed3]
PASS test_selected_provider_unknown_or_mismatched_observation_never_owner_fallback[observed4]
```

#### `api/tests/data/attention/test_x_proxy_dispatch.py`

```text
PASS test_midunit_proxy_failure_discards_partial_sample_charges_and_replaces_whole_unit
PASS test_canary_proxy_failure_preserves_charges_and_does_not_become_account_or_day_failure
PASS test_fallback_typed_proxy_failure_never_retries_direct_or_misclassifies
```

#### `api/tests/data/attention/test_x_proxy_policy.py`

```text
PASS test_policy_roundtrip_fixed_sources_and_no_provider_default
PASS test_policy_rejects_wrong_types_values_and_normalized_duplicates[version-True]
PASS test_policy_rejects_wrong_types_values_and_normalized_duplicates[version-2]
PASS test_policy_rejects_wrong_types_values_and_normalized_duplicates[metadata_provider-reputation]
PASS test_policy_rejects_wrong_types_values_and_normalized_duplicates[service_sid-S-1-5-4294967296]
PASS test_policy_rejects_wrong_types_values_and_normalized_duplicates[service_sid-S-1-281474976710656-1]
PASS test_policy_rejects_wrong_types_values_and_normalized_duplicates[service_sid-S-1-05-1]
PASS test_policy_rejects_wrong_types_values_and_normalized_duplicates[cache_dir-relative]
PASS test_policy_rejects_wrong_types_values_and_normalized_duplicates[allowed_origins-value7]
PASS test_policy_rejects_wrong_types_values_and_normalized_duplicates[allowed_origins-value8]
PASS test_nested_policy_exact_keys_and_no_credentials[echo-response_format-text]
PASS test_nested_policy_exact_keys_and_no_credentials[echo-url-http://echo.example/ip]
PASS test_nested_policy_exact_keys_and_no_credentials[echo-url-https://user:SECRET@echo.example/ip]
PASS test_nested_policy_exact_keys_and_no_credentials[baseline-sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA]
PASS test_nested_policy_exact_keys_and_no_credentials[baseline-url-https://baseline.example/plain#fragment]
PASS test_nested_policy_exact_keys_and_no_credentials[baseline-extra-True]
PASS test_unknown_and_missing_policy_keys_fail[None]
PASS test_unknown_and_missing_policy_keys_fail[echo]
PASS test_unknown_and_missing_policy_keys_fail[baseline]
PASS test_cache_escape_and_fixed_source_origin_required
PASS test_sticky_assignment_reorder_and_unassigned_spare
PASS test_assignment_refusals[duplicate_line]
PASS test_assignment_refusals[duplicate_id]
PASS test_assignment_refusals[duplicate_ip]
PASS test_assignment_refusals[mapped_duplicate_ip]
PASS test_assignment_refusals[missing]
PASS test_assignment_refusals[unknown]
PASS test_assignment_refusals[removed]
PASS test_assignment_refusals[bool_line]
PASS test_assignment_refusals[empty_url]
PASS test_assignment_refusals[unknown_entry]
PASS test_assignment_refusals[bad_timezone]
PASS test_assignment_refusals[bad_language]
PASS test_assignment_refusals[duplicate_key]
PASS test_identity_coherence_is_checked_even_for_sticky_id
PASS test_feed_body_clocks_membership_and_source_tuple[spamhaus-; Last-Modified: Wed, 04 Nov 2026 11:00:00 +0000\n; Expires: Wed, 04 Nov 2026 13:00:00 +0000\n9.0.0.0/24 ; SBL12345\n]
PASS test_feed_body_clocks_membership_and_source_tuple[firehol-# This File Date: Wed, 04 Nov 2026 11:00:00 +0000\n# Source File Date: Mon, 02 Nov 2026 12:00:00 +0000\n# Entries: 2\n9.0.0.0/24\n2001:4860::1\n]
PASS test_feed_malformed_stale_future_and_line_bounds[spamhaus-; Last-Modified: Tue, 03 Nov 2026 11:00:00 +0000\n; Expires: Wed, 04 Nov 2026 13:00:00 +0000\n9.0.0.0/24 ; SBL12345\n]
PASS test_feed_malformed_stale_future_and_line_bounds[spamhaus-; Last-Modified: Wed, 04 Nov 2026 13:00:00 +0000\n; Expires: Wed, 04 Nov 2026 13:00:00 +0000\n9.0.0.0/24 ; SBL12345\n]
PASS test_feed_malformed_stale_future_and_line_bounds[spamhaus-; Last-Modified: Wed, 04 Nov 2026 11:00:00 +0000\n; Expires: Wed, 04 Nov 2026 11:00:00 +0000\n9.0.0.0/24 ; SBL12345\n]
PASS test_feed_malformed_stale_future_and_line_bounds[spamhaus-9.0.0.0/24 ; SBL123\n]
PASS test_feed_malformed_stale_future_and_line_bounds[spamhaus-; Last-Modified: Wed, 04 Nov 2026 11:00:00 +0000\n; Expires: Wed, 04 Nov 2026 13:00:00 +0000\n9.0.0.0/24 ; INVALID\n]
PASS test_feed_malformed_stale_future_and_line_bounds[firehol-# This File Date: Tue, 03 Nov 2026 11:00:00 +0000\n# Source File Date: Mon, 02 Nov 2026 12:00:00 +0000\n# Entries: 2\n9.0.0.0/24\n2001:4860::1\n]
PASS test_feed_malformed_stale_future_and_line_bounds[firehol-# This File Date: Wed, 04 Nov 2026 13:00:00 +0000\n# Source File Date: Mon, 02 Nov 2026 12:00:00 +0000\n# Entries: 2\n9.0.0.0/24\n2001:4860::1\n]
PASS test_feed_malformed_stale_future_and_line_bounds[firehol-# This File Date: Wed, 04 Nov 2026 11:00:00 +0000\n# Source File Date: Mon, 02 Nov 2026 12:00:00 +0000\n# Entries: 1\n9.0.0.0/24\n2001:4860::1\n]
PASS test_feed_malformed_stale_future_and_line_bounds[firehol-# This File Date: Wed, 04 Nov 2026 11:00:00 +0000\n# Ignored Date: Mon, 02 Nov 2026 12:00:00 +0000\n# Entries: 2\n9.0.0.0/24\n2001:4860::1\n]
PASS test_feed_malformed_stale_future_and_line_bounds[firehol-# This File Date: Wed, 04 Nov 2026 11:00:00 +0000\n# Source File Date: Mon, 02 Nov 2026 12:00:00 +0000\n# Entries: 2\n9.0.0.1/24\n2001:4860::1\n]
PASS test_feed_malformed_stale_future_and_line_bounds[firehol-# This File Date: Wed, 04 Nov 2026 11:00:00 +0000\n# Source File Date: Mon, 02 Nov 2026 12:00:00 +0000\n# Entries: 2\n9.0.0.0/24\n2001:4860::1\n#xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx]
PASS test_feed_malformed_stale_future_and_line_bounds[firehol-# This File Date: Wed, 04 Nov 2026 11:00:00 +0000\n# Source File Date: Mon, 02 Nov 2026 12:00:00 +0000\n# Entries: 2\n9.0.0.0/24\n2001:4860::1\n\xff]
PASS test_feed_entry_ceiling_before_membership_allocation_grows
PASS test_public_optional_config_strictness[over0]
PASS test_public_optional_config_strictness[over1]
PASS test_public_optional_config_strictness[over2]
PASS test_public_optional_config_strictness[over3]
PASS test_public_optional_config_strictness[over4]
PASS test_public_optional_config_strictness[over5]
PASS test_public_optional_config_strictness[over6]
PASS test_public_optional_config_strictness[over7]
PASS test_public_optional_config_strictness[over8]
PASS test_public_optional_config_strictness[over9]
PASS test_public_config_off_defaults_and_roundtrip
PASS test_query_file_bound_is_enforced_before_json_parsing
```

#### `api/tests/data/attention/test_x_proxy_private.py`

```text
PASS test_exact_private_root_and_file_acl_snapshots_pass
PASS test_private_acl_refuses_owner_inheritance_denies_unknown_and_extra_aces[acl0]
PASS test_private_acl_refuses_owner_inheritance_denies_unknown_and_extra_aces[acl1]
PASS test_private_acl_refuses_owner_inheritance_denies_unknown_and_extra_aces[acl2]
PASS test_private_acl_refuses_owner_inheritance_denies_unknown_and_extra_aces[acl3]
PASS test_private_acl_refuses_owner_inheritance_denies_unknown_and_extra_aces[acl4]
PASS test_private_acl_refuses_owner_inheritance_denies_unknown_and_extra_aces[acl5]
PASS test_private_acl_refuses_owner_inheritance_denies_unknown_and_extra_aces[acl6]
PASS test_private_acl_refuses_owner_inheritance_denies_unknown_and_extra_aces[acl7]
PASS test_private_acl_refuses_owner_inheritance_denies_unknown_and_extra_aces[acl8]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-21-1-2-3-1001-2]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-21-1-2-3-1001-4]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-21-1-2-3-1001-16]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-21-1-2-3-1001-64]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-21-1-2-3-1001-256]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-21-1-2-3-1001-65536]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-21-1-2-3-1001-262144]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-21-1-2-3-1001-524288]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-21-1-2-3-1001-1073741824]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-21-1-2-3-1001-268435456]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-32-545-2]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-32-545-4]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-32-545-16]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-32-545-64]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-32-545-256]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-32-545-65536]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-32-545-262144]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-32-545-524288]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-32-545-1073741824]
PASS test_ancestor_any_group_write_or_control_rights_fail[S-1-5-32-545-268435456]
PASS test_ancestor_read_traverse_only_and_privileged_sid_exceptions
PASS test_unavailable_acl_inspector_and_actual_service_mismatch_fail
PASS test_repo_containment_and_symlink_ambiguity_refuse
PASS test_os_lock_is_bounded_nonreentrant_and_released
PASS test_atomic_public_state_write_is_complete_and_temporary_removed
PASS test_posix_privacy_synthetic_inspector[None]
PASS test_posix_privacy_synthetic_inspector[file_mode]
PASS test_posix_privacy_synthetic_inspector[root_mode]
PASS test_posix_privacy_synthetic_inspector[wrong_owner]
PASS test_posix_privacy_synthetic_inspector[writable_ancestor]
PASS test_posix_privacy_synthetic_inspector[symlink]
PASS test_posix_privacy_synthetic_inspector[reparse]
PASS test_untrusted_ancestor_owner_cannot_gain_implicit_write_dac
```

#### `api/tests/data/attention/test_x_proxy_resolver.py`

```text
PASS test_dns_rejects_any_private_answer_without_a_connection
```

#### `api/tests/data/attention/test_x_proxy_runtime.py`

```text
PASS test_same_label_raw_snapshot_change_invalidates_admission_even_identity_off
PASS test_unchanged_snapshot_preserves_revision_without_network
PASS test_one_account_assignment_edit_preserves_other_reader_revision
PASS test_reader_reconcile_in_same_pass_evicts_only_changed_account_with_identity_off
```

#### `api/tests/data/attention/test_x_proxy_snapshot.py`

```text
PASS test_snapshot_parses_only_verified_handle_bytes_and_hides_private_repr
PASS test_discovery_policy_change_is_not_used_after_verification
PASS test_attestation_exact_frame_matches_independent_hmac_and_is_redacted
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[label-beta]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[proxy_id-00000000-0000-0000-0000-000000000002]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[identity_revision-2ff8e00b-bede-4a09-8706-2735eebd723f]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[backend-httpx]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[request_nonce-2222222222222222222222222222222222222222222222222222222222222222]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[admission_expires_at-2026-11-04T14:00:00+00:00]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[query-$BTC]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[kv-value7]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[kv-value8]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[kv-value9]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[attestation_tag-0000000000000000000000000000000000000000000000000000000000000000]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[attestation_key-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[attestation_key-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA]
PASS test_work_envelope_and_sensitive_pair_tampering_fails_before_clients[attestation_key-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[0-0]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[0-1]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[0-2]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[1-0]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[1-1]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[1-2]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[2-0]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[2-1]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[2-2]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[3-0]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[3-1]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[3-2]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[4-0]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[4-1]
PASS test_role_order_path_and_exact_raw_byte_tampering_fails[4-2]
PASS test_work_bounds_are_utf8_bytes_not_characters[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-None]
PASS test_work_bounds_are_utf8_bytes_not_characters[\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c-None]
PASS test_work_bounds_are_utf8_bytes_not_characters[ok-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
PASS test_work_bounds_are_utf8_bytes_not_characters[ok-\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c\u754c]
```

#### `api/tests/data/attention/test_x_proxy_spawn.py`

```text
PASS test_spawned_child_hmac_current_snapshot_both_factories_no_secret_output[current-revision]
PASS test_spawned_child_hmac_current_snapshot_both_factories_no_secret_output[changed-raw-snapshot]
PASS test_spawned_explicit_direct_off_predicate_never_implicit_or_configured[valid]
PASS test_spawned_explicit_direct_off_predicate_never_implicit_or_configured[omitted]
PASS test_spawned_explicit_direct_off_predicate_never_implicit_or_configured[required]
PASS test_spawned_explicit_direct_off_predicate_never_implicit_or_configured[partial]
PASS test_spawned_explicit_direct_off_predicate_never_implicit_or_configured[malformed]
PASS test_parent_capture_limits_kill_real_child_without_disclosing_stdin[stdout]
PASS test_parent_capture_limits_kill_real_child_without_disclosing_stdin[stderr]
```

#### `api/tests/data/attention/test_x_proxy_sqlite.py`

```text
PASS test_real_migrate_commit_reopen_rollback_keeps_journal_identity
PASS test_unsafe_sidecar_refused_before_sqlite_open[-wal]
PASS test_unsafe_sidecar_refused_before_sqlite_open[-shm]
PASS test_unsafe_sidecar_refused_before_sqlite_open[-unknown]
PASS test_missing_persistent_journal_never_silently_recreated
PASS test_native_protected_sqlite_live_writer_inspection_and_immutable_input_sharing
PASS test_real_crash_recovery_preserves_rollback_value_and_guarded_journal
PASS test_exclusive_guarded_connections_serialize_and_release_after_close
```

#### `api/tests/data/attention/test_x_proxy_state.py`

```text
PASS test_old_and_partial_migration_read_only_then_persist_complete
PASS test_corrupt_future_and_out_of_range_budget_refused[budget0]
PASS test_corrupt_future_and_out_of_range_budget_refused[budget1]
PASS test_corrupt_future_and_out_of_range_budget_refused[budget2]
PASS test_corrupt_future_and_out_of_range_budget_refused[budget3]
PASS test_corrupt_future_and_out_of_range_budget_refused[budget4]
PASS test_corrupt_future_and_out_of_range_budget_refused[budget5]
PASS test_corrupt_future_and_out_of_range_budget_refused[budget6]
PASS test_proxy_state_exact_types_and_measurement_requirements[proxy_id-https://SECRET]
PASS test_proxy_state_exact_types_and_measurement_requirements[identity_revision-1]
PASS test_proxy_state_exact_types_and_measurement_requirements[proxy_health-direct]
PASS test_proxy_state_exact_types_and_measurement_requirements[proxy_reason-SECRET]
PASS test_proxy_state_exact_types_and_measurement_requirements[proxy_reason-value4]
PASS test_proxy_state_exact_types_and_measurement_requirements[proxy_checked_at-2026-11-04T12:00:00+01:00]
PASS test_proxy_state_exact_types_and_measurement_requirements[proxy_health-healthy]
PASS test_provider_null_day_reservation_is_durable_before_send_no_refund
PASS test_cap_and_final_eleven_seconds_send_nothing
PASS test_day_rollover_reset_and_between_reservation_send_no_refund
PASS test_stale_collector_save_cannot_overwrite_provider_reservation
PASS test_nested_mutation_uses_explicit_ownership_not_second_lock
PASS test_provider_holds_shared_lock_through_completion_even_same_pool_threads
PASS test_two_processes_one_remaining_quota_and_single_inflight
PASS test_process_death_releases_lock_but_consumes_reservation
PASS test_quarantine_wake_precedes_later_lock_and_never_clears_day_pause
PASS test_route_change_preserves_charges_and_invalidates_only_changed_canary
PASS test_stopped_rollback_exact_keys_preserves_part_a_data
PASS test_changed_recent_account_canary_prioritized_and_pending_survives_batch
```

#### `api/tests/data/attention/test_x_proxy_transport.py`

```text
PASS test_numeric_connect_original_host_sni_verified_separate_roots[http-proxy-plain]
PASS test_numeric_connect_original_host_sni_verified_separate_roots[http-proxy-curl]
PASS test_numeric_connect_original_host_sni_verified_separate_roots[https-proxy-plain]
PASS test_numeric_connect_original_host_sni_verified_separate_roots[https-proxy-curl]
PASS test_untrusted_origin_or_wrong_origin_name_never_reaches_application[http-proxy-origin-root-plain]
PASS test_untrusted_origin_or_wrong_origin_name_never_reaches_application[http-proxy-origin-root-curl]
PASS test_untrusted_origin_or_wrong_origin_name_never_reaches_application[http-proxy-origin-name-plain]
PASS test_untrusted_origin_or_wrong_origin_name_never_reaches_application[http-proxy-origin-name-curl]
PASS test_untrusted_origin_or_wrong_origin_name_never_reaches_application[https-proxy-origin-root-plain]
PASS test_untrusted_origin_or_wrong_origin_name_never_reaches_application[https-proxy-origin-root-curl]
PASS test_untrusted_origin_or_wrong_origin_name_never_reaches_application[https-proxy-origin-name-plain]
PASS test_untrusted_origin_or_wrong_origin_name_never_reaches_application[https-proxy-origin-name-curl]
PASS test_https_proxy_own_root_and_hostname_required_even_with_hostile_ambient_ca[proxy-root-plain]
PASS test_https_proxy_own_root_and_hostname_required_even_with_hostile_ambient_ca[proxy-root-curl]
PASS test_https_proxy_own_root_and_hostname_required_even_with_hostile_ambient_ca[proxy-name-plain]
PASS test_https_proxy_own_root_and_hostname_required_even_with_hostile_ambient_ca[proxy-name-curl]
PASS test_redirect_refused_with_exactly_one_wire_attempt_no_direct_fallback[http-proxy-plain]
PASS test_redirect_refused_with_exactly_one_wire_attempt_no_direct_fallback[http-proxy-curl]
PASS test_redirect_refused_with_exactly_one_wire_attempt_no_direct_fallback[https-proxy-plain]
PASS test_redirect_refused_with_exactly_one_wire_attempt_no_direct_fallback[https-proxy-curl]
PASS test_unallowlisted_page_derived_url_refused_before_a_socket[http-proxy-plain]
PASS test_unallowlisted_page_derived_url_refused_before_a_socket[http-proxy-curl]
PASS test_unallowlisted_page_derived_url_refused_before_a_socket[https-proxy-plain]
PASS test_unallowlisted_page_derived_url_refused_before_a_socket[https-proxy-curl]
PASS test_stream_bound_before_buffering_oversized_x_response[http-proxy-plain]
PASS test_stream_bound_before_buffering_oversized_x_response[http-proxy-curl]
PASS test_stream_bound_before_buffering_oversized_x_response[https-proxy-plain]
PASS test_stream_bound_before_buffering_oversized_x_response[https-proxy-curl]
PASS test_dedicated_feed_wire_and_decompressed_limits_are_separate[http-proxy]
PASS test_dedicated_feed_wire_and_decompressed_limits_are_separate[https-proxy]
PASS test_both_factories_account_revision_isolation_and_no_credential_output[plain]
PASS test_both_factories_account_revision_isolation_and_no_credential_output[curl]
PASS test_cancelled_wire_request_drains_native_ownership_without_slowclose_extension[http-proxy-plain]
PASS test_cancelled_wire_request_drains_native_ownership_without_slowclose_extension[http-proxy-curl]
PASS test_cancelled_wire_request_drains_native_ownership_without_slowclose_extension[https-proxy-plain]
PASS test_cancelled_wire_request_drains_native_ownership_without_slowclose_extension[https-proxy-curl]
PASS test_partial_native_retirement_retains_slist_until_retry_finishes[http-proxy-easy-close]
PASS test_partial_native_retirement_retains_slist_until_retry_finishes[http-proxy-watcher-remove]
PASS test_partial_native_retirement_retains_slist_until_retry_finishes[http-proxy-timer-cancel]
PASS test_partial_native_retirement_retains_slist_until_retry_finishes[https-proxy-easy-close]
PASS test_partial_native_retirement_retains_slist_until_retry_finishes[https-proxy-watcher-remove]
PASS test_partial_native_retirement_retains_slist_until_retry_finishes[https-proxy-timer-cancel]
PASS test_typed_failure_escapes_real_queue_retries_and_bootstrap_swallow[http-proxy-queue-plain]
PASS test_typed_failure_escapes_real_queue_retries_and_bootstrap_swallow[http-proxy-queue-curl]
PASS test_typed_failure_escapes_real_queue_retries_and_bootstrap_swallow[http-proxy-swallowed-bootstrap-asset-plain]
PASS test_typed_failure_escapes_real_queue_retries_and_bootstrap_swallow[http-proxy-swallowed-bootstrap-asset-curl]
PASS test_typed_failure_escapes_real_queue_retries_and_bootstrap_swallow[https-proxy-queue-plain]
PASS test_typed_failure_escapes_real_queue_retries_and_bootstrap_swallow[https-proxy-queue-curl]
PASS test_typed_failure_escapes_real_queue_retries_and_bootstrap_swallow[https-proxy-swallowed-bootstrap-asset-plain]
PASS test_typed_failure_escapes_real_queue_retries_and_bootstrap_swallow[https-proxy-swallowed-bootstrap-asset-curl]
PASS test_new_request_revalidates_binding_and_never_reuses_rebound_origin[http-proxy-plain]
PASS test_new_request_revalidates_binding_and_never_reuses_rebound_origin[http-proxy-curl]
PASS test_new_request_revalidates_binding_and_never_reuses_rebound_origin[https-proxy-plain]
PASS test_new_request_revalidates_binding_and_never_reuses_rebound_origin[https-proxy-curl]
```

### All observed skips, separated from required B2 acceptance

- SKIP `api/tests/data/attention/test_trends_runs.py::test_symlink_is_skipped` — symlinks not available.
- SKIP `api/tests/data/attention/test_twscrape_reader.py::test_accounts_db_permissions_checked_fake_fs` — POSIX mode bits.
- SKIP `api/tests/data/test_cache_atomic_writes.py::test_mode_handling` — POSIX permission bits only.
- SKIP `api/tests/deploy/test_lane_scope.py::test_lane_scope_only_allowed_paths` — lane scope check only runs on claude/p2-deploy.
- SKIP `api/tests/scripts/test_snapshot_workflow_schedules.py::test_tolerant_git_add_exits_zero_when_path_missing_or_ignored[absent-liquidity-backfill-snapshot.yml]` — git and bash are required for the tolerant-staging subprocess check.
- SKIP `api/tests/scripts/test_snapshot_workflow_schedules.py::test_tolerant_git_add_exits_zero_when_path_missing_or_ignored[absent-pairs-refresh-snapshot.yml]` — git and bash are required for the tolerant-staging subprocess check.
- SKIP `api/tests/scripts/test_snapshot_workflow_schedules.py::test_tolerant_git_add_exits_zero_when_path_missing_or_ignored[present_and_ignored-liquidity-backfill-snapshot.yml]` — git and bash are required for the tolerant-staging subprocess check.
- SKIP `api/tests/scripts/test_snapshot_workflow_schedules.py::test_tolerant_git_add_exits_zero_when_path_missing_or_ignored[present_and_ignored-pairs-refresh-snapshot.yml]` — git and bash are required for the tolerant-staging subprocess check.

The three symlink/POSIX-permission skips, one branch-specific deploy-lane skip and four missing git/bash subprocess prerequisites are legacy/environment-specific cases. No new `test_x_proxy*`, new public-health GET or identity-transport case was skipped. Five existing integration-marked live cases were deselected by the repository default.

### All 53 failed IDs

```text
api/tests/analytics/attention/test_sources_proxy_health.py::test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[None-configured]
api/tests/analytics/attention/test_sources_proxy_health.py::test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[None-direct]
api/tests/analytics/attention/test_sources_proxy_health.py::test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[proxy_reason-configured]
api/tests/analytics/attention/test_sources_proxy_health.py::test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[proxy_reason-direct]
api/tests/analytics/attention/test_sources_proxy_health.py::test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[proxy_checked_at-configured]
api/tests/analytics/attention/test_sources_proxy_health.py::test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[proxy_checked_at-direct]
api/tests/analytics/attention/test_sources_proxy_health.py::test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[state-configured]
api/tests/analytics/attention/test_sources_proxy_health.py::test_actual_status_get_is_read_only_and_uses_only_safe_pool_projection[state-direct]
api/tests/analytics/attention/test_universe_classes.py::test_discovery_end_to_end_on_fixture
api/tests/data/test_equities_store.py::test_path_override_honoured_at_call_time
api/tests/routers/test_attention.py::test_default_window_30_reads_store_only
api/tests/routers/test_attention.py::test_valid_windows[7]
api/tests/routers/test_attention.py::test_valid_windows[30]
api/tests/routers/test_attention.py::test_valid_windows[90]
api/tests/routers/test_attention.py::test_bad_window_is_422[14]
api/tests/routers/test_attention.py::test_bad_window_is_422[0]
api/tests/routers/test_attention.py::test_bad_window_is_422[abc]
api/tests/routers/test_discovery.py::test_ok_payload_shape
api/tests/routers/test_discovery.py::test_default_window_is_30
api/tests/routers/test_discovery.py::test_enum_accepts[7]
api/tests/routers/test_discovery.py::test_enum_accepts[30]
api/tests/routers/test_discovery.py::test_enum_accepts[90]
api/tests/routers/test_discovery.py::test_enum_rejects_with_422[14]
api/tests/routers/test_discovery.py::test_enum_rejects_with_422[0]
api/tests/routers/test_discovery.py::test_enum_rejects_with_422[-7]
api/tests/routers/test_discovery.py::test_enum_rejects_with_422[abc]
api/tests/routers/test_discovery.py::test_enum_rejects_with_422[30.5]
api/tests/routers/test_discovery.py::test_sources_route_shape_and_no_network
api/tests/routers/test_discovery.py::test_router_discovery_new_fields_present
api/tests/routers/test_discovery_history.py::test_coin_payload_shape
api/tests/routers/test_discovery_history.py::test_category_payload_shape
api/tests/routers/test_discovery_history.py::test_default_window_is_30
api/tests/routers/test_discovery_history.py::test_bad_window_is_422[14]
api/tests/routers/test_discovery_history.py::test_bad_window_is_422[0]
api/tests/routers/test_discovery_history.py::test_bad_window_is_422[abc]
api/tests/routers/test_discovery_history.py::test_needs_exactly_one_subject
api/tests/routers/test_discovery_history.py::test_unknown_subjects_are_404_with_plain_message
api/tests/routers/test_discovery_history.py::test_empty_is_no_data
api/tests/routers/test_discovery_history.py::test_live_endpoint_unchanged
api/tests/routers/test_discovery_history.py::test_category_payload_carries_membership_as_of_and_old_ids_resolve
api/tests/routers/test_discovery_price.py::test_ok_returns_window_days_ending_yesterday
api/tests/routers/test_discovery_price.py::test_no_cache_is_no_data
api/tests/routers/test_discovery_price.py::test_cache_older_than_window_is_no_data_but_reports_last_date
api/tests/routers/test_discovery_price.py::test_non_finite_and_non_positive_closes_are_dropped
api/tests/routers/test_discovery_price.py::test_bad_input_is_422[params0]
api/tests/routers/test_discovery_price.py::test_bad_input_is_422[params1]
api/tests/routers/test_discovery_price.py::test_bad_input_is_422[params2]
api/tests/routers/test_discovery_price.py::test_bad_input_is_422[params3]
api/tests/routers/test_discovery_price.py::test_bad_input_is_422[params4]
api/tests/routers/test_equities_router.py::test_concurrent_adds_store_exactly_thirty
api/tests/tooling_guards/test_attention_workflow_guard.py::test_trends_step_propagates_the_fetcher_exit_code
api/tests/tooling_guards/test_x_reader_guards.py::test_default_env_does_not_install_or_import_twscrape
api/tests/tooling_guards/test_x_reader_guards.py::test_no_auto_update_code_path
```

### Failure root causes, ownership and evidence limits

1. **New required GET regressions — 8 failures, consumer test harness.** `test_sources_proxy_health.py:85-90` blanket-patches `socket.socket.connect`, `create_connection` and DNS before creating a TestClient request. On native Windows, AnyIO creates a Proactor loop; `_make_self_pipe → socket.socketpair → _fallback_socketpair → csock.connect((127.0.0.1, ephemeral_port))` hits that denial. The assertion is raised before the app route, not by a provider attempt. All four malformed projections × configured/direct fail at the same boundary. Reported to Main and B2Consumers with exact command, times and IDs. Parent-authorized shared test-only network guard work was subsequently reported by B2Consumers; no correction was exercised here. Do not weaken the actual route/read-only/no-DNS/no-external-network/secret-absence assertions to make this green.
2. **B2 tooling boundary guards — 2 failures, backend owner.** At the executed snapshot, `test_default_env_does_not_install_or_import_twscrape` excluded only twscrape_reader from its function-level import search, so it rejected the new maintained lazy `x_proxy_curl.py` and `x_proxy_sqlite.py` hooks. The same run's `test_no_auto_update_code_path` banned every `Popen`, including the new bounded fixed-command `run_child` capture path. Failures are at the run's guard lines 93 and 230. These failures do not demonstrate an actual dependency install or auto-update. B2BackendFinish reported explicit lazy-boundary/top-level-import and fixed-command/no-shell AST guard corrections after the run; they remain unverified by this acceptance command.
3. **Unchanged baseline Windows socket plumbing — 40 failures.** `test_universe_classes` 1; `test_attention` 7; `test_discovery` 12; `test_discovery_history` 11; `test_discovery_price` 9. Each recorded trace reaches the same Windows `socketpair` fallback and blanket socket denial before handler execution. Relevant fixture sites: universe_classes.py:266-271; routers/test_attention.py:33-38; test_discovery.py:24-29; test_discovery_history.py:27; test_discovery_price.py:32. All five test files were byte-compared against `git show febe7f44:<path>` after CRLF normalization and found unchanged. This is source-grounded baseline attribution, not an independent baseline test run or permission to waive failed commands.
4. **Unchanged baseline path assertion — 1 failure.** `test_equities_store.py:107` calls `os.fspath(WindowsPath(...)).endswith("api/data/equities.json")`; the observed backslash path cannot satisfy the literal POSIX suffix. Prior temporary-file behavior assertions reached that final check. Test file and `equities_store.py` are unchanged from baseline. No platform-specific expectation was edited by this tester.
5. **Unchanged equities concurrency path — 1 failure.** `test_equities_router.py:85-99` starts 35 workers and expects all 35 replies. Only 32 replies were present; warnings contain three `WinError 5` exceptions at `equities_store.py:82`, `os.replace(temp, equities.json)`. Both store and router sources and their test are unchanged from baseline. The store serializes writes with `_LOCK`, but unlocked reads (`load_tickers`, lines 64-69) may overlap replacement on Windows; that overlapping-read explanation is **[INFERENCE]**, not proven by this run. The proven failure is denied replacement and missing worker results; do not relabel it as harmless flakiness.
6. **Unchanged missing-shell prerequisite — 1 failure.** `test_attention_workflow_guard.py:248-266` executes `["bash", "-e", "-c", ...]`; the subprocess raises `FileNotFoundError [WinError 2]` before execution. The test file is unchanged from baseline. No `.github/` file was edited, and installing/reconfiguring the host shell was outside this assignment.

Baseline comparisons covered the five socket-denial test files, equities store/test/router files, and the workflow-guard test. No separate worktree was created, changed or tested; no failure was silently waived.

### Warnings

All **57** remain captured in full output:

- 1 Starlette TestClient/httpx deprecation and 1 AnyIO BlockingPortal alias deprecation.
- 7 unraisable Proactor-loop teardown warnings (`_ssock` absent) following socketpair initialization denial.
- 30 curl_cffi warnings about Proactor `add_reader` support (3 identity-transport, 27 B2 transport), using its additional selector thread.
- 15 curl_cffi HTTPS-proxy advisory warnings.
- 3 unhandled equities worker-thread warnings with denied `os.replace` operations.

No warnings were suppressed and no dependency/policy change was made to hide them.

## 7. Tests NOT run and missing proof

- No full-suite retry, narrow smoke replay, changed-case retry, baseline-only suite, frontend suite, TypeScript/build, browser or live check was performed in this lane.
- Final source acceptance after consumer/guard changes is **NOT RUN**. The full command's changed helper and later guard/regression corrections prevent a final immutable-snapshot PASS claim.
- Actual public GET/read-only/malformed-projection/secret-absence proof remains missing because all eight relevant cases failed before the endpoint.
- Direct/off spawned predicate tests passed, but their executed fixture replaces `API.search_raw` with an immediate synthetic empty result (`proxy_child_fixture.py:34-38`). They do **not** demonstrate actual direct library/client wire activity or assert the continuation cursor. Their test at `test_x_proxy_spawn.py:78-109` only checks status/refusal. Existing twscrape cursor/charge/daily-fallback tests use an injected Child; existing identity fallback calls `_child` in-process. Therefore this report does not count those cases as composed real spawned direct plain→curl continuation + account/global charges + daily-cap runtime proof. This is a genuine regression-proof gap, **not an observed production defect**. B2BackendFinish later reported adding `test_composed_direct_plain_to_spawned_curl_wire_cursor_charges_and_daily_cap` and `test_spawned_configured_route_never_uses_available_direct_wire`; neither was part of this run and no PASS is implied.
- Configured spawned HMAC proof is real subprocess + actual routed bootstrap/account client wire, with synthetic inspector/distribution/search dispatch injection. It is not a deployment-host ACL or real X query proof.
- Native temporary DB/journal tests, including crash/reopen/rollback, passed; actual deployment ancestor ownership, service SID and ACL selection remain a separate unperformed release gate.
- RT4 risk evidence pack, manual acceptance and separately authorized live route/provider evidence are not supplied by this report. No complete risk-pack/release approval is inferred.

## 8. Deviations

The requested single full collection was executed without changed selection or test suppression, but concurrent consumer helper edits violated whole-snapshot immutability. That fact is explicitly recorded. Later parent/source-owner corrections were not silently substituted for the tested source.

Temporary JUnit reporting was added solely to preserve exact executed IDs. All stdout/stderr was retained, including complete failures. No acceptance count is formed by summing earlier smoke runs.

## 9. Blockers

**Backend acceptance remains FAIL** until required GET/tooling failures and the final-snapshot proof boundary are resolved by their owners and independently exercised under parent direction. The 43 source-grounded baseline/environment failures also require explicit disposition; they cannot be removed from the full command's FAIL result.

**Release remains BLOCKED/not authorized** for the separately specified live configuration, host ACL, provider terms/probes, RT4 evidence and manual acceptance requirements. None is relaxed by successful temporary-fixture tests.

## 10. Follow-up ownership

Main received exact failures, times, artifact paths, baseline attribution, snapshot caveat and direct-fallback proof limitation. B2BackendFinish received source-owned guard failures and the regression-proof gap; B2Consumers received the eight actual GET failures. Owner-reported guard/direct-regression and consumer network-guard changes are intentionally not presented as exercised fixes.

Any further targeted execution or new integrated run belongs to an explicit parent-directed acceptance assignment after owners freeze the changed source. Do not rerun the unchanged failed command or weaken expectations. This lane's requested execution and report are complete; the implementation's runtime acceptance is not.

## 11. Evidence and context cost

Evidence is the observed single integrated command, its full retained output/JUnit, UTC metadata, source manifests, exact IDs and read-only source tracing above. No fabricated screenshots, live proof or green completion claim. Context cost unmeasured. Discovery/reading and metadata extraction were not additional test runs.
