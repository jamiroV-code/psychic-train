# Sources health stale fix report: a source waiting on purpose no longer reads stale

## 1 Task ID
Health-line stale false alarm after the daily budget is spent (owner-approved EXECUTE, 01-11-26), found in a real 4-hour X run. SPEC `narrative-baskets-xreddit-collector_SPEC_21-10-26.md` AC39. Branch `claude/health-stale-after-budget`, draft PR (number in 10).

## 2 Outcome
review. Code and tests are done, and the draft PR is open. CI result: see 6 and 10.

## 3 Summary
The defect: once X had spent its day budget (used 792 of 800, `spent_day` = today, not paused), the worker correctly waited for the next UTC day. During that wait the Sources health row showed `stale: true` and the completeness text ended "; stale". The cause was `_health` in `api/analytics/attention/sources.py`. It judged stale as `last_unit_at` older than 2 x `expected_gap_s`, and `expected_gap_s` is the in-day pace (360 s degraded) even while the source is waiting on purpose.

What changed (reader only, no worker change):
- New `_idle_until(state)` reads the persisted worker state. It returns when a by-design wait ends:
  - **Budget spent:** `spent_day`, or `budget_day` when `used >= effective`, gives 00:00 UTC of the next day + `pc_pace.BEHIND_DELAY_S` (20 s). This is the same time the worker schedules (`attention_pc_refresh._next_day`).
  - **Timed pause:** a pause with a non-owner-action reason ends at its persisted `pause_until`.
  - If both apply, it takes the later end. An owner-action pause (`pause_until` null) has no end and returns None.
- Stale now counts the gap from the later of `last_unit_at` and that wait end: `now - max(last_unit_at, idle_until) > 2 x expected_gap_s`. This gives:
  - While waiting, the row is not stale.
  - After the wait end + 2 x gap with no new unit, it is stale again.
  - With no by-design wait, nothing changes: a stuck source is still stale, and so is a source that never ran a unit.
  - An owner-action pause keeps today's rule.
- The completeness text no longer ends "; stale" while waiting. Instead it ends "; waiting for next UTC day" until the wait end. `completeness` is an existing string field, so the web contract is unchanged (`web/lib/source-health.ts` only interpolates it).
- Rows with no worker state are unchanged (no `health` key).
- The `stale` field comment in `api/models/discovery.py` now describes the rule. No field was added.

## 4 Files changed
- api/analytics/attention/sources.py
- api/models/discovery.py (comment only)
- api/tests/analytics/attention/test_sources_health.py
- this report

`api/data/attention_queries.json` (the owner's local edit) was never staged. `git diff --name-only origin/main...HEAD` does not list it.

## 5 Commits
1. `6342693c` test(sources): red - idle-by-design (budget spent, timed pause) must not read stale
2. `90af59b0` fix(sources): budget-spent / timed-pause wait is not stale; gap counts from the wait's end
3. report commit

## 6 Tests run
- **Red at commit 1:** in `test_sources_health.py`, 3 failed and 15 passed.
  - The 3 that failed reproduce the defect: `test_budget_spent_idle_until_next_day_is_not_stale` (stale at 12:00 while budget spent), `test_future_pause_until_idle_is_not_stale` and `test_completeness_text_has_no_stale_suffix_when_waiting_by_design` (text ended "; stale").
  - Four new tests passed at red: `test_budget_spent_stale_again_after_next_due_plus_two_gaps`, `test_owner_action_pause_keeps_existing_stale_rule`, `test_stuck_source_without_budget_spent_is_still_stale` and `test_rows_without_worker_state_unchanged`. They guard behaviour that must stay the same after the fix.
- **Green:** `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention/test_sources_health.py`: 18 passed.
- **Acceptance run** (`api/tests/analytics/attention api/tests/data/attention api/tests/tooling_guards api/tests/data/test_attention_pc_refresh.py`): 1502 passed, 1 skipped, 2 failed.
  - `test_universe_classes.py::test_discovery_end_to_end_on_fixture` is the known Windows-only failure ("handler must not reach the network").
  - `test_twscrape_reader.py::test_accounts_db_path_outside_repo_required` fails only because of the owner's uncommitted `attention_queries.json` (its account path). With that file stashed, it passes (1 passed).
- **Replaced tests:** none. Every existing test passed unchanged. `test_stale_after_twice_the_expected_gap` and `test_paused_source_shows_reason_code_and_end` cover states that are not by-design waits, or do not assert stale.
- **CI on Linux:** see 10.

## 7 Tests NOT run
- Web vitest and tsc: no web file changed, and the field set is unchanged.
- `api/tests/routers`: known Windows-only failures; CI is the judge.
- No live run, as instructed.

## 8 Deviations
- **No worker-side change.** The next due time is derived in the reader from the already-persisted `spent_day`, `budget_day`, `used`, `effective` and `pause_until`, together with `pc_pace.BEHIND_DELAY_S`. `api/data/attention_pc_refresh.py` and its tests are untouched.
- **Timed pause end:** following the contract, it is `pause_until` itself, not `pause_until` + 20 s. The worker actually resumes 20 s later (`_next_day`). That difference is far below 2 x gap.
- **Wait note:** "; waiting for next UTC day" is also shown during a timed warning pause. `pc_pace.warn` always sets `pause_until` to the next UTC day's 00:00, so the note is accurate there too.

## 9 Blockers
None.

## 10 Follow-up
- **SPEC AC39 wording:** it still reads "more than 2 x the expected gap". A one-line amendment ("counted from the end of a by-design wait: budget spent or timed pause") would match the code. It was not edited here because the SPEC was outside this envelope's file list.
- **Draft PR and CI:** the PR number and the final `gh pr checks` result are in the worker's hand-off message.

## 11 Context and cost
Single worker pass. I read `sources.py`, `test_sources_health.py`, the pace state code in `pc_pace.py` (roll, spend, warn, pause) and the scheduling lines in `attention_pc_refresh.py`. I also read the `DiscoverySourceHealth` model, the web formatter lines, and one earlier report for the template. Local runs: about 10 s for the health file and about 6.5 minutes for the acceptance set.
