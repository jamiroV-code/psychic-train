---
name: plan:narrative-baskets-trends-t100b
description: "T144 FAST MODE PLAN and VALIDATE (COMPLEX) for slices T100b (Trends fetch: one coin per request, replace-series store, per-pull archive, too-little-interest rule) and T100c (daily workflow integration, needs the owner's separate approval because it touches .github/). Compares four batching designs against owner-run evidence and the code. Docs only."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# Trends by name, slices T100b and T100c: PLAN (how the daily pull is batched)

[MODE: VALIDATE]

Date: 21-10-26
Complexity: COMPLEX (two slices with different approvals; one touches `.github/`)
Status: VALIDATED: Gate: PASS (T100b). T100c is planned only and is blocked on the owner's approval of the `.github/` change.
Validation: T144 (FAST MODE: compressed RESEARCH, INNOVATE, PLAN, VALIDATE in one session), 21-10-26, on `main` 4675f82. Next step: the owner's separate ENTER EXECUTE MODE for T100b. This session builds nothing and did not contact Google.

**Summary:** The SPEC (T120, `narrative-baskets-trends-by-name_SPEC_21-10-26.md`) puts an anchor term (Bitcoin) in every request and divides each coin by it. The owner's real-Google run shows that crushes small coins to 0 or 1. The code shows the anchor is not needed: every consumer of a stored series uses a per-coin ratio (recent mean over longer mean), which does not change if a whole series is multiplied by a constant. So each coin only needs one request scale for the days it is compared, and a coin requested ALONE peaks at 100, which is the best possible resolution. **Recommended design: one coin per request (design 1), replace the whole stored series on every daily pull, archive each pull by pull date, and mark a coin missing (never 0) when its series is too sparse.** About 43 requests today (up to 75), roughly 3 to 6 minutes at 3 s spacing. The anchor, the per-day ratio and the anchor ladder are dropped.

## Overview and Context

Context router: `process/context/all-context.md`; tests: `process/context/tests/all-tests.md`. Phase Completion Rules: T100b is done when its red tests are green, the gates of the Validate Contract pass, and the report lists the owner probes. T100a (keyword file, validator, check tool, probe) is merged on main (verified: `api/data/attention/trends_keywords.py`, `api/scripts/check_trends_keywords.py`, `api/scripts/probe_trends.py`, `api/scripts/trends_cli_common.py` exist on 4675f82). The runner still calls `trends.fetch_series(s, s.lower(), ...)` with the ticker (`api/scripts/refresh_attention.py:178`); T100b replaces that.

## 1. Goal and non-goals

**Goal.** Trends (weight 25) becomes a working source: per in-universe coin with a keyword, a daily series of at least 90 complete UTC days on one request scale, refreshed daily, with enough resolution that a +10 percent change of the 7-day mean is meaningful, and honest `unavailable` where Google gives too little signal.

**Non-goals.** Cross-coin comparable Trends levels (not needed, section 2); a Trends "level" display; the anchor, per-day ratio and bridging machinery of the SPEC; reader changes for point-in-time history (the archive is written now, the reader is a later task); `.github/` edits (T100c, needs the owner); weights; a paid Trends API; fixing keywords (owner runs the checker).

## 2. Key question answered from the code

Claim to test: cross-coin comparability of Trends levels is not needed for the trigger; each coin needs resolution and a stable scale across the days that are compared.

**Evidence (all read on `main` 4675f82):**
1. Trigger path: `discovery._source_change` (`api/analytics/attention/discovery.py:166-183`) takes, per coin and source, `mean(last 7 days) / mean(window days before) - 1`, with `window` 7, 30 or 90 (`api/routers/discovery.py:27`). Multiplying a coin's whole series by a constant `k` cancels in that ratio. Coins are never added or compared on Trends level; they are combined only as booleans "rising or not" weighted by source weight.
2. Rank-score path (older feature): `series.ratio_at` calls `attention_ratio` (`api/analytics/attention/ratio.py:12-21`, mean of last 7 over mean of last 90, needs at least 90 points), then ranks the RATIO against other coins' ratios (`series.py:33-37`). Also a per-coin ratio; the level is never ranked.
3. Nothing reads a Trends level: `grep trends` over `api/analytics/attention/*.py` finds only the weighted-source list and the panel label (`discovery.py:38`, `sources.py:23`). The sources panel shows history days and last day only (`sources.py:63-77`).

So the requirement is: **inside one stored series, all days that a window compares must share one scale.** The widest compared span is 7 + 90 = 97 days (window 90). One request with an explicit 100-day daily range covers it. Rows pulled on different days sit on different scales (Google renormalises every request), so they must never be mixed in one series.

