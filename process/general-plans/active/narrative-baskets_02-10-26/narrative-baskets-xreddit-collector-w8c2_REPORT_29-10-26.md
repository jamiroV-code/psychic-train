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

## 14 Fix round 3 (30-10-26, redo after the independent review of head `74da1fec`)

### 1 Task ID

W8c2 fix round 3 on branch `claude/w8c2-reddit-stream` (draft PR #191). Worker: riper-opus, RT2. This is a redo: the earlier attempt stopped on a usage limit and left nothing, so this run started from the pushed head `74da1fec`. Inputs: owner decisions E1 (false feed end), E2 (retention), E3 (per-poll page cap and cross-poll continuation), E4 (`gap_unreachable` reporting), and the tests the last review named as missing. D1 (combined feeds, coverage per feed kind), D2 (no stream canary, no AC3 zeros) and D3 (default order `reddit_web`, `reddit_stream`) are unchanged.

### 2 Outcome

done

### 3 Summary

- E1: a poll is complete only when its paging reached its floor, meaning it holds an entry at or before the floor. Every other end before the floor now marks the poll TRUNCATED:
  - an empty page, a page that makes no progress, or a short page;
  - a full page with comments paging off;
  - a posts page;
  - the page cap, a pause, a failed page, a non-`t1_` last id, or the spent budget.

  A truncated poll never settles a day and never becomes the anchor (the last complete poll, whose newest entry is the next floor), so the next poll pages the same gap again. A quiet feed whose short page reaches past the floor is complete. A well-formed empty feed stays a recorded poll (`empty_feed`), now truncated.
- Posts: posts never page, so a posts poll is complete only when its one page reaches its floor. That floor is the newest entry of the last complete posts poll, or the start of the newest completed UTC day when there is none. This is the conservative rule. A page that stops short may be a transient short or rate-limited response, or a feed narrower than the gap. Calling it the feed's end would let the next complete poll treat the hole as unreachable and settle the day on an undercount. Consequence: after a host stop longer than the posts feed span, posts polls stay truncated until the anchor leaves the retention window. A posts day still settles when the overlapping truncated polls cover all 24 hours (coverage 1). Days touched by the hole stay missing.
- E2: new config key `reddit_stream_poll_retention_days`, default 30, validated as a positive int (0, negative numbers, bools, floats, strings and null are rejected).
  - After each poll (the empty-feed poll included), `prune_polls` deletes only the stream's own poll files (`_meta/_polls/<day>.json`) for UTC days before the window. Each file deletion is a single unlink. Seen ids, completeness files, the item ledger and pace state are not touched.
  - `stored_polls(until, retention_days)` reads only the window. `_paging_floor`, `commit_day` and `stream_status` all go through it, so with no complete poll inside the window the existing fallback floor applies.
- E3: new config key `reddit_stream_max_pages_per_poll`, default 10, with the same validation. A poll that reaches the cap before its floor is truncated.
  - A truncated comments poll stores its observed stretches in its poll record (`runs`): each is [oldest, newest] plus a cursor, the `after=` id of the stretch's oldest entry. Each poll record also keeps its floor.
  - The next due poll pages fresh from the newest entry. Once a page reaches into what the open segment observed, it resumes at the cursor below that coverage instead of fetching it again. The open segment is the truncated polls since the anchor that ran against the same floor, inside the retention window. Its coverage is merged into disjoint blocks.
  - Every request (fresh, reconnecting and resumed) counts against the cap and is spent from the shared daily budget.
  - A fresh prefix cut before it reconnects keeps only its own stretch: no span bridges an interval that no page observed. The next poll reconnects to the newest stored stretch and pages through the hole.
  - A resumed page that is not wholly older than its cursor ends the poll as truncated.
  - A cursor is never requested when it belongs to another floor, lies outside the retention window, or is not a `t1_` id.
  - The state is the poll files only, so it is bounded by E2.
- Worst case requests per UTC day from the stream: comments 12 polls x 10 = 120. Posts never page, so each posts poll is one request: 4 a day at the default 21600 s interval, at most 12 under the per-kind poll cap. That gives 124 at the default intervals and at most 132. The envelope's formula, 12 polls x 2 kinds x 10 = 240, is a looser bound that assumes posts page; it is still under the baseline budget of 250 but over the degraded 150. Every request is also checked against the shared budget (`can_spend`), so the stream can never exceed 250, or 150 when degraded. In steady state (polls every 2 h, each continuous with the last) a comments poll needs 1-2 pages: about 16-28 requests a day.
- E4: `_holes` takes the union of the stretches truncated polls observed and subtracts it from each hole between two consecutive complete polls. `gap_unreachable` (hours and spans) reports only the uncovered rest. A hole that truncated polls observed entirely is neither unreachable nor skipped. A remaining hole is never reported as 0 hours.

### 4 Files changed

- `api/data/attention/reddit_stream.py`:
  - `Poll.runs` and `Poll.spans()`;
  - `stored_polls(until, retention_days)`, `prune_polls` and `_store`;
  - `_merged`, `_uncovered`, `_covered_s` (now counts stretches), and `_holes` (E4);
  - `_anchor`, `_paging_floor(kind, now, polls)`, `_Block` and `_blocks`;
  - `run_poll` (E1 completion rule, page cap, resume at a saved cursor);
  - `commit_day` (retention window and a guard, see heading 8), `stream_status(now, q, days)`, and the module docstring.
- `api/data/attention/web_queries.py`: the two keys in `REDDIT_STREAM_DEFAULTS` and in `CollectorConfig`, validated by the existing positive-int branch of `_stream_value`.
- `api/data/attention_queries.json`: `"reddit_stream_poll_retention_days": 30`, `"reddit_stream_max_pages_per_poll": 10`.
- `api/scripts/probe_pc_sources.py`: `stream_status` passes the loaded queries (needed for the retention window).
- `api/tests/data/attention/test_reddit_stream.py`: 14 new test functions (19 cases), helpers `floor_at`, `after_ids` and `_next`, and the changed tests listed in heading 8.
- `api/tests/data/attention/test_web_queries.py`: 2 new test functions (16 cases).
- `api/tests/scripts/test_probe_pc_sources.py`: not changed.
- This report (this section).

### 5 Commits

- `673097f3dcc87f41e884508c6c068929b16b8f53`: fix round 3 code and tests (parent `74da1fec`).
- The commit that adds this section (its SHA is in the PR).

### 6 Tests run

All runs: `UV_FROZEN=1 uv run --project api pytest <target> -q -p no:cacheprovider`. Owned test files = `api/tests/data/attention/test_reddit_stream.py api/tests/data/attention/test_web_queries.py api/tests/scripts/test_probe_pc_sources.py`.

- Baseline, owned test files, 2026-10-30T11:12:46Z, head `74da1fec`: 108 passed.
- New tests:
  - E1: `test_transient_end_before_floor_is_truncated_then_good_poll_pages_the_gap_no_undercount[empty|short|no_progress]`, `test_comments_paging_off_full_page_short_of_floor_is_truncated`, `test_empty_feed_poll_is_truncated_and_never_the_anchor`. Two guards for the complete side: `test_quiet_feed_short_page_reaching_its_floor_is_complete` and `test_posts_page_reaching_its_floor_is_complete`.
  - E3: `test_capped_polls_make_deeper_progress_across_polls_and_settle_without_undercount` (commits after each intermediate cut poll and asserts D unsettled and nothing stored), `test_disconnected_fresh_prefix_never_bridges_and_later_polls_still_reach_the_floor`, `test_requests_per_poll_stay_within_page_cap_after_long_host_stop`, `test_saved_cursor_resumed_only_from_valid_state[valid|other_floor|not_t1|beyond_retention]`.
  - E2: `test_prune_removes_only_stream_poll_files_older_than_retention`, `test_paging_floor_falls_back_past_retention`, `test_day_before_retention_window_is_not_evaluated_again`, `test_stream_retention_and_page_cap_keys[...]` (2 cases), `test_stream_retention_and_page_cap_rejected_when_invalid[...]` (14 cases).
  - E4: `test_gap_unreachable_excludes_what_a_truncated_poll_covered`, `test_gap_unreachable_empty_when_a_truncated_poll_covered_the_whole_hole`.
- Red, owned test files, 2026-10-30T11:17:25Z, tests written, code unchanged: 33 failed, 109 passed.
  - The E1 tests failed on `truncated is True` (False): the empty, short and no-progress page, paging off, the empty feed, and the feed-depth test.
  - The E4 tests failed on `hours` 4.0 against 3.0 and 0.0.
  - The prune test failed with `assert not True`: the old poll file was still there.
  - The E3 and E2 tests failed on the missing config keys and the new `Poll`, `stored_polls` and `stream_status` signatures.
  - Two config-key cases failed with `AttributeError`. The 14 invalid-value cases passed while red, because the old validator rejects any unknown key with a message that names it.
- Green, 2026-10-30T11:20:51Z: 1 failed, 141 passed. The failure was the posts-anchor fixture case (heading 8, item 2). After the fixture change, at 11:22:11Z: 142 passed.
- Red for the retention guard, 2026-10-30T11:23:45Z: `test_day_before_retention_window_is_not_evaluated_again` failed. The completeness file was rewritten with `coverage {'comments': 0.0, 'new': 0.0}` and `polls {0, 0}` instead of the stored 0.833333 and 1.0. Green after the guard, owned test files, 11:24:09Z: 143 passed.
- Mutation checks on `test_reddit_stream.py` (temporary edits, then restored; the restored file has the same content as the green file):
  - E1 reverted (only error, page cap, budget or pause truncate; natural ends complete again), 11:25:08Z: 10 failed, 74 passed. Failures: the 3 transient cases, paging off, the empty feed, both feed-depth cases, `test_posts_never_send_after`, the long-stop test (posts poll), and `test_non_t1_last_id_after_midnight_does_not_settle_previous_day` (the mutant does not truncate on a non-`t1_` id).
  - E3 reverted (no page cap, no resume at a cursor), 11:26:06Z: 13 failed, 71 passed. Requests per poll reached 11 to 68 against the cap of 10. Failures: (a), (b), (e), (d), the truncated-only test, both feed-depth cases, the capped-progress test (27 requests), the disconnected-prefix test, the long-stop test (68 requests), and the three non-retention cursor cases.
  - E3 continuation only reverted (cap kept, no resume at a cursor), 11:27:24Z: 8 failed, 76 passed. The capped-progress test ran 323 polls without reaching the floor, because each poll fetched the same capped prefix again. (a), (b), (e), (d), the truncated-only test and the disconnected-prefix test failed with "no poll reached its floor", and `[valid]` never requested its cursor.
- Gates on the green code (committed as `673097f3`):
  - `api/tests/data/attention`, 2026-10-30T11:35:58Z to 11:38:12Z: 878 passed, 1 skipped, 0 failed.
  - `api/tests/tooling_guards`, 11:38:12Z to 11:38:25Z: 128 passed, 0 failed. The known Windows failure in `test_cli_guard.py` did not occur.
  - `api/tests/scripts`, 11:38:25Z to 11:41:14Z: 648 passed, 0 failed, 2 warnings.
- File set: `git diff --name-only origin/main...HEAD` lists the 7 owned files and this report.
- `git diff --check` on the change: no output. New lines are at most 120 characters.
- Hygiene and verdict words: the added lines (`+` lines of `git diff` against `74da1fec`) were grepped for these patterns, with no hits:
  - `bullish|bearish|signal strength|confidence|triggered|confirmed|trust weight|TODO|FIXME`;
  - the repo owner and slug, user paths and URLs;
  - `cookie=`, `api key` and `token`.

### 7 Tests NOT run

- The owner probe `--source reddit --stream-status` was not run on a live machine. There is no provider access here, and no live Reddit call was made.
- No linter: `ruff` and `pyflakes` are not in the project environment.

### 8 Deviations

Existing tests changed to assert the new, safer rule. Counts and coverage assertions were kept; no test was deleted.

1. `test_posts_never_send_after`: `truncated is False` is now `truncated is True`, because under E1 a posts page that does not reach its floor (01:00) is truncated. Added: the floor stays 01:00. The opposite case is the new `test_posts_page_reaching_its_floor_is_complete`.
2. `test_posts_plus_comments_day_needs_both_feed_kinds_covered`: the fixture gained a synthetic posts anchor at 03:30. Under E1 the one-entry posts poll at 12:00 would otherwise be truncated (it is short of the fallback floor), and the day would end `not_settled` instead of `below_coverage`. The anchor restores the case the test was written for: a posts poll set that is settled, but below 0.80. The assertions are unchanged.
3. `_full_poll` now polls every 2 h until one poll reaches its floor, and asserts that each poll stays within the cap. E3 supersedes "one poll pages to any depth". Tests (a), (b), (e), (d) and `test_day_with_only_truncated_polls_never_settles_through_fallback_floor` take the "poll wholly after D" time and the commit time from the completing poll (`_next`), not from fixed hours. Every assertion is kept: floor, oldest at or before the floor, D settled with full coverage and the full count (`_settled_full`), `gap_unreachable` 0, and not settled for the truncated-only case.
4. `_cut_poll` takes a `span_h` argument (default 1, unchanged). Tests (a) and (e) pass 3, so the cut polls read the same fake feed as the complete polls. A cursor from a fake feed on a different time grid does not exist in the other feed.
5. `test_gap_beyond_feed_depth_is_unreachable_reported_and_never_stored_as_full[20-fetched|12-below_coverage]` became `test_gap_beyond_feed_depth_stays_truncated_and_never_stored[20|12]`, still 2 cases. E1 supersedes "the feed's end is complete, so the hole is unreachable and D settles partial or missing by the 0.80 rule". Now each poll at 58, 60 and 62 h is truncated, with floor = the anchor and at most the cap in requests, and the floor stays at the anchor, so the gap is paged again. D is not settled. The comments coverage equals `anchor_h / 24`, the equivalent coverage assertion. Posts `gap_unreachable` is 0. SOL is missing as `not_settled`, nothing is stored, and D stays in `open_days`.
6. Calls changed with the signatures; values and assertions are unchanged:
   - `_paging_floor(kind, now)` calls go through the `floor_at` helper (`_paging_floor(kind, now, polls)` over the retention window);
   - `stream_status(now)` calls are now `stream_status(now, q)`.

Code beyond the envelope's literal text. Each change is needed for E1-E4 to hold:

7. `commit_day` no longer re-evaluates a day before the retention window. It returns the stored completeness file unchanged (or None). Without this, an unsettled day listed by `open_days` would be rewritten after pruning with coverage 0.0 from missing polls, which would make missing look like 0 (test `test_day_before_retention_window_is_not_evaluated_again`).
8. E4 also changes the skip decision. A hole between two complete polls that truncated polls observed entirely is not a skipped hole for comments either: nothing in it is missing.
9. A failed resume (a resumed page that is empty or not older than its cursor) leaves the poll truncated and the cursor stored. The next poll tries it again. No other cursor and no traversal of the block is tried in the same poll. This keeps the request cost of a dead cursor at one request a poll.

### 9 Blockers

No blockers. Items for the planner:

- New config keys:
  - this round adds TWO: `reddit_stream_poll_retention_days` (30) and `reddit_stream_max_pages_per_poll` (10). E1 needs no key. The envelope speaks of "the three new config keys"; I found no third key in E1-E3. Please confirm whether a third key was meant;
  - the stream keys W8c2 adds in total are: `reddit_stream_subreddits`, `reddit_comments_poll_interval_s`, `reddit_posts_poll_interval_s`, `reddit_stream_polls_per_day_cap`, `reddit_stream_min_coverage`, `reddit_comments_paging`, `reddit_impl_order`, and the two above.
- PLAN `narrative-baskets-xreddit-collector_PLAN_21-10-26.md` lines to update:
  - line 184: the default order is inverted against AC14. It says "default `reddit_stream`, `reddit_web`, so a day without comment coverage falls back to the posts-only series"; AC14 and the code (owner D3) use `reddit_web`, then `reddit_stream`.
  - line 186 (Files and keys): add `reddit_stream_poll_retention_days` 30 and `reddit_stream_max_pages_per_poll` 10, together with the key names and values from fix round 1, heading 9.
  - line 187 (red-first tests): add the E1-E4 tests from heading 6.
  - line 188 (AC30 tests): `test_paging_on_requests_after_t1_id_within_daily_budget` now also lies within the per-poll cap.
  - line 191 (owner probe): also check how often polls end truncated and how deep the paging goes.
  - line 192 (Q17).
- SPEC `narrative-baskets-xreddit-collector_SPEC_21-10-26.md` lines to update:
  - line 79, rule 15: the baseline schedule, plus the per-poll page cap.
  - line 80, rule 16: the page cap is a safety limit on requests, not a time budget; completeness has no per-day `pagecap` flag for the stream yet (see the risks below).
  - lines 169-171, AC26: a poll covers its observed stretches; a poll is complete only when it reached its floor (E1); poll fields `truncated`, `floor`, `runs`.
  - lines 182-184, AC30: paging to the floor, the page cap, continuation at a saved cursor (E3); paging off means a full page short of the floor is truncated.
  - lines 204-206, AC37: the stream's worst case of 124-132 requests a day inside the shared 250/150 budget.
  - lines 207-209, AC38: the truncated and unsettled states, and `gap_unreachable` net of truncated coverage (E4).
  - lines 213-215, AC40: add `reddit_stream_poll_retention_days` to the bounded-state retention configs.
  - line 304, Q15, and line 306, Q17: as in fix round 1, heading 9.
  - lines 388-392, A.2 M2: the day value and coverage rule (E1, E3, E4) and the new keys.
  - lines 396-404, A.2b: comments paging (E1, E3).
  - line 545, slice W8c2 (row 3b): paging is on, with the page cap.
  - line 584, Annex J 4: the stream poll-file retention.
  - line 586, Annex J 6: the page cap bounds the burst after a restart.
- Risks:
  - Degraded mode: after a long stop the stream can spend up to 124-132 of the degraded 150 requests in a day, leaving 18-26 for the per-coin searches. In baseline mode it leaves at least 118 of 250.
  - A cursor Reddit no longer serves (past the listing depth, or a removed comment; Reddit's behaviour for these is UNVERIFIED) keeps the segment open: every later poll ends truncated, at about 1-2 fresh requests plus 1 resumed request. This lasts until the anchor leaves the retention window (at most 30 days). Then the floor falls back, the old segment no longer matches the floor, and the next poll pages fresh. Meanwhile days settle only at coverage 1, and the days of the hole stay missing, never wrong.
  - Since E1, a complete poll written by this head always reached its floor, so it is continuous with the complete poll before it. A non-empty `gap_unreachable` can only come from stored poll records whose complete poll did not reach its floor (written by an earlier head of this branch). The stream is not wired into any worker yet (W8e), so no such owner data is expected. The planner may decide whether that reporting path should stay.
  - Rule 16 asks for cap flags in completeness. The stream's completeness file has no per-day count of page-capped polls. It shows `settled` and coverage only. Adding one would be a new field: an owner or planner decision.
- Registry request: none.

### 10 Follow-up

- Owner: run the `--stream-status` probe after a host stop. It shows how many polls end truncated and whether the gap closes within a few polls.
- Planner: the PLAN and SPEC lines in heading 9, and a decision on page-cap flags in the stream's completeness file.

### 11 Context cost

Files loaded (partly): `reddit_stream.py` (full), `test_reddit_stream.py` (full), `web_queries.py` and `attention_queries.json` (stream keys), the `probe_pc_sources.py` and `test_probe_pc_sources.py` diffs, `pc_pace.py` (state API by grep), `reddit_items.py` (`LedgerRow`), the attention `conftest.py`, the SPEC lines named in the envelope, PLAN lines 180-192, and this report. About 45,000 tokens of files. Tools: read, grep, edit, bash (git, uv, pytest). Model: one model throughout (no switch observed, no usage limit hit in this run).
