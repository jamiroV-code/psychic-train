## 1 Task ID
B1 — transport identity and feasibility gate (PLAN `collector-identity-pool_02-11-26`, SPEC AC10, AC12, AC17-AC20). Branch `claude/identity-b1`.

## 2 Outcome
Implemented and green offline; draft PR open. No live comparison, no proxy, no request to X or Reddit. Defaults unchanged: `x_connection_style` plain, `x_identity_enabled` false.

## 3 Summary
- Optional settings `x_connection_style`, `x_identity_enabled`, `x_account_identities` in `web_queries.py` (not in required X_DEFAULTS; `attention_queries.json` untouched). Enabled identity requires an exact `impersonation_target` per label in both styles, plus a family-coherent literal `user_agent` in plain; unknown labels, invalid values and duplicate identities are rejected.
- `twscrape_reader.py`: selected backend is verified (platform, distribution, wheel tag, lock/hash, install record; no binary re-hash) before the library loads; selected curl that does not verify refuses startup; no curl-on-curl fallback; plain keeps one qualifying curl fallback per UTC day pool-wide. `IdentityAdapter` wraps the GraphQL client factory and the signature bootstrap, account carried by context-local state, bootstrap cache scoped by identity revision, compatibility assertions refuse startup if pinned hooks differ. Cookie refresh reconciles identity. The fallback child reconstructs the account's target (missing target refuses the fallback).
- `deploy/start-collector.ps1` passes the validated style as `TWS_HTTP_BACKEND` (parse-checked only, never run).
- Docs: canonical collector SPEC "Superseding decision 02-11-26" section (history kept; rules 5, 8, 17-20, AC41, AC46, AC53, AC55, Q24/Q30), identity SPEC/PLAN wording, `deploy/README.md`, reader module docstring.

## 4 Files changed
- api/data/attention/web_queries.py, twscrape_reader.py, x_reader.py
- api/tests/data/attention/test_identity_transport.py (new), test_twscrape_reader.py, test_web_queries.py
- api/tests/tooling_guards/test_x_reader_guards.py (deliberate: allow only the lazy adapter boundary and approved hooks; pins, debug, login, lock-reset, telemetry bans kept)
- test_twscrape_reader.py deliberate amendments: old per-account UA refusal replaced by narrow identity acceptance; the "curl_cffi not in sys.modules" assertion now compares before/after because other B1 tests load curl_cffi in the same process
- deploy/start-collector.ps1, deploy/README.md
- process/general-plans/active/collector-identity-pool_02-11-26/ (PLAN, SPEC, VALIDATE-B1, this report)
- process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-xreddit-collector_SPEC_21-10-26.md

## 5 Commits
Red tests first (78bbe803 … 34a5070e etc.), then implementation (9e9975a5, 3c9eaf56, eca6a3a6, 40bae23a), amendments and fixes (c5314989 … 33413488) and the final docs/report commit on `claude/identity-b1`.

## 6 Tests run
Windows host, UV_FROZEN=1, `uv run --project api --frozen --group xreader pytest api/tests/data/attention api/tests/tooling_guards api/tests/analytics/attention -q`: 1770 passed, 2 skipped, 1 failed. The failure is `test_universe_classes.py::test_discovery_end_to_end_on_fixture` (known Windows-host quirk, judged by Linux CI). Loopback wire proofs cover GraphQL and bootstrap paths, two accounts, both backends, restart, identity change, fresh regeneration, concurrent interleaving and the fallback child.

Per-target wire table (loopback, curl_cffi 0.16.3, supplied `accept-language: en-US,en;q=0.9`; plain-HTTP artefacts `Upgrade: h2c`, `HTTP2-Settings`, `Connection` omitted):

| target | User-Agent | client hints | Accept-Language | notable header order |
|---|---|---|---|---|
| chrome131 | Chrome/131.0.0.0, macOS | sec-ch-ua "Google Chrome";v=131, mobile ?0, platform "macOS" | kept (lowercase, after Accept-Encoding) | sec-ch-ua*, Upgrade-Insecure-Requests, User-Agent, Accept, Sec-Fetch-Site/Mode/User/Dest, Accept-Encoding (gzip, deflate, br, zstd), accept-language |
| safari170 | Version/17.0 Safari/605.1.15, macOS | none | kept | Accept, Sec-Fetch-Site, Accept-Encoding (gzip, deflate, br), Sec-Fetch-Mode, user-agent, accept-language, Sec-Fetch-Dest |
| firefox133 | Firefox/133.0, macOS 10.15 rv:133 | none | kept | User-Agent, Accept, accept-language, Accept-Encoding (gzip, deflate, br, zstd), Upgrade-Insecure-Requests, Sec-Fetch-*, Priority u=0 i, Te trailers |
| edge101 | Chrome/101.0.4951.64 Edg/101.0.1210.47, Windows | sec-ch-ua "Microsoft Edge";v=101, mobile ?0, platform "Windows" | kept | sec-ch-ua*, Upgrade-Insecure-Requests, User-Agent, Accept, Sec-Fetch-*, Accept-Encoding (gzip, deflate, br), accept-language |

Curl ignores a supplied User-Agent and sends the target's own; the identity UA under curl therefore derives from the target.

## 7 Tests NOT run
- TLS fingerprint (JA3/ClientHello) verification: NOT performed (no reviewed local capture parser; TLS match is only the library's claim).
- The separately approved live real-account comparison, proxies, B2/B3, Linux CI before the PR existed (see PR checks), the `deploy/start-collector.ps1` script itself (never run).

## 8 Deviations
- Fallback in plain style sends the target-derived UA, not necessarily the account's literal UA (documented bounded limitation).
- Canonical SPEC amended by an appended dated superseding section (history preserved), not by in-place rewrites.

## 9 Blockers
None for B1. Windows-only failure above is a known host quirk.

## 10 Follow-up
Owner-approved live comparison to choose the default style; B2 (proxies/admission) and B3 (behaviour measures); optional TLS capture.

## 11 Context cost
Resumed an existing worktree; read the plan block, tests and reader hooks selectively. Tools: git, uv, filesystem. No subagents.
