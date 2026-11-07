# S-RAcct-A slice report (07-11-26)

## 1. Status
CODE-COMPLETE for account-state scope; not LIVE-READY. No push or PR (assignment explicitly prohibits pushing).

## 2. Scope
Reddit account state, selection, navigation accounting, rest/ready gates, session outcomes, atomic session day guard and pure poll failover. No runtime browser/provider calls.

## 3. Changes
- Added `api/data/attention/reddit_accounts.py`.
- Added `api/tests/data/attention/test_reddit_accounts.py`.
- Added this report. No sibling-owned files edited.

## 4. Tests (red first, then green)
Command: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_reddit_accounts.py -q -rs`.
Initial red: import collection error before implementation. Rollback regression red: 1 failed, 25 passed. Admission seam red: 28 failed, 4 passed (new keyword not implemented, default admission open). Final: 32 passed in 3.15s. No full suite, network or live checks.

## 5. Evidence
Coverage includes exact keys, migration, removed-label retention, StatusAPI reader compatibility, LRU selection, cap skip/day reset, rest and next-day ready, no-ready missing result, one-account poll, one failover with failed navigations charged and only successful data returned, sticky suspension, session reactivation, restart persistence, six concurrent independent day-guard claimants, clock rollback, CLI and five direct/off configuration combinations.

## 6. Deviations
Parent resolved the proxy interface question: preserve all seven B2 fields and add derived `proxy_state`; default-deny injected admission. No live requests. During test development the cache isolation fixture was initially missing; test-created Reddit account/ready files and their locks in the worktree cache were removed, then the fixture was added and all final runs used temporary caches.

## 7. Interfaces
`RedditAccounts(labels, clock=..., cap=..., rest_days=..., proxy_required=False, admission=None)`; `from_config(config, clock=..., admission=None)`.

Admission seam: `admission(site: str, label: str) -> str`, with site always `reddit`; allowed successful route modes are `proxy` and `direct`, otherwise unadmitted. Omitted provider always refuses. Required proxy additionally needs stored healthy state; healthy alone never admits. `from_config` requires proxy whenever `x_proxy_required` is true OR any of `x_proxy_list_path`, `x_proxy_assignments_path`, `x_proxy_policy_path` is non-null (including union assignment configuration). Only all-null plus required=false permits an explicitly admitted direct route.

S-RAcct-B owns authoritative current site-scoped route admission, union assignment reconciliation and runtime integration. It injects the provider and writes the seven fields using `set_proxy(label, **fields)`. Provider is a pure admission lookup under the state lock, not a networking callback. This is planned B-scope, not a deviation.

`try_claim(site, label, day: ISO-day-string) -> bool` implements the injected CK-2 day guard; claims persist and older days never reopen. `record_session(label, state)` persists safe session state, not cookies. `begin_pass()` persists registration/rest start before polling; read-only selection alone does not persist registration.

`run_poll(pool, read)` expects `read(label) -> (value, navigation_count)` or `AccountLost(reason, navigations=n)`. It never merges failed data and retries at most once on a distinct account. Browser caller owns per-navigation/global budgets and actual IO; `charge` records completed/failed navigation counts, not a pre-send reservation.

On disk: `_pc_state/reddit_accounts.json` is `{"accounts": {label: entry}}`. Entry has state/reason, reads_day/reads_used, rest_until/last_used, session_state/session_checked_at/session_day, all seven B2 fields and derived proxy_state. `_pc_state/reddit_account_ready.json` is `{"ready": {label: "YYYY-MM-DD"}}`, effective from next UTC day. Matches StatusAPI section 7.

## 8. Risks
Only targeted file-only tests exercised. Live route validity, browser serialization and navigation limits depend on the assigned downstream runtime slices. No claim of a live-ready account or live Reddit behavior.

## 9. Rollback
Remove/revert the two new code/test files and this report. No existing code/schema consumer changed. New state files can remain unused; absent state is unknown to StatusAPI. No rollback of a live deployment was exercised.

## 10. Open questions
None blocking the A-scope interface after parent's admission decision.

## 11. Next
Main integrates the committed slice. S-RAcct-B injects authoritative admission; Cookie-C consumes the day guard; RBrowser supplies whole-poll reader and navigation budget enforcement. Owner mark: `python -m api.data.attention.reddit_accounts --mark-ready LABEL [--queries PATH]`.
