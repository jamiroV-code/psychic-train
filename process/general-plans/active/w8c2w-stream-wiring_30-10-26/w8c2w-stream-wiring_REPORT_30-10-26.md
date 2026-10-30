# W8c2w report: Reddit stream wiring PLAN (PLAN-REV 3, plan fixes round 2)

## 1 Task ID

T222 (ID free: T221 is the highest in `git log --all` subjects and PR titles; no T222 anywhere; W8c2 PRs have no T id), slice W8c2w. Phase PLAN only (RIPER-5), agent riper-sonnet, direct lane. Branch `claude/w8c2w-stream-wiring-plan` (PR #200, draft). Plan: `w8c2w-stream-wiring_PLAN_30-10-26.md` in this folder. This report covers the original plan, round 1 (owner decisions Q1-Q9) and round 2 (second independent review of PR #200 and the owner decision of the share default).

## 2 Outcome

done (plan revised to PLAN-REV 3 and re-validated; nothing implemented; all owner questions Q1-Q9 decided, none open)

## 3 Summary

Round 2 changes:

- Fix 1 (blocking, W11): ONE authoritative request-count path. Every stream request passes through `share_src.spend(n)` (`run_poll` calls `src.spend(1)` immediately before each request it sends). The wrapper writes the stream's day count (`reddit_stream/_meta/_budget/<day>.json`) BEFORE it delegates to the shared `src.spend`, restores it if the delegate raises, and is the only writer. The sum of `PollOutcome.requests` is no longer a counter (it would double count with `spend`); tests use it only as a cross-check. The shared `reddit_web` counter stays the authority. Why not the preferred "derive from poll records": checked on the #198 head (`403bc676`, `reddit_stream.py`, `run_poll` and `Poll`): NOT every sent request is recorded. `Poll` has no `requests` field; `Poll.pages` counts only pages that made progress; a poll whose requests all fail stores no `Poll`; an empty feed stores `pages=0` for one request; a poll whose second page fails stores `pages=1` for two requests; an unexpected exception leaves `run_poll` after `spend(1)` with no `PollOutcome`. `PollOutcome.requests` is complete on every normal return (a failed request included, no retry), but misses the exception path. A failed request therefore counts exactly once, through `spend`.
- Fix 1 tests (red-first, section 4 row "One counting path"): `test_stream_counter_equals_requests_sent_no_double_count`, `test_stream_counter_counts_failed_empty_and_dead_cursor_requests_that_poll_records_miss`, `test_stream_counter_after_restart_continues_from_file_no_double_count`, `test_failed_request_counts_once`, `test_unexpected_exception_in_poll_still_counts_its_request_once`, `test_spend_refused_by_shared_budget_does_not_increment_stream_counter`. P-S3 now also reads the `_budget` count.
- Fix 2 (owner decision): default `reddit_stream_budget_share` = 0.45 everywhere (W4, W11, section 2 arithmetic, owned-file table, tests, risks, probes, W-AC6, W-AC9, Public Contracts, Q1, envelope DECIDED paragraph, G8 grep). BASELINE cap 112 of 250 (searches keep 138), DEGRADED cap 67 of 150 (searches keep 83, covering the 76 needed with 7 to spare). Tradeoff stated as an expected consequence: in BASELINE a day near the stream bound (124-132) hits the cap at 112; polls after it are truncated and continue at the first poll after 00:00 UTC, nothing dropped; the stream series may lag or show that day missing or partial under the E1 rule, never 0 (whether the continuation can still cover the tail is UNVERIFIED until P-S3). New tests: `test_stream_cap_is_112_baseline_and_67_degraded_at_default_share`, `test_baseline_cap_reached_mid_day_truncates_remaining_polls_next_utc_day_continues_nothing_dropped`, `test_cap_truncated_day_is_missing_or_partial_never_zero`; renamed `test_budget_share_default_is_0_45` and `test_degraded_stream_requests_never_exceed_67_at_default_share`.
- Fix 3 (reporting gap, new W12 and W9 text): the same day file records `share_exhausted` with `cap`, `budget`, `requests` and `exhausted_at`, set only when the share (not the shared budget) refused a request. The Sources text says `share_exhausted (cap C, requests counted N)` for that day, distinct from `no entry observed, unknown`; an absent completeness file is never evidence of exhaustion; missing is never 0. Tests: `test_share_exhausted_recorded_with_cap_and_count_distinct_from_no_entry`, `test_share_exhausted_not_set_when_shared_budget_is_the_reason`, `test_sources_text_share_exhausted_names_cap_and_count_not_unknown`, `test_sources_text_no_entry_and_no_exhaustion_says_no_entry_observed_unknown`, `test_share_exhausted_day_without_completeness_file_is_missing_never_zero`.
- Fix 4 (G8): the gate now runs the named switch tests (`pytest -k` of four names: exact-1 semantics, unset means off, off by default, env off sends zero requests and writes no files), requires exit 0 and at least 4 passed (a missing or renamed name makes the selection short and fails), in addition to the greps (variable present, absent from conftest and workflows) and the share key `0.45` grep. The four names are also in the G4 required list.
- Fix 5: stated as VERIFIED 30-10-26 in the plan: `git ls-tree -r origin/claude/w8c2-reddit-stream` shows 0 matches for `api/data/attention_pc_refresh.py` (the file arrives with `main`).
- Fix 6: envelope 5,689 B (`wc -c`, cap 8,000), first line `ROLE: WORKER`; marker `PLAN-REV: 3` (plain text outside the fence) with the envelope check and the handoff text updated; 84 named red-first tests (was 69); strict validator 0 failures, 0 warnings.

## 4 Files changed

- `process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_PLAN_30-10-26.md` (revised)
- `process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_REPORT_30-10-26.md` (this file)

## 5 Commits

One new commit on `claude/w8c2w-stream-wiring-plan` on top of `f50e3c24`, plain push (no force) to the existing branch, updating PR #200; hash in the worker's final message.

## 6 Tests run

No product tests (plan only). Run, 30-10-26:

- Strict plan validator `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs --strict <plan>`: 0 failures, 0 warnings.
- `bash -n` of the extracted Validate Contract (extraction with `tr -d '\r'`, as the envelope does): OK, 78 lines.
- Envelope measured with `wc -c` on the text between the four-backtick fences: 5,689 B (cap 8,000).
- Dry run of the contract on `origin/main` (`BASE=origin/main`, temporary worktree, `REPO` exported from the remote on the command line only): exit 1. FAIL: G0 (#198 not merged), G1 (empty change set), G4 (test file and all required names missing, 0 of 50 tests), G5 (no EXEC-REPORT), G6 (pytest exit 4: test file missing), G7 (no BASEFAIL file; the pytest part itself ran and collected on `main`), G8 (switch, env-switch tests exit 4 and 0 passed, share key and `PC_STORES` missing), G10 (#198 touches three owned files). PASS: G2, G3, G9. This is the expected pre-EXECUTE pattern (G0, G1, G4-G8, G10 fail, G2, G3, G9 pass; G5 and G6 also fail because the EXEC-REPORT and the test file do not exist yet).
- Temporary worktree: `git worktree remove` failed with Invalid argument on Windows; handled with `rm -rf` and `git worktree prune`.
- Read-only inspection of the #198 head (`git show`, `git ls-tree`) for fix 1 and fix 5.

## 7 Tests NOT run

- Every test of the plan's section 4 (they do not exist yet).
- Validate Contract passing paths of G4-G10 (need the EXECUTE tree), including the new G8 test selection.
- All owner probes P-S1 to P-S5 (live behaviour, owner's machine).

## 8 Deviations

1. The review's preferred path for fix 1 (derive the count from persisted poll records) is NOT adopted, because the #198 code does not record every sent request (facts in section 3). The minimal counter that is complete is the wrapper's `spend` write-through, specified in W11.
2. The gate G8 now runs pytest (small named selection) rather than only grepping; it adds a few seconds and needs the stream test file.
3. The share counter and the `share_exhausted` record are one small day file under `reddit_stream/_meta/_budget/` written by the worker (the shared `PcSource` has no per-caller counter); it is a cap and a report, not a second budget state.
4. The shared worktree held copied parent changes at the start; they were stashed in a named stash (`parent-copy-t222b`) in the isolated checkout and not touched. `origin` was added in that checkout for publication, never written to a file.

## 9 Blockers

None for this plan. EXECUTE is blocked on: #198 merged, this plan PR merged, Main filling the three envelope values.

## 10 Follow-up

- After EXECUTE the owner runs P-S1 to P-S5; P-S3 reports the real stream spend (`used`, `_budget` count, poll pages), which decides whether 0.45 stays.
- Proposed owner-decision line for a later docs task (Q4): "SPEC AC14 waiver: one method per coin series and window is accepted; Discovery takes the first store of `source_impl.reddit` that yields a change for the coin and window; `reddit_impl_order` and `source_impl.reddit` stay two copies guarded by a consistency test." Not part of the EXECUTE slice.
- Not in this slice: a second health line for the stream on the Sources row (Q3), window-level method choice, engagement enrichment (W8c3).

## 11 Context and cost

Read: the plan, the report, `reddit_stream.py` of the #198 head (`Poll`, `PollOutcome`, `run_poll`, `run_due`), `pc_pace.py` on `main` (`PcSource.spend`, `_save`), `git ls-tree` of the #198 branch. The gate dry run took about 140 s. No model spend figure is measured here (UNVERIFIED).
