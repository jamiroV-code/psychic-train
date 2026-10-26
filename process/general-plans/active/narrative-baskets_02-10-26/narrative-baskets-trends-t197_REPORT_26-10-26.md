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
