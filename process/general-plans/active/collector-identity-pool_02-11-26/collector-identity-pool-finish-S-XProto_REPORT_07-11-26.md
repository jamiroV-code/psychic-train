# S-XProto EXECUTE report — 07-11-26

## 1. Status
CODE-COMPLETE for S-XProto. Default off; no live X, Reddit or provider requests. LIVE-READY is not claimed. Worktree `wt-b2-validate`, branch `claude/b2-validate`; no push or PR action (task-envelope instruction).

## 2. Scope
Finished-product PLAN §S-XProto XP-1/XP-2/XP-3, shared contract E, ownership chains and rollback G. Static discovery constants were checked against REF-X §2.4 and its cited source URL, offline only. The existing feasibility probe establishes the module-level SearchTimeline hook. Config and fixture interfaces were consumed, not changed.

## 3. Changed paths
- `api/data/attention/x_queryids.py` (new)
- `api/data/attention/x_queryids_fetch.py` (new)
- `api/data/attention/x_proxy_snapshot.py`
- `api/data/attention/x_proxy_child.py`
- `api/data/attention/twscrape_reader.py`
- `api/data/attention/x_proxy_runtime.py` (approved narrow ownership exception)
- `api/tests/data/attention/test_x_queryids.py` (new)
- `api/tests/data/attention/test_x_queryids_fetch.py` (new)
- `api/tests/data/attention/test_x_proxy_snapshot.py`
- `api/tests/data/attention/test_twscrape_reader.py`
- `api/tests/data/attention/test_x_proxy_spawn.py` (approved narrow ownership exception)
- `api/tests/tooling_guards/test_pc_collector_guards.py`
- `api/tests/tooling_guards/test_x_reader_guards.py`
- This report.

## 4. Implementation
XP-1: pure pinned table for SearchTimeline, UserTweets, TweetDetail and UserByScreenName; bounded strict JSON reads, exact schema validation, atomic single-writer persistence, 32 bounded evidence records. Bundle-active SearchTimeline without matching passed parseable evidence falls back to the pin. Ordinary operations never adopt. Same-user evidence forgery is explicitly outside this validation boundary. Duplicate/conflicting operation mappings or repeated IDs reject the candidate set; only literal queryId/operationName pairs are parsed, never executed. Static bundle URLs are reconstructed from a validated hash and fixed origin/path.

XP-2: `run_check` is synchronous and single-writer. Off returns before reading or writing state. Sentinel/auto run a two-GET check only with sufficient remaining daily budget (default 6); each GET is persisted before network execution. A configured proxy without admission cannot fall back to direct; missing static origins produce `refused_by_policy`. Network failures are `blocked`, malformed discovery/bundle is `unknown`. No raw body, route or credential is persisted. The B2 one-shot client supplies the 10-second total timeout, bounded streaming/cleanup, no redirects/retry, and a 4 MiB limit; the sentinel supplies the honest user agent and no cookies/account.

XP-3: v2 HMAC domain, mandatory `query_id` exact key, null/present framing immediately after the cursor frame, ASCII ID grammar. The direct builder/validator and routed preparation ship together. The fallback captures the already-loaded current operation at its boundary and the child binds it before constructing its reader. Missing field/v1 tags, malformed values and tampering are refused. The direct/off policy predicate is preserved.

## 5. Qualifications
The sentinel is intentionally standalone until S-XDrift's unit-boundary wiring; Main explicitly confirmed this ownership boundary by IRC. No runtime scheduling/candidate evaluation was added to sibling-owned pool or worker files. No new dependency, .github change, login, credentials, live traffic or gateway work. Windows POSIX-mode skip is inherited. Static URL availability today was not live-probed under this task's no-live rule.

## 6. Tests and evidence
Tests were written and actually run red before implementation:
- `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_queryids.py api/tests/data/attention/test_x_queryids_fetch.py -q -rs`: **2 collection errors**, missing new modules.
- Same command with `test_x_proxy_snapshot.py test_twscrape_reader.py`: **14 failed, 81 passed, 1 skipped**; failures demonstrate absent v2 framing/domain/validation/binding.

