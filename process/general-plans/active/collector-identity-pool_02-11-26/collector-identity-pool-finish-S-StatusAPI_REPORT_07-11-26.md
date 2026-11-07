# S-StatusAPI slice report (07-11-26)

## 1. Status
CODE-COMPLETE for the backend status contract (AC13, AC14 status side). Stage 2, branch `claude/b2-validate`. Not pushed.

## 2. Scope
Owned files only: `api/analytics/attention/sources.py`, `api/models/discovery.py`, `api/tests/analytics/attention/test_sources.py`, new `api/tests/analytics/attention/test_sources_finish_status.py`. `test_discovery.py` did not need changes.

## 3. Changes
- Models (all optional, allowlisted, omitted from JSON when absent): X account `endpoint_state`, `behaviour{…}`, `harvest{…}`, `ct0_rotations_seen`; `DiscoveryQueryIdHealth` (`health.queryids`); `DiscoveryRedditMethodHealth` (`health.methods[]`, also `collector.sources[reddit].methods`); `DiscoveryRedditAccountHealth`, a separate model with states `active|resting|paused|locked|unknown` and `site: "reddit"`, carried in `health.accounts[]` (X `DiscoveryAccountHealth.state` literals are not widened); `collector.daily_report`, `collector.doctor`, `collector.browser{relay_refusals ≤ 5 hostnames, profile_state}`.
- Values are limited to codes (`[a-z][a-z0-9_]{0,39}`), counts, UTC timestamps, ISO days, hostnames and closed literals. A malformed group is replaced with `unknown` or left out; it is never guessed.
- Readers in `sources.py` read files only: `reddit_methods` is a separate reader with one row per `REDDIT_METHODS` entry and no merging; `reddit_accounts`; `_queryids`, `_daily_report`, `_doctor`, `_browser`. `_project_account` refuses either the whole proxy group or the whole finish group and keeps the rest. A malformed legacy field still makes the snapshot unreadable, as before.
- `PC_STORES` is unchanged, so the stream-exclusion contract still holds (table H, "preserved" option).

## 4. Tests (red first, then green)
`UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/analytics/attention/test_sources_finish_status.py test_sources.py test_sources_health.py test_sources_proxy_health.py test_discovery.py api/tests/data/test_attention_pc_refresh_stream.py -q -rs` → 304 passed, 0 skipped.

## 5. Evidence
All-off equivalence test: no `methods`, `queryids`, `daily_report`, `doctor`, `browser` keys appear. Secret-marker assertions cover every reader. An end-to-end `build_sources` test checks the Reddit row and the collector box.

## 6. Deviations
None from the plan. One amended exact-key test (`test_sources_model_key_set_without_testclient`, table H): it adds `daily_report`/`doctor`/`browser` and the collector-source `methods`, and keeps the legacy omission checks.

## 7. File contracts producers must write (defined by this slice; later slices conform or message the S-StatusAPI owner)
- `_pc_state/reddit_live/<store>_health.json` (S-RCore-B): `{state, reason, lanes{posts,comments: 0..1}, comments_scope, requests_today, cap}`. `last_settled_day` comes from the method's own completeness documents.
- `_pc_state/reddit_accounts.json` (S-RAcct-A): `{"accounts": {label: {state, reason, reads_day, reads_used, rest_until, session_state, session_checked_at, proxy_state, …}}}`. `_pc_state/reddit_account_ready.json`: `{"ready": {label: "YYYY-MM-DD"}}`; an account counts as ready from the next UTC day.
- `_pc_state/x_queryids.json` (S-XProto): `{check_state, last_check, operations: {op: {active: {id, source, adopted_at}}}}`.
- `_reports/daily_report_<D>.json` (S-Report): `{revision, per_source_method: {"<source>/<method>": {eligible, stored, exact, estimated, missing, reasons}}}`.
- `_reports/doctor.json` (S-OpsDoctor): `{state: PASS|WARN|FAIL|UNKNOWN, checked_at, failures, warnings}` (lists are counted).
- `_pc_state/browser_health.json` (S-Relay): `{relay_refusals: {hostname: count}, profile_state}`.
- X pool `health()` accounts may add `endpoint_state`, `behaviour`, `harvest`, `ct0_rotations_seen`. They pass through automatically.

## 8. Risks
The producer layouts above are fixed here ahead of their slices. If a producer chooses a different layout, the status shows `unknown`; it does not show a false success.

## 9. Rollback
Revert the commit. No state files are written or migrated.

## 10. Open questions
None blocking.

## 11. Next
S-StatusUI consumes the models. The producer slices conform to section 7.
