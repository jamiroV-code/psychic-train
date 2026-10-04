# T32 / S1 freshness core: worker report (04-10-26)

## 1 Task ID

T32 (screener batch 1, slice S1: freshness core). Branch `claude/t32-s1-freshness-core`, from `main` 8c235b7.

## 2 Outcome

done (status `review`). Gates G-S1-1 to G-S1-11 pass. P-S1-1 is a user-PC probe and is not claimed. Not merged: self-merge condition (f) (planner records `accepted` and then `archived`) has not happened, and P-S1-1 is still open.

## 3 Summary

- **Forming candle expires.** A cache counts as fresh only if it was fetched inside the current bar and less than `FORMING_TTL` ago (15m 180 s, 1h 300 s, 4h 900 s, 1d 900 s). The fetch time is stored in an atomic sidecar, `<tf>.meta.json`, written after the parquet. When there is no sidecar, the parquet mtime is used.
- **Gap bug fixed.** With `since=None`, the adapter now requests the latest `TAIL_LIMIT` bars (200 for sub-daily, 500 for 1d) through `_tail_since()`, which returns None today.
  - A sub-daily tail that does not touch the cache replaces it (`note="gap-replaced"`).
  - A non-contiguous 1d tail keeps the deep history and appends the new bars (`note="gap-kept"`).
  - An empty response writes nothing.
  - On this path only, a newest bar past the staleness threshold gives status `stale`. The explicit-`since` path is unchanged and never returns `stale`.
- **Sub-daily history bounded.** 15m, 1h and 4h keep their newest 200 bars on every adapter write. 1d is never trimmed.
- **Payload freshness fields.**
  - `ChartSeries` gains `last_bar_ts`, `fetched_at`, `is_partial`, `server_time` (all ISO-8601 with a trailing `Z`) and `stale`.
  - `stale` is computed from the last bar's age, not from the adapter status. For 1w it is computed from the daily bar.
  - `ScreenerBoardResponse` gains `server_time`, `clock_skew_seconds` and `clock_skew_warning`.
  - All of these are mirrored in `screener.ts`.
- **Clock skew.** Measured on the live path at most once every 15 minutes, using `fetch_time` bracketed by two host reads. A missing or failing `fetch_time` reads as unknown.
- **Old red proof is green.** The deploy test case `screener_chart_carries_staleness_marker` no longer carries `xfail` and passes.

## 4 Files changed

Owned list only (the G-S1-7 scope check prints nothing):

- `api/data/freshness.py` (new, pure, no ccxt import)
- `api/data/cache.py`: `write_ohlcv(..., *, retain_bars=None, fetched_at=None)`, `ohlcv_meta_path`, `_atomic_write_json`, `read_fetched_at`.
  - `.to_parquet(` still appears exactly once.
  - The frozen API is unchanged: `_atomic_to_parquet`, `CACHE_ROOT`, `OHLCV_COLUMNS`, `bootstrap_cache_dirs`.
- `api/data/ccxt_adapter.py`:
  - added `_now`, `_host_time`, `_tail_since`, `_tail_status`, `reference_now`, `refresh_clock_skew`, `last_clock_skew`, `clock_skew_warning`, `reset_clock_skew`
  - `_cache_is_fresh(cached, timeframe, fetched_at=None, now=None)`
  - `OhlcvResult.fetched_at` and `OhlcvResult.note`, appended after `status` and defaulted
  - the `fetch_ohlcv` signature and `_derive_weekly_from_daily` are unchanged
- `api/models/screener.py`, `api/analytics/screener_board.py`, `web/lib/types/screener.ts`
- New tests:
  - `api/tests/data/test_freshness.py` (5)
  - `api/tests/data/test_ccxt_tail_fetch.py` (12)
  - `api/tests/data/test_cache_fetched_at_retention.py` (6)
  - `api/tests/data/test_ccxt_clock_skew.py` (5)
  - `api/tests/routers/test_screener_freshness_payload.py` (4)
- Edited tests:
  - `api/tests/deploy/test_fresh_deploy_degrade.py` (one case only)
  - `api/tests/data/test_ccxt_symbol_resolution.py` (the two assertions listed in heading 9)
  - fixture builders in `web/components/screener/__tests__/ScreenerBoard.test.tsx` and `DrillDownView.test.tsx` (a `NO_FRESHNESS` spread plus the board-level fields)
