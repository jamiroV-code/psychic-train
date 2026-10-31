# X unclean-stop lock fix report: the library's in-flight lock no longer costs a UTC day

## 1 Task ID
X unclean-stop lock fix (owner-approved EXECUTE, 31-10-26), from the owner's kill-and-restart test of the X worker. SPEC `narrative-baskets-xreddit-collector_SPEC_21-10-26.md` rule 18 (d)(k), AC40, AC46, AC49, AC52. Branch `claude/x-unclean-stop-lock`, draft PR #201.

## 2 Outcome
review. The code, the tests, the SPEC amendment and the draft PR are done. CI on Linux passed for the first push. The fix has not been tried on the owner's PC with the real library (see 7 and 10).

## 3 Summary
The defect, as the owner reported it: a hard kill during a request leaves twscrape's in-flight lock (`accounts.locks.SearchTimeline` = take time + 15 min). After a restart inside that window, `no_account_cause` read any future lock as a rate limit. `_account_failure` then day-locked acct1, restarted the unit on acct2, and day-locked acct2 too. X paused with `no_usable_account` until 00:00 UTC.

What changed:
- `x_reader.no_account_cause(row, now, *, rate_limit_evidence)` (the keyword is required). An active row with a future search lock counts as `locked`/`rate_limited` only in these cases:
  - our side recorded rate-limit evidence;
  - the row carries code 88;
  - the lock lasts longer than an in-flight lock can (15 min + 1 min slack).
  
  Without any of these, the lock is `waiting`/`in_flight_lock`. New helpers: `near_rate_limit`, `search_lock`, and the constants `IN_FLIGHT_LOCK`, `IN_FLIGHT_SLACK`, `IN_FLIGHT_REASON`, `RATE_LIMIT_CODE`, `RATE_LIMIT_STATUS`, `RATE_LIMIT_NEAR`.
- `x_pool`:
  - Evidence comes from three places: `failure.status == 429`; code 88 on an active row; or `x-rate-limit-remaining <= 1` on that account's last page within 15 minutes. The last one is kept per account as `rate_limit_seen` in `x_pool.json`. Older state files load: the missing key is added as None.
  - `_account_failure` returns `wait` for a bare lock. `wait_for_lock` then marks the account `locked` with reason `in_flight_lock` until the library's lock end + `LOCK_MARGIN_S` (30 s). The library file is never written: no `reset_locks`, no unlock, no lock rewrite.
  - With no usable account, `pause_no_account` pauses until the earliest in-flight lock end (pause reason `in_flight_lock`, `resume_at()`). Only when no account is waiting does it fall back to the old `no_usable_account` day pause.
  - A unit whose last attempt hit a bare lock ends with `in_flight_lock`, not `account_failed`. Failover to an unlocked account is unchanged. `health()` now carries `pause_until`.
  - If an account in the canary met a bare lock, the canary does not pass on the other account alone. It pauses until the lock ends, does not mark anyone canaried, and runs again on both.
  - Every request is stamped with `src.stamp_attempt()` before `search_raw` (unit pages and canary). A request killed in flight therefore still counts for the minimum spacing after a restart.
- `attention_pc_refresh`:
  - For an in-flight lock wait, the X pass returns the new outcome `account_wait` (not `paused`).
  - `Stream._behind` gains a `_resume_at` hook. XStream uses it to schedule at `pool.resume_at()` instead of 00:00 + 20 s.
  - `_held` no longer treats the wait as a day hold.
  - A pass that starts early folds the resume time into its due time instead of returning at once (no 20 s busy loop).
- Rule 18 inactive handling (88 with remaining above 0, 326, 32, bare 403 mark that account inactive with an alert) is unchanged. Day locks with evidence work as before.

## 4 Files changed
- api/data/attention/x_reader.py
- api/data/attention/x_pool.py
- api/data/attention_pc_refresh.py
- api/tests/data/attention/test_x_reader.py
- api/tests/data/attention/test_twscrape_reader.py
- api/tests/data/test_attention_pc_refresh.py
- process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-xreddit-collector_SPEC_21-10-26.md (rule 18 (d)(k), AC40, AC46, AC52 and their proven-by lines, change-log row 31-10-26)
- this report

