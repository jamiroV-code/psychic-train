# W8f: Discovery wiring (REPORT, 30-10-26)

## 1 Task ID

W8f Discovery wiring (PLAN `narrative-baskets-xreddit-collector_PLAN_21-10-26.md`, section "W8f: Discovery wiring", lines 230-236; SPEC AC5, AC6, AC14, AC23, AC32 rescale part; Locked pacing rule 9, Q10, Q13). Branch `claude/w8f-discovery-wiring`, based on `origin/main` 8f1b5023 (W8e merged). Draft PR #193.

## 2 Outcome

review (done with the deviations in heading 8; CI result in heading 6)

## 3 Summary

- `api/data/discovery.json`: new keys `fetch_side` (`xsearch`, `reddit` = `pc_side`; `trends`, `wikipedia`, `exchange_activity`, `defillama`, `github_dev` = `github`), `source_impl` (`xsearch: xsearch_web`, `reddit: [reddit_web, reddit_stream]`), `x_discovery_mode: rotation`, `x_rotation_points: 3`, `x_rotation_max_lag_days: 7`.
- `api/analytics/attention/discovery.py`: the 5 keys join `CONFIG_KEYS`; `_check_wiring` validates them strictly: `fetch_side` must be an object naming every weighted source exactly once with `github` or `pc_side`; `source_impl` keys must be in `registry.SOURCE_IMPLS`, the value one known store or a non-empty list of distinct known stores, and every listed store must belong to that source's fetch side (PC stores need `pc_side`, the official store needs `github`); `x_discovery_mode` in `rotation`/`window`; `x_rotation_points` int >= 2; `x_rotation_max_lag_days` int >= 0. New helpers `fetch_sides`, `source_impls`, `x_setting`, `DEFAULT_FETCH_SIDE` (equal to the W8e worker's `FETCH_SIDE`, guarded by a test).
- Scoring: `_weighted_source` reads the `source_impl` stores in order; the first store that yields a change feeds the whole window and is the only one used (never spliced, AC14). `series_names` returns the impl stores, so live scoring, signal snapshots and history all read the chosen stores.
- X rotation mode (`_rotation_change`): newest of the latest `x_rotation_points` stored points dated <= the scored day against the mean of the earlier ones, base mean must be > 0; fewer points, or a newest point older than `x_rotation_max_lag_days`, makes X missing and weights rescale. In rotation mode a series in state `insufficient-history` still counts (the 3 points replace the 90-day gate for X only). Every other source keeps the 7-day window and `max_source_lag_days`. `window` mode is today's rule.
- `api/data/attention/registry.py`: `SOURCE_IMPLS`, `PC_STORES` (`xsearch_web`, `reddit_web`, `reddit_stream`), PC stores skip the probe-record gate; `read_series(..., known_at_time=True)` drops points whose evidence row is `backfilled` or was collected after D+1 (AC5, Annex B). `build_discovery(..., known_at_time=False)` passes it through.
- `api/analytics/attention/sources.py` and `api/models/discovery.py`: `DiscoverySourceRow` gains `reason` (closed list: "", `parked`, `x_live_off`, `not_probed`, `stale`, `insufficient_history`, `no_stored_data`, `invalid_file`) and `impl` (the store a weighted row reports). A weighted row reports the first impl store with usable coins, else the first with data, else the first. X in rotation mode uses the 3-point gate and the 7-day lag on the row. State mapping: short history = `insufficient-history`, stale or failed = `unavailable`, with the reason code and the note.

## 4 Files changed