- `process/general-plans/active/screener-batch1_03-10-26/s1-probe/probe_freshness.py` (read-only PC probe)
- `process/general-plans/backlog/ohlcv-negative-cache-and-1d-gap-replace_NOTE_04-10-26.md` (D7, D18)
- this report

## 5 Commits

- 82c5062 `feat(screener): T32 S1 freshness core ...` (code, tests, probe, backlog stub)
- report commit: the next commit on the branch after 82c5062. It touches this file only.
- Branch: `claude/t32-s1-freshness-core`, pushed to origin. A PR is opened against `main`.

## 6 Tests run

All gates ran once after the last code edit, at 82c5062. UV_FROZEN=1 was set on every pytest run.

**Red-first (G-S1-11): G-S1-1 on the untouched base, 2026-10-04T01:32:12Z, HEAD 8c235b7.** Only the five new test files had been added; no source file had changed yet.
- Command: `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_freshness.py api/tests/data/test_ccxt_tail_fetch.py api/tests/data/test_cache_fetched_at_retention.py api/tests/data/test_ccxt_clock_skew.py api/tests/routers/test_screener_freshness_payload.py -q`
- Result: **26 failed, 2 passed, 4 errors**.
- The two that passed are `test_explicit_since_path_unchanged_for_backfill` and `test_one_day_bars_are_never_trimmed`. Both guard behaviour that already holds on base.
- The four errors are setup errors in the skew fixture, because `reset_clock_skew` is missing on base.
- Behavioural reds, each an assertion failure and not an import error:
  - `test_forming_candle_refresh_after_ttl`: `AssertionError: the forming candle must be refetched once its TTL has passed`. Base made 1 exchange call where 2 were expected.
  - `test_500_bar_gap_regression_catches_up`: newest bar `2026-10-03 05:45` against the expected `2026-10-04 01:00`. That is 77 bars behind after one refresh.
  - `test_trim_on_write_15m_1h_4h_keeps_newest_200`: `AssertionError: 15m`. The file held 502 rows, not 200.
- The deploy case under `--runxfail` on base, same time and SHA: `1 failed, 10 passed`. The failure is `test_aged_cache_regime_and_screener_never_500_and_no_nan[screener_chart_carries_staleness_marker]`.
- Base full-suite baseline at 8c235b7, run at spawn (full-suite run 1 of 2): `870 passed, 1 skipped, 5 deselected, 1 xfailed`.

**Gates at 82c5062:**

| Gate | UTC | Result |
|---|---|---|
| G-S1-1 (command above) | 2026-10-04T01:38:26Z | 32 passed (exit 0) |
| G-S1-2 `UV_FROZEN=1 uv run --project api pytest api/ -q` (full-suite run 2 of 2) | 2026-10-04T01:38:26Z | 903 passed, 1 skipped, 5 deselected, 0 xfailed (exit 0) |
| G-S1-3 `pnpm --filter web test` | 2026-10-04T01:38:39Z | 30 files, 223 passed |
| G-S1-4 `pnpm --filter web exec tsc --noEmit --incremental false` | 2026-10-04T01:38:34Z | exit 0, no output |
| G-S1-5 `cd web && pnpm build:islands` | 2026-10-04T01:38:52Z | `built in 5.89s`, exit 0 |
| G-S1-6 `git diff --check` | 2026-10-04T01:38:59Z | exit 0, no output |
| G-S1-7 S1-scope | 2026-10-04T01:42Z | prints nothing |
| G-S1-7b FORBIDDEN | 2026-10-04T01:42Z | prints nothing |
| G-S1-8 `... pytest api/tests/deploy/test_fresh_deploy_degrade.py -q` | 2026-10-04T01:38:29Z | 11 passed, 0 xfailed |
| G-S1-9 `... pytest api/tests/data/test_cache_atomic_writes.py -q` | 2026-10-04T01:38:33Z | 26 passed (includes `test_no_bypass`) |
| G-S1-10 FIXTURES | 2026-10-04T01:42Z | prints nothing |
| G-S1-11 red-first record | n/a | present (above) |

- The scope commands (G-S1-7, G-S1-7b, G-S1-10) are re-run after the report commit, because they read the branch diff.
- The web deps were not installed in the container, so before G-S1-3/4/5 I ran `pnpm install --frozen-lockfile` in `web/`. The lockfile is unchanged.

## 7 Tests NOT run

