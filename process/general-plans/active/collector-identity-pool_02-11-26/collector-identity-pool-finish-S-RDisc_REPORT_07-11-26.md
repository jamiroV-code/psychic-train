# S-RDisc slice report: Discovery wiring (07-11-26)

## 1. Status
CODE-COMPLETE. Targeted tests: 463 passed. No live requests; LIVE-READY is not established by this slice. No push or PR (task envelope forbids pushing).

## 2. Scope delivered
Contract C1/C2/C4/C5/C6: committed Discovery and collector orders are live browser, live GraphQL, web feed, stream. Discovery still chooses one usable method for the entire window, without score changes. History admits the two live PC stores without probe records and uses registry's exact known-at-time filtering. Legacy feed and non-Reddit history admission remains unchanged. Evidence sidecars participate in history cache invalidation. Method changes are available as a read-only diagnostic.

## 3. Changed paths
- api/data/discovery.json
- api/data/attention_queries.json (reddit_impl_order only)
- api/analytics/attention/discovery.py
- api/analytics/attention/discovery_history.py
- api/tests/analytics/attention/test_discovery_wiring.py
- api/tests/analytics/attention/test_discovery_reddit_cutover.py (new)
- api/tests/data/test_attention_pc_refresh_stream.py (single equality test)
- api/tests/data/attention/test_web_queries.py (two committed-order assertions)
- api/tests/data/attention/test_reddit_stream.py (single committed-order assertion)
- This report.

## 4. Interfaces for later slices
- `discovery.pick_source_impl(src, cfg, data, symbol, end, recent, window, max_lag) -> tuple[str, DiscoverySource] | None`: the exact selection used by weighted scoring, returns chosen store and score contribution; no mixing.
- `discovery_history.method_switches(symbol: str, window: int, *, today: date, source: str = "reddit", probe_path: Path | None = None, config_path: Path | None = None) -> list[tuple[str, str | None, str | None]]`: entries are `(ISO day, previous method, method from that day)`. None denotes no usable method. Reports changes between successive chart days, not the initial method. Read-only; no payload/model change. S-StatusUI/S-Report may consume this diagnostic.
- History uses `registry._known_at_time`, thereby sharing `known_lag_days` and backfilled exclusion exactly; live store names derive from `reddit_core.STORES` intersected with `registry.PC_STORES`.

## 5. Tests run (targeted only)
Command prefix: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest`; suffix: `-q -rs`.
- Red: `api/tests/analytics/attention/test_discovery_reddit_cutover.py api/tests/analytics/attention/test_discovery_wiring.py api/tests/data/test_attention_pc_refresh_stream.py api/tests/data/attention/test_web_queries.py api/tests/data/attention/test_reddit_stream.py` -> 6 failed, 408 passed (326.12 seconds). Observed failures include missing method_switches and old shipped order.
- Green: same files plus `api/tests/analytics/attention/test_discovery_history.py api/tests/analytics/attention/test_discovery_history_pit.py` -> 463 passed (382.42 seconds).
- Order assertions remain exact tuple equality against all four names, so removal, reordering, or an old feed-only order fails rather than passing vacuously. The stream selection test retains its method and point assertions.

## 6. Acceptance mapping
- C1/C5: real build_discovery tests cover browser preference, GraphQL fallback, feed fallback without live points, insufficient live history without splicing, known-at-time fallback.
- C2/C4: real coin_history tests cover probe-free live admission, unchanged legacy feed gate, late/backfilled point removal, and sidecar-only cache invalidation.
- C5: diagnostic test observes GraphQL-to-browser switch on the exact history eligibility day and no X switch.
- AC18: existing order equality preserved, X assertions unchanged, legacy history and PIT regression tests pass.

## 7. Deviations
Main approved via IRC: C5 flagging is the read-only method_switches diagnostic rather than a model/payload change; exact signature and shape above. Main also approved updating the second committed-order assertion in test_web_queries and the committed-order assertion in test_reddit_stream outside the originally enumerated table-H edit. Neither weakens coverage.

## 8. Red-first note
New tests and order assertion amendments were written before implementation. The red run was launched before implementation and completed with six failures. Implementation edits began while that run was still running, so it was not a frozen pre-implementation snapshot; the observed old-order and missing-diagnostic failures are genuine, but not every amended assertion was independently observed failing.

## 9. Privacy / safety
Synthetic local stores only. No new collector activation, live requests, accounts, credentials, provider actions, dependency edits, or .github changes. Default-off collection switches untouched.

## 10. Risks / open items
Method-switch diagnostics are not automatically included in public history payloads (approved by Main); callers must request them separately. History intentionally retains old feed admission behavior per C2. No unrelated plan/probe files were staged. No LIVE-READY claim.

## 11. Next checks for Main
Review the approved diagnostic interface for downstream consumers. Targeted tests above passed; no full suite was run. Review/commit integration can proceed without any live gate. Rollback before S-RDisc restores both literal orders to ["reddit_web", "reddit_stream"] as contract G specifies.
