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
