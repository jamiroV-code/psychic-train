# Collector identity pool B2 — VALIDATE contract

Date: 03-11-26  
Scope: this worker corrects B2 documentation only; no production source or suites. User authorizes complete synthetic local implementation/build/testing; parent additionally authorizes final RT0 plan/diff and feasibility-artifact validation in this lane. No live X/Reddit/provider/proxy activity, purchases, deployment, commit/push/PR/merge.
Decision: independent local design disposition **CONDITIONAL**; implementation now complete and locally tested on synthetic fixtures. **Automated implementation acceptance PASSED with explicit caveats in §20**; **live-operation/release BLOCKED**. Earlier NOT RUN entries record pre-implementation snapshots; historical Review6 BLOCKED remains history, not rewritten as PASS. This documentation worker records parent-observed implementation results rather than rerunning suites.

## Post-merge dependency update

PR #240 is MERGED on `main` at `febe7f44cfdfc08965fca0a721a8cbc83bf22b5a`. Post-merge CI run [41692827246](https://github.com/jamiroV-code/psychic-train/actions/runs/41692827246) passed API pytest and web Vitest/TypeScript/island build. Parent reports successful local fast-forward to that revision with autostash reapplied, preserving existing document edits. Upstream dependency and local B1 incorporation are resolved; no B2 gate upgrade or test result is implied. OPEN/draft/unmerged statements below describe historical reviews only.

**Current classification supersedes historical mixed prerequisites.** Merged B1 baseline is `febe7f44cfdfc08965fca0a721a8cbc83bf22b5a`; local design disposition CONDITIONAL permitted full synthetic implementation, now complete with automated acceptance PASSED subject to §20 caveats. Real assignments/exits, live baseline URL/hash, provider terms and deployment service/ACL details remain release/runtime inputs. Local evidence is not all-suites-clean, full SPEC/live acceptance or deployment permission.

## 1. Executive finding

Historical finding: the earlier B2 draft lacked explicit dispatch, revision lifecycle, scheduling, security-boundary, admission ownership, consumer inventory and RT4 evidence requirements. Initial layers identified **0 FAIL / 5 CONCERN**; this is historical, not a current PASS. Reviews `B2FinalReview4`, `B2FinalReview5` and `B2FinalReview6` returned **BLOCKED**. Review6 found policy consistent but mixed local feasibility, owner configuration, dependency and release evidence into execution blockers. Current timing and authority are in §5; historical results are not erased or silently promoted.

## 2. Tested revision and evidence boundary

