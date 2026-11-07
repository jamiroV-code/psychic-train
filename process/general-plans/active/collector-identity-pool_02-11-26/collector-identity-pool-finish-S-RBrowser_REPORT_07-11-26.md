# S-RBrowser slice report: PRIMARY Reddit browser method (07-11-26)

## 1. Status
CODE-COMPLETE on fixtures. NOT LIVE-READY. LIVE-READY waits on: a published `browser` section and an owner-approved PR2 bootstrap then verify; BG-1 (A19 self-test outcome, O-2 firewall rule applied), BG-2 re-confirmed on Edge 157, BG-3 (BP3c pin at the first admitted session); accounts ready after the rest ends on 14-11-26, each logged in once. Default off: nothing runs unless `browser` is in `reddit_live_methods`. No live request was sent and real Edge was never launched. Only the spawned `browser_fake_main` and in-memory drivers ran. Branch `claude/b2-validate`, committed locally, not pushed.

## 2. Scope
Plan §S-RBrowser BR-1..BR-6, RC-9 supply, CK-6 Reddit wiring. Both halves were done in one commit:
- **Surface and lanes:** the evidence state machine, the CDP driver, the PR2 executor, and relay hosts taken from the published section.
- **Account scheduling and wiring:** the Reddit account pool plus `RedditRoutes`, which builds an `AdmittedRoute` from `snapshot.reddit_assignments` and `revisions`. The admission provider goes into `reddit_accounts.from_config`, and `reconcile(..., reddit=RedditRouteView)` is called from both the method and the `browser_session` CLI.

## 3. Changed paths
- New: `api/data/attention/reddit_browser.py`, `api/scripts/probe_browser.py`, `api/tests/data/attention/test_reddit_browser.py`, `api/tests/scripts/test_probe_browser.py`.
- `api/data/attention/browser_session.py`:
  - adds `SessionRefused` and `open_browser(...)`. `check_session` now uses them; its behaviour is unchanged.
  - the CLI builds `RedditRoutes` for `--site reddit` (previously DENY).
  - the CLI records the Reddit session outcome in the account pool, so an owner relogin reopens the pause.
- `api/data/attention_pc_live.py`: `deps` adds `config_path`; the `poll_result` fact `account` is `method.last_account`.
- `api/scripts/probe_executors.py`: a PR2 branch in `build_dependencies` and the registration import.
- Tests:
  - `browser_fake_main.py`: scripted `xhr` and `scrolls` captures.
  - `test_probe_executors.py`, `test_probe_gql.py`: PR2 is no longer pending.
  - guard chain links in `test_browser_host_guards.py` and `test_reddit_collector_guards.py`.
- This report.

## 4. Work completed
- **BR-1 gate**, in this order:
  1. The `disabled` switch.
  2. The surface: `needs_probe` or `unsupported_format`.
  3. `probe_owner.verify_gate`, which must be fresh, pass, and match hash and revision; otherwise `needs_probe`.
  4. Browser configured; otherwise `method_unavailable`.
  5. The relay admission record of the binary (`read_admission`): `browser_unadmitted` or `containment_residual_unaccepted`.
  6. A sticky session refusal held for 1 h: `cdp_pipe_unavailable` or `profile_policy_unsatisfied`.
  7. At least one ready account, otherwise `no_ready_account`. A proxy account that can be admitted also counts.

  The launch-time login check is the first navigation of each session: final URL plus cookie names through CK-1 `classify`, so it costs no extra navigation.
- **BR-2 evidence:**
  - `read_chain` navigates only to allowlisted pages and matches captures to section endpoints.
  - Each next page must carry the previous page's `next_cursor`, placed where `request_cursor` says. This is the request→response→body correlation. The chain continues to the floor, scrolling for each page.
  - Stop reasons: `exhausted`, `cap` (pages, 12 scrolls per page, navigations, minutes), `error` (non-200 status, missing next page, CDP failure), `empty_shell` (no matching response, including block pages), `schema_mismatch`, `unsupported_format`, and `login_required` (all attempts lost).
  - Comments come only from the threads opened.
  - Items are reduced at once (`reddit_core.reduce_item`).
- **BR-3:**
  - Per attempt, navigations are capped at the lesser of the daily navigations left and the account cap left.
  - `_browser_state.json` persists the browser seconds per UTC day. When they are exhausted, `next_poll_due` moves to the next UTC midnight.
  - The machine lock (`browser_busy`) or low memory delays the poll by 60 s.
- **BR-4:**
  - `reddit_accounts.run_poll`: on a login or challenge loss the account is paused, its navigations stay charged, a `challenge` fact is written, and the poll is retried once on another account.
  - `proxy_not_admitted` puts the route in an unknown state, not the session.
  - An owner relogin through `browser_session --site reddit --interactive` reopens the account.
- **Routes:** `RedditRoutes` runs `ProxyRuntime.reconcile(_XUntouched(), reddit=RedditRouteView)`, so the X pool is never written from here. It provides `route_admission` and an `admitted_route` that mirrors `XRouteProvider`:
  - direct only under the all-null configuration;
  - proxy only for an admitted, current-revision assignment;
  - its `admission()` returns `None` after expiry.

  The relay allowlist for a read is `section.hosts`; bootstrap uses the relay's bootstrap hosts.
