## 1 Task ID

Collector identity pool, Part A / Stage 0. EXECUTE worker IdentityPartA.
Plan: `collector-identity-pool_PLAN_02-11-26.md`, Gate PASS, E1-E3.
Draft PR: https://github.com/jamiroV-code/psychic-train/pull/234

## 2 Outcome

partial — implementation complete and submitted for review; phase verification is not complete without the bounded browser evidence and owner confirmation. No merge or deployment. Part B and Stages 2+ were not implemented.

## 3 Summary

- Optional daily cap and rest settings default off without editing the committed queries file.
- Pool loads old state, counts each account's loaded pages, finishes a started coin-day on one account and preserves failover accounting.
- At-cap selection skips with `account_cap`; in-flight waits win; otherwise caps exhaust the source with `budget_spent`.
- Producer registration persists rest deadlines; read-only status never writes. Separate atomic ready marks survive pool saves and become eligible on a later UTC day.
- All three production pool construction sites receive settings and ready marks; live pool readiness reloads the separate file.
- Sizing is computed by the X stream and read from files; stale or malformed sizing stays unknown.
- Existing account health and completeness drive account, cap, rest, ready, sizing and coverage display; no second per-account wire list.
- Smoke uses fake readers, fake UTC clocks, temporary cache, no provider calls. Local tests and evidence below.

## 4 Files changed

Backend implementation:
- `api/data/attention/web_queries.py`
- `api/data/attention/x_pool.py`
- `api/data/attention/x_capacity.py` (new pure arithmetic helper)
- `api/data/attention/twscrape_reader.py`
- `api/data/attention_pc_refresh.py`
- `api/analytics/attention/sources.py`
- `api/models/discovery.py`

Backend tests/guards:
- `api/tests/data/attention/test_x_pool.py` (new)
- `api/tests/data/attention/test_web_queries.py`
- `api/tests/data/attention/test_twscrape_reader.py`
- `api/tests/data/test_attention_pc_refresh.py`
- `api/tests/analytics/attention/test_sources.py`
- `api/tests/analytics/attention/test_sources_health.py`
- `api/tests/tooling_guards/test_pc_collector_guards.py`

Web:
- `web/lib/types/discovery.ts`
- `web/lib/source-health.ts`
- `web/lib/__tests__/source-health.test.ts`
- `web/components/narrative/CollectorStatus.tsx`
- `web/components/narrative/DiscoverySourcesPanel.tsx`
- `web/components/narrative/__tests__/CollectorStatus.test.tsx`

Docs: `deploy/README.md` and this report. PLAN/SPEC left unchanged: phase completion is not being asserted.
Existing pool/reader regression tests in `test_x_reader.py`, router wire-shape tests and other listed touchpoints were intentionally retained unchanged where no contract update was required. No dependencies, `.github/`, query data, Reddit logic or scoring changes.

## 5 Commits

Branch: `claude/identity-pool-part-a`.
Worktree: `C:/Users/jamir/.herdr/worktrees/my_site/wt-identity-a` (retained).
Fetched main before creating it: `a6d3e382`.

- `aa4f8775`: backend red tests (missing sizing module fails collection).
- `64f4bb78`: UI red tests (8 failures observed, 12 existing cases passed).
- `b66ce579`: pool/config/CLI/accounting/sizing/models and integration tests.
- `f1c0d2a1`: account/coverage display and owner documentation.
- `6b0412027323dd3bc38b6ebbbb21bf0b852c218f`: deliberate metadata contract test update, asserting unchanged old serialized shape.

The report is committed after that implementation/test head. Final report-only head and final-head CI result are recorded in the worker handoff and PR checks.

## 6 Tests run

All commands ran in the isolated worktree (web commands in `web/`), one heavy command at a time. Date: 2026-11-02 UTC. Individual start timestamps were not separately captured for the early backend commands; no fabricated per-run timestamps are supplied. Verification revision/time recorded by shell: `6b0412027323dd3bc38b6ebbbb21bf0b852c218f`, 2026-11-02T19:33:59Z.