- `api/analytics/attention/discovery.py`
- `api/analytics/attention/sources.py`
- `api/data/attention/registry.py`
- `api/models/discovery.py` (2 additive fields on `DiscoverySourceRow`)
- `api/data/discovery.json`
- `api/tests/analytics/attention/test_discovery_wiring.py` (new)
- `api/tests/routers/test_discovery.py` (one line: the exact Sources row key set now includes `reason` and `impl`; outside the envelope's file list, see heading 8 item 8)
- this report

`api/data/attention_pc_refresh.py` was NOT edited: its default `FETCH_SIDE` already equals the validated config, and its raw read of `fetch_side` gives `[xsearch_web, reddit_web]` on the shipped file (both asserted in `test_fetch_side_rejects_unknown_value`).

## 5 Commits

- 934cab81 test(attention): W8f red-first discovery wiring and X rotation tests (15 tests, all failing at that commit: missing helpers / unknown config keys)
- 423a2e66 feat(attention): W8f discovery wiring (implementation; also two test fixes, see heading 8)
- report commit (this file)

## 6 Tests run

- Red: `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention/test_discovery_wiring.py -q` at 934cab81: 15 failed.
- Baseline on main 8f1b5023 (this Windows host): `pytest api/tests/analytics/attention -q`: 1 failed, 378 passed; the failure is `test_universe_classes.py::test_discovery_end_to_end_on_fixture` ("handler must not reach the network", the known ProactorEventLoop issue).
- After: `pytest api/tests/analytics/attention -q` (full run before the last fixture fix): 2 failed, 392 passed (394 = baseline 379 + 15 new); the 2 failures were the same Windows-only test and `test_sources_row_shows_reason_code` (fixture bug, heading 8 item 6). After that fix `test_discovery_wiring.py` alone: 15 passed, so the suite is 393 passed + the 1 Windows-only failure. No existing discovery or sources test was changed or deleted.
- `api/tests/routers -k "discovery or narrative or sources"`: on main 32 failed, 25 passed; on this branch every failure shown was "handler must not reach the network" (Windows host issue, not chased per envelope; the branch's summary line was cut off, so the branch count is not recorded).
- Red test names from the PLAN, all present: `test_fetch_side_rejects_unknown_value`, `test_source_impl_reads_web_store`, `test_two_methods_never_spliced`, `test_pc_off_gap_rescales_not_zero`, `test_t96_lag_drops_source`, `test_point_in_time_truncate_recompute_identical`, `test_backfilled_flag_excludable`, `test_sources_row_shows_reason_code`, `test_rotation_three_points_scores`, `test_rotation_fewer_than_three_points_is_missing`, `test_rotation_lag_uses_x_rotation_max_lag_days`, `test_other_sources_keep_seven_day_window`, `test_window_mode_reproduces_current_x_behaviour`, `test_rotation_point_in_time_truncate_identical`; plus `test_shipped_config_selects_web_methods_and_rotation`.
- CI (PR #193), first run on the report commit: `web` pass; `api — pytest` FAILED with 1 failed, 2948 passed: `api/tests/routers/test_discovery.py::test_sources_route_shape_and_no_network` asserts the exact Sources row key set, and the 2 new model fields broke it. Fixed in a follow-up commit (heading 8 item 8); the CI result of that commit is in the worker's final message.

## 7 Tests NOT run

- Full `api/tests` on Linux (CI is the judge); router tests on this host fail on main for the event-loop reason.
- No live data: nothing was run against a real PC store; the X rotation behaviour is proven only on fixtures.

## 8 Deviations

1. Absent `x_discovery_mode` means `window` in code (configs that predate W8f, including every existing test fixture); the shipped `discovery.json` sets `rotation`, so production X uses rotation as the SPEC says. Making the code default `rotation` would have changed existing tests' X results.
2. PC stores (`xsearch_web`, `reddit_web`, `reddit_stream`) skip the probe-record gate in `registry.read_series`: `record_probe.py` can only record `registry.FETCHERS` sources, so without this the selected web stores could never score. A stored file is taken as the evidence that the worker ran on the owner's host. Owner/planner decision to confirm.
3. "X points older than `x_rotation_max_lag_days` drop out" (AC23) is implemented as the T96 rule (rule 9): the newest of the 3 points must be within the lag; older points inside the latest 3 still count. If the owner meant every one of the 3 points must be within 7 days, `_rotation_change` needs a filter before taking the latest 3.
4. `known_at_time` drops a point whose evidence row is `backfilled` OR has `collected_at` later than D+1 (Annex B "known at D+1"). Today no collector passes `backfilled=True` to `web_evidence.commit_day`, so the `collected_at` rule is what actually separates backfill on real data.
5. `source_impl` with a list implements AC14's `reddit_impl_order` as part of `source_impl` (no separate `reddit_impl_order` key); the "first method with enough points" is the first store that yields a change for that coin and window.
6. Two red tests were corrected after the red commit (test bugs, not behaviour changes): `test_backfilled_flag_excludable` marked the newest recent day, which correctly re-anchors the window, so it now marks an inner recent day; the `test_sources_row_shows_reason_code` fixture took weights v1 (END is before the v3 cut-over) and now takes the shipped current weights.
7. The `x_*` keys live in `discovery.json` (where discovery validation is), not in `attention_queries.json` (open PR #191 untouched).
8. `api/tests/routers/test_discovery.py` is outside the envelope's file list: its exact-key contract for a Sources row had to gain `reason` and `impl`, the 2 fields the PLAN's "reason codes on the Sources row" needs. One line; nothing else in that file changed.

## 9 Blockers

None. Unproven: discovery history (`discovery_history.py`, not in the file list) still gates every series by `min_history_days` per day through `_Stored.at`, which returns no points below the gate, so X in rotation mode appears on history charts only once a coin has `min_history_days` (30) X points; live scoring, signal snapshots and the Sources row use the 3-point rule. Needs a follow-up slice to pass the rotation gate into `_Stored`.

## 10 Follow-up

- Planner: confirm deviations 2 and 3; dispatch the `discovery_history.py` rotation gate (heading 9); W8g shows `reason`/`impl` in the web Sources text (`web/lib/types/discovery.ts` not touched here).
- Collectors should pass `backfilled=True` for backfill units (W8e worker `_pass` and `reddit_web`), so the flag carries meaning beyond the `collected_at` rule.
- Request `accepted` and `archived` after CI green and planner review; this worker does not merge.

## 11 Context cost

About 110k tokens. Tools: read, bash, edit, write, grep; no subagents.
