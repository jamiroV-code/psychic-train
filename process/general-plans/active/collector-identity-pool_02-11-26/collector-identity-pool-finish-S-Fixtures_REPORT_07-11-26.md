# S-Fixtures slice report (07-11-26)

## 1. Status
CODE-COMPLETE (test-only slice; no live gate). Branch `claude/b2-validate`, Stage 2.

## 2. Scope
Plan §S-Fixtures: shared test seams, envelope-v2 `query_id` fixture support, fake-X Cookie/duplicate-`ct0` helper, synthetic host/SAN set, spawned-process network denial, OpenSSL preflight.

## 3. Changed paths
- `api/tests/data/attention/fixture_seams.py` (new)
- `api/tests/data/attention/test_fixture_seams.py` (new, this slice's tests)
- `api/tests/data/attention/proxy_wire_fixture.py`
- `api/tests/data/attention/proxy_child_fixture.py`

## 4. What was built
- `PERMITTED_SEAMS` (temporary paths, clock/wait, memory/RSS and ACL inspectors, spawn launcher, resolver answer source, relay dialer, synthetic trust roots, transaction-ID parser), `FORBIDDEN_REPLACEMENTS` (run_unit, search_raw dispatch, pool selection, reader bootstrap request, relay policy, browser_host, CDP client, browser_selftest), `require_permitted`.
- A6b: `synthetic_resolver` (fixture answer source; answer validated by the REAL `x_proxy.public_address`), `FixtureDialer` (exact token `93.184.216.34` → loopback listener only; records dials).
- `FakeClock`, `ScriptedInspector`, `spawn_launcher`, `loopback_resolution`.
- `install_network_denial` (audit hook: non-loopback getaddrinfo/connect/sendto → `NetworkDenied`); installed first by `proxy_child_fixture.main`.
- `openssl_binary` preflight (Git-for-Windows fallback; missing FAILS); `proxy_wire_fixture.certificates` uses it.
- HOSTS/origin SANs gain `x.com`, `abs.twimg.com` (static asset origin), `www.reddit.com` (also the `.rss` feed origin), `gql-fed.reddit.com`. Origin records every `Cookie` header (`get_all`) per request.
- `proxy_child_fixture`: `expected_query_id` (envelope-v2 grammar `[A-Za-z0-9_-]{16,32}` or null); the stubbed search asserts `twscrape.api.OP_SearchTimeline` uses it when given. `FakeXCookies` + `ct0_count` report requests with duplicate `ct0`.

## 5. Qualifications
- PARSER_QUALIFICATION: with the deterministic parser substituted, runs exercise the real bootstrap REQUEST path, NOT the real transaction-ID parser.
- NATIVE_CONTAINMENT_GAP (BP13 INCONCLUSIVE): Python-level guard only; native curl/Chromium sockets and grandchildren are not covered; never called a sandbox.

## 6. Tests run
`UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_fixture_seams.py api/tests/data/attention/test_x_proxy_spawn.py api/tests/data/attention/test_x_proxy_transport.py -q -rs` → 78 passed, 0 skipped (172.97s). Spawn/transport suites confirm the denial guard and extended SANs do not break B2 routed/direct children.

## 7. Data verification
No data files written; temporary certificates live in `TemporaryDirectory` only. Spawned denial check output: `denied,denied,loopback`.

## 8. Error handling
Unlisted/forbidden seam, unmapped dial, non-fixture host, private/loopback/link-local/multicast answer (`ProxyFailure`), exhausted inspector, negative wait, bad `query_id`, missing OpenSSL: each raises; tested.

## 9. Deviations
None from plan scope. Tests were written before the module but the red run was not executed separately (first run was green after implementation). Relay `Dialer` interface is a sync `dial(host, port, *, timeout)`; S-Relay may request changes from S-Fixtures.

## 10. Gate honesty
No probe gate on this slice; BP13 INCONCLUSIVE recorded as the native-containment gap above.

## 11. Next
S-XProto consumes `expected_query_id`; S-XCookie consumes `FakeXCookies`; S-BrowserHost/S-Relay consume launcher, inspectors, resolver and dialer.
