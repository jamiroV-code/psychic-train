# S-RAcct-B slice report (07-11-26)

## 1. Status
CODE-COMPLETE for contract F. Not LIVE-READY: no live request was sent and no real proxy, Reddit account or browser was used.

## 2. Scope
Plan: `collector-identity-pool-finish_PLAN_06-11-26.md`, slice S-RAcct-B, contract F, rollback row "6 S-RAcct-B". Combined X/Reddit assignment namespace, site-scoped reconciliation, Reddit route admission provider, single provider budget.

## 3. Changed paths
- `api/data/attention/x_proxy.py`: `parse_assignments(..., reddit_labels=())` takes the union; an X/Reddit label collision is `proxy_config`; unknown labels and duplicate proxy IDs/exits are refused across both sites; `required` still demands every X label; a Reddit label without an entry is valid but is never admitted. The v1 exact-key schema is unchanged and has no `reddit_accounts` key.
- `api/data/attention/x_proxy_snapshot.py`: `load_snapshot` passes the configured `reddit_browser_accounts` labels.
- `api/data/attention/x_proxy_runtime.py`:
  - `Snapshot.reddit_assignments`: `assignments` stays X-only, so the twscrape and child paths are unchanged.
  - `ProviderBudget`: wraps the X pool's `provider_request`.
  - `RedditRouteView`: writes the seven B2 fields through `RedditAccounts.set_proxy`.
  - `ProxyRuntime.reconcile(pool, *, reddit=None)` is site-scoped. X effective state excludes `reddit_*` config keys. Reddit effective state is assignment + policy + `x_proxy_*` keys. The raw-only eviction fires only when neither site changed semantically. Pruning a label is site-aware. The method returns only the changed X labels.
  - `admit()` resolves the union assignment and refuses a missing one with `proxy_assignment` before any reservation.
  - `route_admission(site, label)` is the authoritative S-RAcct-A provider.
- `api/tests/data/attention/test_x_proxy_reddit.py` (new, 16 tests).

## 4. Tests
Red first: the new file failed 15 of 15 before implementation (`proxy_assignment` from the X-only parser, missing APIs). The parametrized case brings the green count to 16.
Green, targeted: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest` over `test_x_proxy_reddit.py` and every other `test_x_proxy*.py`, plus `test_x_pool.py`, `test_reddit_accounts.py`, `test_twscrape_reader.py` and `test_identity_transport.py`. Result: **484 passed, 1 skipped** (POSIX mode bits), in 210 s.

What the new tests cover:
- Reddit labels are accepted, unknown labels rejected, a cross-site label collision is a config error.
- A duplicate exit or proxy ID across sites is refused and the error carries no secret.
- The snapshot holds the union while the X child's `admission_role` still refuses a Reddit label.
- Reconciliation is site-scoped in both directions.
- An unassigned Reddit label is never admitted.
- A proxy-required Reddit account is never selected until it is admitted; once admitted it is selected.
- Failure quarantines; replacement resets quarantine and needs a fresh admission; rollback gives a new revision and is unadmitted again.
- Single 899/day budget under two-site contention, with no second budget record; with no X pool, ipapi is refused before any send.
- Direct mode only for the all-null configuration.
- Secret marker scan of reprs, Reddit/X state and the admission cache.

## 5. Acceptance (AC9)
- The inherited B2 route-failure matrices pass unchanged.
- Reddit admission, quarantine and replacement reuse `ProxyRuntime.admit` and its health interval.
- An unadmitted Reddit account resolves to `locked/proxy_not_admitted` through the real `RedditAccounts`, so no browser is ever selected.

## 6. Deviations
1. **Account-view names.** The Reddit side implements the B2 route protocol that `ProxyRuntime` already drives on `XPool`: `reconcile_proxy`, `proxy_result`, `proxy_unknown`, `provider_request`, `path` and `_acct`, plus `labels()`. It does not use the literal names `get`, `set_route_fields` and `admit_inputs`. There is therefore no X-side adapter edit in `x_pool.py`: `XPool` already is that view, and `XPool.labels` is an attribute, so a `labels()` method would collide with it. Contract semantics (each site reconciles only its own labels) are kept and tested.
2. **Private read.** `RedditRouteView._acct` reads the B2 fields through `RedditAccounts._load()` under its `state_lock`, because S-RAcct-A exposes no public getter. `reddit_accounts.py` was not edited.
3. S-XProto's `one_shot` and `test_x_proxy_spawn.py` amendments are untouched and still pass.

## 7. Interfaces
- `ProxyRuntime.route_admission("reddit", label) -> "proxy"|"direct"|"unadmitted"`: inject it as `reddit_accounts.from_config(config, clock=..., admission=runtime.route_admission)`.
- `RedditRouteView(accounts, ProviderBudget(x_pool), clock=...)`: pass it as `runtime.reconcile(x_pool, reddit=view)` and admit with `runtime.admit(label, view)`.
- The proxy-mode `AdmittedRoute` (revision, relay callable, `PrivateRoute`) needed by Cookie-C's helper is built by S-RBrowser / S-Cookie-X from `runtime.snapshot.reddit_assignments[label].route` and `snapshot.revisions[label]`.

## 8. Risks
- Production wiring (who constructs the view and calls `reconcile(..., reddit=)` per pass) belongs to S-RBrowser.
- Until it lands, Reddit stays default-deny.
- `_acct` depends on S-RAcct-A's private `_load`.

## 9. Rollback
Revert the three code files and the new test. Per plan G stage 6, remove the Reddit label entries from the owner's private assignments file. With the code reverted, the pre-RAcct-B parser rejects them as unknown labels.

## 10. Open questions
Whether the literal account-view names (`get`, `set_route_fields`, `admit_inputs`) are required. Security re-read at VALIDATE v2 is pending.

## 11. Next
Main integrates. S-B3I and S-RBrowser consume `route_admission`/`RedditRouteView`. Commit on `claude/b2-validate` only; not pushed.
