# S-XDrift EXECUTE report — 07-11-26

## 1. Status
CODE-COMPLETE for S-XDrift (XD-1 to XD-4). Everything stays off by default: `x_queryid_mode=off` binds nothing, makes no check and runs no evaluation. No live X, Reddit or provider requests were made, and LIVE-READY is not claimed. Work is in worktree `wt-b2-validate` on branch `claude/b2-validate`. Nothing was pushed and no PR action was taken (task envelope).

## 2. Scope
Finish PLAN §S-XDrift, contract E (forced candidate evaluation), contract G literal pool defaults (`endpoint_404_day: null`, `endpoint_404_count: 0`), contract D facts call sites (isolation, locks, evaluations), and the ownership chains for `x_pool.py`, `x_reader.py`, `twscrape_reader.py` and the small `attention_pc_refresh.py` edit. Interfaces consumed: S-XProto `x_queryids` / `x_queryids_fetch.run_check` / `bind_query_id`, and S-Facts `daily_facts.append`.

## 3. Changed paths
- `api/data/attention/x_pool.py`
- `api/data/attention/x_reader.py`
- `api/data/attention/twscrape_reader.py`
- `api/data/attention_pc_refresh.py` (small edit: 13 lines)
- `api/tests/data/attention/test_x_pool.py`
- `api/tests/data/attention/test_x_reader.py`
- `api/tests/data/attention/test_twscrape_reader.py`
- `api/tests/data/test_attention_pc_refresh.py` (one new test)
- This report.

## 4. Implementation
- **XD-1.** `_run_attempt` now returns a `not_found` restart instead of counting drift. `run_unit` reruns the same unit once on another selectable account. The rerun gets one extra attempt beyond `x_unit_max_restarts`, is charged normally and counts as one unit. If the rerun succeeds, `XPool.note_endpoint_404` sets `endpoint_404_day` and increments `endpoint_404_count`. The first account then shows `("locked","endpoint_restricted")` for the rest of the UTC day. A second event on a different day sets `lock_until` = now + 24 h with reason `x_endpoint_404`, shown as `("locked","endpoint_404")`. The count resets when more than 7 days have passed since the last event. A 404 on both accounts, or with no other account, is drift (`confirmed` when two accounts saw it). No proxy is rotated. The two new account keys use `setdefault` migration before the exact-key check and are validated as ISO day or null and int ≥ 0.
- **XD-2.** `INACTIVE_CODES[64]="x_account_suspended"`. `ReaderFailure(codes=...)` keeps only allowlisted integer codes (the `INACTIVE_CODES` keys). `map_exception` takes the codes from `ApiError.errors` strings and never keeps the text. `x_reader.inactive_reason()` maps those codes to a reason, except 88 (a rate limit is never a ban). A unit or canary that hits such an error deactivates the account and alerts. The unit then fails over through the normal restart, and reads are charged once.
- **XD-3.** `XPool.evaluate_candidate(operation, candidate_id, *, readers, src, config, bind, observed_by=None)` handles SearchTimeline only and does not look at the canary's `already_passed` cache. It reads one canary page per account with the candidate bound, charged normally, on up to 2 distinct selectable accounts, trying accounts other than the observer first. It writes one evidence record per executed evaluation. An evaluation passes only with ≥ `x_canary_min_results` parseable in-window ids and no parse drop. A 404, GQL-outdated or parse failure counts as failed. A block, proxy, account or other error, or too few results, counts as inconclusive. Aggregation follows contract E exactly. It returns `adopted`, `rejected` (`rejected_until` +24 h, `evaluation_failed`), `inconclusive` (the candidate stays), `budget` (3 per UTC day) or `no_candidate`. Evidence is trimmed to 32 records and the active entry's evidence is never dropped. The registry's active ID is always re-bound in `finally`.
- **XD-4.** In `auto` mode, with a bind hook and a registry candidate, a confirmed drift runs the evaluation before `DRIFT_STOP`. A confirmed drift is the one that would stop X, or a 404 seen on two accounts. An adoption clears the drift streak. `twscrape_reader.query_hook_compatible()` checks that `twscrape.api.OP_SearchTimeline` has the expected shape and that `API.search_raw` reads it as a global. It returns True on the installed pinned library. `start()` refuses with `query_hook_incompatible` when the mode is not off and this check fails. `XStart.query_boundary(config, pool, cache_root, now)` does the following:
  - runs `run_check` at most once per UTC day, on the admitted route/policy of the next account `pool.peek()` would select (direct when there is no policy; no request without admission);
  - binds the registry's active SearchTimeline ID.

  `XStart.bind_query` exposes the bind. The worker calls `query_boundary` at every unit boundary, inside the existing reconcile `ProxyFailure` handler, and passes `bind=start.bind_query` to `run_unit`.