- **PR2:** the executor works over the driver seam.
  - `bootstrap` captures listings with scrolls plus one thread, runs `surface_tool.propose`, then `write_candidate`. Bodies are never written.
  - `verify` reads the published grammar through `read_chain`; the record binds its hash.
  - Production dependencies use the least recently used ready account's profile.

## 5. Interfaces
- `reddit_browser.make_method(config, deps)`. Optional deps: `config_path`, `reddit_routes`, `browser_host`, `reddit_sessions`, `browser_admission`, `monotonic`, `hasher`, `queries`.
- `RedditRoutes(config, *, config_path, runtime=None)` with `.refresh() -> RedditAccounts`, `.admit(label)`, `.route_admission`, `.admitted_route`.
- `BrowserSessions.open(label, *, role, section, subreddits)`: a context manager yielding a `CdpDriver`.
- Driver seam: `navigate(url) -> ok|login_required|challenge`, `scroll()`, `drain() -> [Capture]`, `refused_hosts()`.
- `read_chain(driver, section, lane, url, *, budget, max_pages, floor) -> Chain(pages, stop, abort)`.
- `browser_session.open_browser(...)`.
- `probe_browser.pr2_browser`.

## 6. Tests run
Command: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest <files> -q -rs` (repo root).
- **Red, actually run:** with `reddit_browser.py` and `probe_browser.py` held aside, 3 collection errors (`test_reddit_browser`, `test_probe_browser`, `test_probe_executors`: ImportError).
- **Green, slice files:** `test_reddit_browser.py`, `test_probe_browser.py`, `test_probe_executors.py`, `test_reddit_collector_guards.py`, `test_browser_host_guards.py` → **72 passed**, 0 skipped. This includes the 2 Windows end-to-end cases over the real host, CDP, relay and `RedditRoutes`.
- **Adjacent:** `test_browser_session.py`, `test_reddit_accounts.py`, `test_x_proxy_reddit.py`, `test_reddit_core.py`, `test_reddit_live.py`, `test_reddit_gql.py`, `test_browser_cdp.py`, `test_browser_relay.py`, `test_probe_owner.py`, `test_probe_gql.py`, `test_surface_tool.py` → 353 passed, 1 failed. The failure was a stale `"PR2" not in EXECUTORS` assertion in `test_probe_gql.py`, now updated. On the rerun, `test_probe_gql`, `test_probe_browser` and `test_probe_executors` gave 33 passed.
- `test_attention_pc_refresh_stream.py -k "live or deps"` → 7 passed.

## 7. Data verification
Synthetic data only: `reddit_probe_fixtures` captures, with `SECRET_MARK` in every text and planted usernames. The tests scan every cache file, the `repr` of results and the method, and the probe cache root. None of the planted values were found, and the cookie marker does not appear on disk.

## 8. Error handling
Each failure ends up as one of the following:
- a lane stop reason;
- a gate state;
- an account loss code (`reddit_login_required`, `challenge`, `proxy_not_admitted`);
- an allowlisted PR2 reason code.

Further rules:
- `Refused` (busy, low memory, unadmitted browser) returns an empty poll and is never counted as a failure.
- Facts errors are swallowed.
- There is no logging.

## 9. Deviations and interpretations
1. **Interpretation:** BR-1's `reddit_login_required + needs_owner` is not in the closed `GATE_STATES`. The gate reports `no_ready_account`, the paused reason sits on each account (`reddit_accounts.json`), and a poll where every attempt was lost writes `login_required` lanes.
2. **Ownership chain edits:**
   - `browser_session.py` (S-Cookie-C, CK-6 Reddit wiring is this slice): adds `open_browser`, the CLI routes and the session record.
   - `attention_pc_live.py` (S-RCore-B): adds `config_path` to deps and the account label in facts.
   - `probe_executors.py` (S-OpsProbe): the PR2 registration.
   - `browser_fake_main.py` (browser fixture chain).
   - `test_probe_gql.py`: one stale assertion.
3. **Limitation:** the CDP capture holds no request bodies, so a section whose cursor is placed in the body cannot be chained past page 1 (the lane ends `error`). The synthetic grammar uses query cursors. PR2 decides fit.
4. **Interpretation:** with no routes provider and no config path (an injected config), `RedditRoutes` is direct-only. Proxy configuration without the private files resolves to every label unadmitted.

## 10. Review decision needed
- After PR2 bootstrap on real Reddit, check whether listings arrive as XHR captures. Server-rendered first pages would make every lane `empty_shell`. A misfit goes to "extend parser" (authorized) or an owner decision (B2/BR-6).
- Security re-read of `open_browser` (shared by the session check and the reader) and `RedditRoutes` (`_XUntouched` reconcile).

## 11. Handoff
- **Owner runbook (S-OpsDeploy):**
  1. After rest and login: `python -m api.scripts.probe_owner PR2 --mode bootstrap --approve <digest>`.
  2. `surface_tool --approve-surface browser`.
  3. `probe_owner PR2 --mode verify --approve <digest> --surface-path <surface>`.
  4. Add `browser` to `reddit_live_methods`.
  - Rollback: remove `browser` from `reddit_live_methods`, then delete `<cache>/attention/reddit_live_browser/_meta/_browser_state.json`.
- **S-Report / S-OpsDoctor:** read `_browser_state.json` (seconds per day), `poll_result.account`, and `challenge` facts.
- **Main:** rerun the files listed in §6.
