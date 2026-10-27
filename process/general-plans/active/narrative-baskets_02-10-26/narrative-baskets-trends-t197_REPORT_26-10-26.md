# T197 report: Trends per-coin outcomes per run, one retry of an empty response

## 1 Summary
Each daily Trends run now writes `api/data/cache/attention/trends_runs/<UTC date>.json` with one record per coin (outcome, reason class, keyword kind, median, zero share, last-7 vs prior-28 ratio, attempts, retried). An `empty response` is retried once after 10 s plus jitter. The existing `trends detail:` fields and the 429 backoff/breaker are unchanged. Real Google behaviour is not provable here.

## 2 Owner reads after the next run
File: `api/data/cache/attention/trends_runs/2026-10-27.json` (the bot commits it; the workflow already force-adds the folder).
List failed coins (PowerShell, from the repo root):
`python -c "import json,sys;d=json.load(open(sys.argv[1]));[print(s,c['reason'],c['attempts']) for r in d.get('runs',[d]) for s,c in r['coins'].items() if c['outcome']=='failed']" api/data/cache/attention/trends_runs/2026-10-27.json`
Also read: `totals` (counts per outcome, `retried`, `recovered`) and the log line `trends detail: ... retried N (recovered M)`.

## 3 File shape
First run of a UTC day: `{run_started_utc, run_finished_utc, pytrends_version, budget_s, coins, totals}`. A second run the same day turns the file into `{"runs": [earlier, later]}` (appended, never overwritten); the one-liner above handles both. Outcomes: ok, too-little-interest, quiet-then-surge, no-keyword, skipped-unqualified, failed, capped, time-budget. non-daily and insufficient-history are `failed` with that reason. Reasons are exception class / HTTP status or fixed labels, cleaned to `[\w ():.,-]` and cut to 80 chars. Stats are filled for ok, too-little-interest and quiet-then-surge; ratio is null when the prior-28 mean is 0. `attempts` counts every request (429 backoff repeats included). pytrends_version is null when not installed. Size: 100 coins, 2 runs, under 40 KB (tested).

## 4 Retry rules
Retried once: `empty response` only, wait 10 s + `_jitter()`, same request. Never retried: 429 (existing 30/60/120 backoff), exceptions, parse, bad-value, out-of-range, not-current, non-daily, missing-column, too-little. A retry that would end past the 540 s budget is not started: the coin is `time-budget` and the source stops (same as the 429 wait rule). A retry answered with 429 goes through the existing backoff and counts once toward the 3-in-a-row breaker; empty twice is `failed` and never feeds the breaker. `recovered` = retried and the final outcome is ok.

## 5 Files changed
`api/scripts/refresh_attention.py` (retry, run record, detail suffix, store-failed hook), `api/data/attention/trends.py` (`series_stats`, optional `stats` out-param of `fetch_alone`), `api/data/attention/trends_runs.py` (new: path, atomic append), `api/tests/scripts/test_refresh_attention_trends_runs.py` (new, 33 tests), this report. No .github, pyproject, uv.lock, keyword file.

## 6 Commits
Red `7086a97` (27 of 30 fail, 3 pass trivially), then green (code + tests fixed where my red tests had bugs: wrong frame end date, rotation order, ratio fixture), then this report. PR is a draft to main, not merged.

## 7 Tests run
`pytest api/tests/scripts api/tests/data/attention`: 886 passed (853 on main + 33 new). Full `pytest api`: 2286 passed, 1 skipped, 5 deselected, no failure (not re-run on main since nothing failed). Existing attention_extra and trends tests untouched and green. Includes a subprocess test of the `2>&1` pipe last-line rule for a run-file write failure. ruff: refresh_attention.py 15 findings (same as main), trends.py 1 (same), new files clean. `git diff --check` clean, secret scan no hits, file set as in section 5.

## 8 Mutation check
18 mutations on the new logic (retry any failure, wait 0, no jitter, no budget check, recovered=retried, retried flag, attempts count, empty feeding the breaker, overwrite instead of append, store-failed hook, capped mapping, sanitizer off, cut removed, ratio window, stats not cleared, detail note always, totals, zero-share). First pass: 13 killed, 4 survived (sanitizer, cut, stats reuse, zero-share arithmetic), 1 mis-targeted by my script (hit another function, redone precisely: killed). Added 3 tests; all 18 killed. The sanitizer test also exposed `::` surviving; collapsed.

## 9 Not provable here
Real Google behaviour: whether an empty response is transient, how often 10 s recovers it, pytrends version string. The next daily run shows it in `totals.retried/recovered`.

