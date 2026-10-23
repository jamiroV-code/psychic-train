---
name: report:narrative-baskets-trends-t149-t100b-r2
description: "T149 round 2: fixes from the independent review T152 on PR #162 (M3 fail-closed pulls and store guard, M2 quiet-then-surge, M-pin, LOW items) plus the planner's qualified-term rule for risky symbols. M1 (point-in-time chart) is characterized by a test but not fixed: the fix needs an api/analytics change, so it needs the owner's input."
date: 23-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T149 round 2 (T152 review fixes on PR #162): REPORT

## 1 Task ID

T149 round 2. Fixes from review T152 (verdict MERGE AFTER SMALL FIXES) on PR #162, branch `claude/t149-t100b-trends-fetch`. Round 1 is `narrative-baskets-trends-t149-t100b_REPORT_22-10-26.md`.

## 2 Outcome

**needs_input** for M1 only (heading 9). M3, M2, M-pin and both LOW items are done.

## 3 Summary

- **Merged origin/main** (9c128cc, includes #157 topic ids and #159 plan) into the branch: merge commit, no rebase, no conflicts.
- **M3 (data integrity), done.** `fetch_alone` now fails closed and stores nothing unless every check passes:
  - no row after yesterday (`out-of-range`);
  - the last row is yesterday (`not-current`);
  - no row before the requested start of an explicit range (`out-of-range`);
  - daily steps with no duplicate date (`non-daily`);
  - no missing value (`gap`);
  - at least 90 complete days.
  `store.write_series(mode="replace-series")` now checks the series itself (`_replaceable`), so no caller can bypass `fetch_alone`. It rejects a series that is shorter than 90 rows, all zero, unsorted, has a duplicate date or has a gap; the stored series is then left as it was. A row dated today or later is still dropped before the check, as in every store mode.
- **M2 (interest rule), done.** New reason `quiet-then-surge`. The coin fails the rule, but its baseline (the days before the last 7) has a median under `TRENDS_MIN_MEDIAN`, and each of the last 7 days is above 0 with a median of at least `TRENDS_MIN_MEDIAN`. Such a coin is still missing: never stored, never 0, never archived. It has its own bucket in the `trends detail:` line. Example: 93 zero days then 7 days at 80 now reads `quiet-then-surge`, not `too-little-interest`. Discovery scoring is not changed.
- **M-pin, done.** A runner-level test runs `main()` with Wikipedia and Trends and spies on every `store.write_series` call. Only Trends uses `replace-series`; Wikipedia uses `first`. The reviewer's surviving mutation (replace mode for every source) is now killed.
- **LOW, done.**
  - (a) `probe_trends --alone` now defaults to the daily run's explicit 100-day range ending yesterday. The owner no longer types dates; `--timeframe` still overrides.
  - (b) The 540 s budget is now checked before every 429 backoff wait. A wait that would end past the budget is not started; that coin and the rest are capped `time budget reached`.
- **Qualified terms for risky symbols (planner, after T155), done.** `NAME_RISK_SYMBOLS` now skips a `term` entry only when it is unqualified: the bare name or ticker. A qualified term is pulled: one with a qualifier word (`crypto`, `coin`, `token`, `network`, `protocol`, `finance`, `swap`, `chain`) beside the name, as produced by the checker v3 "qualified-term fallback". For example, `tron crypto` and `Aptos Crypto` are pulled; `Tron`, `TRX`, `Aptos`, `Crypto` alone and `tron classic` are skipped. Topic entries are always pulled. The status-line bucket is now `skipped-unqualified`, and the reason reads `name-ambiguous: needs topic or qualified term`. The probe's risk note follows the same rule. Commit 7f91951.
- **M1 (point-in-time), characterized, NOT fixed.** A truncate-and-recompute test shows which past chart days change after a replace. The fix needs an `api/analytics/` edit, which is a hard stop of this slice. Options are in heading 9.

## 4 Files changed

Within the nine PLAN paths only (round 2 adds no new file except this report):
- `api/data/attention/trends.py`: `QUALIFIER_WORDS`, `is_qualified_term`, `requested_range`, `OUT_OF_RANGE`, `NOT_CURRENT`, `QUIET_THEN_SURGE`, `SURGE_DAYS`, fail-closed checks in `fetch_alone`. `complete_days(frame, term)` no longer filters dates and rejects NaN values as `gap`.
- `api/data/attention/store.py`: `_replaceable` guard for replace-series.
- `api/scripts/refresh_attention.py`: the qualified-term check in `_run_trends`; the `skipped-unqualified` and `quiet-then-surge` buckets; the budget deadline passed into `_trends_fetch_429`.
- `api/scripts/probe_trends.py`: the `--alone` default timeframe; `--timeframe` defaults to None and resolves per mode.
- Tests: `test_trends.py` (+6, 1 rewritten), `test_store.py` (+1 with 4 cases, 1 rewritten), `test_trends_pull.py` (+1, the M1 characterization), `test_refresh_attention_trends.py` (+3, plus the qualified-term test with 2 cases), `test_trends.py` also gains `test_qualified_term_rule` (16 cases), `test_probe_trends.py` (1 rewritten).
- This report.

## 5 Commits

Branch `claude/t149-t100b-trends-fetch`:
- `7f1692c`: merge of origin/main 9c128cc
- `112d5a6`: T152 fixes plus this report
- `7f91951`: qualified terms for risky symbols
- `534e949`: merge of origin/main 7c73d3f (includes #163, the weights-guard fix)

## 6 Tests run

All runs used `UV_FROZEN=1`, from the repo root, on 23-10-26 UTC.

| Gate | Baseline origin/main 9c128cc | Branch after round 2 | Result |
|---|---|---|---|
| G1 (5 Trends test files) | n/a (the new files are not on main) | 101 passed (round 1: 87) | PASS |
| G2 data group | 197 passed | 235 passed (+38: round 1 +27, round 2 +11) | PASS |
| G3 scripts | 358 passed | 379 passed (+21: round 1 +18, round 2 +3) | PASS |
| G4 attention analytics | 280 passed, 1 failed (`test_weights_v2` guard; fix in PR #163) | 280 passed, 1 failed (the same test) | unchanged, already failing on main |
| G5 full API | 1874 passed, 1 failed (same test), 1 skipped, 5 deselected | 1933 passed, 1 failed (the same test), 1 skipped, 5 deselected: +59 = round 1 +45 and round 2 +14 | same single failure, already on main |
| G7 frozen hashes | | `OK` x3 | PASS |
| G9 scale invariance | | 1 passed | PASS |
| G10 imports; no network or pytrends import | | import exit 0; the grep printed nothing | PASS |
| G11 default store mode | | 38 passed | PASS |
| ruff on the touched files | | only the BLE001 in the old `fetch_series` remains (it was already there) | |

**After the qualified-term change and the merge of main 7c73d3f** (#163 merged): G1 119 passed. Full API: **1961 passed, 0 failed**, 1 skipped, 5 deselected. Baseline on main 7c73d3f: 1884 passed, 0 failed. +77 = round 1 +45, round 2 +14, qualified terms +18. G7 3x OK, `git diff --check` clean. The weights-guard failure is gone.

**Red first, qualified terms:** 19 failed before the code (16 rule cases, 2 runner cases, and the summary bucket rename). **Mutations:** dropping the qualified-term check in the runner was killed by `test_risky_symbol_bare_term_skipped_qualified_term_fetched`; dropping the "a word besides the qualifier" condition was killed by `test_qualified_term_rule`.

**Red first.** The new and rewritten tests on the fix-free code (same G1 command) gave `14 failed, 87 passed`. Two new tests were green before any code change, by design:
- `test_replace_mode_pinned_to_trends_only` pins correct current behaviour; the mutation check below proves it.
- `test_replace_revises_past_chart_days_truncate_and_recompute` characterizes the current M1 behaviour.

**Mutation check.** 16 mutations; all were run again with `PYTHONDONTWRITEBYTECODE=1` and an mtime bump after each restore. A same-size mutation restored within the same second left a stale `.pyc` once, and I caught it. All 16 killed:

| Round 2 mutation | Killed by |
|---|---|
| store: drop the all-zero check | `test_replace_series_rejects_bad_series_itself[all-zero]` |
| store: consecutive-day check `== 1` -> `>= 1` | `...[gap]` |
| fetch_alone: drop the last-row-is-yesterday check | `test_fetch_alone_pull_ending_10_days_ago_fails_closed` |
| fetch_alone: drop the before-start check | `test_fetch_alone_150_rows_fails_closed` |
| surge: drop the quiet-baseline condition | `test_many_zero_days_too_little_interest` |
| runner: drop the budget check inside backoff | `test_time_budget_checked_inside_backoff` |
| runner: replace-series for every source (the reviewer's survivor) | `test_replace_mode_pinned_to_trends_only` |
| probe: `--alone` default back to `today 3-m` | `test_alone_one_request_per_symbol` |

All 8 round-1 mutations were re-run on the new code (two of them retargeted to the rewritten lines): all killed.

## 7 Tests NOT run

- No live Google call (owner probes, heading 10).
- Web checks were not run: web is untouched.

## 8 Deviations

- `complete_days` lost its `today` parameter. Date filtering moved into `fetch_alone`, so a pull outside the range fails instead of being trimmed silently. The probe filters `d < today` itself.
- The ordering of the fail-closed checks is chosen so that each case gets the most telling reason:
  1. a row after yesterday: `out-of-range`
  2. a last row that is not yesterday: `not-current` (this covers a stale pull and a partial yesterday)
  3. a row before the start: `out-of-range` (an oversized pull)
- With a relative timeframe (`today 3-m`, only possible from the probe or a direct caller), there is no start bound. The last-row check still applies.

## 9 Blockers

**M1, needs_input: past chart days change when the Trends series is replaced.**

What happens, shown by `test_replace_revises_past_chart_days_truncate_and_recompute`:
1. `discovery_history` rebuilds every past day from the live store (`_Stored.at(day)`, gated to 90 points dated <= that day).
2. A replace-series pull holds exactly 100 days. So only the newest 11 chart days carry Trends at all.
3. Each daily replace drops the oldest row. The chart day that had exactly 90 points then loses Trends retroactively: one past day per day.
4. A pure rescale (Google renormalising) changes nothing else.
5. A revised past value (Google re-sampling) moves every chart day whose 14-day span holds that value. In the test, one value 5 days back moves the last 5 chart days.

Who else reads the series:
- **Frozen signal snapshots:** cannot change. They are files; G7 confirms the hashes.
- **The sources panel:** shows only history days and the last day.
- **Live Discovery for today:** uses the current pull, and that is intended.

Not live yet: Trends is still `not-probed` in the registry until T100c records a probe, so nothing reads it today.

Options (each one edits `api/analytics/attention/discovery_history.py`, a hard stop of T100b, so the owner must approve):

| Option | What | Effort | Point-in-time? |
|---|---|---|---|
| **A (recommended)** | For Trends, the chart day D reads the pull archive `trends_pulls/(D+1).parquet` (the pull the live score used on the run after D), gated as now. No archive for D+1 means no Trends that day, never 0. | About 40 lines plus 6 tests, about 2 to 4 USD, in a separate task (T100b-PIT). The archive already exists from this PR. | Yes, exactly what the live score saw |
| B | The chart reads frozen snapshot values for every day that has a snapshot, and the live store only for newer days. | Larger: changes all sources' chart path. Also, snapshots are taken before `refresh-extra`, so they lag Trends by a day. | Partly |
| C | Accept the revision and document it. | 0 | No |

Recommendation: **A**, as its own small task after this PR merges, before T100c records the Trends probe (that is when the chart starts reading Trends).

**Owner question (M2b, SPEC/signal rule):** should "rising from nothing" (a `quiet-then-surge` coin) count as rising? The default for now is **NO**: the coin stays missing, Discovery is unchanged (`base_mean <= 0` already gives None), and the coin is only counted in the `trends detail:` line. A YES needs a SPEC change to the trigger rule.

**CI:** #163 has merged and main is merged into the branch (534e949). The full API suite is green locally (1961 passed, 0 failed); CI re-runs on the push.

**Owner decisions, 23-10-26 (relayed by the planner):** M1 = option A as a separate task T100b-PIT after #162 merges; nothing more for M1 in #162. M2b = NO for now: `quiet-then-surge` stays shown but not scored.

**Registry update request:** T149 round 2 done except M1 (needs_input); propose T100b-PIT (option A).

## 10 Follow-up

**Owner probes (PowerShell, repo root).** No dates needed now: `--alone` defaults to the 100-day range ending yesterday.

```
# P-CHK  topic ids (or a qualified-term fallback) for the risky names still on a bare term
uv run --project api --with pytrends python -m api.scripts.check_trends_keywords --symbols 'TRX,ONDO,MORPHO,ICP,PEPE,BNB,CRO,HBAR,APT'

# P-RES  single-term resolution over the daily run's own range (ends yesterday automatically)
uv run --project api --with pytrends python -m api.scripts.probe_trends --alone 'LINK,AAVE,INJ,MORPHO,ONDO,PEPE'

# P-RES-B  the same coins over Google's relative window, to compare
uv run --project api --with pytrends python -m api.scripts.probe_trends --alone 'LINK,AAVE,INJ,MORPHO,ONDO,PEPE' --timeframe 'today 3-m'
```

For an explicit range, the end must be YESTERDAY and the start 99 days earlier. For a run on 23-10-26 that is `--timeframe '2026-07-15 2026-10-22'`. The reviewer verified `'2026-07-14 2026-10-21'` for a run on 22-10-26.

**Numbers to set after P-RES** (in `api/data/attention/trends.py`):
- `TRENDS_MIN_MEDIAN` (now 3): the minimum median of a coin's own series. It also sets the surge test's "live last week" level.
- `TRENDS_MAX_ZERO_DAY_PCT` (now 40): the maximum share of zero days, in percent.
- `SURGE_DAYS` (now 7) can stay. It matches the recent window of Discovery.

**Proposed tasks:**
1. T100b-PIT (M1 option A).
2. T100c (workflow, owner approval).
3. Owner SPEC decision on "rising from nothing".

## 11 Context cost

Loaded: the T152 review message, the current PR #162 diff (own code), `discovery_history.py` lines 1-100, `discovery.py` `_source_change`, the CI job log, and the PR #163 file list. About 60k tokens for this round. USD not metered in-session; my estimate for both rounds together is under the 10 USD ask level. Tools: Bash, file tools, GitHub MCP.
