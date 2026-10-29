---
name: report:narrative-baskets-xreddit-collector-w8c2
description: "W8c2 EXECUTE report: Reddit stream-and-count (comments and posts feeds, method reddit_stream)."
date: 29-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# W8c2 EXECUTE report (29-10-26)

## 1 Task ID

W8c2: Reddit stream-and-count complement, including comments feeds (PLAN `narrative-baskets-xreddit-collector_PLAN_21-10-26.md`, slice row 3b, section W8c2). Branch `claude/w8c2-reddit-stream`. Worker: riper-opus, RT2.

## 2 Outcome

done

## 3 Summary

- New `api/data/attention/reddit_stream.py`: method `reddit_stream` (source `reddit_stream`, method id `reddit_stream_feeds_v1`), stored apart from `reddit_web`.
- It polls one combined `comments/.rss` feed and one combined `new/.rss` feed over the stream subreddit set (default: the existing 12-name `subreddits` list). Comments are polled every 7200 s and posts every 21600 s, with at most 12 polls per kind per UTC day. Every request uses W8c's fetcher and parser, the honest user agent, the pause rules (403, 429, block page) and the one shared Reddit budget and pacing state.
- Duplicate entries are removed by id across polls and feeds. Comment items enter the ledger with their `t1_` id and author hash. Comments paging with `after=t1_...` is on by default, limited by the gap to the previous poll and by the daily budget.
- Coverage comes from entry timestamps (the union of [oldest, newest] per kind). A day is stored only when it is complete, both kinds are settled, and both kinds reach coverage 0.80. Below 1 the day is flagged `partial`; otherwise it is MISSING (`below_coverage` or `not_settled`), never 0.
- A completeness file is written per source-day. `pick_impl` uses `reddit_impl_order` and picks exactly one method per window.
- Config keys were added to `attention_queries.json`, with validation in `web_queries.py` (owner-approved scope addition). The probe now has `--source reddit --stream-status`, which reads local state only.

## 4 Files changed

- `api/data/attention/reddit_stream.py` (new)
- `api/tests/data/attention/test_reddit_stream.py` (new, 46 test cases including parametrised ones)
- `api/data/attention_queries.json`: 7 keys added to `collector` (lines 22-28): `reddit_stream_subreddits` null, `reddit_comments_poll_interval_s` 7200, `reddit_posts_poll_interval_s` 21600, `reddit_stream_polls_per_day_cap` 12, `reddit_stream_min_coverage` 0.8, `reddit_comments_paging` true, `reddit_impl_order` ["reddit_stream", "reddit_web"]
- `api/data/attention/web_queries.py` (owner-approved addition; `git diff -U0 origin/main` hunks):
  - `@@ -76,0 +77,12 @@`: `REDDIT_STREAM_DEFAULTS` and `REDDIT_METHODS`
  - `@@ -78 +90 @@`: `DEFAULTS` merge now also includes `REDDIT_STREAM_DEFAULTS`
  - `@@ -133,0 +146,7 @@`: 7 `CollectorConfig` fields
  - `@@ -176,0 +196,15 @@`: `_stream_value` typed validator
  - `@@ -186 +220,4 @@`: stream defaults are merged and every stream key is validated
  - `@@ -199 +236,5 @@`: `reddit_impl_order` is converted to a tuple, and a list `reddit_stream_subreddits` too
  - `@@ -298,0 +340,5 @@`: `stream_subreddits(q)`

  No existing validation was removed.
- `api/tests/data/attention/test_web_queries.py`: 4 tests added (one parametrised with 16 invalid cases); nothing else changed.
- `api/scripts/probe_pc_sources.py`: `--stream-status` mode (`stream_status()`); docstring updated. With no mode, `--source reddit` now says "choose --feed-depth, --compare-scope or --stream-status" instead of "not built yet (W8c2)".
- `api/tests/scripts/test_probe_pc_sources.py`: `test_reddit_stream_status_reads_local_state_only` added. In `test_modes_not_built_in_w8b_exit_2_without_network`, line 37 now calls `--source reddit` with no mode (still exit 2) instead of `--stream-status`, which is built now. The test was not weakened: the X call and the "not built yet" assertion stay.
- Guard test file lists: NOT changed. `test_reddit_collector_guards.py` already lists `reddit_stream.py` in `REDDIT_FILES` and `HTTP_ALLOWED`.