## 10 Risks and decisions
A run-file write failure is red by the owner's rule even though the series are stored. A corrupt earlier same-day file raises (kept, not overwritten) and so also ends red. First-run top-level shape kept literally as specified; always using `runs` would be simpler for readers.

## 11 Docs opened
operating-instructions.md, decisions.md and protocols not opened. Read: CLAUDE.md, the envelope, the named code and tests, the T194 report (3.2).

## Round 2 (T200)
Review T199 of 82ae7f4: merge after fixes. Fixed on the same branch, red `f3664da` first, then green.

**Change: the empty-response retry is deferred.** Sections 4 and 8 above describe the inline retry and are superseded by this section.
- Main pass: an `empty response` is recorded as `failed (empty response)`, attempts 1, retried false, no sleep. Healthy coins are never delayed by a retry.
- After the whole main pass, each empty coin is retried once, in main-pass order, with a single request (no 429 backoff), 10 s + jitter (`TRENDS_EMPTY_RETRY_WAIT_S`) after the previous step. The budget (540 s) is checked before each retry including its wait. A retry that does not fit is not started: the coin keeps `empty response`, run record `retry_skipped: "retry-skipped-budget"`. At most `TRENDS_MAX_RETRIES_PER_RUN = 20` retries; the rest get `retry-skipped-cap`.
- Never retried: 429, ConnectionError and other exceptions, parse-failed, bad-value, out-of-range, not-current, non-daily, missing-column, insufficient-history, too-little-interest.
- A 429 in the deferred pass is recorded for that coin (capped, attempts 2, retried true) and ends the pass. The remaining empty coins get `retry-skipped-rate-limit`. This reason name is my choice; the envelope named none for this case. The 3-in-a-row breaker and the 429 backoff run in the main pass only, unchanged.
- A recovered coin is stored exactly like an ok coin (main() replace-series, 90-day gate untouched); its record shows attempts 2, retried true, outcome ok. `recovered` = retried and ok.
- Run record: each coin gets `retry_skipped` (null or a reason above); `totals` gets `retry_skipped` (count). Existing fields are unchanged.
- Detail line: existing fields intact, suffix `, retried N (recovered M, skipped K)`, shown when N or K is above 0 (before: only when N was above 0). The `trends:` summary line for attention_extra is unchanged.

**Simulation (fake clock, 2 s per request, 540 s budget, 92 coins, 20 empty):** all 72 healthy coins stored, main pass about 457 s, then 6 retries fit; 14 empties are `retry-skipped-budget`. The last request can end up to one request time (2 s) past 540, because the check is on the wait, not on the request. Before: 3 healthy coins lost.

**Low findings:** the varying-prior-window fixture is added (`series_stats` ramp case: prior 28 days ramp 1..28, ratio 2.0), which pins the 28-day window. The other two Lows from T199 were not relayed; from re-reading my own diff I removed the inline-retry code and the `once()` closure with its optional `calls` argument (now a module function with required arguments), and fixed the comments that described the inline retry. No behaviour guessed beyond the above.

**Gates (T200):** `pytest api/tests/scripts api/tests/data/attention`: 1087 passed (main merged in; 39 tests in the T197 file, was 33). Full `pytest api`: 2507 passed, 1 skipped, 5 deselected, no failure. Mutation check: 17 mutations on the changed logic (budget check removed, jitter left out of the check, cap `>=` to `>`, cap removed, 429 not ending the pass, retry using the 429 backoff, attempts not carried, stats of the retry dropped, empty-reason filter dropped, retried flag, suffix only when retried, skipped count, wrong skip reason, retry counter, reversed order, 28-day window to 14, recovered = retried): 14 killed on the first pass, 3 survived (retry stats dropped, suffix when only skipped, empty-reason filter), two tests added, 17 of 17 killed. ruff: refresh_attention.py 18 findings vs 16 on main (the two extra are T197's `_utcnow` UP017 and one BLE001, same idiom as existing code, left alone); trends.py 2 (same as main); new files only the repo-wide I001 import quirk. `git diff --check` clean, secret scan no hits (only the fake test secret constant), file set unchanged from section 5 (plus the merged-in main files).

**Tests:**  `test_retry_refused_when_it_would_end_past_budget`, `test_retry_that_hits_429_counts_once_toward_the_breaker` and the inline-retry expectations were replaced by deferred-pass tests (empties among 92, budget short, jitter counted in the budget check, cap of 20, 429 ends the pass, recovered stored as ok, detail line, run-record fields, breaker unchanged). The `2>&1` store-failed last-line test is unchanged and green.

**Docs opened:** none beyond CLAUDE.md, the envelope, the PR code and tests.