Setup: `UV_FROZEN=1 uv sync --project api --frozen`; in web, `pnpm install --frozen-lockfile` — succeeded, no dependency-file changes.

Red evidence:
- `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_x_pool.py api/tests/data/attention/test_web_queries.py -q` — collection failed because `x_capacity` did not yet exist; committed as `aa4f8775`. This does not claim that every red test body was independently observed failing.
- `pnpm exec vitest run components/narrative/__tests__/CollectorStatus.test.tsx` — 8 failed, 12 passed, before UI implementation; committed as `64f4bb78`.

Targeted development evidence (working tree over the red commits):
- `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_x_pool.py api/tests/data/attention/test_x_reader.py api/tests/data/attention/test_twscrape_reader.py api/tests/data/attention/test_web_queries.py -q` — 203 passed, 1 skipped, 3 failures. Two new rest fixtures had not performed producer registration; corrected to call the same explicit `begin_pass` used by the stream. Existing reader status dict expectation extended for the new fields.
- `pnpm exec vitest run components/narrative/__tests__/CollectorStatus.test.tsx components/narrative/__tests__/DiscoverySourcesPanel.test.tsx lib/__tests__/source-health.test.ts` — 32 passed, 1 expected-text mismatch in the existing account line; deliberately updated to the extended text.
- `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_x_pool.py api/tests/data/attention/test_x_reader.py api/tests/data/attention/test_twscrape_reader.py api/tests/data/attention/test_web_queries.py api/tests/data/attention/test_x_window.py api/tests/data/test_attention_pc_refresh.py api/tests/data/test_attention_pc_refresh_collector.py api/tests/data/test_attention_pc_refresh_stream.py api/tests/analytics/attention/test_sources.py api/tests/analytics/attention/test_sources_health.py api/tests/tooling_guards/test_x_reader_guards.py api/tests/tooling_guards/test_pc_collector_guards.py -q` — terminated at the tool's 300-second deadline, no failure shown before termination. Not called a pass; the later focused/full runs cover these files.

Isolated smoke (working tree subsequently committed in `b66ce579`):

`UV_FROZEN=1 uv run --project api pytest api/tests/data/test_attention_pc_refresh.py::test_stage0_isolated_smoke_cap_no_split_budget_spent_sizing api/tests/data/test_attention_pc_refresh.py::test_stage0_new_registration_rest_and_ready_next_day_canary api/tests/data/attention/test_x_pool.py -q -s`

**25 passed**, 17.28 s. Emitted evidence:

```text
STAGE0 SMOKE: cap skip, no-split 2 pages, canary+unit=60, budget_spent, next-day schedule, coverage 1/3
STAGE0 SMOKE: rest gate, ready survives running save, next-day canary includes new account
STAGE0 SMOKE: loss failover once; account reads 20+40=global 60; stored sample 40, not 60
```

Consolidated gates:

1. At `f1c0d2a1`: `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/analytics/attention api/tests/data/test_attention_pc_refresh.py api/tests/data/test_attention_pc_refresh_collector.py api/tests/data/test_attention_pc_refresh_stream.py api/tests/tooling_guards -q` — **1888 passed, 2 skipped, 2 failed**, 656.96 s. One metadata exact-key assertion fixed in `6b041202`; the other was the known Windows loopback/socketpair failure in `test_universe_classes`.
2. At `6b041202`: `UV_FROZEN=1 uv run --project api pytest api/ -q` — **3656 passed, 42 failed, 4 skipped, 5 deselected**, 935.74 s. The corrected metadata test and all new Stage 0 tests passed. Forty failures are blocked Windows socketpair creation in the existing universe/router tests. Two unrelated equities tests fail on Windows path separators and an `os.replace` sharing/access failure. Those files were not changed or weakened; Linux CI is the judge. No unchanged baseline was rerun to reconfirm user-reported host failures.
3. At `6b041202`: `pnpm test` — **638 passed in 67 files**, 71.09 s. Start 20:31:09 host local time; observed 2026-11-02 UTC. Existing React act warnings remain warnings.
4. At `6b041202`: `pnpm exec tsc --noEmit --incremental false` — **pass**, exit 0.
5. At `6b041202`: `pnpm build:islands` — **pass**, 1080 modules transformed, 10.39 s build.

