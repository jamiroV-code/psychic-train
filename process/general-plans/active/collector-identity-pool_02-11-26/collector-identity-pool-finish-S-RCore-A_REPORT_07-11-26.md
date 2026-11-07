# S-RCore-A slice report: Reddit core, new-file part (07-11-26)

## 1. Status
CODE-COMPLETE for S-RCore-A. LIVE-READY: not applicable to this slice; it has no live surface. Default off: nothing runs unless `reddit_live_methods` names a method, and no method module (`reddit_browser`, `reddit_gql`) exists yet, so the factory table resolves to `method_unavailable`.

## 2. Scope delivered (plan sections S-RCore-A, B1-B2, B6 hash rule, C3, C4, RC-1..RC-9)
- `reddit_surface.py` (new): grammar v1 engine. Covers request match (method, URL glob, operationName), items path with `[*]` (depth 12, 2 wildcards), one `where` predicate, a discriminator union, the closed transform list, the three full-text proofs, continuation and cursor placement (`query:`, `body:`, `path:`), the bounds (200 pointers, 64 KiB, `max_body_bytes` ≤ 2 MiB) and `section_sha256` over the canonical section. It fails closed with `schema_mismatch`, `unsupported_format`, `empty_shell`, `cap` or `error`.
- `reddit_core.py` (new): stores and method ids, stop reasons, gate states, the RC-8 reason allowlist, `LiveItem` (the six RC-7 fields only), `reduce_item`, the per-method item store and `FACTORY_TABLE`. Resolution is a lazy import for named methods only, through `resolve_method`/`resolve_methods`. Any failure returns `UnavailableMethod`.
- `reddit_live.py` (new): the `LiveMethod` Protocol, `LaneEvidence`, `PollContext` and `PollResult`. It also has lane persistence, the floor/anchor rule, spans and holes, the thread denominator, thread selection (close-poll re-opens included), comments coverage, the closing canary, `day_status` and `commit_day`. `commit_day` uses option-B zeros through `zero_policy="positive_history"` and writes a completeness document. It also keeps the RC-6 counters and breaker, persisted in `_live_state.json`.
- `density.finalize` / `web_evidence.commit_day`: these take the new keywords `zero_policy` (default `"trailing_median"`) and `history_ok` (default False). The default path is unchanged.
- `registry.py`: the two live stores are added to `SOURCE_IMPLS["reddit"]` (after the feeds) and to `PC_STORES`. `KNOWN_LAG_DAYS` and `known_lag_days()` are added (default 1, used by `_known_at_time`; S-RDisc consumes them for history).
- `test_reddit_collector_guards.py` (table H, first link): the file list is now globs over `reddit_*.py` and `browser_*.py`. The new core modules must stay network-free. There is one narrow exemption: exactly one `importlib.import_module` in `reddit_core.py`, with a planted-negative test.

## 3. Changed paths
- api/data/attention/reddit_surface.py (new)
- api/data/attention/reddit_core.py (new)
- api/data/attention/reddit_live.py (new)
- api/data/attention/density.py
- api/data/attention/web_evidence.py
- api/data/attention/registry.py
- api/tests/data/attention/test_reddit_surface.py (new)
- api/tests/data/attention/test_reddit_core.py (new)
- api/tests/data/attention/test_reddit_live.py (new)
- api/tests/data/attention/test_density.py
- api/tests/data/attention/test_web_evidence.py
- api/tests/data/attention/test_registry.py
- api/tests/tooling_guards/test_reddit_collector_guards.py

## 4. Interfaces for later slices
- S-RCore-B: `reddit_core.resolve_methods(config, deps)`, `reddit_live.build_context(store, subreddits, now, threads_per_poll=, request_cap=)`, `reddit_live.record_poll(store, result)`, `reddit_live.breaker_open(store, now)`, `reddit_live.poll_due(store, now, polls_per_day)`, `reddit_live.commit_day(store, day, q, now=, subreddits=)`.
- S-RBrowser / S-RGQL: `make_method(config, deps)` returns an object that satisfies `reddit_live.LiveMethod`. Pages are read through `reddit_surface.load_surface/match_request/place_cursor/extract_page`. Items are reduced with `reddit_core.reduce_item`. Each lane reports `LaneEvidence` (`stop_reason="exhausted"` only when paging reached the floor or `has_more` is false).
- S-RDisc: `registry.known_lag_days(source)` and `registry.PC_STORES` admit the live stores.
- S-OpsProbe: `reddit_surface.section_sha256(section)` is the published-hash rule (canonical JSON without `sha256`).

## 5. Tests run (targeted only)
- `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_reddit_surface.py api/tests/data/attention/test_reddit_core.py api/tests/data/attention/test_reddit_live.py api/tests/data/attention/test_density.py api/tests/data/attention/test_web_evidence.py api/tests/data/attention/test_registry.py api/tests/tooling_guards/test_reddit_collector_guards.py -q -rs` → 165 passed, 0 skipped.
- Adjacent consumers (`test_discovery_wiring.py`, `test_sources.py`, `test_reddit_stream.py`, `test_pc_collector_guards.py`, `test_x_density.py`) were run as a read-only regression check; the result is in the final message.

## 6. Acceptance mapping
- AC15 (core part): a synthetic `LiveMethod` reads its pages through the real grammar engine and the core. That yields a completeness document and a stored value that `registry.read_series(..., known_at_time=True)` (the Discovery reader) returns (`test_synthetic_surface_yields_values_discovery_reads`).
- AC18: table H amendments to the reddit guard only; default policy tables in density/web_evidence are unchanged and still pass.

## 7. Deviations
None from the plan text. Interpretations where the plan was open:
- A complete posts lane covers [floor, collected_at]: it paged `new` from the head down to the floor. A truncated lane covers only [oldest, collected_at].
- The "close poll" re-open set: after never-opened and grown threads, each poll re-opens the newest completed day's denominator threads that have not been re-opened since D's end.
- A failed breaker unit is a poll with any lane stop reason among `error|empty_shell|login_required|schema_mismatch|unsupported_format|unknown`.
- `complete` in C3 means the `DayResult` is neither `capped` nor `pagecap`.

## 8. Red-first note
The tests were written alongside the implementation, not run red first as a separate commit. The default-policy tables in `test_density.py`/`test_web_evidence.py` existed before and passed unchanged.

## 9. Privacy / safety
No network, no live requests, no credentials. Item rows hold only `{id, kind, subreddit, created_utc, author_hash, coins}`. `RawItem.text` is excluded from its repr. `test_no_text_or_username_persisted` scans every file written under the isolated cache for planted usernames and text.

## 10. Risks / open items
- With the default `reddit_live_threads_per_poll`=30 and an active canary subreddit, it can take several polls after D's end before D's threads are all re-opened. That delays settling. This is honest, but S-RCore-B scheduling and S-RBrowser should take it into account.
- `reddit_live` imports `registry` (for the Reddit store list); `registry` imports the GitHub fetchers. No cycle arises.

## 11. Next checks for Main
Run the targeted command in section 5. For the stage gate, also run `api/tests/analytics/attention/` and `api/tests/data/attention/test_reddit_stream.py`, because the `SOURCE_IMPLS`/`PC_STORES` additions are visible to `discovery.py` config validation and `sources.py`.