## 5 Commits

- `dbbb2c97dca0b6f72c0e4564825ec88b89574df4`: W8c2 code, tests and config
- the commit that adds this report (SHA in the PR)

## 6 Tests run

- Baseline before any change, `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention -q`, 2026-10-29 about 22:22Z: 775 passed, 1 skipped. The 3 failures were my own new red `test_web_queries` tests, added while the run was starting. No baseline failure is attributable to existing code.
- Red evidence, 2026-10-29T22:25:39Z, base 4b3f70a9:
  - `test_reddit_stream.py` failed at collection with `ImportError: cannot import name 'reddit_stream'`.
  - `test_web_queries.py` plus `test_probe_pc_sources.py`: 4 failed, 38 passed. The failures were `CollectorConfig` having no `reddit_stream_subreddits`, no `REDDIT_STREAM_DEFAULTS`, no `stream_subreddits`, and the probe `ImportError`.
  - The parametrised invalid-value cases passed while red only because the old validator rejects unknown keys with a message naming the key. They pass now through the typed validator.
- Green, all files:
  - `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/tooling_guards api/tests/scripts -q`, 2026-10-29T22:30:26Z to 22:34:28Z: 1595 passed, 1 skipped, 0 failed. This covers the attention suite, the guard tests and the scripts suite.
- Green after the final edits (a reason renamed to `zero_not_stored` for the banned-word gate, and an unused import removed):
  - `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_reddit_stream.py api/tests/data/attention/test_web_queries.py api/tests/data/attention/test_reddit_web.py api/tests/tooling_guards api/tests/scripts/test_probe_pc_sources.py -q`, 2026-10-29T22:34:47Z: 270 passed, 0 failed. This ran on the code committed as `dbbb2c9`.
- File-set check: `git diff --name-only origin/main...HEAD` lists exactly the 7 owned files above (plus this report).
- Hygiene: grep of all changed files for secrets, the repo slug, user paths, TODO and FIXME: no hits. The banned verdict-word grep (bullish, bearish, signal strength, confidence, triggered, confirmed, trust weight) had one hit, `zero_unconfirmed`; it was renamed to `zero_not_stored`, and the grep then found nothing in new code.

## 7 Tests NOT run

- Owner probe `python -m api.scripts.probe_pc_sources --source reddit --stream-status`: not run here (owner machine only; this sandbox has no provider access, and nothing live was called).
- No linter: `ruff` and `pyflakes` are not installed in the project environment. Unused imports were checked by grep instead.

## 8 Deviations

1. Owner-approved scope addition (relayed by the planner on 29-10-26): `web_queries.py` and `test_web_queries.py` were added to the owned set. Changes there are additions only, for the new keys. Without them the loader would reject any new key.
2. Combined feeds: the stream polls ONE multi-subreddit feed per kind (`/r/A+B+.../comments/.rss`, `/new/.rss`), not one feed per subreddit. With the owner's 12 subreddits, per-subreddit polling would cost 12 x (12 comments + 4 posts) = 192 requests a day. Together with about 76 M1 searches plus the canary, that is over the shared 250 budget. Combined feeds cost 16 a day plus paging. The SPEC's "mean over the configured feeds" therefore becomes coverage per feed kind.
3. PLAN test `test_stream_feed_count_must_be_4_to_6` was replaced by `test_stream_subreddit_set_is_top_level_list_in_one_combined_feed_url` (owner delta 1: 12 names, by reference).
4. `reddit_stream_polls_per_day_cap` defaults to 12, not 6: the 7200 s comments cadence needs 12 polls a day (AC37).
5. Default `reddit_impl_order` is `["reddit_stream", "reddit_web"]`, per the PLAN W8c2 text ("so a day without comment coverage falls back to the posts-only series"). SPEC AC14 says the default is `reddit_web`, `reddit_stream`. I followed the PLAN; the order is config either way.
6. Settling rule (added for correctness): a complete day is stored only once each kind is settled, meaning its coverage is 1 or a later poll's oldest entry is after D. Otherwise an undercount could be frozen by first-write-wins before later polls finish covering D. Until then the day is missing with reason `not_settled`, and `open_days` lists it.
7. `commit_day` passes `canary_ok=True` to `web_evidence.commit_day`. The settled coverage of at least 0.8 on both kinds can only come from real entries, so it serves as the canary. The AC3 trailing-median zero rule still applies.