Green targeted run:
- `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_queryids.py api/tests/data/attention/test_x_queryids_fetch.py api/tests/data/attention/test_x_proxy_snapshot.py api/tests/data/attention/test_twscrape_reader.py api/tests/data/attention/test_x_proxy_spawn.py api/tests/data/attention/test_identity_transport.py api/tests/tooling_guards/test_pc_collector_guards.py api/tests/tooling_guards/test_x_reader_guards.py -q -rs`: **186 passed, 1 skipped, 3 warnings**, 98.46 seconds. Spawn tests exercise real child HMAC, routed factories, direct/off predicate, direct plain-to-curl composition and credential/output marker assertions. Identity transport tests cover both plain and curl. Skip: POSIX mode bits on Windows. Warnings: curl_cffi adds a selector thread to the Windows Proactor event loop.
- After adding five additional off-state/one-shot failure cases: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_queryids_fetch.py api/tests/data/attention/test_x_proxy_runtime.py -q -rs`: **25 passed**, 1.38 seconds.
No full suite, lint, formatter, build or live smoke test run.

## 7. Interfaces and on-disk layout
`x_queryids.state_path(cache_root)` = `<cache>/attention/_pc_state/x_queryids.json`.

Top-level exact keys: `version:1`, `check_state`, `last_check`, `bundle_sha256`, `budget:{day,used}`, `operations`, `evidence`.
- Every operation has `active:{id,source,adopted_at,evidence_id}`, `candidate:null|{id,seen_at,rejected_until,reason}`, `observed:null|{id,seen_at}`.
- `source` is pinned/bundle; timestamps are UTC ISO strings or nullable where initial/unknown. Initial pinned adopted_at is null, so status age is honestly unknown.
- Candidate reason: null, evaluation_failed, inconclusive. Only SearchTimeline can carry a candidate.
- Evidence exact keys: `evidence_id`, `operation`, `candidate_id`, `account_label`, `evaluated_at`, `result` (passed/failed/inconclusive), `entries`, `parse_ok`; evidence IDs are unique `[A-Za-z0-9_-]{1,64}`. S-XDrift must preserve the evidence referenced by active when bounding the list.
- `load(path)`, `validate(value)`, `save(path,state)`, `active_id(state,operation='SearchTimeline')`, `apply_check(state,now,...)` are available. State mutation/evaluation aggregation/adoption belongs to S-XDrift, with `save` validating before persistence.
- `x_queryids_fetch.run_check(config, *, cache_root, now, route=None, policy=None, get=static_get)` is called after next-account selection/admission at a synchronous unit boundary. `route` and `policy` must be that selected account's admitted pair, not arbitrary configuration. Static fetch receives no account. Missing admission makes no request.
- `x_proxy_runtime.one_shot(route,policy,url,limit,*,headers=None)`: explicit `(None,None)` direct route; partial pair refused. Existing routed defaults retained.
- `x_proxy_child.prepare(..., *, query_id=None)` and `fallback_request(..., cursor=..., query_id=None)` always emit the new key. Reader's `current_query_id()`/`bind_query_id()` capture and apply the existing library hook.

StatusAPI section 7 compatibility: **no mismatch**. Required `check_state`, `last_check`, `operations[op].active.{id,source,adopted_at}` are present; additional fields carry registry/budget/evidence data and are ignored by its reader.

## 8. Failure and disclosure behavior
Malformed/untrusted state resets to pinned; missing passed adoption evidence resets the active ID. Unknown/blocked checks retain prior candidate/observation data but never claim a fresh ok/stale result. Fetch failures retain the already-charged budget. No raw JS, HTTP diagnostics, credentials, cookies, route authentication, HMAC key/tag or body is written to state or exposed in child output. Guard additions keep registry pure and network imports lazy, restricting the sentinel to the B2 one-shot boundary.

## 9. Approved deviations
Main approved by IRC:
1. Mechanical v2 amendments to three hand-built requests in `test_x_proxy_spawn.py`, plus one real-query-ID spawned binding assertion.
2. Narrow `x_proxy_runtime.one_shot` extension for optional headers and explicit direct path, rather than duplicating B2 streaming.
3. S-XDrift owns selection/unit-boundary invocation; S-XProto remains standalone/inert until that stage.
S-RAcct-B must rebase its later runtime/spawn chain on these amendments. No other outside-ownership files changed.

## 10. Rollback and operator documentation fragment
Keep parent and child protocol versions together: v1 work is deliberately refused by v2. To disable optional sentinel behavior set `x_queryid_mode=off`; it makes zero fetches and does not touch registry state. Before rolling back to a pre-Stage-3 checkpoint, follow PLAN G for `x_queryids.json` and introduced config keys; never run mismatched parent/child versions. Sentinel/auto requires policy permission for both `https://x.com` and `https://abs.twimg.com` on the selected admitted route. An unknown/blocked/refused result is not evidence of endpoint health or drift. Auto adoption still requires S-XDrift's forced account evaluation.

## 11. Next ownership handoff
S-XDrift consumes the registry and wires `run_check` after account selection/admission, performs forced candidate evaluation and evidence-backed adoption, and binds the resulting ID before each ordinary unit. S-RAcct-B rebases the child/snapshot/runtime/spawn chain. Main owns broader integration verification. No push or merge performed.
