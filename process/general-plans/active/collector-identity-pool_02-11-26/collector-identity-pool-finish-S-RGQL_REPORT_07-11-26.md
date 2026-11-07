# S-RGQL slice report: anonymous GraphQL secondary (07-11-26)

## 1. Status
CODE-COMPLETE on fixtures. Not LIVE-READY. LIVE-READY needs four things: owner acknowledgement of the B7 amendment (§9), a published `gql_anon` section, an owner-approved PR1 verify pass, and an admitted route. Default off: nothing runs unless `gql_anon` is in `reddit_live_methods`. No live requests were sent; the in-process fake was the only transport. Branch `claude/b2-validate`, committed locally, not pushed.

## 2. Scope
Plan §S-RGQL, contract B7 and RC-9 supply:
- the `LiveMethod` (`make_method`)
- the request grammar
- token renewal (≤ 2 per day)
- the persisted daily cap
- `ops_stale` on a rejected hash
- the PR1 executor, registered through `probe_owner.register`
- Stage 0 shapes REF and the fake
- the reddit guard chain link

## 3. Changed paths
- `api/data/attention/reddit_gql.py` (new)
- `api/scripts/probe_gql.py` (new; the PR1 executor and its production dependencies)
- `api/scripts/probe_executors.py`: a PR1 branch in `build_dependencies`, a registration import and a docstring change
- `api/data/attention/reddit_surface.py`: optional raw `requests` key, `gql_anon` only (approved deviation, §9)
- `api/tests/data/attention/reddit_gql_fake.py` (new), `api/tests/data/attention/test_reddit_gql.py` (new), `api/tests/scripts/test_probe_gql.py` (new)
- `api/tests/scripts/test_probe_executors.py` (PR1 is no longer pending), `api/tests/data/attention/test_reddit_surface.py` (+1 test), `api/tests/tooling_guards/test_reddit_collector_guards.py` (narrow `asyncio` exemption for `reddit_gql.py` and a planted-negative test)
- `collector-identity-pool-gql-shapes_REF_07-11-26.md` (Stage 0) and this report

## 4. Work completed
**B7 grammar** (`load_requests`). This is a closed schema for `client_id`, `token` and `operations.{posts,comments}`.
- Placeholders sit only at their allowed positions: whole-string variables, path segments and query values.
- `{token}` appears only as the exact operation header `Authorization: Bearer {token}`.
- Credential-named headers and transport headers are refused. A template `Authorization` on the token request is refused.
- Each operation must `match_request` an endpoint of its lane. Responses are read through the B1 engine (`extract_page`).

**Mint.** Code builds `Authorization: Basic base64(client_id:)` from the hash-bound section field. The bearer token is held in memory only, and the client and method reprs hide it.

**Method.**
- The gate checks, in order: the switch, the surface and B7, `probe_owner.verify_gate` (fresh, pass, hash and revision), `ops_stale` and the transport.
- Posts lanes page `new` down to the floor and carry a cursor chain. Comment lanes cover only the threads opened; failed threads go into a separate lane with their stop reason.
- Before each send the method charges a persisted `_gql_state.json` (`day, requests, mints, ops_stale`). This works together with the core counters. The file never holds the token.
- On a rejected hash the poll stops after a single request and the gate stays `needs_probe` until the section hash changes. A 403 block page or a cap stops the poll. An empty shell or a mismatch fails only its lane. A 401 gets one renewal per request, never a loop.
- **Production transport** comes from `route_transport`. It uses the B2 hardened clients (`x_proxy_transport.direct_client`, or `client(route, policy narrowed to the section hosts)`):
  - with a route provider in `deps.routes`, its answer for `("reddit","gql_anon")` decides;
  - without one, `direct` is allowed only when no X proxy is configured (the PX1 rule);
  - otherwise there is no transport and the gate is `method_unavailable`.

**PR1 executor.**
- Steps: mint, `new` feed to the start of the previous UTC day, `PostComments` of the busiest thread (≤ 3 pages). Each request is charged before it is sent, within the 120 budget.
- `bootstrap` runs on the draft section; `verify` runs on the published section, which `run()` binds.
- Reason codes are allowlisted only.

