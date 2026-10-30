---
name: w8c2w-stream-wiring-plan
description: "PLAN (T222, W8c2w) for wiring the merged Reddit stream-and-count method (reddit_stream, W8c2) into the PC worker: polls inside the Reddit pass, commit of settled days, completeness sidecar, Sources health row, Discovery method order, and the shared 250/150 request budget question for the owner. Plan only."
date: 30-10-26
---

# W8c2w: Reddit stream wiring into the PC worker - PLAN

Date: 30-10-26
Task: T222 (next free ID: T221 is the highest in `git log --all` subjects and PR titles; no T222 exists anywhere; W8c2 and its PRs carry no T id)
Status: PLAN only, nothing in this file has been executed. PLAN-REV: 1
Phase: PLAN (RIPER-5). EXECUTE agent: `riper-opus`. Risk tier RT2 (runtime behaviour of an unattended worker, no live provider calls in tests).
Complexity: COMPLEX (scheduler change in a threaded worker, shared request budget, health and Discovery readers, one owner decision)
Branch of this plan: `claude/w8c2w-stream-wiring-plan` (ONE draft PR, plan only). Branch of EXECUTE: `claude/w8c2w-stream-wiring`.

## Context

W8c2 (merged, PR #191) built the library `api/data/attention/reddit_stream.py` (method `reddit_stream`, method id `reddit_stream_feeds_v1`): `run_due`, `run_poll`, `due_kinds`, `commit_day`, `open_days`, `stream_status`, `pick_impl`, `Poll`, and the `reddit_stream_*` and `reddit_comments_*` config keys. Nothing calls it from the running worker. Today `RedditStream._pass` in `api/data/attention_pc_refresh.py` (lines 507-549) runs only `reddit_web.run_pass`. So the registry (`registry.SOURCE_IMPLS`, `registry.PC_STORES`) and `discovery.json` (`source_impl.reddit = [reddit_web, reddit_stream]`) already name a store that no process fills.

This slice wires the library into the worker, behind an owner-set switch that is OFF by default, and makes the result visible (completeness file, Sources row). It adds no collector logic: fetching, parsing, pacing, pause rules, paging, coverage and the AC3 zero rule stay in `reddit_stream.py` and `reddit_web.py`.

Goal: with the switch on and the host up since before 00:00 UTC (BASELINE), the Reddit stream of the worker polls the comments and posts feeds at the configured cadence between the per-coin searches, commits every settled completed day under `reddit_stream`, writes the per-day completeness file, and the Sources row can report the stream store. With the switch off, behaviour is byte-identical to today.

Non-goals: no change to `reddit_stream.py` (open PR #198 owns it), `web_queries.py`, `attention_queries.json`, `discovery.json`, `discovery.py`, `probe_pc_sources.py`, `web/`, `.github/`; no X changes; no engagement enrichment (W8c3); no verdict logic.

## Verified inputs (measured in this PLAN session, read-only, `origin/main` = `3cd39e26`)

| Fact | Where (main) | Consequence for the wiring |
|---|---|---|
| The worker runs two threads (X, Reddit); `PASS_LOCKS[REDDIT_SOURCE]` serialises a Reddit pass; the loop is `schedule -> _wait_until(due - 20 s) -> run_pass` | `attention_pc_refresh.py` 83, 293-304, 643-657 | Polls MUST go inside the Reddit stream's pass, under the same lock, so searches and polls never overlap and the 60-120 s request spacing holds for both. A second thread is rejected. |
| `Stream.run_pass` returns `"done"` when the search queue is empty, and `done`, `paused`, `budget_spent` are in `NEXT_DAY`, so the stream sleeps to 00:00 UTC + 20 s | 101, 322-348, 306-319 | With the stream on, an empty search queue must not end the day: the schedule needs a second wake source (next poll due). Without this the polls would run once a day. |
| `reddit_web.run_pass(... stop_at=...)` stops with `"host_stopped"` before a unit whose due time is at or after `stop_at`; items left stay queued | `reddit_web.py` 548-613 | The stream round can slice the search pass at the next poll due time with no change to `reddit_web`. |
| `reddit_web.run_pass` tries ONE canary per call and UTC day while `canary_ok(now)` is false | 560-586 | Slicing calls `run_pass` many times a day; a canary that keeps failing without a pause could be retried once per slice. Bounded by the slice count; the red test `test_canary_failure_not_repeated_across_search_slices_same_day` decides whether `reddit_web` needs one optional parameter (RFC-4). |
| Budget and pause state is ONE file per source: `pc_pace.state_path` accepts only `xsearch_web` and `reddit_web`; `reddit_source(config, degraded=...)` gives 250 (baseline) or 150 (degraded), non-adaptive | `pc_pace.py` 34-35, 146-149; `reddit_web.py` 330-345 | Stream polls MUST use the `PcSource` of `reddit_web` (`run_poll` already takes `src`). The stream has no state file of its own and must not get one. |
| `run_due(client, src, q, *, ledger, clock, sleep, rng, stop_at=None)` returns `StreamPass(outcomes, stop)` with stop in `done`, `host_stopped`, `paused`, `budget_spent` or a CollectorError reason; it ends early on pause or `budget_spent`; polls use `reddit_web.fetch_feed` (honest UA, no redirects, block rules) | `reddit_stream.py` 436-458, 9-12 | The honest user agent, pause rules and shared budget come for free if the worker calls `run_due` with the shared `src` and its own `client` (`worker.reddit_client()`). |
| `commit_day(day, q, ledger, *, now)` returns the completeness doc or None (day not complete); `open_days(now)` lists completed days with stream entries that are not settled (oldest first); `stream_status(now)` reads local files | 474-532, 549-572 | Wiring calls `commit_day` for every `open_days(now)` after each round. Repeat calls are safe by AC4 (frozen) and cheap (files only). A day that can never settle (round-2 finding I2) stays in `open_days` forever and is re-evaluated every round: bounded by the `_seen` retention (RFC-5). |
| `commit_day` stores through `web_evidence.commit_day` under source `reddit_stream`; `CANARY_OK = False`, so a covered real zero stays missing (`zero_no_canary`) | 47-51, 88 | No zero is ever stored by the stream. Sources text must say missing, never 0. |
| `registry.SOURCE_IMPLS["reddit"]` and `registry.PC_STORES` already include `reddit_stream`; `sources.PC_STORES` (line 56) does NOT | `registry.py` 27-30; `sources.py` 56 | `sources.py` keeps its own copy that has drifted. The row health is attached only `if impl in PC_STORES` (line 314). |
| `sources._health(store_id, ...)` calls `pc_pace.state_path(store_id)` (raises `ValueError` for `reddit_stream`), reads `<store>_health.json` next to it, and `_completeness` parses the per-coin `reddit_web` completeness format | `sources.py` 108-190 | Simply adding `reddit_stream` to `PC_STORES` would crash the Sources route for a stream row. The health reader must map the stream to the shared `reddit_web` state and read the stream's own (different) completeness format (RFC-6). |
| Discovery: `source_impl.reddit = ["reddit_web", "reddit_stream"]` (discovery.json 75); `_weighted_source` takes the first store that yields a change for the coin and window; W8f deviation 5 states there is no separate `reddit_impl_order` key in Discovery | W8f report | The shipped order already equals SPEC AC14. Meanwhile `attention_queries.json` holds a second copy `reddit_impl_order` and `reddit_stream.pick_impl` has no production caller. Two sources of truth: see Q4. |
| Evidence `known_at_time` drops points whose `collected_at` is after D+1 | W8f report 17, 58 | A stream day committed later than D+1 (host off) is excluded from point-in-time history. Honest, by design; stated here so nobody calls it a bug. |

### Code that differs on `origin/claude/w8c2-reddit-stream` (PR #198, draft, not merged)

Compared with `git diff origin/main...origin/claude/w8c2-reddit-stream` and by grep of the head. #198 touches: `reddit_stream.py`, `web_queries.py`, `attention_queries.json`, `probe_pc_sources.py`, `test_reddit_stream.py`, `test_web_queries.py`, the W8c2 REPORT. What changes for this plan:

- New keys `reddit_stream_poll_retention_days` (30) and `reddit_stream_max_pages_per_poll` (10): one poll sends at most 10 requests (fresh, reconnecting and resumed pages); truncated polls keep their cursors and resume (`Poll.runs`).
- Signature changes: `stored_polls(until, retention_days)` and `stream_status(now, q, *, days=3)` (the probe call becomes `stream_status(clock(), web_queries.load())`). UNCHANGED on the #198 head (checked by grep of the `def` lines): `run_due`, `run_poll`, `due_kinds`, `commit_day`, `open_days`, `read_completeness`, `pick_impl`. This plan calls only the unchanged ones.
- `prune_polls(now, retention_days)` runs after every poll inside `reddit_stream` (E2); the worker must NOT prune `_polls`. What #198 does to `_seen` and `_completeness` is cut in my read of its docstring line 41 (UNVERIFIED); EXECUTE reads lines 38-45 of the #198 head and prunes `_seen` and `_completeness` itself only if they are not pruned there.

DECISION: EXECUTE starts only after #198 is merged to `main` (gate G0). Reasons: the wiring's page-cap and retention behaviour is the one the owner approved in #198; the budget bound below depends on the page cap; a stacked PR would make the owner review two moving parts. If the owner wants earlier work, base on the #198 head and say so in the PR; not recommended.

## 1. What must be wired (design)

All file edits are listed in section 3. Names are proposals; EXECUTE may rename if it keeps the contracts in section "Public Contracts".

W1. Switch. `SCREENER_ATTENTION_REDDIT_STREAM` exactly `1` (the `FLAG_ENV` pattern: tests and workflows never set it) turns the stream on; absent or any other value: off. `AttentionPcWorker(..., reddit_stream: bool | None = None)`; `None` reads the environment in `start_from_env`. No new config key (this keeps `web_queries.py` and `attention_queries.json` out of the owned set and away from #198, and gives the owner a one-line off switch).

W2. Stream round inside `RedditStream._pass` (under the existing Reddit lock), only when the stream is ON, the mode is BASELINE (Q1 option d), and the ledger exists:
1. `reddit_stream.run_due(client, src, q, ledger=ledger, clock=w.clock, sleep=w._sleep, rng=self.rng, stop_at=stop_at)` with the SAME `src` (`reddit_source`, shared 250 budget and pause state), the same `client` (`reddit_web.make_client`: honest user agent, no redirects, no proxy) and the worker's interruptible `_sleep`. `paused` and `budget_spent` end the round and the pass with that outcome (same codes as the search pass); `host_stopped` ends it with `host_stopped`.
2. `commit_open_days`: for each day in `reddit_stream.open_days(now)`: `reddit_stream.commit_day(day, q, ledger, now=now)`; an exception is logged as `attention pc reddit_stream commit skipped: <ExceptionClass>` (class name only) and never ends the pass.
3. The search slice: `reddit_web.run_pass(..., stop_at=min(stop_at, next_poll_due))` over the same `queue(q, syms)`. If it returns `host_stopped` while the worker's own `stop_at` is not reached, the pass returns the new outcome `stream_due` (not in `NEXT_DAY`): the schedule wakes at the next poll or the next search, whichever is first.
4. The stream round runs BEFORE the search slice, so a poll that is due is never delayed by a long search queue, and searches resume at the configured spacing because `run_pass` derives its first due time from `src.last_unit_at()` (polls update it through `PcSource`).

W3. Schedule. `Stream.run_pass` gets one hook `_idle(q, syms)` (default: `not self.queue(q, syms)`), and `Stream._behind` one hook for an extra wake time (default None). `RedditStream` overrides them so that with the stream ON and the polls not capped for the day: an empty search queue does not return `done`; `done` and `stream_due` both schedule `min(next search due, next poll due)`; paused, budget spent or poll caps reached still wait for the next UTC day. `next_poll_due(q, now)` is computed in the worker from `reddit_stream.read_polls` and the public config (interval per kind, `reddit_stream_polls_per_day_cap`), without touching `reddit_stream.py`; the property test `test_next_poll_due_matches_due_kinds` pins it to `due_kinds`. X is untouched (hooks default to today's behaviour).

W4. Degraded mode. In DEGRADED (restart day) no stream poll is sent (Q1 option d). Searches run exactly as today. Stream days with polls missing stay unsettled, so their coin-days are missing, never 0. The mode switch needs no new rule: `worker.mode(now)` already follows host uptime, never an hour of the day (AC28).

W5. Open days and completeness. `commit_day` writes `reddit_stream/_meta/_completeness/<day>.json` (coverage per feed kind, polls, settled, partial, fetched, missing reasons, `gap_unreachable`, `canary_ok: false`) when the day is complete (AC38). A completed day for which the stream never saw an entry has no file; the Sources text then says `unknown`, never 0 (Q5).

W6. Retention (AC40). `RedditStream._prune` also prunes `reddit_stream/_meta/_seen` and `_completeness` day files older than `ledger_retention_days` (default 400) with the existing `_prune_day_files`, using the public `seen_path(day).parent` and `completeness_path(day).parent`; `_polls` is #198's job. No new directory grows without a bound.

W7. Ledger. `worker.reddit_ledger()` may be None (salt error). Then the stream stays OFF for the pass with reason code `ledger_unavailable` in the log, and searches continue as today (`reddit_web.run_pass` accepts `ledger=None`). Nothing is stored without the ledger.

W8. Logs. Only the source, an outcome or reason code and the exception class name; never a URL, subreddit set, entry id or author (the existing `_DropRedditRequestLine` filter stays installed on the client).

W9. Sources health. `sources.py`: `PC_STORES = registry.PC_STORES` (one definition); `_health` maps store `reddit_stream` to the `reddit_web` state and schedule files (shared budget, pause, last unit) and reads the stream completeness file for the target day: text `D: settled yes|no, coverage comments x new y, fetched n, missing m (reasons), partial yes|no, newest Nh old` with `unknown` for any absent field. `completeness_attempted` stays None (the stream has polls, not per-coin attempts). `DiscoverySourceHealth` (model) and `web/` are NOT changed.

W10. Discovery method choice (AC14). No `discovery.py` or `discovery.json` change: `source_impl.reddit` is already `["reddit_web", "reddit_stream"]`. This slice only adds a guard test that `reddit_impl_order` in the collector config equals `source_impl.reddit`, and the test that the stream store is used when `reddit_web` has no usable points (Q4 covers the per-coin versus per-window difference).

## 2. Shared Reddit request budget: OWNER DECISION Q1

The one Reddit counter (`reddit_web` state) is 250 requests per UTC day in BASELINE and 150 in DEGRADED. Per-coin searches need about 75 requests for yesterday plus 1 canary (75 coins; backfill of up to 5 earlier days comes after yesterday and is the first thing cut).

Stream cost per UTC day (bound, from the merged code and the #198 page cap): comments 12 polls (interval 7200 s) times at most 10 requests each, posts 4 polls (interval 21600 s; the cap key allows 12) which never page: 12 x 10 + 4 = 124 with the interval, 12 x 10 + 12 = 132 if the posts cap and not the interval were the limit. The typical day is far lower (a poll that reaches its floor on page 1 costs 1; 16 requests); the bound is what the budget must survive. All figures are from code reading, UNVERIFIED until the owner's spend probe P-S3.

| Mode | Budget | Stream at its bound | Left for per-coin searches |
|---|---|---|---|
| BASELINE | 250 | 124-132 | 118-126 (yesterday 76 fits; backfill shrinks from about 170 to about 45) |
| DEGRADED | 150 | 124-132 | 18-26 (yesterday needs 76: only about a quarter of the coins) |

Options:

- (a) No reserve. Simplest. In DEGRADED the polls can spend most of 150 before the searches run (polls are due first), so the primary series (`reddit_web`, first in the order) loses most coin-days on every restart day. Rejected.
- (b) New key `reddit_stream_budget_share`. Tunable in both modes. Needs a config key and validation in `web_queries.py` and `attention_queries.json` (both owned by #198 now, so strictly after its merge), plus a stream-spend counter (sum of page counts of today's polls) because the budget `used` is shared. More surface for a number nobody has measured.
- (c) Searches first, stream with the remainder. Keeps the primary series whole in both modes, but the polls then start late in the day; the comments feed is deep only to the page cap, so late polls leave unreachable holes and more truncated polls (gap shown, never 0). Needs a two-phase scheduler: the most complex option.
- (d) Stream polls only in BASELINE. No new key, no new counter, the DEGRADED rules stay exactly as the SPEC states them: AC37 lists the comments and posts polls under BASELINE and says DEGRADED is "AC24 behaviour with budget 150". On a restart day the stream has holes, so that day is missing in the stream series (honest, never 0) and `reddit_web` is whole. BASELINE leaves 118-126 for searches, enough for yesterday.

RECOMMENDATION: (d). Reasons: (1) it is what the SPEC text says; (2) it protects the primary series where the budget is tight; (3) it adds no key, so it does not touch #198's files; (4) the cost is bounded and visible: stream days are missing after a restart, never wrong; (5) if the owner's probe P-S3 shows the BASELINE spend is far below the bound, nothing needs tuning, and if it shows backfill starved, option (b) is a small later slice on measured numbers. The owner may choose (a), (b) or (c); (b) and (c) change the owned file set (section 3) and the test list, and the plan must be amended before EXECUTE.

## 3. File ownership and collision proof

EXECUTE owned files (option d):

| File | Change |
|---|---|
| `api/data/attention_pc_refresh.py` | switch, worker argument, `Stream` hooks (`_idle`, extra wake), `RedditStream` round, `next_poll_due`, `commit_open_days`, prune of the stream day files |
| `api/analytics/attention/sources.py` | `PC_STORES = registry.PC_STORES`, `_health` mapping for `reddit_stream`, stream completeness text |
| `api/data/attention/reddit_web.py` | CONDITIONAL, only if `test_canary_failure_not_repeated_across_search_slices_same_day` is red on the unchanged code: one optional keyword parameter `canary_days` of `run_pass`, default behaviour unchanged |
| `api/tests/data/test_attention_pc_refresh_stream.py` | NEW: the stream wiring tests |
| `api/tests/data/test_attention_pc_refresh.py` | only if an existing worker test needs the new hook signature; no assertion weakened |
| `api/tests/analytics/attention/test_sources_health.py` | stream health and text tests |
| `api/tests/data/attention/test_reddit_web.py` | CONDITIONAL with `reddit_web.py` |
| `process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_EXEC-REPORT_30-10-26.md` | NEW: the EXECUTE report |

Not owned (never edited): `api/data/attention/reddit_stream.py`, `web_queries.py`, `attention_queries.json`, `discovery.json`, `api/analytics/attention/discovery.py`, `registry.py`, `pc_pace.py`, `api/models/**`, `api/routers/**`, `api/scripts/**`, `web/**`, `.github/**`, `.claude/**`, other plans.

Collision proof, measured with `gh pr list --state open --json number,files` on 30-10-26: exactly ONE open PR, #198 (draft), files `reddit_stream.py`, `web_queries.py`, `attention_queries.json`, `probe_pc_sources.py`, `test_reddit_stream.py`, `test_web_queries.py`, and the W8c2 REPORT. None is in the owned set above: empty intersection. The peers running now (a docs catch-up, a #198 fix worker, this plan) own docs, the #198 files, and this folder; no code overlap. G0 and G1 re-check at EXECUTE start (the open-PR list is re-read; any PR touching an owned file stops the worker).

Read dependencies on files that #198 changes, with the signature facts above: `reddit_stream.run_due`, `commit_day`, `open_days`, `seen_path`, `completeness_path`, `read_polls`, `read_completeness` (unchanged by #198) and the config fields `reddit_comments_poll_interval_s`, `reddit_posts_poll_interval_s`, `reddit_stream_polls_per_day_cap` (unchanged).

## 4. Red-first tests (names, by acceptance criterion)

All in `api/tests/data/test_attention_pc_refresh_stream.py` unless noted; fake clock, fake httpx transport, loopback only, no live call. SPEC refers to `narrative-baskets-xreddit-collector_SPEC_21-10-26.md`.

| AC | Test names |
|---|---|
| AC37 (c) baseline poll cadence | `test_baseline_24h_polls_comments_every_7200s_posts_every_21600s`; `test_polls_and_searches_never_closer_than_min_delay`; `test_search_slice_resumes_at_spacing_after_poll`; `test_empty_search_queue_still_polls_stream`; `test_done_outcome_with_stream_on_waits_for_next_poll_not_next_day`; `test_next_poll_due_matches_due_kinds` (property: due at the computed time, not one second before) |
| AC37 degraded, AC28 | `test_degraded_mode_sends_no_stream_poll`; `test_mode_switch_stream_starts_next_utc_day_when_up_since_midnight`; `test_no_fixed_utc_hour_in_stream_schedule` |
| Switch and no-regression | `test_stream_off_by_default_runs_only_search_pass_as_before`; `test_stream_flag_only_exact_one_enables`; `test_stream_off_leaves_schedule_outcomes_unchanged` |
| Shared budget and pause (SPEC rules 10, 15, 16; AC24) | `test_stream_and_search_requests_count_in_one_budget`; `test_budget_spent_by_polls_stops_searches_until_next_utc_day`; `test_pause_by_poll_403_pauses_searches_same_day`; `test_pause_by_search_stops_polls`; `test_stream_requests_use_honest_user_agent_no_redirect_no_proxy` |
| Lock and spacing | `test_poll_runs_under_reddit_pass_lock_never_beside_search`; `test_x_stream_not_blocked_by_reddit_poll` |
| Canary | `test_canary_failure_not_repeated_across_search_slices_same_day` (if red, add `canary_days`; then `test_run_pass_default_canary_behaviour_unchanged` in `test_reddit_web.py`) |
| AC14, AC26 (own store) | `test_stream_values_stored_under_reddit_stream_never_reddit_web`; `test_reddit_impl_order_equals_discovery_source_impl_reddit`; `test_stream_store_used_when_reddit_web_has_no_usable_points` (in `test_sources_health.py` or a Discovery test file only if no assertion there is edited) |
| AC4, AC30 (commit, frozen) | `test_open_day_committed_when_settled_and_not_before`; `test_open_days_reevaluated_each_round_until_settled`; `test_second_commit_of_settled_day_changes_nothing`; `test_unsettled_or_below_coverage_day_writes_no_zero`; `test_commit_exception_logged_by_class_only_pass_continues` |
| AC38 (completeness, Sources text) | `test_stream_completeness_file_written_for_complete_day` (in `test_sources_health.py`: `test_stream_row_text_has_settled_coverage_fetched_missing_reasons_newest_age`); `test_stream_row_text_unknown_not_zero_without_completeness_file` |
| AC39 (health) | `test_sources_pc_stores_equals_registry_pc_stores`; `test_stream_row_health_reads_shared_reddit_web_state_without_error`; `test_stream_row_shows_pause_reason_from_shared_state`; `test_stream_row_stale_uses_shared_last_unit` |
| AC29 (ledger) | `test_ledger_unavailable_holds_stream_searches_continue`; `test_polled_entries_reach_the_ledger_once_per_id` |
| AC40 (unattended) | `test_stream_day_files_pruned_by_ledger_retention_days`; `test_restart_resumes_polls_without_burst`; `test_ninety_day_ticks_state_bounded_with_stream_on`; `test_host_stop_leaves_poll_kind_due_for_next_window` |
| Privacy | `test_logs_hold_no_url_subreddit_id_or_author_with_stream_on` |

Red-first rule: write all tests first, run the test files, record the number failing for the right reason (missing hook, missing outcome, `ValueError` from `state_path`), commit that state, then implement. The report lists the red count and the green count.

## 5. Tests, gates and Validate Contract

Test Procedure (RT2, from the repo root, Git Bash, no live provider call):

```
UV_FROZEN=1 uv run --project api pytest api/tests/data/test_attention_pc_refresh_stream.py api/tests/data/test_attention_pc_refresh.py api/tests/analytics/attention/test_sources_health.py api/tests/data/attention -q -p no:cacheprovider
UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention api/tests/routers/test_discovery.py api/tests/routers/test_discovery_history.py -q -p no:cacheprovider
```

Regression gate: before any edit, run the second command and the first (existing files only) and save the failing node ids; after the work the set of failing ids must have no new member. The W8e report records 40 pre-existing router failures on the Windows host in the full router directory, so only a diff of ids is meaningful, never a count. `process/context/tests/all-tests.md` is the test index; `process/context/all-context.md` is the context router. Also run the whole `api/tests` once after the last commit, record the result and judge failures by the id diff; if it is not run, list it under "Tests NOT run".

## Validate Contract

Run from the repository root in the EXECUTE checkout after the last commit. `BASE` is `origin/main`. `REPO` is set by Main for the leak check and never written into any file. Each gate prints FAIL and sets a non-zero exit; a gate that cannot fail is a defect. The script was checked with `bash -n` in the PLAN session, and the G0 branch was exercised against the current `origin/main` (it fails there because #198 is not merged, which is the intended result).

```bash
set -u
BASE="${BASE:-origin/main}"; RC=0; T="$(mktemp -d)"
bad() { echo "FAIL: $1"; RC=1; }
# G0 precondition: the #198 page cap is on BASE (run before EXECUTE and again before the PR)
git show "$BASE:api/data/attention/web_queries.py" | grep -q 'reddit_stream_max_pages_per_poll' || bad "G0 PR 198 not merged on $BASE"
# G1 file-set check: every changed file must be in the owned set
OWN='^(api/data/attention_pc_refresh\.py|api/analytics/attention/sources\.py|api/data/attention/reddit_web\.py|api/tests/data/test_attention_pc_refresh_stream\.py|api/tests/data/test_attention_pc_refresh\.py|api/tests/data/attention/test_reddit_web\.py|api/tests/analytics/attention/test_sources_health\.py|process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_EXEC-REPORT_30-10-26\.md)$'
git diff --name-only "$BASE"...HEAD | grep -Ev "$OWN" | tee "$T/extra" | grep -q . && bad "G1 files outside the owned set: $(tr '\n' ' ' < "$T/extra")"
git diff --name-only "$BASE"...HEAD | grep -q . || bad "G1 empty change set"
# G2 forbidden paths, even if the owned regex were widened by mistake
git diff --name-only "$BASE"...HEAD | grep -E '^(\.github/|\.claude/|web/|api/models/|api/routers/|api/scripts/|api/data/discovery\.json|api/data/attention_queries\.json|api/data/attention/(reddit_stream|web_queries|registry|pc_pace)\.py)' && bad "G2 forbidden path changed"
# G3 no secrets, IPs, home paths or the repo slug in added lines
git diff "$BASE"...HEAD | grep -E '^\+' | grep -nE '/Users/|\\Users\\|[0-9]{1,3}(\.[0-9]{1,3}){3}|(api[_-]?key|secret|cookie|token) *[:=] *[A-Za-z0-9]{8,}' && bad "G3 secret-like text in added lines"
[ -n "${REPO:-}" ] && git diff "$BASE"...HEAD | grep -E '^\+' | grep -nF "$REPO" && bad "G3 repo slug in added lines"
# G4 required red-first tests exist
for n in test_baseline_24h_polls_comments_every_7200s_posts_every_21600s test_degraded_mode_sends_no_stream_poll test_stream_off_by_default_runs_only_search_pass_as_before test_stream_and_search_requests_count_in_one_budget test_pause_by_poll_403_pauses_searches_same_day test_poll_runs_under_reddit_pass_lock_never_beside_search test_next_poll_due_matches_due_kinds test_second_commit_of_settled_day_changes_nothing test_stream_row_health_reads_shared_reddit_web_state_without_error test_sources_pc_stores_equals_registry_pc_stores test_stream_day_files_pruned_by_ledger_retention_days test_logs_hold_no_url_subreddit_id_or_author_with_stream_on; do
  grep -rq "def $n" api/tests || bad "G4 missing test $n"; done
# G5 report holds the red result (failed count above zero) and the green result
R=process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_EXEC-REPORT_30-10-26.md
grep -E '^- Red' "$R" | grep -Eq '[1-9][0-9]* failed' || bad "G5 report has no red result"
grep -E '^- Green' "$R" | grep -Eq '[0-9]+ passed' || bad "G5 report has no green result"
# G6 targeted tests pass
UV_FROZEN=1 uv run --project api pytest api/tests/data/test_attention_pc_refresh_stream.py api/tests/data/test_attention_pc_refresh.py api/tests/analytics/attention/test_sources_health.py api/tests/data/attention -q -p no:cacheprovider 2>&1 | tee "$T/t1" | tail -3
grep -Eq '[0-9]+ passed' "$T/t1" && ! grep -Eq '[0-9]+ (failed|error)' "$T/t1" || bad "G6 targeted tests"
# G7 regression: no new failing node id against the saved baseline (BASEFAIL holds the sorted ids from before the edits)
UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention api/tests/routers/test_discovery.py api/tests/routers/test_discovery_history.py -q -p no:cacheprovider 2>&1 | grep -E '^FAILED' | sed 's/ - .*//' | sort > "$T/after"
[ -f "${BASEFAIL:-/nonexistent}" ] || bad "G7 BASEFAIL baseline file missing"
comm -13 "${BASEFAIL:-/nonexistent}" "$T/after" | tee "$T/new" | grep -q . && bad "G7 new failures: $(tr '\n' ' ' < "$T/new")"
# G8 switch exact and off by default; sources uses the registry set; no hour-of-day in the worker
grep -q 'SCREENER_ATTENTION_REDDIT_STREAM' api/data/attention_pc_refresh.py || bad "G8 switch missing"
grep -rn 'SCREENER_ATTENTION_REDDIT_STREAM' api/tests/conftest.py .github 2>/dev/null && bad "G8 switch set in conftest or workflows"
grep -q 'PC_STORES *= *registry\.PC_STORES' api/analytics/attention/sources.py || bad "G8 sources PC_STORES not the registry set"
a=$(git show "$BASE:api/data/attention_pc_refresh.py" | grep -cE '\.hour\b|utcnow'); b=$(grep -cE '\.hour\b|utcnow' api/data/attention_pc_refresh.py)
[ "$b" -le "$a" ] || bad "G8 new hour-of-day or utcnow use in the worker"
# G9 stream polls reach only the shared source: no new PcSource or state file for reddit_stream
grep -nE "PcSource\(.*reddit_stream|reddit_stream.*_pc_state|_pc_state.*reddit_stream" api/data/attention_pc_refresh.py api/analytics/attention/sources.py && bad "G9 separate reddit_stream state"
rm -rf "$T"; echo "validate-contract exit $RC"; exit $RC
```

File-set check (G1) is the contract's second gate and the one most likely to catch scope drift; `git diff --name-only origin/main...HEAD` must list only owned files.

## 6. Risks, rollout, owner probes, cost

Risks:

| Risk | Mitigation |
|---|---|
| Stream starves searches in BASELINE after all (the bound is code reading, not measured) | Option d plus the bound table; P-S3 measures the day's spend; if backfill is starved, option (b) on measured numbers |
| Empty search queue ends the day and polls stop | hook `_idle` and extra wake; tests `test_empty_search_queue_still_polls_stream`, `test_done_outcome_with_stream_on_waits_for_next_poll_not_next_day` |
| A poll round delays searches or the reverse; two requests closer than the spacing | one thread, one lock, `last_unit_at` shared; test `test_polls_and_searches_never_closer_than_min_delay` |
| Slicing repeats a failed canary | `test_canary_failure_not_repeated_across_search_slices_same_day`, conditional `canary_days` |
| `next_poll_due` drifts from `due_kinds` | property test |
| A day that can never settle is re-evaluated each round forever | `_seen` pruned by retention (W6); cost is local file reads |
| Sources route crashes for a stream row (`state_path` ValueError) | W9 mapping and test |
| #198 changes a signature this plan relies on | G0 first; only unchanged functions are called; the worker reads config fields by name |
| Host off for hours: polls resume, one poll pages back to its floor (page cap 10, cursor continuation) | #198 behaviour, inside the shared budget; no burst: `run_due` spaces requests 60-120 s |
| Public repo | no names, paths, IPs, keys; G3 |

Rollout: merge with the switch OFF (nothing changes). The owner turns it on by setting `SCREENER_ATTENTION_REDDIT_STREAM=1` in the same shell or service environment that sets `SCREENER_ATTENTION_PC_WORKER=1`, and restarts the API process; the first full stream day is the first UTC day the host was up since before 00:00 (BASELINE). Off: unset the variable and restart; stored stream files stay and age out by retention. Discovery keeps reading `reddit_web` first, so turning the stream on cannot change a score until `reddit_web` has no usable points for a coin and window.

Owner probes (live behaviour is proven only on the owner's machine; planner and worker never run them):
- P-S1: start the worker with both switches on, host up since before 00:00 UTC. After 6 h run the probe `api/scripts/probe_pc_sources.py` with `--source reddit --stream-status` (local files only) and check: today's comments polls are about every 2 h, posts about every 6 h, entries seen is above 0.
- P-S2: after the first UTC midnight: the Sources row for Reddit shows the stream text when `reddit_web` has no usable points, and yesterday's `--stream-status` line shows both kinds settled (or `unknown`/`partial`, never 0 for missing data); at least one coin has a stored `reddit_stream` point or a stated missing reason.
- P-S3 (budget): at the end of one BASELINE UTC day read the `used` figure in the Reddit pace state and the sum of poll pages in the stream poll files; report both numbers (no secrets). This turns the 124-132 bound into a measurement.
- P-S4 (restart): restart the process in the afternoon; confirm that day sends no stream poll (log lines carry outcome codes only) and searches continue; confirm the next UTC day polls resume.
- P-S5: when a pause happens by itself, read its reason code on the Sources row; never provoke a block on purpose.

Cost estimate (UNVERIFIED, from the PLAN table row for W8c2 "opus, medium, 3-4" in the collector PLAN): about 3 to 6 USD for the EXECUTE session with `riper-opus`; PLAN session spend is not measured here. No invented figure beyond that range. Model: `riper-opus` for EXECUTE (owner choice, RT2).

## Acceptance Criteria

W-AC1. With the switch off, every existing test passes unchanged and the new off-by-default tests pass (no behaviour change).
W-AC2. With the switch on and BASELINE, a 24 h fake-clock run sends comments polls every 7200 s and posts polls every 21600 s (AC37 c), interleaved with the per-coin searches, no two requests closer than the configured minimum delay, one Reddit lock.
W-AC3. Stream and searches share the one Reddit counter and pause state; a 403 or 429 on either stops both for the UTC day; budget spent stops both; the honest user agent is used (AC24, rules 10, 15, 16).
W-AC4. Settled completed days are stored under `reddit_stream` only, frozen once stored, never 0 for missing data (AC3, AC4, AC14, AC26, AC30).
W-AC5. Each completed stream day has a completeness file and the Sources row text states settled, coverage, fetched, missing with reasons and newest age, `unknown` where absent (AC38, AC39).
W-AC6. DEGRADED sends no poll (Q1 d); state stays bounded over 90 simulated days; a restart resumes with no burst (AC40).
W-AC7. `sources.PC_STORES` equals `registry.PC_STORES`; a stream impl row does not raise.
W-AC8. The file-set check, the secret check and the targeted test run pass (Validate Contract G0-G9).

Phase Completion Rules: EXECUTE is complete only when every gate G0-G9 prints no FAIL, the EXEC-REPORT holds the red and green results with dates, the 11-heading report is written, ONE draft PR is open with the gate result in its body, and nothing stronger than status `review` is claimed. Anything not run is listed under "Tests NOT run", and every live behaviour is listed as an owner probe. No `canary`, zero or verdict logic is added.

## Implementation Checklist (EXECUTE)

RFC-1. Step 0: isolation, remote, fetch, collision re-check (`gh pr list --state open --json number,files`), G0, baseline failing ids.
RFC-2. Tests first (section 4), commit "test: red", record the red count.
RFC-3. `Stream` hooks (`_idle`, extra wake) with X behaviour unchanged; `RedditStream` switch, round, outcome `stream_due`, `next_poll_due`, `commit_open_days`.
RFC-4. `reddit_web.run_pass` `canary_days` only if the canary-slices test is red.
RFC-5. Prune of `_seen` and `_completeness` (W6), unless #198 already prunes them.
RFC-6. `sources.py` mapping and stream completeness text.
RFC-7. Green run, gates G0-G9, EXEC-REPORT, push, ONE draft PR.

## Touchpoints

`api/data/attention_pc_refresh.py` (Stream, RedditStream, AttentionPcWorker, start_from_env); `api/analytics/attention/sources.py` (PC_STORES, `_health`, `_completeness`); optionally `reddit_web.run_pass`. Read only: `reddit_stream.py`, `registry.py`, `pc_pace.py`, `discovery.json`.

## Public Contracts

- Environment: `SCREENER_ATTENTION_REDDIT_STREAM` exactly `1`.
- Worker: `AttentionPcWorker(reddit_stream=...)`; new outcome code `stream_due`; `Stream._idle` and the extra-wake hook default to today's behaviour.
- Files: `reddit_stream/_meta/_completeness/<day>.json` and `_seen`, written by `reddit_stream.py`; no new state file; budget and pause stay in `reddit_web`'s pace state.
- `DiscoverySourceHealth`, the Sources route shape, `web/`: unchanged.

## Blast Radius

Runtime: only the Reddit thread of the PC worker, only with the switch on. Sources route: the Reddit row when its impl is `reddit_stream`. Data: new files under `reddit_stream`. Discovery scores: unchanged unless `reddit_web` has no usable points. CI: the new tests run in the API job; the full suite is not changed.

## Verification Evidence

EXECUTE records in the EXEC-REPORT: baseline failing ids, red count (date, time), green count, G0-G9 output, the `git diff --name-only` list, the open-PR list used for collision, and the list of owner probes not run. All live statements stay UNVERIFIED until P-S1 to P-S5 are answered by the owner.

## Risks and Owner Questions (open)

Q1. Budget option. Recommended (d); see section 2. Needs the owner's choice before EXECUTE.
Q2. Switch as an environment variable (recommended: no #198 collision, one-line off) versus a config key `reddit_stream_enabled` (needs #198 merged and edits to `web_queries.py` and `attention_queries.json`).
Q3. The Reddit row reports only the first impl store with usable data, so with `reddit_web` first the stream's health is not on the Sources row; only `--stream-status` shows it. Accept, or add a second health line (needs a model and `web/` change: another slice).
Q4. AC14 says one method per window. W8f implemented "first store that yields a change for the coin and window", which is per coin, so two coins in one window can come from two methods (each coin's series stays one method). Accept, or add a window-level choice with `pick_impl` in `discovery.py`. Also: `reddit_impl_order` (collector config) and `source_impl.reddit` (Discovery) are two copies of one setting; this plan adds only a consistency test. Keep both, or remove one in a later slice.
Q5. A completed day with no stream entry has no completeness file and shows `unknown`. Accept, or write an empty completeness file (a worker write for a day the stream never touched).
Q6. Start EXECUTE after #198 is merged (recommended) or stack on its head.
Q7. Allow the conditional additive `canary_days` parameter in `reddit_web.run_pass` if the canary-slices test is red.
Q8. DEGRADED restart days leave the stream series missing for that day (consequence of option d). Accept.
Q9. The point-in-time rule drops stream days committed after D+1; accept as designed.

## Resume and Execution Handoff

Primary execute anchor: this file, sections 1-5 and the envelope below. Supporting files: `reddit_stream.py`, `attention_pc_refresh.py`, `sources.py`, the W8c2, W8e, W8e2, W8f and W8g reports in `process/general-plans/active/narrative-baskets_02-10-26/`, and the collector SPEC (AC14, AC26, AC30, AC37, AC38, AC39, AC40, rules 15 and 16). Main fills the three FILL_IN values, confirms Q1 to Q8 with the owner (at minimum Q1, Q2, Q6), confirms #198 is merged, spawns `riper-opus` with the envelope, and gives the explicit ENTER EXECUTE MODE for T222. Expect the worker's changes to also appear in the parent checkout (`task.isolation.apply` = true, OBSERVED 29-10-26): do not commit or publish them again.

### EXECUTE envelope (ready to paste)

````
ROLE: WORKER
You are a WORKER (agent riper-opus), direct lane. Do not spawn subagents. Phase: EXECUTE (RT2) for T222 W8c2w, Reddit stream wiring into the PC worker. You see no CLAUDE.md or AGENTS.md: these rules are binding and complete.

VALUES (Main replaces FILL_IN; plain text. If any still reads FILL_IN, stop and report): ORIGIN_URL=FILL_IN REPO=FILL_IN OWNER_Q1=FILL_IN (the owner's budget option, d unless changed) PR198_MERGED=FILL_IN (yes or no)

HARD RULES: The OWNER merges every PR; never merge or close a PR. Never push to main. Push only claude/w8c2w-stream-wiring. Never touch .github/**. Never write secrets, keys, IPs, cookies, account names, user-name home paths, or the repository owner/name slug or URL into any repo file, report, commit message or PR text (use $REPO and $ORIGIN_URL only on the command line). No live provider calls: tests use fakes, loopback only. Unknown = UNVERIFIED; missing data is never 0. No verdict logic. Nothing stronger than status review. No invented costs or IDs. Report in the 11-heading format. Stop and report on scope expansion, secrets, .github, a failing validator you did not cause, or a decision not given here.

READ FIRST: process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_PLAN_30-10-26.md (sections 1-5, Public Contracts). It is binding.

OWNED FILES ONLY: api/data/attention_pc_refresh.py; api/analytics/attention/sources.py; api/tests/data/test_attention_pc_refresh_stream.py (new); api/tests/data/test_attention_pc_refresh.py; api/tests/analytics/attention/test_sources_health.py; conditional: api/data/attention/reddit_web.py and api/tests/data/attention/test_reddit_web.py (only if test_canary_failure_not_repeated_across_search_slices_same_day is red); the new file w8c2w-stream-wiring_EXEC-REPORT_30-10-26.md in the plan folder. Nothing else (validate-contract G1 and G2 enforce it).

STEPS
0. Isolation (OBSERVED: task.isolation.apply = true): your changes are also auto-applied to the parent checkout and your branch does not exist there, so YOU publish, from your isolated checkout. If git remote -v is empty: git remote add origin "$ORIGIN_URL". Stash any copied parent changes with a named stash first. git fetch origin. If this fails, stop and report. If PR198_MERGED is not yes or G0 fails, stop and report. git switch -c claude/w8c2w-stream-wiring origin/main. gh pr list -R "$REPO" --state open --json number,files: any open PR touching an owned file, stop and report.
1. P=process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_PLAN_30-10-26.md ; cat "$P" | tr -d '\r' | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' | tee /tmp/w8c2w_gates.sh | bash -n ; no output means the syntax is fine. Run the second pytest command of Test Procedure and the existing-file part of the first; save the sorted FAILED node ids (cut at " - ") as the file BASEFAIL.
2. Write ALL red tests of PLAN section 4 first; run them; commit "test: red"; record "- Red ..., N failed" in the EXEC-REPORT.
3. Implement PLAN section 1 (W1-W10) for option d. Stream only in BASELINE, one thread, one lock, the shared reddit_web PcSource, switch SCREENER_ATTENTION_REDDIT_STREAM exactly 1, off by default. Do NOT edit reddit_stream.py, web_queries.py, attention_queries.json, discovery files, registry.py, pc_pace.py, models, routers, scripts or web.
4. Green: run both pytest commands; record "- Green ..., N passed". Fix, commit (2 fix cycles max, then stop and report).
5. Run the script with BASEFAIL and REPO exported; every gate must print no FAIL. Put its output in the EXEC-REPORT (11 headings; list owner probes P-S1 to P-S5 as not run).
6. Push only: git push origin claude/w8c2w-stream-wiring. Open ONE DRAFT PR: gh pr create -R "$REPO" --draft --base main --head claude/w8c2w-stream-wiring with the gate output in the body (no slug). Do not merge. If push or PR fails, stop and report.
7. Final message: results only; say your changes were also auto-applied to the parent checkout and the planner must NOT commit, push or open a PR from it.

STOP AND REPORT if: scope expansion, anything touching .github/, secrets, a newly failing validator, push or auth failure, isolation failure, an open PR touching an owned file.
````

Envelope size (LF, between the four-backtick fences): see REPORT heading 11 (cap 8,000 B, measured with `wc -c`).

ENTER EXECUTE MODE only after the owner has answered Q1, Q2 and Q6 and merged this plan PR and #198. RIPER-5 next step: EXECUTE, agent `riper-opus`.