- **Facts.** The `account_state` kind records `pause/endpoint_restricted` and `lock/x_endpoint_404`. The `handoff` kind records `endpoint_404` with from/to labels. The `queryid_state` kind records each evaluation verdict. Switch provenance comes from `x_pool.facts_switches(config)`: the mode plus the boolean finish switches, without names containing "cookie", which the facts key guard rejects. Fact writes never stop collection.

## 5. Qualifications
- The worker test was written after the worker edit, so it was not run red first. All other new tests were run red first.
- Evaluation pages call `src.record_unit()` the same way canary pages do.
- The sentinel runs once per UTC day at a unit boundary (the plan sets no cadence).
- In off mode the hook check is skipped, so off-mode behaviour is unchanged.

## 6. Tests and evidence
Red run first (new tests, before implementation): `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_pool.py api/tests/data/attention/test_x_reader.py api/tests/data/attention/test_twscrape_reader.py -q -rs`: **28 failed, 153 passed, 1 skipped**.

Green runs:
- The same three files: **181 passed, 1 skipped**.
- With `test_x_proxy_state.py`, `test_x_queryids.py`, `test_x_queryids_fetch.py`, `test_identity_transport.py` and `test_x_proxy_runtime.py` added: **261 passed, 1 skipped**.
- `test_x_proxy_spawn.py`, `tooling_guards/test_pc_collector_guards.py` and `tooling_guards/test_x_reader_guards.py`: **47 passed**. This run came after fixing one guard hit: the evidence ID had used an hour format, and now uses an epoch integer.
- Worker files (`test_attention_pc_refresh.py`, `test_attention_pc_refresh_collector.py`, `test_attention_pc_refresh_stream.py`) plus `analytics/attention/test_sources_health.py`: **178 passed**, 441 s.

The skip is the POSIX mode bits test on Windows. Running `test_x_proxy_spawn.py` in the same pytest invocation as the `api/tests/data/*.py` files produced `fixture 'attention_cache' not found` collection errors. That file passes alone. Not touched, since it is outside this slice.

No full suite, lint, formatter or live smoke test was run.

## 7. Interfaces and on-disk layout
- Pool account keys added: `endpoint_404_day` (ISO day or null) and `endpoint_404_count` (int ≥ 0). `XDRIFT_ACCOUNT_DEFAULTS` holds the literals.
- New `account_state` reasons: `endpoint_restricted` and `endpoint_404`. The account `reason` value `x_endpoint_404` is used while locked.
- `XPool.note_endpoint_404(label) -> "restricted"|"locked"`
- `XPool.evaluate_candidate(...) -> adopted|rejected|inconclusive|budget|no_candidate`
- `XPool.peek()` and `XPool.fact(event)`
- `run_unit(..., bind=None)`
- `x_reader.inactive_reason`, `ReaderFailure.codes`
- `twscrape_reader.query_hook_compatible`, `XStart.query_boundary`, `XStart.bind_query`
- The registry layout is unchanged from S-XProto. Evidence IDs look like `ev<epoch>_<i>_<label>`.

## 8. Failure and disclosure behavior
- Facts, logs and the registry carry no API error text, cookies or route data: only labels, codes and verdicts.
- A changed library hook refuses the start (when the mode is not off) or raises `ProxyFailure(proxy_config)` at the boundary, which pauses the pass with that reason.
- An unadmitted routed account makes no static request.
- A rejected or inconclusive candidate never changes the bound ID.

## 9. Approved deviations
- None outside the slice's owned files.
- The guard files needed no edit.
- The `attention_pc_refresh.py` edit is 13 lines, within the ~40-line budget.

## 10. Rollback and operator documentation fragment
To roll back to the Stage 3 checkpoint:
- stop the collector;
- remove `endpoint_404_day` and `endpoint_404_count` from every account in `x_pool.json`;
- restore the Stage 3 code for parent and child together.

`x_queryids.json` evidence written by evaluations stays valid under the S-XProto validator. Operators: `x_queryid_mode=auto` lets a confirmed drift adopt a candidate only after passed forced evaluations, and `sentinel` only observes. An account shown as `endpoint_restricted` sits out SearchTimeline for the rest of the UTC day; `endpoint_404` is a 24 h lock that clears by itself.

## 11. Next ownership handoff
- S-XCookie continues the `twscrape_reader.py` chain.
- S-B3P continues the `x_pool.py` chain. Ordinary-operation `ordinary_op_stale` handling stays with B3, and the restriction currently applies to every unit because all units are SearchTimeline.
- S-RCore-B rebases its worker edit on this one.
- Main runs the stage gate.