`api/data/attention_queries.json` (the owner's local edit) was never staged. `git diff --name-only origin/main...HEAD` does not list it.

## 5 Commits
1. `3d15334f` test(x): red tests for the unclean-stop in-flight lock escalating to a UTC-day lock
2. `b58cc6aa` fix(x): wait out the library's in-flight lock after an unclean stop instead of a UTC-day lock; stamp before each request
3. `f2160b7b` test(x): two-account wait test shares the canary page so the canary agrees
4. `d18fb9f5` docs(spec): rule 18, AC40/46/52 and change log for the in-flight lock fix
5. `48fa0639` test(x): red test: a canary with one bare-locked account must run again after the lock, not pass alone
6. `3a4ebfb3` fix(x): a canary that met a bare in-flight lock runs again after the lock instead of passing on the other account alone
7. `b34f92f1` docs(spec): rule 18 (k) canary rerun after an in-flight lock
8. report commit

## 6 Tests run
- **Red at commit 1:** on the new and changed tests, 26 failed and 6 passed. The kill-at-every-tick test failed with outcome `paused` at all 14 ticks, which reproduces the owner's defect. The 6 that passed are the four rate-limit-evidence cases plus two replaced tests that now give evidence; they guard behaviour that must stay the same. The canary-rerun test was red at commit 5: the canary passed on one account.
- **Green:** `UV_FROZEN=1 uv run --project api pytest` on `test_x_reader.py`, `test_twscrape_reader.py` and `test_attention_pc_refresh.py`: all passed except `test_twscrape_reader.py::test_accounts_db_path_outside_repo_required`. That test fails only because of the owner's uncommitted local `attention_queries.json` (its account path). With that file stashed, it passes.
- **Acceptance runs** with the local file stashed: `api/tests/data/attention api/tests/tooling_guards api/tests/data/test_attention_pc_refresh.py api/tests/analytics/attention`. After commit 4: 1477 passed, 1 skipped, 1 failed. Final run after commit 7: 1478 passed, 1 skipped, 1 failed. Both times the failure is `test_universe_classes.py::test_discovery_end_to_end_on_fixture` ("handler must not reach the network"), the known Windows-only failure, not mine.
- **New tests** (names as asked):
  - test_x_reader.py: `test_bare_library_lock_does_not_day_lock_account`, `test_bare_lock_unit_waits_for_lock_end_and_resumes`, `test_real_rate_limit_evidence_still_day_locks_account[code_88|http_429|remaining_0|remaining_persisted]`, `test_failover_uses_unlocked_account_when_other_has_bare_lock`, `test_both_accounts_bare_locked_pass_retries_after_lock_end_not_next_day` (pool level), `test_canary_on_bare_locked_accounts_waits_for_lock_end`, `test_canary_with_one_bare_locked_account_runs_again_after_lock_end`, `test_attempt_stamped_before_each_request`.
  - test_attention_pc_refresh.py: `test_attempt_stamped_before_request_so_killed_request_counts_for_spacing`, `test_health_shows_transient_pause_with_real_end` (also checks the Sources health payload), `test_both_accounts_bare_locked_pass_retries_after_lock_end_not_next_day` (worker level, two accounts), `test_kill_at_every_tick_never_pauses_a_utc_day[0..13]`.
  - The kill-at-every-tick test uses a fake reader shaped like the library. A request takes a 15-minute lock and releases it on return; a kill leaves the lock. While the lock is in the future, the reader raises `no_account` and its pool row shows a bare, active lock. The test kills at each of 14 ticks: canary plus 3 coins x 2 pages, each request either in flight or served but not yet returned. It then restarts and drives passes at the times `schedule` gives. It checks:
    - no `lock_for_day` call, no `paused` outcome, and every due time before midnight;
    - no request inside the lock window;
    - one stored point and one X evidence row per coin-day;
    - completeness attempted == fetched == 3 with 0 missing;
    - budget used == entries that reached our side (the aborted unit's returned pages counted once, the killed page not at all).
- **Replaced tests** (changed on purpose):
  - `test_x_reader.py::test_noaccounterror_cause_read_from_pool_row`: the new required keyword. A bare lock is now `("waiting", "in_flight_lock")`. Added the 88-on-active-row and longer-than-in-flight cases.
  - `test_x_reader.py::test_rate_limit_lock_ends_at_day_boundary_not_inactive`: it used a bare lock as the day-lock trigger, which is exactly the defect. It now raises `no_account` with status 429 (evidence). The day-boundary assertions are unchanged.
  - `test_x_reader.py::test_second_failure_gives_account_failed_missing`: two bare locks are now a wait, not a failure, so both failures carry 429 evidence. This keeps the test's meaning: a second real failure leaves the coin-day `account_failed`.
  - `test_twscrape_reader.py::test_noaccounterror_cause_read_from_pool_row_inactive_locked_active_error`: the new keyword, with both lock branches through the wrapper's real `pool_row()`.
  - `test_twscrape_reader.py::test_all_accounts_locked_pauses_day` → `test_all_accounts_bare_locked_wait_for_lock_end_not_day`: it asserted the observed bug (two bare 14-minute locks gave a `no_usable_account` day pause). It now asserts `in_flight_lock` until lock end + 30 s, both accounts usable afterwards, and no reset, unlock or lock call on the library.
- **CI on Linux:** for commit `d18fb9f5`, both checks passed: `api — pytest` (4m5s) and `web — vitest, tsc, island build` (56s), run 41203766206. The final head's result is in 10.

## 7 Tests NOT run
- No run against the real library or X. A second kill-and-restart test on the owner's PC is the real proof; see 10.
- No new test for a lock held across pages: the fake releases it per page. The library holds it for the whole generator, but our classification only depends on the lock row seen at restart.

## 8 Deviations
- **Code fact, rule number:** the contract says the "rule 20 lock handling sentence". The lock handling actually lives in rule 18 (d) and (k), plus AC46 and AC52; rule 20 has no lock sentence. Rule 18 was amended and rule 20 was left untouched.
- **Code fact, what "rate-limit evidence" can be on our side:** at the pinned commit, `queue_client._check_rep` handles all three signals itself:
  - a response with `x-rate-limit-remaining == 0` and a reset is locked until `x-rate-limit-reset` and raises `HandledError`, so our wrapper only sees `NoAccountError`;
  - code 88 with remaining above 0 marks the account inactive;
  - a 429 is handled the same way.
  
  So on the default path our side never sees 0, 88 or 429 directly. The evidence that is actually reachable is the last page's `x-rate-limit-remaining` at 1 or below (the next request reaches 0), within 15 minutes, persisted. The 429 status and 88-on-active-row checks are implemented as the contract asks. [INFERENCE] With the current wrapper they are not reachable in production: `map_exception` sets no status on `no_account`, and the library sets no `error_msg` on an active, locked row.
- **Residual weakness of that evidence rule:** the library's own retries can use up several requests inside one page. A real rate limit reached from a last-seen remaining above 1 is then treated as an in-flight lock. In that case X waits until the library's lock end, which for a real rate limit is X's own reset time, instead of locking the account for the UTC day. That is weaker than rule 18 (e) in that one corner, but X is never retried before X's reset.
- **Added beyond the contract:** a lock longer than 16 minutes is treated as a rate limit, because no in-flight lock lasts that long. This keeps the conservative path.
- **Added beyond the listed tests, after review:** with two accounts, a kill during the canary left acct1 waiting. The canary then passed on acct2 alone, so acct1's units for the rest of the day would have been read but stored as missing (`account_not_canaried`). That is also a day of lost value for one account. The canary now pauses until the lock ends and runs again on both (commits 5-7, red first).
- **Test fix after the red commit:** the worker-level two-account test gave each account different canary ids. The canary came out inconclusive and paused for the day (a test artefact; the `day_locks` spy caught it). The two readers now share the canary page.

## 9 Blockers
None.

## 10 Follow-up
- **Owner probe:** repeat the kill-and-restart test on the PC. Kill the worker during a unit, restart within 15 minutes, then check:
  - `x_pool.json`: the killed account has `lock_until` = library lock + 30 s and `reason` `in_flight_lock`;
  - `pause_reason` is `in_flight_lock` only when no account is usable;
  - X resumes after that time, not at 00:00 UTC.
- CI on the final head (commits 5-8) finished after this report was written. Its result is in PR #201 and in the worker's hand-off message.
- The local `x_pool.json` on the owner's PC still holds the day locks from the 30-10-26 test until 00:00 UTC on 31-10-26. They lapse by themselves; nothing in this change edits them.

## 11 Context and cost
Single worker pass. I read the named files, the twscrape pinned `queue_client.py` (library lock and rate-limit handling), the SPEC rule 18 and the AC lines, plus one existing report for the template. Local test runs: about 4 minutes per file group and about 7 minutes for the acceptance set.
