# G-FINAL closeout report (collector identity pool finish, 08-11-26)

## 1. Status
CODE DONE, fixture-proven, on branch `claude/b2-validate` (HEAD at the time of writing: `fd90e69a` plus this report commit). NOT LIVE-READY and NOT VERIFIED: no live X or Reddit request, no real-browser run on the combined tree, owner steps below are open. "VERIFIED" needs the Phase Completion Rules (LIVE-READY plus the owner's confirmation).

## 2. Evidence
| Check | Command | Result |
|---|---|---|
| E2E acceptance (synthetic loopback) | `python -m api.tests.cycle.acceptance` | C1-C14 passed, no skips; 56 s, peak 280 MB (selftest child run: 118 s) |
| UI acceptance | `... acceptance --ui` (S-E2E-UI, commit `15e60f8b`) | C1-C14 + UI at 375/768/1280 passed (worker-reported, not re-run here) |
| Consolidated gate | pytest `analytics/attention`, `data/attention`, `tooling_guards`, `cycle` | 2927 passed, 2 skipped, 1 failed (`test_session_helper_never_types_credentials_or_logs`) |
| Failure fix | `parser.error` -> `parser.exit(2, ...)` in `browser_session.py` (`fd90e69a`); the guard bans `.error(` calls as logging | `tooling_guards` + `cycle`: 155 passed; `-k session`: 123 passed |

Not re-run after the fix: the full `analytics/attention` and `data/attention` directories (the first run stopped at the failure with `-x`, so some of them had run and some had not). The change is one line in a CLI argument check. Known unrelated failure from earlier stages: `test_equities_store::test_path_override_honoured_at_call_time` (Windows, other session). CI on the PR is not yet observed.

## 3. Security re-reads (read-only reviewer, 08-11-26)
| Area | Verdict |
|---|---|
| S-B3I child envelope `count` | PASS. Set only from `variation.page_size` (10 or 20); re-validated as exact int at every hop; fail-closed on tampered archives |
| S-B3I single-page `ordinary()` | FINDING, medium-low, contract gap, not exploitable. Route admission and `ct0` handling are covered (via `RoutedClient`). Skipped: rate-limit evidence (`x-rate-limit-remaining`, 429 has no cooldown branch), Cloudflare/HTML block classification, `GqlFeaturesOutdated`, unbounded `response.json()`. Capped at 3 calls/day. Fix: classify like `check_rep` in `single_page` and add a `run_mixed` branch |
| `open_browser` / `RedditRoutes` / `reddit_browser` | PASS. Default-deny admission, no `Input` domain, no raw CDP, cookie values discarded or login-gated |
| Relay `browser_relay.py` | PASS. Loopback bind, strict CONNECT grammar, numeric-dial after `public_address` check (no rebinding), per-account revision admission. Low residuals: no relay authentication (local processes), no tunnel cap or idle timeout, NAT64 prefix accepted as global |

Follow-ups (proposed, not done, need owner approval as a new slice): `ordinary()` rate-limit/block classification; relay concurrency cap + idle timeout; reject `64:ff9b::/96`.

## 4. Probes and live gates
Owner has not run any live probe (PR1/PR2 need real Reddit captures; PX probes need `--approve`). Gate state unchanged from STATUS: BG-1 FAIL until the firewall rule (O-2) is applied and the A19 sentinel passes; BG-3 depends on the pinned ACEs (O-1/O-1b accepted, BP3c pin check at first admitted session); BG-2 re-confirm on Edge 157.

## 5. Owner actions pending
- Create 2 more X accounts (rest week); Reddit accounts rest until 14-11-26.
- Review and apply the generated firewall rule (`browser_firewall_rule.py`; it applies to the Edge executable path).
- Create the private files per `deploy/README.md`; run probes with `--approve`.
- Provide real Reddit captures so the grammar extension can be done.
- Review PR, decide task-folder archiving.

## 6. Housekeeping observed
The main checkout has an uncommitted `api/data/attention_queries.json` change (`x_accounts_db_path` = `C:\xpool`, `x_accounts` = `["acct1","acct2"]`) that looks like test residue; not touched.
