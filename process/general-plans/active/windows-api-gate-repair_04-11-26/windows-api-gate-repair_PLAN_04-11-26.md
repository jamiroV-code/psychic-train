# Windows API gate repair

Date: 2026-11-04
Complexity: SIMPLE

## Overview
One API-package repair stream addressing Windows harness isolation and equities file synchronization; preserve the approved BTC signal model and owner data.

Status: VALIDATED — Gate PASS after one recorded plan-fix/recheck cycle. Awaiting explicit ENTER EXECUTE MODE; no implementation completion implied.

## Goal
Repair the Windows failures blocking BTC-momentum PR #241 without changing owner configuration, disabling network isolation, or changing HTTP contracts. Keep PR #241 draft and T223 paused until the repair is verified.

## Evidence and limits
- T222 commit 66e5cb3c and documentation head 804f47f7 both passed GitHub API/web CI; latest run 41756474119.
- Original Windows run: 44 failed, 3675 passed, 4 skipped, 5 deselected, 1 error. Historical failed-node cache has no BTC T222 node. Original tracebacks are not fully retained.
- A project-Python throwaway probe observed native socketpair absent and fallback loopback connect rejected by an unconditional socket.connect blocker during asyncio loop creation. Forty cached nodes install this blocker. Historical per-node attribution remains inferred.
- Equities-store test has a native-path/forward-slash assertion mismatch. Twscrape containment test ends with an unrelated assumption that owner account configuration is empty.
- A temporary-file Windows probe observed os.replace fail with PermissionError/winerror 5 while the destination reader is open, then succeed after the reader closes. Equities public load_tickers is unlocked while writes use os.replace under a mutation lock. This proves a reachable read/replace hazard, not the exact historical concurrent-test traceback.
- Old real-data guard false positive from live heartbeat has already been repaired with an exact-path exclusion and isolated regression. Other live collector writes may still legitimately change real cache during a long run; never broaden exclusions automatically.

## Acceptance criteria
- AC1: Offline test guards allow internal loopback sockets but still reject non-loopback network access; no global test networking bypass.
- AC2: Path tests compare meaningful path components rather than native separator spelling; remove incidental default-path assertion instead if it tests no consumer behavior.
- AC3: Account containment tests use explicit configuration and do not assert an owner's configured account path is empty. Remove the incidental empty-default assertion; do not re-pin another default.
- AC4: Equities reads and mutations share synchronization so an in-process reader cannot overlap atomic replacement; retain idempotent add, cap 30, atomic writes, and error propagation.
- AC5: Scoped Windows tests and a real temporary-store concurrent request probe pass; real owner data remains untouched by test writes.
- AC6: Full Windows API gate against a disposable repair checkout and GitHub CI pass before T222 is cleared. Unexpected failures require diagnosis, not skips, assertion weakening, or a baseline waiver. This does not claim verification of the active collector checkout.

## Touchpoints
- api/tests/routers/test_attention.py
- api/tests/routers/test_discovery.py
- api/tests/routers/test_discovery_history.py
- api/tests/routers/test_discovery_price.py
- api/tests/analytics/attention/test_universe_classes.py
- api/tests/data/test_equities_store.py
- api/tests/data/attention/test_twscrape_reader.py
- api/data/equities_store.py
- api/tests/routers/test_equities_router.py — mandatory bounded concurrent-request regression with captured exceptions and exact persisted/accepted-symbol equality.
- api/data/equities_store.py module/lock comments — document in-process synchronization and its limits; no new generic runbook or unrelated canonical-context edits.

## Public Contracts
No HTTP request/response, ticker cap, schema, provider, account configuration, or BTC signal contract changes. load_tickers/add_ticker/remove_ticker signatures stay unchanged. All exported-symbol edits require reference inspection using LSP first.

## Blast Radius
API package only, approximately 8–10 files. Test isolation and in-process file synchronization; no cross-process locking promise, retries, new dependencies, migrations, authentication, deployment changes, or live cache mutation. Runtime equities correction means this is not the earlier heartbeat-only QUICK FIX.

Review-only callers: api/routers/equities.py; api/analytics/equities_board.py; api/data/equities_refresh.py; api/data/layout.py; api/tests/data/test_equities_refresh.py; equities/layout/status tests and api/scripts/seed_e2e_equities.py; web/lib/api/equities.ts and web/lib/screener-variant.ts. Keep frontend contracts unchanged. Store locking must not invert layout-to-equities ordering or hold the store lock through refresh/network/layout callbacks. Per-operation synchronization does not make the router's separate pre-read/add one transaction; do not expand scope to duplicate-request side-effect semantics.