Independently reviewed plan: `process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md`, prior baseline `33c9a7b5b389675099297366377be1e724ec9b02` (#239). Reviews 4–6 returned BLOCKED before the current gate-classification correction. PR #240 was then OPEN/draft at `4f6eaf1b`; it is now merged and incorporated locally as recorded above. Historical review baseline remains unchanged. This worker exercises no code/test behavior; parent runs RT0 after document/probe integration. SPEC, B1, B3 and Part A are intentionally unchanged by this worker.

## 3. Layer 1 findings

Layer 1 found that the existing B2 design has useful foundations—explicit direct mode, immutable owner assignments, fail-closed admission intent, unit-boundary handoff, migrated state and public health fields—but its operational contract is incomplete in several connected areas. Existing source locations relevant to the gaps are `api/data/attention/x_reader.py`; `api/data/attention_pc_refresh.py:472-486,500-563`; `api/data/attention/x_pool.py:382-408`; and `api/data/attention_pc_refresh.py:335-367,457-469`. The original plan had no B2-specific V1–V8 gate; lines 274–285 are B1 validation only.

## 4. Layer 2 findings and concerns

Count: **0 FAIL / 5 CONCERN**.

1. **Dispatch and lifecycle:** no explicit safe typed proxy-failure code/child serialization consumers across normal units, canary, fallback child, charged page and replacement; incomplete per-unit assignment/config revision reconciliation, account-scoped eviction and changed-account canary behavior when identity is disabled.
2. **Scheduler and budgets:** day cap, pool pause and midnight priorities did not define quarantine/health wake precedence, combined capped/quarantined and pool-pause/quarantine behavior, or a separate bounded health-control budget.
3. **Security and admission contract:** missing explicit URL scheme and plaintext-credential policy; trust-root isolation from ambient CA variables in parent and child; per-hop origin/resolved-address restrictions; hard wire/decompressed/parser/child-protocol bounds; complete secret-marker coverage; exact admission-input and replacement ownership schemas.
4. **Consumer/public contract:** incomplete formatter/API/UI/CLI inventory, null omission, matching `xsearch` fixture, legacy-shape and secret-absence tests through the actual API→formatter→UI path and requested viewport widths.
5. **Risk and proof:** RT3 understated the secrets/schema/public-API/runtime risk (must be RT4); no B2-specific V1–V8 gates and sufficiently explicit execution/probe/evidence requirements. PR #240 status/dependency, two unrun feasibility signals, and limits of local TLS evidence also required precise wording.

No finding asserts an implemented B2 defect; these are plan-contract gaps, not B2 runtime test results.

## 5. Formal gate and decision rule

**Current independent local design/EXECUTE gate: CONDITIONAL.** `B2SecurityGate` re-disposition: Infra PASS / Security CONCERN, mandatory implementation acceptance and no unresolved local blocker. `B2CoverageGate` final re-disposition: Coverage PASS / Breaking-change PASS, no outstanding decisions in those dimensions. Both reviewers distinguish scoped mechanism feasibility from production acceptance and recommend full synthetic local work. The user already authorizes proceeding with that risk; earlier `B2FinalReview6` BLOCKED is preserved as historical, not silently relabeled PASS. Tests for unwritten code remain acceptance work after implementation.

| Layer 1 dimensions | Status |
|---|---|
| Infra fit | PASS |
| Test coverage | PASS |
| Breaking changes | PASS |
| Security surface | CONCERN — mandatory implementation constraints accepted for local work |

| Layer 2 sections | Status |
|---|---|
| B2 HTTPX destination-binding mechanism | VIABLE, mechanism scope |
| B2 curl destination-binding mechanism | VIABLE, mechanism scope |

**Local dimension totals: 0 FAIL / 1 CONCERN / 3 PASS → Net local gate CONDITIONAL.** No outstanding local design decision. Do not count mechanism VIABLE as completed V1–V8 automation or live release.

| Class | Obligations | Disposition / timing |
|---|---|---|
| Local design / implementation prerequisites | Merged B1 incorporated at `febe7f44cfdfc08965fca0a721a8cbc83bf22b5a`; private interfaces frozen, both backend mechanisms scoped VIABLE and independently dispositioned. Security instructions mandatory. | **CONDITIONAL — complete synthetic local implementation/build/testing authorized**. No unresolved local design blocker. |
| Automated implementation acceptance | Complete B2 implementation locally tested on synthetic fixtures; parent-observed backend, child, web and browser results in §20. | **PASSED with caveats**, not a clean-all-suites claim. One unrelated backend failure remains unwaived; both earlier browser failures and later passing invocation retained. |
| Live-operation / release | Real private proxy list/assignments and unique exits/regions; final deployment origin allowlist, baseline URL+hash, provider selection/terms/privacy and Spamhaus terms; service SID/private paths/host ACLs; separately authorized real route/provider evidence, RT4 evidence pack and manual acceptance. | **BLOCKED / not authorized**. Missing/invalid inputs refuse proxy-required operation; never direct fallback or healthy-by-default. |

Synthetic local endpoints, trust roots and ACL snapshots must be explicit test injections, not production exceptions. The local probe may use loopback only as a test harness; production private/loopback/link-local destination rejection remains required. Complete local automation does not imply release permission or complete SPEC acceptance.

The `vc-predict` STOP is recorded as a risk assessment and does not replace the BLOCKED gate.

## 6. V4 plan corrections required

The B2 plan now requires the following explicit corrections and evidence:

- Add `x_reader.py` typed failure and child serialization; enumerate all consumers. Proxy failures preserve spent charges, discard partial samples and cannot map to login/suspension/Cloudflare/day-pause.
- Reconcile assignment/config snapshot and revision before every unit, evict only changed-account identity/cache/readers, rerun that account's canary even if `x_identity_enabled=false`, and test same-label mid-pass file changes for stale-identity prevention.
- Define earliest quarantine/health wake and combined scheduler precedence while preserving caps; separate health-control and X-read budgets with a bounded control allowance.
- Specify secure schemes/credentials, isolated parent/child trust roots, redirect/address rejection and hard resource/protocol bounds. Retain numeric limits in §12; implement and test enforcement after implementation. The separate pre-implementation destination-binding mechanism probes are now resolved at scoped VIABLE with independent local disposition; production acceptance remains required.
- State exact ownership/schema for required feeds, cache/refresh/revision, baseline URL/digest/redirect, optional default-off reputation provider and spare/replacement activation. Fail closed for required missing/invalid inputs; never publish proxy URLs or credentials.
- Inventory API, formatter, UI and CLI; retain legacy shape, omit nulls, fix matching `xsearch` fixture, and test direct/unknown/healthy/quarantined/blocked states with missing-field and secret absence through actual API→formatter→UI at 375/768/1280.
- Set risk tier to RT4, introduce B2-specific V1–V8, require locked `xreader` group, actually run adapter transport/no-leak test, spawned child, all client paths/redirects, persistence/reload/rollback, seeded API-screen and Windows ACL host evidence. Include RT4 evidence pack, manual acceptance and probe boundary.
- Record #240 merged upstream and incorporated locally at `febe7f44cfdfc08965fca0a721a8cbc83bf22b5a`; preserve pre-merge reviews as history. Local TLS capture is not proxy/browser equivalence. Do not invent a B1 live-comparison prerequisite.
- Preserve both `VC-FEASIBILITY-PROBE-NEEDED` signals as unrun: live route/provider behavior (unauthorized/not run), and selected Windows ACL inspector on deployment host (cheap-local/not run). No probes were made during this documentation validation.

## 7. Scenario and prediction summary

Scenario review covered dispatch/error classification and charged-page behavior; identity revision/file mutation and canary/cache lifecycle; quarantine wake precedence under caps and pool pauses; proxy/admission trust, redirects, resolved destination and bounded inputs; secret exposure across parent/child and all output/error paths; owner-controlled assignments/replacements; migrations/rollback; API/formatter/UI/CLI compatibility; CI/local locked test coverage; RT4 pre-deploy evidence and manual gates. The scenario set is captured as implementation gates, not claimed as executed tests.

Prediction review returned **STOP for the current draft** because the plan did not sufficiently bound runtime, credential-leak, trust-root, scheduler-budget, consumer compatibility and deployment evidence risks. Following the corrections reduces ambiguity but does not prove implementation safety. Revalidation must verify the corrections and maintain the no-live-probe boundary; only later authorized execution and evidence can address runtime outcomes.

## 8. Unrun feasibility signals and probe boundary

- `VC-FEASIBILITY-PROBE-NEEDED` — route/provider endpoint behavior. `needs-live-provider`; not authorized and not run. Retain as an explicit pre-deploy/manual gate; no route quality or provider compatibility claim.
- `VC-FEASIBILITY-PROBE-NEEDED` — selected Windows ACL inspector against deployment host. `cheap-local`; not run. Retain as an explicit pre-deploy/manual gate; no Windows ACL behavior claim.

No live provider/proxy requests, X/Reddit requests, Windows ACL checks, deployment, restart, or network-backed test occurred or is authorized by this documentation pass. B1 live comparison is unperformed and is not an execution prerequisite unless B2 itself requires it; do not infer one.

## 9. E1–E8 EXECUTE instructions (user-authorized, subject to local design gate)

Merged B1 incorporation is complete. After independent local-design disposition, implement the complete B2 scope using explicit synthetic fixtures. E1–E7 and E8 automated evidence follow implementation; E8 live/host/manual evidence gates release separately. No circular requirement to pass implementation tests before writing code.

- **E1 — Inputs and ownership:** implement/validate the specified feed schemas/formats, fixed source/origin policy, cache/revision, baseline digest/redirect and owner-controlled assignments/replacements with synthetic inputs. Real values/credentials, terms and deployment identities are release/runtime inputs. Required invalid/missing runtime inputs fail closed.
- **E2 — Secure admission boundary:** implement sequential admission with approved proxy schemes, no credentials over plaintext, explicit parent+child trust roots, hostile ambient CA-variable tests, per-hop origin/resolved-address checks, destination rejection and justified hard resource/parser/protocol bounds. Test secret markers across every boundary.
- **E3 — Typed proxy failures:** implement safe code/child serialization and every named consumer in `x_reader.py`; assert charges remain, partial data is discarded and proxy failures do not become account lock/day-pause classifications.
- **E4 — Per-unit revision lifecycle:** reconcile before each unit; same-label file mutation in one pass; scope eviction to changed account; pending canary regardless of identity switch; prove no stale identity before subsequent storage.
- **E5 — Scheduling/accounting:** implement earliest health/quarantine wake and precedence for capped+quarantined and pool-pause+quarantine. Separate bounded health-control budget from X reads; retain all account/global/page caps.
- **E6 — State and ownership:** migration, persistence, reload and rollback; assignment ownership immutable; atomic owner-controlled spare/replacement activation; preserve Part A data and legacy behavior.
- **E7 — Consumer boundary:** null omission and legacy shape; safe CLI decision; actual API→formatter→screen seeded coverage at 375/768/1280 for direct/unknown/healthy/quarantined/blocked, missing fields and secret absence.
- **E8 — Acceptance then release:** after implementation run locked `xreader` and unskipped transport/no-leak, spawned child, every client path/redirect, state reload/rollback and seeded screen tests. Default CI excludes xreader; it is not coverage evidence. Require explicit locked-group evidence; persistent `.github/` edits need separate owner approval and are out of scope. Separately retain RT4/manual acceptance, deployment-host ACL and real route/provider probes as BLOCKED release gates; no live activity, merge or deploy under local authorization.

### Frozen local interfaces — coverage/breaking-change correction

Independent `B2CoverageGate` final re-disposition is **Coverage PASS / Breaking-change PASS**: integrated interfaces and command inventory resolve its prior concerns, including preserved bounded query/product/cursor child payload. No owner/release-only input blocks synthetic work. Independent revised Infra PASS and Security CONCERN support the CONDITIONAL local gate; the PLAN's frozen public contracts define:

- Optional `x_proxy_policy_path`: nonempty absolute path or null, default null, included in optional defaults/`CollectorConfig` validation/`as_dict()`. Required proxy mode needs list+assignment+policy, while explicit direct mode has all three null.
- Exact-key version-1 private policy `{version,allowed_origins,echo,baseline,metadata_provider,service_sid,cache_dir}`; duplicate-key rejection. Canonical HTTPS origin array excludes userinfo/query/fragment/non-root paths. Echo exact `{url,response_format:"json-ip"}` validates a bounded JSON object's string IP independently of ipapi; baseline exact `{url,sha256}`. Configured echo/baseline and fixed feed/selected provider endpoints require origin membership; fixed feed/provider URLs cannot be substituted. Selector null/`"ipapi"`; valid Windows service SID; absolute cache directory constrained within verified private policy-parent root. No arbitrary API/runtime URLs; values synthetic locally.
- Exact-key version-1 assignment `{version,lines,accounts}`, exact account entry `{proxy_id,expected_ip,region,timezone,accept_language}`; no duplicate keys, active IDs/exits or line numbers. Unassigned spare line entries allowed; account keys only configured labels. Owner atomic replacement at unit boundary, no automatic rotation.
- Region/provenance interpretation: B1 identity `region` is alpha-2 country; assignment `region` is country or country-subdivision. Required declared metadata must be valid/coherent with identity country, tzdb timezone and any explicit country in the primary language tag; absent/invalid/contradictory required declarations block. Echo verifies expected UNIQUE exit IP, not geographic location. Null metadata selector makes no provider call and uses **OWNER-DECLARED mapping for the verified expected exit**, not measured geolocation. Explicit ipapi selection requires matching country, subdivision if declared and timezone observations; unknown/mismatch/error blocks with no owner-declaration fallback. Never auto-select/make optional provider mandatory; no new public field or change to outgoing-header provenance.
- V2 synthetic acceptance distinguishes the branches: null selector validates declarations/unique echo with zero provider calls and honest owner provenance; selected ipapi requires observations and fails closed on missing/mismatched/error metadata. Existing budgets, all gates, fixed endpoints and live-evidence limitations remain unchanged.
- Per fixed-source raw validated bounded cache body plus `{retrieved_at,source_version,sha256}`, source version from parsed header/timestamp tuple. Atomic revision publication; reload reparses body/hash/freshness/counts and reconstructs membership. Metadata alone cannot establish membership; retain all existing response/parser/line/count ceilings.
- For configured routing, explicit absolute private owner-query config path is selected by launcher/config argument. Exact routing/config/identity fields: `config_path`, configured validated label, canonical UUID `proxy_id`, opaque UUID4 `identity_revision`, allowlisted `backend` (fallback `"curl"`), and the security-approved transient attestation exception below. Preserve existing bounded query/product/cursor continuation work (product `"Latest"`; query/cursor <=4096 UTF-8 bytes), derive/validate DB from trusted config/root+label, and never send raw proxy URLs/credentials/provider secrets. Configured child revalidates snapshot and fresh admission before clients, never provider calls; both factories/bootstrap remain route/revision-bound with identity disabled. The direct/off exception below is narrow, not a failure fallback for configured routing.
- Security-approved child snapshot equality exception supersedes earlier “only path/label/ID/revision”: fresh per-invocation CSPRNG32-byte `attestation_key` and independent random32-byte `request_nonce`, strict 64-lowercase-hex key/nonce/HMAC-SHA256 `attestation_tag`, plus canonical UTC `admission_expires_at` equal to validated admission JSON expiry. Domain `collector-b2-child-v1`+NUL; every frame is 8-byte unsigned-big-endian length then bytes. Exact role tokens/order: `query-config`, `policy`, `assignments`, `list`, `safe-admission`; EACH role is framed role name, THEN framed canonical resolved absolute path, THEN framed exact raw bytes. Follow with fixed-order label/proxyID/UUIDrevision/`backend`/nonce/expiry/exact UTF-8 query/product/null-or-present cursor. `backend` is one exact protocol field, not a separate style field; config already authenticates style. Total private stdin <=16 MiB. No credential-derived digest persists; public revisions stay opaque UUIDs. Key/tag are sensitive verifier material whose joint leak enables offline low-entropy credential guessing after expiry—not harmless random fields.
- Read discovery bytes only bounded/side-effect-free, then owner/ACL-verify actual handles and process/service SID, re-read the same verified handles into immutable snapshot bytes, compare in constant time before any library/client construction and parse/use only those attested bytes. Label passes `LABEL_RE`+configured membership before paths; DB/root/label and admission path are derived and contained with handle checks, no symlink/reparse ambiguity. Check same-revision fresh admission/feed revisions; mismatch safe `proxy_revision`, no direct/provider fallback.
- Only private bounded stdin may carry transient key/tag; never persist or expose in env/argv/logs/reports/errors/exception causes/stdout/stderr/captured diagnostics/response. Reply echoes `request_nonce`+opaque `identity_revision` alongside existing bounded result payload. Parent matches invocation and rechecks current effective snapshot/revision/admission freshness before adopt/storage; stale response discarded with spent charges retained and next-unit rebuild/canary. Drop references promptly, no Python zeroization promise. Equality attestation does not independently authenticate admission or resist compromised same-user processes. Required synthetic acceptance covers verifier absence at all other boundaries, frame/path/work/snapshot tampering, replay, changed same-size/mtime input, raced handoff and stale response.
- Explicit direct/off compatibility exception: a valid config with `x_proxy_required=false` AND all three proxy paths null may retain the bounded plain→curl daily fallback without routing-only private policy, HMAC or admission. Parent explicitly selects and sends the canonical repository query-config path in bounded stdin; child never chooses an implicit default, validates supplied config and the exact direct/off predicate before clients, derives/validates DB from trusted config+label and retains all existing label/work/backend/protocol limits. Required mode, any configured/partial/invalid path or missing/malformed config cannot use this exception; require full private attested configured-routing flow or refuse safely, never go direct. No budget, cursor, accounting or normal-curl retry semantics change.

| Child-mode acceptance (V1/V4/V8) | Required post-implementation result |
|---|---|
| Valid explicit direct/off, supplied canonical repository config, all three paths null | Actual spawned bounded plain→curl continuation works without private routing inputs/HMAC/admission; same daily allowance, cursor and read charges. |
| Omitted/implicit config source, invalid config/label/DB/work fields | Refuse before clients; never silently reload default or infer direct mode. |
| Required mode or any configured/partial/invalid proxy path | Direct exception unavailable; complete private attested same-revision admission or safe refusal. |
| Configured child snapshot/admission mismatch, route failure or normal curl | No direct fallback or extra backend retry; retain spent charges and existing unit discard/continuation rules. |
- One deterministic shared-state lock, reload before every read-modify-write (not only save), explicit internal non-reentrant ownership and bounded fail-closed acquisition. Prevent stale collector saves overwriting reservations. Status stays read-only/no-network. Preserve migrations before exact-key validation, including partial migration, wrong types/bool-as-int, future dates and stopped rollback.
- Correct serializer owner is `api/models/discovery.py`, not collector script. Preserve legacy states/nulls; omit unavailable new fields; unknown is not direct/healthy. Cover real sources API, CLI reader/status formatting, web fetch/types/formatter and both components; fix fixture `id:"xsearch"` without API renaming.

Spawned-child evidence must launch the real subprocess entrypoint with synthetic private config/DB/admission and bounded capture; calling `_child()` in-process with patched guards is only a unit test. New seeded `web/e2e/collector-status.spec.ts` must use real seeded API state, not `page.route().fulfill()`, at 375/768/1280 with all five proxy states, missing/legacy values, unknown wording, secret absence and overflow checks.

### Security implementation constraints and mechanism evidence

`B2SecurityGate` initially returned infra/setup FAIL narrowly for missing HTTPX HTTPS-proxy evidence. Its revised independent review resolves that FAIL: **Infra PASS / Security CONCERN**, recommending CONDITIONAL complete local implementation/build/testing with mandatory acceptance constraints and no remaining local design blocker in its dimensions. Live release remains BLOCKED. Historical Review6 is not rewritten as PASS; current final local synthesis follows the independent dimension dispositions in §5.

- App-owned HTTPX `AsyncBaseTransport` may adapt the public `httpcore.AsyncHTTPProxy(network_backend=..., ssl_context=origin_ctx, proxy_ssl_context=proxy_ctx, retries=0)` seam; no HTTPX private-pool mutation/global patches. Prefer structured numeric CONNECT. If framing is selected, require bounded complete headers across fragmented writes, exactly one CONNECT with exact original method/authority and one matching Host, replace authority+Host together, reject ambiguity before forwarding, preserve state across HTTPS-proxy `start_tls` and never rewrite tunneled TLS/application bytes. Original Host/SNI/certificate verification remains intact. Apply address/origin policy to explicit bootstrap-derived asset URLs as well as redirects/new or expired bindings; no hostname/direct fallback.
- Curl `CONNECT_TO` requires retained native `curl_slist*`, immutable per session/revision, released only after all handles/requests finish. No Python-list substitution/shared active option mutation. Both route factories and bootstrap cache remain enforced with identity disabled.
- Safe typed route failures must escape QueueClient broad catches/retries/logging/cooldowns using its recognized `AbortReqError` pass-through seam, mapped before generic abort/account handling. Bootstrap's broad asset-task `Exception` swallow requires an account/client-scoped sticky failure latch checked at the outer boundary; refuse further sends, surface original safe proxy failure and preserve cleanup/cancellation. No secret-bearing causes/reprs. Assert actual wire-attempt counts across HTTPX, curl and QueueClient layers; `_CURL_MAX_RETRIES=0` alone is insufficient.
- Enforce existing resource limits while streaming, before decompression/parsing/unbounded child capture/stdin buffering. Apply overall elapsed deadlines including waits/cleanup, not only per-operation timeouts. Single state transaction reload/mutate/persist under one non-reentrant lock preserves reservations across stale collector snapshots. No automatic ACL repair; unsupported ACE/SID/reparse inspection fails closed. Real service path/SID and conforming deployment ancestors remain release selection, not synthetic prerequisites.
- Configured-private account DB uses a maintained app-owned SQLite hook, not site-packages/global patch: owner/ACL-verify or securely create DB AND protected rollback journal before SQLite. On EVERY connection FIRST execute/verify `PRAGMA main.locking_mode=EXCLUSIVE`, THEN set/verify `journal_mode=PERSIST` and `temp_store=MEMORY`, before schema access/migration/read/write. Unsupported/refused/incorrect mode or failed verification refuses safely; never proceed or relax journal identity. Root inheritance is insufficient. Refuse WAL/shm/unknown/unverified sidecars; verify DB/journal identity+ACL after transactions/close. No journal removal/recreation exception or unsecured replacement. Cookie refresh/child/reopen use same ordering; direct/off unchanged. Journal remnants remain sensitive after header zeroing.
- V1/V7/V8 locked-`xreader` acceptance must exercise actual account DB migration/write/reopen, rollback preserving prior value, crash/recovery and journal identity/ACL retention; negative WAL/shm/unknown/unverified/replaced-sidecar cases and cookie-refresh hook reuse, with direct/off regression coverage. Parent's reported cheap-local sqlite3 3.50.4 precreated-files PERSIST/MEMORY observation retained the journal inode, only DB+journal, rollback value and zeroed header. It does not prove locked aiosqlite behavior, crash handling or deployment Windows DACLs; no runtime PASS or release-gate upgrade.
- Later narrow parent-reported evidence: locked sqlite3 3.53.1 EXCLUSIVE-first probe left child exit 17/hot header `d9d505f920a163d7`, then recovered 10 original rows with same journal inode and only DB+journal. Parent reports owner smoke 8 passed/0 skipped across mixed repaired paths, including locked actual crash rollback and protected disposable-DB sharing/reopen; do not attribute every case to this primitive or claim full acceptance. These are not this worker's runs or deployment-host ACL proof. Mandatory implementation acceptance retains verified-mode refusal, same-identity hot recovery/rollback/reopen and no unsecured journal recreation.

### Feasibility Probes Resolved

Both artifacts are colocated with this contract; neither changes production source or proves complete B2 acceptance:

| Artifact | Scoped evidence | Remaining implementation acceptance |
|---|---|---|
| `collector-identity-pool-b2-httpx_FEASIBILITY_03-11-26.md` — VIABLE, HTTPX 0.28.1/httpcore 1.0.9 | Public app-owned transport/core backend seam; HTTP and HTTPS loopback proxies observed numeric CONNECT; origin Host/SNI retained; trusted 200; wrong origin name/untrusted origin root rejected in both modes; untrusted HTTPS-proxy root rejected. Wrapper survives proxy TLS upgrade. | Adversarial framing, policy/rebinding/redirect enforcement, cancellation/pooling/lifecycle, production factories, concurrency and actual child; HTTPS-proxy wrong-hostname negative test. |
| `collector-identity-pool-b2-curl_FEASIBILITY_03-11-26.md` — VIABLE mechanism, curl_cffi 0.16.3/twscrape 0.20.1 | Retained CONNECT_TO native slist at session construction; numeric CONNECT through HTTP/HTTPS proxies; HTTP-proxy case retained origin Host/SNI, trusted 200 and rejected trusted wrong SAN; HTTPS-proxy separate roots trusted 200 and rejected untrusted proxy root. | Production slist lifetime/account isolation, full origin/proxy hostname negative matrix, concurrent factories, retries, child propagation and lifecycle. |

Evidence semantics are **requested numeric CONNECT authority plus authenticated origin TLS**, not proof of a malicious proxy's actual remote socket destination. Independent re-dispositions support CONDITIONAL local implementation, not completed implementation acceptance or live release. Automated gaps above remain due after implementation, not pre-code tests.

### Exact proposed commands — current tooling, not run

Commands below are proposed from current tooling and `B2CoverageGate` inventory; **not run**. New `test_x_proxy.py` and browser spec are implementation deliverables, not existing coverage. PowerShell, repo root:

```powershell
$env:UV_FROZEN = "1"
$env:SCREENER_REFRESH_WORKER = "0"
$env:SCREENER_ATTENTION_PC_WORKER = "0"
$env:SCREENER_ATTENTION_REDDIT_STREAM = "0"
$env:SPOT_VOLUME_REFRESH = "0"
uv sync --project api --frozen --group xreader
uv run --project api --frozen --group xreader python -c "import twscrape, curl_cffi, httpx, httpcore"
```

Sync only if the locked environment is not already prepared; package access may require approval, never real collection/provider calls. Required import preflight prevents module-level `importorskip("twscrape")` from masquerading as acceptance. Record collected/executed transport IDs and zero required skips, not merely exit status.

| Gates | Fixture scope | Exact targeted command (development/diagnostic alternative) |
|---|---|---|
| V1 | Config/default/off, required refusal, pure guards | `uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_web_queries.py api/tests/data/attention/test_x_proxy.py api/tests/tooling_guards -q -rs` |
| V2 | Echo/provider/feed/body cache/freshness/baseline | `uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_proxy.py -q -rs` |
| V3 | Actual local wire/TLS/proxy, Host/SNI, bad SAN/roots, retries, bounds/secrets | `uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_identity_transport.py api/tests/data/attention/test_twscrape_reader.py -q -rs` |
| V4 | Typed failures, normal/canary/fallback/replacement and charges | `uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_reader.py api/tests/data/attention/test_x_pool.py -q -rs` |
| V5 | Per-unit mutation, eviction, identity-off canary | `uv run --project api --frozen --group xreader pytest api/tests/data/test_attention_pc_refresh.py api/tests/data/test_attention_pc_refresh_stream.py api/tests/data/test_attention_pc_refresh_collector.py -q -rs` |
| V6 | Fake-clock wake, real local locks, last quota, stale saves, rollover/crash | `uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_proxy.py api/tests/data/attention/test_x_pool.py api/tests/data/test_attention_pc_refresh_stream.py -q -rs` |
| V7 | Migration/reload/rollback, JSON, sources/router and CLI | `uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_x_pool.py api/tests/analytics/attention/test_sources.py api/tests/analytics/attention/test_sources_health.py api/tests/routers/test_discovery.py api/tests/scripts/test_probe_pc_sources.py -q -rs` |
| V8 automated | Real spawned child; both factories/backends; no direct/no leak | `uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_identity_transport.py api/tests/data/attention/test_twscrape_reader.py -q -rs` |

At final integration choose **one complete backend invocation**, not repeated unchanged collections from each row:

```powershell
uv run --project api --frozen --group xreader pytest api/ -q -rs
```

Existing named tests `test_identity_transport.py::test_both_factory_paths_send_account_identity` and `::test_fallback_child_uses_configured_target_on_both_paths` prove identity/unit behavior only, not complete B2 no-direct/no-leak/spawned-process coverage. Extend actual transport suite; do not duplicate those unchanged cases in a second final acceptance run.

Frontend consumer command, then consolidated RT4 regressions after integration:

```powershell
pnpm --filter web exec vitest run lib/__tests__/source-health.test.ts components/narrative/__tests__/CollectorStatus.test.tsx components/narrative/__tests__/DiscoverySourcesPanel.test.tsx
pnpm --filter web test
pnpm --filter web exec tsc --noEmit --incremental false
pnpm --filter web build:islands
```

Proposed real-server seeded V7/V8 smoke, **from `web/`**, after implementing the spec:

```powershell
$env:E2E_CACHE_ROOT = Join-Path $env:TEMP ("b2-e2e-" + [guid]::NewGuid().ToString("N"))
$env:E2E_API_PORT = "18141"
$env:E2E_WEB_PORT = "18142"
pnpm test:e2e -- collector-status.spec.ts --workers=1
```

Use module-autouse `isolated_cache` for state-touching tests, private temporary owner queries/account DB/list/assignment/policy/body cache, explicit config shared by actual child/API processes, fake clocks/RNG/sleep, synthetic public-looking exit metadata and test-only loopback address policy. Distinct test proxy/origin CAs, network denial except listeners, subprocess egress containment and direct-origin/proxy connection counters must establish wire coverage. Check synthetic credential markers in every public/persistent/process boundary. Browser harness uses fresh disposable cache, unique ports, one worker, `reuseExistingServer:false` and disabled background workers; never modify tracked owner queries or touch live services. ACL/SID snapshots prove policy only; deployment ACL and real route/provider proof remain release gates.

## 10. Patch and permitted verification

Documentation-only files in scope:

1. `process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md` — B2 policy updates only; B1, B3, Part A and canonical SPEC intentionally unchanged.
2. `process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_VALIDATE-B2_03-11-26.md` — updated research evidence, residuals and permitted verification record. This is not independent revalidation.

Parent expressly authorizes this worker's final RT0 after documentation integration: plan-artifact validator, `git diff --check` and discovered feasibility-verdict validators for the two B2 artifacts. Diff check does not cover untracked contract/artifacts. No production source, suites/build/lint/formatters, live activity, commits/pushes/PR/merge or SPEC amendments in this lane. Current RT0 results are recorded separately from historical output below.

**Historical RT0 only — predates this correction; not validation of the current edits.** A prior worker recorded the plan validator exited 0 with output:
```json
{
  "checkedPlans": [
    {
      "path": "process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md",
      "failures": 0,
      "warnings": 0,
      "lines": 396
    }
  ],
  "strict": false,
  "warnings": [],
  "failures": []
}
```
Historical `git diff --check` exited 0 with no output; untracked contract was not covered. These are preserved prior-pass records, not checks run by this worker or current-head acceptance.

## 11. Revalidation handoff

Initial reviews `B2FinalValidate`/Review2/Review3 returned CONDITIONAL; Reviews4–6 returned BLOCKED. Current independent `B2SecurityGate` re-disposition (Infra PASS/Security CONCERN) and `B2CoverageGate` final (Coverage PASS/Breaking-change PASS), with both scoped VIABLE artifacts, supersede earlier local blockers and yield **CONDITIONAL** complete synthetic implementation/build/testing. Preserve historical outcomes. Merged B1 is incorporated. Real release inputs remain blocked for live operation; V1–V8 automation follows implementation.

## 12. Policy update and revalidation boundary

Review history: `B2FinalValidate`, `B2FinalReview2` and `B2FinalReview3` returned **CONDITIONAL**. `B2FinalReview4` identified five policy gaps and returned **BLOCKED**; `B2FinalReview5` and `B2FinalReview6` also returned **BLOCKED**. Review6 found the corrected policy text consistent, while confirming unresolved owner, PR, feasibility, runtime and host-evidence blockers. The policy requirements are not runtime proof or owner authorization.

**Current authority: §5 and final implementation evidence §20.** Local design disposition CONDITIONAL; implementation complete and synthetic automated acceptance PASSED with caveats; live release BLOCKED. Earlier NOT RUN/current-at-the-time entries are historical snapshots. This lane records parent-provided outcomes, not its own suite execution or deployment approval.
Historical Review5 corrected stale status and confirmed lock/migration and ACL policy consistency. Review6 found the subsequent policy consistent but returned BLOCKED with #240 then unmerged and owner/terms, destination binding and runtime/host evidence outstanding. #240 is now merged upstream; release inputs have been correctly separated from local prerequisites. No historical runtime proof is claimed.

Corrections applied in this documentation-only policy revision:

- Spamhaus freshness remains based on its body `; Last-Modified:` and `; Expires:` fields as previously recorded. FireHOL now explicitly uses `This File Date:` as the published-snapshot freshness clock; `Source File Date:` is required, parsed and stored for diagnostics but is not the age clock. Both timestamps must be valid UTC and nonfuture; `This File Date:` must be no more than 24 hours old. `Entries:` must equal the parsed record count; bare host IPs and CIDRs are accepted. Missing, malformed, future/stale timestamps, malformed/missing/count-mismatched headers or malformed records fail closed. FireHOL content is dynamic; no live feed fetch occurred.
- HTTPX: origin and HTTPS-proxy TLS use separate package-managed contexts: `origin_ctx = httpx.create_ssl_context(verify=True, trust_env=False)`; HTTPS proxy uses a separately created `proxy_ctx` and `httpx.Proxy(proxy_url_without_userinfo, auth=proxy_auth, ssl_context=proxy_ctx)`. HTTP proxy has no proxy TLS context or auth. Transport passes the proxy object and origin context with `trust_env=False, retries=0`; client uses that transport, `trust_env=False, follow_redirects=False`. Direct route uses origin context only. Other explicit transports set own origin/proxy contexts, disable env trust and retries. V3 loopback tests must prove distinct verified contexts, hostile CA variables cannot trust untrusted proxy certificates, and expected fixture roots pass. No test was run.
- Actual retries: admission/health/provider paths use a dedicated one-shot app-owned HTTP client and never twscrape's request wrapper. Pinned twscrape `_CURL_MAX_RETRIES=3` means four outer attempts on `NetworkError`; `curl_cffi retry=0` alone is insufficient. The maintained adapter must set `_CURL_MAX_RETRIES=0` before X request use and prove one actual wire attempt. HTTPX transport retries are 0; redirects are disabled; explicit handoff is not hidden retry.
- Provider budget: `day:null` first use initializes to the current UTC day; its hard cap is 899 request starts per UTC day. Persist each reservation before send under one deterministic cross-process lock; recheck the day immediately before send and if it rolled over, do not send and do not refund the consumed reservation. Hold the lock through the single request's completion/timeout and release it in `finally`; do not clear or refund the reservation. State is only `{day,used}`—there is no `in_flight` field or state-clearing step. No other provider request is in flight while the lock is held. No retries; final-11-second deferral; at most one prior-day request may cross into the next day, yielding at most 900 requests under the documented model. Provider quota-counting/late-delivery semantics unproven → keep ipapi unselected/off. Owner terms/privacy acceptance and authorized probe remain required.
- Provider separation: official ipapi docs describe the optional admission/region metadata endpoint as `GET https://ipapi.co/json/`, requiring `ip`, `region_code`, `country_code`, `timezone`; schema version 1 is local and extra fields ignored. Fixed HTTPS origin/path, 64 KiB cap, global budget 899/day. Default unselected/off; owner separately accepts terms/privacy and authorizes live probe. Ipapi is not a reputation provider. Reputation is a separate optional feature, default off; no arbitrary URL, and any future provider requires its own owner-approved endpoint/schema/key/quota/terms contract. No reputation provider is currently selected or enabled.
- Ancestor ACLs: at the protected private root and files, retain the exact allowlist: service SID owns the private directory and has `Modify`; SYSTEM `S-1-5-18` has directory `ReadAndExecute` and file `Read`; no inherited or other ACEs. On directories strictly above the private root, service SID may have read/traverse only, not write/delete/delete-child/ACL/owner rights. SYSTEM and explicitly out-of-scope elevated Administrators `S-1-5-32-544` may have privileged ancestor rights. For every other SID/group reject allow ACEs granting write, delete, delete-child, `WRITE_DAC`, `WRITE_OWNER` or equivalent; read-only ACEs are allowed. Evaluate by SID, treating group ACEs as applicable without assuming membership. Reject deny, conditional/callback/unknown ACEs and unknown rights that could affect service/SYSTEM. Service SID must match actual scheduled-task/service identity. Host probe remains unrun.
- Ancestor-owner precision (independent backend source-review correction): read-only ACEs are insufficient because Windows owner has implicit `WRITE_DAC`. For each directory strictly above the private root require owner SYSTEM `S-1-5-18` or explicitly out-of-scope Administrators `S-1-5-32-544`; service or arbitrary ordinary owner refuses despite read-only masks. Continue evaluating all existing ACE/control restrictions; private root/files retain their service-owned protected policy. Synthetic SID/ancestor tests must cover ordinary/service/unknown-owner refusal and privileged owner with conforming/nonconforming ACEs. Bounded native primitive smoke uses only fresh disposable fixtures—never change existing system/user ACLs. No new live prerequisite: complete conforming deployment-root/identity verification remains BLOCKED release evidence, not a synthetic-development requirement or result of this doc correction.

Earlier corrections in §12 remain in force: FireHOL snapshot/source dates and counts; package-managed curl_cffi roots with CA-variable scrubbing before imports; resource ceilings, redirect/address restrictions and evidence gates. The contract now specifies HTTPX context separation and actual twscrape retry handling above. These are policy requirements, not runtime proof. The validation contract remains untracked, so `git diff --check` does not cover it.

The plan retains the bounded resource ceilings as policy, not runtime proof: feed 8 MiB encoded / 32 MiB decoded, 4 KiB line, 50,000 entries; baseline 1 MiB; echo/provider 64 KiB; X response 32 MiB; child stdout 16 MiB and stderr 1 MiB. It also retains no-auto-redirect, address-binding failure gate, fixed origin allowlists, no arbitrary URLs, fail-closed behavior, health cadence and RT4 evidence requirements.

- Local design decisions are resolved through frozen interfaces, both scoped VIABLE mechanism artifacts and independent re-dispositions. Remaining lifecycle/framing/policy/concurrency/retry/child proofs are post-implementation acceptance, not pre-code blockers. Release inputs/evidence remain unresolved: actual private assignments/exits/regions, deployment allowlist/baseline URL+hash, service/private paths/host ACL, provider choice/terms/privacy and separately authorized live probe, Spamhaus terms, RT4/manual acceptance. Upstream and local B1 dependency resolved; no feature/backend dropped.

Static research remains limited: Spamhaus feed source body metadata and official terms were inspected statically, not fetched live; FireHOL content/count is dynamic; ipapi.co docs/pricing document up to 1,000 free lookups/day; curl_cffi/twscrape/HTTPX findings are pinned-source evidence, not runtime proof. Cloudflare documentation did not establish a stable trace schema. `B2FinalReview6` independently reviewed the corrected policy text and returned BLOCKED. No live HTTP headers, provider/proxy requests, X/Reddit requests, Windows ACL checks, deployment, restart or network-backed test occurred or is authorized by this documentation pass. B1 live comparison remains unperformed and is not silently added as a prerequisite.

Current local gate is **CONDITIONAL**, grounded in recorded independent re-dispositions and bounded mechanism evidence, not fabricated PASS. User authorization covers complete local implementation/build/testing; missing live configuration cannot block synthetic development. Implementation tests remain required after implementation. Production fails closed and release remains BLOCKED.

Implementation must preserve all probe limitations and execute V1–V8: address/redirect/rebinding policy, adversarial framing, both backend factory/cache paths, lifecycle/concurrency/retry and actual child/no-leak acceptance. Mechanism evidence does not prove those finished. Historical RT0 above predates this correction; current final documentation/artifact validation results are recorded separately.

## 13. Current RT0 evidence — final gate correction

Executed once from the assigned B2 worktree after final policy/interface/disposition integration, with explicit parent authorization:

| Command | Observed result |
|---|---|
| `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md` | Exit 0; `failures:0`, `warnings:0`, `lines:432`, overall empty failures/warnings arrays. |
| `git diff --check` | Exit 0; no output. Untracked contract/artifacts are not covered. |
| `node .claude/skills/vc-feasibility-test/scripts/validate-feasibility-verdict.mjs process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool-b2-httpx_FEASIBILITY_03-11-26.md` | Exit 1; `sectionsFound:[]`, `verdictValue:null`, `costClass:null`, `originatingPhase:"pvl"`; eight missing `##` section failures listed below. |
| `node .claude/skills/vc-feasibility-test/scripts/validate-feasibility-verdict.mjs process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool-b2-curl_FEASIBILITY_03-11-26.md` | Exit 1; same structural failures. Curl command ran separately because the initial `&&` chain stopped at HTTPX failure. |

Validator requires `## Hypothesis`, `## Mechanism Under Test`, `## Probe Family`, `## Probe Cost Class`, `## Probe Method`, `## Evidence Captured`, `## Verdict`, `## Resulting Design Constraint`. Both artifacts use `###` as shown in the skill. This is an artifact-format validation failure, not an empirical mechanism failure; do not claim validator PASS. Parent notified for artifact-owner correction/revalidation; this worker's ownership remains PLAN/VALIDATE. Skill/validator heading-depth mismatch reported through tool QA. Current contract evidence appendix was added after the above runs; no suite, production build, lint, formatter, live request, source edit or deployment was performed by this worker.

### Artifact-format correction and final validator disposition

Parent subsequently authorized formatting-only normalization in the two **B2** feasibility artifacts (not the merged B1 artifact): eight required `###` headings became `##`; curl also received a bare `VIABLE` line before its unchanged mechanism-scope paragraph. No empirical output, verdict value, evidence or limitation changed.

- HTTPX verdict validator after heading normalization: exit 0; all eight sections found, `verdictValue:"VIABLE"`, `costClass:"cheap-local"`, `originatingPhase:"pvl"`, `failures:[]`.
- Curl validator first found all eight headings but rejected its inline bold verdict presentation; after parent-authorized bare keyword presentation, its final validator exited 0 with all eight sections found, `verdictValue:"VIABLE"`, `costClass:"cheap-local"`, `originatingPhase:"pvl"`, `failures:[]`.

The initial structural failures above are resolved and preserved as history, not current blockers. Final documentation evidence: plan validator PASS; tracked whitespace diff PASS; both B2 feasibility artifact validators PASS. These are document/schema checks only—not V1–V8 implementation tests or repeat probes. Evidence appendix was updated after the recorded checks; no routine rerun or suite was performed. Local gate remains **CONDITIONAL** for complete synthetic implementation/build/testing; live release **BLOCKED**.

## 14. Security-approved transient child attestation correction

Parent requested the implementation-discovered snapshot-equality gap be closed without persisting credential-derived digests or trusting UUID/stat metadata. `B2SecurityGate` approves the narrowly scoped transient HMAC exception and mandatory bounds/threat limitations now recorded in PLAN B2 and §9 above. Final framing precision uses identical five role tokens/order and role→canonical path→raw bytes in both documents; `backend` is the single protocol field, not an extra style field. Backend owner coordinated final names `request_nonce`, `attestation_key`, `attestation_tag`, `admission_expires_at`; existing query/product/cursor payload retained. This is an internal implementation contract correction under existing full local authorization, no live scope or release upgrade.

After the final correction, with explicit parent authorization, ran once:

- `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md` — exit 0; plan `failures:0`, `warnings:0`, `lines:435`; overall empty failures/warnings arrays.
- `git diff --check` — exit 0; no output. Untracked files remain outside its coverage.

This results appendix was added after those checks. No source, suites, builds, lint, formatter, repeat network probe or live request in this documentation lane. Current local gate remains **CONDITIONAL**, complete synthetic implementation/testing authorized; automated acceptance remains due after implementation and live release **BLOCKED**.

## 15. Explicit direct/off child compatibility correction

Parent approved the narrow direct/off alternative to private child reconstruction, preserving existing bounded plain→curl daily fallback with explicit parent-selected canonical repository query-config path in stdin. The child validates supplied config/label/DB/work and never implicitly selects a default. Routing-only private HMAC/admission requirements apply to configured routing, not the valid all-off predicate; configured, partial, required or malformed inputs cannot enter this exception. PLAN B2 and §9 now include the direct/configured acceptance matrix; no budgets, cursor continuation, charge semantics or live scope changed.

Authorized RT0 after these edits, once per command:

- `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md` — exit 0; `failures:0`, `warnings:0`, `lines:437`; overall empty failure/warning arrays.
- `git diff --check` — exit 0; no output. Untracked files not covered.

Results appendix added after checks. No source/suite/build/lint/formatter/network activity in this correction; implementation acceptance remains unrun in this lane. Local implementation/testing **CONDITIONAL and authorized**; live release **BLOCKED**.

## 16. Optional metadata provenance clarification

Parent's implementation semantic resolution is recorded in PLAN B2 and §9: identity country versus assignment country/subdivision, required declaration coherence, independent unique-IP echo, null-provider owner-declared provenance without provider calls, and explicitly selected ipapi observations failing closed without owner fallback. No automatic provider selection, new public feature field, extra required live input or change to budgets/gates.

Authorized RT0 once after clarification:

- `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md` — exit 0; `failures:0`, `warnings:0`, `lines:440`; overall empty failure/warning arrays.
- `git diff --check` — exit 0; no output; untracked files excluded.

Results appendix added after checks. No source/suite/build/lint/formatter/network activity in this documentation clarification. Local **CONDITIONAL** and live-release **BLOCKED** dispositions unchanged; fixture acceptance remains implementation work.

## 17. Configured-private SQLite journal lifecycle correction

Parent approved the AC17 implementation requirement now recorded in PLAN B2 and §9: maintained scoped secure DB/journal creation and open hook, PERSIST/MEMORY before migration/write, sidecar refusal, post-operation identity/ACL verification and cookie-refresh reuse; direct/off unchanged. Parent's sqlite3 3.50.4 observation is explicitly narrow reported mechanism evidence, not this worker's probe, locked aiosqlite acceptance, crash proof or Windows deployment ACL proof. Persistent journal remnants remain sensitive despite zeroed headers. Locked fixture acceptance remains mandatory; no source or release upgrade.

Authorized RT0 after this correction, once each:

- `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md` — exit 0; `failures:0`, `warnings:0`, `lines:442`; overall empty failure/warning arrays.
- `git diff --check` — exit 0; no output; untracked files excluded.

Results appendix added afterward. No suites/build/lint/formatters/source edits or network probes run by this documentation lane. Local gate **CONDITIONAL**; live release **BLOCKED**.

## 18. Ancestor owner/control-right correction

Parent relayed the independent backend source-review finding: Windows ancestor ownership grants implicit `WRITE_DAC`, so ACE-only checks are insufficient. PLAN B2 and §12 now require SYSTEM/Administrators ownership above the private root alongside existing ACE restrictions; ordinary/service/unknown ancestor owners refuse even with read-only masks. Protected private-root/file policy is unchanged. Synthetic SID/ancestor and bounded native disposable-fixture acceptance are required; never modify existing system/user ACLs for tests. Full conforming deployment-root evidence remains a release-host gate, not an added live prerequisite.

Authorized RT0 once after edit:

- `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md` — exit 0; `failures:0`, `warnings:0`, `lines:443`; overall empty failure/warning arrays.
- `git diff --check` — exit 0; no output; untracked files excluded.

Results appendix added after checks. No source changes, suites, builds, lint, formatter, ACL manipulation or native smoke run in this documentation lane. Local **CONDITIONAL** and live-release **BLOCKED** dispositions unchanged.

## 19. EXCLUSIVE-first protected-journal hot recovery

Parent's later recovery resolution is recorded in PLAN B2 and §9: verify `main.locking_mode=EXCLUSIVE` FIRST, then verified PERSIST/MEMORY before any schema/migration/read/write. Failed mode setting/verification refuses safely; original protected journal identity is never relaxed. Cookie refresh/child/reopen share the ordering, direct/off unchanged. Narrow parent-reported sqlite3 3.53.1 hot recovery and mixed-scope owner smoke are distinguished from full B2 acceptance and deployment proof; this documentation worker did not rerun them.

Authorized RT0 once after final ordering edits:

- `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md` — exit 0; `failures:0`, `warnings:0`, `lines:444`; overall empty failure/warning arrays.
- `git diff --check` — exit 0; no output; untracked files excluded.

Results appendix added after checks. No source, suites, builds, lint, formatters or runtime probe performed by this lane. No complete-acceptance or live-release PASS claimed; local gate **CONDITIONAL**, live release **BLOCKED**.

## 20. Final local implementation status and acceptance caveats

**B2 implementation is complete and locally tested on synthetic fixtures. Automated implementation acceptance: PASSED with the caveats below. Live operation/release remains BLOCKED.** These are final observed results supplied by the parent; this documentation worker did not execute implementation suites. They supersede earlier pre-implementation NOT RUN statuses, not historical review outcomes.

| Evidence scope | Parent-observed result / limitation |
|---|---|
| Final locked full backend | **4123 passed, 4 legacy skipped, 1 failed**. Failure is the unrelated baseline equities Windows path-separator test owned by another session; it is recorded and **not waived**. Do not call the full backend green. |
| Composed direct + negative spawned-child cases | **5 passed**. |
| Web | Vitest **647 passed**; TypeScript **passed**; island build **passed**. |
| B2 seeded browser | **3 passed** at **375/768/1280**. |
| D18 browser | **1 passed**. |
| Normal browser regression history | Corrected invocation **86 passed / 2 failed** (layout reload timeout and context-close; no product cause proven), followed by a later full invocation **88 passed**. Both outcomes retained; the later pass does not erase failures or prove a clean isolated run. |

No feature/backend reduction or live permission follows from local acceptance. Required release inputs/evidence remain **BLOCKED**: real private assignments and expected exits/regions; live baseline URL+hash and endpoint policy; provider terms/privacy (and applicable feed terms); deployment service identity/private-root ACL host probe; separately authorized real route/provider probes; RT4 manual acceptance. Missing/invalid production inputs remain fail-closed, never direct fallback or healthy-by-default.

Final status-documentation RT0, once after edits (not a suite rerun):

- `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md` — exit 0; `failures:0`, `warnings:0`, `lines:444`, empty overall failure/warning arrays.
- `git diff --check` — exit 0; no output; untracked files excluded.

This RT0 results note was added after checks. No source edits or implementation tests/builds/browser runs by this documentation worker; implementation results above are explicitly parent-supplied.
