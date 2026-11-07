# S-B3I report (07-11-26)

## 1. Status
CODE-COMPLETE (targeted tests green). Not LIVE-READY: no live request was made. All five B3 switches default off. Security re-read requested for the child-envelope `count` extension and the `ordinary` low-level request.

## 2. Scope delivered
- `x_pool.py`: quiet-hours and B3 cooldown holds lock an account like an in-flight lock (`b3_hold`, `B3_WAIT_REASONS`). The pool waits for the earliest end, never the whole day. A challenge waits for the owner, and `owner_clear` lifts it. Warm-up starts in `begin_pass` and lowers the cap through `effective_cap` (also used by `remaining_caps` and `account_state`). Rate-limit, confirmed stripped-strike and shrink-run cooldowns go through `apply_cooldown`. `note_result` and a `unit_completed` fact are recorded after each successful unit. Status has a `behaviour` block only when a switch is on. `run_mixed` and `mixed_pick` make at most one approved ordinary call. That call is charged max(20, actual) at the page callback, including on failure. A 404 suspends the operation as `ordinary_op_stale`. `_run_attempt` uses the variation page size and pause multiplier.
- `twscrape_reader.py`: `TwscrapeReader.ordinary(op, target, on_page)` handles only the allowlist `user_by_login` / `tweet_details` / `user_tweets` with pinned operation IDs (not the query-id registry). It checks the target shape, gets the queue context, uses the cached transaction id, and makes exactly one identity-bound `ctx.clt.request`. It does not go through `Ctx.req` or `QueueClient._check_rep`. It charges before classifying the response, classifies the response locally, and the queue context is closed on exit. `fallback_request` and `_child_work` accept the optional `count` in {10, 20}.
- `x_proxy_snapshot.py`: `work_envelope` authenticates `count` with null-vs-present framing, the same way it does `cursor` and `query_id`.
- `x_raw.py`: `write_page(requested_page_size=)` records the page size, and `reparse` checks cursor exhaustion against it. Records without it fall back to `PAGE_ENTRIES`. First-write-wins and UTC behaviour are unchanged.
- `x_reader.py`: `FakeXReader.ordinary` is a scripted test double.
- `attention_pc_refresh.py`: `XStream._next_due` applies the variation multiplier and the earliest B3 hold end. `vary_order` reorders only items that are equally due. `run_mixed` is called after each unit.

## 3. Interfaces for later slices
`XPool.b3_hold(label) -> (reason, end|None)|None`, `effective_cap`, `apply_cooldown(label, Cooldown|None)`, `note_result(label, day, count)`, `x_pool.run_mixed(pool, readers, src, config, *, units_since_last, stale) -> op|None`, and `XReader.ordinary(op, target, *, on_page)`. New fact kinds: `cooldown` (set/cleared), `mixed_call`, `unit_completed`, and `queryid_state` with `to_state=ordinary_op_stale`. S-Cookie-X and S-B3R read these.

## 4. Pool keys and defaults
No keys were added beyond S-B3P's seven. When every switch is off, nothing changes: no holds, the cap is the configured cap, there is no status `behaviour` block, no mixed calls are made, the page size is 20 with multiplier 1.0, and the order is unchanged.

## 5. Tests (red first)
Earlier workers ran the red tests (`test_x_b3_integration.py` failed on missing interfaces; recorded in the prior draft). After the guard update, the targeted runs pass:
- integration, twscrape_reader, proxy_snapshot, x_raw, x_pool and x_reader together: 292 passed, 1 skipped (POSIX mode bits).
- the three refresh files, x_behaviour, x_quiet, identity_transport, x_window and both guards: 288 passed, 2 failed. Both failures were in `test_x_reader_guards.py` (new lazy imports). The guard was updated with a function-scoped approval, and the rerun of the guards gave 32 passed.

## 6. Verification commands
From the repo root: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest <files above> -q -rs`.

## 7. Deviations and review blockers
These were authorized by the parent and are recorded here:
- `twscrape_reader.py` has a low-level single-page helper.
- The child and snapshot envelopes have an extra `count` field. Security re-read requested.
- `x_raw.py` stores the requested page size.
- `test_x_reader_guards.py` (S-B3I is in its chain, table H) now approves the `twscrape.api` and `twscrape.queue_client` imports only inside `ordinary/single_page`.
- Risk: `x_mixed_targets` is a flat list (schema owned by S-Config), so a numeric target may be a user id passed to `tweet_details`. That request is still one charged request, classified locally, and it causes no coin write.

## 8. Rollback
Revert this commit. Turning the switches off restores the baseline behaviour without a code revert. Archived records without `requested_page_size` reparse as before.

## 9. Risks
The pinned operation IDs will go stale when X changes them. A 404 suspends only that operation. No live evidence for quiet hours or warm-up (REF-X §4.3).

## 10. Owner actions
None for CODE-COMPLETE. LIVE-READY needs an owner-approved live run with the switches turned on.

## 11. Changed paths
api/data/attention/{twscrape_reader,x_pool,x_proxy_snapshot,x_raw,x_reader}.py, api/data/attention_pc_refresh.py, api/tests/data/attention/{test_twscrape_reader,test_x_proxy_snapshot,test_x_raw,test_x_b3_integration}.py, api/tests/tooling_guards/test_x_reader_guards.py, this report.