## Implementation checklist
- [ ] Inspect references before exported-function body changes using available LSP; if LSP cannot initialize, record that failure and use targeted reference inspection without claiming LSP evidence.
- [ ] At the five known fixtures, retain both HTTP transport blockers and use the numeric-IP tuple-only convention from api/tests/data/test_attention_pc_refresh_stream.py. Forward valid IPv4/IPv6 loopback tuples (including IPv6 four-tuples) only. Deny external literals, hostnames, malformed and AF_UNIX/string addresses before forwarding; no DNS or additional networking exceptions.
- [ ] Remove incidental native-path spelling and owner-default assertions, plus any newly unused imports; preserve behavioral call-time override and explicit account containment/refusal tests. Do not re-pin another incidental default.
- [ ] Change the equities store lock to threading.RLock and hold it across the entire existing public load_tickers body, including file-handle closure. Retain add/remove mutation critical sections and parsing/error behavior. No retries, extra normalization, new lock registries, or public-signature changes. Release before all external callbacks.
- [ ] Add controlled temporary-store reader/mutator regression: hold an actual destination reader open; observe writer lock contention via test-only instrumentation, not a sleep or worker-start event; assert real replacement occurs only after handle closure. Parameterize add/remove if useful. Collect all errors and assert the old reader snapshot and exact final set. Release reader in finally and bound all worker completion.
- [ ] Add one public-read OSError regression proving propagation and subsequent successful access from another thread, so a leaked RLock cannot hide behind same-thread reentrancy. Preserve the existing interrupted-write persistence/cleanup test; avoid duplicate cap/idempotency tests.
- [ ] Harden existing 35-request router test: bounded workers, explicit exceptions/results, exactly thirty 200s and five 409s with cap text, and persisted symbols equal accepted symbols. Redirect cache/watchlist/equities/layout and stub refresh/external networking until all workers finish. No group_id is needed.
- [ ] Run focused tests once after final edits in the isolated child environment; run the required separate throwaway temporary-store real TestClient concurrency smoke with the same exact outcomes. All concurrency exercises use parent-enforced process deadlines; executor context exit is not a timeout guarantee. No dependency/plugin installation.
- [ ] Run the full Windows API gate only against a disposable clean repair snapshot, using the mandatory isolation protocol below. Keep live collector running unchanged; do not expand guard exclusions, restore owner files, or copy private data.
- [ ] Update the existing relevant documentation and T222 evidence after smoke proof; remove probe scaffolding. Commit only scoped files on a branch, then push and verify CI before considering merge.

## Verification Evidence
| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Existing 40 affected router/end-to-end nodes with repaired fixtures | Fully-Automated: scoped pytest | AC1 |
| Explicit external destination denied, internal loopback allowed in throwaway guard probe | Agent-Probe, no external connection | AC1 |
| Equities-store and twscrape containment tests | Fully-Automated: scoped pytest | AC2, AC3 |
| Deterministic reader/writer exclusion plus existing cap/idempotent/error cases | Fully-Automated: equities tests | AC4 |
| Temporary-store 35 concurrent real TestClient POSTs, exceptions captured, exact HTTP results and persisted symbols | Agent-Probe | AC4, AC5 |
| Full Windows pytest.main with explicit api/pyproject.toml in the disposable repair checkout, import/store confinement preflight, seeded synthetic guard files, retained sanitized diagnostics and parent timeout | Fully-Automated | AC5, AC6 |
| GitHub API/web CI on published repair head | Fully-Automated | AC6 |

Scoped pytest arguments passed to pytest.main in the disposable bootstrap (not a command to run in the live checkout): `-c api/pyproject.toml api/tests/routers/test_attention.py api/tests/routers/test_discovery.py api/tests/routers/test_discovery_history.py api/tests/routers/test_discovery_price.py api/tests/analytics/attention/test_universe_classes.py api/tests/data/test_equities_store.py api/tests/data/attention/test_twscrape_reader.py api/tests/routers/test_equities_router.py api/tests/deploy/test_real_data_snapshot.py -q`. The API smoke uses a fresh temporary store inside the same isolated snapshot.

## Disposable verification protocol
- Use the complete tracked nonsecret repository snapshot at the repair commit, not just api/. Do not copy untracked owner files, .env, account databases, cookies, real cache, or private configuration. Reject links/junction escapes. No changes to the owner's interpreter, .pth files, collector environment, or machine settings.
- Reuse existing project Python with -I only with a same-process bootstrap: remove original root/API source search entries, prepend disposable root/API, and reject editable finders or preloaded/loaded owner-source modules. -I alone is insufficient.
- Before importing application modules, disable SCREENER_REFRESH_WORKER, SCREENER_ATTENTION_PC_WORKER, SPOT_VOLUME_REFRESH and fallback providers in the child only; remove inherited credentials and path overrides or redirect them inside the sandbox. Preserve deliberate per-test overrides.
- Assert namespace api.__path__ entries, concrete source module origins (cache/equities/main/deploy guard), and effective cache/watchlist/equities/layout/config paths resolve inside disposable roots. api is a namespace package; do not require api.__file__. Verify no owner source remains reachable through startup hooks/search paths and maintain confinement through collection/execution. Fail before pytest collection on any violation.
- Seed a minimal synthetic cache sentinel and reader-valid watchlist at disposable default paths BEFORE importing deploy conftest and its baseline; this keeps the existing equality guard active rather than skipped. No real data is copied. Keep that guard and its exact heartbeat exclusion unchanged.
- Invoke pytest.main in this exact preflighted process with -c api/pyproject.toml and the selected test paths. Parent process enforces deadlines (scoped/smoke 600 seconds, full suite 1800 seconds), captures all output/exit status, and terminates only its own disposable child on timeout. Tests must release coordinated workers before temporary redirects unwind.
- Logs stay local; publish sanitized failure summaries only, never environment dumps, account paths, config bodies, cookies, credentials, secret hashes, or raw logs automatically.
- Feasibility evidence: windows-api-gate-repair_FEASIBILITY_04-11-26.md observed the installed-interpreter mechanism on an api-only tracked temporary snapshot. Repeat and extend its assertions on the complete repair snapshot before tests. This is not yet a passing test gate.