**(a) Stitching successive daily pulls.** Not needed if each daily run REPLACES the whole stored series with the full window it just pulled (replace-series, section 4). No overlap, no stitching. The SPEC's "keep stored dates outside the new window" is the part to drop: it would leave older rows on an old scale at the edge of the 97-day span. With a 93-row pull (92 complete days, owner evidence) the oldest 5 days of a window-90 base would otherwise come from an older pull. With a 100-day explicit range they are all inside the pull.
**(b) A "level" display.** No consumer exists (point 3). A level would need cross-coin anchoring; it is a future feature, not a reason to build the anchor now. Challenged and removed from scope.
**(c) Detecting "too little interest".** The anchor does not help and a level rule cannot work alone: a coin requested alone peaks at exactly 100 by construction, so "stays at 0 or 1" can only be true for an all-zero series. The right test is sparsity of the coin's own series (days at 0, median), section 3 and 5. The anchor's only legitimate job (comparing sizes) is not needed.
**What the anchor would actively break.** With the SPEC formula `raw(coin)/raw(anchor)*100`, both numerator and denominator are integers; Chainlink (median 1, max 2, owner evidence) over Bitcoin (median 37) becomes values like 2.7 and 5.4 from rounding noise, and a Bitcoin spike lowers every coin's value, creating false "falls" and, on a Bitcoin drop, false "rises" (SPEC risk R2). That is the opposite of what a per-coin trigger needs.

**Residual caveat (UNVERIFIED, owner probe P-RES):** whether a very small coin requested alone has real structure (not mostly zeros). Google zeroes terms below a privacy threshold, so Morpho and similar may still be empty alone. The rule in section 3 marks those coins missing instead of inventing a signal.

## 3. Design comparison (INNOVATE)

Numbers for N coins with a keyword: N = 43 today (43 `term`, 0 `topic`, 32 `no-keyword` in `api/data/trends_keywords.json`), up to 75 once topics are pasted. Latency 0.5 s (owner evidence). Spacing S = 3 s as `probe_trends.INTERVAL_SECONDS` (`api/scripts/probe_trends.py:44`), plus up to 2 s jitter in the runner. Seconds = requests x (S + 0.5).

| | 1. One coin per request (RECOMMENDED) | 2. Size-tiered batches of up to 5 | 3. Anchor ladder with bridging | 4. T120 SPEC as written |
|---|---|---|---|---|
| Requests per daily refresh | N: 43 now, 75 max | ceil(N/5) + first-pass ranking: about 9 to 15 now, 15 to 20 max (the ranking needs its own pull or a stored median) | about N/3 batches plus bridges: 20 to 35 | 1 + ceil(N/4): 12 now, 20 max (+1 second anchor for BTC/ETH) |
| Seconds at 3 s spacing (no jitter / with mean 1 s jitter) | 151 / 194 for 43; 263 / 338 for 75 | 32 to 53 / 40 to 66 | 70 to 123 / 90 to 150 | 42 to 73 / 54 to 90 |
| Resolution per coin | Best: each peaks at 100 | Depends on the biggest term in its batch; a mis-tiered coin is crushed; a batch-mate spike coarsens a coin's integers for that pull | Good only for coins mid-batch; bridge ends sit between 20 and 80 by rule so only some coins qualify | Worst: Bitcoin in every request, small coins read 0 to 3, then divided by the anchor's own integer |
| Scale stability between daily pulls | One scale per coin per pull; replace-series, nothing to stitch | Same: one scale per batch per pull; replace-series | Needs stitching across batches (error accumulates along the ladder); not needed for change | Per-day ratio keeps a common scale but injects the anchor's movement into every coin |
| "Too little interest" | Own-series sparsity rule (below); a coin is missing, never 0 | Same rule per coin, but a crushed coin is indistinguishable from a quiet one | Same, plus bridge failure | Anchor epsilon only; a coin at 0 or 1 against a large anchor reads as a real value |
| Failure handling | A failed request affects one coin only; others unaffected | A failed request loses up to 5 coins | One failed bridge loses everything above it | One failed batch loses 4 coins; anchor problems lose the batch |
| Failure of the idea | 75 requests may meet a 429 (UNVERIFIED; owner saw none in 5) | Tier ranking can be wrong or stale | Complexity for a level nobody reads | Over-built and degrades the signal |
| Tests needed | fake client, series build, sparsity rule, store mode, runner | all of 1 plus tiering, tier drift, mis-tier cases | all of 2 plus bridge rule and stitching property tests | AC-T3 to AC-T5 of the SPEC (anchor property tests) |
| Verdict | **Chosen** | Rejected as the default; kept as a config-only fallback | Rejected | Rejected |

**Rationale.** The only argument against design 1 is request count, and the arithmetic is small: about 3 to 6 minutes a day, each request independent. Everything else (resolution, stability, failure isolation, test size) favours it. The fetch function takes a list of terms and splits frame columns per term, so if a 429 problem appears a later change can pass 2 to 5 same-size coins per request with no redesign (tiering is then a config change, not a rewrite). T100b ships and tests only batch size 1.

