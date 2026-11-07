# S-Report report (07-11-26)

## 1. Status
CODE-COMPLETE (targeted tests green). Stage 10, branch `claude/b2-validate`. Not pushed. Offline only: the report has no LIVE-READY gate. It reads evidence files only, makes no network calls and changes no pool state.

## 2. Scope delivered
- New `api/analytics/attention/daily_report.py`. It lives in the analytics layer because it reuses `discovery.pick_source_impl`. The functions are `collect_inputs` (file I/O), `build` (pure), `render` (pure), `rebuild` and `rebuild_recent` (atomic writes), and `selected_methods`.
- **RP-1 inputs for day D:** `_facts/events_<D>.jsonl` (facts and the `universe_snapshot` events), each PC store's `_meta/_completeness/<D>.json`, and the browser admission records `_probes/browser_admission_*.json`.
  - Containment is read from the outcome in those admission records. If there are no records, it prints `unknown`.
  - The universe is never recomputed: with no snapshot, the output is "no data for D" for that source and all its methods.
- **Per source/method:**
  - eligible = stored + missing, where eligible means the snapshot's eligible symbols.
  - stored = coin reason `fetched`.
  - estimated = `capped: true`; exact = stored − estimated.
  - missing gives a reason histogram and a per-coin list. A coin missing from the document gets `not_recorded`; a bad reason gets `invalid_evidence`.
  - A method with no document is `no_data`. An unreadable document is `unknown` and never counted.
- **Methods stay separate:** each one follows the snapshot `method_order` and the counts are never summed.
- **Per-coin `selected_method`:** the result of `pick_source_impl` for the window ending D (default 30). It uses the same known-at-time stored series as Discovery history (`discovery_history._load`). If selection fails, it prints `unknown`.
- **Facts sections:**
  - X per-account totals.
  - Reddit method facts per store: polls, navigations, lanes, requests, stop reasons (breaker included) and accounts.
  - The latest query-id state per operation (or `unknown`).
  - Trigger signals: histograms of challenge, account_state, handoff, cooldown, session_check and mixed_call.
  - Switch provenance.
- **RP-2 rules:**
  - `100% stored` only when stored == eligible > 0.
  - Any other coverage is rounded down and capped at 99.9%.
  - Missing coins are printed as `SYM missing (reason)`. No value is ever printed for them.
- **RP-3 revisions:**
  - Files: `_reports/daily_report_<D>.json`, with `schema`, `revision`, `built_at`, `inputs_digest`, `inputs` (one digest per input) and `revisions` (the history, each entry saying `changed` inputs), plus `.txt`.
  - Both files are written atomically, the text first and the json last. The json is the commit marker.
  - An unchanged digest writes nothing.
  - Only completed UTC days are accepted.
  - A module lock serialises the stream threads.
- New CLI `api/scripts/attention_daily_report.py`: `[--day D] [--print]`. D defaults to yesterday UTC. An open day exits with 2.
- `attention_pc_refresh.py` hook (S-Report link of the chain, 10 lines): `AttentionPcWorker._loop` calls `_daily_report()` after every pass, so it also covers `attention_pc_live.LiveStream` settles. That calls `rebuild_recent` (the last 7 completed days that have evidence). Any exception is logged by type only and never stops collection.

## 3. Interfaces for later slices
- `daily_report.rebuild(day, *, now, selector=None, only_if_inputs=False) -> dict | None`
- `rebuild_recent(now, *, days=7, selector=None) -> list[date]`
- `read_report(day)`, `report_paths(day) -> (json, txt)`, `render(report) -> str`, `coverage(stored, eligible)`
- `selected_methods(day, {source: [syms]}, *, window=30, config_path=None, probe_path=None)`

The json top level includes `per_source_method` in exactly the S-StatusAPI §7 layout (`{"<source>/<method>": {eligible, stored, exact, estimated, missing, reasons}}`). Methods with no data or unknown data are left out of it. S-OpsDoctor and S-E2E-Cycle (C12) can call `rebuild`/`read_report`.

