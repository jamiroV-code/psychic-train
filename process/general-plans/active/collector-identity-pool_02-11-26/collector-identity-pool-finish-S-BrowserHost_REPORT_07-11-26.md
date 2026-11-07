# S-BrowserHost slice report (07-11-26)

## 1. Status
CODE-COMPLETE on the spawned fake. LIVE-READY: NO. Gates BG-3/O-1/O-1b unmet (`OWNER_DECISIONS` default off), A19 admission absent. Commit d22779e9 on `claude/b2-validate`. Not pushed.

## 2. Scope
Plan §S-BrowserHost: A10-A12, A14-A17.

## 3. Changed paths
New: `api/data/attention/browser_host.py`, `browser_profile.py`; `api/tests/data/attention/browser_fake_main.py`, `browser_lifecycle_fixture.py`, `test_browser_host.py`, `test_browser_profile.py` (last three test/fixture files approved by Main); `api/tests/tooling_guards/test_browser_host_guards.py`.

## 4. What was built
- Profile: native SDDL OICI-protected creation; native ACL reader with OI/CI/IO flags; CE-1 SID derived at runtime (`DeriveCapabilitySidsFromName`, verified equal to the BP3c SID); exact CE-1/CE-2 locations and masks; recursive admission (20,000 entries, depth 12, reparse refusal, record with label+root fingerprint); post-session sweep with pin in `_pc_state/profile_records/<label>.json`; drift refused on next launch. Each exception needs its own owner decision.
- Host: kernel mutex `Global\mysite-collector-browser-<16 hex SHA-256(SID)>` (timeout 0; abandoned = success); per-profile lock; suspended create, non-inherited KILL_ON_JOB_CLOSE job, resume after assignment; explicit `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` with only the two pipe ends; NUL-framed pipe transport (1 MiB ceiling, deadline); creation-time-verified orphan termination; memory floor (unreadable = refuse); RSS over the job's PIDs; watcher thread enforces timeout/RSS.
- Argv: single builder, one `--disable-features`, validator rejects duplicates, ports, empty bypass, sandbox/logging flags.

## Interfaces for S-Relay / S-CDP
- `browser_host.executable_version(binary) -> str`
- `write_admission(cache_root, binary, version, *, outcome, destination_classes) -> digest`
- `read_admission(cache_root, binary, version) -> dict` (raises `BrowserFailure(browser_unadmitted|containment_residual_unaccepted)`)
- `residual_digest(binary, version, classes)`; acceptance file read by `read_admission`.
- `BrowserHost(binary, profiles_dir, *, cache_root, policy, spawn, memory, rss, ...).launch(label, profile_name, relay_port) -> BrowserSession` (`.pipe.send/receive`, `.job.pids()`, `.check()`, context manager); `build_argv` takes the relay port.
- `process_tree`, `process_creation`, `terminate_recorded`, `MachineLock`.
- Fake accepts `--fake-script=<json>` (cookies, pages, `wire`, `ca_file`); CONNECT via `--proxy-server`.

## 6. Tests run
`pytest test_browser_profile.py test_browser_host.py test_browser_guards` → 43 passed, 0 skipped. Red-first: both suites were first run failing on the missing modules; later additions (watchdog) red once. Real Edge never launched.

## 7. Data verification
Writes only under tmp caches; state files `profile_records/<label>.json`, `browser_launches/<label>.json`, `_probes/browser_admission_<digest>.json`.

## 8. Error handling
Closed reason codes; no path/argv in messages; failed launches close job, pipe and locks.

## 9. Deviations
- Windows only for launch (POSIX job/process-group not implemented; POSIX lock and mode-0700 profile exist). Needs a plan decision or later slice.
- Relay lifecycle is not started by the host (S-Relay owns; port passed in). Browser version via PE resource; non-Edge-Stable real launches refused by path check.
- `test_reddit_collector_guards.py` currently fails on sibling `reddit_accounts.py` (print at 381/383), not mine.
- Admission check at launch reads outcome only; `contained` firewall attestation is S-Relay's.
- `terminate_recorded` kills the recorded tree by ancestry+creation time.

## 10. Gate honesty
BG-3 NOT-MET until O-1/O-1b; BG-2 pipe proven only on fake and BP2; A19 not run.

## 11. Next
S-BrowserCDP consumes `session.pipe`; S-Relay writes admission records.