## 9 Blockers

No blockers. Risks and open points:

- Combined-feed span is unmeasured: 100 comments over 12 subreddits may span less than the 15 h measured on r/CryptoCurrency alone. The 2 h cadence plus paging should still close the gaps; the owner probe `--stream-status` shows it.
- An empty feed records no poll (reason `empty_feed`), so the next run polls again. With 12 subreddits combined this should not happen.
- PLAN and SPEC text for the planner to update:
  - PLAN `narrative-baskets-xreddit-collector_PLAN_21-10-26.md`:
    - line 184 (impl order wording against AC14)
    - line 186 (`reddit_stream_subreddits` 4-6, `reddit_stream_poll_interval_s` 3600, `reddit_stream_polls_per_day_cap` 6, `reddit_comments_paging` false; the key names here are `reddit_comments_poll_interval_s` and `reddit_posts_poll_interval_s`)
    - line 187 (`test_stream_feed_count_must_be_4_to_6`; `share_daily_budget_150` is the degraded value)
    - line 192 (Q17 open)
  - SPEC `narrative-baskets-xreddit-collector_SPEC_21-10-26.md`:
    - line 129 AC14 (default order)
    - line 169 AC26 (4-6 feeds, 3600 s)
    - line 182 AC30 (paging off)
    - line 304 Q15 (4-6)
    - line 306 Q17 (open; P-R7 passed per the owner)
    - line 388 A.2 M2 (4-6, 3600 s, cap 6, budget 150)
    - line 404 A.2b (paging stays off until P-R7)
    - line 545 Annex H row 3b (off until P-R7)
- Registry request: none.

## 10 Follow-up

- W8e: call `reddit_stream.run_due` and `reddit_stream.commit_day` for each day in `open_days(now)` from the worker, sharing the `reddit_web` PcSource.
- W8f: use `pick_impl` with `reddit_impl_order` when building the Reddit window, and show the stream completeness file on the Sources row.
- Owner: run the `--stream-status` probe after a day of baseline polling.

## 11 Context cost

Files loaded (partly): the PLAN (lines 1-203), the SPEC (targeted lines), `reddit_web.py`, `reddit_items.py`, `reddit_metrics.py`, `pc_pace.py`, `web_evidence.py`, `web_queries.py`, `store.py` (part), `probe_pc_sources.py`, `test_reddit_web.py` (head), `test_web_queries.py`, `test_probe_pc_sources.py` and the guard greps. About 55,000 tokens of files.

## 12 Fix round 1 (29-10-26, owner-approved after the independent review of draft PR #191)

### 1 Task ID