CI: `gh pr checks 234 --watch --interval 20` invoked against the draft PR; final observed results are added below after completion.

## 7 Tests NOT run

- Bounded browser check at 375/768/1280: **not run**. Measured `node -p "Math.round(require('os').freemem()/1024/1024)+' MiB free'"` returned **1446 MiB free** while sharing the host with live services. The permitted low-memory deferral was used; no test browser or dev servers were started. Component rendering is not claimed as browser width/payload-to-screen evidence.
- No real collector/reader invocation, live cache reads, provider calls, cookie refresh, live process control, deployment or merge.
- No Part B/Stage 2+ probes.
- No independent reviewer approval or owner acceptance obtained by this worker. This report does not fabricate a high-risk approval/evidence-pack decision.

## 8 Deviations

1. **Isolation incident, recovered by Main:** early relative-path `edit` calls targeted `api/data/attention/web_queries.py` and `api/data/attention/x_pool.py` in quiet-forest instead of the new worktree. The mismatch was detected from an absolute-path reread. Work stopped and Main was notified at `review`. Main saved the stray diff outside the repo and reverted those two changes, explicitly confirming the owner's `api/data/attention_queries.json` was untouched, then authorized continuation using absolute paths. All subsequent read/edit/write paths were absolute; after edits, status was checked for identity-a, quiet-forest and main. Their existing query-file edits and other plan folders remained unchanged by this worker. No live processes were touched.
2. Backend red gate failed at collection (missing new helper), rather than individual execution of every new red test body. UI red cases were individually observed failing. Later smoke/full tests execute the E2 bodies.
3. A 300-second targeted backend deadline was too short; recorded as incomplete, not green. The focused gate and full API gate subsequently ran with longer deadlines.
4. New rest tests were corrected to model producer registration explicitly, because constructors/status readers must remain read-only. `begin_pass` persists registration even before a reader starts.
5. Three existing expectations were intentionally extended, not deleted: reader status exact account dict (`test_twscrape_reader.py`), collector model metadata key set (`test_sources.py`, with an additional unchanged-legacy-wire assertion), and account status text (`source-health.test.ts`). Existing X pool/reader behavior suites were not replaced.
6. E1 start check: fetched remote refs; inspected open PR branches `claude/pairs-spreads-staging` (#221) and `claude/record-screener-sort-pass` (#220), plus fetched remote branch diffs. No shared-file overlap was printed. Unpushed provider-fallback work cannot be inspected from remote refs; additions to shared models/types are optional and trailing, and null sizing fields are omitted on the wire.

## 9 Blockers

No implementation blocker is known from the executed Stage 0 tests. Local full API is not green on Windows; Linux CI must pass before acceptance. Browser evidence and owner confirmation remain explicit phase-completion gaps. Independent review is still required; the PR remains draft. No approval to merge, deploy or proceed to Part B is implied.

## 10 Follow-up

Owner/Main review the draft, final-head CI and isolated smoke, then arrange the bounded browser/payload-to-screen check when memory allows and obtain owner acceptance. Decide the production cap separately; the default remains unlimited. No live configuration changes were made. Do not remove this worktree. Part B requires its own validation and explicit EXECUTE approval after Part A is merged.

## 11 Context cost

Unmeasured. Read the named PLAN, SPEC, AGENTS.md, master-planner sections 6/9, tests router, operating instructions, named production/test touchpoints and deploy documentation. Debug and risk-evidence skills were consulted. Tools available/used: file read/search/glob/edit/write, shell commands, background wait and parent messaging. No subagents were spawned; no browser was used. Only Main was contacted for the isolation incident/recovery decision.
