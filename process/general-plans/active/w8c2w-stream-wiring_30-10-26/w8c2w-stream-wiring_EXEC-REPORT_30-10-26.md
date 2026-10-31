---
name: w8c2w-stream-wiring-exec-report
description: "EXECUTE report (T222, W8c2w): the Reddit stream (reddit_stream) wired into the PC worker behind SCREENER_ATTENTION_REDDIT_STREAM=1, with the reddit_stream_budget_share cap (default 0.45). Status review."
date: 31-10-26
---

# W8c2w: Reddit stream wiring into the PC worker - EXEC-REPORT

Task: T222. Plan: `w8c2w-stream-wiring_PLAN_30-10-26.md` (PLAN-REV 5, on `origin/main`). Agent: `riper-opus`, RT2.
Branch: `claude/w8c2w-stream-wiring` (local only, NOT pushed). Status: review (nothing stronger is claimed).
STOPPED before push and PR: G10 found an open PR (#201) that touches two owned files (section 4).

## 1. Summary

The worker's Reddit pass now runs the stream when `SCREENER_ATTENTION_REDDIT_STREAM` is exactly `1` (off by
default; `start_from_env` reads it, `AttentionPcWorker(reddit_stream=...)` takes it). With the switch on, each Reddit
pass, under the one Reddit lock and on the same client, first polls the due feeds (`reddit_stream.run_due`), then
commits every open day (`open_days` -> `commit_day`), then runs the search pass only until the next poll is due (new
outcome `stream_due`). The stream spends from the shared `reddit_web` `PcSource` through `StreamShare`, which caps the
stream's requests per UTC day at `floor(reddit_stream_budget_share x budget of the current mode)` (112 of 250, 67 of
150 at the default 0.45) and is the one counting path (`reddit_stream/_meta/_budget/<day>.json`). Switch off: the
pass, schedule and outcomes are the same as before (tests below).

## 2. Files changed

`git diff --name-only origin/main...HEAD` (all in the owned set):

- `api/data/attention_pc_refresh.py`: `STREAM_ENV`, `stream_enabled`, worker argument `reddit_stream`, `Stream`
  hooks `_idle`, `_wakes_between_days`, `_extra_wake` (defaults keep X and switch-off behaviour), `StreamShare`,
  `stream_budget_path`, `read_stream_budget`, `RedditStream.stream_share`, `next_poll_due`, `_stream_round`,
  `_commit_open_days`, outcome `stream_due`, prune of the stream's `_seen`, `_completeness` and `_budget` day files.
- `api/data/attention/web_queries.py`, `api/data/attention_queries.json`: key `reddit_stream_budget_share` (0.45),
  validated like `reddit_stream_min_coverage` (a number in (0, 1], never a bool).
- `api/data/attention/reddit_web.py` (conditional, Q7): optional `run_pass(..., canary_days=None)`; default unchanged.
- Tests: `api/tests/data/test_attention_pc_refresh_stream.py` (new, 79 test functions, 89 test cases),
  `api/tests/data/attention/test_web_queries.py` (+4), `api/tests/data/attention/test_reddit_web.py` (+1).
- This report.

Not changed (Q3 and non-goals): `sources.py`, `test_sources_health.py`, `reddit_stream.py`, `registry.py`,
`pc_pace.py`, `discovery.json`, `discovery.py`, scripts, models, routers, `web/`, `.github/`, SPEC and PLAN.

## 3. Tests (red first, then green)