W8c2 fix round 1 on branch `claude/w8c2-reddit-stream` (draft PR #191). Worker: riper-opus, RT2. Inputs: review finding 1 (blocking), owner decisions D1-D3, small fixes S1 and S2.

### 2 Outcome

done

### 3 Summary

- Finding 1: a poll now records `truncated`. Comments paging cut before its floor (budget spent, pause, a failed page, or a last id that is not `t1_`) is stored with `truncated: true`. Its real span still counts toward coverage, but it never settles a day (`_moved_past`). The next poll's paging floor is the newest entry of the last COMPLETE poll, so the gap a truncated poll left is paged again. Natural ends (floor reached, short page, no-progress or empty page, paging off, posts) are not truncated.
- D1: coverage stays per feed kind over the combined feeds. The module docstring states the owner waiver. The completeness file has `coverage_scope: "feed_kind"`. The probe docstring says per feed kind, never per subreddit. No name, field or probe line claims per-subreddit coverage.
- D2: the `canary_ok=True` shortcut is gone. `commit_day` passes `CANARY_OK = False` because the stream sends no canary query. The completeness file records `canary_ok: false`. A covered, settled real zero is therefore held back by `density.finalize` (AC3 as written) and stays missing with reason `zero_no_canary` and the coin's `trailing_median` (None without history). Non-zero counts are unaffected.
- D3: the default `reddit_impl_order` is now `["reddit_web", "reddit_stream"]` (SPEC AC14), in `web_queries.py` and `attention_queries.json`.
- S1: `stream_status` returns None for a kind that no poll with entries reached on a day. The probe prints `none` there (the probe's existing numbers-only form for an unknown value), never 0.
- S2: a well-formed empty Atom feed is a recorded poll (`entries` 0, `newest`/`oldest` None, `pages` 0, reason `empty_feed`). It covers and settles nothing, and the kind waits for its interval, so it no longer spends the budget at the 60-120 s spacing.

### 4 Files changed

- `api/data/attention/reddit_stream.py`: `Poll.truncated` (required; `newest`/`oldest` may be None), `_moved_past`, the settle predicate in `day_status`, `_paging_floor`, truncation tracking and the empty-feed poll in `run_poll`, `CANARY_OK` and `COVERAGE_SCOPE`, `commit_day` (`zero_no_canary`, `canary_ok`, `coverage_scope`), `stream_status` (None for unknown coverage), and the module docstring.
- `api/data/attention/web_queries.py`: `REDDIT_STREAM_DEFAULTS["reddit_impl_order"]` is now `["reddit_web", "reddit_stream"]`.
- `api/data/attention_queries.json`: the same value for `reddit_impl_order`.
- `api/scripts/probe_pc_sources.py`: docstring only (per feed kind; `none` = unknown coverage).
- `api/tests/data/attention/test_reddit_stream.py`: the `P` helper takes `truncated`. 12 new test functions (13 cases):
  - finding 1: `test_budget_cut_paging_after_midnight_does_not_settle_previous_day`, `test_pause_mid_paging_after_midnight_does_not_settle_previous_day[paused_between_pages|error_on_page_2]`, `test_non_t1_last_id_after_midnight_does_not_settle_previous_day`, `test_complete_paging_after_midnight_settles_previous_day`, `test_poll_after_truncated_poll_pages_back_to_last_complete_poll`, `test_posts_never_send_after`;
  - S2: `test_empty_feed_recorded_as_poll_and_not_retried_before_interval`, `test_empty_poll_never_settles_a_day`;
  - D2: `test_covered_settled_real_zero_missing_without_stream_canary`, `test_zero_without_history_stays_missing`;
  - D1 and S1: `test_coverage_is_per_feed_kind_never_per_subreddit`, `test_stream_status_coverage_unknown_without_polls`.

  Two tests were updated for D3, and no assertion was removed:
  - `test_methods_never_mixed_in_one_window_config_order` now pins the AC14 config order and still checks a stream-first order explicitly.
  - `test_fallback_to_posts_only_series_when_comments_missing` uses an explicit stream-first order to keep its meaning, plus the config-order empty case.
- `api/tests/data/attention/test_web_queries.py`: the pinned default order (D3).
- `api/tests/scripts/test_probe_pc_sources.py`:
  - The `Poll(...)` call passes `truncated`.
  - New test: `test_reddit_stream_status_coverage_none_for_days_without_polls`.
- This report (this section).

### 5 Commits

- `f844d455589f8ef2b4c1c3a2fc0eb9dcb67e325c`: fix round 1 code and tests (parent `6fb6977e`).
- The commit that adds this section (its SHA is in the PR).

### 6 Tests run

- Baseline of the owned test files before any change, `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_reddit_stream.py api/tests/data/attention/test_web_queries.py api/tests/scripts/test_probe_pc_sources.py -q -p no:cacheprovider`, 2026-10-29T22:57:17Z, head `6fb6977e`: 84 passed.
- Red, step 1, same command, 2026-10-29T23:00:58Z, after the tests were written: 39 failed, 59 passed. Most failures were `TypeError: Poll.__init__() takes 7 positional arguments but 8 were given` (the new `truncated` field). The two default-order tests failed on `('reddit_stream', 'reddit_web') == ('reddit_web', 'reddit_stream')`. The empty-feed test failed on `assert (None is not None)` (no poll recorded).
- Red, step 2, same command, 2026-10-29T23:01:28Z. Only the `truncated` field existed at this point, always False, with the old logic. Result: 14 failed, 84 passed.
  - The budget, pause/error and non-`t1_` tests failed on `truncated is True` (False).
  - The floor test failed: the next poll stopped at about 01:30 of D+1 instead of reaching 20:00 of D.
  - `test_empty_poll_never_settles_a_day` failed with `TypeError: '>=' not supported between NoneType and datetime`.
  - The AC3 tests failed with `KeyError: 'canary_ok'`, and with `zero_not_stored` and no `trailing_median`.
  - `coverage_scope` was missing (`KeyError`).
  - The probe printed `coverage_comments=0` for days without polls.
  - The two default-order tests failed as in step 1.
- Red, settle bug reproduced on the old predicate: a throwaway test ran the budget-cut sequence and then `commit_day`. It failed with `assert (True is False)`: the day was settled. The file was deleted after the run and was never committed.
- Guard, not red-first: `test_posts_never_send_after` checks behaviour that was already correct. It failed in step 1 only through the `Poll` field.
- Green, same three files, 2026-10-29T23:04:26Z: 98 passed. This is the code committed as `f844d455`. The worktree differs from that commit only in line endings, which `core.autocrlf` converts.
- Gates, each with `UV_FROZEN=1 uv run --project api pytest <dir> -q -p no:cacheprovider`, on the same code:
  - `api/tests/data/attention`, 2026-10-29T23:04:48Z to 23:06:15Z: 833 passed, 1 skipped, 0 failed.
  - `api/tests/tooling_guards`, 23:06:15Z to 23:06:30Z: 128 passed, 0 failed. The known Windows-path failure in `test_cli_guard.py` did not occur in this run.
  - `api/tests/scripts`, 23:06:30Z to 23:09:13Z: 648 passed, 0 failed, 2 warnings.
- File set: `git diff --name-only origin/main...f844d455` lists the 7 owned code and test files. This report is the eighth file, added in the next commit.
- `git diff --check 6fb6977e f844d455`: no output.
- Hygiene: the added lines (`git diff` against `6fb6977e`, `+` lines) were grepped for these patterns: `bullish|bearish|signal strength|confidence|triggered|confirmed|trust weight|TODO|FIXME`, the repo owner and slug, user paths, `cookie=`, `api key` and `token`. There were no hits.

### 7 Tests NOT run

- The owner probe `--source reddit --stream-status` was not run on a live machine. There is no provider access here, and no live Reddit call was made.
- No linter ran: `ruff` and `pyflakes` are not in the project environment. New lines are at most 120 characters. The 4 longer lines in these files are older lines.

### 8 Deviations

1. `_paging_floor` changed: it now uses the last complete poll with entries, not simply the last poll. This is part of finding 1. Changing only the settle predicate would not be enough: the next poll's floor would be the truncated poll's newest entry, after D, so it would never page back into the gap. The first complete poll after midnight would then settle D with the gap frozen in. Test: `test_poll_after_truncated_poll_pages_back_to_last_complete_poll`.
2. A page that fails after earlier pages counts as truncated. This is the same as a pause, because paging stopped before its floor. Test: `test_pause_mid_paging_after_midnight_does_not_settle_previous_day[error_on_page_2]`.
3. S1 prints `none`, not `n/a`. `report_line` accepts only numbers, booleans and None (printed `none`) and refuses strings, so `none` keeps the output numbers-only.
4. The empty-feed poll stores `pages` 0, meaning pages with entries, which matches how `pages` already counted. One request was still spent and is counted in `PollOutcome.requests`.
5. The missing reason `zero_not_stored` became `zero_no_canary`, and the coin entry now carries `trailing_median`.

### 9 Blockers

No blockers. Items for the planner:

- D1 waiver, owner-approved. Coverage is per feed kind over one combined feed per kind, and each kind must reach 0.80. This waives per-subreddit coverage (SPEC AC26 and A.2 M2: per-subreddit feeds, then the mean). The SPEC was not changed. The per-entry subreddit label read from a combined feed stays UNVERIFIED until the owner's probe; counts do not use it.
- D2 consequence: the stream has no canary query, so under AC3 as written it never stores a zero. Every covered, settled real zero is missing (`zero_no_canary`), whatever the trailing median, so quiet coins will have sparse stream series. A stream zero would need an owner or SPEC decision on what counts as a stream canary. Nothing was guessed here.
- D2 interpretation: "enough history" was read as "a trailing median exists", meaning at least one stored stream point in the 28 days before D. This is the same rule as `reddit_web` (Q-e). No minimum day count was added. Under the current rule this has no effect, because no zero passes without a canary.
- D3: PLAN `narrative-baskets-xreddit-collector_PLAN_21-10-26.md` line 184 still says "default `reddit_stream`, `reddit_web`, so a day without comment coverage falls back to the posts-only series", the reverse of SPEC AC14 and of the new default. The planner should update that line. Deviation 5 in heading 8 above is superseded by D3.
- Heading 9 of the first round said "An empty feed records no poll". That is superseded by S2.
- Registry request: none.

### 10 Follow-up

- Owner: the `--stream-status` probe after a day of baseline polling, now including how often polls are truncated.
- Planner and owner, if wanted: a SPEC decision on a stream canary for AC3 zeros.

### 11 Context cost

Files loaded (partly): `reddit_stream.py`, `test_reddit_stream.py`, `density.py`, `web_evidence.py`, `pc_pace.py` (pause and budget API), `store.py` (part), `probe_pc_sources.py` (part), `test_probe_pc_sources.py` (part), SPEC AC3 (line 96) by grep, PLAN line 184 by grep, the review text, and this report. About 40,000 tokens of files. Tools: read, grep, edit, bash (git, uv, pytest).

## 13 Fix round 2 (29-10-26, after the independent review of head `73185eeb`)

### 1 Task ID

W8c2 fix round 2 on branch `claude/w8c2-reddit-stream` (draft PR #191). Worker: riper-opus, RT2. Inputs: the blocking review finding (an aged-out paging floor lets a reachable undercount settle and freeze), invariants I1-I4, test list (a)-(e), and the small fix (poll files without `truncated`).

### 2 Outcome

done

### 3 Summary

- I1: `_paging_floor(kind, now)` is the newest entry of the last complete poll (not truncated, entries > 0) of the kind, searched in every stored poll file (`stored_polls`; poll files are never pruned, so the lookup reaches as far back as the files do). With no complete poll it uses the existing fallback, the start of the newest completed UTC day. Each poll now stores the floor it ran against (`Poll.floor`).
- I2: a complete poll wholly after D (`_moved_past`) settles D only when `_holes` finds no skipped hole in D. For each pair of consecutive complete polls of a kind whose hole reaches into D: the later poll either reached back to the earlier poll's newest entry (continuity), or it stopped at the feed's end before that floor (short page, no progress or empty page; posts never page). The hole is skipped, and D stays unsettled, when the later poll's floor lay past the hole or is unknown (a poll file of an earlier head). Before the first complete poll of a kind, the floor is only the fallback: if earlier truncated polls reached into D and the first complete poll starts after D's start, D stays unsettled.
- I3: an unreachable hole stays uncovered, so the existing coverage rule decides (stored and flagged `partial` at 0.80 or more per kind, missing as `below_coverage` below). The completeness file now has `gap_unreachable` per kind: `{"hours": <hours in D>, "spans": [[from, to], ...]}`. A kind with no unreachable hole has `{"hours": 0.0, "spans": []}`, a measured zero, not a missing value.
- I4: nothing loops beyond the existing paging loop inside one poll, which still stops at the floor, the feed's end, a cut, or `can_spend(1)` failing. Worst-case spend per UTC day is unchanged as a bound: the shared Reddit budget (`reddit_daily_request_budget` 250, degraded 150). One comments poll can spend at most what is left of that budget, and at most `reddit_stream_polls_per_day_cap` (12) polls per kind run per day. What changed: a floor can now lie days back, so after a long host stop one poll may page more than before. The feed's own depth ends it earlier (UNVERIFIED: Reddit's listing depth is not measured here; the owner probe can show it).
- Small fix: `Poll.from_json` reads a missing `truncated` as True (never settles a day) and a missing `floor` as None.
- Owner decisions D1 (combined feeds, coverage per kind), D2 (no stream canary, no AC3 zeros) and D3 (default order `reddit_web`, `reddit_stream`) are unchanged.

### 4 Files changed

- `api/data/attention/reddit_stream.py`: `Poll.floor` and `from_json` defaults, `stored_polls`, `_paging_floor` (I1), `_holes` and the settle predicate in `day_status` (I2), `DayStatus.gap_unreachable` and the completeness field (I3), `commit_day` and `stream_status` read all stored polls, and the module docstring.
- `api/tests/data/attention/test_reddit_stream.py`: `live_stream` gains a `depth` parameter (the feed's depth; default 10,000, as before); the `P` helper gains `floor`, default far back (a synthetic complete poll that stopped at the feed's end, which is what the existing synthetic tests model). No existing assertion was changed or removed. Ten new test cases (see heading 6).

### 5 Commits

- `ec2c52e55e81ab2cdfe9930bbc192b203eb21468`: fix round 2 code and tests (parent `73185eeb`).
- The commit that adds this section (its SHA is in the PR).

### 6 Tests run

All runs: `UV_FROZEN=1 uv run --project api pytest <target> -q -p no:cacheprovider`.

- Baseline, `api/tests/data/attention/test_reddit_stream.py`, 2026-10-29T23:33:15Z, head `73185eeb`: 55 passed.
- New tests: (a) `test_two_budget_cut_polls_then_complete_poll_reaches_aged_out_floor_no_undercount`; (b) `test_host_off_for_a_day_then_complete_poll_reaches_aged_out_floor_no_undercount`; (c) `test_paging_floor_uses_complete_poll_older_than_due_window`; (d) `test_paging_floor_without_complete_poll_falls_back_then_first_complete_poll_anchors`; (e) `test_truncated_poll_then_complete_poll_past_due_window_settles_previous_day` (the existing `test_poll_after_truncated_poll_pages_back_to_last_complete_poll` is kept); I2 `test_day_with_only_truncated_polls_never_settles_through_fallback_floor` and `test_complete_poll_with_unknown_floor_never_closes_a_hole`; I3 `test_gap_beyond_feed_depth_is_unreachable_reported_and_never_stored_as_full[20-fetched]` and `[12-below_coverage]`; small fix `test_poll_file_of_earlier_head_reads_as_truncated_with_unknown_floor`. (a), (b) and (e) check the stored value: D settles with comments coverage 1.0, every comment of D 20:00-24:00 is among the seen ids, and the stored count equals the seen count.
- Red, step 1, 2026-10-29T23:34:36Z, tests written, code unchanged: 44 failed, 21 passed. Most failed with `TypeError: Poll.__init__() takes 8 positional arguments but 9 were given` (the new `floor` field). The earlier-head poll file test failed with `KeyError: 'truncated'`.
- Red, step 2, 2026-10-29T23:35:17Z, only `Poll.floor` stored (old floor and settle logic): 10 failed, 55 passed. (a) failed on floor `2026-10-28 00:00` instead of D 20:00; (b), (e) and both I3 cases on floor `2026-10-27 00:00` instead of the D anchor; (c), (d) and the earlier-head test on the `_paging_floor` signature; the truncated-only test and the unknown-floor test on `assert (True is False)` (D was settled).
- Green, 2026-10-29T23:36:49Z: 65 passed.
- Mutation checks (temporary edits, restored afterwards; the restored file matched the green snapshot):
  - I1 and I2 both reverted (floor from the one-day window, settle without `_holes`), 2026-10-29T23:37:31Z: 8 failed, 57 passed, including (a) and (b). A throwaway probe test (deleted, never committed) ran the (a) and (b) sequences to `commit_day`: (a) stored SOL = 4 at comments coverage 0.833 (`partial`, D 20:00-24:00 never paged; 4 seen ids), (b) stored 70 at 0.916. With the fix the same sequences store 237 and 170 at coverage 1.0.
  - I1 reverted only: 6 failed, 61 passed. (a), (b), (e), (c) and both I3 cases fail; the probe shows D not settled (missing), never stored.
  - I2 reverted only: 2 failed, 65 passed (the truncated-only test and the unknown-floor test).
- Gates on the green code, 2026-10-29T23:39:52Z to 23:45:48Z:
  - `api/tests/data/attention`: 843 passed, 1 skipped, 0 failed.
  - `api/tests/tooling_guards`: 128 passed, 0 failed. The known Windows failure in `test_cli_guard.py` did not occur.
  - `api/tests/scripts`: 648 passed, 0 failed, 2 warnings.
- File set: `git diff --name-only origin/main...ec2c52e5` lists the 7 owned code and test files and this report.
- `git diff --check 73185eeb ec2c52e5`: no output.
- Hygiene: the added lines (`+` lines of `git diff` against `73185eeb`) were grepped for `bullish|bearish|signal strength|confidence|triggered|confirmed|trust weight|TODO|FIXME`, the repo owner and slug, user paths and URLs. There were no hits. New lines are at most 120 characters.

### 7 Tests NOT run

- The owner probe `--source reddit --stream-status` was not run on a live machine. There is no provider access here, and no live Reddit call was made.
- No linter: `ruff` and `pyflakes` are not in the project environment.

### 8 Deviations

1. A test helper changed: `P` (synthetic stored polls) now passes a `floor`, default far back. `Poll` needed the new field, and a far-back floor states what the existing synthetic tests model: a complete poll that ran out of feed. A synthetic complete poll with `floor=None` would read as an earlier-head poll and keep its day open. No existing assertion changed.
2. `live_stream` now serves only its newest `depth` entries; paging past them, or with an `after` id that has fallen out of that depth, gets an empty page. The default depth (10,000) keeps the old behaviour.
3. The I2 rule for the case with no complete poll before (not spelled out in the envelope): a day that earlier truncated polls reached into, whose hole lies before the first complete poll, stays unsettled (missing). A day no earlier poll reached settles on its coverage, because before the stream's first complete poll nothing could page there.
4. `commit_day` and `stream_status` read every stored poll file, so they find the complete poll before D. `_recent_polls` still serves the interval and daily-cap checks only.

### 9 Blockers

No blockers. Items for the planner:

- A day left unsettled by I2 stays missing (`not_settled`) for good and keeps appearing in `open_days`; nothing later can close it. This is the safe end (missing, never wrong), but W8e will re-run `commit_day` on such days every pass.
- I4 risk: after a long host stop one comments poll can spend much of the shared daily Reddit budget on paging before the per-coin searches run. The bound is the budget itself; the Reddit listing depth is UNVERIFIED. If the planner wants a per-poll page cap, that is a new config key, so an owner decision.
- Registry request: none.

### 10 Follow-up

- Owner: the `--stream-status` probe after a host stop, to see how deep comments paging goes and how often `gap_unreachable` is non-zero.

### 11 Context cost

Files loaded (partly): `reddit_stream.py`, `test_reddit_stream.py`, the attention `conftest.py` fixture name, `reddit_web.py` (budget lines), `density.py` (window lines), `attention_queries.json` (Reddit keys) and this report. About 30,000 tokens of files. Tools: read, grep, edit, bash (git, uv, pytest).
