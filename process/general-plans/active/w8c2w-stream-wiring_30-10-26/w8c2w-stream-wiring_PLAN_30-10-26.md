---
name: w8c2w-stream-wiring-plan
description: "PLAN (T222, W8c2w) for wiring the merged Reddit stream-and-count method (reddit_stream, W8c2) into the PC worker: polls inside the Reddit pass, commit of settled days, completeness sidecar, per-day request-share record (`--stream-status` only, no Sources row), Discovery method order, and the shared 250/150 request budget question for the owner. Plan only."
date: 30-10-26
---

# W8c2w: Reddit stream wiring into the PC worker - PLAN

Date: 30-10-26
Task: T222 (next free ID: T221 is the highest in `git log --all` subjects and PR titles; no T222 exists anywhere; W8c2 and its PRs carry no T id)
Status: PLAN only, nothing in this file has been executed. Round 3 of plan fixes (third independent review of PR #200; #198 and #199 now merged): Q3 enforced (no Sources row, `sources.py` untouched, `reddit_stream` NOT added to `PC_STORES`), day-count rule across a BASELINE/DEGRADED change, G8 checks test identities, collision text rewritten for merged #198. Owner decisions of 30-10-26 recorded (round 2 of plan fixes after the second independent review of PR #200: one request-count path, default share 0.45, `share_exhausted` reporting, G8 runs the switch tests).
PLAN-REV: 5
Phase: PLAN (RIPER-5). EXECUTE agent: `riper-opus`. Risk tier RT2 (runtime behaviour of an unattended worker, no live provider calls in tests).
Complexity: COMPLEX (scheduler change in a threaded worker, shared request budget, health and Discovery readers, one owner decision)
Branch of this plan: `claude/w8c2w-stream-wiring-plan` (ONE draft PR, plan only). Branch of EXECUTE: `claude/w8c2w-stream-wiring`.

## Context

W8c2 (merged, PR #191) built the library `api/data/attention/reddit_stream.py` (method `reddit_stream`, method id `reddit_stream_feeds_v1`): `run_due`, `run_poll`, `due_kinds`, `commit_day`, `open_days`, `stream_status`, `pick_impl`, `Poll`, and the `reddit_stream_*` and `reddit_comments_*` config keys. Nothing calls it from the running worker. Today `RedditStream._pass` in `api/data/attention_pc_refresh.py` (lines 507-549) runs only `reddit_web.run_pass`. So the registry (`registry.SOURCE_IMPLS`, `registry.PC_STORES`) and `discovery.json` (`source_impl.reddit = [reddit_web, reddit_stream]`) already name a store that no process fills.

This slice wires the library into the worker, behind an owner-set switch that is OFF by default, and makes the result visible locally in two separate places: stream completeness and status come from the poll and completeness files (reported by `--stream-status`), and the private budget day record (`reddit_stream/_meta/_budget/<day>.json`) is NOT printed by `--stream-status` and is read by the owner by hand (owner decision 2026-10-31; no probe slice); no Sources row, Q3. It adds no collector logic: fetching, parsing, pacing, pause rules, paging, coverage and the AC3 zero rule stay in `reddit_stream.py` and `reddit_web.py`.

Goal: with the switch on, the Reddit stream of the worker polls the comments and posts feeds at the configured cadence between the per-coin searches in BOTH modes (BASELINE and DEGRADED), inside the one shared Reddit budget and under the stream's own share cap, commits every settled completed day under `reddit_stream`, writes the per-day completeness file, and `--stream-status` can report it. With the switch off, behaviour is byte-identical to today.

Non-goals: no change to `reddit_stream.py` (PR #198 owns it; #198 is merged), `discovery.json`, `discovery.py`, `probe_pc_sources.py`, `sources.py` (Q3: no Sources row; `reddit_stream` is NOT added to `PC_STORES`), `registry.py`, `pc_pace.py`, `web/`, `.github/`, the SPEC and PLAN of the collector (a later docs task, see Q4 waiver text); no X changes; no engagement enrichment (W8c3); no verdict logic. New in this round: the key `reddit_stream_budget_share` lives in `api/data/attention_queries.json` and `api/data/attention/web_queries.py` (+ its test), which this slice now owns.

## Verified inputs (measured in this PLAN session, read-only, `origin/main` = `3cd39e26`; re-read on `224caf56` in round 3 where marked)

| Fact | Where (main) | Consequence for the wiring |
|---|---|---|
| The worker runs two threads (X, Reddit); `PASS_LOCKS[REDDIT_SOURCE]` serialises a Reddit pass; the loop is `schedule -> _wait_until(due - 20 s) -> run_pass` | `attention_pc_refresh.py` 83, 293-304, 643-657 | Polls MUST go inside the Reddit stream's pass, under the same lock, so searches and polls never overlap and the 60-120 s request spacing holds for both. A second thread is rejected. |
| `Stream.run_pass` returns `"done"` when the search queue is empty, and `done`, `paused`, `budget_spent` are in `NEXT_DAY`, so the stream sleeps to 00:00 UTC + 20 s | 101, 322-348, 306-319 | With the stream on, an empty search queue must not end the day: the schedule needs a second wake source (next poll due). Without this the polls would run once a day. |
| `reddit_web.run_pass(... stop_at=...)` stops with `"host_stopped"` before a unit whose due time is at or after `stop_at`; items left stay queued | `reddit_web.py` 548-613 | The stream round can slice the search pass at the next poll due time with no change to `reddit_web`. |
| `reddit_web.run_pass` tries ONE canary per call and UTC day while `canary_ok(now)` is false | 560-586 | Slicing calls `run_pass` many times a day; a canary that keeps failing without a pause could be retried once per slice. Bounded by the slice count; the red test `test_canary_failure_not_repeated_across_search_slices_same_day` decides whether `reddit_web` needs one optional parameter (RFC-4). |
| Budget and pause state is ONE file per source: `pc_pace.state_path` accepts only `xsearch_web` and `reddit_web`; `reddit_source(config, degraded=...)` gives 250 (baseline) or 150 (degraded), non-adaptive | `pc_pace.py` 34-35, 146-149; `reddit_web.py` 330-345 | Stream polls MUST use the `PcSource` of `reddit_web` (`run_poll` already takes `src`). The stream has no state file of its own and must not get one. |
| `run_due(client, src, q, *, ledger, clock, sleep, rng, stop_at=None)` returns `StreamPass(outcomes, stop)` with stop in `done`, `host_stopped`, `paused`, `budget_spent` or a CollectorError reason; it ends early on pause or `budget_spent`; polls use `reddit_web.fetch_feed` (honest UA, no redirects, block rules) | `reddit_stream.py` 436-458, 9-12 | The honest user agent, pause rules and shared budget come for free if the worker calls `run_due` with the shared `src` and its own `client` (`worker.reddit_client()`). |
| `commit_day(day, q, ledger, *, now)` returns the completeness doc or None (day not complete); `open_days(now)` lists completed days with stream entries that are not settled (oldest first); `stream_status(now)` reads local files | 474-532, 549-572 | Wiring calls `commit_day` for every `open_days(now)` after each round. Repeat calls are safe by AC4 (frozen) and cheap (files only). A day that can never settle (round-2 finding I2) stays in `open_days` forever and is re-evaluated every round: bounded by the `_seen` retention (RFC-5). |
| `commit_day` stores through `web_evidence.commit_day` under source `reddit_stream`; `CANARY_OK = False`, so a covered real zero stays missing (`zero_no_canary`) | 47-51, 88 | No zero is ever stored by the stream. Any report of a stream day says missing or unknown, never 0. |
| `registry.SOURCE_IMPLS["reddit"]` and `registry.PC_STORES` already include `reddit_stream`; `sources.PC_STORES` (line 56) does NOT | `registry.py` 27-30; `sources.py` 56 | DECIDED (Q3): `reddit_stream` is NOT added to `sources.PC_STORES`; nothing in `sources.py` changes; the stream gets no Sources row. The drift between the two sets stays as it is (not this slice). |
| `sources._health(store_id, ...)` calls `pc_pace.state_path(store_id)` (raises `ValueError` for `reddit_stream`), reads `<store>_health.json` next to it, and `_completeness` parses the per-coin `reddit_web` completeness format | `sources.py` 108-190 | Four wiring problems would exist ONLY if `reddit_stream` were added to `PC_STORES`: (1) it is not in `sources.PC_STORES`; (2) `pc_pace.state_path('reddit_stream')` raises `ValueError`; (3) `_health` reads `<store>_health.json` beside that path; (4) `_completeness` parses the per-coin `reddit_web` format, not the stream's. Q3 means no Sources row, so `reddit_stream` is not added and none of the four applies. Guard test `test_sources_route_unchanged_with_stream_enabled` pins that the route keeps working. |
| Discovery: `source_impl.reddit = ["reddit_web", "reddit_stream"]` (discovery.json 75); `_weighted_source` takes the first store that yields a change for the coin and window; W8f deviation 5 states there is no separate `reddit_impl_order` key in Discovery | W8f report | The shipped order already equals SPEC AC14. Meanwhile `attention_queries.json` holds a second copy `reddit_impl_order` and `reddit_stream.pick_impl` has no production caller. Two sources of truth: see Q4. |
| Evidence `known_at_time` drops points whose `collected_at` is after D+1 | W8f report 17, 58 | A stream day committed later than D+1 (host off) is excluded from point-in-time history. Honest, by design; stated here so nobody calls it a bug. |
| Existing worker switches are `SCREENER_ATTENTION_PC_WORKER`, `SCREENER_ATTENTION_PC_LOG_FILES`, `SCREENER_ATTENTION_PC_LOG_MAX_BYTES` (grep of `api/data` and `api/analytics` on `origin/main`, 30-10-26) | `attention_pc_refresh.py` | The new switch `SCREENER_ATTENTION_REDDIT_STREAM` matches the prefix; no other naming is introduced. |

### Code that differed on `origin/claude/w8c2-reddit-stream` (PR #198, now MERGED on 30-10-26; dated pre-merge comparison, kept for the facts)

Compared with `git diff origin/main...origin/claude/w8c2-reddit-stream` and by grep of the head. #198 touches: `reddit_stream.py`, `web_queries.py`, `attention_queries.json`, `probe_pc_sources.py`, `test_reddit_stream.py`, `test_web_queries.py`, the W8c2 REPORT. What changes for this plan:

- New keys `reddit_stream_poll_retention_days` (30) and `reddit_stream_max_pages_per_poll` (10): one poll sends at most 10 requests (fresh, reconnecting and resumed pages); truncated polls keep their cursors and resume (`Poll.runs`).
- Signature changes: `stored_polls(until, retention_days)` and `stream_status(now, q, *, days=3)` (the probe call becomes `stream_status(clock(), web_queries.load())`). UNCHANGED on the #198 head (checked by grep of the `def` lines): `run_due`, `run_poll`, `due_kinds`, `commit_day`, `open_days`, `read_completeness`, `pick_impl`. This plan calls only the unchanged ones.
- `prune_polls(now, retention_days)` runs after every poll inside `reddit_stream` (E2); the worker must NOT prune `_polls`. VERIFIED on `origin/main` (`224caf56`, 30-10-26, `reddit_stream.py` lines 47-48 and a grep of `prune`): only the poll files are pruned ("the seen ids, completeness files and item ledger are other stores and stay"); the worker therefore prunes `_seen` and `_completeness` itself (W6, RFC-6).
- VERIFIED 30-10-26 (planner, `git ls-tree -r origin/claude/w8c2-reddit-stream`, 0 matches; head `403bc676`): the #198 branch has NO `api/data/attention_pc_refresh.py`; the file arrives with `main`. A gate dry run against the #198 head therefore cannot read the worker (G8), as expected.
- VERIFIED 30-10-26 (reading `reddit_stream.py`, `run_poll` and `Poll`, on the #198 head) which sent requests are recorded where:
  - `src.spend(1)` and `requests += 1` run immediately before EVERY request `run_poll` sends: first page, paging, reconnecting and resumed pages, and requests that then fail. A failed request is not retried inside `run_poll`. `PollOutcome.requests` is returned on every normal path, including a failed request (`PollOutcome(kind, error.reason, error.status, requests)`).
  - NOT every sent request is in a poll record. `Poll` has no `requests` field; `Poll.pages` counts only pages that made progress (a failed, empty, no-progress or dead-cursor request adds nothing); a poll whose requests all fail stores no `Poll` at all; an empty feed stores `pages=0` for its one request; a poll whose second page fails stores `pages=1` for two requests. An unexpected exception (`except Exception: raise`) leaves `run_poll` after `src.spend(1)` with no `PollOutcome`, so a sum of returned outcomes misses it too.
  - Consequence: neither the poll records nor the sum of `PollOutcome.requests` can be the counter. W11 specifies the one path that sees every request.

DECIDED (owner, 30-10-26, Q6): EXECUTE starts only after #198 is merged to `main` (gate G0); #198 is merged, G0 passes on current `origin/main`. Reasons: the wiring's page-cap and retention behaviour is the one the owner approved in #198; the budget bound below depends on the page cap; and the new key `reddit_stream_budget_share` is added to `web_queries.py` and `attention_queries.json`, which #198 also edits, so the slice must be based on the merged result. No stacking on the #198 head.

## 1. What must be wired (design)

All file edits are listed in section 3. Names are proposals; EXECUTE may rename if it keeps the contracts in section "Public Contracts".

W1. Switch (decided Q2). The environment variable `SCREENER_ATTENTION_REDDIT_STREAM` exactly `1` (same prefix and style as the existing `SCREENER_ATTENTION_PC_WORKER`, `SCREENER_ATTENTION_PC_LOG_FILES`, `SCREENER_ATTENTION_PC_LOG_MAX_BYTES`, read by `start_from_env` the way `FLAG_ENV` is read; tests and workflows never set it) turns the stream on; absent or any other value: off. `AttentionPcWorker(..., reddit_stream: bool | None = None)`; `None` reads the environment in `start_from_env`. Off: zero stream requests, zero stream store writes, schedule and outcomes byte-identical to today. The budget share is a separate config key (W11), because the owner decided option (b).

W2. Stream round inside `RedditStream._pass` (under the existing Reddit lock), only when the stream is ON (BOTH modes, BASELINE and DEGRADED; decided Q1) and the ledger exists:
1. `reddit_stream.run_due(client, share_src, q, ledger=ledger, clock=w.clock, sleep=w._sleep, rng=self.rng, stop_at=stop_at)` where `share_src` is the share wrapper of W11 around the SAME shared `src` (`reddit_source`, shared 250/150 budget and pause state), with the same `client` (`reddit_web.make_client`: honest user agent, no redirects, no proxy) and the worker's interruptible `_sleep`. `paused` and a spent SHARED budget end the round and the pass with that outcome (same codes as the search pass); `host_stopped` ends it with `host_stopped`; a spent SHARE ends only the stream round for the UTC day (W11), the search slice still runs.
2. `commit_open_days`: for each day in `reddit_stream.open_days(now)`: `reddit_stream.commit_day(day, q, ledger, now=now)`; an exception is logged as `attention pc reddit_stream commit skipped: <ExceptionClass>` (class name only) and never ends the pass.
3. The search slice: `reddit_web.run_pass(..., stop_at=min(stop_at, next_poll_due))` over the same `queue(q, syms)`. If it returns `host_stopped` while the worker's own `stop_at` is not reached, the pass returns the new outcome `stream_due` (not in `NEXT_DAY`): the schedule wakes at the next poll or the next search, whichever is first.
4. The stream round runs BEFORE the search slice, so a poll that is due is never delayed by a long search queue, and searches resume at the configured spacing because `run_pass` derives its first due time from `src.last_unit_at()` (polls update it through `PcSource`).

W3. Schedule. `Stream.run_pass` gets one hook `_idle(q, syms)` (default: `not self.queue(q, syms)`), and `Stream._behind` one hook for an extra wake time (default None). `RedditStream` overrides them so that with the stream ON and the polls not capped for the day: an empty search queue does not return `done`; `done` and `stream_due` both schedule `min(next search due, next poll due)`; paused, shared budget spent, poll caps reached or stream share spent (polls only) wait for the next UTC day for the polls. `next_poll_due(q, now)` is computed in the worker from `reddit_stream.read_polls` and the public config (interval per kind, `reddit_stream_polls_per_day_cap`), without touching `reddit_stream.py`; the property test `test_next_poll_due_matches_due_kinds` pins it to `due_kinds`. A restart (`_behind`) never sends a burst: each overdue kind is polled at the normal spacing, one request per 60-120 s (AC40), pinned by `test_behind_restart_schedules_next_poll_at_spacing_not_immediately_for_all_due_kinds`. X is untouched (hooks default to today's behaviour).

W4. Degraded mode (decided Q1 option b). In DEGRADED (restart day, budget 150) the stream polls like in BASELINE, but its requests per UTC day are capped by the share (W11): 67 at the default 0.45, so the searches keep the other 83. The mode switch needs no new rule: `worker.mode(now)` already follows host uptime, never an hour of the day (AC28). A poll cut by the share is truncated and continued by the next poll under the existing E1/E3 rules (cursors kept), never dropped; the stream day it belongs to stays unsettled, so its coin-days are missing, never 0.

W5. Open days and completeness. `commit_day` writes `reddit_stream/_meta/_completeness/<day>.json` (coverage per feed kind, polls, settled, partial, fetched, missing reasons, `gap_unreachable`, `canary_ok: false`) when the day is complete (AC38). A completed day for which the stream never saw an entry has no file; `--stream-status` then shows its numbers as unknown (None), never 0 (Q5). Only the worker's day record (W12) says `share_exhausted`; an absent file alone is never evidence that the share ran out.

W6. Retention (AC40). `RedditStream._prune` also prunes `reddit_stream/_meta/_seen` and `_completeness` day files older than `ledger_retention_days` (default 400) with the existing `_prune_day_files`, using the public `seen_path(day).parent` and `completeness_path(day).parent`; `_polls` is #198's job. The worker's `_budget` day files (W11) are pruned the same way. No new directory grows without a bound.

W7. Ledger. `worker.reddit_ledger()` may be None (salt error). Then the stream stays OFF for the pass with reason code `ledger_unavailable` in the log, and searches continue as today (`reddit_web.run_pass` accepts `ledger=None`). Nothing is stored without the ledger.

W8. Logs. Only the source, an outcome or reason code and the exception class name; never a URL, subreddit set, entry id or author (the existing `_DropRedditRequestLine` filter stays installed on the client).

W9. Sources: NO CHANGE (owner Q3, accept). Stream health is shown only by `--stream-status` (`probe_pc_sources.py`, not owned, not changed). `reddit_stream` is NOT added to `sources.PC_STORES`; `sources.py`, `test_sources_health.py` and the Sources models/`web/` are untouched and the stream gets no Sources row, text or health line. The four wiring problems of the `sources._health` section (not in `PC_STORES`; `pc_pace.state_path('reddit_stream')` raises `ValueError`; `<store>_health.json`; per-coin completeness format) matter only if the store were added, so none is addressed. `share_exhausted` and the counts are written by W12 into the worker's stream day record (`reddit_stream/_meta/_budget/<day>.json`) and, with the library's completeness file, are the stream's local day data. DISPLAY NOTE (UNVERIFIED, flagged to the owner): `reddit_stream.stream_status` reads only polls, seen ids and completeness files and the probe prints its result; neither file is owned here, so this slice does not claim that `--stream-status` prints the day record; the owner reads the record by hand in P-S3 and a later slice may add it to the probe. Guard: `test_sources_route_unchanged_with_stream_enabled` (the Sources route and the Reddit row are identical with the stream on and off).

W10. Discovery method choice (AC14). No `discovery.py` or `discovery.json` change: `source_impl.reddit` is already `["reddit_web", "reddit_stream"]`. This slice only adds a guard test that `reddit_impl_order` in the collector config equals `source_impl.reddit`, and the test that the stream store is used when `reddit_web` has no usable points (Q4 decided: per-coin method choice stays).

W11. Stream budget share and its ONE counting path (decided Q1 option b; default 0.45 decided by the owner, 30-10-26). New config key `reddit_stream_budget_share`, a float fraction in (0, 1], default `0.45`, in `attention_queries.json` and in `REDDIT_STREAM_DEFAULTS`, the dataclass and `_stream_value` of `web_queries.py` (validation rejects 0, negatives, bool, values above 1, text and None). Cap in requests per UTC day: `stream_cap = floor(share * configured_budget)` with the budget of the CURRENT mode: 112 of 250 (BASELINE), 67 of 150 (DEGRADED) at the default (mode changes inside a UTC day: W11b).
Counting path (round 2; ONE path, no second sum): every request the stream sends passes through `share_src.spend(n)`, because `run_poll` calls `src.spend(1)` immediately before each request (fresh, reconnecting and resumed pages, failed requests, and a request that ends in an unexpected exception; see the verified facts above). The wrapper is the only code that changes the stream's count. `spend(n)` first writes the new count to the day file `reddit_stream/_meta/_budget/<UTC day>.json` (atomic write, same style as `PcSource._save`; key `requests`), then delegates `src.spend(n)`; if the delegate raises `BudgetSpent` the wrapper restores the count. A crash between the two steps can over-count the stream by one request (conservative for the cap), never under-count, and never touches the shared counter. Restart: the count is read from the file, so a new worker continues it; a new UTC day starts at 0 (day = the UTC day of `src.clock()`). The count is NOT derived from poll records (they miss failed, empty and dead-cursor requests) and NOT summed from returned `PollOutcome.requests` (it would double count with `spend` and miss an exception); `PollOutcome.requests` is used only by tests as an independent cross-check. This counter is a stream cap, not a `PcSource` state file; it is pruned with retention (W6).
`share_src` delegates everything else to the shared `src` and changes three methods: `can_spend(n)` is true only when `src.can_spend(n)` and `stream_requests + n <= stream_cap`; `spend(n)` as above (it also raises `BudgetSpent` without delegating when `stream_requests + n` is above the current mode's cap); `mark_spent()` does NOT mark the shared budget spent when the share is the reason (searches keep the rest), and delegates when the shared budget itself is spent. A poll that runs into the cap is truncated, keeps its cursor and is continued by the next poll (E1/E3, `Poll.runs`); because the polls of the rest of the day are also refused, the continuation happens at the first poll after 00:00 UTC. Nothing is dropped. The share is a cap, not a reservation: requests the stream does not use stay available to the searches, and the shared `reddit_web` counter (`used`) stays the authority for the day's total in both modes.
W11b. Mode change inside a UTC day (round 3). The mode follows process uptime (`worker.mode(now)`), not the day, so a day can start BASELINE (cap 112 of 250), count e.g. 100, then restart into DEGRADED (cap 67 of 150), or the reverse. Rule: the persisted day count is never refunded and never rescaled. Before EVERY request the wrapper recomputes the cap of the current mode and refuses unless `count < cap_of_current_mode` (for one request: `count + 1 <= cap`); a request is never started when `count >= current cap`. The count itself is not retroactive: requests already sent stay valid. So after BASELINE to DEGRADED with a count above the new cap (100 against 67) the stream sends nothing more that UTC day and the polls wait for the next UTC day; after DEGRADED to BASELINE the remaining BASELINE cap applies (112 minus the count). The shared `reddit_web` budget (250 BASELINE, 150 DEGRADED, `used`) remains the hard limit in both modes: every stream request also passes the shared `can_spend`, the share only limits how much of it the stream may take. Tests: `test_budget_baseline_to_degraded_same_utc_day_count_not_refunded_stream_sends_nothing_more`, `test_budget_degraded_to_baseline_same_utc_day_remaining_baseline_cap_applies`, `test_stream_never_starts_a_request_when_count_at_or_above_current_mode_cap`, `test_shared_reddit_web_budget_stays_hard_limit_in_both_modes`.
W12. Share-exhausted record (round 2). The same day file carries `{"day", "requests", "cap", "budget", "share_exhausted", "exhausted_at"}`: `cap` and `budget` are those in force at the moment of exhaustion (112 of 250 or 67 of 150 at the default), `share_exhausted` is set to true (never cleared in that UTC day) by the wrapper when a `can_spend` or `spend` is refused BECAUSE of the share and not because the shared budget is spent (a spent shared budget keeps today's `budget_spent` reason). It is the stream's day record of the share (local file; no Sources row, Q3; read by the owner in P-S3), so a day for which the share ran out is recorded as `share_exhausted` with cap and count and is distinct from a day with no entry; an absent completeness file alone is never read as evidence that the share ran out, and neither is read as 0. The file exists only when the stream is on and is pruned with retention (W6).

## 2. Shared Reddit request budget: DECIDED Q1 (option b, owner, 30-10-26)

The one Reddit counter (`reddit_web` state) is 250 requests per UTC day in BASELINE and 150 in DEGRADED. Per-coin searches need about 75 requests for yesterday plus 1 canary (75 coins; backfill of up to 5 earlier days comes after yesterday and is the first thing cut).

Stream cost per UTC day (bound, from the merged code and the #198 page cap): comments 12 polls (interval 7200 s) times at most 10 requests each, posts 4 polls (interval 21600 s; the cap key allows 12) which never page: 12 x 10 + 4 = 124 with the interval, 12 x 10 + 12 = 132 if the posts cap and not the interval were the limit. The typical day is far lower (a poll that reaches its floor on page 1 costs 1; 16 requests); the bound is what the budget must survive. All figures are from code reading, UNVERIFIED until the owner's spend probe P-S3.

DECIDED: option (b), default share 0.45 (owner, 30-10-26). A new key `reddit_stream_budget_share` caps the stream's requests per UTC day inside the shared budget in BOTH modes; the searches keep the rest. Polls beyond the share are truncated and continued by the next poll under the existing E1/E3 rules (cursors kept), never dropped; the stream's own day stays unsettled or partial and its coin-days missing, never 0. Mechanism: W11 (one counting path) and W12 (reporting).

Default value DECIDED by the owner (30-10-26): `0.45`. Arithmetic with `stream_cap = floor(share * budget)` (0.45 x 250 = 112.5, floor 112; 0.45 x 150 = 67.5, floor 67):

| Mode | Budget | Stream cap at 0.45 | Stream bound (124-132) | Left for searches if the stream uses its whole cap | Yesterday needs |
|---|---|---|---|---|---|
| BASELINE | 250 | 112 | cut by 12 (124) to 20 (132): the last polls of the UTC day are truncated, not dropped | 138 (backfill about 62) | 76 |
| DEGRADED | 150 | 67 | cut by 57 to 65 (comments polls truncated, continued next day) | 83 (covers the 76 with 7 to spare) | 76 |

Tradeoff, stated as an EXPECTED consequence (owner chose 0.45 knowing it): the searches (the primary series, first in the order) are protected in both modes, at the price that in BASELINE a day on which the stream runs near its code bound (124-132 requests) hits the cap at 112. The polls refused after that are truncated, their cursors stay, and the first poll after 00:00 UTC continues them; nothing is dropped. Whether the continuation can still cover the missing tail of day D depends on how deep the feed is reachable and is UNVERIFIED until P-S3. So the stream series may lag or show a day as missing or partial under the E1 rule (never 0), and the day record says `share_exhausted` with cap and count for that day (W12). The typical day (stream about 16 to 40 requests, a poll that reaches its floor on page 1 costs 1) is far under the cap, and because the share is only a cap, unused stream requests stay available to the searches. The owner can raise the key in the JSON without code. The real spend is UNVERIFIED until P-S3. Tests: `test_baseline_cap_reached_mid_day_truncates_remaining_polls_next_utc_day_continues_nothing_dropped`, `test_cap_truncated_day_is_missing_or_partial_never_zero`.

Options, as compared (kept for the record):

- (a) No reserve. Rejected: in DEGRADED the polls (due first) can spend most of 150 before the searches run, so the primary series (`reddit_web`, first in the order) loses most coin-days on every restart day.
- (b) New key `reddit_stream_budget_share` with a stream-spend counter. CHOSEN by the owner. Cost: one key, validation and a day counter (W11), and an EXECUTE start after #198 (files shared with #198).
- (c) Searches first, stream with the remainder. Rejected: the polls start late in the day; the comments feed is deep only to the page cap, so late polls leave unreachable holes; needs a two-phase scheduler, the most complex option.
- (d) Stream polls only in BASELINE. Rejected by the review and the owner: it conflicts with the SPEC (AC30, rule 10 and AC24 require the stream to poll under the degraded 150 budget too), and a restart day would have no stream data at all.

## 3. File ownership and collision proof

EXECUTE owned files (option b):

| File | Change |
|---|---|
| `api/data/attention_pc_refresh.py` | switch, worker argument, `Stream` hooks (`_idle`, extra wake), `RedditStream` round, share wrapper and day counter (W11), `next_poll_due`, `commit_open_days`, prune of the stream day files |
| `api/data/attention/web_queries.py` | key `reddit_stream_budget_share`: default, dataclass field, validation (after #198 is merged) |
| `api/data/attention_queries.json` | `"reddit_stream_budget_share": 0.45` |
| `api/tests/data/attention/test_web_queries.py` | key tests (default, validation, absent key) |
| `api/data/attention/reddit_web.py` | CONDITIONAL, only if `test_canary_failure_not_repeated_across_search_slices_same_day` is red on the unchanged code (decided Q7): one optional keyword parameter `canary_days` of `run_pass`, default behaviour unchanged |
| `api/tests/data/test_attention_pc_refresh_stream.py` | NEW: the stream wiring tests |
| `api/tests/data/test_attention_pc_refresh.py` | only if an existing worker test needs the new hook signature; no assertion weakened |
| `api/tests/data/attention/test_reddit_web.py` | CONDITIONAL with `reddit_web.py` |
| `process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_EXEC-REPORT_30-10-26.md` | NEW: the EXECUTE report |

Not owned (never edited): `api/analytics/attention/sources.py` and `api/tests/analytics/attention/test_sources_health.py` (Q3: `reddit_stream` is NOT added to `PC_STORES`; run, never edited), `api/scripts/probe_pc_sources.py`, `api/data/attention/reddit_stream.py`, `discovery.json`, `api/analytics/attention/discovery.py`, `registry.py`, `pc_pace.py`, `api/models/**`, `api/routers/**`, `api/scripts/**`, `web/**`, `.github/**`, `.claude/**`, the collector SPEC and PLAN, state docs, other plans. The SPEC waiver (Q4) is a proposed owner-decision line for a later docs task, not a file edit here.

Collision proof, re-snapshotted on 30-10-26 (round 3) with `gh pr list --state open --json number,title,isDraft,files` (read-only; dated, it ages, which is why G10 repeats it at EXECUTE start). ONE open PR: #200 (this plan, draft): only this plan folder's PLAN and REPORT (the EXEC-REPORT is a different file). Intersection with the owned set: empty. #198 (stream fix rounds) and #199 (docs catch-up 2) are MERGED (30-10-26) and are no longer in any open PR; G0 (the #198 page cap key on `origin/main`) now passes.

Historical note (dated 30-10-26, before the merge, kept): #198 touched `reddit_stream.py`, `web_queries.py`, `attention_queries.json`, `probe_pc_sources.py`, `test_reddit_stream.py`, `test_web_queries.py` and the W8c2 REPORT, which intersected three files this slice owns; that was the reason for G0. #199 touched only process docs.

Peers: no open PR other than #200 touches the owned set. G10 re-reads the open-PR list at EXECUTE start and again before the PR; any open PR other than the EXECUTE PR itself that touches an owned file stops the worker.

Read dependencies on files that #198 changes, with the signature facts above: `reddit_stream.run_due`, `run_poll`, `commit_day`, `open_days`, `seen_path`, `completeness_path`, `read_polls`, `read_completeness` (unchanged by #198, now merged) and the config fields `reddit_comments_poll_interval_s`, `reddit_posts_poll_interval_s`, `reddit_stream_polls_per_day_cap`, `reddit_stream_max_pages_per_poll` (see G0). `run_poll` uses only `src.can_spend`, `spend`, `mark_spent`, `is_paused`, `earliest_next`, `stamp_attempt`, `record_unit`, `warn`, `last_unit_at`, `clock` (read on the #198 head, merged); the share wrapper delegates all of them.

## 4. Red-first tests (names, by acceptance criterion)

All in `api/tests/data/test_attention_pc_refresh_stream.py` unless noted; fake clock, fake httpx transport, loopback only, no live call. SPEC refers to `narrative-baskets-xreddit-collector_SPEC_21-10-26.md`.

| AC | Test names |
|---|---|
| AC37 (c) baseline poll cadence | `test_baseline_24h_polls_comments_every_7200s_posts_every_21600s`; `test_polls_and_searches_never_closer_than_min_delay`; `test_search_slice_resumes_at_spacing_after_poll`; `test_empty_search_queue_still_polls_stream`; `test_done_outcome_with_stream_on_waits_for_next_poll_not_next_day`; `test_next_poll_due_matches_due_kinds` (property: due at the computed time, not one second before) |
| AC37 degraded, AC28, AC30 (decided Q1 b: the stream also polls in DEGRADED) | `test_degraded_mode_polls_stream_within_share`; `test_degraded_stream_never_starts_a_request_once_count_reached_67_at_default_share`; `test_mode_switch_stream_starts_next_utc_day_when_up_since_midnight`; `test_no_fixed_utc_hour_in_stream_schedule` |
| Mode change inside a UTC day (W11b, round 3) | `test_budget_baseline_to_degraded_same_utc_day_count_not_refunded_stream_sends_nothing_more` (BASELINE, count 100, restart into DEGRADED: cap 67, the stream sends nothing more that UTC day, the count stays 100); `test_budget_degraded_to_baseline_same_utc_day_remaining_baseline_cap_applies` (DEGRADED, count 40, restart into BASELINE: 72 more requests allowed, then refusal at 112); `test_stream_never_starts_a_request_when_count_at_or_above_current_mode_cap`; `test_shared_reddit_web_budget_stays_hard_limit_in_both_modes` |
| Switch and no-regression | `test_stream_off_by_default_runs_only_search_pass_as_before`; `test_stream_flag_only_exact_one_enables` (values `1` on; unset, empty, `0`, `true`, ` 1`, `2` off); `test_start_from_env_without_variable_means_stream_off`; `test_stream_off_leaves_schedule_outcomes_unchanged`; `test_env_off_sends_zero_stream_requests_and_writes_no_stream_store_files` (G8 runs the first four of these names) |
| Budget share, new key (decided Q1 b, default 0.45) | in `test_web_queries.py`: `test_budget_share_default_is_0_45`; `test_budget_share_rejects_zero_negative_bool_over_one_text_and_none`; `test_budget_share_accepts_one_and_fractions`; `test_budget_share_absent_key_uses_default`. In the stream test file: `test_stream_cap_is_112_baseline_and_67_degraded_at_default_share`; `test_stream_spend_capped_by_share_in_baseline_250`; `test_stream_spend_capped_by_share_in_degraded_150`; `test_poll_cut_by_share_is_truncated_keeps_cursor_not_dropped`; `test_share_cut_poll_continues_at_first_poll_next_utc_day`; `test_share_spent_does_not_mark_shared_budget_spent`; `test_searches_keep_the_remainder_when_share_is_spent`; `test_unused_stream_share_stays_available_to_searches`; `test_stream_spend_counter_survives_restart_same_utc_day`; `test_stream_spend_counter_resets_next_utc_day`; `test_baseline_cap_reached_mid_day_truncates_remaining_polls_next_utc_day_continues_nothing_dropped`; `test_cap_truncated_day_is_missing_or_partial_never_zero` |
| One counting path (W11, no double count) | `test_stream_counter_equals_requests_sent_no_double_count` (N requests through the fake transport: stream counter N, shared `used` delta N, sum of `PollOutcome.requests` N); `test_stream_counter_counts_failed_empty_and_dead_cursor_requests_that_poll_records_miss` (the counter equals the transport count while the sum of `Poll.pages` is lower); `test_stream_counter_after_restart_continues_from_file_no_double_count` (N, new worker, N still, then M more gives N+M); `test_failed_request_counts_once` (403, 429 and 500 on a page: counter +1, shared +1, no retry); `test_unexpected_exception_in_poll_still_counts_its_request_once`; `test_spend_refused_by_shared_budget_does_not_increment_stream_counter` |
| Share-exhausted record (W12; local day record only, no Sources row) | `test_share_exhausted_recorded_with_cap_and_count_distinct_from_no_entry`; `test_share_exhausted_not_set_when_shared_budget_is_the_reason`; `test_share_exhausted_day_without_completeness_file_is_missing_never_zero`; `test_share_exhausted_record_carries_cap_and_budget_of_current_mode` |
| Shared budget and pause (SPEC rules 10, 15, 16; AC24) | `test_stream_and_search_requests_count_in_one_budget`; `test_budget_spent_by_polls_stops_searches_until_next_utc_day`; `test_pause_by_poll_403_pauses_searches_same_day`; `test_pause_by_poll_429_pauses_searches_same_day`; `test_pause_by_search_403_stops_polls_same_day`; `test_pause_by_search_429_stops_polls_same_day`; `test_stream_requests_use_honest_user_agent_no_redirect_no_proxy` |
| Lock and spacing | `test_poll_runs_under_reddit_pass_lock_never_beside_search`; `test_x_stream_not_blocked_by_reddit_poll` |
| Canary (decided Q7) | `test_canary_failure_not_repeated_across_search_slices_same_day` (if red, add `canary_days`; then `test_run_pass_default_canary_behaviour_unchanged` in `test_reddit_web.py`) |
| AC14, AC26 (own store) | `test_stream_values_stored_under_reddit_stream_never_reddit_web`; `test_reddit_impl_order_equals_discovery_source_impl_reddit`; `test_stream_store_used_when_reddit_web_has_no_usable_points` (in the stream test file; no existing Discovery or Sources test is edited) |
| AC4, AC30 (commit, frozen) | `test_open_day_committed_when_settled_and_not_before`; `test_open_days_reevaluated_each_round_until_settled`; `test_second_commit_of_settled_day_changes_nothing`; `test_unsettled_or_below_coverage_day_writes_no_zero`; `test_commit_exception_logged_by_class_only_pass_continues` |
| AC38 (per-source-day completeness: attempted, fetched, missing with reason counts) | `test_stream_completeness_file_written_for_complete_day`; `test_stream_day_record_has_attempted_fetched_and_missing_reason_counts`; `test_stream_day_record_attempted_equals_fetched_plus_missing`; `test_stream_day_record_missing_reason_counts_sum_to_missing`; `test_stream_day_without_completeness_file_reports_none_never_zero` (library `stream_status`, no Sources row) |
| AC39 (health; Q3: `--stream-status` only, Sources route unchanged) | `test_sources_route_unchanged_with_stream_enabled` (guard: with the switch on and stream store files present, the Sources route and the Reddit row equal those with the stream off, no exception); `test_sources_pc_stores_still_excludes_reddit_stream` (`sources.PC_STORES` is unchanged and `sources.py` is not edited) |
| AC29 (ledger) | `test_ledger_unavailable_holds_stream_searches_continue`; `test_polled_entries_reach_the_ledger_once_per_id` |
| AC40 (unattended, restart) | `test_stream_day_files_pruned_by_ledger_retention_days`; `test_restart_resumes_polls_without_burst`; `test_behind_restart_schedules_next_poll_at_spacing_not_immediately_for_all_due_kinds` (explicit `_behind` assertion: after a restart with several kinds overdue, the first request is at or after the normal spacing and consecutive requests are 60-120 s apart); `test_restart_with_overdue_kinds_sends_one_poll_per_spacing_not_a_burst`; `test_ninety_day_ticks_state_bounded_with_stream_on`; `test_host_stop_leaves_poll_kind_due_for_next_window` |
| Rule 16 (quality over speed) | `test_pass_that_cannot_finish_in_its_window_continues_next_window_no_poll_dropped`; `test_host_stop_mid_round_keeps_every_due_poll_for_next_window`; `test_search_queue_leftover_resumes_next_window_in_order_no_coin_skipped`; `test_slow_day_never_trades_completeness_for_speed` |
| Privacy | `test_logs_hold_no_url_subreddit_id_or_author_with_stream_on` |

Red-first rule: write all tests first, run the test files, record the number failing for the right reason (missing hook, missing outcome, unknown key), commit that state, then implement. The report lists the red count and the green count.

## 5. Tests, gates and Validate Contract

Test Procedure (RT2, from the repo root, Git Bash, no live provider call):

```
UV_FROZEN=1 uv run --project api pytest api/tests/data/test_attention_pc_refresh_stream.py api/tests/data/test_attention_pc_refresh.py api/tests/analytics/attention/test_sources_health.py api/tests/data/attention -q -p no:cacheprovider
UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention api/tests/routers/test_discovery.py api/tests/routers/test_discovery_history.py -q -p no:cacheprovider -rfE
```

Regression gate: before any edit, run the second command and the first (existing files only) and save the failing node ids; after the work the set of failing ids must have no new member. The W8e report records 40 pre-existing router failures on the Windows host in the full router directory, so only a diff of ids is meaningful, never a count. `test_sources_health.py` is RUN as a regression file, never edited (Q3). `process/context/tests/all-tests.md` is the test index; `process/context/all-context.md` is the context router. Also run the whole `api/tests` once after the last commit, record the result and judge failures by the id diff; if it is not run, list it under "Tests NOT run".

## Validate Contract

Run from the repository root in the EXECUTE checkout after the last commit. `BASE` is `origin/main`. `REPO` MUST be exported by the worker (gate G3 fails without it) and is never written into any file. `ALLOW_PR` is the number of the EXECUTE PR once it exists (empty before). Every gate prints FAIL and sets a non-zero exit; each can fail: git or gh errors, a missing input file, a pytest exit code other than 0 or 1, a summary without a positive passed count, and an empty after-file with failing exit all fail. The script avoids `grep -q` inside pipelines (pipefail would turn a SIGPIPE into a false FAIL) and works through files.

```bash
set -u
set -o pipefail
BASE="${BASE:-origin/main}"; RC=0; T="$(mktemp -d)"
D=process/general-plans/active/w8c2w-stream-wiring_30-10-26
R="$D/w8c2w-stream-wiring_EXEC-REPORT_30-10-26.md"
OWNP='api/data/attention_pc_refresh\.py|api/data/attention/reddit_web\.py|api/data/attention/web_queries\.py|api/data/attention_queries\.json|api/tests/data/test_attention_pc_refresh_stream\.py|api/tests/data/test_attention_pc_refresh\.py|api/tests/data/attention/test_reddit_web\.py|api/tests/data/attention/test_web_queries\.py|process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_EXEC-REPORT_30-10-26\.md'
bad() { echo "FAIL: $1"; RC=1; }
git diff --name-only "$BASE"...HEAD > "$T/files" || bad "G1 git diff names failed"
git diff "$BASE"...HEAD > "$T/diff" || bad "G1 git diff failed"
grep '^+' "$T/diff" > "$T/added"
# G0 precondition: the #198 page cap is on BASE (#198 merged 30-10-26; passes on current origin/main; run before EXECUTE and again before the PR)
git show "$BASE:api/data/attention/web_queries.py" > "$T/wq" || bad "G0 cannot read web_queries.py on $BASE"
grep -q 'reddit_stream_max_pages_per_poll' "$T/wq" || bad "G0 PR 198 not merged on $BASE"
# G1 file-set check: every changed file must be in the owned set, and the set must not be empty
grep -Ev "^($OWNP)$" "$T/files" > "$T/extra"
[ -s "$T/extra" ] && bad "G1 files outside the owned set: $(tr '\n' ' ' < "$T/extra")"
[ -s "$T/files" ] || bad "G1 empty change set"
# G2 forbidden paths, even if the owned regex were widened by mistake
grep -E '^(\.github/|\.claude/|web/|api/models/|api/routers/|api/scripts/|api/data/discovery\.json|api/analytics/attention/(discovery|sources)\.py|api/data/attention/(reddit_stream|registry|pc_pace)\.py|process/context/|process/MASTER|process/archive/|process/general-plans/active/narrative-baskets)' "$T/files" > "$T/forb"
[ -s "$T/forb" ] && bad "G2 forbidden path changed: $(tr '\n' ' ' < "$T/forb")"
# G3 no secrets, IPs, user-name paths or the repo slug in added lines (REPO must be exported)
grep -inE '/Users/|\\Users\\|[A-Za-z]:[\\/]+Users|/home/[A-Za-z0-9_.-]+/|[0-9]{1,3}(\.[0-9]{1,3}){3}|(api[_-]?key|secret|cookie|token|password) *[:=] *[A-Za-z0-9]{8,}' "$T/added" > "$T/g3"
[ -s "$T/g3" ] && bad "G3 secret-like text or user-name path in added lines"
if [ -n "${REPO:-}" ]; then grep -iF -- "$REPO" "$T/added" > "$T/g3b"; [ -s "$T/g3b" ] && bad "G3 repo slug in added lines"; else bad "G3 REPO not exported"; fi
# G4 required red-first tests exist (names), and the stream file is big enough
TF=api/tests/data/test_attention_pc_refresh_stream.py
[ -f "$TF" ] || bad "G4 $TF missing"
for n in test_baseline_24h_polls_comments_every_7200s_posts_every_21600s test_degraded_mode_polls_stream_within_share test_stream_off_by_default_runs_only_search_pass_as_before test_env_off_sends_zero_stream_requests_and_writes_no_stream_store_files test_stream_flag_only_exact_one_enables test_start_from_env_without_variable_means_stream_off test_stream_and_search_requests_count_in_one_budget test_pause_by_poll_403_pauses_searches_same_day test_pause_by_poll_429_pauses_searches_same_day test_pause_by_search_429_stops_polls_same_day test_poll_runs_under_reddit_pass_lock_never_beside_search test_next_poll_due_matches_due_kinds test_second_commit_of_settled_day_changes_nothing test_sources_route_unchanged_with_stream_enabled test_sources_pc_stores_still_excludes_reddit_stream test_budget_baseline_to_degraded_same_utc_day_count_not_refunded_stream_sends_nothing_more test_budget_degraded_to_baseline_same_utc_day_remaining_baseline_cap_applies test_stream_day_files_pruned_by_ledger_retention_days test_behind_restart_schedules_next_poll_at_spacing_not_immediately_for_all_due_kinds test_stream_day_record_has_attempted_fetched_and_missing_reason_counts test_pass_that_cannot_finish_in_its_window_continues_next_window_no_poll_dropped test_stream_spend_capped_by_share_in_degraded_150 test_poll_cut_by_share_is_truncated_keeps_cursor_not_dropped test_budget_share_rejects_zero_negative_bool_over_one_text_and_none test_logs_hold_no_url_subreddit_id_or_author_with_stream_on test_stream_counter_equals_requests_sent_no_double_count test_stream_counter_after_restart_continues_from_file_no_double_count test_failed_request_counts_once test_baseline_cap_reached_mid_day_truncates_remaining_polls_next_utc_day_continues_nothing_dropped test_share_exhausted_recorded_with_cap_and_count_distinct_from_no_entry; do
  grep -rqE "def $n\b" api/tests || bad "G4 missing test $n"; done
NT=$(grep -cE '^[[:space:]]*(async )?def test_' "$TF" 2>/dev/null); [ "${NT:-0}" -ge 50 ] || bad "G4 stream test file has ${NT:-0} tests, need 50 or more"
# G5 report holds the red result (failed above zero) and the green result (passed above zero, none failed)
if [ -f "$R" ]; then
  grep -E '^- Red' "$R" > "$T/red"; grep -E '^- Green' "$R" > "$T/green"
  grep -Eq '(^|[^0-9])[1-9][0-9]* failed' "$T/red" || bad "G5 report has no red result with failed above 0"
  grep -Eq '(^|[^0-9])[1-9][0-9]* passed' "$T/green" || bad "G5 report has no green result with passed above 0"
  grep -Eq '(^|[^0-9])[1-9][0-9]* (failed|error)' "$T/green" && bad "G5 green line reports failures"
else bad "G5 EXEC-REPORT missing"; fi
# G6 targeted tests pass: exit code 0, summary with passed above 0, no failed or error
UV_FROZEN=1 uv run --project api pytest api/tests/data/test_attention_pc_refresh_stream.py api/tests/data/test_attention_pc_refresh.py api/tests/analytics/attention/test_sources_health.py api/tests/data/attention -q -p no:cacheprovider > "$T/t1" 2>&1; E1=$?
tail -3 "$T/t1"
[ "$E1" -eq 0 ] || bad "G6 pytest exit code $E1"
grep -Eq '(^|[^0-9])[1-9][0-9]* passed' "$T/t1" || bad "G6 no passed count in the summary"
grep -Eq '(^|[^0-9])[1-9][0-9]* (failed|error)' "$T/t1" && bad "G6 failed or error in the summary"
# G7 regression: no new failing node id against the saved baseline; pytest must run and collect
UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention api/tests/routers/test_discovery.py api/tests/routers/test_discovery_history.py -q -p no:cacheprovider -rfE > "$T/t2" 2>&1; E2=$?
tail -3 "$T/t2"
{ [ "$E2" -eq 0 ] || [ "$E2" -eq 1 ]; } || bad "G7 pytest exit code $E2 (crash, usage error or nothing collected)"
grep -Eq '(^|[^0-9])[1-9][0-9]* (passed|failed)' "$T/t2" || bad "G7 no passed or failed count in the summary (nothing collected?)"
tr -d '\r' < "$T/t2" | grep -E '^(FAILED|ERROR) ' | sed 's/ - .*//' | LC_ALL=C sort -u > "$T/after"
[ "$E2" -eq 1 ] && [ ! -s "$T/after" ] && bad "G7 pytest exit 1 but no FAILED line parsed"
if [ -f "${BASEFAIL:-/nonexistent}" ]; then
  tr -d '\r' < "$BASEFAIL" | LC_ALL=C sort -u > "$T/before"
  LC_ALL=C comm -13 "$T/before" "$T/after" > "$T/new"
  [ -s "$T/new" ] && bad "G7 new failures: $(tr '\n' ' ' < "$T/new")"
else bad "G7 BASEFAIL baseline file missing"; fi
# G8 switch exact and off by default: each named test must APPEAR in the -v output and PASS (identity, not a count); transition and Sources guard tests the same way; share key 0.45; sources.py untouched (G1, G2); no hour-of-day in the worker
grep -q 'SCREENER_ATTENTION_REDDIT_STREAM' api/data/attention_pc_refresh.py || bad "G8 switch missing"
grep -rn 'SCREENER_ATTENTION_REDDIT_STREAM' api/tests/conftest.py .github > "$T/g8" 2>/dev/null
[ -s "$T/g8" ] && bad "G8 switch set in conftest or workflows"
idcheck() { # $1 tag, $2 -k expression, rest: required test names; each must be PASSED by identity
  local tag="$1" kx="$2"; shift 2
  UV_FROZEN=1 uv run --project api pytest "$TF" -k "$kx" -v -p no:cacheprovider > "$T/$tag" 2>&1; local e=$?
  tr -d '\r' < "$T/$tag" | grep -E '::test_' > "$T/$tag.ids"
  [ "$e" -eq 0 ] || bad "$tag tests exit code $e"
  grep -Eq ' (FAILED|ERROR|SKIPPED|XFAIL|XPASS)' "$T/$tag.ids" && bad "$tag a selected test is not PASSED"
  for n in "$@"; do grep -Eq "::$n(\[[^]]*\])? +PASSED" "$T/$tag.ids" || bad "$tag test $n missing or not PASSED"; done
}
idcheck g8 "test_stream_flag_only_exact_one_enables or test_start_from_env_without_variable_means_stream_off or test_stream_off_by_default_runs_only_search_pass_as_before or test_env_off_sends_zero_stream_requests_and_writes_no_stream_store_files" test_stream_flag_only_exact_one_enables test_start_from_env_without_variable_means_stream_off test_stream_off_by_default_runs_only_search_pass_as_before test_env_off_sends_zero_stream_requests_and_writes_no_stream_store_files
idcheck g8b "test_budget_baseline_to_degraded_same_utc_day_count_not_refunded_stream_sends_nothing_more or test_budget_degraded_to_baseline_same_utc_day_remaining_baseline_cap_applies or test_sources_route_unchanged_with_stream_enabled or test_sources_pc_stores_still_excludes_reddit_stream" test_budget_baseline_to_degraded_same_utc_day_count_not_refunded_stream_sends_nothing_more test_budget_degraded_to_baseline_same_utc_day_remaining_baseline_cap_applies test_sources_route_unchanged_with_stream_enabled test_sources_pc_stores_still_excludes_reddit_stream
grep -Eq '"reddit_stream_budget_share": *0\.45[,[:space:]]' api/data/attention_queries.json || bad "G8 share key missing or not 0.45 in attention_queries.json"
grep -q 'reddit_stream_budget_share' api/data/attention/web_queries.py || bad "G8 share key not in web_queries.py"
grep -q 'reddit_stream_budget_share' api/data/attention_pc_refresh.py || bad "G8 share key not used by the worker"
git diff --quiet "$BASE"...HEAD -- api/analytics/attention/sources.py api/tests/analytics/attention/test_sources_health.py || bad "G8 sources.py or test_sources_health.py changed (Q3)"
git show "$BASE:api/data/attention_pc_refresh.py" > "$T/w0" || bad "G8 cannot read the worker on $BASE"
a=$(grep -cE '\.hour\b|utcnow' "$T/w0"); b=$(grep -cE '\.hour\b|utcnow' api/data/attention_pc_refresh.py)
[ "$b" -le "$a" ] 2>/dev/null || bad "G8 new hour-of-day or utcnow use in the worker (base $a, now $b)"
# G9 stream polls reach only the shared source: no new PcSource or state file for reddit_stream
grep -nE "PcSource\(.*reddit_stream|reddit_stream.*_pc_state|_pc_state.*reddit_stream" api/data/attention_pc_refresh.py api/analytics/attention/sources.py > "$T/g9"
[ -s "$T/g9" ] && bad "G9 separate reddit_stream state"
# G10 open-PR collision re-check (read-only gh); PRs other than ALLOW_PR must not touch an owned file
gh pr list -R "${REPO:-none}" --state open --json number,files -q '.[] | .number as $n | .files[].path | "\($n) \(.)"' > "$T/prs" || bad "G10 gh pr list failed"
grep -E " ($OWNP)$" "$T/prs" | grep -Ev "^${ALLOW_PR:-0} " > "$T/coll"
[ -s "$T/coll" ] && bad "G10 open PR touches an owned file: $(tr '\n' ' ' < "$T/coll")"
rm -rf "$T"; echo "validate-contract exit $RC"; exit $RC
```

File-set check (G1) is the one most likely to catch scope drift; `git diff --name-only origin/main...HEAD` must list only owned files.

File-set check (G1) is the contract's second gate and the one most likely to catch scope drift; `git diff --name-only origin/main...HEAD` must list only owned files.

## 6. Risks, rollout, owner probes, cost

Risks:

| Risk | Mitigation |
|---|---|
| Stream starves searches (the bound is code reading, not measured) | Decided option (b): the share caps the stream at 112 (BASELINE) and 67 (DEGRADED) requests per UTC day at 0.45; tests `test_stream_spend_capped_by_share_*`, `test_stream_cap_is_112_baseline_and_67_degraded_at_default_share`; P-S3 measures the real spend and the owner tunes `reddit_stream_budget_share` in the JSON |
| Empty search queue ends the day and polls stop | hook `_idle` and extra wake; tests `test_empty_search_queue_still_polls_stream`, `test_done_outcome_with_stream_on_waits_for_next_poll_not_next_day` |
| A poll round delays searches or the reverse; two requests closer than the spacing | one thread, one lock, `last_unit_at` shared; test `test_polls_and_searches_never_closer_than_min_delay` |
| Slicing repeats a failed canary | `test_canary_failure_not_repeated_across_search_slices_same_day`, conditional `canary_days` |
| `next_poll_due` drifts from `due_kinds` | property test |
| A day that can never settle is re-evaluated each round forever | `_seen` pruned by retention (W6); cost is local file reads |
| Sources route breaks or changes with the stream on (Q3: no Sources row) | `reddit_stream` NOT added to `PC_STORES`, `sources.py` untouched (G1, G8); guard test `test_sources_route_unchanged_with_stream_enabled` |
| Mode change inside a UTC day (restart BASELINE to DEGRADED or back) leaves the day count above or below the new cap | W11b: count never refunded; before each request `count < cap of the current mode`; tests `test_budget_baseline_to_degraded_*`, `test_budget_degraded_to_baseline_*`; shared `reddit_web` budget stays the hard limit |
| A truncated poll hits the share cap and the day stays unsettled, partial or missing (in BASELINE too when the stream runs near its 124-132 bound; more often in DEGRADED) | EXPECTED consequence of the owner's 0.45 (section 2): by design never 0, never dropped; the stream series is the second in order; the day record says `share_exhausted` with cap and count (W12); `--stream-status` shows the truncated polls; the owner may raise the share; tests `test_baseline_cap_reached_mid_day_truncates_remaining_polls_next_utc_day_continues_nothing_dropped`, `test_cap_truncated_day_is_missing_or_partial_never_zero` |
| The stream counter and the shared budget disagree (crash, double counting) | one counting path (the wrapper's `spend`, written before it delegates): a crash can over-count the stream by one, never under-count; the shared `used` stays the authority; tests `test_stream_counter_equals_requests_sent_no_double_count`, `test_stream_counter_after_restart_continues_from_file_no_double_count`, `test_failed_request_counts_once` |
| #198 changes a signature this plan relies on | G0 first; only unchanged functions are called; the worker reads config fields by name |
| Host off for hours: polls resume, one poll pages back to its floor (page cap 10, cursor continuation) | #198 behaviour, inside the shared budget; no burst: `run_due` spaces requests 60-120 s |
| Public repo | no names, paths, IPs, keys; G3 |

Rollout: merge with the switch OFF (nothing changes). The owner turns it on by setting `SCREENER_ATTENTION_REDDIT_STREAM=1` in the same shell or service environment that sets `SCREENER_ATTENTION_PC_WORKER=1`, and restarts the API process; the stream polls from the first start, in BASELINE or in DEGRADED (share-capped), and the first full stream day is the first UTC day the host was up since before 00:00. Off: unset the variable and restart; stored stream files stay and age out by retention. Discovery keeps reading `reddit_web` first, so turning the stream on cannot change a score until `reddit_web` has no usable points for a coin and window.

Owner probes (live behaviour is proven only on the owner's machine; planner and worker never run them):
- P-S1: start the worker with both switches on, host up since before 00:00 UTC. After 6 h run the probe `api/scripts/probe_pc_sources.py` with `--source reddit --stream-status` (local files only) and check: today's comments polls are about every 2 h, posts about every 6 h, entries seen is above 0.
- P-S2: after the first UTC midnight: the Reddit Sources row is unchanged (Q3) and yesterday's `--stream-status` line shows both kinds settled (or `unknown`/`partial`, never 0 for missing data); at least one coin has a stored `reddit_stream` point or a stated missing reason.
- P-S3 (budget): at the end of one BASELINE UTC day read the `used` figure in the Reddit pace state, the day's `_budget` request count (the stream's own count, W11) and the sum of poll pages in the stream poll files; report all three (no secrets). The `_budget` count is expected to be at least the sum of poll pages (pages miss failed and empty requests). This turns the 124-132 bound into a measurement and tells the owner whether `reddit_stream_budget_share` needs tuning.
- P-S4 (restart): restart the process in the afternoon; confirm the stream polls resume at the normal spacing without a burst (log lines carry outcome codes only), that its requests for the day stay within the share (67 at 0.45 in DEGRADED), that its `_budget` count equals the increase of the shared `used` caused by the stream, and that searches continue.
- P-S5: when a pause happens by itself, read its reason code on the Sources row; never provoke a block on purpose.

Cost estimate (UNVERIFIED, from the PLAN table row for W8c2 "opus, medium, 3-4" in the collector PLAN): about 3 to 6 USD for the EXECUTE session with `riper-opus`; PLAN session spend is not measured here. No invented figure beyond that range. Model: `riper-opus` for EXECUTE (owner choice, RT2).

## Acceptance Criteria

W-AC1. With the switch off, every existing test passes unchanged and the new off-by-default tests pass (no behaviour change).
W-AC2. With the switch on and BASELINE, a 24 h fake-clock run sends comments polls every 7200 s and posts polls every 21600 s (AC37 c), interleaved with the per-coin searches, no two requests closer than the configured minimum delay, one Reddit lock.
W-AC3. Stream and searches share the one Reddit counter and pause state; a 403 or 429 on either stops both for the UTC day; budget spent stops both; the honest user agent is used (AC24, rules 10, 15, 16).
W-AC4. Settled completed days are stored under `reddit_stream` only, frozen once stored, never 0 for missing data (AC3, AC4, AC14, AC26, AC30).
W-AC5. Each completed stream day has a completeness file and `--stream-status` reports its numbers, `unknown` (None) where absent, never 0; there is no Sources row (Q3) (AC38, AC39).
W-AC6. In DEGRADED the stream polls within its share (67 requests per UTC day at the default 0.45) and the searches keep the rest (83); state stays bounded over 90 simulated days; a restart resumes with no burst (AC40).
W-AC7. `reddit_stream` is NOT added to `PC_STORES`; `sources.py` is unchanged and the Sources route works unchanged with the stream enabled (guard test).
W-AC8. The file-set check, the secret check, the targeted test run and the open-PR re-check pass (Validate Contract G0-G10).
W-AC9. The new key `reddit_stream_budget_share` (default 0.45) is validated (rejects 0, negatives, bool, values above 1). The stream never starts a request once the persisted day count has reached the current mode's cap (`floor(share * budget)`: 112 of 250 BASELINE, 67 of 150 DEGRADED); the count itself is not retroactive, never refunded, and a mode change inside a UTC day follows W11b (BASELINE to DEGRADED above the new cap: nothing more that day; DEGRADED to BASELINE: the remaining BASELINE cap). The shared `reddit_web` budget stays the hard limit in both modes. Requests are counted once each by one path (also after a restart, also failed requests); polls beyond the cap are truncated and continued, never dropped; searches keep the rest; a day whose share ran out is recorded as `share_exhausted` with cap and count in the day record, distinct from a day with no entry.
W-AC10. A pass that cannot finish in its window continues in the next window; no poll and no coin is dropped to catch up (rule 16).

Phase Completion Rules: EXECUTE is complete only when every gate G0-G10 prints no FAIL, the EXEC-REPORT holds the red and green results with dates, the 11-heading report is written, ONE draft PR is open with the gate result in its body, and nothing stronger than status `review` is claimed. Anything not run is listed under "Tests NOT run", and every live behaviour is listed as an owner probe. No `canary`, zero or verdict logic is added.

## Implementation Checklist (EXECUTE)

RFC-1. Step 0: isolation, remote, fetch, PLAN-REV check, collision re-check (G10), G0, baseline failing ids.
RFC-2. Tests first (section 4), commit "test: red", record the red count.
RFC-3. `web_queries.py` and `attention_queries.json`: the key `reddit_stream_budget_share` with validation (W11).
RFC-4. `Stream` hooks (`_idle`, extra wake) with X behaviour unchanged; `RedditStream` switch, round, share wrapper and day counter, outcome `stream_due`, `next_poll_due`, `commit_open_days`.
RFC-5. `reddit_web.run_pass` `canary_days` only if the canary-slices test is red.
RFC-6. Prune of `_seen`, `_completeness` and `_budget` day files (W6); `_seen` and `_completeness` are not pruned by `reddit_stream.py` (verified), so the worker does it.
RFC-7. No `sources.py` edit (Q3). Guard tests for the unchanged Sources route and for the mode-change rule (W11b).
RFC-8. Green run, gates G0-G10, EXEC-REPORT, push, ONE draft PR.

## Touchpoints

`api/data/attention_pc_refresh.py` (Stream, RedditStream, AttentionPcWorker, start_from_env); `api/data/attention/web_queries.py` and `api/data/attention_queries.json` (one key); optionally `reddit_web.run_pass`. Read only: `sources.py` (not edited, Q3), `reddit_stream.py`, `registry.py`, `pc_pace.py`, `discovery.json`.

## Public Contracts

- Environment: `SCREENER_ATTENTION_REDDIT_STREAM` exactly `1`.
- Config: `reddit_stream_budget_share`, float in (0, 1], default 0.45; stream cap = `floor(share * budget of the CURRENT mode)` (112 of 250, 67 of 150); a request starts only while the persisted day count is below that cap (never refunded; W11b).
- Worker: `AttentionPcWorker(reddit_stream=...)`; new outcome code `stream_due`; `Stream._idle` and the extra-wake hook default to today's behaviour.
- Files: `reddit_stream/_meta/_completeness/<day>.json` and `_seen`, written by `reddit_stream.py`; `reddit_stream/_meta/_budget/<day>.json` (the stream's request count of the day, share cap and `share_exhausted`, written only by the worker's share wrapper); no new `PcSource` state file; budget and pause stay in `reddit_web`'s pace state.
- `sources.py`, `DiscoverySourceHealth`, the Sources route shape, `web/`: unchanged (Q3).

## Blast Radius

Runtime: only the Reddit thread of the PC worker, only with the switch on. Sources route: unchanged (Q3). Data: new files under `reddit_stream`. Config: one new key with a default, so an existing JSON without it still loads. Discovery scores: unchanged unless `reddit_web` has no usable points. CI: the new tests run in the API job; the full suite is not changed.

## Verification Evidence

EXECUTE records in the EXEC-REPORT: baseline failing ids, red count (date, time), green count, G0-G10 output, the `git diff --name-only` list, the open-PR list used for collision, and the list of owner probes not run. All live statements stay UNVERIFIED until P-S1 to P-S5 are answered by the owner.

## Owner decisions (all decided, none open)

Decided by the owner on 30-10-26 (recorded as decided; the review found no open question left):

- Q1 DECIDED: option (b). Key `reddit_stream_budget_share`, float in (0, 1], typed validation rejects 0, negatives, bool and values above 1. Default 0.45 (owner choice, 30-10-26; arithmetic and tradeoff in section 2: cap 112 of 250 and 67 of 150 against the stream's own bound of 124-132; in BASELINE the stream series may lag or show days as missing or partial when the bound is reached, an expected consequence). The share caps the stream's requests per UTC day inside the shared budget in BOTH modes; searches keep the rest (138 and 83); polls beyond the share are truncated and continued next poll under E1/E3, never dropped. The key lives in `attention_queries.json` and `web_queries.py` (+ `test_web_queries.py`), owned by this EXECUTE slice.
- Q2 DECIDED: switch = environment variable `SCREENER_ATTENTION_REDDIT_STREAM=1` (naming matches the existing `SCREENER_ATTENTION_*` variables).
- Q3 DECIDED (accept): stream health only in `--stream-status`, not on the Sources row (a second health line would need a model and `web/` change: another slice).
- Q4 DECIDED (accept): per-coin method choice (W8f) stays. Proposed owner-decision line for a later docs task (NOT part of this EXECUTE; no SPEC edit is planned): "SPEC AC14 waiver: one method per coin series and window is accepted; Discovery chooses the first store of `source_impl.reddit` that yields a change for the coin and window; two coins in one window may come from two methods; `reddit_impl_order` (collector config) and `source_impl.reddit` (Discovery) are kept as two copies guarded by a consistency test." The planner of that docs task decides where it is written.
- Q5 DECIDED (accept): a completed day with no stream entry has no completeness file and shows `no entry observed, unknown`; a day for which the share ran out is recorded as `share_exhausted` with cap and count in the worker's day record (W12, no Sources row), never inferred from a missing file.
- Q6 DECIDED: EXECUTE starts only after #198 is merged (gate G0).
- Q7 DECIDED (allow): the conditional additive `canary_days` parameter in `reddit_web.run_pass`, only if `test_canary_failure_not_repeated_across_search_slices_same_day` is red.
- Q8 DECIDED (accept): superseded by Q1(b): DEGRADED restart days no longer lose the stream; a day truncated by the share is missing in the stream series, never 0.
- Q9 DECIDED (accept): the point-in-time rule drops stream days committed after D+1.

## Resume and Execution Handoff

Primary execute anchor: this file, sections 1-5 and the envelope below. Supporting files: `reddit_stream.py`, `attention_pc_refresh.py`, `sources.py`, `web_queries.py`, the W8c2, W8e, W8e2, W8f and W8g reports in `process/general-plans/active/narrative-baskets_02-10-26/`, and the collector SPEC (AC14, AC26, AC30, AC37, AC38, AC39, AC40, rules 10, 15 and 16). All owner questions Q1-Q9 are decided (none open); the share default is 0.45; Q3 means `sources.py` is not edited. Main fills the three FILL_IN values, confirms that this plan PR (#200) is merged (#198 already is; the envelope stops with "plan not merged yet" if `origin/main` does not carry `PLAN-REV: 5`), spawns `riper-opus` with the envelope, and gives the explicit ENTER EXECUTE MODE for T222. Expect the worker's changes to also appear in the parent checkout (`task.isolation.apply` = true, OBSERVED 29-10-26): do not commit or publish them again.

### EXECUTE envelope (ready to paste)

````
ROLE: WORKER
You are a WORKER (agent riper-opus), direct lane. Do not spawn subagents. Phase: EXECUTE (RT2) for T222 W8c2w, wiring the Reddit stream (reddit_stream) into the PC worker. You see no CLAUDE.md or AGENTS.md: these rules are binding and complete.

VALUES (Main replaces FILL_IN; plain text, not commands). If any value still reads FILL_IN, stop and report.
ORIGIN_URL=FILL_IN
REPO=FILL_IN
PR198_MERGED=FILL_IN
ORIGIN_URL is the public https URL of origin, REPO the owner/name slug for gh -R, PR198_MERGED yes or no. Paste the three lines into your shell, then run: export ORIGIN_URL REPO PR198_MERGED

DECIDED BY THE OWNER (30-10-26, closed): budget option (b): config key reddit_stream_budget_share (float in (0,1], default 0.45, rejects 0, negatives, bool, above 1) caps the stream's requests per UTC day inside the shared Reddit budget in BOTH modes (floor(share x 250 or 150) = 112 or 67); searches keep the rest; a request starts only while the persisted day count is below the CURRENT mode's cap (112 BASELINE, 67 DEGRADED; never refunded; after BASELINE to DEGRADED above 67 nothing more that day; after DEGRADED to BASELINE the remaining cap; the shared reddit_web budget stays the hard limit); Q3: NO Sources row, sources.py untouched, reddit_stream NOT added to PC_STORES; polls over the share are truncated and continued next poll, never dropped; in BASELINE the stream series may lag or miss days when its bound is reached (expected). Switch: environment variable SCREENER_ATTENTION_REDDIT_STREAM exactly 1, off by default. Gate G0 (PR 198 is merged; passes on origin/main). Other decisions: PLAN section Owner decisions.

HARD RULES: The OWNER merges every PR; never merge or close a PR. Open ONE DRAFT PR only. Never push to main. Push only claude/w8c2w-stream-wiring, normal push, never force. Never touch .github/**. Never write secrets, keys, IPs, cookies, account names, user-name home paths, or the repository owner/name slug or URL into any repo file, report, commit message or PR text (use $REPO and $ORIGIN_URL only on the command line). No live provider calls: tests use fakes, loopback only. Unknown = UNVERIFIED; missing data is never 0. No verdict logic. Nothing stronger than status review. No invented costs or IDs. Report in the 11-heading format. Stop and report on scope expansion, secrets, .github, a failing validator you did not cause, or a decision not given here.

OWNED FILES ONLY: api/data/attention_pc_refresh.py; api/data/attention/web_queries.py; api/data/attention_queries.json; api/tests/data/attention/test_web_queries.py; api/tests/data/test_attention_pc_refresh_stream.py (new); api/tests/data/test_attention_pc_refresh.py; conditional: api/data/attention/reddit_web.py and api/tests/data/attention/test_reddit_web.py (only if test_canary_failure_not_repeated_across_search_slices_same_day is red); the new file w8c2w-stream-wiring_EXEC-REPORT_30-10-26.md in the plan folder. Nothing else (gates G1 and G2 enforce it).

STEPS
0. Isolation (OBSERVED: task.isolation.apply = true): your changes are also auto-applied to the parent checkout and your branch does not exist there, so YOU publish, from your isolated checkout. If git remote -v is empty: git remote add origin "$ORIGIN_URL". Stash any copied parent changes with a named stash first. git fetch origin. If this fails, stop and report. If PR198_MERGED is not yes, stop and report. git switch -c claude/w8c2w-stream-wiring origin/main.
1. PLAN=process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_PLAN_30-10-26.md
   grep -q '^PLAN-REV: 5' "$PLAN" && echo PLAN-OK || echo "plan not merged yet"
   If that prints "plan not merged yet", STOP and report exactly: plan not merged yet (the PLAN on origin/main is older than revision 4; the owner must merge the plan PR first). Otherwise:
   GF="$(git rev-parse --git-dir)/w8c2w-gates.sh"
   tr -d '\r' < "$PLAN" | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' > "$GF"
   bash -n "$GF"
   (no output means the syntax is fine.) Read PLAN sections 1-5 and Public Contracts. Run the second pytest command of the Test Procedure and the existing-file part of the first; save the sorted FAILED ids (cut at " - ") as the file BASEFAIL (an empty file is valid). Run bash "$GF" once now: G0 must not print FAIL; G1 empty change set is expected.
2. Write ALL red tests of PLAN section 4 first; run them; commit "test: red"; record "- Red ..., N failed" in the EXEC-REPORT.
3. Implement PLAN section 1 (W1-W12): switch SCREENER_ATTENTION_REDDIT_STREAM exactly 1, one thread, one lock, the shared reddit_web PcSource wrapped by the share cap, key reddit_stream_budget_share. ONE counting path: the wrapper's spend writes the stream day count (then delegates); never sum PollOutcome.requests or read Poll.pages as the counter; record share_exhausted with cap and count (W12). Do NOT edit reddit_stream.py, discovery files, registry.py, pc_pace.py, models, routers, scripts, web, the SPEC or PLAN of the collector.
4. Green: run both pytest commands; record "- Green ..., N passed". Fix, commit (2 fix cycles max, then stop and report).
5. Export REPO and BASEFAIL, run bash "$GF"; every gate must print no FAIL. Put its output in the EXEC-REPORT (11 headings; list owner probes P-S1 to P-S5 as not run).
6. Push only: git push origin claude/w8c2w-stream-wiring. Open ONE DRAFT PR: gh pr create -R "$REPO" --draft --base main --head claude/w8c2w-stream-wiring --title "feat: wire Reddit stream into the PC worker (T222)" with the gate output in the body (no slug). Then export ALLOW_PR with its number and run G10 again. Do not merge. If push or PR fails, stop and report.
7. Final message: results only; say your changes were also auto-applied to the parent checkout and the planner must NOT commit, push or open a PR from it.

STOP AND REPORT if: scope expansion, anything touching .github/, secrets, a newly failing validator, push or auth failure, isolation failure, an open PR touching an owned file.
````

Envelope size (LF, between the four-backtick fences): 5,972 B (cap 8,000 B, measured with `wc -c`). First line is exactly `ROLE: WORKER`.

ENTER EXECUTE MODE only after the owner has merged this plan PR (#200) (#198 is already merged; Q1, Q2, Q6 are decided). RIPER-5 next step: EXECUTE, agent `riper-opus`.