- Baseline before any edit (31-10-26): the second Test Procedure command plus the existing files of the first: 24
  failed, 1342 passed, 1 skipped; the 24 failing ids (all `api/tests/routers/test_discovery*.py`, "handler must not
  reach the network") are the BASEFAIL file used by G7.
- Red 2026-10-31T13:31Z (`test: red` commit; new stream file and the four key tests, implementation stashed): 92 failed, 61 passed
- Green 2026-10-31T14:45Z (first Test Procedure command after the implementation commit): 1036 passed, 1 skipped
- `test_canary_failure_not_repeated_across_search_slices_same_day` was red on the unchanged `reddit_web` (12 canary
  requests in one BASELINE day instead of 1), so the conditional `canary_days` was added (Q7);
  `test_run_pass_default_canary_behaviour_unchanged` was confirmed red against the unchanged `reddit_web.py`, then green.
- Fix cycles: 1 (test-harness fixes after the first green attempt: the drive loop ended at the pass start instead of
  the unit due time; three test setups; no assertion was weakened against the plan's criteria).

## 4. Validate Contract (G0-G10)

First gate run (2026-10-31, after the implementation and report commits): G0, G1, G2, G4, G5, G6, G7, G8, G9 printed
no FAIL. Two gates failed:

- G3 (my cause, fixed in a follow-up commit): the new test file's socket guard held the loopback address as a
  literal, which the IP pattern matches. It now asks `ipaddress.ip_address(host).is_loopback`; no literal remains.
- G10 (not my cause, STOP condition): open draft PR #201 (`claude/x-unclean-stop-lock`, opened 2026-10-31 13:02Z,
  after this plan's collision snapshot) touches `api/data/attention_pc_refresh.py` and
  `api/tests/data/test_attention_pc_refresh.py`. Per the envelope the worker stopped: no push, no PR. The owner
  decides the order (merge #201 first and rebase this branch, or the reverse).

## 5. Deviations

- D1 (scope note, inside owned files): a feed kind whose poll failed with no poll stored (5xx, network error) waits
  its interval from the failure (`RedditStream._failed_at`, in memory). Without it the worker re-polled a failing
  feed at the 60-120 s spacing and cut every search slice to zero length until the share ran out. The property test
  `test_next_poll_due_matches_due_kinds` still pins `next_poll_due` to `due_kinds` for stored polls. The owner may
  ask to drop it.
- D2: `reddit_web.run_pass` gained the Q7 parameter; a canary is recorded in the caller's set only when it was sent
  (a slice that stops before the canary does not use up the day's attempt).
- D3 (observed, not changed): in BASELINE the search spacing is `max(60-120 s, 24 h / coins)` counted from the last
  Reddit request, polls included. With fewer than 12 coins (spacing above the 7200 s poll interval) the searches
  would never start; with the shipped 75 coins the spacing is 1152 s. Tests with few coins use DEGRADED or 30 coins.
- D4: `free_disk_bytes` of the Reddit health block is ignored in the Sources guard test (it changes between two
  reads of the host disk, with or without the stream).

## 6. Risks

- The stream's real request spend per day is UNVERIFIED until owner probe P-S3 (bound from code: 124-132).
- A BASELINE day near that bound reaches the 112 cap; later polls of that day are refused and continue next UTC day
  (expected, owner decision); the day stays missing or partial, never 0.
- `--stream-status` does not print the `_budget` day record (probe script not owned); the owner reads it by hand.

## 7. Owner probes (not run by the worker)

- P-S1 (6 h cadence via `--stream-status`): not run.
- P-S2 (first UTC midnight, Sources row unchanged, stream day settled or unknown): not run.
- P-S3 (BASELINE day spend: pace `used`, `_budget` count, poll pages): not run.
- P-S4 (restart, no burst, share 67 in DEGRADED): not run.
- P-S5 (pause reason when one happens by itself): not run.

## 8. Tests NOT run

- The whole `api/tests` suite was not run (only the two Test Procedure commands and the gates).
- No live Reddit request (by rule).

## 9. Rollout

Merge with the switch off. The owner sets `SCREENER_ATTENTION_REDDIT_STREAM=1` next to
`SCREENER_ATTENTION_PC_WORKER=1` and restarts the API process; unset and restart to turn it off.

## 10. Open items

None for this slice. Q4 SPEC waiver text stays for a later docs task (not part of this EXECUTE).

## 11. Gate output

```
FAIL: G3 secret-like text or user-name path in added lines
1036 passed, 1 skipped, 2 warnings in 479.37s (0:07:59)
(G7 tail: pytest summary line; Windows asyncio teardown traceback lines from the pre-existing router tests omitted:
 they hold a user-name path)
FAIL: G10 open PR touches an owned file: 201 api/data/attention_pc_refresh.py 201 api/tests/data/test_attention_pc_refresh.py
validate-contract exit 1
```

G7 printed no "new failures" line: no failing id outside BASEFAIL. The gates were not run again after the G3 fix
because G10 stays failing until the owner resolves the #201 collision.