## 5. Interfaces
- `reddit_gql.make_method(config, deps)`. Optional deps: `gql_transport`, `routes`, `proxy_policy`, `hasher`, `queries`, `clock`.
- `GqlClient(section, requests, transport, charge=, may_mint=, clock=)`; `Transport(method, url, headers, body) -> Response(status, content_type, body)`.
- `route_transport(config, routes=, policy=, hosts=)`.
- `probe_gql.pr1_gql_anon` and `probe_gql.build_dependencies(config)`.

## 6. Tests run
Command: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest <files> -q -rs`
- Red first:
  - the surface test failed 1 of 1 (`SurfaceInvalid: section`);
  - with `reddit_gql.py` held aside and `probe_gql.py` not yet written: 2 collection errors;
  - `test_probe_executors` + guard: 1 failed (`'PR1' in EXECUTORS`), 23 passed.
- Green, run as one pytest invocation over 9 files: `test_reddit_gql.py`, `test_probe_gql.py`, `test_probe_executors.py`, `test_probe_owner.py`, `test_reddit_collector_guards.py`, `test_reddit_surface.py`, `test_reddit_core.py`, `test_reddit_live.py`, `test_surface_tool.py` → **218 passed**, 0 skipped.

## 7. Data verification
Only synthetic fixtures (the in-process fake shaped after Redlib) and `httpx.MockTransport`. One test scans every cache file and the logs for planted usernames and text, the bearer token, the client id, `Basic ` and `Bearer `. The scan excludes the owner's surface file, which legitimately holds the public client id and the `Bearer {token}` template.

## 8. Error handling
Every failure is a lane stop reason (`cap|error|schema_mismatch|unsupported_format|empty_shell`) or an allowlisted probe reason code (`budget_exhausted|transport_failed|rate_limited|blocked|schema_mismatch|unsupported_format|empty_shell|queryid_changed`). Transport errors keep their class only. There is no logging.

## 9. Deviations
1. **Approved by Main:** `reddit_surface.load_section` now accepts an optional raw `requests` key, in `gql_anon` only. It is carried on `Section.requests` and is part of the whole-section hash, so the B7 templates are hash-bound together with the hosts.
2. **B7 plan amendment, approved by Main, owner acknowledgement needed:** the token mint is a code-owned step. Code builds `Authorization: Basic base64(<client_id>:)` from a pattern-validated public `client_id` held in the hashed section. Templates still cannot carry any credential header. Without this amendment the real mint, which needs Basic auth according to Redlib `oauth.rs`, was impossible under B7. **This gates LIVE-READY only.**
3. **Interpretation:** without a route provider, production allows `direct` only when no X proxy is configured (the same rule as PX1). With proxies configured, or with a provider that refuses, the gate is `method_unavailable`. The worker's `deps` (S-RCore-B) pass only `clock`/`sleep`. Wiring `routes`/`proxy_policy` for Reddit is S-RBrowser's route adapter.
4. **Interpretation:** a rejected persisted hash is detected as GraphQL `errors` that name `PersistedQueryNotFound`. This is the Apollo convention and has not been observed on Reddit. The method records `ops_stale` and the gate reports `needs_probe`, because `ops_stale` is not a GateState.
5. **Ownership:** `probe_executors.py` and its test belong to S-OpsProbe. They were edited only for the PR1 registration, which the envelope assigns to this slice.

## 10. Review decision needed
- The owner should acknowledge the B7 amendment in item 2 of §9.
- After PR1 bootstrap, check the grammar fit of the REF assumptions: the subreddit on the comment node, the comment cursor placement, and full-text proof of `content.markdown`. A misfit goes to "extend parser" (already authorized).

## 11. Handoff
- **S-RBrowser:** supply a Reddit `RouteProvider` (`admitted_route("reddit","gql_anon")`) and `proxy_policy` through `attention_pc_live.deps`, or accept the direct-only default.
- **S-OpsDoctor:** read `_gql_state.json` (`ops_stale`, mints) for its checks.
- **S-OpsDeploy runbook fragment:**
  - write the `gql_anon` section with `requests`, run `surface_tool --approve-surface gql_anon`, then `probe_owner PR1 --mode verify --approve <digest>`, then add `gql_anon` to `reddit_live_methods`;
  - rollback: remove `gql_anon` from `reddit_live_methods` and delete `<cache>/attention/reddit_live_gql/_meta/_gql_state.json`.
- **Main:** rerun the 9 files listed in §6.
