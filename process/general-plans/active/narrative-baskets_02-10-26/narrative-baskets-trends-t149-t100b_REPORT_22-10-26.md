---
name: report:narrative-baskets-trends-t149-t100b
description: "T149 WORKER report: slice T100b of the Trends plan (T144 PLAN, PR #159). One coin per request, replace-series store mode, per-pull archive, too-little-interest rule, name-risk skip, 429 handling, probe --alone. T100c (.github/) not touched."
date: 22-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T149 (slice T100b): Trends fetch, one coin per request: REPORT

## 1 Task ID

T149 = slice T100b of `narrative-baskets-trends-t100b_PLAN_21-10-26.md` (T144, branch `claude/t144-trends-t100b-plan`, PR #159, not yet on main). Branch `claude/t149-t100b-trends-fetch`, from `origin/main` 27b2ac8.

## 2 Outcome

done (draft PR open, not merged). One deviation from the file list (heading 8) and one test failure that already fails on fresh main (heading 9).

## 3 Summary

- `trends.fetch_alone`: one request with only the coin's keyword, over an explicit 100-day daily range ending yesterday (`2026-07-14 2026-10-21` for a run on 22-10-26; the formula is `explicit_timeframe(today)`). Drops `isPartial` rows and rows dated today or later. Rejects non-daily steps, a missing column and an empty frame. Under 90 complete days gives `insufficient-history`. Never raises. A failure reason carries only the exception class and the HTTP status.
- Too-little-interest rule, on the coin's own complete days: all zero, OR median < `TRENDS_MIN_MEDIAN` (3), OR zero days >= `TRENDS_MAX_ZERO_DAY_PCT` (40 %). The result is `unavailable` / `too-little-interest`. It has no points, is never written and never becomes 0. Both numbers are placeholders.
- `NAME_RISK_SYMBOLS`: the 12 T125 names. A `term` entry for one of them costs no request and gives `name-ambiguous: needs topic`. A `topic` entry is fetched.
- `store.write_series(..., mode="replace-series")`: the stored series becomes exactly the pull's completed days. A pull of fewer than 90 complete days changes nothing. The default `mode="first"` is unchanged and `main()` passes the mode only for Trends (`WRITE_MODES`).
- `store.write_pull_archive`: `<cache>/attention/trends_pulls/<pull-date>.parquet` (symbol, date, value). It holds only `ok` coins. A second run on the same date adds only symbols that are missing.
- `_run_trends`: loads the keyword file and rotates the coin order by UTC day. Requests are 3 s apart plus 0 to 2 s of jitter. On HTTP 429 it waits 30, 60 and 120 s for the same coin, then marks it `capped`. Three capped coins in a row stop the source. The time budget is 540 s. If pytrends is missing or the session fails, every coin with a keyword becomes `unavailable` (yellow, not red). The archive write can never cost the live series. One `trends detail:` summary line is printed.
- `probe_trends --alone 'SYMS'`: one request per coin with only its keyword. For each coin it prints the step, days, min, median, max, days at 0, days at 0 or 1, distinct values, the zero share and the rule's verdict. It stops at the first HTTP 429.
- Tests: 47 new, 2 old ones removed (net +45). All 5 gate groups are green. 8 of 8 mutations were killed.

## 4 Files changed

The nine PLAN paths (section 6):
1. `api/data/attention/store.py`: `mode` parameter, `MIN_REPLACE_DAYS`, `pull_archive_path`, `read_pull_archive`, `write_pull_archive`
2. `api/data/attention/trends.py`: `fetch_alone`, `complete_days`, `interest_verdict`, `explicit_timeframe`, the constants, `NAME_RISK_SYMBOLS`, and local `http_status`/`error_class`/`is_rate_limited` (the data layer does not import `api.scripts`)
3. `api/scripts/refresh_attention.py`: `_run_trends` rewritten, Trends constants, `WRITE_MODES`, `TRENDREQ_FACTORY`, `trends_summary`
4. `api/scripts/probe_trends.py`: `--alone`
5. `api/tests/data/attention/test_store.py` (+7)
6. `api/tests/data/attention/test_trends.py` (+14)
7. `api/tests/data/attention/test_trends_pull.py` (new, 6)
8. `api/tests/scripts/test_refresh_attention_trends.py` (new, 15: the 13 PLAN names plus 2, see heading 8)
9. `api/tests/scripts/test_probe_trends.py` (+5)

Outside the list (deviation, heading 8): `api/tests/scripts/test_refresh_attention_extra_hardening.py`.
Plus this report.
Not touched: `.github/`, `web/`, `api/pyproject.toml`, `api/uv.lock`, `api/data/cache/`, `api/data/trends_keywords.json`, `api/scripts/check_trends_keywords.py`, `api/data/pytrends_adapter.py`, `api/analytics/`.

## 5 Commits

Branch `claude/t149-t100b-trends-fetch`:
- `4ff7363`: feat(trends): T100b one coin per request, replace-series store, per-pull archive
- the report commit that follows it

## 6 Tests run

All runs used `UV_FROZEN=1`, from the repo root, on 22-10-26 UTC.

**Baselines on fresh origin/main 27b2ac8** (the PLAN's numbers are from 4675f82):

| Gate | Baseline 27b2ac8 | After (4ff7363) | Floor | Result |
|---|---|---|---|---|
| G1 `pytest test_store.py test_trends.py test_trends_pull.py test_refresh_attention_trends.py test_probe_trends.py -q` | 40 passed (the new files did not exist) | 87 passed | 62 + probe | PASS |
| G2 `pytest api/tests/data/attention api/tests/data/test_pytrends_adapter.py api/tests/scripts/test_backfill_pytrends_history.py -q` | 195 passed | 222 passed | 222 | PASS |
| G3 `pytest api/tests/scripts -q` | 346 passed, 2 warnings | 364 passed, 2 warnings | 364 | PASS |
| G4 `pytest api/tests/analytics/attention -q` | 280 passed, **1 failed** | 280 passed, **1 failed** (same test) | exactly 281 | unchanged; the failure is already on main (heading 9) |
| G5 `pytest api/ -q` | 1860 passed, **1 failed**, 1 skipped, 5 deselected | 1905 passed, **1 failed** (same), 1 skipped, 5 deselected | 1906 | +45 exactly; 1905 = 1906 minus the test that already fails on main |
| G6 `git diff --name-only origin/main...HEAD` | | the 9 PLAN paths, the hardening test file and this report | | deviation, heading 8 |
| G7 `sha256sum -c` (3 hashes of 2026-10-17) | | `OK` x3 | | PASS |
| G8 `git diff --check` plus the secret scan | | exit 0; the scan printed nothing | | PASS |
| G9 `pytest test_trends.py -k percent_change_invariant` | | 1 passed | | PASS |
| G10 importing the 4 modules; grep for network or pytrends imports in trends.py and store.py | | exit 0; the grep printed nothing | | PASS |
| G11 `pytest test_store.py test_wikipedia.py test_reddit.py -q` | 26 passed | 33 passed (+7 store) | >= 26 | PASS |
| G12 plan validator on the PLAN (run in a detached worktree of the PR #159 branch) | | 0 failures, 0 warnings | | PASS |

**Red first** (tests in place, no code yet, same G1 command): `31 failed, 41 passed, 15 errors`. All 46 new behaviour tests were red: 31 failed, 15 errored because the runner fixture patched attributes that did not exist yet. The 41 passing were the 40 existing tests plus `test_percent_change_invariant_to_series_scale`. That test proves a property of the existing `discovery._source_change` (the key-question answer), so it is green by design.

**Mutation check** (each mutation applied, the named test run, then the file restored):

| Mutation | Killed by |
|---|---|
| `MIN_REPLACE_DAYS = 90` -> 89 | `test_replace_series_short_pull_keeps_old_series` |
| zero share `>=` -> `>` | `test_many_zero_days_too_little_interest` |
| drop the `d >= today` filter | `test_fetch_alone_drops_partial_and_today` (it survived at first because the fixture's today row was also flagged partial; the test now adds an unflagged today and tomorrow row, and it is killed) |
| `TRENDS_BREAKER_AFTER` 3 -> 4 | `test_three_capped_in_a_row_stops_source` |
| rotation start forced to 0 | `test_rotation_start_depends_on_day` |
| remove the name-risk skip | `test_name_risk_term_skipped_topic_fetched` |
| archive: drop the "already archived" check | `test_archive_second_run_adds_missing_symbols_only` |
| exception reason `error_class(exc)` -> `exc!r` (leaks the message) | `test_fetch_alone_exception_reports_class_only` (the planted-secret test) |

**No network:** every new test uses a fake TrendReq. The runner, pull and probe tests also call `trends_fixtures.block_network` (any socket connect fails). `pytrends` is not installed in the api env.
**Planted secret:** `SECRET` sits in exception messages and headers. Tests assert it never appears in a reason, the summary line or the probe output (`test_fetch_alone_exception_reports_class_only`, `test_summary_line_counts_every_outcome`, `test_alone_output_has_no_message_or_header`).
**Banned-names guard:** `api/tests/tooling_guards` ran inside G5 and is green.

## 7 Tests NOT run

- No live Google call: by design, these are owner probes (heading 10).
- T100c gates: out of scope.
- Ruff is not a repo gate (`ci.yml` says no linter is configured). It was run on the touched files anyway. The one remaining finding (BLE001 at `trends.py:30`) is in the old `fetch_series` and was already there before this change.

## 8 Deviations

1. **File outside the PLAN list: `api/tests/scripts/test_refresh_attention_extra_hardening.py`.** Five of its tests drove the old ticker-path `_run_trends` (they patched `trends.fetch_series` and passed `S0..S19` with no keyword file). The PLAN's design replaces that runner, so those tests could not pass. The PLAN missed this file in its file list. They were changed as follows (d = 2 deleted, 3 replaced):
   - Replaced, 3: `test_trends_breaker_stops_after_5_blocks...` became `test_guarded_breaker_stops_after_5_blocks_and_keeps_earlier_series`, and `test_trends_code_errors_do_not_trip_breaker` became `test_guarded_code_errors_do_not_trip_breaker`. `test_time_budget_stops_cleanly_and_keeps_fetched` keeps its name. All 3 now drive `_collect_guarded` directly; Reddit still uses that function, so its breaker and budget coverage stays.
   - Moved, 2: `test_trends_partial_results_are_stored_and_line_is_not_failed` is replaced by `test_exit_code_success_with_rate_limited_count`, and `test_trends_all_blocked_line_is_unavailable_never_zero_rows` by `test_all_rate_limited_line_is_unavailable_never_zero_rows`. Both new tests are in `test_refresh_attention_trends.py` and check the same line classification on the new runner.
2. **Two extra runner tests** (15, not 13): the 2 moved tests above, plus `test_pytrends_missing_marks_fetchable_coins_unavailable`. Without pytrends, which is today's workflow state until T100c, the old adapter reported `unavailable` (yellow). The new runner keeps that: the reason `pytrends not installed` classifies as `unavailable`, not `failed`. So merging T100b does not turn the daily extra job red.
3. **`safe_load()` is called without `placed_symbols`.** Passing the run's universe would make one new universe coin with no entry void the whole keyword file, and every coin would go missing. Instead the file is validated as a whole (a bad file still gives `bad keyword file` for every coin), and a symbol with no entry gets `no keyword mapped`.
4. **The summary has one extra bucket, `time-budget`**, so budget-capped coins are not counted as `rate-limited`. The summary is printed as a separate `trends detail:` line. The standard `trends: N/M ok, R rows written [...]` line that the workflow verifier parses is unchanged.
5. **429 handling, interpreted:** "three tries" is read as three retries after the first request (30, 60 and 120 s waits), so a coin makes at most 4 requests before it is `capped`.
6. A `capped` coin keeps its previous stored series. Nothing is written for it.

## 9 Blockers

- **This failure already exists on main and is not caused by this change:** `api/tests/analytics/attention/test_weights_v2.py::test_committed_frozen_snapshots_match_their_days_weights` fails on fresh origin/main 27b2ac8 (`AssertionError: 2026-10-21_w30.json`, a source-weights mismatch). It comes from the data commit `034c93c chore: attention refresh 2026-10-22`, which added `api/data/cache/attention/signals/2026-10-21_*.json`. This branch does not touch `api/data/cache/` or `api/analytics/`, and G7 is OK. That is why G4 shows 280 rather than 281 and G5 shows 1905 rather than 1906. A separate task should look at it (heading 10).
- PR #157 (T134) changes `api/data/trends_keywords.json`. The tests do not depend on the real keyword file except the probe `--alone` tests, which read the keyword for AAVE and INJ from the file instead of hard-coding it. When #157 merges, merge origin/main into this branch (no rebase).
- Risks R1 to R6 of the PLAN still stand. All live Google behaviour is UNVERIFIED (heading 10).
- Registry update request: mark T149 (T100b) as `done, draft PR`. T100c stays blocked until the owner approves the `.github/` change.

## 10 Follow-up

**Owner probes (PowerShell, repo root):**

```
# P-CHK  topic ids for the 12 risky names (until a topic is set, the daily run skips them: name-ambiguous)
uv run --project api --with pytrends python -m api.scripts.check_trends_keywords --symbols 'TRX,ONDO,MORPHO,ICP,SHIB,PEPE,BNB,CRO,HBAR,LINK,APT,SOL'

# P-RES  single-term resolution over the explicit 100-day daily range (works on this branch or after merge)
#        end = yesterday, start = end minus 99 days; for a run on 23-10-26:
uv run --project api --with pytrends python -m api.scripts.probe_trends --alone 'LINK,AAVE,INJ,MORPHO,ONDO,PEPE' --timeframe '2026-07-15 2026-10-22'

# P-RES-B  the same coins with the default window, to compare
uv run --project api --with pytrends python -m api.scripts.probe_trends --alone 'LINK,AAVE,INJ,MORPHO,ONDO,PEPE'
```

Paste the output back. Each coin prints a line like `LINK (Chainlink) | step daily | days 100 | min .. | median .. | max .. | at 0: .. | at 0 or 1: .. | distinct .. | zero share ..% | verdict: ..`.

**Numbers the owner must set after P-RES** (both in `api/data/attention/trends.py`, one line each):
- `TRENDS_MIN_MEDIAN = 3`: the minimum median of a coin's own daily series. A coin below it is missing.
- `TRENDS_MAX_ZERO_DAY_PCT = 40`: the maximum share of zero days, in percent. A coin at or above it is missing.

P-RES also answers whether the explicit range returns 100 daily rows (look for `step daily | days 100`). If it does not, the PLAN's risk R3 applies.

**Proposed tasks:**
1. T100c: the workflow step (needs the owner's separate approval of the `.github/` change, as the PLAN describes).
2. Point-in-time reader: history for a past day D read from `trends_pulls/D.parquet`.
3. Look into the `test_weights_v2` frozen-snapshot failure on main, from data commit 034c93c (heading 9).
4. Optional: add `too-little-interest`, `name-ambiguous: needs topic`, `non-daily` and `pytrends not installed` to `attention_extra.DATA_REASONS`. Today they classify as `provider` (yellow), which is safe but not precise. That file is outside this slice.

## 11 Context cost

Files loaded: CLAUDE.md, the task envelope, the T144 PLAN (all of it) and the master-planner.md section 9 template. Code: `trends.py`, `store.py`, `trends_keywords.py`, `probe_trends.py`, `trends_cli_common.py`, part of `pytrends_adapter.py`, `refresh_attention.py`, `discovery.py` lines 150-200, `attention_extra.py`, `types.py`, and the existing tests and fixtures (`trends_fixtures.py`, `test_store.py`, `test_trends.py`, `test_probe_trends.py`, `test_refresh_attention_extra_hardening.py`, conftests). Not opened: the T144 REPORT, the T120 SPEC and the T121 PLAN; the PLAN quoted what this slice needed from them. Approximate tokens: about 200k. USD: not metered in-session; estimated well under the 10 USD ask level. Tools: Bash, Read, Write, Edit, GitHub MCP.