## 4. Pool keys and defaults
None added. No switches. The module is read-only over evidence and writes only `_reports/daily_report_<D>.*`.

## 5. Tests (red first)
- Red: collection ImportError for `test_daily_report.py` and `test_attention_daily_report.py`, and for the two new refresh tests (module missing).
- New `api/tests/analytics/attention/test_daily_report.py` (14 tests): full/100%, partial 999/1000 → 99.9% (never 100), all-missing never zero, absent snapshot/documents → no data/unknown, method separation and no_data method, unreadable document → unknown, per-coin selection via selector, facts sections, containment, revision idempotence plus late-settle revision 2 read by the real `sources._daily_report` (complete=True), open day refused, atomic write failure keeps the previous report, rebuild_recent skips days with no evidence, and real `selected_methods` over seeded stores.
- New `api/tests/scripts/test_attention_daily_report.py` (3 tests): CLI.
- Two tests added to `api/tests/data/test_attention_pc_refresh.py`: the pass end rebuilds, and a report failure never stops the loop and never logs the message.
- Green: the new files plus the two hook tests gave 19 passed. The full gate below gave **227 passed** (8m28s).

## 6. Verification commands
From the repo root: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/test_attention_pc_refresh.py api/tests/data/test_attention_pc_refresh_collector.py api/tests/data/test_attention_pc_refresh_stream.py api/tests/analytics/attention/test_sources_finish_status.py api/tests/analytics/attention/test_daily_report.py api/tests/scripts/test_attention_daily_report.py -q -rs`

Data verification: a synthetic run (temporary cache, reddit snapshot SOL/ETH, browser document SOL fetched, ETH `zero_unverified`, settled) printed:
```
[reddit] universe: 2 eligible, 0 ambiguous
  reddit_live_browser: eligible 2, stored 1, exact 1, estimated 0, missing 1 (zero_unverified 1): 50% stored [settled]
    ETH missing (zero_unverified)
  reddit_live_gql: no data for 2026-11-05
  selected method per coin: ETH none, SOL reddit_live_browser
Query ids: unknown
Browser containment: unknown
```
`per_source_method` = `{"reddit/reddit_live_browser": {"eligible": 2, "stored": 1, "exact": 1, "estimated": 0, "missing": 1, "reasons": {"zero_unverified": 1}}}`

## 7. Deviations and review blockers
- `method_switches` is **not** surfaced. The plan's S-Report section (RP-1..RP-3) does not assign it to this slice. It asks for the per-coin `selected_method` instead, and that is delivered. The status follow-up stays with S-StatusAPI, or needs a plan amendment.
- `selected_methods` uses the private `discovery_history._load` so that the series gating is the same as Discovery history. S-RDisc owns that module, so no public wrapper was added.
- Containment is read from the admission records, which are not dated by day. It is the latest admission outcome, not a D-specific fact. No facts kind exists for it, and the schema is owned by S-Facts.
- The hook runs at every pass end of every stream, not only at settles. The digest check makes it a no-op unless D's evidence changed.
- Store points are not part of the digest. A selection change without any document or facts change does not revise D.

## 8. Rollback
Revert this commit. To remove only the hook, drop the `_daily_report()` call and method in `attention_pc_refresh.py`. Existing `_reports/daily_report_*` files can be deleted, and the status reader then shows no report.

## 9. Risks
- Every pass end does file reads for 7 days. A changed day also reads stores for every eligible coin (selection).
- The refresh suites took 8.5 minutes. No baseline was measured, so it is unknown whether the hook added time.

## 10. Owner actions
None.

## 11. Changed paths
api/analytics/attention/daily_report.py, api/scripts/attention_daily_report.py, api/data/attention_pc_refresh.py, api/tests/analytics/attention/test_daily_report.py, api/tests/scripts/test_attention_daily_report.py, api/tests/data/test_attention_pc_refresh.py, this report.