**"Too little interest" rule (applies to design 1, owner tunes the two numbers after P-RES).** On the complete days of one coin's own pull: missing when the series is all zero, or median is below `TRENDS_MIN_MEDIAN` (default 3), or the share of zero days is at least `TRENDS_MAX_ZERO_DAY_PCT` (default 40). Missing means: no store write, `SourceSeries(state="unavailable", reason="too-little-interest")`, counted in the run summary. It is never written as 0. The two defaults are placeholders chosen from the owner's batch evidence (Chainlink and Aave were 0 or 1 on 90 and 91 of 93 days next to Bitcoin) and are replaced by P-RES numbers; they live as named constants so one line changes them.

**Name-fallback risk (the T125 review list).** A bare name for TRON, Ondo, Morpho, Internet Computer, Shiba Inu, Pepe coin, BNB, Cronos, Hedera, Chainlink, Aptos, Solana can collect unrelated searches (Hedera, Cronos, Solana, Aptos, Chainlink, Morpho are also ordinary words or other entities; BNB shares letters with a travel brand). In `api/data/trends_keywords.json` they are `term` entries today (verified, symbols TRX, ONDO, MORPHO, ICP, SHIB, PEPE, BNB, CRO, HBAR, LINK, APT, SOL). Rule for T100b: the constant `NAME_RISK_SYMBOLS` lists those 12; a `term` entry for one of them is NOT fetched (state `unavailable`, reason `name-ambiguous: needs topic`) until the owner pastes a topic from the checker; a `topic` entry is fetched normally. A test proves the skip and proves a topic entry is fetched. This stops a wrong series being ingested under a coin's name; 12 of 43 coins wait for topics (the checker run lists 12 PASS today, among them LINK, SOL, AAVE, INJ).

**Departures from the SPEC.** Differences from SPEC section 3, each listed so the owner can overrule: (1) no anchor and no per-day ratio; (2) `replace-series` instead of `replace-window` (stored dates outside the new pull are dropped, not kept); (3) an explicit 100-day daily date range instead of `today 3-m` (3 months can be 89 to 92 days, which would put a series under the 90-point gate of `registry.read_series` (`api/data/attention/registry.py:49-51`) in some months; explicit dates give a fixed count; daily granularity up to about 270 days is UNVERIFIED and is measured by P-RES with the existing `--timeframe` option); (4) the per-pull archive is added; (5) request spacing and the 429 breaker are kept from the SPEC.

## 4. Store semantics (T100b)

- `store.write_series(series, today=None, mode="first")` gains `mode="replace-series"`. For that mode: take the rows of the new series with `d < today`; if fewer than `MIN_REPLACE_DAYS = 90` rows remain, change nothing and return 0 (a short pull must never shrink a good 92-day series); otherwise the stored series becomes exactly these rows (old rows removed), sorted, written with the existing atomic parquet writer (`cache._atomic_to_parquet`, used at `api/data/attention/store.py:63`). Return the new row count. Default `mode="first"` behaves exactly as before (existing 11 store tests unchanged). Only the Trends runner passes the new mode.
- **Point-in-time (owner wish: frozen per pull date).** Replacing revises the past in the live series. So every Trends run also writes `<cache>/attention/trends_pulls/<pull-date>.parquet` (columns symbol, date, value; only coins that passed the interest rule; one row per coin and day, about 75 x 100 rows). A second run on the same pull date adds only symbols not already archived (first write per symbol and pull date wins). Written in T100b because the pulled values cannot be recovered later. The reader (history for a past day D using the pull dated D) is NOT in T100b and is proposed as a follow-up (heading 10 of the report).
- **Frozen snapshots.** The nine-plus files under `api/data/cache/attention/signals/` are copies of computed output and are not read by the store; gate G7 proves their hashes do not change.

## 5. Fetch and runner design (T100b)

