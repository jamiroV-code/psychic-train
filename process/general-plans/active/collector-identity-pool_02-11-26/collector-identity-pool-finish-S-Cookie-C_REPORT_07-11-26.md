# S-Cookie-C slice report (07-11-26)

## 1. Status
CODE-COMPLETE on fixtures (real host + real relay + real CDP client over the spawned fake; in-memory pipe for polling). LIVE-READY: NO (BG-1 FAIL, BG-2 pending on Edge 157, BG-3 NOT-MET until O-1/O-1b). Default off: nothing calls the helper automatically; the CLI's default route provider denies. Branch `claude/b2-validate`, not pushed.

## 2. Scope
Plan §S-Cookie-C: CK-1..CK-7, new files only, plus the browser guard chain link (relay constructor set, CK-3 static guard).

## 3. Changed paths
New: `api/data/attention/browser_session.py`, `api/tests/data/attention/test_browser_session.py`.
Edited (guard chain): `api/tests/tooling_guards/test_browser_host_guards.py` (relay constructors = {`browser_selftest.py`, `browser_session.py`}; admission_run still only self-test; new CK-3 guard + planted-code test).

## 4. What was built
- `check_session(site, label, *, host, profile_name, day_guard, routes, mode, timeout, clock, sleep, wall) -> SessionResult`. Order: automatic → `DayGuard.try_claim(site, label, utc_day)` (false → `failed/daily_check_used`, nothing else runs); `RouteProvider.admitted_route` (non-`AdmittedRoute` → `refused/proxy_not_admitted`); real `Relay` per session; `host.launch` (machine lock, profile, admission, memory gates); `CdpClient.version()` (failure → `refused/cdp_pipe_unavailable`); `observe`; teardown via session exit (job object) and relay close. Never retries, never relaunches.
- `observe`: one `Page.navigate` to the home; automatic/probe wait ≤ timeout only for the page to leave `about:blank`, then one cookie read and classify; interactive polls href+cookies every 2 s until logged in or timeout, never sending input.
- `classify`: X logged in iff netloc exactly `x.com`, path `/home`, `auth_token`+`ct0` present; login paths → `login_required/login_page`; `/account/`, other `/i/flow/` → `challenge`. Reddit: netloc exactly `www.reddit.com` (raw netloc, case-sensitive; bare/old/http/uppercase → `host_mismatch`), first segment login/register → login_required, account/verify/captcha → challenge, `reddit_session` absent/expired/session-only → login_required. Off-allowlist redirect (CDP `navigation_off_allowlist`) → `login_required`.
- CK-4 `--probe` uses the `bootstrap` CDP role; CK-5 `earliest_expiry` + `expiry_class` (absent/session/expired/lt_1d/lt_7d/lt_30d/ge_30d).
- Values: Reddit values dropped at parse (CDP client, hook refused); X values only in `SessionResult.cookies` (repr=False, excluded from `public()`), only when logged in.
- CLI `python -m api.data.attention.browser_session --site x|reddit --label L [--init-profile|--interactive|--probe]`: one JSON line; `--init-profile` → `ProfileStore.prepare` (A10).

## 5. Interfaces
`AdmittedRoute(mode, revision, admission: () -> browser_relay.Admission, route=PrivateRoute|None, hosts=None)`; `RouteProvider.admitted_route(site,label) -> AdmittedRoute | refusal str`; `DayGuard.try_claim(site,label,day) -> bool` (real Reddit: `RedditAccounts.try_claim`); `SessionResult{site,label,state,reason,mode,owner_initiated,cookie_names_present,earliest_expiry,expiry_class,cookies}`; `STATES`, `REFUSED_REASONS` (exactly CK-7), `ROLES`, `DENY_ROUTES`, `classify`, `expiry_class`, `observe`, `main`. S-RAcct-B's admission (`'proxy'|'direct'|'unadmitted'` string) needs an adapter producing `AdmittedRoute` with the account's `PrivateRoute` — owned by S-RBrowser (Reddit) / S-Cookie-X (X) per CK-6.

## 6. Tests run
Red first (run): `test_browser_session.py` + guards → collection ImportError (module absent). Green: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_browser_session.py api/tests/tooling_guards/test_browser_host_guards.py -q -rs` → 76 passed, 0 skipped (58 s). Adjacent: `test_reddit_collector_guards.py test_browser_selftest.py test_reddit_accounts.py` → 47 passed. Real Edge never launched; no network.

## 7. Data verification
Fixture runs write only under pytest tmp (profiles, admission record, launch record removed at close, `reddit_accounts.json` for the real guard). Marker scan: the cookie marker never appears in `public()`, repr, CLI output, or any written file except the fake's own script/jar.

## 8. Error handling
Closed codes only. Refused (CK-7): the seven gate reasons. Failed: `daily_check_used`, `day_guard_unavailable`, `label_unconfigured`, `browser_not_configured`, relay/CDP/profile reason codes. No logging, no print except the CLI line.

## 9. Deviations
- Cookie AGE is not observable via `Network.getCookies` (no creation time); CK-5 carries expiry class + earliest expiry; age stays with the caller (`cookie_ages`, S-Cookie-X).
- The day guard is claimed FIRST (before route/gates), so a refused attempt consumes that day's automatic check (strict "one automatic attempt per day"); owner `--interactive`/`--probe` bypass it.
- "No second automatic attempt" returns `failed/daily_check_used` (not `refused`, to keep CK-7's reason set closed).
- CLI X automatic returns `day_guard_unavailable` until S-Cookie-X wires the pool key; CLI default `RouteProvider` is `DENY_ROUTES` until S-Cookie-X / S-RBrowser wire real providers.
- Interactive test of the poll loop uses the real `CdpClient` over an in-memory pipe (the spawned fake has a static jar); gate/state cases use the real host + fake.

## 10. Gate honesty
BG-1 FAIL, BG-2 pending (157), BG-3 NOT-MET: live use returns `refused` with the matching reason. PX6/PR2 real behaviour not exercised.

## 11. Next
S-OpsProbe consumes `--probe`/`check_session(mode="probe")`; S-Cookie-X wires X DayGuard (pool `harvest_day`) + B2 route; S-RBrowser wires `RedditAccounts.try_claim` + S-RAcct-B route into `AdmittedRoute`. Owner: O-1/O-1b/O-2, then one manual login per profile via `--interactive`.