- **P-S1-1** (user PC): `uv run --project api python process/general-plans/active/screener-batch1_03-10-26/s1-probe/probe_freshness.py`.
  - The sandbox cannot reach `api.hyperliquid.xyz`, so (b), (c) and (d) are unverifiable here.
  - (a) was smoke-run against a temporary cache and printed the table with the sidecar source.
  - AC-S1-2r and AC-S1-6r stay class C. If (c) shows that `since=None` does not return the latest bars, the fallback is a one-line `_tail_since` change, described in its docstring.
- CI has not run yet at the time of writing. The tester or planner confirms it on the PR.

## 8 Deviations

- **Unavailable charts set `server_time` to null.** The plan says an unavailable chart "has nulls". I read that literally, so `server_time` is null there too. The board-level `server_time` is always set.
- **Skew is measured on the non-injected path only.** Measurement uses the process-wide exchange (`_exchange()`), never an injected test double, which matches "reusing the already-built exchange". `test_skew_measured_once_per_15_minutes` drives that live path through a patched `ccxt.hyperliquid`.
- **The cache-fresh short-circuit also reports `stale`.** On the since=None path it reports `stale` when the newest cached bar is past the threshold (for example a delisted coin), so every since=None return applies B5 consistently.
- **`build_scalp_view` makes one extra fetch at `1w`.** It fetches `1d` so that weekly staleness is judged on the daily bar. That fetch is a cache hit when it is fresh.
- **Gate counts are kept without parametrization.** Multi-timeframe cases run as in-test loops so that G-S1-1 counts exactly 32 tests.

## 9 Blockers

No blockers.

**Test-assertion edits (D3, N2), in `test_ccxt_symbol_resolution.py`:**
- `test_a_cold_cache_still_reaches_the_exchange`: the clock is injected (`_now` = 2026-10-03T14:10Z), and the module's fake bar is monkeypatched to that clock's current daily open. The test still asserts `status == "ok"`.
- `test_weekly_recursion_does_not_deadlock`: the status check is widened to `("ok", "stale", "unavailable")`, because the 2023 fixture bar now reads as `stale`.

**Seed and refresh scripts (not edited, since `api/scripts/**` is forbidden):**
- `seed_e2e_cache.py` writes through `write_ohlcv`, so the seeded bars are stamped `fetched_at` = seed time. Once their TTL expires (3 to 15 min) a request would try a refresh. Offline, that refresh fails and the cached bars are still served (risk 5).
- `refresh_cache.py:74` counts a coin with status `stale` as not ok. This is benign: such a coin really has an old newest bar.

**Risks:**
- Do not deploy S1 alone. A board opened after idle can refetch up to 120 (coin, timeframe) pairs, which is above the web client's 10 s timeout. S8 solves this, and P-S1-1 (d) measures it.
- Failed fetches are not negatively cached (backlog stub, D7).

**Registry-update request:** please record T32 S1 as `review`. After the planner's check, record `accepted` and then `archived` with refs 82c5062 and the report commit. P-S1-1 is pending on the user PC.

## 10 Follow-up

- Run P-S1-1 on the user PC. If (c) shows the oldest bars for `since=None`, switch `_tail_since` to the documented fallback.
- Backlog: `process/general-plans/backlog/ohlcv-negative-cache-and-1d-gap-replace_NOTE_04-10-26.md` (D7 retry cost while the exchange is down; D18 holes in daily history).
- S2 and S8 can import `api/data/freshness.py`. S8 must merge before any PC deploy.

## 11 Context cost

**Files loaded:**
- CLAUDE.md
- the envelope
- the plan, by the listed line ranges only
- the S1 source and test files
- `process/development-protocols/master-planner.md`, §9 template and §5 self-merge rule only (on demand, to follow the report template and the merge rule)

operating-instructions.md was not opened.

Approximate tokens: about 130k input. Tools: Bash, Read, Write, Edit, Agent, GitHub MCP.

**Subagents (capped lane, 2 of 3 used, sonnet):**
1. `vc-code-reviewer` (sonnet), read-only, diffed `api/models/screener.py` against `web/lib/types/screener.ts` at 82c5062.
   - Result: no mismatches in the 8 new fields or in the existing models.
   - It confirmed that every freshness field is filled with its declared type and that timestamps end in `Z`.
   - About 46k tokens, 9 tool calls.
2. `vc-tester` (sonnet): not spawned. Every gate in heading 6 was run directly; CI confirmation is left to the PR checks.

Cost estimate: within 2 to 5 USD (unmeasured).
