# S-XCookie report (07-11-26)

## 1. Status
CODE-COMPLETE. Stage 5, RT4. Branch `claude/b2-validate`. No push. Default off, no live requests, loopback fixtures only.

## 2. Scope
Plan section "S-XCookie: X hardening (c)": jar scoped to `.x.com`, a refreshed `ct0` replaces the old one (REF-X rec 8, upstream PR #363 semantics) on the identity adapter's curl and httpx paths and in `CurlRouteClient`; wire test with exactly one `ct0` per `Cookie` header equal to `x-csrf-token`, both backends, GraphQL and bootstrap, after a refresh; observe-only `ct0_rotations_seen`; AC19 identity wire retest in both backends.

## 3. Changed paths
- `api/data/attention/x_proxy_curl.py`: `X_COOKIE_DOMAIN`, `seed_cookies`, `scope_cookies`, `cookie_values`; `CurlRouteClient` seeds the jar at `.x.com` and collapses it after every response (snapshot taken before the request).
- `api/data/attention/twscrape_reader.py`: `IdentityAdapter.ct0_rotations_seen` (None until a response is observed with a `ct0`); `RoutedClient.request` keeps `x-csrf-token` equal to the jar `ct0` (only when the header is already present), collapses the jar after each successful response for both backends and counts rotations; httpx route/direct clients receive a `.x.com`-scoped `httpx.Cookies`.
- `api/tests/data/attention/test_identity_transport.py`: `test_refreshed_ct0_replaces_old_one_on_the_wire` (plain/curl x domain/host-only `Set-Cookie`).

## 4. Interfaces
- `x_proxy_curl.seed_cookies(jar, mapping) -> jar`, `scope_cookies(jar, previous) -> set[str]` (changed names), `cookie_values(jar) -> dict`. Usable by S-Cookie-X.
- `IdentityAdapter.ct0_rotations_seen: int | None` (observe-only).

## 5. Tests (red first)
- Red: new test, 4 failed (`AttributeError: ct0_rotations_seen`) before the change.
- Green: `-k ct0` 4 passed.
- AC19 retest: `test_identity_transport.py test_x_proxy_transport.py test_twscrape_reader.py test_x_proxy_spawn.py test_fixture_seams.py` 146 passed, 1 skipped (POSIX mode bits).
- `api/tests/tooling_guards` + `test_x_reader.py`: 214 passed.
Command: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest <files> -q -rs`.

## 6. Acceptance mapping
AC2 (partial, this slice's part: cookie jar correctness), AC19 (identity wire paths retested in both backends after the jar change).

## 7. Deviations
- `ct0_rotations_seen` lives on the in-process adapter only; it is not added to `reader_status`/health line, which is computed out of process from config and pool state and has no observation source yet (a constant `unknown` field would be dead weight). Persisting it belongs with facts/pool owners (S-Cookie-X / S-B3I) if wanted.
- "No automatic adoption" interpreted as: the rotated `ct0` replaces the old one inside the live client (and `x-csrf-token` follows it so the wire stays consistent), but is never written back to the stored account (test asserts `acc.cookies["ct0"] == "OLD"`).
- Red run failed on the new attribute first; the wire duplicate itself was established offline by REF-X rec 8 (not re-run against HEAD).

## 8. Risks
- Cookies set by non-X origins through `CurlRouteClient` are also rescoped to `.x.com`; the client is the X route client, so they could only ever be sent to X.
- Whether X really rotates `ct0` on GraphQL responses remains [LIVE] (REF-X §3.2).

## 9. Rollback
Revert this slice's commit; no data, config or schema change.

## 10. Live gates
None touched. Live-ready questions for `ct0` rotation stay open (REF-X open question 5).

## 11. Next
S-B3I and S-Cookie-X continue the `twscrape_reader.py` chain; S-Cookie-X may reuse `seed_cookies`/`scope_cookies`.