- `api/data/attention/trends.py`: keeps `fetch_series` (ticker path, still used by tests; marked superseded in its docstring) and adds `fetch_alone(symbol, term, client, *, today, timeframe)`. One `build_payload([term], timeframe=timeframe, geo="")` + `interest_over_time()` call. Rules: frame must contain the term column; index step must be exactly 1 day everywhere else rejected as `non-daily`; drop `isPartial` rows and any row with date `>= today`; values to float; fewer than 90 complete days gives state `insufficient-history`; apply the interest rule; else state `ok`. Never raises; reasons carry the exception class and HTTP status only (the `trends_cli_common` policy, T100a). The client is injected (a `TrendReq`-like object); tests use a fake.
- `api/scripts/refresh_attention.py`: `_run_trends` loads the keyword file with `trends_keywords.safe_load(placed_symbols=...)` (a bad file gives `unavailable`, reason `bad keyword file`, for every coin, no crash); symbols without a keyword, `no-keyword` entries and name-risk `term` entries become `unavailable` with their reason and cost no request; the rest are fetched in a rotated order (start index = the UTC day number modulo the list length) so a budget stop does not always starve the same coins; spacing `TRENDS_INTERVAL_S = 3.0` plus jitter 0 to 2 s through the injected `sleep`; on HTTP 429 back off 30 s, 60 s, 120 s for the same coin (three tries) then mark `capped` (rate-limited); three coins in a row ending rate-limited stop the source (circuit breaker, like `CIRCUIT_BREAKER_AFTER = 5` at `refresh_attention.py:34` but 3, as the SPEC says); a Trends-specific time budget `TRENDS_TIME_BUDGET_S = 540` (the shared `SOURCE_TIME_BUDGET_S = 360` at line 37 is below the 75-coin worst case; the workflow step timeout is raised in T100c). The run writes with `mode="replace-series"`, writes the pull archive, and prints one summary line with counts: `ok`, `too-little-interest`, `name-ambiguous`, `no-keyword`, `non-daily`, `rate-limited`, `insufficient-history`, `failed(class)`.
- `api/data/pytrends_adapter.py` is not edited. `pytrends` stays out of `api/pyproject.toml` (the run uses `--with pytrends`; whether to declare it is the owner's call in T100c).
- `api/scripts/probe_trends.py` gains `--alone SYMBOLS`: one request per symbol, only that term, prints days, min, median, max, number of days at 0, at 0 or 1, distinct values and the share of zero days, plus the verdict the rule would give. This is the owner probe P-RES (section 8). It belongs to slice T100b because no option of the existing tools requests one term alone (verified: `probe_trends` always sends `[anchor + 4 coins]` and two evidence requests of `[A, B, coins]`, `probe_trends.py:243-261`).

## 6. Slices, files, order, cost

| Slice | Approval | Model / tier | Branch | Cost (USD) |
|---|---|---|---|---|
| T100b store mode + fetch alone + interest rule + name-risk skip + runner + archive + `--alone` probe option + tests | Owner's own ENTER EXECUTE MODE | opus (source code), RT2 | `claude/t100b-trends-fetch` | estimate 5 to 7; ask at 6; hard cap 10 |
| T100c daily workflow integration | Owner's SEPARATE approval of the `.github/` change, then ENTER EXECUTE MODE | sonnet (YAML, docs, no code logic), RT0/RT2 | `claude/t100c-trends-workflow` | estimate 2 to 3; ask at 3; hard cap 5 |

Order: T100b merges; owner runs P-RES (and the checker for the 12 risky names); thresholds are set; then T100c. T100c must not start before P-GH/P-RES tell whether Google answers a GitHub runner (SPEC section 4).

**T100b file list (nine paths, collision proof against T100a: only new test and edit sections, no T100a file is edited except `probe_trends.py`):**
1. `api/data/attention/store.py` (edit: `mode` parameter, `trends_pulls` archive helper)
2. `api/data/attention/trends.py` (edit: `fetch_alone`, constants, interest rule, `NAME_RISK_SYMBOLS`)
3. `api/scripts/refresh_attention.py` (edit: `_run_trends`, Trends budget and spacing constants)
4. `api/scripts/probe_trends.py` (edit: `--alone`)
5. `api/tests/data/attention/test_store.py` (edit: replace-series tests)
6. `api/tests/data/attention/test_trends.py` (edit: fetch_alone and rule tests)
7. `api/tests/data/attention/test_trends_pull.py` (new: archive and an end-to-end fake pull)
8. `api/tests/scripts/test_refresh_attention_trends.py` (new: runner tests, 429, breaker, rotation, skips)
9. `api/tests/scripts/test_probe_trends.py` (edit: `--alone` tests)
Forbidden: `.github/`, `web/`, `api/pyproject.toml`, `api/uv.lock`, `api/data/cache/`, `api/data/trends_keywords.json`, `api/data/attention/probe_records.json`, `api/data/pytrends_adapter.py`, `api/analytics/`, any SPEC or other process file.

**T100c file list (blocked on owner approval):** `.github/workflows/attention-refresh.yml` (trends step: `--with pytrends`; step `timeout-minutes` from 8 to 14; failure class in the log; the trends step must not abort the other extra steps if Google refuses the runner); `api/data/attention/probe_records.json` via `api/scripts/record_probe.py` after the first real run; the sources-panel last-failure line (`web/` file UNVERIFIED, may be split off as T100d); `api/tests/tooling_guards/test_attention_workflow_guard.py` and `api/tests/scripts/test_ci_workflow.py` expectations if the guards pin the step. **This session writes no workflow text.** T100c description for the owner's approval: change one workflow step so the daily job installs `pytrends` for the Trends step (the likely reason the step took 1 second, SPEC section 1), raises its time limit to fit about 75 requests at 3 s spacing, and logs the failure class; nothing else in `.github/` changes.

## 7. Red tests (written first; each fails before the code exists)

`test_store.py` (+7): `test_replace_series_drops_old_rows`, `test_replace_series_ignores_today_and_future`, `test_replace_series_short_pull_keeps_old_series`, `test_replace_series_is_atomic_on_write_error` (monkeypatch the writer, old file intact), `test_default_mode_unchanged_first_wins`, `test_replace_series_sorted_and_returns_count`, `test_replace_mode_rejects_unknown_mode`.
`test_trends.py` (+14): `test_fetch_alone_builds_single_term_payload` (fake client records one term), `test_fetch_alone_drops_partial_and_today`, `test_fetch_alone_rejects_non_daily_step`, `test_fetch_alone_missing_column_unavailable`, `test_fetch_alone_under_90_days_insufficient_history`, `test_fetch_alone_100_rows_ok`, `test_all_zero_series_too_little_interest`, `test_low_median_too_little_interest`, `test_many_zero_days_too_little_interest`, `test_interest_rule_never_writes_zero`, `test_percent_change_invariant_to_series_scale` (series times 0.5 and 3.7 give the same `discovery._source_change`, tolerance 1e-9; this is the executable form of the key-question answer), `test_fetch_alone_exception_reports_class_only` (sentinel in message not in reason), `test_http_429_reason_has_status`, `test_name_risk_symbols_match_t125_list`.
`test_trends_pull.py` (+6): `test_archive_written_per_pull_date`, `test_archive_second_run_adds_missing_symbols_only`, `test_archive_excludes_missing_coins`, `test_archive_roundtrip_values`, `test_replace_then_archive_end_to_end_two_days` (day 1 and day 2 pulls on different scales: stored series is the day 2 pull whole, archive holds both days separately), `test_frozen_signals_files_untouched` (hash before and after).
`test_refresh_attention_trends.py` (+13): `test_bad_keyword_file_all_unavailable`, `test_no_keyword_costs_no_request`, `test_name_risk_term_skipped_topic_fetched`, `test_one_request_per_keyword_coin`, `test_spacing_uses_injected_sleep`, `test_rotation_start_depends_on_day`, `test_429_backoff_30_60_120_then_capped`, `test_three_capped_in_a_row_stops_source`, `test_one_failure_does_not_touch_other_coins`, `test_failed_coin_keeps_previous_series`, `test_time_budget_caps_the_rest`, `test_summary_line_counts_every_outcome`, `test_exit_code_success_with_rate_limited_count`.
`test_probe_trends.py` (+5): `test_alone_one_request_per_symbol`, `test_alone_prints_stats_and_verdict`, `test_alone_rejects_bad_symbol_list`, `test_alone_429_stops_and_reports`, `test_alone_output_has_no_message_or_header`.
Total named: 45. No test opens a network connection; fakes only.

## 8. Owner probes

Run on the owner's PC from the repo root (PowerShell; quote comma lists; the first two work TODAY with the T100a tools):

```
# P-CHK  topic ids for the 12 risky names (checker as it exists today)
uv run --project api --with pytrends python -m api.scripts.check_trends_keywords --symbols 'TRX,ONDO,MORPHO,ICP,SHIB,PEPE,BNB,CRO,HBAR,LINK,APT,SOL'

# P-BATCH  (optional, existing probe) reproduces the crush for small coins inside a Bitcoin/Ethereum batch
uv run --project api --with pytrends python -m api.scripts.probe_trends --coins 'LINK,AAVE,INJ,MORPHO,ONDO,PEPE'

# P-RES  AFTER T100b merges (needs the new --alone option; slice T100b):
# single-term resolution of 6 small coins over an explicit 100-day daily range (replace the two dates:
# end = yesterday, start = end minus 99 days)
uv run --project api --with pytrends python -m api.scripts.probe_trends --alone 'LINK,AAVE,INJ,MORPHO,ONDO,PEPE' --timeframe '2026-07-13 2026-10-20'

# P-RES-B  the same with the default window, to compare with the explicit range
uv run --project api --with pytrends python -m api.scripts.probe_trends --alone 'LINK,AAVE,INJ,MORPHO,ONDO,PEPE'
```
(The `--timeframe` option exists today with the explicit-date pattern, `probe_trends.py:46`.) Paste the printed output back. What it decides: (1) whether each coin alone has median at least 3 and fewer than 40 percent zero days (the two placeholders of section 3); (2) whether the explicit 100-day range returns 100 daily rows; (3) the real request latency and any 429 over 6 spaced requests. Tier boundaries (design 2) are NOT needed for the recommended design; if P-RES shows several coins are empty alone, those coins stay `unavailable` and tiering stays rejected. P-GH (does Google answer a GitHub runner) belongs to T100c and needs the owner's workflow approval.

## 9. Rollback and risks

Rollback: revert the T100b PR (the store default is unchanged; the new files are additive). Archive files can be deleted without effect.
Risks: R1 75 requests may draw a 429 on some day (breaker plus rotation limit the loss; a failed coin keeps its previous series and ages out after 3 days). R2 pytrends is archived and Google can change the endpoint (presumed-dead logic exists in `pytrends_adapter.py`, unchanged). R3 an explicit range may not be daily at 100 days (P-RES; fallback `today 3-m` with `MIN_REPLACE_DAYS` lowered to 85 would then violate the 90-point gate, so the fallback is "insufficient-history until 90 days accumulate", not silent). R4 the two interest-rule numbers are guesses until P-RES. R5 revision of past values by each replace (owner decision: revised; archive keeps the first-seen pull). R6 Trends terms of use for automation are unclear (keep volume low: about 75 requests a day).

## Acceptance Criteria

- **AC-B1** A coin with a keyword is requested alone; one request per coin; no anchor term is sent (tests `test_fetch_alone_builds_single_term_payload`, `test_one_request_per_keyword_coin`).
- **AC-B2** `write_series(mode="replace-series")` replaces the whole stored series, never stores `d >= today`, and never lets a pull of fewer than 90 complete days shrink a stored series; default mode is unchanged.
- **AC-B3** A series multiplied by any positive constant gives the same Discovery change (`test_percent_change_invariant_to_series_scale`).
- **AC-B4** A too-sparse series is `unavailable` / `too-little-interest`, writes nothing, and is never stored as 0.
- **AC-B5** The 12 name-risk coins with only a `term` are skipped without a request; with a `topic` they are fetched.
- **AC-B6** 429 handling: 30 s, 60 s, 120 s backoff, then `capped`; three capped coins in a row stop the source; other coins keep their series.
- **AC-B7** Every run writes one per-pull archive file; a second run on the same date adds only missing symbols.
- **AC-B8** `probe_trends --alone` prints per-coin stats and the rule verdict, no message, header or cookie.
- **AC-B9** No frozen signals file changes (G7); no file outside section 6 changes (G6).
- **AC-C1 (T100c, after owner approval)** The workflow Trends step installs `pytrends`, has a timeout that fits the run, logs the failure class, and does not abort the other extra steps.

## Implementation Checklist (phased delivery)

**Phase 1, T100b (opus, owner ENTER EXECUTE MODE):**
1. Write the red tests of section 7 and quote the failing run.
2. `store.py`: `mode="replace-series"` and the archive helper.
3. `trends.py`: `fetch_alone`, interest rule constants, `NAME_RISK_SYMBOLS`.
4. `refresh_attention.py`: `_run_trends` (keyword file, rotation, spacing, 429 backoff, breaker, budget, summary).
5. `probe_trends.py`: `--alone`.
6. Run gates G1 to G12; write the report.

**Phase 2, owner:** P-CHK, P-RES (section 8); set the two interest-rule numbers; paste topics for the 12 risky names.

**Phase 3, T100c (sonnet, only after the owner approves the `.github/` change):** workflow step, probe record, panel line, gates of the T100c section.

## Touchpoints

`api/data/attention/store.py`, `trends.py`; `api/scripts/refresh_attention.py`, `probe_trends.py`; tests above. T100c: `.github/workflows/attention-refresh.yml`.

## Public Contracts

`store.write_series(series, today=None, mode="first")` keeps its signature and default behaviour. `trends.fetch_series` unchanged. `SourceSeries` unchanged (`api/data/attention/types.py`). The CLI of `refresh_attention.py` unchanged. `probe_trends.py` gains one option; its exit codes (0, 1, 2, 3) are unchanged.

## Blast Radius

Only the Trends source changes behaviour. Wikipedia, CoinGecko, Reddit, X and exchange sources keep `mode="first"` (their store tests are the proof). The Discovery response gains Trends rising votes for coins that reach 90 days; coins without a Trends series are unchanged. No web or API contract changes.

## Verification Evidence

Baselines and cites in the Validate Contract. Owner evidence (real Google, 21-10-26) is quoted from the task envelope and was not re-measured here.

## Resume and Execution Handoff

Handoff to the planner: send the T100b envelope (section 6 file list, forbidden list, gates G1 to G12, ask 6 / cap 10 USD, opus). The owner types ENTER EXECUTE MODE for T100b. T100c waits for the owner's written approval of the `.github/` change described in section 6.

## Validate Contract

Status: PASS
Date: 2026-10-21
date: 2026-10-21
generated-by: outer-pvl
Code under test: `main` 4675f82 (fresh `origin/main`, 21-10-26 UTC). Method: FAST MODE, two layers in one session (T144). Layer 1: infra, test coverage, breaking changes, security on this PLAN. Layer 2: per-section feasibility with every cite re-read on 4675f82. Findings F1 to F7 are fixed in the text above.

### Baselines (main 4675f82, measured this session with `UV_FROZEN=1`)

| What | Command (repo root) | Result |
|---|---|---|
| Store + trends tests | `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_store.py api/tests/data/attention/test_trends.py -q` | 17 passed |
| data/attention + pytrends group | `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/data/test_pytrends_adapter.py api/tests/scripts/test_backfill_pytrends_history.py -q` | 195 passed, 2.7 s |
| Scripts tests | `UV_FROZEN=1 uv run --project api pytest api/tests/scripts -q` | 346 passed, 2 warnings, 43.0 s |
| Attention analytics suite | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention -q` | 281 passed, 2 warnings, 15.3 s |
| Workflow guards | `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards/test_attention_workflow_guard.py api/tests/scripts/test_ci_workflow.py -q` | 22 passed |
| Full API | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 1861 passed, 1 skipped, 5 deselected, 2 warnings, 144.6 s |
| Frozen signal snapshots | `git ls-files api/data/cache/attention/signals \| wc -l` | 12 files (3 windows x 17 to 20 Oct); the count grows daily |
| Keyword file | `python3 -c "import json;d=json.load(open('api/data/trends_keywords.json'));print(len(d)-1)"` | 75 coins: 43 term, 0 topic, 32 no-keyword |
| Plan validator on a baseline plan | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-trends-t100a_PLAN_21-10-26.md` | 0 failures |

### Test gates for T100b (exact commands; Pass rule: 0 failed; skipped and deselected unchanged at 1 and 5; passed counts at least the floor, d = tests deleted or replaced, each listed in the report with its reason)

| Gate | Command | Pass criterion |
|---|---|---|
| G1 new and extended tests | `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_store.py api/tests/data/attention/test_trends.py api/tests/data/attention/test_trends_pull.py api/tests/scripts/test_refresh_attention_trends.py api/tests/scripts/test_probe_trends.py -q` | 0 failed; at least 17 + 7 + 14 + 6 + 13 + 5 = 62 passed plus the existing probe tests; red-first evidence: the report quotes the failing run before the code existed |
| G2 data group | the 195 row command | 0 failed; at least 195 + 27 = 222 passed |
| G3 scripts suite | `UV_FROZEN=1 uv run --project api pytest api/tests/scripts -q` | 0 failed; at least 346 + 18 = 364 passed |
| G4 attention analytics | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention -q` | exactly 281 passed (nothing there is edited) |
| G5 full API (once, by the tester) | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 0 failed; at least 1861 + 45 = 1906 passed, 1 skipped, 5 deselected |
| G6 forbidden paths and exact file set | `git fetch origin main && git diff --name-only origin/main...HEAD \| sort` | prints exactly the nine paths of section 6 plus the report and task-folder files, nothing under `.github`, `web`, `api/pyproject.toml`, `api/uv.lock`, `api/data/cache`, `api/data/trends_keywords.json`, `api/data/pytrends_adapter.py` |
| G7 frozen snapshots | `cd api/data/cache/attention/signals && sha256sum -c` over the hashes of the 2026-10-17 files: `eb4730e44d5f7f17d86fc1e704a87c69b1a247d4fc1ab41aca0555f226bbcdde  2026-10-17_w30.json`, `597fb394fcfc3207c5f8adfc35e57827f39cf81e6cff031787678a2e76d6aef1  2026-10-17_w7.json`, `09946558044b0bfa7093dfeb5fe1ab586eca6b762fd89301b807eb01ec9909ac  2026-10-17_w90.json` | three lines `OK` |
| G8 hygiene | `git diff --check origin/main...HEAD` and `git diff -U0 origin/main...HEAD \| grep -nE "^\+.*(Bearer [A-Za-z0-9._-]{12,}\|(API_?KEY\|SECRET\|TOKEN\|PASSWORD)[A-Z_]* *[:=] *[\"'][A-Za-z0-9+/_-]{12,})"` | `diff --check` exit 0; scan prints nothing (sentinels built from two string parts) |
| G9 scale invariance | `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_trends.py -q -k "percent_change_invariant"` | 1 passed (the key-question proof) |
| G10 no network, no pytrends at import | `UV_FROZEN=1 uv run --project api python -c "import api.data.attention.trends, api.data.attention.store, api.scripts.refresh_attention, api.scripts.probe_trends"` and `grep -nE "^\s*(import\|from) +(requests\|httpx\|socket\|urllib\|pytrends)" api/data/attention/trends.py api/data/attention/store.py` | import exit 0; grep prints nothing |
| G11 default store mode unchanged | `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_store.py api/tests/data/attention/test_wikipedia.py api/tests/data/attention/test_reddit.py -q` | 0 failed, counts not below baseline |
| G12 plan validator | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-trends-t100b_PLAN_21-10-26.md` | 0 failures; warnings recorded in the validation record |

### T100c gates (not run now; blocked on owner approval)

`UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards/test_attention_workflow_guard.py api/tests/scripts/test_ci_workflow.py -q` (22 passed baseline, 0 failed after), `git diff --name-only origin/main...HEAD` shows only the T100c files, and a `workflow_dispatch` run on the owner's repo whose log shows the failure-class line (owner step, P-GH).

### Owner probes and rollback

Probes: section 8. Rollback: section 9.

### Hard stops (verbatim for the /goal block)

- Any change under `.github/`, `web/`, `api/pyproject.toml`, `api/uv.lock`, `api/data/cache/`, `api/data/trends_keywords.json`, `api/data/pytrends_adapter.py`, `api/analytics/`, any SPEC: stop and report.
- Any `topic` value written to the keyword file by the worker: stop and report (topics come from the owner's checker run only).
- A test, tool or script that opens a network connection, prints an exception message, header, cookie or token, or calls Google: stop and report.
- A frozen snapshot hash of G7 differs: stop and report.
- A baseline on fresh main differs from the table above by anything other than a merged earlier PR: stop and report the numbers.
- The default store mode behaviour changes (G11): stop.
- Slice cost at 6 USD: ask; hard cap 10 USD. Never merge any PR. `needs_input`: stop; do not open a new PR.

### Dimension findings (after the fixes in this PLAN)

| Dimension | Status | Evidence |
|---|---|---|
| infra/setup-fit | PASS | every cited file and line exists on 4675f82; baselines measured; fake-client pattern exists in `api/tests/scripts/test_probe_trends.py` and `trends_fixtures.py`; no new dependency |
| test-coverage | PASS | 45 named red tests; the key claim has an executable test (G9); live behaviour is a recorded known gap with owner probes |
| breaking-changes | PASS | `write_series` default unchanged (G11); no existing contract changed; `probe_trends` gains an option only; keyword file not edited |
| security-surface | PASS | exception class and HTTP status only in any output; terms come from the validated keyword file; no secret, header or cookie is read or printed; archive path built from a validated date and symbols matching `SYMBOL_RE` |

### Findings of this validation

| # | Finding | Severity | Fix |
|---|---|---|---|
| F1 | SPEC "keep dates outside the new window" leaves old-scale rows inside the 97-day compared span | CONCERN | replace-series (drop old rows) with a short-pull guard |
| F2 | `today 3-m` can return 89 to 92 complete days, under the 90-point gates (`registry.py:49`, `ratio.py:16`) | CONCERN | explicit 100-day range, probed by P-RES; short pull never replaces a good series |
| F3 | Alone, every series peaks at 100, so a level test for "too little interest" cannot work | CONCERN | sparsity rule (median, zero-day share) |
| F4 | Existing probe cannot request one term alone | CONCERN | `--alone` option, slice T100b |
| F5 | Shared `SOURCE_TIME_BUDGET_S = 360` is below the 75-coin worst case | CONCERN | Trends-specific 540 s budget in T100b; workflow timeout in T100c |
| F6 | Risky bare names would ingest wrong series | CONCERN | `NAME_RISK_SYMBOLS` skip until a topic exists |
| F7 | Revising the live series loses point-in-time values | CONCERN | per-pull archive in T100b; reader deferred |

### Open gaps

None blocking T100b. Recorded known gaps: every live Google behaviour (alone-request resolution, daily at 100 days, 429 threshold at 43 to 75 requests, GitHub runner reachability) is UNVERIFIED and covered by P-RES and P-GH only; the two interest-rule numbers are placeholders; T100c waits on the owner.

### What This Coverage Does NOT Prove

The gates drive fakes. They do not prove that Google returns daily rows for an explicit 100-day range, that a single small coin has real structure when requested alone, that 75 requests at 3 s spacing avoid a 429, or that a GitHub runner is answered at all. The owner-evidence numbers (0.5 s latency, integers 0 to 100, 93 rows, the crushed medians) are quoted from the task envelope, not re-measured.

### Accepted by

session (T144 worker, 21-10-26, docs only), on the planner's envelope. Not yet accepted by the owner: the departures from the SPEC (anchor dropped, replace-series, explicit range, archive), the placeholder numbers, the cost thresholds, and T100c.

## Validation record (T144, 21-10-26)

Layer 1 and Layer 2 as in the Validate Contract header. All seven findings are fixed in the text above. Plan validator result is recorded in the T144 report (heading 6).
