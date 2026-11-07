# S-BrowserCDP slice report (07-11-26)

## 1. Status
CODE-COMPLETE on the in-memory pipe and on the real `browser_host` pipe against the spawned fake. LIVE-READY: NO (BG-2 not re-confirmed on Edge 157; BG-1/BG-3 unmet upstream). Default off: nothing constructs the client in production yet. Branch `claude/b2-validate`, not pushed.

## 2. Scope
Plan §S-BrowserCDP: A1-A4, A16-A18 over the pipe. Done criterion: "the guard proves the single chokepoint and no-input property statically" — met.

## 3. Changed paths
New: `api/data/attention/browser_cdp.py`, `api/tests/data/attention/test_browser_cdp.py`.
Chain edits (browser fixture/guard chain, S-BrowserHost → S-BrowserCDP): `api/tests/tooling_guards/test_browser_host_guards.py` (CDP guards appended), `api/tests/data/attention/browser_fake_main.py` (navigation `requestWillBeSent` now carries `type: "Document"`).

## 4. What was built
- `METHODS` exact per role (`session_check`, `reddit_read`, `bootstrap`), `BROWSER_LEVEL` scope set; no wildcards.
- `CdpClient._frame(session_id, method, params)`: the only `json.dumps` and the only `pipe.send`; checks session failure, 600 s bound, method in role table, browser-vs-session scope, known session, exact params key set/values per method, URL policy, evaluate policy, navigation/scroll caps, outbound frame ≤ 64 KiB; called only from `_call`.
- `UrlPolicy(site, subreddits=(), queries=())`: `.target(url, create=False)` (about:blank create-only; https, host exact, optional :443, no userinfo/fragment/`..`/backslash, templates `/`, x `/home`, reddit `/r/<sub>/new/`, `/r/<sub>/comments/<id>/`, closed query set) and `.observed_ok(url)` for main-frame/Document events (`navigation_off_allowlist` ends the session; subresources/child frames left to the relay).
- Evaluate: `location_href()` and `scroll(n)` (int 200..4000, not `session_check`, ≤ 12 per page).
- `bounds(role, max_body_bytes=None)`: session_check 65536/262144; reddit_read section size (default 262144, cap 2 MiB) ×4, 500 responses; bootstrap 2 MiB/16 MiB, 150 responses, 15 navigations; all ≤ 100 outstanding, 600 s. `Network.enable` accepts only the exact role bounds.
- Capture: requestId correlation through `loadingFinished`/`loadingFailed`; `Record.kind` ∈ data/redirect/cached (`fromDiskCache` or `requestServedFromCache`)/http_error/failed; redirect hops from `redirectResponse`; caps record `limits_hit` (`capture_outstanding_cap`, `capture_response_cap`); `body()` only for `data` records; `-32000 … evicted` → `capture_evicted`; decoded size ≤ resource bound.
- Cookies: `cookies(sid, urls, hook=None)` → `[{name, expires}]`; values go only to an in-memory hook, X only (`cdp_cookie_hook_refused` for Reddit).
- Errors are closed codes; device error text and frames never enter exceptions; no logging.

## 5. Interfaces for S-Relay / S-Cookie-C / S-OpsProbe / S-RBrowser
`CdpClient(pipe, role, UrlPolicy, *, max_body_bytes=None, clock=, timeout=30)`: `.version()`, `.open_page(url="about:blank") -> sid`, `.navigate(sid,url)`, `.location_href(sid)`, `.scroll(sid,n)`, `.cookies(sid,urls,hook=None)`, `.responses(finished=True) -> [Record]`, `.body(sid,request_id) -> bytes`, `.network_disable(sid)`, `.close_target(target_id)`, `.close()`, `.limits_hit`. A failed client is finished: tear down through the host job object, not CDP (stale replies may remain on the pipe). A19's `Browser.getVersion` round trip = `CdpClient(session.pipe, "session_check", policy).version()`; on failure S-Relay records `cdp_pipe_unavailable`.

## 6. Tests run
Red first: `test_browser_cdp.py` collection failed `ImportError: cannot import name 'browser_cdp'` (the guard additions ran in the same interrupted session). Green: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_browser_cdp.py api/tests/data/attention/test_browser_host.py api/tests/data/attention/test_browser_profile.py api/tests/tooling_guards/test_browser_host_guards.py api/tests/tooling_guards/test_reddit_collector_guards.py -q -rs` → 135 passed, 0 skipped. Note: these must run from the repo root (the spawned fake is `python -m api.tests…`); from `api/` the host lifecycle tests fail with `cdp_pipe_unavailable`.

## 7. Data verification
No files written by the module; tests write only under pytest tmp dirs. No network beyond the loopback fake pipe.

## 8. Error handling
Codes: `cdp_method_refused`, `cdp_session_unknown`, `cdp_params_refused`, `cdp_url_refused`, `cdp_evaluate_refused`, `cdp_frame_too_large`, `cdp_protocol_error`, `cdp_command_failed`, `cdp_timeout`, `cdp_pipe_unavailable` (transport), `cdp_cookie_hook_refused`, `cdp_role_invalid`, `cdp_bounds_invalid`, `cdp_policy_invalid`, `capture_evicted`, `capture_not_ready`, `capture_not_data`, `capture_too_large`, `capture_navigation_cap`, `capture_scroll_cap`, `capture_time_exceeded`, `navigation_off_allowlist`.

## 9. Deviations
- Not stated by the plan, chosen here: `session_check` keeps reddit_read's counts (500 responses, 100 outstanding, 600 s) with 0 scrolls; navigations are capped only for `bootstrap` (per-poll navigation budgets are BR-3, S-RBrowser).
- Off-allowlist detection is host-level for observed URLs (path templates apply to commands, not to in-site redirects).
- Unknown-length/compressed stress limits remain unproved (as A18 states).
- Real Edge not launched: the slice acceptance is static; BG-2 re-confirmation per version is A19 (S-Relay).

## 10. Gate honesty
BG-2: BP2 VIABLE on Edge 156 only; NOT re-confirmed on 157 → pending A19. Live use stays refused until A19's round trip passes.

## 11. Next
S-Relay (Stage 5): A19 self-test uses `version()` over `BrowserHost.launch(...).pipe`; S-Cookie-C consumes `cookies(..., hook=)`; S-OpsProbe/S-RBrowser use the `bootstrap`/`reddit_read` roles.