## Test Infra Improvement Notes
Original failure output lost detailed tracebacks amid a large metadata diff. Preserve full output for repair verification and report only changed paths for diagnostics; no broad guard redesign in this scope. Never edit api/data/attention_queries.json or real cache/watchlist to satisfy tests.

## Validate Contract
Gate: PASS (2026-11-04). First pass identified unsafe active-checkout verification and underspecified guards/concurrency checks; the plan was amended and independently rechecked. WinRepairInfra, WinRepairCoverage, WinRepairContracts, and WinRepairSecurity returned PASS for the amended plan. No concerns or failures remain in plan validation; runtime gates are still unexecuted.

### Required execution gates
1. Execute only this plan and its listed touchpoints; inspect references first. Preserve all private configuration, live data, and collector behavior.
2. Before scoped tests, smoke, or full tests, satisfy the same-process disposable isolation protocol and synthetic default-guard baseline. Fail closed on any escaped source/store path, worker activation, editable finder, or link escape.
3. Verify actual repaired numeric loopback guards against recorder-only allowed/denied destinations; retain both HTTP blockers. Do not make real external connections.
4. Run the listed scoped pytest selection, deterministic exclusion/error-release regressions, and separate real TestClient temporary-store 35-request smoke with exact responses/persistence and bounded process lifetime.
5. Run one full Windows API gate in the preflighted disposable repair snapshot with `pytest.main(["-c", "api/pyproject.toml", "api/", "-q"])`. Capture sanitized evidence and enforce the parent deadline. Existing equality guard must execute, not skip.
6. Update module synchronization documentation and repair/T222 evidence only after smoke proof; commit only scoped files on a branch when authorized, publish and inspect CI at the exact repair head. No merge or T223 until all required gates pass. Any new failure remains a blocker, not a waiver.

### Feasibility Probes Resolved
The colocated FEASIBILITY artifact records VIABLE reused-interpreter import isolation on the observed API-only synthetic snapshot, exit 0. This licenses the bounded bootstrap design only; repeat the extended preflight on the complete repair snapshot before actual tests.

### Evidence boundary
Independent recheck is source/plan validation, not an observed passing Windows suite. Historical failure attribution remains as recorded. See `results.tsv` and the colocated validation report.

## Resume and Execution Handoff
- Selected plan: process/general-plans/active/windows-api-gate-repair_04-11-26/windows-api-gate-repair_PLAN_04-11-26.md
- Last completed step: independent validation recheck after plan amendments, all four dimensions and feasibility PASS.
- Validate-contract status: written; Gate PASS; full behavioral gates pending execution.
- Supporting context: process/context/all-context.md; process/context/tests/all-tests.md; vc-debug; T222 report and prior baseline reports cited there.
- Next step: obtain explicit ENTER EXECUTE MODE for this exact separate repair plan, then implement its bounded scope and run the required gates. Do not start T223 or merge PR #241 before repair verification.

## Phase Completion Rules
Draft planning is not implementation approval. Validation must resolve its gaps before explicit execution authorization. Code-only completion is not VERIFIED: require scoped tests, temporary-store API smoke, the full Windows gate, and published-head CI. Keep T222 draft and T223 blocked until these gates are satisfied; do not waive failures automatically.

## Autonomous Goal Block
SESSION GOAL: Repair Windows API harness/concurrency failures without touching owner data, then verify the disposable Windows gate and GitHub CI.
Autonomy rules: No standing execution consent; explicit execution authorization is required. Once authorized, implement this selected plan only.
Hard stops: Owner source/data escape, unsafe networking, live collector changes, unobserved worker failures, unresolved verification failures.
Next phase: EXECUTE after explicit user command.
Contract summary: Numeric loopback-only test exception; store-local RLock; bounded behavioral regressions; isolated same-process preflight and full Windows gate; no baseline waiver.
Execute start command: ENTER EXECUTE MODE for process/general-plans/active/windows-api-gate-repair_04-11-26/windows-api-gate-repair_PLAN_04-11-26.md
